"""erp_{dcf,gordon,ey,cape,canonical} schemas per spec §8.

Revision ID: 007_erp_schema
Revises: 006_cost_of_capital_daily
Create Date: 2026-04-21
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "007_erp_schema"
down_revision = "006_cost_of_capital_daily"
branch_labels = None
depends_on = None


def _method_preamble() -> list[Any]:
    return [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("erp_id", sa.String(36), nullable=False),
        sa.Column("market_index", sa.String(16), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("erp_bps", sa.Integer, nullable=False),
    ]


def _method_tail() -> list[Any]:
    return [
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
    # erp_canonical must exist first — method tables FK to erp_canonical.erp_id.
    op.create_table(
        "erp_canonical",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("erp_id", sa.String(36), nullable=False),
        sa.Column("market_index", sa.String(16), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("erp_median_bps", sa.Integer, nullable=False),
        sa.Column("erp_range_bps", sa.Integer, nullable=False),
        sa.Column("methods_available", sa.Integer, nullable=False),
        sa.Column("erp_dcf_bps", sa.Integer, nullable=True),
        sa.Column("erp_gordon_bps", sa.Integer, nullable=True),
        sa.Column("erp_ey_bps", sa.Integer, nullable=True),
        sa.Column("erp_cape_bps", sa.Integer, nullable=True),
        sa.Column("forward_eps_divergence_pct", sa.Float, nullable=True),
        sa.Column("xval_deviation_bps", sa.Integer, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_erp_canonical_confidence"),
        sa.CheckConstraint("methods_available BETWEEN 1 AND 4", name="ck_erp_canonical_methods"),
        sa.UniqueConstraint("erp_id", name="uq_erp_canonical_erp_id"),
        sa.UniqueConstraint(
            "market_index", "date", "methodology_version", name="uq_erp_canonical_mdm"
        ),
    )
    op.create_index("idx_erp_canonical_md", "erp_canonical", ["market_index", "date"])

    for table, method_cols in (
        (
            "erp_dcf",
            [
                sa.Column("implied_r_pct", sa.Float, nullable=False),
                sa.Column("earnings_growth_pct", sa.Float, nullable=False),
                sa.Column("terminal_growth_pct", sa.Float, nullable=False),
            ],
        ),
        (
            "erp_gordon",
            [
                sa.Column("dividend_yield_pct", sa.Float, nullable=False),
                sa.Column("buyback_yield_pct", sa.Float, nullable=True),
                sa.Column("g_sustainable_pct", sa.Float, nullable=False),
            ],
        ),
        (
            "erp_ey",
            [
                sa.Column("forward_pe", sa.Float, nullable=False),
                sa.Column("forward_earnings", sa.Float, nullable=False),
                sa.Column("index_level", sa.Float, nullable=False),
            ],
        ),
        (
            "erp_cape",
            [
                sa.Column("cape_ratio", sa.Float, nullable=False),
                sa.Column("real_risk_free_pct", sa.Float, nullable=False),
                sa.Column("real_earnings_10y_avg", sa.Float, nullable=False),
            ],
        ),
    ):
        op.create_table(
            table,
            *_method_preamble(),
            *method_cols,
            *_method_tail(),
            sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=f"ck_{table}_confidence"),
            sa.UniqueConstraint(
                "market_index",
                "date",
                "methodology_version",
                name=f"uq_{table}_mdm",
            ),
            sa.ForeignKeyConstraint(
                ["erp_id"],
                ["erp_canonical.erp_id"],
                ondelete="CASCADE",
                name=f"fk_{table}_erp_id",
            ),
        )
        op.create_index(f"idx_{table}_md", table, ["market_index", "date"])


def downgrade() -> None:
    for table in ("erp_cape", "erp_ey", "erp_gordon", "erp_dcf"):
        op.drop_index(f"idx_{table}_md", table)
        op.drop_table(table)
    op.drop_index("idx_erp_canonical_md", "erp_canonical")
    op.drop_table("erp_canonical")
