"""MSC composite 7 T1 countries vertical-slice integration test (sprint6-2 c4).

Parametrized across the seven Tier-1 countries for a single
``observation_date = 2024-12-31``. Each country gets a synthetic
sub-index seed profile appropriate for its coverage tier:

- **US**: all 4 of (M1, M2, M3, M4) seeded → MSC computes.
- **EA (DE / IT / ES / FR / NL)**: M1 + M3 + M4 seeded → ≥ 3 inputs
  → MSC computes with M2_MISSING + COMM_SIGNAL_MISSING flags.
- **PT**: M3 only seeded → < MIN_INPUTS=3 → MSC raises.
- **UK / JP**: no rows seeded → raises.

Policy 1 edge cases (one seeding configuration per variant) live at
the bottom of the file. ≥ 12 integration assertions total across the
parametrized matrix + edge cases.
"""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cycles.base import InsufficientCycleInputsError
from sonar.cycles.monetary_msc import (
    MIN_INPUTS,
    compute_msc,
    persist_msc_result,
)
from sonar.db.models import (
    Base,
    IndexValue,
    M1EffectiveRatesResult,
    M2TaylorGapsResult,
    M4FciResult,
    MonetaryCycleScore,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


OBS_DATE = date(2024, 12, 31)


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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_m1(
    session: Session,
    country: str,
    *,
    score: float = 62.0,
    flags: str | None = None,
) -> None:
    session.add(
        M1EffectiveRatesResult(
            country_code=country,
            date=OBS_DATE,
            methodology_version="M1_EFFECTIVE_RATES_v0.2",
            score_normalized=score,
            score_raw=0.5,
            policy_rate_pct=5.25,
            shadow_rate_pct=5.25,
            real_rate_pct=2.3,
            r_star_pct=0.7,
            components_json="{}",
            lookback_years=10,
            confidence=0.85,
            flags=flags,
            source_connector="FRED",
        )
    )


def _seed_m2(
    session: Session,
    country: str,
    *,
    score: float = 54.0,
) -> None:
    session.add(
        M2TaylorGapsResult(
            country_code=country,
            date=OBS_DATE,
            methodology_version="M2_TAYLOR_GAPS_v0.1",
            score_normalized=score,
            score_raw=0.2,
            taylor_implied_pct=3.5,
            taylor_gap_pp=1.2,
            taylor_uncertainty_pp=0.5,
            r_star_source="HLW",
            output_gap_source="CBO",
            variants_computed=3,
            components_json="{}",
            lookback_years=10,
            confidence=0.82,
            source_connector="FRED",
        )
    )


def _seed_m3(
    session: Session,
    country: str,
    *,
    value_0_100: float = 45.0,
    anchor_status: str | None = None,
) -> None:
    sub = {"anchor_status": anchor_status} if anchor_status else None
    session.add(
        IndexValue(
            index_code="M3_MARKET_EXPECTATIONS",
            country_code=country,
            date=OBS_DATE,
            methodology_version="M3_MARKET_EXPECTATIONS_ANCHOR_v0.1",
            raw_value=0.3,
            zscore_clamped=0.3,
            value_0_100=value_0_100,
            sub_indicators_json=json.dumps(sub) if sub else None,
            confidence=0.80,
        )
    )


def _seed_m4(
    session: Session,
    country: str,
    *,
    score: float = 42.0,
) -> None:
    session.add(
        M4FciResult(
            country_code=country,
            date=OBS_DATE,
            methodology_version="M4_FCI_v0.1",
            score_normalized=score,
            score_raw=0.1,
            fci_level=-0.1,
            fci_change_12m=0.05,
            fci_provider="NFCI_CHICAGO",
            components_available=4,
            fci_components_json="{}",
            lookback_years=10,
            confidence=0.85,
            source_connector="FRED",
        )
    )


def _seed_country(session: Session, country: str) -> None:
    """Seed a per-country profile matching real Phase 0-1 coverage."""
    if country == "US":
        _seed_m1(session, country, score=62.0)
        _seed_m2(session, country, score=54.0)
        _seed_m3(session, country, value_0_100=45.0)
        _seed_m4(session, country, score=42.0)
    elif country in {"DE", "IT", "ES", "FR", "NL"}:
        # EA proxy (M1 via R_STAR_PROXY) + M3 + M4; M2 pending per sprint
        # 2b ingestion maturity.
        _seed_m1(session, country, score=58.0, flags="R_STAR_PROXY")
        _seed_m3(session, country, value_0_100=48.0)
        _seed_m4(session, country, score=46.0)
    elif country == "PT":
        # PT: only M3 available (real data — spec-intent partial coverage).
        _seed_m3(session, country, value_0_100=50.0)
    elif country in {"UK", "JP"}:
        # Connectors pending Week 7 → no rows.
        return
    session.commit()


# ---------------------------------------------------------------------------
# 7-country parametrized matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("country", "expected_persists", "expected_min_inputs"),
    [
        ("US", True, 4),
        ("DE", True, 3),
        ("IT", True, 3),
        ("ES", True, 3),
        ("FR", True, 3),
        ("NL", True, 3),
        ("PT", False, 0),
        ("UK", False, 0),
        ("JP", False, 0),
    ],
)
def test_msc_per_country(
    db_session: Session,
    country: str,
    expected_persists: bool,
    expected_min_inputs: int,
) -> None:
    _seed_country(db_session, country)
    if not expected_persists:
        with pytest.raises(InsufficientCycleInputsError):
            compute_msc(db_session, country, OBS_DATE)
        return

    result = compute_msc(db_session, country, OBS_DATE)
    assert result.inputs_available >= expected_min_inputs
    assert 0 <= result.score_0_100 <= 100
    assert result.regime_6band in {
        "STRONGLY_ACCOMMODATIVE",
        "ACCOMMODATIVE",
        "NEUTRAL_ACCOMMODATIVE",
        "NEUTRAL_TIGHT",
        "TIGHT",
        "STRONGLY_TIGHT",
    }
    assert result.regime_3band in {"ACCOMMODATIVE", "NEUTRAL", "TIGHT"}
    assert "COMM_SIGNAL_MISSING" in result.flags

    persist_msc_result(db_session, result)
    row = db_session.execute(
        select(MonetaryCycleScore).where(MonetaryCycleScore.country_code == country)
    ).scalar_one()
    assert row.score_0_100 == pytest.approx(result.score_0_100)


