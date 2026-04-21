"""Unit tests for MonetaryInputsBuilder (CAL-100, week6 sprint 2b)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from sonar.connectors.base import Observation
from sonar.indices.monetary.builders import (
    FRED_CA_BANK_RATE_SERIES,
    FRED_GB_BANK_RATE_SERIES,
    FRED_JP_BANK_RATE_SERIES,
    MonetaryInputsBuilder,
    _last_day_of_month,
    _latest_on_or_before,
    _resample_monthly,
    _to_dated,
    build_m1_ca_inputs,
    build_m1_ea_inputs,
    build_m1_gb_inputs,
    build_m1_jp_inputs,
    build_m1_uk_inputs,
    build_m1_us_inputs,
    build_m2_ca_inputs,
    build_m2_jp_inputs,
    build_m2_us_inputs,
    build_m4_ca_inputs,
    build_m4_jp_inputs,
    build_m4_us_inputs,
)
from sonar.overlays.exceptions import DataUnavailableError, InsufficientDataError

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

    async def fetch_series(self, series_id: str, start: date, end: date) -> list[Observation]:
        # Used by build_m1_gb_inputs + build_m1_jp_inputs + build_m1_ca_inputs
        # cascades. Returns monthly OECD-mirror policy rate values. GB pins at
        # 4.70 %, JP at 0.40 %, CA at 3.00 % (reflecting the 2024-25
        # normalisation band).
        country_code: str
        yield_bps_val: int
        if series_id == FRED_GB_BANK_RATE_SERIES:
            country_code = "GB"
            yield_bps_val = 470  # 4.70 %
        elif series_id == FRED_JP_BANK_RATE_SERIES:
            country_code = "JP"
            yield_bps_val = 40  # 0.40 %
        elif series_id == FRED_CA_BANK_RATE_SERIES:
            country_code = "CA"
            yield_bps_val = 300  # 3.00 %
        else:
            return []
        out: list[Observation] = []
        year, month = start.year, start.month
        while date(year, month, 1) <= end:
            out.append(
                Observation(
                    country_code=country_code,
                    observation_date=date(year, month, 1),
                    tenor_years=0.01,
                    yield_bps=yield_bps_val,
                    source="FRED",
                    source_series_id=series_id,
                )
            )
            month += 1
            if month > 12:
                month = 1
                year += 1
        return out


class _FakeBoESuccess:
    async def fetch_bank_rate(self, start: date, end: date) -> list[Observation]:
        out: list[Observation] = []
        d = start
        while d <= end:
            out.append(
                Observation(
                    country_code="GB",
                    observation_date=d,
                    tenor_years=0.01,
                    yield_bps=475,  # 4.75 % — BoE native value differs from FRED to prove cascade
                    source="BOE",
                    source_series_id="IUDBEDR",
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeBoEAkamai:
    """Simulates the Akamai anti-bot ErrorPage behaviour."""

    async def fetch_bank_rate(self, start: date, end: date) -> list[Observation]:
        _ = start, end
        msg = "BoE IADB ErrorPage — Akamai anti-bot gated"
        raise DataUnavailableError(msg)


@dataclass(frozen=True)
class _FakeTEIndicatorObs:
    """Mirrors :class:`TEIndicatorObservation` shape for cascade tests."""

    observation_date: date
    value: float
    historical_data_symbol: str = "UKBRBASE"


class _FakeTESuccess:
    """TE primary path — returns daily GB Bank Rate observations in pct."""

    def __init__(self, *, pct: float = 4.80) -> None:
        self.pct = pct

    async def fetch_gb_bank_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        out: list[_FakeTEIndicatorObs] = []
        d = start
        while d <= end:
            out.append(_FakeTEIndicatorObs(observation_date=d, value=self.pct))
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeTEUnavailable:
    """TE primary fails with DataUnavailableError — cascade fails over."""

    async def fetch_gb_bank_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        _ = start, end
        msg = "TE returned empty series: country='GB' indicator='interest rate'"
        raise DataUnavailableError(msg)

    async def fetch_jp_bank_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        _ = start, end
        msg = "TE returned empty series: country='JP' indicator='interest rate'"
        raise DataUnavailableError(msg)


class _FakeTEJpSuccess:
    """TE primary path for JP — returns daily BoJ policy-rate observations in pct."""

    def __init__(self, *, pct: float = 0.50) -> None:
        self.pct = pct

    async def fetch_jp_bank_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        out: list[_FakeTEIndicatorObs] = []
        d = start
        while d <= end:
            out.append(
                _FakeTEIndicatorObs(
                    observation_date=d, value=self.pct, historical_data_symbol="BOJDTR"
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeBoJSuccess:
    async def fetch_bank_rate(self, start: date, end: date) -> list[Observation]:
        out: list[Observation] = []
        d = start
        while d <= end:
            out.append(
                Observation(
                    country_code="JP",
                    observation_date=d,
                    tenor_years=0.01,
                    yield_bps=45,  # 0.45 % — BoJ native value differs from TE to prove cascade
                    source="BOJ",
                    source_series_id="FM01'STRAMUCOLR",
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeBoJGated:
    """Simulates the BoJ TSD portal browser-gated behaviour."""

    async def fetch_bank_rate(self, start: date, end: date) -> list[Observation]:
        _ = start, end
        msg = "BoJ TSD portal is browser-gated"
        raise DataUnavailableError(msg)


class _FakeTECaSuccess:
    """TE primary path for CA — returns daily BoC overnight-target observations in pct."""

    def __init__(self, *, pct: float = 3.25) -> None:
        self.pct = pct

    async def fetch_ca_bank_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        out: list[_FakeTEIndicatorObs] = []
        d = start
        while d <= end:
            out.append(
                _FakeTEIndicatorObs(
                    observation_date=d, value=self.pct, historical_data_symbol="CCLR"
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeTECaUnavailable:
    """TE primary fails for CA with DataUnavailableError — cascade fails over."""

    async def fetch_ca_bank_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        _ = start, end
        msg = "TE returned empty series: country='CA' indicator='interest rate'"
        raise DataUnavailableError(msg)


class _FakeBoCSuccess:
    """BoC Valet native — V39079 overnight target, returns pct as yield_bps=325 (3.25 %)."""

    def __init__(self, *, yield_bps: int = 310) -> None:
        self.yield_bps = yield_bps

    async def fetch_bank_rate(self, start: date, end: date) -> list[Observation]:
        out: list[Observation] = []
        d = start
        while d <= end:
            out.append(
                Observation(
                    country_code="CA",
                    observation_date=d,
                    tenor_years=0.01,
                    yield_bps=self.yield_bps,  # 3.10 % differs from TE to prove cascade
                    source="BOC",
                    source_series_id="V39079",
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeBoCUnavailable:
    """Simulates a Valet outage (e.g. transient HTTP 5xx after retries exhausted)."""

    async def fetch_bank_rate(self, start: date, end: date) -> list[Observation]:
        _ = start, end
        msg = "BoC Valet unreachable (test-fake)"
        raise DataUnavailableError(msg)


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
# M1 GB (Sprint I-patch — TE primary → BoE native → FRED stale-flagged)
# ---------------------------------------------------------------------------


class TestBuildM1Gb:
    @pytest.mark.asyncio
    async def test_te_primary_path(self) -> None:
        """TE succeeds → canonical daily series, no staleness flags."""
        fred = _FakeFredConnector()
        boe = _FakeBoESuccess()  # present but skipped (TE wins priority)
        te = _FakeTESuccess(pct=4.80)
        inputs = await build_m1_gb_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            boe=boe,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.country_code == "GB"
        # TE returned 4.80 % — priority-first-wins over BoE fake's 4.75 %.
        assert inputs.policy_rate_pct == pytest.approx(0.048)
        assert "GB_BANK_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "GB_BANK_RATE_BOE_NATIVE" not in inputs.upstream_flags
        assert "GB_BANK_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "EXPECTED_INFLATION_CB_TARGET" in inputs.upstream_flags
        assert "GB_BS_GDP_PROXY_ZERO" in inputs.upstream_flags
        assert inputs.source_connector == ("te",)

    @pytest.mark.asyncio
    async def test_boe_secondary_when_te_unavailable(self) -> None:
        """TE raises DataUnavailableError → BoE native takes over."""
        fred = _FakeFredConnector()
        boe = _FakeBoESuccess()
        te = _FakeTEUnavailable()
        inputs = await build_m1_gb_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            boe=boe,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.0475)  # BoE 4.75 %
        assert "GB_BANK_RATE_BOE_NATIVE" in inputs.upstream_flags
        assert "GB_BANK_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "GB_BANK_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("boe",)

    @pytest.mark.asyncio
    async def test_fred_last_resort_stale_flagged(self) -> None:
        """TE + BoE both fail → FRED emits staleness flags."""
        fred = _FakeFredConnector()
        boe = _FakeBoEAkamai()
        te = _FakeTEUnavailable()
        inputs = await build_m1_gb_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            boe=boe,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.047)  # FRED 4.70 %
        assert "GB_BANK_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "GB_BANK_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "GB_BANK_RATE_BOE_NATIVE" not in inputs.upstream_flags
        assert inputs.source_connector == ("fred",)

    @pytest.mark.asyncio
    async def test_fred_only_when_te_and_boe_absent(self) -> None:
        """te=None + boe=None → FRED path still emits staleness flags."""
        fred = _FakeFredConnector()
        inputs = await build_m1_gb_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            history_years=2,
        )
        assert inputs.country_code == "GB"
        assert inputs.source_connector == ("fred",)
        assert "GB_BANK_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_all_sources_fail_raises(self) -> None:
        """TE unavailable + BoE gated + FRED empty → ValueError."""

        class _EmptyFred:
            async def fetch_series(
                self, series_id: str, start: date, end: date
            ) -> list[Observation]:
                _ = series_id, start, end
                return []

        with pytest.raises(ValueError, match="TE, BoE, and FRED"):
            await build_m1_gb_inputs(
                _EmptyFred(),  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=_FakeTEUnavailable(),  # type: ignore[arg-type]
                boe=_FakeBoEAkamai(),  # type: ignore[arg-type]
                history_years=1,
            )


# ---------------------------------------------------------------------------
# M1 JP (Sprint L — TE primary → BoJ native → FRED stale-flagged)
# ---------------------------------------------------------------------------


class TestBuildM1Jp:
    @pytest.mark.asyncio
    async def test_te_primary_path(self) -> None:
        """TE succeeds → canonical daily BoJ-sourced series, no staleness flags."""
        fred = _FakeFredConnector()
        boj = _FakeBoJSuccess()  # present but skipped (TE wins priority)
        te = _FakeTEJpSuccess(pct=0.50)
        inputs = await build_m1_jp_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            boj=boj,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.country_code == "JP"
        assert inputs.policy_rate_pct == pytest.approx(0.005)  # TE 0.50 %
        assert "JP_BANK_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "JP_BANK_RATE_BOJ_NATIVE" not in inputs.upstream_flags
        assert "JP_BANK_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "EXPECTED_INFLATION_CB_TARGET" in inputs.upstream_flags
        assert "JP_BS_GDP_PROXY_ZERO" in inputs.upstream_flags
        assert inputs.source_connector == ("te",)
        assert inputs.r_star_pct == pytest.approx(0.000)

    @pytest.mark.asyncio
    async def test_boj_secondary_when_te_unavailable(self) -> None:
        """TE raises DataUnavailableError → BoJ native takes over."""
        fred = _FakeFredConnector()
        boj = _FakeBoJSuccess()
        te = _FakeTEUnavailable()
        inputs = await build_m1_jp_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            boj=boj,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.0045)  # BoJ 0.45 %
        assert "JP_BANK_RATE_BOJ_NATIVE" in inputs.upstream_flags
        assert "JP_BANK_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "JP_BANK_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("boj",)

    @pytest.mark.asyncio
    async def test_fred_last_resort_stale_flagged(self) -> None:
        """TE + BoJ both fail → FRED emits staleness flags."""
        fred = _FakeFredConnector()
        boj = _FakeBoJGated()
        te = _FakeTEUnavailable()
        inputs = await build_m1_jp_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            boj=boj,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.004)  # FRED 0.40 %
        assert "JP_BANK_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "JP_BANK_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "JP_BANK_RATE_BOJ_NATIVE" not in inputs.upstream_flags
        assert inputs.source_connector == ("fred",)

    @pytest.mark.asyncio
    async def test_fred_only_when_te_and_boj_absent(self) -> None:
        """te=None + boj=None → FRED path still emits staleness flags."""
        fred = _FakeFredConnector()
        inputs = await build_m1_jp_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            history_years=2,
        )
        assert inputs.country_code == "JP"
        assert inputs.source_connector == ("fred",)
        assert "JP_BANK_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_all_sources_fail_raises(self) -> None:
        """TE unavailable + BoJ gated + FRED empty → ValueError."""

        class _EmptyFred:
            async def fetch_series(
                self, series_id: str, start: date, end: date
            ) -> list[Observation]:
                _ = series_id, start, end
                return []

        with pytest.raises(ValueError, match="TE, BoJ, and FRED"):
            await build_m1_jp_inputs(
                _EmptyFred(),  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=_FakeTEUnavailable(),  # type: ignore[arg-type]
                boj=_FakeBoJGated(),  # type: ignore[arg-type]
                history_years=1,
            )

    @pytest.mark.asyncio
    async def test_jp_flags_include_bs_gdp_proxy_zero(self) -> None:
        """JP BS/GDP ratio is placeholder — always emits JP_BS_GDP_PROXY_ZERO."""
        fred = _FakeFredConnector()
        te = _FakeTEJpSuccess(pct=0.50)
        inputs = await build_m1_jp_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.balance_sheet_pct_gdp_current == 0.0
        assert inputs.balance_sheet_pct_gdp_12m_ago == 0.0
        assert "JP_BS_GDP_PROXY_ZERO" in inputs.upstream_flags


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
# M2 JP (Sprint L — scaffold raises until JP gap + CPI connectors land)
# ---------------------------------------------------------------------------


class TestBuildM2Jp:
    @pytest.mark.asyncio
    async def test_raises_insufficient_data_pending_connectors(self) -> None:
        """M2 JP scaffold is wire-ready but raises until JP gap/CPI land."""
        fred = _FakeFredConnector()
        te = _FakeTEJpSuccess(pct=0.50)
        with pytest.raises(InsufficientDataError, match="CAL-JP-OUTPUT-GAP"):
            await build_m2_jp_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_raises_even_without_connectors(self) -> None:
        """Scaffold raises regardless of connector presence (pre-wire state)."""
        fred = _FakeFredConnector()
        with pytest.raises(InsufficientDataError):
            await build_m2_jp_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# ---------------------------------------------------------------------------
# M4 JP (Sprint L — scaffold raises until ≥5 custom-FCI components wired)
# ---------------------------------------------------------------------------


class TestBuildM4Jp:
    @pytest.mark.asyncio
    async def test_raises_insufficient_components(self) -> None:
        """M4 JP scaffold raises until ≥5 FCI components wire."""
        fred = _FakeFredConnector()
        te = _FakeTEJpSuccess(pct=0.50)
        with pytest.raises(InsufficientDataError, match="CAL-JP-M4-FCI"):
            await build_m4_jp_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_raises_without_te(self) -> None:
        """Scaffold raises regardless of TE handle presence."""
        fred = _FakeFredConnector()
        with pytest.raises(InsufficientDataError):
            await build_m4_jp_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# ---------------------------------------------------------------------------
# M1 CA (Sprint S — TE primary → BoC Valet native → FRED stale-flagged)
# ---------------------------------------------------------------------------


class TestBuildM1Ca:
    @pytest.mark.asyncio
    async def test_te_primary_path(self) -> None:
        """TE succeeds → canonical daily BoC-sourced series, no staleness flags."""
        fred = _FakeFredConnector()
        boc = _FakeBoCSuccess()  # present but skipped (TE wins priority)
        te = _FakeTECaSuccess(pct=3.25)
        inputs = await build_m1_ca_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            boc=boc,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.country_code == "CA"
        assert inputs.policy_rate_pct == pytest.approx(0.0325)  # TE 3.25 %
        assert "CA_BANK_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "CA_BANK_RATE_BOC_NATIVE" not in inputs.upstream_flags
        assert "CA_BANK_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "EXPECTED_INFLATION_CB_TARGET" in inputs.upstream_flags
        assert "CA_BS_GDP_PROXY_ZERO" in inputs.upstream_flags
        assert inputs.source_connector == ("te",)
        assert inputs.r_star_pct == pytest.approx(0.0075)

    @pytest.mark.asyncio
    async def test_boc_secondary_when_te_unavailable(self) -> None:
        """TE raises DataUnavailableError → BoC Valet native takes over (robust path)."""
        fred = _FakeFredConnector()
        boc = _FakeBoCSuccess(yield_bps=310)
        te = _FakeTECaUnavailable()
        inputs = await build_m1_ca_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            boc=boc,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.031)  # BoC 3.10 %
        assert "CA_BANK_RATE_BOC_NATIVE" in inputs.upstream_flags
        assert "CA_BANK_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "CA_BANK_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("boc",)

    @pytest.mark.asyncio
    async def test_fred_last_resort_stale_flagged(self) -> None:
        """TE + BoC both fail → FRED emits staleness flags."""
        fred = _FakeFredConnector()
        boc = _FakeBoCUnavailable()
        te = _FakeTECaUnavailable()
        inputs = await build_m1_ca_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            boc=boc,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.03)  # FRED 3.00 %
        assert "CA_BANK_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "CA_BANK_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "CA_BANK_RATE_BOC_NATIVE" not in inputs.upstream_flags
        assert inputs.source_connector == ("fred",)

    @pytest.mark.asyncio
    async def test_fred_only_when_te_and_boc_absent(self) -> None:
        """te=None + boc=None → FRED path still emits staleness flags."""
        fred = _FakeFredConnector()
        inputs = await build_m1_ca_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            history_years=2,
        )
        assert inputs.country_code == "CA"
        assert inputs.source_connector == ("fred",)
        assert "CA_BANK_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_all_sources_fail_raises(self) -> None:
        """TE unavailable + BoC unavailable + FRED empty → ValueError."""

        class _EmptyFred:
            async def fetch_series(
                self, series_id: str, start: date, end: date
            ) -> list[Observation]:
                _ = series_id, start, end
                return []

        with pytest.raises(ValueError, match="TE, BoC, and FRED"):
            await build_m1_ca_inputs(
                _EmptyFred(),  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=_FakeTECaUnavailable(),  # type: ignore[arg-type]
                boc=_FakeBoCUnavailable(),  # type: ignore[arg-type]
                history_years=1,
            )

    @pytest.mark.asyncio
    async def test_ca_flags_include_bs_gdp_proxy_zero(self) -> None:
        """CA BS/GDP ratio is placeholder — always emits CA_BS_GDP_PROXY_ZERO."""
        fred = _FakeFredConnector()
        te = _FakeTECaSuccess(pct=3.25)
        inputs = await build_m1_ca_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.balance_sheet_pct_gdp_current == 0.0
        assert inputs.balance_sheet_pct_gdp_12m_ago == 0.0
        assert "CA_BS_GDP_PROXY_ZERO" in inputs.upstream_flags


# ---------------------------------------------------------------------------
# M2 CA (Sprint S — scaffold raises until CA gap + CPI connectors land)
# ---------------------------------------------------------------------------


class TestBuildM2Ca:
    @pytest.mark.asyncio
    async def test_raises_insufficient_data_pending_connectors(self) -> None:
        """M2 CA scaffold is wire-ready but raises until CA gap/CPI land."""
        fred = _FakeFredConnector()
        te = _FakeTECaSuccess(pct=3.25)
        with pytest.raises(InsufficientDataError, match="CAL-130"):
            await build_m2_ca_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_raises_even_without_connectors(self) -> None:
        """Scaffold raises regardless of connector presence (pre-wire state)."""
        fred = _FakeFredConnector()
        with pytest.raises(InsufficientDataError):
            await build_m2_ca_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# ---------------------------------------------------------------------------
# M4 CA (Sprint S — scaffold raises until ≥5 custom-FCI components wired)
# ---------------------------------------------------------------------------


class TestBuildM4Ca:
    @pytest.mark.asyncio
    async def test_raises_insufficient_components(self) -> None:
        """M4 CA scaffold raises until ≥5 FCI components wire."""
        fred = _FakeFredConnector()
        te = _FakeTECaSuccess(pct=3.25)
        boc = _FakeBoCSuccess()
        with pytest.raises(InsufficientDataError, match="CAL-131"):
            await build_m4_ca_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                boc=boc,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_raises_without_te(self) -> None:
        """Scaffold raises regardless of TE handle presence."""
        fred = _FakeFredConnector()
        with pytest.raises(InsufficientDataError):
            await build_m4_ca_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


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
    async def test_build_m1_gb_via_facade(self) -> None:
        """GB M1 dispatch — FRED-only path (no TE/BoE handles) → stale flags."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("GB", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "GB"
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "GB_BANK_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_build_m1_gb_via_facade_te_primary(self) -> None:
        """GB M1 dispatch — TE handle present → canonical TE primary path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTESuccess(pct=4.80),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("GB", date(2024, 12, 31), history_years=2)
        assert "GB_BANK_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "GB_BANK_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("te",)

    @pytest.mark.asyncio
    async def test_build_m1_via_facade_uk_alias_normalises_to_gb(self) -> None:
        """UK alias passed to dispatch → delegates to GB cascade silently.

        ADR-0007 / CAL-128: the CLI entry layer emits the operator-facing
        deprecation warning; ``MonetaryInputsBuilder`` normalises silently
        so the trace stays clean for direct library consumers.
        """
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTESuccess(pct=4.80),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("UK", date(2024, 12, 31), history_years=2)
        # Row persists under the canonical code regardless of alias input.
        assert inputs.country_code == "GB"
        assert "GB_BANK_RATE_TE_PRIMARY" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_build_m1_jp_via_facade_te_primary(self) -> None:
        """JP M1 dispatch — TE handle present → canonical TE primary path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEJpSuccess(pct=0.50),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("JP", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "JP"
        assert "JP_BANK_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "JP_BANK_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("te",)

    @pytest.mark.asyncio
    async def test_build_m1_jp_via_facade_fred_fallback(self) -> None:
        """JP M1 dispatch — FRED-only path (no TE/BoJ handles) → stale flags."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("JP", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "JP"
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "JP_BANK_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_m1_unsupported_country_raises(self) -> None:
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        # AU remains unwired at Sprint S close — CA is now a supported
        # country (see :func:`build_m1_ca_inputs`).
        with pytest.raises(NotImplementedError, match="AU"):
            await builder.build_m1_inputs("AU", date(2024, 12, 31))

    @pytest.mark.asyncio
    async def test_build_m1_ca_via_facade_te_primary(self) -> None:
        """CA M1 dispatch — TE handle present → canonical TE primary path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTECaSuccess(pct=3.25),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("CA", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "CA"
        assert "CA_BANK_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "CA_BANK_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("te",)

    @pytest.mark.asyncio
    async def test_build_m1_ca_via_facade_boc_secondary(self) -> None:
        """CA M1 dispatch — TE absent, BoC handle present → native path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            boc=_FakeBoCSuccess(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("CA", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "CA"
        assert "CA_BANK_RATE_BOC_NATIVE" in inputs.upstream_flags
        assert inputs.source_connector == ("boc",)

    @pytest.mark.asyncio
    async def test_build_m1_ca_via_facade_fred_fallback(self) -> None:
        """CA M1 dispatch — FRED-only path (no TE/BoC handles) → stale flags."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("CA", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "CA"
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "CA_BANK_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_m2_ca_dispatches_to_ca_builder(self) -> None:
        """CA M2 dispatch routes to the CA scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTECaSuccess(pct=3.25),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-130"):
            await builder.build_m2_inputs("CA", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_m4_ca_dispatches_to_ca_builder(self) -> None:
        """CA M4 dispatch routes to the CA scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTECaSuccess(pct=3.25),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-131"):
            await builder.build_m4_inputs("CA", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_m2_jp_dispatches_to_jp_builder(self) -> None:
        """JP M2 dispatch routes to the JP scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEJpSuccess(pct=0.50),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-JP"):
            await builder.build_m2_inputs("JP", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_m4_jp_dispatches_to_jp_builder(self) -> None:
        """JP M4 dispatch routes to the JP scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEJpSuccess(pct=0.50),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-JP-M4-FCI"):
            await builder.build_m4_inputs("JP", date(2024, 12, 31), history_years=2)

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


# ---------------------------------------------------------------------------
# Backward compat alias (ADR-0007 / CAL-128) — removal Week 10 Day 1
# ---------------------------------------------------------------------------


class TestBuildM1UkDeprecatedAlias:
    @pytest.mark.asyncio
    async def test_build_m1_uk_inputs_alias_emits_deprecation_warning(self) -> None:
        """Calling the deprecated wrapper emits a structlog warning."""
        import structlog.testing  # noqa: PLC0415 — fixture-style import

        fred = _FakeFredConnector()
        te = _FakeTESuccess(pct=4.80)

        with structlog.testing.capture_logs() as captured:
            await build_m1_uk_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                history_years=2,
            )

        deprecation_events = [
            e for e in captured if e.get("event") == "builders.build_m1_uk_inputs.deprecated"
        ]
        assert len(deprecation_events) == 1
        event = deprecation_events[0]
        assert event["log_level"] == "warning"
        assert event["replacement"] == "build_m1_gb_inputs"
        assert event["adr"] == "ADR-0007"

    @pytest.mark.asyncio
    async def test_build_m1_uk_inputs_alias_returns_same_as_gb_inputs(self) -> None:
        """The deprecated wrapper returns the same inputs as the canonical."""
        fred_uk = _FakeFredConnector()
        te_uk = _FakeTESuccess(pct=4.80)
        uk_inputs = await build_m1_uk_inputs(
            fred_uk,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te_uk,  # type: ignore[arg-type]
            history_years=2,
        )

        fred_gb = _FakeFredConnector()
        te_gb = _FakeTESuccess(pct=4.80)
        gb_inputs = await build_m1_gb_inputs(
            fred_gb,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te_gb,  # type: ignore[arg-type]
            history_years=2,
        )

        # Structural equality — the alias is a pure delegation wrapper.
        assert uk_inputs == gb_inputs
        assert uk_inputs.country_code == "GB"
        assert "GB_BANK_RATE_TE_PRIMARY" in uk_inputs.upstream_flags
