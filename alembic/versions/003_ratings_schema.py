"""ratings_{agency_raw,consolidated,spread_calibration} schemas per spec §8.

Revision ID: 003_ratings_schema
Revises: 002_yield_curves_spot_zero_forwards_real
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_ratings_schema"
down_revision = "002_yield_curves_spot_zero_forwards_real"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ratings_agency_raw",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rating_id", sa.String(36), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("agency", sa.String(8), nullable=False),
        sa.Column("rating_type", sa.String(2), nullable=False),
        sa.Column("rating_raw", sa.String(16), nullable=False),
        sa.Column("sonar_notch_base", sa.Integer, nullable=False),
        sa.Column("outlook", sa.String(16), nullable=False),
        sa.Column("watch", sa.String(20), nullable=True),
        sa.Column("notch_adjusted", sa.Float, nullable=False),
        sa.Column("action_date", sa.Date, nullable=False),
        sa.Column("source_connector", sa.String(32), nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("agency IN ('SP','MOODYS','FITCH','DBRS')", name="ck_rar_agency"),
        sa.CheckConstraint("rating_type IN ('FC','LC')", name="ck_rar_rating_type"),
        sa.CheckConstraint("sonar_notch_base BETWEEN 0 AND 21", name="ck_rar_notch_base"),
        sa.CheckConstraint(
            "outlook IN ('positive','stable','negative','developing')",
            name="ck_rar_outlook",
        ),
        sa.CheckConstraint(
            "watch IS NULL OR watch IN ('watch_positive','watch_negative','watch_developing')",
            name="ck_rar_watch",
        ),
        sa.CheckConstraint("notch_adjusted BETWEEN -1.0 AND 22.0", name="ck_rar_notch_adj"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_rar_confidence"),
        sa.UniqueConstraint(
            "country_code",
            "date",
            "agency",
            "rating_type",
            "methodology_version",
            name="uq_rar_cdarm",
        ),
    )
    op.create_index("idx_rar_cdt", "ratings_agency_raw", ["country_code", "date", "rating_type"])
    op.create_index("idx_rar_rid", "ratings_agency_raw", ["rating_id"])

    op.create_table(
        "ratings_consolidated",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rating_id", sa.String(36), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("rating_type", sa.String(2), nullable=False),
        sa.Column("consolidated_sonar_notch", sa.Float, nullable=False),
        sa.Column("notch_fractional", sa.Float, nullable=False),
        sa.Column("agencies_count", sa.Integer, nullable=False),
        sa.Column("agencies_json", sa.Text, nullable=False),
        sa.Column("outlook_composite", sa.String(16), nullable=False),
        sa.Column("watch_composite", sa.String(20), nullable=True),
        sa.Column("default_spread_bps", sa.Integer, nullable=True),
        sa.Column("calibration_date", sa.Date, nullable=True),
        sa.Column("rating_cds_deviation_pct", sa.Float, nullable=True),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("rating_type IN ('FC','LC')", name="ck_rc_rating_type"),
        sa.CheckConstraint("consolidated_sonar_notch BETWEEN 0 AND 21", name="ck_rc_notch"),
        sa.CheckConstraint("agencies_count BETWEEN 0 AND 4", name="ck_rc_agencies_count"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_rc_confidence"),
        sa.UniqueConstraint("rating_id", name="uq_rc_rating_id"),
        sa.UniqueConstraint(
            "country_code", "date", "rating_type", "methodology_version", name="uq_rc_cdrm"
        ),
    )
    op.create_index("idx_rc_cdt", "ratings_consolidated", ["country_code", "date", "rating_type"])

    op.create_table(
        "ratings_spread_calibration",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("calibration_date", sa.Date, nullable=False),
        sa.Column("sonar_notch_int", sa.Integer, nullable=False),
        sa.Column("rating_equivalent", sa.String(8), nullable=False),
        sa.Column("default_spread_bps", sa.Integer, nullable=True),
        sa.Column("range_low_bps", sa.Integer, nullable=True),
        sa.Column("range_high_bps", sa.Integer, nullable=True),
        sa.Column("moodys_pd_5y_pct", sa.Float, nullable=True),
        sa.Column("calibration_source", sa.String(64), nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint("sonar_notch_int BETWEEN 0 AND 21", name="ck_rsc_notch"),
        sa.UniqueConstraint(
            "calibration_date", "sonar_notch_int", "methodology_version", name="uq_rsc_dnm"
        ),
    )
    op.create_index(
        "idx_rsc_notch", "ratings_spread_calibration", ["sonar_notch_int", "calibration_date"]
    )


def downgrade() -> None:
    op.drop_index("idx_rsc_notch", "ratings_spread_calibration")
    op.drop_table("ratings_spread_calibration")
    op.drop_index("idx_rc_cdt", "ratings_consolidated")
    op.drop_table("ratings_consolidated")
    op.drop_index("idx_rar_rid", "ratings_agency_raw")
    op.drop_index("idx_rar_cdt", "ratings_agency_raw")
    op.drop_table("ratings_agency_raw")
