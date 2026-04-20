"""CBOE connector — VIX + VVIX + put/call ratio via FRED mirror.

Primary path: FRED-wrapped series (fetch fed by ``_fred_util``). CBOE
direct endpoints require cookie-based session; FRED is cleaner for
single-series daily fetch and is the production canonical per spec
``F3-risk-appetite.md`` §2 + §10 (FRED ``VIXCLS`` attribution).

Observations returned carry the raw FRED value:

- VIX / VVIX: level in annualized % (e.g. ``14.2``)
- CBOE total put/call: ratio (e.g. ``0.85``)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

import httpx
import structlog

from sonar.connectors._fred_util import fetch_fred_values
from sonar.connectors.cache import ConnectorCache

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()

# FRED series IDs — canonical CBOE mirror.
FRED_SERIES_VIX = "VIXCLS"
FRED_SERIES_VVIX = "VVIXCLS"
FRED_SERIES_PUTCALL = "PUTCLSPX"  # CBOE S&P 500 total P/C ratio (CPC)

__all__ = [
    "FRED_SERIES_PUTCALL",
    "FRED_SERIES_VIX",
    "FRED_SERIES_VVIX",
    "CboeConnector",
    "CboeObservation",
]


@dataclass(frozen=True, slots=True)
class CboeObservation:
    """CBOE market-level observation (level or ratio, per ``metric``)."""

    observation_date: date
    value: float
    metric: str  # "VIX" | "VVIX" | "PUTCALL"
    source: str = "FRED"
    source_series_id: str = ""


class CboeConnector:
    """L0 connector for CBOE-published volatility + options series via FRED."""

    def __init__(
        self,
        api_key: str,
        cache_dir: str | Path,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout)

    async def _fetch_metric(
        self,
        series_id: str,
        metric: str,
        start: date,
        end: date,
    ) -> list[CboeObservation]:
        pairs = await fetch_fred_values(
            self.client,
            self.cache,
            series_id=series_id,
            api_key=self.api_key,
            start=start,
            end=end,
            cache_prefix="cboe",
        )
        return [
            CboeObservation(
                observation_date=d,
                value=v,
                metric=metric,
                source_series_id=series_id,
            )
            for d, v in pairs
        ]

    async def fetch_vix(self, start: date, end: date) -> list[CboeObservation]:
        return await self._fetch_metric(FRED_SERIES_VIX, "VIX", start, end)

    async def fetch_vvix(self, start: date, end: date) -> list[CboeObservation]:
        return await self._fetch_metric(FRED_SERIES_VVIX, "VVIX", start, end)

    async def fetch_put_call(self, start: date, end: date) -> list[CboeObservation]:
        return await self._fetch_metric(FRED_SERIES_PUTCALL, "PUTCALL", start, end)

    async def fetch_latest_level(
        self, metric: str, observation_date: date, *, window_days: int = 7
    ) -> CboeObservation | None:
        """Return the most recent observation on or before ``observation_date``.

        Window widened to ``window_days`` so a weekend/holiday lookup still
        returns the prior session's value. Returns ``None`` if the
        window is empty.
        """
        start = observation_date - timedelta(days=window_days)
        end = observation_date
        fetcher = {
            "VIX": self.fetch_vix,
            "VVIX": self.fetch_vvix,
            "PUTCALL": self.fetch_put_call,
        }.get(metric)
        if fetcher is None:
            err = f"Unknown CBOE metric {metric!r}"
            raise ValueError(err)
        obs = await fetcher(start, end)
        usable = [o for o in obs if o.observation_date <= observation_date]
        if not usable:
            return None
        usable.sort(key=lambda o: o.observation_date)
        return usable[-1]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
