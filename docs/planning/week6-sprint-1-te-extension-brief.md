# Week 6 Sprint 1 — TE Pro Extension (Fallback for FRED Delisted + DE Sentiment)

**Target**: Extend `connectors/te.py` to serve as fallback for FRED-delisted US sentiment (ISM Mfg/Services, NFIB, CB Consumer Confidence) + DE-specific sentiment (Ifo, ZEW). Resolves CAL-092 + CAL-086 + CAL-093.

**Priority**: HIGH (unlocks E4 Sentiment quality materially — US from 6/13 to ~10/13 components; DE from 3/13 to 7-8/13)

**Budget**: 2–3h CC autonomous
**Commits**: ~5–7
**Base**: main HEAD post Sprint 2b (`6089572` or later)
**Concurrency**: Parallel to Week 6 Sprint 1b MSC indices brief in tmux `sonar-l3`. See §3.

---

## 1. Scope

In:
- Extend `src/sonar/connectors/te.py` with:
  - Generic `fetch_indicator(country_iso, indicator_name, start_date, end_date)` using TE `/indicators/country/{country}` endpoint
  - Specific wrappers for CAL-targeted indicators
- Update E4 Sentiment builder in `src/sonar/indices/economic/builders.py` with TE as secondary-priority fallback (FRED primary → TE fallback → flag `TE_FALLBACK_{INDICATOR}`)
- Unit tests + cassette fixtures + live canaries
- Close CAL-092 (FRED ISM/NFIB delisted) + CAL-086 (ZEW + Ifo DE) + CAL-093 (CB Consumer Confidence stale)
- Retrospective

Out:
- Primary-source migration to TE (TE stays fallback; FRED/Eurostat primary where working)
- BoJ Tankan JP (CAL-087, JP out of T1 Phase 1 scope)
- Policy uncertainty scrape (CAL-085, FRED USEPUINDXD still works)
- Atlanta Fed wage tracker (CAL-084, separate US-specific CAL)
- ECB SDW connector refinements (MSC scope)

---

## 2. Spec reference

Authoritative:
- `docs/backlog/calibration-tasks.md` — CAL-092, CAL-086, CAL-093 entries
- `docs/specs/indices/economic/E4-sentiment.md` §2 — TE-fetchable indicators noted as fallback path in some rows
- `docs/governance/LICENSING.md` §7 — TE terms, Pro tier usage
- SESSION_CONTEXT §Decision authority + §Brief format + §Regras operacionais

Existing assets:
- `src/sonar/connectors/te.py` — currently ships `fetch_sovereign_yield_historical` + `fetch_10y_window_around` (Week 3.5 scope)
- `.env` — `TE_API_KEY` configured (Pro tier, 10k calls/mês total)
- `src/sonar/connectors/crp.py` (via overlays/crp.py) — existing TE consumer (sovereign yields)

**TE Pro capacity planning**: 10k calls/mês budget.
- This sprint live canaries: ~15 calls one-time
- Daily refresh post-ship: ~10 calls/day × 30 days = 300 calls/month
- Historical backfill (20Y monthly data × 6 indicators): ~1440 calls one-time spread over days
- Remaining margin: ~8k calls/mês buffer for ad-hoc / new indicators

---

## 3. Concurrency — parallel protocol with MSC brief

MSC brief runs concurrently in tmux `sonar-l3`. Both push to main.

**Hard-locked resource allocation**:
- Migration numbers: **this brief creates no migration**. MSC brief uses 014 (next after 013).
- `src/sonar/db/models.py`: **no changes** (no new ORMs)
- `src/sonar/connectors/`: this brief modifies `te.py` only. MSC touches `cbo.py` (new) + potentially extends `fred.py` / `ecb_sdw.py`. Zero file overlap.
- `src/sonar/indices/`: this brief modifies `indices/economic/builders.py`. MSC creates `indices/monetary/{m1_effective_rates,m2_taylor_gaps,m4_fci}.py`. Zero overlap (economic vs monetary packages).
- Tests: separate test files per existing pattern
- `pyproject.toml`: neither brief expected to add deps

**Push race handling**:
- Normal `git pull --rebase origin main` on rejection
- `te.py` modifications + `builders.py` additions — MSC doesn't touch these

**Start order**: this brief arranca primeiro (small sprint, closes early, unblocks idle CC for any cleanup). MSC arranca ~1 min depois.

---

## 4. Commits

### Commit 1 — TE generic indicator fetcher

