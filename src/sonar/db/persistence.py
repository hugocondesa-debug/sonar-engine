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
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog
from sqlalchemy.exc import IntegrityError

from sonar.db.models import (
    ERPCAPE,
    ERPDCF,
    ERPEY,
    BisCreditRaw,
    CreditGdpGap,
    CreditGdpStock,
    CreditImpulse,
    Dsr,
    E1Activity,
    E3Labor,
    E4Sentiment,
    ERPCanonical,
    ERPGordon,
    FinancialMomentum,
    FinancialPositioning,
    FinancialRiskAppetite,
    FinancialValuations,
    IndexValue,
    L5MetaRegime,
    M1EffectiveRatesResult as M1EffectiveRatesRow,
    M2TaylorGapsResult as M2TaylorGapsRow,
    M4FciResult as M4FciRow,
    NSSYieldCurveForwards,
    NSSYieldCurveReal,
    NSSYieldCurveSpot,
    NSSYieldCurveZero,
    RatingsAgencyRaw,
    RatingsConsolidated,
)
from sonar.overlays.erp import G_SUSTAINABLE_CAP
from sonar.overlays.rating_spread import _compute_confidence

log = structlog.get_logger()

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import date

    from sqlalchemy.orm import Session

    from sonar.indices.base import IndexResult
    from sonar.indices.credit.l1_credit_gdp_stock import CreditGdpStockResult
    from sonar.indices.credit.l2_credit_gdp_gap import CreditGdpGapResult
    from sonar.indices.credit.l3_credit_impulse import CreditImpulseResult
    from sonar.indices.credit.l4_dsr import DsrResult
    from sonar.indices.economic.e1_activity import E1ActivityResult
    from sonar.indices.economic.e3_labor import E3LaborResult
    from sonar.indices.economic.e4_sentiment import E4SentimentResult
    from sonar.indices.financial.f1_valuations import F1Result
    from sonar.indices.financial.f2_momentum import F2Result
    from sonar.indices.financial.f3_risk_appetite import F3Result
    from sonar.indices.financial.f4_positioning import F4Result
    from sonar.indices.monetary.m1_effective_rates import (
        M1EffectiveRatesResult as M1Result,
    )
    from sonar.indices.monetary.m2_taylor_gaps import (
        M2TaylorGapsResult as M2Result,
    )
    from sonar.indices.monetary.m4_fci import M4FciResult as M4Result
    from sonar.indices.monetary.orchestrator import MonetaryIndicesResults
    from sonar.indices.orchestrator import CreditIndicesResults, FinancialIndicesResults
    from sonar.overlays.erp import ERPFitResult, ERPInput
    from sonar.overlays.nss import NSSFitResult
    from sonar.overlays.rating_spread import ConsolidatedRating, RatingAgencyRaw
    from sonar.regimes.types import L5RegimeResult


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


def _to_credit_gdp_gap_row(result: CreditGdpGapResult) -> CreditGdpGap:
    return CreditGdpGap(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        gap_hp_pp=result.gap_hp_pp,
        gap_hamilton_pp=result.gap_hamilton_pp,
        trend_gdp_pct=result.trend_gdp_pct,
        hp_lambda=result.hp_lambda,
        hamilton_horizon_q=result.hamilton_horizon_q,
        concordance=result.concordance,
        phase_band=result.phase_band,
        components_json=result.components_json,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_connector=result.source_connector,
    )


def persist_credit_gdp_gap_result(session: Session, result: CreditGdpGapResult) -> None:
    """Persist a single L2 ``credit_to_gdp_gap`` row atomically."""
    row = _to_credit_gdp_gap_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"L2 row already persisted: country={result.country_code}, "
                f"date={result.date}, version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


def _to_credit_impulse_row(result: CreditImpulseResult) -> CreditImpulse:
    return CreditImpulse(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        segment=result.segment,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        impulse_pp=result.impulse_pp,
        flow_t_lcu=result.flow_t_lcu,
        flow_t_minus4_lcu=result.flow_t_minus4_lcu,
        delta_flow_lcu=result.delta_flow_lcu,
        gdp_t_minus4_lcu=result.gdp_t_minus4_lcu,
        series_variant=result.series_variant,
        smoothing=result.smoothing,
        state=result.state,
        components_json=result.components_json,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_connector=result.source_connector,
    )


def persist_credit_impulse_result(session: Session, result: CreditImpulseResult) -> None:
    """Persist a single L3 ``credit_impulse`` row atomically (segment-aware)."""
    row = _to_credit_impulse_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"L3 row already persisted: country={result.country_code}, "
                f"date={result.date}, segment={result.segment}, "
                f"version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


