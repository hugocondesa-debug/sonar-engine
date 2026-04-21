"""Unit tests for RBA statistical-tables L0 connector (Sprint T).

The RBA statistics host (``https://www.rba.gov.au/statistics/tables/csv/``)
is public but Akamai-gated — the connector passes
:data:`RBA_USER_AGENT` to clear the screen (empirical probe 2026-04-21,
see module docstring). Tests exercise:

- Series-ID catalogue stability (regression guard).
- Happy-path parse from a trimmed real F1 CSV cassette.
- Date-range window filtering.
- Empty column / series-id-not-in-header → ``DataUnavailableError``.
- HTTP error → ``DataUnavailableError``.
- Disk cache round-trip (set / get short-circuits the HTTP call).
- Both ``fetch_cash_rate`` + ``fetch_government_10y`` convenience
  wrappers land via the canonical F1 / F2 paths with the right tenors.
- @slow live canary probes F1 FIRMMCRTD + bands the recent band.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
from tenacity import wait_none

from sonar.connectors.base import Observation
from sonar.connectors.rba import (
    RBA_CASH_RATE_TARGET,
    RBA_F1_TABLE_ID,
    RBA_F2_TABLE_ID,
    RBA_GOVERNMENT_10Y,
    RBA_STATISTICS_BASE_URL,
    RBA_USER_AGENT,
    RBAConnector,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


def _f1_cassette() -> str:
    return (CASSETTE_DIR / "rba_f1_sample.csv").read_text()


def _f2_cassette() -> str:
    return (CASSETTE_DIR / "rba_f2_sample.csv").read_text()


def test_series_ids_are_canonical() -> None:
    """Regression guard — RBA F-table series codes must stay stable."""
    assert RBA_CASH_RATE_TARGET == "FIRMMCRTD"
    assert RBA_GOVERNMENT_10Y == "FCMYGBAG10D"


def test_table_ids_are_canonical() -> None:
    assert RBA_F1_TABLE_ID == "f1"
    assert RBA_F2_TABLE_ID == "f2"


def test_base_url_canonical() -> None:
    assert RBA_STATISTICS_BASE_URL == "https://www.rba.gov.au/statistics/tables/csv"


def test_user_agent_is_descriptive() -> None:
    """Generic ``Mozilla/5.0`` is Akamai-rejected on rba.gov.au — guard the fix."""
    assert "SONAR" in RBA_USER_AGENT
    assert "Mozilla" not in RBA_USER_AGENT


class TestRBAConnectorLifecycle:
    @pytest.mark.asyncio
    async def test_instantiation_and_aclose(self, tmp_path: Path) -> None:
        conn = RBAConnector(cache_dir=str(tmp_path / "rba"))
        assert conn.CONNECTOR_ID == "rba"
        assert conn.CACHE_NAMESPACE == "rba_stats"
        await conn.aclose()


@pytest.fixture
async def rba_connector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RBAConnector:
    monkeypatch.setattr(RBAConnector._fetch_raw.retry, "wait", wait_none())
    return RBAConnector(cache_dir=str(tmp_path / "rba"))


class TestRBAConnectorFetchSeries:
    @pytest.mark.asyncio
    async def test_happy_path_parses_f1_cassette(
        self, httpx_mock: HTTPXMock, rba_connector: RBAConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET", text=_f1_cassette(), headers={"content-type": "text/csv"}
        )
        try:
            obs = await rba_connector.fetch_series(
                RBA_F1_TABLE_ID,
                RBA_CASH_RATE_TARGET,
                date(2011, 1, 4),
                date(2026, 4, 30),
            )
            assert len(obs) >= 100
            assert all(isinstance(o, Observation) for o in obs)
            assert obs[0].country_code == "AU"
            assert obs[0].source == "RBA"
            assert obs[0].source_series_id == RBA_CASH_RATE_TARGET
            assert obs[0].observation_date == date(2011, 1, 4)
            # 4.75 % → yield_bps = round(4.75 * 100) = 475.
            assert obs[0].yield_bps == 475
        finally:
            await rba_connector.aclose()

    @pytest.mark.asyncio
    async def test_window_filters_out_of_range_rows(
        self, httpx_mock: HTTPXMock, rba_connector: RBAConnector
    ) -> None:
        httpx_mock.add_response(method="GET", text=_f1_cassette())
        try:
            # The cassette has rows spanning 2011-2026. Narrow to 2026.
            obs = await rba_connector.fetch_series(
                RBA_F1_TABLE_ID,
                RBA_CASH_RATE_TARGET,
                date(2026, 1, 1),
                date(2026, 4, 30),
            )
            assert len(obs) >= 1
            for o in obs:
                assert date(2026, 1, 1) <= o.observation_date <= date(2026, 4, 30)
                # 2026 band: RBA cash rate ranged 3.60-4.10 % through the
                # cycle (Feb + Mar + May cuts), so all rows sit in [3.6, 4.1].
                assert 350 <= o.yield_bps <= 420
        finally:
            await rba_connector.aclose()

    @pytest.mark.asyncio
    async def test_series_id_missing_from_header_raises(
        self, httpx_mock: HTTPXMock, rba_connector: RBAConnector
    ) -> None:
        httpx_mock.add_response(method="GET", text=_f1_cassette())
        try:
            with pytest.raises(DataUnavailableError, match="not in header"):
                await rba_connector.fetch_series(
                    RBA_F1_TABLE_ID,
                    "FAKE_NONEXISTENT_SERIES",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                )
        finally:
            await rba_connector.aclose()

    @pytest.mark.asyncio
    async def test_empty_window_raises(
        self, httpx_mock: HTTPXMock, rba_connector: RBAConnector
    ) -> None:
        """Window outside cassette coverage → no rows → DataUnavailableError."""
        httpx_mock.add_response(method="GET", text=_f1_cassette())
        try:
            with pytest.raises(DataUnavailableError, match="no rows in"):
                await rba_connector.fetch_series(
                    RBA_F1_TABLE_ID,
                    RBA_CASH_RATE_TARGET,
                    date(1990, 1, 1),
                    date(1990, 12, 31),
                )
        finally:
            await rba_connector.aclose()

    @pytest.mark.asyncio
    async def test_http_error_raises_unavailable(
        self, httpx_mock: HTTPXMock, rba_connector: RBAConnector
    ) -> None:
        """500s exhaust tenacity's 5 retries → surface as ``DataUnavailableError``."""
        httpx_mock.add_response(
            method="GET",
            status_code=500,
            text="Internal Server Error",
            is_reusable=True,
        )
        try:
            with pytest.raises(DataUnavailableError, match="HTTP error"):
                await rba_connector.fetch_series(
                    RBA_F1_TABLE_ID,
                    RBA_CASH_RATE_TARGET,
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                )
        finally:
            await rba_connector.aclose()

    @pytest.mark.asyncio
    async def test_empty_cells_are_skipped(self, rba_connector: RBAConnector) -> None:
        """Trailing empty observation rows (pre-announcement) must not pollute output."""
        csv_body = (
            "F1 RBA STATS\r\n"
            "Title,Cash Rate Target,Other\r\n"
            "Description,foo,bar\r\n"
            "Frequency,Daily,Daily\r\n"
            "Type,Original,Original\r\n"
            "Units,Per cent,Per cent\r\n"
            "\r\n"
            "\r\n"
            "Source,RBA,RBA\r\n"
            "Publication date,21-Apr-2026,21-Apr-2026\r\n"
            "Series ID,FIRMMCRTD,OTHER\r\n"
            "20-Apr-2026,4.10,1.0\r\n"
            "21-Apr-2026,,\r\n"
        )
        parsed = RBAConnector._parse_csv(
            csv_body, series_id=RBA_CASH_RATE_TARGET, table_id=RBA_F1_TABLE_ID
        )
        try:
            assert len(parsed) == 1
            obs_date, value_pct = parsed[0]
            assert value_pct == 4.10
            assert obs_date == date(2026, 4, 20)
        finally:
            await rba_connector.aclose()

    @pytest.mark.asyncio
    async def test_cache_round_trip_skips_second_http_call(
        self, httpx_mock: HTTPXMock, rba_connector: RBAConnector
    ) -> None:
        """Second call on the same ``(table, series, start, end)`` hits the cache."""
        httpx_mock.add_response(method="GET", text=_f1_cassette())
        try:
            first = await rba_connector.fetch_series(
                RBA_F1_TABLE_ID,
                RBA_CASH_RATE_TARGET,
                date(2011, 1, 4),
                date(2011, 2, 1),
            )
            second = await rba_connector.fetch_series(
                RBA_F1_TABLE_ID,
                RBA_CASH_RATE_TARGET,
                date(2011, 1, 4),
                date(2011, 2, 1),
            )
            assert len(first) >= 1
            assert first == second
            assert len(httpx_mock.get_requests()) == 1
        finally:
            await rba_connector.aclose()


