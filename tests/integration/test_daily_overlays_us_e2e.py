"""End-to-end US canary for daily_overlays --backend=live (Sprint 7F C7).

One canonical US run with realistic Dec-2024 inputs. Asserts that:

- ERP persists with ≥3 of 4 methods available (DCF / Gordon / EY / CAPE).
- ERP canonical ``methodology_version`` is ``ERP_CANONICAL_v0.1``.
- The FORWARD_EPS_PROXY_TRAILING flag is emitted on the ERP result
  (forward-EPS connector not wired in this sprint).
- CRP resolves to BENCHMARK (USD) with 0 bps.
- Rating consolidates 3 agencies (SP+MOODYS+FITCH) at Aaa/AA+ notches.
- All three overlays land in their ORM tables via
  ``persist_many_overlay_results``.

No network — connectors are fakes seeded with plausible values.
"""

from __future__ import annotations

import types
from datetime import date
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from sonar.connectors.damodaran import DamodaranERPRow
from sonar.connectors.shiller import ShillerSnapshot
from sonar.db.models import (
    Base,
    ERPCanonical,
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


# ---------------------------------------------------------------------------
# Realistic Dec-2024 connector fakes
# ---------------------------------------------------------------------------


class _FMP:
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


class _Shiller:
    async def fetch_snapshot(self, observation_date: date) -> ShillerSnapshot:
        _ = observation_date
        return ShillerSnapshot(
            observation_date=ANCHOR,
            price_nominal=5881.0,
            dividend_nominal=72.5,  # ~1.23 % yield
            earnings_nominal=205.0,
            cpi=315.0,
            long_rate_pct=4.55,
            real_price=5300.0,
            real_earnings_10y_avg=170.0,
            cape_ratio=37.5,
        )


class _Multpl:
    async def fetch_current_dividend_yield_decimal(self) -> float:
        return 0.0125


class _Damodaran:
    async def fetch_annual_erp(self, year: int) -> DamodaranERPRow | None:
        _ = year
        return DamodaranERPRow(
            year=2024,
            implied_erp_decimal=0.0451,
            source_column="Implied Premium (FCFE with sustainable Payout)",
        )


class _TE:
    async def fetch_10y_window_around(
        self, country: str, observation_date: date, lookback_days: int = 0
    ) -> list[Any]:
        _ = country, observation_date, lookback_days
        return []


def _seed_us_state(session: Session) -> None:
    session.add(
        NSSYieldCurveSpot(
            country_code="US",
            date=ANCHOR,
            methodology_version="NSS_v1.0",
            fit_id="fit-us-2024-12-31",
            beta_0=0.04,
            beta_1=-0.01,
            beta_2=0.005,
            beta_3=None,
            lambda_1=1.5,
            lambda_2=None,
            fitted_yields_json='{"10Y": 0.0455}',
            observations_used=11,
            rmse_bps=5.0,
            xval_deviation_bps=None,
            confidence=0.92,
            flags=None,
            source_connector="fred",
        )
    )
    for agency, raw_rating, notch in [
        ("SP", "AA+", 20),
        ("MOODYS", "Aaa", 21),
        ("FITCH", "AA+", 20),
    ]:
        session.add(
            RatingsAgencyRaw(
                rating_id=f"rid-{agency.lower()}-us",
                country_code="US",
                date=ANCHOR,
                agency=agency,
                rating_type="FC",
                rating_raw=raw_rating,
                sonar_notch_base=notch,
                outlook="stable",
                watch=None,
                notch_adjusted=float(notch),
                action_date=date(2024, 6, 15),
                source_connector="seed",
                methodology_version="RATING_AGENCY_v0.1",
                confidence=1.0,
                flags=None,
            )
        )
    session.commit()


def _build_live_suite() -> LiveInputsBuilder:
    suite = LiveConnectorSuite(
        fmp=_FMP(),  # type: ignore[arg-type]
        shiller=_Shiller(),  # type: ignore[arg-type]
        te=_TE(),  # type: ignore[arg-type]
        multpl=_Multpl(),  # type: ignore[arg-type]
        damodaran=_Damodaran(),  # type: ignore[arg-type]
    )
    return LiveInputsBuilder(
        suite,
        risk_free_resolver=lambda _s, _c, _d: (0.0455, 0.0205, 0.95),
    )


# ---------------------------------------------------------------------------
# Canary
# ---------------------------------------------------------------------------


class TestUSCanary:
    def test_us_full_stack_persists(self, db_session: Session) -> None:
        _seed_us_state(db_session)
        builder = _build_live_suite()
        outcome = run_one(db_session, "US", ANCHOR, inputs_builder=builder)

        # ERP: all 4 methods must be available with the complete bundle.
        assert outcome.results.erp is not None
        assert outcome.results.erp.canonical.methodology_version == "ERP_CANONICAL_v0.1"
        assert outcome.results.erp.canonical.methods_available >= 3
        # forward EPS was proxied via trailing — the flag must bubble.
        assert "FORWARD_EPS_PROXY_TRAILING" in outcome.results.erp.canonical.flags

        # CRP: USD benchmark → BENCHMARK method with 0 bps.
        assert outcome.results.crp is not None
        assert outcome.results.crp.method_selected == "BENCHMARK"
        assert outcome.results.crp.crp_canonical_bps == 0

        # Rating: 3 agencies consolidated.
        assert outcome.results.rating is not None
        assert outcome.results.rating.agencies_count == 3
        assert outcome.results.rating.notch_int in {20, 21}

        # Persistence check — each overlay lands in its table.
        erp_rows = (
            db_session.execute(select(ERPCanonical).where(ERPCanonical.country_code == "US"))
            .scalars()
            .all()
        )
        assert len(erp_rows) == 1
        assert erp_rows[0].methodology_version == "ERP_CANONICAL_v0.1"

        rating_rows = (
            db_session.execute(
                select(RatingsConsolidated).where(RatingsConsolidated.country_code == "US")
            )
            .scalars()
            .all()
        )
        assert len(rating_rows) == 1
        assert rating_rows[0].agencies_count == 3

        # Outcome dict: 3 overlays persisted; expected_inflation still empty
        # because the Sprint F builder does not wire BEI yet.
        assert outcome.persisted["erp"] == 1
        assert outcome.persisted["crp"] == 1
        assert outcome.persisted["rating"] == 1
        assert outcome.persisted["expected_inflation"] == 0
