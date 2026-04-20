"""Behavioral tests for NSS overlay fit + derivations.

All values in decimal per ``docs/specs/conventions/units.md`` §Yields.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sonar.overlays import ConvergenceError, InsufficientDataError, nss

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "nss-curves"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


def _make_input(fx: dict[str, Any]) -> nss.NSSInput:
    i = fx["input"]
    return nss.NSSInput(
        tenors_years=np.array(i["tenors_years"]),
        yields=np.array(i["yields"]),
        country_code=i["country_code"],
        observation_date=date.fromisoformat(i["observation_date"]),
        curve_input_type="par",
    )


class TestFitUSCanonical:
    @pytest.fixture
    def fixture_data(self) -> dict[str, Any]:
        return _load_fixture("us_2024_01_02")

    def test_fit_converges(self, fixture_data: dict[str, Any]) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        assert isinstance(spot, nss.SpotCurve)

    def test_rmse_within_tolerance(self, fixture_data: dict[str, Any]) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        max_rmse = fixture_data["expected"]["rmse_bps_max"]
        assert spot.rmse_bps <= max_rmse, (
            f"rmse_bps={spot.rmse_bps} exceeds fixture tolerance {max_rmse}"
        )

    def test_beta_0_approx(self, fixture_data: dict[str, Any]) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        expected = fixture_data["expected"]["beta_0_approx"]
        tol_pct = fixture_data["tolerance"]["beta_relative_pct"] / 100.0
        assert abs(spot.params.beta_0 - expected) / expected <= tol_pct

    def test_fitted_10y(self, fixture_data: dict[str, Any]) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        expected = fixture_data["expected"]["fitted_10Y_approx"]
        tol_bps = fixture_data["tolerance"]["fitted_bps"]
        actual = spot.fitted_yields["10Y"]
        assert abs(actual - expected) * 10_000 <= tol_bps

    def test_confidence_above_floor(self, fixture_data: dict[str, Any]) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        assert spot.confidence >= fixture_data["expected"]["confidence_min"]

    def test_observations_used(self, fixture_data: dict[str, Any]) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        assert spot.observations_used == 11

    def test_no_reduced_flag(self, fixture_data: dict[str, Any]) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        assert "NSS_REDUCED" not in spot.flags

    def test_params_full_svensson(self, fixture_data: dict[str, Any]) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        assert spot.params.beta_3 is not None
        assert spot.params.lambda_2 is not None


class TestInsufficientData:
    def test_sparse_5_raises(self) -> None:
        fx = _load_fixture("us_sparse_5")
        with pytest.raises(InsufficientDataError):
            nss.fit_nss(_make_input(fx))

    def test_nan_yields_raises(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 2.0, 5.0, 10.0, 30.0]),
            yields=np.array([0.040, 0.042, np.nan, 0.044, 0.045, 0.046]),
            country_code="US",
            observation_date=date(2024, 1, 2),
            curve_input_type="par",
        )
        with pytest.raises(InsufficientDataError, match="Non-finite"):
            nss.fit_nss(inp)

    def test_yield_out_of_range_raises(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 2.0, 5.0, 10.0, 30.0]),
            yields=np.array([0.040, 0.042, 0.043, 0.044, 0.045, 0.50]),
            country_code="US",
            observation_date=date(2024, 1, 2),
            curve_input_type="par",
        )
        with pytest.raises(InsufficientDataError):
            nss.fit_nss(inp)

    def test_non_ascending_tenors_raises(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 2.0, 5.0, 10.0, 5.0]),
            yields=np.array([0.040, 0.042, 0.043, 0.044, 0.045, 0.046]),
            country_code="US",
            observation_date=date(2024, 1, 2),
            curve_input_type="par",
        )
        with pytest.raises(InsufficientDataError, match="ascending"):
            nss.fit_nss(inp)

    def test_length_mismatch_raises(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 2.0, 5.0, 10.0, 30.0]),
            yields=np.array([0.040, 0.042, 0.043]),
            country_code="US",
            observation_date=date(2024, 1, 2),
            curve_input_type="par",
        )
        with pytest.raises(InsufficientDataError, match="length mismatch"):
            nss.fit_nss(inp)


class TestMultiHumpStress:
    def test_either_converges_degraded_or_raises(self) -> None:
        fx = _load_fixture("synthetic_multi_hump")
        try:
            spot = nss.fit_nss(_make_input(fx))
        except ConvergenceError:
            return
        assert "HIGH_RMSE" in spot.flags


class TestLinkerThreshold:
    """CAL-033: linker_real curves accept n_obs>=5 (TIPS coverage carve-out)."""

    def test_linker_5_tenors_fits(self) -> None:
        # US TIPS DFII5/7/10/20/30 — 5 tenors below MIN_OBSERVATIONS=6.
        inp = nss.NSSInput(
            tenors_years=np.array([5.0, 7.0, 10.0, 20.0, 30.0]),
            yields=np.array([0.0176, 0.0175, 0.0174, 0.0184, 0.0191]),
            country_code="US",
            observation_date=date(2024, 1, 2),
            curve_input_type="linker_real",
        )
        spot = nss.fit_nss(inp)
        assert spot.observations_used == 5
        # 5 obs < MIN_OBSERVATIONS_FOR_SVENSSON (9) → reduced fit emits NSS_REDUCED.
        assert "NSS_REDUCED" in spot.flags

    def test_linker_4_tenors_still_raises(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([5.0, 7.0, 10.0, 30.0]),
            yields=np.array([0.0176, 0.0175, 0.0174, 0.0191]),
            country_code="US",
            observation_date=date(2024, 1, 2),
            curve_input_type="linker_real",
        )
        with pytest.raises(InsufficientDataError):
            nss.fit_nss(inp)

    def test_nominal_5_tenors_still_raises(self) -> None:
        # CAL-033 carve-out is linker-only; nominal must still enforce 6.
        inp = nss.NSSInput(
            tenors_years=np.array([1.0, 2.0, 5.0, 10.0, 30.0]),
            yields=np.array([0.045, 0.044, 0.043, 0.040, 0.041]),
            country_code="US",
            observation_date=date(2024, 1, 2),
            curve_input_type="par",
        )
        with pytest.raises(InsufficientDataError):
            nss.fit_nss(inp)


class TestReducedFit:
    def test_7_obs_triggers_reduced(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0]),
            yields=np.array([0.0540, 0.0480, 0.0433, 0.0405, 0.0393, 0.0395, 0.0408]),
            country_code="US",
            observation_date=date(2024, 1, 2),
            curve_input_type="par",
        )
        spot = nss.fit_nss(inp)
        assert "NSS_REDUCED" in spot.flags
        assert spot.params.beta_3 is None
        assert spot.params.lambda_2 is None
        assert spot.confidence <= 0.75


class TestDerivations:
    @pytest.fixture
    def us_spot(self) -> nss.SpotCurve:
        return nss.fit_nss(_make_input(_load_fixture("us_2024_01_02")))

    def test_zero_curve_shape(self, us_spot: nss.SpotCurve) -> None:
        z = nss.derive_zero_curve(us_spot)
        assert set(z.zero_rates.keys()) == set(nss.STANDARD_OUTPUT_TENORS)
        assert z.derivation == "nss_derived"

    def test_zero_curve_values_realistic(self, us_spot: nss.SpotCurve) -> None:
        z = nss.derive_zero_curve(us_spot)
        for tenor_label, rate in z.zero_rates.items():
            assert -0.05 <= rate <= 0.30, (
                f"Zero rate {tenor_label}={rate} out of decimal sane range"
            )

    def test_forward_curve_keys(self, us_spot: nss.SpotCurve) -> None:
        z = nss.derive_zero_curve(us_spot)
        f = nss.derive_forward_curve(z)
        assert set(f.forwards.keys()) == set(nss.STANDARD_FORWARD_KEYS)

    def test_forward_5y5y_within_sane_bounds(self, us_spot: nss.SpotCurve) -> None:
        z = nss.derive_zero_curve(us_spot)
        f = nss.derive_forward_curve(z)
        # 5y5y for US 2024-01-02 historically ~3.8-4.0% → 0.038-0.040 decimal.
        assert 0.02 <= f.forwards["5y5y"] <= 0.06

    def test_breakeven_forwards_none_in_isolation(self, us_spot: nss.SpotCurve) -> None:
        z = nss.derive_zero_curve(us_spot)
        f = nss.derive_forward_curve(z)
        assert f.breakeven_forwards is None

    def test_real_curve_none_without_inputs(self, us_spot: nss.SpotCurve) -> None:
        r = nss.derive_real_curve(us_spot, linker_yields=None)
        assert r is None

    def test_real_curve_direct_linker_path(self, us_spot: nss.SpotCurve) -> None:
        # Synthetic TIPS-like yields (2Y..30Y) ~1.5-2.2% decimal, 6 tenors ≥ MIN_OBSERVATIONS.
        linker = {
            "2Y": 0.0155,
            "5Y": 0.0180,
            "7Y": 0.0188,
            "10Y": 0.0195,
            "20Y": 0.0205,
            "30Y": 0.0210,
        }
        r = nss.derive_real_curve(
            us_spot,
            linker_yields=linker,
            observation_date=date(2024, 1, 2),
            country_code="US",
        )
        assert r is not None
        assert r.method == "direct_linker"
        assert r.linker_connector == "fred"
        assert set(r.real_yields.keys()) == set(nss.STANDARD_OUTPUT_TENORS)


class TestConfidencePropagation:
    def test_base_confidence_no_flags(self) -> None:
        assert nss._compute_confidence([], tier="T1") == 1.0

    def test_reduced_caps_at_075(self) -> None:
        assert nss._compute_confidence(["NSS_REDUCED"], tier="T1") <= 0.75

    def test_high_rmse_deducts_020(self) -> None:
        c = nss._compute_confidence(["HIGH_RMSE"], tier="T1")
        assert abs(c - 0.80) < 1e-9

    def test_stacking_reduced_plus_high_rmse(self) -> None:
        c = nss._compute_confidence(["NSS_REDUCED", "HIGH_RMSE"], tier="T1")
        assert c == pytest.approx(0.75)

    def test_tier_4_cap(self) -> None:
        assert nss._compute_confidence([], tier="T4") <= 0.70

    def test_em_coverage_flag_caps_070(self) -> None:
        # flags.md §1.1 EM_COVERAGE: cap at 0.70 (co-emitted by T4 countries).
        assert nss._compute_confidence(["EM_COVERAGE"], tier="T1") <= 0.70

    def test_regime_break_caps_060(self) -> None:
        assert nss._compute_confidence(["REGIME_BREAK"], tier="T1") <= 0.60

    def test_nss_fail_caps_050(self) -> None:
        assert nss._compute_confidence(["NSS_FAIL"], tier="T1") <= 0.50

    def test_deductions_sum_additive(self) -> None:
        # HIGH_RMSE (-0.20) + STALE (-0.20) + XVAL_DRIFT (-0.10) = 0.50.
        c = nss._compute_confidence(["HIGH_RMSE", "STALE", "XVAL_DRIFT"], tier="T1")
        assert c == pytest.approx(0.50)

    def test_floor_clamp_zero(self) -> None:
        # All additive deductions stacked: base 1.0 - (0.20+0.10+0.15+0.10+0.20+0.10) = 0.15.
        c = nss._compute_confidence(
            ["HIGH_RMSE", "XVAL_DRIFT", "NEG_FORWARD", "EXTRAPOLATED", "STALE", "COMPLEX_SHAPE"],
            tier="T1",
        )
        assert c == pytest.approx(0.15)
