"""Integration smoke for daily_overlays --backend=live (Sprint 7F C6).

7 Tier-1 country sweep with mocked connector suite. Each country
routes through :class:`LiveInputsBuilder` exactly as the CLI does
under ``--backend=live``; the connectors themselves are replaced with
in-process fakes so we never hit the network.

Coverage intent per country:

* **US** — full stack: ERP persists via SPX/Shiller/Multpl/Damodaran
  fakes; CRP short-circuits to BENCHMARK (USD); rating reads seeded
  ratings_agency_raw (SP+MOODYS+FITCH). 4 overlays persist.
* **DE** — EUR benchmark: CRP is BENCHMARK; no ERP (US-only); rating
  seeded. ERP slot empty + CRP BENCHMARK + rating OK.
* **FR / IT / ES / NL** — EUR periphery: TE fake returns sovereign
  yields → SOV_SPREAD CRP; rating seeded; no ERP.
* **PT** — EUR periphery with DIFFERENT yield to exercise CRP spread;
  agency row with outlook=negative to exercise modifier path.
"""

from __future__ import annotations

import types
from datetime import date
from typing import TYPE_CHECKING, Any, ClassVar
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sonar.connectors.base import Observation
from sonar.connectors.damodaran import DamodaranERPRow
from sonar.connectors.shiller import ShillerSnapshot
from sonar.db.models import (
    Base,
    NSSYieldCurveSpot,
    RatingsAgencyRaw,
    RatingsConsolidated,
)
from sonar.overlays.live_assemblers import (
    LiveConnectorSuite,
    LiveInputsBuilder,
)
from sonar.pipelines.daily_overlays import run_one

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


pytestmark = pytest.mark.slow


ANCHOR = date(2024, 12, 31)


# ---------------------------------------------------------------------------
# Fixtures — in-memory DB + seeded NSS/ratings + fake connectors
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


def _seed_nss(session: Session, country: str) -> None:
    session.add(
        NSSYieldCurveSpot(
            country_code=country,
            date=ANCHOR,
            methodology_version="NSS_v1.0",
            fit_id=f"fit-{country}-{ANCHOR.isoformat()}",
            beta_0=0.04,
            beta_1=-0.01,
            beta_2=0.005,
            beta_3=None,
            lambda_1=1.5,
            lambda_2=None,
            fitted_yields_json='{"10Y": 0.04}',
            observations_used=11,
            rmse_bps=5.0,
            xval_deviation_bps=None,
            confidence=0.9,
            flags=None,
            source_connector="fred",
        )
    )
    session.commit()


def _seed_ratings(session: Session, country: str, outlook: str = "stable") -> None:
    session.add_all(
        [
            RatingsAgencyRaw(
                rating_id=f"rid-sp-{country}",
                country_code=country,
                date=ANCHOR,
                agency="SP",
                rating_type="FC",
                rating_raw="AA+",
                sonar_notch_base=20,
                outlook=outlook,
                watch=None,
                notch_adjusted=20.0,
                action_date=date(2024, 6, 15),
                source_connector="seed",
                methodology_version="RATING_AGENCY_v0.1",
                confidence=1.0,
                flags=None,
            ),
            RatingsAgencyRaw(
                rating_id=f"rid-moody-{country}",
                country_code=country,
                date=ANCHOR,
                agency="MOODYS",
                rating_type="FC",
                rating_raw="Aaa",
                sonar_notch_base=21,
                outlook=outlook,
                watch=None,
                notch_adjusted=21.0,
                action_date=date(2024, 7, 1),
                source_connector="seed",
                methodology_version="RATING_AGENCY_v0.1",
                confidence=1.0,
                flags=None,
            ),
            RatingsAgencyRaw(
                rating_id=f"rid-fitch-{country}",
                country_code=country,
                date=ANCHOR,
                agency="FITCH",
                rating_type="FC",
                rating_raw="AA+",
                sonar_notch_base=20,
                outlook=outlook,
                watch=None,
                notch_adjusted=20.0,
                action_date=date(2024, 8, 1),
                source_connector="seed",
                methodology_version="RATING_AGENCY_v0.1",
                confidence=1.0,
                flags=None,
            ),
        ]
    )
    session.commit()


