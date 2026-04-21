"""Unit tests for BoE IADB L0 connector.

No live HTTP — all tests exercise the CSV parser with synthetic bodies
or monkey-patch ``_fetch_raw``. The live canary (gated on network
reachability) lives in the integration suite only if and when BoE
relaxes their Akamai anti-bot gate.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from sonar.connectors.boe_database import (
    BOE_BALANCE_SHEET_M4,
    BOE_BANK_RATE,
    BOE_GILT_10Y,
    BOE_SONIA_RATE,
    BoEDatabaseConnector,
    _parse_csv,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Series-ID catalogue
# ---------------------------------------------------------------------------


def test_series_ids_are_canonical() -> None:
    assert BOE_BANK_RATE == "IUDBEDR"
    assert BOE_SONIA_RATE == "IUDSOIA"
    assert BOE_GILT_10Y == "IUDMNPY"
    assert BOE_BALANCE_SHEET_M4 == "LPMVWYR"


# ---------------------------------------------------------------------------
# _parse_csv — CSV parser unit tests
# ---------------------------------------------------------------------------


def test_parse_csv_happy_path_bank_rate() -> None:
    body = "DATE,IUDBEDR\n01 Dec 2024,4.75\n05 Dec 2024,4.75\n18 Dec 2024,4.75\n"
    obs = _parse_csv(
        body,
        "IUDBEDR",
        tenor_years=0.01,
        start=date(2024, 12, 1),
        end=date(2024, 12, 31),
    )
    assert len(obs) == 3
    assert obs[0].country_code == "GB"
    assert obs[0].source == "BOE"
    assert obs[0].source_series_id == "IUDBEDR"
    assert obs[0].yield_bps == 475  # 4.75 pct * 100


def test_parse_csv_skips_placeholder_rows() -> None:
    body = (
        "DATE,IUDBEDR\n"
        "01 Dec 2024,4.75\n"
        "02 Dec 2024,.\n"  # IADB uses . for no-value
        "03 Dec 2024,-\n"
        "04 Dec 2024,\n"
        "05 Dec 2024,4.75\n"
    )
    obs = _parse_csv(
        body,
        "IUDBEDR",
        tenor_years=0.01,
        start=date(2024, 12, 1),
        end=date(2024, 12, 31),
    )
    assert len(obs) == 2
    assert [o.observation_date for o in obs] == [date(2024, 12, 1), date(2024, 12, 5)]


def test_parse_csv_filters_by_date_window() -> None:
    body = (
        "DATE,IUDBEDR\n"
        "28 Nov 2024,5.00\n"  # outside window
        "02 Dec 2024,4.75\n"
        "05 Jan 2025,4.75\n"  # outside window
    )
    obs = _parse_csv(
        body,
        "IUDBEDR",
        tenor_years=0.01,
        start=date(2024, 12, 1),
        end=date(2024, 12, 31),
    )
    assert len(obs) == 1
    assert obs[0].observation_date == date(2024, 12, 2)


def test_parse_csv_empty_body_raises() -> None:
    with pytest.raises(DataUnavailableError, match="empty CSV"):
        _parse_csv(
            "",
            "IUDBEDR",
            tenor_years=0.01,
            start=date(2024, 12, 1),
            end=date(2024, 12, 31),
        )


def test_parse_csv_schema_drift_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    # Header column 2 contains a different series code — the parser
    # warns and keeps parsing rather than raising.
    body = "DATE,SURPRISE_COLUMN\n02 Dec 2024,4.75\n"
    obs = _parse_csv(
        body,
        "IUDBEDR",
        tenor_years=0.01,
        start=date(2024, 12, 1),
        end=date(2024, 12, 31),
    )
    assert len(obs) == 1


def test_parse_csv_yield_series_tenor_preserved() -> None:
    body = "DATE,IUDMNPY\n02 Dec 2024,4.43\n"
    obs = _parse_csv(
        body,
        "IUDMNPY",
        tenor_years=10.0,
        start=date(2024, 12, 1),
        end=date(2024, 12, 31),
    )
    assert len(obs) == 1
    assert obs[0].tenor_years == 10.0
    assert obs[0].yield_bps == 443


# ---------------------------------------------------------------------------
# BoEDatabaseConnector — monkey-patched fetch path
# ---------------------------------------------------------------------------


class TestConnector:
    @pytest.mark.asyncio
    async def test_fetch_bank_rate_success(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        body = "DATE,IUDBEDR\n02 Dec 2024,4.75\n"
        conn = BoEDatabaseConnector(cache_dir=str(tmp_path / "boe"))

        async def _fake_fetch(series_id: str, start: date, end: date) -> str:
            _ = series_id, start, end
            return body

        monkeypatch.setattr(conn, "_fetch_raw", _fake_fetch)
        obs = await conn.fetch_bank_rate(date(2024, 12, 1), date(2024, 12, 31))
        assert len(obs) == 1
        assert obs[0].yield_bps == 475
        await conn.aclose()

    @pytest.mark.asyncio
    async def test_fetch_gilt_10y_returns_tenor_10(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        body = "DATE,IUDMNPY\n02 Dec 2024,4.43\n"
        conn = BoEDatabaseConnector(cache_dir=str(tmp_path / "boe"))

        async def _fake_fetch(series_id: str, start: date, end: date) -> str:
            _ = series_id, start, end
            return body

        monkeypatch.setattr(conn, "_fetch_raw", _fake_fetch)
        obs = await conn.fetch_gilt_10y(date(2024, 12, 1), date(2024, 12, 31))
        assert len(obs) == 1
        assert obs[0].tenor_years == 10.0
        await conn.aclose()

    @pytest.mark.asyncio
    async def test_error_page_raises_data_unavailable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Simulate the Akamai anti-bot redirect → HTML body."""
        conn = BoEDatabaseConnector(cache_dir=str(tmp_path / "boe"))

        async def _html_body(series_id: str, start: date, end: date) -> str:
            _ = series_id, start, end
            # In production _fetch_raw itself detects the ErrorPage and
            # raises DataUnavailableError before returning. Simulate.
            msg = f"BoE IADB ErrorPage for series={series_id!r}"
            raise DataUnavailableError(msg)

        monkeypatch.setattr(conn, "_fetch_raw", _html_body)
        with pytest.raises(DataUnavailableError, match="ErrorPage"):
            await conn.fetch_bank_rate(date(2024, 12, 1), date(2024, 12, 31))
        await conn.aclose()

    @pytest.mark.asyncio
    async def test_cache_avoids_second_fetch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        body = "DATE,IUDBEDR\n02 Dec 2024,4.75\n"
        conn = BoEDatabaseConnector(cache_dir=str(tmp_path / "boe"))
        call_count = 0

        async def _fake_fetch(series_id: str, start: date, end: date) -> str:
            nonlocal call_count
            _ = series_id, start, end
            call_count += 1
            return body

        monkeypatch.setattr(conn, "_fetch_raw", _fake_fetch)
        await conn.fetch_bank_rate(date(2024, 12, 1), date(2024, 12, 31))
        await conn.fetch_bank_rate(date(2024, 12, 1), date(2024, 12, 31))
        assert call_count == 1  # second call served from disk cache
        await conn.aclose()
