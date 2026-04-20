# L3 Indices (E2 + M3 + Credit) — Execution Brief (v2)

**Target**: Week 4 kickoff — L3 indices that do NOT depend on full ERP
**Priority**: HIGH (parallel track with ERP brief; unblocks M1 economic/monetary/credit signal dimensions)
**Budget**: 6–8h CC autonomous
**Commits**: ~8–10
**Base**: main HEAD (`d8166e2` or later)
**Parallel session**: runs concurrently with ERP brief in tmux `sonar`; see §Concurrency

---

## 1. Scope

In:
- **E2 Leading** (Economic Cycle): 10Y-2Y slope, NSS-derived — US, DE operational
- **M3 Market Expectations** (Monetary Cycle): 5y5y forward + BC credibility signal — US, DE, PT
- **L1-L4 Credit indices** (Credit Cycle subset): CRP-based, ratings-based — 7 T1 countries (US/DE/PT/IT/ES/FR/NL)
- `src/sonar/indices/` package scaffold (new)
- Alembic migration **008** (`index_values` + sibling tables per spec §8)
- Behavioral + integration tests
- Canonical output normalization `clip(50 + 16.67·z_clamped, 0, 100)` per SESSION_CONTEXT §Distinção crítica

Out:
- **E1 Growth, E3 Coincident, E4 Trailing** (economic cycle complement — need FRED GDP, employment series beyond current Week 2 scope)
- **M1 Effective Rates, M2 BC Stance, M4 Financial Conditions** (monetary complement)
- **F1 Valuations** (blocked on CAL-048 ERP — separate track)
- **F2 Momentum, F3 Risk Appetite, F4 Flows** (financial cycle complement)
- **L5 Sovereign Risk** (can defer — requires CRP historical depth not yet in place)
- L4 cycle classifiers (Week 5+)

---

## 2. Spec reference

- `docs/specs/indices/E2-leading.md` @ E2_v0.2 (post Phase 0 Bloco E2)
- `docs/specs/indices/M3-market-expectations.md` @ M3_v0.1
- `docs/specs/indices/L1-credit-to-gdp-gap.md` @ L1_v0.1
- `docs/specs/indices/L2-debt-service-ratio.md` @ L2_v0.1
- `docs/specs/indices/L3-sovereign-spread.md` @ L3_v0.1
- `docs/specs/indices/L4-cds-divergence.md` @ L4_v0.1
- `docs/specs/conventions/units.md`, `flags.md`
- `docs/specs/conventions/composite-aggregation.md` (Policy 1 fail-mode — relevant for future L4 cycle aggregation)
- SESSION_CONTEXT §Decision authority + §Brief format + §Distinção crítica (L3 normalization)

---

## 3. Concurrency — parallel session protocol

An ERP CC session runs concurrently in tmux `sonar`. Both push to main.

**Hard-locked resource allocation**:
- Migration number: this brief uses **008** (ERP uses 007). Do NOT pick 009 or above without checking `alembic heads`.
- `src/sonar/db/models.py`: append only between bookmark comments `# === Indices models begin ===` and `# === Indices models end ===`. ERP brief (Commit 1) creates both bookmarks. If bookmark absent when L3 Commit 1 starts → wait up to 10 min, re-pull, retry. If still absent after 10 min → create bookmarks defensively as first action, mark in commit body "bookmark creation due to ERP brief delay".
- `pyproject.toml`: this brief does NOT touch pdfplumber/openpyxl rows (ERP adds those). L3 may add `scikit-learn` (for z-score clipping helper) or prefer scipy (already present). Prefer scipy; avoid sklearn addition.

**Push race handling**:
- On `git push` rejection: `git pull --rebase origin main`, resolve, re-push. Never `--force`.
- If rebase conflict in `models.py` outside Indices bookmark zone → HALT (ERP brief violated bookmark discipline).
- If rebase conflict in migration 008 file → HALT (number collision; chat resolves).

---

## 4. Commits

### Commit 1 — Indices package scaffold + models bookmarks check

