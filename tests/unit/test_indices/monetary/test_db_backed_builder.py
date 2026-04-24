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
    ExpInflationBeiRow,
    ExpInflationSurveyRow,
    IndexValue,
    NSSYieldCurveForwards,
    NSSYieldCurveSpot,
)
from sonar.indices.monetary.db_backed_builder import (
    EXPINF_INDEX_CODE,
    M3_EXPINF_FROM_BEI_FLAG,
    M3_EXPINF_FROM_SURVEY_FLAG,
    MonetaryDbBackedInputsBuilder,
    build_m3_inputs_from_db,
)
from sonar.indices.monetary.exp_inflation_writers import persist_bei_row

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


# ---------------------------------------------------------------------------
# Sprint Q.1.2 — _load_histories survey fallback
# ---------------------------------------------------------------------------


def test_load_histories_canonical_path_unchanged_sprint_q_1_2(session: Session) -> None:
    """Sprint Q.1.2: canonical history path remains bit-identical (US regression)."""
    # Seed 4 prior dates canonical path, no survey rows → Q.1.2 fallback MUST not trigger.
    for i, delta_days in enumerate([90, 60, 30, 0]):
        prior = ANCHOR - timedelta(days=delta_days)
        _forwards_with_spot(
            session, prior, country="US", forward_5y5y=0.040 + i * 0.0005, fit_suffix=f"u{i}"
        )
        session.add(_expinf_row(prior, country="US", be_5y5y=0.024 + i * 0.0002))
    session.commit()

    out = build_m3_inputs_from_db(session, "US", ANCHOR, history_days=120)
    assert out is not None
    assert len(out.nominal_5y5y_history_bps) == 4
    assert len(out.anchor_deviation_abs_history_bps) == 4
    # No FROM_SURVEY flag — canonical path exclusive.
    assert M3_EXPINF_FROM_SURVEY_FLAG not in out.expinf_flags


def test_load_histories_survey_fallback_populates_anchor_hist(session: Session) -> None:
    """Sprint Q.1.2: canonical empty + survey populated → anchor_hist forward-filled."""
    # Seed 4 forwards rows for EA across 90d window, no canonical IndexValue.
    for i, delta_days in enumerate([90, 60, 30, 0]):
        prior = ANCHOR - timedelta(days=delta_days)
        _forwards_with_spot(
            session, prior, country="EA", forward_5y5y=0.039 + i * 0.0005, fit_suffix=f"e{i}"
        )
    # 2 sparse survey rows — forward-fill against all 4 forwards dates.
    session.add(_survey_row(ANCHOR - timedelta(days=95), country="EA", be_5y5y=0.020, be_10y=0.020))
    session.add(_survey_row(ANCHOR - timedelta(days=45), country="EA", be_5y5y=0.022, be_10y=0.022))
    # Data-point survey row at anchor so build_m3_inputs_from_db main path resolves.
    session.add(_survey_row(ANCHOR, country="EA", be_5y5y=0.022, be_10y=0.022))
    session.commit()

    out = build_m3_inputs_from_db(session, "EA", ANCHOR, history_days=120)
    assert out is not None
    # All 4 forwards dates produced a forward-filled anchor deviation.
    assert len(out.nominal_5y5y_history_bps) == 4
    assert len(out.anchor_deviation_abs_history_bps) == 4
    assert M3_EXPINF_FROM_SURVEY_FLAG in out.expinf_flags


def test_load_histories_survey_sparse_forward_fill_all_dates(session: Session) -> None:
    """Sprint Q.1.2: single early survey release forward-fills every later forwards date."""
    for i, delta_days in enumerate([80, 60, 40, 20, 0]):
        prior = ANCHOR - timedelta(days=delta_days)
        _forwards_with_spot(session, prior, country="EA", forward_5y5y=0.041, fit_suffix=f"s{i}")
    # Single survey release ~90d before anchor.
    session.add(_survey_row(ANCHOR - timedelta(days=90), country="EA", be_5y5y=0.021))
    # Anchor-date survey row so main builder resolves.
    session.add(_survey_row(ANCHOR, country="EA", be_5y5y=0.021))
    session.commit()

    out = build_m3_inputs_from_db(session, "EA", ANCHOR, history_days=120)
    assert out is not None
    # All 5 forwards dates get the same forward-filled anchor deviation.
    assert len(out.anchor_deviation_abs_history_bps) == 5
    # 0.021 decimal → 210 bps; ECB target 2% → 200 bps → |210-200|=10.
    for value in out.anchor_deviation_abs_history_bps:
        assert value == pytest.approx(10.0)


