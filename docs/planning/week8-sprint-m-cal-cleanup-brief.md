# Week 8 Sprint M — CAL Cleanup (Trimmed): Backfill-L5 + BEI/SURVEY Split + Formalization

**Target**: Close technical debt accumulated Week 7-8. Implement CAL-backfill-l5 script + CAL-113 BEI/SURVEY split + formalize both in backlog file.
**Priority**: MEDIUM (cleanup sprint; unblocks Phase 2+ empirical work)
**Budget**: 2-2.5h CC autonomous
**Commits**: ~5-7
**Base**: branch `sprint-m-cal-cleanup` (isolated worktree `/home/macro/projects/sonar-wt-sprint-m`)
**Concurrency**: Parallel to Sprint N systemd ops in worktree `sonar-wt-sprint-n`. See §3.

---

## 1. Scope

In:
- **CAL formalization** into `docs/backlog/calibration-tasks.md`:
  - CAL-backfill-l5: L5 retroactive classification script
  - CAL-113: BEI/SURVEY split in EXPINF sub_indicators JSON
- **CAL-backfill-l5 implementation** (per Sprint K C6 brief):
  - `src/sonar/scripts/backfill_l5.py` new module
  - Iterates (country, date) tuples with ≥ 3/4 L4 cycles present + no L5 row
  - Invokes `MetaRegimeClassifier` + persists via `persist_l5_meta_regime_result`
  - CLI: `--country`, `--all-t1`, `--from-date`, `--dry-run|--execute`
  - Idempotent: skip already-classified dates
- **CAL-113 BEI/SURVEY split implementation**:
  - Modify `src/sonar/pipelines/daily_overlays._compute_expected_inflation` to emit separate `bei_tenors` + `survey_tenors` + `method_per_tenor` in sub_indicators JSON
  - Update `src/sonar/indices/monetary/db_backed_builder.build_m3_inputs_from_db` to consume each separately (populate `bei_10y_bps` + `survey_10y_bps` distinct fields)
  - Backward compat: old EXPINF rows without split still parse (fallback to unified tenors)
- Unit tests for both changes
- Integration smoke for backfill script
- Retrospective

Out:
- CAL-128 (GB vs UK rename) — deferred to dedicated sprint (scope too pervasive)
- CAL-114 (dedicated CRP/EXPINF ORM tables) — deferred Phase 2+ (migration + consumer rewrites warrant focus)
- CAL-125/126/127 (UK M2/M3/M4 connector extensions) — require new connectors
- Empirical calibration of L5 thresholds — Phase 2+ (needs 24m production data)
- L5b cross-cycle 4×4 matrix — Phase 2+

---

## 2. Spec reference

Authoritative:
- `docs/specs/regimes/cross-cycle-meta-regimes.md` — L5 classification logic (backfill uses same)
- `docs/specs/regimes/integration-with-l4.md` — FK pattern + Policy 1 fail-mode
- `docs/specs/overlays/expected-inflation.md` — EXPINF hierarchy BEI > SWAP > DERIVED > SURVEY
- `docs/specs/indices/monetary/M3-market-expectations.md` §2 — M3 input schema
- `docs/planning/retrospectives/week8-sprint-k-l5-wiring-cli-report.md` — CAL-backfill-l5 scope
- `docs/planning/retrospectives/week7-sprint-e-cal-108-report.md` — CAL-113 scope (§CAL status updates "new CALs surfaced")
- `src/sonar/scripts/retention.py` — script pattern template (Sprint G Week 7)

**Pre-flight requirement**: Commit 1 CC reads:
1. `src/sonar/scripts/retention.py` — CLI Typer pattern for sonar scripts
2. `src/sonar/regimes/assemblers.py` — build_l5_inputs_from_cycles_result pattern (Sprint K shipped)
3. `src/sonar/regimes/meta_regime_classifier.py` — classifier invocation
4. `src/sonar/db/models.py` — 4 cycle ORM tables + L5MetaRegime
5. `src/sonar/pipelines/daily_overlays.py` — `_compute_expected_inflation` current implementation
6. `src/sonar/indices/monetary/db_backed_builder.py` — current `build_m3_inputs_from_db` consumer of EXPINF
7. `docs/backlog/calibration-tasks.md` — current structure/format for new CAL entries

Document findings in commit body.

