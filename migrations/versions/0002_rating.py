"""rating — rate_table (versioned, immutable) + quote

Revision ID: 0002_rating
Revises: 0001_initial
Create Date: 2026-09-27

Seeds rate table version 1 (ADR-004) so the quote endpoint has a current rate table. Types are
generic (String/BigInteger/JSON/DateTime) so the same migration runs on Postgres and SQLite.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0002_rating"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_V1_RULES = {
    "base_rate_permille": "0.5",
    "occupancy_factors": {
        "office": "1.0",
        "retail": "1.1",
        "warehouse": "1.25",
        "light_manufacturing": "1.5",
        "fireworks_manufacturing": "3.0",
    },
    "adjustments": [
        {"name": "high_tiv_loading", "kind": "loading", "factor": "1.10", "applies_when": "high_tiv"},
        {"name": "sprinklered_discount", "kind": "discount", "factor": "0.95", "applies_when": "sprinklered"},
    ],
}


def upgrade() -> None:
    op.create_table(
        "rate_table",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
    )
    op.create_table(
        "quote",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("submission_id", sa.String(length=36), sa.ForeignKey("submission.id"), nullable=False, index=True),
        sa.Column("premium_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rate_table_version", sa.Integer(), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Seed rate table v1 (ADR-004: versioned, immutable).
    rate_table = sa.table(
        "rate_table",
        sa.column("id", sa.String),
        sa.column("version", sa.Integer),
        sa.column("effective_at", sa.DateTime(timezone=True)),
        sa.column("rules", sa.JSON),
    )
    op.bulk_insert(
        rate_table,
        [
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "version": 1,
                "effective_at": datetime.now(UTC),
                "rules": json.loads(json.dumps(_V1_RULES)),
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("quote")
    op.drop_table("rate_table")
