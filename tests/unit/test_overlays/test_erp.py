"""Unit tests for ERP overlay (Commit 5 — 4-method compute)."""

from __future__ import annotations

from datetime import date

import pytest

from sonar.overlays.erp import (
    DIVERGENCE_THRESHOLD_BPS,
    FORWARD_EPS_DIVERGENCE_THRESHOLD,
    G_SUSTAINABLE_CAP,
    METHODOLOGY_VERSION_CANONICAL,
    METHODOLOGY_VERSION_CAPE,
    METHODOLOGY_VERSION_DCF,
    METHODOLOGY_VERSION_EY,
    METHODOLOGY_VERSION_GORDON,
    ERPFitResult,
    ERPInput,
    _compute_canonical,
    _compute_cape,
    _compute_dcf,
    _compute_ey,
    _compute_forward_eps_divergence,
    _compute_gordon,
    fit_erp_us,
)
from sonar.overlays.exceptions import InsufficientDataError


def _us_inputs(**overrides: float | int | str | tuple[str, ...] | None) -> ERPInput:
    """Canonical US 2024-01-02 fixture — all four methods viable."""
    base: dict[str, object] = {
        "market_index": "SPX",
        "country_code": "US",
        "observation_date": date(2024, 1, 2),
        "index_level": 4742.83,
        "trailing_earnings": 221.41,
        "forward_earnings_est": 243.73,
        "dividend_yield_pct": 0.0155,
        "buyback_yield_pct": 0.025,
        "cape_ratio": 31.5,
        "risk_free_nominal": 0.0415,
        "risk_free_real": 0.0175,
        "consensus_growth_5y": 0.10,
        "retention": 0.60,
        "roe": 0.20,
        "risk_free_confidence": 0.95,
        "upstream_flags": (),
    }
    base.update(overrides)
    return ERPInput(**base)  # type: ignore[arg-type]


class TestGordon:
    def test_formula(self) -> None:
        inputs = _us_inputs()
        result = _compute_gordon(inputs)
        # dividend 0.0155 + buyback 0.025 + min(0.60*0.20, 0.06)=0.06 - 0.0415
        assert result.erp_decimal == pytest.approx(0.0155 + 0.025 + 0.06 - 0.0415)
        assert result.method == "GORDON"
        assert result.methodology_version == METHODOLOGY_VERSION_GORDON

    def test_g_sustainable_capped(self) -> None:
        # retention * roe = 0.80 * 0.25 = 0.20 > cap 0.06 → should be clamped
        inputs = _us_inputs(retention=0.80, roe=0.25)
        result = _compute_gordon(inputs)
        # 0.0155 + 0.025 + 0.06 (capped) - 0.0415
        assert result.erp_decimal == pytest.approx(0.0155 + 0.025 + G_SUSTAINABLE_CAP - 0.0415)

    def test_none_buyback_emits_stale(self) -> None:
        inputs = _us_inputs(buyback_yield_pct=None)
        result = _compute_gordon(inputs)
        assert "STALE" in result.flags
        # buyback treated as 0.0 → 0.0155 + 0 + 0.06 - 0.0415
        assert result.erp_decimal == pytest.approx(0.0155 + 0.0 + G_SUSTAINABLE_CAP - 0.0415)


class TestEY:
    def test_formula(self) -> None:
        inputs = _us_inputs()
        result = _compute_ey(inputs)
        # 243.73 / 4742.83 - 0.0415
        assert result.erp_decimal == pytest.approx(243.73 / 4742.83 - 0.0415)
        assert result.methodology_version == METHODOLOGY_VERSION_EY


class TestCAPE:
    def test_formula(self) -> None:
        inputs = _us_inputs()
        result = _compute_cape(inputs)
        # 1/31.5 - 0.0175
        assert result.erp_decimal == pytest.approx(1.0 / 31.5 - 0.0175)
        assert result.methodology_version == METHODOLOGY_VERSION_CAPE

    def test_zero_cape_raises(self) -> None:
        inputs = _us_inputs(cape_ratio=0.0)
        with pytest.raises(InsufficientDataError, match="cape_ratio"):
            _compute_cape(inputs)


class TestDCF:
    def test_converges_with_realistic_inputs(self) -> None:
        inputs = _us_inputs()
        result = _compute_dcf(inputs)
        assert result is not None
        assert result.methodology_version == METHODOLOGY_VERSION_DCF
        # With ~10% growth + ~4% payout + ~4% rf, r should land between
        # 4% (rf) and 30% (DCF_BOUNDS max); empirically near 8-12%.
        assert 0.0 <= result.erp_decimal <= 0.30

    def test_zero_payout_returns_none(self) -> None:
        inputs = _us_inputs(dividend_yield_pct=0.0, buyback_yield_pct=0.0)
        assert _compute_dcf(inputs) is None


