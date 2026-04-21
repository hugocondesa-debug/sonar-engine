"""Tests for persist_many_overlay_results batch helper (week7 sprint C C6)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from sonar.db.models import ERPCanonical, IndexValue, RatingsConsolidated
from sonar.db.persistence import (
    DuplicatePersistError,
    persist_many_overlay_results,
)
from sonar.indices.base import IndexResult
from sonar.overlays.erp import ERPInput, fit_erp_us
from sonar.overlays.rating_spread import (
    RatingAgencyRaw,
    apply_modifiers,
    consolidate,
    lookup_base_notch,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


ANCHOR = date(2024, 12, 31)


def _erp_us_fit() -> tuple[object, ERPInput]:
    inputs = ERPInput(
        market_index="SPX",
        country_code="US",
        observation_date=ANCHOR,
        index_level=4742.83,
        trailing_earnings=221.41,
        forward_earnings_est=243.73,
        dividend_yield_pct=0.0155,
        buyback_yield_pct=0.025,
        cape_ratio=31.5,
        risk_free_nominal=0.0415,
        risk_free_real=0.0175,
        consensus_growth_5y=0.10,
        retention=0.60,
        roe=0.20,
        risk_free_confidence=0.95,
    )
    return fit_erp_us(inputs), inputs


def _rating_consolidated() -> object:
    rows: list[RatingAgencyRaw] = []
    for agency, raw in [("SP", "AA+"), ("MOODYS", "Aaa"), ("FITCH", "AA+")]:
        base_notch = lookup_base_notch(agency, raw)  # type: ignore[arg-type]
        rows.append(
            RatingAgencyRaw(
                agency=agency,  # type: ignore[arg-type]
                rating_raw=raw,
                rating_type="FC",
                base_notch=base_notch,
                notch_adjusted=apply_modifiers(base_notch=base_notch, outlook="stable", watch=None),
                outlook="stable",
                watch=None,
                action_date=ANCHOR,
            )
        )
    return consolidate(rows=rows, country_code="US", observation_date=ANCHOR)


def _crp_index() -> IndexResult:
    return IndexResult(
        index_code="CRP",
        country_code="PT",
        date=ANCHOR,
        methodology_version="CRP_v1.0",
        raw_value=0.039,
        zscore_clamped=0.0,
        value_0_100=50.0,
        confidence=0.85,
        flags=("CRP_VOL_STANDARD",),
        sub_indicators={"method_selected": "SOV_SPREAD"},
    )


def _expinf_index() -> IndexResult:
    return IndexResult(
        index_code="EXPINF_CANONICAL",
        country_code="US",
        date=ANCHOR,
        methodology_version="EXPINF_v1.0",
        raw_value=0.024,
        zscore_clamped=0.0,
        value_0_100=50.0,
        confidence=0.85,
        flags=(),
        sub_indicators={"methods_available": 1},
    )


def test_persist_all_four(db_session: Session) -> None:
    erp, inputs = _erp_us_fit()
    rating = _rating_consolidated()
    written = persist_many_overlay_results(
        db_session,
        erp=erp,  # type: ignore[arg-type]
        erp_inputs=inputs,
        rating=rating,  # type: ignore[arg-type]
        crp_index=_crp_index(),
        expected_inflation_index=_expinf_index(),
    )
    assert written == {"erp": 1, "crp": 1, "rating": 1, "expected_inflation": 1}
    assert db_session.query(ERPCanonical).count() == 1
    assert db_session.query(RatingsConsolidated).count() == 1
    assert db_session.query(IndexValue).count() == 2


def test_empty_call_returns_zeros(db_session: Session) -> None:
    assert persist_many_overlay_results(db_session) == {
        "erp": 0,
        "crp": 0,
        "rating": 0,
        "expected_inflation": 0,
    }


def test_erp_without_inputs_raises(db_session: Session) -> None:
    erp, _ = _erp_us_fit()
    with pytest.raises(ValueError, match="requires erp_inputs"):
        persist_many_overlay_results(db_session, erp=erp)  # type: ignore[arg-type]


def test_partial_subset_ok(db_session: Session) -> None:
    written = persist_many_overlay_results(
        db_session,
        crp_index=_crp_index(),
        expected_inflation_index=_expinf_index(),
    )
    assert written == {"erp": 0, "crp": 1, "rating": 0, "expected_inflation": 1}
    assert db_session.query(IndexValue).count() == 2


def test_duplicate_crp_bubbles_with_overlay_prefix(db_session: Session) -> None:
    persist_many_overlay_results(db_session, crp_index=_crp_index())
    with pytest.raises(DuplicatePersistError, match="overlay=crp"):
        persist_many_overlay_results(db_session, crp_index=_crp_index())


def test_duplicate_rating_bubbles_with_overlay_prefix(db_session: Session) -> None:
    rating = _rating_consolidated()
    persist_many_overlay_results(db_session, rating=rating)  # type: ignore[arg-type]
    with pytest.raises(DuplicatePersistError, match="overlay=rating"):
        persist_many_overlay_results(db_session, rating=rating)  # type: ignore[arg-type]
