"""L0 BIS ingestion pipeline — daily pass for 7 T1 countries.

Fetches WS_TC (credit-to-GDP), WS_DSR, WS_CREDIT_GAP for each T1 country
and persists the observations into ``bis_credit_raw``. Idempotent via
upsert: re-runs skip rows with identical ``fetch_response_hash``; if the
hash differs the row is updated in place and a ``BIS_DATA_REVISION``
warning is logged.

Intended cadence: daily. At 1 req/sec polite pacing x 7 countries x
3 dataflows = ~21 s per full pass. Sequential by design; parallelism
deferred to a future CAL if we ever outgrow this.

CLI::

    python -m sonar.pipelines.daily_bis_ingestion \\
        --start-date 2024-01-01 --end-date 2024-07-01 \\
        --countries US,DE --dataflows WS_TC,WS_DSR

Defaults: last 90 days back from today, all 7 T1 countries, all 3
dataflows.

Exit codes:

* ``0`` — success (all fetches OK, persistence green)
* ``1`` — config error (bad CLI args / unknown country / unknown dataflow)
* ``2`` — partial (some countries succeeded, others failed)
* ``3`` — total failure (all fetches failed — network / BIS outage)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import typer

from sonar.connectors.bis import BisConnector, BisObservation
from sonar.db.persistence import BisRawObservation, persist_bis_raw_observations
from sonar.db.session import SessionLocal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.orm import Session

log = structlog.get_logger()

T1_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")
DATAFLOWS: tuple[str, ...] = ("WS_TC", "WS_DSR", "WS_CREDIT_GAP")
# BIS credit aggregates publish quarterly with a ~2-quarter lag (e.g. on
# 2026-04-21 the latest available WS_TC quarter is 2025-Q3). A 90-day
# window falls entirely inside that publication lag and returns HTTP 404
# for every (country, dataflow) pair. 540 days ≈ 6 quarters guarantees
# the window overlaps at least the last 4 published quarters even if BIS
# stalls a release. CAL-136 (Week 9 Sprint AA) raised this from 90.
DEFAULT_LOOKBACK_DAYS: int = 540

UNIT_DESCRIPTOR: dict[str, str] = {
    "WS_TC": "pct_gdp",
    "WS_DSR": "dsr_pct",
    "WS_CREDIT_GAP": "gap_pp",
}

EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_PARTIAL = 2
EXIT_TOTAL_FAILURE = 3


def _hash_obs(obs: BisObservation) -> str:
    """Deterministic hash over the observation value + key.

    Used as ``fetch_response_hash`` so revision detection fires when BIS
    republishes the same quarter with a different value. Full-response
    hashing is avoided (BIS responses embed timestamps / metadata that
    would break hash stability across fetches).
    """
    payload = json.dumps(
        {
            "country": obs.country_code,
            "date": obs.observation_date.isoformat(),
            "value_pct": obs.value_pct,
            "series_key": obs.source_series_key,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _to_raw(obs: BisObservation, dataflow: str) -> BisRawObservation:
    return BisRawObservation(
        country_code=obs.country_code,
        date=obs.observation_date,
        dataflow=dataflow,
        value_raw=obs.value_pct,
        unit_descriptor=UNIT_DESCRIPTOR[dataflow],
        fetch_response_hash=_hash_obs(obs),
    )


async def _fetch_one(
    connector: BisConnector, country: str, dataflow: str, start: date, end: date
) -> list[BisObservation]:
    if dataflow == "WS_TC":
        return await connector.fetch_credit_stock_ratio(country, start, end)
    if dataflow == "WS_DSR":
        return await connector.fetch_dsr(country, start, end)
    if dataflow == "WS_CREDIT_GAP":
        return await connector.fetch_credit_gap(country, start, end)
    msg = f"Unknown dataflow: {dataflow}"
    raise ValueError(msg)


async def run_ingestion(
    session: Session,
    connector: BisConnector,
    countries: Sequence[str],
    dataflows: Sequence[str],
    start_date: date,
    end_date: date,
) -> dict[str, object]:
    """Sequentially fetch + persist observations for every (country, dataflow).

    Returns a report dict with per-pair outcome + aggregate counts,
    suitable for CLI exit-code mapping.
    """
    per_pair: list[dict[str, object]] = []
    totals = {"new": 0, "skipped": 0, "updated": 0}
    successes = 0
    failures = 0
    for country in countries:
        for dataflow in dataflows:
            try:
                observations = await _fetch_one(connector, country, dataflow, start_date, end_date)
            except Exception as exc:
                log.error(
                    "bis_ingest.fetch_failed",
                    country=country,
                    dataflow=dataflow,
                    error=str(exc),
                )
                per_pair.append(
                    {
                        "country": country,
                        "dataflow": dataflow,
                        "error": str(exc),
                    }
                )
                failures += 1
                continue
            raws = [_to_raw(o, dataflow) for o in observations]
            counts = persist_bis_raw_observations(session, raws)
            for k in totals:
                totals[k] += counts[k]
            per_pair.append(
                {
                    "country": country,
                    "dataflow": dataflow,
                    "fetched": len(observations),
                    **counts,
                }
            )
            successes += 1
    return {
        "totals": totals,
        "successes": successes,
        "failures": failures,
        "per_pair": per_pair,
    }


def _parse_csv_list(raw: str, allowed: tuple[str, ...]) -> list[str]:
    """Split comma-separated CLI input, validate membership in ``allowed``."""
    if not raw:
        return list(allowed)
    items = [x.strip() for x in raw.split(",") if x.strip()]
    unknown = [x for x in items if x not in allowed]
    if unknown:
        msg = f"Unknown values {unknown!r}; allowed: {allowed}"
        raise typer.BadParameter(msg)
    return items


def main(
    start_date: str = typer.Option("", "--start-date", help="ISO start date; default=today-90d."),
    end_date: str = typer.Option("", "--end-date", help="ISO end date; default=today."),
    countries: str = typer.Option("", "--countries", help="CSV country codes; default=all 7 T1."),
    dataflows: str = typer.Option(
        "", "--dataflows", help="CSV dataflows; default=WS_TC,WS_DSR,WS_CREDIT_GAP."
    ),
    cache_dir: Path = typer.Option(  # noqa: B008
        Path(".cache/bis"), "--cache-dir", help="BIS disk cache directory."
    ),
) -> None:
    """Run the daily BIS ingestion pass."""
    today = date.today()  # noqa: DTZ011 — calendar date only, no tz semantics
    try:
        start = (
            date.fromisoformat(start_date)
            if start_date
            else today - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        )
        end = date.fromisoformat(end_date) if end_date else today
    except ValueError as exc:
        typer.echo(f"Invalid date: {exc}", err=True)
        sys.exit(EXIT_CONFIG)
    if start > end:
        typer.echo(f"start-date {start} after end-date {end}", err=True)
        sys.exit(EXIT_CONFIG)
    try:
        target_countries = _parse_csv_list(countries, T1_COUNTRIES)
        target_dataflows = _parse_csv_list(dataflows, DATAFLOWS)
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        sys.exit(EXIT_CONFIG)

    cache_dir.mkdir(parents=True, exist_ok=True)

    async def _orchestrate() -> dict[str, object]:
        connector = BisConnector(cache_dir=str(cache_dir))
        session = SessionLocal()
        try:
            return await run_ingestion(
                session, connector, target_countries, target_dataflows, start, end
            )
        finally:
            await connector.aclose()
            session.close()

    report = asyncio.run(_orchestrate())
    log.info(
        "bis_ingest.complete",
        totals=report["totals"],
        successes=report["successes"],
        failures=report["failures"],
    )
    if report["failures"] == 0:
        sys.exit(EXIT_OK)
    if report["successes"] == 0:
        sys.exit(EXIT_TOTAL_FAILURE)
    sys.exit(EXIT_PARTIAL)


if __name__ == "__main__":
    typer.run(main)
