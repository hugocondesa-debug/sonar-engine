"""L8 ``daily-curves`` pipeline — Week 2 US-only skeleton.

Orchestrates a single (country, date) tuple end-to-end:
L0 FRED fetch → L2 NSS fit + derive (zero / forward / real) → L1 persist.

Week 3 generalises the loop across `country_tiers.yaml` T1; Week 2 ships
US only as the Day 4 skeleton (per
``docs/planning/week2-close-sprint-brief.md`` §3 D4-1/3).

CLI entrypoint:

    python -m sonar.pipelines.daily_curves --country US --date 2024-01-02

Exit codes:

* ``0`` — clean run, all 4 sibling rows persisted.
* ``1`` — ``InsufficientDataError`` from validation/fit.
* ``2`` — ``ConvergenceError`` from optimizer.
* ``3`` — ``DuplicatePersistError`` (triplet already in DB).
* ``4`` — IO / network / unexpected exception.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import structlog
import typer

from sonar.config import settings
from sonar.connectors.fred import FredConnector
from sonar.db.persistence import DuplicatePersistError, persist_nss_fit_result
from sonar.db.session import SessionLocal
from sonar.overlays.exceptions import ConvergenceError, InsufficientDataError
from sonar.overlays.nss import (
    NSSInput,
    _label_to_years,
    assemble_nss_fit_result,
    derive_forward_curve,
    derive_real_curve,
    derive_zero_curve,
    fit_nss,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from sonar.overlays.nss import NSSFitResult

log = structlog.get_logger()

EXIT_OK = 0
EXIT_INSUFFICIENT_DATA = 1
EXIT_CONVERGENCE = 2
EXIT_DUPLICATE = 3
EXIT_IO = 4


async def run_us(
    observation_date: date,
    session: Session,
    fred: FredConnector,
) -> NSSFitResult:
    """Single-country (US) end-to-end: fetch → fit → derive → persist.

    Returns the assembled ``NSSFitResult`` after a successful persist.
    """
    nominals = await fred.fetch_yield_curve_nominal(country="US", observation_date=observation_date)
    linkers = await fred.fetch_yield_curve_linker(country="US", observation_date=observation_date)

    labels = sorted(nominals.keys(), key=_label_to_years)
    nss_input = NSSInput(
        tenors_years=np.array([_label_to_years(t) for t in labels]),
        yields=np.array([nominals[t].yield_bps / 10_000.0 for t in labels]),
        country_code="US",
        observation_date=observation_date,
        curve_input_type="par",
    )
    spot = fit_nss(nss_input)
    zero = derive_zero_curve(spot)
    forward = derive_forward_curve(zero)

    linker_yields = {t: linkers[t].yield_bps / 10_000.0 for t in linkers}
    real = derive_real_curve(
        spot,
        linker_yields=linker_yields if linker_yields else None,
        observation_date=observation_date,
        country_code="US",
    )

    result = assemble_nss_fit_result(
        country_code="US",
        observation_date=observation_date,
        spot=spot,
        zero=zero,
        forward=forward,
        real=real,
    )
    persist_nss_fit_result(session, result, source_connector="fred")
    log.info(
        "daily_curves.persisted",
        country="US",
        date=observation_date.isoformat(),
        fit_id=str(result.fit_id),
        rmse_bps=spot.rmse_bps,
        confidence=spot.confidence,
    )
    return result


def _run_us_sync(observation_date: date, cache_dir: Path, api_key: str) -> int:
    async def _orchestrate() -> int:
        fred = FredConnector(api_key=api_key, cache_dir=str(cache_dir))
        session = SessionLocal()
        try:
            await run_us(observation_date, session, fred)
        except InsufficientDataError as exc:
            log.error("daily_curves.insufficient_data", error=str(exc))
            return EXIT_INSUFFICIENT_DATA
        except ConvergenceError as exc:
            log.error("daily_curves.convergence_failed", error=str(exc))
            return EXIT_CONVERGENCE
        except DuplicatePersistError as exc:
            log.error("daily_curves.duplicate", error=str(exc))
            return EXIT_DUPLICATE
        finally:
            await fred.aclose()
            session.close()
        return EXIT_OK

    return asyncio.run(_orchestrate())


def main(
    country: str = typer.Option(
        ..., "--country", help="ISO 3166-1 alpha-2 country code (Week 2: US only)."
    ),
    target_date: str = typer.Option(..., "--date", help="ISO date (e.g. 2024-01-02)."),
    cache_dir: Path = typer.Option(  # noqa: B008
        Path(".cache/fred"), "--cache-dir", help="FRED disk cache directory."
    ),
) -> None:
    """Run the daily-curves pipeline for ``--country`` on ``--date``."""
    if country != "US":
        typer.echo(f"Week 2 supports US only; got country={country}", err=True)
        sys.exit(EXIT_IO)

    placeholder = "your_fred_api_key_here"  # pragma: allowlist secret
    if not settings.fred_api_key or settings.fred_api_key == placeholder:
        typer.echo("FRED_API_KEY not configured in .env", err=True)
        sys.exit(EXIT_IO)

    try:
        obs_date = date.fromisoformat(target_date)
    except ValueError:
        typer.echo(f"Invalid --date={target_date!r}; expected ISO YYYY-MM-DD", err=True)
        sys.exit(EXIT_IO)

    cache_dir.mkdir(parents=True, exist_ok=True)
    code = _run_us_sync(obs_date, cache_dir, settings.fred_api_key)
    sys.exit(code)


if __name__ == "__main__":
    typer.run(main)
