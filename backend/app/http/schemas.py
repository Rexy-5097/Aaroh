"""Request and response models for the preparation goal (ADR-0065).

Note what the request model does NOT contain: any owner identifier. The owner
comes from the verified identity, never from the request body (ADR-0061 I-4).
Accepting a `user_id` here would be the classic IDOR-by-design, and governance
check I-30 exists to keep it that way.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class PreparationGoalRequest(BaseModel):
    """What a student may send. Shape only -- the domain layer judges validity."""

    model_config = ConfigDict(extra="forbid")

    target_role: str = Field(..., description="Role being prepared for")
    target_company: str | None = Field(None, description="Optional target company")
    deadline: date = Field(..., description="Date the preparation is aimed at")
    # StrictInt, not int: Pydantic coerces JSON `true` to 1, so a client
    # sending `true` would silently record one hour. An invented number is
    # worse than a rejected request. Found while testing the DSA slice; the
    # same defect existed here.
    weekly_hours: StrictInt = Field(..., description="Hours per week available")


class PreparationGoalResponse(BaseModel):
    """What the caller gets back.

    `days_remaining` is derived on read rather than stored: a stored value would
    be wrong the following morning. It is presentation, not ranking -- the
    engine receives the raw deadline (ADR-0059).
    """

    target_role: str
    target_company: str | None
    deadline: date
    weekly_hours: int
    days_remaining: int


class DsaActivityRequest(BaseModel):
    """One practice event, as a student reports it.

    No owner field -- ownership comes from the verified identity (ADR-0065 I-30).
    Vocabularies are validated in the domain layer, not here: the schema checks
    shape, the domain checks membership.
    """

    model_config = ConfigDict(extra="forbid")

    problem_title: str = Field(..., description="The problem, as the student names it")
    topic: str = Field(..., description="One of Aaroh's controlled topics")
    difficulty: str = Field(..., description="easy | medium | hard")
    outcome: str = Field(..., description="solved | attempted")
    # StrictInt: JSON `true` must not become one minute (ADR-0066 section 6).
    minutes_spent: StrictInt | None = Field(None, description="Optional time on this problem")
    platform: str | None = Field(None, description="Optional metadata; no integration")


class DsaActivityResponse(BaseModel):
    """A recorded practice event.

    `problem_ref` is returned so a client can group re-solves of the same
    problem without re-deriving the normalisation and drifting from it.
    """

    id: UUID
    problem_title: str
    problem_ref: str
    topic: str
    difficulty: str
    outcome: str
    minutes_spent: int | None
    platform: str | None
    occurred_at: datetime
