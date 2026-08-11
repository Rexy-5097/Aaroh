"""DSA activity persistence (ADR-0066).

Inside the sanctioned db/ layer but creates no connection: every function takes
a connection already bound to the caller's identity by `request_transaction`.

No query filters by user_id. RLS is the filter. A WHERE clause here would be a
second, weaker authorization path that could drift from the policy.
"""

from __future__ import annotations

from typing import Any

from app.domain.dsa import DsaActivity

# Bounded so a list request cannot become an unbounded scan.
DEFAULT_LIMIT = 100

_COLUMNS = (
    "id, problem_title, problem_ref, topic, difficulty, outcome, "
    "minutes_spent, platform, occurred_at"
)


def record_activity(conn: Any, activity: DsaActivity) -> dict[str, Any]:
    """Append one practice event.

    `user_id` is never supplied: the column defaults to auth.uid(), so the owner
    comes from the database session identity rather than anything the request
    could influence (ADR-0061 I-4).

    There is no ON CONFLICT clause. Recording the same problem again is a new
    event, not a replacement (ADR-0066 section 1).
    """
    row = conn.execute(
        f"""
        INSERT INTO public.dsa_activities
            (problem_title, problem_ref, topic, difficulty, outcome,
             minutes_spent, platform)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING {_COLUMNS}
        """,
        (
            activity.problem_title,
            activity.problem_ref,
            activity.topic,
            activity.difficulty,
            activity.outcome,
            activity.minutes_spent,
            activity.platform,
        ),
    ).fetchone()
    return _as_dict(row)


def list_activities(conn: Any, *, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Return the caller's activities, most recent first. RLS decides which."""
    rows = conn.execute(
        f"""
        SELECT {_COLUMNS} FROM public.dsa_activities
        ORDER BY occurred_at DESC, id DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [_as_dict(r) for r in rows]


def _as_dict(row: Any) -> dict[str, Any]:
    keys = [c.strip() for c in _COLUMNS.split(",")]
    return dict(zip(keys, row))
