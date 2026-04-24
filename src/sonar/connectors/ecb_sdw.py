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

Week 10 Sprint D pilot (2026-04-22) executed the first national-CB
integration (FR via Banque de France webstat) and **inverted the
pattern assumption**: BdF decommissioned its legacy SDMX-JSON REST
mid-2024 in a migration to OpenDatasoft that exposes only a monthly
archive dataset (tenor-incomplete, publication frozen 2024-07-11).
All four brief §9 fallback paths (BdF / AFT / TE / FRED) failed,
firing HALT-0. ``CAL-CURVES-FR-BDF`` is consequently marked BLOCKED;
see :mod:`sonar.connectors.banque_de_france` for the scaffolded
placeholder connector and ``docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md``
for the pattern lessons applicable to the four successor sprints
(IT/ES/PT/NL).

Week 10 Sprint G (2026-04-22, combined IT + ES pilot) extended the
ADR-0009 probe discipline to the second and third EA-periphery
successors. Both landed in HALT-0 territory but via different
sub-cases: IT is strict "all paths dead" (ECB legacy SDMX
decommissioned; BdI Infostat subdomains NXDOMAIN; MEF Tesoro
HTML-only; ECB SDW FM + IRS EA-aggregate; FRED 10Y-monthly) while
ES lands on a new "HTTP 200 + non-daily" sub-case (BdE BIE REST
``https://app.bde.es/bierest/`` is live and publishes 11-tenor
Spanish sovereign yields but all at monthly frequency, below the
daily pipeline cadence). ``CAL-CURVES-IT-BDI`` + ``CAL-CURVES-ES-BDE``
are BLOCKED; see :mod:`sonar.connectors.banca_ditalia` +
:mod:`sonar.connectors.banco_espana` for the scaffolded placeholders.
Pattern-library update in ADR-0009 captures the new sub-case.

Reference: ``docs/data_sources/monetary.md`` §3.2 ECB SDW; spec
``docs/specs/overlays/nss-curves.md`` §2 T1 DE/EA-AAA;
``docs/planning/retrospectives/week10-sprint-ea-periphery-report.md``;
``docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md``;
``docs/planning/retrospectives/week10-sprint-curves-it-es-report.md``.
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

# ---------------------------------------------------------------------------
# MIR dataflow — MFI interest rates (Sprint J, Week 10 Day 2)
# ---------------------------------------------------------------------------
#
# Key format ``M.{CC}.B.A2C.A.R.A.2250.EUR.N`` = monthly MFI lending
# rate for new business, loans to households for house purchase
# (narrowly-defined effective rate, EUR-denominated, no amount cap).
# Sprint J Commit 1 pre-flight probe (2026-04-22) confirmed 7/7
# coverage for EA aggregate (U2) + DE + FR + IT + ES + NL + PT.
# GB / JP / CA / AU / NZ / CH / SE / NO / DK are not served by MIR
# (non-EA jurisdictions) and are tracked under
# CAL-M4-MORTGAGE-RATE-T1-NATIVE-EXPANSION for per-CB native
# mortgage-rate series.
# ---------------------------------------------------------------------------
# SPF dataflow — Survey of Professional Forecasters (Sprint Q.1, Week 11)
# ---------------------------------------------------------------------------
#
# Per the Sprint Q.1 pre-flight probe
# (``docs/backlog/probe-results/sprint-q-1-ecb-spf-probe.md``, 2026-04-24):
#
# * Dataflow ``SPF`` is live (HTTP 200) and backed by DSD
#   ``ECB:ECB_FCT1(1.0)`` (7 dimensions: FREQ, REF_AREA, FCT_TOPIC,
#   FCT_BREAKDOWN, FCT_HORIZON, SURVEY_FREQ, FCT_SOURCE).
# * ``REF_AREA`` is **U2 only** — no per-country SPF series. The EA
#   aggregate is proxied to EA members (DE/FR/IT/ES/PT/NL) under the
#   ``SPF_AREA_PROXY`` flag; per-country upgrades are tracked under
#   ``CAL-EXPINF-PER-COUNTRY-LINKERS-FOLLOWUP``.
# * Horizon convention: ``FCT_HORIZON`` encodes a calendar target year
#   (e.g. ``2027``) or the literal ``LT`` (long-term ≈ 5y ahead). The
#   canonical tenor is derived from ``(target_year - survey_year)``:
#   1 → ``1Y``, 2 → ``2Y``, ``LT`` → ``LTE`` (anchor proxy).
# * ``FCT_SOURCE=AVG`` returns data; ``MDN`` returned HTTP 404 at probe
#   time and is deferred to ``CAL-ECB-SPF-MDN-VARIANT``.
ECB_SPF_DATAFLOW: str = "SPF"
ECB_SPF_REF_AREA: str = "U2"
ECB_SPF_TOPIC_HICP: str = "HICP"
ECB_SPF_BREAKDOWN_POINT: str = "POINT"
ECB_SPF_SURVEY_FREQ: str = "Q"
ECB_SPF_SOURCE_AVG: str = "AVG"
# Wildcard on FCT_HORIZON — one CSV call returns every horizon per
# survey quarter in the requested window. Position-5 wildcard (``...``)
# preserves the 7-dimension key shape.
ECB_SPF_WILDCARD_KEY: str = (
    f"{ECB_SPF_SURVEY_FREQ}.{ECB_SPF_REF_AREA}.{ECB_SPF_TOPIC_HICP}"
    f".{ECB_SPF_BREAKDOWN_POINT}...{ECB_SPF_SOURCE_AVG}"
)
ECB_SPF_SURVEY_NAME: str = "ECB_SPF_HICP"

