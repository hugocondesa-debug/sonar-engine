# Week 10 Day 0 — Cleanup & Strategic Alignment Sprint

**Target**: Post-Week-9 consolidation — apply consumer model revision (README + ROADMAP) + CAL backlog grooming + minor tech debt cleanup + retro backfill check. Single solo execution, no paralelo CC, low-risk discipline-intensive work.
**Priority**: HIGH (unblocks Week 10+ strategic execution on clean premise)
**Budget**: 5-6h solo CC
**Commits**: ~6-10 (granular per track)
**Base**: branch `cleanup-week10-day0` (isolated worktree `/home/macro/projects/sonar-wt-day0-cleanup`)
**Concurrency**: Solo — no parallel sprint

---

## 1. Scope

In (4 tracks):

**Track 1 — Strategic documentation (~2h)**
- Apply README.md update (consumer model revision — MCP/API privado + Website público)
- Apply ROADMAP.md update (Phase 3 reframed around L7 API + Website, Phase 2.5 NEW bridge phase, deprecations)
- Resolve SESSION_CONTEXT canonicality conflict raised Sprint Z-WEEK9-RETRO
- Update CLAUDE.md if canonicality resolution requires it

**Track 2 — CAL backlog grooming (~2h)**
- Audit CAL items Weeks 7-9 shipped not closed in `docs/backlog/calibration-tasks.md`
- Close with commit-SHA references
- Deduplicate country-specific CALs (M2/M4/M3 per-country) vs generic Phase 2+ items
- Re-categorize stale items (CAL items that became Phase 2.5 OR Phase 3 scope per roadmap revision)

**Track 3 — Minor cleanup (~1-2h)**
- Flaky test triage (pre-existing test-ordering issue, Sprint V-CH/W-SE/X-NO/Y-DK retros documented)
- Production DB orphan cleanup on VPS (`sonar.db`, `data/sonar-dev.db`, `sonar_phase0.db` 0-byte files)
- curves service file cosmetic comment update
- systemd services audit script commit
- Weekly canary CAL-137 wiring decision (wire now OR defer to CAL-138 sprint)

**Track 4 — Retro backfill check (~30min)**
- Verify Sprint I Week 8 retrospective exists
- Verify Week 7 Sprint G retrospective format (Phase 1 close + M1 US milestone declaration)
- Backfill gaps OR document rationale for absence

Out:
- CAL-138 curves multi-country implementation (separate Sprint Week 10 Day 1-2)
- Per-country ERP live paths (Week 10 Day 2+ scope)
- T2 expansion (Phase 2.5 scope)
- Any feature work
- Production code changes beyond service file cosmetic
- Anything requiring new tests or migrations

---

## 2. Spec reference

Authoritative:
- `/mnt/user-data/outputs/README.md` — source of Track 1 README update (upload to `/home/macro/projects/sonar-wt-day0-cleanup/docs/staging/README.md` via scp)
- `/mnt/user-data/outputs/ROADMAP.md` — source of Track 1 ROADMAP update
- `docs/backlog/calibration-tasks.md` — current CAL state (Track 2)
- `docs/planning/retrospectives/week9-retrospective.md` — Week 9 CAL evolution (Z-RETRO §6)
- `docs/planning/retrospectives/week9-sprint-*-report.md` — individual sprint CAL closures (Track 2)
- `docs/milestones/m1-us.md` + `docs/milestones/m1-us-gap-analysis.md` — Week 7 closure artifacts (Track 4)
- `CLAUDE.md` §8 — SESSION_CONTEXT canonicality declaration (Track 1 resolution)
- `SESSION_CONTEXT.md` (repo root, shipped Sprint Z commit 3033555) — advisory proposal to review

**Pre-flight requirement**: Commit 1 CC:
1. Read Z-RETRO §6 (CAL evolution) + §10 (deviations — SESSION_CONTEXT canonicality flag)
2. Read each Week 7-9 sprint retro §"CAL items opened" + §"CAL closures" to compile shipped-but-open list
3. Verify staging dir exists for README/ROADMAP uploads: `ls /home/macro/projects/sonar-wt-day0-cleanup/docs/staging/ 2>/dev/null`
4. Inventory production DB files: `find /home/macro/projects/sonar-engine -name "sonar*.db" -o -name "*.db" | head -20`
5. Check CLAUDE.md §8 current wording
6. Decide SESSION_CONTEXT canonicality resolution (propose Option 2: remove repo-root file, keep Project Knowledge canonical, add `docs/status/` folder for phase snapshots)

