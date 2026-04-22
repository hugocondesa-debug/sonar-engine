# Week 9 Sprint T-AU — Australia RBA Connector + M1 AU (TE-primary Cascade)

**Target**: Ship Reserve Bank of Australia connector + AU country enablement for M1 monetary. M2 T1 progression from 10 to 11 countries. TE-primary cascade per Sprint I-patch/Sprint L/Sprint S-CA canonical pattern.
**Priority**: HIGH (M2 T1 Completionist progression — 2 of 7 remaining T1 countries)
**Budget**: 3-4h CC autonomous
**Commits**: ~6-8
**Base**: branch `sprint-t-au-connector` (isolated worktree `/home/macro/projects/sonar-wt-sprint-t`)
**Concurrency**: Parallel to Sprint AA BIS v2 migration in worktree `sonar-wt-sprint-aa`. See §3.

---

## 1. Scope

In:
- `src/sonar/connectors/rba.py` — new Reserve Bank of Australia connector
- **Cascade strategy per Sprint L/S-CA canonical pattern (TE-primary default)**:
  1. **Primary: TE native AU Cash Rate / Commonwealth bond yields** (daily, RBA-sourced via TE)
  2. **Secondary: RBA statistical tables CSV/XML** (public, well-documented)
  3. **Tertiary: FRED OECD mirror** (monthly-lagged; last-resort with `CALIBRATION_STALE` flag)
- TE wrapper `fetch_au_cash_rate` with HistoricalDataSymbol source-drift guard
- Core series empirical discovery:
  - AU Cash Rate target: probe Commit 1 (likely `IR`, `RBACSHIR`, or similar)
  - AU 10Y Commonwealth bond yield: TE `GACGB10:IND` (verify existing mapping)
  - AU CPI + unemployment: TE generic `fetch_indicator(country="AU", ...)` pattern
- Empirical RBA statistical tables probe (time-boxed 20 min)
- AU country entry in `docs/data_sources/country_tiers.yaml` (verify Tier 1 per ADR-0005)
- r* AU entry in `src/sonar/config/r_star_values.yaml` (~1.0-1.5% per RBA staff research)
- AU inflation target in `src/sonar/config/bc_targets.yaml` (0.025 midpoint per RBA 2-3% target band)
- M1 AU builder via TE-primary cascade (M2/M4 scaffolds only; full wiring deferred CAL-AU-*)
- Pipeline integration `daily_monetary_indices.py --country AU`
- Cassette + `@pytest.mark.slow` live canary for TE + RBA paths
- Retrospective

Out:
- M2 AU live (output gap requires ABS / RBA output gap estimate OR OECD EO connector — CAL-AU-M2-OUTPUT-GAP)
- M3 AU (requires persisted NSS forwards + expected-inflation for AU — CAL-AU-M3)
- M4 AU (FCI — requires VIX-AU, credit spreads AU, AUD NEER — CAL-AU-M4-FCI)
- AU ERP per-country live (deferred Phase 2+)
- AU CRP (BENCHMARK via spec; sovereign yield spread automatic)
- AU rating-spread (AAA baseline sovereign)
- L3 economic indices AU (E1/E2/E3/E4 — separate sprint)
- L3 credit indices AU (BIS coverage existing via Sprint 2b — depends on Sprint AA BIS fix)
- L3 financial indices AU (F1-F4 US proxies; Phase 2+)

---

## 2. Spec reference

Authoritative:
- `docs/data_sources/country_tiers.yaml` — AU should be Tier 1 per ADR-0005
- `docs/specs/indices/monetary/M1-effective-rates.md` §2 — monetary inputs per country
- `docs/specs/indices/monetary/M2-taylor-gaps.md` §2 — r*, policy rate, inflation inputs
- `docs/specs/conventions/patterns.md` — Pattern 4 (Aggregator-primary with native-override)
- `docs/planning/retrospectives/week9-sprint-s-ca-connector-report.md` — **Sprint S-CA most recent pattern**
- `docs/planning/retrospectives/week8-sprint-l-boj-connector-report.md` — **Sprint L JP pattern**
- SESSION_CONTEXT §Critical technical reference — TE HistoricalDataSymbol validated list
- `src/sonar/connectors/boc.py` — Sprint S-CA native connector pattern template
- `src/sonar/connectors/boj.py` — Sprint L alternative pattern
- `src/sonar/connectors/te.py` — existing AU country mappings

