"""Unit tests for Riksbank Swea L0 connector (Sprint W-SE).

The Riksbank Swea public API is reachable + scriptable (empirical
probe 2026-04-22 — see module docstring). The connector ships with a
real fetch implementation, not a gated scaffold; tests exercise:

- Series-ID catalogue stability (regression guard).
- Happy-path parse (date + value from the ``{date, value}`` schema).
- Negative-value preservation across the parse layer (core Sprint
  W-SE contract — the 2015-2020 negative-rate corridor must flow
  through unchanged to the downstream cascade).
- Empty ``[]`` → ``DataUnavailableError``.
- HTTP error → ``DataUnavailableError``.
- Disk cache round-trip (set / get short-circuits the HTTP call).
- All three convenience wrappers (``fetch_policy_rate`` /
  ``fetch_deposit_rate`` / ``fetch_lending_rate``).
- @slow live canary probes SECBREPOEFF and bands the recent band.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import pytest
from tenacity import wait_none

from sonar.connectors.base import Observation
from sonar.connectors.riksbank import (
    RIKSBANK_DEPOSIT_RATE,
    RIKSBANK_LENDING_RATE,
    RIKSBANK_POLICY_RATE,
    RIKSBANK_SWEA_BASE_URL,
    RiksbankConnector,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock


def test_series_ids_are_canonical() -> None:
    """Regression guard — Swea series codes must stay stable."""
    assert RIKSBANK_POLICY_RATE == "SECBREPOEFF"
    assert RIKSBANK_DEPOSIT_RATE == "SECBDEPOEFF"
    assert RIKSBANK_LENDING_RATE == "SECBLENDEFF"


def test_base_url_canonical() -> None:
    assert RIKSBANK_SWEA_BASE_URL == "https://api.riksbank.se/swea/v1"


class TestRiksbankConnectorLifecycle:
    @pytest.mark.asyncio
    async def test_instantiation_and_aclose(self, tmp_path: Path) -> None:
        conn = RiksbankConnector(cache_dir=str(tmp_path / "riksbank"))
        assert conn.CONNECTOR_ID == "riksbank"
        assert conn.CACHE_NAMESPACE == "riksbank_swea"
        await conn.aclose()


@pytest.fixture
async def riksbank_connector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RiksbankConnector:
    monkeypatch.setattr(RiksbankConnector._fetch_raw.retry, "wait", wait_none())
    return RiksbankConnector(cache_dir=str(tmp_path / "riksbank"))


class TestRiksbankConnectorFetchSeries:
    @pytest.mark.asyncio
    async def test_happy_path_parses_observations(
        self, httpx_mock: HTTPXMock, riksbank_connector: RiksbankConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            json=[
                {"date": "2024-01-02", "value": 4.0},
                {"date": "2024-01-03", "value": 4.0},
                {"date": "2024-06-27", "value": 3.75},
            ],
        )
        try:
            obs = await riksbank_connector.fetch_series(
                RIKSBANK_POLICY_RATE, date(2024, 1, 1), date(2024, 7, 1)
            )
            assert len(obs) == 3
            assert all(isinstance(o, Observation) for o in obs)
            # yield_bps = round(pct * 100). 4.00 % → 400 bps.
            assert obs[0].yield_bps == 400
            assert obs[0].country_code == "SE"
            assert obs[0].source == "RIKSBANK"
            assert obs[0].source_series_id == RIKSBANK_POLICY_RATE
            assert obs[0].observation_date == date(2024, 1, 2)
            assert obs[-1].yield_bps == 375  # 3.75 %
        finally:
            await riksbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_negative_values_preserved(
        self, httpx_mock: HTTPXMock, riksbank_connector: RiksbankConnector
    ) -> None:
        """Negative-rate era 2015-2020: signs flow through unchanged.

        This is the core Sprint W-SE contract — the 2015-02-12 →
        2020-01-07 Riksbank corridor must NOT be clamped at zero,
        flipped in sign, or silently dropped at the parse layer.
        Downstream cascade ``_se_policy_rate_cascade`` emits
        ``SE_NEGATIVE_RATE_ERA_DATA`` when any post-parse observation
        in the resolved window is strictly negative.
        """
        httpx_mock.add_response(
            method="GET",
            json=[
                {"date": "2016-02-17", "value": -0.5},
                {"date": "2017-06-15", "value": -0.5},
                {"date": "2019-01-09", "value": -0.25},
            ],
        )
        try:
            obs = await riksbank_connector.fetch_series(
                RIKSBANK_POLICY_RATE, date(2015, 1, 1), date(2020, 12, 31)
            )
            assert len(obs) == 3
            assert [o.yield_bps for o in obs] == [-50, -50, -25]
            assert all(o.yield_bps < 0 for o in obs)
            assert all(o.country_code == "SE" for o in obs)
        finally:
            await riksbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_empty_observations_raises_unavailable(
        self, httpx_mock: HTTPXMock, riksbank_connector: RiksbankConnector
    ) -> None:
        httpx_mock.add_response(method="GET", json=[])
        try:
            with pytest.raises(DataUnavailableError, match="empty observations"):
                await riksbank_connector.fetch_series(
                    RIKSBANK_POLICY_RATE, date(2024, 12, 1), date(2024, 12, 31)
                )
        finally:
            await riksbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_http_error_raises_unavailable(
        self, httpx_mock: HTTPXMock, riksbank_connector: RiksbankConnector
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
                await riksbank_connector.fetch_series(
                    RIKSBANK_POLICY_RATE, date(2024, 12, 1), date(2024, 12, 31)
                )
        finally:
            await riksbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_rows_with_null_values_are_skipped(
        self, httpx_mock: HTTPXMock, riksbank_connector: RiksbankConnector
    ) -> None:
        """Swea occasionally returns ``{"value": null}`` for holidays — drop."""
        httpx_mock.add_response(
            method="GET",
            json=[
                {"date": "2024-12-25", "value": None},
                {"date": "2024-12-26", "value": 3.75},
                {"date": None, "value": 3.75},
                {"date": "", "value": 3.75},
            ],
        )
        try:
            obs = await riksbank_connector.fetch_series(
                RIKSBANK_POLICY_RATE, date(2024, 12, 1), date(2024, 12, 31)
            )
            assert len(obs) == 1
            assert obs[0].observation_date == date(2024, 12, 26)
        finally:
            await riksbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_all_rows_unparseable_raises(
        self, httpx_mock: HTTPXMock, riksbank_connector: RiksbankConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            json=[
                {"date": "2024-12-25", "value": None},
                {"date": "2024-12-26", "value": None},
            ],
        )
        try:
            with pytest.raises(DataUnavailableError, match="unparseable"):
                await riksbank_connector.fetch_series(
                    RIKSBANK_POLICY_RATE, date(2024, 12, 1), date(2024, 12, 31)
                )
        finally:
            await riksbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_cache_round_trip_skips_second_http_call(
        self, httpx_mock: HTTPXMock, riksbank_connector: RiksbankConnector
    ) -> None:
        """Second call on same ``(series, start, end)`` hits cache, not HTTP."""
        httpx_mock.add_response(
            method="GET",
            json=[{"date": "2024-12-11", "value": 4.0}],
        )
        try:
            first = await riksbank_connector.fetch_series(
                RIKSBANK_POLICY_RATE, date(2024, 12, 1), date(2024, 12, 31)
            )
            second = await riksbank_connector.fetch_series(
                RIKSBANK_POLICY_RATE, date(2024, 12, 1), date(2024, 12, 31)
            )
            assert len(first) == 1
            assert first == second
            # Only one mocked HTTP call registered — second was cache.
            assert len(httpx_mock.get_requests()) == 1
        finally:
            await riksbank_connector.aclose()


class TestRiksbankConnectorWrappers:
    @pytest.mark.asyncio
    async def test_fetch_policy_rate_uses_canonical_series(
        self, httpx_mock: HTTPXMock, riksbank_connector: RiksbankConnector
    ) -> None:
        """``fetch_policy_rate`` routes to SECBREPOEFF."""
        httpx_mock.add_response(
            method="GET",
            json=[{"date": "2024-01-02", "value": 4.0}],
        )
        try:
            obs = await riksbank_connector.fetch_policy_rate(date(2024, 1, 1), date(2024, 1, 31))
            assert obs[0].source_series_id == RIKSBANK_POLICY_RATE
            assert obs[0].yield_bps == 400
        finally:
            await riksbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_fetch_deposit_rate_uses_canonical_series(
        self, httpx_mock: HTTPXMock, riksbank_connector: RiksbankConnector
    ) -> None:
        """``fetch_deposit_rate`` routes to SECBDEPOEFF."""
        httpx_mock.add_response(
            method="GET",
            json=[{"date": "2024-01-02", "value": 3.25}],
        )
        try:
            obs = await riksbank_connector.fetch_deposit_rate(date(2024, 1, 1), date(2024, 1, 31))
            assert obs[0].source_series_id == RIKSBANK_DEPOSIT_RATE
            assert obs[0].yield_bps == 325
        finally:
            await riksbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_fetch_lending_rate_uses_canonical_series(
        self, httpx_mock: HTTPXMock, riksbank_connector: RiksbankConnector
    ) -> None:
        """``fetch_lending_rate`` routes to SECBLENDEFF."""
        httpx_mock.add_response(
            method="GET",
            json=[{"date": "2024-01-02", "value": 4.75}],
        )
        try:
            obs = await riksbank_connector.fetch_lending_rate(date(2024, 1, 1), date(2024, 1, 31))
            assert obs[0].source_series_id == RIKSBANK_LENDING_RATE
            assert obs[0].yield_bps == 475
        finally:
            await riksbank_connector.aclose()


@pytest.mark.slow
async def test_live_canary_riksbank_policy_rate(tmp_path: Path) -> None:
    """Live Swea probe — SECBREPOEFF (Riksbank policy rate) last 60 days.

    Does not require any API key — Swea is public. Skips only if the
    network is unreachable. Asserts the recent band roughly matches
    the Riksbank normalisation (2023-26 policy stayed within
    [1.50, 4.00] %).
    """
    conn = RiksbankConnector(cache_dir=str(tmp_path / "riksbank"))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=60)
        try:
            obs = await conn.fetch_policy_rate(start, today)
        except (httpx.HTTPError, DataUnavailableError) as exc:
            pytest.skip(f"Riksbank Swea unreachable: {exc}")
        assert len(obs) >= 10  # ≥10 trading days in a 60-day window
        assert obs[0].country_code == "SE"
        assert obs[0].source_series_id == RIKSBANK_POLICY_RATE
        for o in obs:
            # yield_bps in [-100, 600] — band guards against unit
            # regression while leaving slack for the negative-rate
            # floor of the historical -0.50 % corridor (pre-2019).
            assert -100 <= o.yield_bps <= 600
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_riksbank_policy_rate_negative_era(tmp_path: Path) -> None:
    """Live Swea probe of a hardcoded window inside the 2015-2020
    negative-rate corridor — validates end-to-end negative-value
    preservation through the parse + yield_bps conversion layers.
    """
    conn = RiksbankConnector(cache_dir=str(tmp_path / "riksbank"))
    try:
        try:
            obs = await conn.fetch_policy_rate(date(2017, 1, 1), date(2017, 6, 30))
        except (httpx.HTTPError, DataUnavailableError) as exc:
            pytest.skip(f"Riksbank Swea unreachable: {exc}")
        assert len(obs) >= 50
        neg = [o for o in obs if o.yield_bps < 0]
        # 2017 was fully inside the -0.50 % corridor — every observation
        # should be strictly-negative.
        assert len(neg) == len(obs)
        assert all(o.yield_bps == -50 for o in obs)
    finally:
        await conn.aclose()


# Parametrised unit coverage of the Riksbank env-hook (no key required).
def test_no_env_key_required_for_riksbank() -> None:
    """Swea API is keyless — ``RIKSBANK_API_KEY`` / similar must not exist."""
    assert "RIKSBANK_API_KEY" not in os.environ
