"""HTTP authentication boundary tests (ADR-0064).

Proves the property the slice exists for: an HTTP request cannot reach a
protected operation without passing the already-verified cryptographic identity
boundary, and failure discloses nothing beyond "not authenticated".

Keys are generated locally, as in slice 2. Nothing here touches the network or
the live Supabase project.
"""

from __future__ import annotations

import time
import uuid

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.config import AuthConfig
from app.auth.identity import VerifiedIdentity
from app.auth.jwks import JwksCache
from app.auth.verifier import JwtVerifier
from app.http.app import create_app
from app.http.dependencies import require_identity
from auth_fixtures import ISSUER, KeyPair, jwks_document, valid_claims

PROBE = "/internal/boundary-probe"


@pytest.fixture()
def key() -> KeyPair:
    return KeyPair("http-kid", "ES256")


@pytest.fixture()
def verifier(key) -> JwtVerifier:
    return JwtVerifier(AuthConfig.from_issuer(ISSUER), JwksCache(lambda: jwks_document(key)))


@pytest.fixture()
def client(verifier) -> TestClient:
    """App with no pool: the auth boundary is exercised without a database."""
    return TestClient(create_app(verifier, pool=None))


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── Bearer envelope parsing ──────────────────────────────────────────────────

def test_no_authorization_header_is_rejected(client):
    assert client.get(PROBE).status_code == 401


@pytest.mark.parametrize(
    "header",
    [
        "",                      # empty header
        "Bearer",                # scheme only, no token
        "Bearer ",               # scheme and whitespace
        "Bearer a b",            # extra segment
        "  Bearer token  ",      # padded -- still two parts after split, but tested explicitly
        "BearerTOKEN",           # no separator
        "token-without-scheme",
    ],
)
def test_malformed_authorization_headers_are_rejected(client, header):
    assert client.get(PROBE, headers={"Authorization": header}).status_code == 401


@pytest.mark.parametrize("scheme", ["Basic", "Token", "Digest", "JWT", "MAC"])
def test_wrong_scheme_is_rejected(client, key, scheme):
    token = key.sign(valid_claims())
    response = client.get(PROBE, headers={"Authorization": f"{scheme} {token}"})
    assert response.status_code == 401


def test_extra_segments_are_rejected_even_when_the_token_is_valid(client, key):
    """Discriminating test for the arity check.

    Asserting only "malformed header -> 401" is not enough: a parser that
    truncated to the first two parts would still 401 on a garbage token, so the
    weakness would hide behind a passing test. Mutation testing found exactly
    that. Pairing a VALID token with a trailing segment is the case that
    separates a strict parser from a lenient one -- lenient returns 200.
    """
    valid = key.sign(valid_claims())
    assert client.get(PROBE, headers=bearer(valid)).status_code == 200

    for header in (f"Bearer {valid} extra",
                   f"Bearer {valid} {valid}",
                   f"Bearer extra {valid}"):
        response = client.get(PROBE, headers={"Authorization": header})
        assert response.status_code == 401, f"lenient parse accepted: {header[:40]}..."


def test_empty_bearer_token_is_rejected(client):
    """Covered by the arity check rather than a dedicated guard.

    `str.split()` cannot produce an empty part, so "Bearer " is a one-element
    split and fails arity. The property holds; the redundant guard that appeared
    to enforce it was removed as unreachable.
    """
    for header in ("Bearer ", "Bearer", "Bearer\t", "Bearer  "):
        assert client.get(PROBE, headers={"Authorization": header}).status_code == 401


def test_bearer_scheme_is_case_insensitive(client, key):
    """RFC 7235 makes the scheme case-insensitive; rejecting `bearer` would
    break conformant clients for no security gain."""
    token = key.sign(valid_claims())
    for scheme in ("Bearer", "bearer", "BEARER", "BeArEr"):
        response = client.get(PROBE, headers={"Authorization": f"{scheme} {token}"})
        assert response.status_code == 200, scheme


# ── Verification outcomes, surfaced through HTTP ─────────────────────────────

def test_valid_token_is_accepted(client, key):
    claims = valid_claims()
    response = client.get(PROBE, headers=bearer(key.sign(claims)))
    assert response.status_code == 200
    assert response.json()["subject"] == claims["sub"]


