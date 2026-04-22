"""Norges Bank DataAPI L0 connector (SDMX-JSON REST).

Empirical probe 2026-04-22 (Week 9 Sprint X-NO pre-flight): the Norges
Bank DataAPI at ``https://data.norges-bank.no/api/data/{dataflow}/{key}``
serves **SDMX-JSON** responses for every dataflow in its public
catalogue. The endpoint is public + scriptable + unscreened — a plain
``curl`` with ``Accept: application/vnd.sdmx.data+json`` clears with
no auth and no anti-bot gate. This is the second native connector in
the monetary-cascade family (alongside BoC Valet JSON REST — Sprint S)
with a first-class reachable secondary slot; the SDMX-JSON transport
shape is a deliberate choice by Norges Bank and matches the ECB SDW
philosophy (vs. the BoC / RBA / SNB shape which is JSON REST or CSV).

Canonical dataflows + series keys (all observed live during the Sprint
X-NO probe):

* **``IR`` / ``B.KPRA.SD.R``** — Key policy rate (sight deposit rate).
  Daily cadence back to 1991-01-01; 1586 observations between
  2020-01-02 → 2026-04-20 at probe. This is the cascade's M1 input;
  the key dimensions are ``FREQ=B`` (Business), ``INSTRUMENT_TYPE=KPRA``
  (Key policy rate), ``TENOR=SD`` (policy rate), ``UNIT_MEASURE=R``
  (Rate).
* **``GOVT_GENERIC_RATES`` / ``B.10Y.GBON``** — 10Y generic government
  bond yield (constant-maturity). Daily cadence back to ~2000 as a
  derived "generic yield" on the closest-maturity bond for each date.
  Landing point for M4 FCI NO 10Y input (CAL-NO-M4-FCI — deferred
  Sprint X-NO).

SDMX-JSON shape (both dataflows):

```
{
    "meta": {...},
    "data": {
        "dataSets": [{"series": {"<dim-key>": {"observations": {"<obs-idx>": ["<value>"]}}}}],
        "structure": {
            "dimensions": {
                "series": [{"id": "FREQ", "values": [...]}, ...],
                "observation": [{"id": "TIME_PERIOD", "values": [{"id": "YYYY-MM-DD", ...}]}]
            }
        }
    }
}
```

The ``series`` dict is keyed by colon-joined dimension indices (e.g.
``"0:0:0:0"`` for the policy-rate flow). Within a single flow the
series index is stable across calls — when the caller pins all series
dimensions via the resource key (e.g. ``B.KPRA.SD.R``) the response
contains exactly one series and the colon-indexed key is always
``0:0:0:0``.

All observations are returned as ``list[Observation]`` per
``base.Observation`` with ``yield_bps = int(round(rate_pct * 100))``
per ``conventions/units.md`` §Spreads. Norway never ran a negative
policy rate — empirical Sprint X-NO probe confirmed ``min = 0 %``
across the full 35Y history. The connector preserves whatever sign
the API returns (there is no clamp); negatives would flow through
unchanged if they ever appeared.

Callers in the monetary-indices cascade
(:mod:`sonar.indices.monetary.builders`) treat
:class:`DataUnavailableError` from this connector as a soft fail and
fall back to FRED OECD mirror per the Sprint X-NO cascade (TE primary
→ Norges Bank DataAPI native → FRED stale-flagged).
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
    "NORGESBANK_BASE_URL",
    "NORGESBANK_GBON_10Y_FLOW",
    "NORGESBANK_GBON_10Y_KEY",
    "NORGESBANK_POLICY_RATE_FLOW",
    "NORGESBANK_POLICY_RATE_KEY",
    "NORGESBANK_USER_AGENT",
    "NorgesBankConnector",
]

# Dataflow + series-key catalogue (Norges Bank canonical; validated
# empirically during Sprint X-NO pre-flight, 2026-04-22).
NORGESBANK_POLICY_RATE_FLOW: Final[str] = "IR"
NORGESBANK_POLICY_RATE_KEY: Final[str] = "B.KPRA.SD.R"
NORGESBANK_GBON_10Y_FLOW: Final[str] = "GOVT_GENERIC_RATES"
NORGESBANK_GBON_10Y_KEY: Final[str] = "B.10Y.GBON"

NORGESBANK_BASE_URL: Final[str] = "https://data.norges-bank.no/api/data"

# Norges Bank DataAPI accepts any UA — we pass a descriptive one for
# operator identity on the server-side request log, mirroring the
# Sprint S (BoC) / Sprint T (RBA) / Sprint V (SNB) pattern.
NORGESBANK_USER_AGENT: Final[str] = "SONAR/2.0 (monetary-cascade; contact hugocondesa@pm.me)"


class NorgesBankConnector:
    """L0 connector for the Norges Bank DataAPI SDMX-JSON endpoint.

    The DataAPI is public — no API key, no auth, no bot screen on the
    ``/api/data/{flow}/{key}`` path (Sprint X-NO probe 2026-04-22).
    Responses are **daily** SDMX-JSON with the standard shape described
    in the module docstring.

    Slot in cascade: **secondary** behind TE primary for NO monetary
    inputs (see :func:`build_m1_no_inputs`). Returns results in the
    generic ``Observation`` shape so the builder resampler can consume
    them unchanged.

    Daily cadence matches TE's primary exactly (contrast SNB / RBA
    native paths which are monthly-averaged). The cascade never emits
    a staleness flag on the Norges Bank native path — the
    daily-versus-daily parity means the native secondary lands
    ``NO_POLICY_RATE_NORGESBANK_NATIVE`` with no cadence qualifier.
    """

    BASE_URL: Final[str] = NORGESBANK_BASE_URL
    CACHE_NAMESPACE: Final[str] = "norgesbank_dataapi"
    CONNECTOR_ID: Final[str] = "norgesbank"

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
                "User-Agent": NORGESBANK_USER_AGENT,
                "Accept": "application/vnd.sdmx.data+json",
            },
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(
        self,
        flow: str,
        key: str,
        start: date,
        end: date,
    ) -> dict[str, Any]:
        """Hit ``/api/data/{flow}/{key}`` with SDMX ``startPeriod`` / ``endPeriod`` filters."""
        url = f"{self.BASE_URL}/{flow}/{key}"
        params = {
            "format": "sdmx-json",
            "startPeriod": start.isoformat(),
            "endPeriod": end.isoformat(),
        }
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        payload = r.json()
        return cast("dict[str, Any]", payload or {})

    @staticmethod
    def _parse_sdmx_json(
        payload: dict[str, Any],
        *,
        flow: str,
        key: str,
    ) -> list[tuple[date, float]]:
        """Parse an SDMX-JSON response into ``[(obs_date, value), ...]``.

        Walks the ``data.structure.dimensions.observation[0].values``
        list to recover the TIME_PERIOD date axis, then iterates
        ``data.dataSets[0].series`` (pinned to exactly one series when
        the caller supplies a fully-specified dimension key like
        ``B.KPRA.SD.R``) emitting ``(date, float)`` tuples for every
        non-null observation.

        Raises :class:`DataUnavailableError` when the SDMX-JSON schema
        does not have the expected shape (dataflow retired / key
        mis-specified / upstream change) or when the series maps to
        zero parseable rows. The NO cascade treats that as soft-fail.
        """
        data = payload.get("data") or {}
        datasets = data.get("dataSets") or []
        structure = data.get("structure") or {}
        dims = structure.get("dimensions") or {}
        obs_dim_list = dims.get("observation") or []

        if not datasets or not obs_dim_list:
            msg = (
                f"Norges Bank DataAPI flow={flow!r} key={key!r}: "
                "empty dataSets or missing observation dimension"
            )
            raise DataUnavailableError(msg)

        obs_dim = obs_dim_list[0]
        obs_values = obs_dim.get("values") or []
        if not obs_values:
            msg = f"Norges Bank DataAPI flow={flow!r} key={key!r}: empty time_period values"
            raise DataUnavailableError(msg)
        dates_by_index: list[str] = [str(v.get("id", "")) for v in obs_values]

        series_map: dict[str, Any] = datasets[0].get("series") or {}
        if not series_map:
            msg = f"Norges Bank DataAPI flow={flow!r} key={key!r}: empty series map"
            raise DataUnavailableError(msg)

        out: list[tuple[date, float]] = []
        for _series_key, series_body in series_map.items():
            observations = series_body.get("observations") or {}
            for idx_str, cell in observations.items():
                try:
                    idx = int(idx_str)
                except (TypeError, ValueError):
                    continue
                if not 0 <= idx < len(dates_by_index):
                    continue
                raw_date = dates_by_index[idx]
                if not raw_date:
                    continue
                if not isinstance(cell, list) or not cell:
                    continue
                raw_value = cell[0]
                if raw_value is None or raw_value == "":
                    continue
                try:
                    obs_date = datetime.strptime(raw_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
                    value_pct = float(raw_value)
                except (TypeError, ValueError):
                    continue
                out.append((obs_date, value_pct))

        if not out:
            msg = f"Norges Bank DataAPI flow={flow!r} key={key!r}: no parseable rows"
            raise DataUnavailableError(msg)
        return out

    async def fetch_series(
        self,
        series_id: str,
        start: date,
        end: date,
    ) -> list[Observation]:
        """Return parsed observations for ``series_id = "{flow}/{key}"`` in ``[start, end]``.

        Cached 24h. ``series_id`` encodes both the SDMX dataflow and the
        series key as ``"<FLOW>/<KEY>"`` — e.g. ``"IR/B.KPRA.SD.R"``.

        Empty response / malformed SDMX-JSON / HTTP error raises
        :class:`DataUnavailableError`; upstream cascade callers treat
        that as soft-fail and fall back to FRED OECD mirror.
        """
        try:
            flow, key = series_id.split("/", 1)
        except ValueError as exc:
            msg = (
                f"Norges Bank series_id must be '<FLOW>/<KEY>' "
                f"(e.g. 'IR/B.KPRA.SD.R'); got {series_id!r}"
            )
            raise DataUnavailableError(msg) from exc

        cache_key = f"{self.CACHE_NAMESPACE}:{flow}:{key}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("norgesbank.cache_hit", flow=flow, key=key)
            return list(cached)

        try:
            payload = await self._fetch_raw(flow, key, start, end)
        except (httpx.HTTPError, RetryError) as exc:
            msg = f"Norges Bank DataAPI flow={flow!r} key={key!r} HTTP error: {exc}"
            raise DataUnavailableError(msg) from exc

        parsed = self._parse_sdmx_json(payload, flow=flow, key=key)
        out: list[Observation] = []
        for obs_date, value_pct in parsed:
            if not (start <= obs_date <= end):
                continue
            out.append(
                Observation(
                    country_code="NO",
                    observation_date=obs_date,
                    tenor_years=0.01,
                    yield_bps=round(value_pct * 100),
                    source="NORGESBANK",
                    source_series_id=series_id,
                )
            )
        if not out:
            msg = (
                f"Norges Bank DataAPI flow={flow!r} key={key!r}: no rows in "
                f"[{start.isoformat()}, {end.isoformat()}]"
            )
            raise DataUnavailableError(msg)
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        log.info("norgesbank.fetched", flow=flow, key=key, n=len(out))
        return out

    async def fetch_policy_rate(self, start: date, end: date) -> list[Observation]:
        """Key policy rate (sight-deposit rate) — flow :data:`NORGESBANK_POLICY_RATE_FLOW`.

        Norges Bank's operational policy rate since the 2001 inflation-
        targeting regime. Daily cadence (business days); the series
        constant-fills between decision dates so any window returns the
        full decision history plus interim quotes.

        Named ``fetch_policy_rate`` to stay consistent with the
        GB / JP / CA / AU / NZ / CH cascade vocabulary — the M1 cascade
        slot is the same regardless of country. Wraps
        :func:`fetch_series` with the pinned ``IR/B.KPRA.SD.R``
        identifier so callers don't have to remember the SDMX
        dimensions.
        """
        return await self.fetch_series(
            f"{NORGESBANK_POLICY_RATE_FLOW}/{NORGESBANK_POLICY_RATE_KEY}",
            start,
            end,
        )

    async def fetch_gbon_10y(self, start: date, end: date) -> list[Observation]:
        """10Y generic Norwegian government bond yield — flow :data:`NORGESBANK_GBON_10Y_FLOW`.

        Constant-maturity 10-year benchmark. Landing point for M4 FCI NO
        10Y input (CAL-NO-M4-FCI). Tenor is overridden to 10.0 years on
        the returned Observations (vs the 0.01 default
        :func:`fetch_series` stamps for short-rate use).
        """
        obs = await self.fetch_series(
            f"{NORGESBANK_GBON_10Y_FLOW}/{NORGESBANK_GBON_10Y_KEY}",
            start,
            end,
        )
        return [o.model_copy(update={"tenor_years": 10.0}) for o in obs]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
