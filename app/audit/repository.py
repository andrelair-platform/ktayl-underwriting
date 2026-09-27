"""AuditEntry repository — append + read only. No update/delete by design (ADR-004)."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditEntry


class AuditRepository(Protocol):
    def append(
        self,
        submission_id: str,
        action: str,
        actor: str,
        ruleset_version: int | None = None,
        outcome: str | None = None,
        detail: dict | None = None,
    ) -> AuditEntry: ...

    def list_for_submission(self, submission_id: str) -> list[AuditEntry]: ...


class SqlAuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(
        self,
        submission_id: str,
        action: str,
        actor: str,
        ruleset_version: int | None = None,
        outcome: str | None = None,
        detail: dict | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            submission_id=submission_id,
            action=action,
            actor=actor,
            ruleset_version=ruleset_version,
            outcome=outcome,
            detail=detail or {},
        )
        self._session.add(entry)
        self._session.flush()
        return entry

    def list_for_submission(self, submission_id: str) -> list[AuditEntry]:
        return list(
            self._session.scalars(
                select(AuditEntry).where(AuditEntry.submission_id == submission_id).order_by(AuditEntry.at)
            )
        )
