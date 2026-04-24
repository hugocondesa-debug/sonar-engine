"""Sprint Q.3 — BoC CES inflation-expectations backfill CLI.

Drains the three Canadian Survey of Consumer Expectations aggregate
series (:data:`~sonar.connectors.boc.BOC_CES_SHORT_TERM` / ``MID_TERM``
/ ``LONG_TERM``) over a user-chosen window and upserts one
``exp_inflation_survey`` row per quarterly release via
:func:`persist_survey_row`.

Usage::

    uv run python -m sonar.connectors.boc_ces_backfill \\
        --date-start 2014-01-01 --date-end 2026-04-24

CES was launched 2014-Q4; earlier observations are not published.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

import structlog

from sonar.connectors.boc import BoCConnector, CESInflationExpectation
from sonar.db.session import SessionLocal
from sonar.indices.monetary.exp_inflation_writers import persist_survey_row
from sonar.overlays.exceptions import DataUnavailableError
from sonar.overlays.expected_inflation import (
    METHODOLOGY_VERSION_SURVEY,
    ExpInfSurvey,
    compute_5y5y,
)

log = structlog.get_logger()


_SURVEY_NAME: str = "BOC_CES"

# CES release latency — BoC publishes the quarterly panel approximately
# 30-60 days after quarter close. 45 days is a conservative midpoint
# used only for the schema's ``survey_release_date`` field; downstream
# consumers that care about publication latency read ``flags``.
_CES_RELEASE_LAG_DAYS: int = 45

_CONFIDENCE: float = 1.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill BoC CES inflation expectations")
    parser.add_argument("--date-start", type=_parse_date, required=True)
    parser.add_argument("--date-end", type=_parse_date, required=True)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/cache"),
        help="L0 connector cache root (default: data/cache).",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run(args.date_start, args.date_end, args.cache_dir))


async def _run(date_start: date, date_end: date, cache_dir: Path) -> int:
    connector = BoCConnector(cache_dir=cache_dir)
    inserted_total = 0
    fetched_total = 0
    failed_total = 0
    try:
        try:
            releases = await connector.fetch_ces_inflation_expectations(
                date_start,
                date_end,
            )
        except DataUnavailableError as exc:
            log.error(
                "boc_ces_backfill.fetch_failed",
                start=date_start.isoformat(),
                end=date_end.isoformat(),
                error=str(exc),
            )
            return 1

        with SessionLocal() as session:
            for release in releases:
                fetched_total += 1
                survey = _release_to_expinfsurvey(release)
                try:
                    inserted = persist_survey_row(
                        session,
                        survey,
                        methodology_version=METHODOLOGY_VERSION_SURVEY,
                    )
                except Exception as exc:
                    log.warning(
                        "boc_ces_backfill.persist_error",
                        release_date=release.release_date.isoformat(),
                        error=str(exc),
                    )
                    failed_total += 1
                    continue
                inserted_total += int(inserted)
            session.commit()
    finally:
        await connector.aclose()

    log.info(
        "boc_ces_backfill.done",
        fetched=fetched_total,
        inserted=inserted_total,
        failed=failed_total,
    )
    return 0 if fetched_total > 0 else 1


def _release_to_expinfsurvey(release: CESInflationExpectation) -> ExpInfSurvey:
    """Map a CES release into :class:`ExpInfSurvey` with canonical tenors.

    CES publishes 1Y / 2Y / 5Y horizons. Mapping:

    * ``1Y`` / ``2Y`` / ``5Y`` — direct from release horizons.
    * ``3Y`` — linear interp between 2Y + 5Y when both present.
    * ``10Y`` / ``5y5y`` / ``30Y`` — set to 5Y value with
      ``CES_LT_AS_ANCHOR`` flag (analogous to Sprint Q.1's
      ``SPF_LT_AS_ANCHOR`` — BoC CES does not publish a 10Y horizon;
      5Y serves as the flat long-run anchor).

    Values converted from % to decimal.
    """
    pct = release.horizons_pct
    horizons_dec = {k: v / 100.0 for k, v in pct.items()}
    interpolated: dict[str, float] = dict(horizons_dec)
    if "2Y" in horizons_dec and "5Y" in horizons_dec:
        span_years = 5.0 - 2.0
        per_year = (horizons_dec["5Y"] - horizons_dec["2Y"]) / span_years
        interpolated.setdefault("3Y", horizons_dec["2Y"] + per_year)

    flags: list[str] = []
    if "5Y" in horizons_dec:
        lt = horizons_dec["5Y"]
        interpolated.setdefault("10Y", lt)
        interpolated.setdefault("5y5y", lt)
        interpolated.setdefault("30Y", lt)
        flags.append("CES_LT_AS_ANCHOR")
        if "10Y" in interpolated and "5Y" in interpolated and interpolated["10Y"] != lt:
            interpolated["5y5y"] = compute_5y5y(interpolated["5Y"], interpolated["10Y"])

    return ExpInfSurvey(
        country_code="CA",
        observation_date=release.release_date,
        survey_name=_SURVEY_NAME,
        survey_release_date=release.release_date + timedelta(days=_CES_RELEASE_LAG_DAYS),
        horizons=horizons_dec,
        interpolated_tenors=interpolated,
        confidence=_CONFIDENCE,
        flags=tuple(flags),
    )


def _parse_date(raw: str) -> date:
    return date.fromisoformat(raw)


if __name__ == "__main__":
    sys.exit(main())
