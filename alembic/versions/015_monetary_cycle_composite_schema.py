"""MSC cycle composite table per spec cycles/monetary-msc.md §8.

Revision ID: 015_monetary_cycle_composite_schema
Revises: 014_monetary_indices_schemas
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "015_monetary_cycle_composite_schema"
down_revision = "014_monetary_indices_schemas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monetary_cycle_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("msc_id", sa.String(36), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_0_100", sa.Float, nullable=False),
        sa.Column("regime_6band", sa.String(32), nullable=False),
        sa.Column("regime_3band", sa.String(16), nullable=False),
        sa.Column("regime_persistence_days", sa.Integer, nullable=False),
        sa.Column("m1_score_0_100", sa.Float, nullable=True),
        sa.Column("m2_score_0_100", sa.Float, nullable=True),
        sa.Column("m3_score_0_100", sa.Float, nullable=True),
        sa.Column("m4_score_0_100", sa.Float, nullable=True),
        sa.Column("cs_score_0_100", sa.Float, nullable=True),
        sa.Column("m1_weight_effective", sa.Float, nullable=False),
        sa.Column("m2_weight_effective", sa.Float, nullable=False),
        sa.Column("m3_weight_effective", sa.Float, nullable=False),
        sa.Column("m4_weight_effective", sa.Float, nullable=False),
        sa.Column("cs_weight_effective", sa.Float, nullable=False),
        sa.Column("inputs_available", sa.Integer, nullable=False),
        sa.Column("cs_hawkish_score", sa.Float, nullable=True),
        sa.Column("fed_dissent_count", sa.Integer, nullable=True),
        sa.Column("dot_plot_drift_bps", sa.Integer, nullable=True),
        sa.Column("dilemma_overlay_active", sa.Integer, nullable=False, server_default="0"),
        sa.Column("dilemma_trigger_json", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("msc_id", name="uq_msc_id"),
        sa.CheckConstraint("score_0_100 BETWEEN 0 AND 100", name="ck_msc_score"),
        sa.CheckConstraint(
            "regime_6band IN ('STRONGLY_ACCOMMODATIVE','ACCOMMODATIVE',"
            "'NEUTRAL_ACCOMMODATIVE','NEUTRAL_TIGHT','TIGHT','STRONGLY_TIGHT')",
            name="ck_msc_regime_6band",
        ),
        sa.CheckConstraint(
            "regime_3band IN ('ACCOMMODATIVE','NEUTRAL','TIGHT')",
            name="ck_msc_regime_3band",
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_msc_confidence"),
        sa.CheckConstraint("inputs_available BETWEEN 3 AND 5", name="ck_msc_inputs_available"),
        sa.CheckConstraint(
            "dilemma_overlay_active IN (0, 1)", name="ck_msc_dilemma_overlay_active"
        ),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_msc_cdm"),
    )
    op.create_index("idx_msc_cd", "monetary_cycle_scores", ["country_code", "date"])


def downgrade() -> None:
    op.drop_index("idx_msc_cd", "monetary_cycle_scores")
    op.drop_table("monetary_cycle_scores")
