# Week 6 Sprint 3 — Connector Quick Wins

**Target**: Close 3 open CAL items + add 2 new data quality uplifts via TE catalog discovery.

**Priority**: HIGH (unblocks F4 5/5 US coverage, FCS Bubble Warning condition-3, E4 +2 components US)

**Budget**: 2.5–3h CC autonomous
**Commits**: ~7-9
**Base**: main HEAD (post MSC c6 + Ingestion Omnibus in-progress; CC picks up latest)
**Concurrency**: Parallel to Week 6 Sprint 2b Ingestion Omnibus still running in tmux `sonar-l3`. See §3.

---

## 1. Scope

In:
- **CAL-072 resolve**: Fix BIS `WS_LONG_PP` → `WS_SPP` dataflow rename in `connectors/bis.py`. Re-record cassette. Remove xfail marker on BIS property canary.
- **CAL-093 re-open + resolve**: Conference Board Consumer Confidence via TE. Empirical validation already confirmed TE `consumer confidence` indicator returns Conference Board data (HistoricalDataSymbol `CONCCONF`). Previous Sprint 1 Week 6 conclusion was incorrect premise. Add `fetch_conference_board_cc_us()` wrapper + E4 builder TE fallback.
- **New CAL (to surface)**: Michigan 5Y Inflation Expectations (MICHM5YM5 FRED delisted). TE catalog confirmed `michigan 5 year inflation expectations` indicator exists. Add `fetch_michigan_5y_inflation_us()` wrapper + E4 builder TE fallback.
- **CAL-073 resolve**: CBOE put/call (PUTCLSPX FRED delisted). Yahoo Finance `^CPC` symbol. Add `connectors/yahoo_finance.py` extension or new connector mirroring MOVE pattern from Week 5 Sprint 1. Wire into F4 Positioning builder.
- Unit tests + cassettes + `@pytest.mark.slow` live canaries
- Integration smoke: verify E4 US component count delta (pre-sprint baseline → post-sprint +2) + F4 US components (4/5 → 5/5)
- Close CAL-072, CAL-073, CAL-093 + open+close new CAL for UMich 5Y
- Retrospective

Out:
- MSC composite re-run with newly-available data (trivial; next daily pipeline run picks up automatically)
- Nasdaq Data Link paid subscription (alternative CB path — not needed since TE resolves)
- CBOE direct scraping (alternative put/call path — Yahoo sufficient)
- Atlanta Fed wage tracker (CAL-084, separate scope)
- BoJ Tankan (CAL-087, JP not in scope yet)
- Daily pipeline refresh orchestration changes (composite auto-upgrades when sub-indices update)

---

## 2. Spec reference

Authoritative:
- `docs/backlog/calibration-tasks.md` — CAL-072, CAL-073, CAL-093 entries + add new UMich 5Y CAL
- `docs/specs/indices/financial/F4-positioning.md` §2 — put/call_ratio input
- `docs/specs/indices/economic/E4-sentiment.md` §2 — cb_confidence + umich_5y_inflation inputs
- `src/sonar/connectors/move_index.py` — reference pattern for Yahoo Finance `^MOVE` wrapper (mirror pattern para `^CPC`)
- `src/sonar/connectors/te.py` — existing wrappers pattern (Sprint 1 Week 6)
- SESSION_CONTEXT §Decision authority + §Brief format + §Regras operacionais

**Pre-flight verification completed** (this sprint does not require fresh spec reading — scope validated via empirical probes):
- TE `consumer confidence` → HistoricalDataSymbol `CONCCONF` (Conference Board source confirmed)
- TE `michigan 5 year inflation expectations` → valid data returns
- TE `michigan consumer expectations` → HistoricalDataSymbol `USAMCE` (distinct from CB)
- BIS `WS_SPP` vs `WS_LONG_PP` — Sprint 1 Week 5 retrospective documents rename

