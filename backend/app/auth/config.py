"""Trusted authentication configuration and the JWKS SSRF boundary.

ADR-0063 section 3a draws one line and everything here enforces it:

  TRUSTED STATIC CONFIGURATION   the issuer, supplied at deploy time, fixed for
                                 the process lifetime.
  ATTACKER-CONTROLLED RUNTIME    anything in a request -- headers, body, and
                                 THE TOKEN ITSELF, including its `iss` and
                                 `kid` claims.

The token's `iss` is COMPARED against the configured issuer. It is never used
to LOCATE the key set. Choosing a JWKS URL from a claim inside a token nobody
has verified yet is the path from "we validate the issuer" to "the attacker
picks the signing key".
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from .errors import ConfigurationError

JWKS_PATH = "/.well-known/jwks.json"


@dataclass(frozen=True)
class AuthConfig:
    """Immutable, trusted configuration.

    Built once at startup from deployment configuration. Nothing derived from a
    request may construct or mutate it.
    """

    issuer: str
    jwks_url: str
    expected_host: str

    @classmethod
    def from_issuer(cls, issuer: str) -> "AuthConfig":
        """Derive everything from the one trusted value.

        The JWKS URL is NOT independently configurable. There is therefore no
        second value to misconfigure, and no separate knob for an attacker or a
        careless deploy to point somewhere else.
        """
        if not issuer or not isinstance(issuer, str):
            raise ConfigurationError("issuer must be a non-empty string")

        issuer = issuer.rstrip("/")
        parts = urlparse(issuer)

        if parts.scheme != "https":
            raise ConfigurationError(
                f"issuer must use https, got {parts.scheme!r}. Verification keys "
                "fetched over http can be substituted in transit."
            )
        if not parts.netloc:
            raise ConfigurationError("issuer has no host")
        if parts.query or parts.fragment:
            raise ConfigurationError("issuer must not carry a query or fragment")

        jwks_url = urlunparse(
            (parts.scheme, parts.netloc, parts.path + JWKS_PATH, "", "", "")
        )
        return cls(issuer=issuer, jwks_url=jwks_url, expected_host=parts.netloc)

    def assert_url_allowed(self, url: str) -> None:
        """Reject any URL that is not https on exactly the configured host.

        Host comparison is EXACT EQUALITY, never a suffix test.

        A `*.supabase.co` suffix test would be worse than useless here: anyone
        can create a Supabase project, so `evil.supabase.co` would pass while
        looking like a tightened control, and the attacker would then be serving
        the key set Aaroh trusts. The configured host is the boundary; the
        `.supabase.co` shape is incidental to it.
        """
        parts = urlparse(url)
        if parts.scheme != "https":
            raise ConfigurationError(f"refusing non-https JWKS URL: scheme={parts.scheme!r}")
        if parts.netloc != self.expected_host:
            raise ConfigurationError(
                "refusing JWKS URL whose host does not exactly match the "
                "configured issuer host"
            )