Document pre-flight findings in Commit 1 body.

---

## 3. Concurrency — ISOLATED WORKTREE (solo)

**Day 0 operates in isolated worktree**: `/home/macro/projects/sonar-wt-day0-cleanup`

**Workflow**:
1. CC starts by `cd /home/macro/projects/sonar-wt-day0-cleanup`
2. All file operations happen in this worktree
3. Branch name: `cleanup-week10-day0`
4. Pushes to `origin/cleanup-week10-day0`
5. Final merge to main via fast-forward post-sprint-close

**File scope Day 0 (all Track branches)**:
- `README.md` MODIFY (Track 1)
- `docs/ROADMAP.md` MODIFY (Track 1)
- `SESSION_CONTEXT.md` DELETE or RELOCATE (Track 1, pending resolution decision)
- `CLAUDE.md` MODIFY if canonicality resolution requires (Track 1)
- `docs/backlog/calibration-tasks.md` MODIFY (Track 2 — heavy edits)
- `pyproject.toml` MAY MODIFY (Track 3 — pytest config for flaky marker if adopted)
- `tests/conftest.py` MAY MODIFY (Track 3 — flaky fixture)
- Specific test files with `@pytest.mark.flaky` decorator added (Track 3)
- `/etc/systemd/system/sonar-daily-curves.service` MODIFY ON VPS (Track 3 — comment only, not in repo)
- `scripts/ops/systemd_audit.sh` NEW (Track 3)
- `docs/planning/retrospectives/week8-sprint-i-*.md` NEW if gap (Track 4)
- `docs/planning/retrospectives/week7-sprint-g-*.md` NEW if gap (Track 4)

**No conflicts** — solo execution, no parallel sprint.

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-day0-cleanup && git pull origin main`

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only cleanup-week10-day0
git push origin main
```

---

## 4. Commits

### Commit 1 — Pre-flight audit + scope confirmation

```
chore(cleanup): Week 10 Day 0 pre-flight audit

Pre-flight findings (document in commit body):

1. Z-RETRO §6 CAL evolution review:
   - Week 9 start: 62 CAL items
   - Week 9 end (projected post-Y-DK): ~127 CAL items
   - CAL openings Week 9: country-specific (CA/AU/NZ/CH/SE/NO/DK * 5-8 each)
   - CAL closures Week 9: CAL-128, CAL-129, CAL-136 documented
   - Known gap: Week 7-8 closures not yet reflected

2. Shipped-but-open CAL candidates (Week 7-9):
   [LIST from retros — CC compiles]
   - CAL-057 (daily_erp_us dedicated pipeline) — Week 7 Sprint shipped
   - CAL-128 (UK→GB) — Week 9 Day 1 Sprint P shipped
   - CAL-128-FOLLOWUP (overlay/cycle sweep) — Week 9 Day 1 Sprint P shipped
   - CAL-129 partial (CA M1 live) — Week 9 Day 1 Sprint S-CA shipped
   - CAL-136 (BIS v2 migration) — Week 9 Day 2 Sprint AA shipped
   - Plus ~15-20 country-specific CALs closable with "shipped via Sprint X" references

3. Country-specific CAL dedup candidates:
   CAL-CA-M2-OUTPUT-GAP + CAL-AU-M2-OUTPUT-GAP + CAL-NZ-M2-OUTPUT-GAP +
   CAL-CH-M2-OUTPUT-GAP + CAL-SE-M2-OUTPUT-GAP + CAL-NO-M2-OUTPUT-GAP +
   CAL-DK-M2-OUTPUT-GAP
   → Consolidate as CAL-M2-T1-OUTPUT-GAP-EXPANSION (single item, T1-scoped)
   Similar for M3, M4, ERP-per-country

4. SESSION_CONTEXT canonicality state:
   - CLAUDE.md §8 declares: "canonical file external (Project Knowledge Claude chat)"
   - Sprint Z shipped `SESSION_CONTEXT.md` at repo root as advisory proposal
   - Conflict: in-repo file contradicts external-canonical declaration
   - Resolution decision: [Option 2 recommended — remove repo-root, keep Project Knowledge canonical, add docs/status/ for phase snapshots]

5. Production DB files on VPS:
   [LIST from find command]
   - /home/macro/projects/sonar-engine/sonar.db (0 bytes, orphan)
   - /home/macro/projects/sonar-engine/data/sonar.db (0 bytes, orphan — not actual production DB)
   - /home/macro/projects/sonar-engine/data/sonar-dev.db (0 bytes, orphan)
   - /home/macro/projects/sonar-engine/sonar_phase0.db (0 bytes, orphan)
   - [Actual production DB path per sonar health: TBD]

6. Flaky test triage:
   - Test-ordering issue documented Sprint V-CH/W-SE/X-NO/Y-DK retros
   - Passes in isolation, fails in full suite
   - Not a blocker for pre-push gate (pytest -x allows exit on failure; flaky would need @flaky retry logic)
   - Options: (a) fix root cause (ordering dependency unknown — investigative), (b) add @pytest.mark.flaky with pytest-rerunfailures plugin, (c) document as known issue in testing-strategy doc, no code change
   - Recommendation: Option (c) for Day 0 scope; (a) deferred Phase 2.5 quality sprint

7. Retro backfill check:
   - ls docs/planning/retrospectives/week8-*.md — [check output]
   - ls docs/planning/retrospectives/week7-sprint-g-*.md — [check output]
   - If gaps, produce minimal retrospectives referencing m1-us.md + m1-us-gap-analysis.md

This commit establishes audit findings. Subsequent commits execute tracks.
```

