# Week 8 Sprint H — L5 Regime Classifier Spec + Scaffold — Implementation Report

## Summary

- **Duration**: ~3h actual / 4-5h budget.
- **Commits**: 7 feature commits (C1-C7) + this retrospective = 8 total.
- **Status**: **CLOSED**. Phase 2 foundation shipped. L5 regime
  classifier is specced, migrated, scaffolded, implemented with the
  Phase-1 rule-based decision tree, persisted through a dedicated
  helper, and exercised by 8 canonical fixtures (25 unit tests across
  the package + 4 persistence tests + 6 ORM tests + 12 scaffold
  tests = 47 new tests).
- **Scope**: Spec-first (C1-C3 spec writing before code) then
  implementation (C4-C7) — deliberate per brief §9 because L5 is a
  Phase-0 spec gap being retrofitted.

## Commits (main-visible SHAs)

| # | SHA | Scope |
|---|---|---|
| 1 | `13fa926` | docs(specs): L5 regimes directory + meta-regime classifier spec (README + cross-cycle-meta-regimes.md) |
| 2 | `b35f67a` | docs(specs): L5 integration-with-l4 — FK pattern + Policy 1 extension |
| 3 | `b80dfbd` | docs(adr): ADR-0006 L5 regime classifier — design decisions |
| 4 | `4907337` | feat(db): migration 017 + L5MetaRegime ORM + 6 ORM tests |
| 5 | `3693924` | feat(regimes): L5 package scaffold — base ABC + types + exceptions + 12 scaffold tests |
| 6 | `5094989` | feat(regimes): MetaRegimeClassifier decision tree + 8 canonical fixtures + 25 classifier tests |
| 7 | `b6e5f78` | feat(db): persist_l5_meta_regime_result helper + 4 persistence tests |
| 8 | _this_ | Retrospective |

## Spec artefacts shipped

- **`docs/specs/regimes/README.md`** — L5 layer overview, 6 canonical
  meta-regimes, design principles (read-only of L4, FK-linked,
  rule-based, Policy 1 extension, confidence inheritance), Phase 2+
  scope boundary.
- **`docs/specs/regimes/cross-cycle-meta-regimes.md`** — full inputs
  schema (12 fields across 4 L4 cycle tables + overlays),
  priority-ordered decision tree (6 branches), Policy 1 fail-mode,
  outputs schema, 8 canonical-fixture contract, flag lexicon
  additions, methodology version frozen at `L5_META_REGIME_v0.1`.
- **`docs/specs/regimes/integration-with-l4.md`** — FK design,
  query pattern (quarterly CCCS forward-fill vs monthly exact match
  for the other three), Policy-1 integration, flag lexicon (6
  regime-level + 4 missing-cycle + 1 error-only), re-classification
  semantics, ingest-orchestration deferral to the Week 8 Day 2
  sprint.
- **`docs/adr/ADR-0006-l5-regime-classifier.md`** — five design
  decisions (architecture / taxonomy / Policy 1 integration / FK
  design / auditability); rejected alternatives documented (ML
  classifier, simple score-average, inline L4 extension, 12+ regime
  taxonomy).

## Code shipped

- **Migration 017** — `l5_meta_regimes` table with 4 nullable UUID
  FKs to the cycle tables, CHECK constraint on the 6-value
  `meta_regime` enum, `(country, date, methodology_version)`
  uniqueness.
- **`L5MetaRegime` ORM** — in a new `# === L5 Regime models ===`
  bookmark zone at the tail of `src/sonar/db/models.py`.
- **`src/sonar/regimes/` package** — 4 modules (`__init__.py` +
  `base.py` + `exceptions.py` + `types.py` +
  `meta_regime_classifier.py`). `MetaRegime` is a `StrEnum`;
  snapshots are frozen/slotted dataclasses; `L5RegimeInputs.available_count()`
  and `.missing_flags()` drive the Policy-1 path.
- **`MetaRegimeClassifier`** — concrete `RegimeClassifier`
  implementation of the decision tree. Priority ordering
  stagflation (1) > recession (2) > late-bubble (3) > overheating
  (4) > soft-landing (5) > unclassified (6). Confidence cap 0.75 at
  1-missing; 2-missing raises.
- **`persist_l5_meta_regime_result`** — atomic insert into
  `l5_meta_regimes`; reuses the shared `_flags_to_csv` helper and
  raises `DuplicatePersistError` on the uniqueness collision.

## Tests shipped

| Module | Tests |
|---|---|
| `tests/unit/test_db/test_l5_meta_regime_model.py` | 6 (table creation, all-FKs roundtrip, nullable FKs, CHECK rejects unknown regime, uniqueness violation, confidence bounds) |
| `tests/unit/test_regimes/test_base_types.py` | 12 (MetaRegime enum shape, StrEnum comparison, available_count edges, missing_flags CSV shape, default methodology, ABC cannot instantiate, incomplete subclass rejected, concrete subclass OK, exception hierarchy) |
| `tests/unit/test_regimes/test_meta_regime_classifier.py` | 25 (6 canonical fixture branches, 3/4 ECS-missing cap+flag, 2/4 insufficient raises, priority ordering, regime flag always emitted, methodology stamping, FK id propagation, min-confidence semantics) |
| `tests/unit/test_db/test_l5_persistence.py` | 4 (happy path, duplicate raises, nullable FKs persist, empty flags round-trip) |

**47 new tests total**; full suite holds at 1160 unit tests passing
(21 slow deselected) with mypy clean over 107 source files.

## HALT triggers

