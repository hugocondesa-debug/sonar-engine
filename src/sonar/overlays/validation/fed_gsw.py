"""Fed GSW (Gurkaynak-Sack-Wright) cross-validation canary.

Reference: https://www.federalreserve.gov/data/nominal-yield-curve.htm
Static snapshot of feds200628.csv covers a single business day. Compares the
published zero curve (SVENY01..SVENY30) against SONAR NSS spot output at the
same tenors and reports per-tenor deviation in basis points.

Spec §7 cross-validation target for US: <10 bps vs Fed GSW. Spec §6 row 5
emits ``XVAL_DRIFT`` when ``|deviation| > target``; we flag at the
spec §7 default 10 bps threshold.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import date as date_type
    from pathlib import Path

    from sonar.overlays.nss import SpotCurve

# Spec §7 us_2024_01_02 cross-validation target: 10 bps deviation per tenor.
FED_GSW_XVAL_THRESHOLD_BPS: float = 10.0

# Default tenors from spec §7 + brief §3PM-3 (canonical xval points).
DEFAULT_XVAL_TENORS_YEARS: tuple[int, ...] = (2, 5, 10, 30)


@dataclass(frozen=True, slots=True)
class GSWReference:
    """Single-day Fed GSW reference parsed from feds200628.csv.

    ``zero_yields`` keyed by tenor in integer years (1..30); values are
    decimal (0.0395 = 3.95%). Tenors with NA values are dropped.
    """

    observation_date: date_type
    zero_yields: dict[int, float]
    beta_0: float
    beta_1: float
    beta_2: float
    beta_3: float
    tau_1: float
    tau_2: float


def parse_feds200628_csv(path: Path, target_date: date_type) -> GSWReference:
    """Parse a single row of the Fed feds200628.csv snapshot.

    Skips the leading note + metadata block; reads the canonical header
    starting with ``Date,BETA0,BETA1,...`` and locates the row for
    ``target_date``. Yields are stored in the file as percent (3.95 for
    3.95%); we convert to decimal.
    """
    with path.open(newline="") as fh:
        reader = csv.reader(fh)
        header: list[str] | None = None
        for row in reader:
            if row and row[0] == "Date":
                header = row
                break
        if header is None:
            msg = f"feds200628.csv at {path}: header row 'Date,BETA0,...' not found"
            raise ValueError(msg)

        target_iso = target_date.isoformat()
        for row in reader:
            if row and row[0] == target_iso:
                return _row_to_reference(header, row, target_date)
    msg = f"feds200628.csv at {path}: no row for {target_iso}"
    raise ValueError(msg)


def _row_to_reference(header: list[str], row: list[str], target_date: date_type) -> GSWReference:
    cells = dict(zip(header, row, strict=True))
    zero_yields: dict[int, float] = {}
    for years in range(1, 31):
        key = f"SVENY{years:02d}"
        raw = cells.get(key, "NA")
        if raw in {"", "NA"}:
            continue
        zero_yields[years] = float(raw) / 100.0  # percent → decimal

    return GSWReference(
        observation_date=target_date,
        zero_yields=zero_yields,
        beta_0=float(cells["BETA0"]) / 100.0,
        beta_1=float(cells["BETA1"]) / 100.0,
        beta_2=float(cells["BETA2"]) / 100.0,
        beta_3=float(cells["BETA3"]) / 100.0,
        tau_1=float(cells["TAU1"]),
        tau_2=float(cells["TAU2"]),
    )


def compare_to_gsw(
    spot: SpotCurve,
    reference: GSWReference,
    tenors_years: Iterable[int] = DEFAULT_XVAL_TENORS_YEARS,
) -> dict[int, float]:
    """Return ``{tenor_years: |sonar - gsw|_bps}`` for the requested tenors.

    SpotCurve.fitted_yields are keyed by canonical labels (e.g. ``"10Y"``);
    we map integer tenors to those labels.
    """
    deviations: dict[int, float] = {}
    for tenor in tenors_years:
        label = f"{tenor}Y"
        if label not in spot.fitted_yields:
            continue
        if tenor not in reference.zero_yields:
            continue
        sonar = spot.fitted_yields[label]
        gsw = reference.zero_yields[tenor]
        deviations[tenor] = abs(sonar - gsw) * 10_000.0
    return deviations
