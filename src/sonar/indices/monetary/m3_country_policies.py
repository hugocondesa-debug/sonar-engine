"""M3 T1 country-policy dispatcher + compute-mode classifier (Sprint O).

Per-country metadata + classifier wiring for the M3 Market Expectations
Anchor index. Mirrors the Sprint F :func:`_classify_m2_compute_mode` and
Sprint J :func:`_classify_m4_compute_mode` observability pattern: emits
``FULL`` / ``DEGRADED`` / ``NOT_IMPLEMENTED`` per ``(country, date)`` so
the daily monetary-indices pipeline can log ``m3_compute_mode`` alongside
its existing M2/M4 counterparts.

M3's compute-mode differs from M2/M4 in that the mode depends on
**upstream data presence** (:table:`yield_curves_forwards` +
:index_code:`EXPINF_CANONICAL` :table:`index_values`) rather than
emit-side flags on the built inputs bundle. The classifier therefore
queries the DB session at evaluation time; M2/M4 classifiers are pure
functions over already-emitted flag tuples.

Sprint O scope (Week 10 Day 3 late): T1 9-country cohort
(US/DE/EA/GB/JP/CA/IT/ES/FR). PT (existing canonical path via EA SPF
fallback, pre-Sprint-O) and NL (blocked on Sprint M curves ship) are
**not** in :data:`M3_T1_COUNTRIES` — they classify as ``NOT_IMPLEMENTED``
until their respective follow-up sprints merge.

Audit cross-ref: ``docs/backlog/audits/sprint-o-m3-exp-inflation-audit.md``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from sonar.db.models import (
    ExpInflationBeiRow,
    ExpInflationSurveyRow,
    IndexValue,
    NSSYieldCurveForwards,
)
from sonar.indices.monetary.db_backed_builder import (
    EXPINF_INDEX_CODE,
    M3_EXPINF_FROM_BEI_FLAG,
    M3_EXPINF_FROM_SURVEY_FLAG,
)
from sonar.indices.monetary.m3_market_expectations import MIN_EXPINF_CONFIDENCE

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session


log = structlog.get_logger()


__all__ = [
    "M3_T1_COUNTRIES",
    "M3_T1_DEGRADED_EXPECTED",
    "M3_TIER_FLAG_TEMPLATE",
    "classify_m3_compute_mode",
    "country_m3_flags",
]


# Sprint O T1 9-country cohort — C2 shipped US/DE/EA/GB/JP/CA; C3
# extends the set with IT/ES/FR (EA periphery members reached by
# Sprint H + I curves backfill). PT stays out (existing canonical path
# pre-dates Sprint O); NL stays out (blocked on Sprint M curves probe).
M3_T1_COUNTRIES: frozenset[str] = frozenset({"US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR"})


# Countries where DEGRADED is the *expected* long-run mode even after
# the upstream EXPINF wiring gap closes (CAL-EXPINF-LIVE-ASSEMBLER-WIRING,
# Week 11 P0) — the linker (BEI) leg is structurally thin or absent, so
# the canonical EA SPF / national-survey fallback lands with a DEGRADED
# confidence penalty. Uplift to FULL requires dedicated national linker
# connectors (CAL-EXPINF-BEI-EA-PERIPHERY) + survey probes
# (CAL-EXPINF-SURVEY-JP-CA). FR is excluded — OATi/OATei depth + EA SPF
# covers the full EXPINF composite once upstream wiring lands.
M3_T1_DEGRADED_EXPECTED: frozenset[str] = frozenset({"JP", "CA", "IT", "ES"})


M3_TIER_FLAG_TEMPLATE: str = "{country}_M3_T1_TIER"


# Per-country sparsity-reason flags — attached alongside the tier flag so
# operators reading journals can tell *why* DEGRADED is structural for a
# given country without cross-referencing the audit doc.
_LINKER_SPARSITY_FLAGS: dict[str, str] = {
    "JP": "JP_M3_BEI_LINKER_THIN_EXPECTED",
    "CA": "CA_M3_BEI_RRB_LIMITED_EXPECTED",
    "IT": "IT_M3_BEI_BTP_EI_SPARSE_EXPECTED",
    "ES": "ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED",
}


def country_m3_flags(country_code: str) -> tuple[str, ...]:
    """Return the T1-tier flag set expected on every M3 emission for the country.

    Always emits ``{COUNTRY}_M3_T1_TIER`` so downstream consumers can key
    on membership. Countries in :data:`M3_T1_DEGRADED_EXPECTED` additionally
    emit a linker-sparsity reason flag (e.g., ``JP_M3_BEI_LINKER_THIN_EXPECTED``
    surfaces JGB linker thin coverage vs the US TIPS baseline).

    Returns an empty tuple for countries outside :data:`M3_T1_COUNTRIES`
    so callers can cheaply guard with ``if flags:`` instead of needing
    a membership check first.
    """
    country = country_code.upper()
    if country not in M3_T1_COUNTRIES:
        return ()
    flags = [M3_TIER_FLAG_TEMPLATE.format(country=country)]
    sparsity = _LINKER_SPARSITY_FLAGS.get(country)
    if sparsity is not None:
        flags.append(sparsity)
    return tuple(flags)


def classify_m3_compute_mode(  # noqa: PLR0911  # guard-style early returns per mode branch
    session: Session,
    country_code: str,
    observation_date: date,
) -> tuple[str, tuple[str, ...]]:
    """Return ``(mode, flags)`` for M3 at ``(country, date)``.

    Mirrors the Sprint F :func:`_classify_m2_compute_mode` / Sprint J
    :func:`_classify_m4_compute_mode` observability contract while
    adapting to M3's upstream-data-driven mode semantics.

    Modes:

    * ``FULL`` — forwards row present in :table:`yield_curves_forwards`,
      EXPINF row present in :table:`index_values` (``index_code =
      'EXPINF_CANONICAL'``) with 5y5y tenor reachable and confidence
      ≥ :data:`MIN_EXPINF_CONFIDENCE`. M3 compute proceeds without
      degradation. Flags include ``{COUNTRY}_M3_T1_TIER`` +
      ``M3_FULL_LIVE``.

    * ``DEGRADED`` — country is in the T1 cohort and forwards are
      present, but EXPINF is missing or sub-threshold. Today all 9 T1
      countries land here until CAL-EXPINF-LIVE-ASSEMBLER-WIRING closes
      (see audit §3). Long-run DEGRADED for :data:`M3_T1_DEGRADED_EXPECTED`
      countries even post-closure. Flags include ``{COUNTRY}_M3_T1_TIER``,
      the country's sparsity-reason flag if any, plus a cause flag
      (``M3_FORWARDS_MISSING`` / ``M3_EXPINF_MISSING`` /
      ``M3_EXPINF_CONFIDENCE_SUBTHRESHOLD``).

    * ``NOT_IMPLEMENTED`` — country outside :data:`M3_T1_COUNTRIES`.
      Covers PT (pre-Sprint-O canonical path kept separate to avoid
      double-classification churn), NL (blocked on Sprint M curves),
      and the 6 Week-11+ sparse T1 probes (AU/NZ/CH/SE/NO/DK). Flags
      empty — no tier membership, nothing useful to attach.

    The session argument is required because M3 mode is a runtime
    property of the DB snapshot, not of the inputs-builder emit flags
    (contrast M2/M4 which can classify from ``tuple[str, ...]`` alone).
    """
    country = country_code.upper()

    if country not in M3_T1_COUNTRIES:
        return "NOT_IMPLEMENTED", ()

    flags: list[str] = list(country_m3_flags(country))

    forwards_row = (
        session.query(NSSYieldCurveForwards)
        .filter(
            NSSYieldCurveForwards.country_code == country,
            NSSYieldCurveForwards.date == observation_date,
        )
        .first()
    )
    if forwards_row is None:
        flags.append("M3_FORWARDS_MISSING")
        return "DEGRADED", tuple(flags)

    expinf_row = (
        session.query(IndexValue)
        .filter(
            IndexValue.index_code == EXPINF_INDEX_CODE,
            IndexValue.country_code == country,
            IndexValue.date == observation_date,
        )
        .order_by(IndexValue.confidence.desc())
        .first()
    )
    if expinf_row is None:
        # Sprint Q.1.1 — survey fallback. The canonical EXPINF IndexValue
        # is absent; consult the ``exp_inflation_survey`` table populated
        # by the Sprint Q.1 ECB SDW SPF writer. A recent high-confidence
        # survey row uplifts the country from DEGRADED to FULL with the
        # survey flags propagated.
        survey_row = (
            session.query(ExpInflationSurveyRow)
            .filter(
                ExpInflationSurveyRow.country_code == country,
                ExpInflationSurveyRow.date <= observation_date,
            )
            .order_by(ExpInflationSurveyRow.date.desc())
            .first()
        )
        if survey_row is not None:
            if survey_row.confidence < MIN_EXPINF_CONFIDENCE:
                flags.append("M3_EXPINF_CONFIDENCE_SUBTHRESHOLD")
                return "DEGRADED", tuple(flags)
            survey_flags = [f for f in (survey_row.flags or "").split(",") if f]
            flags.extend(survey_flags)
            flags.append(M3_EXPINF_FROM_SURVEY_FLAG)
            flags.append("M3_FULL_LIVE")
            return "FULL", tuple(flags)

        # Sprint Q.2 — BEI fallback. Canonical + SPF survey both empty;
        # consult ``exp_inflation_bei`` populated by the BoE yield-curves
        # writer. Mirrors the cascade priority of
        # :func:`build_m3_inputs_from_db`: canonical > survey > BEI. A
        # BEI row ≥ MIN_EXPINF_CONFIDENCE uplifts the country to FULL with
        # ``M3_EXPINF_FROM_BEI`` propagated for observability.
        bei_row = (
            session.query(ExpInflationBeiRow)
            .filter(
                ExpInflationBeiRow.country_code == country,
                ExpInflationBeiRow.date <= observation_date,
            )
            .order_by(ExpInflationBeiRow.date.desc())
            .first()
        )
        if bei_row is None:
            flags.append("M3_EXPINF_MISSING")
            return "DEGRADED", tuple(flags)
        if bei_row.confidence < MIN_EXPINF_CONFIDENCE:
            flags.append("M3_EXPINF_CONFIDENCE_SUBTHRESHOLD")
            return "DEGRADED", tuple(flags)
        bei_flags_csv = [f for f in (bei_row.flags or "").split(",") if f]
        flags.extend(bei_flags_csv)
        flags.append(M3_EXPINF_FROM_BEI_FLAG)
        flags.append("M3_FULL_LIVE")
        return "FULL", tuple(flags)
    if expinf_row.confidence < MIN_EXPINF_CONFIDENCE:
        flags.append("M3_EXPINF_CONFIDENCE_SUBTHRESHOLD")
        return "DEGRADED", tuple(flags)

    flags.append("M3_FULL_LIVE")
    return "FULL", tuple(flags)
