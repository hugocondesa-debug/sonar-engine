# Week 8 Sprint L — JP BoJ Connector + M2 T1 Expansion (TE-primary Cascade)

**Target**: Ship Bank of Japan connector + JP country enablement across monetary indices. M2 T1 progression from 8 to 9 countries. **TE-primary cascade by default** (per Sprint I-patch lesson — mandatory pattern for all country expansions).
**Priority**: HIGH (M2 T1 Core milestone progression)
**Budget**: 3-4h CC autonomous
**Commits**: ~6-8
**Base**: branch `sprint-l-boj-connector` (isolated worktree `/home/macro/projects/sonar-wt-sprint-l`)
**Concurrency**: Parallel to Sprint O GB/UK rename in worktree `sonar-wt-sprint-o`. See §3.

---

## 1. Scope

In:
- `src/sonar/connectors/boj.py` — new BoJ connector for Time Series Database (TSD) public API
- **Cascade strategy (mandatory per Sprint I-patch lesson Pattern 4)**:
  1. **Primary: TE native JP Bank Rate / JGB yields** (daily, BoJ-sourced via TE)
  2. **Secondary: BoJ native TSD** (public API; may work OR may fail similar to BoE Akamai)
  3. **Tertiary: FRED OECD mirror** (monthly-lagged; last-resort with `CALIBRATION_STALE` flag)
- TE wrapper `fetch_jp_bank_rate` with HistoricalDataSymbol source-drift guard per Sprint 3 Quick Wins discipline
- Core series empirical discovery:
  - JP Bank Rate (Tanto Ritsu / Uncollateralized overnight call rate): likely TE `JPNSHIKIN` or similar; probe Commit 1
  - JP 10Y JGB yield: TE `GJGB10:IND` (mapping exists per SESSION_CONTEXT)
  - JP CPI + unemployment: TE generic `fetch_indicator(country="JP", ...)` pattern
- Empirical BoJ TSD probe (time-boxed 30 min; falls to TE primary if unreachable)
- JP country entry in `docs/data_sources/country_tiers.yaml` (verify Tier 1 per ADR-0005)
- r* JP entry in `src/sonar/config/r_star_values.yaml` (~0.000 per BoJ staff research, proxy: true flag)
- JP inflation target in `src/sonar/config/bc_targets.yaml` (0.02 per BoJ YCC)
- Monetary indices M1/M2/M4 JP builders via TE primary cascade
- Pipeline integration `daily_monetary_indices.py --country JP`
- Cassette + `@pytest.mark.slow` live canary per major series
- Retrospective

Out:
- GB/UK rename work (Sprint O paralelo domain)
- JP M3 (requires persisted overlays — CAL-105 pattern for JP)
- JP ERP live path (per-country ERP deferred Phase 2+)
- JP CRP (BENCHMARK via spec; sovereign yield spread automatic)
- JP rating-spread (AAA baseline sovereign)
- L3 economic indices JP path (E1/E2/E3/E4; connector gaps separate sprint)
- L3 credit indices JP (BIS coverage existing via Sprint 2b; verify but not new work)
- L3 financial indices JP (F1-F4 US proxies; Phase 2+)

---

## 2. Spec reference

Authoritative:
- `docs/data_sources/country_tiers.yaml` — JP should be Tier 1 per ADR-0005
- `docs/specs/indices/monetary/M1-effective-rates.md` §2 — monetary inputs per country
- `docs/specs/indices/monetary/M2-taylor-gaps.md` §2 — r*, policy rate, inflation inputs
- `docs/specs/indices/monetary/M4-fci.md` §2 — FCI components
- `docs/specs/conventions/patterns.md` — Pattern 4 (Aggregator-primary with native-override)
- `docs/planning/retrospectives/week8-sprint-i-patch-te-cascade-report.md` — **TE primary is canonical for all country expansion**
- SESSION_CONTEXT §Critical technical reference — TE HistoricalDataSymbol validated list
- `src/sonar/connectors/boe_database.py` — pattern template (similar gated-API + TE cascade)
- `src/sonar/connectors/te.py` — existing JP country mappings

