"""Regression tests for Sprint Q — EXPINF live-assembler wiring.

Covers :mod:`sonar.indices.monetary.exp_inflation_loader` + the
:class:`LiveInputsBuilder` path that wires the loader into
:attr:`sonar.pipelines.daily_overlays.OverlayBundle.expected_inflation`.
See audit `docs/backlog/audits/sprint-q-expinf-wiring-audit.md` §6.4
for the test matrix rationale.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sonar.connectors.base import Observation
from sonar.db.models import Base
from sonar.indices.monetary.exp_inflation_loader import load_live_exp_inflation_kwargs
from sonar.overlays.expected_inflation import ExpInfBEI, ExpInfSurvey
from sonar.overlays.live_assemblers import LiveConnectorSuite, LiveInputsBuilder

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


OBS_DATE = date(2026, 4, 23)


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


def _obs(tenor_years: float, pct: float, series_id: str, obs_date: date = OBS_DATE) -> Observation:
    """Build an Observation mirroring FRED's bps encoding (percent * 100)."""
    return Observation(
        country_code="US",
        observation_date=obs_date,
        tenor_years=tenor_years,
        yield_bps=round(pct * 100),
        source="FRED",
        source_series_id=series_id,
    )


class _FakeFred:
    """Async-compatible fake FRED with configurable per-method behaviour."""

    def __init__(
        self,
        *,
        nominal: dict[str, Observation] | None = None,
        bei: dict[str, Observation] | None = None,
        survey: dict[str, Observation] | None = None,
        bei_error: Exception | None = None,
        survey_error: Exception | None = None,
        nominal_error: Exception | None = None,
    ) -> None:
        self._nominal = nominal or {}
        self._bei = bei or {}
        self._survey = survey or {}
        self._bei_error = bei_error
        self._survey_error = survey_error
        self._nominal_error = nominal_error

    async def fetch_yield_curve_nominal(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        if self._nominal_error is not None:
            raise self._nominal_error
        return self._nominal

    async def fetch_bei_series(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        if self._bei_error is not None:
            raise self._bei_error
        return self._bei

    async def fetch_survey_inflation(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        if self._survey_error is not None:
            raise self._survey_error
        return self._survey


def _full_us_fake_fred() -> _FakeFred:
    return _FakeFred(
        nominal={
            "5Y": _obs(5.0, 4.30, "DGS5"),
            "10Y": _obs(10.0, 4.55, "DGS10"),
        },
        bei={
            "5Y": _obs(5.0, 2.35, "T5YIE"),
            "10Y": _obs(10.0, 2.40, "T10YIE"),
        },
        survey={
            "MICH_1Y": _obs(1.0, 3.10, "MICH"),
            "SPF_10Y": _obs(10.0, 2.30, "EXPINF10YR"),
        },
    )


# ---------------------------------------------------------------------------
# load_live_exp_inflation_kwargs
# ---------------------------------------------------------------------------


class TestLoadLiveExpInflationKwargs:
    @pytest.mark.asyncio
    async def test_us_full_path_returns_both_bei_and_survey(self) -> None:
        kwargs = await load_live_exp_inflation_kwargs(
            "US",
            OBS_DATE,
            fred=_full_us_fake_fred(),  # type: ignore[arg-type]
        )
        assert kwargs is not None
        assert kwargs["country_code"] == "US"
        assert kwargs["observation_date"] == OBS_DATE
        assert kwargs["bc_target_pct"] == pytest.approx(0.02)
        assert isinstance(kwargs["bei"], ExpInfBEI)
        assert isinstance(kwargs["survey"], ExpInfSurvey)
        # BEI 5Y decimal = 235 / 10_000 = 0.0235 ; 5y5y present (from 5Y+10Y).
        assert kwargs["bei"].bei_tenors["5Y"] == pytest.approx(0.0235)
        assert kwargs["bei"].bei_tenors["10Y"] == pytest.approx(0.0240)
        assert "5y5y" in kwargs["bei"].bei_tenors
        # Survey 1Y = 310 bps / 10_000 ; 10Y = 230 bps / 10_000.
        assert kwargs["survey"].horizons["1Y"] == pytest.approx(0.031)
        assert kwargs["survey"].horizons["10Y"] == pytest.approx(0.023)

    @pytest.mark.asyncio
    async def test_us_bei_only_when_survey_fetch_errors(self) -> None:
        fake = _FakeFred(
            nominal={"10Y": _obs(10.0, 4.55, "DGS10")},
            bei={"10Y": _obs(10.0, 2.40, "T10YIE")},
            survey_error=httpx.HTTPError("FRED survey 500"),
        )
        kwargs = await load_live_exp_inflation_kwargs(
            "US",
            OBS_DATE,
            fred=fake,  # type: ignore[arg-type]
        )
        assert kwargs is not None
        assert kwargs["bei"] is not None
        assert kwargs["survey"] is None

    @pytest.mark.asyncio
    async def test_us_survey_only_when_bei_fetch_errors(self) -> None:
        fake = _FakeFred(
            bei_error=httpx.HTTPError("FRED BEI 500"),
            survey={
                "MICH_1Y": _obs(1.0, 3.10, "MICH"),
                "SPF_10Y": _obs(10.0, 2.30, "EXPINF10YR"),
            },
        )
        kwargs = await load_live_exp_inflation_kwargs(
            "US",
            OBS_DATE,
            fred=fake,  # type: ignore[arg-type]
        )
        assert kwargs is not None
        assert kwargs["bei"] is None
        assert kwargs["survey"] is not None

    @pytest.mark.asyncio
    async def test_us_no_sources_returns_none(self) -> None:
        fake = _FakeFred()  # all empty
        kwargs = await load_live_exp_inflation_kwargs(
            "US",
            OBS_DATE,
            fred=fake,  # type: ignore[arg-type]
        )
        assert kwargs is None

    @pytest.mark.asyncio
    async def test_us_http_error_returns_none_on_both_legs(self) -> None:
        fake = _FakeFred(
            bei_error=httpx.HTTPError("500"),
            survey_error=httpx.HTTPError("500"),
        )
        kwargs = await load_live_exp_inflation_kwargs(
            "US",
            OBS_DATE,
            fred=fake,  # type: ignore[arg-type]
        )
        assert kwargs is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("country", ["DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR"])
    async def test_non_us_returns_none(self, country: str) -> None:
        kwargs = await load_live_exp_inflation_kwargs(
            country,
            OBS_DATE,
            fred=_full_us_fake_fred(),  # type: ignore[arg-type]
        )
        assert kwargs is None

    @pytest.mark.asyncio
    async def test_us_fred_none_returns_none(self) -> None:
        kwargs = await load_live_exp_inflation_kwargs("US", OBS_DATE, fred=None)
        assert kwargs is None


# ---------------------------------------------------------------------------
# LiveInputsBuilder wiring — bundle.expected_inflation is populated
# ---------------------------------------------------------------------------


class _StubConnector:
    """Raises AttributeError on unexpected attr use — for tests that
    don't exercise ERP / CRP / rating paths (so MagicMock noise is
    out of the assertion surface).
    """


def _suite_with_fred(fred: Any) -> LiveConnectorSuite:
    return LiveConnectorSuite(
        fmp=MagicMock(),
        shiller=MagicMock(),
        te=MagicMock(),
        fred=fred,
    )


class TestLiveAssemblersExpinfWiring:
    """Exercise the builder's async ``_run`` directly so the test does not
    nest :func:`asyncio.run` inside a pytest-asyncio event loop — that
    combo leaks sockets/loops across tests and ``filterwarnings=error``
    in pyproject.toml turns the leak into a test failure.
    """

    @pytest.mark.asyncio
    async def test_us_bundle_expected_inflation_populated(self, db_session: Session) -> None:
        builder = LiveInputsBuilder(_suite_with_fred(_full_us_fake_fred()))
        bundle = await builder._run(
            db_session,
            "US",
            OBS_DATE,
            currency="USD",
            rf_tuple=None,
        )
        assert bundle.expected_inflation is not None
        assert bundle.expected_inflation["country_code"] == "US"
        assert bundle.expected_inflation["bei"] is not None
        assert bundle.expected_inflation["survey"] is not None

    @pytest.mark.asyncio
    async def test_non_us_bundle_expected_inflation_none(self, db_session: Session) -> None:
        builder = LiveInputsBuilder(_suite_with_fred(_full_us_fake_fred()))
        bundle = await builder._run(
            db_session,
            "DE",
            OBS_DATE,
            currency="EUR",
            rf_tuple=None,
        )
        assert bundle.expected_inflation is None

    @pytest.mark.asyncio
    async def test_us_bundle_none_when_no_fred(self, db_session: Session) -> None:
        builder = LiveInputsBuilder(_suite_with_fred(None))
        bundle = await builder._run(
            db_session,
            "US",
            OBS_DATE,
            currency="USD",
            rf_tuple=None,
        )
        assert bundle.expected_inflation is None

    @pytest.mark.asyncio
    async def test_us_bundle_none_when_all_fred_legs_error(self, db_session: Session) -> None:
        fake = _FakeFred(
            bei_error=httpx.HTTPError("500"),
            survey_error=httpx.HTTPError("500"),
            nominal_error=httpx.HTTPError("500"),
        )
        builder = LiveInputsBuilder(_suite_with_fred(fake))
        bundle = await builder._run(
            db_session,
            "US",
            OBS_DATE,
            currency="USD",
            rf_tuple=None,
        )
        assert bundle.expected_inflation is None
