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
    @pytest.mark.parametrize("country", ["GB", "JP", "CA", "BR", "IN"])
    async def test_non_us_non_ea_returns_none(self, country: str) -> None:
        """Countries outside US + EA cohort return None (no live connector)."""
        kwargs = await load_live_exp_inflation_kwargs(
            country,
            OBS_DATE,
            fred=_full_us_fake_fred(),  # type: ignore[arg-type]
        )
        assert kwargs is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("country", ["EA", "DE", "FR", "IT", "ES", "PT", "NL"])
    async def test_ea_cohort_returns_none_without_ecb_sdw(self, country: str) -> None:
        """EA cohort members without ecb_sdw connector → None (Sprint Q.1 guard)."""
        kwargs = await load_live_exp_inflation_kwargs(
            country,
            OBS_DATE,
            fred=_full_us_fake_fred(),  # type: ignore[arg-type]
            ecb_sdw=None,
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


# ---------------------------------------------------------------------------
# Sprint Q.1 — ECB SDW SPF EA cohort wiring
# ---------------------------------------------------------------------------


from datetime import date as _date  # noqa: E402 — placed after original imports

from sonar.connectors.ecb_sdw import ExpInflationSurveyObservation as _SpfObs  # noqa: E402
from sonar.overlays.expected_inflation import METHODOLOGY_VERSION_SURVEY  # noqa: E402


class _FakeEcbSdw:
    """Async-compatible fake EcbSdwConnector for SPF tests."""

    def __init__(
        self,
        *,
        observations: list[_SpfObs] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._observations = observations or []
        self._error = error
        self.calls: list[tuple[str, _date, _date]] = []

    async def fetch_survey_expected_inflation(
        self, *, country: str, start: _date, end: _date
    ) -> list[_SpfObs]:
        self.calls.append((country, start, end))
        if self._error is not None:
            raise self._error
        return self._observations


def _full_spf_observations(survey_date: _date = _date(2026, 1, 1)) -> list[_SpfObs]:
    """2026-Q1 release with 1Y / 2Y / LTE horizons populated."""
    return [
        _SpfObs(survey_date=survey_date, horizon_year="2027", tenor="1Y", value_pct=1.971),
        _SpfObs(survey_date=survey_date, horizon_year="2028", tenor="2Y", value_pct=2.051),
        _SpfObs(survey_date=survey_date, horizon_year="LT", tenor="LTE", value_pct=2.017),
        # Junk horizons that should be filtered out by the loader.
        _SpfObs(survey_date=survey_date, horizon_year="2026", tenor="0Y", value_pct=1.838),
        _SpfObs(
            survey_date=_date(2025, 10, 1),
            horizon_year="LT",
            tenor="LTE",
            value_pct=2.023,
        ),
    ]


class TestEaSpfCohort:
    @pytest.mark.asyncio
    async def test_ea_aggregate_populates_kwargs(self, db_session: Session) -> None:
        ecb = _FakeEcbSdw(observations=_full_spf_observations())
        kwargs = await load_live_exp_inflation_kwargs(
            "EA",
            OBS_DATE,
            fred=None,
            ecb_sdw=ecb,  # type: ignore[arg-type]
            session=db_session,
        )
        assert kwargs is not None
        assert kwargs["country_code"] == "EA"
        assert kwargs["bei"] is None
        assert kwargs["survey"] is not None
        assert kwargs["bc_target_pct"] == pytest.approx(0.02)

        survey = kwargs["survey"]
        assert survey.horizons["1Y"] == pytest.approx(0.01971)
        assert survey.horizons["LTE"] == pytest.approx(0.02017)
        assert survey.interpolated_tenors["5y5y"] == pytest.approx(0.02017)
        assert "SPF_LT_AS_ANCHOR" in survey.flags
        assert "SPF_AREA_PROXY" not in survey.flags

    @pytest.mark.asyncio
    @pytest.mark.parametrize("country", ["DE", "FR", "IT", "ES", "PT", "NL"])
    async def test_ea_member_carries_area_proxy_flag(
        self, db_session: Session, country: str
    ) -> None:
        ecb = _FakeEcbSdw(observations=_full_spf_observations())
        kwargs = await load_live_exp_inflation_kwargs(
            country,
            OBS_DATE,
            fred=None,
            ecb_sdw=ecb,  # type: ignore[arg-type]
            session=db_session,
        )
        assert kwargs is not None
        assert kwargs["country_code"] == country
        assert "SPF_AREA_PROXY" in kwargs["survey"].flags

    @pytest.mark.asyncio
    async def test_empty_spf_window_returns_none(self, db_session: Session) -> None:
        ecb = _FakeEcbSdw(observations=[])
        kwargs = await load_live_exp_inflation_kwargs(
            "EA",
            OBS_DATE,
            fred=None,
            ecb_sdw=ecb,  # type: ignore[arg-type]
            session=db_session,
        )
        assert kwargs is None

    @pytest.mark.asyncio
    async def test_spf_http_error_returns_none(self, db_session: Session) -> None:
        ecb = _FakeEcbSdw(error=httpx.HTTPError("SDW 500"))
        kwargs = await load_live_exp_inflation_kwargs(
            "EA",
            OBS_DATE,
            fred=None,
            ecb_sdw=ecb,  # type: ignore[arg-type]
            session=db_session,
        )
        assert kwargs is None

    @pytest.mark.asyncio
    async def test_session_persists_survey_row(self, db_session: Session) -> None:
        from sonar.db.models import ExpInflationSurveyRow  # noqa: PLC0415

        ecb = _FakeEcbSdw(observations=_full_spf_observations())
        _ = await load_live_exp_inflation_kwargs(
            "EA",
            OBS_DATE,
            fred=None,
            ecb_sdw=ecb,  # type: ignore[arg-type]
            session=db_session,
        )
        db_session.commit()
        rows = db_session.query(ExpInflationSurveyRow).all()
        assert len(rows) == 1
        assert rows[0].country_code == "EA"
        assert rows[0].survey_name == "ECB_SPF_HICP"
        assert "SPF_LT_AS_ANCHOR" in (rows[0].flags or "")

    @pytest.mark.asyncio
    async def test_session_upsert_is_idempotent(self, db_session: Session) -> None:
        from sonar.db.models import ExpInflationSurveyRow  # noqa: PLC0415

        ecb = _FakeEcbSdw(observations=_full_spf_observations())
        for _ in range(3):
            await load_live_exp_inflation_kwargs(
                "EA",
                OBS_DATE,
                fred=None,
                ecb_sdw=ecb,  # type: ignore[arg-type]
                session=db_session,
            )
            db_session.commit()
        # Unique constraint honoured; duplicate inserts skipped.
        count = (
            db_session.query(ExpInflationSurveyRow)
            .filter(ExpInflationSurveyRow.country_code == "EA")
            .count()
        )
        assert count == 1

    @pytest.mark.asyncio
    async def test_none_session_still_returns_kwargs(self) -> None:
        """Without session the loader computes kwargs without persistence."""
        ecb = _FakeEcbSdw(observations=_full_spf_observations())
        kwargs = await load_live_exp_inflation_kwargs(
            "EA",
            OBS_DATE,
            fred=None,
            ecb_sdw=ecb,  # type: ignore[arg-type]
            session=None,
        )
        assert kwargs is not None
        assert kwargs["survey"].horizons["LTE"] == pytest.approx(0.02017)
        assert METHODOLOGY_VERSION_SURVEY == "EXP_INF_SURVEY_v0.1"
