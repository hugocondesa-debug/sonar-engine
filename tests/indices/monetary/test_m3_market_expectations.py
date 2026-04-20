"""Behavioral tests for M3 Market Expectations (anchor subset)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sonar.indices.exceptions import InsufficientInputsError
from sonar.indices.monetary.m3_market_expectations import (
    METHODOLOGY_VERSION,
    M3Inputs,
    M3MarketExpectationsAnchor,
    compute_m3_market_expectations_anchor,
)

FIXTURES_DIR = (
    Path(__file__).parent.parent.parent / "fixtures" / "indices" / "m3-market-expectations"
)


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


def _synth_history(mean_bps: float, sd_bps: float, n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.normal(loc=mean_bps, scale=sd_bps, size=n).tolist()


def _abs_history(mean_bps: float, sd_bps: float, n: int, seed: int) -> list[float]:
    raw = _synth_history(mean_bps, sd_bps, n, seed)
    return [abs(x) for x in raw]


def _inputs_from_fixture(fx: dict[str, Any]) -> M3Inputs:
    i = fx["input"]
    nominal_hist = _synth_history(mean_bps=300.0, sd_bps=50.0, n=1260, seed=111)
    anchor_hist = _abs_history(mean_bps=25.0, sd_bps=20.0, n=1260, seed=112)
    divergence_hist = (
        _abs_history(mean_bps=10.0, sd_bps=15.0, n=1260, seed=113)
        if i["bei_10y_bps"] is not None
        else None
    )
    return M3Inputs(
        country_code=i["country_code"],
        observation_date=date.fromisoformat(i["observation_date"]),
        nominal_5y5y_bps=float(i["nominal_5y5y_bps"]),
        breakeven_5y5y_bps=float(i["breakeven_5y5y_bps"]),
        bc_target_bps=float(i["bc_target_bps"]) if i["bc_target_bps"] is not None else None,
        bei_10y_bps=float(i["bei_10y_bps"]) if i["bei_10y_bps"] is not None else None,
        survey_10y_bps=float(i["survey_10y_bps"]) if i["survey_10y_bps"] is not None else None,
        nominal_5y5y_history_bps=nominal_hist,
        anchor_deviation_abs_history_bps=anchor_hist,
        bei_survey_div_abs_history_bps=divergence_hist,
        expinf_confidence=float(i["expinf_confidence"]),
        expinf_flags=tuple(i.get("expinf_flags", [])),
    )


@pytest.mark.parametrize(
    "fixture_id",
    ["us_2024_01_02", "de_2024_01_02", "pt_2024_01_02_derived"],
)
def test_fixture_value_within_expected_band(fixture_id: str) -> None:
    fx = _load(fixture_id)
    result = compute_m3_market_expectations_anchor(_inputs_from_fixture(fx))
    lo, hi = fx["expected"]["value_0_100_range"]
    assert lo <= result.value_0_100 <= hi, (
        f"{fixture_id}: value_0_100={result.value_0_100:.2f} outside [{lo}, {hi}]"
    )
    assert result.methodology_version == METHODOLOGY_VERSION
    for flag in fx["expected"].get("flags_contains", []):
        assert flag in result.flags


def test_de_more_anchored_than_us() -> None:
    us = compute_m3_market_expectations_anchor(_inputs_from_fixture(_load("us_2024_01_02")))
    de = compute_m3_market_expectations_anchor(_inputs_from_fixture(_load("de_2024_01_02")))
    assert de.value_0_100 > us.value_0_100, (
        f"DE anchor (dev ~10 bps) should score higher than US (dev ~54 bps), "
        f"got US={us.value_0_100:.2f}, DE={de.value_0_100:.2f}"
    )


def test_output_in_0_100_range() -> None:
    for fxid in ("us_2024_01_02", "de_2024_01_02", "pt_2024_01_02_derived"):
        r = compute_m3_market_expectations_anchor(_inputs_from_fixture(_load(fxid)))
        assert 0.0 <= r.value_0_100 <= 100.0


def test_no_target_path_reweights() -> None:
    fx = _load("us_2024_01_02")
    base = _inputs_from_fixture(fx)
    no_target = M3Inputs(
        country_code=base.country_code,
        observation_date=base.observation_date,
        nominal_5y5y_bps=base.nominal_5y5y_bps,
        breakeven_5y5y_bps=base.breakeven_5y5y_bps,
        bc_target_bps=None,
        bei_10y_bps=base.bei_10y_bps,
        survey_10y_bps=base.survey_10y_bps,
        nominal_5y5y_history_bps=base.nominal_5y5y_history_bps,
        anchor_deviation_abs_history_bps=base.anchor_deviation_abs_history_bps,
        bei_survey_div_abs_history_bps=base.bei_survey_div_abs_history_bps,
        expinf_confidence=base.expinf_confidence,
    )
    r = compute_m3_market_expectations_anchor(no_target)
    assert "NO_TARGET" in r.flags
    weights = r.sub_indicators["weights"]
    assert weights["anchor_deviation"] == 0.0
    assert weights["nominal_5y5y"] + weights["bei_survey_divergence"] == pytest.approx(1.0)


def test_low_expinf_confidence_raises() -> None:
    fx = _load("us_2024_01_02")
    base = _inputs_from_fixture(fx)
    degraded = M3Inputs(
        country_code=base.country_code,
        observation_date=base.observation_date,
        nominal_5y5y_bps=base.nominal_5y5y_bps,
        breakeven_5y5y_bps=base.breakeven_5y5y_bps,
        bc_target_bps=base.bc_target_bps,
        bei_10y_bps=base.bei_10y_bps,
        survey_10y_bps=base.survey_10y_bps,
        nominal_5y5y_history_bps=base.nominal_5y5y_history_bps,
        anchor_deviation_abs_history_bps=base.anchor_deviation_abs_history_bps,
        bei_survey_div_abs_history_bps=base.bei_survey_div_abs_history_bps,
        expinf_confidence=0.30,
    )
    with pytest.raises(InsufficientInputsError, match="confidence"):
        compute_m3_market_expectations_anchor(degraded)


def test_facade_compute_matches_pure() -> None:
    fx = _load("de_2024_01_02")
    inp = _inputs_from_fixture(fx)
    facade = M3MarketExpectationsAnchor()
    r = facade.compute(inp.country_code, inp.observation_date, inputs=inp)
    direct = compute_m3_market_expectations_anchor(inp)
    assert r.value_0_100 == direct.value_0_100


def test_pt_derived_inherits_flags() -> None:
    fx = _load("pt_2024_01_02_derived")
    r = compute_m3_market_expectations_anchor(_inputs_from_fixture(fx))
    assert "DIFFERENTIAL_TENOR_PROXY" in r.flags
    assert "LINKER_UNAVAILABLE" in r.flags


def test_bei_survey_missing_reweights_to_zero() -> None:
    fx = _load("pt_2024_01_02_derived")
    r = compute_m3_market_expectations_anchor(_inputs_from_fixture(fx))
    weights = r.sub_indicators["weights"]
    assert weights["bei_survey_divergence"] == 0.0
    assert weights["nominal_5y5y"] + weights["anchor_deviation"] == pytest.approx(1.0)
