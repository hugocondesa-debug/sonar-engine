# Week 6 Sprint 2 — MSC Monetary Stance Composite

**Brief:** `docs/planning/week6-sprint-2-msc-composite-brief.md`
**Duration:** ~2.5h (2026-04-20)
**Commits:** 6 (all pushed to main; CI green)
**Status:** SPRINT CLOSED — 3/4 L4 cycles operational

---

## 1. Summary

Shipped the third L4 cycle composite (MSC) on top of the M1/M2/M3/M4
sub-indices that landed earlier this week. The spec (`cycles/
monetary-msc.md`) turned out to be substantially richer than the brief
assumed — 5 inputs instead of 4, two-track regime classification
(6-band + 3-band), hysteresis, and a Dilemma Trigger A overlay. All
spec features landed; brief assumptions were reconciled in commit
bodies and this retrospective.

MSC US 2024-12-31 smoke lands at **score 61.33, regime NEUTRAL_TIGHT /
3-band TIGHT**, confidence 0.62, 4/5 inputs (CS family not yet
shipped — COMM_SIGNAL_MISSING flag on every Phase 0-1 row).

## 2. Commits

| # | SHA | Title | Gate |
|---|-----|-------|------|
| 1 | `e6d06b7` | feat(cycles): MonetaryCycleScore ORM + migration 015 | green |
| 2 | `f73717a` | feat(cycles): MSC composite per monetary-msc spec | green |
| 3 | `88abae3` | feat(cycles): extend orchestrator with MSC | green |
| 4 | `4557629` | test(integration): MSC composite 7 T1 countries vertical slice | green |
| 5 | `95ef490` | test(integration): MSC US end-to-end smoke with scorecard | green |
| 6 | _this doc_ | docs(planning): retrospective | pending |

Pre-push gate green before every push (ruff format --check, ruff check,
full-project mypy, `pytest tests/unit/ -x --no-cov` excluding
tests/unit/test_db/test_economic_models orphan). No `--no-verify`.

## 3. Spec deviations from brief (HALT #0 soft)

Brief §4 assumed a 4-input formula `0.30·M1 + 0.15·M2 + 0.35·M3 + 0.20·M4`.
Spec `cycles/monetary-msc.md` carries a 5-input formula with distinct
M3 and CS terms:

```
MSC_t = 0.30·M1 + 0.15·M2 + 0.25·M3 + 0.20·M4 + 0.10·CS
```

Other spec-honored features the brief did not pre-declare:

- **Two-track regime classification**: `regime_6band` (6-band per Cap
  15.8: STRONGLY_ACCOMMODATIVE .. STRONGLY_TIGHT) + `regime_3band`
  (consumer convenience: ACCOMMODATIVE / NEUTRAL / TIGHT).
- **Hysteresis**: `|Δscore| > 5` threshold with `≥ 3`-business-day
  sustained streak. Sticky branches emit `REGIME_HYSTERESIS_HOLD`.
- **Dilemma Trigger A overlay**: when `score > 60` + anchor drifting
  + ECS < 55. ECS composite not yet shipped → Phase 0-1 emits
  `DILEMMA_NO_ECS` flag and leaves the overlay inactive.
- **Confidence formula**: `min(sub_confidences) · (available / 5)`
  with 0.75 cap when any slot is missing.

Per brief HALT #0 rule ("document + honor spec; HALT only if scope >
2x budget") the extra scope added ~45 minutes to Commit 2 — well
within the 3-4h total — so no HALT fired. The richer ORM ships in
Commit 1 to avoid a mid-sprint migration churn.

## 4. Commits detail

### C1 — ORM + migration 015

`MonetaryCycleScore` appended inside the existing `# === Cycle
models ===` bookmark. Schema mirrors spec §8 end-to-end (msc_id UUID,
per-input score + weight, inputs_available [3,5] CHECK, both regime
columns with enum CHECKs, Dilemma fields, 24 columns total).
Migration 015 upgrade + downgrade round-trip clean. 9 ORM constraint
tests.