**Pre-flight requirement**: Commit 1 CC:
1. Verify TE AU mappings: `"AU": "australia"` (indicator) + `"AU": "GACGB10:IND"` (bonds) already exist from Sprint 1
2. Probe TE AU Cash Rate empirically:
   ```bash
   set -a && source .env && set +a
   curl -s "https://api.tradingeconomics.com/historical/country/australia/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'
   ```
3. Document TE HistoricalDataSymbol for AU Cash Rate (probe finding)
4. Time-boxed 20 min RBA statistical tables probe:
   - URL pattern: `https://www.rba.gov.au/statistics/tables/` (public)
   - Tables catalog: `https://www.rba.gov.au/statistics/tables/catalogue.html`
   - Cash rate historical: table F01 or F01.1
   - 10Y bond yield: table F02
   - Try CSV/XLS format for programmatic access
5. If RBA probe SUCCEEDS → implement RBA connector as secondary in cascade
6. If RBA probe FAILS → scaffold with raise DataUnavailableError (gated, similar to BoJ TSD pattern)
7. Read `boc.py` as template (Sprint S-CA most recent pattern, matched Valet pattern)
8. Verify AU in `country_tiers.yaml`; if missing, add as Tier 1

Document findings in Commit 1 body.

Existing assets:
- `TEConnector` generic + wrappers (7 from Sprint 1 + UK/GB Bank Rate Sprint I-patch + JP Bank Rate Sprint L + CA Bank Rate Sprint S-CA)
- FRED connector has `fetch_series` for any series ID
- `country_tiers.yaml` canonical (ISO alpha-2 convention post-Sprint O)
- `bc_targets.yaml` + `r_star_values.yaml` extended Sprint S-CA pattern

---

## 3. Concurrency — parallel protocol with Sprint AA + ISOLATED WORKTREES

**Sprint T-AU operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-t`

Sprint AA operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-aa`

**Critical workflow**:
1. Sprint T-AU CC starts by `cd /home/macro/projects/sonar-wt-sprint-t`
2. All file operations happen in this worktree
3. Branch name: `sprint-t-au-connector`
4. Pushes to `origin/sprint-t-au-connector`
5. Final merge to main via fast-forward post-sprint-close

**File scope Sprint T-AU**:
- `src/sonar/connectors/rba.py` NEW
- `src/sonar/connectors/te.py` APPEND (new `fetch_au_cash_rate` wrapper + AU-specific constants)
- `src/sonar/indices/monetary/builders.py` APPEND (add AU builders — `build_m1_au_inputs`)
- `docs/data_sources/country_tiers.yaml` — verify/add AU entry (likely exists)
- `src/sonar/config/r_star_values.yaml` — add AU entry
- `src/sonar/config/bc_targets.yaml` — verify/add AU entry
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (add AU to MONETARY_SUPPORTED_COUNTRIES + AU country dispatch)
- Tests:
  - `tests/unit/test_connectors/test_rba.py` NEW
  - `tests/unit/test_connectors/test_te_indicator.py` APPEND (AU Cash Rate wrapper tests)
  - `tests/unit/test_indices/monetary/test_builders.py` APPEND (AU builder tests)
  - `tests/unit/test_pipelines/test_daily_monetary_indices.py` APPEND (AU country)
  - `tests/integration/test_daily_monetary_au.py` NEW
  - `tests/fixtures/cassettes/rba/` + `tests/cassettes/connectors/te_au_cash_rate_*.json`
- `docs/planning/retrospectives/week9-sprint-t-au-connector-report.md` NEW

**Sprint AA scope** (for awareness, DO NOT TOUCH):
- `src/sonar/connectors/bis.py` — Sprint AA modify
- `tests/integration/test_bis_ingestion.py` — Sprint AA modify
- `tests/fixtures/cassettes/bis/*` — Sprint AA cassette refresh
- BIS-related systemd timer ops — Sprint AA owner