def persist_many_credit_results(session: Session, results: CreditIndicesResults) -> dict[str, int]:
    """Persist all available credit sub-indices inside a single transaction.

    Returns a ``{index_name: rows_written}`` map. Sub-indices absent from
    ``results`` (``None``) are skipped silently. On any ``IntegrityError``
    the entire transaction rolls back and :class:`DuplicatePersistError`
    surfaces.
    """
    written: dict[str, int] = {"l1": 0, "l2": 0, "l3": 0, "l4": 0}
    rows: list[CreditGdpStock | CreditGdpGap | CreditImpulse | Dsr] = []
    if results.l1 is not None:
        rows.append(_to_credit_gdp_stock_row(results.l1))
        written["l1"] = 1
    if results.l2 is not None:
        rows.append(_to_credit_gdp_gap_row(results.l2))
        written["l2"] = 1
    if results.l3 is not None:
        rows.append(_to_credit_impulse_row(results.l3))
        written["l3"] = 1
    if results.l4 is not None:
        rows.append(_to_dsr_row(results.l4))
        written["l4"] = 1
    if not rows:
        return written
    try:
        session.add_all(rows)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = f"Batch credit persist contains duplicate: {e.orig}"
            raise DuplicatePersistError(err) from e
        raise
    return written


# =============================================================================
# BIS ingestion (CAL-058) — upsert with revision detection
# =============================================================================


@dataclass(frozen=True, slots=True)
class BisRawObservation:
    """Normalized BIS observation ready for persistence.

    Unit descriptors per dataflow: WS_TC → ``pct_gdp``, WS_DSR →
    ``dsr_pct``, WS_CREDIT_GAP → ``gap_pp``. ``fetch_response_hash`` is
    sha256 of the raw BIS response body, used for revision detection on
    re-fetch (see :func:`persist_bis_raw_observations`).
    """

    country_code: str
    date: date
    dataflow: str
    value_raw: float
    unit_descriptor: str
    fetch_response_hash: str | None


def persist_bis_raw_observations(
    session: Session,
    observations: Iterable[BisRawObservation],
) -> dict[str, int]:
    """Idempotent upsert of BIS observations into ``bis_credit_raw``.

    For each observation:

    * If no existing row for (country, date, dataflow) → INSERT (counts as new).
    * If row exists and hash matches → skip silently (counts as skipped).
    * If row exists and hash differs → UPDATE value_raw +
      fetch_response_hash + fetched_at; counts as updated. A
      BIS_DATA_REVISION warning is logged so operators can trace
      provider revisions.

    Transaction: commits at end. On :class:`IntegrityError` rolls back
    and re-raises (callers do not typically see dup errors because we
    pre-check via SELECT; any IntegrityError would indicate a race).

    Returns ``{"new": int, "skipped": int, "updated": int}``.
    """
    counts = {"new": 0, "skipped": 0, "updated": 0}
    obs_list = list(observations)
    if not obs_list:
        return counts

    for obs in obs_list:
        existing = (
            session.query(BisCreditRaw)
            .filter(
                BisCreditRaw.country_code == obs.country_code,
                BisCreditRaw.date == obs.date,
                BisCreditRaw.dataflow == obs.dataflow,
            )
            .one_or_none()
        )
        if existing is None:
            session.add(
                BisCreditRaw(
                    country_code=obs.country_code,
                    date=obs.date,
                    dataflow=obs.dataflow,
                    value_raw=obs.value_raw,
                    unit_descriptor=obs.unit_descriptor,
                    fetch_response_hash=obs.fetch_response_hash,
                )
            )
            counts["new"] += 1
            continue
        if existing.fetch_response_hash == obs.fetch_response_hash:
            counts["skipped"] += 1
            continue
        # Revision detected — update in place, surface via log.
        log.warning(
            "bis.data_revision",
            country=obs.country_code,
            date=obs.date.isoformat(),
            dataflow=obs.dataflow,
            old_value=existing.value_raw,
            new_value=obs.value_raw,
        )
        existing.value_raw = obs.value_raw
        existing.fetch_response_hash = obs.fetch_response_hash
        existing.unit_descriptor = obs.unit_descriptor
        counts["updated"] += 1
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise
    return counts


def _to_f1_row(result: F1Result) -> FinancialValuations:
    return FinancialValuations(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        components_json=result.components_json,
        cape_ratio=result.cape_ratio,
        erp_median_bps=result.erp_median_bps,
        buffett_ratio=result.buffett_ratio,
        forward_pe=result.forward_pe,
        property_gap_pp=result.property_gap_pp,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_overlay=result.source_overlay,
    )


