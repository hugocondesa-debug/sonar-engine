# Week 6 Sprint 1b — MSC Monetary Indices (M1 + M2 + M4, US + M1 EA)

**Target**: Ship M1 Effective Rates, M2 Taylor Gaps, M4 FCI for US + M1 for EA via existing ECB SDW. Unblocks MSC composite Week 7.

**Priority**: HIGH (3 new L3 indices → 16/16 L3 shipped total; unblocks 3rd L4 cycle composite)

**Budget**: 5–7h CC autonomous (6-8h if M1 EA extension integrates smoothly)
**Commits**: ~10–13
**Base**: main HEAD post Sprint 2b (`6089572` or later)
**Concurrency**: Parallel to Week 6 Sprint 1 TE extension in tmux `sonar`. See §3.

---

## 1. Scope

In:
- `src/sonar/indices/monetary/` package (M3 already exists from Week 3.5)
  - `m1_effective_rates.py` per `M1_EFFECTIVE_RATES_v0.2`
  - `m2_taylor_gaps.py` per `M2_TAYLOR_GAPS_v0.1`
  - `m4_fci.py` per `M4_FCI_v0.1`
- `connectors/cbo.py` — new connector for CBO output gap (US only, for M2)
- `src/sonar/config/r_star_values.yaml` — hardcoded HLW r* quarterly values for US/EA (workaround until full HLW connector Phase 2+)
- `src/sonar/config/bc_targets.yaml` — central bank inflation targets (Fed 2%, ECB 2%, BoE 2%, BoJ 2%) per M2 spec §2 precondition
- FRED connector extension: WALCL (Fed balance sheet), DTWEXBGS (USD NEER), MORTGAGE30US, PCEPILFE (if not already), output gap-adjacent series
- ECB SDW connector usage for M1 EA: DFR policy rate + ILM balance sheet (connector already shipped)
- Alembic migration **014** — 3 dedicated tables per spec §8:
  - `monetary_m1_effective_rates`
  - `monetary_m2_taylor_gaps`
  - `monetary_m4_fci`
- ORM models in Indices bookmark zone
- Input builders analogous to E1/E3/E4 pattern
- Integration test US + EA smoke
- Retrospective

Out:
- M1 UK/JP coverage (requires BoE + BoJ connectors — Week 7+)
- M2 EA/UK/JP coverage (same reason)
- M4 EA/UK/JP coverage (requires custom-FCI 7-component + VSTOXX connector — Week 7+)
- **MSC composite** (L4 cycle) — next sprint after all 4 M-indices exist 7 T1
- **Shadow rate connector** (Krippner/Wu-Xia) — Phase 2+ (M1 algorithm gracefully uses policy rate when not ZLB; current US + EA are above ZLB)
- **Full HLW connector** (Laubach-Williams) — Phase 2+ (workaround via hardcoded YAML)
- **Output gap xcheck** (OECD EO / AMECO) — M2 ships with primary source only; xcheck deferred
- **T2-T4 country coverage** — US + EA only this sprint

---

## 2. Spec reference

Authoritative (verified 2026-04-20):
- `docs/specs/indices/monetary/M1-effective-rates.md` @ `M1_EFFECTIVE_RATES_v0.2` (v0.2: DFEDTAR removed, DFEDTARU/L pair primary)
- `docs/specs/indices/monetary/M2-taylor-gaps.md` @ `M2_TAYLOR_GAPS_v0.1`
- `docs/specs/indices/monetary/M4-fci.md` @ `M4_FCI_v0.1`
- `docs/specs/indices/monetary/README.md` — 30Y rolling canonical, 15Y T4 fallback, MSC formula preview (`0.30·M1 + 0.15·M2 + 0.35·M3 + 0.20·M4`)
- `docs/specs/conventions/units.md`, `flags.md`, `exceptions.md`
- SESSION_CONTEXT §Decision authority + §Brief format + §Regras operacionais