**Pre-flight requirement**: Commit 1 CC:
1. Verify TE JP mappings: `"JP": "japan"` (indicator) + `"JP": "GJGB10:IND"` (bonds)
2. Probe TE JP Bank Rate empirically:
   ```bash
   set -a && source .env && set +a
   curl -s "https://api.tradingeconomics.com/historical/country/japan/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'
   ```
3. Document TE HistoricalDataSymbol for JP Bank Rate (probe finding)
4. Time-boxed 30 min BoJ TSD probe (optional native attempt):
   - Base URL likely `https://www.stat-search.boj.or.jp/` (undocumented for scripting)
   - If probe succeeds → wire as secondary
   - If gated/unreachable → document + skip, rely on TE primary + FRED fallback
5. Read `boe_database.py` + `te.py` UK wrappers for pattern
6. Verify JP in `country_tiers.yaml`; if missing, add as Tier 1

Document findings in Commit 1 body.

Existing assets:
- `TEConnector` generic + wrappers (7 from Sprint 1 + UK Bank Rate from Sprint I-patch)
- FRED connector has `fetch_series` for any series ID
- `country_tiers.yaml` canonical (ISO alpha-2 convention)
- `bc_targets.yaml` + `r_star_values.yaml` shipped Week 6 Sprint 1b

---

## 3. Concurrency — parallel protocol with Sprint O + ISOLATED WORKTREES + carve-out

**Sprint L operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-l`

Sprint O operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-o`

**Critical workflow**:
1. Sprint L CC starts by `cd /home/macro/projects/sonar-wt-sprint-l`
2. All file operations happen in this worktree
3. Branch name: `sprint-l-boj-connector`
4. Pushes to `origin/sprint-l-boj-connector`
5. Final merge to main via fast-forward post-sprint-close

**File scope Sprint L**:
- `src/sonar/connectors/boj.py` NEW
- `src/sonar/connectors/te.py` APPEND (new `fetch_jp_bank_rate` wrapper + JP-specific constants)
- `src/sonar/indices/monetary/builders.py` MODIFY (add JP builders — `build_m1_jp_inputs`, etc.)
- `docs/data_sources/country_tiers.yaml` — verify/add JP entry
- `src/sonar/config/r_star_values.yaml` — add JP entry
- `src/sonar/config/bc_targets.yaml` — verify/add JP entry
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (wire JP country support)
- Tests:
  - `tests/unit/test_connectors/test_boj.py` NEW
  - `tests/unit/test_connectors/test_te.py` APPEND (JP Bank Rate wrapper tests)
  - `tests/unit/test_indices/monetary/test_builders.py` APPEND (JP builder tests)
  - `tests/unit/test_pipelines/test_daily_monetary_indices.py` APPEND (JP country)
  - `tests/integration/test_daily_monetary_jp.py` NEW
  - `tests/fixtures/cassettes/boj/` + `tests/fixtures/cassettes/te/jp_*.json`
- `docs/planning/retrospectives/week8-sprint-l-boj-connector-report.md` NEW

**Sprint O scope** (for awareness, CARVE-OUT respected):
- Sprint O touches ALL files with "UK" references EXCEPT `src/sonar/indices/monetary/builders.py`
- Sprint O renames `country_tiers.yaml` UK → GB
- Sprint O renames `bc_targets.yaml` UK → GB
- Sprint O renames `r_star_values.yaml` UK → GB
- Sprint O renames TE wrapper references UK → GB (in `te.py`)
- Sprint O updates tests UK → GB
- Sprint O documents post-sprint chore: final UK → GB rename sweep on `builders.py` (consolidated single commit after both sprints merge)

