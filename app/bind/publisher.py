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
from typing import Protocol

# Subject the reinsurance/actuarial consumers subscribe to.
BOUND_RISK_SUBJECT = "insurance.underwriting.bound-risk"


class BoundRiskPublisher(Protocol):
    """Publish a bound-risk event. May raise; the caller treats a failure as best-effort."""

    def publish(self, event: dict) -> None: ...


class NatsBoundRiskPublisher:
    """nats-py-backed publisher — connect, publish one message, drain (per-publish connection).

    A short-lived connection per publish keeps this dependency-light (no long-lived client to manage
    in the modular monolith). The synchronous ``publish`` drives the async nats client via
    ``asyncio.run``.
    """

    def __init__(self, nats_url: str, subject: str = BOUND_RISK_SUBJECT, connect_timeout_seconds: float = 5.0) -> None:
        self._nats_url = nats_url
        self._subject = subject
        self._connect_timeout_seconds = connect_timeout_seconds

    def publish(self, event: dict) -> None:
        asyncio.run(self._publish(event))

    async def _publish(self, event: dict) -> None:
        import nats

        connection = await nats.connect(self._nats_url, connect_timeout=self._connect_timeout_seconds)
        try:
            await connection.publish(self._subject, json.dumps(event).encode("utf-8"))
            await connection.flush()
        finally:
            await connection.drain()
