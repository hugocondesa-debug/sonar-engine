"""Trading Economics (TE) L0 connector — sovereign yields + economic-indicator fallback.

Week 3.5 scope: 10Y government bond yield historical daily via the
``/markets/historical`` endpoint with Bloomberg-style symbols
(``USGG10YR:IND``, ``GDBR10:IND``, etc.).

Week 6 Sprint 1 extension (CAL-092/086/093): fallback path for the
FRED-delisted US sentiment series (ISM Mfg, ISM Svc, NFIB) and the
DE sentiment series (Ifo, ZEW) via the
``/historical/country/{country}/indicator/{indicator}`` endpoint.

Auth: ``TE_API_KEY`` env (format ``key:secret``). Endpoints:

- Markets historical:
  ``.../markets/historical/<symbol>?c=<key>&d1=YYYY-MM-DD&d2=YYYY-MM-DD&f=json``
- Country indicator historical:
  ``.../historical/country/<country>/indicator/<indicator>?c=<key>&d1=...&d2=...&f=json``

Returned markets rows: ``{Symbol, Date (DD/MM/YYYY), Open, High, Low, Close}``
— yields in percent. We store ``yield_bps`` at the L0 boundary per
``conventions/units.md`` §Spreads (``int(round(close_pct * 100))``).

Returned indicator rows: ``{Country, Category, DateTime
(YYYY-MM-DDT...), Value, Frequency, HistoricalDataSymbol, ...}``. We
expose the flat ``(date, value)`` tuple via :class:`TEIndicatorObservation`.
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

from sonar.connectors.base import Observation
from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

log = structlog.get_logger()


# ISO 3166-1 alpha-2 → TE canonical country name (used by
# /historical/country/{country}/indicator/{indicator}).
# "GB" is the canonical alpha-2 for United Kingdom per ADR-0007;
# "UK" retained as deprecated alias (emits warning on lookup via
# :func:`_canonicalize_country_iso`).
TE_COUNTRY_NAME_MAP: dict[str, str] = {
    "US": "united states",
    "DE": "germany",
    "GB": "united kingdom",
    "UK": "united kingdom",  # deprecated alias — ADR-0007
    "JP": "japan",
    "CA": "canada",
    "AU": "australia",
    "NZ": "new zealand",
    "CH": "switzerland",
    "NO": "norway",
    "SE": "sweden",
    "DK": "denmark",
    "IT": "italy",
    "ES": "spain",
    "FR": "france",
    "NL": "netherlands",
    "PT": "portugal",
    # EA aggregate — TE publishes "euro area" under the ``stock market``
    # indicator (SX5E symbol) + a handful of aggregate macros. Added
    # Week 10 Sprint B equity index scaffolding (2026-04-22).
    "EA": "euro area",
}

# Canonical TE indicator names (verified empirically Week 6 Sprint 1
# pre-flight probe). TE labels the *headline* ISM PMI as "Business
# Confidence" (sourced from ISM) and the Ifo Business Climate headline
# likewise as "Business Confidence" under Germany. Store both the
# TE-facing name and an internal key for dispatch.
TE_INDICATOR_ISM_MFG_HEADLINE = "business confidence"
TE_INDICATOR_ISM_SVC_HEADLINE = "non manufacturing pmi"
TE_INDICATOR_NFIB = "nfib business optimism index"
TE_INDICATOR_IFO_HEADLINE = "business confidence"
TE_INDICATOR_ZEW_ECONOMIC_SENTIMENT = "zew economic sentiment index"
TE_INDICATOR_CONSUMER_CONFIDENCE = "consumer confidence"
TE_INDICATOR_MICHIGAN_5Y_INFLATION = "michigan 5 year inflation expectations"
TE_INDICATOR_INTEREST_RATE = "interest rate"
# Headline CPI year-over-year label per TE catalogue. Same slug powers
# both the historical (``/historical/country/.../indicator/inflation%20rate``)
# and forecast (``/forecast/country/.../indicator/inflation%20rate``)
# endpoints; the per-country HistoricalDataSymbol differs and is tracked
# individually in :data:`TE_CPI_YOY_EXPECTED_SYMBOL` so source drift
# surfaces cleanly. Week 10 Sprint F empirical probe 2026-04-22
# validated all 16 T1 countries via this slug.
TE_INDICATOR_INFLATION_RATE = "inflation rate"
# Per-country aggregate equity index (close price only — dividend yield
# + EPS + PE not exposed via this endpoint per Week 10 Sprint B probe
# 2026-04-22). Used as scaffolding for Phase 2.5 per-country ERP once
# fundamentals connectors land (CAL-ERP-COUNTRY-FUNDAMENTALS).
TE_INDICATOR_STOCK_MARKET = "stock market"

# Expected HistoricalDataSymbol values for the wrappers. Used as a
# source-identity guard: when TE reshuffles its catalogue, confirming
# the returned symbol still matches the expected one catches quiet
# mis-attribution early (Sprint 1 Week 6 closed CAL-093 on an
# incorrect premise for lack of this guard).
TE_EXPECTED_SYMBOL_CONFERENCE_BOARD_CC = "CONCCONF"
TE_EXPECTED_SYMBOL_MICHIGAN_5Y_INFLATION = "USAM5YIE"
TE_EXPECTED_SYMBOL_GB_BANK_RATE = "UKBRBASE"
# Per-country equity index source-identity guards (Week 10 Sprint B).
# TE surfaces the closing level of each market's flagship index under
# the country-indicator endpoint; the ``HistoricalDataSymbol`` pins the
# concrete benchmark so we catch reassignments (e.g. DE rotating DAX
# vs TecDAX) before quietly mis-attributing ERP inputs. Empirical
# values probed 2026-04-22. For JP, TE surfaces the Nikkei 225 (NKY),
# *not* TOPIX — retrospective notes the divergence from the original
# Sprint B brief which presumed TOPIX.
TE_EXPECTED_SYMBOL_DE_EQUITY_INDEX = "DAX"
TE_EXPECTED_SYMBOL_GB_EQUITY_INDEX = "UKX"
TE_EXPECTED_SYMBOL_JP_EQUITY_INDEX = "NKY"
TE_EXPECTED_SYMBOL_FR_EQUITY_INDEX = "CAC"
TE_EXPECTED_SYMBOL_EA_EQUITY_INDEX = "SX5E"

# Aggregated lookup — used by :meth:`TEConnector.fetch_equity_index_historical`
# to dispatch the guard symbol per ISO code without branching. Keyed on
# SONAR 2-letter country code; ``EA`` is the euro-area aggregate.
TE_EQUITY_INDEX_EXPECTED_SYMBOL: dict[str, str] = {
    "DE": TE_EXPECTED_SYMBOL_DE_EQUITY_INDEX,
    "GB": TE_EXPECTED_SYMBOL_GB_EQUITY_INDEX,
    "JP": TE_EXPECTED_SYMBOL_JP_EQUITY_INDEX,
    "FR": TE_EXPECTED_SYMBOL_FR_EQUITY_INDEX,
    "EA": TE_EXPECTED_SYMBOL_EA_EQUITY_INDEX,
}

# ---------------------------------------------------------------------------
# Multi-tenor sovereign yield curve symbols (CAL-138 Sprint)
# ---------------------------------------------------------------------------
#
# Bloomberg-style ``<PREFIX><TENOR>:IND`` symbols for TE
# ``/markets/historical`` endpoint. Empirical probe 2026-04-22 (Sprint
# CAL-138 Commit 1) mapped per-country tenor availability — only 3 of
# 9 non-EA T1 countries return ≥ MIN_OBSERVATIONS (6) tenors needed
# for any NSS fit:
#
# - **GB** (GUKG family): 12 tenors 1M-30Y — full Svensson.
# - **JP** (GJGB family): 9 tenors 1M-10Y — Svensson-minimum
#   (MIN_OBSERVATIONS_FOR_SVENSSON=9).
# - **CA** (GCAN family): 6 tenors 1M-10YR — NS-reduced fit
#   (MIN_OBSERVATIONS=6); large 2Y-10Y gap tracked under
#   CAL-CURVES-CA-MIDCURVE.
#
# AU/NZ/CH/SE/NO/DK empirical coverage is 0-2 tenors via TE — deferred
# under CAL-CURVES-T1-SPARSE (ship path: native CB yield-curve
# connectors Phase 2+).
#
# EA periphery remainder (FR / NL / PT) via TE 10Y-only (Bloomberg
# symbols GFRN10 / GNTH10YR / GSPT10YR) — deferred under per-country
# CAL items (CAL-CURVES-FR-BDF / CAL-CURVES-NL-DNB / CAL-CURVES-PT-BPSTAT)
# post Sprint A 2026-04-22 probe. IT + ES were in the same deferred
# cohort post Sprint G (national-CB HALT-0), but Sprint H (2026-04-22)
# shipped both via TE per-tenor cascade — the Sprint G brief §2 probe
# list had omitted TE (see Week 10 Sprint H retro + ADR-0009 addendum).
# Sprint H probe 2026-04-22 empirically confirmed 12-tenor IT coverage
# via the ``GBTPGR`` BTP family over the ``/markets/historical``
# endpoint. FR re-probe is tracked under CAL-CURVES-FR-TE-PROBE
# (opened Sprint H).
#
# Symbol quirks discovered empirically (do **not** normalise without a
# fresh probe — TE symbol naming is non-uniform):
# - GB: ``GUKG2:IND`` (no ``Y``), ``GUKG3Y:IND`` (with ``Y``),
#   ``GUKG5Y:IND``/``GUKG7Y:IND`` (with ``Y``), ``GUKG10:IND``/
#   ``GUKG15:IND``/``GUKG30:IND`` (no ``Y``), ``GUKG20Y:IND`` (with ``Y``).
# - JP: ``GJGB`` prefix with ``Y`` suffix for sub-10Y, no ``Y`` for 10Y.
# - CA: ``GCAN`` prefix with ``Y`` suffix for sub-10Y (``GCAN1Y:IND``
#   etc.), ``YR`` suffix for 10YR (``GCAN10YR:IND``).
# - IT (Sprint H): ``GBTPGR`` prefix; ``M`` suffix for sub-year, ``Y``
#   suffix for 1Y-7Y and 15Y-30Y, **no** suffix for 10Y (``GBTPGR10``).
#   Probe-empty tenors (``GBTPGR2``, ``GBTPGR3``, ``GBTPGR5``, ``GBTPGR7``,
#   ``GBTPGR15``, ``GBTPGR20``, ``GBTPGR30``, ``GBTPGR10YR``) were
#   rejected — see Sprint H retro matrix. 12 tenors total (full 1M-30Y
#   spectrum; Svensson-capable).
TE_YIELD_CURVE_SYMBOLS: dict[str, dict[str, str]] = {
    "GB": {
        "1M": "GUKG1M:IND",
        "3M": "GUKG3M:IND",
        "6M": "GUKG6M:IND",
        "1Y": "GUKG1Y:IND",
        "2Y": "GUKG2:IND",
        "3Y": "GUKG3Y:IND",
        "5Y": "GUKG5Y:IND",
        "7Y": "GUKG7Y:IND",
        "10Y": "GUKG10:IND",
        "15Y": "GUKG15:IND",
        "20Y": "GUKG20Y:IND",
        "30Y": "GUKG30:IND",
    },
    "JP": {
        "1M": "GJGB1M:IND",
        "3M": "GJGB3M:IND",
        "6M": "GJGB6M:IND",
        "1Y": "GJGB1Y:IND",
        "2Y": "GJGB2Y:IND",
        "3Y": "GJGB3Y:IND",
        "5Y": "GJGB5Y:IND",
        "7Y": "GJGB7Y:IND",
        "10Y": "GJGB10:IND",
    },
    "CA": {
        "1M": "GCAN1M:IND",
        "3M": "GCAN3M:IND",
        "6M": "GCAN6M:IND",
        "1Y": "GCAN1Y:IND",
        "2Y": "GCAN2Y:IND",
        "10Y": "GCAN10YR:IND",
    },
    "IT": {
        "1M": "GBTPGR1M:IND",
        "3M": "GBTPGR3M:IND",
        "6M": "GBTPGR6M:IND",
        "1Y": "GBTPGR1Y:IND",
        "2Y": "GBTPGR2Y:IND",
        "3Y": "GBTPGR3Y:IND",
        "5Y": "GBTPGR5Y:IND",
        "7Y": "GBTPGR7Y:IND",
        "10Y": "GBTPGR10:IND",
        "15Y": "GBTPGR15Y:IND",
        "20Y": "GBTPGR20Y:IND",
        "30Y": "GBTPGR30Y:IND",
    },
}

# Tenor label → years lookup for constructing Observation rows. Kept
# local (duplicates the ``overlays.nss._TENOR_LABEL_TO_YEARS`` table)
# to avoid a connector → overlay import; drift caught by the
# ``test_te_yield_curve_tenor_years_match_nss`` sanity test.
_TE_TENOR_YEARS: dict[str, float] = {
    "1M": 1 / 12,
    "3M": 0.25,
    "6M": 0.5,
    "1Y": 1.0,
    "2Y": 2.0,
    "3Y": 3.0,
    "5Y": 5.0,
    "7Y": 7.0,
    "10Y": 10.0,
    "15Y": 15.0,
    "20Y": 20.0,
    "30Y": 30.0,
}
# Deprecated alias for :data:`TE_EXPECTED_SYMBOL_GB_BANK_RATE` per
# ADR-0007 (UK → GB canonical rename). Removed Week 10 Day 1.
TE_EXPECTED_SYMBOL_UK_BANK_RATE = TE_EXPECTED_SYMBOL_GB_BANK_RATE
TE_EXPECTED_SYMBOL_JP_BANK_RATE = "BOJDTR"
TE_EXPECTED_SYMBOL_CA_BANK_RATE = "CCLR"
TE_EXPECTED_SYMBOL_AU_CASH_RATE = "RBATCTR"
TE_EXPECTED_SYMBOL_NZ_OCR = "NZOCRS"
# SNB policy rate mirror. Symbol inherits the legacy "Swiss LIBOR
# Target Rate" identifier (``SZLTTR``) even though SNB migrated from a
# 3M-CHF-LIBOR target midpoint (pre-2019) to a directly-set SNB policy
# rate (2019-now) — TE preserves the single-series contract across the
# regime change. Sprint V empirical probe 2026-04-21 confirmed all 341
# observations (2000-01-03 → 2026-03-19) carry ``SZLTTR``, including
# the 93 rows spanning the negative-rate era 2014-12-18 → 2022-08-31.
TE_EXPECTED_SYMBOL_CH_POLICY_RATE = "SZLTTR"
# Norges Bank policy rate (sight deposit rate / key policy rate).
# Symbol ``NOBRDEP`` ("Norwegian Bank Rate Deposit") identifies the
# sight-deposit-rate series TE sources from Norges Bank. Sprint X-NO
# empirical probe 2026-04-22 confirmed all 504 observations
# (1991-01-01 → 2026-03-26) carry ``NOBRDEP`` — single-series contract
# across every regime (Norway never ran a negative policy rate; the
# minimum observed is 0 % during the 2020-2022 COVID-response trough).
TE_EXPECTED_SYMBOL_NO_POLICY_RATE = "NOBRDEP"
# Riksbank policy rate ("styrränta"; called "repo rate" / "reporänta"
# prior to 2022-06-08 but the series is continuous across the rename).
# TE ships under ``SWRRATEI`` — the legacy "Swedish Repo Rate
# Indicator" code preserved across the 2022 rename. Sprint W-SE
# empirical probe 2026-04-22 confirmed all 463 observations
# (1994-05-26 → 2026-04-30) carry ``SWRRATEI``, including the 58 rows
# spanning the negative-rate era 2015-02-12 → 2019-11-30 (min -0.50 %).
TE_EXPECTED_SYMBOL_SE_POLICY_RATE = "SWRRATEI"
# Danmarks Nationalbanken policy rate as exposed by TE. Symbol
# ``DEBRDISC`` ("Denmark Bank Rate Discount") identifies the legacy
# **discount rate** (``diskontoen``) — Nationalbanken's historical
# benchmark rate. Crucially this is *not* the active EUR-peg defence
# tool: Nationalbanken manages the DKK/EUR peg via the **certificate-
# of-deposit (CD) rate** (``indskudsbevisrenten``), and the two
# instruments diverged sharply across the 2014-2022 negative-rate
# corridor (CD trough -0.75 % at 2015-04-07; discount only briefly
# negative 2021-2022 with min -0.60 %). The native Statbank cascade
# layer (:class:`NationalbankenConnector`) consumes the CD rate
# (``OIBNAA``) explicitly so the cascade emits both representations
# and downstream consumers can pick the right semantic — Sprint Y-DK
# documents the divergence in retro §4. Sprint Y-DK probe 2026-04-22
# confirmed all 464 observations (1987-08-31 → 2026-03-31) carry
# ``DEBRDISC``, including 18 strictly-negative rows spanning
# 2021-03-31 → 2022-08-31 (min -0.60 %).
TE_EXPECTED_SYMBOL_DK_POLICY_RATE = "DEBRDISC"

# ---------------------------------------------------------------------------
# CPI YoY per-country HistoricalDataSymbol guards (Week 10 Sprint F)
# ---------------------------------------------------------------------------
#
# Empirical probe 2026-04-22 mapped the TE ``inflation rate`` indicator
# to per-country symbols. Keyed on SONAR 2-letter code. All 16 T1
# countries are covered — no EA member requires ECB SDW fallback at
# this sprint's scope (brief §5 HALT-1 evaluated: not triggered).
#
# Frequency / coverage quirks documented individually:
#
# - **US** ``"CPI YOY"``: note the literal space in the symbol. Monthly
#   cadence, 1914-12 → present (1335+ observations).
# - **AU** ``AUCPIYOY``: monthly cadence **only since 2025-04-30** per
#   ABS Monthly CPI Indicator (introduced 2022-11 by ABS but TE's
#   coverage starts later). Quarterly headline CPI remains ABS's
#   authoritative publication; AU consumers must tolerate a sparse
#   monthly series (11 observations at Sprint F probe 2026-04-22). The
#   downstream M2 AU builder emits ``AU_M2_CPI_SPARSE_MONTHLY`` when
#   the returned window contains fewer than 12 observations.
# - **NZ** ``NZCPIYOY``: **Quarterly** cadence (StatsNZ publishes CPI
#   quarterly, and TE mirrors the native frequency — unlike most T1
#   countries where the TE slug aggregates to monthly). 417
#   observations back to 1918-09-30. The M2 NZ builder emits
#   ``NZ_M2_CPI_QUARTERLY`` on every persist to record the lower
#   cadence.
# - **SE** ``SWCPYOY``: 7-character symbol (no ``I`` between ``W`` and
#   ``C``) — empirically verified; do not "normalise" to ``SWCPIYOY``.
# - **PT** ``PLCPYOY``: 7-character symbol prefixed ``PL`` (not ``PT``).
#   TE's legacy convention retained across the Eurozone migration.
# - **GB** ``UKRPCJYR``: **not** ``UKCPIYOY``. TE retains the "UK
#   Retail Price Consumer — Jevons Year" code for the ONS headline
#   CPI series even post ADR-0007 rename; values align with ONS CPIH
#   ex-owner-occupied-housing (headline CPI). Do not confuse with
#   RPI or RPIX — the series under this symbol is the modern CPI.
TE_EXPECTED_SYMBOL_US_CPI_YOY = "CPI YOY"  # literal space — do not normalise
TE_EXPECTED_SYMBOL_DE_CPI_YOY = "GRBC20YY"
TE_EXPECTED_SYMBOL_FR_CPI_YOY = "FRCPIYOY"
TE_EXPECTED_SYMBOL_IT_CPI_YOY = "ITCPNICY"
TE_EXPECTED_SYMBOL_ES_CPI_YOY = "SPIPCYOY"
TE_EXPECTED_SYMBOL_NL_CPI_YOY = "NECPIYOY"
TE_EXPECTED_SYMBOL_PT_CPI_YOY = "PLCPYOY"
TE_EXPECTED_SYMBOL_GB_CPI_YOY = "UKRPCJYR"
TE_EXPECTED_SYMBOL_JP_CPI_YOY = "JNCPIYOY"
TE_EXPECTED_SYMBOL_CA_CPI_YOY = "CACPIYOY"
TE_EXPECTED_SYMBOL_AU_CPI_YOY = "AUCPIYOY"
TE_EXPECTED_SYMBOL_NZ_CPI_YOY = "NZCPIYOY"
TE_EXPECTED_SYMBOL_CH_CPI_YOY = "SZCPIYOY"
TE_EXPECTED_SYMBOL_SE_CPI_YOY = "SWCPYOY"
TE_EXPECTED_SYMBOL_NO_CPI_YOY = "NOCPIYOY"
TE_EXPECTED_SYMBOL_DK_CPI_YOY = "DNCPIYOY"

TE_CPI_YOY_EXPECTED_SYMBOL: dict[str, str] = {
    "US": TE_EXPECTED_SYMBOL_US_CPI_YOY,
    "DE": TE_EXPECTED_SYMBOL_DE_CPI_YOY,
    "FR": TE_EXPECTED_SYMBOL_FR_CPI_YOY,
    "IT": TE_EXPECTED_SYMBOL_IT_CPI_YOY,
    "ES": TE_EXPECTED_SYMBOL_ES_CPI_YOY,
    "NL": TE_EXPECTED_SYMBOL_NL_CPI_YOY,
    "PT": TE_EXPECTED_SYMBOL_PT_CPI_YOY,
    "GB": TE_EXPECTED_SYMBOL_GB_CPI_YOY,
    "JP": TE_EXPECTED_SYMBOL_JP_CPI_YOY,
    "CA": TE_EXPECTED_SYMBOL_CA_CPI_YOY,
    "AU": TE_EXPECTED_SYMBOL_AU_CPI_YOY,
    "NZ": TE_EXPECTED_SYMBOL_NZ_CPI_YOY,
    "CH": TE_EXPECTED_SYMBOL_CH_CPI_YOY,
    "SE": TE_EXPECTED_SYMBOL_SE_CPI_YOY,
    "NO": TE_EXPECTED_SYMBOL_NO_CPI_YOY,
    "DK": TE_EXPECTED_SYMBOL_DK_CPI_YOY,
}


@dataclass(frozen=True, slots=True)
class TEIndicatorObservation:
    """Single historical observation from TE's country-indicator endpoint."""

    observation_date: date
    value: float
    country: str  # ISO alpha-2, uppercase
    indicator: str  # canonical lowercase TE name
    source: str = "TE"
    frequency: str = ""  # "Monthly", "Quarterly", etc.
    historical_data_symbol: str = ""  # TE "HistoricalDataSymbol" — source id


