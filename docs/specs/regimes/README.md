# L5 Regime Layer — Cross-Cycle Meta-Regime Classification

**Status**: Phase 2 transition — spec shipped Week 8 Sprint H.

---

## 1. Layer purpose

L5 sits on top of the four L4 cycle composites (CCCS + FCS + MSC + ECS)
and consolidates them into a single **cross-cycle meta-regime** per
`(country, date)` triplet. Where L4 answers "what does each cycle
look like?", L5 answers "what macro configuration is the country
in?".

L5 is **not** another compute layer for cycle scores — it reads the
persisted L4 rows via foreign keys and applies a rule-based
classifier. Phase 1 ships a **simple 6-band taxonomy**; Phase 2+ may
replace the rule tree with an ML classifier once ≥ 24 months of
production cycle data are available for training.

## 2. Six canonical meta-regimes

Phase 1 / Option B taxonomy:

| Meta-regime | Canonical shape |
|---|---|
| `overheating` | Economic peak + credit boom + financial optimism; no policy dilemma |
| `stagflation_risk` | Stagflation overlay firing on ECS + dilemma overlay firing on MSC |
| `late_cycle_bubble` | Financial euphoria + bubble-warning active + credit speculation |
| `recession_risk` | Economic recession regime + credit distress / repair |
| `soft_landing` | Expansion + credit recovery + financial optimism/caution + monetary neutral |
| `unclassified` | Transitional configurations that don't match any of the above (also used when the classifier cannot decide decisively) |

The classifier evaluates the decision tree in priority order (first
match wins); see
[`cross-cycle-meta-regimes.md`](cross-cycle-meta-regimes.md) §3.

## 3. Design principles

1. **Read-only of L4** — L5 never recomputes cycle scores. It
   consumes `economic_cycle_scores.score_0_100`, `.regime`,
   `.stagflation_overlay_active`, etc. as inputs.
2. **FK-linked rows** — each L5 row carries the four L4 UUIDs
   (`ecs_id`, `cccs_id`, `fcs_id`, `msc_id`) it was derived from,
   nullable to accommodate Policy 1 ≥ 3/4 fail-mode.
3. **Rule-based / auditable** — decision tree is documented explicitly;
   every classification has a `classification_reason` string
   identifying the branch that matched.
4. **Policy 1 fail-mode extension** — L5 classifies whenever at
   least 3 of the 4 L4 cycles are present; fewer than 3 raises
   :class:`InsufficientL4DataError`. See
   [`integration-with-l4.md`](integration-with-l4.md) §3.
5. **Confidence inheritance** — L5 confidence is the minimum of the
   available L4 confidences, capped at 0.75 when one cycle is missing
   (the 2-missing case triggers the exception and doesn't produce a
   row).

## 4. Scope explicitly out of Phase 1

- Live integration in `daily_cycles.py` (Sprint H ships foundation
  only; daily wiring lands in a follow-on Week 8 sprint).
- Backfill of existing cycle rows with historical L5 classifications.
- **L5b cross-cycle diagnostics matrix** (4 × 4 cycle-vs-cycle
  interaction map) — Phase 2+.
- Empirical threshold calibration (needs ≥ 24 m production data).
- ML classifier variant.

## 5. References

- [`cross-cycle-meta-regimes.md`](cross-cycle-meta-regimes.md) —
  taxonomy + decision tree + inputs/outputs schemas.
- [`integration-with-l4.md`](integration-with-l4.md) — FK pattern +
  Policy 1 integration + flag lexicon extensions.
- [`../../adr/ADR-0006-l5-regime-classifier.md`](../../adr/ADR-0006-l5-regime-classifier.md)
  — design decisions + rejected alternatives.
- [`../conventions/composite-aggregation.md`](../conventions/composite-aggregation.md)
  — Policy 1 pattern.
- [`../conventions/flags.md`](../conventions/flags.md) — flag lexicon
  L5_* additions.
- [`../cycles/`](../cycles/) — 4 L4 cycle specs (CCCS / FCS / MSC /
  ECS) with embedded overlays feeding L5 inputs.

---

_L5 introduced Week 8 Sprint H as Phase 2 foundation work._
