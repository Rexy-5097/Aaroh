"""DSA activity API: HTTP -> identity -> RLS (ADR-0066).

Proves Aaroh's first snapshot data source travels the chain proven in slices 1-3
without a second path, that one student cannot reach another's practice history,
and that the log is genuinely append-only.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.config import AuthConfig
from app.auth.jwks import JwksCache
from app.auth.verifier import JwtVerifier
from app.http.app import create_app
from auth_fixtures import ISSUER, KeyPair, jwks_document, valid_claims
from conftest import USER_A, USER_B

DSA = "/v1/dsa-activity"


@pytest.fixture()
def key() -> KeyPair:
    return KeyPair("dsa-kid", "ES256")


@pytest.fixture()
def client(key, pool) -> TestClient:
    verifier = JwtVerifier(AuthConfig.from_issuer(ISSUER), JwksCache(lambda: jwks_document(key)))
    return TestClient(create_app(verifier, pool=pool))


@pytest.fixture(autouse=True)
def clean_activities(admin_conn):
    admin_conn.execute("DELETE FROM public.dsa_activities")
    yield


def auth(key, subject) -> dict[str, str]:
    return {"Authorization": f"Bearer {key.sign(valid_claims(sub=str(subject)))}"}


def payload(**overrides) -> dict:
    body = {
        "problem_title": "Two Sum",
        "topic": "arrays",
        "difficulty": "easy",
        "outcome": "solved",
    }
    body.update(overrides)
    return body


def count(admin_conn) -> int:
    return admin_conn.execute("SELECT count(*) FROM public.dsa_activities").fetchone()[0]


# ── The capability works ─────────────────────────────────────────────────────

def test_a_student_can_record_and_list_activity(client, key):
    created = client.post(DSA, json=payload(minutes_spent=20, platform="LeetCode"),
                          headers=auth(key, USER_A))
    assert created.status_code == 201
    body = created.json()
    assert body["problem_title"] == "Two Sum"
    assert body["problem_ref"] == "two sum"
    assert (body["topic"], body["difficulty"], body["outcome"]) == (
        "arrays", "easy", "solved")
    assert body["minutes_spent"] == 20
    assert body["platform"] == "LeetCode"

    listed = client.get(DSA, headers=auth(key, USER_A))
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == body["id"]


def test_optional_fields_may_be_omitted(client, key):
    body = client.post(DSA, json=payload(), headers=auth(key, USER_A)).json()
    assert body["minutes_spent"] is None
    assert body["platform"] is None


def test_no_activity_returns_an_empty_list(client, key):
    """Absence here means "nothing recorded yet", not "not found"."""
    response = client.get(DSA, headers=auth(key, USER_A))
    assert response.status_code == 200
    assert response.json() == []


def test_activities_are_listed_most_recent_first(client, key, admin_conn):
    for title in ("First", "Second", "Third"):
        client.post(DSA, json=payload(problem_title=title), headers=auth(key, USER_A))
    admin_conn.execute(
        "UPDATE public.dsa_activities SET occurred_at = now() - "
        "(interval '1 hour' * (CASE problem_title WHEN 'First' THEN 3 "
        "WHEN 'Second' THEN 2 ELSE 1 END))"
    )
    titles = [a["problem_title"] for a in client.get(DSA, headers=auth(key, USER_A)).json()]
    assert titles == ["Third", "Second", "First"]


# ── Re-solving is a new event, not a duplicate ───────────────────────────────

def test_the_same_problem_can_be_recorded_twice(client, key, admin_conn):
    """Re-solving is signal. There is deliberately no uniqueness constraint."""
    first = client.post(DSA, json=payload(outcome="attempted"), headers=auth(key, USER_A))
    second = client.post(DSA, json=payload(outcome="solved", minutes_spent=12),
                         headers=auth(key, USER_A))
    assert first.status_code == second.status_code == 201
    assert count(admin_conn) == 2, "the second recording replaced the first"


def test_repeated_activities_remain_distinguishable(client, key):
    a = client.post(DSA, json=payload(outcome="attempted"), headers=auth(key, USER_A)).json()
    b = client.post(DSA, json=payload(outcome="solved"), headers=auth(key, USER_A)).json()

    assert a["id"] != b["id"], "distinct events must have distinct identities"
    assert a["problem_ref"] == b["problem_ref"], "but they name the same problem"
    outcomes = {x["outcome"] for x in client.get(DSA, headers=auth(key, USER_A)).json()}
    assert outcomes == {"attempted", "solved"}


def test_re_recording_does_not_overwrite_the_earlier_activity(client, key):
    first_id = client.post(DSA, json=payload(minutes_spent=5),
                           headers=auth(key, USER_A)).json()["id"]
    client.post(DSA, json=payload(minutes_spent=99), headers=auth(key, USER_A))

    listed = {a["id"]: a for a in client.get(DSA, headers=auth(key, USER_A)).json()}
    assert first_id in listed
    assert listed[first_id]["minutes_spent"] == 5, "the earlier event was mutated"


# ── Cross-user isolation ─────────────────────────────────────────────────────

def test_user_b_cannot_read_user_a_activity(client, key):
    client.post(DSA, json=payload(problem_title="A private practice"),
                headers=auth(key, USER_A))
    response = client.get(DSA, headers=auth(key, USER_B))
    assert response.status_code == 200
    assert response.json() == [], "B saw A's activity"
    assert "A private practice" not in response.text


def test_user_a_cannot_read_user_b_activity(client, key):
    client.post(DSA, json=payload(problem_title="B private practice"),
                headers=auth(key, USER_B))
    response = client.get(DSA, headers=auth(key, USER_A))
    assert response.json() == []
    assert "B private practice" not in response.text


def test_each_student_sees_only_their_own_history(client, key):
    client.post(DSA, json=payload(problem_title="A one"), headers=auth(key, USER_A))
    client.post(DSA, json=payload(problem_title="A two"), headers=auth(key, USER_A))
    client.post(DSA, json=payload(problem_title="B one"), headers=auth(key, USER_B))

    a = [x["problem_title"] for x in client.get(DSA, headers=auth(key, USER_A)).json()]
    b = [x["problem_title"] for x in client.get(DSA, headers=auth(key, USER_B)).json()]
    assert sorted(a) == ["A one", "A two"]
    assert b == ["B one"]


def test_a_client_supplied_user_id_cannot_choose_the_owner(client, key, admin_conn):
    response = client.post(DSA, json={**payload(), "user_id": str(USER_B)},
                           headers=auth(key, USER_A))
    assert response.status_code in (201, 422)
    owners = {r[0] for r in admin_conn.execute(
        "SELECT user_id FROM public.dsa_activities").fetchall()}
    assert USER_B not in owners, "a request body chose another student as the owner"


# ── Direct SQL: the policies the API cannot exercise ─────────────────────────

def test_a_direct_insert_naming_another_owner_is_refused(pool):
    """Makes WITH CHECK load-bearing.

    The API never supplies user_id, so a permissive write policy would be
    invisible through the endpoint — the gap mutation testing exposed in PR #12.
    """
    import psycopg
    from app.auth.testing import identity_for
    from app.db.session import request_transaction

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with request_transaction(pool, identity_for(USER_A)) as conn:
            conn.execute(
                "INSERT INTO public.dsa_activities "
                "(user_id, problem_title, problem_ref, topic, difficulty, outcome) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (USER_B, "planted", "planted", "arrays", "easy", "solved"),
            )


def test_updates_are_denied_for_having_no_policy(client, key, pool):
    """The log is append-only: RLS denies UPDATE because no policy grants it."""
    import psycopg
    from app.auth.testing import identity_for
    from app.db.session import request_transaction

    client.post(DSA, json=payload(), headers=auth(key, USER_A))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with request_transaction(pool, identity_for(USER_A)) as conn:
            conn.execute("UPDATE public.dsa_activities SET outcome = 'attempted'")


def test_deletes_are_denied_for_having_no_policy(client, key, pool):
    import psycopg
    from app.auth.testing import identity_for
    from app.db.session import request_transaction

    client.post(DSA, json=payload(), headers=auth(key, USER_A))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with request_transaction(pool, identity_for(USER_A)) as conn:
            conn.execute("DELETE FROM public.dsa_activities")


def test_account_deletion_removes_activity(client, key, admin_conn):
    """Retention: activity lives while the account does (ADR-0066 section 10)."""
    client.post(DSA, json=payload(), headers=auth(key, USER_A))
    assert count(admin_conn) == 1

    admin_conn.execute("DELETE FROM auth.users WHERE id = %s", (USER_A,))
    assert count(admin_conn) == 0, "activity survived account deletion"

    admin_conn.execute("INSERT INTO auth.users (id, email) VALUES (%s, %s)",
                       (USER_A, "restored@example.test"))


# ── Authentication ───────────────────────────────────────────────────────────

def test_unauthenticated_create_is_rejected(client):
    assert client.post(DSA, json=payload()).status_code == 401


def test_unauthenticated_read_is_rejected(client):
    assert client.get(DSA).status_code == 401


def test_unauthenticated_create_persists_nothing(client, admin_conn):
    client.post(DSA, json=payload())
    assert count(admin_conn) == 0


@pytest.mark.parametrize("header", [{"Authorization": "Basic x"},
                                    {"Authorization": "Bearer not-a-jwt"}])
def test_bad_credentials_are_rejected(client, header):
    assert client.get(DSA, headers=header).status_code == 401


def test_a_rejected_role_cannot_record_activity(client, key, admin_conn):
    token = key.sign(valid_claims(sub=str(USER_A), role="anon"))
    assert client.post(DSA, json=payload(),
                       headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert count(admin_conn) == 0


# ── Invalid input ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "bad,field",
    [
        ({"problem_title": ""}, "problem_title"),
        ({"problem_title": "   "}, "problem_title"),
        ({"problem_title": "x" * 300}, "problem_title"),
        ({"topic": "unknown-topic"}, "topic"),
        ({"topic": "Arrays"}, "topic"),
        ({"difficulty": "trivial"}, "difficulty"),
        ({"difficulty": "Easy"}, "difficulty"),
        ({"outcome": "skipped"}, "outcome"),
        ({"minutes_spent": 0}, "minutes_spent"),
        ({"minutes_spent": 601}, "minutes_spent"),
        ({"platform": "p" * 100}, "platform"),
    ],
)
def test_invalid_activities_are_rejected_with_the_field_named(client, key, bad, field):
    response = client.post(DSA, json=payload(**bad), headers=auth(key, USER_A))
    assert response.status_code == 422
    assert field in response.text


def test_invalid_input_persists_nothing(client, key, admin_conn):
    client.post(DSA, json=payload(topic="nonsense"), headers=auth(key, USER_A))
    assert count(admin_conn) == 0


@pytest.mark.parametrize(
    "bad",
    [{"minutes_spent": "twenty"}, {"unexpected": "x"}, {"problem_title": None},
     {"minutes_spent": 12.5}],
)
def test_malformed_payloads_are_rejected(client, key, bad):
    assert client.post(DSA, json=payload(**bad),
                       headers=auth(key, USER_A)).status_code == 422


def test_boolean_minutes_are_rejected_through_http(client, key, admin_conn):
    """bool is an int subclass; `True` must not become one minute."""
    assert client.post(DSA, json=payload(minutes_spent=True),
                       headers=auth(key, USER_A)).status_code == 422
    assert count(admin_conn) == 0


def test_missing_body_is_rejected(client, key):
    assert client.post(DSA, headers=auth(key, USER_A)).status_code == 422


# ── Privacy ──────────────────────────────────────────────────────────────────

def test_the_response_carries_no_token_or_owner_id(client, key):
    token = key.sign(valid_claims(sub=str(USER_A)))
    response = client.post(DSA, json=payload(),
                           headers={"Authorization": f"Bearer {token}"})
    assert token not in response.text
    assert str(USER_A) not in response.text, "the owner id need not be echoed"
    assert "Authorization" not in response.text


def test_only_declared_columns_reach_postgresql(admin_conn):
    """No speculative fields: unused personal data is a liability."""
    columns = {r[0] for r in admin_conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'dsa_activities'").fetchall()}
    assert columns == {
        "id", "user_id", "problem_title", "problem_ref", "topic", "difficulty",
        "outcome", "minutes_spent", "platform", "occurred_at", "created_at",
    }
    for absent in ("code", "submission", "url", "runtime", "memory", "language",
                   "company", "notes", "tenant_id", "org_id"):
        assert absent not in columns
