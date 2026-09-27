"""Binding repository — a typing.Protocol interface + a SQLAlchemy impl.

Bindings are insert + read only (there is no bind-then-edit path in v1). Reads by submission and by
policy_number back the idempotent re-bind guard in the service.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bind.models import Binding


class BindingRepository(Protocol):
    """Persist a binding + read it back by submission or policy_number."""

    def add(
        self,
        submission_id: str,
        quote_id: str,
        policy_number: str,
        pas_policy_id: str,
        status: str,
        event_published: bool,
        bound_by: str,
    ) -> Binding: ...

    def by_submission(self, submission_id: str) -> Binding | None: ...

    def by_policy_number(self, policy_number: str) -> Binding | None: ...


class SqlBindingRepository:
    """SQLAlchemy-backed binding store — insert + read (one binding per submission)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        submission_id: str,
        quote_id: str,
        policy_number: str,
        pas_policy_id: str,
        status: str,
        event_published: bool,
        bound_by: str,
    ) -> Binding:
        binding = Binding(
            submission_id=submission_id,
            quote_id=quote_id,
            policy_number=policy_number,
            pas_policy_id=pas_policy_id,
            status=status,
            event_published=event_published,
            bound_by=bound_by,
        )
        self._session.add(binding)
        self._session.flush()
        return binding

    def by_submission(self, submission_id: str) -> Binding | None:
        return self._session.scalar(select(Binding).where(Binding.submission_id == submission_id))

    def by_policy_number(self, policy_number: str) -> Binding | None:
        return self._session.scalar(select(Binding).where(Binding.policy_number == policy_number))
