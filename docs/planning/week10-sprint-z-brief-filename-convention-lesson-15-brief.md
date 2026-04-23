# Sprint Z — Brief Filename Convention Lesson #15 Amendment

**Branch**: `sprint-z-brief-filename-convention-lesson-15`
**Worktree**: `/home/macro/projects/sonar-wt-z-brief-filename-convention-lesson-15`
**Data**: 2026-04-23 Day 3 late night (~23:30 WEST arranque, paralelo com Sprint T)
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy per SESSION_CONTEXT)
**Budget**: 30-45min solo
**ADR-0010 tier scope**: N/A (docs + ops only)
**ADR-0009 v2 TE Path 1 probe**: N/A (no country-data fetch)
**Brief format**: v3.2 (Tier A / Tier B split)
**Systemd services affected**: none
**Parent**: Sprint V R2 bundle extension — Lesson #15 emerged during Sprint V brief arranque

---

## §1 Scope (why)

### Lesson #15 — Brief filename convention not enforced

**Pattern**: Sprint V brief was initially uploaded as `week10-sprint-v-lessons-11-14-brief.md` while sprint ID was `sprint-v-lessons-11-14-permanent-fixes`. The `-permanent-fixes` slug was missing from filename. `sprint_setup.sh` Lesson #1 fix glob (`docs/planning/week*-sprint-v-lessons-11-14-permanent-fixes-*brief.md`) returned no match → HALT at setup.

**Resolution applied manually**: `git mv` rename brief filename to include full sprint_id literal, then re-run `sprint_setup.sh`. Workflow interruption ~5 min operator time.

**Root cause**: brief author discipline — no enforcement that filename contains sprint_id exact literal. `sprint_setup.sh` Lesson #1 fix DETECTS the mismatch (HALT gracefully) but does not PREVENT it at author time.

**Operator framing**: each minor friction compounds across Week N sprints. Week 10 shipped 19 sprints = 19 brief uploads = potential 19× occurrences of this mismatch without convention enforcement.

### Objectivo Sprint Z

Codify convention **Brief filename MUST contain sprint_id literal** in 3 places:

1. `docs/planning/brief-format-v3.md` §8 (header metadata section) — convention rule
2. `docs/templates/cc-arranque-prompt.md` — pre-flight ls command uses derived filename
3. **Optional**: `scripts/ops/sprint_setup.sh` emits warning if multiple briefs matched but exact-sprint_id match unambiguous — improves diagnostic message

---

## §2 Spec (what)

### 2.1 Brief format v3.2 → v3.3 amendment

**File**: `docs/planning/brief-format-v3.md`

Add new subsection after header metadata block (or append to existing §8 Dependencies):

```markdown
### Filename convention (canonical)

Brief filename MUST follow pattern:

    week<NN>-<sprint_id>-brief.md

Where `<sprint_id>` is the EXACT sprint ID (dashes, not abbreviations). Example:

- Sprint ID: `sprint-v-lessons-11-14-permanent-fixes`
- Valid filename: `week10-sprint-v-lessons-11-14-permanent-fixes-brief.md`
- INVALID: `week10-sprint-v-lessons-11-14-brief.md` (missing `-permanent-fixes`)

**Rationale**: `sprint_setup.sh` (Week 10 Lesson #1 fix) glob-matches using sprint_id
literal. Filename abbreviation breaks glob, causing setup HALT. Enforcing exact
sprint_id in filename prevents author-time errors.

**Convention check before commit**:
```bash
EXPECTED="docs/planning/week${WEEK}-${SPRINT_ID}-brief.md"
test -f "$EXPECTED" || echo "WARNING: brief filename does not match sprint_id"
```

Author responsibility. Sprint_setup.sh will catch mismatches but this is
author-side first gate.
```

Bump version: v3.2 → v3.3.

### 2.2 CC arranque template update

**File**: `docs/templates/cc-arranque-prompt.md`

Current template pre-flight includes generic `ls` command. Update to derived-from-sprint_id:

```markdown
### Template pre-flight (filename-aware)

Before any tool call:

```
cd /home/macro/projects/sonar-wt-<sprint_id> && pwd
git rev-parse --abbrev-ref HEAD
# Expected: <sprint_id>

ls -la docs/planning/week<NN>-<sprint_id>-brief.md
# Canonical filename per brief format v3.3 convention (Lesson #15)
# If missing, HALT — brief upload or rename required before proceeding
```
```

Replace placeholder-form `week<NN>-sprint-<sprint_id>-*brief.md` with exact-form.

### 2.3 Optional — sprint_setup.sh diagnostic enhancement

**File**: `scripts/ops/sprint_setup.sh`

Current error on glob miss (Lesson #1 fix):
```
[HALT] No brief found matching docs/planning/week*-<sprint_id>-*brief.md
[HALT] Expected shape: docs/planning/week<NN>-<sprint_id>-<slug>-brief.md
```

Enhance with convention reference:
```
[HALT] No brief found matching docs/planning/week*-<sprint_id>-*brief.md
[HALT]
[HALT] Canonical filename convention (brief format v3.3, Week 10 Lesson #15):
[HALT]     week<NN>-<sprint_id>-brief.md
[HALT]
[HALT] Common mistake: brief filename uses abbreviated sprint_id.
[HALT] Example: sprint_id=sprint-v-lessons-11-14-permanent-fixes
[HALT]   VALID:   week10-sprint-v-lessons-11-14-permanent-fixes-brief.md
[HALT]   INVALID: week10-sprint-v-lessons-11-14-brief.md
[HALT]
[HALT] Resolution:
[HALT]   1. Rename existing brief OR upload with canonical name
[HALT]   2. Commit + push to main
[HALT]   3. Re-run: ./scripts/ops/sprint_setup.sh <sprint_id>
[HALT]
[HALT] OR supply --brief <path> for non-convention location.
```

**Scope note**: §2.3 is optional nice-to-have. If budget tight, skip C3 and ship Z via §2.1 + §2.2 only.

### 2.4 SESSION_CONTEXT.md update

Append to Lessons section:

```markdown
### Lesson #15 — Brief filename convention enforcement

- **Pattern**: brief filenames must contain sprint_id exact literal; abbreviated
  forms break sprint_setup.sh glob matching.
- **Fix shipped**: brief format v3.3 convention documented + CC arranque template
  updated + sprint_setup.sh diagnostic enhanced.
- **Sprint**: Z (Day 3 late night, ~23:30 WEST arranque)

### Total lessons Week 10: 12 (11 shipped permanent fix, 1 pending operator decision)
```

### 2.5 Retro

`docs/planning/retrospectives/week10-sprint-z-report.md` — brief retro:

- Lesson #15 emergence timing (Sprint V arranque)
- Fix scope (3 file amendments)
- Empirical validation plan: next CC sprint arranque will follow convention naturally (no additional testing needed — convention is prescriptive)
- Budget: expected 30-45min, actual X min
- Week 10 lesson ledger final: 12 total (10 R1 bundle shipping + Sprint V R2 + Sprint Z)

---

## §3 Commits plan

| Commit | Scope | Ficheiro |
|---|---|---|
| **C1** | docs(planning): brief format v3.2 → v3.3 filename convention | `docs/planning/brief-format-v3.md` |
| **C2** | docs(templates): CC arranque prompt filename-aware | `docs/templates/cc-arranque-prompt.md` |
| **C3** | fix(ops): sprint_setup.sh diagnostic enhancement (optional) | `scripts/ops/sprint_setup.sh` |
| **C4** | docs(session-context,planning): SESSION_CONTEXT Lesson #15 + Sprint Z retro | `SESSION_CONTEXT.md`, `docs/planning/retrospectives/week10-sprint-z-report.md` |

If budget tight, merge C3 into Week 11 R3 micro-bundle and ship Z with C1 + C2 + C4 only (3 commits).

---

## §4 HALT triggers

**HALT-0**: none expected — scope is pure docs + optional shell enhancement.

**HALT-material**:
- If C3 sprint_setup.sh enhancement accidentally breaks existing Lesson #1 fix behaviour → revert, ship C1 + C2 + C4 only.

**HALT-scope**:
- Any temptation to touch src/sonar/ → STOP (Sprint T running parallel)
- Any temptation to extend to Lessons #16+ (none exist yet) → STOP

**HALT-security**: standard.

---

## §5 Acceptance (Tier A per v3.3)

1. **Brief format v3.3 convention present**:
   ```bash
   grep "v3.3\|Filename convention\|Lesson #15" docs/planning/brief-format-v3.md | wc -l
   ```
   Expected: ≥3

2. **CC arranque template filename-aware**:
   ```bash
   grep "week<NN>-<sprint_id>-brief.md" docs/templates/cc-arranque-prompt.md | wc -l
   ```
   Expected: ≥1

3. **(Optional) sprint_setup.sh diagnostic enhanced**:
   ```bash
   grep "Canonical filename convention\|Common mistake" scripts/ops/sprint_setup.sh | wc -l
   ```
   Expected: ≥2 if C3 shipped, 0 if deferred

4. **SESSION_CONTEXT updated**:
   ```bash
   grep "Lesson #15\|Total lessons Week 10: 12" SESSION_CONTEXT.md
   ```
   Expected: matches found

5. **Shellcheck clean** (if C3 shipped):
   ```bash
   shellcheck scripts/ops/sprint_setup.sh
   ```
   Expected: exit 0

6. **Pre-commit clean double-run** (Lesson #2):
   ```bash
   uv run pre-commit run --all-files
   uv run pre-commit run --all-files
   ```
   Expected: clean second run

### Tier B: N/A (no systemd services affected).

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week10-sprint-z-report.md`:

1. **Lesson #15 emergence**: Sprint V arranque mismatch, discovered by sprint_setup.sh Lesson #1 fix HALT
2. **Fix scope**: 3 file amendments (brief format, CC template, optional sprint_setup)
3. **Compound value**: convention reduces author-time errors; sprint_setup.sh diagnostic reduces diagnosis time
4. **Week 10 lesson ledger final**: 12 total
   - 10 shipped permanent fix (R1: #1-#7 sans #3; R2: #11-#14; R3/Z: #15; #6 shipped Sprint T0)
   - 1 shipped investigation pending decision (#13)
   - 1 deferred Week 11+ (#8 CAL-TE-QUOTA-TELEMETRY)
5. **Machine discipline narrative**: Week 10 set canonical pattern — discover gap → document lesson → ship fix same-or-next sprint. Compound velocity.

---

## §7 Execution notes

- **CC arranque template** (Lesson #5 fix) — apply to this CC session
- **Pre-commit double-run** (Lesson #2)
- **sprint_merge.sh Step 10** cleanup (Lesson #4)
- **Paralelo awareness**: Sprint T running. Sprint T touches `src/sonar/` + `docs/adr/` + `docs/backlog/`. Sprint Z touches `docs/planning/` + `docs/templates/` + optionally `scripts/ops/` + `SESSION_CONTEXT.md`. **Zero overlap** expected.
- **Budget discipline**: hard 45min cap. If C3 optional enhancement extends budget, defer C3 to Week 11 R3 micro-bundle.
- **Low-stakes sprint**: pure discipline documentation, zero runtime risk.

---

## §8 Dependencies & CAL interactions

### Parent sprint
Sprint V (Lessons #11-#14 R2 bundle — Lesson #15 emerged during V arranque)

### CAL items closed by this sprint
- Lesson #15 permanent fix (no formal CAL, but V+Z bundle tracker closes)

### CAL items opened by this sprint
- None

### Sprints blocked by this sprint
- None

### Sprints unblocked by this sprint (structural)
- **All future sprints**: brief filename author-time convention + improved sprint_setup diagnostic = less workflow friction

---

*End of brief. Lesson #15 cleanup. Ship quick, close Week 10 lesson ledger cleanly.*
