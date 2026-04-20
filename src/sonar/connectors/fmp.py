"""Financial Modeling Prep (FMP) L0 connector — equity index historical EOD.

Ultimate tier provides 30Y+ daily EOD history for major equity indices
— Week 3.5 pivot from twelvedata/yfinance (CAL-040 closed). Auth via
``FMP_API_KEY`` env.

Endpoint: ``https://financialmodelingprep.com/stable/historical-price-eod/full``
Documented URL pattern: ``?symbol=<s>&from=YYYY-MM-DD&to=YYYY-MM-DD&apikey=<k>``

Symbol mapping: FMP uses ``^`` prefixed tickers for indices
(``^GSPC`` = S&P 500, ``^GDAXI`` = DAX, ``^FCHI`` = CAC 40, ``^FTSE``
= FTSE 100, ``^STOXX50E`` = STOXX 50, ``^N225`` = Nikkei 225, etc.).
See ``FMP_INDEX_SYMBOLS`` for the SONAR-aliased lookup.

Observations keep decimal close price in ``yield_bps`` (re-purposed
as integer "scaled price x 100" per L0 integer storage convention —
consumer ``overlays/crp.py`` converts back on the L2 boundary). This
breaks the strict yield semantics but preserves the Observation
pydantic contract for unified connector caching / test patterns.

For strict equity index persistence we use a separate field — so the
method returns ``list[FMPPriceObservation]`` (a dedicated dataclass),
not the Observation pydantic model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

log = structlog.get_logger()

# SONAR alias → FMP symbol. Use SONAR aliases externally; this mapping
# lives at the connector boundary.
FMP_INDEX_SYMBOLS: dict[str, str] = {
    "SPX": "^GSPC",
    "DAX": "^GDAXI",
    "CAC": "^FCHI",
    "FTSE": "^FTSE",
    "FTSEMIB": "FTSEMIB.MI",
    "AEX": "^AEX",
    "IBEX": "^IBEX",
    "PSI": "PSI20.LS",
    "SXXP": "^STOXX",
    "SX5E": "^STOXX50E",
    "NKY": "^N225",
    "TPX": "^TPX",
}


@dataclass(frozen=True, slots=True)
class FMPPriceObservation:
    """Single EOD price row from FMP (decimal close kept as-is)."""

    symbol_sonar: str
    symbol_fmp: str
    observation_date: date
    close: float
    volume: int | None
    source: str = "FMP"


class FMPConnector:
    """L0 connector for FMP stable v3 historical EOD data."""

    BASE_URL = "https://financialmodelingprep.com/stable"
    ENDPOINT_HISTORICAL_EOD = "/historical-price-eod/full"

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
    async def _fetch_raw(self, symbol_fmp: str, start: date, end: date) -> list[dict[str, Any]]:
        url = f"{self.BASE_URL}{self.ENDPOINT_HISTORICAL_EOD}"
        params = {
            "symbol": symbol_fmp,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "apikey": self.api_key,
        }
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        payload = r.json()
        if isinstance(payload, dict) and "Error Message" in payload:
            msg = f"FMP error for {symbol_fmp}: {payload['Error Message']}"
            raise ValueError(msg)
        return cast("list[dict[str, Any]]", payload or [])

    async def fetch_index_historical(
        self,
        symbol_sonar: str,
        start: date,
        end: date,
    ) -> list[FMPPriceObservation]:
        """Return EOD price rows for a SONAR-aliased index, ascending by date.

        Raises:
            ValueError: unknown ``symbol_sonar`` alias OR API error payload.
        """
        symbol_fmp = FMP_INDEX_SYMBOLS.get(symbol_sonar)
        if symbol_fmp is None:
            msg = f"Unknown SONAR index alias: {symbol_sonar}"
            raise ValueError(msg)

        cache_key = f"fmp:{symbol_fmp}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("fmp.cache_hit", symbol=symbol_fmp)
            return cast("list[FMPPriceObservation]", cached)

        raw = await self._fetch_raw(symbol_fmp, start, end)
        out: list[FMPPriceObservation] = []
        for row in raw:
            raw_date = row.get("date")
            raw_close = row.get("close")
            if not raw_date or raw_close is None:
                continue
            try:
                obs_date = datetime.fromisoformat(str(raw_date)).date()
                close = float(raw_close)
            except (ValueError, TypeError):
                continue
            volume_raw = row.get("volume")
            try:
                volume: int | None = int(volume_raw) if volume_raw is not None else None
            except (ValueError, TypeError):
                volume = None
            out.append(
                FMPPriceObservation(
                    symbol_sonar=symbol_sonar,
                    symbol_fmp=symbol_fmp,
                    observation_date=obs_date,
                    close=close,
                    volume=volume,
                )
            )
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        log.info("fmp.fetched", symbol=symbol_fmp, n=len(out))
        return out

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
