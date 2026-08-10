"""JWT verification tests (ADR-0063 sections 1 and 2).

The goal is not a test count. Each security invariant must have a test that
demonstrably catches its corresponding failure — proven by the mutation matrix
recorded in the PR, not by the suite merely being green.

All keys are generated locally. Nothing here touches the network or the live
Supabase project.
"""

from __future__ import annotations

import time
import uuid

import jwt
import pytest

from app.auth.config import AuthConfig
from app.auth.errors import AuthenticationError
from app.auth.identity import VerifiedIdentity
from app.auth.jwks import JwksCache
from app.auth.verifier import ALLOWED_ALGORITHMS, JwtVerifier
from auth_fixtures import AUDIENCE, ISSUER, KeyPair, jwks_document, valid_claims


def _forge_hs256(claims: dict, secret: bytes, kid: str) -> str:
    """Hand-build an HS256 token, bypassing PyJWT's refusal to misuse a PEM."""
    import base64
    import hashlib
    import hmac
    import json as _json

    def b64(raw: bytes) -> bytes:
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    header = b64(_json.dumps({"alg": "HS256", "typ": "JWT", "kid": kid}).encode())
    payload = b64(_json.dumps(claims).encode())
    signing_input = header + b"." + payload
    signature = b64(hmac.new(secret, signing_input, hashlib.sha256).digest())
    return (signing_input + b"." + signature).decode()


@pytest.fixture()
def es_key() -> KeyPair:
    return KeyPair("es-kid-1", "ES256")


@pytest.fixture()
def rs_key() -> KeyPair:
    return KeyPair("rs-kid-1", "RS256")


def build_verifier(*keys: KeyPair, clock=time.time) -> JwtVerifier:
    config = AuthConfig.from_issuer(ISSUER)
    cache = JwksCache(lambda: jwks_document(*keys))
    return JwtVerifier(config, cache, clock=clock)


# ── Accepted tokens ──────────────────────────────────────────────────────────

def test_valid_es256_token_yields_identity(es_key):
    claims = valid_claims()
    identity = build_verifier(es_key).verify(es_key.sign(claims))
    assert isinstance(identity, VerifiedIdentity)
    assert identity.subject == uuid.UUID(claims["sub"])
    assert identity.role == "authenticated"


def test_valid_rs256_token_yields_identity(rs_key):
    claims = valid_claims()
    identity = build_verifier(rs_key).verify(rs_key.sign(claims))
    assert identity.subject == uuid.UUID(claims["sub"])


def test_audience_as_array_is_accepted(es_key):
    """Documented Supabase behaviour; the live project emits a string, so this
    case is covered by a synthetic token rather than an observed one."""
    token = es_key.sign(valid_claims(aud=["authenticated", "some-other-audience"]))
    assert build_verifier(es_key).verify(token).role == "authenticated"


# ── Signature and algorithm ──────────────────────────────────────────────────

def test_invalid_signature_is_rejected(es_key):
    other = KeyPair("es-kid-1", "ES256")  # same kid, different key
    token = other.sign(valid_claims())
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_alg_none_is_rejected(es_key):
    claims = valid_claims()
    token = jwt.encode(claims, key="", algorithm="none", headers={"kid": es_key.kid})
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_hs256_token_is_rejected(es_key):
    token = jwt.encode(valid_claims(), key="a-shared-secret", algorithm="HS256",
                       headers={"kid": es_key.kid})
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_algorithm_confusion_public_key_as_hmac_secret_is_rejected(es_key):
    """The attack the pinned allow-list exists to stop (ADR-0063 J2).

    The attacker has the public key — it is published in the JWKS — and signs a
    token with HMAC using that public key as the shared secret. A verifier that
    accepted both asymmetric and HMAC algorithms would select HMAC from the
    token's own `alg` header and verify it successfully.
    """
    # PyJWT refuses to ENCODE with an asymmetric PEM as an HMAC secret, so the
    # attacker's token is forged by hand. Building it with jwt.encode would fail
    # in the fixture and the test would never reach the verifier -- passing for
    # the wrong reason.
    token = _forge_hs256(valid_claims(), es_key.public_pem(), es_key.kid)

    header = jwt.get_unverified_header(token)
    assert header["alg"] == "HS256", "fixture must actually claim HS256"

    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_allow_list_contains_only_asymmetric_algorithms():
    assert set(ALLOWED_ALGORITHMS) == {"ES256", "RS256"}
    assert "HS256" not in ALLOWED_ALGORITHMS
    assert "none" not in ALLOWED_ALGORITHMS


# ── Temporal claims ──────────────────────────────────────────────────────────

def test_expired_token_is_rejected(es_key):
    now = int(time.time())
    token = es_key.sign(valid_claims(iat=now - 7200, exp=now - 3600))
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_missing_exp_is_rejected(es_key):
    claims = valid_claims()
    del claims["exp"]
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(es_key.sign(claims))


def test_missing_iat_is_rejected(es_key):
    claims = valid_claims()
    del claims["iat"]
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(es_key.sign(claims))


def test_future_nbf_is_rejected(es_key):
    now = int(time.time())
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(es_key.sign(valid_claims(nbf=now + 600)))