# ---------------------------------------------------------------------------
# Policy 1 edge cases
# ---------------------------------------------------------------------------


class TestPolicy1:
    def test_m2_missing_reweights_without_raising(self, db_session: Session) -> None:
        _seed_m1(db_session, "US", score=62.0)
        # M2 intentionally absent.
        _seed_m3(db_session, "US", value_0_100=45.0)
        _seed_m4(db_session, "US", score=42.0)
        db_session.commit()
        result = compute_msc(db_session, "US", OBS_DATE)
        assert result.inputs_available == 3
        assert "M2_MISSING" in result.flags
        assert "COMM_SIGNAL_MISSING" in result.flags
        # Weights re-normalised over M1+M3+M4 = 0.75 total.
        assert result.m2_weight_effective == 0.0
        assert result.m2_score_0_100 is None

    def test_two_inputs_raises(self, db_session: Session) -> None:
        _seed_m1(db_session, "US")
        _seed_m3(db_session, "US")
        db_session.commit()
        with pytest.raises(InsufficientCycleInputsError):
            compute_msc(db_session, "US", OBS_DATE)

    def test_min_inputs_constant_is_3(self) -> None:
        assert MIN_INPUTS == 3

    def test_confidence_capped_when_reweighted(self, db_session: Session) -> None:
        """Even with all high-confidence sub-inputs, re-weighting caps
        MSC confidence at 0.75 per spec §6 COMM_SIGNAL_MISSING row."""
        _seed_m1(db_session, "US", score=62.0)
        _seed_m2(db_session, "US", score=54.0)
        _seed_m3(db_session, "US", value_0_100=45.0)
        _seed_m4(db_session, "US", score=42.0)
        db_session.commit()
        result = compute_msc(db_session, "US", OBS_DATE)
        assert result.confidence <= 0.75

    def test_score_composite_is_canonical_weighted_sum_us(self, db_session: Session) -> None:
        """Manual sanity: m1=62, m2=54, m3=45, m4=42 + CS absent →
        (0.30·62 + 0.15·54 + 0.25·45 + 0.20·42) / 0.90 ≈ 49.28.
        """
        _seed_m1(db_session, "US", score=62.0)
        _seed_m2(db_session, "US", score=54.0)
        _seed_m3(db_session, "US", value_0_100=45.0)
        _seed_m4(db_session, "US", score=42.0)
        db_session.commit()
        result = compute_msc(db_session, "US", OBS_DATE)
        expected = (0.30 * 62 + 0.15 * 54 + 0.25 * 45 + 0.20 * 42) / 0.90
        assert result.score_0_100 == pytest.approx(expected, abs=0.01)
