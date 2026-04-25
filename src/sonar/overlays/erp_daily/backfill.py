"""US ERP daily backfill orchestrator (Sprint 3).

Iterates a business-day window for ``market_index='SPX'`` /
``country_code='US'``; for each date it assembles an
:class:`~sonar.overlays.erp.ERPInput` from L1 yield rows + connector
output, fits all 4 ERP methods via :func:`fit_erp_us`, and persists the
atomic 5-sibling row set (DCF + Gordon + EY + CAPE + canonical)
sharing a single ``erp_id`` UUID per ``(market_index, date)``.

Inputs sourced per spec §2:

* **Risk-free** (`yield_curves_spot/real`, US 10Y) — read from the
  L1 store; the NSS spot/real backfill (Sprint 2) populated 66 days
  of US history that this orchestrator consumes verbatim.
* **Index level** — FRED ``SP500`` daily series via
  :func:`sonar.connectors._fred_util.fetch_fred_values` (one batched
  call covering the full window).
* **Trailing earnings + CAPE + price/dividend** — Shiller monthly
  ``ie_data.xls`` via :class:`sonar.connectors.shiller.ShillerConnector`
  (one xls download cached 30d, parsed per-date for the
  at-or-before monthly row).
* **Forward earnings** — proxied from trailing earnings with
  ``FORWARD_EPS_PROXY_TRAILING`` flag; FactSet/Yardeni PDF scrapers
  are not invoked in the historical backfill (current-snapshot only —
  Phase 2+ wires per-week PDF replay).
* **Buyback yield** — Sprint 1 stub
  :class:`sonar.connectors.spdji_buyback.SPDJIBuybackConnector`
  raises ``DataUnavailableError`` unconditionally; we pass
  ``buyback_yield_pct=None`` so :func:`_compute_gordon` emits ``STALE``
  per spec §6 row "Buyback > 1q stale".
* **Damodaran xval** — monthly implied ERP per ``date.month`` via
  :class:`sonar.connectors.damodaran.DamodaranConnector` (US only,
  spec §4 step 8 — silent skip when histimpl row absent).

Idempotent: each per-day ``persist_erp_fit_result`` writes inside its
own transaction; ``DuplicatePersistError`` on the
``(market_index, date, methodology_version)`` UNIQUE constraint is
caught and counted as ``skipped_existing``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

import httpx
import pandas as pd
import structlog

from sonar.connectors._fred_util import fetch_fred_values
from sonar.connectors.cache import ConnectorCache
from sonar.connectors.damodaran import DamodaranConnector
from sonar.connectors.shiller import ShillerConnector
from sonar.db.models import NSSYieldCurveReal, NSSYieldCurveSpot
from sonar.db.persistence import DuplicatePersistError, persist_erp_fit_result
from sonar.overlays.erp import ERPInput, fit_erp_us
from sonar.overlays.exceptions import InsufficientDataError, OverlayError

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session

log = structlog.get_logger()

FRED_SERIES_SP500 = "SP500"
FRED_TTL_SECONDS = 24 * 3600
DEFAULT_LOOKBACK_BD = 60


@dataclass(frozen=True)
class ErpBackfillSummary:
    """Aggregate counters returned by :func:`backfill_erp_us`."""

    dates_window: tuple[date, date] | None
    persisted: int
    skipped_existing: int
    skipped_no_inputs: int
    errors: int

    def total(self) -> int:
        return self.persisted + self.skipped_existing + self.skipped_no_inputs + self.errors


def _bdays(start: date, end: date) -> list[date]:
    """Inclusive business-day range using pandas' default ``B`` calendar."""
    if end < start:
        return []
    return [d.date() for d in pd.bdate_range(start=pd.Timestamp(start), end=pd.Timestamp(end))]


def _read_us_10y_yields(
    session: Session,
    *,
    start: date,
    end: date,
) -> tuple[dict[date, float], dict[date, float], dict[date, float]]:
    """Return ``(spot_10y_by_date, real_10y_by_date, spot_confidence_by_date)``.

    Each map keyed by observation date (US, 10Y tenor only). Missing
    entries are silently absent — callers fall back to the latest
    at-or-before lookup.
    """
    spot_rows = (
        session.query(NSSYieldCurveSpot)
        .filter(
            NSSYieldCurveSpot.country_code == "US",
            NSSYieldCurveSpot.date >= start,
            NSSYieldCurveSpot.date <= end,
        )
        .all()
    )
    real_rows = (
        session.query(NSSYieldCurveReal)
        .filter(
            NSSYieldCurveReal.country_code == "US",
            NSSYieldCurveReal.date >= start,
            NSSYieldCurveReal.date <= end,
        )
        .all()
    )

    spot: dict[date, float] = {}
    real: dict[date, float] = {}
    confidence: dict[date, float] = {}
    for spot_row in spot_rows:
        fitted = json.loads(spot_row.fitted_yields_json)
        rate = fitted.get("10Y")
        if rate is not None:
            spot[spot_row.date] = float(rate)
            confidence[spot_row.date] = float(spot_row.confidence)
    for real_row in real_rows:
        real_fitted = json.loads(real_row.real_yields_json)
        real_rate = real_fitted.get("10Y")
        if real_rate is not None:
            real[real_row.date] = float(real_rate)
    return spot, real, confidence