**Pre-flight requirement**: Commit 1 CC reads all 3 spec files (M1, M2, M4) end-to-end + monetary README. Document material deviations from brief §4 placeholder guidance. Spec weights/components/formulas authoritative. Pattern from Week 5 ECS + Sprint 2b — do NOT HALT for first deviation; HALT only if scope increase > 2x budget or architectural incompatibility.

Canonical normalization per README (applies all M-indices):
- z-score vs 30Y rolling window (canonical) / 15Y T4 fallback
- aggregate per spec §4 weights
- output: `clip(50 + 16.67·z, 0, 100)` — **higher = tighter stance** (sign convention critical)
- `lookback_years` column persisted

Existing assets:
- `src/sonar/connectors/fred.py` — extensive, extend with WALCL + DTWEXBGS + MORTGAGE30US if not present
- `src/sonar/connectors/ecb_sdw.py` — **exists** (confirmed via ls)
- `src/sonar/overlays/nss-curves` — consumed by M1 (3M short end), M4 (10Y level)
- `src/sonar/overlays/expected-inflation` — consumed by M1 (5Y for real rate), M2 (2Y forecast variant)
- `src/sonar/indices/monetary/m3_market_expectations.py` — shipped Week 3.5 (reference pattern)

---

## 3. Concurrency — parallel protocol with TE brief

TE brief runs concurrently in tmux `sonar`. Both push to main.

**Hard-locked resource allocation**:
- Migration number: **014** (TE brief creates no migration)
- `src/sonar/db/models.py`: this brief adds M1/M2/M4 ORMs inside existing `# === Indices models ===` bookmark (after M3 ORM shipped Week 3.5). TE brief doesn't touch models.py.
- `src/sonar/connectors/`: this brief creates `cbo.py` (new) + extends `fred.py` (new FRED series). TE brief modifies `te.py` only. Zero file overlap.
- `src/sonar/indices/`: this brief creates `indices/monetary/{m1,m2,m4}*.py`. TE brief modifies `indices/economic/builders.py`. Zero overlap (monetary vs economic packages).
- `src/sonar/config/`: this brief creates `r_star_values.yaml` + `bc_targets.yaml`. TE doesn't touch.
- Tests: separate directories/filenames per pattern
- `pyproject.toml`: neither brief expected to add deps

**Push race**:
- Normal `git pull --rebase origin main`
- Zero file collisions expected

**Start order**: TE brief arranca primeiro (smaller sprint). This brief arranca ~1 min depois.

---

## 4. Commits

### Commit 1 — Monetary indices package extension + ORMs

```
feat(indices): M1/M2/M4 scaffold + ORMs in models.py Indices zone

Extend src/sonar/indices/monetary/ package:
- __init__.py add M1/M2/M4 exports alongside existing m3_market_expectations
- Per-index modules scaffolded with dataclass skeletons:
  - M1Inputs, M1Result
  - M2Inputs, M2Result
  - M4Inputs, M4Result

In src/sonar/db/models.py inside # === Indices models === bookmark
(append after M3 ORM):
- M1EffectiveRatesResult ORM per spec §8
- M2TaylorGapsResult ORM per spec §8
- M4FciResult ORM per spec §8

Common columns for all 3 (Monetary-specific mixin):
- id, country_code, date, methodology_version, score_normalized,
  score_raw, components_json, lookback_years, confidence, flags,
  source_connector, created_at
- UNIQUE (country_code, date, methodology_version) each

Per-spec extra columns (from each spec §8):
- M1: shadow_rate_pct, real_rate_pct, r_star_pct, stance_vs_neutral_pct,
  balance_sheet_pct_gdp_yoy, es_subscore_real_shadow,
  es_subscore_rstar_gap, es_subscore_bs
- M2: taylor_1993_gap, taylor_1999_gap, taylor_inertia_gap,
  taylor_forward_gap, gap_median_pp, gap_range_pp, variants_computed
- M4: nfci_zscore, fci_composite_z, components_count, fci_regime
  (tight/neutral/loose)

Indexes: idx_m{1,2,4}_cd per standard pattern.

Sanity check commit body (v3 brief requirement):
  python -c "from sonar.db.models import M1EffectiveRatesResult, M2TaylorGapsResult, M4FciResult; print('OK')"

No migration yet — Commit 2.
```

