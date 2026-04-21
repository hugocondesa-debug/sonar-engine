"""Integration smoke: E2 + M3 land via the DB-backed readers (CAL-108).

Seeds the same fixtures a production run would have persisted
(``yield_curves_spot`` + ``yield_curves_forwards`` from daily_curves +
``IndexValue(index_code='EXPINF_CANONICAL')`` from daily_overlays),
then exercises the DB-backed readers end-to-end. No connectors are
hit — these tests validate the reader → compute → persist chain.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import sonar.db.session  # noqa: F401 — activates the FK=ON connect listener
from sonar.db.models import (
    Base,
    IndexValue,
    NSSYieldCurveForwards,
    NSSYieldCurveSpot,
)
from sonar.indices.economic.db_backed_builder import EconomicDbBackedInputsBuilder
from sonar.indices.economic.e2_leading import compute_e2_leading_slope
from sonar.indices.monetary.db_backed_builder import (
    EXPINF_INDEX_CODE,
    MonetaryDbBackedInputsBuilder,
)
from sonar.indices.monetary.m3_market_expectations import (
    compute_m3_market_expectations_anchor,
)

pytestmark = pytest.mark.slow


ANCHOR = date(2024, 12, 31)


@pytest.fixture
def mem_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _fit_id(d: date, country: str, idx: int = 0) -> str:
    return f"{country:>2}{d.isoformat().replace('-', '')}{idx:>012}"[:36].ljust(36, "0")


def _seed_nss_pair(
    session: Session,
    obs_date: date,
    *,
    country: str = "US",
    spot_2y: float = 0.0421,
    spot_10y: float = 0.0395,
    forward_2y1y: float = 0.0380,
    forward_5y5y: float = 0.0410,
    idx: int = 0,
) -> None:
    fit_id = _fit_id(obs_date, country, idx)
    fitted = {
        "1M": 0.0530,
        "3M": 0.0525,
        "6M": 0.0510,
        "1Y": 0.0475,
        "2Y": spot_2y,
        "5Y": 0.0398,
        "10Y": spot_10y,
    }
    forwards = {
        "1y1y": 0.0430,
        "2y1y": forward_2y1y,
        "5y5y": forward_5y5y,
    }
    session.add(
        NSSYieldCurveSpot(
            country_code=country,
            date=obs_date,
            methodology_version="NSS_v1.0",
            fit_id=fit_id,
            beta_0=0.04,
            beta_1=-0.01,
            beta_2=0.005,
            beta_3=None,
            lambda_1=1.5,
            lambda_2=None,
            fitted_yields_json=json.dumps(fitted),
            observations_used=11,
            rmse_bps=5.0,
            xval_deviation_bps=None,
            confidence=0.9,
            flags=None,
            source_connector="fred",
        )
    )
    session.flush()
    session.add(
        NSSYieldCurveForwards(
            country_code=country,
            date=obs_date,
            methodology_version="NSS_v1.0",
            fit_id=fit_id,
            forwards_json=json.dumps(forwards),
            breakeven_forwards_json=None,
            confidence=0.9,
            flags=None,
        )
    )


def _seed_expinf(
    session: Session,
    obs_date: date,
    *,
    country: str = "US",
    be_5y5y: float = 0.0245,
    be_10y: float | None = 0.024,
    flags: str | None = None,
) -> None:
    tenors: dict[str, float] = {"5y5y": be_5y5y}
    if be_10y is not None:
        tenors["10Y"] = be_10y
    sub = {
        "expected_inflation_tenors": tenors,
        "source_method_per_tenor": dict.fromkeys(tenors, "BEI"),
        "methods_available": 1,
        "anchor_status": "well_anchored",
    }
    session.add(
        IndexValue(
            index_code=EXPINF_INDEX_CODE,
            country_code=country,
            date=obs_date,
            methodology_version="EXPINF_v1.0",
            raw_value=be_5y5y,
            zscore_clamped=0.0,
            value_0_100=50.0,
            sub_indicators_json=json.dumps(sub),
            confidence=0.85,
            flags=flags,
            source_overlays_json=json.dumps({}),
        )
    )


def _seed_full_upstream(
    session: Session,
    anchor: date,
    country: str,
    *,
    history_points: int = 4,
) -> None:
    """Seed NSS + forwards + EXPINF rows for the anchor plus a short history."""
    for i, delta_days in enumerate(reversed([0, 30, 60, 90][:history_points])):
        prior = anchor - timedelta(days=delta_days)
        _seed_nss_pair(
            session,
            prior,
            country=country,
            # Small drift so z-score history has variance.
            spot_2y=0.042 + i * 0.0003,
            spot_10y=0.040 - i * 0.0002,
            forward_2y1y=0.038 + i * 0.0002,
            forward_5y5y=0.041 - i * 0.0001,
            idx=i,
        )
        _seed_expinf(session, prior, country=country, be_5y5y=0.0245 + i * 0.0003)
    session.commit()


def test_e2_us_db_backed_end_to_end(mem_session: Session) -> None:
    _seed_full_upstream(mem_session, ANCHOR, "US")
    builder = EconomicDbBackedInputsBuilder(mem_session)
    inputs = builder.build_e2_inputs("US", ANCHOR)
    assert inputs is not None
    result = compute_e2_leading_slope(inputs)
    # Sanity: score stays in the canonical 0-100 band and methodology
    # version is the expected E2 v0.1 contract.
    assert 0.0 <= result.value_0_100 <= 100.0
    assert result.methodology_version.startswith("E2_LEADING")


def test_m3_us_db_backed_end_to_end(mem_session: Session) -> None:
    _seed_full_upstream(mem_session, ANCHOR, "US")
    builder = MonetaryDbBackedInputsBuilder(mem_session)
    inputs = builder.build_m3_inputs("US", ANCHOR)
    assert inputs is not None
    assert inputs.bc_target_bps == pytest.approx(200.0)  # Fed 2% target
    result = compute_m3_market_expectations_anchor(inputs)
    assert 0.0 <= result.value_0_100 <= 100.0
    assert result.methodology_version.startswith("M3_MARKET_EXPECTATIONS")


def test_m3_ea_db_backed_end_to_end(mem_session: Session) -> None:
    """EA partial coverage path: bc_target comes from ECB entry (2%)."""
    _seed_full_upstream(mem_session, ANCHOR, "EA")
    builder = MonetaryDbBackedInputsBuilder(mem_session)
    inputs = builder.build_m3_inputs("EA", ANCHOR)
    assert inputs is not None
    assert inputs.country_code == "EA"
    # ECB inflation target 2% → 200 bps.
    assert inputs.bc_target_bps == pytest.approx(200.0)
    result = compute_m3_market_expectations_anchor(inputs)
    assert 0.0 <= result.value_0_100 <= 100.0


def test_missing_upstream_yields_none(mem_session: Session) -> None:
    """Anchor date with no persisted rows → reader returns None for both."""
    econ = EconomicDbBackedInputsBuilder(mem_session).build_e2_inputs("US", ANCHOR)
    mon = MonetaryDbBackedInputsBuilder(mem_session).build_m3_inputs("US", ANCHOR)
    assert econ is None
    assert mon is None