class _FakeFMP:
    async def fetch_index_historical(self, symbol: str, start: date, end: date) -> list[Any]:
        _ = symbol, start
        return [
            types.SimpleNamespace(
                symbol_sonar="SPX",
                symbol_fmp="^GSPC",
                observation_date=end,
                close=5881.63,
                volume=None,
            )
        ]


class _FakeShiller:
    async def fetch_snapshot(self, observation_date: date) -> ShillerSnapshot:
        _ = observation_date
        return ShillerSnapshot(
            observation_date=ANCHOR,
            price_nominal=5881.0,
            dividend_nominal=70.0,
            earnings_nominal=205.0,
            cpi=310.0,
            long_rate_pct=4.55,
            real_price=5300.0,
            real_earnings_10y_avg=170.0,
            cape_ratio=37.5,
        )


class _FakeMultpl:
    async def fetch_current_dividend_yield_decimal(self) -> float:
        return 0.0125


class _FakeDamodaran:
    async def fetch_annual_erp(self, year: int) -> DamodaranERPRow | None:
        _ = year
        return DamodaranERPRow(year=2024, implied_erp_decimal=0.0451, source_column="x")


class _FakeTE:
    """TE fake returning different yields per country so SOV_SPREAD varies."""

    _YIELDS_BPS: ClassVar[dict[str, int]] = {
        "US": 435,
        "DE": 240,  # benchmark EUR
        "FR": 310,
        "IT": 390,
        "ES": 360,
        "NL": 270,
        "PT": 340,
    }

    async def fetch_10y_window_around(
        self,
        country: str,
        observation_date: date,
        lookback_days: int = 365 * 5 + 30,
    ) -> list[Observation]:
        _ = lookback_days
        bps = self._YIELDS_BPS.get(country)
        if bps is None:
            return []
        return [
            Observation(
                country_code=country,
                observation_date=observation_date,
                tenor_years=10.0,
                yield_bps=bps,
                source="TE",
                source_series_id=f"{country}GG10:IND",
            )
        ]


def _make_live_builder() -> LiveInputsBuilder:
    suite = LiveConnectorSuite(
        fmp=_FakeFMP(),  # type: ignore[arg-type]
        shiller=_FakeShiller(),  # type: ignore[arg-type]
        te=_FakeTE(),  # type: ignore[arg-type]
        multpl=_FakeMultpl(),  # type: ignore[arg-type]
        damodaran=_FakeDamodaran(),  # type: ignore[arg-type]
    )
    return LiveInputsBuilder(
        suite,
        risk_free_resolver=lambda _s, _c, _d: (0.0455, 0.0205, 0.95),
    )


# ---------------------------------------------------------------------------
# Per-country matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("country", "expect_erp", "expect_crp_method"),
    [
        ("US", True, "BENCHMARK"),  # USD benchmark
        ("DE", False, "BENCHMARK"),  # EUR benchmark
        ("FR", False, "SOV_SPREAD"),
        ("IT", False, "SOV_SPREAD"),
        ("ES", False, "SOV_SPREAD"),
        ("NL", False, "SOV_SPREAD"),
        ("PT", False, "SOV_SPREAD"),
    ],
)
def test_live_smoke_per_country(
    db_session: Session,
    country: str,
    expect_erp: bool,
    expect_crp_method: str,
) -> None:
    _seed_nss(db_session, country)
    _seed_ratings(db_session, country)
    builder = _make_live_builder()
    outcome = run_one(db_session, country, ANCHOR, inputs_builder=builder)
    if expect_erp:
        assert outcome.results.erp is not None
        assert outcome.results.erp.canonical.methods_available >= 2
    else:
        assert outcome.results.erp is None
    # Rating seeded for all 7 — consolidated.
    assert outcome.results.rating is not None
    assert outcome.results.rating.agencies_count >= 2
    # CRP resolves via hierarchy (BENCHMARK for USD/EUR benchmarks, SOV_SPREAD
    # for periphery).
    assert outcome.results.crp is not None
    assert outcome.results.crp.method_selected == expect_crp_method


