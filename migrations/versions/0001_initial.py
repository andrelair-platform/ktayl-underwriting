"""initial schema — counterparty, submission, appetite_ruleset, decision, audit_entry

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-27

Seeds appetite ruleset version 1 (ADR-004) so the assess endpoint has a current ruleset. Types are
generic (String/BigInteger/JSON/DateTime) so the same migration runs on Postgres and SQLite.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_V1_RULES = {
    "allowed_lobs": ["commercial_property"],
    "max_tiv_eur": 1_000_000_000,
    "excluded_occupancies": ["fireworks_manufacturing"],
    "sanctioned_countries": ["KP", "IR", "SY", "RU"],
}


def upgrade() -> None:
    op.create_table(
        "counterparty",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "submission",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("counterparty_id", sa.String(length=36), sa.ForeignKey("counterparty.id"), nullable=False),
        sa.Column("line_of_business", sa.String(length=64), nullable=False),
        sa.Column("tiv_eur", sa.BigInteger(), nullable=False),
        sa.Column("occupancy", sa.String(length=64), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("postcode", sa.String(length=16), nullable=False),
        sa.Column("requested_cover", sa.String(length=255), nullable=False),
        sa.Column("broker_ref", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "appetite_ruleset",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
    )
    op.create_table(
        "decision",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("submission_id", sa.String(length=36), sa.ForeignKey("submission.id"), nullable=False, index=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("appetite_version", sa.Integer(), nullable=False),
        sa.Column("decided_by", sa.String(length=128), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_entry",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("submission_id", sa.String(length=36), sa.ForeignKey("submission.id"), nullable=False, index=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ruleset_version", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
    )

    # Seed appetite ruleset v1 (ADR-004: versioned, immutable).
    appetite = sa.table(
        "appetite_ruleset",
        sa.column("id", sa.String),
        sa.column("version", sa.Integer),
        sa.column("effective_at", sa.DateTime(timezone=True)),
        sa.column("rules", sa.JSON),
    )
    op.bulk_insert(
        appetite,
        [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "version": 1,
                "effective_at": datetime.now(UTC),
                "rules": json.loads(json.dumps(_V1_RULES)),
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("audit_entry")
    op.drop_table("decision")
    op.drop_table("appetite_ruleset")
    op.drop_table("submission")
    op.drop_table("counterparty")
