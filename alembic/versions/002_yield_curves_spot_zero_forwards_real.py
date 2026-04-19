"""yield_curves_{spot,zero,forwards,real} schemas per spec §8.

Adds the four NSS sibling tables alongside the Week 1 Migration 001 schema
(`yield_curves_{raw,params,fitted,metadata}`). The Week 1 family is now
effectively superseded by this one for L2 NSS persistence; clean-up of the
orphaned Week 1 tables is deferred to a future migration once no caller
references them.

Spec §8 minor tightening (doc-only, no NSS_v0.1 bump): a UNIQUE constraint
is added on `yield_curves_spot.fit_id` so the sibling tables can FK to it.
The spec showed FK targets without explicitly making the column UNIQUE; the
fix preserves the spec's intent (one fit_id per spot row) and does not
change any computed value.

Revision ID: 002_yield_curves_spot_zero_forwards_real
Revises: 001_nss_schema
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002_yield_curves_spot_zero_forwards_real"
down_revision = "001_nss_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "yield_curves_spot",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("fit_id", sa.String(36), nullable=False),
        sa.Column("beta_0", sa.Float, nullable=False),
        sa.Column("beta_1", sa.Float, nullable=False),
        sa.Column("beta_2", sa.Float, nullable=False),
        sa.Column("beta_3", sa.Float, nullable=True),
        sa.Column("lambda_1", sa.Float, nullable=False),
        sa.Column("lambda_2", sa.Float, nullable=True),
        sa.Column("fitted_yields_json", sa.Text, nullable=False),
        sa.Column("observations_used", sa.Integer, nullable=False),
        sa.Column("rmse_bps", sa.Float, nullable=False),
        sa.Column("xval_deviation_bps", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_connector", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ycs_confidence"),
        sa.UniqueConstraint(
            "country_code",
            "date",
            "methodology_version",
            name="uq_ycs_country_date_method",
        ),
        sa.UniqueConstraint("fit_id", name="uq_ycs_fit_id"),
    )
    op.create_index("idx_ycs_cd", "yield_curves_spot", ["country_code", "date"])

    op.create_table(
        "yield_curves_zero",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("fit_id", sa.String(36), nullable=False),
        sa.Column("zero_rates_json", sa.Text, nullable=False),
        sa.Column("derivation", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("derivation IN ('nss_derived', 'bootstrap')", name="ck_ycz_derivation"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ycz_confidence"),
        sa.UniqueConstraint(
            "country_code",
            "date",
            "methodology_version",
            name="uq_ycz_country_date_method",
        ),
        sa.ForeignKeyConstraint(
            ["fit_id"],
            ["yield_curves_spot.fit_id"],
            ondelete="CASCADE",
            name="fk_ycz_fit_id",
        ),
    )
    op.create_index("idx_ycz_cd", "yield_curves_zero", ["country_code", "date"])
    op.create_index("idx_ycz_fitid", "yield_curves_zero", ["fit_id"])

    op.create_table(
        "yield_curves_forwards",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("fit_id", sa.String(36), nullable=False),
        sa.Column("forwards_json", sa.Text, nullable=False),
        sa.Column("breakeven_forwards_json", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ycf_confidence"),
        sa.UniqueConstraint(
            "country_code",
            "date",
            "methodology_version",
            name="uq_ycf_country_date_method",
        ),
        sa.ForeignKeyConstraint(
            ["fit_id"],
            ["yield_curves_spot.fit_id"],
            ondelete="CASCADE",
            name="fk_ycf_fit_id",
        ),
    )
    op.create_index("idx_ycf_cd", "yield_curves_forwards", ["country_code", "date"])
    op.create_index("idx_ycf_fitid", "yield_curves_forwards", ["fit_id"])

    op.create_table(
        "yield_curves_real",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("fit_id", sa.String(36), nullable=False),
        sa.Column("real_yields_json", sa.Text, nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("linker_connector", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("method IN ('direct_linker', 'derived')", name="ck_ycr_method"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ycr_confidence"),
        sa.UniqueConstraint(
            "country_code",
            "date",
            "methodology_version",
            name="uq_ycr_country_date_method",
        ),
        sa.ForeignKeyConstraint(
            ["fit_id"],
            ["yield_curves_spot.fit_id"],
            ondelete="CASCADE",
            name="fk_ycr_fit_id",
        ),
    )
    op.create_index("idx_ycr_cd", "yield_curves_real", ["country_code", "date"])
    op.create_index("idx_ycr_fitid", "yield_curves_real", ["fit_id"])


def downgrade() -> None:
    op.drop_index("idx_ycr_fitid", "yield_curves_real")
    op.drop_index("idx_ycr_cd", "yield_curves_real")
    op.drop_table("yield_curves_real")
    op.drop_index("idx_ycf_fitid", "yield_curves_forwards")
    op.drop_index("idx_ycf_cd", "yield_curves_forwards")
    op.drop_table("yield_curves_forwards")
    op.drop_index("idx_ycz_fitid", "yield_curves_zero")
    op.drop_index("idx_ycz_cd", "yield_curves_zero")
    op.drop_table("yield_curves_zero")
    op.drop_index("idx_ycs_cd", "yield_curves_spot")
    op.drop_table("yield_curves_spot")
