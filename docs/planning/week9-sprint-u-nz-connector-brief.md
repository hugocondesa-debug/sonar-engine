# Week 9 Sprint U-NZ — New Zealand RBNZ Connector + M1 NZ (TE-primary Cascade)

**Target**: Ship Reserve Bank of New Zealand connector + NZ country enablement for M1 monetary. M2 T1 progression from 11 to 12 countries. TE-primary cascade per Sprint L/S-CA/T-AU canonical pattern.
**Priority**: HIGH (M2 T1 Completionist progression — 3 of 7 remaining T1 countries at Week 9 start)
**Budget**: 3-4h CC autonomous
**Commits**: ~6-8
**Base**: branch `sprint-u-nz-connector` (isolated worktree `/home/macro/projects/sonar-wt-sprint-u`)
**Concurrency**: Parallel to Sprint V-CH Switzerland SNB connector in worktree `sonar-wt-sprint-v`. See §3.

---

## 1. Scope

In:
- `src/sonar/connectors/rbnz.py` — new Reserve Bank of New Zealand connector
- **Cascade strategy per Sprint L/S-CA/T-AU canonical pattern (TE-primary default)**:
  1. **Primary: TE native NZ OCR / GoNZ bond yields** (daily, RBNZ-sourced via TE)
  2. **Secondary: RBNZ statistical tables** (public CSV/XLS, well-documented)
  3. **Tertiary: FRED OECD mirror** (monthly-lagged; last-resort with `CALIBRATION_STALE` flag)
- TE wrapper `fetch_nz_ocr` with HistoricalDataSymbol source-drift guard
- Core series empirical discovery:
  - NZ OCR (Official Cash Rate): probe Commit 1 (likely `NZOCR`, `RBNZOCR`, or similar)
  - NZ 10Y Government Stock yield: TE `GNZGB10:IND` (verify existing mapping)
  - NZ CPI + unemployment: TE generic `fetch_indicator(country="NZ", ...)` pattern
- Empirical RBNZ statistical tables probe (time-boxed 20 min)
  - URL: `https://www.rbnz.govt.nz/statistics`
  - Tables catalogue likely similar to RBA pattern (CSV downloads)
- NZ country entry in `docs/data_sources/country_tiers.yaml` (verify Tier 1 per ADR-0005)
- r* NZ entry in `src/sonar/config/r_star_values.yaml` (~1.5-2.0% per RBNZ staff research)
- NZ inflation target in `src/sonar/config/bc_targets.yaml` (0.02 midpoint per RBNZ 1-3% band)
- M1 NZ builder via TE-primary cascade (M2/M4 scaffolds only; full wiring deferred CAL-NZ-*)
- Pipeline integration `daily_monetary_indices.py --country NZ`
- Cassette + `@pytest.mark.slow` live canary for TE + RBNZ paths
- Retrospective

Out:
- M2 NZ live (output gap requires Stats NZ / OECD EO — CAL-NZ-M2-OUTPUT-GAP)
- M3 NZ (requires persisted NSS forwards + expected-inflation for NZ — CAL-NZ-M3)
- M4 NZ (FCI — requires VIX-NZ, credit spreads NZ, NZD NEER — CAL-NZ-M4-FCI)
- NZ ERP per-country live (deferred Phase 2+)
- NZ CRP (BENCHMARK via spec; sovereign yield spread automatic)
- L3 credit indices NZ (BIS coverage may exist; depends on BIS post-Sprint-AA fix)

---

## 2. Spec reference

Authoritative:
- `docs/data_sources/country_tiers.yaml` — NZ should be Tier 1 per ADR-0005
- `docs/specs/indices/monetary/M1-effective-rates.md` §2
- `docs/specs/indices/monetary/M2-taylor-gaps.md` §2
- `docs/specs/conventions/patterns.md` — Pattern 4
- `docs/planning/retrospectives/week9-sprint-t-au-connector-report.md` — **Sprint T-AU most recent pattern (RBA CSV tables)**
- `docs/planning/retrospectives/week9-sprint-s-ca-connector-report.md` — Sprint S-CA BoC Valet JSON REST precedent
- `docs/planning/retrospectives/week8-sprint-l-boj-connector-report.md` — Sprint L JP scaffold pattern
- `src/sonar/connectors/rba.py` — Sprint T-AU CSV connector template (most relevant for RBNZ)
- `src/sonar/connectors/boc.py` — Sprint S-CA JSON REST connector alt template
- `src/sonar/connectors/te.py` — existing NZ country mappings

