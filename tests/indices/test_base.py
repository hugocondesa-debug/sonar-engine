"""Tests for ``sonar.indices.base`` normalization primitives.

Per SESSION_CONTEXT §Distinção crítica:
``value_0_100 = clip(50 + 16.67 · z_clamped, 0, 100)``.
"""

from __future__ import annotations

import math

import pytest

from sonar.indices.base import (
    Z_CLAMP_BOUND,
    Z_TO_0_100_SLOPE,
    normalize_zscore_to_0_100,
    z_clamp,
)


@pytest.mark.parametrize(
    ("z", "expected"),
    [
        (0.0, 50.0),
        (1.5, 50.0 + Z_TO_0_100_SLOPE * 1.5),
        (-1.5, 50.0 - Z_TO_0_100_SLOPE * 1.5),
        (3.0, 100.0),
        (-3.0, 0.0),
        (10.0, 100.0),
        (-10.0, 0.0),
    ],
)
def test_normalize_zscore_endpoints(z: float, expected: float) -> None:
    assert math.isclose(normalize_zscore_to_0_100(z), expected, abs_tol=1e-9)


def test_normalize_zscore_in_range() -> None:
    for z in (-5.0, -3.0, -1.7, 0.0, 1.7, 3.0, 5.0):
        v = normalize_zscore_to_0_100(z)
        assert 0.0 <= v <= 100.0


def test_normalize_zscore_neutral_at_zero() -> None:
    assert normalize_zscore_to_0_100(0.0) == 50.0


def test_normalize_zscore_nan_raises() -> None:
    with pytest.raises(ValueError, match="NaN"):
        normalize_zscore_to_0_100(float("nan"))


@pytest.mark.parametrize(
    ("z", "bound", "expected"),
    [
        (2.0, 3.0, 2.0),
        (4.0, 3.0, 3.0),
        (-4.0, 3.0, -3.0),
        (1.0, 1.0, 1.0),
        (1.5, 1.0, 1.0),
    ],
)
def test_z_clamp(z: float, bound: float, expected: float) -> None:
    assert z_clamp(z, bound=bound) == expected


def test_z_clamp_default_bound_matches_spec() -> None:
    assert Z_CLAMP_BOUND == 3.0


def test_slope_constant_matches_spec() -> None:
    assert math.isclose(Z_TO_0_100_SLOPE, 100.0 / 6.0, rel_tol=1e-12)