### Commit 2 — Track 1a: README consumer model revision

```
docs: consumer model revision — MCP/API + Website (Phase 3 reframe)

Major roadmap revision following consumer model clarification (2026-04-22):

Consumer A (MCP/API privado) + Consumer B (website sonar.hugocondesa.com):
- README "Quem usa" section → "Consumidores" with explicit Consumer A/B
- Principle 3 "Portugal-aware by design" → "Cross-country uniform coverage"
- Phase summary updated (Phase 1 COMPLETE, Phase 2 in progress, Phase 2.5 NEW, Phase 3 primary unlock, Phase 4 gated)
- Added coverage table (M2 T1 Core state Week 9)
- Removed Phase 5 dashboard + Phase 6 operationalization (conflated into Phase 3)

Apply README from staging:
  cp docs/staging/README.md README.md

Run pre-commit hooks (Day 4 lesson):
  uv run pre-commit run --all-files
  # If modifications, re-run to confirm clean

Verify:
  grep -c "Consumidores" README.md  # expect 1+
  grep "Phase 2.5" README.md  # expect at least 2 references
  grep "sonar.hugocondesa.com" README.md  # expect 1+
```

### Commit 3 — Track 1b: ROADMAP Phase 3 reframe

```
docs(roadmap): Phase 3 reframed around L7 API + Website launch

Phase 3 redesigned completely:
- Primary unlock milestone: L7 API + Website live
- Consumer A endpoints (MCP + REST) fully specified (9 endpoints)
- Consumer B website pages listed (Home, Cycles, Curves, Cost of capital, Matriz 4-way, Diagnostics, Methodology, Editorial)
- Shared infrastructure (deployment, monitoring, versioning)

Phase 2.5 NEW introduced:
- Bridge between Phase 2 horizontal completion and Phase 3 L7 launch
- Scope: L5 regimes, L6 integration, walk-forward backtests, T2 expansion, OpenAPI spec draft, L7 tech stack decisions

Phase 4 clarified:
- Calibration empirical gated by 24m production data
- Earliest 2028-Q2

Deprecated section:
- Editorial pipeline standalone (substituted by website)
- Alerts email + Telegram (pull model, defer Phase 4 conditional)
- Streamlit dashboard MVP (skip — direct Phase 3 website)
- PT Valuation Stack dedicated (T1 uniform covers PT)
- React dashboard interna (Phase 3 website is the dashboard)

Apply ROADMAP from staging:
  cp docs/staging/ROADMAP.md docs/ROADMAP.md

Pre-commit hooks + verify.

Próximos milestones numbered 1-8 ending at "Phase 3 gate — L7 API + Website live".
```

### Commit 4 — Track 1c: SESSION_CONTEXT canonicality resolution

