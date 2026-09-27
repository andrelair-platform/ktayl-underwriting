"""Pydantic v2 schemas for the entity (Counterparty) module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CounterpartyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    country: str = Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code")


class CounterpartyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    country: str
    created_at: datetime
