"""Unit tests for DamodaranConnector — synthetic xlsx fixture."""

from __future__ import annotations

import io

import openpyxl
import pytest

from sonar.connectors.damodaran import (
    COL_IMPLIED_FCFE,
    COL_IMPLIED_FCFE_SUSTAINABLE,
    COL_SHEET,
    COL_YEAR,
    DamodaranERPRow,
    _parse_year,
)


def _build_synthetic_xlsx(*, include_sustainable: bool = True) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = COL_SHEET

    # 6 metadata rows, then header row at index 6, then data.
    for i in range(6):
        ws.append([f"meta{i}"])
    header = [COL_YEAR, "Earnings Yield", "Dividend Yield", COL_IMPLIED_FCFE]
    if include_sustainable:
        header.append(COL_IMPLIED_FCFE_SUSTAINABLE)
    ws.append(header)

    # Data rows 2020-2024.
    for year in range(2020, 2025):
        row = [year, 0.04, 0.02, 0.045 + (year - 2020) * 0.001]
        if include_sustainable:
            row.append(0.050 + (year - 2020) * 0.001)
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseYear:
    def test_preferred_sustainable_column(self) -> None:
        body = _build_synthetic_xlsx(include_sustainable=True)
        result = _parse_year(body, 2024)
        assert isinstance(result, DamodaranERPRow)
        assert result.year == 2024
        assert result.source_column == COL_IMPLIED_FCFE_SUSTAINABLE
        assert result.implied_erp_decimal == pytest.approx(0.054)

    def test_fallback_to_fcfe_when_sustainable_missing(self) -> None:
        body = _build_synthetic_xlsx(include_sustainable=False)
        result = _parse_year(body, 2024)
        assert result is not None
        assert result.source_column == COL_IMPLIED_FCFE
        assert result.implied_erp_decimal == pytest.approx(0.049)

    def test_year_not_found_returns_none(self) -> None:
        body = _build_synthetic_xlsx()
        assert _parse_year(body, 1950) is None

    def test_header_row_required(self) -> None:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = COL_SHEET
        ws.append(["no-header-here"])
        buf = io.BytesIO()
        wb.save(buf)
        assert _parse_year(buf.getvalue(), 2024) is None
