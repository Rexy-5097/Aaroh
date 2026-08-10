"""JWT verification (ADR-0063 sections 1 and 2).

Turns a bearer token into a VerifiedIdentity, or raises. There is no third
outcome: nothing here returns a partially-trusted result.
"""

from __future__ import annotations

import time
from typing import Any, Callable
from uuid import UUID

import jwt

from .config import AuthConfig
from .errors import AuthenticationError
from .identity import AUTHENTICATED_ROLE, VerifiedIdentity, _build
from .jwks import JwksCache

# Pinned allow-list. Asymmetric only.
#
# This tuple is the algorithm-confusion defence (ADR-0063 J2). If HS256 were
# present, an attacker could HMAC-sign a token using the PUBLIC key as the
# shared secret and the library would happily verify it. The token's own `alg`
# header selects only from this list -- it never extends it.
#
# RS256 is included so a provider-side move between asymmetric algorithms does
# not require a code change. Adding HS256 or "none" here is a security
# regression and is blocked by governance (I-16).
ALLOWED_ALGORITHMS = ("ES256", "RS256")

CLOCK_SKEW_SECONDS = 30
REQUIRED_AUDIENCE = "authenticated"


class JwtVerifier:
    def __init__(
        self,
        config: AuthConfig,
        jwks: JwksCache,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._config = config
        self._jwks = jwks
        self._clock = clock  # UTC epoch seconds; injectable for temporal tests

    def verify(self, token: str) -> VerifiedIdentity:
        """Verify `token` and return the identity it establishes."""
        if not token or not isinstance(token, str):
            raise AuthenticationError("missing_token")

        # The header is read WITHOUT trusting it. `kid` selects a candidate key;
        # `alg` is not consulted here at all -- jwt.decode is given the pinned
        # allow-list, so a hostile header cannot widen what is accepted.
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("malformed_token") from exc

        signing_key = self._jwks.get_key(header.get("kid", ""))

        try:
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=REQUIRED_AUDIENCE,
                issuer=self._config.issuer,
                leeway=CLOCK_SKEW_SECONDS,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("expired") from exc
        except jwt.ImmatureSignatureError as exc:
            raise AuthenticationError("not_yet_valid") from exc
        except jwt.InvalidAudienceError as exc:
            raise AuthenticationError("bad_audience") from exc
        except jwt.InvalidIssuerError as exc:
            raise AuthenticationError("bad_issuer") from exc
        except jwt.MissingRequiredClaimError as exc:
            raise AuthenticationError("missing_claim") from exc
        except jwt.InvalidAlgorithmError as exc:
            raise AuthenticationError("bad_algorithm") from exc
        except jwt.InvalidSignatureError as exc:
            raise AuthenticationError("bad_signature") from exc
        except jwt.PyJWTError as exc:
            raise AuthenticationError("invalid_token") from exc

        self._check_temporal(claims)
        self._check_role(claims)
        subject = self._check_subject(claims)

        return _build(subject, AUTHENTICATED_ROLE)

    # -- claim checks PyJWT does not perform ---------------------------------
    def _check_temporal(self, claims: dict[str, Any]) -> None:
        """Bound `iat` in the future (ADR-0063 section 2, threat J18).

        PyJWT validates that `iat` is a number and, since 2.x, does not reject
        an `iat` in the future. An unbounded `iat` lets a token be minted now
        and held until its window opens, and defeats any later reasoning about
        token age.
        """
        iat = claims.get("iat")
        if iat is None:
            raise AuthenticationError("missing_iat")
        try:
            iat_value = float(iat)
        except (TypeError, ValueError) as exc:
            raise AuthenticationError("malformed_iat") from exc
        if iat_value > self._clock() + CLOCK_SKEW_SECONDS:
            raise AuthenticationError("iat_in_future")

    def _check_role(self, claims: dict[str, Any]) -> None:
        """Allow-list of exactly one role.

        Requiring equality with `authenticated` rejects the anonymous role and
        the privileged bypass role without naming either -- an allow-list of one
        is stricter than a deny-list of two, and stays correct if the provider
        adds a third role later.
        """
        if claims.get("role") != AUTHENTICATED_ROLE:
            raise AuthenticationError("role_not_permitted")
        if claims.get("is_anonymous") is True:
            raise AuthenticationError("anonymous_user")

    def _check_subject(self, claims: dict[str, Any]) -> UUID:
        subject = claims.get("sub")
        if not subject:
            raise AuthenticationError("missing_subject")
        try:
            return UUID(str(subject))
        except (ValueError, TypeError, AttributeError) as exc:
            raise AuthenticationError("subject_not_uuid") from exc