**Sprint L respects carve-out**:
- Sprint L does NOT rename UK references
- Sprint L adds JP references using current "UK" convention (consistent with pre-rename state)
- Post-both-merges, chore commit on `builders.py` does UK → GB sweep covering Sprint L's new JP additions AND pre-existing UK references
- This preserves clean paralelo without file overlap

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-sprint-l && git pull origin main --rebase`
- Ensures Sprint L base contains Sprint M + N merges from Day 3

**Push race**: normal `git push origin sprint-l-boj-connector`. Zero collisions expected with Sprint O (different files entirely).

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-l-boj-connector
git push origin main
```
Fast-forward expected.

---

## 4. Commits

### Commit 1 — Pre-flight + TE JP Bank Rate wrapper

```
feat(connectors): TE fetch_jp_bank_rate wrapper + source-drift guard

Pre-flight: probe TE JP Bank Rate + verify BoJ TSD reachability.

Expected probe (document findings commit body):
  set -a && source .env && set +a
  curl -s "https://api.tradingeconomics.com/historical/country/japan/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'

Document in commit body:
- Actual HistoricalDataSymbol returned (likely JPNLENDRATE or similar)
- Response format (date + value)
- Historical range (expected: daily since BoJ 1882 or later post-war)
- Latest value sanity check (should match current BoJ target ~0.50% Dec 2024)

BoJ TSD probe (time-boxed 30 min):
  curl -s "https://www.stat-search.boj.or.jp/..." (probe entrypoint)
  # Document reachability: success OR Akamai-style gate OR auth required

Extend src/sonar/connectors/te.py:

JP_BANK_RATE_EXPECTED_SYMBOL: Final = "[EMPIRICAL — probe result]"
JP_BANK_RATE_INDICATOR: Final = "interest rate"

async def fetch_jp_bank_rate(
    self,
    start: date,
    end: date,
) -> list[TEIndicatorObservation]:
    """Fetch JP uncollateralized overnight call rate / Bank Rate from TE.

    TE sources from BoJ directly — avoids FRED OECD mirror monthly lag.
    Validates HistoricalDataSymbol matches expected per Sprint 3 Quick
    Wins source-drift discipline.

    Raises DataUnavailableError("source drift") if HistoricalDataSymbol
    != JP_BANK_RATE_EXPECTED_SYMBOL.
    """
    obs = await self.fetch_indicator(
        country="JP",
        indicator=JP_BANK_RATE_INDICATOR,
        start=start,
        end=end,
    )
    if obs and obs[0].historical_data_symbol != JP_BANK_RATE_EXPECTED_SYMBOL:
        raise DataUnavailableError(...)
    return obs

Sanity check commit body:
  python -c "from sonar.connectors.te import TEConnector; c = TEConnector(api_key='x'); print(hasattr(c, 'fetch_jp_bank_rate'))"

Tests (tests/unit/test_connectors/test_te.py append):
- Unit: happy path mocked response
- Unit: HistoricalDataSymbol mismatch → DataUnavailableError
- Unit: empty response → empty list
- @pytest.mark.slow live canary: fetch Bank Rate 2024-12-01..31 →
  assert ≥ 1 obs, value ∈ [-0.1%, 1.0%] (reasonable range for Dec 2024)

Cassette: tests/fixtures/cassettes/te/jp_bank_rate_2024_12.json

Coverage te.py additions ≥ 90%.
```

### Commit 2 — BoJ TSD connector scaffold

