"""Unit tests for FCS compute."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cycles.base import InsufficientCycleInputsError
from sonar.cycles.financial_fcs import (
    BUBBLE_WARNING_FCS_THRESHOLD,
    CANONICAL_WEIGHTS,
    MIN_INDICES_REQUIRED,
    TIER_1_STRICT_COUNTRIES,
    TIER_CONFIDENCE_CAPS,
    classify_regime,
    compute_fcs,
    persist_fcs_result,
    resolve_tier,
)
from sonar.db.models import (
    Base,
    FinancialCycleScore,
    FinancialMomentum,
    FinancialPositioning,
    FinancialRiskAppetite,
    FinancialValuations,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class TestResolveTier:
    def test_us_is_tier_1(self) -> None:
        assert resolve_tier("US") == 1

    def test_pt_is_tier_3(self) -> None:
        assert resolve_tier("PT") == 3

    def test_fr_is_tier_2(self) -> None:
        assert resolve_tier("FR") == 2

    def test_zz_unknown_is_tier_4(self) -> None:
        assert resolve_tier("ZZ") == 4


class TestClassifyRegime:
    def test_stress(self) -> None:
        assert classify_regime(20.0) == "STRESS"

    def test_caution(self) -> None:
        assert classify_regime(45.0) == "CAUTION"

    def test_optimism(self) -> None:
        assert classify_regime(65.0) == "OPTIMISM"

    def test_euphoria(self) -> None:
        assert classify_regime(80.0) == "EUPHORIA"

    def test_boundary_30_is_caution(self) -> None:
        assert classify_regime(30.0) == "CAUTION"

    def test_boundary_55_is_caution(self) -> None:
        assert classify_regime(55.0) == "CAUTION"

    def test_boundary_75_is_optimism(self) -> None:
        assert classify_regime(75.0) == "OPTIMISM"


def _seed_f_rows(
    session: Session,
    country: str = "US",
    observation_date: date = date(2024, 1, 31),
    *,
    f1: float | None = 60.0,
    f2: float | None = 62.0,
    f3: float | None = 58.0,
    f4: float | None = 55.0,
) -> None:
    if f1 is not None:
        session.add(
            FinancialValuations(
                country_code=country,
                date=observation_date,
                methodology_version="F1_VALUATIONS_v0.1",
                score_normalized=f1,
                score_raw=0.5,
                components_json="{}",
                lookback_years=20,
                confidence=0.85,
            )
        )
    if f2 is not None:
        session.add(
            FinancialMomentum(
                country_code=country,
                date=observation_date,
                methodology_version="F2_MOMENTUM_v0.1",
                score_normalized=f2,
                score_raw=0.7,
                components_json="{}",
                primary_index="SPX" if country == "US" else "STOXX",
                lookback_years=20,
                confidence=0.85,
            )
        )
    if f3 is not None:
        session.add(
            FinancialRiskAppetite(
                country_code=country,
                date=observation_date,
                methodology_version="F3_RISK_APPETITE_v0.1",
                score_normalized=f3,
                score_raw=0.3,
                components_json="{}",
                components_available=4,
                lookback_years=20,
                confidence=0.85,
            )
        )
    if f4 is not None:
        session.add(
            FinancialPositioning(
                country_code=country,
                date=observation_date,
                methodology_version="F4_POSITIONING_v0.1",
                score_normalized=f4,
                score_raw=0.2,
                components_json="{}",
                components_available=3,
                lookback_years=20,
                confidence=0.85,
            )
        )
    session.commit()


class TestComputeFcsHappy:
    def test_us_full_stack(self, db_session: Session) -> None:
        _seed_f_rows(db_session, country="US")
        result = compute_fcs(db_session, "US", date(2024, 1, 31))
        # FCS = 0.30*60 + 0.25*62 + 0.25*58 + 0.20*55 = 18 + 15.5 + 14.5 + 11 = 59
        assert result.score_0_100 == pytest.approx(59.0)
        assert result.regime == "OPTIMISM"
        assert result.indices_available == 4
        assert result.country_tier == 1
        # M4 always flagged until MSC sprint ships.
        assert "M4_UNAVAILABLE" in result.flags

    def test_weights_match_spec(self) -> None:
        assert CANONICAL_WEIGHTS == {"F1": 0.30, "F2": 0.25, "F3": 0.25, "F4": 0.20}

    def test_tier_1_countries_match_spec(self) -> None:
        assert frozenset({"US", "DE", "UK", "JP"}) == TIER_1_STRICT_COUNTRIES


class TestPolicyFour:
    def test_us_t1_missing_f4_raises(self, db_session: Session) -> None:
        _seed_f_rows(db_session, country="US", f4=None)
        with pytest.raises(InsufficientCycleInputsError, match="Tier-1"):
            compute_fcs(db_session, "US", date(2024, 1, 31))

    def test_pt_t3_missing_f4_degrades(self, db_session: Session) -> None:
        _seed_f_rows(db_session, country="PT", f4=None)
        result = compute_fcs(db_session, "PT", date(2024, 1, 31))
        assert result.country_tier == 3
        assert "F4_COVERAGE_SPARSE" in result.flags
        # 3 indices available → passes min; re-weight applied.
        assert result.indices_available == 3
        # Tier cap 0.80; re-weight cap 0.75 → confidence <= 0.75.
        assert result.confidence <= 0.75

    def test_fr_t2_missing_f4_degrades(self, db_session: Session) -> None:
        _seed_f_rows(db_session, country="FR", f4=None)
        result = compute_fcs(db_session, "FR", date(2024, 1, 31))
        assert result.country_tier == 2
        assert result.confidence <= TIER_CONFIDENCE_CAPS[2]


class TestMinimumThreshold:
    def test_two_indices_raises(self, db_session: Session) -> None:
        _seed_f_rows(db_session, country="PT", f1=None, f2=None)
        with pytest.raises(InsufficientCycleInputsError, match=f">= {MIN_INDICES_REQUIRED}"):
            compute_fcs(db_session, "PT", date(2024, 1, 31))

    def test_zero_indices_raises(self, db_session: Session) -> None:
        with pytest.raises(InsufficientCycleInputsError):
            compute_fcs(db_session, "PT", date(2024, 1, 31))


class TestPersistenceRoundTrip:
    def test_persists_fcs_row(self, db_session: Session) -> None:
        _seed_f_rows(db_session, country="US")
        result = compute_fcs(db_session, "US", date(2024, 1, 31))
        persist_fcs_result(db_session, result)
        row = db_session.execute(select(FinancialCycleScore)).scalar_one()
        assert row.regime == result.regime
        assert row.score_0_100 == pytest.approx(result.score_0_100)


class TestBubbleWarningPlaceholder:
    def test_high_fcs_without_property_gap_skips_overlay(self, db_session: Session) -> None:
        # High F1/F2/F3/F4 drives FCS high; but no property gap available
        # → overlay stays off + BUBBLE_WARNING_INPUTS_UNAVAILABLE flag.
        _seed_f_rows(db_session, country="US", f1=85.0, f2=80.0, f3=75.0, f4=70.0)
        result = compute_fcs(db_session, "US", date(2024, 1, 31))
        assert result.score_0_100 > BUBBLE_WARNING_FCS_THRESHOLD
        assert result.bubble_warning_active == 0
        assert "BUBBLE_WARNING_INPUTS_UNAVAILABLE" in result.flags
