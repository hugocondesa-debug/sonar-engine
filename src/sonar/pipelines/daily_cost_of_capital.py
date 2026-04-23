"""L6 primitive — daily cost-of-capital per country.

Composes ``k_e(country) = rf_local_10Y + beta * ERP_mature + CRP(country)``
with ``beta = 1.0`` stub (Phase 2 refinement).

Scope: compute for 7 T1 countries (US/DE/PT/IT/ES/FR/NL). CRP comes from
Week 3.5C vol_ratio + existing CRP compute; ERP comes from the persisted
``erp_canonical`` row when available (US ships live ERP from erp-us c8
onward). Non-US countries proxy the US ERP with a ``MATURE_ERP_PROXY_US``
flag until per-country ERP overlays land (Week 4+).

Mature-ERP resolution order (each country, each date):

1. ``erp_canonical`` SPX row ≤ target date — SONAR's own compute-don't-
   consume ERP. No flag for US; ``MATURE_ERP_PROXY_US`` for non-US.
2. Damodaran monthly implied ERP for the target month (pulled live via
   :class:`sonar.connectors.damodaran.DamodaranConnector`) — still "live"
   in the sense that it reflects the latest S&P 500 market state.
   Flag ``ERP_MATURE_LIVE_DAMODARAN`` (+ ``MATURE_ERP_PROXY_US`` for
   non-US). Opt-in via ``--no-damodaran-live`` / env
   ``SONAR_DISABLE_DAMODARAN_LIVE=1`` for tests + offline runs.
3. Static Damodaran-standard 5.5 % mature ERP — last-resort fallback.
   Flag ``ERP_STUB``.

Width ``1 → 2`` replaces the pre-Week-10-Sprint-B behaviour where the
static 5.5 % stub was the only fallback (leaving non-US k_e in a
chronically-stale state when the SONAR ERP pipeline had not yet run).

CLI:

    python -m sonar.pipelines.daily_cost_of_capital --country US --date 2024-01-02
    python -m sonar.pipelines.daily_cost_of_capital --all-t1 --date 2024-01-02

Upstream: run ``daily_erp_us`` (or equivalent) first to populate
``erp_canonical`` for the target date so this pipeline can read live
ERP instead of the stub.

Exit codes (ADR-0011 aligned, Sprint T0 2026-04-23):

- ``0`` — happy path: pipeline ran to completion. Mixes of persisted
  + duplicate-skipped + insufficient-data-skipped countries are OK.
- ``1`` — *every* country failed insufficient_data (no single persist
  or duplicate-skip). Strict-single mode maps insufficient_data to 1.
- ``4`` — IO / unexpected exception at orchestrator boundary.

Sprint T0 removed exit code 3 (DuplicatePersistError) from the
happy-path contract per ADR-0011 Principle 1: duplicates are skip +
continue; `insufficient_data` per country no longer kills the
pipeline in --all-t1 mode.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

import structlog
import typer
from sqlalchemy.exc import IntegrityError

from sonar.connectors.damodaran import DamodaranConnector, DamodaranMonthlyERPRow
from sonar.db.models import CostOfCapitalDaily, ERPCanonical, NSSYieldCurveSpot
from sonar.db.persistence import DuplicatePersistError
from sonar.db.session import SessionLocal
from sonar.overlays.crp import (
    BENCHMARK_COUNTRIES_BY_CURRENCY,
    DAMODARAN_STANDARD_RATIO,
    build_canonical,
    compute_sov_spread,
    is_benchmark,
)
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session

    from sonar.overlays.crp import CRPCanonical

log = structlog.get_logger()

METHODOLOGY_VERSION: str = "K_E_DAILY_v0.1"

# Damodaran global mature-market ERP (decimal) — used only when no
# persisted erp_canonical row exists for the target market/date. Emits
# the ERP_STUB flag so consumers know the composition is degraded.
DAMODARAN_MATURE_ERP_DECIMAL: float = 0.055
DAMODARAN_MATURE_ERP_BPS: int = round(DAMODARAN_MATURE_ERP_DECIMAL * 10_000)

# Week 3.5F target countries.
T1_7_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")

# Country → (currency, ERP proxy market_index). US and EA periphery share
# SPX as the ERP input today — per-country ERP overlays land Week 4+.
# Keys are ISO 3166-1 alpha-2 canonical (ADR-0007); legacy "UK" input is
# normalised to "GB" via :func:`_normalize_country_code` at CLI + run_one
# entry. Removal Week 10 Day 1.
COUNTRY_TO_CURRENCY: dict[str, str] = {
    "US": "USD",
    "DE": "EUR",
    "PT": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "FR": "EUR",
    "NL": "EUR",
    "GB": "GBP",
    "JP": "JPY",
}

# ADR-0007 deprecated country aliases — preserved during CAL-128-FOLLOWUP
# transition window. Removal scheduled Week 10 Day 1
# (deprecation_target="CAL-128-alias-removal-week10").
_DEPRECATED_COUNTRY_ALIASES: dict[str, str] = {"UK": "GB"}


def _normalize_country_code(country_code: str) -> str:
    """Normalise deprecated ISO aliases to canonical codes (ADR-0007).

    Emits a structlog deprecation warning when an alias is resolved. Canonical
    codes are returned unchanged. Removal scheduled Week 10 Day 1.
    """
    canonical = _DEPRECATED_COUNTRY_ALIASES.get(country_code)
    if canonical is None:
        return country_code
    log.warning(
        "cost_of_capital.deprecated_country_alias",
        alias=country_code,
        canonical=canonical,
        adr="ADR-0007",
        deprecation_target="CAL-128-alias-removal-week10",
    )
    return canonical


# All 7 T1 countries currently proxy the SPX canonical ERP. Swap per
# country as each market's own ERP overlay comes online.
COUNTRY_TO_ERP_MARKET_INDEX: dict[str, str] = dict.fromkeys(T1_7_COUNTRIES, "SPX")

EXIT_OK = 0
EXIT_INSUFFICIENT_DATA = 1
EXIT_DUPLICATE = 3  # retained for back-compat; unreachable under ADR-0011
EXIT_IO = 4

# T1 countries with shipped NSS curves (Sprint M 2026-04-23 /
# post-Sprint-I + PT). insufficient_data for these countries is a
# genuine upstream signal (curves were expected from the prior
# daily_curves run); for countries outside this set, insufficient_data
# is the expected state. Split drives warn vs info-level logging so
# journals communicate severity proportional to coverage expectations.
# Drift guard: ``test_curves_shipped_countries_matches_daily_curves``
# in ``tests/unit/test_pipelines/test_daily_cost_of_capital.py``
# enforces equality with ``daily_curves.CURVE_SUPPORTED_COUNTRIES``.
_CURVES_SHIPPED_COUNTRIES: frozenset[str] = frozenset(
    {"US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR", "PT"}
)


@dataclass(frozen=True, slots=True)
class KEResult:
    """Composite k_e result for a single (country, date)."""

    country_code: str
    observation_date: date
    rf_local_pct: float
    erp_mature_bps: int
    crp_bps: int
    beta: float
    k_e_pct: float
    confidence: float
    flags: tuple[str, ...]


def _lookup_erp_canonical(
    session: Session, market_index: str, observation_date: date
) -> int | None:
    """Return ``erp_median_bps`` from the most recent canonical row for
    ``(market_index, <= observation_date)``, or ``None`` if none exists.

    The ``<=`` tolerance is intentional: ERP canonical rows are weekly
    cadence (Factset + Shiller update weekly / monthly). Consumers at
    daily cadence need the most recent row; spec §4 step 5.5 handles
    freshness deductions further upstream.
    """
    row = (
        session.query(ERPCanonical)
        .filter(
            ERPCanonical.market_index == market_index,
            ERPCanonical.date <= observation_date,
        )
        .order_by(ERPCanonical.date.desc())
        .first()
    )
    if row is None:
        return None
    return int(row.erp_median_bps)


def _fetch_nss_10y(session: Session, country_code: str, observation_date: date) -> float:
    """Read the latest NSS spot 10Y decimal yield for (country, date).

    Raises:
        InsufficientDataError: when no spot row exists for the triplet.
    """
    row = (
        session.query(NSSYieldCurveSpot)
        .filter(
            NSSYieldCurveSpot.country_code == country_code,
            NSSYieldCurveSpot.date <= observation_date,
        )
        .order_by(NSSYieldCurveSpot.date.desc())
        .first()
    )
    if row is None:
        msg = (
            f"No NSS spot row for country={country_code} "
            f"on or before {observation_date.isoformat()}"
        )
        raise InsufficientDataError(msg)
    fitted = json.loads(row.fitted_yields_json)
    rate_10y = fitted.get("10Y")
    if rate_10y is None:
        msg = f"NSS spot row for {country_code} {row.date} has no 10Y tenor"
        raise InsufficientDataError(msg)
    return float(rate_10y)


def compose_k_e(
    *,
    country_code: str,
    observation_date: date,
    rf_local_decimal: float,
    crp: CRPCanonical,
    erp_mature_bps: int = DAMODARAN_MATURE_ERP_BPS,
    erp_flags: tuple[str, ...] = (),
    beta: float = 1.0,
) -> KEResult:
    """Compose k_e per spec §4 (simplified):

    ``k_e = rf_local + beta * ERP_mature + CRP(country)``

    all in decimal internally; convert at persistence boundary. ``erp_flags``
    are merged into the composite flag set (CRP flags + ERP-provenance
    flags like ``MATURE_ERP_PROXY_US`` or ``ERP_STUB``).
    """
    crp_decimal = float(crp.crp_canonical_bps) / 10_000.0
    erp_decimal = erp_mature_bps / 10_000.0
    k_e_decimal = rf_local_decimal + beta * erp_decimal + crp_decimal

    crp_flags = tuple(crp.flags) if hasattr(crp, "flags") else ()
    flags = tuple(sorted(set(crp_flags) | set(erp_flags)))
    confidence = float(getattr(crp, "confidence", 1.0))
    if "ERP_STUB" in flags:
        confidence = max(0.0, confidence - 0.20)

    return KEResult(
        country_code=country_code,
        observation_date=observation_date,
        rf_local_pct=rf_local_decimal,
        erp_mature_bps=erp_mature_bps,
        crp_bps=int(crp.crp_canonical_bps),
        beta=beta,
        k_e_pct=k_e_decimal,
        confidence=confidence,
        flags=flags,
    )


def _build_crp_for_country(
    *,
    country_code: str,
    observation_date: date,
    rf_local_decimal: float,
    rf_benchmark_decimal: float,
) -> CRPCanonical:
    """Week 3.5F simplified — SOV_SPREAD only (no CDS, no RATING lookup yet).

    Uses Damodaran standard vol_ratio; the country-specific vol_ratio
    from 3.5C requires 5Y equity+bond histories which are a separate
    pipeline fetch step (will wire in 3.5E).
    """
    currency = COUNTRY_TO_CURRENCY.get(country_code, "EUR")
    if is_benchmark(country_code, currency):
        return build_canonical(
            country_code=country_code,
            observation_date=observation_date,
            currency=currency,
        )
    sov = compute_sov_spread(
        country_code=country_code,
        observation_date=observation_date,
        sov_yield_country_pct=rf_local_decimal,
        sov_yield_benchmark_pct=rf_benchmark_decimal,
        currency_denomination=currency,
        vol_ratio=DAMODARAN_STANDARD_RATIO,
        vol_ratio_source="damodaran_standard",
    )
    return build_canonical(
        country_code=country_code,
        observation_date=observation_date,
        sov_spread=sov,
        currency=currency,
    )


def persist_k_e(session: Session, result: KEResult) -> None:
    row = CostOfCapitalDaily(
        country_code=result.country_code,
        date=result.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        rf_local_pct=result.rf_local_pct,
        erp_mature_bps=result.erp_mature_bps,
        crp_bps=result.crp_bps,
        beta=result.beta,
        k_e_pct=result.k_e_pct,
        confidence=result.confidence,
        flags=",".join(result.flags) if result.flags else None,
    )
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"k_e already persisted: country={result.country_code}, "
                f"date={result.observation_date}, version={METHODOLOGY_VERSION}"
            )
            raise DuplicatePersistError(err) from e
        raise


def _resolve_erp_bps(
    session: Session,
    country_code: str,
    observation_date: date,
    *,
    mature_fallback: _MatureFallback | None = None,
) -> tuple[int, tuple[str, ...]]:
    """Lookup the mature-market ERP for ``(country, date)``.

    Returns ``(erp_bps, flags)``. Resolution order:

    1. erp_canonical row for country's mapped market_index → use live bps.
    2. Damodaran monthly implied ERP (when ``mature_fallback`` carries
       a live row) → tag ``ERP_MATURE_LIVE_DAMODARAN`` (+
       ``MATURE_ERP_PROXY_US`` for non-US).
    3. No canonical row anywhere and no Damodaran live row →
       Damodaran-standard stub 5.5 %, tag ``ERP_STUB``.

    ``mature_fallback`` is resolved once per pipeline invocation at
    CLI entry (see :func:`main`) and carries either a live Damodaran
    monthly row or ``None`` (offline mode).
    """
    market_index = COUNTRY_TO_ERP_MARKET_INDEX.get(country_code, "SPX")
    live_bps = _lookup_erp_canonical(session, market_index, observation_date)
    if live_bps is not None:
        flags = () if country_code == "US" else ("MATURE_ERP_PROXY_US",)
        return live_bps, flags
    # No SONAR-computed canonical → try Damodaran monthly live first.
    if mature_fallback is not None and mature_fallback.damodaran_row is not None:
        live = mature_fallback.damodaran_row
        mature_bps = round(live.implied_erp_decimal * 10_000)
        base_flags: tuple[str, ...] = ("ERP_MATURE_LIVE_DAMODARAN",)
        if country_code != "US":
            base_flags = (*base_flags, "MATURE_ERP_PROXY_US")
        return mature_bps, base_flags
    # Last-resort static stub.
    return DAMODARAN_MATURE_ERP_BPS, ("ERP_STUB",)


@dataclass(frozen=True, slots=True)
class _MatureFallback:
    """Per-run mature-market ERP fallback bundle.

    When ``damodaran_row`` is populated the pipeline prefers the live
    monthly implied ERP over the static 5.5 % stub. Resolved once at
    CLI entry so every ``(country, date)`` tick within the run shares
    a single Damodaran fetch + parse.
    """

    damodaran_row: DamodaranMonthlyERPRow | None


def resolve_mature_erp_fallback(
    observation_date: date,
    *,
    cache_dir: str | Path | None = None,
    disabled: bool = False,
) -> _MatureFallback:
    """Fetch the Damodaran monthly implied ERP for ``observation_date``.

    Runs the async connector under :func:`asyncio.run`; returns a
    ``_MatureFallback`` whose ``damodaran_row`` is ``None`` when the
    fallback is disabled, the fetch fails, or no file resolves within
    the Damodaran lookback window. Errors are logged, never raised —
    the caller continues with the static 5.5 % stub.
    """
    if disabled or os.environ.get("SONAR_DISABLE_DAMODARAN_LIVE") == "1":
        log.debug(
            "cost_of_capital.damodaran_live.disabled",
            reason="env_or_flag",
        )
        return _MatureFallback(damodaran_row=None)

    cache_path = (
        str(cache_dir)
        if cache_dir is not None
        else os.environ.get("SONAR_CONNECTOR_CACHE_DIR", ".cache/connectors")
    )

    async def _run() -> DamodaranMonthlyERPRow | None:
        conn = DamodaranConnector(cache_dir=cache_path)
        try:
            return await conn.fetch_monthly_implied_erp(
                observation_date.year, observation_date.month
            )
        finally:
            await conn.aclose()

    try:
        row = asyncio.run(_run())
    except Exception as exc:  # degrade gracefully at boundary
        log.warning(
            "cost_of_capital.damodaran_live.fetch_error",
            error=str(exc),
            observation_date=observation_date.isoformat(),
        )
        return _MatureFallback(damodaran_row=None)
    if row is None:
        log.info(
            "cost_of_capital.damodaran_live.no_row",
            observation_date=observation_date.isoformat(),
        )
    else:
        log.info(
            "cost_of_capital.damodaran_live.resolved",
            source_file=row.source_file,
            mature_erp_bps=round(row.implied_erp_decimal * 10_000),
            observation_date=observation_date.isoformat(),
        )
    return _MatureFallback(damodaran_row=row)


def run_one(
    session: Session,
    country_code: str,
    observation_date: date,
    benchmark_code: str,
    *,
    beta: float = 1.0,
    mature_fallback: _MatureFallback | None = None,
) -> KEResult:
    """Single (country, date) compute + persist. Idempotent when duplicate
    raises — caller decides continue-on-dup semantics at batch level.

    Deprecated ISO aliases (e.g. "UK") are normalised to canonical ("GB")
    at entry and emit a structlog deprecation warning. Removal Week 10
    Day 1 per ADR-0007.

    ``mature_fallback`` is an optional pre-resolved Damodaran monthly
    ERP bundle (see :func:`resolve_mature_erp_fallback`). When omitted
    the resolver uses the static 5.5 % stub as before Week 10 Sprint B.
    """
    country_code = _normalize_country_code(country_code)
    rf_local = _fetch_nss_10y(session, country_code, observation_date)
    rf_benchmark = _fetch_nss_10y(session, benchmark_code, observation_date)
    crp = _build_crp_for_country(
        country_code=country_code,
        observation_date=observation_date,
        rf_local_decimal=rf_local,
        rf_benchmark_decimal=rf_benchmark,
    )
    erp_bps, erp_flags = _resolve_erp_bps(
        session, country_code, observation_date, mature_fallback=mature_fallback
    )
    k_e = compose_k_e(
        country_code=country_code,
        observation_date=observation_date,
        rf_local_decimal=rf_local,
        crp=crp,
        erp_mature_bps=erp_bps,
        erp_flags=erp_flags,
        beta=beta,
    )
    persist_k_e(session, k_e)
    log.info(
        "cost_of_capital.persisted",
        country=country_code,
        date=observation_date.isoformat(),
        k_e_pct=round(k_e.k_e_pct * 100, 2),
        rf_local_pct=round(k_e.rf_local_pct * 100, 2),
        erp_bps=k_e.erp_mature_bps,
        crp_bps=k_e.crp_bps,
        flags=list(k_e.flags),
    )
    return k_e


@dataclass(slots=True)
class _CostOfCapitalRunOutcomes:
    """Bucketed per-country outcomes across a --all-t1 orchestration.

    ADR-0011 Principle 4 — four disjoint buckets: persisted (row
    landed), duplicate (idempotent no-op re-run), insufficient
    (upstream NSS spot or CRP missing), failed (uncaught exception).
    """

    persisted: list[str] = field(default_factory=list)
    duplicate: list[str] = field(default_factory=list)
    insufficient: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def _dispatch_country_loop(
    *,
    session: Session,
    targets: list[str],
    observation_date: date,
    mature_fallback: _MatureFallback,
) -> _CostOfCapitalRunOutcomes:
    """Run each target country; collect outcomes across four buckets.

    ADR-0011 Principles 1-2: pre-existing rows skip silently via the
    ``DuplicatePersistError`` catch (info level, not error); each
    country's exception is isolated so one failure does not sink the
    pipeline. ``InsufficientDataError`` branches on whether the
    country is in :data:`_CURVES_SHIPPED_COUNTRIES` — a T1-shipped
    country missing NSS spot is a warning (upstream daily_curves
    regressed); a non-shipped country missing it is info (expected).
    """
    outcomes = _CostOfCapitalRunOutcomes()
    for raw in targets:
        # ADR-0007: normalise legacy ISO aliases (e.g. "UK" → "GB")
        # at CLI entry so currency / benchmark resolution + persisted
        # row all carry canonical codes. Structlog deprecation
        # warning fires once per invocation; removal Week 10 Day 1.
        c = _normalize_country_code(raw)
        country_upper = c.upper()
        benchmark = BENCHMARK_COUNTRIES_BY_CURRENCY[COUNTRY_TO_CURRENCY.get(c, "EUR")]
        try:
            run_one(session, c, observation_date, benchmark, mature_fallback=mature_fallback)
            outcomes.persisted.append(country_upper)
        except InsufficientDataError as exc:
            if country_upper in _CURVES_SHIPPED_COUNTRIES:
                log.warning(
                    "cost_of_capital.insufficient_data",
                    country=country_upper,
                    error=str(exc),
                    severity="upstream_shipped_regressed",
                )
            else:
                log.info(
                    "cost_of_capital.insufficient_data",
                    country=country_upper,
                    error=str(exc),
                    severity="expected_upstream_absent",
                )
            outcomes.insufficient.append((country_upper, str(exc)))
        except DuplicatePersistError as exc:
            # ADR-0011 Principle 1: duplicate = skip + continue.
            log.info(
                "cost_of_capital.duplicate_skipped",
                country=country_upper,
                error=str(exc),
            )
            outcomes.duplicate.append(country_upper)
        except Exception as exc:  # ADR-0011 Principle 2 — per-country isolation
            log.error(
                "cost_of_capital.country_failed",
                country=country_upper,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            outcomes.failed.append((country_upper, f"{type(exc).__name__}: {exc}"))
    return outcomes


def main(
    country: str = typer.Option("", "--country", help="ISO 3166-1 alpha-2 (omit with --all-t1)."),
    target_date: str = typer.Option(..., "--date", help="ISO date (e.g. 2024-01-02)."),
    all_t1: bool = typer.Option(
        False,  # noqa: FBT003 — typer Option requires positional default
        "--all-t1",
        help="Iterate over all 7 Week 3.5F T1 countries.",
    ),
    disable_damodaran_live: bool = typer.Option(
        False,  # noqa: FBT003 — typer Option requires positional default
        "--no-damodaran-live",
        help=(
            "Skip the Damodaran monthly implied ERP fallback; use static "
            "5.5 % stub when no erp_canonical row exists. Equivalent to "
            "SONAR_DISABLE_DAMODARAN_LIVE=1."
        ),
    ),
) -> None:
    """Run the daily cost-of-capital pipeline."""
    try:
        obs_date = date.fromisoformat(target_date)
    except ValueError:
        typer.echo(f"Invalid --date={target_date!r}; expected ISO YYYY-MM-DD", err=True)
        sys.exit(EXIT_IO)

    targets: list[str] = list(T1_7_COUNTRIES) if all_t1 else [country]
    if not targets or targets == [""]:
        typer.echo("Must pass --country or --all-t1", err=True)
        sys.exit(EXIT_IO)

    # Resolve the live mature-market ERP once per invocation; every
    # (country, date) tick shares the result so we don't re-parse the
    # Damodaran workbook per country.
    mature_fallback = resolve_mature_erp_fallback(obs_date, disabled=disable_damodaran_live)

    session = SessionLocal()
    strict_single = not all_t1
    try:
        outcomes = _dispatch_country_loop(
            session=session,
            targets=targets,
            observation_date=obs_date,
            mature_fallback=mature_fallback,
        )
    finally:
        session.close()

    log.info(
        "cost_of_capital.summary",
        date=obs_date.isoformat(),
        n_persisted=len(outcomes.persisted),
        n_duplicate=len(outcomes.duplicate),
        n_insufficient=len(outcomes.insufficient),
        n_failed=len(outcomes.failed),
        countries_persisted=outcomes.persisted,
        countries_duplicate=outcomes.duplicate,
        countries_insufficient=[c for c, _ in outcomes.insufficient],
        countries_failed=[c for c, _ in outcomes.failed],
    )

    ok_count = len(outcomes.persisted) + len(outcomes.duplicate)
    if strict_single:
        # --country <X>: surface insufficient_data + failed as
        # non-zero. Persist / duplicate → exit 0.
        if outcomes.failed:
            sys.exit(EXIT_IO)
        if outcomes.insufficient:
            sys.exit(EXIT_INSUFFICIENT_DATA)
        if ok_count == 0:
            sys.exit(EXIT_INSUFFICIENT_DATA)
        sys.exit(EXIT_OK)
    # --all-t1: exit 0 if any country persisted or duplicate-skipped.
    # Exit 1 only if *every* country failed insufficient_data / error.
    if ok_count == 0:
        sys.exit(EXIT_INSUFFICIENT_DATA)
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    typer.run(main)
