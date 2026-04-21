# Week 8 Sprint K — L5 daily_cycles Wiring + sonar status CLI Integration

**Target**: Wire `MetaRegimeClassifier` into `daily_cycles.py` pipeline + extend `sonar status` CLI to display L5 meta-regime. Complete vertical slice L4 → L5 → user-facing output.
**Priority**: HIGH (Phase 2 first visible deliverable; L5 becomes operational not just foundation)
**Budget**: 2.5-3h CC autonomous
**Commits**: ~6-8
**Base**: main HEAD post Week 8 Day 1 (`ca0034f` or later)
**Concurrency**: Parallel to Sprint I-patch TE cascade in tmux `sonar`. See §3.

---

## 1. Scope

In:
- Extend `src/sonar/pipelines/daily_cycles.py` to invoke L5 classifier post-L4 orchestrator:
  - After `compute_all_cycles` returns `CyclesOrchestrationResult`
  - Build `L5RegimeInputs` from the 4 L4 results (using Snapshot dataclasses per Sprint H design)
  - Invoke `MetaRegimeClassifier().classify(inputs)`
  - Persist via `persist_l5_meta_regime_result`
  - Handle `InsufficientL4DataError` as structured skip (log + continue; not crash)
- Extend `src/sonar/cli/status.py`:
  - Add `l5_meta_regime` field to `CountryStatus` dataclass
  - Query `l5_meta_regimes` table for (country, date) latest
  - Display in summary table + verbose output
  - Color coding per regime (6 colors)
- Integration smoke test: seed L4 rows → run daily_cycles → verify L5 persisted → query sonar status → verify display
- Optional backfill script `scripts/backfill_l5.py` (if budget permits): iterate existing cycle dates + retroactively classify
- Retrospective

Out:
- L5b cross-cycle 4×4 matrix (Phase 2+ per ADR-0006)
- ML classifier upgrade (Phase 2+ when 24m production data available)
- L5 regime confidence calibration (empirical; Phase 2+)
- New meta-regimes beyond canonical 6 (frozen at L5_META_REGIME_v0.1)
- Historical backfill beyond recent months (low priority; production data < 1m old)
- L5 integration in `daily_economic_indices` / `daily_monetary_indices` / other pipelines (out of scope; L5 reads cycles table)

---

## 2. Spec reference

Authoritative:
- `docs/specs/regimes/README.md` (Sprint H shipped)
- `docs/specs/regimes/cross-cycle-meta-regimes.md` (Sprint H shipped — decision tree)
- `docs/specs/regimes/integration-with-l4.md` (Sprint H shipped — FK + query patterns)
- `docs/adr/ADR-0006-l5-regime-classifier.md` (Sprint H shipped)
- `src/sonar/regimes/` package (Sprint H shipped — reference)
- `src/sonar/pipelines/daily_cycles.py` (Sprint D Week 7 shipped)
- `src/sonar/cli/status.py` (Sprint G Week 7 shipped)
- SESSION_CONTEXT §Decision authority

**Pre-flight requirement**: Commit 1 CC reads:
1. `src/sonar/regimes/meta_regime_classifier.py` — `MetaRegimeClassifier.classify` signature + `L5RegimeInputs` structure
2. `src/sonar/regimes/types.py` — Snapshot dataclasses (EcsSnapshot / CccsSnapshot / FcsSnapshot / MscSnapshot)
3. `src/sonar/cycles/orchestrator.py` — `CyclesOrchestrationResult` structure returned by `compute_all_cycles`
4. `src/sonar/pipelines/daily_cycles.py` — current implementation (post-Sprint D)
5. `src/sonar/cli/status.py` — existing CountryStatus + status rendering
6. `src/sonar/db/models.py` — `L5MetaRegime` ORM + 4 cycle ORM tables

Document pattern decisions in commit body.

Existing assets (per Sprint H retrospective):
- `MetaRegimeClassifier` with 6-regime decision tree + Policy 1 (≥ 3/4)
- `L5RegimeInputs` accepts `Snapshot | None` per cycle
- `persist_l5_meta_regime_result` raises `DuplicatePersistError`
- `InsufficientL4DataError` exception defined
- Migration 017 + `l5_meta_regimes` table live

