"""Unit tests for the BdF scaffold — scope-narrow per Sprint D HALT-0 (2026-04-22).

The connector ships as a documentation-first scaffold (see module
docstring) while all four probed FR data paths are non-viable.
The tests lock down the interface contract so the future swap-in of
a functional implementation is a pure-methods delta.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from sonar.connectors.banque_de_france import (
    BDF_BASE_URL,
    BDF_PROBE_DATE,
    BDF_PROBE_FINDINGS,
    BDF_USER_AGENT,
    FR_CAL_POINTER,
    BanqueDeFranceConnector,
)
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def connector(tmp_path: Path) -> BanqueDeFranceConnector:
    return BanqueDeFranceConnector(cache_dir=str(tmp_path / "bdf_cache"))


def test_module_constants_expose_probe_findings() -> None:
    """Operator reading the module at tool-tip depth sees the probe state."""
    assert FR_CAL_POINTER == "CAL-CURVES-FR-BDF"
    assert BDF_PROBE_DATE == "2026-04-22"
    # Findings tuple covers the four probed paths + FRED fallback.
    assert len(BDF_PROBE_FINDINGS) == 5
    joined = " | ".join(BDF_PROBE_FINDINGS)
    assert "SDMX" in joined
    assert "OpenDatasoft" in joined
    assert "AFT" in joined
    assert "TE" in joined
    assert "FRED" in joined


def test_base_url_points_at_current_opendatasoft_api() -> None:
    """Forward-reference URL — present-state reachable even if empty of yields."""
    assert BDF_BASE_URL.startswith("https://webstat.banque-france.fr/api/explore/")
    assert "SONAR" in BDF_USER_AGENT


def test_connector_constructor_matches_bundesbank_signature(tmp_path: Path) -> None:
    """cache_dir + timeout kwargs mirror BundesbankConnector for drop-in swap."""
    conn = BanqueDeFranceConnector(cache_dir=str(tmp_path), timeout=45.0)
    assert conn._cache_dir == str(tmp_path)
    assert conn._timeout == 45.0


@pytest.mark.asyncio
async def test_fetch_series_raises_insufficient_data(
    connector: BanqueDeFranceConnector,
) -> None:
    """Low-level fetch path short-circuits with the CAL pointer + probe date."""
    with pytest.raises(InsufficientDataError) as exc:
        await connector.fetch_series("OAT.10Y", date(2024, 1, 1), date(2024, 12, 31))
    msg = str(exc.value)
    assert FR_CAL_POINTER in msg
    assert BDF_PROBE_DATE in msg
    assert "fetch_series" in msg


@pytest.mark.asyncio
async def test_fetch_yield_curve_nominal_raises_for_fr(
    connector: BanqueDeFranceConnector,
) -> None:
    """FR yield curve deferred — error cites the probe-finding narrative."""
    with pytest.raises(InsufficientDataError) as exc:
        await connector.fetch_yield_curve_nominal(country="FR", observation_date=date(2024, 12, 31))
    msg = str(exc.value)
    assert FR_CAL_POINTER in msg
    assert "EA-AAA proxy" in msg
    # At least one probe-finding fragment surfaces in the error so the
    # operator sees the *reason* alongside the pointer.
    assert any(finding in msg for finding in BDF_PROBE_FINDINGS)


@pytest.mark.asyncio
async def test_fetch_yield_curve_linker_raises_for_fr(
    connector: BanqueDeFranceConnector,
) -> None:
    """Linker path mirrors the nominal deferral — nominal gap blocks real curve."""
    with pytest.raises(InsufficientDataError) as exc:
        await connector.fetch_yield_curve_linker(country="FR", observation_date=date(2024, 12, 31))
    assert FR_CAL_POINTER in str(exc.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_country", ["DE", "IT", "ES", "PT", "NL", "US"])
async def test_fetch_methods_reject_non_fr_country(
    connector: BanqueDeFranceConnector, bad_country: str
) -> None:
    """Single-country contract mirrors Bundesbank DE-only precedent."""
    with pytest.raises(ValueError, match="only supports country='FR'"):
        await connector.fetch_yield_curve_nominal(
            country=bad_country, observation_date=date(2024, 12, 31)
        )
    with pytest.raises(ValueError, match="only supports country='FR'"):
        await connector.fetch_yield_curve_linker(
            country=bad_country, observation_date=date(2024, 12, 31)
        )


@pytest.mark.asyncio
async def test_fetch_accepts_lower_case_fr(
    connector: BanqueDeFranceConnector,
) -> None:
    """Country normalisation matches BundesbankConnector idiom."""
    with pytest.raises(InsufficientDataError):
        await connector.fetch_yield_curve_nominal(country="fr", observation_date=date(2024, 12, 31))


@pytest.mark.asyncio
async def test_aclose_is_noop(connector: BanqueDeFranceConnector) -> None:
    """Scaffold owns no resources — aclose returns None."""
    result = await connector.aclose()
    assert result is None
