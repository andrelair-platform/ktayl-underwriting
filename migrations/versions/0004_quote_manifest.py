"""quote manifest — ADR-009 P1 staged subtotals + input facts on the quote

Revision ID: 0004_quote_manifest
Revises: 0003_bind
Create Date: 2026-10-21

Adds the ADR-009 P1 pricing manifest to the quote: the staged premium subtotals (pure / technical /
commercial / taxes, eurocents) and the exact priced facts (JSON), so a quote is actuarially legible
AND replayable. All columns are NULLABLE — quotes written before P1 don't carry them. `facts` uses
`sa.JSON()` to match the existing `quote.breakdown` / `rate_table.rules` columns (Postgres + SQLite).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_quote_manifest"
down_revision: str | None = "0003_bind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quote", sa.Column("pure_premium_minor", sa.BigInteger(), nullable=True))
    op.add_column("quote", sa.Column("technical_premium_minor", sa.BigInteger(), nullable=True))
    op.add_column("quote", sa.Column("commercial_premium_minor", sa.BigInteger(), nullable=True))
    op.add_column("quote", sa.Column("taxes_minor", sa.BigInteger(), nullable=True))
    op.add_column("quote", sa.Column("facts", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("quote", "facts")
    op.drop_column("quote", "taxes_minor")
    op.drop_column("quote", "commercial_premium_minor")
    op.drop_column("quote", "technical_premium_minor")
    op.drop_column("quote", "pure_premium_minor")