**Zero file overlap confirmed**. Different domains entirely.

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-sprint-t && git pull origin main --rebase`

**Push race**: normal `git push origin sprint-t-au-connector`. Zero collisions expected.

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-t-au-connector
git push origin main
```
Fast-forward expected (or rebase if Sprint AA merged first — backlog.md conflict likely).

---

## 4. Commits

### Commit 1 — Pre-flight + TE AU Cash Rate wrapper

```
feat(connectors): TE fetch_au_cash_rate wrapper + source-drift guard

Pre-flight: probe TE AU Cash Rate + verify RBA statistical tables reachability.

Expected probe (document findings commit body):
  set -a && source .env && set +a
  curl -s "https://api.tradingeconomics.com/historical/country/australia/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'

Document in commit body:
- Actual HistoricalDataSymbol returned (likely RBATCTR, AUCRR, or IR-type)
- Response format (date + value)
- Historical range (expected: daily since RBA cash rate inception mid-1990s)
- Latest value sanity check (should match current RBA cash rate ~3.35-4.35% range as of late 2024/2025)

RBA statistical tables probe (time-boxed 20 min):
  # Explore tables catalogue
  curl -s "https://www.rba.gov.au/statistics/tables/catalogue.html" | head -100
  # Try cash rate table F01
  curl -s "https://www.rba.gov.au/statistics/tables/csv/f1-data.csv" -o /tmp/rba_f1.csv
  head -10 /tmp/rba_f1.csv
  # Try 10Y bond yield F02
  curl -s "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv" -o /tmp/rba_f2.csv
  head -10 /tmp/rba_f2.csv

Document: reachability, response format (CSV headers), series stability

Extend src/sonar/connectors/te.py:

AU_CASH_RATE_EXPECTED_SYMBOL: Final = "[EMPIRICAL — probe result]"
AU_CASH_RATE_INDICATOR: Final = "interest rate"

async def fetch_au_cash_rate(
    self,
    start: date,
    end: date,
) -> list[TEIndicatorObservation]:
    """Fetch AU Cash Rate from TE.

    TE sources from RBA directly — avoids FRED OECD mirror monthly lag.
    Validates HistoricalDataSymbol matches expected per Sprint 3 Quick
    Wins source-drift discipline.

    Raises DataUnavailableError("source drift") if HistoricalDataSymbol
    != AU_CASH_RATE_EXPECTED_SYMBOL.
    """
    obs = await self.fetch_indicator(
        country="AU",
        indicator=AU_CASH_RATE_INDICATOR,
        start=start,
        end=end,
    )
    if obs and obs[0].historical_data_symbol != AU_CASH_RATE_EXPECTED_SYMBOL:
        raise DataUnavailableError(...)
    return obs

Sanity check commit body:
  python -c "from sonar.connectors.te import TEConnector; c = TEConnector(api_key='x'); print(hasattr(c, 'fetch_au_cash_rate'))"

Tests (tests/unit/test_connectors/test_te_indicator.py append):
- Unit: happy path mocked response
- Unit: HistoricalDataSymbol mismatch → DataUnavailableError
- Unit: empty response → empty list
- @pytest.mark.slow live canary: fetch AU Cash Rate 2024-12-01..31 →
  assert ≥ 1 obs, value ∈ [0.10%, 7.0%] (reasonable range for recent RBA cycles)

Cassette: tests/cassettes/connectors/te_au_cash_rate_2024_12.json

Coverage te.py additions ≥ 90%.
```

### Commit 2 — RBA statistical tables connector