def _rejected_tokens(key) -> dict[str, str]:
    now = int(time.time())
    other = KeyPair("http-kid", "ES256")  # same kid, different key
    return {
        "malformed": "not-a-jwt",
        "bad_signature": other.sign(valid_claims()),
        "expired": key.sign(valid_claims(iat=now - 7200, exp=now - 3600)),
        "wrong_issuer": key.sign(valid_claims(iss="https://evil.example.com/auth/v1")),
        "wrong_audience": key.sign(valid_claims(aud="another-service")),
        "rejected_role": key.sign(valid_claims(role="anon")),
        "anonymous": key.sign(valid_claims(is_anonymous=True)),
        "unknown_kid": jwt.encode(
            valid_claims(), key.private, algorithm="ES256", headers={"kid": "no-such-kid"}
        ),
        "alg_none": jwt.encode(valid_claims(), key="", algorithm="none",
                               headers={"kid": "http-kid"}),
    }


@pytest.mark.parametrize("case", list(_rejected_tokens(KeyPair("http-kid", "ES256"))))
def test_every_rejected_token_returns_401(client, key, case):
    token = _rejected_tokens(key)[case]
    assert client.get(PROBE, headers=bearer(token)).status_code == 401


def test_all_failures_are_byte_identical(client, key):
    """The anti-oracle property (I-24).

    A missing header, a malformed token, a bad signature, an expired token and a
    rejected role must be indistinguishable to the caller. If any of these ever
    differ, the endpoint has become a token-validation oracle.
    """
    responses = [client.get(PROBE)]                                   # no header
    responses.append(client.get(PROBE, headers={"Authorization": "Basic xyz"}))
    for token in _rejected_tokens(key).values():
        responses.append(client.get(PROBE, headers=bearer(token)))

    bodies, statuses, wwws = set(), set(), set()
    for r in responses:
        body = r.json()
        body.pop("correlation_id")          # unique per request by design
        bodies.add(repr(sorted(body.items())))
        statuses.add(r.status_code)
        wwws.add(r.headers.get("WWW-Authenticate"))

    assert statuses == {401}
    assert len(bodies) == 1, f"authentication failures are distinguishable: {bodies}"
    assert wwws == {"Bearer"}


def test_www_authenticate_carries_no_error_detail(client):
    """RFC 6750 permits error="invalid_token"; omitting it keeps `missing`
    indistinguishable from `rejected` at the header level too."""
    header = client.get(PROBE).headers.get("WWW-Authenticate")
    assert header == "Bearer"
    assert "error" not in header.lower()


def test_problem_body_shape(client):
    response = client.get(PROBE)
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert set(body) == {"type", "title", "status", "detail", "correlation_id"}
    assert body["status"] == 401
    assert "instance" not in body, "instance would reflect client-controlled input"


# ── Token must never leak (I-27) ─────────────────────────────────────────────

def test_token_never_appears_in_the_response(client, key):
    token = key.sign(valid_claims(iss="https://evil.example.com/auth/v1"))
    response = client.get(PROBE, headers=bearer(token))
    haystack = response.text + repr(dict(response.headers))
    assert token not in haystack
    for segment in token.split("."):
        assert segment not in haystack
    assert "Authorization" not in response.text


def test_failure_reason_never_reaches_the_client(client, key):
    """The verifier's internal reason is for logs only."""
    body = client.get(PROBE, headers=bearer(key.sign(valid_claims(role="anon")))).text
    for reason in ("role_not_permitted", "bad_signature", "expired", "bad_issuer",
                   "anonymous_user", "unknown_kid", "jwks_unavailable"):
        assert reason not in body


def test_correlation_id_is_server_generated_and_client_value_ignored(client):
    """A client-supplied id would let a caller inject text into logs and into a
    body some client will render."""
    injected = "<script>alert(1)</script>"
    response = client.get(PROBE, headers={"X-Request-ID": injected})
    assert injected not in response.text
    assert response.headers["X-Request-ID"] != injected
    uuid.UUID(response.json()["correlation_id"])          # well-formed UUID
    assert response.headers["X-Request-ID"] == response.json()["correlation_id"]


def test_correlation_id_differs_between_requests(client):
    first = client.get(PROBE).json()["correlation_id"]
    second = client.get(PROBE).json()["correlation_id"]
    assert first != second


# ── The handler receives an identity, and only on success (I-25, I-29) ───────