```
docs(session): resolve SESSION_CONTEXT canonicality — remove repo-root advisory

Sprint Z-WEEK9-RETRO shipped SESSION_CONTEXT.md at repo root as advisory
proposal (§10 deviations). CLAUDE.md §8 declares canonical file external
(Project Knowledge Claude chat). Conflict resolved per Option 2:

1. Remove repo-root SESSION_CONTEXT.md:
   git rm SESSION_CONTEXT.md

2. Preserve historical value — create docs/status/ for phase snapshots:
   mkdir docs/status
   Move content inspiration to docs/status/week9-close-state.md as
   historical snapshot (NOT canonical session bridge, but reference for
   future phase closures).

3. Update CLAUDE.md §8 to explicitly declare:
   - Canonical: Project Knowledge (Claude chat) — live session bridge
   - Historical: docs/status/week{N}-close-state.md — per-phase snapshots
   - Rationale: external canonical avoids stale in-repo files (5-week
     staleness observed at Week 9 start); historical snapshots preserve
     phase transitions for retrospective reference.

4. Session continuity unchanged: Hugo updates Project Knowledge at phase
   closes via paste of Z-retro content. CC reads Project Knowledge via
   system prompt (always current).

Commit body references Sprint Z retro §10 for context.
```

### Commit 5 — Track 2a: CAL closures batch (Weeks 7-9 shipped items)

```
docs(backlog): CAL grooming — close Week 7-9 shipped items

Batch closure of CAL items shipped during Weeks 7-9 but not yet reflected
in calibration-tasks.md:

Status: done → with commit references

Week 7 (M1 US milestone close):
- CAL-057: daily_erp_us dedicated pipeline — shipped Week 7 Sprint G (SHA [lookup])
  Rationale: ERP composition lives in daily_cost_of_capital; dedicated
  pipeline not materialized but composite functional. Close as
  "done (via daily_cost_of_capital composition)".

Week 9 Day 1 — Sprint S-CA + P:
- CAL-128: UK→GB canonical chore — shipped Sprint P (SHA [lookup])
- CAL-128-FOLLOWUP: overlay/cycle UK→GB sweep — shipped Sprint P
- CAL-129 (partial): CA M1 live cascade — shipped Sprint S-CA

Week 9 Day 2 — Sprint AA + T-AU:
- CAL-136: BIS v2 API migration + lookback extension — shipped Sprint AA

Week 9 Day 3-5 — country sprints (AU/NZ/CH/SE/NO/DK):
Close country-specific CAL items that were resolved in sprint retros:
- CAL-CA-RIKSBANK-ANALOGUE (hypothetical example — check actual retro)
- [CC compiles from retros §"CAL closures"]

Format per closure:
  ### CAL-XXX — <title>
  - **Status**: done (shipped via Sprint <X>, commit <SHA>)
  - **Resolution**: <1-line summary>

Estimated closures: 15-20 items.
```

### Commit 6 — Track 2b: CAL deduplication batch