### Commit 2 — Alembic migration 014 + 3 monetary tables

```
feat(db): migration 014 monetary indices (M1 + M2 + M4 tables)

3 dedicated tables per spec §8:
- monetary_m1_effective_rates
- monetary_m2_taylor_gaps
- monetary_m4_fci

Common preamble + per-spec extras (see Commit 1).
UNIQUE (country_code, date, methodology_version) each.
CHECK constraints: score_normalized [0,100], confidence [0,1].
Per-spec CHECK constraints:
- M1: real_rate_pct range, r_star_pct range
- M4: fci_regime IN ('tight', 'neutral', 'loose') if categorical

Indexes: idx_m{1,2,4}_cd on (country_code, date).

Alembic upgrade/downgrade round-trip verified clean.

Pre-flight: verify alembic heads = 013 (cycles from Sprint 2b).
If 014 claimed elsewhere, bump to 015.
```

### Commit 3 — FRED connector extension for monetary series

```
feat(connectors): FRED extension for M1/M2/M4 monetary series

Extend src/sonar/connectors/fred.py with new section:

# === Monetary indicators (M1 Effective Rates, M2 Taylor Gaps, M4 FCI) ===

Helper methods (thin wrappers, FRED series IDs):

For M1 Effective Rates:
- fetch_fed_funds_target_upper_us(start, end) — DFEDTARU
- fetch_fed_funds_target_lower_us(start, end) — DFEDTARL
- fetch_fed_funds_effective_us(start, end) — FEDFUNDS
- fetch_fed_balance_sheet_us(start, end) — WALCL (weekly, level)

For M2 Taylor Gaps:
- fetch_pce_core_yoy_us(start, end) — PCEPILFE (PCE ex food/energy)
  (US core inflation preferred by Fed)
- fetch_gdp_real_us(start, end) — already shipped; consume here

For M4 FCI:
- fetch_nfci_chicago_us(start, end) — NFCI (already shipped Week 4 CAL?)
  Verify existence; if present, reuse.
- fetch_anfci_chicago_us(start, end) — ANFCI (adjusted)
- fetch_hy_oas_us(start, end) — BAMLH0A0HYM2 (already Week 4 if shipped)
- fetch_ig_oas_us(start, end) — BAMLC0A0CM
- fetch_usd_neer_us(start, end) — DTWEXBGS (trade-weighted dollar)
- fetch_mortgage_30y_us(start, end) — MORTGAGE30US
- fetch_vix_us(start, end) — VIXCLS (may already exist; if so, reuse)

Delisted-series guards: some may be discontinued (verify Commit 3 live).
If fetch returns 404 → DataUnavailableError + flag {INDICATOR}_DELISTED
→ CAL item if material.

Tests:
- Cassette-replay per series
- @pytest.mark.slow live canary for 3 representative
  (DFEDTARU, PCEPILFE, NFCI)
- Coverage fred.py stays ≥ 95%
```

### Commit 4 — CBO output gap connector

