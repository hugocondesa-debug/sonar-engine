# Sprint A — Test-hygiene + SESSION_STATE.md hybrid governance (CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL + new SESSION_STATE infra)

**Tier scope**: Infrastructure sprint — no T1 cohort scope; cross-cutting cleanup + governance.
**Pattern reference**: Sprint A precedente Week 7-10 (governance/infra sprints recurrent pattern).

---

## 1. Scope

**In**:
- **Track 1 (test-hygiene)**: Fix CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL
  - Issue 1 (genuine failure): `tests/integration/test_cycles_composites.py::TestOrchestratorSmoke::test_us_smoke_end_to_end` — `_seed_all` schema name mismatch (canonical: monetary_m1_effective_rates / monetary_m2_taylor_gaps / monetary_m4_fci)
  - Issue 2 (flake): `tests/unit/test_cycles/test_financial_fcs.py::TestComputeFcsHappy::test_us_full_stack` — order-dependent state pollution / shared fixture interaction
  - Add per-test session isolation where needed (function-scoped fixtures)
  - Verify composite readers (compute_all_cycles, compute_fcs) match seed naming
- **Track 2 (hybrid governance)**: Ship SESSION_STATE.md + WORKFLOW mandate
  - Create `docs/SESSION_STATE.md` (terse, machine-readable factual state)
  - Update `docs/governance/WORKFLOW.md` with mandate: CC updates SESSION_STATE.md as final commit of every sprint (or in retrospective commit)
  - Document field schema in WORKFLOW.md
- Pre-push gate green clean post-sprint (zero pre-existing failures inherited)
- CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL closed

**Out**:
- T1 country expansion (no overlay/index work)
- Sprint 7A NSS criterion formalisation (defer per Sprint 7B 7-tenor outcome)
- ADR-0009 v2.3.4 formalisation (separate sprint when next multi-dimension SDMX surfaces)
- Move SESSION_CONTEXT to GitHub (status quo Project knowledge maintained per Hugo decision 2026-04-26)

---

## 2. Spec reference + pre-flight

**Authoritative**:
- `tests/integration/test_cycles_composites.py` (`_seed_all` function audit target)
- `tests/unit/test_cycles/test_financial_fcs.py` (`_seed_f_rows` function audit target)
- `src/sonar/cycles/` (composite readers — compute_all_cycles, compute_fcs canonical naming)
- Schema canonical names (verify via `sqlite3 data/sonar-dev.db ".tables"`):
  - `monetary_m1_effective_rates`, `monetary_m2_taylor_gaps`, `monetary_m4_fci`
  - `monetary_cycle_scores`, `economic_cycle_scores`, `credit_cycle_scores`, `financial_cycle_scores`
  - `f1_valuations`, `f2_momentum`, `f3_risk_appetite`, `f4_positioning`
  - `idx_economic_e1_activity`, `idx_economic_e3_labor`, `idx_economic_e4_sentiment`
- `docs/governance/WORKFLOW.md` (existing paralelo orchestration canonical)
- `docs/backlog/calibration-tasks.md` `CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL` (this sprint closes it)

**Pre-flight HALT #0 requirement** (mandatory Commit 1):

CC reads end-to-end:
1. `_seed_all` source + comparison vs canonical schema names list above
2. `_seed_f_rows` source + sibling test interactions analysis
3. `compute_all_cycles` + `compute_fcs` table reads — confirm naming alignment
4. WORKFLOW.md current state + identify mandate insertion point

**No TE quota usage** (Track 2 governance work; Track 1 test work uses local DB fixtures only).

---

## 3. Concurrency

**Single CC sequential** — no worktree split. Infrastructure sprint, mixed-track, single discipline thread.

**File-level isolation**: not applicable (single CC).

**Migration numbers**: NONE (data + code only, no schema change).

---

## 4. Commits

Target ~5-7 commits:

**Track 1 (test-hygiene)**:
1. **Pre-flight audit** — schema names verification + seed function source comparison + plan
2. **Fix `_seed_all` Issue 1** — populate canonical monetary subindex schema names + verify test_us_smoke_end_to_end PASS isolated and in full-suite
3. **Fix `_seed_f_rows` Issue 2** — function-scoped fixture isolation + verify test_us_full_stack PASS consistently in full-suite (run pytest 5x to confirm not flaky)
4. **CAL closure** — `docs/backlog/calibration-tasks.md` close CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL with fix details + test runs evidence