Existing assets:
- `src/sonar/connectors/bis.py` — has `fetch_property_price_index` using `WS_LONG_PP` (404s live)
- `src/sonar/connectors/te.py` — 6 TE wrappers shipped Sprint 1 Week 6
- `src/sonar/connectors/move_index.py` — Yahoo Finance `^MOVE` pattern (reference)
- `src/sonar/indices/economic/builders.py` — E4 builder already tries FRED for CB + UMich 5Y; missing TE fallback wiring
- `src/sonar/indices/financial/f4_positioning.py` — F4 compute module; may or may not have put/call already wired

---

## 3. Concurrency — parallel with Ingestion Omnibus (still running)

Ingestion Omnibus continues in tmux `sonar-l3`. Last visible commits: `bdaea88` (FRED monetary) + `2f38a82` (CBO) + `c82ce18`. Ingestion Omnibus likely in C3-C5 of 7 at sprint start time.

**Hard-locked resource allocation**:
- Migration numbers: **this brief creates no migration**. Ingestion Omnibus may create none too (per its brief). If Ingestion lands migration (unlikely), CC coordinates via rebase.
- `src/sonar/db/models.py`: **no changes** from this brief.
- `src/sonar/connectors/`: this brief modifies `bis.py` + `te.py` + creates/extends `yahoo_finance.py`. Ingestion Omnibus modifies `fred.py` + `cbo.py` (new) + `ecb_sdw.py`. **Zero overlap** — different files.
- `src/sonar/indices/`: this brief modifies `economic/builders.py` + possibly `financial/builders.py` or `financial/f4_positioning.py`. Ingestion Omnibus creates `monetary/builders.py`. Different sub-packages — **zero overlap**.
- Tests: separate test files per existing pattern.
- `docs/backlog/calibration-tasks.md`: **both briefs modify** (Quick Wins closes CAL-072/073/093 + opens UMich; Ingestion closes CAL-096/097/098/100). Last-write-wins via rebase. Established pattern.
- `pyproject.toml`: no new deps either side.

**Push race handling**:
- Normal `git pull --rebase origin main`
- If `calibration-tasks.md` conflicts, merge manually adding both sets of CAL modifications
- Connectors files are different — no concurrency issue

**Start order**: this brief arranca **now** (MSC tmux idle). Ingestion Omnibus continues in its tmux uninterrupted.

---

## 4. Commits

### Commit 1 — Fix BIS WS_LONG_PP → WS_SPP (CAL-072)

```
fix(connectors): BIS property dataflow WS_LONG_PP -> WS_SPP (CAL-072)

Problem: BIS renamed property price dataflow from WS_LONG_PP to WS_SPP
(discovered Week 5 Sprint 1 live canary; xfailed since).

Actions in src/sonar/connectors/bis.py:
- Replace all "WS_LONG_PP" references with "WS_SPP"
- Dataflow key structure likely identical (SDMX-JSON 1.0); verify live
- Update any constants / module-level dataflow IDs
- Update docstrings referencing old name

Actions in tests:
- Re-record cassette for fetch_property_price_index with WS_SPP data
- Remove @pytest.mark.xfail(strict=False) from property canary
  (tests/unit/test_connectors/test_bis.py or wherever located)
- Live canary assert: fetch PT property price last year, non-empty
  observations returned

Verification commit body:
- Show before/after dataflow ID diff in bis.py
- Confirm cassette re-record (file path + size)
- Confirm canary passes (uncomment xfail, run pytest -m slow)

Close CAL-072 in docs/backlog/calibration-tasks.md with SHA reference.

Tests: re-recorded cassette + un-xfailed canary. Coverage bis.py
maintains ≥ 95%.

Pre-flight check commit body:
  grep -n "WS_LONG_PP" src/sonar/connectors/bis.py  # should return 0 matches after commit
```

### Commit 2 — TE Conference Board CC wrapper (CAL-093 resolve)

