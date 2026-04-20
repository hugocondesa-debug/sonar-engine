"""Chicago Fed National Financial Conditions Index (NFCI) connector via FRED.

Per spec ``F3-risk-appetite.md`` §2: NFCI (US) ``NFCI`` weekly standardized
stress index (mean 0, stdev 1 by construction); ANFCI (adjusted) as
diagnostic. Higher values = tighter financial conditions / elevated
stress.

Observations stay in the native NFCI z-score scale; consumers at F3
apply **additional** 20Y rolling z-score per spec §4 (invert sign so
loose conditions → high risk appetite score).
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

FRED_SERIES_NFCI = "NFCI"  # Chicago Fed National Financial Conditions Index
FRED_SERIES_ANFCI = "ANFCI"  # Adjusted NFCI (residual after macro controls)

NFCI_METRIC_TO_SERIES: dict[str, str] = {
    "NFCI": FRED_SERIES_NFCI,
    "ANFCI": FRED_SERIES_ANFCI,
}

__all__ = [
    "FRED_SERIES_ANFCI",
    "FRED_SERIES_NFCI",
    "ChicagoFedNfciConnector",
    "NfciObservation",
]


@dataclass(frozen=True, slots=True)
class NfciObservation:
    """NFCI observation in native z-score (mean=0, stdev=1 by construction)."""

    observation_date: date
    value_zscore: float
    metric: str  # "NFCI" | "ANFCI"
    source: str = "FRED"
    source_series_id: str = ""


class ChicagoFedNfciConnector:
    """L0 connector for Chicago Fed NFCI / ANFCI via FRED."""

    def __init__(
        self,
        api_key: str,
        cache_dir: str | Path,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout)

    async def fetch_nfci(self, metric: str, start: date, end: date) -> list[NfciObservation]:
        series_id = NFCI_METRIC_TO_SERIES.get(metric)
        if series_id is None:
            err = f"Unknown NFCI metric {metric!r}; expected NFCI/ANFCI"
            raise ValueError(err)
        pairs = await fetch_fred_values(
            self.client,
            self.cache,
            series_id=series_id,
            api_key=self.api_key,
            start=start,
            end=end,
            cache_prefix="chicago_fed_nfci",
        )
        return [
            NfciObservation(
                observation_date=d,
                value_zscore=v,
                metric=metric,
                source_series_id=series_id,
            )
            for d, v in pairs
        ]

    async def fetch_latest(
        self, metric: str, observation_date: date, *, window_days: int = 14
    ) -> NfciObservation | None:
        """NFCI is weekly (Wednesdays); widen window to 14 days by default."""
        start = observation_date - timedelta(days=window_days)
        end = observation_date
        obs = await self.fetch_nfci(metric, start, end)
        usable = [o for o in obs if o.observation_date <= observation_date]
        if not usable:
            return None
        usable.sort(key=lambda o: o.observation_date)
        return usable[-1]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