```
feat(indices): L3 indices package scaffold + models.py bookmark check

Create src/sonar/indices/ package:
- __init__.py with public exports
- exceptions.py (InsufficientInputsError base, per-index exceptions)
- base.py (IndexBase ABC: normalize_zscore_to_0_100, z_clamp, compute)
  per SESSION_CONTEXT §Distinção crítica: output = clip(50 + 16.67·z_clamped, 0, 100)

In src/sonar/db/models.py:
- Verify ERP brief has created both # === ERP models begin/end === and
  # === Indices models begin/end === bookmarks.
- If Indices bookmarks absent: create defensively (paired with ERP zone
  above) and note in commit body.
- Scaffold IndexValue ORM class inside Indices bookmark zone: (id,
  index_code, country_code, date, methodology_version, raw_value,
  zscore_clamped, value_0_100, sub_indicators_json, confidence, flags,
  source_overlays_json, created_at, UNIQUE triplet).

Tests: base normalization (z=0 → 50, z=+3 → 100 clipped, z=-3 → 0 clipped).
```

### Commit 2 — Alembic migration 008

```
feat(db): migration 008 index_values table + indexes

Single table index_values per SESSION_CONTEXT §Distinção (not separate
table per index — single polymorphic table keyed by index_code).

Columns: id PK, index_code TEXT (E2/M3/L1/L2/L3/L4/...), country_code,
date, methodology_version, raw_value REAL, zscore_clamped REAL,
value_0_100 REAL CHECK (0-100), sub_indicators_json TEXT,
confidence REAL CHECK [0,1], flags TEXT, source_overlays_json TEXT
(FK-equivalent: list of overlay fit_ids used), created_at.

UNIQUE (index_code, country_code, date, methodology_version).
Indexes: idx_iv_code_cd (index_code, country_code, date), idx_iv_cd
(country_code, date).

alembic upgrade/downgrade round-trip verified.
```

### Commit 3 — E2 Leading index (economic slope signal)

```
feat(indices): E2 Leading index — 10Y-2Y slope + subcomponents (US, DE)

src/sonar/indices/economic/e2_leading.py per spec E2_v0.2:
- Input: yield_curves_spot US/DE nominal + forward 2y1y (NSS-derived).
- Primary signal: 10Y-2Y slope bps. Historical z-score vs 5Y rolling mean.
- Sub-indicators (per spec E2): slope (70% weight), forward 2y1y spread
  (20%), NSS-implied recession probability proxy (10%).
- Normalize: clip(50 + 16.67·z_clamped, 0, 100). Higher → earlier-stage
  expansion; lower → inversion/recession signal.
- Country coverage Week 4 scope: US (FRED NSS) + DE (Bundesbank NSS).

Flags per flags.md:
- INSUFFICIENT_HISTORY (< 1260 business days, 5Y) → cap 0.75
- SLOPE_INVERTED (slope < 0) → informational, no confidence impact
- NSS_UPSTREAM_DEGRADED (inherit NSS confidence < 0.75) → cap 0.65

Confidence per flags.md propagation: min(NSS_confidence) · deduction rules.

Tests: fixtures us_2024_01_02 (pre-inversion post-hike cycle) and
de_2024_01_02 (positive slope). Historical z-score fixture
us_inversion_2022_07_13 (deepest inversion since 1981).
```

### Commit 4 — M3 Market Expectations index

```
feat(indices): M3 Market Expectations — 5y5y forward + anchor (US, DE, PT)

src/sonar/indices/monetary/m3_market_expectations.py per spec M3_v0.1:
- Input: yield_curves_forwards (5y5y nominal) + exp_inflation_canonical
  (5y5y BEI-derived) + bc_target from config/bc_targets.yaml.
- Primary signal: |5y5y_inflation_expectation - bc_target| (anchor
  deviation bps).
- Sub-indicators: nominal 5y5y level (40%), anchor deviation 5y5y (40%),
  BEI-vs-survey divergence from ExpInf (20%).
- Normalize: higher → well-anchored; lower → unanchored.
- Country coverage Week 4: US (ExpInf BEI live), DE (Bundesbank linker
  + ECB SPF proxy), PT (DERIVED per ExpInf).

Flags:
- ANCHOR_UNCOMPUTABLE (5y5y missing) → confidence 0
- BC_TARGET_UNDEFINED (country not in bc_targets.yaml) → flag NO_TARGET,
  skip anchor component, 70% weight redistributes
- INFLATION_METHOD_DIVERGENCE inherited from ExpInf → cap 0.80

Tests: us_2024_01_02 (Fed target 2%, 5y5y ~2.54% → drifting anchor),
de_2024_01_02 (ECB target 2%), pt_2024_01_02_derived (derived path).
```

### Commit 5 — Credit L1 Credit-to-GDP Gap

