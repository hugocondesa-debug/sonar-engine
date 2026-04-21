# Week 8 Sprint K — L5 daily_cycles Wiring + sonar status CLI

**Brief:** `docs/planning/week8-sprint-k-l5-wiring-cli-brief.md`
**Duration:** ~2h (2026-04-21)
**Commits:** 5 shipped + retrospective (sprint8-K c1–c6). Backfill script (planned C6) deferred per brief §4 note.
**Status:** SPRINT CLOSED — Phase 2 first user-facing deliverable live

---

## 1. Summary

L5 is now operational. The `daily_cycles` pipeline runs the
`MetaRegimeClassifier` right after the four L4 composites persist,
writes the resulting row to `l5_meta_regimes`, and `sonar status`
renders the classification alongside the existing cycle breakdown.

Phase 2's first externally-visible deliverable shipped: running
`sonar status --country US` now surfaces a colour-coded meta-regime
label with confidence and classification reason, backed by the
decision tree in `docs/specs/regimes/cross-cycle-meta-regimes.md`.

## 2. Commits

| # | SHA | Title | Gate |
|---|-----|-------|------|
| 1 | `427e964` | feat(regimes): ORM-to-Snapshot helpers for L5 input assembly | green |
| 2 | `86216e5` | feat(pipelines): daily_cycles invokes L5 classifier post-L4 | green |
| 3 | `9fc677c` | feat(cli): sonar status shows L5 meta-regime | green* |
| 4 | `18417b6` | test(integration): daily_cycles + sonar status L5 end-to-end | green |
| 5 | `8adaef3` | test(integration): L5 classification branches via assembler round-trip | green |
| 6 | _this doc_ | docs(planning): retrospective | pending |

*C3 also included a WIP snapshot of Sprint I-patch's `builders.py` + `test_builders.py` that had been left unstaged when the pre-commit hook stashed/unstashed the tree (see §7). The Sprint I-patch changes were independently valid and all gates passed; the commit message only describes the sonar-status additions because that was the user-visible scope of Sprint K. Flagged here for audit.

Pre-push gate (full-project mypy 108→110 files + ruff + detect-secrets)
green before every push. No `--no-verify`.

## 3. Design decisions (Commit 1)

### In-memory Snapshot build vs DB re-read

Option A (chosen): assemble Snapshots directly from the
`CyclesOrchestrationResult` the orchestrator returns. The
`persist_{cccs,fcs,msc,ecs}_result` helpers write the same values
that live on the `*ComputedResult` dataclasses — re-reading from the
DB would be an extra round-trip with zero correctness benefit.

### Module placement

`src/sonar/regimes/assemblers.py` bridges `sonar.cycles.*` (L4) with
`sonar.regimes.types` (L5). Keeping it in the regimes package avoids
contaminating `types.py` with orchestrator imports.

### Flag coercion at the boundary

The overlay flag columns (`boom_overlay_active`,
`bubble_warning_active`, `dilemma_overlay_active`,
`stagflation_overlay_active`) are `int` on the L4 result dataclasses
and `bool` on the Snapshot dataclasses. Helpers coerce `int → bool`
so the classifier predicates read naturally
(`if ecs.stagflation_active and msc.dilemma_active: …`).

## 4. Tests shipped

| File | New tests | Focus |
|------|-----------|-------|
| `test_regimes/test_assemblers.py` | 10 | per-cycle snapshot helpers + composite build + None pass-through + missing-flag propagation |
| `test_pipelines/test_daily_cycles.py` | 3 | full-stack L5 persist + 1/4 cycle skip + duplicate rerun |
| `test_cli/test_status.py` | 7 | L5 row populated / absent / stale + summary / verbose / matrix rendering |
| `test_integration/test_l5_vertical_slice.py` | 3 | L3 seed → L4 → L5 → `get_country_status` → Rich rendering |
| `test_integration/test_l5_classification_branches.py` | 6 | parametrised end-to-end per canonical regime |

Total: 29 new tests, all green. Integration tests marked
`@pytest.mark.slow`.

## 5. HALT triggers

