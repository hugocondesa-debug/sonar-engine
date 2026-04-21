# Week 7 Sprint G — M1 US Polish (Phase 1 Close) — Implementation Report

## Summary

- **Duration**: ~3h actual / 3.5-4h budget.
- **Commits**: 6 feature commits (C1-C6) + this retrospective = 7 total.
- **Status**: **CLOSED**. Phase 1 Week 7 formally ends here. **M1 US
  milestone declared complete** (implementation scope 100 %; spec
  scope ~70-75 %, deltas catalogued in `m1-us-gap-analysis.md`).
- **Scope**: 5 coherent sub-scopes in a single sprint — documentation
  consolidation, retention policies, basic monitoring, CLI dashboard,
  gap documentation. Every item shipped green.

## Commits (main-visible SHAs)

| # | SHA | Scope |
|---|---|---|
| 1 | `cc354a0` | M1 US milestone scorecard (`docs/milestones/m1-us.md`) + README Phase 1 status + CLAUDE.md §9 refresh |
| 2 | `75a3f43` | Retention policies + VACUUM helper + Typer sub-app + 8 unit tests |
| 3 | `4fbd6a2` | `sonar health` pipeline freshness + Rich table + AlertSink Protocol + 11 unit tests |
| 4 | `5c585fc` | `sonar status` cross-cycle dashboard + `sonar.cli.main` root Typer app + pyproject.toml entry point fix + 9 unit tests |
| 5 | `298f6f5` | M1 US gap analysis (`docs/milestones/m1-us-gap-analysis.md`) with CAL categorization |
| 6 | `60a98bb` | Integration smoke — 6 @slow canaries exercising all 4 CLI commands |
| 7 | _this_ | Retrospective + Phase 1 close |

## CLI commands shipped

```bash
sonar status --country US --date 2024-12-31
sonar status --country US --verbose
sonar status --all-t1
sonar health
sonar health --country US
sonar retention run --dry-run        # default
sonar retention run --execute
sonar retention vacuum
```

`sonar --help` now lists all three sub-apps (status / health /
retention) through the new `sonar.cli.main:app` Typer root — the
pyproject.toml entry point was fixed from the stale
`sonar.outputs.cli.main:app` reference.

## Documentation artefacts

- **`docs/milestones/m1-us.md`** — L0-L8 scorecard + 7-country
  coverage matrix + CLI quickstart + cross-reference to gap analysis.
- **`docs/milestones/m1-us-gap-analysis.md`** — 62 CAL items
  categorized by impact (A/B/C/D); spec-implementation mapping table
  per overlay / index / cycle / pipeline.
- **`README.md`** — new "Estado — Phase 1 Week 7 (M1 US)" section with
  component-by-component summary + quickstart block.
- **`CLAUDE.md`** — §9 refreshed from the stale "Phase 1 Week 3.5 em
  curso" to the current "Phase 1 Week 7 CLOSED — M1 US ~95 %" with
  the full component status.

## Operational hooks shipped

- **Retention**:
  - `bis_credit_raw` 10y, `yield_curves_spot` 15y, `yield_curves_forwards` 10y, `ratings_agency_raw` 5y.
  - L3 indices + L4 cycles + `index_values` (CRP + EXPINF) kept
    forever.
  - Dry-run default; `--execute` explicit. Each table's DELETE in its
    own transaction so one failure doesn't poison the batch.
- **Monitoring**:
  - `PIPELINE_TO_TABLE` maps 17 pipeline-output pairs with their
    timestamp columns (most `created_at`; `bis_credit_raw`
    `fetched_at`).
  - Fresh (< 24h) / stale (24-72h) / missing (> 72h or no rows)
    classification.
  - `AlertSink` Protocol + `NullAlertSink` default — Phase 2+
    extension point for real email / webhook / Slack delivery.
