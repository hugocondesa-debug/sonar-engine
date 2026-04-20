"""Eurostat JSON-stat 2.0 connector for E1/E3/E4 EA inputs.

Per spec ``docs/specs/indices/economic/E{1,3,4}.md`` §2 + brief
``week5-sprint-2a`` §Commit 1: public Eurostat dissemination API
at ``https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1``.

Despite the URL path containing ``sdmx/2.1`` the default response when
``format=JSON`` is **JSON-stat 2.0** (``version: "2.0"``, ``class:
"dataset"``). It is *not* SDMX-JSON 1.0. We parse the JSON-stat shape
directly — no ``sdmx1`` or ``pyjstat`` dependency.

JSON-stat 2.0 layout (only the fields we touch):

- ``id``:   list of dimension ids in positional order. Time is usually last.
- ``size``: list of cardinalities — one per dimension. Single-select
            query dimensions have size 1; time has the period count.
- ``value``: flat dict ``{"<i>": <float|null>}`` indexed by the
             C-order linearized offset across all dims. For a query
             with all non-time dims single-select, ``value[i]``
             corresponds to the i-th time period.
- ``dimension.<id>.category.index``: label → positional index.

Schema-drift guard raises :class:`SchemaChangedError` when ``id`` or
``dimension`` keys disagree with the caller's expectations.

Dataflow keys follow the Eurostat positional dot-separated convention
(e.g. ``Q.CLV20_MEUR.SCA.B1GQ.DE`` for ``namq_10_gdp`` DE). Each
dataflow exposes a distinct dimension order; helpers in sub-
sequent commits assemble correct keys per dataflow.

Closes CAL-080.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

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

EUROSTAT_BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"

# EA aggregate geo code — composition changes with member count; 2023+ is EA20.
EA_GEO_CODE_PRE_2023 = "EA19"
EA_GEO_CODE_2023_PLUS = "EA20"


class SchemaChangedError(DataUnavailableError):
    """Raised when Eurostat JSON-stat shape deviates from the expected contract.

    Subclass of :class:`DataUnavailableError` so existing indices/overlays
    code that catches the base class can handle drift uniformly without
    special-casing the subtype.
    """


__all__ = [
    "EA_GEO_CODE_2023_PLUS",
    "EA_GEO_CODE_PRE_2023",
    "EUROSTAT_BASE_URL",
    "EurostatConnector",
    "EurostatObservation",
    "SchemaChangedError",
    "resolve_ea_geo_code",
]


def resolve_ea_geo_code(d: date) -> str:
    """Return the correct EA aggregate code for the given observation date.

    The composition of the Euro Area changes over time (EA19 ≤ 2022;
    EA20 ≥ 2023). This helper lets callers pass a canonical ``'EA'``
    token and have it resolved per data point.
    """
    if d.year <= 2022:
        return EA_GEO_CODE_PRE_2023
    return EA_GEO_CODE_2023_PLUS


@dataclass(frozen=True, slots=True)
class EurostatObservation:
    """Single time-indexed value returned by ``EurostatConnector.fetch_series``."""

    observation_date: date
    value: float
    dataflow: str
    geo: str
    time_period: str  # raw JSON-stat label (e.g. "2024-Q3", "2024-09")
    source: str = "EUROSTAT"
    status: str = ""  # e.g. "p" provisional, "e" estimate (empty if none)
    dimensions: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def _period_label_to_date(label: str) -> date:
    """Convert a JSON-stat time-period label to a calendar ``date``.

    Supports:
    - ``YYYY``         → December 31 of that year
    - ``YYYY-Qn``      → quarter-end (Mar-31 / Jun-30 / Sep-30 / Dec-31)
    - ``YYYY-MM``      → month-end
    - ``YYYY-MM-DD``   → that exact date
    """
    if len(label) == 4 and label.isdigit():
        return date(int(label), 12, 31)
    if "Q" in label:
        year_s, q_s = label.split("-Q")
        q = int(q_s)
        month = q * 3
        day = {3: 31, 6: 30, 9: 30, 12: 31}[month]
        return date(int(year_s), month, day)
    if len(label) == 7:  # YYYY-MM
        year_s, month_s = label.split("-")
        year = int(year_s)
        month = int(month_s)
        # Month-end via first-of-next-month minus one day.
        next_month = date(year + (month // 12), (month % 12) + 1, 1)
        return date.fromordinal(next_month.toordinal() - 1)
    # YYYY-MM-DD full ISO.
    return datetime.fromisoformat(label).date()


def _parse_jsonstat(  # noqa: PLR0912, PLR0915
    payload: dict[str, Any],
    *,
    expected_dataflow: str,
    expected_geo: str,
) -> list[EurostatObservation]:
    """Flatten a JSON-stat 2.0 single-series response into observations.

    Assumes every non-time dimension is single-select (size 1) — the
    helper method shape this connector exposes. If any non-time dim
    has size > 1 we'd need multi-series unpacking; not supported yet
    (and not needed by E1/E3/E4 inputs). Raises
    :class:`SchemaChangedError` on layout deviation.
    """
    try:
        dim_ids = payload["id"]
        dim_sizes = payload["size"]
        values = payload.get("value", {})
        statuses = payload.get("status", {})
        dim_meta = payload["dimension"]
    except KeyError as e:
        err = f"Eurostat response missing required key {e!r}"
        raise SchemaChangedError(err) from e

    if len(dim_ids) != len(dim_sizes):
        err = f"Eurostat dim/size length mismatch: ids={dim_ids} sizes={dim_sizes}"
        raise SchemaChangedError(err)

    if "time" not in dim_ids:
        err = f"Eurostat response missing time dimension: dims={dim_ids}"
        raise SchemaChangedError(err)
    time_dim_id = "time"
    if time_dim_id not in dim_meta:
        err = f"Eurostat response missing time dimension metadata: dims={dim_ids}"
        raise SchemaChangedError(err)

    time_meta = dim_meta[time_dim_id]
    try:
        time_index_map: dict[str, int] = time_meta["category"]["index"]
    except KeyError as e:
        err = f"Eurostat time dimension malformed: {e!r}"
        raise SchemaChangedError(err) from e

    # Invert to position → label.
    time_labels: dict[int, str] = {int(idx): label for label, idx in time_index_map.items()}

    # Non-time dims must all be single-select for our flat parse.
    for did, dsize in zip(dim_ids, dim_sizes, strict=True):
        if did == time_dim_id:
            continue
        if dsize != 1:
            err = f"Eurostat dim {did!r} has size {dsize}; expected single-select"
            raise SchemaChangedError(err)

    # Extract pinned dimension labels (for EurostatObservation provenance).
    pinned: list[tuple[str, str]] = []
    for did in dim_ids:
        if did == time_dim_id:
            continue
        try:
            idx_map = dim_meta[did]["category"]["index"]
        except KeyError:
            continue
        # Single-select → exactly one entry.
        label_text = next(iter(idx_map.keys()))
        pinned.append((did, label_text))

    observations: list[EurostatObservation] = []
    # value keys come as JSON strings; convert to int.
    for k, v in values.items():
        if v is None:
            continue
        pos = int(k)
        # With all non-time dims size-1, the linearized offset equals
        # the time index directly.
        label = time_labels.get(pos)
        if label is None:
            continue
        status_token = statuses.get(k, "") if isinstance(statuses, dict) else ""
        observations.append(
            EurostatObservation(
                observation_date=_period_label_to_date(label),
                value=float(v),
                dataflow=expected_dataflow,
                geo=expected_geo,
                time_period=label,
                status=status_token,
                dimensions=tuple(pinned),
            )
        )

    observations.sort(key=lambda o: o.observation_date)
    return observations


class EurostatConnector:
    """L0 connector for Eurostat dissemination JSON-stat API."""

    def __init__(
        self,
        cache_dir: str | Path,
        timeout: float = 30.0,
        rate_limit_seconds: float = 0.5,  # polite 2 req/s
    ) -> None:
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        self._rate_limit_seconds = rate_limit_seconds
        self._last_request_monotonic: float = 0.0

    async def _respect_rate_limit(self) -> None:
        import asyncio  # noqa: PLC0415

        if self._rate_limit_seconds <= 0:
            return
        loop = asyncio.get_event_loop()
        now = loop.time()
        elapsed = now - self._last_request_monotonic
        if elapsed < self._rate_limit_seconds:
            await asyncio.sleep(self._rate_limit_seconds - elapsed)
        self._last_request_monotonic = loop.time()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(
        self,
        dataflow: str,
        key: str,
        start_period: str,
        end_period: str,
    ) -> dict[str, Any]:
        url = f"{EUROSTAT_BASE_URL}/data/{dataflow}/{key}"
        params = {
            "startPeriod": start_period,
            "endPeriod": end_period,
            "format": "JSON",
        }
        await self._respect_rate_limit()
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        return dict(r.json())

    async def fetch_series(
        self,
        dataflow: str,
        geo: str,
        key: str,
        start_period: str,
        end_period: str,
    ) -> list[EurostatObservation]:
        """Fetch a single time series for ``(dataflow, geo, key)``.

        ``key`` is the positional dot-separated dataflow key (e.g.
        ``"Q.CLV20_MEUR.SCA.B1GQ.DE"``). Helper methods in
        :mod:`eurostat` assemble the right key per dataflow.

        ``start_period`` / ``end_period`` are JSON-stat period strings
        (e.g. ``"2024-01"``, ``"2024-Q1"``, ``"2024"``).
        """
        cache_key = f"eurostat:{dataflow}:{geo}:{key}:{start_period}:{end_period}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return list(cached)

        payload = await self._fetch_raw(dataflow, key, start_period, end_period)
        obs = _parse_jsonstat(payload, expected_dataflow=dataflow, expected_geo=geo)
        self.cache.set(cache_key, obs, ttl=DEFAULT_TTL_SECONDS)
        log.info("eurostat.fetched", dataflow=dataflow, geo=geo, n=len(obs))
        return obs

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
