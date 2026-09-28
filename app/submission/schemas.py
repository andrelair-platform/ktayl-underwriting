"""Pydantic v2 schemas for the submission module.

The create schema embeds the counterparty inline (local entity model, ADR-002) — a later MDM
refactor would swap this for a counterparty ref lookup.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.decision.schemas import DecisionRead
from app.entity.schemas import CounterpartyCreate
from app.enums import LineOfBusiness, Occupancy, Outcome


class SubmissionCreate(BaseModel):
    counterparty: CounterpartyCreate
    line_of_business: LineOfBusiness
    tiv_eur: int = Field(gt=0, description="Total insured value in eurocents (minor units)")
    occupancy: Occupancy
    country: str = Field(min_length=2, max_length=2, description="Risk location ISO 3166-1 alpha-2")
    postcode: str = Field(min_length=1, max_length=16)
    requested_cover: str = Field(min_length=1, max_length=255)
    broker_ref: str | None = Field(default=None, max_length=64)


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    counterparty_id: str
    line_of_business: LineOfBusiness
    tiv_eur: int
    occupancy: Occupancy
    country: str
    postcode: str
    requested_cover: str
    broker_ref: str | None
    created_at: datetime


class SubmissionDetail(SubmissionRead):
    """Submission plus its latest decision (None until assessed)."""

    latest_decision: DecisionRead | None = None


class SubmissionListItem(SubmissionRead):
    """A submission as it appears in the workbench inbox: its fields + the latest appetite outcome
    (None until assessed) + whether it has been bound. The inbox filters/triages on these two."""

    latest_outcome: Outcome | None = None
    bound: bool = False
