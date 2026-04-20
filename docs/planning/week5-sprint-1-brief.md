# Sprint 1 — F-cycle Connectors Live Wiring + Canary Backfill

**Target**: Week 5 Sprint 1 — resolve CAL-061/062/063 + CAL-067 (canary coverage gap)
**Priority**: HIGH (unblocks F4 full stack + FCS composite with strong signal quality)
**Budget**: 4–5h CC autonomous
**Commits**: ~7–9
**Base**: main HEAD post F-cycle (`5a42b15` or later)
**Concurrency**: Parallel to ECS indices brief in tmux `sonar`. See §Concurrency.

---

## 1. Scope

In:
- **CAL-061 MOVE index live wiring**: replace placeholder `move_index.py` with functional data source
- **CAL-062 AAII sentiment live wiring**: replace placeholder `aaii.py` with xls fetch + parsing
- **CAL-063 CFTC COT live wiring**: replace placeholder `cftc_cot.py` with publicreporting.cftc.gov JSON API client
- **CAL-067 canary coverage backfill**: 8 `@pytest.mark.slow` live canary tests for all F-cycle connectors (CBOE, ICE BofA OAS, Chicago Fed NFCI, MOVE, AAII, CFTC COT, FINRA margin debt, BIS property)
- **Cassette fixtures**: pre-record live responses into `tests/cassettes/connectors/` for deterministic test replay
- 3 CAL items closed in `docs/backlog/calibration-tasks.md`
- Retrospective artifact

Out:
- FCS composite (Sprint 2 scope)
- F4 index internal logic changes (only inputs become live — logic unchanged)
- F3 signal reweighting (same — spec flags handle redistribution)
- Backfilling historical AAII/COT/MOVE data beyond 5Y (only current window + rolling updates)

---

## 2. Spec reference

Authoritative:
- `docs/backlog/calibration-tasks.md` — CAL-061, CAL-062, CAL-063, CAL-067 entries
- `docs/specs/indices/financial/F3-risk-appetite.md` §2 — MOVE as input
- `docs/specs/indices/financial/F4-positioning.md` §2 — AAII + COT as inputs
- `docs/specs/overlays/exceptions.py` — existing DataUnavailableError pattern
- `docs/governance/LICENSING.md` §7 — data provider governance (Yahoo scrape for MOVE requires consent verification)
- SESSION_CONTEXT §Decision authority + §Brief format + §Regras operacionais

Existing assets:
- `src/sonar/connectors/move_index.py` — placeholder (raises DataUnavailableError)
- `src/sonar/connectors/aaii.py` — placeholder
- `src/sonar/connectors/cftc_cot.py` — placeholder
- `src/sonar/connectors/cboe.py` — live via FRED (reference pattern for canary test)
- `src/sonar/indices/financial/{f3,f4}*.py` — accept `float | None` inputs (gracefully degrade when connectors fail)

---

## 3. Concurrency — parallel protocol with ECS indices brief

ECS brief runs concurrently in tmux `sonar`. Both push to main.

**Hard-locked resource allocation**:
- Migration number: **this brief does NOT create migrations** (no schema changes). ECS uses 012.
- `src/sonar/db/models.py`: **no changes** (no new ORMs). ECS may touch Indices bookmark zone.
- `src/sonar/connectors/`: this brief modifies `move_index.py`, `aaii.py`, `cftc_cot.py` (existing files, replace placeholder logic). ECS creates new files: `eurostat.py`, `spglobal_pmi.py`, `ism.py`. Zero file overlap.
- Tests: this brief touches `tests/unit/test_connectors/test_{move_index,aaii,cftc_cot}.py` + adds canary tests. ECS creates new test files.
- Cassettes: `tests/cassettes/connectors/` — this brief creates. ECS may also create for new connectors. Different subdirectories or filename conventions by connector name — zero collision.
- `pyproject.toml`: this brief may add small deps (lxml for xls parsing if openpyxl insufficient). ECS may add eurostatapiclient or similar. Coordinate: ECS goes first if both need deps; this brief rebases.

**Push race handling**:
- Normal `git pull --rebase` + re-push on rejection
- Cassette binary files may conflict if written to same path — unlikely given file-per-connector naming

---

## 4. Commits

### Commit 1 — MOVE index live wiring

