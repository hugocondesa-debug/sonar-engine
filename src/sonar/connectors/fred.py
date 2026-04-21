"""FRED (Federal Reserve Economic Data) L0 connector — US Treasury yields + economic indicators.

Layered API:

- ``fetch_series(series_id, start, end)`` — generic low-level; any series in
  ``FRED_SERIES_TENORS`` (nominal DGS* + linker DFII*).
- ``fetch_yield_curve_nominal(country, observation_date)`` — domain wrapper;
  returns ``{tenor_label: Observation}`` for US nominal Treasuries.
- ``fetch_yield_curve_linker(country, observation_date)`` — domain wrapper;
  TIPS counterpart (DFII5/7/10/20/30).

Observation values stay in bps per units.md §Spreads; overlays convert to
decimal at the L0→L2 boundary (``Observation.yield_bps / 10_000``).

The **Economic indicators** section (below, per CAL-083) exposes 23
helpers for E1/E3/E4 compute inputs. Values come through as raw
``FredEconomicObservation`` (``observation_date``, ``value``,
``series_id``) — **not** bps-scaled. Helpers that need YoY
transformation wrap :func:`_yoy_transform`.
"""

from __future__ import annotations

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
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()

# US nominal Treasury constant maturity series.
FRED_US_NOMINAL_SERIES: dict[str, str] = {
    "1M": "DGS1MO",
    "3M": "DGS3MO",
    "6M": "DGS6MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "3Y": "DGS3",
    "5Y": "DGS5",
    "7Y": "DGS7",
    "10Y": "DGS10",
    "20Y": "DGS20",
    "30Y": "DGS30",
}

# US TIPS (inflation-indexed) series — Fed publishes 5Y+ only; short-end TIPS
# liquidity is too thin. This caps real-curve direct-linker fit at 5 tenors,
# below MIN_OBSERVATIONS=6 per spec §6 (see CAL-033).
FRED_US_LINKER_SERIES: dict[str, str] = {
    "5Y": "DFII5",
    "7Y": "DFII7",
    "10Y": "DFII10",
    "20Y": "DFII20",
    "30Y": "DFII30",
}

# US breakeven inflation (BEI) market-implied series.
FRED_US_BEI_SERIES: dict[str, str] = {
    "5Y": "T5YIE",
    "10Y": "T10YIE",
    "30Y": "T30YIEM",  # monthly-only at 30Y per FRED
}

# US Michigan + SPF survey series (used by ExpInf SURVEY path).
# Note: Michigan 5-10Y expectation has no public FRED series; only the 1Y is
# directly available. EXPINF10YR (Cleveland Fed model) covers the long-end.
FRED_US_SURVEY_SERIES: dict[str, str] = {
    "MICH_1Y": "MICH",  # 1Y inflation expectation, monthly
    "SPF_10Y": "EXPINF10YR",  # 10Y expected inflation, monthly
}

# Combined series_id → tenor_years lookup for the generic fetch_series path.
FRED_SERIES_TENORS: dict[str, float] = {
    "DGS1MO": 1 / 12,
    "DGS3MO": 0.25,
    "DGS6MO": 0.5,
    "DGS1": 1.0,
    "DGS2": 2.0,
    "DGS3": 3.0,
    "DGS5": 5.0,
    "DGS7": 7.0,
    "DGS10": 10.0,
    "DGS20": 20.0,
    "DGS30": 30.0,
    "DFII5": 5.0,
    "DFII7": 7.0,
    "DFII10": 10.0,
    "DFII20": 20.0,
    "DFII30": 30.0,
    # BEI series (tenor matches their market name).
    "T5YIE": 5.0,
    "T10YIE": 10.0,
    "T30YIEM": 30.0,
    # Survey series — synthetic horizon tenor (consumer treats as expectation
    # horizon, not bond maturity).
    "MICH": 1.0,
    "EXPINF10YR": 10.0,
    # OECD MEI mirror series — monthly short-term interest rates
    # (consumed by the GB / JP / CA monetary M1 cascades as last-
    # resort FRED fallback when TE + country-native connectors both
    # fail). Tenor ≈ 0.01Y (overnight) since all three track the
    # short-rate target. Added Week 9 Sprint S when the CA cascade
    # was wired; same commit fixes the corresponding GB / JP tests
    # that asserted FRED fallback without this mapping in place.
    "IRSTCI01GBM156N": 0.01,
    "IRSTCI01JPM156N": 0.01,
    "IRSTCI01CAM156N": 0.01,
    # OECD MEI mirror — monthly long-term interest rates (10Y
    # sovereign benchmark). Reserved for M4 FCI custom paths across
    # GB / JP / CA; not yet consumed at Sprint S scope but wired for
    # the upcoming CAL-121 / CAL-131 FCI bundles.
    "IRLTLT01GBM156N": 10.0,
    "IRLTLT01JPM156N": 10.0,
    "IRLTLT01CAM156N": 10.0,
}

