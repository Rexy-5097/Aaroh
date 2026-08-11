"""Preparation goal API: HTTP -> identity -> RLS (ADR-0065).

Proves the first product capability travels the chain proven in slices 1-3
without introducing a second path, and that one student cannot reach another's
goal.

A test that only asserts HTTP 200 proves nothing here; every case below asserts
either the data returned or the data withheld.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth.config import AuthConfig
from app.auth.jwks import JwksCache
from app.auth.verifier import JwtVerifier
from app.http.app import create_app
from auth_fixtures import ISSUER, KeyPair, jwks_document, valid_claims
from conftest import USER_A, USER_B

GOAL = "/v1/preparation-goal"


@pytest.fixture()
def key() -> KeyPair:
    return KeyPair("product-kid", "ES256")


@pytest.fixture()
def client(key, pool) -> TestClient:
    verifier = JwtVerifier(AuthConfig.from_issuer(ISSUER), JwksCache(lambda: jwks_document(key)))
    return TestClient(create_app(verifier, pool=pool))


@pytest.fixture(autouse=True)
def clean_goals(admin_conn):
    admin_conn.execute("DELETE FROM public.preparation_goals")
    yield


def auth(key, subject) -> dict[str, str]:
    return {"Authorization": f"Bearer {key.sign(valid_claims(sub=str(subject)))}"}


def payload(**overrides) -> dict:
    body = {
        "target_role": "Backend SWE",
        "target_company": "Acme",
        "deadline": (date.today() + timedelta(days=90)).isoformat(),
        "weekly_hours": 12,
    }
    body.update(overrides)
    return body


# ── The capability works ─────────────────────────────────────────────────────

def test_a_student_can_set_and_read_their_goal(client, key):
    put = client.put(GOAL, json=payload(), headers=auth(key, USER_A))
    assert put.status_code == 200
    body = put.json()
    assert body["target_role"] == "Backend SWE"
    assert body["target_company"] == "Acme"
    assert body["weekly_hours"] == 12
    assert body["days_remaining"] == 90

    got = client.get(GOAL, headers=auth(key, USER_A))
    assert got.status_code == 200
    assert got.json() == body


def test_setting_a_goal_twice_replaces_rather_than_duplicates(client, key, admin_conn):
    """PUT is idempotent replacement: a student has one active goal."""
    client.put(GOAL, json=payload(target_role="First"), headers=auth(key, USER_A))
    client.put(GOAL, json=payload(target_role="Second", weekly_hours=20),
               headers=auth(key, USER_A))

    got = client.get(GOAL, headers=auth(key, USER_A)).json()
    assert got["target_role"] == "Second"
    assert got["weekly_hours"] == 20
    count = admin_conn.execute("SELECT count(*) FROM public.preparation_goals").fetchone()[0]
    assert count == 1, "replacement created a second row"


def test_absent_goal_returns_404(client, key):
    assert client.get(GOAL, headers=auth(key, USER_A)).status_code == 404


def test_days_remaining_is_computed_not_stored(client, key, admin_conn):
    client.put(GOAL, json=payload(), headers=auth(key, USER_A))
    columns = {
        r[0]
        for r in admin_conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'preparation_goals'"
        ).fetchall()
    }
    assert "days_remaining" not in columns, "a stored value would be wrong tomorrow"
    assert "days_remaining" in client.get(GOAL, headers=auth(key, USER_A)).json()


# ── Cross-user isolation — the property that matters ─────────────────────────

def test_user_a_cannot_read_user_b_goal(client, key):
    client.put(GOAL, json=payload(target_role="B's plan"), headers=auth(key, USER_B))

    response = client.get(GOAL, headers=auth(key, USER_A))
    assert response.status_code == 404, "A saw a goal that belongs to B"
    assert "B's plan" not in response.text


def test_user_b_cannot_read_user_a_goal(client, key):
    client.put(GOAL, json=payload(target_role="A's plan"), headers=auth(key, USER_A))

    response = client.get(GOAL, headers=auth(key, USER_B))
    assert response.status_code == 404
    assert "A's plan" not in response.text


def test_each_student_sees_only_their_own_goal(client, key):
    client.put(GOAL, json=payload(target_role="A role", weekly_hours=5),
               headers=auth(key, USER_A))
    client.put(GOAL, json=payload(target_role="B role", weekly_hours=30),
               headers=auth(key, USER_B))

    a = client.get(GOAL, headers=auth(key, USER_A)).json()
    b = client.get(GOAL, headers=auth(key, USER_B)).json()
    assert (a["target_role"], a["weekly_hours"]) == ("A role", 5)
    assert (b["target_role"], b["weekly_hours"]) == ("B role", 30)


def test_writing_does_not_overwrite_another_students_goal(client, key, admin_conn):
    client.put(GOAL, json=payload(target_role="A role"), headers=auth(key, USER_A))
    client.put(GOAL, json=payload(target_role="B role"), headers=auth(key, USER_B))

    rows = dict(
        admin_conn.execute(
            "SELECT user_id, target_role FROM public.preparation_goals"
        ).fetchall()
    )
    assert rows[USER_A] == "A role"
    assert rows[USER_B] == "B role"


def test_a_client_supplied_user_id_is_ignored(client, key, admin_conn):
    """The IDOR-by-design case: the body must not be able to choose the owner."""
    response = client.put(
        GOAL, json={**payload(), "user_id": str(USER_B)}, headers=auth(key, USER_A)
    )
    # extra="forbid" rejects it outright; either way B must own nothing.
    assert response.status_code in (200, 422)
    owners = [
        r[0] for r in admin_conn.execute(
            "SELECT user_id FROM public.preparation_goals"
        ).fetchall()
    ]
    assert USER_B not in owners, "a request body chose another user as the owner"


def test_a_direct_insert_naming_another_owner_is_refused(pool):
    """Makes WITH CHECK load-bearing.

    The API never supplies `user_id` -- the column defaults to auth.uid() -- so a
    permissive write policy would be invisible through the endpoint. Mutation
    testing proved exactly that: relaxing the INSERT policy to WITH CHECK (true)
    left the whole suite green.

    This test bypasses the default and names another owner explicitly, which is
    what an attacker with code execution in a handler would do. Only the policy
    stands in the way.
    """
    import psycopg
    from app.auth.testing import identity_for
    from app.db.session import request_transaction

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with request_transaction(pool, identity_for(USER_A)) as conn:
            conn.execute(
                "INSERT INTO public.preparation_goals "
                "(user_id, target_role, deadline, weekly_hours) VALUES (%s, %s, %s, %s)",
                (USER_B, "planted", date.today() + timedelta(days=30), 10),
            )


def test_a_direct_update_reassigning_ownership_is_refused(pool, key, client):
    """The UPDATE counterpart: a student must not move their goal to someone else."""
    import psycopg
    from app.auth.testing import identity_for
    from app.db.session import request_transaction

    client.put(GOAL, json=payload(), headers=auth(key, USER_A))

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with request_transaction(pool, identity_for(USER_A)) as conn:
            conn.execute(
                "UPDATE public.preparation_goals SET user_id = %s", (USER_B,)
            )


# ── Authentication is required ───────────────────────────────────────────────

@pytest.mark.parametrize("method", ["get", "put"])
def test_unauthenticated_requests_are_refused(client, method):
    call = getattr(client, method)
    response = call(GOAL, json=payload()) if method == "put" else call(GOAL)
    assert response.status_code == 401


@pytest.mark.parametrize(
    "header", [{"Authorization": "Basic xyz"}, {"Authorization": "Bearer not-a-jwt"}]
)
def test_bad_credentials_are_refused(client, header):
    assert client.get(GOAL, headers=header).status_code == 401


def test_unauthenticated_write_persists_nothing(client, admin_conn):
    client.put(GOAL, json=payload())
    count = admin_conn.execute("SELECT count(*) FROM public.preparation_goals").fetchone()[0]
    assert count == 0, "a rejected request reached the database"


def test_rejected_token_cannot_reach_the_endpoint(client, key):
    """A validly-signed token with a rejected role must not pass."""
    token = key.sign(valid_claims(sub=str(USER_A), role="anon"))
    response = client.get(GOAL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# ── Invalid domain input ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "bad,field",
    [
        ({"target_role": ""}, "target_role"),
        ({"target_role": "   "}, "target_role"),
        ({"target_role": "x" * 200}, "target_role"),
        ({"deadline": (date.today() - timedelta(days=1)).isoformat()}, "deadline"),
        ({"deadline": date.today().isoformat()}, "deadline"),
        ({"deadline": (date.today() + timedelta(days=5000)).isoformat()}, "deadline"),
        ({"weekly_hours": 0}, "weekly_hours"),
        ({"weekly_hours": 200}, "weekly_hours"),
    ],
)
def test_invalid_goals_are_rejected_with_the_field_named(client, key, bad, field):
    response = client.put(GOAL, json=payload(**bad), headers=auth(key, USER_A))
    assert response.status_code == 422
    assert field in response.text


def test_invalid_input_persists_nothing(client, key, admin_conn):
    client.put(GOAL, json=payload(weekly_hours=0), headers=auth(key, USER_A))
    count = admin_conn.execute("SELECT count(*) FROM public.preparation_goals").fetchone()[0]
    assert count == 0


@pytest.mark.parametrize(
    "bad",
    [
        {"deadline": "not-a-date"},
        {"weekly_hours": "twelve"},
        {"target_role": None},
        {"unexpected_field": "x"},
    ],
)
def test_malformed_payloads_are_rejected(client, key, bad):
    assert client.put(GOAL, json=payload(**bad), headers=auth(key, USER_A)).status_code == 422


def test_boolean_weekly_hours_are_rejected_through_http(client, key, admin_conn):
    """Regression: Pydantic coerces JSON `true` to 1, so a plain `int` field
    would have silently recorded one hour per week. The domain layer rejects
    bool, but coercion happened before it ever saw one. Found while testing the
    DSA slice; the same latent defect existed here."""
    assert client.put(GOAL, json=payload(weekly_hours=True),
                      headers=auth(key, USER_A)).status_code == 422
    count = admin_conn.execute("SELECT count(*) FROM public.preparation_goals").fetchone()[0]
    assert count == 0


def test_missing_body_is_rejected(client, key):
    assert client.put(GOAL, headers=auth(key, USER_A)).status_code == 422
