"""DSA activity endpoints (ADR-0066).

Aaroh's first source of `snapshot` data: a student records what they practised.

The chain is the one proven in slices 1-3, unchanged:

    request -> require_identity -> VerifiedIdentity -> request_transaction
            -> SET LOCAL -> RLS -> caller-owned rows

Append-only. There is no update or delete endpoint, and no policy permitting
either: a past practice event is a fact (ADR-0066 section 9).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.identity import VerifiedIdentity
from app.db.dsa import DEFAULT_LIMIT, list_activities, record_activity
from app.db.session import request_transaction
from app.domain.dsa import InvalidActivity, validate_activity

from ..dependencies import require_identity
from ..schemas import DsaActivityRequest, DsaActivityResponse

router = APIRouter(prefix="/v1", tags=["dsa-activity"])


@router.post(
    "/dsa-activity",
    response_model=DsaActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dsa_activity(
    request: Request,
    payload: DsaActivityRequest,
    identity: VerifiedIdentity = Depends(require_identity),
) -> DsaActivityResponse:
    """Record one practice event.

    POST, not PUT: each call appends a new event. Recording the same problem
    again is a re-solve, which is signal rather than a duplicate to be merged.
    """
    try:
        activity = validate_activity(
            problem_title=payload.problem_title,
            topic=payload.topic,
            difficulty=payload.difficulty,
            outcome=payload.outcome,
            minutes_spent=payload.minutes_spent,
            platform=payload.platform,
        )
    except InvalidActivity as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"field": exc.field, "message": exc.message},
        ) from None

    with request_transaction(request.app.state.pool, identity) as conn:
        row = record_activity(conn, activity)
    return DsaActivityResponse(**row)


@router.get("/dsa-activity", response_model=list[DsaActivityResponse])
def list_dsa_activity(
    request: Request,
    identity: VerifiedIdentity = Depends(require_identity),
) -> list[DsaActivityResponse]:
    """List the caller's practice events, most recent first.

    Bounded by a fixed limit so a list request cannot become an unbounded scan.
    An empty list is a valid answer -- unlike the preparation goal, absence here
    means "nothing recorded yet", not "not found".
    """
    with request_transaction(request.app.state.pool, identity) as conn:
        rows = list_activities(conn, limit=DEFAULT_LIMIT)
    return [DsaActivityResponse(**row) for row in rows]