Existing assets:
- `MetaRegimeClassifier` operational (Sprint H)
- `persist_l5_meta_regime_result` helper (Sprint H)
- `daily_overlays._compute_expected_inflation` (Sprint C)
- `build_m3_inputs_from_db` (Sprint E)
- Retention script pattern (Sprint G)

---

## 3. Concurrency — parallel protocol with Sprint N + ISOLATED WORKTREES

**Sprint M operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-m`

Sprint N operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-n`

**Critical workflow**:
1. Sprint M CC starts by `cd /home/macro/projects/sonar-wt-sprint-m`
2. All file operations happen in this worktree
3. Branch name: `sprint-m-cal-cleanup`
4. Pushes to `origin/sprint-m-cal-cleanup`
5. Final merge to main via fast-forward or merge commit

**File scope Sprint M**:
- `src/sonar/scripts/backfill_l5.py` NEW
- `src/sonar/pipelines/daily_overlays.py` MODIFY (`_compute_expected_inflation`)
- `src/sonar/indices/monetary/db_backed_builder.py` MODIFY (`build_m3_inputs_from_db`)
- `docs/backlog/calibration-tasks.md` APPEND (CAL-113 + CAL-backfill-l5 entries)
- `tests/unit/test_scripts/test_backfill_l5.py` NEW
- `tests/unit/test_pipelines/test_daily_overlays.py` APPEND (split tests)
- `tests/unit/test_indices/test_monetary_db_backed_builder.py` APPEND (split consumer tests)
- `tests/integration/test_backfill_l5.py` NEW
- `docs/planning/retrospectives/week8-sprint-m-cal-cleanup-report.md` NEW

**Sprint N scope** (for awareness, do NOT touch):
- `deploy/systemd/*.service` + `*.timer`
- `scripts/install-timers.sh` + `scripts/uninstall-timers.sh`
- `docs/ops/systemd-deployment.md`
- `CLAUDE.md`

**Zero file overlap confirmed**. Different domains entirely.

**Merge strategy end-of-sprint**:
- Sprint M: `git checkout main && git merge sprint-m-cal-cleanup` (fast-forward expected)
- Order independent of Sprint N

**Push protocol during sprint**:
- Normal commits to `sprint-m-cal-cleanup` branch
- Push via `git push origin sprint-m-cal-cleanup`
- No rebase needed between sprints (isolated branches)

---

## 4. Commits

### Commit 1 — Pre-flight + CAL formalization in backlog

```
docs(backlog): formalize CAL-backfill-l5 + CAL-113 BEI/SURVEY split

Pre-flight: read retention.py + assemblers.py + classifier + daily_overlays
+ db_backed_builder + backlog.md structure. Document findings commit body.

Append to docs/backlog/calibration-tasks.md:

### CAL-backfill-l5 — L5 retroactive classification script
- **Priority**: LOW (< 30 production dates affected; not critical path)
- **Trigger**: Sprint K (Week 8 Day 2) deferred C6 per brief §4 allowance
- **Scope**: Iterate (country, date) triplets with ≥ 3/4 L4 cycles persisted AND no L5 row; classify via MetaRegimeClassifier; persist via persist_l5_meta_regime_result
- **Implementation**: `src/sonar/scripts/backfill_l5.py` + CLI integration
- **Dependency**: Sprint H L5 infrastructure shipped
- **Status**: In progress Sprint M Week 8 Day 3

### CAL-113 — BEI/SURVEY split in EXPINF sub_indicators
- **Priority**: LOW (affects M3 diagnostic only; composite unaffected)
- **Trigger**: Sprint E retro §Deviations + Sprint C EXPINF persistence pattern
- **Context**: Today EXPINF IndexValue rows collapse BEI + SURVEY methods into single `expected_inflation_tenors` dict. M3 cannot distinguish BEI vs SURVEY signal per spec §2 (`bei_10y_bps` + `survey_10y_bps` distinct fields).
- **Scope**:
  - Modify `daily_overlays._compute_expected_inflation` to emit `bei_tenors` + `survey_tenors` + `method_per_tenor` separately
  - Update `build_m3_inputs_from_db` to consume each separately
  - Backward compat: old rows without split fall back to unified tenors
- **Dependency**: Sprint C EXPINF persistence + Sprint E M3 DB-backed reader
- **Status**: In progress Sprint M Week 8 Day 3

Also update backlog summary counters if format includes counters.

No tests (documentation); formalization commit.
```

### Commit 2 — CAL-backfill-l5 script implementation

