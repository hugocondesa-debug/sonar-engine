"""Unit tests for SPDJIBuybackConnector (Week 3.5B graceful stub)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sonar.connectors.spdji_buyback import (
    DataUnavailableError,
    SPDJIBuybackConnector,
)

if TYPE_CHECKING:
    from pathlib import Path


async def test_stub_raises_data_unavailable(tmp_path: Path) -> None:
    conn = SPDJIBuybackConnector(cache_dir=str(tmp_path))
    with pytest.raises(DataUnavailableError, match="graceful stub"):
        await conn.fetch_latest_buyback_yield_decimal()
    await conn.aclose()
