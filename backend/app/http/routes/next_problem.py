"""The recommendation endpoint (ADR-0071, ADR-0072).

Aaroh's first capability that *decides* something. The chain, all of it already
proven in earlier slices:

    request -> require_identity -> VerifiedIdentity -> request_transaction
            -> SET LOCAL -> RLS -> the caller's own rows
            -> StudentSnapshot -> rank() -> top candidate

Read-only. Nothing is written, nothing is persisted, and no trace is stored --
`ADR-0072` D3 and D7 leave trace storage and its retention to a later slice, and
storing a recommendation before its retention rule exists would breach
`standards/privacy.md`.

Where the work happens
----------------------
The database is touched only inside `request_transaction`, so RLS scopes every
read to the caller. `rank()` is pure and receives plain data: this module is the
only place the two meet, and it passes no identifier to filter on -- RLS already
decided what is visible (`ADR-0061` I-4).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.identity import VerifiedIdentity
from app.db.goals import fetch_goal
from app.db.session import request_transaction
from app.db.snapshot import load_snapshot
from app.decision_engine import rank
from app.domain.catalogue_v1 import V1_CATALOGUE
from app.domain.goals import PreparationGoal

from ..dependencies import require_identity
from ..schemas import NextProblemResponse

router = APIRouter(prefix="/v1", tags=["recommendation"])


def _now() -> datetime:
    """UTC now.

    The single place a wall clock is read for this endpoint. It is passed into
    the snapshot builder as `as_of`, which is what keeps the engine and the
    builder pure (`ADR-0067` section 5): neither reads a clock itself.
    """
    return datetime.now(timezone.utc)


@router.get("/next-problem", response_model=NextProblemResponse)
def next_problem(
    request: Request,
    identity: VerifiedIdentity = Depends(require_identity),
) -> NextProblemResponse:
    """Recommend the single problem this student should do next.

    404 when Aaroh has nothing to recommend, which happens for two reasons and
    the detail says which:

    * **No preparation goal.** `ADR-0065`'s product rule -- *"No recommendation
      may exist without a deadline and a time budget"* -- is a precondition, and
      `rank()` refuses without one. This reuses the 404 that `GET
      /v1/preparation-goal` already returns when a goal is absent, rather than
      inventing a status code.
    * **No candidates.** Defensive only: `V1_CATALOGUE` is a non-empty constant,
      so this is unreachable in V1. It exists so an empty catalogue produces an
      honest refusal rather than an index error.

    The response deliberately carries **no score and no confidence**: `ADR-0071`
    section 3.1 made weakness ordinal with no magnitude, so there is no number to
    report, and confidence has no definition anywhere. It also carries no
    `user_id` and no goal field -- the caller already knows who they are, and
    target role and company are High-class (`standards/privacy.md`).
    """
    as_of = _now()

    with request_transaction(request.app.state.pool, identity) as conn:
        goal_row = fetch_goal(conn)
        snapshot = load_snapshot(conn, subject=identity.subject, as_of=as_of)

    if goal_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "No recommendation is available until a preparation "
                           "goal has been set."
            },
        )

    # Rebuild the domain object from the stored row WITHOUT re-running temporal
    # validation. `ADR-0065` is explicit that "a row valid when written must not
    # become invalid merely because time passed. Temporal validity is an input
    # rule, not a storage rule" -- so re-validating here would contradict it and
    # would make a student with a passed deadline unable to get any advice at
    # all. The values were validated on write and are constrained by database
    # CHECKs; what `rank()` needs is the domain type, not a re-decision.
    #
    # Whether an expired deadline *should* change the advice is a product
    # question nobody has answered; refusing to answer would be a worse default.
    goal = PreparationGoal(
        target_role=goal_row["target_role"],
        target_company=goal_row["target_company"],
        deadline=goal_row["deadline"],
        weekly_hours=goal_row["weekly_hours"],
    )

    result = rank(snapshot, goal, V1_CATALOGUE)
    if not result.candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "No candidate problems are available."},
        )

    top = result.candidates[0]
    item = next(i for i in V1_CATALOGUE if i.slug == top.slug)

    return NextProblemResponse(
        slug=item.slug,
        title=item.title,
        topics=list(item.topics),
        difficulty=item.difficulty,
        reason=top.reason,
        reason_topic=top.reason_topic,
    )