```
feat(connectors): CBO output gap connector (US) for M2 Taylor

src/sonar/connectors/cbo.py subclasses BaseConnector.

Source: Congressional Budget Office (CBO) output gap data
Primary: https://www.cbo.gov/data/budget-economic-data (Excel releases)
Alternative: FRED may have CBO-derived series — verify
  (GDPPOT potential output series, then compute gap = GDP / GDPPOT - 1)

Implementation approach (2 paths):
Path A: FRED-backed if CBO potential GDP available on FRED
  (GDPPOT is a FRED series)
  - fetch_potential_gdp_us() → GDPPOT from FRED
  - Compute output_gap = (actual_GDP - potential_GDP) / potential_GDP
  - No new connector file needed; extend FRED section

Path B: CBO Excel download (fallback)
  - Download monthly release Excel from cbo.gov
  - Parse specific rows for potential GDP + actual GDP
  - Fragile; schema-drift guard mandatory

Start with Path A (trivial if GDPPOT exists). If absent, implement
Path B as new connector file.

Tests:
- Unit tests for gap calculation math
- Cassette for GDPPOT fetch
- @pytest.mark.slow live canary
- Coverage ≥ 92%
```

### Commit 5 — r* values YAML + bc_targets YAML config

```
feat(config): hardcoded r_star + inflation targets YAML

Create src/sonar/config/r_star_values.yaml:
  # Hardcoded HLW r* quarterly values (Phase 1 workaround; full HLW
  # connector Phase 2+ CAL-089 or similar)
  # Source: NY Fed HLW quarterly release (https://www.newyorkfed.org/research/policy/rstar)
  # Last update: 2024-Q4 release (2025-01)
  # Next update trigger: quarterly manual refresh

  US:
    r_star_pct: 0.008  # 0.8%, HLW Q4 2024
    last_updated: "2025-01-15"
    source: "NY Fed HLW Q4 2024"
  EA:
    r_star_pct: -0.005  # -0.5%, Holston-Laubach-Williams EA
    last_updated: "2025-01-15"
    source: "HLW EA equivalent Q4 2024"
  # PT: uses EA proxy (+ R_STAR_PROXY flag) per spec
  # UK: pending Phase 2+ manual entry

Create src/sonar/config/bc_targets.yaml:
  # Central bank inflation targets (stable config)
  # Per M2 spec §2 precondition

  Fed: 0.02       # 2% PCE core
  ECB: 0.02       # 2% HICP medium-term
  BoE: 0.02       # 2% CPI
  BoJ: 0.02       # 2% CPI (post-2013)
  RBA: 0.025      # 2-3% midpoint
  BoC: 0.02       # 2% CPI
  # Mapping to country_code:
  US: Fed
  EA: ECB
  DE: ECB
  PT: ECB
  IT: ECB
  ES: ECB
  FR: ECB
  NL: ECB
  UK: BoE
  JP: BoJ
  AU: RBA
  CA: BoC

Loader helper in src/sonar/config/loaders.py:
  - load_r_star_values() → dict[str, dict]
  - load_bc_targets() → dict[str, float]
  - Staleness check: r* last_updated > 95 days triggers CALIBRATION_STALE flag
    downstream (spec §2 precondition)

Tests: config load + staleness check + country → target resolution.
```

### Commit 6 — M1 Effective Rates implementation