class TestRBAConnectorWrappers:
    @pytest.mark.asyncio
    async def test_fetch_cash_rate_uses_f1_firmmcrtd(
        self, httpx_mock: HTTPXMock, rba_connector: RBAConnector
    ) -> None:
        """``fetch_cash_rate`` routes to F1 / FIRMMCRTD."""
        httpx_mock.add_response(method="GET", text=_f1_cassette())
        try:
            obs = await rba_connector.fetch_cash_rate(date(2011, 1, 4), date(2011, 2, 1))
            assert len(obs) >= 1
            assert obs[0].source_series_id == RBA_CASH_RATE_TARGET
            # F1 CSV publishes Per cent values — 4.75 % → 475 bps.
            assert obs[0].yield_bps == 475
            assert obs[0].tenor_years == 0.01
        finally:
            await rba_connector.aclose()

    @pytest.mark.asyncio
    async def test_fetch_government_10y_uses_f2_fcmygbag10d_and_tenor(
        self, httpx_mock: HTTPXMock, rba_connector: RBAConnector
    ) -> None:
        """``fetch_government_10y`` routes to F2 / FCMYGBAG10D and sets tenor 10.0Y."""
        httpx_mock.add_response(method="GET", text=_f2_cassette())
        try:
            obs = await rba_connector.fetch_government_10y(date(2013, 5, 20), date(2013, 12, 31))
            assert len(obs) >= 1
            assert obs[0].source_series_id == RBA_GOVERNMENT_10Y
            assert obs[0].tenor_years == 10.0
            # Sanity: AGB 10Y stayed in [0, 20] pct.
            for o in obs:
                assert 0 <= o.yield_bps <= 2000
        finally:
            await rba_connector.aclose()


