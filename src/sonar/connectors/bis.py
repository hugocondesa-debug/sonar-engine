"""BIS SDMX v2 connector — WS_DSR + WS_CREDIT_GAP + WS_TC.

Public API:
- ``fetch_dsr(country, start_date, end_date)`` → ``list[BisObservation]``
  Dataflow ``BIS:WS_DSR(1.0)``, key ``Q.{CTY}.P``. Returns DSR in percent
  display (e.g. 14.5 for US 2024-Q2). Phase 0 Bloco D validated 7/7 T1;
  credit-indices-brief-v3 Commit 1 re-validated 2026-04-20.
- ``fetch_credit_gap(country, start_date, end_date, cg_dtype='C')`` →
  ``list[BisObservation]``. Dataflow ``BIS:WS_CREDIT_GAP(1.0)``,
  key ``Q.{CTY}.P.A.{CG_DTYPE}`` where ``CG_DTYPE ∈ {A, B, C}``:
  A=actual, B=trend (BIS one-sided HP), C=gap (actual-trend). Default
  ``C`` for the L2 consumer.
- ``fetch_credit_stock_ratio(country, start_date, end_date)`` →
  ``list[BisObservation]``. Dataflow ``BIS:WS_TC(2.0)`` (migrated from
  1.0 during 2026 — see :data:`DATAFLOW_VERSIONS`), key
  ``Q.{CTY}.P.A.M.770.A`` per CAL-019 resolution 2026-04-20.
  Returns credit-to-GDP ratio in percent display.
- ``fetch_property_price_index(country, start_date, end_date)`` →
  ``list[BisObservation]``. Dataflow ``BIS:WS_SPP(1.0)``, key
  ``Q.{CTY}.N.628`` — F-cycle F1 input.
- ``fetch_structure(dataflow_id)`` → ``dict``. Used by CAL-019 debug
  path; retained here for future structure-drift detection.

Base URL: ``https://stats.bis.org/api/v2``. Path pattern (SDMX v2 REST):
``/data/dataflow/{AGENCY}/{DATAFLOW_ID}/{VERSION}/{key}`` — legacy
``/data/{DATAFLOW_ID}/{key}?format=jsondata`` was retired during 2026
(CAL-136, Week 9 Sprint AA).

Accept header: ``application/vnd.sdmx.data+json;version=1.0.0`` —
**mandatory**. Omission returns SDMX-XML (StructureSpecificData) and
``;version=2.0.0``/``;version=3.0.0`` are rejected with HTTP 406.

Rate limit: 1 req/sec polite-use throttle (undocumented).
Auth: none (public).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final, Literal, cast

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

log = structlog.get_logger()

BASE_URL = "https://stats.bis.org/api/v2"
AGENCY_ID = "BIS"
ACCEPT_HEADER = "application/vnd.sdmx.data+json;version=1.0.0"
RATE_LIMIT_SLEEP_SECONDS = 1.0

# Canonical dataflow → version map (Week 9 Sprint AA / CAL-136).
# WS_TC migrated from 1.0 → 2.0 during 2026; WS_LONG_PP renamed → WS_SPP
# during Week 5 / CAL-072. Consumers that need `(flow_id, version)`
# tuples should use the DATAFLOW_WS_* helpers below (back-compat).
# WS_EER added Week 10 Sprint J (2026-04-22) for NEER per T1 country +
# EA aggregate (XM) — 17/17 coverage confirmed in Commit 1 pre-flight.
DATAFLOW_VERSIONS: Final[dict[str, str]] = {
    "WS_TC": "2.0",
    "WS_DSR": "1.0",
    "WS_CREDIT_GAP": "1.0",
    "WS_SPP": "1.0",
    "WS_EER": "1.0",
}

# Tuple-shaped aliases retained for call sites that import the
# `(flow_id, version)` pair directly. Derived from DATAFLOW_VERSIONS so
# new dataflows need only a single entry above.
DATAFLOW_WS_DSR = ("WS_DSR", DATAFLOW_VERSIONS["WS_DSR"])
DATAFLOW_WS_CREDIT_GAP = ("WS_CREDIT_GAP", DATAFLOW_VERSIONS["WS_CREDIT_GAP"])
DATAFLOW_WS_TC = ("WS_TC", DATAFLOW_VERSIONS["WS_TC"])
DATAFLOW_WS_SPP = ("WS_SPP", DATAFLOW_VERSIONS["WS_SPP"])
DATAFLOW_WS_EER = ("WS_EER", DATAFLOW_VERSIONS["WS_EER"])

# BIS WS_EER supports 16 T1 countries + XM (EA aggregate). The key
# format for broad-basket nominal monthly is ``M.N.B.{REF_AREA}``.
# Per Sprint J Commit 1 pre-flight (2026-04-22), all 17 return HTTP
# 200 with monthly observations. The connector rejects unsupported
# T2 countries at the wrapper layer to surface sourcing gaps loudly.
BIS_EER_COUNTRY_CODES: Final[frozenset[str]] = frozenset(
    {
        "US",
        "DE",
        "FR",
        "IT",
        "ES",
        "NL",
        "PT",
        "GB",
        "JP",
        "CA",
        "AU",
        "NZ",
        "CH",
        "SE",
        "NO",
        "DK",
        "XM",
    }
)

# Canonical SONAR ISO code → BIS REF_AREA mapping. SONAR uses ``EA``
# for the euro-area aggregate where BIS uses ``XM`` per SDMX
# conventions (``XM`` = euro area, ISO 4217 reserved).
_SONAR_TO_BIS_EER_COUNTRY: Final[dict[str, str]] = {
    "EA": "XM",
}

CgDtype = Literal["A", "B", "C"]  # A=actual, B=trend, C=gap


@dataclass(frozen=True, slots=True)
class BisObservation:
    """Quarterly BIS credit observation (percent display).

    Distinct from :class:`sonar.connectors.base.Observation` because BIS
    credit series are quarterly ratios (% of GDP, % DSR), not yields in
    bps at a tenor. Consumers in ``indices/credit/`` treat
    ``value_pct`` as the canonical input.
    """

    country_code: str
    observation_date: date
    value_pct: float
    source: str  # e.g. "BIS_WS_DSR", "BIS_WS_CREDIT_GAP", "BIS_WS_TC"
    source_series_key: str


@dataclass(frozen=True, slots=True)
class BisEerObservation:
    """Monthly BIS effective-exchange-rate observation (index level).

    Distinct from :class:`BisObservation` because WS_EER publishes a
    nominal/real NEER **index** (base period 2010 = 100, dimensionless)
    rather than a percentage-of-GDP ratio. The ``value_index`` field
    carries the published level; consumers in M4 FCI transform to
    z-score over a rolling 30Y window per spec §4.
    """

    country_code: str  # SONAR canonical — ``EA`` maps from BIS ``XM``
    observation_date: date  # month-end
    value_index: float
    source: str = "BIS_WS_EER"
    source_series_key: str = ""


def _quarter_label_to_end_date(label: str) -> date:
    """Convert SDMX quarter label 'YYYY-Qn' to quarter-end date."""
    year_s, q_s = label.split("-Q")
    year = int(year_s)
    q = int(q_s)
    month = q * 3
    # Quarter-end day per calendar.
    last_day = {3: 31, 6: 30, 9: 30, 12: 31}[month]
    return date(year, month, last_day)


def _month_label_to_end_date(label: str) -> date:
    """Convert SDMX monthly label 'YYYY-MM' to month-end date."""
    year_s, m_s = label.split("-")
    year = int(year_s)
    month = int(m_s)
    if month == 12:
        return date(year, 12, 31)
    next_month_first = date(year, month + 1, 1)
    return date(next_month_first.year, next_month_first.month, 1) - timedelta(days=1)


def _try_parse_iso(label: str) -> date | None:
    try:
        return datetime.fromisoformat(label).date()
    except ValueError:
        return None


class BisConnector:
    """L0 connector for BIS stats.bis.org SDMX v2 API."""

    def __init__(
        self,
        cache_dir: str | Path,
        timeout: float = 30.0,
        rate_limit_seconds: float = RATE_LIMIT_SLEEP_SECONDS,
    ) -> None:
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Accept": ACCEPT_HEADER},
        )
        self._rate_limit_seconds = rate_limit_seconds
        self._last_request_at: float = 0.0

    async def _respect_rate_limit(self) -> None:
        """Sleep if the previous request was under the rate-limit window."""
        if self._rate_limit_seconds <= 0:
            return
        loop = asyncio.get_event_loop()
        now = loop.time()
        elapsed = now - self._last_request_at
        if elapsed < self._rate_limit_seconds:
            await asyncio.sleep(self._rate_limit_seconds - elapsed)
        self._last_request_at = loop.time()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw_data(
        self,
        dataflow: tuple[str, str],
        key: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        flow_id, version = dataflow
        url = f"{BASE_URL}/data/dataflow/{AGENCY_ID}/{flow_id}/{version}/{key}"
        params = {
            "startPeriod": _date_to_period(start_date),
            "endPeriod": _date_to_period(end_date),
        }
        await self._respect_rate_limit()
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        return cast("dict[str, Any]", r.json())

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def fetch_structure(self, dataflow_id: str) -> dict[str, Any]:
        """Fetch dataflow structure (codelists + dimensions) for audit."""
        url = f"{BASE_URL}/structure/dataflow/{AGENCY_ID}/{dataflow_id}"
        params = {"references": "all", "detail": "full"}
        await self._respect_rate_limit()
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        return cast("dict[str, Any]", r.json())

    async def _fetch_observations(
        self,
        dataflow: tuple[str, str],
        key: str,
        country: str,
        source_tag: str,
        start_date: date,
        end_date: date,
    ) -> list[BisObservation]:
        cache_key = (
            f"bis:{dataflow[0]}:{dataflow[1]}:{key}:{start_date.isoformat()}:{end_date.isoformat()}"
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("bis.cache_hit", key=key)
            return cast("list[BisObservation]", cached)

        payload = await self._fetch_raw_data(dataflow, key, start_date, end_date)
        obs = list(_parse_series(payload, country=country, source_tag=source_tag, series_key=key))
        self.cache.set(cache_key, obs, ttl=DEFAULT_TTL_SECONDS)
        log.info("bis.fetched", flow=dataflow[0], country=country, n=len(obs))
        return obs

    async def fetch_dsr(
        self, country: str, start_date: date, end_date: date
    ) -> list[BisObservation]:
        """BIS debt-service ratio (% of income). PNFS segment."""
        key = f"Q.{country}.P"
        return await self._fetch_observations(
            DATAFLOW_WS_DSR,
            key=key,
            country=country,
            source_tag="BIS_WS_DSR",
            start_date=start_date,
            end_date=end_date,
        )

    async def fetch_credit_gap(
        self,
        country: str,
        start_date: date,
        end_date: date,
        cg_dtype: CgDtype = "C",
    ) -> list[BisObservation]:
        """BIS credit-to-GDP gap (pp); default CG_DTYPE=C (actual-trend)."""
        key = f"Q.{country}.P.A.{cg_dtype}"
        return await self._fetch_observations(
            DATAFLOW_WS_CREDIT_GAP,
            key=key,
            country=country,
            source_tag=f"BIS_WS_CREDIT_GAP_{cg_dtype}",
            start_date=start_date,
            end_date=end_date,
        )

    async def fetch_credit_stock_ratio(
        self, country: str, start_date: date, end_date: date
    ) -> list[BisObservation]:
        """BIS total credit to PNFS, % of GDP (L1 input). Resolved CAL-019 key."""
        key = f"Q.{country}.P.A.M.770.A"
        return await self._fetch_observations(
            DATAFLOW_WS_TC,
            key=key,
            country=country,
            source_tag="BIS_WS_TC",
            start_date=start_date,
            end_date=end_date,
        )

    async def fetch_property_price_index(
        self, country: str, start_date: date, end_date: date
    ) -> list[BisObservation]:
        """BIS Selected Property Prices — nominal residential index (F1 input).

        Dataflow ``BIS:WS_SPP(1.0)``. Key structure ``Q.{CTY}.N.628`` for
        nominal residential property, 2010 = 100 index. Parsing mirrors
        the credit datasets; the ``value_pct`` field stores the index
        level (not a percentage of GDP). Schema drift would surface as
        a 404 or empty payload — caller in F1 emits
        ``PROPERTY_GAP_UNAVAILABLE`` per spec §6 HALT-trigger #4.

        Historical note: BIS renamed this dataflow from ``WS_LONG_PP``
        to ``WS_SPP`` during 2026. The SDMX-JSON 1.0 response shape is
        identical between the two — only the dataflow id changed.
        """
        key = f"Q.{country}.N.628"
        return await self._fetch_observations(
            DATAFLOW_WS_SPP,
            key=key,
            country=country,
            source_tag="BIS_WS_SPP",
            start_date=start_date,
            end_date=end_date,
        )

    # -------------------------------------------------------------------
    # M4 FCI NEER component (Sprint J — Week 10 Day 2)
    # -------------------------------------------------------------------
    #
    # WS_EER(1.0) dataflow exposes effective exchange-rate indices for
    # 60+ reference areas at monthly cadence. Key format for broad-basket
    # nominal monthly = ``M.N.B.{REF_AREA}``. SONAR consumes the BIS feed
    # as the single cross-country NEER source for M4 FCI since FRED only
    # covers US (DTWEXBGS); BIS coverage is 17/17 for T1 + XM per Sprint
    # J Commit 1 pre-flight probe. Daily FCI compute uses most-recent
    # monthly value + ``_M4_NEER_MONTHLY_CADENCE`` flag (daily
    # interpolation via bilateral-FX composite deferred to
    # CAL-M4-NEER-FREQUENCY-DAILY).

    async def fetch_neer(
        self,
        country: str,
        start_date: date,
        end_date: date,
    ) -> list[BisEerObservation]:
        """BIS broad-basket nominal NEER (monthly, index 2010=100).

        ``country`` is the SONAR ISO 2-letter code; EA is silently
        mapped to BIS ``XM``. Unsupported T2 countries raise
        :class:`ValueError` with a CAL pointer.

        Returns ``list[BisEerObservation]`` sorted ascending by
        ``observation_date`` (month-end). Empty response is allowed
        (returns empty list — BIS publishes with ~2-month lag on some
        small economies); callers layer staleness checks.
        """
        country_upper = country.upper()
        bis_ref = _SONAR_TO_BIS_EER_COUNTRY.get(country_upper, country_upper)
        if bis_ref not in BIS_EER_COUNTRY_CODES:
            msg = (
                f"BIS WS_EER NEER only supports T1 + EA (XM) at Sprint J "
                f"scope; got {country!r}. Unsupported countries open "
                f"CAL-M4-NEER-T2-EXPANSION."
            )
            raise ValueError(msg)
        key = f"M.N.B.{bis_ref}"
        raw_obs = await self._fetch_observations(
            DATAFLOW_WS_EER,
            key=key,
            country=country_upper,
            source_tag="BIS_WS_EER",
            start_date=start_date,
            end_date=end_date,
        )
        # Re-wrap the generic BisObservation rows as monthly EER rows —
        # the shared parser returns BisObservation (value_pct field) but
        # for NEER the value is an index level, not a ratio, so we
        # surface a distinct dataclass to the consumer.
        return [
            BisEerObservation(
                country_code=country_upper,
                observation_date=o.observation_date,
                value_index=o.value_pct,
                source="BIS_WS_EER",
                source_series_key=key,
            )
            for o in raw_obs
        ]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


def _date_to_period(d: date) -> str:
    """Convert a calendar date to SDMX quarterly period 'YYYY-Qn'."""
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def _parse_series(
    payload: dict[str, Any],
    *,
    country: str,
    source_tag: str,
    series_key: str,
) -> Sequence[BisObservation]:
    """Parse SDMX-JSON 1.0 data response into ``BisObservation`` rows.

    Expects ``data.dataSets[0].series`` + ``data.structure.dimensions.observation``
    per SDMX-JSON 1.0 schema. Returns empty list if the response has no
    series (valid for some key combinations that the server silently
    returns empty).
    """
    try:
        datasets = payload["data"]["dataSets"]
    except (KeyError, TypeError):
        return []
    if not datasets:
        return []

    series_map = datasets[0].get("series", {})
    if not series_map:
        return []

    # Resolve TIME_PERIOD ordering from structure.observation[0].values.
    try:
        obs_dims = payload["data"]["structure"]["dimensions"]["observation"]
    except (KeyError, TypeError):
        return []
    time_dim = next((d for d in obs_dims if d["id"] == "TIME_PERIOD"), None)
    if time_dim is None:
        return []
    period_labels = [v["id"] for v in time_dim.get("values", [])]

    out: list[BisObservation] = []
    for _series_idx, series_data in series_map.items():
        observations = series_data.get("observations", {})
        for obs_idx_str, obs_values in observations.items():
            obs_idx = int(obs_idx_str)
            if obs_idx >= len(period_labels):
                continue
            label = period_labels[obs_idx]
            raw = obs_values[0] if obs_values else None
            if raw is None or raw == "":
                continue
            try:
                value_pct = float(raw)
            except (TypeError, ValueError):
                continue
            obs_date = _try_parse_iso(label) or _label_to_end_date(label)
            out.append(
                BisObservation(
                    country_code=country,
                    observation_date=obs_date,
                    value_pct=value_pct,
                    source=source_tag,
                    source_series_key=series_key,
                )
            )
    return out


def _label_to_end_date(label: str) -> date:
    """Route SDMX period label to the correct cadence end-of-period.

    Handles the ``YYYY-Qn`` quarterly and ``YYYY-MM`` monthly label
    formats used by the BIS dataflows consumed at Sprint J scope
    (WS_DSR / WS_TC / WS_SPP / WS_CREDIT_GAP = quarterly;
    WS_EER = monthly). Other cadences fall through to
    :func:`_quarter_label_to_end_date` for back-compat with earlier
    dataflow shapes.
    """
    if "-Q" in label:
        return _quarter_label_to_end_date(label)
    if len(label) == 7 and label[4] == "-":
        return _month_label_to_end_date(label)
    return _quarter_label_to_end_date(label)


__all__ = [
    "ACCEPT_HEADER",
    "AGENCY_ID",
    "BASE_URL",
    "BIS_EER_COUNTRY_CODES",
    "DATAFLOW_VERSIONS",
    "DATAFLOW_WS_CREDIT_GAP",
    "DATAFLOW_WS_DSR",
    "DATAFLOW_WS_EER",
    "DATAFLOW_WS_SPP",
    "DATAFLOW_WS_TC",
    "BisConnector",
    "BisEerObservation",
    "BisObservation",
    "CgDtype",
]
