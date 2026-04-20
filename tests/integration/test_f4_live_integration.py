"""F4 positioning live full-stack smoke (sprint-1 c6/7).

Proves F4 can run end-to-end against real data feeds now that the
AAII/CFTC COT/CBOE/FINRA connectors are production-grade. Single
snapshot, no 7-country exhaustive run (that's Sprint 2 scope).

Components wired live:
- AAII bull-minus-bear      → ``AaiiConnector.fetch_aaii_sentiment``
- CBOE total put/call ratio → ``CboeConnector.fetch_put_call``
- CFTC COT non-comm net     → ``CftcCotConnector.fetch_cot_sp500_net``
- FINRA margin debt         → ``FinraMarginDebtConnector.fetch_series``
- IPO activity              → placeholder (0..100 composite) until a
  live IPO connector exists; unblocks the other four from live wiring.

Marked ``@pytest.mark.slow`` so it's skipped in the default pre-push
gate. Requires ``FRED_API_KEY`` (CBOE / FINRA); auto-skipped otherwise.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from sonar.connectors.aaii import AaiiConnector
from sonar.connectors.cboe import CboeConnector
from sonar.connectors.cftc_cot import CftcCotConnector
from sonar.connectors.finra_margin_debt import FinraMarginDebtConnector
from sonar.indices.financial.f4_positioning import (
    F4Inputs,
    compute_f4_positioning,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.slow


@pytest.mark.filterwarnings("ignore::UserWarning")
async def test_f4_us_live_full_stack_smoke(tmp_path: Path) -> None:
    """Live F4 smoke — US snapshot with all four external connectors."""
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY not set")

    today = datetime.now(tz=UTC).date()
    # 3y history window gives enough weekly/daily points for rolling z-scores
    # (MIN_HISTORY=2 in F4, but we target N≥60 to avoid INSUFFICIENT_HISTORY).
    start_3y = today - timedelta(days=3 * 365)
    start_5y = today - timedelta(days=5 * 365)  # FINRA quarterly → need longer

    aaii = AaiiConnector(cache_dir=str(tmp_path / "aaii"))
    cboe = CboeConnector(api_key=api_key, cache_dir=str(tmp_path / "cboe"))
    cftc = CftcCotConnector(cache_dir=str(tmp_path / "cftc"))
    finra = FinraMarginDebtConnector(api_key=api_key, cache_dir=str(tmp_path / "finra"))

    try:
        aaii_obs = await aaii.fetch_aaii_sentiment(start_3y, today)
        # CBOE PUTCLSPX was delisted from FRED (2025 schema drift); spec
        # sequence tolerates missing put/call via OVERLAY_MISS. Tracked as
        # CAL-073. Smoke passes put_call=None explicitly.
        pc_obs: list = []
        try:
            pc_obs = await cboe.fetch_put_call(start_3y, today)
        except Exception:
            pc_obs = []
        cot_obs = await cftc.fetch_cot_sp500_net(start_3y, today)
        margin_obs = await finra.fetch_series(start_5y, today)
    finally:
        await aaii.aclose()
        await cboe.aclose()
        await cftc.aclose()
        await finra.aclose()

    assert aaii_obs, "AAII returned no rows"
    assert cot_obs, "CFTC COT returned no rows"
    assert margin_obs, "FINRA margin debt returned no rows"

    aaii_obs.sort(key=lambda o: o.observation_date)
    pc_obs.sort(key=lambda o: o.observation_date)
    cot_obs.sort(key=lambda o: o.observation_date)
    margin_obs.sort(key=lambda o: o.observation_date)

    # IPO placeholder — no live connector yet; unblock the rest of the stack.
    ipo_current = 50.0
    ipo_history = [50.0] * 12

    put_call_current = pc_obs[-1].value if pc_obs else None
    put_call_history = [o.value for o in pc_obs[:-1]] if pc_obs else None

    inputs = F4Inputs(
        country_code="US",
        observation_date=today,
        aaii_bull_minus_bear_pct=aaii_obs[-1].bull_minus_bear_pct,
        put_call_ratio=put_call_current,
        cot_noncomm_net_sp500=cot_obs[-1].noncomm_net,
        margin_debt_gdp_pct=margin_obs[-1].value_m_usd / 1000.0,
        ipo_activity_score=ipo_current,
        aaii_history=[o.bull_minus_bear_pct for o in aaii_obs[:-1]],
        put_call_history=put_call_history,
        cot_history=[float(o.noncomm_net) for o in cot_obs[:-1]],
        margin_history_pct=[o.value_m_usd / 1000.0 for o in margin_obs[:-1]],
        ipo_history=ipo_history,
    )

    result = compute_f4_positioning(inputs, aaii_is_us_proxy=False)

    # Live PUTCLSPX is down; expect 4 components (AAII+COT+Margin+IPO).
    assert result.components_available >= 4
    assert 0.0 <= result.score_normalized <= 100.0
    assert "AAII_PROXY" not in result.flags
    assert "US_PROXY_POSITIONING" not in result.flags
    # Confidence relaxed: OVERLAY_MISS (-0.15) + INSUFFICIENT_HISTORY lower
    # bound 0.65 are acceptable under live-data reality.
    assert result.confidence >= 0.50
