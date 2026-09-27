"""Domain enums shared across modules. Kept as string enums so they serialise cleanly and store
as plain VARCHARs (portable across Postgres and the SQLite test DB)."""

from __future__ import annotations

from enum import StrEnum


class LineOfBusiness(StrEnum):
    """Lines of business. v1 starter LOB is commercial_property; others are out of appetite."""

    COMMERCIAL_PROPERTY = "commercial_property"
    MARINE = "marine"
    ENGINEERING = "engineering"
    FINANCIAL_LINES = "financial_lines"


class Occupancy(StrEnum):
    """Occupancy / activity of the insured risk (commercial property)."""

    OFFICE = "office"
    RETAIL = "retail"
    WAREHOUSE = "warehouse"
    LIGHT_MANUFACTURING = "light_manufacturing"
    FIREWORKS_MANUFACTURING = "fireworks_manufacturing"


class Outcome(StrEnum):
    """Appetite/eligibility assessment outcome."""

    ACCEPT = "accept"
    REFER = "refer"
    DECLINE = "decline"


class ReasonCode(StrEnum):
    """Stable, auditable reason codes emitted by the appetite engine."""

    LOB_OUT_OF_APPETITE = "LOB_OUT_OF_APPETITE"
    TIV_ABOVE_AUTHORITY = "TIV_ABOVE_AUTHORITY"
    EXCLUDED_OCCUPANCY = "EXCLUDED_OCCUPANCY"
    SANCTIONED_COUNTRY = "SANCTIONED_COUNTRY"
    WITHIN_APPETITE = "WITHIN_APPETITE"
