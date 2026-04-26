# Sprint 8 — Test pollution root-cause diagnosis (continuation Sprint A test infrastructure)

**Tier scope**: Infrastructure sprint — no T1 cohort scope; cross-cutting cleanup.
**Pattern reference**: Sprint A precedente (test-hygiene + SESSION_STATE.md hybrid governance, 2026-04-26 manhã).
**Predecessor outcome**: Sprint A fixed Issue 1 (genuine schema mismatch); Issue 2 NOT-REPRODUCIBLE post Issue 1 fix (knock-on symptom). Sprint 8 attacks meta-pattern visible across other tests in full-suite runs.

---

## 1. Scope

**In**:
- Reproduce + diagnose root cause of full-suite test pollution flakes documented Sprint A retro §2.2:
  - `test_economic_ecs::test_fixture_us_2020_03_23_recession` (full-suite intermittent; isolated PASS confirmed 5x 2026-04-26)
  - `test_te_indicator::test_wrapper_equity_index_from_cassette[EA]` (full-suite intermittent runs 2/4/5 Sprint A)
  - `test_te_indicator::test_cpi_yoy_c2_from_cassette[SE]` (full-suite intermittent run 3 Sprint A)
- Hypothesis: shared fixture state / connection pool / async teardown / cassette VCR state pollution between tests
- Identify single root cause OR confirm multiple independent causes
- Ship fix(es) OR document hypothesis with empirical evidence + escalation
- File retroactive CALs for any documented-WONT-FIX residuals

**Out**:
- New T1 country expansion
- Feature work (overlays, indices, cycles)
- Refactor sibling tests beyond minimum needed for fix
- TE cassette refresh (cassettes are old — separate concern, CAL candidate if surfaces during diagnosis)

---

## 2. Spec reference + pre-flight

**Authoritative**:
- `docs/planning/retrospectives/week11-sprint-a-test-hygiene-and-session-state-report.md` §2.2 (Issue 2 NOT-REPRODUCIBLE rationale + flake table from 5x runs)
- `tests/unit/test_cycles/test_economic_ecs.py` (38 tests; isolated PASS confirmed 5x 2026-04-26 by Hugo)
- `tests/unit/test_connectors/test_te_indicator.py` (cassette-based TE tests; EA + SE intermittent reports)
- `conftest.py` files at root + tests/ dir + subdirs (fixture lifecycle definitions)
- `tests/conftest.py` if exists (shared fixtures)
- pytest configuration: `pyproject.toml` [tool.pytest.ini_options] OR pytest.ini

**Pre-flight HALT #0 requirement** (mandatory Commit 1):

CC reads end-to-end + executes empirical baseline:

1. Read Sprint A retro §2.2 (flake history table)
2. Read all conftest.py files — identify shared fixtures + scope (function/class/module/session)
3. Read pytest configuration — identify ordering (`-p random`, `--randomly-seed`, etc.)
4. **Empirical baseline 5x runs full-suite** (`pytest -m "not slow"` 5x consecutive) — record any flakes that surface + which tests + which runs
5. **Empirical baseline 3x runs targeted subset** — `pytest tests/unit/test_cycles/ tests/unit/test_connectors/test_te_indicator.py` 3x to constrain scope
6. Categorise flakes observed: shared DB session pollution / async cleanup / cassette VCR state / module-level mutable / other

**Resource budget**: Budget hard-cap **4-6h CC wall-clock**. If root cause unidentifiable within budget → HALT-3 escalation per §5 trigger.

---

## 3. Concurrency

**Single CC sequential** — no worktree split. Diagnosis sprint requires single coherent investigation thread.

**File-level isolation**: not applicable.

**Migration numbers**: NONE.

---

## 4. Commits

Target ~4-6 commits (variable by outcome):

1. **Pre-flight audit + empirical baseline** — conftest reads + pytest config + 5x full-suite + 3x targeted runs; commit body documents flake matrix verbatim
2. **Hypothesis ranking** — categorise observed flakes; rank hypotheses by likelihood + fix tractability (commit body lists top 3 hypotheses with empirical evidence)
3. **Top hypothesis instrumentation** — add diagnostic logging / fixture state assertions / connection pool monitoring to confirm or falsify top hypothesis (if fix is small, may merge with Commit 4)
4. **Fix(es)** — ship fix(es) targeting confirmed root cause; verify 5x consecutive full-suite PASS clean
5. **CAL closure / filing** — close `CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL` Issue residuals OR file new CAL `CAL-TEST-POLLUTION-DIAGNOSED-PHASE25` if outcome C
6. **Retrospective** — `docs/planning/retrospectives/week11-sprint-8-test-pollution-rootcause-report.md`

Outcome-conditional commit shape:
- **A (root cause + single fix)**: 5-6 commits as above
- **B (partial fix)**: 5-6 commits + KNOWN-BACKGROUND documentation
- **C (unidentifiable in budget)**: 4 commits (pre-flight + baseline + hypothesis doc + retro/escalation)

