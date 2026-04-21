"""L5 retroactive classification script (CAL-backfill-l5).

Iterates ``(country, date)`` tuples where at least one of the four
L4 cycle rows has been persisted but no matching ``l5_meta_regimes``
row exists, then classifies via
:class:`sonar.regimes.meta_regime_classifier.MetaRegimeClassifier`
and persists via
:func:`sonar.db.persistence.persist_l5_meta_regime_result`.

The script is **idempotent** — second runs are no-ops because
classified dates drop out of the eligible set. Dry-run is the
default; ``--execute`` is required to write.

Exit codes mirror ``sonar retention``:

- ``0`` — completed cleanly (including dry-run and zero-eligible).
- ``2`` — CLI mis-use (no ``--country`` / ``--all-t1``).
- ``4`` — IO / DB error during the run.

Usage::

    # Safe default (dry-run):
    python -m sonar.scripts.backfill_l5 --country US
    python -m sonar.scripts.backfill_l5 --all-t1

    # Execute:
    python -m sonar.scripts.backfill_l5 --country US --execute
    python -m sonar.scripts.backfill_l5 --all-t1 --from-date 2024-01-01 --execute
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

import structlog
import typer
from sqlalchemy import select

from sonar.db.models import (
    CreditCycleScore,
    EconomicCycleScore,
    FinancialCycleScore,
    L5MetaRegime,
    MonetaryCycleScore,
)
from sonar.db.persistence import (
    DuplicatePersistError,
    persist_l5_meta_regime_result,
)
from sonar.db.session import SessionLocal
from sonar.regimes.assemblers import (
    build_cccs_snapshot_from_orm,
    build_ecs_snapshot_from_orm,
    build_fcs_snapshot_from_orm,
    build_l5_inputs_from_snapshots,
    build_msc_snapshot_from_orm,
)
from sonar.regimes.exceptions import InsufficientL4DataError
from sonar.regimes.meta_regime_classifier import MetaRegimeClassifier

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

    from sonar.regimes.types import (
        CccsSnapshot,
        EcsSnapshot,
        FcsSnapshot,
        MscSnapshot,
    )


log = structlog.get_logger()


__all__ = [
    "T1_COUNTRIES",
    "BackfillReport",
    "app",
    "backfill_country",
    "iter_classifiable_triplets",
]


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_IO = 4

# The original Tier-1 7-country roster; UK is opt-in via --country UK
# per Sprint I convention (see daily_monetary_indices.py).
T1_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")


@dataclass(slots=True)
class BackfillReport:
    """Counters for a single backfill invocation."""

    eligible: int = 0
    classified: int = 0
    persisted: int = 0
    skipped_duplicate: int = 0
    skipped_insufficient: int = 0
    per_country: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def iter_classifiable_triplets(
    session: Session,
    country_code: str,
    *,
    from_date: date | None = None,
) -> Iterator[date]:
    """Yield dates where ``country`` has any L4 row but no ``l5_meta_regimes`` row.

    The classifier itself enforces the ≥ 3/4 Policy-1 threshold — this
    iterator is deliberately permissive: dates with 1/4 cycles show up
    and are surfaced as ``skipped_insufficient`` in the report.
    """
    ecs_dates = set(
        session.execute(
            select(EconomicCycleScore.date).where(EconomicCycleScore.country_code == country_code)
        )
        .scalars()
        .all()
    )
    cccs_dates = set(
        session.execute(
            select(CreditCycleScore.date).where(CreditCycleScore.country_code == country_code)
        )
        .scalars()
        .all()
    )
    fcs_dates = set(
        session.execute(
            select(FinancialCycleScore.date).where(FinancialCycleScore.country_code == country_code)
        )
        .scalars()
        .all()
    )
    msc_dates = set(
        session.execute(
            select(MonetaryCycleScore.date).where(MonetaryCycleScore.country_code == country_code)
        )
        .scalars()
        .all()
    )
    l5_dates = set(
        session.execute(select(L5MetaRegime.date).where(L5MetaRegime.country_code == country_code))
        .scalars()
        .all()
    )
    candidate_dates = (ecs_dates | cccs_dates | fcs_dates | msc_dates) - l5_dates
    if from_date is not None:
        candidate_dates = {d for d in candidate_dates if d >= from_date}
    yield from sorted(candidate_dates)


def _snapshots_for(
    session: Session, country_code: str, observation_date: date
) -> tuple[
    EcsSnapshot | None,
    CccsSnapshot | None,
    FcsSnapshot | None,
    MscSnapshot | None,
]:
    """Fetch the four L4 rows + build Snapshots; ``None`` for missing cycles."""
    ecs_row = session.execute(
        select(EconomicCycleScore)
        .where(
            EconomicCycleScore.country_code == country_code,
            EconomicCycleScore.date == observation_date,
        )
        .order_by(EconomicCycleScore.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    cccs_row = session.execute(
        select(CreditCycleScore)
        .where(
            CreditCycleScore.country_code == country_code,
            CreditCycleScore.date == observation_date,
        )
        .order_by(CreditCycleScore.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    fcs_row = session.execute(
        select(FinancialCycleScore)
        .where(
            FinancialCycleScore.country_code == country_code,
            FinancialCycleScore.date == observation_date,
        )
        .order_by(FinancialCycleScore.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    msc_row = session.execute(
        select(MonetaryCycleScore)
        .where(
            MonetaryCycleScore.country_code == country_code,
            MonetaryCycleScore.date == observation_date,
        )
        .order_by(MonetaryCycleScore.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return (
        build_ecs_snapshot_from_orm(ecs_row),
        build_cccs_snapshot_from_orm(cccs_row),
        build_fcs_snapshot_from_orm(fcs_row),
        build_msc_snapshot_from_orm(msc_row),
    )


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------


def backfill_country(
    session: Session,
    country_code: str,
    *,
    from_date: date | None = None,
    dry_run: bool = True,
    report: BackfillReport | None = None,
) -> BackfillReport:
    """Backfill one country's missing L5 rows; returns an updated :class:`BackfillReport`."""
    classifier = MetaRegimeClassifier()
    rep = report if report is not None else BackfillReport()
    country_count = 0
    for obs_date in iter_classifiable_triplets(session, country_code, from_date=from_date):
        rep.eligible += 1
        ecs, cccs, fcs, msc = _snapshots_for(session, country_code, obs_date)
        inputs = build_l5_inputs_from_snapshots(
            country_code, obs_date, ecs=ecs, cccs=cccs, fcs=fcs, msc=msc
        )
        try:
            result = classifier.classify(inputs)
        except InsufficientL4DataError:
            rep.skipped_insufficient += 1
            log.info(
                "l5_backfill.insufficient",
                country=country_code,
                date=obs_date.isoformat(),
                available=inputs.available_count(),
            )
            continue

        rep.classified += 1
        country_count += 1
        if dry_run:
            log.info(
                "l5_backfill.dry_run",
                country=country_code,
                date=obs_date.isoformat(),
                meta_regime=str(result.meta_regime),
                confidence=result.confidence,
            )
            continue

        try:
            persist_l5_meta_regime_result(session, result)
        except DuplicatePersistError:
            rep.skipped_duplicate += 1
            log.info(
                "l5_backfill.duplicate",
                country=country_code,
                date=obs_date.isoformat(),
            )
        else:
            rep.persisted += 1
            log.info(
                "l5_backfill.persisted",
                country=country_code,
                date=obs_date.isoformat(),
                meta_regime=str(result.meta_regime),
            )
    if country_count:
        rep.per_country[country_code] = country_count
    return rep


