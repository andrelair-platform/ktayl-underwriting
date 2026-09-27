"""bind — binding (the UW-side record of a risk bound into the live policy service, ADR-006)

Revision ID: 0003_bind
Revises: 0002_rating
Create Date: 2026-09-27

One binding per submission (unique). policy_number is unique + deterministic from the quote id
(ADR-006 idempotency). Types are generic (String/Boolean/DateTime) so the same migration runs on
Postgres and SQLite.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_bind"
down_revision: str | None = "0002_rating"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "binding",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "submission_id",
            sa.String(length=36),
            sa.ForeignKey("submission.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("quote_id", sa.String(length=36), sa.ForeignKey("quote.id"), nullable=False, index=True),
        sa.Column("policy_number", sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column("pas_policy_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("event_published", sa.Boolean(), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bound_by", sa.String(length=128), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("binding")
