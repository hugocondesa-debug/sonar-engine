# Week 9 Sprint X-NO — Norway Norges Bank Connector + M1 NO (TE-primary Cascade)

**Target**: Ship Norges Bank connector + NO country enablement for M1 monetary. M2 T1 progression from 14 to 15 countries. TE-primary cascade per canonical pattern. Unique context: oil-driven FX dynamics, never had negative rates.
**Priority**: HIGH (M2 T1 Completionist progression — 6 of 7 remaining T1 countries at Week 9 start)
**Budget**: 3-4h CC autonomous
**Commits**: ~6-8
**Base**: branch `sprint-x-no-connector` (isolated worktree `/home/macro/projects/sonar-wt-sprint-x`)
**Concurrency**: Parallel to Sprint W-SE Sweden Riksbank connector in worktree `sonar-wt-sprint-w`. See §3.

---

## 1. Scope

In:
- `src/sonar/connectors/norgesbank.py` — new Norges Bank connector
- **Cascade strategy per canonical pattern (TE-primary default)**:
  1. **Primary: TE native NO Policy Rate / Norwegian Gov bond yields** (daily, Norges Bank-sourced via TE)
  2. **Secondary: Norges Bank data API** (public REST — https://data.norges-bank.no/api/)
  3. **Tertiary: FRED OECD mirror** (monthly-lagged; last-resort with `CALIBRATION_STALE` flag)
- TE wrapper `fetch_no_policy_rate` with HistoricalDataSymbol source-drift guard
- Core series empirical discovery:
  - NO Policy Rate (Styringsrenten): probe Commit 1 (likely `NORIR`, `NBPOLRATE`, or similar)
  - NO 10Y Government bond yield: TE `GNOR10YR:IND` or similar (verify existing mapping)
  - NO CPI + unemployment: TE generic `fetch_indicator(country="NO", ...)` pattern
- Empirical Norges Bank data API probe (time-boxed 20 min)
  - API docs: `https://app.norges-bank.no/iv-api-client/` (DataAPI)
  - Pattern: `https://data.norges-bank.no/api/data/{dataset}/{key}?format=json`
- NO country entry in `docs/data_sources/country_tiers.yaml` (verify Tier 1 per ADR-0005)
- r* NO entry in `src/sonar/config/r_star_values.yaml` (~1.0-1.5% per Norges Bank research)
- NO inflation target in `src/sonar/config/bc_targets.yaml` (0.02 per Norges Bank 2% target since 2018)
- M1 NO builder via TE-primary cascade (M2/M4 scaffolds only; full wiring deferred CAL-NO-*)
- Pipeline integration `daily_monetary_indices.py --country NO`
- Cassette + `@pytest.mark.slow` live canary for TE + Norges Bank paths
- Retrospective

Out:
- M2 NO live (output gap requires SSB / OECD EO — CAL-NO-M2-OUTPUT-GAP)
- M3 NO (requires persisted NSS forwards + expected-inflation for NO — CAL-NO-M3)
- M4 NO (FCI — requires VIX-NO, credit spreads NO, NOK NEER — CAL-NO-M4-FCI)
- NO ERP per-country live (deferred Phase 2+)
- NO CRP (BENCHMARK via spec; sovereign yield spread automatic)
- L3 credit indices NO (BIS coverage via Sprint AA fix)
- **Oil-price coupling analysis** — deferred Phase 2+ research topic (NOK/USD driven by Brent crude)

---

## 2. Spec reference

Authoritative:
- `docs/data_sources/country_tiers.yaml` — NO should be Tier 1 per ADR-0005
- `docs/specs/indices/monetary/M1-effective-rates.md` §2
- `docs/specs/indices/monetary/M2-taylor-gaps.md` §2
- `docs/specs/conventions/patterns.md` — Pattern 4
- `docs/planning/retrospectives/week9-sprint-v-ch-connector-report.md` — Sprint V-CH data-portal pattern
- `docs/planning/retrospectives/week9-sprint-s-ca-connector-report.md` — **Sprint S-CA BoC Valet JSON REST pattern (most relevant)**
- `docs/planning/retrospectives/week9-sprint-t-au-connector-report.md` — Sprint T-AU RBA CSV pattern
- `src/sonar/connectors/boc.py` — Sprint S-CA JSON REST connector template (most likely Norges Bank analog)
- `src/sonar/connectors/snb.py` — Sprint V-CH data-portal template alt
- `src/sonar/connectors/te.py` — existing NO country mappings

**Pre-flight requirement**: Commit 1 CC:
1. Verify TE NO mappings: `"NO": "norway"` (indicator) + NO bond mapping likely exists from Sprint 1
2. Probe TE NO Policy Rate empirically:
   ```bash
   set -a && source .env && set +a
   curl -s "https://api.tradingeconomics.com/historical/country/norway/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'
   ```
3. Document TE HistoricalDataSymbol for NO Policy Rate (probe finding)
4. Time-boxed 20 min Norges Bank data API probe:
   - DataAPI docs: `curl -sL "https://data.norges-bank.no/api/" | head -30`
   - Policy rate dataset (guess): `IR` or `STYR`:
     ```
     curl -s "https://data.norges-bank.no/api/data/IR/B.KPRA.SD.R.?format=json&lastNObservations=5" | head -40
     ```
     OR
     ```
     curl -s "https://data.norges-bank.no/api/data/STYR?format=json&lastNObservations=5" | head -40
     ```
   - Documentation: `https://app.norges-bank.no/iv-api-client/`
   - Apply UA-gate lesson per Sprint T-AU if 403: use `User-Agent: SONAR/2.0 (monetary-cascade; ...)` header
5. If Norges Bank probe SUCCEEDS → implement connector as secondary in cascade
6. If Norges Bank probe FAILS → scaffold raising DataUnavailableError (gated; document for CAL-NO-NORGESBANK-API)
7. Read `boc.py` as template first (JSON REST most likely for Norges Bank)
8. Verify NO in `country_tiers.yaml`; if missing, add as Tier 1

Document findings in Commit 1 body. **Note**: NO never had negative rates (unlike CH, SE, EA). Standard positive-rate processing applies.

Existing assets:
- `TEConnector` generic + 10 country wrappers (pre-Day-4) — SE + NO Day 4 additions
- FRED connector has `fetch_series` for any series ID
- `country_tiers.yaml` canonical (ISO alpha-2)
- `bc_targets.yaml` + `r_star_values.yaml` extended CH/SE pattern

---

## 3. Concurrency — parallel protocol with Sprint W-SE + ISOLATED WORKTREES

**Sprint X-NO operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-x`

Sprint W-SE operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-w`

**Critical workflow**:
1. Sprint X-NO CC starts by `cd /home/macro/projects/sonar-wt-sprint-x`
2. All file operations happen in this worktree
3. Branch name: `sprint-x-no-connector`
4. Pushes to `origin/sprint-x-no-connector`
5. Final merge to main via fast-forward post-sprint-close (rebase likely — W-SE merges first alphabetically)

**File scope Sprint X-NO**:
- `src/sonar/connectors/norgesbank.py` NEW
- `src/sonar/connectors/te.py` APPEND (new `fetch_no_policy_rate` wrapper + NO-specific constants)
- `src/sonar/indices/monetary/builders.py` APPEND (add NO builders — `build_m1_no_inputs`)
- `src/sonar/connectors/fred.py` MODIFY (add NO FRED OECD series constants)
- `docs/data_sources/country_tiers.yaml` — verify/add NO entry (likely exists)
- `src/sonar/config/r_star_values.yaml` — add NO entry
- `src/sonar/config/bc_targets.yaml` — verify/add NO entry
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (add NO to MONETARY_SUPPORTED_COUNTRIES + NO country dispatch)
- Tests:
  - `tests/unit/test_connectors/test_norgesbank.py` NEW
  - `tests/unit/test_connectors/test_te_indicator.py` APPEND (NO Policy Rate wrapper tests)
  - `tests/unit/test_indices/monetary/test_builders.py` APPEND (NO builder tests)
  - `tests/unit/test_indices/monetary/test_config_loaders.py` APPEND (NO entries)
  - `tests/unit/test_pipelines/test_daily_monetary_indices.py` APPEND (NO country)
  - `tests/integration/test_daily_monetary_no.py` NEW
  - `tests/fixtures/cassettes/norgesbank/` + `tests/cassettes/connectors/te_no_policy_rate_*.json`
- `docs/backlog/calibration-tasks.md` MODIFY (CAL-NO-* entries)
- `docs/planning/retrospectives/week9-sprint-x-no-connector-report.md` NEW

**Sprint W-SE scope** (for awareness, DO NOT TOUCH):
- `src/sonar/connectors/riksbank.py` NEW
- `src/sonar/connectors/te.py` APPEND (SE wrapper — **concurrent append zone**)
- `src/sonar/indices/monetary/builders.py` APPEND (SE builders — **concurrent append zone**)
- `src/sonar/connectors/fred.py` MODIFY (SE FRED series — **concurrent append zone**)
- `src/sonar/config/*.yaml` (SE entries — **concurrent modify zone**)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (SE dispatch — **concurrent modify zone**)

**Potential conflict zones** (same as W-SE §3, mirror):
- `te.py` — both append wrappers (different functions, merge clean)
- `fred.py` — both append constants (different names, merge clean)
- `builders.py` — both append builders (different functions, merge clean)
- `daily_monetary_indices.py` — both add to MONETARY_SUPPORTED_COUNTRIES tuple (likely conflict, union-merge)
- `r_star_values.yaml` + `bc_targets.yaml` — both add entries (merge clean if different keys)
- `calibration-tasks.md` — CAL entries (union-merge precedent)

**Rebase expected post-merge**. Sprint W-SE merges first (alphabetical priority) → X-NO rebases.

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-sprint-x && git pull origin main --rebase`

**Push race**: normal `git push origin sprint-x-no-connector`. Minor conflicts resolved via rebase.

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-x-no-connector
git push origin main
```
(If rebase needed: `git rebase origin/main` in worktree → resolve → push --force-with-lease → merge.)

---

## 4. Commits

### Commit 1 — Pre-flight + TE NO Policy Rate wrapper

```
feat(connectors): TE fetch_no_policy_rate wrapper + source-drift guard

Pre-flight: probe TE NO Policy Rate + verify Norges Bank data API reachability.

Expected probe (document findings commit body):
  set -a && source .env && set +a
  curl -s "https://api.tradingeconomics.com/historical/country/norway/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'

Document in commit body:
- Actual HistoricalDataSymbol returned (likely NORIR, NBPOLRATE, or policy-rate type)
- Response format (date + value)
- Historical range (expected: daily since Norges Bank inflation-targeting 2001)
- Latest value sanity check (should match current Norges Bank Styringsrenten ~4.00-4.50% as of 2024/2025)

Norges Bank data API probe (time-boxed 20 min):
  # Policy rate dataset IR
  curl -s "https://data.norges-bank.no/api/data/IR/B.KPRA.SD.R.?format=sdmx-json&lastNObservations=5" | head -60

  # OR STYR dataset
  curl -s "https://data.norges-bank.no/api/data/STYR?format=sdmx-json&lastNObservations=5" | head -40

  # Explore datasets
  curl -s "https://data.norges-bank.no/api/data" | head -50

Document: reachability, response format (SDMX JSON or CSV), series stability, UA requirements, dataset ID for Styringsrenten.

Extend src/sonar/connectors/te.py:

NO_POLICY_RATE_EXPECTED_SYMBOL: Final = "[EMPIRICAL — probe result]"
NO_POLICY_RATE_INDICATOR: Final = "interest rate"

async def fetch_no_policy_rate(
    self,
    start: date,
    end: date,
) -> list[TEIndicatorObservation]:
    """Fetch NO Norges Bank Policy Rate (Styringsrenten) from TE.

    TE sources from Norges Bank directly — avoids FRED OECD mirror monthly lag.
    Validates HistoricalDataSymbol matches expected per Sprint 3 Quick
    Wins source-drift discipline.

    Raises DataUnavailableError("source drift") if HistoricalDataSymbol
    != NO_POLICY_RATE_EXPECTED_SYMBOL.
    """
    obs = await self.fetch_indicator(
        country="NO",
        indicator=NO_POLICY_RATE_INDICATOR,
        start=start,
        end=end,
    )
    if obs and obs[0].historical_data_symbol != NO_POLICY_RATE_EXPECTED_SYMBOL:
        raise DataUnavailableError(...)
    return obs

Sanity check commit body:
  python -c "from sonar.connectors.te import TEConnector; c = TEConnector(api_key='x'); print(hasattr(c, 'fetch_no_policy_rate'))"

Tests (tests/unit/test_connectors/test_te_indicator.py append):
- Unit: happy path mocked response
- Unit: HistoricalDataSymbol mismatch → DataUnavailableError
- Unit: empty response → empty list
- @pytest.mark.slow live canary: fetch NO Policy Rate 2024-12-01..31 →
  assert ≥ 1 obs, value ∈ [0.10%, 8.0%] (reasonable range for recent Norges Bank cycles)

Cassette: tests/cassettes/connectors/te_no_policy_rate_2024_12.json

Coverage te.py additions ≥ 90%.
```

### Commit 2 — Norges Bank data API connector

```
feat(connectors): Norges Bank DataAPI public JSON REST connector

Create src/sonar/connectors/norgesbank.py:

"""Norges Bank data API connector.

Public data — no auth required. SDMX-JSON REST API.
Fallback cascade per Sprint L/S-CA/T-AU/V-CH pattern: TE → Norges Bank API → FRED.

Empirical probe findings (Commit 1):
- Base URL: https://data.norges-bank.no/api/
- Endpoints: /data/{dataset}/{key}?format=sdmx-json
- Format: SDMX-JSON (1.0 or 2.0 per probe)
- Auth: public
- Key datasets (probe-validated Commit 1-2):
  - IR (Interest Rates): Styringsrenten at key B.KPRA.SD.R.
  - EXR (Exchange Rates): NOK/USD, NOK/EUR
  - CPI: Consumer Price Index
"""

from __future__ import annotations
from datetime import date
from typing import Final

from sonar.connectors.base import BaseConnector
from sonar.connectors.exceptions import (
    DataUnavailableError,
    ConnectorError,
)

NORGESBANK_UA: Final = "SONAR/2.0 (monetary-cascade; https://github.com/hugocondesa-debug/sonar-engine)"
NORGESBANK_POLICY_RATE_DATASET: Final = "IR"
NORGESBANK_POLICY_RATE_KEY: Final = "B.KPRA.SD.R."  # probe-validated
NORGESBANK_BOND_10Y_DATASET: Final = "[probe-validated]"

class NorgesBankConnector(BaseConnector):
    """Norges Bank DataAPI — public JSON REST."""

    BASE_URL = "https://data.norges-bank.no/api/"
    CONNECTOR_ID = "norgesbank"
    USER_AGENT = NORGESBANK_UA

    async def fetch_data(
        self,
        dataset: str,
        key: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[NorgesBankObservation]:
        """Fetch data from Norges Bank DataAPI.

        Endpoint: /data/{dataset}/{key}?format=sdmx-json
        Returns list of observations filtered by date range.
        Raises DataUnavailableError if dataset/key unreachable.
        """
        url = f"{self.BASE_URL}data/{dataset}/{key}"
        params = {"format": "sdmx-json"}
        if start_date:
            params["startPeriod"] = start_date.isoformat()
        if end_date:
            params["endPeriod"] = end_date.isoformat()

        response = await self._get(
            url,
            params=params,
            headers={"User-Agent": NORGESBANK_UA},
        )
        # Parse SDMX-JSON → date/value tuples
        ...

    async def fetch_policy_rate(
        self,
        start_date: date,
        end_date: date,
    ) -> list[NorgesBankObservation]:
        """Convenience: Styringsrenten (Norges Bank Policy Rate)."""
        return await self.fetch_data(
            NORGESBANK_POLICY_RATE_DATASET,
            NORGESBANK_POLICY_RATE_KEY,
            start_date,
            end_date,
        )

Sanity check:
  python -c "from sonar.connectors.norgesbank import NorgesBankConnector; print('OK')"

Tests (tests/unit/test_connectors/test_norgesbank.py):
- Unit: class instantiation + URL building + UA header set
- Unit: fetch_data success path (mocked SDMX-JSON)
- Unit: fetch_data 404 → DataUnavailableError
- Unit: fetch_data empty → DataUnavailableError
- Unit: date filter behavior (startPeriod/endPeriod params)
- Unit: disk cache behavior
- @pytest.mark.slow live canary: probe Policy Rate recent;
  assert ≥ 1 obs, values reasonable

Coverage norgesbank.py ≥ 85%.

Cassette: tests/fixtures/cassettes/norgesbank/policy_rate_2024_12.json

Note: if Norges Bank API uses different SDMX version (2.1 vs 2.0), adapt
parser. If probe failed Commit 1, scaffold with DataUnavailableError
+ open CAL-NO-NORGESBANK-API.
```

### Commit 3 — NO Tier 1 config + r*/bc_targets YAML entries

```
feat(config): NO Tier 1 enabled + monetary YAML entries

1. Verify docs/data_sources/country_tiers.yaml contains NO as Tier 1.
   Expected: already present.
   If missing, add:
   - iso_code: NO
     tier: 1
     monetary: enabled
     description: "Norway — Tier 1 per ADR-0005"

2. Update src/sonar/config/r_star_values.yaml — add NO entry:
   NO:
     value: 0.0125       # Norges Bank staff research ~1.0-1.5% (midpoint 1.25%)
     proxy: true
     source: "Norges Bank Occasional Papers / Staff Memos — neutral rate ~2024"
     timestamp: "2024-12-01"
     note: "NO resource-rich economy; r* reflects neutral rate post-Oil Fund stabilization"

   Loader auto-emits R_STAR_PROXY flag.

3. Update src/sonar/config/bc_targets.yaml — add NO entry:
   NO:
     target: 0.02        # Norges Bank 2% since 2018 (was 2.5% 2001-2018)
     source: "Norges Bank Regulations for Monetary Policy (revised 2018)"
     note: "NO target revised 2018 (2.5% → 2.0%); pre-2018 backtests should use 2.5%"

Unit tests:
- Loader reads NO r* with proxy=true
- bc_targets loader reads NO 2% target
- country_tiers_parser includes NO in T1 list

Coverage maintained.
```

### Commit 4 — M1 NO builder with TE-primary cascade

```
feat(indices): M1 NO builder TE-primary cascade

Add build_m1_no_inputs to src/sonar/indices/monetary/builders.py:

async def build_m1_no_inputs(
    fred: FredConnector,
    te: TEConnector,
    observation_date: date,
    *,
    norgesbank: NorgesBankConnector | None = None,
    history_years: int = 15,
) -> M1Inputs:
    """Build M1 NO inputs via TE primary cascade.

    Cascade priority (per canonical pattern):
    1. TE primary — NO_POLICY_RATE_TE_PRIMARY flag (daily Norges Bank-sourced)
    2. Norges Bank API native — NO_POLICY_RATE_NORGESBANK_NATIVE flag (SDMX-JSON)
    3. FRED OECD mirror — NO_POLICY_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE

    r* via r_star_values.yaml (R_STAR_PROXY flag, 1.25%).
    Inflation target via bc_targets.yaml (2% Norges Bank target).

    NO never had negative rates (no _NEGATIVE_RATE_ERA_DATA flag needed).
    """
    flags = []
    obs = None

    # Primary: TE
    if te:
        try:
            obs = await te.fetch_no_policy_rate(start, end)
            if obs:
                flags.append("NO_POLICY_RATE_TE_PRIMARY")
        except (DataUnavailableError, ConnectorError):
            flags.append("NO_POLICY_RATE_TE_UNAVAILABLE")

    # Secondary: Norges Bank API
    if not obs and norgesbank:
        try:
            nb_obs = await norgesbank.fetch_policy_rate(start, end)
            if nb_obs:
                obs = [_DatedValue(...) for o in nb_obs]
                flags.append("NO_POLICY_RATE_NORGESBANK_NATIVE")
        except (DataUnavailableError, ConnectorError):
            flags.append("NO_POLICY_RATE_NORGESBANK_UNAVAILABLE")

    # Tertiary: FRED OECD mirror (last-resort, monthly stale)
    if not obs:
        fred_obs = await fred.fetch_series(FRED_NO_POLICY_RATE_SERIES, start, end)
        if fred_obs:
            obs = [_DatedValue(...) for o in fred_obs]
            flags.extend([
                "NO_POLICY_RATE_FRED_FALLBACK_STALE",
                "CALIBRATION_STALE",
            ])

    if not obs:
        raise ValueError("NO Policy Rate unavailable from TE, Norges Bank, FRED")

    # r* from YAML
    r_star, r_star_is_proxy = resolve_r_star("NO")
    if r_star_is_proxy:
        flags.append("R_STAR_PROXY")

    # Build M1Inputs ...

Constants (add to fred.py):
FRED_NO_POLICY_RATE_SERIES: str = "IRSTCI01NOM156N"  # OECD MEI NO short-rate
FRED_NO_BOND_10Y_SERIES: str = "IRLTLT01NOM156N"  # OECD MEI NO long-rate

Expose in __all__:
    "build_m1_no_inputs",

Tests:
- Unit: TE primary success → NO_POLICY_RATE_TE_PRIMARY
- Unit: TE fails, Norges Bank succeeds → NO_POLICY_RATE_NORGESBANK_NATIVE
- Unit: TE + Norges Bank fail → FRED fallback → CALIBRATION_STALE
- Unit: all fail → ValueError
- Unit: r* loaded NO with proxy flag (1.25%)
- Unit: bc_targets NO 2% loaded

Coverage build_m1_no_inputs ≥ 95%.
```

### Commit 5 — Pipeline integration daily_monetary_indices NO

```
feat(pipelines): daily_monetary_indices NO country support + FRED OECD NO

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Add NO to MONETARY_SUPPORTED_COUNTRIES:
   MONETARY_SUPPORTED_COUNTRIES = ("US", "EA", "GB", "UK", "JP", "CA", "AU", "NZ", "CH", "SE", "NO")
   # NO follows Sprint V-CH/W-SE data-portal pattern
   # Note: SE addition may conflict via Sprint W-SE parallel — rebase resolution

2. NO country branch routes to build_m1_no_inputs
3. M2/M3/M4 NO: raise NotImplementedError gracefully
4. Connector lifecycle: Norges Bank connector added to connectors_to_close

Update src/sonar/connectors/fred.py:
- Add FRED_NO_POLICY_RATE_SERIES constant
- Add FRED_NO_BOND_10Y_SERIES constant

Verify --country NO and --all-t1 (includes NO) work.

Tests:
- Unit: pipeline invokes NO builders when country=NO
- Unit: NO M2/M3/M4 graceful skip
- Unit: connector_to_close includes Norges Bank instance

Integration smoke @slow:
tests/integration/test_daily_monetary_no.py:

@pytest.mark.slow
def test_daily_monetary_no_te_primary():
    """Full pipeline NO 2024-12-31 with TE primary cascade.

    Expected:
    - M1 NO row persists
    - NO_POLICY_RATE_TE_PRIMARY flag present
    - R_STAR_PROXY flag present
    - policy_rate_pct daily-fresh"""

@pytest.mark.slow
def test_daily_monetary_no_norgesbank_native_fallback():
    """TE unavailable, Norges Bank API succeeds. Expected NO_POLICY_RATE_NORGESBANK_NATIVE flag."""

Wall-clock ≤ 15s combined.

Coverage maintained.
```

### Commit 6 — M2/M4 NO scaffolds

```
feat(indices): M2 + M4 NO scaffolds (wire-ready, raise pending connectors)

Per canonical pattern — M2/M4 NO builders are scaffolds
raising InsufficientDataError.

async def build_m2_no_inputs(...) -> M2Inputs:
    """M2 NO scaffold — output gap needs SSB or OECD EO."""
    raise InsufficientDataError(
        "NO M2 requires output_gap; pending SSB/OECD EO connector. "
        "CAL-NO-M2-OUTPUT-GAP tracking resolution."
    )

async def build_m4_no_inputs(...) -> M4Inputs:
    """M4 NO scaffold — FCI components need NOK-specific VIX, credit spreads, NEER."""
    raise InsufficientDataError(
        "NO M4 requires VIX-NO / credit-spread-NO / NEER-NOK; all deferred. "
        "CAL-NO-M4-FCI tracking full wire-up."
    )

Tests:
- Unit: build_m2_no_inputs raises InsufficientDataError
- Unit: build_m4_no_inputs raises InsufficientDataError
- Unit: error message references correct CAL items

Coverage maintained.
```

### Commit 7 — Retrospective + CAL items opened

```
docs(planning+backlog): Week 9 Sprint X-NO Norges Bank connector retrospective

File: docs/planning/retrospectives/week9-sprint-x-no-connector-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- Empirical findings:
  - TE NO Policy Rate HistoricalDataSymbol: [probe result]
  - Norges Bank DataAPI reachability: [success/issues/partial]
  - FRED OECD NO mirror series validated
- Coverage delta
- Live canary outcomes
- HALT triggers fired / not fired
- Deviations from brief
- M2 T1 progression: 14 → 15 countries
- NO monetary indices operational:
  - M1: live via TE cascade (Norges Bank API if probe succeeded)
  - M2: scaffold (CAL-NO-M2-OUTPUT-GAP)
  - M3: deferred (CAL-NO-M3)
  - M4: scaffold (CAL-NO-M4-FCI)
- Pattern validation:
  - TE-primary cascade continues canonical (8th country)
  - Norges Bank = SDMX-JSON REST (BoC Valet / SNB analog)
  - NO never negative-rate — standard positive-only processing
- Isolated worktree: zero collision incidents with Sprint W-SE parallel
- Merge strategy: branch sprint-x-no-connector → main (rebase expected post W-SE merge)
- New CAL items opened:
  - CAL-NO-M2-OUTPUT-GAP
  - CAL-NO-M3
  - CAL-NO-M4-FCI
  - CAL-NO-NORGESBANK-API (if probe failed)
  - CAL-NO-OIL-COUPLING (deferred Phase 2+ research — NOK/Brent coupling analysis)

Open CAL-NO-* items formally in docs/backlog/calibration-tasks.md.

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git merge --ff-only sprint-x-no-connector
  git push origin main
  # If rebase needed (Sprint W-SE merged first):
  # cd /home/macro/projects/sonar-wt-sprint-x
  # git fetch origin && git rebase origin/main
  # Resolve union-merge conflicts (te.py/fred.py/builders.py/pipelines/YAMLs/backlog)
  # git push --force-with-lease
  # Then merge
```

---

## 5. HALT triggers (atomic)

0. **TE NO Policy Rate empirical probe fails** — HALT + surface. Alternative: FRED primary.
1. **HistoricalDataSymbol mismatch** — HALT.
2. **Norges Bank API unreachable** — apply UA lesson. If still unreachable, scaffold + open CAL-NO-NORGESBANK-API. Not a HALT.
3. **Norges Bank SDMX version mismatch** — if API returns different SDMX format than probe expected, adapt or scope narrow.
4. **NO in country_tiers.yaml Tier mismatch** — HALT + verify against ADR-0005.
5. **r* NO value uncertainty** — 1.25% midpoint + R_STAR_PROXY flag.
6. **bc_targets NO ambiguity** — 2% explicit since 2018. Document historical 2.5% for pre-2018 backtests.
7. **M2/M4 scaffolds pattern** — per precedent, raise InsufficientDataError. Verify pattern replication.
8. **TE rate limits** during live canaries — tenacity handles.
9. **Coverage regression > 3pp** → HALT.
10. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
11. **Concurrent Sprint W-SE touches files in Sprint X scope** → reconcile via rebase post-merge.

---

## 6. Acceptance

### Global sprint-end
- [ ] 6-8 commits pushed to branch `sprint-x-no-connector`
- [ ] `src/sonar/connectors/norgesbank.py` shipped + tested (even if API probe partial)
- [ ] `fetch_no_policy_rate` TE wrapper + source-drift guard shipped
- [ ] TE NO HistoricalDataSymbol validated + documented
- [ ] Norges Bank API reachability documented (probe result)
- [ ] NO Tier 1 in country_tiers.yaml
- [ ] r_star_values.yaml NO entry added (with proxy: true, 1.25%)
- [ ] bc_targets.yaml NO entry present (2%)
- [ ] `build_m1_no_inputs` cascade operational
- [ ] M2 + M4 NO scaffolds shipped (raise InsufficientDataError)
- [ ] `daily_monetary_indices.py --country NO` runs end-to-end
- [ ] Live canaries PASS: TE NO Policy Rate + NO monetary pipeline
- [ ] Coverage norgesbank.py ≥ 85%, builders.py NO path ≥ 95%
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week9-sprint-x-no-connector-report.md`

**Final tmux echo**:
```
SPRINT X-NO NORWAY CONNECTOR DONE: N commits on branch sprint-x-no-connector
TE HistoricalDataSymbol NO validated: [symbol]
Norges Bank API reachability: [success / issues / partial]
NO monetary: M1 (cascade), M2/M4 (scaffolds), M3 (deferred)
M2 T1 progression: 14 → 15 countries
HALT triggers: [list or "none"]
Merge: git checkout main && git merge --ff-only sprint-x-no-connector
   (rebase may be required if Sprint W-SE merged first)
Artifact: docs/planning/retrospectives/week9-sprint-x-no-connector-report.md
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

### TE primary canonical (8th consecutive country)
Pattern stable 7 iterations deep. NO follows same approach.

### Norges Bank DataAPI = SDMX-JSON REST
Well-documented Norwegian central bank API. Expected easy success. BoC Valet / SNB data-portal closest analogs.

### NO is the first country in Week 9 expansion WITHOUT negative-rate era
SE + CH both had negative rates. NO never went negative (lowest was 0.25% 2020-2021). Standard positive-only processing applies.

### Pattern replication discipline (8th iteration)
Sprint V-CH and Sprint W-SE shipped with negative-rate era. NO is simpler (no negative handling needed):
- TE wrapper with source-drift guard
- Native connector (SDMX-JSON REST per Norges Bank DataAPI)
- M1 builder with cascade (standard)
- M2/M4 scaffolds
- Pipeline integration
- Retro

### Target change 2018
NO changed target 2.5% → 2.0% in 2018. Current target is 2%. Historical backtests pre-2018 should use 2.5% — document in bc_targets.yaml note for future reference.

### Oil-price coupling (Phase 2+ topic)
NOK/USD strongly coupled to Brent crude. Norges Bank policy decisions reflect oil-price environment. Unique country for SONAR regime analysis — noted in retro but NOT scope for this sprint.

### Isolated worktree workflow
Sprint X-NO operates entirely in `/home/macro/projects/sonar-wt-sprint-x`. Branch: `sprint-x-no-connector`.

### Sprint W-SE parallel
Runs in `sonar-wt-sprint-w`. Shared-file append zones + pipelines modification zones → rebase-expected post-merge. Alphabetical: W-SE merges first; X-NO rebases.

---

*End of Week 9 Sprint X-NO Norway connector brief. 6-8 commits. NO T1 shipped with TE-primary cascade.*
