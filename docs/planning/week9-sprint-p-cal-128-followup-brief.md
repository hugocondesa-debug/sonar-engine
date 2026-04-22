# Week 9 Sprint P — CAL-128-FOLLOWUP (Overlay / Cycle / Cost-of-Capital UK → GB Sweep)

**Target**: Complete ISO 3166-1 alpha-2 compliance started Sprint O by sweeping UK → GB in files carved out of Sprint O strict scope: `cycles/financial_fcs.py`, `overlays/crp.py`, `overlays/live_assemblers.py`, `pipelines/daily_cost_of_capital.py`.
**Priority**: MEDIUM (tech debt closure; CAL-128-FOLLOWUP tracking)
**Budget**: 1.5-2h CC autonomous
**Commits**: ~4-6
**Base**: branch `sprint-p-cal-128-followup` (isolated worktree `/home/macro/projects/sonar-wt-sprint-p`)
**Concurrency**: Parallel to Sprint S-CA Canada connector in worktree `sonar-wt-sprint-s`. See §3.

---

## 1. Scope

In:
- Sweep UK → GB canonical rename in 4 files Sprint O carved out:
  - `src/sonar/cycles/financial_fcs.py` — UK references in F4 positioning / composite country dispatch
  - `src/sonar/overlays/crp.py` — UK country-specific CRP computation
  - `src/sonar/overlays/live_assemblers.py` — live CRP/ERP overlay assemblers with UK branches
  - `src/sonar/pipelines/daily_cost_of_capital.py` — k_e pipeline UK country support
- Backward compat alias preservation strategy (per Sprint O Pattern):
  - Critical lookup points: preserve "UK" alias with structlog deprecation warning
  - Function names: rename primary `_uk_` → `_gb_`, add deprecated alias with warning
  - String literals: rename "UK" → "GB" in country_code tests/config
- Update associated tests in `tests/unit/test_cycles/`, `tests/unit/test_overlays/`, `tests/unit/test_pipelines/`
- Formalize CAL-128-FOLLOWUP closure in `docs/backlog/calibration-tasks.md`
- Verify no UK references remain in those 4 files (rg sweep post-rename)
- Retrospective

Out:
- `src/sonar/indices/monetary/builders.py` — **ALREADY CLOSED** via Week 8 Day 4 Sprint O + Week 9 chore commit (CAL-128 CLOSED)
- Historical retrospectives (preserved as archival record)
- Test fixture JSONs with UK literal data content (preserved — data authenticity)
- Non-identified UK references in other files (scope strictly limited to 4 files listed)
- Deprecation alias removal (Week 10 Day 1 per CAL-128 timeline)
- New CA country references (Sprint S domain; no overlap)

---

## 2. Spec reference

Authoritative:
- `docs/adr/ADR-0007-iso-country-codes.md` — ISO 3166-1 alpha-2 canonical (GB not UK)
- `docs/backlog/calibration-tasks.md` — CAL-128-FOLLOWUP entry with file list
- `docs/planning/retrospectives/week8-sprint-o-gb-uk-rename-report.md` — Sprint O precedent + deprecation pattern
- `docs/planning/retrospectives/week9-cal-128-chore-commit.md` (if exists; check) — builders.py closure precedent
- SESSION_CONTEXT.md §Country tiers — "iso_code: US/DE/PT/GB" convention
- `src/sonar/connectors/te.py` — Sprint O alias pattern template
- `src/sonar/indices/monetary/builders.py` — Week 9 chore alias pattern template

**Pre-flight requirement**: Commit 1 CC:
1. Inventory UK references in the 4 in-scope files:
   ```bash
   cd /home/macro/projects/sonar-wt-sprint-p
   rg -n '\bUK\b|"UK"|_uk_|_UK_' src/sonar/cycles/financial_fcs.py src/sonar/overlays/crp.py src/sonar/overlays/live_assemblers.py src/sonar/pipelines/daily_cost_of_capital.py
   ```
2. Document findings in commit body:
   - Line counts per file
   - Categorize: dict keys / constant names / function names / string literals / docstring prose
3. Read CAL-128-FOLLOWUP entry in backlog for scope guardrails
4. Read Sprint O precedent + Week 9 chore commit for alias pattern
5. Verify CA-related work from Sprint S parallel hasn't touched these files (separate worktrees ensure yes)

