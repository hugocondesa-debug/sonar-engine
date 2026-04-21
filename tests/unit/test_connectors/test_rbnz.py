"""Unit tests for RBNZ statistical-tables L0 connector (Sprint U-NZ).

The RBNZ statistics host (``https://www.rbnz.govt.nz/``) currently
403s every probed path from the SONAR VPS regardless of User-Agent
(empirical probe 2026-04-21, see module docstring of
:mod:`sonar.connectors.rbnz`). The connector therefore ships
wire-ready but raising :class:`DataUnavailableError` against the live
host; tests mock the HTTP layer so the parser + UA discipline + cache
behaviour can still be exercised deterministically. Once the
perimeter block lifts (CAL-NZ-RBNZ-TABLES) the @slow live canary
switches from "expected DataUnavailable" to a band assertion.

Scope:

- Series-ID / URL catalogue stability (regression guard).
- UA discipline (SONAR-branded descriptive UA required for the day
  the edge unblocks; guard against accidental Mozilla regressions).
- Happy-path CSV parse against a synthetic B2 cassette (mirrors
  expected RBNZ format pending empirical validation).
- Date-range window filtering.
- Schema-drift raises (missing ``Series ID`` row, missing OCR column).
- Perimeter-block detection (HTML ``Website unavailable`` body →
  :class:`DataUnavailableError` even under a 200 response).
- HTTP error → :class:`DataUnavailableError`.
- Disk-cache round-trip short-circuits the HTTP call.
- @slow live canary probes the live host and expects DataUnavailable
  for as long as the edge block persists.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
from tenacity import wait_none

from sonar.connectors.base import Observation
from sonar.connectors.rbnz import (
    RBNZ_B2_SERIES,
    RBNZ_B2_SERIES_URL,
    RBNZ_GOVT_10Y_SERIES,
    RBNZ_OCR_COLUMN,
    RBNZ_STATISTICS_BASE_URL,
    RBNZ_USER_AGENT,
    RBNZConnector,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


def _b2_cassette() -> str:
    return (CASSETTE_DIR / "rbnz_b2_sample.csv").read_text()


def test_series_ids_are_canonical() -> None:
    """Regression guard — RBNZ B-series codes must stay stable."""
    assert RBNZ_B2_SERIES == "hb2-daily"
    assert RBNZ_GOVT_10Y_SERIES == "hb2-weekly"
    assert RBNZ_OCR_COLUMN == "OCR"


def test_base_url_canonical() -> None:
    assert RBNZ_STATISTICS_BASE_URL == "https://www.rbnz.govt.nz"
    assert RBNZ_B2_SERIES_URL.startswith(RBNZ_STATISTICS_BASE_URL)
    assert RBNZ_B2_SERIES_URL.endswith("hb2-daily.csv")


def test_user_agent_is_descriptive() -> None:
    """Guard against accidental Mozilla regressions once the edge unblocks."""
    assert "SONAR" in RBNZ_USER_AGENT
    assert "Mozilla" not in RBNZ_USER_AGENT


class TestRBNZConnectorLifecycle:
    @pytest.mark.asyncio
    async def test_instantiation_and_aclose(self, tmp_path: Path) -> None:
        conn = RBNZConnector(cache_dir=str(tmp_path / "rbnz"))
        assert conn.CONNECTOR_ID == "rbnz"
        assert conn.CACHE_NAMESPACE == "rbnz_stats"
        await conn.aclose()


@pytest.fixture
async def rbnz_connector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RBNZConnector:
    monkeypatch.setattr(RBNZConnector._fetch_raw.retry, "wait", wait_none())
    return RBNZConnector(cache_dir=str(tmp_path / "rbnz"))


class TestRBNZConnectorParse:
    """Parser-only tests — static bodies, no network."""

    def test_parse_happy_path_extracts_ocr_column(self) -> None:
        body = _b2_cassette()
        parsed = RBNZConnector._parse_csv(
            body, series_label=RBNZ_B2_SERIES, column_label=RBNZ_OCR_COLUMN
        )
        assert len(parsed) == 10
        assert parsed[0] == (date(2024, 12, 30), 4.25)
        assert parsed[-1] == (date(2026, 4, 8), 2.25)
        for _, v in parsed:
            assert 0.0 <= v <= 10.0

    def test_parse_missing_series_id_row_raises(self) -> None:
        body = "title,col\n2024-01-01,1.0\n"
        with pytest.raises(DataUnavailableError, match="no 'Series ID' header row"):
            RBNZConnector._parse_csv(body, series_label="hb2-daily", column_label="OCR")

    def test_parse_missing_column_raises(self) -> None:
        body = "Series ID,NOT_OCR\n2024-01-01,1.0\n"
        with pytest.raises(DataUnavailableError, match="column='OCR' not in header"):
            RBNZConnector._parse_csv(body, series_label="hb2-daily", column_label="OCR")

    def test_parse_skips_bad_dates_and_empty_cells(self) -> None:
        body = (
            "Series ID,OCR\n"
            "bad-date,4.25\n"
            "2024-12-30,\n"  # empty value skipped
            "2024-12-31,4.25\n"
        )
        parsed = RBNZConnector._parse_csv(body, series_label="hb2-daily", column_label="OCR")
        assert parsed == [(date(2024, 12, 31), 4.25)]

    def test_parse_raises_when_no_rows_parseable(self) -> None:
        body = "Series ID,OCR\nbad-date,4.25\n2024-12-30,\n"
        with pytest.raises(DataUnavailableError, match="no parseable rows"):
            RBNZConnector._parse_csv(body, series_label="hb2-daily", column_label="OCR")


class TestRBNZConnectorFetchSeries:
    @pytest.mark.asyncio
    async def test_happy_path_parses_b2_cassette(
        self, httpx_mock: HTTPXMock, rbnz_connector: RBNZConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET", text=_b2_cassette(), headers={"content-type": "text/csv"}
        )
        try:
            obs = await rbnz_connector.fetch_ocr(date(2024, 12, 30), date(2026, 5, 1))
            assert len(obs) == 10
            assert all(isinstance(o, Observation) for o in obs)
            assert obs[0].country_code == "NZ"
            assert obs[0].source == "RBNZ"
            assert obs[0].source_series_id == f"{RBNZ_B2_SERIES}:{RBNZ_OCR_COLUMN}"
            # Sanity: yield_bps conversion is (rate_pct * 100) rounded.
            assert obs[0].yield_bps == 425
            assert obs[-1].yield_bps == 225
        finally:
            await rbnz_connector.aclose()

    @pytest.mark.asyncio
    async def test_date_range_filtering(
        self, httpx_mock: HTTPXMock, rbnz_connector: RBNZConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET", text=_b2_cassette(), headers={"content-type": "text/csv"}
        )
        try:
            obs = await rbnz_connector.fetch_ocr(date(2025, 1, 1), date(2025, 12, 31))
            dates = [o.observation_date for o in obs]
            for d in dates:
                assert date(2025, 1, 1) <= d <= date(2025, 12, 31)
            assert len(obs) >= 3
        finally:
            await rbnz_connector.aclose()

    @pytest.mark.asyncio
    async def test_no_rows_in_window_raises(
        self, httpx_mock: HTTPXMock, rbnz_connector: RBNZConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET", text=_b2_cassette(), headers={"content-type": "text/csv"}
        )
        try:
            with pytest.raises(DataUnavailableError, match="no rows in"):
                await rbnz_connector.fetch_ocr(date(2030, 1, 1), date(2030, 12, 31))
        finally:
            await rbnz_connector.aclose()

    @pytest.mark.asyncio
    async def test_http_403_raises_data_unavailable(
        self, httpx_mock: HTTPXMock, rbnz_connector: RBNZConnector
    ) -> None:
        # Mock the perimeter 403 we observed empirically (2026-04-21).
        httpx_mock.add_response(method="GET", status_code=403, text="Website unavailable")
        httpx_mock.add_response(method="GET", status_code=403, text="Website unavailable")
        httpx_mock.add_response(method="GET", status_code=403, text="Website unavailable")
        try:
            with pytest.raises(DataUnavailableError, match="HTTP error"):
                await rbnz_connector.fetch_ocr(date(2024, 12, 1), date(2024, 12, 31))
        finally:
            await rbnz_connector.aclose()

    @pytest.mark.asyncio
    async def test_200_html_perimeter_body_raises_data_unavailable(
        self, httpx_mock: HTTPXMock, rbnz_connector: RBNZConnector
    ) -> None:
        """Edge occasionally serves 200 + HTML perimeter page."""
        html = "<!DOCTYPE html><html><body><h1>Website unavailable</h1></body></html>"
        httpx_mock.add_response(
            method="GET", status_code=200, text=html, headers={"content-type": "text/html"}
        )
        try:
            with pytest.raises(DataUnavailableError, match="HTML perimeter page"):
                await rbnz_connector.fetch_ocr(date(2024, 12, 1), date(2024, 12, 31))
        finally:
            await rbnz_connector.aclose()

    @pytest.mark.asyncio
    async def test_cache_short_circuits_http(
        self, httpx_mock: HTTPXMock, rbnz_connector: RBNZConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET", text=_b2_cassette(), headers={"content-type": "text/csv"}
        )
        try:
            first = await rbnz_connector.fetch_ocr(date(2024, 12, 30), date(2025, 1, 5))
            # Second call must not hit the HTTP mock — no second response queued.
            second = await rbnz_connector.fetch_ocr(date(2024, 12, 30), date(2025, 1, 5))
            assert [o.observation_date for o in first] == [o.observation_date for o in second]
        finally:
            await rbnz_connector.aclose()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_canary_rbnz_ocr_expects_block(tmp_path: Path) -> None:
    """Live probe of RBNZ B2 — currently expected to 403 at the perimeter.

    Sprint U-NZ probe (2026-04-21) confirmed the RBNZ host 403s every
    path; the canary documents this state until CAL-NZ-RBNZ-TABLES
    closes. Once the edge unblocks, flip this assertion to a band
    check (OCR in [0.25, 5.50]%) — the parser is ready.

    Skipped when ``SONAR_SKIP_NETWORK_TESTS=1`` (local CI / offline
    runs).
    """
    if os.environ.get("SONAR_SKIP_NETWORK_TESTS") == "1":
        pytest.skip("SONAR_SKIP_NETWORK_TESTS=1")
    conn = RBNZConnector(cache_dir=str(tmp_path / "rbnz"))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=30)
        with pytest.raises(DataUnavailableError):
            await conn.fetch_ocr(start, today)
    except httpx.HTTPError:
        # Network-level failure also counts as "still blocked" for the
        # purposes of this canary — the point is that no OCR rows land.
        pass
    finally:
        await conn.aclose()