```
feat(connectors): BoJ Time Series Database connector scaffold

Create src/sonar/connectors/boj.py:

"""Bank of Japan Time Series Database (TSD) connector.

Handles the public BoJ TSD API for JP macro time series.
Fallback cascade per Sprint I-patch lesson: TE → BoJ native → FRED.

Empirical probe findings (Commit 1):
- Base URL: https://www.stat-search.boj.or.jp/ (or equivalent)
- Availability: [document — reachable OR gated]
- Response format: [CSV | JSON]
- Auth: [public | required]
"""

from __future__ import annotations
from datetime import date
from sonar.connectors.base import BaseConnector
from sonar.connectors.exceptions import (
    DataUnavailableError,
    ConnectorError,
)

# Empirically validated series IDs (probe-validated Commit 1-2)
BOJ_BANK_RATE = "..."  # uncollateralized overnight call rate
BOJ_JGB_10Y = "..."    # 10Y JGB yield
BOJ_BALANCE_SHEET = "..." # BoJ balance sheet

class BoJConnector(BaseConnector):
    """Public TSD API; likely no auth required."""

    BASE_URL = "https://www.stat-search.boj.or.jp/"
    CONNECTOR_ID = "boj"

    async def fetch_series(
        self,
        series_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[TSDObservation]:
        """Fetch time series from BoJ TSD.

        Returns list of observations.
        Raises DataUnavailableError if series empty, 404, or gated.
        """
        ...

    async def fetch_bank_rate(...) -> float:
        """Convenience: latest uncollateralized overnight call rate."""
        ...

Design decision documented commit body:
- If BoJ TSD probe SUCCEEDED: implement full fetch logic
- If gated/unreachable: ship wire-ready scaffold (raises DataUnavailableError
  with documented reason); cascade upstream treats as soft fail, falls to TE

Sanity check:
  python -c "from sonar.connectors.boj import BoJConnector; print('OK')"

Tests (tests/unit/test_connectors/test_boj.py):
- Unit: class instantiation + URL building
- Unit: fetch_series success path (if reachable)
- Unit: fetch_series 404 → DataUnavailableError
- Unit: fetch_series gated response → DataUnavailableError
- Unit: disk cache behavior
- @pytest.mark.slow live canary: probe bank rate (if reachable); OR
  skip with reason if probe confirmed gated Commit 1

Coverage boj.py ≥ 80% (tolerance for probe-gated connector).

Cassette: tests/fixtures/cassettes/boj/*.json (or minimal if gated)
```

### Commit 3 — JP Tier 1 config + r*/bc_targets YAML entries

```
feat(config): JP Tier 1 enabled + monetary YAML entries

1. Verify docs/data_sources/country_tiers.yaml contains JP as Tier 1.
   If missing, add:
   - iso_code: JP
     tier: 1
     monetary: enabled
     description: "Japan — Tier 1 per ADR-0005"
   Note: JP is canonical ISO alpha-2.

2. Update src/sonar/config/r_star_values.yaml — add JP entry:
   JP:
     value: 0.000       # BoJ staff research estimate ~0.0% neutral
     proxy: true
     source: "BoJ Research & Studies ~2024 (QQE legacy; ultra-low rate regime)"
     timestamp: "2024-12-01"

   Loader auto-emits R_STAR_PROXY flag.

3. Verify src/sonar/config/bc_targets.yaml JP entry:
   JP:
     target: 0.02        # BoJ 2% YCC target
     source: "BoJ Policy Statement 2013 (YCC maintained)"
   If missing, add.

Unit tests:
- Loader reads JP r* with proxy=true
- bc_targets loader reads JP 2% target
- country_tiers_parser includes JP in T1 list

Coverage maintained.
```

### Commit 4 — M1 JP builder with TE-primary cascade

