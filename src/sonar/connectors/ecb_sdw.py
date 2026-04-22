"""ECB SDW (Statistical Data Warehouse) L0 connector.

Pattern mirrors :class:`sonar.connectors.fred.FredConnector`: low-level
``fetch_series`` returns ``list[Observation]`` for any ECB SDW series; a
domain wrapper ``fetch_yield_curve_nominal`` aggregates the EA AAA
Svensson par-rate curve into ``{tenor_label: Observation}`` per spec §2.

ECB SDW is open (no API key). Endpoint: ``https://data-api.ecb.europa.eu``;
CSV (``format=csvdata``) chosen over SDMX-XML/JSON for parser simplicity.

Per-country EA periphery coverage is **empirically infeasible via ECB
SDW** — confirmed by the Week 10 Sprint A pre-flight probe (2026-04-22):

* ``YC`` dataflow: ``REF_AREA`` = ``U2`` only (EA aggregate AAA Svensson).
* ``FM`` dataflow: ``REF_AREA`` ∈ {U2, DK, GB, JP, SE, US} — no EA
  periphery sovereign series are published.
* ``IRS`` dataflow: monthly 10Y Maastricht convergence rate per country
  (single point, below NSS ``MIN_OBSERVATIONS=6`` so cannot fit a curve).

PT/IT/ES/FR/NL therefore require national-CB connectors (analog to
:class:`~sonar.connectors.bundesbank.BundesbankConnector` for DE);
each country is tracked under its own CAL item (see
:data:`PERIPHERY_CAL_POINTERS`). The Sprint A probe superseded the
umbrella ``CAL-CURVES-EA-PERIPHERY`` with the five per-country items.

Reference: ``docs/data_sources/monetary.md`` §3.2 ECB SDW; spec
``docs/specs/overlays/nss-curves.md`` §2 T1 DE/EA-AAA;
``docs/planning/retrospectives/week10-sprint-ea-periphery-report.md``.
"""

from __future__ import annotations

import csv
import io
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

from sonar.connectors.base import BaseConnector, Observation
from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()

# EA AAA Svensson spot-rate yield curve series. Key composition documented in
# `data_sources/monetary.md` §3.2 + ECB SDW dataflow `YC`. Tenors keyed by the
# canonical SONAR labels (no "1M" — Fed publishes it but ECB does not).
ECB_EA_NOMINAL_SERIES: dict[str, str] = {
    "3M": "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M",
    "6M": "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_6M",
    "1Y": "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y",
    "2Y": "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y",
    "3Y": "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3Y",
    "5Y": "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y",
    "7Y": "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_7Y",
    "10Y": "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
    "15Y": "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_15Y",
    "20Y": "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_20Y",
    "30Y": "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_30Y",
}

# --------------------------------------------------------------------------
# M1 EA monetary inputs (CAL-098, week6 sprint 2b)
# --------------------------------------------------------------------------
# Dataflow keys confirmed via live pre-flight probe:
# - DFR:                FM/D.U2.EUR.4F.KR.DFR.LEV    (daily)
# - Eurosystem assets:  ILM/W.U2.C.T000000.Z5.Z01    (weekly consolidated
#                                                     Eurosystem balance
#                                                     sheet total assets)
ECB_DFR_DATAFLOW = "FM"
ECB_DFR_SERIES_ID = "D.U2.EUR.4F.KR.DFR.LEV"
ECB_EUROSYSTEM_BS_DATAFLOW = "ILM"
ECB_EUROSYSTEM_BS_SERIES_ID = "W.U2.C.T000000.Z5.Z01"

# Per-country CAL pointers for EA periphery members whose full yield
# curves are not served by ECB SDW (Sprint A 2026-04-22 probe finding).
# These supersede the umbrella CAL-CURVES-EA-PERIPHERY — each country
# has its own national-CB integration path + estimate.
PERIPHERY_CAL_POINTERS: dict[str, str] = {
    "PT": "CAL-CURVES-PT-BPSTAT",
    "IT": "CAL-CURVES-IT-BDI",
    "ES": "CAL-CURVES-ES-BDE",
    "FR": "CAL-CURVES-FR-BDF",
    "NL": "CAL-CURVES-NL-DNB",
}


@dataclass(frozen=True, slots=True)
class EcbMonetaryObservation:
    """Generic ECB SDW monetary-series observation (non-curve).

    Shape differs from :class:`Observation` (which is curve-specific with a
    ``tenor_years`` field). Used by M1 EA inputs (DFR policy rate,
    Eurosystem balance-sheet total assets).
    """

    observation_date: date
    value: float
    dataflow: str
    source_series_id: str
    source: str = "ECB_SDW"


