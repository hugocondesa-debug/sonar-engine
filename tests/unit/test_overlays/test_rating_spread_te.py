"""Sprint 4 — fixture tests for TE-driven rating-spread backfill.

Hermetic: TE HTTP responses mocked via ``pytest-httpx``; persistence
runs against an in-memory SQLite engine seeded from
``Base.metadata.create_all``. No live network calls; no engine DB.

Coverage:

* TE outlook string parsing (Stable / Negative Watch / N/A / empty).
* TE country-name to ISO alpha-2 mapping (Tier 1 overrides + unmappable).
* :meth:`TEConnector.fetch_sovereign_ratings_current` round-trip.
* :meth:`TEConnector.fetch_sovereign_ratings_historical` 200 + 404 paths.
* :func:`backfill_te_current_snapshot` end-to-end against in-memory DB
  (PT canonical 4-agency happy path + partial-coverage skip path).
* :func:`backfill_consolidate` harmonises sibling rating_id and writes
  ``ratings_consolidated`` rows whose UUID matches the agency_raw siblings.
* :func:`backfill_calibration_april_2026` writes 22 rows (idempotent).
"""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from tenacity import wait_none

import sonar.db.session  # noqa: F401 — registers PRAGMA foreign_keys listener
from sonar.connectors.te import (
    TEConnector,
    TERatingCurrent,
    TERatingHistoricalAction,
)
from sonar.db.models import (
    Base,
    RatingsAgencyRaw,
    RatingsConsolidated,
    RatingsSpreadCalibration,
)
from sonar.overlays.rating_spread import (
    METHODOLOGY_VERSION_AGENCY,
    METHODOLOGY_VERSION_CALIBRATION,
    METHODOLOGY_VERSION_CONSOLIDATED,
)
from sonar.overlays.rating_spread_backfill import (
    CALIBRATION_DATE_APRIL_2026,
    TE_COUNTRY_OVERRIDES_TIER1,
    TIER1_COUNTRIES,
    _normalize_te_agency,
    _parse_te_outlook,
    _te_country_to_iso,
    backfill_calibration_april_2026,
    backfill_consolidate,
    backfill_te_current_snapshot,
    backfill_te_historical,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Fresh in-memory SQLite + Base.metadata.create_all per test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _disable_tenacity_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(TEConnector._fetch_raw.retry, "wait", wait_none())


@pytest_asyncio.fixture
async def te_connector(tmp_path: Path) -> AsyncIterator[TEConnector]:
    cache_dir = tmp_path / "te_cache"
    cache_dir.mkdir()
    conn = TEConnector(api_key="test:secret", cache_dir=str(cache_dir))
    yield conn
    await conn.aclose()


def _pt_snapshot_payload() -> list[dict[str, object]]:
    """Empirical Portugal-shaped row from /ratings (truncated to 4 countries)."""
    return [
        {
            "Country": "Portugal",
            "TE": "73",
            "TE_Outlook": "Stable",
            "SP": "A+",
            "SP_Outlook": "Positive",
            "Moodys": "A3",
            "Moodys_Outlook": "Stable",
            "Fitch": "A",
            "Fitch_Outlook": "Positive",
            "DBRS": "A (high)",
            "DBRS_Outlook": "Stable",
        },
        {
            "Country": "United States",
            "TE": "94",
            "TE_Outlook": "Stable",
            "SP": "AA+",
            "SP_Outlook": "Stable",
            "Moodys": "Aaa",
            "Moodys_Outlook": "Negative",
            "Fitch": "AA+",
            "Fitch_Outlook": "Stable",
            "DBRS": "AAA",
            "DBRS_Outlook": "Stable",
        },
        {
            # Partial coverage: only 2 of 4 agencies populate.
            "Country": "Australia",
            "TE": "90",
            "TE_Outlook": "Stable",
            "SP": "AAA",
            "SP_Outlook": "Stable",
            "Moodys": "Aaa",
            "Moodys_Outlook": "Stable",
            "Fitch": "",
            "Fitch_Outlook": "",
            "DBRS": "",
            "DBRS_Outlook": "",
        },
        {
            # Unmappable country (Albania not in TIER1 overrides).
            "Country": "Albania",
            "TE": "40",
            "TE_Outlook": "Stable",
            "SP": "BB",
            "SP_Outlook": "Stable",
            "Moodys": "Ba3",
            "Moodys_Outlook": "Stable",
            "Fitch": "",
            "Fitch_Outlook": "",
            "DBRS": "",
            "DBRS_Outlook": "",
        },
    ]


def _pt_historical_payload() -> list[dict[str, object]]:
    """Three sample historical actions for Portugal (descending by date)."""
    return [
        {
            "Country": "Portugal",
            "Date": "3/6/2026",
            "Agency": "Fitch",
            "Rating": "A",
            "Outlook": "Positive",
        },
        {
            "Country": "Portugal",
            "Date": "2/27/2026",
            "Agency": "S&P",
            "Rating": "A+",
            "Outlook": "Positive",
        },
        {
            "Country": "Portugal",
            "Date": "1/17/2025",
            "Agency": "DBRS",
            "Rating": "A (high)",
            "Outlook": "Stable",
        },
    ]


# ---------------------------------------------------------------------------
# 1. Outlook parse — edge cases
# ---------------------------------------------------------------------------


class TestParseTEOutlook:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Stable", ("stable", None)),
            ("Positive", ("positive", None)),
            ("Negative", ("negative", None)),
            ("Developing", ("developing", None)),
            ("Negative Watch", ("negative", "watch_negative")),
            ("Positive Watch", ("positive", "watch_positive")),
            ("Stable Watch", ("stable", None)),  # 'stable' is the default base
            ("N/A", ("stable", None)),
            ("", ("stable", None)),
            ("   ", ("stable", None)),
            ("STABLE", ("stable", None)),  # case-insensitive
            ("negative watch", ("negative", "watch_negative")),
        ],
    )
    def test_parse_outlook(self, raw: str, expected: tuple[str, str | None]) -> None:
        assert _parse_te_outlook(raw) == expected


