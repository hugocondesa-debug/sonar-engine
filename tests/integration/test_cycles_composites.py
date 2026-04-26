"""Integration tests — CCCS + FCS 7 T1 vertical slice + smoke run.

Collapses brief §4 Commits 6, 7, and 8 into a single integration module:
CCCS multi-country, FCS multi-country, Policy 1 fail-mode, and a US
end-to-end smoke via the orchestrator.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cycles.base import InsufficientCycleInputsError
from sonar.cycles.credit_cccs import compute_cccs, persist_cccs_result
from sonar.cycles.financial_fcs import compute_fcs, persist_fcs_result
from sonar.cycles.orchestrator import compute_all_cycles
from sonar.db.models import (
    Base,
    CreditCycleScore,
    CreditGdpGap,
    CreditGdpStock,
    CreditImpulse,
    Dsr,
    E1Activity,
    E3Labor,
    E4Sentiment,
    IndexValue,
    M1EffectiveRatesResult,
    M2TaylorGapsResult,
    M4FciResult,
)
from tests.unit.test_cycles.test_credit_cccs import _seed_sub_rows as _seed_cccs_inputs
from tests.unit.test_cycles.test_financial_fcs import _seed_f_rows as _seed_fcs_inputs

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

T1_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")


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


def _seed_all(
    session: Session,
    country: str,
    observation_date: date = date(2024, 1, 31),
    *,
    include_f4: bool = True,
) -> None:
    """Seed CCCS + FCS + MSC + ECS upstream rows for the orchestrator smoke run.

    Covers the full input surface compute_all_cycles needs to land all
    four cycle composites (CCCS / FCS / MSC / ECS) without
    InsufficientCycleInputsError skips. Score values are mid-range
    (~50) and confidences ≥ 0.85 so every sub-index passes the
    composite gates.
    """
    _seed_cccs_inputs(
        session,
        country=country,
        observation_date=observation_date,
        margin_debt_pct=3.5 if include_f4 else None,
    )
    _seed_fcs_inputs(
        session,
        country=country,
        observation_date=observation_date,
        f3=None,
        f4=None,  # F4 reused from CCCS seed when include_f4=True
    )
    _seed_monetary_subindices(session, country=country, observation_date=observation_date)
    _seed_economic_subindices(session, country=country, observation_date=observation_date)


def _seed_monetary_subindices(
    session: Session,
    country: str,
    observation_date: date,
) -> None:
    """Seed M1 / M2 / M4 rows + M3 IndexValue (CS stays None per Phase 0-1)."""
    session.add_all(
        [
            M1EffectiveRatesResult(
                country_code=country,
                date=observation_date,
                methodology_version="M1_EFFECTIVE_RATES_v0.1",
                score_normalized=50.0,
                score_raw=0.0,
                policy_rate_pct=0.05,
                shadow_rate_pct=0.05,
                real_rate_pct=0.02,
                r_star_pct=0.005,
                components_json="{}",
                lookback_years=20,
                confidence=0.9,
                source_connector="fred",
            ),
            M2TaylorGapsResult(
                country_code=country,
                date=observation_date,
                methodology_version="M2_TAYLOR_GAPS_v0.1",
                score_normalized=50.0,
                score_raw=0.0,
                taylor_implied_pct=0.05,
                taylor_gap_pp=0.0,
                taylor_uncertainty_pp=0.5,
                r_star_source="HLW",
                output_gap_source="OECD",
                variants_computed=2,
                components_json="{}",
                lookback_years=20,
                confidence=0.85,
                source_connector="fred",
            ),
            M4FciResult(
                country_code=country,
                date=observation_date,
                methodology_version="M4_FCI_v0.1",
                score_normalized=50.0,
                score_raw=0.0,
                fci_level=0.0,
                fci_change_12m=0.0,
                fci_provider="NFCI_CHICAGO",
                components_available=5,
                fci_components_json="{}",
                lookback_years=20,
                confidence=0.9,
                source_connector="fred",
            ),
            IndexValue(
                index_code="M3_MARKET_EXPECTATIONS",
                country_code=country,
                date=observation_date,
                methodology_version="M3_MARKET_EXPECTATIONS_v0.1",
                raw_value=0.0,
                zscore_clamped=0.0,
                value_0_100=50.0,
                sub_indicators_json=None,
                confidence=0.85,
            ),
        ]
    )
    session.commit()


def _seed_economic_subindices(
    session: Session,
    country: str,
    observation_date: date,
) -> None:
    """Seed E1 / E3 / E4 rows + E2 IndexValue per ECS reader contract."""
    session.add_all(
        [
            E1Activity(
                country_code=country,
                date=observation_date,
                methodology_version="E1_ACTIVITY_v0.1",
                score_normalized=50.0,
                score_raw=0.0,
                components_json="{}",
                components_available=5,
                lookback_years=20,
                confidence=0.85,
                source_connectors="fred",
            ),
            E3Labor(
                country_code=country,
                date=observation_date,
                methodology_version="E3_LABOR_v0.1",
                score_normalized=50.0,
                score_raw=0.0,
                sahm_triggered=0,
                sahm_value=0.0,
                components_json="{}",
                components_available=7,
                lookback_years=20,
                confidence=0.85,
                source_connectors="fred",
            ),
            E4Sentiment(
                country_code=country,
                date=observation_date,
                methodology_version="E4_SENTIMENT_v0.1",
                score_normalized=50.0,
                score_raw=0.0,
                components_json="{}",
                components_available=8,
                lookback_years=20,
                confidence=0.85,
                source_connectors="fred",
            ),
            IndexValue(
                index_code="E2_LEADING",
                country_code=country,
                date=observation_date,
                methodology_version="E2_LEADING_v0.1",
                raw_value=0.0,
                zscore_clamped=0.0,
                value_0_100=50.0,
                sub_indicators_json=None,
                confidence=0.85,
            ),
        ]
    )
    session.commit()


class TestCCCS7T1:
    @pytest.mark.parametrize("country", T1_COUNTRIES)
    def test_each_country_persists(self, db_session: Session, country: str) -> None:
        _seed_cccs_inputs(db_session, country=country, observation_date=date(2024, 1, 31))
        result = compute_cccs(db_session, country, date(2024, 1, 31))
        persist_cccs_result(db_session, result)
        assert 0 <= result.score_0_100 <= 100
        assert result.regime in {"REPAIR", "RECOVERY", "BOOM", "SPECULATION", "DISTRESS"}

    def test_seven_countries_all_persist(self, db_session: Session) -> None:
        for country in T1_COUNTRIES:
            _seed_cccs_inputs(db_session, country=country, observation_date=date(2024, 1, 31))
            result = compute_cccs(db_session, country, date(2024, 1, 31))
            persist_cccs_result(db_session, result)
        rows = db_session.execute(select(CreditCycleScore)).scalars().all()
        assert len(rows) == 7
        assert {r.country_code for r in rows} == set(T1_COUNTRIES)

    def test_policy_1_raises_when_below_min(self, db_session: Session) -> None:
        # Spec §6: CCCS requires >= 3 of CS/LC/MS. With F3 missing MS is
        # uncomputable, leaving CS + LC = 2 → below min, raise.
        session = db_session
        d = date(2024, 1, 31)
        # Hand-seed L1-L4 only (no F3) so MS is uncomputable.
        session.add_all(
            [
                CreditGdpStock(
                    country_code="US",
                    date=d,
                    methodology_version="L1_CREDIT_GDP_STOCK_v0.1",
                    score_normalized=0.2,
                    score_raw=150.0,
                    components_json="{}",
                    series_variant="Q",
                    gdp_vintage_mode="production",
                    lookback_years=20,
                    confidence=0.9,
                    source_connector="bis",
                ),
                CreditGdpGap(
                    country_code="US",
                    date=d,
                    methodology_version="L2_CREDIT_GDP_GAP_v0.1",
                    score_normalized=0.3,
                    score_raw=3.5,
                    gap_hp_pp=3.5,
                    gap_hamilton_pp=3.0,
                    trend_gdp_pct=2.0,
                    hp_lambda=400000,
                    hamilton_horizon_q=8,
                    concordance="both_above",
                    phase_band="neutral",
                    components_json="{}",
                    lookback_years=20,
                    confidence=0.9,
                    source_connector="bis",
                ),
                CreditImpulse(
                    country_code="US",
                    date=d,
                    methodology_version="L3_CREDIT_IMPULSE_v0.1",
                    score_normalized=0.1,
                    score_raw=1.5,
                    impulse_pp=1.5,
                    flow_t_lcu=1000.0,
                    flow_t_minus4_lcu=900.0,
                    delta_flow_lcu=100.0,
                    gdp_t_minus4_lcu=50000.0,
                    state="expansion",
                    series_variant="Q",
                    smoothing="raw",
                    components_json="{}",
                    lookback_years=20,
                    segment="PNFS",
                    confidence=0.85,
                    source_connector="bis",
                ),
                Dsr(
                    country_code="US",
                    date=d,
                    methodology_version="L4_DSR_v0.1",
                    score_normalized=-0.1,
                    score_raw=14.5,
                    dsr_pct=14.5,
                    dsr_deviation_pp=0.5,
                    lending_rate_pct=0.04,
                    avg_maturity_years=8.0,
                    debt_to_gdp_ratio=1.5,
                    annuity_factor=0.07,
                    formula_mode="full",
                    band="baseline",
                    denominator="GDP_4Q_sum",
                    segment="PNFS",
                    components_json="{}",
                    lookback_years=20,
                    confidence=0.9,
                    source_connector="bis",
                ),
            ]
        )
        session.commit()

        with pytest.raises(InsufficientCycleInputsError, match=">= 3"):
            compute_cccs(session, "US", d)


class TestFCS7T1:
    @pytest.mark.parametrize("country", T1_COUNTRIES)
    def test_each_country_persists(self, db_session: Session, country: str) -> None:
        _seed_fcs_inputs(db_session, country=country, observation_date=date(2024, 1, 31))
        result = compute_fcs(db_session, country, date(2024, 1, 31))
        persist_fcs_result(db_session, result)
        assert 0 <= result.score_0_100 <= 100
        assert result.regime in {"STRESS", "CAUTION", "OPTIMISM", "EUPHORIA"}

    def test_t1_strict_degraded_f4_raises(self, db_session: Session) -> None:
        """US is T1-strict per spec — F4 missing forces raise."""
        _seed_fcs_inputs(db_session, country="US", observation_date=date(2024, 1, 31), f4=None)
        with pytest.raises(InsufficientCycleInputsError, match="Tier-1"):
            compute_fcs(db_session, "US", date(2024, 1, 31))

    def test_t3_country_degrades_with_flag(self, db_session: Session) -> None:
        _seed_fcs_inputs(db_session, country="PT", observation_date=date(2024, 1, 31), f4=None)
        result = compute_fcs(db_session, "PT", date(2024, 1, 31))
        assert "F4_COVERAGE_SPARSE" in result.flags
        assert result.country_tier == 3


class TestOrchestratorSmoke:
    def test_us_smoke_end_to_end(self, db_session: Session) -> None:
        """US full-stack via orchestrator — persists both rows."""
        _seed_all(db_session, "US", date(2024, 1, 31))
        outcome = compute_all_cycles(db_session, "US", date(2024, 1, 31))
        assert outcome.cccs is not None
        assert outcome.fcs is not None
        assert outcome.skips == {}
        # Confidence check: at least above 0.4 baseline given mostly synthetic
        # but well-formed fixture inputs.
        assert outcome.cccs.confidence > 0.4
        assert outcome.fcs.confidence > 0.4