Sanity: `python -c "from sonar.db.models import MonetaryCycleScore; print('OK')"`
→ OK.

### C2 — MSC composite

`src/sonar/cycles/monetary_msc.py` reads M1/M2/M4 from the dedicated
tables and M3 from `index_values` (polymorphic, `index_code =
"M3_MARKET_EXPECTATIONS"`). Applies Policy 1 re-weight via the
shared `apply_policy_1` helper from Sprint 2b.

32 unit tests cover: weight constants + spec-formula equality, both
regime classifiers (6 + 3 band with boundary cases), hysteresis
(cold-start / same / large Δ / small Δ sticky / boundary Δ=5),
compute_msc end-to-end (full 4 inputs, persist round-trip, 1 input →
raise, 2 inputs → raise, 3 inputs suffices, hysteresis against
previous row, DILEMMA_NO_ECS, sub-index flag inheritance, tight
regime, accommodative regime, canonical weighted-sum arithmetic).

### C3 — Orchestrator extension

`compute_all_cycles` grows from `{cccs, fcs}` to `{cccs, fcs, msc}`.
`CyclesOrchestrationResult` gains `.msc`. MSC attempt is wrapped in
try/`InsufficientCycleInputsError` catch so a missing M-stack doesn't
sink the other two cycles. CLI log now emits `msc_score` +
`msc_regime_6band` + `msc_regime_3band`.

### C4 — 7-country vertical slice

Parametrized test matrix:

| Country | Seeded | Expected | Inputs |
|---------|--------|----------|--------|
| US | M1+M2+M3+M4 | persists | 4 |
| DE / IT / ES / FR / NL | M1+M3+M4 (R_STAR_PROXY) | persists | 3 |
| PT | M3 only | raises | — |
| UK / JP | no rows | raises | — |

Plus 5 Policy 1 edge cases (M2 missing, two-inputs raises, MIN_INPUTS
constant, confidence cap, canonical weighted-sum). 14 tests total.

### C5 — US smoke

Seeds a plausible Fed 2024-12-31 hawkish snapshot (rates 5.25%,
real rate 2.4%, Taylor gap +0.95pp, anchor 0.45z, FCI mildly tight)
and computes MSC end-to-end. Scorecard captured:

```
MSC US 2024-12-31:
  score_0_100         = 61.33
  regime_6band        = NEUTRAL_TIGHT
  regime_3band        = TIGHT
  inputs_available    = 4/5
  effective weights   = M1 0.333 / M2 0.167 / M3 0.278 / M4 0.222
  confidence          = 0.62
  flags               = ('COMM_SIGNAL_MISSING',)
```

Assertions: score in [0, 100], regime valid enum, score > DILEMMA_MSC_
THRESHOLD (60), regime_3band == "TIGHT", confidence ≥ 0.60,
COMM_SIGNAL_MISSING flag present.

## 5. Per-country MSC coverage (synthetic 2024-12-31)

| Country | Seeded | MSC score | regime_6band | regime_3band | Flags |
|---------|--------|-----------|--------------|--------------|-------|
| US | full stack | 61.33 | NEUTRAL_TIGHT | TIGHT | COMM_SIGNAL_MISSING |
| DE | M1+M3+M4 (proxy) | ≈51 | NEUTRAL_TIGHT | NEUTRAL | M2_MISSING, COMM_SIGNAL_MISSING, R_STAR_PROXY |
| IT/ES/FR/NL | M1+M3+M4 (proxy) | ≈51 | NEUTRAL_TIGHT | NEUTRAL | same |
| PT | M3 only | — | — | — | raises InsufficientCycleInputsError |
| UK | — | — | — | — | raises |
| JP | — | — | — | — | raises |

Synthetic-data caveat: Sprint 2b Ingestion Omnibus was still landing
real data while this sprint ran (SHAs `bdaea88`, `2f38a82`, `c82ce18`
showed FRED monetary + CBO gap + ECB SDW connectors land). Once the
real-data daily pipeline runs, MSC rows upgrade from synthetic to
live automatically — compute side reads whatever's persisted.

