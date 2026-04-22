"""Unit tests for the Banca d'Italia scaffold — Sprint G HALT-0 (2026-04-22).

The connector ships as a documentation-first scaffold (see module
docstring) after the combined Sprint G pre-flight probe found all
five IT data paths non-viable. Tests lock down the interface contract
so the future swap-in of a functional implementation (conditional on
Banca d'Italia publishing a public SDMX surface for BTP yields) is a
pure-methods delta.

Symmetric structure with ``test_banque_de_france.py`` — Sprint D pilot
precedent — so the four EA-periphery scaffolds share a uniform test
shape under ADR-0009 pattern discipline.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from sonar.connectors.banca_ditalia import (
    BDI_BASE_URL,
    BDI_PROBE_DATE,
    BDI_PROBE_FINDINGS,
    BDI_USER_AGENT,
    IT_CAL_POINTER,
    BancaDItaliaConnector,
)
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def connector(tmp_path: Path) -> BancaDItaliaConnector:
    return BancaDItaliaConnector(cache_dir=str(tmp_path / "bdi_cache"))


def test_module_constants_expose_probe_findings() -> None:
    """Operator reading the module at tool-tip depth sees the probe state."""
    assert IT_CAL_POINTER == "CAL-CURVES-IT-BDI"
    assert BDI_PROBE_DATE == "2026-04-22"
    # Findings tuple covers the five brief §2 probed paths + FRED fallback.
    assert len(BDI_PROBE_FINDINGS) == 6
    joined = " | ".join(BDI_PROBE_FINDINGS)
    assert "SDMX" in joined
    assert "Infostat" in joined
    assert "MEF" in joined
    assert "ECB SDW FM" in joined
    assert "IRS" in joined
    assert "FRED" in joined


def test_base_url_points_at_infostat_landing() -> None:
    """Forward-reference URL — reachable today but serves only an SPA."""
    assert BDI_BASE_URL.startswith("https://infostat.bancaditalia.it/")
    assert "SONAR" in BDI_USER_AGENT


def test_connector_constructor_matches_bundesbank_signature(tmp_path: Path) -> None:
    """cache_dir + timeout kwargs mirror BundesbankConnector for drop-in swap."""
    conn = BancaDItaliaConnector(cache_dir=str(tmp_path), timeout=45.0)
    assert conn._cache_dir == str(tmp_path)
    assert conn._timeout == 45.0


@pytest.mark.asyncio
async def test_fetch_series_raises_insufficient_data(
    connector: BancaDItaliaConnector,
) -> None:
    """Low-level fetch path short-circuits with the CAL pointer + probe date."""
    with pytest.raises(InsufficientDataError) as exc:
        await connector.fetch_series("BTP.10Y", date(2024, 1, 1), date(2024, 12, 31))
    msg = str(exc.value)
    assert IT_CAL_POINTER in msg
    assert BDI_PROBE_DATE in msg
    assert "fetch_series" in msg


@pytest.mark.asyncio
async def test_fetch_yield_curve_nominal_raises_for_it(
    connector: BancaDItaliaConnector,
) -> None:
    """IT yield curve deferred — error cites the probe-finding narrative."""
    with pytest.raises(InsufficientDataError) as exc:
        await connector.fetch_yield_curve_nominal(country="IT", observation_date=date(2024, 12, 31))
    msg = str(exc.value)
    assert IT_CAL_POINTER in msg
    assert "EA-AAA proxy" in msg
    # At least one probe-finding fragment surfaces in the error so the
    # operator sees the *reason* alongside the pointer.
    assert any(finding in msg for finding in BDI_PROBE_FINDINGS)


@pytest.mark.asyncio
async def test_fetch_yield_curve_linker_raises_for_it(
    connector: BancaDItaliaConnector,
) -> None:
    """Linker path mirrors the nominal deferral — nominal gap blocks real curve."""
    with pytest.raises(InsufficientDataError) as exc:
        await connector.fetch_yield_curve_linker(country="IT", observation_date=date(2024, 12, 31))
    assert IT_CAL_POINTER in str(exc.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_country", ["DE", "FR", "ES", "PT", "NL", "US"])
async def test_fetch_methods_reject_non_it_country(
    connector: BancaDItaliaConnector, bad_country: str
) -> None:
    """Single-country contract mirrors Bundesbank DE-only + BdF FR-only precedent."""
    with pytest.raises(ValueError, match="only supports country='IT'"):
        await connector.fetch_yield_curve_nominal(
            country=bad_country, observation_date=date(2024, 12, 31)
        )
    with pytest.raises(ValueError, match="only supports country='IT'"):
        await connector.fetch_yield_curve_linker(
            country=bad_country, observation_date=date(2024, 12, 31)
        )


@pytest.mark.asyncio
async def test_fetch_accepts_lower_case_it(
    connector: BancaDItaliaConnector,
) -> None:
    """Country normalisation matches BundesbankConnector + BdF idiom."""
    with pytest.raises(InsufficientDataError):
        await connector.fetch_yield_curve_nominal(country="it", observation_date=date(2024, 12, 31))


@pytest.mark.asyncio
async def test_aclose_is_noop(connector: BancaDItaliaConnector) -> None:
    """Scaffold owns no resources — aclose returns None."""
    result = await connector.aclose()
    assert result is None
