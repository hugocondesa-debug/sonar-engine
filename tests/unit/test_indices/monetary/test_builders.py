"""Unit tests for MonetaryInputsBuilder (CAL-100, week6 sprint 2b)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from sonar.connectors.base import Observation
from sonar.indices.monetary.builders import (
    FRED_AU_CASH_RATE_SERIES,
    FRED_CA_BANK_RATE_SERIES,
    FRED_CH_POLICY_RATE_SERIES,
    FRED_GB_BANK_RATE_SERIES,
    FRED_JP_BANK_RATE_SERIES,
    FRED_NO_POLICY_RATE_SERIES,
    FRED_NZ_OCR_SERIES,
    FRED_SE_POLICY_RATE_SERIES,
    MonetaryInputsBuilder,
    _last_day_of_month,
    _latest_on_or_before,
    _resample_monthly,
    _to_dated,
    build_m1_au_inputs,
    build_m1_ca_inputs,
    build_m1_ch_inputs,
    build_m1_ea_inputs,
    build_m1_gb_inputs,
    build_m1_jp_inputs,
    build_m1_no_inputs,
    build_m1_nz_inputs,
    build_m1_se_inputs,
    build_m1_uk_inputs,
    build_m1_us_inputs,
    build_m2_au_inputs,
    build_m2_ca_inputs,
    build_m2_ch_inputs,
    build_m2_jp_inputs,
    build_m2_no_inputs,
    build_m2_nz_inputs,
    build_m2_se_inputs,
    build_m2_us_inputs,
    build_m4_au_inputs,
    build_m4_ca_inputs,
    build_m4_ch_inputs,
    build_m4_jp_inputs,
    build_m4_no_inputs,
    build_m4_nz_inputs,
    build_m4_se_inputs,
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
        # + build_m1_au_inputs cascades. Returns monthly OECD-mirror policy
        # rate values. GB pins at 4.70 %, JP at 0.40 %, CA at 3.00 %, AU at
        # 4.00 % (reflecting the 2024-25 normalisation band).
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
        elif series_id == FRED_AU_CASH_RATE_SERIES:
            country_code = "AU"
            yield_bps_val = 400  # 4.00 %
        elif series_id == FRED_NZ_OCR_SERIES:
            country_code = "NZ"
            yield_bps_val = 375  # 3.75 %
        elif series_id == FRED_CH_POLICY_RATE_SERIES:
            country_code = "CH"
            yield_bps_val = -25  # -0.25 % — negative-rate-era fixture value
        elif series_id == FRED_NO_POLICY_RATE_SERIES:
            country_code = "NO"
            yield_bps_val = 400  # 4.00 % — post-2024 normalisation level
        elif series_id == FRED_SE_POLICY_RATE_SERIES:
            country_code = "SE"
            yield_bps_val = -25  # -0.25 % — negative-rate-era fixture value
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


class _FakeTEAuSuccess:
    """TE primary path for AU — returns daily RBA cash-rate observations in pct."""

    def __init__(self, *, pct: float = 4.10) -> None:
        self.pct = pct

    async def fetch_au_cash_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        out: list[_FakeTEIndicatorObs] = []
        d = start
        while d <= end:
            out.append(
                _FakeTEIndicatorObs(
                    observation_date=d, value=self.pct, historical_data_symbol="RBATCTR"
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeTEAuUnavailable:
    """TE primary fails for AU with DataUnavailableError — cascade fails over."""

    async def fetch_au_cash_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        _ = start, end
        msg = "TE returned empty series: country='AU' indicator='interest rate'"
        raise DataUnavailableError(msg)


class _FakeRBASuccess:
    """RBA F1 native — FIRMMCRTD cash-rate target."""

    def __init__(self, *, yield_bps: int = 395) -> None:
        self.yield_bps = yield_bps

    async def fetch_cash_rate(self, start: date, end: date) -> list[Observation]:
        out: list[Observation] = []
        d = start
        while d <= end:
            out.append(
                Observation(
                    country_code="AU",
                    observation_date=d,
                    tenor_years=0.01,
                    yield_bps=self.yield_bps,  # 3.95 % differs from TE to prove cascade
                    source="RBA",
                    source_series_id="FIRMMCRTD",
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeRBAUnavailable:
    """Simulates an RBA host outage (e.g. Akamai reject / transient 5xx)."""

    async def fetch_cash_rate(self, start: date, end: date) -> list[Observation]:
        _ = start, end
        msg = "RBA F1 unreachable (test-fake)"
        raise DataUnavailableError(msg)


class _FakeTENzSuccess:
    """TE primary path for NZ — returns daily RBNZ OCR observations in pct."""

    def __init__(self, *, pct: float = 3.75) -> None:
        self.pct = pct

    async def fetch_nz_ocr(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        out: list[_FakeTEIndicatorObs] = []
        d = start
        while d <= end:
            out.append(
                _FakeTEIndicatorObs(
                    observation_date=d, value=self.pct, historical_data_symbol="NZOCRS"
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeTENzUnavailable:
    """TE primary fails for NZ with DataUnavailableError — cascade fails over."""

    async def fetch_nz_ocr(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        _ = start, end
        msg = "TE returned empty series: country='NZ' indicator='interest rate'"
        raise DataUnavailableError(msg)


class _FakeRBNZSuccess:
    """RBNZ B2 native — hb2-daily OCR column (hypothetical once edge unblocks)."""

    def __init__(self, *, yield_bps: int = 360) -> None:
        self.yield_bps = yield_bps

    async def fetch_ocr(self, start: date, end: date) -> list[Observation]:
        out: list[Observation] = []
        d = start
        while d <= end:
            out.append(
                Observation(
                    country_code="NZ",
                    observation_date=d,
                    tenor_years=0.01,
                    yield_bps=self.yield_bps,  # 3.60 % differs from TE to prove cascade
                    source="RBNZ",
                    source_series_id="hb2-daily:OCR",
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeRBNZUnavailable:
    """Simulates the current live RBNZ perimeter-403 state (2026-04-21)."""

    async def fetch_ocr(self, start: date, end: date) -> list[Observation]:
        _ = start, end
        msg = "RBNZ host returned HTML perimeter page (test-fake, CAL-NZ-RBNZ-TABLES)"
        raise DataUnavailableError(msg)


class _FakeTEChSuccess:
    """TE primary path for CH — returns daily SNB policy-rate obs (pct)."""

    def __init__(self, *, pct: float = 1.5) -> None:
        self.pct = pct

    async def fetch_ch_policy_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        out: list[_FakeTEIndicatorObs] = []
        d = start
        while d <= end:
            out.append(
                _FakeTEIndicatorObs(
                    observation_date=d, value=self.pct, historical_data_symbol="SZLTTR"
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeTENoSuccess:
    """TE primary path for NO — returns daily Norges Bank policy-rate obs (pct)."""

    def __init__(self, *, pct: float = 4.5) -> None:
        self.pct = pct

    async def fetch_no_policy_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        out: list[_FakeTEIndicatorObs] = []
        d = start
        while d <= end:
            out.append(
                _FakeTEIndicatorObs(
                    observation_date=d, value=self.pct, historical_data_symbol="NOBRDEP"
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeTENoUnavailable:
    """TE primary fails for NO — cascade fails over to Norges Bank native."""

    async def fetch_no_policy_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        _ = start, end
        msg = "TE returned empty series: country='NO' indicator='interest rate'"
        raise DataUnavailableError(msg)


class _FakeNorgesBankSuccess:
    """Norges Bank DataAPI native — daily cadence (no staleness or cadence flag)."""

    def __init__(self, *, yield_bps: int = 425) -> None:
        self.yield_bps = yield_bps

    async def fetch_policy_rate(self, start: date, end: date) -> list[Observation]:
        out: list[Observation] = []
        d = start
        while d <= end:
            out.append(
                Observation(
                    country_code="NO",
                    observation_date=d,
                    tenor_years=0.01,
                    yield_bps=self.yield_bps,
                    source="NORGESBANK",
                    source_series_id="IR/B.KPRA.SD.R",
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeNorgesBankUnavailable:
    """Simulates a Norges Bank DataAPI outage / schema drift."""

    async def fetch_policy_rate(self, start: date, end: date) -> list[Observation]:
        _ = start, end
        msg = "Norges Bank DataAPI unreachable (test-fake)"
        raise DataUnavailableError(msg)


class _FakeTEChUnavailable:
    """TE primary fails for CH — cascade fails over to SNB native."""

    async def fetch_ch_policy_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        _ = start, end
        msg = "TE returned empty series: country='CH' indicator='interest rate'"
        raise DataUnavailableError(msg)


class _FakeSNBSuccess:
    """SNB native — zimoma cube SARON row. Monthly cadence, yield_bps signed."""

    def __init__(self, *, yield_bps: int = 125) -> None:
        self.yield_bps = yield_bps

    async def fetch_saron(self, start: date, end: date) -> list[Observation]:
        # Monthly observations anchored to the 1st of each month.
        out: list[Observation] = []
        year, month = start.year, start.month
        while date(year, month, 1) <= end:
            out.append(
                Observation(
                    country_code="CH",
                    observation_date=date(year, month, 1),
                    tenor_years=0.01,
                    yield_bps=self.yield_bps,
                    source="SNB",
                    source_series_id="zimoma:SARON",
                )
            )
            month += 1
            if month > 12:
                month = 1
                year += 1
        return out


class _FakeSNBUnavailable:
    """Simulates an SNB host outage / schema drift."""

    async def fetch_saron(self, start: date, end: date) -> list[Observation]:
        _ = start, end
        msg = "SNB zimoma unreachable (test-fake)"
        raise DataUnavailableError(msg)


class _FakeTESeSuccess:
    """TE primary path for SE — returns daily Riksbank policy-rate obs (pct)."""

    def __init__(self, *, pct: float = 4.0) -> None:
        self.pct = pct

    async def fetch_se_policy_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        out: list[_FakeTEIndicatorObs] = []
        d = start
        while d <= end:
            out.append(
                _FakeTEIndicatorObs(
                    observation_date=d, value=self.pct, historical_data_symbol="SWRRATEI"
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeTESeUnavailable:
    """TE primary fails for SE — cascade fails over to Riksbank native."""

    async def fetch_se_policy_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        _ = start, end
        msg = "TE returned empty series: country='SE' indicator='interest rate'"
        raise DataUnavailableError(msg)


class _FakeRiksbankSuccess:
    """Riksbank native — Swea SECBREPOEFF daily series."""

    def __init__(self, *, yield_bps: int = 375) -> None:
        self.yield_bps = yield_bps

    async def fetch_policy_rate(self, start: date, end: date) -> list[Observation]:
        out: list[Observation] = []
        d = start
        while d <= end:
            out.append(
                Observation(
                    country_code="SE",
                    observation_date=d,
                    tenor_years=0.01,
                    yield_bps=self.yield_bps,  # default 3.75 % differs from TE to prove cascade
                    source="RIKSBANK",
                    source_series_id="SECBREPOEFF",
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeRiksbankUnavailable:
    """Simulates a Swea host outage / rate-limit exhaustion."""

    async def fetch_policy_rate(self, start: date, end: date) -> list[Observation]:
        _ = start, end
        msg = "Riksbank Swea unreachable (test-fake)"
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
# M1 AU (Sprint T — TE primary → RBA F1 native → FRED stale-flagged)
# ---------------------------------------------------------------------------


class TestBuildM1Au:
    @pytest.mark.asyncio
    async def test_te_primary_path(self) -> None:
        """TE succeeds → canonical daily RBA-sourced series, no staleness flags."""
        fred = _FakeFredConnector()
        rba = _FakeRBASuccess()  # present but skipped (TE wins priority)
        te = _FakeTEAuSuccess(pct=4.10)
        inputs = await build_m1_au_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            rba=rba,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.country_code == "AU"
        assert inputs.policy_rate_pct == pytest.approx(0.041)  # TE 4.10 %
        assert "AU_CASH_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "AU_CASH_RATE_RBA_NATIVE" not in inputs.upstream_flags
        assert "AU_CASH_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "EXPECTED_INFLATION_CB_TARGET" in inputs.upstream_flags
        assert "AU_BS_GDP_PROXY_ZERO" in inputs.upstream_flags
        assert inputs.source_connector == ("te",)
        assert inputs.r_star_pct == pytest.approx(0.0075)
        # RBA inflation target midpoint 2.5 %.
        assert inputs.expected_inflation_5y_pct == pytest.approx(0.025)

    @pytest.mark.asyncio
    async def test_rba_secondary_when_te_unavailable(self) -> None:
        """TE raises DataUnavailableError → RBA F1 native takes over (robust path)."""
        fred = _FakeFredConnector()
        rba = _FakeRBASuccess(yield_bps=395)
        te = _FakeTEAuUnavailable()
        inputs = await build_m1_au_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            rba=rba,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.0395)  # RBA 3.95 %
        assert "AU_CASH_RATE_RBA_NATIVE" in inputs.upstream_flags
        assert "AU_CASH_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "AU_CASH_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("rba",)

    @pytest.mark.asyncio
    async def test_fred_last_resort_stale_flagged(self) -> None:
        """TE + RBA both fail → FRED emits staleness flags."""
        fred = _FakeFredConnector()
        rba = _FakeRBAUnavailable()
        te = _FakeTEAuUnavailable()
        inputs = await build_m1_au_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            rba=rba,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.04)  # FRED 4.00 %
        assert "AU_CASH_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "AU_CASH_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "AU_CASH_RATE_RBA_NATIVE" not in inputs.upstream_flags
        assert inputs.source_connector == ("fred",)

    @pytest.mark.asyncio
    async def test_fred_only_when_te_and_rba_absent(self) -> None:
        """te=None + rba=None → FRED path still emits staleness flags."""
        fred = _FakeFredConnector()
        inputs = await build_m1_au_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            history_years=2,
        )
        assert inputs.country_code == "AU"
        assert inputs.source_connector == ("fred",)
        assert "AU_CASH_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_all_sources_fail_raises(self) -> None:
        """TE unavailable + RBA unavailable + FRED empty → ValueError."""

        class _EmptyFred:
            async def fetch_series(
                self, series_id: str, start: date, end: date
            ) -> list[Observation]:
                _ = series_id, start, end
                return []

        with pytest.raises(ValueError, match="TE, RBA, and FRED"):
            await build_m1_au_inputs(
                _EmptyFred(),  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=_FakeTEAuUnavailable(),  # type: ignore[arg-type]
                rba=_FakeRBAUnavailable(),  # type: ignore[arg-type]
                history_years=1,
            )

    @pytest.mark.asyncio
    async def test_au_flags_include_bs_gdp_proxy_zero(self) -> None:
        """AU BS/GDP ratio is placeholder — always emits AU_BS_GDP_PROXY_ZERO."""
        fred = _FakeFredConnector()
        te = _FakeTEAuSuccess(pct=4.10)
        inputs = await build_m1_au_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.balance_sheet_pct_gdp_current == 0.0
        assert inputs.balance_sheet_pct_gdp_12m_ago == 0.0
        assert "AU_BS_GDP_PROXY_ZERO" in inputs.upstream_flags


# ---------------------------------------------------------------------------
# M2 AU (Sprint T — scaffold raises until AU gap + CPI connectors land)
# ---------------------------------------------------------------------------


class TestBuildM2Au:
    @pytest.mark.asyncio
    async def test_raises_insufficient_data_pending_connectors(self) -> None:
        """M2 AU scaffold is wire-ready but raises until AU gap/CPI land."""
        fred = _FakeFredConnector()
        te = _FakeTEAuSuccess(pct=4.10)
        with pytest.raises(InsufficientDataError, match="CAL-AU"):
            await build_m2_au_inputs(
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
            await build_m2_au_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# ---------------------------------------------------------------------------
# M4 AU (Sprint T — scaffold raises until ≥5 custom-FCI components wired)
# ---------------------------------------------------------------------------


class TestBuildM4Au:
    @pytest.mark.asyncio
    async def test_raises_insufficient_components(self) -> None:
        """M4 AU scaffold raises until ≥5 FCI components wire."""
        fred = _FakeFredConnector()
        te = _FakeTEAuSuccess(pct=4.10)
        rba = _FakeRBASuccess()
        with pytest.raises(InsufficientDataError, match="CAL-AU-M4-FCI"):
            await build_m4_au_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                rba=rba,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_raises_without_connectors(self) -> None:
        """Scaffold raises regardless of connector presence."""
        fred = _FakeFredConnector()
        with pytest.raises(InsufficientDataError):
            await build_m4_au_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# ---------------------------------------------------------------------------
# M1 NZ (Sprint U-NZ — TE primary → RBNZ scaffold → FRED stale-flagged)
# ---------------------------------------------------------------------------


class TestBuildM1Nz:
    @pytest.mark.asyncio
    async def test_te_primary_path(self) -> None:
        """TE succeeds → canonical daily RBNZ-sourced series, no staleness flags."""
        fred = _FakeFredConnector()
        rbnz = _FakeRBNZSuccess()  # present but skipped (TE wins priority)
        te = _FakeTENzSuccess(pct=3.75)
        inputs = await build_m1_nz_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            rbnz=rbnz,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.country_code == "NZ"
        assert inputs.policy_rate_pct == pytest.approx(0.0375)  # TE 3.75 %
        assert "NZ_OCR_TE_PRIMARY" in inputs.upstream_flags
        assert "NZ_OCR_RBNZ_NATIVE" not in inputs.upstream_flags
        assert "NZ_OCR_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "EXPECTED_INFLATION_CB_TARGET" in inputs.upstream_flags
        assert "NZ_BS_GDP_PROXY_ZERO" in inputs.upstream_flags
        assert inputs.source_connector == ("te",)
        assert inputs.r_star_pct == pytest.approx(0.0175)
        # RBNZ 1-3 % band midpoint 2 %.
        assert inputs.expected_inflation_5y_pct == pytest.approx(0.02)

    @pytest.mark.asyncio
    async def test_rbnz_secondary_when_te_unavailable(self) -> None:
        """TE raises DataUnavailableError → RBNZ B2 native takes over (robust path)."""
        fred = _FakeFredConnector()
        rbnz = _FakeRBNZSuccess(yield_bps=360)
        te = _FakeTENzUnavailable()
        inputs = await build_m1_nz_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            rbnz=rbnz,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.036)  # RBNZ 3.60 %
        assert "NZ_OCR_RBNZ_NATIVE" in inputs.upstream_flags
        assert "NZ_OCR_TE_UNAVAILABLE" in inputs.upstream_flags
        assert "NZ_OCR_TE_PRIMARY" not in inputs.upstream_flags
        assert "NZ_OCR_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("rbnz",)

    @pytest.mark.asyncio
    async def test_fred_last_resort_stale_flagged(self) -> None:
        """TE + RBNZ both fail → FRED emits staleness flags (current live state)."""
        fred = _FakeFredConnector()
        rbnz = _FakeRBNZUnavailable()  # simulates perimeter 403
        te = _FakeTENzUnavailable()
        inputs = await build_m1_nz_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            rbnz=rbnz,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.0375)  # FRED 3.75 %
        assert "NZ_OCR_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "NZ_OCR_TE_UNAVAILABLE" in inputs.upstream_flags
        assert "NZ_OCR_RBNZ_UNAVAILABLE" in inputs.upstream_flags
        assert "NZ_OCR_TE_PRIMARY" not in inputs.upstream_flags
        assert "NZ_OCR_RBNZ_NATIVE" not in inputs.upstream_flags
        assert inputs.source_connector == ("fred",)

    @pytest.mark.asyncio
    async def test_fred_only_when_te_and_rbnz_absent(self) -> None:
        """te=None + rbnz=None → FRED path still emits staleness flags."""
        fred = _FakeFredConnector()
        inputs = await build_m1_nz_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            history_years=2,
        )
        assert inputs.country_code == "NZ"
        assert inputs.source_connector == ("fred",)
        assert "NZ_OCR_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_all_sources_fail_raises(self) -> None:
        """TE unavailable + RBNZ unavailable + FRED empty → ValueError."""

        class _EmptyFred:
            async def fetch_series(
                self, series_id: str, start: date, end: date
            ) -> list[Observation]:
                _ = series_id, start, end
                return []

        with pytest.raises(ValueError, match="TE, RBNZ, and FRED"):
            await build_m1_nz_inputs(
                _EmptyFred(),  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=_FakeTENzUnavailable(),  # type: ignore[arg-type]
                rbnz=_FakeRBNZUnavailable(),  # type: ignore[arg-type]
                history_years=1,
            )

    @pytest.mark.asyncio
    async def test_nz_flags_include_bs_gdp_proxy_zero(self) -> None:
        """NZ BS/GDP ratio is placeholder — always emits NZ_BS_GDP_PROXY_ZERO."""
        fred = _FakeFredConnector()
        te = _FakeTENzSuccess(pct=3.75)
        inputs = await build_m1_nz_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.balance_sheet_pct_gdp_current == 0.0
        assert inputs.balance_sheet_pct_gdp_12m_ago == 0.0
        assert "NZ_BS_GDP_PROXY_ZERO" in inputs.upstream_flags


# ---------------------------------------------------------------------------
# M2 NZ (Sprint U-NZ — scaffold raises until NZ gap + CPI connectors land)
# ---------------------------------------------------------------------------


class TestBuildM2Nz:
    @pytest.mark.asyncio
    async def test_raises_insufficient_data_pending_connectors(self) -> None:
        """M2 NZ scaffold is wire-ready but raises until NZ gap/CPI land."""
        fred = _FakeFredConnector()
        te = _FakeTENzSuccess(pct=3.75)
        with pytest.raises(InsufficientDataError, match="CAL-NZ"):
            await build_m2_nz_inputs(
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
            await build_m2_nz_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# ---------------------------------------------------------------------------
# M4 NZ (Sprint U-NZ — scaffold raises until ≥5 custom-FCI components wired)
# ---------------------------------------------------------------------------


class TestBuildM4Nz:
    @pytest.mark.asyncio
    async def test_raises_insufficient_components(self) -> None:
        """M4 NZ scaffold raises until ≥5 FCI components wire."""
        fred = _FakeFredConnector()
        te = _FakeTENzSuccess(pct=3.75)
        rbnz = _FakeRBNZSuccess()
        with pytest.raises(InsufficientDataError, match="CAL-NZ-M4-FCI"):
            await build_m4_nz_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                rbnz=rbnz,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_raises_without_connectors(self) -> None:
        """Scaffold raises regardless of connector presence."""
        fred = _FakeFredConnector()
        with pytest.raises(InsufficientDataError):
            await build_m4_nz_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# M1 CH (Sprint V — TE primary → SNB native → FRED stale-flagged; negatives)
# ---------------------------------------------------------------------------


class TestBuildM1Ch:
    @pytest.mark.asyncio
    async def test_te_primary_path(self) -> None:
        """TE succeeds → canonical daily SNB-sourced series, no staleness flags."""
        fred = _FakeFredConnector()
        snb = _FakeSNBSuccess()  # present but skipped (TE wins priority)
        te = _FakeTEChSuccess(pct=1.5)
        inputs = await build_m1_ch_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            snb=snb,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.country_code == "CH"
        assert inputs.policy_rate_pct == pytest.approx(0.015)  # TE 1.50 %
        assert "CH_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "CH_POLICY_RATE_SNB_NATIVE" not in inputs.upstream_flags
        assert "CH_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "EXPECTED_INFLATION_CB_TARGET" in inputs.upstream_flags
        assert "CH_INFLATION_TARGET_BAND" in inputs.upstream_flags
        assert "CH_BS_GDP_PROXY_ZERO" in inputs.upstream_flags
        assert inputs.source_connector == ("te",)
        assert inputs.r_star_pct == pytest.approx(0.0025)
        # 1.5 % policy, all positive → no negative-rate-era flag.
        assert "CH_NEGATIVE_RATE_ERA_DATA" not in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_te_primary_negative_rate_era_flag(self) -> None:
        """Negative-rate window surfaces CH_NEGATIVE_RATE_ERA_DATA downstream.

        Pinning TE to -0.75 % across the lookback window mirrors the
        2020 SNB policy-rate regime; the cascade must propagate the
        sign into ``policy_rate_pct`` **and** add the negative-era
        flag so regime classifiers can branch appropriately.
        """
        fred = _FakeFredConnector()
        te = _FakeTEChSuccess(pct=-0.75)
        inputs = await build_m1_ch_inputs(
            fred,  # type: ignore[arg-type]
            date(2020, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(-0.0075)  # -0.75 %
        assert "CH_NEGATIVE_RATE_ERA_DATA" in inputs.upstream_flags
        assert "CH_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags
        # Real-shadow history must preserve signs — pre-conversion
        # policy is -0.75 %, inflation target 1 %, so real shadow =
        # -0.0075 - 0.01 = -0.0175. Every monthly sample should match.
        for r in inputs.real_shadow_rate_history:
            assert r == pytest.approx(-0.0175, abs=1e-6)

    @pytest.mark.asyncio
    async def test_snb_secondary_when_te_unavailable(self) -> None:
        """TE raises DataUnavailableError → SNB SARON native takes over."""
        fred = _FakeFredConnector()
        snb = _FakeSNBSuccess(yield_bps=125)  # 1.25 %
        te = _FakeTEChUnavailable()
        inputs = await build_m1_ch_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            snb=snb,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.0125)  # SNB 1.25 %
        assert "CH_POLICY_RATE_SNB_NATIVE" in inputs.upstream_flags
        assert "CH_POLICY_RATE_SNB_NATIVE_MONTHLY" in inputs.upstream_flags
        assert "CH_POLICY_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "CH_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        # Critically: SNB native does NOT carry CALIBRATION_STALE.
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("snb",)

    @pytest.mark.asyncio
    async def test_snb_native_preserves_negative_values(self) -> None:
        """Negative SNB SARON observations surface correctly on the secondary path."""
        fred = _FakeFredConnector()
        snb = _FakeSNBSuccess(yield_bps=-75)  # -0.75 % SNB corridor
        te = _FakeTEChUnavailable()
        inputs = await build_m1_ch_inputs(
            fred,  # type: ignore[arg-type]
            date(2020, 12, 31),
            te=te,  # type: ignore[arg-type]
            snb=snb,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(-0.0075)
        assert "CH_NEGATIVE_RATE_ERA_DATA" in inputs.upstream_flags
        assert "CH_POLICY_RATE_SNB_NATIVE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_fred_last_resort_stale_flagged(self) -> None:
        """TE + SNB both fail → FRED emits staleness flags."""
        fred = _FakeFredConnector()
        snb = _FakeSNBUnavailable()
        te = _FakeTEChUnavailable()
        inputs = await build_m1_ch_inputs(
            fred,  # type: ignore[arg-type]
            date(2020, 12, 31),
            te=te,  # type: ignore[arg-type]
            snb=snb,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(-0.0025)  # FRED -0.25 %
        assert "CH_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "CH_POLICY_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "CH_POLICY_RATE_SNB_NATIVE" not in inputs.upstream_flags
        # FRED fixture returns -0.25 %, so the negative-era flag still
        # fires — proves the flag attaches to the value, not the source.
        assert "CH_NEGATIVE_RATE_ERA_DATA" in inputs.upstream_flags
        assert inputs.source_connector == ("fred",)

    @pytest.mark.asyncio
    async def test_fred_only_when_te_and_snb_absent(self) -> None:
        """te=None + snb=None → FRED path still emits staleness flags."""
        fred = _FakeFredConnector()
        inputs = await build_m1_ch_inputs(
            fred,  # type: ignore[arg-type]
            date(2020, 12, 31),
            history_years=2,
        )
        assert inputs.country_code == "CH"
        assert inputs.source_connector == ("fred",)
        assert "CH_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_all_sources_fail_raises(self) -> None:
        """TE unavailable + SNB unavailable + FRED empty → ValueError."""

        class _EmptyFred:
            async def fetch_series(
                self, series_id: str, start: date, end: date
            ) -> list[Observation]:
                _ = series_id, start, end
                return []

        with pytest.raises(ValueError, match="TE, SNB, and FRED"):
            await build_m1_ch_inputs(
                _EmptyFred(),  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=_FakeTEChUnavailable(),  # type: ignore[arg-type]
                snb=_FakeSNBUnavailable(),  # type: ignore[arg-type]
                history_years=1,
            )

    @pytest.mark.asyncio
    async def test_ch_flags_include_bs_gdp_proxy_zero(self) -> None:
        """CH BS/GDP ratio is placeholder — always emits CH_BS_GDP_PROXY_ZERO."""
        fred = _FakeFredConnector()
        te = _FakeTEChSuccess(pct=1.5)
        inputs = await build_m1_ch_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.balance_sheet_pct_gdp_current == 0.0
        assert inputs.balance_sheet_pct_gdp_12m_ago == 0.0
        assert "CH_BS_GDP_PROXY_ZERO" in inputs.upstream_flags


# ---------------------------------------------------------------------------
# M2 CH (Sprint V — scaffold raises until CH gap + CPI connectors land)
# ---------------------------------------------------------------------------


class TestBuildM2Ch:
    @pytest.mark.asyncio
    async def test_raises_insufficient_data_pending_connectors(self) -> None:
        """M2 CH scaffold is wire-ready but raises until CH gap/CPI land."""
        fred = _FakeFredConnector()
        te = _FakeTEChSuccess(pct=1.5)
        with pytest.raises(InsufficientDataError, match="CAL-CH"):
            await build_m2_ch_inputs(
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
            await build_m2_ch_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# ---------------------------------------------------------------------------
# M4 CH (Sprint V — scaffold raises until ≥5 custom-FCI components wired)
# ---------------------------------------------------------------------------


class TestBuildM4Ch:
    @pytest.mark.asyncio
    async def test_raises_insufficient_components(self) -> None:
        """M4 CH scaffold raises until ≥5 FCI components wire."""
        fred = _FakeFredConnector()
        te = _FakeTEChSuccess(pct=1.5)
        snb = _FakeSNBSuccess()
        with pytest.raises(InsufficientDataError, match="CAL-CH-M4-FCI"):
            await build_m4_ch_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                snb=snb,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_raises_without_connectors(self) -> None:
        """Scaffold raises regardless of connector presence."""
        fred = _FakeFredConnector()
        with pytest.raises(InsufficientDataError):
            await build_m4_ch_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# ---------------------------------------------------------------------------
# M1 NO (Sprint X-NO — TE primary → Norges Bank native → FRED stale-flagged)
# ---------------------------------------------------------------------------


class TestBuildM1No:
    @pytest.mark.asyncio
    async def test_te_primary_path(self) -> None:
        """TE succeeds → canonical daily Norges-Bank-sourced series, no staleness."""
        fred = _FakeFredConnector()
        norgesbank = _FakeNorgesBankSuccess()  # present but skipped (TE wins priority)
        te = _FakeTENoSuccess(pct=4.5)
        inputs = await build_m1_no_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            norgesbank=norgesbank,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.country_code == "NO"
        assert inputs.policy_rate_pct == pytest.approx(0.045)  # TE 4.50 %
        assert "NO_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "NO_POLICY_RATE_NORGESBANK_NATIVE" not in inputs.upstream_flags
        assert "NO_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "EXPECTED_INFLATION_CB_TARGET" in inputs.upstream_flags
        assert "NO_BS_GDP_PROXY_ZERO" in inputs.upstream_flags
        assert inputs.source_connector == ("te",)
        assert inputs.r_star_pct == pytest.approx(0.0125)

    @pytest.mark.asyncio
    async def test_no_negative_rate_flag_emitted(self) -> None:
        """NO standard positive-only contract — no country-specific neg flag."""
        fred = _FakeFredConnector()
        te = _FakeTENoSuccess(pct=4.5)
        inputs = await build_m1_no_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        # Cascade does not attach CH_NEGATIVE_RATE_ERA_DATA for NO.
        # Verify no country-specific negative-era flag lands — regardless
        # of whether a CH-labelled flag would fire (it shouldn't).
        assert not any("NEGATIVE_RATE" in f for f in inputs.upstream_flags)

    @pytest.mark.asyncio
    async def test_norgesbank_secondary_when_te_unavailable(self) -> None:
        """TE raises → Norges Bank DataAPI native takes over (daily parity)."""
        fred = _FakeFredConnector()
        norgesbank = _FakeNorgesBankSuccess(yield_bps=425)  # 4.25 %
        te = _FakeTENoUnavailable()
        inputs = await build_m1_no_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            norgesbank=norgesbank,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.0425)  # Norges Bank 4.25 %
        assert "NO_POLICY_RATE_NORGESBANK_NATIVE" in inputs.upstream_flags
        assert "NO_POLICY_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "NO_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        # Critically: Norges Bank native is daily-parity with TE so no
        # staleness or monthly qualifier flag surfaces — contrast CH
        # (SNB monthly).
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert not any("MONTHLY" in f for f in inputs.upstream_flags)
        assert inputs.source_connector == ("norgesbank",)

    @pytest.mark.asyncio
    async def test_fred_last_resort_stale_flagged(self) -> None:
        """TE + Norges Bank both fail → FRED emits staleness flags."""
        fred = _FakeFredConnector()
        norgesbank = _FakeNorgesBankUnavailable()
        te = _FakeTENoUnavailable()
        inputs = await build_m1_no_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            norgesbank=norgesbank,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.04)  # FRED 4.00 %
        assert "NO_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "NO_POLICY_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "NO_POLICY_RATE_NORGESBANK_NATIVE" not in inputs.upstream_flags
        assert inputs.source_connector == ("fred",)

    @pytest.mark.asyncio
    async def test_fred_only_when_te_and_norgesbank_absent(self) -> None:
        """te=None + norgesbank=None → FRED path still emits staleness flags."""
        fred = _FakeFredConnector()
        inputs = await build_m1_no_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            history_years=2,
        )
        assert inputs.country_code == "NO"
        assert inputs.source_connector == ("fred",)
        assert "NO_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_all_sources_fail_raises(self) -> None:
        """TE unavailable + Norges Bank unavailable + FRED empty → ValueError."""

        class _EmptyFred:
            async def fetch_series(
                self, series_id: str, start: date, end: date
            ) -> list[Observation]:
                _ = series_id, start, end
                return []

        with pytest.raises(ValueError, match="TE, Norges Bank, and FRED"):
            await build_m1_no_inputs(
                _EmptyFred(),  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=_FakeTENoUnavailable(),  # type: ignore[arg-type]
                norgesbank=_FakeNorgesBankUnavailable(),  # type: ignore[arg-type]
                history_years=1,
            )

    @pytest.mark.asyncio
    async def test_no_flags_include_bs_gdp_proxy_zero(self) -> None:
        """NO BS/GDP ratio is placeholder — always emits NO_BS_GDP_PROXY_ZERO."""
        fred = _FakeFredConnector()
        te = _FakeTENoSuccess(pct=4.5)
        inputs = await build_m1_no_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.balance_sheet_pct_gdp_current == 0.0
        assert inputs.balance_sheet_pct_gdp_12m_ago == 0.0
        assert "NO_BS_GDP_PROXY_ZERO" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_zero_policy_rate_covid_trough(self) -> None:
        """2020-2021 COVID trough anchors: NO policy-rate 0 % flows through clean."""
        fred = _FakeFredConnector()
        te = _FakeTENoSuccess(pct=0.0)
        inputs = await build_m1_no_inputs(
            fred,  # type: ignore[arg-type]
            date(2021, 6, 30),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.0)
        assert "NO_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags


# ---------------------------------------------------------------------------
# M2 NO (Sprint X-NO — scaffold raises until NO CPI + gap connectors land)
# ---------------------------------------------------------------------------


class TestBuildM2No:
    @pytest.mark.asyncio
    async def test_raises_insufficient_data_pending_connectors(self) -> None:
        """M2 NO scaffold is wire-ready but raises until NO gap/CPI land."""
        fred = _FakeFredConnector()
        te = _FakeTENoSuccess(pct=4.5)
        with pytest.raises(InsufficientDataError, match="CAL-NO"):
            await build_m2_no_inputs(
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
            await build_m2_no_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# ---------------------------------------------------------------------------
# M4 NO (Sprint X-NO — scaffold raises until ≥5 custom-FCI components wired)
# ---------------------------------------------------------------------------


class TestBuildM4No:
    @pytest.mark.asyncio
    async def test_raises_insufficient_components(self) -> None:
        """M4 NO scaffold raises until ≥5 FCI components wire."""
        fred = _FakeFredConnector()
        te = _FakeTENoSuccess(pct=4.5)
        norgesbank = _FakeNorgesBankSuccess()
        with pytest.raises(InsufficientDataError, match="CAL-NO-M4-FCI"):
            await build_m4_no_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                norgesbank=norgesbank,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_raises_without_connectors(self) -> None:
        """Scaffold raises regardless of connector presence."""
        fred = _FakeFredConnector()
        with pytest.raises(InsufficientDataError):
            await build_m4_no_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# ---------------------------------------------------------------------------
# M1 SE (Sprint W-SE — TE primary → Riksbank native → FRED stale-flagged)
# ---------------------------------------------------------------------------


class TestBuildM1Se:
    @pytest.mark.asyncio
    async def test_te_primary_path(self) -> None:
        """TE succeeds → canonical daily Riksbank-sourced series, no staleness flags."""
        fred = _FakeFredConnector()
        riksbank = _FakeRiksbankSuccess()  # present but skipped (TE wins priority)
        te = _FakeTESeSuccess(pct=4.0)
        inputs = await build_m1_se_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            riksbank=riksbank,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.country_code == "SE"
        assert inputs.policy_rate_pct == pytest.approx(0.04)  # TE 4.00 %
        assert "SE_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "SE_POLICY_RATE_RIKSBANK_NATIVE" not in inputs.upstream_flags
        assert "SE_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "EXPECTED_INFLATION_CB_TARGET" in inputs.upstream_flags
        # SE uses a clean 2 % CPIF point target — no band flag (contrast CH).
        assert "SE_INFLATION_TARGET_BAND" not in inputs.upstream_flags
        assert "CH_INFLATION_TARGET_BAND" not in inputs.upstream_flags
        assert "SE_BS_GDP_PROXY_ZERO" in inputs.upstream_flags
        assert inputs.source_connector == ("te",)
        assert inputs.r_star_pct == pytest.approx(0.0075)
        # 4.0 % policy, all positive → no negative-rate-era flag.
        assert "SE_NEGATIVE_RATE_ERA_DATA" not in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_te_primary_negative_rate_era_flag(self) -> None:
        """Negative-rate window surfaces SE_NEGATIVE_RATE_ERA_DATA downstream.

        Pinning TE to -0.50 % across the lookback window mirrors the
        Feb 2016 → Dec 2018 Riksbank deep-corridor regime; the cascade
        must propagate the sign into ``policy_rate_pct`` **and** add
        the negative-era flag so regime classifiers can branch
        appropriately — matching the Sprint V-CH flag contract but with
        the SE-specific flag name.
        """
        fred = _FakeFredConnector()
        te = _FakeTESeSuccess(pct=-0.5)
        inputs = await build_m1_se_inputs(
            fred,  # type: ignore[arg-type]
            date(2017, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(-0.005)  # -0.50 %
        assert "SE_NEGATIVE_RATE_ERA_DATA" in inputs.upstream_flags
        assert "SE_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags
        # Real-shadow history must preserve signs — pre-conversion
        # policy -0.50 %, inflation target 2 % CPIF, so real shadow =
        # -0.005 - 0.02 = -0.025. Every monthly sample should match.
        for r in inputs.real_shadow_rate_history:
            assert r == pytest.approx(-0.025, abs=1e-6)

    @pytest.mark.asyncio
    async def test_riksbank_secondary_when_te_unavailable(self) -> None:
        """TE raises DataUnavailableError → Riksbank Swea native takes over."""
        fred = _FakeFredConnector()
        riksbank = _FakeRiksbankSuccess(yield_bps=375)  # 3.75 %
        te = _FakeTESeUnavailable()
        inputs = await build_m1_se_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            riksbank=riksbank,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.0375)  # Riksbank 3.75 %
        assert "SE_POLICY_RATE_RIKSBANK_NATIVE" in inputs.upstream_flags
        # SE Riksbank native is daily — no *_MONTHLY cadence flag
        # (contrast CH where SNB SARON is monthly).
        assert "SE_POLICY_RATE_RIKSBANK_NATIVE_MONTHLY" not in inputs.upstream_flags
        assert "SE_POLICY_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "SE_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("riksbank",)

    @pytest.mark.asyncio
    async def test_riksbank_native_preserves_negative_values(self) -> None:
        """Negative Riksbank observations surface correctly on the secondary path."""
        fred = _FakeFredConnector()
        riksbank = _FakeRiksbankSuccess(yield_bps=-50)  # -0.50 % corridor trough
        te = _FakeTESeUnavailable()
        inputs = await build_m1_se_inputs(
            fred,  # type: ignore[arg-type]
            date(2017, 12, 31),
            te=te,  # type: ignore[arg-type]
            riksbank=riksbank,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(-0.005)
        assert "SE_NEGATIVE_RATE_ERA_DATA" in inputs.upstream_flags
        assert "SE_POLICY_RATE_RIKSBANK_NATIVE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_fred_last_resort_stale_flagged(self) -> None:
        """TE + Riksbank both fail → FRED emits staleness flags."""
        fred = _FakeFredConnector()
        riksbank = _FakeRiksbankUnavailable()
        te = _FakeTESeUnavailable()
        inputs = await build_m1_se_inputs(
            fred,  # type: ignore[arg-type]
            date(2020, 12, 31),
            te=te,  # type: ignore[arg-type]
            riksbank=riksbank,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(-0.0025)  # FRED -0.25 %
        assert "SE_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "SE_POLICY_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "SE_POLICY_RATE_RIKSBANK_NATIVE" not in inputs.upstream_flags
        # FRED fixture returns -0.25 %, so the negative-era flag still
        # fires — proves the flag attaches to the value, not the source.
        assert "SE_NEGATIVE_RATE_ERA_DATA" in inputs.upstream_flags
        assert inputs.source_connector == ("fred",)

    @pytest.mark.asyncio
    async def test_fred_only_when_te_and_riksbank_absent(self) -> None:
        """te=None + riksbank=None → FRED path still emits staleness flags."""
        fred = _FakeFredConnector()
        inputs = await build_m1_se_inputs(
            fred,  # type: ignore[arg-type]
            date(2020, 12, 31),
            history_years=2,
        )
        assert inputs.country_code == "SE"
        assert inputs.source_connector == ("fred",)
        assert "SE_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_all_sources_fail_raises(self) -> None:
        """TE unavailable + Riksbank unavailable + FRED empty → ValueError."""

        class _EmptyFred:
            async def fetch_series(
                self, series_id: str, start: date, end: date
            ) -> list[Observation]:
                _ = series_id, start, end
                return []

        with pytest.raises(ValueError, match="TE, Riksbank, and FRED"):
            await build_m1_se_inputs(
                _EmptyFred(),  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=_FakeTESeUnavailable(),  # type: ignore[arg-type]
                riksbank=_FakeRiksbankUnavailable(),  # type: ignore[arg-type]
                history_years=1,
            )

    @pytest.mark.asyncio
    async def test_se_flags_include_bs_gdp_proxy_zero(self) -> None:
        """SE BS/GDP ratio is placeholder — always emits SE_BS_GDP_PROXY_ZERO."""
        fred = _FakeFredConnector()
        te = _FakeTESeSuccess(pct=4.0)
        inputs = await build_m1_se_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.balance_sheet_pct_gdp_current == 0.0
        assert inputs.balance_sheet_pct_gdp_12m_ago == 0.0
        assert "SE_BS_GDP_PROXY_ZERO" in inputs.upstream_flags


# ---------------------------------------------------------------------------
# M2 SE (Sprint W-SE — scaffold raises until SE gap + CPI connectors land)
# ---------------------------------------------------------------------------


class TestBuildM2Se:
    @pytest.mark.asyncio
    async def test_raises_insufficient_data_pending_connectors(self) -> None:
        """M2 SE scaffold is wire-ready but raises until SE gap/CPI land."""
        fred = _FakeFredConnector()
        te = _FakeTESeSuccess(pct=4.0)
        with pytest.raises(InsufficientDataError, match="CAL-SE"):
            await build_m2_se_inputs(
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
            await build_m2_se_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                history_years=2,
            )


# ---------------------------------------------------------------------------
# M4 SE (Sprint W-SE — scaffold raises until ≥5 custom-FCI components wired)
# ---------------------------------------------------------------------------


class TestBuildM4Se:
    @pytest.mark.asyncio
    async def test_raises_insufficient_components(self) -> None:
        """M4 SE scaffold raises until ≥5 FCI components wire."""
        fred = _FakeFredConnector()
        te = _FakeTESeSuccess(pct=4.0)
        riksbank = _FakeRiksbankSuccess()
        with pytest.raises(InsufficientDataError, match="CAL-SE-M4-FCI"):
            await build_m4_se_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                riksbank=riksbank,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_raises_without_connectors(self) -> None:
        """Scaffold raises regardless of connector presence."""
        fred = _FakeFredConnector()
        with pytest.raises(InsufficientDataError):
            await build_m4_se_inputs(
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
        # NZ + CH + NO all wired (Sprint U-NZ + Sprint V-CH + Sprint X-NO);
        # SE remains Phase 2+ — probe with it.
        with pytest.raises(NotImplementedError, match="SE"):
            await builder.build_m1_inputs("SE", date(2024, 12, 31))

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
    async def test_build_m1_au_via_facade_te_primary(self) -> None:
        """AU M1 dispatch — TE handle present → canonical TE primary path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEAuSuccess(pct=4.10),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("AU", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "AU"
        assert "AU_CASH_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "AU_CASH_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("te",)

    @pytest.mark.asyncio
    async def test_build_m1_au_via_facade_rba_secondary(self) -> None:
        """AU M1 dispatch — TE absent, RBA handle present → native path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            rba=_FakeRBASuccess(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("AU", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "AU"
        assert "AU_CASH_RATE_RBA_NATIVE" in inputs.upstream_flags
        assert inputs.source_connector == ("rba",)

    @pytest.mark.asyncio
    async def test_build_m1_au_via_facade_fred_fallback(self) -> None:
        """AU M1 dispatch — FRED-only path (no TE/RBA handles) → stale flags."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("AU", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "AU"
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "AU_CASH_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_m2_au_dispatches_to_au_builder(self) -> None:
        """AU M2 dispatch routes to the AU scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEAuSuccess(pct=4.10),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-AU"):
            await builder.build_m2_inputs("AU", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_m4_au_dispatches_to_au_builder(self) -> None:
        """AU M4 dispatch routes to the AU scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEAuSuccess(pct=4.10),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-AU-M4-FCI"):
            await builder.build_m4_inputs("AU", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_build_m1_nz_via_facade_te_primary(self) -> None:
        """NZ M1 dispatch — TE handle present → canonical TE primary path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTENzSuccess(pct=3.75),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("NZ", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "NZ"
        assert "NZ_OCR_TE_PRIMARY" in inputs.upstream_flags
        assert "NZ_OCR_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("te",)

    @pytest.mark.asyncio
    async def test_build_m1_nz_via_facade_rbnz_secondary(self) -> None:
        """NZ M1 dispatch — TE absent, RBNZ handle present → native path (post-unblock)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            rbnz=_FakeRBNZSuccess(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("NZ", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "NZ"
        assert "NZ_OCR_RBNZ_NATIVE" in inputs.upstream_flags
        assert inputs.source_connector == ("rbnz",)

    @pytest.mark.asyncio
    async def test_build_m1_nz_via_facade_fred_fallback(self) -> None:
        """NZ M1 dispatch — TE unavailable + RBNZ 403 → FRED stale (current live state)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTENzUnavailable(),  # type: ignore[arg-type]
            rbnz=_FakeRBNZUnavailable(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("NZ", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "NZ"
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "NZ_OCR_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "NZ_OCR_RBNZ_UNAVAILABLE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_m2_nz_dispatches_to_nz_builder(self) -> None:
        """NZ M2 dispatch routes to the NZ scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTENzSuccess(pct=3.75),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-NZ"):
            await builder.build_m2_inputs("NZ", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_m4_nz_dispatches_to_nz_builder(self) -> None:
        """NZ M4 dispatch routes to the NZ scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTENzSuccess(pct=3.75),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-NZ-M4-FCI"):
            await builder.build_m4_inputs("NZ", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_build_m1_ch_via_facade_te_primary(self) -> None:
        """CH M1 dispatch — TE handle present → canonical TE primary path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEChSuccess(pct=1.5),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("CH", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "CH"
        assert "CH_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "CH_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("te",)

    @pytest.mark.asyncio
    async def test_build_m1_ch_via_facade_snb_secondary(self) -> None:
        """CH M1 dispatch — TE absent, SNB handle present → native path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            snb=_FakeSNBSuccess(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("CH", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "CH"
        assert "CH_POLICY_RATE_SNB_NATIVE" in inputs.upstream_flags
        assert "CH_POLICY_RATE_SNB_NATIVE_MONTHLY" in inputs.upstream_flags
        assert inputs.source_connector == ("snb",)

    @pytest.mark.asyncio
    async def test_build_m1_ch_via_facade_fred_fallback(self) -> None:
        """CH M1 dispatch — FRED-only path (no TE/SNB handles) → stale flags."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("CH", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "CH"
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "CH_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_m2_ch_dispatches_to_ch_builder(self) -> None:
        """CH M2 dispatch routes to the CH scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEChSuccess(pct=1.5),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-CH"):
            await builder.build_m2_inputs("CH", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_m4_ch_dispatches_to_ch_builder(self) -> None:
        """CH M4 dispatch routes to the CH scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEChSuccess(pct=1.5),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-CH-M4-FCI"):
            await builder.build_m4_inputs("CH", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_build_m1_no_via_facade_te_primary(self) -> None:
        """NO M1 dispatch — TE handle present → canonical TE primary path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTENoSuccess(pct=4.5),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("NO", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "NO"
        assert "NO_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "NO_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("te",)

    @pytest.mark.asyncio
    async def test_build_m1_no_via_facade_norgesbank_secondary(self) -> None:
        """NO M1 dispatch — TE absent, Norges Bank handle present → native path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            norgesbank=_FakeNorgesBankSuccess(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("NO", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "NO"
        assert "NO_POLICY_RATE_NORGESBANK_NATIVE" in inputs.upstream_flags
        # Daily-parity — no cadence qualifier / staleness flag on native path.
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("norgesbank",)

    @pytest.mark.asyncio
    async def test_build_m1_no_via_facade_fred_fallback(self) -> None:
        """NO M1 dispatch — FRED-only path (no TE/NB handles) → stale flags."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("NO", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "NO"
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "NO_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_m2_no_dispatches_to_no_builder(self) -> None:
        """NO M2 dispatch routes to the NO scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTENoSuccess(pct=4.5),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-NO"):
            await builder.build_m2_inputs("NO", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_m4_no_dispatches_to_no_builder(self) -> None:
        """NO M4 dispatch routes to the NO scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTENoSuccess(pct=4.5),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-NO-M4-FCI"):
            await builder.build_m4_inputs("NO", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_build_m1_se_via_facade_te_primary(self) -> None:
        """SE M1 dispatch — TE handle present → canonical TE primary path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTESeSuccess(pct=4.0),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("SE", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "SE"
        assert "SE_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "SE_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("te",)

    @pytest.mark.asyncio
    async def test_build_m1_se_via_facade_riksbank_secondary(self) -> None:
        """SE M1 dispatch — TE absent, Riksbank handle present → native path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            riksbank=_FakeRiksbankSuccess(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("SE", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "SE"
        assert "SE_POLICY_RATE_RIKSBANK_NATIVE" in inputs.upstream_flags
        # Daily-cadence native — no *_MONTHLY flag (contrast CH).
        assert "SE_POLICY_RATE_RIKSBANK_NATIVE_MONTHLY" not in inputs.upstream_flags
        assert inputs.source_connector == ("riksbank",)

    @pytest.mark.asyncio
    async def test_build_m1_se_via_facade_fred_fallback(self) -> None:
        """SE M1 dispatch — FRED-only path (no TE/Riksbank handles) → stale flags."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("SE", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "SE"
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "SE_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_m2_se_dispatches_to_se_builder(self) -> None:
        """SE M2 dispatch routes to the SE scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTESeSuccess(pct=4.0),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-SE"):
            await builder.build_m2_inputs("SE", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_m4_se_dispatches_to_se_builder(self) -> None:
        """SE M4 dispatch routes to the SE scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTESeSuccess(pct=4.0),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-SE-M4-FCI"):
            await builder.build_m4_inputs("SE", date(2024, 12, 31), history_years=2)

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
