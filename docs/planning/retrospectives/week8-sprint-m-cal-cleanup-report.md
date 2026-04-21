# Week 8 Sprint M — CAL Cleanup (Trimmed)

**Brief:** `docs/planning/week8-sprint-m-cal-cleanup-brief.md`
**Duration:** ~1.75h (2026-04-21)
**Commits:** 5 shipped + retrospective (sprint8-M c1–c6)
**Branch:** `sprint-m-cal-cleanup` (isolated worktree)
**Status:** SPRINT CLOSED — 2 CAL closures; merge-to-main pending operator action

---

## 1. Summary

Two technical-debt items closed in a single session, both in an
isolated worktree so Sprint N could run deploy/systemd work
concurrently without any collision risk.

- **CAL-backfill-l5** — CLOSED. `src/sonar/scripts/backfill_l5.py`
  walks the four L4 cycle tables, skips any date that already has an
  ``l5_meta_regimes`` row, classifies via `MetaRegimeClassifier`, and
  persists via `persist_l5_meta_regime_result`. Idempotent by
  construction; dry-run default.
- **CAL-113 BEI/SURVEY split** — CLOSED. The EXPINF emitter
  (`daily_overlays._compute_expected_inflation`) now carries three
  new `sub_indicators` keys alongside the unified canonical dict;
  the M3 DB-backed consumer (`build_m3_inputs_from_db`) reads them
  distinctly while falling back to legacy behaviour for pre-Sprint-M
  rows.

Both CALs formalised in `docs/backlog/calibration-tasks.md` with full
Priority / Trigger / Scope / Dependency / Status fields.

## 2. Commits

| # | SHA | Title | Gate |
|---|-----|-------|------|
| 1 | `279dbbf` | docs(backlog): formalize CAL-backfill-l5 + CAL-113 | green |
| 2 | `c62b468` | feat(scripts): backfill_l5.py L5 retroactive classification | green |
| 3 | `fb85517` | feat(pipelines): BEI/SURVEY split in EXPINF sub_indicators | green |
| 4 | `1bfe4b7` | feat(indices): M3 DB-backed consumer reads BEI/SURVEY split | green |
| 5 | `33d5db6` | test(integration): backfill_l5 + CAL-113 round-trip smoke | green |
| 6 | _this doc_ | docs(planning): retrospective | pending |

Pre-push gate (ruff format + ruff check + detect-secrets + mypy
109 src files + conventional-commit lint) green on every push. No
`--no-verify`.

## 3. Pre-flight findings (Commit 1)

- `retention.py` (Sprint G) — mature Typer CLI pattern with
  dry-run/--execute toggle and SessionLocal lifecycle. Replicated
  verbatim in `backfill_l5.py`.
- `assemblers.py` (Sprint K) — only shipped
  `build_l5_inputs_from_cycles_result(CyclesOrchestrationResult)`. A
  snapshot-based sibling was missing; Commit 2 added
  `build_l5_inputs_from_snapshots(...)` plus four
  `build_*_snapshot_from_orm` helpers that read persisted cycle rows
  directly.
- `_compute_expected_inflation` — unified `expected_inflation_tenors`
  key only; `source_method_per_tenor` already contained the
  method-per-tenor information so the split emitter is a pure
  augmentation.
- `build_m3_inputs_from_db` — comment at lines 212-215 explicitly
  flagged the gap: `survey_10y_bps` forced to `None` "so the compute
  module flags BEI_SURVEY_DIVERGENCE_UNAVAILABLE rather than
  overreporting". Sprint M closes that gap.
- `M3Inputs` dataclass already carries `bei_10y_bps` + `survey_10y_bps`
  as optional fields, so CAL-113 was pure emitter+consumer work
  without a schema change.

## 4. Tests shipped

| File | New tests | Focus |
|------|-----------|-------|
| `test_scripts/test_backfill_l5.py` | 10 | iter_classifiable_triplets (4) + backfill_country (4) + constants (2) |
| `test_pipelines/test_daily_overlays.py` | +2 | split emitted in sub_indicators + method_per_tenor mirrors legacy key |
| `test_indices/monetary/test_db_backed_builder.py` | +4 | BEI-only / SURVEY-only / both split / backward-compat legacy row |
| `test_integration/test_backfill_l5.py` | 7 | happy path + dry-run + idempotent + from_date + insufficient + multi-country |
| `test_integration/test_cal_113_round_trip.py` | 2 | emitter → consumer round-trip + backward-compat |

Total: 25 new tests, all green.

## 5. HALT triggers

9 triggers atomic; none fired:

| # | Trigger | Fired | Notes |
|---|---------|-------|-------|
| 0 | Missing snapshot-based assembler helper | — | `build_l5_inputs_from_snapshots` + 4 ORM→Snapshot helpers added to `assemblers.py` in Commit 2 |
| 1 | EXPINF `sub_indicators` schema surprise | — | Existing keys preserved; three new keys added additively |
| 2 | `M3Inputs` missing `bei_10y_bps`/`survey_10y_bps` | — | Fields already present (optional) |
| 3 | Backward-compat break | — | Dedicated test (`test_legacy_row_without_split_backward_compat`) asserts pre-Sprint-M rows still parse |
| 4 | Cycle ORM date-semantics mismatch | — | Iterator uses exact `date` equality, no month-end / business-day translation needed |
| 5 | Script CLI integration | — | Script is module-level Typer app (`python -m sonar.scripts.backfill_l5`) matching `retention.py` convention |
| 6 | Coverage regression > 3pp | — | Added modules coverage ≥ 85 % (backfill_l5.py) / ≥ 90 % (BEI split additions) |
| 7 | Pre-push gate fails | — | Full mypy green on 109 src files every push |
| 8 | Sprint N file overlap | — | Zero. Sprint N touches `deploy/systemd/*` + `CLAUDE.md`; no intersection. |

## 6. Isolated-worktree experience

This was the first sprint run entirely in a dedicated git worktree
(`/home/macro/projects/sonar-wt-sprint-m` on branch
`sprint-m-cal-cleanup`). Observations:

**Wins**:

- Zero pre-commit stash/pop interactions with the other worktree.
  Earlier sprints (Sprint K C3, for example) had commit-scope tangles
  because Sprint I-patch's unstaged files ended up in the stash that
  the hook was popping. Isolated branches make that impossible.
- Pushes go to a dedicated upstream branch
  (`origin/sprint-m-cal-cleanup`), so there's no race with Sprint N's
  `main` pushes.
- The worktree naturally enforces the file-scope contract in the
  brief §3 — there's no way to accidentally edit a Sprint N file
  from this shell.

**Costs**:

- One-time setup overhead: first `uv run` in the worktree triggered
  a full venv build (~120 ms) plus a full `uv sync --all-extras`.
- `.env` is gitignored; had to `cp` it from the main checkout so
  pydantic-settings would accept the config.
- Final merge is a manual operator action (not part of the sprint);
  the retrospective §8 documents the exact command.

**Recommendation**: adopt worktree isolation as the default for any
two-or-more-way parallel sprint going forward. The one-time setup
cost is amortised across all commits and eliminates the recurring
stash-pop tangle risk.

## 7. Backlog state (roughly)

Pre-Sprint M: ~41 items tracked across the backlog (with CAL-053
through CAL-108 + some legacy IDs). Post-Sprint M: 2 explicit
closures (CAL-backfill-l5 + CAL-113). Items marked CLOSED in the
backlog now carry the sprint + date breadcrumb.

Remaining in-flight CALs noted as Sprint M follow-ups:

- **CAL-128** (GB vs UK canonical rename) — deferred to dedicated
  sprint. Affects TE mappings, bc_targets, connector boundary, and
  the UK M1 builder; too pervasive to co-mix with CAL cleanup.
- **CAL-114** (dedicated CRP/EXPINF ORM tables) — deferred Phase 2+.
  Current `index_values` + `sub_indicators_json` workaround is
  functional; a dedicated migration needs the consumer rewrites that
  would dominate the sprint.
- **CAL-125/126/127** (UK M2/M3/M4) — need new connectors (OECD EO,
  ONS, UK FCI composite); connector-sprint work not CAL-cleanup.

## 8. Merge strategy

This sprint ran on branch `sprint-m-cal-cleanup` and has **not** been
merged to `main`. Operator action required:

```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-m-cal-cleanup
git push origin main
```

Fast-forward is expected because the branch diverged from `main` at
`22a0465` and only adds commits on top of that base; Sprint N runs
in a separate worktree with a different branch so there's no rebase
work needed either.

Post-merge, the `sprint-m-cal-cleanup` branch can be deleted:

```bash
git branch -d sprint-m-cal-cleanup
git push origin --delete sprint-m-cal-cleanup
```

The `/home/macro/projects/sonar-wt-sprint-m` worktree can be torn
down via `git worktree remove` once its branch is gone.

## 9. Deviations from brief

- **Commit count**: brief projected 5-7 (with optional backfill);
  shipped 5 feature commits + retro = 6. Mid-range.
- **Integration test count**: brief itemised 5 cases; shipped 9
  (seven in backfill file, two in round-trip file). Added
  multi-country coverage not in the brief because the fixture
  pattern was already there.
- **No new CALs opened**: pure debt reduction, as expected.

*End of retrospective. Sprint CLOSED 2026-04-21. Merge pending operator action.*
