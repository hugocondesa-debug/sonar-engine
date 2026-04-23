# CC Arranque Prompt Template (canonical)

**Purpose**: Canonical header for Claude Code session arranque. Prevents CWD stranding (Week 10 Lesson #5) and enforces discipline before work begins.

**When to use**: Every CC session arranque for a sprint. Paste the template as-is, customize `{placeholders}`.

---

## Template

```
Sprint {sprint_id} — {sprint_title}. Full autonomy per SESSION_CONTEXT.

=== MANDATORY PRE-FLIGHT ===

Before any other action, verify working directory:

  cd /home/macro/projects/sonar-wt-{sprint_id} && pwd

If the directory does not exist or pwd output differs from expected path, STOP
and report. Do not create the directory. Do not proceed with any tool call.

Confirm git branch:

  git rev-parse --abbrev-ref HEAD

Expected: sprint-{sprint_id}. If different, STOP and report.

Confirm brief present (canonical filename per brief format v3.3
§Filename convention — Week 10 Lesson #15):

  ls -la docs/planning/week<NN>-<sprint_id>-brief.md

Example (Sprint V): ls -la docs/planning/week10-sprint-v-lessons-11-14-permanent-fixes-brief.md

If missing, STOP. Brief upload verification (Week 10 Lesson #1 fix) should
have caught this at sprint_setup time; if we reach here without brief,
something drifted — typically a filename-mismatch (Lesson #15): the
uploaded brief does not contain the full sprint_id literal.

=== BRIEF ===

Full brief: docs/planning/week<NN>-<sprint_id>-brief.md
# Canonical form per brief format v3.3 §Filename convention (Lesson #15)

=== CONTEXT 1-LINER ===

{one_sentence_root_cause_or_scope}

=== CRITICAL SCOPE LOCKS ===

- {scope_lock_1}
- {scope_lock_2}

=== PRIMARY ACCEPTANCE ===

{primary_acceptance_gate} — NOT local CLI only if pipeline runs via systemd
(Week 10 Lesson #7). Must include systemctl is-active + journalctl verify
when applicable.

=== EXECUTION ===

Execute per brief §1-§{last}. HALT triggers §4. Report retro when shipped.

Pre-commit double-run before each commit (Week 10 Lesson #2).
sprint_merge.sh Step 10 handles worktree + tmux cleanup (Week 10 Lesson #4).
```

---

## Filled example (Sprint T0.1)

```
Sprint T0.1 — Monetary Pipeline Async Lifecycle Fix. Full autonomy per SESSION_CONTEXT.

=== MANDATORY PRE-FLIGHT ===

Before any other action, verify working directory:

  cd /home/macro/projects/sonar-wt-t0-1-monetary-async-fix && pwd

If the directory does not exist or pwd output differs from expected path, STOP
and report. Do not create the directory. Do not proceed with any tool call.

Confirm git branch:

  git rev-parse --abbrev-ref HEAD

Expected: sprint-t0-1-monetary-async-fix. If different, STOP and report.

Confirm brief present:

  ls -la docs/planning/week10-sprint-t0-1-monetary-async-fix-brief.md

If missing, STOP.

=== BRIEF ===

Full brief: docs/planning/week10-sprint-t0-1-monetary-async-fix-brief.md

=== CONTEXT 1-LINER ===

src/sonar/pipelines/daily_monetary_indices.py uses asyncio.run() per-country
(lines 627, 745). Event loop churn kills httpx.AsyncClient bound to dead loops.

=== CRITICAL SCOPE LOCKS ===

- Monetary pipeline only. Zero touch daily_curves / daily_cost_of_capital.
- No new connectors, no country expansion, no schema migration.

=== PRIMARY ACCEPTANCE ===

systemctl start sonar-daily-monetary-indices.service → exit 0 (inactive) OR
active. Zero 'Event loop is closed' in journalctl post-fix. Local CLI alone
is NOT sufficient (Week 10 Lesson #7).

=== EXECUTION ===

Execute per brief §1-§7. HALT triggers §4. Report retro when shipped.
Pre-commit double-run before each commit. sprint_merge.sh Step 10 handles
cleanup.
```

---

## Rationale

**Lesson #5 (CC CWD stranding)**: After `sprint_merge.sh` removes a worktree, CC's Bash tool retains the old worktree path as CWD. Subsequent `bash` calls fail with "no such directory". Template forces explicit `cd /absolute/path && pwd` as first action, surfacing stale-CWD immediately instead of silent failures mid-sprint.

**Lesson #7 (systemd vs local CLI)**: Template surfaces systemd acceptance requirement explicitly. If brief §5 acceptance is local-only, operator must amend before CC begins, not after CC claims shipped.

**Lesson #1 (brief upload)**: Pre-flight verifies brief present. If `sprint_setup.sh` pre-flight check (Lesson #1 fix) failed, this is second net.

**Lesson #15 (brief filename convention)**: Template pre-flight `ls` now uses the canonical `week<NN>-<sprint_id>-brief.md` form (brief format v3.3 §Filename convention). Abbreviated filenames break the glob match — surfacing the mismatch at author time prevents sprint_setup HALT mid-arranque.

**Lesson #4 (tmux cleanup)**: Template closing notes reference `sprint_merge.sh` Step 10 responsibility, reinforcing operator awareness.

**Lesson #2 (pre-commit double-run)**: Template closing notes reference explicitly, reducing operator reliance on memory.

---

## Maintenance

If additional lessons emerge, amend template with new gate clauses in PRE-FLIGHT section or EXECUTION notes. Template itself is versioned under `docs/templates/` for historical trace.

*Last updated: 2026-04-23 Week 10 Day 3 late night — Sprint Z (Lesson #15 filename convention).*
