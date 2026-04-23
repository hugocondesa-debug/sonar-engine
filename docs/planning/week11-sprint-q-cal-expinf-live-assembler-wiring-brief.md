# Sprint Q — CAL-EXPINF-LIVE-ASSEMBLER-WIRING (M3 FULL P0 Unlock)

**Branch**: `sprint-q-cal-expinf-live-assembler-wiring`
**Worktree**: `/home/macro/projects/sonar-wt-q-cal-expinf-live-assembler-wiring`
**Data**: Week 11 Day 1 (2026-04-24) — target arranque ~09:30-10:00 WEST
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy per SESSION_CONTEXT)
**Budget**: 4-6h solo
**Priority**: **P0** — critical path unlock Phase 2 fim Maio 2026 target
**ADR-0010 tier scope**: T1 ONLY
**ADR-0009 v2.2 TE Path 1 probe**: N/A (architectural wiring — no new country-data fetch)
**Brief format**: v3.3 (Tier A / Tier B split + filename convention Lesson #15 compliance)
**Systemd services affected**: `sonar-daily-monetary-indices.service` + `sonar-daily-overlays.service` (if exists separately) + downstream M3 builders for 9 T1 countries
**Parent**: Sprint O audit discovery (Week 10 Day 3) — classifier shipped with 9/16 T1 cohort, runtime 0/16 FULL blocked by EXPINF persistence gap

---

## §1 Scope (why)

### Problem statement

Sprint O (Week 10 Day 3) shipped M3 country-policy classifier + dispatcher extension covering 9 T1 countries (US/DE/EA/GB/JP/CA/IT/ES/FR). **Observability channel 9/16 emitting** `monetary_pipeline.m3_compute_mode`. **Runtime FULL coverage remains 0/16** — all 9 resolve to **DEGRADED** mode, not FULL.

### Root cause (Sprint O audit §2.1 findings)

`src/sonar/indices/overlays/live_assemblers.py` (or equivalent — verify exact location during C1 audit) passes `expected_inflation=None` hard-coded to M3 builders. Consequence:

1. M3 builder receives `forwards` (from `yield_curves_forwards`) ✓
2. M3 builder receives `expected_inflation=None` ✗
3. Builder classifier flags `M3_DEGRADED_EXPINF_MISSING`
4. Output mode = DEGRADED, not FULL

**EXPINF data is persisted** in `exp_inflation_canonical` + `exp_inflation_bei` + `exp_inflation_swap` + `exp_inflation_survey` tables (connectors for BEI, swaps, surveys already shipped Week 4-9). The gap is **wiring** — `live_assemblers` does not query these tables before invoking M3 builder.

### Objectivo Sprint Q

Close the wiring gap. Enable M3 builder to receive canonical `expected_inflation` input from persisted tables. Expected outcome: **9/16 T1 M3 promotes from DEGRADED to FULL** (US/DE/EA/GB/JP/CA/IT/ES/FR).

### Phase 2 impact

**Single-sprint unlock**: +20pp T1 coverage contribution via M3 FULL activation × 9 countries / 16 slots = +56pp of M3 layer = ~+12-15pp T1 overall (weighted across layers).

Post-Sprint Q: T1 overall ~57.5% → **~70-72%** projection. Phase 2 fim Maio 2026 target (75-80%) within single additional week's sprint scope.

---

## §2 Spec (what)

### 2.1 Pre-flight audit (MANDATORY BEFORE C2 code)

CC must complete the following audits and document findings in `docs/backlog/audits/sprint-q-expinf-wiring-audit.md` (new):

#### 2.1.1 Locate live_assemblers + verify EXPINF gap

```bash
cd /home/macro/projects/sonar-engine
find src/sonar/ -type f -name "*.py" | xargs grep -l "live_assembler\|live_assemble\|expected_inflation.*=.*None" 2>/dev/null | head -10
```

Inspect each match. Confirm the `expected_inflation=None` hard-code claim from Sprint O audit. Document exact file + function + line numbers.

#### 2.1.2 EXPINF tables inventory

```bash
sqlite3 data/sonar-dev.db << 'EOF'
.schema exp_inflation_canonical
.schema exp_inflation_bei
.schema exp_inflation_swap
.schema exp_inflation_survey
.schema exp_inflation_derived
EOF
```

Document canonical date column name, unique constraint, country coverage per table.

#### 2.1.3 Per-country EXPINF coverage (re-execute Sprint O §2.1 audit)

```bash
for tbl in exp_inflation_canonical exp_inflation_bei exp_inflation_swap exp_inflation_survey exp_inflation_derived; do
  echo "=== $tbl ==="
  sqlite3 data/sonar-dev.db "SELECT country_code, MAX(date) AS latest, COUNT(*) AS n FROM $tbl GROUP BY country_code ORDER BY country_code;"
done
```

Cross-reference with 9 T1 cohort (US/DE/EA/GB/JP/CA/IT/ES/FR). **Expected findings**:

- **Tier 1 (FULL-capable)**: US, EA, GB — likely have BEI + swap + survey
- **Tier 2 (possibly FULL)**: DE, JP — BEI may be available; verify
- **Tier 3 (possibly DEGRADED-FULL-mode)**: CA, FR — likely BEI + swap, no survey
- **Tier 4 (persistent DEGRADED)**: IT, ES — BTP€i/Bonos€i thin, survey sparse, may stay DEGRADED

Document per-country tier assignment with justification.

#### 2.1.4 Canonical-inflation consumer location

Where does M3 builder expect `expected_inflation` parameter? Verify signature:

```bash
grep -rn "def.*build_m3\|def.*M3.*build\|expected_inflation" src/sonar/indices/monetary/ | head -20
```

Document expected parameter shape (single float? dict by tenor? structured object?).

### 2.2 Wiring implementation

Based on §2.1 findings, refactor `live_assemblers.py` (or equivalent) to:

1. **Load expected_inflation per country before M3 builder invocation**:
   - Query `exp_inflation_canonical` primary source
   - Fallback hierarchy: canonical → derived → (BEI + swap synthesis) → survey
   - Return structured object with value + source flag

2. **Pass loaded value to M3 builder** (replace hard-coded None):
```python
# Before (line X in live_assemblers.py):
m3_output = build_m3(country, date, forwards=forwards, expected_inflation=None)

# After:
exp_inf = load_canonical_exp_inflation(country, date)  # new function
m3_output = build_m3(country, date, forwards=forwards, expected_inflation=exp_inf)
```

3. **Graceful fallback for per-country gaps**:
```python
if exp_inf is None:
    log.info("expinf.fallback.degraded_mode", country=country, date=date)
    # M3 builder still invoked; classifier returns DEGRADED for this country
```

### 2.3 Canonical-inflation loader function

New helper in `src/sonar/indices/monetary/exp_inflation_loader.py` (or extend existing module):

```python
def load_canonical_exp_inflation(
    country: str,
    date: date,
    session: Session,
) -> Optional[ExpInflationInput]:
    """
    Load canonical expected_inflation for (country, date) with fallback hierarchy.

    Sources (priority order):
    1. exp_inflation_canonical — synthesized canonical value
    2. exp_inflation_derived — derived from available sources
    3. exp_inflation_bei — break-even inflation (TIPS-style)
    4. exp_inflation_swap — inflation swap market
    5. exp_inflation_survey — SPF / UMich / equivalent

    Returns None if no source has data for (country, date).
    """
```

Returns `ExpInflationInput` dataclass (new):
```python
@dataclass
class ExpInflationInput:
    value: float  # annual %, decimal form (e.g., 0.023 for 2.3%)
    source: str   # 'canonical' | 'derived' | 'bei' | 'swap' | 'survey'
    tenor: str    # '5Y' | '10Y' | '5Y5Y' etc. — tenor of expectation
    flags: List[str]  # e.g., ['STALE_1D', 'INTERPOLATED']
```

### 2.4 M3 classifier update (if needed)

`src/sonar/indices/monetary/m3_country_policies.py` (shipped Sprint O) — may need:

- Update `_classify_m3_compute_mode` to correctly handle the new non-None input path
- DEGRADED → FULL promotion logic: if `expected_inflation is not None AND source in canonical_tier_1`, mode=FULL
- Otherwise DEGRADED persists (e.g., IT/ES where BEI sparse)

### 2.5 Regression tests

New tests in `tests/unit/test_pipelines/test_expinf_wiring.py`:

- `test_load_canonical_expinf_us_full_path` — US with BEI + swap + survey all present → canonical source
- `test_load_canonical_expinf_degraded_fallback` — mock country with only survey → fallback to survey, flag DEGRADED-like
- `test_load_canonical_expinf_none_absent` — mock country with zero sources → None returned
- `test_m3_classifier_full_promotion_with_expinf` — integration: M3 builder called with expinf, classifier returns FULL
- `test_m3_classifier_degraded_persists_without_expinf` — integration: expinf None, classifier returns DEGRADED (backward compat)
- Parametric over 9 T1 countries: assert M3 dispatcher classification matches expected tier from §2.1.3 audit

### 2.6 Backfill Apr 21-24

Post-code ship, backfill M3 FULL for 9 T1 countries × 4 days:

```bash
for date in 2026-04-21 2026-04-22 2026-04-23 2026-04-24; do
  uv run python -m sonar.pipelines.daily_monetary_indices --indices m3 --all-t1 --date $date
done
```

Verify cohort classifications shifted DEGRADED → FULL for countries in §2.1.3 Tier 1-3:

```bash
sudo journalctl -u sonar-daily-monetary-indices.service --since "-10 min" --no-pager | \
  grep "m3_compute_mode" | awk '{print $NF}' | sort | uniq -c
# Expected: FULL count >> DEGRADED count (unlike pre-Sprint-Q where 100% DEGRADED)
```

### 2.7 ADR-0011 Principle 8 amendment (if pattern generalizable)

If EXPINF wiring pattern suggests canonical pattern for future layer integrations (E1/E3/E4 will have similar "connector-shipped but not wired" risk), document:

```markdown
### Principle 8 — Observability-before-wiring anti-pattern

Layers with classifier-emitting dispatchers MUST verify wiring (data flow from
persisted tables into builder) before declaring layer FULL-capable. Observability
emit (classifier fires per country) is necessary but not sufficient; runtime FULL
requires end-to-end path verified.

Check pattern (before declaring FULL coverage for any layer):
1. Dispatcher classifier emits per country → ✓ observability
2. Builder receives non-None structured input from upstream → ✓ wiring
3. Builder output persisted or consumed downstream → ✓ completion
```

Budget for Principle 8 ADR write: 20 min if pattern emerges. Skip if Sprint Q reveals it's EXPINF-specific wiring issue with no generalization.

---

## §3 Commits plan

| Commit | Scope | Ficheiros |
|---|---|---|
| **C1** | docs(backlog): Sprint Q pre-flight EXPINF wiring audit | `docs/backlog/audits/sprint-q-expinf-wiring-audit.md` (new) |
| **C2** | feat(indices): canonical EXPINF loader with fallback hierarchy | `src/sonar/indices/monetary/exp_inflation_loader.py` (new) |
| **C3** | refactor(pipelines): live_assemblers EXPINF wiring — replace hard-coded None | `src/sonar/indices/overlays/live_assemblers.py` (path TBD via C1 audit) |
| **C4** | refactor(indices): M3 classifier FULL-promotion logic | `src/sonar/indices/monetary/m3_country_policies.py` |
| **C5** | test: EXPINF loader + M3 FULL promotion regression (9-country parametric) | `tests/unit/test_pipelines/test_expinf_wiring.py` (new) |
| **C6** | ops: backfill Apr 21-24 + classifier verification | logs (no commit, ops-only) |
| **C7** | docs(adr,backlog): ADR-0011 Principle 8 (optional) + CAL-EXPINF-LIVE-ASSEMBLER-WIRING closure | `docs/adr/ADR-0011-*.md` (amendment if applicable), `docs/backlog/calibration-tasks.md` |
| **C8** | docs(planning): Sprint Q retrospective + M3 FULL coverage matrix (before/after) | `docs/planning/retrospectives/week11-sprint-q-cal-expinf-live-assembler-wiring-report.md` |

---

## §4 HALT triggers

**HALT-0 (structural data gap)**:
- **All 9 T1 countries have zero EXPINF coverage**: if §2.1.3 audit reveals none of exp_inflation_* tables have any country-date rows → HALT. Root cause = connector pipelines shipped but never backfilled. Triage separate sprint for EXPINF connector backfill before wiring.
- **EXPINF table schemas incompatible**: if per-country schemas vary (e.g., date column names differ across tables) → HALT. Schema standardization sprint needed before wiring.

**HALT-material (architecture issue)**:
- **live_assemblers.py does not exist or structure different from Sprint O audit claim**: investigate upstream data flow further. Sprint Q may need rescoping.
- **M3 builder signature doesn't accept `expected_inflation` parameter**: builder was shipped without wiring interface. Sprint Q needs additional C2.5 refactor of M3 builder signature.
- **EXPINF loader fallback hierarchy produces negative or nonsensical values** (e.g., exp_inflation=-5%): data quality issue upstream. Flag + HALT.

**HALT-scope**:
- Any tentação de novo EXPINF connectors (BEI/swap/survey) → STOP. Sprint Q is wiring-only.
- Any tentação de touch E1/E3/E4 economic indices → STOP. Sprint R scope.
- Any tentação de back-modify Sprint O classifier extensively → minor amendments OK (§2.4), full refactor STOP.

**HALT-security**: standard.

---

## §5 Acceptance

### Tier A — pre-merge (CC scope, v3.2 compliance)

1. **Audit doc shipped** (`docs/backlog/audits/sprint-q-expinf-wiring-audit.md`):
   ```bash
   test -f docs/backlog/audits/sprint-q-expinf-wiring-audit.md && \
     wc -l docs/backlog/audits/sprint-q-expinf-wiring-audit.md
   ```
   Expected: present, ≥60 lines with per-country tier matrix.

2. **EXPINF loader implementation**:
   ```bash
   test -f src/sonar/indices/monetary/exp_inflation_loader.py
   grep "def load_canonical_exp_inflation" src/sonar/indices/monetary/exp_inflation_loader.py
   ```
   Expected: function exists, dataclass defined.

3. **live_assemblers wiring replaced**:
   ```bash
   grep -c "expected_inflation=None" src/sonar/indices/overlays/live_assemblers.py
   ```
   Expected: 0 hard-coded None (replaced by loader call).

4. **Local CLI test — M3 FULL emit**:
   ```bash
   uv run python -m sonar.pipelines.daily_monetary_indices --indices m3 --all-t1 --date 2026-04-23 2>&1 | \
     grep "m3_compute_mode" | grep -c "FULL"
   ```
   Expected: ≥3 (at minimum Tier 1 countries US + EA + GB resolve FULL).

5. **Bash wrapper smoke** (Lesson #12 Tier A compliance):
   ```bash
   bash -lc 'uv run python -m sonar.pipelines.daily_monetary_indices --indices m3 --all-t1 --date 2026-04-23'
   ```
   Expected: exit 0, same FULL count as direct CLI.

6. **Regression tests**:
   ```bash
   uv run pytest tests/unit/test_pipelines/test_expinf_wiring.py -v
   ```
   Expected: all pass. Full suite: `uv run pytest tests/` — no regressions.

7. **Pre-commit clean double-run** (Lesson #2):
   Expected: clean second run.

### Tier B — post-merge (operator scope, applied post-merge Day 1 afternoon)

1. **Systemd verify M3 FULL observability**:
   ```bash
   sudo systemctl reset-failed sonar-daily-monetary-indices.service
   sudo systemctl start sonar-daily-monetary-indices.service
   sleep 180
   systemctl is-active sonar-daily-monetary-indices.service
   ```
   Expected: inactive (exit 0).

2. **M3 FULL classification count**:
   ```bash
   sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
     grep "m3_compute_mode" | grep -c "FULL"
   ```
   Expected: ≥3, realistically 5-7 depending on Tier 1-3 country EXPINF coverage.

3. **No event-loop regression** (ADR-0011 P6 holds):
   ```bash
   sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
     grep -iE "event loop is closed|connector_aclose_error" | wc -l
   ```
   Expected: 0.

4. **Summary clean**:
   ```bash
   sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
     grep "monetary_pipeline.summary"
   ```
   Expected: n_failed=0.

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week11-sprint-q-cal-expinf-live-assembler-wiring-report.md`:

### M3 coverage matrix (critical deliverable)

| Country | Pre-Q DEGRADED | Post-Q mode | EXPINF sources used | Flags |
|---|---|---|---|---|
| US | DEGRADED | FULL/DEGRADED | ... | ... |
| DE | ... | ... | ... | ... |
| EA | ... | ... | ... | ... |
| GB | ... | ... | ... | ... |
| JP | ... | ... | ... | ... |
| CA | ... | ... | ... | ... |
| IT | ... | ... | ... | ... |
| ES | ... | ... | ... | ... |
| FR | ... | ... | ... | ... |

### Phase 2 T1 coverage delta

- Pre-Q T1 overall: ~57.5%
- Post-Q T1 overall: projected ~67-72% (+10-15pp from M3 FULL × Tier 1-3 countries)
- Phase 2 target fim Maio: 75-80%
- Week 11 remaining velocity needed: ~5-10pp over 4 days = comfortable

### Sprint O retrospective follow-up

Sprint O discovered the wiring gap via audit-first discipline. Sprint Q closed it via targeted refactor. Validates:
1. Audit-first discipline surfaces structural issues that observability alone misses
2. Classifier shipping without wiring = "ghost FULL" — observability emits but runtime degraded
3. CAL-EXPINF-LIVE-ASSEMBLER-WIRING P0 correctly prioritized over sparse T1 Path 2 (higher leverage)

### ADR-0011 Principle 8 candidate (if applicable)

Document pattern: "observability emit ≠ runtime completion". Generalize to future layer integrations (E1/E3/E4 Week 11+ sprints). If Principle 8 written, cross-reference applies to all future layer-shipping sprints.

### Week 11 Day 1 sequencing reflection

Sprint Q was Day 1 morning first sprint. Was budget 4-6h accurate? How did Sprint Q unblock Sprint P (MSC EA composite)?

---

## §7 Execution notes

### Audit-first discipline (critical)

- C1 audit MUST be completed before C2 code. §2.1 findings drive C2 loader implementation.
- If audit reveals different structure than Sprint O claimed, pause + report before proceeding.

### Backward compatibility

- M3 classifier pre-Sprint-Q had DEGRADED as default for all 9 countries. Post-Sprint-Q, DEGRADED must remain valid for countries where EXPINF genuinely absent.
- No country should regress from classifier-capable to NOT_IMPLEMENTED.

### Performance

- EXPINF loader runs once per (country, date) pair = 9 queries per pipeline run. Cheap. Add query caching if exceeds 100ms total.
- Async-lifecycle compliance: loader is DB-read only, no new async surface. ADR-0011 P6 single-loop discipline unaffected.

### Testing

- Regression suite pre-existing tests (32 from Sprint O, 248 total) must pass. Full run:
  ```bash
  uv run pytest tests/ -x --tb=short
  ```

### Discipline
- **CC arranque template** (Lesson #5 fix) — apply to this session
- **DB symlink** auto-provisioned via sprint_setup.sh (Lesson #14 fix)
- **Pre-commit double-run** (Lesson #2)
- **sprint_merge.sh Step 10** cleanup (Lesson #4)
- **Brief format v3.3 filename** (Lesson #15 — this brief complies)
- **Empty commits blocked** (Lesson #11 — hook shipped Sprint V)
- **Systemd verify Tier B operator-driven** (Lesson #12) — CC reports Tier A criteria only

---

## §8 Dependencies & CAL interactions

### Parent sprint
Sprint O (Week 10 Day 3) — M3 classifier shipped + CAL-EXPINF-LIVE-ASSEMBLER-WIRING opened

### CAL items closed by this sprint
- **CAL-EXPINF-LIVE-ASSEMBLER-WIRING** (P0 Week 11) — primary deliverable

### CAL items potentially opened by this sprint
- **CAL-EXPINF-BEI-EA-PERIPHERY** — if §2.1.3 audit reveals IT/ES BEI coverage gaps (BTP€i/Bonos€i sparse) → open for Week 12+ linker connector probe
- **CAL-EXPINF-SURVEY-JP-CA** — if Tankan / BoC surveys gaps surface
- **CAL-M3-UPLIFT-DEGRADED-TO-FULL** — tracking countries that post-Q remain DEGRADED; periodic re-check as EXPINF connectors mature
- **Potential ADR-0011 Principle 8** (observability-before-wiring)

### Sprints blocked by this sprint
- **None blocking** — Sprint Q is P0 unblock, not blocked

### Sprints unblocked by this sprint
- **Sprint P (MSC EA composite)** — MSC requires M1+M2+M3+M4 all FULL for EA. Post-Sprint-Q, M3 EA FULL = MSC EA newly feasible (complementa M1 16/16 ✓, M2 EA FULL ✓, M4 EA FULL ✓ from Sprint J).
- **Sprint R (E1 activity indices)** — independent, but Sprint Q validates "audit-first + targeted wiring" pattern applicable to E1 connector-shipped-but-maybe-not-wired scenarios.
- **Future L4 cross-country MSC expansion** — depends on per-country M2 (Sprint M2-EA-per-country Week 11 Day 3) + M3 FULL uplift (Sprint Q shipping) + M4 scaffold upgrade (Sprint M4-upgrade Week 11 Day 5).

---

## §9 Time budget

Arranque target: Week 11 Day 1 Monday ~09:30-10:00 WEST (post Day 4 verification routine).

Hard stop: ~16:00 WEST Day 1 (6h wall-clock). If exceeded, ship partial (C1-C4 + backfill partial) + retro documenting residual gaps for Sprint Q.1 continuation.

Realistic range:
- **Best case** 4h: §2.1 audit reveals clean structure, C2-C4 trivial wiring, tests pass first try
- **Median case** 5-6h: audit surfaces 1-2 per-country quirks (e.g., survey table has different schema), iterative loader refinement
- **Worst case** 6h+ HALT: audit reveals EXPINF connectors never backfilled → HALT, rescope sprint to connector backfill + wiring split

---

*End of brief. P0 architectural wiring. Ship disciplined. Unlock M3 FULL coverage for Phase 2 trajectory.*
