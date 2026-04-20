"""Persistence tests for M1/M2/M4 rows (week6 sprint 2b C6, CAL-100)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from sonar.db.models import (
    M1EffectiveRatesResult as M1Row,
    M2TaylorGapsResult as M2Row,
    M4FciResult as M4Row,
)
from sonar.db.persistence import (
    DuplicatePersistError,
    persist_m1_effective_rates_result,
    persist_m2_taylor_gaps_result,
    persist_m4_fci_result,
    persist_many_monetary_results,
)
from sonar.indices.base import IndexResult
from sonar.indices.monetary.m1_effective_rates import M1EffectiveRatesResult
from sonar.indices.monetary.m2_taylor_gaps import M2TaylorGapsResult
from sonar.indices.monetary.m4_fci import M4FciResult
from sonar.indices.monetary.orchestrator import MonetaryIndicesResults

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _m1_result(**overrides: object) -> M1EffectiveRatesResult:
    base: dict[str, object] = {
        "country_code": "US",
        "date": date(2024, 12, 31),
        "methodology_version": "M1_EFFECTIVE_RATES_v0.2",
        "score_normalized": 70.0,
        "score_raw": 0.0195,
        "policy_rate_pct": 0.0525,
        "shadow_rate_pct": 0.0525,
        "real_rate_pct": 0.0275,
        "r_star_pct": 0.008,
        "components_json": '{"real_shadow_rate": 0.0275}',
        "lookback_years": 30,
        "confidence": 0.80,
        "flags": (),
        "source_connector": "fred",
    }
    base.update(overrides)
    return M1EffectiveRatesResult(**base)  # type: ignore[arg-type]


def _m2_result(**overrides: object) -> M2TaylorGapsResult:
    base: dict[str, object] = {
        "country_code": "US",
        "date": date(2024, 12, 31),
        "methodology_version": "M2_TAYLOR_GAPS_v0.1",
        "score_normalized": 65.0,
        "score_raw": 0.005,
        "taylor_implied_pct": 0.0475,
        "taylor_gap_pp": 0.005,
        "taylor_uncertainty_pp": 0.002,
        "r_star_source": "HLW",
        "output_gap_source": "CBO",
        "variants_computed": 4,
        "components_json": '{"taylor_1993_gap_pp": 0.005}',
        "lookback_years": 30,
        "confidence": 0.75,
        "flags": (),
        "source_connector": "fred,cbo",
    }
    base.update(overrides)
    return M2TaylorGapsResult(**base)  # type: ignore[arg-type]


def _m4_result(**overrides: object) -> M4FciResult:
    base: dict[str, object] = {
        "country_code": "US",
        "date": date(2024, 12, 31),
        "methodology_version": "M4_FCI_v0.1",
        "score_normalized": 55.0,
        "score_raw": -0.5,
        "fci_level": -0.5,
        "fci_change_12m": -0.1,
        "fci_provider": "NFCI_CHICAGO",
        "components_available": 1,
        "fci_components_json": '{"nfci_level": -0.5}',
        "lookback_years": 30,
        "confidence": 0.85,
        "flags": (),
        "source_connector": "fred",
    }
    base.update(overrides)
    return M4FciResult(**base)  # type: ignore[arg-type]


class TestPersistM1:
    def test_happy_path(self, db_session: Session) -> None:
        persist_m1_effective_rates_result(db_session, _m1_result())
        row = db_session.query(M1Row).one()
        assert row.country_code == "US"
        assert row.methodology_version == "M1_EFFECTIVE_RATES_v0.2"
        assert row.score_normalized == pytest.approx(70.0)

    def test_duplicate_raises(self, db_session: Session) -> None:
        persist_m1_effective_rates_result(db_session, _m1_result())
        with pytest.raises(DuplicatePersistError, match="M1 row already persisted"):
            persist_m1_effective_rates_result(db_session, _m1_result())

    def test_flags_csv_serialization(self, db_session: Session) -> None:
        persist_m1_effective_rates_result(
            db_session,
            _m1_result(flags=("R_STAR_PROXY", "CALIBRATION_STALE")),
        )
        row = db_session.query(M1Row).one()
        assert row.flags == "R_STAR_PROXY,CALIBRATION_STALE"


class TestPersistM2:
    def test_happy_path(self, db_session: Session) -> None:
        persist_m2_taylor_gaps_result(db_session, _m2_result())
        row = db_session.query(M2Row).one()
        assert row.variants_computed == 4
        assert row.r_star_source == "HLW"

    def test_duplicate_raises(self, db_session: Session) -> None:
        persist_m2_taylor_gaps_result(db_session, _m2_result())
        with pytest.raises(DuplicatePersistError, match="M2 row already persisted"):
            persist_m2_taylor_gaps_result(db_session, _m2_result())


class TestPersistM4:
    def test_happy_path(self, db_session: Session) -> None:
        persist_m4_fci_result(db_session, _m4_result())
        row = db_session.query(M4Row).one()
        assert row.fci_provider == "NFCI_CHICAGO"
        assert row.components_available == 1

    def test_duplicate_raises(self, db_session: Session) -> None:
        persist_m4_fci_result(db_session, _m4_result())
        with pytest.raises(DuplicatePersistError, match="M4 row already persisted"):
            persist_m4_fci_result(db_session, _m4_result())

    def test_distinct_country_persists(self, db_session: Session) -> None:
        persist_m4_fci_result(db_session, _m4_result(country_code="US"))
        persist_m4_fci_result(
            db_session, _m4_result(country_code="DE", fci_provider="CUSTOM_SONAR")
        )
        assert db_session.query(M4Row).count() == 2


def _m3() -> IndexResult:
    return IndexResult(
        index_code="M3",
        country_code="US",
        date=date(2024, 12, 31),
        methodology_version="M3_MARKET_EXPECTATIONS_v1.0",
        raw_value=0.02,
        zscore_clamped=0.5,
        value_0_100=58.3,
        confidence=0.7,
        flags=(),
    )


class TestPersistManyMonetary:
    def test_m1_m2_m4_in_bundle(self, db_session: Session) -> None:
        bundle = MonetaryIndicesResults(
            country_code="US",
            observation_date=date(2024, 12, 31),
            m1=_m1_result(),
            m2=_m2_result(),
            m4=_m4_result(),
        )
        written = persist_many_monetary_results(db_session, bundle)
        assert written == {"m1": 1, "m2": 1, "m3": 0, "m4": 1}
        assert db_session.query(M1Row).count() == 1
        assert db_session.query(M2Row).count() == 1
        assert db_session.query(M4Row).count() == 1

    def test_m1_plus_m3(self, db_session: Session) -> None:
        bundle = MonetaryIndicesResults(
            country_code="US",
            observation_date=date(2024, 12, 31),
            m1=_m1_result(),
        )
        written = persist_many_monetary_results(db_session, bundle, m3=_m3())
        assert written == {"m1": 1, "m2": 0, "m3": 1, "m4": 0}

    def test_empty_bundle_returns_zeros(self, db_session: Session) -> None:
        bundle = MonetaryIndicesResults(country_code="US", observation_date=date(2024, 12, 31))
        assert persist_many_monetary_results(db_session, bundle) == {
            "m1": 0,
            "m2": 0,
            "m3": 0,
            "m4": 0,
        }

    def test_duplicate_in_batch_rolls_back(self, db_session: Session) -> None:
        persist_m1_effective_rates_result(db_session, _m1_result())
        bundle = MonetaryIndicesResults(
            country_code="US",
            observation_date=date(2024, 12, 31),
            m1=_m1_result(),
            m4=_m4_result(),
        )
        with pytest.raises(DuplicatePersistError, match="Batch monetary persist"):
            persist_many_monetary_results(db_session, bundle)
        # M4 must not have been persisted due to rollback.
        assert db_session.query(M4Row).count() == 0
