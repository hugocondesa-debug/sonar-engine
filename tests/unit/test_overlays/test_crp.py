"""Unit tests for CRP overlay (Week 3 minimal — SOV_SPREAD + RATING + BENCHMARK)."""

from __future__ import annotations

from datetime import date

import pytest

from sonar.overlays.crp import (
    BENCHMARK_COUNTRIES_BY_CURRENCY,
    DAMODARAN_STANDARD_RATIO,
    build_canonical,
    compute_rating,
    compute_sov_spread,
    is_benchmark,
)
from sonar.overlays.exceptions import InsufficientDataError


class TestBenchmark:
    def test_de_is_eur_benchmark(self) -> None:
        assert is_benchmark("DE", "EUR")

    def test_us_is_usd_benchmark(self) -> None:
        assert is_benchmark("US", "USD")

    def test_pt_is_not_eur_benchmark(self) -> None:
        assert not is_benchmark("PT", "EUR")

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
            "GBP": "UK",
            "JPY": "JP",
        }

    def test_default_vol_ratio_is_15(self) -> None:
        assert DAMODARAN_STANDARD_RATIO == 1.5
