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
from app.bind.policy_client import HttpPolicyServiceClient, PolicyServiceClient
from app.bind.publisher import BoundRiskPublisher, NatsBoundRiskPublisher
from app.bind.repository import BindingRepository, SqlBindingRepository
from app.bind.token import ClientCredentialsTokenProvider, TokenProvider
from app.config import get_settings
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


def get_binding_repository(db: DbSession) -> BindingRepository:
    return SqlBindingRepository(db)


def get_token_provider() -> TokenProvider:
    """The real Authentik client-credentials token provider (overridden in tests)."""
    settings = get_settings()
    return ClientCredentialsTokenProvider(
        token_url=settings.oidc_token_url,
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        scope=settings.oidc_scope,
    )


TokenProviderDep = Annotated[TokenProvider, Depends(get_token_provider)]


def get_policy_service_client(token_provider: TokenProviderDep) -> PolicyServiceClient:
    """The real httpx PAS client bound to POLICY_SERVICE_URL (overridden in tests)."""
    return HttpPolicyServiceClient(base_url=get_settings().policy_service_url, token_provider=token_provider)


def get_bound_risk_publisher() -> BoundRiskPublisher:
    """The real NATS bound-risk publisher (overridden in tests)."""
    return NatsBoundRiskPublisher(nats_url=get_settings().nats_url)


CounterpartyRepo = Annotated[CounterpartyRepository, Depends(get_counterparty_repository)]
AppetiteRepo = Annotated[AppetiteRepository, Depends(get_appetite_repository)]
AuditRepo = Annotated[AuditRepository, Depends(get_audit_repository)]
RateTableRepo = Annotated[RateTableRepository, Depends(get_rate_table_repository)]
QuoteRepo = Annotated[QuoteRepository, Depends(get_quote_repository)]
BindingRepo = Annotated[BindingRepository, Depends(get_binding_repository)]
PolicyServiceClientDep = Annotated[PolicyServiceClient, Depends(get_policy_service_client)]
BoundRiskPublisherDep = Annotated[BoundRiskPublisher, Depends(get_bound_risk_publisher)]
