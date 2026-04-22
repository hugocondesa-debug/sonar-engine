# Week 9 Sprint S-CA — Canada BoC Connector + M1 CA (TE-primary Cascade)

**Target**: Ship Bank of Canada connector + CA country enablement for M1 monetary. M2 T1 progression from 9 to 10 countries. TE-primary cascade per Sprint I-patch/Sprint L lesson (canonical pattern for country expansion).
**Priority**: HIGH (M2 T1 Completionist progression — 1 of 7 remaining T1 countries)
**Budget**: 3-4h CC autonomous
**Commits**: ~6-8
**Base**: branch `sprint-s-ca-connector` (isolated worktree `/home/macro/projects/sonar-wt-sprint-s`)
**Concurrency**: Parallel to Sprint P CAL-128-FOLLOWUP in worktree `sonar-wt-sprint-p`. See §3.

---

## 1. Scope

In:
- `src/sonar/connectors/boc.py` — new BoC Valet API connector
- **Cascade strategy per Sprint L pattern (TE-primary default, per Sprint I-patch lesson)**:
  1. **Primary: TE native CA Bank Rate / GoC yields** (daily, BoC-sourced via TE)
  2. **Secondary: BoC Valet API native** (public API, well-documented, likely reachable unlike BoE/BoJ)
  3. **Tertiary: FRED OECD mirror** (monthly-lagged; last-resort with `CALIBRATION_STALE` flag)
- TE wrapper `fetch_ca_bank_rate` with HistoricalDataSymbol source-drift guard
- Core series empirical discovery:
  - CA Bank Rate (overnight target rate): probe Commit 1 (likely `CABANKRATE` or similar)
  - CA 10Y GoC yield: TE `GCAN10YR:IND` (verify existing mapping)
  - CA CPI + unemployment: TE generic `fetch_indicator(country="CA", ...)` pattern
- Empirical BoC Valet API probe (time-boxed 20 min; expected to succeed given public API docs)
- CA country entry in `docs/data_sources/country_tiers.yaml` (verify Tier 1 per ADR-0005)
- r* CA entry in `src/sonar/config/r_star_values.yaml` (~0.025 per FRB-CA/BoC staff research)
- CA inflation target in `src/sonar/config/bc_targets.yaml` (0.02 per BoC 2% mandate)
- M1 CA builder via TE-primary cascade (M2/M4 scaffolds only; full wiring deferred CAL-CA-*)
- Pipeline integration `daily_monetary_indices.py --country CA`
- Cassette + `@pytest.mark.slow` live canary for TE + BoC paths
- Retrospective

Out:
- M2 CA live (output gap requires Statistics Canada OR OECD EO connector — CAL-CA-M2-OUTPUT-GAP)
- M3 CA (requires persisted NSS forwards + expected-inflation for CA — CAL-CA-M3)
- M4 CA (FCI — requires VIX-CA, credit spreads Canada, CAD NEER — CAL-CA-M4-FCI)
- CA ERP per-country live (deferred Phase 2+)
- CA CRP (BENCHMARK via spec; sovereign yield spread automatic)
- CA rating-spread (AAA baseline sovereign)
- L3 economic indices CA (E1/E2/E3/E4 — separate sprint)
- L3 credit indices CA (BIS coverage existing via Sprint 2b; verify but not new work)
- L3 financial indices CA (F1-F4 US proxies; Phase 2+)

---

## 2. Spec reference

Authoritative:
- `docs/data_sources/country_tiers.yaml` — CA should be Tier 1 per ADR-0005
- `docs/specs/indices/monetary/M1-effective-rates.md` §2 — monetary inputs per country
- `docs/specs/indices/monetary/M2-taylor-gaps.md` §2 — r*, policy rate, inflation inputs
- `docs/specs/conventions/patterns.md` — Pattern 4 (Aggregator-primary with native-override)
- `docs/planning/retrospectives/week8-sprint-i-patch-te-cascade-report.md` — **TE primary is canonical for all country expansion**
- `docs/planning/retrospectives/week8-sprint-l-boj-connector-report.md` — **Sprint L JP pattern (most recent)**
- SESSION_CONTEXT §Critical technical reference — TE HistoricalDataSymbol validated list
- `src/sonar/connectors/boj.py` — pattern template (Sprint L shipped, cleanest reference)
- `src/sonar/connectors/te.py` — existing CA country mappings

