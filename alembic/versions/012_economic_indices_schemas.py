"""Economic indices dedicated tables (E1 / E3 / E4).

Single migration creating 3 sibling tables per spec §8 for each index.
E2 already has its row in ``index_values`` (polymorphic table) from
Week 3.5; the new E-indices use dedicated tables for typed columns +
CHECK constraints + spec-specific extras (Sahm trigger columns on E3).

Revision ID: 012_economic_indices_schemas
Revises: 011_bis_credit_raw
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "012_economic_indices_schemas"
down_revision = "011_bis_credit_raw"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idx_economic_e1_activity",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("components_available", sa.Integer, nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_connectors", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_e1_score_normalized"),
        sa.CheckConstraint(
            "components_available BETWEEN 4 AND 6", name="ck_e1_components_available"
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_e1_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_e1_cdm"),
    )
    op.create_index("idx_e1_cd", "idx_economic_e1_activity", ["country_code", "date"])

    op.create_table(
        "idx_economic_e3_labor",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("sahm_triggered", sa.Integer, nullable=False),
        sa.Column("sahm_value", sa.Float, nullable=True),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("components_available", sa.Integer, nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_connectors", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_e3_score_normalized"),
        sa.CheckConstraint("sahm_triggered IN (0, 1)", name="ck_e3_sahm_triggered"),
        sa.CheckConstraint(
            "components_available BETWEEN 6 AND 10", name="ck_e3_components_available"
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_e3_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_e3_cdm"),
    )
    op.create_index("idx_e3_cd", "idx_economic_e3_labor", ["country_code", "date"])
    op.create_index(
        "idx_e3_sahm",
        "idx_economic_e3_labor",
        ["country_code", "sahm_triggered", "date"],
    )

    op.create_table(
        "idx_economic_e4_sentiment",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_normalized", sa.Float, nullable=False),
        sa.Column("score_raw", sa.Float, nullable=False),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("components_available", sa.Integer, nullable=False),
        sa.Column("lookback_years", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("source_connectors", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_e4_score_normalized"),
        sa.CheckConstraint(
            "components_available BETWEEN 6 AND 13", name="ck_e4_components_available"
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_e4_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_e4_cdm"),
    )
    op.create_index("idx_e4_cd", "idx_economic_e4_sentiment", ["country_code", "date"])


def downgrade() -> None:
    op.drop_index("idx_e4_cd", "idx_economic_e4_sentiment")
    op.drop_table("idx_economic_e4_sentiment")
    op.drop_index("idx_e3_sahm", "idx_economic_e3_labor")
    op.drop_index("idx_e3_cd", "idx_economic_e3_labor")
    op.drop_table("idx_economic_e3_labor")
    op.drop_index("idx_e1_cd", "idx_economic_e1_activity")
    op.drop_table("idx_economic_e1_activity")
