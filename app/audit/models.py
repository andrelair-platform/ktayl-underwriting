"""AuditEntry — an append-only audit record (ADR-004: the decision trail is append-only).

Rows are only ever inserted and read, never updated or deleted. There is deliberately no update/
delete path in the repository.
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


class AuditEntry(Base):
    __tablename__ = "audit_entry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    submission_id: Mapped[str] = mapped_column(String(36), ForeignKey("submission.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    ruleset_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    detail: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
