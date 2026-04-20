"""f1_valuations + f2_momentum + f3_risk_appetite + f4_positioning per spec §8.

Four dedicated tables per docs/specs/indices/financial/<F>-*.md §8.

Revision ID: 010_financial_indices_schemas
Revises: 009_credit_indices_schemas
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "010_financial_indices_schemas"
down_revision = "009_credit_indices_schemas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "f1_valuations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("cape_ratio", sa.Float, nullable=True),
        sa.Column("erp_median_bps", sa.Integer, nullable=True),
        sa.Column("buffett_ratio", sa.Float, nullable=True),
        sa.Column("forward_pe", sa.Float, nullable=True),
        sa.Column("property_gap_pp", sa.Float, nullable=True),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_overlay", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_f1_score_range"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_f1_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_f1_cdm"),
    )
    op.create_index("idx_f1_cd", "f1_valuations", ["country_code", "date"])

    op.create_table(
        "f2_momentum",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("mom_3m_pct", sa.Float, nullable=True),
        sa.Column("mom_6m_pct", sa.Float, nullable=True),
        sa.Column("mom_12m_pct", sa.Float, nullable=True),
        sa.Column("breadth_above_ma200_pct", sa.Float, nullable=True),
        sa.Column("cross_asset_score", sa.Float, nullable=True),
        sa.Column("primary_index", sa.String(16), nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_f2_score_range"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_f2_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_f2_cdm"),
    )
    op.create_index("idx_f2_cd", "f2_momentum", ["country_code", "date"])

    op.create_table(
        "f3_risk_appetite",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("vix_level", sa.Float, nullable=True),
        sa.Column("move_level", sa.Float, nullable=True),
        sa.Column("credit_spread_hy_bps", sa.Integer, nullable=True),
        sa.Column("credit_spread_ig_bps", sa.Integer, nullable=True),
        sa.Column("fci_level", sa.Float, nullable=True),
        sa.Column("crypto_vol_level", sa.Float, nullable=True),
        sa.Column("components_available", sa.Integer, nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_f3_score_range"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_f3_confidence"),
        sa.CheckConstraint(
            "components_available BETWEEN 3 AND 5", name="ck_f3_components_available"
        ),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_f3_cdm"),
    )
    op.create_index("idx_f3_cd", "f3_risk_appetite", ["country_code", "date"])

    op.create_table(
        "f4_positioning",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("aaii_bull_minus_bear_pct", sa.Float, nullable=True),
        sa.Column("put_call_ratio", sa.Float, nullable=True),
        sa.Column("cot_noncomm_net_sp500", sa.Integer, nullable=True),
        sa.Column("margin_debt_gdp_pct", sa.Float, nullable=True),
        sa.Column("ipo_activity_score", sa.Float, nullable=True),
        sa.Column("components_available", sa.Integer, nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_f4_score_range"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_f4_confidence"),
        sa.CheckConstraint(
            "components_available BETWEEN 2 AND 5", name="ck_f4_components_available"
        ),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_f4_cdm"),
    )
    op.create_index("idx_f4_cd", "f4_positioning", ["country_code", "date"])


def downgrade() -> None:
    op.drop_index("idx_f4_cd", "f4_positioning")
    op.drop_table("f4_positioning")
    op.drop_index("idx_f3_cd", "f3_risk_appetite")
    op.drop_table("f3_risk_appetite")
    op.drop_index("idx_f2_cd", "f2_momentum")
    op.drop_table("f2_momentum")
    op.drop_index("idx_f1_cd", "f1_valuations")
    op.drop_table("f1_valuations")
