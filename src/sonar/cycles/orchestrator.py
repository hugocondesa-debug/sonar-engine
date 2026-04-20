"""Cycles orchestrator — compute + persist CCCS + FCS + MSC for (country, date).

Thin dispatch layer over the per-cycle modules. Gracefully skips any
cycle whose compute raises :class:`InsufficientCycleInputsError` so a
single missing upstream row doesn't sink the full pass.

CLI::

    python -m sonar.cycles.orchestrator --country US --date 2024-01-31

Exit codes:

* ``0`` — all requested cycles computed (or skipped with log).
* ``1`` — CLI argument error.
* ``3`` — duplicate persist collision.
* ``4`` — IO / unexpected.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

import structlog
import typer

from sonar.cycles.base import InsufficientCycleInputsError
from sonar.cycles.credit_cccs import (
    CccsComputedResult,
    compute_cccs,
    persist_cccs_result,
)
from sonar.cycles.financial_fcs import (
    FcsComputedResult,
    compute_fcs,
    persist_fcs_result,
)
from sonar.cycles.monetary_msc import (
    MscComputedResult,
    compute_msc,
    persist_msc_result,
)
from sonar.db.session import SessionLocal

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = structlog.get_logger()

EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_DUPLICATE = 3
EXIT_IO = 4


@dataclass(frozen=True, slots=True)
class CyclesOrchestrationResult:
    """Per-(country, date) cycles-composite outcome bundle."""

    country_code: str
    observation_date: date
    cccs: CccsComputedResult | None
    fcs: FcsComputedResult | None
    msc: MscComputedResult | None
    skips: dict[str, str]


def compute_all_cycles(
    session: Session,
    country_code: str,
    observation_date: date,
    *,
    persist: bool = True,
) -> CyclesOrchestrationResult:
    """Compute CCCS + FCS + MSC; ``persist=False`` leaves results in-memory.

    Each cycle's :class:`InsufficientCycleInputsError` is caught and
    recorded in the ``skips`` map; the orchestrator continues with the
    remaining cycles. Other exceptions propagate.
    """
    skips: dict[str, str] = {}

    cccs_result: CccsComputedResult | None = None
    try:
        cccs_result = compute_cccs(session, country_code, observation_date)
        if persist:
            persist_cccs_result(session, cccs_result)
    except InsufficientCycleInputsError as exc:
        skips["CCCS"] = str(exc)
        log.info("cycles.cccs.skipped", country=country_code, error=str(exc))

    fcs_result: FcsComputedResult | None = None
    try:
        fcs_result = compute_fcs(session, country_code, observation_date)
        if persist:
            persist_fcs_result(session, fcs_result)
    except InsufficientCycleInputsError as exc:
        skips["FCS"] = str(exc)
        log.info("cycles.fcs.skipped", country=country_code, error=str(exc))

    msc_result: MscComputedResult | None = None
    try:
        msc_result = compute_msc(session, country_code, observation_date)
        if persist:
            persist_msc_result(session, msc_result)
    except InsufficientCycleInputsError as exc:
        skips["MSC"] = str(exc)
        log.info("cycles.msc.skipped", country=country_code, error=str(exc))

    return CyclesOrchestrationResult(
        country_code=country_code,
        observation_date=observation_date,
        cccs=cccs_result,
        fcs=fcs_result,
        msc=msc_result,
        skips=skips,
    )


def main(
    country: str = typer.Option(..., "--country", help="ISO 3166-1 alpha-2 country."),
    target_date: str = typer.Option(..., "--date", help="ISO date (e.g. 2024-01-31)."),
    cycles_only: bool = typer.Option(
        True,  # noqa: FBT003 — typer positional default
        "--cycles-only",
        help="Reserved flag — cycles orchestrator already isolated from indices.",
    ),
) -> None:
    """Run CCCS + FCS cycle composites for ``(country, date)``."""
    _ = cycles_only
    try:
        obs_date = date.fromisoformat(target_date)
    except ValueError:
        typer.echo(f"Invalid --date={target_date!r}; expected ISO YYYY-MM-DD", err=True)
        sys.exit(EXIT_CONFIG)

    session = SessionLocal()
    try:
        outcome = compute_all_cycles(session, country, obs_date, persist=True)
    finally:
        session.close()

    cccs_score = outcome.cccs.score_0_100 if outcome.cccs else None
    fcs_score = outcome.fcs.score_0_100 if outcome.fcs else None
    msc_score = outcome.msc.score_0_100 if outcome.msc else None
    log.info(
        "cycles.orchestrator.complete",
        country=country,
        date=obs_date.isoformat(),
        cccs_score=cccs_score,
        cccs_regime=outcome.cccs.regime if outcome.cccs else None,
        fcs_score=fcs_score,
        fcs_regime=outcome.fcs.regime if outcome.fcs else None,
        msc_score=msc_score,
        msc_regime_6band=outcome.msc.regime_6band if outcome.msc else None,
        msc_regime_3band=outcome.msc.regime_3band if outcome.msc else None,
        skips=outcome.skips,
    )
    sys.exit(EXIT_OK)


if __name__ == "__main__":  # pragma: no cover
    typer.run(main)
