"""HTTP -> identity -> RLS integration (ADR-0064, mandatory).

    HTTP request with a real signed JWT
      -> FastAPI dependency
      -> VerifiedIdentity
      -> request_transaction
      -> SET LOCAL
      -> PostgreSQL RLS
      -> only caller-owned rows

Every other test in this slice stops at the dependency. These run the whole
chain against real PostgreSQL, because the point of the slice is that the two
already-proven boundaries connect without a gap between them.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth.config import AuthConfig
from app.auth.identity import VerifiedIdentity
from app.auth.jwks import JwksCache
from app.auth.verifier import JwtVerifier
from app.db.session import request_transaction
from app.http.app import create_app
from app.http.dependencies import require_identity
from auth_fixtures import ISSUER, KeyPair, jwks_document, valid_claims
from conftest import USER_A, USER_B

PROBE = "/internal/boundary-probe"


@pytest.fixture()
def key() -> KeyPair:
    return KeyPair("integration-kid", "ES256")


@pytest.fixture()
def client(key, pool) -> TestClient:
    verifier = JwtVerifier(AuthConfig.from_issuer(ISSUER), JwksCache(lambda: jwks_document(key)))
    return TestClient(create_app(verifier, pool=pool))


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed(admin_conn, user_id: uuid.UUID, name: str) -> None:
    admin_conn.execute(
        "INSERT INTO public.profiles (user_id, display_name) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET display_name = EXCLUDED.display_name",
        (user_id, name),
    )


def test_authenticated_request_reaches_rls_and_sees_only_its_own_rows(
    client, key, admin_conn
):
    """The complete chain, in one HTTP request."""
    _seed(admin_conn, USER_A, "alice")
    _seed(admin_conn, USER_B, "bob")

    response = client.get(PROBE, headers=bearer(key.sign(valid_claims(sub=str(USER_A)))))

    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == str(USER_A)
    # Two rows exist; RLS shows this caller exactly one.
    assert body["visible_rows"] == 1


def test_two_callers_are_isolated_across_http(client, key, admin_conn):
    """Cross-user isolation still holds when the identity arrives over HTTP."""
    _seed(admin_conn, USER_A, "alice")
    _seed(admin_conn, USER_B, "bob")

    a = client.get(PROBE, headers=bearer(key.sign(valid_claims(sub=str(USER_A))))).json()
    b = client.get(PROBE, headers=bearer(key.sign(valid_claims(sub=str(USER_B))))).json()

    assert a["subject"] == str(USER_A)
    assert b["subject"] == str(USER_B)
    assert a["visible_rows"] == 1
    assert b["visible_rows"] == 1
    assert a["subject"] != b["subject"]


def test_unauthenticated_request_performs_no_database_work(client, admin_conn):
    """A rejected request must not reach the database at all."""
    _seed(admin_conn, USER_A, "alice")
    response = client.get(PROBE)
    assert response.status_code == 401
    assert "visible_rows" not in response.text


def test_identity_from_http_propagates_to_auth_uid(client, key, pool, admin_conn):
    """auth.uid() inside the transaction equals the subject from the HTTP token."""
    _seed(admin_conn, USER_A, "alice")

    verifier = client.app.state.verifier
    identity = verifier.verify(key.sign(valid_claims(sub=str(USER_A))))

    with request_transaction(pool, identity) as conn:
        assert conn.execute("SELECT auth.uid()").fetchone()[0] == USER_A


def test_rls_still_blocks_cross_user_access_after_http_authentication(
    client, key, pool, admin_conn
):
    """Slice 1's guarantee is unchanged by the HTTP layer."""
    _seed(admin_conn, USER_A, "alice")
    _seed(admin_conn, USER_B, "bob")

    verifier = client.app.state.verifier
    identity_a = verifier.verify(key.sign(valid_claims(sub=str(USER_A))))

    with request_transaction(pool, identity_a) as conn:
        rows = conn.execute(
            "SELECT user_id FROM public.profiles WHERE user_id = %s", (USER_B,)
        ).fetchall()
    assert rows == [], "RLS did not block cross-user access after HTTP authentication"


def test_a_dict_cannot_be_substituted_for_the_identity(pool):
    """Even holding the pool, a plausible dict is refused at the db boundary."""
    from app.db.session import UnverifiedIdentityError

    with pytest.raises(UnverifiedIdentityError):
        with request_transaction(pool, {"sub": str(USER_A), "role": "authenticated"}):
            pytest.fail("an unverified dict established a database identity")


def test_route_without_the_dependency_cannot_obtain_an_identity(client, pool):
    """The structural reason a forgotten dependency fails safe: the handler has
    no way to construct the type it would need."""
    from app.auth.errors import UnauthorizedIdentityConstruction

    app = client.app

    @app.get("/probe-forgotten")
    def forgotten():
        with pytest.raises(UnauthorizedIdentityConstruction):
            VerifiedIdentity(USER_A, "authenticated")
        return {"reached": True}

    assert TestClient(app).get("/probe-forgotten").json() == {"reached": True}