- **#0** Pre-flight cycle spec divergence — not fired. The spec
  authors reviewed the L4 ORM column names directly
  (`stagflation_overlay_active`, `regime_3band`, etc.) before
  writing the spec so the wire fields match the code.
- **#1** FK cardinality — not fired. `(country, date,
  methodology_version)` uniqueness matches the L4 cycle pattern; no
  need for multiple rows per triplet.
- **#2** UUID source — not fired. `L5MetaRegime` takes an explicit
  `l5_id` on insert (generated in `_to_l5_row`); FK columns are
  `String(36)` matching the cycle table PKs.
- **#3** Decision tree ambiguity — handled by design: missing
  cycles short-circuit predicates to `False`; anything not matching
  a decisive branch falls to `unclassified` with
  `classification_reason="default"`.
- **#4** Migration ordering — not fired. Migration 017 chains off
  016 (`economic_cycle_composite_schema`); all four parent tables
  (013, 015, 016 chain) exist.
- **#5** ORM bookmark zone — handled by placing the new zone at the
  tail of `models.py` after the `# === Cycle models end ===`
  marker; no existing zone touched.
- **#6** Fixture realism — fixtures named after canonical US
  macro episodes (1974 / 2007-Q2 / 2009-Q1 / 2015 / 2021-Q2) with
  scores + regimes consistent with the embedded overlays.
- **#7** Coverage regression — none. Every new module sits ≥ 90 %
  line coverage via its dedicated test file.
- **#8** Pre-push gate failure — green every push (ruff + mypy 107
  source files + 1160 unit tests).
- **#9** Sprint I collision — not fired. Sprint I landed
  `connectors/boe_database.py` + extensions to
  `indices/monetary/builders.py` + `config/country_tiers.yaml` +
  `pipelines/daily_monetary_indices.py`; zero file overlap with this
  sprint's `docs/specs/regimes/` + `docs/adr/ADR-0006` + `migration
  017` + `src/sonar/regimes/` + `models.py` L5 zone + `persistence.py`
  append.

## Deviations from brief

1. **Snapshot dataclasses** — the brief described `L5RegimeInputs`
   carrying full `EconomicCycleScore | None` etc. from the ORM.
   Shipped instead with lightweight `EcsSnapshot / CccsSnapshot /
   FcsSnapshot / MscSnapshot` frozen dataclasses that expose only
   the 4-5 fields the classifier reads. Decouples the classifier
   from ORM concretes + keeps tests + fixtures self-contained.
2. **Fixtures as Python builders** — the brief suggested JSON files
   under `tests/unit/test_regimes/fixtures/`. Shipped as Python
   builder functions in the test module instead. JSON would have
   required a loader + a serialisation contract; the builder form is
   more refactor-friendly when the `Snapshot` dataclasses evolve.
   Spec §7 still names the 8 scenarios and the test module maps
   them 1-to-1.
3. **`StrEnum` instead of `str, Enum`** — Ruff `UP042` flagged the
   dual-base pattern; swapped for Python 3.11+'s `StrEnum`. Same
   runtime behaviour (string equality works), cleaner typing.
4. **`MetaRegimeClassifier` local UUID generation** — brief wrote
   the ORM model's `l5_id` default as a lambda in the SQLAlchemy
   column. Shipped the default in the persistence helper
   (`_to_l5_row`) instead since the classifier keeps the Result
   dataclass free of id generation (the id belongs to the ORM layer,
   not to the compute output).

## Remaining L5 work for Day 2+

- **`daily_cycles.py` wiring** — extend the L4 orchestrator pipeline
  to read its own persisted cycle rows, build `L5RegimeInputs`, call
  `MetaRegimeClassifier().classify(...)`, and persist via
  `persist_l5_meta_regime_result`. Surface `InsufficientL4DataError`
  as a structured skip.
- **Live integration test** — seed ≥ 1 month of real cycle rows via
  the existing pipelines, run L5 classification, verify plausible
  meta-regime output.
- **Backfill script** — retrospective L5 classification over all
  existing cycle rows (optional; low priority since prod data < 1m
  old).
- **L5b cross-cycle matrix** — 4×4 cycle-vs-cycle diagnostics —
  Phase 2+.
- **Empirical calibration** — threshold adjustments to the decision
  tree once ≥ 24 m production data is available.

## Phase 2 transition formally open

Phase 1 closed Week 7 Sprint G; Phase 2 transition opens here with
the L5 layer. The classifier is a **foundation** — next sprints will:

- Wire it into the daily orchestration path.
- Expose regimes on the `sonar status` CLI (3-line addition).
- Produce the first editorial-facing cross-country regime output.

## Final tmux echo

```
SPRINT H L5 REGIME CLASSIFIER DONE: 8 commits, Phase 2 foundation shipped
Spec: 3 files (README + cross-cycle + integration-with-l4) + ADR-0006
Code: regimes/ package (4 modules) + migration 017 + L5MetaRegime ORM + persist_l5_meta_regime_result
Fixtures: 8 canonical covering 6 meta-regimes + Policy 1 3/4 + 2/4 cases
Tests: 47 new (6 ORM + 12 scaffold + 25 classifier + 4 persist); 1160 total unit tests green
HALT triggers: none fired
Day 2+ work: daily_cycles L5 wiring, live integration, backfill, L5b matrix Phase 2+
Artifact: docs/planning/retrospectives/week8-sprint-h-l5-regime-classifier-report.md
```

_End of Week 8 Sprint H retrospective. Phase 2 foundation shipped.
L5 classifier is ready for daily-orchestration wiring in the
follow-on sprint._
