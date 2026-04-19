"""Persistence test for rating-spread overlay rows."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from sonar.db.models import (
    RatingsAgencyRaw as RatingsAgencyRawDB,
    RatingsConsolidated as RatingsConsolidatedDB,
)
from sonar.db.persistence import (
    DuplicatePersistError,
    persist_rating_agency_row,
    persist_rating_consolidated,
)
from sonar.overlays.rating_spread import (
    METHODOLOGY_VERSION_AGENCY,
    METHODOLOGY_VERSION_CONSOLIDATED,
    RatingAgencyRaw,
    apply_modifiers,
    consolidate,
    lookup_base_notch,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _make(agency: str, raw: str) -> RatingAgencyRaw:
    base = lookup_base_notch(agency, raw)
    return RatingAgencyRaw(
        agency=agency,
        rating_raw=raw,
        rating_type="FC",
        base_notch=base,
        notch_adjusted=apply_modifiers(base, "stable"),
        outlook="stable",
        watch=None,
        action_date=date(2026, 4, 17),
    )


def test_persist_agency_row_then_consolidated_join_by_rating_id(db_session: Session) -> None:
    rid = str(uuid4())
    rows = [
        _make("SP", "A-"),
        _make("MOODYS", "A3"),
        _make("FITCH", "A-"),
        _make("DBRS", "A (low)"),
    ]
    for r in rows:
        persist_rating_agency_row(
            db_session,
            r,
            country_code="PT",
            observation_date=date(2026, 4, 17),
            rating_id=rid,
            source_connector="manual_seed",
            methodology_version=METHODOLOGY_VERSION_AGENCY,
        )

    agency_count = (
        db_session.query(RatingsAgencyRawDB)
        .filter_by(country_code="PT", date=date(2026, 4, 17), rating_type="FC")
        .count()
    )
    assert agency_count == 4

    consolidated = consolidate(rows, country_code="PT", observation_date=date(2026, 4, 17))
    persist_rating_consolidated(
        db_session, consolidated, methodology_version=METHODOLOGY_VERSION_CONSOLIDATED
    )

    db_row = (
        db_session.query(RatingsConsolidatedDB)
        .filter_by(country_code="PT", date=date(2026, 4, 17), rating_type="FC")
        .one()
    )
    assert db_row.consolidated_sonar_notch == 15.0
    assert db_row.default_spread_bps == 90
    assert db_row.confidence >= 0.85
    agencies = json.loads(db_row.agencies_json)
    assert set(agencies.keys()) == {"SP", "MOODYS", "FITCH", "DBRS"}


def test_duplicate_agency_row_raises(db_session: Session) -> None:
    rid = str(uuid4())
    row = _make("SP", "A-")
    persist_rating_agency_row(
        db_session,
        row,
        country_code="PT",
        observation_date=date(2026, 4, 17),
        rating_id=rid,
        source_connector="manual_seed",
        methodology_version=METHODOLOGY_VERSION_AGENCY,
    )
    with pytest.raises(DuplicatePersistError, match="Rating agency"):
        persist_rating_agency_row(
            db_session,
            row,
            country_code="PT",
            observation_date=date(2026, 4, 17),
            rating_id=rid,
            source_connector="manual_seed",
            methodology_version=METHODOLOGY_VERSION_AGENCY,
        )


def test_duplicate_consolidated_raises(db_session: Session) -> None:
    rows = [_make("SP", "A-"), _make("MOODYS", "A3")]
    consolidated = consolidate(rows, country_code="PT", observation_date=date(2026, 4, 17))
    persist_rating_consolidated(db_session, consolidated)
    # second persist same triplet → fails on uq_rc_cdrm
    with pytest.raises(DuplicatePersistError, match="Consolidated rating"):
        persist_rating_consolidated(db_session, consolidated)