```
feat(connectors): TE Conference Board Consumer Confidence (CAL-093 resolve)

Previous Sprint 1 Week 6 closed CAL-093 as "not resolvable by TE"
based on premise that TE US "Consumer Confidence" = UMich-sourced.
Empirical validation (2026-04-20) disproves this:
- TE indicator "consumer confidence" → HistoricalDataSymbol CONCCONF
  (Conference Board source, confirmed via /historical/... endpoint)
- TE indicator "michigan consumer expectations" → HistoricalDataSymbol
  USAMCE (distinct UMich series)

Add wrapper to src/sonar/connectors/te.py:

async def fetch_conference_board_cc_us(
    self, start: date, end: date
) -> list[TEIndicatorObservation]:
    """Conference Board Consumer Confidence Index (US).
    TE indicator name: 'consumer confidence'.
    Source: The Conference Board (CONCCONF).
    Monthly cadence; validates schema-drift + source match."""
    return await self.fetch_indicator(
        country_iso="US",
        indicator_name="consumer confidence",
        start_date=start,
        end_date=end,
    )

Pre-flight source validation (Commit 2 body):
- TE response contains HistoricalDataSymbol field
- Assert first observation's symbol starts with 'CONCCONF' (not 'USAMCE')
- If mismatch, raise SchemaChangedError

Tests:
- Cassette: tests/cassettes/connectors/te_consumer_confidence_us_*.json
- Unit test: wrapper calls generic fetch_indicator with correct args
- @pytest.mark.slow live canary: fetch last 3 months, assert
  ≥ 1 observation + HistoricalDataSymbol == CONCCONF (source guard)
  + value in plausible CB CC range [50, 150]

Coverage te.py maintains ≥ 92%.

Re-open CAL-093 in docs/backlog/calibration-tasks.md; document
that previous Sprint 1 Week 6 premise was incorrect; resolve.
```

### Commit 3 — TE Michigan 5Y Inflation Expectations wrapper (new CAL)

```
feat(connectors): TE Michigan 5Y Inflation Expectations (new CAL close)

MICHM5YM5 FRED series delisted (flagged Sprint 2a live validation).
TE catalog confirmed `michigan 5 year inflation expectations`
indicator live (empirical validation 2026-04-20).

Add wrapper to src/sonar/connectors/te.py:

async def fetch_michigan_5y_inflation_us(
    self, start: date, end: date
) -> list[TEIndicatorObservation]:
    """UMich 5-10Y inflation expectations (US).
    TE indicator name: 'michigan 5 year inflation expectations'.
    Source: University of Michigan Survey of Consumers.
    Monthly cadence."""
    return await self.fetch_indicator(
        country_iso="US",
        indicator_name="michigan 5 year inflation expectations",
        start_date=start,
        end_date=end,
    )

Tests:
- Cassette: tests/cassettes/connectors/te_michigan_5y_inflation_us_*.json
- Unit test pattern
- @pytest.mark.slow live canary: fetch last 12 months, assert
  ≥ 3 observations + values in [1.5, 5.0] (historical UMich 5Y range)

Coverage te.py maintains ≥ 92%.

Open new CAL in docs/backlog/calibration-tasks.md:
- CAL-XXX (next available number after CAL-101 if any new Sprint 2b
  opened; probably CAL-102 or CAL-103) — "MICHM5YM5 FRED delisted,
  resolved via TE"
- Mark CLOSED immediately (this commit resolves).
```

### Commit 4 — E4 Sentiment builder TE fallback extension