```
feat(connectors): MOVE index live data via Yahoo Finance

Replace placeholder src/sonar/connectors/move_index.py with functional
implementation.

Source: Yahoo Finance ^MOVE symbol (MOVE index ticker).
Endpoint: https://query1.finance.yahoo.com/v7/finance/chart/^MOVE
  ?interval=1d&range=5y
Returns JSON with timestamps + close values.

Implementation:
- BaseConnector subclass (same pattern as cboe.py FRED wrapper)
- fetch_move(start_date, end_date) -> list[Observation]
- Graceful DataUnavailableError on HTTP error or schema drift
  (Yahoo may return unexpected JSON shape)
- Daily cadence; disk-cached per-day

Licensing note: Yahoo Finance data is public via their chart API.
Add attribution note in module docstring. This is consistent with
existing FRED wrapping pattern (public API, internal compute use).

Tests:
- Cassette-replay unit tests (5+ test dates)
- @pytest.mark.slow live canary: fetch MOVE for last 30 days, assert
  non-empty response + value in sanity band (5-200 — MOVE typical range)
- Coverage ≥ 92% per phase1-coverage-policy connector hard gate

pyproject.toml: no new dependencies expected (existing httpx handles).

Close CAL-061 in docs/backlog/calibration-tasks.md with SHA reference.
```

### Commit 2 — AAII sentiment live wiring

```
feat(connectors): AAII sentiment live xls fetch + schema-drift guard

Replace placeholder src/sonar/connectors/aaii.py with functional
xls-based fetcher.

Source: AAII public sentiment survey
URL: https://www.aaii.com/files/surveys/sentiment.xls
Cadence: weekly Thursday update
Schema: bull pct, bear pct, neutral pct, historical going back decades

Implementation:
- BaseConnector subclass
- fetch_aaii_sentiment(start_date, end_date) -> list[Observation]
  Returns bull-bear spread (primary), bull pct + bear pct + neutral pct
  (diagnostic in components_json)
- xls parsing via openpyxl
- Schema-drift guard: assert expected column names (Date, Bullish, Neutral, Bearish)
  at file load; raise SchemaChangedError (new exception) on mismatch
  → caller may fallback to scrape HTML version at
  https://www.aaii.com/sentimentsurvey
- Disk-cached (weekly refresh cadence sufficient)

Exception hierarchy:
- Add SchemaChangedError to src/sonar/connectors/exceptions.py
  (subclass of DataUnavailableError for backward compat)

Tests:
- Cassette-replay unit tests
- Schema drift simulation test (fixture with wrong column names)
- @pytest.mark.slow live canary: fetch AAII current week, assert
  bull+bear+neutral sums to ~100% within 1%
- Coverage ≥ 92%

Close CAL-062 in docs/backlog/calibration-tasks.md.
```

### Commit 3 — CFTC COT live wiring via JSON API

```
feat(connectors): CFTC COT JSON API client for S&P non-comm positions

Replace placeholder src/sonar/connectors/cftc_cot.py with functional
CFTC Socrata JSON API client.

Source: CFTC public reporting API (SODA 2.1)
Base URL: https://publicreporting.cftc.gov/resource/6dca-aqww.json
Auth: none required (public)
Rate limit: undocumented; polite usage 1 req/sec

Filter pattern:
  ?$where=market_and_exchange_names LIKE 'E-MINI S%26P 500%25'
   &$order=report_date_as_yyyy_mm_dd DESC
   &$limit=52   # 1 year weekly data

Implementation:
- BaseConnector subclass
- fetch_cot_sp500_net(start_date, end_date) -> list[Observation]
  Returns non-commercial net positions (noncomm_positions_long_all
  minus noncomm_positions_short_all) weekly
- Optional diagnostic: VIX futures, 10Y Treasury, DXY (spec §2 notes)
  - Skip this sprint unless trivial — flag CFTC_DIAGNOSTIC_DEFERRED
- Weekly Tuesday data published Friday (3-day lag)

Tests:
- Cassette-replay unit tests
- Schema field name stability check
- @pytest.mark.slow live canary: fetch last 4 weeks S&P COT, assert
  non-empty + net position in plausible range (-300k to +300k contracts)
- Coverage ≥ 92%

Close CAL-063 in docs/backlog/calibration-tasks.md.
```

### Commit 4 — Canary tests backfill (F-cycle connectors)

