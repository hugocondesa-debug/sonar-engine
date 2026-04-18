# Expected Inflation — Spec

> Layer L2 · overlay · slug: `expected-inflation` · methodology_version: `EXP_INF_CANONICAL_v0.1` (canonical hierarchy); per-method versions em §4.
> Last review: 2026-04-19 (Phase 0 Bloco E1)

## 1. Purpose

Produz term structure diária de expected inflation (`1Y`, `2Y`, `5Y`, `5y5y` forward, `10Y`, `30Y`) para **17+ countries** via hierarquia de métodos: breakeven directo (`BEI`), inflation swaps, síntese regional+differential (Portugal, Spain, periphery sem linker próprio), survey-based (SPF, Michigan, ECB SPF, BoJ Tankan) e consensus forecast. Primitivo para real yields (`nss-curves.yield_curves_real` derived path), anchoring assessment (MSC Dilemma) e PPP FX forwards (CRP).

## 2. Inputs

### Data inputs

| Input | Source connector | Freq | Used by |
|---|---|---|---|
| `nominal_yield(τ)` decimal | `overlays/nss-curves.yield_curves_spot` | daily | BEI (subtrahend) |
| `linker_real_yield(τ)` decimal | per-country linker connector (§ hierarchy) | daily | BEI direct |
| `inflation_swap_rate(τ)` decimal | `ecb_sdw` (EA), `fred` (US), Bloomberg (UK/JP) | daily | SWAP |
| `ea_aggregate_bei(τ)` decimal | `ecb_sdw` (ECB fitted) | daily | DERIVED |
| US SPF 1Y/2Y/5Y/10Y | `spf_philly` | quarterly | SURVEY |
| US Michigan `MICH`, `MICH5Y` | `fred` | monthly | SURVEY |
| ECB SPF 1Y/2Y/5Y | `ecb_sdw` | quarterly | SURVEY |
| BoE DMP 1Y/3Y | `boe_dmp` | quarterly | SURVEY |
| BoJ Tankan 1Y/3Y/5Y | `boj_tankan` | quarterly | SURVEY |
| IMF WEO CPI 1Y/5Y | `imf_weo` | semi-annual | SURVEY (EM) |
| FocusEconomics 1Y/5Y | `focuseconomics` (CSV, Tier 3 EM) — **Phase 2+ verify ToS** | monthly | SURVEY (EM) |
| `pt_hicp_yoy`, `ea_hicp_yoy` | `eurostat` (`prc_hicp_manr geo=PT/U2`) — INE endpoint broken per D2 CAL-022; proxy `INE_MIRROR_EUROSTAT` applied | monthly | DERIVED (PT diff) |
| BdP *Perspetivas Económicas* | `bdp_bpstat` | quarterly | cross-check only |

### Hierarchy per country-tenor (primary → fallback)

| Country | 1Y/2Y | 5Y/10Y/30Y | 5y5y | Linker connector |
|---|---|---|---|---|
| US | SPF/Michigan → BEI | BEI (`DFII5/10`, `T5YIE/T10YIE/T30YIE`) | BEI-derived (xval `T5YIFR`) | `fred` |
| UK | BoE DMP → ILG BEI | ILG BEI | BEI-derived | `boe_yieldcurves` |
| DE | ECB SPF → ILB BEI | ILB BEI | BEI-derived | `bundesbank` |
| FR | ECB SPF → OATi BEI | OATi BEI | BEI-derived | `aft_france` |
| IT | ECB SPF → BTP€i BEI | BTP€i BEI | BEI-derived | `mef_italy` |
| ES | ECB SPF → BEIi (thin) | BEIi thin → DERIVED | DERIVED | `tesoro_spain` |
| EA | ECB SPF → SWAP | SWAP → EA fitted BEI | SWAP-derived | `ecb_sdw` |
| **PT** | ECB SPF → **DERIVED** | **DERIVED** (EA BEI + PT-EA diff) | DERIVED | — |
| CA / AU | survey → linker BEI | RRB / TIB BEI | BEI-derived | `boc_canada` / `rba` |
| JP | Tankan → SURVEY | SURVEY (BEI thin) | SURVEY-interp | `boj_tankan` |
| BR / MX | survey → linker BEI | NTN-B / UDI BEI | BEI-derived | `bcb_brazil` / `banxico` |
| IN / CN | SURVEY | SURVEY + IMF WEO | n/a | — |
| TR / AR | SURVEY + IMF WEO + Consensus | idem (wide CI) | n/a | — |

