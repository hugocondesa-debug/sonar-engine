"""L8 daily-overlays pipeline — orchestrate 4 L2 overlays post daily_curves.

Mirrors :mod:`sonar.pipelines.daily_curves` CLI/session/exit-code
conventions and the :mod:`sonar.pipelines.daily_economic_indices` +
:mod:`sonar.pipelines.daily_monetary_indices` Sprint B pattern
(orchestrator + graceful skip + batch persist).

Pipeline stages per ``(country, date)`` tuple:

1. **Precondition**: verify that :class:`NSSYieldCurveSpot` has been
   persisted by ``daily_curves`` for the same triplet — the
   expected-inflation DERIVED path needs NSS forwards, and ERP + CRP
   lean on the risk-free from the same curve.
2. **Parallel gather** (``asyncio.gather`` with
   ``return_exceptions=True``): ERP + CRP + rating-spread +
   expected-inflation compute concurrently; each helper catches its
   own overlay-specific exceptions and returns ``None`` on soft fail
   so the gather never short-circuits.
3. **Batch persist** via
   :func:`sonar.db.persistence.persist_many_overlay_results`.

CLI::

    python -m sonar.pipelines.daily_overlays --country US --date 2024-12-31
    python -m sonar.pipelines.daily_overlays --all-t1 --date 2024-12-31

Exit codes mirror :mod:`daily_curves`: ``0`` clean, ``1`` insufficient
data, ``2`` convergence, ``3`` duplicate, ``4`` IO.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, Protocol

import structlog
import typer

from sonar.db.models import NSSYieldCurveSpot
from sonar.db.persistence import DuplicatePersistError
from sonar.db.session import SessionLocal
from sonar.overlays.exceptions import (
    ConvergenceError,
    InsufficientDataError,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from sonar.indices.base import IndexResult
    from sonar.overlays.crp import CRPCanonical
    from sonar.overlays.erp import ERPFitResult, ERPInput
    from sonar.overlays.rating_spread import ConsolidatedRating


log = structlog.get_logger()

__all__ = [
    "T1_7_COUNTRIES",
    "DailyOverlaysOutcome",
    "InputsBuilder",
    "OverlayBundle",
    "OverlayResults",
    "StaticInputsBuilder",
    "build_erp_us_bundle",
    "build_expected_inflation_bundle",
    "build_rating_bundle",
    "build_sov_spread_crp_bundle",
    "default_inputs_builder",
    "main",
    "nss_spot_exists",
    "run_one",
]


T1_7_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")

EXIT_OK = 0
EXIT_INSUFFICIENT_DATA = 1
EXIT_CONVERGENCE = 2
EXIT_DUPLICATE = 3
EXIT_IO = 4


# ---------------------------------------------------------------------------
# Per-overlay inputs + results bundles
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OverlayBundle:
    """Pre-assembled inputs per overlay for a single ``(country, date)`` run.

    Each field is ``None`` when the caller cannot source that overlay's
    inputs — the orchestrator then routes a structured skip rather than
    crashing.
    """

    country_code: str
    observation_date: date
    erp: ERPInput | None = None
    crp: dict[str, Any] | None = None  # kwargs for crp.build_canonical
    rating: dict[str, Any] | None = None  # kwargs for rating_spread.consolidate
    expected_inflation: dict[str, Any] | None = (
        None  # kwargs for expected_inflation.build_canonical
    )


@dataclass(frozen=True, slots=True)
class OverlayResults:
    """Outputs bundle — one field per overlay (``None`` when skipped)."""

    country_code: str
    observation_date: date
    erp: ERPFitResult | None = None
    crp: CRPCanonical | None = None
    rating: ConsolidatedRating | None = None
    expected_inflation: IndexResult | None = None
    skips: dict[str, str] | None = None


# ---------------------------------------------------------------------------
# DAG precondition
# ---------------------------------------------------------------------------


def nss_spot_exists(session: Session, country_code: str, observation_date: date) -> bool:
    """Return ``True`` when ``yield_curves_spot`` already has a row for the triplet.

    The ``(country, date)`` tuple is matched without regard for
    ``methodology_version`` — any fitted NSS curve satisfies the DAG
    precondition. Callers that need a minimum confidence should apply
    their own filter.
    """
    row = (
        session.query(NSSYieldCurveSpot)
        .filter(
            NSSYieldCurveSpot.country_code == country_code,
            NSSYieldCurveSpot.date == observation_date,
        )
        .first()
    )
    return row is not None


# ---------------------------------------------------------------------------
# Inputs builder Protocol + default
# ---------------------------------------------------------------------------


class InputsBuilder(Protocol):
    """Build :class:`OverlayBundle` for a ``(country, date)``."""

    def __call__(
        self,
        session: Session,
        country_code: str,
        observation_date: date,
    ) -> OverlayBundle: ...


def default_inputs_builder(
    session: Session,  # noqa: ARG001 — Protocol compatibility
    country_code: str,
    observation_date: date,
) -> OverlayBundle:
    """MVP default — empty bundle so every overlay reports a structured skip."""
    return OverlayBundle(country_code=country_code, observation_date=observation_date)


# ---------------------------------------------------------------------------
# Bundle assemblers — C2-C5 wire each overlay's inputs from reasonable
# defaults. Live-connector assemblers (FMP / Shiller / Multpl / TE
# sovereign yields / Damodaran scrape / ECB linkers) land in follow-on
# CALs; this sprint orchestrates the compute + persist layer.
# ---------------------------------------------------------------------------


def build_erp_us_bundle(
    *,
    observation_date: date,
    index_level: float,
    trailing_earnings: float,
    forward_earnings_est: float,
    dividend_yield_pct: float,
    cape_ratio: float,
    risk_free_nominal: float,
    risk_free_real: float,
    buyback_yield_pct: float | None = None,
    consensus_growth_5y: float = 0.10,
    retention: float = 0.60,
    roe: float = 0.20,
    risk_free_confidence: float = 0.95,
    upstream_flags: tuple[str, ...] = (),
) -> ERPInput:
    """Assemble an :class:`ERPInput` for US with explicit live-ish values.

    Pass-through to the :class:`sonar.overlays.erp.ERPInput` dataclass
    with sensible Week-3.5 defaults for ``consensus_growth_5y`` /
    ``retention`` / ``roe`` (Damodaran standard table). Callers that
    have a live FMP / Shiller / Multpl assembly override.
    """
    from sonar.overlays.erp import ERPInput  # noqa: PLC0415

    return ERPInput(
        market_index="SPX",
        country_code="US",
        observation_date=observation_date,
        index_level=index_level,
        trailing_earnings=trailing_earnings,
        forward_earnings_est=forward_earnings_est,
        dividend_yield_pct=dividend_yield_pct,
        buyback_yield_pct=buyback_yield_pct,
        cape_ratio=cape_ratio,
        risk_free_nominal=risk_free_nominal,
        risk_free_real=risk_free_real,
        consensus_growth_5y=consensus_growth_5y,
        retention=retention,
        roe=roe,
        risk_free_confidence=risk_free_confidence,
        upstream_flags=upstream_flags,
    )


def build_sov_spread_crp_bundle(
    *,
    country_code: str,
    observation_date: date,
    sov_yield_country_pct: float,
    sov_yield_benchmark_pct: float,
    vol_ratio: float = 1.23,
    vol_ratio_source: str = "damodaran_standard",
    tenor: str = "10Y",
    currency_denomination: str = "EUR",
) -> dict[str, Any]:
    """Build a CRP kwargs dict routed through the SOV_SPREAD method.

    Yields in decimal (e.g. ``0.042`` for 4.2 %). Returns a ``**kwargs``
    dict ready for :func:`sonar.overlays.crp.build_canonical`.
    """
    from sonar.overlays.crp import compute_sov_spread  # noqa: PLC0415

    sov_spread = compute_sov_spread(
        country_code=country_code,
        observation_date=observation_date,
        sov_yield_country_pct=sov_yield_country_pct,
        sov_yield_benchmark_pct=sov_yield_benchmark_pct,
        tenor=tenor,
        currency_denomination=currency_denomination,
        vol_ratio=vol_ratio,
        vol_ratio_source=vol_ratio_source,
    )
    return {
        "country_code": country_code,
        "observation_date": observation_date,
        "sov_spread": sov_spread,
        "currency": currency_denomination,
    }


def build_rating_bundle(
    *,
    country_code: str,
    observation_date: date,
    agency_ratings: list[dict[str, Any]],
    rating_type: str = "FC",
) -> dict[str, Any]:
    """Build a rating-spread kwargs dict from per-agency raw rating inputs.

    Each element of ``agency_ratings`` is a dict with ``agency`` /
    ``rating_raw`` / ``outlook`` / ``watch`` / ``action_date`` keys —
    the assembler runs them through ``apply_modifiers`` to produce the
    :class:`RatingAgencyRaw` rows that ``consolidate`` expects.
    """
    from sonar.overlays.rating_spread import (  # noqa: PLC0415
        RatingAgencyRaw,
        apply_modifiers,
        lookup_base_notch,
    )

    rows: list[RatingAgencyRaw] = []
    for raw in agency_ratings:
        base_notch = lookup_base_notch(raw["agency"], raw["rating_raw"])
        adjusted = apply_modifiers(
            base_notch=base_notch,
            outlook=raw["outlook"],
            watch=raw["watch"],
        )
        rows.append(
            RatingAgencyRaw(
                agency=raw["agency"],
                rating_raw=raw["rating_raw"],
                rating_type=rating_type,  # type: ignore[arg-type]
                base_notch=base_notch,
                notch_adjusted=adjusted,
                outlook=raw["outlook"],
                watch=raw["watch"],
                action_date=raw["action_date"],
            )
        )
    return {
        "rows": rows,
        "country_code": country_code,
        "observation_date": observation_date,
        "rating_type": rating_type,
    }


def build_expected_inflation_bundle(
    *,
    country_code: str,
    observation_date: date,
    nominal_yields: dict[str, float],
    linker_real_yields: dict[str, float] | None = None,
    survey_horizons: dict[str, float] | None = None,
    survey_name: str | None = None,
    survey_release_date: date | None = None,
    bc_target_pct: float | None = 0.02,
) -> dict[str, Any]:
    """Build expected-inflation kwargs dict for :func:`build_canonical`.

    Supplies a BEI row when both nominal + linker yields are provided,
    and/or a SURVEY row when survey horizons are provided. Returns a
    dict directly usable as ``**kwargs``.
    """
    from sonar.overlays.expected_inflation import (  # noqa: PLC0415
        ExpInfBEI,
        ExpInfSurvey,
        compute_bei_from_yields,
    )

    bei: ExpInfBEI | None = None
    if linker_real_yields is not None:
        tenors = compute_bei_from_yields(nominal_yields, linker_real_yields)
        if tenors:
            bei = ExpInfBEI(
                country_code=country_code,
                observation_date=observation_date,
                nominal_yields=dict(nominal_yields),
                linker_real_yields=dict(linker_real_yields),
                bei_tenors=tenors,
                linker_connector="fred",
                nss_fit_id=None,
                confidence=0.85,
                flags=(),
            )

    survey: ExpInfSurvey | None = None
    if survey_horizons and survey_name and survey_release_date:
        survey = ExpInfSurvey(
            country_code=country_code,
            observation_date=observation_date,
            survey_name=survey_name,
            survey_release_date=survey_release_date,
            horizons=dict(survey_horizons),
            interpolated_tenors=dict(survey_horizons),
            confidence=0.75,
            flags=(),
        )

    return {
        "country_code": country_code,
        "observation_date": observation_date,
        "bei": bei,
        "survey": survey,
        "bc_target_pct": bc_target_pct,
    }


class StaticInputsBuilder:
    """Wrap pre-assembled per-country ``OverlayBundle`` objects.

    Test and integration-smoke friendly: construct with a
    ``{country_code: OverlayBundle}`` mapping and the builder dispatches
    on ``country_code`` in its ``__call__``. Unknown countries fall
    back to an empty bundle so the orchestrator routes a structured
    skip.
    """

    def __init__(self, bundles: dict[str, OverlayBundle]) -> None:
        self._bundles = bundles

    def __call__(
        self,
        session: Session,  # noqa: ARG002 — Protocol compatibility
        country_code: str,
        observation_date: date,
    ) -> OverlayBundle:
        hit = self._bundles.get(country_code)
        if hit is not None:
            return hit
        return OverlayBundle(country_code=country_code, observation_date=observation_date)


# ---------------------------------------------------------------------------
# Per-overlay compute helpers — run_one invokes these via asyncio.gather.
# Each returns (result_or_none, skip_reason_or_none) so one overlay's
# InsufficientDataError/ValueError never short-circuits the gather.
# ---------------------------------------------------------------------------


async def _compute_erp(bundle: OverlayBundle) -> tuple[ERPFitResult | None, str | None]:
    if bundle.erp is None:
        return None, "no inputs provided"
    from sonar.overlays.erp import fit_erp_us  # noqa: PLC0415

    try:
        return fit_erp_us(bundle.erp), None
    except InsufficientDataError as exc:
        return None, str(exc)


async def _compute_crp(bundle: OverlayBundle) -> tuple[CRPCanonical | None, str | None]:
    if bundle.crp is None:
        return None, "no inputs provided"
    from sonar.overlays.crp import build_canonical  # noqa: PLC0415

    try:
        return build_canonical(**bundle.crp), None
    except (InsufficientDataError, ValueError) as exc:
        return None, str(exc)


async def _compute_rating(bundle: OverlayBundle) -> tuple[ConsolidatedRating | None, str | None]:
    if bundle.rating is None:
        return None, "no inputs provided"
    from sonar.overlays.rating_spread import consolidate  # noqa: PLC0415

    try:
        return consolidate(**bundle.rating), None
    except (InsufficientDataError, ValueError) as exc:
        return None, str(exc)


async def _compute_expected_inflation(
    bundle: OverlayBundle,
) -> tuple[IndexResult | None, str | None]:
    if bundle.expected_inflation is None:
        return None, "no inputs provided"
    from sonar.overlays.expected_inflation import build_canonical  # noqa: PLC0415

    try:
        canonical = build_canonical(**bundle.expected_inflation)
    except (InsufficientDataError, ValueError) as exc:
        return None, str(exc)
    # Normalise into an IndexResult so the batch persist helper can write
    # it through the generic index_values table (no dedicated overlay
    # table exists yet — shipping one would require a migration, which
    # §3 concurrency forbids for this sprint).
    from sonar.indices.base import IndexResult  # noqa: PLC0415

    tenors = canonical.expected_inflation_tenors
    # raw_value = 10Y tenor if available, else any available tenor, else 0.
    raw_value = tenors.get("10Y") or next(iter(tenors.values()), 0.0)
    return (
        IndexResult(
            index_code="EXPINF_CANONICAL",
            country_code=bundle.country_code,
            date=bundle.observation_date,
            methodology_version="EXPINF_v1.0",
            raw_value=float(raw_value),
            zscore_clamped=0.0,
            value_0_100=50.0,
            confidence=canonical.confidence,
            flags=canonical.flags,
            sub_indicators={
                "expected_inflation_tenors": {k: float(v) for k, v in tenors.items()},
                "source_method_per_tenor": {
                    k: str(v) for k, v in canonical.source_method_per_tenor.items()
                },
                "methods_available": canonical.methods_available,
                "anchor_status": canonical.anchor_status,
            },
        ),
        None,
    )


# ---------------------------------------------------------------------------
# compute_all_overlays + run_one
# ---------------------------------------------------------------------------


async def compute_all_overlays(bundle: OverlayBundle) -> OverlayResults:
    """Run the 4 overlays concurrently and collate into :class:`OverlayResults`."""
    erp_task = _compute_erp(bundle)
    crp_task = _compute_crp(bundle)
    rating_task = _compute_rating(bundle)
    expinf_task = _compute_expected_inflation(bundle)
    (erp_r, erp_s), (crp_r, crp_s), (rat_r, rat_s), (exp_r, exp_s) = await asyncio.gather(
        erp_task, crp_task, rating_task, expinf_task
    )
    skips: dict[str, str] = {}
    if erp_s is not None:
        skips["erp"] = erp_s
    if crp_s is not None:
        skips["crp"] = crp_s
    if rat_s is not None:
        skips["rating"] = rat_s
    if exp_s is not None:
        skips["expected_inflation"] = exp_s
    return OverlayResults(
        country_code=bundle.country_code,
        observation_date=bundle.observation_date,
        erp=erp_r,
        crp=crp_r,
        rating=rat_r,
        expected_inflation=exp_r,
        skips=skips,
    )


@dataclass(frozen=True, slots=True)
class DailyOverlaysOutcome:
    country_code: str
    observation_date: date
    results: OverlayResults
    persisted: dict[str, int]


def run_one(
    session: Session,
    country_code: str,
    observation_date: date,
    *,
    inputs_builder: InputsBuilder | None = None,
    require_nss: bool = True,
) -> DailyOverlaysOutcome:
    """Single ``(country, date)`` pipeline run: precondition → compute → persist.

    ``require_nss=True`` (default) raises :class:`InsufficientDataError`
    when no ``yield_curves_spot`` row exists for the triplet. Callers
    that want to exercise the overlays without a curve (unit tests
    with synthetic bundles) can set it to ``False``.
    """
    if require_nss and not nss_spot_exists(session, country_code, observation_date):
        msg = (
            f"yield_curves_spot missing for country={country_code} "
            f"date={observation_date.isoformat()} — run daily_curves first"
        )
        raise InsufficientDataError(msg)

    builder = inputs_builder or default_inputs_builder
    bundle = builder(session, country_code, observation_date)
    results = asyncio.run(compute_all_overlays(bundle))

    # Commit 6 swaps this for persist_many_overlay_results; C1 default
    # path persists nothing so unit tests stay deterministic.
    persisted: dict[str, int] = {"erp": 0, "crp": 0, "rating": 0, "expected_inflation": 0}
    log.info(
        "daily_overlays.computed",
        country=country_code,
        date=observation_date.isoformat(),
        computed={
            "erp": results.erp is not None,
            "crp": results.crp is not None,
            "rating": results.rating is not None,
            "expected_inflation": results.expected_inflation is not None,
        },
        skips=results.skips,
    )
    return DailyOverlaysOutcome(
        country_code=country_code,
        observation_date=observation_date,
        results=results,
        persisted=persisted,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(
    country: str = typer.Option("", "--country", help="ISO 3166-1 alpha-2 (omit with --all-t1)."),
    target_date: str = typer.Option(..., "--date", help="ISO date (e.g. 2024-12-31)."),
    all_t1: bool = typer.Option(
        False,  # noqa: FBT003
        "--all-t1",
        help="Iterate over all 7 T1 countries (US/DE/PT/IT/ES/FR/NL).",
    ),
) -> None:
    """Run the daily overlays pipeline (skeleton — helpers wire in subsequent commits)."""
    try:
        obs_date = date.fromisoformat(target_date)
    except ValueError:
        typer.echo(f"Invalid --date={target_date!r}; expected ISO YYYY-MM-DD", err=True)
        sys.exit(EXIT_IO)

    targets: list[str] = list(T1_7_COUNTRIES) if all_t1 else [country]
    if not targets or targets == [""]:
        typer.echo("Must pass --country or --all-t1", err=True)
        sys.exit(EXIT_IO)

    session = SessionLocal()
    exit_code = EXIT_OK
    try:
        for c in targets:
            try:
                run_one(session, c, obs_date)
            except InsufficientDataError as exc:
                log.error("daily_overlays.insufficient_data", country=c, error=str(exc))
                exit_code = exit_code or EXIT_INSUFFICIENT_DATA
            except ConvergenceError as exc:
                log.error("daily_overlays.convergence_failed", country=c, error=str(exc))
                exit_code = EXIT_CONVERGENCE
            except DuplicatePersistError as exc:
                log.error("daily_overlays.duplicate", country=c, error=str(exc))
                exit_code = EXIT_DUPLICATE
    finally:
        session.close()
    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    typer.run(main)
