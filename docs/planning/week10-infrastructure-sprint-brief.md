# Week 10 Infrastructure Sprint — Merge Automation + Brief Format v3

**Target**: Ship reusable merge automation tooling + update brief format to v3 with pre-merge checklist + document workflow discipline as governance.
**Priority**: HIGH (blocks sustainable paralelo CC velocity Week 10+)
**Budget**: 1-2h solo CC
**Commits**: ~4-5
**Base**: branch `infrastructure-merge-automation` (isolated worktree `/home/macro/projects/sonar-wt-infra`)
**Concurrency**: Solo — no parallel sprint. Must merge before Day 1 CAL-138 arranque.

---

## 1. Scope

In:
- `scripts/ops/sprint_merge.sh` NEW — atomic merge sequence (push + fetch + merge + push + cleanup) with failure HALT
- `scripts/ops/sprint_setup.sh` NEW — worktree creation + env copy + tmux session helper (optional companion to sprint_merge)
- `docs/planning/brief-format-v3.md` NEW — updated template with §Pre-merge checklist mandatory section
- `docs/planning/brief-format-v2.md` DEPRECATE — add header note pointing to v3
- `docs/governance/WORKFLOW.md` UPDATE — add paralelo CC orchestration discipline section (merge workflow lessons, 7 recovery pattern history)
- Makefile OR equivalent helper commands (optional — `make sprint-merge BRANCH=<x>`)

