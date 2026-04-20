"""cost_of_capital_daily table — L6 pipeline output (Week 3.5F).

Revision ID: 006_cost_of_capital_daily
Revises: 005_crp_schema
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "006_cost_of_capital_daily"
down_revision = "005_crp_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cost_of_capital_daily",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("rf_local_pct", sa.Float, nullable=False),
        sa.Column("erp_mature_bps", sa.Integer, nullable=False),
        sa.Column("crp_bps", sa.Integer, nullable=False),
        sa.Column("beta", sa.Float, nullable=False),
        sa.Column("k_e_pct", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_kc_confidence"),
        sa.CheckConstraint("beta > 0", name="ck_kc_beta"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_kc_cdm"),
    )
    op.create_index("idx_kc_cd", "cost_of_capital_daily", ["country_code", "date"])


def downgrade() -> None:
    op.drop_index("idx_kc_cd", "cost_of_capital_daily")
    op.drop_table("cost_of_capital_daily")
