# Brief Format v3 (active from 2026-04-22)

Builds on [`brief-format-v2.md`](./brief-format-v2.md). Same minimalist
spirit; adds three mandatory sections after Week 9 / Day 0 Week 10
merge workflow lessons (7 incidents in 5 days). Supersedes v2 for new
sprints. Existing v2 briefs in `docs/planning/` are historical and
ship as-is — **v3 is forward-only; no retrofit required**.

## Purpose

Minimal execution briefs for Claude Code autonomous runs, with merge
discipline baked into the template so the operator does not have to
reassemble it mentally at sprint close.

## What changed from v2

1. **NEW §10 Pre-merge checklist** — explicit verification list the
   CC instance runs before handing the sprint back for merge. Covers
   the Week 9-10 incident patterns (branch pushed? workspace clean?
   pre-push gate green? branch tracking configured?).
2. **NEW §11 Merge execution** — single-command merge via
   `scripts/ops/sprint_merge.sh <branch>`. Atomic; HALTs on any step
   failure; no bulk cleanup.
3. **NEW §12 Post-merge verification** — the quick checks the
   operator runs after the script reports success (tip SHA, worktree
   list, branch list).
4. **REVISED §3 Concurrency** — paralelo CC protocol is now explicit.
   Rebase is stated as expected cost of parallel velocity, not an
   anomaly; CC delegation for mechanical rebase is the recommended
   path (15-25 min wall-clock typical).

## Structure (12 sections)

```
1.  Scope (in/out)
2.  Spec reference + pre-flight
3.  Concurrency (paralelo protocol OR solo statement)
4.  Commits (numbered with msg templates)
5.  HALT triggers (atomic)
6.  Acceptance (global sprint-end checklist)
7.  Report-back artifact
8.  Pre-push gate (mandatory)
9.  Notes on implementation
10. Pre-merge checklist     (NEW)
11. Merge execution         (NEW)
12. Post-merge verification (NEW)
```

Sections 1-9 keep v2 semantics. Sections 10-12 are new and mandatory.

## Skeleton

````markdown
# [Sprint name] — Execution Brief

**Target**: [Phase X Week Y Days A-B]
**Priority**: [HIGH/MEDIUM]
**Budget**: [Xh CC autonomous]
**Commits**: [N]
**Base**: branch `[branch-name]` (worktree `/home/macro/projects/sonar-wt-<suffix>`)
**Concurrency**: [paralelo with sprint-X OR solo]

---

## 1. Scope

In:
- [bullet]

Out:
- [bullet]

## 2. Spec reference

- docs/specs/[path] @ vX.Y
- docs/specs/conventions/[path]

**Pre-flight** (first commit body):
1. [read references]
2. [document findings]

## 3. Concurrency

**If paralelo**:
- Paralelo with: `sprint-<other>` (worktree `/home/macro/projects/sonar-wt-<other>`)
- Shared append zones: [list of files + merge convention]
- Merge order: [alphabetical by default; deviation requires justification]
- Rebase expectation: the later-merged branch rebases on main.
  Typical effort via CC delegation: 15-25 min wall-clock, 5-9 files
  union-merge. Not a failure mode.

**If solo**:
- Solo sprint; no parallel work. Merge before [downstream sprint]
  arranca.

## 4. Commits

### Commit 1/N — [task name]
```
[type]([scope]): [summary]

[body]
```

## 5. HALT triggers

1. [atomic condition]
...

## 6. Acceptance

### Global sprint-end
- [ ] [testable check]

## 7. Report-back

[retro artifact path OR "no standalone retro" statement + final
tmux echo structure]

## 8. Pre-push gate (mandatory)

```
uv run pre-commit run --all-files
```

No --no-verify. Hooks must pass green twice before commit sequence
begins (Day 4 Week 9 lesson — silent cache invalidation).

## 9. Notes on implementation

[any in-scope deviations or design details]

## 10. Pre-merge checklist (NEW — mandatory)

Before declaring the sprint ready for merge, verify each item. Failure
to satisfy any is a HALT; operator does not chase these.

- [ ] **All commits pushed to origin**:
      `git log origin/<branch> --oneline` shows the expected tip.
      (Pattern A: branch not pushed to origin before merge.)
- [ ] **Workspace clean**:
      `git status --porcelain` returns empty. No untracked, no
      modified, no staged-but-uncommitted files.
      (Pattern D: untracked working tree blocks merge.)
- [ ] **Pre-push gate green**:
      `uv run pre-commit run --all-files` passes on the final commit.
      Run twice before committing (cache invalidation lesson).
- [ ] **Branch tracking set**:
      `git branch -vv` shows `[origin/<branch>]` for the sprint
      branch. Set implicitly by `git push -u origin <branch>`.
- [ ] **Sprint canaries documented** in the retro / report-back
      artifact if live data was touched.

## 11. Merge execution (NEW — mandatory)

Single command, run from the primary repo root:

```
./scripts/ops/sprint_merge.sh <branch-name>
```

The script enforces the 10-step atomic sequence (workspace clean →
push → fetch → checkout main → ff-only → push main → cleanup). It
HALTs on any failure; no destructive step runs before the preceding
verification. See `scripts/ops/sprint_merge.sh` header for the
sequence + [`../governance/WORKFLOW.md`](../governance/WORKFLOW.md)
§Paralelo CC orchestration for recovery patterns.

If the script reports Pattern C (fast-forward not possible), the
recovery recipe is printed inline: rebase the branch worktree on
main, force-with-lease, re-run the script.

**Do not** run the merge + cleanup as a bulk shell block. Do not
delete the worktree before the script has removed it. These were
the root causes of the Week 9 Day 4 and Week 10 Day 0 recoveries.

## 12. Post-merge verification (NEW — mandatory)

After the script reports `=== Sprint merge COMPLETE ===`, the operator
confirms the final state:

- [ ] `git log --oneline -10` — tip is the expected sprint-final SHA.
- [ ] `git worktree list` — only the primary repo remains (or only
      active paralelo worktrees remain).
- [ ] `git branch -a` — no leftover `<branch>` locally;
      `origin/<branch>` absent.

Any leftover state here is the signal for the follow-up retrospective
§Lessons — do not paper over.
````

## Deprecated: v2

`brief-format-v2.md` carries a DEPRECATED header pointing here. The
file is preserved for historical reference; briefs already written in
v2 (Week 4 - Week 9, Day 0 Week 10) complete their lifecycle on v2
without retrofit. New sprints Week 10 Day 1+ use v3.

## References

- [`brief-format-v2.md`](./brief-format-v2.md) — historical predecessor.
- [`../governance/WORKFLOW.md`](../governance/WORKFLOW.md) §Paralelo
  CC orchestration — merge discipline + recovery patterns.
- `scripts/ops/sprint_merge.sh` — atomic merge script (Week 10
  infrastructure sprint, Commit 2).
- `scripts/ops/sprint_setup.sh` — worktree + tmux helper (Week 10
  infrastructure sprint, Commit 3).
- SESSION_CONTEXT §Decision authority — autonomy scope.
- [`./phase1-coverage-policy.md`](./phase1-coverage-policy.md) — gate
  thresholds.
