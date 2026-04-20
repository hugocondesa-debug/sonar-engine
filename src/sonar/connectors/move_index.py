"""MOVE index live connector via Yahoo Finance chart API.

Per spec ``docs/specs/indices/financial/F3-risk-appetite.md`` §2 MOVE
is the canonical US bond-volatility input. MOVE is **not** on FRED
natively and ICE paid endpoints gate the direct feed, so we consume
the public Yahoo Finance chart endpoint for the ``^MOVE`` ticker.

Endpoint (public, no auth):

    GET https://query1.finance.yahoo.com/v7/finance/chart/^MOVE
        ?interval=1d&range=5y

Licensing: Yahoo Finance chart API is publicly accessible and is
consistent with the existing FRED-wrapped pattern (external compute
input, not redistributed raw). Attribution string: "MOVE index via
Yahoo Finance". See ``governance/LICENSING.md`` §7.

Closes CAL-061.
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

from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

log = structlog.get_logger()

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v7/finance/chart/%5EMOVE"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)

# MOVE typical range gate for canary / HALT #4. Outside this band the
# response likely contains a unit/scale error; caller should flag.
SANITY_MIN_LEVEL: float = 5.0
SANITY_MAX_LEVEL: float = 200.0

__all__ = [
    "DEFAULT_USER_AGENT",
    "SANITY_MAX_LEVEL",
    "SANITY_MIN_LEVEL",
    "YAHOO_CHART_URL",
    "MoveIndexConnector",
    "MoveObservation",
]


@dataclass(frozen=True, slots=True)
class MoveObservation:
    """MOVE observation — level in bps-annualized (e.g. 110.5)."""

    observation_date: date
    value_level: float
    source: str = "Yahoo"
    source_series_id: str = "^MOVE"


class MoveIndexConnector:
    """L0 connector for MOVE index via Yahoo Finance chart API."""

    def __init__(
        self,
        cache_dir: str | Path,
        timeout: float = 30.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "*/*"},
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(self, range_str: str = "5y") -> dict[str, Any]:
        params = {"interval": "1d", "range": range_str}
        r = await self.client.get(YAHOO_CHART_URL, params=params)
        r.raise_for_status()
        return cast("dict[str, Any]", r.json())

    @staticmethod
    def _parse_payload(payload: dict[str, Any]) -> list[MoveObservation]:
        """Extract ``list[MoveObservation]`` from Yahoo chart JSON.

        Raises :class:`DataUnavailableError` when the schema diverges
        (no ``chart.result[0].timestamp`` OR ``indicators.quote[0].close``).
        """
        try:
            result = payload["chart"]["result"][0]
            timestamps = result["timestamp"]
            closes = result["indicators"]["quote"][0]["close"]
        except (KeyError, IndexError, TypeError) as e:
            err = f"Yahoo MOVE chart schema drift: {e}"
            raise DataUnavailableError(err) from e

        if not timestamps or not closes or len(timestamps) != len(closes):
            err = "Yahoo MOVE chart returned empty or mis-aligned arrays"
            raise DataUnavailableError(err)

        out: list[MoveObservation] = []
        for ts, close in zip(timestamps, closes, strict=True):
            if close is None:
                continue
            try:
                obs_date = datetime.fromtimestamp(int(ts), tz=UTC).date()
            except (OSError, ValueError, TypeError):
                continue
            out.append(
                MoveObservation(
                    observation_date=obs_date,
                    value_level=float(close),
                )
            )
        return out

    async def fetch_move(
        self,
        start_date: date,
        end_date: date,
        *,
        range_str: str | None = None,
    ) -> list[MoveObservation]:
        """Return MOVE observations within ``[start_date, end_date]``.

        Yahoo endpoint accepts ``range`` shortcuts (``5d``, ``1mo``,
        ``3mo``, ``1y``, ``5y``, ``max``). ``range_str`` default picks
        the smallest window covering the request.
        """
        if range_str is None:
            span_days = (end_date - start_date).days
            if span_days <= 5:
                range_str = "1mo"
            elif span_days <= 90:
                range_str = "3mo"
            elif span_days <= 365:
                range_str = "1y"
            else:
                range_str = "5y"

        cache_key = f"move_yahoo:{range_str}:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("move.cache_hit", range=range_str)
            return cast("list[MoveObservation]", cached)

        payload = await self._fetch_raw(range_str=range_str)
        all_obs = self._parse_payload(payload)
        within = [o for o in all_obs if start_date <= o.observation_date <= end_date]
        self.cache.set(cache_key, within, ttl=DEFAULT_TTL_SECONDS)
        log.info("move.fetched", n=len(within), range=range_str)
        return within

    async def fetch_latest(
        self, observation_date: date, *, window_days: int = 14
    ) -> MoveObservation | None:
        """Return the most recent observation on or before ``observation_date``."""
        start = observation_date - timedelta(days=window_days)
        obs = await self.fetch_move(start, observation_date)
        usable = [o for o in obs if o.observation_date <= observation_date]
        if not usable:
            return None
        usable.sort(key=lambda o: o.observation_date)
        return usable[-1]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
