# Sprint I-patch — UK Monetary TE Primary Cascade

**Target**: Fix Sprint I UK M1 cascade — replace FRED OECD mirror (monthly stale) with TE primary (daily real-time BoE-sourced). Quality correction, not new feature.
**Priority**: HIGH (corrects signal quality degradation shipped Week 8 Day 1)
**Budget**: 1-1.5h CC autonomous
**Commits**: ~4-5
**Base**: main HEAD post Week 8 Day 1 close (`ca0034f` or later)
**Concurrency**: Single sprint. Runs before Sprint K L5 wiring OR paralelo with Sprint K in tmux sonar-l3 (file isolation trivial).

---

## 1. Scope

In:
- Add TE wrapper `fetch_uk_bank_rate` to `TEConnector` — mirrors `fetch_conference_board_cc_us` pattern (Week 6 Sprint 3 Quick Wins)
- Add TE wrapper `fetch_uk_10y_gilt` — or verify existing `fetch_sovereign_yield_historical(country='UK')` suffices (Commit 1 decision)
- HistoricalDataSymbol source-identity guard per convention (expected symbol TBD empirically; probe during Commit 1)
- Cassette + `@pytest.mark.slow` live canary per new TE wrapper
- **Update `build_m1_uk_inputs` cascade** in `src/sonar/indices/monetary/builders.py`:
  - Primary: TE UK Bank Rate (expected daily BoE-sourced)
  - Secondary: BoE native (preserved — wire-ready for future Akamai bypass)
  - Tertiary: FRED OECD mirror (last-resort fallback with explicit `UK_POLICY_RATE_FRED_OECD_STALE` flag)
- Update flag lexicon:
  - `UK_BANK_RATE_TE_PRIMARY` (default expected path)
  - `UK_BANK_RATE_BOE_NATIVE` (preserved; rare)
  - `UK_BANK_RATE_FRED_FALLBACK_STALE` (last-resort)
- Sprint I retrospective AMENDMENT documenting FRED OECD staleness issue + TE-primary correction
- No new CAL items expected (this closes the Sprint I signal quality gap)

Out:
- UK M2/M3/M4 extensions (CAL-125/126/127 remain Week 8 Day 3+)
- Other country FRED OECD mirror reviews (separate sweep if pattern found elsewhere)
- BoE IADB Akamai bypass research (Phase 2+ investigation; ProtonVPN rejected this sprint)
- Integration test changes beyond cassette updates
- New TE wrappers for JP or other countries (JP BoJ separate Sprint L)

---

## 2. Spec reference

Authoritative-ish (quality correction, not spec change):
- `docs/specs/indices/monetary/M1-effective-rates.md` §2 — M1 inputs require current policy rate (daily cadence implied)
- `docs/specs/conventions/patterns.md` — Pattern 2 hierarchy best-of + Pattern 4 TE primary
- `docs/planning/retrospectives/week7-sprint-3-quick-wins-report.md` — TE HistoricalDataSymbol validation discipline
- `docs/planning/retrospectives/week8-sprint-i-boe-connector-report.md` — cascade context
- SESSION_CONTEXT §Critical technical reference — TE HistoricalDataSymbol validated list
- SESSION_CONTEXT §Regras operacionais — TE wrapper source-drift guards mandatory

**Pre-flight requirement**: Commit 1 CC:
1. Probes TE UK Bank Rate empirically:
   ```bash
   curl -s "https://api.tradingeconomics.com/historical/country/united kingdom/indicator/interest rate?c=$TE_API_KEY&format=json" | head
   ```
   Expected response: BoE Bank Rate daily observations. Document HistoricalDataSymbol returned (likely `GBINTR` per pattern).

2. Verifies `fetch_sovereign_yield_historical(country='UK')` returns 10Y gilt (pattern shipped Week 3.5; `GUKG10:IND` mapping present).

3. Reads existing Quick Wins wrapper pattern (`fetch_conference_board_cc_us` + `fetch_michigan_5y_inflation_us`) for source-drift guard template.

4. Reads `build_m1_uk_inputs` current cascade for precise modification points.

Document empirical findings in Commit 1 body.

Existing assets:
- `TEConnector` generic + 7 wrappers shipped
- `TEIndicatorObservation.historical_data_symbol` field + source-drift guards canonical (Sprint 3 Quick Wins)
- Country mapping `"UK": "united kingdom"` + `"UK": "GUKG10:IND"` present
- `build_m1_uk_inputs` cascade structure established (BoE → FRED)

---

## 3. Concurrency — single sprint (flexible)

Default single sprint in tmux `sonar`. Can run paralelo Sprint K L5 wiring in `sonar-l3`:

