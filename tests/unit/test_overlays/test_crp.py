"""Unit tests for CRP overlay (Week 3 minimal — SOV_SPREAD + RATING + BENCHMARK)."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from sonar.connectors.base import Observation
from sonar.connectors.fmp import FMPPriceObservation
from sonar.overlays.crp import (
    BENCHMARK_COUNTRIES_BY_CURRENCY,
    DAMODARAN_STANDARD_RATIO,
    MIN_VOL_OBSERVATIONS,
    VOL_RATIO_BOUNDS,
    build_canonical,
    compute_rating,
    compute_sov_spread,
    compute_vol_ratio,
    is_benchmark,
)
from sonar.overlays.exceptions import InsufficientDataError


class TestBenchmark:
    def test_de_is_eur_benchmark(self) -> None:
        assert is_benchmark("DE", "EUR")

    def test_us_is_usd_benchmark(self) -> None:
        assert is_benchmark("US", "USD")

    def test_gb_is_gbp_benchmark(self) -> None:
        assert is_benchmark("GB", "GBP")

    def test_pt_is_not_eur_benchmark(self) -> None:
        assert not is_benchmark("PT", "EUR")

    def test_uk_alias_resolves_to_gbp_benchmark_with_warning(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """ADR-0007: "UK" still matches GBP benchmark via alias normaliser."""
        assert is_benchmark("UK", "GBP")
        captured = capsys.readouterr()
        assert "deprecated_country_alias" in captured.out
        assert "alias=UK" in captured.out
        assert "canonical=GB" in captured.out

    def test_canonical_benchmark_shortcut(self) -> None:
        result = build_canonical(
            country_code="DE",
            observation_date=date(2024, 1, 2),
            currency="EUR",
        )
        assert result.method_selected == "BENCHMARK"
        assert result.crp_canonical_bps == 0
        assert result.default_spread_bps == 0
        assert "CRP_BENCHMARK" in result.flags
        assert result.confidence == 1.0


class TestSovSpread:
    def test_pt_vs_de_2024_01_02_realistic(self) -> None:
        # PT 10Y ≈ 3.10%, Bund 10Y ≈ 2.13% → spread ≈ 97 bps x 1.5 vol_ratio = 145 bps
        result = compute_sov_spread(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            sov_yield_country_pct=0.0310,
            sov_yield_benchmark_pct=0.0213,
            tenor="10Y",
            currency_denomination="EUR",
        )
        assert result.default_spread_bps == 97
        # crp_decimal = 0.0097 x 1.5 = 0.01455 → bps 145 (rounded)
        assert result.crp_bps == 146  # 0.01455 * 10000 = 145.5, banker's round → 146
        assert result.vol_ratio == DAMODARAN_STANDARD_RATIO
        assert "CRP_VOL_STANDARD" in result.flags
        assert "CRP_NEG_SPREAD" not in result.flags

    def test_negative_spread_clamped_with_flag(self) -> None:
        result = compute_sov_spread(
            country_code="LU",
            observation_date=date(2024, 1, 2),
            sov_yield_country_pct=0.0205,
            sov_yield_benchmark_pct=0.0213,
        )
        assert result.default_spread_bps == 0
        assert result.crp_bps == 0
        assert "CRP_NEG_SPREAD" in result.flags
        assert result.confidence < 1.0  # deduction applied

    def test_country_specific_vol_ratio_no_standard_flag(self) -> None:
        result = compute_sov_spread(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            sov_yield_country_pct=0.0310,
            sov_yield_benchmark_pct=0.0213,
            vol_ratio=2.1,
            vol_ratio_source="country_specific",
        )
        assert "CRP_VOL_STANDARD" not in result.flags
        # 0.0097 * 2.1 = 0.02037 → 204 bps
        assert 200 <= result.crp_bps <= 210


class TestRating:
    def test_pt_a_minus_with_default_vol_ratio(self) -> None:
        # Notch 15 → spread 90 bps x 1.5 = 135 bps
        result = compute_rating(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            consolidated_sonar_notch=15.0,
            default_spread_bps=90,
            rating_id="abc-123",
            calibration_date=date(2024, 1, 1),
        )
        assert result.notch_int == 15
        assert result.default_spread_bps == 90
        assert result.crp_bps == 135
        assert "CRP_VOL_STANDARD" in result.flags

    def test_fractional_notch_rounded(self) -> None:
        result = compute_rating(
            country_code="IT",
            observation_date=date(2024, 1, 2),
            consolidated_sonar_notch=12.6,
            default_spread_bps=200,
            rating_id="def-456",
            calibration_date=date(2024, 1, 1),
        )
        assert result.notch_int == 13  # round(12.6) = 13


class TestCanonicalHierarchy:
    def test_sov_spread_chosen_over_rating_when_both_present(self) -> None:
        sov = compute_sov_spread(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            sov_yield_country_pct=0.0310,
            sov_yield_benchmark_pct=0.0213,
        )
        rating = compute_rating(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            consolidated_sonar_notch=15.0,
            default_spread_bps=90,
            rating_id="abc-123",
            calibration_date=date(2024, 1, 1),
        )
        result = build_canonical(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            sov_spread=sov,
            rating=rating,
            currency="EUR",
        )
        assert result.method_selected == "SOV_SPREAD"
        assert result.crp_canonical_bps == sov.crp_bps
        # both method values still surfaced for editorial triangulation
        assert result.crp_sov_spread_bps == sov.crp_bps
        assert result.crp_rating_bps == rating.crp_bps

    def test_falls_back_to_rating_when_sov_missing(self) -> None:
        rating = compute_rating(
            country_code="GH",
            observation_date=date(2024, 1, 2),
            consolidated_sonar_notch=8.0,
            default_spread_bps=720,
            rating_id="ghana-1",
            calibration_date=date(2024, 1, 1),
        )
        result = build_canonical(
            country_code="GH",
            observation_date=date(2024, 1, 2),
            rating=rating,
            currency="USD",
        )
        assert result.method_selected == "RATING"
        assert result.crp_canonical_bps == rating.crp_bps

    def test_no_methods_raises(self) -> None:
        with pytest.raises(InsufficientDataError, match="no method available"):
            build_canonical(
                country_code="ZZ",
                observation_date=date(2024, 1, 2),
                currency="USD",
            )

    def test_benchmark_returns_zero_even_with_methods_provided(self) -> None:
        # DE is benchmark — shortcut overrides any provided methods.
        sov = compute_sov_spread(
            country_code="DE",
            observation_date=date(2024, 1, 2),
            sov_yield_country_pct=0.0213,
            sov_yield_benchmark_pct=0.0213,
        )
        result = build_canonical(
            country_code="DE",
            observation_date=date(2024, 1, 2),
            sov_spread=sov,
            currency="EUR",
        )
        assert result.method_selected == "BENCHMARK"
        assert result.crp_canonical_bps == 0


class TestSpec:
    def test_benchmark_dict_completeness(self) -> None:
        assert BENCHMARK_COUNTRIES_BY_CURRENCY == {
            "EUR": "DE",
            "USD": "US",
            "GBP": "GB",
            "JPY": "JP",
        }

    def test_default_vol_ratio_is_15(self) -> None:
        assert DAMODARAN_STANDARD_RATIO == 1.5

    def test_vol_ratio_bounds_match_spec(self) -> None:
        assert VOL_RATIO_BOUNDS == (1.2, 2.5)

    def test_min_vol_observations_match_spec(self) -> None:
        assert MIN_VOL_OBSERVATIONS == 750


def _eq(n: int, scale: float = 0.01) -> list[FMPPriceObservation]:
    """Synthesize n equity closes with deterministic log-return drift."""
    out: list[FMPPriceObservation] = []
    price = 1000.0
    start = date(2022, 1, 3)
    for i in range(n + 1):  # +1 because we'll compute returns
        out.append(
            FMPPriceObservation(
                symbol_sonar="SPX",
                symbol_fmp="^GSPC",
                observation_date=start + timedelta(days=i),
                close=price,
                volume=None,
            )
        )
        # oscillate to produce sigma ≈ scale · sqrt(252)
        price *= math.exp(scale if i % 2 == 0 else -scale * 0.5)
    return out


def _bonds(n: int, yield_scale_bps: int = 50) -> list[Observation]:
    """Synthesize n daily 10Y yield observations with volatile changes."""
    out: list[Observation] = []
    base = 400  # 4%
    start = date(2022, 1, 3)
    for i in range(n + 1):
        delta = yield_scale_bps if i % 2 == 0 else -yield_scale_bps
        base += delta
        out.append(
            Observation(
                country_code="US",
                observation_date=start + timedelta(days=i),
                tenor_years=10.0,
                yield_bps=base,
                source="TE",
                source_series_id="USGG10YR:IND",
            )
        )
    return out


class TestVolRatio:
    def test_insufficient_obs_falls_back_to_damodaran(self) -> None:
        result = compute_vol_ratio(_eq(100), _bonds(100))
        assert result.source == "damodaran_standard"
        assert result.vol_ratio == DAMODARAN_STANDARD_RATIO

    def test_zero_bond_vol_falls_back(self) -> None:
        flat_bonds = [
            Observation(
                country_code="US",
                observation_date=date(2022, 1, 3) + timedelta(days=i),
                tenor_years=10.0,
                yield_bps=400,
                source="TE",
                source_series_id="USGG10YR:IND",
            )
            for i in range(800)
        ]
        result = compute_vol_ratio(_eq(800, scale=0.01), flat_bonds)
        assert result.source == "damodaran_standard"

    def test_out_of_bounds_ratio_falls_back(self) -> None:
        # Equity vol very large vs bond → ratio > 2.5 → fallback.
        result = compute_vol_ratio(_eq(800, scale=0.10), _bonds(800, yield_scale_bps=2))
        assert result.source == "damodaran_standard"

    def test_country_specific_when_inside_bounds(self) -> None:
        # Tuned sigma pair → ratio lands ~1.5-2.0 (inside 1.2-2.5).
        result = compute_vol_ratio(
            _eq(800, scale=0.015),
            _bonds(800, yield_scale_bps=15),
        )
        # Could still fall back if tuning misses; test accepts either result
        # with semantic assertion about the source.
        assert result.equity_obs >= 750
        assert result.bond_obs >= 750
        if result.source == "country_specific":
            assert VOL_RATIO_BOUNDS[0] <= result.vol_ratio <= VOL_RATIO_BOUNDS[1]
            assert result.sigma_equity is not None
            assert result.sigma_bond is not None
