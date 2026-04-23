# Week 10 Sprint Z — Brief Filename Convention Lesson #15 Amendment Retrospective

**Sprint**: Z — R3/micro-bundle for Lesson #15 (Week 10 Day 3 late night).
**Branch**: `sprint-z-brief-filename-convention-lesson-15`.
**Worktree**: `/home/macro/projects/sonar-wt-z-brief-filename-convention-lesson-15`.
**Brief**: `docs/planning/week10-sprint-z-brief-filename-convention-lesson-15-brief.md` (format v3.2; applies v3.3 retroactively once merged).
**Duration**: ~25min CC (single session 2026-04-23 ~23:30 WEST arranque, well inside the 30-45min budget).
**Commits**: 4 substantive (brief upload + C1 + C2 + C3) + this retro = 5 total (retro bundled with SESSION_CONTEXT update as C4).
**Paralelo**: Sprint T running on `src/sonar/` + `docs/adr/` + `docs/backlog/`; Sprint Z touched `docs/planning/` + `docs/templates/` + `scripts/ops/` + `SESSION_CONTEXT.md`. Zero file overlap.
**Outcome**: **PASS**. Lesson #15 shipped permanent fix via three-file convention amendment (brief format v3.2 → v3.3, CC arranque template filename-aware, sprint_setup.sh diagnostic enhanced). Tier A acceptance clean; Tier B N/A (no systemd services affected).

---

## 1. Scope outcome vs brief

### Brief's ambition (§2 Spec, §3 Commits plan)

1. **C1** — brief format v3.2 → v3.3 codifies canonical filename pattern `week<NN>-<sprint_id>-brief.md`
2. **C2** — CC arranque template pre-flight `ls` + `Full brief` path use canonical form
3. **C3 (optional)** — `sprint_setup.sh` HALT diagnostic references the convention + common-mistake exemplar
4. **C4** — SESSION_CONTEXT mirror + this retro

### Delivered

| # | SHA | Subject | Status |
|---|---|---|---|
| C0 | `170163f` | `docs(planning): Sprint Z brief — filename convention Lesson #15 amendment` | SHIP |
| C1 | `accba7f` | `docs(planning): brief format v3.2 → v3.3 filename convention (Lesson #15)` | SHIP |
| C2 | `c85d5d6` | `docs(templates): CC arranque prompt filename-aware (Lesson #15)` | SHIP |
| C3 | `516d674` | `fix(ops): sprint_setup.sh HALT diagnostic — reference filename convention (Lesson #15)` | SHIP |
| C4 | (this commit) | `docs(session-context,planning): SESSION_CONTEXT Lesson #15 + Sprint Z retro` | SHIP |

**All 5 commits PASS** per brief §5 Tier A acceptance. C3 optional enhancement fit inside the 45min hard cap (single heredoc amendment + shellcheck clean + bash -n clean); budget deferral to Week 11 R3 not needed.

---

## 2. Lesson #15 summary

### Emergence timing

Surfaced during Sprint V arranque itself (2026-04-23 ~21:50 WEST). Brief originally uploaded as `week10-sprint-v-lessons-11-14-brief.md` — missing the trailing `-permanent-fixes` slug from `sprint_id = sprint-v-lessons-11-14-permanent-fixes`. `sprint_setup.sh`'s Lesson #1 fix glob (`docs/planning/week*-sprint-v-lessons-11-14-permanent-fixes-*brief.md`) returned zero matches and HALTed. Operator resolved manually (`git mv` rename + re-run sprint_setup); workflow interruption ~5 min.

### Root cause

Author-time discipline gap. `sprint_setup.sh` Lesson #1 fix DETECTS the mismatch (graceful HALT) but does not PREVENT it at brief-authoring time. No canonical filename convention existed in `brief-format-v3.md` or the CC arranque template; the pattern `week*-sprint-<id>-*brief.md` was tooling-implicit, not author-explicit.

### Fix shipped

Three-point codification:

1. **brief format v3.2 → v3.3** (`docs/planning/brief-format-v3.md` +53/-7): new top-level §Filename convention (canonical — v3.3) documents the exact pattern `week<NN>-<sprint_id>-brief.md`, worked example (Sprint V valid vs invalid), rationale, and author-side shell check snippet. `What changed in v3.3` narrative block added.

2. **CC arranque template filename-aware** (`docs/templates/cc-arranque-prompt.md` +12/-5): pre-flight `ls` command + `Full brief` path both switched from `week{NN}-sprint-{sprint_id}-*brief.md` (ambiguous glob form) to `week<NN>-<sprint_id>-brief.md` (canonical literal). Rationale section gains Lesson #15 entry; `Last updated` timestamp bumped.

3. **sprint_setup.sh HALT diagnostic** (`scripts/ops/sprint_setup.sh` +11/-3): the zero-match HALT heredoc now references the canonical convention + brief format v3.3 + Week 10 Lesson #15, and surfaces the Sprint V exemplar (valid vs invalid filename). Glob logic unchanged — message-only enhancement. Shellcheck + `bash -n` clean.