**Hard-locked resource allocation (if paralelo Sprint K)**:
- `src/sonar/connectors/te.py`: this brief appends 2 wrappers at end.
- `src/sonar/indices/monetary/builders.py`: this brief modifies `build_m1_uk_inputs` function only.
- `src/sonar/pipelines/`: NOT touched.
- `src/sonar/cycles/`: NOT touched.
- `src/sonar/regimes/`: NOT touched (Sprint K domain).
- `src/sonar/cli/`: NOT touched.
- `db/models.py` + `db/persistence.py`: NOT touched.
- Migration numbers: NONE.
- `docs/specs/`: NOT touched.
- Tests: separate files.

**Zero file overlap with Sprint K**. Paralelo viable.

If running single sequentially: no concurrency concerns.

---

## 4. Commits

### Commit 1 — Pre-flight + TE UK Bank Rate wrapper

```
feat(connectors): TE fetch_uk_bank_rate wrapper + source-drift guard

Pre-flight: probe TE UK Bank Rate endpoint empirically.

Expected probe:
  set -a && source .env && set +a
  curl -s "https://api.tradingeconomics.com/historical/country/united kingdom/indicator/interest rate?c=$TE_API_KEY&format=json" | jq '.[0]'

Document empirical findings in commit body:
- Actual HistoricalDataSymbol returned (likely "GBINTR")
- Response format (date + value + source attribution)
- Historical range (expected: daily since BoE inception 1694)
- Latest value sanity check (should match current Bank Rate)

Extend src/sonar/connectors/te.py:

UK_BANK_RATE_EXPECTED_SYMBOL: Final = "GBINTR"  # update post-probe
UK_BANK_RATE_INDICATOR: Final = "interest rate"

async def fetch_uk_bank_rate(
    self,
    start: date,
    end: date,
) -> list[TEIndicatorObservation]:
    """Fetch UK Bank Rate (BoE policy rate) from TE.

    TE sources from Bank of England directly — avoids FRED OECD
    mirror monthly lag. Validates HistoricalDataSymbol matches
    expected per Sprint 3 Quick Wins source-drift discipline.

    Raises DataUnavailableError("source drift") if
    HistoricalDataSymbol != UK_BANK_RATE_EXPECTED_SYMBOL.

    Returns observations in chronological order.
    """
    obs = await self.fetch_indicator(
        country="UK",
        indicator=UK_BANK_RATE_INDICATOR,
        start=start,
        end=end,
    )
    if obs and obs[0].historical_data_symbol != UK_BANK_RATE_EXPECTED_SYMBOL:
        raise DataUnavailableError(
            f"UK Bank Rate source drift: expected "
            f"{UK_BANK_RATE_EXPECTED_SYMBOL}, got "
            f"{obs[0].historical_data_symbol}"
        )
    return obs

Sanity check commit body:
  python -c "from sonar.connectors.te import TEConnector; c = TEConnector(api_key='x'); print(hasattr(c, 'fetch_uk_bank_rate'))"

Tests (tests/unit/test_connectors/test_te.py append):
- Unit: happy path mocked response → UK observations
- Unit: HistoricalDataSymbol mismatch → DataUnavailableError
- Unit: empty response → returns empty list
- @pytest.mark.slow live canary: fetch Bank Rate 2024-12-01 to 2024-12-31 →
  assert ≥ 1 obs, value ∈ [4%, 6%] (sanity range for Dec 2024)

Cassette: tests/fixtures/cassettes/te/uk_bank_rate_2024_12.json

Coverage te.py additions ≥ 90%.
```

### Commit 2 — UK 10Y gilt wrapper (if needed) + verification

```
feat(connectors): TE UK 10Y gilt — verify or add wrapper

Verify existing fetch_sovereign_yield_historical(country='UK') works:
- `"UK": "GUKG10:IND"` mapping exists
- Returns daily gilt yield observations

Commit body decision:
- If existing sufficient → this commit is verification only + cassette
  addition
- If gap → add fetch_uk_10y_gilt wrapper mirroring US equivalent

Probe:
  curl -s "https://api.tradingeconomics.com/markets/historical/GUKG10:IND?c=$TE_API_KEY&format=json&d1=2024-12-01&d2=2024-12-31"

Tests:
- Unit: existing pattern verified or new wrapper tested
- @pytest.mark.slow live canary: fetch UK 10Y Dec 2024 → assert range
  3.5%-5% sanity

Cassette: tests/fixtures/cassettes/te/uk_10y_gilt_2024_12.json (if wrapper added)
```

### Commit 3 — Update build_m1_uk_inputs cascade