```
feat(indices): M1 Effective Rates per M1_EFFECTIVE_RATES_v0.2

src/sonar/indices/monetary/m1_effective_rates.py per spec §4.

Inputs:
- policy_rate_pct: US → FRED DFEDTARU+DFEDTARL midpoint (spec preferred);
  fallback FEDFUNDS effective + flag FED_TARGET_RANGE.
  EA → ECB SDW DFR series.
- shadow_rate_pct: Krippner not yet implemented.
  Per spec §2 precondition: "fora do ZLB use policy_rate_pct como proxy
  (shadow_rate_pct = policy_rate_pct)". Currently US ~5%, EA ~3% — both
  above ZLB. Apply proxy.
- nss_short_end_pct: from yield_curves_spot fitted_yields_json["3M"]
  (US + EA nss overlays shipped Week 3)
- expected_inflation_pct: expected_inflation_canonical
  expected_inflation_tenors_json["5Y"] (US live; EA partial)
- r_star_pct: from r_star_values.yaml (hardcoded workaround)
- balance_sheet_pct_gdp_yoy: FRED WALCL (US) / ECB ILM (EA) divided by
  GDP (nominal); compute YoY change

Compute per spec §4:
1. Fetch all inputs for (country, date)
2. Resolve shadow_rate: policy_rate if not ZLB; policy_rate ≤ 0.5% =
   ZLB, use Krippner (unavailable → skip, flag SHADOW_RATE_UNAVAILABLE)
3. real_shadow_rate = shadow_rate - expected_inflation
4. stance_vs_neutral = real_shadow_rate - r_star (score_raw)
5. balance_sheet_signal = -(BS/GDP_t - BS/GDP_{t-12m})
6. Z-scores vs 30Y rolling (all 3 sub-components):
   - z(real_shadow_rate)
   - z(stance_vs_neutral)
   - z(balance_sheet_signal)
7. ES_raw = 0.50·z(real_shadow) + 0.35·z(stance) + 0.15·z(bs_signal)
8. score_normalized = clip(50 + 16.67·ES_raw, 0, 100)
9. Flags: FED_TARGET_RANGE, SHADOW_RATE_UNAVAILABLE (if ZLB + Krippner
   missing), R_STAR_PROXY (PT/IE/NL EA proxy), CALIBRATION_STALE (r*
   > 95 days), INSUFFICIENT_HISTORY (< 25Y obs)

Sign: higher = tighter. Z-scores preserve sign naturally.

Persistence via persist_m1_effective_rates_result helper.

Countries:
- US: full 3-component path
- EA: full (ECB SDW DFR + ILM BS + EA nss_short + EA exp_inflation partial)
- PT: EA proxy policy rate + EA r* proxy + EA nss_short + EA exp_inflation
  partial; flags EA_PROXY_MULTIPLE

Fixtures per spec §7 if defined. Synthetic spec-plausible otherwise.

Behavioral tests ≥ 18; coverage ≥ 90%.
```

### Commit 7 — M2 Taylor Gaps implementation

```
feat(indices): M2 Taylor Gaps per M2_TAYLOR_GAPS_v0.1

src/sonar/indices/monetary/m2_taylor_gaps.py per spec §4.

Inputs:
- policy_rate_pct: same as M1
- inflation_yoy_pct: FRED PCEPILFE (US core PCE); Eurostat prc_hicp_manr
  ex-energy-food (EA, if available)
- inflation_target_pct: from bc_targets.yaml
- inflation_forecast_h: expected_inflation_canonical 2Y tenor (forward-
  looking variant)
- output_gap_pct: CBO (US) via cbo connector or FRED GDPPOT-derived;
  EA via IMF WEO / OECD EO (**deferred this sprint — US only for M2**)
- r_star_pct: shared with M1 (r_star_values.yaml)
- prev_period_policy_rate_pct: self-table lookup previous month

Compute per spec §4 (4 Taylor variants):
1. Taylor 1993: r* + π + 0.5·(π - π*) + 0.5·output_gap
2. Taylor 1999: r* + π + 1.5·(π - π*) + 0.5·output_gap
3. Taylor with inertia: 0.85·prev_rate + 0.15·Taylor_1993
4. Forward-looking: r* + π_forecast + 0.5·(π_forecast - π*) +
   0.5·output_gap

gap_t = policy_rate - Taylor_variant_implied_rate

Aggregate:
- gap_median_pp = median of available variants (≥ 2 required; else raise)
- gap_range_pp = max(available) - min(available)
- variants_computed = count of available

Z-score vs 30Y rolling on gap_median_pp.
score_normalized = clip(50 + 16.67·z, 0, 100)
Sign: higher = tighter policy (positive gap = policy above rule = hawkish)

Flags: R_STAR_PROXY (PT/IE/NL), CALIBRATION_STALE (r*), STALE
(output_gap > 200 days), NO_TARGET (some EM — skip this sprint),
OVERLAY_MISS (forward-looking variant absent), INSUFFICIENT_VARIANTS
(< 2 variants computed → raise)

Countries:
- US: all 4 variants (output_gap US via CBO/GDPPOT, inflation PCEPILFE,
  target 2%, r* hardcoded)
- EA: M2 deferred this sprint (output_gap connector not built);
  flag OUTPUT_GAP_UNAVAILABLE + raise gracefully OR skip EA
  for M2 only (still ship M1 EA)

Behavioral tests ≥ 18; coverage ≥ 90%.
```