## 6. Policy 1 validation

- 4 inputs + CS missing → re-weight over 0.90 weight-pool, confidence
  capped at 0.75. Exercised across all US tests.
- 3 inputs (M2 dropped) → re-weight over 0.75 pool, M2_MISSING flag,
  confidence ≤ 0.75. Exercised in TestPolicy1.
- 2 inputs → raises `InsufficientCycleInputsError`. Exercised in 3
  locations (unit + integration + orchestrator paths).
- Canonical weighted-sum arithmetic sanity: manual expected value
  asserted with 0.01 tolerance (unit + integration).

## 7. HALT triggers

- **#0 (pre-flight)**: fired soft on spec deviation; documented +
  honored per rule. Cost ~45 min, below 2x-budget threshold.
- **#1 (monetary-msc.md absent)**: not fired — spec present.
- **#2 (hysteresis mechanics)**: fired informationally — spec does
  require hysteresis, implemented.
- **#3 (regime boundary ambiguity)**: spec bands are concrete, no
  placeholder needed.
- **#4 (migration 015 collision)**: not fired.
- **#5 (models.py bookmark discipline)**: not fired — Ingestion
  Omnibus respected zone separation.
- **#6 (Policy 1 math inconsistency)**: reused `apply_policy_1`
  verbatim; `CS_MISSING` renamed to `COMM_SIGNAL_MISSING` per spec.
- **#7 / #8 / #9**: not fired.

## 8. Deviations from brief

- Canonical weights: 5-input `{M1: 0.30, M2: 0.15, M3: 0.25, M4: 0.20,
  CS: 0.10}` replacing brief's 4-input `0.30/0.15/0.35/0.20`.
- Both `regime_6band` and `regime_3band` persisted (brief mentioned
  a single `regime_phase`).
- Dilemma overlay fields (`dilemma_overlay_active`,
  `dilemma_trigger_json`) added per spec §8.
- Confidence formula uses `available / 5` scaling, not a flat min
  propagation.
- Commit count: 6 (not 7-9). Brief's extra commits were subsumed
  into C1's richer ORM.

## 9. Concurrency with Sprint 2b Ingestion Omnibus

MSC and Ingestion Omnibus interleaved cleanly:

- Migration numbers: MSC took 015; Ingestion Omnibus did not create
  any migration this sprint.
- `models.py`: MSC stayed inside the `# === Cycle models ===`
  bookmark. Ingestion Omnibus stayed in connectors/.
- `src/sonar/cycles/`: MSC-only files. Ingestion Omnibus did not
  touch cycles.
- `src/sonar/connectors/`: Ingestion Omnibus-only (per brief §3
  "DO NOT TOUCH"). MSC reads from persisted tables.
- Four push-races observed (bdaea88, 2f38a82, c82ce18) resolved via
  `git stash push -u -- docs/planning/` before committing +
  `git stash pop` after, avoiding pre-commit auto-fix conflicts on
  concurrent-brief untracked files.

Zero code collision; zero rebase required.

## 10. New backlog items

None. MSC ships self-contained. CAL-099 (TE rate-limit production
monitoring) and CAL-101 (CS connector family: central_bank_nlp /
fed_dissent / fomc_sep) can be filed if/when Phase 2+ requirements
crystallise; not filed this sprint.

## 11. Sprint readiness downstream

- **L4 cycles status**: CCCS ✓ FCS ✓ MSC ✓ — **3/4 operational**.
- **ECS composite (L4 #4)**: pending Week 5 Sprint 2a ingestion +
  E1/E3/E4 real-data rows. Week 7 target.
- **Regime classifier**: needs all 4 cycles. Post-ECS.
- **integration/matriz-4way (L6)**: can now consume MSC
  `regime_3band` + `score_0_100`. Input for Week 7.
- **integration/cost-of-capital (L6)**: MSC `score_0_100` stance
  feed available for the forward-path-adjusted discount computation.

*End of retrospective. Sprint CLOSED 2026-04-20.*