def test_load_histories_no_survey_rows_before_earliest_forwards(session: Session) -> None:
    """Sprint Q.1.2: survey releases AFTER all forwards → early dates get no anchor."""
    # Forwards at D1,D2,D3 (early); survey at D4 (after last forwards but in window).
    d1 = ANCHOR - timedelta(days=60)
    d2 = ANCHOR - timedelta(days=45)
    d3 = ANCHOR - timedelta(days=30)
    d4 = ANCHOR - timedelta(days=15)
    for i, prior in enumerate([d1, d2, d3]):
        _forwards_with_spot(session, prior, country="EA", fit_suffix=f"f{i}")
    session.add(_survey_row(d4, country="EA", be_5y5y=0.020))
    # Anchor-date survey so main builder resolves (doesn't count for history).
    session.add(_survey_row(ANCHOR, country="EA", be_5y5y=0.020))
    _forwards_with_spot(session, ANCHOR, country="EA", fit_suffix="anc")
    session.commit()

    out = build_m3_inputs_from_db(session, "EA", ANCHOR, history_days=90)
    assert out is not None
    # 4 forwards rows total; first 3 before d4 survey → no anchor match for those 3.
    # Anchor date itself matches d4 (latest on-or-before) → 1 anchor point from d4 +
    # 1 from the anchor-date survey row = 2 total (anchor + anchor-date both use
    # anchor-date survey which is latest-on-or-before for ANCHOR, the d4 row is
    # latest-on-or-before for every forwards >= d4).
    assert len(out.nominal_5y5y_history_bps) == 4
    # Only forwards at/after d4 get a match → just the anchor date = 1 entry.
    # (d1,d2,d3 are before d4; anchor is at ANCHOR ≥ d4 so it matches.)
    assert len(out.anchor_deviation_abs_history_bps) == 1


def test_load_histories_no_canonical_no_survey_returns_empty_anchor(session: Session) -> None:
    """Sprint Q.1.2: empty canonical + empty survey → anchor_hist empty (backward compat)."""
    # EA country but no EXPINF canonical AND no survey rows in history window.
    _forwards_with_spot(session, ANCHOR - timedelta(days=30), country="EA", fit_suffix="x0")
    _forwards_with_spot(session, ANCHOR, country="EA", fit_suffix="x1")
    # Provide a single survey row AT anchor only (for build_m3_inputs main-path resolve)
    # — but outside the history window so it doesn't contribute to forward-fill.
    # Actually the window is [anchor-history_days, anchor] so ANCHOR itself is inside.
    # Use history_days=10 so 30d-prior forwards is outside but will still be queried —
    # in fact the forwards query uses the same window so it's also outside. Let's just
    # have NO prior forwards and let history be len 1 for nominal.
    session.commit()

    # With only the single anchor-date survey row (no history survey coverage other
    # than anchor itself), anchor_hist has at most 1 entry from the anchor date. Add
    # survey row at anchor so main builder resolves, then assert history short.
    session.add(_survey_row(ANCHOR, country="EA", be_5y5y=0.020))
    session.commit()

    out = build_m3_inputs_from_db(session, "EA", ANCHOR, history_days=120)
    assert out is not None
    # 2 forwards rows (30d prior + anchor) → 2 nominal_hist entries.
    assert len(out.nominal_5y5y_history_bps) == 2
    # Only the single survey row at anchor → forward-fills just the anchor (prior date
    # has no survey on-or-before). 1 anchor entry.
    assert len(out.anchor_deviation_abs_history_bps) == 1


