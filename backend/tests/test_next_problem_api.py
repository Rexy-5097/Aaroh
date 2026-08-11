"""The recommendation endpoint: HTTP -> identity -> RLS -> snapshot -> rank().

Proves the whole chain end to end, and proves the property that matters most for
the product: **changing what a student practises changes what Aaroh recommends.**

Every expected recommendation below names the decision that produces it:
  ADR-0065     a goal is a precondition; 404 when absent
  ADR-0070 s6  foundational ordering for insufficiently observed topics
  ADR-0071 s3  lower solve rate = weaker
  ADR-0071 s4  a topic needs >= 3 recorded activities
  ADR-0072 B1  repair-first
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth.config import AuthConfig
from app.auth.jwks import JwksCache
from app.auth.verifier import JwtVerifier
from app.domain.catalogue_v1 import V1_CATALOGUE
from app.http.app import create_app
from auth_fixtures import ISSUER, KeyPair, jwks_document, valid_claims
from conftest import USER_A, USER_B

NEXT = "/v1/next-problem"
GOAL = "/v1/preparation-goal"
DSA = "/v1/dsa-activity"


@pytest.fixture()
def key() -> KeyPair:
    return KeyPair("next-kid", "ES256")


@pytest.fixture()
def client(key, pool) -> TestClient:
    verifier = JwtVerifier(AuthConfig.from_issuer(ISSUER), JwksCache(lambda: jwks_document(key)))
    return TestClient(create_app(verifier, pool=pool))


@pytest.fixture(autouse=True)
def clean(admin_conn):
    admin_conn.execute("DELETE FROM public.dsa_activities")
    admin_conn.execute("DELETE FROM public.preparation_goals")
    yield


def auth(key, subject) -> dict[str, str]:
    return {"Authorization": f"Bearer {key.sign(valid_claims(sub=str(subject)))}"}


def set_goal(client, key, subject=USER_A):
    body = {
        "target_role": "Backend SWE", "target_company": None,
        "deadline": (date.today() + timedelta(days=120)).isoformat(),
        "weekly_hours": 10,
    }
    assert client.put(GOAL, json=body, headers=auth(key, subject)).status_code == 200


def practise(client, key, topic, solved=0, attempted=0, subject=USER_A):
    for outcome, count in (("solved", solved), ("attempted", attempted)):
        for n in range(count):
            body = {"problem_title": f"{topic}-{outcome}-{n}", "topic": topic,
                    "difficulty": "medium", "outcome": outcome}
            assert client.post(DSA, json=body, headers=auth(key, subject)).status_code == 201


def recommend(client, key, subject=USER_A):
    return client.get(NEXT, headers=auth(key, subject))


# ── The capability works ─────────────────────────────────────────────────────

def test_a_cold_student_receives_the_first_foundational_problem(client, key):
    """ADR-0070 s5: no history means every signal ties, so the foundational
    ordering decides. `arrays` is position 1 and `two-sum` is its only carrier."""
    set_goal(client, key)
    response = recommend(client, key)
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "two-sum"
    assert body["reason"] == "foundational"
    assert body["reason_topic"] == "arrays"


def test_the_response_carries_exactly_the_declared_fields(client, key):
    set_goal(client, key)
    body = recommend(client, key).json()
    assert set(body) == {"slug", "title", "topics", "difficulty", "reason", "reason_topic"}
    assert body["title"] == "Two Sum"
    assert body["difficulty"] == "easy"
    assert sorted(body["topics"]) == ["arrays", "hash-tables"]


# ── Preconditions (ADR-0065) ─────────────────────────────────────────────────

def test_without_a_preparation_goal_there_is_no_recommendation(client, key):
    """ADR-0065's product rule: "No recommendation may exist without a deadline
    and a time budget." Reuses the 404 that GET /v1/preparation-goal already
    returns rather than inventing a status code."""
    response = recommend(client, key)
    assert response.status_code == 404
    assert "preparation goal" in response.json()["detail"]["message"]


def test_a_goal_whose_deadline_has_passed_still_yields_a_recommendation(client, key,
                                                                        admin_conn):
    """A goal written months ago must not make the endpoint fail. Whether an
    expired goal should change the advice is an open product question; refusing
    to answer at all would be a worse default than answering."""
    set_goal(client, key)
    admin_conn.execute("UPDATE public.preparation_goals SET deadline = %s",
                       (date.today() - timedelta(days=5),))
    assert recommend(client, key).status_code == 200


# ── Evidence threshold and repair-first ──────────────────────────────────────

def test_two_activities_are_not_enough_to_change_the_recommendation(client, key):
    """ADR-0071 s4: below three the topic stays foundational however bad it looks."""
    set_goal(client, key)
    practise(client, key, "graphs", solved=0, attempted=2)
    assert recommend(client, key).json()["slug"] == "two-sum"


def test_three_activities_with_no_solves_flips_to_repair_first(client, key):
    """THE PRODUCT MOMENT. `graphs` sits at foundational position 13 -- nearly
    last -- yet three activities with no solves put it first (ADR-0072 B1)."""
    set_goal(client, key)
    practise(client, key, "graphs", solved=0, attempted=3)
    body = recommend(client, key).json()
    assert body["slug"] == "course-schedule"
    assert body["reason"] == "weak-topic"
    assert body["reason_topic"] == "graphs"


def test_the_weakest_of_several_eligible_topics_wins(client, key):
    """ADR-0071 s3: 1/4 in graphs is a lower solve rate than 3/4 in trees."""
    set_goal(client, key)
    practise(client, key, "graphs", solved=1, attempted=3)
    practise(client, key, "trees", solved=3, attempted=1)
    assert recommend(client, key).json()["reason_topic"] == "graphs"


def test_a_strong_topic_does_not_displace_a_weak_one(client, key):
    """Practising something well must not make Aaroh recommend more of it."""
    set_goal(client, key)
    practise(client, key, "strings", solved=5, attempted=0)
    practise(client, key, "graphs", solved=0, attempted=3)
    assert recommend(client, key).json()["reason_topic"] == "graphs"


# ── The product journey: behaviour -> snapshot -> ranking -> recommendation ──

def test_the_recommendation_changes_as_the_student_practises(client, key):
    """The hypothesis this whole slice exists to test.

    A student starts cold, struggles with graphs, then improves at graphs while
    neglecting trees -- and Aaroh's advice follows them at each step.
    """
    set_goal(client, key)

    # 1. Cold: the foundational ordering leads.
    assert recommend(client, key).json()["slug"] == "two-sum"

    # 2. Three failed attempts at graphs: repair-first takes over.
    practise(client, key, "graphs", solved=0, attempted=3)
    step2 = recommend(client, key).json()
    assert step2["reason_topic"] == "graphs" and step2["reason"] == "weak-topic"

    # 3. Now weak in trees too, and worse there (0/3 vs graphs' 0/3 -> tie broken
    #    by foundational order, trees=11 before graphs=13).
    practise(client, key, "trees", solved=0, attempted=3)
    assert recommend(client, key).json()["reason_topic"] == "trees"

    # 4. Solve several trees problems: graphs becomes the weaker topic again.
    practise(client, key, "trees", solved=6, attempted=0)
    step4 = recommend(client, key).json()
    assert step4["reason_topic"] == "graphs"
    assert step4["slug"] == "course-schedule"


# ── Isolation (ADR-0061) ─────────────────────────────────────────────────────

def test_another_students_history_cannot_influence_the_recommendation(client, key):
    """USER_B practising graphs heavily must not change USER_A's advice."""
    set_goal(client, key, USER_A)
    practise(client, key, "graphs", solved=0, attempted=9, subject=USER_B)
    assert recommend(client, key, USER_A).json()["slug"] == "two-sum"


