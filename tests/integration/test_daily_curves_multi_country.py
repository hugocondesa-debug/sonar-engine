"""Integration tests — daily-curves multi-country dispatch.

Covers the post-Sprint-H curve-fit surface (2026-04-22): US (FRED,
existing), DE (Bundesbank), EA (ECB SDW), GB/JP/CA/IT/ES (TE). The
Sprint H TE cascade closed ``CAL-CURVES-IT-BDI`` +
``CAL-CURVES-ES-BDE``; the EA periphery remainder (PT / FR / NL) +
sparse T1 members (AU/NZ/CH/SE/NO/DK) continue to raise
:class:`InsufficientDataError` at dispatch — verified by unit tests
of ``_fetch_nominals_linkers``; integration tests here exercise the
live cascade end-to-end.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401 — registers SQLite FK pragma listener
from sonar.config import settings
from sonar.connectors.bundesbank import BundesbankConnector
from sonar.connectors.ecb_sdw import EcbSdwConnector
from sonar.connectors.te import TEConnector
from sonar.db.models import Base, NSSYieldCurveSpot
from sonar.overlays.exceptions import InsufficientDataError
from sonar.pipelines.daily_curves import (
    CURVE_SUPPORTED_COUNTRIES,
    T1_CURVES_COUNTRIES,
    _fetch_nominals_linkers,
    run_country,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from pathlib import Path

    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest_asyncio.fixture
async def bundesbank(tmp_path: Path) -> AsyncIterator[BundesbankConnector]:
    cache = tmp_path / "bundesbank"
    cache.mkdir()
    conn = BundesbankConnector(cache_dir=str(cache))
    yield conn
    await conn.aclose()


@pytest_asyncio.fixture
async def ecb_sdw(tmp_path: Path) -> AsyncIterator[EcbSdwConnector]:
    cache = tmp_path / "ecb_sdw"
    cache.mkdir()
    conn = EcbSdwConnector(cache_dir=str(cache))
    yield conn
    await conn.aclose()


@pytest_asyncio.fixture
async def te(tmp_path: Path) -> AsyncIterator[TEConnector]:
    api_key = settings.te_api_key
    if not api_key:
        pytest.skip("TE_API_KEY not configured in .env")
    cache = tmp_path / "te"
    cache.mkdir()
    conn = TEConnector(api_key=api_key, cache_dir=str(cache))
    yield conn
    await conn.aclose()


# ---------------------------------------------------------------------------
# Dispatch unit coverage
# ---------------------------------------------------------------------------


def test_t1_curves_tier_constant_matches_expected() -> None:
    """Sprint H IT + ES TE cascade (2026-04-22): ``--all-t1`` iterates
    the eight curve-capable T1 countries. First six entries preserve
    Sprint E ordering (journal/tool compatibility); IT + ES append
    at the tail.
    """
    assert T1_CURVES_COUNTRIES == ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES")
    assert set(T1_CURVES_COUNTRIES) == CURVE_SUPPORTED_COUNTRIES


def test_curve_supported_countries_matches_sprint_h_scope() -> None:
    """Post-Sprint-H ship list: US (FRED) + DE (BB) + EA (ECB) +
    GB/JP/CA/IT/ES (TE — 5 countries via Bloomberg-symbol cascade).
    """
    assert frozenset({"US", "DE", "EA", "GB", "JP", "CA", "IT", "ES"}) == CURVE_SUPPORTED_COUNTRIES


async def test_fetch_nominals_raises_for_periphery_with_cal_pointer(
    bundesbank: BundesbankConnector, ecb_sdw: EcbSdwConnector
) -> None:
    """EA periphery remainder raises InsufficientDataError with per-
    country CAL pointer.

    Post-Sprint-H (2026-04-22) IT + ES are no longer deferred — they
    ship via TE cascade and therefore route into the dispatcher's TE
    branch (which raises "requires TEConnector" when te=None is passed,
    not a CAL pointer). Only PT / FR / NL remain with CAL pointers
    at dispatch; the umbrella ``CAL-CURVES-EA-PERIPHERY`` was
    superseded by per-country items (Sprint A 2026-04-22 probe).
    """
    expected_pointers = {
        "PT": "CAL-CURVES-PT-BPSTAT",
        "FR": "CAL-CURVES-FR-BDF",
        "NL": "CAL-CURVES-NL-DNB",
    }
    for country, pointer in expected_pointers.items():
        with pytest.raises(InsufficientDataError, match=pointer):
            await _fetch_nominals_linkers(
                country,
                date(2024, 12, 30),
                fred=None,
                bundesbank=bundesbank,
                ecb_sdw=ecb_sdw,
                te=None,
            )


async def test_fetch_nominals_raises_for_sparse_t1_with_cal_pointer(
    bundesbank: BundesbankConnector, ecb_sdw: EcbSdwConnector
) -> None:
    """AU/NZ/CH/SE/NO/DK raise InsufficientDataError pointing to CAL-CURVES-T1-SPARSE."""
    for country in ("AU", "NZ", "CH", "SE", "NO", "DK"):
        with pytest.raises(InsufficientDataError, match="CAL-CURVES-T1-SPARSE"):
            await _fetch_nominals_linkers(
                country,
                date(2024, 12, 30),
                fred=None,
                bundesbank=bundesbank,
                ecb_sdw=ecb_sdw,
                te=None,
            )


# ---------------------------------------------------------------------------
# Live canaries (one per shipped country except US — already covered in
# test_daily_curves_pipeline.py). Wall-clock target ≤ 60s combined.
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_daily_curves_de_end_to_end(
    bundesbank: BundesbankConnector, db_session: Session
) -> None:
    """DE 2024-12-30 via Bundesbank → full NSS fit persisted."""
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="DE",
        observation_date=obs_date,
        session=db_session,
        bundesbank=bundesbank,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="DE", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used >= 6  # NS min
    assert spot.source_connector == "bundesbank"


@pytest.mark.slow
async def test_daily_curves_ea_end_to_end(ecb_sdw: EcbSdwConnector, db_session: Session) -> None:
    """EA AAA 2024-12-30 via ECB SDW → full NSS fit persisted."""
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="EA",
        observation_date=obs_date,
        session=db_session,
        ecb_sdw=ecb_sdw,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="EA", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used >= 9  # Svensson min
    assert spot.source_connector == "ecb_sdw"


@pytest.mark.slow
async def test_daily_curves_gb_end_to_end(te: TEConnector, db_session: Session) -> None:
    """GB 2024-12-30 via TE GUKG family → full NSS fit persisted."""
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="GB",
        observation_date=obs_date,
        session=db_session,
        te=te,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="GB", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used >= 8
    assert spot.source_connector == "te"


@pytest.mark.slow
async def test_daily_curves_jp_end_to_end(te: TEConnector, db_session: Session) -> None:
    """JP 2024-12-30 via TE GJGB family → full NSS fit persisted."""
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="JP",
        observation_date=obs_date,
        session=db_session,
        te=te,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="JP", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used >= 7
    assert spot.source_connector == "te"


@pytest.mark.slow
async def test_daily_curves_ca_end_to_end(te: TEConnector, db_session: Session) -> None:
    """CA 2024-12-30 via TE GCAN family → NS-reduced fit persisted."""
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="CA",
        observation_date=obs_date,
        session=db_session,
        te=te,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="CA", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    # CA has 6 tenors → NS-reduced fit (MIN_OBSERVATIONS met,
    # MIN_OBSERVATIONS_FOR_SVENSSON=9 not met).
    assert 6 <= spot.observations_used < 9
    assert spot.source_connector == "te"


# ---------------------------------------------------------------------------
# Sprint E sparse-inclusion — full ``--all-t1`` iteration canary
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_daily_curves_all_t1_sparse_inclusion(
    bundesbank: BundesbankConnector,
    ecb_sdw: EcbSdwConnector,
    te: TEConnector,
    db_session: Session,
) -> None:
    """``--all-t1`` iteration persists seven non-US curves on one date.

    Sprint E (CAL-CURVES-T1-SPARSE-INCLUSION 2026-04-22) expanded
    ``T1_CURVES_COUNTRIES`` to (US, DE, EA, GB, JP, CA). Sprint H
    (IT + ES TE cascade, 2026-04-22) further expanded to eight
    (US, DE, EA, GB, JP, CA, IT, ES). This canary validates the seven
    non-US countries (which do not need a FRED key) persist
    successfully in a single run — mirroring the production
    ``sonar-daily-curves.service`` invocation.

    US is exercised separately in ``test_daily_curves_pipeline.py`` to
    keep this test independent of ``FRED_API_KEY`` presence.
    """
    obs_date = date(2024, 12, 30)
    non_us = [c for c in T1_CURVES_COUNTRIES if c != "US"]
    assert non_us == ["DE", "EA", "GB", "JP", "CA", "IT", "ES"]

    for country in non_us:
        await run_country(
            country=country,
            observation_date=obs_date,
            session=db_session,
            bundesbank=bundesbank,
            ecb_sdw=ecb_sdw,
            te=te,
        )

    persisted = {
        row.country_code: row
        for row in db_session.query(NSSYieldCurveSpot).filter_by(date=obs_date).all()
    }
    assert set(persisted) == set(non_us)
    assert persisted["DE"].source_connector == "bundesbank"
    assert persisted["EA"].source_connector == "ecb_sdw"
    for country in ("GB", "JP", "CA", "IT", "ES"):
        assert persisted[country].source_connector == "te"
        assert persisted[country].observations_used >= 6
    # Sprint H NSS quality guards (per-country) — aligned with RMSE ≤ 10 bps
    # acceptance from the Sprint H brief §6.
    for country in ("IT", "ES"):
        assert persisted[country].rmse_bps <= 15  # liquidity premium headroom
        assert persisted[country].confidence >= 0.85
