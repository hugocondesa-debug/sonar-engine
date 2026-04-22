"""OECD Economic Outlook (EO) L0 connector — annual output-gap series.

Primary use case: populate ``M2TaylorGapsInputs.output_gap_pct`` for the
Tier-1 countries that lack a native quarterly potential-GDP feed the way
the US does via CBO ``GDPPOT`` (wrapped in
:class:`~sonar.connectors.cbo.CboConnector`). OECD publishes the
annual output gap directly under the ``GAP`` measure of the ``DSD_EO``
dataflow (agency ``OECD.ECO.MAD``) — no derivation from GDPV/GDPVTR
required.

Empirical probe 2026-04-22 (Week 10 Sprint C pre-flight):

* Endpoint: ``https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO,1.4``
* Public (no auth / key), JSON via ``format=jsondata``.
* ``GAP`` measure = output gap as percent of potential GDP, **annual**
  (``FREQ=A``). Edition EO118 covers 1990 → 2027 (historicals + two-year
  forecasts). Forecasts are interleaved with historicals in the same
  series — the connector returns all observations and leaves cadence-
  discrimination to the caller (per-country ``last_historical`` year
  documented in EO publication metadata).
* Coverage confirmed live for 16 T1 ISO3 codes: ``USA / DEU / FRA /
  ITA / ESP / NLD / PRT / GBR / JPN / CAN / AUS / NZL / CHE / SWE /
  NOR / DNK``. EA aggregate is served as ``EA17`` (legacy 17-member
  composition — ``EA19`` / ``EA20`` return ``NoRecordsFound``).

Cadence caveat vs US CBO quarterly path: OECD EO publishes twice per
year (June + November editions). For observation dates mid-cycle,
the latest available ``TIME_PERIOD`` that is ≤ ``observation_date.year``
is the best nowcast estimate. M2 builders should document this in the
``source_connector`` / ``upstream_flags`` on the resulting
``M2TaylorGapsInputs`` so downstream consumers can see the cadence
difference vs the US canonical path.

Related CAL items: ``CAL-M2-T1-OUTPUT-GAP-EXPANSION`` (Sprint C scope).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
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

from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()

__all__ = [
    "OECD_EO_BASE_URL",
    "OECD_EO_COUNTRY_MAP",
    "OECD_EO_DATAFLOW",
    "OECDEOConnector",
    "OutputGapObservation",
]

# SDMX-JSON endpoint root. Public (no auth).
OECD_EO_BASE_URL: Final[str] = (
    "https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO,1.4"
)
OECD_EO_DATAFLOW: Final[str] = "DSD_EO@DF_EO"

# ISO2 (SONAR canonical country code) → OECD EO REF_AREA code.
# 16 T1 countries + EA aggregate confirmed live during Sprint C pre-
# flight probe 2026-04-22. EA aggregate uses the legacy ``EA17`` code
# (EA19 / EA20 return NoRecordsFound for the GAP measure as of EO118).
OECD_EO_COUNTRY_MAP: Final[dict[str, str]] = {
    "US": "USA",
    "DE": "DEU",
    "FR": "FRA",
    "IT": "ITA",
    "ES": "ESP",
    "NL": "NLD",
    "PT": "PRT",
    "GB": "GBR",
    "JP": "JPN",
    "CA": "CAN",
    "AU": "AUS",
    "NZ": "NZL",
    "CH": "CHE",
    "SE": "SWE",
    "NO": "NOR",
    "DK": "DNK",
    "EA": "EA17",
}

# Default history window for the gap series — 10y covers the OECD
# historical vintage comfortably and keeps payload small.
_DEFAULT_HISTORY_YEARS: Final[int] = 10


@dataclass(frozen=True, slots=True)
class OutputGapObservation:
    """Annual output gap observation from OECD EO.

    ``gap_pct`` is expressed in percent of potential GDP (already
    decimal-percent per OECD convention — e.g. ``-4.02`` means the
    economy is running 4.02% below potential). Callers that need a
    decimal ratio (``-0.0402``) should divide by 100.
    """

    country_code: str
    observation_date: date
    gap_pct: float
    ref_area: str
    source: str = "OECD_EO"
    measure: str = "GAP"


class OECDEOConnector:
    """L0 connector for OECD Economic Outlook SDMX-JSON endpoint.

    Pattern mirrors :class:`~sonar.connectors.boc.BoCConnector`:
    public JSON REST, httpx async client with tenacity retries, disk-
    backed cache with 24h TTL, and
    :class:`~sonar.overlays.exceptions.DataUnavailableError` on soft
    fail so upstream builders can cleanly skip without crashing the
    pipeline.

    Supported countries: keys of :data:`OECD_EO_COUNTRY_MAP`. Any
    other country raises ``ValueError`` with a pointer to
    ``CAL-M2-T1-OUTPUT-GAP-EXPANSION`` so callers see where to track
    the gap.
    """

    BASE_URL: Final[str] = OECD_EO_BASE_URL
    CACHE_NAMESPACE: Final[str] = "oecd_eo"
    CONNECTOR_ID: Final[str] = "oecd_eo"

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
                "User-Agent": "SONAR/2.0 (output-gap; contact hugocondesa@pm.me)",
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
        ref_area: str,
        measure: str,
        start_period: str,
        end_period: str,
    ) -> str:
        """Return raw JSON body for ``(ref_area, measure, range)`` query."""
        # OECD SDMX key format: ``REF_AREA.MEASURE....`` (dots for every
        # remaining dimension; they become wildcards).
        key = f"{ref_area}.{measure}...."
        url = f"{self.BASE_URL}/{key}"
        params = {
            "startPeriod": start_period,
            "endPeriod": end_period,
            "format": "jsondata",
        }
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        return r.text

    def _resolve_ref_area(self, country_code: str) -> str:
        ref = OECD_EO_COUNTRY_MAP.get(country_code)
        if ref is None:
            msg = (
                f"OECD EO GAP not mapped for country={country_code!r}. "
                f"Supported: {sorted(OECD_EO_COUNTRY_MAP)}. Add mapping "
                f"+ probe under CAL-M2-T1-OUTPUT-GAP-EXPANSION if this "
                f"country needs coverage."
            )
            raise ValueError(msg)
        return ref

    async def fetch_output_gap(
        self,
        country_code: str,
        start: date,
        end: date,
    ) -> list[OutputGapObservation]:
        """Return annual ``GAP`` observations for ``country_code``.

        ``country_code`` is SONAR canonical ISO2 (see
        :data:`OECD_EO_COUNTRY_MAP`). Range ``[start, end]`` covers
        calendar years (OECD GAP is annual). Empty responses raise
        :class:`DataUnavailableError`; callers in the M2 cascade
        treat this as soft-fail and raise a narrower
        ``InsufficientDataError`` upstream.
        """
        ref_area = self._resolve_ref_area(country_code)
        start_period = str(start.year)
        end_period = str(end.year)
        cache_key = f"{self.CACHE_NAMESPACE}:gap:{ref_area}:{start_period}:{end_period}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("oecd_eo.cache_hit", ref_area=ref_area, measure="GAP")
            return list(cached)

        try:
            body = await self._fetch_raw(ref_area, "GAP", start_period, end_period)
        except (httpx.HTTPError, RetryError) as exc:
            msg = f"OECD EO GAP ref_area={ref_area!r} HTTP error: {exc}"
            raise DataUnavailableError(msg) from exc

        if body.strip().startswith("NoRecordsFound") or not body.strip():
            msg = (
                f"OECD EO returned no records: ref_area={ref_area!r} "
                f"measure=GAP range={start_period}-{end_period}"
            )
            raise DataUnavailableError(msg)

        try:
            payload = cast("dict[str, Any]", json.loads(body))
        except json.JSONDecodeError as exc:
            msg = f"OECD EO ref_area={ref_area!r} returned non-JSON body: {body[:120]!r}"
            raise DataUnavailableError(msg) from exc

        observations = list(_parse_gap_payload(payload, country_code, ref_area))
        if not observations:
            msg = (
                f"OECD EO GAP ref_area={ref_area!r}: payload parsed but "
                f"no usable observations in range {start_period}-{end_period}"
            )
            raise DataUnavailableError(msg)
        observations.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, observations, ttl=DEFAULT_TTL_SECONDS)
        log.info(
            "oecd_eo.fetched",
            ref_area=ref_area,
            measure="GAP",
            n=len(observations),
            first=observations[0].observation_date.isoformat(),
            last=observations[-1].observation_date.isoformat(),
        )
        return observations

    async def fetch_latest_output_gap(
        self,
        country_code: str,
        observation_date: date,
        *,
        history_years: int = _DEFAULT_HISTORY_YEARS,
    ) -> OutputGapObservation | None:
        """Return the most recent ``GAP`` observation ≤ ``observation_date``.

        The EO series is annual — the returned observation carries
        ``observation_date = date(YYYY, 12, 31)`` for the calendar year
        reported by OECD. Callers anchoring M2 inputs on a specific
        date should treat the year-end timestamp as a nowcast.
        """
        start = observation_date - timedelta(days=history_years * 366)
        try:
            gaps = await self.fetch_output_gap(country_code, start, observation_date)
        except DataUnavailableError:
            return None
        usable = [g for g in gaps if g.observation_date <= observation_date]
        if not usable:
            return None
        usable.sort(key=lambda g: g.observation_date)
        return usable[-1]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


def _parse_gap_payload(
    payload: dict[str, Any], country_code: str, ref_area: str
) -> list[OutputGapObservation]:
    """Extract observations from SDMX-JSON 2.0 payload.

    Structure:
    ``data.dataSets[0].series[SERIES_KEY].observations[OBS_INDEX] =
    [value, ...attrs]`` where ``OBS_INDEX`` is a position into
    ``data.structures[0].dimensions.observation[0].values[]`` (which
    lists ``TIME_PERIOD`` ids — e.g. ``"2024"``).
    """
    data = payload.get("data") or {}
    structures = data.get("structures") or []
    if not structures:
        return []
    obs_dims = structures[0].get("dimensions", {}).get("observation") or []
    if not obs_dims:
        return []
    time_periods = [str(v.get("id")) for v in (obs_dims[0].get("values") or [])]
    datasets = data.get("dataSets") or []
    if not datasets:
        return []
    series = datasets[0].get("series") or {}
    out: list[OutputGapObservation] = []
    for _series_key, series_block in series.items():
        observations = series_block.get("observations") or {}
        for idx_key, value_pack in observations.items():
            try:
                idx = int(idx_key.split(":")[0])
            except (AttributeError, ValueError):
                continue
            if idx < 0 or idx >= len(time_periods):
                continue
            if not value_pack:
                continue
            raw_value = value_pack[0]
            if raw_value is None:
                continue
            try:
                value_pct = float(raw_value)
            except (TypeError, ValueError):
                continue
            time_period = time_periods[idx]
            try:
                year = int(time_period)
            except ValueError:
                continue
            out.append(
                OutputGapObservation(
                    country_code=country_code,
                    observation_date=date(year, 12, 31),
                    gap_pct=value_pct,
                    ref_area=ref_area,
                )
            )
    return out
