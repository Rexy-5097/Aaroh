"""Request and response models for the preparation goal (ADR-0065).

Note what the request model does NOT contain: any owner identifier. The owner
comes from the verified identity, never from the request body (ADR-0061 I-4).
Accepting a `user_id` here would be the classic IDOR-by-design, and governance
check I-30 exists to keep it that way.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PreparationGoalRequest(BaseModel):
    """What a student may send. Shape only -- the domain layer judges validity."""

    model_config = ConfigDict(extra="forbid")

    target_role: str = Field(..., description="Role being prepared for")
    target_company: str | None = Field(None, description="Optional target company")
    deadline: date = Field(..., description="Date the preparation is aimed at")
    weekly_hours: int = Field(..., description="Hours per week available")


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
