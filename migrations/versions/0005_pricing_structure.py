"""submission pricing structure — ADR-010 deductible/limit + loss history

Revision ID: 0005_submission_pricing_structure
Revises: 0004_quote_manifest
Create Date: 2026-11-20

Adds the ADR-010 deterministic actuarial completeness inputs to the submission: the policy
deductible + limit (for deductible-credit + ILF pricing) and the experience-period prior premium +
prior losses (for credibility-blended experience rating). All columns are NULLABLE — submissions
created before ADR-010 don't carry them, and a null input prices neutral (×1), so existing quotes
are unchanged. Money is eurocents (minor units), matching `submission.tiv_eur`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_pricing_structure"
down_revision: str | None = "0004_quote_manifest"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("submission", sa.Column("deductible_eur", sa.BigInteger(), nullable=True))
    op.add_column("submission", sa.Column("limit_eur", sa.BigInteger(), nullable=True))
    op.add_column("submission", sa.Column("prior_premium_eur", sa.BigInteger(), nullable=True))
    op.add_column("submission", sa.Column("prior_losses_eur", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("submission", "prior_losses_eur")
    op.drop_column("submission", "prior_premium_eur")
    op.drop_column("submission", "limit_eur")
    op.drop_column("submission", "deductible_eur")
