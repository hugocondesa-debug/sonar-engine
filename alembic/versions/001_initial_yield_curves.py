"""initial yield curves schema

Revision ID: 001_nss_schema
Revises:
Create Date: 2026-04-19
"""

import sqlalchemy as sa
from alembic import op

revision = "001_nss_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "yield_curves_raw",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("observation_date", sa.Date, nullable=False),
        sa.Column("tenor_years", sa.Numeric(6, 3), nullable=False),
        sa.Column("yield_bps", sa.Integer, nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_series_id", sa.String(100)),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "country_code",
            "observation_date",
            "tenor_years",
            "source",
            name="uq_raw_obs",
        ),
    )
    op.create_index(
        "ix_raw_country_date",
        "yield_curves_raw",
        ["country_code", "observation_date"],
    )

    op.create_table(
        "yield_curves_params",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("observation_date", sa.Date, nullable=False),
        sa.Column("beta0", sa.Numeric(10, 6), nullable=False),
        sa.Column("beta1", sa.Numeric(10, 6), nullable=False),
        sa.Column("beta2", sa.Numeric(10, 6), nullable=False),
        sa.Column("beta3", sa.Numeric(10, 6), nullable=False),
        sa.Column("tau1", sa.Numeric(10, 6), nullable=False),
        sa.Column("tau2", sa.Numeric(10, 6), nullable=False),
        sa.Column("rmse_bps", sa.Numeric(8, 3)),
        sa.Column("n_observations", sa.Integer, nullable=False),
        sa.Column("methodology_version", sa.String(10), nullable=False),
        sa.Column("flags_json", sa.JSON),
        sa.Column(
            "fitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "country_code",
            "observation_date",
            "methodology_version",
            name="uq_params",
        ),
    )

    op.create_table(
        "yield_curves_fitted",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("observation_date", sa.Date, nullable=False),
        sa.Column("tenor_years", sa.Numeric(6, 3), nullable=False),
        sa.Column("fitted_yield_bps", sa.Integer, nullable=False),
        sa.Column("methodology_version", sa.String(10), nullable=False),
        sa.UniqueConstraint(
            "country_code",
            "observation_date",
            "tenor_years",
            "methodology_version",
            name="uq_fitted",
        ),
    )
    op.create_index(
        "ix_fitted_country_date",
        "yield_curves_fitted",
        ["country_code", "observation_date"],
    )

    op.create_table(
        "yield_curves_metadata",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("observation_date", sa.Date, nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("methodology_version", sa.String(10), nullable=False),
        sa.Column("optimizer_status", sa.String(20)),
        sa.Column("optimizer_iterations", sa.Integer),
        sa.Column("input_sources_json", sa.JSON),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_metadata_run", "yield_curves_metadata", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_metadata_run", "yield_curves_metadata")
    op.drop_table("yield_curves_metadata")
    op.drop_index("ix_fitted_country_date", "yield_curves_fitted")
    op.drop_table("yield_curves_fitted")
    op.drop_table("yield_curves_params")
    op.drop_index("ix_raw_country_date", "yield_curves_raw")
    op.drop_table("yield_curves_raw")
