"""BoundRiskPublisher — the seam that emits the bound-risk event after activate (ADR-006).

The event is the downstream seam for reinsurance/actuarial — it makes underwriting the authoritative
premium source. The interface is a ``typing.Protocol`` so tests inject a fake; the real impl publishes
to NATS (connect → publish → drain). Publishing is **best-effort**: a failure must NOT fail an
already-activated bind — the service logs it, records it in the audit detail, and leaves
``event_published`` False.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Protocol

logger = logging.getLogger(__name__)

# Subject the reinsurance/actuarial consumers subscribe to.
BOUND_RISK_SUBJECT = "insurance.underwriting.bound-risk"

# Bounded publish retry: a few attempts with a short backoff before giving up. This is a best-effort
# in-process retry (it never fails the bind — the service still catches a final failure and leaves
# `event_published=false`). It is NOT a durable delivery guarantee.
#
# Durability note (deferred): a Binding with `event_published=false` is the **replay seed for a
# future transactional outbox / reconciler** — the prod-hardening path is to persist the intent in
# the same DB transaction as the Binding and have a background reconciler re-publish un-published
# bindings until NATS acks. Do NOT build the full outbox now; the flag + this bounded retry are the
# thin v1 stand-in.
_PUBLISH_MAX_ATTEMPTS = 3
_PUBLISH_BACKOFF_SECONDS = 0.2


class BoundRiskPublisher(Protocol):
    """Publish a bound-risk event. May raise; the caller treats a failure as best-effort."""

    def publish(self, event: dict) -> None: ...


class NatsBoundRiskPublisher:
    """nats-py-backed publisher — connect, publish one message, drain (per-publish connection).

    A short-lived connection per publish keeps this dependency-light (no long-lived client to manage
    in the modular monolith). The synchronous ``publish`` drives the async nats client via
    ``asyncio.run``.
    """

    def __init__(
        self,
        nats_url: str,
        subject: str = BOUND_RISK_SUBJECT,
        connect_timeout_seconds: float = 5.0,
        max_attempts: int = _PUBLISH_MAX_ATTEMPTS,
        backoff_seconds: float = _PUBLISH_BACKOFF_SECONDS,
    ) -> None:
        self._nats_url = nats_url
        self._subject = subject
        self._connect_timeout_seconds = connect_timeout_seconds
        self._max_attempts = max(1, max_attempts)
        self._backoff_seconds = backoff_seconds

    def publish(self, event: dict) -> None:
        """Publish with a bounded retry; the LAST failure is re-raised for the caller to treat as
        best-effort (log + `event_published=false`). A binding left un-published is the replay seed
        for the future outbox/reconciler (see module docstring)."""
        last_exc: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                asyncio.run(self._publish(event))
                return
            except Exception as exc:  # noqa: BLE001 — bounded retry, re-raised below if all fail
                last_exc = exc
                logger.warning(
                    "bound-risk publish attempt %d/%d failed for %s: %s",
                    attempt,
                    self._max_attempts,
                    event.get("policy_number"),
                    exc,
                )
                if attempt < self._max_attempts:
                    time.sleep(self._backoff_seconds * attempt)
        assert last_exc is not None  # loop ran ≥1 time and every attempt failed
        raise last_exc

    async def _publish(self, event: dict) -> None:
        import nats

        connection = await nats.connect(self._nats_url, connect_timeout=self._connect_timeout_seconds)
        try:
            await connection.publish(self._subject, json.dumps(event).encode("utf-8"))
            await connection.flush()
        finally:
            await connection.drain()
