# Week 9 Sprint W-SE — Sweden Riksbank Connector + M1 SE (TE-primary Cascade)

**Target**: Ship Sveriges Riksbank connector + SE country enablement for M1 monetary. M2 T1 progression from 13 to 14 countries. TE-primary cascade per Sprint L/S-CA/T-AU/U-NZ/V-CH canonical pattern. Includes negative-rate era support (2015-2020, pattern per Sprint V-CH CH).
**Priority**: HIGH (M2 T1 Completionist progression — 5 of 7 remaining T1 countries at Week 9 start)
**Budget**: 3-4h CC autonomous
**Commits**: ~6-8
**Base**: branch `sprint-w-se-connector` (isolated worktree `/home/macro/projects/sonar-wt-sprint-w`)
**Concurrency**: Parallel to Sprint X-NO Norway Norges Bank connector in worktree `sonar-wt-sprint-x`. See §3.

---

## 1. Scope

In:
- `src/sonar/connectors/riksbank.py` — new Sveriges Riksbank connector
- **Cascade strategy per Sprint L/S-CA/T-AU/U-NZ/V-CH canonical pattern (TE-primary default)**:
  1. **Primary: TE native SE Policy Rate / Swedish Government bond yields** (daily, Riksbank-sourced via TE)
  2. **Secondary: Riksbank data portal** (public API — https://www.riksbank.se/sv/statistik/sok-rantor--valutakurser/)
  3. **Tertiary: FRED OECD mirror** (monthly-lagged; last-resort with `CALIBRATION_STALE` flag)
- TE wrapper `fetch_se_policy_rate` with HistoricalDataSymbol source-drift guard
- Core series empirical discovery:
  - SE Policy Rate (Reporäntan until 2019; Riksbank Policy Rate unified thereafter): probe Commit 1
  - SE 10Y Government Bond yield: TE `GSGB10YR:IND` or similar (verify existing mapping)
  - SE CPI + unemployment: TE generic `fetch_indicator(country="SE", ...)` pattern
- Empirical Riksbank data portal probe (time-boxed 20 min)
  - Swedish Swea API: `https://api.riksbank.se/swea/v1/` — REST JSON
  - Fallback: CSV download paths
- SE country entry in `docs/data_sources/country_tiers.yaml` (verify Tier 1 per ADR-0005)
- r* SE entry in `src/sonar/config/r_star_values.yaml` (~0.5-1.0% per Riksbank staff research)
- SE inflation target in `src/sonar/config/bc_targets.yaml` (0.02 per Riksbank 2% explicit target since 1993)
- M1 SE builder via TE-primary cascade (M2/M4 scaffolds only; full wiring deferred CAL-SE-*)
- Pipeline integration `daily_monetary_indices.py --country SE`
- Cassette + `@pytest.mark.slow` live canary for TE + Riksbank paths
- **Negative-rate era validation** (SE had -0.50% trough 2015-2019; Sprint V-CH CH pattern applies)
- Retrospective

Out:
- M2 SE live (output gap requires SCB / OECD EO — CAL-SE-M2-OUTPUT-GAP)
- M3 SE (requires persisted NSS forwards + expected-inflation for SE — CAL-SE-M3)
- M4 SE (FCI — requires VIX-SE, credit spreads SE, SEK NEER — CAL-SE-M4-FCI)
- SE ERP per-country live (deferred Phase 2+)
- SE CRP (BENCHMARK via spec; sovereign yield spread automatic)
- L3 credit indices SE (BIS coverage via Sprint AA fix)
- Krippner shadow-rate connector (Phase 2+ — same deferral as CH)

---

## 2. Spec reference

Authoritative:
- `docs/data_sources/country_tiers.yaml` — SE should be Tier 1 per ADR-0005
- `docs/specs/indices/monetary/M1-effective-rates.md` §2
- `docs/specs/indices/monetary/M2-taylor-gaps.md` §2
- `docs/specs/conventions/patterns.md` — Pattern 4
- `docs/planning/retrospectives/week9-sprint-v-ch-connector-report.md` — **Sprint V-CH negative-rate era pattern (most recent + most relevant)**
- `docs/planning/retrospectives/week9-sprint-u-nz-connector-report.md` — Sprint U-NZ perimeter-block scaffold pattern
- `docs/planning/retrospectives/week9-sprint-t-au-connector-report.md` — Sprint T-AU RBA CSV pattern
- `docs/planning/retrospectives/week9-sprint-s-ca-connector-report.md` — Sprint S-CA BoC Valet JSON REST
- `src/sonar/connectors/snb.py` — Sprint V-CH data-portal template (most relevant)
- `src/sonar/connectors/boc.py` — Sprint S-CA JSON REST connector alt template
- `src/sonar/connectors/rba.py` — Sprint T-AU CSV connector alt template
- `src/sonar/connectors/te.py` — existing SE country mappings

**Pre-flight requirement**: Commit 1 CC:
1. Verify TE SE mappings: `"SE": "sweden"` (indicator) + SE bond mapping likely exists from Sprint 1
2. Probe TE SE Policy Rate empirically:
   ```bash
   set -a && source .env && set +a
   curl -s "https://api.tradingeconomics.com/historical/country/sweden/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'
   ```
3. Document TE HistoricalDataSymbol for SE Policy Rate (probe finding)
4. Time-boxed 20 min Riksbank data portal probe:
   - Swea API: `curl -s "https://api.riksbank.se/swea/v1/Observations/SECBREPOEFF" | head -50`
     (pattern guess: SECBREPOEFF = SEK Central Bank Repo Rate Effective)
   - Alternative series IDs: `SECBPOLICYRATE`, `SEKPOLICYRATE`
   - Documentation: `https://www.riksbank.se/en-gb/statistics/interest-rates-and-exchange-rates/search-interest--exchange-rates/`
   - Apply UA-gate lesson per Sprint T-AU: use `User-Agent: SONAR/2.0 (monetary-cascade; ...)` header
5. If Riksbank probe SUCCEEDS → implement Riksbank connector as secondary in cascade
6. If Riksbank probe FAILS → scaffold raising DataUnavailableError (gated; document for CAL-SE-RIKSBANK-PORTAL)
7. Read `snb.py` as template first (Sprint V-CH negative-rate era handling + cube API pattern most relevant)
8. Verify SE in `country_tiers.yaml`; if missing, add as Tier 1

Document findings in Commit 1 body. **Note negative-rate historical context**: SE Policy Rate went to -0.50% from Feb 2015 to Dec 2019. Ensure parser handles negative values correctly.

Existing assets:
- `TEConnector` generic + 10 country wrappers (US/DE/PT/IT/ES/FR/NL Sprint 1 + GB Sprint I-patch + JP Sprint L + CA Sprint S-CA + AU Sprint T-AU + NZ Sprint U-NZ + CH Sprint V-CH)
- FRED connector has `fetch_series` for any series ID
- `country_tiers.yaml` canonical (ISO alpha-2)
- `bc_targets.yaml` + `r_star_values.yaml` extended CH Sprint V-CH pattern (including band-midpoint convention)

---

## 3. Concurrency — parallel protocol with Sprint X-NO + ISOLATED WORKTREES

**Sprint W-SE operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-w`

Sprint X-NO operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-x`

**Critical workflow**:
1. Sprint W-SE CC starts by `cd /home/macro/projects/sonar-wt-sprint-w`
2. All file operations happen in this worktree
3. Branch name: `sprint-w-se-connector`
4. Pushes to `origin/sprint-w-se-connector`
5. Final merge to main via fast-forward post-sprint-close (rebase likely if X-NO merges first)

**File scope Sprint W-SE**:
- `src/sonar/connectors/riksbank.py` NEW
- `src/sonar/connectors/te.py` APPEND (new `fetch_se_policy_rate` wrapper + SE-specific constants)
- `src/sonar/indices/monetary/builders.py` APPEND (add SE builders — `build_m1_se_inputs`)
- `src/sonar/connectors/fred.py` MODIFY (add SE FRED OECD series constants)
- `docs/data_sources/country_tiers.yaml` — verify/add SE entry (likely exists)
- `src/sonar/config/r_star_values.yaml` — add SE entry
- `src/sonar/config/bc_targets.yaml` — verify/add SE entry
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (add SE to MONETARY_SUPPORTED_COUNTRIES + SE country dispatch)
- Tests:
  - `tests/unit/test_connectors/test_riksbank.py` NEW
  - `tests/unit/test_connectors/test_te_indicator.py` APPEND (SE Policy Rate wrapper tests)
  - `tests/unit/test_indices/monetary/test_builders.py` APPEND (SE builder tests)
  - `tests/unit/test_indices/monetary/test_config_loaders.py` APPEND (SE entries)
  - `tests/unit/test_pipelines/test_daily_monetary_indices.py` APPEND (SE country)
  - `tests/integration/test_daily_monetary_se.py` NEW
  - `tests/fixtures/cassettes/riksbank/` + `tests/cassettes/connectors/te_se_policy_rate_*.json`
- `docs/backlog/calibration-tasks.md` MODIFY (CAL-SE-* entries)
- `docs/planning/retrospectives/week9-sprint-w-se-connector-report.md` NEW

**Sprint X-NO scope** (for awareness, DO NOT TOUCH):
- `src/sonar/connectors/norgesbank.py` NEW
- `src/sonar/connectors/te.py` APPEND (NO wrapper — **concurrent append zone**)
- `src/sonar/indices/monetary/builders.py` APPEND (NO builders — **concurrent append zone**)
- `src/sonar/connectors/fred.py` MODIFY (NO FRED series — **concurrent append zone**)
- `src/sonar/config/*.yaml` (NO entries — **concurrent modify zone**)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (NO dispatch — **concurrent modify zone**)

**Potential conflict zones** (same pattern as Day 3 U-NZ / V-CH):
- `te.py` — both sprints append wrappers (different functions, merge clean)
- `fred.py` — both append series constants (different constants, merge clean)
- `builders.py` — both append builders (different functions, merge clean)
- `daily_monetary_indices.py` — both add to MONETARY_SUPPORTED_COUNTRIES tuple (likely conflict, union-merge)
- `r_star_values.yaml` + `bc_targets.yaml` — both add country entries (merge clean if different keys)
- `calibration-tasks.md` — CAL entries (union-merge precedent)

**Rebase expected post-merge**. Sprint W-SE merges first (alphabetical branch priority) → X-NO rebases.

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-sprint-w && git pull origin main --rebase`

**Push race**: normal `git push origin sprint-w-se-connector`. Minor conflicts resolved via rebase.

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-w-se-connector
git push origin main
```

---

## 4. Commits

### Commit 1 — Pre-flight + TE SE Policy Rate wrapper

```
feat(connectors): TE fetch_se_policy_rate wrapper + source-drift guard

Pre-flight: probe TE SE Policy Rate + verify Riksbank data portal reachability.

Expected probe (document findings commit body):
  set -a && source .env && set +a
  curl -s "https://api.tradingeconomics.com/historical/country/sweden/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'

Document in commit body:
- Actual HistoricalDataSymbol returned (likely SEREPO, SEKIR, or policy-rate type)
- Response format (date + value)
- Historical range (expected: daily since Reporäntan inception 1994)
- **Negative values expected 2015-02..2019-12** (Riksbank negative-rate era, -0.50% trough)
- Latest value sanity check (should match current Riksbank Policy Rate ~2.25-4.00% as of 2024/2025)

Riksbank data portal probe (time-boxed 20 min):
  # Swea API (primary)
  curl -s -H "User-Agent: SONAR/2.0 (monetary-cascade)" \
    "https://api.riksbank.se/swea/v1/Observations/SECBREPOEFF" | head -30

  # Alternative series IDs if above 404
  curl -s -H "User-Agent: SONAR/2.0" \
    "https://api.riksbank.se/swea/v1/SeriesInfo/SECBREPOEFF" | head -50

  # Or list all series
  curl -s -H "User-Agent: SONAR/2.0" \
    "https://api.riksbank.se/swea/v1/series" | head -100

Document: reachability, response format (JSON likely), series stability, UA requirements, negative-value preservation.

Extend src/sonar/connectors/te.py:

SE_POLICY_RATE_EXPECTED_SYMBOL: Final = "[EMPIRICAL — probe result]"
SE_POLICY_RATE_INDICATOR: Final = "interest rate"

async def fetch_se_policy_rate(
    self,
    start: date,
    end: date,
) -> list[TEIndicatorObservation]:
    """Fetch SE Riksbank Policy Rate from TE.

    TE sources from Riksbank directly — avoids FRED OECD mirror monthly lag.
    Handles historical negative values (2015-2019 era, per Sprint V-CH pattern).
    Validates HistoricalDataSymbol matches expected per Sprint 3 Quick
    Wins source-drift discipline.

    Raises DataUnavailableError("source drift") if HistoricalDataSymbol
    != SE_POLICY_RATE_EXPECTED_SYMBOL.
    """
    obs = await self.fetch_indicator(
        country="SE",
        indicator=SE_POLICY_RATE_INDICATOR,
        start=start,
        end=end,
    )
    if obs and obs[0].historical_data_symbol != SE_POLICY_RATE_EXPECTED_SYMBOL:
        raise DataUnavailableError(...)
    return obs

Sanity check commit body:
  python -c "from sonar.connectors.te import TEConnector; c = TEConnector(api_key='x'); print(hasattr(c, 'fetch_se_policy_rate'))"

Tests (tests/unit/test_connectors/test_te_indicator.py append):
- Unit: happy path mocked response (positive value)
- Unit: happy path with NEGATIVE value (e.g. -0.50% for 2017 data)
- Unit: HistoricalDataSymbol mismatch → DataUnavailableError
- Unit: empty response → empty list
- @pytest.mark.slow live canary: fetch SE Policy Rate 2024-12-01..31 →
  assert ≥ 1 obs, value ∈ [-1.0%, 5.0%] (wide range covering historic negative + recent positive)

Cassette: tests/cassettes/connectors/te_se_policy_rate_2024_12.json

Coverage te.py additions ≥ 90%.
```

### Commit 2 — Riksbank data portal (Swea API) connector

```
feat(connectors): Riksbank Swea API public connector

Create src/sonar/connectors/riksbank.py:

"""Sveriges Riksbank data portal connector.

Public data — no auth required. Uses Swea API REST JSON.
Fallback cascade per Sprint L/S-CA/T-AU/V-CH pattern: TE → Riksbank Swea → FRED.

Empirical probe findings (Commit 1):
- Base URL: https://api.riksbank.se/swea/v1/
- Endpoints: /Observations/{series_id}, /SeriesInfo/{series_id}
- Format: JSON
- Auth: public (descriptive UA recommended)
- Key series (probe-validated Commit 1-2):
  - Policy Rate (Reporäntan/Riksbank Policy Rate): [probe result]
  - SE Gov 10Y: [probe result]
  - SEK NEER: [probe result]
"""

from __future__ import annotations
from datetime import date
from typing import Final

from sonar.connectors.base import BaseConnector
from sonar.connectors.exceptions import (
    DataUnavailableError,
    ConnectorError,
)

RIKSBANK_UA: Final = "SONAR/2.0 (monetary-cascade; https://github.com/hugocondesa-debug/sonar-engine)"
RIKSBANK_POLICY_RATE_SERIES: Final = "[probe-validated]"  # e.g. SECBREPOEFF
RIKSBANK_10Y_BOND_SERIES: Final = "[probe-validated]"

class RiksbankConnector(BaseConnector):
    """Riksbank Swea API — public, JSON REST, descriptive UA."""

    BASE_URL = "https://api.riksbank.se/swea/v1/"
    CONNECTOR_ID = "riksbank"
    USER_AGENT = RIKSBANK_UA

    async def fetch_observations(
        self,
        series_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[RiksbankObservation]:
        """Fetch time series observations from Swea API.

        Endpoint: /Observations/{series_id}[?from=...&to=...]
        Returns list of observations filtered by date range.
        Handles negative values (2015-2019 era, per Sprint V-CH pattern).
        Raises DataUnavailableError if series unreachable.
        """
        url = f"{self.BASE_URL}Observations/{series_id}"
        params = {}
        if start_date:
            params["from"] = start_date.isoformat()
        if end_date:
            params["to"] = end_date.isoformat()

        response = await self._get(
            url,
            params=params,
            headers={"User-Agent": RIKSBANK_UA},
        )
        # Parse JSON → date/value tuples (including negatives)
        ...

    async def fetch_policy_rate(
        self,
        start_date: date,
        end_date: date,
    ) -> list[RiksbankObservation]:
        """Convenience: Riksbank Policy Rate."""
        return await self.fetch_observations(RIKSBANK_POLICY_RATE_SERIES, start_date, end_date)

Sanity check:
  python -c "from sonar.connectors.riksbank import RiksbankConnector; print('OK')"

Tests (tests/unit/test_connectors/test_riksbank.py):
- Unit: class instantiation + URL building + UA header set
- Unit: fetch_observations success path (mocked JSON)
- Unit: fetch_observations NEGATIVE values handled (-0.50 example)
- Unit: fetch_observations 404 → DataUnavailableError
- Unit: fetch_observations empty → DataUnavailableError
- Unit: date filter behavior (from/to params)
- Unit: disk cache behavior
- @pytest.mark.slow live canary: probe Policy Rate recent;
  assert ≥ 1 obs, values reasonable

Coverage riksbank.py ≥ 85%.

Cassette: tests/fixtures/cassettes/riksbank/policy_rate_2024_12.json

Note: if Swea API probe failed Commit 1, scaffold with DataUnavailableError
+ open CAL-SE-RIKSBANK-PORTAL. Pattern per Sprint U-NZ RBNZ scaffold.
```

### Commit 3 — SE Tier 1 config + r*/bc_targets YAML entries

```
feat(config): SE Tier 1 enabled + monetary YAML entries

1. Verify docs/data_sources/country_tiers.yaml contains SE as Tier 1.
   Expected: already present.
   If missing, add:
   - iso_code: SE
     tier: 1
     monetary: enabled
     description: "Sweden — Tier 1 per ADR-0005"

2. Update src/sonar/config/r_star_values.yaml — add SE entry:
   SE:
     value: 0.0075       # Riksbank staff research ~0.5-1.0% (midpoint 0.75%)
     proxy: true
     source: "Riksbank Sveriges Riksbank Economic Review — neutral rate ~2024"
     timestamp: "2024-12-01"
     note: "SE historically low r*; EU + Swedish structural factors"

   Loader auto-emits R_STAR_PROXY flag.

3. Update src/sonar/config/bc_targets.yaml — add SE entry:
   SE:
     target: 0.02        # Riksbank 2% explicit target since 1993
     source: "Riksbank inflation target (introduced 1993, CPIF primary measure 2017+)"
     note: "SE uses 2% CPIF (inflation + mortgage fix rate) since 2017; was CPI previously"

Unit tests:
- Loader reads SE r* with proxy=true
- Loader handles LOW r* value (0.75% vs typical 1-2.5%)
- bc_targets loader reads SE 2% target
- country_tiers_parser includes SE in T1 list

Coverage maintained.
```

### Commit 4 — M1 SE builder with TE-primary cascade + negative-rate handling

```
feat(indices): M1 SE builder TE-primary cascade + negative-rate flag

Add build_m1_se_inputs to src/sonar/indices/monetary/builders.py:

async def build_m1_se_inputs(
    fred: FredConnector,
    te: TEConnector,
    observation_date: date,
    *,
    riksbank: RiksbankConnector | None = None,
    history_years: int = 15,
) -> M1Inputs:
    """Build M1 SE inputs via TE primary cascade.

    Cascade priority (per Sprint I-patch/L/S-CA/T-AU/U-NZ/V-CH canonical pattern):
    1. TE primary — SE_POLICY_RATE_TE_PRIMARY flag (daily Riksbank-sourced)
    2. Riksbank Swea native — SE_POLICY_RATE_RIKSBANK_NATIVE flag (REST JSON)
    3. FRED OECD mirror — SE_POLICY_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE

    r* via r_star_values.yaml (R_STAR_PROXY flag, LOW value ~0.75%).
    Inflation target via bc_targets.yaml (2% Riksbank CPIF target).

    Handles negative rate era (2015-02..2019-12) via value preservation
    (no filtering of negatives) + CH_NEGATIVE_RATE_ERA_DATA-analog flag
    for SE: SE_NEGATIVE_RATE_ERA_DATA.
    """
    flags = []
    obs = None

    # Primary: TE
    if te:
        try:
            obs = await te.fetch_se_policy_rate(start, end)
            if obs:
                flags.append("SE_POLICY_RATE_TE_PRIMARY")
                # Check for negative-rate era coverage
                if any(o.value < 0 for o in obs):
                    flags.append("SE_NEGATIVE_RATE_ERA_DATA")
        except (DataUnavailableError, ConnectorError):
            flags.append("SE_POLICY_RATE_TE_UNAVAILABLE")

    # Secondary: Riksbank Swea
    if not obs and riksbank:
        try:
            riksbank_obs = await riksbank.fetch_policy_rate(start, end)
            if riksbank_obs:
                obs = [_DatedValue(...) for o in riksbank_obs]
                flags.append("SE_POLICY_RATE_RIKSBANK_NATIVE")
        except (DataUnavailableError, ConnectorError):
            flags.append("SE_POLICY_RATE_RIKSBANK_UNAVAILABLE")

    # Tertiary: FRED OECD mirror (last-resort, monthly stale)
    if not obs:
        fred_obs = await fred.fetch_series(FRED_SE_POLICY_RATE_SERIES, start, end)
        if fred_obs:
            obs = [_DatedValue(...) for o in fred_obs]
            flags.extend([
                "SE_POLICY_RATE_FRED_FALLBACK_STALE",
                "CALIBRATION_STALE",
            ])

    if not obs:
        raise ValueError("SE Policy Rate unavailable from TE, Riksbank, FRED")

    # r* from YAML (LOW value expected)
    r_star, r_star_is_proxy = resolve_r_star("SE")
    if r_star_is_proxy:
        flags.append("R_STAR_PROXY")

    # Build M1Inputs ...

Constants (add to fred.py):
FRED_SE_POLICY_RATE_SERIES: str = "IRSTCI01SEM156N"  # OECD MEI SE short-rate
FRED_SE_BOND_10Y_SERIES: str = "IRLTLT01SEM156N"  # OECD MEI SE long-rate

Expose in __all__:
    "build_m1_se_inputs",

Tests:
- Unit: TE primary success → SE_POLICY_RATE_TE_PRIMARY
- Unit: NEGATIVE rate historical data → SE_NEGATIVE_RATE_ERA_DATA flag
- Unit: TE fails, Riksbank succeeds → SE_POLICY_RATE_RIKSBANK_NATIVE
- Unit: TE + Riksbank fail → FRED fallback → CALIBRATION_STALE
- Unit: all fail → ValueError
- Unit: r* loaded SE with proxy flag (0.75%)
- Unit: bc_targets SE 2% loaded

Coverage build_m1_se_inputs ≥ 95%.
```

### Commit 5 — Pipeline integration daily_monetary_indices SE

```
feat(pipelines): daily_monetary_indices SE country support + FRED OECD SE

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Add SE to MONETARY_SUPPORTED_COUNTRIES:
   MONETARY_SUPPORTED_COUNTRIES = ("US", "EA", "GB", "UK", "JP", "CA", "AU", "NZ", "CH", "SE")
   # SE follows Sprint V-CH negative-rate pattern
   # Note: NO addition may conflict via Sprint X-NO parallel — rebase resolution

2. SE country branch routes to build_m1_se_inputs
3. M2/M3/M4 SE: raise NotImplementedError gracefully (pattern per prior countries)
4. Connector lifecycle: Riksbank connector added to connectors_to_close (if ingested)

Update src/sonar/connectors/fred.py:
- Add FRED_SE_POLICY_RATE_SERIES constant
- Add FRED_SE_BOND_10Y_SERIES constant

Verify --country SE and --all-t1 (includes SE) work.

Tests:
- Unit: pipeline invokes SE builders when country=SE
- Unit: SE M2/M3/M4 graceful skip (NotImplementedError caught)
- Unit: connector_to_close includes Riksbank instance

Integration smoke @slow:
tests/integration/test_daily_monetary_se.py:

@pytest.mark.slow
def test_daily_monetary_se_te_primary():
    """Full pipeline SE 2024-12-31 with TE primary cascade.

    Expected:
    - M1 SE row persists
    - SE_POLICY_RATE_TE_PRIMARY flag present
    - R_STAR_PROXY flag present
    - policy_rate_pct daily-fresh"""

@pytest.mark.slow
def test_daily_monetary_se_riksbank_native_fallback():
    """TE unavailable, Riksbank Swea succeeds. Expected SE_POLICY_RATE_RIKSBANK_NATIVE flag."""

@pytest.mark.slow
def test_daily_monetary_se_negative_rate_historical():
    """Fetch SE Policy Rate 2017-01..12 (negative era).

    Expected:
    - Values < 0 preserved (no filtering)
    - SE_NEGATIVE_RATE_ERA_DATA flag present"""

Wall-clock ≤ 20s combined.

Coverage maintained.
```

### Commit 6 — M2/M4 SE scaffolds

```
feat(indices): M2 + M4 SE scaffolds (wire-ready, raise pending connectors)

Per Sprint L/S-CA/T-AU/U-NZ/V-CH pattern — M2/M4 SE builders are scaffolds
raising InsufficientDataError.

async def build_m2_se_inputs(...) -> M2Inputs:
    """M2 SE scaffold — output gap needs SCB or OECD EO."""
    raise InsufficientDataError(
        "SE M2 requires output_gap; pending SCB/OECD EO connector. "
        "CAL-SE-M2-OUTPUT-GAP tracking resolution."
    )

async def build_m4_se_inputs(...) -> M4Inputs:
    """M4 SE scaffold — FCI components need SEK-specific VIX, credit spreads, NEER."""
    raise InsufficientDataError(
        "SE M4 requires VIX-SE / credit-spread-SE / NEER-SEK; all deferred. "
        "CAL-SE-M4-FCI tracking full wire-up."
    )

Tests:
- Unit: build_m2_se_inputs raises InsufficientDataError
- Unit: build_m4_se_inputs raises InsufficientDataError
- Unit: error message references correct CAL items

Coverage maintained.
```

### Commit 7 — Retrospective + CAL items opened

```
docs(planning+backlog): Week 9 Sprint W-SE Riksbank connector retrospective

File: docs/planning/retrospectives/week9-sprint-w-se-connector-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- Empirical findings:
  - TE SE Policy Rate HistoricalDataSymbol: [probe result]
  - Riksbank Swea API reachability: [success/issues/partial]
  - FRED OECD SE mirror series validated
  - Negative-rate era handling (2015-2019 values preserved, SE_NEGATIVE_RATE_ERA_DATA flag)
- Coverage delta
- Live canary outcomes (including negative-rate historical canary)
- HALT triggers fired / not fired
- Deviations from brief
- M2 T1 progression: 13 → 14 countries
- SE monetary indices operational:
  - M1: live via TE cascade (Riksbank Swea if probe succeeded)
  - M2: scaffold (CAL-SE-M2-OUTPUT-GAP)
  - M3: deferred (CAL-SE-M3)
  - M4: scaffold (CAL-SE-M4-FCI)
- Pattern validation:
  - TE-primary cascade continues canonical (7th country)
  - Second negative-rate country (CH Sprint V-CH first) — pattern reusable
  - Riksbank Swea = JSON REST likely (BoC Valet / SNB data-portal analog)
- Isolated worktree: zero collision incidents with Sprint X-NO parallel
- Merge strategy: branch sprint-w-se-connector → main (rebase if X-NO merged first)
- New CAL items opened:
  - CAL-SE-M2-OUTPUT-GAP
  - CAL-SE-M3
  - CAL-SE-M4-FCI
  - CAL-SE-RIKSBANK-PORTAL (if probe failed)
  - CAL-SE-NEGATIVE-RATE-SHADOW (deferred Phase 2+ — shared with CH)

Open CAL-SE-* items formally in docs/backlog/calibration-tasks.md.

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git merge --ff-only sprint-w-se-connector
  git push origin main
  # If rebase needed (X-NO merged first):
  # cd /home/macro/projects/sonar-wt-sprint-w
  # git fetch origin && git rebase origin/main
  # Resolve union-merge conflicts (te.py/fred.py/builders.py/pipelines/YAMLs/backlog)
  # git push --force-with-lease
  # Then merge
```

---

## 5. HALT triggers (atomic)

0. **TE SE Policy Rate empirical probe fails** — if TE returns no SE data or unexpected format, HALT + surface. Alternative: FRED primary.
1. **HistoricalDataSymbol mismatch** — if TE returns different symbol than probe found, do NOT assume benign. HALT.
2. **Riksbank Swea unreachable** — possible; apply UA lesson. If still unreachable, scaffold with DataUnavailableError + open CAL-SE-RIKSBANK-PORTAL. Not a HALT.
3. **Negative values causing parser errors** — if any logic assumes positive rates, HALT + fix for negative-rate-era compatibility (per Sprint V-CH precedent).
4. **SE in country_tiers.yaml Tier mismatch** — HALT + verify against ADR-0005.
5. **r* SE value uncertainty** — use 0.75% midpoint + R_STAR_PROXY flag. Document source in YAML comment.
6. **bc_targets SE** — 2% explicit target, no band ambiguity.
7. **M2/M4 scaffolds pattern** — per precedent, raise InsufficientDataError. Verify pattern replication.
8. **TE rate limits** during live canaries — tenacity handles; document in retro if persistent.
9. **Coverage regression > 3pp** → HALT.
10. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
11. **Concurrent Sprint X-NO touches files in Sprint W scope** (likely minor conflicts in te.py/fred.py/builders.py/pipelines/daily_monetary_indices.py/YAMLs/backlog) → reconcile via rebase post-merge.

---

## 6. Acceptance

### Global sprint-end
- [ ] 6-8 commits pushed to branch `sprint-w-se-connector`
- [ ] `src/sonar/connectors/riksbank.py` shipped + tested (even if Swea probe partial)
- [ ] `fetch_se_policy_rate` TE wrapper + source-drift guard shipped
- [ ] TE SE HistoricalDataSymbol validated + documented
- [ ] Riksbank Swea reachability documented (probe result)
- [ ] Negative-rate era handling validated (2015-2019 values preserved)
- [ ] SE Tier 1 in country_tiers.yaml
- [ ] r_star_values.yaml SE entry added (with proxy: true, 0.75%)
- [ ] bc_targets.yaml SE entry present (2% CPIF)
- [ ] `build_m1_se_inputs` cascade operational with SE_NEGATIVE_RATE_ERA_DATA flag
- [ ] M2 + M4 SE scaffolds shipped (raise InsufficientDataError)
- [ ] `daily_monetary_indices.py --country SE` runs end-to-end
- [ ] Live canaries PASS: TE SE Policy Rate + SE monetary pipeline + historical negative-rate test
- [ ] Coverage riksbank.py ≥ 85%, builders.py SE path ≥ 95%
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week9-sprint-w-se-connector-report.md`

**Final tmux echo**:
```
SPRINT W-SE SWEDEN CONNECTOR DONE: N commits on branch sprint-w-se-connector
TE HistoricalDataSymbol SE validated: [symbol]
Riksbank Swea reachability: [success / issues / partial]
Negative-rate era support: VALIDATED (2015-2019 data preserved, SE_NEGATIVE_RATE_ERA_DATA)
SE monetary: M1 (cascade), M2/M4 (scaffolds), M3 (deferred)
M2 T1 progression: 13 → 14 countries
HALT triggers: [list or "none"]
Merge: git checkout main && git merge --ff-only sprint-w-se-connector
   (rebase may be required if Sprint X-NO merged first)
Artifact: docs/planning/retrospectives/week9-sprint-w-se-connector-report.md
```

---

## 8. Pre-push gate (mandatory)

```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov
```

Full project mypy. No `--no-verify`.

Live canaries (@pytest.mark.slow) run explicitly during Commit 1+2+5.

---

## 9. Notes on implementation

### TE primary canonical (7th consecutive country)
Pattern stable 6 iterations deep. SE replicates CH pattern closely (negative-rate + low r*).

### Riksbank Swea API likely JSON REST
Well-documented Swedish central bank API. Expect success. BoC Valet / SNB data-portal closest analogs.

### Negative-rate era (2nd country — CH Sprint V-CH was first)
SE had -0.50% trough 2015-02..2019-12. Pattern established Sprint V-CH:
- Parser preserves negative values
- Flag: `SE_NEGATIVE_RATE_ERA_DATA`
- Known limitation: M1 compute may raise InsufficientDataError at ZLB (shared CAL with CH — CAL-NEGATIVE-RATE-SHADOW for Krippner shadow-rate connector Phase 2+)

### Pattern replication discipline (7th iteration)
Sprint V-CH CH shipped Day 3. This sprint mirrors closely:
- TE wrapper with source-drift guard
- Native connector (JSON REST per Swea API)
- M1 builder with cascade + negative-rate handling
- M2/M4 scaffolds
- Pipeline integration
- Retro

### Isolated worktree workflow
Sprint W-SE operates entirely in `/home/macro/projects/sonar-wt-sprint-w`. Branch: `sprint-w-se-connector`.

### Sprint X-NO parallel
Runs in `sonar-wt-sprint-x`. Shared-file append zones → rebase-expected post-merge. Alphabetical: W-SE first; X-NO rebases.

---

*End of Week 9 Sprint W-SE Sweden connector brief. 6-8 commits. SE T1 shipped with TE-primary cascade + negative-rate era support.*
