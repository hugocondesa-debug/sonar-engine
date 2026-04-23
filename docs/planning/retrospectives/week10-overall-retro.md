# Week 10 Retrospective — Machine Hardening Week

**Data**: 2026-04-23 Day 3 close (~19:30 WEST scope)
**Author**: Hugo Condesa (chat reviewer) + CC (co-author)
**Weeks prior**: Week 9 (effective rates M1 completion)
**Weeks next**: Week 11 (curves remaining + E indices + L4 composites)

---

## 1. Executive summary

Week 10 shipped **15 sprints** over 3 days, advancing T1 completion from ~32% to ~54% (**+22pp**). Beyond raw velocity, Week 10 canonicalised **4 ADRs** (0009 v2, 0010, 0011 base + 0011 Principle 6 amendment) that encode governance discipline learned through empirical probe cycles and systemd failure analysis. Day 3 inverted narrative — Days 1-2 were pure expansion (13 sprints), Day 3 was **foundation hardening** (2 prod-healing sprints T0 + T0.1) after natural fires exposed partial-persist + async event-loop defects that had been latent since Week 9 service enablement.

Net assessment: Week 10 is the **strategic moat week** — velocity preserved, machine discipline elevated, prod fundação healthy for Week 11 ritmo.

### Key metrics

| Metric | Week 9 close | Week 10 close | Delta |
|---|---|---|---|
| T1 completion | ~32% | ~54% | **+22pp** |
| L0 connectors | ~60% | ~75% | +15pp |
| L3 M-indices FULL | M1 16/16 | M1 16/16, M2 11/16, M3 4/16, M4 8/17 | M2/M3/M4 activated |
| L3 curves T1 | 8/16 | 9/16 | +1 (FR) |
| ADRs canónicos | 0008 | 0008 + 0009v2 + 0010 + 0011 + 0011.P6 | +3 ADRs + 1 amendment |
| Services systemd green | 3/3 untested | 3/3 verified | +verification discipline |
| Pre-commit test count | ~55 (estimate) | 81+ pipelines scope | +26+ tests |

### Sprints shipped

| Day | Date | Count | Sprint IDs |
|---|---|---|---|
| Day 1 | 2026-04-21 | 6 | Infrastructure + CAL-138 + A + B + C + D |
| Day 2 | 2026-04-22 | 7 | E + F + G + H + L + I + J |
| Day 3 | 2026-04-23 | 2 | T0 + T0.1 |
| **Total** | — | **15** | — |

---

## 2. Lessons identified and disposition

Six lessons emerged through Days 1-3. Each is classified by disposition: **Shipped** (fix merged Week 10), **Shipping Day 3 close** (retro bundle), **Deferred** (Week 11+).

### Lesson #1 — Brief upload via scp manual fix (6 occurrences)

**Pattern**: Day 1+2 each sprint required manual `scp ~/Downloads/*.md macro@...:/docs/planning/` + `cp` to worktree. Operator burden ~2min/sprint × 13 sprints = ~25min cumulative, plus context switches.

**Root cause**: `scripts/ops/sprint_setup.sh` creates worktree from main HEAD; if brief not yet in main at setup time, worktree has no brief. Operator must copy manually.

**Fix permanent shipped Day 3**: `sprint_setup.sh` amendment — pre-flight check verify `docs/planning/<sprint-id>-brief.md` exists in main **before** worktree creation. If missing, abort with clear message. Additionally, `--brief-path <path>` optional flag to auto-`cp` brief into worktree post-setup if brief in main is at different path than convention.

**Disposition**: ✅ **Shipped Day 3 R1 bundle** (`scripts/ops/sprint_setup.sh`)

### Lesson #2 — Pre-commit rollback (6 occurrences)

**Pattern**: `git commit` rejected by pre-commit hooks that auto-fix whitespace/EOL/import ordering. First run fixes files, commit fails. Second run passes because files already fixed. Operator burden small but cognitive tax.

**Root cause**: pre-commit hooks mutate file content then exit non-zero. Commit machinery sees non-zero + staged state is stale. Second commit picks up fixes.