def test_each_student_receives_their_own_recommendation(client, key):
    set_goal(client, key, USER_A)
    set_goal(client, key, USER_B)
    practise(client, key, "graphs", solved=0, attempted=3, subject=USER_A)
    practise(client, key, "trees", solved=0, attempted=3, subject=USER_B)
    assert recommend(client, key, USER_A).json()["reason_topic"] == "graphs"
    assert recommend(client, key, USER_B).json()["reason_topic"] == "trees"


def test_another_students_goal_does_not_satisfy_the_precondition(client, key):
    """USER_B having a goal must not let USER_A get a recommendation."""
    set_goal(client, key, USER_B)
    assert recommend(client, key, USER_A).status_code == 404


# ── Authentication (ADR-0064) ────────────────────────────────────────────────

def test_an_unauthenticated_request_is_rejected(client):
    assert client.get(NEXT).status_code == 401


@pytest.mark.parametrize("header", [
    {}, {"Authorization": "Bearer"}, {"Authorization": "Bearer bad.token.here"},
    {"Authorization": "Basic abc"},
])
def test_bad_credentials_are_rejected(client, header):
    assert client.get(NEXT, headers=header).status_code == 401


def test_a_client_supplied_user_id_cannot_change_whose_history_is_used(client, key):
    """The identity comes from the verified token. A query parameter naming
    another student must not reach the data (ADR-0061 I-4)."""
    set_goal(client, key, USER_A)
    practise(client, key, "graphs", solved=0, attempted=3, subject=USER_B)
    body = client.get(f"{NEXT}?user_id={USER_B}", headers=auth(key, USER_A)).json()
    assert body["slug"] == "two-sum", "USER_B's history leaked into USER_A's recommendation"


