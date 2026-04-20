"""CFTC Commitments of Traders (COT) connector via Socrata JSON API.

Per spec ``docs/specs/indices/financial/F4-positioning.md`` §2 + brief
§Commit 3: non-commercial long/short positions for E-MINI S&P 500
futures, weekly Tuesday as-of, Friday release (3-day lag).

Endpoint: https://publicreporting.cftc.gov/resource/6dca-aqww.json
(Socrata Open Data API; public, no auth). Filter by
``market_and_exchange_names LIKE 'E-MINI S&P 500%'`` for SP500 series.

Closes CAL-070.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()

CFTC_JSON_API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
# Socrata $where LIKE pattern — literal string; httpx handles URL-encoding.
# `%` is the SQL wildcard; `&` must stay literal (do NOT URL-encode here).
SP500_MARKET_FILTER = "E-MINI S&P 500%"

# Expected Socrata field names (HALT #3 guard). If field names change we
# raise DataUnavailableError so the consumer emits the degraded flag.
REQUIRED_FIELDS: tuple[str, ...] = (
    "report_date_as_yyyy_mm_dd",
    "market_and_exchange_names",
    "noncomm_positions_long_all",
    "noncomm_positions_short_all",
)

__all__ = [
    "CFTC_JSON_API",
    "REQUIRED_FIELDS",
    "SP500_MARKET_FILTER",
    "CftcCotConnector",
    "CotObservation",
]


@dataclass(frozen=True, slots=True)
class CotObservation:
    """COT non-commercial net position for a futures contract."""

    observation_date: date  # Tuesday as-of date
    contract: str  # e.g. "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE"
    noncomm_long: int
    noncomm_short: int
    source: str = "CFTC"

    @property
    def noncomm_net(self) -> int:
        return self.noncomm_long - self.noncomm_short


class CftcCotConnector:
    """L0 connector for CFTC COT via Socrata JSON API."""

    def __init__(
        self,
        cache_dir: str | Path,
        timeout: float = 30.0,
    ) -> None:
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(self, *, market_filter: str, limit: int = 104) -> list[dict[str, Any]]:
        """Query Socrata for latest ``limit`` rows matching ``market_filter``.

        ``limit=104`` covers ~2 years of weekly data.
        """
        params = {
            "$where": f"market_and_exchange_names like '{market_filter}'",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": str(limit),
        }
        r = await self.client.get(CFTC_JSON_API, params=params)
        r.raise_for_status()
        payload = r.json()
        if not isinstance(payload, list):
            err = f"CFTC Socrata returned non-list payload: {type(payload).__name__}"
            raise DataUnavailableError(err)
        return cast("list[dict[str, Any]]", payload)

    @staticmethod
    def _parse_rows(rows: list[dict[str, Any]]) -> list[CotObservation]:
        """Parse Socrata rows into CotObservations.

        Raises :class:`DataUnavailableError` when any row is missing a
        required field (HALT #3 schema-drift guard).
        """
        out: list[CotObservation] = []
        for row in rows:
            for field in REQUIRED_FIELDS:
                if field not in row:
                    err = f"CFTC Socrata schema drift: missing field {field!r}"
                    raise DataUnavailableError(err)
            try:
                dt_str = row["report_date_as_yyyy_mm_dd"]
                obs_date = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).date()
                noncomm_long = int(row["noncomm_positions_long_all"])
                noncomm_short = int(row["noncomm_positions_short_all"])
            except (ValueError, TypeError, AttributeError) as e:
                err = f"CFTC row parse error: {e}; row={row}"
                raise DataUnavailableError(err) from e
            out.append(
                CotObservation(
                    observation_date=obs_date,
                    contract=row["market_and_exchange_names"],
                    noncomm_long=noncomm_long,
                    noncomm_short=noncomm_short,
                )
            )
        return out

    async def fetch_cot_sp500_net(
        self, start_date: date, end_date: date, *, limit: int = 104
    ) -> list[CotObservation]:
        """Return E-MINI S&P 500 non-commercial positions within range."""
        cache_key = f"cftc_cot_sp500:{start_date.isoformat()}:{end_date.isoformat()}:{limit}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return list(cached)
        rows = await self._fetch_raw(market_filter=SP500_MARKET_FILTER, limit=limit)
        all_obs = self._parse_rows(rows)
        within = [o for o in all_obs if start_date <= o.observation_date <= end_date]
        within.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, within, ttl=DEFAULT_TTL_SECONDS)
        log.info("cftc_cot.fetched", n=len(within))
        return within

    async def fetch_latest_sp500(
        self, observation_date: date, *, window_days: int = 30
    ) -> CotObservation | None:
        """Return the latest observation on or before ``observation_date``.

        Default window 30 days absorbs CFTC's weekly cadence + 3-day
        release lag + occasional holiday delay.
        """
        start = observation_date - timedelta(days=window_days)
        obs = await self.fetch_cot_sp500_net(start, observation_date)
        usable = [o for o in obs if o.observation_date <= observation_date]
        if not usable:
            return None
        usable.sort(key=lambda o: o.observation_date)
        return usable[-1]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
