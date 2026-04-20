"""Tests for the shared rolling z-score helper."""

from __future__ import annotations

import math

import numpy as np
import pytest

from sonar.indices._helpers.z_score_rolling import (
    MIN_HISTORY_HARD_FLOOR_QUARTERS,
    Z_CLAMP_BOUND,
    rolling_zscore,
)


def test_z_at_mean_is_zero() -> None:
    rng = np.random.default_rng(1)
    series = rng.normal(loc=100.0, scale=5.0, size=100).tolist()
    mu = float(np.mean(series))
    z, mu_returned, sigma, n = rolling_zscore(series, current=mu)
    assert z == pytest.approx(0.0, abs=1e-9)
    assert mu_returned == pytest.approx(mu, rel=1e-9)
    assert sigma > 0.0
    assert n == 100


def test_z_one_sigma_above() -> None:
    rng = np.random.default_rng(2)
    series = rng.normal(loc=50.0, scale=10.0, size=200).tolist()
    sigma = float(np.std(series, ddof=1))
    mu = float(np.mean(series))
    z, _, _, _ = rolling_zscore(series, current=mu + sigma)
    assert 0.95 < z < 1.05


def test_z_clamped_at_bound() -> None:
    # Force extreme value 100 sigmas above mean → should clamp at Z_CLAMP_BOUND.
    series = [0.0, 0.1, -0.1, 0.05, -0.05] * 40
    z, _, _, _ = rolling_zscore(series, current=1000.0)
    assert z == Z_CLAMP_BOUND


def test_z_clamped_at_negative_bound() -> None:
    series = [0.0, 0.1, -0.1, 0.05, -0.05] * 40
    z, _, _, _ = rolling_zscore(series, current=-1000.0)
    assert z == -Z_CLAMP_BOUND


def test_defaults_current_to_endpoint() -> None:
    series = [1.0, 2.0, 3.0, 4.0, 5.0]
    z_implicit, mu_i, sigma_i, n_i = rolling_zscore(series)
    z_explicit, mu_e, sigma_e, n_e = rolling_zscore(series, current=5.0)
    assert z_implicit == pytest.approx(z_explicit, rel=1e-9)
    assert mu_i == mu_e
    assert sigma_i == sigma_e
    assert n_i == n_e


def test_single_observation_returns_zero() -> None:
    z, mu, sigma, n = rolling_zscore([42.0])
    assert z == 0.0
    assert mu == 42.0
    assert sigma == 0.0
    assert n == 1


def test_empty_series_returns_zero_and_nan_mu() -> None:
    z, mu, _sigma, n = rolling_zscore([])
    assert z == 0.0
    assert math.isnan(mu)
    assert n == 0


def test_zero_variance_series_returns_zero() -> None:
    z, mu, sigma, n = rolling_zscore([5.0] * 50, current=5.0)
    assert z == 0.0
    assert mu == 5.0
    assert sigma == 0.0 or sigma < 1e-10
    assert n == 50


def test_zero_variance_still_returns_zero_when_current_differs() -> None:
    # Guard against divide-by-zero: sigma=0 short-circuits to z=0.
    z, _, _, _ = rolling_zscore([5.0] * 50, current=10.0)
    assert z == 0.0


def test_nan_current_returns_zero() -> None:
    z, _, _, _ = rolling_zscore([1.0, 2.0, 3.0], current=float("nan"))
    assert z == 0.0


def test_constants_match_spec() -> None:
    # Spec: clamp window ±5 per README § normalization choice; hard floor 60Q.
    assert Z_CLAMP_BOUND == 5.0
    assert MIN_HISTORY_HARD_FLOOR_QUARTERS == 60


def test_ddof_1_vs_ddof_0() -> None:
    series = list(range(1, 11))  # 1..10
    z_ddof1, _, sigma1, _ = rolling_zscore(series, current=5.5, ddof=1)
    z_ddof0, _, sigma0, _ = rolling_zscore(series, current=5.5, ddof=0)
    # Population stdev (ddof=0) < sample stdev (ddof=1) => |z| for ddof=0 larger.
    # At the mean (5.5) both z-scores are 0.
    assert z_ddof1 == 0.0
    assert z_ddof0 == 0.0
    assert sigma1 > sigma0
