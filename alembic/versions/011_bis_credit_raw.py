"""bis_credit_raw table — L0 ingestion cache for BIS credit dataflows.

One row per (country_code, date, dataflow) triplet per CAL-058 brief §4
Commit 2. Enables downstream indices to re-compute without re-fetching
BIS. Revision detection via fetch_response_hash (sha256 of BIS response).

Revision ID: 011_bis_credit_raw
Revises: 010_financial_indices_schemas
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "011_bis_credit_raw"
down_revision = "010_financial_indices_schemas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bis_credit_raw",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("dataflow", sa.String(16), nullable=False),
        sa.Column("value_raw", sa.Float, nullable=False),
        sa.Column("unit_descriptor", sa.String(32), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column("fetch_response_hash", sa.String(64), nullable=True),
        sa.CheckConstraint(
            "dataflow IN ('WS_TC','WS_DSR','WS_CREDIT_GAP')",
            name="ck_bcr_dataflow",
        ),
        sa.UniqueConstraint("country_code", "date", "dataflow", name="uq_bcr_cdd"),
    )
    op.create_index("idx_bcr_cd", "bis_credit_raw", ["country_code", "date"])


def downgrade() -> None:
    op.drop_index("idx_bcr_cd", "bis_credit_raw")
    op.drop_table("bis_credit_raw")
