"""Shared submission payload factories + rule specs for tests. No large inline blobs in tests."""

from __future__ import annotations

from typing import Any

from app.appetite.rules import RulesetSpec

# The v1 seed ruleset as a pure spec (mirrors the seeded DB ruleset).
V1_SPEC = RulesetSpec(
    version=1,
    allowed_lobs=frozenset({"commercial_property"}),
    max_tiv_eur=1_000_000_000,  # €10,000,000 in eurocents
    excluded_occupancies=frozenset({"fireworks_manufacturing"}),
    sanctioned_countries=frozenset({"KP", "IR", "SY", "RU"}),
)


def submission_payload(**overrides: Any) -> dict[str, Any]:
    """A valid commercial_property submission-create payload; override any field per test."""
    payload: dict[str, Any] = {
        "counterparty": {"name": "Acme Logistics SAS", "country": "FR"},
        "line_of_business": "commercial_property",
        "tiv_eur": 500_000_00,  # €500,000
        "occupancy": "warehouse",
        "country": "FR",
        "postcode": "75001",
        "requested_cover": "All-risks property damage + business interruption",
        "broker_ref": "BRK-001",
    }
    payload.update(overrides)
    return payload
