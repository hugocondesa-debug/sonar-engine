"""Unit tests for :mod:`sonar.connectors.boj_tankan` — Sprint Q.3.

Exercises:

* URL template + 5-year bucket candidate derivation.
* Happy-path ZIP → XLSX → TABLE7 parsing (synthetic workbook built
  in-test via openpyxl so no fixture asset needs to ship).
* Missing-sheet / missing-XLSX / no-match paths surface as
  :class:`DataUnavailableError` via :meth:`fetch_release`.
* Cache round-trip short-circuits the HTTP call.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date
from typing import TYPE_CHECKING

import pytest
from openpyxl import Workbook
from tenacity import wait_none

from sonar.connectors.boj_tankan import (
    BOJ_TANKAN_GAIYO_URL_TEMPLATE,
    BoJTankanConnector,
    TankanInflationOutlook,
    _bucket_candidates,
    _parse_tankan_xlsx_blob,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock


# ---------------------------------------------------------------------------
# Synthetic Tankan TABLE7 fixture — smallest viable layout mirroring the
# empirical probe (see docs/backlog/probe-results/sprint-q-3-jp-ca-survey-probe.md §1.2).
# ---------------------------------------------------------------------------


def _build_tankan_xlsx_blob(
    *,
    pct_1y: float = 2.6,
    pct_3y: float = 2.5,
    pct_5y: float = 2.5,
    include_all_enterprises: bool = True,
) -> bytes:
    """Return a ZIP blob containing a minimal GA_E1.xlsx with TABLE7.

    TABLE7 carries only the three rows the parser needs — "All
    Enterprises / All industries / {1Y, 3Y, 5Y} / Current projection".
    The surrounding header rows are omitted to keep the fixture terse
    while still hitting the "inside_all_enterprises" state transition.
    """
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "TABLE7"
    if include_all_enterprises:
        # Row layout: col A (row_label), B (industry), C (horizon),
        # D (projection), E (output prices %), F (change), G (general
        # prices %), H (change). Parser indexes 0-based.
        ws.append(
            [
                "All Enterprises",
                "All industries",
                "1 year ahead",
                "Current projection",
                pct_1y + 1.0,
                0.1,
                pct_1y,
                0.1,
            ]
        )
        ws.append(
            [None, None, "3 years ahead", "Current projection", pct_3y + 1.0, 0.1, pct_3y, 0.1]
        )
        ws.append(
            [None, None, "5 years ahead", "Current projection", pct_5y + 1.0, 0.1, pct_5y, 0.1]
        )
    else:
        ws.append(
            [
                "Large Enterprises",
                "Manu-facturing",
                "1 year ahead",
                "Current projection",
                1.0,
                0.0,
                1.0,
                0.0,
            ]
        )
    xlsx_buffer = io.BytesIO()
    wb.save(xlsx_buffer)
    wb.close()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("GA_E1.xlsx", xlsx_buffer.getvalue())
    return zip_buffer.getvalue()


def _build_zip_without_xlsx() -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("NOT_THE_FILE.txt", "garbage")
    return zip_buffer.getvalue()


# ---------------------------------------------------------------------------
# URL + bucket
# ---------------------------------------------------------------------------


def test_url_template_shape() -> None:
    assert "{bucket}" in BOJ_TANKAN_GAIYO_URL_TEMPLATE
    assert "{yy}" in BOJ_TANKAN_GAIYO_URL_TEMPLATE
    assert "{mm}" in BOJ_TANKAN_GAIYO_URL_TEMPLATE
    assert BOJ_TANKAN_GAIYO_URL_TEMPLATE.startswith("https://www.boj.or.jp/")


def test_bucket_candidates_pre_zip_window_returns_empty() -> None:
    """Pre-2021 releases are PDF-only — connector short-circuits."""
    assert _bucket_candidates(2020) == []
    assert _bucket_candidates(2019) == []


def test_bucket_candidates_current_bucket_year() -> None:
    """2021 is its own 5-year bucket start — single candidate."""
    assert _bucket_candidates(2021) == [2021]


def test_bucket_candidates_non_bucket_year_falls_back_to_floor() -> None:
    """2022-2025 probe the release year first, then 2021 bucket floor."""
    assert _bucket_candidates(2022) == [2022, 2021]
    assert _bucket_candidates(2023) == [2023, 2021]
    assert _bucket_candidates(2025) == [2025, 2021]


def test_bucket_candidates_next_bucket_edge() -> None:
    """2026 starts a fresh 5-year bucket — single candidate."""
    assert _bucket_candidates(2026) == [2026]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_parse_tankan_xlsx_happy_path() -> None:
    blob = _build_tankan_xlsx_blob(pct_1y=2.6, pct_3y=2.5, pct_5y=2.5)
    horizons = _parse_tankan_xlsx_blob(blob)
    assert horizons == {"1Y": 2.6, "3Y": 2.5, "5Y": 2.5}


def test_parse_tankan_xlsx_missing_xlsx_raises() -> None:
    blob = _build_zip_without_xlsx()
    with pytest.raises(KeyError, match=r"GA_E1\.xlsx"):
        _parse_tankan_xlsx_blob(blob)


def test_parse_tankan_xlsx_no_all_enterprises_returns_empty() -> None:
    blob = _build_tankan_xlsx_blob(include_all_enterprises=False)
    horizons = _parse_tankan_xlsx_blob(blob)
    assert horizons == {}


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------


class TestBoJTankanConnectorLifecycle:
    @pytest.mark.asyncio
    async def test_instantiation_and_aclose(self, tmp_path: Path) -> None:
        conn = BoJTankanConnector(cache_dir=str(tmp_path / "boj_tankan"))
        assert conn.CONNECTOR_ID == "boj_tankan"
        assert conn.CACHE_NAMESPACE == "boj_tankan"
        await conn.aclose()


class TestBoJTankanFetchRelease:
    @pytest.mark.asyncio
    async def test_happy_path_returns_outlook(self, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
        blob = _build_tankan_xlsx_blob(pct_1y=2.6, pct_3y=2.5, pct_5y=2.5)
        httpx_mock.add_response(method="GET", content=blob)
        conn = BoJTankanConnector(cache_dir=str(tmp_path / "c"))
        try:
            outlook = await conn.fetch_release(2026, 3)
            assert isinstance(outlook, TankanInflationOutlook)
            assert outlook.reference_date == date(2026, 3, 1)
            assert outlook.release_year == 2026
            assert outlook.release_quarter_end_month == 3
            assert outlook.horizons_pct == {"1Y": 2.6, "3Y": 2.5, "5Y": 2.5}
        finally:
            await conn.aclose()

    @pytest.mark.asyncio
    async def test_falls_back_to_five_year_bucket_on_404(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        """2022 release: first candidate /gaiyo/2022/ 404s, fallback /gaiyo/2021/ wins."""
        blob = _build_tankan_xlsx_blob()
        httpx_mock.add_response(
            method="GET",
            url="https://www.boj.or.jp/en/statistics/tk/gaiyo/2022/tka2203.zip",
            status_code=404,
        )
        httpx_mock.add_response(
            method="GET",
            url="https://www.boj.or.jp/en/statistics/tk/gaiyo/2021/tka2203.zip",
            content=blob,
        )
        conn = BoJTankanConnector(cache_dir=str(tmp_path / "c"))
        try:
            outlook = await conn.fetch_release(2022, 3)
            assert outlook.release_year == 2022
            assert outlook.horizons_pct == {"1Y": 2.6, "3Y": 2.5, "5Y": 2.5}
        finally:
            await conn.aclose()

    @pytest.mark.asyncio
    async def test_all_candidates_404_raises_data_unavailable(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        httpx_mock.add_response(method="GET", status_code=404, is_reusable=True)
        conn = BoJTankanConnector(cache_dir=str(tmp_path / "c"))
        try:
            with pytest.raises(DataUnavailableError, match="fetch failed"):
                await conn.fetch_release(2024, 6)
        finally:
            await conn.aclose()

    @pytest.mark.asyncio
    async def test_parse_failure_raises_data_unavailable(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        bad_blob = _build_zip_without_xlsx()
        httpx_mock.add_response(method="GET", content=bad_blob)
        conn = BoJTankanConnector(cache_dir=str(tmp_path / "c"))
        try:
            with pytest.raises(DataUnavailableError, match="parse failed"):
                await conn.fetch_release(2026, 3)
        finally:
            await conn.aclose()

    @pytest.mark.asyncio
    async def test_rejects_non_quarter_end_month(self, tmp_path: Path) -> None:
        conn = BoJTankanConnector(cache_dir=str(tmp_path / "c"))
        try:
            with pytest.raises(ValueError, match="release month"):
                await conn.fetch_release(2026, 4)
        finally:
            await conn.aclose()

    @pytest.mark.asyncio
    async def test_cache_round_trip_skips_http(self, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
        blob = _build_tankan_xlsx_blob()
        httpx_mock.add_response(method="GET", content=blob)
        conn = BoJTankanConnector(cache_dir=str(tmp_path / "c"))
        try:
            first = await conn.fetch_release(2026, 3)
            second = await conn.fetch_release(2026, 3)
            assert first.horizons_pct == second.horizons_pct
            assert len(httpx_mock.get_requests()) == 1
        finally:
            await conn.aclose()

    @pytest.mark.asyncio
    async def test_transient_500_retries_then_raises(
        self, httpx_mock: HTTPXMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Transient 5xx exhaust tenacity retries then surface as
        :class:`DataUnavailableError` via ``RetryError``.
        """
        monkeypatch.setattr(BoJTankanConnector._fetch_bucket.retry, "wait", wait_none())
        httpx_mock.add_response(method="GET", status_code=500, is_reusable=True)
        conn = BoJTankanConnector(cache_dir=str(tmp_path / "c"))
        try:
            with pytest.raises(DataUnavailableError, match="fetch failed"):
                await conn.fetch_release(2026, 3)
        finally:
            await conn.aclose()
