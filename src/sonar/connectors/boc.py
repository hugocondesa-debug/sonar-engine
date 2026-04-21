"""Bank of Canada (BoC) Valet public API L0 connector.

Empirical probe 2026-04-21 (Week 9 Sprint S pre-flight): the Valet
JSON REST API at ``https://www.bankofcanada.ca/valet/observations/``
is **public and reachable** — HTTP 200 on `V39079` with no auth and
standard JSON payload. This is the first native connector in the
monetary-cascade family (BoE IADB / BoJ TSD both gated) that lands as
a first-class scriptable secondary behind TE primary.

Canonical series codes (Valet catalogue; all observed live during the
Sprint S probe):

* **V39079** — Target for the overnight rate (BoC policy rate). This
  is the cascade's M1 input; label ``"Target for the overnight rate"``
  per the Valet ``seriesDetail``.
* **BD.CDN.10YR.DQ.YLD** — 10-year benchmark Government of Canada bond
  yield (daily); Valet label ``"10 year | Government of Canada
  benchmark bond yields"``. Landing point for M4 FCI CA 10Y input
  (CAL-131 — deferred Sprint S).

All observations are returned as ``list[Observation]`` per
``base.Observation`` with ``yield_bps = int(round(rate_pct * 100))``
per ``conventions/units.md`` §Spreads.

Response schema (Sprint S empirical probe):
```
{
    "terms": {"url": "https://www.bankofcanada.ca/terms/"},
    "seriesDetail": {"V39079": {"label": ..., "description": ...}},
    "observations": [{"d": "2026-04-20", "V39079": {"v": "2.25"}}],
}
```

Callers in the monetary-indices cascade
(:mod:`sonar.indices.monetary.builders`) treat
:class:`DataUnavailableError` from this connector as a soft fail and
fall back to FRED OECD mirror per the Sprint S cascade (TE primary →
BoC Valet native → FRED stale-flagged).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, cast

import httpx
import structlog
from tenacity import (
    RetryError,
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

__all__ = [
    "BOC_GOC_10Y",
    "BOC_OVERNIGHT_TARGET",
    "BOC_VALET_BASE_URL",
    "BoCConnector",
]

# Series-ID catalogue (BoC Valet canonical; validated empirically during
# Sprint S pre-flight, 2026-04-21). Kept public so tests + cascades can
# reference the series without magic strings.
BOC_OVERNIGHT_TARGET: Final[str] = "V39079"
BOC_GOC_10Y: Final[str] = "BD.CDN.10YR.DQ.YLD"

BOC_VALET_BASE_URL: Final[str] = "https://www.bankofcanada.ca/valet"


class BoCConnector:
    """L0 connector for BoC Valet public JSON REST API.

    Valet is public and scriptable — no auth, no anti-bot gate (Sprint
    S empirical probe 2026-04-21). Responses are date-filterable via
    ``start_date`` / ``end_date`` query params.

    Slot in cascade: **secondary** behind TE primary for CA monetary
    inputs (see :func:`build_m1_ca_inputs`). Returns results in the
    generic ``Observation`` shape so the builder resampler can consume
    them unchanged.
    """

    BASE_URL: Final[str] = BOC_VALET_BASE_URL
    CACHE_NAMESPACE: Final[str] = "boc_valet"
    CONNECTOR_ID: Final[str] = "boc"

    def __init__(
        self,
        cache_dir: str | Path,
        timeout: float = 30.0,
    ) -> None:
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "SONAR/2.0 (monetary-cascade; contact hugocondesa@pm.me)",
                "Accept": "application/json",
            },
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(
        self,
        series_id: str,
        start: date,
        end: date,
    ) -> dict[str, Any]:
        """Hit Valet ``/observations/{series_id}`` with date filters."""
        url = f"{self.BASE_URL}/observations/{series_id}"
        params = {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        payload = r.json()
        return cast("dict[str, Any]", payload or {})

    async def fetch_series(
        self,
        series_id: str,
        start: date,
        end: date,
    ) -> list[Observation]:
        """Return parsed observations for ``(series_id, start, end)``. Cached 24h.

        Empty ``observations`` or HTTP error raises
        :class:`DataUnavailableError`; upstream cascade callers treat
        that as soft-fail and fall back to FRED OECD mirror.
        """
        cache_key = f"{self.CACHE_NAMESPACE}:{series_id}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("boc.cache_hit", series=series_id)
            return list(cached)

        try:
            payload = await self._fetch_raw(series_id, start, end)
        except (httpx.HTTPError, RetryError) as exc:
            msg = f"BoC Valet series={series_id!r} HTTP error: {exc}"
            raise DataUnavailableError(msg) from exc

        rows = payload.get("observations") or []
        if not rows:
            msg = f"BoC Valet returned empty observations: series={series_id!r}"
            raise DataUnavailableError(msg)

        out: list[Observation] = []
        for row in rows:
            raw_date = row.get("d")
            series_cell = row.get(series_id)
            if not raw_date or not isinstance(series_cell, dict):
                continue
            raw_value = series_cell.get("v")
            if raw_value is None or raw_value == "":
                continue
            try:
                obs_date = datetime.strptime(str(raw_date), "%Y-%m-%d").replace(tzinfo=UTC).date()
                value_pct = float(raw_value)
            except (TypeError, ValueError):
                continue
            out.append(
                Observation(
                    country_code="CA",
                    observation_date=obs_date,
                    tenor_years=0.01,
                    yield_bps=round(value_pct * 100),
                    source="BOC",
                    source_series_id=series_id,
                )
            )
        if not out:
            msg = f"BoC Valet series={series_id!r}: all rows unparseable"
            raise DataUnavailableError(msg)
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        log.info("boc.fetched", series=series_id, n=len(out))
        return out

    async def fetch_bank_rate(self, start: date, end: date) -> list[Observation]:
        """Target for the overnight rate — series :data:`BOC_OVERNIGHT_TARGET`.

        This is the BoC policy rate; V39079 is the canonical daily
        series the monetary cascade consumes. Named ``fetch_bank_rate``
        to stay consistent with the GB/JP cascade vocabulary (the M1
        cascade slot is the same regardless of country).
        """
        return await self.fetch_series(BOC_OVERNIGHT_TARGET, start, end)

    async def fetch_goc_10y(self, start: date, end: date) -> list[Observation]:
        """10Y benchmark Government of Canada bond yield — series :data:`BOC_GOC_10Y`."""
        return await self.fetch_series(BOC_GOC_10Y, start, end)

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