# EA aggregate + periphery cohort receiving the SPF proxy. ``NL`` is
# included for forward compatibility with Sprint P (MSC EA); the
# 6-country M3 FULL cascade target set is a subset (EA + DE + FR + IT +
# ES + PT per Sprint Q.1 brief §1).
ECB_SPF_COHORT: frozenset[str] = frozenset(
    {"EA", "DE", "FR", "IT", "ES", "PT", "NL"},
)


ECB_MIR_DATAFLOW = "MIR"
# SONAR ISO code → ECB MIR REF_AREA code.
_SONAR_TO_ECB_MIR_REF_AREA: dict[str, str] = {
    "EA": "U2",
    "DE": "DE",
    "FR": "FR",
    "IT": "IT",
    "ES": "ES",
    "NL": "NL",
    "PT": "PT",
}
ECB_MIR_SUPPORTED_COUNTRIES: frozenset[str] = frozenset(_SONAR_TO_ECB_MIR_REF_AREA)


def _ecb_mir_series_id(country: str) -> str:
    """Return the MIR dataflow series ID for ``country`` (SONAR ISO code).

    Raises ValueError for non-supported countries — non-EA T1
    jurisdictions open CAL-M4-MORTGAGE-RATE-T1-NATIVE-EXPANSION.
    """
    country_upper = country.upper()
    ref_area = _SONAR_TO_ECB_MIR_REF_AREA.get(country_upper)
    if ref_area is None:
        msg = (
            f"ECB MIR only supports EA aggregate + 6 EA members at Sprint J "
            f"scope; got {country!r}. Non-EA T1 jurisdictions open "
            f"CAL-M4-MORTGAGE-RATE-T1-NATIVE-EXPANSION for per-CB native "
            f"mortgage-rate series."
        )
        raise ValueError(msg)
    return f"M.{ref_area}.B.A2C.A.R.A.2250.EUR.N"


# Per-country CAL pointers for EA periphery members whose full yield
# curves are not served by ECB SDW (Sprint A 2026-04-22 probe finding).
# These supersede the umbrella CAL-CURVES-EA-PERIPHERY — each country
# has its own national-CB integration path + estimate. Sprint D pilot
# 2026-04-22 executed the FR-BDF integration and marked
# ``CAL-CURVES-FR-BDF`` BLOCKED (BdF legacy SDMX decommissioned +
# OpenDatasoft successor publishes only a monthly archive); ADR-0009
# carries the pattern notes for IT/ES/PT/NL pre-flights.
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


