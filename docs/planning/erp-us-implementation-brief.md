# ERP US Full Implementation — Execution Brief (v2)

**Target**: Week 3.5 continuation — CAL-048 resolution (ERP US 4 methods)
**Priority**: HIGH (unblocks F1 Valuations Week 4 + upgrades k_e pipeline ERP stub)
**Budget**: 4–6h CC autonomous
**Commits**: ~6–8
**Base**: main HEAD (`d8166e2` or later)
**Parallel session**: runs concurrently with L3 indices brief in tmux `sonar-l3`; see §Concurrency

---

## 1. Scope

In:
- FactSet Earnings Insight PDF scraper (primary)
- Yardeni Earnings Forecasts PDF scraper (secondary, P2-028 consent assumed)
- multpl.com scrape (US dividend yield)
- S&P DJI buybacks PDF scrape (US)
- Shiller ie_data.xls download + parse (CAPE components)
- Damodaran histimpl.xlsx download + parse (monthly xval)
- `src/sonar/overlays/erp.py` 4-method compute (DCF + Gordon + EY + CAPE)
- Alembic migration **007** (erp_* tables per spec §8)
- ERP canonical aggregation + FactSet/Yardeni divergence flag
- Damodaran xval hook with `XVAL_DRIFT` flag
- Replace 5.5% stub in `pipelines/daily_cost_of_capital.py` with real ERP lookup
- Behavioral test suite per spec §7 fixtures

Out:
- EA ERP (deferred Week 4+ per scope — would need SXXP + ECB SPF growth via TE)
- UK/JP ERP (deferred)
- CAL-050 persistence helpers separate scope (defer until ERP lands + L3 brief closes)

---

## 2. Spec reference

- `docs/specs/overlays/erp-daily.md` @ ERP_CANONICAL_v0.1 (post-sweep `4820b85` — Yardeni + FactSet dual source confirmed)
- `docs/specs/conventions/units.md`, `flags.md`
- `docs/specs/overlays/nss-curves.md` @ NSS_v0.1 (risk-free consumption contract)
- SESSION_CONTEXT §Decision authority + §Brief format
- P2-028 (Yardeni consent: assumed granted per Hugo decision 2026-04-20)

---

## 3. Concurrency — parallel session protocol

A second CC session runs L3 indices brief concurrently in tmux `sonar-l3`. Both push to main.

**Hard-locked resource allocation**:
- Migration number: this brief uses **007** (L3 uses 008)
- `src/sonar/db/models.py`: append only between bookmark comments `# === ERP models begin ===` and `# === ERP models end ===`. Create both bookmarks in Commit 1 (initial models.py touch).
- `pyproject.toml` dependencies: if adding `pdfplumber>=0.11` or `openpyxl>=3.1`, L3 brief does NOT touch these rows — no conflict expected.

**Push race handling**:
- On `git push` rejection (non-fast-forward): `git pull --rebase origin main`, resolve any trivial conflicts (tests imports, init files), re-push. Never `--force`.
- If rebase surfaces conflicts in `models.py` outside ERP bookmark zone → HALT (L3 brief violated bookmark discipline; needs chat triage).
- If rebase surfaces conflicts in migration files → HALT (number collision; chat resolves).

---

## 4. Commits

### Commit 1 — models.py bookmarks + ERP models scaffolding

```
feat(db): add ERP model scaffolding + concurrency bookmarks in models.py

Create section bookmarks in src/sonar/db/models.py:
- "# === ERP models begin ===" / "# === ERP models end ==="
- "# === Indices models begin ===" / "# === Indices models end ==="

Inside ERP section: scaffold 5 ORM classes matching spec §8:
NSSYieldCurveSpot-pattern mirror for erp_dcf, erp_gordon, erp_ey,
erp_cape, erp_canonical. Shared common-preamble helper via mixin
(Declarative shared cols: id, erp_id, market_index, country_code,
date, methodology_version, confidence, flags, created_at, UNIQUE
triplet).

Scope: scaffolding only, no data yet. Migration 007 separate commit.
```

### Commit 2 — Alembic migration 007

```
feat(db): migration 007 erp_* tables per spec §8

Five tables: erp_dcf, erp_gordon, erp_ey, erp_cape, erp_canonical.
Common preamble inlined per table. CheckConstraint confidence [0,1].
UNIQUE (market_index, date, methodology_version) per table.
erp_canonical.erp_id UNIQUE (FK referenceable).
Method tables FK erp_id → erp_canonical.erp_id ON DELETE CASCADE.
Indexes idx_erp_*_md per spec §8.

alembic upgrade/downgrade round-trip verified clean.
```

### Commit 3 — Data source connectors (batch)

```
feat(connectors): ERP data sources (Shiller, Damodaran, multpl, spdji)

Four connectors built per spec §2:
- src/sonar/connectors/shiller.py: download ie_data.xls from
  http://www.econ.yale.edu/~shiller/data/ie_data.xls; parse via
  openpyxl (CAPE, 10Y real earnings avg, trailing earnings).
  Monthly refresh cadence; disk cache.
- src/sonar/connectors/damodaran.py: download histimpl.xlsx from
  https://pages.stern.nyu.edu/~adamodar/pc/datasets/histimpl.xlsx;
  parse monthly ERP row per date. xval consumer.
- src/sonar/connectors/multpl.py: scrape multpl.com for S&P 500
  dividend yield. Graceful DataUnavailableError on parse fail.
- src/sonar/connectors/spdji_buyback.py: S&P DJI quarterly buyback
  PDF scrape. Graceful degrade.

All: cassette-replayed unit tests, @pytest.mark.live canary, coverage
≥ 92% per module (hard gate overlays/connectors, per phase1-coverage-policy).

pyproject.toml: add openpyxl>=3.1 (Shiller xls), beautifulsoup4>=4.12
(multpl scrape). pdfplumber added in commit 4.
```

### Commit 4 — FactSet + Yardeni PDF scrapers

```
feat(connectors): FactSet Earnings Insight + Yardeni PDF scrapers

Two PDF scrapers for forward earnings estimates:
- src/sonar/connectors/factset_insight.py: weekly PDF at
  https://advantage.factset.com/hubfs/Website/Resources%20Section/
  Research%20Desk/Earnings%20Insight/EarningsInsight_MMDDYY.pdf.
  Extract forward 12M EPS, forward P/E, CY+1/CY+2 estimates,
  analyst consensus growth. pdfplumber table extraction.
- src/sonar/connectors/yardeni.py: weekly Earnings Squiggles PDF.
  Consent per P2-028 (Hugo authorization assumed pre-implementation,
  documentation pending in docs/governance/licensing/yardeni-consent-*.md).
  Extract current-year + next-year EPS forecasts, time-weighted
  forward per Earnings Squiggles methodology.

Both: graceful DataUnavailableError on parse/URL fail → caller flags
OVERLAY_MISS. Module docstrings document URL fragility + scraper
maintenance contract. Cassette fixtures for happy path; mock tests
for failure paths.

pyproject.toml: add pdfplumber>=0.11.
```

### Commit 5 — ERP compute core

```
feat(overlays): ERP 4-method compute US implementation (spec §4)

src/sonar/overlays/erp.py:
- Dataclasses (frozen, slots): ERPInput, ERPMethodResult, ERPCanonical,
  ERPFitResult composite.
- _compute_dcf(inputs): scipy.optimize.newton root-find per spec §4,
  bounded [0, 0.30], x0 = risk_free + 0.05. Catch ConvergenceError.
- _compute_gordon(inputs): dividend + buyback + g_sustainable - rf.
  g_sustainable = min(retention · ROE, cap 0.06).
- _compute_ey(inputs): forward_earnings/index_level - rf.
- _compute_cape(inputs): (1/CAPE) - real_rf. CAPE from Shiller;
  real_rf from yield_curves_real US 10Y.
- _compute_canonical(method_results): median of available, erp_range_bps,
  methods_available, confidence per spec E4 (cap min + deduct 0.05 per
  missing, aligns flags.md propagation).
- _compute_forward_eps_divergence(factset_eps, yardeni_eps): per spec §4
  step 8.5; flag ERP_SOURCE_DIVERGENCE when > 5%.
- fit_erp_us(inputs) -> ERPFitResult: orchestrates all methods atomically.

Exceptions: raise InsufficientDataError when < min_methods_for_canonical=2.
All yields/spreads stored decimal internally; bps at persistence boundary
per units.md.

No network in erp.py — inputs pre-fetched.
```

### Commit 6 — ERP persistence + Damodaran xval wiring

```
feat(db): ERP persistence helper + Damodaran xval integration

src/sonar/db/persistence.py:
- persist_erp_fit_result(session, result): atomic 5-row transaction
  (4 methods + canonical). DuplicatePersistError on UNIQUE violation.
  Pattern mirrors persist_nss_fit_result.

Damodaran xval wired into fit_erp_us: when date.month in histimpl,
compute xval_deviation_bps = |erp_dcf_bps - damodaran_bps|, flag
XVAL_DRIFT if > 20 bps. US only (spec §4 step 8 note).

Integration test: fetch connectors (cassette) → fit_erp_us → persist →
query → assert 5 rows persisted, canonical readable.
```

### Commit 7 — Behavioral test suite + fixtures

```
test(overlays): ERP US behavioral suite + spec §7 fixtures

Fixtures in tests/fixtures/erp-daily/ per spec §7:
- us_2024_01_02.json: canonical 4-method fit
- us_partial_3methods.json: FactSet down, 3 methods
- us_partial_2methods.json: DCF + CAPE only (min boundary)
- us_divergence_2020_03_23.json: COVID trough
- damodaran_xval_2024_01_31.json: xval sanity

Behavioral test classes:
- TestERPCanonical: median, range, methods_available, confidence
- TestDCF: newton convergence, ConvergenceError path
- TestGordon: retention cap behaviour
- TestEY + TestCAPE: straightforward formulas
- TestForwardEPSDivergence: FactSet vs Yardeni > 5% flag
- TestDamodaranXval: |dev| > 20 bps flag
- TestInsufficientData: < 2 methods raises
- TestPersistence: atomic 5-row, DuplicatePersistError

Target ≥ 25 behavioral tests, coverage ≥ 90% on erp.py.
```

