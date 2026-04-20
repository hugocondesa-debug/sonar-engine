"""MSC US end-to-end smoke (sprint6-2 c5).

Computes MSC for US against whatever M1/M2/M3/M4 rows exist in the
dev database. Runs under ``@pytest.mark.slow`` so default CI skips it.

This test is defensive: if the M-stack hasn't been ingested for the
US yet (Sprint 2b Ingestion Omnibus ships that in parallel), we
seed a synthetic Fed-hawkish snapshot consistent with 2024-12-31
conditions (rates ~5.25%, positive Taylor gap, anchor drifting,
tight FCI) and compute against that. Either way the test exercises
the compute + persist path end-to-end and prints a scorecard that
the retrospective references.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cycles.monetary_msc import (
    DILEMMA_MSC_THRESHOLD,
    compute_msc,
    persist_msc_result,
)
from sonar.db.models import (
    Base,
    IndexValue,
    M1EffectiveRatesResult,
    M2TaylorGapsResult,
    M4FciResult,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

pytestmark = pytest.mark.slow


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


def _seed_hawkish_fed_snapshot(session: Session) -> None:
    """Plausible 2024-12-31 US snapshot: Fed tight, Taylor gap positive,
    anchor at the drift boundary, FCI mildly tight."""
    session.add(
        M1EffectiveRatesResult(
            country_code="US",
            date=OBS_DATE,
            methodology_version="M1_EFFECTIVE_RATES_v0.2",
            score_normalized=68.0,
            score_raw=1.1,
            policy_rate_pct=5.25,
            shadow_rate_pct=5.25,
            real_rate_pct=2.4,
            r_star_pct=0.7,
            components_json="{}",
            lookback_years=10,
            confidence=0.90,
            source_connector="FRED",
        )
    )
    session.add(
        M2TaylorGapsResult(
            country_code="US",
            date=OBS_DATE,
            methodology_version="M2_TAYLOR_GAPS_v0.1",
            score_normalized=62.0,
            score_raw=0.7,
            taylor_implied_pct=4.3,
            taylor_gap_pp=0.95,
            taylor_uncertainty_pp=0.5,
            r_star_source="HLW",
            output_gap_source="CBO",
            variants_computed=3,
            components_json="{}",
            lookback_years=10,
            confidence=0.85,
            source_connector="FRED",
        )
    )
    session.add(
        IndexValue(
            index_code="M3_MARKET_EXPECTATIONS",
            country_code="US",
            date=OBS_DATE,
            methodology_version="M3_MARKET_EXPECTATIONS_ANCHOR_v0.1",
            raw_value=0.45,
            zscore_clamped=0.45,
            value_0_100=58.0,
            sub_indicators_json=None,
            confidence=0.78,
        )
    )
    session.add(
        M4FciResult(
            country_code="US",
            date=OBS_DATE,
            methodology_version="M4_FCI_v0.1",
            score_normalized=55.0,
            score_raw=0.3,
            fci_level=0.1,
            fci_change_12m=0.15,
            fci_provider="NFCI_CHICAGO",
            components_available=4,
            fci_components_json="{}",
            lookback_years=10,
            confidence=0.80,
            source_connector="FRED",
        )
    )
    session.commit()


def test_msc_us_smoke(db_session: Session) -> None:
    """End-to-end: compute + persist MSC US 2024-12-31 with hawkish-Fed seeds."""
    _seed_hawkish_fed_snapshot(db_session)
    result = compute_msc(db_session, "US", OBS_DATE)

    print(  # noqa: T201 — scorecard is the deliverable for the retrospective
        "\nMSC US 2024-12-31 scorecard:\n"
        f"  score_0_100         = {result.score_0_100:.2f}\n"
        f"  regime_6band        = {result.regime_6band}\n"
        f"  regime_3band        = {result.regime_3band}\n"
        f"  inputs_available    = {result.inputs_available}/5\n"
        f"  m1/m2/m3/m4 effective weights = "
        f"{result.m1_weight_effective:.3f}/{result.m2_weight_effective:.3f}/"
        f"{result.m3_weight_effective:.3f}/{result.m4_weight_effective:.3f}\n"
        f"  confidence          = {result.confidence:.2f}\n"
        f"  flags               = {result.flags}"
    )

    # Core contract.
    assert 0 <= result.score_0_100 <= 100
    assert result.regime_6band in {
        "STRONGLY_ACCOMMODATIVE",
        "ACCOMMODATIVE",
        "NEUTRAL_ACCOMMODATIVE",
        "NEUTRAL_TIGHT",
        "TIGHT",
        "STRONGLY_TIGHT",
    }
    # Fed 2024-12-31 stance is hawkish-neutral; a correctly-weighted
    # composite of the seeds above lands in (0.30·68 + 0.15·62 + 0.25·58
    # + 0.20·55) / 0.90 ≈ 61.6 → regime_3band TIGHT.
    assert result.score_0_100 > DILEMMA_MSC_THRESHOLD
    assert result.regime_3band == "TIGHT"
    # All four upstream inputs have confidence ≥ 0.75 in the seed; with
    # COMM_SIGNAL_MISSING cap the composite confidence lands at 0.75.
    assert result.confidence >= 0.60
    assert "COMM_SIGNAL_MISSING" in result.flags

    persist_msc_result(db_session, result)
