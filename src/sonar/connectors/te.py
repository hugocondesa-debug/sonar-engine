"""Trading Economics (TE) L0 connector — sovereign yields + economic-indicator fallback.

Week 3.5 scope: 10Y government bond yield historical daily via the
``/markets/historical`` endpoint with Bloomberg-style symbols
(``USGG10YR:IND``, ``GDBR10:IND``, etc.).

Week 6 Sprint 1 extension (CAL-092/086/093): fallback path for the
FRED-delisted US sentiment series (ISM Mfg, ISM Svc, NFIB) and the
DE sentiment series (Ifo, ZEW) via the
``/historical/country/{country}/indicator/{indicator}`` endpoint.

Auth: ``TE_API_KEY`` env (format ``key:secret``). Endpoints:

- Markets historical:
  ``.../markets/historical/<symbol>?c=<key>&d1=YYYY-MM-DD&d2=YYYY-MM-DD&f=json``
- Country indicator historical:
  ``.../historical/country/<country>/indicator/<indicator>?c=<key>&d1=...&d2=...&f=json``

Returned markets rows: ``{Symbol, Date (DD/MM/YYYY), Open, High, Low, Close}``
— yields in percent. We store ``yield_bps`` at the L0 boundary per
``conventions/units.md`` §Spreads (``int(round(close_pct * 100))``).

Returned indicator rows: ``{Country, Category, DateTime
(YYYY-MM-DDT...), Value, Frequency, HistoricalDataSymbol, ...}``. We
expose the flat ``(date, value)`` tuple via :class:`TEIndicatorObservation`.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

log = structlog.get_logger()


# ISO 3166-1 alpha-2 → TE canonical country name (used by
# /historical/country/{country}/indicator/{indicator}).
TE_COUNTRY_NAME_MAP: dict[str, str] = {
    "US": "united states",
    "DE": "germany",
    "UK": "united kingdom",
    "JP": "japan",
    "IT": "italy",
    "ES": "spain",
    "FR": "france",
    "NL": "netherlands",
    "PT": "portugal",
}

# Canonical TE indicator names (verified empirically Week 6 Sprint 1
# pre-flight probe). TE labels the *headline* ISM PMI as "Business
# Confidence" (sourced from ISM) and the Ifo Business Climate headline
# likewise as "Business Confidence" under Germany. Store both the
# TE-facing name and an internal key for dispatch.
TE_INDICATOR_ISM_MFG_HEADLINE = "business confidence"
TE_INDICATOR_ISM_SVC_HEADLINE = "non manufacturing pmi"
TE_INDICATOR_NFIB = "nfib business optimism index"
TE_INDICATOR_IFO_HEADLINE = "business confidence"
TE_INDICATOR_ZEW_ECONOMIC_SENTIMENT = "zew economic sentiment index"
TE_INDICATOR_CONSUMER_CONFIDENCE = "consumer confidence"


@dataclass(frozen=True, slots=True)
class TEIndicatorObservation:
    """Single historical observation from TE's country-indicator endpoint."""

    observation_date: date
    value: float
    country: str  # ISO alpha-2, uppercase
    indicator: str  # canonical lowercase TE name
    source: str = "TE"
    frequency: str = ""  # "Monthly", "Quarterly", etc.


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
        # Call counter for Pro-tier quota telemetry (10k/mês). Incremented
        # on every successful fetch against either endpoint. Reset via
        # :meth:`reset_call_count`.
        self._call_count: int = 0

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
                    yield_bps=round(close_pct * 100),
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

    # -------------------------------------------------------------------
    # Economic-indicator fallback (CAL-092/086/093) — Week 6 Sprint 1
    # -------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_indicator_raw(
        self, country_name: str, indicator_name: str, start: date, end: date
    ) -> list[dict[str, Any]]:
        url = f"{self.BASE_URL}/historical/country/{country_name}/indicator/{indicator_name}"
        params = {
            "c": self.api_key,
            "d1": start.isoformat(),
            "d2": end.isoformat(),
            "f": "json",
        }
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        payload = r.json()
        if not isinstance(payload, list):
            err = (
                f"TE indicator response non-list: country={country_name!r} "
                f"indicator={indicator_name!r} type={type(payload).__name__}"
            )
            raise DataUnavailableError(err)
        return cast("list[dict[str, Any]]", payload)

    async def fetch_indicator(
        self,
        country_iso: str,
        indicator_name: str,
        start_date: date,
        end_date: date,
    ) -> list[TEIndicatorObservation]:
        """Fetch a TE economic indicator time series.

        ``country_iso`` is the SONAR 2-letter code (``"US"``, ``"DE"`` …);
        mapped to TE's canonical country slug via
        :data:`TE_COUNTRY_NAME_MAP`. ``indicator_name`` is the exact TE
        lowercase label (see ``TE_INDICATOR_*`` constants).

        Empty response for the (country, indicator) pair raises
        :class:`DataUnavailableError`. Per-row missing ``Value`` /
        ``DateTime`` is skipped. Cached 24h.
        """
        country_name = TE_COUNTRY_NAME_MAP.get(country_iso.upper())
        if country_name is None:
            msg = f"Unknown TE country mapping: {country_iso!r}"
            raise ValueError(msg)

        cache_key = (
            f"te_ind:{country_iso.upper()}:{indicator_name}:"
            f"{start_date.isoformat()}:{end_date.isoformat()}"
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug(
                "te.indicator.cache_hit",
                country=country_iso,
                indicator=indicator_name,
            )
            return list(cached)

        rows = await self._fetch_indicator_raw(country_name, indicator_name, start_date, end_date)
        self._call_count += 1
        log.info(
            "te.call",
            indicator=indicator_name,
            country=country_iso,
            cumulative_calls=self._call_count,
        )

        if not rows:
            err = f"TE returned empty series: country={country_iso!r} indicator={indicator_name!r}"
            raise DataUnavailableError(err)

        out: list[TEIndicatorObservation] = []
        for row in rows:
            raw_date = row.get("DateTime")
            raw_value = row.get("Value")
            if raw_date is None or raw_value is None:
                continue
            try:
                obs_date = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00")).date()
                val = float(raw_value)
            except (TypeError, ValueError):
                continue
            out.append(
                TEIndicatorObservation(
                    observation_date=obs_date,
                    value=val,
                    country=country_iso.upper(),
                    indicator=indicator_name,
                    frequency=str(row.get("Frequency", "")),
                )
            )
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        return out

    # -------------------------------------------------------------------
    # Telemetry
    # -------------------------------------------------------------------

    def get_call_count(self) -> int:
        """Return cumulative TE indicator-fetch calls this instance has made."""
        return self._call_count

    def reset_call_count(self) -> None:
        self._call_count = 0

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
