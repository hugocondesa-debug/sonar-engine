"""Unit tests for SNB data-portal L0 connector (Sprint V).

The SNB data portal (``https://data.snb.ch/api/cube/{cube_id}/data/
csv/en``) is public and unscreened — no API key, no bot-detection
gate. Tests exercise:

- Cube-ID + series-code catalogue stability (regression guard).
- Happy-path parse from trimmed real zimoma + rendoblim CSV cassettes.
- Multi-series cube filtering — only the requested ``D0`` value flows
  through.
- **Negative-value preservation** — the 2015-2022 CHF negative-rate
  era must survive the parse → Observation round-trip unchanged (the
  whole reason SNB ships its own connector rather than leaning on
  FRED OECD).
- Schema-drift guard — header row mismatch → ``DataUnavailableError``.
- Empty column / series-code-not-in-cube → ``DataUnavailableError``.
- HTTP error → ``DataUnavailableError``.
- Disk cache round-trip (set / get short-circuits the HTTP call).
- Both ``fetch_saron`` + ``fetch_confederation_10y`` convenience
  wrappers land via the canonical cubes with the right tenors.
- @slow live canary probes ``zimoma`` SARON + asserts the recent band.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
from tenacity import wait_none

from sonar.connectors.base import Observation
from sonar.connectors.snb import (
    SNB_CONFED_10Y_TENOR,
    SNB_DATA_PORTAL_BASE_URL,
    SNB_RENDOBLIM_CUBE,
    SNB_SARON_SERIES,
    SNB_USER_AGENT,
    SNB_ZIMOMA_CUBE,
    SNBConnector,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


def _zimoma_cassette() -> str:
    return (CASSETTE_DIR / "snb_zimoma_2024_01_02.csv").read_text()


def _rendoblim_cassette() -> str:
    return (CASSETTE_DIR / "snb_rendoblim_2024_01_02.csv").read_text()


def test_cube_ids_are_canonical() -> None:
    """Regression guard — SNB cube codes must stay stable."""
    assert SNB_ZIMOMA_CUBE == "zimoma"
    assert SNB_RENDOBLIM_CUBE == "rendoblim"


def test_series_codes_are_canonical() -> None:
    assert SNB_SARON_SERIES == "SARON"
    assert SNB_CONFED_10Y_TENOR == "10J"


def test_base_url_canonical() -> None:
    assert SNB_DATA_PORTAL_BASE_URL == "https://data.snb.ch/api/cube"


def test_user_agent_is_descriptive() -> None:
    """SNB portal does not bot-screen, but operator identity still required."""
    assert "SONAR" in SNB_USER_AGENT
    assert "Mozilla" not in SNB_USER_AGENT


class TestSNBConnectorLifecycle:
    @pytest.mark.asyncio
    async def test_instantiation_and_aclose(self, tmp_path: Path) -> None:
        conn = SNBConnector(cache_dir=str(tmp_path / "snb"))
        assert conn.CONNECTOR_ID == "snb"
        assert conn.CACHE_NAMESPACE == "snb_portal"
        await conn.aclose()


@pytest.fixture
async def snb_connector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SNBConnector:
    monkeypatch.setattr(SNBConnector._fetch_raw.retry, "wait", wait_none())
    return SNBConnector(cache_dir=str(tmp_path / "snb"))


class TestSNBConnectorFetchSeries:
    @pytest.mark.asyncio
    async def test_happy_path_parses_zimoma_saron(
        self, httpx_mock: HTTPXMock, snb_connector: SNBConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            text=_zimoma_cassette(),
            headers={"content-type": "text/csv"},
        )
        try:
            obs = await snb_connector.fetch_series(
                SNB_ZIMOMA_CUBE,
                SNB_SARON_SERIES,
                date(2010, 1, 1),
                date(2026, 4, 1),
            )
            assert len(obs) >= 100
            assert all(isinstance(o, Observation) for o in obs)
            assert obs[0].country_code == "CH"
            assert obs[0].source == "SNB"
            assert obs[0].source_series_id == f"{SNB_ZIMOMA_CUBE}:{SNB_SARON_SERIES}"
        finally:
            await snb_connector.aclose()

    @pytest.mark.asyncio
    async def test_preserves_negative_rate_era_values(
        self, httpx_mock: HTTPXMock, snb_connector: SNBConnector
    ) -> None:
        """2015-2022 SARON negative-rate corridor must flow through
        with sign intact — the very reason SNB ships its own connector
        rather than leaning on FRED OECD for the CH fallback.
        """
        httpx_mock.add_response(method="GET", text=_zimoma_cassette())
        try:
            obs = await snb_connector.fetch_series(
                SNB_ZIMOMA_CUBE,
                SNB_SARON_SERIES,
                date(2015, 1, 1),
                date(2022, 12, 31),
            )
            assert len(obs) >= 36  # at least 3Y of monthly observations
            neg = [o for o in obs if o.yield_bps < 0]
            assert len(neg) >= 12, (
                "expected ≥ 12 monthly negative-rate observations across "
                "2015-2022 — negative-rate era preservation is the point "
                "of the native connector"
            )
            # SNB SARON minimum was ≈ -0.76 % → yield_bps ≈ -76.
            min_bps = min(o.yield_bps for o in neg)
            assert -100 <= min_bps <= -50
        finally:
            await snb_connector.aclose()

    @pytest.mark.asyncio
    async def test_multi_series_filtering(
        self, httpx_mock: HTTPXMock, snb_connector: SNBConnector
    ) -> None:
        """``zimoma`` cube multiplexes SARON / 1TGT / EURIBOR / ... —
        only the requested ``D0`` series should flow through.
        """
        httpx_mock.add_response(method="GET", text=_zimoma_cassette())
        try:
            obs = await snb_connector.fetch_series(
                SNB_ZIMOMA_CUBE,
                "EURIBOR",
                date(2020, 1, 1),
                date(2024, 12, 31),
            )
            assert all(o.source_series_id == f"{SNB_ZIMOMA_CUBE}:EURIBOR" for o in obs)
        finally:
            await snb_connector.aclose()

    @pytest.mark.asyncio
    async def test_series_code_missing_raises(
        self, httpx_mock: HTTPXMock, snb_connector: SNBConnector
    ) -> None:
        httpx_mock.add_response(method="GET", text=_zimoma_cassette())
        try:
            with pytest.raises(DataUnavailableError, match="no parseable rows"):
                await snb_connector.fetch_series(
                    SNB_ZIMOMA_CUBE,
                    "FAKE_NONEXISTENT_SERIES",
                    date(2020, 1, 1),
                    date(2024, 12, 31),
                )
        finally:
            await snb_connector.aclose()

    @pytest.mark.asyncio
    async def test_empty_window_raises(
        self, httpx_mock: HTTPXMock, snb_connector: SNBConnector
    ) -> None:
        """Window outside cassette coverage → no rows → DataUnavailableError."""
        httpx_mock.add_response(method="GET", text=_zimoma_cassette())
        try:
            with pytest.raises(DataUnavailableError, match="no rows in"):
                await snb_connector.fetch_series(
                    SNB_ZIMOMA_CUBE,
                    SNB_SARON_SERIES,
                    date(1900, 1, 1),
                    date(1900, 12, 31),
                )
        finally:
            await snb_connector.aclose()

    @pytest.mark.asyncio
    async def test_http_error_raises_unavailable(
        self, httpx_mock: HTTPXMock, snb_connector: SNBConnector
    ) -> None:
        """500s exhaust tenacity's 5 retries → surface as DataUnavailableError."""
        httpx_mock.add_response(
            method="GET",
            status_code=500,
            text="Internal Server Error",
            is_reusable=True,
        )
        try:
            with pytest.raises(DataUnavailableError, match="HTTP error"):
                await snb_connector.fetch_series(
                    SNB_ZIMOMA_CUBE,
                    SNB_SARON_SERIES,
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                )
        finally:
            await snb_connector.aclose()

    def test_header_row_drift_raises(self) -> None:
        """If SNB reshuffles the schema, the parser must refuse to guess."""
        bad_csv = (
            '"CubeId";"zimoma"\n'
            '"PublishingDate";"2026-04-01 14:30"\n'
            "\n"
            '"Date";"Series";"Level"\n'
            '"2024-01";"SARON";"1.5"\n'
        )
        with pytest.raises(DataUnavailableError, match="header mismatch"):
            SNBConnector._parse_csv(bad_csv, cube_id=SNB_ZIMOMA_CUBE, series_code=SNB_SARON_SERIES)

    def test_short_body_raises(self) -> None:
        with pytest.raises(DataUnavailableError, match="CSV too short"):
            SNBConnector._parse_csv(
                '"CubeId";"zimoma"\n',
                cube_id=SNB_ZIMOMA_CUBE,
                series_code=SNB_SARON_SERIES,
            )

    def test_empty_and_malformed_value_cells_are_skipped(self) -> None:
        """Empty ``Value`` cells (not-yet-populated) and non-numeric cells
        (defensive — should not occur in real SNB CSVs) are both silently
        skipped."""
        csv_body = (
            '"CubeId";"zimoma"\n'
            '"PublishingDate";"2026-04-01 14:30"\n'
            "\n"
            '"Date";"D0";"Value"\n'
            '"2024-01";"SARON";"1.5"\n'
            '"2024-02";"SARON";""\n'
            '"2024-03";"SARON";"not a number"\n'
            '"2024-04";"SARON";"1.75"\n'
        )
        parsed = SNBConnector._parse_csv(
            csv_body, cube_id=SNB_ZIMOMA_CUBE, series_code=SNB_SARON_SERIES
        )
        assert len(parsed) == 2
        assert parsed[0] == (date(2024, 1, 1), 1.5)
        assert parsed[1] == (date(2024, 4, 1), 1.75)

    @pytest.mark.asyncio
    async def test_cache_round_trip_skips_second_http_call(
        self, httpx_mock: HTTPXMock, snb_connector: SNBConnector
    ) -> None:
        httpx_mock.add_response(method="GET", text=_zimoma_cassette())
        try:
            first = await snb_connector.fetch_series(
                SNB_ZIMOMA_CUBE,
                SNB_SARON_SERIES,
                date(2020, 1, 1),
                date(2020, 6, 1),
            )
            second = await snb_connector.fetch_series(
                SNB_ZIMOMA_CUBE,
                SNB_SARON_SERIES,
                date(2020, 1, 1),
                date(2020, 6, 1),
            )
            assert len(first) >= 1
            assert first == second
            assert len(httpx_mock.get_requests()) == 1
        finally:
            await snb_connector.aclose()