class TestForwardEPSDivergence:
    def test_below_threshold(self) -> None:
        # 243.73 vs 245.10 → ~0.56% → below 5%
        d = _compute_forward_eps_divergence(
            243.73, 245.10, factset_fresh_days=2, yardeni_fresh_days=3
        )
        assert d is not None
        assert d < FORWARD_EPS_DIVERGENCE_THRESHOLD

    def test_above_threshold(self) -> None:
        d = _compute_forward_eps_divergence(
            240.0, 260.0, factset_fresh_days=1, yardeni_fresh_days=1
        )
        assert d is not None
        assert d > FORWARD_EPS_DIVERGENCE_THRESHOLD

    def test_stale_source_returns_none(self) -> None:
        assert (
            _compute_forward_eps_divergence(
                240.0, 260.0, factset_fresh_days=1, yardeni_fresh_days=10
            )
            is None
        )

    def test_missing_yardeni_returns_none(self) -> None:
        assert (
            _compute_forward_eps_divergence(
                240.0, None, factset_fresh_days=1, yardeni_fresh_days=None
            )
            is None
        )


class TestCanonical:
    def test_median_and_range(self) -> None:
        inputs = _us_inputs()
        dcf = _compute_dcf(inputs)
        gordon = _compute_gordon(inputs)
        ey = _compute_ey(inputs)
        cape = _compute_cape(inputs)
        canonical = _compute_canonical(
            (dcf, gordon, ey, cape),
            upstream_flags=(),
            forward_eps_divergence_pct=None,
            xval_deviation_bps=None,
        )
        assert canonical.methods_available == 4
        assert canonical.methodology_version == METHODOLOGY_VERSION_CANONICAL
        assert canonical.erp_range_bps >= 0

    def test_divergence_flag_when_range_exceeds(self) -> None:
        inputs = _us_inputs()
        # Construct methods with artificial divergence — manual results.
        gordon = _compute_gordon(inputs)
        ey = _compute_ey(inputs)
        # Force CAPE very high to widen range.
        cape_high = _compute_cape(_us_inputs(cape_ratio=5.0))
        canonical = _compute_canonical(
            (None, gordon, ey, cape_high),
            upstream_flags=(),
            forward_eps_divergence_pct=None,
            xval_deviation_bps=None,
        )
        if canonical.erp_range_bps > DIVERGENCE_THRESHOLD_BPS:
            assert "ERP_METHOD_DIVERGENCE" in canonical.flags

    def test_xval_drift_flag_when_deviation_exceeds(self) -> None:
        inputs = _us_inputs()
        gordon = _compute_gordon(inputs)
        ey = _compute_ey(inputs)
        canonical = _compute_canonical(
            (None, gordon, ey, None),
            upstream_flags=(),
            forward_eps_divergence_pct=None,
            xval_deviation_bps=25,
        )
        assert "XVAL_DRIFT" in canonical.flags

    def test_insufficient_methods_raises(self) -> None:
        inputs = _us_inputs()
        gordon = _compute_gordon(inputs)
        with pytest.raises(InsufficientDataError, match="requires 2 methods"):
            _compute_canonical(
                (None, gordon, None, None),
                upstream_flags=(),
                forward_eps_divergence_pct=None,
                xval_deviation_bps=None,
            )

    def test_confidence_deduction_per_missing_method(self) -> None:
        # Inputs tuned so Gordon and EY land within the divergence threshold
        # (range < 400 bps), isolating the missing-method deduction.
        inputs = _us_inputs(
            dividend_yield_pct=0.015,
            buyback_yield_pct=0.0,
            forward_earnings_est=280.0,  # EY ~5.9% - 4.15% = 1.75%  → 175 bps
            retention=0.50,
            roe=0.10,  # g_sustainable 0.05 < cap
        )
        gordon = _compute_gordon(inputs)
        ey = _compute_ey(inputs)
        assert abs(gordon.erp_bps - ey.erp_bps) < DIVERGENCE_THRESHOLD_BPS
        canonical = _compute_canonical(
            (None, gordon, ey, None),
            upstream_flags=(),
            forward_eps_divergence_pct=None,
            xval_deviation_bps=None,
        )
        # 2 missing → 0.05 * (4-2) = 0.10 deducted from min confidence 1.0
        assert canonical.confidence == pytest.approx(1.0 - 0.10)


class TestFitOrchestrator:
    def test_full_fit_us_happy_path(self) -> None:
        inputs = _us_inputs()
        result = fit_erp_us(inputs)
        assert isinstance(result, ERPFitResult)
        assert result.market_index == "SPX"
        assert result.canonical.methods_available == 4
        assert result.dcf is not None
        assert result.gordon is not None
        assert result.ey is not None
        assert result.cape is not None
        assert result.erp_id is not None

    def test_low_risk_free_confidence_raises(self) -> None:
        inputs = _us_inputs(risk_free_confidence=0.40)
        with pytest.raises(InsufficientDataError, match="risk_free_confidence"):
            fit_erp_us(inputs)

    def test_dcf_failure_still_yields_3_methods(self) -> None:
        # Zero payout kills DCF but other methods remain.
        inputs = _us_inputs(dividend_yield_pct=0.0, buyback_yield_pct=0.0)
        result = fit_erp_us(inputs)
        assert result.dcf is None
        assert result.canonical.methods_available == 3

    def test_bps_conversion_is_banker_rounded(self) -> None:
        inputs = _us_inputs()
        result = fit_erp_us(inputs)
        for method in (result.gordon, result.ey, result.cape):
            assert method is not None
            assert method.erp_bps == round(method.erp_decimal * 10_000)
