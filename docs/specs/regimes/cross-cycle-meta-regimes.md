# Cross-Cycle Meta-Regimes — Classification Specification

**Methodology version**: `L5_META_REGIME_v0.1` (Phase 1).

---

## 1. Purpose

Classify each `(country, date)` into exactly one of six canonical
meta-regimes by consuming the four L4 cycle scores + their embedded
overlays. The output is a single discrete label plus the ids of the
L4 rows the classification was derived from, so every L5 row is fully
auditable and reversible to the cycle data that produced it.

## 2. Inputs

Per `(country, date)` the classifier reads up to **four L4 cycle
rows** (one per cycle). Each row contributes the fields below:

| Source table | Field | L5 input name | Type | Notes |
|---|---|---|---|---|
| `economic_cycle_scores` | `ecs_id` | `ecs.ecs_id` | UUID | FK carried through to L5 row |
| `economic_cycle_scores` | `score_0_100` | `ecs.score` | float [0, 100] | ECS composite score |
| `economic_cycle_scores` | `regime` | `ecs.regime` | enum | `EXPANSION` / `PEAK_ZONE` / `EARLY_RECESSION` / `RECESSION` |
| `economic_cycle_scores` | `stagflation_overlay_active` | `ecs.stagflation_active` | bool | ECS Cap 16 Trigger A |
| `economic_cycle_scores` | `confidence` | `ecs.confidence` | float [0, 1] | |
| `credit_cycle_scores` | `cccs_id` | `cccs.cccs_id` | UUID | |
| `credit_cycle_scores` | `score_0_100` | `cccs.score` | float | |
| `credit_cycle_scores` | `regime` | `cccs.regime` | enum | `REPAIR` / `RECOVERY` / `BOOM` / `SPECULATION` / `DISTRESS` |
| `credit_cycle_scores` | `boom_overlay_active` | `cccs.boom_active` | bool | Boom overlay trigger |
| `credit_cycle_scores` | `confidence` | `cccs.confidence` | float | |
| `financial_cycle_scores` | `fcs_id` | `fcs.fcs_id` | UUID | |
| `financial_cycle_scores` | `score_0_100` | `fcs.score` | float | |
| `financial_cycle_scores` | `regime` | `fcs.regime` | enum | `STRESS` / `CAUTION` / `OPTIMISM` / `EUPHORIA` |
| `financial_cycle_scores` | `bubble_warning_active` | `fcs.bubble_warning_active` | bool | |
| `financial_cycle_scores` | `confidence` | `fcs.confidence` | float | |
| `monetary_cycle_scores` | `msc_id` | `msc.msc_id` | UUID | |
| `monetary_cycle_scores` | `score_0_100` | `msc.score` | float | |
| `monetary_cycle_scores` | `regime_3band` | `msc.regime_3band` | enum | `ACCOMMODATIVE` / `NEUTRAL` / `TIGHT` |
| `monetary_cycle_scores` | `dilemma_overlay_active` | `msc.dilemma_active` | bool | |
| `monetary_cycle_scores` | `confidence` | `msc.confidence` | float | |

The MSC 3-band regime is used (not the 6-band) to keep the decision
tree tractable; finer MSC nuance survives in the underlying row via
the `msc_id` foreign key.

## 3. Decision tree

Priority-ordered; first predicate that evaluates `True` wins. Each
branch names the `classification_reason` string emitted on the result.

| Priority | Meta-regime | Predicate | `classification_reason` |
|---|---|---|---|
| 1 | `stagflation_risk` | `ecs.stagflation_active AND msc.dilemma_active` | `stagflation+dilemma` |
| 2 | `recession_risk` | `ecs.regime IN (EARLY_RECESSION, RECESSION) AND cccs.regime IN (DISTRESS, REPAIR)` | `recession+distress` |
| 3 | `late_cycle_bubble` | `fcs.regime == EUPHORIA AND fcs.bubble_warning_active AND cccs.regime == SPECULATION` | `euphoria+bubble+speculation` |
| 4 | `overheating` | `ecs.regime == PEAK_ZONE AND cccs.regime == BOOM AND fcs.regime IN (OPTIMISM, EUPHORIA) AND NOT msc.dilemma_active` | `peak+boom+optimism` |
| 5 | `soft_landing` | `ecs.regime == EXPANSION AND cccs.regime IN (RECOVERY, BOOM) AND fcs.regime IN (OPTIMISM, CAUTION) AND msc.regime_3band == NEUTRAL` | `expansion+neutral` |
| 6 | `unclassified` | default (no predicate matched) | `default` |

