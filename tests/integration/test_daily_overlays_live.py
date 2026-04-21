"""Integration smoke for the daily_overlays pipeline (week7 sprint C C7).

These tests exercise the end-to-end orchestration in an in-memory
SQLite database using pre-assembled bundles (``StaticInputsBuilder``).
They verify that:

- The DAG precondition (NSS row present) is honoured.
- The 4 compute helpers fire concurrently and collate into
  :class:`OverlayResults`.
- :func:`persist_many_overlay_results` writes to the expected tables.
- Partial coverage (US benchmark / PT periphery / DE mid) degrades
  gracefully per brief §Commit 7.

Marked ``@pytest.mark.slow`` to stay aligned with the other live-smoke
integration modules (no external network in this sprint, but the
tests still exercise the full pipeline wiring so keeping them out of
the default CI run matches convention). ``FRED_API_KEY`` is not
required — these are pipeline-orchestration smokes, not connector
canaries.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import (
    Base,
    ERPCanonical,
    IndexValue,
    NSSYieldCurveSpot,
    RatingsConsolidated,
)
from sonar.pipelines.daily_overlays import (
    OverlayBundle,
    StaticInputsBuilder,
    build_erp_us_bundle,
    build_expected_inflation_bundle,
    build_rating_bundle,
    build_sov_spread_crp_bundle,
    run_one,
)

pytestmark = pytest.mark.slow


ANCHOR = date(2024, 12, 31)


@pytest.fixture
def mem_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_nss(session: Session, country: str, obs_date: date) -> None:
    session.add(
        NSSYieldCurveSpot(
            country_code=country,
            date=obs_date,
            methodology_version="NSS_v1.0",
            fit_id=f"11111111-1111-1111-1111-{country:<012}".replace(" ", "0")[:36],
            beta_0=0.04,
            beta_1=-0.01,
            beta_2=0.005,
            beta_3=None,
            lambda_1=1.5,
            lambda_2=None,
            fitted_yields_json='{"10Y": 0.04}',
            observations_used=11,
            rmse_bps=5.0,
            xval_deviation_bps=None,
            confidence=0.9,
            flags=None,
            source_connector="fred",
        )
    )
    session.commit()


def _us_bundle() -> OverlayBundle:
    erp = build_erp_us_bundle(
        observation_date=ANCHOR,
        index_level=4742.83,
        trailing_earnings=221.41,
        forward_earnings_est=243.73,
        dividend_yield_pct=0.0155,
        buyback_yield_pct=0.025,
        cape_ratio=31.5,
        risk_free_nominal=0.0415,
        risk_free_real=0.0175,
    )
    rating = build_rating_bundle(
        country_code="US",
        observation_date=ANCHOR,
        agency_ratings=[
            {
                "agency": "SP",
                "rating_raw": "AA+",
                "outlook": "stable",
                "watch": None,
                "action_date": ANCHOR,
            },
            {
                "agency": "MOODYS",
                "rating_raw": "Aaa",
                "outlook": "stable",
                "watch": None,
                "action_date": ANCHOR,
            },
            {
                "agency": "FITCH",
                "rating_raw": "AA+",
                "outlook": "stable",
                "watch": None,
                "action_date": ANCHOR,
            },
        ],
    )
    # US is the USD benchmark → build_canonical short-circuits to BENCHMARK.
    crp = build_sov_spread_crp_bundle(
        country_code="US",
        observation_date=ANCHOR,
        sov_yield_country_pct=0.043,
        sov_yield_benchmark_pct=0.043,
        currency_denomination="USD",
    )
    expinf = build_expected_inflation_bundle(
        country_code="US",
        observation_date=ANCHOR,
        nominal_yields={"2Y": 0.041, "5Y": 0.040, "10Y": 0.043, "5y5y": 0.045},
        linker_real_yields={"2Y": 0.018, "5Y": 0.017, "10Y": 0.019, "5y5y": 0.021},
    )
    return OverlayBundle(
        country_code="US",
        observation_date=ANCHOR,
        erp=erp,
        crp=crp,
        rating=rating,
        expected_inflation=expinf,
    )


def _de_bundle() -> OverlayBundle:
    # DE is the EUR benchmark → CRP short-circuits to BENCHMARK; rating DE AAA;
    # expected-inflation survey-only (no linker dict supplied → BEI absent).
    rating = build_rating_bundle(
        country_code="DE",
        observation_date=ANCHOR,
        agency_ratings=[
            {
                "agency": "SP",
                "rating_raw": "AAA",
                "outlook": "stable",
                "watch": None,
                "action_date": ANCHOR,
            },
            {
                "agency": "MOODYS",
                "rating_raw": "Aaa",
                "outlook": "stable",
                "watch": None,
                "action_date": ANCHOR,
            },
            {
                "agency": "FITCH",
                "rating_raw": "AAA",
                "outlook": "stable",
                "watch": None,
                "action_date": ANCHOR,
            },
        ],
    )
    crp = build_sov_spread_crp_bundle(
        country_code="DE",
        observation_date=ANCHOR,
        sov_yield_country_pct=0.023,
        sov_yield_benchmark_pct=0.023,
        currency_denomination="EUR",
    )
    expinf = build_expected_inflation_bundle(
        country_code="DE",
        observation_date=ANCHOR,
        nominal_yields={"10Y": 0.023, "5y5y": 0.025},
        survey_horizons={"10Y": 0.022, "5y5y": 0.020},
        survey_name="ECB_SPF",
        survey_release_date=ANCHOR,
    )
    return OverlayBundle(
        country_code="DE",
        observation_date=ANCHOR,
        erp=None,  # EA periphery proxies US ERP — follow-on CAL
        crp=crp,
        rating=rating,
        expected_inflation=expinf,
    )


def _pt_bundle() -> OverlayBundle:
    # PT: SOV_SPREAD against DE baseline + single-agency rating + DERIVED expinf.
    rating = build_rating_bundle(
        country_code="PT",
        observation_date=ANCHOR,
        agency_ratings=[
            {
                "agency": "SP",
                "rating_raw": "A-",
                "outlook": "stable",
                "watch": None,
                "action_date": ANCHOR,
            },
        ],
    )
    crp = build_sov_spread_crp_bundle(
        country_code="PT",
        observation_date=ANCHOR,
        sov_yield_country_pct=0.032,
        sov_yield_benchmark_pct=0.024,
        currency_denomination="EUR",
    )
    expinf = build_expected_inflation_bundle(
        country_code="PT",
        observation_date=ANCHOR,
        nominal_yields={"10Y": 0.032, "5y5y": 0.035},
        survey_horizons={"10Y": 0.025},
        survey_name="ECB_SPF",
        survey_release_date=ANCHOR,
    )
    return OverlayBundle(
        country_code="PT",
        observation_date=ANCHOR,
        erp=None,
        crp=crp,
        rating=rating,
        expected_inflation=expinf,
    )


def test_daily_overlays_us_end_to_end(mem_session: Session) -> None:
    _seed_nss(mem_session, "US", ANCHOR)
    builder = StaticInputsBuilder({"US": _us_bundle()})
    outcome = run_one(mem_session, "US", ANCHOR, inputs_builder=builder)

    assert outcome.persisted == {"erp": 1, "crp": 1, "rating": 1, "expected_inflation": 1}
    assert mem_session.query(ERPCanonical).count() == 1
    assert mem_session.query(RatingsConsolidated).count() == 1
    # CRP + expected-inflation both ride on the generic IndexValue table.
    assert mem_session.query(IndexValue).count() == 2
    assert outcome.results.crp is not None
    assert outcome.results.crp.method_selected == "BENCHMARK"
    assert outcome.results.expected_inflation is not None
    assert outcome.results.expected_inflation.raw_value == pytest.approx(0.024, abs=1e-6)


def test_daily_overlays_de_partial_coverage(mem_session: Session) -> None:
    _seed_nss(mem_session, "DE", ANCHOR)
    builder = StaticInputsBuilder({"DE": _de_bundle()})
    outcome = run_one(mem_session, "DE", ANCHOR, inputs_builder=builder)

    # ERP absent by design (EA ERP proxy not wired in this sprint).
    assert outcome.persisted["erp"] == 0
    assert outcome.results.skips is not None
    assert outcome.results.skips.get("erp") == "no inputs provided"
    # Other three land.
    assert outcome.persisted["crp"] == 1
    assert outcome.persisted["rating"] == 1
    assert outcome.persisted["expected_inflation"] == 1
    assert outcome.results.crp is not None
    assert outcome.results.crp.method_selected == "BENCHMARK"


def test_daily_overlays_pt_periphery(mem_session: Session) -> None:
    _seed_nss(mem_session, "PT", ANCHOR)
    builder = StaticInputsBuilder({"PT": _pt_bundle()})
    outcome = run_one(mem_session, "PT", ANCHOR, inputs_builder=builder)

    assert outcome.persisted["crp"] == 1
    assert outcome.persisted["rating"] == 1
    assert outcome.persisted["expected_inflation"] == 1
    assert outcome.results.crp is not None
    # PT is not a benchmark → should route through SOV_SPREAD.
    assert outcome.results.crp.method_selected == "SOV_SPREAD"
    assert outcome.results.crp.crp_canonical_bps > 0
    # Single-agency rating must surface the flag.
    assert outcome.results.rating is not None
    assert "RATING_SINGLE_AGENCY" in outcome.results.rating.flags
