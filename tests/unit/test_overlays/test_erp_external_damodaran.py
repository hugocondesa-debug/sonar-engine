"""Sprint 3.1 — fixture tests for the Damodaran external-reference writer.

Hermetic: synthesises ``DamodaranMonthlyERPRow`` instances directly,
no live fetch against ``pages.stern.nyu.edu``. Validates the
:func:`build_damodaran_external_row` contract:

* Canonical happy path (Jan 2024) — bps + columns wired correctly.
* Invalid implied-ERP (NaN) — raises ``InsufficientDataError``.
* Recent freshness (Dec 2025) — confirms the writer accepts
  end-of-history snapshots.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from sonar.connectors.damodaran import DamodaranMonthlyERPRow
from sonar.overlays.erp_external.damodaran import build_damodaran_external_row
from sonar.overlays.exceptions import InsufficientDataError


def _row(
    *,
    year: int,
    month: int,
    implied: float,
    source_file: str,
) -> DamodaranMonthlyERPRow:
    """Build a synthetic ``DamodaranMonthlyERPRow`` for the writer tests."""
    return DamodaranMonthlyERPRow(
        start_of_month=date(year, month, 1),
        implied_erp_decimal=implied,
        implied_erp_t12m_decimal=implied + 0.0008 if not math.isnan(implied) else None,
        sp500_level=4_800.0,
        tbond_rate_decimal=0.0410,
        source_file=source_file,
    )


class TestDamodaranExternalWriter:
    """Spec §6 (Sprint 3.1) — fixture-based writer tests."""

    def test_build_row_2024_01_canonical(self) -> None:
        """Damodaran Jan 2024 monthly snapshot → 5.50 % → 550 bps."""
        damodaran_row = _row(year=2024, month=1, implied=0.0550, source_file="ERPJan24.xlsx")

        row = build_damodaran_external_row(
            year=2024,
            month=1,
            damodaran_row=damodaran_row,
        )

        assert row.market_index == "SPX"
        assert row.country_code == "US"
        assert row.date == date(2024, 1, 1)
        assert row.source == "damodaran_monthly"
        assert row.erp_bps == 550
        assert row.publication_date is None
        assert row.source_file == "ERPJan24.xlsx"
        assert row.methodology_version == "DAMODARAN_MONTHLY_v0.1"
        assert row.confidence == 0.95
        assert row.flags is None

    def test_build_row_invalid_implied_raises(self) -> None:
        """NaN implied ERP must raise ``InsufficientDataError``.

        ``DamodaranMonthlyERPRow.implied_erp_decimal`` is non-Optional
        (the connector returns ``None`` for the whole row when the
        column is absent), so the writer guards against the in-band
        ``NaN`` / non-positive sentinels instead.
        """
        damodaran_row = _row(
            year=2024,
            month=2,
            implied=float("nan"),
            source_file="ERPFeb24.xlsx",
        )
        with pytest.raises(InsufficientDataError, match="implied_erp_decimal invalid"):
            build_damodaran_external_row(
                year=2024,
                month=2,
                damodaran_row=damodaran_row,
            )

    def test_build_row_2025_12_recent_freshness(self) -> None:
        """Recent monthly snapshot (Dec 2025; latest verified 2026-04-25)."""
        damodaran_row = _row(year=2025, month=12, implied=0.0480, source_file="ERPDec25.xlsx")

        row = build_damodaran_external_row(
            year=2025,
            month=12,
            damodaran_row=damodaran_row,
        )

        assert row.erp_bps == 480
        assert row.date == date(2025, 12, 1)
        assert row.source_file == "ERPDec25.xlsx"
        assert row.methodology_version == "DAMODARAN_MONTHLY_v0.1"
