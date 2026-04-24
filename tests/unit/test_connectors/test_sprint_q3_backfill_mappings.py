"""Sprint Q.3 — mapping layer between raw connector outputs and ExpInfSurvey.

Exercises the ``_outlook_to_expinfsurvey`` (Tankan) and
``_release_to_expinfsurvey`` (CES) helpers that convert a raw release
into the dataclass consumed by :func:`persist_survey_row`. These
helpers are the spot where 5Y horizons fan out to 10Y / 5y5y / 30Y
canonical tenors; a regression here would cause the M3 builder to
miss ``interpolated_tenors['5y5y']`` and reject the row.
"""

from __future__ import annotations

from datetime import date

import pytest

from sonar.connectors.boc import CESInflationExpectation
from sonar.connectors.boc_ces_backfill import _release_to_expinfsurvey
from sonar.connectors.boj_tankan import TankanInflationOutlook
from sonar.connectors.boj_tankan_backfill import (
    _enumerate_releases,
    _outlook_to_expinfsurvey,
)

# ---------------------------------------------------------------------------
# Tankan mapping
# ---------------------------------------------------------------------------


def test_tankan_mapping_full_horizons() -> None:
    outlook = TankanInflationOutlook(
        reference_date=date(2026, 3, 1),
        release_year=2026,
        release_quarter_end_month=3,
        horizons_pct={"1Y": 2.6, "3Y": 2.5, "5Y": 2.5},
    )
    sv = _outlook_to_expinfsurvey(outlook)
    assert sv.country_code == "JP"
    assert sv.survey_name == "BOJ_TANKAN"
    assert sv.observation_date == date(2026, 3, 1)
    # Release date falls in the month after the reference quarter end.
    assert sv.survey_release_date == date(2026, 4, 1)
    # Horizons preserved in decimal (tolerate float-precision noise on /100).
    assert set(sv.horizons) == {"1Y", "3Y", "5Y"}
    assert sv.horizons["1Y"] == pytest.approx(0.026)
    assert sv.horizons["3Y"] == pytest.approx(0.025)
    assert sv.horizons["5Y"] == pytest.approx(0.025)
    # Canonical tenors that the M3 builder reads must be present.
    for key in ("5y5y", "5Y", "10Y"):
        assert key in sv.interpolated_tenors
    # 2Y linear-interpolated between 1Y + 3Y.
    assert sv.interpolated_tenors["2Y"] == pytest.approx(0.0255)
    # 5y5y anchored at 5Y under TANKAN_LT_AS_ANCHOR.
    assert sv.interpolated_tenors["5y5y"] == pytest.approx(0.025)
    assert sv.interpolated_tenors["10Y"] == pytest.approx(0.025)
    assert sv.interpolated_tenors["30Y"] == pytest.approx(0.025)
    assert "TANKAN_LT_AS_ANCHOR" in sv.flags


def test_tankan_mapping_release_date_crosses_year_boundary() -> None:
    """December-quarter release is published in January of the next year."""
    outlook = TankanInflationOutlook(
        reference_date=date(2025, 12, 1),
        release_year=2025,
        release_quarter_end_month=12,
        horizons_pct={"1Y": 2.4, "3Y": 2.3, "5Y": 2.2},
    )
    sv = _outlook_to_expinfsurvey(outlook)
    assert sv.survey_release_date == date(2026, 1, 1)


def test_tankan_mapping_confidence_is_1() -> None:
    outlook = TankanInflationOutlook(
        reference_date=date(2026, 3, 1),
        release_year=2026,
        release_quarter_end_month=3,
        horizons_pct={"5Y": 2.5},
    )
    sv = _outlook_to_expinfsurvey(outlook)
    assert sv.confidence == 1.0


def test_tankan_enumerate_releases_only_zip_window() -> None:
    """Pre-2021 releases are PDF-only — enumerator must exclude them."""
    releases = _enumerate_releases(date(2019, 1, 1), date(2026, 4, 24))
    years = sorted({y for y, _ in releases})
    # First ZIP-format year is 2021; 2019/2020 must be excluded.
    assert years[0] == 2021
    # Every year should have exactly four quarter-end months.
    assert releases.count((2023, 3)) == 1
    assert (2020, 3) not in releases


# ---------------------------------------------------------------------------
# CES mapping
# ---------------------------------------------------------------------------


def test_ces_mapping_three_horizons() -> None:
    rel = CESInflationExpectation(
        release_date=date(2026, 1, 1),
        horizons_pct={"1Y": 3.98, "2Y": 3.40, "5Y": 3.02},
    )
    sv = _release_to_expinfsurvey(rel)
    assert sv.country_code == "CA"
    assert sv.survey_name == "BOC_CES"
    assert sv.observation_date == date(2026, 1, 1)
    # Release date = quarter start + ~45d lag.
    assert sv.survey_release_date > rel.release_date
    assert sv.horizons == {"1Y": 0.0398, "2Y": 0.034, "5Y": 0.0302}
    assert sv.interpolated_tenors["5y5y"] == pytest.approx(0.0302)
    assert sv.interpolated_tenors["10Y"] == pytest.approx(0.0302)
    # 3Y = linear interp between 2Y and 5Y.
    assert sv.interpolated_tenors["3Y"] == pytest.approx(0.034 + (0.0302 - 0.034) / 3)
    assert "CES_LT_AS_ANCHOR" in sv.flags


def test_ces_mapping_partial_horizons_no_5y_skips_anchor_flag() -> None:
    """Release missing 5Y → no LT anchor spread; 5y5y absent → caller rejects."""
    rel = CESInflationExpectation(
        release_date=date(2026, 1, 1),
        horizons_pct={"1Y": 3.98, "2Y": 3.40},
    )
    sv = _release_to_expinfsurvey(rel)
    # Flag gated on 5Y presence; absent here.
    assert "CES_LT_AS_ANCHOR" not in sv.flags
    assert "5y5y" not in sv.interpolated_tenors


def test_ces_mapping_country_not_leaking_other_code() -> None:
    rel = CESInflationExpectation(
        release_date=date(2024, 7, 1),
        horizons_pct={"1Y": 2.8, "2Y": 2.6, "5Y": 2.5},
    )
    sv = _release_to_expinfsurvey(rel)
    assert sv.country_code == "CA"
    assert sv.survey_name == "BOC_CES"
