"""``sonar backfill`` — historical fill orchestrators.

Sprint 2 (Week 11) ships the first sub-command: ``nss-curves``, the
10-country tenor backfill orchestrator described in
:mod:`sonar.overlays.nss_curves_backfill`. Future sprints register
additional sub-commands under the same ``sonar backfill <name>``
namespace.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

import structlog
import typer

from sonar.overlays.nss_curves_backfill import (
    DEFAULT_LOOKBACK_BD,
    T1_SPOT_BACKFILL_COUNTRIES,
    backfill_nss_curves,
)

log = structlog.get_logger()

app = typer.Typer(
    name="backfill",
    help="Historical-fill orchestrators (Sprint 2: nss-curves).",
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
