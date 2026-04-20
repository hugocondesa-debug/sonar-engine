"""Yahoo Finance chart-API connector — generic daily-close fetcher.

Exposes :class:`YahooFinanceConnector.fetch_chart(symbol, range_str)`
for any Yahoo ticker accepted by the public
``query1.finance.yahoo.com/v7/finance/chart/{symbol}`` endpoint, plus
pre-wired wrappers for symbols we consume from other modules
(e.g. ``^CPC`` for the CBOE equity put/call ratio).

Distinct module from :mod:`sonar.connectors.move_index` — that module
shipped earlier (Week 5 Sprint 1) with a MOVE-specific dataclass and
sanity band. It stays untouched for backward-compat; this module is
the future-proof generic path. A later refactor can migrate MOVE to
consume this module.

Licensing: Yahoo Finance chart API is publicly accessible. Requests
require a browser-class User-Agent (bare curl UA → 403/429).
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

YAHOO_CHART_BASE_URL = "https://query1.finance.yahoo.com/v7/finance/chart"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)

# CBOE equity put/call ratio — Yahoo ticker. The caret (``^``) marks
# an index-family symbol; HTTP-encoded as ``%5E`` on the wire (httpx
# encodes automatically).
YAHOO_SYMBOL_PUT_CALL = "^CPC"

# Put/call ratio sanity band — historical daily readings sit in
# [0.3, 3.0]; anything outside is suspicious.
PUT_CALL_SANITY_MIN = 0.3
PUT_CALL_SANITY_MAX = 3.0


@dataclass(frozen=True, slots=True)
class YahooObservation:
    """Generic daily close observation from the Yahoo chart API."""

    observation_date: date
    value_close: float
    symbol: str
    source: str = "YAHOO"


__all__ = [
    "DEFAULT_USER_AGENT",
    "PUT_CALL_SANITY_MAX",
    "PUT_CALL_SANITY_MIN",
    "YAHOO_CHART_BASE_URL",
    "YAHOO_SYMBOL_PUT_CALL",
    "YahooFinanceConnector",
    "YahooObservation",
]


def _pick_range(span_days: int) -> str:
    """Map a calendar-day span to the smallest Yahoo range shortcut that covers it."""
    if span_days <= 5:
        return "1mo"
    if span_days <= 90:
        return "3mo"
    if span_days <= 365:
        return "1y"
    if span_days <= 5 * 365:
        return "5y"
    return "max"


class YahooFinanceConnector:
    """L0 connector for the public Yahoo Finance chart API.

    Single generic ``fetch_chart`` path + thin wrappers per symbol we
    intentionally depend on. Designed to be extended as more Yahoo-
    hosted series become primary data sources (current: put/call
    ratio for F4 positioning).
    """

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
    async def _fetch_raw(self, symbol: str, range_str: str) -> dict[str, Any]:
        url = f"{YAHOO_CHART_BASE_URL}/{symbol}"
        params = {"interval": "1d", "range": range_str}
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        return cast("dict[str, Any]", r.json())

    @staticmethod
    def _parse_payload(payload: dict[str, Any], symbol: str) -> list[YahooObservation]:
        """Extract daily closes from the Yahoo chart JSON envelope.

        Raises :class:`DataUnavailableError` when the schema diverges
        (missing ``chart.result[0].timestamp`` or ``indicators.quote[0].close``).
        """
        try:
            result = payload["chart"]["result"][0]
            timestamps = result["timestamp"]
            closes = result["indicators"]["quote"][0]["close"]
        except (KeyError, IndexError, TypeError) as e:
            err = f"Yahoo chart schema drift for {symbol!r}: {e}"
            raise DataUnavailableError(err) from e

        if not timestamps or not closes or len(timestamps) != len(closes):
            err = f"Yahoo chart returned empty or mis-aligned arrays for {symbol!r}"
            raise DataUnavailableError(err)

        out: list[YahooObservation] = []
        for ts, close in zip(timestamps, closes, strict=True):
            if close is None:
                continue
            try:
                obs_date = datetime.fromtimestamp(int(ts), tz=UTC).date()
            except (OSError, ValueError, TypeError):
                continue
            out.append(
                YahooObservation(
                    observation_date=obs_date,
                    value_close=float(close),
                    symbol=symbol,
                )
            )
        return out

    async def fetch_chart(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        *,
        range_str: str | None = None,
    ) -> list[YahooObservation]:
        """Return daily closes for ``symbol`` within ``[start_date, end_date]``.

        ``range_str`` defaults to the smallest Yahoo range shortcut that
        covers ``end_date - start_date`` (``1mo`` / ``3mo`` / ``1y`` /
        ``5y`` / ``max``). The full range payload is fetched once per
        ``(symbol, range_str)`` tuple and trimmed client-side to the
        requested window before return.
        """
        if range_str is None:
            range_str = _pick_range((end_date - start_date).days)

        cache_key = f"yahoo:{symbol}:{range_str}:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("yahoo.cache_hit", symbol=symbol, range=range_str)
            return cast("list[YahooObservation]", cached)

        payload = await self._fetch_raw(symbol, range_str)
        all_obs = self._parse_payload(payload, symbol)
        within = [o for o in all_obs if start_date <= o.observation_date <= end_date]
        self.cache.set(cache_key, within, ttl=DEFAULT_TTL_SECONDS)
        log.info("yahoo.fetched", symbol=symbol, range=range_str, n=len(within))
        return within

    async def fetch_put_call_ratio_us(
        self, start_date: date, end_date: date
    ) -> list[YahooObservation]:
        """CBOE Equity Put/Call Ratio via Yahoo ``^CPC`` symbol.

        Daily close. Source: CBOE. Substitutes FRED ``PUTCLSPX`` which
        CBOE delisted from FRED (CAL-073 resolution). Each observation
        carries ``symbol="^CPC"``.
        """
        return await self.fetch_chart(YAHOO_SYMBOL_PUT_CALL, start_date, end_date)

    async def fetch_latest_put_call(
        self, observation_date: date, *, window_days: int = 14
    ) -> YahooObservation | None:
        """Return the most recent put/call close on or before ``observation_date``."""
        start = observation_date - timedelta(days=window_days)
        obs = await self.fetch_put_call_ratio_us(start, observation_date)
        usable = [o for o in obs if o.observation_date <= observation_date]
        if not usable:
            return None
        usable.sort(key=lambda o: o.observation_date)
        return usable[-1]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