**Fix permanent (soft-shipped Week 10)**: Operator discipline — run `uv run pre-commit run --all-files` **twice** before `git commit`. Second run is idempotent pass. Verified pattern Sprint I onwards.

**Disposition**: 🟡 **Formalized in brief format v3 template amendment** (Day 3 R1 bundle — optional append to `docs/planning/brief-format-v3.md` §7 execution notes).

### Lesson #3 — Sprint G TE omission → suboptimal HALT-0

**Pattern**: Sprint G brief §2 pre-flight probe list missed TE as Path 1 for Brazil connector probe. CC went direct to Banco Central do Brasil (Path 3). When that failed, suboptimal HALT-0 — should have been HALT-0 on TE probe before trying Path 3.

**Root cause**: brief author (chat) omitted TE line. Discipline gap.

**Fix permanent shipped Day 2**: **ADR-0009 v2** — TE Path 1 mandatory for any country-data probe. Brief format v3 amendment — §2 must include "TE probe mandatory" line for country-data sprints. Sprint I FR validated v2 empirically (3rd HALT-0 inversion confirmed).

**Disposition**: ✅ **Shipped Week 10 Day 2** (ADR-0009 v2 + brief format v3 convention)

### Lesson #4 — tmux session orphan post-merge

**Pattern**: `sprint_merge.sh` removes worktree but leaves tmux session associated with worktree alive. Session becomes orphan pointing to non-existent path. Accumulates across sprints. Day 3 morning verification found 2 orphan sessions from Day 2 still alive.

**Root cause**: `sprint_merge.sh` Step 10 cleanup only handles git worktree removal, not tmux session kill.

**Fix permanent shipped Day 3**: `sprint_merge.sh` Step 10 amendment — detect tmux session name convention `sprint-<sprint-id>` and `tmux kill-session -t <name>` if exists. Graceful handling if session not found (no-op).

**Disposition**: ✅ **Shipped Day 3 R1 bundle** (`scripts/ops/sprint_merge.sh`)

### Lesson #5 — CC crash post-merge CWD stranding (recurring)

**Pattern**: After `sprint_merge.sh` removes worktree, CC's Bash tool retains CWD = deleted worktree path. Subsequent bash calls blocked with "no such directory" errors until CC restarts. Recurred in Sprint T0 post-merge (Day 3 afternoon).

**Root cause**: CC Bash tool persists CWD across tool calls; post-merge worktree removal invalidates it. CC has no automatic CWD verification.

**Fix permanent shipped Day 3**: New `docs/templates/cc-arranque-prompt.md` — canonical CC startup prompt template with mandatory header:

```
Before any other action, verify working directory:
cd /absolute/path/to/worktree && pwd

If the directory doesn't exist, STOP and report. Do not create it.
```

Operator applies template for all sprint arranques. Prevents CWD stranding + forces CC to assert-then-operate on valid path.

**Disposition**: ✅ **Shipped Day 3 R1 bundle** (`docs/templates/cc-arranque-prompt.md`)

### Lesson #6 — Partial-persist + non-idempotent retry (new Day 3 discovery)

**Pattern**: Overnight Apr 23, 3 services failed. Root cause: `daily_curves` Run 1 persisted US successfully, crashed mid-pipeline on transient HTTPStatusError before IT/ES/FR/PT/NL. Run 2 (systemd restart) recommeçou do início → `UNIQUE(country_code, date, methodology_version)` violation on US → exit 3 → cascade to monetary + cost-of-capital.

**Root cause**: Pipeline did not implement idempotency at row-level. Retry semantics assumed full-batch atomicity where actual is per-row. Plus: per-country failures were fatal, not isolated.

**Fix permanent shipped Day 3**: **ADR-0011** (Systemd Service Idempotency — 5 principles) + Sprint T0 refactor of `daily_curves`, `daily_monetary_indices`, `daily_cost_of_capital`. Row-level idempotent pre-check. Per-country try/except isolation. Exit code sanitization.

**Disposition**: ✅ **Shipped Day 3 Sprint T0**

### Lesson #7 — CC acceptance gap: local CLI vs systemd invocation (new Day 3 discovery)