@dataclass(frozen=True, slots=True)
class TEInflationForecast:
    """Projection row from TE's ``/forecast/country/.../indicator/inflation rate`` endpoint.

    TE exposes four quarterly projections (``q1``..``q4``) plus three
    year-end projections (``year_end``..``year_end_3``) per country.
    The per-quarter dates anchor each value so downstream consumers do
    not have to infer the publication offset (TE typically publishes q1
    as "next quarter after the latest historical observation"; varies
    per country by weeks). ``forecast_last_update`` records when TE
    last revised the projection so consumers can enforce a freshness
    SLA (M2 Taylor-gap consumers flag ``*_INFLATION_FORECAST_STALE``
    when this timestamp is more than 90 days old).

    ``forecast_12m_pct`` exposes the closest match to the 12-month-ahead
    horizon M2 Taylor-forward variants consume. Empirically this is
    ``q4`` (publishing offset of ~3 quarters from latest observation is
    typical across TE's T1 coverage); if the publication schedule
    shifts, consumers can fall back to ``year_end`` via
    :attr:`forecast_year_end_pct`.
    """

    country: str  # ISO alpha-2, uppercase
    indicator: str  # canonical lowercase TE name ("inflation rate")
    historical_data_symbol: str  # matches the historical wrapper's guard
    latest_value_pct: float  # most recent historical observation value
    latest_value_date: date
    forecast_12m_pct: float  # ≈ q4 (~12m-ahead horizon)
    forecast_12m_date: date
    forecast_year_end_pct: float  # current calendar year end
    forecast_year_end_2_pct: float | None = None
    forecast_year_end_3_pct: float | None = None
    forecast_q1_pct: float | None = None
    forecast_q1_date: date | None = None
    forecast_q2_pct: float | None = None
    forecast_q2_date: date | None = None
    forecast_q3_pct: float | None = None
    forecast_q3_date: date | None = None
    frequency: str = ""
    source: str = "TE"
    forecast_last_update: datetime | None = None


