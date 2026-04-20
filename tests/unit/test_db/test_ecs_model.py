"""Unit tests for EconomicCycleScore ORM (sprint-7.A c1)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from sonar.db.models import EconomicCycleScore

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestEconomicCycleScore:
    def _row(self, **overrides: object) -> EconomicCycleScore:
        base: dict[str, object] = {
            "ecs_id": "00000000-0000-0000-0000-000000000001",
            "country_code": "US",
            "date": date(2024, 12, 31),
            "methodology_version": "ECS_COMPOSITE_v0.1",
            "score_0_100": 58.5,
            "regime": "EXPANSION",
            "regime_persistence_days": 1,
            "e1_score_0_100": 62.0,
            "e2_score_0_100": 55.0,
            "e3_score_0_100": 57.0,
            "e4_score_0_100": 58.0,
            "e1_weight_effective": 0.35,
            "e2_weight_effective": 0.25,
            "e3_weight_effective": 0.25,
            "e4_weight_effective": 0.15,
            "indices_available": 4,
            "stagflation_overlay_active": 0,
            "confidence": 0.82,
            "flags": None,
        }
        base.update(overrides)
        return EconomicCycleScore(**base)  # type: ignore[arg-type]

    def test_insert_and_read_back(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        row = db_session.execute(select(EconomicCycleScore)).scalar_one()
        assert row.regime == "EXPANSION"
        assert row.score_0_100 == pytest.approx(58.5)
        assert row.indices_available == 4
        assert row.stagflation_overlay_active == 0

    def test_invalid_regime_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(regime="DEPRESSION"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_valid_regime_peak_zone(self, db_session: Session) -> None:
        db_session.add(self._row(regime="PEAK_ZONE", score_0_100=60.0))
        db_session.commit()

    def test_valid_regime_early_recession(self, db_session: Session) -> None:
        db_session.add(self._row(regime="EARLY_RECESSION", score_0_100=45.0))
        db_session.commit()

    def test_valid_regime_recession(self, db_session: Session) -> None:
        db_session.add(self._row(regime="RECESSION", score_0_100=30.0))
        db_session.commit()

    def test_score_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(score_0_100=101.0))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_negative_score_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(score_0_100=-1.0))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_indices_below_3_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(indices_available=2))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_indices_above_4_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(indices_available=5))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_indices_3_with_e4_null_accepted(self, db_session: Session) -> None:
        db_session.add(
            self._row(
                e4_score_0_100=None,
                e1_weight_effective=0.412,
                e2_weight_effective=0.294,
                e3_weight_effective=0.294,
                e4_weight_effective=0.0,
                indices_available=3,
                confidence=0.72,
                flags="E4_MISSING",
            )
        )
        db_session.commit()
        row = db_session.execute(select(EconomicCycleScore)).scalar_one()
        assert row.e4_score_0_100 is None
        assert row.indices_available == 3
        assert row.flags == "E4_MISSING"

    def test_weight_above_1_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(e1_weight_effective=1.2))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_persistence_zero_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(regime_persistence_days=0))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_stagflation_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(stagflation_overlay_active=2))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_confidence_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(confidence=1.1))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_unique_cdm(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        db_session.add(self._row(ecs_id="00000000-0000-0000-0000-000000000002"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_stagflation_active_with_json(self, db_session: Session) -> None:
        db_session.add(
            self._row(
                score_0_100=41.0,
                regime="EARLY_RECESSION",
                stagflation_overlay_active=1,
                stagflation_trigger_json='{"cpi_yoy": 0.115, "sahm_triggered": 1}',
                flags="STAGFLATION_OVERLAY_ACTIVE",
            )
        )
        db_session.commit()
        row = db_session.execute(select(EconomicCycleScore)).scalar_one()
        assert row.stagflation_overlay_active == 1
        assert row.stagflation_trigger_json is not None
