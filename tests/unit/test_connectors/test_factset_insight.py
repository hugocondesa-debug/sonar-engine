"""Unit tests for FactSetInsightConnector — synthetic text fixtures."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import httpx
import pytest

from sonar.connectors.factset_insight import (
    FACTSET_URL_TEMPLATE,
    DataUnavailableError,
    FactSetInsightConnector,
    FactSetInsightSnapshot,
    _format_mmddyy,
    _most_recent_friday,
    _parse_pdf_text,
)

if TYPE_CHECKING:
    from pathlib import Path


_HAPPY_TEXT = """\
FactSet Earnings Insight — Weekly Brief
Publication Date: January 05, 2024

S&P 500 Forward 12-Month EPS: $243.73
Forward 12-Month P/E: 19.55
CY1 EPS: $221.41
CY2 EPS: $246.02
5-Year EPS Growth: 12.40%
"""


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Path:
    d = tmp_path / "factset_cache"
    d.mkdir()
    return d


class TestMostRecentFriday:
    def test_friday_returns_self(self) -> None:
        assert _most_recent_friday(date(2024, 1, 5)) == date(2024, 1, 5)

    def test_saturday_returns_friday(self) -> None:
        assert _most_recent_friday(date(2024, 1, 6)) == date(2024, 1, 5)

    def test_sunday_returns_friday(self) -> None:
        assert _most_recent_friday(date(2024, 1, 7)) == date(2024, 1, 5)

    def test_thursday_returns_prior_friday(self) -> None:
        assert _most_recent_friday(date(2024, 1, 4)) == date(2023, 12, 29)


class TestFormatMMDDYY:
    def test_zero_padding(self) -> None:
        assert _format_mmddyy(date(2024, 1, 5)) == "010524"

    def test_late_year(self) -> None:
        assert _format_mmddyy(date(2024, 12, 27)) == "122724"


class TestParsePdfText:
    def test_happy_path(self) -> None:
        snap = _parse_pdf_text(_HAPPY_TEXT, date(2024, 1, 5))
        assert snap.forward_12m_eps == pytest.approx(243.73)
        assert snap.forward_pe == pytest.approx(19.55)
        assert snap.cy1_eps == pytest.approx(221.41)
        assert snap.cy2_eps == pytest.approx(246.02)
        # 5Y growth stored as decimal, not percent.
        assert snap.consensus_growth_5y == pytest.approx(0.124)
        assert snap.publication_date == date(2024, 1, 5)

    def test_missing_forward_eps_raises(self) -> None:
        bad = _HAPPY_TEXT.replace("Forward 12-Month EPS: $243.73", "")
        with pytest.raises(DataUnavailableError, match="Forward 12-Month EPS"):
            _parse_pdf_text(bad, date(2024, 1, 5))

    def test_non_numeric_growth_raises(self) -> None:
        bad = _HAPPY_TEXT.replace("5-Year EPS Growth: 12.40%", "5-Year EPS Growth: N/A%")
        with pytest.raises(DataUnavailableError, match="5-Year EPS Growth"):
            _parse_pdf_text(bad, date(2024, 1, 5))


class TestConnectorFetchFlow:
    async def test_http_error_surfaces_as_data_unavailable(
        self, tmp_cache: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        conn = FactSetInsightConnector(cache_dir=str(tmp_cache))
        mock = AsyncMock(side_effect=httpx.HTTPError("404 not found"))
        monkeypatch.setattr(conn, "_download", mock)
        try:
            with pytest.raises(DataUnavailableError, match="FactSet PDF fetch failed"):
                await conn.fetch_latest_snapshot(date(2024, 1, 5))
        finally:
            await conn.aclose()

    async def test_cache_hit_skips_http(self, tmp_cache: Path) -> None:
        conn = FactSetInsightConnector(cache_dir=str(tmp_cache))
        pre = FactSetInsightSnapshot(
            publication_date=date(2024, 1, 5),
            forward_12m_eps=243.73,
            forward_pe=19.55,
            cy1_eps=221.41,
            cy2_eps=246.02,
            consensus_growth_5y=0.124,
        )
        conn.cache.set(f"{conn.CACHE_NAMESPACE_PARSED}:2024-01-05", pre)
        try:
            result = await conn.fetch_latest_snapshot(date(2024, 1, 5))
            assert result == pre
        finally:
            await conn.aclose()

    async def test_happy_path_with_mocked_parse(
        self, tmp_cache: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        conn = FactSetInsightConnector(cache_dir=str(tmp_cache))
        monkeypatch.setattr(conn, "_download", AsyncMock(return_value=b"fake pdf bytes"))
        # Patch _parse_pdf_bytes at the module level — we don't exercise
        # pdfplumber in this unit test.
        from sonar.connectors import factset_insight  # noqa: PLC0415 — test-local

        monkeypatch.setattr(
            factset_insight,
            "_parse_pdf_bytes",
            lambda body, d: _parse_pdf_text(_HAPPY_TEXT, d),
        )
        try:
            snap = await conn.fetch_latest_snapshot(date(2024, 1, 5))
            assert snap.publication_date == date(2024, 1, 5)
            assert snap.consensus_growth_5y == pytest.approx(0.124)
        finally:
            await conn.aclose()


class TestUrlTemplate:
    def test_template_formats_cleanly(self) -> None:
        url = FACTSET_URL_TEMPLATE.format(mmddyy="010524")
        assert url.endswith("EarningsInsight_010524.pdf")
        assert url.startswith("https://advantage.factset.com/")