# SONAR 2-letter country code → TE 10Y Bloomberg symbol. GB is
# canonical (ADR-0007); UK alias preserved for backward compat.
TE_10Y_SYMBOLS: dict[str, str] = {
    "US": "USGG10YR:IND",
    "DE": "GDBR10:IND",
    "GB": "GUKG10:IND",
    "UK": "GUKG10:IND",  # deprecated alias — ADR-0007
    "JP": "GJGB10:IND",
    "IT": "GBTPGR10:IND",
    "ES": "GSPG10YR:IND",
    "FR": "GFRN10:IND",
    "NL": "GNTH10YR:IND",
    "PT": "GSPT10YR:IND",
}


class TEConnector:
    """L0 connector for TradingEconomics markets historical yields."""

    BASE_URL = "https://api.tradingeconomics.com"

    def __init__(
        self,
        api_key: str,
        cache_dir: str | Path,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        # Call counter for Pro-tier quota telemetry (10k/mês). Incremented
        # on every successful fetch against either endpoint. Reset via
        # :meth:`reset_call_count`.
        self._call_count: int = 0

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(self, symbol: str, start: date, end: date) -> list[dict[str, Any]]:
        url = f"{self.BASE_URL}/markets/historical/{symbol}"
        params = {
            "c": self.api_key,
            "d1": start.isoformat(),
            "d2": end.isoformat(),
            "f": "json",
        }
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        payload = r.json()
        return cast("list[dict[str, Any]]", payload or [])

    async def fetch_sovereign_yield_historical(
        self,
        country: str,
        tenor: str,
        start: date,
        end: date,
    ) -> list[Observation]:
        """Return daily 10Y yields (as Observations with ``yield_bps``).

        Week 3.5 supports ``tenor == "10Y"`` only — TE covers the
        full curve for most T1 countries but mapping the long-end
        is sufficient for the CRP vol_ratio use case.

        Raises:
            ValueError: unknown country or unsupported tenor.
        """
        if tenor != "10Y":
            msg = f"TEConnector supports tenor='10Y' only for Week 3.5; got {tenor}"
            raise ValueError(msg)
        symbol = TE_10Y_SYMBOLS.get(country)
        if symbol is None:
            msg = f"Unknown TE 10Y symbol for country: {country}"
            raise ValueError(msg)

        cache_key = f"te:{symbol}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("te.cache_hit", symbol=symbol)
            return cast("list[Observation]", cached)

        rows = await self._fetch_raw(symbol, start, end)
        out: list[Observation] = []
        for row in rows:
            raw_date = row.get("Date")
            raw_close = row.get("Close")
            if not raw_date or raw_close is None:
                continue
            # TE format: "DD/MM/YYYY"
            try:
                obs_date = datetime.strptime(str(raw_date), "%d/%m/%Y").replace(tzinfo=UTC).date()
                close_pct = float(raw_close)
            except (ValueError, TypeError):
                continue
            out.append(
                Observation(
                    country_code=country,
                    observation_date=obs_date,
                    tenor_years=10.0,
                    yield_bps=round(close_pct * 100),
                    source="TE",
                    source_series_id=symbol,
                )
            )
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        log.info("te.fetched", symbol=symbol, n=len(out))
        return out

    async def fetch_10y_window_around(
        self,
        country: str,
        observation_date: date,
        lookback_days: int = 365 * 5 + 30,
    ) -> list[Observation]:
        """Return 5Y of daily 10Y yields ending at ``observation_date``.

        Convenience wrapper used by ``overlays/crp.py`` vol_ratio
        computation which needs ≥ 750 business-day observations.
        """
        start = observation_date - timedelta(days=lookback_days)
        return await self.fetch_sovereign_yield_historical(country, "10Y", start, observation_date)

    # -------------------------------------------------------------------
    # Economic-indicator fallback (CAL-092/086/093) — Week 6 Sprint 1
    # -------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_indicator_raw(
        self, country_name: str, indicator_name: str, start: date, end: date
    ) -> list[dict[str, Any]]:
        url = f"{self.BASE_URL}/historical/country/{country_name}/indicator/{indicator_name}"
        params = {
            "c": self.api_key,
            "d1": start.isoformat(),
            "d2": end.isoformat(),
            "f": "json",
        }
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        payload = r.json()
        if not isinstance(payload, list):
            err = (
                f"TE indicator response non-list: country={country_name!r} "
                f"indicator={indicator_name!r} type={type(payload).__name__}"
            )
            raise DataUnavailableError(err)
        return cast("list[dict[str, Any]]", payload)

    async def fetch_indicator(
        self,
        country_iso: str,
        indicator_name: str,
        start_date: date,
        end_date: date,
    ) -> list[TEIndicatorObservation]:
        """Fetch a TE economic indicator time series.

        ``country_iso`` is the SONAR 2-letter code (``"US"``, ``"DE"`` …);
        mapped to TE's canonical country slug via
        :data:`TE_COUNTRY_NAME_MAP`. ``indicator_name`` is the exact TE
        lowercase label (see ``TE_INDICATOR_*`` constants).

        Empty response for the (country, indicator) pair raises
        :class:`DataUnavailableError`. Per-row missing ``Value`` /
        ``DateTime`` is skipped. Cached 24h.
        """
        country_name = TE_COUNTRY_NAME_MAP.get(country_iso.upper())
        if country_name is None:
            msg = f"Unknown TE country mapping: {country_iso!r}"
            raise ValueError(msg)

        cache_key = (
            f"te_ind:{country_iso.upper()}:{indicator_name}:"
            f"{start_date.isoformat()}:{end_date.isoformat()}"
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug(
                "te.indicator.cache_hit",
                country=country_iso,
                indicator=indicator_name,
            )
            return list(cached)

        rows = await self._fetch_indicator_raw(country_name, indicator_name, start_date, end_date)
        self._call_count += 1
        log.info(
            "te.call",
            indicator=indicator_name,
            country=country_iso,
            cumulative_calls=self._call_count,
        )

        if not rows:
            err = f"TE returned empty series: country={country_iso!r} indicator={indicator_name!r}"
            raise DataUnavailableError(err)

        out: list[TEIndicatorObservation] = []
        for row in rows:
            raw_date = row.get("DateTime")
            raw_value = row.get("Value")
            if raw_date is None or raw_value is None:
                continue
            try:
                obs_date = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00")).date()
                val = float(raw_value)
            except (TypeError, ValueError):
                continue
            out.append(
                TEIndicatorObservation(
                    observation_date=obs_date,
                    value=val,
                    country=country_iso.upper(),
                    indicator=indicator_name,
                    frequency=str(row.get("Frequency", "")),
                    historical_data_symbol=str(row.get("HistoricalDataSymbol", "")),
                )
            )
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        return out

    # -------------------------------------------------------------------
    # Forecast endpoint (Week 10 Sprint F — CAL-CPI-INFL-T1-WRAPPERS)
    # -------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_forecast_raw(
        self, country_name: str, indicator_name: str
    ) -> list[dict[str, Any]]:
        url = f"{self.BASE_URL}/forecast/country/{country_name}/indicator/{indicator_name}"
        params = {"c": self.api_key, "f": "json"}
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        payload = r.json()
        if not isinstance(payload, list):
            err = (
                f"TE forecast response non-list: country={country_name!r} "
                f"indicator={indicator_name!r} type={type(payload).__name__}"
            )
            raise DataUnavailableError(err)
        return cast("list[dict[str, Any]]", payload)

    async def fetch_inflation_forecast(
        self,
        country_iso: str,
        observation_date: date,
    ) -> TEInflationForecast:
        """Fetch TE's inflation-rate forecast for ``country_iso``.

        Queries ``/forecast/country/{country}/indicator/inflation rate``
        — the TE forecast surface for headline CPI YoY. The endpoint
        returns a single projection row per country with:

        - ``LatestValue`` + ``LatestValueDate``: the most recent
          historical observation (matches the final row of the
          ``fetch_indicator`` historical series).
        - ``q1``..``q4`` + matching ``q*_date``: four quarterly
          projections ahead of ``LatestValueDate``. q4 is the closest
          stable proxy for a 12-month-ahead forecast (publishing offset
          typically three quarters).
        - ``YearEnd``..``YearEnd3``: current-calendar-year and next two
          calendar-year-end forecasts. Used as fallback for 12m-ahead
          when the quarterly offset is ambiguous (e.g. when TE delays
          updating q4 beyond the 90-day freshness SLA).
        - ``HistoricalDataSymbol``: matches the historical series;
          callers asserting identity reuse the single per-country
          symbol table :data:`TE_CPI_YOY_EXPECTED_SYMBOL`.

        ``observation_date`` is used only for cache partitioning — the
        TE forecast endpoint exposes the *current* projection, not a
        historical snapshot, so we cache per anchor-date so that
        integration tests and deterministic backtests see stable values
        for a given date. Cache TTL matches the historical endpoint.

        Empty response raises :class:`DataUnavailableError`.
        """
        country_upper = country_iso.upper()
        country_name = TE_COUNTRY_NAME_MAP.get(country_upper)
        if country_name is None:
            msg = f"Unknown TE country mapping: {country_iso!r}"
            raise ValueError(msg)

        cache_key = (
            f"te_fcst:{country_upper}:{TE_INDICATOR_INFLATION_RATE}:{observation_date.isoformat()}"
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug(
                "te.forecast.cache_hit",
                country=country_upper,
                indicator=TE_INDICATOR_INFLATION_RATE,
            )
            return cast("TEInflationForecast", cached)

        rows = await self._fetch_forecast_raw(country_name, TE_INDICATOR_INFLATION_RATE)
        self._call_count += 1
        log.info(
            "te.forecast.call",
            indicator=TE_INDICATOR_INFLATION_RATE,
            country=country_upper,
            cumulative_calls=self._call_count,
        )

        if not rows:
            err = (
                f"TE forecast empty: country={country_iso!r} "
                f"indicator={TE_INDICATOR_INFLATION_RATE!r}"
            )
            raise DataUnavailableError(err)

        row = rows[0]
        parsed = _parse_forecast_row(row, country_upper, TE_INDICATOR_INFLATION_RATE)
        self.cache.set(cache_key, parsed, ttl=DEFAULT_TTL_SECONDS)
        return parsed

    # -------------------------------------------------------------------
    # CAL-targeted convenience wrappers (Week 6 Sprint 1 c2)
    # -------------------------------------------------------------------

    async def fetch_ism_manufacturing_us(
        self, start: date, end: date
    ) -> list[TEIndicatorObservation]:
        """US ISM Manufacturing PMI headline (TE labels as 'Business Confidence')."""
        return await self.fetch_indicator("US", TE_INDICATOR_ISM_MFG_HEADLINE, start, end)

    async def fetch_ism_services_us(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """US ISM Services PMI headline ('Non Manufacturing PMI' on TE)."""
        return await self.fetch_indicator("US", TE_INDICATOR_ISM_SVC_HEADLINE, start, end)

    async def fetch_nfib_us(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """US NFIB Small Business Optimism Index."""
        return await self.fetch_indicator("US", TE_INDICATOR_NFIB, start, end)

    async def fetch_ifo_business_climate_de(
        self, start: date, end: date
    ) -> list[TEIndicatorObservation]:
        """DE Ifo Business Climate headline (TE labels as 'Business Confidence')."""
        return await self.fetch_indicator("DE", TE_INDICATOR_IFO_HEADLINE, start, end)

    async def fetch_zew_economic_sentiment_de(
        self, start: date, end: date
    ) -> list[TEIndicatorObservation]:
        """DE ZEW Economic Sentiment Index."""
        return await self.fetch_indicator("DE", TE_INDICATOR_ZEW_ECONOMIC_SENTIMENT, start, end)

    async def fetch_conference_board_cc_us(
        self, start: date, end: date
    ) -> list[TEIndicatorObservation]:
        """US Conference Board Consumer Confidence Index.

        TE indicator name: ``consumer confidence`` (Category same).
        Source: The Conference Board (``HistoricalDataSymbol=CONCCONF``).
        Monthly cadence.

        Week 6 Sprint 3 (CAL-093 re-open + resolve): an earlier sprint
        closed this CAL on the incorrect premise that TE's
        ``consumer confidence`` feed for the US was UMich-sourced.
        Empirical probe disproves — every observation carries
        ``CONCCONF`` as its ``HistoricalDataSymbol``, which is the
        Conference Board series. This wrapper guards the premise by
        asserting the first returned row's symbol matches
        :data:`TE_EXPECTED_SYMBOL_CONFERENCE_BOARD_CC`; on mismatch we
        raise :class:`DataUnavailableError` so callers can handle the
        drift explicitly.
        """
        obs = await self.fetch_indicator("US", TE_INDICATOR_CONSUMER_CONFIDENCE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_CONFERENCE_BOARD_CC)
        ):
            err = (
                "TE consumer-confidence source drift: expected "
                f"{TE_EXPECTED_SYMBOL_CONFERENCE_BOARD_CC!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_michigan_5y_inflation_us(
        self, start: date, end: date
    ) -> list[TEIndicatorObservation]:
        """US UMich 5-year inflation expectations (Survey of Consumers).

        TE indicator name: ``michigan 5 year inflation expectations``.
        Source: University of Michigan Survey of Consumers
        (``HistoricalDataSymbol=USAM5YIE``). Monthly cadence.

        Substitutes the FRED ``MICHM5YM5`` series delisted during
        Sprint 2a live validation. Guards source identity via the
        ``USAM5YIE`` symbol check, same pattern as Conference Board.
        """
        obs = await self.fetch_indicator("US", TE_INDICATOR_MICHIGAN_5Y_INFLATION, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(
                TE_EXPECTED_SYMBOL_MICHIGAN_5Y_INFLATION
            )
        ):
            err = (
                "TE michigan-5y source drift: expected "
                f"{TE_EXPECTED_SYMBOL_MICHIGAN_5Y_INFLATION!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_jp_bank_rate(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """JP Bank Rate — BoJ policy-rate series, TE-sourced.

        TE ``interest rate`` indicator for ``japan`` returns the BoJ
        uncollateralized overnight call rate (HistoricalDataSymbol
        ``BOJDTR`` — Bank of Japan Discount & Target Rate feed). Daily
        cadence, one row per rate-change announcement; the series
        back-fills the full decision history regardless of ``d1``/``d2``.

        Chosen as the **primary** source for JP M1 policy-rate inputs
        (Sprint L) per the Sprint I-patch cascade pattern — TE is daily
        and BoJ-sourced, while the FRED OECD mirror ``IRSTCI01JPM156N``
        is monthly-lagged. The native BoJ TSD probe during Sprint L
        pre-flight found the portal form-based (Shift_JIS) with no
        documented JSON/CSV endpoint, so the BoJ connector ships as a
        wire-ready scaffold and TE primary carries JP.

        Guards source identity via the ``BOJDTR`` symbol check
        mirroring the Conference Board / Michigan-5Y / GB-Bank-Rate
        wrappers; on drift raises :class:`DataUnavailableError` so the
        JP cascade can fall back cleanly.
        """
        obs = await self.fetch_indicator("JP", TE_INDICATOR_INTEREST_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_JP_BANK_RATE)
        ):
            err = (
                "TE JP-bank-rate source drift: expected "
                f"{TE_EXPECTED_SYMBOL_JP_BANK_RATE!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_ca_bank_rate(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """CA Bank Rate — BoC policy-rate (overnight target), TE-sourced.

        TE ``interest rate`` indicator for ``canada`` returns the BoC
        target for the overnight rate directly (HistoricalDataSymbol
        ``CCLR`` — Canadian Central Lending Rate feed). Daily cadence
        back-filled to 1990-02-07 (~2320 observations at Sprint S probe,
        2026-04-21); TE surfaces each rate-change announcement plus the
        constant intervening quotes so a single query returns the full
        decision history regardless of ``d1``/``d2``.

        Chosen as the **primary** source for CA M1 policy-rate inputs
        (Sprint S) per the Sprint I-patch cascade pattern — TE is daily
        and BoC-sourced, and the BoC Valet native connector (Sprint S
        C2) sits in the secondary slot as a first-class robust fallback
        because the Valet JSON REST API is public and reachable. FRED
        OECD mirror ``IRSTCI01CAM156N`` is relegated to last-resort
        with staleness flags.

        Guards source identity via the ``CCLR`` symbol check mirroring
        the Conference Board / Michigan-5Y / GB / JP wrappers; on drift
        raises :class:`DataUnavailableError` so the CA cascade can fall
        back cleanly.
        """
        obs = await self.fetch_indicator("CA", TE_INDICATOR_INTEREST_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_CA_BANK_RATE)
        ):
            err = (
                "TE CA-bank-rate source drift: expected "
                f"{TE_EXPECTED_SYMBOL_CA_BANK_RATE!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_au_cash_rate(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """AU Cash Rate — RBA policy-rate (cash-rate target), TE-sourced.

        TE ``interest rate`` indicator for ``australia`` returns the RBA
        target cash rate directly (HistoricalDataSymbol ``RBATCTR`` —
        Reserve Bank of Australia Target Cash Rate feed). Daily cadence
        back-filled to 1990-01-22 (~330 observations at Sprint T probe,
        2026-04-21); TE surfaces each rate-change announcement plus the
        constant intervening quotes so a single query returns the full
        decision history regardless of ``d1``/``d2``.

        Chosen as the **primary** source for AU M1 policy-rate inputs
        (Sprint T) per the Sprint I-patch cascade pattern — TE is daily
        and RBA-sourced, and the RBA F1 statistical-table CSV (Sprint T
        C2) sits in the secondary slot as a first-class robust fallback
        because ``f1-data.csv`` is a public static CSV with a descriptive
        user-agent (the Akamai edge rejects generic ``Mozilla/5.0`` but
        accepts a project-identifying UA — empirical probe 2026-04-21).
        FRED OECD mirror ``IRSTCI01AUM156N`` is relegated to last-resort
        with staleness flags.

        Guards source identity via the ``RBATCTR`` symbol check mirroring
        the Conference Board / Michigan-5Y / GB / JP / CA wrappers; on
        drift raises :class:`DataUnavailableError` so the AU cascade can
        fall back cleanly.
        """
        obs = await self.fetch_indicator("AU", TE_INDICATOR_INTEREST_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_AU_CASH_RATE)
        ):
            err = (
                "TE AU-cash-rate source drift: expected "
                f"{TE_EXPECTED_SYMBOL_AU_CASH_RATE!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_nz_ocr(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """NZ Official Cash Rate — RBNZ policy-rate, TE-sourced.

        TE ``interest rate`` indicator for ``new zealand`` returns the
        RBNZ Official Cash Rate (HistoricalDataSymbol ``NZOCRS``).
        Empirical probe 2026-04-21 (Week 9 Sprint U pre-flight) confirmed
        the symbol, with the series back-filled to 1985-01 and surfaced
        at daily cadence for the OCR regime (post-1999 inception) —
        pre-1999 values reflect legacy RBNZ policy-rate proxies TE
        consolidates under the same interest-rate indicator.

        Chosen as the **primary** source for NZ M1 policy-rate inputs
        (Sprint U-NZ) per the Sprint I-patch cascade pattern: TE is
        daily and RBNZ-sourced, whereas the FRED OECD mirror
        (``IRSTCI01NZM156N``) updates only monthly. The RBNZ
        statistical-tables CSVs sit in the secondary slot as a wire-
        ready scaffold — the www.rbnz.govt.nz host **403s at the
        perimeter regardless of User-Agent** (Sprint U probe
        2026-04-21 confirmed this against both Mozilla and descriptive
        ``SONAR/2.0`` UAs), so the RBNZ connector ships raising
        :class:`DataUnavailableError` until the host-level block lifts
        (CAL-NZ-RBNZ-TABLES).

        Guards source identity via the ``NZOCRS`` symbol check
        mirroring the Conference Board / Michigan-5Y / GB / JP / CA /
        AU wrappers; on drift raises :class:`DataUnavailableError` so
        the NZ cascade can fall back cleanly.
        """
        obs = await self.fetch_indicator("NZ", TE_INDICATOR_INTEREST_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_NZ_OCR)
        ):
            err = (
                "TE NZ-OCR source drift: expected "
                f"{TE_EXPECTED_SYMBOL_NZ_OCR!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_ch_policy_rate(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """CH Policy Rate — SNB policy-rate series, TE-sourced.

        TE ``interest rate`` indicator for ``switzerland`` returns the
        SNB policy rate directly (HistoricalDataSymbol ``SZLTTR`` —
        legacy "Swiss LIBOR Target Rate" identifier, preserved by TE
        across the 2019 regime change when SNB dropped the 3M-CHF-LIBOR
        target midpoint in favour of a directly-set policy rate). Daily
        cadence back-filled to 2000-01-03 (~341 observations at Sprint V
        probe, 2026-04-21); TE surfaces each rate-change announcement
        plus the constant intervening quotes so a single query returns
        the full decision history regardless of ``d1``/``d2``.

        **Negative-rate era preservation**: 93 rows across 2014-12-18 →
        2022-08-31 carry negative values (minimum -0.75 %, the deepest
        negative-rate regime of any G10 central bank). The wrapper (and
        the downstream builder) preserve the sign throughout — the
        ``int(round(value * 100))`` conversion at the Observation layer
        handles negative yields naturally via Python's round-half-even
        semantics, and no clamp is applied. Cascade callers emit
        ``CH_NEGATIVE_RATE_ERA_DATA`` when the returned window contains
        at least one strictly-negative observation.

        Chosen as the **primary** source for CH M1 policy-rate inputs
        (Sprint V) per the Sprint I-patch cascade pattern — TE is daily
        and SNB-sourced, while the SNB data-portal native path (Sprint
        V C2) covers overnight-money-market rates (SARON) via the
        ``zimoma`` cube at monthly cadence. FRED OECD mirror
        ``IRSTCI01CHM156N`` is relegated to last-resort with staleness
        flags.

        Guards source identity via the ``SZLTTR`` symbol check mirroring
        the GB / JP / CA / AU wrappers; on drift raises
        :class:`DataUnavailableError` so the CH cascade can fall back
        cleanly.
        """
        obs = await self.fetch_indicator("CH", TE_INDICATOR_INTEREST_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_CH_POLICY_RATE)
        ):
            err = (
                "TE CH-policy-rate source drift: expected "
                f"{TE_EXPECTED_SYMBOL_CH_POLICY_RATE!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_no_policy_rate(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """NO Policy Rate — Norges Bank key policy (sight-deposit) rate, TE-sourced.

        TE ``interest rate`` indicator for ``norway`` returns the Norges
        Bank key policy rate directly (HistoricalDataSymbol ``NOBRDEP``
        — "Norwegian Bank Rate Deposit", TE's identifier for the
        sight-deposit-rate series Norges Bank has targeted since the
        inflation-targeting regime began in 2001). Daily cadence
        back-filled to 1991-01-01 (504 observations at Sprint X-NO
        probe, 2026-04-22); TE surfaces each rate-change announcement
        plus the constant intervening quotes so a single query returns
        the full decision history.

        **Standard positive-only processing** (contrast CH Sprint V):
        Norway never ran a negative policy rate across the full 35-year
        history. The minimum observation is 0 % during the
        2020-05-08 → 2021-09-24 COVID-response trough; across the
        2014-2022 global negative-rate era when SNB / ECB / BoJ / Riksbank
        all breached zero, Norges Bank stayed at 0.5 % (or above). No
        ``_NEGATIVE_RATE_ERA_DATA`` flag is emitted because the wrapper
        never sees negative inputs — if TE ever returns one the downstream
        cascade will surface it unchanged but no country-specific flag is
        needed at Sprint X-NO scope.

        Chosen as the **primary** source for NO M1 policy-rate inputs
        (Sprint X-NO) per the Sprint I-patch cascade pattern — TE is
        daily and Norges-Bank-sourced, while the Norges Bank DataAPI
        native path (Sprint X-NO C2) provides a public SDMX-JSON REST
        endpoint at the same daily cadence. FRED OECD mirror
        ``IRSTCI01NOM156N`` is relegated to last-resort with staleness
        flags (monthly cadence).

        Guards source identity via the ``NOBRDEP`` symbol check mirroring
        the GB / JP / CA / AU / NZ / CH wrappers; on drift raises
        :class:`DataUnavailableError` so the NO cascade can fall back
        cleanly.
        """
        obs = await self.fetch_indicator("NO", TE_INDICATOR_INTEREST_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_NO_POLICY_RATE)
        ):
            err = (
                "TE NO-policy-rate source drift: expected "
                f"{TE_EXPECTED_SYMBOL_NO_POLICY_RATE!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_se_policy_rate(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """SE Policy Rate — Riksbank styrränta, TE-sourced.

        TE ``interest rate`` indicator for ``sweden`` returns the
        Riksbank policy rate directly (HistoricalDataSymbol
        ``SWRRATEI`` — legacy "Swedish Repo Rate Indicator" code,
        preserved by TE across the 2022-06-08 rename when Riksbank
        dropped the "repo rate" label in favour of "policy rate"
        (styrränta); the underlying instrument — the 7-day deposit /
        borrowing rate banks transact with the Riksbank — is unchanged).
        Daily cadence back-filled to 1994-05-26 (~463 observations at
        Sprint W-SE probe, 2026-04-22); TE surfaces each rate-change
        announcement plus the constant intervening quotes so a single
        query returns the full decision history regardless of
        ``d1``/``d2``.

        **Negative-rate era preservation**: 58 rows across 2015-02-12 →
        2019-11-30 carry negative values (minimum -0.50 %, roughly
        two-thirds as deep as SNB's -0.75 % corridor). The wrapper (and
        the downstream builder) preserve the sign throughout — the
        ``int(round(value * 100))`` conversion at the Observation layer
        handles negative yields naturally via Python's round-half-even
        semantics, and no clamp is applied. Cascade callers emit
        ``SE_NEGATIVE_RATE_ERA_DATA`` when the returned window contains
        at least one strictly-negative observation, mirroring the CH
        cascade pattern Sprint V-CH established.

        Chosen as the **primary** source for SE M1 policy-rate inputs
        (Sprint W-SE) per the Sprint I-patch cascade pattern — TE is
        daily and Riksbank-sourced, while the Riksbank Swea native path
        (Sprint W-SE C2) covers ``SECBREPOEFF`` (the Riksbank's own
        canonical policy-rate series) at daily cadence as a first-class
        robust fallback. FRED OECD mirror ``IRSTCI01SEM156N`` is
        relegated to last-resort and is **discontinued at 2020-10-01**
        (Sprint W-SE probe) — the series has been frozen for ~5.5 years
        so the staleness flag pair fires on virtually every realistic
        window.

        Guards source identity via the ``SWRRATEI`` symbol check
        mirroring the GB / JP / CA / AU / NZ / CH wrappers; on drift
        raises :class:`DataUnavailableError` so the SE cascade can fall
        back cleanly.
        """
        obs = await self.fetch_indicator("SE", TE_INDICATOR_INTEREST_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_SE_POLICY_RATE)
        ):
            err = (
                "TE SE-policy-rate source drift: expected "
                f"{TE_EXPECTED_SYMBOL_SE_POLICY_RATE!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_dk_policy_rate(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """DK Policy Rate — Nationalbanken discount rate, TE-sourced.

        TE ``interest rate`` indicator for ``denmark`` returns
        Nationalbanken's **discount rate** (``diskontoen``) under the
        ``HistoricalDataSymbol`` ``DEBRDISC`` ("Denmark Bank Rate
        Discount"). Daily cadence back-filled to 1987-08-31 (~464
        observations at Sprint Y-DK probe 2026-04-22); TE surfaces each
        rate-change announcement plus the constant intervening quotes so
        a single query returns the full decision history regardless of
        ``d1``/``d2``.

        **Source-instrument divergence vs the native cascade layer**:
        the discount rate is Nationalbanken's *historical* benchmark and
        is not the active EUR-peg defence tool. Nationalbanken pegs DKK
        to EUR within a ±2.25 % ERM-II band and defends the peg via the
        **certificate-of-deposit (CD) rate** (``indskudsbevisrenten``;
        Statbank series ``OIBNAA``) — the discount rate and CD rate
        diverged sharply across the 2014-2022 negative-rate corridor
        (CD trough -0.75 % at 2015-04-07; discount only briefly negative
        2021-2022 with min -0.60 %). The Sprint Y-DK cascade therefore
        ships TE-primary as the canonical first source per the GB / JP /
        CA / AU / NZ / CH / NO / SE pattern, but the
        :class:`NationalbankenConnector` native secondary returns the CD
        rate explicitly so operators can pick the appropriate semantic
        for downstream consumers — see retro §4 for the empirical
        details.

        **Negative-rate era preservation**: 18 rows across
        2021-03-31 → 2022-08-31 carry negative discount-rate values
        (minimum -0.60 %, considerably shallower than the CD-rate
        corridor depth of -0.75 % over the longer 2015-04 → 2022-09
        window). The wrapper (and the downstream builder) preserve the
        sign throughout — the ``int(round(value * 100))`` conversion at
        the Observation layer handles negative yields naturally via
        Python's round-half-even semantics, and no clamp is applied.
        Cascade callers emit ``DK_NEGATIVE_RATE_ERA_DATA`` when the
        returned window contains at least one strictly-negative
        observation, mirroring the CH / SE flag contract.

        **EUR-peg-imported inflation target**: unlike the GB / JP / CA
        / AU / NZ / CH / NO / SE wrappers, DK has *no domestic*
        inflation target — Nationalbanken's mandate is exchange-rate
        stability (DKK/EUR fixed at 7.46038 ± 2.25 %), and the de facto
        inflation anchor is imported from the ECB's 2 % HICP medium-
        term target via the peg. The cascade emits
        ``DK_INFLATION_TARGET_IMPORTED_FROM_EA`` on every persisted DK
        M1 row to surface the convention to operators (the
        ``bc_targets.yaml`` DK entry carries an explicit
        ``target_convention: imported_eur_peg`` field; see
        :mod:`sonar.indices.monetary.builders` for the flag-emission
        contract).

        Chosen as the **primary** source for DK M1 policy-rate inputs
        (Sprint Y-DK) per the Sprint I-patch cascade pattern — TE is
        daily and Nationalbanken-sourced, while the Statbank native path
        (Sprint Y-DK C2) covers ``OIBNAA`` (the active CD rate) at
        daily cadence as the secondary. FRED OECD mirror
        ``IRSTCI01DKM156N`` is relegated to last-resort with staleness
        flags (monthly cadence; last observation 2025-12 at probe so
        ~4-month lag — comparable to the NO mirror's freshness, much
        better than the SE mirror's 5.5-year discontinuation).

        Guards source identity via the ``DEBRDISC`` symbol check
        mirroring the GB / JP / CA / AU / NZ / CH / NO / SE wrappers;
        on drift raises :class:`DataUnavailableError` so the DK cascade
        can fall back cleanly.
        """
        obs = await self.fetch_indicator("DK", TE_INDICATOR_INTEREST_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_DK_POLICY_RATE)
        ):
            err = (
                "TE DK-policy-rate source drift: expected "
                f"{TE_EXPECTED_SYMBOL_DK_POLICY_RATE!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_gb_bank_rate(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """GB Bank Rate — BoE policy-rate series, TE-sourced.

        TE ``interest rate`` indicator for ``united kingdom`` returns
        the BoE Bank Rate directly (HistoricalDataSymbol
        ``UKBRBASE``). Daily cadence with observations for every
        rate-change announcement — the series back-fills forward so a
        single query returns the full decision history.

        Chosen as the **primary** source for GB M1 policy-rate inputs
        (Sprint I-patch) because the FRED OECD mirror shipped Sprint I
        Day 1 is monthly-lagged vs BoE's daily-cadence decisions.
        Guards source identity via the ``UKBRBASE`` symbol check
        mirroring the Conference Board / Michigan-5Y wrappers; on
        drift raises :class:`DataUnavailableError` so the GB cascade
        can fall back cleanly.

        Canonical name post ADR-0007. :func:`fetch_uk_bank_rate` remains
        available as a deprecated alias.
        """
        obs = await self.fetch_indicator("GB", TE_INDICATOR_INTEREST_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_GB_BANK_RATE)
        ):
            err = (
                "TE GB-bank-rate source drift: expected "
                f"{TE_EXPECTED_SYMBOL_GB_BANK_RATE!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_uk_bank_rate(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """Deprecated alias for :meth:`fetch_gb_bank_rate` (ADR-0007).

        Preserved so Sprint L's untouched ``builders.py`` carve-out can
        continue calling the UK-named method during the transition
        window. Emits a structlog ``te.fetch_uk_bank_rate.deprecated``
        warning on every invocation. Removed Week 10 Day 1.
        """
        log.warning(
            "te.fetch_uk_bank_rate.deprecated",
            replacement="fetch_gb_bank_rate",
            adr="ADR-0007",
        )
        return await self.fetch_gb_bank_rate(start, end)

    # -------------------------------------------------------------------
    # Per-country CPI YoY + inflation forecast (Week 10 Sprint F)
    # CAL-CPI-INFL-T1-WRAPPERS. TE ``inflation rate`` slug powers both
    # endpoints; per-country HistoricalDataSymbol guards catch source
    # drift before the M2 Taylor compute mis-attributes an unrelated
    # series. Pre-flight probe 2026-04-22 mapped every T1 country's
    # symbol individually (see :data:`TE_CPI_YOY_EXPECTED_SYMBOL`).
    # -------------------------------------------------------------------

    async def fetch_ca_cpi_yoy(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """CA headline CPI YoY — StatCan Consumer Price Index, TE-sourced.

        TE ``inflation rate`` indicator for ``canada`` returns the
        StatCan all-items CPI year-on-year change directly
        (HistoricalDataSymbol ``CACPIYOY``). Monthly cadence back-filled
        to 1915-01-31 (~1335 observations at Sprint F probe
        2026-04-22); each row is a month-end value, with the series
        publishing two-to-three weeks after the reference month (StatCan
        release calendar).

        Chosen as the **primary** source for CA M2 Taylor-gap CPI
        inputs per CAL-CPI-INFL-T1-WRAPPERS. TE mirrors StatCan without
        a latency premium and exposes the same series as the BoC MPR
        headline inflation chart. Native StatCan web-data service and
        BoC Valet are candidate secondary slots but Phase 2+ scope —
        per ADR-0010 Sprint F ships T1 complete via TE primary before
        expanding to native-CB secondaries.

        Guards source identity via the ``CACPIYOY`` symbol check
        mirroring the CA / AU / NZ bank-rate wrappers; on drift raises
        :class:`DataUnavailableError` so the M2 CA cascade can
        surface the symbol drift cleanly.
        """
        obs = await self.fetch_indicator("CA", TE_INDICATOR_INFLATION_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_CA_CPI_YOY)
        ):
            err = (
                "TE CA-cpi-yoy source drift: expected "
                f"{TE_EXPECTED_SYMBOL_CA_CPI_YOY!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_ca_inflation_forecast(self, observation_date: date) -> TEInflationForecast:
        """CA inflation-rate forecast — TE projection for Canada CPI YoY.

        Returns the TE q1..q4 + YearEnd projection bundle anchored on
        ``observation_date`` (used only for cache partitioning — the TE
        forecast endpoint always returns the current projection). TE's
        forecast blends BoC MPR published projections with TE's own
        model output; the 12-month-ahead value
        (:attr:`TEInflationForecast.forecast_12m_pct`) is the canonical
        input for the M2 Taylor-forward variant.

        Source-drift guard: ``historical_data_symbol`` must match
        :data:`TE_EXPECTED_SYMBOL_CA_CPI_YOY` (``CACPIYOY``) — the
        forecast endpoint returns the same symbol as the historical so
        a single guard protects both surfaces.
        """
        fcst = await self.fetch_inflation_forecast("CA", observation_date)
        if fcst.historical_data_symbol and not fcst.historical_data_symbol.startswith(
            TE_EXPECTED_SYMBOL_CA_CPI_YOY
        ):
            err = (
                "TE CA-inflation-forecast source drift: expected "
                f"{TE_EXPECTED_SYMBOL_CA_CPI_YOY!r}, got "
                f"{fcst.historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return fcst

    async def fetch_au_cpi_yoy(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """AU headline CPI YoY — ABS Monthly CPI Indicator, TE-sourced.

        TE ``inflation rate`` indicator for ``australia`` returns the
        ABS Monthly CPI Indicator year-on-year (HistoricalDataSymbol
        ``AUCPIYOY``). The ABS Monthly CPI Indicator was introduced in
        2022-11; TE's coverage however starts only at 2025-04-30 — just
        11 observations at Sprint F probe 2026-04-22, spanning the
        latest full year of monthly data. Consumers needing a longer
        series should prefer the quarterly headline CPI (separate ABS
        publication — TE exposes it under a different indicator slug
        not in Sprint F scope).

        The M2 AU builder emits ``AU_M2_CPI_SPARSE_MONTHLY`` when the
        returned window contains fewer than 12 observations so
        downstream consumers can surface the sparse coverage cleanly.

        Chosen as the **primary** source for AU M2 Taylor-gap CPI
        inputs per CAL-CPI-INFL-T1-WRAPPERS. The short history is
        adequate for M2 because the Taylor compute only needs the
        latest observation; the sparse `cpi_yoy_history` that M2
        otherwise ingests falls back to the constant-inflation-target
        scaffold in the absence of a full 10Y series.

        Guards source identity via the ``AUCPIYOY`` symbol check
        mirroring the country bank-rate wrappers.
        """
        obs = await self.fetch_indicator("AU", TE_INDICATOR_INFLATION_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_AU_CPI_YOY)
        ):
            err = (
                "TE AU-cpi-yoy source drift: expected "
                f"{TE_EXPECTED_SYMBOL_AU_CPI_YOY!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_au_inflation_forecast(self, observation_date: date) -> TEInflationForecast:
        """AU inflation-rate forecast — TE projection for Australia CPI YoY.

        Returns the TE q1..q4 + YearEnd projection bundle. The AU
        forecast surface blends RBA Statement on Monetary Policy (SoMP)
        published projections with TE's own model output. 12m-ahead
        value powers the M2 Taylor-forward variant.

        Source-drift guard on ``AUCPIYOY``.
        """
        fcst = await self.fetch_inflation_forecast("AU", observation_date)
        if fcst.historical_data_symbol and not fcst.historical_data_symbol.startswith(
            TE_EXPECTED_SYMBOL_AU_CPI_YOY
        ):
            err = (
                "TE AU-inflation-forecast source drift: expected "
                f"{TE_EXPECTED_SYMBOL_AU_CPI_YOY!r}, got "
                f"{fcst.historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return fcst

    async def fetch_nz_cpi_yoy(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """NZ headline CPI YoY — StatsNZ Consumer Price Index, TE-sourced.

        TE ``inflation rate`` indicator for ``new zealand`` returns the
        StatsNZ CPI year-on-year change (HistoricalDataSymbol
        ``NZCPIYOY``) at **Quarterly** cadence — StatsNZ publishes CPI
        quarterly and TE mirrors the native frequency (unlike most T1
        countries where the TE slug returns monthly). 417 observations
        back to 1918-09-30 at Sprint F probe 2026-04-22; values publish
        approximately four weeks after each quarter-end (e.g. Q4 2024
        published mid-January 2025).

        The M2 NZ builder emits ``NZ_M2_CPI_QUARTERLY`` on every
        compute to record the lower cadence — downstream consumers can
        then surface the latency-vs-US-monthly delta to operators.

        Chosen as the **primary** source for NZ M2 Taylor-gap CPI
        inputs per CAL-CPI-INFL-T1-WRAPPERS. RBNZ Monetary Policy
        Statement publishes matching projections; TE mirrors both the
        historical and forecast surfaces at the same cadence.

        Guards source identity via the ``NZCPIYOY`` symbol check.
        """
        obs = await self.fetch_indicator("NZ", TE_INDICATOR_INFLATION_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_NZ_CPI_YOY)
        ):
            err = (
                "TE NZ-cpi-yoy source drift: expected "
                f"{TE_EXPECTED_SYMBOL_NZ_CPI_YOY!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_nz_inflation_forecast(self, observation_date: date) -> TEInflationForecast:
        """NZ inflation-rate forecast — TE projection for New Zealand CPI YoY.

        Quarterly frequency mirrors the historical series. 12m-ahead
        value powers the M2 Taylor-forward variant; RBNZ MPS-blended
        projections inform the baseline path.

        Source-drift guard on ``NZCPIYOY``.
        """
        fcst = await self.fetch_inflation_forecast("NZ", observation_date)
        if fcst.historical_data_symbol and not fcst.historical_data_symbol.startswith(
            TE_EXPECTED_SYMBOL_NZ_CPI_YOY
        ):
            err = (
                "TE NZ-inflation-forecast source drift: expected "
                f"{TE_EXPECTED_SYMBOL_NZ_CPI_YOY!r}, got "
                f"{fcst.historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return fcst

    # -------------------------------------------------------------------
    # Week 10 Sprint F Commit 2 — CH / SE / NO / DK + GB / JP CPI wrappers
    # Negative-rate era (CH / SE / DK) does NOT affect CPI — these wrappers
    # ship the standard positive-only CPI YoY series and require no rate-
    # regime flag (contrast the M1 cascade builders which emit
    # _NEGATIVE_RATE_ERA_DATA on policy-rate observations). Source-drift
    # guards identical to Commit 1.
    # -------------------------------------------------------------------

    async def fetch_ch_cpi_yoy(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """CH headline CPI YoY — BfS Consumer Price Index, TE-sourced.

        TE ``inflation rate`` indicator for ``switzerland`` returns the
        Bundesamt für Statistik (BfS) CPI year-on-year change directly
        (HistoricalDataSymbol ``SZCPIYOY``). Monthly cadence back-filled
        to 1956-01-31 (~843 observations at Sprint F probe 2026-04-22).
        The SNB monetary-policy "price stability" mandate anchors on
        this series — target band 0-2 %, represented as a 1 %
        midpoint in :mod:`sonar.indices.monetary._config`.

        Guards source identity via the ``SZCPIYOY`` symbol check.
        """
        obs = await self.fetch_indicator("CH", TE_INDICATOR_INFLATION_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_CH_CPI_YOY)
        ):
            err = (
                "TE CH-cpi-yoy source drift: expected "
                f"{TE_EXPECTED_SYMBOL_CH_CPI_YOY!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_ch_inflation_forecast(self, observation_date: date) -> TEInflationForecast:
        """CH inflation-rate forecast — TE projection for Switzerland CPI YoY.

        SNB publishes a conditional inflation forecast alongside each
        Monetary Policy Assessment (quarterly). TE's forecast blends
        the SNB path with TE's own model output.

        Source-drift guard on ``SZCPIYOY``.
        """
        fcst = await self.fetch_inflation_forecast("CH", observation_date)
        if fcst.historical_data_symbol and not fcst.historical_data_symbol.startswith(
            TE_EXPECTED_SYMBOL_CH_CPI_YOY
        ):
            err = (
                "TE CH-inflation-forecast source drift: expected "
                f"{TE_EXPECTED_SYMBOL_CH_CPI_YOY!r}, got "
                f"{fcst.historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return fcst

    async def fetch_se_cpi_yoy(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """SE headline CPI YoY — SCB Consumer Price Index, TE-sourced.

        TE ``inflation rate`` indicator for ``sweden`` returns the
        Statistikmyndigheten SCB CPI year-on-year change (Historical
        DataSymbol ``SWCPYOY`` — 7-character code, *not* ``SWCPIYOY``;
        do not normalise). Monthly cadence back-filled to 1980-01-31
        (~555 observations at Sprint F probe).

        Note: the Riksbank's policy target has been **CPIF** (CPI
        excluding the impact of mortgage-rate changes on owner-occupied
        housing) since 2017-09-07, not CPI. TE's ``inflation rate``
        series is CPI (headline) — the CPI / CPIF gap is typically ≤
        30 bps. A future CPIF wrapper can be added under a separate
        TE indicator slug if the M2 Taylor compute requires CPIF
        strictness; for Sprint F the CPI headline is the M2 input per
        the brief and mirrors what most published headline
        comparisons use.

        Guards source identity via the ``SWCPYOY`` symbol check.
        """
        obs = await self.fetch_indicator("SE", TE_INDICATOR_INFLATION_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_SE_CPI_YOY)
        ):
            err = (
                "TE SE-cpi-yoy source drift: expected "
                f"{TE_EXPECTED_SYMBOL_SE_CPI_YOY!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_se_inflation_forecast(self, observation_date: date) -> TEInflationForecast:
        """SE inflation-rate forecast — TE projection for Sweden CPI YoY.

        Note the CPI-vs-CPIF caveat above; the TE forecast returns the
        headline CPI projection, not CPIF. Source-drift guard on
        ``SWCPYOY``.
        """
        fcst = await self.fetch_inflation_forecast("SE", observation_date)
        if fcst.historical_data_symbol and not fcst.historical_data_symbol.startswith(
            TE_EXPECTED_SYMBOL_SE_CPI_YOY
        ):
            err = (
                "TE SE-inflation-forecast source drift: expected "
                f"{TE_EXPECTED_SYMBOL_SE_CPI_YOY!r}, got "
                f"{fcst.historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return fcst

    async def fetch_no_cpi_yoy(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """NO headline CPI YoY — StatsNorway CPI, TE-sourced.

        TE ``inflation rate`` indicator for ``norway`` returns the
        StatsNorway (SSB) CPI year-on-year (HistoricalDataSymbol
        ``NOCPIYOY``). Monthly cadence back-filled to 1950-01-31 (~915
        observations at Sprint F probe). Norges Bank's 2 % inflation
        target (reduced from 2.5 % on 2018-03-02) anchors on this
        series; the primary domestic alternative CPI-ATE
        (core excluding energy and tax) is a separate TE indicator not
        in Sprint F scope.

        Guards source identity via the ``NOCPIYOY`` symbol check.
        """
        obs = await self.fetch_indicator("NO", TE_INDICATOR_INFLATION_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_NO_CPI_YOY)
        ):
            err = (
                "TE NO-cpi-yoy source drift: expected "
                f"{TE_EXPECTED_SYMBOL_NO_CPI_YOY!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_no_inflation_forecast(self, observation_date: date) -> TEInflationForecast:
        """NO inflation-rate forecast — TE projection for Norway CPI YoY.

        Norges Bank publishes an MPR inflation path quarterly; TE's
        forecast blends MPR with TE's own model output. Source-drift
        guard on ``NOCPIYOY``.
        """
        fcst = await self.fetch_inflation_forecast("NO", observation_date)
        if fcst.historical_data_symbol and not fcst.historical_data_symbol.startswith(
            TE_EXPECTED_SYMBOL_NO_CPI_YOY
        ):
            err = (
                "TE NO-inflation-forecast source drift: expected "
                f"{TE_EXPECTED_SYMBOL_NO_CPI_YOY!r}, got "
                f"{fcst.historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return fcst

    async def fetch_dk_cpi_yoy(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """DK headline CPI YoY — Danmarks Statistik CPI, TE-sourced.

        TE ``inflation rate`` indicator for ``denmark`` returns the
        DST CPI year-on-year (HistoricalDataSymbol ``DNCPIYOY``).
        Monthly cadence back-filled to 1981-01-31 (~543 observations
        at Sprint F probe).

        DK has **no domestic inflation target** — Nationalbanken's
        mandate is exchange-rate stability (DKK/EUR peg), so the de-
        facto anchor is imported from the ECB's 2 % HICP target via
        the peg. The M2 DK builder emits
        ``DK_INFLATION_TARGET_IMPORTED_FROM_EA`` on every compute to
        surface the convention (mirrors the M1 DK pattern from
        Sprint Y-DK).

        Guards source identity via the ``DNCPIYOY`` symbol check.
        """
        obs = await self.fetch_indicator("DK", TE_INDICATOR_INFLATION_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_DK_CPI_YOY)
        ):
            err = (
                "TE DK-cpi-yoy source drift: expected "
                f"{TE_EXPECTED_SYMBOL_DK_CPI_YOY!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_dk_inflation_forecast(self, observation_date: date) -> TEInflationForecast:
        """DK inflation-rate forecast — TE projection for Denmark CPI YoY.

        Nationalbanken does not publish a domestic inflation forecast
        (peg regime); the Economic Council (Vismændene) publishes
        semi-annual forecasts, and TE blends those with its own model.
        Source-drift guard on ``DNCPIYOY``.
        """
        fcst = await self.fetch_inflation_forecast("DK", observation_date)
        if fcst.historical_data_symbol and not fcst.historical_data_symbol.startswith(
            TE_EXPECTED_SYMBOL_DK_CPI_YOY
        ):
            err = (
                "TE DK-inflation-forecast source drift: expected "
                f"{TE_EXPECTED_SYMBOL_DK_CPI_YOY!r}, got "
                f"{fcst.historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return fcst

    async def fetch_gb_cpi_yoy(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """GB headline CPI YoY — ONS Consumer Prices Index, TE-sourced.

        TE ``inflation rate`` indicator for ``united kingdom`` returns
        the ONS headline CPI year-on-year (HistoricalDataSymbol
        ``UKRPCJYR`` — note this is *not* ``UKCPIYOY``; TE retains the
        legacy "UK Retail Price Consumer — Jevons Year" code for the
        modern CPI series). Monthly cadence back-filled to 1989-01-31
        (~447 observations at Sprint F probe).

        Crucially, ``UKRPCJYR`` is the ONS CPI (headline — 2 % BoE
        target series), *not* RPI or RPIX. The M2 GB builder uses
        this for the Taylor compute; the BoE's historical RPIX target
        (pre-2003) is not in Sprint F scope.

        Guards source identity via the ``UKRPCJYR`` symbol check.
        """
        obs = await self.fetch_indicator("GB", TE_INDICATOR_INFLATION_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_GB_CPI_YOY)
        ):
            err = (
                "TE GB-cpi-yoy source drift: expected "
                f"{TE_EXPECTED_SYMBOL_GB_CPI_YOY!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_gb_inflation_forecast(self, observation_date: date) -> TEInflationForecast:
        """GB inflation-rate forecast — TE projection for UK CPI YoY.

        BoE Monetary Policy Report publishes quarterly CPI projections
        at 1Y / 2Y / 3Y horizons; TE blends MPR with TE's own model
        output. Source-drift guard on ``UKRPCJYR``.
        """
        fcst = await self.fetch_inflation_forecast("GB", observation_date)
        if fcst.historical_data_symbol and not fcst.historical_data_symbol.startswith(
            TE_EXPECTED_SYMBOL_GB_CPI_YOY
        ):
            err = (
                "TE GB-inflation-forecast source drift: expected "
                f"{TE_EXPECTED_SYMBOL_GB_CPI_YOY!r}, got "
                f"{fcst.historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return fcst

    async def fetch_jp_cpi_yoy(self, start: date, end: date) -> list[TEIndicatorObservation]:
        """JP headline CPI YoY — Statistics Bureau CPI, TE-sourced.

        TE ``inflation rate`` indicator for ``japan`` returns the
        Statistics Bureau all-items CPI year-on-year (HistoricalData
        Symbol ``JNCPIYOY``). Monthly cadence back-filled to 1958-01-31
        (~818 observations at Sprint F probe). The BoJ 2 % price-
        stability target (adopted 2013) anchors on this headline
        series; core-CPI variants (core, core-core) are separate TE
        indicators not in Sprint F scope.

        Guards source identity via the ``JNCPIYOY`` symbol check.
        """
        obs = await self.fetch_indicator("JP", TE_INDICATOR_INFLATION_RATE, start, end)
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(TE_EXPECTED_SYMBOL_JP_CPI_YOY)
        ):
            err = (
                "TE JP-cpi-yoy source drift: expected "
                f"{TE_EXPECTED_SYMBOL_JP_CPI_YOY!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    async def fetch_jp_inflation_forecast(self, observation_date: date) -> TEInflationForecast:
        """JP inflation-rate forecast — TE projection for Japan CPI YoY.

        BoJ Outlook Report publishes quarterly CPI projections; TE
        blends BoJ Outlook with TE's own model output. Source-drift
        guard on ``JNCPIYOY``.
        """
        fcst = await self.fetch_inflation_forecast("JP", observation_date)
        if fcst.historical_data_symbol and not fcst.historical_data_symbol.startswith(
            TE_EXPECTED_SYMBOL_JP_CPI_YOY
        ):
            err = (
                "TE JP-inflation-forecast source drift: expected "
                f"{TE_EXPECTED_SYMBOL_JP_CPI_YOY!r}, got "
                f"{fcst.historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return fcst

    # -------------------------------------------------------------------
    # Per-country equity index (Week 10 Sprint B scaffolding)
    # -------------------------------------------------------------------

    async def fetch_equity_index_historical(
        self,
        country: str,
        start_date: date,
        end_date: date,
    ) -> list[TEIndicatorObservation]:
        """Fetch the flagship equity-index closing level for ``country``.

        Supported ISO 2-letter codes (Week 10 Sprint B pre-flight probe):
        ``DE`` (DAX), ``GB`` (UKX / FTSE 100), ``JP`` (NKY / Nikkei 225 —
        *not* TOPIX despite the brief wording; TE's country-indicator
        endpoint publishes NKY as the Japan stock-market headline),
        ``FR`` (CAC 40), ``EA`` (SX5E / EuroStoxx 50 aggregate).

        This is scaffolding only. TE's ``/historical/country/.../indicator/
        stock market`` endpoint exposes only the index *closing level* —
        dividend yield, earnings yield, trailing/forward EPS and CAPE
        ratio are **not** surfaced for non-US markets. The full ERP
        4-method compute per country is therefore blocked on Phase 2.5
        per-market fundamentals connectors (CAL-ERP-COUNTRY-FUNDAMENTALS).
        The Sprint B retrospective documents the empirical findings in
        full.

        Source-identity is guarded via the ``HistoricalDataSymbol`` field
        (``DAX``, ``UKX``, ``NKY``, ``CAC``, ``SX5E``) — if TE rotates
        the benchmark series (e.g. DE flipping from DAX to TecDAX),
        :class:`DataUnavailableError` fires instead of quietly returning
        a different index's closing level.
        """
        country_upper = country.upper()
        expected_symbol = TE_EQUITY_INDEX_EXPECTED_SYMBOL.get(country_upper)
        if expected_symbol is None:
            msg = (
                f"TE equity index only supports "
                f"{sorted(TE_EQUITY_INDEX_EXPECTED_SYMBOL)} (Week 10 Sprint B "
                f"empirical scope); got {country}. Other markets defer per "
                f"CAL-ERP-COUNTRY-FUNDAMENTALS."
            )
            raise ValueError(msg)

        obs = await self.fetch_indicator(
            country_upper, TE_INDICATOR_STOCK_MARKET, start_date, end_date
        )
        if (
            obs
            and obs[0].historical_data_symbol
            and not obs[0].historical_data_symbol.startswith(expected_symbol)
        ):
            err = (
                f"TE {country_upper}-equity-index source drift: expected "
                f"{expected_symbol!r}, got "
                f"{obs[0].historical_data_symbol!r}"
            )
            raise DataUnavailableError(err)
        return obs

    # -------------------------------------------------------------------
    # Multi-tenor yield curve (CAL-138 Sprint)
    # -------------------------------------------------------------------

    async def fetch_yield_curve_nominal(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        """Multi-tenor sovereign nominal yield curve via TE Bloomberg symbols.

        Supported countries: GB (12 tenors), JP (9 tenors), CA (6 tenors),
        IT (12 tenors, Sprint H). Other non-EA T1 countries are deferred
        per CAL-CURVES-T1-SPARSE (AU/NZ/CH/SE/NO/DK have insufficient
        tenor coverage on TE); EA periphery remainder (FR / NL / PT)
        deferred per per-country CAL items (see
        :data:`sonar.connectors.ecb_sdw.PERIPHERY_CAL_POINTERS`). ES
        ships in Sprint H Commit 2.

        Returns ``{tenor_label: Observation}`` with ``yield_bps`` on the
        latest trading day ≤ ``observation_date`` inside a 7-day window.
        Tenors with no observations in window are omitted (caller decides
        how to handle gaps; pipeline skips countries failing
        :data:`sonar.overlays.nss.MIN_OBSERVATIONS`).

        Each per-symbol fetch goes through :meth:`_fetch_raw` (cached
        24h) + counted against the Pro-tier quota via ``_call_count``.

        Raises:
            ValueError: country not in :data:`TE_YIELD_CURVE_SYMBOLS`.
        """
        country_upper = country.upper()
        symbols = TE_YIELD_CURVE_SYMBOLS.get(country_upper)
        if symbols is None:
            msg = (
                f"TE yield curve only supports "
                f"{sorted(TE_YIELD_CURVE_SYMBOLS)} (CAL-138 + Sprint H "
                f"empirical scope); got {country}. Other T1 countries "
                f"defer per CAL-CURVES-T1-SPARSE (AU/NZ/CH/SE/NO/DK) or "
                f"per per-country CAL items (FR / NL / PT — see "
                f"sonar.connectors.ecb_sdw.PERIPHERY_CAL_POINTERS; IT "
                f"closed Sprint H via TE cascade, ES lands Commit 2)."
            )
            raise ValueError(msg)

        window_days = 7
        start = observation_date - timedelta(days=window_days)
        end = observation_date

        out: dict[str, Observation] = {}
        for tenor_label, symbol in symbols.items():
            cache_key = f"te:{symbol}:{start.isoformat()}:{end.isoformat()}"
            cached = self.cache.get(cache_key)
            if cached is not None:
                rows_parsed = cast("list[Observation]", cached)
            else:
                rows = await self._fetch_raw(symbol, start, end)
                self._call_count += 1
                rows_parsed = list(_parse_markets_rows(rows, country_upper, tenor_label, symbol))
                rows_parsed.sort(key=lambda o: o.observation_date)
                self.cache.set(cache_key, rows_parsed, ttl=DEFAULT_TTL_SECONDS)
            usable = [o for o in rows_parsed if o.observation_date <= observation_date]
            if not usable:
                continue
            out[tenor_label] = usable[-1]
        log.info(
            "te.yield_curve.fetched",
            country=country_upper,
            n_tenors=len(out),
            date=observation_date.isoformat(),
        )
        return out

    async def fetch_yield_curve_linker(
        self,
        country: str,
        observation_date: date,  # noqa: ARG002 — stub; symmetric signature with nominal
    ) -> dict[str, Observation]:
        """Inflation-indexed (linker) curve stub — empty dict for all T1.

        TE does not expose per-country inflation-linked bond yields
        (confirmed CAL-138 empirical probe 2026-04-22); linker coverage
        for GB gilts-IL / JP JGBi / CA RRB is deferred to native CB
        feeds under CAL-CURVES-T1-LINKER. Callers receive an empty
        dict; the NSS real-curve pipeline falls back to the ``derived``
        method (BEI-based) when expected-inflation wiring lands.
        """
        country_upper = country.upper()
        if country_upper not in TE_YIELD_CURVE_SYMBOLS:
            msg = (
                f"TE yield curve linker stub only accepts "
                f"{sorted(TE_YIELD_CURVE_SYMBOLS)}; got {country}."
            )
            raise ValueError(msg)
        return {}

    # -------------------------------------------------------------------
    # Telemetry
    # -------------------------------------------------------------------

    def get_call_count(self) -> int:
        """Return cumulative TE indicator-fetch calls this instance has made."""
        return self._call_count

    def reset_call_count(self) -> None:
        self._call_count = 0

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


def _parse_forecast_date(raw: Any) -> date | None:
    """Parse TE forecast ``q*_date`` / ``LatestValueDate`` fields."""
    if raw is None or raw == "":
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def _parse_forecast_timestamp(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _parse_forecast_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_forecast_row(
    row: dict[str, Any], country_iso: str, indicator_name: str
) -> TEInflationForecast:
    """Build :class:`TEInflationForecast` from a TE ``/forecast/...`` row.

    Raises :class:`DataUnavailableError` when the required q4 projection
    or LatestValue is missing — those fields power the 12m-ahead M2
    Taylor-forward variant which is the M2-full-compute gate.
    """
    latest_value = _parse_forecast_float(row.get("LatestValue"))
    latest_date = _parse_forecast_date(row.get("LatestValueDate"))
    q4 = _parse_forecast_float(row.get("q4"))
    q4_date = _parse_forecast_date(row.get("q4_date"))
    year_end = _parse_forecast_float(row.get("YearEnd"))
    if latest_value is None or latest_date is None or q4 is None or q4_date is None:
        err = (
            f"TE forecast missing critical fields: country={country_iso!r} "
            f"indicator={indicator_name!r} latest_value={latest_value!r} "
            f"latest_date={latest_date!r} q4={q4!r} q4_date={q4_date!r}"
        )
        raise DataUnavailableError(err)
    year_end_fallback: float = year_end if year_end is not None else q4
    return TEInflationForecast(
        country=country_iso.upper(),
        indicator=indicator_name,
        historical_data_symbol=str(row.get("HistoricalDataSymbol", "")),
        latest_value_pct=latest_value,
        latest_value_date=latest_date,
        forecast_12m_pct=q4,
        forecast_12m_date=q4_date,
        forecast_year_end_pct=year_end_fallback,
        forecast_year_end_2_pct=_parse_forecast_float(row.get("YearEnd2")),
        forecast_year_end_3_pct=_parse_forecast_float(row.get("YearEnd3")),
        forecast_q1_pct=_parse_forecast_float(row.get("q1")),
        forecast_q1_date=_parse_forecast_date(row.get("q1_date")),
        forecast_q2_pct=_parse_forecast_float(row.get("q2")),
        forecast_q2_date=_parse_forecast_date(row.get("q2_date")),
        forecast_q3_pct=_parse_forecast_float(row.get("q3")),
        forecast_q3_date=_parse_forecast_date(row.get("q3_date")),
        frequency=str(row.get("Frequency", "")),
        forecast_last_update=_parse_forecast_timestamp(row.get("ForecastLastUpdate")),
    )


def _parse_markets_rows(
    rows: list[dict[str, Any]],
    country: str,
    tenor_label: str,
    symbol: str,
) -> list[Observation]:
    """Parse ``/markets/historical`` rows into :class:`Observation` instances.

    TE format: ``{Symbol, Date (DD/MM/YYYY), Open, High, Low, Close}`` —
    yields in percent. Converted to ``yield_bps`` via
    ``round(close_pct * 100)`` per ``conventions/units.md`` §Spreads.
    Malformed rows (bad date / non-float close) skipped silently.
    """
    tenor_years = _TE_TENOR_YEARS[tenor_label]
    out: list[Observation] = []
    for row in rows:
        raw_date = row.get("Date")
        raw_close = row.get("Close")
        if not raw_date or raw_close is None:
            continue
        try:
            obs_date = datetime.strptime(str(raw_date), "%d/%m/%Y").replace(tzinfo=UTC).date()
            close_pct = float(raw_close)
        except (ValueError, TypeError):
            continue
        out.append(
            Observation(
                country_code=country,
                observation_date=obs_date,
                tenor_years=tenor_years,
                yield_bps=round(close_pct * 100),
                source="TE",
                source_series_id=symbol,
            )
        )
    return out
