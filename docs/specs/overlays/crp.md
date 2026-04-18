# Country Risk Premium — Spec

> Layer L2 · overlay · slug: `crp` · methodology_version: `CRP_CANONICAL_v0.1` (canonical summary); per-method versions em §4.
> Last review: 2026-04-19 (Phase 0 Bloco E1)

## 1. Purpose

Compute daily Country Risk Premium em **bps** para 30+ sovereigns via hierarquia Damodaran `CRP = default_spread × (σ_equity / σ_bond)`. `default_spread` tem três fontes ordenadas: **CDS 5Y** (primary quando líquido), **sovereign bond spread** vs risk-free benchmark (fallback DM / local-currency EM), **rating-implied** via `overlays/rating-spread` (final fallback). Canonical é o método **best-available per hierarquia** (não média/mediana). Primitivo para `integration/cost-of-capital` (`cost_of_equity_country = risk_free + β·ERP_mature + CRP_country`) e editorial Portugal (2012 ~1500 bps → 2026 ~54 bps).

## 2. Inputs

### Risk-free benchmark (from `overlays/nss-curves.yield_curves_spot`)

| Target market | Benchmark | NSS query |
|---|---|---|
| EUR-denominated (DE, FR, IT, ES, PT, IE, NL, GR, BE, AT, FI) | Bund 10Y | `country=DE` · tenor `10Y` |
| USD-denominated / USD-dominated EM (BR, MX, TR, ZA, CO, ID, …) | UST 10Y | `country=US` · tenor `10Y` |
| GBP (UK) | Gilt 10Y | `country=UK` · tenor `10Y` |
| JPY (JP) | JGB 10Y | `country=JP` · tenor `10Y` |
| Local-currency-only (IN, CN, local-ccy EM) | case-by-case (local CB benchmark); flag `LOCAL_CCY_SPREAD` | per country map |

Benchmark country is its own 0-bps anchor (DE CRP = 0; US CRP = 0 for USD-denominated world view).

### Default-spread + vol-ratio inputs

| Input | Method | Type | Source |
|---|---|---|---|
| `cds_5y_bps` | CDS | `int` | `connectors/wgb` (WGB scrape, 5Y USD CR14/CR07; ~45 countries) |
| `cds_liquidity_class` | CDS | `Literal` | derived from bid-ask + staleness: `"liquid"` \| `"moderate"` \| `"thin"` |
| `sov_yield_country_pct` | SOV_SPREAD | `float` | `overlays/nss-curves` OR `connectors/te`/`wgb` bond scrape (10Y primary, 5Y fallback) |
| `sov_yield_benchmark_pct` | SOV_SPREAD | `float` | `yield_curves_spot` benchmark row (same tenor) |
| `consolidated_sonar_notch` | RATING | `float` | `overlays/rating-spread.ratings_consolidated (country, date, rating_type='FC')` |
| `default_spread_bps` | RATING | `int` | `overlays/rating-spread.ratings_spread_calibration (sonar_notch_int, calibration_date)` |
| `equity_returns_daily` | vol | `pd.Series` | `connectors/twelvedata` (PSI-20, IBEX, FTSE MIB, BOVESPA, …); 5Y rolling, ≥ 750 obs. **Phase 2+ verify ToS** — twelvedata tier/licensing não validado em D-block. |
| `bond_returns_daily` | vol | `pd.Series` | `connectors/te` / `yfinance` sovereign long-bond price series; 5Y rolling, ≥ 750 obs. **Phase 2+ verify** — yfinance scrape estability não validado em D-block. |
| `damodaran_standard_ratio` | vol fallback | `float` | `config/crp.yaml` (default `1.5`) |

### Parameters (config)

- `cds_liquidity_threshold_bps = 15` (bid-ask ≤ 15 bps → `"liquid"`); *placeholder — recalibrate after 12m of production data*.
- `cds_staleness_max_bd = 2` (business days; stale → `"thin"`).
- `vol_ratio_bounds = (1.2, 2.5)`; fora deste range → usar Damodaran `1.5`; *placeholder — recalibrate after 18m*.
- `vol_ratio_min_obs = 750` (≈3Y daily); `vol_ratio_window_years = 5`.
- `rating_cds_divergence_threshold_pct = 50` (|cds − rating_implied| / cds > 0.50 → `RATING_CDS_DIVERGE`); *placeholder — recalibrate after 18m*.
- `basis_alert_threshold_bps = 50` (|bond_spread − cds| > 50 → `CRP_BOND_CDS_BASIS`).
- `min_methods_for_canonical = 1` (hierarchy best-of; qualquer método bastando).