# ---------------------------------------------------------------------------
# 2. Country mapping — overrides + unmappable
# ---------------------------------------------------------------------------


class TestCountryMapping:
    @pytest.mark.parametrize(
        ("name", "iso"),
        [
            ("United States", "US"),
            ("Germany", "DE"),
            ("Portugal", "PT"),
            ("United Kingdom", "GB"),
            ("Japan", "JP"),
            ("Australia", "AU"),
        ],
    )
    def test_overrides_resolve(self, name: str, iso: str) -> None:
        assert _te_country_to_iso(name) == iso

    @pytest.mark.parametrize(
        "name", ["Albania", "Botswana", "Vanuatu", "South Korea", "Czech Republic"]
    )
    def test_unmappable_returns_none(self, name: str) -> None:
        # South Korea + Czech Republic intentionally NOT in TIER1 —
        # cohort is sovereign Tier 1 only (Sprint 4 + Sprint 6 = 15 países;
        # CAL-RATING-COHORT-EXPANSION closed Sprint 6).
        assert _te_country_to_iso(name) is None

    def test_tier1_cohort_complete(self) -> None:
        assert set(TE_COUNTRY_OVERRIDES_TIER1.values()) == set(TIER1_COUNTRIES)
        assert len(TIER1_COUNTRIES) == 15

    @pytest.mark.parametrize(
        ("raw", "code"),
        [
            ("S&P", "SP"),
            ("Moody's", "MOODYS"),
            ("Fitch", "FITCH"),
            ("DBRS", "DBRS"),
            ("DBRS Morningstar", "DBRS"),
        ],
    )
    def test_agency_normalize(self, raw: str, code: str) -> None:
        assert _normalize_te_agency(raw) == code

    def test_agency_unknown(self) -> None:
        assert _normalize_te_agency("Scope") is None


# ---------------------------------------------------------------------------
# 3. TE connector — fetch_sovereign_ratings_current + historical
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sovereign_ratings_current_parses_wide_rows(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_pt_snapshot_payload())
    rows = await te_connector.fetch_sovereign_ratings_current()

    assert len(rows) == 4
    pt = next(r for r in rows if r.country == "Portugal")
    assert isinstance(pt, TERatingCurrent)
    assert pt.sp_rating == "A+"
    assert pt.sp_outlook == "Positive"
    assert pt.moodys_rating == "A3"
    assert pt.fitch_rating == "A"
    assert pt.dbrs_rating == "A (high)"
    assert pt.te_score == 73