### Parameters (config)

- `pt_ea_differential_window_years = 5`, `pt_ea_differential_refresh_months = 3`.
- `irp_haircut_bps = {"5Y":20, "10Y":35, "30Y":50}` — applied only on canonical, never on raw method rows. *Placeholder — recalibrate after 12m of production data.*
- `anchor_bands_bps`: `<20 well_anchored | 20-50 moderately_anchored | 50-100 drifting | >100 unanchored`. *Placeholder — recalibrate after 18m.*
- `survey_freshness_max_days = 120` (quarterly + buffer).
- `min_confidence_nominal = 0.50` (upstream `yield_curves_spot`).

### Preconditions

- BEI path: `yield_curves_spot` row existe com `confidence ≥ 0.50` para mesma `(country, date)`; linker connector ≥ 3 tenors no grid canónico.
- DERIVED path: EA aggregate BEI disponível + PT-EA differential dentro de `pt_ea_differential_refresh_months`; senão flag `CALIBRATION_STALE`.
- SURVEY path: survey row ≤ `survey_freshness_max_days`; senão flag `STALE`.
- `methodology_version` de inputs NSS bate com runtime ou raise `VersionMismatchError`.
- Inputs partilham `date` canonical (business day local) e país ISO α-2 upper.

## 3. Outputs

Per `(country, date)`, até 5 method rows + 1 canonical row, todas partilhando `exp_inf_id` UUID.

| Output | Storage | `methodology_version` | Emitted when |
|---|---|---|---|
| Market breakeven | `exp_inflation_bei` | `EXP_INF_BEI_v0.1` | linker connector + NSS disponíveis |
| Inflation swap | `exp_inflation_swap` | `EXP_INF_SWAP_v0.1` | swap connector disponível |
| Synthesized (regional + diff) | `exp_inflation_derived` | `EXP_INF_DERIVED_v0.1` | EA aggregate + differential OR nominal − survey |
| Survey-based | `exp_inflation_survey` | `EXP_INF_SURVEY_v0.1` | survey connector retorna row fresh |
| Canonical per-tenor selection | `exp_inflation_canonical` | `EXP_INF_CANONICAL_v0.1` | ≥ 1 method row persistido |

Per-method rows armazenam tenor dict `{"1Y": decimal, "2Y": ..., "5Y": ..., "10Y": ..., "30Y": ..., "5y5y": ...}`. Canonical row expõe um `expected_inflation_tenors_json` + `source_method_per_tenor_json` + `anchor_status`.

**Consumers read `exp_inflation_canonical`** (per-tenor best-available via hierarchy). Method rows são auditoria / cross-validation.

## 4. Algorithm

> **Units**: rates em decimal storage/compute (ex: `0.0230`); `_bps` só em deviations (ex: `anchor_deviation_bps`). Regras em [`conventions/units.md`](../conventions/units.md) §Yields, §Spreads.

### Formulas

**BEI (`EXP_INF_BEI_v0.1`)** — `BEI(τ) = nominal_yield(τ) − linker_real_yield(τ)`. Linker real é fetched directly (linker tenors alinhados ao grid via linear interp interno quando diferem; NÃO refit NSS aqui).

**SWAP (`EXP_INF_SWAP_v0.1`)** — leitura directa de zero-coupon inflation swap rate por tenor.

**DERIVED (`EXP_INF_DERIVED_v0.1`)** — Portugal path:

```text
E[π_PT(τ)] = E[π_EA(τ)] + diff_pt_ea_5y_rolling
diff_pt_ea_5y_rolling = mean( pt_hicp_yoy − ea_hicp_yoy, last 60 monthly obs )
```

**SURVEY (`EXP_INF_SURVEY_v0.1`)** — leitura do survey no horizon mais próximo; linear interp para grid tenors quando gap < 3Y; tenor fora de coverage → `NULL`.

