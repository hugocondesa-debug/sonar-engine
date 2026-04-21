"""Daily economic indices pipeline — orchestrate E1/E3/E4 persistence.

Mirrors :mod:`sonar.pipelines.daily_credit_indices` (CLI + session +
exit-code convention) and :mod:`sonar.pipelines.daily_financial_indices`
(empty-bundle InputsBuilder pattern).

**Scope this sprint (Week 7 Sprint B)**:

- E1 / E3 / E4 live via the async builders shipped in Sprint 2a
  (``sonar.indices.economic.builders``), wrapped through ``asyncio.run``
  inside the synchronous :func:`run_one` entry point.
- E2 Leading is deliberately **not** wired to the live path — its
  inputs come from persisted NSS curves + expected-inflation overlays
  (L2), not from L0 connectors directly. The empty default builder
  leaves ``e2=None`` and the orchestrator would skip E2 anyway. Wiring
  is a follow-on CAL.
- For non-US countries the economic builders still return partial
  :class:`...Inputs` bundles; the compute modules raise
  :class:`InsufficientDataError` if a mandatory component is missing,
  which this pipeline catches and logs as a skip (no crash).

CLI::

    python -m sonar.pipelines.daily_economic_indices --country US --date 2024-12-31
    python -m sonar.pipelines.daily_economic_indices --all-t1 --date 2024-12-31

Exit codes mirror :mod:`daily_cost_of_capital`: 0 clean, 1 no inputs,
3 duplicate, 4 IO.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

import structlog
import typer

from sonar.db.persistence import (
    DuplicatePersistError,
    persist_many_economic_results,
)
from sonar.db.session import SessionLocal
from sonar.indices.economic.builders import (
    build_e1_inputs,
    build_e3_inputs,
    build_e4_inputs,
)
from sonar.indices.economic.e1_activity import (
    E1ActivityInputs,
    E1ActivityResult,
    compute_e1_activity,
)
from sonar.indices.economic.e2_leading import E2Inputs, compute_e2_leading_slope
from sonar.indices.economic.e3_labor import (
    E3LaborInputs,
    E3LaborResult,
    compute_e3_labor,
)
from sonar.indices.economic.e4_sentiment import (
    E4SentimentInputs,
    E4SentimentResult,
    compute_e4_sentiment,
)
from sonar.indices.exceptions import InsufficientInputsError as E2InsufficientInputsError
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from sonar.connectors.eurostat import EurostatConnector
    from sonar.connectors.fred import FredConnector
    from sonar.connectors.te import TEConnector
    from sonar.indices.base import IndexResult
    from sonar.indices.economic.db_backed_builder import EconomicDbBackedInputsBuilder

log = structlog.get_logger()

__all__ = [
    "T1_7_COUNTRIES",
    "EconomicIndicesInputs",
    "EconomicIndicesResults",
    "EconomicPipelineOutcome",
    "InputsBuilder",
    "build_live_economic_inputs",
    "compute_all_economic_indices",
    "default_inputs_builder",
    "main",
    "run_one",
]

T1_7_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")

EXIT_OK = 0
EXIT_NO_INPUTS = 1
EXIT_DUPLICATE = 3
EXIT_IO = 4


@dataclass(frozen=True, slots=True)
class EconomicIndicesInputs:
    """Bundle of E1/E2/E3/E4 inputs.

    E2 populated via :class:`EconomicDbBackedInputsBuilder` (CAL-108);
    E1/E3/E4 via the async live connector builders.
    """

    country_code: str
    observation_date: date
    e1: E1ActivityInputs | None = None
    e2: E2Inputs | None = None
    e3: E3LaborInputs | None = None
    e4: E4SentimentInputs | None = None


@dataclass(frozen=True, slots=True)
class EconomicIndicesResults:
    """Outputs bundle — one field per economic sub-index (``None`` when skipped)."""

    country_code: str
    observation_date: date
    e1: E1ActivityResult | None = None
    e2: IndexResult | None = None
    e3: E3LaborResult | None = None
    e4: E4SentimentResult | None = None
    skips: dict[str, str] | None = None


class InputsBuilder(Protocol):
    """Build :class:`EconomicIndicesInputs` for a ``(country, date)``."""

    def __call__(
        self,
        session: Session,
        country_code: str,
        observation_date: date,
    ) -> EconomicIndicesInputs: ...


def default_inputs_builder(
    session: Session,  # noqa: ARG001 — Protocol compatibility
    country_code: str,
    observation_date: date,
) -> EconomicIndicesInputs:
    """MVP default — empty bundle so orchestrator skips gracefully (test path)."""
    return EconomicIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
    )


async def build_live_economic_inputs(
    country_code: str,
    observation_date: date,
    *,
    fred: FredConnector,
    eurostat: EurostatConnector,
    te: TEConnector | None = None,
) -> EconomicIndicesInputs:
    """Live builder — invokes the async E1/E3/E4 builders from Sprint 2a.

    Any builder that fails (e.g., connector 404, mandatory field
    missing) is logged as ``economic_pipeline.builder_error`` and its
    input slot left ``None`` so the orchestrator can skip that index
    without crashing the whole run.
    """
    e1: E1ActivityInputs | None = None
    e3: E3LaborInputs | None = None
    e4: E4SentimentInputs | None = None

    try:
        e1 = await build_e1_inputs(country_code, observation_date, fred=fred, eurostat=eurostat)
    except (InsufficientDataError, ValueError) as exc:
        log.warning(
            "economic_pipeline.builder_error", index="e1", country=country_code, error=str(exc)
        )
    try:
        e3 = await build_e3_inputs(country_code, observation_date, fred=fred, eurostat=eurostat)
    except (InsufficientDataError, ValueError) as exc:
        log.warning(
            "economic_pipeline.builder_error", index="e3", country=country_code, error=str(exc)
        )
    try:
        e4 = await build_e4_inputs(
            country_code, observation_date, fred=fred, eurostat=eurostat, te=te
        )
    except (InsufficientDataError, ValueError) as exc:
        log.warning(
            "economic_pipeline.builder_error", index="e4", country=country_code, error=str(exc)
        )

    return EconomicIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
        e1=e1,
        e3=e3,
        e4=e4,
    )


def compute_all_economic_indices(inputs: EconomicIndicesInputs) -> EconomicIndicesResults:
    """Run E1/E2/E3/E4 independently, catching compute failures as skips."""
    skips: dict[str, str] = {}
    e1: E1ActivityResult | None = None
    e2: IndexResult | None = None
    e3: E3LaborResult | None = None
    e4: E4SentimentResult | None = None

    if inputs.e1 is not None:
        try:
            e1 = compute_e1_activity(inputs.e1)
        except InsufficientDataError as exc:
            skips["e1"] = str(exc)
    else:
        skips["e1"] = "no inputs provided"

    if inputs.e2 is not None:
        try:
            e2 = compute_e2_leading_slope(inputs.e2)
        except (InsufficientDataError, E2InsufficientInputsError) as exc:
            skips["e2"] = str(exc)
    else:
        skips["e2"] = "no inputs provided"

    if inputs.e3 is not None:
        try:
            e3 = compute_e3_labor(inputs.e3)
        except InsufficientDataError as exc:
            skips["e3"] = str(exc)
    else:
        skips["e3"] = "no inputs provided"

    if inputs.e4 is not None:
        try:
            e4 = compute_e4_sentiment(inputs.e4)
        except InsufficientDataError as exc:
            skips["e4"] = str(exc)
    else:
        skips["e4"] = "no inputs provided"

    return EconomicIndicesResults(
        country_code=inputs.country_code,
        observation_date=inputs.observation_date,
        e1=e1,
        e2=e2,
        e3=e3,
        e4=e4,
        skips=skips,
    )


@dataclass(frozen=True, slots=True)
class EconomicPipelineOutcome:
    country_code: str
    observation_date: date
    results: EconomicIndicesResults
    persisted: dict[str, int]


def run_one(
    session: Session,
    country_code: str,
    observation_date: date,
    *,
    inputs_builder: InputsBuilder | None = None,
    db_backed_builder: EconomicDbBackedInputsBuilder | None = None,
) -> EconomicPipelineOutcome:
    """Single ``(country, date)`` pipeline run: build → compute → persist.

    When ``db_backed_builder`` is supplied the pipeline additionally
    reads persisted NSS rows via :meth:`EconomicDbBackedInputsBuilder.build_e2_inputs`
    and merges the result into the live bundle. The overlay path is
    additive — live E1/E3/E4 slots are preserved; only ``e2`` is filled
    when DB rows are available (CAL-108). Missing NSS rows keep
    ``e2 is None`` and the orchestrator logs a clean skip.
    """
    builder = inputs_builder or default_inputs_builder
    inputs = builder(session, country_code, observation_date)
    if db_backed_builder is not None:
        try:
            e2_inputs = db_backed_builder.build_e2_inputs(country_code, observation_date)
        except Exception as exc:
            log.warning(
                "economic_pipeline.db_backed_e2_error",
                country=country_code,
                error=str(exc),
            )
            e2_inputs = None
        if e2_inputs is not None:
            inputs = EconomicIndicesInputs(
                country_code=inputs.country_code,
                observation_date=inputs.observation_date,
                e1=inputs.e1,
                e2=e2_inputs,
                e3=inputs.e3,
                e4=inputs.e4,
            )
    results = compute_all_economic_indices(inputs)
    persisted = persist_many_economic_results(
        session, e1=results.e1, e2=results.e2, e3=results.e3, e4=results.e4
    )
    log.info(
        "economic_pipeline.persisted",
        country=country_code,
        date=observation_date.isoformat(),
        persisted=persisted,
        skips=results.skips,
    )
    return EconomicPipelineOutcome(
        country_code=country_code,
        observation_date=observation_date,
        results=results,
        persisted=persisted,
    )


def _live_inputs_builder_factory(
    *,
    fred: FredConnector,
    eurostat: EurostatConnector,
    te: TEConnector | None = None,
) -> InputsBuilder:
    """Wrap the async live builder into the synchronous InputsBuilder Protocol."""

    def _builder(
        session: Session,  # noqa: ARG001 — Protocol compatibility
        country_code: str,
        observation_date: date,
    ) -> EconomicIndicesInputs:
        return asyncio.run(
            build_live_economic_inputs(
                country_code, observation_date, fred=fred, eurostat=eurostat, te=te
            )
        )

    return _builder


def main(
    country: str = typer.Option("", "--country", help="ISO 3166-1 alpha-2 (omit with --all-t1)."),
    target_date: str = typer.Option(..., "--date", help="ISO date (e.g. 2024-12-31)."),
    all_t1: bool = typer.Option(
        False,  # noqa: FBT003
        "--all-t1",
        help="Iterate over all 7 T1 countries (US/DE/PT/IT/ES/FR/NL).",
    ),
    backend: str = typer.Option(
        "live",
        "--backend",
        help="Inputs source: 'live' (async connector fetch) or 'default' (empty bundle).",
    ),
    fred_api_key: str = typer.Option(
        "",
        "--fred-api-key",
        envvar="FRED_API_KEY",
        help="FRED API key for live backend.",
    ),
    cache_dir: str = typer.Option(
        ".cache/daily_economic",
        "--cache-dir",
        help="Connector cache directory.",
    ),
) -> None:
    """Run the daily economic-indices pipeline."""
    try:
        obs_date = date.fromisoformat(target_date)
    except ValueError:
        typer.echo(f"Invalid --date={target_date!r}; expected ISO YYYY-MM-DD", err=True)
        sys.exit(EXIT_IO)

    targets: list[str] = list(T1_7_COUNTRIES) if all_t1 else [country]
    if not targets or targets == [""]:
        typer.echo("Must pass --country or --all-t1", err=True)
        sys.exit(EXIT_IO)
    if backend not in {"default", "live"}:
        typer.echo(f"Unknown --backend={backend!r}; expected 'default' or 'live'", err=True)
        sys.exit(EXIT_IO)

    builder: InputsBuilder = default_inputs_builder
    connectors_to_close: list[object] = []
    if backend == "live":
        if not fred_api_key:
            typer.echo("FRED_API_KEY required for --backend=live", err=True)
            sys.exit(EXIT_IO)
        # Local imports — connectors only instantiated on live backend so the
        # default path keeps a zero-dependency CLI footprint.
        from sonar.connectors.eurostat import EurostatConnector  # noqa: PLC0415
        from sonar.connectors.fred import FredConnector  # noqa: PLC0415

        fred = FredConnector(api_key=fred_api_key, cache_dir=f"{cache_dir}/fred")
        eurostat = EurostatConnector(cache_dir=f"{cache_dir}/eurostat")
        connectors_to_close.extend([fred, eurostat])
        builder = _live_inputs_builder_factory(fred=fred, eurostat=eurostat)

    session = SessionLocal()
    # Always spin up the DB-backed reader so E2 fills when daily_curves
    # has persisted rows for the country/date — CAL-108 makes this
    # additive over whatever live path the bundle assembles.
    from sonar.indices.economic.db_backed_builder import (  # noqa: PLC0415
        EconomicDbBackedInputsBuilder as _EconomicDbBackedInputsBuilder,
    )

    db_backed = _EconomicDbBackedInputsBuilder(session)
    exit_code = EXIT_OK
    try:
        for c in targets:
            try:
                outcome = run_one(
                    session, c, obs_date, inputs_builder=builder, db_backed_builder=db_backed
                )
                if sum(outcome.persisted.values()) == 0:
                    log.warning(
                        "economic_pipeline.no_inputs",
                        country=c,
                        date=obs_date.isoformat(),
                        skips=outcome.results.skips,
                    )
                    exit_code = exit_code or EXIT_NO_INPUTS
            except DuplicatePersistError as exc:
                log.error("economic_pipeline.duplicate", country=c, error=str(exc))
                exit_code = EXIT_DUPLICATE
    finally:
        session.close()
        for conn in connectors_to_close:
            close = getattr(conn, "aclose", None)
            if close is not None:
                asyncio.run(close())
    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    typer.run(main)