**Pattern**: Sprint T0 CC reported "3 services exit 0" and claimed shipped. Operator manual verification via `sudo systemctl start sonar-daily-monetary-indices.service` revealed **failed** — exit 1, restart loop. Discrepancy: CC tested via `uv run python -m sonar.pipelines.daily_monetary_indices` (direct CLI), systemd invokes via `bash -lc 'uv run python -m ...'`. Wrapper alters shell env, CWD context, async event-loop initialization. Bug (`Event loop is closed`) manifested only in systemd path.

**Root cause**: CC acceptance criteria in brief §5 was ambiguous — "exit 0" not qualified as local OR systemd. Default CC interpretation was local (cheaper). Systemd is the **actual** production path (natural fires run via timer → service → bash wrapper).

**Fix permanent shipped Day 3**: Brief format v3 §5 Acceptance template amendment — if deliverable affects code that runs via systemd service, acceptance MUST include `systemctl is-active <service>` + `journalctl -u <service> --since` verification clauses. Operator rejects CC "shipped" without systemd verification pour les pipelines concernées.

Sprint T0.1 immediately demonstrated fix — brief §2.7 + §5 explicitly require systemd invocation, and §6 retro calls out the T0 gap.

**Disposition**: ✅ **Shipped Day 3 R1 bundle** (brief format v3 amendment)

### Lesson #8 — TE quota surprise (new Day 3 discovery)

**Pattern**: Day 3 ~17:30 WEST, operator probe TE returned HTTP 403 "exceeded API subscription limit". Panic moment. Dashboard check revealed actual status: 23.32% / 5000 consumption April. False positive — 403 likely transient burst rate-limit, not monthly quota exceeded. Misleading error message from TE.

**Root cause**: SONAR has zero telemetry on TE quota state. Operator reacts to single 403 probe without context. Misread error message caused ~15min planning churn (Sprint M blocked decision).

**Fix permanent deferred**: `CAL-TE-QUOTA-TELEMETRY` — daily HEAD request to TE quota endpoint, persist to `connector_quota_telemetry` table, alert if <20% remaining OR if 403 rate observed > baseline. Budget 2-3h scoped sprint. Not critical Week 10, but valuable Phase 2.5 observability.

**Disposition**: 📋 **Deferred** — CAL opened, scope Week 11+ non-urgent

---

## 3. ADRs shipped Week 10

| ADR | Title | Day | Principle summary |
|---|---|---|---|
| **0009 v2** | National CB connectors EA periphery — TE Path 1 mandatory | Day 2 (Sprint H + I validation) | Any country-data probe MUST try TE first before national CB/stat office fallback. Empirical probe-before-scaffold discipline. |
| **0010** | T1 complete before T2 expansion | Day 2 (Sprint F/L scope lock) | Phase 2-4 T1 ONLY (16 countries). T2 Phase 5+ earliest Q3 2027. Prevent premature horizontal expansion. |
| **0011** | Systemd service idempotency (Principles 1-5) | Day 3 (Sprint T0) | Row-level idempotency, per-country isolation, exit code sanitization, summary emit, partial-persist recovery. |
| **0011 Principle 6** | Async lifecycle discipline (amendment) | Day 3 (Sprint T0.1) | Single `asyncio.run()` at process entry, connectors via `AsyncExitStack` + `async with` context. |

---

## 4. Phase 2 trajectory update

### State at Week 10 close

- **T1 completion**: ~54%
- **L0 connectors**: ~75% (25+ shipped)
- **L1 DB**: ~95%
- **L2 overlays**: ~70%
- **L3 indices M1**: 16/16 ✓
- **L3 indices M2**: 11/16 FULL (US + EA + 9 non-EA T1)
- **L3 indices M3**: 4/16 (US/DE/EA/PT — builder-only pattern confirmed)
- **L3 indices M4**: 8/17 FULL (US + EA + DE + FR + IT + ES + NL + PT) + 9/17 scaffold
- **L3 indices E1/E3/E4**: 0/16 each (pending)
- **L3 indices Credit L1-L4**: 4/4 ✓
- **L3 indices Financial F1-F4**: 4/4 ✓ (degraded)
- **L4 cycles**: 4/4 US only
- **L5 regime**: 0% (Phase 2.5)
- **L6 integration**: 0% (Phase 2.5+)
- **L7 outputs**: 0% (Phase 3)

