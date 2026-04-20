"""index_values table — polymorphic L3 indices persistence.

Single table keyed by index_code per SESSION_CONTEXT Distincao critica
(not one table per index). value_0_100 = clip(50 + 16.67 * z_clamped, 0, 100).

Revision ID: 008_index_values
Revises: 007_erp_schema
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "008_index_values"
down_revision = "007_erp_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "index_values",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("index_code", sa.String(16), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("raw_value", sa.Float, nullable=False),
        sa.Column("zscore_clamped", sa.Float, nullable=False),
        sa.Column("value_0_100", sa.Float, nullable=False),
        sa.Column("sub_indicators_json", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_overlays_json", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("value_0_100 BETWEEN 0 AND 100", name="ck_iv_value_range"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_iv_confidence"),
        sa.UniqueConstraint(
            "index_code",
            "country_code",
            "date",
            "methodology_version",
            name="uq_iv_codecdm",
        ),
    )
    op.create_index(
        "idx_iv_code_cd",
        "index_values",
        ["index_code", "country_code", "date"],
    )
    op.create_index("idx_iv_cd", "index_values", ["country_code", "date"])


def downgrade() -> None:
    op.drop_index("idx_iv_cd", "index_values")
    op.drop_index("idx_iv_code_cd", "index_values")
    op.drop_table("index_values")
