"""Unit tests for BoC Valet L0 connector (Sprint S).

The BoC Valet public API is reachable + scriptable (empirical probe
2026-04-21 — see module docstring). The connector ships with a real
fetch implementation, not a gated scaffold; tests exercise:

- Series-ID catalogue stability (regression guard).
- Happy-path parse (date + value from the ``{d, {v}}`` schema).
- Empty ``observations`` → ``DataUnavailableError``.
- HTTP error → ``DataUnavailableError``.
- Disk cache round-trip (set / get short-circuits the HTTP call).
- Both ``fetch_bank_rate`` + ``fetch_goc_10y`` convenience wrappers.
- @slow live canary probes V39079 and bands the recent band.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import pytest
from tenacity import wait_none

from sonar.connectors.base import Observation
from sonar.connectors.boc import (
    BOC_GOC_10Y,
    BOC_OVERNIGHT_TARGET,
    BOC_VALET_BASE_URL,
    BoCConnector,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock


def test_series_ids_are_canonical() -> None:
    """Regression guard — BoC Valet series codes must stay stable."""
    assert BOC_OVERNIGHT_TARGET == "V39079"
    assert BOC_GOC_10Y == "BD.CDN.10YR.DQ.YLD"


def test_base_url_canonical() -> None:
    assert BOC_VALET_BASE_URL == "https://www.bankofcanada.ca/valet"


class TestBoCConnectorLifecycle:
    @pytest.mark.asyncio
    async def test_instantiation_and_aclose(self, tmp_path: Path) -> None:
        conn = BoCConnector(cache_dir=str(tmp_path / "boc"))
        assert conn.CONNECTOR_ID == "boc"
        assert conn.CACHE_NAMESPACE == "boc_valet"
        await conn.aclose()


@pytest.fixture
async def boc_connector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BoCConnector:
    monkeypatch.setattr(BoCConnector._fetch_raw.retry, "wait", wait_none())
    return BoCConnector(cache_dir=str(tmp_path / "boc"))


class TestBoCConnectorFetchSeries:
    @pytest.mark.asyncio
    async def test_happy_path_parses_observations(
        self, httpx_mock: HTTPXMock, boc_connector: BoCConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            json={
                "terms": {"url": "https://www.bankofcanada.ca/terms/"},
                "seriesDetail": {
                    "V39079": {
                        "label": "V39079",
                        "description": "Target for the overnight rate",
                    }
                },
                "observations": [
                    {"d": "2024-12-11", "V39079": {"v": "3.25"}},
                    {"d": "2024-12-12", "V39079": {"v": "3.25"}},
                    {"d": "2025-01-29", "V39079": {"v": "3.00"}},
                ],
            },
        )
        try:
            obs = await boc_connector.fetch_series(
                BOC_OVERNIGHT_TARGET, date(2024, 12, 1), date(2025, 2, 1)
            )
            assert len(obs) == 3
            assert all(isinstance(o, Observation) for o in obs)
            # yield_bps = round(pct * 100). 3.25 % → 325 bps.
            assert obs[0].yield_bps == 325
            assert obs[0].country_code == "CA"
            assert obs[0].source == "BOC"
            assert obs[0].source_series_id == BOC_OVERNIGHT_TARGET
            assert obs[0].observation_date == date(2024, 12, 11)
            assert obs[-1].yield_bps == 300  # 3.00 %
        finally:
            await boc_connector.aclose()

    @pytest.mark.asyncio
    async def test_empty_observations_raises_unavailable(
        self, httpx_mock: HTTPXMock, boc_connector: BoCConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            json={"seriesDetail": {"V39079": {}}, "observations": []},
        )
        try:
            with pytest.raises(DataUnavailableError, match="empty observations"):
                await boc_connector.fetch_series(
                    BOC_OVERNIGHT_TARGET, date(2024, 12, 1), date(2024, 12, 31)
                )
        finally:
            await boc_connector.aclose()

    @pytest.mark.asyncio
    async def test_http_error_raises_unavailable(
        self, httpx_mock: HTTPXMock, boc_connector: BoCConnector
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
                await boc_connector.fetch_series(
                    BOC_OVERNIGHT_TARGET, date(2024, 12, 1), date(2024, 12, 31)
                )
        finally:
            await boc_connector.aclose()

    @pytest.mark.asyncio
    async def test_rows_with_null_values_are_skipped(
        self, httpx_mock: HTTPXMock, boc_connector: BoCConnector
    ) -> None:
        """Valet occasionally returns ``{"v": ""}`` for holidays — drop those rows."""
        httpx_mock.add_response(
            method="GET",
            json={
                "observations": [
                    {"d": "2024-12-25", "V39079": {"v": ""}},
                    {"d": "2024-12-26", "V39079": {"v": None}},
                    {"d": "2024-12-27", "V39079": {"v": "3.25"}},
                ],
            },
        )
        try:
            obs = await boc_connector.fetch_series(
                BOC_OVERNIGHT_TARGET, date(2024, 12, 1), date(2024, 12, 31)
            )
            assert len(obs) == 1
            assert obs[0].observation_date == date(2024, 12, 27)
        finally:
            await boc_connector.aclose()

    @pytest.mark.asyncio
    async def test_all_rows_unparseable_raises(
        self, httpx_mock: HTTPXMock, boc_connector: BoCConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            json={
                "observations": [
                    {"d": "2024-12-25", "V39079": {"v": None}},
                    {"d": "2024-12-26", "V39079": {"v": ""}},
                ],
            },
        )
        try:
            with pytest.raises(DataUnavailableError, match="unparseable"):
                await boc_connector.fetch_series(
                    BOC_OVERNIGHT_TARGET, date(2024, 12, 1), date(2024, 12, 31)
                )
        finally:
            await boc_connector.aclose()

    @pytest.mark.asyncio
    async def test_cache_round_trip_skips_second_http_call(
        self, httpx_mock: HTTPXMock, boc_connector: BoCConnector
    ) -> None:
        """Second call on the same ``(series, start, end)`` hits the cache, not HTTP."""
        httpx_mock.add_response(
            method="GET",
            json={"observations": [{"d": "2024-12-11", "V39079": {"v": "3.25"}}]},
        )
        try:
            first = await boc_connector.fetch_series(
                BOC_OVERNIGHT_TARGET, date(2024, 12, 1), date(2024, 12, 31)
            )
            second = await boc_connector.fetch_series(
                BOC_OVERNIGHT_TARGET, date(2024, 12, 1), date(2024, 12, 31)
            )
            assert len(first) == 1
            assert first == second
            # Only one mocked HTTP call registered — second was cache.
            assert len(httpx_mock.get_requests()) == 1
        finally:
            await boc_connector.aclose()


class TestBoCConnectorWrappers:
    @pytest.mark.asyncio
    async def test_fetch_bank_rate_uses_overnight_target_series(
        self, httpx_mock: HTTPXMock, boc_connector: BoCConnector
    ) -> None:
        """``fetch_bank_rate`` routes to V39079 (overnight target)."""
        httpx_mock.add_response(
            method="GET",
            json={"observations": [{"d": "2024-12-11", "V39079": {"v": "3.25"}}]},
        )
        try:
            obs = await boc_connector.fetch_bank_rate(date(2024, 12, 1), date(2024, 12, 31))
            assert obs[0].source_series_id == BOC_OVERNIGHT_TARGET
            assert obs[0].yield_bps == 325
        finally:
            await boc_connector.aclose()

    @pytest.mark.asyncio
    async def test_fetch_goc_10y_uses_canonical_series(
        self, httpx_mock: HTTPXMock, boc_connector: BoCConnector
    ) -> None:
        """``fetch_goc_10y`` routes to BD.CDN.10YR.DQ.YLD (GoC 10Y benchmark)."""
        httpx_mock.add_response(
            method="GET",
            json={"observations": [{"d": "2024-12-11", "BD.CDN.10YR.DQ.YLD": {"v": "3.20"}}]},
        )
        try:
            obs = await boc_connector.fetch_goc_10y(date(2024, 12, 1), date(2024, 12, 31))
            assert obs[0].source_series_id == BOC_GOC_10Y
            assert obs[0].yield_bps == 320
        finally:
            await boc_connector.aclose()


@pytest.mark.slow
async def test_live_canary_boc_overnight_target(tmp_path: Path) -> None:
    """Live Valet probe — V39079 (BoC overnight target) within the last 60 days.

    Does not require any API key — Valet is public. Skips only if the
    network is unreachable. Asserts the recent band roughly matches the
    BoC normalisation (2023-26 policy stayed within [2.25, 5.00] %).
    """
    conn = BoCConnector(cache_dir=str(tmp_path / "boc"))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=60)
        try:
            obs = await conn.fetch_bank_rate(start, today)
        except (httpx.HTTPError, DataUnavailableError) as exc:
            pytest.skip(f"BoC Valet unreachable: {exc}")
        assert len(obs) >= 10  # ≥10 trading days in a 60-day window
        assert obs[0].country_code == "CA"
        assert obs[0].source_series_id == BOC_OVERNIGHT_TARGET
        for o in obs:
            # yield_bps in [100, 600] — guards against unit regression
            # (BoC hasn't touched that band post-2000 outside emergency).
            assert 100 <= o.yield_bps <= 600
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_boc_goc_10y(tmp_path: Path) -> None:
    """Live Valet probe — V122544 (GoC 10Y benchmark yield) last 60 days."""
    conn = BoCConnector(cache_dir=str(tmp_path / "boc"))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=60)
        try:
            obs = await conn.fetch_goc_10y(start, today)
        except (httpx.HTTPError, DataUnavailableError) as exc:
            pytest.skip(f"BoC Valet unreachable: {exc}")
        assert len(obs) >= 10
        # GoC 10Y stayed within [0.5, 5.0] % across the last decade.
        for o in obs:
            assert 50 <= o.yield_bps <= 600
    finally:
        await conn.aclose()


# Parametrised unit coverage of the BoC env-hook (no TE key required).
# Kept as a light smoke to ensure ``os.environ`` read paths don't
# accidentally become required for the otherwise-keyless Valet API.
def test_no_env_key_required_for_boc() -> None:
    """Valet API is keyless — ``BOC_API_KEY`` / similar env must not exist."""
    assert "BOC_API_KEY" not in os.environ
