"""Readiness snapshot domain rules (ADR-0067).

Pure unit tests -- no database, no HTTP, no clock. That this file can exist at
all is the point: ADR-0059 requires the engine be testable "with no database,
network, or fixtures beyond plain data", which is only true if its input can be
constructed the same way.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import UUID

import pytest

from app.domain.dsa import DIFFICULTIES, MAX_MINUTES, MIN_MINUTES, OUTCOMES, TOPICS
from app.domain.snapshot import (
    DifficultyStat,
    DsaSnapshot,
    NaiveTimestamp,
    StudentSnapshot,
    TopicStat,
    UnknownTopic,
    snapshot_from_activities,
    snapshot_from_aggregates,
)

SUBJECT = UUID("11111111-1111-4111-8111-111111111111")
OTHER = UUID("22222222-2222-4222-8222-222222222222")
NOON = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def activity(**overrides) -> dict:
    record = {
        "topic": "arrays",
        "difficulty": "easy",
        "outcome": "solved",
        "minutes_spent": None,
        "occurred_at": NOON - timedelta(hours=1),
    }
    record.update(overrides)
    return record


def build(*activities, subject=SUBJECT, as_of=NOON) -> StudentSnapshot:
    return snapshot_from_activities(subject=subject, as_of=as_of, activities=activities)


def topic_of(snapshot: StudentSnapshot, topic: str) -> TopicStat:
    (stat,) = [t for t in snapshot.dsa.topics if t.topic == topic]
    return stat


@lru_cache(maxsize=1)
def _domain_ast() -> ast.Module:
    from app.domain import snapshot as module

    return ast.parse(inspect.getsource(module))


# ── Data model: immutability ─────────────────────────────────────────────────

def test_the_snapshot_is_immutable():
    snapshot = build(activity())
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.as_of = NOON  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.dsa = None  # type: ignore[misc]


def test_nested_structures_are_immutable():
    snapshot = build(activity())
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.dsa.total_activities = 99  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        topic_of(snapshot, "arrays").solved = 99  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        topic_of(snapshot, "arrays").by_difficulty[0].solved = 99  # type: ignore[misc]


def test_no_mutable_collection_leaks_into_a_snapshot():
    """A list or dict anywhere in the structure would let a consumer mutate a
    snapshot another consumer is still holding -- and would break equality."""
    snapshot = build(activity())
    assert isinstance(snapshot.dsa.topics, tuple)
    for stat in snapshot.dsa.topics:
        assert isinstance(stat.by_difficulty, tuple)
        for field in dataclasses.fields(stat):
            assert not isinstance(getattr(stat, field.name), (list, dict, set))


def test_mutating_the_input_afterwards_does_not_change_the_snapshot():
    records = [activity()]
    snapshot = build(*records)
    records.append(activity(topic="graphs"))
    records[0]["topic"] = "trees"
    assert snapshot.dsa.total_activities == 1
    assert topic_of(snapshot, "arrays").solved == 1


def test_snapshots_are_comparable_and_hashable():
    """Equality is structural, so a determinism test is `==` rather than a walk."""
    assert build(activity()) == build(activity())
    assert build(activity()) != build(activity(topic="graphs"))
    assert len({build(activity()), build(activity())}) == 1


# ── Data model: the empty case ───────────────────────────────────────────────

def test_a_student_with_no_activity_has_a_valid_snapshot():
    """ADR-0067 section 9: a snapshot is total. It is never an error and never
    substitutes defaults -- `context/state.md` records that a new user with no
    DSA history must still get a useful first session."""
    snapshot = build()
    assert isinstance(snapshot, StudentSnapshot)
    assert isinstance(snapshot.dsa, DsaSnapshot)
    assert snapshot.dsa.total_activities == 0
    assert snapshot.dsa.first_activity_at is None
    assert snapshot.dsa.last_activity_at is None
    assert len(snapshot.dsa.topics) == len(TOPICS)


def test_every_topic_is_zeroed_in_an_empty_snapshot():
    for stat in build().dsa.topics:
        assert (stat.solved, stat.attempted) == (0, 0)
        assert (stat.minutes_recorded, stat.activities_with_minutes) == (0, 0)
        assert stat.last_practised_at is None
        assert all(d.solved == 0 and d.attempted == 0 for d in stat.by_difficulty)


def test_the_subject_is_carried_and_not_invented():
    assert build(activity(), subject=OTHER).subject == OTHER


def test_as_of_is_carried():
    other_time = NOON - timedelta(days=3)
    assert build(as_of=other_time).as_of == other_time


@pytest.mark.parametrize("offset_hours", [5.5, -8, 0, 13])
def test_as_of_is_normalised_to_utc(offset_hours):
    """Regression: `_utc(as_of)` once had its return value discarded, so `as_of`
    kept the CALLER's timezone while every database-derived timestamp was
    normalised. The two snapshots below compare equal -- aware datetimes compare
    by instant -- so equality could not detect it. They serialised differently,
    and a snapshot is serialised into every stored trace (ADR-0060).

    The original normalisation test only covered the timestamps that come out of
    PostgreSQL, which is exactly why it missed the one field the model is
    anchored to.
    """
    zone = timezone(timedelta(hours=offset_hours))
    same_instant = NOON.astimezone(zone)

    snapshot = build(as_of=same_instant)
    assert snapshot.as_of.tzinfo is timezone.utc
    assert snapshot.as_of.utcoffset() == timedelta(0)
    assert snapshot.as_of.isoformat() == NOON.isoformat()
    assert snapshot == build(as_of=NOON), "representation must not affect the snapshot"


def test_every_snapshot_timestamp_is_utc():
    """Sweeps the whole structure rather than naming fields, so a timestamp
    added later cannot quietly escape normalisation."""
    zone = timezone(timedelta(hours=5, minutes=30))
    snapshot = snapshot_from_activities(
        subject=SUBJECT,
        as_of=NOON.astimezone(zone),
        activities=[activity(occurred_at=(NOON - timedelta(days=1)).astimezone(zone),
                             minutes_spent=10)],
    )
    stamps = [snapshot.as_of, snapshot.dsa.first_activity_at, snapshot.dsa.last_activity_at]
    stamps += [t.last_practised_at for t in snapshot.dsa.topics if t.last_practised_at]
    assert len(stamps) == 4, "expected as_of, first, last and one topic timestamp"
    for stamp in stamps:
        assert stamp.tzinfo is timezone.utc, f"{stamp!r} is not UTC"


# ── Temporal semantics (ADR-0067 section 5) ──────────────────────────────────

def test_activity_before_as_of_is_included():
    assert build(activity(occurred_at=NOON - timedelta(seconds=1))).dsa.total_activities == 1


def test_activity_exactly_at_as_of_is_included():
    """The bound is `<=`. A boundary-exclusive bound would drop the most recent
    practice from every snapshot taken at the instant it was recorded."""
    assert build(activity(occurred_at=NOON)).dsa.total_activities == 1


def test_activity_after_as_of_is_excluded():
    snapshot = build(activity(occurred_at=NOON + timedelta(seconds=1)))
    assert snapshot.dsa.total_activities == 0
    assert snapshot.dsa.last_activity_at is None
    assert topic_of(snapshot, "arrays").last_practised_at is None


def test_the_as_of_boundary_partitions_a_mixed_history():
    snapshot = build(
        activity(occurred_at=NOON - timedelta(days=1)),
        activity(occurred_at=NOON),
        activity(occurred_at=NOON + timedelta(microseconds=1)),
        activity(occurred_at=NOON + timedelta(days=1)),
    )
    assert snapshot.dsa.total_activities == 2
    assert snapshot.dsa.last_activity_at == NOON


def test_replaying_with_the_same_as_of_is_identical():
    """ADR-0060's replay guarantee: the same rows and the same instant must
    reproduce the same snapshot, or a stored trace cannot be re-derived."""
    records = [activity(occurred_at=NOON - timedelta(hours=h)) for h in range(1, 6)]
    assert build(*records) == build(*records)


def test_a_later_as_of_sees_more_history():
    records = [activity(occurred_at=NOON + timedelta(days=1))]
    assert build(*records).dsa.total_activities == 0
    assert build(*records, as_of=NOON + timedelta(days=2)).dsa.total_activities == 1


def test_the_builder_refuses_a_naive_as_of():
    """Aaroh works in UTC throughout. A naive datetime would compare
    inconsistently and reach PostgreSQL as session-local time."""
    with pytest.raises(NaiveTimestamp):
        snapshot_from_activities(
            subject=SUBJECT, as_of=datetime(2026, 8, 11, 12), activities=[]
        )


def test_the_builder_refuses_a_naive_occurred_at():
    with pytest.raises(NaiveTimestamp):
        build(activity(occurred_at=datetime(2026, 8, 11, 11)))


def test_the_builder_never_reads_a_clock():
    """A builder that called now() would make snapshots unreproducible before
    the engine was even reached (ADR-0067 section 5).

    Parsed, not grepped: a substring scan would be satisfied by a comment
    promising not to read the clock, which is not the same as not reading it.
    """
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(_domain_ast())
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert not called & {"now", "utcnow", "today", "time", "monotonic"}


# ── Aggregation: counts ──────────────────────────────────────────────────────

def test_total_activities_counts_every_included_record():
    snapshot = build(*[activity(topic=t) for t in TOPICS], activity())
    assert snapshot.dsa.total_activities == len(TOPICS) + 1


def test_first_and_last_activity_timestamps():
    times = [NOON - timedelta(days=d) for d in (5, 1, 3)]
    snapshot = build(*[activity(occurred_at=t) for t in times])
    assert snapshot.dsa.first_activity_at == min(times)
    assert snapshot.dsa.last_activity_at == max(times)


def test_first_and_last_span_different_topics():
    """Both are global extrema, not per-topic ones."""
    early, late = NOON - timedelta(days=9), NOON - timedelta(days=2)
    snapshot = build(
        activity(topic="graphs", occurred_at=early),
        activity(topic="trees", occurred_at=late),
    )
    assert snapshot.dsa.first_activity_at == early
    assert snapshot.dsa.last_activity_at == late


def test_a_single_activity_is_both_first_and_last():
    snapshot = build(activity(occurred_at=NOON - timedelta(hours=2)))
    assert snapshot.dsa.first_activity_at == snapshot.dsa.last_activity_at


def test_per_topic_counts_are_independent():
    snapshot = build(
        activity(topic="graphs"),
        activity(topic="graphs", outcome="attempted"),
        activity(topic="trees"),
    )
    assert (topic_of(snapshot, "graphs").solved, topic_of(snapshot, "graphs").attempted) == (1, 1)
    assert (topic_of(snapshot, "trees").solved, topic_of(snapshot, "trees").attempted) == (1, 0)
    assert topic_of(snapshot, "heaps").solved == 0


def test_per_difficulty_counts_are_independent():
    snapshot = build(
        activity(topic="graphs", difficulty="easy"),
        activity(topic="graphs", difficulty="hard"),
        activity(topic="graphs", difficulty="hard", outcome="attempted"),
    )
    stats = {d.difficulty: d for d in topic_of(snapshot, "graphs").by_difficulty}
    assert (stats["easy"].solved, stats["easy"].attempted) == (1, 0)
    assert (stats["medium"].solved, stats["medium"].attempted) == (0, 0)
    assert (stats["hard"].solved, stats["hard"].attempted) == (1, 1)


def test_topic_counts_equal_the_sum_of_their_difficulty_counts():
    """The two are stored separately (ADR-0067 section 4) so consumers do not
    re-sum differently; that only helps if they cannot disagree."""
    snapshot = build(
        *[activity(topic="graphs", difficulty=d, outcome=o)
          for d in DIFFICULTIES for o in OUTCOMES]
    )
    for stat in snapshot.dsa.topics:
        assert stat.solved == sum(d.solved for d in stat.by_difficulty)
        assert stat.attempted == sum(d.attempted for d in stat.by_difficulty)


def test_total_equals_the_sum_of_every_topic():
    snapshot = build(
        *[activity(topic=t, difficulty=d) for t in ("graphs", "trees") for d in DIFFICULTIES]
    )
    assert snapshot.dsa.total_activities == sum(
        t.solved + t.attempted for t in snapshot.dsa.topics
    )


@pytest.mark.parametrize("outcome", OUTCOMES)
def test_each_outcome_lands_in_its_own_counter(outcome):
    """ADR-0066's meanings are used exactly; no third category is invented and
    success is never inferred from difficulty or minutes."""
    stat = topic_of(build(activity(outcome=outcome)), "arrays")
    assert getattr(stat, outcome) == 1
    other = "attempted" if outcome == "solved" else "solved"
    assert getattr(stat, other) == 0


def test_last_practised_at_is_per_topic():
    recent, older = NOON - timedelta(days=1), NOON - timedelta(days=30)
    snapshot = build(
        activity(topic="graphs", occurred_at=recent),
        activity(topic="trees", occurred_at=older),
    )
    assert topic_of(snapshot, "graphs").last_practised_at == recent
    assert topic_of(snapshot, "trees").last_practised_at == older
    assert topic_of(snapshot, "heaps").last_practised_at is None


def test_last_practised_at_is_the_maximum_not_the_latest_seen():
    """Input order must not decide an extremum."""
    early, late = NOON - timedelta(days=8), NOON - timedelta(days=2)
    forward = build(activity(occurred_at=early), activity(occurred_at=late))
    reverse = build(activity(occurred_at=late), activity(occurred_at=early))
    assert forward == reverse
    assert topic_of(forward, "arrays").last_practised_at == late


# ── Aggregation: minutes (ADR-0067 section 4.2) ──────────────────────────────

def test_minutes_are_summed_when_all_records_have_them():
    snapshot = build(
        activity(minutes_spent=10), activity(minutes_spent=25), activity(minutes_spent=5)
    )
    stat = topic_of(snapshot, "arrays")
    assert stat.minutes_recorded == 40
    assert stat.activities_with_minutes == 3


def test_no_recorded_minutes_is_distinguishable_from_zero_minutes():
    """NULL is never coerced to 0. `minutes_recorded == 0` with
    `activities_with_minutes == 0` means "nothing recorded"; the denominator is
    what stops a consumer averaging over rows that never had a value."""
    stat = topic_of(build(activity(), activity()), "arrays")
    assert stat.minutes_recorded == 0
    assert stat.activities_with_minutes == 0


def test_mixed_null_and_present_minutes():
    snapshot = build(
        activity(minutes_spent=30), activity(minutes_spent=None), activity(minutes_spent=15)
    )
    stat = topic_of(snapshot, "arrays")
    assert stat.minutes_recorded == 45
    assert stat.activities_with_minutes == 2, "the record without minutes must not count"
    assert stat.solved == 3, "but it is still a practice event"


@pytest.mark.parametrize("minutes", [MIN_MINUTES, MAX_MINUTES])
def test_boundary_minute_values_are_summed_unchanged(minutes):
    stat = topic_of(build(activity(minutes_spent=minutes)), "arrays")
    assert stat.minutes_recorded == minutes


def test_minutes_are_summed_across_difficulties_within_a_topic():
    snapshot = build(
        activity(topic="graphs", difficulty="easy", minutes_spent=10),
        activity(topic="graphs", difficulty="hard", minutes_spent=50),
    )
    assert topic_of(snapshot, "graphs").minutes_recorded == 60


def test_minutes_do_not_leak_between_topics():
    snapshot = build(
        activity(topic="graphs", minutes_spent=42), activity(topic="trees", minutes_spent=7)
    )
    assert topic_of(snapshot, "graphs").minutes_recorded == 42
    assert topic_of(snapshot, "trees").minutes_recorded == 7
    assert topic_of(snapshot, "heaps").minutes_recorded == 0


def test_excluded_activities_contribute_no_minutes():
    snapshot = build(activity(minutes_spent=600, occurred_at=NOON + timedelta(days=1)))
    assert topic_of(snapshot, "arrays").minutes_recorded == 0
    assert topic_of(snapshot, "arrays").activities_with_minutes == 0


# ── Dense vocabulary (ADR-0067 section 4.1) ──────────────────────────────────

def test_all_sixteen_topics_are_present():
    assert len(build().dsa.topics) == 16
    assert len(build(activity()).dsa.topics) == 16


def test_topics_appear_exactly_once_each():
    names = [t.topic for t in build(activity(), activity(topic="graphs")).dsa.topics]
    assert len(names) == len(set(names))
    assert set(names) == set(TOPICS)


def test_topics_are_emitted_in_vocabulary_order():
    """Ordering is fixed rather than incidental: dict iteration order is a
    leading cause of non-determinism (standards/decision_engine.md)."""
    assert tuple(t.topic for t in build(activity(topic="trees")).dsa.topics) == TOPICS


def test_topic_order_does_not_depend_on_input_order():
    a = build(activity(topic="trees"), activity(topic="arrays"))
    b = build(activity(topic="arrays"), activity(topic="trees"))
    assert a == b
    assert tuple(t.topic for t in a.dsa.topics) == TOPICS


def test_every_topic_carries_all_three_difficulties_in_order():
    for stat in build(activity()).dsa.topics:
        assert tuple(d.difficulty for d in stat.by_difficulty) == DIFFICULTIES


def test_an_untouched_topic_is_zeroed_not_omitted():
    snapshot = build(activity(topic="arrays"))
    stat = topic_of(snapshot, "dynamic-programming")
    assert (stat.solved, stat.attempted, stat.minutes_recorded) == (0, 0, 0)
    assert stat.activities_with_minutes == 0
    assert stat.last_practised_at is None


def test_a_topic_outside_the_vocabulary_is_refused():
    """Skipping it would make total_activities silently disagree with the sum
    of the per-topic counts."""
    with pytest.raises(UnknownTopic):
        build(activity(topic="monotonic-stack"))


@pytest.mark.parametrize("bad", ["Arrays", "", None, "graph"])
def test_near_miss_topics_are_refused(bad):
    with pytest.raises(UnknownTopic):
        build(activity(topic=bad))


@pytest.mark.parametrize("field,bad", [("difficulty", "trivial"), ("outcome", "skipped")])
def test_values_outside_the_other_vocabularies_are_refused(field, bad):
    with pytest.raises(ValueError):
        build(activity(**{field: bad}))


# ── Facts, not judgement (ADR-0067 section 2) ────────────────────────────────

def test_no_snapshot_field_holds_a_float():
    """Integers only: cross-platform float summation order must not be able to
    alter a snapshot, and a fraction is a model decision in disguise."""
    snapshot = build(activity(minutes_spent=7), activity(outcome="attempted"))
    for stat in snapshot.dsa.topics:
        for field in dataclasses.fields(stat):
            assert not isinstance(getattr(stat, field.name), float)
        for difficulty in stat.by_difficulty:
            assert isinstance(difficulty.solved, int)
            assert isinstance(difficulty.attempted, int)
    assert isinstance(snapshot.dsa.total_activities, int)


def test_the_model_declares_no_derived_or_scoring_field():
    """Interpretation belongs to the engine. A snapshot that scored its own
    topics would move the ranking decision outside the pure package."""
    names = set()
    for cls in (StudentSnapshot, DsaSnapshot, TopicStat, DifficultyStat):
        names |= {f.name for f in dataclasses.fields(cls)}
    for forbidden in (
        "score", "weakness", "rank", "ranking", "readiness", "weight", "confidence",
        "rate", "ratio", "percentage", "percent", "average", "mean", "normalised",
        "normalized", "recommendation", "priority",
    ):
        assert not any(forbidden in n for n in names), f"{forbidden!r} is judgement"


def test_the_snapshot_carries_no_preparation_goal_field():
    """ADR-0067 section 7: the goal is `constraints`, not `snapshot`. It is also
    the privacy boundary -- goals are High-class, DSA history is Medium."""
    names = {f.name for f in dataclasses.fields(StudentSnapshot)}
    names |= {f.name for f in dataclasses.fields(DsaSnapshot)}
    for forbidden in ("target_role", "target_company", "deadline", "weekly_hours",
                      "days_remaining", "goal"):
        assert forbidden not in names


def test_the_snapshot_carries_no_free_text_or_platform_field():
    """ADR-0067 section 4.3: problem titles and platform names are excluded.
    A snapshot is copied into every stored trace, so unused personal data there
    is a liability that compounds."""
    names = {f.name for f in dataclasses.fields(TopicStat)}
    for forbidden in ("problem_title", "problem_ref", "platform", "url", "notes"):
        assert forbidden not in names


def test_the_domain_module_imports_nothing_impure():
    """The snapshot must stay independent of PostgreSQL, HTTP and auth: the
    future engine consumes it, and ADR-0059's purity depends on it.

    Imports are read from the parse tree rather than the file text. The earlier
    text version failed on its own docstring -- prose naming `app.db.snapshot`
    is not an import, and a check that cannot tell the difference would train
    people to word comments around it.
    """
    imported: set[str] = set()
    for node in ast.walk(_domain_ast()):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    for name in imported:
        root = name.split(".")[0]
        assert root not in {"psycopg", "psycopg_pool", "fastapi", "starlette", "jwt",
                            "requests", "httpx", "urllib", "socket", "os"}, \
            f"the snapshot model imports {name}"
        assert not name.startswith(("app.db", "app.http", "app.auth")), \
            f"the snapshot model imports {name}"


# ── Agreement between the two construction paths ─────────────────────────────

def test_the_aggregate_path_reproduces_the_activity_path():
    """ADR-0067 section 11 requires both paths to agree. This is the pure half;
    `test_snapshot_aggregation.py` proves the SQL half against real rows."""
    rows = [
        {
            "topic": "graphs", "difficulty": "hard", "outcome": "solved",
            "activity_count": 2, "minutes_recorded": 90, "activities_with_minutes": 2,
            "first_occurred_at": NOON - timedelta(days=4),
            "last_occurred_at": NOON - timedelta(days=1),
        },
        {
            "topic": "graphs", "difficulty": "easy", "outcome": "attempted",
            "activity_count": 1, "minutes_recorded": 0, "activities_with_minutes": 0,
            "first_occurred_at": NOON - timedelta(days=2),
            "last_occurred_at": NOON - timedelta(days=2),
        },
    ]
    from_aggregates = snapshot_from_aggregates(subject=SUBJECT, as_of=NOON, rows=rows)
    from_activities = build(
        activity(topic="graphs", difficulty="hard", minutes_spent=45,
                 occurred_at=NOON - timedelta(days=4)),
        activity(topic="graphs", difficulty="hard", minutes_spent=45,
                 occurred_at=NOON - timedelta(days=1)),
        activity(topic="graphs", difficulty="easy", outcome="attempted",
                 occurred_at=NOON - timedelta(days=2)),
    )
    assert from_aggregates == from_activities


def test_the_aggregate_path_produces_a_valid_empty_snapshot():
    assert snapshot_from_aggregates(subject=SUBJECT, as_of=NOON, rows=[]) == build()


def test_the_aggregate_path_refuses_an_unknown_topic():
    with pytest.raises(UnknownTopic):
        snapshot_from_aggregates(subject=SUBJECT, as_of=NOON, rows=[{
            "topic": "quantum", "difficulty": "easy", "outcome": "solved",
            "activity_count": 1, "minutes_recorded": 0, "activities_with_minutes": 0,
            "first_occurred_at": NOON, "last_occurred_at": NOON,
        }])