**Pre-flight requirement**: Commit 1 CC:
1. Verify TE NZ mappings: `"NZ": "new zealand"` (indicator) + `"NZ": "GNZGB10:IND"` (bonds) likely exist from Sprint 1
2. Probe TE NZ OCR empirically:
   ```bash
   set -a && source .env && set +a
   curl -s "https://api.tradingeconomics.com/historical/country/new zealand/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'
   ```
3. Document TE HistoricalDataSymbol for NZ OCR (probe finding)
4. Time-boxed 20 min RBNZ tables probe:
   - `curl -sL "https://www.rbnz.govt.nz/statistics" | head -100` — explore tables catalogue
   - Try OCR table direct: `curl -sL "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily.xlsx"` (pattern guess; probe actual path)
   - Try CSV format for programmatic access
   - **Apply Sprint T-AU UA-gate lesson**: use `User-Agent: SONAR/2.0 (monetary-cascade; email)` header (Mozilla may be blocked by Akamai/CDN)
5. If RBNZ probe SUCCEEDS → implement RBNZ connector as secondary in cascade
6. If RBNZ probe FAILS → scaffold raising DataUnavailableError (gated; document for CAL-NZ-RBNZ-TABLES)
7. Read `rba.py` as template (Sprint T-AU most recent CSV pattern)
8. Verify NZ in `country_tiers.yaml`; if missing, add as Tier 1

Document findings in Commit 1 body.

Existing assets:
- `TEConnector` generic + wrappers (shipped US/DE/PT/IT/ES/FR/NL Sprint 1 + GB Sprint I-patch + JP Sprint L + CA Sprint S-CA + AU Sprint T-AU)
- FRED connector has `fetch_series` for any series ID
- `country_tiers.yaml` canonical (ISO alpha-2)
- `bc_targets.yaml` + `r_star_values.yaml` extended AU Sprint T-AU pattern

---

## 3. Concurrency — parallel protocol with Sprint V-CH + ISOLATED WORKTREES

**Sprint U-NZ operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-u`

Sprint V-CH operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-v`

**Critical workflow**:
1. Sprint U-NZ CC starts by `cd /home/macro/projects/sonar-wt-sprint-u`
2. All file operations happen in this worktree
3. Branch name: `sprint-u-nz-connector`
4. Pushes to `origin/sprint-u-nz-connector`
5. Final merge to main via fast-forward post-sprint-close (may require rebase if V-CH merges first — backlog.md conflict likely)

**File scope Sprint U-NZ**:
- `src/sonar/connectors/rbnz.py` NEW
- `src/sonar/connectors/te.py` APPEND (new `fetch_nz_ocr` wrapper + NZ-specific constants)
- `src/sonar/indices/monetary/builders.py` APPEND (add NZ builders — `build_m1_nz_inputs`)
- `docs/data_sources/country_tiers.yaml` — verify/add NZ entry (likely exists)
- `src/sonar/config/r_star_values.yaml` — add NZ entry
- `src/sonar/config/bc_targets.yaml` — verify/add NZ entry
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (add NZ to MONETARY_SUPPORTED_COUNTRIES + NZ country dispatch)
- Tests:
  - `tests/unit/test_connectors/test_rbnz.py` NEW
  - `tests/unit/test_connectors/test_te_indicator.py` APPEND (NZ OCR wrapper tests)
  - `tests/unit/test_indices/monetary/test_builders.py` APPEND (NZ builder tests)
  - `tests/unit/test_pipelines/test_daily_monetary_indices.py` APPEND (NZ country)
  - `tests/integration/test_daily_monetary_nz.py` NEW
  - `tests/fixtures/cassettes/rbnz/` + `tests/cassettes/connectors/te_nz_ocr_*.json`
- `docs/backlog/calibration-tasks.md` MODIFY (CAL-NZ-* entries)
- `docs/planning/retrospectives/week9-sprint-u-nz-connector-report.md` NEW

**Sprint V-CH scope** (for awareness, DO NOT TOUCH):
- `src/sonar/connectors/snb.py` NEW (Swiss National Bank)
- `src/sonar/connectors/te.py` APPEND (CH wrapper — **concurrent append zone**)
- `src/sonar/indices/monetary/builders.py` APPEND (CH builders — **concurrent append zone**)
- `src/sonar/config/*.yaml` (CH entries — **concurrent modify zone**)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (CH dispatch — **concurrent modify zone**)

**Potential conflict zones**:
- `te.py` — both sprints append new wrappers (different functions, merge clean)
- `builders.py` — both append new builders (different functions, merge clean)
- `daily_monetary_indices.py` — both add to MONETARY_SUPPORTED_COUNTRIES tuple (likely conflict, union-merge)
- `r_star_values.yaml` + `bc_targets.yaml` — both add country entries (merge clean if different keys)
- `calibration-tasks.md` — CAL entries (union-merge precedent)

**Rebase expected post-merge**. Sprint U-NZ merges first (alphabetical branch) → V-CH rebases.

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-sprint-u && git pull origin main --rebase`

**Push race**: normal `git push origin sprint-u-nz-connector`. Minor conflicts resolved via rebase.

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-u-nz-connector
git push origin main
```

---

## 4. Commits

### Commit 1 — Pre-flight + TE NZ OCR wrapper

```
feat(connectors): TE fetch_nz_ocr wrapper + source-drift guard

Pre-flight: probe TE NZ OCR + verify RBNZ statistical tables reachability.

Expected probe (document findings commit body):
  set -a && source .env && set +a
  curl -s "https://api.tradingeconomics.com/historical/country/new zealand/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'

Document in commit body:
- Actual HistoricalDataSymbol returned (likely NZOCR, RBNZOCR, or IR-type)
- Response format (date + value)
- Historical range (expected: daily since OCR inception 1999)
- Latest value sanity check (should match current RBNZ OCR ~4.25-5.50% range as of late 2024/2025)

RBNZ statistical tables probe (time-boxed 20 min, apply UA-gate lesson):
  # Explore tables catalogue
  curl -sL -H "User-Agent: SONAR/2.0 (monetary-cascade)" \
    "https://www.rbnz.govt.nz/statistics" | head -100

  # Try OCR table (B2 series typical)
  curl -sL -H "User-Agent: SONAR/2.0 (monetary-cascade)" \
    "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily.csv" -o /tmp/rbnz_b2.csv
  head -10 /tmp/rbnz_b2.csv

  # Try government bond yields
  # (explore catalogue for canonical B-series or equivalent)

Document: reachability, response format (CSV/XLS), series stability, UA requirements.

Extend src/sonar/connectors/te.py:

NZ_OCR_EXPECTED_SYMBOL: Final = "[EMPIRICAL — probe result]"
NZ_OCR_INDICATOR: Final = "interest rate"

async def fetch_nz_ocr(
    self,
    start: date,
    end: date,
) -> list[TEIndicatorObservation]:
    """Fetch NZ Official Cash Rate (OCR) from TE.

    TE sources from RBNZ directly — avoids FRED OECD mirror monthly lag.
    Validates HistoricalDataSymbol matches expected per Sprint 3 Quick
    Wins source-drift discipline.

    Raises DataUnavailableError("source drift") if HistoricalDataSymbol
    != NZ_OCR_EXPECTED_SYMBOL.
    """
    obs = await self.fetch_indicator(
        country="NZ",
        indicator=NZ_OCR_INDICATOR,
        start=start,
        end=end,
    )
    if obs and obs[0].historical_data_symbol != NZ_OCR_EXPECTED_SYMBOL:
        raise DataUnavailableError(...)
    return obs

Sanity check commit body:
  python -c "from sonar.connectors.te import TEConnector; c = TEConnector(api_key='x'); print(hasattr(c, 'fetch_nz_ocr'))"

Tests (tests/unit/test_connectors/test_te_indicator.py append):
- Unit: happy path mocked response
- Unit: HistoricalDataSymbol mismatch → DataUnavailableError
- Unit: empty response → empty list
- @pytest.mark.slow live canary: fetch NZ OCR 2024-12-01..31 →
  assert ≥ 1 obs, value ∈ [0.10%, 8.5%] (reasonable range for recent RBNZ cycles)

Cassette: tests/cassettes/connectors/te_nz_ocr_2024_12.json

Coverage te.py additions ≥ 90%.
```

### Commit 2 — RBNZ statistical tables connector

```
feat(connectors): RBNZ statistical tables CSV connector (public, UA-gated)

Create src/sonar/connectors/rbnz.py:

"""Reserve Bank of New Zealand statistical tables connector.

Public data — no auth required. Descriptive User-Agent required
(Akamai gate blocks Mozilla default per Sprint T-AU lesson).

Fallback cascade per Sprint L/S-CA/T-AU pattern: TE → RBNZ tables → FRED.

Empirical probe findings (Commit 1):
- Base URL: https://www.rbnz.govt.nz/
- Statistics path: /statistics/series/b/b2/...
- Format: CSV (published daily/weekly)
- Auth: public (with descriptive UA)
- Key series (probe-validated Commit 1-2):
  - B2 daily: OCR historical (per RBNZ B-series convention)
  - Other B-series tables: government bond yields, exchange rates
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

RBNZ_UA: Final = "SONAR/2.0 (monetary-cascade; https://github.com/hugocondesa-debug/sonar-engine)"
RBNZ_OCR_SERIES: Final = "hb2-daily.csv"  # probe-validated Commit 1
RBNZ_10Y_BOND_SERIES: Final = "[probe-validated]"

class RBNZConnector(BaseConnector):
    """RBNZ statistical tables — public, descriptive UA required."""

    BASE_URL = "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/"
    CONNECTOR_ID = "rbnz"
    USER_AGENT = RBNZ_UA

    async def fetch_series(
        self,
        series_path: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[RBNZObservation]:
        """Fetch statistical series CSV from RBNZ.

        Returns list of observations filtered by date range.
        Raises DataUnavailableError if table unreachable.
        """
        url = f"{self.BASE_URL}{series_path}"
        response = await self._get(
            url,
            headers={"User-Agent": RBNZ_UA},
        )
        # Parse CSV rows → date/value tuples
        ...

    async def fetch_ocr(
        self,
        start_date: date,
        end_date: date,
    ) -> list[RBNZObservation]:
        """Convenience: OCR (Official Cash Rate) daily."""
        return await self.fetch_series(RBNZ_OCR_SERIES, start_date, end_date)

Sanity check:
  python -c "from sonar.connectors.rbnz import RBNZConnector; print('OK')"

Tests (tests/unit/test_connectors/test_rbnz.py):
- Unit: class instantiation + URL building + UA header set
- Unit: fetch_series success path (mocked CSV response)
- Unit: fetch_series 403 (UA gate) → DataUnavailableError
- Unit: fetch_series 404 → DataUnavailableError
- Unit: fetch_series malformed CSV → DataUnavailableError
- Unit: date filter behavior
- Unit: disk cache behavior
- @pytest.mark.slow live canary: probe OCR recent;
  assert ≥ 1 obs, values reasonable

Coverage rbnz.py ≥ 85%.

Cassette: tests/fixtures/cassettes/rbnz/ocr_2024_12.csv

Note: if RBNZ tables probe FAILED Commit 1, scaffold raises
DataUnavailableError + open CAL-NZ-RBNZ-TABLES for later resolution.
```

### Commit 3 — NZ Tier 1 config + r*/bc_targets YAML entries

```
feat(config): NZ Tier 1 enabled + monetary YAML entries

1. Verify docs/data_sources/country_tiers.yaml contains NZ as Tier 1.
   Expected: already present.
   If missing, add:
   - iso_code: NZ
     tier: 1
     monetary: enabled
     description: "New Zealand — Tier 1 per ADR-0005"

2. Update src/sonar/config/r_star_values.yaml — add NZ entry:
   NZ:
     value: 0.0175       # RBNZ staff research estimate ~1.5-2.0% (midpoint 1.75%)
     proxy: true
     source: "RBNZ Bulletin / Discussion Papers — neutral rate estimates 2023-2024"
     timestamp: "2024-12-01"

   Loader auto-emits R_STAR_PROXY flag.

3. Update src/sonar/config/bc_targets.yaml — add NZ entry:
   NZ:
     target: 0.02        # RBNZ target midpoint of 1-3% band
     source: "RBNZ Policy Targets Agreement (PTA) / Remit (renewed periodically)"

   Note: RBNZ uses 1-3% band with 2% midpoint explicit focus since 2012.

Unit tests:
- Loader reads NZ r* with proxy=true
- bc_targets loader reads NZ 2% target
- country_tiers_parser includes NZ in T1 list (likely already passes)

Coverage maintained.
```

