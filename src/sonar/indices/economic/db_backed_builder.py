"""DB-backed :class:`E2Inputs` reader (CAL-108 part 1).

Mirrors the :class:`sonar.pipelines.daily_credit_indices.DbBackedInputsBuilder`
pattern from Week 5 Sprint 2b: assembles inputs from rows already
persisted by upstream daily pipelines (``daily_curves`` here) without
ever calling an L0 connector. Callers route
``daily_economic_indices`` ``--backend=db`` through this builder so E2
Leading can persist alongside E1/E3/E4 once NSS curves land.

Scope: currently implements E2. Other economic sub-indices (E1/E3/E4)
source from live connectors and are not DB-backed this sprint.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import TYPE_CHECKING

import structlog

from sonar.db.models import NSSYieldCurveForwards, NSSYieldCurveSpot
from sonar.indices.economic.e2_leading import E2Inputs

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


log = structlog.get_logger()


__all__ = ["EconomicDbBackedInputsBuilder", "build_e2_inputs_from_db"]


MIN_NSS_CONFIDENCE: float = 0.50
DEFAULT_HISTORY_DAYS: int = 365 * 5  # 5Y rolling window for slope + forward spread z-scores


class EconomicDbBackedInputsBuilder:
    """Assembles economic sub-index inputs from persisted overlay rows.

    Mirrors :class:`sonar.pipelines.daily_credit_indices.DbBackedInputsBuilder`
    (Sprint 2b CAL-058): held by the pipeline, carries a
    :class:`Session` reference, and exposes per-sub-index
    ``build_*_inputs`` methods. Callers that only need a single input
    can skip the class and go through the module-level helpers.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def build_e2_inputs(
        self,
        country_code: str,
        observation_date: date,
        *,
        history_days: int = DEFAULT_HISTORY_DAYS,
    ) -> E2Inputs | None:
        """Return :class:`E2Inputs` for ``(country, date)`` or ``None`` on miss.

        Missing or low-confidence NSS rows yield ``None`` + a structured
        log entry so the pipeline routes a clean skip rather than a
        crash.
        """
        return build_e2_inputs_from_db(
            self.session, country_code, observation_date, history_days=history_days
        )


def _parse_decimal_dict(raw: str) -> dict[str, float]:
    """Parse a NSS ``fitted_yields_json`` / ``forwards_json`` payload."""
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        msg = f"expected dict JSON payload, got {type(parsed).__name__}"
        raise ValueError(msg)
    return {str(k): float(v) for k, v in parsed.items()}


def _decimal_to_bps(value: float) -> float:
    return value * 10_000.0


