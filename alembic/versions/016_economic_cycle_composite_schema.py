"""ECS cycle composite table per spec cycles/economic-ecs.md §8.

Revision ID: 016_economic_cycle_composite_schema
Revises: 015_monetary_cycle_composite_schema
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "016_economic_cycle_composite_schema"
down_revision = "015_monetary_cycle_composite_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "economic_cycle_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ecs_id", sa.String(36), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("score_0_100", sa.Float, nullable=False),
        sa.Column("regime", sa.String(16), nullable=False),
        sa.Column("regime_persistence_days", sa.Integer, nullable=False),
        sa.Column("e1_score_0_100", sa.Float, nullable=True),
        sa.Column("e2_score_0_100", sa.Float, nullable=True),
        sa.Column("e3_score_0_100", sa.Float, nullable=True),
        sa.Column("e4_score_0_100", sa.Float, nullable=True),
        sa.Column("e1_weight_effective", sa.Float, nullable=False),
        sa.Column("e2_weight_effective", sa.Float, nullable=False),
        sa.Column("e3_weight_effective", sa.Float, nullable=False),
        sa.Column("e4_weight_effective", sa.Float, nullable=False),
        sa.Column("indices_available", sa.Integer, nullable=False),
        sa.Column(
            "stagflation_overlay_active",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("stagflation_trigger_json", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("ecs_id", name="uq_ecs_id"),
        sa.CheckConstraint("score_0_100 BETWEEN 0 AND 100", name="ck_ecs_score"),
        sa.CheckConstraint(
            "regime IN ('EXPANSION','PEAK_ZONE','EARLY_RECESSION','RECESSION')",
            name="ck_ecs_regime",
        ),
        sa.CheckConstraint("regime_persistence_days >= 1", name="ck_ecs_regime_persistence_days"),
        sa.CheckConstraint(
            "e1_score_0_100 IS NULL OR e1_score_0_100 BETWEEN 0 AND 100",
            name="ck_ecs_e1_score",
        ),
        sa.CheckConstraint(
            "e2_score_0_100 IS NULL OR e2_score_0_100 BETWEEN 0 AND 100",
            name="ck_ecs_e2_score",
        ),
        sa.CheckConstraint(
            "e3_score_0_100 IS NULL OR e3_score_0_100 BETWEEN 0 AND 100",
            name="ck_ecs_e3_score",
        ),
        sa.CheckConstraint(
            "e4_score_0_100 IS NULL OR e4_score_0_100 BETWEEN 0 AND 100",
            name="ck_ecs_e4_score",
        ),
        sa.CheckConstraint(
            "e1_weight_effective BETWEEN 0 AND 1", name="ck_ecs_e1_weight_effective"
        ),
        sa.CheckConstraint(
            "e2_weight_effective BETWEEN 0 AND 1", name="ck_ecs_e2_weight_effective"
        ),
        sa.CheckConstraint(
            "e3_weight_effective BETWEEN 0 AND 1", name="ck_ecs_e3_weight_effective"
        ),
        sa.CheckConstraint(
            "e4_weight_effective BETWEEN 0 AND 1", name="ck_ecs_e4_weight_effective"
        ),
        sa.CheckConstraint("indices_available BETWEEN 3 AND 4", name="ck_ecs_indices_available"),
        sa.CheckConstraint(
            "stagflation_overlay_active IN (0, 1)",
            name="ck_ecs_stagflation_overlay_active",
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ecs_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version", name="uq_ecs_cdm"),
    )
    op.create_index("idx_ecs_cd", "economic_cycle_scores", ["country_code", "date"])
    op.create_index(
        "idx_ecs_regime",
        "economic_cycle_scores",
        ["country_code", "regime", "date"],
    )


def downgrade() -> None:
    op.drop_index("idx_ecs_regime", "economic_cycle_scores")
    op.drop_index("idx_ecs_cd", "economic_cycle_scores")
    op.drop_table("economic_cycle_scores")
