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

from sonar.db.models import IndexValue, NSSYieldCurveForwards
from sonar.indices.monetary._config import load_bc_targets, load_country_to_target
from sonar.indices.monetary.m3_market_expectations import M3Inputs

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


log = structlog.get_logger()


__all__ = ["MonetaryDbBackedInputsBuilder", "build_m3_inputs_from_db"]


EXPINF_INDEX_CODE: str = "EXPINF_CANONICAL"
DEFAULT_HISTORY_DAYS: int = 365 * 5  # 5Y rolling window


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


def build_m3_inputs_from_db(
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
    if expinf_row is None:
        log.warning(
            "m3_db_backed.expinf_missing",
            country=country_code,
            date=observation_date.isoformat(),
        )
        return None
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

    expinf_flags = tuple(expinf_row.flags.split(",")) if expinf_row.flags else ()
    # CAL-113 (Sprint M): if the EXPINF row carries per-method tenor
    # splits, distinguish bei_10y from survey_10y; otherwise fall back
    # to the legacy behaviour (populate bei only from unified tenors +
    # leave survey None so the compute module emits
    # BEI_SURVEY_DIVERGENCE_UNAVAILABLE).
    bei_tenors_bps = _expinf_method_tenors_bps(expinf_row, "bei_tenors")
    survey_tenors_bps = _expinf_method_tenors_bps(expinf_row, "survey_tenors")
    if bei_tenors_bps or survey_tenors_bps:
        bei_10y_bps: float | None = bei_tenors_bps.get("10Y")
        survey_10y_bps: float | None = survey_tenors_bps.get("10Y")
    else:
        bei_10y_bps = tenors_bps.get("10Y")
        survey_10y_bps = None

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
        expinf_confidence=expinf_row.confidence,
        expinf_flags=expinf_flags,
    )


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
        expinf_row = expinf_by_date.get(fwd.date)
        if expinf_row is None:
            continue
        expinf_tenors = _expinf_tenors_bps(expinf_row)
        be_5y5y = expinf_tenors.get("5y5y")
        if be_5y5y is None:
            continue
        anchor_hist.append(abs(be_5y5y - bc_target_bps))

    return nominal_hist, anchor_hist