### Commit 8 — Pipeline wiring (replace 5.5% stub)

```
feat(pipelines): replace ERP stub 5.5% with live fit_erp_us (US only)

src/sonar/pipelines/daily_cost_of_capital.py:
- For country=US: fetch ERP inputs (FactSet, Yardeni, Shiller, multpl,
  spdji, FRED SP500) → fit_erp_us → persist → read erp_canonical.
  erp_median_bps into k_e composition.
- For country ∈ {DE,PT,IT,ES,FR,NL}: keep interim fallback (ERP=EA
  proxy = US_ERP for Week 3.5, flag MATURE_ERP_PROXY_US). EA ERP
  proper is Week 4+ scope.
- CLI flag --all-t1 runs 7 countries; US uses live ERP, others use
  US as proxy with flag.

Integration test updates: US k_e now uses computed ERP not stub;
assert within plausible band (7-11% depending on current market).

Closes CAL-048. k_e pipeline is no longer degraded for US.
```

---

## 5. HALT triggers (atomic)

1. FactSet PDF URL 404 or HTTP 403 — halt, document current URL state, ship without FactSet (3-method ERP for US)
2. Yardeni PDF download returns 403 or TOS-related block — halt, P2-028 signal surface to Hugo
3. Shiller ie_data.xls schema changed (new columns / removed) vs known format — halt, parser adaptation decision
4. Damodaran histimpl.xlsx schema changed — halt, parser adaptation
5. Migration 007 collides with migration 008 from L3 brief (shouldn't, but if rebase reveals) — halt
6. Coverage regression > 3pp on overlays or connectors scope — halt, investigate
7. scipy.optimize.newton fails converge on canonical US 2024-01-02 fixture — halt, parameter tuning decision
8. `models.py` rebase conflict outside ERP bookmark zone — halt, L3 brief violated discipline

"User authorized in principle" does NOT cover specific triggers. Per SESSION_CONTEXT §Decision authority.

---

## 6. Acceptance

- [ ] 6-8 commits pushed, main HEAD matches remote
- [ ] Migration 007 applied clean; downgrade/upgrade round-trip green
- [ ] `src/sonar/overlays/erp.py` coverage ≥ 90%
- [ ] `src/sonar/connectors/` coverage ≥ 92% (hard gate)
- [ ] `src/sonar/db/persistence.py` persist_erp_fit_result coverage ≥ 90%
- [ ] US 2024-01-02 canonical fit: 4 methods all contribute, erp_median_bps within 400-600 range, no XVAL_DRIFT vs Damodaran Jan 2024
- [ ] FactSet + Yardeni both operational (or degraded path documented)
- [ ] `python -m sonar.pipelines.daily_cost_of_capital --country US --date 2024-01-02` produces row with real ERP (not 5.5% stub)
- [ ] CAL-048 closed in calibration-tasks.md
- [ ] No `--no-verify` pushes

---

## 7. Report-back artifact export (mandatory)

Write progressive reports as sub-stages complete:

Single consolidated artifact: `docs/planning/retrospectives/erp-us-implementation-report.md`

Structure:
```markdown
# ERP US Implementation Report

## Summary
- Duration: Xh Ymin actual / 4-6h budget
- Commits: N
- Status: COMPLETE / PARTIAL / HALTED

## Commits
| SHA | Scope |

## Coverage delta
| Scope | Before | After |

## Tests
- Added: N behavioral
- Pass rate: X/Y

## Validation
- US 2024-01-02 canonical: {dcf_bps, gordon_bps, ey_bps, cape_bps, median_bps, range_bps}
- Damodaran xval: |deviation| bps
- FactSet vs Yardeni divergence: %

## Connector validation outcomes
| Connector | Status | Notes |

## HALT triggers
[fired/resolved or "none"]

## Deviations from brief
[if any]

## New backlog items
[CAL/P2 surfaced]

## Integration with pipeline
- k_e US pre-brief: 5.5% stub
- k_e US post-brief: X.X% computed
- Other 6 countries: using US proxy with MATURE_ERP_PROXY_US flag

## Blockers for next work
- CAL-050 persistence still pending (separate brief, if desired)
- EA/UK/JP ERP deferred
```

Commit report in final `docs(planning):` commit after push 8.

tmux echo on completion:
```
ERP US IMPLEMENTATION DONE: N commits, erp.py XX% cov, k_e US upgraded from stub to computed
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/erp-us-implementation-report.md
```

---

*End of brief. Runs parallel to L3 indices brief. Migration 007 hard-locked. models.py ERP bookmark zone hard-locked.*