```
feat(indices): L1 Credit-to-GDP Gap — BIS WS_DSR + Eurostat (T1 countries)

src/sonar/indices/credit/l1_credit_to_gdp_gap.py per spec L1_v0.1:
- Input: BIS WS_DSR quarterly credit-to-GDP by country (validated Phase 0
  Bloco D — 7/7 endpoints OK per SESSION_CONTEXT).
- Primary: HP-filtered gap (lambda=400000 per BIS methodology) vs long-run
  trend. Signal: gap in pp.
- Sub-indicators: current gap (60%), 5Y change rate (20%), historical
  percentile (20%).
- Country coverage Week 4: US, DE, PT, IT, ES, FR, NL.
- Normalize: HIGHER gap → higher L1 value (credit boom signal).

Flags:
- INSUFFICIENT_HISTORY (< 40 quarters) → cap 0.60
- BIS_WS_DSR_STALE (last datapoint > 2 quarters old) → flag STALE, −0.15
- HP_FILTER_ENDPOINT_BIAS (within 4 quarters of series end) → flag
  ENDPOINT_UNSTABLE, −0.10

Depends on connectors/bis (WS_DSR validated). If connector absent from
current codebase, build minimal fetch_credit_to_gdp(country) wrapper
inside indices module (preferred: add to connectors/ package proper).
```

### Commit 6 — Credit L2 Debt Service Ratio

```
feat(indices): L2 DSR — BIS WS_DSR debt service ratio (T1 countries)

src/sonar/indices/credit/l2_debt_service_ratio.py per spec L2_v0.1:
- Input: BIS WS_DSR aggregate DSR quarterly.
- Primary: DSR level + 5Y z-score vs own history.
- Sub-indicators: current DSR (60%), trend 2Y change (30%), volatility
  5Y stdev (10%).
- Coverage: 7 T1 countries.
- Higher DSR z-score → higher L2 (debt stress signal).

Flags analogous to L1.

Tests: fixtures per 7 countries, synthetic time series for historical
percentile validation.
```

### Commit 7 — Credit L3 Sovereign Spread + L4 CDS-bond basis

```
feat(indices): L3 Sovereign Spread + L4 CDS-Bond Basis (T1 countries)

src/sonar/indices/credit/l3_sovereign_spread.py per spec L3_v0.1:
- Input: crp_canonical (SOV_SPREAD method preferred; RATING fallback).
- Primary: default_spread_bps vs historical 5Y distribution for country.
- Sub-indicators: current spread z-score (70%), 6M change (20%),
  vs-benchmark-history quartile (10%).
- Coverage: PT, IT, ES, FR, NL vs DE Bund. Benchmark DE = 0.

src/sonar/indices/credit/l4_cds_divergence.py per spec L4_v0.1:
- Input: crp_canonical.basis_default_spread_sov_minus_cds_bps (renamed
  per Day 1 spec C5).
- Since CDS branch deferred (WGB not validated), L4 emits:
  flag CDS_DATA_UNAVAILABLE, value_0_100 = 50 (neutral), confidence 0.30.
- When CDS later validates: real computation resumes automatically.

Tests: L3 fixtures for 5 periphery countries; L4 unit test for
degraded-state neutral output.

Two indices in one commit (thematic coherence: both are CRP-derived).
```

### Commit 8 — Persistence + orchestrator for L3 indices

```
feat(db): IndexValue persistence helper + compute_all_indices orchestrator

src/sonar/db/persistence.py additions:
- persist_index_value(session, IndexResult): single-row atomic upsert
  pattern (given uniqueness per index_code+country+date+version,
  caller provides via explicit overwrite=False default).
- persist_many_index_values(session, list[IndexResult]): batched.

src/sonar/indices/orchestrator.py:
- compute_all_indices(country, date, session) -> dict[str, IndexResult]:
  runs E2, M3, L1, L2, L3, L4 for given (country, date). Skip gracefully
  any index raising InsufficientInputsError. Returns available.
- CLI: python -m sonar.indices.orchestrator --country US --date 2024-01-02

Integration test: all 6 indices for US + DE 2024-01-02; assert
value_0_100 within [0,100]; assert flags.md propagation correct.
```

### Commit 9 — Week 4 L3 retrospective

