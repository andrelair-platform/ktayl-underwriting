"""Pydantic v2 schema for the bind module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    submission_id: str
    quote_id: str
    policy_number: str
    pas_policy_id: str
    status: str
    event_published: bool
    bound_at: datetime
    bound_by: str