@dataclass(frozen=True, slots=True)
class ExpInflationSurveyObservation:
    """SPF (Survey of Professional Forecasters) point-forecast observation.

    Shape:

    * ``survey_date``: first day of the survey quarter (from ECB
      ``TIME_PERIOD``, e.g. ``2026-Q1`` → ``date(2026, 1, 1)``).
    * ``horizon_year``: the target calendar year for the forecast, or
      ``"LT"`` for the long-term (≈ 5y ahead) horizon.
    * ``tenor``: canonical SONAR tenor derived from
      ``(horizon_year - survey_date.year)``. Values: ``"0Y"``, ``"1Y"``,
      ``"2Y"``, ``"3Y"``, ``"LTE"`` (long-term). ``None`` for horizons
      outside the derivation rule (kept raw for the writer to persist +
      downstream filters).
    * ``value_pct``: point forecast expressed in percent (e.g. ``2.017``
      = 2.017 %; decimal conversion left to the caller per
      ``conventions/units.md``).
    * ``source``: constant ``"ecb_sdw_spf_area"`` — REF_AREA is U2-only
      on the SPF dataflow, so every observation is an EA aggregate.
    """

    survey_date: date
    horizon_year: str
    tenor: str | None
    value_pct: float
    source: str = "ecb_sdw_spf_area"


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

    async def fetch_survey_expected_inflation(
        self,
        country: str,
        start: date,
        end: date,
    ) -> list[ExpInflationSurveyObservation]:
        """Fetch SPF HICP point forecasts (euro-area aggregate).

        Per Sprint Q.1 probe
        (``docs/backlog/probe-results/sprint-q-1-ecb-spf-probe.md``):
        ECB SDW publishes a single EA-aggregate SPF series (REF_AREA=U2).
        This method proxies that aggregate to any member of
        :data:`ECB_SPF_COHORT`; callers downstream tag non-EA emits with
        the ``SPF_AREA_PROXY`` flag for analyst transparency.

        One CSV request (wildcarded on FCT_HORIZON) retrieves every
        target-year column for every survey quarter in the
        ``[start, end]`` window. Observations are returned as-fetched
        (unfiltered by tenor) so the writer + loader layers can choose
        their own subsets.

        Parameters
        ----------
        country:
            Canonical SONAR ISO alpha-2 code. Must belong to
            :data:`ECB_SPF_COHORT`; otherwise ``ValueError`` with a CAL
            pointer for the per-country path.
        start, end:
            Survey-quarter window. Passed through to SDW as
            ``startPeriod`` / ``endPeriod`` (supports ``YYYY-MM-DD``,
            which SDW rounds to the enclosing quarter).
        """
        country_upper = country.upper()
        if country_upper not in ECB_SPF_COHORT:
            msg = (
                f"ECB SDW SPF only covers the euro-area aggregate (REF_AREA=U2) "
                f"proxied to EA members {sorted(ECB_SPF_COHORT)}; got {country!r}. "
                f"Non-EA jurisdictions require per-country survey connectors "
                f"(CAL-EXPINF-GB-BOE-ILG-SPF / CAL-EXPINF-SURVEY-JP-CA)."
            )
            raise ValueError(msg)

        cache_key = f"ecb_sdw_spf:{ECB_SPF_WILDCARD_KEY}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("ecb_sdw.spf.cache_hit", country=country_upper)
            return cast("list[ExpInflationSurveyObservation]", cached)

        body = await self._fetch_raw(ECB_SPF_WILDCARD_KEY, start, end, dataflow=ECB_SPF_DATAFLOW)
        observations = list(_parse_spf_csv(body))
        self.cache.set(cache_key, observations, ttl=DEFAULT_TTL_SECONDS)
        log.info(
            "ecb_sdw.spf.fetched",
            country=country_upper,
            n=len(observations),
            start=start.isoformat(),
            end=end.isoformat(),
        )
        return observations

    async def fetch_mortgage_rate(
        self,
        country: str,
        start: date,
        end: date,
    ) -> list[EcbMonetaryObservation]:
        """MFI mortgage rate — monthly AAR / NDER, new business (Sprint J).

        Consumes MIR dataflow key
        ``M.{REF_AREA}.B.A2C.A.R.A.2250.EUR.N`` — lending rate for new
        business loans to households for house purchase
        (narrowly-defined effective rate, EUR, no amount cap). Supported
        countries: EA aggregate (U2) + DE + FR + IT + ES + NL + PT.
        Non-EA T1 jurisdictions open
        CAL-M4-MORTGAGE-RATE-T1-NATIVE-EXPANSION for per-CB native
        series.

        Returns ``list[EcbMonetaryObservation]`` in percent (decimal
        point e.g. 3.30 % at PT Jan 2024); monthly cadence with
        ``observation_date`` anchored on month-end.
        """
        series_id = _ecb_mir_series_id(country)
        return await self._fetch_monetary_series(ECB_MIR_DATAFLOW, series_id, start, end)

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


