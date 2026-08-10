"""End-to-end authentication tests (ADR-0063 section 4a — mandatory).

    signed JWT -> JwtVerifier -> VerifiedIdentity -> request_transaction
              -> SET LOCAL -> auth.uid() -> RLS -> user-owned rows only

The RLS suite uses the sanctioned test factory so row-isolation tests stay fast
and focused. That factory stands in for the real path, so the real path must be
proven somewhere — this file is that proof. Without it the suite could be green
while the authentication chain was broken.

Keys are generated locally per run. No production key material, and no contact
with the live Supabase project.
"""

from __future__ import annotations

import json
import uuid

import psycopg
import pytest

from app.auth.config import AuthConfig
from app.auth.jwks import JwksCache
from app.auth.verifier import JwtVerifier
from app.db.session import request_transaction
from auth_fixtures import ISSUER, KeyPair, jwks_document, valid_claims
from conftest import ADMIN_DSN, USER_A, USER_B


@pytest.fixture()
def verifier():
    key = KeyPair("e2e-kid", "ES256")
    config = AuthConfig.from_issuer(ISSUER)
    cache = JwksCache(lambda: jwks_document(key))
    return key, JwtVerifier(config, cache)


def _seed(admin_conn, user_id: uuid.UUID, name: str) -> None:
    admin_conn.execute(
        "INSERT INTO public.profiles (user_id, display_name) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET display_name = EXCLUDED.display_name",
        (user_id, name),
    )


def test_signed_token_reaches_rls_and_returns_only_the_callers_rows(
    verifier, pool, admin_conn
):
    """The whole chain, for real."""
    key, jwt_verifier = verifier
    _seed(admin_conn, USER_A, "alice")
    _seed(admin_conn, USER_B, "bob")

    token = key.sign(valid_claims(sub=str(USER_A)))

    # 1. verification produces an identity from a signed token
    identity = jwt_verifier.verify(token)
    assert identity.subject == USER_A

    # 2. that identity establishes the database session
    with request_transaction(pool, identity) as conn:
        assert conn.execute("SELECT auth.uid()").fetchone()[0] == USER_A
        rows = conn.execute("SELECT user_id FROM public.profiles").fetchall()

    # 3. RLS returned only the caller's row
    assert rows == [(USER_A,)]


def test_two_tokens_cannot_see_each_others_rows(verifier, pool, admin_conn):
    """Isolation across the complete chain, on the same pooled connection."""
    key, jwt_verifier = verifier
    _seed(admin_conn, USER_A, "alice")
    _seed(admin_conn, USER_B, "bob")

    identity_a = jwt_verifier.verify(key.sign(valid_claims(sub=str(USER_A))))
    identity_b = jwt_verifier.verify(key.sign(valid_claims(sub=str(USER_B))))

    with request_transaction(pool, identity_a) as conn:
        a_rows = conn.execute("SELECT user_id FROM public.profiles").fetchall()
    with request_transaction(pool, identity_b) as conn:
        b_rows = conn.execute("SELECT user_id FROM public.profiles").fetchall()

    assert a_rows == [(USER_A,)]
    assert b_rows == [(USER_B,)]


def test_only_sub_and_role_reach_postgresql(verifier, pool, admin_conn):
    """Claim minimisation proven against the live session GUC (I-20).

    The token carries email, phone, user_metadata and app_metadata — exactly as
    a real Supabase token does. None of it may appear in request.jwt.claims.
    """
    key, jwt_verifier = verifier
    claims = valid_claims(sub=str(USER_A))
    assert {"email", "phone", "user_metadata", "app_metadata"} <= set(claims), (
        "fixture must carry High-class claims or this test proves nothing"
    )

    identity = jwt_verifier.verify(key.sign(claims))

    with request_transaction(pool, identity) as conn:
        raw = conn.execute("SELECT current_setting('request.jwt.claims', true)").fetchone()[0]

    payload = json.loads(raw)
    assert set(payload) == {"sub", "role"}
    assert payload["sub"] == str(USER_A)
    assert payload["role"] == "authenticated"

    for forbidden in ("email", "phone", "user_metadata", "app_metadata",
                      "session_id", "aal", "amr", claims["email"], claims["phone"]):
        assert str(forbidden) not in raw, f"{forbidden!r} leaked into session state"


def test_a_rejected_token_never_reaches_the_database(verifier, pool):
    """Verification failure must stop before any session is opened."""
    key, jwt_verifier = verifier
    from app.auth.errors import AuthenticationError

    bad = key.sign(valid_claims(sub=str(USER_A), iss="https://evil.example.com/auth/v1"))
    with pytest.raises(AuthenticationError):
        identity = jwt_verifier.verify(bad)
        with request_transaction(pool, identity):
            pytest.fail("a rejected token opened a database session")


def test_identity_does_not_leak_between_end_to_end_transactions(
    verifier, pool, admin_conn
):
    """I-3 still holds when identities arrive from the real verifier."""
    key, jwt_verifier = verifier
    _seed(admin_conn, USER_A, "alice")

    identity = jwt_verifier.verify(key.sign(valid_claims(sub=str(USER_A))))
    with request_transaction(pool, identity) as conn:
        pid = conn.execute("SELECT pg_backend_pid()").fetchone()[0]

    with pool.connection() as conn:
        assert conn.execute("SELECT pg_backend_pid()").fetchone()[0] == pid
        leaked = conn.execute(
            "SELECT current_setting('request.jwt.claims', true)"
        ).fetchone()[0]
        assert conn.execute("SELECT current_user").fetchone()[0] == "aaroh_app"
    assert leaked in (None, "")
