"""FINRA margin-debt connector via FRED (quarterly).

Per spec ``F4-positioning.md`` §2: FINRA member firm customer margin
loans by broker-dealers. FRED hosts the Fed Z.1 aggregate
``BOGZ1FL663067003Q`` (Securities brokers and dealers; security credit
as a liability of the household sector) quarterly. Raw value is in
millions of USD.

F4 computes ``margin_debt_gdp_pct = value_m_usd / (gdp_m_usd) * 100``
using FRED ``GDP`` (billions USD) as denominator — conversion is the
consumer's responsibility, this connector returns the raw series.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import httpx
import structlog

from sonar.connectors._fred_util import fetch_fred_values
from sonar.connectors.cache import ConnectorCache

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

log = structlog.get_logger()

FRED_SERIES_MARGIN_DEBT = "BOGZ1FL663067003Q"

__all__ = [
    "FRED_SERIES_MARGIN_DEBT",
    "FinraMarginDebtConnector",
    "MarginDebtObservation",
]


@dataclass(frozen=True, slots=True)
class MarginDebtObservation:
    """Quarterly margin-debt observation in millions USD."""

    observation_date: date
    value_m_usd: float
    source: str = "FRED"
    source_series_id: str = FRED_SERIES_MARGIN_DEBT


class FinraMarginDebtConnector:
    """L0 connector for FINRA margin-debt quarterly via FRED mirror."""

    def __init__(
        self,
        api_key: str,
        cache_dir: str | Path,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout)

    async def fetch_series(self, start: date, end: date) -> list[MarginDebtObservation]:
        pairs = await fetch_fred_values(
            self.client,
            self.cache,
            series_id=FRED_SERIES_MARGIN_DEBT,
            api_key=self.api_key,
            start=start,
            end=end,
            cache_prefix="finra_margin_debt",
        )
        return [MarginDebtObservation(observation_date=d, value_m_usd=v) for d, v in pairs]

    async def fetch_latest(
        self, observation_date: date, *, window_days: int = 180
    ) -> MarginDebtObservation | None:
        """Quarterly release ~60d lag; widen default window to 180d."""
        start = observation_date - timedelta(days=window_days)
        end = observation_date
        obs = await self.fetch_series(start, end)
        usable = [o for o in obs if o.observation_date <= observation_date]
        if not usable:
            return None
        usable.sort(key=lambda o: o.observation_date)
        return usable[-1]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
