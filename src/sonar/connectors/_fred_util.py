"""Shared FRED fetch helper for level/ratio/index series.

The existing :mod:`sonar.connectors.fred` layer is yield-curve oriented
(Observation carries ``yield_bps``). F-cycle connectors (CBOE, ICE BofA
OAS, Chicago NFCI, FINRA margin, etc.) need to fetch FRED series that
are raw levels (VIX, NFCI z-score) or ratios (FRED margin-to-GDP).
Rather than stretching :class:`Observation`, this helper returns
plain ``(date, value_float)`` pairs from the canonical
``/fred/series/observations`` endpoint; each F-cycle connector wraps
the result in a domain-specific dataclass.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

if TYPE_CHECKING:
    from datetime import date

    from sonar.connectors.cache import ConnectorCache

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=60),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
)
async def _fetch_raw(
    client: httpx.AsyncClient,
    series_id: str,
    api_key: str,
    start: date,
    end: date,
) -> dict[str, Any]:
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat(),
    }
    r = await client.get(FRED_BASE_URL, params=params)
    r.raise_for_status()
    return cast("dict[str, Any]", r.json())


async def fetch_fred_values(
    client: httpx.AsyncClient,
    cache: ConnectorCache,
    *,
    series_id: str,
    api_key: str,
    start: date,
    end: date,
    cache_prefix: str = "fred_series",
) -> list[tuple[date, float]]:
    """Return ``[(observation_date, raw_float_value), ...]`` for a FRED series.

    Skips rows whose ``value == "."`` (FRED sentinel for "not published").
    Cached with 24h TTL by default per ``ConnectorCache.set`` defaults.
    """
    cache_key = f"{cache_prefix}:{series_id}:{start.isoformat()}:{end.isoformat()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cast("list[tuple[date, float]]", cached)

    raw = await _fetch_raw(client, series_id, api_key, start, end)
    out: list[tuple[date, float]] = []
    for obs in raw.get("observations", []):
        raw_val = obs.get("value")
        if raw_val in (None, "", "."):
            continue
        try:
            value = float(raw_val)
        except (TypeError, ValueError):
            continue
        try:
            obs_date = datetime.fromisoformat(obs["date"]).date()
        except (KeyError, ValueError):
            continue
        out.append((obs_date, value))

    cache.set(cache_key, out)
    return out
