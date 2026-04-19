"""exp_inflation_{bei,swap,derived,survey,canonical} schemas per spec §8.

Revision ID: 004_exp_inflation_schema
Revises: 003_ratings_schema
Create Date: 2026-04-21
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "004_exp_inflation_schema"
down_revision = "003_ratings_schema"
branch_labels = None
depends_on = None


def _common_preamble() -> list[Any]:
    return [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("exp_inf_id", sa.String(36), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
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
        "exp_inflation_bei",
        *_common_preamble(),
        sa.Column("nominal_yields_json", sa.Text, nullable=False),
        sa.Column("linker_real_yields_json", sa.Text, nullable=False),
        sa.Column("bei_tenors_json", sa.Text, nullable=False),
        sa.Column("linker_connector", sa.String(32), nullable=False),
        sa.Column("nss_fit_id", sa.String(36), nullable=True),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_exp_bei_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_exp_bei_cdm"),
    )
    op.create_index("idx_exp_bei_cd", "exp_inflation_bei", ["country_code", "date"])

    op.create_table(
        "exp_inflation_swap",
        *_common_preamble(),
        sa.Column("swap_rates_json", sa.Text, nullable=False),
        sa.Column("swap_provider", sa.String(32), nullable=False),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_exp_swap_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_exp_swap_cdm"),
    )
    op.create_index("idx_exp_swap_cd", "exp_inflation_swap", ["country_code", "date"])

    op.create_table(
        "exp_inflation_derived",
        *_common_preamble(),
        sa.Column("regional_bei_json", sa.Text, nullable=False),
        sa.Column("regional_source", sa.String(32), nullable=False),
        sa.Column("differential_pp", sa.Float, nullable=False),
        sa.Column("differential_window_years", sa.Integer, nullable=False),
        sa.Column("differential_computed_at", sa.DateTime, nullable=False),
        sa.Column("derived_tenors_json", sa.Text, nullable=False),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_exp_derived_confidence"),
        sa.UniqueConstraint(
            "country_code", "date", "methodology_version", name="uq_exp_derived_cdm"
        ),
    )
    op.create_index("idx_exp_derived_cd", "exp_inflation_derived", ["country_code", "date"])

    op.create_table(
        "exp_inflation_survey",
        *_common_preamble(),
        sa.Column("survey_name", sa.String(32), nullable=False),
        sa.Column("survey_release_date", sa.Date, nullable=False),
        sa.Column("horizons_json", sa.Text, nullable=False),
        sa.Column("interpolated_tenors_json", sa.Text, nullable=False),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_exp_survey_confidence"),
        sa.UniqueConstraint(
            "country_code",
            "date",
            "survey_name",
            "methodology_version",
            name="uq_exp_survey_cdsm",
        ),
    )
    op.create_index("idx_exp_survey_cd", "exp_inflation_survey", ["country_code", "date"])

    op.create_table(
        "exp_inflation_canonical",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("exp_inf_id", sa.String(36), nullable=False, unique=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("expected_inflation_tenors_json", sa.Text, nullable=False),
        sa.Column("source_method_per_tenor_json", sa.Text, nullable=False),
        sa.Column("methods_available", sa.Integer, nullable=False),
        sa.Column("bc_target_pct", sa.Float, nullable=True),
        sa.Column("anchor_deviation_bps", sa.Integer, nullable=True),
        sa.Column("anchor_status", sa.String(32), nullable=True),
        sa.Column("bei_vs_survey_divergence_bps", sa.Integer, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("methods_available BETWEEN 1 AND 4", name="ck_exp_canonical_methods"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_exp_canonical_confidence"),
        sa.UniqueConstraint(
            "country_code", "date", "methodology_version", name="uq_exp_canonical_cdm"
        ),
    )
    op.create_index("idx_exp_canonical_cd", "exp_inflation_canonical", ["country_code", "date"])


def downgrade() -> None:
    op.drop_index("idx_exp_canonical_cd", "exp_inflation_canonical")
    op.drop_table("exp_inflation_canonical")
    op.drop_index("idx_exp_survey_cd", "exp_inflation_survey")
    op.drop_table("exp_inflation_survey")
    op.drop_index("idx_exp_derived_cd", "exp_inflation_derived")
    op.drop_table("exp_inflation_derived")
    op.drop_index("idx_exp_swap_cd", "exp_inflation_swap")
    op.drop_table("exp_inflation_swap")
    op.drop_index("idx_exp_bei_cd", "exp_inflation_bei")
    op.drop_table("exp_inflation_bei")