```
test(connectors): add @pytest.mark.slow live canaries for F-cycle 8

Backfill coverage gap flagged as CAL-067 in F-cycle retrospective.
Eight F-cycle connectors shipped Commit 3-5 of F-cycle brief without
live canaries. Add one live canary per connector:

tests/unit/test_connectors/test_cboe.py:
  - test_live_canary_vix_recent() — fetch VIX last 5 days, assert
    non-empty + value in [5, 100]
tests/unit/test_connectors/test_ice_bofa_oas.py:
  - test_live_canary_hy_oas_recent() — fetch BAMLH0A0HYM2 last 30 days,
    assert non-empty + value in [100, 2500] bps
tests/unit/test_connectors/test_chicago_fed_nfci.py:
  - test_live_canary_nfci_recent() — fetch NFCI last 4 weeks, assert
    non-empty + value in [-2, 5]
tests/unit/test_connectors/test_finra_margin_debt.py:
  - test_live_canary_margin_recent() — fetch BOGZ1FL663067003Q last
    2 quarters, assert non-empty + value positive
tests/unit/test_connectors/test_bis.py:
  - test_live_canary_property_recent() — fetch BIS property PT last
    year, assert non-empty index values
+ canaries for MOVE (Commit 1), AAII (Commit 2), CFTC COT (Commit 3)
  already added inline

All canaries @pytest.mark.slow + @pytest.mark.live (if slow marker
overloaded). Run via `pytest -m "slow and live"` — not in default
test run; CI may enable on nightly schedule.

Close CAL-067 in docs/backlog/calibration-tasks.md.
```

### Commit 5 — Cassette fixtures backfill

```
test(connectors): cassette fixtures for F-cycle connectors

Pre-recorded BIS + FRED + Yahoo + AAII + CFTC responses for
deterministic test replay.

Create tests/cassettes/connectors/ directory structure:
- cboe_vix_2024_01_02.json
- ice_bofa_hy_oas_2024_01_02.json
- chicago_nfci_2024_01_02.json
- move_yahoo_2024_01_02.json
- aaii_sentiment_2024_01_02.xlsx (binary; small file, ~50KB)
- cftc_cot_sp500_2024_01_02.json
- finra_margin_2024_01_02.json
- bis_property_pt_2024_01_02.json

Tests:
- Cassette-replay unit tests in corresponding test_*.py files use
  these fixtures instead of live HTTP
- Mock transport that reads from fixture file matching request URL
- Deterministic; CI-safe

Pattern: if connector tests were pure mock-based before (per F-cycle
retrospective finding), this commit upgrades them to cassette-based.
Cleaner audit trail + catches schema drift via fixture file shape.

Rationale per CAL-067: sprint findings showed F-cycle connectors
shipped with pure mocks. Cassettes provide middle ground between
mocks (no network) and live (unreliable in CI).
```

### Commit 6 — Verification: F4 now live with real data

```
test(integration): F4 live-path smoke test — post-CAL-061/062/063

Add tests/integration/test_f4_live_integration.py:
- @pytest.mark.slow
- Fetch live AAII + CFTC COT + MOVE (via new connectors)
- Fetch live VIX + margin debt (existing connectors)
- Compose F4Inputs with all 5 components
- Invoke compute_f4_positioning
- Assert:
  - All 5 components non-None
  - score_normalized ∈ [0, 100]
  - No US_PROXY_POSITIONING flag
  - No AAII_PROXY flag
  - confidence ≥ 0.75 (full-components baseline)

Test is smoke-only — single run on US 2024-01-02 equivalent window.
Not 7-country exhaustive (that's Sprint 2 scope).

Demonstrates Sprint 1 objective met: F4 can run at full fidelity.
```

### Commit 7 — Retrospective

```
docs(planning): Week 5 Sprint 1 retrospective

File: docs/planning/retrospectives/week5-sprint-1-live-wiring-report.md

Structure per prior retrospectives:
- Summary (duration, commits, status)
- Commits table with SHAs + CI status
- CAL resolutions: CAL-061 MOVE, CAL-062 AAII, CAL-063 COT, CAL-067 canaries
- Live validation outcomes:
  - MOVE index current range
  - AAII sentiment current bull/bear spread
  - CFTC COT current S&P non-comm net
  - All 8 F-cycle connector canaries PASS/FAIL
- Schema drift guards:
  - AAII xls schema confirmed stable (or drift detected)
  - CFTC JSON field names confirmed
- F4 full-stack verification: smoke test passed
- HALT triggers fired / not fired
- Coverage delta: F-cycle connectors
- Deviations from brief
- New backlog items (if any)
- Sprint 2 readiness: F-cycle connectors production-grade,
  FCS composite can now compute with strong F4 inputs

Commit closes CAL-061, CAL-062, CAL-063, CAL-067 explicitly.
```