### Commit 4 — M1 NZ builder with TE-primary cascade

```
feat(indices): M1 NZ builder TE-primary cascade

Add build_m1_nz_inputs to src/sonar/indices/monetary/builders.py:

async def build_m1_nz_inputs(
    fred: FredConnector,
    te: TEConnector,
    observation_date: date,
    *,
    rbnz: RBNZConnector | None = None,
    history_years: int = 15,
) -> M1Inputs:
    """Build M1 NZ inputs via TE primary cascade.

    Cascade priority (per Sprint I-patch/Sprint L/S-CA/T-AU canonical pattern):
    1. TE primary — NZ_OCR_TE_PRIMARY flag (daily RBNZ-sourced)
    2. RBNZ tables native — NZ_OCR_RBNZ_NATIVE flag (B2 CSV)
    3. FRED OECD mirror — NZ_OCR_FRED_FALLBACK_STALE + CALIBRATION_STALE

    r* via r_star_values.yaml (R_STAR_PROXY flag).
    Inflation target via bc_targets.yaml (2% RBNZ midpoint).
    """
    flags = []
    obs = None

    # Primary: TE
    if te:
        try:
            obs = await te.fetch_nz_ocr(start, end)
            if obs:
                flags.append("NZ_OCR_TE_PRIMARY")
        except (DataUnavailableError, ConnectorError):
            flags.append("NZ_OCR_TE_UNAVAILABLE")

    # Secondary: RBNZ tables
    if not obs and rbnz:
        try:
            rbnz_obs = await rbnz.fetch_ocr(start, end)
            if rbnz_obs:
                obs = [_DatedValue(...) for o in rbnz_obs]
                flags.append("NZ_OCR_RBNZ_NATIVE")
        except (DataUnavailableError, ConnectorError):
            flags.append("NZ_OCR_RBNZ_UNAVAILABLE")

    # Tertiary: FRED OECD mirror (last-resort, monthly stale)
    if not obs:
        fred_obs = await fred.fetch_series(FRED_NZ_OCR_SERIES, start, end)
        if fred_obs:
            obs = [_DatedValue(...) for o in fred_obs]
            flags.extend([
                "NZ_OCR_FRED_FALLBACK_STALE",
                "CALIBRATION_STALE",
            ])

    if not obs:
        raise ValueError("NZ OCR unavailable from TE, RBNZ, FRED")

    # r* from YAML
    r_star, r_star_is_proxy = resolve_r_star("NZ")
    if r_star_is_proxy:
        flags.append("R_STAR_PROXY")

    # Build M1Inputs ...

Constants:
FRED_NZ_OCR_SERIES: str = "IRSTCI01NZM156N"  # OECD MEI NZ short-rate
FRED_NZ_BOND_10Y_SERIES: str = "IRLTLT01NZM156N"  # OECD MEI NZ long-rate

Expose in __all__:
    "build_m1_nz_inputs",

Tests:
- Unit: TE primary success → NZ_OCR_TE_PRIMARY
- Unit: TE fails, RBNZ succeeds → NZ_OCR_RBNZ_NATIVE
- Unit: TE + RBNZ fail → FRED fallback → CALIBRATION_STALE
- Unit: all fail → ValueError
- Unit: r* loaded NZ with proxy flag
- Unit: bc_targets NZ 2% loaded

Coverage build_m1_nz_inputs ≥ 95%.
```

### Commit 5 — Pipeline integration daily_monetary_indices NZ

