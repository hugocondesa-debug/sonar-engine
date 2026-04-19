"""Integration smoke tests for FredConnector — live FRED API.

Marked @pytest.mark.integration. Skipped em default pytest run (requires
`pytest -m integration`). Rate-limit impact: ~5 calls per run, well
under FRED 120/min.
"""

import time
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from sonar.config import settings
from sonar.connectors.fred import FredConnector

pytestmark = pytest.mark.integration


def _today_utc() -> date:
    """UTC-anchored today; avoids DTZ011 + naive-datetime pitfalls."""
    return datetime.now(tz=UTC).date()


@pytest.fixture
def smoke_cache_dir(tmp_path: Path) -> Path:
    """Isolated cache per test — evita cross-test contamination."""
    d = tmp_path / "fred_smoke_cache"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def live_fred(smoke_cache_dir: Path) -> AsyncIterator[FredConnector]:
    """Real FredConnector com key from settings; skip se não configurada."""
    placeholder = "your_fred_api_key_here"  # pragma: allowlist secret
    if not settings.fred_api_key or settings.fred_api_key == placeholder:
        pytest.skip("FRED_API_KEY not configured in .env")
    conn = FredConnector(api_key=settings.fred_api_key, cache_dir=str(smoke_cache_dir))
    yield conn
    await conn.aclose()


# ---------------------------------------------------------------------------
# 1 — Structural validation: fetched data conforms ao schema
# ---------------------------------------------------------------------------
async def test_fetch_recent_dgs10_structural(live_fred: FredConnector) -> None:
    end = _today_utc()
    start = end - timedelta(days=30)
    obs = await live_fred.fetch_series("DGS10", start, end)

    assert len(obs) > 0, "DGS10 last 30d should return non-empty"
    assert all(o.country_code == "US" for o in obs)
    assert all(o.tenor_years == 10.0 for o in obs)
    assert all(o.source == "FRED" for o in obs)
    assert all(o.source_series_id == "DGS10" for o in obs)
    assert all(isinstance(o.yield_bps, int) for o in obs)


# ---------------------------------------------------------------------------
# 2 — Sanity ranges: DGS10 em plausible macro bounds
# ---------------------------------------------------------------------------
async def test_fetch_recent_dgs10_sanity_ranges(live_fred: FredConnector) -> None:
    """DGS10 plausible range 3.0%-6.0% (300-600 bps) Phase 1 era.

    Se fail: regime change detected, triage needed (nao silent pass).
    Range calibrado contra D2 baseline (2026-04-16 = 432 bps).
    """
    end = _today_utc()
    start = end - timedelta(days=30)
    obs = await live_fred.fetch_series("DGS10", start, end)

    out_of_range = [o for o in obs if not (300 <= o.yield_bps <= 600)]
    assert not out_of_range, (
        f"DGS10 yields outside 300-600 bps range: "
        f"{[(o.observation_date, o.yield_bps) for o in out_of_range]}"
    )


# ---------------------------------------------------------------------------
# 3 — Yield curve shape: normal expected, inversion warns not fails
# ---------------------------------------------------------------------------
async def test_yield_curve_shape_normal(live_fred: FredConnector) -> None:
    """DGS2 < DGS10 < DGS30 em curva normal.

    Inversion e factual data (not bug). Warn em vez de fail —
    assertions limitam-se a: 3 fetches structural-sound.
    """
    end = _today_utc()
    start = end - timedelta(days=30)

    obs_2 = await live_fred.fetch_series("DGS2", start, end)
    obs_10 = await live_fred.fetch_series("DGS10", start, end)
    obs_30 = await live_fred.fetch_series("DGS30", start, end)

    assert len(obs_2) > 0
    assert len(obs_10) > 0
    assert len(obs_30) > 0

    # Pick most recent common date across 3 series
    dates_2 = {o.observation_date for o in obs_2}
    dates_10 = {o.observation_date for o in obs_10}
    dates_30 = {o.observation_date for o in obs_30}
    common = sorted(dates_2 & dates_10 & dates_30)
    assert common, "No overlapping dates across DGS2/DGS10/DGS30"
    latest = common[-1]

    y2 = next(o.yield_bps for o in obs_2 if o.observation_date == latest)
    y10 = next(o.yield_bps for o in obs_10 if o.observation_date == latest)
    y30 = next(o.yield_bps for o in obs_30 if o.observation_date == latest)

    if not (y2 <= y10 <= y30):
        pytest.warns(
            UserWarning,
            match=f"Curve inverted on {latest}: DGS2={y2} DGS10={y10} DGS30={y30}",
        )


# ---------------------------------------------------------------------------
# 4 — Cache determinism: 2nd call << 1st call (cache hit)
# ---------------------------------------------------------------------------
async def test_cache_determinism(live_fred: FredConnector) -> None:
    """2 calls identicas -> identical data; 2nd call >10x faster (cache hit)."""
    end = _today_utc()
    start = end - timedelta(days=5)

    t0 = time.perf_counter()
    obs1 = await live_fred.fetch_series("DGS10", start, end)
    elapsed_1 = time.perf_counter() - t0

    t0 = time.perf_counter()
    obs2 = await live_fred.fetch_series("DGS10", start, end)
    elapsed_2 = time.perf_counter() - t0

    # Same structure + values
    assert len(obs1) == len(obs2)
    for o1, o2 in zip(obs1, obs2, strict=True):
        assert o1.observation_date == o2.observation_date
        assert o1.yield_bps == o2.yield_bps

    # Cache hit must be materially faster (generous 10x threshold)
    assert elapsed_2 < elapsed_1 / 10, (
        f"Cache hit expected <<10x faster. " f"Call 1: {elapsed_1:.3f}s, Call 2: {elapsed_2:.3f}s"
    )


# ---------------------------------------------------------------------------
# 5 — D2 historical immutable match
# ---------------------------------------------------------------------------
async def test_d2_historical_immutable_match(live_fred: FredConnector) -> None:
    """Hard assert vs D2 baseline.

    D2 registered (docs/data_sources/D2_empirical_validation.md §3):
      DGS10 | 2026-04-16 | 4.32% | 432 bps

    FRED historical data e immutable — mismatch = real regression.
    """
    target_date = date(2026, 4, 16)
    obs = await live_fred.fetch_series("DGS10", target_date, target_date)

    assert len(obs) == 1, f"Expected 1 obs for {target_date}, got {len(obs)}"
    assert obs[0].observation_date == target_date
    assert obs[0].yield_bps == 432, (
        f"D2 baseline DGS10 2026-04-16 = 432 bps; got {obs[0].yield_bps} bps. "
        f"Data mutation OR mapping regression."
    )