```
feat(indices): UK M1 cascade TE primary + FRED staleness flag

Update src/sonar/indices/monetary/builders.py build_m1_uk_inputs:

New cascade (priority-ordered):

1. TE primary (NEW — default expected path):
   - Call te.fetch_uk_bank_rate(start, end)
   - On DataUnavailableError/ConnectorError → flag UK_BANK_RATE_TE_UNAVAILABLE
   - On success → flag UK_BANK_RATE_TE_PRIMARY (no proxy warning; canonical)

2. BoE native (preserved as secondary):
   - Call boe.fetch_bank_rate if boe supplied
   - Akamai gate likely fails → flag UK_BANK_RATE_BOE_FALLBACK
   - On success (rare) → flag UK_BANK_RATE_BOE_NATIVE

3. FRED OECD mirror (last-resort with explicit staleness):
   - Call fred.fetch_series(FRED_UK_BANK_RATE_SERIES)
   - Emit BOTH flags: UK_BANK_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE
   - Log structured warning: "UK Bank Rate served from FRED OECD
     monthly mirror; TE + BoE both unreachable"

Order of attempt (fail-open):
```python
# Pseudocode
flags = []
obs = None
if te:
    try:
        obs = await te.fetch_uk_bank_rate(start, end)
        if obs:
            flags.append("UK_BANK_RATE_TE_PRIMARY")
    except (DataUnavailableError, ConnectorError):
        flags.append("UK_BANK_RATE_TE_UNAVAILABLE")
if not obs and boe:
    try:
        boe_obs = await boe.fetch_bank_rate(start, end)
        if boe_obs:
            obs = [_DatedValue(...) for x in boe_obs]
            flags.append("UK_BANK_RATE_BOE_NATIVE")
    except DataUnavailableError:
        flags.append("UK_BANK_RATE_BOE_FALLBACK")
if not obs:
    fred_obs = await fred.fetch_series(FRED_UK_BANK_RATE_SERIES, start, end)
    if fred_obs:
        obs = [_DatedValue(...) for x in fred_obs]
        flags.extend([
            "UK_BANK_RATE_FRED_FALLBACK_STALE",
            "CALIBRATION_STALE",
        ])
if not obs:
    raise ValueError("UK Bank Rate unavailable from TE, BoE, and FRED")
```

Signature update:
- `build_m1_uk_inputs(fred, te, observation_date, *, boe=None, ...)`:
- `te` becomes required parameter (was implicit via pipeline)
- Backward compat: None accepted during transition but logs warning

Tests:
- Unit: TE primary path (TE returns data) → UK_BANK_RATE_TE_PRIMARY flag
- Unit: TE fails, BoE succeeds → UK_BANK_RATE_BOE_NATIVE flag
- Unit: TE + BoE fail, FRED succeeds → UK_BANK_RATE_FRED_FALLBACK_STALE +
  CALIBRATION_STALE flags
- Unit: all fail → ValueError
- Unit: TE disabled, BoE disabled, FRED primary → FRED path works backward-compat

Coverage build_m1_uk_inputs path ≥ 95%.

Update docs in builder docstring documenting cascade rationale.
```

### Commit 4 — Pipeline wiring + integration smoke

```
feat(pipelines): daily_monetary_indices UK TE cascade integration

Update src/sonar/pipelines/daily_monetary_indices.py:

Ensure TE connector instantiated + passed to build_m1_uk_inputs
for UK country. Verify connector lifecycle (aclose) includes TE.

No changes to exit codes or CLI flags.

Integration test: tests/integration/test_daily_monetary_uk_te_cascade.py

@pytest.mark.slow
def test_daily_monetary_uk_te_primary():
    """Full pipeline UK 2024-12-31 with TE enabled.

    Expected:
    - M1 UK row persists
    - UK_BANK_RATE_TE_PRIMARY flag present
    - policy_rate_pct daily-fresh (match TE Dec 2024 data)
    - No UK_BANK_RATE_FRED_FALLBACK_STALE flag (TE primary working)"""

@pytest.mark.slow
def test_daily_monetary_uk_fred_fallback_when_te_down():
    """Simulate TE unreachable; pipeline falls to FRED OECD mirror.

    Expected:
    - M1 UK row persists (signal delivered)
    - UK_BANK_RATE_TE_UNAVAILABLE + UK_BANK_RATE_FRED_FALLBACK_STALE
      + CALIBRATION_STALE flags
    - Exit code 0 (not crash; degraded but operational)"""

Wall-clock ≤ 20s combined.

Coverage maintained.
```

### Commit 5 — Retrospective amendment + CAL review

