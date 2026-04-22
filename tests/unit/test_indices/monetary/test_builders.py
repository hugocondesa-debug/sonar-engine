"""Unit tests for MonetaryInputsBuilder (CAL-100, week6 sprint 2b)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import ClassVar

import pytest

from sonar.connectors.base import Observation
from sonar.indices.monetary.builders import (
    FRED_AU_CASH_RATE_SERIES,
    FRED_CA_BANK_RATE_SERIES,
    FRED_CH_POLICY_RATE_SERIES,
    FRED_DK_POLICY_RATE_SERIES,
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
    build_m1_dk_inputs,
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
    build_m2_dk_inputs,
    build_m2_ea_inputs,
    build_m2_gb_inputs,
    build_m2_jp_inputs,
    build_m2_no_inputs,
    build_m2_nz_inputs,
    build_m2_se_inputs,
    build_m2_us_inputs,
    build_m4_au_inputs,
    build_m4_ca_inputs,
    build_m4_ch_inputs,
    build_m4_dk_inputs,
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
        elif series_id == FRED_DK_POLICY_RATE_SERIES:
            country_code = "DK"
            yield_bps_val = -50  # -0.50 % — negative-rate-era fixture value
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


class _FakeTEDkSuccess:
    """TE primary path for DK — returns daily Nationalbanken-discount-rate obs (pct)."""

    def __init__(self, *, pct: float = 3.25) -> None:
        self.pct = pct

    async def fetch_dk_policy_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        out: list[_FakeTEIndicatorObs] = []
        d = start
        while d <= end:
            out.append(
                _FakeTEIndicatorObs(
                    observation_date=d, value=self.pct, historical_data_symbol="DEBRDISC"
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeTEDkUnavailable:
    """TE primary fails for DK — cascade fails over to Nationalbanken native."""

    async def fetch_dk_policy_rate(self, start: date, end: date) -> list[_FakeTEIndicatorObs]:
        _ = start, end
        msg = "TE returned empty series: country='DK' indicator='interest rate'"
        raise DataUnavailableError(msg)


class _FakeNationalbankenSuccess:
    """Nationalbanken native — Statbank OIBNAA (CD rate) daily series."""

    def __init__(self, *, yield_bps: int = 325) -> None:
        self.yield_bps = yield_bps

    async def fetch_policy_rate(self, start: date, end: date) -> list[Observation]:
        out: list[Observation] = []
        d = start
        while d <= end:
            out.append(
                Observation(
                    country_code="DK",
                    observation_date=d,
                    tenor_years=0.01,
                    yield_bps=self.yield_bps,  # default 3.25 % differs from TE to prove cascade
                    source="NATIONALBANKEN",
                    source_series_id="OIBNAA",
                )
            )
            d = date.fromordinal(d.toordinal() + 1)
        return out


class _FakeNationalbankenUnavailable:
    """Simulates a Statbank.dk host outage / rate-limit exhaustion."""

    async def fetch_policy_rate(self, start: date, end: date) -> list[Observation]:
        _ = start, end
        msg = "Nationalbanken Statbank unreachable (test-fake)"
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


# M2 JP full compute lives in :class:`TestBuildM2SprintFFlipped` (Sprint F Commit 5).


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
# M2 CA (Sprint F — full compute; Sprint S + Sprint C scaffold deleted)
# ---------------------------------------------------------------------------
# The explicit per-country TestBuildM2* classes for the seven Sprint-F-flipped
# builders (CA/AU/NZ/CH/SE/NO/DK) now live in :class:`TestBuildM2SprintFFlipped`
# as a single parametric suite — happy path, CPI missing, gap missing,
# forecast-missing-partial, and legacy-unwired-raises scenarios.


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
# M2 AU (Sprint F — full compute; see :class:`TestBuildM2SprintFFlipped` below)
# ---------------------------------------------------------------------------


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


# M2 NZ full compute lives in :class:`TestBuildM2SprintFFlipped`.


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


# M2 CH full compute lives in :class:`TestBuildM2SprintFFlipped`.


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


# M2 NO full compute lives in :class:`TestBuildM2SprintFFlipped`.


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


# M2 SE full compute lives in :class:`TestBuildM2SprintFFlipped`.


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
# M1 DK (Sprint Y-DK — TE primary → Nationalbanken native → FRED stale-flagged)
# ---------------------------------------------------------------------------


class TestBuildM1Dk:
    @pytest.mark.asyncio
    async def test_te_primary_path(self) -> None:
        """TE succeeds → DEBRDISC discount-rate-sourced series, no staleness flags."""
        fred = _FakeFredConnector()
        nationalbanken = _FakeNationalbankenSuccess()  # present but skipped (TE wins)
        te = _FakeTEDkSuccess(pct=3.25)
        inputs = await build_m1_dk_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            nationalbanken=nationalbanken,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.country_code == "DK"
        assert inputs.policy_rate_pct == pytest.approx(0.0325)  # TE 3.25 %
        assert "DK_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "DK_POLICY_RATE_NATIONALBANKEN_NATIVE" not in inputs.upstream_flags
        assert "DK_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags
        # DK uses imported_eur_peg → DK-specific flag, NOT the
        # standard EXPECTED_INFLATION_CB_TARGET.
        assert "DK_INFLATION_TARGET_IMPORTED_FROM_EA" in inputs.upstream_flags
        assert "EXPECTED_INFLATION_CB_TARGET" not in inputs.upstream_flags
        assert "DK_BS_GDP_PROXY_ZERO" in inputs.upstream_flags
        assert inputs.source_connector == ("te",)
        assert inputs.r_star_pct == pytest.approx(0.0075)
        # 3.25 % policy, all positive → no negative-rate-era flag.
        assert "DK_NEGATIVE_RATE_ERA_DATA" not in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_te_primary_imported_target_value_matches_ecb(self) -> None:
        """Sprint Y-DK convention: imported target value is the ECB 2 %."""
        fred = _FakeFredConnector()
        te = _FakeTEDkSuccess(pct=3.25)
        inputs = await build_m1_dk_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        # Real-shadow: policy 3.25 % - target 2 % = 1.25 % real.
        for r in inputs.real_shadow_rate_history:
            assert r == pytest.approx(0.0125, abs=1e-6)

    @pytest.mark.asyncio
    async def test_te_primary_negative_rate_era_flag(self) -> None:
        """TE-primary discount-rate dip 2021-2022 surfaces DK_NEGATIVE_RATE_ERA_DATA.

        Pinning TE to -0.50 % across the lookback window mirrors the
        2021-09-30 deep discount-rate observation (min was -0.60 % per
        Sprint Y-DK probe). The cascade must propagate the sign into
        ``policy_rate_pct`` AND add the negative-era flag.
        """
        fred = _FakeFredConnector()
        te = _FakeTEDkSuccess(pct=-0.5)
        inputs = await build_m1_dk_inputs(
            fred,  # type: ignore[arg-type]
            date(2021, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=1,
        )
        assert inputs.policy_rate_pct == pytest.approx(-0.005)  # -0.50 %
        assert "DK_NEGATIVE_RATE_ERA_DATA" in inputs.upstream_flags
        assert "DK_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_nationalbanken_secondary_when_te_unavailable(self) -> None:
        """TE raises DataUnavailableError → Nationalbanken Statbank takes over."""
        fred = _FakeFredConnector()
        nationalbanken = _FakeNationalbankenSuccess(yield_bps=325)  # 3.25 %
        te = _FakeTEDkUnavailable()
        inputs = await build_m1_dk_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            nationalbanken=nationalbanken,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(0.0325)
        assert "DK_POLICY_RATE_NATIONALBANKEN_NATIVE" in inputs.upstream_flags
        # DK Statbank native is daily — no *_MONTHLY cadence flag
        # (matches the Sprint W-SE Riksbank pattern, contrast CH).
        assert "DK_POLICY_RATE_NATIONALBANKEN_NATIVE_MONTHLY" not in inputs.upstream_flags
        assert "DK_POLICY_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "DK_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert "CALIBRATION_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("nationalbanken",)

    @pytest.mark.asyncio
    async def test_nationalbanken_native_preserves_negative_cd_rate(self) -> None:
        """Negative CD-rate observations (-0.75 % corridor 2015-2022) flow through.

        This is the key Sprint Y-DK invariant for the secondary path
        — the Nationalbanken CD rate (OIBNAA) is the actual EUR-peg
        defence tool and went deeply negative 2015-04 → 2022-09.
        """
        fred = _FakeFredConnector()
        nationalbanken = _FakeNationalbankenSuccess(yield_bps=-75)  # -0.75 %
        te = _FakeTEDkUnavailable()
        inputs = await build_m1_dk_inputs(
            fred,  # type: ignore[arg-type]
            date(2017, 12, 31),
            te=te,  # type: ignore[arg-type]
            nationalbanken=nationalbanken,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(-0.0075)
        assert "DK_NEGATIVE_RATE_ERA_DATA" in inputs.upstream_flags
        assert "DK_POLICY_RATE_NATIONALBANKEN_NATIVE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_fred_last_resort_stale_flagged(self) -> None:
        """TE + Nationalbanken both fail → FRED emits staleness flags."""
        fred = _FakeFredConnector()
        nationalbanken = _FakeNationalbankenUnavailable()
        te = _FakeTEDkUnavailable()
        inputs = await build_m1_dk_inputs(
            fred,  # type: ignore[arg-type]
            date(2020, 12, 31),
            te=te,  # type: ignore[arg-type]
            nationalbanken=nationalbanken,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.policy_rate_pct == pytest.approx(-0.005)  # FRED -0.50 %
        assert "DK_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "DK_POLICY_RATE_TE_PRIMARY" not in inputs.upstream_flags
        assert "DK_POLICY_RATE_NATIONALBANKEN_NATIVE" not in inputs.upstream_flags
        # FRED fixture returns -0.50 %, so the negative-era flag still
        # fires — proves the flag attaches to the value, not the source.
        assert "DK_NEGATIVE_RATE_ERA_DATA" in inputs.upstream_flags
        assert inputs.source_connector == ("fred",)

    @pytest.mark.asyncio
    async def test_fred_only_when_te_and_nationalbanken_absent(self) -> None:
        """te=None + nationalbanken=None → FRED path still emits staleness flags."""
        fred = _FakeFredConnector()
        inputs = await build_m1_dk_inputs(
            fred,  # type: ignore[arg-type]
            date(2020, 12, 31),
            history_years=2,
        )
        assert inputs.country_code == "DK"
        assert inputs.source_connector == ("fred",)
        assert "DK_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags
        assert "CALIBRATION_STALE" in inputs.upstream_flags
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "DK_INFLATION_TARGET_IMPORTED_FROM_EA" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_all_sources_fail_raises(self) -> None:
        """TE unavailable + Nationalbanken unavailable + FRED empty → ValueError."""

        class _EmptyFred:
            async def fetch_series(
                self, series_id: str, start: date, end: date
            ) -> list[Observation]:
                _ = series_id, start, end
                return []

        with pytest.raises(ValueError, match="TE, Nationalbanken, and FRED"):
            await build_m1_dk_inputs(
                _EmptyFred(),  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=_FakeTEDkUnavailable(),  # type: ignore[arg-type]
                nationalbanken=_FakeNationalbankenUnavailable(),  # type: ignore[arg-type]
                history_years=1,
            )

    @pytest.mark.asyncio
    async def test_dk_flags_include_bs_gdp_proxy_zero(self) -> None:
        """DK BS/GDP ratio is placeholder — always emits DK_BS_GDP_PROXY_ZERO."""
        fred = _FakeFredConnector()
        te = _FakeTEDkSuccess(pct=3.25)
        inputs = await build_m1_dk_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.balance_sheet_pct_gdp_current == 0.0
        assert inputs.balance_sheet_pct_gdp_12m_ago == 0.0
        assert "DK_BS_GDP_PROXY_ZERO" in inputs.upstream_flags


# ---------------------------------------------------------------------------
# M2 DK (Sprint Y-DK — scaffold raises pending CPI/gap/inflation-forecast)
# ---------------------------------------------------------------------------


# M2 DK full compute lives in :class:`TestBuildM2SprintFFlipped`.


# ---------------------------------------------------------------------------
# M4 DK (Sprint Y-DK — scaffold raises until ≥5 custom-FCI components wired)
# ---------------------------------------------------------------------------


class TestBuildM4Dk:
    @pytest.mark.asyncio
    async def test_raises_insufficient_components(self) -> None:
        """M4 DK scaffold raises until ≥5 FCI components wire."""
        fred = _FakeFredConnector()
        te = _FakeTEDkSuccess(pct=3.25)
        nationalbanken = _FakeNationalbankenSuccess()
        with pytest.raises(InsufficientDataError, match="CAL-DK-M4-FCI"):
            await build_m4_dk_inputs(
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                nationalbanken=nationalbanken,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_raises_without_connectors(self) -> None:
        """Scaffold raises regardless of connector presence."""
        fred = _FakeFredConnector()
        with pytest.raises(InsufficientDataError):
            await build_m4_dk_inputs(
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
        # NZ + CH + NO + SE + DK all wired (Sprints U-NZ / V-CH / X-NO
        # / W-SE / Y-DK); CN remains Phase 2+ — probe with it.
        with pytest.raises(NotImplementedError, match="CN"):
            await builder.build_m1_inputs("CN", date(2024, 12, 31))

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
        # Sprint F flipped the per-country builder to full compute; the
        # raise surface now differs (CPI / output-gap / forecast missing)
        # from the Sprint-C pre-flip CAL-blocker message. Dispatch-test
        # intent preserved: builder must route to the right country
        # scaffold and surface InsufficientDataError if fake is incomplete.
        with pytest.raises(InsufficientDataError):
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
        # Sprint F flipped the per-country builder to full compute; the
        # raise surface now differs (CPI / output-gap / forecast missing)
        # from the Sprint-C pre-flip CAL-blocker message. Dispatch-test
        # intent preserved: builder must route to the right country
        # scaffold and surface InsufficientDataError if fake is incomplete.
        with pytest.raises(InsufficientDataError):
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
        # Sprint F flipped the per-country builder to full compute; the
        # raise surface now differs (CPI / output-gap / forecast missing)
        # from the Sprint-C pre-flip CAL-blocker message. Dispatch-test
        # intent preserved: builder must route to the right country
        # scaffold and surface InsufficientDataError if fake is incomplete.
        with pytest.raises(InsufficientDataError):
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
        # Sprint F flipped the per-country builder to full compute; the
        # raise surface now differs (CPI / output-gap / forecast missing)
        # from the Sprint-C pre-flip CAL-blocker message. Dispatch-test
        # intent preserved: builder must route to the right country
        # scaffold and surface InsufficientDataError if fake is incomplete.
        with pytest.raises(InsufficientDataError):
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
        # Sprint F flipped the per-country builder to full compute; the
        # raise surface now differs (CPI / output-gap / forecast missing)
        # from the Sprint-C pre-flip CAL-blocker message. Dispatch-test
        # intent preserved: builder must route to the right country
        # scaffold and surface InsufficientDataError if fake is incomplete.
        with pytest.raises(InsufficientDataError):
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
    async def test_build_m1_dk_via_facade_te_primary(self) -> None:
        """DK M1 dispatch — TE handle present → canonical TE-primary discount-rate path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEDkSuccess(pct=3.25),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("DK", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "DK"
        assert "DK_POLICY_RATE_TE_PRIMARY" in inputs.upstream_flags
        assert "DK_INFLATION_TARGET_IMPORTED_FROM_EA" in inputs.upstream_flags
        assert "EXPECTED_INFLATION_CB_TARGET" not in inputs.upstream_flags
        assert "DK_POLICY_RATE_FRED_FALLBACK_STALE" not in inputs.upstream_flags
        assert inputs.source_connector == ("te",)

    @pytest.mark.asyncio
    async def test_build_m1_dk_via_facade_nationalbanken_secondary(self) -> None:
        """DK M1 dispatch — TE absent, Nationalbanken handle present → CD-rate native path."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            nationalbanken=_FakeNationalbankenSuccess(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("DK", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "DK"
        assert "DK_POLICY_RATE_NATIONALBANKEN_NATIVE" in inputs.upstream_flags
        # Daily-cadence native — no *_MONTHLY flag (matches SE Riksbank).
        assert "DK_POLICY_RATE_NATIONALBANKEN_NATIVE_MONTHLY" not in inputs.upstream_flags
        assert "DK_INFLATION_TARGET_IMPORTED_FROM_EA" in inputs.upstream_flags
        assert inputs.source_connector == ("nationalbanken",)

    @pytest.mark.asyncio
    async def test_build_m1_dk_via_facade_fred_fallback(self) -> None:
        """DK M1 dispatch — FRED-only path (no TE/Nationalbanken handles) → stale flags."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m1_inputs("DK", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "DK"
        assert "R_STAR_PROXY" in inputs.upstream_flags
        assert "DK_INFLATION_TARGET_IMPORTED_FROM_EA" in inputs.upstream_flags
        assert "DK_POLICY_RATE_FRED_FALLBACK_STALE" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_m2_dk_dispatches_to_dk_builder(self) -> None:
        """DK M2 dispatch routes to the DK full-compute builder (Sprint F).

        The raise message surface changed from CAL-blocker phrasing
        (pre-Sprint-F) to CPI / output-gap diagnostics. Dispatch wiring
        invariant preserved.
        """
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEDkSuccess(pct=3.25),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError):
            await builder.build_m2_inputs("DK", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_m4_dk_dispatches_to_dk_builder(self) -> None:
        """DK M4 dispatch routes to the DK scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTEDkSuccess(pct=3.25),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError, match="CAL-DK-M4-FCI"):
            await builder.build_m4_inputs("DK", date(2024, 12, 31), history_years=2)

    @pytest.mark.asyncio
    async def test_m2_ca_dispatches_to_ca_builder(self) -> None:
        """CA M2 dispatch routes to the CA scaffold (raises InsufficientDataError)."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            te=_FakeTECaSuccess(pct=3.25),  # type: ignore[arg-type]
        )
        # Sprint F flipped the per-country builder to full compute; the
        # raise surface now differs (CPI / output-gap / forecast missing)
        # from the Sprint-C pre-flip CAL-blocker message. Dispatch-test
        # intent preserved: builder must route to the right country
        # scaffold and surface InsufficientDataError if fake is incomplete.
        with pytest.raises(InsufficientDataError):
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
        # Sprint F flipped the per-country builder to full compute; the
        # raise surface now differs (CPI / output-gap / forecast missing)
        # from the Sprint-C pre-flip CAL-blocker message. Dispatch-test
        # intent preserved: builder must route to the right country
        # scaffold and surface InsufficientDataError if fake is incomplete.
        with pytest.raises(InsufficientDataError):
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
    async def test_m2_ea_routes_to_aggregate_builder_post_sprint_l(self) -> None:
        """Sprint L flipped EA aggregate M2 to live compute.

        Pre-Sprint-L this test asserted NotImplementedError; the CAL item
        (CAL-M2-EA-AGGREGATE) is now closed so the dispatch must route
        to :func:`build_m2_ea_inputs`. Absent ancillary connectors
        (te / oecd_eo) the helper surfaces ``InsufficientDataError``
        from the CPI branch — not ``NotImplementedError``.
        """
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        with pytest.raises(InsufficientDataError):
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

    @pytest.mark.asyncio
    @pytest.mark.parametrize("country", ["DE", "FR", "IT", "ES", "NL", "PT"])
    async def test_m2_unsupported_ea_country_references_phase_2_backlog(self, country: str) -> None:
        """Sprint F + Sprint L: M2 per-country EA members are deferred to Phase 2+.

        Sprint F completed the non-EA T1 countries (US + 9 live).
        Sprint L (CAL-M2-EA-AGGREGATE) flipped EA aggregate to live
        compute — EA is therefore no longer in this parametrize set.
        Per-country EA members (DE / FR / IT / ES / NL / PT) remain out
        of scope pending a country-specific reaction-function spec; the
        raise message redirects operators to :cal:`CAL-M2-EA-PER-COUNTRY`.
        """
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        with pytest.raises(NotImplementedError) as excinfo:
            await builder.build_m2_inputs(country, date(2024, 12, 31))
        message = str(excinfo.value)
        assert "CAL-M2-EA-PER-COUNTRY" in message
        # EA aggregate is NO LONGER deferred post-Sprint-L — the
        # NotImplementedError message should not point operators at the
        # closed CAL item for the per-country members' gap.
        assert "CAL-M2-EA-AGGREGATE" not in message

    @pytest.mark.asyncio
    async def test_m2_ea_aggregate_now_implemented_post_sprint_l(self) -> None:
        """Sprint L: EA aggregate M2 dispatches (not raises) post-Sprint-L.

        Counter-test to the per-country members guard above — the EA
        aggregate dispatch must not raise ``NotImplementedError`` even
        when the ancillary connectors (te / oecd_eo) are absent; the
        raise instead surfaces ``InsufficientDataError`` from the
        Sprint F full-compute helper when a required input is missing.
        """
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            # te + oecd_eo deliberately None → expect InsufficientDataError
            # on the HICP branch, NOT NotImplementedError on dispatch.
        )
        with pytest.raises((InsufficientDataError, NotImplementedError)) as excinfo:
            await builder.build_m2_inputs("EA", date(2024, 12, 31))
        # Must not be NotImplementedError — EA is now a routed country.
        assert not isinstance(excinfo.value, NotImplementedError)


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


