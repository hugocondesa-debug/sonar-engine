"""credit_to_gdp_stock + credit_to_gdp_gap + credit_impulse + dsr per spec §8.

Four dedicated tables per README §"Output schema (consistent across 4)":
- L1 credit_to_gdp_stock (spec L1_CREDIT_GDP_STOCK_v0.1)
- L2 credit_to_gdp_gap (spec L2_CREDIT_GDP_GAP_v0.1)
- L3 credit_impulse (spec L3_CREDIT_IMPULSE_v0.1) — UNIQUE includes segment
- L4 dsr (spec L4_DSR_v0.1) — UNIQUE includes segment

Revision ID: 009_credit_indices_schemas
Revises: 008_index_values
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "009_credit_indices_schemas"
down_revision = "008_index_values"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_to_gdp_stock",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("series_variant", sa.String(2), nullable=False),
        sa.Column("gdp_vintage_mode", sa.String(16), nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("structural_band", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_connector", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("series_variant IN ('Q', 'F')", name="ck_l1_cgs_series_variant"),
        sa.CheckConstraint(
            "gdp_vintage_mode IN ('production', 'backtest')",
            name="ck_l1_cgs_vintage_mode",
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_l1_cgs_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_l1_cgs_cdm"),
    )
    op.create_index("idx_l1_cgs_cd", "credit_to_gdp_stock", ["country_code", "date"])

    op.create_table(
        "credit_to_gdp_gap",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("gap_hp_pp", sa.Float, nullable=False),
        sa.Column("gap_hamilton_pp", sa.Float, nullable=False),
        sa.Column("trend_gdp_pct", sa.Float, nullable=False),
        sa.Column("hp_lambda", sa.Integer, nullable=False, server_default="400000"),
        sa.Column("hamilton_horizon_q", sa.Integer, nullable=False, server_default="8"),
        sa.Column("concordance", sa.String(16), nullable=False),
        sa.Column("phase_band", sa.String(16), nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_connector", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "concordance IN ('both_above','both_below','divergent')",
            name="ck_l2_cgg_concordance",
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_l2_cgg_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_l2_cgg_cdm"),
    )
    op.create_index("idx_l2_cgg_cd", "credit_to_gdp_gap", ["country_code", "date"])

    op.create_table(
        "credit_impulse",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("segment", sa.String(4), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("impulse_pp", sa.Float, nullable=False),
        sa.Column("flow_t_lcu", sa.Float, nullable=False),
        sa.Column("flow_t_minus4_lcu", sa.Float, nullable=False),
        sa.Column("delta_flow_lcu", sa.Float, nullable=False),
        sa.Column("gdp_t_minus4_lcu", sa.Float, nullable=False),
        sa.Column("series_variant", sa.String(2), nullable=False),
        sa.Column("smoothing", sa.String(4), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_connector", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("segment IN ('PNFS','HH','NFC')", name="ck_l3_ci_segment"),
        sa.CheckConstraint("series_variant IN ('Q','F')", name="ck_l3_ci_series_variant"),
        sa.CheckConstraint("smoothing IN ('raw','ma4')", name="ck_l3_ci_smoothing"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_l3_ci_confidence"),
        sa.UniqueConstraint(
            "country_code",
            "date",
            "methodology_version",
            "segment",
            name="uq_l3_ci_cdms",
        ),
    )
    op.create_index("idx_l3_ci_cd", "credit_impulse", ["country_code", "date"])

    op.create_table(
        "dsr",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("segment", sa.String(4), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("dsr_pct", sa.Float, nullable=False),
        sa.Column("dsr_deviation_pp", sa.Float, nullable=False),
        sa.Column("lending_rate_pct", sa.Float, nullable=False),
        sa.Column("avg_maturity_years", sa.Float, nullable=False),
        sa.Column("debt_to_gdp_ratio", sa.Float, nullable=False),
        sa.Column("annuity_factor", sa.Float, nullable=False),
        sa.Column("formula_mode", sa.String(4), nullable=False),
        sa.Column("band", sa.String(16), nullable=False),
        sa.Column("denominator", sa.String(32), nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_connector", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("segment IN ('PNFS','HH','NFC')", name="ck_l4_dsr_segment"),
        sa.CheckConstraint("formula_mode IN ('full','o2','o1')", name="ck_l4_dsr_formula_mode"),
        sa.CheckConstraint("band IN ('baseline','alert','critical')", name="ck_l4_dsr_band"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_l4_dsr_confidence"),
        sa.UniqueConstraint(
            "country_code",
            "date",
            "methodology_version",
            "segment",
            name="uq_l4_dsr_cdms",
        ),
    )
    op.create_index("idx_l4_dsr_cd", "dsr", ["country_code", "date"])


def downgrade() -> None:
    op.drop_index("idx_l4_dsr_cd", "dsr")
    op.drop_table("dsr")
    op.drop_index("idx_l3_ci_cd", "credit_impulse")
    op.drop_table("credit_impulse")
    op.drop_index("idx_l2_cgg_cd", "credit_to_gdp_gap")
    op.drop_table("credit_to_gdp_gap")
    op.drop_index("idx_l1_cgs_cd", "credit_to_gdp_stock")
    op.drop_table("credit_to_gdp_stock")
