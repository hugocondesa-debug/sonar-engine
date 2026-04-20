"""Behavioral tests for E2 Leading (slope subset) index.

Per brief §Commit 3: fixtures ``us_2024_01_02`` (post-hike cycle,
inverted), ``de_2024_01_02`` (near-flat Bund), and historical
``us_inversion_2022_07_13`` (deepest post-1981 inversion).

Historical z-score baselines are synthesised from a normal-regime mean
so the fixtures stay deterministic and self-contained.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sonar.indices.economic.e2_leading import (
    METHODOLOGY_VERSION,
    E2Inputs,
    E2LeadingSlope,
    compute_e2_leading_slope,
)
from sonar.indices.exceptions import InsufficientInputsError

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "indices" / "e2-leading"


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


def _synth_history(mean_bps: float, sd_bps: float, n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.normal(loc=mean_bps, scale=sd_bps, size=n).tolist()


def _inputs_from_fixture(fx: dict[str, Any]) -> E2Inputs:
    i = fx["input"]
    slope_hist = _synth_history(mean_bps=60.0, sd_bps=40.0, n=1260, seed=42)
    fwd_spread_hist = _synth_history(mean_bps=-20.0, sd_bps=30.0, n=1260, seed=43)
    return E2Inputs(
        country_code=i["country_code"],
        observation_date=date.fromisoformat(i["observation_date"]),
        spot_2y_bps=float(i["spot_2y_bps"]),
        spot_10y_bps=float(i["spot_10y_bps"]),
        forward_2y1y_bps=float(i["forward_2y1y_bps"]),
        slope_history_bps=slope_hist,
        forward_spread_history_bps=fwd_spread_hist,
        nss_confidence=float(i["nss_confidence"]),
        nss_flags=tuple(i.get("nss_flags", [])),
    )


@pytest.mark.parametrize(
    "fixture_id",
    ["us_2024_01_02", "de_2024_01_02", "us_inversion_2022_07_13"],
)
def test_fixture_produces_low_value_when_inverted(fixture_id: str) -> None:
    fx = _load(fixture_id)
    result = compute_e2_leading_slope(_inputs_from_fixture(fx))
    lo, hi = fx["expected"]["value_0_100_range"]
    assert lo <= result.value_0_100 <= hi, (
        f"{fixture_id}: value_0_100={result.value_0_100:.2f} outside [{lo}, {hi}]"
    )
    assert result.methodology_version == METHODOLOGY_VERSION
    for flag in fx["expected"].get("flags_contains", []):
        assert flag in result.flags, f"{fixture_id} missing flag {flag}"


def test_output_in_0_100_range() -> None:
    fx = _load("us_2024_01_02")
    result = compute_e2_leading_slope(_inputs_from_fixture(fx))
    assert 0.0 <= result.value_0_100 <= 100.0


def test_slope_inverted_flag_added_only_when_inverted() -> None:
    fx = _load("us_2024_01_02")
    inputs = _inputs_from_fixture(fx)
    # Synthesise a positive-slope scenario by flipping spot_2y vs spot_10y.
    pos_slope = E2Inputs(
        country_code=inputs.country_code,
        observation_date=inputs.observation_date,
        spot_2y_bps=300.0,
        spot_10y_bps=420.0,
        forward_2y1y_bps=380.0,
        slope_history_bps=inputs.slope_history_bps,
        forward_spread_history_bps=inputs.forward_spread_history_bps,
        nss_confidence=inputs.nss_confidence,
    )
    result = compute_e2_leading_slope(pos_slope)
    assert "SLOPE_INVERTED" not in result.flags


def test_low_nss_confidence_raises() -> None:
    fx = _load("us_2024_01_02")
    base = _inputs_from_fixture(fx)
    degraded = E2Inputs(
        country_code=base.country_code,
        observation_date=base.observation_date,
        spot_2y_bps=base.spot_2y_bps,
        spot_10y_bps=base.spot_10y_bps,
        forward_2y1y_bps=base.forward_2y1y_bps,
        slope_history_bps=base.slope_history_bps,
        forward_spread_history_bps=base.forward_spread_history_bps,
        nss_confidence=0.30,
    )
    with pytest.raises(InsufficientInputsError, match="confidence"):
        compute_e2_leading_slope(degraded)


def test_short_history_raises() -> None:
    fx = _load("us_2024_01_02")
    base = _inputs_from_fixture(fx)
    short = E2Inputs(
        country_code=base.country_code,
        observation_date=base.observation_date,
        spot_2y_bps=base.spot_2y_bps,
        spot_10y_bps=base.spot_10y_bps,
        forward_2y1y_bps=base.forward_2y1y_bps,
        slope_history_bps=[50.0],
        forward_spread_history_bps=[-10.0],
        nss_confidence=base.nss_confidence,
    )
    with pytest.raises(InsufficientInputsError, match="history"):
        compute_e2_leading_slope(short)


def test_facade_compute_matches_pure_function() -> None:
    fx = _load("de_2024_01_02")
    inputs = _inputs_from_fixture(fx)
    facade = E2LeadingSlope()
    r = facade.compute(inputs.country_code, inputs.observation_date, inputs=inputs)
    direct = compute_e2_leading_slope(inputs)
    assert r.value_0_100 == direct.value_0_100
    assert r.methodology_version == direct.methodology_version


def test_facade_mismatch_raises() -> None:
    fx = _load("de_2024_01_02")
    inputs = _inputs_from_fixture(fx)
    facade = E2LeadingSlope()
    with pytest.raises(ValueError, match="must match"):
        facade.compute("US", inputs.observation_date, inputs=inputs)


def test_insufficient_history_flag_fires() -> None:
    fx = _load("us_2024_01_02")
    base = _inputs_from_fixture(fx)
    short_but_valid = E2Inputs(
        country_code=base.country_code,
        observation_date=base.observation_date,
        spot_2y_bps=base.spot_2y_bps,
        spot_10y_bps=base.spot_10y_bps,
        forward_2y1y_bps=base.forward_2y1y_bps,
        slope_history_bps=_synth_history(60.0, 40.0, 300, seed=11),
        forward_spread_history_bps=_synth_history(-20.0, 30.0, 300, seed=12),
        nss_confidence=0.85,
    )
    r = compute_e2_leading_slope(short_but_valid)
    assert "INSUFFICIENT_HISTORY" in r.flags
    assert r.confidence <= 0.65


def test_recession_proxy_sign_inverted() -> None:
    """When slope is sharply inverted, recession_proxy_z should be negative
    after the sign flip (high absolute probability pulls E2 down)."""
    fx = _load("us_inversion_2022_07_13")
    r = compute_e2_leading_slope(_inputs_from_fixture(fx))
    assert r.sub_indicators["recession_proxy_z"] < 0
    assert r.sub_indicators["recession_prob_proxy"] > 0.5