9 triggers atomic (plus 10 from brief §5 which enumerates through 9
explicitly + budget overflow as #6); none fired:

| # | Trigger | Fired | Notes |
|---|---------|-------|-------|
| 0 | Snapshot builder field mismatch | — | Verified against all four `*ComputedResult` dataclasses in pre-flight |
| 1 | `CyclesOrchestrationResult` structure drift | — | Confirmed field names match orchestrator output |
| 2 | `DuplicatePersistError` crashes pipeline | — | Explicit catch in `_classify_and_persist_l5`; L5 skip-reason populated |
| 3 | `InsufficientL4DataError` signature | — | `sonar.regimes.exceptions.InsufficientL4DataError` handled cleanly |
| 4 | Rich colours unavailable | — | `rich` already in `pyproject.toml`; `bright_black` chosen for `unclassified` (Rich has no `gray` primitive) |
| 5 | Seeding complexity for integration test | — | Reused Sprint D/A `_seed_e{1,2,3,4}` + `_seed_m{1-4}` + `_seed_f_rows` + `_seed_sub_rows` helpers |
| 6 | Backfill scope creep | deferred | C6 deferred per brief §4 note; ~30 production dates affected so not critical path |
| 7 | Coverage regression > 3pp | — | Added modules ≥ 90 % (assemblers 100 %; `_classify_and_persist_l5` + status L5 branch exercised by integration tests) |
| 8 | Pre-push gate fails | — | Full mypy green across 108→110 src files every push |
| 9 | Concurrent Sprint I-patch file overlap | minor | No logical overlap; one bookkeeping tangle documented in §7 |

## 6. Spec deviations from brief

- **Commit 6 backfill deferred** per brief §4 explicit allowance. Rationale: ~30 production dates affected so not critical path; can land in a follow-up patch when needed.
- **No `"orange"` Rich colour**: late_cycle_bubble mapped to `yellow` (Rich standard palette lacks orange). Acceptable divergence; documented in `_L5_REGIME_STYLE` comment.
- **Commit count**: brief projected 6-8, shipped 5 feature commits + retro (= 6). Within range.

## 7. Concurrency report + bookkeeping tangle

Sprint I-patch (TE UK wrappers + UK M1 cascade refinements) ran in
parallel per brief §3. Zero file overlap in intent — all hard-locked
resources respected. Observed interaction:

During C3's pre-commit/stash dance, Sprint I-patch's unstaged
modifications to `src/sonar/indices/monetary/builders.py` +
`tests/unit/test_indices/monetary/test_builders.py` ended up in my
commit `9fc677c` despite my `git add` only targeting `status.py` +
`test_status.py`. The Sprint I-patch changes were independently
correct (full gate green) but the commit message doesn't describe
them. Noted so operator can verify their provenance via
`git blame` on those files.

**Process fix for next sprint**: use `git diff --staged` explicitly
after `git add` and before `git commit`, not just `git status`, to
catch this class of pre-commit-stash interaction.

## 8. Phase-2 readiness

- **User-visible**: `sonar status --country US` now renders the L5
  meta-regime with colour coding + confidence + freshness +
  classification reason. Editorial team / 7365 Capital analysts can
  read cross-cycle regime classification without drilling into
  individual cycles.
- **Matrix view**: `sonar status --all-t1` compact L5 column shows
  meta-regime across the seven Tier-1 countries — useful for
  dashboard snapshots.
- **Observability**: structlog events
  `cycles_pipeline.l5_persisted`, `cycles_pipeline.l5_insufficient_l4`,
  `cycles_pipeline.l5_duplicate_skip` make L5 operationalisation
  measurable.

## 9. Phase-2 follow-ups (no new CALs from this sprint)

- **CAL-backfill-l5** (deferred from C6): iterate historical cycle
  dates + classify retroactively. Low priority — production data <1m
  old means < 30 dates affected.
- **L5b 4×4 cross-country matrix** (Phase 2+ per ADR-0006).
- **Empirical confidence calibration** (needs 24m production data).
- **ML classifier upgrade** (Phase 2+ under same `RegimeClassifier`
  Protocol).

No new backlog items opened; Sprint K is pure implementation of the
Sprint H spec.

*End of retrospective. Sprint CLOSED 2026-04-21.*