- **Dashboard**:
  - Single-country summary (Score + Regime + Confidence + Freshness).
  - Verbose mode with L3 sub-scores + flags.
  - `--all-t1` 7-country matrix with `N/A` cells where rows are
    missing.
  - MSC uses the 3-band regime (ACCOMMODATIVE / NEUTRAL / TIGHT).

## Coverage delta

| Module | Before | After |
|---|---|---|
| `src/sonar/cli/` | n/a (outputs/cli/ was broken pyproject ref) | 3 new files: main.py + health.py + status.py |
| `src/sonar/scripts/retention.py` | n/a | 262 LOC + 8 tests |
| `docs/milestones/` | n/a | 2 new files: m1-us.md + m1-us-gap-analysis.md |
| `tests/unit/test_cli/` | n/a | 20 tests (11 health + 9 status) |
| `tests/unit/test_scripts/test_retention.py` | n/a | 8 tests |
| `tests/integration/test_cli_commands.py` | n/a | 6 @slow canaries |

Full suite: **1105 unit tests passing** (21 slow deselected). mypy
over 101 source files clean. One pre-existing flaky
`test_full_stack_us_persists_all_four` passes in isolation — surfaced
in Sprint E, unrelated to this sprint.

Pre-commit `mypy` hook gained `typer` + `rich` deps (mirroring the
earlier `numpy/scipy/statsmodels` addition) so the isolated hook env
resolves Typer decorator types.

## HALT triggers

- **#0** CLI framework decision — not fired. Typer matches the
  existing pipeline CLIs.
- **#1** Rich library not available — not fired. Already a project
  dep.
- **#2** Existing `sonar` CLI structure — pyproject pointed at
  `sonar.outputs.cli.main:app` which didn't exist. Fixed by creating
  `sonar.cli.main` and flipping the entry point.
- **#3** SQLite VACUUM locking — noted in docstrings; tests use
  in-memory fixtures so locking doesn't bite.
- **#4** Retention policy table list — surfaced a real schema mismatch
  on `ratings_agency_raw` (spec suggested `observation_date`, actual
  column is `date`). Fixed before commit.
- **#5** Health check performance — n/a. Queries are single-row
  `MAX(created_at)` + `COUNT(*)` per table; no aggregation lag.
- **#6** Dashboard data-source consistency — handled by
  `_fetch_latest` reading one cycle table at a time with per-cycle
  sub-column maps; no cross-cycle joins.
- **#7** Gap docs CAL accuracy — verified against actual
  `docs/backlog/calibration-tasks.md` (62 items, 21 closed, 41 open).
- **#8** Coverage regression — none.
- **#9** Pre-push gate failures — fired twice (pre-commit `mypy`
  decorator untyped-decorator error on `@app.command()`; fixed by
  adding `typer` + `rich` to hook deps + `rm -rf ~/.cache/pre-commit`
  + `pre-commit install-hooks`). Also a couple of silent empty-
  commits from the stash/restore cycle; recovered by re-staging and
  re-committing.

## Deviations from brief

1. **pyproject.toml entry point fix** — brief assumed the `sonar` CLI
   already existed; it didn't (`sonar.outputs.cli.main:app` was a
   broken reference). Created `sonar.cli.main` + flipped the entry
   point. Two lines.
2. **Pre-commit hook dep extension** — brief didn't mention, but
   `typer` + `rich` needed to join the isolated `mypy` hook env to
   resolve decorator types. One config-only change.
3. **E2 "1 of 8 components" re-classification** — gap analysis
   clarifies that the shipped `E2Inputs` dataclass has 3 scalar
   inputs (all NSS-derived) + histories. The spec's 8-component shape
   was never implemented; CAL-054 tracks the upgrade. The original
   brief's phrasing was spec-aspirational rather than an audit of
   shipped code.
4. **`sonar status --verbose` with `--all-t1`** — the verbose mode
   only works with `--country`; the matrix mode is inherently compact.
   Documented in CLI help, not explicit guard in code.