### Commit 8 — M4 FCI implementation

```
feat(indices): M4 FCI per M4_FCI_v0.1

src/sonar/indices/monetary/m4_fci.py per spec §4.

Inputs (US primary path):
- nfci_chicago: FRED NFCI (already shipped Week 4 F3 Risk Appetite)
- policy_or_shadow_rate_pct: from m1_effective_rates.shadow_rate_pct
  (cross-spec read via DB) OR connector
- gov_10y_yield_pct: from yield_curves_spot fitted_yields_json["10Y"]
- credit_spread_bps: FRED BAMLH0A0HYM2 (HY OAS) — already shipped
- equity_pe_zscore: derive from overlays/erp-daily (ERP contains P/E)
  OR accept NULL initial + flag PE_UNAVAILABLE
- fx_neer_zscore: FRED DTWEXBGS for US (new FRED helper Commit 3)
- mortgage_rate_pct: FRED MORTGAGE30US (new)
- vol_index: FRED VIXCLS (already shipped)

Compute per spec §4:
For US path: direct NFCI z-score (already standardized by Chicago Fed)
→ score_normalized
For non-US: custom 7-component FCI (weighted per spec weights):
  FCI_composite_z = Σ w_i · z_i for 7 components
  score_normalized = clip(50 + 16.67·FCI_composite_z, 0, 100)

Sign: higher = tighter conditions.

US path shipped this sprint; custom FCI for EA (PT/IE/NL per spec)
deferred Week 7+ (requires VSTOXX + ECB mortgage + EUR NEER which
exist but not fully wired into input builder).

Flags:
- OVERLAY_MISS (nss or erp unavailable)
- STALE (mortgage > 45 days, vol > 1 BD)
- CUSTOM_FCI_DEGRADED (< 5/7 components for EA path)

Behavioral tests ≥ 18; coverage ≥ 90%.
```

### Commit 9 — ECB SDW integration for M1 EA + Input builders

```
feat(indices): monetary input builders (US + EA) wiring real data

Extend/create src/sonar/indices/monetary/builders.py (analogous to
economic/builders.py pattern):

MonetaryInputsBuilder class:
- build_m1_inputs(country, date, fred_conn, ecb_sdw_conn, ...)
  → M1Inputs
  - US path: FRED primary
  - EA path: ECB SDW for DFR + ILM (balance sheet)
    - DFR dataflow key: "M.U2.EUR.4F.KR.DFR.LEV"
    - ILM balance sheet: "BSI.M.U2.Y.V.A.A.MAT.U2.2300.Z01.E"
    - Verify exact keys via Commit 9 live probe; document
  - PT path: EA proxy for DFR + EA r* proxy, flags

- build_m2_inputs(country, date, fred_conn, eurostat_conn, cbo_conn, ...)
  → M2Inputs
  - US only this sprint (output_gap via CBO)

- build_m4_inputs(country, date, fred_conn, ...) → M4Inputs
  - US only this sprint (NFCI-primary)

All builders handle None gracefully for missing inputs.

Unit tests: mocked connector responses + fallback paths.
Coverage builders.py ≥ 90%.
```

### Commit 10 — Integration smoke: M1 + M2 + M4 US + M1 EA