def _parse_time_period(time_period: str) -> date | None:  # noqa: PLR0911 — explicit cascade over {daily, weekly, monthly} cadences reads more clearly than a table
    """Convert ECB SDW ``TIME_PERIOD`` into a date.

    Supports ``YYYY-MM-DD`` (daily), ``YYYY-Www`` (weekly, anchors on
    the Friday of the ISO week) and ``YYYY-MM`` (monthly, anchors on
    the month-end). Monthly support added Sprint J for the MIR
    dataflow (mortgage interest rates).
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
    # Monthly (``YYYY-MM``) — anchor on the last day of the month.
    if len(time_period) == 7 and time_period[4] == "-":
        try:
            year = int(time_period[:4])
            month = int(time_period[5:])
        except ValueError:
            return None
        if month == 12:
            return date(year, 12, 31)
        next_first = date(year, month + 1, 1)
        return next_first - timedelta(days=1)
    try:
        return datetime.fromisoformat(time_period).date()
    except ValueError:
        return None


def _spf_quarter_to_date(time_period: str) -> date | None:
    """Parse ``YYYY-Qn`` into the first day of the quarter."""
    if len(time_period) != 7 or time_period[4:6] != "-Q":
        return None
    try:
        year = int(time_period[:4])
        quarter = int(time_period[6])
    except ValueError:
        return None
    if not 1 <= quarter <= 4:
        return None
    month = (quarter - 1) * 3 + 1
    return date(year, month, 1)


def _spf_derive_tenor(survey_year: int, horizon: str) -> str | None:
    """Derive canonical tenor from ``(survey_year, horizon)``.

    ``LT`` → ``"LTE"`` (long-term equivalent ≈ 5y ahead). Integer horizons
    within 0-3 years ahead map to ``"0Y"`` / ``"1Y"`` / ``"2Y"`` / ``"3Y"``.
    Everything else (≥ 4 years ahead, or target year in the past) returns
    ``None`` — SPF keeps legacy series in the response that aren't useful
    to M3.
    """
    if horizon == "LT":
        return "LTE"
    try:
        target_year = int(horizon)
    except ValueError:
        return None
    delta = target_year - survey_year
    if 0 <= delta <= 3:
        return f"{delta}Y"
    return None


def _parse_spf_csv(body: str) -> list[ExpInflationSurveyObservation]:
    """Parse SPF csvdata response into typed observations."""
    reader = csv.DictReader(io.StringIO(body))
    out: list[ExpInflationSurveyObservation] = []
    for row in reader:
        time_period = (row.get("TIME_PERIOD") or "").strip()
        raw_value = (row.get("OBS_VALUE") or "").strip()
        horizon = (row.get("FCT_HORIZON") or "").strip()
        if not time_period or not raw_value or raw_value in {"NA", "."}:
            continue
        try:
            value = float(raw_value)
        except ValueError:
            continue
        survey_date = _spf_quarter_to_date(time_period)
        if survey_date is None:
            continue
        tenor = _spf_derive_tenor(survey_date.year, horizon)
        out.append(
            ExpInflationSurveyObservation(
                survey_date=survey_date,
                horizon_year=horizon,
                tenor=tenor,
                value_pct=value,
            )
        )
    return out


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
