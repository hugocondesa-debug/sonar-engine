"""Unit tests for the Banco de España scaffold — Sprint G HALT-0 (2026-04-22).

The connector ships as a documentation-first scaffold (see module
docstring) after the combined Sprint G pre-flight probe found the
BdE BIE REST API reachable but publishing only monthly Spanish
sovereign yields, below the daily pipeline cadence.

Tests lock down the interface contract so the future swap-in of a
functional implementation (conditional on BdE publishing daily
Bono yields, or the pipeline gaining a monthly-cadence path) is a
pure-methods delta.

Symmetric structure with ``test_banque_de_france.py`` +
``test_banca_ditalia.py`` so the four EA-periphery scaffolds share
a uniform test shape under ADR-0009 pattern discipline.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from sonar.connectors.banco_espana import (
    BDE_BASE_URL,
    BDE_PROBE_DATE,
    BDE_PROBE_FINDINGS,
    BDE_USER_AGENT,
    ES_CAL_POINTER,
    BancoEspanaConnector,
)
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def connector(tmp_path: Path) -> BancoEspanaConnector:
    return BancoEspanaConnector(cache_dir=str(tmp_path / "bde_cache"))


def test_module_constants_expose_probe_findings() -> None:
    """Operator reading the module at tool-tip depth sees the probe state."""
    assert ES_CAL_POINTER == "CAL-CURVES-ES-BDE"
    assert BDE_PROBE_DATE == "2026-04-22"
    # Findings tuple covers the five brief §2 probed paths + FRED fallback.
    assert len(BDE_PROBE_FINDINGS) == 6
    joined = " | ".join(BDE_PROBE_FINDINGS)
    assert "BDEstad" in joined
    assert "BIE REST" in joined
    assert "MONTHLY" in joined
    assert "Tesoro" in joined
    assert "ECB SDW FM" in joined
    assert "FRED" in joined


def test_base_url_points_at_bierest_api() -> None:
    """Forward-reference URL — live REST API today; blocked on frequency, not reachability."""
    assert BDE_BASE_URL.startswith("https://app.bde.es/bierest/")
    assert "SONAR" in BDE_USER_AGENT


def test_connector_constructor_matches_bundesbank_signature(tmp_path: Path) -> None:
    """cache_dir + timeout kwargs mirror BundesbankConnector for drop-in swap."""
    conn = BancoEspanaConnector(cache_dir=str(tmp_path), timeout=45.0)
    assert conn._cache_dir == str(tmp_path)
    assert conn._timeout == 45.0


@pytest.mark.asyncio
async def test_fetch_series_raises_insufficient_data(
    connector: BancoEspanaConnector,
) -> None:
    """Low-level fetch path short-circuits with the CAL pointer + probe date."""
    with pytest.raises(InsufficientDataError) as exc:
        await connector.fetch_series("D_1NBBO320", date(2024, 1, 1), date(2024, 12, 31))
    msg = str(exc.value)
    assert ES_CAL_POINTER in msg
    assert BDE_PROBE_DATE in msg
    assert "fetch_series" in msg


@pytest.mark.asyncio
async def test_fetch_yield_curve_nominal_raises_for_es(
    connector: BancoEspanaConnector,
) -> None:
    """ES yield curve deferred — error cites the frequency-gap narrative."""
    with pytest.raises(InsufficientDataError) as exc:
        await connector.fetch_yield_curve_nominal(country="ES", observation_date=date(2024, 12, 31))
    msg = str(exc.value)
    assert ES_CAL_POINTER in msg
    assert "EA-AAA proxy" in msg
    # At least one probe-finding fragment surfaces in the error so the
    # operator sees the *reason* alongside the pointer.
    assert any(finding in msg for finding in BDE_PROBE_FINDINGS)


@pytest.mark.asyncio
async def test_fetch_yield_curve_linker_raises_for_es(
    connector: BancoEspanaConnector,
) -> None:
    """Linker path mirrors the nominal deferral — nominal gap blocks real curve."""
    with pytest.raises(InsufficientDataError) as exc:
        await connector.fetch_yield_curve_linker(country="ES", observation_date=date(2024, 12, 31))
    assert ES_CAL_POINTER in str(exc.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_country", ["DE", "FR", "IT", "PT", "NL", "US"])
async def test_fetch_methods_reject_non_es_country(
    connector: BancoEspanaConnector, bad_country: str
) -> None:
    """Single-country contract mirrors Bundesbank + BdF + BdI precedent."""
    with pytest.raises(ValueError, match="only supports country='ES'"):
        await connector.fetch_yield_curve_nominal(
            country=bad_country, observation_date=date(2024, 12, 31)
        )
    with pytest.raises(ValueError, match="only supports country='ES'"):
        await connector.fetch_yield_curve_linker(
            country=bad_country, observation_date=date(2024, 12, 31)
        )


@pytest.mark.asyncio
async def test_fetch_accepts_lower_case_es(
    connector: BancoEspanaConnector,
) -> None:
    """Country normalisation matches BundesbankConnector + BdF + BdI idiom."""
    with pytest.raises(InsufficientDataError):
        await connector.fetch_yield_curve_nominal(country="es", observation_date=date(2024, 12, 31))


@pytest.mark.asyncio
async def test_aclose_is_noop(connector: BancoEspanaConnector) -> None:
    """Scaffold owns no resources — aclose returns None."""
    result = await connector.aclose()
    assert result is None