### Preconditions

Invariantes antes da invocação:

- `overlays/nss-curves.yield_curves_spot` row existe para benchmark (`DE`/`US`/`UK`/`JP`) no mesmo `date` com `confidence ≥ 0.50`; senão raise `InsufficientDataError`.
- Para método CDS: `connectors/wgb` `fetched_at` ≤ `cds_staleness_max_bd` business days; senão emit com `STALE` ou drop para SOV_SPREAD.
- Para método SOV_SPREAD: sovereign bond yield + benchmark yield partilham `date` business day local e tenor (10Y canonical).
- Para método RATING: `ratings_consolidated` row existe com `(country, date, rating_type='FC', methodology_version)` e `default_spread_bps IS NOT NULL`; `ratings_spread_calibration` row existe para `(sonar_notch_int, calibration_date ≤ date)` com `staleness_days ≤ 90`.
- Country code ISO α-2 upper; pertence ao universo de 30+ countries em `config/crp_coverage.yaml`.
- `methodology_version` dos inputs upstream bate com runtime ou raise `VersionMismatchError`.
- Pelo menos 1 método produz `default_spread_bps` finito; senão raise `InsufficientDataError` (no canonical persist).

## 3. Outputs

Per `(country, date)`, até 3 method rows + 1 canonical row, todas partilhando `crp_id` UUID.

| Output | Storage | `methodology_version` | Emitted when |
|---|---|---|---|
| CDS-based CRP | `crp_cds` | `CRP_CDS_v0.1` | CDS connector retorna finite 5Y e liquidity ≠ `"thin"` |
| Sovereign-spread CRP | `crp_sov_spread` | `CRP_SOV_SPREAD_v0.1` | Country + benchmark yields disponíveis same tenor |
| Rating-implied CRP | `crp_rating` | `CRP_RATING_v0.1` | `ratings_consolidated` + calibration lookup ambos disponíveis |
| Canonical summary | `crp_canonical` | `CRP_CANONICAL_v0.1` | ≥ 1 method row persistido |

**Downstream consumers read `crp_canonical.crp_canonical_bps`**. Method tables expõem todos os 3 valores lado-a-lado para audit + editorial triangulation.

**Canonical JSON shape**:

```json
{"crp_id":"7a1f...","country":"PT","date":"2026-04-17",
 "crp_cds_bps":54,"crp_sov_spread_bps":108,"crp_rating_bps":90,
 "crp_canonical_bps":54,"method_selected":"CDS",
 "default_spread_bps":35,"vol_ratio":1.54,"vol_ratio_source":"country_specific",
 "basis_bond_minus_cds_bps":35,"confidence":0.85,"flags":""}
```

## 4. Algorithm

> **Units**: `default_spread_bps`, `crp_*_bps`, `basis_*_bps` armazenados como `INTEGER` bps; `vol_ratio`, yields, and volatilidades em `REAL` decimal (ex: `0.182` = 18.2%). Conversão `bps = int(round(decimal × 10_000))` aplicada no ponto de persistência. Full rules em [`conventions/units.md`](../conventions/units.md) §Spreads.

### Formulas

```text
CRP_method_bps = int(round(default_spread_method_bps × vol_ratio))          # Damodaran core identity
vol_ratio      = σ_equity_5y / σ_bond_5y      if obs ≥ 750 AND ratio ∈ [1.2, 2.5]
               | damodaran_standard_ratio     otherwise (1.5)
σ_x_5y         = std(daily_returns_x) · sqrt(252)                           # annualized, 5Y rolling

# Default spread per method:
CDS        (CRP_CDS_v0.1)         default_spread_cds_bps    = cds_5y_bps(country)              # absolute, Damodaran §10.9
SOV_SPREAD (CRP_SOV_SPREAD_v0.1)  default_spread_sov_bps    = int(round((y_country − y_benchmark) · 10_000))
                                                              # clamp < 0 → 0 + CRP_NEG_SPREAD
RATING     (CRP_RATING_v0.1)      notch_int                 = int(round(consolidated_sonar_notch))
                                  default_spread_rating_bps = ratings_spread_calibration(notch_int, calibration_date ≤ date).default_spread_bps
                                                              # fractional notch → linear interp (notch_int, notch_int+1)

# Canonical selection (hierarchy best-of, NOT median/mean):
method_selected = first_available([CDS, SOV_SPREAD, RATING])
  where available ≡ confidence ≥ 0.50 AND default_spread_bps IS NOT NULL AND (method ≠ CDS OR liquidity ≠ "thin")
crp_canonical_bps = crp_{method_selected}_bps
```