**5y5y forward** (compounded, em qualquer method com `5Y` + `10Y`):

```text
5y5y = [ (1 + rate_10Y)^10 / (1 + rate_5Y)^5 ]^(1/5) − 1
```

Forma linear `(10·r10 − 5·r5)/5` do reference é aproximação; NÃO usar em storage.

**Canonical selection per tenor** — `hierarchy_pick(country, tenor, date)` retorna first-available de `[BEI, SWAP, DERIVED, SURVEY, CONSENSUS]` com `row.confidence ≥ 0.50` + freshness OK.

**Anchor**: `anchor_deviation_bps = int(round((value_5y5y − bc_target) · 10_000))`. `bc_target` via `config/bc_targets.yaml` (Fed/ECB/BoE/BoJ/BoC `0.02`, BCB `0.03`, RBI `0.04`, Banxico `0.03`, RBA `0.025` midpoint; CN/TR/AR — no operative target, skip). `anchor_status` = band em `anchor_bands_bps` aplicado a `|anchor_deviation_bps|`, sinal preservado em `anchor_deviation_bps`.

### Pipeline per `(country, date)`

1. Resolve hierarchy da § table; run branches independentemente (não short-circuit — todos emitem para auditoria).
2. **BEI**: se linker disponível → compute `BEI(τ)` para tenors ∈ grid ∩ coverage; derive `5y5y` (compounded); inherit `flags` de `yield_curves_spot`.
3. **SWAP**: se swap connector disponível → fetch direct; derive `5y5y`.
4. **DERIVED** (PT + periphery): fetch `ea_aggregate_bei`; if cached `diff_pt_ea_5y_rolling` age > `pt_ea_differential_refresh_months` → recompute from INE + Eurostat 60-month history; se recompute falha por dados faltosos → use cache + flag `CALIBRATION_STALE`.
5. **SURVEY**: fetch latest survey per horizon; linear-interp to grid tenors (gap < 3Y); wider → tenor = `NULL`.
6. Compute `confidence` per method (§6 matrix) + inherit upstream flags.
7. `exp_inf_id = uuid4()`; persist method rows atomically.
8. **Canonical**: for each tenor ∈ `["1Y","2Y","5Y","10Y","30Y","5y5y"]`, pick first method per hierarchy com `confidence ≥ 0.50`. Store `source_method_per_tenor_json`. `confidence_canonical = weighted_mean(method_confidences, weights=tenor_count_per_method)`. Compute `anchor_deviation_bps` + `anchor_status` se `5y5y` disponível; senão `NULL` + flag `ANCHOR_UNCOMPUTABLE`.
9. Cross-validate: se BEI + SURVEY ambos disponíveis, `bei_vs_survey_divergence_bps = |BEI_10Y − SURVEY_10Y| · 10_000`; `> 100 bps` → flag `INFLATION_METHOD_DIVERGENCE`.
10. Persist canonical row.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | arrays, rolling mean |
| `pandas` | 2.1 | monthly HICP series, rolling window |
| `scipy` | 1.11 | interpolation (linear, shape-preserving) |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network; inputs pre-fetched via connectors upstream.

## 6. Edge cases

Flags → [`conventions/flags.md`](../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../conventions/exceptions.md). Propagação conforme § "Convenção de propagação".