```
feat(scripts): backfill_l5.py L5 retroactive classification

Create src/sonar/scripts/backfill_l5.py:

"""L5 retroactive classification for existing cycle dates.

For each (country, date) triplet where:
- At least 3/4 L4 cycles persisted (ecs/cccs/fcs/msc)
- No L5 row present (l5_meta_regimes)

Runs MetaRegimeClassifier + persists via persist_l5_meta_regime_result.

Idempotent: skips dates already classified.

Usage:
  # Dry-run (safe default)
  python -m sonar.scripts.backfill_l5 --country US --dry-run
  python -m sonar.scripts.backfill_l5 --all-t1 --dry-run

  # Execute (writes rows)
  python -m sonar.scripts.backfill_l5 --country US --execute
  python -m sonar.scripts.backfill_l5 --all-t1 --from-date 2024-01-01 --execute
"""

from __future__ import annotations

import sys
from datetime import date
from typing import Iterator

import structlog
import typer
from sqlalchemy import select
from sqlalchemy.orm import Session

from sonar.db.session import SessionLocal
from sonar.db.models import (
    EconomicCycleScore,
    CreditCycleScore,
    FinancialCycleScore,
    MonetaryCycleScore,
    L5MetaRegime,
)
from sonar.regimes.assemblers import build_l5_inputs_from_snapshots
from sonar.regimes.meta_regime_classifier import MetaRegimeClassifier
from sonar.regimes.exceptions import InsufficientL4DataError
from sonar.db.persistence import (
    persist_l5_meta_regime_result,
    DuplicatePersistError,
)

logger = structlog.get_logger(__name__)
app = typer.Typer()

T1_COUNTRIES = ["US", "DE", "PT", "IT", "ES", "FR", "NL"]  # current 7 T1 + UK post-Sprint I


def _iter_classifiable_triplets(
    session: Session,
    country: str,
    from_date: date | None = None,
) -> Iterator[tuple[str, date]]:
    """Yield (country, date) triplets with ≥ 3/4 cycles + no L5 row yet."""
    # Union of all 4 cycle dates for country
    ecs_dates = session.execute(
        select(EconomicCycleScore.date).where(
            EconomicCycleScore.country_code == country
        )
    ).scalars().all()
    cccs_dates = session.execute(
        select(CreditCycleScore.date).where(
            CreditCycleScore.country_code == country
        )
    ).scalars().all()
    fcs_dates = session.execute(
        select(FinancialCycleScore.date).where(
            FinancialCycleScore.country_code == country
        )
    ).scalars().all()
    msc_dates = session.execute(
        select(MonetaryCycleScore.date).where(
            MonetaryCycleScore.country_code == country
        )
    ).scalars().all()

    all_dates = set(ecs_dates) | set(cccs_dates) | set(fcs_dates) | set(msc_dates)
    if from_date:
        all_dates = {d for d in all_dates if d >= from_date}

    # L5 already classified
    l5_dates = set(session.execute(
        select(L5MetaRegime.date).where(
            L5MetaRegime.country_code == country
        )
    ).scalars().all())

    for d in sorted(all_dates - l5_dates):
        yield (country, d)


def _build_snapshots_for_date(
    session: Session, country: str, d: date
) -> tuple[object, object, object, object]:
    """Read persisted cycle rows + build Snapshots. Returns (ecs, cccs, fcs, msc)
    tuples of Snapshot or None."""
    # Query each table for (country, date); return snapshot or None
    ...


@app.command()
def run(
    country: str | None = typer.Option(None),
    all_t1: bool = typer.Option(False, "--all-t1"),
    from_date: str | None = typer.Option(None, "--from-date"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute"),
) -> int:
    """Backfill L5 rows for existing cycle dates."""
    session = SessionLocal()
    classifier = MetaRegimeClassifier()

    countries = T1_COUNTRIES if all_t1 else [country] if country else []
    if not countries:
        logger.error("no_country_specified")
        return 2

    from_date_obj = date.fromisoformat(from_date) if from_date else None

    total_eligible = 0
    total_classified = 0
    total_skipped = 0
    total_insufficient = 0

    for country_code in countries:
        triplets = list(_iter_classifiable_triplets(session, country_code, from_date_obj))
        total_eligible += len(triplets)

        for _, d in triplets:
            snapshots = _build_snapshots_for_date(session, country_code, d)
            l5_inputs = build_l5_inputs_from_snapshots(
                country_code, d, *snapshots
            )

            try:
                result = classifier.classify(l5_inputs)
            except InsufficientL4DataError:
                total_insufficient += 1
                logger.info("l5_backfill_insufficient", country=country_code, date=d.isoformat())
                continue

            if dry_run:
                logger.info(
                    "l5_backfill_would_persist",
                    country=country_code,
                    date=d.isoformat(),
                    meta_regime=result.meta_regime,
                )
                total_classified += 1
            else:
                try:
                    persist_l5_meta_regime_result(session, result)
                    total_classified += 1
                    logger.info("l5_backfill_persisted", country=country_code, date=d.isoformat())
                except DuplicatePersistError:
                    total_skipped += 1

    logger.info(
        "l5_backfill_complete",
        eligible=total_eligible,
        classified=total_classified,
        skipped=total_skipped,
        insufficient=total_insufficient,
        dry_run=dry_run,
    )
    session.close()
    return 0


def main():
    app()


if __name__ == "__main__":
    main()

Sanity check commit body:
  python -c "from sonar.scripts.backfill_l5 import run; print('OK')"

Tests (tests/unit/test_scripts/test_backfill_l5.py):
- Unit: _iter_classifiable_triplets excludes already-L5 dates
- Unit: _iter_classifiable_triplets respects from_date filter
- Unit: _build_snapshots_for_date with all 4 cycles → tuple of 4 snapshots
- Unit: _build_snapshots_for_date with 2/4 → 2 None entries
- Unit: run() dry-run reports expected counts
- Unit: run() execute persists rows idempotently
- Unit: insufficient L4 data → counts in insufficient bucket

Coverage backfill_l5.py ≥ 85% (CLI wrapper tolerance).

Note: assemblers.py may need new helper `build_l5_inputs_from_snapshots`
that takes individual Snapshot args; verify Commit 1 pre-flight whether
Sprint K shipped this or only `build_l5_inputs_from_cycles_result`.
```

