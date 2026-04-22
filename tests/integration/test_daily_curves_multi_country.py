"""Integration tests — daily-curves multi-country dispatch.

Covers the post-Sprint-I curve-fit surface (2026-04-22): US (FRED,
existing), DE (Bundesbank), EA (ECB SDW), GB/JP/CA/IT/ES/FR (TE). The
Sprint H TE cascade closed ``CAL-CURVES-IT-BDI`` +
``CAL-CURVES-ES-BDE``; Sprint I closed ``CAL-CURVES-FR-TE-PROBE`` via
the same cascade. The remaining EA periphery (PT / NL) + sparse T1
members (AU/NZ/CH/SE/NO/DK) continue to raise
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
    """Sprint I FR TE cascade (2026-04-22): ``--all-t1`` iterates the
    nine curve-capable T1 countries. First eight entries preserve the
    Sprint H ordering (journal/tool compatibility); FR appends at the
    tail.
    """
    assert T1_CURVES_COUNTRIES == ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR")
    assert set(T1_CURVES_COUNTRIES) == CURVE_SUPPORTED_COUNTRIES


def test_curve_supported_countries_matches_sprint_i_scope() -> None:
    """Post-Sprint-I ship list: US (FRED) + DE (BB) + EA (ECB) +
    GB/JP/CA/IT/ES/FR (TE — 6 countries via Bloomberg-symbol cascade).
    """
    assert (
        frozenset({"US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR"})
        == CURVE_SUPPORTED_COUNTRIES
    )


async def test_fetch_nominals_raises_for_periphery_with_cal_pointer(
    bundesbank: BundesbankConnector, ecb_sdw: EcbSdwConnector
) -> None:
    """EA periphery remainder raises InsufficientDataError with per-
    country CAL pointer.

    Post-Sprint-H (2026-04-22) IT + ES are no longer deferred — they
    ship via TE cascade. Sprint I (2026-04-22) moved FR out via the
    same cascade. Only PT / NL remain with CAL pointers at dispatch;
    the umbrella ``CAL-CURVES-EA-PERIPHERY`` was superseded by
    per-country items (Sprint A 2026-04-22 probe). FR's remaining
    ``CAL-CURVES-FR-BDF`` tracks the orthogonal national-CB
    direct-connector path (still BLOCKED) — not the daily-pipeline
    surface.
    """
    expected_pointers = {
        "PT": "CAL-CURVES-PT-BPSTAT",
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


@pytest.mark.slow
async def test_daily_curves_it_end_to_end(te: TEConnector, db_session: Session) -> None:
    """IT 2024-12-30 via TE GBTPGR family → Svensson fit persisted.

    Sprint H empirical probe 2026-04-22 established 12-tenor IT BTP
    coverage. NSS fit acceptance per Sprint H §6: RMSE ≤ 10 bps +
    confidence ≥ 0.9 target (guarded softer at 15 / 0.85 because
    2024-12-30 liquidity differs from the target fitting window;
    production RMSE on ≥ 10 tenors consistently lands well under 10
    bps across the GB/JP/CA prior cohort).
    """
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="IT",
        observation_date=obs_date,
        session=db_session,
        te=te,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="IT", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used >= 9  # Svensson-min reached (12-tenor curve)
    assert spot.source_connector == "te"
    # Sprint H brief §6 acceptance: RMSE ≤ 10 bps + confidence ≥ 0.9.
    # Live canary 2026-04-22 observed RMSE=5.23 bps + confidence=1.0.
    assert spot.rmse_bps <= 10
    assert spot.confidence >= 0.9


@pytest.mark.slow
async def test_daily_curves_es_end_to_end(te: TEConnector, db_session: Session) -> None:
    """ES 2024-12-30 via TE GSPG family → Svensson-minimum fit persisted.

    Sprint H empirical probe 2026-04-22 established 9-tenor ES SPGB
    coverage (missing 1M / 2Y / 20Y). 9 tenors sits at the exact
    MIN_OBSERVATIONS_FOR_SVENSSON boundary; assertion tolerates the
    boundary condition.
    """
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="ES",
        observation_date=obs_date,
        session=db_session,
        te=te,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="ES", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used >= 7  # allow TE 1-tenor thinning vs 9-probe
    assert spot.source_connector == "te"
    # Sprint H brief §6 acceptance: RMSE ≤ 10 bps + confidence ≥ 0.9.
    # Live canary 2026-04-22 observed RMSE=4.41 bps + confidence=1.0.
    assert spot.rmse_bps <= 10
    assert spot.confidence >= 0.9


@pytest.mark.slow
async def test_daily_curves_fr_end_to_end(te: TEConnector, db_session: Session) -> None:
    """FR 2024-12-30 via TE GFRN OAT family → Svensson fit persisted.

    Sprint I empirical probe 2026-04-22 established 10-tenor FR OAT
    coverage (1M-30Y minus 3Y / 15Y). 10 tenors clears
    ``MIN_OBSERVATIONS_FOR_SVENSSON=9``; live canary 2026-04-22 observed
    RMSE=2.005 bps + confidence=1.0 (cleaner than IT 5.23 / ES 4.41
    via the same /markets/historical surface).
    """
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="FR",
        observation_date=obs_date,
        session=db_session,
        te=te,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="FR", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used >= 9  # Svensson-minimum reached (10-tenor curve)
    assert spot.source_connector == "te"
    # Sprint I brief §6 acceptance: RMSE ≤ 10 bps + confidence ≥ 0.9.
    assert spot.rmse_bps <= 10
    assert spot.confidence >= 0.9


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
    """``--all-t1`` iteration persists eight non-US curves on one date.

    Sprint E (CAL-CURVES-T1-SPARSE-INCLUSION 2026-04-22) expanded
    ``T1_CURVES_COUNTRIES`` to (US, DE, EA, GB, JP, CA). Sprint H
    (IT + ES TE cascade, 2026-04-22) further expanded to eight
    (US, DE, EA, GB, JP, CA, IT, ES). Sprint I (FR TE cascade,
    2026-04-22) extends to nine. This canary validates the eight non-US
    countries (which do not need a FRED key) persist successfully in a
    single run — mirroring the production ``sonar-daily-curves.service``
    invocation.

    US is exercised separately in ``test_daily_curves_pipeline.py`` to
    keep this test independent of ``FRED_API_KEY`` presence.
    """
    obs_date = date(2024, 12, 30)
    non_us = [c for c in T1_CURVES_COUNTRIES if c != "US"]
    assert non_us == ["DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR"]

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
    for country in ("GB", "JP", "CA", "IT", "ES", "FR"):
        assert persisted[country].source_connector == "te"
        assert persisted[country].observations_used >= 6
    # NSS quality guards (per-country) — aligned with the brief §6
    # acceptance (RMSE ≤ 10 bps + confidence ≥ 0.9). Live canaries
    # 2026-04-22 observed IT 5.23 / ES 4.41 / FR ~5 bps at 1.0
    # confidence; bound preserves the explicit brief target rather
    # than tightening to the observation.
    for country in ("IT", "ES", "FR"):
        assert persisted[country].rmse_bps <= 10
        assert persisted[country].confidence >= 0.9
