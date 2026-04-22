# Week 10 Day 2 Sprint E — CAL-CURVES-T1-SPARSE-INCLUSION (GB/JP/CA --all-t1)

**Tier scope**: T1 ONLY (16 countries). T2 expansion deferred to Phase 5 per ADR-0010.

**Target**: Add GB/JP/CA to `T1_7_COUNTRIES` tuple in `daily_curves.py` so `--all-t1` iteration covers these 3 countries. Connectors + dispatcher routing already shipped Sprint CAL-138 — this is tuple expansion + live canaries + systemd validation.
**Priority**: HIGH (quick-ship expansion Phase 2 T1 curves; unblocks overlays cascade for 3 additional T1 countries)
**Budget**: 2-3h CC
**Commits**: ~4-5
**Base**: branch `sprint-curves-t1-sparse-inclusion` (isolated worktree `/home/macro/projects/sonar-wt-curves-t1-sparse`)
**Concurrency**: PARALELO with Sprint F (CAL-CPI-INFL-T1-WRAPPERS). Different primary files.

**Brief format**: v3

---

## 1. Scope

In (3 tracks):

### Track 1 — Tuple expansion + dispatcher verification (~30min)
- `src/sonar/pipelines/daily_curves.py` MODIFY:
  - Current `T1_7_COUNTRIES = ("US", "DE", "EA")` (3 countries post CAL-138 scope + Sprint A HALT)
  - Post this sprint: `("US", "DE", "EA", "GB", "JP", "CA")` (6 countries)
- Verify dispatcher routes GB/JP/CA correctly to `te.fetch_{gb,jp,ca}_yield_curve_nominal`
- Confirm connectors already shipped Sprint CAL-138 (they were — just not in tuple iteration)

### Track 2 — Tests (~1h)
- Unit: `--all-t1` iterates 6 countries
- Unit: per-country dispatch routes correctly (GB/JP/CA via TE)
- Integration @pytest.mark.slow: live canary for each (GB/JP/CA) NSS fit + persistence
- RMSE target ≤ 10 bps per country (DE reference)
- Tenor spectrum per country validated:
  - GB: 12 tenors per CAL-138 retro
  - JP: 9 tenors per CAL-138 retro
  - CA: 6 tenors NS-reduced per CAL-138 retro

### Track 3 — Tests + CAL closures + retro (~30min)
- CAL-CURVES-T1-SPARSE-INCLUSION CLOSED with commit refs
- Production validation: --all-t1 execution fresh date persists 6 countries
- systemd service unchanged (--all-t1 already active)
- Retrospective per v3 format

Out:
- AU/NZ/CH/SE/NO/DK curves (still CAL-CURVES-T1-SPARSE subset — deferred per ADR-0009 probe-before-scaffold discipline; likely need national-CB connectors)
- EA periphery (PT/IT/ES/FR/NL) — CAL-CURVES-*-BDF/BDI/BDE/BPSTAT/DNB separate sprints
- Linker data per country (deferred CAL-CURVES-T1-LINKER)
- Historical backfill (Phase 2.5 backtest scope)

---

## 2. Spec reference

Authoritative:
- `docs/backlog/calibration-tasks.md` — CAL-CURVES-T1-SPARSE-INCLUSION entry (opened CAL-138)
- `docs/planning/retrospectives/week10-sprint-cal138-report.md` — GB/JP/CA connector implementation details (already shipped)
- `src/sonar/connectors/te.py` — existing `fetch_gb_yield_curve_nominal` + `fetch_jp_yield_curve_nominal` + `fetch_ca_yield_curve_nominal` (shipped CAL-138)
- `src/sonar/pipelines/daily_curves.py` — current `T1_7_COUNTRIES` tuple + dispatcher
- `docs/adr/ADR-0010-t1-complete-before-t2-expansion.md` — tier scope lock

**Pre-flight requirement**: Commit 1 CC:
1. Read CAL-138 retro to verify GB/JP/CA connectors shipped + tested
2. Verify TE fetch methods exist + pass existing unit tests:
   ```bash
   grep -n "fetch_gb_yield_curve\|fetch_jp_yield_curve\|fetch_ca_yield_curve" src/sonar/connectors/te.py
   ```
3. Check current `T1_7_COUNTRIES` definition:
   ```bash
   grep -n "T1_7_COUNTRIES" src/sonar/pipelines/daily_curves.py
   ```
4. Check dispatcher routing for GB/JP/CA:
   ```bash
   grep -A 20 "def run_country" src/sonar/pipelines/daily_curves.py
   ```
