"""Unit tests for CreditCycleScore + FinancialCycleScore ORMs (sprint-2b c2)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from sonar.db.models import CreditCycleScore, FinancialCycleScore

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestCreditCycleScore:
    def _row(self, **overrides: object) -> CreditCycleScore:
        base: dict[str, object] = {
            "cccs_id": "00000000-0000-0000-0000-000000000001",
            "country_code": "US",
            "date": date(2024, 1, 31),
            "methodology_version": "CCCS_COMPOSITE_v0.1",
            "score_0_100": 58.0,
            "regime": "BOOM",
            "regime_persistence_days": 1,
            "cs_score_0_100": 55.0,
            "lc_score_0_100": 60.0,
            "ms_score_0_100": 62.0,
            "qs_score_0_100": None,
            "cs_weight_effective": 0.44,
            "lc_weight_effective": 0.33,
            "ms_weight_effective": 0.22,
            "components_available": 3,
            "boom_overlay_active": 0,
            "confidence": 0.85,
            "flags": "QS_PLACEHOLDER",
        }
        base.update(overrides)
        return CreditCycleScore(**base)  # type: ignore[arg-type]

    def test_insert_and_read_back(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        row = db_session.execute(select(CreditCycleScore)).scalar_one()
        assert row.regime == "BOOM"
        assert row.score_0_100 == pytest.approx(58.0)
        assert row.qs_score_0_100 is None

    def test_invalid_regime_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(regime="STAGNATION"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_score_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(score_0_100=101.0))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_components_above_4_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(components_available=5))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_boom_overlay_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(boom_overlay_active=2))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_unique_cdm(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        db_session.add(self._row(cccs_id="00000000-0000-0000-0000-000000000002"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestFinancialCycleScore:
    def _row(self, **overrides: object) -> FinancialCycleScore:
        base: dict[str, object] = {
            "fcs_id": "00000000-0000-0000-0000-000000000010",
            "country_code": "US",
            "date": date(2024, 1, 31),
            "methodology_version": "FCS_COMPOSITE_v0.1",
            "score_0_100": 62.0,
            "regime": "OPTIMISM",
            "regime_persistence_days": 1,
            "f1_score_0_100": 60.0,
            "f2_score_0_100": 65.0,
            "f3_score_0_100": 58.0,
            "f4_score_0_100": 66.0,
            "f1_weight_effective": 0.30,
            "f2_weight_effective": 0.25,
            "f3_weight_effective": 0.25,
            "f4_weight_effective": 0.20,
            "indices_available": 4,
            "country_tier": 1,
            "bubble_warning_active": 0,
            "confidence": 0.85,
        }
        base.update(overrides)
        return FinancialCycleScore(**base)  # type: ignore[arg-type]

    def test_insert_and_read_back(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        row = db_session.execute(select(FinancialCycleScore)).scalar_one()
        assert row.regime == "OPTIMISM"

    def test_invalid_regime_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(regime="PANIC"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_country_tier_range(self, db_session: Session) -> None:
        db_session.add(self._row(country_tier=5))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_indices_below_3_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(indices_available=2))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_unique_cdm(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        db_session.add(self._row(fcs_id="00000000-0000-0000-0000-000000000020"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