```
feat(connectors): TE generic indicator fetcher for multi-country data

Extend src/sonar/connectors/te.py with:

Public method:
  fetch_indicator(country_iso: str, indicator_name: str,
                  start_date: date, end_date: date)
    -> list[TEIndicatorObservation]

TE endpoint pattern:
  GET https://api.tradingeconomics.com/historical/country/{country}/indicator/{indicator}
  Auth: ?c={TE_API_KEY}
  Format: JSON list of {Country, Category, DateTime, Value, ...}

Country code mapping: TE uses country names (e.g., "united states",
"germany") not ISO codes. Add `_TE_COUNTRY_NAME_MAP` dict translating
ISO 3166-1 alpha-2 → TE canonical country name for 7 T1 set:
  {'US': 'united states', 'DE': 'germany', 'PT': 'portugal', ...}

Indicator name: TE uses spaces + lowercase (e.g., "ism manufacturing
pmi", "zew economic sentiment index"). Store exact names as constants:
  TE_INDICATORS_ISM_MFG = "ism manufacturing pmi"
  TE_INDICATORS_ISM_SVC = "ism non manufacturing pmi"
  TE_INDICATORS_NFIB = "nfib business optimism index"
  TE_INDICATORS_IFO = "ifo business climate"
  TE_INDICATORS_ZEW = "zew economic sentiment index"
  TE_INDICATORS_CB_CC = "consumer confidence"

Schema-drift guard: if response JSON missing Value/DateTime fields,
raise DataUnavailableError with indicator context. Empty response
(country/indicator pair not in TE coverage) raises same.

Rate limiting: reuse existing `tenacity` retry pattern. Polite pacing
1 req/sec (TE Pro allows bursts but conservative).

Cache: reuse existing ConnectorCache; TTL 24h per (country, indicator,
start, end) tuple.

Tests:
- Unit cassette-replay: 3+ indicators × 2 countries minimum
- @pytest.mark.slow live canary: fetch ISM Manufacturing US last 12
  months, assert non-empty + values in [20, 80] (PMI range)
- Coverage ≥ 92% on te.py (target; currently higher since small file)

Sanity check commit body:
  python -c "from sonar.connectors.te import TEConnector, TE_INDICATORS_ISM_MFG; print('OK')"
```

### Commit 2 — TE specific wrappers per CAL-targeted indicator

```
feat(connectors): TE specific wrappers per CAL-092 + CAL-086 + CAL-093

Add convenience methods to TEConnector wrapping fetch_indicator:

# CAL-092 (FRED ISM/NFIB delisted):
- fetch_ism_manufacturing_us(start, end) -> list[TEObservation]
- fetch_ism_services_us(start, end)
- fetch_nfib_us(start, end)

# CAL-086 (DE sentiment):
- fetch_ifo_business_climate_de(start, end)
- fetch_zew_economic_sentiment_de(start, end)

# CAL-093 (CB Consumer Confidence US):
- fetch_conference_board_cc_us(start, end)

Each wrapper:
- Validates that country_iso_fixed matches (US/DE per wrapper)
- Calls fetch_indicator with constant indicator name
- Returns normalized data (value as float, date as date_t)

Unit tests: 1+ test per wrapper using cassettes.

Each wrapper cassette stored at:
  tests/cassettes/connectors/te_{indicator_snake_case}_{country}_{date}.json

Live canary: @pytest.mark.slow, fetch all 6 indicators for last 6
months, assert each returns ≥ 3 observations + values within sanity
bands (PMI [20,80], sentiment indices [50, 150] generally).
```

### Commit 3 — E4 builder TE fallback integration

```
feat(indices): E4 Sentiment builder TE fallback wiring

Modify src/sonar/indices/economic/builders.py:

Extend build_e4_inputs(country, date, eurostat_conn, fred_conn,
                        te_conn) to accept TE connector.

Priority logic per component (primary → fallback → flag):
1. UMich sentiment US: FRED UMCSENT (primary) → no TE fallback (FRED
   works). No flag.
2. Conference Board CC US: FRED CONCCONF (stale per CAL-093) →
   TE fetch_conference_board_cc_us → flag TE_FALLBACK_CB_CC
3. ISM Manufacturing US: FRED NAPM (delisted) → TE fetch_ism_manufacturing_us
   → flag TE_FALLBACK_ISM_MFG
4. ISM Services US: FRED NAPMII (delisted) → TE fetch_ism_services_us
   → flag TE_FALLBACK_ISM_SVC
5. NFIB US: FRED NFIBBTI (delisted) → TE fetch_nfib_us
   → flag TE_FALLBACK_NFIB
6. Ifo DE: Eurostat not applicable → TE fetch_ifo_business_climate_de
   → flag TE_FALLBACK_IFO
7. ZEW DE: Eurostat not applicable → TE fetch_zew_economic_sentiment_de
   → flag TE_FALLBACK_ZEW
8. Other components unchanged (UMich 5Y infl, ESI, VIX, SLOOS)

Graceful degradation: if TE fetch also fails (rare), flag
{INDICATOR}_UNAVAILABLE + None. E4 compute §6 handles minimum
threshold.

Unit tests: builder tests with mocked TE responses covering:
- TE primary path (when FRED delisted)
- TE fallback fails → flag + None
- Priority order verified (FRED tried first when available)

Coverage ≥ 90% on builders.py extension.
```