**Track 2 (hybrid governance)**:
5. **SESSION_STATE.md ship** — `docs/SESSION_STATE.md` initial content (factual state Phase 2 T1 post-Sprint 7B; terse format; machine-readable)
6. **WORKFLOW mandate** — `docs/governance/WORKFLOW.md` amendment + field schema documentation + mandate language
7. **Sprint A retrospective** — `docs/planning/retrospectives/week11-sprint-a-test-hygiene-and-session-state-report.md`

Commit body checklist enforceable per Track 1 commit:
- Test ran isolated PASS
- Test ran full-suite PASS
- Test ran 5x consecutive PASS (Issue 2 specifically — anti-flake validation)
- Schema names verified canonical

---

## 5. HALT triggers (atomic)

0. **Pre-flight HALT #0 fail** — schema names diverge from documented canonical OR seed functions unrecognisable structure → HALT, document
1. **Issue 1 fix doesn't make test_us_smoke_end_to_end PASS** → HALT, deeper diagnosis (cycles MSC composite logic may have additional gaps)
2. **Issue 2 fix doesn't stabilise test_us_full_stack across 5x runs** → HALT, escalate (deeper test infrastructure issue)
3. **New tests regress** (unit pass count drops vs baseline 2320) → HALT, no `--no-verify`
4. **Coverage regression > 3pp** → HALT
5. **Pre-push gate fail** → fix, no `--no-verify`
6. **WORKFLOW.md mandate conflicts with existing paralelo orchestration** → HALT, surface conflict for Hugo

---

## 6. Acceptance

**Track 1 (test-hygiene)**:
- [ ] `test_us_smoke_end_to_end` PASS isolated AND in full-suite consistently
- [ ] `test_us_full_stack` PASS isolated AND in full-suite consistently (5x consecutive runs verified)
- [ ] Pre-push gate clean: zero failures, zero flaky tests in pytest -m "not slow"
- [ ] CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL closed with fix evidence
- [ ] No new test regressions

**Track 2 (hybrid governance)**:
- [ ] `docs/SESSION_STATE.md` shipped with initial content (see §8 schema below)
- [ ] `docs/governance/WORKFLOW.md` amended with SESSION_STATE update mandate
- [ ] WORKFLOW.md documents SESSION_STATE.md field schema explicitly

**Sprint-end**:
- [ ] No `--no-verify`
- [ ] Pre-commit 2x every commit
- [ ] Pre-push gate green every push
- [ ] Sprint A retrospective shipped

---

## 7. Report-back artifact

Path: `docs/planning/retrospectives/week11-sprint-a-test-hygiene-and-session-state-report.md`

Structure:
- Sprint metadata (CC duration, commits, tracks)
- Track 1: schema names diff + fix description + test runs evidence (5x consecutive for Issue 2)
- Track 2: SESSION_STATE.md schema + WORKFLOW.md mandate text + governance rationale
- Pre-existing failures status (zero)
- Lessons learned: what test infrastructure rot looked like + prevention discipline going forward

---

## 8. Notes on implementation

### SESSION_STATE.md schema (terse, machine-readable, factual state only)

Initial content target:

```markdown
# SESSION_STATE — SONAR Engine

*Auto-updated post-sprint per WORKFLOW.md governance.*
*Companion to claude.ai Project knowledge SESSION_CONTEXT.md (narrative/decisions).*
*Last updated: <ISO timestamp> by Sprint <id>.*

## Phase
- **Current**: Phase 2 T1 horizontal expansion
- **Completion estimate**: ~62-65%
- **Target**: ~80-85% T1 fim Maio 2026

## Last sprint shipped
- **ID**: Sprint 7B
- **Branch**: sprint-7b-l2-curves-no-path2-norges-2y (merged)
- **SHA range**: 15c21fe..1bd9978
- **Outcome**: NO 12/16 NSS T1 via Norges Bank Path C single-source

## Coverage by overlay/layer (T1 = 16 países canonical)

| Layer | T1 % | Countries live | Gaps |
|---|---|---|---|
| L0 connectors | ~95% functional | 25+ | TE Path 1 + Path 2 emerging |
| L1 persistence | 100% | head 019 | — |
| L2 NSS curves | 75% | 12/16 | NL/NZ/CH/SE Path 2 deferred |
| L2 ERP | 100% methodology | 1 native + 15 proxy | acceptable |
| L2 CRP | 75% | 12/16 viável | follows NSS gap |
| L2 Rating-spread | 94% | 15/16 | DK Phase 5+ |
| L2 EXPINF | unaudited | 4/16 confirmed | CAL-EXPINF-T1-AUDIT |
| L3 M1 | 100% | 16/16 | — |
| L3 M2 | 69% | 11/16 FULL | EA per-country pending |
| L3 M3 | 25% | 4/16 | curves-derived expansion |
| L3 M4 | 47% FULL | 8/17 | SCAFFOLD upgrade pending |
| L3 Credit/Financial | shipped Week 4 | 4+4 | — |
| L3 E1/E3/E4 | 0% | 0/16 each | from-zero pending |
| L4 cycles | 6% cross-country | US only | 15 países pending each |

## Path 2 cohort (Phase 2.5+ deferred)
- NL — CAL-CURVES-NL-DNB-PROBE
- NZ — CAL-CURVES-NZ-PATH-2
- CH — CAL-CURVES-CH-PATH-2
- SE — CAL-CURVES-SE-PATH-2

## Active high-priority CALs
- CAL-EXPINF-T1-AUDIT (filed 2026-04-26)
- CAL-RATING-DK-PHASE5 (Phase 5+ candidate)
- CAL-RATING-COHORT-TARGET-CALIBRATION (low priority)

## Test infrastructure
- Pre-push gate: green (post Sprint A test-hygiene)
- Active flakes: zero (Sprint A closed CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL)

## TE quota
- Tier: 5000/mo
- Consumption Week 11 post-Sprint 7B: ~41-42%

## Pipelines production (systemd timers, 06:00-07:30 WEST)
- sonar-daily-curves.service (12 T1 countries)
- sonar-daily-monetary-indices.service (M1 16, M2 11, M4 8 FULL)
- sonar-daily-cost-of-capital.service (US canonical + Damodaran fallback)

## Active worktrees + tmux
- (auto-populated post-update; empty if no active sprint)

## Next sprint candidates
- CAL-EXPINF-T1-AUDIT (HIGH priority — closes biggest L2 gap)
- CAL-M3-T1-EXPANSION (curves-derived; 12 curves available)
- L4 cross-country composites (MSC + CCCS + ECS + FCS first cross-country)
```

### WORKFLOW.md mandate text (proposal — CC may refine)

Insert into WORKFLOW.md governance section:

```markdown
### SESSION_STATE.md update mandate (post-Sprint A 2026-04-26)

Every sprint MUST update `docs/SESSION_STATE.md` as part of retrospective commit (or dedicated commit if cleaner). Update covers:

- Phase status + completion estimate
- Last sprint shipped (ID, branch, SHA range, outcome 1-line)
- Coverage table updates (overlays + indices + cycles for any T1 country deltas)
- Active CALs surface changes (new filings + closures)
- Test infrastructure status
- TE quota delta
- Active worktrees + tmux (if any in-flight)
- Next sprint candidates (refresh based on backlog priority post-sprint)

Rationale: SESSION_STATE.md is the GitHub-side machine-readable state companion to claude.ai Project knowledge SESSION_CONTEXT.md (narrative/decisions). Eliminates baseline drift identified Week 11 Sprint 5A redundancy + Sprint 6 DK tier error + Sprint 7B 2Y binary inversion patterns.

CC updates SESSION_STATE.md autonomously per sprint retro; Hugo updates SESSION_CONTEXT.md in claude.ai Project knowledge upon copy/paste-ready text from chat.
```

### Implementation guidance

- Track 1 fixes: surgical edits to seed functions; do not refactor sibling tests unless minimum needed for fixture isolation
- Track 2: SESSION_STATE.md schema is descriptive — CC may adjust field structure if cleaner alternatives surface, but preserve "machine-readable" + "factual state only" + "no narrative" principles
- Sustainable pacing: target sprint complete same-day, ~3-4h wall-clock single CC (Track 1 ~2h + Track 2 ~1h + retro ~30min)
