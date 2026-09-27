"""Submission model — a risk submission for the v1 starter LOB (commercial_property).

Money (tiv_eur) is stored as BigInteger eurocents (minor units) per the platform convention.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Submission(Base):
    __tablename__ = "submission"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    counterparty_id: Mapped[str] = mapped_column(String(36), ForeignKey("counterparty.id"), nullable=False)
    line_of_business: Mapped[str] = mapped_column(String(64), nullable=False)
    tiv_eur: Mapped[int] = mapped_column(BigInteger, nullable=False)  # eurocents (minor units)
    occupancy: Mapped[str] = mapped_column(String(64), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    postcode: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_cover: Mapped[str] = mapped_column(String(255), nullable=False)
    broker_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
