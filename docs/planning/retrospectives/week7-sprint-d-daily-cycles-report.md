# Week 7 Sprint D — Daily Cycles Pipeline

**Brief:** user-provided spec (no brief file on disk — SESSION_CONTEXT authorized autonomy using existing code as authoritative reference)
**Duration:** ~1.5h (2026-04-21)
**Commits:** 4 (C1–C4; C5 = this doc)
**Status:** SPRINT CLOSED

---

## 1. Summary

Shipped the daily cycles pipeline (`src/sonar/pipelines/daily_cycles.py`)
— the production entry-point that runs all four L4 composites
(CCCS + FCS + MSC + ECS) for a ``(country, date)`` tuple and persists
each result in a single session. Pipeline is a thin wrapper over
``compute_all_cycles`` (Week 7 Sprint A), plus a stagflation-inputs
resolver plug that auto-wires FRED when ``--backend=live`` is set.

C2 was skipped: pre-flight confirmed all four per-cycle persist
helpers (``persist_{cccs,fcs,msc,ecs}_result``) already shipped in
their respective Sprint retros. No helper gaps; no new persistence
work needed. The pipeline is a **pure orchestration layer** — it
adds zero compute, zero math, zero SQL.

## 2. Commits

| # | SHA | Title | Gate |
|---|-----|-------|------|
| 1 | `581ba25` | feat(pipelines): daily cycles pipeline — thin wrapper over compute_all_cycles | green |
| 2 | _skipped_ | (all persist helpers pre-existing) | n/a |
| 3 | `3efa370` | test(pipelines): daily_cycles pipeline unit tests | green |
| 4 | `b94a17d` | test(integration): daily_cycles pipeline 7 T1 vertical slice | green |
| 5 | _this doc_ | docs(planning): retrospective | pending |

Pre-push gate (`ruff format --check + ruff check + full-project mypy
+ pytest --no-cov`) green before every push. No `--no-verify`.

## 3. Pre-flight audit (C1)

Verified before touching any code:

| Symbol | Location | Status |
|--------|----------|--------|
| `compute_all_cycles(session, country, date, *, persist, ecs_stagflation_inputs)` | `src/sonar/cycles/orchestrator.py:77` | ✓ |
| `persist_cccs_result` | `credit_cccs.py:440` | ✓ |
| `persist_fcs_result` | `financial_fcs.py:345` | ✓ |
| `persist_msc_result` | `monetary_msc.py:401` | ✓ |
| `persist_ecs_result` | `economic_ecs.py:411` | ✓ |

C2 "fill any missing persist helpers" therefore became a no-op.

## 4. Pipeline design

`daily_cycles.py` (276 lines) exposes:

- `T1_7_COUNTRIES` — canonical 7-country tuple.
- `CyclesPipelineOutcome` — dataclass (country, date, orchestration,
  persisted).
- `StagflationInputsResolver` Protocol — `(session, country, date) →
  StagflationInputs | None`.
- `default_stagflation_resolver` — returns None → ECS overlay
  inactive + `STAGFLATION_INPUT_MISSING` flag.
- `run_one(session, country, date, *, stagflation_resolver=None) →
  CyclesPipelineOutcome` — single-country entry-point.
- `count_persisted(orch_result) → {"cccs": 0|1, …}` — per-cycle
  audit map.
- `main()` — typer CLI with `--country`/`--all-t1`/`--date`/
  `--backend=[default|live]`/`--fred-api-key`/`--cache-dir`.

Exit codes mirror `daily_economic_indices`: 0 OK, 1 no inputs,
3 duplicate collision, 4 CLI/IO.

The `--backend=live` path wires `resolve_stagflation_inputs`
(from Sprint A) via `_live_stagflation_resolver_factory`. The
resolver is called once per country per run inside `run_one`,
feeding the ECS overlay with CPI YoY + Sahm trigger + unemployment
delta.

## 5. Test coverage

### Unit tests (C3 — 14 tests)

- T1 country set constant match.
- Exit-code constants.
- `count_persisted` all-present / all-None / partial.
- `run_one` full-stack → 4/4 persisted.
- `run_one` empty DB → 0/4 + all 4 in skips.
- `run_one` ECS-only inputs → only ECS persists.
- `run_one` default resolver → `STAGFLATION_INPUT_MISSING` flag
  fires on ECS result.
- CLI error paths (invalid date / missing country / unknown backend /
  live-without-key) → EXIT_IO.

### Integration tests (C4 — 9 tests)

7-country parametrized sweep for 2024-12-31:

| Country | Full stack | ECS persists | Notes |
|---------|-----------|--------------|-------|
| US | yes | yes (4/4) | all cycles compute |
| DE | no | yes | CCCS + FCS + MSC in skips (no sub-inputs seeded); ECS persists via Eurostat + TE |
| IT/ES/FR/NL | no | yes | same as DE |
| PT | no | yes | E1_MISSING + re-weight; 3/4 ECS inputs |

Plus two end-to-end cases: US 4/4 verifying one row per L4 table
with `methodology_version` ending in `v0.1`; PT `E1_MISSING` path
asserting `indices_available == 3` + confidence ≤ 0.75.

## 6. HALT triggers

None of the 9 triggers fired. Full-project mypy green before every
push (88 → 92 source files post-C1). Concurrency note below covers
the Sprint C interplay.

## 7. Concurrency report

Sprint C (daily_overlays) was visible on main through the sprint
at `e39b17d` (shipped by the time Sprint D opened). No Sprint C
commits landed during this sprint window, so zero push-races
occurred. `db/persistence.py` was not touched by this sprint
(all needed helpers already present) → zero append-conflict
surface either.

## 8. Deviations from brief

- **Commit count**: 4 effective commits + this retro (brief
  projected 5). Commit 2 "fill any missing persist helpers"
  skipped because pre-flight found zero gaps; the count-vs-plan
  drop reflects the delta closer to zero rather than scope
  reduction.
- No other deviations; pipeline architecture, CLI, exit codes,
  and test matrix all match brief intent.

## 9. Sprint readiness downstream

- **Cron / scheduler**: pipeline is CLI-invokable; a cron wrapper
  can call `python -m sonar.pipelines.daily_cycles --all-t1 --date $(date -I -d yesterday) --backend live` nightly.
- **Daily orchestrator** (future): the canonical "run all pipelines
  in dependency order" shell can chain daily_economic_indices →
  daily_financial_indices → daily_monetary_indices → daily_cycles
  → daily_overlays.
- **Monitoring**: structlog events `cycles_pipeline.persisted`,
  `cycles_pipeline.no_inputs`, `cycles_pipeline.duplicate` expose
  operational signals for observability wiring in Phase 2+.

*End of retrospective. Sprint CLOSED 2026-04-21.*
