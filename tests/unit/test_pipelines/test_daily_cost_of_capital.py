"""Unit tests for daily_cost_of_capital compose_k_e + build helpers."""

from __future__ import annotations

from datetime import date

import pytest

from sonar.overlays.crp import CRPCanonical, build_canonical, compute_sov_spread
from sonar.pipelines.daily_cost_of_capital import (
    COUNTRY_TO_CURRENCY,
    DAMODARAN_MATURE_ERP_BPS,
    DAMODARAN_MATURE_ERP_DECIMAL,
    T1_7_COUNTRIES,
    compose_k_e,
)


def _make_crp(country: str, crp_bps: int, flags: tuple[str, ...] = ()) -> CRPCanonical:
    return CRPCanonical(
        crp_id=__import__("uuid").uuid4(),
        country_code=country,
        observation_date=date(2024, 1, 2),
        method_selected="SOV_SPREAD",
        crp_canonical_bps=crp_bps,
        default_spread_bps=crp_bps,
        vol_ratio=1.5,
        vol_ratio_source="damodaran_standard",
        crp_cds_bps=None,
        crp_sov_spread_bps=crp_bps,
        crp_rating_bps=None,
        basis_default_spread_sov_minus_cds_bps=None,
        confidence=0.9,
        flags=flags,
    )


class TestComposeKE:
    def test_us_benchmark_plus_erp_equals_rf_plus_erp(self) -> None:
        # US is benchmark → crp_canonical_bps = 0.
        crp = build_canonical(
            country_code="US",
            observation_date=date(2024, 1, 2),
            currency="USD",
        )
        rf = 0.04  # 4% nominal 10Y
        result = compose_k_e(
            country_code="US",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=rf,
            crp=crp,
            beta=1.0,
        )
        # k_e = rf + 1.0 * 5.5% + 0% = 9.5%
        assert result.k_e_pct == pytest.approx(0.095)
        assert result.crp_bps == 0

    def test_pt_adds_crp_spread(self) -> None:
        # PT 10Y = 3.10%, DE 10Y = 2.13% → SOV spread ≈ 97 bps → CRP ≈ 146 bps
        sov = compute_sov_spread(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            sov_yield_country_pct=0.0310,
            sov_yield_benchmark_pct=0.0213,
        )
        crp = build_canonical(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            sov_spread=sov,
            currency="EUR",
        )
        result = compose_k_e(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=0.0310,
            crp=crp,
            beta=1.0,
        )
        # k_e = 3.10% + 5.50% + 1.46% ≈ 10.06%
        assert 0.095 <= result.k_e_pct <= 0.105
        assert result.crp_bps >= 100

    def test_beta_scaling(self) -> None:
        crp = _make_crp("PT", 146)
        result_b1 = compose_k_e(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=0.031,
            crp=crp,
            beta=1.0,
        )
        result_b2 = compose_k_e(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=0.031,
            crp=crp,
            beta=1.2,
        )
        # Delta should be 0.2 * ERP = 0.2 * 5.5% = 1.1%.
        assert result_b2.k_e_pct - result_b1.k_e_pct == pytest.approx(0.011, abs=1e-5)


class TestConstants:
    def test_damodaran_erp_55pct(self) -> None:
        assert DAMODARAN_MATURE_ERP_DECIMAL == 0.055
        assert DAMODARAN_MATURE_ERP_BPS == 550

    def test_t1_7_countries_complete(self) -> None:
        assert set(T1_7_COUNTRIES) == {"US", "DE", "PT", "IT", "ES", "FR", "NL"}

    def test_country_currency_mapping_complete(self) -> None:
        for c in T1_7_COUNTRIES:
            assert c in COUNTRY_TO_CURRENCY
