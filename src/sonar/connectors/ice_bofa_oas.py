"""ICE BofA OAS (Option-Adjusted Spread) connector via FRED.

Per spec ``F3-risk-appetite.md`` §2: US HY (BAMLH0A0HYM2) and US IG
(BAMLC0A0CM) option-adjusted spreads, plus optional BBB IG
(BAMLC0A4CBBB) diagnostic.

Returned values are **percent** as published by FRED (e.g. ``4.25`` for
4.25%). F3 converts to bps internally; keeping percent here matches
the FRED native unit + avoids lossy integer rounding.
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

FRED_SERIES_HY_OAS = "BAMLH0A0HYM2"  # ICE BofA US High Yield Master II OAS
FRED_SERIES_IG_OAS = "BAMLC0A0CM"  # ICE BofA US Corporate Master OAS
FRED_SERIES_BBB_OAS = "BAMLC0A4CBBB"  # ICE BofA BBB US Corporate OAS (diagnostic)

OAS_METRIC_TO_SERIES: dict[str, str] = {
    "HY": FRED_SERIES_HY_OAS,
    "IG": FRED_SERIES_IG_OAS,
    "BBB": FRED_SERIES_BBB_OAS,
}

__all__ = [
    "FRED_SERIES_BBB_OAS",
    "FRED_SERIES_HY_OAS",
    "FRED_SERIES_IG_OAS",
    "IceBofaOasConnector",
    "OasObservation",
]


@dataclass(frozen=True, slots=True)
class OasObservation:
    """OAS observation in percent (e.g. 4.25 → 425 bps equivalent)."""

    observation_date: date
    value_pct: float
    metric: str  # "HY" | "IG" | "BBB"
    source: str = "FRED"
    source_series_id: str = ""

    @property
    def value_bps(self) -> int:
        """Convenience converter for consumers keeping bps internally."""
        return round(self.value_pct * 100)


class IceBofaOasConnector:
    """L0 connector for ICE BofA OAS spreads via FRED mirror."""

    def __init__(
        self,
        api_key: str,
        cache_dir: str | Path,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout)

    async def fetch_oas(self, metric: str, start: date, end: date) -> list[OasObservation]:
        series_id = OAS_METRIC_TO_SERIES.get(metric)
        if series_id is None:
            err = f"Unknown OAS metric {metric!r}; expected HY/IG/BBB"
            raise ValueError(err)
        pairs = await fetch_fred_values(
            self.client,
            self.cache,
            series_id=series_id,
            api_key=self.api_key,
            start=start,
            end=end,
            cache_prefix="ice_bofa_oas",
        )
        return [
            OasObservation(
                observation_date=d,
                value_pct=v,
                metric=metric,
                source_series_id=series_id,
            )
            for d, v in pairs
        ]

    async def fetch_latest(
        self, metric: str, observation_date: date, *, window_days: int = 7
    ) -> OasObservation | None:
        start = observation_date - timedelta(days=window_days)
        end = observation_date
        obs = await self.fetch_oas(metric, start, end)
        usable = [o for o in obs if o.observation_date <= observation_date]
        if not usable:
            return None
        usable.sort(key=lambda o: o.observation_date)
        return usable[-1]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