```
feat(connectors): RBA statistical tables CSV connector (public, unauthenticated)

Create src/sonar/connectors/rba.py:

"""Reserve Bank of Australia statistical tables connector.

Public data — no auth required. Handles Australian macro time series
via RBA publishing CSVs.
Fallback cascade per Sprint L/S-CA pattern: TE → RBA tables → FRED.

Empirical probe findings (Commit 1):
- Base URL: https://www.rba.gov.au/statistics/tables/
- Format: CSV (published weekly/monthly)
- Auth: public
- Key tables (probe-validated Commit 1-2):
  - F01 / F01.1: Cash rate target historical
  - F02: Commonwealth Government bond yields
  - G01: CPI headline
"""

from __future__ import annotations
from datetime import date
from typing import Final
import csv
from io import StringIO

from sonar.connectors.base import BaseConnector
from sonar.connectors.exceptions import (
    DataUnavailableError,
    ConnectorError,
)

RBA_CASH_RATE_TABLE: Final = "f1-data.csv"
RBA_10Y_BOND_YIELD_TABLE: Final = "f2-data.csv"
RBA_CPI_TABLE: Final = "g1-data.csv"

class RBAConnector(BaseConnector):
    """RBA statistical tables — public, no auth."""

    BASE_URL = "https://www.rba.gov.au/statistics/tables/csv/"
    CONNECTOR_ID = "rba"

    async def fetch_table(
        self,
        table_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[RBAObservation]:
        """Fetch statistical table from RBA.

        Endpoint: /statistics/tables/csv/{table_id}
        Returns list of observations filtered by date range.
        Raises DataUnavailableError if table unreachable.
        """
        url = f"{self.BASE_URL}{table_id}"
        response = await self._get(url)
        # Parse CSV rows → date/value tuples
        ...

    async def fetch_cash_rate(
        self,
        start_date: date,
        end_date: date,
    ) -> list[RBAObservation]:
        """Convenience: cash rate target."""
        return await self.fetch_table(RBA_CASH_RATE_TABLE, start_date, end_date)

    async def fetch_10y_bond_yield(
        self,
        start_date: date,
        end_date: date,
    ) -> list[RBAObservation]:
        """Convenience: 10Y Commonwealth Government bond yield."""
        return await self.fetch_table(RBA_10Y_BOND_YIELD_TABLE, start_date, end_date)

Sanity check:
  python -c "from sonar.connectors.rba import RBAConnector; print('OK')"

Tests (tests/unit/test_connectors/test_rba.py):
- Unit: class instantiation + URL building
- Unit: fetch_table success path (mocked CSV response)
- Unit: fetch_table 404 → DataUnavailableError
- Unit: fetch_table malformed CSV → DataUnavailableError
- Unit: date filter behavior
- Unit: disk cache behavior
- @pytest.mark.slow live canary: probe RBA_CASH_RATE_TABLE recent;
  assert ≥ 1 obs, values reasonable

Coverage rba.py ≥ 85%.

Cassette: tests/fixtures/cassettes/rba/cash_rate_2024_12.csv

Note: if RBA CSV structure requires significant per-table custom parsing,
implement minimal parser for F01 only; defer F02/G01 to CAL-AU-*.
```

### Commit 3 — AU Tier 1 config + r*/bc_targets YAML entries

```
feat(config): AU Tier 1 enabled + monetary YAML entries

1. Verify docs/data_sources/country_tiers.yaml contains AU as Tier 1.
   Expected: already present from Sprint 2b (BIS credit coverage).
   If missing, add:
   - iso_code: AU
     tier: 1
     monetary: enabled
     description: "Australia — Tier 1 per ADR-0005"

2. Update src/sonar/config/r_star_values.yaml — add AU entry:
   AU:
     value: 0.0125       # RBA staff research estimate ~1.0-1.5% (midpoint 1.25%)
     proxy: true
     source: "RBA Bulletin / Economic Research articles ~2024"
     timestamp: "2024-12-01"

   Loader auto-emits R_STAR_PROXY flag.

3. Update src/sonar/config/bc_targets.yaml — add AU entry:
   AU:
     target: 0.025        # RBA target midpoint of 2-3% band
     source: "RBA Statement on the Conduct of Monetary Policy (1996, revised)"

   Note: RBA uses 2-3% band rather than point target; midpoint 2.5% used.

Unit tests:
- Loader reads AU r* with proxy=true
- bc_targets loader reads AU 2.5% target
- country_tiers_parser includes AU in T1 list (likely already passes)

Coverage maintained.
```

### Commit 4 — M1 AU builder with TE-primary cascade

