"""``sonar backfill`` — historical fill orchestrators.

Sprint 2 (Week 11) shipped ``nss-curves`` — the 10-country tenor
backfill orchestrator described in
:mod:`sonar.overlays.nss_curves_backfill`.

Sprint 1.1 (Week 11) adds ``expinf-us-bei`` — fetches + persists US
BEI rows from FRED, then re-runs the canonical T1 orchestrator so the
new rows compose into ``exp_inflation_canonical`` alongside the
SURVEY / SWAP / DERIVED legs already shipped by Sprint 1.

Sprint 3 (Week 11) adds ``erp-daily`` — US 60-business-day backfill
for the 4-method ERP overlay (DCF + Gordon + EY + CAPE + canonical).
See :mod:`sonar.overlays.erp_daily.backfill` for input plumbing.

Future sprints register additional sub-commands under the same
``sonar backfill <name>`` namespace.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import structlog
import typer

from sonar.config import settings
from sonar.db.session import SessionLocal
from sonar.overlays.erp_daily.backfill import (
    DEFAULT_LOOKBACK_BD as ERP_DEFAULT_LOOKBACK_BD,
    backfill_erp_us,
)
from sonar.overlays.expected_inflation.backfill import (
    T1_COUNTRIES,
    backfill_canonical_t1,
    backfill_us_bei,
)
from sonar.overlays.nss_curves_backfill import (
    DEFAULT_LOOKBACK_BD,
    T1_SPOT_BACKFILL_COUNTRIES,
    backfill_nss_curves,
)

log = structlog.get_logger()

app = typer.Typer(
    name="backfill",
    help="Historical-fill orchestrators (Sprint 2: nss-curves, Sprint 1.1: expinf-us-bei).",
    no_args_is_help=True,
    add_completion=False,
)

EXIT_OK = 0
EXIT_IO = 4


@app.command("nss-curves")
def nss_curves(
    start: str = typer.Option(
        "",
        "--start",
        help=(
            "Inclusive start date (ISO YYYY-MM-DD). When omitted, the "
            "trailing --lookback-bd business days end at --end / today."
        ),
    ),
    end: str = typer.Option(
        "",
        "--end",
        help="Inclusive end date (ISO YYYY-MM-DD). Defaults to today (UTC).",
    ),
    lookback_bd: int = typer.Option(
        DEFAULT_LOOKBACK_BD,
        "--lookback-bd",
        help="Trailing business-day window when --start is omitted.",
    ),
    cache_dir: Path = typer.Option(  # noqa: B008 — Typer convention
        Path(".cache/curves"),
        "--cache-dir",
        help="Connector disk cache (per-connector subdir).",
    ),
    skip_gb_real: bool = typer.Option(
        False,  # noqa: FBT003 — Typer flag
        "--skip-gb-real",
        help="Skip the Pattern B real-only fill for GB existing spot rows.",
    ),
) -> None:
    """Backfill 4-sibling NSS rows for 10 T1 countries (GB excluded from
    spot phase) over a date window.

    Idempotent per ADR-0011 P1 — re-running on the same window is safe;
    rows already persisted are skipped at the per-(country, date) level.
    """
    start_d: date | None = None
    end_d: date | None = None
    try:
        if start:
            start_d = date.fromisoformat(start)
        if end:
            end_d = date.fromisoformat(end)
    except ValueError as exc:
        typer.echo(f"Invalid date: {exc}", err=True)
        sys.exit(EXIT_IO)

    cache_dir.mkdir(parents=True, exist_ok=True)

    async def _run() -> int:
        summary = await backfill_nss_curves(
            start=start_d,
            end=end_d,
            lookback_bd=lookback_bd,
            countries=T1_SPOT_BACKFILL_COUNTRIES,
            cache_dir=cache_dir,
            fill_gb_real=not skip_gb_real,
        )
        window = (
            f"{summary.dates_window[0].isoformat()}..{summary.dates_window[1].isoformat()}"
            if summary.dates_window
            else "(empty)"
        )
        typer.echo(f"nss-curves backfill window: {window}")
        typer.echo(f"  persisted (full 4-sibling): {summary.persisted_full}")
        typer.echo(f"  skipped (existing):        {summary.skipped_existing}")
        typer.echo(f"  skipped (insufficient):    {summary.skipped_insufficient}")
        typer.echo(f"  failed:                    {summary.failed}")
        typer.echo(
            f"  GB real-only fill: persisted={summary.gb_real_persisted} "
            f"skipped={summary.gb_real_skipped}",
        )
        return EXIT_OK

    sys.exit(asyncio.run(_run()))


def _bdays_in_range(start: date, end: date) -> int:
    """Count business days in ``[start, end]`` inclusive."""
    return len(pd.bdate_range(start=pd.Timestamp(start), end=pd.Timestamp(end)))


@app.command("expinf-us-bei")
def expinf_us_bei(
    start: str = typer.Option(..., "--start", help="ISO start date (inclusive)."),
    end: str = typer.Option(..., "--end", help="ISO end date (inclusive)."),
    skip_canonical: bool = typer.Option(
        False,  # noqa: FBT003
        "--skip-canonical",
        help="Persist BEI rows only; skip the canonical T1 rerun.",
    ),
) -> None:
    """Sprint 1.1: US BEI backfill via FRED + canonical rerun for T1 cohort.

    Persists ``exp_inflation_bei`` rows for ``country_code='US'`` over
    the requested window, then re-runs :func:`backfill_canonical_t1`
    so the new BEI rows compose into ``exp_inflation_canonical``.

    The canonical rerun covers the full T1 cohort
    (``US/EA/DE/FR/IT/ES/PT/GB/JP/CA``) — Sprint 1 shipped the writer
    code but the canonical orchestrator was never executed against
    the live DB, so this run also fills the 9 non-US rows from the
    already-persisted SURVEY / synthesised SWAP / DERIVED legs.
    """
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if end_date < start_date:
        msg = f"end ({end}) precedes start ({start})"
        raise typer.BadParameter(msg)

    lookback_bd = _bdays_in_range(start_date, end_date)
    typer.echo(f"US BEI backfill: start={start} end={end} lookback_bd={lookback_bd}")

    with SessionLocal() as session:
        bei_result = asyncio.run(backfill_us_bei(session, lookback_bd=lookback_bd, as_of=end_date))
        typer.echo(
            f"  exp_inflation_bei US: inserted={bei_result.inserted} "
            f"duplicate={bei_result.duplicate} "
            f"skipped_no_spot={bei_result.skipped_no_spot} "
            f"errors={bei_result.errors}"
        )

        if skip_canonical:
            typer.echo("Canonical rerun skipped (--skip-canonical).")
            return

        canonical = backfill_canonical_t1(
            session,
            lookback_bd=lookback_bd,
            as_of=end_date,
            countries=T1_COUNTRIES,
        )
        typer.echo(
            f"  exp_inflation_canonical T1: "
            f"canonical_inserted={canonical.canonical_inserted} "
            f"canonical_skipped={canonical.canonical_skipped} "
            f"swap_inserted={canonical.swap_inserted} "
            f"derived_inserted={canonical.derived_inserted}"
        )


@app.command("erp-daily")
def erp_daily(
    start: str = typer.Option(..., "--start", help="ISO start date (inclusive)."),
    end: str = typer.Option(..., "--end", help="ISO end date (inclusive)."),
    cache_dir: Path = typer.Option(  # noqa: B008 — Typer convention
        Path(".cache/erp_daily"),
        "--cache-dir",
        help="Connector disk cache (per-connector subdir).",
    ),
) -> None:
    """Sprint 3: US ERP daily backfill (SPX) — 60bd default window.

    Reads risk-free yields from ``yield_curves_spot/real`` (US 10Y),
    SP500 daily close from FRED, Shiller monthly snapshot for CAPE +
    trailing earnings, and Damodaran monthly histimpl for the
    cross-validation hook (US only). Persists 5 sibling rows per
    business day (DCF + Gordon + EY + CAPE + canonical) sharing one
    ``erp_id`` UUID.

    Idempotent: ``DuplicatePersistError`` is treated as
    ``skipped_existing``; safe to re-run on any window.
    """
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if end_date < start_date:
        msg = f"end ({end}) precedes start ({start})"
        raise typer.BadParameter(msg)

    fred_api_key = os.environ.get("FRED_API_KEY") or settings.fred_api_key
    if not fred_api_key:
        typer.echo("FRED_API_KEY not set — required for SP500 daily fetch.", err=True)
        sys.exit(EXIT_IO)

    cache_dir.mkdir(parents=True, exist_ok=True)
    bdays = _bdays_in_range(start_date, end_date)
    typer.echo(
        f"erp-daily backfill: start={start} end={end} bdays={bdays} "
        f"(default window: {ERP_DEFAULT_LOOKBACK_BD} bd)"
    )

    with SessionLocal() as session:
        summary = asyncio.run(
            backfill_erp_us(
                session,
                start=start_date,
                end=end_date,
                cache_dir=cache_dir,
                fred_api_key=fred_api_key,
            )
        )

    window = (
        f"{summary.dates_window[0].isoformat()}..{summary.dates_window[1].isoformat()}"
        if summary.dates_window
        else "(empty)"
    )
    typer.echo(f"erp-daily backfill window: {window}")
    typer.echo(f"  persisted (full 5-sibling): {summary.persisted}")
    typer.echo(f"  skipped (existing):        {summary.skipped_existing}")
    typer.echo(f"  skipped (no inputs):       {summary.skipped_no_inputs}")
    typer.echo(f"  errors:                    {summary.errors}")