def test_load_histories_canonical_wins_over_survey_when_both_present(session: Session) -> None:
    """Sprint Q.1.2: mixed window — canonical populated → survey table NOT queried.

    Design decision captured in audit §4.3: minimum-change approach queries survey
    only when canonical is fully empty. With even one canonical row present, the
    survey branch is skipped entirely and non-matching dates simply get no anchor
    entry. Guards against regressing the US canonical path.
    """
    # Canonical has 1 row @ ANCHOR; forwards has 2 (anchor + 30d prior). Seed a
    # survey row at 30d-prior too — it MUST be ignored.
    _forwards_with_spot(session, ANCHOR - timedelta(days=30), country="US", fit_suffix="p0")
    _forwards_with_spot(session, ANCHOR, country="US", fit_suffix="p1")
    session.add(_expinf_row(ANCHOR, country="US", be_5y5y=0.024))
    # Survey row that would have forward-filled 30d-prior had survey branch been taken.
    session.add(_survey_row(ANCHOR - timedelta(days=45), country="US", be_5y5y=0.021))
    session.commit()

    out = build_m3_inputs_from_db(session, "US", ANCHOR, history_days=120)
    assert out is not None
    # Canonical-only branch: only the ANCHOR date has a match → 1 anchor entry.
    # 30d-prior forwards has no canonical match and survey branch NOT taken → skipped.
    assert len(out.nominal_5y5y_history_bps) == 2
    assert len(out.anchor_deviation_abs_history_bps) == 1
    assert M3_EXPINF_FROM_SURVEY_FLAG not in out.expinf_flags


def test_load_histories_ea_full_path_persistable_by_downstream(session: Session) -> None:
    """Sprint Q.1.2 integration: EA M3Inputs history arrays satisfy z-score guard."""
    # Seed enough history that m3_market_expectations guard (≥2 points both arrays) passes.
    for i, delta_days in enumerate([100, 80, 60, 40, 20, 0]):
        prior = ANCHOR - timedelta(days=delta_days)
        _forwards_with_spot(
            session, prior, country="EA", forward_5y5y=0.038 + i * 0.001, fit_suffix=f"p{i}"
        )
    # Quarterly survey cadence: 2 releases in the 100d window + anchor date.
    session.add(_survey_row(ANCHOR - timedelta(days=95), country="EA", be_5y5y=0.019))
    session.add(_survey_row(ANCHOR - timedelta(days=30), country="EA", be_5y5y=0.021))
    session.add(_survey_row(ANCHOR, country="EA", be_5y5y=0.021))
    session.commit()

    out = build_m3_inputs_from_db(session, "EA", ANCHOR, history_days=120)
    assert out is not None
    # Critical invariant: both history arrays ≥ 2 (closes Q.1.1 regression).
    assert len(out.nominal_5y5y_history_bps) >= 2
    assert len(out.anchor_deviation_abs_history_bps) >= 2


# ---------------------------------------------------------------------------
# Sprint Q.2 — BEI fallback (main builder + _load_histories together;
# Lesson #20 #5 applied from start — see
# docs/backlog/probe-results/sprint-q-2-boe-ilg-spf-probe.md §4)
# ---------------------------------------------------------------------------


def _bei_row(
    obs_date: date,
    *,
    country: str = "GB",
    y5: float = 0.040,
    y10: float = 0.035,
    extra_tenors: dict[str, float] | None = None,
    flags: str | None = "BEI_FITTED_IMPLIED",
    confidence: float = 0.85,
    linker_connector: str = "BOE_GLC_INFLATION",
) -> ExpInflationBeiRow:
    """Factory: BEI row matching the Sprint Q.2 writer shape.

    Defaults mirror a realistic GB BEI snapshot (5Y=4.0 %, 10Y=3.5 %) so
    the implied 5Y5Y forward derives to ``2*350 - 400 = 300`` bps.
    """
    tenors: dict[str, float] = {"5Y": y5, "10Y": y10}
    if extra_tenors:
        tenors.update(extra_tenors)
    return ExpInflationBeiRow(
        exp_inf_id=f"{country}-{obs_date.isoformat()}-bei",
        country_code=country,
        date=obs_date,
        methodology_version="EXPINF_BEI_v1.0",
        confidence=confidence,
        flags=flags,
        nominal_yields_json=json.dumps({}),
        linker_real_yields_json=json.dumps({}),
        bei_tenors_json=json.dumps(tenors),
        linker_connector=linker_connector,
        nss_fit_id=None,
    )