Commit body checklist enforceable per fix commit:
- 5x consecutive full-suite PASS verified
- Specific flake fix (which test was rotating; now consistently passes)
- Hypothesis confirmed evidence

---

## 5. HALT triggers (atomic)

0. **Pre-flight HALT #0 fail** — conftest fixture lifecycle unrecognisable / pytest config conflicts → HALT, document
1. **Empirical baseline shows ZERO flakes in 5x full-suite + 3x targeted** → outcome **DONE-NULL**: residuals self-resolved post Sprint A fix; CAL filings retroactive close + retro documents non-reproducibility
2. **Top-hypothesis fix introduces regression** (any test that was previously passing now fails) → HALT, revert + revisit
3. **Coverage regression > 3pp** → HALT
4. **Pre-push gate fail** → fix, no `--no-verify`
5. **Budget hard-cap 6h exceeded** → outcome **C escalation**: document hypothesis + file CAL `CAL-TEST-POLLUTION-DIAGNOSED-PHASE25` + ship retro; defer further work Phase 2.5

---

## 6. Acceptance

**Outcome A (root cause + fix)**:
- [ ] Root cause identified with empirical evidence (commit 2 hypothesis ranking + commit 3 instrumentation)
- [ ] Fix shipped targeting root cause
- [ ] 5x consecutive full-suite PASS clean — zero flakes
- [ ] CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL Issue residuals documented closed
- [ ] No new test regressions
- [ ] Coverage stable

**Outcome B (partial fix)**:
- [ ] Root cause partially identified
- [ ] Partial fix ships (eliminates ≥50% of flake instances)
- [ ] Remaining flakes documented as KNOWN-BACKGROUND with empirical pattern
- [ ] CAL filings updated accordingly

**Outcome C (unidentifiable in budget)**:
- [ ] Hypothesis documentation complete (top 3 ranked + falsification evidence)
- [ ] CAL `CAL-TEST-POLLUTION-DIAGNOSED-PHASE25` filed with hypothesis + recommended next steps
- [ ] Sprint 8 retro escalates to ADR or dedicated Phase 2.5 sprint candidate

**Outcome DONE-NULL (HALT-1 fired)**:
- [ ] Empirical baseline confirms residuals non-reproducible
- [ ] Sprint A test-hygiene fix retroactively closed all known issues
- [ ] CAL filings retroactive close
- [ ] Retro documents non-reproducibility + Sprint A success expanded

**Sprint-end (all outcomes)**:
- [ ] No `--no-verify`
- [ ] Pre-commit 2x every commit
- [ ] Pre-push gate green every push
- [ ] Sprint 8 retrospective shipped
- [ ] SESSION_STATE.md updated per WORKFLOW.md mandate (hybrid governance discipline first sprint enforcement)

---

## 7. Report-back artifact

Path: `docs/planning/retrospectives/week11-sprint-8-test-pollution-rootcause-report.md`

Structure:
- Sprint metadata (CC duration, commits, outcome A/B/C/DONE-NULL)
- Empirical baseline 5x full-suite + 3x targeted matrix verbatim
- Hypothesis ranking + falsification evidence
- Fix description (if any) + verification 5x consecutive PASS
- CAL closures + filings
- Pattern observations vs Sprint A (which heuristics worked, which didn't)
- Recommendations for future test-hygiene if applicable

---

## 8. Notes on implementation

### Hypothesis priors (CC may revise based on empirical findings)

Top candidates for root cause based on Sprint A retro evidence + flakes pattern:

1. **Cassette VCR state mutation** — `vcrpy` cassettes shared across test files; one test consumes cassette state, next test sees mutated cursor. Most likely given that 4/5 Sprint A flake instances are `test_te_indicator::*cassette` tests.
2. **Async cleanup pollution** — connector teardown leaks event loop state (precedent: ADR-0011 Principle 6 single async lifecycle); inconsistent across tests.
3. **DB session shared state** — `db_session` fixture function-scoped already (Sprint A retro confirms); but module-level shared `engine` may leak transactions.

### Empirical discipline

- CC runs 5x consecutive full-suite **before** any fix — establishes baseline
- CC runs 5x consecutive full-suite **after** each fix — verifies improvement
- "5x consecutive PASS" is hard threshold for any "fixed" claim (matches Sprint A Issue 2 anti-flake validation discipline)

### Out-of-scope contingencies

- TE cassette refresh: if cassettes appear stale (data-dated), file `CAL-TEST-CASSETTES-REFRESH` separate; do NOT refresh in this sprint (would introduce TE quota burn + scope creep)
- pytest-randomly / pytest-ordering plugins: do NOT add new plugins this sprint; if needed, document recommendation for future sprint

### SESSION_STATE.md update mandate

Per WORKFLOW.md (post Sprint A): CC updates `docs/SESSION_STATE.md` as part of retrospective commit (or dedicated commit). Specifically update:
- "Test infrastructure" section
- "Active high-priority CALs" section (close + new filings)
- "Last sprint shipped" section
- Timestamp footer

### Sustainable pacing

Target sprint complete same-day, ~3-5h wall-clock single CC. Budget hard-cap 6h per HALT-5 trigger.