```
docs(planning): L3 indices parallel-track retrospective

Summary of L3 indices session vs ERP parallel track:
- 6 indices operational: E2, M3, L1, L2, L3, L4
- 7 T1 countries coverage for credit (L1-L4)
- 2 countries coverage for E2 (US, DE)
- 3 countries coverage for M3 (US, DE, PT)
- Pipeline integration: indices consume NSS/ExpInf/CRP outputs live.
- Coverage + test count.
- Concurrency with ERP brief: merge conflicts resolved (if any), push
  race incidents (if any).
- Blockers for Week 5 (L4 cycle classifiers): need all 16 indices; F1
  still blocked on CAL-048 (ERP completion track).
```

---

## 5. HALT triggers (atomic)

1. `models.py` Indices bookmark zone conflicts on rebase — ERP brief violated discipline; surface to chat
2. Migration 008 collision with 007 or other number on rebase — halt, chat reconciles
3. BIS WS_DSR connector does not exist in current codebase AND L1/L2 cannot proceed with inline wrapper (scope inflation beyond brief) — halt, chat decides connectors/bis.py standalone commit vs defer
4. spec files for E2/M3/L1-L4 have version bumps since brief written — halt, verify brief still aligns
5. Coverage regression > 3pp on existing scopes — halt
6. Any index output outside [0,100] range post-normalization — halt (math bug)
7. HP filter (L1) statsmodels dependency missing — add via `statsmodels>=0.14` in pyproject.toml; if fails to install, halt (environment issue)

"User authorized in principle" does NOT cover specific triggers.

---

## 6. Acceptance

- [ ] 8-9 commits pushed, main HEAD matches remote
- [ ] Migration 008 applied clean; downgrade/upgrade round-trip green
- [ ] 6 index modules operational (E2, M3, L1, L2, L3, L4)
- [ ] `src/sonar/indices/` coverage ≥ 90%
- [ ] E2 US 2024-01-02 canonical: value_0_100 in valid range reflecting 2y-10Y slope of that date (deeply inverted → low value near 0-20)
- [ ] M3 US 2024-01-02: 5y5y anchor deviation flagged correctly vs Fed 2% target
- [ ] L1/L2/L3/L4 compute for 7 T1 countries 2024-01-02 (benchmarks DE + US = neutral L3=50 + L4=50 degraded)
- [ ] `python -m sonar.indices.orchestrator --country US --date 2024-01-02` outputs 6 index rows (E2, M3, L1, L2, L3, L4)
- [ ] No `--no-verify` pushes

---

## 7. Report-back artifact export (mandatory)

Single consolidated artifact: `docs/planning/retrospectives/l3-indices-implementation-report.md`

Structure:
```markdown
# L3 Indices Implementation Report

## Summary
- Duration: Xh Ymin / 6-8h budget
- Commits: N
- Status: COMPLETE / PARTIAL / HALTED
- Parallel track: ERP brief status at snapshot time

## Commits
| SHA | Scope |

## Coverage delta
| Scope | Before | After |

## Indices operational
| Index | Spec version | Countries | Notes |
| E2 Leading | E2_v0.2 | US, DE | ... |
| M3 Market Expectations | M3_v0.1 | US, DE, PT | ... |
| L1 Credit-to-GDP Gap | L1_v0.1 | 7 T1 | ... |
| L2 DSR | L2_v0.1 | 7 T1 | ... |
| L3 Sovereign Spread | L3_v0.1 | 5 periphery | ... |
| L4 CDS-Bond Basis | L4_v0.1 | 7 T1 (degraded) | CDS_DATA_UNAVAILABLE |

## Validation snapshot 2024-01-02
| Country | E2 | M3 | L1 | L2 | L3 | L4 |
| US | XX | YY | ZZ | ... |

## Concurrency events
- Push race conflicts: N (rebased cleanly / chat escalated)
- models.py bookmark respect: clean / violated
- Migration 008 numbering: clean / collision

## HALT triggers
[fired/resolved or "none"]

## Deviations from brief
[if any]

## New backlog items
[CAL/P2 surfaced]

## Blockers for Week 5
- L4 cycle classifiers need all 16 indices; F1/F2/F3/F4 financial cycle pending
- E1/E3/E4 economic complement pending FRED additional connectors
```

Commit report in final `docs(planning):` commit.

tmux echo on completion:
```
L3 INDICES DONE: N commits, 6 indices operational, XX% coverage
Parallel ERP status at snapshot: [running / done / halted]
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/l3-indices-implementation-report.md
```

---

*End of brief. Runs parallel to ERP brief. Migration 008 hard-locked. models.py Indices bookmark zone hard-locked.*
