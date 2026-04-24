"""DERIVED method — synthesised expected inflation via regional + diff.

Spec: ``docs/specs/overlays/expected-inflation.md`` §4 DERIVED formula
for Portugal (+ other periphery sem linker próprio). Sprint 1 scope:
Portugal only; Spain periphery deferred.

Formula (spec §4)::

    E[π_PT(τ)] = E[π_EA(τ)] + diff_pt_ea_5y_rolling
    diff_pt_ea_5y_rolling = mean( pt_hicp_yoy - ea_hicp_yoy, last 60 monthly obs )

Phase 1 simplification (spec §4 Portugal path note): the differential
is applied flat across tenors (1Y = 30Y same delta); per-tenor
differential decomposition deferred to Phase 2 (CAL-042). Short-dated
DERIVED tenors therefore carry ``DIFFERENTIAL_TENOR_PROXY`` so
canonical consumers can trace the proxy origin.

Sprint 1 uses a hard-coded ``PT_EA_DIFFERENTIAL_PLACEHOLDER_PP`` (≈ 18 bps
per spec §7 ``pt_differential_recompute`` fixture); live INE + Eurostat
HICP recompute is CAL-PT-HICP-DIFFERENTIAL (pending). Rows emitted with
the placeholder carry ``CALIBRATION_STALE`` + ``INE_MIRROR_EUROSTAT`` +
``PROXY_APPLIED`` per spec §6 edge cases matrix.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date as date_t, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog
from sqlalchemy import text

from sonar.overlays.expected_inflation import compute_5y5y

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = structlog.get_logger()

__all__ = [
    "DIFFERENTIAL_WINDOW_YEARS",
    "METHODOLOGY_VERSION_DERIVED",
    "PT_EA_DIFFERENTIAL_PLACEHOLDER_PP",
    "ExpInfDerived",
    "compute_derived_pt",
    "persist_derived_row",
]

METHODOLOGY_VERSION_DERIVED: str = "EXP_INF_DERIVED_v0.1"

# Spec §2 parameters.
DIFFERENTIAL_WINDOW_YEARS: int = 5

# Sprint 1 placeholder — recalibrate after live INE + Eurostat HICP
# recompute is wired (CAL-PT-HICP-DIFFERENTIAL). Value ≈ spec §7
# ``pt_differential_recompute`` fixture target (0.0018 = 18 bps).
# Flagged ``CALIBRATION_STALE`` + ``INE_MIRROR_EUROSTAT`` +
# ``PROXY_APPLIED`` on every emit.
PT_EA_DIFFERENTIAL_PLACEHOLDER_PP: float = 0.0018


@dataclass(frozen=True, slots=True)
class ExpInfDerived:
    """DERIVED method row — regional aggregate + country differential."""

    country_code: str
    observation_date: date_t
    regional_bei: dict[str, float]
    regional_source: str
    differential_pp: float
    differential_window_years: int
    differential_computed_at: datetime
    derived_tenors: dict[str, float]
    confidence: float
    flags: tuple[str, ...]


def compute_derived_pt(
    *,
    observation_date: date_t,
    regional_bei: dict[str, float],
    regional_source: str = "EA_AGGREGATE",
    differential_pp: float = PT_EA_DIFFERENTIAL_PLACEHOLDER_PP,
    differential_window_years: int = DIFFERENTIAL_WINDOW_YEARS,
    differential_computed_at: datetime | None = None,
    upstream_flags: tuple[str, ...] = (),
    is_placeholder_differential: bool = True,
) -> ExpInfDerived:
    """Build :class:`ExpInfDerived` for Portugal via EA aggregate + diff.

    Applies the flat differential across every regional tenor (spec §4
    Portugal path note — per-tenor decomposition is Phase 2). Adds
    compounded ``5y5y`` when ``5Y`` + ``10Y`` derived tenors are both
    present. Upstream flags from the EA aggregate row propagate through
    (spec §4 step 6 — DERIVED inherits EA aggregate BEI flags).

    Emits on every row:

    * ``DIFFERENTIAL_TENOR_PROXY`` — flat-tenor differential per spec
      §6. Downstream consumers use this to scope the Phase 2
      per-tenor CAL-042 migration.

    Emits on every placeholder row (Sprint 1 default):

    * ``CALIBRATION_STALE`` — differential is a hard-coded constant,
      not live recompute (spec §6 — cache age > refresh_months).
    * ``INE_MIRROR_EUROSTAT`` — INE endpoint broken D2 CAL-022; PT
      HICP forwarded via Eurostat mirror.
    * ``PROXY_APPLIED`` — conventions/proxies.md companion flag.
    """
    if not regional_bei:
        msg = f"compute_derived_pt: empty regional_bei for {observation_date.isoformat()}"
        raise ValueError(msg)

    derived_tenors: dict[str, float] = {
        tenor: value + differential_pp for tenor, value in regional_bei.items()
    }
    if "5Y" in derived_tenors and "10Y" in derived_tenors and "5y5y" not in derived_tenors:
        derived_tenors["5y5y"] = compute_5y5y(derived_tenors["5Y"], derived_tenors["10Y"])

    flags: list[str] = []
    flags.extend(upstream_flags)
    flags.append("DIFFERENTIAL_TENOR_PROXY")
    if is_placeholder_differential:
        flags.extend(("CALIBRATION_STALE", "INE_MIRROR_EUROSTAT", "PROXY_APPLIED"))

    # De-duplicate whilst preserving first occurrence (upstream order).
    seen: set[str] = set()
    deduped: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            deduped.append(f)

    # Spec §6: PT-EA differential placeholder drops confidence -0.15;
    # DIFFERENTIAL_TENOR_PROXY -0.10 on the DERIVED row (canonical then
    # inherits). Combined deduction saturates at 0.70 baseline to keep
    # the row ≥ 0.50 min-confidence floor for canonical selection.
    confidence = 1.0
    if is_placeholder_differential:
        confidence -= 0.15
    confidence -= 0.10
    confidence = max(0.50, round(confidence, 4))

    return ExpInfDerived(
        country_code="PT",
        observation_date=observation_date,
        regional_bei=dict(regional_bei),
        regional_source=regional_source,
        differential_pp=differential_pp,
        differential_window_years=differential_window_years,
        differential_computed_at=(
            differential_computed_at or datetime.now(UTC).replace(tzinfo=None)
        ),
        derived_tenors=derived_tenors,
        confidence=confidence,
        flags=tuple(deduped),
    )


_INSERT_DERIVED_SQL = text(
    """
    INSERT OR IGNORE INTO exp_inflation_derived (
        exp_inf_id,
        country_code,
        date,
        methodology_version,
        confidence,
        flags,
        regional_bei_json,
        regional_source,
        differential_pp,
        differential_window_years,
        differential_computed_at,
        derived_tenors_json
    ) VALUES (
        :exp_inf_id,
        :country_code,
        :date,
        :methodology_version,
        :confidence,
        :flags,
        :regional_bei_json,
        :regional_source,
        :differential_pp,
        :differential_window_years,
        :differential_computed_at,
        :derived_tenors_json
    )
    """,
)


def persist_derived_row(
    session: Session,
    derived: ExpInfDerived,
    *,
    methodology_version: str = METHODOLOGY_VERSION_DERIVED,
) -> bool:
    """Upsert a single :class:`ExpInfDerived` row into ``exp_inflation_derived``.

    Returns ``True`` if a new row was inserted, ``False`` if the unique
    key ``(country_code, date, methodology_version)`` matched an
    existing row (idempotent retry / backfill per ADR-0011 P1). Flags
    stored CSV lexicographic-sorted per ``conventions/flags.md``.
    """
    flags_csv = ",".join(sorted(derived.flags)) if derived.flags else None
    params = {
        "exp_inf_id": str(uuid4()),
        "country_code": derived.country_code,
        "date": derived.observation_date.isoformat(),
        "methodology_version": methodology_version,
        "confidence": float(derived.confidence),
        "flags": flags_csv,
        "regional_bei_json": json.dumps(derived.regional_bei, sort_keys=True),
        "regional_source": derived.regional_source,
        "differential_pp": float(derived.differential_pp),
        "differential_window_years": int(derived.differential_window_years),
        "differential_computed_at": derived.differential_computed_at.isoformat(),
        "derived_tenors_json": json.dumps(derived.derived_tenors, sort_keys=True),
    }
    result = session.execute(_INSERT_DERIVED_SQL, params)
    rowcount = getattr(result, "rowcount", None) or 0
    inserted = rowcount > 0
    result.close()
    if inserted:
        log.info(
            "exp_inflation_writers.derived.inserted",
            country=derived.country_code,
            date=params["date"],
            regional_source=derived.regional_source,
            differential_pp=derived.differential_pp,
            tenors=sorted(derived.derived_tenors),
        )
    else:
        log.debug(
            "exp_inflation_writers.derived.duplicate_skipped",
            country=derived.country_code,
            date=params["date"],
            methodology_version=methodology_version,
        )
    return inserted
