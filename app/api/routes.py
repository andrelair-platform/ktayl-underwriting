"""FastAPI routers: the /v1 workbench-core endpoints + ops endpoints (/healthz, /info)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import (
    AppetiteRepo,
    AuditRepo,
    BindingRepo,
    BoundRiskPublisherDep,
    CounterpartyRepo,
    DbSession,
    PolicyServiceClientDep,
    QuoteRepo,
    RateTableRepo,
)
from app.audit.schemas import AuditEntryRead
from app.bind import service as bind_service
from app.bind.schemas import BindingRead
from app.config import get_settings
from app.decision.schemas import DecisionRead
from app.rating import service as rating_service
from app.rating.schemas import QuoteRead, RateTableRead
from app.submission import service
from app.submission.schemas import SubmissionCreate, SubmissionDetail, SubmissionRead

# The authenticated underwriter would come from the OIDC token (Authentik) at deploy time; for the
# v1 API+domain slice the actor is a fixed placeholder recorded in the decision/audit trail.
_ACTOR = "underwriter@ktayl"

v1 = APIRouter(prefix="/v1", tags=["underwriting"])
ops = APIRouter(tags=["ops"])


@v1.post("/submissions", response_model=SubmissionRead, status_code=status.HTTP_201_CREATED)
def create_submission(
    payload: SubmissionCreate,
    db: DbSession,
    counterparties: CounterpartyRepo,
    audit: AuditRepo,
) -> SubmissionRead:
    submission = service.create_submission(db, payload, counterparties, audit, actor=_ACTOR)
    return SubmissionRead.model_validate(submission)


@v1.post("/submissions/{submission_id}/assess", response_model=DecisionRead)
def assess_submission(
    submission_id: str,
    db: DbSession,
    appetite: AppetiteRepo,
    audit: AuditRepo,
) -> DecisionRead:
    try:
        decision = service.assess_submission(db, submission_id, appetite, audit, actor=_ACTOR)
    except service.SubmissionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found") from None
    except service.NoRulesetError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="no appetite ruleset available"
        ) from None
    return DecisionRead.model_validate(decision)


@v1.get("/submissions/{submission_id}", response_model=SubmissionDetail)
def get_submission(submission_id: str, db: DbSession) -> SubmissionDetail:
    try:
        submission = service.get_submission(db, submission_id)
    except service.SubmissionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found") from None
    decision = service.latest_decision(db, submission_id)
    detail = SubmissionDetail.model_validate(submission)
    if decision is not None:
        detail.latest_decision = DecisionRead.model_validate(decision)
    return detail


@v1.post("/submissions/{submission_id}/quote", response_model=QuoteRead)
def quote_submission(
    submission_id: str,
    db: DbSession,
    rate_tables: RateTableRepo,
    quotes: QuoteRepo,
    audit: AuditRepo,
) -> QuoteRead:
    try:
        quote = rating_service.quote_submission(db, submission_id, rate_tables, quotes, audit, actor=_ACTOR)
    except service.SubmissionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found") from None
    except rating_service.NoDecisionError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission has not been assessed") from None
    except rating_service.DeclinedRiskError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a declined risk cannot be quoted") from None
    except rating_service.NoRateTableError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="no rate table available") from None
    return QuoteRead.model_validate(quote)


@v1.get("/submissions/{submission_id}/quote", response_model=QuoteRead)
def get_quote(submission_id: str, db: DbSession, quotes: QuoteRepo) -> QuoteRead:
    # 404 if the submission itself does not exist, or if it exists but has no quote yet.
    try:
        service.get_submission(db, submission_id)
    except service.SubmissionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found") from None
    quote = rating_service.latest_quote(db, submission_id, quotes)
    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no quote for submission") from None
    return QuoteRead.model_validate(quote)


@v1.post("/submissions/{submission_id}/bind", response_model=BindingRead)
def bind_submission(
    submission_id: str,
    db: DbSession,
    bindings: BindingRepo,
    quotes: QuoteRepo,
    audit: AuditRepo,
    policy_client: PolicyServiceClientDep,
    publisher: BoundRiskPublisherDep,
) -> BindingRead:
    # Guard: the latest decision must be accept AND a quote must exist; re-bind is an idempotent no-op.
    try:
        binding = bind_service.bind_submission(
            db, submission_id, bindings, quotes, audit, policy_client, publisher, actor=_ACTOR
        )
    except service.SubmissionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found") from None
    except bind_service.NoAcceptedDecisionError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="only an accepted submission can be bound",
        ) from None
    except bind_service.NoQuoteError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="submission has no quote to bind"
        ) from None
    except bind_service.PolicyAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="policy already exists in the policy service but could not be resolved",
        ) from None
    return BindingRead.model_validate(binding)


@v1.get("/submissions/{submission_id}/bind", response_model=BindingRead)
def get_binding(submission_id: str, db: DbSession, bindings: BindingRepo) -> BindingRead:
    # 404 if the submission itself does not exist, or if it exists but is not bound yet.
    try:
        service.get_submission(db, submission_id)
    except service.SubmissionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found") from None
    binding = bind_service.latest_binding(db, submission_id, bindings)
    if binding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission is not bound") from None
    return BindingRead.model_validate(binding)


@v1.get("/rate-tables", response_model=list[RateTableRead])
def list_rate_tables(rate_tables: RateTableRepo) -> list[RateTableRead]:
    return [RateTableRead.model_validate(rt) for rt in rate_tables.list_versions()]


@v1.get("/submissions/{submission_id}/audit", response_model=list[AuditEntryRead])
def get_submission_audit(submission_id: str, db: DbSession, audit: AuditRepo) -> list[AuditEntryRead]:
    # 404 if the submission itself does not exist (an empty log ≠ a missing submission).
    try:
        service.get_submission(db, submission_id)
    except service.SubmissionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found") from None
    entries = audit.list_for_submission(submission_id)
    return [AuditEntryRead.model_validate(e) for e in entries]


@ops.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@ops.get("/info")
def info() -> dict[str, str]:
    settings = get_settings()
    return {"service": settings.service_name, "version": settings.version}