```
feat(indices): M1 AU builder TE-primary cascade

Add build_m1_au_inputs to src/sonar/indices/monetary/builders.py:

async def build_m1_au_inputs(
    fred: FredConnector,
    te: TEConnector,
    observation_date: date,
    *,
    rba: RBAConnector | None = None,
    history_years: int = 15,
) -> M1Inputs:
    """Build M1 AU inputs via TE primary cascade.

    Cascade priority (per Sprint I-patch/Sprint L/S-CA canonical pattern):
    1. TE primary — AU_CASH_RATE_TE_PRIMARY flag (daily RBA-sourced)
    2. RBA tables native — AU_CASH_RATE_RBA_NATIVE flag (F01 CSV)
    3. FRED OECD mirror — AU_CASH_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE

    r* via r_star_values.yaml (R_STAR_PROXY flag).
    Inflation target via bc_targets.yaml (2.5% RBA midpoint).
    """
    # Pseudocode mirroring Sprint S-CA CA cascade
    flags = []
    obs = None

    # Primary: TE
    if te:
        try:
            obs = await te.fetch_au_cash_rate(start, end)
            if obs:
                flags.append("AU_CASH_RATE_TE_PRIMARY")
        except (DataUnavailableError, ConnectorError):
            flags.append("AU_CASH_RATE_TE_UNAVAILABLE")

    # Secondary: RBA tables
    if not obs and rba:
        try:
            rba_obs = await rba.fetch_cash_rate(start, end)
            if rba_obs:
                obs = [_DatedValue(...) for o in rba_obs]
                flags.append("AU_CASH_RATE_RBA_NATIVE")
        except (DataUnavailableError, ConnectorError):
            flags.append("AU_CASH_RATE_RBA_UNAVAILABLE")

    # Tertiary: FRED OECD mirror (last-resort, monthly stale)
    if not obs:
        fred_obs = await fred.fetch_series(FRED_AU_CASH_RATE_SERIES, start, end)
        if fred_obs:
            obs = [_DatedValue(...) for o in fred_obs]
            flags.extend([
                "AU_CASH_RATE_FRED_FALLBACK_STALE",
                "CALIBRATION_STALE",
            ])

    if not obs:
        raise ValueError("AU Cash Rate unavailable from TE, RBA, FRED")

    # r* from YAML
    r_star, r_star_is_proxy = resolve_r_star("AU")
    if r_star_is_proxy:
        flags.append("R_STAR_PROXY")

    # Build M1Inputs ...

Constants:
FRED_AU_CASH_RATE_SERIES: str = "IRSTCI01AUM156N"  # OECD MEI AU short-rate
FRED_AU_BOND_10Y_SERIES: str = "IRLTLT01AUM156N"    # OECD MEI AU long-rate

Expose in __all__:
    "build_m1_au_inputs",

Tests:
- Unit: TE primary success → AU_CASH_RATE_TE_PRIMARY
- Unit: TE fails, RBA succeeds → AU_CASH_RATE_RBA_NATIVE
- Unit: TE + RBA fail → FRED fallback → CALIBRATION_STALE
- Unit: all fail → ValueError
- Unit: r* loaded AU with proxy flag
- Unit: bc_targets AU 2.5% loaded

Coverage build_m1_au_inputs ≥ 95%.
```

### Commit 5 — Pipeline integration daily_monetary_indices AU

```
feat(pipelines): daily_monetary_indices AU country support

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Add AU to MONETARY_SUPPORTED_COUNTRIES:
   MONETARY_SUPPORTED_COUNTRIES = ("US", "EA", "GB", "UK", "JP", "CA", "AU")
   # AU follows Sprint S-CA CA pattern

2. AU country branch routes to build_m1_au_inputs
3. M2/M3/M4 AU: raise NotImplementedError gracefully (pattern per Sprint L JP / S-CA CA)
4. Connector lifecycle: RBA connector added to connectors_to_close (if ingested)

Verify --country AU and --all-t1 (includes AU) work.

Tests:
- Unit: pipeline invokes AU builders when country=AU
- Unit: AU M2/M3/M4 graceful skip (NotImplementedError caught)
- Unit: connector_to_close includes RBA instance

Integration smoke @slow:
tests/integration/test_daily_monetary_au.py:

@pytest.mark.slow
def test_daily_monetary_au_te_primary():
    """Full pipeline AU 2024-12-31 with TE primary cascade.

    Expected:
    - M1 AU row persists
    - AU_CASH_RATE_TE_PRIMARY flag present
    - R_STAR_PROXY flag present
    - policy_rate_pct daily-fresh"""

@pytest.mark.slow
def test_daily_monetary_au_rba_native_fallback():
    """TE unavailable, RBA tables succeed. Expected AU_CASH_RATE_RBA_NATIVE flag."""

Wall-clock ≤ 15s combined.

Coverage maintained.
```

