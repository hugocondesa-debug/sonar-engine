"""NSS real curve writer (L2) — dual-path direct_linker / derived dispatcher.

Spec: ``docs/specs/overlays/nss-curves.md`` §4 step 6 + §8
``yield_curves_real``. Sprint 2 (Week 11) ships the path between the
``RealCurve`` dataclass and the persisted real row.

Two cohorts per spec §4 step 6:

* **Direct linker** ({US, GB, DE, IT, FR, CA, AU}) — fit NSS to inflation-
  linked yields (TIPS / ILGs / OATi / BTP€i / Bonos-i / RRBs / TIBs) and
  evaluate at :data:`sonar.overlays.nss.STANDARD_OUTPUT_TENORS`. Sprint 2
  covers GB and the EA-3 cohort the daily pipeline already wires (the
  underlying linker connectors fill in over Phase 2 — TE returns empty
  today, so derived fallback dominates outside US).
* **Derived** ({PT, JP, ES} + sparse-linker fallback) —
  ``real(tau) = nominal(tau) - E[pi](tau)`` from the canonical
  ``exp_inflation_canonical`` row.

Two public entry points wrap a shared ``_compute_real_curve`` core
(per Hugo's Sprint 2 clarification, dual-pattern):

* :func:`build_real_curve` — in-memory builder. Returns ``RealCurve | None``
  for :func:`sonar.pipelines.daily_curves.run_country` to pack into
  ``NSSFitResult`` and persist atomically alongside spot/zero/forwards
  (spec §4 step 9).
* :func:`build_real_row` — standalone backfill writer. Given an existing
  ``NSSYieldCurveSpot`` row, queries E[π] (and optionally accepts pre-
  fetched linker yields) and returns an unsaved ``NSSYieldCurveReal``
  sharing ``spot_row.fit_id``. Caller commits.

Flag policy:

* Sparse-linker fallback emits ``LINKER_UNAVAILABLE`` (canonical, owned
  by ``overlays/expected-inflation`` per ``conventions/flags.md`` §1.5
  — re-emitted here per the catalog rule that allows non-owner specs
  to reference the same token).
* The brief's proposed ``LINKER_SPARSE`` is not in the canonical catalog
  and would require a frozen-contract bump (CLAUDE.md §4) — out of scope
  for Sprint 2.

Confidence policy (Sprint 2 baseline; recalibrate after 12m of production
data — placeholder per CLAUDE.md §4):

* ``direct_linker`` base = 0.85
* ``derived`` base = 0.75
* ``LINKER_UNAVAILABLE`` caps at 0.70 (per ``flags.md`` §1.5)
* ``HIGH_RMSE`` (Tier 1) deducts 0.20; ``NSS_REDUCED`` caps at 0.75
* Real confidence is bounded above by the parent spot's confidence
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

import numpy as np
import structlog

from sonar.db.models import (
    ExpInflationCanonicalRow,
    NSSYieldCurveReal,
    NSSYieldCurveSpot,
)
from sonar.overlays.exceptions import InsufficientDataError
from sonar.overlays.nss import (
    LINKER_MIN_OBSERVATIONS,
    STANDARD_OUTPUT_TENORS,
    NSSInput,
    NSSParams,
    RealCurve,
    RealCurveMethod,
    SpotCurve,
    _label_to_years,
    _nss_eval,
    _params_as_args,
    fit_nss,
)

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

log = structlog.get_logger()

__all__ = [
    "CONFIDENCE_DERIVED_BASE",
    "CONFIDENCE_DIRECT_LINKER_BASE",
    "DERIVED_COUNTRIES",
    "DIRECT_LINKER_COUNTRIES",
    "LINKER_CONNECTOR_MAP",
    "build_real_curve",
    "build_real_row",
]


# ---------------------------------------------------------------------------
# Country routing (spec §4 step 6)
# ---------------------------------------------------------------------------

# Direct-linker countries with dedicated inflation-linked sovereign curves.
# Spec §4 step 6: {US, UK, DE, IT, FR, CA, AU}. UK ↔ GB (ISO 3166-1 alpha-2 post P2-023).
DIRECT_LINKER_COUNTRIES: Final[frozenset[str]] = frozenset(
    {"US", "GB", "DE", "IT", "FR", "CA", "AU"},
)

# Derived path = real(tau) = nominal(tau) - E[pi](tau). Sprint 2 cohort (PT/JP/ES).
DERIVED_COUNTRIES: Final[frozenset[str]] = frozenset({"PT", "JP", "ES"})

# Audit-trail label for ``yield_curves_real.linker_connector``. Connector
# routing itself lives in ``pipelines.daily_curves._fetch_nominals_linkers``.
LINKER_CONNECTOR_MAP: Final[dict[str, str]] = {
    "US": "fred",
    "GB": "boe_yield_curves",
    "DE": "bundesbank",
    "IT": "te",
    "FR": "te",
    "CA": "te",
    "AU": "te",
}

# Sprint 2 placeholders — recalibrate after 12m of production data
# (CLAUDE.md §4 placeholder rule).
CONFIDENCE_DIRECT_LINKER_BASE: Final[float] = 0.85
CONFIDENCE_DERIVED_BASE: Final[float] = 0.75

_CONFIDENCE_CAP_LINKER_UNAVAILABLE: Final[float] = 0.70
_CONFIDENCE_CAP_NSS_REDUCED: Final[float] = 0.75
_CONFIDENCE_DEDUCT_HIGH_RMSE: Final[float] = 0.20


# ---------------------------------------------------------------------------
# Direct-linker path
# ---------------------------------------------------------------------------


def _fit_linker_real(
    country_code: str,
    observation_date: date,
    linker_yields: dict[str, float],
) -> tuple[RealCurve, list[str]]:
    """Fit NSS to ``linker_yields`` and evaluate at the standard tenor grid.

    Returns ``(real_curve, real_specific_flags)``. ``real_specific_flags``
    propagate the linker fit's NSS_REDUCED / HIGH_RMSE so the real row
    surfaces them independently from the parent nominal spot's flags.
    """
    flags: list[str] = []
    labels = sorted(linker_yields.keys(), key=_label_to_years)
    tenors = np.array([_label_to_years(label) for label in labels], dtype=np.float64)
    yields_dec = np.array([linker_yields[label] for label in labels], dtype=np.float64)

    linker_input = NSSInput(
        tenors_years=tenors,
        yields=yields_dec,
        country_code=country_code,
        observation_date=observation_date,
        curve_input_type="linker_real",
    )
    linker_fit = fit_nss(linker_input)
    if "NSS_REDUCED" in linker_fit.flags:
        flags.append("NSS_REDUCED")
    if "HIGH_RMSE" in linker_fit.flags:
        flags.append("HIGH_RMSE")

    std_years = np.array(
        [_label_to_years(label) for label in STANDARD_OUTPUT_TENORS],
        dtype=np.float64,
    )
    real_decimal = _nss_eval(std_years, *_params_as_args(linker_fit.params))
    real_yields = {
        label: float(r) for label, r in zip(STANDARD_OUTPUT_TENORS, real_decimal, strict=True)
    }
    return (
        RealCurve(
            real_yields=real_yields,
            method="direct_linker",
            linker_connector=LINKER_CONNECTOR_MAP[country_code],
        ),
        flags,
    )


# ---------------------------------------------------------------------------
# Derived path: real(tau) = nominal(tau) - E[pi](tau)
# ---------------------------------------------------------------------------


def _compute_derived(
    nominal_spot: SpotCurve,
    exp_inflation_tenors: dict[str, float],
) -> RealCurve:
    """real(tau) = nominal(tau) - E[pi](tau) for tenors present in both maps.

    Both inputs are decimal per units.md §Yields. Tenors absent from
    either side are silently dropped — the caller decides how to handle
    a missing 10Y / 5Y. An empty intersection raises
    :class:`InsufficientDataError` so the caller skips the real row.
    """
    real_yields: dict[str, float] = {}
    for label in STANDARD_OUTPUT_TENORS:
        nominal = nominal_spot.fitted_yields.get(label)
        if nominal is None:
            continue
        expinf = exp_inflation_tenors.get(label)
        if expinf is None:
            continue
        real_yields[label] = nominal - expinf
    if not real_yields:
        msg = (
            "derived real curve: no tenor overlap between nominal "
            f"({sorted(nominal_spot.fitted_yields)}) and E[π] "
            f"({sorted(exp_inflation_tenors)})"
        )
        raise InsufficientDataError(msg)
    return RealCurve(
        real_yields=real_yields,
        method="derived",
        linker_connector=None,
    )


# ---------------------------------------------------------------------------
# Confidence (Sprint 2 baseline)
# ---------------------------------------------------------------------------


def _real_confidence(
    method: RealCurveMethod,
    flags: list[str],
    spot_confidence: float,
) -> float:
    """Cap-then-deduct, bounded above by ``spot_confidence``.

    Real confidence cannot exceed the parent nominal fit's confidence —
    a degraded spot caps the real downstream regardless of the linker /
    E[π] quality. Method-specific base + flag caps + flag deductions
    follow the same arithmetic as :func:`sonar.overlays.nss._compute_confidence`.
    """
    base = CONFIDENCE_DIRECT_LINKER_BASE if method == "direct_linker" else CONFIDENCE_DERIVED_BASE
    cap = base
    if "LINKER_UNAVAILABLE" in flags:
        cap = min(cap, _CONFIDENCE_CAP_LINKER_UNAVAILABLE)
    if "NSS_REDUCED" in flags:
        cap = min(cap, _CONFIDENCE_CAP_NSS_REDUCED)

    deduction = 0.0
    if "HIGH_RMSE" in flags:
        deduction += _CONFIDENCE_DEDUCT_HIGH_RMSE

    return float(max(0.0, min(spot_confidence, cap - deduction)))


# ---------------------------------------------------------------------------
# Core dispatcher
# ---------------------------------------------------------------------------


def _compute_real_curve(
    country_code: str,
    observation_date: date,
    nominal_spot: SpotCurve,
    linker_yields: dict[str, float] | None,
    exp_inflation_tenors: dict[str, float] | None,
) -> RealCurve | None:
    """Dispatch direct_linker / derived per spec §4 step 6.

    Returns ``None`` when:

    * country is outside the 10-cohort scope, or
    * derived path is required but ``exp_inflation_tenors`` is missing
      (logged at WARNING with a remedy hint so the operator can rerun
      the EXPINF canonical backfill).

    A sparse linker (n_obs < :data:`sonar.overlays.nss.LINKER_MIN_OBSERVATIONS`)
    on a direct-linker country falls through to the derived path with
    ``LINKER_UNAVAILABLE`` flagged, matching the existing
    ``flags.md`` §1.5 semantic for sub-threshold linker coverage.
    """
    country = country_code.upper()
    fallback_flags: list[str] = []

    if country in DIRECT_LINKER_COUNTRIES:
        usable = linker_yields or {}
        if len(usable) >= LINKER_MIN_OBSERVATIONS:
            real, sub_flags = _fit_linker_real(country, observation_date, usable)
            real_flags = tuple(sorted(set(sub_flags)))
            confidence = _real_confidence(
                "direct_linker",
                list(real_flags),
                nominal_spot.confidence,
            )
            return RealCurve(
                real_yields=real.real_yields,
                method=real.method,
                linker_connector=real.linker_connector,
                confidence=confidence,
                flags=real_flags,
            )
        # Sparse linker → fall through to derived path with LINKER_UNAVAILABLE.
        fallback_flags.append("LINKER_UNAVAILABLE")

    if country in DIRECT_LINKER_COUNTRIES or country in DERIVED_COUNTRIES:
        if not exp_inflation_tenors:
            log.warning(
                "nss_real.expinf_missing",
                country=country,
                date=observation_date.isoformat(),
                method="derived",
                remedy=(
                    "EXPINF canonical missing — real row skipped; "
                    "rerun expinf canonical backfill to fill the gap"
                ),
            )
            return None
        real = _compute_derived(nominal_spot, exp_inflation_tenors)
        real_flags = tuple(sorted(set(fallback_flags)))
        confidence = _real_confidence("derived", list(real_flags), nominal_spot.confidence)
        return RealCurve(
            real_yields=real.real_yields,
            method=real.method,
            linker_connector=real.linker_connector,
            confidence=confidence,
            flags=real_flags,
        )

    return None


# ---------------------------------------------------------------------------
# Pattern A — in-memory builder (daily pipeline)
# ---------------------------------------------------------------------------


def build_real_curve(
    country_code: str,
    observation_date: date,
    nominal_spot: SpotCurve,
    linker_yields: dict[str, float] | None = None,
    exp_inflation_tenors: dict[str, float] | None = None,
) -> RealCurve | None:
    """In-memory dispatcher used by ``pipelines.daily_curves.run_country``.

    Replaces the legacy :func:`sonar.overlays.nss.derive_real_curve` direct-
    linker-only path. Returns a fully-populated :class:`RealCurve` (with
    real-row-specific ``confidence`` + ``flags``) ready to be packed into
    :class:`sonar.overlays.nss.NSSFitResult` for atomic 4-sibling persist
    via :func:`sonar.db.persistence.persist_nss_fit_result` (spec §4 step 9).

    Returns ``None`` when the country has no real-curve path or the
    derived fallback's E[π] input is missing.
    """
    return _compute_real_curve(
        country_code=country_code,
        observation_date=observation_date,
        nominal_spot=nominal_spot,
        linker_yields=linker_yields,
        exp_inflation_tenors=exp_inflation_tenors,
    )


# ---------------------------------------------------------------------------
# Pattern B — standalone backfill writer
# ---------------------------------------------------------------------------


def _spot_curve_from_row(row: NSSYieldCurveSpot) -> SpotCurve:
    """Reconstruct a :class:`SpotCurve` from a persisted spot row.

    The persisted fitted_yields_json is the authoritative tenor map; the
    derived-path computation feeds off it without re-running NSS.
    """
    fitted = json.loads(row.fitted_yields_json)
    flags: tuple[str, ...] = tuple(row.flags.split(",")) if row.flags else ()
    return SpotCurve(
        params=NSSParams(
            beta_0=row.beta_0,
            beta_1=row.beta_1,
            beta_2=row.beta_2,
            beta_3=row.beta_3,
            lambda_1=row.lambda_1,
            lambda_2=row.lambda_2,
        ),
        fitted_yields=fitted,
        rmse_bps=row.rmse_bps,
        confidence=row.confidence,
        flags=flags,
        observations_used=row.observations_used,
    )


def _expinf_tenors_for(
    session: Session,
    country_code: str,
    observation_date: date,
) -> dict[str, float] | None:
    """Latest ``exp_inflation_canonical`` tenors for ``(country, date)``.

    Returns ``None`` when no canonical row exists. Methodology version
    is intentionally lenient (Sprint 1 versions exist; future sprints
    will tighten via the methodology_versions.md catalog).
    """
    row = (
        session.query(ExpInflationCanonicalRow)
        .filter(
            ExpInflationCanonicalRow.country_code == country_code,
            ExpInflationCanonicalRow.date == observation_date,
        )
        .order_by(ExpInflationCanonicalRow.id.desc())
        .first()
    )
    if row is None:
        return None
    payload = json.loads(row.expected_inflation_tenors_json)
    return {k: float(v) for k, v in payload.items()}


def build_real_row(
    session: Session,
    country_code: str,
    observation_date: date,
    spot_row: NSSYieldCurveSpot,
    *,
    linker_yields: dict[str, float] | None = None,
) -> NSSYieldCurveReal | None:
    """Standalone real-row writer for backfill use cases (spec §8 FK).

    Reuses an existing ``yield_curves_spot`` row's ``fit_id`` so the
    real row joins the spot via the ``ON DELETE CASCADE`` FK. The
    function does not persist — caller invokes ``session.add`` + commit
    so a backfill orchestrator can batch by date / country and isolate
    failures at its preferred granularity.

    ``linker_yields`` is the optional direct-linker payload (callers
    that already fetched it pass through to skip a re-fetch). Without
    it, a direct-linker country degrades to derived if E[π] is available
    (spec §6 sparse fallback), or returns ``None`` otherwise.

    Inherits upstream ``spot_row.flags`` into the real row (additive,
    lexicographic per ``conventions/flags.md`` §"Storage").
    """
    nominal_spot = _spot_curve_from_row(spot_row)
    expinf = _expinf_tenors_for(session, country_code.upper(), observation_date)
    real = _compute_real_curve(
        country_code=country_code,
        observation_date=observation_date,
        nominal_spot=nominal_spot,
        linker_yields=linker_yields,
        exp_inflation_tenors=expinf,
    )
    if real is None:
        return None

    inherited = tuple(spot_row.flags.split(",")) if spot_row.flags else ()
    merged = tuple(sorted(set(inherited) | set(real.flags)))
    flags_csv = ",".join(merged) if merged else None

    confidence = real.confidence if real.confidence is not None else spot_row.confidence

    return NSSYieldCurveReal(
        country_code=country_code.upper(),
        date=observation_date,
        methodology_version=spot_row.methodology_version,
        fit_id=spot_row.fit_id,
        real_yields_json=json.dumps(real.real_yields),
        method=real.method,
        linker_connector=real.linker_connector,
        confidence=confidence,
        flags=flags_csv,
    )
