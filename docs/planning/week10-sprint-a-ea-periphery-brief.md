# Week 10 Day 1+ Sprint A — CAL-CURVES-EA-PERIPHERY (5 EA members)

**Target**: Extend daily_curves multi-country to 5 EA periphery members (PT/IT/ES/FR/NL) via ECB SDW connector. Mirror Sprint CAL-138 DE pattern. Absorb `--all-t1` tuple inclusion for newly-supported countries.
**Priority**: HIGH (unblocks overlay cascade 5 additional T1; Phase 2 exit progression)
**Budget**: 4-5h CC
**Commits**: ~5-7
**Base**: branch `sprint-curves-ea-periphery` (isolated worktree `/home/macro/projects/sonar-wt-ea-periphery`)
**Concurrency**: PARALELO with Sprint B (per-country ERP live paths). Minimal file overlap.

**Brief format**: v3

---

## 1. Scope

In:
- `src/sonar/connectors/ecb_sdw.py` EXTEND — add PT/IT/ES/FR/NL yield curve fetch methods (mirror DE pattern from Sprint CAL-138)
- `src/sonar/pipelines/daily_curves.py` MODIFY — expand T1_7_COUNTRIES tuple to include PT/IT/ES/FR/NL; add dispatch routing
- Linker data per country (inflation-indexed bonds):
  - FR: OATi/OATei (well-established, reliable)
  - IT: BTP€I (decent coverage post-2007)
  - DE: already shipped Sprint CAL-138 — reuse
  - PT/ES/NL: limited historical; emit `LINKER_UNAVAILABLE` + fallback to DERIVED real curve
- Cassettes + live canaries per country (5 new cassettes, 5 new live canaries)
- Retrospective per v3 format

Out:
- GB/JP/CA inclusion in --all-t1 (Sprint CAL-138 deferred as CAL-CURVES-T1-SPARSE; separate follow-on sprint if decided)
- Non-EA T1 yields (AU/NZ/CH/SE/NO/DK — CAL-CURVES-T1-SPARSE broader scope)
- systemd service file changes (--all-t1 already set; tuple expansion alone suffices)
- M3 market-expectations per-country (depends curves, separate sprint)

---

## 2. Spec reference

Authoritative:
- `docs/backlog/calibration-tasks.md` — CAL-CURVES-EA-PERIPHERY entry
- `docs/planning/retrospectives/week10-sprint-cal138-report.md` — DE pattern + ECB SDW integration
- `src/sonar/connectors/ecb_sdw.py` — existing DE fetch methods (Sprint CAL-138)
- `src/sonar/connectors/bundesbank.py` — DE Bundesbank reference (may need EA periphery analog if ECB SDW insufficient)
- `src/sonar/pipelines/daily_curves.py` — current run_country + dispatcher
- `src/sonar/overlays/nss_curves/` — NSS fit logic (reused uniform)

**Pre-flight requirement**: Commit 1 CC:
1. Read Sprint CAL-138 retro + existing ECB SDW implementation
2. Probe ECB SDW dataflows for each EA periphery country:
   ```bash
   # PT yield curves via ECB SDW
   curl -s "https://data-api.ecb.europa.eu/service/data/YC?detail=dataonly&format=jsondata&startPeriod=2026-04-18&endPeriod=2026-04-22&filter=REF_AREA:PT" | head -100

   # Similar for IT, ES, FR, NL
   for country in PT IT ES FR NL; do
       echo "=== $country ==="
       curl -s "https://data-api.ecb.europa.eu/service/data/YC/B.U2.$country.R.L.L40.CI.0040Y?format=jsondata" | head -30
   done
   ```
3. Verify ECB SDW YC dataflow has per-country zero-coupon yield curves (not just EA aggregate)
4. If YC dataflow lacks per-country granular, probe FM (Financial Markets) dataflow for raw sovereign yields:
   ```bash
   for country in PT IT ES FR NL; do
       echo "=== $country sovereign 10Y via FM ==="
       curl -s "https://data-api.ecb.europa.eu/service/data/FM/B.$country.EUR.4F.BB.N.A.A.A.A.N.A?format=jsondata" | head -30
   done
   ```
5. Verify linker series availability:
   - FR OATei: FR generic indexed bond series
   - IT BTP€I: via ECB SDW or Banca d'Italia
   - PT/ES/NL: may require fallback to DERIVED method
6. Document findings Commit 1 body; narrow scope per HALT trigger 1 if any country lacks viable data.

---

## 3. Concurrency — PARALELO with Sprint B

**Sprint A worktree**: `/home/macro/projects/sonar-wt-ea-periphery`
**Sprint A branch**: `sprint-curves-ea-periphery`

**Sprint B (for awareness)**: per-country ERP live paths, worktree `/home/macro/projects/sonar-wt-erp-t1`