# ---------------------------------------------------------------------------
# Sprint C — OECD EO output-gap wiring per T1 country (Week 10)
# ---------------------------------------------------------------------------


@dataclass
class _FakeOECDEOSuccess:
    """Stub OECD EO connector that returns a single-observation gap."""

    gap_pct: float = -1.5
    ref_area: str = "FAKE"

    async def fetch_latest_output_gap(self, country_code: str, observation_date: date):  # type: ignore[no-untyped-def]
        from sonar.connectors.oecd_eo import OutputGapObservation  # noqa: PLC0415

        return OutputGapObservation(
            country_code=country_code,
            observation_date=date(observation_date.year, 12, 31),
            gap_pct=self.gap_pct,
            ref_area=self.ref_area,
        )


@dataclass
class _FakeOECDEOUnavailable:
    """Stub OECD EO connector that soft-fails (returns None)."""

    async def fetch_latest_output_gap(self, country_code: str, observation_date: date):  # type: ignore[no-untyped-def]
        return None


class TestSprintFUsBaselineGuard:
    """Sprint F HALT-2 regression guard: US M2 canonical compute invariant.

    All six prior commits flipped per-country M2 builders; the US builder
    was intentionally not touched (CBO GDPPOT quarterly is strictly
    better than OECD EO annual for US). This class re-asserts that the
    US signature, dispatch, and output contract are unchanged.
    """

    @pytest.mark.asyncio
    async def test_us_builder_signature_unchanged_no_regression(self) -> None:
        """US M2 builder signature stays CBO-primary — no oecd_eo kwarg.

        HALT-0 trigger: US canonical path must not drift to OECD EO
        annual (coarser than CBO quarterly). Verify by calling
        ``build_m2_us_inputs`` the same way Sprint-C-precedent tests do.
        """
        # build_m2_us_inputs expects fred + cbo positional — this is the
        # signature that existed pre-Sprint-C. If it broke, this test
        # would fail at parameter binding long before reaching the
        # fakes. We don't exercise a happy-path here — that's covered
        # in TestBuildM2Us — we just guard the kwargs surface.
        import inspect  # noqa: PLC0415

        from sonar.indices.monetary.builders import (  # noqa: PLC0415
            build_m2_us_inputs,
        )

        sig = inspect.signature(build_m2_us_inputs)
        # oecd_eo is intentionally NOT a parameter on US M2.
        assert "oecd_eo" not in sig.parameters
        # cbo still a required positional (US output-gap primary).
        assert sig.parameters["cbo"].kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD,)

    @pytest.mark.asyncio
    async def test_us_dispatches_through_facade_unchanged(self) -> None:
        """MonetaryInputsBuilder routes US M2 to the canonical CBO-primary path.

        Sprint F HALT-2 regression guard: the facade US branch must not
        accidentally route through any per-country builder. This test
        locks the facade behaviour: calling build_m2_inputs("US", ...)
        reaches :func:`build_m2_us_inputs` (which uses fred + cbo, no
        oecd_eo). ``_FakeCboConnector`` emits a synthetic output-gap
        obs + ``_FakeFredConnector`` emits the rest; a happy-path
        result proves the CBO path is in effect.
        """
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m2_inputs("US", date(2024, 1, 2), history_years=2)
        assert inputs.country_code == "US"
        assert inputs.output_gap_source == "CBO"
        # US canonical path uses ("fred", "cbo") source tuple — no te, no oecd_eo.
        assert inputs.source_connector == ("fred", "cbo")
        # US M2 r_star pulled from r_star_values.yaml (US canonical, not proxy).
        assert "R_STAR_PROXY" not in inputs.upstream_flags
        # US forecast uses UMich 5Y — flag pattern preserved.
        assert "INFLATION_FORECAST_PROXY_UMICH" in inputs.upstream_flags
        # No Sprint F country-specific flags should leak into US compute.
        for flag in inputs.upstream_flags:
            assert not flag.startswith("US_M2_CPI_TE_LIVE")
            assert not flag.startswith("US_M2_FULL_COMPUTE_LIVE")
            assert not flag.startswith("US_M2_OUTPUT_GAP_OECD_EO_LIVE")