Existing assets:
- CAL-128 CLOSED for builders.py + config YAMLs + connectors
- Sprint O alias pattern established (deprecation warning via structlog)
- ADR-0007 authoritative
- Week 10 Day 1 alias removal planned — this sprint aligns

---

## 3. Concurrency — parallel protocol with Sprint S-CA + ISOLATED WORKTREES

**Sprint P operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-p`

Sprint S-CA operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-s`

**Critical workflow**:
1. Sprint P CC starts by `cd /home/macro/projects/sonar-wt-sprint-p`
2. All file operations happen in this worktree
3. Branch name: `sprint-p-cal-128-followup`
4. Pushes to `origin/sprint-p-cal-128-followup`
5. Final merge to main via fast-forward post-sprint-close

**File scope Sprint P (STRICT)**:
- `src/sonar/cycles/financial_fcs.py` MODIFY (UK → GB rename)
- `src/sonar/overlays/crp.py` MODIFY (UK → GB rename)
- `src/sonar/overlays/live_assemblers.py` MODIFY (UK → GB rename)
- `src/sonar/pipelines/daily_cost_of_capital.py` MODIFY (UK → GB rename)
- `tests/unit/test_cycles/test_financial_fcs.py` MODIFY (rename test refs)
- `tests/unit/test_overlays/test_crp.py` MODIFY
- `tests/unit/test_overlays/test_live_assemblers.py` MODIFY
- `tests/unit/test_pipelines/test_daily_cost_of_capital.py` MODIFY
- `docs/backlog/calibration-tasks.md` MODIFY (CAL-128-FOLLOWUP closure)
- `docs/planning/retrospectives/week9-sprint-p-cal-128-followup-report.md` NEW

