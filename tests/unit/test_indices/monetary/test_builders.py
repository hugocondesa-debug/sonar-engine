"""Unit tests for MonetaryInputsBuilder (CAL-100, week6 sprint 2b)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from sonar.indices.monetary.builders import (
    MonetaryInputsBuilder,
    _last_day_of_month,
    _latest_on_or_before,
    _resample_monthly,
    _to_dated,
    build_m1_ea_inputs,
    build_m1_us_inputs,
    build_m2_us_inputs,
    build_m4_us_inputs,
)

# ---------------------------------------------------------------------------
# Helpers + fakes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Obs:
    observation_date: date
    value: float


@dataclass(frozen=True)
class _GapObs:
    observation_date: date
    gap: float


def _daily_range(start: date, end: date, value: float) -> list[_Obs]:
    out: list[_Obs] = []
    d = start
    while d <= end:
        out.append(_Obs(observation_date=d, value=value))
        d = date.fromordinal(d.toordinal() + 1)
    return out


class _FakeFredConnector:
    def __init__(
        self,
        *,
        target_upper: float = 4.5,
        target_lower: float = 4.25,
        umich_5y_pct: float = 3.0,
        walcl_mn: float = 7_000_000.0,
        gdp_bn: float = 23_000.0,
        pce_yoy_decimal: float = 0.028,
        nfci_level: float = -0.5,
    ) -> None:
        self.target_upper = target_upper
        self.target_lower = target_lower
        self.umich_5y_pct = umich_5y_pct
        self.walcl_mn = walcl_mn
        self.gdp_bn = gdp_bn
        self.pce_yoy_decimal = pce_yoy_decimal
        self.nfci_level = nfci_level

    async def fetch_fed_funds_target_upper_us(self, start: date, end: date) -> list[_Obs]:
        return _daily_range(start, end, self.target_upper)

    async def fetch_fed_funds_target_lower_us(self, start: date, end: date) -> list[_Obs]:
        return _daily_range(start, end, self.target_lower)

    async def fetch_umich_5y_inflation_us(self, start: date, end: date) -> list[_Obs]:
        return _daily_range(start, end, self.umich_5y_pct)

    async def fetch_fed_balance_sheet_us(self, start: date, end: date) -> list[_Obs]:
        # WALCL is weekly; downsample by 7 days.
        out: list[_Obs] = []
        d = start
        while d <= end:
            out.append(_Obs(observation_date=d, value=self.walcl_mn))
            d = date.fromordinal(d.toordinal() + 7)
        return out

    async def fetch_real_gdp_us(self, start: date, end: date) -> list[_Obs]:
        # Quarterly (Jan/Apr/Jul/Oct 1st) approximation.
        out: list[_Obs] = []
        year = start.year
        while year <= end.year:
            for m in (1, 4, 7, 10):
                d = date(year, m, 1)
                if start <= d <= end:
                    out.append(_Obs(observation_date=d, value=self.gdp_bn))
            year += 1
        return out

    async def fetch_pce_core_yoy_us(self, start: date, end: date) -> list[_Obs]:
        # Monthly.
        out: list[_Obs] = []
        year, month = start.year, start.month
        while date(year, month, 1) <= end:
            out.append(_Obs(observation_date=date(year, month, 1), value=self.pce_yoy_decimal))
            month += 1
            if month > 12:
                month = 1
                year += 1
        return out

    async def fetch_nfci_us(self, start: date, end: date) -> list[_Obs]:
        out: list[_Obs] = []
        d = start
        while d <= end:
            out.append(_Obs(observation_date=d, value=self.nfci_level))
            d = date.fromordinal(d.toordinal() + 7)
        return out


class _FakeCboConnector:
    def __init__(self, gap: float = 0.005) -> None:
        self.gap = gap

    async def fetch_output_gap_us(self, start: date, end: date) -> list[_GapObs]:
        out: list[_GapObs] = []
        year = start.year
        while year <= end.year:
            for m in (1, 4, 7, 10):
                d = date(year, m, 1)
                if start <= d <= end:
                    out.append(_GapObs(observation_date=d, gap=self.gap))
            year += 1
        return out


class _FakeEcbConnector:
    def __init__(
        self,
        *,
        dfr_pct: float = 3.0,
        eurosystem_bs_eur_mn: float = 6_400_000.0,
    ) -> None:
        self.dfr_pct = dfr_pct
        self.bs = eurosystem_bs_eur_mn

    async def fetch_dfr_rate(self, start: date, end: date) -> list[_Obs]:
        return _daily_range(start, end, self.dfr_pct)

    async def fetch_eurosystem_balance_sheet(self, start: date, end: date) -> list[_Obs]:
        # Weekly.
        out: list[_Obs] = []
        d = start
        while d <= end:
            out.append(_Obs(observation_date=d, value=self.bs))
            d = date.fromordinal(d.toordinal() + 7)
        return out


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_last_day_of_month_non_december(self) -> None:
        assert _last_day_of_month(2024, 2) == date(2024, 2, 29)  # leap
        assert _last_day_of_month(2023, 2) == date(2023, 2, 28)
        assert _last_day_of_month(2024, 4) == date(2024, 4, 30)

    def test_last_day_of_month_december(self) -> None:
        assert _last_day_of_month(2024, 12) == date(2024, 12, 31)

    def test_latest_on_or_before(self) -> None:
        rows = _to_dated(
            [
                _Obs(observation_date=date(2024, 1, 1), value=1.0),
                _Obs(observation_date=date(2024, 6, 1), value=2.0),
                _Obs(observation_date=date(2024, 12, 1), value=3.0),
            ]
        )
        hit = _latest_on_or_before(rows, date(2024, 7, 15))
        assert hit is not None
        assert hit.value == 2.0

    def test_latest_on_or_before_none_when_empty(self) -> None:
        assert _latest_on_or_before([], date(2024, 7, 15)) is None

    def test_resample_monthly_forward_fills(self) -> None:
        rows = _to_dated(
            [
                _Obs(observation_date=date(2024, 1, 15), value=1.0),
                _Obs(observation_date=date(2024, 4, 15), value=4.0),
            ]
        )
        series = _resample_monthly(rows, date(2024, 4, 30), n_months=4)
        # April = 4, March forwards from Jan = 1, Feb = 1, Jan = 1.
        assert series == [1.0, 1.0, 1.0, 4.0]

    def test_resample_monthly_breaks_when_no_prior(self) -> None:
        rows = _to_dated([_Obs(observation_date=date(2024, 3, 15), value=2.0)])
        series = _resample_monthly(rows, date(2024, 4, 30), n_months=6)
        # Backwards from Apr: Apr=2, Mar=2, Feb=None → break.
        assert series == [2.0, 2.0]


# ---------------------------------------------------------------------------
# M1 US
# ---------------------------------------------------------------------------


class TestBuildM1Us:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        fred = _FakeFredConnector()
        inputs = await build_m1_us_inputs(
            fred,
            date(2024, 12, 31),
            history_years=2,  # type: ignore[arg-type]
        )
        assert inputs.country_code == "US"
        # policy rate midpoint = (4.5 + 4.25)/2/100 = 0.04375
        assert inputs.policy_rate_pct == pytest.approx(0.04375)
        # umich series is 3 %, so decimal = 0.03
        assert inputs.expected_inflation_5y_pct == pytest.approx(0.03)
        # r* US = 0.008 per YAML
        assert inputs.r_star_pct == pytest.approx(0.008)
        # BS/GDP = (7_000_000 / 1_000) / 23_000 = 7_000 / 23_000 ≈ 0.3043
        assert inputs.balance_sheet_pct_gdp_current == pytest.approx(7000.0 / 23000.0, abs=1e-6)
        assert len(inputs.real_shadow_rate_history) >= 12  # 2Y monthly

    @pytest.mark.asyncio
    async def test_raises_without_expected_inflation(self) -> None:
        class _NoInflation(_FakeFredConnector):
            async def fetch_umich_5y_inflation_us(self, start: date, end: date) -> list[_Obs]:
                return []

        with pytest.raises(ValueError, match="UMich 5Y inflation"):
            await build_m1_us_inputs(_NoInflation(), date(2024, 12, 31), history_years=2)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# M1 EA
# ---------------------------------------------------------------------------


class TestBuildM1Ea:
    @pytest.mark.asyncio
    async def test_happy_path_with_default_gdp_resolver(self) -> None:
        ecb = _FakeEcbConnector()
        inputs = await build_m1_ea_inputs(
            ecb,
            date(2024, 12, 31),
            history_years=2,  # type: ignore[arg-type]
        )
        assert inputs.country_code == "EA"
        assert inputs.policy_rate_pct == pytest.approx(0.03)  # 3% / 100
        # EXPECTED_INFLATION_PROXY flag present per spec.
        assert "EXPECTED_INFLATION_PROXY" in inputs.upstream_flags
        # r* EA = -0.005 per YAML
        assert inputs.r_star_pct == pytest.approx(-0.005)
        # BS / 14_000_000 default = 6_400_000 / 14_000_000 ≈ 0.457
        assert inputs.balance_sheet_pct_gdp_current == pytest.approx(6_400_000.0 / 14_000_000.0)

    @pytest.mark.asyncio
    async def test_custom_gdp_resolver(self) -> None:
        ecb = _FakeEcbConnector()
        inputs = await build_m1_ea_inputs(
            ecb,  # type: ignore[arg-type]
            date(2024, 12, 31),
            history_years=2,
            ea_gdp_eur_mn_resolver=lambda _d: 10_000_000.0,
        )
        assert inputs.balance_sheet_pct_gdp_current == pytest.approx(0.64)


# ---------------------------------------------------------------------------
# M2 US
# ---------------------------------------------------------------------------


class TestBuildM2Us:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        fred = _FakeFredConnector()
        cbo = _FakeCboConnector()
        inputs = await build_m2_us_inputs(
            fred,  # type: ignore[arg-type]
            cbo,  # type: ignore[arg-type]
            date(2024, 12, 31),
            history_years=2,
        )
        assert inputs.country_code == "US"
        assert inputs.inflation_yoy_pct == pytest.approx(0.028)
        assert inputs.output_gap_pct == pytest.approx(0.005)
        assert inputs.inflation_target_pct == pytest.approx(0.02)  # Fed target
        assert inputs.r_star_pct == pytest.approx(0.008)
        assert "INFLATION_FORECAST_PROXY_UMICH" in inputs.upstream_flags
        assert inputs.prev_policy_rate_pct == pytest.approx(0.04375)


# ---------------------------------------------------------------------------
# M4 US
# ---------------------------------------------------------------------------


class TestBuildM4Us:
    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        fred = _FakeFredConnector()
        inputs = await build_m4_us_inputs(
            fred,
            date(2024, 12, 31),
            history_years=2,  # type: ignore[arg-type]
        )
        assert inputs.country_code == "US"
        assert inputs.nfci_level == pytest.approx(-0.5)
        assert inputs.fci_level_12m_ago == pytest.approx(-0.5)
        assert len(inputs.nfci_history) >= 12


# ---------------------------------------------------------------------------
# Facade dispatch
# ---------------------------------------------------------------------------


class TestMonetaryInputsBuilderFacade:
    @pytest.mark.asyncio
    async def test_build_m1_us_via_facade(self) -> None:
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("US", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "US"

    @pytest.mark.asyncio
    async def test_build_m1_ea_via_facade(self) -> None:
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("EA", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "EA"

    @pytest.mark.asyncio
    async def test_m1_unsupported_country_raises(self) -> None:
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        with pytest.raises(NotImplementedError, match="UK"):
            await builder.build_m1_inputs("UK", date(2024, 12, 31))

    @pytest.mark.asyncio
    async def test_m2_ea_raises(self) -> None:
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        with pytest.raises(NotImplementedError, match="EA"):
            await builder.build_m2_inputs("EA", date(2024, 12, 31))

    @pytest.mark.asyncio
    async def test_m4_ea_raises(self) -> None:
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        with pytest.raises(NotImplementedError, match="EA"):
            await builder.build_m4_inputs("EA", date(2024, 12, 31))