async def _prefetch_sp500(
    *,
    api_key: str,
    cache_dir: Path,
    start: date,
    end: date,
) -> dict[date, float]:
    """Batch-fetch FRED SP500 daily closes for the full window."""
    cache = ConnectorCache(cache_dir / "fred_sp500")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Pad the window 7 calendar days backward so we always have a
            # close to consume even if the start date itself is non-trading.
            pairs = await fetch_fred_values(
                client,
                cache,
                series_id=FRED_SERIES_SP500,
                api_key=api_key,
                start=start - timedelta(days=7),
                end=end,
                cache_prefix="erp_daily_sp500",
            )
    finally:
        cache.close()
    return dict(pairs)


def _at_or_before(by_date: dict[date, float], target: date) -> tuple[date, float] | None:
    """Return ``(observation_date, value)`` for the most recent key ≤ target."""
    candidates = [d for d in by_date if d <= target]
    if not candidates:
        return None
    chosen = max(candidates)
    return chosen, by_date[chosen]


async def backfill_erp_us(
    session: Session,
    *,
    start: date,
    end: date,
    cache_dir: Path,
    fred_api_key: str,
) -> ErpBackfillSummary:
    """Persist ERP rows for every business day in ``[start, end]`` (US/SPX).

    Skip rules:

    * Missing NSS spot or real 10Y row at-or-before the date → record
      ``skipped_no_inputs`` (Sprint 2 already populated 66 US days; gaps
      are improbable inside the window).
    * Missing FRED ``SP500`` close at-or-before the date → record
      ``skipped_no_inputs``.
    * Shiller fetch raises any error → record ``errors`` and continue.
    * ``persist_erp_fit_result`` raises :class:`DuplicatePersistError`
      → record ``skipped_existing`` (idempotent re-run).
    * ``risk_free_confidence < 0.50`` (precondition raise inside
      :func:`fit_erp_us`) → record ``skipped_no_inputs``.

    Returns a structured :class:`ErpBackfillSummary` for the CLI to
    surface.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    bdays = _bdays(start, end)
    if not bdays:
        log.warning("erp_daily.backfill.empty_window", start=start, end=end)
        return ErpBackfillSummary(None, 0, 0, 0, 0)

    log.info(
        "erp_daily.backfill.start",
        start=bdays[0].isoformat(),
        end=bdays[-1].isoformat(),
        bdays=len(bdays),
    )

    spot_map, real_map, spot_conf_map = _read_us_10y_yields(
        session, start=bdays[0] - timedelta(days=14), end=bdays[-1]
    )
    sp500_map = await _prefetch_sp500(
        api_key=fred_api_key,
        cache_dir=cache_dir,
        start=bdays[0],
        end=bdays[-1],
    )

    shiller = ShillerConnector(cache_dir=str(cache_dir / "shiller"))
    damodaran = DamodaranConnector(cache_dir=str(cache_dir / "damodaran"))

    persisted = 0
    skipped_existing = 0
    skipped_no_inputs = 0
    errors = 0

    try:
        for d in bdays:
            outcome = await _persist_one_day(
                session,
                observation_date=d,
                spot_map=spot_map,
                real_map=real_map,
                spot_conf_map=spot_conf_map,
                sp500_map=sp500_map,
                shiller=shiller,
                damodaran=damodaran,
            )
            if outcome == "persisted":
                persisted += 1
            elif outcome == "duplicate":
                skipped_existing += 1
            elif outcome == "no_inputs":
                skipped_no_inputs += 1
            else:
                errors += 1
    finally:
        await shiller.aclose()
        await damodaran.aclose()

    log.info(
        "erp_daily.backfill.done",
        persisted=persisted,
        skipped_existing=skipped_existing,
        skipped_no_inputs=skipped_no_inputs,
        errors=errors,
    )
    return ErpBackfillSummary(
        dates_window=(bdays[0], bdays[-1]),
        persisted=persisted,
        skipped_existing=skipped_existing,
        skipped_no_inputs=skipped_no_inputs,
        errors=errors,
    )


async def _persist_one_day(  # noqa: PLR0911 — outcome routing keeps each branch readable
    session: Session,
    *,
    observation_date: date,
    spot_map: dict[date, float],
    real_map: dict[date, float],
    spot_conf_map: dict[date, float],
    sp500_map: dict[date, float],
    shiller: ShillerConnector,
    damodaran: DamodaranConnector,
) -> str:
    """Compute + persist for a single date. Return outcome string.

    Outcomes: ``"persisted"`` / ``"duplicate"`` / ``"no_inputs"`` /
    ``"error"``. Errors are logged but never raised — backfill keeps
    going across days.
    """
    spot_lookup = _at_or_before(spot_map, observation_date)
    real_lookup = _at_or_before(real_map, observation_date)
    sp500_lookup = _at_or_before(sp500_map, observation_date)
    if spot_lookup is None or real_lookup is None or sp500_lookup is None:
        log.info(
            "erp_daily.backfill.skip_no_inputs",
            date=observation_date.isoformat(),
            spot_missing=spot_lookup is None,
            real_missing=real_lookup is None,
            sp500_missing=sp500_lookup is None,
        )
        return "no_inputs"

    _, rf_nominal = spot_lookup
    _, rf_real = real_lookup
    spot_date, _ = spot_lookup
    rf_confidence = spot_conf_map.get(spot_date, 0.95)
    _, sp500_close = sp500_lookup

    upstream_flags: list[str] = []

    try:
        shiller_snap = await shiller.fetch_snapshot(observation_date)
    except (OverlayError, ValueError, OSError, httpx.HTTPError) as exc:
        log.warning(
            "erp_daily.backfill.shiller_error",
            date=observation_date.isoformat(),
            error=str(exc),
        )
        return "error"

    cape_ratio = float(shiller_snap.cape_ratio)
    trailing_earnings = float(shiller_snap.earnings_nominal)
    if cape_ratio <= 0 or trailing_earnings <= 0:
        log.info(
            "erp_daily.backfill.shiller_invalid",
            date=observation_date.isoformat(),
            cape=cape_ratio,
            trailing=trailing_earnings,
        )
        return "no_inputs"

    dividend_yield_pct = (
        shiller_snap.dividend_nominal / shiller_snap.price_nominal
        if shiller_snap.price_nominal
        else 0.0
    )
    forward_earnings_est = trailing_earnings
    upstream_flags.append("FORWARD_EPS_PROXY_TRAILING")

    damodaran_decimal: float | None = None
    try:
        dam_row = await damodaran.fetch_monthly_implied_erp(
            observation_date.year, observation_date.month
        )
    except (OverlayError, ValueError, OSError, httpx.HTTPError) as exc:
        log.warning(
            "erp_daily.backfill.damodaran_error",
            date=observation_date.isoformat(),
            error=str(exc),
        )
    else:
        if dam_row is not None:
            damodaran_decimal = float(dam_row.implied_erp_decimal)

    inputs = ERPInput(
        market_index="SPX",
        country_code="US",
        observation_date=observation_date,
        index_level=float(sp500_close),
        trailing_earnings=trailing_earnings,
        forward_earnings_est=forward_earnings_est,
        dividend_yield_pct=float(dividend_yield_pct),
        buyback_yield_pct=None,
        cape_ratio=cape_ratio,
        risk_free_nominal=float(rf_nominal),
        risk_free_real=float(rf_real),
        consensus_growth_5y=0.10,
        retention=0.60,
        roe=0.20,
        risk_free_confidence=float(rf_confidence),
        upstream_flags=tuple(sorted(upstream_flags)),
    )

    try:
        fit = fit_erp_us(inputs, damodaran_erp_decimal=damodaran_decimal)
    except InsufficientDataError as exc:
        log.warning(
            "erp_daily.backfill.insufficient",
            date=observation_date.isoformat(),
            error=str(exc),
        )
        return "no_inputs"

    try:
        persist_erp_fit_result(session, fit, inputs)
    except DuplicatePersistError:
        log.info(
            "erp_daily.backfill.duplicate",
            date=observation_date.isoformat(),
            erp_id=str(fit.erp_id),
        )
        return "duplicate"
    except Exception as exc:
        session.rollback()
        log.error(
            "erp_daily.backfill.persist_error",
            date=observation_date.isoformat(),
            error=str(exc),
        )
        return "error"

    return "persisted"
