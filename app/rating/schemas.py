"""Pydantic v2 schemas for the rating module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LineItemRead(BaseModel):
    """One explainable step of the premium build-up (mirrors engine.LineItem)."""

    label: str
    kind: str  # base | factor | loading | discount | fee | tax
    value: str
    running_subtotal_minor: int
    stage: str = "loss_cost"  # loss_cost | technical | commercial | taxes


class QuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    submission_id: str
    premium_minor: int  # final quoted premium (incl. taxes/fees)
    currency: str
    rate_table_version: int
    breakdown: list[LineItemRead]
    # ADR-009 P1 staged subtotals (eurocents). Nullable for pre-P1 quotes.
    pure_premium_minor: int | None = None
    technical_premium_minor: int | None = None
    commercial_premium_minor: int | None = None
    taxes_minor: int | None = None
    created_by: str
    created_at: datetime


class RateTableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    effective_at: datetime
    rules: dict
