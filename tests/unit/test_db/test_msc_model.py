"""Unit tests for MonetaryCycleScore ORM (sprint-6.2 c1)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from sonar.db.models import MonetaryCycleScore

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestMonetaryCycleScore:
    def _row(self, **overrides: object) -> MonetaryCycleScore:
        base: dict[str, object] = {
            "msc_id": "00000000-0000-0000-0000-000000000001",
            "country_code": "US",
            "date": date(2024, 12, 31),
            "methodology_version": "MSC_COMPOSITE_v0.1",
            "score_0_100": 58.0,
            "regime_6band": "NEUTRAL_TIGHT",
            "regime_3band": "NEUTRAL",
            "regime_persistence_days": 1,
            "m1_score_0_100": 62.0,
            "m2_score_0_100": 54.0,
            "m3_score_0_100": 60.0,
            "m4_score_0_100": 52.0,
            "cs_score_0_100": None,
            "m1_weight_effective": 0.333,
            "m2_weight_effective": 0.167,
            "m3_weight_effective": 0.278,
            "m4_weight_effective": 0.222,
            "cs_weight_effective": 0.0,
            "inputs_available": 4,
            "dilemma_overlay_active": 0,
            "confidence": 0.72,
            "flags": "COMM_SIGNAL_MISSING",
        }
        base.update(overrides)
        return MonetaryCycleScore(**base)  # type: ignore[arg-type]

    def test_insert_and_read_back(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        row = db_session.execute(select(MonetaryCycleScore)).scalar_one()
        assert row.regime_6band == "NEUTRAL_TIGHT"
        assert row.regime_3band == "NEUTRAL"
        assert row.score_0_100 == pytest.approx(58.0)
        assert row.cs_score_0_100 is None
        assert row.inputs_available == 4

    def test_invalid_regime_6band_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(regime_6band="DOVISH"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_invalid_regime_3band_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(regime_3band="EASING"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_score_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(score_0_100=101.0))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_inputs_above_5_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(inputs_available=6))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_inputs_below_3_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(inputs_available=2))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_dilemma_overlay_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(dilemma_overlay_active=2))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_confidence_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(confidence=1.01))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_unique_cdm(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        db_session.add(self._row(msc_id="00000000-0000-0000-0000-000000000002"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
