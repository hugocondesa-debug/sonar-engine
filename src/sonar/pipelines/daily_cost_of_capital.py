"""L6 primitive — daily cost-of-capital per country.

Composes ``k_e(country) = rf_local_10Y + beta * ERP_mature + CRP(country)``
with ``beta = 1.0`` stub (Phase 2 refinement).

Scope: compute for 7 T1 countries (US/DE/PT/IT/ES/FR/NL). CRP comes from
Week 3.5C vol_ratio + existing CRP compute; ERP comes from the persisted
``erp_canonical`` row when available (US ships live ERP from erp-us c8
onward). Non-US countries proxy the US ERP with a ``MATURE_ERP_PROXY_US``
flag until per-country ERP overlays land (Week 4+). When no canonical
row exists for the target (market, date), the pipeline falls back to
the Damodaran-standard mature ERP 5.5% and emits the ``ERP_STUB`` flag.

CLI:

    python -m sonar.pipelines.daily_cost_of_capital --country US --date 2024-01-02
    python -m sonar.pipelines.daily_cost_of_capital --all-t1 --date 2024-01-02

Upstream: run ``daily_erp_us`` (or equivalent) first to populate
``erp_canonical`` for the target date so this pipeline can read live
ERP instead of the stub.

Exit codes:

- ``0`` clean run (all requested countries persisted)
- ``1`` InsufficientDataError (typically CRP no-method)
- ``3`` DuplicatePersistError
- ``4`` IO / unexpected
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

import structlog
import typer
from sqlalchemy.exc import IntegrityError

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
COUNTRY_TO_CURRENCY: dict[str, str] = {
    "US": "USD",
    "DE": "EUR",
    "PT": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "FR": "EUR",
    "NL": "EUR",
    "UK": "GBP",
    "JP": "JPY",
}

# All 7 T1 countries currently proxy the SPX canonical ERP. Swap per
# country as each market's own ERP overlay comes online.
COUNTRY_TO_ERP_MARKET_INDEX: dict[str, str] = dict.fromkeys(T1_7_COUNTRIES, "SPX")

EXIT_OK = 0
EXIT_INSUFFICIENT_DATA = 1
EXIT_DUPLICATE = 3
EXIT_IO = 4


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
    session: Session, country_code: str, observation_date: date
) -> tuple[int, tuple[str, ...]]:
    """Lookup the mature-market ERP for ``(country, date)``.

    Returns ``(erp_bps, flags)``. Resolution order:

    1. erp_canonical row for country's mapped market_index → use live bps.
    2. If non-US proxy chain maps to SPX, use SPX canonical → tag
       MATURE_ERP_PROXY_US (per Week 3.5 scope).
    3. No canonical row anywhere → Damodaran-standard stub 5.5 %, tag
       ERP_STUB.
    """
    market_index = COUNTRY_TO_ERP_MARKET_INDEX.get(country_code, "SPX")
    live_bps = _lookup_erp_canonical(session, market_index, observation_date)
    if live_bps is not None:
        flags = () if country_code == "US" else ("MATURE_ERP_PROXY_US",)
        return live_bps, flags
    # No live canonical available → stub.
    return DAMODARAN_MATURE_ERP_BPS, ("ERP_STUB",)


def run_one(
    session: Session,
    country_code: str,
    observation_date: date,
    benchmark_code: str,
    *,
    beta: float = 1.0,
) -> KEResult:
    """Single (country, date) compute + persist. Idempotent when duplicate
    raises — caller decides continue-on-dup semantics at batch level.
    """
    rf_local = _fetch_nss_10y(session, country_code, observation_date)
    rf_benchmark = _fetch_nss_10y(session, benchmark_code, observation_date)
    crp = _build_crp_for_country(
        country_code=country_code,
        observation_date=observation_date,
        rf_local_decimal=rf_local,
        rf_benchmark_decimal=rf_benchmark,
    )
    erp_bps, erp_flags = _resolve_erp_bps(session, country_code, observation_date)
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


def main(
    country: str = typer.Option("", "--country", help="ISO 3166-1 alpha-2 (omit with --all-t1)."),
    target_date: str = typer.Option(..., "--date", help="ISO date (e.g. 2024-01-02)."),
    all_t1: bool = typer.Option(
        False,  # noqa: FBT003 — typer Option requires positional default
        "--all-t1",
        help="Iterate over all 7 Week 3.5F T1 countries.",
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

    session = SessionLocal()
    exit_code = EXIT_OK
    try:
        for c in targets:
            benchmark = BENCHMARK_COUNTRIES_BY_CURRENCY[COUNTRY_TO_CURRENCY.get(c, "EUR")]
            try:
                run_one(session, c, obs_date, benchmark)
            except InsufficientDataError as exc:
                log.error("cost_of_capital.insufficient_data", country=c, error=str(exc))
                exit_code = EXIT_INSUFFICIENT_DATA
            except DuplicatePersistError as exc:
                log.error("cost_of_capital.duplicate", country=c, error=str(exc))
                exit_code = EXIT_DUPLICATE
    finally:
        session.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    typer.run(main)