def persist_f1_valuations_result(session: Session, result: F1Result) -> None:
    row = _to_f1_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = f"F1 row already persisted: {result.country_code} {result.date}"
            raise DuplicatePersistError(err) from e
        raise


def _to_f2_row(result: F2Result) -> FinancialMomentum:
    return FinancialMomentum(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        components_json=result.components_json,
        mom_3m_pct=result.mom_3m_pct,
        mom_6m_pct=result.mom_6m_pct,
        mom_12m_pct=result.mom_12m_pct,
        breadth_above_ma200_pct=result.breadth_above_ma200_pct,
        cross_asset_score=result.cross_asset_score,
        primary_index=result.primary_index,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
    )


def persist_f2_momentum_result(session: Session, result: F2Result) -> None:
    row = _to_f2_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = f"F2 row already persisted: {result.country_code} {result.date}"
            raise DuplicatePersistError(err) from e
        raise


def _to_f3_row(result: F3Result) -> FinancialRiskAppetite:
    return FinancialRiskAppetite(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        components_json=result.components_json,
        vix_level=result.vix_level,
        move_level=result.move_level,
        credit_spread_hy_bps=result.credit_spread_hy_bps,
        credit_spread_ig_bps=result.credit_spread_ig_bps,
        fci_level=result.fci_level,
        crypto_vol_level=result.crypto_vol_level,
        components_available=result.components_available,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
    )


def persist_f3_risk_appetite_result(session: Session, result: F3Result) -> None:
    row = _to_f3_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = f"F3 row already persisted: {result.country_code} {result.date}"
            raise DuplicatePersistError(err) from e
        raise


def _to_f4_row(result: F4Result) -> FinancialPositioning:
    return FinancialPositioning(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        components_json=result.components_json,
        aaii_bull_minus_bear_pct=result.aaii_bull_minus_bear_pct,
        put_call_ratio=result.put_call_ratio,
        cot_noncomm_net_sp500=result.cot_noncomm_net_sp500,
        margin_debt_gdp_pct=result.margin_debt_gdp_pct,
        ipo_activity_score=result.ipo_activity_score,
        components_available=result.components_available,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
    )


def persist_f4_positioning_result(session: Session, result: F4Result) -> None:
    row = _to_f4_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = f"F4 row already persisted: {result.country_code} {result.date}"
            raise DuplicatePersistError(err) from e
        raise


# ---------------------------------------------------------------------------
# Monetary indices (M1 / M2 / M4) — week6 sprint 2b C6 (CAL-100)
# ---------------------------------------------------------------------------


def _to_m1_row(result: M1Result) -> M1EffectiveRatesRow:
    return M1EffectiveRatesRow(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        policy_rate_pct=result.policy_rate_pct,
        shadow_rate_pct=result.shadow_rate_pct,
        real_rate_pct=result.real_rate_pct,
        r_star_pct=result.r_star_pct,
        components_json=result.components_json,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_connector=result.source_connector,
    )


def persist_m1_effective_rates_result(session: Session, result: M1Result) -> None:
    """Persist a single ``monetary_m1_effective_rates`` row atomically."""
    row = _to_m1_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"M1 row already persisted: country={result.country_code}, "
                f"date={result.date}, version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


def _to_m2_row(result: M2Result) -> M2TaylorGapsRow:
    return M2TaylorGapsRow(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        taylor_implied_pct=result.taylor_implied_pct,
        taylor_gap_pp=result.taylor_gap_pp,
        taylor_uncertainty_pp=result.taylor_uncertainty_pp,
        r_star_source=result.r_star_source,
        output_gap_source=result.output_gap_source,
        variants_computed=result.variants_computed,
        components_json=result.components_json,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_connector=result.source_connector,
    )


def persist_m2_taylor_gaps_result(session: Session, result: M2Result) -> None:
    """Persist a single ``monetary_m2_taylor_gaps`` row atomically."""
    row = _to_m2_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"M2 row already persisted: country={result.country_code}, "
                f"date={result.date}, version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


def _to_m4_row(result: M4Result) -> M4FciRow:
    return M4FciRow(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        fci_level=result.fci_level,
        fci_change_12m=result.fci_change_12m,
        fci_provider=result.fci_provider,
        components_available=result.components_available,
        fci_components_json=result.fci_components_json,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_connector=result.source_connector,
    )


def persist_m4_fci_result(session: Session, result: M4Result) -> None:
    """Persist a single ``monetary_m4_fci`` row atomically."""
    row = _to_m4_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"M4 row already persisted: country={result.country_code}, "
                f"date={result.date}, version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