```
feat(indices): E4 Sentiment TE fallback for CB CC + UMich 5Y inflation

Extend src/sonar/indices/economic/builders.py E4 builder.

Current state (grep confirmed):
- cb_vals attempts fred.fetch_conference_board_confidence_us
- umich_5y_vals attempts fred.fetch_umich_5y_inflation_us
- Both fail silently (FRED delisted) without TE fallback
- ISM/NFIB already have TE fallback pattern from Sprint 1 Week 6

Add TE fallback pattern (mirror ISM Mfg structure):

# After FRED attempt for cb_vals:
if cb_vals is None and te is not None:
    cb_vals = await _try_fetch_te(
        "cb_confidence_te", te.fetch_conference_board_cc_us(start, observation_date)
    )
    if cb_vals is not None:
        flags.append("TE_FALLBACK_CB_CC")
        if "TE" not in sources:
            sources.append("TE")

# After FRED attempt for umich_5y_vals:
if umich_5y_vals is None and te is not None:
    umich_5y_vals = await _try_fetch_te(
        "umich_5y_te", te.fetch_michigan_5y_inflation_us(start, observation_date)
    )
    if umich_5y_vals is not None:
        flags.append("TE_FALLBACK_UMICH_5Y")
        if "TE" not in sources:
            sources.append("TE")

Tests (unit):
- Test E4 builder US with FRED cb_confidence returning None + TE
  succeeding → assert TE_FALLBACK_CB_CC flag present + cb_vals populated
- Same for umich_5y
- Test E4 builder US with both FRED + TE failing → assert None + no
  flag (graceful degradation; component counted as missing)

Coverage builders.py additions ≥ 90%.
```

### Commit 5 — Yahoo Finance put/call wrapper (CAL-073 resolve)

```
feat(connectors): Yahoo Finance ^CPC put/call ratio (CAL-073 resolve)

PUTCLSPX FRED series delisted (flagged Week 5 Sprint 1).
Alternative: Yahoo Finance `^CPC` symbol (CBOE Equity Put/Call Ratio).

Decision path: extend existing src/sonar/connectors/move_index.py OR
create src/sonar/connectors/yahoo_finance.py generic.

Prefer: create `yahoo_finance.py` generic (future-proof for more Yahoo
symbols). Move MOVE fetch into generic pattern + add CPC.

Implementation:
async def fetch_yahoo_chart(
    self, symbol: str, start: date, end: date
) -> list[YahooObservation]:
    """Generic Yahoo Finance chart API fetch.
    Endpoint: https://query1.finance.yahoo.com/v7/finance/chart/{symbol}
    ?interval=1d&range=5y&period1=...&period2=..."""
    ...

async def fetch_put_call_ratio_us(
    self, start: date, end: date
) -> list[YahooObservation]:
    """CBOE Equity Put/Call Ratio via Yahoo ^CPC symbol.
    Daily close. Source: CBOE."""
    return await self.fetch_yahoo_chart("^CPC", start, end)

# Optional migration path: have move_index.py import and wrap
# yahoo_finance.py (future refactor; not required this sprint)

Tests:
- Cassette-replay unit tests
- @pytest.mark.slow live canary: fetch last 30 days ^CPC, assert
  non-empty + values in [0.3, 3.0] (historical P/C range)
- Coverage yahoo_finance.py ≥ 92%

If existing move_index.py logic is refactored, all its tests continue
to pass (backward-compat preserved).

Close CAL-073 in docs/backlog/calibration-tasks.md.
```

### Commit 6 — F4 Positioning wiring (put/call via Yahoo)

```
feat(indices): F4 Positioning put/call live via Yahoo (CAL-073 closure completion)

Check F4 Positioning current put/call source:
- grep "put_call_ratio\|^CPC\|PUTCLSPX" src/sonar/indices/financial/

If builders.py handles F4 inputs:
- Add put/call fetch via new yahoo_finance connector
- Flag YAHOO_PUT_CALL_USED (informational; not error)

If f4_positioning.py handles inputs directly:
- Update input accessor to consume new connector

Verify F4 components_available count: pre-sprint US 4/5, target 5/5
(AAII + COT + margin + IPO + P/C all live).

Integration smoke:
- tests/integration/test_f4_put_call_live.py
- @pytest.mark.slow
- Build F4Inputs for US with all 5 components live (AAII via TE/FRED,
  COT via CFTC, margin via FRED, IPO via existing, P/C via Yahoo)
- Assert components_available == 5
- Assert no OVERLAY_MISS flag

Coverage F4 components ≥ 90% maintained.
```

### Commit 7 — Integration test: E4 + F4 quality uplift smoke

```
test(integration): E4 + F4 quality uplift post-Quick-Wins

tests/integration/test_sentiment_positioning_uplift.py:

@pytest.mark.slow
def test_e4_us_post_quick_wins():
    """E4 US with TE fallbacks active.
    Baseline pre-sprint: 9/13 components (CB + UMich 5Y missing).
    Post-sprint target: 11/13 components."""
    # Build E4Inputs US 2026-04-20
    # Assert components_available >= 11
    # Assert flags contain TE_FALLBACK_CB_CC, TE_FALLBACK_UMICH_5Y

@pytest.mark.slow
def test_f4_us_post_quick_wins():
    """F4 US with P/C via Yahoo.
    Baseline pre-sprint: 4/5 components (P/C OVERLAY_MISS).
    Post-sprint target: 5/5 components."""
    # Build F4Inputs US 2026-04-20
    # Assert components_available == 5
    # Assert no OVERLAY_MISS flag

Wall-clock ≤ 30s combined. Real TE + Yahoo calls.
```

### Commit 8 — Retrospective + CAL closures final

```
docs(planning): Week 6 Sprint 3 Quick Wins retrospective

File: docs/planning/retrospectives/week6-sprint-3-quick-wins-report.md

Structure per prior retrospectives:
- Summary (duration, commits, CAL closures)
- Commits table with SHAs + gate status
- CAL resolutions:
  - CAL-072 CLOSED (BIS WS_SPP rename)
  - CAL-073 CLOSED (PUTCLSPX via Yahoo ^CPC)
  - CAL-093 RE-OPENED + CLOSED (CB CC via TE; previous premise wrong)
  - New CAL (102 or 103) opened + closed (MICHM5YM5 via TE)
- Diagnostic finding: Sprint 1 Week 6 CC closed CAL-093 based on
  incorrect premise. Empirical probe revealed TE has CB CC via
  indicator 'consumer confidence' (CONCCONF source). Operational
  lesson: always verify HistoricalDataSymbol metadata before
  concluding a source identity.
- Quality delta validation:
  - E4 US: baseline 9/13 → actual post-sprint count (target 11/13)
  - F4 US: baseline 4/5 → actual post-sprint count (target 5/5)
  - FCS Bubble Warning: condition-3 now armable (BIS property live)
- Concurrency report: Sprint 2b Ingestion Omnibus status at arrival;
  Sprint 2b status at Sprint 3 completion; any race conditions
- HALT triggers fired / not fired
- Deviations from brief
- New backlog (if any)

Close CAL-072, CAL-073, CAL-093 in docs/backlog/calibration-tasks.md;
open + close new CAL for MICHM5YM5 resolution.
```

---

## 5. HALT triggers (atomic)

