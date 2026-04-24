"""Unit tests for :class:`MonetaryDbBackedInputsBuilder` (CAL-108 part 2)."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Import sonar.db.session so the connect-event listener enabling
# SQLite PRAGMA foreign_keys=ON is registered (parity with
# tests/unit/test_db/conftest.py).
import sonar.db.session  # noqa: F401
from sonar.db.models import (
    Base,
    ExpInflationSurveyRow,
    IndexValue,
    NSSYieldCurveForwards,
    NSSYieldCurveSpot,
)
from sonar.indices.monetary.db_backed_builder import (
    EXPINF_INDEX_CODE,
    M3_EXPINF_FROM_SURVEY_FLAG,
    MonetaryDbBackedInputsBuilder,
    build_m3_inputs_from_db,
)

ANCHOR = date(2024, 12, 31)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _make_fit_id(obs_date: date, country: str, suffix: str = "a") -> str:
    return f"{country:>2}{obs_date.isoformat().replace('-', '')}{suffix:>012}"[:36].ljust(36, "0")


def _forwards_with_spot(
    session: Session,
    obs_date: date,
    *,
    country: str = "US",
    forward_5y5y: float = 0.0410,
    fit_suffix: str = "a",
) -> None:
    """Seed a NSS spot row + forwards row with the same fit_id (FK-safe)."""
    fit_id = _make_fit_id(obs_date, country, fit_suffix)
    spot = NSSYieldCurveSpot(
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
        fitted_yields_json=json.dumps({"10Y": 0.04}),
        observations_used=11,
        rmse_bps=5.0,
        xval_deviation_bps=None,
        confidence=0.9,
        flags=None,
        source_connector="fred",
    )
    forwards = NSSYieldCurveForwards(
        country_code=country,
        date=obs_date,
        methodology_version="NSS_v1.0",
        fit_id=fit_id,
        forwards_json=json.dumps(
            {
                "1y1y": 0.0430,
                "2y1y": 0.0380,
                "5y5y": forward_5y5y,
            }
        ),
        breakeven_forwards_json=None,
        confidence=0.9,
        flags=None,
    )
    session.add(spot)
    session.flush()
    session.add(forwards)


def _expinf_row(
    obs_date: date,
    *,
    country: str = "US",
    be_5y5y: float = 0.0245,
    be_10y: float | None = 0.024,
    flags: str | None = None,
    confidence: float = 0.85,
) -> IndexValue:
    tenors: dict[str, float] = {"5y5y": be_5y5y}
    if be_10y is not None:
        tenors["10Y"] = be_10y
    sub = {
        "expected_inflation_tenors": tenors,
        "source_method_per_tenor": dict.fromkeys(tenors, "BEI"),
        "methods_available": 1,
        "anchor_status": "well_anchored",
    }
    return IndexValue(
        index_code=EXPINF_INDEX_CODE,
        country_code=country,
        date=obs_date,
        methodology_version="EXPINF_v1.0",
        raw_value=be_5y5y,
        zscore_clamped=0.0,
        value_0_100=50.0,
        sub_indicators_json=json.dumps(sub),
        confidence=confidence,
        flags=flags,
        source_overlays_json=json.dumps({}),
    )


def test_builder_instantiation(session: Session) -> None:
    builder = MonetaryDbBackedInputsBuilder(session)
    assert builder.session is session


def test_missing_forwards_returns_none(session: Session) -> None:
    assert build_m3_inputs_from_db(session, "US", ANCHOR) is None


def test_missing_expinf_returns_none(session: Session) -> None:
    _forwards_with_spot(session, ANCHOR)
    session.commit()
    assert build_m3_inputs_from_db(session, "US", ANCHOR) is None


def test_expinf_missing_5y5y_returns_none(session: Session) -> None:
    _forwards_with_spot(session, ANCHOR)
    # Build EXPINF row without the 5y5y tenor.
    sub = {"expected_inflation_tenors": {"10Y": 0.024}, "methods_available": 1}
    session.add(
        IndexValue(
            index_code=EXPINF_INDEX_CODE,
            country_code="US",
            date=ANCHOR,
            methodology_version="EXPINF_v1.0",
            raw_value=0.024,
            zscore_clamped=0.0,
            value_0_100=50.0,
            sub_indicators_json=json.dumps(sub),
            confidence=0.85,
            flags=None,
            source_overlays_json=json.dumps({}),
        )
    )
    session.commit()
    assert build_m3_inputs_from_db(session, "US", ANCHOR) is None


def test_happy_path_populates_m3_inputs(session: Session) -> None:
    _forwards_with_spot(session, ANCHOR)
    session.add(_expinf_row(ANCHOR))
    session.commit()
    out = build_m3_inputs_from_db(session, "US", ANCHOR)
    assert out is not None
    assert out.country_code == "US"
    # 0.0410 decimal → 410 bps
    assert out.nominal_5y5y_bps == pytest.approx(410.0)
    # 0.0245 decimal → 245 bps
    assert out.breakeven_5y5y_bps == pytest.approx(245.0)
    # US inflation target 2% → 200 bps per bc_targets.yaml Fed entry
    assert out.bc_target_bps == pytest.approx(200.0)
    # 10Y tenor available → bei_10y_bps populated
    assert out.bei_10y_bps == pytest.approx(240.0)
    assert out.survey_10y_bps is None  # no BEI/SURVEY split in current sub_indicators
    assert out.expinf_confidence == pytest.approx(0.85)


def test_no_10y_tenor_leaves_bei_and_survey_none(session: Session) -> None:
    _forwards_with_spot(session, ANCHOR)
    session.add(_expinf_row(ANCHOR, be_10y=None))
    session.commit()
    out = build_m3_inputs_from_db(session, "US", ANCHOR)
    assert out is not None
    assert out.bei_10y_bps is None
    assert out.survey_10y_bps is None


def test_flags_csv_parsed_into_tuple(session: Session) -> None:
    _forwards_with_spot(session, ANCHOR)
    session.add(_expinf_row(ANCHOR, flags="ANCHOR_UNCOMPUTABLE,NO_TARGET"))
    session.commit()
    out = build_m3_inputs_from_db(session, "US", ANCHOR)
    assert out is not None
    assert out.expinf_flags == ("ANCHOR_UNCOMPUTABLE", "NO_TARGET")


def test_unknown_country_leaves_bc_target_none(session: Session) -> None:
    # Seed forwards + expinf under a country code that has no bc_target entry.
    _forwards_with_spot(session, ANCHOR, country="XX")
    session.add(_expinf_row(ANCHOR, country="XX"))
    session.commit()
    out = build_m3_inputs_from_db(session, "XX", ANCHOR)
    assert out is not None
    assert out.bc_target_bps is None


def test_history_reconstructs_from_paired_rows(session: Session) -> None:
    # Seed 3 prior dates with forwards + expinf rows plus the anchor.
    for i, delta_days in enumerate([90, 60, 30, 0]):
        prior = ANCHOR - timedelta(days=delta_days)
        _forwards_with_spot(session, prior, forward_5y5y=0.040 + i * 0.0005, fit_suffix=f"h{i}")
        session.add(_expinf_row(prior, be_5y5y=0.024 + i * 0.0002))
    session.commit()
    out = build_m3_inputs_from_db(session, "US", ANCHOR, history_days=120)
    assert out is not None
    # 4 forwards rows → 4 nominal history points.
    assert len(out.nominal_5y5y_history_bps) == 4
    # 4 paired expinf rows with bc_target → 4 anchor deviation points.
    assert len(out.anchor_deviation_abs_history_bps) == 4


def test_class_delegates_to_module_helper(session: Session) -> None:
    _forwards_with_spot(session, ANCHOR)
    session.add(_expinf_row(ANCHOR))
    session.commit()
    builder = MonetaryDbBackedInputsBuilder(session)
    out = builder.build_m3_inputs("US", ANCHOR)
    assert out is not None
    assert out.nominal_5y5y_bps == pytest.approx(410.0)


def test_malformed_sub_indicators_returns_none(session: Session) -> None:
    _forwards_with_spot(session, ANCHOR)
    session.add(
        IndexValue(
            index_code=EXPINF_INDEX_CODE,
            country_code="US",
            date=ANCHOR,
            methodology_version="EXPINF_v1.0",
            raw_value=0.024,
            zscore_clamped=0.0,
            value_0_100=50.0,
            sub_indicators_json="{not valid",
            confidence=0.85,
            flags=None,
            source_overlays_json=json.dumps({}),
        )
    )
    session.commit()
    # Malformed JSON yields empty tenors → breakeven_5y5y_bps missing → None.
    assert build_m3_inputs_from_db(session, "US", ANCHOR) is None


# ---------------------------------------------------------------------------
# CAL-113 (Sprint M) — BEI/SURVEY split consumer
# ---------------------------------------------------------------------------


def _expinf_row_with_split(
    obs_date: date,
    *,
    country: str = "US",
    bei_10y: float | None = 0.024,
    survey_10y: float | None = 0.027,
) -> IndexValue:
    """EXPINF row with bei_tenors + survey_tenors keys (Sprint M emitter)."""
    unified: dict[str, float] = {"5y5y": 0.0245}
    bei_tenors: dict[str, float] = {}
    survey_tenors: dict[str, float] = {}
    if bei_10y is not None:
        unified["10Y"] = bei_10y
        bei_tenors["10Y"] = bei_10y
    if survey_10y is not None:
        # Survey typically sourced distinct from BEI — emit under 10Y too.
        unified.setdefault("10Y", survey_10y)
        survey_tenors["10Y"] = survey_10y
    method_per_tenor = {
        **dict.fromkeys(bei_tenors, "BEI"),
        **dict.fromkeys(survey_tenors, "SURVEY"),
    }
    sub = {
        "expected_inflation_tenors": unified,
        "bei_tenors": bei_tenors,
        "survey_tenors": survey_tenors,
        "method_per_tenor": method_per_tenor,
        "methods_available": 2 if bei_tenors and survey_tenors else 1,
        "anchor_status": "well_anchored",
    }
    return IndexValue(
        index_code=EXPINF_INDEX_CODE,
        country_code=country,
        date=obs_date,
        methodology_version="EXPINF_v1.0",
        raw_value=0.0245,
        zscore_clamped=0.0,
        value_0_100=50.0,
        sub_indicators_json=json.dumps(sub),
        confidence=0.85,
        flags=None,
        source_overlays_json=json.dumps({}),
    )


def test_bei_only_split_populates_bei_leaves_survey_none(session: Session) -> None:
    _forwards_with_spot(session, ANCHOR)
    session.add(_expinf_row_with_split(ANCHOR, bei_10y=0.024, survey_10y=None))
    session.commit()
    out = build_m3_inputs_from_db(session, "US", ANCHOR)
    assert out is not None
    assert out.bei_10y_bps == pytest.approx(240.0)
    assert out.survey_10y_bps is None


def test_survey_only_split_populates_survey_leaves_bei_none(session: Session) -> None:
    _forwards_with_spot(session, ANCHOR)
    session.add(_expinf_row_with_split(ANCHOR, bei_10y=None, survey_10y=0.027))
    session.commit()
    out = build_m3_inputs_from_db(session, "US", ANCHOR)
    assert out is not None
    assert out.bei_10y_bps is None
    assert out.survey_10y_bps == pytest.approx(270.0)


def test_both_split_populate_distinctly(session: Session) -> None:
    _forwards_with_spot(session, ANCHOR)
    session.add(_expinf_row_with_split(ANCHOR, bei_10y=0.024, survey_10y=0.027))
    session.commit()
    out = build_m3_inputs_from_db(session, "US", ANCHOR)
    assert out is not None
    assert out.bei_10y_bps == pytest.approx(240.0)
    assert out.survey_10y_bps == pytest.approx(270.0)


def test_legacy_row_without_split_preserves_existing_behaviour(session: Session) -> None:
    """Pre-Sprint-M rows (no bei_tenors / survey_tenors) → survey stays None."""
    _forwards_with_spot(session, ANCHOR)
    session.add(_expinf_row(ANCHOR))  # legacy fixture helper, no split keys
    session.commit()
    out = build_m3_inputs_from_db(session, "US", ANCHOR)
    assert out is not None
    assert out.bei_10y_bps == pytest.approx(240.0)
    assert out.survey_10y_bps is None


# ---------------------------------------------------------------------------
# Sprint Q.1.1 — survey table fallback
# ---------------------------------------------------------------------------


def _survey_row(
    obs_date: date,
    *,
    country: str = "EA",
    be_5y5y: float = 0.0202,
    be_10y: float | None = 0.0202,
    flags: str | None = "SPF_LT_AS_ANCHOR",
    confidence: float = 1.0,
    survey_name: str = "ECB_SPF_HICP",
) -> ExpInflationSurveyRow:
    """Factory: survey row matching the Sprint Q.1 writer shape."""
    tenors: dict[str, float] = {"5y5y": be_5y5y, "5Y": be_5y5y, "1Y": 0.0197, "2Y": 0.0205}
    if be_10y is not None:
        tenors["10Y"] = be_10y
        tenors["30Y"] = be_10y
    return ExpInflationSurveyRow(
        exp_inf_id=f"{country}-{obs_date.isoformat()}-spf",
        country_code=country,
        date=obs_date,
        methodology_version="EXPINF_SURVEY_v1.0",
        confidence=confidence,
        flags=flags,
        survey_name=survey_name,
        survey_release_date=obs_date,
        horizons_json=json.dumps({"1Y": 0.0197, "2Y": 0.0205, "LTE": be_5y5y}),
        interpolated_tenors_json=json.dumps(tenors),
    )


def test_survey_fallback_canonical_primary(session: Session) -> None:
    """Sprint Q.1.1: canonical IndexValue takes priority over survey row."""
    _forwards_with_spot(session, ANCHOR, country="EA")
    # Populate BOTH canonical + survey for EA
    session.add(_expinf_row(ANCHOR, country="EA", be_5y5y=0.0245, be_10y=0.024))
    session.add(_survey_row(ANCHOR, country="EA", be_5y5y=0.02))
    session.commit()

    out = build_m3_inputs_from_db(session, "EA", ANCHOR)
    assert out is not None
    # Canonical 5y5y=245bps wins, not survey 200bps.
    assert out.breakeven_5y5y_bps == pytest.approx(245.0)
    assert M3_EXPINF_FROM_SURVEY_FLAG not in out.expinf_flags


def test_survey_fallback_activates_when_canonical_empty(session: Session) -> None:
    """Sprint Q.1.1: survey row serves M3Inputs when IndexValue absent."""
    _forwards_with_spot(session, ANCHOR, country="EA")
    session.add(_survey_row(ANCHOR, country="EA", be_5y5y=0.0202, be_10y=0.0202))
    session.commit()

    out = build_m3_inputs_from_db(session, "EA", ANCHOR)
    assert out is not None
    # 0.0202 decimal → 202bps
    assert out.breakeven_5y5y_bps == pytest.approx(202.0)
    # Survey path: 10Y populates survey_10y_bps (not bei_10y_bps)
    assert out.survey_10y_bps == pytest.approx(202.0)
    assert out.bei_10y_bps is None
    assert M3_EXPINF_FROM_SURVEY_FLAG in out.expinf_flags
    assert "SPF_LT_AS_ANCHOR" in out.expinf_flags
    assert out.expinf_confidence == pytest.approx(1.0)


def test_survey_fallback_preserves_area_proxy_flag(session: Session) -> None:
    """Sprint Q.1.1: AREA_PROXY flag from survey row is propagated verbatim."""
    _forwards_with_spot(session, ANCHOR, country="DE")
    session.add(
        _survey_row(
            ANCHOR,
            country="DE",
            flags="SPF_LT_AS_ANCHOR,SPF_AREA_PROXY",
        )
    )
    session.commit()

    out = build_m3_inputs_from_db(session, "DE", ANCHOR)
    assert out is not None
    assert "SPF_LT_AS_ANCHOR" in out.expinf_flags
    assert "SPF_AREA_PROXY" in out.expinf_flags
    assert M3_EXPINF_FROM_SURVEY_FLAG in out.expinf_flags


def test_survey_fallback_picks_most_recent_on_or_before(session: Session) -> None:
    """Sprint Q.1.1: sparse survey releases → pick most recent ≤ observation_date."""
    _forwards_with_spot(session, ANCHOR, country="EA")
    # Two survey rows: one from 60d earlier, one at anchor.
    session.add(_survey_row(ANCHOR - timedelta(days=60), country="EA", be_5y5y=0.019))
    session.add(_survey_row(ANCHOR, country="EA", be_5y5y=0.021))
    session.commit()

    out = build_m3_inputs_from_db(session, "EA", ANCHOR)
    assert out is not None
    # Most recent (anchor date, 0.021) wins.
    assert out.breakeven_5y5y_bps == pytest.approx(210.0)


def test_survey_fallback_no_data_returns_none(session: Session) -> None:
    """Sprint Q.1.1: neither canonical nor survey → None (M3_EXPINF_MISSING path)."""
    _forwards_with_spot(session, ANCHOR, country="EA")
    session.commit()
    assert build_m3_inputs_from_db(session, "EA", ANCHOR) is None


def test_survey_fallback_missing_5y5y_tenor_returns_none(session: Session) -> None:
    """Sprint Q.1.1: survey row without 5y5y key is unusable → None."""
    _forwards_with_spot(session, ANCHOR, country="EA")
    session.add(
        ExpInflationSurveyRow(
            exp_inf_id="ea-no-5y5y",
            country_code="EA",
            date=ANCHOR,
            methodology_version="EXPINF_SURVEY_v1.0",
            confidence=1.0,
            flags="SPF_LT_AS_ANCHOR",
            survey_name="ECB_SPF_HICP",
            survey_release_date=ANCHOR,
            horizons_json=json.dumps({}),
            interpolated_tenors_json=json.dumps({"10Y": 0.02}),
        )
    )
    session.commit()
    assert build_m3_inputs_from_db(session, "EA", ANCHOR) is None


def test_survey_fallback_malformed_json_returns_none(session: Session) -> None:
    """Sprint Q.1.1: malformed interpolated_tenors_json → unusable → None."""
    _forwards_with_spot(session, ANCHOR, country="EA")
    session.add(
        ExpInflationSurveyRow(
            exp_inf_id="ea-bad-json",
            country_code="EA",
            date=ANCHOR,
            methodology_version="EXPINF_SURVEY_v1.0",
            confidence=1.0,
            flags="SPF_LT_AS_ANCHOR",
            survey_name="ECB_SPF_HICP",
            survey_release_date=ANCHOR,
            horizons_json=json.dumps({}),
            interpolated_tenors_json="{not valid json",
        )
    )
    session.commit()
    assert build_m3_inputs_from_db(session, "EA", ANCHOR) is None


def test_survey_fallback_us_regression_unchanged(session: Session) -> None:
    """Sprint Q.1.1: US canonical path identical pre/post fallback addition."""
    _forwards_with_spot(session, ANCHOR, country="US")
    session.add(_expinf_row(ANCHOR, country="US"))
    # Seed a survey row too — canonical must still win with no FROM_SURVEY flag.
    session.add(_survey_row(ANCHOR, country="US", be_5y5y=0.019))
    session.commit()

    out = build_m3_inputs_from_db(session, "US", ANCHOR)
    assert out is not None
    # Canonical 245bps, not survey 190bps.
    assert out.breakeven_5y5y_bps == pytest.approx(245.0)
    assert out.bei_10y_bps == pytest.approx(240.0)
    assert M3_EXPINF_FROM_SURVEY_FLAG not in out.expinf_flags
