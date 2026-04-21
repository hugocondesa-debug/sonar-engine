"""Unit tests for overlays/live_assemblers.py (Sprint 7F).

Each live builder is exercised with a minimal fake connector — real
HTTP, cache, and disk IO are bypassed so the test runs in-process with
no network. The schema-drift + graceful-degradation paths are the
focus; full wire-level tests live in the C6/C7 integration suites.
"""

from __future__ import annotations

import types
from datetime import date
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sonar.connectors.damodaran import DamodaranERPRow
from sonar.connectors.multpl import DataUnavailableError
from sonar.connectors.shiller import ShillerSnapshot
from sonar.db.models import Base, RatingsAgencyRaw
from sonar.overlays.live_assemblers import (
    LiveConnectorSuite,
    LiveInputsBuilder,
    build_erp_us_from_live,
    build_rating_from_live,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


OBS_DATE = date(2024, 12, 31)


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


class _FakeFMP:
    def __init__(self, close: float = 5881.63, n_rows: int = 10) -> None:
        self.close = close
        self.n_rows = n_rows

    async def fetch_index_historical(self, symbol: str, start: date, end: date) -> list[Any]:
        _ = symbol, start
        rows = []
        for i in range(self.n_rows):
            rows.append(
                types.SimpleNamespace(
                    symbol_sonar="SPX",
                    symbol_fmp="^GSPC",
                    observation_date=end,
                    close=self.close + i,
                    volume=None,
                )
            )
        return rows


class _EmptyFMP:
    async def fetch_index_historical(self, symbol: str, start: date, end: date) -> list[Any]:
        _ = symbol, start, end
        return []


class _RaisingFMP:
    async def fetch_index_historical(self, symbol: str, start: date, end: date) -> list[Any]:
        _ = symbol, start, end
        raise httpx.ConnectError("network down")


def _make_shiller(price: float = 5881.0, earnings: float = 205.0, cape: float = 37.5) -> Any:
    class _FakeShiller:
        async def fetch_snapshot(self, observation_date: date) -> ShillerSnapshot:
            _ = observation_date
            return ShillerSnapshot(
                observation_date=OBS_DATE,
                price_nominal=price,
                dividend_nominal=price * 0.012,  # ~1.2% yield
                earnings_nominal=earnings,
                cpi=310.0,
                long_rate_pct=4.55,
                real_price=price * 0.9,
                real_earnings_10y_avg=earnings * 0.7,
                cape_ratio=cape,
            )

    return _FakeShiller()


class _FakeMultpl:
    def __init__(self, decimal_yield: float = 0.012) -> None:
        self.value = decimal_yield

    async def fetch_current_dividend_yield_decimal(self) -> float:
        return self.value


class _RaisingMultpl:
    async def fetch_current_dividend_yield_decimal(self) -> float:
        raise DataUnavailableError("multpl parse failed")


class _FakeDamodaran:
    def __init__(self, row: DamodaranERPRow | None) -> None:
        self._row = row

    async def fetch_annual_erp(self, year: int) -> DamodaranERPRow | None:
        _ = year
        return self._row


# ---------------------------------------------------------------------------
# CAL-109 — build_erp_us_from_live
# ---------------------------------------------------------------------------


class TestBuildERPUSFromLive:
    @pytest.mark.asyncio
    async def test_happy_path_assembles_full_input(self) -> None:
        fmp = _FakeFMP(close=5881.63)
        shiller = _make_shiller(cape=37.5, earnings=205.0)
        multpl = _FakeMultpl(decimal_yield=0.0125)
        damodaran = _FakeDamodaran(
            DamodaranERPRow(year=2024, implied_erp_decimal=0.0451, source_column="x")
        )
        result = await build_erp_us_from_live(
            OBS_DATE,
            fmp=fmp,  # type: ignore[arg-type]
            shiller=shiller,
            multpl=multpl,  # type: ignore[arg-type]
            damodaran=damodaran,  # type: ignore[arg-type]
            risk_free_nominal_pct=0.0455,
            risk_free_real_pct=0.0205,
        )
        assert result is not None
        assert result.market_index == "SPX"
        assert result.country_code == "US"
        assert result.observation_date == OBS_DATE
        assert result.index_level == pytest.approx(5881.63 + 9)  # last (ascending) row
        assert result.cape_ratio == pytest.approx(37.5)
        assert result.trailing_earnings == pytest.approx(205.0)
        assert result.forward_earnings_est == pytest.approx(205.0)
        assert result.dividend_yield_pct == pytest.approx(0.0125)
        assert result.risk_free_nominal == pytest.approx(0.0455)
        assert result.risk_free_real == pytest.approx(0.0205)
        assert "FORWARD_EPS_PROXY_TRAILING" in result.upstream_flags
        # Damodaran row present → no UNAVAILABLE flag.
        assert "DAMODARAN_XVAL_UNAVAILABLE" not in result.upstream_flags

    @pytest.mark.asyncio
    async def test_fmp_empty_returns_none(self) -> None:
        result = await build_erp_us_from_live(
            OBS_DATE,
            fmp=_EmptyFMP(),  # type: ignore[arg-type]
            shiller=_make_shiller(),
            risk_free_nominal_pct=0.04,
            risk_free_real_pct=0.02,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_fmp_http_error_returns_none(self) -> None:
        result = await build_erp_us_from_live(
            OBS_DATE,
            fmp=_RaisingFMP(),  # type: ignore[arg-type]
            shiller=_make_shiller(),
            risk_free_nominal_pct=0.04,
            risk_free_real_pct=0.02,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_multpl_error_falls_back_to_shiller_dividend(self) -> None:
        result = await build_erp_us_from_live(
            OBS_DATE,
            fmp=_FakeFMP(close=5800.0, n_rows=1),  # type: ignore[arg-type]
            shiller=_make_shiller(price=5800.0),
            multpl=_RaisingMultpl(),  # type: ignore[arg-type]
            risk_free_nominal_pct=0.04,
            risk_free_real_pct=0.02,
        )
        assert result is not None
        # Shiller fallback: D/P = 0.012 by construction.
        assert result.dividend_yield_pct == pytest.approx(0.012)
        assert "DIVIDEND_YIELD_FALLBACK_SHILLER" in result.upstream_flags

    @pytest.mark.asyncio
    async def test_multpl_none_flags_fallback(self) -> None:
        result = await build_erp_us_from_live(
            OBS_DATE,
            fmp=_FakeFMP(close=5800.0, n_rows=1),  # type: ignore[arg-type]
            shiller=_make_shiller(price=5800.0),
            risk_free_nominal_pct=0.04,
            risk_free_real_pct=0.02,
        )
        assert result is not None
        assert "DIVIDEND_YIELD_FALLBACK_SHILLER" in result.upstream_flags

    @pytest.mark.asyncio
    async def test_damodaran_missing_year_flags_unavailable(self) -> None:
        result = await build_erp_us_from_live(
            OBS_DATE,
            fmp=_FakeFMP(close=5800.0, n_rows=1),  # type: ignore[arg-type]
            shiller=_make_shiller(),
            damodaran=_FakeDamodaran(None),  # type: ignore[arg-type]
            risk_free_nominal_pct=0.04,
            risk_free_real_pct=0.02,
        )
        assert result is not None
        assert "DAMODARAN_XVAL_UNAVAILABLE" in result.upstream_flags

    @pytest.mark.asyncio
    async def test_damodaran_absent_flags_skipped(self) -> None:
        result = await build_erp_us_from_live(
            OBS_DATE,
            fmp=_FakeFMP(close=5800.0, n_rows=1),  # type: ignore[arg-type]
            shiller=_make_shiller(),
            risk_free_nominal_pct=0.04,
            risk_free_real_pct=0.02,
        )
        assert result is not None
        assert "DAMODARAN_XVAL_SKIPPED" in result.upstream_flags


# ---------------------------------------------------------------------------
# CAL-111 — build_rating_from_live
# ---------------------------------------------------------------------------


def _seed_agency_rows(session: Session, country: str = "US") -> None:
    session.add_all(
        [
            RatingsAgencyRaw(
                rating_id="rid-sp",
                country_code=country,
                date=OBS_DATE,
                agency="SP",
                rating_type="FC",
                rating_raw="AA+",
                sonar_notch_base=20,
                outlook="stable",
                watch=None,
                notch_adjusted=20.0,
                action_date=date(2024, 6, 15),
                source_connector="seed",
                methodology_version="RATING_AGENCY_v0.1",
                confidence=1.0,
                flags=None,
            ),
            RatingsAgencyRaw(
                rating_id="rid-moodys",
                country_code=country,
                date=OBS_DATE,
                agency="MOODYS",
                rating_type="FC",
                rating_raw="Aaa",
                sonar_notch_base=21,
                outlook="stable",
                watch=None,
                notch_adjusted=21.0,
                action_date=date(2024, 7, 20),
                source_connector="seed",
                methodology_version="RATING_AGENCY_v0.1",
                confidence=1.0,
                flags=None,
            ),
        ]
    )
    session.commit()


class TestBuildRatingFromLive:
    @pytest.mark.asyncio
    async def test_reads_persisted_rows(self, db_session: Session) -> None:
        _seed_agency_rows(db_session, "US")
        kwargs = await build_rating_from_live(
            "US",
            OBS_DATE,
            session=db_session,
        )
        assert kwargs is not None
        rows = kwargs["rows"]
        assert len(rows) == 2
        agencies = {r.agency for r in rows}
        assert agencies == {"SP", "MOODYS"}

    @pytest.mark.asyncio
    async def test_no_rows_returns_none(self, db_session: Session) -> None:
        kwargs = await build_rating_from_live(
            "XX",
            OBS_DATE,
            session=db_session,
        )
        assert kwargs is None

    @pytest.mark.asyncio
    async def test_unknown_token_drops_row(self, db_session: Session) -> None:
        db_session.add(
            RatingsAgencyRaw(
                rating_id="rid-bad",
                country_code="US",
                date=OBS_DATE,
                agency="SP",
                rating_type="FC",
                rating_raw="AA++",  # invalid token — not in lookup
                sonar_notch_base=20,
                outlook="stable",
                watch=None,
                notch_adjusted=20.0,
                action_date=date(2024, 1, 1),
                source_connector="seed",
                methodology_version="RATING_AGENCY_v0.1",
                confidence=1.0,
                flags=None,
            )
        )
        db_session.commit()
        kwargs = await build_rating_from_live("US", OBS_DATE, session=db_session)
        # The only row was invalid → None (zero usable rows).
        assert kwargs is None

    @pytest.mark.asyncio
    async def test_rating_type_filter_respected(self, db_session: Session) -> None:
        _seed_agency_rows(db_session, "US")
        kwargs = await build_rating_from_live(
            "US",
            OBS_DATE,
            session=db_session,
            rating_type="LC",  # nothing seeded for LC
        )
        assert kwargs is None


# ---------------------------------------------------------------------------
# LiveInputsBuilder
# ---------------------------------------------------------------------------


class TestLiveInputsBuilder:
    def test_builder_us_full_stack(self, db_session: Session) -> None:
        _seed_agency_rows(db_session, "US")
        suite = LiveConnectorSuite(
            fmp=_FakeFMP(close=5800.0, n_rows=1),  # type: ignore[arg-type]
            shiller=_make_shiller(),
            te=MagicMock(),
            multpl=_FakeMultpl(),  # type: ignore[arg-type]
            damodaran=_FakeDamodaran(None),  # type: ignore[arg-type]
        )
        # TE mock — has to return empty list so SOV_SPREAD path is skipped
        # cleanly (US is benchmark anyway → BENCHMARK shortcut).
        builder = LiveInputsBuilder(
            suite,
            risk_free_resolver=lambda _s, _c, _d: (0.0455, 0.0205, 0.95),
        )
        bundle = builder(db_session, "US", OBS_DATE)
        assert bundle.country_code == "US"
        assert bundle.observation_date == OBS_DATE
        assert bundle.erp is not None
        assert bundle.erp.market_index == "SPX"
        # US → BENCHMARK short-circuit (crp kwargs present, no methods).
        assert bundle.crp is not None
        assert bundle.crp["sov_spread"] is None
        assert bundle.rating is not None
        assert bundle.rating["rows"]

    def test_builder_non_us_skips_erp(self, db_session: Session) -> None:
        suite = LiveConnectorSuite(
            fmp=_FakeFMP(),  # type: ignore[arg-type]
            shiller=_make_shiller(),
            te=MagicMock(),
        )
        builder = LiveInputsBuilder(suite)
        bundle = builder(db_session, "DE", OBS_DATE)
        assert bundle.erp is None  # no risk_free_resolver for non-US

    def test_risk_free_resolver_error_logged(self, db_session: Session) -> None:
        def _raising(_s: Any, _c: str, _d: date) -> Any:
            raise RuntimeError("NSS lookup failed")

        suite = LiveConnectorSuite(
            fmp=_FakeFMP(),  # type: ignore[arg-type]
            shiller=_make_shiller(),
            te=MagicMock(),
        )
        builder = LiveInputsBuilder(suite, risk_free_resolver=_raising)
        bundle = builder(db_session, "US", OBS_DATE)
        # Resolver raised → rf_tuple stays None → ERP is not built.
        assert bundle.erp is None
