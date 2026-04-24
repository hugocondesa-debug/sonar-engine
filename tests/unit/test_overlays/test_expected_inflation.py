"""Unit tests for expected-inflation overlay (Week 3 US v0.1)."""

from __future__ import annotations

from datetime import date

import pytest

from sonar.overlays.expected_inflation import (
    ANCHOR_BANDS_BPS,
    STANDARD_TENORS,
    anchor_status,
    build_canonical,
    compute_5y5y,
    compute_bei_from_yields,
    compute_bei_us,
    compute_survey_spf,
    compute_survey_us,
)


class TestBEI:
    def test_bei_from_yields_subtracts_per_tenor(self) -> None:
        nominal = {"5Y": 0.0395, "10Y": 0.0398}
        linker = {"5Y": 0.0176, "10Y": 0.0174}
        bei = compute_bei_from_yields(nominal, linker)
        assert bei["5Y"] == pytest.approx(0.0219)
        assert bei["10Y"] == pytest.approx(0.0224)

    def test_bei_from_yields_skips_missing(self) -> None:
        bei = compute_bei_from_yields({"5Y": 0.04, "10Y": 0.04}, {"5Y": 0.018})
        assert "10Y" not in bei

    def test_compute_bei_us_adds_5y5y(self) -> None:
        # FRED-published BEI 5Y/10Y/30Y; 5y5y derived.
        bei = compute_bei_us(
            nominal_yields={"5Y": 0.0393, "10Y": 0.0395, "30Y": 0.0408},
            bei_market={"5Y": 0.0217, "10Y": 0.0221, "30Y": 0.0224},
            observation_date=date(2024, 1, 2),
        )
        assert bei.bei_tenors["5Y"] == pytest.approx(0.0217)
        assert "5y5y" in bei.bei_tenors
        assert 0.020 < bei.bei_tenors["5y5y"] < 0.025
        assert bei.confidence == 1.0


class TestSurvey:
    def test_survey_us_interpolates_5y_between_1y_and_10y(self) -> None:
        survey = compute_survey_us(
            survey_horizons={"1Y": 0.029, "10Y": 0.0216},
            observation_date=date(2024, 1, 2),
            survey_release_date=date(2024, 1, 1),
        )
        assert survey.interpolated_tenors["1Y"] == pytest.approx(0.029)
        assert survey.interpolated_tenors["10Y"] == pytest.approx(0.0216)
        # Linear interp: at year 5, weight = (5-1)/(10-1) = 4/9.
        expected_5y = 0.029 + (4 / 9) * (0.0216 - 0.029)
        assert survey.interpolated_tenors["5Y"] == pytest.approx(expected_5y)
        assert survey.interpolated_tenors["30Y"] == pytest.approx(0.0216)
        assert "5y5y" in survey.interpolated_tenors


class TestAnchor:
    @pytest.mark.parametrize(
        ("dev_bps", "status"),
        [
            (0, "well_anchored"),
            (15, "well_anchored"),
            (25, "moderately_anchored"),
            (45, "moderately_anchored"),
            (75, "drifting"),
            (95, "drifting"),
            (150, "unanchored"),
            (500, "unanchored"),
        ],
    )
    def test_anchor_band_thresholds(self, dev_bps: int, status: str) -> None:
        assert anchor_status(dev_bps) == status

    def test_thresholds_match_config(self) -> None:
        assert ANCHOR_BANDS_BPS["well_anchored"] == 20
        assert ANCHOR_BANDS_BPS["moderately_anchored"] == 50
        assert ANCHOR_BANDS_BPS["drifting"] == 100


