"""L6 primitive — daily cost-of-capital per country (Week 3.5F).

Composes ``k_e(country) = rf_local_10Y + beta * ERP_mature + CRP(country)``
with ``beta = 1.0`` stub (Phase 2 refinement).

Week 3.5 scope: compute for 7 T1 countries (US/DE/PT/IT/ES/FR/NL) using
Week 3.5C vol_ratio + existing CRP compute + a Damodaran-standard
mature ERP (5.5%) placeholder until the full ERP overlay (3.5B) lands.
Persist to ``cost_of_capital_daily``.

CLI:

    python -m sonar.pipelines.daily_cost_of_capital --country US --date 2024-01-02
    python -m sonar.pipelines.daily_cost_of_capital --all-t1 --date 2024-01-02

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

from sonar.db.models import CostOfCapitalDaily, NSSYieldCurveSpot
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

# 3.5F interim: Damodaran global mature-market ERP (decimal) — replace
# once 3.5B lands the real ERP compute.
DAMODARAN_MATURE_ERP_DECIMAL: float = 0.055
DAMODARAN_MATURE_ERP_BPS: int = round(DAMODARAN_MATURE_ERP_DECIMAL * 10_000)

# Week 3.5F target countries.
T1_7_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")

# EUR periphery → DE benchmark; US world → US benchmark (itself).
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
    beta: float = 1.0,
) -> KEResult:
    """Compose k_e per spec §4 (simplified):

    ``k_e = rf_local + beta * ERP_mature + CRP(country)``

    all in decimal internally; convert at persistence boundary.
    """
    crp_decimal = float(crp.crp_canonical_bps) / 10_000.0
    erp_decimal = erp_mature_bps / 10_000.0
    k_e_decimal = rf_local_decimal + beta * erp_decimal + crp_decimal

    flags = tuple(crp.flags) if hasattr(crp, "flags") else ()
    confidence = float(getattr(crp, "confidence", 1.0))

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
    k_e = compose_k_e(
        country_code=country_code,
        observation_date=observation_date,
        rf_local_decimal=rf_local,
        crp=crp,
        beta=beta,
    )
    persist_k_e(session, k_e)
    log.info(
        "cost_of_capital.persisted",
        country=country_code,
        date=observation_date.isoformat(),
        k_e_pct=round(k_e.k_e_pct * 100, 2),
        rf_local_pct=round(k_e.rf_local_pct * 100, 2),
        crp_bps=k_e.crp_bps,
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
