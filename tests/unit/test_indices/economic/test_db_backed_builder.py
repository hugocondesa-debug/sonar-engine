"""Unit tests for :class:`EconomicDbBackedInputsBuilder` (CAL-108)."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import Base, NSSYieldCurveForwards, NSSYieldCurveSpot
from sonar.indices.economic.db_backed_builder import (
    EconomicDbBackedInputsBuilder,
    build_e2_inputs_from_db,
)

ANCHOR = date(2024, 12, 31)


# Import sonar.db.session so the connect-event listener enabling SQLite
# PRAGMA foreign_keys=ON is registered (same pattern as tests/unit/test_db/conftest.py).
import sonar.db.session  # noqa: F401, E402


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _make_fit_id(obs_date: date, country: str, suffix: str = "a") -> str:
    return f"{country:>2}{obs_date.isoformat().replace('-', '')}{suffix:>012}"[:36].ljust(36, "0")


def _spot_row(
    obs_date: date,
    *,
    country: str = "US",
    spot_2y: float = 0.0421,
    spot_10y: float = 0.0395,
    confidence: float = 0.9,
    flags: str | None = None,
    fit_suffix: str = "a",
) -> NSSYieldCurveSpot:
    fitted = {
        "1M": 0.0530,
        "3M": 0.0525,
        "6M": 0.0510,
        "1Y": 0.0475,
        "2Y": spot_2y,
        "3Y": 0.0410,
        "5Y": 0.0398,
        "7Y": 0.0396,
        "10Y": spot_10y,
        "15Y": 0.0400,
        "20Y": 0.0410,
        "30Y": 0.0412,
    }
    return NSSYieldCurveSpot(
        country_code=country,
        date=obs_date,
        methodology_version="NSS_v1.0",
        fit_id=_make_fit_id(obs_date, country, fit_suffix),
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
        confidence=confidence,
        flags=flags,
        source_connector="fred",
    )


def _forwards_row(
    obs_date: date,
    *,
    country: str = "US",
    forward_2y1y: float = 0.0380,
    forward_5y5y: float = 0.0410,
    fit_suffix: str = "a",
) -> NSSYieldCurveForwards:
    forwards = {
        "1y1y": 0.0430,
        "2y1y": forward_2y1y,
        "1y2y": 0.0420,
        "1y5y": 0.0400,
        "5y5y": forward_5y5y,
        "10y10y": 0.0415,
    }
    return NSSYieldCurveForwards(
        country_code=country,
        date=obs_date,
        methodology_version="NSS_v1.0",
        fit_id=_make_fit_id(obs_date, country, fit_suffix),
        forwards_json=json.dumps(forwards),
        breakeven_forwards_json=None,
        confidence=0.9,
        flags=None,
    )


def _seed_pair(session: Session, spot: NSSYieldCurveSpot, forwards: NSSYieldCurveForwards) -> None:
    """Seed spot + forwards respecting the FK from forwards.fit_id.

    SQLAlchemy's UoW doesn't guarantee spot lands before forwards
    within a single commit when SQLite ``PRAGMA foreign_keys=ON``
    is active (set globally by sonar.db.session's connect listener).
    Explicit flush between the two adds fixes it.
    """
    session.add(spot)
    session.flush()
    session.add(forwards)
    session.commit()


def test_builder_instantiation(session: Session) -> None:
    builder = EconomicDbBackedInputsBuilder(session)
    assert builder.session is session


def test_missing_spot_row_returns_none(session: Session) -> None:
    assert build_e2_inputs_from_db(session, "US", ANCHOR) is None


def test_low_confidence_spot_returns_none(session: Session) -> None:
    _seed_pair(session, _spot_row(ANCHOR, confidence=0.30), _forwards_row(ANCHOR))
    assert build_e2_inputs_from_db(session, "US", ANCHOR) is None


def test_missing_forwards_row_returns_none(session: Session) -> None:
    session.add(_spot_row(ANCHOR))
    session.commit()
    assert build_e2_inputs_from_db(session, "US", ANCHOR) is None


def test_happy_path_populates_inputs(session: Session) -> None:
    _seed_pair(session, _spot_row(ANCHOR), _forwards_row(ANCHOR))
    out = build_e2_inputs_from_db(session, "US", ANCHOR)
    assert out is not None
    assert out.country_code == "US"
    # 0.0421 decimal → 421 bps
    assert out.spot_2y_bps == pytest.approx(421.0)
    assert out.spot_10y_bps == pytest.approx(395.0)
    assert out.forward_2y1y_bps == pytest.approx(380.0)
    assert out.nss_confidence == pytest.approx(0.9)


def test_history_reconstructs_from_trailing_rows(session: Session) -> None:
    # Seed 4 prior dates plus the anchor; each with small yield drift.
    for i, delta_days in enumerate([90, 60, 30, 0]):
        prior = ANCHOR - timedelta(days=delta_days)
        suffix = f"h{i}"
        _seed_pair(
            session,
            _spot_row(
                prior,
                spot_2y=0.042 + i * 0.0005,
                spot_10y=0.0395 + i * 0.0003,
                fit_suffix=suffix,
            ),
            _forwards_row(prior, forward_2y1y=0.0380 + i * 0.0002, fit_suffix=suffix),
        )
    out = build_e2_inputs_from_db(session, "US", ANCHOR, history_days=120)
    assert out is not None
    # 4 spot rows → 4 slope points; 4 forwards rows → 4 forward-spread points.
    assert len(out.slope_history_bps) == 4
    assert len(out.forward_spread_history_bps) == 4


def test_missing_tenors_returns_none(session: Session) -> None:
    partial = NSSYieldCurveSpot(
        country_code="US",
        date=ANCHOR,
        methodology_version="NSS_v1.0",
        fit_id=_make_fit_id(ANCHOR, "US", "pt"),
        beta_0=0.04,
        beta_1=-0.01,
        beta_2=0.005,
        beta_3=None,
        lambda_1=1.5,
        lambda_2=None,
        # Only 1 tenor present → missing 2Y / 10Y
        fitted_yields_json=json.dumps({"5Y": 0.04}),
        observations_used=11,
        rmse_bps=5.0,
        xval_deviation_bps=None,
        confidence=0.9,
        flags=None,
        source_connector="fred",
    )
    _seed_pair(session, partial, _forwards_row(ANCHOR, fit_suffix="pt"))
    assert build_e2_inputs_from_db(session, "US", ANCHOR) is None


def test_flags_csv_is_parsed_into_tuple(session: Session) -> None:
    _seed_pair(
        session,
        _spot_row(ANCHOR, flags="XVAL_DRIFT,INSUFFICIENT_HISTORY"),
        _forwards_row(ANCHOR),
    )
    out = build_e2_inputs_from_db(session, "US", ANCHOR)
    assert out is not None
    assert out.nss_flags == ("XVAL_DRIFT", "INSUFFICIENT_HISTORY")


def test_malformed_fitted_yields_json_returns_none(session: Session) -> None:
    bad = _spot_row(ANCHOR)
    bad.fitted_yields_json = "{not valid json"
    _seed_pair(session, bad, _forwards_row(ANCHOR))
    assert build_e2_inputs_from_db(session, "US", ANCHOR) is None


def test_class_delegates_to_module_helper(session: Session) -> None:
    _seed_pair(session, _spot_row(ANCHOR), _forwards_row(ANCHOR))
    builder = EconomicDbBackedInputsBuilder(session)
    out = builder.build_e2_inputs("US", ANCHOR)
    assert out is not None
    assert out.spot_10y_bps == pytest.approx(395.0)
