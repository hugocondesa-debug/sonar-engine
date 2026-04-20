"""Tests for L4 DSR annuity-factor helper."""

from __future__ import annotations

import pytest

from sonar.indices._helpers.annuity import annuity_factor


def test_full_mode_canonical() -> None:
    # i=3.45%, s=15Y → closed form i / (1 - (1.0345)^-15)
    # = 0.0345 / (1 - 1/1.6640) = 0.0345 / 0.3990 ≈ 0.08652.
    # Spec example shows 0.0843 (rounded from slightly different
    # parameterization); we assert the mathematically exact value.
    af = annuity_factor(0.0345, 15.0, "full")
    assert af == pytest.approx(0.08652, abs=0.0005)


def test_o2_approximation() -> None:
    # o2 = i + 1/s  (3.45% + 1/15 = 0.0345 + 0.0667 = 0.1012)
    af = annuity_factor(0.0345, 15.0, "o2")
    assert af == pytest.approx(0.0345 + 1.0 / 15.0, rel=1e-9)


def test_o1_interest_only() -> None:
    af = annuity_factor(0.0345, None, "o1")
    assert af == 0.0345


def test_o1_ignores_maturity() -> None:
    assert annuity_factor(0.05, 10.0, "o1") == 0.05
    assert annuity_factor(0.05, None, "o1") == 0.05


def test_full_mode_requires_maturity() -> None:
    with pytest.raises(ValueError, match="maturity"):
        annuity_factor(0.04, None, "full")
    with pytest.raises(ValueError, match="maturity"):
        annuity_factor(0.04, 0.0, "full")
    with pytest.raises(ValueError, match="maturity"):
        annuity_factor(0.04, 75.0, "full")


def test_o2_requires_maturity() -> None:
    with pytest.raises(ValueError, match="maturity"):
        annuity_factor(0.04, None, "o2")


def test_negative_rate_jp_like() -> None:
    # JP 2020: lending rate ~ -0.1%, maturity 15Y — formula remains
    # finite and positive for small negative rates.
    af = annuity_factor(-0.001, 15.0, "full")
    assert af > 0.0
    assert af == pytest.approx(1.0 / 15.0, abs=0.01)


def test_rate_below_minus_one_rejected() -> None:
    with pytest.raises(ValueError, match="stability bound"):
        annuity_factor(-1.0, 15.0, "full")
    with pytest.raises(ValueError, match="stability bound"):
        annuity_factor(-1.5, 15.0, "full")


def test_full_approaches_rate_at_long_maturity() -> None:
    # As s increases, annuity_factor_full approaches i (asymptote).
    # Test at 45Y (below the 50Y sanity cap).
    af_45y = annuity_factor(0.04, 45.0, "full")
    af_10y = annuity_factor(0.04, 10.0, "full")
    # 45Y result should be closer to i (0.04) than 10Y result.
    assert abs(af_45y - 0.04) < abs(af_10y - 0.04)


def test_o2_within_20pct_of_full_at_canonical_pnfs() -> None:
    # Per BIS WP 529 Table 1 ~0.95 correlation across a wide (i, s)
    # grid. At canonical PNFS (i=3%, s=15Y) the ratio o2/full is ~1.15
    # (o2 is a first-order expansion so it overestimates near-dated
    # cashflows). We assert the weaker but safer +-20% envelope.
    full = annuity_factor(0.03, 15.0, "full")
    o2 = annuity_factor(0.03, 15.0, "o2")
    assert 1.0 < o2 / full < 1.20
