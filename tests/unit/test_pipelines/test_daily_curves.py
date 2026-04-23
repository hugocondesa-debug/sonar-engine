"""Unit tests — daily_curves dispatcher routing.

Covers the post-Sprint-M (PT TE cascade 2026-04-23) surface of
:func:`sonar.pipelines.daily_curves._fetch_nominals_linkers`:

- Positive routing for the ten curve-capable T1 members (US / DE /
  EA / GB / JP / CA / IT / ES / FR / PT) — each country lands on the
  expected connector and returns the expected ``source_connector``
  label.
- Missing-connector HALT path (each supported country raises
  ``InsufficientDataError`` when the caller omits the required
  connector instance).
- Tuple invariants: :data:`T1_CURVES_COUNTRIES` matches
  :data:`CURVE_SUPPORTED_COUNTRIES` and is disjoint from the deferred
  CAL-pointer map.
- ADR-0011 idempotency: :func:`_curve_already_persisted` returns True
  when a matching ``(country_code, date, methodology_version)`` row
  exists and False otherwise (Sprint T0 2026-04-23).

Pure unit — no network; the idempotency test uses an in-memory SQLite
DB so the canonical UNIQUE constraint surface is exercised.
"""

from __future__ import annotations

import json as _json
from datetime import date
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401 — registers SQLite pragma listeners
from sonar.connectors.base import Observation
from sonar.db.models import Base, NSSYieldCurveSpot
from sonar.overlays.exceptions import InsufficientDataError
from sonar.overlays.nss import METHODOLOGY_VERSION as NSS_METHODOLOGY_VERSION
from sonar.pipelines.daily_curves import (
    _DEFERRAL_CAL_MAP,
    CURVE_SUPPORTED_COUNTRIES,
    T1_CURVES_COUNTRIES,
    _curve_already_persisted,
    _CurveRunOutcomes,
    _fetch_nominals_linkers,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

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
    (FR TE cascade, 2026-04-22) appended FR; Sprint M (PT TE cascade,
    2026-04-23) appends PT. The first nine entries remain bit-stable
    with the Sprint I ordering for journal/tool compatibility. NL stays
    deferred (Path 1 HALT-0 — CAL-CURVES-NL-DNB-PROBE).
    """
    assert T1_CURVES_COUNTRIES == (
        "US",
        "DE",
        "EA",
        "GB",
        "JP",
        "CA",
        "IT",
        "ES",
        "FR",
        "PT",
    )


# ---------------------------------------------------------------------------
# Positive dispatch — TE branch (GB/JP/CA) — new surface for Sprint E
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("country", ["GB", "JP", "CA", "IT", "ES", "FR", "PT"])
async def test_dispatch_routes_non_ea_t1_to_te(country: str) -> None:
    """GB/JP/CA dispatch lands on ``TEConnector`` (CAL-138 empirical
    probe 2026-04-22); IT + ES join the TE branch post Sprint H
    (2026-04-22) via the same per-country ``TE_YIELD_CURVE_SYMBOLS``
    dispatch; FR joins post Sprint I (2026-04-22); PT joins post
    Sprint M (2026-04-23).
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


@pytest.mark.parametrize("country", ["GB", "JP", "CA", "IT", "ES", "FR", "PT"])
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


# ---------------------------------------------------------------------------
# ADR-0011 idempotency — pre-INSERT existence check (Sprint T0 2026-04-23)
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session_in_memory() -> Iterator[Session]:
    """In-memory SQLite session with the full ORM schema applied.

    Enforces the production UNIQUE constraint
    ``uq_ycs_country_date_method`` so the idempotency pre-check can be
    validated under the canonical schema (ADR-0011 Principle 1).
    """
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _insert_spot_row(session: Session, country: str, observation_date: date) -> None:
    row = NSSYieldCurveSpot(
        country_code=country,
        date=observation_date,
        methodology_version=NSS_METHODOLOGY_VERSION,
        fit_id=f"fit-{country}-{observation_date.isoformat()}",
        beta_0=0.04,
        beta_1=-0.01,
        beta_2=0.005,
        beta_3=0.0,
        lambda_1=1.5,
        lambda_2=3.0,
        fitted_yields_json=_json.dumps({"10Y": 0.04}),
        observations_used=10,
        rmse_bps=3.0,
        xval_deviation_bps=None,
        confidence=0.95,
        flags=None,
        source_connector="unit_test",
    )
    session.add(row)
    session.commit()


def test_curve_already_persisted_false_on_empty_db(db_session_in_memory: Session) -> None:
    """Empty DB → no existing triplet → returns False.

    Expected happy path before any run has persisted anything.
    """
    assert not _curve_already_persisted(db_session_in_memory, "US", OBSERVATION_DATE)


def test_curve_already_persisted_true_after_insert(db_session_in_memory: Session) -> None:
    """After an INSERT for the triplet → returns True → orchestrator skip.

    Matches ADR-0011 Principle 1: idempotent re-runs hit the pre-check,
    skip the fetch + fit cost, log ``daily_curves.skip_existing`` and
    continue. No UNIQUE violation, no exit 3.
    """
    _insert_spot_row(db_session_in_memory, "US", OBSERVATION_DATE)
    assert _curve_already_persisted(db_session_in_memory, "US", OBSERVATION_DATE)


def test_curve_already_persisted_discriminates_country(db_session_in_memory: Session) -> None:
    """UNIQUE is ``(country, date, method)`` — US row does not mask a
    missing DE row on the same date.
    """
    _insert_spot_row(db_session_in_memory, "US", OBSERVATION_DATE)
    assert _curve_already_persisted(db_session_in_memory, "US", OBSERVATION_DATE)
    assert not _curve_already_persisted(db_session_in_memory, "DE", OBSERVATION_DATE)


def test_curve_already_persisted_discriminates_date(db_session_in_memory: Session) -> None:
    """Different observation_date for the same country → not masked."""
    _insert_spot_row(db_session_in_memory, "US", OBSERVATION_DATE)
    other = date(2024, 12, 31)
    assert not _curve_already_persisted(db_session_in_memory, "US", other)


def test_curve_run_outcomes_default_is_empty() -> None:
    """Default-constructed outcomes bucket starts empty across all four
    slots. Summary-emit Principle 4 depends on this invariant.
    """
    outcomes = _CurveRunOutcomes()
    assert outcomes.persisted == []
    assert outcomes.skipped_existing == []
    assert outcomes.skipped_insufficient == []
    assert outcomes.failed == []