# ---------------------------------------------------------------------------
# Sprint F — M2 full-compute parametric tests for the 9 flipped countries
# (CA / AU / NZ / CH / SE / NO / DK / GB / JP).
# ---------------------------------------------------------------------------


@dataclass
class _FakeTEInflationForecast:
    country: str
    historical_data_symbol: str
    latest_value_pct: float
    latest_value_date: date
    forecast_12m_pct: float
    forecast_12m_date: date
    forecast_year_end_pct: float
    indicator: str = "inflation rate"
    frequency: str = "Monthly"


class _FakeTESprintF:
    """Fake TEConnector providing Sprint F CPI + forecast + bank-rate methods.

    Instantiated once per country — registers the country-specific
    method names dynamically so each builder finds its expected wrappers
    (e.g. ``fetch_ca_cpi_yoy`` vs ``fetch_au_cpi_yoy``). Also satisfies
    the M1 cascade's bank-rate wrappers so the full-compute builders
    can run end-to-end without a separate policy-rate mock.
    """

    _POLICY_METHOD: ClassVar[dict[str, tuple[str, str]]] = {
        "CA": ("fetch_ca_bank_rate", "CCLR"),
        "AU": ("fetch_au_cash_rate", "RBATCTR"),
        "NZ": ("fetch_nz_ocr", "NZOCRS"),
        "CH": ("fetch_ch_policy_rate", "SZLTTR"),
        "NO": ("fetch_no_policy_rate", "NOBRDEP"),
        "SE": ("fetch_se_policy_rate", "SWRRATEI"),
        "DK": ("fetch_dk_policy_rate", "DEBRDISC"),
        "GB": ("fetch_gb_bank_rate", "UKBRBASE"),
        "JP": ("fetch_jp_bank_rate", "BOJDTR"),
    }
    _CPI_SYMBOL: ClassVar[dict[str, str]] = {
        "CA": "CACPIYOY",
        "AU": "AUCPIYOY",
        "NZ": "NZCPIYOY",
        "CH": "SZCPIYOY",
        "NO": "NOCPIYOY",
        "SE": "SWCPYOY",
        "DK": "DNCPIYOY",
        "GB": "UKRPCJYR",
        "JP": "JNCPIYOY",
    }

    def __init__(
        self,
        country_code: str,
        *,
        policy_pct: float = 3.0,
        cpi_pct: float = 2.5,
        forecast_12m_pct: float = 2.1,
        cpi_available: bool = True,
        forecast_available: bool = True,
        cpi_obs_count: int = 24,
    ) -> None:
        self.country = country_code
        self.policy_pct = policy_pct
        self.cpi_pct = cpi_pct
        self.forecast_12m_pct = forecast_12m_pct
        self.cpi_available = cpi_available
        self.forecast_available = forecast_available
        self.cpi_obs_count = cpi_obs_count
        policy_method, policy_symbol = self._POLICY_METHOD[country_code]
        cpi_symbol = self._CPI_SYMBOL[country_code]

        async def _policy(start: date, end: date) -> list[_FakeTEIndicatorObs]:
            out: list[_FakeTEIndicatorObs] = []
            d = start
            while d <= end:
                out.append(
                    _FakeTEIndicatorObs(
                        observation_date=d,
                        value=self.policy_pct,
                        historical_data_symbol=policy_symbol,
                    )
                )
                d = date.fromordinal(d.toordinal() + 1)
            return out

        async def _cpi(start: date, end: date) -> list[_FakeTEIndicatorObs]:
            if not self.cpi_available:
                msg = (
                    f"TE returned empty series: country={country_code!r} indicator='inflation rate'"
                )
                raise DataUnavailableError(msg)
            out: list[_FakeTEIndicatorObs] = []
            d = end
            count = 0
            while count < self.cpi_obs_count and d >= start:
                out.insert(
                    0,
                    _FakeTEIndicatorObs(
                        observation_date=d,
                        value=self.cpi_pct,
                        historical_data_symbol=cpi_symbol,
                    ),
                )
                d = date.fromordinal(d.toordinal() - 30)
                count += 1
            return out

        async def _forecast(observation_date: date) -> _FakeTEInflationForecast:
            if not self.forecast_available:
                msg = f"TE forecast empty: country={country_code!r} indicator='inflation rate'"
                raise DataUnavailableError(msg)
            return _FakeTEInflationForecast(
                country=country_code,
                historical_data_symbol=cpi_symbol,
                latest_value_pct=self.cpi_pct,
                latest_value_date=observation_date,
                forecast_12m_pct=self.forecast_12m_pct,
                forecast_12m_date=observation_date,
                forecast_year_end_pct=self.forecast_12m_pct,
            )

        setattr(self, policy_method, _policy)
        setattr(self, f"fetch_{country_code.lower()}_cpi_yoy", _cpi)
        setattr(self, f"fetch_{country_code.lower()}_inflation_forecast", _forecast)