@pytest.mark.asyncio
async def test_fetch_sovereign_ratings_current_handles_blank_te_score(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Portugal",
                "TE": "",
                "TE_Outlook": "",
                "SP": "A+",
                "SP_Outlook": "Stable",
                "Moodys": "",
                "Moodys_Outlook": "",
                "Fitch": "",
                "Fitch_Outlook": "",
                "DBRS": "",
                "DBRS_Outlook": "",
            }
        ],
    )
    rows = await te_connector.fetch_sovereign_ratings_current()
    assert len(rows) == 1
    assert rows[0].te_score is None


@pytest.mark.asyncio
async def test_fetch_sovereign_ratings_historical_parses_dates(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_pt_historical_payload())
    rows = await te_connector.fetch_sovereign_ratings_historical("Portugal")

    assert len(rows) == 3
    assert all(isinstance(r, TERatingHistoricalAction) for r in rows)
    assert rows[0].action_date == date(2026, 3, 6)
    assert rows[0].agency == "Fitch"
    assert rows[0].rating_raw == "A"
    assert rows[0].outlook == "Positive"


@pytest.mark.asyncio
async def test_fetch_sovereign_ratings_historical_404_returns_empty(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(method="GET", status_code=404)
    rows = await te_connector.fetch_sovereign_ratings_historical("Vanuatu")
    assert rows == []


@pytest.mark.asyncio
async def test_fetch_sovereign_ratings_current_cache_hit_no_http(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_pt_snapshot_payload())

    rows_first = await te_connector.fetch_sovereign_ratings_current()
    rows_second = await te_connector.fetch_sovereign_ratings_current()
    assert len(rows_first) == len(rows_second) == 4
    # Only one HTTP request was registered; second call served from cache.


# ---------------------------------------------------------------------------
# 4. Backfill — current snapshot end-to-end (PT canonical + AU partial)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_te_current_snapshot_pt_canonical(
    httpx_mock: HTTPXMock, te_connector: TEConnector, db_session: Session
) -> None:
    httpx_mock.add_response(method="GET", json=_pt_snapshot_payload())

    snapshot_date = date(2026, 4, 25)
    result = await backfill_te_current_snapshot(
        db_session,
        te_connector=te_connector,
        countries=("PT", "US", "AU"),
        snapshot_date=snapshot_date,
    )

    # PT has 4 agencies, US has 4, AU has 2 → 10 rows persisted.
    assert result.agency_raw_persisted == 10
    assert result.agency_raw_skipped_invalid == 0
    assert result.countries_processed == 3  # PT, US, AU all in cohort

    # Albania (in payload, not in TIER1 overrides) → unmappable counter.
    assert result.countries_unmappable == 1

    pt_rows = (
        db_session.query(RatingsAgencyRaw).filter_by(country_code="PT", date=snapshot_date).all()
    )
    assert len(pt_rows) == 4
    by_agency = {r.agency: r for r in pt_rows}
    assert set(by_agency) == {"SP", "MOODYS", "FITCH", "DBRS"}

    # SP A+ Positive → base 17, +0.25 → 17.25.
    assert by_agency["SP"].rating_raw == "A+"
    assert by_agency["SP"].sonar_notch_base == 17
    assert by_agency["SP"].notch_adjusted == pytest.approx(17.25)
    assert by_agency["SP"].outlook == "positive"
    assert by_agency["SP"].watch is None
    assert by_agency["SP"].source_connector == "te"
    assert by_agency["SP"].methodology_version == METHODOLOGY_VERSION_AGENCY

    # All four PT siblings share the same rating_id (per snapshot).
    assert len({r.rating_id for r in pt_rows}) == 1


@pytest.mark.asyncio
async def test_backfill_te_current_snapshot_partial_agencies_au(
    httpx_mock: HTTPXMock, te_connector: TEConnector, db_session: Session
) -> None:
    httpx_mock.add_response(method="GET", json=_pt_snapshot_payload())

    result = await backfill_te_current_snapshot(
        db_session,
        te_connector=te_connector,
        countries=("AU",),
        snapshot_date=date(2026, 4, 25),
    )

    # AU has only SP + MOODYS (Fitch + DBRS empty in payload).
    assert result.agency_raw_persisted == 2
    au_rows = db_session.query(RatingsAgencyRaw).filter_by(country_code="AU").all()
    assert {r.agency for r in au_rows} == {"SP", "MOODYS"}
    assert all(r.sonar_notch_base == 21 for r in au_rows)  # AAA / Aaa