**Pre-flight requirement**: Commit 1 CC:
1. Verify TE CA mappings: `"CA": "canada"` (indicator) + `"CA": "GCAN10YR:IND"` (bonds) already exist from Sprint 1
2. Probe TE CA Bank Rate empirically:
   ```bash
   set -a && source .env && set +a
   curl -s "https://api.tradingeconomics.com/historical/country/canada/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'
   ```
3. Document TE HistoricalDataSymbol for CA Bank Rate (probe finding)
4. Time-boxed 20 min BoC Valet API probe:
   ```bash
   # Valet API public — no auth
   curl -s "https://www.bankofcanada.ca/valet/observations/V39079?recent=10" | jq '.'
   # V39079 = Canada overnight rate (Bank of Canada canonical series)
   # Alternative: V122530 = Bank rate (official policy rate)
   ```
5. If Valet probe SUCCEEDS → implement BoC connector as secondary in cascade
6. Read `boj.py` as template (Sprint L most recent pattern)
7. Read `te.py` JP/UK wrappers for pattern
8. Verify CA in `country_tiers.yaml`; if missing, add as Tier 1

Document findings in Commit 1 body.

Existing assets:
- `TEConnector` generic + wrappers (7 from Sprint 1 + UK Bank Rate Sprint I-patch + JP Bank Rate Sprint L)
- FRED connector has `fetch_series` for any series ID
- `country_tiers.yaml` canonical (ISO alpha-2 convention post-Sprint O)
- `bc_targets.yaml` + `r_star_values.yaml` shipped Week 6 Sprint 1b

---

## 3. Concurrency — parallel protocol with Sprint P + ISOLATED WORKTREES

**Sprint S-CA operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-s`

Sprint P operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-p`

**Critical workflow**:
1. Sprint S-CA CC starts by `cd /home/macro/projects/sonar-wt-sprint-s`
2. All file operations happen in this worktree
3. Branch name: `sprint-s-ca-connector`
4. Pushes to `origin/sprint-s-ca-connector`
5. Final merge to main via fast-forward post-sprint-close

**File scope Sprint S-CA**:
- `src/sonar/connectors/boc.py` NEW
- `src/sonar/connectors/te.py` APPEND (new `fetch_ca_bank_rate` wrapper + CA-specific constants)
- `src/sonar/indices/monetary/builders.py` APPEND (add CA builders — `build_m1_ca_inputs`)
- `docs/data_sources/country_tiers.yaml` — verify/add CA entry (likely exists)
- `src/sonar/config/r_star_values.yaml` — add CA entry
- `src/sonar/config/bc_targets.yaml` — verify/add CA entry
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (add CA to MONETARY_SUPPORTED_COUNTRIES + CA country dispatch)
- Tests:
  - `tests/unit/test_connectors/test_boc.py` NEW
  - `tests/unit/test_connectors/test_te_indicator.py` APPEND (CA Bank Rate wrapper tests)
  - `tests/unit/test_indices/monetary/test_builders.py` APPEND (CA builder tests)
  - `tests/unit/test_pipelines/test_daily_monetary_indices.py` APPEND (CA country)
  - `tests/integration/test_daily_monetary_ca.py` NEW
  - `tests/fixtures/cassettes/boc/` + `tests/cassettes/connectors/te_ca_bank_rate_*.json`
- `docs/planning/retrospectives/week9-sprint-s-ca-connector-report.md` NEW