---

## 5. HALT triggers (atomic)

1. **Yahoo MOVE API requires cookie or auth** → fall back to alternative (Stooq.com, alpha vantage if key available, or direct ICE scrape); document in commit body
2. **AAII xls endpoint 404 or renamed** → fallback to HTML scrape of sentimentsurvey page
3. **CFTC Socrata API schema change** (field names) → document + use latest schema; if fundamentally different, HALT
4. **MOVE value sanity out of [5, 200]** during live canary → halt, verify source + scale (may need decimal normalization)
5. **Any connector hits rate limit during live canary** → halt, increase pacing
6. **Coverage regression > 3pp** on connectors scope → halt
7. **AAII xls parsing requires new Python library** beyond openpyxl → evaluate; if material scope creep, defer to separate commit
8. **CFTC JSON response > 10MB** (unlikely for filtered query) → pagination needed; halt, add to commit
9. **Pre-push gate fails** → fix before push, no `--no-verify`
10. **Concurrent ECS brief touches connectors/ via new file** with same rationale as one we're creating → halt, reconcile

"User authorized in principle" does NOT cover specific triggers.

---

## 6. Acceptance

### Per commit
Commit body checklist enforceable.

### Global sprint-end
- [ ] 7-9 commits pushed, main HEAD matches remote, all CI green
- [ ] `src/sonar/connectors/move_index.py` coverage ≥ 92%; live canary PASS
- [ ] `src/sonar/connectors/aaii.py` coverage ≥ 92%; schema-drift guard tested; live canary PASS
- [ ] `src/sonar/connectors/cftc_cot.py` coverage ≥ 92%; live canary PASS
- [ ] 5 additional `@pytest.mark.slow` canaries added (CBOE, ICE BofA, Chicago NFCI, FINRA, BIS property)
- [ ] 8 cassette fixture files committed in `tests/cassettes/connectors/`
- [ ] Integration smoke: F4 US 2024-01-02 equivalent runs with all 5 components non-None
- [ ] CAL-061, CAL-062, CAL-063, CAL-067 all CLOSED in `docs/backlog/calibration-tasks.md`
- [ ] No `--no-verify` pushes

---

## 7. Report-back artifact export (mandatory)

File: `docs/planning/retrospectives/week5-sprint-1-live-wiring-report.md`

Structure per Commit 7 template.

**Per-commit tmux echoes** (short form):
```
COMMIT N/7 DONE: <scope>, SHA, coverage delta, canary status, HALT status
```

**Final tmux echo**:
```
SPRINT 1 DONE: N commits, 3 live connectors wired + 8 canaries backfilled
F4 full-stack verified: all 5 components live
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/week5-sprint-1-live-wiring-report.md
```

---

## 8. Pre-push gate (mandatory per CI-debt saga lessons)

Before every `git push`:
```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov
```

All four exit 0. No `--no-verify`.

Live canaries (`@pytest.mark.slow`) do NOT run in default pytest invocation — they run via explicit `pytest -m slow` or CI nightly. Pre-push gate stays fast.

---

## 9. Notes on implementation

### MOVE alternative sources if Yahoo fails
Fallbacks documented in `governance/LICENSING.md` §7:
1. Stooq.com (no API but CSV download)
2. Alpha Vantage (requires API key)
3. FRED (if ever added — historically not there)

Pick cleanest. Document rationale in commit body.

### AAII schema drift guard
AAII is historically stable but not guaranteed. Schema-drift guard protects against xls structure changes without silent breakage.

### CFTC JSON API preferred over text format
Socrata API is structured, paginated, filterable. Text format at cftc.gov/dea/newcot/deacot.txt is legacy and harder to parse reliably.

### Cassette size discipline
Binary .xlsx fixtures can bloat repo if unbounded. Limit to 1 representative fixture per connector per reference date. Prune if > 100KB each.

### Parallel ECS brief
Runs in tmux `sonar`. Zero file overlap expected. If conflicts emerge at push time, normal rebase + re-push. Pre-push gate applies.

---

*End of Sprint 1 brief. 7-9 commits, 3 CAL live wiring + 1 CAL canary backfill, production-grade F-cycle. Sprint 2 (CCCS + FCS composites) follows after this closes.*