def test_handler_receives_a_verified_identity_not_claims(verifier, key):
    seen: dict[str, object] = {}
    app = create_app(verifier)

    @app.get("/probe-type")
    def probe(identity: VerifiedIdentity = Depends(require_identity)):
        seen["identity"] = identity
        return {"ok": True}

    claims = valid_claims()
    assert TestClient(app).get("/probe-type", headers=bearer(key.sign(claims))).status_code == 200
    identity = seen["identity"]
    assert isinstance(identity, VerifiedIdentity)
    assert not isinstance(identity, dict)
    assert identity.subject == uuid.UUID(claims["sub"])
    # The handler cannot inspect a claim it was never given.
    for absent in ("email", "phone", "user_metadata", "app_metadata", "session_id"):
        assert not hasattr(identity, absent)


def test_handler_does_not_execute_on_authentication_failure(verifier, key):
    """I-25 asserted, not assumed: FastAPI resolves dependencies before the body."""
    executed: list[bool] = []
    app = create_app(verifier)

    @app.get("/probe-exec")
    def probe(identity: VerifiedIdentity = Depends(require_identity)):
        executed.append(True)
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/probe-exec").status_code == 401
    assert client.get("/probe-exec", headers={"Authorization": "Basic x"}).status_code == 401
    assert client.get("/probe-exec", headers=bearer("garbage")).status_code == 401
    assert executed == [], "the handler ran despite authentication failing"

    assert client.get("/probe-exec", headers=bearer(key.sign(valid_claims()))).status_code == 200
    assert executed == [True]


def test_identity_is_not_reused_between_requests(verifier, key):
    """Dependency caching is per-request. If it ever leaked across requests, one
    caller would act as another."""
    subjects: list[str] = []
    app = create_app(verifier)

    @app.get("/probe-reuse")
    def probe(identity: VerifiedIdentity = Depends(require_identity)):
        subjects.append(str(identity.subject))
        return {"ok": True}

    client = TestClient(app)
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    client.get("/probe-reuse", headers=bearer(key.sign(valid_claims(sub=first))))
    client.get("/probe-reuse", headers=bearer(key.sign(valid_claims(sub=second))))
    assert subjects == [first, second]


def test_dependency_verifies_once_per_request(verifier, key):
    """Within one request the identity is resolved once, not per use site."""
    calls: list[int] = []
    app = create_app(verifier)

    @app.get("/probe-cache")
    def probe(
        a: VerifiedIdentity = Depends(require_identity),
        b: VerifiedIdentity = Depends(require_identity),
    ):
        calls.append(1)
        assert a is b, "the same request resolved two distinct identities"
        return {"ok": True}

    assert TestClient(app).get(
        "/probe-cache", headers=bearer(key.sign(valid_claims()))
    ).status_code == 200
    assert calls == [1]


# ── The dependency touches no database (I-28) ────────────────────────────────

def test_auth_dependency_opens_zero_database_connections(verifier, key):
    """A pool that raises if touched: proves authentication needs no database."""

    class ExplodingPool:
        def connection(self):  # pragma: no cover - must never be called
            raise AssertionError("the authentication dependency opened a connection")

    app = create_app(verifier, pool=ExplodingPool())

    @app.get("/probe-nodb")
    def probe(identity: VerifiedIdentity = Depends(require_identity)):
        return {"subject": str(identity.subject)}

    client = TestClient(app)
    assert client.get("/probe-nodb").status_code == 401            # failure path
    assert client.get(
        "/probe-nodb", headers=bearer(key.sign(valid_claims()))
    ).status_code == 200                                            # success path


def test_http_package_imports_no_database_driver():
    import importlib
    import sys

    for name in ("app.http", "app.http.app", "app.http.dependencies", "app.http.errors"):
        importlib.import_module(name)

    forbidden = {"psycopg", "psycopg_pool", "sqlalchemy", "asyncpg", "supabase"}
    for module_name in [m for m in sys.modules if m.startswith("app.http")]:
        module = sys.modules[module_name]
        imported = {
            getattr(v, "__module__", "").split(".")[0]
            for v in vars(module).values()
            if hasattr(v, "__module__")
        }
        assert not (imported & forbidden), f"{module_name}: {imported & forbidden}"


# ── No second verification path (I-26) ───────────────────────────────────────

def test_http_layer_performs_no_jwt_decoding_of_its_own():
    """Asserted on the source, because the risk is a future convenience decode."""
    import pathlib

    http_dir = pathlib.Path(__file__).resolve().parents[1] / "app" / "http"
    for path in http_dir.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for banned in ("jwt.decode", "get_unverified", "decode_complete", "base64"):
            assert banned not in source, f"{path.name} performs its own token handling: {banned}"