Out:
- Feature work (Sprint CAL-138 scope is separate)
- Automated worktree cleanup (script prompts, doesn't auto-delete)
- Pre-commit hook enforcement changes (separate)
- CI integration (script is local-use only Phase 2)

---

## 2. Spec reference

Authoritative:
- **Week 9 merge recovery pattern** — 4 rebase conflicts + 3 "branch not pushed to origin" recoveries + 1 Day 0 recovery = **7 incidents in 5 days** (Week 9 retrospective §§3-6)
- `CLAUDE.md` §5 — current "no push without authorization" interpretation
- `docs/planning/brief-format-v2.md` — current template
- `docs/planning/retrospectives/week9-retrospective.md` §Lessons — "merge workflow discipline" captured
- Sprint Z-WEEK9-RETRO §10 — deviations catalog

**Pre-flight requirement**: Commit 1 CC:
1. Read Week 9 retrospective §Lessons learned entries re merge workflow
2. Inventory Week 9 recovery incidents:
   - Day 1: S-CA rebase on main post-P merge (calibration-tasks.md union-merge)
   - Day 3: T-AU rebase (2 files)
   - Day 3: V-CH recovery (9-file union-merge via CC delegation)
   - Day 4: W-SE orphaned after cleanup-before-merge mistake (4th rebase via CC)
   - Day 4: X-NO push race (force-with-lease recovery)
   - Day 0 Week 10: cleanup-week10-day0 local-only recovery via reflog
   - Day 0 Week 10: docs/staging/ untracked files blocked merge
3. Document each pattern's root cause:
   - Pattern A: "branch not pushed to origin before merge" (2 occurrences)
   - Pattern B: "cleanup-before-merge" (1 occurrence)
   - Pattern C: "rebase expected, CC delegation efficient" (4 occurrences)
   - Pattern D: "untracked working tree blocks merge" (1 occurrence)
4. Document findings in Commit 1 body.

---

## 3. Concurrency — SOLO

**Worktree**: `/home/macro/projects/sonar-wt-infra`
**Branch**: `infrastructure-merge-automation`

Solo execution, no parallel sprint. Must ship + merge before Day 1 CAL-138 arranca (CAL-138 sprint uses new script + v3 template).

**Worktree sync**:
```bash
cd /home/macro/projects/sonar-wt-infra && git pull origin main
```

**Merge strategy end-of-sprint** (using new script — dogfooding!):
```bash
# First completion: manual merge since script doesn't exist yet
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only infrastructure-merge-automation
git push origin main
# Cleanup: worktree + branches local + remote
```

---

## 4. Commits

### Commit 1 — Pre-flight audit + scope confirmation

```
chore(infra): pre-flight audit for merge automation sprint

Week 9 + Day 0 merge incident inventory (document in commit body):

Pattern A: Branch not pushed to origin before merge attempt
  - Occurrence 1: Sprint W-SE Day 4 — merged to main locally, operator attempted origin merge which failed; recovered via manual push + rebase.
  - Occurrence 2: Day 0 Week 10 cleanup-week10-day0 — CC reported "branch ready for merge" but did not push; operator merge failed; recovered via reflog + push + merge.
  - Root cause: CLAUDE.md §5 "no push without authorization" interpreted over-conservatively. CC extends policy from "main branch" to "any branch".
  - Fix: brief format v3 §Pre-merge checklist mandates `git push -u origin <branch>` as explicit commit step, not deferred to operator.

Pattern B: Cleanup-before-merge mistake
  - Occurrence: Day 4 Week 9 — cleanup sequence executed bulk in single shell block; cleanup removed worktree before merge completed, orphaning commits locally.
  - Root cause: operator executed 6-step sequence as single shell paste, not step-by-step.
  - Fix: sprint_merge.sh script atomicizes sequence with exit-code gates; each step verifies prior before proceeding.

Pattern C: Rebase expected via paralelo CC
  - Occurrences: 4 × across Week 9 (S-CA, T-AU, V-CH, W-SE each required rebase post adjacent sprint merge)
  - Root cause: paralelo sprints modify shared append zones (te.py, fred.py, builders.py, pipelines, YAMLs, backlog). Linear merge ordering means 2nd branch rebases.
  - Status: NOT a bug — expected cost of paralelo velocity. CC delegation solves efficiency concern (15-25 min per rebase).
  - Fix: brief format v3 §Concurrency explicit about rebase expectation + CC delegation pattern.

Pattern D: Untracked working tree blocks merge
  - Occurrence: Day 0 Week 10 — docs/staging/ files uploaded by operator to staging, forgotten, merge refused due to untracked files that would be overwritten.
  - Root cause: no pre-merge workspace cleanliness check.
  - Fix: sprint_merge.sh runs `git status --porcelain` pre-merge; HALT if untracked OR modified files present; operator must clean or stash.

Scope this sprint:
1. scripts/ops/sprint_merge.sh — atomic sequence with HALT gates
2. scripts/ops/sprint_setup.sh (optional) — worktree creation helper
3. docs/planning/brief-format-v3.md — updated template
4. docs/planning/brief-format-v2.md — deprecation header
5. docs/governance/WORKFLOW.md — paralelo CC orchestration section

Subsequent commits implement each.
```

### Commit 2 — sprint_merge.sh implementation

```
feat(ops): sprint_merge.sh atomic merge automation

Create scripts/ops/sprint_merge.sh:

#!/bin/bash
# Sprint merge automation — atomic sequence with HALT gates.
# Usage: ./scripts/ops/sprint_merge.sh <branch-name>
#
# Sequence:
#   1. Verify workspace clean (no untracked or modified files)
#   2. Push branch to origin (with -u tracking)
#   3. Fetch origin
#   4. Checkout main + pull latest
#   5. Merge --ff-only origin/<branch>
#   6. Push main
#   7. Remove worktree (if exists)
#   8. Delete local branch
#   9. Delete remote branch
#  10. Verify final state (worktree list + branch list + log)
#
# HALT on any failure: exit non-zero + error message.
# No bulk cleanup — each step atomic + verified.

set -euo pipefail

BRANCH="${1:?Usage: $0 <branch-name>}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_HINT="$REPO_ROOT/../sonar-wt-${BRANCH#sprint-}"

log() { echo "[sprint_merge] $*"; }
halt() { echo "[HALT] $*" >&2; exit 1; }

# Step 1 — verify workspace clean
log "Step 1/10: verify workspace clean"
if [ -n "$(git status --porcelain)" ]; then
    git status --short
    halt "Workspace has untracked or modified files. Clean first: git stash OR git clean -fd OR commit."
fi
log "  ✓ Workspace clean"

# Step 2 — verify branch exists locally or in worktree
log "Step 2/10: verify branch $BRANCH exists"
if ! git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    # Maybe in a worktree?
    if ! git worktree list | grep -q "$BRANCH"; then
        halt "Branch $BRANCH not found locally or in any worktree."
    fi
fi
log "  ✓ Branch $BRANCH exists"

# Step 3 — push branch to origin
log "Step 3/10: push $BRANCH to origin"
# Find worktree where branch lives OR current repo
WORKTREE_FOR_BRANCH="$(git worktree list --porcelain | grep -B 2 "branch refs/heads/$BRANCH" | grep '^worktree' | sed 's/worktree //' | head -1)"
if [ -n "$WORKTREE_FOR_BRANCH" ] && [ "$WORKTREE_FOR_BRANCH" != "$REPO_ROOT" ]; then
    log "  Branch is in worktree: $WORKTREE_FOR_BRANCH"
    (cd "$WORKTREE_FOR_BRANCH" && git push -u origin "$BRANCH")
else
    git push -u origin "$BRANCH"
fi
log "  ✓ Branch pushed to origin"

# Step 4 — fetch origin
log "Step 4/10: fetch origin"
git fetch origin
log "  ✓ Origin fetched"

# Step 5 — checkout main + pull
log "Step 5/10: checkout main + pull"
git checkout main
git pull origin main --ff-only
log "  ✓ Main up-to-date"

# Step 6 — verify main is behind or equal to origin/<branch>
log "Step 6/10: verify fast-forward possible"
if ! git merge-base --is-ancestor HEAD "origin/$BRANCH"; then
    halt "Main is not ancestor of origin/$BRANCH. Rebase needed. Run:
    cd <branch-worktree>
    git fetch origin
    git rebase origin/main
    # resolve conflicts
    git push --force-with-lease origin $BRANCH
    Then re-run this script."
fi
log "  ✓ Fast-forward possible"

# Step 7 — merge --ff-only
log "Step 7/10: merge origin/$BRANCH --ff-only"
git merge --ff-only "origin/$BRANCH"
log "  ✓ Merge complete"

# Step 8 — push main
log "Step 8/10: push main"
git push origin main
log "  ✓ Main pushed"

# Step 9 — remove worktree (if exists)
log "Step 9/10: remove worktree (if exists)"
if [ -n "$WORKTREE_FOR_BRANCH" ] && [ -d "$WORKTREE_FOR_BRANCH" ]; then
    git worktree remove --force "$WORKTREE_FOR_BRANCH"
    log "  ✓ Worktree $WORKTREE_FOR_BRANCH removed"
else
    log "  - No worktree to remove"
fi

# Step 10 — delete branches
log "Step 10/10: delete local + remote branches"
git branch -d "$BRANCH" 2>/dev/null || git branch -D "$BRANCH"
git push origin --delete "$BRANCH" 2>/dev/null || log "  - Remote branch already deleted"
log "  ✓ Branches deleted"

log ""
log "=== Sprint merge COMPLETE: $BRANCH ==="
git log --oneline -5
git worktree list
echo ""

Permissions: chmod +x scripts/ops/sprint_merge.sh

Tests (ad-hoc — no formal test framework for shell):
- Verify script sets -euo pipefail (defensive)
- Verify shellcheck clean: shellcheck scripts/ops/sprint_merge.sh
- Verify executable bit: test -x scripts/ops/sprint_merge.sh

Document in commit body:
- Script is local-use only (not CI)
- HALT exits non-zero at any step failure
- Operator runs post-sprint-close in repo root
- Dogfooding: this sprint's own merge uses manual sequence (script not yet available)
```

### Commit 3 — sprint_setup.sh helper (optional but recommended)

```
feat(ops): sprint_setup.sh worktree + tmux helper

Create scripts/ops/sprint_setup.sh:

#!/bin/bash
# Sprint setup — create worktree + copy env + setup tmux session.
# Usage: ./scripts/ops/sprint_setup.sh <branch-name> [<tmux-session-name>]
#
# Creates:
#   1. Worktree at /home/macro/projects/sonar-wt-<branch-suffix>
#   2. Copies .env with 0600 perms
#   3. Creates tmux session with worktree as cwd

set -euo pipefail

BRANCH="${1:?Usage: $0 <branch-name> [tmux-session-name]}"
TMUX_SESSION="${2:-$(echo "$BRANCH" | sed 's/[^a-zA-Z0-9]/-/g' | cut -c1-20)}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
BRANCH_SUFFIX="${BRANCH#sprint-}"
BRANCH_SUFFIX="${BRANCH_SUFFIX%-connector}"
WORKTREE_PATH="$REPO_ROOT/../sonar-wt-$BRANCH_SUFFIX"

log() { echo "[sprint_setup] $*"; }

log "Creating worktree: $WORKTREE_PATH (branch $BRANCH)"
git -C "$REPO_ROOT" worktree add -b "$BRANCH" "$WORKTREE_PATH" main

log "Copying .env"
cp "$REPO_ROOT/.env" "$WORKTREE_PATH/.env"
chmod 0600 "$WORKTREE_PATH/.env"

log "Creating tmux session: $TMUX_SESSION"
tmux new-session -d -s "$TMUX_SESSION" -c "$WORKTREE_PATH" 2>/dev/null || log "  Session may already exist"

log ""
log "=== Sprint setup COMPLETE ==="
log "Worktree: $WORKTREE_PATH"
log "Branch: $BRANCH"
log "tmux: tmux attach -t $TMUX_SESSION"
log ""
log "Next: tmux attach -t $TMUX_SESSION; claude --dangerously-skip-permissions"

Permissions: chmod +x scripts/ops/sprint_setup.sh

Document in commit body:
- Pairs with sprint_merge.sh for complete sprint lifecycle
- Eliminates 4-5 manual commands per sprint start
- tmux session naming conventional (derive from branch)
```

### Commit 4 — Brief format v3

```
docs(planning): brief format v3 — pre-merge checklist mandatory

Create docs/planning/brief-format-v3.md (replace v2 as active template).

Key changes from v2:
1. NEW §10 Pre-merge checklist (before §"Merge command"):
   - [ ] All commits pushed: `git log origin/<branch>` shows expected commits
   - [ ] Workspace clean: `git status` returns no modifications
   - [ ] Pre-push gate passed: ruff + mypy + pytest green
   - [ ] Branch tracking set: `git branch -vv` shows [origin/<branch>]
   - [ ] Tests from sprint canaries documented in retro

2. REVISED §3 Concurrency:
   - Explicit paralelo CC pattern (isolated worktrees)
   - Rebase expectation stated (not surprise)
   - CC delegation for mechanical rebase (15-25min typical)

3. NEW §11 Merge execution:
   - Single command: `./scripts/ops/sprint_merge.sh <branch>`
   - HALT on any step failure (script exits non-zero)
   - Post-merge operator runs VPS-side actions if documented in brief

4. NEW §12 Post-merge verification:
   - `git log --oneline -10` expected tip
   - `git worktree list` expected main only
   - `git branch -a` expected minimal

Structure (v3):
  # Sprint <X> — <Title>
  ## 1. Scope (in/out)
  ## 2. Spec reference + pre-flight
  ## 3. Concurrency (paralelo protocol OR solo statement)
  ## 4. Commits (numbered with msg templates)
  ## 5. HALT triggers (atomic)
  ## 6. Acceptance (global sprint-end checklist)
  ## 7. Report-back artifact
  ## 8. Pre-push gate (mandatory)
  ## 9. Notes on implementation
  ## 10. Pre-merge checklist (NEW)
  ## 11. Merge execution (NEW)
  ## 12. Post-merge verification (NEW)

v2 deprecation:
- Add header to docs/planning/brief-format-v2.md:
  "**DEPRECATED** (2026-04-22). Use brief-format-v3.md for all new sprints.
  Kept for historical reference; existing briefs using v2 ship as-is.
  Migration to v3 is opt-in; no forced retrofit."

Document in commit body:
- v3 addresses 7 merge recovery incidents Week 9-10 Day 0
- Backward-compatible: v2 briefs continue to ship
- Week 10 Day 1+ briefs use v3
```

### Commit 5 — Governance WORKFLOW.md update

```
docs(governance): paralelo CC orchestration + merge discipline section

Update docs/governance/WORKFLOW.md with new section:

## Paralelo CC orchestration (Week 9+ pattern)

### When paralelo appropriate
- 2+ independent sprints with minimal file overlap
- Both sprints have clear scope + HALT triggers
- Operator bandwidth for monitoring 2 tmux sessions
- Velocity gain > merge overhead cost (typically ~30% gain, ~15% overhead)

### Isolated worktrees mandatory
- Each paralelo sprint gets `/home/macro/projects/sonar-wt-<suffix>`
- Created via `scripts/ops/sprint_setup.sh <branch>`
- Branch naming: `sprint-<letter-suffix>-<theme>` (e.g. sprint-y-dk-connector)

### Append-zone conventions
Shared files between paralelo sprints require explicit conventions:
- `src/sonar/connectors/te.py` — append new country wrappers at end of file
- `src/sonar/connectors/fred.py` — append FRED OECD series constants at end
- `src/sonar/indices/monetary/builders.py` — append builders using bookmark comments
- `src/sonar/pipelines/daily_monetary_indices.py` — MONETARY_SUPPORTED_COUNTRIES tuple union-merge
- `src/sonar/config/r_star_values.yaml` — different country keys merge clean
- `src/sonar/config/bc_targets.yaml` — different country keys merge clean
- `docs/backlog/calibration-tasks.md` — append CAL items at end

### Rebase protocol
- Paralelo sprints merge to main in alphabetical branch order
- 2nd branch rebases post-1st-merge (expected, not failure)
- CC delegation for rebase: operator creates worktree with branch, starts CC with rebase-specific prompt
- Typical rebase duration: 15-25 min CC wall-clock
- Zero-conflict rebase uncommon; union-merge across 5-11 files typical

### Merge discipline
Post Week 9 lessons, codified:

**DO**:
- Run `./scripts/ops/sprint_merge.sh <branch>` for full sequence
- Verify each script step completes before next (script handles this via `set -e`)
- Cleanup worktree + branches ONLY after merge confirmed on origin main
- Use brief format v3 with §Pre-merge checklist

**DON'T**:
- Execute merge + cleanup as single shell block
- Delete worktree before merge verified
- Push branch only implicitly (always explicit `git push -u origin <branch>` before merge attempt)
- Skip pre-merge workspace cleanliness check

### Recovery patterns (Week 9-10 documented)

Pattern A: Branch not pushed → `git branch --list <branch>` + `git log --oneline <branch>` confirm local; `git push -u origin <branch>`; re-attempt merge.

Pattern B: Cleanup-before-merge → `git reflog | head -20` finds orphaned commits; `git branch recovery <SHA>`; merge; cleanup.

Pattern C: Untracked files block → `git status --short` identifies; `git clean -fd` OR `git stash` OR commit; re-attempt merge.

Pattern D: Rebase conflict → CC delegation with union-merge prompt; typical 9-file conflict resolves 15-25min.

### Metric monitoring
Target: ≤ 1 merge incident per 10 sprints (10% incident rate).
Week 9 baseline: 6 incidents / 10 sprints (60% rate — unacceptable).
Week 10+ target: ≤ 3 incidents / 15 sprints (20% rate — improvement phase).
Week 11+ steady: ≤ 1 incident / 10 sprints (mature).

Incidents tracked in weekly retrospective §Lessons with root cause + recovery time.

Commit body documents:
- Section added per Week 9-10 Day 0 lessons
- Metrics established for tracking improvement
- Governance doc is living reference (updated as patterns emerge)
```

---

## 5. HALT triggers (atomic)

0. **Shellcheck fails** — script must pass shellcheck clean before commit. Fix syntax issues.
1. **Script syntax error** — run `bash -n scripts/ops/sprint_merge.sh` to validate.
2. **Permissions missing** — `chmod +x` required.
3. **Governance doc structure change** — WORKFLOW.md may need section reordering; preserve existing content, only add new section.
4. **Brief format v3 scope creep** — if v3 becomes rewrite vs incremental v2 enhancement, HALT and reassess.
5. **v2 deprecation wording** — must not invalidate existing v2 briefs (active in git history).
6. **Pre-push gate** — ruff/mypy skip for shell + docs; shellcheck hook active if configured.
7. **No --no-verify** — standard discipline.

---

## 6. Acceptance

### Global sprint-end
- [ ] `scripts/ops/sprint_merge.sh` shipped + executable + shellcheck clean
- [ ] `scripts/ops/sprint_setup.sh` shipped + executable (optional but recommended)
- [ ] `docs/planning/brief-format-v3.md` shipped with §Pre-merge checklist
- [ ] `docs/planning/brief-format-v2.md` header deprecation note added
- [ ] `docs/governance/WORKFLOW.md` paralelo CC orchestration section added
- [ ] 4-5 commits pushed to branch `infrastructure-merge-automation`
- [ ] **Pre-merge checklist executed** (dogfooding):
  - [ ] All commits pushed: `git log origin/infrastructure-merge-automation` shows tip
  - [ ] Workspace clean
  - [ ] Pre-push gate green
- [ ] Merge via manual sequence (script not available until after this sprint merges)
- [ ] Branch cleanup post-merge
- [ ] No --no-verify

---

## 7. Report-back artifact

No standalone retrospective file (infrastructure, not feature).

**Final tmux echo**:
```
INFRASTRUCTURE SPRINT DONE: N commits on branch infrastructure-merge-automation

Deliverables:
- scripts/ops/sprint_merge.sh (atomic merge, 10 steps, HALT gates)
- scripts/ops/sprint_setup.sh (worktree + tmux helper)
- docs/planning/brief-format-v3.md (pre-merge checklist mandatory)
- docs/governance/WORKFLOW.md (paralelo orchestration section)

Week 10 Day 1+ sprints use v3 format + sprint_merge.sh for merge.

Merge manual (script not yet in use):
  cd /home/macro/projects/sonar-engine
  git fetch origin
  git checkout main
  git merge --ff-only origin/infrastructure-merge-automation
  git push origin main
  # cleanup
  git worktree remove --force ../sonar-wt-infra
  git branch -d infrastructure-merge-automation
  git push origin --delete infrastructure-merge-automation

Post-merge: Day 1 Sprint CAL-138 arranque using sprint_setup.sh + sprint_merge.sh.
```

---

## 8. Pre-push gate (mandatory)

```
uv run pre-commit run --all-files
```

Hooks: whitespace + conventional commit + shellcheck (if configured) + secrets.

Shellcheck on new scripts:
```
shellcheck scripts/ops/sprint_merge.sh
shellcheck scripts/ops/sprint_setup.sh
```

No --no-verify.

---

## 9. Notes on implementation

### Script design principles
- Atomic: each step verified before next
- Idempotent where possible (e.g. remote branch delete swallows failure)
- Fail-loud: exit non-zero + clear error message
- No destructive bulk operations

### Governance doc style
Match existing WORKFLOW.md tone and structure. Add new section; do not rewrite existing.

### Brief format v3 rollout
- Week 10 Day 1+ sprints MUST use v3
- Active v2 briefs (if any still in flight — none currently) allowed to complete on v2
- Migration is forward-only

### Dogfooding limitation
This sprint ships sprint_merge.sh but cannot use it for its own merge (script doesn't exist pre-merge). Hugo executes manual sequence. Week 10 Day 1+ sprints use the new script.

### Shell script testing
No formal test framework. Ad-hoc verification:
- bash -n validates syntax
- shellcheck catches common issues
- Manual run in test branch (optional dry-run flag for future)

---

*End of infrastructure sprint brief. 4-5 commits. Reusable tooling + v3 template + governance updates. Unblocks Week 10+ feature sprints with better machine.*
