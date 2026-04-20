"""Unit tests for AaiiConnector (xlsx + schema-drift guard)."""

from __future__ import annotations

import io
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import openpyxl
import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.aaii import (
    AAII_XLSX_URL,
    EXPECTED_HEADERS,
    AaiiConnector,
    AaiiSurveyObservation,
    SchemaChangedError,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "aaii_cache"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def aaii_connector(
    tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AaiiConnector]:
    monkeypatch.setattr(AaiiConnector._fetch_xlsx_bytes.retry, "wait", wait_none())
    conn = AaiiConnector(cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _load_cassette_bytes(name: str) -> bytes:
    return (CASSETTE_DIR / name).read_bytes()


# ---------------------------------------------------------------------------
# Cassette replay
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("ignore::UserWarning")
async def test_fetch_aaii_from_cassette(
    httpx_mock: HTTPXMock, aaii_connector: AaiiConnector
) -> None:
    httpx_mock.add_response(
        method="GET", content=_load_cassette_bytes("aaii_sentiment_2024_01_02.xlsx")
    )
    obs = await aaii_connector.fetch_aaii_sentiment(date(1990, 1, 1), date(2030, 1, 1))
    assert len(obs) > 100  # AAII has decades of history
    assert all(isinstance(o, AaiiSurveyObservation) for o in obs)
    # Bull/bear/neutral should roughly sum to 100% (±1% tolerance).
    sample = obs[-10:]
    for o in sample:
        total = o.bull_pct + o.bear_pct + o.neutral_pct
        assert 99.0 <= total <= 101.0, f"{o.observation_date}: bull+bear+neutral={total}"


@pytest.mark.filterwarnings("ignore::UserWarning")
async def test_fetch_latest_from_cassette(
    httpx_mock: HTTPXMock, aaii_connector: AaiiConnector
) -> None:
    httpx_mock.add_response(
        method="GET", content=_load_cassette_bytes("aaii_sentiment_2024_01_02.xlsx")
    )
    # Use a date within the cassette's historical range to guarantee a hit.
    target = date(2026, 3, 19)
    latest = await aaii_connector.fetch_latest(target, window_days=30)
    assert latest is not None
    assert latest.observation_date <= target


# ---------------------------------------------------------------------------
# Schema-drift guard
# ---------------------------------------------------------------------------


def _build_xlsx_with_headers(headers: tuple[str, ...]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SENTIMENT"
    for _ in range(3):
        ws.append(["", "", "", "", "", "", "", ""])
    ws.append(list(headers))
    # One data row (must be datetime in col 0 + decimals in cols 1-3 so it
    # survives the data-filter loop). Naive datetime per openpyxl (Excel
    # does not support tzinfo — parser relies on naive values anyway).
    ws.append([datetime(2024, 1, 4), 0.42, 0.32, 0.26])  # noqa: DTZ001
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def test_parse_rejects_drift_headers() -> None:
    # Keep row[0]='Date' so the anchor is found, but mutate cols 1..3.
    bad = _build_xlsx_with_headers(("Date", "Pct Bull", "Pct Neutral", "Pct Bear"))
    with pytest.raises(SchemaChangedError, match="header drift"):
        AaiiConnector._parse_workbook_bytes(bad)


def test_parse_rejects_missing_date_anchor() -> None:
    bad = _build_xlsx_with_headers(("Data", "Bullish", "Neutral", "Bearish"))
    with pytest.raises(SchemaChangedError, match="missing 'Date' header"):
        AaiiConnector._parse_workbook_bytes(bad)


def test_parse_accepts_expected_headers() -> None:
    good = _build_xlsx_with_headers(EXPECTED_HEADERS)
    obs = AaiiConnector._parse_workbook_bytes(good)
    assert len(obs) == 1
    assert obs[0].bull_pct == pytest.approx(42.0)


def test_parse_rejects_missing_sentiment_sheet() -> None:
    wb = openpyxl.Workbook()
    wb.active.title = "OTHER"
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    with pytest.raises(SchemaChangedError, match="SENTIMENT"):
        AaiiConnector._parse_workbook_bytes(buf.getvalue())


def test_parse_rejects_garbage_bytes() -> None:
    with pytest.raises(DataUnavailableError, match="unreadable"):
        AaiiConnector._parse_workbook_bytes(b"not an xlsx file")


def test_schema_changed_is_subclass_of_data_unavailable() -> None:
    """F4 AAII_PROXY fallback catches DataUnavailableError only."""
    assert issubclass(SchemaChangedError, DataUnavailableError)


# ---------------------------------------------------------------------------
# Dataclass / URL constants
# ---------------------------------------------------------------------------


def test_observation_bull_minus_bear_property() -> None:
    obs = AaiiSurveyObservation(
        observation_date=date(2024, 1, 4),
        bull_pct=42.5,
        bear_pct=25.0,
        neutral_pct=32.5,
    )
    assert obs.bull_minus_bear_pct == 17.5


def test_xlsx_url_constant() -> None:
    assert AAII_XLSX_URL == "https://www.aaii.com/files/surveys/sentiment.xlsx"


# ---------------------------------------------------------------------------
# Live canary (CAL-071) — @pytest.mark.slow
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_live_canary_aaii_recent(tmp_cache_dir: Path) -> None:
    """Fetch AAII current week; assert bull+bear+neutral ≈ 100% ±1%."""
    conn = AaiiConnector(cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_aaii_sentiment(today - timedelta(days=30), today)
        assert len(obs) >= 1
        for o in obs:
            total = o.bull_pct + o.bear_pct + o.neutral_pct
            assert 99.0 <= total <= 101.0, f"AAII {o.observation_date} total={total}"
    finally:
        await conn.aclose()
