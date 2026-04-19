"""FRED (Federal Reserve Economic Data) L0 connector — US Treasury yields.

Layered API:

- ``fetch_series(series_id, start, end)`` — generic low-level; any series in
  ``FRED_SERIES_TENORS`` (nominal DGS* + linker DFII*).
- ``fetch_yield_curve_nominal(country, observation_date)`` — domain wrapper;
  returns ``{tenor_label: Observation}`` for US nominal Treasuries.
- ``fetch_yield_curve_linker(country, observation_date)`` — domain wrapper;
  TIPS counterpart (DFII5/7/10/20/30).

Observation values stay in bps per units.md §Spreads; overlays convert to
decimal at the L0→L2 boundary (``Observation.yield_bps / 10_000``).
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.base import BaseConnector, Observation
from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache

log = structlog.get_logger()

# US nominal Treasury constant maturity series.
FRED_US_NOMINAL_SERIES: dict[str, str] = {
    "1M": "DGS1MO",
    "3M": "DGS3MO",
    "6M": "DGS6MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "3Y": "DGS3",
    "5Y": "DGS5",
    "7Y": "DGS7",
    "10Y": "DGS10",
    "20Y": "DGS20",
    "30Y": "DGS30",
}

# US TIPS (inflation-indexed) series — Fed publishes 5Y+ only; short-end TIPS
# liquidity is too thin. This caps real-curve direct-linker fit at 5 tenors,
# below MIN_OBSERVATIONS=6 per spec §6 (see CAL-033).
FRED_US_LINKER_SERIES: dict[str, str] = {
    "5Y": "DFII5",
    "7Y": "DFII7",
    "10Y": "DFII10",
    "20Y": "DFII20",
    "30Y": "DFII30",
}

# Combined series_id → tenor_years lookup for the generic fetch_series path.
FRED_SERIES_TENORS: dict[str, float] = {
    "DGS1MO": 1 / 12,
    "DGS3MO": 0.25,
    "DGS6MO": 0.5,
    "DGS1": 1.0,
    "DGS2": 2.0,
    "DGS3": 3.0,
    "DGS5": 5.0,
    "DGS7": 7.0,
    "DGS10": 10.0,
    "DGS20": 20.0,
    "DGS30": 30.0,
    "DFII5": 5.0,
    "DFII7": 7.0,
    "DFII10": 10.0,
    "DFII20": 20.0,
    "DFII30": 30.0,
}

# Back-compat alias for Week 1 nominal-only callers.
FRED_US_TENORS: dict[str, float] = {
    sid: FRED_SERIES_TENORS[sid] for sid in FRED_US_NOMINAL_SERIES.values()
}


class FredConnector(BaseConnector):
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str, cache_dir: str | Path, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(self, series_id: str, start: date, end: date) -> dict[str, Any]:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
        }
        r = await self.client.get(self.BASE_URL, params=params)
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        return data

    async def fetch_series(self, series_id: str, start: date, end: date) -> list[Observation]:
        cache_key = f"fred:{series_id}:{start.isoformat()}:{end.isoformat()}"
        cached_raw = self.cache.get(cache_key)
        if cached_raw is not None:
            log.debug("fred.cache_hit", series=series_id)
            return cast("list[Observation]", cached_raw)

        tenor = FRED_SERIES_TENORS.get(series_id)
        if tenor is None:
            msg = f"Unknown FRED series mapping: {series_id}"
            raise ValueError(msg)

        raw = await self._fetch_raw(series_id, start, end)
        observations: list[Observation] = []
        for obs in raw.get("observations", []):
            if obs["value"] == ".":
                continue
            observations.append(
                Observation(
                    country_code="US",
                    observation_date=datetime.fromisoformat(obs["date"]).date(),
                    tenor_years=tenor,
                    yield_bps=round(float(obs["value"]) * 100),
                    source="FRED",
                    source_series_id=series_id,
                )
            )

        self.cache.set(cache_key, observations, ttl=DEFAULT_TTL_SECONDS)
        log.info("fred.fetched", series=series_id, n=len(observations))
        return observations

    async def _fetch_curve(
        self,
        series_map: dict[str, str],
        country: str,
        observation_date: date,
    ) -> dict[str, Observation]:
        """Fetch a yield curve family (nominal or linker) on a single date.

        Window spans ``observation_date ± 5`` business days so sparse series
        (e.g. weekends, DFII*) still return the closest available observation.
        Returns ``{tenor_label: Observation}`` for every series that yielded a
        non-empty observation on ``observation_date`` or the most recent
        predecessor inside the window. Series with no obs in window are
        simply omitted (caller decides how to handle gaps).
        """
        if country != "US":
            msg = f"FRED connector only supports country=US; got {country}"
            raise ValueError(msg)

        window_days = 7
        start = observation_date - timedelta(days=window_days)
        end = observation_date

        out: dict[str, Observation] = {}
        for tenor_label, series_id in series_map.items():
            obs_list = await self.fetch_series(series_id, start, end)
            usable = [o for o in obs_list if o.observation_date <= observation_date]
            if not usable:
                continue
            usable.sort(key=lambda o: o.observation_date)
            out[tenor_label] = usable[-1]
        return out

    async def fetch_yield_curve_nominal(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        """Return ``{tenor_label: Observation}`` for US nominal Treasuries."""
        return await self._fetch_curve(FRED_US_NOMINAL_SERIES, country, observation_date)

    async def fetch_yield_curve_linker(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        """Return ``{tenor_label: Observation}`` for US TIPS (DFII*)."""
        return await self._fetch_curve(FRED_US_LINKER_SERIES, country, observation_date)

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
