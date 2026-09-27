"""FastAPI dependency providers for the DB session and the repositories.

Repos are injected via Depends so tests can override them (or, more simply, override get_db to a
SQLite in-memory session and let the real repos run against it).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.appetite.repository import AppetiteRepository, SqlAppetiteRepository
from app.audit.repository import AuditRepository, SqlAuditRepository
from app.db.base import get_db
from app.entity.repository import CounterpartyRepository, SqlCounterpartyRepository
from app.rating.repository import (
    QuoteRepository,
    RateTableRepository,
    SqlQuoteRepository,
    SqlRateTableRepository,
)

DbSession = Annotated[Session, Depends(get_db)]


def get_counterparty_repository(db: DbSession) -> CounterpartyRepository:
    return SqlCounterpartyRepository(db)


def get_appetite_repository(db: DbSession) -> AppetiteRepository:
    return SqlAppetiteRepository(db)


def get_audit_repository(db: DbSession) -> AuditRepository:
    return SqlAuditRepository(db)


def get_rate_table_repository(db: DbSession) -> RateTableRepository:
    return SqlRateTableRepository(db)


def get_quote_repository(db: DbSession) -> QuoteRepository:
    return SqlQuoteRepository(db)


CounterpartyRepo = Annotated[CounterpartyRepository, Depends(get_counterparty_repository)]
AppetiteRepo = Annotated[AppetiteRepository, Depends(get_appetite_repository)]
AuditRepo = Annotated[AuditRepository, Depends(get_audit_repository)]
RateTableRepo = Annotated[RateTableRepository, Depends(get_rate_table_repository)]
QuoteRepo = Annotated[QuoteRepository, Depends(get_quote_repository)]