Benchmark countries (DE, US) → `default_spread = 0` shortcut, flag `CRP_BENCHMARK`.

**Rationale (hierarchy vs median)**: reference §10.2 e decision tree §11.10 prescrevem hierarchy (CDS primary when liquid; bond fallback; rating final). Median mixing across methods contaminaria CDS of high quality com rating estimate noisy — oposto da hierarquia intencional. Todos os method values persistidos para transparência + editorial triangulation.

### Pipeline per `(country, date)`

1. Resolve benchmark per §2; fetch `risk_free_pct` from `yield_curves_spot` (raise `InsufficientDataError` if `confidence < 0.50`).
2. **Vol ratio**: fetch 5Y daily equity + bond returns; `σ_x = std · sqrt(252)`; `vol_ratio = σ_eq / σ_bond`. If `obs < 750` OR `vol_ratio ∉ [1.2, 2.5]` OR fetch fails → fallback to `damodaran_standard_ratio = 1.5`, `vol_ratio_source="damodaran_standard"`, flag `CRP_VOL_STANDARD`; else `"country_specific"`.
3. **CDS branch**: fetch `cds_5y_bps` via `connectors/wgb`; classify liquidity (bid-ask + staleness). If `"thin"` → skip; else `crp_cds_bps = int(round(cds_5y_bps × vol_ratio))`; persist `crp_cds`.
4. **SOV_SPREAD branch**: fetch country 10Y (NSS preferred, else connector) + benchmark 10Y. `default_spread_sov_bps = int(round((y_c − y_b) × 10_000))`; clamp `< 0` to 0 + `CRP_NEG_SPREAD`. `crp_sov_spread_bps = default_spread_sov_bps × vol_ratio`; persist `crp_sov_spread`.
5. **RATING branch**: lookup `ratings_consolidated (country, date, 'FC')` → `consolidated_sonar_notch`; if missing → `OVERLAY_MISS`, skip. Else resolve `default_spread_rating_bps` via `ratings_spread_calibration (notch_int, calibration_date ≤ date)`; `crp_rating_bps = default_spread_rating_bps × vol_ratio`; persist `crp_rating`.
6. **Cross-checks** (when both siblings present): `basis_bond_minus_cds_bps = default_spread_sov_bps − cds_5y_bps` → `|basis| > 50` flag `CRP_BOND_CDS_BASIS`; `|cds − rating_implied|/cds > 0.50` flag `RATING_CDS_DIVERGE` (reemit, owned by `rating-spread`).
7. `crp_id = uuid4()`; persist all method rows atomically (shared `crp_id`).
8. **Canonical**: apply §Canonical selection; if zero methods available → raise `InsufficientDataError`. `confidence_canonical = confidence(method_selected) + flag penalties` clamped `[0,1]`; persist `crp_canonical`.
9. **Benchmark countries** (DE for EUR, US for USD): shortcut — `default_spread = 0`, `crp_canonical_bps = 0`, `method_selected = "BENCHMARK"`, `confidence = 1.0`, flag `CRP_BENCHMARK`.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | rolling std, array ops |
| `pandas` | 2.1 | 5Y rolling windows, returns |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network inside the algorithm — CDS/bond/equity series pre-fetched by connectors (`wgb`, `te`, `twelvedata`, `yfinance`).

## 6. Edge cases

Flags → [`conventions/flags.md`](../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../conventions/exceptions.md). Propagação conforme § "Convenção de propagação" (aditivo, clamp `[0,1]`).

