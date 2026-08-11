"""The readiness snapshot (ADR-0067).

An immutable, point-in-time projection of one student's readiness-relevant
state. This module is the `snapshot` argument of the engine contract:

    rank(snapshot, constraints, catalog, weights) -> RankedResult

Pure. No database, no HTTP, no authentication, no clock. `as_of` is an input,
exactly as ADR-0059 requires of the engine and ADR-0065 already applied to the
goal domain -- and ADR-0067 section 5 extends the rule to the builder, because a
builder that reads a clock makes snapshots unreproducible before the engine is
even reached.

Facts, not judgement
--------------------
The load-bearing rule of ADR-0067 section 2: this module counts, sums and takes
extrema. It does not divide, weight, rank, normalise or score. A snapshot
carrying a `weakness_score` would mean the ranking decision had been made
*outside* the pure engine package -- unversioned, untraced, and unreachable by
ADR-0060's golden files.

Every numeric field is an integer. No float appears anywhere in a snapshot, so
cross-platform floating-point summation order cannot alter one.

Two construction paths
----------------------
`snapshot_from_activities` builds from individual records; `snapshot_from_aggregates`
builds from the SQL GROUP BY in `app.db.snapshot`. Both are pure and both must
produce the same snapshot over the same data -- `test_snapshot_agreement` proves
it. The first makes ranking testable with no database at all; the second is what
production uses, because it never loads a student's whole history into memory.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.domain.dsa import DIFFICULTIES, OUTCOMES, TOPICS

# ADR-0067 section 4 also specifies a `vocabulary_version` field on
# StudentSnapshot. It is NOT implemented here, deliberately.
#
# The repository defines no versioning mechanism for anything -- `engine_version`
# and `weights_version` exist as ADR-0060 prose and nowhere in code -- so
# choosing a representation now (semantic version, content hash, date stamp)
# would be inventing the scheme that ADR-0060's identifiers must eventually
# share. It has no consumer until the decision trace exists, so deferring it
# costs nothing and pre-committing could contradict a later decision.
#
# Adding it is additive: one field, one constant, no restructuring.


class UnknownTopic(ValueError):
    """A stored activity names a topic outside the current vocabulary.

    Raised rather than skipped. Dropping the row would make `total_activities`
    silently disagree with the sum of the per-topic counts, and a snapshot that
    quietly under-reports practice is worse than one that refuses to build.
    """


class NaiveTimestamp(ValueError):
    """A timestamp arrived without a timezone.

    Aaroh works in UTC throughout (`app/http/routes/preparation_goal.py`).
    Comparing a naive datetime to an aware one raises in Python, and handing a
    naive one to PostgreSQL silently reinterprets it in the session timezone --
    so the boundary refuses them rather than guessing which is meant.
    """


@dataclass(frozen=True)
class DifficultyStat:
    """Outcome counts for one difficulty within one topic."""

    difficulty: str
    solved: int
    attempted: int


@dataclass(frozen=True)
class TopicStat:
    """One topic's practice record.

    `solved` and `attempted` repeat what `by_difficulty` totals. ADR-0067
    specifies both so a consumer interested only in topic-level counts does not
    re-sum -- and so two consumers cannot re-sum differently.

    `minutes_recorded` and `activities_with_minutes` travel together because
    `minutes_spent` is optional (ADR-0066 section 6). Without the denominator a
    consumer would divide by `solved + attempted` and average over rows that
    never carried a value, which is precisely the fabricated precision
    `standards/decision_engine.md` forbids. No average is computed here: the
    ratio is a model question, so the snapshot supplies both numbers and the
    engine decides what to do with them.
    """

    topic: str
    solved: int
    attempted: int
    by_difficulty: tuple[DifficultyStat, ...]
    minutes_recorded: int
    activities_with_minutes: int
    last_practised_at: datetime | None


@dataclass(frozen=True)
class DsaSnapshot:
    """Everything the snapshot knows about a student's DSA practice.

    `topics` is dense: exactly one entry per vocabulary topic, in declaration
    order, including topics never practised (ADR-0067 section 4.1). "Absent" and
    "zero" are the same thing here, so the engine never handles a missing key
    and never needs the vocabulary itself.
    """

    total_activities: int
    first_activity_at: datetime | None
    last_activity_at: datetime | None
    topics: tuple[TopicStat, ...]


@dataclass(frozen=True)
class StudentSnapshot:
    """A student's readiness state at one instant.

    Carries no preparation-goal field. Target role, company, deadline and weekly
    hours are the engine's `constraints` argument, decided by ADR-0065 and
    recorded again by ADR-0067 section 7. The separation is also the privacy
    boundary: DSA history is Medium-class and the goal is High-class, so merging
    them would promote every stored trace to High.

    Frozen and built from tuples, so equality is structural and a determinism
    test is `==` rather than a field-by-field walk.
    """

    subject: UUID
    as_of: datetime
    dsa: DsaSnapshot


def _utc(value: datetime, *, field: str) -> datetime:
    """Require an aware timestamp and normalise it to UTC.

    Normalisation is not cosmetic. psycopg returns `timestamptz` in the database
    session's timezone, so the same row read by two processes with different
    `TimeZone` settings yields datetimes that are equal as instants but differ
    in representation. Snapshots are serialised into decision traces
    (ADR-0060), where that difference would survive -- and
    `standards/decision_engine.md` requires reproducibility to hold *across
    processes*, not merely within one.

    Naive values are refused rather than assumed to be UTC: guessing is how a
    timestamp silently shifts by the host's offset.
    """
    if not isinstance(value, datetime):
        raise NaiveTimestamp(f"{field} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise NaiveTimestamp(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


class _Bucket:
    """Mutable accumulator, private to this module.

    Nothing here escapes: `_freeze` copies every value into the frozen
    dataclasses above, so no mutable structure is reachable from a snapshot.
    """

    __slots__ = ("counts", "minutes_recorded", "activities_with_minutes", "last_at", "first_at")

    def __init__(self) -> None:
        # (difficulty, outcome) -> count. Dense-filled at freeze time.
        self.counts: dict[tuple[str, str], int] = {}
        self.minutes_recorded = 0
        self.activities_with_minutes = 0
        self.last_at: datetime | None = None
        self.first_at: datetime | None = None

    def add(
        self,
        *,
        difficulty: str,
        outcome: str,
        count: int,
        minutes_recorded: int,
        activities_with_minutes: int,
        first_at: datetime | None,
        last_at: datetime | None,
    ) -> None:
        key = (difficulty, outcome)
        self.counts[key] = self.counts.get(key, 0) + count
        self.minutes_recorded += minutes_recorded
        self.activities_with_minutes += activities_with_minutes
        if first_at is not None and (self.first_at is None or first_at < self.first_at):
            self.first_at = first_at
        if last_at is not None and (self.last_at is None or last_at > self.last_at):
            self.last_at = last_at


def _freeze_topic(topic: str, bucket: _Bucket) -> TopicStat:
    """Turn one accumulator into an immutable TopicStat.

    Difficulties are emitted in DIFFICULTIES order rather than dictionary order:
    `standards/decision_engine.md` names dict/set iteration order as a leading
    cause of non-determinism, and a snapshot whose field order varies is not
    reproducible even when its values are correct.
    """
    by_difficulty = tuple(
        DifficultyStat(
            difficulty=difficulty,
            solved=bucket.counts.get((difficulty, "solved"), 0),
            attempted=bucket.counts.get((difficulty, "attempted"), 0),
        )
        for difficulty in DIFFICULTIES
    )
    return TopicStat(
        topic=topic,
        solved=sum(d.solved for d in by_difficulty),
        attempted=sum(d.attempted for d in by_difficulty),
        by_difficulty=by_difficulty,
        minutes_recorded=bucket.minutes_recorded,
        activities_with_minutes=bucket.activities_with_minutes,
        last_practised_at=bucket.last_at,
    )


def _assemble(
    *, subject: UUID, as_of: datetime, buckets: dict[str, _Bucket]
) -> StudentSnapshot:
    topics = tuple(_freeze_topic(topic, buckets.get(topic, _Bucket())) for topic in TOPICS)

    total = sum(sum(b.counts.values()) for b in buckets.values())
    firsts = [b.first_at for b in buckets.values() if b.first_at is not None]
    lasts = [b.last_at for b in buckets.values() if b.last_at is not None]

    return StudentSnapshot(
        subject=subject,
        as_of=as_of,
        dsa=DsaSnapshot(
            total_activities=total,
            first_activity_at=min(firsts) if firsts else None,
            last_activity_at=max(lasts) if lasts else None,
            topics=topics,
        ),
    )


def _checked_topic(value: Any) -> str:
    if value not in TOPICS:
        raise UnknownTopic(f"activity names a topic outside the vocabulary: {value!r}")
    return str(value)


def _checked(value: Any, allowed: tuple[str, ...], *, field: str) -> str:
    if value not in allowed:
        raise ValueError(f"{field} is not one of {allowed}: {value!r}")
    return str(value)


def snapshot_from_activities(
    *, subject: UUID, as_of: datetime, activities: Iterable[Mapping[str, Any]]
) -> StudentSnapshot:
    """Build a snapshot from individual activity records. Pure.

    Each record needs `topic`, `difficulty`, `outcome`, `minutes_spent` and
    `occurred_at`. This is the path a unit test uses -- ADR-0059 requires the
    engine be testable "with no database, network, or fixtures beyond plain
    data", and that is only true if a snapshot can be built the same way.

    Production uses `snapshot_from_aggregates`. This path is correct but loads
    every record, so it is not what a student with thousands of activities
    should go through.
    """
    as_of = _utc(as_of, field="as_of")

    buckets: dict[str, _Bucket] = {}
    for activity in activities:
        occurred_at = _utc(activity["occurred_at"], field="occurred_at")
        # ADR-0067 section 5. Today this excludes nothing -- occurred_at is not
        # client-settable -- but without it, replaying a stored trace after new
        # activity arrived would produce a different snapshot than the one
        # recorded, which is exactly what ADR-0060's replay guarantee forbids.
        if occurred_at > as_of:
            continue

        topic = _checked_topic(activity["topic"])
        minutes = activity.get("minutes_spent")
        bucket = buckets.setdefault(topic, _Bucket())
        bucket.add(
            difficulty=_checked(activity["difficulty"], DIFFICULTIES, field="difficulty"),
            outcome=_checked(activity["outcome"], OUTCOMES, field="outcome"),
            count=1,
            # NULL is not zero: a record with no minutes contributes nothing to
            # either number, so "no time recorded" stays distinguishable from
            # "zero minutes spent".
            minutes_recorded=minutes if minutes is not None else 0,
            activities_with_minutes=1 if minutes is not None else 0,
            first_at=occurred_at,
            last_at=occurred_at,
        )

    return _assemble(subject=subject, as_of=as_of, buckets=buckets)


def snapshot_from_aggregates(
    *, subject: UUID, as_of: datetime, rows: Iterable[Mapping[str, Any]]
) -> StudentSnapshot:
    """Build a snapshot from pre-aggregated group rows. Pure.

    Consumes what `app.db.snapshot.aggregate_dsa` returns: one row per
    (topic, difficulty, outcome) actually present, already filtered by `as_of`
    in SQL. At most 96 rows exist regardless of how much a student has
    practised, which is what keeps the snapshot bounded (ADR-0067 section 6).

    Densification happens here rather than in SQL because it is judgement-free
    structure, and structure is cheaper to test without a database.
    """
    as_of = _utc(as_of, field="as_of")

    buckets: dict[str, _Bucket] = {}
    for row in rows:
        topic = _checked_topic(row["topic"])
        buckets.setdefault(topic, _Bucket()).add(
            difficulty=_checked(row["difficulty"], DIFFICULTIES, field="difficulty"),
            outcome=_checked(row["outcome"], OUTCOMES, field="outcome"),
            count=int(row["activity_count"]),
            minutes_recorded=int(row["minutes_recorded"]),
            activities_with_minutes=int(row["activities_with_minutes"]),
            first_at=_utc(row["first_occurred_at"], field="first_occurred_at"),
            last_at=_utc(row["last_occurred_at"], field="last_occurred_at"),
        )

    return _assemble(subject=subject, as_of=as_of, buckets=buckets)