Any cycle that is `None` (Policy 1 pass-through — see §4) is treated
as a neutral input by each predicate: a predicate that references the
missing cycle evaluates to `False`. This biases the classifier toward
the more specific branches only firing when their evidence is
actually present; if the evidence is missing, the decision flows
downward and often lands on `unclassified`.

## 4. Policy 1 fail-mode

L5 extends the L4 Policy 1 convention from
[`../conventions/composite-aggregation.md`](../conventions/composite-aggregation.md).

- **Minimum coverage** — at least **3 of 4** L4 cycles must be
  present. Below that the classifier raises
  :class:`InsufficientL4DataError`; no L5 row is persisted.
- **Missing cycle flag** — for each `None` input, the L5 row emits
  the corresponding `L5_{CYCLE}_MISSING` flag (e.g.
  `L5_ECS_MISSING`).
- **Confidence cap** — L5 confidence is `min(confidences of present
  cycles)`, capped at **0.75** when exactly one cycle is missing.
  The 2-missing case is unreachable (exception fires first) but the
  nominal cap is 0.60 — documented for forward compatibility.

## 5. Confidence

`confidence_l5 = min({c.confidence for c in present_cycles})` with
the cap described above. The minimum-of-minimums rule matches the
existing L4 cycle conventions and keeps L5 strictly no-more-confident
than its least-certain input.

## 6. Outputs

Persisted to the `l5_meta_regimes` table (migration 017):

| Field | Type | Description |
|---|---|---|
| `l5_id` | UUID | Primary key |
| `country_code` | str (ISO 3166-1 α-2) | |
| `date` | date | Matches the L4 date for that triplet |
| `meta_regime` | enum | One of the six canonical values |
| `ecs_id` / `cccs_id` / `fcs_id` / `msc_id` | UUID FK | Nullable; populated with the L4 row id used |
| `confidence` | float [0, 1] | Post-cap |
| `flags` | CSV | `L5_OVERHEATING`, `L5_STAGFLATION_RISK`, ..., plus `L5_{CYCLE}_MISSING` when applicable |
| `classification_reason` | str | Branch identifier from §3 |
| `methodology_version` | str | `L5_META_REGIME_v0.1` |
| `created_at` | datetime | Audit timestamp |

## 7. Canonical fixtures

The L5 classifier ships with 8 canonical fixtures under
`tests/unit/test_regimes/fixtures/`. Each fixture is a JSON payload
serialising the four L4 cycle shapes into
`sonar.regimes.types.L5RegimeInputs`; the tests assert the expected
`meta_regime` and `classification_reason`.

| Fixture | Target regime | Scenario |
|---|---|---|
| `fixture_1_overheating.json` | `overheating` | US 2021-Q2-ish peak + boom + optimism |
| `fixture_2_stagflation_risk.json` | `stagflation_risk` | US 1974-ish stagflation + dilemma |
| `fixture_3_late_cycle_bubble.json` | `late_cycle_bubble` | US 2007-Q2-ish euphoria + bubble warning + speculation |
| `fixture_4_recession_risk.json` | `recession_risk` | US 2009-Q1-ish recession + distress |
| `fixture_5_soft_landing.json` | `soft_landing` | US 2015-ish expansion + recovery + neutral MSC |
| `fixture_6_unclassified.json` | `unclassified` | Transitional: neither peak nor recession, mixed signals |
| `fixture_7_ecs_missing.json` | `unclassified` | 3/4 cycles — ECS slot `None` |
| `fixture_8_insufficient.json` | (raises) | 2/4 cycles — triggers `InsufficientL4DataError` |

Adding fixtures is welcome whenever a new production configuration
stresses the decision tree.

## 8. Flag lexicon (extension)

New L5 flags land in [`../conventions/flags.md`](../conventions/flags.md).
The classifier emits a regime-level flag for every successful
classification plus a per-cycle missing flag when applicable.

- `L5_OVERHEATING`, `L5_STAGFLATION_RISK`, `L5_LATE_CYCLE_BUBBLE`,
  `L5_RECESSION_RISK`, `L5_SOFT_LANDING`, `L5_UNCLASSIFIED`
- `L5_ECS_MISSING`, `L5_CCCS_MISSING`, `L5_FCS_MISSING`,
  `L5_MSC_MISSING`
- `L5_INSUFFICIENT_CYCLES` — raised via exception, never persisted as
  a flag.

## 9. Methodology version

`L5_META_REGIME_v0.1` encodes the taxonomy + decision tree frozen in
this document. Any change to §3 or §4 requires a minor bump; any
change to §2 (inputs) requires a major bump per
[`../conventions/methodology-versions.md`](../conventions/methodology-versions.md).
