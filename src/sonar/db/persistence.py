"""Persistence functions for L2 overlay outputs.

Atomic 4-row write of an ``NSSFitResult`` into the spec §8 sibling tables
(``yield_curves_{spot,zero,forwards,real}``). On any per-row failure the
whole transaction rolls back: callers never see partial state.

Duplicates surface as a typed exception (``DuplicatePersistError``) so
callers can decide overwrite policy explicitly — there is no implicit
upsert. Phase 2+ may introduce a ``mode="overwrite"`` flag.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from sonar.db.models import (
    NSSYieldCurveForwards,
    NSSYieldCurveReal,
    NSSYieldCurveSpot,
    NSSYieldCurveZero,
    RatingsAgencyRaw,
    RatingsConsolidated,
)
from sonar.overlays.rating_spread import _compute_confidence

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

    from sonar.overlays.nss import NSSFitResult
    from sonar.overlays.rating_spread import ConsolidatedRating, RatingAgencyRaw


class DuplicatePersistError(Exception):
    """Raised when persisting a fit whose ``(country, date, methodology)``
    triplet already exists. The failed transaction is fully rolled back.
    """


def _flags_to_csv(flags: tuple[str, ...]) -> str | None:
    return ",".join(flags) if flags else None


def _to_spot_row(r: NSSFitResult, source_connector: str) -> NSSYieldCurveSpot:
    return NSSYieldCurveSpot(
        country_code=r.country_code,
        date=r.observation_date,
        methodology_version=r.methodology_version,
        fit_id=str(r.fit_id),
        beta_0=r.spot.params.beta_0,
        beta_1=r.spot.params.beta_1,
        beta_2=r.spot.params.beta_2,
        beta_3=r.spot.params.beta_3,
        lambda_1=r.spot.params.lambda_1,
        lambda_2=r.spot.params.lambda_2,
        fitted_yields_json=json.dumps(r.spot.fitted_yields),
        observations_used=r.spot.observations_used,
        rmse_bps=r.spot.rmse_bps,
        xval_deviation_bps=None,
        confidence=r.spot.confidence,
        flags=_flags_to_csv(r.spot.flags),
        source_connector=source_connector,
    )


def _to_zero_row(r: NSSFitResult) -> NSSYieldCurveZero:
    return NSSYieldCurveZero(
        country_code=r.country_code,
        date=r.observation_date,
        methodology_version=r.methodology_version,
        fit_id=str(r.fit_id),
        zero_rates_json=json.dumps(r.zero.zero_rates),
        derivation=r.zero.derivation,
        confidence=r.spot.confidence,
        flags=_flags_to_csv(r.spot.flags),
    )


def _to_forwards_row(r: NSSFitResult) -> NSSYieldCurveForwards:
    breakeven_json = (
        json.dumps(r.forward.breakeven_forwards)
        if r.forward.breakeven_forwards is not None
        else None
    )
    return NSSYieldCurveForwards(
        country_code=r.country_code,
        date=r.observation_date,
        methodology_version=r.methodology_version,
        fit_id=str(r.fit_id),
        forwards_json=json.dumps(r.forward.forwards),
        breakeven_forwards_json=breakeven_json,
        confidence=r.spot.confidence,
        flags=_flags_to_csv(r.spot.flags),
    )


def _to_real_row(r: NSSFitResult) -> NSSYieldCurveReal:
    assert r.real is not None  # caller-checked
    return NSSYieldCurveReal(
        country_code=r.country_code,
        date=r.observation_date,
        methodology_version=r.methodology_version,
        fit_id=str(r.fit_id),
        real_yields_json=json.dumps(r.real.real_yields),
        method=r.real.method,
        linker_connector=r.real.linker_connector,
        confidence=r.spot.confidence,
        flags=_flags_to_csv(r.spot.flags),
    )


def persist_nss_fit_result(
    session: Session,
    result: NSSFitResult,
    source_connector: str = "fred",
) -> None:
    """Persist all sibling rows atomically.

    Writes 3 or 4 rows (real is optional) inside a single transaction. On
    UNIQUE violation against the existing triplet, raises
    ``DuplicatePersistError``; on any other DB error the transaction is
    rolled back and the original exception propagates.
    """
    spot_row = _to_spot_row(result, source_connector=source_connector)
    zero_row = _to_zero_row(result)
    forwards_row = _to_forwards_row(result)
    real_row = _to_real_row(result) if result.real is not None else None

    try:
        # Spot must land first so siblings' FK to spot.fit_id resolves.
        session.add(spot_row)
        session.flush()
        session.add(zero_row)
        session.add(forwards_row)
        if real_row is not None:
            session.add(real_row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        msg_lower = str(e.orig).lower()
        if "unique" in msg_lower:
            err = (
                f"Fit already persisted: country={result.country_code}, "
                f"date={result.observation_date}, version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


def persist_rating_agency_row(
    session: Session,
    row: RatingAgencyRaw,
    *,
    country_code: str,
    observation_date: date,
    rating_id: str,
    source_connector: str,
    methodology_version: str,
) -> None:
    """Persist a single per-agency raw rating row.

    No atomic-set semantics here — each agency row stands alone and the
    consolidator joins them by ``(country, date, rating_type)`` later.
    Re-persisting the same triplet raises ``DuplicatePersistError``.
    """
    confidence = _compute_confidence(flags=[], agencies_count=1)  # per-agency baseline 1.0
    db_row = RatingsAgencyRaw(
        rating_id=rating_id,
        country_code=country_code,
        date=observation_date,
        agency=row.agency,
        rating_type=row.rating_type,
        rating_raw=row.rating_raw,
        sonar_notch_base=row.base_notch,
        outlook=row.outlook,
        watch=row.watch,
        notch_adjusted=row.notch_adjusted,
        action_date=row.action_date,
        source_connector=source_connector,
        methodology_version=methodology_version,
        confidence=confidence,
    )
    try:
        session.add(db_row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"Rating agency row already persisted: country={country_code}, "
                f"date={observation_date}, agency={row.agency}, "
                f"rating_type={row.rating_type}, version={methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


def persist_rating_consolidated(
    session: Session,
    consolidated: ConsolidatedRating,
    *,
    calibration_date: date | None = None,
    methodology_version: str = "RATING_SPREAD_v0.2",
) -> None:
    """Persist a consolidated rating row."""
    db_row = RatingsConsolidated(
        rating_id=str(consolidated.rating_id),
        country_code=consolidated.country_code,
        date=consolidated.observation_date,
        rating_type=consolidated.rating_type,
        consolidated_sonar_notch=consolidated.consolidated_sonar_notch,
        notch_fractional=consolidated.notch_fractional,
        agencies_count=consolidated.agencies_count,
        agencies_json=json.dumps(consolidated.agencies),
        outlook_composite=consolidated.outlook_composite,
        watch_composite=consolidated.watch_composite,
        default_spread_bps=consolidated.default_spread_bps,
        calibration_date=calibration_date,
        methodology_version=methodology_version,
        confidence=consolidated.confidence,
        flags=_flags_to_csv(consolidated.flags),
    )
    try:
        session.add(db_row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"Consolidated rating already persisted: country={consolidated.country_code}, "
                f"date={consolidated.observation_date}, "
                f"rating_type={consolidated.rating_type}, version={methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise
