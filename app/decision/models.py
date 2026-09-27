"""Decision model — the persisted outcome of an appetite assessment.

Records which appetite ruleset version produced it (ADR-004 explainability). reason_codes are stored
as JSON list of stable code strings.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.appetite.models import JsonType
from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Decision(Base):
    __tablename__ = "decision"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    submission_id: Mapped[str] = mapped_column(String(36), ForeignKey("submission.id"), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_codes: Mapped[list] = mapped_column(JsonType, nullable=False)
    appetite_version: Mapped[int] = mapped_column(Integer, nullable=False)
    decided_by: Mapped[str] = mapped_column(String(128), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
