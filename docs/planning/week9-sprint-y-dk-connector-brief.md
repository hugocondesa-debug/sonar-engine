# Week 9 Sprint Y-DK — Denmark Danmarks Nationalbank Connector + M1 DK (M2 T1 COMPLETE)

**Target**: Ship Danmarks Nationalbank connector + DK country enablement for M1 monetary. M2 T1 progression from 15 to **16 countries — M2 T1 COMPLETE milestone**. TE-primary cascade per canonical pattern. DK unique: DKK EUR-pegged (DKK/EUR ±2.25% band since 1999), simpler inflation/target alignment.
**Priority**: HIGH (M2 T1 Completionist COMPLETION — last T1 country)
**Budget**: 3-4h CC autonomous
**Commits**: ~6-8
**Base**: branch `sprint-y-dk-connector` (isolated worktree `/home/macro/projects/sonar-wt-sprint-y`)
**Concurrency**: Parallel to Sprint Z-WEEK9-RETRO meta-retrospective in worktree `sonar-wt-sprint-z`. See §3.

---

## 1. Scope

In:
- `src/sonar/connectors/nationalbanken.py` — new Danmarks Nationalbank connector
- **Cascade strategy per canonical pattern (TE-primary default)**:
  1. **Primary: TE native DK Policy Rate / Danish Gov bond yields** (daily, Nationalbanken-sourced via TE)
  2. **Secondary: Nationalbanken Statbank API** (public — https://www.statbank.dk/)
  3. **Tertiary: FRED OECD mirror** (monthly-lagged; last-resort with `CALIBRATION_STALE` flag)
- TE wrapper `fetch_dk_policy_rate` with HistoricalDataSymbol source-drift guard
- Core series empirical discovery:
  - DK Policy Rate (Nationalbankens Udlånsrente / Lending Rate): probe Commit 1
  - DK 10Y Government Bond yield: TE `GDDK10YR:IND` or similar (verify existing mapping)
  - DK CPI + unemployment: TE generic `fetch_indicator(country="DK", ...)` pattern
- Empirical Nationalbanken Statbank API probe (time-boxed 20 min)
  - Statbank API pattern: `https://api.statbank.dk/v1/data/<table>/JSON?...`
  - Documentation: `https://www.statbank.dk/statbank5a/default.asp?w=1920` + API docs
- DK country entry in `docs/data_sources/country_tiers.yaml` (verify Tier 1 per ADR-0005)
- r* DK entry in `src/sonar/config/r_star_values.yaml` (~0.5-1.0% per Nationalbanken research — EA-anchored via peg)
- DK inflation target in `src/sonar/config/bc_targets.yaml` — **DK uses ECB target via DKK/EUR peg** (Nationalbanken maintains peg, does NOT have explicit domestic inflation target)
- M1 DK builder via TE-primary cascade (M2/M4 scaffolds only; full wiring deferred CAL-DK-*)
- Pipeline integration `daily_monetary_indices.py --country DK`
- Cassette + `@pytest.mark.slow` live canary for TE + Nationalbanken paths
- **Negative-rate era** (DK had -0.75% trough 2015-2022, longer than CH) — validation required per Sprint V-CH/W-SE pattern
- Retrospective

Out:
- M2 DK live (output gap requires Statistics Denmark / OECD EO — CAL-DK-M2-OUTPUT-GAP)
- M3 DK (requires persisted NSS forwards + expected-inflation for DK — CAL-DK-M3)
- M4 DK (FCI — requires VIX-DK, credit spreads DK, DKK NEER — CAL-DK-M4-FCI)
- DK ERP per-country live (deferred Phase 2+)
- DK CRP (BENCHMARK via spec; sovereign yield spread automatic)
- L3 credit indices DK (BIS coverage via Sprint AA fix)
- Krippner shadow-rate connector (Phase 2+ — shared with CH, SE)
- **DKK/EUR peg stability analysis** (Phase 2+ research topic)

---

## 2. Spec reference

Authoritative:
- `docs/data_sources/country_tiers.yaml` — DK should be Tier 1 per ADR-0005
- `docs/specs/indices/monetary/M1-effective-rates.md` §2
- `docs/specs/indices/monetary/M2-taylor-gaps.md` §2
- `docs/specs/conventions/patterns.md` — Pattern 4
- `docs/planning/retrospectives/week9-sprint-w-se-connector-report.md` — **Sprint W-SE negative-rate era pattern (most relevant — SE also Nordic negative)**
- `docs/planning/retrospectives/week9-sprint-v-ch-connector-report.md` — Sprint V-CH first negative-rate precedent
- `docs/planning/retrospectives/week9-sprint-x-no-connector-report.md` — Sprint X-NO SDMX-JSON API pattern
- `src/sonar/connectors/riksbank.py` — Sprint W-SE JSON REST + negative-rate handling (closest template)
- `src/sonar/connectors/snb.py` — Sprint V-CH data-portal template alt
- `src/sonar/connectors/te.py` — existing DK country mappings

**Pre-flight requirement**: Commit 1 CC:
1. Verify TE DK mappings: `"DK": "denmark"` (indicator) + DK bond mapping likely exists from Sprint 1
2. Probe TE DK Policy Rate empirically:
   ```bash
   set -a && source .env && set +a
   curl -s "https://api.tradingeconomics.com/historical/country/denmark/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'
   ```
3. Document TE HistoricalDataSymbol for DK Policy Rate (probe finding)
4. Time-boxed 20 min Nationalbanken Statbank probe:
   - Statbank API docs: `curl -sL "https://api.statbank.dk/v1/tables?lang=en" | head -40`
   - Try interest rates table (MPK/DNRENTM likely IDs):
     ```bash
     curl -s "https://api.statbank.dk/v1/data/MPK100?lang=en" | head -50
     ```
   - Alternative: Nationalbanken DST API `https://nationalbanken.statistikbank.dk/`
   - Apply UA-gate lesson: use `User-Agent: SONAR/2.0 (monetary-cascade; ...)` header
5. If Nationalbanken probe SUCCEEDS → implement connector as secondary in cascade
6. If Nationalbanken probe FAILS → scaffold raising DataUnavailableError (gated; document for CAL-DK-NATIONALBANKEN-API)
7. Read `riksbank.py` as template first (SE — Sprint W-SE, negative-rate handling most relevant)
8. Verify DK in `country_tiers.yaml`; if missing, add as Tier 1

Document findings in Commit 1 body. **Note negative-rate historical context**: DK had -0.75% trough 2015-2022 (DKK-EUR peg defense during ECB negative rates). Parser must preserve negative values — per Sprint V-CH/W-SE precedent.

Existing assets:
- `TEConnector` generic + 11 country wrappers (all Week 9 expansion up to NO)
- FRED connector has `fetch_series` for any series ID
- `country_tiers.yaml` canonical (ISO alpha-2)
- `bc_targets.yaml` + `r_star_values.yaml` extended all Week 9 pattern

---

## 3. Concurrency — parallel protocol with Sprint Z-WEEK9-RETRO + ISOLATED WORKTREES

**Sprint Y-DK operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-y`

Sprint Z-WEEK9-RETRO operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-z`

**Critical workflow**:
1. Sprint Y-DK CC starts by `cd /home/macro/projects/sonar-wt-sprint-y`
2. All file operations happen in this worktree
3. Branch name: `sprint-y-dk-connector`
4. Pushes to `origin/sprint-y-dk-connector`
5. Final merge to main via fast-forward post-sprint-close (rebase likely if Z merges first)

**File scope Sprint Y-DK**:
- `src/sonar/connectors/nationalbanken.py` NEW
- `src/sonar/connectors/te.py` APPEND (new `fetch_dk_policy_rate` wrapper + DK-specific constants)
- `src/sonar/indices/monetary/builders.py` APPEND (add DK builders — `build_m1_dk_inputs`)
- `src/sonar/connectors/fred.py` MODIFY (add DK FRED OECD series constants)
- `docs/data_sources/country_tiers.yaml` — verify/add DK entry (likely exists)
- `src/sonar/config/r_star_values.yaml` — add DK entry
- `src/sonar/config/bc_targets.yaml` — **add DK entry WITH SPECIAL CASE** (EUR peg, no explicit target)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (add DK to MONETARY_SUPPORTED_COUNTRIES + DK country dispatch)
- Tests:
  - `tests/unit/test_connectors/test_nationalbanken.py` NEW
  - `tests/unit/test_connectors/test_te_indicator.py` APPEND (DK Policy Rate wrapper tests)
  - `tests/unit/test_indices/monetary/test_builders.py` APPEND (DK builder tests)
  - `tests/unit/test_indices/monetary/test_config_loaders.py` APPEND (DK entries)
  - `tests/unit/test_pipelines/test_daily_monetary_indices.py` APPEND (DK country)
  - `tests/integration/test_daily_monetary_dk.py` NEW
  - `tests/fixtures/cassettes/nationalbanken/` + `tests/cassettes/connectors/te_dk_policy_rate_*.json`
- `docs/backlog/calibration-tasks.md` MODIFY (CAL-DK-* entries)
- `docs/planning/retrospectives/week9-sprint-y-dk-connector-report.md` NEW

**Sprint Z-WEEK9-RETRO scope** (for awareness, DO NOT TOUCH):
- `docs/planning/retrospectives/week9-retrospective.md` NEW (comprehensive Week 9 synthesis)
- `docs/planning/retrospectives/README.md` MODIFY (index update)
- Possibly `SESSION_CONTEXT.md` updates (prose, not code)

**Potential conflict zones**:
- `docs/planning/retrospectives/README.md` — both may modify (Y-DK adds new retro link, Z may rewrite index)
- Other files: zero overlap (Y is monetary code, Z is retrospective prose)

**Rebase expected post-merge**. Sprint Y-DK merges first (alphabetical priority) → Z-WEEK9-RETRO rebases if README touched.

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-sprint-y && git pull origin main --rebase`

**Push race**: normal `git push origin sprint-y-dk-connector`. Minor conflicts resolved via rebase.

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-y-dk-connector
git push origin main
```

---

## 4. Commits

### Commit 1 — Pre-flight + TE DK Policy Rate wrapper

```
feat(connectors): TE fetch_dk_policy_rate wrapper + source-drift guard

Pre-flight: probe TE DK Policy Rate + verify Nationalbanken Statbank API reachability.

Expected probe (document findings commit body):
  set -a && source .env && set +a
  curl -s "https://api.tradingeconomics.com/historical/country/denmark/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'

Document in commit body:
- Actual HistoricalDataSymbol returned (likely DKLendingR, DKIR, or policy-rate type)
- Response format (date + value)
- Historical range (expected: daily since Nationalbanken inception or peg era)
- **Negative values expected 2015-07..2022-09** (DK negative-rate era, -0.75% trough — DKK/EUR peg defense during ECB negative rates)
- Latest value sanity check (should match current Nationalbanken Lending Rate ~2.60-3.60% as of 2024/2025)

Nationalbanken Statbank probe (time-boxed 20 min):
  # Statbank general API
  curl -s -H "User-Agent: SONAR/2.0 (monetary-cascade)" \
    "https://api.statbank.dk/v1/tables?lang=en&subjects=MPK" | head -30

  # Interest rate tables (MPK100 likely key rates)
  curl -s "https://api.statbank.dk/v1/data/MPK100?lang=en&ForeignCurr=DK&Rate=UDLAN&Time=2024M12" | head -50

  # Alternative: Nationalbanken statbank
  curl -s "https://nationalbanken.statistikbank.dk/statbank5a/default.asp?w=1920" | head -30

Document: reachability, response format (Statbank JSON), series stability, UA requirements, negative-value preservation.

Extend src/sonar/connectors/te.py:

DK_POLICY_RATE_EXPECTED_SYMBOL: Final = "[EMPIRICAL — probe result]"
DK_POLICY_RATE_INDICATOR: Final = "interest rate"

async def fetch_dk_policy_rate(
    self,
    start: date,
    end: date,
) -> list[TEIndicatorObservation]:
    """Fetch DK Nationalbanken Lending Rate from TE.

    TE sources from Nationalbanken directly — avoids FRED OECD mirror monthly lag.
    Handles historical negative values (2015-2022 era, per Sprint V-CH/W-SE pattern).
    DK uses EUR-peg regime; rate mirrors ECB moves closely.
    Validates HistoricalDataSymbol matches expected per Sprint 3 Quick
    Wins source-drift discipline.

    Raises DataUnavailableError("source drift") if HistoricalDataSymbol
    != DK_POLICY_RATE_EXPECTED_SYMBOL.
    """
    obs = await self.fetch_indicator(
        country="DK",
        indicator=DK_POLICY_RATE_INDICATOR,
        start=start,
        end=end,
    )
    if obs and obs[0].historical_data_symbol != DK_POLICY_RATE_EXPECTED_SYMBOL:
        raise DataUnavailableError(...)
    return obs

Sanity check commit body:
  python -c "from sonar.connectors.te import TEConnector; c = TEConnector(api_key='x'); print(hasattr(c, 'fetch_dk_policy_rate'))"

Tests (tests/unit/test_connectors/test_te_indicator.py append):
- Unit: happy path mocked response (positive value)
- Unit: happy path with NEGATIVE value (e.g. -0.75% for 2019 data)
- Unit: HistoricalDataSymbol mismatch → DataUnavailableError
- Unit: empty response → empty list
- @pytest.mark.slow live canary: fetch DK Policy Rate 2024-12-01..31 →
  assert ≥ 1 obs, value ∈ [-1.0%, 5.0%] (wide range covering historic negative + recent positive)

Cassette: tests/cassettes/connectors/te_dk_policy_rate_2024_12.json

Coverage te.py additions ≥ 90%.
```

### Commit 2 — Nationalbanken Statbank connector

```
feat(connectors): Danmarks Nationalbank Statbank API public connector

Create src/sonar/connectors/nationalbanken.py:

"""Danmarks Nationalbank Statbank API connector.

Public data — no auth required. Uses Statbank v1 REST API.
Fallback cascade per Sprint L/S-CA/T-AU/V-CH/W-SE pattern: TE → Statbank → FRED.

Empirical probe findings (Commit 1):
- Base URL: https://api.statbank.dk/v1/
- Endpoints: /data/{table_id}[?lang=en&...], /tables, /tableinfo/{table_id}
- Format: JSON
- Auth: public (descriptive UA recommended)
- Key tables (probe-validated Commit 1-2):
  - MPK100 (or similar): Nationalbanken key interest rates
  - MPK3 or MPK4: Government bond yields
- DKK/EUR peg context: rates track ECB closely
"""

from __future__ import annotations
from datetime import date
from typing import Final

from sonar.connectors.base import BaseConnector
from sonar.connectors.exceptions import (
    DataUnavailableError,
    ConnectorError,
)

NATIONALBANKEN_UA: Final = "SONAR/2.0 (monetary-cascade; https://github.com/hugocondesa-debug/sonar-engine)"
NATIONALBANKEN_POLICY_RATE_TABLE: Final = "[probe-validated]"
NATIONALBANKEN_10Y_BOND_TABLE: Final = "[probe-validated]"

class NationalbankenConnector(BaseConnector):
    """Danmarks Nationalbank Statbank API — public, JSON REST."""

    BASE_URL = "https://api.statbank.dk/v1/"
    CONNECTOR_ID = "nationalbanken"
    USER_AGENT = NATIONALBANKEN_UA

    async def fetch_table(
        self,
        table_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        filters: dict | None = None,
    ) -> list[NationalbankenObservation]:
        """Fetch data from Statbank API table.

        Endpoint: /data/{table_id}?lang=en&...
        Returns list of observations filtered by date range + optional filters.
        Handles negative values (2015-2022 era, per Sprint V-CH/W-SE pattern).
        Raises DataUnavailableError if table unreachable.
        """
        url = f"{self.BASE_URL}data/{table_id}"
        params = {"lang": "en"}
        if start_date:
            params["TimeFrom"] = start_date.isoformat()
        if end_date:
            params["TimeTo"] = end_date.isoformat()
        if filters:
            params.update(filters)

        response = await self._get(
            url,
            params=params,
            headers={"User-Agent": NATIONALBANKEN_UA},
        )
        # Parse Statbank JSON → date/value tuples (including negatives)
        ...

    async def fetch_policy_rate(
        self,
        start_date: date,
        end_date: date,
    ) -> list[NationalbankenObservation]:
        """Convenience: Nationalbanken Lending Rate."""
        return await self.fetch_table(
            NATIONALBANKEN_POLICY_RATE_TABLE,
            start_date,
            end_date,
        )

Sanity check:
  python -c "from sonar.connectors.nationalbanken import NationalbankenConnector; print('OK')"

Tests (tests/unit/test_connectors/test_nationalbanken.py):
- Unit: class instantiation + URL building + UA header set
- Unit: fetch_table success path (mocked Statbank JSON)
- Unit: fetch_table NEGATIVE values handled (-0.75 example)
- Unit: fetch_table 404 → DataUnavailableError
- Unit: fetch_table empty → DataUnavailableError
- Unit: date filter behavior (TimeFrom/TimeTo params)
- Unit: disk cache behavior
- @pytest.mark.slow live canary: probe Policy Rate recent;
  assert ≥ 1 obs, values reasonable

Coverage nationalbanken.py ≥ 85%.

Cassette: tests/fixtures/cassettes/nationalbanken/policy_rate_2024_12.json

Note: if Statbank API probe failed Commit 1, scaffold with DataUnavailableError
+ open CAL-DK-NATIONALBANKEN-API. Pattern per Sprint U-NZ RBNZ scaffold.
```

### Commit 3 — DK Tier 1 config + r*/bc_targets YAML entries (special case: EUR peg)

```
feat(config): DK Tier 1 enabled + monetary YAML entries (EUR peg convention)

1. Verify docs/data_sources/country_tiers.yaml contains DK as Tier 1.
   Expected: already present.
   If missing, add:
   - iso_code: DK
     tier: 1
     monetary: enabled
     description: "Denmark — Tier 1 per ADR-0005; DKK/EUR ±2.25% peg since 1999"

2. Update src/sonar/config/r_star_values.yaml — add DK entry:
   DK:
     value: 0.0075       # Nationalbanken staff research ~0.5-1.0% (midpoint 0.75%)
     proxy: true
     source: "Danmarks Nationalbank Monetary Review — neutral rate estimate ~2024"
     timestamp: "2024-12-01"
     note: "DK r* anchored to ECB via DKK/EUR peg; similar to EA neutral rate"

   Loader auto-emits R_STAR_PROXY flag.

3. Update src/sonar/config/bc_targets.yaml — add DK entry (SPECIAL CASE):
   DK:
     target: 0.02        # ECB target via DKK/EUR peg (Nationalbanken does NOT have domestic target)
     source: "DKK/EUR ±2.25% peg since 1999; effectively imports ECB 2% target"
     note: "DK has no domestic explicit inflation target — maintains peg. Uses ECB 2% via transmission."
     target_convention: "imported_eur_peg"  # New field for documentation clarity

   Loader may add DK_INFLATION_TARGET_IMPORTED_FROM_EA flag automatically.

Unit tests:
- Loader reads DK r* with proxy=true (0.75%)
- bc_targets loader reads DK 2% target
- Loader adds DK_INFLATION_TARGET_IMPORTED_FROM_EA flag (if implemented)
- country_tiers_parser includes DK in T1 list

Coverage maintained.
```

### Commit 4 — M1 DK builder with TE-primary cascade + negative-rate handling

```
feat(indices): M1 DK builder TE-primary cascade + EUR-peg flag + negative-rate

Add build_m1_dk_inputs to src/sonar/indices/monetary/builders.py:

async def build_m1_dk_inputs(
    fred: FredConnector,
    te: TEConnector,
    observation_date: date,
    *,
    nationalbanken: NationalbankenConnector | None = None,
    history_years: int = 15,
) -> M1Inputs:
    """Build M1 DK inputs via TE primary cascade.

    Cascade priority (per canonical pattern):
    1. TE primary — DK_POLICY_RATE_TE_PRIMARY flag (daily Nationalbanken-sourced)
    2. Nationalbanken Statbank native — DK_POLICY_RATE_NATIONALBANKEN_NATIVE flag
    3. FRED OECD mirror — DK_POLICY_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE

    r* via r_star_values.yaml (R_STAR_PROXY flag, 0.75%).
    Inflation target via bc_targets.yaml (2% imported from ECB via DKK/EUR peg).

    Handles negative rate era (2015-07..2022-09) via value preservation
    + DK_NEGATIVE_RATE_ERA_DATA flag (per Sprint V-CH/W-SE pattern).

    DK UNIQUE: DK_INFLATION_TARGET_IMPORTED_FROM_EA flag emitted
    (DK has no domestic target; imports ECB 2% via peg).
    """
    flags = []
    obs = None

    # Primary: TE
    if te:
        try:
            obs = await te.fetch_dk_policy_rate(start, end)
            if obs:
                flags.append("DK_POLICY_RATE_TE_PRIMARY")
                # Check for negative-rate era coverage
                if any(o.value < 0 for o in obs):
                    flags.append("DK_NEGATIVE_RATE_ERA_DATA")
        except (DataUnavailableError, ConnectorError):
            flags.append("DK_POLICY_RATE_TE_UNAVAILABLE")

    # Secondary: Nationalbanken Statbank
    if not obs and nationalbanken:
        try:
            nb_obs = await nationalbanken.fetch_policy_rate(start, end)
            if nb_obs:
                obs = [_DatedValue(...) for o in nb_obs]
                flags.append("DK_POLICY_RATE_NATIONALBANKEN_NATIVE")
        except (DataUnavailableError, ConnectorError):
            flags.append("DK_POLICY_RATE_NATIONALBANKEN_UNAVAILABLE")

    # Tertiary: FRED OECD mirror (last-resort, monthly stale)
    if not obs:
        fred_obs = await fred.fetch_series(FRED_DK_POLICY_RATE_SERIES, start, end)
        if fred_obs:
            obs = [_DatedValue(...) for o in fred_obs]
            flags.extend([
                "DK_POLICY_RATE_FRED_FALLBACK_STALE",
                "CALIBRATION_STALE",
            ])

    if not obs:
        raise ValueError("DK Policy Rate unavailable from TE, Nationalbanken, FRED")

    # r* from YAML (LOW value expected, EUR-anchored)
    r_star, r_star_is_proxy = resolve_r_star("DK")
    if r_star_is_proxy:
        flags.append("R_STAR_PROXY")

    # Inflation target: imported from EUR peg
    flags.append("DK_INFLATION_TARGET_IMPORTED_FROM_EA")

    # Build M1Inputs ...

Constants (add to fred.py):
FRED_DK_POLICY_RATE_SERIES: str = "IRSTCI01DKM156N"  # OECD MEI DK short-rate
FRED_DK_BOND_10Y_SERIES: str = "IRLTLT01DKM156N"  # OECD MEI DK long-rate

Expose in __all__:
    "build_m1_dk_inputs",

Tests:
- Unit: TE primary success → DK_POLICY_RATE_TE_PRIMARY
- Unit: NEGATIVE rate historical data → DK_NEGATIVE_RATE_ERA_DATA flag
- Unit: DK_INFLATION_TARGET_IMPORTED_FROM_EA flag always present (peg convention)
- Unit: TE fails, Nationalbanken succeeds → DK_POLICY_RATE_NATIONALBANKEN_NATIVE
- Unit: TE + Nationalbanken fail → FRED fallback → CALIBRATION_STALE
- Unit: all fail → ValueError
- Unit: r* loaded DK with proxy flag (0.75%)
- Unit: bc_targets DK 2% loaded

Coverage build_m1_dk_inputs ≥ 95%.
```

### Commit 5 — Pipeline integration daily_monetary_indices DK

```
feat(pipelines): daily_monetary_indices DK country support + FRED OECD DK

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Add DK to MONETARY_SUPPORTED_COUNTRIES:
   MONETARY_SUPPORTED_COUNTRIES = ("US", "EA", "GB", "UK", "JP", "CA", "AU", "NZ", "CH", "SE", "NO", "DK")
   # DK follows Sprint V-CH/W-SE negative-rate pattern + EUR-peg special case
   # M2 T1 COMPLETE milestone — 16 countries monetary M1 live (US/EA/GB/UK counted as 2 — US + EA/GB pair)

2. DK country branch routes to build_m1_dk_inputs
3. M2/M3/M4 DK: raise NotImplementedError gracefully
4. Connector lifecycle: Nationalbanken connector added to connectors_to_close

Update src/sonar/connectors/fred.py:
- Add FRED_DK_POLICY_RATE_SERIES constant
- Add FRED_DK_BOND_10Y_SERIES constant

Verify --country DK and --all-t1 (includes DK) work.

Tests:
- Unit: pipeline invokes DK builders when country=DK
- Unit: DK M2/M3/M4 graceful skip
- Unit: connector_to_close includes Nationalbanken instance

Integration smoke @slow:
tests/integration/test_daily_monetary_dk.py:

@pytest.mark.slow
def test_daily_monetary_dk_te_primary():
    """Full pipeline DK 2024-12-31 with TE primary cascade.

    Expected:
    - M1 DK row persists
    - DK_POLICY_RATE_TE_PRIMARY flag present
    - R_STAR_PROXY flag present
    - DK_INFLATION_TARGET_IMPORTED_FROM_EA flag present
    - policy_rate_pct daily-fresh"""

@pytest.mark.slow
def test_daily_monetary_dk_nationalbanken_native_fallback():
    """TE unavailable, Nationalbanken Statbank succeeds."""

@pytest.mark.slow
def test_daily_monetary_dk_negative_rate_historical():
    """Fetch DK Policy Rate 2019-01..12 (negative era).

    Expected:
    - Values < 0 preserved (no filtering)
    - DK_NEGATIVE_RATE_ERA_DATA flag present"""

Wall-clock ≤ 20s combined.

Coverage maintained.
```

### Commit 6 — M2/M4 DK scaffolds

```
feat(indices): M2 + M4 DK scaffolds (wire-ready, raise pending connectors)

Per canonical pattern — M2/M4 DK builders are scaffolds raising InsufficientDataError.

async def build_m2_dk_inputs(...) -> M2Inputs:
    """M2 DK scaffold — output gap needs Statistics Denmark or OECD EO."""
    raise InsufficientDataError(
        "DK M2 requires output_gap; pending Statistics Denmark/OECD EO connector. "
        "CAL-DK-M2-OUTPUT-GAP tracking resolution."
    )

async def build_m4_dk_inputs(...) -> M4Inputs:
    """M4 DK scaffold — FCI components need DKK-specific VIX, credit spreads, NEER."""
    raise InsufficientDataError(
        "DK M4 requires VIX-DK / credit-spread-DK / NEER-DKK; all deferred. "
        "CAL-DK-M4-FCI tracking full wire-up."
    )

Tests:
- Unit: build_m2_dk_inputs raises InsufficientDataError
- Unit: build_m4_dk_inputs raises InsufficientDataError
- Unit: error message references correct CAL items

Coverage maintained.
```

### Commit 7 — Retrospective + CAL items opened + M2 T1 COMPLETE milestone

```
docs(planning+backlog): Week 9 Sprint Y-DK Nationalbanken connector retrospective — M2 T1 COMPLETE

File: docs/planning/retrospectives/week9-sprint-y-dk-connector-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- **M2 T1 COMPLETE milestone achieved** (16 countries monetary M1 live)
- Commits table with SHAs + gate status
- Empirical findings:
  - TE DK Policy Rate HistoricalDataSymbol: [probe result]
  - Nationalbanken Statbank API reachability: [success/issues/partial]
  - FRED OECD DK mirror series validated
  - Negative-rate era handling (2015-07..2022-09 values preserved, DK_NEGATIVE_RATE_ERA_DATA flag)
  - EUR-peg convention (DK_INFLATION_TARGET_IMPORTED_FROM_EA flag always present)
- Coverage delta
- Live canary outcomes (including negative-rate historical canary)
- HALT triggers fired / not fired
- Deviations from brief
- DK monetary indices operational:
  - M1: live via TE cascade (Nationalbanken Statbank if probe succeeded)
  - M2: scaffold (CAL-DK-M2-OUTPUT-GAP)
  - M3: deferred (CAL-DK-M3)
  - M4: scaffold (CAL-DK-M4-FCI)
- Pattern validation:
  - TE-primary cascade continues canonical (9th consecutive country, 100% Week 9 expansion success)
  - Third negative-rate country (CH, SE precedent — longest era CH 2014-2022)
  - First EUR-peg country with imported target convention
  - Pattern maturity: template replication effortless by 9th iteration
- **M2 T1 COMPLETE**: 16 countries M1 live (US + EA + GB + UK + JP + CA + AU + NZ + CH + SE + NO + DK + DE + PT + IT + ES + FR + NL)
  - Corrected count post-reconciliation needed for canonical tally
- Isolated worktree: zero collision incidents with Sprint Z-WEEK9-RETRO parallel
- Merge strategy: branch sprint-y-dk-connector → main (rebase expected post Z merge)
- New CAL items opened:
  - CAL-DK-M2-OUTPUT-GAP
  - CAL-DK-M3
  - CAL-DK-M4-FCI
  - CAL-DK-NATIONALBANKEN-API (if probe failed)
  - CAL-DK-EUR-PEG-STABILITY (deferred Phase 2+ research topic)

Open CAL-DK-* items formally in docs/backlog/calibration-tasks.md.

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git merge --ff-only sprint-y-dk-connector
  git push origin main
  # If rebase needed (Sprint Z-WEEK9-RETRO merged first):
  # cd /home/macro/projects/sonar-wt-sprint-y
  # git fetch origin && git rebase origin/main
  # Resolve conflicts (minimal — possibly retrospectives/README.md)
  # git push --force-with-lease
  # Then merge
```

---

## 5. HALT triggers (atomic)

0. **TE DK Policy Rate empirical probe fails** — HALT + surface. Alternative: FRED primary.
1. **HistoricalDataSymbol mismatch** — HALT.
2. **Nationalbanken Statbank unreachable** — apply UA lesson. If still unreachable, scaffold + open CAL-DK-NATIONALBANKEN-API. Not a HALT.
3. **Statbank API schema divergent** (tables use unfamiliar filtering semantics) — scope narrow to policy rate only.
4. **Negative values causing parser errors** — per Sprint V-CH/W-SE precedent, parser preserves. HALT if logic assumes positive-only.
5. **DK in country_tiers.yaml Tier mismatch** — HALT + verify against ADR-0005.
6. **r* DK value uncertainty** — 0.75% EUR-anchored + R_STAR_PROXY flag.
7. **bc_targets DK special case handling** — target_convention: "imported_eur_peg" field optional. Document decision.
8. **DK_INFLATION_TARGET_IMPORTED_FROM_EA flag** — new flag convention. If flag mechanism elsewhere, follow precedent.
9. **M2/M4 scaffolds pattern** — per precedent, raise InsufficientDataError.
10. **TE rate limits** during live canaries — tenacity handles.
11. **Coverage regression > 3pp** → HALT.
12. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
13. **Concurrent Sprint Z-WEEK9-RETRO touches Y-DK scope** (shouldn't per §3; zero overlap expected) → reconcile via rebase.

---

## 6. Acceptance

### Global sprint-end
- [ ] 6-8 commits pushed to branch `sprint-y-dk-connector`
- [ ] `src/sonar/connectors/nationalbanken.py` shipped + tested (even if Statbank probe partial)
- [ ] `fetch_dk_policy_rate` TE wrapper + source-drift guard shipped
- [ ] TE DK HistoricalDataSymbol validated + documented
- [ ] Nationalbanken Statbank reachability documented (probe result)
- [ ] Negative-rate era handling validated (2015-2022 values preserved, DK_NEGATIVE_RATE_ERA_DATA)
- [ ] EUR-peg convention validated (DK_INFLATION_TARGET_IMPORTED_FROM_EA flag)
- [ ] DK Tier 1 in country_tiers.yaml
- [ ] r_star_values.yaml DK entry added (with proxy: true, 0.75%)
- [ ] bc_targets.yaml DK entry present (2% EUR-imported)
- [ ] `build_m1_dk_inputs` cascade operational with DK_NEGATIVE_RATE_ERA_DATA flag
- [ ] M2 + M4 DK scaffolds shipped (raise InsufficientDataError)
- [ ] `daily_monetary_indices.py --country DK` runs end-to-end
- [ ] Live canaries PASS: TE DK Policy Rate + DK monetary pipeline + historical negative-rate test
- [ ] Coverage nationalbanken.py ≥ 85%, builders.py DK path ≥ 95%
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push
- [ ] **M2 T1 COMPLETE** milestone note in retro

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week9-sprint-y-dk-connector-report.md`

**Final tmux echo**:
```
SPRINT Y-DK DENMARK CONNECTOR DONE: N commits on branch sprint-y-dk-connector
TE HistoricalDataSymbol DK validated: [symbol]
Nationalbanken Statbank reachability: [success / issues / partial]
Negative-rate era support: VALIDATED (2015-2022 data preserved, DK_NEGATIVE_RATE_ERA_DATA)
EUR-peg convention: DK_INFLATION_TARGET_IMPORTED_FROM_EA flag added
DK monetary: M1 (cascade), M2/M4 (scaffolds), M3 (deferred)
**M2 T1 COMPLETE MILESTONE**: 16 countries monetary M1 live
HALT triggers: [list or "none"]
Merge: git checkout main && git merge --ff-only sprint-y-dk-connector
   (rebase may be required if Sprint Z-WEEK9-RETRO merged first)
Artifact: docs/planning/retrospectives/week9-sprint-y-dk-connector-report.md
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

### TE primary canonical (9th consecutive country, 100% success Week 9)
Pattern stable 8 iterations deep. DK is final T1 expansion. Template replication effortless.

### Nationalbanken Statbank API = JSON REST
Well-documented Danish Statistics API. Expected success similar to Riksbank Swea (SE).

### Third negative-rate country + longest era
CH (2014-2022) > SE (2015-2019) > DK (2015-2022) — DK similar to CH duration. Pattern established Sprint V-CH, replicated Sprint W-SE, now final iteration Y-DK.

### EUR-peg SPECIAL CASE — novel convention
DK has no domestic inflation target — imports ECB 2% via DKK/EUR peg.
New flag: `DK_INFLATION_TARGET_IMPORTED_FROM_EA`
New YAML field: `target_convention: "imported_eur_peg"`

This is the first imported-target country. Sets precedent for future EUR-peg or dollar-peg countries (e.g., some Gulf states T2+).

### Pattern replication discipline (9th iteration — final)
Sprint W-SE SE shipped Day 4. This sprint mirrors closely:
- TE wrapper with source-drift guard
- Native connector (JSON REST per Statbank)
- M1 builder with cascade + negative-rate + EUR-peg handling
- M2/M4 scaffolds
- Pipeline integration
- Retro

### M2 T1 COMPLETE milestone
16 countries M1 live end of Sprint Y-DK merge. Full T1 coverage achieved.

Accurate tally (post-merge):
- Original T1 Sprint 1: US, DE, PT, IT, ES, FR, NL (7)
- Week 8: GB, JP (2)
- Week 9: CA, AU, NZ, CH, SE, NO, DK (7)
- **Total: 16 countries M1 live**

Note: EA treated as aggregate (covered via individual members DE/PT/IT/ES/FR/NL + pending ECB direct). UK = GB canonical post-CAL-128.

### Isolated worktree workflow
Sprint Y-DK operates entirely in `/home/macro/projects/sonar-wt-sprint-y`. Branch: `sprint-y-dk-connector`.

### Sprint Z-WEEK9-RETRO parallel
Runs in `sonar-wt-sprint-z`. Different domains entirely (DK code vs Week 9 retro synthesis). Zero file overlap per §3. Rebase expected post-merge only if README.md updated.

---

*End of Week 9 Sprint Y-DK Denmark connector brief. 6-8 commits. DK T1 shipped. M2 T1 COMPLETE milestone.*
