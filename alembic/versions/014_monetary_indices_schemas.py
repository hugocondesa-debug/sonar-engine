"""Monetary indices dedicated tables (M1 + M2 + M4).

Per specs indices/monetary/M{1,2,4}-*.md §8. M3 stays in the
polymorphic ``index_values`` table per Week 3.5 decision.

Revision ID: 014_monetary_indices_schemas
Revises: 013_cycle_composite_schemas
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "014_monetary_indices_schemas"
down_revision = "013_cycle_composite_schemas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monetary_m1_effective_rates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("policy_rate_pct", sa.Float, nullable=False),
        sa.Column("shadow_rate_pct", sa.Float, nullable=False),
        sa.Column("real_rate_pct", sa.Float, nullable=False),
        sa.Column("r_star_pct", sa.Float, nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_connector", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_m1_score_normalized"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_m1_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_m1_cdm"),
    )
    op.create_index("idx_m1_cd", "monetary_m1_effective_rates", ["country_code", "date"])

    op.create_table(
        "monetary_m2_taylor_gaps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("taylor_implied_pct", sa.Float, nullable=False),
        sa.Column("taylor_gap_pp", sa.Float, nullable=False),
        sa.Column("taylor_uncertainty_pp", sa.Float, nullable=False),
        sa.Column("r_star_source", sa.String(32), nullable=False),
        sa.Column("output_gap_source", sa.String(32), nullable=True),
        sa.Column("variants_computed", sa.Integer, nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_connector", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_m2_score_normalized"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_m2_confidence"),
        sa.CheckConstraint("variants_computed BETWEEN 1 AND 4", name="ck_m2_variants_computed"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_m2_cdm"),
    )
    op.create_index("idx_m2_cd", "monetary_m2_taylor_gaps", ["country_code", "date"])

    op.create_table(
        "monetary_m4_fci",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("fci_level", sa.Float, nullable=False),
        sa.Column("fci_change_12m", sa.Float, nullable=True),
        sa.Column("fci_provider", sa.String(32), nullable=False),
        sa.Column("components_available", sa.Integer, nullable=False),
        sa.Column("fci_components_json", sa.Text, nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_connector", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_m4_score_normalized"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_m4_confidence"),
        sa.CheckConstraint(
            "fci_provider IN ('NFCI_CHICAGO','CUSTOM_SONAR','IMF_GFSR')",
            name="ck_m4_fci_provider",
        ),
        sa.CheckConstraint(
            "components_available BETWEEN 1 AND 7", name="ck_m4_components_available"
        ),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_m4_cdm"),
    )
    op.create_index("idx_m4_cd", "monetary_m4_fci", ["country_code", "date"])


def downgrade() -> None:
    op.drop_index("idx_m4_cd", "monetary_m4_fci")
    op.drop_table("monetary_m4_fci")
    op.drop_index("idx_m2_cd", "monetary_m2_taylor_gaps")
    op.drop_table("monetary_m2_taylor_gaps")
    op.drop_index("idx_m1_cd", "monetary_m1_effective_rates")
    op.drop_table("monetary_m1_effective_rates")
