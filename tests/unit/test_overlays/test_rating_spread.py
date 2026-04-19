"""Unit tests for rating-spread overlay (consolidation + calibration)."""

from __future__ import annotations

from datetime import date

import pytest

from sonar.overlays.exceptions import InsufficientDataError
from sonar.overlays.rating_spread import (
    APRIL_2026_CALIBRATION,
    InvalidRatingTokenError,
    RatingAgencyRaw,
    apply_modifiers,
    consolidate,
    lookup_base_notch,
    lookup_default_spread_bps,
    notch_to_grade,
)


def _row(
    agency: str,
    rating_raw: str,
    *,
    outlook: str = "stable",
    watch: str | None = None,
    rating_type: str = "FC",
    action_date: date = date(2026, 4, 17),
) -> RatingAgencyRaw:
    base = lookup_base_notch(agency, rating_raw)
    adj = apply_modifiers(base, outlook, watch)
    return RatingAgencyRaw(
        agency=agency,
        rating_raw=rating_raw,
        rating_type=rating_type,
        base_notch=base,
        notch_adjusted=adj,
        outlook=outlook,
        watch=watch,
        action_date=action_date,
    )


class TestLookups:
    def test_sp_aaa_to_21(self) -> None:
        assert lookup_base_notch("SP", "AAA") == 21

    def test_moodys_aaa_to_21(self) -> None:
        assert lookup_base_notch("MOODYS", "Aaa") == 21

    def test_dbrs_aa_high_to_20(self) -> None:
        assert lookup_base_notch("DBRS", "AA (high)") == 20

    def test_fitch_a_minus_to_15(self) -> None:
        assert lookup_base_notch("FITCH", "A-") == 15

    def test_default_d_to_zero(self) -> None:
        assert lookup_base_notch("SP", "D") == 0
        assert lookup_base_notch("FITCH", "RD") == 0

    def test_unknown_token_raises(self) -> None:
        with pytest.raises(InvalidRatingTokenError):
            lookup_base_notch("SP", "AA++")


class TestModifiers:
    def test_positive_outlook_adds_025(self) -> None:
        assert apply_modifiers(15, "positive") == pytest.approx(15.25)

    def test_negative_watch_subtracts_05(self) -> None:
        assert apply_modifiers(15, "stable", "watch_negative") == pytest.approx(14.5)

    def test_developing_outlook_no_modifier(self) -> None:
        assert apply_modifiers(15, "developing") == pytest.approx(15.0)


class TestCalibration:
    def test_anchor_lookup_exact(self) -> None:
        assert lookup_default_spread_bps(15) == 90
        assert lookup_default_spread_bps(12) == 245
        assert lookup_default_spread_bps(21) == 10

    def test_interpolation_between_anchors(self) -> None:
        # notch 13 between 12 (245) and 15 (90): 1/3 of the way → 245 - (155/3) ≈ 193
        v = lookup_default_spread_bps(13)
        assert 180 <= v <= 210, f"interpolated 13={v}"

    def test_default_returns_none(self) -> None:
        assert lookup_default_spread_bps(0) is None

    def test_calibration_anchors_present(self) -> None:
        for notch in (0, 3, 6, 9, 12, 15, 18, 21):
            assert notch in APRIL_2026_CALIBRATION


class TestNotchToGrade:
    @pytest.mark.parametrize(
        ("notch", "grade"),
        [
            (21, "AAA"),
            (20, "AA"),
            (15, "A"),
            (12, "BBB"),
            (9, "BB"),
            (6, "B"),
            (3, "CCC"),
            (0, "D"),
        ],
    )
    def test_grade_buckets(self, notch: int, grade: str) -> None:
        assert notch_to_grade(notch) == grade


class TestConsolidate:
    def test_pt_2026_04_17_a_minus(self) -> None:
        # Spec §7 fixture pt_2026_04_17 — all 4 agencies agree A-/A3.
        rows = [
            _row("SP", "A-"),
            _row("MOODYS", "A3"),
            _row("FITCH", "A-"),
            _row("DBRS", "A (low)"),
        ]
        result = consolidate(rows, country_code="PT", observation_date=date(2026, 4, 17))
        assert result.consolidated_sonar_notch == 15.0
        assert result.notch_int == 15
        assert result.default_spread_bps == 90  # anchor
        assert result.agencies_count == 4
        assert result.outlook_composite == "stable"
        assert result.confidence >= 0.85
        assert "RATING_SPLIT" not in result.flags

    def test_us_2026_04_17_split_aa_plus_aaa(self) -> None:
        # Spec §7 fixture us_2026_04_17_split — SP AA+, Moody's Aaa, Fitch AA+, DBRS AAA.
        rows = [
            _row("SP", "AA+"),
            _row("MOODYS", "Aaa"),
            _row("FITCH", "AA+"),
            _row("DBRS", "AAA"),
        ]
        result = consolidate(rows, country_code="US", observation_date=date(2026, 4, 17))
        # median of [20, 21, 20, 21] = 20.5; conservative tie → floor → 20
        assert result.consolidated_sonar_notch == 20.0  # floor of 20.5 per conservative rule
        assert result.notch_int == 20

    def test_single_agency_caps_confidence(self) -> None:
        rows = [_row("FITCH", "CCC+")]
        result = consolidate(rows, country_code="GH", observation_date=date(2026, 4, 17))
        assert result.agencies_count == 1
        assert "RATING_SINGLE_AGENCY" in result.flags
        assert result.confidence <= 0.60

    def test_split_rating_flagged(self) -> None:
        # 3 notches of spread → RATING_SPLIT
        rows = [
            _row("SP", "BBB+"),  # 14
            _row("MOODYS", "Baa3"),  # 12
            _row("FITCH", "BB+"),  # 11
        ]
        result = consolidate(rows, country_code="IT", observation_date=date(2026, 4, 17))
        assert "RATING_SPLIT" in result.flags

    def test_default_d_caps_confidence(self) -> None:
        rows = [_row("SP", "D"), _row("FITCH", "D")]
        result = consolidate(rows, country_code="LB", observation_date=date(2026, 4, 17))
        assert result.notch_int == 0
        assert "RATING_DEFAULT" in result.flags
        assert result.default_spread_bps is None
        assert result.confidence <= 0.40

    def test_empty_rows_raises(self) -> None:
        with pytest.raises(InsufficientDataError):
            consolidate([], country_code="XX", observation_date=date(2026, 4, 17))

    def test_outlook_developing_flagged(self) -> None:
        rows = [
            _row("SP", "A-", outlook="developing"),
            _row("MOODYS", "A3"),
        ]
        result = consolidate(rows, country_code="TR", observation_date=date(2026, 4, 17))
        assert "RATING_OUTLOOK_UNCERTAIN" in result.flags
