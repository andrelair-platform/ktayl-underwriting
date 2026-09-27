"""Pydantic v2 schemas for the decision module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.enums import Outcome, ReasonCode


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    submission_id: str
    outcome: Outcome
    reason_codes: list[ReasonCode]
    appetite_version: int
    decided_by: str
    decided_at: datetime
