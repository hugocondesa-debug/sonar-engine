"""Unit tests for BoJ TSD L0 connector (Sprint L).

The BoJ TSD portal is browser-gated at Sprint L scope (empirical probe
2026-04-21 — see module docstring). The connector ships as a wire-ready
scaffold that raises :class:`DataUnavailableError` on every
:meth:`fetch_series` call so the JP monetary cascade falls through to
TE primary. Tests exercise:

- Series-ID catalogue stability (regression guard vs rename typos).
- Gated fetch raises `DataUnavailableError` with the canonical
  `portal gated` reason.
- Disk cache seeds bypass the raise (future-unblock transition path).
- Instantiation + aclose lifecycle.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from sonar.connectors.base import Observation
from sonar.connectors.boj import (
    BOJ_BALANCE_SHEET,
    BOJ_BANK_RATE,
    BOJ_JGB_10Y,
    BOJ_PORTAL_GATED_REASON,
    BOJ_TSD_URL,
    BoJConnector,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path


def test_series_ids_are_canonical() -> None:
    """Regression guard — BoJ FAME codes must stay stable."""
    assert BOJ_BANK_RATE == "FM01'STRAMUCOLR"
    assert BOJ_JGB_10Y == "FM02'OUCYOTKMM10Y"
    assert BOJ_BALANCE_SHEET == "BS01'MABJMTA"


def test_portal_url_canonical() -> None:
    assert BOJ_TSD_URL.endswith("/ssi/cgi-bin/famecgi2")
    assert "stat-search.boj.or.jp" in BOJ_TSD_URL


def test_portal_gated_reason_pins_phrasing() -> None:
    """Retrospective artefact pins this exact phrasing — guard it."""
    assert "browser-gated" in BOJ_PORTAL_GATED_REASON
    assert "TE primary" in BOJ_PORTAL_GATED_REASON


class TestBoJConnectorLifecycle:
    @pytest.mark.asyncio
    async def test_instantiation_and_aclose(self, tmp_path: Path) -> None:
        conn = BoJConnector(cache_dir=str(tmp_path / "boj"))
        assert conn.CONNECTOR_ID == "boj"
        assert conn.CACHE_NAMESPACE == "boj_tsd"
        await conn.aclose()


class TestBoJConnectorGatedPath:
    @pytest.mark.asyncio
    async def test_fetch_series_raises_portal_gated(self, tmp_path: Path) -> None:
        """Default path while portal is browser-gated — raise cleanly."""
        conn = BoJConnector(cache_dir=str(tmp_path / "boj"))
        try:
            with pytest.raises(DataUnavailableError, match="browser-gated"):
                await conn.fetch_series(BOJ_BANK_RATE, date(2024, 12, 1), date(2024, 12, 31))
        finally:
            await conn.aclose()

    @pytest.mark.asyncio
    async def test_fetch_bank_rate_raises(self, tmp_path: Path) -> None:
        conn = BoJConnector(cache_dir=str(tmp_path / "boj"))
        try:
            with pytest.raises(DataUnavailableError, match="browser-gated"):
                await conn.fetch_bank_rate(date(2024, 1, 1), date(2024, 12, 31))
        finally:
            await conn.aclose()

    @pytest.mark.asyncio
    async def test_fetch_jgb_10y_raises(self, tmp_path: Path) -> None:
        conn = BoJConnector(cache_dir=str(tmp_path / "boj"))
        try:
            with pytest.raises(DataUnavailableError, match="browser-gated"):
                await conn.fetch_jgb_10y(date(2024, 1, 1), date(2024, 12, 31))
        finally:
            await conn.aclose()

    @pytest.mark.asyncio
    async def test_fetch_balance_sheet_raises(self, tmp_path: Path) -> None:
        conn = BoJConnector(cache_dir=str(tmp_path / "boj"))
        try:
            with pytest.raises(DataUnavailableError, match="browser-gated"):
                await conn.fetch_balance_sheet(date(2024, 1, 1), date(2024, 12, 31))
        finally:
            await conn.aclose()

    @pytest.mark.asyncio
    async def test_fetch_raw_error_message_mentions_series(self, tmp_path: Path) -> None:
        """Error surfaces the series ID so cascade logs are traceable."""
        conn = BoJConnector(cache_dir=str(tmp_path / "boj"))
        try:
            with pytest.raises(DataUnavailableError) as exc_info:
                await conn._fetch_raw(BOJ_BANK_RATE, date(2024, 1, 1), date(2024, 12, 31))
            assert BOJ_BANK_RATE in str(exc_info.value)
        finally:
            await conn.aclose()


class TestBoJConnectorCachePath:
    """When the portal ships a scriptable endpoint (future unblock), the
    disk cache path bypasses the raise. Seed the cache directly and
    confirm."""

    @pytest.mark.asyncio
    async def test_cache_hit_short_circuits_raise(self, tmp_path: Path) -> None:
        conn = BoJConnector(cache_dir=str(tmp_path / "boj"))
        try:
            seeded = [
                Observation(
                    country_code="JP",
                    observation_date=date(2024, 12, 19),
                    tenor_years=0.01,
                    yield_bps=25,  # 0.25 pct
                    source="BOJ",
                    source_series_id=BOJ_BANK_RATE,
                )
            ]
            cache_key = (
                f"{conn.CACHE_NAMESPACE}:{BOJ_BANK_RATE}:"
                f"{date(2024, 12, 1).isoformat()}:{date(2024, 12, 31).isoformat()}"
            )
            conn.cache.set(cache_key, seeded)
            obs = await conn.fetch_series(BOJ_BANK_RATE, date(2024, 12, 1), date(2024, 12, 31))
            assert len(obs) == 1
            assert obs[0].country_code == "JP"
            assert obs[0].source_series_id == BOJ_BANK_RATE
            assert obs[0].yield_bps == 25
        finally:
            await conn.aclose()
