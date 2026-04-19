"""FRED (Federal Reserve Economic Data) L0 connector — US Treasury yields."""

from datetime import date, datetime
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

# US Treasury constant maturity series → tenor_years.
# Source: docs/data_sources/D2_empirical_validation.md (validated).
FRED_US_TENORS: dict[str, float] = {
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

        tenor = FRED_US_TENORS.get(series_id)
        if tenor is None:
            msg = f"Unknown FRED series mapping: {series_id}"
            raise ValueError(msg)

        raw = await self._fetch_raw(series_id, start, end)
        observations: list[Observation] = []
        for obs in raw.get("observations", []):
            if obs["value"] == ".":  # FRED sentinel for missing
                continue
            observations.append(
                Observation(
                    country_code="US",
                    observation_date=datetime.fromisoformat(obs["date"]).date(),
                    tenor_years=tenor,
                    yield_bps=round(float(obs["value"]) * 100),  # pct → bps
                    source="FRED",
                    source_series_id=series_id,
                )
            )

        self.cache.set(cache_key, observations, ttl=DEFAULT_TTL_SECONDS)
        log.info("fred.fetched", series=series_id, n=len(observations))
        return observations

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