def test_a_rejected_role_cannot_reach_the_endpoint(client, key):
    token = key.sign(valid_claims(sub=str(USER_A), role="anon"))
    assert client.get(NEXT, headers={"Authorization": f"Bearer {token}"}).status_code == 401


# ── Determinism ──────────────────────────────────────────────────────────────

def test_repeated_requests_with_unchanged_data_are_identical(client, key):
    set_goal(client, key)
    practise(client, key, "graphs", solved=1, attempted=3)
    first = recommend(client, key).json()
    for _ in range(4):
        assert recommend(client, key).json() == first


# ── Privacy (standards/privacy.md) ───────────────────────────────────────────

def test_the_response_leaks_no_identity_token_or_goal(client, key):
    set_goal(client, key)
    token = key.sign(valid_claims(sub=str(USER_A)))
    response = client.get(NEXT, headers={"Authorization": f"Bearer {token}"})
    text = response.text
    assert token not in text
    assert str(USER_A) not in text, "the owner id must not be echoed"
    for high_class in ("Backend SWE", "target_role", "target_company", "deadline",
                       "weekly_hours"):
        assert high_class not in text, f"{high_class} is High-class and must not appear"


def test_the_response_carries_no_score_or_confidence(client, key):
    """ADR-0071 s3.1: weakness is ordinal with no magnitude, so there is no
    number to report; confidence has no definition anywhere."""
    set_goal(client, key)
    body = recommend(client, key).json()
    for invented in ("score", "confidence", "weight", "rank", "position", "rating"):
        assert invented not in body


def test_the_recommendation_does_not_expose_the_whole_candidate_set(client, key):
    """One primary recommendation per day (context/architecture.md). The full
    candidate set belongs in the trace, which this slice does not build."""
    set_goal(client, key)
    body = recommend(client, key).json()
    assert isinstance(body, dict) and "candidates" not in body


# ── The catalogue (ADR-0069) ─────────────────────────────────────────────────

def test_the_v1_catalogue_is_valid_and_is_the_only_definition(client, key):
    assert len(V1_CATALOGUE) == 12
    assert len({i.slug for i in V1_CATALOGUE}) == 12
    for item in V1_CATALOGUE:
        assert item.topics and item.difficulty in ("easy", "medium", "hard")


def test_the_catalogue_carries_no_estimated_time(client, key):
    """ADR-0069 s10 rejected invented per-item durations."""
    import dataclasses
    for item in V1_CATALOGUE:
        names = {f.name for f in dataclasses.fields(item)}
        for forbidden in ("minutes", "duration", "estimated", "time"):
            assert not any(forbidden in n for n in names)


def test_an_empty_catalogue_is_refused_rather_than_guessed(client, key, monkeypatch):
    """Defensive: V1_CATALOGUE is a non-empty constant so this is unreachable in
    production, but an empty one must produce an honest 404 rather than an
    index error or an invented recommendation."""
    import app.http.routes.next_problem as route
    monkeypatch.setattr(route, "V1_CATALOGUE", ())
    set_goal(client, key)
    response = recommend(client, key)
    assert response.status_code == 404
    assert "candidate" in response.json()["detail"]["message"]


def test_the_snapshot_is_labelled_with_the_authenticated_subject(client, key, monkeypatch):
    """Closes a gap mutation testing found.

    `subject` LABELS a snapshot; RLS SCOPES it (`app/db/snapshot.py`). So passing
    the wrong subject changes no row and no recommendation -- it is invisible
    through the response. It would stop being invisible the moment a snapshot is
    copied into a decision trace (`ADR-0060`), where a mislabelled subject would
    attribute one student's reasoning to another.

    Asserted here rather than left for the trace slice to discover.
    """
    import app.http.routes.next_problem as route

    seen = {}
    original = route.rank

    def capture(snapshot, constraints, catalog, weights=None):
        seen["subject"] = snapshot.subject
        return original(snapshot, constraints, catalog, weights)

    monkeypatch.setattr(route, "rank", capture)
    set_goal(client, key, USER_A)
    assert recommend(client, key, USER_A).status_code == 200
    assert seen["subject"] == USER_A