# ---------------------------------------------------------------------------
# Economic indices (E1 / E3 / E4) — week7 sprint B (daily pipeline)
# ---------------------------------------------------------------------------


def _to_e1_row(result: E1ActivityResult) -> E1Activity:
    return E1Activity(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        components_json=result.components_json,
        components_available=result.components_available,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_connectors=result.source_connectors,
    )


def persist_e1_activity_result(session: Session, result: E1ActivityResult) -> None:
    """Persist a single ``idx_economic_e1_activity`` row atomically."""
    row = _to_e1_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"E1 row already persisted: country={result.country_code}, "
                f"date={result.date}, version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


def _to_e3_row(result: E3LaborResult) -> E3Labor:
    return E3Labor(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        sahm_triggered=1 if result.sahm_triggered else 0,
        sahm_value=result.sahm_value,
        components_json=result.components_json,
        components_available=result.components_available,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_connectors=result.source_connectors,
    )


def persist_e3_labor_result(session: Session, result: E3LaborResult) -> None:
    """Persist a single ``idx_economic_e3_labor`` row atomically."""
    row = _to_e3_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"E3 row already persisted: country={result.country_code}, "
                f"date={result.date}, version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


def _to_e4_row(result: E4SentimentResult) -> E4Sentiment:
    return E4Sentiment(
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_normalized=result.score_normalized,
        score_raw=result.score_raw,
        components_json=result.components_json,
        components_available=result.components_available,
        lookback_years=result.lookback_years,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        source_connectors=result.source_connectors,
    )


def persist_e4_sentiment_result(session: Session, result: E4SentimentResult) -> None:
    """Persist a single ``idx_economic_e4_sentiment`` row atomically."""
    row = _to_e4_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"E4 row already persisted: country={result.country_code}, "
                f"date={result.date}, version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise


def persist_many_economic_results(
    session: Session,
    *,
    e1: E1ActivityResult | None = None,
    e2: IndexResult | None = None,
    e3: E3LaborResult | None = None,
    e4: E4SentimentResult | None = None,
) -> dict[str, int]:
    """Persist any subset of E1/E2/E3/E4 results in a single transaction.

    E2 (Leading) persists as a generic :class:`IndexValue` row (no
    dedicated table); E1/E3/E4 each have their own typed table. On any
    UNIQUE violation the whole batch rolls back and
    :class:`DuplicatePersistError` is raised.
    """
    written: dict[str, int] = {"e1": 0, "e2": 0, "e3": 0, "e4": 0}
    rows: list[E1Activity | E3Labor | E4Sentiment | IndexValue] = []
    if e1 is not None:
        rows.append(_to_e1_row(e1))
        written["e1"] = 1
    if e2 is not None:
        rows.append(_to_index_row(e2))
        written["e2"] = 1
    if e3 is not None:
        rows.append(_to_e3_row(e3))
        written["e3"] = 1
    if e4 is not None:
        rows.append(_to_e4_row(e4))
        written["e4"] = 1
    if not rows:
        return written
    try:
        session.add_all(rows)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = f"Batch economic persist contains duplicate: {e.orig}"
            raise DuplicatePersistError(err) from e
        raise
    return written


def persist_many_monetary_results(
    session: Session,
    results: MonetaryIndicesResults,
    *,
    m3: IndexResult | None = None,
) -> dict[str, int]:
    """Persist available M1/M2/M4 rows (from :class:`MonetaryIndicesResults`)
    plus optional M3 (generic :class:`IndexValue`) in one transaction."""
    written: dict[str, int] = {"m1": 0, "m2": 0, "m3": 0, "m4": 0}
    rows: list[M1EffectiveRatesRow | M2TaylorGapsRow | M4FciRow | IndexValue] = []
    if results.m1 is not None:
        rows.append(_to_m1_row(results.m1))
        written["m1"] = 1
    if results.m2 is not None:
        rows.append(_to_m2_row(results.m2))
        written["m2"] = 1
    if m3 is not None:
        rows.append(_to_index_row(m3))
        written["m3"] = 1
    if results.m4 is not None:
        rows.append(_to_m4_row(results.m4))
        written["m4"] = 1
    if not rows:
        return written
    try:
        session.add_all(rows)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = f"Batch monetary persist contains duplicate: {e.orig}"
            raise DuplicatePersistError(err) from e
        raise
    return written


