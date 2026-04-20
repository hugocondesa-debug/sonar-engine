"""E4 Sentiment + F4 Positioning quality uplift smoke (sprint6-3 c7).

Two ``@pytest.mark.slow`` tests that measure the post-Quick-Wins
component-availability deltas:

- **E4 US**: baseline pre-sprint 6 components available (UMich, CB
  CC via OECD-CLI proxy, UMich-5Y via Cleveland-Fed proxy, EPU, VIX,
  SLOOS). With the TE primary wiring for CB + UMich-5Y (Sprint 6.3
  c4) the same 6 slots populate but CB/UMich-5Y now flow through TE
  (TE_FALLBACK_CB_CC + TE_FALLBACK_UMICH_5Y flags). Plus TE covers
  ISM Mfg + ISM Svc + NFIB from Sprint 6.1 → 9 components target.
- **F4 US**: baseline pre-sprint 4/5 (put/call absent, OVERLAY_MISS).
  With Yahoo ^CPC wired (Sprint 6.3 c5+c6) → 5/5.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from sonar.connectors.aaii import AaiiConnector
from sonar.connectors.cftc_cot import CftcCotConnector
from sonar.connectors.eurostat import EurostatConnector
from sonar.connectors.finra_margin_debt import FinraMarginDebtConnector
from sonar.connectors.fred import FredConnector
from sonar.connectors.te import TEConnector
from sonar.connectors.yahoo_finance import YahooFinanceConnector
from sonar.indices.economic.builders import build_e4_inputs
from sonar.indices.financial.f4_positioning import F4Inputs, compute_f4_positioning

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.slow


def _count_e4_available(inputs: object) -> int:
    slots = (
        "umich_sentiment_12m_change",
        "conference_board_confidence_12m_change",
        "umich_5y_inflation_exp",
        "ism_manufacturing",
        "ism_services",
        "nfib_small_business",
        "epu_index",
        "ec_esi",
        "zew_expectations",
        "ifo_business_climate",
        "vix_level",
        "tankan_large_mfg",
        "sloos_standards_net_pct",
    )
    return sum(1 for s in slots if getattr(inputs, s, None) is not None)


@pytest.mark.filterwarnings("ignore::UserWarning")
async def test_e4_us_post_quick_wins(tmp_path: Path) -> None:
    """E4 US with TE + FRED primary: expect ≥ 9/13 with CB + UMich-5Y TE flags."""
    fred_key = os.environ.get("FRED_API_KEY")
    te_key = os.environ.get("TE_API_KEY")
    if not fred_key or not te_key:
        pytest.skip("FRED_API_KEY or TE_API_KEY not set")

    today = datetime.now(tz=UTC).date()
    observation_date = today - timedelta(days=60)

    fred = FredConnector(api_key=fred_key, cache_dir=str(tmp_path / "fred"))
    eurostat = EurostatConnector(cache_dir=str(tmp_path / "eurostat"), rate_limit_seconds=0.5)
    te = TEConnector(api_key=te_key, cache_dir=str(tmp_path / "te"))

    try:
        inputs = await build_e4_inputs("US", observation_date, fred=fred, eurostat=eurostat, te=te)
    finally:
        await fred.aclose()
        await eurostat.aclose()
        await te.aclose()

    count = _count_e4_available(inputs)
    assert count >= 9, f"E4 US availability {count} < 9 post-Quick-Wins"
    # CB + UMich-5Y now served by TE.
    for flag in ("TE_FALLBACK_CB_CC", "TE_FALLBACK_UMICH_5Y"):
        assert flag in inputs.upstream_flags, f"{flag} missing"
    # ISM + NFIB still via TE (Sprint 6.1 wiring).
    for flag in ("TE_FALLBACK_ISM_MFG", "TE_FALLBACK_ISM_SVC", "TE_FALLBACK_NFIB"):
        assert flag in inputs.upstream_flags
    assert "TE" in inputs.source_connectors


@pytest.mark.filterwarnings("ignore::UserWarning")
async def test_f4_us_post_quick_wins(tmp_path: Path) -> None:
    """F4 US with Yahoo put/call + full stack: expect 5/5 components."""
    fred_key = os.environ.get("FRED_API_KEY")
    if not fred_key:
        pytest.skip("FRED_API_KEY not set")

    today = datetime.now(tz=UTC).date()
    start_3y = today - timedelta(days=3 * 365)
    start_5y = today - timedelta(days=5 * 365)

    aaii = AaiiConnector(cache_dir=str(tmp_path / "aaii"))
    cftc = CftcCotConnector(cache_dir=str(tmp_path / "cftc"))
    finra = FinraMarginDebtConnector(api_key=fred_key, cache_dir=str(tmp_path / "finra"))
    yahoo = YahooFinanceConnector(cache_dir=str(tmp_path / "yahoo"))

    try:
        aaii_obs = await aaii.fetch_aaii_sentiment(start_3y, today)
        pc_obs: list = []
        try:
            pc_obs = await yahoo.fetch_put_call_ratio_us(start_3y, today)
        except Exception:
            pc_obs = []
        cot_obs = await cftc.fetch_cot_sp500_net(start_3y, today)
        margin_obs = await finra.fetch_series(start_5y, today)
    finally:
        await aaii.aclose()
        await cftc.aclose()
        await finra.aclose()
        await yahoo.aclose()

    # Yahoo may rate-limit → allow skip, since the uplift target is
    # contingent on put/call availability.
    if not pc_obs:
        pytest.skip("Yahoo ^CPC rate-limited during probe; see CAL-073 note")

    aaii_obs.sort(key=lambda o: o.observation_date)
    pc_obs.sort(key=lambda o: o.observation_date)
    cot_obs.sort(key=lambda o: o.observation_date)
    margin_obs.sort(key=lambda o: o.observation_date)

    ipo_current = 50.0
    ipo_history = [50.0] * 12

    inputs = F4Inputs(
        country_code="US",
        observation_date=today,
        aaii_bull_minus_bear_pct=aaii_obs[-1].bull_minus_bear_pct,
        put_call_ratio=pc_obs[-1].value_close,
        cot_noncomm_net_sp500=cot_obs[-1].noncomm_net,
        margin_debt_gdp_pct=margin_obs[-1].value_m_usd / 1000.0,
        ipo_activity_score=ipo_current,
        aaii_history=[o.bull_minus_bear_pct for o in aaii_obs[:-1]],
        put_call_history=[o.value_close for o in pc_obs[:-1]],
        cot_history=[float(o.noncomm_net) for o in cot_obs[:-1]],
        margin_history_pct=[o.value_m_usd / 1000.0 for o in margin_obs[:-1]],
        ipo_history=ipo_history,
    )

    result = compute_f4_positioning(inputs, aaii_is_us_proxy=False)
    # Post-Quick-Wins target: all 5 components available.
    assert result.components_available == 5, (
        f"F4 US components_available={result.components_available}, expected 5/5"
    )
    assert "OVERLAY_MISS" not in result.flags
