"""Sprint 3 — fixture tests against the ``sonar.overlays.erp_daily`` namespace.

Validates the public re-export surface of :mod:`sonar.overlays.erp_daily`
and exercises the spec §7 fixture set via the new namespace. The
existing :mod:`tests.unit.test_overlays.test_erp_behavioral` suite
covers the same fixtures through the underlying :mod:`sonar.overlays.erp`
import path; this module pins the ``erp_daily`` re-export contract so
callers wiring through the new namespace (CLI ``sonar backfill
erp-daily``, future EA/UK/JP backfills) read consistent values.

Also adds explicit coverage for the Sprint 3 DELTA 2 fix: DCF Newton
non-convergence emits ``NSS_FAIL`` on the canonical row per spec §6,
distinct from zero-payout (which is a data-miss, not a Newton
failure, and emits no flag).
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from sonar.overlays.erp_daily import ERPInput, fit_erp_us

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "erp-daily"


def _load_fixture(name: str) -> dict:
    with (FIXTURE_DIR / name).open() as f:
        return json.load(f)


def _make_input(inputs_dict: dict) -> ERPInput:
    d = dict(inputs_dict)
    d["observation_date"] = date.fromisoformat(d["observation_date"])
    d["upstream_flags"] = tuple(d.get("upstream_flags", []))
    return ERPInput(**d)


class TestUS20240102:
    """Fixture ``us_2024_01_02`` — full 4-method fit baseline."""

    fixture = "us_2024_01_02.json"

    @pytest.fixture
    def data(self) -> dict:
        return _load_fixture(self.fixture)

    def test_methods_available_is_four(self, data: dict) -> None:
        result = fit_erp_us(_make_input(data["inputs"]))
        assert result.canonical.methods_available == data["expected"]["methods_available"]

    def test_per_method_bps_within_tolerance(self, data: dict) -> None:
        result = fit_erp_us(_make_input(data["inputs"]))
        exp = data["expected"]
        tol = exp["tolerance_bps_per_method"]
        assert result.dcf is not None
        assert abs(result.dcf.erp_bps - exp["dcf_bps"]) <= tol
        assert result.gordon is not None
        assert abs(result.gordon.erp_bps - exp["gordon_bps"]) <= tol
        assert result.ey is not None
        assert abs(result.ey.erp_bps - exp["ey_bps"]) <= tol
        assert result.cape is not None
        assert abs(result.cape.erp_bps - exp["cape_bps"]) <= tol

    def test_canonical_median_within_tolerance(self, data: dict) -> None:
        result = fit_erp_us(_make_input(data["inputs"]))
        exp = data["expected"]
        assert (
            abs(result.canonical.erp_median_bps - exp["median_bps"]) <= exp["tolerance_bps_median"]
        )

    def test_no_nss_fail_on_normal_fit(self, data: dict) -> None:
        # DELTA 2 negative: 4-method viable fit must not emit NSS_FAIL.
        result = fit_erp_us(_make_input(data["inputs"]))
        assert "NSS_FAIL" not in result.canonical.flags


class TestUSPartial3Methods:
    """Fixture ``us_partial_3methods`` — zero payout skips DCF without NSS_FAIL."""

    fixture = "us_partial_3methods.json"

    @pytest.fixture
    def data(self) -> dict:
        return _load_fixture(self.fixture)

    def test_dcf_absent_methods_three(self, data: dict) -> None:
        result = fit_erp_us(_make_input(data["inputs"]))
        assert result.dcf is None
        assert result.canonical.methods_available == 3

    def test_no_nss_fail_on_zero_payout(self, data: dict) -> None:
        # DELTA 2 positive: zero-payout is a data miss, not a Newton failure.
        # Fixture sets dividend_yield_pct=buyback_yield_pct=0 → DCF skipped
        # without attempting Newton, so NSS_FAIL must not fire (per spec
        # §6 row "DCF Newton não convergiu" applies only to convergence
        # failures, not pre-empted attempts).
        result = fit_erp_us(_make_input(data["inputs"]))
        assert "NSS_FAIL" not in result.canonical.flags


class TestDivergence:
    """Fixture ``us_divergence_2020_03_23`` — COVID-trough stress, range > 400 bps."""

    fixture = "us_divergence_2020_03_23.json"

    @pytest.fixture
    def data(self) -> dict:
        return _load_fixture(self.fixture)

    def test_erp_method_divergence_flag(self, data: dict) -> None:
        result = fit_erp_us(_make_input(data["inputs"]))
        assert "ERP_METHOD_DIVERGENCE" in result.canonical.flags
        assert result.canonical.erp_range_bps > 400

    def test_confidence_deducted_for_divergence(self, data: dict) -> None:
        result = fit_erp_us(_make_input(data["inputs"]))
        # Spec §6: ERP_METHOD_DIVERGENCE -> -0.10 on canonical confidence.
        assert abs(result.canonical.confidence - 0.90) <= 0.02


class TestDamodaranXval:
    """Fixture ``damodaran_xval_2024_01_31`` — DCF matches histimpl within 20 bps."""

    fixture = "damodaran_xval_2024_01_31.json"

    @pytest.fixture
    def data(self) -> dict:
        return _load_fixture(self.fixture)

    def test_xval_deviation_within_threshold(self, data: dict) -> None:
        inputs = _make_input(data["inputs"])
        dam = data["damodaran_erp_decimal"]
        result = fit_erp_us(inputs, damodaran_erp_decimal=dam)
        assert result.canonical.xval_deviation_bps is not None
        assert result.canonical.xval_deviation_bps <= data["expected"]["xval_deviation_bps_max"]

    def test_no_xval_drift_flag(self, data: dict) -> None:
        inputs = _make_input(data["inputs"])
        result = fit_erp_us(inputs, damodaran_erp_decimal=data["damodaran_erp_decimal"])
        assert "XVAL_DRIFT" not in result.canonical.flags


class TestNSSFailEmission:
    """Sprint 3 DELTA 2 — DCF Newton non-convergence emits NSS_FAIL.

    Spec §6 row "DCF Newton não convergiu | catch ConvergenceError;
    skip DCF; flag NSS_FAIL (reemit)". Pre-Sprint-3 behaviour silently
    returned ``None`` without surfacing the failure flag — this test
    pins the corrected emission so downstream consumers see the
    methodology-stress signal.
    """

    def _payout_starved_inputs(self) -> ERPInput:
        # Construct numerics that force scipy.optimize.newton to fail
        # (tiny payout vs huge price → residual surface near-flat at x0,
        # Newton's first iteration overshoots the tolerance → RuntimeError).
        return ERPInput(
            market_index="SPX",
            country_code="US",
            observation_date=date(2024, 1, 2),
            index_level=4742.83,
            trailing_earnings=0.001,
            forward_earnings_est=243.73,
            dividend_yield_pct=1e-9,
            buyback_yield_pct=0.0,
            cape_ratio=31.5,
            risk_free_nominal=0.0415,
            risk_free_real=0.0175,
            consensus_growth_5y=0.0,
            retention=0.60,
            roe=0.20,
            risk_free_confidence=0.95,
            upstream_flags=(),
        )

    def test_dcf_skipped_methods_three(self) -> None:
        result = fit_erp_us(self._payout_starved_inputs())
        assert result.dcf is None
        assert result.canonical.methods_available == 3

    def test_canonical_emits_nss_fail(self) -> None:
        result = fit_erp_us(self._payout_starved_inputs())
        assert "NSS_FAIL" in result.canonical.flags

    def test_zero_payout_does_not_emit_nss_fail(self) -> None:
        # Zero-payout never attempts Newton — it is a data miss, not a
        # convergence failure. NSS_FAIL must not fire so consumers can
        # distinguish "no DCF input" from "DCF tried + failed".
        starved = self._payout_starved_inputs()
        zero = replace(starved, dividend_yield_pct=0.0, trailing_earnings=221.41)
        result = fit_erp_us(zero)
        assert result.dcf is None
        assert "NSS_FAIL" not in result.canonical.flags
