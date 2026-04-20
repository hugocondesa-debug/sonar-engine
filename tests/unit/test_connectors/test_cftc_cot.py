"""Unit tests for CftcCotConnector (Socrata JSON API)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.cftc_cot import (
    CFTC_JSON_API,
    REQUIRED_FIELDS,
    CftcCotConnector,
    CotObservation,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cftc_cache"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def cftc_connector(
    tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[CftcCotConnector]:
    monkeypatch.setattr(CftcCotConnector._fetch_raw.retry, "wait", wait_none())
    conn = CftcCotConnector(cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _load_cassette(name: str) -> list[dict]:
    return json.loads((CASSETTE_DIR / name).read_text())


# ---------------------------------------------------------------------------
# Cassette replay
# ---------------------------------------------------------------------------


async def test_fetch_cot_sp500_from_cassette(
    httpx_mock: HTTPXMock, cftc_connector: CftcCotConnector
) -> None:
    rows = _load_cassette("cftc_cot_sp500_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=rows)
    obs = await cftc_connector.fetch_cot_sp500_net(date(2020, 1, 1), date(2030, 1, 1))
    assert len(obs) == len(rows)
    assert all(isinstance(o, CotObservation) for o in obs)
    assert all("E-MINI S&P 500" in o.contract for o in obs)
    # Sanity: non-commercial positions should be plausible
    # (tens of thousands to hundreds of thousands of contracts).
    for o in obs:
        assert 0 < o.noncomm_long < 1_000_000
        assert 0 < o.noncomm_short < 1_000_000


async def test_fetch_latest_from_cassette(
    httpx_mock: HTTPXMock, cftc_connector: CftcCotConnector
) -> None:
    rows = _load_cassette("cftc_cot_sp500_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=rows)
    # Pick the max date from the cassette.
    max_dt = max(
        datetime.fromisoformat(r["report_date_as_yyyy_mm_dd"].replace("Z", "+00:00")).date()
        for r in rows
    )
    latest = await cftc_connector.fetch_latest_sp500(max_dt, window_days=365)
    assert latest is not None
    assert latest.observation_date <= max_dt


# ---------------------------------------------------------------------------
# Schema-drift / parse guards
# ---------------------------------------------------------------------------


def test_parse_rows_missing_required_field_raises() -> None:
    # Omit noncomm_positions_long_all to trigger HALT #3 guard.
    bad = [
        {
            "report_date_as_yyyy_mm_dd": "2026-04-14T00:00:00.000",
            "market_and_exchange_names": "E-MINI S&P 500 - CME",
            "noncomm_positions_short_all": "100",
            # noncomm_positions_long_all missing
        }
    ]
    with pytest.raises(DataUnavailableError, match="missing field"):
        CftcCotConnector._parse_rows(bad)


def test_parse_rows_bad_date_raises() -> None:
    bad = [
        {
            "report_date_as_yyyy_mm_dd": "not-a-date",
            "market_and_exchange_names": "E-MINI S&P 500 - CME",
            "noncomm_positions_long_all": "100",
            "noncomm_positions_short_all": "100",
        }
    ]
    with pytest.raises(DataUnavailableError, match="row parse error"):
        CftcCotConnector._parse_rows(bad)


def test_parse_rows_non_integer_position_raises() -> None:
    bad = [
        {
            "report_date_as_yyyy_mm_dd": "2026-04-14T00:00:00.000",
            "market_and_exchange_names": "E-MINI S&P 500 - CME",
            "noncomm_positions_long_all": "not-a-number",
            "noncomm_positions_short_all": "100",
        }
    ]
    with pytest.raises(DataUnavailableError, match="row parse error"):
        CftcCotConnector._parse_rows(bad)


def test_parse_rows_happy() -> None:
    good = [
        {
            "report_date_as_yyyy_mm_dd": "2026-04-14T00:00:00.000",
            "market_and_exchange_names": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
            "noncomm_positions_long_all": "236683",
            "noncomm_positions_short_all": "352445",
        }
    ]
    obs = CftcCotConnector._parse_rows(good)
    assert len(obs) == 1
    assert obs[0].observation_date == date(2026, 4, 14)
    assert obs[0].noncomm_net == 236_683 - 352_445


def test_required_fields_constant() -> None:
    assert "noncomm_positions_long_all" in REQUIRED_FIELDS
    assert "noncomm_positions_short_all" in REQUIRED_FIELDS
    assert "report_date_as_yyyy_mm_dd" in REQUIRED_FIELDS
    assert "market_and_exchange_names" in REQUIRED_FIELDS


async def test_non_list_payload_raises(
    httpx_mock: HTTPXMock, cftc_connector: CftcCotConnector
) -> None:
    httpx_mock.add_response(method="GET", json={"error": "unexpected shape"})
    with pytest.raises(DataUnavailableError, match="non-list"):
        await cftc_connector.fetch_cot_sp500_net(date(2020, 1, 1), date(2030, 1, 1))


# ---------------------------------------------------------------------------
# Dataclass + URL
# ---------------------------------------------------------------------------


def test_cot_noncomm_net_property() -> None:
    obs = CotObservation(
        observation_date=date(2024, 1, 2),
        contract="E-MINI S&P 500",
        noncomm_long=200_000,
        noncomm_short=115_000,
    )
    assert obs.noncomm_net == 85_000


def test_api_url_constant() -> None:
    assert CFTC_JSON_API == "https://publicreporting.cftc.gov/resource/6dca-aqww.json"


# ---------------------------------------------------------------------------
# Live canary (CAL-071)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_live_canary_cot_sp500_recent(tmp_cache_dir: Path) -> None:
    """Fetch last 30 days SP500 COT; assert non-empty + plausible magnitude."""
    conn = CftcCotConnector(cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_cot_sp500_net(today - timedelta(days=30), today)
        assert len(obs) >= 2  # weekly → ~4 in 30d, tolerate 2 for holiday windows
        for o in obs:
            assert 0 < o.noncomm_long < 1_000_000
            assert 0 < o.noncomm_short < 1_000_000
            assert -500_000 < o.noncomm_net < 500_000
    finally:
        await conn.aclose()