```
docs(backlog): CAL grooming — deduplicate country-specific items

Country-specific CAL items accumulate as country sprints ship. 7 country
additions Week 9 produce 7× M2 output-gap, 7× M3, 7× M4, etc CAL items
that describe identical gaps per country. Consolidate into generic items:

Consolidations:

CAL-M2-T1-OUTPUT-GAP-EXPANSION (NEW)
  Replaces: CAL-CA-M2-OUTPUT-GAP + CAL-AU-M2-OUTPUT-GAP +
            CAL-NZ-M2-OUTPUT-GAP + CAL-CH-M2-OUTPUT-GAP +
            CAL-SE-M2-OUTPUT-GAP + CAL-NO-M2-OUTPUT-GAP +
            CAL-DK-M2-OUTPUT-GAP
  Scope: OECD EO / Statistics offices output-gap connectors for 7 T1 countries
  Priority: MEDIUM (Phase 2 scope — T1 uniformity)

CAL-M3-T1-EXPANSION (NEW)
  Replaces: CAL-CA-M3 + CAL-AU-M3 + CAL-NZ-M3 + CAL-CH-M3 +
            CAL-SE-M3 + CAL-NO-M3 + CAL-DK-M3
  Scope: NSS forwards + expected-inflation persistence for 7 T1 countries
  Priority: MEDIUM (dependent CAL-138 curves multi-country)

CAL-M4-T1-FCI-EXPANSION (NEW)
  Replaces: CAL-CA-M4-FCI + CAL-AU-M4-FCI + CAL-NZ-M4-FCI +
            CAL-CH-M4-FCI + CAL-SE-M4-FCI + CAL-NO-M4-FCI + CAL-DK-M4-FCI
  Scope: VIX-per-country + credit-spread + NEER for 7 T1 countries
  Priority: LOW (Phase 2.5 scope)

CAL-ERP-T1-PER-COUNTRY (NEW, may already exist)
  Replaces: per-country ERP items if duplicated
  Scope: Replace MATURE_ERP_PROXY_US flag with per-market ERPInput assemblers
  Priority: HIGH (Phase 2 scope — listed in roadmap Phase 2 exit criteria)

CAL-ZLB-SHADOW-RATE (NEW, consolidation)
  Replaces: CAL-NEGATIVE-RATE-SHADOW (CH) + CAL-SE-NEGATIVE-RATE-SHADOW +
            CAL-DK-NEGATIVE-RATE-SHADOW-IF-ZLB-RETURNS + CAL-099 (Krippner)
  Scope: Krippner / Wu-Xia shadow-rate connector for ZLB M1 compute
  Priority: LOW (Phase 4 — no current ZLB countries binding)

Replaced items marked:
  ### CAL-XXX — <title>
  - **Status**: merged into CAL-YYY-T1-EXPANSION (see consolidated item)

Estimated new consolidated items: 5
Estimated removed country-specific items: ~30
Net CAL count: ~127 → ~100

Post-consolidation CAL breakdown by priority (to document in closing
commit):
- HIGH: ~8 items (CAL-138 curves, CAL-064, CAL-ERP-T1, etc.)
- MEDIUM: ~40 items (M2/M3/M4 expansions, BIS L3/L4, F-cycle)
- LOW: ~50 items (calibration refinements, scraper hardening, Phase 2.5+)
```

### Commit 7 — Track 2c: CAL re-categorization per roadmap revision

```
docs(backlog): CAL grooming — re-categorize per Phase 3 reframe

Roadmap revision deprecated several scope items (editorial pipeline, alerts,
Streamlit MVP, etc.). Existing CAL items tied to these scopes must be
re-categorized or marked deferred:

Deferred to Phase 4-conditional:
  CAL items related to email/Telegram alerts — mark "Phase 4 conditional
  on consumer demand"

Moved to Phase 3 scope (L7 API + Website):
  CAL items related to outputs/rendering/dashboard — consolidated as
  CAL-L7-API-ENDPOINTS (list of 9 MCP + REST endpoints)
  CAL-L7-WEBSITE-PAGES (list of 8 page categories)

Moved to Phase 2.5 scope (bridge):
  CAL items related to L5 regimes schema → CAL-L5-REGIME-TAXONOMY
  CAL items related to L6 integration → CAL-L6-MATRIZ-4WAY + CAL-L6-DIAGNOSTICS
  CAL items related to backtests → CAL-BACKTEST-HARNESS

Closed as deprecated (scope removed per roadmap revision):
  CAL items for Streamlit dashboard — close as "deprecated per ROADMAP revision 2026-04-22"
  CAL items for PT-vertical work — close as "deprecated per T1 uniform principle"
  CAL items for alerts MVP — close as "deprecated per pull-consumer model"

Add top-of-file note in calibration-tasks.md:
  "Last major revision: 2026-04-22 (Phase 3 reframe + country-CAL dedup).
   CAL items catalogued per 9-layer + Phase scope. See ROADMAP.md for
   phase definitions."

Estimate closures via deprecation: ~10 items
Estimate new consolidated items (L5/L6/L7/backtest): ~5-7 items
Final CAL count post-Track-2: ~80-90 items
```

### Commit 8 — Track 3a: flaky test documentation + DB orphan cleanup

