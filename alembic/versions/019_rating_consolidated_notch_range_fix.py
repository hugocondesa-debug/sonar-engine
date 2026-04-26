"""Sprint 4 patch: relax ck_rc_notch range to [-1.0, 22.0].

Spec §4 (Algorithm) defines ``consolidated_sonar_notch = median(notch_adjusted_i)``
where ``notch_adjusted ∈ [-1.0, 22.0]`` (sonar_notch_base [0,21] plus
outlook ±0.25 plus watch ±0.50). Spec §8 schema constraint ``BETWEEN 0 AND 21``
contradicted §4 — single-agency extreme rating actions (e.g. JP MOODYS
Aaa+positive → 21.25) failed CHECK on consolidate.

Resolution: align §8 with §4 by relaxing range to mirror raw table
``ck_rar_notch_adj`` constraint. Spec §8 amended in the same patch.

Revision ID: 019_rating_consolidated_notch_range_fix
Revises: 018_erp_external_reference
Create Date: 2026-04-25
"""

from __future__ import annotations

from alembic import op

revision = "019_rating_consolidated_notch_range_fix"
down_revision = "018_erp_external_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite: CHECK constraints require table rebuild via batch_alter_table.
    with op.batch_alter_table("ratings_consolidated") as batch_op:
        batch_op.drop_constraint("ck_rc_notch", type_="check")
        batch_op.create_check_constraint(
            "ck_rc_notch",
            "consolidated_sonar_notch BETWEEN -1.0 AND 22.0",
        )


def downgrade() -> None:
    with op.batch_alter_table("ratings_consolidated") as batch_op:
        batch_op.drop_constraint("ck_rc_notch", type_="check")
        batch_op.create_check_constraint(
            "ck_rc_notch",
            "consolidated_sonar_notch BETWEEN 0 AND 21",
        )
