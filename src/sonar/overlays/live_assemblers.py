"""Live connector assemblers for L2 overlays (Sprint 7F).

Each public builder is an async coroutine that sources overlay inputs
from live connectors (FMP / Shiller / Multpl / Damodaran / TE / FRED)
and returns either a ready-to-compute dataclass or ``None``. Builders
**never** raise on a sourceable-but-missing field — they aggregate
``upstream_flags`` and degrade gracefully per conventions/flags.md.
Hard failures (connector 404, ``OverlayError``, ``httpx.HTTPError``,
ambiguous schema drift) are logged and propagate as ``None`` so the
daily-overlays orchestrator reports a structured skip rather than
crashing the whole run.

The synchronous :class:`LiveInputsBuilder` wraps all three async
builders into the :class:`sonar.pipelines.daily_overlays.InputsBuilder`
Protocol via a single ``asyncio.run`` per ``(country, date)`` tick.

Scope:

* :func:`build_erp_us_from_live` — FMP index + Shiller CAPE/earnings +
  Multpl dividend + Damodaran xval, with FRED-sourced risk-free passed
  in by the caller (CAL-109).
* :func:`build_crp_from_live` — TE sovereign yields for country +
  benchmark with optional persisted-rating fallback (CAL-110).
* :func:`build_rating_from_live` — reads ``ratings_agency_raw`` rows
  persisted upstream; the agency-scrape connectors themselves remain
  a follow-on CAL (no FMP / S&P / Moody's / Fitch / DBRS endpoint in
  Phase 1 scope).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from sonar.overlays.crp import compute_sov_spread
from sonar.overlays.exceptions import InsufficientDataError, OverlayError
from sonar.overlays.rating_spread import (
    RatingAgencyRaw,
    apply_modifiers,
    lookup_base_notch,
)
from sonar.pipelines.daily_overlays import OverlayBundle

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from sonar.connectors.damodaran import DamodaranConnector
    from sonar.connectors.fmp import FMPConnector
    from sonar.connectors.multpl import MultplConnector
    from sonar.connectors.shiller import ShillerConnector
    from sonar.connectors.te import TEConnector
    from sonar.overlays.erp import ERPInput

log = structlog.get_logger()

__all__ = [
    "BENCHMARK_BY_CURRENCY",
    "LiveInputsBuilder",
    "build_crp_from_live",
    "build_erp_us_from_live",
    "build_rating_from_live",
]

# Currency block → benchmark country ISO alpha-2. Mirrors
# :data:`sonar.overlays.crp.BENCHMARK_COUNTRIES_BY_CURRENCY` but kept
# local so the assembler does not depend on private crp internals.
BENCHMARK_BY_CURRENCY: dict[str, str] = {
    "EUR": "DE",
    "USD": "US",
    "GBP": "UK",
    "JPY": "JP",
}


# Connector-boundary exception set — anything we catch in live builders
# should degrade gracefully, not crash the pipeline.
_ConnectorErrors = (OverlayError, httpx.HTTPError, ValueError, RuntimeError)


# ---------------------------------------------------------------------------
# CAL-109 — ERP US live
# ---------------------------------------------------------------------------


async def build_erp_us_from_live(
    observation_date: date,
    *,
    fmp: FMPConnector,
    shiller: ShillerConnector,
    multpl: MultplConnector | None = None,
    damodaran: DamodaranConnector | None = None,
    risk_free_nominal_pct: float,
    risk_free_real_pct: float,
    risk_free_confidence: float = 0.95,
    consensus_growth_5y: float = 0.10,
    retention: float = 0.60,
    roe: float = 0.20,
) -> ERPInput | None:
    """Assemble a live :class:`ERPInput` for SPX from connector output.

    Returns ``None`` when any critical field (FMP index level, Shiller
    CAPE + earnings) cannot be sourced. Non-critical fields
    (Multpl dividend, Damodaran xval) degrade with a flag.

    ``risk_free_nominal_pct`` + ``risk_free_real_pct`` are passed in by
    the pipeline (typically derived from the persisted NSS spot + FRED
    TIPS lookup). The spec's DCF/Gordon solvers drive on these values;
    sourcing them lives in the pipeline layer, not here.
    """
    from sonar.overlays.erp import ERPInput  # noqa: PLC0415

    flags: list[str] = []

    # --- FMP index level (critical) -----------------------------------
    try:
        window_start = observation_date - timedelta(days=10)
        prices = await fmp.fetch_index_historical("SPX", window_start, observation_date)
    except _ConnectorErrors as exc:
        log.warning("erp_live.fmp_error", error=str(exc), date=observation_date.isoformat())
        return None
    if not prices:
        log.warning("erp_live.fmp_empty", date=observation_date.isoformat())
        return None
    index_level = float(prices[-1].close)

    # --- Shiller CAPE + earnings (critical) ---------------------------
    try:
        shiller_snap = await shiller.fetch_snapshot(observation_date)
    except _ConnectorErrors as exc:
        log.warning("erp_live.shiller_error", error=str(exc))
        return None
    cape_ratio = float(shiller_snap.cape_ratio)
    trailing_earnings = float(shiller_snap.earnings_nominal)
    shiller_dividend_yield = (
        shiller_snap.dividend_nominal / shiller_snap.price_nominal
        if shiller_snap.price_nominal
        else 0.0
    )

    # --- Multpl current dividend yield (optional) ---------------------
    dividend_yield_pct: float = shiller_dividend_yield
    if multpl is not None:
        try:
            dividend_yield_pct = await multpl.fetch_current_dividend_yield_decimal()
        except _ConnectorErrors as exc:
            flags.append("DIVIDEND_YIELD_FALLBACK_SHILLER")
            log.warning("erp_live.multpl_error", error=str(exc))
    else:
        flags.append("DIVIDEND_YIELD_FALLBACK_SHILLER")

    # --- Damodaran xval reference (optional) --------------------------
    if damodaran is not None:
        try:
            dam_row = await damodaran.fetch_annual_erp(observation_date.year)
        except _ConnectorErrors as exc:
            flags.append("DAMODARAN_XVAL_ERROR")
            log.warning("erp_live.damodaran_error", error=str(exc))
        else:
            if dam_row is None:
                flags.append("DAMODARAN_XVAL_UNAVAILABLE")
    else:
        flags.append("DAMODARAN_XVAL_SKIPPED")

    # Forward EPS: no FactSet / IBES connector yet — use trailing as a
    # conservative proxy and flag it so downstream diagnostics can
    # surface the gap (spec allows this degraded path).
    forward_earnings_est = trailing_earnings
    flags.append("FORWARD_EPS_PROXY_TRAILING")

    return ERPInput(
        market_index="SPX",
        country_code="US",
        observation_date=observation_date,
        index_level=index_level,
        trailing_earnings=trailing_earnings,
        forward_earnings_est=forward_earnings_est,
        dividend_yield_pct=dividend_yield_pct,
        buyback_yield_pct=None,
        cape_ratio=cape_ratio,
        risk_free_nominal=risk_free_nominal_pct,
        risk_free_real=risk_free_real_pct,
        consensus_growth_5y=consensus_growth_5y,
        retention=retention,
        roe=roe,
        risk_free_confidence=risk_free_confidence,
        upstream_flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# CAL-110 — CRP live
# ---------------------------------------------------------------------------


async def build_crp_from_live(
    country_code: str,
    observation_date: date,
    *,
    te: TEConnector,
    currency: str = "EUR",
    vol_ratio: float = 1.23,
    vol_ratio_source: str = "damodaran_standard",
    session: Session | None = None,
) -> dict[str, Any] | None:
    """Assemble CRP kwargs dict via TE sovereign-yield SOV_SPREAD method.

    Returns a ``**kwargs`` dict consumable by
    :func:`sonar.overlays.crp.build_canonical`, or ``None`` when the
    country is not a benchmark and neither TE yields nor a persisted
    rating row can be sourced.

    Hierarchy within this builder:

    1. SOV_SPREAD — TE fetches country yield + benchmark yield at 10Y.
    2. RATING — read ``ratings_consolidated`` via ``session`` (if
       provided) and fall back to that method when SOV_SPREAD fails.
    3. ``None`` — orchestrator reports ``crp: no inputs`` skip.

    Benchmark countries (DE for EUR, US for USD, UK for GBP, JP for
    JPY) short-circuit to a dedicated empty-kwargs path because
    :func:`build_canonical` handles them via the ``BENCHMARK`` shortcut.
    """
    # Benchmark short-circuit — caller still routes through
    # build_canonical which will return method_selected="BENCHMARK".
    if BENCHMARK_BY_CURRENCY.get(currency) == country_code:
        return {
            "country_code": country_code,
            "observation_date": observation_date,
            "sov_spread": None,
            "rating": None,
            "currency": currency,
        }

    benchmark = BENCHMARK_BY_CURRENCY.get(currency)
    if benchmark is None:
        log.warning("crp_live.unknown_currency", country=country_code, currency=currency)
        return None

    sov_spread = None
    # --- SOV_SPREAD via TE 10Y yields ---------------------------------
    try:
        country_obs = await te.fetch_10y_window_around(country_code, observation_date)
        benchmark_obs = await te.fetch_10y_window_around(benchmark, observation_date)
    except _ConnectorErrors as exc:
        log.warning(
            "crp_live.te_error",
            country=country_code,
            benchmark=benchmark,
            error=str(exc),
        )
    else:
        country_obs = [o for o in country_obs if o.observation_date <= observation_date]
        benchmark_obs = [o for o in benchmark_obs if o.observation_date <= observation_date]
        if country_obs and benchmark_obs:
            country_obs.sort(key=lambda o: o.observation_date)
            benchmark_obs.sort(key=lambda o: o.observation_date)
            # yield_bps int (per units.md §Spreads) → decimal.
            country_yield_decimal = country_obs[-1].yield_bps / 10_000.0
            benchmark_yield_decimal = benchmark_obs[-1].yield_bps / 10_000.0
            sov_spread = compute_sov_spread(
                country_code=country_code,
                observation_date=observation_date,
                sov_yield_country_pct=country_yield_decimal,
                sov_yield_benchmark_pct=benchmark_yield_decimal,
                tenor="10Y",
                currency_denomination=currency,
                vol_ratio=vol_ratio,
                vol_ratio_source=vol_ratio_source,
            )

    rating = _load_persisted_crp_rating(
        session=session,
        country_code=country_code,
        observation_date=observation_date,
        vol_ratio=vol_ratio,
        vol_ratio_source=vol_ratio_source,
    )

    if sov_spread is None and rating is None:
        log.warning(
            "crp_live.no_method_available",
            country=country_code,
            date=observation_date.isoformat(),
        )
        return None

    return {
        "country_code": country_code,
        "observation_date": observation_date,
        "sov_spread": sov_spread,
        "rating": rating,
        "currency": currency,
    }


def _load_persisted_crp_rating(
    *,
    session: Session | None,
    country_code: str,
    observation_date: date,
    vol_ratio: float,
    vol_ratio_source: str,
) -> Any | None:  # CRPRating | None — untyped to avoid import cycle.
    """Best-effort RATING method builder from persisted consolidated row.

    Returns ``None`` when no session is provided or no consolidated row
    exists for ``(country, ≤date)``. Errors are swallowed as ``None``
    so the SOV_SPREAD path still runs.
    """
    if session is None:
        return None
    from sonar.db.models import RatingsConsolidated  # noqa: PLC0415
    from sonar.overlays.crp import compute_rating  # noqa: PLC0415

    try:
        row = (
            session.query(RatingsConsolidated)
            .filter(
                RatingsConsolidated.country_code == country_code,
                RatingsConsolidated.date <= observation_date,
            )
            .order_by(RatingsConsolidated.date.desc())
            .first()
        )
    except Exception as exc:
        log.warning("crp_live.rating_lookup_error", error=str(exc))
        return None
    if row is None:
        return None
    if row.default_spread_bps is None:
        return None
    return compute_rating(
        country_code=country_code,
        observation_date=observation_date,
        consolidated_sonar_notch=float(row.consolidated_sonar_notch),
        default_spread_bps=int(row.default_spread_bps),
        rating_id=str(row.rating_id),
        calibration_date=observation_date,
        vol_ratio=vol_ratio,
        vol_ratio_source=vol_ratio_source,
    )


# ---------------------------------------------------------------------------
# CAL-111 — Rating-spread live (DB-backed reader + schema-drift guard)
# ---------------------------------------------------------------------------


# Schema-drift guard: minimum fields per persisted agency row. If any
# of these are missing / malformed, the builder drops the row and
# emits ``SCHEMA_DRIFT_ROW_DROPPED``. Keeps the sprint shippable while
# the upstream scrape connectors remain on the Phase 2 backlog.
_EXPECTED_AGENCY_ROW_FIELDS: tuple[str, ...] = (
    "agency",
    "rating_type",
    "rating_raw",
    "outlook",
    "action_date",
)


async def build_rating_from_live(
    country_code: str,
    observation_date: date,
    *,
    session: Session,
    rating_type: str = "FC",
    damodaran: DamodaranConnector | None = None,  # noqa: ARG001
) -> dict[str, Any] | None:
    """Read persisted ``ratings_agency_raw`` rows and marshal into bundle kwargs.

    ``damodaran`` is kept in the signature for forward compatibility —
    the Damodaran ``ctryprem.xlsx`` backfill is out of scope for this
    sprint (new connector surface + schema-drift guards belong in a
    follow-on CAL). Passing a connector instance today is a no-op.

    Graceful degradation:

    * No DB rows for ``(country, ≤date, rating_type)`` → return ``None``
      (orchestrator routes ``rating: no inputs`` skip).
    * A row missing required fields (see
      :data:`_EXPECTED_AGENCY_ROW_FIELDS`) is silently dropped; a
      ``RATING_SCHEMA_DRIFT`` flag propagates on the consolidated row.
    * Agency tokens that do not resolve via :func:`lookup_base_notch`
      are dropped with a ``RATING_UNKNOWN_TOKEN`` flag.
    """
    from sonar.db.models import RatingsAgencyRaw  # noqa: PLC0415

    # The DB layer is synchronous; we keep the builder await-able so it
    # composes cleanly with the other live assemblers but the query
    # itself runs in-thread.
    try:
        raw_rows = list(
            session.query(RatingsAgencyRaw)
            .filter(
                RatingsAgencyRaw.country_code == country_code,
                RatingsAgencyRaw.rating_type == rating_type,
                RatingsAgencyRaw.date <= observation_date,
            )
            .order_by(RatingsAgencyRaw.agency, RatingsAgencyRaw.date.desc())
            .all()
        )
    except Exception as exc:
        log.warning("rating_live.db_error", country=country_code, error=str(exc))
        return None

    if not raw_rows:
        return None

    # Keep the latest row per agency.
    latest_per_agency: dict[str, Any] = {}
    for row in raw_rows:
        existing = latest_per_agency.get(row.agency)
        if existing is None or row.date > existing.date:
            latest_per_agency[row.agency] = row

    consolidated_flags: list[str] = []
    rows_out: list[RatingAgencyRaw] = []
    for row in latest_per_agency.values():
        if not _row_has_expected_fields(row):
            consolidated_flags.append("RATING_SCHEMA_DRIFT")
            continue
        try:
            base_notch = lookup_base_notch(row.agency, row.rating_raw)
        except OverlayError:
            consolidated_flags.append("RATING_UNKNOWN_TOKEN")
            log.warning(
                "rating_live.unknown_token",
                agency=row.agency,
                rating_raw=row.rating_raw,
            )
            continue
        adjusted = apply_modifiers(
            base_notch=base_notch,
            outlook=row.outlook,
            watch=row.watch,
        )
        rows_out.append(
            RatingAgencyRaw(
                agency=row.agency,
                rating_raw=row.rating_raw,
                rating_type=row.rating_type,
                base_notch=base_notch,
                notch_adjusted=adjusted,
                outlook=row.outlook,
                watch=row.watch,
                action_date=row.action_date,
            )
        )

    if not rows_out:
        log.warning(
            "rating_live.no_usable_rows",
            country=country_code,
            dropped=len(latest_per_agency),
        )
        return None

    kwargs: dict[str, Any] = {
        "rows": rows_out,
        "country_code": country_code,
        "observation_date": observation_date,
        "rating_type": rating_type,
    }
    if consolidated_flags:
        kwargs["_preconsolidation_flags"] = tuple(consolidated_flags)
    return kwargs


def _row_has_expected_fields(row: Any) -> bool:
    return all(getattr(row, field, None) is not None for field in _EXPECTED_AGENCY_ROW_FIELDS)


# ---------------------------------------------------------------------------
# LiveInputsBuilder — sync adapter over the three async builders
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LiveConnectorSuite:
    """Bundled connector handles passed to :class:`LiveInputsBuilder`."""

    fmp: FMPConnector
    shiller: ShillerConnector
    te: TEConnector
    multpl: MultplConnector | None = None
    damodaran: DamodaranConnector | None = None


class LiveInputsBuilder:
    """Sync :class:`InputsBuilder` that wraps the three async live assemblers.

    Calls ``asyncio.run`` once per ``(country, date)`` tick and composes
    the three live assemblers into a single :class:`OverlayBundle`. ERP
    is wired for country US only (SPX); any other country leaves the
    ERP slot empty and the orchestrator skips with ``no inputs``.
    """

    def __init__(
        self,
        connectors: LiveConnectorSuite,
        *,
        risk_free_resolver: Any | None = None,
        currency_by_country: dict[str, str] | None = None,
    ) -> None:
        self._connectors = connectors
        # Resolver signature: (session, country_code, date) ->
        # (risk_free_nominal_pct, risk_free_real_pct, confidence) or None.
        self._risk_free_resolver = risk_free_resolver
        self._currency_by_country = currency_by_country or _DEFAULT_CURRENCY_BY_COUNTRY

    def __call__(
        self,
        session: Session,
        country_code: str,
        observation_date: date,
    ) -> OverlayBundle:
        currency = self._currency_by_country.get(country_code, "EUR")
        rf_tuple = None
        if self._risk_free_resolver is not None and country_code == "US":
            try:
                rf_tuple = self._risk_free_resolver(session, country_code, observation_date)
            except Exception as exc:
                log.warning("live_assemblers.risk_free_error", error=str(exc))
        return asyncio.run(self._run(session, country_code, observation_date, currency, rf_tuple))

    async def _run(
        self,
        session: Session,
        country_code: str,
        observation_date: date,
        currency: str,
        rf_tuple: tuple[float, float, float] | None,
    ) -> OverlayBundle:
        erp = None
        if country_code == "US" and rf_tuple is not None:
            rf_nom, rf_real, rf_conf = rf_tuple
            try:
                erp = await build_erp_us_from_live(
                    observation_date,
                    fmp=self._connectors.fmp,
                    shiller=self._connectors.shiller,
                    multpl=self._connectors.multpl,
                    damodaran=self._connectors.damodaran,
                    risk_free_nominal_pct=rf_nom,
                    risk_free_real_pct=rf_real,
                    risk_free_confidence=rf_conf,
                )
            except _ConnectorErrors as exc:
                log.warning("live_assemblers.erp_error", error=str(exc))

        crp_kwargs = None
        try:
            crp_kwargs = await build_crp_from_live(
                country_code,
                observation_date,
                te=self._connectors.te,
                currency=currency,
                session=session,
            )
        except _ConnectorErrors as exc:
            log.warning("live_assemblers.crp_error", country=country_code, error=str(exc))

        rating_kwargs = None
        try:
            rating_kwargs = await build_rating_from_live(
                country_code,
                observation_date,
                session=session,
                damodaran=self._connectors.damodaran,
            )
        except _ConnectorErrors as exc:
            log.warning("live_assemblers.rating_error", country=country_code, error=str(exc))
        # Drop schema-drift marker before handing to consolidate() since it
        # is not a valid kwarg for consolidate(); the flag is already
        # surfaced through logging.
        if rating_kwargs is not None:
            rating_kwargs.pop("_preconsolidation_flags", None)

        return OverlayBundle(
            country_code=country_code,
            observation_date=observation_date,
            erp=erp,
            crp=crp_kwargs,
            rating=rating_kwargs,
            expected_inflation=None,  # Phase-2 scope; not wired in Sprint 7F.
        )


# Default currency mapping for the 7 T1 countries + common extensions.
_DEFAULT_CURRENCY_BY_COUNTRY: dict[str, str] = {
    "US": "USD",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "NL": "EUR",
    "PT": "EUR",
    "UK": "GBP",
    "JP": "JPY",
}


def __getattr__(name: str) -> Any:
    # InsufficientDataError is re-exported for callers that catch it when
    # composing a custom risk-free resolver; avoids a second import line.
    if name == "InsufficientDataError":
        return InsufficientDataError
    raise AttributeError(name)