# Tenor years lookup (subset of FRED_SERIES_TENORS for ECB-published tenors).
ECB_SERIES_TENORS: dict[str, float] = {
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M": 0.25,
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_6M": 0.5,
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y": 1.0,
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y": 2.0,
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3Y": 3.0,
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y": 5.0,
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_7Y": 7.0,
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y": 10.0,
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_15Y": 15.0,
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_20Y": 20.0,
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_30Y": 30.0,
}


class EcbSdwConnector(BaseConnector):
    """L0 connector for ECB Statistical Data Warehouse (SDW)."""

    BASE_URL = "https://data-api.ecb.europa.eu/service/data"
    DATAFLOW = "YC"

    def __init__(self, cache_dir: str | Path, timeout: float = 30.0) -> None:
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(
        self, series_id: str, start: date, end: date, *, dataflow: str | None = None
    ) -> str:
        df = dataflow or self.DATAFLOW
        url = f"{self.BASE_URL}/{df}/{series_id}"
        params: dict[str, Any] = {
            "startPeriod": start.isoformat(),
            "endPeriod": end.isoformat(),
            "format": "csvdata",
        }
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        return r.text

    async def _fetch_monetary_series(
        self, dataflow: str, series_id: str, start: date, end: date
    ) -> list[EcbMonetaryObservation]:
        """Fetch + parse any ECB SDW series into generic monetary observations."""
        cache_key = f"ecb_sdw_monetary:{dataflow}:{series_id}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("ecb_sdw.monetary.cache_hit", dataflow=dataflow, series=series_id)
            return cast("list[EcbMonetaryObservation]", cached)

        body = await self._fetch_raw(series_id, start, end, dataflow=dataflow)
        observations = list(_parse_monetary_csv(body, dataflow, series_id))
        self.cache.set(cache_key, observations, ttl=DEFAULT_TTL_SECONDS)
        log.info(
            "ecb_sdw.monetary.fetched", dataflow=dataflow, series=series_id, n=len(observations)
        )
        return observations

    async def fetch_dfr_rate(self, start: date, end: date) -> list[EcbMonetaryObservation]:
        """ECB Deposit Facility Rate (DFR, daily, percent level).

        Authoritative key: ``FM/D.U2.EUR.4F.KR.DFR.LEV`` — confirmed live
        during week6-sprint-2b pre-flight probe.
        """
        return await self._fetch_monetary_series(ECB_DFR_DATAFLOW, ECB_DFR_SERIES_ID, start, end)

    async def fetch_eurosystem_balance_sheet(
        self, start: date, end: date
    ) -> list[EcbMonetaryObservation]:
        """Eurosystem consolidated balance-sheet total assets (weekly, EUR mn).

        Authoritative key: ``ILM/W.U2.C.T000000.Z5.Z01`` — confirmed live
        during week6-sprint-2b pre-flight probe (≈6.44T EUR 2024-W41).
        """
        return await self._fetch_monetary_series(
            ECB_EUROSYSTEM_BS_DATAFLOW,
            ECB_EUROSYSTEM_BS_SERIES_ID,
            start,
            end,
        )

    async def fetch_series(self, series_id: str, start: date, end: date) -> list[Observation]:
        cache_key = f"ecb_sdw:{series_id}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("ecb_sdw.cache_hit", series=series_id)
            return cast("list[Observation]", cached)

        tenor = ECB_SERIES_TENORS.get(series_id)
        if tenor is None:
            msg = f"Unknown ECB SDW series mapping: {series_id}"
            raise ValueError(msg)

        body = await self._fetch_raw(series_id, start, end)
        observations = list(_parse_csv(body, series_id, tenor))
        self.cache.set(cache_key, observations, ttl=DEFAULT_TTL_SECONDS)
        log.info("ecb_sdw.fetched", series=series_id, n=len(observations))
        return observations

    async def fetch_yield_curve_nominal(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        """EA AAA Svensson par-rate curve. ``country`` must be ``EA``.

        Per-country EA members (DE / PT / IT / ES / FR / NL) are not
        served by the ``YC`` dataflow (which publishes a single
        EA-aggregate AAA Svensson fit); DE has a dedicated
        :class:`sonar.connectors.bundesbank.BundesbankConnector`, and
        periphery coverage is tracked under the five per-country CAL
        items listed in :data:`PERIPHERY_CAL_POINTERS` (2026-04-22
        Sprint A probe superseded the umbrella CAL-CURVES-EA-PERIPHERY).
        """
        if country != "EA":
            periphery_pointer = PERIPHERY_CAL_POINTERS.get(country)
            if periphery_pointer is not None:
                msg = (
                    f"ECB SDW yield curve only supports country=EA "
                    f"(aggregate AAA Svensson); got {country}. "
                    f"{country} requires a national-CB connector — "
                    f"tracked under {periphery_pointer}."
                )
            else:
                msg = (
                    f"ECB SDW yield curve only supports country=EA "
                    f"(aggregate AAA Svensson); got {country}. "
                    f"For DE use BundesbankConnector; PT/IT/ES/FR/NL defer "
                    f"per their per-country CAL items (see "
                    f"PERIPHERY_CAL_POINTERS)."
                )
            raise ValueError(msg)

        window_days = 7
        start = observation_date - timedelta(days=window_days)
        end = observation_date
        out: dict[str, Observation] = {}
        for tenor_label, series_id in ECB_EA_NOMINAL_SERIES.items():
            obs_list = await self.fetch_series(series_id, start, end)
            usable = [o for o in obs_list if o.observation_date <= observation_date]
            if not usable:
                continue
            usable.sort(key=lambda o: o.observation_date)
            out[tenor_label] = usable[-1]
        return out

    async def fetch_yield_curve_linker(
        self,
        country: str,
        observation_date: date,  # noqa: ARG002 — stub; symmetric signature with nominal
    ) -> dict[str, Observation]:
        """Inflation-indexed (linker) curve stub for EA — returns empty dict.

        The ``YC`` dataflow has no inflation-indexed counterpart;
        per-country ILB series (OATei/BTP€i/Bonos-i/DBR-i/DSL-i) live in
        dedicated national-CB feeds and are tracked under the per-country
        CAL items in :data:`PERIPHERY_CAL_POINTERS` (linker coverage is
        bundled into each per-country sprint). Callers receive an empty
        dict + should emit a ``LINKER_UNAVAILABLE`` flag on the resulting
        :class:`~sonar.overlays.nss.RealCurve` (method remains
        ``derived`` via BEI fallback where feasible).
        """
        if country != "EA":
            periphery_pointer = PERIPHERY_CAL_POINTERS.get(country)
            if periphery_pointer is not None:
                msg = (
                    f"ECB SDW yield curve linker stub only accepts "
                    f"country=EA; got {country}. {country} linker "
                    f"coverage tracked under {periphery_pointer}."
                )
            else:
                msg = f"ECB SDW yield curve linker stub only accepts country=EA; got {country}."
            raise ValueError(msg)
        return {}

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


def _parse_monetary_csv(body: str, dataflow: str, series_id: str) -> list[EcbMonetaryObservation]:
    """Parse ECB SDW csvdata into generic monetary observations.

    Handles both daily ISO dates (``2024-12-18``) and weekly period codes
    (``2024-W41``). Weekly periods anchor on Friday of the ISO week per
    ECB convention.
    """
    reader = csv.DictReader(io.StringIO(body))
    out: list[EcbMonetaryObservation] = []
    for row in reader:
        time_period = (row.get("TIME_PERIOD") or "").strip()
        raw_value = (row.get("OBS_VALUE") or "").strip()
        if not time_period or not raw_value or raw_value in {"NA", "."}:
            continue
        try:
            value = float(raw_value)
        except ValueError:
            continue
        obs_date = _parse_time_period(time_period)
        if obs_date is None:
            continue
        out.append(
            EcbMonetaryObservation(
                observation_date=obs_date,
                value=value,
                dataflow=dataflow,
                source_series_id=series_id,
            )
        )
    return out


def _parse_time_period(time_period: str) -> date | None:
    """Convert ECB SDW ``TIME_PERIOD`` into a date.

    Supports ``YYYY-MM-DD`` (daily) and ``YYYY-Www`` (weekly, anchors on
    the Friday of the ISO week).
    """
    # ISO week format (``YYYY-Www``) has to be handled before fromisoformat —
    # Python 3.11+ parses ``2024-W41`` to the Monday of that week, but ECB
    # publishes weekly observations anchored on the Friday close.
    if len(time_period) == 8 and time_period[4] == "-" and time_period[5] == "W":
        try:
            year = int(time_period[:4])
            week = int(time_period[6:])
            return date.fromisocalendar(year, week, 5)  # Friday
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(time_period).date()
    except ValueError:
        return None


def _parse_csv(body: str, series_id: str, tenor: float) -> list[Observation]:
    """Parse ECB SDW csvdata response into Observation rows.

    Schema includes many SDMX dimensions; we extract TIME_PERIOD + OBS_VALUE.
    Empty / NA / "." rows are skipped.
    """
    reader = csv.DictReader(io.StringIO(body))
    out: list[Observation] = []
    for row in reader:
        time_period = (row.get("TIME_PERIOD") or "").strip()
        raw_value = (row.get("OBS_VALUE") or "").strip()
        if not time_period or not raw_value or raw_value in {"NA", "."}:
            continue
        try:
            value_pct = float(raw_value)
        except ValueError:
            continue
        try:
            obs_date = datetime.fromisoformat(time_period).date()
        except ValueError:
            continue
        out.append(
            Observation(
                country_code="EA",
                observation_date=obs_date,
                tenor_years=tenor,
                yield_bps=round(value_pct * 100),
                source="ECB_SDW",
                source_series_id=series_id,
            )
        )
    return out