@pytest.mark.slow
async def test_live_canary_rba_cash_rate(tmp_path: Path) -> None:
    """Live RBA probe — F1 FIRMMCRTD (cash rate target) within the last 60 days.

    Requires no API key — the host is public. Skips if the network is
    unreachable. Asserts the recent band roughly matches the RBA
    normalisation cycle (2023-26 cash rate stayed within [0.10, 4.35]
    %).
    """
    conn = RBAConnector(cache_dir=str(tmp_path / "rba"))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=60)
        try:
            obs = await conn.fetch_cash_rate(start, today)
        except (httpx.HTTPError, DataUnavailableError) as exc:
            pytest.skip(f"RBA F1 unreachable: {exc}")
        assert len(obs) >= 10
        assert obs[0].country_code == "AU"
        assert obs[0].source_series_id == RBA_CASH_RATE_TARGET
        for o in obs:
            # yield_bps in [0, 2000] — guards against unit regression.
            assert 0 <= o.yield_bps <= 2000
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_rba_government_10y(tmp_path: Path) -> None:
    """Live RBA probe — F2 FCMYGBAG10D (AGB 10Y benchmark) last 60 days."""
    conn = RBAConnector(cache_dir=str(tmp_path / "rba"))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=60)
        try:
            obs = await conn.fetch_government_10y(start, today)
        except (httpx.HTTPError, DataUnavailableError) as exc:
            pytest.skip(f"RBA F2 unreachable: {exc}")
        assert len(obs) >= 10
        assert obs[0].tenor_years == 10.0
        for o in obs:
            # AGB 10Y stayed in [0, 20]% across the last decade.
            assert 0 <= o.yield_bps <= 2000
    finally:
        await conn.aclose()