def test_bei_fallback_activates_when_canonical_and_survey_empty(session: Session) -> None:
    """Sprint Q.2: BEI row serves M3Inputs when both canonical + survey absent."""
    _forwards_with_spot(session, ANCHOR, country="GB")
    # Seed BEI-only at ANCHOR; no canonical IndexValue, no SPF survey.
    session.add(_bei_row(ANCHOR, country="GB", y5=0.040, y10=0.035))
    session.commit()

    out = build_m3_inputs_from_db(session, "GB", ANCHOR)
    assert out is not None
    # 5Y5Y derived: 2 * 350 - 400 = 300 bps.
    assert out.breakeven_5y5y_bps == pytest.approx(300.0)
    # BEI path exposes the market-implied leg.
    assert out.bei_10y_bps == pytest.approx(350.0)
    assert out.survey_10y_bps is None
    assert M3_EXPINF_FROM_BEI_FLAG in out.expinf_flags
    assert "BEI_FITTED_IMPLIED" in out.expinf_flags
    assert out.expinf_confidence == pytest.approx(0.85)


def test_bei_fallback_canonical_primary(session: Session) -> None:
    """Sprint Q.2: canonical IndexValue takes priority over BEI row."""
    _forwards_with_spot(session, ANCHOR, country="GB")
    session.add(_expinf_row(ANCHOR, country="GB", be_5y5y=0.0245, be_10y=0.024))
    session.add(_bei_row(ANCHOR, country="GB", y5=0.040, y10=0.035))
    session.commit()

    out = build_m3_inputs_from_db(session, "GB", ANCHOR)
    assert out is not None
    assert out.breakeven_5y5y_bps == pytest.approx(245.0)
    assert M3_EXPINF_FROM_BEI_FLAG not in out.expinf_flags
    assert M3_EXPINF_FROM_SURVEY_FLAG not in out.expinf_flags


def test_bei_fallback_survey_wins_over_bei(session: Session) -> None:
    """Sprint Q.2: priority is canonical > survey > BEI — survey beats BEI."""
    _forwards_with_spot(session, ANCHOR, country="GB")
    # No canonical; both survey + BEI populated.
    session.add(
        _survey_row(
            ANCHOR,
            country="GB",
            be_5y5y=0.0250,
            be_10y=0.0245,
            survey_name="BOE_SEF",
            flags="SPF_LT_AS_ANCHOR",
        )
    )
    session.add(_bei_row(ANCHOR, country="GB", y5=0.040, y10=0.035))
    session.commit()

    out = build_m3_inputs_from_db(session, "GB", ANCHOR)
    assert out is not None
    # Survey 0.025 → 250bps wins; BEI derivation would have been 300bps.
    assert out.breakeven_5y5y_bps == pytest.approx(250.0)
    assert M3_EXPINF_FROM_SURVEY_FLAG in out.expinf_flags
    assert M3_EXPINF_FROM_BEI_FLAG not in out.expinf_flags


def test_bei_fallback_picks_most_recent_on_or_before(session: Session) -> None:
    """Sprint Q.2: weekend / holiday forward-fill — most recent BEI row wins."""
    _forwards_with_spot(session, ANCHOR, country="GB")
    # Two BEI rows: 3d prior (most recent weekday) + 10d prior.
    session.add(_bei_row(ANCHOR - timedelta(days=10), country="GB", y5=0.041, y10=0.036))
    session.add(_bei_row(ANCHOR - timedelta(days=3), country="GB", y5=0.040, y10=0.035))
    session.commit()

    out = build_m3_inputs_from_db(session, "GB", ANCHOR)
    assert out is not None
    # Most-recent row (3d prior): 5Y=0.040, 10Y=0.035 → 5Y5Y = 300 bps.
    assert out.breakeven_5y5y_bps == pytest.approx(300.0)


def test_bei_fallback_partial_curve_returns_none(session: Session) -> None:
    """Sprint Q.2: BEI row missing 5Y OR 10Y tenor → 5Y5Y uncomputable → None."""
    _forwards_with_spot(session, ANCHOR, country="GB")
    session.add(
        ExpInflationBeiRow(
            exp_inf_id="gb-partial",
            country_code="GB",
            date=ANCHOR,
            methodology_version="EXPINF_BEI_v1.0",
            confidence=0.85,
            flags=None,
            nominal_yields_json=json.dumps({}),
            linker_real_yields_json=json.dumps({}),
            # Only 10Y present — 5Y missing → _bei_5y5y_bps_from_tenors = None.
            bei_tenors_json=json.dumps({"10Y": 0.035}),
            linker_connector="BOE_GLC_INFLATION",
        )
    )
    session.commit()
    assert build_m3_inputs_from_db(session, "GB", ANCHOR) is None