def build_e2_inputs_from_db(
    session: Session,
    country_code: str,
    observation_date: date,
    *,
    history_days: int = DEFAULT_HISTORY_DAYS,
) -> E2Inputs | None:
    """Assemble :class:`E2Inputs` from persisted NSS spot + forwards rows.

    Reads the current ``(country, date)`` triplet for spot + forwards
    and reconstructs slope + forward-spread histories from the trailing
    ``history_days`` window of spot/forward rows. Returns ``None`` when
    the current triplet is absent or confidence < 0.50 so the pipeline
    logs an OVERLAY_MISS-class skip.
    """
    spot = (
        session.query(NSSYieldCurveSpot)
        .filter(
            NSSYieldCurveSpot.country_code == country_code,
            NSSYieldCurveSpot.date == observation_date,
        )
        .order_by(NSSYieldCurveSpot.confidence.desc())
        .first()
    )
    if spot is None:
        log.warning(
            "e2_db_backed.spot_missing",
            country=country_code,
            date=observation_date.isoformat(),
        )
        return None
    if spot.confidence < MIN_NSS_CONFIDENCE:
        log.warning(
            "e2_db_backed.spot_low_confidence",
            country=country_code,
            date=observation_date.isoformat(),
            confidence=spot.confidence,
        )
        return None

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
            "e2_db_backed.forwards_missing",
            country=country_code,
            date=observation_date.isoformat(),
        )
        return None

    try:
        spot_yields = _parse_decimal_dict(spot.fitted_yields_json)
        forwards = _parse_decimal_dict(forwards_row.forwards_json)
    except (ValueError, json.JSONDecodeError) as exc:
        log.error(
            "e2_db_backed.parse_error",
            country=country_code,
            date=observation_date.isoformat(),
            error=str(exc),
        )
        return None

    spot_2y = spot_yields.get("2Y")
    spot_10y = spot_yields.get("10Y")
    forward_2y1y = forwards.get("2y1y")
    if spot_2y is None or spot_10y is None or forward_2y1y is None:
        log.warning(
            "e2_db_backed.tenor_missing",
            country=country_code,
            date=observation_date.isoformat(),
            have_spot=sorted(spot_yields),
            have_forwards=sorted(forwards),
        )
        return None

    start = observation_date - timedelta(days=history_days)
    slope_history, forward_spread_history = _load_histories(
        session, country_code, start=start, end=observation_date
    )

    flags = tuple(spot.flags.split(",")) if spot.flags else ()
    return E2Inputs(
        country_code=country_code,
        observation_date=observation_date,
        spot_2y_bps=_decimal_to_bps(spot_2y),
        spot_10y_bps=_decimal_to_bps(spot_10y),
        forward_2y1y_bps=_decimal_to_bps(forward_2y1y),
        slope_history_bps=tuple(slope_history),
        forward_spread_history_bps=tuple(forward_spread_history),
        nss_confidence=spot.confidence,
        nss_flags=flags,
    )


def _load_histories(
    session: Session,
    country_code: str,
    *,
    start: date,
    end: date,
) -> tuple[list[float], list[float]]:
    """Return ``(slope_history_bps, forward_spread_history_bps)``.

    ``slope`` = 10Y - 2Y from spot; ``forward_spread`` = 2y1y - 10Y
    from forwards + spot. Both series are aligned on dates where both
    spot + forwards rows exist. Dates without complete coverage are
    skipped silently; downstream compute flags ``INSUFFICIENT_HISTORY``
    when the resulting series is < 2 points.
    """
    spot_rows = (
        session.query(NSSYieldCurveSpot)
        .filter(
            NSSYieldCurveSpot.country_code == country_code,
            NSSYieldCurveSpot.date >= start,
            NSSYieldCurveSpot.date <= end,
            NSSYieldCurveSpot.confidence >= MIN_NSS_CONFIDENCE,
        )
        .order_by(NSSYieldCurveSpot.date.asc())
        .all()
    )
    forward_rows = (
        session.query(NSSYieldCurveForwards)
        .filter(
            NSSYieldCurveForwards.country_code == country_code,
            NSSYieldCurveForwards.date >= start,
            NSSYieldCurveForwards.date <= end,
        )
        .order_by(NSSYieldCurveForwards.date.asc())
        .all()
    )
    forwards_by_date = {row.date: row for row in forward_rows}

    slope: list[float] = []
    fwd_spread: list[float] = []
    for spot_row in spot_rows:
        try:
            spot_yields = _parse_decimal_dict(spot_row.fitted_yields_json)
        except (ValueError, json.JSONDecodeError):
            continue
        two_y = spot_yields.get("2Y")
        ten_y = spot_yields.get("10Y")
        if two_y is None or ten_y is None:
            continue
        slope.append(_decimal_to_bps(ten_y - two_y))

        forwards_row = forwards_by_date.get(spot_row.date)
        if forwards_row is None:
            continue
        try:
            forwards = _parse_decimal_dict(forwards_row.forwards_json)
        except (ValueError, json.JSONDecodeError):
            continue
        two_y1y = forwards.get("2y1y")
        if two_y1y is None:
            continue
        fwd_spread.append(_decimal_to_bps(two_y1y - ten_y))

    return slope, fwd_spread
