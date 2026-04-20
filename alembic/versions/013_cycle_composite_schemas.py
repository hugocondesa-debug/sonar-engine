"""Cycle composite tables (CCCS + FCS) per specs cycles/credit-cccs.md §8
and cycles/financial-fcs.md §8.

Revision ID: 013_cycle_composite_schemas
Revises: 012_economic_indices_schemas
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "013_cycle_composite_schemas"
down_revision = "012_economic_indices_schemas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_cycle_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("cccs_id", sa.String(36), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_0_100", sa.Float, nullable=False),
        sa.Column("regime", sa.String(16), nullable=False),
        sa.Column("regime_persistence_days", sa.Integer, nullable=False),
        sa.Column("cs_score_0_100", sa.Float, nullable=True),
        sa.Column("lc_score_0_100", sa.Float, nullable=True),
        sa.Column("ms_score_0_100", sa.Float, nullable=True),
        sa.Column("qs_score_0_100", sa.Float, nullable=True),
        sa.Column("cs_weight_effective", sa.Float, nullable=False),
        sa.Column("lc_weight_effective", sa.Float, nullable=False),
        sa.Column("ms_weight_effective", sa.Float, nullable=False),
        sa.Column("components_available", sa.Integer, nullable=False),
        sa.Column("l1_contribution_pct", sa.Float, nullable=True),
        sa.Column("l2_contribution_pct", sa.Float, nullable=True),
        sa.Column("l3_contribution_pct", sa.Float, nullable=True),
        sa.Column("l4_contribution_pct", sa.Float, nullable=True),
        sa.Column("f3_contribution_pct", sa.Float, nullable=True),
        sa.Column("f4_margin_debt_contribution_pct", sa.Float, nullable=True),
        sa.Column("boom_overlay_active", sa.Integer, nullable=False, server_default="0"),
        sa.Column("boom_trigger_json", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("cccs_id", name="uq_cccs_id"),
        sa.CheckConstraint("score_0_100 BETWEEN 0 AND 100", name="ck_cccs_score"),
        sa.CheckConstraint(
            "regime IN ('REPAIR','RECOVERY','BOOM','SPECULATION','DISTRESS')",
            name="ck_cccs_regime",
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_cccs_confidence"),
        sa.CheckConstraint(
            "components_available BETWEEN 3 AND 4", name="ck_cccs_components_available"
        ),
        sa.CheckConstraint("boom_overlay_active IN (0, 1)", name="ck_cccs_boom_overlay_active"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_cccs_cdm"),
    )
    op.create_index("idx_cccs_cd", "credit_cycle_scores", ["country_code", "date"])

    op.create_table(
        "financial_cycle_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fcs_id", sa.String(36), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_0_100", sa.Float, nullable=False),
        sa.Column("regime", sa.String(16), nullable=False),
        sa.Column("regime_persistence_days", sa.Integer, nullable=False),
        sa.Column("f1_score_0_100", sa.Float, nullable=True),
        sa.Column("f2_score_0_100", sa.Float, nullable=True),
        sa.Column("f3_score_0_100", sa.Float, nullable=True),
        sa.Column("f4_score_0_100", sa.Float, nullable=True),
        sa.Column("f1_weight_effective", sa.Float, nullable=False),
        sa.Column("f2_weight_effective", sa.Float, nullable=False),
        sa.Column("f3_weight_effective", sa.Float, nullable=False),
        sa.Column("f4_weight_effective", sa.Float, nullable=True),
        sa.Column("indices_available", sa.Integer, nullable=False),
        sa.Column("country_tier", sa.Integer, nullable=False),
        sa.Column("f3_m4_divergence", sa.Float, nullable=True),
        sa.Column("bubble_warning_active", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bubble_warning_components_json", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("fcs_id", name="uq_fcs_id"),
        sa.CheckConstraint("score_0_100 BETWEEN 0 AND 100", name="ck_fcs_score"),
        sa.CheckConstraint(
            "regime IN ('STRESS','CAUTION','OPTIMISM','EUPHORIA')", name="ck_fcs_regime"
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_fcs_confidence"),
        sa.CheckConstraint("indices_available BETWEEN 3 AND 4", name="ck_fcs_indices_available"),
        sa.CheckConstraint("country_tier BETWEEN 1 AND 4", name="ck_fcs_country_tier"),
        sa.CheckConstraint("bubble_warning_active IN (0, 1)", name="ck_fcs_bubble_warning_active"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_fcs_cdm"),
    )
    op.create_index("idx_fcs_cd", "financial_cycle_scores", ["country_code", "date"])


def downgrade() -> None:
    op.drop_index("idx_fcs_cd", "financial_cycle_scores")
    op.drop_table("financial_cycle_scores")
    op.drop_index("idx_cccs_cd", "credit_cycle_scores")
    op.drop_table("credit_cycle_scores")