```
feat(indices): M1 JP builder TE primary cascade

Add build_m1_jp_inputs to src/sonar/indices/monetary/builders.py:

async def build_m1_jp_inputs(
    fred: FredConnector,
    te: TEConnector,
    observation_date: date,
    *,
    boj: BoJConnector | None = None,
    history_years: int = 15,
) -> M1Inputs:
    """Build M1 JP inputs via TE primary cascade.

    Cascade priority:
    1. TE primary — JP_BANK_RATE_TE_PRIMARY flag (daily BoJ-sourced)
    2. BoJ native — JP_BANK_RATE_BOJ_NATIVE flag (rare if gated)
    3. FRED OECD mirror — JP_BANK_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE

    r* via r_star_values.yaml (R_STAR_PROXY flag).
    Inflation target via bc_targets.yaml (2% BoJ).
    """
    # Pseudocode mirroring Sprint I-patch UK cascade
    flags = []
    obs = None

    # Primary: TE
    if te:
        try:
            obs = await te.fetch_jp_bank_rate(start, end)
            if obs:
                flags.append("JP_BANK_RATE_TE_PRIMARY")
        except (DataUnavailableError, ConnectorError):
            flags.append("JP_BANK_RATE_TE_UNAVAILABLE")

    # Secondary: BoJ (if probe succeeded)
    if not obs and boj:
        try:
            boj_obs = await boj.fetch_bank_rate(start, end)
            if boj_obs:
                obs = [_DatedValue(...) for o in boj_obs]
                flags.append("JP_BANK_RATE_BOJ_NATIVE")
        except DataUnavailableError:
            flags.append("JP_BANK_RATE_BOJ_FALLBACK")

    # Tertiary: FRED OECD mirror (last-resort, monthly stale)
    if not obs:
        fred_obs = await fred.fetch_series(FRED_JP_BANK_RATE_SERIES, start, end)
        if fred_obs:
            obs = [_DatedValue(...) for o in fred_obs]
            flags.extend([
                "JP_BANK_RATE_FRED_FALLBACK_STALE",
                "CALIBRATION_STALE",
            ])

    if not obs:
        raise ValueError("JP Bank Rate unavailable from TE, BoJ, FRED")

    # r* from YAML
    r_star, r_star_is_proxy = resolve_r_star("JP")
    if r_star_is_proxy:
        flags.append("R_STAR_PROXY")

    # Build M1Inputs ...

Constants:
FRED_JP_BANK_RATE_SERIES: str = "IRSTCI01JPM156N"  # OECD MEI JP short-rate
FRED_JP_JGB_10Y_SERIES: str = "IRLTLT01JPM156N"     # OECD MEI JP long-rate

Expose in __all__:
    "build_m1_jp_inputs",

Tests:
- Unit: TE primary success → JP_BANK_RATE_TE_PRIMARY
- Unit: TE fails, BoJ succeeds (if reachable) → JP_BANK_RATE_BOJ_NATIVE
- Unit: TE + BoJ fail → FRED fallback → CALIBRATION_STALE
- Unit: all fail → ValueError
- Unit: r* loaded JP with proxy flag
- Unit: bc_targets JP 2% loaded

Coverage build_m1_jp_inputs ≥ 95%.
```

### Commit 5 — M2 + M4 JP builders (partial, deferred where gaps exist)

```
feat(indices): M2 JP + M4 JP builders (best-effort)

M2 JP via Taylor gap:
- Policy rate: from M1 JP (TE cascade)
- r* JP: 0.000 per YAML
- Inflation target: 0.02 per bc_targets
- Output gap: Japan-specific source — likely OECD EO if available via
  TE country indicator ("gdp gap") OR descope with JP_M2_OUTPUT_GAP_MISSING flag
- Decision: ship builder with output gap optional; if unavailable, raise
  InsufficientDataError with flag

M4 JP via FCI:
- Components per spec §M4 §2 inputs:
  - Credit spread: TE credit spread JP OR proxy from US
  - Equity volatility: Nikkei VI OR ^VIX proxy with flag
  - Stock market drawdown: Nikkei 225 via FRED NIKKEI225 OR Yahoo
  - Real lending rate: TE 10Y JGB - inflation expectation
  - Currency: JPY NEER via BIS OR TE
- Ship builder with best-effort coverage; flag missing components

Signature:
async def build_m2_jp_inputs(...) -> M2Inputs:
    ...  # TE primary for output gap, fallback FRED NIKKEI225 + flags

async def build_m4_jp_inputs(...) -> M4Inputs:
    ...  # best-effort; flag degraded components

Tests:
- Unit: M2 JP happy path with output gap available
- Unit: M2 JP output gap missing → InsufficientDataError
- Unit: M4 JP with partial components → flags
- Unit: M4 JP full components → clean result

Note: JP M3 DEFERRED (requires persisted NSS forwards + expected-inflation
for JP — analog CAL-104/105 pattern).

Coverage maintained.
```

