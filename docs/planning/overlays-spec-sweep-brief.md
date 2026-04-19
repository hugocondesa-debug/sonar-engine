# Overlays Spec Doc Sweep — Execution Brief (v2)

**Target**: Pre-Week 3 implementation (run after Week 2 close)
**Priority**: HIGH (blocker for Week 3 spec-driven implementation)
**Budget**: 45–75 min CC autonomous
**Commits**: 2 (specs + CAL entries)
**Base**: main HEAD post Week 2 close

---

## 1. Scope

In:
- `docs/specs/overlays/erp-daily.md` — 6 consistency fixes
- `docs/specs/overlays/crp.md` — 6 consistency fixes
- `docs/specs/overlays/expected-inflation.md` — 6 consistency fixes
- `docs/backlog/calibration-tasks.md` — 10 new CAL entries for placeholders + connector validation

Out: no code changes. Pure doc + backlog.

---

## 2. Spec reference

- `docs/specs/conventions/units.md` — spreads in bps, yields decimal
- `docs/specs/conventions/flags.md` — propagation rules (cap-then-deduct, additive)
- SESSION_CONTEXT §Brief format + §Decision authority

---

## 3. Commits

### Commit 1/2 — specs consistency sweep

Three files touched. Apply all fixes below in order; no behavioral change; methodology_versions unchanged.

#### erp-daily.md

**E1** — §4 units normalization. Find the units comment line:
```
> Units: per-method tables armazenam `erp_pct` decimal (ex: `0.0482`); canonical table armazena `_bps` integer (ex: `482`). `conventions/units.md` §Spreads.
```
Replace with:
```
> Units: all ERP values stored as `erp_bps` INTEGER across per-method and canonical tables, per conventions/units.md §Spreads. Compute in decimal internally; convert at persistence boundary via `int(round(decimal × 10_000))`.
```

Then in §8 Storage schema, rename `erp_pct REAL` → `erp_bps INTEGER` across all 4 method tables (`erp_dcf`, `erp_gordon`, `erp_ey`, `erp_cape`). Keep REAL diagnostic columns (`implied_r_pct`, `forward_pe`, `cape_ratio`, etc.) as-is — those are intermediate quantities, not the ERP spread.

In §7 fixtures column "Expected", rename per-method `dcf≈0.0482` notation to `dcf_bps≈482`, etc.

**E2** — §2 preconditions relax. Find:
```
- `methodology_version` row da `yield_curves_spot/real` batem com runtime ou raise `VersionMismatchError`.
```
Replace:
```
- `methodology_version` of upstream `yield_curves_spot/real` matches major version of runtime (e.g. `NSS_v0.*` compatible within major). Minor version mismatch emits `UPSTREAM_VERSION_DRIFT` flag (−0.05 confidence) but proceeds. Major version mismatch raises `VersionMismatchError`.
```