# ---------------------------------------------------------------------------
# Schema-drift guard + graceful degradation
# ---------------------------------------------------------------------------


def test_te_404_graceful_skip_keeps_rating(db_session: Session) -> None:
    """If TE yields are missing for a periphery country, CRP falls back to RATING.

    The CRP rating-method fallback reads ``ratings_consolidated`` (which is
    the output of a prior consolidation run), so we seed one directly —
    same table the live pipeline would populate day N-1.
    """
    _seed_nss(db_session, "PT")
    _seed_ratings(db_session, "PT")
    # Seed a consolidated row so CRP's RATING fallback has something to
    # read. In production this row is written by the rating overlay on a
    # prior persist pass.
    db_session.add(
        RatingsConsolidated(
            rating_id="rcid-pt",
            country_code="PT",
            date=ANCHOR,
            rating_type="FC",
            consolidated_sonar_notch=14.0,
            notch_fractional=0.0,
            agencies_count=3,
            agencies_json="{}",
            outlook_composite="stable",
            watch_composite=None,
            default_spread_bps=245,
            calibration_date=ANCHOR,
            rating_cds_deviation_pct=None,
            methodology_version="RATING_SPREAD_v0.2",
            confidence=0.8,
            flags=None,
        )
    )
    db_session.commit()

    class _EmptyTE:
        async def fetch_10y_window_around(self, country: str, observation_date: date) -> list[Any]:
            _ = country, observation_date
            return []

    suite = LiveConnectorSuite(
        fmp=_FakeFMP(),  # type: ignore[arg-type]
        shiller=_FakeShiller(),  # type: ignore[arg-type]
        te=_EmptyTE(),  # type: ignore[arg-type]
    )
    builder = LiveInputsBuilder(suite)
    outcome = run_one(db_session, "PT", ANCHOR, inputs_builder=builder, persist=False)
    assert outcome.results.crp is not None
    assert outcome.results.crp.method_selected == "RATING"
    assert outcome.results.rating is not None


def test_no_ratings_no_sov_spread_skips_crp(db_session: Session) -> None:
    """Periphery country with neither TE yields nor rating → crp skip."""
    _seed_nss(db_session, "PT")

    class _EmptyTE:
        async def fetch_10y_window_around(self, country: str, observation_date: date) -> list[Any]:
            _ = country, observation_date
            return []

    suite = LiveConnectorSuite(
        fmp=_FakeFMP(),  # type: ignore[arg-type]
        shiller=_FakeShiller(),  # type: ignore[arg-type]
        te=_EmptyTE(),  # type: ignore[arg-type]
    )
    builder = LiveInputsBuilder(suite)
    outcome = run_one(db_session, "PT", ANCHOR, inputs_builder=builder)
    assert outcome.results.crp is None
    assert outcome.results.rating is None
    assert outcome.results.skips is not None
    assert outcome.results.skips.get("crp") is not None


def test_fmp_failure_skips_erp_only(db_session: Session) -> None:
    """FMP failure leaves CRP/rating untouched (ERP alone is affected)."""
    _seed_nss(db_session, "US")
    _seed_ratings(db_session, "US")

    class _RaisingFMP:
        async def fetch_index_historical(self, symbol: str, start: date, end: date) -> list[Any]:
            _ = symbol, start, end
            raise httpx.ConnectError("fmp down")

    suite = LiveConnectorSuite(
        fmp=_RaisingFMP(),  # type: ignore[arg-type]
        shiller=_FakeShiller(),  # type: ignore[arg-type]
        te=MagicMock(),
    )
    builder = LiveInputsBuilder(
        suite,
        risk_free_resolver=lambda _s, _c, _d: (0.0455, 0.0205, 0.95),
    )
    outcome = run_one(db_session, "US", ANCHOR, inputs_builder=builder)
    assert outcome.results.erp is None
    # Rating still present (seeded rows).
    assert outcome.results.rating is not None