## Week 7 Day 3 summary (all three sprints)

- **Sprint E** CAL-108 (E2 + M3 DB-backed readers) — 2h, 5 commits,
  CAL-104 + CAL-105 upgraded to fully CLOSED.
- **Sprint F** CAL-109/110/111 (live-connector assemblers for
  ERP/CRP/rating) — ~2h, 5 commits.
- **Sprint G** M1 US Polish (this sprint) — ~3h, 7 commits.
- **Total Day 3**: ~7-8h wall-clock, 17 commits.
- **CAL closures Day 3**: CAL-108 + CAL-104 + CAL-105 upgraded + (if
  CAL-115/116/117 closed by Sprint F — see their retro).
- **New CALs surfaced**: see Sprint E retro (113, 114); Sprint G
  introduces none (documentation + polish only).

## Phase 1 close summary

- Phase 1 spanned Week 1 through Week 7 (~6 weeks calendar).
- **Major sprints shipped**: ~20 briefs covering bootstrap → L0
  connectors → L1 persistence → L2 overlays → L3 indices → L4
  cycles → L8 pipelines → M1 US polish.
- **Tests**: ~180 baseline → 1105+ unit + ~35 integration + ~28 slow
  canaries.
- **Migrations**: 001 → 016 (16 Alembic migrations).
- **Connectors**: 22+ operational.
- **Overlays**: 5/5 shipped.
- **Indices**: 16/16 compute; 14-16/16 real-data.
- **Cycles**: 4/4 L4 composites operational with overlays + regime
  classification.
- **Pipelines**: 9 daily pipelines + orchestration.
- **CAL items**: 62 total (21 closed, 41 open — mostly M2 T1 / Phase
  2+ scope).
- **Retrospectives**: 17 files (this one closes the sprint sequence).

## M1 US milestone declared complete

**Implementation scope**: 100 % of Phase 1 planned features shipped.

**Spec scope**: ~70-75 %. Deltas documented in
`m1-us-gap-analysis.md` — biggest known: E2 Leading at 3 / 8
components (CAL-054), rating-spread agency scrape forward-path
partial (multi-agency daily scrape Phase 2+).

**Out of Phase 1 scope**: L5 regimes + weekly integration matrix +
L7 outputs + Postgres + systemd / cron wiring + email / webhook
alerting delivery + 18-24 months production data for empirical
calibration.

## Next steps Week 8+

- **M2 T1 Core** — UK + JP connector suites; per-country ERP live
  paths; EA periphery M2 + M4 (CAL-101/102); Eurostat GDP EA resolver
  (CAL-103).
- **Agency scrape forward-path** — CAL-115 Phase 2+ (multi-agency
  daily).
- **L5 regime classifier spec** — Phase 2+ transition work.
- **Postgres migration planning**.
- **Systemd timer / cron ops wiring**.
- **Forward-EPS dedicated connector** — CAL-117 (FactSet / IBES) if
  scrape sources flake.

## Final tmux echo

```
SPRINT G M1 US POLISH DONE: 7 commits, Phase 1 Week 7 CLOSED
Docs: m1-us.md + m1-us-gap-analysis.md + README + CLAUDE updated
CLI: sonar status + sonar health + sonar retention shipped + pyproject entry point fixed
Ops: retention policies (4 raw tables) + monitoring interface (AlertSink stub) shipped
M1 US milestone: DECLARED COMPLETE (implementation scope 100%)
Gap analysis: spec 70-75% (documented; 41 open CAL items categorized)
HALT triggers: #2 (CLI root bootstrap) + #4 (ratings_agency_raw column name) + #9 (pre-commit mypy hook deps + stash cycle) all recovered
Artifact: docs/planning/retrospectives/week7-sprint-g-m1-us-polish-report.md
```

_End of Week 7 Sprint G retrospective. Phase 1 Week 7 formally closed.
M1 US declared complete. Next milestone: M2 T1 Core._
