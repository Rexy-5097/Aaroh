"""Preparation goal domain rules (ADR-0065).

Pure unit tests — no database, no HTTP, no clock. `today` is an argument, so
every temporal rule is testable without freezing time or waiting for it.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.goals import (
    MAX_HORIZON_DAYS,
    MAX_TEXT_LENGTH,
    MAX_WEEKLY_HOURS,
    MIN_WEEKLY_HOURS,
    InvalidGoal,
    PreparationGoal,
    validate_goal,
)

TODAY = date(2026, 3, 1)


def build(**overrides):
    args = dict(
        target_role="Backend SWE",
        target_company=None,
        deadline=TODAY + timedelta(days=90),
        weekly_hours=12,
        today=TODAY,
    )
    args.update(overrides)
    return validate_goal(**args)


# ── Accepted ─────────────────────────────────────────────────────────────────

def test_a_complete_goal_is_accepted():
    goal = build(target_company="Acme")
    assert isinstance(goal, PreparationGoal)
    assert goal.target_role == "Backend SWE"
    assert goal.target_company == "Acme"
    assert goal.weekly_hours == 12


def test_target_company_is_optional():
    assert build(target_company=None).target_company is None
    assert build(target_company="   ").target_company is None, "blank is absent, not empty"


def test_text_is_trimmed():
    assert build(target_role="  Data Engineer  ").target_role == "Data Engineer"


def test_the_goal_is_immutable():
    goal = build()
    with pytest.raises(Exception):
        goal.target_role = "changed"  # type: ignore[misc]


# ── Deadline ─────────────────────────────────────────────────────────────────

def test_tomorrow_is_the_earliest_acceptable_deadline():
    assert build(deadline=TODAY + timedelta(days=1)).days_remaining(TODAY) == 1


@pytest.mark.parametrize("offset", [0, -1, -365])
def test_a_deadline_today_or_earlier_is_rejected(offset):
    """A past deadline cannot be prepared for, and would give the engine a zero
    or negative time budget to divide by."""
    with pytest.raises(InvalidGoal) as exc:
        build(deadline=TODAY + timedelta(days=offset))
    assert exc.value.field == "deadline"


def test_the_horizon_boundary_is_inclusive():
    assert build(deadline=TODAY + timedelta(days=MAX_HORIZON_DAYS)) is not None
    with pytest.raises(InvalidGoal) as exc:
        build(deadline=TODAY + timedelta(days=MAX_HORIZON_DAYS + 1))
    assert exc.value.field == "deadline"


def test_days_remaining_is_derived_not_stored():
    goal = build(deadline=TODAY + timedelta(days=10))
    assert goal.days_remaining(TODAY) == 10
    assert goal.days_remaining(TODAY + timedelta(days=4)) == 6, (
        "the same goal must yield a different answer on a different day"
    )


def test_a_non_date_deadline_is_rejected():
    with pytest.raises(InvalidGoal) as exc:
        build(deadline="2026-06-01")
    assert exc.value.field == "deadline"


# ── Weekly hours ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hours", [MIN_WEEKLY_HOURS, 40, MAX_WEEKLY_HOURS])
def test_weekly_hours_within_range_are_accepted(hours):
    assert build(weekly_hours=hours).weekly_hours == hours


@pytest.mark.parametrize("hours", [0, -5, MAX_WEEKLY_HOURS + 1, 168, 1000])
def test_weekly_hours_outside_range_are_rejected(hours):
    with pytest.raises(InvalidGoal) as exc:
        build(weekly_hours=hours)
    assert exc.value.field == "weekly_hours"


@pytest.mark.parametrize("hours", ["12", 12.5, None, True])
def test_non_integer_weekly_hours_are_rejected(hours):
    """`True` is included deliberately: bool is an int subclass in Python, and
    `weekly_hours=True` would otherwise be silently accepted as 1 hour."""
    with pytest.raises(InvalidGoal) as exc:
        build(weekly_hours=hours)
    assert exc.value.field == "weekly_hours"


# ── Text fields ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("role", ["", "   ", None])
def test_target_role_is_required(role):
    with pytest.raises(InvalidGoal) as exc:
        build(target_role=role)
    assert exc.value.field == "target_role"


def test_text_length_boundary():
    assert build(target_role="x" * MAX_TEXT_LENGTH) is not None
    with pytest.raises(InvalidGoal) as exc:
        build(target_role="x" * (MAX_TEXT_LENGTH + 1))
    assert exc.value.field == "target_role"

    with pytest.raises(InvalidGoal) as exc:
        build(target_company="y" * (MAX_TEXT_LENGTH + 1))
    assert exc.value.field == "target_company"


def test_validation_reports_the_offending_field():
    """Input validation names the field. Unlike an authentication failure this
    discloses nothing about any other user, so being specific is a kindness
    rather than an oracle."""
    with pytest.raises(InvalidGoal) as exc:
        build(weekly_hours=0)
    assert exc.value.field == "weekly_hours"
    assert "weekly_hours" in exc.value.message