# ---------------------------------------------------------------------------
# Typer CLI
# ---------------------------------------------------------------------------


app = typer.Typer(no_args_is_help=True, help="Backfill L5 meta-regime rows for historical dates.")


@app.command("run")
def cli_run(
    country: str = typer.Option("", "--country", help="Single ISO 3166-1 alpha-2."),
    all_t1: bool = typer.Option(
        False,  # noqa: FBT003
        "--all-t1",
        help="Iterate the seven Tier-1 countries (US/DE/PT/IT/ES/FR/NL).",
    ),
    from_date: str = typer.Option(
        "",
        "--from-date",
        help="ISO date; only backfill dates >= this anchor. Default: all history.",
    ),
    dry_run: bool = typer.Option(
        True,  # noqa: FBT003
        "--dry-run/--execute",
        help="Default dry-run reports counts; --execute writes rows.",
    ),
) -> None:
    """Backfill L5 rows for missing ``(country, date)`` triplets."""
    if not country and not all_t1:
        typer.echo("Must pass --country or --all-t1", err=True)
        sys.exit(EXIT_USAGE)
    countries: list[str] = list(T1_COUNTRIES) if all_t1 else [country.upper()]

    from_date_obj: date | None = None
    if from_date:
        try:
            from_date_obj = date.fromisoformat(from_date)
        except ValueError:
            typer.echo(f"Invalid --from-date={from_date!r}; expected ISO YYYY-MM-DD", err=True)
            sys.exit(EXIT_USAGE)

    session = SessionLocal()
    report = BackfillReport()
    try:
        for code in countries:
            backfill_country(
                session,
                code,
                from_date=from_date_obj,
                dry_run=dry_run,
                report=report,
            )
    except Exception as exc:
        typer.echo(f"backfill failed: {exc}", err=True)
        sys.exit(EXIT_IO)
    finally:
        session.close()

    title = "DRY-RUN" if dry_run else "EXECUTED"
    typer.echo(
        f"[l5-backfill {title}] eligible={report.eligible} "
        f"classified={report.classified} persisted={report.persisted} "
        f"insufficient={report.skipped_insufficient} duplicate={report.skipped_duplicate}"
    )
    for code, n in sorted(report.per_country.items()):
        typer.echo(f"  - {code}: {n}")
    sys.exit(EXIT_OK)


if __name__ == "__main__":  # pragma: no cover
    app()