```
chore: document known flaky test + cleanup orphan DB files

1. Flaky test documentation:
   - Add section to docs/testing-strategy.md (create if missing):
     "### Known flaky tests
     - test_pipelines/test_daily_monetary_indices.py::<specific test>:
       test-ordering dependency; passes in isolation, fails in full suite.
       Root cause unknown (investigative Phase 2.5).
       Workaround: pre-push gate uses pytest -x (exits on first failure);
       if flake surfaces, re-run full suite — stable on retry."
   - Do NOT add @pytest.mark.flaky (requires pytest-rerunfailures plugin;
     adds dependency; defer to Phase 2.5 quality sprint).

2. Orphan DB files cleanup (VPS, not in repo):
   Verify actual production DB path per sonar health:
     uv run sonar health | grep -i database OR grep DATABASE_URL .env

   Orphan 0-byte files to remove:
     /home/macro/projects/sonar-engine/sonar.db (orphan)
     /home/macro/projects/sonar-engine/sonar_phase0.db (legacy)
     /home/macro/projects/sonar-engine/data/sonar.db (if orphan)
     /home/macro/projects/sonar-engine/data/sonar-dev.db (orphan)

   Command (execute cautiously):
     cd /home/macro/projects/sonar-engine
     # Verify production DB (actual rows):
     sqlite3 <actual-prod-path> "SELECT COUNT(*) FROM alembic_version;" # sanity
     # Remove orphans (0-byte files only):
     for f in sonar.db sonar_phase0.db data/sonar-dev.db; do
       if [ -f "$f" ] && [ ! -s "$f" ]; then
         echo "Removing 0-byte orphan: $f"
         rm "$f"
       fi
     done

   Commit: only documentation change in repo; DB cleanup is VPS-side ops.

   Document in commit body:
     - Actual production DB path confirmed: [PATH]
     - Orphans removed: [LIST]
     - This cleanup is reversible (orphans 0-byte = no data lost)
```

### Commit 9 — Track 3b: systemd audit script + curves service cosmetic

```
chore(ops): systemd services audit script + curves service cosmetic

1. Create scripts/ops/systemd_audit.sh (reusable):

   #!/bin/bash
   # Audit all sonar-daily-*.service files for scope consistency
   # Usage: ./scripts/ops/systemd_audit.sh
   #
   # Reports: ExecStart line per service, flags any --country-hardcoded entries
   #          that should use --all-t1 (pattern revealed Week 9 Day 4 CAL-138)

   echo "=== Sonar systemd services audit ==="
   echo "Date: $(date -u -I)"
   echo ""

   for f in /etc/systemd/system/sonar-daily-*.service; do
       name=$(basename "$f" .service)
       exec=$(grep "^ExecStart" "$f" | sed 's/ExecStart=//')
       flag="✓"
       if echo "$exec" | grep -q "\-\-country US"; then
           flag="⚠️ HARDCODED US"
       fi
       if echo "$exec" | grep -q "\-\-all-t1"; then
           flag="✓ T1"
       fi
       echo "[$flag] $name"
       echo "    $exec"
   done

   echo ""
   echo "Services with --country US hardcoded require update per CAL-138."

   chmod +x scripts/ops/systemd_audit.sh

2. curves service cosmetic (optional; documentation only):
   Current /etc/systemd/system/sonar-daily-curves.service comment:
     # Phase 1 ships US only; daily_curves requires a single --country and --date.

   Updated comment (VPS-side, not in repo):
     # Phase 1 Week 2 scope — US only. T1 expansion pending CAL-138
     # (daily_curves multi-country support). Until CAL-138 resolves,
     # service must use --country US; --all-t1 will fail (CLI rejection).

   VPS command:
     sudo sed -i 's|# Phase 1 ships US only; daily_curves requires.*|# Phase 1 Week 2 scope — US only. T1 expansion pending CAL-138.|' /etc/systemd/system/sonar-daily-curves.service
     sudo systemctl daemon-reload

   Commit body: documents VPS-side change; repo only gets systemd_audit.sh.

3. Weekly canary decision:
   CAL-137 BIS v2 surveillance — defer to CAL-138 sprint Day 1 (embed
   weekly canary wiring as part of curves multi-country sprint scope).
   No action Day 0.
```

### Commit 10 — Track 4: retro backfill check

