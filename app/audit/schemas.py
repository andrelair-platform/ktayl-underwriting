"""Pydantic v2 schema for the audit module."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    submission_id: str
    action: str
    actor: str
    at: datetime
    ruleset_version: int | None
    outcome: str | None
    detail: dict[str, Any]
