"""DB-backed :class:`M3Inputs` reader (CAL-108 part 2).

Reads persisted NSS forwards + expected-inflation canonical rows
(stored via the Sprint C ``daily_overlays`` pipeline under
``IndexValue(index_code='EXPINF_CANONICAL')``) to build :class:`M3Inputs`
for the M3 Market Expectations Anchor index without any L0 connector
call. Central-bank inflation target comes from the YAML config shipped
in Week 6 Sprint 1b (``sonar.indices.monetary._config``).

Mirrors :class:`sonar.indices.economic.db_backed_builder.EconomicDbBackedInputsBuilder`
structure so pipelines can hold one class per domain.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import structlog

from sonar.db.models import ExpInflationSurveyRow, IndexValue, NSSYieldCurveForwards
from sonar.indices.monetary._config import load_bc_targets, load_country_to_target
from sonar.indices.monetary.m3_market_expectations import M3Inputs

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


log = structlog.get_logger()


__all__ = [
    "M3_EXPINF_FROM_SURVEY_FLAG",
    "MonetaryDbBackedInputsBuilder",
    "build_m3_inputs_from_db",
]


EXPINF_INDEX_CODE: str = "EXPINF_CANONICAL"
DEFAULT_HISTORY_DAYS: int = 365 * 5  # 5Y rolling window

# Sprint Q.1.1 — flag appended when survey-table fallback serves the
# EXPINF leg because the EXPINF_CANONICAL IndexValue row is missing for
# ``(country, date)``. Consumers of ``expinf_flags`` can key on it to
# distinguish the canonical vs survey-fallback provenance.
M3_EXPINF_FROM_SURVEY_FLAG: str = "M3_EXPINF_FROM_SURVEY"


class MonetaryDbBackedInputsBuilder:
    """Assembles monetary sub-index inputs from persisted overlay rows.

    Held by :mod:`sonar.pipelines.daily_monetary_indices` when the CLI
    flag ``--backend=db`` is set. Single method for now
    (:meth:`build_m3_inputs`); M1 + M2 + M4 stay on the live connector
    path shipped in Sprint 2b.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def build_m3_inputs(
        self,
        country_code: str,
        observation_date: date,
        *,
        history_days: int = DEFAULT_HISTORY_DAYS,
    ) -> M3Inputs | None:
        """Return :class:`M3Inputs` for ``(country, date)`` or ``None`` on miss."""
        return build_m3_inputs_from_db(
            self.session, country_code, observation_date, history_days=history_days
        )


def _parse_json_dict(raw: str) -> dict[str, Any]:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        msg = f"expected dict JSON payload, got {type(parsed).__name__}"
        raise ValueError(msg)
    return parsed


def _decimal_to_bps(value: float) -> float:
    return value * 10_000.0


def _resolve_bc_target_pct(country_code: str) -> float | None:
    """Return the central-bank inflation target for the country as decimal."""
    try:
        mapping = load_country_to_target()
        cb_name = mapping.get(country_code)
        if cb_name is None:
            return None
        targets = load_bc_targets()
        return float(targets[cb_name])
    except (KeyError, ValueError, FileNotFoundError):
        return None


def _query_expinf(session: Session, country_code: str, observation_date: date) -> IndexValue | None:
    return (
        session.query(IndexValue)
        .filter(
            IndexValue.index_code == EXPINF_INDEX_CODE,
            IndexValue.country_code == country_code,
            IndexValue.date == observation_date,
        )
        .order_by(IndexValue.confidence.desc())
        .first()
    )


def _query_survey(
    session: Session,
    country_code: str,
    observation_date: date,
) -> ExpInflationSurveyRow | None:
    """Return most recent survey row on-or-before ``observation_date``.

    Sprint Q.1.1 fallback path — reads ``exp_inflation_survey`` populated
    by the Sprint Q.1 ECB SDW SPF writer. Ordered by ``date desc`` so a
    sparse survey schedule (quarterly SPF releases) still serves a
    recent observation for the target date.
    """
    return (
        session.query(ExpInflationSurveyRow)
        .filter(
            ExpInflationSurveyRow.country_code == country_code,
            ExpInflationSurveyRow.date <= observation_date,
        )
        .order_by(ExpInflationSurveyRow.date.desc())
        .first()
    )