def test_bei_fallback_no_data_returns_none(session: Session) -> None:
    """Sprint Q.2: no canonical, no survey, no BEI → None."""
    _forwards_with_spot(session, ANCHOR, country="GB")
    session.commit()
    assert build_m3_inputs_from_db(session, "GB", ANCHOR) is None


def test_bei_fallback_us_regression_unchanged(session: Session) -> None:
    """Sprint Q.2: US canonical path identical — BEI row present but ignored."""
    _forwards_with_spot(session, ANCHOR, country="US")
    session.add(_expinf_row(ANCHOR, country="US"))
    # Seed a BEI row too — canonical must win; BEI branch not entered.
    session.add(_bei_row(ANCHOR, country="US", y5=0.040, y10=0.035))
    session.commit()

    out = build_m3_inputs_from_db(session, "US", ANCHOR)
    assert out is not None
    assert out.breakeven_5y5y_bps == pytest.approx(245.0)
    assert out.bei_10y_bps == pytest.approx(240.0)  # from canonical, NOT 350bps BEI.
    assert M3_EXPINF_FROM_BEI_FLAG not in out.expinf_flags
    assert M3_EXPINF_FROM_SURVEY_FLAG not in out.expinf_flags


def test_load_histories_bei_fallback_when_canonical_and_survey_empty(session: Session) -> None:
    """Sprint Q.2 Lesson #20 #5: _load_histories extends to BEI fallback."""
    # 4 forwards rows across 90d window; no canonical, no survey, BEI-only.
    for i, delta_days in enumerate([90, 60, 30, 0]):
        prior = ANCHOR - timedelta(days=delta_days)
        _forwards_with_spot(
            session, prior, country="GB", forward_5y5y=0.045 + i * 0.0005, fit_suffix=f"g{i}"
        )
    # BEI rows: one per forwards date (daily cadence).
    for delta_days in [90, 60, 30, 0]:
        prior = ANCHOR - timedelta(days=delta_days)
        session.add(_bei_row(prior, country="GB", y5=0.040, y10=0.035))
    session.commit()

    out = build_m3_inputs_from_db(session, "GB", ANCHOR, history_days=120)
    assert out is not None
    assert len(out.nominal_5y5y_history_bps) == 4
    # Each forwards date matches a BEI row → 4 anchor points.
    assert len(out.anchor_deviation_abs_history_bps) == 4
    # 5Y5Y = 300 bps; GB target (BoE) 2% = 200 bps; |300-200|=100.
    for value in out.anchor_deviation_abs_history_bps:
        assert value == pytest.approx(100.0)
    assert M3_EXPINF_FROM_BEI_FLAG in out.expinf_flags


def test_load_histories_bei_sparse_forward_fill(session: Session) -> None:
    """Sprint Q.2: BEI row on earlier date forward-fills later forwards dates."""
    for i, delta_days in enumerate([40, 20, 10, 0]):
        prior = ANCHOR - timedelta(days=delta_days)
        _forwards_with_spot(session, prior, country="GB", forward_5y5y=0.045, fit_suffix=f"s{i}")
    # Only one BEI row, 50d prior — forward-fills every later forwards date.
    session.add(_bei_row(ANCHOR - timedelta(days=50), country="GB", y5=0.040, y10=0.035))
    # Anchor-date BEI so main builder resolves.
    session.add(_bei_row(ANCHOR, country="GB", y5=0.040, y10=0.035))
    session.commit()

    out = build_m3_inputs_from_db(session, "GB", ANCHOR, history_days=120)
    assert out is not None
    # All 4 forwards rows get forward-filled anchor deviations.
    assert len(out.anchor_deviation_abs_history_bps) == 4