### Commit 6 — M2/M4 AU scaffolds (pattern per Sprint L/S-CA)

```
feat(indices): M2 + M4 AU scaffolds (wire-ready, raise pending connectors)

Per Sprint L JP / Sprint S-CA CA pattern — M2/M4 AU builders are scaffolds
raising InsufficientDataError until full connectors wired.

async def build_m2_au_inputs(...) -> M2Inputs:
    """M2 AU scaffold — output gap needs ABS or OECD EO."""
    raise InsufficientDataError(
        "AU M2 requires output_gap; pending ABS/OECD EO connector. "
        "CAL-AU-M2-OUTPUT-GAP tracking resolution."
    )

async def build_m4_au_inputs(...) -> M4Inputs:
    """M4 AU scaffold — FCI components need AUD-specific VIX, credit spreads, NEER."""
    raise InsufficientDataError(
        "AU M4 requires VIX-AU / credit-spread-AU / NEER-AUD; all deferred. "
        "CAL-AU-M4-FCI tracking full wire-up."
    )

Tests:
- Unit: build_m2_au_inputs raises InsufficientDataError
- Unit: build_m4_au_inputs raises InsufficientDataError
- Unit: error message references correct CAL items

Import InsufficientDataError from exceptions module.

Coverage maintained.
```

### Commit 7 — Retrospective + CAL items opened

```
docs(planning): Week 9 Sprint T-AU Australia connector retrospective

File: docs/planning/retrospectives/week9-sprint-t-au-connector-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- Empirical findings:
  - TE AU Cash Rate HistoricalDataSymbol: [probe result]
  - RBA tables reachability: [success/issues]
  - FRED OECD AU mirror series validated
- Coverage delta
- Live canary outcomes
- HALT triggers fired / not fired
- Deviations from brief
- M2 T1 progression: 10 → 11 countries
- AU monetary indices operational:
  - M1: live via TE cascade (RBA tables if probe succeeded)
  - M2: scaffold (CAL-AU-M2-OUTPUT-GAP)
  - M3: deferred (CAL-AU-M3)
  - M4: scaffold (CAL-AU-M4-FCI)
- Pattern validation:
  - TE-primary cascade continues canonical
  - RBA tables = similar robust public API pattern to BoC Valet (Sprint S-CA precedent)
- Isolated worktree: zero collision incidents with Sprint AA parallel
- Merge strategy: branch sprint-t-au-connector → main fast-forward
- New CAL items opened:
  - CAL-AU-M2-OUTPUT-GAP: AU M2 output gap via ABS/OECD EO
  - CAL-AU-M3: AU M3 market expectations (needs AU NSS + expinf overlays)
  - CAL-AU-M4-FCI: AU M4 FCI full component wiring

Open CAL-AU-* items formally in docs/backlog/calibration-tasks.md.

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git merge --ff-only sprint-t-au-connector
  git push origin main
```

---

## 5. HALT triggers (atomic)