```
docs(planning): Week 8 Sprint I-patch TE primary cascade retrospective

File: docs/planning/retrospectives/week8-sprint-i-patch-te-cascade-report.md

Structure:
- Summary (duration, commits, scope)
- Context: Sprint I shipped FRED OECD mirror as UK M1 fallback;
  user identified staleness issue (monthly lag vs daily BoE decisions)
- Decision: TE primary (daily BoE-sourced) vs VPN proxy workaround
  vs keep FRED; chose TE per existing infrastructure + zero
  operational overhead
- Commits table with SHAs
- TE HistoricalDataSymbol validated: [actual symbol]
- Cascade design: TE primary → BoE secondary → FRED last-resort
  (staleness flagged)
- Live smoke outcomes: TE primary path working; FRED fallback
  path validated
- Sprint I retrospective AMENDMENT appended to sprint-i-boe-connector-report.md
- Lessons for brief format v3:
  - Connector briefs must state data freshness requirements explicitly
  - "Aggregator-primary (TE) with native-override" Pattern 4 should
    be default for country expansion; monthly mirrors are last-resort
  - Signal quality evaluation required during cascade design, not
    just "does connector return data"
- No CAL closures (this closes the Sprint I quality gap,
  operationally)
- No new CALs (unless pattern review reveals other FRED OECD
  mirror cases — surface if found)

Brief format v3 update proposed (for SESSION_CONTEXT):
- New requirement: connector briefs include "signal freshness
  requirement" section + cascade priority rationale tied to
  index cadence (daily vs monthly vs quarterly)
```

---

## 5. HALT triggers (atomic)

0. **TE UK Bank Rate empirical probe fails** — if TE returns no UK data or unexpected format, HALT + surface to chat. Alternative cascade design needed.
1. **HistoricalDataSymbol mismatch** (Sprint 3 Quick Wins pattern) — if TE returns different symbol than expected, do NOT assume benign. HALT + surface for validation.
2. **TE rate limits** during live canary — tenacity handles; if persistent, mark slow test only, document in retro.
3. **build_m1_uk_inputs signature break** — existing callers may pass specific args; verify backward compat.
4. **Pipeline integration touches other country paths** — scope creep risk; keep changes UK-scoped.
5. **FRED OECD mirror completely breaks** if TE primary cascade incomplete — ensure fallback preserved throughout.
6. **Coverage regression > 3pp** → HALT.
7. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
8. **Concurrent Sprint K touches same files** (shouldn't per §3) → reconcile via rebase.

---

## 6. Acceptance

### Global sprint-end
- [ ] 4-5 commits pushed, main HEAD matches remote, CI green
- [ ] `fetch_uk_bank_rate` wrapper shipped + HistoricalDataSymbol guard
- [ ] UK 10Y gilt wrapper verified or added
- [ ] `build_m1_uk_inputs` cascade updated: TE primary → BoE secondary → FRED staleness-flagged last-resort
- [ ] Flag lexicon: `UK_BANK_RATE_TE_PRIMARY` + `UK_BANK_RATE_FRED_FALLBACK_STALE` + `CALIBRATION_STALE` working
- [ ] Live canary PASS: `@slow` tests verify TE path + FRED fallback path
- [ ] Sprint I retrospective amendment documents correction
- [ ] Coverage maintained ≥ existing + additions ≥ 90%
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week8-sprint-i-patch-te-cascade-report.md`

**Final tmux echo**:
```
SPRINT I-PATCH TE CASCADE DONE: N commits, signal quality corrected
UK M1 cascade: TE primary → BoE secondary → FRED staleness-flagged last-resort
TE HistoricalDataSymbol validated: [actual]
Live canary: TE path working + FRED fallback tested
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/week8-sprint-i-patch-te-cascade-report.md
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

### Why this patch now
Sprint I Day 1 shipped signal quality regression via FRED OECD monthly mirror. User identified — correct call. Phase 1 cannot defer signal quality debt to production.

### TE is canonical — infrastructure already paid
TE Pro 10k calls/mês, ~60 lifetime usage. UK Bank Rate wrapper adds ~30 calls/month production — negligible impact on quota.

### Pattern 4 Aggregator-primary
This is textbook Pattern 4 application — TE is proven aggregator with native-override capability (BoE when reachable). FRED last-resort is acceptable degradation.

### No ProtonVPN
Rejected. Operational complexity vs single-operator maintenance burden; redundant given TE; grey-area ToS for BoE.

### Lesson for future country expansions
JP BoJ (Sprint L Week 8 Day 3) should default to TE primary + BoJ native-override + FRED last-resort. Pattern applies to all non-US country expansions.

### Sprint K paralelo viability
This brief's scope (TE connector + M1 UK builder) has zero file overlap with Sprint K (daily_cycles + regimes + CLI status). Safe paralelo.

---

*End of Sprint I-patch brief. 4-5 commits. Signal quality correction. ~1-1.5h CC.*
