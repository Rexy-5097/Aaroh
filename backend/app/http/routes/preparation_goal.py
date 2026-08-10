"""Preparation goal endpoints (ADR-0065).

The first product capability: a student states what they are preparing for, by
when, and how much time they have. Every future recommendation depends on this
existing, because the engine cannot rank against an unknown time budget.

The chain is the one proven in slices 1-3, unchanged:

    request -> require_identity -> VerifiedIdentity -> request_transaction
            -> SET LOCAL -> RLS -> caller-owned row
"""

from __future__ import annotations

from datetime import date, timezone
from datetime import datetime as _datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.identity import VerifiedIdentity
from app.db.goals import fetch_goal, upsert_goal
from app.db.session import request_transaction
from app.domain.goals import InvalidGoal, validate_goal

from ..dependencies import require_identity
from ..schemas import PreparationGoalRequest, PreparationGoalResponse

router = APIRouter(prefix="/v1", tags=["preparation-goal"])


def _today() -> date:
    """UTC today.

    The single place a wall clock is read for this slice. The domain layer takes
    `today` as an argument so its rules stay pure and testable.
    """
    return _datetime.now(timezone.utc).date()


def _to_response(row: dict, today: date) -> PreparationGoalResponse:
    return PreparationGoalResponse(
        target_role=row["target_role"],
        target_company=row["target_company"],
        deadline=row["deadline"],
        weekly_hours=row["weekly_hours"],
        days_remaining=(row["deadline"] - today).days,
    )


@router.put("/preparation-goal", response_model=PreparationGoalResponse)
def set_preparation_goal(
    request: Request,
    payload: PreparationGoalRequest,
    identity: VerifiedIdentity = Depends(require_identity),
) -> PreparationGoalResponse:
    """Create or replace the caller's preparation goal.

    PUT rather than POST: a student has exactly one active goal, so the
    operation is idempotent replacement rather than collection append.
    """
    today = _today()
    try:
        goal = validate_goal(
            target_role=payload.target_role,
            target_company=payload.target_company,
            deadline=payload.deadline,
            weekly_hours=payload.weekly_hours,
            today=today,
        )
    except InvalidGoal as exc:
        # Ordinary input validation. Naming the field is helpful and discloses
        # nothing about any other user -- unlike an authentication failure,
        # which is deliberately uniform (ADR-0064 I-24).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"field": exc.field, "message": exc.message},
        ) from None

    with request_transaction(request.app.state.pool, identity) as conn:
        row = upsert_goal(conn, goal)
    return _to_response(row, today)


@router.get("/preparation-goal", response_model=PreparationGoalResponse)
def get_preparation_goal(
    request: Request,
    identity: VerifiedIdentity = Depends(require_identity),
) -> PreparationGoalResponse:
    """Return the caller's preparation goal.

    404 when absent. Under RLS another student's goal is simply not visible, so
    "not set" and "belongs to someone else" are indistinguishable here -- which
    is the anti-enumeration behaviour ADR-0061 section 6 requires, obtained
    without any special-case code.
    """
    today = _today()
    with request_transaction(request.app.state.pool, identity) as conn:
        row = fetch_goal(conn)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "No preparation goal has been set."},
        )
    return _to_response(row, today)