@pytest.mark.asyncio
async def test_backfill_te_current_snapshot_idempotent(
    httpx_mock: HTTPXMock, te_connector: TEConnector, db_session: Session
) -> None:
    httpx_mock.add_response(method="GET", json=_pt_snapshot_payload())

    first = await backfill_te_current_snapshot(
        db_session,
        te_connector=te_connector,
        countries=("PT",),
        snapshot_date=date(2026, 4, 25),
    )
    second = await backfill_te_current_snapshot(
        db_session,
        te_connector=te_connector,
        countries=("PT",),
        snapshot_date=date(2026, 4, 25),
    )
    assert first.agency_raw_persisted == 4
    assert second.agency_raw_persisted == 0
    assert second.agency_raw_skipped_existing == 4
    assert db_session.query(RatingsAgencyRaw).count() == 4


# ---------------------------------------------------------------------------
# 5. Backfill — historical
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_te_historical_pt(
    httpx_mock: HTTPXMock, te_connector: TEConnector, db_session: Session
) -> None:
    httpx_mock.add_response(method="GET", json=_pt_historical_payload())

    result = await backfill_te_historical(
        db_session,
        te_connector=te_connector,
        countries=("PT",),
        delay_seconds=0.0,
    )

    assert result.historical_actions_fetched == 3
    assert result.agency_raw_persisted == 3
    assert result.countries_processed == 1

    rows = db_session.query(RatingsAgencyRaw).filter_by(country_code="PT").all()
    assert len(rows) == 3
    fitch = next(r for r in rows if r.agency == "FITCH")
    assert fitch.action_date == date(2026, 3, 6)
    assert fitch.rating_raw == "A"
    assert fitch.outlook == "positive"
    assert fitch.flags is None  # post-2023 → no BACKFILL_STALE


# ---------------------------------------------------------------------------
# 6. Backfill — consolidate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_consolidate_pt_full_4_agencies(
    httpx_mock: HTTPXMock, te_connector: TEConnector, db_session: Session
) -> None:
    httpx_mock.add_response(method="GET", json=_pt_snapshot_payload())
    snapshot_date = date(2026, 4, 25)
    await backfill_te_current_snapshot(
        db_session,
        te_connector=te_connector,
        countries=("PT",),
        snapshot_date=snapshot_date,
    )

    result = backfill_consolidate(db_session)

    assert result.consolidated_persisted == 1
    cons = (
        db_session.query(RatingsConsolidated).filter_by(country_code="PT", date=snapshot_date).one()
    )
    assert cons.agencies_count == 4
    assert cons.methodology_version == METHODOLOGY_VERSION_CONSOLIDATED
    payload = json.loads(cons.agencies_json)
    assert set(payload) == {"SP", "MOODYS", "FITCH", "DBRS"}

    # Sibling rating_id harmonised post-consolidation.
    pt_raws = (
        db_session.query(RatingsAgencyRaw).filter_by(country_code="PT", date=snapshot_date).all()
    )
    rating_ids = {r.rating_id for r in pt_raws}
    assert rating_ids == {cons.rating_id}


# ---------------------------------------------------------------------------
# 7. Calibration seed (idempotent, 22 rows)
# ---------------------------------------------------------------------------


def test_backfill_calibration_april_2026_writes_22_rows(db_session: Session) -> None:
    n = backfill_calibration_april_2026(db_session)
    assert n == 22

    rows = (
        db_session.query(RatingsSpreadCalibration)
        .filter_by(calibration_date=CALIBRATION_DATE_APRIL_2026)
        .all()
    )
    assert len(rows) == 22
    notches = sorted(r.sonar_notch_int for r in rows)
    assert notches == list(range(22))

    # Anchor at notch 15 → 90 bps per spec §4 line 147.
    n15 = next(r for r in rows if r.sonar_notch_int == 15)
    assert n15.default_spread_bps == 90
    assert n15.range_low_bps == 60
    assert n15.range_high_bps == 130
    assert n15.rating_equivalent == "A"

    # Notch 0 stores NULL spread per spec (default territory).
    n0 = next(r for r in rows if r.sonar_notch_int == 0)
    assert n0.default_spread_bps is None
    assert n0.rating_equivalent == "D"

    assert all(r.methodology_version == METHODOLOGY_VERSION_CALIBRATION for r in rows)


def test_backfill_calibration_idempotent(db_session: Session) -> None:
    first = backfill_calibration_april_2026(db_session)
    second = backfill_calibration_april_2026(db_session)
    assert first == 22
    assert second == 0
    assert db_session.query(RatingsSpreadCalibration).count() == 22