5. Document findings Commit 1 body — should be trivial confirmation (no new code needed beyond tuple expansion).

**Pre-flight HALT trigger**: if CAL-138 retro claims GB/JP/CA shipped but code inspection reveals incomplete (connectors missing OR dispatcher incomplete), HALT + surface.

---

## 3. Concurrency — PARALELO with Sprint F

**Sprint E worktree**: `/home/macro/projects/sonar-wt-curves-t1-sparse`
**Sprint E branch**: `sprint-curves-t1-sparse-inclusion`

**Sprint F (for awareness)**: CAL-CPI-INFL-T1-WRAPPERS, worktree `/home/macro/projects/sonar-wt-cpi-infl-t1`

**File scope Sprint E**:
- `src/sonar/pipelines/daily_curves.py` MODIFY (primary — tuple + possibly dispatcher confirmation)
- `tests/unit/test_pipelines/test_daily_curves.py` EXTEND (tuple assertion + dispatch unit tests)
- `tests/integration/test_daily_curves_multi_country.py` EXTEND (live canaries GB/JP/CA)
- `docs/backlog/calibration-tasks.md` MODIFY (close CAL-CURVES-T1-SPARSE-INCLUSION)
- `docs/planning/retrospectives/week10-sprint-curves-t1-sparse-report.md` NEW

**Sprint F file scope** (for awareness, DO NOT TOUCH):
- `src/sonar/indices/monetary/builders.py` (primary — M2 CPI paths)
- `src/sonar/connectors/te.py` APPEND or `src/sonar/connectors/ecb_sdw.py` EXTEND (CPI YoY + inflation forecast wrappers)
- `src/sonar/pipelines/daily_monetary_indices.py` (Sprint F — M2 CPI integration)

**Zero primary-file overlap**:
- Sprint E: `daily_curves.py` (pipelines) + `te.py` read-only
- Sprint F: `daily_monetary_indices.py` + `builders.py` M2 paths + `te.py`/`ecb_sdw.py` APPEND

**Potential conflict**: `src/sonar/connectors/te.py` — Sprint F may APPEND new CPI wrappers. Sprint E only reads existing yield wrappers. Sprint F append doesn't conflict with Sprint E read-only usage.

**Shared secondary**: `docs/backlog/calibration-tasks.md` — both sprints close CAL items in different sections. Union-merge trivial.

**Rebase expected minimal**: alphabetical merge priority → Sprint E ships first (2-3h budget); Sprint F ships second (4-6h budget); Sprint F rebases CAL file only.

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed
- [ ] Workspace clean
- [ ] Pre-push gate green
- [ ] Branch tracking set
- [ ] Live canaries GB/JP/CA PASS
- [ ] Tier scope verified T1 only (per ADR-0010)

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-curves-t1-sparse-inclusion
```

---

## 4. Commits

### Commit 1 — Pre-flight + tuple expansion

```
refactor(pipelines): T1_7_COUNTRIES tuple expansion GB/JP/CA

Pre-flight findings (Commit 1 body):
- CAL-138 GB/JP/CA connector verification:
  - te.fetch_gb_yield_curve_nominal: [confirmed exists, N tenors]
  - te.fetch_jp_yield_curve_nominal: [confirmed exists, N tenors]
  - te.fetch_ca_yield_curve_nominal: [confirmed exists, N tenors]
- Pipeline dispatcher routing verification:
  - run_country handles GB/JP/CA → TE dispatch: [confirmed/needs addition]
- Current T1_7_COUNTRIES tuple: ("US", "DE", "EA")
- Post this sprint: ("US", "DE", "EA", "GB", "JP", "CA")

Modify src/sonar/pipelines/daily_curves.py:

T1_7_COUNTRIES: Final = ("US", "DE", "EA", "GB", "JP", "CA")
# Tier scope lock per ADR-0010: T1 only through Phase 4.

Update docstring to reflect 6 countries iteration.

Verify dispatcher (run_country or equivalent) routes GB/JP/CA correctly:
- GB → te.fetch_gb_yield_curve_nominal
- JP → te.fetch_jp_yield_curve_nominal
- CA → te.fetch_ca_yield_curve_nominal

If dispatcher needs addition (not shipped CAL-138), add minimal routing.

Tests:
- Unit: T1_7_COUNTRIES contains exactly 6 entries
- Unit: ADR-0010 compliance (no T2 country slipped into tuple)

Coverage daily_curves.py maintained ≥ 90%.
```

### Commit 2 — Unit tests dispatcher

```
test(pipelines): daily_curves dispatcher GB/JP/CA unit tests

