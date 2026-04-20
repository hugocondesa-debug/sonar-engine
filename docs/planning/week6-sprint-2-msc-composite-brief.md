# Week 6 Sprint 2 — MSC Monetary Stance Composite

**Target**: Ship 3rd L4 cycle composite (MSC) using shipped M1/M2/M3/M4 compute layer. Mirror CCCS/FCS pattern.
**Priority**: HIGH (L4 3/4 after ship; only ECS composite remaining for full L4 coverage)
**Budget**: 3-4h CC autonomous
**Commits**: ~7-9
**Base**: main HEAD post Sprint 1 + 1b (`3f5417f` or later)
**Concurrency**: Parallel to Week 6 Sprint 2b Monetary Ingestion Omnibus in tmux `sonar-l3`. See §3.

---

## 1. Scope

In:
- `src/sonar/cycles/monetary_msc.py` — MSC composite per spec `cycles/monetary-msc.md`
- Alembic migration **015** — `monetary_cycle_scores` table per spec naming
- MonetaryCycleScore ORM inside existing `# === Cycle models ===` bookmark (adjacent CreditCycleScore + FinancialCycleScore from Sprint 2b)
- Reuse existing CycleCompositeBase ABC + Policy 1 helper from Sprint 2b
- Integration tests 7 T1 countries (US + EA focus; others spec-intent partial)
- Orchestrator extension: `compute_all_cycles` already shipped — just add MSC to the dict
- Persistence helper `persist_msc_result`
- Retrospective

Out:
- ECS composite (depends on Week 5 Sprint 2a Eurostat ingestion + E1/E3/E4 real rows — ECS composite Week 7)
- Regime classifier (needs all 4 cycles — pending after ECS)
- M1/M2/M4 connector wiring (separate Track B sprint this session)
- MSC backtest vs historical NBER/CEPR (Phase 4 calibration scope)

---

## 2. Spec reference

Authoritative (likely exists — verify Commit 1):
- `docs/specs/cycles/monetary-msc.md` — MSC formula, regimes, Policy 1 handling
- `docs/specs/indices/monetary/README.md` — MSC formula preview `0.30·M1 + 0.15·M2 + 0.35·M3 + 0.20·M4`
- `docs/specs/conventions/composite-aggregation.md` — Policy 1 fail-mode
- SESSION_CONTEXT §Decision authority

**Pre-flight requirement**: Commit 1 CC reads:
1. `cycles/monetary-msc.md` end-to-end (if exists)
2. `indices/monetary/README.md` for formula confirmation
3. Sprint 2b CCCS + FCS implementations as reference pattern

If `cycles/monetary-msc.md` exists and has material deviations from brief §4 assumptions, document in commit body. Do NOT HALT unless architectural incompatibility or scope > 2x budget (pattern established Week 5/6).

Likely MSC formula per monetary README:
```
MSC = 0.30·M1 + 0.15·M2 + 0.35·M3 + 0.20·M4
```

Sign convention: **higher = tighter stance** (same as M1/M2/M3/M4 sub-indices — monetary cycle is tightness direction).

Existing assets from Sprint 2b:
- `src/sonar/cycles/base.py` — CycleCompositeBase ABC + Policy 1 helper
- `src/sonar/cycles/credit_cccs.py` — reference pattern
- `src/sonar/cycles/financial_fcs.py` — reference pattern
- `src/sonar/cycles/orchestrator.py` — already returns {'CCCS', 'FCS'}, extend to include 'MSC'
- `src/sonar/db/models.py` Cycle bookmark zone — add MonetaryCycleScore ORM

---

## 3. Concurrency — parallel protocol with Ingestion Omnibus

Ingestion Omnibus runs concurrently in tmux `sonar-l3`. Both push to main.

