# Brief Format v3.3 (active from 2026-04-23 Week 10 Day 3 late night)

Builds on [`brief-format-v2.md`](./brief-format-v2.md). Same minimalist
spirit; adds three mandatory sections after Week 9 / Day 0 Week 10
merge workflow lessons (7 incidents in 5 days). v3.1 amends v3 with
five Week 10 lesson codifications (see §What changed in v3.1). v3.2
refines §6 systemd clause into Tier A (CC pre-merge) + Tier B
(operator post-merge) after Week 10 Lesson #12 (see §What changed in v3.2).
v3.3 codifies the brief filename convention after Week 10 Lesson #15
(see §What changed in v3.3). Supersedes v2 for new sprints. Existing
v2 briefs in `docs/planning/` are historical and ship as-is — **v3 is
forward-only; no retrofit required**. v3 → v3.1 → v3.2 → v3.3 is
additive — earlier-version briefs stay valid; retrofit only if edited.

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

## What changed in v3.2

Additive refinement of the v3.1 §6 systemd clause after Week 10 Sprint M
surfaced Lesson #12 — CC operates inside a worktree + has no sudo, so
`systemctl start` is structurally undeliverable pre-merge. v3.1's
"acceptance MUST include systemd verification" was therefore operationally
ambiguous (written as blocker, structurally deferred).

1. **REVISED §6 Invocation context requirements** — split into **Tier A
   (CC pre-merge)** + **Tier B (operator post-merge)**. Tier A covers
   local CLI + `bash -lc` wrapper smoke + tests + worktree-local grep
   for known-bad patterns — all structurally achievable inside a
   worktree. Tier B covers `sudo systemctl start` + journalctl +
   `systemctl is-active` + timer re-enable — operator-executed post-merge
   within 24h. Brief §6 acceptance reports Tier A as shippable criteria;
   retro §7 acknowledges Tier B as operator follow-up.

## What changed in v3.3

Additive codification of the brief filename convention after Week 10
Sprint V arranque surfaced Lesson #15 — the uploaded brief filename
dropped part of the sprint_id slug (`-permanent-fixes`), so
`sprint_setup.sh`'s Lesson #1 fix glob returned zero matches and
HALTed. The tooling detection worked; the author-time convention did
not exist. v3.3 fixes that gap.

1. **NEW §Filename convention (canonical)** — brief filename MUST
   follow `week<NN>-<sprint_id>-brief.md`, where `<sprint_id>` is the
   exact sprint ID literal (dashes, no abbreviation). Author-side
   first gate; `sprint_setup.sh` remains the tooling-side second
   gate.

## Filename convention (canonical — v3.3)

Brief filename MUST follow the pattern:

    week<NN>-<sprint_id>-brief.md

Where `<sprint_id>` is the EXACT sprint ID (dashes, not abbreviations).
Example:

- Sprint ID: `sprint-v-lessons-11-14-permanent-fixes`
- Valid filename: `week10-sprint-v-lessons-11-14-permanent-fixes-brief.md`
- INVALID: `week10-sprint-v-lessons-11-14-brief.md` (missing
  `-permanent-fixes`)

**Rationale**: `sprint_setup.sh` (Week 10 Lesson #1 fix) glob-matches
using the sprint_id literal. Filename abbreviation breaks the glob,
causing setup HALT. Enforcing exact sprint_id in filename prevents
author-time errors.

**Convention check before commit**:

```
EXPECTED="docs/planning/week${WEEK}-${SPRINT_ID}-brief.md"
test -f "$EXPECTED" || echo "WARNING: brief filename does not match sprint_id"
```

Author responsibility. `sprint_setup.sh` will catch mismatches but this
is the author-side first gate (Week 10 Lesson #15).

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

### Invocation context requirements (v3.2 — Week 10 Lessons #7 + #12)

If the deliverable affects code that runs via a systemd service (e.g.,
`sonar-daily-curves`, `sonar-daily-monetary-indices`,
`sonar-daily-cost-of-capital`, or future services), acceptance splits
into TWO tiers. CC operates inside a worktree + has no sudo, so
`systemctl start` is structurally undeliverable pre-merge (Week 10
Lesson #12). Tier A captures everything CC can verify inside the
worktree; Tier B captures the sudo-requiring verifications operator
executes post-merge within 24h.

Local CLI exit 0 is **not sufficient** — the systemd wrapper
(`bash -lc 'uv run ...'`) alters shell environment, CWD context, and
async event loop initialization. Week 10 Sprint T0 shipped with local
CLI passing but systemd failed (`Event loop is closed`); gap closed
only in Sprint T0.1. Tier A adds a bash-wrapper smoke surrogate that
simulates that environment without sudo.

#### Tier A — Pre-merge acceptance (CC scope)

CC must verify the following BEFORE claiming shipped. All four are
worktree-achievable without sudo. Brief §6 acceptance checkboxes
report Tier A results.

1. **Local CLI exit 0**:
   ```
   uv run python -m <module> <args>
   # Expected: exit 0 with the expected summary line + persist count
   ```
2. **Bash wrapper smoke (systemd surrogate)**:
   ```
   bash -lc 'cd /home/macro/projects/sonar-engine && uv run python -m <module> <args>'
   # Simulates sonar-daily-*.service's ExecStart wrapper: fresh shell,
   # login-profile PATH, CWD inheritance, async event-loop initialization.
   # Expected: exit 0; zero "Event loop is closed" / "connector_aclose_error"
   # in stderr.
   ```
3. **Unit + regression tests pass**:
   ```
   uv run pytest tests/unit/test_pipelines/ -k "<scope>"
   # Expected: green — drift guards + per-country dispatcher contracts.
   ```
4. **Worktree-local log grep (journal surrogate)**:
   ```
   uv run python -m <module> <args> 2>&1 | tee /tmp/sprint-<id>-stderr.log
   grep -iE "Event loop is closed|connector_aclose_error|Traceback" /tmp/sprint-<id>-stderr.log
   # Expected: zero matches.
   ```

#### Tier B — Post-merge acceptance (operator scope)

Operator executes after `sprint_merge.sh` reports success, within 24h:

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

**Ship / retro contract** — brief §6 reports Tier A verifications as
shippable criteria (CC exit). Retro §7 records Tier A as completed +
Tier B as operator follow-up (name + expected window). Operator
confirms Tier B within 24h of merge; if a Tier B failure emerges, it
opens a new sprint (not a retroactive HALT on the merged sprint).

For sprints NOT affecting systemd-invoked code, mark this sub-section
explicitly **N/A (no systemd services affected)**. Tier A/B both
become N/A.

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
without retrofit. Sprints Week 10 Day 1-2 use v3. Sprints Week 10
Day 3 (R1 bundle + Sprint M + Sprint O) use v3.1. Sprints Week 10
Day 3 late (Sprint V + Sprint T) use v3.2. Sprint Z (Day 3 late
night) onward use v3.3 (filename convention enforcement).

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
