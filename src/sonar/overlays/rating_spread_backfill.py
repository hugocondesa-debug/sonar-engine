"""TE-driven rating-spread backfill orchestrator (Sprint 4 + Sprint 6).

Flat sibling of :mod:`sonar.overlays.rating_spread` (compute-only
module shipped Week 3). Sprint 4 ships the data layer: TE Premium
``/ratings`` (current snapshot) + ``/ratings/historical/{country}``
(per-country archive) → ``ratings_agency_raw`` →
:func:`sonar.overlays.rating_spread.consolidate` →
``ratings_consolidated`` + ``ratings_spread_calibration`` seeded from
the ``APRIL_2026_CALIBRATION`` anchor table.

Cohort scope: 15 sovereign Tier 1 countries.

- Sprint 4 (2026-04-25): 10 países —
  US / DE / FR / IT / ES / PT / GB / JP / CA / AU.
- Sprint 6 (2026-04-26): +5 países —
  NL / NZ / CH / SE / NO (CAL-RATING-COHORT-EXPANSION closed).

EA aggregate excluded — sovereign rating agencies rate individual
issuers, not currency-union aggregates. DK deferred Phase 5+
(T2 per ``country_tiers.yaml``; ADR-0010 strict T1-ONLY enforcement
through Phase 4) — see CAL-RATING-DK-PHASE5 candidate in Sprint 6
retrospective §9.

Idempotent via UNIQUE constraints on all 3 target tables — re-running
is safe; rows already persisted are skipped at row level.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, date as date_t, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog
from sqlalchemy import func

from sonar.db.models import (
    RatingsAgencyRaw,
    RatingsConsolidated,
    RatingsSpreadCalibration,
)
from sonar.overlays.exceptions import InsufficientDataError
from sonar.overlays.rating_spread import (
    AGENCY_LOOKUP,
    APRIL_2026_CALIBRATION,
    METHODOLOGY_VERSION_AGENCY,
    METHODOLOGY_VERSION_CALIBRATION,
    METHODOLOGY_VERSION_CONSOLIDATED,
    MODIFIER_OUTLOOK,
    MODIFIER_WATCH,
    RatingAgencyRaw,
    consolidate,
    lookup_default_spread_bps,
    notch_to_grade,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from sonar.connectors.te import (
        TEConnector,
        TERatingCurrent,
        TERatingHistoricalAction,
    )

log = structlog.get_logger()

__all__ = [
    "CALIBRATION_DATE_APRIL_2026",
    "CALIBRATION_SOURCE_LABEL",
    "TE_COUNTRY_OVERRIDES_TIER1",
    "TIER1_COUNTRIES",
    "TIER1_ISO_TO_TE_NAME",
    "TERatingsBackfillResult",
    "backfill_calibration_april_2026",
    "backfill_consolidate",
    "backfill_te_current_snapshot",
    "backfill_te_historical",
]


# ---------------------------------------------------------------------------
# Tier 1 cohort + TE-name <-> ISO alpha-2 manual mapping
# (Sprint 4 = 10 países; Sprint 6 = +5 sparse — closes CAL-RATING-COHORT-EXPANSION)
# ---------------------------------------------------------------------------

TIER1_COUNTRIES: tuple[str, ...] = (
    # Sprint 4 cohort (2026-04-25)
    "US",
    "DE",
    "FR",
    "IT",
    "ES",
    "PT",
    "GB",
    "JP",
    "CA",
    "AU",
    # Sprint 6 expansion (2026-04-26)
    "NL",
    "NZ",
    "CH",
    "SE",
    "NO",
)

# TE-canonical country name -> ISO alpha-2. Sprint 4 entries verified
# empirically against the live ``/ratings`` snapshot 2026-04-25.
# Sprint 6 entries verified 2026-04-26 — TE returns canonical English
# country names (single word for NL/CH/SE/NO; "New Zealand" 2-word
# capitalised matching the Sprint 4 ``United States`` /
# ``United Kingdom`` pattern). DK deferred Phase 5+ per ADR-0010.
TE_COUNTRY_OVERRIDES_TIER1: dict[str, str] = {
    # Sprint 4 cohort
    "United States": "US",
    "Germany": "DE",
    "France": "FR",
    "Italy": "IT",
    "Spain": "ES",
    "Portugal": "PT",
    "United Kingdom": "GB",
    "Japan": "JP",
    "Canada": "CA",
    "Australia": "AU",
    # Sprint 6 expansion
    "Netherlands": "NL",
    "New Zealand": "NZ",
    "Switzerland": "CH",
    "Sweden": "SE",
    "Norway": "NO",
}

TIER1_ISO_TO_TE_NAME: dict[str, str] = {
    iso: name for name, iso in TE_COUNTRY_OVERRIDES_TIER1.items()
}

# TE-native agency strings → SONAR canonical codes. TE returns ``S&P``
# / ``Moody's`` / ``Fitch`` / ``DBRS`` in the historical endpoint
# (verified 2026-04-25 Portugal sample).
_TE_AGENCY_NORMALIZE: dict[str, str] = {
    "S&P": "SP",
    "S&P Global Ratings": "SP",
    "SP": "SP",
    "Moody's": "MOODYS",
    "Moodys": "MOODYS",
    "MOODYS": "MOODYS",
    "Fitch": "FITCH",
    "Fitch Ratings": "FITCH",
    "FITCH": "FITCH",
    "DBRS": "DBRS",
    "DBRS Morningstar": "DBRS",
}


# ---------------------------------------------------------------------------
# Helpers (testable in isolation)
# ---------------------------------------------------------------------------


def _te_country_to_iso(te_name: str) -> str | None:
    return TE_COUNTRY_OVERRIDES_TIER1.get(te_name.strip())


def _normalize_te_agency(te_agency: str) -> str | None:
    return _TE_AGENCY_NORMALIZE.get(te_agency.strip())


def _parse_te_outlook(outlook_raw: str) -> tuple[str, str | None]:
    """Parse TE outlook string into ``(outlook, watch)``.

    Empirically observed inputs (2026-04-25 audit): ``"Stable"``,
    ``"Positive"``, ``"Negative"``, ``"Negative Watch"``,
    ``"Stable Watch"``, ``"N/A"``, empty.

    Outputs:
      outlook ∈ {``"positive"``, ``"stable"``, ``"negative"``, ``"developing"``}
      watch   ∈ {``"watch_positive"``, ``"watch_negative"``,
                 ``"watch_developing"``, ``None``}

    Ambiguous / empty / ``"N/A"`` defaults to ``("stable", None)``.
    """
    raw = (outlook_raw or "").strip().lower()
    if not raw or raw == "n/a":
        return ("stable", None)

    watch: str | None = None
    if "watch" in raw:
        if "positive" in raw:
            watch = "watch_positive"
        elif "negative" in raw:
            watch = "watch_negative"
        elif "developing" in raw:
            watch = "watch_developing"
        residual = raw.replace("watch", "").strip()
    else:
        residual = raw

    if "positive" in residual:
        outlook = "positive"
    elif "negative" in residual:
        outlook = "negative"
    elif "developing" in residual:
        outlook = "developing"
    else:
        outlook = "stable"

    return (outlook, watch)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TERatingsBackfillResult:
    """Aggregate counters across one or more backfill phases."""

    agency_raw_persisted: int = 0
    agency_raw_skipped_existing: int = 0
    agency_raw_skipped_invalid: int = 0
    consolidated_persisted: int = 0
    consolidated_skipped_existing: int = 0
    consolidated_skipped_insufficient: int = 0
    countries_processed: int = 0
    countries_unmappable: int = 0
    historical_actions_fetched: int = 0
    historical_actions_persisted: int = 0
    calibration_persisted: int = 0


# ---------------------------------------------------------------------------
# Persist helper (idempotent insert into ratings_agency_raw)
# ---------------------------------------------------------------------------


def _insert_agency_row_if_absent(
    session: Session,
    *,
    rating_id: str,
    country_iso: str,
    obs_date: date_t,
    agency: str,
    rating_raw: str,
    sonar_notch_base: int,
    notch_adjusted: float,
    outlook: str,
    watch: str | None,
    action_date: date_t,
    confidence: float,
    flags: str | None,
    source_connector: str = "te",
) -> bool:
    """Insert one ratings_agency_raw row. Returns ``True`` iff new."""
    existing = (
        session.query(RatingsAgencyRaw.id)
        .filter_by(
            country_code=country_iso,
            date=obs_date,
            agency=agency,
            rating_type="FC",
            methodology_version=METHODOLOGY_VERSION_AGENCY,
        )
        .first()
    )
    if existing is not None:
        return False

    session.add(
        RatingsAgencyRaw(
            rating_id=rating_id,
            country_code=country_iso,
            date=obs_date,
            agency=agency,
            rating_type="FC",
            rating_raw=rating_raw,
            sonar_notch_base=sonar_notch_base,
            notch_adjusted=notch_adjusted,
            outlook=outlook,
            watch=watch,
            action_date=action_date,
            source_connector=source_connector,
            methodology_version=METHODOLOGY_VERSION_AGENCY,
            confidence=confidence,
            flags=flags,
        )
    )
    return True


# ---------------------------------------------------------------------------
# Step A+B: current-snapshot backfill
# ---------------------------------------------------------------------------


async def backfill_te_current_snapshot(
    session: Session,
    *,
    te_connector: TEConnector,
    countries: tuple[str, ...] = TIER1_COUNTRIES,
    snapshot_date: date_t | None = None,
) -> TERatingsBackfillResult:
    """Fetch ``/ratings`` snapshot and persist agency_raw rows.

    Filters to ``countries`` (Sprint 4 default = TIER1 10 sovereigns).
    EA aggregate excluded by construction. Per-country rating_id is
    a fresh UUID4 — :func:`backfill_consolidate` later harmonises
    sibling rating_ids to the consolidated row's UUID.
    """
    if snapshot_date is None:
        snapshot_date = datetime.now(tz=UTC).date()

    snapshot: list[TERatingCurrent] = await te_connector.fetch_sovereign_ratings_current()

    persisted = 0
    skipped_existing = 0
    skipped_invalid = 0
    countries_processed = 0
    countries_unmappable = 0
    cohort = set(countries)

    for row in snapshot:
        country_iso = _te_country_to_iso(row.country)
        if country_iso is None:
            countries_unmappable += 1
            continue
        if country_iso not in cohort:
            continue
        countries_processed += 1

        rating_id = uuid4().hex

        for agency_code, rating_raw, outlook_raw in (
            ("SP", row.sp_rating, row.sp_outlook),
            ("MOODYS", row.moodys_rating, row.moodys_outlook),
            ("FITCH", row.fitch_rating, row.fitch_outlook),
            ("DBRS", row.dbrs_rating, row.dbrs_outlook),
        ):
            if not rating_raw:
                continue

            try:
                base_notch = AGENCY_LOOKUP[agency_code][rating_raw]  # type: ignore[index]
            except KeyError:
                log.warning(
                    "te.snapshot.invalid_token",
                    country=country_iso,
                    agency=agency_code,
                    rating_raw=rating_raw,
                )
                skipped_invalid += 1
                continue

            outlook, watch = _parse_te_outlook(outlook_raw)
            outlook_mod = MODIFIER_OUTLOOK.get(outlook, 0.0)
            watch_mod = MODIFIER_WATCH.get(watch, 0.0) if watch else 0.0
            notch_adjusted = float(base_notch) + outlook_mod + watch_mod

            written = _insert_agency_row_if_absent(
                session,
                rating_id=rating_id,
                country_iso=country_iso,
                obs_date=snapshot_date,
                agency=agency_code,
                rating_raw=rating_raw,
                sonar_notch_base=base_notch,
                notch_adjusted=notch_adjusted,
                outlook=outlook,
                watch=watch,
                action_date=snapshot_date,
                confidence=0.85,
                flags=None,
            )
            if written:
                persisted += 1
            else:
                skipped_existing += 1

    session.commit()
    log.info(
        "rating_spread.backfill.snapshot",
        persisted=persisted,
        skipped_existing=skipped_existing,
        skipped_invalid=skipped_invalid,
        countries_processed=countries_processed,
        countries_unmappable=countries_unmappable,
    )

    return TERatingsBackfillResult(
        agency_raw_persisted=persisted,
        agency_raw_skipped_existing=skipped_existing,
        agency_raw_skipped_invalid=skipped_invalid,
        countries_processed=countries_processed,
        countries_unmappable=countries_unmappable,
    )


# ---------------------------------------------------------------------------
# Step C+D: historical-archive backfill
# ---------------------------------------------------------------------------


async def backfill_te_historical(
    session: Session,
    *,
    te_connector: TEConnector,
    countries: tuple[str, ...] = TIER1_COUNTRIES,
    delay_seconds: float = 0.5,
) -> TERatingsBackfillResult:
    """Fetch ``/ratings/historical/{country}`` per cohort, persist actions.

    Sequential per country with optional ``delay_seconds`` gap to
    soften TE Premium rate limits. The 7d connector cache makes
    re-runs cheap (one HTTP call per country per week).

    ``BACKFILL_STALE`` flag set on rows with ``action_date <
    2023-01-01`` per spec §2 v0.2 source-selection note (pre-2023 is
    Damodaran-historical territory; TE archive coverage is the
    Sprint 4 stop-gap).
    """
    fetched = 0
    persisted = 0
    skipped_existing = 0
    skipped_invalid = 0
    countries_processed = 0

    for country_iso in countries:
        te_name = TIER1_ISO_TO_TE_NAME.get(country_iso)
        if te_name is None:
            log.warning("te.historical.no_te_name", country=country_iso)
            continue
        countries_processed += 1

        actions: list[
            TERatingHistoricalAction
        ] = await te_connector.fetch_sovereign_ratings_historical(te_name)
        fetched += len(actions)

        for action in actions:
            agency_code = _normalize_te_agency(action.agency)
            if agency_code is None:
                log.warning(
                    "te.historical.unknown_agency",
                    country=country_iso,
                    agency_te=action.agency,
                )
                skipped_invalid += 1
                continue

            try:
                base_notch = AGENCY_LOOKUP[agency_code][action.rating_raw]  # type: ignore[index]
            except KeyError:
                log.warning(
                    "te.historical.invalid_token",
                    country=country_iso,
                    agency=agency_code,
                    rating_raw=action.rating_raw,
                )
                skipped_invalid += 1
                continue

            outlook, watch = _parse_te_outlook(action.outlook)
            outlook_mod = MODIFIER_OUTLOOK.get(outlook, 0.0)
            watch_mod = MODIFIER_WATCH.get(watch, 0.0) if watch else 0.0
            notch_adjusted = float(base_notch) + outlook_mod + watch_mod

            flags = "BACKFILL_STALE" if action.action_date < date_t(2023, 1, 1) else None

            written = _insert_agency_row_if_absent(
                session,
                rating_id=uuid4().hex,
                country_iso=country_iso,
                obs_date=action.action_date,
                agency=agency_code,
                rating_raw=action.rating_raw,
                sonar_notch_base=base_notch,
                notch_adjusted=notch_adjusted,
                outlook=outlook,
                watch=watch,
                action_date=action.action_date,
                confidence=0.85,
                flags=flags,
            )
            if written:
                persisted += 1
            else:
                skipped_existing += 1

        session.commit()
        if delay_seconds:
            await asyncio.sleep(delay_seconds)

    log.info(
        "rating_spread.backfill.historical",
        countries_processed=countries_processed,
        fetched=fetched,
        persisted=persisted,
        skipped_existing=skipped_existing,
        skipped_invalid=skipped_invalid,
    )

    return TERatingsBackfillResult(
        agency_raw_persisted=persisted,
        agency_raw_skipped_existing=skipped_existing,
        agency_raw_skipped_invalid=skipped_invalid,
        countries_processed=countries_processed,
        historical_actions_fetched=fetched,
        historical_actions_persisted=persisted,
    )


# ---------------------------------------------------------------------------
# Step E+F: consolidate per (country, date, rating_type)
# ---------------------------------------------------------------------------


def backfill_consolidate(session: Session) -> TERatingsBackfillResult:
    """Run :func:`consolidate` for each ``(country, date, rating_type)``
    tuple with ≥ 1 agency_raw row, persist consolidated row, and
    harmonise sibling agency_raw ``rating_id`` to the consolidated
    row's UUID per spec §3 sibling-correlation contract.

    Single-agency tuples are persisted with ``RATING_SINGLE_AGENCY``
    flag (cap confidence 0.60 — handled inside ``consolidate()``).
    """
    candidates = (
        session.query(
            RatingsAgencyRaw.country_code,
            RatingsAgencyRaw.date,
            RatingsAgencyRaw.rating_type,
            func.count().label("n_agencies"),
        )
        .filter(RatingsAgencyRaw.methodology_version == METHODOLOGY_VERSION_AGENCY)
        .group_by(
            RatingsAgencyRaw.country_code,
            RatingsAgencyRaw.date,
            RatingsAgencyRaw.rating_type,
        )
        .all()
    )

    persisted = 0
    skipped_existing = 0
    skipped_insufficient = 0

    for country_iso, obs_date, rating_type, _n_agencies in candidates:
        existing = (
            session.query(RatingsConsolidated.id)
            .filter_by(
                country_code=country_iso,
                date=obs_date,
                rating_type=rating_type,
                methodology_version=METHODOLOGY_VERSION_CONSOLIDATED,
            )
            .first()
        )
        if existing is not None:
            skipped_existing += 1
            continue

        rows = (
            session.query(RatingsAgencyRaw)
            .filter_by(
                country_code=country_iso,
                date=obs_date,
                rating_type=rating_type,
                methodology_version=METHODOLOGY_VERSION_AGENCY,
            )
            .all()
        )

        agency_inputs = [
            RatingAgencyRaw(
                agency=row.agency,  # type: ignore[arg-type]
                rating_raw=row.rating_raw,
                rating_type=row.rating_type,  # type: ignore[arg-type]
                base_notch=row.sonar_notch_base,
                notch_adjusted=row.notch_adjusted,
                outlook=row.outlook,  # type: ignore[arg-type]
                watch=row.watch,  # type: ignore[arg-type]
                action_date=row.action_date,
            )
            for row in rows
        ]

        try:
            consolidated = consolidate(
                agency_inputs,
                country_code=country_iso,
                observation_date=obs_date,
                rating_type=rating_type,
            )
        except InsufficientDataError:
            skipped_insufficient += 1
            continue

        shared_rating_id = consolidated.rating_id.hex
        for r in rows:
            r.rating_id = shared_rating_id

        cal_row = (
            session.query(RatingsSpreadCalibration)
            .filter(
                RatingsSpreadCalibration.calibration_date <= obs_date,
                RatingsSpreadCalibration.methodology_version == METHODOLOGY_VERSION_CALIBRATION,
            )
            .order_by(RatingsSpreadCalibration.calibration_date.desc())
            .first()
        )
        calibration_date = cal_row.calibration_date if cal_row is not None else None

        session.add(
            RatingsConsolidated(
                rating_id=shared_rating_id,
                country_code=country_iso,
                date=obs_date,
                rating_type=rating_type,
                consolidated_sonar_notch=consolidated.consolidated_sonar_notch,
                notch_fractional=consolidated.notch_fractional,
                agencies_count=consolidated.agencies_count,
                agencies_json=json.dumps(consolidated.agencies),
                outlook_composite=consolidated.outlook_composite,
                watch_composite=consolidated.watch_composite,
                default_spread_bps=consolidated.default_spread_bps,
                calibration_date=calibration_date,
                rating_cds_deviation_pct=None,
                methodology_version=METHODOLOGY_VERSION_CONSOLIDATED,
                confidence=consolidated.confidence,
                flags=",".join(consolidated.flags) if consolidated.flags else None,
            )
        )
        persisted += 1

    session.commit()
    log.info(
        "rating_spread.backfill.consolidate",
        persisted=persisted,
        skipped_existing=skipped_existing,
        skipped_insufficient=skipped_insufficient,
    )

    return TERatingsBackfillResult(
        consolidated_persisted=persisted,
        consolidated_skipped_existing=skipped_existing,
        consolidated_skipped_insufficient=skipped_insufficient,
    )


# ---------------------------------------------------------------------------
# Step G: calibration seed (APRIL_2026 anchors + interpolated fill)
# ---------------------------------------------------------------------------

CALIBRATION_DATE_APRIL_2026: date_t = date_t(2026, 4, 1)
CALIBRATION_SOURCE_LABEL: str = "APRIL_2026_CALIBRATION (placeholder)"


def backfill_calibration_april_2026(session: Session) -> int:
    """Seed ``ratings_spread_calibration`` with 22 rows (notches 0-21).

    Anchors at notches {0, 3, 6, 9, 12, 15, 18, 21} from the in-code
    ``APRIL_2026_CALIBRATION`` constant (spec §4 line 147 — placeholders,
    recalibrate quarterly). Non-anchor notches use the existing linear
    interpolation in :func:`lookup_default_spread_bps`; ``range_low_bps``
    + ``range_high_bps`` populated only on anchor rows (interpolated
    rows store ``NULL`` for the percentile bands).
    """
    persisted = 0
    for notch_int in range(22):
        existing = (
            session.query(RatingsSpreadCalibration.id)
            .filter_by(
                calibration_date=CALIBRATION_DATE_APRIL_2026,
                sonar_notch_int=notch_int,
                methodology_version=METHODOLOGY_VERSION_CALIBRATION,
            )
            .first()
        )
        if existing is not None:
            continue

        anchor = APRIL_2026_CALIBRATION.get(notch_int)
        if anchor is not None:
            spread_bps, grade, p25, p75 = anchor
            spread_value: int | None = spread_bps if notch_int > 0 else None
            range_low: int | None = p25 if notch_int > 0 else None
            range_high: int | None = p75 if notch_int > 0 else None
        else:
            grade = notch_to_grade(notch_int)
            spread_value = lookup_default_spread_bps(notch_int)
            range_low = None
            range_high = None

        session.add(
            RatingsSpreadCalibration(
                calibration_date=CALIBRATION_DATE_APRIL_2026,
                sonar_notch_int=notch_int,
                rating_equivalent=grade,
                default_spread_bps=spread_value,
                range_low_bps=range_low,
                range_high_bps=range_high,
                moodys_pd_5y_pct=None,
                calibration_source=CALIBRATION_SOURCE_LABEL,
                methodology_version=METHODOLOGY_VERSION_CALIBRATION,
            )
        )
        persisted += 1

    session.commit()
    log.info("rating_spread.backfill.calibration", persisted=persisted)
    return persisted