### Target Phase 2 close (fim Maio 2026, ~4-5 weeks)

- T1 completion: 75-80%
- L2 uniform (curves 13+/16)
- L3 T1 majority across M1/M2/M3/M4 (10+/16 each)
- L4 composites cross-country (4+ countries with all M-indices FULL)
- L3 E1/E3/E4 coverage initiated

### Velocity analysis

- Week 10 shipped +22pp over 3 days (13 expansion + 2 hardening)
- Target Week 11-14 pace: +5-7pp per week sustained
- Buffer: Week 10 exceeded weekly target by ~2×; **ahead of schedule meaningfully**
- Week 11 scope priority: remaining curves (PT + NL + 6 sparse T1 probes), M3 expansion, E1/E3/E4 start, L4 MSC cross-country

### Phase 2.5 + Phase 3 horizon

- **Phase 2.5 Bridge** (L5 regime + L6 integration): Q2-Q3 2026
- **Phase 3 primary unlock** (L7 API + sonar.hugocondesa.com): Q4 2026 - Q1 2027
- **T1 product complete 100%**: Q1 2027 consistent projection

---

## 5. Machine discipline assessment

### Strengths validated Week 10

- **Brief format v3** (13+ sprints executed clean) — minimalist template works, scales.
- **HALT triggers saved wasted work** — conservative estimate 10-12h wasted work avoided across Week 10 via HALT-0 / HALT-material inversions.
- **Paralelo pairs** — Day 2 proved 7 sprints shipped via zero-overlap pair pattern. Foundation for Phase 2 velocity.
- **Reviewer role (Hugo chat-side)** — caught brief gaps (Lesson #3), pushed back on false TE "exhausted" claim, verified acceptance gaps (Lesson #7). Critical safety net.

### Gaps consolidated Week 10

- Lesson #1-#5 + #7: all **shipped** as permanent fixes Day 3 R1 bundle
- Lesson #6: shipped ADR-0011 Sprint T0
- Lesson #8: deferred with CAL opened

### Pattern for Week 11+

- Apply brief format v3 with §2 TE probe + §5 systemd verification (both new conventions) uniformly
- Use CC arranque prompt template (new) for all CC sessions
- Monitor TE quota dashboard weekly (Hugo operator-side) until CAL-TE-QUOTA-TELEMETRY shipped
- Maintain 2-3 sprints/day sustainable pace; avoid Day 2 overnight heroism replication
- Fresh Hugo morning = best reviewer output; CC executor afternoon+

---

## 6. Retro action items

| # | Item | Owner | Disposition |
|---|---|---|---|
| A1 | `sprint_setup.sh` brief pre-flight check | CC (or operator) | Day 3 R1 ✅ |
| A2 | `sprint_merge.sh` Step 10 tmux kill | CC (or operator) | Day 3 R1 ✅ |
| A3 | CC arranque prompt template | Operator | Day 3 R1 ✅ |
| A4 | Brief format v3 §5 systemd clause | Operator | Day 3 R1 ✅ |
| A5 | Brief format v3 §2 TE probe line (ADR-0009 v2 formalize) | Operator | Week 10 Day 2 ✅ |
| A6 | `CAL-TE-QUOTA-TELEMETRY` | Deferred | Week 11+ 📋 |
| A7 | SESSION_CONTEXT.md schema naming fix | Operator | Day 3 close (pending) 🟡 |
| A8 | Week 11 brief + arranque plan (Sprint M + O) | Operator | Day 4 manhã 📋 |

---

## 7. Closing

Week 10 transitioned SONAR from "velocity-tested" to "machine-proven". Foundation hardening via ADR-0011 + permanent fixes means Week 11 executes on healthier substrate. Net: velocity preserved, discipline elevated, Phase 2 fim Maio 2026 on track with buffer.

Ship sustainable. Next: Day 4 manhã fresh → Sprint M (curves PT+NL probe) + Sprint O (M3 expansion) paralelo per original Day 3 plan.

---

*End of retro. 15 sprints, 4 ADRs, 8 lessons (7 shipped). Compound foundation effect for Week 11.*
