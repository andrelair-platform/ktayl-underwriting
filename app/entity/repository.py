"""Counterparty repository — a typing.Protocol interface (ADR-001/002) + a SQLAlchemy impl.

The interface is what callers depend on, so an MDM-backed implementation can replace the local one
later with no change upstream.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.entity.models import Counterparty


class CounterpartyRepository(Protocol):
    """Read/write access to counterparties, decoupled from storage."""

    def add(self, name: str, country: str) -> Counterparty: ...

    def get(self, counterparty_id: str) -> Counterparty | None: ...


class SqlCounterpartyRepository:
    """SQLAlchemy-backed local implementation (ADR-002)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, name: str, country: str) -> Counterparty:
        cp = Counterparty(name=name, country=country.upper())
        self._session.add(cp)
        self._session.flush()
        return cp

    def get(self, counterparty_id: str) -> Counterparty | None:
        return self._session.scalar(select(Counterparty).where(Counterparty.id == counterparty_id))
