"""Sveriges Riksbank Swea public API L0 connector.

Empirical probe 2026-04-22 (Week 9 Sprint W-SE pre-flight): the Swea
JSON REST API at ``https://api.riksbank.se/swea/v1/`` is **public and
reachable** — HTTP 200 with no auth required for the historical
series. First Nordic-native connector in the monetary-cascade family.
The Riksbank also publishes an ``api-test.riksbank.se`` host that
appears to be a (slightly-lagged) cache of the same catalogue; the
canonical production host is the bare ``api.riksbank.se`` subdomain.

Canonical series codes (Swea catalogue ``GET /Series`` response; all
observed live during the Sprint W-SE probe):

* **SECBREPOEFF** — Riksbank policy rate ("styrränta"; called "repo
  rate" / "reporänta" prior to 2022-06-08 but the underlying 7-day
  deposit/borrowing instrument is continuous across the rename — Swea
  presents a single uninterrupted daily series 1994-06-01 → current).
  This is the cascade's M1 input; Swea label
  ``"Policy rate"``. Back-filled 8008 daily observations at probe time
  (2026-04-22), 1226 strictly-negative spanning 2015-02-18 →
  2020-01-07 (min -0.50 %).
* **SECBDEPOEFF** — Deposit rate (policy rate minus 0.75 pp; floor of
  the interest-rate corridor). Reserved for future M4 FCI SE corridor
  input (CAL-SE-M4-FCI).
* **SECBLENDEFF** — Lending rate (policy rate + 0.75 pp; ceiling of
  the interest-rate corridor). Reserved for future M4 FCI SE corridor
  input (CAL-SE-M4-FCI).

All observations are returned as ``list[Observation]`` per
``base.Observation`` with ``yield_bps = round(rate_pct * 100)`` per
``conventions/units.md`` §Spreads — negative values preserved
verbatim (no clamp, no sign flip).

Response schema (Sprint W-SE empirical probe):
```
[{"date": "2017-01-02", "value": -0.5}, {"date": "2017-01-03", "value": -0.5}, ...]
```

Callers in the monetary-indices cascade
(:mod:`sonar.indices.monetary.builders`) treat
:class:`DataUnavailableError` from this connector as a soft fail and
fall back to FRED OECD mirror per the Sprint W-SE cascade
(TE primary → Riksbank Swea native → FRED stale-flagged). Because the
FRED OECD SE mirror ``IRSTCI01SEM156N`` was **discontinued at
2020-10-01** (Sprint W-SE empirical probe — series frozen ~5.5 years),
Swea sits in a more load-bearing secondary slot than in prior
cascades — TE outages in the SE path largely fall through to Swea,
not FRED, because FRED is effectively dead for modern windows.
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
    "RIKSBANK_DEPOSIT_RATE",
    "RIKSBANK_LENDING_RATE",
    "RIKSBANK_POLICY_RATE",
    "RIKSBANK_SWEA_BASE_URL",
    "RiksbankConnector",
]

# Series-ID catalogue (Swea canonical; validated empirically during
# Sprint W-SE pre-flight, 2026-04-22). Kept public so tests + cascades
# can reference the series without magic strings.
RIKSBANK_POLICY_RATE: Final[str] = "SECBREPOEFF"
RIKSBANK_DEPOSIT_RATE: Final[str] = "SECBDEPOEFF"
RIKSBANK_LENDING_RATE: Final[str] = "SECBLENDEFF"

RIKSBANK_SWEA_BASE_URL: Final[str] = "https://api.riksbank.se/swea/v1"


class RiksbankConnector:
    """L0 connector for the Riksbank Swea public JSON REST API.

    Swea is public and scriptable — no auth, no anti-bot gate (Sprint
    W-SE empirical probe 2026-04-22). Responses are date-filterable
    via path segments (``/Observations/{seriesId}/{from}/{to}``),
    **not** query params. The API does enforce a soft rate limit
    (empirical ``HTTP 429 "Rate limit is exceeded. Try again in N
    seconds"`` observed during burst probes); tenacity's exponential
    jitter handles transient 429s cleanly at sprint scale.

    Slot in cascade: **secondary** behind TE primary for SE monetary
    inputs (see :func:`build_m1_se_inputs`). Returns results in the
    generic ``Observation`` shape so the builder resampler can consume
    them unchanged — critically, **negative values flow through
    verbatim** (no clamp, no sign flip) to preserve the 2015-2020
    Riksbank negative-rate corridor that Sprint W-SE's
    ``SE_NEGATIVE_RATE_ERA_DATA`` cascade flag annotates.
    """

    BASE_URL: Final[str] = RIKSBANK_SWEA_BASE_URL
    CACHE_NAMESPACE: Final[str] = "riksbank_swea"
    CONNECTOR_ID: Final[str] = "riksbank"

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
    ) -> list[dict[str, Any]]:
        """Hit Swea ``/Observations/{series_id}/{from}/{to}``."""
        url = f"{self.BASE_URL}/Observations/{series_id}/{start.isoformat()}/{end.isoformat()}"
        r = await self.client.get(url)
        r.raise_for_status()
        payload = r.json()
        return cast("list[dict[str, Any]]", payload or [])

    async def fetch_series(
        self,
        series_id: str,
        start: date,
        end: date,
    ) -> list[Observation]:
        """Return parsed observations for ``(series_id, start, end)``. Cached 24h.

        Empty list or HTTP error raises :class:`DataUnavailableError`;
        upstream cascade callers treat that as soft-fail and fall back
        to FRED OECD mirror per the Sprint W-SE cascade contract.
        """
        cache_key = f"{self.CACHE_NAMESPACE}:{series_id}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("riksbank.cache_hit", series=series_id)
            return list(cached)

        try:
            rows = await self._fetch_raw(series_id, start, end)
        except (httpx.HTTPError, RetryError) as exc:
            msg = f"Riksbank Swea series={series_id!r} HTTP error: {exc}"
            raise DataUnavailableError(msg) from exc

        if not rows:
            msg = f"Riksbank Swea returned empty observations: series={series_id!r}"
            raise DataUnavailableError(msg)

        out: list[Observation] = []
        for row in rows:
            raw_date = row.get("date")
            raw_value = row.get("value")
            if not raw_date or raw_value is None:
                continue
            try:
                obs_date = datetime.strptime(str(raw_date), "%Y-%m-%d").replace(tzinfo=UTC).date()
                value_pct = float(raw_value)
            except (TypeError, ValueError):
                continue
            out.append(
                Observation(
                    country_code="SE",
                    observation_date=obs_date,
                    tenor_years=0.01,
                    # round() preserves sign naturally for negative rates:
                    # -0.50 % → -50 bps without clamp.
                    yield_bps=round(value_pct * 100),
                    source="RIKSBANK",
                    source_series_id=series_id,
                )
            )
        if not out:
            msg = f"Riksbank Swea series={series_id!r}: all rows unparseable"
            raise DataUnavailableError(msg)
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        log.info("riksbank.fetched", series=series_id, n=len(out))
        return out

    async def fetch_policy_rate(self, start: date, end: date) -> list[Observation]:
        """Riksbank policy rate — series :data:`RIKSBANK_POLICY_RATE` (SECBREPOEFF).

        This is the Riksbank styrränta (called "repo rate" / reporänta
        pre-2022-06-08; continuous daily series across the rename).
        SECBREPOEFF is the canonical daily series the monetary cascade
        consumes as the SE native secondary behind TE primary.

        Named ``fetch_policy_rate`` to stay consistent with the GB /
        JP / CA / AU / NZ / CH cascade vocabulary (``fetch_bank_rate``
        / ``fetch_ocr`` / ``fetch_cash_rate`` / ``fetch_policy_rate``
        — the M1 cascade slot is the same regardless of country label).
        """
        return await self.fetch_series(RIKSBANK_POLICY_RATE, start, end)

    async def fetch_deposit_rate(self, start: date, end: date) -> list[Observation]:
        """Riksbank deposit rate — series :data:`RIKSBANK_DEPOSIT_RATE`.

        Floor of the interest-rate corridor; policy rate minus 0.75 pp.
        Reserved for future M4 FCI SE corridor input (CAL-SE-M4-FCI).
        """
        return await self.fetch_series(RIKSBANK_DEPOSIT_RATE, start, end)

    async def fetch_lending_rate(self, start: date, end: date) -> list[Observation]:
        """Riksbank lending rate — series :data:`RIKSBANK_LENDING_RATE`.

        Ceiling of the interest-rate corridor; policy rate + 0.75 pp.
        Reserved for future M4 FCI SE corridor input (CAL-SE-M4-FCI).
        """
        return await self.fetch_series(RIKSBANK_LENDING_RATE, start, end)

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