class TestBuildCanonical:
    def test_us_canonical_bei_priority(self) -> None:
        bei = compute_bei_us(
            nominal_yields={"5Y": 0.0393, "10Y": 0.0395, "30Y": 0.0408},
            bei_market={"5Y": 0.0217, "10Y": 0.0221, "30Y": 0.0224},
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
        # 5Y/10Y/30Y/5y5y → BEI; 1Y → SURVEY (BEI lacks short-end)
        assert canonical.source_method_per_tenor["5Y"] == "BEI"
        assert canonical.source_method_per_tenor["10Y"] == "BEI"
        assert canonical.source_method_per_tenor["30Y"] == "BEI"
        assert canonical.source_method_per_tenor["5y5y"] == "BEI"
        assert canonical.source_method_per_tenor["1Y"] == "SURVEY"
        assert canonical.methods_available == 2
        assert canonical.bc_target_pct == 0.02
        assert canonical.anchor_deviation_bps is not None
        assert canonical.anchor_status in {"well_anchored", "moderately_anchored", "drifting"}

    def test_anchor_deviation_for_well_anchored_5y5y(self) -> None:
        # If 5y5y BEI ≈ 2.4%, dev vs Fed target 0.02 = 0.004 → 40 bps → moderately_anchored
        bei = compute_bei_us(
            nominal_yields={"5Y": 0.04, "10Y": 0.04},
            bei_market={"5Y": 0.022, "10Y": 0.0227},  # 5y5y ≈ 0.0234
            observation_date=date(2024, 1, 2),
        )
        canonical = build_canonical(
            country_code="US",
            observation_date=date(2024, 1, 2),
            bei=bei,
            bc_target_pct=0.02,
        )
        assert canonical.anchor_deviation_bps is not None
        assert -100 < canonical.anchor_deviation_bps < 100

    def test_no_5y5y_emits_anchor_uncomputable(self) -> None:
        # SURVEY-only with 1Y but no 10Y → no 5y5y → ANCHOR_UNCOMPUTABLE.
        survey = compute_survey_us(
            survey_horizons={"1Y": 0.025},
            observation_date=date(2024, 1, 2),
            survey_release_date=date(2024, 1, 1),
        )
        canonical = build_canonical(
            country_code="US",
            observation_date=date(2024, 1, 2),
            survey=survey,
            bc_target_pct=0.02,
        )
        assert "ANCHOR_UNCOMPUTABLE" in canonical.flags
        assert canonical.anchor_deviation_bps is None

    def test_inflation_method_divergence_flagged(self) -> None:
        # BEI 10Y vs SURVEY 10Y differ > 100 bps → INFLATION_METHOD_DIVERGENCE.
        bei = compute_bei_us(
            nominal_yields={"5Y": 0.04, "10Y": 0.04},
            bei_market={"5Y": 0.025, "10Y": 0.030},  # 10Y BEI = 3.0%
            observation_date=date(2024, 1, 2),
        )
        survey = compute_survey_us(
            survey_horizons={"1Y": 0.020, "10Y": 0.018},  # 10Y survey = 1.8%
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
        assert "INFLATION_METHOD_DIVERGENCE" in canonical.flags
        assert canonical.bei_vs_survey_divergence_bps == 120


class TestCompute5y5y:
    def test_known_inputs(self) -> None:
        # If r5 = 4% and r10 = 4.5%, 5y5y ≈ ((1.045^10 / 1.04^5)^(1/5) - 1)
        result = compute_5y5y(0.04, 0.045)
        # Verified analytically: ((1.553/1.217)^0.2) - 1 ≈ 0.05005
        assert 0.049 < result < 0.051


class TestStandardTenors:
    def test_includes_5y5y_forward(self) -> None:
        assert "5y5y" in STANDARD_TENORS
        assert len(STANDARD_TENORS) == 6


# ---------------------------------------------------------------------------
# Sprint Q.1 — compute_survey_spf
# ---------------------------------------------------------------------------


class TestSurveySpf:
    def test_ea_aggregate_full_horizons(self) -> None:
        """EA path: 1Y/2Y/LTE horizons produce 5Y/10Y/5y5y/30Y via LT anchor."""
        survey = compute_survey_spf(
            country_code="EA",
            survey_horizons={"1Y": 0.01971, "2Y": 0.02051, "LTE": 0.02017},
            observation_date=date(2026, 4, 23),
            survey_release_date=date(2026, 1, 1),
        )
        assert survey.country_code == "EA"
        assert survey.survey_name == "ECB_SPF_HICP"
        # 1Y + 2Y preserved from raw horizons.
        assert survey.interpolated_tenors["1Y"] == pytest.approx(0.01971)
        assert survey.interpolated_tenors["2Y"] == pytest.approx(0.02051)
        # LT mapped to 5Y / 10Y / 5y5y / 30Y — anchor proxy.
        for tenor in ("5Y", "10Y", "5y5y", "30Y"):
            assert survey.interpolated_tenors[tenor] == pytest.approx(0.02017)
        # Flags — LT-as-anchor always, AREA_PROXY not for EA.
        assert "SPF_LT_AS_ANCHOR" in survey.flags
        assert "SPF_AREA_PROXY" not in survey.flags
        # Confidence baseline 1.0 — degradation applied in build_canonical.
        assert survey.confidence == 1.0

    def test_ea_member_area_proxy_flag_set(self) -> None:
        survey = compute_survey_spf(
            country_code="DE",
            survey_horizons={"1Y": 0.019, "LTE": 0.020},
            observation_date=date(2026, 4, 23),
            survey_release_date=date(2026, 1, 1),
            is_area_proxy=True,
        )
        assert survey.country_code == "DE"
        assert "SPF_AREA_PROXY" in survey.flags
        assert "SPF_LT_AS_ANCHOR" in survey.flags

    def test_missing_lt_skips_anchor_tenors(self) -> None:
        """No LTE input → no 5Y/10Y/5y5y; no SPF_LT_AS_ANCHOR flag."""
        survey = compute_survey_spf(
            country_code="EA",
            survey_horizons={"1Y": 0.019, "2Y": 0.020},
            observation_date=date(2026, 4, 23),
            survey_release_date=date(2026, 1, 1),
        )
        assert "5y5y" not in survey.interpolated_tenors
        assert "10Y" not in survey.interpolated_tenors
        assert "SPF_LT_AS_ANCHOR" not in survey.flags

    def test_build_canonical_spf_survey_only_emits_5y5y(self) -> None:
        """End-to-end build_canonical with EA SPF survey yields 5y5y in output."""
        survey = compute_survey_spf(
            country_code="EA",
            survey_horizons={"1Y": 0.01971, "LTE": 0.02017},
            observation_date=date(2026, 4, 23),
            survey_release_date=date(2026, 1, 1),
        )
        canonical = build_canonical(
            country_code="EA",
            observation_date=date(2026, 4, 23),
            bei=None,
            survey=survey,
            bc_target_pct=0.02,
        )
        assert "5y5y" in canonical.expected_inflation_tenors
        assert canonical.source_method_per_tenor["5y5y"] == "SURVEY"
        # 5y5y = LT (0.02017); dev vs 2% target = +17 bps; well_anchored edge.
        assert canonical.anchor_status in {"well_anchored", "moderately_anchored"}
        assert canonical.methods_available == 1