```
docs(planning): retro backfill check — Week 7 Sprint G + Week 8 Sprint I

Verify retrospective coverage for M1 US milestone close (Week 7 Sprint G)
and M2 T1 kickoff (Week 8 Sprint I):

1. Sprint I Week 8 (UK/GB + JP shipped):
   ls docs/planning/retrospectives/week8-*.md

   Expected:
   - week8-sprint-i-uk-canonical-report.md OR similar
   - week8-sprint-j-jp-partial-report.md OR similar

   If gap: produce minimal backfill retrospective referencing:
     - Sprint I commits (git log --oneline --grep="UK\|GB" --since="2026-04-18" --until="2026-04-21")
     - CAL items opened (CAL-128, CAL-128-FOLLOWUP, JP-specific items)
     - Live canary outcomes
     - Brief summary per sprint structure

2. Sprint G Week 7 (M1 US milestone close):
   ls docs/planning/retrospectives/week7-sprint-g-*.md

   Expected:
   - week7-sprint-g-m1-us-close-report.md OR similar

   If gap: m1-us.md + m1-us-gap-analysis.md may serve as milestone artifacts;
   document this rationale in a minimal retrospective index entry:

   docs/planning/retrospectives/week7-m1-us-milestone-note.md (NEW if needed):
   "# Week 7 Sprint G — M1 US Milestone Close (Note)

   Formal retrospective not produced per sprint pattern. Milestone artifacts
   serve as closure:
   - docs/milestones/m1-us.md — scorecard + coverage matrix + CLI quickstart
   - docs/milestones/m1-us-gap-analysis.md — spec-vs-implementation deltas (62 CAL items, 21 closed, 41 open)

   Future phase closures follow this pattern: milestone doc primary,
   retrospective secondary."

3. Update docs/planning/retrospectives/README.md index if backfills produced.

Estimated output: 0-2 new retrospective files + README index update.
```

---

## 5. HALT triggers (atomic)