**Hard-locked resource allocation**:
- Migration number: **015** (Ingestion Omnibus doesn't create migrations — verify)
- `src/sonar/db/models.py`: this brief adds MonetaryCycleScore inside `# === Cycle models ===` bookmark (existing). Ingestion Omnibus doesn't touch models.py.
- `src/sonar/cycles/`: new file `monetary_msc.py`. Zero overlap.
- `src/sonar/connectors/`: **DO NOT TOUCH** — Ingestion Omnibus owns. This brief reads from persisted tables only.
- `src/sonar/indices/monetary/builders.py`: **DO NOT CREATE** — Ingestion Omnibus owns (CAL-100).
- Tests: separate test files per pattern
- `pyproject.toml`: no new deps

**Push race**:
- Normal `git pull --rebase origin main`
- Zero file collisions expected

**Start order**: this brief arranca primeiro. Ingestion Omnibus ~1 min depois.

---

## 4. Commits

### Commit 1 — MonetaryCycleScore ORM + migration 015

```
feat(cycles): MonetaryCycleScore ORM + migration 015

In src/sonar/db/models.py inside existing # === Cycle models === bookmark
(append after FinancialCycleScore from Sprint 2b):

MonetaryCycleScore ORM:
- id, country_code, date, methodology_version
- score_composite [0-100] CHECK
- confidence [0-1] CHECK
- sub_index_contributions TEXT (JSON)
- regime_phase TEXT (classification per spec — likely TIGHT/NEUTRAL/LOOSE or similar)
- regime_persistence_days INTEGER (hysteresis tracking per spec if applicable)
- flags TEXT (CSV)
- source_cycle TEXT = 'MSC'
- created_at
- UNIQUE (country_code, date, methodology_version)
- Index idx_msc_cd on (country_code, date)

Per-spec extras if spec §8 requires (likely minimal — composites derive from sub-index rows):
- m1_contribution_pct, m2_contribution_pct, m3_contribution_pct, m4_contribution_pct (audit)
- m{1,2,3,4}_weight_effective (Policy 1 re-weighting audit)

Alembic migration 015:
CREATE TABLE monetary_cycle_scores (... per ORM ...)

Pre-flight:
- Verify alembic heads = 014 (monetary indices migration from Sprint 1b).
- If 015 claimed elsewhere (shouldn't), bump.

Sanity check commit body:
  python -c "from sonar.db.models import MonetaryCycleScore; print('OK')"

Migration upgrade/downgrade round-trip clean.

Tests: 6 ORM constraint tests.
```

### Commit 2 — MSC composite implementation

```
feat(cycles): MSC composite per monetary-msc spec

src/sonar/cycles/monetary_msc.py:

class MscComposite(CycleCompositeBase):
    METHODOLOGY_VERSION = "MSC_COMPOSITE_v0.1"
    TABLE_NAME = "monetary_cycle_scores"
    SPEC_WEIGHTS = {
        "M1": 0.30,
        "M2": 0.15,
        "M3": 0.35,
        "M4": 0.20,
    }
    MIN_REQUIRED = 3  # Policy 1: 3 of 4

def compute(country, date, session) -> MonetaryCycleScore:
    1. Query sub-index tables for (country, date):
       - M1 from monetary_m1_effective_rates
       - M2 from monetary_m2_taylor_gaps
       - M3 from monetary_m3_market_expectations (shipped Week 3.5)
       - M4 from monetary_m4_fci

    2. Each sub-index contributes score_normalized + confidence

    3. Apply Policy 1 fail-mode via base helper:
       - If any sub-index missing → flag {INDEX}_MISSING + re-weight
       - ≥ 3 of 4 required else raise InsufficientCycleInputsError
       - Confidence cap 0.75 re-weight active

    4. Weighted aggregate:
       MSC = 0.30·M1 + 0.15·M2 + 0.35·M3 + 0.20·M4 (per spec/README)

    5. Regime classification per spec:
       (if spec-defined) TIGHT (>75?) / NEUTRAL (25-75?) / LOOSE (<25?)
       — verify exact boundaries in spec monetary-msc.md
       If spec §7 uses placeholder "recalibrate Phase 4", ship placeholder +
       flag PLACEHOLDER_THRESHOLDS

    6. Hysteresis (if spec requires — check monetary-msc.md):
       regime_persistence_days via previous row lookup
       Threshold Δ > X + persistence ≥ Y BD

    7. Confidence propagation (Policy 1 cap) + flags

    8. Sub-index contributions audit per spec §8

Persist via persist_msc_result helper.

Countries:
- US: full stack (M1 US + M2 US + M3 US + M4 US all shipped)
- EA aggregate: M1 EA (Sprint 1b) + M3 EA (Week 3.5) + partial M2/M4 if data available
- PT/IT/ES/FR/NL: M1 EA proxy (Sprint 1b handles flags) + M3 partial; M2/M4 deferred
  → likely fails Policy 1 MIN_REQUIRED 3 of 4 → raise InsufficientCycleInputsError
- UK/JP: pending Week 7 BoE/BoJ connectors

Document per-country coverage matrix in retro.

Behavioral tests ≥ 20; coverage ≥ 90%.
```

### Commit 3 — Orchestrator extension + CLI

```
feat(cycles): extend orchestrator with MSC

src/sonar/cycles/orchestrator.py:
- compute_all_cycles now returns {'CCCS', 'FCS', 'MSC'}
- Gracefully handle InsufficientCycleInputsError for MSC (non-US/EA countries likely raise)

CLI flag --cycles-only existing; MSC picked up automatically.

python -m sonar.cycles.orchestrator --country US --date 2024-12-31
  → 3 rows now (CCCS + FCS + MSC)

Tests: 4 unit tests covering:
- US 2024-12-31: 3 cycles all compute (if sub-indices seeded)
- Country with M-data gaps: MSC skipped gracefully (others continue)

Coverage orchestrator.py ≥ 90%.
```

### Commit 4 — Integration test: MSC 7 T1 countries

```
test(integration): MSC composite 7 T1 countries vertical slice

tests/integration/test_msc_composite.py:

Parametrized 7-country test for 2024-12-31:
- Fixtures: pre-seed monetary_m{1,2,3,4}_* tables with synthetic rows
  appropriate for each country's coverage tier:
  - US: all 4 rows
  - EA aggregate: M1 + M3 rows
  - PT/IT/ES/FR/NL: M3 only (likely raises Policy 1)
  - UK/JP: no rows (raises)

Assertions:
- US: MSC row persisted, score_composite ∈ [0, 100], regime assigned
- EA: MSC row persisted (2 sub-indices available if tier allows;
  else raise per spec minimum)
- Others: InsufficientCycleInputsError raised gracefully

Policy 1 validation:
- Test with M2 missing but M1/M3/M4 present → re-weight + persist + flag
- Test with 2 missing → raise

≥ 12 integration tests.
```

### Commit 5 — Smoke test: MSC US end-to-end

```
test(integration): MSC US live smoke

tests/integration/test_msc_smoke.py:

@pytest.mark.slow
def test_msc_us_smoke():
    """Compute MSC for US 2024-12-31 against whatever is in DB.
    Assert:
    - Row persisted
    - score_composite ∈ [0, 100]
    - Given Fed hawkish stance 2024: expect regime TIGHT or high neutral
      (score > 55 likely)
    - Confidence ≥ 0.60 given degraded M4 if pending + synthetic contributions
    - Print scorecard for retrospective"""

Note: this runs on whatever's persisted. If Sprint 2b Ingestion Omnibus
lands real M1/M2/M4 US data, smoke uses real data. Otherwise synthetic
from test fixtures seeded earlier.
```

### Commit 6 — Retrospective + CAL closure if any

```
docs(planning): Week 6 Sprint 2 MSC composite retrospective

File: docs/planning/retrospectives/week6-sprint-2-msc-composite-report.md

Structure per prior retrospectives:
- Summary (duration, commits, status)
- Commits table with SHAs
- Coverage delta
- 7-country MSC snapshot for 2024-12-31:
  - scores + regime phases per country
  - Policy 1 applications (who re-weighted, who raised)
- Synthetic vs real data acknowledgment:
  - Depends on Sprint 2b Ingestion Omnibus ship state
- HALT triggers (likely only #0 if spec deviation)
- Deviations from brief
- New backlog items (unlikely — MSC is math, mostly reuse)
- Sprint 3 readiness:
  - 3/4 L4 cycles done (CCCS + FCS + MSC)
  - ECS composite pending E1/E3/E4 real data
  - Regime classifier needs ECS composite
- Concurrency report with Sprint 2b
```

---

## 5. HALT triggers (atomic)

0. **Pre-flight spec deviation** — MSC spec may have richer regime classification or hysteresis than brief assumes. Document + honor spec. HALT only if scope > 2x budget.
1. **monetary-msc.md absent** from specs/ — use README formula + CCCS/FCS pattern as fallback. Document.
2. **Hysteresis mechanics** — if spec requires previous-row lookup similar to CCCS, implement. If absent, skip (optional feature).
3. **Regime boundary ambiguity** — use placeholder if spec marks "Phase 4 recalibrate"; flag PLACEHOLDER_THRESHOLDS.
4. **Migration 015 collision** with Ingestion Omnibus (shouldn't) → rebase.
5. **models.py rebase conflict outside Cycle bookmark** — Ingestion Omnibus violated discipline → HALT, reconcile.
6. **Policy 1 math inconsistency** with Sprint 2b implementation — reuse base helper exactly; if helper API changed, HALT.
7. **Coverage regression > 3pp** → HALT.
8. **Pre-push gate fails** → fix before push, no `--no-verify`.
9. **ORM silent drop** at Commit 1 — sanity check mandatory.

---

## 6. Acceptance

### Per commit
Commit body checklist.

### Global sprint-end
- [ ] 6-7 commits pushed, main HEAD matches remote, CI green
- [ ] Migration 015 clean
- [ ] `src/sonar/cycles/monetary_msc.py` coverage ≥ 90%
- [ ] MSC computes + persists for US (synthetic or real inputs)
- [ ] Policy 1 fail-mode validated
- [ ] Orchestrator returns 3 cycles {CCCS, FCS, MSC}
- [ ] Full pre-push gate green every push (full mypy + ruff + pytest)
- [ ] No `--no-verify`

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week6-sprint-2-msc-composite-report.md`

**Final tmux echo**:
```
MSC COMPOSITE DONE: N commits, MSC operational
US 2024-12-31: MSC=X (regime TIGHT/NEUTRAL/LOOSE)
L4 cycles status: CCCS ✓ FCS ✓ MSC ✓ ECS pending
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/week6-sprint-2-msc-composite-report.md
```

---

## 8. Pre-push gate (mandatory)

```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov
```

Full project mypy. No `--no-verify`.

---

## 9. Notes on implementation

### Simpler than CCCS/FCS
MSC formula is clean 4-term weighted sum. No double-use, no special mapping. Should be easiest of the 4 composites.

### Spec monetary-msc.md may not exist
If absent, compose from monetary README + spec-indices pattern. Document clearly in commit body. Treat placeholder regimes flag.

### M3 already provides dual-use (EP + CS)
Per monetary README, M3 contributes both Expected Path (25%) and Credibility Signal (10%) = 35% combined. Formula treats M3 as single term with 35% weight. No need to split.

### Synthetic data is fine this sprint
MSC reads from persisted M1/M2/M3/M4 rows. If Sprint 2b Ingestion Omnibus lands real data, MSC auto-upgrades. Compute side doesn't care.

### Parallel Ingestion Omnibus
Runs in tmux `sonar-l3`. Zero file overlap per §3. Pre-push gate catches.

---

*End of Week 6 Sprint 2 MSC composite brief. 6-7 commits. 3/4 L4 cycles operational post-ship.*
