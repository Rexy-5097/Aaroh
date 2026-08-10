"""Preparation goal — the engine's `constraints` input (ADR-0065).

This is where a goal is judged valid, and it is deliberately not the API layer
and not the database. The database enforces *shape* (lengths, ranges) and cannot
enforce *temporal* validity, because a CHECK against `now()` is not IMMUTABLE
and a row valid when written must not become invalid merely because time passed.

Pure: `today` is an input, never read from the clock. That mirrors ADR-0059's
rule for the engine and means every temporal rule here is testable without
freezing time or waiting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

MAX_TEXT_LENGTH = 120

# The database allows 1..168 (the physical ceiling of a week). The domain
# applies a tighter, judgement-based bound: a student claiming more than 80
# hours a week of preparation is describing an intention, not a plan, and the
# engine would rank against time that does not exist.
MIN_WEEKLY_HOURS = 1
MAX_WEEKLY_HOURS = 80

# A deadline further out than this is not a preparation horizon, it is a career
# aspiration; ranking "the next 90 minutes" against it produces noise.
MAX_HORIZON_DAYS = 730


class InvalidGoal(ValueError):
    """A goal that cannot be used as a ranking constraint.

    `field` lets the API report which input was rejected. This is ordinary input
    validation, not authentication, so being specific is helpful rather than an
    oracle — it discloses nothing about any other user.
    """

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class PreparationGoal:
    """A validated goal. Constructing one is the proof it is usable."""

    target_role: str
    target_company: str | None
    deadline: date
    weekly_hours: int

    def days_remaining(self, today: date) -> int:
        """Days from `today` to the deadline.

        Derived, never stored: storing it would be wrong the next morning.
        """
        return (self.deadline - today).days


def _clean_text(value: str | None, *, field: str, required: bool) -> str | None:
    if value is None or not str(value).strip():
        if required:
            raise InvalidGoal(field, f"{field} is required")
        return None
    cleaned = str(value).strip()
    if len(cleaned) > MAX_TEXT_LENGTH:
        raise InvalidGoal(field, f"{field} must be at most {MAX_TEXT_LENGTH} characters")
    return cleaned


def validate_goal(
    *,
    target_role: str | None,
    target_company: str | None,
    deadline: date,
    weekly_hours: int,
    today: date,
) -> PreparationGoal:
    """Validate a goal, or refuse it with the offending field named."""
    role = _clean_text(target_role, field="target_role", required=True)
    company = _clean_text(target_company, field="target_company", required=False)

    if not isinstance(deadline, date):
        raise InvalidGoal("deadline", "deadline must be a date")
    if deadline <= today:
        # A deadline in the past or today cannot be prepared for. Accepting one
        # would let the engine divide by a zero or negative time budget.
        raise InvalidGoal("deadline", "deadline must be in the future")
    if (deadline - today).days > MAX_HORIZON_DAYS:
        raise InvalidGoal(
            "deadline", f"deadline must be within {MAX_HORIZON_DAYS} days"
        )

    if isinstance(weekly_hours, bool) or not isinstance(weekly_hours, int):
        raise InvalidGoal("weekly_hours", "weekly_hours must be a whole number")
    if not MIN_WEEKLY_HOURS <= weekly_hours <= MAX_WEEKLY_HOURS:
        raise InvalidGoal(
            "weekly_hours",
            f"weekly_hours must be between {MIN_WEEKLY_HOURS} and {MAX_WEEKLY_HOURS}",
        )

    return PreparationGoal(
        target_role=role,
        target_company=company,
        deadline=deadline,
        weekly_hours=weekly_hours,
    )
