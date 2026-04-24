"""Sprint Q.3 — BoJ Tankan inflation-outlook backfill CLI.

Drains quarterly :class:`~sonar.connectors.boj_tankan.TankanInflationOutlook`
releases over a user-chosen window and upserts them into
``exp_inflation_survey`` via :func:`persist_survey_row`.

Usage::

    uv run python -m sonar.connectors.boj_tankan_backfill \\
        --date-start 2020-01-01 --date-end 2026-04-24

Releases pre-March 2020 are intentionally skipped — standalone bukka
PDFs (pre-integration) require a separate scrape sprint
(`CAL-EXPINF-JP-SCRAPE-PRE2020`).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

import structlog

from sonar.connectors.boj_tankan import BoJTankanConnector, TankanInflationOutlook
from sonar.db.session import SessionLocal
from sonar.indices.monetary.exp_inflation_writers import persist_survey_row
from sonar.overlays.exceptions import DataUnavailableError
from sonar.overlays.expected_inflation import (
    METHODOLOGY_VERSION_SURVEY,
    ExpInfSurvey,
    compute_5y5y,
)

log = structlog.get_logger()


# Tankan inflation outlook integrated into the TANKAN Summary from the
# March 2020 release, but the scriptable ZIP format only starts with
# the March 2021 release (March 2020 through December 2020 are
# PDF-only in the older 5-year bucket). Pre-2021 data is out of scope
# for Sprint Q.3; ``CAL-EXPINF-JP-SCRAPE-PRE2020`` covers the Week 12+
# PDF scrape.
_FIRST_INTEGRATED_YEAR: int = 2021
_FIRST_INTEGRATED_MONTH: int = 3

# BoC policy inflation target at 2% midpoint of the 1-3% control range
# — used only as a convention anchor; not consumed by the M3 survey
# path (which reads from the NSS forwards + survey 5y5y separately).
_SURVEY_NAME: str = "BOJ_TANKAN"

# Confidence floor for persisted rows. Kept aligned with the Sprint
# Q.1 SPF default (1.0) so the M3 classifier accepts the row without
# sub-threshold degradation; the sparsity-reason flag
# ``JP_M3_BEI_LINKER_THIN_EXPECTED`` is still emitted downstream for
# observability.
_CONFIDENCE: float = 1.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill BoJ Tankan inflation outlook")
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
    releases = list(_enumerate_releases(date_start, date_end))
    if not releases:
        log.warning(
            "boj_tankan_backfill.no_releases_in_window",
            start=date_start.isoformat(),
            end=date_end.isoformat(),
        )
        return 0

    connector = BoJTankanConnector(cache_dir=cache_dir)
    inserted_total = 0
    fetched_total = 0
    failed_total = 0
    try:
        with SessionLocal() as session:
            for year, month in releases:
                try:
                    outlook = await connector.fetch_release(year, month)
                except DataUnavailableError as exc:
                    log.warning(
                        "boj_tankan_backfill.release_unavailable",
                        year=year,
                        month=month,
                        error=str(exc),
                    )
                    failed_total += 1
                    continue
                fetched_total += 1
                survey = _outlook_to_expinfsurvey(outlook)
                try:
                    inserted = persist_survey_row(
                        session,
                        survey,
                        methodology_version=METHODOLOGY_VERSION_SURVEY,
                    )
                except Exception as exc:
                    log.warning(
                        "boj_tankan_backfill.persist_error",
                        year=year,
                        month=month,
                        error=str(exc),
                    )
                    failed_total += 1
                    continue
                inserted_total += int(inserted)
            session.commit()
    finally:
        await connector.aclose()

    log.info(
        "boj_tankan_backfill.done",
        releases_in_window=len(releases),
        fetched=fetched_total,
        inserted=inserted_total,
        failed=failed_total,
    )
    return 0 if fetched_total > 0 else 1


def _enumerate_releases(date_start: date, date_end: date) -> list[tuple[int, int]]:
    """Quarter-end-month releases (3/6/9/12) intersecting [start, end].

    The Tankan survey's reference period is the quarter ending in the
    given month; the release is published ~1-2 weeks into the
    following month. A release is considered part of the window when
    its reference month (first-of-month) lies at/after ``date_start``
    and at/before ``date_end`` — matches the CLI's "what data is
    analytically relevant" intent rather than a publication-date
    filter.
    """
    out: list[tuple[int, int]] = []
    for year in range(date_start.year, date_end.year + 1):
        for month in (3, 6, 9, 12):
            ref = date(year, month, 1)
            if ref < date(_FIRST_INTEGRATED_YEAR, _FIRST_INTEGRATED_MONTH, 1):
                continue
            if ref < date_start or ref > date_end:
                continue
            out.append((year, month))
    return out


def _outlook_to_expinfsurvey(outlook: TankanInflationOutlook) -> ExpInfSurvey:
    """Map a Tankan outlook into :class:`ExpInfSurvey` with canonical tenors.

    Tankan publishes 1Y / 3Y / 5Y horizons. The survey path in the M3
    builder requires ``interpolated_tenors["5y5y"]`` (mandatory) and
    reads ``10Y`` when present. Mapping:

    * ``1Y`` / ``3Y`` / ``5Y`` — direct from Tankan horizons.
    * ``2Y`` — linear interp between 1Y + 3Y when both present.
    * ``10Y`` / ``5y5y`` / ``30Y`` — all set to the 5Y value with the
      ``TANKAN_LT_AS_ANCHOR`` flag emitted (analogous to Sprint Q.1's
      ``SPF_LT_AS_ANCHOR`` pattern; BoJ does not publish a 10Y-equivalent
      horizon so the 5Y serves as the flat long-run anchor).

    All decimals (values converted from % by /100).
    """
    pct = outlook.horizons_pct
    horizons_dec = {k: v / 100.0 for k, v in pct.items()}
    interpolated: dict[str, float] = dict(horizons_dec)
    if "1Y" in horizons_dec and "3Y" in horizons_dec:
        interpolated.setdefault(
            "2Y",
            horizons_dec["1Y"] + (horizons_dec["3Y"] - horizons_dec["1Y"]) / 2.0,
        )
    flags: list[str] = []
    if "5Y" in horizons_dec:
        lt = horizons_dec["5Y"]
        interpolated.setdefault("10Y", lt)
        interpolated.setdefault("5y5y", lt)
        interpolated.setdefault("30Y", lt)
        flags.append("TANKAN_LT_AS_ANCHOR")
        # Preserve 5Y/10Y identity when both surfaced explicitly.
        if "10Y" in interpolated and "5Y" in interpolated and interpolated["10Y"] != lt:
            interpolated["5y5y"] = compute_5y5y(interpolated["5Y"], interpolated["10Y"])

    release_month_end = outlook.release_quarter_end_month
    # The Tankan is published within the first two weeks after the
    # reference quarter closes. Use the 1st of the following month as
    # a conservative release-date anchor — the schema only requires a
    # plausible date for the unique constraint; downstream consumers
    # that care about publication latency read ``flags`` instead.
    release_year = outlook.release_year
    release_month = release_month_end + 1
    if release_month == 13:
        release_year += 1
        release_month = 1
    survey_release_date = date(release_year, release_month, 1)

    return ExpInfSurvey(
        country_code="JP",
        observation_date=outlook.reference_date,
        survey_name=_SURVEY_NAME,
        survey_release_date=survey_release_date,
        horizons=horizons_dec,
        interpolated_tenors=interpolated,
        confidence=_CONFIDENCE,
        flags=tuple(flags),
    )


def _parse_date(raw: str) -> date:
    return date.fromisoformat(raw)


if __name__ == "__main__":
    sys.exit(main())
