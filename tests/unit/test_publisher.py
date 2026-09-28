"""Unit tests for the NATS bound-risk publisher's bounded retry (m3) — no real NATS.

The retry is in-process + best-effort: it re-tries a few times with a short backoff, then re-raises the
last failure so the caller can record ``event_published=false`` (the replay seed for a future outbox).
"""

from __future__ import annotations

import pytest

from app.bind.publisher import NatsBoundRiskPublisher


def test_publish_succeeds_first_try(monkeypatch: pytest.MonkeyPatch) -> None:
    pub = NatsBoundRiskPublisher(nats_url="nats://x", max_attempts=3, backoff_seconds=0)
    calls = {"n": 0}

    async def _ok(event: dict) -> None:
        calls["n"] += 1

    monkeypatch.setattr(pub, "_publish", _ok)
    pub.publish({"policy_number": "UW-1"})
    assert calls["n"] == 1  # no retry when the first attempt works


def test_publish_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    pub = NatsBoundRiskPublisher(nats_url="nats://x", max_attempts=3, backoff_seconds=0)
    calls = {"n": 0}

    async def _flaky(event: dict) -> None:
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")

    monkeypatch.setattr(pub, "_publish", _flaky)
    pub.publish({"policy_number": "UW-2"})
    assert calls["n"] == 2  # failed once, succeeded on the retry


def test_publish_exhausts_attempts_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    pub = NatsBoundRiskPublisher(nats_url="nats://x", max_attempts=3, backoff_seconds=0)
    calls = {"n": 0}

    async def _always_fail(event: dict) -> None:
        calls["n"] += 1
        raise RuntimeError("nats down")

    monkeypatch.setattr(pub, "_publish", _always_fail)
    with pytest.raises(RuntimeError, match="nats down"):
        pub.publish({"policy_number": "UW-3"})
    assert calls["n"] == 3  # bounded — exactly max_attempts tries


def test_max_attempts_floored_at_one(monkeypatch: pytest.MonkeyPatch) -> None:
    pub = NatsBoundRiskPublisher(nats_url="nats://x", max_attempts=0, backoff_seconds=0)
    calls = {"n": 0}

    async def _fail(event: dict) -> None:
        calls["n"] += 1
        raise RuntimeError("x")

    monkeypatch.setattr(pub, "_publish", _fail)
    with pytest.raises(RuntimeError):
        pub.publish({})
    assert calls["n"] == 1  # max(1, 0) → still tries once