Extend tests/unit/test_pipelines/test_daily_curves.py:

- test_run_country_dispatches_gb_to_te
- test_run_country_dispatches_jp_to_te
- test_run_country_dispatches_ca_to_te
- test_all_t1_iterates_6_countries (assert loop count + per-country call)
- test_t1_tuple_matches_adr_0010 (tier scope compliance)

Mock connectors + verify call sequencing + return handling.

Coverage ≥ 90% daily_curves.py.
```

### Commit 3 — Live canaries GB/JP/CA + NSS fit validation

```
test(integration): daily_curves live canaries GB/JP/CA

Extend tests/integration/test_daily_curves_multi_country.py:

@pytest.mark.slow
async def test_daily_curves_gb_live_canary():
    """FR NSS fit via TE for 2024-12-31.

    Assert:
    - NSSYieldCurveSpot persisted
    - confidence ≥ 0.9
    - rmse_bps ≤ 10 (DE reference)
    - tenors_observed ≥ 8
    """

Similar for JP (9 tenors expected), CA (6 tenors NS-reduced).

@pytest.mark.slow
async def test_daily_curves_all_t1_iterates_6():
    """--all-t1 full execution 2024-12-31 persists 6 countries."""

Combined wall-clock target ≤ 45s.

Cassettes reused from CAL-138 shipped (tests/fixtures/cassettes/te/).

Coverage maintained.
```

### Commit 4 — Production verification + retro

```
docs(planning+backlog): Sprint E T1 sparse inclusion retro + CAL closure

CAL-CURVES-T1-SPARSE-INCLUSION CLOSED (partial resolution):
- 3 countries added to --all-t1: GB, JP, CA
- Deferred: AU, NZ, CH, SE, NO, DK (require national-CB connectors per ADR-0009
  probe-before-scaffold discipline OR TE yield curve probes reveal sufficient coverage)

New CAL items if deferred countries:
- CAL-CURVES-AU-SPARSE-PROBE (ADR-0009 probe required)
- CAL-CURVES-NZ-SPARSE-PROBE
- CAL-CURVES-CH-SPARSE-PROBE (negative-rate era handling)
- CAL-CURVES-SE-SPARSE-PROBE (negative-rate era)
- CAL-CURVES-NO-SPARSE-PROBE
- CAL-CURVES-DK-SPARSE-PROBE (negative-rate era)

Retrospective per v3 format:
docs/planning/retrospectives/week10-sprint-curves-t1-sparse-report.md

Content:
- Verification CAL-138 connectors functional GB/JP/CA
- Live canary results per country
- NSS fit RMSE per country
- Production impact: overlays cascade tomorrow 07:30 WEST gains GB/JP/CA
- §10 pre-merge checklist + §11 merge via script
- Paralelo with Sprint F: zero conflicts
- ADR-0010 compliance verified: all new countries T1

Production validation:
- Manual run: `uv run python -m sonar.pipelines.daily_curves --all-t1 --date 2026-04-20`
- Expected: 6 countries persisted
- Verify via DB: `sqlite3 data/sonar-dev.db "SELECT country_code, MAX(curve_date) FROM nss_yield_curves_spot GROUP BY country_code;"`

systemd service: no changes (--all-t1 already active).
Tomorrow 07:00 WEST natural fire will persist 6 countries automatically.
```

---

## 5. HALT triggers (atomic)

0. **CAL-138 connectors verification fails** — if te.fetch_{gb,jp,ca}_yield_curve_nominal don't exist OR fail unit tests, HALT + surface. Precedent: brief assumed shipped; reality check.
1. **Dispatcher routing incomplete** — if run_country doesn't route GB/JP/CA, add routing (non-HALT). If architectural refactor needed, HALT.
2. **Live canary RMSE > 20 bps** — investigate; NSS fit parameters may need tuning per country (tenor spectrum adjustments). HALT if systematic.
3. **Tenor spectrum mismatch** — if probe reveals actual tenors differ from CAL-138 retro claims, adjust + document; not a HALT.
4. **Pre-push gate fails** — fix before push.
5. **No `--no-verify`**.
6. **Coverage regression > 3pp** — HALT.
7. **Push before stopping** — script mandates; brief v3 §10.
8. **Sprint F file conflict** — CAL file union-merge trivial.
9. **ADR-0010 violation** — if tuple expansion sneaks any non-T1 country, HALT.

---

## 6. Acceptance

### Global sprint-end
- [ ] `T1_7_COUNTRIES` tuple expanded to 6 countries (US + DE + EA + GB + JP + CA)
- [ ] Dispatcher routes GB/JP/CA correctly to TE
- [ ] Unit tests 5+ new (dispatcher + tuple + ADR compliance)
- [ ] Live canaries 3+ new (@pytest.mark.slow per country)
- [ ] NSS fit RMSE ≤ 10 bps per country
- [ ] Combined live canary wall-clock ≤ 45s
- [ ] CAL-CURVES-T1-SPARSE-INCLUSION CLOSED with commit refs
- [ ] 6 new CAL items opened for deferred T1 sparse (AU/NZ/CH/SE/NO/DK probe)
- [ ] Coverage daily_curves.py ≥ 90%
- [ ] Production validation manual run successful
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] §10 Pre-merge checklist executed
- [ ] Merge via `sprint_merge.sh`
- [ ] Retrospective shipped per v3 format
- [ ] ADR-0010 tier scope compliance verified

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-curves-t1-sparse-report.md`

