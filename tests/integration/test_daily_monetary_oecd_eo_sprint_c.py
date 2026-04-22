"""Live integration canary — OECD EO output-gap wiring (Sprint C Week 10).

Exercises the Sprint C wiring end-to-end:

- ``test_oecd_eo_live_returns_gap_for_every_t1_country`` — one HTTP
  call per country validates that the OECD EO connector can fetch
  the canonical ``GAP`` series for every ISO2 in
  ``OECD_EO_COUNTRY_MAP`` (16 T1 + EA17).
- ``test_m2_ca_raise_message_reflects_oecd_eo_live`` — composes the
  ``MonetaryInputsBuilder`` via ``_build_live_connectors`` and calls
  ``build_m2_inputs("CA", ...)``. The raise message must include
  "output-gap live via OECD EO" — confirms the connector is wired
  end-to-end through the pipeline dispatch, not just the unit layer.

Both gated by ``pytest -m slow`` so they only run when opted-in
(OECD SDMX is public — no auth keys required — but they still hit
the network).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from sonar.connectors.oecd_eo import OECD_EO_COUNTRY_MAP, OECDEOConnector
from sonar.indices.monetary.builders import MonetaryInputsBuilder
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.slow


@pytest.fixture
def anchor() -> date:
    # OECD EO publishes biannually; use last-year year-end so the
    # observation is guaranteed to be available regardless of release
    # timing.
    today = datetime.now(tz=UTC).date()
    return date(today.year - 1, 12, 31)


@pytest.mark.asyncio
async def test_oecd_eo_live_returns_gap_for_every_t1_country(anchor: date, tmp_path: Path) -> None:
    """Smoke — every ISO2 in the Sprint C map has live GAP data."""
    conn = OECDEOConnector(cache_dir=str(tmp_path / "oecd_eo"))
    try:
        failures: list[tuple[str, str]] = []
        for iso2 in OECD_EO_COUNTRY_MAP:
            gaps = await conn.fetch_output_gap(iso2, anchor - timedelta(days=3 * 366), anchor)
            if not gaps:
                failures.append((iso2, "empty response"))
                continue
            # GAP is percent of potential GDP — sanity band [-15, +10]
            # covers the 2008/2020 troughs without being too tight.
            latest = gaps[-1]
            if not -15.0 < latest.gap_pct < 10.0:
                failures.append((iso2, f"gap out of band: {latest.gap_pct}"))
        assert failures == [], f"OECD EO live GAP failures: {failures}"
    finally:
        await conn.aclose()


@pytest.mark.asyncio
async def test_m2_ca_raise_message_reflects_oecd_eo_live(anchor: date, tmp_path: Path) -> None:
    """End-to-end: facade dispatch → M2 CA builder → OECD EO fetch success.

    Asserts that ``MonetaryInputsBuilder`` passes the real OECD EO
    connector through to the CA builder and the builder's
    ``InsufficientDataError`` acknowledges the output-gap is wired.
    """
    from sonar.connectors.cbo import CboConnector  # noqa: PLC0415
    from sonar.connectors.ecb_sdw import EcbSdwConnector  # noqa: PLC0415
    from sonar.connectors.fred import FredConnector  # noqa: PLC0415

    # Synthetic FRED key — Sprint C M2 CA builder only uses fred as an
    # unused parameter (``noqa: ARG001``) at this stage. No real FRED
    # call happens.
    fred = FredConnector(
        api_key="sprint-c-oecd-canary",  # pragma: allowlist secret
        cache_dir=str(tmp_path / "fred"),
    )
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    oecd_eo = OECDEOConnector(cache_dir=str(tmp_path / "oecd_eo"))
    try:
        builder = MonetaryInputsBuilder(
            fred=fred,
            cbo=cbo,
            ecb_sdw=ecb,
            oecd_eo=oecd_eo,
        )
        with pytest.raises(InsufficientDataError) as excinfo:
            await builder.build_m2_inputs("CA", anchor, history_years=2)
        message = str(excinfo.value)
        assert "output-gap live via OECD EO" in message
        assert "CAL-M2-T1-OUTPUT-GAP-EXPANSION" in message
        assert "M2 CA" in message
    finally:
        await fred.aclose()
        await ecb.aclose()
        await oecd_eo.aclose()
