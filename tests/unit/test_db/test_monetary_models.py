"""Unit tests for M1/M2/M4 ORM constraints (week6-sprint-1b c1-c2)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from sonar.db.models import M1EffectiveRatesResult, M2TaylorGapsResult, M4FciResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestM1Orm:
    def _row(self, **overrides: object) -> M1EffectiveRatesResult:
        base: dict[str, object] = {
            "country_code": "US",
            "date": date(2024, 12, 31),
            "methodology_version": "M1_EFFECTIVE_RATES_v0.2",
            "score_normalized": 65.0,
            "score_raw": 0.02,
            "policy_rate_pct": 0.0525,
            "shadow_rate_pct": 0.0525,
            "real_rate_pct": 0.0275,
            "r_star_pct": 0.008,
            "components_json": "{}",
            "lookback_years": 30,
            "confidence": 0.9,
            "source_connector": "fred",
        }
        base.update(overrides)
        return M1EffectiveRatesResult(**base)  # type: ignore[arg-type]

    def test_insert_and_read_back(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        row = db_session.execute(select(M1EffectiveRatesResult)).scalar_one()
        assert row.r_star_pct == pytest.approx(0.008)

    def test_score_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(score_normalized=110.0))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_unique_cdm(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        db_session.add(self._row(score_normalized=70.0))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestM2Orm:
    def _row(self, **overrides: object) -> M2TaylorGapsResult:
        base: dict[str, object] = {
            "country_code": "US",
            "date": date(2024, 12, 31),
            "methodology_version": "M2_TAYLOR_GAPS_v0.1",
            "score_normalized": 60.0,
            "score_raw": 0.005,
            "taylor_implied_pct": 0.045,
            "taylor_gap_pp": 0.005,
            "taylor_uncertainty_pp": 0.003,
            "r_star_source": "HLW",
            "output_gap_source": "CBO",
            "variants_computed": 4,
            "components_json": "{}",
            "lookback_years": 30,
            "confidence": 0.85,
            "source_connector": "fred,cbo",
        }
        base.update(overrides)
        return M2TaylorGapsResult(**base)  # type: ignore[arg-type]

    def test_insert_and_variants_field(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        row = db_session.execute(select(M2TaylorGapsResult)).scalar_one()
        assert row.variants_computed == 4

    def test_variants_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(variants_computed=5))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestM4Orm:
    def _row(self, **overrides: object) -> M4FciResult:
        base: dict[str, object] = {
            "country_code": "US",
            "date": date(2024, 12, 31),
            "methodology_version": "M4_FCI_v0.1",
            "score_normalized": 55.0,
            "score_raw": -0.5,
            "fci_level": -0.5,
            "fci_change_12m": 0.1,
            "fci_provider": "NFCI_CHICAGO",
            "components_available": 1,
            "fci_components_json": "{}",
            "lookback_years": 30,
            "confidence": 0.9,
            "source_connector": "fred",
        }
        base.update(overrides)
        return M4FciResult(**base)  # type: ignore[arg-type]

    def test_insert_and_provider_field(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        row = db_session.execute(select(M4FciResult)).scalar_one()
        assert row.fci_provider == "NFCI_CHICAGO"

    def test_invalid_provider_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(fci_provider="UNKNOWN"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_components_above_7_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(components_available=8))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