_SPRINT_F_BUILDERS: dict[str, object] = {
    "CA": build_m2_ca_inputs,
    "AU": build_m2_au_inputs,
    "NZ": build_m2_nz_inputs,
    "CH": build_m2_ch_inputs,
    "NO": build_m2_no_inputs,
    "SE": build_m2_se_inputs,
    "DK": build_m2_dk_inputs,
    "GB": build_m2_gb_inputs,
    "JP": build_m2_jp_inputs,
}


_SPRINT_F_SECONDARY_KW: dict[str, str] = {
    "CA": "boc",
    "AU": "rba",
    "NZ": "rbnz",
    "CH": "snb",
    "NO": "norgesbank",
    "SE": "riksbank",
    "DK": "nationalbanken",
    "GB": "boe",
    "JP": "boj",
}


def _extra_kwargs_for(country: str) -> dict[str, object]:
    """Per-country kwarg aliases for the M1 cascade secondary slots."""
    kw = _SPRINT_F_SECONDARY_KW.get(country)
    return {kw: None} if kw else {}


class TestBuildM2SprintFFlipped:
    """Sprint F full-compute behaviour for CA / AU / NZ / CH / SE / NO / DK."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("country", list(_SPRINT_F_BUILDERS.keys()))
    async def test_full_compute_live_happy_path(self, country: str) -> None:
        """All four components present → builder returns with FULL_COMPUTE_LIVE."""
        fred = _FakeFredConnector()
        te = _FakeTESprintF(country, policy_pct=3.0, cpi_pct=2.5, forecast_12m_pct=2.1)
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5)
        builder = _SPRINT_F_BUILDERS[country]
        inputs = await builder(  # type: ignore[operator]
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            oecd_eo=oecd,  # type: ignore[arg-type]
            history_years=2,
            **_extra_kwargs_for(country),
        )
        assert inputs.country_code == country
        assert inputs.observation_date == date(2024, 12, 31)
        # Unit convention: inflation_yoy in decimal, target from YAML in decimal.
        assert inputs.inflation_yoy_pct == pytest.approx(0.025)
        assert inputs.inflation_forecast_2y_pct == pytest.approx(0.021)
        assert inputs.output_gap_pct == pytest.approx(-0.5)
        assert inputs.policy_rate_pct == pytest.approx(0.03)
        assert f"{country}_M2_CPI_TE_LIVE" in inputs.upstream_flags
        assert f"{country}_M2_INFLATION_FORECAST_TE_LIVE" in inputs.upstream_flags
        assert f"{country}_M2_OUTPUT_GAP_OECD_EO_LIVE" in inputs.upstream_flags
        assert f"{country}_M2_FULL_COMPUTE_LIVE" in inputs.upstream_flags
        assert "te" in inputs.source_connector
        assert "oecd_eo" in inputs.source_connector

    @pytest.mark.asyncio
    @pytest.mark.parametrize("country", list(_SPRINT_F_BUILDERS.keys()))
    async def test_cpi_missing_raises(self, country: str) -> None:
        """CPI unavailable → InsufficientDataError (cannot compute Taylor)."""
        fred = _FakeFredConnector()
        te = _FakeTESprintF(country, cpi_available=False)
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5)
        builder = _SPRINT_F_BUILDERS[country]
        with pytest.raises(InsufficientDataError, match="CPI YoY unavailable"):
            await builder(  # type: ignore[operator]
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                oecd_eo=oecd,  # type: ignore[arg-type]
                history_years=2,
                **_extra_kwargs_for(country),
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("country", list(_SPRINT_F_BUILDERS.keys()))
    async def test_output_gap_missing_raises(self, country: str) -> None:
        """OECD EO output-gap unavailable → InsufficientDataError."""
        fred = _FakeFredConnector()
        te = _FakeTESprintF(country)
        oecd = _FakeOECDEOUnavailable()
        builder = _SPRINT_F_BUILDERS[country]
        with pytest.raises(InsufficientDataError, match="output gap unavailable"):
            await builder(  # type: ignore[operator]
                fred,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                oecd_eo=oecd,  # type: ignore[arg-type]
                history_years=2,
                **_extra_kwargs_for(country),
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("country", list(_SPRINT_F_BUILDERS.keys()))
    async def test_forecast_missing_ships_partial_compute(self, country: str) -> None:
        """Forecast unavailable → PARTIAL_COMPUTE flag; Taylor-forward variant deferred."""
        fred = _FakeFredConnector()
        te = _FakeTESprintF(country, forecast_available=False)
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5)
        builder = _SPRINT_F_BUILDERS[country]
        inputs = await builder(  # type: ignore[operator]
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            oecd_eo=oecd,  # type: ignore[arg-type]
            history_years=2,
            **_extra_kwargs_for(country),
        )
        assert inputs.inflation_forecast_2y_pct is None
        assert f"{country}_M2_INFLATION_FORECAST_UNAVAILABLE" in inputs.upstream_flags
        assert f"{country}_M2_PARTIAL_COMPUTE" in inputs.upstream_flags
        assert f"{country}_M2_FULL_COMPUTE_LIVE" not in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_au_sparse_monthly_flag_when_cpi_obs_fewer_than_12(self) -> None:
        """AU-specific: <12 CPI observations → AU_M2_CPI_SPARSE_MONTHLY flag."""
        fred = _FakeFredConnector()
        te = _FakeTESprintF("AU", cpi_obs_count=5)
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5)
        inputs = await build_m2_au_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            oecd_eo=oecd,  # type: ignore[arg-type]
            history_years=2,
        )
        assert "AU_M2_CPI_SPARSE_MONTHLY" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_nz_emits_quarterly_flag(self) -> None:
        """NZ: always emits NZ_M2_CPI_QUARTERLY regardless of observation count."""
        fred = _FakeFredConnector()
        te = _FakeTESprintF("NZ")
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5)
        inputs = await build_m2_nz_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            oecd_eo=oecd,  # type: ignore[arg-type]
            history_years=2,
        )
        assert "NZ_M2_CPI_QUARTERLY" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_ch_emits_inflation_target_band_flag(self) -> None:
        """CH: always emits CH_INFLATION_TARGET_BAND (0-2 % band midpoint convention)."""
        fred = _FakeFredConnector()
        te = _FakeTESprintF("CH")
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5)
        inputs = await build_m2_ch_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            oecd_eo=oecd,  # type: ignore[arg-type]
            history_years=2,
        )
        assert "CH_INFLATION_TARGET_BAND" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_dk_emits_eur_peg_misfit_and_imported_target_flags(self) -> None:
        """DK: imported EUR-peg target + Taylor-misfit warning flag."""
        fred = _FakeFredConnector()
        te = _FakeTESprintF("DK")
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5)
        inputs = await build_m2_dk_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            oecd_eo=oecd,  # type: ignore[arg-type]
            history_years=2,
        )
        assert "DK_INFLATION_TARGET_IMPORTED_FROM_EA" in inputs.upstream_flags
        assert "DK_M2_EUR_PEG_TAYLOR_MISFIT" in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_se_emits_headline_not_cpif_flag(self) -> None:
        """SE: CPI headline not CPIF (Riksbank target is CPIF — flag surfaces the delta)."""
        fred = _FakeFredConnector()
        te = _FakeTESprintF("SE")
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5)
        inputs = await build_m2_se_inputs(
            fred,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            oecd_eo=oecd,  # type: ignore[arg-type]
            history_years=2,
        )
        assert "SE_M2_CPI_HEADLINE_NOT_CPIF" in inputs.upstream_flags


# ---------------------------------------------------------------------------
# Sprint L — M2 EA aggregate builder (CAL-M2-EA-AGGREGATE)
# ---------------------------------------------------------------------------


class _FakeTESprintL:
    """Fake TEConnector for the EA aggregate M2 builder.

    Registers ``fetch_ea_hicp_yoy`` + ``fetch_ea_inflation_forecast``
    on the instance so :func:`build_m2_ea_inputs` can dispatch through
    the Sprint L wrappers without touching the live TE API.
    """

    def __init__(
        self,
        *,
        hicp_pct: float = 2.4,
        forecast_12m_pct: float = 2.1,
        hicp_available: bool = True,
        forecast_available: bool = True,
        hicp_obs_count: int = 24,
    ) -> None:
        self.hicp_pct = hicp_pct
        self.forecast_12m_pct = forecast_12m_pct
        self.hicp_available = hicp_available
        self.forecast_available = forecast_available
        self.hicp_obs_count = hicp_obs_count

        async def _hicp(start: date, end: date) -> list[_FakeTEIndicatorObs]:
            if not self.hicp_available:
                msg = "TE returned empty series: country='EA' indicator='inflation rate'"
                raise DataUnavailableError(msg)
            out: list[_FakeTEIndicatorObs] = []
            d = end
            count = 0
            while count < self.hicp_obs_count and d >= start:
                out.insert(
                    0,
                    _FakeTEIndicatorObs(
                        observation_date=d,
                        value=self.hicp_pct,
                        historical_data_symbol="ECCPEMUY",
                    ),
                )
                d = date.fromordinal(d.toordinal() - 30)
                count += 1
            return out

        async def _forecast(observation_date: date) -> _FakeTEInflationForecast:
            if not self.forecast_available:
                msg = "TE forecast empty: country='EA' indicator='inflation rate'"
                raise DataUnavailableError(msg)
            return _FakeTEInflationForecast(
                country="EA",
                historical_data_symbol="ECCPEMUY",
                latest_value_pct=self.hicp_pct,
                latest_value_date=observation_date,
                forecast_12m_pct=self.forecast_12m_pct,
                forecast_12m_date=observation_date,
                forecast_year_end_pct=self.forecast_12m_pct,
            )

        self.fetch_ea_hicp_yoy = _hicp
        self.fetch_ea_inflation_forecast = _forecast


class TestBuildM2Ea:
    """Sprint L — EA aggregate M2 Taylor-gap builder (CAL-M2-EA-AGGREGATE)."""

    @pytest.mark.asyncio
    async def test_full_compute_live_happy_path(self) -> None:
        """All four components present → builder returns with FULL_COMPUTE_LIVE."""
        ecb = _FakeEcbConnector(dfr_pct=3.0)
        te = _FakeTESprintL(hicp_pct=2.4, forecast_12m_pct=2.1)
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5, ref_area="EA17")
        inputs = await build_m2_ea_inputs(
            ecb,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            oecd_eo=oecd,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.country_code == "EA"
        assert inputs.observation_date == date(2024, 12, 31)
        # Decimal unit conventions: TE pct-values → /100 at the builder
        # boundary; target + r* come from YAML in decimal already.
        assert inputs.policy_rate_pct == pytest.approx(0.03)
        assert inputs.inflation_yoy_pct == pytest.approx(0.024)
        assert inputs.inflation_forecast_2y_pct == pytest.approx(0.021)
        assert inputs.inflation_target_pct == pytest.approx(0.02)  # ECB 2 %
        assert inputs.r_star_pct == pytest.approx(-0.005)  # HLW EA Q4 2024
        assert inputs.output_gap_pct == pytest.approx(-0.5)
        assert inputs.output_gap_source == "OECD_EO"
        # Flag contract — mirror Sprint F uniform naming; EA-specific
        # DFR-source marker sits alongside the standard observability set.
        assert "EA_M2_POLICY_RATE_ECB_DFR_LIVE" in inputs.upstream_flags
        assert "EA_M2_CPI_TE_LIVE" in inputs.upstream_flags
        assert "EA_M2_INFLATION_FORECAST_TE_LIVE" in inputs.upstream_flags
        assert "EA_M2_OUTPUT_GAP_OECD_EO_LIVE" in inputs.upstream_flags
        assert "EA_M2_FULL_COMPUTE_LIVE" in inputs.upstream_flags
        # r* for EA is non-proxy — the HLW series is native, so no flag.
        assert "R_STAR_PROXY" not in inputs.upstream_flags
        # Source connectors — ECB DFR first, then te + oecd_eo via helper.
        assert inputs.source_connector[0] == "ecb_sdw"
        assert "te" in inputs.source_connector
        assert "oecd_eo" in inputs.source_connector

    @pytest.mark.asyncio
    async def test_hicp_missing_raises_insufficient_data(self) -> None:
        """HICP unavailable → InsufficientDataError (Taylor compute requires CPI)."""
        ecb = _FakeEcbConnector(dfr_pct=3.0)
        te = _FakeTESprintL(hicp_available=False)
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5, ref_area="EA17")
        with pytest.raises(InsufficientDataError, match="CPI YoY unavailable"):
            await build_m2_ea_inputs(
                ecb,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                oecd_eo=oecd,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_output_gap_missing_raises_insufficient_data(self) -> None:
        """OECD EO EA17 unavailable → InsufficientDataError."""
        ecb = _FakeEcbConnector(dfr_pct=3.0)
        te = _FakeTESprintL()
        oecd = _FakeOECDEOUnavailable()
        with pytest.raises(InsufficientDataError, match="output gap unavailable"):
            await build_m2_ea_inputs(
                ecb,  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                oecd_eo=oecd,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_forecast_missing_ships_partial_compute(self) -> None:
        """Forecast unavailable → PARTIAL_COMPUTE flag; Taylor-forward deferred."""
        ecb = _FakeEcbConnector(dfr_pct=3.0)
        te = _FakeTESprintL(forecast_available=False)
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5, ref_area="EA17")
        inputs = await build_m2_ea_inputs(
            ecb,  # type: ignore[arg-type]
            date(2024, 12, 31),
            te=te,  # type: ignore[arg-type]
            oecd_eo=oecd,  # type: ignore[arg-type]
            history_years=2,
        )
        assert inputs.inflation_forecast_2y_pct is None
        assert "EA_M2_INFLATION_FORECAST_UNAVAILABLE" in inputs.upstream_flags
        assert "EA_M2_PARTIAL_COMPUTE" in inputs.upstream_flags
        assert "EA_M2_FULL_COMPUTE_LIVE" not in inputs.upstream_flags

    @pytest.mark.asyncio
    async def test_dfr_missing_raises_insufficient_data(self) -> None:
        """Policy-rate source (ECB DFR) empty → InsufficientDataError."""

        class _FakeEcbEmpty:
            async def fetch_dfr_rate(self, start: date, end: date) -> list[_Obs]:
                _ = (start, end)  # unused stub
                return []

        te = _FakeTESprintL()
        oecd = _FakeOECDEOSuccess(gap_pct=-0.5, ref_area="EA17")
        with pytest.raises(InsufficientDataError, match="ECB DFR unavailable"):
            await build_m2_ea_inputs(
                _FakeEcbEmpty(),  # type: ignore[arg-type]
                date(2024, 12, 31),
                te=te,  # type: ignore[arg-type]
                oecd_eo=oecd,  # type: ignore[arg-type]
                history_years=2,
            )

    @pytest.mark.asyncio
    async def test_facade_dispatches_ea_m2_to_new_builder(self) -> None:
        """MonetaryInputsBuilder routes EA M2 to :func:`build_m2_ea_inputs`."""
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(dfr_pct=3.0),  # type: ignore[arg-type]
            te=_FakeTESprintL(),  # type: ignore[arg-type]
            oecd_eo=_FakeOECDEOSuccess(gap_pct=-0.5, ref_area="EA17"),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m2_inputs("EA", date(2024, 12, 31), history_years=2)
        assert inputs.country_code == "EA"
        assert "EA_M2_FULL_COMPUTE_LIVE" in inputs.upstream_flags
        assert inputs.output_gap_source == "OECD_EO"


class TestSprintLUsBaselineGuard:
    """Sprint L HALT-3 regression guard: US M2 canonical compute invariant.

    Sprint L added EA aggregate M2 on top of the Sprint F full-compute
    helper; the US builder was intentionally not touched (CBO GDPPOT
    quarterly remains strictly better than OECD EO annual for US). This
    class re-asserts that the US signature, dispatch, and output
    contract are unchanged post-Sprint-L.
    """

    @pytest.mark.asyncio
    async def test_us_builder_signature_unchanged_no_regression(self) -> None:
        """US M2 builder stays CBO-primary post-Sprint-L — no oecd_eo kwarg."""
        import inspect  # noqa: PLC0415

        from sonar.indices.monetary.builders import (  # noqa: PLC0415
            build_m2_us_inputs,
        )

        sig = inspect.signature(build_m2_us_inputs)
        assert "oecd_eo" not in sig.parameters
        assert sig.parameters["cbo"].kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD,)
        # Sprint L did not add EA-specific kwargs to the US builder.
        assert "ecb_sdw" not in sig.parameters
        assert "te" not in sig.parameters

    @pytest.mark.asyncio
    async def test_us_dispatches_through_facade_unchanged_post_sprint_l(self) -> None:
        """Facade US branch still routes through :func:`build_m2_us_inputs`.

        Sprint L HALT-3 regression guard — verifies no US path leakage
        through the EA branch added this sprint. Uses the same fakes as
        Sprint F's regression guard so any breakage surfaces as a diff
        against the exact-same inputs.
        """
        builder = MonetaryInputsBuilder(
            fred=_FakeFredConnector(),  # type: ignore[arg-type]
            cbo=_FakeCboConnector(),  # type: ignore[arg-type]
            ecb_sdw=_FakeEcbConnector(),  # type: ignore[arg-type]
            # Inject Sprint L fakes to ensure none leak into the US path.
            te=_FakeTESprintL(),  # type: ignore[arg-type]
            oecd_eo=_FakeOECDEOSuccess(gap_pct=-0.5, ref_area="USA"),  # type: ignore[arg-type]
        )
        inputs = await builder.build_m2_inputs("US", date(2024, 1, 2), history_years=2)
        assert inputs.country_code == "US"
        assert inputs.output_gap_source == "CBO"
        # US canonical path uses ("fred", "cbo") — no te, no oecd_eo, no ecb_sdw.
        assert inputs.source_connector == ("fred", "cbo")
        # r_star from YAML — not proxy for US.
        assert "R_STAR_PROXY" not in inputs.upstream_flags
        # Forecast proxy flag — Sprint L did not change US forecast source.
        assert "INFLATION_FORECAST_PROXY_UMICH" in inputs.upstream_flags
        # Sprint L flags (any) must not leak into US compute.
        for flag in inputs.upstream_flags:
            assert not flag.startswith("US_M2_")
            assert not flag.startswith("EA_M2_")
            assert not flag.startswith("POLICY_RATE_ECB_DFR")
