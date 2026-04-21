"""Tests for daily_overlays pipeline skeleton (week7 sprint C C1)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import Base, NSSYieldCurveSpot
from sonar.overlays.exceptions import InsufficientDataError
from sonar.pipelines.daily_overlays import (
    EXIT_CONVERGENCE,
    EXIT_DUPLICATE,
    EXIT_INSUFFICIENT_DATA,
    EXIT_IO,
    EXIT_OK,
    T1_7_COUNTRIES,
    OverlayBundle,
    StaticInputsBuilder,
    build_erp_us_bundle,
    build_expected_inflation_bundle,
    build_rating_bundle,
    build_sov_spread_crp_bundle,
    default_inputs_builder,
    nss_spot_exists,
    run_one,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_nss_spot(session: Session, country: str, obs_date: date) -> None:
    row = NSSYieldCurveSpot(
        country_code=country,
        date=obs_date,
        methodology_version="NSS_v1.0",
        fit_id="00000000-0000-0000-0000-000000000000",
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
    session.add(row)
    session.commit()


def test_exit_code_enum() -> None:
    assert EXIT_OK == 0
    assert EXIT_INSUFFICIENT_DATA == 1
    assert EXIT_CONVERGENCE == 2
    assert EXIT_DUPLICATE == 3
    assert EXIT_IO == 4


def test_t1_constant() -> None:
    assert T1_7_COUNTRIES == ("US", "DE", "PT", "IT", "ES", "FR", "NL")
    assert len(T1_7_COUNTRIES) == 7


def test_default_builder_returns_empty_bundle(session: Session) -> None:
    bundle = default_inputs_builder(session, "US", date(2024, 12, 31))
    assert isinstance(bundle, OverlayBundle)
    assert bundle.country_code == "US"
    assert bundle.erp is None
    assert bundle.crp is None
    assert bundle.rating is None
    assert bundle.expected_inflation is None


def test_nss_spot_exists_false_when_empty(session: Session) -> None:
    assert nss_spot_exists(session, "US", date(2024, 12, 31)) is False


def test_nss_spot_exists_true_after_seed(session: Session) -> None:
    _seed_nss_spot(session, "US", date(2024, 12, 31))
    assert nss_spot_exists(session, "US", date(2024, 12, 31)) is True


def test_run_one_requires_nss_by_default(session: Session) -> None:
    with pytest.raises(InsufficientDataError, match="yield_curves_spot missing"):
        run_one(session, "US", date(2024, 12, 31))


def test_run_one_skips_all_overlays_with_empty_bundle(session: Session) -> None:
    _seed_nss_spot(session, "US", date(2024, 12, 31))
    outcome = run_one(session, "US", date(2024, 12, 31))
    # Every overlay skipped because default bundle supplies no inputs.
    assert outcome.results.erp is None
    assert outcome.results.crp is None
    assert outcome.results.rating is None
    assert outcome.results.expected_inflation is None
    assert outcome.results.skips == {
        "erp": "no inputs provided",
        "crp": "no inputs provided",
        "rating": "no inputs provided",
        "expected_inflation": "no inputs provided",
    }
    assert outcome.persisted == {"erp": 0, "crp": 0, "rating": 0, "expected_inflation": 0}


def test_run_one_without_nss_precondition_works_for_tests(session: Session) -> None:
    """Unit-test path: ``require_nss=False`` bypasses the DAG gate."""
    outcome = run_one(session, "DE", date(2024, 12, 31), require_nss=False)
    assert outcome.country_code == "DE"
    assert outcome.persisted == {"erp": 0, "crp": 0, "rating": 0, "expected_inflation": 0}


# ---------------------------------------------------------------------------
# Per-overlay assemblers + StaticInputsBuilder (C2-C5)
# ---------------------------------------------------------------------------


ANCHOR = date(2024, 12, 31)


def _us_erp_bundle() -> OverlayBundle:
    erp_input = build_erp_us_bundle(
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
    return OverlayBundle(country_code="US", observation_date=ANCHOR, erp=erp_input)


def _pt_crp_bundle() -> OverlayBundle:
    crp_kwargs = build_sov_spread_crp_bundle(
        country_code="PT",
        observation_date=ANCHOR,
        sov_yield_country_pct=0.032,
        sov_yield_benchmark_pct=0.024,
        vol_ratio=1.23,
        vol_ratio_source="damodaran_standard",
    )
    return OverlayBundle(country_code="PT", observation_date=ANCHOR, crp=crp_kwargs)


def _us_rating_bundle() -> OverlayBundle:
    rating_kwargs = build_rating_bundle(
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
    return OverlayBundle(country_code="US", observation_date=ANCHOR, rating=rating_kwargs)


def _us_expinf_bundle() -> OverlayBundle:
    expinf_kwargs = build_expected_inflation_bundle(
        country_code="US",
        observation_date=ANCHOR,
        nominal_yields={
            "2Y": 0.041,
            "5Y": 0.040,
            "10Y": 0.043,
            "5y5y": 0.045,
        },
        linker_real_yields={
            "2Y": 0.018,
            "5Y": 0.017,
            "10Y": 0.019,
            "5y5y": 0.021,
        },
    )
    return OverlayBundle(
        country_code="US", observation_date=ANCHOR, expected_inflation=expinf_kwargs
    )


def test_build_erp_us_bundle_produces_erp_input() -> None:
    bundle = _us_erp_bundle()
    assert bundle.erp is not None
    assert bundle.erp.market_index == "SPX"
    assert bundle.erp.trailing_earnings == pytest.approx(221.41)
    assert bundle.erp.risk_free_confidence >= 0.50  # satisfies fit_erp_us precondition


def test_erp_helper_returns_fit_result(session: Session) -> None:
    _seed_nss_spot(session, "US", ANCHOR)
    builder = StaticInputsBuilder({"US": _us_erp_bundle()})
    outcome = run_one(session, "US", ANCHOR, inputs_builder=builder)
    assert outcome.results.erp is not None
    assert outcome.results.erp.canonical.methods_available == 4
    assert outcome.results.skips is not None
    assert "erp" not in outcome.results.skips


def test_crp_sov_spread_helper_returns_canonical(session: Session) -> None:
    _seed_nss_spot(session, "PT", ANCHOR)
    builder = StaticInputsBuilder({"PT": _pt_crp_bundle()})
    outcome = run_one(session, "PT", ANCHOR, inputs_builder=builder)
    assert outcome.results.crp is not None
    # PT on EUR: sov_spread = 320 bps raw; times 1.23 vol_ratio ~= 394 bps CRP.
    assert outcome.results.crp.method_selected == "SOV_SPREAD"
    assert outcome.results.crp.crp_canonical_bps > 0


def test_rating_helper_consolidates_3_agencies(session: Session) -> None:
    _seed_nss_spot(session, "US", ANCHOR)
    builder = StaticInputsBuilder({"US": _us_rating_bundle()})
    outcome = run_one(session, "US", ANCHOR, inputs_builder=builder)
    assert outcome.results.rating is not None
    assert outcome.results.rating.agencies_count == 3


def test_expected_inflation_helper_produces_index_result(session: Session) -> None:
    _seed_nss_spot(session, "US", ANCHOR)
    builder = StaticInputsBuilder({"US": _us_expinf_bundle()})
    outcome = run_one(session, "US", ANCHOR, inputs_builder=builder)
    assert outcome.results.expected_inflation is not None
    assert outcome.results.expected_inflation.index_code == "EXPINF_CANONICAL"
    assert outcome.results.expected_inflation.country_code == "US"
    # 10Y BEI = 0.043 - 0.019 = 0.024 → raw_value ≈ 0.024
    assert outcome.results.expected_inflation.raw_value == pytest.approx(0.024, abs=1e-6)


def test_all_four_overlays_compute_together(session: Session) -> None:
    _seed_nss_spot(session, "US", ANCHOR)
    erp = _us_erp_bundle().erp
    rating = _us_rating_bundle().rating
    expinf = _us_expinf_bundle().expected_inflation
    # CRP US is a benchmark — build a self-spread that collapses cleanly.
    crp = build_sov_spread_crp_bundle(
        country_code="US",
        observation_date=ANCHOR,
        sov_yield_country_pct=0.043,
        sov_yield_benchmark_pct=0.043,
        currency_denomination="USD",
    )
    composite = OverlayBundle(
        country_code="US",
        observation_date=ANCHOR,
        erp=erp,
        crp=crp,
        rating=rating,
        expected_inflation=expinf,
    )
    builder = StaticInputsBuilder({"US": composite})
    outcome = run_one(session, "US", ANCHOR, inputs_builder=builder)
    assert outcome.results.erp is not None
    assert outcome.results.crp is not None
    assert outcome.results.rating is not None
    assert outcome.results.expected_inflation is not None
    assert outcome.results.skips == {}


def test_static_builder_unknown_country_returns_empty() -> None:
    builder = StaticInputsBuilder({"US": _us_erp_bundle()})
    bundle = builder(session=None, country_code="XX", observation_date=ANCHOR)  # type: ignore[arg-type]
    assert bundle.erp is None
    assert bundle.crp is None