0. **TE AU Cash Rate empirical probe fails** — if TE returns no AU data or unexpected format, HALT + surface. Alternative: FRED primary + accept monthly-stale with explicit operator warning.
1. **HistoricalDataSymbol mismatch** — if TE returns different symbol than probe found, do NOT assume benign. HALT.
2. **RBA tables unreachable** — possible; RBA publishes CSVs without guaranteed programmatic stability. If unreachable, scaffold raises gracefully. Not a HALT — note in retro.
3. **RBA CSV schema per-table divergent** — if F01 vs F02 vs G01 have different row structures requiring heavy parsing, scope Commit 2 narrow to F01 only; defer others.
4. **AU in country_tiers.yaml Tier mismatch** — if AU marked Tier 2+ instead of Tier 1, HALT + verify against ADR-0005.
5. **r* AU value uncertainty** — use RBA staff research estimate + R_STAR_PROXY flag. Document source in YAML comment.
6. **M2/M4 scaffolds — pattern correct?** — per Sprint L JP / Sprint S-CA CA, raise InsufficientDataError. Verify pattern replication.
7. **TE rate limits** during live canaries — tenacity handles; if persistent, mark slow + document in retro.
8. **Coverage regression > 3pp** → HALT.
9. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
10. **Concurrent Sprint AA touches files in Sprint T scope** (shouldn't per §3) → reconcile via rebase.

---

## 6. Acceptance

### Global sprint-end
- [ ] 6-8 commits pushed to branch `sprint-t-au-connector`
- [ ] `src/sonar/connectors/rba.py` shipped + tested (even if RBA probe partial)
- [ ] `fetch_au_cash_rate` TE wrapper + source-drift guard shipped
- [ ] TE AU HistoricalDataSymbol validated + documented
- [ ] RBA tables reachability documented (probe result)
- [ ] AU Tier 1 in country_tiers.yaml
- [ ] r_star_values.yaml AU entry added (with proxy: true)
- [ ] bc_targets.yaml AU entry present (2.5%)
- [ ] `build_m1_au_inputs` cascade operational
- [ ] M2 + M4 AU scaffolds shipped (raise InsufficientDataError)
- [ ] `daily_monetary_indices.py --country AU` runs end-to-end
- [ ] Live canaries PASS: TE AU Cash Rate + AU monetary pipeline
- [ ] Coverage rba.py ≥ 85%, builders.py AU path ≥ 95%
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week9-sprint-t-au-connector-report.md`

**Final tmux echo**:
```
SPRINT T-AU AUSTRALIA CONNECTOR DONE: N commits on branch sprint-t-au-connector
TE HistoricalDataSymbol AU validated: [symbol]
RBA tables reachability: [success / issues / partial]
AU monetary: M1 (cascade), M2/M4 (scaffolds), M3 (deferred)
M2 T1 progression: 10 → 11 countries
HALT triggers: [list or "none"]
Merge: git checkout main && git merge --ff-only sprint-t-au-connector
Artifact: docs/planning/retrospectives/week9-sprint-t-au-connector-report.md
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

Live canaries do NOT run default pytest (`@pytest.mark.slow`).

---

## 9. Notes on implementation

### TE primary is canonical (Sprint I-patch/Sprint L/Sprint S-CA lesson)
All country expansion defaults to TE primary → native override → FRED last-resort. Fourth consecutive country replicating pattern.

### RBA tables are public but CSV not REST
Unlike BoC Valet (Sprint S-CA JSON REST), RBA publishes statistical tables as CSV files. Simpler parsing but less structured. Expect success but variable table schemas.

### Pattern replication discipline
Sprint S-CA CA shipped Day 1 (most recent). This sprint replicates pattern closely:
- TE wrapper with source-drift guard
- Native connector (CSV rather than JSON REST)
- M1 builder with cascade
- M2/M4 scaffolds raising InsufficientDataError
- Pipeline integration
- Retro

### r* AU is explicit proxy
RBA staff research estimates vary ~1.0-1.5%; midpoint 1.25% reasonable + R_STAR_PROXY flag + YAML citation.

### M3 AU deferred
Per Sprint L JP / Sprint S-CA CA precedent, M3 needs persisted NSS forwards + expected-inflation for country. AU overlays not yet shipped — CAL-AU-M3 analog pattern.

### Isolated worktree workflow
Sprint T-AU operates entirely in `/home/macro/projects/sonar-wt-sprint-t`. Branch: `sprint-t-au-connector`. Final merge via fast-forward.

### Sprint AA parallel
Runs in `sonar-wt-sprint-aa`. Different domains entirely (BIS v2 migration vs AU connector). Zero file overlap per §3.

---

*End of Week 9 Sprint T-AU Australia connector brief. 6-8 commits. AU T1 shipped with TE-primary cascade.*
