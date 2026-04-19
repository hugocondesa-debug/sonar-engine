"""Contract tests for NSS overlay module.

Verifies module structure, type contracts, and constant values match
spec nss-curves.md. Does NOT test fit behavior (Day 2 AM implementation).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from sonar.overlays import ConvergenceError, InsufficientDataError, OverlayError, nss


class TestConstants:
    def test_methodology_version(self) -> None:
        assert nss.METHODOLOGY_VERSION == "NSS_v0.1"

    def test_standard_output_tenors_count(self) -> None:
        # Spec §3: 12 standard output tenors.
        assert len(nss.STANDARD_OUTPUT_TENORS) == 12

    def test_standard_output_tenors_content(self) -> None:
        expected = (
            "1M",
            "3M",
            "6M",
            "1Y",
            "2Y",
            "3Y",
            "5Y",
            "7Y",
            "10Y",
            "15Y",
            "20Y",
            "30Y",
        )
        assert expected == nss.STANDARD_OUTPUT_TENORS

    def test_standard_forward_keys_includes_2y1y(self) -> None:
        # Spec §3 post-sweep (957e765): 2y1y required for M3 consumer.
        assert "2y1y" in nss.STANDARD_FORWARD_KEYS

    def test_standard_forward_keys_complete(self) -> None:
        expected = ("1y1y", "2y1y", "1y2y", "1y5y", "5y5y", "10y10y")
        assert expected == nss.STANDARD_FORWARD_KEYS

    def test_fit_bounds_shape(self) -> None:
        assert len(nss.FIT_BOUNDS) == 6  # 6 NSS parameters

    def test_fit_bounds_beta_0_week2(self) -> None:
        # Spec §4: (0, 0.20) for Week 2. CAL-030 addresses negative yields pre-Week 3.
        assert nss.FIT_BOUNDS[0] == (0.0, 0.20)

    def test_min_observations(self) -> None:
        assert nss.MIN_OBSERVATIONS == 6

    def test_yield_range(self) -> None:
        assert nss.YIELD_RANGE_PCT == (-5.0, 30.0)


class TestExceptionHierarchy:
    def test_insufficient_data_is_overlay_error(self) -> None:
        assert issubclass(InsufficientDataError, OverlayError)

    def test_convergence_is_overlay_error(self) -> None:
        assert issubclass(ConvergenceError, OverlayError)


class TestDataclassContracts:
    def test_nss_input_frozen(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 10.0]),
            yields_pct=np.array([4.0, 4.5, 4.3]),
            country_code="US",  # alpha-2 post P2-023
            observation_date=date(2026, 4, 17),
            curve_input_type="par",
        )
        with pytest.raises(AttributeError):
            inp.country_code = "DE"  # type: ignore[misc]

    def test_nss_params_allows_none_for_4param(self) -> None:
        # 4-param Nelson-Siegel reduced fit: beta_3 and lambda_2 are None.
        p = nss.NSSParams(
            beta_0=0.04,
            beta_1=-0.01,
            beta_2=0.005,
            beta_3=None,
            lambda_1=1.5,
            lambda_2=None,
        )
        assert p.beta_3 is None
        assert p.lambda_2 is None


class TestFunctionSignatures:
    def test_fit_nss_not_implemented(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 2.0, 5.0, 10.0, 30.0]),
            yields_pct=np.array([4.0, 4.2, 4.3, 4.4, 4.5, 4.6]),
            country_code="US",
            observation_date=date(2026, 4, 17),
            curve_input_type="par",
        )
        with pytest.raises(NotImplementedError):
            nss.fit_nss(inp)

    def test_derive_zero_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            nss.derive_zero_curve(None)  # type: ignore[arg-type]

    def test_derive_forward_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            nss.derive_forward_curve(None)  # type: ignore[arg-type]

    def test_derive_real_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            nss.derive_real_curve(None)  # type: ignore[arg-type]
