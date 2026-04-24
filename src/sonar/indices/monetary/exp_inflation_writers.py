"""Writers for the ``exp_inflation_*`` tables — Sprint Q.1 first ship.

The exp-inflation schema landed in migration ``004_exp_inflation_schema``
(Week 3) but has carried no writer since — Sprint Q audit (§6.1,
``docs/backlog/audits/sprint-q-expinf-wiring-audit.md``) flagged the
``exp_inflation_survey`` table as dormant. Sprint Q.1 ships the first
writer, driven by the ECB SDW SPF connector extension.

Persistence pattern: raw-SQL upsert (INSERT … ON CONFLICT DO NOTHING)
on the unique key ``(country_code, date, survey_name,
methodology_version)`` defined by migration
``004_exp_inflation_schema.uq_exp_survey_cdsm``. Row-level idempotence
per ADR-0011 Principle 1; duplicate inserts are logged + skipped so
a retry / re-backfill is safe.

Scope explicitly:

* ``persist_survey_observations`` — writes one row per
  ``(country_code, survey_quarter)`` with the horizon dict stored as
  JSON in ``horizons_json`` + ``interpolated_tenors_json``. Sprint Q.1
  consumers only call this for the SPF EA cohort.

A minimal ORM class :class:`~sonar.db.models.ExpInflationSurveyRow`
registers the table with :attr:`Base.metadata` so the in-memory
SQLite test fixtures can create it via ``create_all``. The writer
itself uses raw SQL (SQLAlchemy Core ``text()``) to keep the
surface small + portable to the Phase 2+ Postgres migration
(``INSERT OR IGNORE`` → ``ON CONFLICT DO NOTHING``).
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

__all__ = ["persist_survey_row"]


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