### Commit 6 — Pipeline integration daily_monetary_indices JP

```
feat(pipelines): daily_monetary_indices JP country support

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Add JP to MONETARY_SUPPORTED_COUNTRIES tuple/list (alongside US, EA, UK)
2. JP country branch routes to build_m1_jp_inputs / build_m2_jp_inputs / build_m4_jp_inputs
3. M3 JP: raises NotImplementedError gracefully (pattern consistent with UK M3)
4. Connector lifecycle: BoJ connector added to connectors_to_close

Verify --country JP and --all-t1 (includes JP when enabled) work.

Tests:
- Unit: pipeline invokes JP builders when country=JP
- Unit: JP M3 graceful skip
- Unit: connector_to_close includes BoJ instance

Integration smoke @slow:
tests/integration/test_daily_monetary_jp.py:

@pytest.mark.slow
def test_daily_monetary_jp_te_primary():
    """Full pipeline JP 2024-12-31 with TE primary cascade.

    Expected:
    - M1 JP row persists
    - JP_BANK_RATE_TE_PRIMARY flag present
    - R_STAR_PROXY flag present
    - policy_rate_pct daily-fresh"""

@pytest.mark.slow
def test_daily_monetary_jp_partial_coverage():
    """M2/M4 JP run with degraded paths; graceful flags."""

Wall-clock ≤ 15s combined.

Coverage maintained.
```

### Commit 7 — Retrospective

```
docs(planning): Week 8 Sprint L BoJ connector retrospective

File: docs/planning/retrospectives/week8-sprint-l-boj-connector-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- Empirical findings:
  - TE JP Bank Rate HistoricalDataSymbol: [probe result]
  - BoJ TSD reachability: [success / gated / unreachable]
  - FRED OECD JP mirror series validated
- Coverage delta
- Live canary outcomes
- HALT triggers fired / not fired
- Deviations from brief
- M2 T1 progression: 8 → 9 countries (UK + JP both T1 monetary)
- JP monetary indices operational:
  - M1: live via TE cascade
  - M2: live via Taylor gap (best-effort on output gap)
  - M4: partial live with component flags
  - M3: deferred (CAL-JP-M3 analog pattern)
- Pattern validation:
  - TE-primary cascade is now canonical for country expansion
  - BoJ native scaffold preserved wire-ready
  - FRED OECD mirror relegated to last-resort with staleness flags
- Isolated worktree: zero collision incidents with Sprint O parallel
- Merge strategy: branch sprint-l-boj-connector → main fast-forward
- New CAL items opened:
  - CAL-JP-M3: JP M3 market expectations (needs JP NSS + expinf overlays)
  - CAL-JP-OUTPUT-GAP: JP M2 output gap connector (OECD EO or similar) if deferred
  - CAL-JP-FCI: JP M4 FCI full component wiring (if partial)

Close CAL-JP items formally in docs/backlog/calibration-tasks.md.

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git merge --ff-only sprint-l-boj-connector
  git push origin main
```

---

## 5. HALT triggers (atomic)