**Final tmux echo**:
```
SPRINT E T1 SPARSE INCLUSION DONE: N commits on branch sprint-curves-t1-sparse-inclusion

T1_7_COUNTRIES expanded: 3 → 6 countries (US + DE + EA + GB + JP + CA)

Live canary results:
- GB: NSS RMSE [value] bps, [N] tenors
- JP: NSS RMSE [value] bps, [N] tenors
- CA: NSS RMSE [value] bps, [N] tenors

CAL-CURVES-T1-SPARSE-INCLUSION CLOSED.
6 new CAL items opened for AU/NZ/CH/SE/NO/DK probe sprints (ADR-0009).

Production impact: tomorrow 07:30 WEST overlays cascade gains GB/JP/CA functional.

T1 curves coverage post-merge: US + DE + EA + GB + JP + CA (6 of 16 T1 countries, 37.5%).
Remaining T1 curves: 4 EA periphery (PT/IT/ES/FR/NL via national CB sprints) + 6 T1 sparse (AU/NZ/CH/SE/NO/DK via probe sprints).

Paralelo with Sprint F: zero file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-curves-t1-sparse-inclusion

Artifact: docs/planning/retrospectives/week10-sprint-curves-t1-sparse-report.md
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

Live canaries (@pytest.mark.slow) run explicitly during Commit 3.

---

## 9. Notes on implementation

### Quick-ship discipline
Sprint E should be ~2-3h maximum. Trivial extension post-CAL-138 groundwork. Don't over-engineer.

### If dispatcher routing needs addition
CAL-138 retro suggests dispatcher was partially shipped. If grepping reveals GB/JP/CA routing incomplete, add minimal `elif country == "GB"` branches + equivalent — do NOT refactor to abstract dispatch pattern in this sprint. Defer refactor to Phase 2.5 quality sprint.

### Tenor spectrum per country
Per CAL-138 retro:
- GB: 12 tenors (GUKG series, 1M-30Y)
- JP: 9 tenors (GJGB series, 1M-40Y but truncate if NSS fit instability)
- CA: 6 tenors (GCAN series, NS-reduced — document in tests)

NSS fit expects ≥ 6 tenors per Phase 0 convention. CA at exactly 6 tenors = edge case; document if RMSE higher than DE reference.

### Paralelo discipline
Sprint F works in M2 CPI paths (connectors + builders + daily_monetary_indices). Sprint E works in daily_curves.py. Zero primary overlap.

### systemd service
Already set to `--all-t1` via CAL-138 Day 1 shipping. No changes needed this sprint. Tomorrow 07:00 WEST natural fire will pick up tuple expansion automatically.

### CAL items opened for deferred T1 sparse
Per ADR-0009 probe-before-scaffold discipline, AU/NZ/CH/SE/NO/DK each need empirical probe before deciding connector path:
- TE yield curve availability per country
- Native CB API availability (Reserve Bank of Australia, RBNZ, SNB, Riksbank, Norges Bank, Nationalbanken)
- Negative-rate era handling (CH/SE/DK)
- Tenor spectrum per country

Each probe sprint ~4-5h if connector path viable, OR HALT-0 pattern if not.

### ADR-0010 compliance
All T1 countries in expanded tuple (US + DE + EA + GB + JP + CA). Zero T2 slipped in. Brief format v3 header enforces.

### Script merge dogfooded
6th production use (Day 1 + Day 2 Sprint E). Apply learned patterns.

---

*End of Sprint E brief. 4-5 commits. T1 curves coverage 3 → 6 countries via trivial tuple expansion. Paralelo-ready with Sprint F.*