**Sprint P scope** (for awareness, DO NOT TOUCH):
- `src/sonar/cycles/financial_fcs.py` — Sprint P rename UK → GB
- `src/sonar/overlays/crp.py` — Sprint P
- `src/sonar/overlays/live_assemblers.py` — Sprint P
- `src/sonar/pipelines/daily_cost_of_capital.py` — Sprint P
- NOT builders.py (CAL-128 closed; Sprint P doesn't need to touch it)
- NOT connectors/te.py (no UK refs remaining Sprint P scope; CA additions Sprint S only)

**Zero file overlap confirmed**. Different domains entirely.

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-sprint-s && git pull origin main --rebase`

**Push race**: normal `git push origin sprint-s-ca-connector`. Zero collisions expected.

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-s-ca-connector
git push origin main
```
Fast-forward expected.

---

## 4. Commits

### Commit 1 — Pre-flight + TE CA Bank Rate wrapper

```
feat(connectors): TE fetch_ca_bank_rate wrapper + source-drift guard

Pre-flight: probe TE CA Bank Rate + verify BoC Valet API reachability.

Expected probe (document findings commit body):
  set -a && source .env && set +a
  curl -s "https://api.tradingeconomics.com/historical/country/canada/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'

Document in commit body:
- Actual HistoricalDataSymbol returned (likely CAIRYY or similar)
- Response format (date + value)
- Historical range (expected: daily since BoC inflation-targeting era ~1991)
- Latest value sanity check (should match current BoC policy rate ~3.25% Dec 2024)

BoC Valet API probe (time-boxed 20 min):
  curl -s "https://www.bankofcanada.ca/valet/observations/V39079?recent=10" | jq '.'
  curl -s "https://www.bankofcanada.ca/valet/observations/V122530?recent=10" | jq '.'
  # V39079 = overnight rate, V122530 = bank rate
  # Document: reachability, response format, series stability

Extend src/sonar/connectors/te.py:

CA_BANK_RATE_EXPECTED_SYMBOL: Final = "[EMPIRICAL — probe result]"
CA_BANK_RATE_INDICATOR: Final = "interest rate"

async def fetch_ca_bank_rate(
    self,
    start: date,
    end: date,
) -> list[TEIndicatorObservation]:
    """Fetch CA overnight target rate / Bank Rate from TE.

    TE sources from BoC directly — avoids FRED OECD mirror monthly lag.
    Validates HistoricalDataSymbol matches expected per Sprint 3 Quick
    Wins source-drift discipline.

    Raises DataUnavailableError("source drift") if HistoricalDataSymbol
    != CA_BANK_RATE_EXPECTED_SYMBOL.
    """
    obs = await self.fetch_indicator(
        country="CA",
        indicator=CA_BANK_RATE_INDICATOR,
        start=start,
        end=end,
    )
    if obs and obs[0].historical_data_symbol != CA_BANK_RATE_EXPECTED_SYMBOL:
        raise DataUnavailableError(...)
    return obs

Sanity check commit body:
  python -c "from sonar.connectors.te import TEConnector; c = TEConnector(api_key='x'); print(hasattr(c, 'fetch_ca_bank_rate'))"

Tests (tests/unit/test_connectors/test_te_indicator.py append):
- Unit: happy path mocked response
- Unit: HistoricalDataSymbol mismatch → DataUnavailableError
- Unit: empty response → empty list
- @pytest.mark.slow live canary: fetch Bank Rate 2024-12-01..31 →
  assert ≥ 1 obs, value ∈ [0.25%, 6.0%] (reasonable range for Dec 2024)

Cassette: tests/cassettes/connectors/te_ca_bank_rate_2024_12.json

Coverage te.py additions ≥ 90%.
```

### Commit 2 — BoC Valet connector

```
feat(connectors): BoC Valet API connector (public, unauthenticated)

Create src/sonar/connectors/boc.py:

"""Bank of Canada Valet API connector.

Public API — no auth required. Handles Canadian macro time series.
Fallback cascade per Sprint L pattern: TE → BoC Valet → FRED.

Empirical probe findings (Commit 1):
- Base URL: https://www.bankofcanada.ca/valet/
- Availability: [document — reachable / CDN-cached]
- Response format: JSON
- Auth: public

Key series IDs (probe-validated Commit 1-2):
- V39079: Canadian overnight rate (target)
- V122530: Bank rate (official)
- V122544: Prime business rate
- V80691333: CPI headline YoY
- V39063: GoC 10Y bond yield
"""

from __future__ import annotations
from datetime import date
from typing import Final

from sonar.connectors.base import BaseConnector
from sonar.connectors.exceptions import (
    DataUnavailableError,
    ConnectorError,
)

BOC_OVERNIGHT_RATE: Final = "V39079"
BOC_BANK_RATE: Final = "V122530"
BOC_PRIME_RATE: Final = "V122544"
BOC_CPI_HEADLINE: Final = "V80691333"
BOC_GOC_10Y: Final = "V39063"

class BoCConnector(BaseConnector):
    """BoC Valet API — public, no auth."""

    BASE_URL = "https://www.bankofcanada.ca/valet/"
    CONNECTOR_ID = "boc"

    async def fetch_series(
        self,
        series_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ValetObservation]:
        """Fetch time series from BoC Valet API.

        Endpoint: /observations/{series_id}?start_date=...&end_date=...
        Returns list of observations.
        Raises DataUnavailableError if series empty, 404.
        """
        url = f"{self.BASE_URL}observations/{series_id}"
        params = {}
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()

        response = await self._get(url, params=params)
        # Parse response.observations
        ...

    async def fetch_overnight_rate(
        self,
        start_date: date,
        end_date: date,
    ) -> list[ValetObservation]:
        """Convenience: overnight target rate."""
        return await self.fetch_series(BOC_OVERNIGHT_RATE, start_date, end_date)

    async def fetch_10y_goc_yield(
        self,
        start_date: date,
        end_date: date,
    ) -> list[ValetObservation]:
        """Convenience: 10Y Government of Canada bond yield."""
        return await self.fetch_series(BOC_GOC_10Y, start_date, end_date)

Sanity check:
  python -c "from sonar.connectors.boc import BoCConnector; print('OK')"

Tests (tests/unit/test_connectors/test_boc.py):
- Unit: class instantiation + URL building
- Unit: fetch_series success path (mocked Valet response)
- Unit: fetch_series 404 → DataUnavailableError
- Unit: fetch_series empty observations → DataUnavailableError
- Unit: disk cache behavior
- @pytest.mark.slow live canary: probe BOC_OVERNIGHT_RATE recent 10 obs;
  assert ≥ 1 obs, values reasonable

Coverage boc.py ≥ 85%.

Cassette: tests/fixtures/cassettes/boc/overnight_rate_2024_12.json
```

### Commit 3 — CA Tier 1 config + r*/bc_targets YAML entries

```
feat(config): CA Tier 1 enabled + monetary YAML entries

1. Verify docs/data_sources/country_tiers.yaml contains CA as Tier 1.
   Expected: already present from Sprint 2b (BIS credit coverage).
   If missing, add:
   - iso_code: CA
     tier: 1
     monetary: enabled
     description: "Canada — Tier 1 per ADR-0005"

2. Update src/sonar/config/r_star_values.yaml — add CA entry:
   CA:
     value: 0.025       # FRB-CA/BoC staff research estimate ~2.5%
     proxy: true
     source: "BoC Economic Review / FRB-CA staff working papers ~2024"
     timestamp: "2024-12-01"

   Loader auto-emits R_STAR_PROXY flag.

3. Verify src/sonar/config/bc_targets.yaml CA entry:
   CA:
     target: 0.02        # BoC 2% mandate
     source: "BoC Inflation-Control Target Agreement (renewed 2021)"
   If missing, add.

Unit tests:
- Loader reads CA r* with proxy=true
- bc_targets loader reads CA 2% target
- country_tiers_parser includes CA in T1 list (likely already passes)

Coverage maintained.
```

### Commit 4 — M1 CA builder with TE-primary cascade

```
feat(indices): M1 CA builder TE-primary cascade

Add build_m1_ca_inputs to src/sonar/indices/monetary/builders.py:

async def build_m1_ca_inputs(
    fred: FredConnector,
    te: TEConnector,
    observation_date: date,
    *,
    boc: BoCConnector | None = None,
    history_years: int = 15,
) -> M1Inputs:
    """Build M1 CA inputs via TE primary cascade.

    Cascade priority (per Sprint I-patch/Sprint L canonical pattern):
    1. TE primary — CA_BANK_RATE_TE_PRIMARY flag (daily BoC-sourced)
    2. BoC Valet native — CA_BANK_RATE_BOC_NATIVE flag (V39079 overnight rate)
    3. FRED OECD mirror — CA_BANK_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE

    r* via r_star_values.yaml (R_STAR_PROXY flag).
    Inflation target via bc_targets.yaml (2% BoC).
    """
    # Pseudocode mirroring Sprint L JP cascade
    flags = []
    obs = None

    # Primary: TE
    if te:
        try:
            obs = await te.fetch_ca_bank_rate(start, end)
            if obs:
                flags.append("CA_BANK_RATE_TE_PRIMARY")
        except (DataUnavailableError, ConnectorError):
            flags.append("CA_BANK_RATE_TE_UNAVAILABLE")

    # Secondary: BoC Valet (if reachable)
    if not obs and boc:
        try:
            boc_obs = await boc.fetch_overnight_rate(start, end)
            if boc_obs:
                obs = [_DatedValue(...) for o in boc_obs]
                flags.append("CA_BANK_RATE_BOC_NATIVE")
        except (DataUnavailableError, ConnectorError):
            flags.append("CA_BANK_RATE_BOC_UNAVAILABLE")

    # Tertiary: FRED OECD mirror (last-resort, monthly stale)
    if not obs:
        fred_obs = await fred.fetch_series(FRED_CA_BANK_RATE_SERIES, start, end)
        if fred_obs:
            obs = [_DatedValue(...) for o in fred_obs]
            flags.extend([
                "CA_BANK_RATE_FRED_FALLBACK_STALE",
                "CALIBRATION_STALE",
            ])

    if not obs:
        raise ValueError("CA Bank Rate unavailable from TE, BoC, FRED")

    # r* from YAML
    r_star, r_star_is_proxy = resolve_r_star("CA")
    if r_star_is_proxy:
        flags.append("R_STAR_PROXY")

    # Build M1Inputs ...

Constants:
FRED_CA_BANK_RATE_SERIES: str = "IRSTCI01CAM156N"  # OECD MEI CA short-rate
FRED_CA_GOC_10Y_SERIES: str = "IRLTLT01CAM156N"    # OECD MEI CA long-rate

Expose in __all__:
    "build_m1_ca_inputs",

Tests:
- Unit: TE primary success → CA_BANK_RATE_TE_PRIMARY
- Unit: TE fails, BoC succeeds → CA_BANK_RATE_BOC_NATIVE
- Unit: TE + BoC fail → FRED fallback → CALIBRATION_STALE
- Unit: all fail → ValueError
- Unit: r* loaded CA with proxy flag
- Unit: bc_targets CA 2% loaded

Coverage build_m1_ca_inputs ≥ 95%.
```

### Commit 5 — Pipeline integration daily_monetary_indices CA

```
feat(pipelines): daily_monetary_indices CA country support

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Add CA to MONETARY_SUPPORTED_COUNTRIES:
   MONETARY_SUPPORTED_COUNTRIES = ("US", "EA", "GB", "UK", "JP", "CA")
   # CA follows Sprint L JP pattern

2. CA country branch routes to build_m1_ca_inputs
3. M2/M3/M4 CA: raise NotImplementedError gracefully (pattern per Sprint L JP)
4. Connector lifecycle: BoC connector added to connectors_to_close (if ingested)

Verify --country CA and --all-t1 (includes CA) work.

Tests:
- Unit: pipeline invokes CA builders when country=CA
- Unit: CA M2/M3/M4 graceful skip (NotImplementedError caught)
- Unit: connector_to_close includes BoC instance

Integration smoke @slow:
tests/integration/test_daily_monetary_ca.py:

@pytest.mark.slow
def test_daily_monetary_ca_te_primary():
    """Full pipeline CA 2024-12-31 with TE primary cascade.

    Expected:
    - M1 CA row persists
    - CA_BANK_RATE_TE_PRIMARY flag present
    - R_STAR_PROXY flag present
    - policy_rate_pct daily-fresh"""

@pytest.mark.slow
def test_daily_monetary_ca_boc_native_fallback():
    """TE unavailable, BoC Valet succeeds. Expected CA_BANK_RATE_BOC_NATIVE flag."""

Wall-clock ≤ 15s combined.

Coverage maintained.
```

### Commit 6 — M2/M4 CA scaffolds (pattern per Sprint L)

```
feat(indices): M2 + M4 CA scaffolds (wire-ready, raise pending connectors)

Per Sprint L JP pattern — M2/M4 CA builders are scaffolds raising
InsufficientDataError until full connectors wired (CAL-CA-M2-OUTPUT-GAP,
CAL-CA-M4-FCI).

async def build_m2_ca_inputs(...) -> M2Inputs:
    """M2 CA scaffold — output gap needs Statistics Canada or OECD EO."""
    raise InsufficientDataError(
        "CA M2 requires output_gap; pending StatCan/OECD EO connector. "
        "CAL-CA-M2-OUTPUT-GAP tracking resolution."
    )

async def build_m4_ca_inputs(...) -> M4Inputs:
    """M4 CA scaffold — FCI components need CAD-specific VIX, credit spreads, NEER."""
    raise InsufficientDataError(
        "CA M4 requires VIX-CA / credit-spread-CA / NEER-CAD; all deferred. "
        "CAL-CA-M4-FCI tracking full wire-up."
    )

Tests:
- Unit: build_m2_ca_inputs raises InsufficientDataError
- Unit: build_m4_ca_inputs raises InsufficientDataError
- Unit: error message references correct CAL items

Import InsufficientDataError from exceptions module.

Coverage maintained.
```

### Commit 7 — Retrospective + CAL items opened

```
docs(planning): Week 9 Sprint S-CA Canada connector retrospective

File: docs/planning/retrospectives/week9-sprint-s-ca-connector-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- Empirical findings:
  - TE CA Bank Rate HistoricalDataSymbol: [probe result]
  - BoC Valet API reachability: [success/issues]
  - FRED OECD CA mirror series validated
- Coverage delta
- Live canary outcomes
- HALT triggers fired / not fired
- Deviations from brief
- M2 T1 progression: 9 → 10 countries
- CA monetary indices operational:
  - M1: live via TE cascade (BoC Valet functional if probe succeeded)
  - M2: scaffold (CAL-CA-M2-OUTPUT-GAP)
  - M3: deferred (CAL-CA-M3)
  - M4: scaffold (CAL-CA-M4-FCI)
- Pattern validation:
  - TE-primary cascade continues canonical
  - BoC Valet = most robust native API vs BoE/BoJ gates (precedent for reachable natives)
- Isolated worktree: zero collision incidents with Sprint P parallel
- Merge strategy: branch sprint-s-ca-connector → main fast-forward
- New CAL items opened:
  - CAL-CA-M2-OUTPUT-GAP: CA M2 output gap via StatCan/OECD EO
  - CAL-CA-M3: CA M3 market expectations (needs CA NSS + expinf overlays)
  - CAL-CA-M4-FCI: CA M4 FCI full component wiring

Close CAL-CA-* items formally in docs/backlog/calibration-tasks.md.

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git merge --ff-only sprint-s-ca-connector
  git push origin main
```

---

## 5. HALT triggers (atomic)

0. **TE CA Bank Rate empirical probe fails** — if TE returns no CA data or unexpected format, HALT + surface. Alternative: FRED primary + accept monthly-stale with explicit operator warning.
1. **HistoricalDataSymbol mismatch** — if TE returns different symbol than probe found, do NOT assume benign. HALT.
2. **BoC Valet API unreachable** — unlikely given well-documented public API. If unreachable, scaffold raises gracefully. Not a HALT.
3. **CA in country_tiers.yaml Tier mismatch** — if CA marked Tier 2+ instead of Tier 1, HALT + verify against ADR-0005.
4. **r* CA value uncertainty** — use FRB-CA/BoC staff research estimate + R_STAR_PROXY flag. Document source in YAML comment.
5. **M2/M4 scaffolds — pattern correct?** — per Sprint L JP, raise InsufficientDataError. Verify pattern replication.
6. **TE rate limits** during live canaries — tenacity handles; if persistent, mark slow + document in retro.
7. **Coverage regression > 3pp** → HALT.
8. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
9. **Concurrent Sprint P touches files in Sprint S scope** (shouldn't per §3) → reconcile via rebase.

---

## 6. Acceptance

### Global sprint-end
- [ ] 6-8 commits pushed to branch `sprint-s-ca-connector`
- [ ] `src/sonar/connectors/boc.py` shipped + tested
- [ ] `fetch_ca_bank_rate` TE wrapper + source-drift guard shipped
- [ ] TE CA HistoricalDataSymbol validated + documented
- [ ] BoC Valet API reachability documented (probe result)
- [ ] CA Tier 1 in country_tiers.yaml
- [ ] r_star_values.yaml CA entry added (with proxy: true)
- [ ] bc_targets.yaml CA entry present (2%)
- [ ] `build_m1_ca_inputs` cascade operational
- [ ] M2 + M4 CA scaffolds shipped (raise InsufficientDataError)
- [ ] `daily_monetary_indices.py --country CA` runs end-to-end
- [ ] Live canaries PASS: TE CA Bank Rate + CA monetary pipeline
- [ ] Coverage boc.py ≥ 85%, builders.py CA path ≥ 95%
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week9-sprint-s-ca-connector-report.md`

**Final tmux echo**:
```
SPRINT S-CA CANADA CONNECTOR DONE: N commits on branch sprint-s-ca-connector
TE HistoricalDataSymbol CA validated: [symbol]
BoC Valet API reachability: [success / issues]
CA monetary: M1 (cascade), M2/M4 (scaffolds), M3 (deferred)
M2 T1 progression: 9 → 10 countries
HALT triggers: [list or "none"]
Merge: git checkout main && git merge --ff-only sprint-s-ca-connector
Artifact: docs/planning/retrospectives/week9-sprint-s-ca-connector-report.md
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

### TE primary is canonical (Sprint I-patch/Sprint L lesson)
All country expansion defaults to TE primary → native override → FRED last-resort.

### BoC Valet API is well-documented public API
Unlike BoE/BoJ (gated), BoC Valet is explicitly designed for programmatic access. Probe expected to succeed. If so, Valet becomes meaningful secondary (not just scaffold).

### Pattern replication discipline
Sprint L JP shipped recent. This sprint replicates pattern closely:
- TE wrapper with source-drift guard
- Native connector with @slow canaries
- M1 builder with cascade
- M2/M4 scaffolds raising InsufficientDataError
- Pipeline integration
- Retro

### r* CA is explicit proxy
FRB-CA/BoC staff research varies; ~2.5% reasonable estimate + R_STAR_PROXY flag + YAML citation.

### M3 CA deferred
Per Sprint L JP precedent, M3 needs persisted NSS forwards + expected-inflation for country. CA overlays not yet shipped — CAL-CA-M3 analog pattern.

### Isolated worktree workflow
Sprint S-CA operates entirely in `/home/macro/projects/sonar-wt-sprint-s`. Branch: `sprint-s-ca-connector`. Final merge via fast-forward.

### Sprint P parallel
Runs in `sonar-wt-sprint-p`. Different concerns (CA addition vs overlay/cycle UK rename). Zero file overlap per §3.

---

*End of Week 9 Sprint S-CA Canada connector brief. 6-8 commits. CA T1 shipped with TE-primary cascade.*
