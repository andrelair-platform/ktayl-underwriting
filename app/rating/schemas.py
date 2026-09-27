"""Pydantic v2 schemas for the rating module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LineItemRead(BaseModel):
    """One explainable step of the premium build-up (mirrors engine.LineItem)."""

    label: str
    kind: str  # base | factor | loading | discount
    value: str
    running_subtotal_minor: int


class QuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    submission_id: str
    premium_minor: int
    currency: str
    rate_table_version: int
    breakdown: list[LineItemRead]
    created_by: str
    created_at: datetime


class RateTableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    effective_at: datetime
    rules: dict