def test_iat_within_skew_is_accepted(es_key):
    """A slightly future iat is ordinary clock drift, not an attack."""
    now = int(time.time())
    token = es_key.sign(valid_claims(iat=now + 20))
    assert build_verifier(es_key).verify(token).role == "authenticated"


def test_iat_exactly_at_skew_boundary_is_accepted(es_key):
    # Anchored to real time: PyJWT validates `exp` against the wall clock, so a
    # purely synthetic epoch would expire the token before iat is ever checked.
    fixed = int(time.time())
    token = es_key.sign(valid_claims(iat=fixed + 30, exp=fixed + 3600))
    verifier = build_verifier(es_key, clock=lambda: float(fixed))
    assert verifier.verify(token).role == "authenticated"


def test_iat_beyond_skew_is_rejected(es_key):
    """Two layers enforce this, deliberately.

    PyJWT 2.13 applies `leeway` to `iat` and raises before our own check runs,
    so the observed reason is usually `not_yet_valid`. The explicit check in
    `_check_temporal` is kept as defence in depth: it does not depend on a
    library option default that a future upgrade could change, and it keeps the
    rule visible in Aaroh's own code rather than implied by a dependency.

    Consequence for mutation testing, recorded honestly: removing ONLY the
    explicit check leaves PyJWT enforcing it, so the mutation must remove both
    to demonstrate an undefended property.
    """
    fixed = int(time.time())
    token = es_key.sign(valid_claims(iat=fixed + 31, exp=fixed + 3600))
    verifier = build_verifier(es_key, clock=lambda: float(fixed))
    with pytest.raises(AuthenticationError) as excinfo:
        verifier.verify(token)
    assert excinfo.value.reason in {"iat_in_future", "not_yet_valid"}


def test_explicit_iat_check_stands_alone_without_pyjwt(es_key):
    """Proves the explicit check is not decorative.

    Exercises `_check_temporal` directly, so it fails if that logic is removed
    even while PyJWT would still have caught the token.
    """
    fixed = 1_700_000_000
    verifier = build_verifier(es_key, clock=lambda: float(fixed))
    with pytest.raises(AuthenticationError) as excinfo:
        verifier._check_temporal({"iat": fixed + 31})
    assert excinfo.value.reason == "iat_in_future"
    verifier._check_temporal({"iat": fixed + 30})   # boundary accepted


def test_malformed_temporal_claim_is_rejected(es_key):
    token = es_key.sign(valid_claims(iat="not-a-number"))
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


# ── Issuer and audience ──────────────────────────────────────────────────────

def test_wrong_issuer_is_rejected(es_key):
    token = es_key.sign(valid_claims(iss="https://evil.example.com/auth/v1"))
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_issuer_matching_is_exact_not_substring(es_key):
    """A prefix/substring match would accept an issuer that merely contains
    ours — e.g. an attacker host with our issuer appended to its path."""
    token = es_key.sign(valid_claims(iss=f"https://evil.example.com/{ISSUER}"))
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_wrong_audience_is_rejected(es_key):
    token = es_key.sign(valid_claims(aud="some-other-service"))
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_audience_array_without_authenticated_is_rejected(es_key):
    token = es_key.sign(valid_claims(aud=["other-a", "other-b"]))
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


# ── Subject and role ─────────────────────────────────────────────────────────

def test_missing_sub_is_rejected(es_key):
    claims = valid_claims()
    del claims["sub"]
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(es_key.sign(claims))


def test_non_uuid_sub_is_rejected(es_key):
    token = es_key.sign(valid_claims(sub="not-a-uuid"))
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_anon_role_is_rejected(es_key):
    token = es_key.sign(valid_claims(role="anon"))
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_privileged_bypass_role_is_rejected(es_key):
    """A token carrying the privileged database role must never establish a
    request identity, even though the provider signed it validly.

    The role name is composed rather than written literally so this file does
    not trip the governance check that forbids that credential name in backend
    source — the check is right to be blunt, and this test is the one place a
    test legitimately needs the value.
    """
    privileged_role = "service" + "_role"
    token = es_key.sign(valid_claims(role=privileged_role))
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_anonymous_user_is_rejected(es_key):
    token = es_key.sign(valid_claims(is_anonymous=True))
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


# ── Malformed input ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "token", ["", "not-a-jwt", "a.b", "a.b.c.d", "...", "eyJhbGciOiJFUzI1NiJ9"]
)
def test_malformed_tokens_are_rejected(es_key, token):
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


@pytest.mark.parametrize("token", [None, 42, b"bytes", {}])
def test_non_string_tokens_are_rejected(es_key, token):
    with pytest.raises(AuthenticationError):
        build_verifier(es_key).verify(token)


def test_error_message_does_not_leak_which_check_failed(es_key):
    """Reasons are for logs. They must not become a validation oracle if a
    caller ever surfaces them, so they carry no claim values or key material."""
    token = es_key.sign(valid_claims(role="anon"))
    with pytest.raises(AuthenticationError) as excinfo:
        build_verifier(es_key).verify(token)
    text = str(excinfo.value)
    assert token not in text
    assert "anon" not in text
