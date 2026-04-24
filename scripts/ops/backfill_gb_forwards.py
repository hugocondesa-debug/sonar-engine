"""GB gilt forwards historical backfill (Sprint P.2 — 2026-04-24).

Populates :table:`yield_curves_forwards` for GB over a multi-year window
so M3 ``nominal_5y5y_history_bps`` carries ≥ 1260 business days and the
:flag:`INSUFFICIENT_HISTORY` flag stamped by
:func:`sonar.indices.monetary.m3_market_expectations.compute_m3` falls
off the GB emit.

Parent CAL: ``CAL-EXPINF-GB-FORWARDS-BACKFILL`` (Sprint Q.2 retro
sub-item). Separate ops concern from the Q.2 BEI spot-curve unblock;
this script does nominal only.

Path B (brief §2.2): Sprint Q.2's ``BoeYieldCurvesConnector`` fetches
the inflation archive only — this script relies on the Sprint P.2
extension that added
:meth:`sonar.connectors.boe_yield_curves.BoeYieldCurvesConnector.fetch_nominal_spot_curve`
over the sibling ``glcnominalddata.zip`` archive.

Flow per observation date:

1. BoE spot-curve row (8 tenors: 2Y/3Y/5Y/7Y/10Y/15Y/20Y/30Y, decimal).
2. :func:`sonar.overlays.nss.fit_nss` → :class:`NSS reduced 4-param
   fit <sonar.overlays.nss.NSSParams>` (8 obs < 9 = Svensson minimum →
   ``NSS_REDUCED`` flag).
3. :func:`derive_zero_curve` + :func:`derive_forward_curve` — populates
   the standard forward keys (``5y5y``, ``10y10y`` etc.) in
   ``forwards_json``.
4. :func:`persist_nss_fit_result` with ``source_connector="boe_glc_nominal"``
   (4-row atomic insert: spot + zero + forwards; no real leg, BoE
   nominal archive carries no linker side).

Idempotency: :class:`DuplicatePersistError` is caught per-row so
``(country, date, methodology)`` triplets already persisted by
``daily_curves`` (typically the last 1-2 trading days via TE) are
silently skipped.

Usage::

    uv run python scripts/ops/backfill_gb_forwards.py \\
        --date-start 2020-01-01 --date-end 2026-04-24

    # Preview what would be persisted without touching the DB:
    uv run python scripts/ops/backfill_gb_forwards.py --dry-run \\
        --date-start 2020-01-01 --date-end 2020-02-01
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import numpy as np
import structlog

from sonar.connectors.boe_yield_curves import BoeYieldCurvesConnector
from sonar.db.persistence import DuplicatePersistError, persist_nss_fit_result
from sonar.db.session import SessionLocal
from sonar.overlays.exceptions import ConvergenceError, InsufficientDataError
from sonar.overlays.nss import (
    NSSInput,
    assemble_nss_fit_result,
    derive_forward_curve,
    derive_zero_curve,
    fit_nss,
)

if TYPE_CHECKING:
    from sonar.connectors.boe_yield_curves import BoeNominalSpotObservation

log = structlog.get_logger()


SOURCE_CONNECTOR: str = "boe_glc_nominal"

# Canonical ordered tenor labels used to pack the BoE observation's
# decimal tenors into the NSS input arrays. Must match the connector's
# ``_DEFAULT_NOMINAL_TENORS`` so ``fetch_nominal_spot_curve`` emits all
# 8 keys.
_TENOR_LABELS_ORDERED: tuple[str, ...] = (
    "2Y",
    "3Y",
    "5Y",
    "7Y",
    "10Y",
    "15Y",
    "20Y",
    "30Y",
)

_TENOR_YEARS_ORDERED: tuple[float, ...] = (2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0)


def _parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC).date()


def _build_nss_input(obs: BoeNominalSpotObservation) -> NSSInput | None:
    """Pack a BoE observation into an :class:`NSSInput`.

    Returns ``None`` when the obs omits any of the canonical 8 tenors —
    ``fetch_nominal_spot_curve`` is supposed to emit only complete rows
    but we double-check defensively (partial rows would fail NSS
    validation anyway).
    """
    try:
        yields = np.array(
            [obs.tenors[label] for label in _TENOR_LABELS_ORDERED],
            dtype=np.float64,
        )
    except KeyError as exc:
        log.warning(
            "backfill_gb.tenor_missing",
            date=obs.observation_date.isoformat(),
            missing=str(exc),
        )
        return None
    tenors_years = np.array(_TENOR_YEARS_ORDERED, dtype=np.float64)
    return NSSInput(
        tenors_years=tenors_years,
        yields=yields,
        country_code="GB",
        observation_date=obs.observation_date,
        curve_input_type="par",
    )


def _persist_observation(
    session: object,
    obs: BoeNominalSpotObservation,
    *,
    dry_run: bool,
) -> str:
    """Fit + derive + persist one observation; return a bucket label.

    Buckets: ``"persisted"``, ``"skipped_existing"``, ``"skipped_fit"``,
    ``"dry_run"``.
    """
    nss_input = _build_nss_input(obs)
    if nss_input is None:
        return "skipped_fit"
    try:
        spot = fit_nss(nss_input)
    except (InsufficientDataError, ConvergenceError) as exc:
        log.warning(
            "backfill_gb.fit_failed",
            date=obs.observation_date.isoformat(),
            error=str(exc),
        )
        return "skipped_fit"
    zero = derive_zero_curve(spot)
    forward = derive_forward_curve(zero)
    result = assemble_nss_fit_result(
        country_code="GB",
        observation_date=obs.observation_date,
        spot=spot,
        zero=zero,
        forward=forward,
        real=None,
    )
    if dry_run:
        log.info(
            "backfill_gb.dry_run",
            date=obs.observation_date.isoformat(),
            rmse_bps=spot.rmse_bps,
            flags=list(spot.flags),
            forward_5y5y=forward.forwards.get("5y5y"),
        )
        return "dry_run"
    try:
        persist_nss_fit_result(session, result, source_connector=SOURCE_CONNECTOR)  # type: ignore[arg-type]
    except DuplicatePersistError:
        return "skipped_existing"
    return "persisted"


async def backfill_gb_forwards(
    date_start: date,
    date_end: date,
    *,
    dry_run: bool,
) -> dict[str, int]:
    """Fetch the BoE nominal archive and persist GB forwards rows.

    Returns a bucket-count summary (``persisted`` / ``skipped_existing``
    / ``skipped_fit`` / ``dry_run``).
    """
    connector = BoeYieldCurvesConnector()
    try:
        observations = await connector.fetch_nominal_spot_curve(date_start, date_end)
    finally:
        await connector.aclose()

    log.info(
        "backfill_gb.fetched",
        count=len(observations),
        date_start=date_start.isoformat(),
        date_end=date_end.isoformat(),
    )

    buckets: dict[str, int] = {
        "persisted": 0,
        "skipped_existing": 0,
        "skipped_fit": 0,
        "dry_run": 0,
    }

    session = SessionLocal() if not dry_run else None
    try:
        for obs in observations:
            bucket = _persist_observation(session, obs, dry_run=dry_run)
            buckets[bucket] = buckets.get(bucket, 0) + 1
    finally:
        if session is not None:
            session.close()
    return buckets


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill GB yield_curves_forwards rows from the BoE nominal gilt spot-curve archive."
        )
    )
    parser.add_argument(
        "--date-start",
        type=_parse_iso_date,
        required=True,
        help="ISO start date (e.g. 2020-01-01).",
    )
    parser.add_argument(
        "--date-end",
        type=_parse_iso_date,
        required=True,
        help="ISO end date (inclusive).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fit + derive per date but do not write to DB.",
    )
    args = parser.parse_args()

    buckets = asyncio.run(
        backfill_gb_forwards(args.date_start, args.date_end, dry_run=args.dry_run)
    )

    log.info(
        "backfill_gb.done",
        date_start=args.date_start.isoformat(),
        date_end=args.date_end.isoformat(),
        **buckets,
    )
    # Exit 0 on any successful run (persisted + skipped_existing), 1 if
    # zero rows landed at all (probable upstream issue).
    total_handled = buckets["persisted"] + buckets["skipped_existing"] + buckets["dry_run"]
    return 0 if total_handled > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
