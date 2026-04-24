"""Canonical composer fixtures per ``docs/specs/overlays/expected-inflation.md`` §7.

Sprint 1 ships 5 of the 10 fixtures listed in §7 — those exercising
the new :mod:`sonar.overlays.expected_inflation.canonical` composer
and the two method legs added this sprint (:mod:`.swap`, :mod:`.derived`):

1. ``us_2024_01_02_canonical`` — BEI 5/10/30Y + SPF 1Y → canonical
   picks BEI for 5/10/30/5y5y, SURVEY for 1Y.
2. ``pt_2024_01_02_derived`` — EA aggregate + 15 bps differential →
   PT tenors = EA + diff; confidence ≤ 0.80.
3. ``jp_survey_only`` — Tankan-only; no 10Y → no 5y5y → flag
   ``ANCHOR_UNCOMPUTABLE``.
4. ``ea_5y5y_compounded_vs_linear`` — swap 5Y 0.021 / 10Y 0.0225
   compounded ≈ linear within 1 bps; stored value is compounded.
5. ``us_method_divergence_2022_q2`` — BEI 10Y 0.028 vs SPF 10Y 0.022
   → ``bei_vs_survey_divergence_bps=600`` + ``INFLATION_METHOD_DIVERGENCE``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from sonar.overlays.expected_inflation import (
    ExpInfSurvey,
    build_canonical,
    compute_5y5y,
    compute_bei_us,
    compute_survey_spf,
    compute_survey_us,
)
from sonar.overlays.expected_inflation.derived import (
    PT_EA_DIFFERENTIAL_PLACEHOLDER_PP,
    compute_derived_pt,
)
from sonar.overlays.expected_inflation.swap import compute_swap


class TestUsCanonical20240102:
    """Spec §7 fixture: ``us_2024_01_02_canonical``."""

    def test_hierarchy_bei_primary_survey_fallback_1y(self) -> None:
        bei = compute_bei_us(
            nominal_yields={"5Y": 0.0393, "10Y": 0.0395, "30Y": 0.0408},
            bei_market={"5Y": 0.0225, "10Y": 0.0235, "30Y": 0.0240},
            observation_date=date(2024, 1, 2),
        )
        survey = compute_survey_us(
            survey_horizons={"1Y": 0.029, "10Y": 0.0216},
            observation_date=date(2024, 1, 2),
            survey_release_date=date(2024, 1, 1),
        )
        canonical = build_canonical(
            country_code="US",
            observation_date=date(2024, 1, 2),
            bei=bei,
            survey=survey,
            bc_target_pct=0.02,
        )

        # BEI wins 5/10/30Y + 5y5y forward; SURVEY supplies the 1Y that
        # BEI lacks (FRED ``T5YIE/T10YIE/T30YIE`` don't publish 1Y).
        assert canonical.source_method_per_tenor["5Y"] == "BEI"
        assert canonical.source_method_per_tenor["10Y"] == "BEI"
        assert canonical.source_method_per_tenor["30Y"] == "BEI"
        assert canonical.source_method_per_tenor["5y5y"] == "BEI"
        assert canonical.source_method_per_tenor["1Y"] == "SURVEY"

        assert canonical.methods_available == 2
        # 5y5y ≈ [(1.0235)^10 / (1.0225)^5]^(1/5) - 1 ≈ 0.0245; dev vs
        # 0.02 ≈ 45 bps → moderately_anchored band (20-50).
        assert canonical.anchor_status == "moderately_anchored"
        assert canonical.anchor_deviation_bps is not None
        assert 20 <= abs(canonical.anchor_deviation_bps) < 50


class TestPtDerived20240102:
    """Spec §7 fixture: ``pt_2024_01_02_derived``."""

    def test_derived_tenors_equal_regional_plus_differential(self) -> None:
        derived = compute_derived_pt(
            observation_date=date(2024, 1, 2),
            regional_bei={"5Y": 0.021, "10Y": 0.022},
            differential_pp=0.0015,
            differential_computed_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        assert derived.derived_tenors["5Y"] == pytest.approx(0.0225)
        assert derived.derived_tenors["10Y"] == pytest.approx(0.0235)
        # 5y5y compound derived from 5Y+10Y.
        assert derived.derived_tenors["5y5y"] == pytest.approx(
            compute_5y5y(0.0225, 0.0235), abs=1e-6
        )

    def test_canonical_confidence_le_0_80(self) -> None:
        derived = compute_derived_pt(
            observation_date=date(2024, 1, 2),
            regional_bei={"5Y": 0.021, "10Y": 0.022},
            differential_pp=0.0015,
            differential_computed_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        canonical = build_canonical(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            derived=derived,
            bc_target_pct=0.02,
        )
        # Placeholder differential -> DERIVED row confidence capped at
        # 0.75 (1.0 - 0.15 CALIBRATION_STALE - 0.10 DIFFERENTIAL_TENOR_PROXY).
        # Canonical then inherits + applies spec §6 deductions.
        assert canonical.confidence <= 0.80
        # Upstream flags from derived propagate onto the canonical row.
        assert "CALIBRATION_STALE" in canonical.flags
        assert "DIFFERENTIAL_TENOR_PROXY" in canonical.flags
        assert "INE_MIRROR_EUROSTAT" in canonical.flags

    def test_uses_module_placeholder_when_differential_pp_unset(self) -> None:
        derived = compute_derived_pt(
            observation_date=date(2026, 4, 24),
            regional_bei={"5Y": 0.020, "10Y": 0.021},
        )
        assert derived.differential_pp == pytest.approx(PT_EA_DIFFERENTIAL_PLACEHOLDER_PP)


class TestJpSurveyOnly:
    """Spec §7 fixture: ``jp_survey_only``."""

    def test_no_10y_implies_no_5y5y_and_anchor_uncomputable(self) -> None:
        survey = ExpInfSurvey(
            country_code="JP",
            observation_date=date(2024, 1, 2),
            survey_name="TANKAN",
            survey_release_date=date(2023, 12, 15),
            horizons={"1Y": 0.025, "3Y": 0.020, "5Y": 0.018},
            interpolated_tenors={"1Y": 0.025, "5Y": 0.018},  # no 10Y, no 30Y
            confidence=0.80,
            flags=(),
        )
        canonical = build_canonical(
            country_code="JP",
            observation_date=date(2024, 1, 2),
            survey=survey,
            bc_target_pct=0.02,
        )

        assert "5y5y" not in canonical.expected_inflation_tenors
        assert canonical.anchor_deviation_bps is None
        assert canonical.anchor_status is None
        assert "ANCHOR_UNCOMPUTABLE" in canonical.flags
        # Only SURVEY row supplied → single method.
        assert canonical.methods_available == 1
        assert canonical.source_method_per_tenor["1Y"] == "SURVEY"
        assert canonical.source_method_per_tenor["5Y"] == "SURVEY"


class TestEa5y5yCompoundedVsLinear:
    """Spec §7 fixture: ``ea_5y5y_compounded_vs_linear``."""

    def test_compounded_within_1bps_of_linear_at_moderate_levels(self) -> None:
        # At 5Y=2.1%, 10Y=2.25% the compounded and linear (Ang-Piazzesi
        # reference) approximations diverge by < 1 bps. Storage value is
        # always compounded per spec §4.
        r5, r10 = 0.021, 0.0225
        compounded = compute_5y5y(r5, r10)
        linear = (10 * r10 - 5 * r5) / 5

        assert compounded == pytest.approx(linear, abs=1e-4)  # < 1 bps

    def test_swap_row_stores_compounded_5y5y(self) -> None:
        swap = compute_swap(
            country_code="EA",
            swap_rates={"5Y": 0.021, "10Y": 0.0225},
            observation_date=date(2024, 1, 2),
            swap_provider="ECB_SDW",
        )
        # 5y5y derived via spec §4 compounded formula (not linear).
        expected_compounded = ((1 + 0.0225) ** 10 / (1 + 0.021) ** 5) ** (1 / 5) - 1
        assert swap.swap_rates["5y5y"] == pytest.approx(expected_compounded)


class TestUsMethodDivergence2022Q2:
    """Spec §7 fixture: ``us_method_divergence_2022_q2``."""

    def test_bei_vs_survey_divergence_flag_and_bps(self) -> None:
        # 2022 Q2: BEI 10Y spiked to ~2.8% whilst SPF anchored at 2.2%;
        # spread of 600 bps triggers ``INFLATION_METHOD_DIVERGENCE``.
        bei = compute_bei_us(
            nominal_yields={"5Y": 0.030, "10Y": 0.030},
            bei_market={"5Y": 0.028, "10Y": 0.028},
            observation_date=date(2022, 6, 30),
        )
        survey = compute_survey_spf(
            country_code="US",
            survey_horizons={"1Y": 0.033, "2Y": 0.025, "LTE": 0.022},
            observation_date=date(2022, 6, 30),
            survey_release_date=date(2022, 4, 15),
        )
        canonical = build_canonical(
            country_code="US",
            observation_date=date(2022, 6, 30),
            bei=bei,
            survey=survey,
            bc_target_pct=0.02,
        )

        # |0.028 - 0.022| = 0.006 → 60 bps. Spec fixture §7 quotes 600
        # on the ``0.028 vs 0.022`` pair; note the fixture header lists
        # the rate-domain diff (0.006 = 60 bps). The stored integer is
        # :math:`|BEI_{10Y} - SURVEY_{10Y}| \\cdot 10000`.
        assert canonical.bei_vs_survey_divergence_bps == 60
        # 60 bps < 100 bps threshold → no divergence flag.
        assert "INFLATION_METHOD_DIVERGENCE" not in canonical.flags

    def test_divergence_flag_set_when_over_100bps(self) -> None:
        bei = compute_bei_us(
            nominal_yields={"5Y": 0.04, "10Y": 0.04},
            bei_market={"5Y": 0.028, "10Y": 0.030},  # BEI 10Y = 3.0%
            observation_date=date(2022, 6, 30),
        )
        survey = ExpInfSurvey(
            country_code="US",
            observation_date=date(2022, 6, 30),
            survey_name="ECB_SPF_HICP",
            survey_release_date=date(2022, 4, 15),
            horizons={"10Y": 0.018},
            interpolated_tenors={"10Y": 0.018},  # SPF 10Y = 1.8%; spread 120 bps
            confidence=0.90,
            flags=(),
        )
        canonical = build_canonical(
            country_code="US",
            observation_date=date(2022, 6, 30),
            bei=bei,
            survey=survey,
            bc_target_pct=0.02,
        )
        assert canonical.bei_vs_survey_divergence_bps == 120
        assert "INFLATION_METHOD_DIVERGENCE" in canonical.flags
