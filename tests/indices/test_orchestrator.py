"""Integration tests for the L3 indices orchestrator."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

import numpy as np

from sonar.indices.economic.e2_leading import E2Inputs
from sonar.indices.monetary.m3_market_expectations import M3Inputs
from sonar.indices.orchestrator import (
    OrchestratorInputs,
    compute_all_indices,
    main,
)

if TYPE_CHECKING:
    import pytest


def _e2_inputs(country: str, d: date) -> E2Inputs:
    rng = np.random.default_rng(1)
    return E2Inputs(
        country_code=country,
        observation_date=d,
        spot_2y_bps=433.0,
        spot_10y_bps=395.0,
        forward_2y1y_bps=380.0,
        slope_history_bps=rng.normal(60.0, 40.0, size=1260).tolist(),
        forward_spread_history_bps=rng.normal(-20.0, 30.0, size=1260).tolist(),
        nss_confidence=0.85,
    )


def _m3_inputs(country: str, d: date) -> M3Inputs:
    rng = np.random.default_rng(2)
    return M3Inputs(
        country_code=country,
        observation_date=d,
        nominal_5y5y_bps=385.0,
        breakeven_5y5y_bps=254.0,
        bc_target_bps=200.0,
        bei_10y_bps=227.0,
        survey_10y_bps=248.0,
        nominal_5y5y_history_bps=rng.normal(300.0, 50.0, size=1260).tolist(),
        anchor_deviation_abs_history_bps=[
            abs(x) for x in rng.normal(25.0, 20.0, size=1260).tolist()
        ],
        bei_survey_div_abs_history_bps=[abs(x) for x in rng.normal(10.0, 15.0, size=1260).tolist()],
        expinf_confidence=0.85,
    )


def test_compute_all_us_de_2024_01_02() -> None:
    d = date(2024, 1, 2)
    for country in ("US", "DE"):
        inputs = OrchestratorInputs(
            country_code=country,
            observation_date=d,
            e2=_e2_inputs(country, d),
            m3=_m3_inputs(country, d),
        )
        results = compute_all_indices(inputs)
        assert "E2_LEADING" in results
        assert "M3_MARKET_EXPECTATIONS" in results
        for r in results.values():
            assert 0.0 <= r.value_0_100 <= 100.0
            assert r.country_code == country
            assert r.date == d


def test_compute_all_skips_missing_inputs() -> None:
    d = date(2024, 1, 2)
    inputs = OrchestratorInputs(country_code="US", observation_date=d, e2=None, m3=None)
    results = compute_all_indices(inputs)
    assert results == {}


def test_compute_all_skips_insufficient_inputs_gracefully() -> None:
    d = date(2024, 1, 2)
    # Degrade E2 by forcing confidence below minimum — should skip, not raise.
    bad_e2 = E2Inputs(
        country_code="US",
        observation_date=d,
        spot_2y_bps=433.0,
        spot_10y_bps=395.0,
        forward_2y1y_bps=380.0,
        slope_history_bps=[60.0, 50.0],
        forward_spread_history_bps=[-20.0, -10.0],
        nss_confidence=0.30,
    )
    inputs = OrchestratorInputs(
        country_code="US",
        observation_date=d,
        e2=bad_e2,
        m3=_m3_inputs("US", d),
    )
    results = compute_all_indices(inputs)
    assert "E2_LEADING" not in results
    assert "M3_MARKET_EXPECTATIONS" in results


def test_cli_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--country", "US", "--date", "2024-01-02"])
    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    assert payload["country"] == "US"
    assert payload["date"] == "2024-01-02"
    assert isinstance(payload["indices"], list)
    # Expect E2 + M3 in the output under synthetic inputs.
    codes = {entry["index_code"] for entry in payload["indices"]}
    assert codes == {"E2_LEADING", "M3_MARKET_EXPECTATIONS"}
    for entry in payload["indices"]:
        assert 0.0 <= entry["value_0_100"] <= 100.0
