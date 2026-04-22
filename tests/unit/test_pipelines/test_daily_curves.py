"""Unit tests — daily_curves dispatcher routing.

Covers the post-Sprint-H (IT + ES TE cascade 2026-04-22) surface of
:func:`sonar.pipelines.daily_curves._fetch_nominals_linkers`:

- Positive routing for the eight curve-capable T1 members (US / DE /
  EA / GB / JP / CA / IT / ES) — each country lands on the expected
  connector and returns the expected ``source_connector`` label.
- Missing-connector HALT path (each supported country raises
  ``InsufficientDataError`` when the caller omits the required
  connector instance).
- Tuple invariants: :data:`T1_CURVES_COUNTRIES` matches
  :data:`CURVE_SUPPORTED_COUNTRIES` and is disjoint from the deferred
  CAL-pointer map.

Pure unit — no network, no DB. Each connector is replaced with an
``AsyncMock`` returning a 10-tenor nominal + empty linker dict, which
is the dispatch-layer contract the pipeline relies on before NSS fit.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from sonar.connectors.base import Observation
from sonar.overlays.exceptions import InsufficientDataError
from sonar.pipelines.daily_curves import (
    _DEFERRAL_CAL_MAP,
    CURVE_SUPPORTED_COUNTRIES,
    T1_CURVES_COUNTRIES,
    _fetch_nominals_linkers,
)

OBSERVATION_DATE = date(2024, 12, 30)

_STUB_TENORS: tuple[tuple[str, float], ...] = (
    ("3M", 0.25),
    ("6M", 0.5),
    ("1Y", 1.0),
    ("2Y", 2.0),
    ("3Y", 3.0),
    ("5Y", 5.0),
    ("7Y", 7.0),
    ("10Y", 10.0),
    ("20Y", 20.0),
    ("30Y", 30.0),
)


def _stub_nominals(country: str, source_series_prefix: str = "STUB") -> dict[str, Observation]:
    return {
        label: Observation(
            country_code=country,
            observation_date=OBSERVATION_DATE,
            tenor_years=years,
            yield_bps=400 + int(years * 5),
            source=source_series_prefix,
            source_series_id=f"{source_series_prefix}_{label}",
        )
        for label, years in _STUB_TENORS
    }


# ---------------------------------------------------------------------------
# Tuple invariants
# ---------------------------------------------------------------------------


def test_t1_curves_countries_matches_supported() -> None:
    """``--all-t1`` iteration set must match the dispatch whitelist.

    Guard against future drift: adding a country to either side should
    surface as a test failure so both invariants move in lockstep.
    """
    assert set(T1_CURVES_COUNTRIES) == CURVE_SUPPORTED_COUNTRIES


def test_t1_curves_countries_disjoint_from_deferrals() -> None:
    """Countries iterated in ``--all-t1`` must not have an active
    deferral CAL pointer — otherwise the pipeline would emit a CAL-
    pointer warning for a country it actually serves.
    """
    assert set(T1_CURVES_COUNTRIES).isdisjoint(_DEFERRAL_CAL_MAP)


def test_t1_curves_countries_ordering_stable() -> None:
    """Preserve historical ordering so systemd journals and cassette
    filenames remain stable across sprints.

    Sprint H (IT + ES TE cascade, 2026-04-22) appended IT + ES; Sprint I
    (FR TE cascade, 2026-04-22) appends FR. The first eight entries
    remain bit-stable with the Sprint H ordering for journal/tool
    compatibility.
    """
    assert T1_CURVES_COUNTRIES == ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR")


# ---------------------------------------------------------------------------
# Positive dispatch — TE branch (GB/JP/CA) — new surface for Sprint E
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("country", ["GB", "JP", "CA", "IT", "ES", "FR"])
async def test_dispatch_routes_non_ea_t1_to_te(country: str) -> None:
    """GB/JP/CA dispatch lands on ``TEConnector`` (CAL-138 empirical
    probe 2026-04-22); IT + ES join the TE branch post Sprint H
    (2026-04-22) via the same per-country ``TE_YIELD_CURVE_SYMBOLS``
    dispatch; FR joins post Sprint I (2026-04-22).
    """
    te = AsyncMock()
    te.fetch_yield_curve_nominal.return_value = _stub_nominals(country, source_series_prefix="TE")
    te.fetch_yield_curve_linker.return_value = {}

    nominals, linkers, source = await _fetch_nominals_linkers(
        country,
        OBSERVATION_DATE,
        fred=None,
        bundesbank=None,
        ecb_sdw=None,
        te=te,
    )

    te.fetch_yield_curve_nominal.assert_awaited_once_with(
        country=country, observation_date=OBSERVATION_DATE
    )
    te.fetch_yield_curve_linker.assert_awaited_once_with(
        country=country, observation_date=OBSERVATION_DATE
    )
    assert source == "te"
    assert len(nominals) == len(_STUB_TENORS)
    assert linkers == {}


@pytest.mark.parametrize("country", ["GB", "JP", "CA", "IT", "ES", "FR"])
async def test_dispatch_raises_when_te_missing_for_non_ea_t1(country: str) -> None:
    """Missing TE connector for a TE-served country surfaces as
    ``InsufficientDataError`` with the country code cited — not a
    silent ``None`` or an ``AttributeError`` deeper in the stack.
    """
    with pytest.raises(InsufficientDataError, match=country):
        await _fetch_nominals_linkers(
            country,
            OBSERVATION_DATE,
            fred=None,
            bundesbank=None,
            ecb_sdw=None,
            te=None,
        )


async def test_dispatch_passes_country_code_upper_to_te() -> None:
    """Input country is upper-cased before dispatch (docs promise
    case-insensitive ``--country``).
    """
    te = AsyncMock()
    te.fetch_yield_curve_nominal.return_value = _stub_nominals("GB", source_series_prefix="TE")
    te.fetch_yield_curve_linker.return_value = {}

    _, _, source = await _fetch_nominals_linkers(
        "gb",
        OBSERVATION_DATE,
        fred=None,
        bundesbank=None,
        ecb_sdw=None,
        te=te,
    )
    te.fetch_yield_curve_nominal.assert_awaited_once_with(
        country="GB", observation_date=OBSERVATION_DATE
    )
    assert source == "te"


# ---------------------------------------------------------------------------
# Positive dispatch — existing US/DE/EA branches (regression guards)
# ---------------------------------------------------------------------------


async def test_dispatch_routes_us_to_fred() -> None:
    fred = AsyncMock()
    fred.fetch_yield_curve_nominal.return_value = _stub_nominals("US", source_series_prefix="FRED")
    fred.fetch_yield_curve_linker.return_value = {}

    _, _, source = await _fetch_nominals_linkers(
        "US",
        OBSERVATION_DATE,
        fred=fred,
        bundesbank=None,
        ecb_sdw=None,
        te=None,
    )
    assert source == "fred"


async def test_dispatch_routes_de_to_bundesbank() -> None:
    bundesbank = AsyncMock()
    bundesbank.fetch_yield_curve_nominal.return_value = _stub_nominals(
        "DE", source_series_prefix="BBSIS"
    )
    bundesbank.fetch_yield_curve_linker.return_value = {}

    _, _, source = await _fetch_nominals_linkers(
        "DE",
        OBSERVATION_DATE,
        fred=None,
        bundesbank=bundesbank,
        ecb_sdw=None,
        te=None,
    )
    assert source == "bundesbank"


async def test_dispatch_routes_ea_to_ecb_sdw() -> None:
    ecb_sdw = AsyncMock()
    ecb_sdw.fetch_yield_curve_nominal.return_value = _stub_nominals(
        "EA", source_series_prefix="ECB"
    )
    ecb_sdw.fetch_yield_curve_linker.return_value = {}

    _, _, source = await _fetch_nominals_linkers(
        "EA",
        OBSERVATION_DATE,
        fred=None,
        bundesbank=None,
        ecb_sdw=ecb_sdw,
        te=None,
    )
    assert source == "ecb_sdw"
