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
    """The insured risk's classification — the rating factor dimension. Named ``occupancy`` for the v1
    commercial-property LOB; from the multi-LOB extension it is the generic risk class and its meaning
    depends on the submission's line of business (property occupancy · marine cargo/hull class ·
    engineering works class). Each LOB's rate table carries the factor map for its own classes."""

    # Commercial property — building occupancy.
    OFFICE = "office"
    RETAIL = "retail"
    WAREHOUSE = "warehouse"
    LIGHT_MANUFACTURING = "light_manufacturing"
    FIREWORKS_MANUFACTURING = "fireworks_manufacturing"

    # Marine — cargo / hull class.
    CARGO_GENERAL = "cargo_general"
    CARGO_TEMPERATURE_CONTROLLED = "cargo_temperature_controlled"
    CARGO_HAZARDOUS = "cargo_hazardous"
    PROJECT_CARGO = "project_cargo"
    HULL = "hull"

    # Engineering — works / equipment class.
    CONTRACT_WORKS = "contract_works"  # CAR — contractors' all risks
    ERECTION_WORKS = "erection_works"  # EAR — erection all risks
    MACHINERY_BREAKDOWN = "machinery_breakdown"
    ELECTRONIC_EQUIPMENT = "electronic_equipment"


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