**Sprint S scope** (for awareness, DO NOT TOUCH):
- `src/sonar/connectors/boc.py` NEW
- `src/sonar/connectors/te.py` APPEND (CA wrapper)
- `src/sonar/indices/monetary/builders.py` APPEND (CA builders)
- `src/sonar/config/*.yaml` (CA entries)
- `src/sonar/pipelines/daily_monetary_indices.py` (CA dispatch — different pipeline from Sprint P's daily_cost_of_capital.py)
- Tests for CA connector

**Zero file overlap confirmed**. daily_cost_of_capital (Sprint P) ≠ daily_monetary_indices (Sprint S). Separate pipelines.

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-sprint-p && git pull origin main --rebase`

**Push race**: normal `git push origin sprint-p-cal-128-followup`. Zero collisions expected.

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-p-cal-128-followup
git push origin main
```

---

## 4. Commits

### Commit 1 — Pre-flight UK reference inventory

```
docs(planning): CAL-128-FOLLOWUP pre-flight UK reference inventory

Pre-flight: inventory UK references in 4 in-scope files.

Document in commit body:
  rg -n '\bUK\b|"UK"|_uk_|_UK_' \
    src/sonar/cycles/financial_fcs.py \
    src/sonar/overlays/crp.py \
    src/sonar/overlays/live_assemblers.py \
    src/sonar/pipelines/daily_cost_of_capital.py

Categorize findings per file:
- financial_fcs.py: [N refs; dict keys / function names / ...]
- crp.py: [N refs; ...]
- live_assemblers.py: [N refs; ...]
- daily_cost_of_capital.py: [N refs; ...]

Also identify test files that reference UK in test data/country_code
strings (will touch in Commit 5):
  rg -l '\bUK\b|"UK"' tests/unit/test_cycles/test_financial_fcs.py \
    tests/unit/test_overlays/test_crp.py \
    tests/unit/test_overlays/test_live_assemblers.py \
    tests/unit/test_pipelines/test_daily_cost_of_capital.py

Design decisions (documented commit body):
- Alias pattern: preserve "UK" as structlog-warning deprecated alias
  (per Sprint O + Week 9 chore commit precedent)
- Rename primary name: `_uk_` → `_gb_` function/constant names
- Removal target: Week 10 Day 1 (aligns with existing deprecation plan)

No code changes this commit. Pre-flight inventory only.
```

### Commit 2 — financial_fcs.py UK → GB rename

```
feat(cycles): financial_fcs.py UK → GB canonical rename (CAL-128-FOLLOWUP)

Modify src/sonar/cycles/financial_fcs.py:
- Rename function/constant names containing `_uk_` → `_gb_`
- Rename dict keys "UK": → "GB":
- Update string literals referencing country_code "UK" → "GB"
- Update docstring prose UK references → GB or "United Kingdom"

Backward compat aliases (if public API surface):
- Preserve `_uk_` function names as deprecated aliases
- Emit structlog deprecation warning with target=CAL-128-alias-removal-week10
- Alias body calls GB-canonical function

Tests:
- Update tests/unit/test_cycles/test_financial_fcs.py accordingly
- Keep 1 backward compat test verifying UK alias still functional + emits warning

Verify no new UK refs introduced + full ruff/mypy gate.

Coverage maintained.
```

### Commit 3 — crp.py + live_assemblers.py UK → GB rename

```
feat(overlays): crp + live_assemblers UK → GB canonical rename (CAL-128-FOLLOWUP)

Modify src/sonar/overlays/crp.py:
- UK country-specific vol_ratio / sovereign spread refs → GB
- Dict keys "UK": → "GB":
- Function/constant rename if applicable

Modify src/sonar/overlays/live_assemblers.py:
- UK branches in live CRP/ERP assembly → GB
- Country dispatch "UK" → "GB"
- Backward compat alias preservation

Backward compat aliases per Sprint O pattern.

Tests:
- Update tests/unit/test_overlays/test_crp.py
- Update tests/unit/test_overlays/test_live_assemblers.py
- Preserve 1 backward compat test per module

Coverage maintained.
```

### Commit 4 — daily_cost_of_capital.py UK → GB rename

```
feat(pipelines): daily_cost_of_capital UK → GB canonical (CAL-128-FOLLOWUP)

Modify src/sonar/pipelines/daily_cost_of_capital.py:
- UK country support dispatch → GB
- CLI --country UK → still accepted via _warn_if_deprecated_alias helper
  (pattern from Sprint O daily_monetary_indices.py)
- Internal flow routes to GB-canonical logic

COST_OF_CAPITAL_SUPPORTED_COUNTRIES (if exists): ("US", "EA", "GB", "UK")
with UK as deprecated alias.

Tests:
- Update tests/unit/test_pipelines/test_daily_cost_of_capital.py
- Add test: --country UK dispatches to GB path + emits deprecation warning

Coverage maintained.
```

### Commit 5 — CAL-128-FOLLOWUP closure + retrospective

```
docs(backlog+planning): CAL-128-FOLLOWUP CLOSED + retrospective

Update docs/backlog/calibration-tasks.md CAL-128-FOLLOWUP entry:
- Status: OPEN → CLOSED 2026-04-22 (Week 9 Day 1 Sprint P)
- Closure commit SHA list (commits 2-4 above)
- Note: "All 4 carve-out files renamed UK → GB. Backward compat aliases
  preserved per Sprint O pattern. Removal planned Week 10 Day 1 per
  CAL-128-alias-removal-week10 timeline."

Create docs/planning/retrospectives/week9-sprint-p-cal-128-followup-report.md:

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- UK reference inventory pre/post (count reduction)
- 4 files swept:
  - financial_fcs.py: [N → 0 UK refs except aliases]
  - crp.py: [N → 0]
  - live_assemblers.py: [N → 0]
  - daily_cost_of_capital.py: [N → 0]
- Backward compat alias surfaces count
- Coverage delta (no regression expected)
- Tests shipped (rename + preserve backward compat tests)
- HALT triggers fired / not fired
- Deviations from brief
- Pattern validation:
  - Sprint O/Week-9-chore alias pattern reusable across files
  - ISO compliance Phase 1 COMPLETE (all T1 countries + all overlay/cycle/pipeline consumers)
- Isolated worktree: zero collision incidents with Sprint S-CA parallel
- Merge strategy: branch sprint-p-cal-128-followup → main fast-forward
- Cleanup pointer: Week 10 Day 1 alias removal sprint

Final commit message: "docs: CAL-128-FOLLOWUP CLOSED + Sprint P retrospective"

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git merge --ff-only sprint-p-cal-128-followup
  git push origin main
```

### Commit 6 (optional) — Verification sweep

```
chore: verify zero UK refs in in-scope files post-rename

Final rg sweep:
  rg -l '\bUK\b|"UK"' src/sonar/cycles/financial_fcs.py \
    src/sonar/overlays/crp.py \
    src/sonar/overlays/live_assemblers.py \
    src/sonar/pipelines/daily_cost_of_capital.py

Expected: 0 files OR only alias definition sites.

If verification passes, no code change — commit as documentation trace.
If refs remain unexpectedly, HALT + categorize (escaped docstring, alias
body, etc.) + decide keep/rename.

Skip this commit if verification inline in Commit 5 retro.
```

---

## 5. HALT triggers (atomic)

0. **Pre-flight inventory reveals 0 UK refs** in expected files — verify scope correctness; may be Sprint O already caught these OR files don't have UK refs. If 0 refs, sprint trivial — ship Commit 5 retro noting finding.
1. **UK refs in files outside 4-file scope** — if rg finds UK in unexpected files, HALT + add to CAL-128-FOLLOWUP scope OR open new CAL item. Don't silently expand scope.
2. **Alias pattern misfit** — some UK refs may be inside docstrings only (prose, not code). Decide: rename docstrings too (yes) or preserve (no, history archive). Document decision.
3. **Test failures post-rename** — some tests may have hardcoded "UK" in assertions. Update + verify semantic equivalence preserved.
4. **Backward compat import break** — if downstream modules import `build_x_uk_inputs` and alias not properly exposed, imports fail. Verify `__all__` exports.
5. **Coverage regression > 3pp** → HALT.
6. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
7. **Concurrent Sprint S-CA touches Sprint P files** (shouldn't per §3) → reconcile via rebase.
8. **CAL-128-FOLLOWUP scope ambiguity** — if backlog entry unclear, re-read + consult Sprint O retro for authoritative scope list.

---

## 6. Acceptance

### Global sprint-end
- [ ] 4-6 commits pushed to branch `sprint-p-cal-128-followup`
- [ ] 4 in-scope files swept: financial_fcs.py + crp.py + live_assemblers.py + daily_cost_of_capital.py
- [ ] UK refs renamed to GB in all 4 files (except alias definitions)
- [ ] Backward compat aliases preserved with structlog deprecation warnings
- [ ] Tests updated + preserved backward compat test per module
- [ ] `rg '\bUK\b|"UK"' <4 files>` returns only alias body matches
- [ ] CAL-128-FOLLOWUP CLOSED in backlog
- [ ] Retrospective shipped
- [ ] Merge strategy documented
- [ ] Coverage maintained (no regression)
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week9-sprint-p-cal-128-followup-report.md`

**Final tmux echo**:
```
SPRINT P CAL-128-FOLLOWUP DONE: N commits on branch sprint-p-cal-128-followup
ISO compliance: 4 files swept (financial_fcs + crp + live_assemblers + daily_cost_of_capital)
Backward compat aliases: N surfaces preserved with deprecation warnings
CAL-128-FOLLOWUP CLOSED: 2026-04-22
HALT triggers: [list or "none"]
Merge: git checkout main && git merge --ff-only sprint-p-cal-128-followup
ISO compliance Phase 1: COMPLETE (all T1 + all consumers)
Artifact: docs/planning/retrospectives/week9-sprint-p-cal-128-followup-report.md
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

---

## 9. Notes on implementation

### Strict scope discipline critical
Sprint O HALT #0 was triggered by scope creep. This sprint has explicit 4-file scope. If rg finds UK refs elsewhere, HALT + open new CAL item.

### Alias pattern from Sprint O + Week 9 chore commit
Reusable template:
```python
async def _uk_something(*args, **kwargs):
    """DEPRECATED: use _gb_something. Removal planned Week 10 Day 1."""
    logger.warning(
        "_uk_something is deprecated; use _gb_something",
        deprecation_target="CAL-128-alias-removal-week10",
    )
    return await _gb_something(*args, **kwargs)
```

### Quick sprint — could be 1-1.5h
Scope is mechanical + narrow. If pre-flight shows low UK ref count, entire sprint closes fast.

### Week 10 Day 1 alias removal sprint — prepared
This sprint's CAL-128-FOLLOWUP closure + builders.py closure + Sprint O closure together span all deprecation aliases. Week 10 Day 1 removal sprint pulls all together in single commit.

### Isolated worktree workflow
Sprint P operates entirely in `/home/macro/projects/sonar-wt-sprint-p`. Branch: `sprint-p-cal-128-followup`. Final merge via fast-forward.

### Sprint S-CA parallel
Runs in `sonar-wt-sprint-s`. Different domains entirely. Zero file overlap per §3.

---

*End of Week 9 Sprint P CAL-128-FOLLOWUP brief. 4-6 commits. ISO compliance Phase 1 complete.*
