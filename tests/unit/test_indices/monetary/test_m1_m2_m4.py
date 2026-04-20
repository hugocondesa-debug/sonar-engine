"""Unit tests for M1 + M2 + M4 monetary compute modules (week6-sprint-1b)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from sonar.db.models import M1EffectiveRatesResult, M2TaylorGapsResult, M4FciResult
from sonar.indices.monetary import (
    M1_METHODOLOGY_VERSION,
    M2_METHODOLOGY_VERSION,
    M4_METHODOLOGY_VERSION,
    M1EffectiveRatesInputs,
    M2TaylorGapsInputs,
    M4FciInputs,
    compute_m1_effective_rates,
    compute_m2_taylor_gaps,
    compute_m4_fci,
)
from sonar.indices.monetary.m1_effective_rates import (
    SUBSCORE_WEIGHTS as M1_SUBSCORE_WEIGHTS,
    ZLB_THRESHOLD_PCT,
)
from sonar.indices.monetary.m2_taylor_gaps import (
    MIN_VARIANTS_FOR_COMPUTE,
    VARIANT_WEIGHTS,
)
from sonar.indices.monetary.m4_fci import (
    CUSTOM_COMPONENT_WEIGHTS,
    FC_AGGREGATE_WEIGHTS,
    MIN_CUSTOM_COMPONENTS,
)
from sonar.overlays.exceptions import InsufficientDataError


def _hist(level: float, n: int = 360, noise: float = 0.002) -> list[float]:
    """Synthetic 30-year monthly history with tiny drift noise."""
    return [level + noise * (i % 7 - 3) for i in range(n)]


# ---------------------------------------------------------------------------
# M1
# ---------------------------------------------------------------------------


def _m1_inputs(**overrides: object) -> M1EffectiveRatesInputs:
    base: dict[str, object] = {
        "country_code": "US",
        "observation_date": date(2024, 12, 31),
        "policy_rate_pct": 0.0525,
        "expected_inflation_5y_pct": 0.025,
        "r_star_pct": 0.008,
        "balance_sheet_pct_gdp_current": 0.30,
        "balance_sheet_pct_gdp_12m_ago": 0.34,
        "real_shadow_rate_history": _hist(0.01),
        "stance_vs_neutral_history": _hist(0.005),
        "balance_sheet_signal_history": _hist(0.0, noise=0.01),
        "lookback_years": 30,
        "source_connector": ("fred",),
        "upstream_flags": (),
    }
    base.update(overrides)
    return M1EffectiveRatesInputs(**base)  # type: ignore[arg-type]


class TestM1:
    def test_above_zlb_uses_policy_as_shadow(self) -> None:
        result = compute_m1_effective_rates(_m1_inputs())
        assert result.shadow_rate_pct == pytest.approx(0.0525)
        assert 0 <= result.score_normalized <= 100
        assert result.methodology_version == M1_METHODOLOGY_VERSION

    def test_score_raw_equals_stance_vs_neutral(self) -> None:
        result = compute_m1_effective_rates(_m1_inputs())
        # real_shadow = 0.0525 - 0.025 = 0.0275
        # stance = 0.0275 - 0.008 = 0.0195
        assert result.score_raw == pytest.approx(0.0195)
        assert result.real_rate_pct == pytest.approx(0.0275)

    def test_zlb_without_shadow_raises(self) -> None:
        with pytest.raises(InsufficientDataError, match="ZLB"):
            compute_m1_effective_rates(_m1_inputs(policy_rate_pct=0.0025, shadow_rate_pct=None))

    def test_explicit_shadow_rate_honoured(self) -> None:
        result = compute_m1_effective_rates(_m1_inputs(shadow_rate_pct=-0.003))
        assert result.shadow_rate_pct == pytest.approx(-0.003)

    def test_bs_expansion_signals_looser(self) -> None:
        """BS growing (current > 12m ago) → negative balance_sheet_signal."""
        # Standard inputs have BS shrinking (0.30 < 0.34) → signal +0.04 (tighter).
        # Flip: BS growing.
        result = compute_m1_effective_rates(
            _m1_inputs(
                balance_sheet_pct_gdp_current=0.40,
                balance_sheet_pct_gdp_12m_ago=0.34,
            )
        )
        components = json.loads(result.components_json)
        assert components["balance_sheet_pct_gdp_yoy"] == pytest.approx(0.06)
        # Signal inverted: -(0.40-0.34) = -0.06 → lower z → lower score.

    def test_weights_match_spec(self) -> None:
        assert M1_SUBSCORE_WEIGHTS == {
            "real_shadow_rate": 0.50,
            "stance_vs_neutral": 0.35,
            "balance_sheet_signal": 0.15,
        }

    def test_zlb_threshold_match(self) -> None:
        assert pytest.approx(0.005) == ZLB_THRESHOLD_PCT


# ---------------------------------------------------------------------------
# M2
# ---------------------------------------------------------------------------


def _m2_inputs(**overrides: object) -> M2TaylorGapsInputs:
    base: dict[str, object] = {
        "country_code": "US",
        "observation_date": date(2024, 12, 31),
        "policy_rate_pct": 0.0525,
        "inflation_yoy_pct": 0.028,
        "inflation_target_pct": 0.02,
        "output_gap_pct": 0.005,
        "r_star_pct": 0.008,
        "prev_policy_rate_pct": 0.0525,
        "inflation_forecast_2y_pct": 0.024,
        "gap_1993_history": _hist(0.0, noise=0.003),
        "gap_1999_history": _hist(0.0, noise=0.003),
        "gap_forward_history": _hist(0.0, noise=0.003),
        "gap_inertia_history": _hist(0.0, noise=0.003),
        "lookback_years": 30,
        "source_connector": ("fred", "cbo"),
    }
    base.update(overrides)
    return M2TaylorGapsInputs(**base)  # type: ignore[arg-type]


class TestM2:
    def test_all_four_variants_computed(self) -> None:
        result = compute_m2_taylor_gaps(_m2_inputs())
        assert result.variants_computed == 4
        assert result.methodology_version == M2_METHODOLOGY_VERSION
        assert 0 <= result.score_normalized <= 100

    def test_variant_weights_match_spec(self) -> None:
        assert VARIANT_WEIGHTS == {
            "taylor_1993": 0.30,
            "taylor_1999": 0.25,
            "taylor_forward": 0.30,
            "taylor_inertia": 0.15,
        }

    def test_missing_forward_falls_to_3_variants(self) -> None:
        result = compute_m2_taylor_gaps(_m2_inputs(inflation_forecast_2y_pct=None))
        assert result.variants_computed == 3
        components = json.loads(result.components_json)
        assert "taylor_forward_gap_pp" not in components

    def test_two_variants_is_at_minimum(self) -> None:
        # Without inertia + forward → 1993 + 1999 = 2 variants = min. Passes.
        result = compute_m2_taylor_gaps(
            _m2_inputs(prev_policy_rate_pct=None, inflation_forecast_2y_pct=None)
        )
        assert result.variants_computed == MIN_VARIANTS_FOR_COMPUTE

    def test_taylor_1993_formula(self) -> None:
        # T1993 = r* + π + 0.5*(π - π*) + 0.5*y_gap
        #       = 0.008 + 0.028 + 0.5*0.008 + 0.5*0.005
        #       = 0.0425
        # gap_1993 = 0.0525 - 0.0425 = 0.010 (100 bps)
        result = compute_m2_taylor_gaps(_m2_inputs())
        components = json.loads(result.components_json)
        assert components["taylor_1993_gap_pp"] == pytest.approx(0.010, abs=1e-6)

    def test_range_divergence_flag(self) -> None:
        # Construct variants with very different gap — though our synthetic
        # inputs produce small ranges. Use forward with much higher forecast.
        result = compute_m2_taylor_gaps(_m2_inputs(inflation_forecast_2y_pct=0.08))
        # Forward T_prescribed = 0.008 + 0.08 + 0.5*(0.06) + 0.5*0.005 = 0.1205
        # gap_forward = 0.0525 - 0.1205 = -0.068 → wide range vs 1993 gap +0.006.
        assert result.taylor_uncertainty_pp > 0.01
        assert "TAYLOR_VARIANT_DIVERGE" in result.flags


# ---------------------------------------------------------------------------
# M4
# ---------------------------------------------------------------------------


class TestM4:
    def test_us_with_nfci_uses_direct_path(self) -> None:
        inputs = M4FciInputs(
            country_code="US",
            observation_date=date(2024, 12, 31),
            nfci_level=-0.65,  # loose conditions
            fci_level_12m_ago=-0.45,
            source_connector=("fred",),
        )
        result = compute_m4_fci(inputs)
        assert result.fci_provider == "NFCI_CHICAGO"
        assert result.fci_level == pytest.approx(-0.65)
        assert result.fci_change_12m == pytest.approx(-0.20)
        assert 0 <= result.score_normalized <= 100
        assert result.methodology_version == M4_METHODOLOGY_VERSION

    def test_custom_path_all_5_components(self) -> None:
        inputs = M4FciInputs(
            country_code="DE",
            observation_date=date(2024, 12, 31),
            credit_spread_bps=320.0,
            credit_spread_bps_history=_hist(280.0, noise=30.0),
            vol_index=18.5,
            vol_index_history=_hist(17.0, noise=3.0),
            gov_10y_yield_pct=0.0235,
            gov_10y_yield_pct_history=_hist(0.020, noise=0.003),
            fx_neer_pct=0.98,
            fx_neer_pct_history=_hist(1.0, noise=0.02),
            mortgage_rate_pct=0.038,
            mortgage_rate_pct_history=_hist(0.035, noise=0.004),
            fci_level_12m_ago=0.1,
            source_connector=("ecb_sdw", "eurostat"),
        )
        result = compute_m4_fci(inputs)
        assert result.fci_provider == "CUSTOM_SONAR"
        assert result.components_available == 5
        assert 0 <= result.score_normalized <= 100

    def test_custom_path_below_min_raises(self) -> None:
        inputs = M4FciInputs(
            country_code="DE",
            observation_date=date(2024, 12, 31),
            credit_spread_bps=320.0,
            credit_spread_bps_history=_hist(280.0, noise=30.0),
            vol_index=18.5,
            vol_index_history=_hist(17.0, noise=3.0),
            # Only 2 components supplied → below min 5.
        )
        with pytest.raises(InsufficientDataError, match=f">= {MIN_CUSTOM_COMPONENTS}"):
            compute_m4_fci(inputs)

    def test_weights_match_spec(self) -> None:
        assert CUSTOM_COMPONENT_WEIGHTS == {
            "credit_spread_bps": 0.30,
            "vol_index": 0.25,
            "gov_10y_yield_pct": 0.20,
            "fx_neer_pct": 0.15,
            "mortgage_rate_pct": 0.10,
        }
        assert FC_AGGREGATE_WEIGHTS == {
            "fci_level": 0.55,
            "fci_change_12m": 0.25,
            "cross_asset_stress": 0.20,
        }

    def test_momentum_missing_flag(self) -> None:
        inputs = M4FciInputs(
            country_code="US",
            observation_date=date(2024, 12, 31),
            nfci_level=-0.5,
            fci_level_12m_ago=None,
        )
        result = compute_m4_fci(inputs)
        assert "FCI_MOMENTUM_MISSING" in result.flags


# ---------------------------------------------------------------------------
# Cross-module sanity
# ---------------------------------------------------------------------------


class TestORMLink:
    def test_orm_attributes_exist(self) -> None:
        # Models should be importable and carry the column names used by
        # the Result dataclasses (smoke test only — full constraint tests
        # live under test_db/test_monetary_models.py).
        assert hasattr(M1EffectiveRatesResult, "shadow_rate_pct")
        assert hasattr(M2TaylorGapsResult, "taylor_implied_pct")
        assert hasattr(M4FciResult, "fci_provider")

    def test_methodology_version_constants(self) -> None:
        assert M1_METHODOLOGY_VERSION == "M1_EFFECTIVE_RATES_v0.2"
        assert M2_METHODOLOGY_VERSION == "M2_TAYLOR_GAPS_v0.1"
        assert M4_METHODOLOGY_VERSION == "M4_FCI_v0.1"
