"""Unit tests for Fed GSW xval canary parser + comparator."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from sonar.overlays.nss import NSSParams, SpotCurve
from sonar.overlays.validation import (
    FED_GSW_XVAL_THRESHOLD_BPS,
    GSWReference,
    compare_to_gsw,
    parse_feds200628_csv,
)

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "xval" / "feds200628_2024-01-02.csv"


def test_threshold_default_bps() -> None:
    assert FED_GSW_XVAL_THRESHOLD_BPS == 10.0


def test_parse_feds200628_csv_known_date() -> None:
    ref = parse_feds200628_csv(FIXTURE, date(2024, 1, 2))
    assert isinstance(ref, GSWReference)
    assert ref.observation_date == date(2024, 1, 2)
    # Spot-check a few zero yields published by Fed for 2024-01-02 (decimal).
    assert 0.038 < ref.zero_yields[10] < 0.042
    assert 0.040 < ref.zero_yields[2] < 0.05  # 2Y was high in early 2024
    assert 0.04 < ref.zero_yields[30] < 0.045
    # All 4 NSS betas + 2 taus parsed.
    assert ref.tau_1 > 0


def test_parse_feds200628_csv_unknown_date_raises() -> None:
    with pytest.raises(ValueError, match="no row"):
        parse_feds200628_csv(FIXTURE, date(1900, 1, 1))


def test_compare_to_gsw_identity_zero_deviation() -> None:
    """If SONAR fitted_yields equal GSW zero_yields, deviation is 0 bps."""
    ref = parse_feds200628_csv(FIXTURE, date(2024, 1, 2))
    fitted = {f"{y}Y": ref.zero_yields[y] for y in (2, 5, 10, 30)}
    spot = SpotCurve(
        params=NSSParams(0.04, -0.01, 0.005, 0.0, 1.5, 5.0),
        fitted_yields=fitted,
        rmse_bps=0.0,
        confidence=1.0,
        flags=(),
        observations_used=11,
    )
    deviations = compare_to_gsw(spot, ref)
    assert set(deviations.keys()) == {2, 5, 10, 30}
    for d in deviations.values():
        assert d == pytest.approx(0.0, abs=1e-9)


def test_compare_to_gsw_known_offset() -> None:
    """A 10 bps lift on every fitted tenor produces 10 bps deviation each."""
    ref = parse_feds200628_csv(FIXTURE, date(2024, 1, 2))
    fitted = {f"{y}Y": ref.zero_yields[y] + 0.001 for y in (2, 5, 10, 30)}
    spot = SpotCurve(
        params=NSSParams(0.04, -0.01, 0.005, 0.0, 1.5, 5.0),
        fitted_yields=fitted,
        rmse_bps=0.0,
        confidence=1.0,
        flags=(),
        observations_used=11,
    )
    deviations = compare_to_gsw(spot, ref)
    for d in deviations.values():
        assert d == pytest.approx(10.0, abs=1e-6)


def test_compare_to_gsw_skips_missing_tenors() -> None:
    ref = parse_feds200628_csv(FIXTURE, date(2024, 1, 2))
    fitted = {"5Y": ref.zero_yields[5]}  # only 5Y fitted
    spot = SpotCurve(
        params=NSSParams(0.04, -0.01, 0.005, 0.0, 1.5, 5.0),
        fitted_yields=fitted,
        rmse_bps=0.0,
        confidence=1.0,
        flags=(),
        observations_used=11,
    )
    deviations = compare_to_gsw(spot, ref)
    assert set(deviations.keys()) == {5}
