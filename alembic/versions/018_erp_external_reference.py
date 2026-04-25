"""Sprint 3.1: erp_external_reference table (Damodaran + future sources).

Adjacent to computed ``erp_canonical`` (Sprint 3); preserves spec
``overlays/erp-daily.md`` §11 "compute, don't consume" — canonical stays
computed, this table holds editorial / benchmarking external references.

Revision ID: 018_erp_external_reference
Revises: 017_l5_meta_regimes_schema
Create Date: 2026-04-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "018_erp_external_reference"
down_revision = "017_l5_meta_regimes_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "erp_external_reference",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("market_index", sa.String(16), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("erp_bps", sa.Integer, nullable=False),
        sa.Column("publication_date", sa.Date, nullable=True),
        sa.Column("source_file", sa.String(64), nullable=True),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_erp_external_conf"),
        sa.UniqueConstraint("market_index", "date", "source", name="uq_erp_external_mds"),
    )
    op.create_index(
        "idx_erp_external_md",
        "erp_external_reference",
        ["market_index", "date", "source"],
    )


def downgrade() -> None:
    op.drop_index("idx_erp_external_md", "erp_external_reference")
    op.drop_table("erp_external_reference")
