"""L5 meta-regimes table per spec regimes/cross-cycle-meta-regimes.md §6.

Revision ID: 017_l5_meta_regimes_schema
Revises: 016_economic_cycle_composite_schema
Create Date: 2026-04-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "017_l5_meta_regimes_schema"
down_revision = "016_economic_cycle_composite_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "l5_meta_regimes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("l5_id", sa.String(36), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("meta_regime", sa.String(32), nullable=False),
        sa.Column(
            "ecs_id",
            sa.String(36),
            sa.ForeignKey("economic_cycle_scores.ecs_id", name="fk_l5_ecs_id"),
            nullable=True,
        ),
        sa.Column(
            "cccs_id",
            sa.String(36),
            sa.ForeignKey("credit_cycle_scores.cccs_id", name="fk_l5_cccs_id"),
            nullable=True,
        ),
        sa.Column(
            "fcs_id",
            sa.String(36),
            sa.ForeignKey("financial_cycle_scores.fcs_id", name="fk_l5_fcs_id"),
            nullable=True,
        ),
        sa.Column(
            "msc_id",
            sa.String(36),
            sa.ForeignKey("monetary_cycle_scores.msc_id", name="fk_l5_msc_id"),
            nullable=True,
        ),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("classification_reason", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("l5_id", name="uq_l5_id"),
        sa.CheckConstraint(
            "meta_regime IN ('overheating','stagflation_risk','late_cycle_bubble',"
            "'recession_risk','soft_landing','unclassified')",
            name="ck_l5_meta_regime",
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_l5_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_l5_cdm"),
    )
    op.create_index("idx_l5_cd", "l5_meta_regimes", ["country_code", "date"])
    op.create_index(
        "idx_l5_regime",
        "l5_meta_regimes",
        ["country_code", "meta_regime", "date"],
    )


def downgrade() -> None:
    op.drop_index("idx_l5_regime", "l5_meta_regimes")
    op.drop_index("idx_l5_cd", "l5_meta_regimes")
    op.drop_table("l5_meta_regimes")