Mapping ORM → Snapshot:
- Sprint H shipped lightweight Snapshot dataclasses decoupled from ORM
- This sprint builds Snapshots from ORM rows (read then snapshot; don't pass ORM to classifier)
- Likely helper: `_ecs_snapshot_from_orm(row: EconomicCycleScore) -> EcsSnapshot` per cycle

---

## 3. Concurrency — parallel protocol with Sprint I-patch

Sprint I-patch runs concurrently in tmux `sonar`. Both push to main.

**Hard-locked resource allocation**:
- Migration numbers: nenhuma (L5 migration 017 already shipped Sprint H)
- `src/sonar/db/models.py`: **NOT touched**
- `src/sonar/connectors/`: **NOT touched** — Sprint I-patch domain (te.py)
- `src/sonar/indices/monetary/builders.py`: **NOT touched** — Sprint I-patch domain (UK M1 cascade)
- `src/sonar/pipelines/daily_cycles.py`: this brief modifies
- `src/sonar/pipelines/daily_monetary_indices.py`: **NOT touched** (Sprint I-patch may modify)
- `src/sonar/cycles/`: read-only usage (import orchestrator)
- `src/sonar/regimes/`: read-only usage (import classifier + types)
- `src/sonar/cli/status.py`: this brief modifies
- `src/sonar/cli/main.py`: **NOT touched** (no new commands registered)
- `src/sonar/cli/health.py`: **NOT touched**
- `src/sonar/scripts/`: may add `backfill_l5.py` new file (if budget permits C7)
- `db/persistence.py`: **NOT touched**
- `docs/specs/`: **NOT touched**
- `docs/adr/`: **NOT touched**
- Tests: separate directories

**Zero file overlap with Sprint I-patch**. Safe paralelo.

**Push race**: normal `git pull --rebase origin main`. Zero collisions expected.

**Start order**: Sprint K arranca ~1 min after Sprint I-patch.

---

## 4. Commits

### Commit 1 — Pre-flight + ORM → Snapshot builder helpers

```
feat(regimes): ORM-to-Snapshot helpers for L5 input assembly

Pre-flight: read MetaRegimeClassifier signature + Snapshot dataclasses +
orchestrator result structure + daily_cycles current state + cycle ORM
schemas. Document decisions:
- MetaRegimeClassifier.classify takes L5RegimeInputs (not ORM directly)
- Snapshot dataclasses expose only fields classifier uses (4-5 per cycle)
- daily_cycles persists cycle ORM rows THEN reads them THEN snapshots
- Alternative: build snapshots directly from CyclesOrchestrationResult
  (avoids re-reading from DB)

Design decision (Commit 1 body):
- Option A: Build snapshots from in-memory CycleResult (faster, no DB round-trip)
- Option B: Read persisted rows then snapshot (ensures persisted state)
- Recommend: Option A — in-memory coupling cleaner; DB re-read adds latency

Add src/sonar/regimes/assemblers.py (new module):

"""L5 input assemblers — build L5RegimeInputs from L4 outputs."""

from sonar.cycles.orchestrator import CyclesOrchestrationResult
from sonar.cycles.credit_cccs import CreditCycleResult
from sonar.cycles.financial_fcs import FinancialCycleResult
from sonar.cycles.monetary_msc import MonetaryCycleResult
from sonar.cycles.economic_ecs import EconomicCycleResult
from sonar.regimes.types import (
    L5RegimeInputs,
    EcsSnapshot,
    CccsSnapshot,
    FcsSnapshot,
    MscSnapshot,
)

def _ecs_snapshot(result: EconomicCycleResult | None) -> EcsSnapshot | None:
    """Build EcsSnapshot from EconomicCycleResult. None if result is None."""
    if result is None:
        return None
    return EcsSnapshot(
        ecs_id=result.ecs_id,
        score=result.score_0_100,
        regime=result.regime,
        stagflation_active=result.stagflation_overlay_active,
        confidence=result.confidence,
    )

# Similar _cccs_snapshot / _fcs_snapshot / _msc_snapshot

def build_l5_inputs_from_cycles_result(
    country_code: str,
    observation_date: date,
    result: CyclesOrchestrationResult,
) -> L5RegimeInputs:
    """Assemble L5RegimeInputs from orchestrator result.

    Uses in-memory cycle results to avoid DB re-read latency.
    Returns L5RegimeInputs with None for any missing cycle.
    """
    return L5RegimeInputs(
        country_code=country_code,
        date=observation_date,
        ecs=_ecs_snapshot(result.ecs),
        cccs=_cccs_snapshot(result.cccs),
        fcs=_fcs_snapshot(result.fcs),
        msc=_msc_snapshot(result.msc),
    )

Tests in tests/unit/test_regimes/test_assemblers.py:
- Unit: build_l5_inputs all 4 cycles present
- Unit: 1 cycle None → Snapshot None preserved
- Unit: 3 cycles None → Snapshot Nones; classifier downstream raises InsufficientL4DataError
- Unit: each _cycle_snapshot unit test

Sanity check commit body:
  python -c "from sonar.regimes.assemblers import build_l5_inputs_from_cycles_result; print('OK')"

Coverage assemblers.py ≥ 95%.
```

### Commit 2 — daily_cycles.py L5 integration

```
feat(pipelines): daily_cycles invokes L5 classifier post-L4

Update src/sonar/pipelines/daily_cycles.py:

After compute_all_cycles returns + per-cycle persistence:

1. Build L5RegimeInputs via build_l5_inputs_from_cycles_result
2. Invoke MetaRegimeClassifier.classify
3. Handle InsufficientL4DataError as structured skip:
   - Log warning with country + date + available cycle count
   - Do NOT raise; pipeline continues (L4 persistence already happened)
4. On successful classify:
   - Invoke persist_l5_meta_regime_result
   - Log info with meta_regime + confidence + classification_reason
5. On DuplicatePersistError:
   - Log info (expected when re-running same country+date)
   - Pipeline continues

Pseudocode integration:
```python
from sonar.regimes.meta_regime_classifier import MetaRegimeClassifier
from sonar.regimes.assemblers import build_l5_inputs_from_cycles_result
from sonar.regimes.exceptions import InsufficientL4DataError
from sonar.db.persistence import persist_l5_meta_regime_result, DuplicatePersistError

def compute_country_date(country, date, session):
    # Existing L4 orchestration
    result = compute_all_cycles(country, date, session)
    persist_many_cycle_results(session, result)

    # NEW: L5 classification
    try:
        l5_inputs = build_l5_inputs_from_cycles_result(country, date, result)
        classifier = MetaRegimeClassifier()
        l5_result = classifier.classify(l5_inputs)
        logger.info("l5_regime_classified", meta_regime=l5_result.meta_regime,
                    confidence=l5_result.confidence, reason=l5_result.classification_reason)
        try:
            persist_l5_meta_regime_result(session, l5_result)
            logger.info("l5_regime_persisted", country=country, date=date)
        except DuplicatePersistError:
            logger.info("l5_regime_duplicate_skip", country=country, date=date)
    except InsufficientL4DataError as e:
        logger.warning("l5_insufficient_l4", country=country, date=date, reason=str(e))
        # Pipeline continues; L4 still persisted

    return result
```

Exit codes maintained:
- 0 clean (includes L5 skip case)
- 1 insufficient data (< 3/4 L4 cycles — unchanged behavior)
- 3 duplicate
- 4 IO errors

Tests:
- Unit: daily_cycles with all 4 cycles → L5 persisted
- Unit: daily_cycles with 3/4 cycles → L5 persisted with 1-missing flag + cap
- Unit: daily_cycles with 2/4 cycles → InsufficientL4DataError raised → pipeline logs warning + continues (not crash)
- Unit: L5 duplicate → structured skip, pipeline clean exit

Coverage daily_cycles.py maintained ≥ 90%.
```

### Commit 3 — sonar status extension with L5 meta-regime display

```
feat(cli): sonar status shows L5 meta-regime

Update src/sonar/cli/status.py:

1. Extend CountryStatus dataclass:

@dataclass(frozen=True)
class CountryStatus:
    country_code: str
    as_of_date: date
    cccs: CycleStatus | None
    fcs: CycleStatus | None
    msc: CycleStatus | None
    ecs: CycleStatus | None
    l5_meta_regime: L5MetaRegimeStatus | None  # NEW

@dataclass(frozen=True)
class L5MetaRegimeStatus:
    meta_regime: str  # one of 6 canonical
    confidence: float
    flags: tuple[str, ...]
    classification_reason: str
    last_updated: datetime
    freshness: Literal["fresh", "stale"]

2. Extend get_country_status:
   - After querying 4 cycle tables, query l5_meta_regimes for (country, date)
   - Return None if no L5 row (L4 cycles may exist without L5 yet)
   - Populate L5MetaRegimeStatus with freshness (24h threshold)

3. Update format_status_summary:
   - Add "Meta-Regime" row to summary table
   - Show meta_regime + confidence
   - Color-coding per regime:
     - overheating: red
     - stagflation_risk: magenta
     - late_cycle_bubble: orange/yellow
     - recession_risk: red
     - soft_landing: green
     - unclassified: gray

4. Update format_status_verbose:
   - Additional L5 section with classification_reason + flags
   - Shows which decision tree branch matched

5. Update format_matrix (--all-t1):
   - Add column for meta_regime icon/short-code
   - Use Rich table symbols for compactness

Tests (append tests/unit/test_cli/test_status.py):
- Unit: get_country_status with L5 row → L5MetaRegimeStatus populated
- Unit: get_country_status without L5 row → l5_meta_regime=None
- Unit: format_status_summary includes meta_regime row
- Unit: format_status_summary color-coding per regime
- Unit: format_status_verbose includes classification_reason
- Unit: format_matrix compact L5 column

Coverage status.py additions ≥ 90%.
```

### Commit 4 — Integration smoke: end-to-end L5 flow

```
test(integration): daily_cycles + sonar status L5 end-to-end

tests/integration/test_l5_vertical_slice.py:

@pytest.mark.slow
def test_l5_full_vertical_slice_us():
    """Full vertical: seed L4 → daily_cycles → L5 persisted → sonar status displays.

    Steps:
    1. Seed L3 sub-indices rows for US 2024-12-31 (E1-E4 + L1-L4 + F1-F4 + M1-M4)
    2. Invoke daily_cycles.compute_country_date(US, 2024-12-31)
    3. Assert L4 rows persisted (4 cycles)
    4. Assert L5 row persisted in l5_meta_regimes
    5. Invoke get_country_status(US, 2024-12-31)
    6. Assert CountryStatus.l5_meta_regime populated
    7. Invoke format_status_summary
    8. Assert output contains "Meta-Regime:" + regime label + confidence
    9. Assert Rich color codes in output"""

@pytest.mark.slow
def test_l5_insufficient_cycles_pipeline_survives():
    """Only 2/4 L4 cycles available; daily_cycles logs + continues.

    Steps:
    1. Seed only 2 L3 sub-index sets (e.g. E + F only)
    2. Invoke daily_cycles (should compute 2 cycles, raise for others)
    3. Assert 2 L4 rows persisted
    4. Assert NO L5 row (insufficient)
    5. Assert pipeline exit code 0 (not crash)
    6. sonar status: l5_meta_regime is None, displays "N/A" gracefully"""

@pytest.mark.slow
def test_l5_duplicate_rerun_idempotent():
    """Re-run same (country, date) — L5 duplicate handled gracefully.

    Steps:
    1. First run: L5 persists
    2. Second run same country+date: L5 DuplicatePersistError → logged + skipped
    3. Pipeline exit code 0
    4. L5 row unchanged (no duplicate)"""

Wall-clock ≤ 30s combined.
```

### Commit 5 — Edge cases: classification branches tested via fixtures

```
test(integration): L5 classification branches exercised end-to-end

tests/integration/test_l5_classification_branches.py:

@pytest.mark.slow
@pytest.mark.parametrize("fixture_name, expected_regime", [
    ("overheating_2021Q2", "overheating"),
    ("stagflation_1974", "stagflation_risk"),
    ("late_cycle_bubble_2007Q2", "late_cycle_bubble"),
    ("recession_2009Q1", "recession_risk"),
    ("soft_landing_2015", "soft_landing"),
    ("unclassified_transitional", "unclassified"),
])
def test_classification_branch(fixture_name, expected_regime):
    """Parametrized: each canonical fixture classifies to expected regime.

    Steps:
    1. Load fixture values (scores + regimes + overlays per 4 L4 cycles)
    2. Build L5RegimeInputs from fixture
    3. classifier.classify
    4. Assert meta_regime == expected_regime
    5. Assert classification_reason matches decision tree branch"""

Fixtures source from Sprint H test_meta_regime_classifier fixture builders
(Python not JSON per Sprint H deviation #2).

Coverage classifier paths exercised end-to-end.
```

### Commit 6 — Backfill script (if budget permits)

```
feat(scripts): backfill_l5.py for retrospective classification

Create src/sonar/scripts/backfill_l5.py:

"""L5 retrospective classification for existing cycle dates.

For each (country, date) triplet where at least 3/4 L4 cycles exist
AND no L5 row present, compute L5 meta-regime + persist.

Usage:
  python -m sonar.scripts.backfill_l5 --country US --dry-run
  python -m sonar.scripts.backfill_l5 --all-t1 --execute
  python -m sonar.scripts.backfill_l5 --country US --from-date 2024-01-01 --execute
"""

from datetime import date
from typing import Iterator

import structlog
import typer
from sqlalchemy import select
from sonar.db.session import SessionLocal
from sonar.db.models import (
    EconomicCycleScore,
    CreditCycleScore,
    FinancialCycleScore,
    MonetaryCycleScore,
    L5MetaRegime,
)
from sonar.regimes.assemblers import build_l5_inputs_from_cycles_result
from sonar.regimes.meta_regime_classifier import MetaRegimeClassifier
from sonar.regimes.exceptions import InsufficientL4DataError
from sonar.db.persistence import persist_l5_meta_regime_result, DuplicatePersistError

app = typer.Typer()

def _iter_classifiable_dates(session, country: str, from_date: date | None) -> Iterator[tuple[str, date]]:
    """Yield (country, date) triplets with ≥ 3/4 cycles + no L5 row yet."""
    # Query cycle tables for dates, intersect with L5 absent
    ...

@app.command()
def run(
    country: str | None = typer.Option(None),
    all_t1: bool = typer.Option(False, "--all-t1"),
    from_date: str | None = typer.Option(None, "--from-date"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute"),
) -> int:
    """Backfill L5 rows for existing cycle dates."""
    ...

Tests (light):
- Unit: _iter_classifiable_dates excludes already-L5 dates
- Unit: dry-run reports what would be classified without persisting
- Unit: execute persists L5 rows idempotently
- Integration @slow: full backfill on fixture DB with 30 dates

Coverage backfill_l5.py ≥ 80% (tolerance for CLI wrapper).

If budget tight, defer C6 to Week 8 Day 3 — not critical path for Sprint K.
```

### Commit 7 — Retrospective

```
docs(planning): Week 8 Sprint K L5 wiring + CLI retrospective

File: docs/planning/retrospectives/week8-sprint-k-l5-wiring-cli-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- Spec shipped (none; implementation of Sprint H spec)
- Code shipped:
  - src/sonar/regimes/assemblers.py (new)
  - src/sonar/pipelines/daily_cycles.py (extended)
  - src/sonar/cli/status.py (extended with L5 display)
  - src/sonar/scripts/backfill_l5.py (if shipped)
- Tests shipped (target ~15-20 new; ~1180 total)
- Pattern validation:
  - in-memory Snapshot build vs DB re-read (Commit 1 decision documented)
  - InsufficientL4DataError graceful handling (pipeline continues)
  - DuplicatePersistError skip on re-run
- HALT triggers fired / not fired
- Deviations from brief
- Live smoke outcomes:
  - Full vertical slice US: L3 seed → L4 compute → L5 classify → status display
  - 2/4 cycles → L5 skip, pipeline clean
  - Duplicate → skip graceful
- Phase 2 first user-facing deliverable shipped:
  - `sonar status --country US` now shows L5 meta-regime
  - Color-coded per 6 canonical regimes
  - Matrix view compactly shows regimes across T1 countries
- Remaining L5 work Week 8+:
  - Cross-country regime comparison (L5b matrix Phase 2+)
  - Empirical threshold calibration (24m data needed)
  - ML classifier upgrade (Phase 2+)
- No new CAL items expected (pure implementation sprint)
- Phase 2 transition now operational, not just foundational
```

---

## 5. HALT triggers (atomic)

0. **Snapshot builder signature mismatch** — Sprint H Snapshot dataclasses may require different fields than expected. Verify Commit 1.
1. **Orchestrator result structure** — `CyclesOrchestrationResult` fields may not exactly match assumptions. Verify.
2. **DuplicatePersistError behavior** — should not crash pipeline; verify graceful handling.
3. **InsufficientL4DataError signature** — from Sprint H types.py. Verify correct exception class.
4. **Rich color coding availability** — Sprint G verified Rich in pyproject.toml; re-confirm.
5. **Integration test seeding complexity** — may require fixture helpers for seeding 16 L3 rows per country+date. Use existing fixtures if available.
6. **Backfill script scope creep** — if Commit 6 expands beyond 1h, defer to Week 8 Day 3 sprint.
7. **Coverage regression > 3pp** → HALT.
8. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
9. **Concurrent Sprint I-patch touches same files** (shouldn't per §3) → reconcile via rebase.

---

## 6. Acceptance

### Global sprint-end
- [ ] 6-8 commits pushed (5-7 if backfill deferred), main HEAD matches remote, CI green
- [ ] `src/sonar/regimes/assemblers.py` shipped + tested
- [ ] `daily_cycles.py` invokes L5 classifier + persists + handles graceful skip
- [ ] `sonar status` displays L5 meta-regime + color coding + matrix
- [ ] Integration smoke: full vertical slice PASS
- [ ] Classification branches test parametrized (6 regimes)
- [ ] Backfill script shipped (or deferred with CAL note)
- [ ] Coverage new modules ≥ 90%
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week8-sprint-k-l5-wiring-cli-report.md`

**Final tmux echo**:
```
SPRINT K L5 WIRING DONE: N commits, Phase 2 user-facing deliverable shipped
daily_cycles: L4 → L5 classification integrated
sonar status: meta-regime column with 6-color coding
Integration: full vertical slice verified
Backfill: [shipped/deferred]
HALT triggers: [list or "none"]
Phase 2 operational: `sonar status --country US` shows meta_regime
Artifact: docs/planning/retrospectives/week8-sprint-k-l5-wiring-cli-report.md
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

Live integration (`@pytest.mark.slow`) does not run default pytest.

---

## 9. Notes on implementation

### Sprint H did the hard work
Sprint H shipped classifier, spec, migration, persist helper, canonical fixtures. Sprint K wires them together + adds CLI display. Mostly glue code.

### Snapshot builders in new module
Avoids contamination of `regimes/types.py` with orchestrator dependency. `assemblers.py` depends on both cycles + regimes — appropriate placement.

### In-memory build vs DB re-read
Option A (in-memory from orchestrator result) is cleaner + faster. Option B (DB re-read) has no benefit. Commit 1 documents decision.

### Graceful degradation pattern
Pipeline continues on L5 errors. L4 persistence already happened when L5 fails. User-facing sonar status shows "N/A" for L5 when row missing.

### First Phase 2 user-facing output
Sprint K delivers visible value: `sonar status --country US` now shows meta_regime. Editorial team / 7365 Capital analysts get regime classification without technical drilldown.

### No breaking changes
Backward compat preserved: sonar status without L5 row shows "N/A" gracefully; daily_cycles without L5 wiring continues working (though L5 skipped).

### Backfill is nice-to-have
If Commit 6 fits in budget, ship it. Otherwise defer to Week 8 Day 3 sprint (low priority; production data < 1m old so backfill affects < 30 dates).

### Sprint I-patch paralelo
Runs in tmux `sonar`. Different concerns (TE connector vs L5 wiring). Zero file overlap per §3.

---

*End of Week 8 Sprint K brief. 6-8 commits. L5 operational + first Phase 2 user-facing deliverable.*
