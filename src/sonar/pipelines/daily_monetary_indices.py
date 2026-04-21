"""Daily monetary indices pipeline — orchestrate M1/M2/M4 persistence.

Mirrors :mod:`sonar.pipelines.daily_economic_indices` (which itself mirrors
the credit + financial templates). Uses the
:class:`sonar.indices.monetary.builders.MonetaryInputsBuilder` facade
shipped in Week 6 Sprint 2b and the sync
:func:`sonar.indices.monetary.orchestrator.compute_all_monetary_indices`
orchestrator.

**Scope this sprint (Week 7 Sprint B)**:

- M1 / M2 / M4 live via the async builders on ``MonetaryInputsBuilder``.
  Non-US/EA combinations raise :class:`NotImplementedError` inside the
  facade and the pipeline logs a ``monetary_pipeline.builder_skipped``
  warning instead of crashing.
- M3 Market Expectations is **not** wired to the live path — its inputs
  come from persisted NSS + expected-inflation overlays (L2), not from
  L0 connectors directly, same as E2 in the economic pipeline. M3 stays
  out of this sprint and the pipeline persists only M1/M2/M4.
- EA M2 / M4 are explicitly not supported by the Sprint-2b builder
  (``NotImplementedError`` with a Week 7 pointer). The pipeline catches
  those and routes to a structured skip log so the --all-t1 loop
  continues.

CLI::

    python -m sonar.pipelines.daily_monetary_indices --country US --date 2024-12-31
    python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2024-12-31

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
    persist_many_monetary_results,
)
from sonar.db.session import SessionLocal
from sonar.indices.monetary.builders import MonetaryInputsBuilder
from sonar.indices.monetary.m3_market_expectations import (
    compute_m3_market_expectations_anchor,
)
from sonar.indices.monetary.orchestrator import (
    MonetaryIndicesInputs,
    MonetaryIndicesResults,
    compute_all_monetary_indices,
)
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from sonar.indices.base import IndexResult
    from sonar.indices.monetary.db_backed_builder import MonetaryDbBackedInputsBuilder


log = structlog.get_logger()

__all__ = [
    "MONETARY_SUPPORTED_COUNTRIES",
    "T1_7_COUNTRIES",
    "InputsBuilder",
    "MonetaryPipelineOutcome",
    "build_live_monetary_inputs",
    "default_inputs_builder",
    "main",
    "run_one",
]

# Kept module-private — public surface guarded via __all__. Tests import
# directly via module path.

T1_7_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")

# Monetary pipeline accepts GB via BoE -> FRED cascade (sprint 8-I).
# Kept separate from T1_7_COUNTRIES so --all-t1 preserves the historical
# 7-country semantics; callers opt in to GB via --country GB (or the
# deprecated "UK" alias — ADR-0007).
#
# Backward compat: "UK" preserved as deprecated alias. CLI emits a
# structlog deprecation warning when ``--country UK`` is passed and
# forwards the code verbatim — builders.py still dispatches on "UK"
# during Sprint O due to carve-out. The canonical ``GB`` entry is
# accepted syntactically; end-to-end GB dispatch lands with the
# post-Sprint-L chore commit that finalises builders.py
# (CAL-128 closure).
MONETARY_SUPPORTED_COUNTRIES: tuple[str, ...] = ("US", "EA", "GB", "UK")

# ADR-0007 deprecated country aliases. Map ``alias -> canonical``.
_DEPRECATED_COUNTRY_ALIASES: dict[str, str] = {"UK": "GB"}


def _warn_if_deprecated_alias(country_code: str) -> None:
    """Emit a structlog deprecation warning when ``country_code`` is an alias.

    Canonical codes are silent. Used at CLI entry to signal migration to
    operators still passing ``--country UK``. The alias value is passed
    through verbatim to downstream builders during Sprint O (carve-out
    preserves ``builders.py`` UK dispatch).
    """
    upper = country_code.upper()
    canonical = _DEPRECATED_COUNTRY_ALIASES.get(upper)
    if canonical is None:
        return
    log.warning(
        "monetary_pipeline.deprecated_country_alias",
        alias=upper,
        canonical=canonical,
        adr="ADR-0007",
    )


EXIT_OK = 0
EXIT_NO_INPUTS = 1
EXIT_DUPLICATE = 3
EXIT_IO = 4


class InputsBuilder(Protocol):
    """Build :class:`MonetaryIndicesInputs` for a ``(country, date)``."""

    def __call__(
        self,
        session: Session,
        country_code: str,
        observation_date: date,
    ) -> MonetaryIndicesInputs: ...


def default_inputs_builder(
    session: Session,  # noqa: ARG001 — Protocol compatibility
    country_code: str,
    observation_date: date,
) -> MonetaryIndicesInputs:
    """MVP default — empty bundle so orchestrator skips gracefully (test path)."""
    return MonetaryIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
    )


async def build_live_monetary_inputs(
    country_code: str,
    observation_date: date,
    *,
    builder: MonetaryInputsBuilder,
    history_years: int = 15,
) -> MonetaryIndicesInputs:
    """Live builder — invokes the MonetaryInputsBuilder facade.

    ``NotImplementedError`` from the facade for non-supported
    ``(country, index)`` combinations (e.g., M2 EA, M4 EA) is caught
    and logged as ``monetary_pipeline.builder_skipped``; the slot is
    left ``None`` and the orchestrator skips that sub-index.
    ``InsufficientDataError`` is likewise caught.

    ``history_years`` defaults to 15 (Tier-4 fallback) to keep live
    canary wall-clock tractable; callers can opt into the canonical
    30Y via the CLI ``--history-years`` flag.
    """
    country = country_code.upper()
    m1 = m2 = m4 = None
    try:
        m1 = await builder.build_m1_inputs(country, observation_date, history_years=history_years)
    except (NotImplementedError, InsufficientDataError, ValueError) as exc:
        log.warning(
            "monetary_pipeline.builder_skipped",
            index="m1",
            country=country,
            error=str(exc),
        )
    try:
        m2 = await builder.build_m2_inputs(country, observation_date, history_years=history_years)
    except (NotImplementedError, InsufficientDataError, ValueError) as exc:
        log.warning(
            "monetary_pipeline.builder_skipped",
            index="m2",
            country=country,
            error=str(exc),
        )
    try:
        m4 = await builder.build_m4_inputs(country, observation_date, history_years=history_years)
    except (NotImplementedError, InsufficientDataError, ValueError) as exc:
        log.warning(
            "monetary_pipeline.builder_skipped",
            index="m4",
            country=country,
            error=str(exc),
        )
    return MonetaryIndicesInputs(
        country_code=country,
        observation_date=observation_date,
        m1=m1,
        m2=m2,
        m4=m4,
    )


@dataclass(frozen=True, slots=True)
class MonetaryPipelineOutcome:
    country_code: str
    observation_date: date
    results: MonetaryIndicesResults
    persisted: dict[str, int]


def run_one(
    session: Session,
    country_code: str,
    observation_date: date,
    *,
    inputs_builder: InputsBuilder | None = None,
    db_backed_builder: MonetaryDbBackedInputsBuilder | None = None,
) -> MonetaryPipelineOutcome:
    """Single ``(country, date)`` pipeline run: build → compute → persist.

    When ``db_backed_builder`` is supplied the pipeline additionally
    reads persisted NSS forwards + EXPINF rows via
    :meth:`MonetaryDbBackedInputsBuilder.build_m3_inputs` and routes the
    computed M3 IndexResult through ``persist_many_monetary_results``'s
    ``m3=`` kwarg (CAL-108). Missing rows keep ``m3=None`` so the
    orchestrator reports a clean skip.
    """
    builder = inputs_builder or default_inputs_builder
    inputs = builder(session, country_code, observation_date)
    results = compute_all_monetary_indices(inputs)

    m3_result: IndexResult | None = None
    if db_backed_builder is not None:
        try:
            m3_inputs = db_backed_builder.build_m3_inputs(country_code, observation_date)
        except Exception as exc:
            log.warning(
                "monetary_pipeline.db_backed_m3_error",
                country=country_code,
                error=str(exc),
            )
            m3_inputs = None
        if m3_inputs is not None:
            try:
                m3_result = compute_m3_market_expectations_anchor(m3_inputs)
            except InsufficientDataError as exc:
                log.warning(
                    "monetary_pipeline.m3_insufficient_data",
                    country=country_code,
                    error=str(exc),
                )

    persisted = persist_many_monetary_results(session, results, m3=m3_result)
    log.info(
        "monetary_pipeline.persisted",
        country=country_code,
        date=observation_date.isoformat(),
        persisted=persisted,
        skips=results.skips,
    )
    return MonetaryPipelineOutcome(
        country_code=country_code,
        observation_date=observation_date,
        results=results,
        persisted=persisted,
    )


def _build_live_connectors(
    *,
    fred_api_key: str,
    te_api_key: str,
    cache_dir: str,
) -> tuple[MonetaryInputsBuilder, list[object]]:
    """Instantiate live monetary connectors + bundle them for aclose().

    TE is optional: when ``te_api_key`` is empty the builder falls
    through to BoE → FRED (stale-flagged) for the GB cascade.
    """
    from sonar.connectors.boe_database import BoEDatabaseConnector  # noqa: PLC0415
    from sonar.connectors.cbo import CboConnector  # noqa: PLC0415
    from sonar.connectors.ecb_sdw import EcbSdwConnector  # noqa: PLC0415
    from sonar.connectors.fred import FredConnector  # noqa: PLC0415
    from sonar.connectors.te import TEConnector  # noqa: PLC0415

    fred = FredConnector(api_key=fred_api_key, cache_dir=f"{cache_dir}/fred")
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=f"{cache_dir}/ecb")
    boe = BoEDatabaseConnector(cache_dir=f"{cache_dir}/boe")
    te = TEConnector(api_key=te_api_key, cache_dir=f"{cache_dir}/te") if te_api_key else None
    builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb, boe=boe, te=te)
    connectors: list[object] = [fred, ecb, boe]
    if te is not None:
        connectors.append(te)
    return builder, connectors


def _live_inputs_builder_factory(
    *,
    builder: MonetaryInputsBuilder,
    history_years: int,
) -> InputsBuilder:
    """Wrap the async live builder into the synchronous InputsBuilder Protocol."""

    def _builder(
        session: Session,  # noqa: ARG001 — Protocol compatibility
        country_code: str,
        observation_date: date,
    ) -> MonetaryIndicesInputs:
        return asyncio.run(
            build_live_monetary_inputs(
                country_code,
                observation_date,
                builder=builder,
                history_years=history_years,
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
    te_api_key: str = typer.Option(
        "",
        "--te-api-key",
        envvar="TE_API_KEY",
        help=(
            "TradingEconomics API key — unlocks the GB M1 TE-primary cascade "
            "(Sprint I-patch). Optional; FRED OECD mirror is used when absent."
        ),
    ),
    cache_dir: str = typer.Option(
        ".cache/daily_monetary",
        "--cache-dir",
        help="Connector cache directory.",
    ),
    history_years: int = typer.Option(
        15,
        "--history-years",
        help="Rolling-window span (years) for M1/M2/M4 histories (canonical 30, Tier-4 15).",
    ),
) -> None:
    """Run the daily monetary-indices pipeline."""
    try:
        obs_date = date.fromisoformat(target_date)
    except ValueError:
        typer.echo(f"Invalid --date={target_date!r}; expected ISO YYYY-MM-DD", err=True)
        sys.exit(EXIT_IO)

    targets: list[str] = list(T1_7_COUNTRIES) if all_t1 else [country]
    if not targets or targets == [""]:
        typer.echo("Must pass --country or --all-t1", err=True)
        sys.exit(EXIT_IO)
    for t in targets:
        _warn_if_deprecated_alias(t)
    if backend not in {"default", "live"}:
        typer.echo(f"Unknown --backend={backend!r}; expected 'default' or 'live'", err=True)
        sys.exit(EXIT_IO)

    builder: InputsBuilder = default_inputs_builder
    connectors_to_close: list[object] = []
    if backend == "live":
        if not fred_api_key:
            typer.echo("FRED_API_KEY required for --backend=live", err=True)
            sys.exit(EXIT_IO)
        monetary_builder, connectors_to_close = _build_live_connectors(
            fred_api_key=fred_api_key, te_api_key=te_api_key, cache_dir=cache_dir
        )
        builder = _live_inputs_builder_factory(
            builder=monetary_builder, history_years=history_years
        )

    session = SessionLocal()
    # Always spin up the DB-backed reader so M3 fills when daily_curves
    # + daily_overlays have persisted the NSS forwards + EXPINF row for
    # the country/date (CAL-108). Additive over live M1/M2/M4.
    from sonar.indices.monetary.db_backed_builder import (  # noqa: PLC0415
        MonetaryDbBackedInputsBuilder as _MonetaryDbBackedInputsBuilder,
    )

    db_backed = _MonetaryDbBackedInputsBuilder(session)
    exit_code = EXIT_OK
    try:
        for c in targets:
            try:
                outcome = run_one(
                    session, c, obs_date, inputs_builder=builder, db_backed_builder=db_backed
                )
                if sum(outcome.persisted.values()) == 0:
                    log.warning(
                        "monetary_pipeline.no_inputs",
                        country=c,
                        date=obs_date.isoformat(),
                        skips=outcome.results.skips,
                    )
                    exit_code = exit_code or EXIT_NO_INPUTS
            except DuplicatePersistError as exc:
                log.error("monetary_pipeline.duplicate", country=c, error=str(exc))
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