```
feat(pipelines): daily_monetary_indices NZ country support

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Add NZ to MONETARY_SUPPORTED_COUNTRIES:
   MONETARY_SUPPORTED_COUNTRIES = ("US", "EA", "GB", "UK", "JP", "CA", "AU", "NZ")
   # NZ follows Sprint T-AU AU pattern

2. NZ country branch routes to build_m1_nz_inputs
3. M2/M3/M4 NZ: raise NotImplementedError gracefully (pattern per Sprint L JP / S-CA CA / T-AU AU)
4. Connector lifecycle: RBNZ connector added to connectors_to_close (if ingested)

Verify --country NZ and --all-t1 (includes NZ) work.

Tests:
- Unit: pipeline invokes NZ builders when country=NZ
- Unit: NZ M2/M3/M4 graceful skip (NotImplementedError caught)
- Unit: connector_to_close includes RBNZ instance

Integration smoke @slow:
tests/integration/test_daily_monetary_nz.py:

@pytest.mark.slow
def test_daily_monetary_nz_te_primary():
    """Full pipeline NZ 2024-12-31 with TE primary cascade.

    Expected:
    - M1 NZ row persists
    - NZ_OCR_TE_PRIMARY flag present
    - R_STAR_PROXY flag present
    - policy_rate_pct daily-fresh"""

@pytest.mark.slow
def test_daily_monetary_nz_rbnz_native_fallback():
    """TE unavailable, RBNZ tables succeed. Expected NZ_OCR_RBNZ_NATIVE flag."""

Wall-clock ≤ 15s combined.

Coverage maintained.
```

### Commit 6 — M2/M4 NZ scaffolds

```
feat(indices): M2 + M4 NZ scaffolds (wire-ready, raise pending connectors)

Per Sprint L JP / Sprint S-CA CA / Sprint T-AU AU pattern — M2/M4 NZ
builders are scaffolds raising InsufficientDataError.

async def build_m2_nz_inputs(...) -> M2Inputs:
    """M2 NZ scaffold — output gap needs Stats NZ or OECD EO."""
    raise InsufficientDataError(
        "NZ M2 requires output_gap; pending Stats NZ/OECD EO connector. "
        "CAL-NZ-M2-OUTPUT-GAP tracking resolution."
    )

async def build_m4_nz_inputs(...) -> M4Inputs:
    """M4 NZ scaffold — FCI components need NZD-specific VIX, credit spreads, NEER."""
    raise InsufficientDataError(
        "NZ M4 requires VIX-NZ / credit-spread-NZ / NEER-NZD; all deferred. "
        "CAL-NZ-M4-FCI tracking full wire-up."
    )

Tests:
- Unit: build_m2_nz_inputs raises InsufficientDataError
- Unit: build_m4_nz_inputs raises InsufficientDataError
- Unit: error message references correct CAL items

Coverage maintained.
```

### Commit 7 — Retrospective + CAL items opened

```
docs(planning+backlog): Week 9 Sprint U-NZ RBNZ connector retrospective

File: docs/planning/retrospectives/week9-sprint-u-nz-connector-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- Empirical findings:
  - TE NZ OCR HistoricalDataSymbol: [probe result]
  - RBNZ tables reachability: [success/issues/partial]
  - UA-gate status (per Sprint T-AU lesson)
  - FRED OECD NZ mirror series validated
- Coverage delta
- Live canary outcomes
- HALT triggers fired / not fired
- Deviations from brief
- M2 T1 progression: 11 → 12 countries
- NZ monetary indices operational:
  - M1: live via TE cascade (RBNZ tables if probe succeeded)
  - M2: scaffold (CAL-NZ-M2-OUTPUT-GAP)
  - M3: deferred (CAL-NZ-M3)
  - M4: scaffold (CAL-NZ-M4-FCI)
- Pattern validation:
  - TE-primary cascade continues canonical
  - RBNZ tables similar to RBA CSV pattern; UA-gate lesson applied
- Isolated worktree: zero collision incidents with Sprint V-CH parallel
- Merge strategy: branch sprint-u-nz-connector → main fast-forward (or rebase if V-CH merged first)
- New CAL items opened:
  - CAL-NZ-M2-OUTPUT-GAP
  - CAL-NZ-M3
  - CAL-NZ-M4-FCI
  - CAL-NZ-RBNZ-TABLES (if probe failed)

Open CAL-NZ-* items formally in docs/backlog/calibration-tasks.md.

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git merge --ff-only sprint-u-nz-connector
  git push origin main
```

---

## 5. HALT triggers (atomic)

