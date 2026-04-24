"""Writers for the ``exp_inflation_*`` tables — Sprint Q.1 first ship.

The exp-inflation schema landed in migration ``004_exp_inflation_schema``
(Week 3) but has carried no writer since — Sprint Q audit (§6.1,
``docs/backlog/audits/sprint-q-expinf-wiring-audit.md``) flagged the
``exp_inflation_survey`` + ``exp_inflation_bei`` tables as dormant.

Persistence pattern: raw-SQL upsert (INSERT … ON CONFLICT DO NOTHING)
on the per-table unique key defined in migration 004. Row-level
idempotence per ADR-0011 Principle 1; duplicate inserts are logged +
skipped so a retry / re-backfill is safe.

Scope shipped:

* ``persist_survey_row`` (Sprint Q.1) — one row per
  ``(country_code, survey_name, date, methodology_version)`` with the
  horizon + interpolated-tenor dicts stored as JSON. ECB SDW SPF EA
  writer.
* ``persist_bei_row`` (Sprint Q.2) — one row per
  ``(country_code, date, methodology_version)`` carrying the BEI
  tenor map as JSON. BoE yield-curves GB writer; extensible to any
  source that publishes a spot-curve BEI (real-linkers BEI, US TIPS
  BEI, EA HICPx swap BEI).

Minimal ORM classes (:class:`~sonar.db.models.ExpInflationSurveyRow`
+ :class:`~sonar.db.models.ExpInflationBeiRow`) register both tables
with :attr:`Base.metadata` so in-memory SQLite test fixtures can
``create_all`` them. The writers use raw SQL (SQLAlchemy Core
``text()``) to keep the surface small + portable to the Phase 2+
Postgres migration (``INSERT OR IGNORE`` → ``ON CONFLICT … DO
NOTHING``).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog
from sqlalchemy import text

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

    from sonar.overlays.expected_inflation import ExpInfSurvey

log = structlog.get_logger()

__all__ = ["persist_bei_row", "persist_survey_row"]


# SQLite + Postgres both support ``INSERT OR IGNORE`` (SQLite) and
# ``ON CONFLICT (...) DO NOTHING`` (Postgres). Starting on SQLite MVP
# (CLAUDE.md §9) so we use the SQLite form; migration to Postgres is a
# mechanical rewrite (``ON CONFLICT (country_code, date, survey_name,
# methodology_version) DO NOTHING``) tracked under
# ``CAL-POSTGRES-MIGRATION`` (Phase 2+).
_INSERT_SURVEY_SQL = text(
    """
    INSERT OR IGNORE INTO exp_inflation_survey (
        exp_inf_id,
        country_code,
        date,
        methodology_version,
        confidence,
        flags,
        survey_name,
        survey_release_date,
        horizons_json,
        interpolated_tenors_json
    ) VALUES (
        :exp_inf_id,
        :country_code,
        :date,
        :methodology_version,
        :confidence,
        :flags,
        :survey_name,
        :survey_release_date,
        :horizons_json,
        :interpolated_tenors_json
    )
    """,
)


def persist_survey_row(
    session: Session,
    survey: ExpInfSurvey,
    *,
    methodology_version: str,
) -> bool:
    """Upsert a single :class:`ExpInfSurvey` row.

    Returns ``True`` if a new row was inserted, ``False`` if the unique
    constraint matched an existing row (idempotent retry / backfill).
    The caller commits.
    """
    flags_csv = ",".join(survey.flags) if survey.flags else None
    params = {
        "exp_inf_id": str(uuid4()),
        "country_code": survey.country_code,
        "date": _as_iso(survey.observation_date),
        "methodology_version": methodology_version,
        "confidence": float(survey.confidence),
        "flags": flags_csv,
        "survey_name": survey.survey_name,
        "survey_release_date": _as_iso(survey.survey_release_date),
        "horizons_json": json.dumps(survey.horizons, sort_keys=True),
        "interpolated_tenors_json": json.dumps(survey.interpolated_tenors, sort_keys=True),
    }
    result = session.execute(_INSERT_SURVEY_SQL, params)
    rowcount = getattr(result, "rowcount", None) or 0
    inserted = rowcount > 0
    # CursorResult must be closed explicitly when we only consume
    # rowcount — leaving it open under pytest-asyncio surfaces as a
    # ``PytestUnraisableExceptionWarning`` when the test's loop tears
    # down with the DB socket still live (flaky on SQLAlchemy Core).
    result.close()
    if inserted:
        log.info(
            "exp_inflation_writers.survey.inserted",
            country=survey.country_code,
            date=params["date"],
            survey_name=survey.survey_name,
            methodology_version=methodology_version,
        )
    else:
        log.debug(
            "exp_inflation_writers.survey.duplicate_skipped",
            country=survey.country_code,
            date=params["date"],
            survey_name=survey.survey_name,
            methodology_version=methodology_version,
        )
    return inserted


def _as_iso(value: date) -> str:
    """SQLite binds dates as text; normalise to ISO ``YYYY-MM-DD``."""
    return value.isoformat()


# ---- BEI (Sprint Q.2) ----

_INSERT_BEI_SQL = text(
    """
    INSERT OR IGNORE INTO exp_inflation_bei (
        exp_inf_id,
        country_code,
        date,
        methodology_version,
        confidence,
        flags,
        nominal_yields_json,
        linker_real_yields_json,
        bei_tenors_json,
        linker_connector,
        nss_fit_id
    ) VALUES (
        :exp_inf_id,
        :country_code,
        :date,
        :methodology_version,
        :confidence,
        :flags,
        :nominal_yields_json,
        :linker_real_yields_json,
        :bei_tenors_json,
        :linker_connector,
        :nss_fit_id
    )
    """,
)


def persist_bei_row(
    session: Session,
    *,
    country_code: str,
    observation_date: date,
    bei_tenors_decimal: dict[str, float],
    linker_connector: str,
    methodology_version: str,
    confidence: float = 0.85,
    flags: tuple[str, ...] = (),
    nominal_yields_decimal: dict[str, float] | None = None,
    linker_real_yields_decimal: dict[str, float] | None = None,
    nss_fit_id: str | None = None,
) -> bool:
    """Upsert a BEI observation into ``exp_inflation_bei``.

    ``bei_tenors_decimal`` carries the breakeven-inflation curve as
    decimals (``0.035`` = 3.5 %). The caller derives the curve either
    by subtracting a real-yield leg from a nominal-yield leg or — for
    sources like BoE that publish a pre-fitted implied inflation spot
    curve — by consuming the spot series directly and leaving the
    input legs empty (``None`` / ``{}``) with the
    ``BEI_FITTED_IMPLIED`` flag stamped.

    Returns ``True`` when a new row was inserted, ``False`` when the
    unique key ``(country_code, date, methodology_version)`` matched
    an existing row (idempotent retry / backfill per ADR-0011 P1).
    """
    if not bei_tenors_decimal:
        msg = (
            f"persist_bei_row: empty bei_tenors_decimal for "
            f"{country_code!r} {observation_date.isoformat()}"
        )
        raise ValueError(msg)
    params = {
        "exp_inf_id": str(uuid4()),
        "country_code": country_code,
        "date": _as_iso(observation_date),
        "methodology_version": methodology_version,
        "confidence": float(confidence),
        "flags": ",".join(flags) if flags else None,
        "nominal_yields_json": json.dumps(
            nominal_yields_decimal if nominal_yields_decimal is not None else {},
            sort_keys=True,
        ),
        "linker_real_yields_json": json.dumps(
            linker_real_yields_decimal if linker_real_yields_decimal is not None else {},
            sort_keys=True,
        ),
        "bei_tenors_json": json.dumps(bei_tenors_decimal, sort_keys=True),
        "linker_connector": linker_connector,
        "nss_fit_id": nss_fit_id,
    }
    result = session.execute(_INSERT_BEI_SQL, params)
    rowcount = getattr(result, "rowcount", None) or 0
    inserted = rowcount > 0
    result.close()
    if inserted:
        log.info(
            "exp_inflation_writers.bei.inserted",
            country=country_code,
            date=params["date"],
            linker_connector=linker_connector,
            methodology_version=methodology_version,
            tenors=sorted(bei_tenors_decimal),
        )
    else:
        log.debug(
            "exp_inflation_writers.bei.duplicate_skipped",
            country=country_code,
            date=params["date"],
            methodology_version=methodology_version,
        )
    return inserted
