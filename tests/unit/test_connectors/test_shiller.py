"""Unit tests for ShillerConnector — synthetic xls fixture for parser."""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
import pytest

from sonar.connectors.shiller import (
    SHILLER_IE_DATA_URL,
    ShillerSnapshot,
    _parse_snapshot,
)


def _build_synthetic_xls() -> bytes:
    """Build a Shiller-shaped xls — 7 metadata rows, then header + data."""
    columns = [
        "Date",
        "P",
        "D",
        "E",
        "CPI",
        "Rate GS10",
        "Real Price",
        "Real Dividend",
        "Real Earnings",
        "CAPE",
    ]
    data_rows = [
        [2023.12, 4700.0, 70.0, 200.0, 305.0, 4.10, 4700.0, 70.0, 195.0, 28.5],
        [2024.01, 4742.83, 70.5, 202.0, 305.5, 4.15, 4730.0, 70.4, 198.0, 29.1],
        [2024.02, 5000.0, 71.0, 205.0, 306.0, 4.25, 4980.0, 70.7, 200.0, 30.0],
    ]

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # 7 metadata rows (None-filled) + header row at index 7 + data from row 8.
        meta = pd.DataFrame([[None] * len(columns)] * 7, columns=columns)
        meta.to_excel(writer, sheet_name="Data", index=False, header=False, startrow=0)
        # Write the canonical Shiller header at row 7 (0-indexed), data at 8+.
        df = pd.DataFrame(data_rows, columns=columns)
        df.to_excel(writer, sheet_name="Data", index=False, startrow=7)
    return buf.getvalue()


def test_endpoint_url_constant() -> None:
    assert SHILLER_IE_DATA_URL.startswith("http")
    assert "ie_data" in SHILLER_IE_DATA_URL


def test_parse_snapshot_jan_2024_exact_match() -> None:
    body = _build_synthetic_xls()
    snap = _parse_snapshot(body, date(2024, 1, 31))
    assert isinstance(snap, ShillerSnapshot)
    assert snap.observation_date == date(2024, 1, 1)
    assert snap.price_nominal == pytest.approx(4742.83)
    assert snap.cape_ratio == pytest.approx(29.1)
    assert snap.long_rate_pct == pytest.approx(4.15)


def test_parse_snapshot_picks_latest_at_or_before() -> None:
    body = _build_synthetic_xls()
    # Mid-Feb → should pick Feb row (most recent at-or-before).
    snap = _parse_snapshot(body, date(2024, 2, 15))
    assert snap.observation_date == date(2024, 2, 1)
    assert snap.cape_ratio == pytest.approx(30.0)


def test_parse_snapshot_no_data_before_target_raises() -> None:
    body = _build_synthetic_xls()
    with pytest.raises(ValueError, match="no rows at or before"):
        _parse_snapshot(body, date(2020, 1, 1))