```
test(integration): monetary indices live smoke US + M1 EA

tests/integration/test_monetary_indices_live.py:

@pytest.mark.slow
def test_m1_us_live():
    """Compute M1 US for 2024-12-31. Assert:
    - score_normalized ∈ [0, 100]
    - stance_vs_neutral within plausible range (post-Fed hiking ~+200 bps)
    - Flags do NOT include SHADOW_RATE_UNAVAILABLE (above ZLB)
    - Flag R_STAR_PROXY absent (US has direct HLW)
    - Confidence ≥ 0.70"""

@pytest.mark.slow
def test_m2_us_live():
    """Compute M2 US for 2024-12-31. Assert:
    - score_normalized ∈ [0, 100]
    - ≥ 3 of 4 Taylor variants computed (gap_median_pp available)
    - gap_median_pp likely positive (Fed above rule per 2024 stance)
    - Confidence ≥ 0.70"""

@pytest.mark.slow
def test_m4_us_live():
    """Compute M4 US for 2024-12-31. Assert:
    - score_normalized ∈ [0, 100]
    - NFCI direct z-score path used (not custom-FCI)
    - Confidence ≥ 0.75"""

@pytest.mark.slow
def test_m1_ea_live():
    """Compute M1 EA for 2024-12-31. Assert:
    - score_normalized ∈ [0, 100]
    - Policy rate = ECB DFR
    - Balance sheet via ECB ILM
    - R_STAR_PROXY flag NOT present (EA has HLW-equivalent)
    - Confidence ≥ 0.65"""

Wall-clock ≤ 30s total.
```

### Commit 11 — Retrospective

```
docs(planning): Week 6 Sprint 1b monetary indices retrospective

File: docs/planning/retrospectives/week6-sprint-1b-msc-indices-report.md

Structure per prior retros:
- Summary (duration, commits, status)
- Commits table with SHAs + CI status
- Coverage delta per scope
- Tests breakdown (M1 + M2 + M4 + CBO connector + integration)
- US + EA 2024-12-31 snapshot: M1/M2/M4 scores + flags
- Deviations from brief (M2 EA deferred, M4 EA deferred, etc.)
- HALT triggers fired / not fired
- New backlog items:
  - Full Krippner shadow rate connector (Phase 2+)
  - Full HLW connector (Phase 2+)
  - OECD output gap xcheck
  - BoE / BoJ policy rate connectors (Week 7 UK/JP coverage)
  - Custom FCI 7-component EA path (Week 7)
- Sprint 2 readiness: MSC composite can ship for US when M3 (shipped
  Week 3.5) + M1/M2/M4 (this sprint) all produce rows for 2024-12-31.
  MSC composite brief next (~3-4h).
```

---

## 5. HALT triggers (atomic)

