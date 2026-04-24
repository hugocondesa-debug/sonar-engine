"""Sprint Q.2 — backfill ``exp_inflation_bei`` for GB from BoE yield curves.

Bridges :class:`~sonar.connectors.boe_yield_curves.BoeYieldCurvesConnector`
to :func:`~sonar.indices.monetary.exp_inflation_writers.persist_bei_row`,
with idempotency per ADR-0011 Principle 1.

Usage::

    # Dry-run (default):
    python -m sonar.scripts.backfill_boe_bei --date-start 2020-01-01

    # Execute a full 2020 → today backfill:
    python -m sonar.scripts.backfill_boe_bei --date-start 2020-01-01 \\
        --date-end 2026-04-24 --execute

The script only targets GB for now — BoE publishes GB BEI exclusively.
Extensions to other sovereigns would come from different yield-curve
archives (e.g. TIPS for US, which we already source canonically).
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, date, datetime

import structlog
import typer

from sonar.connectors.boe_yield_curves import BoeBeiSpotObservation, BoeYieldCurvesConnector
from sonar.db.session import SessionLocal
from sonar.indices.monetary.exp_inflation_writers import persist_bei_row

log = structlog.get_logger()

app = typer.Typer(add_completion=False, help=__doc__)

METHODOLOGY_VERSION: str = "EXPINF_BEI_v1.0"
LINKER_CONNECTOR: str = "BOE_GLC_INFLATION"
BEI_FLAGS: tuple[str, ...] = ("BEI_FITTED_IMPLIED",)


def _today_utc() -> date:
    return datetime.now(tz=UTC).date()


async def _fetch_curve(
    date_start: date,
    date_end: date,
) -> list[BoeBeiSpotObservation]:
    connector = BoeYieldCurvesConnector()
    try:
        return await connector.fetch_inflation_spot_curve(date_start, date_end)
    finally:
        await connector.aclose()


@app.command()
def main(
    date_start: str = typer.Option(..., "--date-start", help="ISO date, inclusive"),
    date_end: str | None = typer.Option(
        None, "--date-end", help="ISO date, inclusive (default: today UTC)"
    ),
    execute: bool = typer.Option(
        False,  # noqa: FBT003
        "--execute",
        help="Required to actually write; default is dry-run.",
    ),
) -> None:
    """Fetch BoE implied-inflation spot curves + persist to exp_inflation_bei."""
    start = date.fromisoformat(date_start)
    end = date.fromisoformat(date_end) if date_end else _today_utc()

    log.info(
        "backfill_boe_bei.start",
        country="GB",
        date_start=start.isoformat(),
        date_end=end.isoformat(),
        execute=execute,
    )

    try:
        observations = asyncio.run(_fetch_curve(start, end))
    except Exception as exc:
        log.error("backfill_boe_bei.fetch_failed", error=str(exc))
        sys.exit(4)

    log.info(
        "backfill_boe_bei.fetched",
        rows=len(observations),
        first=observations[0].observation_date.isoformat() if observations else None,
        last=observations[-1].observation_date.isoformat() if observations else None,
    )

    if not execute:
        log.info("backfill_boe_bei.dry_run_complete", rows=len(observations))
        return

    inserted = 0
    skipped = 0
    session = SessionLocal()
    try:
        for obs in observations:
            did_insert = persist_bei_row(
                session,
                country_code=obs.country_code,
                observation_date=obs.observation_date,
                bei_tenors_decimal=obs.tenors,
                linker_connector=LINKER_CONNECTOR,
                methodology_version=METHODOLOGY_VERSION,
                flags=BEI_FLAGS,
            )
            if did_insert:
                inserted += 1
            else:
                skipped += 1
        session.commit()
    except Exception as exc:
        session.rollback()
        log.error("backfill_boe_bei.persist_failed", error=str(exc))
        sys.exit(4)
    finally:
        session.close()

    log.info(
        "backfill_boe_bei.complete",
        inserted=inserted,
        skipped_duplicates=skipped,
    )


if __name__ == "__main__":
    app()