**E3** — §2 market data, add footnote after `TE` reference:
```
> **Connector validation pending Week 3 (CAL-035)**: TE `/markets/historical/*:IND` endpoints not empirically validated for daily EOD reuse. Fallback: skip EA/UK/JP ERP if TE unavailable; US ships independently via FRED `SP500`.
```

**E4** — §4 pipeline step 5 (canonical confidence formula). Find:
```
   - `confidence_canonical = min(method_confidences) · (methods_available / 4)`.
```
Replace:
```
   - `confidence_canonical = min(method_confidences)`, capped by floor; then deduct `0.05 × (4 − methods_available)` per missing method (aligns with flags.md propagation: cap-then-deduct, additive). Clamp `[0, 1]`.
```

**E5** — §7 fixtures, append row:
```
| `us_partial_2methods` | Only Gordon + EY available (DCF + CAPE data missing) | `methods_available=2`; canonical computed; flags `OVERLAY_MISS` + method-specific | min-boundary coverage |
```

**E6** — §6 edge cases, append row before the "Market slug unknown" row:
```
| `histimpl.xlsx` connector unavailable OR date.month not in file | `xval_deviation_bps = NULL`; no `XVAL_DRIFT` flag emitted | no impact |
```

#### crp.md

**C1** — §2 parameters. Append bracketed CAL references to each placeholder:
- After `*placeholder — recalibrate after 12m of production data*` on `cds_liquidity_threshold_bps`, add: ` (tracked in CAL-036)`
- After `*placeholder — recalibrate after 18m*` on `vol_ratio_bounds`, add: ` (tracked in CAL-037)`
- After `*placeholder — recalibrate after 18m*` on `rating_cds_divergence_threshold_pct`, add: ` (tracked in CAL-038)`

**C2** — §2 inputs. After the `twelvedata` and `yfinance` table rows, append note:
```
> **Connector validation pending (CAL-039)**: `twelvedata` tier/licensing and `yfinance` scrape stability unvalidated in Phase 0 D-block. Week 3 CRP ships with `damodaran_standard_ratio = 1.5` as default vol_ratio until CAL-039 closes; country-specific vol_ratio activates per-country as each connector validates.
```

**C3** — §2 inputs. After `connectors/wgb` row, append footnote:
```
> **WGB validation status**: check `docs/data_sources/credit.md` before Week 3 CRP CDS branch implementation. If unvalidated, Week 3 ships CRP via SOV_SPREAD + RATING branches only; CDS deferred to Week 4.
```

**C4** — §4 formulas. Find line:
```
CRP_method_bps = int(round(default_spread_method_bps × vol_ratio))          # Damodaran core identity
```
Replace:
```
CRP_method_decimal = (default_spread_method_bps / 10_000) × vol_ratio        # compute in decimal
CRP_method_bps     = int(round(CRP_method_decimal × 10_000))                 # round at persistence layer only
```
Update §8 `crp_cds`, `crp_sov_spread`, `crp_rating` to add `crp_decimal REAL NOT NULL` alongside `crp_bps INTEGER NOT NULL` (both stored; `_bps` is rounded display, `_decimal` is source of truth for recomputation).

**C5** — §8 schema `crp_canonical`. Rename column:
```sql
basis_bond_minus_cds_bps    INTEGER,
```
to:
```sql
basis_default_spread_sov_minus_cds_bps    INTEGER,  -- default_spread_sov_bps − cds_5y_bps; NOT crp_sov_spread_bps − crp_cds_bps
```

**C6** — §6 edge cases. Find row:
```
| Argentina-class distressed (CDS > 1500 bps) | emit; flag `CRP_DISTRESS`; CI wide | cap 0.60 |
```
Replace threshold-citation with config reference:
```
| CDS > `config/crp.yaml::distress_cds_threshold_bps` (default 1500) | emit; flag `CRP_DISTRESS`; CI wide | cap 0.60 |
```

Add to §2 parameters block:
```
- `distress_cds_threshold_bps = 1500` (config/crp.yaml). *Placeholder — recalibrate post-observation (CAL-040).*
```

#### expected-inflation.md

**I1** — §4 DERIVED formula. Append paragraph after the formula block:
```
> **Phase 1 simplification**: differential applied flat across all tenors (1Y = 30Y same delta). Economically, long-dated PT-EA differential likely converges (EU convergence hypothesis); short-dated responds to local shocks. Per-tenor differential computation deferred to Phase 2 (CAL-041).
```

**I2** — §2 Hierarchy table. After the table, append scope note:
```
> **Week 3 connector scope**: US (FRED validated) + EA via ECB SDW (Day 4 Week 2) + DE via Bundesbank (Day 5 Week 2) + PT via DERIVED (Eurostat HICP validated). UK/JP/EM defer to Week 4+ pending `boe_dmp`, `boj_tankan`, `imf_weo`, `focuseconomics` connector validation (CAL-042).
```

**I3** — §4 add pipeline step between current 8 and 9. Renumber subsequent steps.
```
8.5. **IRP haircut (optional)**: if `config/crp.yaml::irp_haircut_bps[tenor]` configured for `(country, tenor)`, subtract from canonical BEI-sourced tenors only. Not applied to SWAP, DERIVED, SURVEY sources (only BEI contains inflation risk premium). Formula: `canonical_tenors_json[tenor] -= irp_haircut_bps[tenor] / 10_000` for BEI-sourced tenors.
```

**I4** — §2 Hierarchy table PT row. Find:
```
| **PT** | ECB SPF → **DERIVED** | **DERIVED** (EA BEI + PT-EA diff) | DERIVED | — |
```
Replace:
```
| **PT** | ECB SPF (if PT-specific question available) → DERIVED | **DERIVED** (EA BEI + PT-EA diff, flat-tenor approximation) | DERIVED | — |
```

Append to §6 edge cases:
```
| PT 1Y/2Y via DERIVED (5Y rolling differential applied to short-dated tenor) | emit; flag `DIFFERENTIAL_TENOR_PROXY` | −0.10 on 1Y/2Y canonical rows only |
```

**I5** — §6 edge cases. Find row:
```
| Country `CN`/`TR`/`AR` (no operative BC target) | skip `anchor_status`; flag `NO_TARGET` | (no impact) |
```
Replace:
```
| Country with no effective inflation target (CN — PBOC no explicit numeric target; AR — hyperinflation, targeting suspended 2018+) | skip `anchor_status`; flag `NO_TARGET` | (no impact) |
| Country with targeting regime but high deviation from target band (TR — CBRT 5%±2pp vs actual 40-70% recent) | emit `anchor_status="unanchored"`; flag `EM_COVERAGE` | cap 0.50 |
```

**I6** — §4 pipeline step 7. Find:
```
6. Compute `confidence` per method (§6 matrix) + inherit upstream flags.
```
Replace:
```
6. Compute `confidence` per method (§6 matrix). Inherit upstream flags per source:
   - BEI: inherits `yield_curves_spot.flags` for (country, date, tenor)
   - SWAP: no upstream inheritance (fresh from connector)
   - DERIVED: inherits EA aggregate BEI `yield_curves_spot.flags` (country=DE or EA)
   - SURVEY: no upstream inheritance (fresh from survey connector)
```

Commit msg:
```
docs(specs): ERP/CRP/Expected Inflation consistency sweep pre-Week 3

18 fixes across 3 overlay specs, zero methodology_version bumps:

erp-daily.md:
- E1 units normalization: per-method erp_pct → erp_bps across storage
- E2 version pinning relaxed: major-version compatibility + DRIFT flag
- E3 TE connector pending validation note (CAL-035 reference)
- E4 canonical confidence aligned to flags.md propagation
- E5 min-boundary fixture us_partial_2methods added
- E6 histimpl.xlsx unavailable edge case explicit

crp.md:
- C1 placeholders cross-referenced to CAL-036/037/038
- C2 twelvedata/yfinance validation pending note (CAL-039)
- C3 WGB validation gate note for Week 3 scope
- C4 CRP formula stores _decimal + _bps (precision preservation)
- C5 basis column renamed for disambiguation
- C6 distress threshold moved to config (CAL-040)

expected-inflation.md:
- I1 DERIVED flat-tenor limitation documented (CAL-041)
- I2 Week 3 connector scope note (CAL-042)
- I3 IRP haircut pipeline step 8.5 explicit
- I4 PT 1Y/2Y DERIVED proxy flag added
- I5 CN/TR/AR anchor edge cases corrected
- I6 upstream flag inheritance table explicit

No behavioral change. Storage schema changes (C4 _decimal column, E1
_pct → _bps rename) do NOT require migration — tables not yet created.
```

### Commit 2/2 — CAL entries

Add 8 new CAL entries to `docs/backlog/calibration-tasks.md` (after CAL-034, in numeric order):

```
### CAL-035 — TE /markets/historical endpoints validation
Priority MEDIUM · Trigger Week 3 ERP EA/UK/JP
**Scope**: Empirically validate TE `/markets/historical/{SXXP,FTAS,TPX}:IND` endpoints for daily EOD reuse: availability, rate limits, licensing for our use case, historical depth (min 10Y for CAPE). Document results in docs/data_sources/financial.md.
**Blocker for**: Week 3 ERP EA/UK/JP implementation.

### CAL-036 — CDS liquidity threshold calibration
Priority LOW · Trigger post 12m production data
**Scope**: Current `cds_liquidity_threshold_bps = 15` (bid-ask) is placeholder from spec draft. Collect 12m production CDS bid-ask data, recalibrate threshold based on empirical distribution (e.g. 75th percentile of observed bid-ask as cutoff).
**Ref**: crp.md §2 parameters.

### CAL-037 — vol_ratio bounds calibration
Priority LOW · Trigger post 18m production data
**Scope**: Current `vol_ratio_bounds = (1.2, 2.5)` placeholder. Recalibrate empirically: compute vol_ratio distribution across 30+ countries × 18m, set bounds at percentiles 5-95 or use robust z-score clipping. Damodaran standard 1.5 remains fallback.
**Ref**: crp.md §2 parameters.

### CAL-038 — rating-CDS divergence threshold calibration
Priority LOW · Trigger post 18m production data
**Scope**: Current `rating_cds_divergence_threshold_pct = 50` placeholder. Recalibrate on observed |cds − rating_implied| / cds distribution; likely 75th or 90th percentile.
**Ref**: crp.md §2 parameters.

### CAL-039 — Equity/bond vol data source validation
Priority MEDIUM · Trigger Week 3 CRP (vol_ratio country-specific branch)
**Scope**: Validate `twelvedata` (equity index daily 5Y history, Tier/licensing review) and `yfinance` (bond ETF price series, scrape stability, ToS). Alternatives if both fail: (a) TE equity history + derived bond vol via sovereign NSS yield changes; (b) Damodaran standard 1.5 permanent.
**Blocker for**: CRP country-specific vol_ratio Week 3+; CRP ships with damodaran_standard=1.5 interim.

### CAL-040 — CRP distress CDS threshold calibration
Priority LOW · Trigger post-observation
**Scope**: Current `distress_cds_threshold_bps = 1500` placeholder (Argentina-class). Recalibrate empirically on observed distressed sovereigns CDS distribution over 5Y+.
**Ref**: crp.md §2 parameters + §6 edge cases.

### CAL-041 — PT-EA inflation differential per-tenor refinement
Priority LOW · Trigger Phase 2
**Scope**: Current DERIVED formula applies flat 5Y rolling PT-EA HICP differential across all tenors (1Y/2Y/5Y/10Y/30Y). Economically, long-dated differential should converge (EU convergence); short-dated responds to local shocks. Investigate per-tenor differential via term_factor scaling or tenor-specific rolling windows.
**Ref**: expected-inflation.md §4 DERIVED + §6 edge cases.

### CAL-042 — Expected inflation connector validation (UK/JP/EM)
Priority MEDIUM · Trigger Week 4+ ExpInf expansion beyond US/EA/DE/PT
**Scope**: Validate 4 connectors: `boe_dmp` (UK DMP survey quarterly, web API/CSV), `boj_tankan` (JP BoJ Tankan quarterly, XML feed), `imf_weo` (IMF WEO CPI projections semi-annual, database API), `focuseconomics` (EM Tier 3 monthly consensus, CSV subscription ToS review).
**Blocker for**: UK/JP/EM ExpInf coverage Week 4+.
```

Update existing CAL entries if they reference spec text changed in commit 1:
- CAL-029 (closed) — no change
- CAL-030 — no change (NSS, not these specs)
- CAL-031 (closed) — no change
- CAL-032 (closed) — no change
- CAL-033 — no change

Commit msg:
```
docs(backlog): 8 CAL entries for ERP/CRP/ExpInf placeholders + connector validation

CAL-035 MEDIUM: TE market data endpoints empirical validation
CAL-036 LOW: CDS liquidity threshold recalibration (12m prod)
CAL-037 LOW: vol_ratio bounds recalibration (18m prod)
CAL-038 LOW: rating-CDS divergence threshold recalibration (18m prod)
CAL-039 MEDIUM: twelvedata/yfinance validation (CRP vol_ratio)
CAL-040 LOW: CRP distress CDS threshold recalibration
CAL-041 LOW: PT-EA differential per-tenor refinement (Phase 2)
CAL-042 MEDIUM: UK/JP/EM expected inflation connector validation

Pairs with 78c3c20 spec sweep referencing these IDs.
```

---

## 4. HALT triggers

1. Any spec fix introduces a contradiction with `conventions/units.md` or `conventions/flags.md` (authoritative) — halt, clarify
2. Storage schema change in commit 1 (C4 adding `_decimal` columns, E1 renaming `_pct` → `_bps`) conflicts with any already-committed migration — halt, reconcile
3. CAL numbering collision (someone else added CAL-035 in parallel) — halt, renumber

---

## 5. Acceptance

- [ ] 2 commits pushed, main HEAD matches remote
- [ ] All 18 issue fixes applied verbatim (E1-E6, C1-C6, I1-I6)
- [ ] 8 CAL entries added in numeric order
- [ ] `grep -c "CAL-04" docs/backlog/calibration-tasks.md` returns ≥ 3 (CAL-040, 041, 042)
- [ ] `grep -c "methodology_version" docs/specs/overlays/erp-daily.md` unchanged from pre-sweep (versions intact)
- [ ] Hooks pass clean (no `--no-verify`)

---

## 6. Report-back

1. 2 commit SHAs
2. Diff stats per file (`git show --stat`)
3. CAL count after sweep (`grep -c "^### CAL-" docs/backlog/calibration-tasks.md`)
4. Any issue fix that required interpretation beyond verbatim (flag in report)
5. Timer vs budget

---

*End of brief.*