0. **TE NZ OCR empirical probe fails** — if TE returns no NZ data or unexpected format, HALT + surface. Alternative: FRED primary + accept monthly-stale with explicit operator warning.
1. **HistoricalDataSymbol mismatch** — if TE returns different symbol than probe found, do NOT assume benign. HALT.
2. **RBNZ tables unreachable** — possible; apply UA lesson. If still unreachable, scaffold with DataUnavailableError + open CAL-NZ-RBNZ-TABLES. Not a HALT.
3. **RBNZ CSV schema divergent from RBA** — if B-series format significantly different (e.g. XLS-only, no CSV), scope Commit 2 narrow to OCR only; defer others.
4. **NZ in country_tiers.yaml Tier mismatch** — if NZ marked Tier 2+ instead of Tier 1, HALT + verify against ADR-0005.
5. **r* NZ value uncertainty** — use RBNZ staff research estimate + R_STAR_PROXY flag. Document source in YAML comment.
6. **M2/M4 scaffolds pattern** — per precedent, raise InsufficientDataError. Verify pattern replication.
7. **TE rate limits** during live canaries — tenacity handles; document in retro if persistent.
8. **Coverage regression > 3pp** → HALT.
9. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
10. **Concurrent Sprint V-CH touches files in Sprint U scope** (likely minor conflicts in te.py/builders.py/pipelines/daily_monetary_indices.py/YAMLs/backlog) → reconcile via rebase post-merge.

---

## 6. Acceptance

### Global sprint-end
- [ ] 6-8 commits pushed to branch `sprint-u-nz-connector`
- [ ] `src/sonar/connectors/rbnz.py` shipped + tested (even if RBNZ probe partial)
- [ ] `fetch_nz_ocr` TE wrapper + source-drift guard shipped
- [ ] TE NZ HistoricalDataSymbol validated + documented
- [ ] RBNZ tables reachability documented (probe result)
- [ ] NZ Tier 1 in country_tiers.yaml
- [ ] r_star_values.yaml NZ entry added (with proxy: true)
- [ ] bc_targets.yaml NZ entry present (2%)
- [ ] `build_m1_nz_inputs` cascade operational
- [ ] M2 + M4 NZ scaffolds shipped (raise InsufficientDataError)
- [ ] `daily_monetary_indices.py --country NZ` runs end-to-end
- [ ] Live canaries PASS: TE NZ OCR + NZ monetary pipeline
- [ ] Coverage rbnz.py ≥ 85%, builders.py NZ path ≥ 95%
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week9-sprint-u-nz-connector-report.md`

**Final tmux echo**:
```
SPRINT U-NZ NEW ZEALAND CONNECTOR DONE: N commits on branch sprint-u-nz-connector
TE HistoricalDataSymbol NZ validated: [symbol]
RBNZ tables reachability: [success / issues / partial]
NZ monetary: M1 (cascade), M2/M4 (scaffolds), M3 (deferred)
M2 T1 progression: 11 → 12 countries
HALT triggers: [list or "none"]
Merge: git checkout main && git merge --ff-only sprint-u-nz-connector
Artifact: docs/planning/retrospectives/week9-sprint-u-nz-connector-report.md
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

### TE primary canonical (Week 8-9 lesson, 5th consecutive country)
All country expansion defaults to TE primary → native override → FRED last-resort. Pattern stable.

### RBNZ tables similar to RBA (Sprint T-AU template most relevant)
Both Southern Hemisphere central banks publish CSVs. Expect similar structure (header + date + value columns). UA-gate applied preventively per Sprint T-AU Akamai lesson.

### Pattern replication discipline (5th iteration)
Sprint T-AU AU shipped earlier today (Day 2). This sprint mirrors closely:
- TE wrapper with source-drift guard
- Native connector (CSV)
- M1 builder with cascade
- M2/M4 scaffolds
- Pipeline integration
- Retro

### r* NZ is explicit proxy
RBNZ staff research varies ~1.5-2.0%; midpoint 1.75% reasonable + R_STAR_PROXY flag.

### M3 NZ deferred
Per precedent, M3 needs persisted NSS forwards + expected-inflation for country. NZ overlays not yet shipped.

### Isolated worktree workflow
Sprint U-NZ operates entirely in `/home/macro/projects/sonar-wt-sprint-u`. Branch: `sprint-u-nz-connector`.

### Sprint V-CH parallel
Runs in `sonar-wt-sprint-v`. Shared-file append zones in te.py/builders.py/pipelines/YAMLs = rebase-expected post-merge. First merge wins; second rebases.

---

*End of Week 9 Sprint U-NZ New Zealand connector brief. 6-8 commits. NZ T1 shipped with TE-primary cascade.*
