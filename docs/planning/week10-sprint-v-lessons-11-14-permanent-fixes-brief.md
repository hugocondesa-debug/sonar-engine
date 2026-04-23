# Sprint V — Lessons #11/#12/#13/#14 Permanent Fixes (R2 Bundle)

**Branch**: `sprint-v-lessons-11-14-permanent-fixes`
**Worktree**: `/home/macro/projects/sonar-wt-v-lessons-11-14-permanent-fixes`
**Data**: 2026-04-23 Day 3 late night (~21:40 WEST arranque, paralelo com Sprint O)
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy per SESSION_CONTEXT)
**Budget**: 2-3h solo
**ADR-0010 tier scope**: N/A (docs + ops only, zero coverage)
**ADR-0009 v2 TE Path 1 probe**: N/A (no country-data fetch)
**Systemd services affected**: none
**Parent**: Week 10 retro R1 bundle extension — 4 new lessons (#11-#14) discovered during Sprint M + O arranque

---

## §1 Scope (why)

Week 10 R1 bundle shipped permanent fixes for Lessons #1-#7. Four new lessons emerged Day 3 late afternoon + evening:

### Lesson #11 — Pre-commit auto-fix → empty commit pathology

**Pattern**: pre-commit hook auto-fix modifies files → files re-staged implicitly → subsequent `git commit` sees empty diff → empty commit shipped.

**Evidence**: Sprint M commit `13dee4e` (C5.1a) shipped empty. Cosmetic only but historial pollution + unclear provenance.

**Root cause**: git behavior when staged changes get unstaged by hooks during commit phase — commit proceeds with empty tree if no additional staged content remaining.

### Lesson #12 — Systemd verify structurally undeliverable pre-merge

**Pattern**: CC operates inside worktree + no sudo. `systemctl start` requires both primary repo context + sudo. Impossible for CC to satisfy Lesson #7 canonical acceptance pre-merge.

**Evidence**: Sprint T0 + T0.1 + M all required operator-driven systemd verification post-merge.

**Implication**: brief format v3.1 §5 systemd clause shipped R1 is operationally ambiguous — written as "acceptance required" but structurally deferred to operator. Needs formalization.

### Lesson #13 — Auto-commit watcher pre-empts CC commits

**Pattern**: unidentified watcher process observed filesystem changes in worktree and auto-committed 5/9 Sprint M commits before CC had opportunity. CC adapted with "git log -5 before commit" defensive pattern mid-sprint.

**Evidence**: Sprint M retrospective §8 lesson #13 documents 5/9 commits authored via watcher (not CC direct).

**Governance question**: intentional feature? Experimental config residual? Vector for non-reviewed commits entering historical record?

### Lesson #14 — Worktree DB absence breaks pre-flight data audits

**Pattern**: `sprint_setup.sh` creates worktree with git checkout but does NOT copy/link data/ contents. Worktree arrives with `data/sonar-dev.db` as 0-byte placeholder (from git's tracked stub) instead of canonical DB. CC attempts sqlite3 queries → empty output → audit pre-flight impossible.

**Evidence**: Sprint O audit §2.1 blocked until operator manual symlink (Day 3 ~21:30 WEST).

**Fix required**: `sprint_setup.sh` should symlink canonical DB automatically.

---

## §2 Spec (what)

### 2.1 Lesson #11 fix — Empty commit prevention

**File**: `.pre-commit-config.yaml` + optional `scripts/ops/pre-commit-wrapper.sh`

**Option A (preferred — simpler)**: pre-commit custom hook

Add to `.pre-commit-config.yaml` at appropriate position (before Conventional Commit hook, after fixers):

```yaml
  - repo: local
    hooks:
      - id: no-empty-commits
        name: Block empty commits
        entry: bash -c 'if git diff --cached --quiet; then echo "ERROR: Empty commit (no staged changes after hooks). Likely cause: pre-commit auto-fix unstaged your changes. Run git add + retry."; exit 1; fi'
        language: system
        pass_filenames: false
        stages: [commit-msg]
```

Rationale: runs at commit-msg stage (after other hooks). If staged tree empty at that point, aborts with actionable message.

**Option B (if Option A surfaces edge cases)**: Wrap `git commit` in shell alias or commit wrapper. Heavier, defer.

### 2.2 Lesson #12 fix — Brief format v3.2 pre/post-merge acceptance separation

**File**: `docs/planning/brief-format-v3.md`

Current v3.1 §5 (from R1 bundle):

```markdown
### Invocation context requirements
If deliverable affects code that runs via a systemd service, acceptance MUST include
systemd invocation verification.
```

Amend to v3.2:

```markdown
### Invocation context requirements (v3.2 amendment — Week 10 Lesson #12)

Acceptance splits into TWO tiers when deliverable affects systemd-invoked code:

#### Tier A — Pre-merge acceptance (CC scope)
CC must verify the following BEFORE claiming shipped:
1. Local CLI exit 0 via `uv run python -m <module>` direct invocation
2. Bash wrapper smoke test via `bash -lc 'uv run python -m <module>'` — simulates systemd
   wrapper environment (PATH, shell init, CWD inheritance)
3. Unit + regression tests pass
4. Zero 'Event loop is closed' / connector_aclose_error in worktree-local journal-equivalent
   logs

#### Tier B — Post-merge acceptance (OPERATOR scope)
Operator executes after merge to main:
1. `sudo systemctl start <service>.service`
2. `sleep <N>` + `systemctl is-active <service>` → inactive (exit 0) or active
3. `journalctl -u <service>` grep for known-bad patterns
4. `systemctl start <service>.timer` re-enable if stopped for sprint

**Brief acceptance (§5) reports Tier A verifications as shippable criteria. Retro (§6)
acknowledges Tier B as operator-owned follow-up. Sprint_merge.sh shipped merge;
operator confirms systemd post-merge within 24h.**
```

### 2.3 Lesson #13 triage — Auto-commit watcher investigation

**File**: `docs/governance/auto-commit-watcher-investigation.md` (new)

CC must:

1. **Discover watcher**: check running processes, systemd user services, cron, `.git/hooks/`, any IDE integrations
```bash
systemctl --user list-units --type=service --all | head -20
ps auxf | grep -iE "watch|inotify|auto.*commit" | head -10
ls -la .git/hooks/ | head -20
crontab -l 2>/dev/null
ls -la ~/.config/systemd/user/ 2>/dev/null
```

2. **Document findings** in the investigation doc:
   - Watcher process identity (if found) or "unidentified"
   - Trigger mechanism
   - Commit signature pattern (author, message style, timing)
   - Historical commit audit: `git log --all --format="%h %an %s" | grep -iE "auto|watch" | head -20`

3. **Recommendation section** with 3 options:
   - **Disable**: if unintended / experimental residual
   - **Document as canonical**: if intentional feature, add to SESSION_CONTEXT governance
   - **Scope-limit**: keep but restrict to specific paths/branches

**Decision NOT required this sprint** — investigation ONLY. Operator decides direction later.

### 2.4 Lesson #14 fix — sprint_setup.sh DB auto-link

**File**: `scripts/ops/sprint_setup.sh`

Add new step between tmux session creation and "Next" print:

```bash
# === DB canonical link (Week 10 Lesson #14 fix) ===
PRIMARY_DB="${PRIMARY_REPO}/data/sonar-dev.db"
WORKTREE_DB="${WORKTREE_PATH}/data/sonar-dev.db"

if [[ -f "$PRIMARY_DB" ]]; then
    # Ensure data/ exists in worktree
    mkdir -p "${WORKTREE_PATH}/data"

    # Remove any 0-byte placeholder that git checkout may have created
    if [[ -f "$WORKTREE_DB" ]] && [[ ! -L "$WORKTREE_DB" ]]; then
        DB_SIZE=$(stat -c%s "$WORKTREE_DB")
        if [[ "$DB_SIZE" -eq 0 ]]; then
            rm "$WORKTREE_DB"
        else
            echo "[sprint_setup] WARNING: non-zero file at $WORKTREE_DB, not overwriting"
            echo "[sprint_setup]   If this is a stale copy, remove manually and re-run"
        fi
    fi

    # Create symlink if no file present
    if [[ ! -e "$WORKTREE_DB" ]]; then
        ln -sf "$PRIMARY_DB" "$WORKTREE_DB"
        echo "[sprint_setup]   ✓ DB symlinked: data/sonar-dev.db -> $PRIMARY_DB"
    fi
else
    echo "[sprint_setup] WARNING: canonical DB not found at $PRIMARY_DB"
    echo "[sprint_setup]   Worktree data/ may be empty. Audit queries will fail."
fi
```

### 2.5 ADR-0011 Principle 7 amendment

**File**: `docs/adr/ADR-0011-systemd-service-idempotency.md`

New principle documenting worktree data lifecycle:

```markdown
### Principle 7 — Worktree data lifecycle

Worktrees created via `sprint_setup.sh` MUST have canonical DB accessible via symlink
to primary repo's `data/sonar-dev.db`. Rationale: builder-only sprints (M3, L4 composites,
etc.) require read access to upstream-persisted data; migration / schema-change sprints
need writable canonical state to avoid divergence.

Symlink (not copy) because:
- Single source of truth — Sprint writes visible immediately in primary
- Avoids divergence — CC Sprint X's backfill visible to Sprint Y reading same DB
- Idempotent via ADR-0011 Principle 1 — duplicate writes across concurrent worktrees
  handled at row-level

Operator reserves right to deviate (copy + isolated DB) for destructive schema experiments;
symlink is the default safe path.
```

### 2.6 SESSION_CONTEXT updates

**File**: `SESSION_CONTEXT.md`

Append to Machine Discipline section:

```markdown
### Sprint V shipped (Week 10 Day 3 late)

- `.pre-commit-config.yaml`: no-empty-commits hook (Lesson #11 fix)
- `docs/planning/brief-format-v3.md`: v3.1 → v3.2 Tier A/Tier B acceptance (Lesson #12)
- `docs/governance/auto-commit-watcher-investigation.md`: watcher triage (Lesson #13)
- `scripts/ops/sprint_setup.sh`: DB auto-link (Lesson #14)
- `docs/adr/ADR-0011`: Principle 7 worktree data lifecycle

### Total lessons Week 10: 11 (8 shipped permanent fix, 3 documented only pending decision)
- Lesson #1-#7: shipped R1 bundle Day 3
- Lesson #11: shipped V bundle Day 3 late
- Lesson #12: shipped V bundle Day 3 late
- Lesson #13: investigation shipped, decision pending operator review
- Lesson #14: shipped V bundle Day 3 late
```

---

## §3 Commits plan

| Commit | Scope | Ficheiros esperados |
|---|---|---|
| **C1** | chore(pre-commit): no-empty-commits hook (Lesson #11 fix) | `.pre-commit-config.yaml` |
| **C2** | docs(planning): brief format v3.1 → v3.2 Tier A/Tier B acceptance (Lesson #12 fix) | `docs/planning/brief-format-v3.md` |
| **C3** | docs(governance): auto-commit watcher investigation (Lesson #13 triage) | `docs/governance/auto-commit-watcher-investigation.md` |
| **C4** | fix(ops): sprint_setup.sh DB auto-link to canonical (Lesson #14 fix) | `scripts/ops/sprint_setup.sh` |
| **C5** | docs(adr): ADR-0011 Principle 7 worktree data lifecycle | `docs/adr/ADR-0011-systemd-service-idempotency.md` |
| **C6** | docs(session-context,planning): SESSION_CONTEXT update + Sprint V retro | `SESSION_CONTEXT.md`, `docs/planning/retrospectives/week10-sprint-v-report.md` |

---

## §4 HALT triggers

**HALT-0 (structural)**:
- Lesson #11 fix — no-empty-commits hook triggers false positive on legitimate merge commits (merge commits may have zero diff vs parent by design) → refine hook to exclude merge commits OR abandon Option A in favor of Option B wrapper.

**HALT-material**:
- Lesson #13 investigation discovers watcher is **destructive** (e.g., auto-commits + auto-pushes, potentially leaking secrets) → STOP. Disable immediately. Escalate to operator.
- Lesson #14 DB symlink approach breaks some downstream tool (e.g., alembic migrations check file type) → STOP. Document, revert, decide copy-vs-symlink reconsidered.

**HALT-scope**:
- Tentação de extender para Lessons #1-#10 retro-amendments → STOP. V is #11-#14 scope.
- Tentação de touch `src/sonar/` code → STOP. V is docs + ops + config only.
- Tentação de tocar Sprint O files (`daily_monetary_indices.py`, M3 builders, audit doc) → STOP. Sprint O paralelo running.

**HALT-security**: standard.

---

## §5 Acceptance

### Tier A (pre-merge, CC scope — following new v3.2 convention this sprint ships)

1. **Empty commit hook fires**:
   ```bash
   # In worktree, test with contrived empty commit attempt
   git commit --allow-empty -m "test: empty commit"  # should FAIL at hook
   ```
   Expected: hook rejects, exit non-zero, actionable message emitted.

2. **Brief format v3.2 ship verification**:
   ```bash
   grep "Tier A\|Tier B\|Week 10 Lesson #12" docs/planning/brief-format-v3.md | wc -l
   ```
   Expected: ≥3 matches.

3. **Watcher investigation complete**:
   ```bash
   test -f docs/governance/auto-commit-watcher-investigation.md
   wc -l docs/governance/auto-commit-watcher-investigation.md  # should be >50 lines documenting findings
   ```

4. **sprint_setup.sh DB symlink logic ships**:
   ```bash
   grep -A 3 "Lesson #14\|DB symlinked\|PRIMARY_DB" scripts/ops/sprint_setup.sh | head -20
   ```
   Expected: logic present.

5. **Shellcheck clean**:
   ```bash
   shellcheck scripts/ops/sprint_setup.sh
   ```
   Expected: clean exit 0.

6. **ADR-0011 Principle 7 present**:
   ```bash
   grep "Principle 7\|Worktree data lifecycle" docs/adr/ADR-0011-systemd-service-idempotency.md
   ```
   Expected: present.

7. **Pre-commit clean (double-run per Lesson #2)**:
   ```bash
   uv run pre-commit run --all-files
   uv run pre-commit run --all-files
   ```
   Expected: clean second run.

### Tier B (post-merge, operator scope — applied Day 4 manhã)

Not applicable this sprint — Sprint V doesn't affect systemd services. Tier B convention applies to future sprints.

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week10-sprint-v-report.md`:

1. **Lesson #11-#14 summary**: emergence timing (all Day 3 late afternoon/evening), root causes, fixes shipped
2. **Lesson #13 investigation findings**: watcher identity, recommendation (disable / document / scope-limit)
3. **V bundle compound value Week 11+**: future sprints using sprint_setup.sh get DB auto-linked (zero operator manual step), empty commits blocked (historial clean), brief acceptance Tier A/B unambiguous (structural clarity)
4. **R1 + V comparison**: R1 shipped 6 fixes for Lessons #1-#7 (Day 1-3 lessons). V ships 4 fixes for Lessons #11-#14 (Day 3 lessons). Total Week 10 permanent fixes: **10** (8 code/ops + 2 documentation/governance)
5. **Week 10 lesson count final**: 11 discovered, 10 shipped permanent fix, 1 (Lesson #13) shipped investigation pending operator decision
6. **Cognitive load observation**: shipping Sprint V alongside Sprint O required zero coordination (clean file partition). Validates Week 10 "machine discipline" narrative — discipline structure enables parallelism without overhead.

---

## §7 Execution notes

- **Start with §2.3 (Lesson #13 investigation)** — this is pure discovery, runs quickly, establishes baseline before fix commits. If watcher is problematic, may need triage pause.
- **§2.4 sprint_setup.sh fix**: test manually with a temp sprint ID before merge. Confirm 3 scenarios: (a) primary DB exists + no worktree DB → symlink created, (b) primary DB exists + worktree has 0-byte DB → remove + symlink, (c) primary DB exists + worktree has real DB → warning, don't overwrite.
- **§2.1 pre-commit hook test**: after adding, verify hook runs in correct order. Order matters — must run AFTER auto-fixers, BEFORE Conventional Commits. Use `stages: [commit-msg]` to guarantee late execution.
- **Pre-commit double-run** before each commit (Week 10 Lesson #2).
- **sprint_merge.sh Step 10** cleanup (Lesson #4 fix).
- **CC arranque template** (Lesson #5 fix) — applied to this CC session from start.
- **Paralelo awareness**: Sprint O actively running. Zero overlap. If Sprint O CC outputs retro during V execution, operator handles O merge AFTER V merge.

---

## §8 Dependencies & CAL interactions

### Parent sprint
Week 10 Day 3 Sprint M retro (discovered Lessons #11-#13) + Sprint O arranque audit failure (discovered Lesson #14)

### CAL items closed by this sprint
- Lesson #11 permanent fix (no formal CAL, but R1 bundle tracker closed)
- Lesson #12 permanent fix (idem)
- Lesson #14 permanent fix (idem)

### CAL items opened by this sprint
- **CAL-WATCHER-DECISION** — operator reviews Lesson #13 investigation findings + decides disable/canonize/scope-limit (Week 11 triage)

### Sprints blocked by this sprint
- **None**

### Sprints unblocked by this sprint (structural benefits)
- **All future sprints** benefit from:
  - No-empty-commits hook (cleaner historial)
  - Brief format v3.2 (unambiguous acceptance)
  - sprint_setup.sh DB auto-link (no manual symlink step)
- **Sprint T (sparse T1 sweep)** immediately benefits — 6 worktree setups × saved manual DB step = ~6× convenience gain

---

## §9 Sprint T preview (post-V)

If Sprint O still running when V ships + Hugo energy sustained, Sprint T (sparse T1 sweep) is next. Preview:

- **Scope**: probe 6 countries (AU/NZ/CH/SE/NO/DK) via TE Path 1, apply ADR-0009 v2.2 S1/S2 classifier as triage
- **Budget**: 4-6h
- **Coverage delta**: +4-6pp L2 curves (realistic 3-4 PASS of 6)
- **Risk**: Médio — 6 live probe decisions, reviewer bandwidth during 3 concurrent sprints
- **Benefit from V shipping first**: sprint_setup.sh DB auto-link saves manual symlink × 1 worktree (Sprint T would be single worktree, 6 probes sequential in same CC session)

Sprint T brief produced only after Sprint V ship + operator confirms energy + Sprint O state assessment.

---

*End of brief. Meta-work discipline hardening. Ship compound value.*