1. **BIS WS_SPP still 404** — rename diagnosis was wrong; different solution needed (document + defer)
2. **TE `consumer confidence` returns non-CONCCONF symbol** — empirical probe was wrong; HALT, re-investigate
3. **TE `michigan 5 year inflation expectations` returns unexpected data** — flag + use alternative indicator `michigan inflation expectations`
4. **Yahoo `^CPC` symbol unavailable or format changed** — fallback to `CPC` sem caret, or Stooq.com
5. **Existing move_index.py refactor breaks tests** — revert refactor, add yahoo_finance.py separately (don't touch move_index)
6. **F4 Positioning puts/call wiring not in builders.py** (may be in f4_positioning.py directly or different path) — verify location first; adapt wiring scope
7. **CAL-093 previously written closure needs manual edit** — backlog file edit without CC hesitation; document in retro as correction
8. **Concurrent Ingestion Omnibus modifies calibration-tasks.md** — rebase + merge both sets of CAL changes manually
9. **Pre-push gate fails** → fix before push, no `--no-verify`. Full project mypy.
10. **TE rate limit hit** — polite pacing already; if > 10 calls this sprint, document + defer remaining canaries

"User authorized in principle" does NOT cover specific triggers.

---

## 6. Acceptance

### Per commit
Commit body checklist.

### Global sprint-end
- [ ] 7-9 commits pushed, main HEAD matches remote, CI green
- [ ] `src/sonar/connectors/bis.py` WS_SPP rename complete + cassette re-recorded + xfail removed
- [ ] `src/sonar/connectors/te.py` 2 new wrappers (CB CC + UMich 5Y) + cassettes + canaries PASS
- [ ] `src/sonar/connectors/yahoo_finance.py` (or move_index extension) put/call helper + cassette + canary PASS
- [ ] `src/sonar/indices/economic/builders.py` E4 TE fallback for CB CC + UMich 5Y integrated
- [ ] F4 Positioning wired to consume put/call via Yahoo
- [ ] E4 US post-sprint components_available ≥ 11/13 (baseline 9/13, +2)
- [ ] F4 US post-sprint components_available == 5/5 (baseline 4/5, +1)
- [ ] CAL-072, CAL-073 CLOSED; CAL-093 re-opened + resolved; new CAL opened + resolved for UMich 5Y
- [ ] TE calls this sprint ≤ 15 (within budget)
- [ ] No `--no-verify` pushes
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact export (mandatory)

File: `docs/planning/retrospectives/week6-sprint-3-quick-wins-report.md`

**Per-commit tmux echoes**:
```
COMMIT N/7-9 DONE: <scope>, SHA, coverage delta, live-canary status, HALT status
```

**Final tmux echo**:
```
SPRINT 3 QUICK WINS DONE: N commits, 4 CAL resolved (072+073+093+new)
E4 US: 9/13 → X/13 | F4 US: 4/5 → 5/5
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/week6-sprint-3-quick-wins-report.md
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

Full project mypy — NOT scoped to committed files. No `--no-verify`.

Live canaries do NOT run in default pytest (marked `@pytest.mark.slow`).

---

## 9. Notes on implementation

### Sprint 1 Week 6 CAL-093 was closed on incorrect premise
Empirical probe (2026-04-20) revealed TE `consumer confidence` indicator returns Conference Board data (HistoricalDataSymbol = `CONCCONF`), not UMich. Previous CC inferred without checking metadata. Lesson: always probe HistoricalDataSymbol on TE indicators to verify source identity.

### BIS dataflow rename is tightly scoped
WS_LONG_PP → WS_SPP is a simple find/replace in `bis.py`. Verify dataflow key structure identical (likely same SDMX shape). Cassette re-record + xfail removal.

### Yahoo Finance pattern reuse
MOVE via Yahoo `^MOVE` was shipped Week 5 Sprint 1 as `connectors/move_index.py`. Same pattern applies to `^CPC`. Decision: generic `yahoo_finance.py` OR mirror pattern in a separate file. Generic preferred (future-proof) but only refactor if tests remain green; else separate file.

### TE calls budget
Sprint 1 Week 6 used ~18 TE calls. This sprint adds ~6-10 (2 new wrappers × 3 calls each for tests + live canary). Running total ~30 calls lifetime TE Pro (10k/month budget) — trivial usage.

### F4 Positioning wiring location
May be in `src/sonar/indices/financial/f4_positioning.py` directly OR in a `builders.py` file for financial indices. CC verifies location Commit 6 before wiring. Do not assume.

### Ingestion Omnibus still running
At sprint start time, Ingestion Omnibus in tmux `sonar-l3` is likely mid-sprint (C3-C5 of 7). Zero file conflict expected per §3. calibration-tasks.md may have concurrent modifications — rebase + merge manually.

---

*End of Week 6 Sprint 3 Quick Wins brief. 7-9 commits. 4 CAL items resolved. E4 + F4 quality uplift material.*
