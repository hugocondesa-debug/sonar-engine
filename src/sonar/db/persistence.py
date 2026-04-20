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
    ERPCAPE,
    ERPDCF,
    ERPEY,
    CreditGdpStock,
    Dsr,
    ERPCanonical,
    ERPGordon,
    IndexValue,
    NSSYieldCurveForwards,
    NSSYieldCurveReal,
    NSSYieldCurveSpot,
    NSSYieldCurveZero,
    RatingsAgencyRaw,
    RatingsConsolidated,
)
from sonar.overlays.erp import G_SUSTAINABLE_CAP
from sonar.overlays.rating_spread import _compute_confidence

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import date

    from sqlalchemy.orm import Session

    from sonar.indices.base import IndexResult
    from sonar.indices.credit.l1_credit_gdp_stock import CreditGdpStockResult
    from sonar.indices.credit.l4_dsr import DsrResult
    from sonar.overlays.erp import ERPFitResult, ERPInput
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


def _to_index_row(result: IndexResult) -> IndexValue:
    return IndexValue(
        index_code=result.index_code,
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        raw_value=result.raw_value,
        zscore_clamped=result.zscore_clamped,
        value_0_100=result.value_0_100,
        sub_indicators_json=json.dumps(result.sub_indicators, default=str),
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_overlays_json=json.dumps(result.source_overlays, default=str),
    )


def persist_index_value(session: Session, result: IndexResult) -> None:
    """Persist a single :class:`IndexResult` row atomically.

    Re-persisting the same ``(index_code, country, date,
    methodology_version)`` triplet raises ``DuplicatePersistError`` —
    callers decide overwrite policy explicitly (Phase 2+ may expose a
    ``mode="overwrite"`` flag once we have idempotency semantics).
    """
    row = _to_index_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"Index value already persisted: index={result.index_code}, "
                f"country={result.country_code}, date={result.date}, "
                f"version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


def persist_many_index_values(session: Session, results: Iterable[IndexResult]) -> int:
    """Persist multiple index rows inside a single transaction.

    Returns the number of rows inserted. On any UNIQUE violation the
    whole batch rolls back and ``DuplicatePersistError`` is raised
    identifying the first collision.
    """
    rows = [_to_index_row(r) for r in results]
    if not rows:
        return 0
    try:
        session.add_all(rows)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = f"Batch contains duplicate index_value triplet: {e.orig}"
            raise DuplicatePersistError(err) from e
        raise
    return len(rows)


# =============================================================================
# ERP persistence — 5-row atomic (DCF + Gordon + EY + CAPE + canonical)
# =============================================================================


def _to_erp_dcf_row(result: ERPFitResult, inputs: ERPInput) -> ERPDCF | None:
    if result.dcf is None:
        return None
    return ERPDCF(
        erp_id=str(result.erp_id),
        market_index=result.market_index,
        country_code=result.country_code,
        date=result.observation_date,
        methodology_version=result.dcf.methodology_version,
        erp_bps=result.dcf.erp_bps,
        implied_r_pct=result.dcf.erp_decimal + inputs.risk_free_nominal,
        earnings_growth_pct=inputs.consensus_growth_5y,
        terminal_growth_pct=inputs.risk_free_nominal,
        confidence=result.dcf.confidence,
        flags=_flags_to_csv(result.dcf.flags),
    )


def _to_erp_gordon_row(result: ERPFitResult, inputs: ERPInput) -> ERPGordon | None:
    if result.gordon is None:
        return None
    g_sustainable = min(inputs.retention * inputs.roe, G_SUSTAINABLE_CAP)
    return ERPGordon(
        erp_id=str(result.erp_id),
        market_index=result.market_index,
        country_code=result.country_code,
        date=result.observation_date,
        methodology_version=result.gordon.methodology_version,
        erp_bps=result.gordon.erp_bps,
        dividend_yield_pct=inputs.dividend_yield_pct,
        buyback_yield_pct=inputs.buyback_yield_pct,
        g_sustainable_pct=g_sustainable,
        confidence=result.gordon.confidence,
        flags=_flags_to_csv(result.gordon.flags),
    )


def _to_erp_ey_row(result: ERPFitResult, inputs: ERPInput) -> ERPEY | None:
    if result.ey is None:
        return None
    return ERPEY(
        erp_id=str(result.erp_id),
        market_index=result.market_index,
        country_code=result.country_code,
        date=result.observation_date,
        methodology_version=result.ey.methodology_version,
        erp_bps=result.ey.erp_bps,
        forward_pe=inputs.index_level / inputs.forward_earnings_est,
        forward_earnings=inputs.forward_earnings_est,
        index_level=inputs.index_level,
        confidence=result.ey.confidence,
        flags=_flags_to_csv(result.ey.flags),
    )


