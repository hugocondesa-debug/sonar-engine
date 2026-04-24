"""Spec §7 fixture tests for the NSS real-curve writer.

Covers the three Sprint 2 fixtures:

* ``real_us_2024_01_02`` — direct-linker path (TIPS DFII*) → ``real_10Y``
  ≈ 0.0185 ± 15 bps + breakeven ``10Y ≈ 0.0210 ± 15 bps``.
* ``de_bund_2024_01_02`` — nominal Bundesbank cross-val target — every
  fitted tenor within ±5 bps of the published proxy.
* ``forward_5y5y_us_2024_01_02`` — nominal ``5y5y`` forward derived from
  the existing ``us_2024_01_02`` fixture, ≈ 0.0385 ± 10 bps.

All values decimal per ``docs/specs/conventions/units.md`` §Yields.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sonar.overlays import nss
from sonar.overlays.nss_real_writer import build_real_curve

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "nss-curves"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


# ---------------------------------------------------------------------------
# real_us_2024_01_02 — direct_linker path
# ---------------------------------------------------------------------------


class TestRealUs20240102:
    """Spec §7 fixture row 9 — direct_linker via 5 TIPS tenors."""

    @pytest.fixture
    def fx(self) -> dict[str, Any]:
        return _load_fixture("real_us_2024_01_02")

    @pytest.fixture
    def us_nominal_spot(self) -> nss.SpotCurve:
        nominal_fx = _load_fixture("us_2024_01_02")
        i = nominal_fx["input"]
        nss_in = nss.NSSInput(
            tenors_years=np.array(i["tenors_years"]),
            yields=np.array(i["yields"]),
            country_code=i["country_code"],
            observation_date=date.fromisoformat(i["observation_date"]),
            curve_input_type="par",
        )
        return nss.fit_nss(nss_in)

    def test_method_direct_linker(
        self,
        fx: dict[str, Any],
        us_nominal_spot: nss.SpotCurve,
    ) -> None:
        real = build_real_curve(
            country_code=fx["input"]["country_code"],
            observation_date=date.fromisoformat(fx["input"]["observation_date"]),
            nominal_spot=us_nominal_spot,
            linker_yields=fx["input"]["linker_yields"],
        )
        assert real is not None
        assert real.method == fx["expected"]["method"]
        assert real.linker_connector == fx["expected"]["linker_connector"]

    def test_real_10y_within_spec_tolerance(
        self,
        fx: dict[str, Any],
        us_nominal_spot: nss.SpotCurve,
    ) -> None:
        real = build_real_curve(
            country_code=fx["input"]["country_code"],
            observation_date=date.fromisoformat(fx["input"]["observation_date"]),
            nominal_spot=us_nominal_spot,
            linker_yields=fx["input"]["linker_yields"],
        )
        assert real is not None
        actual = real.real_yields["10Y"]
        expected = fx["expected"]["real_10Y_approx"]
        tol_bps = fx["tolerance"]["real_yield_bps"]
        assert abs(actual - expected) * 10_000 <= tol_bps, (
            f"real_10Y={actual:.6f} drift={(actual - expected) * 10_000:.2f}bps "
            f"exceeds spec §7 tolerance ±{tol_bps} bps"
        )

    def test_breakeven_10y_within_tolerance(
        self,
        fx: dict[str, Any],
        us_nominal_spot: nss.SpotCurve,
    ) -> None:
        real = build_real_curve(
            country_code=fx["input"]["country_code"],
            observation_date=date.fromisoformat(fx["input"]["observation_date"]),
            nominal_spot=us_nominal_spot,
            linker_yields=fx["input"]["linker_yields"],
        )
        assert real is not None
        breakeven = us_nominal_spot.fitted_yields["10Y"] - real.real_yields["10Y"]
        expected = fx["expected"]["breakeven_10Y_approx"]
        tol_bps = fx["tolerance"]["breakeven_bps"]
        assert abs(breakeven - expected) * 10_000 <= tol_bps, (
            f"breakeven_10Y={breakeven:.6f} drift={(breakeven - expected) * 10_000:.2f}bps "
            f"exceeds tolerance ±{tol_bps} bps"
        )

    def test_confidence_above_floor(
        self,
        fx: dict[str, Any],
        us_nominal_spot: nss.SpotCurve,
    ) -> None:
        real = build_real_curve(
            country_code=fx["input"]["country_code"],
            observation_date=date.fromisoformat(fx["input"]["observation_date"]),
            nominal_spot=us_nominal_spot,
            linker_yields=fx["input"]["linker_yields"],
        )
        assert real is not None
        assert real.confidence is not None
        assert real.confidence >= fx["expected"]["confidence_min"]


# ---------------------------------------------------------------------------
# de_bund_2024_01_02 — nominal NSS cross-val
# ---------------------------------------------------------------------------


class TestDeBund20240102:
    """Spec §7 fixture row 2 — Bundesbank cross-val target <5 bps."""

    @pytest.fixture
    def fx(self) -> dict[str, Any]:
        return _load_fixture("de_bund_2024_01_02")

    @pytest.fixture
    def de_spot(self, fx: dict[str, Any]) -> nss.SpotCurve:
        i = fx["input"]
        nss_in = nss.NSSInput(
            tenors_years=np.array(i["tenors_years"]),
            yields=np.array(i["yields"]),
            country_code=i["country_code"],
            observation_date=date.fromisoformat(i["observation_date"]),
            curve_input_type="par",
        )
        return nss.fit_nss(nss_in)

    def test_rmse_within_5bps(self, de_spot: nss.SpotCurve, fx: dict[str, Any]) -> None:
        max_rmse = fx["expected"]["rmse_bps_max"]
        assert de_spot.rmse_bps <= max_rmse, (
            f"DE Bund rmse_bps={de_spot.rmse_bps} exceeds spec §7 row 2 target {max_rmse}"
        )

    def test_fitted_tenors_within_tolerance(
        self,
        de_spot: nss.SpotCurve,
        fx: dict[str, Any],
    ) -> None:
        tol_bps = fx["tolerance"]["fitted_bps"]
        for tenor_label, expected_key in (
            ("2Y", "fitted_2Y_approx"),
            ("5Y", "fitted_5Y_approx"),
            ("10Y", "fitted_10Y_approx"),
        ):
            actual = de_spot.fitted_yields[tenor_label]
            expected = fx["expected"][expected_key]
            drift_bps = abs(actual - expected) * 10_000
            assert drift_bps <= tol_bps, (
                f"DE Bund {tenor_label}: actual={actual:.6f} expected={expected:.6f} "
                f"drift={drift_bps:.2f} bps exceeds ±{tol_bps} bps"
            )

    def test_confidence_above_floor(
        self,
        de_spot: nss.SpotCurve,
        fx: dict[str, Any],
    ) -> None:
        assert de_spot.confidence >= fx["expected"]["confidence_min"]


# ---------------------------------------------------------------------------
# forward_5y5y_us_2024_01_02 — nominal forward derivation
# ---------------------------------------------------------------------------


class TestForward5y5yUs20240102:
    """Spec §7 fixture row 8 — nominal 5y5y forward ≈ 0.0385 ± 10 bps."""

    @pytest.fixture
    def fx(self) -> dict[str, Any]:
        return _load_fixture("forward_5y5y_us_2024_01_02")

    @pytest.fixture
    def us_spot(self) -> nss.SpotCurve:
        nominal_fx = _load_fixture("us_2024_01_02")
        i = nominal_fx["input"]
        nss_in = nss.NSSInput(
            tenors_years=np.array(i["tenors_years"]),
            yields=np.array(i["yields"]),
            country_code=i["country_code"],
            observation_date=date.fromisoformat(i["observation_date"]),
            curve_input_type="par",
        )
        return nss.fit_nss(nss_in)

    def test_forward_5y5y_within_tolerance(
        self,
        us_spot: nss.SpotCurve,
        fx: dict[str, Any],
    ) -> None:
        zero = nss.derive_zero_curve(us_spot)
        forward = nss.derive_forward_curve(zero)
        actual = forward.forwards["5y5y"]
        expected = fx["expected"]["forward_5y5y_approx"]
        tol_bps = fx["tolerance"]["forward_bps"]
        drift_bps = abs(actual - expected) * 10_000
        assert drift_bps <= tol_bps, (
            f"5y5y={actual:.6f} drift={drift_bps:.2f} bps exceeds ±{tol_bps} bps "
            f"vs target {expected:.6f}"
        )
