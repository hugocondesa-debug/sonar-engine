"""Trading Economics (TE) L0 connector — sovereign 10Y historical yields.

Week 3.5 scope: 10Y government bond yield historical daily for the
target T1 countries. Full markets endpoint uses ``/markets/historical``
with Bloomberg-style symbols (``USGG10YR:IND``, ``GDBR10:IND``, etc.).

Auth: TE_API_KEY env (format ``key:secret``). Endpoint:
``https://api.tradingeconomics.com/markets/historical/<symbol>?c=<key>&d1=YYYY-MM-DD&d2=YYYY-MM-DD&f=json``

Returned rows: ``{Symbol, Date (DD/MM/YYYY), Open, High, Low, Close}``
— yields in percent. We store yield_bps at the L0 boundary per
units.md §Spreads (``int(round(close_pct * 100))``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.base import Observation
from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

log = structlog.get_logger()

# SONAR 2-letter country code → TE 10Y Bloomberg symbol.
TE_10Y_SYMBOLS: dict[str, str] = {
    "US": "USGG10YR:IND",
    "DE": "GDBR10:IND",
    "UK": "GUKG10:IND",
    "JP": "GJGB10:IND",
    "IT": "GBTPGR10:IND",
    "ES": "GSPG10YR:IND",
    "FR": "GFRN10:IND",
    "NL": "GNTH10YR:IND",
    "PT": "GSPT10YR:IND",
}


class TEConnector:
    """L0 connector for TradingEconomics markets historical yields."""

    BASE_URL = "https://api.tradingeconomics.com"

    def __init__(
        self,
        api_key: str,
        cache_dir: str | Path,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(self, symbol: str, start: date, end: date) -> list[dict[str, Any]]:
        url = f"{self.BASE_URL}/markets/historical/{symbol}"
        params = {
            "c": self.api_key,
            "d1": start.isoformat(),
            "d2": end.isoformat(),
            "f": "json",
        }
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        payload = r.json()
        return cast("list[dict[str, Any]]", payload or [])

    async def fetch_sovereign_yield_historical(
        self,
        country: str,
        tenor: str,
        start: date,
        end: date,
    ) -> list[Observation]:
        """Return daily 10Y yields (as Observations with ``yield_bps``).

        Week 3.5 supports ``tenor == "10Y"`` only — TE covers the
        full curve for most T1 countries but mapping the long-end
        is sufficient for the CRP vol_ratio use case.

        Raises:
            ValueError: unknown country or unsupported tenor.
        """
        if tenor != "10Y":
            msg = f"TEConnector supports tenor='10Y' only for Week 3.5; got {tenor}"
            raise ValueError(msg)
        symbol = TE_10Y_SYMBOLS.get(country)
        if symbol is None:
            msg = f"Unknown TE 10Y symbol for country: {country}"
            raise ValueError(msg)

        cache_key = f"te:{symbol}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("te.cache_hit", symbol=symbol)
            return cast("list[Observation]", cached)

        rows = await self._fetch_raw(symbol, start, end)
        out: list[Observation] = []
        for row in rows:
            raw_date = row.get("Date")
            raw_close = row.get("Close")
            if not raw_date or raw_close is None:
                continue
            # TE format: "DD/MM/YYYY"
            try:
                obs_date = datetime.strptime(str(raw_date), "%d/%m/%Y").replace(tzinfo=UTC).date()
                close_pct = float(raw_close)
            except (ValueError, TypeError):
                continue
            out.append(
                Observation(
                    country_code=country,
                    observation_date=obs_date,
                    tenor_years=10.0,
                    yield_bps=int(round(close_pct * 100)),
                    source="TE",
                    source_series_id=symbol,
                )
            )
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        log.info("te.fetched", symbol=symbol, n=len(out))
        return out

    async def fetch_10y_window_around(
        self,
        country: str,
        observation_date: date,
        lookback_days: int = 365 * 5 + 30,
    ) -> list[Observation]:
        """Return 5Y of daily 10Y yields ending at ``observation_date``.

        Convenience wrapper used by ``overlays/crp.py`` vol_ratio
        computation which needs ≥ 750 business-day observations.
        """
        start = observation_date - timedelta(days=lookback_days)
        return await self.fetch_sovereign_yield_historical(country, "10Y", start, observation_date)

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