0. **README/ROADMAP upload missing** — if /mnt/user-data/outputs files not scp'd to VPS before Commit 2, HALT + surface. Request Hugo upload.
1. **CAL state divergence** — if Z-RETRO §6 CAL count (~127) doesn't match `grep -c "^### CAL-" docs/backlog/calibration-tasks.md`, HALT + investigate.
2. **SESSION_CONTEXT canonicality** — resolution decision is Hugo-level strategic; if Option 2 (remove repo-root) is ambiguous, propose in Commit 4 body + surface to Hugo. Do NOT silently delete.
3. **CAL consolidation aggressive** — if country-specific items have content that doesn't merge cleanly into generic (e.g., country-specific notes, calibration values), preserve as sub-bullets in consolidated item. HALT and surface if uncertain.
4. **Retro backfill scope creep** — if Week 7/8 retros missing and backfill requires more than documented structure, do NOT write full retrospective content. Produce minimal "milestone artifact note" only.
5. **Production DB cleanup uncertain** — if actual production DB path unclear, do NOT remove any files. Document state + defer.
6. **Coverage regression N/A** — Day 0 has no code changes.
7. **Pre-push gate** — docs-only commits skip ruff/mypy; whitespace + conventional commit hooks active. Pre-fix workflow: `uv run pre-commit run --all-files` BEFORE `git commit` (Day 4 lesson).
8. **No --no-verify** — standard discipline.
9. **CLAUDE.md §8 wording change** — if canonicality resolution requires CLAUDE.md edit, HALT and surface proposed wording to Hugo before commit.
10. **Deprecated CAL closures** — if any deprecated CAL has open dependencies (e.g., someone else's work blocks), do NOT close; re-categorize instead.
11. **systemd audit script execution** — script is commit artifact only; do NOT run on VPS from CC session. Hugo runs manually post-merge.

---

## 6. Acceptance

### Global sprint-end
- [ ] README.md applied with consumer model revision (Consumer A + B explicit)
- [ ] ROADMAP.md applied with Phase 3 reframe + Phase 2.5 NEW + deprecations
- [ ] SESSION_CONTEXT canonicality resolved (repo-root file removed OR explicit retention decision)
- [ ] CLAUDE.md §8 updated if canonicality resolution required
- [ ] CAL-057 + CAL-128 + CAL-128-FOLLOWUP + CAL-129 + CAL-136 closed with commit refs
- [ ] ~15-20 Week 9 country-specific CAL items closed (M1 live for country X)
- [ ] ~5 country-specific CAL consolidations into generic items (M2/M3/M4/ERP/ZLB)
- [ ] ~10 deprecated CAL items closed (scope removed per roadmap revision)
- [ ] CAL total reduced: ~127 → ~80-90
- [ ] Flaky test documented in testing-strategy.md
- [ ] Production DB orphans removed on VPS (if safely identifiable)
- [ ] systemd_audit.sh committed + executable
- [ ] curves service comment updated VPS-side (cosmetic)
- [ ] Retro backfill check executed (gaps produced OR documented as milestone-artifact-sufficient)
- [ ] docs/planning/retrospectives/README.md index updated if backfills produced
- [ ] 6-10 commits pushed to branch `cleanup-week10-day0`
- [ ] No `--no-verify`
- [ ] Pre-push gate green (docs-only: whitespace + conventional commit)

---

## 7. Report-back artifact

No standalone retrospective file — Day 0 is cleanup/consolidation, not feature sprint.

**Final tmux echo**:
```
WEEK 10 DAY 0 CLEANUP DONE: N commits on branch cleanup-week10-day0

Track 1 (strategic docs): README + ROADMAP revised; SESSION_CONTEXT canonicality resolved via [Option X]
Track 2 (CAL grooming): CAL ~127 → ~[N]; closed [X] shipped, deduplicated [Y] country-specific, deprecated [Z] scope-removed
Track 3 (cleanup): flaky test documented; DB orphans removed ([N] files); systemd_audit.sh shipped
Track 4 (retro backfill): [gaps produced / milestone-artifact-sufficient documented]

CAL breakdown post-cleanup:
- HIGH: [N] items
- MEDIUM: [N] items
- LOW: [N] items

Merge: git checkout main && git merge --ff-only cleanup-week10-day0
Post-merge: Day 1 Sprint CAL-138 curves multi-country ready
```

---

## 8. Pre-push gate (mandatory)

For docs-only commits:
```
uv run pre-commit run --all-files
```

Hooks active:
- trim trailing whitespace
- fix end of files
- check yaml / toml / json (as applicable)
- check for merge conflicts
- detect secrets / gitleaks
- Conventional Commit format

Ruff / mypy skipped (no Python changes except potentially conftest.py — if modified, full gate).

**No --no-verify**. Pre-fix workflow per Day 4 lesson:
```
uv run pre-commit run --all-files  # apply auto-fixes
uv run pre-commit run --all-files  # confirm clean
git add -A
git commit -F /tmp/commit-msg.txt
```

---

## 9. Notes on implementation

### Discipline-intensive work
Day 0 is primarily **reading + synthesis + consistent writing**. No feature logic. Quality risk is **inconsistency** between CAL closures and shipped reality, or between README/ROADMAP claims and engine state. Cross-check each claim against retros + commits.

### Pre-commit hook fatigue
Day 4 revealed pre-commit hook rollback pattern. Day 0 has ~10 commits — apply `uv run pre-commit run --all-files` **twice** before commit sequence starts, then once before each commit. Avoids rollback.

### Solo execution rationale
Cleanup work benefits from consistent voice + cross-referencing. Parallel would fragment. CC solo reads all retros sequentially, builds mental model, then writes consolidated updates.

### SESSION_CONTEXT decision
Option 2 (repo-root removal + docs/status/ historical snapshots) recommended because:
- CLAUDE.md §8 already declares external canonical
- In-repo file at root creates confusion (CC instances may read stale)
- Historical snapshots add value without canonicality burden
- Hugo maintains Project Knowledge in Claude chat (single source of truth)

If Hugo prefers Option 1 (adopt in-repo as canonical + update CLAUDE.md), CC produces alternative Commit 4 + CLAUDE.md update reflecting choice.

### CAL deduplication risk
Aggressive consolidation may lose country-specific context (e.g., DK negative-rate era dates 2015-07..2022-09 differ from CH 2014-12..2022-08). Preserve as sub-bullets in consolidated items when content differs materially.

### Deprecation vs deletion
Deprecated CAL items are closed with status "deprecated per ROADMAP revision 2026-04-22", NOT deleted. Preserve historical reference for future contributors (even if solo operator, context matters for Phase 3+ when external consumers read backlog).

### Commit granularity
10 commits for 4 tracks = 2-3 commits per track. Allows:
- Selective rollback if issue found
- Clear git log narrative (Commit 2 = README, Commit 3 = ROADMAP, etc.)
- Per-track report-back granularity

### Isolated worktree workflow
Day 0 operates entirely in `/home/macro/projects/sonar-wt-day0-cleanup`. Branch: `cleanup-week10-day0`. Solo, no merge conflicts expected.

### Week 10 Day 1 follow-on
Post-merge, Day 1 starts Sprint CAL-138 curves multi-country. Brief for Day 1 produced separately (Hugo or CC).

---

*End of Week 10 Day 0 cleanup brief. 6-10 commits. Strategic alignment + tech debt reduction + groomed CAL backlog. Ready for Week 10 Day 1 Sprint CAL-138 arranque.*
