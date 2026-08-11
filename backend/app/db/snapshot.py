"""Snapshot aggregation (ADR-0067).

Inside the sanctioned db/ layer and, like the rest of it, creates no connection:
every function takes one already bound to the caller's identity by
`request_transaction`.

No query filters by user_id. RLS is the filter, exactly as in `db/dsa.py` and
`db/goals.py` -- a WHERE clause here would be a second, weaker authorization
path that could drift from the policy. `test_a_snapshot_never_sees_another_student`
proves the boundary holds in both directions.

Why this is not `list_activities`
---------------------------------
`db/dsa.py` bounds its listing at 100 rows so an API response cannot become an
unbounded scan. A snapshot built from that path would silently truncate for any
student with a real practice history and report confidently wrong counts --
ADR-0067 section 6 forbids it explicitly. So this module has its own query.

Why one query and not two
-------------------------
`total_activities` and the first/last timestamps are derived from the same
grouped rows rather than fetched by a second statement. Under READ COMMITTED two
statements can see different data if a concurrent insert commits between them,
which would let a snapshot report a total that disagrees with the sum of its own
topics. Deriving both from one result set makes that impossible rather than
unlikely.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.snapshot import StudentSnapshot, snapshot_from_aggregates

_AGGREGATE_COLUMNS = (
    "topic, difficulty, outcome, activity_count, minutes_recorded, "
    "activities_with_minutes, first_occurred_at, last_occurred_at"
)

# One row per (topic, difficulty, outcome) that actually occurs. The vocabulary
# bounds this at 16 x 3 x 2 = 96 rows for any student, whether they have ten
# activities or ten million -- so snapshot cost is flat in history size and
# PostgreSQL does the counting rather than Python.
#
# count(minutes_spent) counts NON-NULL values only. That is the whole reason
# `activities_with_minutes` is honest: NULL is never coerced to zero, so a
# record with no time recorded is distinguishable from one recording zero.
# coalesce applies to the SUM, which is NULL only when every row in the group
# lacks minutes -- and the correct total in that case is 0.
_AGGREGATE_SQL = """
    SELECT topic,
           difficulty,
           outcome,
           count(*)                        AS activity_count,
           coalesce(sum(minutes_spent), 0) AS minutes_recorded,
           count(minutes_spent)            AS activities_with_minutes,
           min(occurred_at)                AS first_occurred_at,
           max(occurred_at)                AS last_occurred_at
      FROM public.dsa_activities
     WHERE occurred_at <= %s
     GROUP BY topic, difficulty, outcome
"""


def aggregate_dsa(conn: Any, *, as_of: datetime) -> list[dict[str, Any]]:
    """Return the caller's DSA practice, grouped. RLS decides whose.

    The `occurred_at <= as_of` bound is applied in SQL (ADR-0067 section 5).
    Today it can exclude nothing, because `occurred_at` is not client-settable
    and defaults to now() at insert. It is applied anyway so that replaying a
    stored decision trace after further practice reproduces the original
    snapshot rather than a newer one.
    """
    keys = [c.strip() for c in _AGGREGATE_COLUMNS.split(",")]
    rows = conn.execute(_AGGREGATE_SQL, (as_of,)).fetchall()
    return [dict(zip(keys, row)) for row in rows]


def load_snapshot(conn: Any, *, subject: UUID, as_of: datetime) -> StudentSnapshot:
    """Build the caller's readiness snapshot.

    The only function that spans both layers, and it does so in one direction:
    db/ imports domain/, never the reverse. `StudentSnapshot` itself holds no
    connection and knows nothing about PostgreSQL, so the future engine consumes
    plain data (ADR-0059).

    `subject` comes from the caller's `VerifiedIdentity`, not from a query. It
    labels the snapshot; it does not scope it -- scoping is RLS's job, and
    passing an identifier in to filter on would be the second authorization path
    ADR-0061 I-4 exists to prevent.
    """
    return snapshot_from_aggregates(
        subject=subject, as_of=as_of, rows=aggregate_dsa(conn, as_of=as_of)
    )
