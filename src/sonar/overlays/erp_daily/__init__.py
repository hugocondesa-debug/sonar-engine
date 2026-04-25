"""ERP daily overlay (L2) — Sprint 3 namespace + US backfill orchestrator.

Spec: docs/specs/overlays/erp-daily.md @ ``ERP_CANONICAL_v0.1``.

The 4-method compute primitives (DCF, Gordon, EY, CAPE) and canonical
aggregation already live in :mod:`sonar.overlays.erp` and are wired
into the :mod:`sonar.pipelines.daily_overlays` daily flow. Sprint 3
adds the *historical-fill* counterpart: a US 60-business-day window
orchestrator (:mod:`.backfill`) reading inputs from the L1 store +
connectors and emitting atomic 5-sibling rows (DCF + Gordon + EY +
CAPE + canonical) sharing a single ``erp_id`` UUID per
``(market_index, date)``.

This package re-exports the public compute surface from
:mod:`sonar.overlays.erp` so callers wiring through the
``erp_daily`` namespace (CLI ``sonar backfill erp-daily``, future
EA/UK/JP backfills) read a single import root.
"""

from __future__ import annotations

from sonar.overlays.erp import (
    DCF_BOUNDS,
    DIVERGENCE_THRESHOLD_BPS,
    FORWARD_EPS_DIVERGENCE_THRESHOLD,
    G_SUSTAINABLE_CAP,
    GROWTH_HORIZON_YEARS,
    METHODOLOGY_VERSION_CANONICAL,
    METHODOLOGY_VERSION_CAPE,
    METHODOLOGY_VERSION_DCF,
    METHODOLOGY_VERSION_EY,
    METHODOLOGY_VERSION_GORDON,
    MIN_METHODS_FOR_CANONICAL,
    ERPCanonicalResult,
    ERPFitResult,
    ERPInput,
    ERPMethodResult,
    fit_erp_us,
)

__all__ = [
    "DCF_BOUNDS",
    "DIVERGENCE_THRESHOLD_BPS",
    "FORWARD_EPS_DIVERGENCE_THRESHOLD",
    "GROWTH_HORIZON_YEARS",
    "G_SUSTAINABLE_CAP",
    "METHODOLOGY_VERSION_CANONICAL",
    "METHODOLOGY_VERSION_CAPE",
    "METHODOLOGY_VERSION_DCF",
    "METHODOLOGY_VERSION_EY",
    "METHODOLOGY_VERSION_GORDON",
    "MIN_METHODS_FOR_CANONICAL",
    "ERPCanonicalResult",
    "ERPFitResult",
    "ERPInput",
    "ERPMethodResult",
    "fit_erp_us",
]
