"""Preparation goal persistence (ADR-0065).

Inside the sanctioned db/ layer, but it creates no connection: every function
takes a connection already bound to the caller's identity by
`request_transaction`. That keeps ADR-0061 I-12 intact and means these queries
cannot be run without an identity having been established first.

No query filters by user_id. That is deliberate: RLS is the filter. A WHERE
clause here would be a second, weaker authorization path that could drift from
the policy — and if it were ever forgotten, RLS still holds.
"""

from __future__ import annotations

from typing import Any

from app.domain.goals import PreparationGoal

_COLUMNS = "target_role, target_company, deadline, weekly_hours, created_at, updated_at"


def upsert_goal(conn: Any, goal: PreparationGoal) -> dict[str, Any]:
    """Insert or replace the caller's goal.

    `user_id` is never supplied: the column defaults to `auth.uid()`, so the
    owner comes from the database session identity rather than from anything the
    request could influence (ADR-0061 I-4).
    """
    row = conn.execute(
        f"""
        INSERT INTO public.preparation_goals
            (target_role, target_company, deadline, weekly_hours)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            target_role    = EXCLUDED.target_role,
            target_company = EXCLUDED.target_company,
            deadline       = EXCLUDED.deadline,
            weekly_hours   = EXCLUDED.weekly_hours,
            updated_at     = now()
        RETURNING {_COLUMNS}
        """,
        (goal.target_role, goal.target_company, goal.deadline, goal.weekly_hours),
    ).fetchone()
    return _as_dict(row)


def fetch_goal(conn: Any) -> dict[str, Any] | None:
    """Return the caller's goal, or None. RLS decides which row that is."""
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM public.preparation_goals"
    ).fetchone()
    return _as_dict(row) if row else None


def _as_dict(row: Any) -> dict[str, Any]:
    keys = [c.strip() for c in _COLUMNS.split(",")]
    return dict(zip(keys, row))