| Trigger | Handling | Confidence |
|---|---|---|
| Benchmark NSS row missing / `confidence < 0.50` | raise `InsufficientDataError` | n/a |
| CDS `cds_liquidity_class == "thin"` | skip CDS branch; fallback SOV_SPREAD | (branch skipped) |
| CDS connector stale > `cds_staleness_max_bd` | emit com `STALE` OR skip per threshold | −0.20 if emitted |
| CDS connector 404 (WGB down) | raise `DataUnavailableError` → skip CDS; flag `OVERLAY_MISS` | (branch skipped) |
| SOV_SPREAD: negative spread (arbitrage noise) | clamp to 0; flag `CRP_NEG_SPREAD` | −0.10 |
| SOV_SPREAD: tenor mismatch (country 10Y vs benchmark 5Y) | raise `InvalidInputError` | n/a |
| SOV_SPREAD: local-currency-only country (IN, CN) | use local-CB benchmark; flag `LOCAL_CCY_SPREAD` | −0.15 |
| RATING: `ratings_consolidated` row missing | skip RATING branch; flag `OVERLAY_MISS` | (branch skipped) |
| RATING: `ratings_spread_calibration` `staleness_days > 90` | emit; flag `CALIBRATION_STALE` | −0.15 |
| RATING: `notch_int ∉ [0,21]` | raise `CalibrationError` | n/a |
| RATING: `notch == 0` (D/SD) | inherit `RATING_DEFAULT`; cap per rating-spread rules | cap 0.40 |
| `vol_ratio` inputs < 750 obs | `vol_ratio = 1.5`; flag `CRP_VOL_STANDARD` | −0.05 |
| `vol_ratio ∉ [1.2, 2.5]` | clamp to 1.5; flag `CRP_VOL_STANDARD` | −0.05 |
| `|bond_spread − cds| > basis_alert_threshold_bps` | flag `CRP_BOND_CDS_BASIS` | canonical: −0.05 |
| `|cds − rating_implied| / cds > 0.50` | reemit `RATING_CDS_DIVERGE` (owner: rating-spread) | canonical: −0.10 |
| Stressed EM (AR, TR, EG) | widen ranges; flag `EM_COVERAGE` | cap 0.70 |
| Argentina-class distressed (CDS > 1500 bps) | emit; flag `CRP_DISTRESS`; CI wide | cap 0.60 |
| Benchmark country (DE, US) | emit `crp = 0`; flag `CRP_BENCHMARK` | 1.0 |
| Zero methods available | raise `InsufficientDataError`; no canonical persist | n/a |
| Stored input `methodology_version` ≠ runtime | raise `VersionMismatchError` | n/a |
| Unknown country (fora de `config/crp_coverage.yaml`) | raise `InvalidInputError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/crp/`. Each `input_<id>.json` + `expected_<id>.json`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `pt_2026_04_17_cds` | PT CDS 35; PSI-20 + PT 10Y vol; Bund 10Y = 2.45% | `vol_ratio≈1.54`, `crp_cds≈54`, `crp_sov_spread≈108` (70 × 1.54), `crp_rating≈90`; canonical=CDS(54); `basis≈35` | ±5 bps |
| `de_benchmark_2026_04_17` | DE inputs | `crp_canonical_bps=0`, `method_selected="BENCHMARK"` | 0 bps |
| `it_2026_04_17_cds` | IT CDS 68; FTSE MIB + IT 10Y | `crp_cds≈100`, `crp_sov_spread≈204` (140 × 1.46); `CRP_BOND_CDS_BASIS` | ±10 bps |
| `br_2026_04_17_em` | BR USD 10Y=7.25%; UST 4.15%; CDS 180; BOVESPA vol | `crp_cds≈300` (180 × 1.67); canonical=CDS | ±15 bps |
| `tr_2026_04_17_stressed` | TR CDS 280 thin (bid-ask 25); BIST+bond | CDS skipped; canonical=SOV_SPREAD; `EM_COVERAGE`+`CRP_DISTRESS` | ±20 bps |
| `ar_2026_04_17_distressed` | AR CDS 1850; bond < CDS (inverted) | `crp_cds≈2960`; `CRP_BOND_CDS_BASIS`; confidence ≤ 0.60 | ±50 bps |
| `gh_rating_only` | Ghana: no CDS, no bond; notch=6 | canonical=RATING; `crp_rating ≈ 1325 × 1.5 = 1988`; `OVERLAY_MISS` (CDS+SOV) | ±100 bps |
| `pt_2012_peak_synth` | PT CDS 1800; vol_ratio 1.4 | `crp_cds ≈ 2520`; `CRP_DISTRESS` | ±50 bps |
| `pt_vol_insufficient` | PT inputs, 500d equity returns | `vol_ratio=1.5` fallback; `CRP_VOL_STANDARD` | — |
| `pt_rating_cds_diverge` | PT CDS 35; rating_implied 90 | divergence 157%; `RATING_CDS_DIVERGE` | — |
| `in_local_ccy_only` | IN: no USD sovereign; local yield only | SOV_SPREAD via local-CB benchmark; `LOCAL_CCY_SPREAD` | — |
| `all_methods_missing` | No CDS, no bond, no rating | raises `InsufficientDataError` | n/a |