0. **Pre-flight spec deviation** — CC reads M1/M2/M4 specs + monetary README Commit 1. Document deviations. No HALT unless architectural incompat or scope > 2x budget.
1. **FRED delisted series** (e.g., DFEDTARU also delisted silently) → document + flag; alternative paths per spec §2
2. **ECB SDW dataflow key format unexpected** — DFR key structure empirical probe needed; if unresolvable in 30min, flag EA_UNAVAILABLE + skip M1 EA
3. **CBO GDPPOT not on FRED** — Path B (Excel scrape) implementation triggered; if scrape fragile, defer M2 to US-only without output gap xcheck → still ships 3 variants (1993/1999/inertia/forward)
4. **r* YAML workaround insufficient** — if spec §4 requires real-time HLW series lookup → flag CALIBRATION_STALE_WORKAROUND + document for Phase 2+ proper connector
5. **Migration 014 collision** with TE brief (shouldn't) → rebase
6. **models.py rebase conflict** outside Indices bookmark → TE brief violated discipline → HALT
7. **NSS or ExpInflation overlays missing** for test date → verify shipped Week 2-3; if absent, seed via existing patterns
8. **Coverage regression > 3pp** → HALT
9. **Pre-push gate fails** → fix before push, no `--no-verify`
10. **ORM silent drop** at Commit 1 — sanity check must pass
11. **Budget overflow > 2x** (> 14h vs 7h target) → HALT, reassess scope

"User authorized in principle" does NOT cover specific triggers.

---

## 6. Acceptance

### Per commit
Commit body checklist.

### Global sprint-end
- [ ] 10-13 commits pushed, main HEAD matches remote, CI green
- [ ] Migration 014 applied clean
- [ ] 3 new L3 compute modules (m1/m2/m4) + coverage ≥ 90% each
- [ ] CBO connector coverage ≥ 92%
- [ ] FRED extension (monetary section) coverage additions
- [ ] ECB SDW integration tested for DFR + ILM paths
- [ ] r_star_values.yaml + bc_targets.yaml loaded + tested
- [ ] US: M1 + M2 + M4 rows persist for 2024-12-31
- [ ] EA: M1 row persists for 2024-12-31 (M2 + M4 deferred per scope)
- [ ] All score_normalized ∈ [0, 100], confidence ∈ [0, 1]
- [ ] Full pre-push gate green every push (ruff + mypy full + pytest --no-cov)
- [ ] No `--no-verify`
- [ ] Full test suite green: targeting ~780 unit + ~60 integration tests total

---

## 7. Report-back artifact export (mandatory)

File: `docs/planning/retrospectives/week6-sprint-1b-msc-indices-report.md`

Structure per Commit 11 template.

**Per-commit tmux echoes**:
```
COMMIT N/10-13 DONE: <scope>, SHA, coverage delta, tests added, HALT status
```

**Final tmux echo**:
```
MSC INDICES DONE: N commits, M1+M2+M4 US operational + M1 EA operational
US 2024-12-31: M1=X (stance Ypp), M2=Z (gap Wpp), M4=V (NFCI-direct)
EA 2024-12-31: M1=T (stance Upp)
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/week6-sprint-1b-msc-indices-report.md
```

---

## 8. Pre-push gate (mandatory)

Before every `git push`:
```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov
```

Full project mypy — NOT scoped to committed files. No `--no-verify`.

---

## 9. Notes on implementation

### v0.2 M1 breaking change
M1 spec v0.2 removes DFEDTAR (single rate, discontinued 2008-12-16).
Use DFEDTARU + DFEDTARL pair midpoint OR FEDFUNDS effective. Both
valid per v0.2.

### Shadow rate workaround is valid per spec
"Fora do ZLB use policy_rate_pct como proxy" — spec explicitly allows.
Current US + EA are above ZLB (Fed ~5%, ECB ~3%). Shadow connector
deferral is fully spec-compliant, not a hack.

### r* YAML is temporary
Document in commit body + retro that hardcoded r* values are Phase 1
workaround pending Phase 2+ Krippner/HLW full connectors. Quarterly
manual refresh ritual noted in YAML comments.

### CBO output gap — verify GDPPOT first
FRED series GDPPOT (real potential GDP) is published by CBO.
If present → trivial wrap in fred.py (not separate connector needed).
If absent → CBO Excel scrape. Verify Commit 4.

### M4 US is simpler than M1
NFCI (Chicago Fed) already standardized z-score. M4 US = simple wrap
around that. Bulk of M4 work is custom-FCI logic (deferred EA).

### ECB SDW dataflow keys empirical
Like BIS SDMX (CAL-019 pattern), ECB SDW dataflow keys may need
empirical probing. Verify Commit 9 with live fetch before composing
builder.

### Parallel TE brief
Runs in tmux `sonar`. Zero file overlap. Pre-push gate catches.

---

*End of Week 6 Sprint 1b MSC indices brief. 10-13 commits, M1+M2+M4 US + M1 EA operational. MSC composite Week 6 Sprint 2 unblocked post-ship.*