### Commit 4 — Rate-limit telemetry + call-count log

```
feat(connectors): TE call counter + rate-limit telemetry

Lightweight call tracking to avoid silent quota exhaustion.

Add to TEConnector:
- Instance attr `_call_count: int = 0` incremented per fetch
- Optional class-level counter for process-level aggregate
- Method `get_call_count() -> int` + `reset_call_count()`
- Log line on each fetch: structlog.info(
    "te.call",
    indicator=indicator_name,
    country=country_iso,
    cumulative_calls=self._call_count,
  )

Daily pipeline adoption (future): log summary at end of each run:
"TE daily refresh: N calls today, M.m calls/month estimated"

No hard quota enforcement this sprint (not ready for production
quota management). Just telemetry for ops visibility.

Tests: 2+ unit tests confirming counter increments + reset works.
Documented in retrospective as operational hook for future CAL.
```

### Commit 5 — Integration smoke: E4 with TE fallback US + DE

```
test(integration): E4 Sentiment with TE fallback US + DE smoke

tests/integration/test_e4_te_fallback.py:

@pytest.mark.slow
def test_e4_us_with_te_fallback():
    """Build E4 inputs for US with TE covering delisted FRED series.
    Assert resulting E4 has ≥ 10 of 13 components available (vs
    baseline 6/13 without TE)."""
    # Mocked FRED returning delisted (DataUnavailableError)
    # Live TE fetches for ISM Mfg/Svc, NFIB, CB CC
    # Build E4Inputs
    # Assert components_available >= 10
    # Assert flags contain TE_FALLBACK_ISM_MFG, TE_FALLBACK_ISM_SVC,
    #        TE_FALLBACK_NFIB, TE_FALLBACK_CB_CC

def test_e4_de_with_te_fallback():
    """Build E4 inputs for DE with TE covering Ifo + ZEW.
    Assert resulting E4 has ≥ 7 of 13 components (vs baseline 3/13)."""
    # Similar pattern

Both tests wall-clock ~15-30s. Real TE API calls ~12 calls total
(within quota trivially).
```

### Commit 6 — Close CAL items + retrospective

```
docs(planning): Week 6 Sprint 1 TE extension retrospective

File: docs/planning/retrospectives/week6-sprint-1-te-extension-report.md

Structure per prior retrospectives:
- Summary (duration, commits, CAL closures)
- Commits table with SHAs + CI status
- CAL resolutions: CAL-092 (ISM + NFIB), CAL-086 (ZEW + Ifo), CAL-093 (CB CC)
- TE indicator coverage validation matrix
- E4 quality delta:
  - US: 6/13 → ~10-11/13 components available (mitigation)
  - DE: 3/13 → ~7-8/13 components
  - PT/IT/ES/FR/NL: unchanged (spec-intent gap; Phase 2 threshold relax)
- TE rate-limit status: calls used in sprint, projected daily refresh
- HALT triggers fired / not fired
- Deviations from brief
- New backlog items (unlikely but possible):
  - CAL-098 potential: TE rate-limit production monitoring (if telemetry insufficient)
  - CAL-099 potential: TE historical backfill automation
- Sprint 2 readiness: ECS composite now has real high-quality inputs
  for US + DE; ECS composite Week 6 Sprint 2 ready to proceed

Close CAL-092, CAL-086, CAL-093 explicitly in
docs/backlog/calibration-tasks.md.
```

---

## 5. HALT triggers (atomic)

