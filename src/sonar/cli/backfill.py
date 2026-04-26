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

Sprint 3.1 (Week 11) adds ``erp-external`` — Damodaran monthly US
implied-ERP backfill (Sep 2008 onwards). Adjacent to the computed
``erp_canonical`` (Sprint 3); spec ``overlays/erp-daily.md`` §11
"compute, don't consume" preserved. See
:mod:`sonar.overlays.erp_external.backfill` for the orchestrator.

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
from sonar.connectors.te import TEConnector
from sonar.db.session import SessionLocal
from sonar.overlays.erp_daily.backfill import (
    DEFAULT_LOOKBACK_BD as ERP_DEFAULT_LOOKBACK_BD,
    backfill_erp_us,
)
from sonar.overlays.erp_external.backfill import (
    DAMODARAN_MONTHLY_START,
    backfill_damodaran_monthly,
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
from sonar.overlays.rating_spread_backfill import (
    TIER1_COUNTRIES as RATING_TIER1_COUNTRIES,
    backfill_calibration_april_2026,
    backfill_consolidate,
    backfill_te_current_snapshot,
    backfill_te_historical,
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


@app.command("erp-external")
def erp_external(
    source: str = typer.Option(
        "damodaran",
        "--source",
        help="External source. Sprint 3.1 ships only 'damodaran'.",
    ),
    start: str = typer.Option(
        DAMODARAN_MONTHLY_START.isoformat(),
        "--start",
        help=(
            "ISO start month (YYYY-MM-DD). Clamped forward to the "
            f"Damodaran archive start ({DAMODARAN_MONTHLY_START.isoformat()}) "
            "when older."
        ),
    ),
    end: str = typer.Option(
        ...,
        "--end",
        help=(
            "ISO end month (YYYY-MM-DD). Damodaran has ~2-month publication "
            "lag; months unavailable upstream are counted as 'unavailable'."
        ),
    ),
    cache_dir: Path = typer.Option(  # noqa: B008 — Typer convention
        Path(".cache/erp_external"),
        "--cache-dir",
        help="Connector disk cache (per-connector subdir).",
    ),
) -> None:
    """Sprint 3.1: Damodaran monthly US ERP external-reference backfill.

    Persists ``erp_external_reference`` rows with ``source='damodaran_monthly'``
    for each calendar month in ``[start, end]`` (idempotent via
    ``UNIQUE (market_index, date, source)``).

    Adjacent to the computed ``erp_canonical`` (Sprint 3); does NOT
    modify ``erp_canonical`` rows. Spec ``overlays/erp-daily.md`` §11
    "compute, don't consume" preserved.
    """
    if source != "damodaran":
        typer.echo(
            f"Unsupported source: {source!r}. Sprint 3.1 ships only 'damodaran'.",
            err=True,
        )
        raise typer.Exit(EXIT_IO)

    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError as exc:
        typer.echo(f"Invalid date: {exc}", err=True)
        raise typer.Exit(EXIT_IO) from exc

    if end_date < start_date:
        msg = f"end ({end}) precedes start ({start})"
        raise typer.BadParameter(msg)

    cache_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(
        f"erp-external backfill: source={source} start={start_date.isoformat()} "
        f"end={end_date.isoformat()}"
    )

    with SessionLocal() as session:
        result = asyncio.run(
            backfill_damodaran_monthly(
                session,
                cache_dir=cache_dir,
                start=start_date,
                end=end_date,
            )
        )

    typer.echo(f"erp-external backfill window: {start_date.isoformat()}..{end_date.isoformat()}")
    typer.echo(f"  persisted:            {result.persisted}")
    typer.echo(f"  skipped_existing:     {result.skipped_existing}")
    typer.echo(f"  skipped_unavailable:  {result.skipped_unavailable}")
    typer.echo(f"  skipped_insufficient: {result.skipped_insufficient}")
    typer.echo(f"  errors:               {result.errors}")


@app.command("rating-spread")
def rating_spread(
    include_historical: bool = typer.Option(
        False,  # noqa: FBT003 — Typer flag
        "--include-historical",
        help=(
            "Also fetch the per-country historical archive "
            "(/ratings/historical/{country}). Slower; ~30-60s for the "
            "Tier 1 cohort with the connector cache cold."
        ),
    ),
    countries: str = typer.Option(
        "",
        "--countries",
        help=(
            "Comma-separated ISO 3166-1 alpha-2 codes to back-fill. Default = "
            "Tier 1 cohort (US,DE,FR,IT,ES,PT,GB,JP,CA,AU + Sprint 6 "
            "expansion NL,NZ,CH,SE,NO)."
        ),
    ),
    cache_dir: Path = typer.Option(  # noqa: B008 — Typer convention
        Path(".cache/rating_spread"),
        "--cache-dir",
        help="Connector disk cache (per-connector subdir).",
    ),
) -> None:
    """TE-driven rating-spread backfill (Tier 1 sovereigns; Sprint 4 + Sprint 6).

    Pipeline:

    1. Seed ``ratings_spread_calibration`` from ``APRIL_2026_CALIBRATION``
       (22 rows; idempotent).
    2. Fetch ``/ratings`` snapshot, persist agency_raw rows for the
       requested cohort (current snapshot — observation date = today UTC).
    3. (Optional) Fetch ``/ratings/historical/{country}`` for each
       cohort country, persist all archived actions.
    4. Run :func:`backfill_consolidate` over every distinct
       ``(country, date, rating_type)`` tuple in agency_raw and
       harmonise sibling ``rating_id`` to the consolidated UUID.

    Idempotent at every step via UNIQUE constraints — safe to re-run.
    """
    cohort: tuple[str, ...]
    if countries.strip():
        cohort = tuple(c.strip().upper() for c in countries.split(",") if c.strip())
        unknown = [c for c in cohort if c not in RATING_TIER1_COUNTRIES]
        if unknown:
            typer.echo(
                f"Unknown country code(s) (not in Tier 1 cohort): "
                f"{','.join(unknown)}. Allowed: "
                f"{','.join(RATING_TIER1_COUNTRIES)}.",
                err=True,
            )
            raise typer.Exit(EXIT_IO)
    else:
        cohort = RATING_TIER1_COUNTRIES

    te_api_key = os.environ.get("TE_API_KEY") or settings.te_api_key
    if not te_api_key:
        typer.echo(
            "TE_API_KEY not set — required for /ratings + /ratings/historical fetch.",
            err=True,
        )
        raise typer.Exit(EXIT_IO)

    cache_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(
        f"rating-spread backfill: cohort={','.join(cohort)} include_historical={include_historical}"
    )

    async def _run() -> int:
        te = TEConnector(api_key=te_api_key, cache_dir=str(cache_dir / "te"))
        try:
            with SessionLocal() as session:
                cal_persisted = backfill_calibration_april_2026(session)
                typer.echo(f"  calibration seed: persisted={cal_persisted} (notch 0-21)")

                snap = await backfill_te_current_snapshot(
                    session,
                    te_connector=te,
                    countries=cohort,
                )
                typer.echo(
                    f"  agency_raw current: persisted={snap.agency_raw_persisted} "
                    f"skipped_existing={snap.agency_raw_skipped_existing} "
                    f"skipped_invalid={snap.agency_raw_skipped_invalid} "
                    f"countries={snap.countries_processed} "
                    f"unmappable={snap.countries_unmappable}"
                )

                if include_historical:
                    hist = await backfill_te_historical(
                        session,
                        te_connector=te,
                        countries=cohort,
                    )
                    typer.echo(
                        f"  agency_raw historical: persisted={hist.agency_raw_persisted} "
                        f"skipped_existing={hist.agency_raw_skipped_existing} "
                        f"skipped_invalid={hist.agency_raw_skipped_invalid} "
                        f"actions_fetched={hist.historical_actions_fetched}"
                    )

                cons = backfill_consolidate(session)
                typer.echo(
                    f"  consolidated: persisted={cons.consolidated_persisted} "
                    f"skipped_existing={cons.consolidated_skipped_existing} "
                    f"skipped_insufficient={cons.consolidated_skipped_insufficient}"
                )
        finally:
            await te.aclose()
        return EXIT_OK

    sys.exit(asyncio.run(_run()))
