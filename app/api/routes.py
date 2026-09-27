"""FastAPI routers: the /v1 workbench-core endpoints + ops endpoints (/healthz, /info)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AppetiteRepo, AuditRepo, CounterpartyRepo, DbSession
from app.audit.schemas import AuditEntryRead
from app.config import get_settings
from app.decision.schemas import DecisionRead
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