0. **Pre-flight spec deviation** — CC reads E4-sentiment.md §2 + CAL-092/086/093 entries at Commit 1. If E4 spec indicates incompatible data source preference or has TE-exclusion rule → HALT, reconcile
1. **TE Pro quota unexpectedly exhausted** (10k calls/mês hit) → HALT, investigate telemetry + monthly quota reset timing
2. **TE country name mapping fails** — indicator exists for country but TE returns 400 due to name format mismatch → document + debug name; if unresolvable in 15min, HALT
3. **TE indicator name format unexpected** — spec names per SESSION_CONTEXT may differ from live TE API (CAL-019 pattern for BIS) → empirical probe + document canonical names; if pattern brittle, surface CAL
4. **TE API returns different schema** than existing code assumes (Week 3.5 sovereign yield path) → check compatibility; if breaking, isolate via separate method variant
5. **ISM Manufacturing/Services not actually in TE** — verify Commit 1 live canary; if absent, shift to CAL-082 ISM direct scrape
6. **NFIB not in TE coverage** — similar; shift to separate CAL
7. **Ifo / ZEW DE name format edge cases** — TE may catalog as "ifo business climate index" vs "ifo business climate"; empirical resolution
8. **CB Consumer Confidence US in TE** — verify availability; FRED CONCCONF stale per CAL-093 but CB data via TE may lag 30-60 days
9. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy project.
10. **Concurrent MSC brief touches te.py** (shouldn't per its brief) → reconcile via rebase

---

## 6. Acceptance

### Per commit
Commit body checklist enforceable.

### Global sprint-end
- [ ] 5-7 commits pushed, main HEAD matches remote, CI green
- [ ] `src/sonar/connectors/te.py` coverage ≥ 92% (maintain + increase)
- [ ] 6 new TE wrappers functional + cassettes + live canaries
- [ ] `src/sonar/indices/economic/builders.py` TE fallback integration tested
- [ ] E4 integration smoke: US ≥ 10 components, DE ≥ 7 components available
- [ ] CAL-092, CAL-086, CAL-093 CLOSED in docs/backlog/calibration-tasks.md
- [ ] TE call counter + structlog telemetry live
- [ ] No `--no-verify` pushes
- [ ] Pre-push gate (full mypy + ruff + pytest) enforced before every push
- [ ] TE calls this sprint ≤ 20 (well within quota)

---

## 7. Report-back artifact export (mandatory)

File: `docs/planning/retrospectives/week6-sprint-1-te-extension-report.md`

Structure per Commit 6 template.

**Per-commit tmux echoes**:
```
COMMIT N/5-7 DONE: <scope>, SHA, coverage delta, live-canary status, HALT status
```

**Final tmux echo**:
```
WEEK 6 SPRINT 1 DONE: N commits, TE fallback extended
E4 US: 6/13 → 10-11/13 | DE: 3/13 → 7-8/13
HALT triggers: [list or "none"]
CAL closed: CAL-092, CAL-086, CAL-093
Artifact: docs/planning/retrospectives/week6-sprint-1-te-extension-report.md
```

---

## 8. Pre-push gate (mandatory)

Before every `git push`:
```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov
```

All four exit 0. Full project mypy — NOT scoped to committed files.

No `--no-verify`.

Live canaries (`@pytest.mark.slow`) do NOT run in default pytest.

---

## 9. Notes on implementation

### TE country name mapping is a real trap
TE API uses full country names not ISO codes. `_TE_COUNTRY_NAME_MAP` dict is critical. Verify Commit 1 with live probe if uncertain; fail fast with HALT #2.

### Indicator name casing
TE indicator names appear lowercase with spaces. Case-sensitivity might cause 400s. Verify empirically Commit 1.

### Rate limit = conservative
10k/mês Pro tier is not infinite. Polite pacing + telemetry = avoid silent exhaustion. Historical backfill (if deemed necessary Week 7+) might need batched approach respecting monthly budget.

### ISM availability in TE
TE catalog includes US ISM Manufacturing + Services PMI historically. Verify in Commit 1 live canary. If absent, CAL-092 needs alternate path (direct ISM scrape — CAL-082 original).

### Sprint concurrent context
MSC brief running in tmux `sonar-l3`. Zero file overlap per §3. Pre-push gate catches any issues.

### TE vs ISM direct scrape future
If this sprint validates TE as reliable ISM source, CAL-082 (ISM direct scrape) becomes unnecessary. Document decision in retro.

---

*End of Week 6 Sprint 1 TE extension brief. 5-7 commits. E4 Sentiment quality substantially improved US + DE. Concurrent with MSC indices sprint via file-level isolation.*
