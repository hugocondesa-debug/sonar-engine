"""crp_{cds,sov_spread,rating,canonical} schemas per spec §8 (post-sweep).

Revision ID: 005_crp_schema
Revises: 004_exp_inflation_schema
Create Date: 2026-04-21
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "005_crp_schema"
down_revision = "004_exp_inflation_schema"
branch_labels = None
depends_on = None


def _common_preamble() -> list[Any]:
    return [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("crp_id", sa.String(36), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("vol_ratio", sa.Float, nullable=False),
        sa.Column("vol_ratio_source", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "crp_cds",
        *_common_preamble(),
        sa.Column("cds_5y_bps", sa.Integer, nullable=False),
        sa.Column("cds_liquidity_class", sa.String(16), nullable=False),
        sa.Column("cds_bid_ask_bps", sa.Integer, nullable=True),
        sa.Column("cds_source", sa.String(32), nullable=False),
        sa.Column("default_spread_bps", sa.Integer, nullable=False),
        sa.Column("crp_decimal", sa.Float, nullable=False),
        sa.Column("crp_bps", sa.Integer, nullable=False),
        sa.CheckConstraint(
            "cds_liquidity_class IN ('liquid','moderate','thin')",
            name="ck_crp_cds_liq",
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_crp_cds_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_crp_cds_cdm"),
    )
    op.create_index("idx_crp_cds_cd", "crp_cds", ["country_code", "date"])

    op.create_table(
        "crp_sov_spread",
        *_common_preamble(),
        sa.Column("sov_yield_country_pct", sa.Float, nullable=False),
        sa.Column("sov_yield_benchmark_pct", sa.Float, nullable=False),
        sa.Column("tenor", sa.String(8), nullable=False),
        sa.Column("default_spread_bps", sa.Integer, nullable=False),
        sa.Column("crp_decimal", sa.Float, nullable=False),
        sa.Column("crp_bps", sa.Integer, nullable=False),
        sa.Column("currency_denomination", sa.String(8), nullable=False),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_crp_sov_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_crp_sov_cdm"),
    )
    op.create_index("idx_crp_sov_cd", "crp_sov_spread", ["country_code", "date"])

    op.create_table(
        "crp_rating",
        *_common_preamble(),
        sa.Column("consolidated_sonar_notch", sa.Float, nullable=False),
        sa.Column("notch_int", sa.Integer, nullable=False),
        sa.Column("calibration_date", sa.Date, nullable=False),
        sa.Column("default_spread_bps", sa.Integer, nullable=False),
        sa.Column("crp_decimal", sa.Float, nullable=False),
        sa.Column("crp_bps", sa.Integer, nullable=False),
        sa.Column("rating_id", sa.String(36), nullable=False),
        sa.CheckConstraint("consolidated_sonar_notch BETWEEN 0 AND 21", name="ck_crp_rating_notch"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_crp_rating_confidence"),
        sa.UniqueConstraint(
            "country_code", "date", "methodology_version", name="uq_crp_rating_cdm"
        ),
    )
    op.create_index("idx_crp_rating_cd", "crp_rating", ["country_code", "date"])

    op.create_table(
        "crp_canonical",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("crp_id", sa.String(36), nullable=False, unique=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("method_selected", sa.String(16), nullable=False),
        sa.Column("crp_cds_bps", sa.Integer, nullable=True),
        sa.Column("crp_sov_spread_bps", sa.Integer, nullable=True),
        sa.Column("crp_rating_bps", sa.Integer, nullable=True),
        sa.Column("crp_canonical_bps", sa.Integer, nullable=False),
        sa.Column("default_spread_bps", sa.Integer, nullable=False),
        sa.Column("vol_ratio", sa.Float, nullable=False),
        sa.Column("vol_ratio_source", sa.String(32), nullable=False),
        sa.Column("basis_default_spread_sov_minus_cds_bps", sa.Integer, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "method_selected IN ('CDS','SOV_SPREAD','RATING','BENCHMARK')",
            name="ck_crp_canonical_method",
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_crp_canonical_confidence"),
        sa.UniqueConstraint(
            "country_code", "date", "methodology_version", name="uq_crp_canonical_cdm"
        ),
    )
    op.create_index("idx_crp_canonical_cd", "crp_canonical", ["country_code", "date"])


def downgrade() -> None:
    op.drop_index("idx_crp_canonical_cd", "crp_canonical")
    op.drop_table("crp_canonical")
    op.drop_index("idx_crp_rating_cd", "crp_rating")
    op.drop_table("crp_rating")
    op.drop_index("idx_crp_sov_cd", "crp_sov_spread")
    op.drop_table("crp_sov_spread")
    op.drop_index("idx_crp_cds_cd", "crp_cds")
    op.drop_table("crp_cds")
