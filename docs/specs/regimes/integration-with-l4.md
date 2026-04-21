# L5 ↔ L4 Integration — FK Pattern + Policy 1 Extension

Companion to [`cross-cycle-meta-regimes.md`](cross-cycle-meta-regimes.md)
describing the structural contract between L5 and the four L4 cycle
tables.

---

## 1. Foreign-key design

Each `l5_meta_regimes` row references up to four L4 cycle rows via
**nullable UUID foreign keys**:

```
l5_meta_regimes
  ├── ecs_id  → economic_cycle_scores.ecs_id    (nullable)
  ├── cccs_id → credit_cycle_scores.cccs_id     (nullable)
  ├── fcs_id  → financial_cycle_scores.fcs_id   (nullable)
  └── msc_id  → monetary_cycle_scores.msc_id    (nullable)
```

The nullability accommodates the Policy-1 fail-mode: L5 can classify
with 3 / 4 cycles present (see §3). When a cycle is missing the
corresponding FK stays `NULL` and the L5 row emits a
`L5_{CYCLE}_MISSING` flag.

## 2. Query pattern

For `(country, date)` the classifier looks up one row per L4 cycle:

```sql
-- ECS, FCS, MSC are monthly cycles → exact-date match.
SELECT *
FROM economic_cycle_scores
WHERE country_code = :country AND date = :date
ORDER BY created_at DESC
LIMIT 1;

-- Credit cycle (CCCS) is quarterly — forward-fill from the last
-- quarter-end on or before the anchor date.
SELECT *
FROM credit_cycle_scores
WHERE country_code = :country AND date <= :date
ORDER BY date DESC, created_at DESC
LIMIT 1;
```

Callers outside the pipeline (for example the ad-hoc `sonar status
--country US --date ...` dashboard) use the same pattern so the L5
reading is consistent with what gets persisted.

## 3. Policy 1 integration

L5 extends the Policy-1 convention from
[`../conventions/composite-aggregation.md`](../conventions/composite-aggregation.md)
to the 4-cycle ensemble:

- Coverage requirement: **≥ 3 of 4** cycles available. Below that the
  classifier raises :class:`sonar.regimes.exceptions.InsufficientL4DataError`
  and does not produce a row.
- Missing-cycle flag: one `L5_{CYCLE}_MISSING` flag per absent cycle
  (`L5_ECS_MISSING`, `L5_CCCS_MISSING`, `L5_FCS_MISSING`,
  `L5_MSC_MISSING`).
- Confidence cap: `min(confidence_i for i in present_cycles)` with a
  hard cap of **0.75** when one cycle is missing. The 2-missing case
  is below the classification threshold (raises instead) but the
  nominal 0.60 cap is documented for forward compatibility with
  future relaxations.

## 4. Flag lexicon additions

Lands in [`../conventions/flags.md`](../conventions/flags.md) under a
new L5 section. Flags fall into three groups:

### 4.1 Regime-level (one per L5 row)

- `L5_OVERHEATING`
- `L5_STAGFLATION_RISK`
- `L5_LATE_CYCLE_BUBBLE`
- `L5_RECESSION_RISK`
- `L5_SOFT_LANDING`
- `L5_UNCLASSIFIED`

Exactly one of the six fires per classification — the classifier
maps the chosen `meta_regime` value to the matching flag.

### 4.2 Missing-cycle annotations

- `L5_ECS_MISSING`
- `L5_CCCS_MISSING`
- `L5_FCS_MISSING`
- `L5_MSC_MISSING`

Zero or more fire per classification; at most one can fire per row
since two missing cycles trips the exception.

### 4.3 Error-only (never persisted)

- `L5_INSUFFICIENT_CYCLES` — name of the error category raised via
  :class:`InsufficientL4DataError`. Documented here so
  pipeline-level exception handlers can surface a consistent label.

## 5. Ingest orchestration (Phase 2 — out of Sprint H scope)

`daily_cycles.py` grows a post-L4 L5 step that:

1. Reads the L4 rows just persisted by its own compute.
2. Builds `L5RegimeInputs`.
3. Invokes `MetaRegimeClassifier().classify(...)` wrapped in the
   usual `try/except InsufficientL4DataError` → structured skip.
4. Persists via `persist_l5_meta_regime_result`.

Sprint H ships the classifier + ORM + persistence helper. The
pipeline wiring + live integration test land in the follow-on sprint
(Week 8 Day 2).

## 6. Re-classification semantics

The `(country, date, methodology_version)` triplet is the uniqueness
constraint on `l5_meta_regimes`. Re-running the classifier with the
same `L5_META_REGIME_v0.1` methodology on the same cycle rows yields
the same row and triggers
:class:`sonar.db.persistence.DuplicatePersistError` on re-persist —
consistent with the existing cycle persistence helpers.

A change to the decision tree bumps the methodology version (see
[`../conventions/methodology-versions.md`](../conventions/methodology-versions.md)),
so re-classification with a new taxonomy produces a new row without
colliding with the prior one.

## 7. Cross-references

- [`cross-cycle-meta-regimes.md`](cross-cycle-meta-regimes.md) —
  decision tree + taxonomy.
- [`../../adr/ADR-0006-l5-regime-classifier.md`](../../adr/ADR-0006-l5-regime-classifier.md)
  — design decisions + rejected alternatives.
- [`../conventions/composite-aggregation.md`](../conventions/composite-aggregation.md)
  — Policy-1 pattern this spec extends.
- [`../conventions/flags.md`](../conventions/flags.md) — flag lexicon
  being extended.
- [`../conventions/methodology-versions.md`](../conventions/methodology-versions.md)
  — bump rules for the classifier.
