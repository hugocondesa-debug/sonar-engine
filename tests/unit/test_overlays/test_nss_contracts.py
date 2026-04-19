"""Contract tests for NSS overlay module.

Verifies module structure, type contracts, and constant values match
spec nss-curves.md. Behavioral tests (fit math, fixtures) live in
test_nss_behavior.py.
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
        assert "2y1y" in nss.STANDARD_FORWARD_KEYS

    def test_standard_forward_keys_complete(self) -> None:
        expected = ("1y1y", "2y1y", "1y2y", "1y5y", "5y5y", "10y10y")
        assert expected == nss.STANDARD_FORWARD_KEYS

    def test_fit_bounds_shape(self) -> None:
        assert len(nss.FIT_BOUNDS) == 6

    def test_fit_bounds_beta_0_week2(self) -> None:
        assert nss.FIT_BOUNDS[0] == (0.0, 0.20)

    def test_min_observations(self) -> None:
        assert nss.MIN_OBSERVATIONS == 6

    def test_yield_range_decimal(self) -> None:
        # units.md §Yields: decimal storage, -5% → 30% == (-0.05, 0.30).
        assert nss.YIELD_RANGE == (-0.05, 0.30)


class TestExceptionHierarchy:
    def test_insufficient_data_is_overlay_error(self) -> None:
        assert issubclass(InsufficientDataError, OverlayError)

    def test_convergence_is_overlay_error(self) -> None:
        assert issubclass(ConvergenceError, OverlayError)


class TestDataclassContracts:
    def test_nss_input_frozen(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 10.0]),
            yields=np.array([0.040, 0.045, 0.043]),
            country_code="US",
            observation_date=date(2026, 4, 17),
            curve_input_type="par",
        )
        with pytest.raises(AttributeError):
            inp.country_code = "DE"  # type: ignore[misc]

    def test_nss_params_allows_none_for_4param(self) -> None:
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
