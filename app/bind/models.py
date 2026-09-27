"""Binding model — the UW-side record that an accepted + quoted risk was bound into the live PAS.

Bind is the cross-service handoff to `ktayl-policy-service` (ADR-006). The PAS `CreatePolicyRequest`
is thin (holder/product/dates only), so premium/limits/terms stay in the UW record, **linked by**
``policy_number``. ``policy_number`` is a deterministic function of the quote id (a stable hash), so a
retry keys onto the same row and the same PAS policy → idempotency. One binding per submission.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Binding(Base):
    """A risk bound into the live policy service. One per submission (idempotent re-bind).

    ``policy_number`` is unique + deterministic from the quote id; ``pas_policy_id`` is the id the
    policy service assigned. ``event_published`` records whether the bound-risk NATS event went out
    (best-effort — a publish failure must not fail an already-activated bind).
    """

    __tablename__ = "binding"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    submission_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("submission.id"), nullable=False, unique=True, index=True
    )
    quote_id: Mapped[str] = mapped_column(String(36), ForeignKey("quote.id"), nullable=False, index=True)
    policy_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    pas_policy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="bound")
    event_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    bound_by: Mapped[str] = mapped_column(String(128), nullable=False)