**File scope Sprint A**:
- `src/sonar/connectors/ecb_sdw.py` EXTEND (primary)
- `src/sonar/pipelines/daily_curves.py` MODIFY (T1_7_COUNTRIES tuple + dispatcher)
- `tests/unit/test_connectors/test_ecb_sdw.py` EXTEND (per country)
- `tests/integration/test_daily_curves_multi_country.py` EXTEND (live canaries per country)
- `tests/fixtures/cassettes/ecb_sdw/` (new cassettes per country)
- `docs/backlog/calibration-tasks.md` MODIFY (close CAL-CURVES-EA-PERIPHERY; open new CAL items if gaps)
- `docs/planning/retrospectives/week10-sprint-ea-periphery-report.md` NEW

**Sprint B file scope** (for awareness, DO NOT TOUCH):
- `src/sonar/overlays/erp/` directory (primary)
- `src/sonar/pipelines/daily_cost_of_capital.py` MODIFY
- `src/sonar/indices/monetary/builders.py` possibly (if ERP input assemblers)
- `tests/unit/test_overlays/test_erp/` new tests

**Zero primary-file overlap**. Secondary overlaps:
- `docs/backlog/calibration-tasks.md` — both sprints add/close CAL items (union-merge trivial)

**Rebase expected minor**: alphabetical merge priority → Sprint A ships first; Sprint B rebases if overlap.

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed: `git log origin/sprint-curves-ea-periphery` shows N commits
- [ ] Workspace clean: `git status`
- [ ] Pre-push gate green
- [ ] Branch tracking set
- [ ] Cassettes + canaries green
- [ ] systemd service unchanged (--all-t1 already set)

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-curves-ea-periphery
```

---

## 4. Commits

### Commit 1 — Pre-flight + ECB SDW PT/IT extension

```
feat(connectors): ECB SDW yield curve extension PT + IT

Pre-flight findings (Commit 1 body):
- ECB SDW YC dataflow per-country availability: [per country]
- ECB SDW FM dataflow alternative: [if YC sparse]
- Linker availability:
  - FR OATei: [series IDs]
  - IT BTP€I: [series IDs]
  - PT/ES/NL: [limited, confirm]

Extend ecb_sdw.py:
- PT fetch_yield_curve_nominal + fetch_yield_curve_linker (or LINKER_UNAVAILABLE)
- IT fetch_yield_curve_nominal + fetch_yield_curve_linker (BTP€I)

Tests:
- Unit: fetch PT happy path mocked + linker handling
- Unit: fetch IT happy path + linker
- @pytest.mark.slow live canary PT + IT for 2024-12-31

Cassettes shipped.

Coverage ecb_sdw.py extensions ≥ 90%.
```

### Commit 2 — ECB SDW ES/FR/NL extension

```
feat(connectors): ECB SDW yield curve extension ES + FR + NL

Mirror PT/IT pattern:
- ES fetch_yield_curve_nominal + linker (likely LIMITED)
- FR fetch_yield_curve_nominal + linker (OATei well-established)
- NL fetch_yield_curve_nominal + linker (likely LIMITED)

Tests per country — unit + @pytest.mark.slow canaries.

Cassettes per country.
```

### Commit 3 — Pipeline T1_7_COUNTRIES tuple expansion

```
refactor(pipelines): daily_curves T1_7_COUNTRIES expand PT/IT/ES/FR/NL

Update T1_7_COUNTRIES tuple to include 5 EA periphery members.
Current Sprint CAL-138: ("US", "DE", "EA")
Post this sprint: ("US", "DE", "EA", "PT", "IT", "ES", "FR", "NL")

Dispatcher routing:
- PT/IT/ES/FR/NL → ecb_sdw.fetch_yield_curve_nominal(country)
- Linker handling: try ecb_sdw.fetch_yield_curve_linker(); fallback DERIVED on LINKER_UNAVAILABLE

Tests:
- Unit: dispatcher routes PT/IT/ES/FR/NL correctly
- Unit: --all-t1 iterates new tuple
- Integration @slow: --all-t1 for 2024-12-31 persists US+DE+PT+IT+ES+FR+NL (EA aggregate may skip or persist)

Coverage pipeline ≥ 90%.

Update pipeline docstring with new T1 scope.
```

### Commit 4 — Cassettes + live canaries full suite

```
test: yield curve cassettes + live canaries 5 EA periphery

Cassettes added:
- ecb_sdw PT yield_curve_nominal + linker
- ecb_sdw IT yield_curve_nominal + linker
- ecb_sdw ES yield_curve_nominal + linker (LINKER_UNAVAILABLE likely)
- ecb_sdw FR yield_curve_nominal + linker (OATei)
- ecb_sdw NL yield_curve_nominal + linker (LINKER_UNAVAILABLE likely)

Live canaries (@pytest.mark.slow):
- tests/integration/test_daily_curves_multi_country.py EXTEND
- 5 new canaries (1 per country)
- Combined wall-clock ≤ 30s

Coverage maintained.
```

### Commit 5 — CAL closures + retrospective

```
docs(planning+backlog): Sprint A EA periphery retrospective + CAL closures

