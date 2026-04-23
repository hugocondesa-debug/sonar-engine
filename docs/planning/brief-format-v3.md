# Brief Format v3.1 (active from 2026-04-23 Week 10 Day 3)

Builds on [`brief-format-v2.md`](./brief-format-v2.md). Same minimalist
spirit; adds three mandatory sections after Week 9 / Day 0 Week 10
merge workflow lessons (7 incidents in 5 days). v3.1 amends v3 with
five Week 10 lesson codifications (see §What changed in v3.1).
Supersedes v2 for new sprints. Existing v2 briefs in `docs/planning/`
are historical and ship as-is — **v3 is forward-only; no retrofit
required**. v3 → v3.1 is additive (new required fields) but backward
compatible — v3 briefs stay valid; retrofit only if edited.

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

## What changed in v3.1

Additive amendments codifying Week 10 lessons (#2 pre-commit double-run,
#3 TE Path 1 probe convention, #7 systemd acceptance gap). Backward
compatible — new required fields but old briefs stay valid.

1. **REVISED §2 Spec reference** — adds pre-flight probe matrix (ADR-0009 v2
   mandatory for country-data sprints). If sprint fetches country-specific
   data from a new source, brief MUST enumerate probe paths in priority
   order (TE Path 1 → national CB/stat office Path 2 → aggregators Path 3).
2. **REVISED §5 HALT triggers** (renumbered Acceptance) — invocation context
   requirements: if deliverable affects systemd-invoked code, acceptance
   MUST include systemctl is-active + journalctl verification clauses.
   Local CLI exit 0 is not sufficient (Week 10 Sprint T0 gap).
3. **REVISED §8 Pre-push gate** — explicit pre-commit double-run convention
   (first run auto-fixes; second run is idempotent pass).
4. **REVISED Header metadata** — adds ADR-0010 tier scope line, ADR-0009 v2
   TE Path 1 probe line, systemd services affected line. Third line drives
   §Acceptance applicability.
5. **NEW §13 Dependencies & CAL interactions** — structured dependency
   graph: parent sprint, CALs closed/opened, sprints blocked/unblocked.
   Forces explicit maintenance of cross-sprint dependencies.

## Structure (13 sections)

```
1.  Scope (in/out)
2.  Spec reference + pre-flight (+ probe matrix in v3.1)
3.  Concurrency (paralelo protocol OR solo statement)
4.  Commits (numbered with msg templates)
5.  HALT triggers (atomic)
6.  Acceptance (global sprint-end checklist + systemd clause in v3.1)
7.  Report-back artifact
8.  Pre-push gate (mandatory, double-run in v3.1)
9.  Notes on implementation
10. Pre-merge checklist              (v3)
11. Merge execution                  (v3)
12. Post-merge verification          (v3)
13. Dependencies & CAL interactions  (v3.1 NEW)
```

Sections 1-9 keep v2 semantics (with v3.1 amendments noted). Sections
10-12 added in v3. Section 13 added in v3.1, all mandatory.

## Skeleton

````markdown
# [Sprint name] — Execution Brief

**Target**: [Phase X Week Y Days A-B]
**Priority**: [HIGH/MEDIUM]
**Budget**: [Xh CC autonomous]
**Commits**: [N]
**Base**: branch `[branch-name]` (worktree `/home/macro/projects/sonar-wt-<suffix>`)
**Concurrency**: [paralelo with sprint-X OR solo]
**ADR-0010 tier scope**: [T1 ONLY | T2 | N/A (refactor)]
**ADR-0009 v2 TE Path 1 probe**: [mandatory | N/A (no country-data fetch)]
**Systemd services affected**: [list-of-service-names | none]

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

### Pre-flight probe matrix (ADR-0009 v2 — mandatory for country-data sprints)

If this sprint fetches country-specific data from a new source, the brief
MUST enumerate probe paths in priority order. Failure to enumerate =
author oversight, not scope flexibility.

| Path | Source tier | Rationale |
|---|---|---|
| 1 | Trading Economics (TE) | Broad coverage, uniform schema, canonical fallback |
| 2 | National CB / stat office API (BPstat, DNB, BdF, Banca d'Italia, ...) | Authoritative but inconsistent schemas |
| 3 | Aggregators (ECB SDW, Eurostat, OECD, BIS) | Uniform but lagged or limited granularity |

**Rule**: CC tries Path 1 first. If ≥6 daily tenors / sufficient data
granularity confirmed via TE, cascade directly. If Path 1 HALT-0
(insufficient data), Path 2. Same for Path 3 fallback.

For sprints that do NOT fetch country-data (refactor, test-only, docs),
mark this sub-section explicitly **N/A (no country-data fetch)**.

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

### Invocation context requirements (v3.1 — Week 10 Lesson #7)

If the deliverable affects code that runs via a systemd service (e.g.,
`sonar-daily-curves`, `sonar-daily-monetary-indices`,
`sonar-daily-cost-of-capital`, or future services), acceptance MUST
include systemd invocation verification.

Local CLI exit 0 is **not sufficient** — the systemd wrapper
(`bash -lc 'uv run ...'`) alters shell environment, CWD context, and
async event loop initialization. Week 10 Sprint T0 shipped with local
CLI passing but systemd failed (`Event loop is closed`); gap closed
only in Sprint T0.1.

Required clauses:

1. **Service starts clean**:
   ```
   sudo systemctl start <service>.service
   sleep <N>
   systemctl is-active <service>.service
   # Expected: active OR inactive (exit 0), NEVER failed
   ```
2. **Journal clean of known-bad patterns**:
   ```
   sudo journalctl -u <service>.service --since "<start_time>" --no-pager \
     | grep -iE "<known_bad_patterns>" | head -10
   # Expected: empty (zero matches)
   ```
3. **Summary legitimacy (pipeline-emitted)**:
   ```
   sudo journalctl -u <service>.service --since "<start_time>" --no-pager \
     | grep "<pipeline>.summary"
   # Expected: summary line with n_persisted or n_skipped_existing > 0,
   #           n_failed = 0
   ```
4. **Timer re-enable** (if timer was disabled during sprint for safety):
   ```
   sudo systemctl start <service>.timer
   systemctl is-active <service>.timer  # Expected: active
   ```

For sprints NOT affecting systemd-invoked code, mark this sub-section
explicitly **N/A (no systemd services affected)**.

### Global sprint-end
- [ ] [testable check]

## 7. Report-back

[retro artifact path OR "no standalone retro" statement + final
tmux echo structure]

## 8. Pre-push gate (mandatory)

**Pre-commit double-run convention** (v3.1 — Week 10 Lesson #2): before
each `git commit`, run the gate **twice**. First run auto-fixes
whitespace / EOL / import ordering (exits non-zero after mutation).
Second run is the idempotent pass (exits zero). Week 10 observed 6
occurrences of commit rejection from single-run; double-run is the
canonical pattern.

```
uv run pre-commit run --all-files   # first run — may mutate + exit non-zero
uv run pre-commit run --all-files   # second run — idempotent pass
```

No --no-verify. Hooks must pass green twice before the commit sequence
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

## 13. Dependencies & CAL interactions (v3.1 NEW — mandatory)

Forces dependency graph maintenance explicit. Reduces Week N+1 plan
ambiguity. Fields may be empty — but must be present with `N/A` or
`(none)` markers, not omitted.

### Parent sprint
`<Sprint ID OR N/A>`

### CAL items closed by this sprint
- `<CAL-ID-1>`: `<brief reason>`
- `<CAL-ID-N>`: …
- (or `none`)

### CAL items opened by this sprint (emergent from execution)
Fill retrospectively during retro — flag new CALs discovered mid-sprint.
- `<CAL-ID-new-1>`: `<brief reason>`
- (or `none — fill during retro if any emerge`)

### Sprints blocked by this sprint
- `<Sprint ID>`: `<why blocked>`
- (or `none`)

### Sprints unblocked by this sprint
- `<Sprint ID>`: `<what unlocked>`
- (or `none`)
````

## Deprecated: v2

`brief-format-v2.md` carries a DEPRECATED header pointing here. The
file is preserved for historical reference; briefs already written in
v2 (Week 4 - Week 9, Day 0 Week 10) complete their lifecycle on v2
without retrofit. Sprints Week 10 Day 1-2 use v3. New sprints Week 10
Day 4+ use v3.1.

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