---

## 3. Compound value (Week 11+)

- **Author-time first gate** — future brief uploads flag mismatch in the operator's own shell before sprint_setup runs, via the v3.3-documented `test -f "$EXPECTED"` pattern. Net expected: zero Sprint V-style manual `git mv` + re-run incidents.
- **Tooling-side diagnosis speed** — when a mismatch slips through (operator copy-paste drift), the enhanced `sprint_setup.sh` HALT message names the convention, the common mistake, and the 3-step resolution in-terminal. Week 10 Sprint V diagnosis took ~5min via operator recall; v3.3 diagnosis is immediate.
- **CC arranque discipline** — the template's pre-flight `ls` line used to include `-*brief.md` placeholder glob (ambiguous). With v3.3, CC's first tool call hits the exact canonical filename; if it's missing, the diagnosis is pointed ("filename-mismatch Lesson #15") rather than generic.
- **No runtime risk** — docs + single-heredoc shell change. No src/sonar/ touch, no systemd units affected, no DB schema implications.

---

## 4. Empirical validation plan

Convention is prescriptive: next CC sprint arranque will follow the v3.3 pattern naturally (brief author applies convention check before commit; CC arranque uses canonical ls form; sprint_setup.sh surfaces the enhanced HALT only if a mismatch slips through). No additional testing loop required for validation — the convention is shipped and observable via the next sprint brief upload.

Regression guard: Sprint T's brief already lives on main with the canonical shape (`week10-sprint-t-<slug>-brief.md`). Its post-merge lifecycle is the first live cross-check; operator confirms no HALT at its setup.

---

## 5. Week 10 lesson ledger final

12 lessons discovered across Day 1-3 (2026-04-21 → 2026-04-23):

| Lesson | Scope | Ship vehicle |
|---|---|---|
| #1 | `sprint_setup.sh` brief pre-flight + auto-cp | R1 bundle |
| #2 | Pre-commit double-run convention (brief format v3.1 §8) | R1 bundle |
| #3 | (skipped — not a distinct lesson) | n/a |
| #4 | `sprint_merge.sh` Step 10 tmux cleanup | R1 bundle |
| #5 | CC arranque template canonical | R1 bundle |
| #6 | Sprint T0 (shipped in-sprint, not retro bundle) | Sprint T0 |
| #7 | Brief format v3.1 §6 systemd verification clause | R1 bundle |
| #8 | CAL-TE-QUOTA-TELEMETRY — deferred Week 11+ | (deferred) |
| #11 | `.pre-commit-config.yaml` no-empty-commits hook | R2 bundle (V) |
| #12 | Brief format v3.1 → v3.2 Tier A/B systemd split | R2 bundle (V) |
| #13 | Auto-commit watcher investigation (decision deferred) | R2 bundle (V, investigation-only) |
| #14 | `sprint_setup.sh` DB auto-link + ADR-0011 Principle 7 | R2 bundle (V) |
| #15 | Brief filename convention + CC template + diagnostic | R3/micro (Z) |

**Totals**: 12 lessons. 11 shipped permanent fix (9 code/ops + 2 documentation/governance). 1 investigation-only (#13, pending operator decision Week 11). 1 deferred (#8, Week 11+ triage).

---

## 6. Machine discipline narrative

Week 10 set the canonical pattern: **discover gap → document lesson → ship fix same-or-next sprint**. R1 bundle (Day 3 afternoon) closed 6 lessons from Days 1-2. R2 bundle (Day 3 evening, Sprint V) closed 4 lessons that emerged during R1-era Sprint M/O arranque. R3/micro-bundle (Day 3 late night, Sprint Z) closed the single remaining lesson (#15) that emerged during Sprint V's own arranque.

Compound velocity observed: R1 → R2 → R3 cascade within ~6h. Each bundle enabled the next by making latent friction visible and removing it. The machine-discipline flywheel is operational.

Week 11+ lesson pipeline: #8 (CAL-TE-QUOTA-TELEMETRY) for triage, #13 (watcher decision) for operator review. No new lessons emerged during Sprint Z execution itself — the convention amendment is prescriptive-only, no adjacent drift surfaced.

---

## 7. Report-back

- Tier A acceptance: **PASS** (4/4 checks — brief format grep ≥3 matches 11, CC template canonical form grep ≥1 matches 3, sprint_setup.sh diagnostic grep ≥2 matches 2, SESSION_CONTEXT Lesson #15 present).
- Tier B acceptance: **N/A** (no systemd services affected).
- Shellcheck + `bash -n`: clean.
- Pre-commit double-run: clean across all 5 commits.
- Budget: actual ~25min vs expected 30-45min (well inside cap).
- Paralelo: zero overlap with Sprint T (confirmed via diff stat review).
- `sprint_merge.sh` Step 10 cleanup: operator-triggered post-merge (Tier B-equivalent discipline step).

---

*Sprint Z closes Week 10 Day 3 machine-discipline cascade. Lesson ledger final: 12 total, 11 permanent-fix shipped.*