CAL-CURVES-EA-PERIPHERY CLOSED: resolved via Sprint A (commits [SHAs])

New CAL items if gaps:
- CAL-LINKER-ES-NL (limited indexed bond coverage)
- CAL-LINKER-PT (historical sparse)

Retrospective per v3 format:
docs/planning/retrospectives/week10-sprint-ea-periphery-report.md

Content:
- Connector outcomes matrix (5 EA periphery)
- NSS fit quality per country (RMSE bps)
- Linker coverage per country
- Flag emissions
- Pattern validation: ECB SDW extension canonical for EA
- Production impact: overlays cascade now functional for US+DE+PT+IT+ES+FR+NL (7 T1)
- §10 pre-merge checklist + §11 merge via script
- Paralelo with Sprint B: zero conflicts
```

---

## 5. HALT triggers (atomic)

0. **ECB SDW YC dataflow lacks per-country** — scope narrow to FM dataflow + SONAR NSS fit (analog to DE Bundesbank path).
1. **Any country lacks ≥ 6 tenors** — skip that country per HALT trigger 1 Sprint CAL-138 precedent; open CAL-CURVES-{CODE}-SPARSE.
2. **Linker universally unavailable** — emit `{COUNTRY}_LINKER_UNAVAILABLE` flag + DERIVED real curve; not a HALT.
3. **ECB SDW rate limits** — tenacity handles; document if persistent.
4. **Sprint B file conflict** — CALIBRATION-TASKS.md union-merge; trivial post-merge rebase.
5. **NSS fit convergence failure** — emit flag + skip country + log; CAL item opens for investigation.
6. **Cassette count < 10** — coverage gap; HALT.
7. **Live canary wall-clock > 40s combined** — optimize OR split.
8. **Pre-push gate fails** — fix before push.
9. **No `--no-verify`**.
10. **Coverage regression > 3pp** — HALT.
11. **Push before stopping** — script mandates; brief v3 §10 enforces.

---

## 6. Acceptance

### Global sprint-end
- [ ] ECB SDW connector serves PT/IT/ES/FR/NL
- [ ] `daily_curves.py` T1_7_COUNTRIES tuple expanded to 8 countries (was 3 post-CAL-138)
- [ ] Dispatcher routes PT/IT/ES/FR/NL correctly
- [ ] Cassettes ≥ 10 shipped (nominal + linker per country)
- [ ] Live canaries ≥ 5 @pytest.mark.slow PASS
- [ ] CAL-CURVES-EA-PERIPHERY CLOSED with commit refs
- [ ] Coverage ecb_sdw.py extensions ≥ 90%, daily_curves.py ≥ 90%
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] §10 Pre-merge checklist executed
- [ ] Merge via `sprint_merge.sh`
- [ ] Retrospective shipped per v3 format

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-ea-periphery-report.md`

**Final tmux echo**:
```
SPRINT A EA PERIPHERY DONE: N commits on branch sprint-curves-ea-periphery

Countries shipped: PT, IT, ES, FR, NL (5 EA periphery)
Total T1 curves coverage post-merge: US + DE + EA + PT + IT + ES + FR + NL (8 countries)

NSS fit RMSE per country: [list bps values]
Linker coverage: [list LINKER_AVAILABLE vs LINKER_UNAVAILABLE]

CAL-CURVES-EA-PERIPHERY CLOSED.

Production impact: tomorrow 07:30 WEST overlays cascade gains PT/IT/ES/FR/NL functional (ERP/CRP/rating-spread/expected-inflation).

Paralelo with Sprint B ERP: zero file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-curves-ea-periphery

Artifact: docs/planning/retrospectives/week10-sprint-ea-periphery-report.md
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

### ECB SDW pattern canonical
Sprint CAL-138 shipped DE via ECB SDW + Bundesbank. Sprint A extends 5 more EA countries via same shared connector. ECB SDW is EA-uniform — no per-country auth, one dataflow.

### Linker handling graceful
PT/ES/NL likely limited linker data. Pattern per Sprint CAL-138 DE: emit `LINKER_UNAVAILABLE` flag + fallback DERIVED real curve method. Not a HALT.

### T1_7_COUNTRIES tuple name retained
Despite holding 8 countries post-sprint, name `T1_7_COUNTRIES` kept for compat. Rename deferred (non-breaking semver concern).

### Paralelo discipline
Sprint A works in `ecb_sdw.py` + `daily_curves.py`. Sprint B works in `overlays/erp/` + `daily_cost_of_capital.py`. Zero primary overlap.

Shared secondary: `docs/backlog/calibration-tasks.md`. Union-merge pattern Week 9 documented.

### Script merge (dogfooding Day 1+2 Week 10)
`sprint_merge.sh` handles push + merge + cleanup atomic. If HALT at any step, surface error + do not manually intervene.

---

*End of Sprint A brief. 5-7 commits. 5 EA periphery countries curves operational. Paralelo-ready with Sprint B.*
