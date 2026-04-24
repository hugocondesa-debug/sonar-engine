"""Canonical composition — hierarchy pick + anchor + persistence.

Spec: ``docs/specs/overlays/expected-inflation.md`` §4 step 8 +
§8 ``exp_inflation_canonical`` schema.

Sprint 1 composes the canonical row across all four method legs
shipped so far — BEI (Q.2 GB), SWAP (this sprint), DERIVED (this
sprint, PT only), SURVEY (Q.1 EA + Q.3 JP/CA). Hierarchy per tenor
is :data:`HIERARCHY` (spec §4 Pattern 2): ``BEI > SWAP > DERIVED >
SURVEY`` with minimum-confidence gate ``0.50``.

Per spec §4 step 6, canonical inherits upstream flags from the
source method row(s) picked for each tenor (BEI + DERIVED inherit
from their upstream yield-curve / regional aggregate; SWAP +
SURVEY are fresh from the connector, so they contribute only the
row's own method-level flags). The existing ``expected_inflation``
package behaviour — propagate every source's flag onto the
canonical row — is preserved; the flag set is CSV
lexicographic-sorted per ``conventions/flags.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text

from sonar.overlays.expected_inflation import (
    METHODOLOGY_VERSION_CANONICAL,
    MIN_CONFIDENCE_NOMINAL,
    STANDARD_TENORS,
    anchor_status,
)

if TYPE_CHECKING:
    from datetime import date as date_t

    from sqlalchemy.orm import Session

    from sonar.overlays.expected_inflation import ExpInfBEI, ExpInfSurvey
    from sonar.overlays.expected_inflation.derived import ExpInfDerived
    from sonar.overlays.expected_inflation.swap import ExpInfSwap

log = structlog.get_logger()

HierarchyMethod = Literal["BEI", "SWAP", "DERIVED", "SURVEY"]

# Spec §4 step 8 hierarchy. CONSENSUS is a Phase 2 extension (T3 EMs)
# and not exposed on this sprint.
HIERARCHY: tuple[HierarchyMethod, ...] = ("BEI", "SWAP", "DERIVED", "SURVEY")


__all__ = [
    "HIERARCHY",
    "ExpInfCanonical",
    "HierarchyMethod",
    "build_canonical",
    "persist_canonical_row",
]


@dataclass(frozen=True, slots=True)
class ExpInfCanonical:
    """Canonical per-tenor selection across methods."""

    exp_inf_id: UUID
    country_code: str
    observation_date: date_t
    expected_inflation_tenors: dict[str, float]
    source_method_per_tenor: dict[str, HierarchyMethod]
    methods_available: int
    bc_target_pct: float | None
    anchor_deviation_bps: int | None
    anchor_status: str | None
    bei_vs_survey_divergence_bps: int | None
    confidence: float
    flags: tuple[str, ...] = field(default_factory=tuple)


def _hierarchy_pick(
    tenor: str,
    method_tenors: dict[HierarchyMethod, dict[str, float]],
    confidences: dict[HierarchyMethod, float],
) -> tuple[HierarchyMethod | None, float | None]:
    """Return the first method in :data:`HIERARCHY` that has ``tenor``
    with confidence ≥ ``MIN_CONFIDENCE_NOMINAL``; else ``(None, None)``.
    """
    for method in HIERARCHY:
        rates = method_tenors.get(method)
        if rates is None:
            continue
        if tenor not in rates:
            continue
        if confidences.get(method, 0.0) < MIN_CONFIDENCE_NOMINAL:
            continue
        return method, rates[tenor]
    return None, None


def build_canonical(  # noqa: PLR0912, PLR0915 — canonical composer inherently branch-heavy per spec §4 step 8
    *,
    country_code: str,
    observation_date: date_t,
    bei: ExpInfBEI | None = None,
    swap: ExpInfSwap | None = None,
    derived: ExpInfDerived | None = None,
    survey: ExpInfSurvey | None = None,
    bc_target_pct: float | None = None,
) -> ExpInfCanonical:
    """Compose canonical row per spec §4 step 8.

    Hierarchy picker (spec Pattern 2) runs across each of
    :data:`STANDARD_TENORS` to select the best method-tenor pair. Flags
    propagate from every contributing source onto the canonical row;
    confidence is the tenor-count-weighted mean of selected methods
    (spec §4 step 8), reduced by ``-0.10`` each for
    ``INFLATION_METHOD_DIVERGENCE`` and ``ANCHOR_UNCOMPUTABLE`` per spec
    §6 matrix.
    """
    method_tenors: dict[HierarchyMethod, dict[str, float]] = {}
    confidences: dict[HierarchyMethod, float] = {}
    if bei is not None:
        method_tenors["BEI"] = bei.bei_tenors
        confidences["BEI"] = bei.confidence
    if swap is not None:
        method_tenors["SWAP"] = swap.swap_rates
        confidences["SWAP"] = swap.confidence
    if derived is not None:
        method_tenors["DERIVED"] = derived.derived_tenors
        confidences["DERIVED"] = derived.confidence
    if survey is not None:
        method_tenors["SURVEY"] = survey.interpolated_tenors
        confidences["SURVEY"] = survey.confidence

    expected_tenors: dict[str, float] = {}
    sources: dict[str, HierarchyMethod] = {}
    tenor_count_per_method: dict[HierarchyMethod, int] = dict.fromkeys(method_tenors, 0)

    for tenor in STANDARD_TENORS:
        method, value = _hierarchy_pick(tenor, method_tenors, confidences)
        if method is None or value is None:
            continue
        expected_tenors[tenor] = value
        sources[tenor] = method
        tenor_count_per_method[method] += 1

    flags: list[str] = []

    # Anchor — requires 5y5y + bc_target.
    deviation_bps: int | None = None
    status: str | None = None
    if bc_target_pct is not None and "5y5y" in expected_tenors:
        deviation = expected_tenors["5y5y"] - bc_target_pct
        deviation_bps = round(deviation * 10_000.0)
        status = anchor_status(abs(deviation_bps))
    else:
        flags.append("ANCHOR_UNCOMPUTABLE")

    # Propagate upstream method flags onto the canonical row (spec §4
    # step 6 — inheritance). De-dup whilst preserving first-seen order
    # then sort lexicographically at persistence time.
    seen: set[str] = set(flags)
    for src in (bei, swap, derived, survey):
        if src is None:
            continue
        for src_flag in src.flags:
            if src_flag not in seen:
                seen.add(src_flag)
                flags.append(src_flag)

    # BEI vs SURVEY 10Y divergence (spec §4 step 9).
    bei_vs_survey: int | None = None
    if bei is not None and survey is not None:
        bei_10y = bei.bei_tenors.get("10Y")
        survey_10y = survey.interpolated_tenors.get("10Y")
        if bei_10y is not None and survey_10y is not None:
            diff = abs(bei_10y - survey_10y)
            bei_vs_survey = round(diff * 10_000.0)
            if bei_vs_survey > 100 and "INFLATION_METHOD_DIVERGENCE" not in seen:
                flags.append("INFLATION_METHOD_DIVERGENCE")
                seen.add("INFLATION_METHOD_DIVERGENCE")

    # Spec §4 step 8: confidence_canonical = weighted_mean(method_confidences,
    # weights=tenor_count_per_method). Safe against zero denominators
    # via guard on ``total_weight`` (possible when no method provides
    # any tenor — caller gets 0.0 then).
    total_weight = sum(tenor_count_per_method.values())
    if total_weight > 0:
        weighted = sum(
            confidences[method] * tenor_count_per_method[method] for method in method_tenors
        )
        base_confidence = weighted / total_weight
    else:
        base_confidence = 0.0

    deduction = 0.0
    if "INFLATION_METHOD_DIVERGENCE" in seen:
        deduction += 0.10
    if "ANCHOR_UNCOMPUTABLE" in seen:
        deduction += 0.10
    confidence_canonical = max(0.0, min(1.0, base_confidence - deduction))

    return ExpInfCanonical(
        exp_inf_id=uuid4(),
        country_code=country_code,
        observation_date=observation_date,
        expected_inflation_tenors=expected_tenors,
        source_method_per_tenor=sources,
        methods_available=len(method_tenors),
        bc_target_pct=bc_target_pct,
        anchor_deviation_bps=deviation_bps,
        anchor_status=status,
        bei_vs_survey_divergence_bps=bei_vs_survey,
        confidence=confidence_canonical,
        flags=tuple(flags),
    )


_INSERT_CANONICAL_SQL = text(
    """
    INSERT OR IGNORE INTO exp_inflation_canonical (
        exp_inf_id,
        country_code,
        date,
        methodology_version,
        expected_inflation_tenors_json,
        source_method_per_tenor_json,
        methods_available,
        bc_target_pct,
        anchor_deviation_bps,
        anchor_status,
        bei_vs_survey_divergence_bps,
        confidence,
        flags
    ) VALUES (
        :exp_inf_id,
        :country_code,
        :date,
        :methodology_version,
        :expected_inflation_tenors_json,
        :source_method_per_tenor_json,
        :methods_available,
        :bc_target_pct,
        :anchor_deviation_bps,
        :anchor_status,
        :bei_vs_survey_divergence_bps,
        :confidence,
        :flags
    )
    """,
)


def persist_canonical_row(
    session: Session,
    canonical: ExpInfCanonical,
    *,
    methodology_version: str = METHODOLOGY_VERSION_CANONICAL,
) -> bool:
    """Upsert a single :class:`ExpInfCanonical` row into
    ``exp_inflation_canonical``.

    Returns ``True`` if a new row was inserted, ``False`` if the unique
    key ``(country_code, date, methodology_version)`` matched an
    existing row (idempotent retry / backfill per ADR-0011 P1). Flags
    stored CSV lexicographic-sorted per ``conventions/flags.md``.
    """
    flags_csv = ",".join(sorted(canonical.flags)) if canonical.flags else None
    params = {
        "exp_inf_id": str(canonical.exp_inf_id),
        "country_code": canonical.country_code,
        "date": canonical.observation_date.isoformat(),
        "methodology_version": methodology_version,
        "expected_inflation_tenors_json": json.dumps(
            canonical.expected_inflation_tenors, sort_keys=True
        ),
        "source_method_per_tenor_json": json.dumps(
            canonical.source_method_per_tenor, sort_keys=True
        ),
        "methods_available": int(canonical.methods_available),
        "bc_target_pct": (
            float(canonical.bc_target_pct) if canonical.bc_target_pct is not None else None
        ),
        "anchor_deviation_bps": (
            int(canonical.anchor_deviation_bps)
            if canonical.anchor_deviation_bps is not None
            else None
        ),
        "anchor_status": canonical.anchor_status,
        "bei_vs_survey_divergence_bps": (
            int(canonical.bei_vs_survey_divergence_bps)
            if canonical.bei_vs_survey_divergence_bps is not None
            else None
        ),
        "confidence": float(canonical.confidence),
        "flags": flags_csv,
    }
    result = session.execute(_INSERT_CANONICAL_SQL, params)
    rowcount = getattr(result, "rowcount", None) or 0
    inserted = rowcount > 0
    result.close()
    if inserted:
        log.info(
            "exp_inflation_writers.canonical.inserted",
            country=canonical.country_code,
            date=params["date"],
            methods_available=canonical.methods_available,
            sources=sorted(canonical.source_method_per_tenor.items()),
        )
    else:
        log.debug(
            "exp_inflation_writers.canonical.duplicate_skipped",
            country=canonical.country_code,
            date=params["date"],
            methodology_version=methodology_version,
        )
    return inserted