# Back-compat alias for Week 1 nominal-only callers.
FRED_US_TENORS: dict[str, float] = {
    sid: FRED_SERIES_TENORS[sid] for sid in FRED_US_NOMINAL_SERIES.values()
}


class FredConnector(BaseConnector):
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str, cache_dir: str | Path, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(self, series_id: str, start: date, end: date) -> dict[str, Any]:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
        }
        r = await self.client.get(self.BASE_URL, params=params)
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        return data

    async def fetch_series(self, series_id: str, start: date, end: date) -> list[Observation]:
        cache_key = f"fred:{series_id}:{start.isoformat()}:{end.isoformat()}"
        cached_raw = self.cache.get(cache_key)
        if cached_raw is not None:
            log.debug("fred.cache_hit", series=series_id)
            return cast("list[Observation]", cached_raw)

        tenor = FRED_SERIES_TENORS.get(series_id)
        if tenor is None:
            msg = f"Unknown FRED series mapping: {series_id}"
            raise ValueError(msg)

        raw = await self._fetch_raw(series_id, start, end)
        observations: list[Observation] = []
        for obs in raw.get("observations", []):
            if obs["value"] == ".":
                continue
            observations.append(
                Observation(
                    country_code="US",
                    observation_date=datetime.fromisoformat(obs["date"]).date(),
                    tenor_years=tenor,
                    yield_bps=round(float(obs["value"]) * 100),
                    source="FRED",
                    source_series_id=series_id,
                )
            )

        self.cache.set(cache_key, observations, ttl=DEFAULT_TTL_SECONDS)
        log.info("fred.fetched", series=series_id, n=len(observations))
        return observations

    async def _fetch_curve(
        self,
        series_map: dict[str, str],
        country: str,
        observation_date: date,
    ) -> dict[str, Observation]:
        """Fetch a yield curve family (nominal or linker) on a single date.

        Window spans ``observation_date ± 5`` business days so sparse series
        (e.g. weekends, DFII*) still return the closest available observation.
        Returns ``{tenor_label: Observation}`` for every series that yielded a
        non-empty observation on ``observation_date`` or the most recent
        predecessor inside the window. Series with no obs in window are
        simply omitted (caller decides how to handle gaps).
        """
        if country != "US":
            msg = f"FRED connector only supports country=US; got {country}"
            raise ValueError(msg)

        window_days = 7
        start = observation_date - timedelta(days=window_days)
        end = observation_date

        out: dict[str, Observation] = {}
        for tenor_label, series_id in series_map.items():
            obs_list = await self.fetch_series(series_id, start, end)
            usable = [o for o in obs_list if o.observation_date <= observation_date]
            if not usable:
                continue
            usable.sort(key=lambda o: o.observation_date)
            out[tenor_label] = usable[-1]
        return out

    async def fetch_yield_curve_nominal(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        """Return ``{tenor_label: Observation}`` for US nominal Treasuries."""
        return await self._fetch_curve(FRED_US_NOMINAL_SERIES, country, observation_date)

    async def fetch_yield_curve_linker(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        """Return ``{tenor_label: Observation}`` for US TIPS (DFII*)."""
        return await self._fetch_curve(FRED_US_LINKER_SERIES, country, observation_date)

    async def fetch_bei_series(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        """Return ``{tenor_label: Observation}`` for US breakeven inflation (T*YIE)."""
        return await self._fetch_curve(FRED_US_BEI_SERIES, country, observation_date)

    async def fetch_survey_inflation(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        """Return ``{horizon_label: Observation}`` for US survey inflation
        (Michigan + SPF). Window widened to 60 days because surveys are
        monthly/quarterly.
        """
        if country != "US":
            msg = f"FRED survey inflation only supports country=US; got {country}"
            raise ValueError(msg)
        window_days = 90
        start = observation_date - timedelta(days=window_days)
        end = observation_date
        out: dict[str, Observation] = {}
        for label, series_id in FRED_US_SURVEY_SERIES.items():
            obs_list = await self.fetch_series(series_id, start, end)
            usable = [o for o in obs_list if o.observation_date <= observation_date]
            if not usable:
                continue
            usable.sort(key=lambda o: o.observation_date)
            out[label] = usable[-1]
        return out

    # =====================================================================
    # Economic indicators (E1 Activity, E3 Labor, E4 Sentiment) — CAL-083
    # =====================================================================
    #
    # These helpers return :class:`FredEconomicObservation` values (raw
    # level — no bps scaling). Delisted series raise
    # :class:`DataUnavailableError` with a dedicated flag hint so the
    # builder can emit the correct E1/E3/E4 spec flag. See CAL-092.

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_economic_raw(self, series_id: str, start: date, end: date) -> dict[str, Any]:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
        }
        r = await self.client.get(self.BASE_URL, params=params)
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        return data

    async def fetch_economic_series(
        self, series_id: str, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Generic raw-level fetch used by the economic helpers below.

        Skips FRED's ``"."`` sentinel rows. Returns observations sorted
        ascending by date.
        """
        cache_key = f"fred_econ:{series_id}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return list(cached)
        raw = await self._fetch_economic_raw(series_id, start, end)
        out: list[FredEconomicObservation] = []
        for row in raw.get("observations", []):
            if row["value"] == ".":
                continue
            try:
                val = float(row["value"])
            except (TypeError, ValueError):
                continue
            out.append(
                FredEconomicObservation(
                    observation_date=datetime.fromisoformat(row["date"]).date(),
                    value=val,
                    series_id=series_id,
                )
            )
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        log.info("fred.economic.fetched", series=series_id, n=len(out))
        return out

    async def _fetch_yoy(
        self,
        series_id: str,
        start: date,
        end: date,
        *,
        periods_per_year: int,
    ) -> list[FredEconomicObservation]:
        """Fetch raw levels + transform to decimal YoY change."""
        # Fetch an extra year of history so YoY can be computed at `start`.
        fetch_start = date(start.year - 1, start.month, 1)
        levels = await self.fetch_economic_series(series_id, fetch_start, end)
        return _yoy_transform(levels, periods_per_year=periods_per_year)

    # ---- E1 Activity helpers ---------------------------------------------

    async def fetch_gdp_real_yoy_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Quarterly real GDP YoY via ``GDPC1``."""
        return await self._fetch_yoy("GDPC1", start, end, periods_per_year=4)

    async def fetch_industrial_production_yoy_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Monthly industrial-production YoY via ``INDPRO``."""
        return await self._fetch_yoy("INDPRO", start, end, periods_per_year=12)

    async def fetch_nonfarm_payrolls_yoy_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Monthly employment YoY via ``PAYEMS`` (headline nonfarm payrolls)."""
        return await self._fetch_yoy("PAYEMS", start, end, periods_per_year=12)

    async def fetch_retail_sales_real_yoy_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Monthly real retail YoY via ``RRSFS``."""
        return await self._fetch_yoy("RRSFS", start, end, periods_per_year=12)

    async def fetch_personal_income_real_yoy_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Monthly real personal income ex-transfers YoY via ``W875RX1``."""
        return await self._fetch_yoy("W875RX1", start, end, periods_per_year=12)

    async def fetch_ism_mfg_pmi(self, start: date, end: date) -> list[FredEconomicObservation]:
        """ISM Manufacturing PMI — series delisted from FRED; raises.

        ``NAPM`` is no longer served by FRED (ISM pulled their licence).
        Callers should catch :class:`DataUnavailableError` and emit
        ``ISM_MFG_UNAVAILABLE`` flag per spec §6. See CAL-092.
        """
        _ = (start, end)  # parameters retained for API stability
        err = "ISM Manufacturing PMI (NAPM) delisted from FRED; see CAL-092"
        raise DataUnavailableError(err)

    # ---- E3 Labor helpers ------------------------------------------------

    async def fetch_unemployment_rate_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Monthly unemployment rate (level, %) via ``UNRATE``."""
        return await self.fetch_economic_series("UNRATE", start, end)

    async def fetch_emp_pop_ratio_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Monthly employment-population ratio via ``EMRATIO``."""
        return await self.fetch_economic_series("EMRATIO", start, end)

    async def fetch_prime_age_lfpr_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Monthly prime-age labour-force participation via ``LNS11300060``."""
        return await self.fetch_economic_series("LNS11300060", start, end)

    async def fetch_jolts_openings_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Monthly JOLTS job openings (thousands, level) via ``JTSJOL``."""
        return await self.fetch_economic_series("JTSJOL", start, end)

    async def fetch_eci_wages_yoy_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Quarterly ECI wages YoY via ``ECIWAG``."""
        return await self._fetch_yoy("ECIWAG", start, end, periods_per_year=4)

    async def fetch_initial_claims_4wma_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Weekly initial-claims 4-wk moving avg (level) via ``IC4WSA``."""
        return await self.fetch_economic_series("IC4WSA", start, end)

    async def fetch_temp_help_yoy_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Monthly temp-help employment YoY via ``TEMPHELPS``."""
        return await self._fetch_yoy("TEMPHELPS", start, end, periods_per_year=12)

    async def fetch_quits_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Monthly JOLTS quits (thousands, level) via ``JTSQUL``."""
        return await self.fetch_economic_series("JTSQUL", start, end)

    # ---- E4 Sentiment helpers --------------------------------------------

    async def fetch_umich_sentiment_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Monthly Michigan consumer sentiment (level) via ``UMCSENT``."""
        return await self.fetch_economic_series("UMCSENT", start, end)

    async def fetch_conference_board_confidence_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Monthly OECD CLI consumer-confidence composite (level) via ``CSCICP03USM665S``.

        Brief spec called for ``CONCCONF`` (Conference Board consumer
        confidence) but that series is not a valid FRED identifier.
        OECD's consumer-confidence composite leading indicator
        ``CSCICP03USM665S`` is the closest FRED-hosted substitute. Note:
        OECD discontinued this feed in 2024-01, so values are frozen
        after that point — callers may flag ``CB_CONFIDENCE_STALE``.
        See CAL-093.
        """
        return await self.fetch_economic_series("CSCICP03USM665S", start, end)

    async def fetch_umich_5y_inflation_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Monthly 5Y inflation expectations via ``EXPINF5YR`` (Cleveland Fed model).

        Brief spec called for ``MICHM5YM5`` (UMich 5-10Y) but that series
        is not on FRED. The Cleveland Fed's model-based 5Y expected-
        inflation feed is the closest substitute with long history.
        """
        return await self.fetch_economic_series("EXPINF5YR", start, end)

    async def fetch_ism_services_pmi(self, start: date, end: date) -> list[FredEconomicObservation]:
        """ISM Services PMI — series delisted from FRED; raises.

        ``NAPMII`` is no longer served by FRED. See CAL-092.
        """
        _ = (start, end)
        err = "ISM Services PMI (NAPMII) delisted from FRED; see CAL-092"
        raise DataUnavailableError(err)

    async def fetch_nfib_small_biz_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """NFIB Small Business Optimism — FRED no longer hosts; raises.

        Neither ``NFIBBTI`` nor ``NFIB`` resolves on FRED. See CAL-092.
        """
        _ = (start, end)
        err = "NFIB Small Business Optimism not served by FRED; see CAL-092"
        raise DataUnavailableError(err)

    async def fetch_epu_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Daily Economic Policy Uncertainty via ``USEPUINDXD``."""
        return await self.fetch_economic_series("USEPUINDXD", start, end)

    async def fetch_vix_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Daily CBOE VIX close via ``VIXCLS``."""
        return await self.fetch_economic_series("VIXCLS", start, end)

    async def fetch_sloos_tightening_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Quarterly SLOOS net pct tightening C&I loans via ``DRTSCILM``."""
        return await self.fetch_economic_series("DRTSCILM", start, end)

    # ----------------------------------------------------------------------
    # === Monetary indicators (M1 / M2 / M4) === — CAL-096 (week6 sprint 2b)
    # ----------------------------------------------------------------------

    async def fetch_fed_funds_target_upper_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Fed funds target rate, upper bound (``DFEDTARU``).

        Daily series; preferred per spec M1 v0.2 (DFEDTAR removed
        2008-12-16). Use midpoint of upper + lower for policy rate.
        """
        return await self.fetch_economic_series("DFEDTARU", start, end)

    async def fetch_fed_funds_target_lower_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Fed funds target rate, lower bound (``DFEDTARL``)."""
        return await self.fetch_economic_series("DFEDTARL", start, end)

    async def fetch_fed_funds_effective_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Effective Fed funds rate (``FEDFUNDS``) — fallback when target range absent."""
        return await self.fetch_economic_series("FEDFUNDS", start, end)

    async def fetch_fed_balance_sheet_us(
        self, start: date, end: date
    ) -> list[FredEconomicObservation]:
        """Fed balance-sheet level (``WALCL``) — weekly, USD millions."""
        return await self.fetch_economic_series("WALCL", start, end)

    async def fetch_pce_core_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Core PCE price index level (``PCEPILFE``) — monthly. Caller computes YoY."""
        return await self.fetch_economic_series("PCEPILFE", start, end)

    async def fetch_pce_core_yoy_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Core PCE YoY % change (decimal). Spans 13 months internally for the YoY transform."""
        levels = await self.fetch_pce_core_us(start, end)
        return _yoy_transform(levels, periods_per_year=12)

    async def fetch_usd_neer_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Trade-weighted broad USD NEER (``DTWEXBGS``) — daily index."""
        return await self.fetch_economic_series("DTWEXBGS", start, end)

    async def fetch_mortgage_30y_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """30-year fixed mortgage rate (``MORTGAGE30US``) — weekly, percent."""
        return await self.fetch_economic_series("MORTGAGE30US", start, end)

    async def fetch_nfci_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Chicago Fed National Financial Conditions Index (``NFCI``) — weekly z-score."""
        return await self.fetch_economic_series("NFCI", start, end)

    async def fetch_potential_gdp_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """CBO real potential GDP (``GDPPOT``) — quarterly, $bn (chained 2017)."""
        return await self.fetch_economic_series("GDPPOT", start, end)

    async def fetch_real_gdp_us(self, start: date, end: date) -> list[FredEconomicObservation]:
        """Real GDP level (``GDPC1``) — quarterly, $bn (chained 2017)."""
        return await self.fetch_economic_series("GDPC1", start, end)

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


# ---------------------------------------------------------------------------
# Economic-indicator observation dataclass + YoY helper (CAL-083)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FredEconomicObservation:
    """Raw-level observation returned by the FRED economic helpers."""

    observation_date: date
    value: float
    series_id: str
    source: str = "FRED"


def _yoy_transform(
    levels: list[FredEconomicObservation], *, periods_per_year: int
) -> list[FredEconomicObservation]:
    """Convert a level series to decimal YoY changes."""
    if not levels:
        return []
    out: list[FredEconomicObservation] = []
    for i in range(periods_per_year, len(levels)):
        prior = levels[i - periods_per_year]
        current = levels[i]
        if prior.value == 0:
            continue
        yoy = (current.value - prior.value) / prior.value
        out.append(
            FredEconomicObservation(
                observation_date=current.observation_date,
                value=yoy,
                series_id=current.series_id,
            )
        )
    return out
