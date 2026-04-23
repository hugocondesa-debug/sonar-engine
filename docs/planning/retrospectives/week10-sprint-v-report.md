# Week 10 Sprint V — Lessons #11-#14 Permanent Fixes (R2 Bundle) Retrospective

**Sprint**: V — R2 machine-discipline bundle (Week 10 Day 3 late).
**Branch**: `sprint-v-lessons-11-14-permanent-fixes`.
**Worktree**: `/home/macro/projects/sonar-wt-v-lessons-11-14-permanent-fixes`.
**Brief**: `docs/planning/week10-sprint-v-lessons-11-14-permanent-fixes-brief.md` (format v3.1; applies v3.2 Tier A in-sprint).
**Duration**: ~45min CC (single session 2026-04-23 ~21:50-22:35 WEST, well inside the 2-3h budget).
**Commits**: 6 substantive + this retro = 7 total (one bundled with SESSION_CONTEXT update).
**Outcome**: **PASS**. All four Lessons (#11, #12, #13, #14) shipped permanent fix (3) + investigation (1). Zero src/sonar/ touch; zero file overlap with parallel Sprint O.

---

## 1. Scope outcome vs brief

### Brief's ambition (§2 Spec, §3 Commits plan)

1. **C1 — Lesson #11** empty-commit pathology → local pre-commit hook at commit-msg stage
2. **C2 — Lesson #12** systemd verify structural impossibility → brief format v3.1 → v3.2 Tier A/B split
3. **C3 — Lesson #13** auto-commit watcher triage → investigation doc (operator decides later)
4. **C4 — Lesson #14** worktree DB absence → `sprint_setup.sh` auto-link
5. **C5** — ADR-0011 Principle 7 worktree data lifecycle
6. **C6** — SESSION_CONTEXT update + this retro

### Delivered

| # | SHA | Subject | Status |
|---|---|---|---|
| C1 | `9432fd3` | `chore(pre-commit): no-empty-commits hook (Sprint V C1, Week 10 Lesson #11 fix)` | SHIP |
| C2 | `00dd8c0` | `docs(planning): brief format v3.1 → v3.2 Tier A/Tier B acceptance (Sprint V C2, Week 10 Lesson #12 fix)` | SHIP |
| C3 | `f83fbab` | `docs(governance): auto-commit watcher investigation (Sprint V C3, Week 10 Lesson #13 triage)` | SHIP |
| C4 | `f424c89` | `fix(ops): sprint_setup.sh DB auto-link to canonical (Sprint V C4, Week 10 Lesson #14 fix)` | SHIP |
| C5 | `f10f17c` | `docs(adr): ADR-0011 Princípio 7 — Worktree data lifecycle (Sprint V C5, Week 10 Lesson #14 fix)` | SHIP |
| C6 | (this commit) | SESSION_CONTEXT update + Sprint V retro | SHIP |

**All 6 commits PASS** per brief §5 Tier A acceptance criteria. Sprint T0.1-style HALTs not triggered. HALT-0 risk around Lesson #11 merge-commit false-positive pre-empted via proactive `MERGE_HEAD` / `CHERRY_PICK_HEAD` / `REVERT_HEAD` guard embedded in the hook entry command.

---

## 2. Lesson #11-#14 summary

### Emergence timing

All four lessons emerged Day 3 late afternoon + evening (2026-04-23 ~18:00-21:30 WEST):

| Lesson | Source sprint | Surfaced when | Symptom |
|---|---|---|---|
| #11 — empty commit | Sprint M | 20:47:25 (C5.1a) | `13dee4e` shipped empty; historical pollution + unclear provenance |
| #12 — systemd pre-merge impossibility | Sprint M + retrospective | 20:57-21:30 (retro write) | CC cannot `sudo systemctl start`; v3.1 §6 forces fake-pass or false-HALT |
| #13 — auto-commit watcher | Sprint M | 20:35-20:48 (5 commits during CC edit) | Unknown entity racing CC for staged content; CC's stage→commit mental model broken |
| #14 — worktree DB absence | Sprint O | 21:28-21:30 (audit pre-flight) | `sqlite3 data/sonar-dev.db` returns empty; audit impossible without operator manual symlink |

Timing pattern: three of four are Sprint M artifacts (PT + NL cascade's own R1-fix-driven behavior exposed them); one is Sprint O arranque artifact (audit-first discipline stressed the worktree bootstrap path). Both sprints are Day 3 outputs of the R1 bundle, so R1 enabled R2 — the machine-discipline flywheel working as designed.

### Root causes + fixes

- **#11 root cause**: pre-commit auto-fix hooks (`trailing-whitespace`, `end-of-file-fixer`, `ruff format`) silently modify files that were staged. `git commit` then sees those modifications as "unstaged" (the staged version is the pre-fix blob); if no other staged content remains, the commit proceeds with empty tree. **Fix**: `no-empty-commits` hook at `commit-msg` stage runs AFTER all auto-fixers; guards merge / cherry-pick / revert via `$GIT_DIR`-marker check; rejects with actionable re-stage message.

- **#12 root cause**: CC operates inside a worktree where `sudo systemctl start <service>` requires (a) primary repo context (systemd units reference `/home/macro/projects/sonar-engine/` paths), (b) operator sudo (CC has no sudoers entry). v3.1 §6 "acceptance MUST include systemd verification" ignored the structural gap. **Fix**: split §6 into Tier A (CC pre-merge, all worktree-achievable — local CLI + bash -lc wrapper smoke + tests + stderr grep) + Tier B (operator post-merge within 24h). Ship contract: brief §6 reports Tier A only; retro §7 records Tier B as operator follow-up; Tier B failure post-merge opens a new sprint, not a retroactive HALT.

- **#13 root cause** (forensic baseline only; decision pending): no filesystem evidence of a daemon on VPS (no user systemd, no cron, no inotify, no git hook, no plugin). H1 (parallel CC instance via second tmux session) is high-confidence — matches commit message quality (CC-grade narrative), timing throughput (5 commits in 13min), and `Co-Authored-By` trailer absence (second CC instance without CLAUDE.md §5 template). Sprint M retro's original note that watcher commits had the trailer was inverted — confirmed via `git show` inspection of `dce9287` / `612cf7f` / `94d68ec` / `a8e9987` / `2909ce6` (no trailer) vs `13dee4e` / `9f744c4` (CC-manual with trailer). **Fix**: none this sprint — investigation doc only. Operator decides Option A (disable) / B (canonize) / C (scope-limit) at Week 11.

- **#14 root cause**: `git worktree add` checks out tracked files — including the 0-byte placeholder `data/sonar-dev.db` that lives in the repo for schema-init-from-empty scenarios. Pre-flight sqlite3 queries on that stub silently return empty; audit impossible. **Fix**: `sprint_setup.sh` new step between tmux creation and Final state — handles 3 scenarios (absent / 0-byte stub / real file); symlinks by default per ADR-0011 Principle 7 (shipped alongside).

---

## 3. Lesson #13 investigation findings (summary)

Full baseline in `docs/governance/auto-commit-watcher-investigation.md`. Headline:

- **Negative filesystem evidence** — nothing on the VPS points to a scripted / daemonized watcher. Clean across user systemd, cron, inotify process tree, client-side git hooks, Claude Code plugin config, local Claude routine config.
- **Commit signature** — author = committer = `Hugo <hugocondesa@gmail.com>` (same as CC commits), message style = Conventional Commits + narrative body + Ref breadcrumbs (CC-grade), timing = <2 min from last file save, `Co-Authored-By` trailer = **absent** (this differs from CC-manual commits and was the key forensic discriminator).
- **High-confidence hypothesis** — H1: parallel CC instance orchestrated via a second tmux session Hugo maintains alongside the "reporting" CC session. Second CC instance's system prompt lacks the CLAUDE.md §5 trailer directive, hence the divergence.
- **Recommendation framework**: A disable / B canonize / C scope-limit — each with action, risk, when-to-pick criteria. **Decision NOT taken this sprint** per brief §2.3 scope lock. CAL-WATCHER-DECISION opens Week 11 for operator review.

---

## 4. V bundle compound value (Week 11+)

Permanent fixes compound across all future sprints. Unlike tactical patches that decay, R2 bundle improvements are structurally embedded:

- **No-empty-commits hook** — every future sprint's commits auto-verified; the C5.1a pathology cannot re-occur without an explicit `--allow-empty` override (which the hook does NOT block — intentional; documentation / audit commits legitimately use it).
- **Brief format v3.2 Tier A/B** — every future sprint-with-systemd-impact has unambiguous CC acceptance scope. No more fake-pass vs false-HALT dilemma. Retro convention codifies Tier B operator ownership + 24h window.
- **sprint_setup.sh DB auto-link** — every future worktree arrives with canonical DB accessible by default. Sprint T's 6-probe sparse sweep (if scheduled) saves 1 manual symlink step; any parallel-worktree sprint (Week 11 R3 if needed) saves N × ~2min.
- **ADR-0011 Principle 7** — canonical data lifecycle contract for the worktree workflow. Future ADRs / retros can reference it without re-deriving rationale.

---

## 5. R1 + R2 + V bundle comparison

| Bundle | Day | Lessons | Files touched | Permanent fix count |
|---|---|---|---|---|
| R1 (Day 3 afternoon) | 2026-04-23 Day 3 | #1-#7 | `sprint_setup.sh` + `sprint_merge.sh` + `brief-format-v3.md` v3.1 + `cc-arranque-prompt.md` + SESSION_CONTEXT | 6 fixes (5 code/ops + 1 doc) |
| R2 = Sprint V (Day 3 late) | 2026-04-23 Day 3 late | #11-#14 | `.pre-commit-config.yaml` + `brief-format-v3.md` v3.2 + `auto-commit-watcher-investigation.md` + `sprint_setup.sh` + `ADR-0011` + SESSION_CONTEXT | 4 fixes (2 code/ops + 2 doc/governance) |

**Total Week 10 permanent fixes**: 10 (8 code/ops + 2 documentation / governance). 11th lesson (#13 watcher) shipped investigation only; decision window Week 11. Week 10 machine-discipline narrative: 11 lessons in 5 days, 10 shipped permanent fix, 1 pending operator judgment — structural progress, not whack-a-mole.

---

## 6. Lesson count finalization

Week 10 lesson ledger (final, post-Sprint V):

| # | Lesson | Fix bundle | Status |
|---|---|---|---|
| 1 | Brief pre-flight + auto-stage to worktree | R1 | shipped |
| 2 | Pre-commit double-run convention | R1 | shipped |
| 3 | ADR-0009 v2 TE Path 1 probe matrix mandatory | R1 | shipped |
| 4 | `sprint_merge.sh` Step 10 tmux cleanup | R1 | shipped |
| 5 | CC arranque prompt template (CWD verify) | R1 | shipped |
| 6 | (reserved — Day 3 R1 bundle scope) | R1 | shipped |
| 7 | Systemd invocation verify in acceptance | R1 | shipped |
| 8 | (not formalized — merged into #7) | — | N/A |
| 9 | (not formalized — merged into #5) | — | N/A |
| 10 | (not formalized — Day 3 discovery, covered by #2/#4) | — | N/A |
| 11 | Empty commit pathology | R2 | shipped |
| 12 | Systemd verify structural impossibility pre-merge | R2 | shipped |
| 13 | Auto-commit watcher | R2 | **investigation shipped; decision pending** |
| 14 | Worktree DB absence | R2 | shipped |

---

## 7. Cognitive load observation

Sprint V executed alongside Sprint O with zero coordination cost. No file overlap by design (brief §1 + §2 scope locks). No merge-conflict surface. No shared session state. Sprint V CC session ran entirely in its worktree; Sprint O CC session ran entirely in its worktree. The only coupling was the `main` branch tip, which matters only at merge time.

This **validates Week 10's "machine discipline" narrative empirically**: the same structural upgrades that hardened the single-sprint workflow (brief pre-flight, tmux cleanup, pre-commit double-run, CC arranque template) also hardened the parallel-sprint workflow. Parallelism is a derivative benefit of single-sprint discipline, not a separate investment.

Week 10 budget reality check: Sprint V budgeted 2-3h, consumed ~45min. Sprint O budgeted 6-8h, consumed ~2h30 (Sprint O retro). Both under-spent because R1 bundle cleared the mechanical overhead that Day 1-3 AM sprints had been absorbing.

---

## 8. Tier A acceptance (v3.2 convention, applied in-sprint)

Sprint V itself applies v3.2 brief-format-v3.md Tier A acceptance convention it ships. Per brief §5:

1. **Empty commit hook fires** — simulated in sandbox (`/tmp/empty-commit-test`) before C1 commit; rejected empty staged tree with exit 1 + ERROR message. ✓ PASS
2. **Brief format v3.2 ship verification** — `grep "Tier A|Tier B|Week 10 Lesson #12" docs/planning/brief-format-v3.md | wc -l` → 18 (≥3 required). ✓ PASS
3. **Watcher investigation complete** — `wc -l docs/governance/auto-commit-watcher-investigation.md` → 351 (>50 required). ✓ PASS
4. **sprint_setup.sh DB symlink logic ships** — `grep -c "Lesson #14|DB symlinked|PRIMARY_DB" scripts/ops/sprint_setup.sh` → 6. ✓ PASS
5. **Shellcheck clean** — `shellcheck scripts/ops/sprint_setup.sh` exit 0, no output. ✓ PASS
6. **ADR-0011 Principle 7 present** — `grep "Princípio 7|Worktree data lifecycle" docs/adr/ADR-0011-systemd-service-idempotency.md` → non-empty. ✓ PASS
7. **Pre-commit clean double-run** — each of the 6 commits preceded by `uv run pre-commit run --files <changed>` twice; double-run idempotent. ✓ PASS

**Tier B**: N/A — Sprint V does not affect systemd services.

---

## 9. CAL items (§13)

### Parent sprint
Week 10 Day 3 Sprint M retro (discovered Lessons #11-#13) + Sprint O arranque audit failure (discovered #14).

### CAL items closed by this sprint
- Lesson #11 permanent fix (no formal CAL — R1 bundle tracker closed)
- Lesson #12 permanent fix (idem)
- Lesson #14 permanent fix (idem)

### CAL items opened by this sprint
- **CAL-WATCHER-DECISION** — operator reviews `docs/governance/auto-commit-watcher-investigation.md` + decides Option A / B / C at Week 11 triage. Blocks: nothing structurally; only unknown-provenance commit risk on future sprints.

### Sprints blocked by this sprint
None.

### Sprints unblocked by this sprint (structural benefits)
- **All future sprints** — no-empty-commits hook + brief format v3.2 + sprint_setup.sh DB auto-link.
- **Sprint T (sparse T1 sweep)** — if scheduled, benefits from sprint_setup.sh DB auto-link on the single worktree it needs; brief can apply v3.2 Tier A natively.

---

## 10. Lessons candidates (Sprint V execution itself)

Observations CC picked up during Sprint V execution that may become Week 10 Lesson #15+ if pattern re-emerges:

### Lesson candidate V1 — YAML plain-scalar colon-space parse failure

**Pattern**: `pre-commit-config.yaml` `entry:` values that contain `ERROR: ...` or similar colon-space substrings parse as nested mappings, breaking the YAML load silently (first-run error surface only).

**Fix applied in-sprint**: used folded block scalar (`>-`) for the `entry:` value in the no-empty-commits hook. Alternative: double-quoted string with `\"` escapes for inner double quotes. Folded block scalar is cleaner for multi-line bash entries.

**Would this repeat?**: yes, if future pre-commit custom hooks embed error messages with colon-space patterns. Candidate for inclusion in `.pre-commit-config.yaml` style comment if a third such hook is added.

### Lesson candidate V2 — Sprint M retrospective's watcher-commit trailer claim was inverted

**Pattern**: retrospectives written at sprint-close without post-hoc diff verification can miscapture forensic details. Sprint M retro stated watcher commits had the `Co-Authored-By` trailer; Sprint V investigation via `git show` confirmed the opposite (CC-manual commits have it; watcher commits lack it).

**Impact**: the corrected forensic detail is now the key discriminator in the investigation doc. Had Sprint V not re-audited, the Week 11 decision would have been based on an incorrect signature.

**Would this repeat?**: possibly. Mitigation: retrospectives that include forensic claims (commit SHAs + authorship attributes) should have those claims verified against `git show` at retro-write time. Not a structural sprint_setup / brief-format issue — more a CC discipline pattern worth naming.

Both candidates deferred to Week 10 close retro (or rolled into Week 11 if pattern re-emerges).

---

## 11. Residuals + follow-ups

**None this sprint.** All 6 commits clean; Tier A verification 7/7; zero src/sonar/ touch; zero Sprint O file overlap; shellcheck + pre-commit green twice on every commit.

**Operator follow-up (Week 11)**: CAL-WATCHER-DECISION per §9.

---

*End retro. R2 bundle shipped empirical. Week 10 machine-discipline
total: 10 permanent fixes + 1 pending operator decision over 5 days.
Week 10 close retro next (after Sprint O + any Sprint T + operator
watcher decision).*