class TestSNBConnectorWrappers:
    @pytest.mark.asyncio
    async def test_fetch_saron_uses_zimoma_cube(
        self, httpx_mock: HTTPXMock, snb_connector: SNBConnector
    ) -> None:
        httpx_mock.add_response(method="GET", text=_zimoma_cassette())
        try:
            obs = await snb_connector.fetch_saron(date(2024, 1, 1), date(2024, 12, 31))
            assert len(obs) >= 1
            assert obs[0].source_series_id == f"{SNB_ZIMOMA_CUBE}:{SNB_SARON_SERIES}"
            assert obs[0].tenor_years == 0.01
        finally:
            await snb_connector.aclose()

    @pytest.mark.asyncio
    async def test_fetch_confederation_10y_uses_rendoblim_and_tenor(
        self, httpx_mock: HTTPXMock, snb_connector: SNBConnector
    ) -> None:
        httpx_mock.add_response(method="GET", text=_rendoblim_cassette())
        try:
            obs = await snb_connector.fetch_confederation_10y(date(2020, 1, 1), date(2024, 12, 31))
            assert len(obs) >= 1
            assert obs[0].source_series_id == f"{SNB_RENDOBLIM_CUBE}:{SNB_CONFED_10Y_TENOR}"
            assert obs[0].tenor_years == 10.0
            # Swiss Confederation 10Y stayed in [-1, 5] pct post-2000.
            for o in obs:
                assert -100 <= o.yield_bps <= 500
        finally:
            await snb_connector.aclose()


@pytest.mark.slow
async def test_live_canary_snb_saron(tmp_path: Path) -> None:
    """Live SNB probe — ``zimoma`` SARON within the last 36 months.

    Requires no API key — the portal is public. Skips if the network
    is unreachable. Asserts the recent band roughly matches the SNB
    normalisation cycle (2023-26 policy rate stayed within
    [-0.25, 1.75] %).
    """
    conn = SNBConnector(cache_dir=str(tmp_path / "snb"))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=365 * 3)
        try:
            obs = await conn.fetch_saron(start, today)
        except (httpx.HTTPError, httpx.ConnectError):
            pytest.skip("SNB data portal unreachable")
        assert len(obs) >= 6
        assert obs[0].country_code == "CH"
        assert obs[0].source == "SNB"
        # SNB policy rate corridor 2023-26: [-0.25, 1.75]% → [-25, 175] bps.
        for o in obs:
            assert -100 <= o.yield_bps <= 250
    finally:
        await conn.aclose()