### Commit 3 — CAL-113 BEI/SURVEY split in EXPINF

```
feat(pipelines): BEI/SURVEY split in EXPINF sub_indicators (CAL-113)

Update src/sonar/pipelines/daily_overlays._compute_expected_inflation:

Before:
    sub_indicators = {
        "expected_inflation_tenors": {"2Y": ..., "5Y": ..., "10Y": ..., "5y5y": ...},
        "source_method_per_tenor": {"2Y": "BEI", ...},
        "methods_available": ["BEI", "SURVEY"],
        "anchor_status": "...",
        "anchor_deviation_bps": ...,
    }

After:
    sub_indicators = {
        "expected_inflation_tenors": {"2Y": ..., "5Y": ..., "10Y": ..., "5y5y": ...},  # Unified (canonical)
        "bei_tenors": {"2Y": ..., "5Y": ...},  # NEW: BEI-method values only
        "survey_tenors": {"10Y": ...},          # NEW: SURVEY-method values only
        "method_per_tenor": {"2Y": "BEI", "5Y": "BEI", "10Y": "SURVEY", "5y5y": "DERIVED"},
        "methods_available": ["BEI", "SURVEY", "DERIVED"],
        "anchor_status": "...",
        "anchor_deviation_bps": ...,
    }

Build logic:
- Iterate hierarchy (BEI > SWAP > DERIVED > SURVEY) per tenor
- Track which method yielded value per tenor
- Emit bei_tenors ONLY for tenors where method was BEI
- Emit survey_tenors ONLY for tenors where method was SURVEY
- (Optional: bei_tenors + survey_tenors for diagnostic; canonical stays unified)

Tests (tests/unit/test_pipelines/test_daily_overlays.py append):
- Unit: all BEI → bei_tenors populated, survey_tenors empty
- Unit: mixed BEI + SURVEY → both populated
- Unit: all DERIVED → bei_tenors + survey_tenors empty (only canonical populated)
- Unit: method_per_tenor maps correctly

Coverage daily_overlays.py path ≥ existing.
```

### Commit 4 — CAL-113 M3 DB-backed builder consumer update