| Trigger | Handling | Confidence |
|---|---|---|
| `yield_curves_spot` missing / `confidence < 0.50` | BEI branch skip; fall down hierarchy | BEI: n/a |
| Linker connector returns < 3 tenors | BEI branch skip; flag `LINKER_UNAVAILABLE` | cap 0.70 on row if emitted partially |
| Swap connector 404 / stale > 5bd | SWAP skip; flag `STALE` se ainda emitted | −0.20 |
| Short-dated BEI (`1Y`, `2Y`) seasonality | sempre flag `BEI_SHORT_SEASONALITY` nesses tenors; canonical prefere SURVEY para `≤2Y` | −0.10 (tenores afetados) |
| PT-EA differential cache age > `pt_ea_differential_refresh_months` + recompute sem dados | use cache; flag `CALIBRATION_STALE` | −0.15 |
| EA aggregate BEI missing | DERIVED branch raise `DataUnavailableError` → fall to SURVEY | DERIVED: n/a |
| Survey row > `survey_freshness_max_days` | emit + flag `STALE` | −0.20 |
| Survey horizon gap > 3Y para tenor pedido | deixar tenor `NULL` na row | (only that tenor skipped) |
| `5Y` ou `10Y` absent → `5y5y` uncomputable | `5y5y = NULL`; flag `ANCHOR_UNCOMPUTABLE` no canonical | −0.10 |
| `|BEI_10Y − SURVEY_10Y| > 100 bps` | flag `INFLATION_METHOD_DIVERGENCE` | canonical −0.10 |
| Country `CN`/`TR`/`AR` (no operative BC target) | skip `anchor_status`; flag `NO_TARGET` | (no impact) |
| Country sem linker + SURVEY path único (JP 5Y+, most T2+ EMs) | emit canonical via SURVEY; flags `BREAKEVEN_PROXY_SURVEY` + `PROXY_APPLIED` per proxies.md entry | −0.10 (per `PROXY_APPLIED` multiplicative) |
| PT HICP source = Eurostat mirror (INE endpoint broken D2) | flag `INE_MIRROR_EUROSTAT` + `PROXY_APPLIED` em DERIVED row | −0.10 |
| Hyperinflation (AR, TR acima 25% YoY) | widen confidence interval; flag `EM_COVERAGE` | cap 0.50 |
| Canonical requires ≥ 1 method row; se 0 | raise `InsufficientDataError` | n/a |
| Stored input `methodology_version` ≠ runtime | raise `VersionMismatchError` | n/a |
| Unknown country ISO | raise `InvalidInputError` | n/a |

## 7. Test fixtures

Stored em `tests/fixtures/expected-inflation/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01_02_bei` | UST 5/10/30Y + DFII5/10/30 | `BEI_5Y≈0.0230`, `BEI_10Y≈0.0242`, `5y5y≈0.0254` (matches `T5YIFR`) | ±10 bps |
| `us_2024_01_02_canonical` | BEI+SPF+Michigan fresh | canonical: BEI 5/10/30Y, SURVEY 1Y/2Y, BEI-derived 5y5y; `anchor_status="moderately_anchored"` | ±10 bps |
| `pt_2024_01_02_derived` | EA BEI 5Y=0.021, 10Y=0.022; PT-EA diff=0.0015 | `E[π_PT] = {5Y:0.0225, 10Y:0.0235}`; `confidence ≤ 0.80` | ±10 bps |
| `pt_differential_recompute` | INE + Eurostat 60-month HICP | `diff_pt_ea_5y_rolling ≈ 0.0018` | ±20 bps |
| `jp_survey_only` | Tankan 1/3/5Y; no BEI, no 10Y | canonical tenors ≤ 5Y SURVEY; `5y5y=NULL`; flag `ANCHOR_UNCOMPUTABLE` | — |
| `ea_5y5y_compounded_vs_linear` | swap 5Y=0.021, 10Y=0.0225 | compounded ≈ linear within 1 bps at these levels (diverge ao high inflation) | ±1 bps |
| `tr_em_wide_ci` | IMF WEO + FocusEconomics 10-20% | `confidence ≤ 0.50`; flags `EM_COVERAGE,NO_TARGET` | — |
| `ar_hyperinflation` | Consensus 45% 1Y, 18% 5Y | row emitted; `anchor_status=NULL`; `EM_COVERAGE` | — |
| `us_method_divergence_2022_q2` | BEI 10Y=0.028, SPF 10Y=0.022 | `bei_vs_survey_divergence_bps=600`; `INFLATION_METHOD_DIVERGENCE` | — |
| `pt_no_ea_bei` | EA aggregate missing | DERIVED raises `DataUnavailableError`; fallback SURVEY (ECB SPF); `OVERLAY_MISS` | — |

## 8. Storage schema

Common preamble inlined em todas as 5 tabelas:

```sql
-- Common preamble (MANDATORY em todas as 5 tabelas):
--   id                    INTEGER PRIMARY KEY AUTOINCREMENT,
--   exp_inf_id            TEXT    NOT NULL,           -- uuid4, shared across sibling rows
--   country_code          TEXT    NOT NULL,           -- ISO α-2 upper, 'EA' permitido
--   date                  DATE    NOT NULL,
--   methodology_version   TEXT    NOT NULL,
--   confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
--   flags                 TEXT,                        -- CSV, ordem lexicográfica
--   source_connector      TEXT,
--   created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--   UNIQUE (country_code, date, methodology_version)
```

```sql
CREATE TABLE exp_inflation_bei (
    /* + common preamble */
    nominal_yields_json       TEXT NOT NULL,            -- {"5Y":0.0415,"10Y":0.0425,...}
    linker_real_yields_json   TEXT NOT NULL,
    bei_tenors_json           TEXT NOT NULL,            -- {"5Y":0.0230,"10Y":0.0242,"5y5y":0.0254}
    linker_connector          TEXT NOT NULL,
    nss_fit_id                TEXT NOT NULL             -- FK to yield_curves_spot.fit_id
);
CREATE INDEX idx_exp_bei_cd ON exp_inflation_bei (country_code, date);

CREATE TABLE exp_inflation_swap (
    /* + common preamble */
    swap_rates_json           TEXT NOT NULL,            -- {"1Y":0.022,"5Y":0.021,"10Y":0.0225,"5y5y":0.0240}
    swap_provider             TEXT NOT NULL             -- 'ECB_SDW' | 'BLOOMBERG' | 'FRED'
);
CREATE INDEX idx_exp_swap_cd ON exp_inflation_swap (country_code, date);

CREATE TABLE exp_inflation_derived (
    /* + common preamble */
    regional_bei_json         TEXT NOT NULL,            -- EA aggregate BEI used
    regional_source           TEXT NOT NULL,            -- 'EA_AGGREGATE'
    differential_pp           REAL NOT NULL,            -- e.g. 0.0015 = 15 bps
    differential_window_years INTEGER NOT NULL,
    differential_computed_at  TIMESTAMP NOT NULL,
    derived_tenors_json       TEXT NOT NULL
);
CREATE INDEX idx_exp_derived_cd ON exp_inflation_derived (country_code, date);

CREATE TABLE exp_inflation_survey (
    /* + common preamble */
    survey_name               TEXT NOT NULL,            -- 'SPF' | 'MICH' | 'ECB_SPF' | 'TANKAN' | 'IMF_WEO' | 'CONSENSUS'
    survey_release_date       DATE NOT NULL,
    horizons_json             TEXT NOT NULL,            -- {"1Y":0.0245,"5Y":0.0230,"10Y":0.0242}
    interpolated_tenors_json  TEXT NOT NULL             -- {"2Y":0.0238,"30Y":null,...}
);
CREATE INDEX idx_exp_survey_cd ON exp_inflation_survey (country_code, date);

CREATE TABLE exp_inflation_canonical (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    exp_inf_id                  TEXT    NOT NULL UNIQUE,
    country_code                TEXT    NOT NULL,
    date                        DATE    NOT NULL,
    methodology_version         TEXT    NOT NULL,      -- 'EXP_INF_CANONICAL_v0.1'
    expected_inflation_tenors_json TEXT NOT NULL,      -- {"1Y":0.0245,"2Y":...,"5Y":...,"10Y":...,"30Y":...,"5y5y":...}
    source_method_per_tenor_json   TEXT NOT NULL,      -- {"1Y":"SURVEY","5Y":"BEI",...}
    methods_available           INTEGER NOT NULL CHECK (methods_available BETWEEN 1 AND 4),
    bc_target_pct               REAL,                   -- NULL para NO_TARGET
    anchor_deviation_bps        INTEGER,                -- NULL se 5y5y uncomputable
    anchor_status               TEXT,                   -- enum: well_anchored|moderately_anchored|drifting|unanchored|NULL
    bei_vs_survey_divergence_bps INTEGER,               -- NULL se ambos não disponíveis
    confidence                  REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                       TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_exp_canonical_cd ON exp_inflation_canonical (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `overlays/nss-curves` | L2 | `expected_inflation_tenors_json` for derived real curve (countries sem linker: PT, JP, most EM) |
| `overlays/crp` | L2 | `5y5y` forward + PT-EA differential para FX-adjusted valuations / PPP forwards |
| `indices/monetary/M3-market-expectations` | L3 | `5y5y` (BC credibility sub-indicator) |
| `indices/monetary/M4-financial-conditions` | L3 | real-rate decomposition |
| `cycles/monetary-msc` | L4 | `anchor_status` → Dilemma overlay (credibility leg) |
| `integration/cost-of-capital` | L6 | PPP-adjusted FX forwards for cross-border DCF |
| `outputs/editorial` | L7 | `anchor_status` shifts, `bei_vs_survey_divergence_bps` spikes → editorial angles |

## 10. Reference

- **Methodology**: [`docs/reference/overlays/expected-inflation.md`](../../reference/overlays/expected-inflation.md) — Manual dos Sub-Modelos Parte V caps 16-17.
- **Data sources**: [`docs/data_sources/monetary.md`](../../data_sources/monetary.md) §§3.3 breakevens/swaps, 5 surveys; [`docs/data_sources/economic.md`](../../data_sources/economic.md) §§3 INE HICP + 6.1 Michigan; [`data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) §7 INE broken + §6 Eurostat HICP fresh.
- **Architecture**: [`specs/conventions/patterns.md`](../conventions/patterns.md) §Pattern 2 (Hierarchy best-of — BEI > SWAP > DERIVED > SURVEY > CONSENSUS); [`adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) (T1 linker countries + T2+ SURVEY path).
- **Proxies**: [`specs/conventions/proxies.md`](../conventions/proxies.md) — `BREAKEVEN_PROXY_SURVEY` (survey + term premium decomposition); `INE_MIRROR_EUROSTAT` (PT HICP via Eurostat mirror).
- **Licensing**: [`governance/LICENSING.md`](../../governance/LICENSING.md) §3 (FRED BEI + ECB SDW swap + Eurostat HICP + survey providers attribution).
- **Papers**:
  - D'Amico S., Kim D., Wei M. (2018), "Tips from TIPS: The Informational Content of Treasury Inflation-Protected Security Prices", *JFQA* 53(1).
  - Gürkaynak R., Sack B., Wright J. (2010), "The TIPS Yield Curve and Inflation Compensation", *AEJ: Macro* 2(1).
  - Haubrich J., Pennacchi G., Ritchken P. (2012), "Inflation Expectations, Real Rates, and Risk Premia", *RFS* 25(5).
  - Ang A., Bekaert G., Wei M. (2007), "Do Macro Variables, Asset Markets, or Surveys Forecast Inflation Better?", *JME* 54(4).
- **Cross-validation**: FRED `T5YIFR` (US 5y5y, daily); ECB SPF `5Y` quarterly; BdP *Perspetivas Económicas* (PT 3Y projections, quarterly).

## 11. Non-requirements

- Does not fit NSS to breakeven curves — `overlays/nss-curves.yield_curves_forwards` faz o `breakeven_forwards_json` job; aqui só tenor-point BEI.
- Does not separate `E[π] + IRP` como stored columns — `irp_haircut_bps` aplicado só em canonical optional; IRP decomposition formal é spec futura `overlays/inflation-risk-premium`.
- Does not emit intraday — daily EOD batch; survey refresh é event-driven pela release date.
- Does not fit real yield curves — `overlays/nss-curves` consome esta spec para derivar real curve via `nominal − E[π]` quando linker inexistente.
- Does not replicate `T5YIFR` — consume-o só como cross-validation; `5y5y` próprio computed via compounded formula sobre `5Y`/`10Y` desta spec.
- Does not cover FX forward derivation — `overlays/crp` + `integration/cost-of-capital` consomem o term structure para PPP.
- Does not make `bc_target_pct` reconfigurável como time series — lookup estático em `config/bc_targets.yaml`; regime change → manual config + MINOR bump.
- Does not substitute BdP/ECB official projections — SONAR é analytical; BdP/ECB são cross-check only.
- Does not pick "best" method per country — todas as method rows expostas; canonical selection é determinística via § Hierarchy, não ML-optimized.
- Does not backfill survey pre-2000 — responsibility de `pipelines/backfill-strategy`.