0. **TE JP Bank Rate empirical probe fails** — if TE returns no JP data or unexpected format, HALT + surface. Alternative: FRED primary + accept monthly-stale with explicit operator warning.
1. **HistoricalDataSymbol mismatch** — if TE returns different symbol than probe found, do NOT assume benign. HALT.
2. **BoJ TSD completely unreachable** — acceptable; ship scaffold that raises gracefully. Not a HALT.
3. **JP in country_tiers.yaml Tier mismatch** — if JP marked Tier 2+ instead of Tier 1, HALT + verify against ADR-0005.
4. **r* JP value uncertainty** — BoJ does not publish neutral rate explicitly. Use BoJ staff research estimate ~0.0% + R_STAR_PROXY flag. Document source in YAML comment.
5. **M2 output gap missing** — if unavailable, descope M2 JP to InsufficientDataError with JP_M2_OUTPUT_GAP_MISSING flag. Not a HALT; documented degradation.
6. **M4 FCI coverage < 3/5 components** — acceptable with multiple flags. Not a HALT.
7. **TE rate limits** during live canaries — tenacity handles; if persistent, mark slow + document in retro.
8. **Coverage regression > 3pp** → HALT.
9. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
10. **Concurrent Sprint O touches builders.py** (shouldn't per §3 carve-out) → reconcile via rebase.

---

## 6. Acceptance

### Global sprint-end
- [ ] 6-8 commits pushed to branch `sprint-l-boj-connector`
- [ ] `src/sonar/connectors/boj.py` shipped + tested
- [ ] `fetch_jp_bank_rate` TE wrapper + source-drift guard shipped
- [ ] TE JP HistoricalDataSymbol validated + documented
- [ ] JP Tier 1 in country_tiers.yaml
- [ ] r_star_values.yaml JP entry added (with proxy: true)
- [ ] bc_targets.yaml JP entry present (2%)
- [ ] `build_m1_jp_inputs` cascade operational
- [ ] M2 + M4 JP builders shipped (best-effort)
- [ ] `daily_monetary_indices.py --country JP` runs end-to-end
- [ ] Live canaries PASS: TE JP Bank Rate + JP monetary pipeline
- [ ] Coverage boj.py ≥ 80%, builders.py JP path ≥ 95%
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push
- [ ] Carve-out respected: Sprint L does NOT rename UK references in any file

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week8-sprint-l-boj-connector-report.md`

**Final tmux echo**:
```
SPRINT L BoJ CONNECTOR DONE: N commits on branch sprint-l-boj-connector
TE HistoricalDataSymbol JP validated: [symbol]
BoJ TSD reachability: [success / gated / unreachable]
JP monetary: M1 (cascade), M2 (best-effort), M4 (partial), M3 deferred
M2 T1 progression: 8 → 9 countries
HALT triggers: [list or "none"]
Merge: git checkout main && git merge --ff-only sprint-l-boj-connector
Carve-out respected: builders.py UK refs untouched (Sprint O domain)
Artifact: docs/planning/retrospectives/week8-sprint-l-boj-connector-report.md
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

### TE primary is canonical
Sprint I-patch lesson shipped as permanent pattern. All country expansion defaults to TE primary → native override → FRED last-resort. JP follows same shape.

### BoJ TSD probe is exploratory
30 min time-box. If gated, ship scaffold (like BoE post-Sprint I). Cascade upstream uses TE primary regardless.

### r* JP is explicit proxy
BoJ hasn't published HLW-equivalent. 0.0% estimate per BoJ staff research + R_STAR_PROXY flag + YAML citation.

### M3 JP deferred
Per spec, M3 needs persisted NSS forwards + expected-inflation for country. JP overlays not yet shipped. Open CAL-JP-M3 analog pattern.

### Carve-out discipline critical
Sprint L MUST NOT rename UK → GB anywhere. New JP additions use existing "UK" convention where it exists. Post-both-merges chore commit does final rename sweep including JP additions + pre-existing UK references.

### Isolated worktree workflow
Sprint L operates entirely in `/home/macro/projects/sonar-wt-sprint-l`. Branch: `sprint-l-boj-connector`. Final merge via fast-forward.

### Sprint O parallel
Runs in `sonar-wt-sprint-o`. Different concerns (JP addition vs UK rename). Zero file overlap per §3 carve-out.

---

*End of Week 8 Sprint L BoJ connector brief. 6-8 commits. JP T1 shipped with TE-primary cascade.*