```
feat(indices): M3 DB-backed builder consumes BEI/SURVEY split (CAL-113 part 2)

Update src/sonar/indices/monetary/db_backed_builder.build_m3_inputs_from_db:

Before:
    # Parse sub_indicators JSON
    expinf_tenors = sub_indicators.get("expected_inflation_tenors", {})
    breakeven_5y5y = expinf_tenors.get("5y5y")  # unified — didn't distinguish method
    # bei_10y_bps and survey_10y_bps left as None (unavailable)

After:
    sub_indicators = json.loads(expinf_row.sub_indicators_json)

    # NEW: consume BEI/SURVEY split if present
    bei_tenors = sub_indicators.get("bei_tenors", {})
    survey_tenors = sub_indicators.get("survey_tenors", {})

    # Canonical 5y5y breakeven (unified)
    expinf_tenors = sub_indicators.get("expected_inflation_tenors", {})
    breakeven_5y5y_pct = expinf_tenors.get("5y5y")

    # BEI-specific (NEW — CAL-113)
    bei_10y_pct = bei_tenors.get("10Y")
    bei_10y_bps = int(bei_10y_pct * 10000) if bei_10y_pct is not None else None

    # SURVEY-specific (NEW — CAL-113)
    survey_10y_pct = survey_tenors.get("10Y")
    survey_10y_bps = int(survey_10y_pct * 10000) if survey_10y_pct is not None else None

    # Populate M3Inputs with split fields
    return M3Inputs(
        ...
        breakeven_5y5y_bps=...,  # unified canonical
        bei_10y_bps=bei_10y_bps,  # NEW
        survey_10y_bps=survey_10y_bps,  # NEW
        ...
    )

Backward compat:
- If sub_indicators has no bei_tenors/survey_tenors (pre-Sprint M rows),
  bei_10y_bps and survey_10y_bps stay None
- Downstream M3 compute gracefully handles None per spec §2

Tests (tests/unit/test_indices/test_monetary_db_backed_builder.py append):
- Unit: BEI present → bei_10y_bps populated
- Unit: SURVEY present → survey_10y_bps populated
- Unit: both present → both populated
- Unit: old row without split (backward compat) → both None, canonical still works

Coverage db_backed_builder.py ≥ existing.
```

### Commit 5 — Integration smoke: backfill end-to-end

```
test(integration): backfill_l5 end-to-end + CAL-113 round-trip

tests/integration/test_backfill_l5.py:

@pytest.mark.slow
def test_backfill_l5_happy_path():
    """Seed 30 dates across 3 countries with 4 L4 cycles each but no L5.
    Run backfill --all-t1 --execute.

    Expected:
    - 30+ L5 rows persisted (modulo insufficient cases)
    - Script exit code 0
    - Idempotent re-run → 0 new rows persisted"""

@pytest.mark.slow
def test_backfill_l5_dry_run():
    """Seed 10 dates; run --dry-run.

    Expected:
    - 0 L5 rows persisted
    - Log output counts match expected"""

@pytest.mark.slow
def test_backfill_l5_insufficient_cycles():
    """Seed 5 dates with only 2/4 cycles each.
    Run backfill --execute.

    Expected:
    - 0 L5 rows persisted
    - Script logs 5 insufficient entries"""

@pytest.mark.slow
def test_backfill_l5_with_from_date_filter():
    """Seed 20 dates; --from-date filters to last 10.

    Expected:
    - Only 10 classified"""

tests/integration/test_cal_113_round_trip.py:

@pytest.mark.slow
def test_bei_survey_split_round_trip():
    """Run daily_overlays → persist EXPINF with split → build_m3_inputs_from_db
    reads split correctly.

    Expected:
    - sub_indicators has bei_tenors + survey_tenors + method_per_tenor
    - M3Inputs from DB has bei_10y_bps + survey_10y_bps distinct
    - Backward compat: manually-crafted old EXPINF row still parses"""

Wall-clock ≤ 30s combined.
```

### Commit 6 — Retrospective

```
docs(planning): Week 8 Sprint M CAL cleanup retrospective

File: docs/planning/retrospectives/week8-sprint-m-cal-cleanup-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- CAL resolutions:
  - CAL-backfill-l5 CLOSED (script shipped + tested + idempotent)
  - CAL-113 BEI/SURVEY split CLOSED (emitter + consumer + backward compat)
  - Formalized both in backlog file
- Coverage delta
- Tests shipped: ~15 new
- HALT triggers fired / not fired
- Deviations from brief
- Backlog state: 41 open → 39 open (2 closures)
- Isolated worktree experience:
  - Pros: zero concurrent-hook collisions (vs Day 2)
  - Cons: slight overhead setup + merge workflow
  - Recommendation: adopt as permanent pattern for paralelo sprints
- Merge strategy: branch sprint-m-cal-cleanup → main fast-forward
- Next steps (no new CALs expected):
  - CAL-128 GB vs UK rename (dedicated sprint)
  - CAL-114 dedicated ORM tables (Phase 2+ migration)
  - CAL-125/126/127 UK M2/M3/M4 (connector sprints)

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git fetch origin
  git merge --ff-only sprint-m-cal-cleanup
  git push origin main
```

