"""Unit tests for YardeniConnector — synthetic text fixtures + URL env wiring."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import httpx
import pytest

from sonar.connectors.yardeni import (
    YARDENI_PDF_URL_ENVVAR,
    DataUnavailableError,
    YardeniConnector,
    YardeniEarningsSquigglesSnapshot,
    _extract_publication_date,
    _parse_pdf_text,
)

if TYPE_CHECKING:
    from pathlib import Path


_HAPPY_TEXT = """\
Yardeni Research — Earnings Squiggles
Published: January 05, 2024

Current Year EPS Estimate: $221.41
Next Year EPS Estimate: $246.02
Time-Weighted Forward EPS: $238.70
"""


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Path:
    d = tmp_path / "yardeni_cache"
    d.mkdir()
    return d


class TestExtractPublicationDate:
    def test_long_month_name(self) -> None:
        assert _extract_publication_date("Published: January 05, 2024") == date(2024, 1, 5)

    def test_short_month_name(self) -> None:
        assert _extract_publication_date("Publication Date: Jan 5 2024") == date(2024, 1, 5)

    def test_missing_returns_none(self) -> None:
        assert _extract_publication_date("no date here") is None


class TestParsePdfText:
    def test_happy_path(self) -> None:
        snap = _parse_pdf_text(_HAPPY_TEXT, fallback_publication_date=None)
        assert snap.current_year_eps == pytest.approx(221.41)
        assert snap.next_year_eps == pytest.approx(246.02)
        assert snap.time_weighted_forward_eps == pytest.approx(238.70)
        assert snap.publication_date == date(2024, 1, 5)

    def test_fallback_date_used_when_pdf_lacks_header(self) -> None:
        no_date_text = _HAPPY_TEXT.replace("Published: January 05, 2024", "")
        snap = _parse_pdf_text(no_date_text, fallback_publication_date=date(2024, 1, 5))
        assert snap.publication_date == date(2024, 1, 5)

    def test_no_date_and_no_fallback_raises(self) -> None:
        no_date_text = _HAPPY_TEXT.replace("Published: January 05, 2024", "")
        with pytest.raises(DataUnavailableError, match="no publication date"):
            _parse_pdf_text(no_date_text, fallback_publication_date=None)

    def test_missing_current_year_raises(self) -> None:
        bad = _HAPPY_TEXT.replace("Current Year EPS Estimate: $221.41", "")
        with pytest.raises(DataUnavailableError, match="current-year EPS"):
            _parse_pdf_text(bad, fallback_publication_date=None)


class TestConnectorConfiguration:
    async def test_missing_url_raises_data_unavailable(self, tmp_cache: Path) -> None:
        conn = YardeniConnector(cache_dir=str(tmp_cache), pdf_url=None)
        # Ensure env is also unset to force graceful-stub behaviour.
        try:
            with pytest.raises(DataUnavailableError, match="no PDF URL configured"):
                await conn.fetch_latest_snapshot()
        finally:
            await conn.aclose()

    async def test_env_var_fallback(self, tmp_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(YARDENI_PDF_URL_ENVVAR, "https://example.invalid/squiggles.pdf")
        conn = YardeniConnector(cache_dir=str(tmp_cache))
        # Override _download so we don't hit the network; parse fails because
        # fake bytes aren't a PDF, surfacing as DataUnavailableError.
        monkeypatch.setattr(conn, "_download", AsyncMock(return_value=b"not a real pdf"))
        try:
            with pytest.raises(DataUnavailableError, match="PDF parse failed"):
                await conn.fetch_latest_snapshot()
        finally:
            await conn.aclose()


class TestConnectorFetchFlow:
    async def test_http_error_surfaces_as_data_unavailable(
        self, tmp_cache: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        conn = YardeniConnector(
            cache_dir=str(tmp_cache), pdf_url="https://example.invalid/squiggles.pdf"
        )
        monkeypatch.setattr(
            conn, "_download", AsyncMock(side_effect=httpx.HTTPError("503 unavailable"))
        )
        try:
            with pytest.raises(DataUnavailableError, match="Yardeni PDF fetch failed"):
                await conn.fetch_latest_snapshot()
        finally:
            await conn.aclose()

    async def test_cache_hit_skips_http(self, tmp_cache: Path) -> None:
        url = "https://example.invalid/squiggles.pdf"
        conn = YardeniConnector(cache_dir=str(tmp_cache), pdf_url=url)
        pre = YardeniEarningsSquigglesSnapshot(
            publication_date=date(2024, 1, 5),
            current_year_eps=221.41,
            next_year_eps=246.02,
            time_weighted_forward_eps=238.70,
        )
        conn.cache.set(f"{conn.CACHE_NAMESPACE_PARSED}:{url}", pre)
        try:
            result = await conn.fetch_latest_snapshot()
            assert result == pre
        finally:
            await conn.aclose()

    async def test_happy_path_with_mocked_parse(
        self, tmp_cache: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        conn = YardeniConnector(
            cache_dir=str(tmp_cache), pdf_url="https://example.invalid/squiggles.pdf"
        )
        monkeypatch.setattr(conn, "_download", AsyncMock(return_value=b"fake pdf bytes"))
        from sonar.connectors import yardeni  # noqa: PLC0415 — test-local

        monkeypatch.setattr(
            yardeni,
            "_parse_pdf_bytes",
            lambda body, fb: _parse_pdf_text(_HAPPY_TEXT, fb),
        )
        try:
            snap = await conn.fetch_latest_snapshot()
            assert snap.publication_date == date(2024, 1, 5)
            assert snap.time_weighted_forward_eps == pytest.approx(238.70)
        finally:
            await conn.aclose()