## 8. Storage schema

4 tables. `crp_cds` + `crp_sov_spread` + `crp_rating` + `crp_canonical` partilham `crp_id` UUID (correlation across sibling rows para mesmo `(country, date)`).

```sql
-- Common preamble (MANDATORY em todas as 4 tabelas):
--   id                    INTEGER PRIMARY KEY AUTOINCREMENT,
--   crp_id                TEXT    NOT NULL,           -- uuid4, shared across sibling rows
--   country_code          TEXT    NOT NULL,           -- ISO α-2 upper
--   date                  DATE    NOT NULL,
--   methodology_version   TEXT    NOT NULL,
--   benchmark_country     TEXT    NOT NULL,           -- 'DE' | 'US' | 'UK' | 'JP' | 'LOCAL'
--   risk_free_pct         REAL    NOT NULL,           -- from NSS (decimal)
--   vol_ratio             REAL    NOT NULL,
--   vol_ratio_source      TEXT    NOT NULL CHECK (vol_ratio_source IN ('country_specific','damodaran_standard')),
--   confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
--   flags                 TEXT,
--   source_connector      TEXT,
--   created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--   UNIQUE (country_code, date, methodology_version)
```

```sql
CREATE TABLE crp_cds (
    /* + common preamble */
    cds_5y_bps                INTEGER NOT NULL,
    cds_liquidity_class       TEXT    NOT NULL CHECK (cds_liquidity_class IN ('liquid','moderate','thin')),
    cds_bid_ask_bps           INTEGER,
    cds_source                TEXT    NOT NULL,        -- 'WGB' | 'BLOOMBERG' | 'MARKIT'
    default_spread_bps        INTEGER NOT NULL,        -- == cds_5y_bps (absolute convention)
    crp_bps                   INTEGER NOT NULL
);
CREATE INDEX idx_crp_cds_cd ON crp_cds (country_code, date);

CREATE TABLE crp_sov_spread (
    /* + common preamble */
    sov_yield_country_pct     REAL    NOT NULL,
    sov_yield_benchmark_pct   REAL    NOT NULL,
    tenor                     TEXT    NOT NULL,        -- canonical '10Y'
    default_spread_bps        INTEGER NOT NULL,        -- clamped ≥ 0
    crp_bps                   INTEGER NOT NULL,
    currency_denomination     TEXT    NOT NULL         -- 'EUR' | 'USD' | 'GBP' | 'JPY' | 'LOCAL'
);
CREATE INDEX idx_crp_sov_cd ON crp_sov_spread (country_code, date);

CREATE TABLE crp_rating (
    /* + common preamble */
    consolidated_sonar_notch  REAL    NOT NULL CHECK (consolidated_sonar_notch BETWEEN 0 AND 21),
    notch_int                 INTEGER NOT NULL,
    calibration_date          DATE    NOT NULL,
    default_spread_bps        INTEGER NOT NULL,        -- from ratings_spread_calibration
    crp_bps                   INTEGER NOT NULL,
    rating_id                 TEXT    NOT NULL          -- FK to ratings_consolidated.rating_id
);
CREATE INDEX idx_crp_rating_cd ON crp_rating (country_code, date);

CREATE TABLE crp_canonical (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    crp_id                      TEXT    NOT NULL UNIQUE,
    country_code                TEXT    NOT NULL,
    date                        DATE    NOT NULL,
    methodology_version         TEXT    NOT NULL,      -- 'CRP_CANONICAL_v0.1'
    method_selected             TEXT    NOT NULL CHECK (method_selected IN ('CDS','SOV_SPREAD','RATING','BENCHMARK')),
    crp_cds_bps                 INTEGER,                -- NULL se CDS branch indisponível
    crp_sov_spread_bps          INTEGER,
    crp_rating_bps              INTEGER,
    crp_canonical_bps           INTEGER NOT NULL,       -- = crp_{method_selected}_bps
    default_spread_bps          INTEGER NOT NULL,       -- selected method default spread
    vol_ratio                   REAL    NOT NULL,
    vol_ratio_source            TEXT    NOT NULL,
    basis_bond_minus_cds_bps    INTEGER,                -- NULL se ambos branches não disponíveis
    rating_cds_deviation_pct    REAL,                   -- NULL se ambos branches não disponíveis
    methods_available           INTEGER NOT NULL CHECK (methods_available BETWEEN 0 AND 3),
    confidence                  REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                       TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_crp_canonical_cd ON crp_canonical (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `integration/cost-of-capital` | L6 | **primary**: `crp_canonical_bps` per country; `cost_of_equity = risk_free + β·ERP_mature + CRP` |
| `indices/credit/L2-credit-to-gdp-gap` | L3 | `crp_canonical_bps` periphery signal (EA fragmentation) |
| `indices/credit/L5-sovereign-risk` | L3 | `crp_canonical_bps` delta vs 5Y history (sovereign stress factor) |
| `cycles/credit-cccs` | L4 | sovereign-credit component; `basis_bond_minus_cds_bps` as stability signal |
| `integration/diagnostics/rating-vs-market` | L6 | `rating_cds_deviation_pct` editorial divergence angle |
| `outputs/editorial` | L7 | direct citation; Portugal trajectory 2007→2012→2026 (20→1500→54 bps); cross-country comparisons |

## 10. Reference

- **Methodology**: [`docs/reference/overlays/crp.md`](../../reference/overlays/crp.md) — Manual dos Sub-Modelos Parte IV, caps 10-12.
- **Data sources**: [`docs/data_sources/credit.md`](../../data_sources/credit.md) §§ CDS scrape WGB + spreads; [`docs/data_sources/financial.md`](../../data_sources/financial.md) § equity/bond volatility; [`data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) (twelvedata/yfinance não testados).
- **Architecture**: [`specs/conventions/patterns.md`](../conventions/patterns.md) §Pattern 2 (Hierarchy best-of — CDS > SOV_SPREAD > RATING); [`adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) (CRP applicable T1-T4; T4 é CRP+rating-spread only per ADR-0005 §Decision).
- **Licensing**: [`governance/LICENSING.md`](../../governance/LICENSING.md) §3 attribution + §4 use case matrix (agency ratings, WGB scrape, CDS sources); Override 3 (agency factual cite + paraphrase rationale).
- **Proxies**: [`specs/conventions/proxies.md`](../conventions/proxies.md) — CDS rating-implied fallback registrado; vol_ratio Damodaran standard placeholder.
- **Upstream specs**: [`overlays/nss-curves`](nss-curves.md) (risk-free), [`overlays/rating-spread`](rating-spread.md) (§3 `ratings_consolidated` + §8 `ratings_spread_calibration`).
- **Papers**:
  - Damodaran A. (2024), "Country Risk: Determinants, Measures and Implications", NYU Stern (annual update).
  - Bekaert G., Harvey C. (2014), "Political Risk Spreads", *J. Int. Business Studies* 45(4).
  - Andrade S. (2009), "A Model of Asset Pricing Under Country Risk", *J. Int. Money & Finance* 28(4).
  - Borri N., Verdelhan A. (2011), "Sovereign Risk Premia", AFA Meetings.
- **Cross-validation**: Damodaran annual country risk table (cross-check yearly, target <50 bps dev for major markets); ECB TPI eligibility list (EA periphery sanity).

## 11. Non-requirements

- Does not compute `cost_of_equity` — lives em [`integration/cost-of-capital`](../integration/) (`k_e = R_f + β·ERP + CRP`); CRP output is only that last term.
- Does not emit ERP nor raw rating → spread mapping — delegated to [`overlays/erp-daily`](erp-daily.md) e [`overlays/rating-spread`](rating-spread.md) (§3 `ratings_consolidated`, §8 `ratings_spread_calibration`); CRP consumes them read-only.
- Does not compute PD / recovery nor lambda-adjusted / implied / Ibbotson CRP — audit-only references; v2 é forward CDS/bond/rating framework with flat CRP (Damodaran §10.1).
- Does not decompose FX currency-risk premium — `LOCAL_CCY_SPREAD` flags contamination; separation lives em [`overlays/expected-inflation`](expected-inflation.md) (PPP) + `integration/cost-of-capital`.
- Does not publish regional aggregates (EA periphery avg, LatAm avg) — computed consumer-side ou em `outputs/editorial`; raw per-country only here.
- Does not emit intraday — daily EOD batch; CDS scrape é end-of-day.
- Does not backfill pre-2005 (CDS market pre-maturity) — responsibility de `pipelines/backfill-strategy`; Portugal pre-2007 usa bond-spread proxy, marked `BACKFILLED`.
- Does not predict rating changes nor CDS spikes — reactive only; forecast em `integration/diagnostics/rating-pressure`.
- Does not enforce beta/lambda sector scaling — flat CRP per Damodaran §10.1; users apply externally.