---

## 5. HALT triggers (atomic)

0. **Pre-flight: assemblers.py signature missing for snapshot-based build** — Sprint K shipped `build_l5_inputs_from_cycles_result(country, date, CyclesOrchestrationResult)`. Backfill script needs snapshot-based alternative. If missing, add new helper `build_l5_inputs_from_snapshots(country, date, ecs_snap, cccs_snap, fcs_snap, msc_snap)` as part of Commit 2.
1. **EXPINF sub_indicators schema ambiguity** — current structure per Sprint C. Verify actual JSON key names before modifying emitter.
2. **M3Inputs dataclass bei_10y_bps + survey_10y_bps fields** — may not exist in current `M3Inputs`. Verify Commit 3 pre-flight; if missing, needs addition to dataclass (but spec §2 lists them so should exist).
3. **Backward compat break** — old EXPINF rows without split must still work. Tests mandatory.
4. **Cycle ORM date matching** — cycles may persist with different date semantics (month-end vs business day). Verify queries handle correctly.
5. **Script CLI integration with sonar main** — script can run standalone or via `sonar retention l5-backfill` subcommand (per Sprint G retention pattern). Decide Commit 2.
6. **Coverage regression > 3pp** → HALT.
7. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
8. **Concurrent Sprint N touches same files** (shouldn't per §3) → reconcile via branch merge.

---

## 6. Acceptance

### Global sprint-end
- [ ] 5-7 commits pushed to branch `sprint-m-cal-cleanup`
- [ ] CAL-113 + CAL-backfill-l5 formalized in backlog
- [ ] `src/sonar/scripts/backfill_l5.py` shipped + tested
- [ ] `daily_overlays._compute_expected_inflation` emits BEI/SURVEY split
- [ ] `build_m3_inputs_from_db` consumes split correctly
- [ ] Backward compat preserved (old rows still parse)
- [ ] Integration smoke tests PASS
- [ ] Retrospective shipped
- [ ] Merge strategy documented
- [ ] Coverage new modules ≥ 90% (backfill_l5.py ≥ 85% CLI tolerance)
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week8-sprint-m-cal-cleanup-report.md`

**Final tmux echo**:
```
SPRINT M CAL CLEANUP DONE: N commits on branch sprint-m-cal-cleanup
CAL closures: CAL-backfill-l5 + CAL-113
Formalized in backlog: both CALs entered with full context
Backlog: 41 open → 39 open (2 closures)
Backward compat: old EXPINF rows verified working
Worktree isolation: zero collision incidents
HALT triggers: [list or "none"]
Merge: git checkout main && git merge --ff-only sprint-m-cal-cleanup
Artifact: docs/planning/retrospectives/week8-sprint-m-cal-cleanup-report.md
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

### Clean sprint, low complexity
Backfill is pattern replication of Sprint K work. BEI/SURVEY split is straightforward dict manipulation + backward compat guard. Retrospective is short.

### assemblers.py helper check
Sprint K shipped `build_l5_inputs_from_cycles_result(CyclesOrchestrationResult)`. Backfill needs alternative taking individual Snapshots (read from DB). Likely need new helper — add as part of Commit 2 or separate commit.

### CAL formalization format
Follow existing entries in backlog file. Keep entries concise. Priority + Trigger + Scope + Status fields standard.

### Idempotent backfill
Script must handle re-run gracefully. Skip dates already classified. Structured logs for auditability.

### Backward compatibility critical
Old EXPINF rows (pre-Sprint M) must still work. Consumer (`build_m3_inputs_from_db`) checks for new keys + falls back gracefully.

### Isolated worktree workflow
Sprint M operates entirely in `/home/macro/projects/sonar-wt-sprint-m`. Branch: `sprint-m-cal-cleanup`. Final merge via fast-forward to main.

### Merge back to main strategy
Post-sprint-close:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-m-cal-cleanup
git push origin main
```

### Sprint N parallel
Runs in `sonar-wt-sprint-n` worktree. Different domain (deploy/systemd vs Python code). Zero overlap per §3.

---

*End of Week 8 Sprint M brief. 5-7 commits. 2 CAL closures + formalization. Technical debt reduction.*