def persist_many_financial_results(
    session: Session, results: FinancialIndicesResults
) -> dict[str, int]:
    """Persist available F1-F4 rows inside a single transaction."""
    written: dict[str, int] = {"f1": 0, "f2": 0, "f3": 0, "f4": 0}
    rows: list[
        FinancialValuations | FinancialMomentum | FinancialRiskAppetite | FinancialPositioning
    ] = []
    if results.f1 is not None:
        rows.append(_to_f1_row(results.f1))
        written["f1"] = 1
    if results.f2 is not None:
        rows.append(_to_f2_row(results.f2))
        written["f2"] = 1
    if results.f3 is not None:
        rows.append(_to_f3_row(results.f3))
        written["f3"] = 1
    if results.f4 is not None:
        rows.append(_to_f4_row(results.f4))
        written["f4"] = 1
    if not rows:
        return written
    try:
        session.add_all(rows)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = f"Batch financial persist contains duplicate: {e.orig}"
            raise DuplicatePersistError(err) from e
        raise
    return written


# ---------------------------------------------------------------------------
# Overlay batch — week7 sprint C C6 (daily_overlays orchestration)
# ---------------------------------------------------------------------------


def persist_many_overlay_results(
    session: Session,
    *,
    erp: ERPFitResult | None = None,
    erp_inputs: ERPInput | None = None,
    rating: ConsolidatedRating | None = None,
    rating_calibration_date: date | None = None,
    rating_methodology_version: str = "RATING_SPREAD_v0.2",
    crp_index: IndexResult | None = None,
    expected_inflation_index: IndexResult | None = None,
) -> dict[str, int]:
    """Persist any subset of the 4 daily overlays in sequence.

    Uses the existing per-overlay helpers rather than a single
    ``session.add_all`` — ERP alone writes 5 rows across sibling tables
    and rating writes through a dedicated helper. CRP + expected-
    inflation ride on the generic :class:`IndexValue` table (no
    dedicated overlay tables exist yet; adding them needs a migration
    out of scope for this sprint).

    Any :class:`DuplicatePersistError` bubbles up with an ``overlay=...``
    prefix so callers can distinguish which overlay collided.
    """
    written: dict[str, int] = {"erp": 0, "crp": 0, "rating": 0, "expected_inflation": 0}

    if erp is not None:
        if erp_inputs is None:
            msg = "persist_many_overlay_results requires erp_inputs alongside erp"
            raise ValueError(msg)
        try:
            persist_erp_fit_result(session, erp, erp_inputs)
        except DuplicatePersistError as e:
            raise DuplicatePersistError(f"overlay=erp {e}") from e
        written["erp"] = 1

    if rating is not None:
        try:
            persist_rating_consolidated(
                session,
                rating,
                calibration_date=rating_calibration_date,
                methodology_version=rating_methodology_version,
            )
        except DuplicatePersistError as e:
            raise DuplicatePersistError(f"overlay=rating {e}") from e
        written["rating"] = 1

    if crp_index is not None:
        try:
            persist_index_value(session, crp_index)
        except DuplicatePersistError as e:
            raise DuplicatePersistError(f"overlay=crp {e}") from e
        written["crp"] = 1

    if expected_inflation_index is not None:
        try:
            persist_index_value(session, expected_inflation_index)
        except DuplicatePersistError as e:
            raise DuplicatePersistError(f"overlay=expected_inflation {e}") from e
        written["expected_inflation"] = 1

    return written


# ---------------------------------------------------------------------------
# L5 regime persistence — week8 sprint H
# ---------------------------------------------------------------------------


def _to_l5_row(result: L5RegimeResult) -> L5MetaRegime:
    from uuid import uuid4  # noqa: PLC0415 — local to keep helper standalone

    return L5MetaRegime(
        l5_id=str(uuid4()),
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        meta_regime=result.meta_regime.value,
        ecs_id=result.ecs_id,
        cccs_id=result.cccs_id,
        fcs_id=result.fcs_id,
        msc_id=result.msc_id,
        confidence=result.confidence,
        flags=_flags_to_csv(result.flags),
        classification_reason=result.classification_reason,
    )


def persist_l5_meta_regime_result(session: Session, result: L5RegimeResult) -> None:
    """Persist an :class:`L5RegimeResult` row atomically.

    Re-persisting the same ``(country, date, methodology_version)``
    triplet raises :class:`DuplicatePersistError` — consistent with
    the existing cycle / index persistence helpers.
    """
    row = _to_l5_row(result)
    try:
        session.add(row)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "unique" in str(e.orig).lower():
            err = (
                f"L5 row already persisted: country={result.country_code}, "
                f"date={result.date}, version={result.methodology_version}"
            )
            raise DuplicatePersistError(err) from e
        raise
