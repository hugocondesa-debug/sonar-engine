# Week 9 Sprint V-CH — Switzerland SNB Connector + M1 CH (TE-primary Cascade)

**Target**: Ship Swiss National Bank connector + CH country enablement for M1 monetary. M2 T1 progression from 12 to 13 countries. TE-primary cascade per Sprint L/S-CA/T-AU canonical pattern. Unique regime: historic negative rates era.
**Priority**: HIGH (M2 T1 Completionist progression — 4 of 7 remaining T1 countries at Week 9 start)
**Budget**: 3-4h CC autonomous
**Commits**: ~6-8
**Base**: branch `sprint-v-ch-connector` (isolated worktree `/home/macro/projects/sonar-wt-sprint-v`)
**Concurrency**: Parallel to Sprint U-NZ New Zealand RBNZ connector in worktree `sonar-wt-sprint-u`. See §3.

---

## 1. Scope

In:
- `src/sonar/connectors/snb.py` — new Swiss National Bank connector
- **Cascade strategy per Sprint L/S-CA/T-AU canonical pattern (TE-primary default)**:
  1. **Primary: TE native CH Policy Rate / Conf bond yields** (daily, SNB-sourced via TE)
  2. **Secondary: SNB data portal** (public REST/CSV — https://data.snb.ch)
  3. **Tertiary: FRED OECD mirror** (monthly-lagged; last-resort with `CALIBRATION_STALE` flag)
- TE wrapper `fetch_ch_policy_rate` with HistoricalDataSymbol source-drift guard
- Core series empirical discovery:
  - CH Policy Rate (SNB Policy Rate, unified since 2019; was LIBOR target band pre-2019): probe Commit 1
  - CH 10Y Conf bond yield: TE `GSWISS10:IND` or similar (verify existing mapping)
  - CH CPI + unemployment: TE generic `fetch_indicator(country="CH", ...)` pattern
- Empirical SNB data portal probe (time-boxed 20 min)
  - URL: `https://data.snb.ch/en/`
  - API docs: may have REST endpoints + CSV downloads
- CH country entry in `docs/data_sources/country_tiers.yaml` (verify Tier 1 per ADR-0005)
- r* CH entry in `src/sonar/config/r_star_values.yaml` (~0-0.5% per SNB staff research — **low/near-zero reflecting Swiss safe-haven dynamics**)
- CH inflation target in `src/sonar/config/bc_targets.yaml` (0.01 midpoint per SNB 0-2% price stability definition)
- M1 CH builder via TE-primary cascade (M2/M4 scaffolds only; full wiring deferred CAL-CH-*)
- Pipeline integration `daily_monetary_indices.py --country CH`
- Cassette + `@pytest.mark.slow` live canary for TE + SNB paths
- Retrospective

Out:
- M2 CH live (output gap requires BFS / OECD EO / SNB EO — CAL-CH-M2-OUTPUT-GAP)
- M3 CH (requires persisted NSS forwards + expected-inflation for CH — CAL-CH-M3)
- M4 CH (FCI — requires VIX-CH, credit spreads CH, CHF NEER — CAL-CH-M4-FCI)
- CH ERP per-country live (deferred Phase 2+)
- CH CRP (BENCHMARK via spec; sovereign yield spread automatic; CH AAA)
- L3 credit indices CH (BIS coverage exists; depends on BIS Sprint AA fix)
- **Historical negative-rate era retrospective analysis** — deferred to Phase 2 research topic

---

## 2. Spec reference

Authoritative:
- `docs/data_sources/country_tiers.yaml` — CH should be Tier 1 per ADR-0005
- `docs/specs/indices/monetary/M1-effective-rates.md` §2
- `docs/specs/indices/monetary/M2-taylor-gaps.md` §2
- `docs/specs/conventions/patterns.md` — Pattern 4
- `docs/planning/retrospectives/week9-sprint-t-au-connector-report.md` — Sprint T-AU CSV pattern (RBA)
- `docs/planning/retrospectives/week9-sprint-s-ca-connector-report.md` — **Sprint S-CA BoC Valet JSON REST pattern (likely SNB equivalent)**
- `docs/planning/retrospectives/week8-sprint-l-boj-connector-report.md` — Sprint L JP scaffold pattern
- `src/sonar/connectors/boc.py` — Sprint S-CA JSON REST connector template (most likely SNB analog)
- `src/sonar/connectors/rba.py` — Sprint T-AU CSV connector alt template
- `src/sonar/connectors/te.py` — existing CH country mappings

**Pre-flight requirement**: Commit 1 CC:
1. Verify TE CH mappings: `"CH": "switzerland"` (indicator) + `"CH": "GSWISS10:IND"` (bonds) likely exist from Sprint 1
2. Probe TE CH Policy Rate empirically:
   ```bash
   set -a && source .env && set +a
   curl -s "https://api.tradingeconomics.com/historical/country/switzerland/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'
   ```
3. Document TE HistoricalDataSymbol for CH Policy Rate (probe finding)
4. Time-boxed 20 min SNB data portal probe:
   - `curl -sL "https://data.snb.ch/en/" | head -100` — explore portal
   - Try SNB Policy Rate via likely REST endpoint pattern
   - Check SNB data portal documentation for API format
   - **Apply UA-gate lesson if 403**: use `User-Agent: SONAR/2.0 (monetary-cascade; ...)` header
5. If SNB probe SUCCEEDS → implement SNB connector as secondary in cascade
6. If SNB probe FAILS → scaffold raising DataUnavailableError (gated; document for CAL-CH-SNB-PORTAL)
7. Read `boc.py` as template first (JSON REST most likely for SNB), fallback to `rba.py` (CSV) if SNB uses CSV
8. Verify CH in `country_tiers.yaml`; if missing, add as Tier 1

Document findings in Commit 1 body. **Note negative-rate historical context**: CH rates went negative 2015-2022 (-0.75% at trough). Ensure parser handles negative values correctly.

Existing assets:
- `TEConnector` generic + wrappers (8 shipped + AU from Day 2)
- FRED connector has `fetch_series` for any series ID
- `country_tiers.yaml` canonical (ISO alpha-2)
- `bc_targets.yaml` + `r_star_values.yaml` extended AU Sprint T-AU pattern

---

## 3. Concurrency — parallel protocol with Sprint U-NZ + ISOLATED WORKTREES

**Sprint V-CH operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-v`

Sprint U-NZ operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-u`

**Critical workflow**:
1. Sprint V-CH CC starts by `cd /home/macro/projects/sonar-wt-sprint-v`
2. All file operations happen in this worktree
3. Branch name: `sprint-v-ch-connector`
4. Pushes to `origin/sprint-v-ch-connector`
5. Final merge to main via fast-forward post-sprint-close (likely rebase needed if U-NZ merges first)

**File scope Sprint V-CH**:
- `src/sonar/connectors/snb.py` NEW
- `src/sonar/connectors/te.py` APPEND (new `fetch_ch_policy_rate` wrapper + CH-specific constants)
- `src/sonar/indices/monetary/builders.py` APPEND (add CH builders — `build_m1_ch_inputs`)
- `docs/data_sources/country_tiers.yaml` — verify/add CH entry (likely exists)
- `src/sonar/config/r_star_values.yaml` — add CH entry
- `src/sonar/config/bc_targets.yaml` — verify/add CH entry
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (add CH to MONETARY_SUPPORTED_COUNTRIES + CH country dispatch)
- Tests:
  - `tests/unit/test_connectors/test_snb.py` NEW
  - `tests/unit/test_connectors/test_te_indicator.py` APPEND (CH Policy Rate wrapper tests)
  - `tests/unit/test_indices/monetary/test_builders.py` APPEND (CH builder tests)
  - `tests/unit/test_pipelines/test_daily_monetary_indices.py` APPEND (CH country)
  - `tests/integration/test_daily_monetary_ch.py` NEW
  - `tests/fixtures/cassettes/snb/` + `tests/cassettes/connectors/te_ch_policy_rate_*.json`
- `docs/backlog/calibration-tasks.md` MODIFY (CAL-CH-* entries)
- `docs/planning/retrospectives/week9-sprint-v-ch-connector-report.md` NEW

**Sprint U-NZ scope** (for awareness, DO NOT TOUCH):
- `src/sonar/connectors/rbnz.py` NEW
- `src/sonar/connectors/te.py` APPEND (NZ wrapper — **concurrent append zone**)
- `src/sonar/indices/monetary/builders.py` APPEND (NZ builders — **concurrent append zone**)
- `src/sonar/config/*.yaml` (NZ entries — **concurrent modify zone**)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (NZ dispatch — **concurrent modify zone**)

**Potential conflict zones** (same as U-NZ §3, mirror):
- `te.py` — both sprints append wrappers (different functions, merge clean)
- `builders.py` — both append builders (different functions, merge clean)
- `daily_monetary_indices.py` — both add to MONETARY_SUPPORTED_COUNTRIES tuple (likely conflict, union-merge)
- `r_star_values.yaml` + `bc_targets.yaml` — both add country entries (merge clean if different keys)
- `calibration-tasks.md` — CAL entries (union-merge precedent)

**Rebase expected post-merge**. Sprint U-NZ merges first (alphabetical branch priority) → V-CH rebases.

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-sprint-v && git pull origin main --rebase`

**Push race**: normal `git push origin sprint-v-ch-connector`. Minor conflicts resolved via rebase.

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-v-ch-connector
git push origin main
```
(If rebase needed: `git rebase origin/main` in worktree → resolve → push --force-with-lease → merge.)

---

## 4. Commits

### Commit 1 — Pre-flight + TE CH Policy Rate wrapper

```
feat(connectors): TE fetch_ch_policy_rate wrapper + source-drift guard

Pre-flight: probe TE CH Policy Rate + verify SNB data portal reachability.

Expected probe (document findings commit body):
  set -a && source .env && set +a
  curl -s "https://api.tradingeconomics.com/historical/country/switzerland/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'

Document in commit body:
- Actual HistoricalDataSymbol returned (likely SNBPR, CHIR, or policy-rate type)
- Response format (date + value)
- Historical range (expected: daily; SNB Policy Rate unified 2019; prior LIBOR target band)
- **Negative values expected 2015-01..2022-09** (SNB negative-rate era)
- Latest value sanity check (should match current SNB Policy Rate ~0.0-1.75% as of 2024/2025)

SNB data portal probe (time-boxed 20 min):
  # Explore portal
  curl -sL "https://data.snb.ch/en/" | head -100

  # SNB has REST API at /api/cube/... (probe to confirm)
  curl -s "https://data.snb.ch/api/cube/zinssaetzelibor/data/json?dimSel=D0(1M)" | head -30
  # OR for SNB Policy Rate (unified 2019):
  # Explore https://data.snb.ch for canonical series ID

  # Fallback: CSV downloads
  # https://data.snb.ch/en/topics/ziredev

Document: reachability, response format (JSON vs CSV), negative-value handling.

Extend src/sonar/connectors/te.py:

CH_POLICY_RATE_EXPECTED_SYMBOL: Final = "[EMPIRICAL — probe result]"
CH_POLICY_RATE_INDICATOR: Final = "interest rate"

async def fetch_ch_policy_rate(
    self,
    start: date,
    end: date,
) -> list[TEIndicatorObservation]:
    """Fetch CH SNB Policy Rate from TE.

    TE sources from SNB directly — avoids FRED OECD mirror monthly lag.
    Handles historical negative values (2015-2022 era).
    Validates HistoricalDataSymbol matches expected per Sprint 3 Quick
    Wins source-drift discipline.

    Raises DataUnavailableError("source drift") if HistoricalDataSymbol
    != CH_POLICY_RATE_EXPECTED_SYMBOL.
    """
    obs = await self.fetch_indicator(
        country="CH",
        indicator=CH_POLICY_RATE_INDICATOR,
        start=start,
        end=end,
    )
    if obs and obs[0].historical_data_symbol != CH_POLICY_RATE_EXPECTED_SYMBOL:
        raise DataUnavailableError(...)
    return obs

Sanity check commit body:
  python -c "from sonar.connectors.te import TEConnector; c = TEConnector(api_key='x'); print(hasattr(c, 'fetch_ch_policy_rate'))"

Tests (tests/unit/test_connectors/test_te_indicator.py append):
- Unit: happy path mocked response (positive value)
- Unit: happy path with NEGATIVE value (e.g. -0.75% for 2020 data)
- Unit: HistoricalDataSymbol mismatch → DataUnavailableError
- Unit: empty response → empty list
- @pytest.mark.slow live canary: fetch CH Policy Rate 2024-12-01..31 →
  assert ≥ 1 obs, value ∈ [-1.0%, 3.0%] (wide range covering historic negative + recent positive)

Cassette: tests/cassettes/connectors/te_ch_policy_rate_2024_12.json

Coverage te.py additions ≥ 90%.
```

### Commit 2 — SNB data portal connector

```
feat(connectors): SNB data portal connector (public REST/CSV)

Create src/sonar/connectors/snb.py:

"""Swiss National Bank data portal connector.

Public data — no auth required. Handles Swiss macro time series
via SNB data portal (https://data.snb.ch).

Fallback cascade per Sprint L/S-CA/T-AU pattern: TE → SNB portal → FRED.

Empirical probe findings (Commit 1):
- Base URL: https://data.snb.ch/
- API path: /api/cube/{series_id}/data/{format}
- Format: JSON or CSV (probe-validated)
- Auth: public
- Key series (probe-validated Commit 1-2):
  - Policy Rate (unified 2019): [probe result]
  - Conf 10Y bond yield: [probe result]
  - CPI: [probe result]
"""

from __future__ import annotations
from datetime import date
from typing import Final

from sonar.connectors.base import BaseConnector
from sonar.connectors.exceptions import (
    DataUnavailableError,
    ConnectorError,
)

SNB_POLICY_RATE_SERIES: Final = "[probe-validated]"
SNB_CONF_10Y_SERIES: Final = "[probe-validated]"

class SNBConnector(BaseConnector):
    """SNB data portal — public REST/CSV."""

    BASE_URL = "https://data.snb.ch/api/cube/"
    CONNECTOR_ID = "snb"

    async def fetch_cube(
        self,
        cube_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[SNBObservation]:
        """Fetch data cube from SNB portal.

        Endpoint: /api/cube/{cube_id}/data/json (or csv)
        Returns list of observations filtered by date range.
        Handles negative values (2015-2022 era).
        Raises DataUnavailableError if cube unreachable.
        """
        url = f"{self.BASE_URL}{cube_id}/data/json"
        response = await self._get(url)
        # Parse JSON → date/value tuples (including negatives)
        ...

    async def fetch_policy_rate(
        self,
        start_date: date,
        end_date: date,
    ) -> list[SNBObservation]:
        """Convenience: SNB Policy Rate (unified 2019)."""
        return await self.fetch_cube(SNB_POLICY_RATE_SERIES, start_date, end_date)

Sanity check:
  python -c "from sonar.connectors.snb import SNBConnector; print('OK')"

Tests (tests/unit/test_connectors/test_snb.py):
- Unit: class instantiation + URL building
- Unit: fetch_cube success path (mocked JSON)
- Unit: fetch_cube NEGATIVE values handled (-0.75 example)
- Unit: fetch_cube 404 → DataUnavailableError
- Unit: fetch_cube empty observations → DataUnavailableError
- Unit: date filter behavior
- Unit: disk cache behavior
- @pytest.mark.slow live canary: probe Policy Rate recent;
  assert ≥ 1 obs, values reasonable

Coverage snb.py ≥ 85%.

Cassette: tests/fixtures/cassettes/snb/policy_rate_2024_12.json

Note: if SNB portal probe uses CSV instead of JSON, adapt accordingly
(follow rba.py pattern). If portal REST reachability fails, scaffold with
DataUnavailableError + open CAL-CH-SNB-PORTAL.
```

### Commit 3 — CH Tier 1 config + r*/bc_targets YAML entries

```
feat(config): CH Tier 1 enabled + monetary YAML entries

1. Verify docs/data_sources/country_tiers.yaml contains CH as Tier 1.
   Expected: already present.
   If missing, add:
   - iso_code: CH
     tier: 1
     monetary: enabled
     description: "Switzerland — Tier 1 per ADR-0005"

2. Update src/sonar/config/r_star_values.yaml — add CH entry:
   CH:
     value: 0.0025       # SNB staff research ~0-0.5% (midpoint 0.25%)
     proxy: true
     source: "SNB Economic Studies / Quarterly Bulletin — neutral rate ~2024"
     timestamp: "2024-12-01"
     note: "CH historically safe-haven; low r* reflects structural factors"

   Loader auto-emits R_STAR_PROXY flag.

3. Update src/sonar/config/bc_targets.yaml — add CH entry:
   CH:
     target: 0.01        # SNB 0-2% price stability midpoint
     source: "SNB price stability definition (since 1999)"
     note: "SNB defines price stability as CPI <2% (no explicit point target); midpoint 1% used"

   Note: SNB uses 0-2% band (no explicit numeric target like 2%);
   1% midpoint chosen for Taylor-rule computation.

Unit tests:
- Loader reads CH r* with proxy=true
- Loader handles LOW r* value (0.25% vs typical 1-2.5%)
- bc_targets loader reads CH 1% midpoint target
- country_tiers_parser includes CH in T1 list

Coverage maintained.
```

### Commit 4 — M1 CH builder with TE-primary cascade

```
feat(indices): M1 CH builder TE-primary cascade

Add build_m1_ch_inputs to src/sonar/indices/monetary/builders.py:

async def build_m1_ch_inputs(
    fred: FredConnector,
    te: TEConnector,
    observation_date: date,
    *,
    snb: SNBConnector | None = None,
    history_years: int = 15,
) -> M1Inputs:
    """Build M1 CH inputs via TE primary cascade.

    Cascade priority (per Sprint I-patch/Sprint L/S-CA/T-AU canonical pattern):
    1. TE primary — CH_POLICY_RATE_TE_PRIMARY flag (daily SNB-sourced)
    2. SNB portal native — CH_POLICY_RATE_SNB_NATIVE flag (REST JSON)
    3. FRED OECD mirror — CH_POLICY_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE

    r* via r_star_values.yaml (R_STAR_PROXY flag, LOW value ~0.25%).
    Inflation target via bc_targets.yaml (1% SNB midpoint of 0-2% band).

    Handles negative rate era (2015-2022) via value preservation
    (no filtering of negatives).
    """
    flags = []
    obs = None

    # Primary: TE
    if te:
        try:
            obs = await te.fetch_ch_policy_rate(start, end)
            if obs:
                flags.append("CH_POLICY_RATE_TE_PRIMARY")
                # Check for negative-rate era coverage
                if any(o.value < 0 for o in obs):
                    flags.append("CH_NEGATIVE_RATE_ERA_DATA")
        except (DataUnavailableError, ConnectorError):
            flags.append("CH_POLICY_RATE_TE_UNAVAILABLE")

    # Secondary: SNB portal
    if not obs and snb:
        try:
            snb_obs = await snb.fetch_policy_rate(start, end)
            if snb_obs:
                obs = [_DatedValue(...) for o in snb_obs]
                flags.append("CH_POLICY_RATE_SNB_NATIVE")
        except (DataUnavailableError, ConnectorError):
            flags.append("CH_POLICY_RATE_SNB_UNAVAILABLE")

    # Tertiary: FRED OECD mirror (last-resort, monthly stale)
    if not obs:
        fred_obs = await fred.fetch_series(FRED_CH_POLICY_RATE_SERIES, start, end)
        if fred_obs:
            obs = [_DatedValue(...) for o in fred_obs]
            flags.extend([
                "CH_POLICY_RATE_FRED_FALLBACK_STALE",
                "CALIBRATION_STALE",
            ])

    if not obs:
        raise ValueError("CH Policy Rate unavailable from TE, SNB, FRED")

    # r* from YAML (low value expected)
    r_star, r_star_is_proxy = resolve_r_star("CH")
    if r_star_is_proxy:
        flags.append("R_STAR_PROXY")

    # Build M1Inputs ...

Constants:
FRED_CH_POLICY_RATE_SERIES: str = "IRSTCI01CHM156N"  # OECD MEI CH short-rate
FRED_CH_BOND_10Y_SERIES: str = "IRLTLT01CHM156N"  # OECD MEI CH long-rate

Expose in __all__:
    "build_m1_ch_inputs",

Tests:
- Unit: TE primary success → CH_POLICY_RATE_TE_PRIMARY
- Unit: NEGATIVE rate historical data → CH_NEGATIVE_RATE_ERA_DATA flag
- Unit: TE fails, SNB succeeds → CH_POLICY_RATE_SNB_NATIVE
- Unit: TE + SNB fail → FRED fallback → CALIBRATION_STALE
- Unit: all fail → ValueError
- Unit: r* loaded CH with proxy flag (LOW value 0.25%)
- Unit: bc_targets CH 1% loaded

Coverage build_m1_ch_inputs ≥ 95%.
```

### Commit 5 — Pipeline integration daily_monetary_indices CH

```
feat(pipelines): daily_monetary_indices CH country support

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Add CH to MONETARY_SUPPORTED_COUNTRIES:
   MONETARY_SUPPORTED_COUNTRIES = ("US", "EA", "GB", "UK", "JP", "CA", "AU", "NZ", "CH")
   # CH follows Sprint T-AU AU pattern
   # Note: NZ addition may conflict via Sprint U-NZ parallel — rebase resolution

2. CH country branch routes to build_m1_ch_inputs
3. M2/M3/M4 CH: raise NotImplementedError gracefully
4. Connector lifecycle: SNB connector added to connectors_to_close

Verify --country CH and --all-t1 (includes CH) work.

Tests:
- Unit: pipeline invokes CH builders when country=CH
- Unit: CH M2/M3/M4 graceful skip
- Unit: connector_to_close includes SNB instance

Integration smoke @slow:
tests/integration/test_daily_monetary_ch.py:

@pytest.mark.slow
def test_daily_monetary_ch_te_primary():
    """Full pipeline CH 2024-12-31 with TE primary cascade.

    Expected:
    - M1 CH row persists
    - CH_POLICY_RATE_TE_PRIMARY flag present
    - R_STAR_PROXY flag present
    - policy_rate_pct daily-fresh"""

@pytest.mark.slow
def test_daily_monetary_ch_snb_native_fallback():
    """TE unavailable, SNB portal succeeds. Expected CH_POLICY_RATE_SNB_NATIVE flag."""

@pytest.mark.slow
def test_daily_monetary_ch_negative_rate_historical():
    """Fetch CH Policy Rate 2020-01..12 (negative era).

    Expected:
    - Values < 0 preserved (no filtering)
    - CH_NEGATIVE_RATE_ERA_DATA flag present"""

Wall-clock ≤ 20s combined.

Coverage maintained.
```

### Commit 6 — M2/M4 CH scaffolds

```
feat(indices): M2 + M4 CH scaffolds (wire-ready, raise pending connectors)

Per Sprint L JP / Sprint S-CA CA / Sprint T-AU AU / Sprint U-NZ pattern —
M2/M4 CH builders are scaffolds raising InsufficientDataError.

async def build_m2_ch_inputs(...) -> M2Inputs:
    """M2 CH scaffold — output gap needs BFS or OECD EO."""
    raise InsufficientDataError(
        "CH M2 requires output_gap; pending BFS/OECD EO connector. "
        "CAL-CH-M2-OUTPUT-GAP tracking resolution."
    )

async def build_m4_ch_inputs(...) -> M4Inputs:
    """M4 CH scaffold — FCI components need CHF-specific VIX, credit spreads, NEER."""
    raise InsufficientDataError(
        "CH M4 requires VIX-CH / credit-spread-CH / NEER-CHF; all deferred. "
        "CAL-CH-M4-FCI tracking full wire-up."
    )

Tests:
- Unit: build_m2_ch_inputs raises InsufficientDataError
- Unit: build_m4_ch_inputs raises InsufficientDataError
- Unit: error message references correct CAL items

Coverage maintained.
```

### Commit 7 — Retrospective + CAL items opened

```
docs(planning+backlog): Week 9 Sprint V-CH SNB connector retrospective

File: docs/planning/retrospectives/week9-sprint-v-ch-connector-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- Empirical findings:
  - TE CH Policy Rate HistoricalDataSymbol: [probe result]
  - SNB data portal reachability: [success/issues/partial] — REST vs CSV
  - FRED OECD CH mirror series validated
  - Negative-rate era handling confirmed (2015-2022 values preserved)
- Coverage delta
- Live canary outcomes (including negative-rate historical canary)
- HALT triggers fired / not fired
- Deviations from brief
- M2 T1 progression: 12 → 13 countries
- CH monetary indices operational:
  - M1: live via TE cascade (SNB portal if probe succeeded)
  - M2: scaffold (CAL-CH-M2-OUTPUT-GAP)
  - M3: deferred (CAL-CH-M3)
  - M4: scaffold (CAL-CH-M4-FCI)
- Pattern validation:
  - TE-primary cascade continues canonical (6th country)
  - SNB portal pattern: [REST JSON like BoC | CSV like RBA — document which]
  - Negative-rate era support validated — important for historical regime analysis
- Isolated worktree: zero collision incidents with Sprint U-NZ parallel
- Merge strategy: branch sprint-v-ch-connector → main (rebase expected post U-NZ merge)
- New CAL items opened:
  - CAL-CH-M2-OUTPUT-GAP
  - CAL-CH-M3
  - CAL-CH-M4-FCI
  - CAL-CH-SNB-PORTAL (if probe failed)
  - CAL-CH-NEGATIVE-RATE-ANALYSIS (deferred Phase 2 research — historical regime)

Open CAL-CH-* items formally in docs/backlog/calibration-tasks.md.

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git merge --ff-only sprint-v-ch-connector
  git push origin main
  # If rebase needed (Sprint U-NZ merged first):
  # cd /home/macro/projects/sonar-wt-sprint-v
  # git fetch origin && git rebase origin/main
  # Resolve conflicts (calibration-tasks.md + pipelines + YAMLs)
  # git push --force-with-lease
  # Then merge
```

---

## 5. HALT triggers (atomic)

0. **TE CH Policy Rate empirical probe fails** — if TE returns no CH data or unexpected format, HALT + surface. Alternative: FRED primary + accept monthly-stale with explicit operator warning.
1. **HistoricalDataSymbol mismatch** — if TE returns different symbol than probe found, do NOT assume benign. HALT.
2. **SNB portal unreachable** — possible; apply UA lesson. If still unreachable, scaffold with DataUnavailableError + open CAL-CH-SNB-PORTAL. Not a HALT.
3. **SNB portal API schema changed** — if REST endpoint pattern differs from typical /api/cube/ path, adapt or scope narrow.
4. **Negative values causing parser errors** — if any logic assumes positive rates (e.g. log transforms), HALT + fix for negative-rate-era compatibility.
5. **CH in country_tiers.yaml Tier mismatch** — if CH marked Tier 2+ instead of Tier 1, HALT + verify against ADR-0005.
6. **r* CH value uncertainty** — low/zero is correct for Swiss safe-haven; use 0.25% midpoint + R_STAR_PROXY flag.
7. **bc_targets CH ambiguity** — SNB uses 0-2% band not point target; midpoint 1% chosen per spec convention. Document.
8. **M2/M4 scaffolds pattern** — per precedent, raise InsufficientDataError. Verify pattern replication.
9. **TE rate limits** during live canaries — tenacity handles; document in retro if persistent.
10. **Coverage regression > 3pp** → HALT.
11. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
12. **Concurrent Sprint U-NZ touches files in Sprint V scope** (likely minor conflicts in te.py/builders.py/pipelines/daily_monetary_indices.py/YAMLs/backlog) → reconcile via rebase post-merge.

---

## 6. Acceptance

### Global sprint-end
- [ ] 6-8 commits pushed to branch `sprint-v-ch-connector`
- [ ] `src/sonar/connectors/snb.py` shipped + tested (even if SNB probe partial)
- [ ] `fetch_ch_policy_rate` TE wrapper + source-drift guard shipped
- [ ] TE CH HistoricalDataSymbol validated + documented
- [ ] SNB portal reachability documented (probe result)
- [ ] Negative-rate era handling validated (2015-2022 values preserved)
- [ ] CH Tier 1 in country_tiers.yaml
- [ ] r_star_values.yaml CH entry added (with proxy: true, LOW value)
- [ ] bc_targets.yaml CH entry present (1% midpoint)
- [ ] `build_m1_ch_inputs` cascade operational with CH_NEGATIVE_RATE_ERA_DATA flag
- [ ] M2 + M4 CH scaffolds shipped (raise InsufficientDataError)
- [ ] `daily_monetary_indices.py --country CH` runs end-to-end
- [ ] Live canaries PASS: TE CH Policy Rate + CH monetary pipeline + historical negative-rate test
- [ ] Coverage snb.py ≥ 85%, builders.py CH path ≥ 95%
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week9-sprint-v-ch-connector-report.md`

**Final tmux echo**:
```
SPRINT V-CH SWITZERLAND CONNECTOR DONE: N commits on branch sprint-v-ch-connector
TE HistoricalDataSymbol CH validated: [symbol]
SNB portal reachability: [success / issues / partial] — [REST JSON / CSV]
Negative-rate era support: VALIDATED (2015-2022 data preserved)
CH monetary: M1 (cascade), M2/M4 (scaffolds), M3 (deferred)
M2 T1 progression: 12 → 13 countries
HALT triggers: [list or "none"]
Merge: git checkout main && git merge --ff-only sprint-v-ch-connector
   (rebase may be required if Sprint U-NZ merged first)
Artifact: docs/planning/retrospectives/week9-sprint-v-ch-connector-report.md
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

### TE primary canonical (Week 8-9 lesson, 6th consecutive country)
All country expansion defaults to TE primary → native override → FRED last-resort. Pattern stable.

### SNB data portal likely JSON REST (BoC Valet analog)
SNB `data.snb.ch` likely serves REST JSON similar to Bank of Canada Valet. If so, Sprint S-CA boc.py is closest template. If CSV, use rba.py.

### Negative-rate era context (unique to CH)
Switzerland had negative rates 2015-01..2022-09. This is important historical regime data. Parser must preserve negative values + flag via `CH_NEGATIVE_RATE_ERA_DATA`. Phase 2 research topic: historical SNB negative-rate regime analysis.

### Pattern replication discipline (6th iteration)
Sprint T-AU AU shipped earlier today. Sprint U-NZ concurrent today. This sprint mirrors closely, with CH-specific adjustments:
- r* LOW (0.25% vs typical 1-2.5%)
- Inflation target midpoint of 0-2% band (not explicit point target)
- Negative-rate era flag

### Pattern evolution — band target
SNB uses inflation band (0-2%) not point target. Convention: use midpoint (1%). Document explicitly in bc_targets.yaml comment.

### Isolated worktree workflow
Sprint V-CH operates entirely in `/home/macro/projects/sonar-wt-sprint-v`. Branch: `sprint-v-ch-connector`.

### Sprint U-NZ parallel
Runs in `sonar-wt-sprint-u`. Shared-file append zones + pipelines modification zones → rebase-expected post-merge. First merge wins (alphabetical: U-NZ first); V-CH rebases.

---

*End of Week 9 Sprint V-CH Switzerland connector brief. 6-8 commits. CH T1 shipped with TE-primary cascade. Negative-rate era support validated.*
