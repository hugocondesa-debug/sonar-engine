"""Backfill orchestrator — 10 T1 countries x 60 recent business days.

Composes ``exp_inflation_canonical`` rows for the T1 cohort using the
method rows already shipped by prior sprints (BEI Q.2 GB, SURVEY Q.1
EA + Q.3 JP/CA + area-proxy DE/FR/IT/ES/PT) plus the two method rows
added this sprint (EA SWAP, PT DERIVED). Idempotent per ADR-0011 P1 —
re-runs skip duplicate canonical keys via the ``INSERT OR IGNORE``
persistence contract.

Spec: ``docs/specs/overlays/expected-inflation.md`` §4 step 8.

Sprint 1 synthetic legs (pending live connectors):

* ``EA SWAP`` — built from the latest ``ECB_SPF_HICP`` survey row's
  long-term anchor (``LTE`` horizon) projected flat as a daily tape.
  Flag ``SWAP_PLACEHOLDER_SYNTHETIC`` identifies rows that must be
  recomputed once ECB SDW swap-tape fetch ships (CAL-EXPINF-SWAP-EA).
* ``PT DERIVED`` — :mod:`.derived` fetch against the latest EA SPF
  row, plus :data:`PT_EA_DIFFERENTIAL_PLACEHOLDER_PP`. Flag
  ``CALIBRATION_STALE`` marks rows pending the live
  INE + Eurostat HICP recompute (CAL-PT-HICP-DIFFERENTIAL).

Both synthetic legs propagate their flags through canonical via the
spec §4 step 6 inheritance so downstream consumers can opt-out.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date as date_t, datetime, timedelta
from typing import TYPE_CHECKING

import pandas as pd
import structlog

from sonar.config import settings
from sonar.connectors.fred import FredConnector
from sonar.db.models import ExpInflationBeiRow, ExpInflationSurveyRow
from sonar.indices.monetary.exp_inflation_writers import persist_bei_row
from sonar.overlays.exceptions import DataUnavailableError
from sonar.overlays.expected_inflation import (
    METHODOLOGY_VERSION_BEI,
    ExpInfBEI,
    ExpInfSurvey,
)
from sonar.overlays.expected_inflation.bei import build_us_bei_row
from sonar.overlays.expected_inflation.canonical import (
    build_canonical,
    persist_canonical_row,
)
from sonar.overlays.expected_inflation.derived import (
    PT_EA_DIFFERENTIAL_PLACEHOLDER_PP,
    ExpInfDerived,
    compute_derived_pt,
    persist_derived_row,
)
from sonar.overlays.expected_inflation.swap import (
    ExpInfSwap,
    compute_swap,
    persist_swap_row,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = structlog.get_logger()

__all__ = [
    "BC_TARGETS_PCT",
    "SURVEY_FRESHNESS_MAX_DAYS",
    "T1_COUNTRIES",
    "BackfillResult",
    "UsBeiBackfillResult",
    "backfill_canonical_t1",
    "backfill_us_bei",
]


# Spec §2 + §4 — T1 linker / SURVEY-primary cohort. Ordering is the
# cohort order used in the Tier B verification prompt.
T1_COUNTRIES: tuple[str, ...] = (
    "US",
    "EA",
    "DE",
    "FR",
    "IT",
    "ES",
    "PT",
    "GB",
    "JP",
    "CA",
)

# Spec §4 + config/bc_targets.yaml — Fed/ECB/BoE/BoJ/BoC all operate a
# 2% headline target; the 2026-04 ECB SPF + FRB SEP + BoE MPR + BoJ
# price-stability framework all reference this anchor. EA members
# (DE/FR/IT/ES/PT) inherit the ECB target.
BC_TARGETS_PCT: dict[str, float] = {
    "US": 0.02,
    "EA": 0.02,
    "DE": 0.02,
    "FR": 0.02,
    "IT": 0.02,
    "ES": 0.02,
    "PT": 0.02,
    "GB": 0.02,
    "JP": 0.02,
    "CA": 0.02,
}

# Spec §2 parameters.
SURVEY_FRESHNESS_MAX_DAYS: int = 120


@dataclass(frozen=True, slots=True)
class BackfillResult:
    """Summary of a backfill run — one row per (country, method)."""

    canonical_inserted: int
    canonical_skipped: int
    swap_inserted: int
    derived_inserted: int
    countries_covered: tuple[str, ...]
    dates_covered: tuple[date_t, date_t] | None


def _bei_row_to_dataclass(row: ExpInflationBeiRow) -> ExpInfBEI:
    flags = tuple(row.flags.split(",")) if row.flags else ()
    return ExpInfBEI(
        country_code=row.country_code,
        observation_date=row.date,
        nominal_yields=json.loads(row.nominal_yields_json),
        linker_real_yields=json.loads(row.linker_real_yields_json),
        bei_tenors=json.loads(row.bei_tenors_json),
        linker_connector=row.linker_connector,
        nss_fit_id=None,
        confidence=row.confidence,
        flags=flags,
    )


def _survey_row_to_dataclass(row: ExpInflationSurveyRow) -> ExpInfSurvey:
    flags = tuple(row.flags.split(",")) if row.flags else ()
    return ExpInfSurvey(
        country_code=row.country_code,
        observation_date=row.date,
        survey_name=row.survey_name,
        survey_release_date=row.survey_release_date,
        horizons=json.loads(row.horizons_json),
        interpolated_tenors=json.loads(row.interpolated_tenors_json),
        confidence=row.confidence,
        flags=flags,
    )


def _latest_bei(session: Session, country_code: str, observation_date: date_t) -> ExpInfBEI | None:
    """Latest BEI row for ``(country, date)``.

    Methodology-version filter is intentionally lenient — Sprint Q.2 GB
    BEI shipped under the legacy ``EXPINF_BEI_v1.0`` tag (canonical
    spec target is ``EXP_INF_BEI_v0.1``). Until the GB rows are
    re-written, accept any version and pick the most-recently-inserted
    if duplicates exist.
    """
    row = (
        session.query(ExpInflationBeiRow)
        .filter(
            ExpInflationBeiRow.country_code == country_code,
            ExpInflationBeiRow.date == observation_date,
        )
        .order_by(ExpInflationBeiRow.id.desc())
        .first()
    )
    if row is None:
        return None
    return _bei_row_to_dataclass(row)


def _latest_survey(
    session: Session,
    country_code: str,
    observation_date: date_t,
    *,
    freshness_max_days: int = SURVEY_FRESHNESS_MAX_DAYS,
) -> ExpInfSurvey | None:
    """Most recent SURVEY row on-or-before ``observation_date`` within
    the freshness window. Returns ``None`` if no row exists or stalest
    row exceeds the window.
    """
    cutoff = observation_date - timedelta(days=freshness_max_days)
    row = (
        session.query(ExpInflationSurveyRow)
        .filter(
            ExpInflationSurveyRow.country_code == country_code,
            ExpInflationSurveyRow.date <= observation_date,
            ExpInflationSurveyRow.date >= cutoff,
        )
        .order_by(ExpInflationSurveyRow.date.desc())
        .first()
    )
    if row is None:
        return None
    survey = _survey_row_to_dataclass(row)
    # Carry-forward: override observation_date so the canonical key is
    # per-day, whilst preserving the survey's release / horizon payload.
    return ExpInfSurvey(
        country_code=survey.country_code,
        observation_date=observation_date,
        survey_name=survey.survey_name,
        survey_release_date=survey.survey_release_date,
        horizons=survey.horizons,
        interpolated_tenors=survey.interpolated_tenors,
        confidence=survey.confidence,
        flags=survey.flags,
    )


def _recent_business_days(lookback_bd: int, as_of: date_t | None) -> list[date_t]:
    """Most-recent ``lookback_bd`` business days ending on ``as_of``
    (inclusive; defaults to the most recent weekday on-or-before today).
    """
    end = as_of or datetime.now(UTC).date()
    # pandas bdate_range end → skip weekends. Take ``lookback_bd`` trailing.
    rng = pd.bdate_range(end=pd.Timestamp(end), periods=lookback_bd)
    return [d.date() for d in rng]


def _synthesize_ea_swap(survey: ExpInfSurvey | None, observation_date: date_t) -> ExpInfSwap | None:
    """Sprint 1 placeholder swap tape for EA: project the SPF long-term
    anchor (``LTE`` horizon mapped onto 5Y/10Y/5y5y) as a flat daily
    quote until ECB SDW swap-tape fetch ships.
    """
    if survey is None:
        return None
    tenors = survey.interpolated_tenors
    # Need at least 5Y + 10Y so the compound 5y5y is derivable in
    # :func:`compute_swap`.
    if "5Y" not in tenors or "10Y" not in tenors:
        return None
    swap_rates = {k: tenors[k] for k in ("1Y", "2Y", "5Y", "10Y", "30Y") if k in tenors}
    return compute_swap(
        country_code="EA",
        swap_rates=swap_rates,
        observation_date=observation_date,
        swap_provider="ECB_SDW",
        confidence=0.70,  # placeholder deduction until live ECB SDW fetch.
        flags=("SWAP_PLACEHOLDER_SYNTHETIC",),
    )


def _synthesize_pt_derived(
    ea_survey: ExpInfSurvey | None, observation_date: date_t
) -> ExpInfDerived | None:
    """Sprint 1 DERIVED tape for PT: EA aggregate (SPF interpolated
    tenors) + placeholder PT-EA differential. Flags on the emitted row
    propagate through canonical (spec §4 step 6).
    """
    if ea_survey is None:
        return None
    regional = {
        k: v
        for k, v in ea_survey.interpolated_tenors.items()
        if k in {"1Y", "2Y", "5Y", "10Y", "30Y"}
    }
    if not regional:
        return None
    return compute_derived_pt(
        observation_date=observation_date,
        regional_bei=regional,
        regional_source="EA_AGGREGATE",
        differential_pp=PT_EA_DIFFERENTIAL_PLACEHOLDER_PP,
        upstream_flags=ea_survey.flags,
        is_placeholder_differential=True,
    )


def backfill_canonical_t1(
    session: Session,
    *,
    lookback_bd: int = 60,
    as_of: date_t | None = None,
    countries: tuple[str, ...] = T1_COUNTRIES,
) -> BackfillResult:
    """Run the T1 canonical backfill — one canonical row per available
    ``(country, date)`` pair over the last ``lookback_bd`` business days.

    The orchestrator is idempotent: both the per-method (swap, derived)
    and canonical persistence layers use ``INSERT OR IGNORE`` on the
    spec §8 unique key, so re-runs skip duplicates without error.

    ``EA SWAP`` + ``PT DERIVED`` rows are synthesised from the upstream
    SPF survey for Sprint 1 (flagged ``SWAP_PLACEHOLDER_SYNTHETIC`` /
    ``CALIBRATION_STALE``). Future sprints will swap the synthesis for
    live connector fetches without changing the orchestrator contract.
    """
    dates = _recent_business_days(lookback_bd, as_of)
    if not dates:
        return BackfillResult(0, 0, 0, 0, countries, None)

    canonical_inserted = 0
    canonical_skipped = 0
    swap_inserted = 0
    derived_inserted = 0

    for observation_date in dates:
        # EA survey is the regional aggregate for the Sprint 1 SWAP +
        # DERIVED synthesis paths; cache once per date to avoid a query
        # per (country, date) combination.
        ea_survey = _latest_survey(session, "EA", observation_date)

        for country in countries:
            bei = _latest_bei(session, country, observation_date)
            survey = _latest_survey(session, country, observation_date)

            swap_row = None
            if country == "EA":
                swap_row = _synthesize_ea_swap(ea_survey, observation_date)
                if swap_row is not None and persist_swap_row(session, swap_row):
                    swap_inserted += 1

            derived_row = None
            if country == "PT":
                derived_row = _synthesize_pt_derived(ea_survey, observation_date)
                if derived_row is not None and persist_derived_row(session, derived_row):
                    derived_inserted += 1

            if bei is None and survey is None and swap_row is None and derived_row is None:
                # No method rows for this (country, date) — canonical
                # requires ≥ 1 per spec §6 (InsufficientDataError).
                canonical_skipped += 1
                continue

            canonical = build_canonical(
                country_code=country,
                observation_date=observation_date,
                bei=bei,
                swap=swap_row,
                derived=derived_row,
                survey=survey,
                bc_target_pct=BC_TARGETS_PCT.get(country),
            )
            if not canonical.expected_inflation_tenors:
                # build_canonical returned an empty-tenors row (all
                # methods failed the confidence floor) — do not persist.
                canonical_skipped += 1
                continue

            if persist_canonical_row(session, canonical):
                canonical_inserted += 1
            else:
                canonical_skipped += 1

        # Commit at day granularity so partial failures don't roll back
        # the full backfill (matches the ADR-0011 idempotent-retry
        # guidance — day-level units of work).
        session.commit()

    log.info(
        "exp_inflation.backfill.completed",
        countries=list(countries),
        lookback_bd=lookback_bd,
        canonical_inserted=canonical_inserted,
        canonical_skipped=canonical_skipped,
        swap_inserted=swap_inserted,
        derived_inserted=derived_inserted,
    )

    return BackfillResult(
        canonical_inserted=canonical_inserted,
        canonical_skipped=canonical_skipped,
        swap_inserted=swap_inserted,
        derived_inserted=derived_inserted,
        countries_covered=countries,
        dates_covered=(dates[0], dates[-1]),
    )


@dataclass(frozen=True, slots=True)
class UsBeiBackfillResult:
    """Counts emitted by :func:`backfill_us_bei`."""

    inserted: int
    duplicate: int
    skipped_no_spot: int
    errors: int
    dates_covered: tuple[date_t, date_t] | None


async def backfill_us_bei(
    session: Session,
    *,
    lookback_bd: int = 60,
    as_of: date_t | None = None,
    fred_connector: FredConnector | None = None,
) -> UsBeiBackfillResult:
    """Sprint 1.1 — fetch + persist US BEI rows for the trailing
    ``lookback_bd`` business days ending ``as_of``.

    Per spec §2 hierarchy table the US BEI feeds the canonical 5Y/10Y/
    30Y tenors; once the rows land here :func:`backfill_canonical_t1`
    picks them up via the existing :func:`_latest_bei` reader, no
    orchestrator changes needed.

    Idempotent per ADR-0011 P1 — duplicates skipped via the
    persistence ``INSERT OR IGNORE`` contract. Dates without a
    matching ``yield_curves_spot`` US row are logged + skipped (spec
    §8 mandates the FK).
    """
    dates = _recent_business_days(lookback_bd, as_of)
    if not dates:
        return UsBeiBackfillResult(0, 0, 0, 0, None)

    inserted = 0
    duplicate = 0
    skipped_no_spot = 0
    errors = 0

    owns_connector = fred_connector is None
    if fred_connector is None:
        fred_connector = FredConnector(
            api_key=settings.fred_api_key,
            cache_dir=str(settings.cache_dir / "fred"),
        )

    try:
        for observation_date in dates:
            try:
                bei = await build_us_bei_row(
                    session,
                    observation_date,
                    fred_connector=fred_connector,
                )
            except DataUnavailableError as exc:
                log.warning(
                    "exp_inflation.us_bei.skip",
                    date=observation_date.isoformat(),
                    reason=str(exc),
                )
                skipped_no_spot += 1
                continue
            except Exception:
                log.exception(
                    "exp_inflation.us_bei.error",
                    date=observation_date.isoformat(),
                )
                errors += 1
                continue

            ok = persist_bei_row(
                session,
                country_code=bei.country_code,
                observation_date=bei.observation_date,
                bei_tenors_decimal=bei.bei_tenors,
                linker_connector=bei.linker_connector,
                methodology_version=METHODOLOGY_VERSION_BEI,
                confidence=bei.confidence,
                flags=bei.flags,
                nominal_yields_decimal=bei.nominal_yields,
                linker_real_yields_decimal=bei.linker_real_yields,
                nss_fit_id=str(bei.nss_fit_id) if bei.nss_fit_id else None,
            )
            if ok:
                inserted += 1
            else:
                duplicate += 1
            session.commit()
    finally:
        if owns_connector:
            await fred_connector.aclose()

    log.info(
        "exp_inflation.us_bei.completed",
        lookback_bd=lookback_bd,
        inserted=inserted,
        duplicate=duplicate,
        skipped_no_spot=skipped_no_spot,
        errors=errors,
    )
    return UsBeiBackfillResult(
        inserted=inserted,
        duplicate=duplicate,
        skipped_no_spot=skipped_no_spot,
        errors=errors,
        dates_covered=(dates[0], dates[-1]),
    )