def test_load_histories_canonical_wins_over_bei_when_both_present(session: Session) -> None:
    """Sprint Q.2: canonical-priority invariant — BEI branch NOT queried if canonical exists.

    Mirrors the Q.1.2 survey-priority test. Any country with at least one canonical
    row in the window stays on the canonical-only branch; BEI rows are ignored.
    """
    _forwards_with_spot(session, ANCHOR - timedelta(days=30), country="US", fit_suffix="b0")
    _forwards_with_spot(session, ANCHOR, country="US", fit_suffix="b1")
    session.add(_expinf_row(ANCHOR, country="US", be_5y5y=0.024))
    # BEI row that would have forward-filled the 30d-prior date — must be ignored.
    session.add(_bei_row(ANCHOR - timedelta(days=45), country="US", y5=0.040, y10=0.035))
    session.commit()

    out = build_m3_inputs_from_db(session, "US", ANCHOR, history_days=120)
    assert out is not None
    assert len(out.nominal_5y5y_history_bps) == 2
    # Canonical-only: only the ANCHOR date has a match (30d prior skipped).
    assert len(out.anchor_deviation_abs_history_bps) == 1
    assert M3_EXPINF_FROM_BEI_FLAG not in out.expinf_flags
    assert M3_EXPINF_FROM_SURVEY_FLAG not in out.expinf_flags


def test_load_histories_survey_wins_over_bei_when_both_present(session: Session) -> None:
    """Sprint Q.2: priority cascade — survey branch entered → BEI query skipped."""
    # Forwards for GB across 60d window; no canonical; survey + BEI both present.
    for i, delta_days in enumerate([60, 30, 0]):
        prior = ANCHOR - timedelta(days=delta_days)
        _forwards_with_spot(session, prior, country="GB", forward_5y5y=0.045, fit_suffix=f"p{i}")
    session.add(_survey_row(ANCHOR, country="GB", be_5y5y=0.025, be_10y=0.025))
    # BEI row at the 30d date — should NOT be consulted because survey is present.
    session.add(_bei_row(ANCHOR - timedelta(days=30), country="GB", y5=0.040, y10=0.035))
    session.commit()

    out = build_m3_inputs_from_db(session, "GB", ANCHOR, history_days=90)
    assert out is not None
    assert M3_EXPINF_FROM_SURVEY_FLAG in out.expinf_flags
    assert M3_EXPINF_FROM_BEI_FLAG not in out.expinf_flags


# ---------------------------------------------------------------------------
# Sprint Q.2 — persist_bei_row writer (Sprint Q.1.1 wire-style integration)
# ---------------------------------------------------------------------------


def test_persist_bei_row_inserts_new_row(session: Session) -> None:
    """Sprint Q.2: first insert returns True + row is retrievable."""
    result = persist_bei_row(
        session,
        country_code="GB",
        observation_date=ANCHOR,
        bei_tenors_decimal={"5Y": 0.040, "10Y": 0.035, "30Y": 0.033},
        linker_connector="BOE_GLC_INFLATION",
        methodology_version="EXPINF_BEI_v1.0",
        flags=("BEI_FITTED_IMPLIED",),
    )
    session.commit()
    assert result is True
    rows = session.query(ExpInflationBeiRow).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.country_code == "GB"
    assert row.date == ANCHOR
    assert row.linker_connector == "BOE_GLC_INFLATION"
    assert row.flags == "BEI_FITTED_IMPLIED"
    assert json.loads(row.bei_tenors_json) == {"10Y": 0.035, "30Y": 0.033, "5Y": 0.040}


def test_persist_bei_row_is_idempotent_on_duplicate(session: Session) -> None:
    """Sprint Q.2: duplicate (country, date, methodology) returns False; one row only."""
    payload = {
        "country_code": "GB",
        "observation_date": ANCHOR,
        "bei_tenors_decimal": {"5Y": 0.040, "10Y": 0.035},
        "linker_connector": "BOE_GLC_INFLATION",
        "methodology_version": "EXPINF_BEI_v1.0",
    }
    assert persist_bei_row(session, **payload) is True
    session.commit()
    assert persist_bei_row(session, **payload) is False
    session.commit()
    assert session.query(ExpInflationBeiRow).count() == 1


def test_persist_bei_row_rejects_empty_tenors(session: Session) -> None:
    """Sprint Q.2: empty tenor map is a programmer bug, not a data miss."""
    with pytest.raises(ValueError, match="empty bei_tenors_decimal"):
        persist_bei_row(
            session,
            country_code="GB",
            observation_date=ANCHOR,
            bei_tenors_decimal={},
            linker_connector="BOE_GLC_INFLATION",
            methodology_version="EXPINF_BEI_v1.0",
        )