def _survey_tenors_bps(row: ExpInflationSurveyRow) -> dict[str, float]:
    """Parse ``interpolated_tenors_json`` → tenor→bps map.

    Mirrors :func:`_expinf_tenors_bps` but for the survey schema where
    the tenor dict is stored directly (no nested
    ``expected_inflation_tenors`` key). Returns ``{}`` on malformed JSON
    so the caller treats the row as unusable and falls through to the
    final ``None`` return.
    """
    if not row.interpolated_tenors_json:
        return {}
    try:
        raw = _parse_json_dict(row.interpolated_tenors_json)
    except (ValueError, json.JSONDecodeError):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = _decimal_to_bps(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _expinf_tenors_bps(row: IndexValue) -> dict[str, float]:
    """Parse EXPINF IndexValue ``sub_indicators_json`` → tenor→bps map."""
    if not row.sub_indicators_json:
        return {}
    try:
        sub = _parse_json_dict(row.sub_indicators_json)
    except (ValueError, json.JSONDecodeError):
        return {}
    tenors_raw = sub.get("expected_inflation_tenors")
    if not isinstance(tenors_raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in tenors_raw.items():
        try:
            out[str(k)] = _decimal_to_bps(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _expinf_method_tenors_bps(row: IndexValue, key: str) -> dict[str, float]:
    """Parse a per-method tenor slice (CAL-113 split) → tenor→bps map.

    Returns ``{}`` when the key is absent (pre-Sprint-M rows) so the
    caller falls back to its legacy unified-tenor path.
    """
    if not row.sub_indicators_json:
        return {}
    try:
        sub = _parse_json_dict(row.sub_indicators_json)
    except (ValueError, json.JSONDecodeError):
        return {}
    tenors_raw = sub.get(key)
    if not isinstance(tenors_raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in tenors_raw.items():
        try:
            out[str(k)] = _decimal_to_bps(float(v))
        except (TypeError, ValueError):
            continue
    return out


def build_m3_inputs_from_db(  # noqa: PLR0911  # guard-style early returns per validation step
    session: Session,
    country_code: str,
    observation_date: date,
    *,
    history_days: int = DEFAULT_HISTORY_DAYS,
) -> M3Inputs | None:
    """Assemble :class:`M3Inputs` from persisted forwards + EXPINF rows.

    Required inputs:

    - ``nominal_5y5y_bps`` from ``yield_curves_forwards.forwards_json``
      key ``"5y5y"`` — mandatory; returns ``None`` on miss.
    - ``breakeven_5y5y_bps`` from the EXPINF IndexValue
      ``sub_indicators_json['expected_inflation_tenors']['5y5y']`` —
      mandatory; returns ``None`` on miss.

    Optional / soft inputs:

    - ``bc_target_bps`` resolved via
      :mod:`sonar.indices.monetary._config`; absent countries get
      ``None`` + ``NO_TARGET`` flag.
    - ``bei_10y_bps`` + ``survey_10y_bps`` from the EXPINF sub-indicator
      tenors when the ``10Y`` key is present (SURVEY only emits
      ``survey_10y_bps``, BEI only ``bei_10y_bps``; this builder does
      best-effort by populating both with the canonical 10Y tenor
      value when source_method_per_tenor is unclear).
    - History series ``nominal_5y5y_history_bps`` +
      ``anchor_deviation_abs_history_bps`` are reconstructed from the
      trailing ``history_days`` window of forwards + EXPINF rows.
    """
    forwards_row = (
        session.query(NSSYieldCurveForwards)
        .filter(
            NSSYieldCurveForwards.country_code == country_code,
            NSSYieldCurveForwards.date == observation_date,
        )
        .first()
    )
    if forwards_row is None:
        log.warning(
            "m3_db_backed.forwards_missing",
            country=country_code,
            date=observation_date.isoformat(),
        )
        return None

    try:
        forwards = _parse_json_dict(forwards_row.forwards_json)
    except (ValueError, json.JSONDecodeError) as exc:
        log.error(
            "m3_db_backed.forwards_parse_error",
            country=country_code,
            date=observation_date.isoformat(),
            error=str(exc),
        )
        return None

    nominal_5y5y = forwards.get("5y5y")
    if nominal_5y5y is None:
        log.warning(
            "m3_db_backed.forwards_tenor_missing",
            country=country_code,
            date=observation_date.isoformat(),
        )
        return None
    nominal_5y5y_bps = _decimal_to_bps(float(nominal_5y5y))

    expinf_row = _query_expinf(session, country_code, observation_date)
    if expinf_row is not None:
        tenors_bps = _expinf_tenors_bps(expinf_row)
        breakeven_5y5y_bps = tenors_bps.get("5y5y")
        if breakeven_5y5y_bps is None:
            log.warning(
                "m3_db_backed.expinf_5y5y_missing",
                country=country_code,
                date=observation_date.isoformat(),
                have_tenors=sorted(tenors_bps),
            )
            return None

        expinf_flags: tuple[str, ...] = (
            tuple(expinf_row.flags.split(",")) if expinf_row.flags else ()
        )
        expinf_confidence: float = expinf_row.confidence
        # CAL-113 (Sprint M): if the EXPINF row carries per-method tenor
        # splits, distinguish bei_10y from survey_10y; otherwise fall
        # back to the legacy behaviour (populate bei only from unified
        # tenors + leave survey None so the compute module emits
        # BEI_SURVEY_DIVERGENCE_UNAVAILABLE).
        bei_tenors_bps = _expinf_method_tenors_bps(expinf_row, "bei_tenors")
        survey_tenors_bps = _expinf_method_tenors_bps(expinf_row, "survey_tenors")
        if bei_tenors_bps or survey_tenors_bps:
            bei_10y_bps: float | None = bei_tenors_bps.get("10Y")
            survey_10y_bps: float | None = survey_tenors_bps.get("10Y")
        else:
            bei_10y_bps = tenors_bps.get("10Y")
            survey_10y_bps = None
    else:
        # Sprint Q.1.1 — survey fallback. EXPINF canonical IndexValue
        # row is missing for ``(country, date)``; try the SPF survey
        # table populated by Sprint Q.1. Flags from the survey row
        # (``SPF_LT_AS_ANCHOR``, optionally ``SPF_AREA_PROXY``) are
        # propagated verbatim, plus ``M3_EXPINF_FROM_SURVEY`` so
        # downstream consumers can tell provenance apart.
        survey_row = _query_survey(session, country_code, observation_date)
        if survey_row is None:
            log.warning(
                "m3_db_backed.expinf_missing",
                country=country_code,
                date=observation_date.isoformat(),
            )
            return None

        survey_tenors_all_bps = _survey_tenors_bps(survey_row)
        breakeven_5y5y_bps = survey_tenors_all_bps.get("5y5y")
        if breakeven_5y5y_bps is None:
            log.warning(
                "m3_db_backed.survey_5y5y_missing",
                country=country_code,
                date=observation_date.isoformat(),
                have_tenors=sorted(survey_tenors_all_bps),
            )
            return None

        log.info(
            "m3_db_backed.survey_fallback",
            country=country_code,
            date=observation_date.isoformat(),
            survey_date=survey_row.date.isoformat(),
            survey_name=survey_row.survey_name,
        )

        survey_flags = (
            tuple(f for f in survey_row.flags.split(",") if f) if survey_row.flags else ()
        )
        expinf_flags = (*survey_flags, M3_EXPINF_FROM_SURVEY_FLAG)
        expinf_confidence = survey_row.confidence
        # Survey path exposes only the survey leg (no BEI) — populate
        # ``survey_10y_bps`` from the 10Y tenor when present, leave
        # ``bei_10y_bps`` None so M3 compute still emits the
        # BEI_SURVEY_DIVERGENCE_UNAVAILABLE flag.
        bei_10y_bps = None
        survey_10y_bps = survey_tenors_all_bps.get("10Y")

    bc_target_decimal = _resolve_bc_target_pct(country_code)
    bc_target_bps = _decimal_to_bps(bc_target_decimal) if bc_target_decimal is not None else None

    start = observation_date - timedelta(days=history_days)
    nominal_hist, anchor_dev_abs_hist = _load_histories(
        session,
        country_code,
        start=start,
        end=observation_date,
        bc_target_bps=bc_target_bps,
    )

    return M3Inputs(
        country_code=country_code,
        observation_date=observation_date,
        nominal_5y5y_bps=nominal_5y5y_bps,
        breakeven_5y5y_bps=breakeven_5y5y_bps,
        bc_target_bps=bc_target_bps,
        bei_10y_bps=bei_10y_bps,
        survey_10y_bps=survey_10y_bps,
        nominal_5y5y_history_bps=tuple(nominal_hist),
        anchor_deviation_abs_history_bps=tuple(anchor_dev_abs_hist),
        bei_survey_div_abs_history_bps=None,
        expinf_confidence=expinf_confidence,
        expinf_flags=expinf_flags,
    )


def _latest_survey_on_or_before(
    survey_rows: list[ExpInflationSurveyRow],
    target_date: date,
) -> ExpInflationSurveyRow | None:
    """Return the latest survey row with ``date <= target_date``.

    Precondition: ``survey_rows`` sorted ascending by ``date``. Linear
    scan with early break — acceptable for the sparse quarterly SPF
    release cadence (≤20 rows per 5Y window vs ~1250 daily forwards).
    """
    matched: ExpInflationSurveyRow | None = None
    for row in survey_rows:
        if row.date <= target_date:
            matched = row
        else:
            break
    return matched


def _load_histories(
    session: Session,
    country_code: str,
    *,
    start: date,
    end: date,
    bc_target_bps: float | None,
) -> tuple[list[float], list[float]]:
    """Return ``(nominal_5y5y_history_bps, anchor_deviation_abs_history_bps)``.

    Both series iterate the intersection of persisted forwards rows
    and EXPINF IndexValue rows over the window. Anchor deviation is
    ``|breakeven_5y5y_bps - bc_target_bps|``; when no target is
    available the list stays empty so downstream compute flags
    ``ANCHOR_UNCOMPUTABLE`` rather than producing a degenerate z-score.

    Sprint Q.1.2 — survey fallback: when the canonical
    ``IndexValue(EXPINF_CANONICAL)`` table is empty for the
    ``(country, window)`` (EA cohort case), fall back to the
    ``exp_inflation_survey`` table populated by the Sprint Q.1 SPF
    writer. Each forwards date is paired with the latest survey row
    on-or-before it (forward-fill against the sparse quarterly
    release cadence). Canonical path takes priority whenever at least
    one canonical row is present — US and other canonical-served
    countries remain bit-identical to the pre-Q.1.2 behaviour.
    """
    forwards = (
        session.query(NSSYieldCurveForwards)
        .filter(
            NSSYieldCurveForwards.country_code == country_code,
            NSSYieldCurveForwards.date >= start,
            NSSYieldCurveForwards.date <= end,
        )
        .order_by(NSSYieldCurveForwards.date.asc())
        .all()
    )
    expinf_rows = (
        session.query(IndexValue)
        .filter(
            IndexValue.index_code == EXPINF_INDEX_CODE,
            IndexValue.country_code == country_code,
            IndexValue.date >= start,
            IndexValue.date <= end,
        )
        .order_by(IndexValue.date.asc())
        .all()
    )
    expinf_by_date = {row.date: row for row in expinf_rows}

    survey_rows: list[ExpInflationSurveyRow] = []
    if not expinf_rows and bc_target_bps is not None:
        survey_rows = (
            session.query(ExpInflationSurveyRow)
            .filter(
                ExpInflationSurveyRow.country_code == country_code,
                ExpInflationSurveyRow.date >= start,
                ExpInflationSurveyRow.date <= end,
            )
            .order_by(ExpInflationSurveyRow.date.asc())
            .all()
        )

    nominal_hist: list[float] = []
    anchor_hist: list[float] = []
    for fwd in forwards:
        try:
            forwards_map = _parse_json_dict(fwd.forwards_json)
        except (ValueError, json.JSONDecodeError):
            continue
        fwd_5y5y = forwards_map.get("5y5y")
        if fwd_5y5y is None:
            continue
        nominal_hist.append(_decimal_to_bps(float(fwd_5y5y)))

        if bc_target_bps is None:
            continue

        be_5y5y: float | None = None
        expinf_row = expinf_by_date.get(fwd.date)
        if expinf_row is not None:
            be_5y5y = _expinf_tenors_bps(expinf_row).get("5y5y")
        elif survey_rows:
            matched_survey = _latest_survey_on_or_before(survey_rows, fwd.date)
            if matched_survey is not None:
                be_5y5y = _survey_tenors_bps(matched_survey).get("5y5y")

        if be_5y5y is None:
            continue
        anchor_hist.append(abs(be_5y5y - bc_target_bps))

    return nominal_hist, anchor_hist