def _to_erp_cape_row(result: ERPFitResult, inputs: ERPInput) -> ERPCAPE | None:
    if result.cape is None:
        return None
    # Derive the 10Y real-earnings average from CAPE per spec §4 identity:
    # CAPE = index_level / real_earnings_10y_avg.
    real_earnings_10y_avg = inputs.index_level / inputs.cape_ratio
    return ERPCAPE(
        erp_id=str(result.erp_id),
        market_index=result.market_index,
        country_code=result.country_code,
        date=result.observation_date,
        methodology_version=result.cape.methodology_version,
        erp_bps=result.cape.erp_bps,
        cape_ratio=inputs.cape_ratio,
        real_risk_free_pct=inputs.risk_free_real,
        real_earnings_10y_avg=real_earnings_10y_avg,
        confidence=result.cape.confidence,
        flags=_flags_to_csv(result.cape.flags),
    )


def _to_erp_canonical_row(result: ERPFitResult) -> ERPCanonical:
    c = result.canonical
    return ERPCanonical(
        erp_id=str(result.erp_id),
        market_index=result.market_index,
        country_code=result.country_code,
        date=result.observation_date,
        methodology_version=c.methodology_version,
        erp_median_bps=c.erp_median_bps,
        erp_range_bps=c.erp_range_bps,
        methods_available=c.methods_available,
        erp_dcf_bps=result.dcf.erp_bps if result.dcf else None,
        erp_gordon_bps=result.gordon.erp_bps if result.gordon else None,
        erp_ey_bps=result.ey.erp_bps if result.ey else None,
        erp_cape_bps=result.cape.erp_bps if result.cape else None,
        forward_eps_divergence_pct=c.forward_eps_divergence_pct,
        xval_deviation_bps=c.xval_deviation_bps,
        confidence=c.confidence,
        flags=_flags_to_csv(c.flags),
    )


def persist_erp_fit_result(
    session: Session,
    result: ERPFitResult,
    inputs: ERPInput,
) -> None:
    """Persist the ERP fit atomically across per-method + canonical tables.

    Writes up to 5 rows inside a single transaction (any method that
    returned ``None`` is skipped; canonical is always written). On
    UNIQUE violation raises :class:`DuplicatePersistError` and the
    transaction rolls back. Mirrors :func:`persist_nss_fit_result`.
    """
    method_rows = [
        _to_erp_dcf_row(result, inputs),
        _to_erp_gordon_row(result, inputs),
        _to_erp_ey_row(result, inputs),
        _to_erp_cape_row(result, inputs),
    ]
    canonical_row = _to_erp_canonical_row(result)

    try:
        for row in method_rows:
            if row is not None:
                session.add(row)
        session.flush()
        session.add(canonical_row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"ERP fit already persisted: market={result.market_index}, "
                f"date={result.observation_date}, erp_id={result.erp_id}"
            )
            raise DuplicatePersistError(err) from e
        raise


def _to_dsr_row(result: DsrResult) -> Dsr:
    return Dsr(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        segment=result.segment,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        dsr_pct=result.dsr_pct,
        dsr_deviation_pp=result.dsr_deviation_pp,
        lending_rate_pct=result.lending_rate_pct,
        avg_maturity_years=result.avg_maturity_years,
        debt_to_gdp_ratio=result.debt_to_gdp_ratio,
        annuity_factor=result.annuity_factor,
        formula_mode=result.formula_mode,
        band=result.band,
        denominator=result.denominator,
        components_json=result.components_json,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_connector=result.source_connector,
    )


def persist_dsr_result(session: Session, result: DsrResult) -> None:
    """Persist a single L4 DSR row atomically.

    Re-persisting the same ``(country_code, date, methodology_version,
    segment)`` quadruple raises :class:`DuplicatePersistError` and the
    transaction rolls back.
    """
    row = _to_dsr_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"DSR row already persisted: country={result.country_code}, "
                f"date={result.date}, segment={result.segment}, "
                f"version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


def _to_credit_gdp_stock_row(result: CreditGdpStockResult) -> CreditGdpStock:
    return CreditGdpStock(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        components_json=result.components_json,
        series_variant=result.series_variant,
        gdp_vintage_mode=result.gdp_vintage_mode,
        lookback_years=result.lookback_years,
        structural_band=result.structural_band,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_connector=result.source_connector,
    )


def persist_credit_gdp_stock_result(session: Session, result: CreditGdpStockResult) -> None:
    """Persist a single L1 ``credit_to_gdp_stock`` row atomically."""
    row = _to_credit_gdp_stock_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"L1 row already persisted: country={result.country_code}, "
                f"date={result.date}, version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise
