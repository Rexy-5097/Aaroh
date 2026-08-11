"""Snapshot aggregation against PostgreSQL (ADR-0067).

Proves the SQL half of the contract: that the aggregation is scoped by RLS
rather than by a WHERE clause, that it agrees exactly with the pure builder, and
that it stays correct and bounded for a student with far more history than any
API listing would return.

Activities are inserted through `request_transaction` under a real identity, so
the rows arrive by the same path production uses. `occurred_at` is then adjusted
with the admin connection where a test needs a specific instant -- it is not
client-settable by design (ADR-0066).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import psycopg
import pytest

from app.auth.testing import identity_for
from app.db.session import request_transaction
from app.db.snapshot import aggregate_dsa, load_snapshot
from app.domain.dsa import TOPICS
from app.domain.snapshot import TopicStat, snapshot_from_activities
from conftest import USER_A, USER_B

FAR_FUTURE = datetime(2099, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clean_activities(admin_conn):
    admin_conn.execute("DELETE FROM public.dsa_activities")
    yield


def insert(pool, subject: UUID, **fields) -> None:
    """Record one activity as `subject`, through the sanctioned path."""
    record = {
        "problem_title": "Two Sum", "problem_ref": "two sum", "topic": "arrays",
        "difficulty": "easy", "outcome": "solved", "minutes_spent": None,
        "platform": None,
    }
    record.update(fields)
    with request_transaction(pool, identity_for(subject)) as conn:
        conn.execute(
            "INSERT INTO public.dsa_activities "
            "(problem_title, problem_ref, topic, difficulty, outcome, "
            " minutes_spent, platform) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            tuple(record[k] for k in
                  ("problem_title", "problem_ref", "topic", "difficulty",
                   "outcome", "minutes_spent", "platform")),
        )


def snapshot_for(pool, subject: UUID, as_of: datetime = FAR_FUTURE):
    with request_transaction(pool, identity_for(subject)) as conn:
        return load_snapshot(conn, subject=subject, as_of=as_of)


def topic_of(snapshot, topic: str) -> TopicStat:
    (stat,) = [t for t in snapshot.dsa.topics if t.topic == topic]
    return stat


def all_rows(admin_conn, subject: UUID) -> list[dict]:
    """Every stored activity for `subject`, as the pure builder consumes them."""
    rows = admin_conn.execute(
        "SELECT topic, difficulty, outcome, minutes_spent, occurred_at "
        "FROM public.dsa_activities WHERE user_id = %s", (subject,)
    ).fetchall()
    keys = ("topic", "difficulty", "outcome", "minutes_spent", "occurred_at")
    return [dict(zip(keys, r)) for r in rows]


# ── The aggregation works ────────────────────────────────────────────────────

def test_an_empty_history_aggregates_to_a_valid_snapshot(pool):
    snapshot = snapshot_for(pool, USER_A)
    assert snapshot.dsa.total_activities == 0
    assert snapshot.dsa.first_activity_at is None
    assert len(snapshot.dsa.topics) == len(TOPICS)


def test_a_single_activity_is_counted(pool):
    insert(pool, USER_A)
    snapshot = snapshot_for(pool, USER_A)
    assert snapshot.dsa.total_activities == 1
    assert topic_of(snapshot, "arrays").solved == 1
    assert snapshot.dsa.first_activity_at == snapshot.dsa.last_activity_at


def test_counts_are_grouped_by_topic_difficulty_and_outcome(pool):
    insert(pool, USER_A, topic="graphs", difficulty="hard", outcome="solved")
    insert(pool, USER_A, topic="graphs", difficulty="hard", outcome="attempted")
    insert(pool, USER_A, topic="graphs", difficulty="easy", outcome="solved")
    insert(pool, USER_A, topic="trees", difficulty="medium", outcome="attempted")

    snapshot = snapshot_for(pool, USER_A)
    assert snapshot.dsa.total_activities == 4

    graphs = {d.difficulty: d for d in topic_of(snapshot, "graphs").by_difficulty}
    assert (graphs["hard"].solved, graphs["hard"].attempted) == (1, 1)
    assert (graphs["easy"].solved, graphs["easy"].attempted) == (1, 0)
    assert (graphs["medium"].solved, graphs["medium"].attempted) == (0, 0)
    assert topic_of(snapshot, "trees").attempted == 1


def test_minutes_are_summed_and_counted_separately(pool):
    insert(pool, USER_A, topic="heaps", minutes_spent=20)
    insert(pool, USER_A, topic="heaps", minutes_spent=None)
    insert(pool, USER_A, topic="heaps", minutes_spent=35)

    stat = topic_of(snapshot_for(pool, USER_A), "heaps")
    assert stat.minutes_recorded == 55
    assert stat.activities_with_minutes == 2, "NULL must not be counted as recorded"
    assert stat.solved == 3


def test_a_topic_with_only_null_minutes_reports_zero_of_both(pool):
    """coalesce turns a NULL SUM into 0; count(minutes_spent) stays 0. The pair
    says "nothing recorded", which is not "zero minutes spent"."""
    insert(pool, USER_A, topic="sorting")
    stat = topic_of(snapshot_for(pool, USER_A), "sorting")
    assert (stat.minutes_recorded, stat.activities_with_minutes) == (0, 0)


def test_the_vocabulary_is_dense_even_with_one_topic_practised(pool):
    insert(pool, USER_A, topic="greedy")
    snapshot = snapshot_for(pool, USER_A)
    assert tuple(t.topic for t in snapshot.dsa.topics) == TOPICS
    assert topic_of(snapshot, "greedy").solved == 1
    assert topic_of(snapshot, "graphs").last_practised_at is None


# ── Temporal semantics against real timestamps ───────────────────────────────

def test_the_as_of_bound_is_applied_in_sql(pool, admin_conn):
    insert(pool, USER_A)
    (occurred,) = admin_conn.execute(
        "SELECT occurred_at FROM public.dsa_activities").fetchone()

    before = snapshot_for(pool, USER_A, as_of=occurred - timedelta(microseconds=1))
    exactly = snapshot_for(pool, USER_A, as_of=occurred)
    after = snapshot_for(pool, USER_A, as_of=occurred + timedelta(microseconds=1))

    assert before.dsa.total_activities == 0, "an activity after as_of must be excluded"
    assert exactly.dsa.total_activities == 1, "the bound is inclusive"
    assert after.dsa.total_activities == 1


def test_future_activity_is_excluded_from_an_earlier_snapshot(pool, admin_conn):
    insert(pool, USER_A, topic="graphs")
    insert(pool, USER_A, topic="trees")
    admin_conn.execute(
        "UPDATE public.dsa_activities SET occurred_at = now() + interval '10 days' "
        "WHERE topic = 'trees'")

    snapshot = snapshot_for(pool, USER_A, as_of=datetime.now(timezone.utc))
    assert snapshot.dsa.total_activities == 1
    assert topic_of(snapshot, "graphs").solved == 1
    assert topic_of(snapshot, "trees").solved == 0
    assert topic_of(snapshot, "trees").last_practised_at is None


def test_replaying_the_same_as_of_reproduces_the_snapshot(pool):
    for topic in ("graphs", "trees", "heaps"):
        insert(pool, USER_A, topic=topic, minutes_spent=15)
    as_of = datetime.now(timezone.utc) + timedelta(days=1)
    assert snapshot_for(pool, USER_A, as_of=as_of) == snapshot_for(pool, USER_A, as_of=as_of)


def test_a_snapshot_is_unchanged_by_later_practice(pool, admin_conn):
    """The replay guarantee ADR-0060 depends on: a stored trace must re-derive
    the snapshot the engine actually saw, not a newer one."""
    insert(pool, USER_A, topic="graphs")
    (frozen_at,) = admin_conn.execute(
        "SELECT max(occurred_at) FROM public.dsa_activities").fetchone()
    original = snapshot_for(pool, USER_A, as_of=frozen_at)

    # The new activity is placed strictly after the frozen instant. The earlier
    # row is left untouched -- moving it would change the very state the
    # snapshot is supposed to have captured, which is what this test asserts.
    insert(pool, USER_A, topic="trees")
    admin_conn.execute(
        "UPDATE public.dsa_activities SET occurred_at = %s + interval '1 day' "
        "WHERE topic = 'trees'", (frozen_at,))

    assert snapshot_for(pool, USER_A, as_of=frozen_at) == original
    assert snapshot_for(pool, USER_A).dsa.total_activities == 2, "the new row does exist"


def test_timestamps_are_normalised_to_utc(pool):
    """psycopg returns timestamptz in the DATABASE SESSION's timezone, so a
    snapshot read under a non-UTC session would serialise differently into a
    trace while comparing equal as an instant. Reproducibility has to hold
    across processes (standards/decision_engine.md), so the boundary normalises.
    """
    insert(pool, USER_A, topic="graphs", minutes_spent=5)
    with request_transaction(pool, identity_for(USER_A)) as conn:
        conn.execute("SET LOCAL TimeZone = 'Asia/Kolkata'")
        kolkata = load_snapshot(conn, subject=USER_A, as_of=FAR_FUTURE)
    with request_transaction(pool, identity_for(USER_A)) as conn:
        conn.execute("SET LOCAL TimeZone = 'America/Los_Angeles'")
        los_angeles = load_snapshot(conn, subject=USER_A, as_of=FAR_FUTURE)

    assert kolkata == los_angeles
    for stamp in (kolkata.dsa.first_activity_at, kolkata.dsa.last_activity_at,
                  topic_of(kolkata, "graphs").last_practised_at):
        assert stamp.utcoffset() == timedelta(0), "a snapshot timestamp is not UTC"
    assert kolkata.dsa.last_activity_at.tzinfo is timezone.utc


# ── Agreement with the pure builder (ADR-0067 section 11) ────────────────────

def test_the_sql_aggregation_agrees_with_the_pure_builder(pool, admin_conn):
    """The two paths must not be able to drift. Anything the SQL counts
    differently from the in-memory builder shows up here as inequality."""
    for index, topic in enumerate(TOPICS[:8]):
        insert(pool, USER_A, topic=topic,
               difficulty=("easy", "medium", "hard")[index % 3],
               outcome=("solved", "attempted")[index % 2],
               minutes_spent=None if index % 3 == 0 else 10 + index)

    from_sql = snapshot_for(pool, USER_A)
    from_rows = snapshot_from_activities(
        subject=USER_A, as_of=FAR_FUTURE, activities=all_rows(admin_conn, USER_A))
    assert from_sql == from_rows


def test_the_two_paths_agree_on_an_empty_history(pool, admin_conn):
    assert snapshot_for(pool, USER_A) == snapshot_from_activities(
        subject=USER_A, as_of=FAR_FUTURE, activities=all_rows(admin_conn, USER_A))


# ── Scale: no pagination limit may affect correctness ────────────────────────

def test_a_history_larger_than_the_api_page_is_counted_in_full(pool):
    """`db/dsa.py` bounds listing at 100 rows. A snapshot built from that path
    would silently truncate -- ADR-0067 section 6 forbids reusing it."""
    from app.db.dsa import DEFAULT_LIMIT

    total = DEFAULT_LIMIT * 3 + 7
    with request_transaction(pool, identity_for(USER_A)) as conn:
        for index in range(total):
            conn.execute(
                "INSERT INTO public.dsa_activities "
                "(problem_title, problem_ref, topic, difficulty, outcome, minutes_spent) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (f"P{index}", f"p{index}", TOPICS[index % len(TOPICS)],
                 "medium", "solved", 5),
            )

    snapshot = snapshot_for(pool, USER_A)
    assert snapshot.dsa.total_activities == total > DEFAULT_LIMIT
    assert sum(t.solved + t.attempted for t in snapshot.dsa.topics) == total
    assert sum(t.minutes_recorded for t in snapshot.dsa.topics) == total * 5
    assert sum(t.activities_with_minutes for t in snapshot.dsa.topics) == total


def test_thousands_of_activities_aggregate_to_a_bounded_row_set(pool):
    """Cost is flat in history size: the GROUP BY can never return more than
    16 topics x 3 difficulties x 2 outcomes, whatever the student has done."""
    with request_transaction(pool, identity_for(USER_A)) as conn:
        conn.execute(
            "INSERT INTO public.dsa_activities "
            "(problem_title, problem_ref, topic, difficulty, outcome, minutes_spent) "
            "SELECT 'P' || i, 'p' || i, t.topic, d.difficulty, o.outcome, 3 "
            "  FROM generate_series(1, 250) AS i, "
            "       (VALUES ('arrays'), ('graphs'), ('trees')) AS t(topic), "
            "       (VALUES ('easy'), ('hard')) AS d(difficulty), "
            "       (VALUES ('solved'), ('attempted')) AS o(outcome)"
        )
        rows = aggregate_dsa(conn, as_of=FAR_FUTURE)
        snapshot = load_snapshot(conn, subject=USER_A, as_of=FAR_FUTURE)

    assert snapshot.dsa.total_activities == 250 * 3 * 2 * 2
    assert len(rows) == 3 * 2 * 2, "one row per occurring (topic, difficulty, outcome)"
    assert len(rows) <= len(TOPICS) * 3 * 2
    assert topic_of(snapshot, "arrays").solved == 500
    assert topic_of(snapshot, "arrays").minutes_recorded == 1000 * 3


# ── Security: RLS is the only scope ──────────────────────────────────────────

def test_a_snapshot_never_sees_another_student(pool):
    insert(pool, USER_A, topic="graphs")
    insert(pool, USER_A, topic="graphs")
    insert(pool, USER_B, topic="trees")

    a = snapshot_for(pool, USER_A)
    assert a.dsa.total_activities == 2
    assert topic_of(a, "graphs").solved == 2
    assert topic_of(a, "trees").solved == 0, "user B's practice leaked into A's snapshot"


def test_the_isolation_holds_in_the_other_direction(pool):
    insert(pool, USER_A, topic="graphs")
    insert(pool, USER_B, topic="trees")
    insert(pool, USER_B, topic="trees")

    b = snapshot_for(pool, USER_B)
    assert b.dsa.total_activities == 2
    assert topic_of(b, "trees").solved == 2
    assert topic_of(b, "graphs").solved == 0, "user A's practice leaked into B's snapshot"


def test_naming_another_subject_does_not_widen_the_snapshot(pool):
    """`subject` labels a snapshot; it does not scope one. Passing someone
    else's id must not fetch their rows -- RLS answers to the transaction
    identity, not to an argument."""
    insert(pool, USER_B, topic="trees")
    with request_transaction(pool, identity_for(USER_A)) as conn:
        mislabelled = load_snapshot(conn, subject=USER_B, as_of=FAR_FUTURE)

    assert mislabelled.dsa.total_activities == 0
    assert topic_of(mislabelled, "trees").solved == 0


def test_the_aggregation_requires_a_verified_identity(pool):
    """There is no second path to the data: the aggregation can only run on a
    connection `request_transaction` has bound (ADR-0063 I-19)."""
    from app.db.session import UnverifiedIdentityError

    with pytest.raises(UnverifiedIdentityError):
        with request_transaction(pool, {"sub": str(USER_A), "role": "authenticated"}):
            pass


def test_the_aggregation_query_names_no_user_column(pool):
    """RLS is the filter. A WHERE user_id clause would be a second, weaker
    authorization path that could drift from the policy."""
    from app.db import snapshot as module

    assert "user_id" not in module._AGGREGATE_SQL
    assert "auth.uid" not in module._AGGREGATE_SQL


def test_an_unauthenticated_role_cannot_aggregate(pool):
    """anon has been revoked on the table; the aggregation must not be a way in."""
    with request_transaction(pool, identity_for(USER_A)) as conn:
        conn.execute("SET LOCAL ROLE anon")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            aggregate_dsa(conn, as_of=FAR_FUTURE)


def test_the_snapshot_reads_no_preparation_goal(pool, admin_conn):
    """ADR-0067 section 7 and section 11: goal data is `constraints`. If the
    aggregation touched it, the snapshot would change when a goal is set."""
    insert(pool, USER_A, topic="graphs")
    before = snapshot_for(pool, USER_A)

    with request_transaction(pool, identity_for(USER_A)) as conn:
        conn.execute(
            "INSERT INTO public.preparation_goals "
            "(target_role, target_company, deadline, weekly_hours) "
            "VALUES ('SDE', 'Acme', current_date + 90, 12)")

    assert snapshot_for(pool, USER_A) == before
    assert admin_conn.execute(
        "SELECT count(*) FROM public.preparation_goals").fetchone()[0] == 1
