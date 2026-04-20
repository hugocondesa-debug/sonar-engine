# ERP Daily — Spec

> Layer L2 · overlay · slug: `erp-daily` · methodology_version: `ERP_CANONICAL_v0.1` (canonical summary); per-method versions em §4.
> Last review: 2026-04-19 (Phase 0 Bloco E1)

## 1. Purpose

Compute daily Equity Risk Premium para **4 mature markets** (US S&P 500, EA STOXX 600, UK FTSE All-Share, JP TOPIX) via **4 independent methods** (DCF, Gordon, Earnings Yield, CAPE). Canonical output é **median dos 4 methods** em bps; `erp_range_bps` exposto como sinal de incerteza. Damodaran monthly é cross-validation (não input).

## 2. Inputs

### Risk-free (from `overlays/nss-curves`)

| Market | Risk-free | NSS query (nominal) | NSS query (real, CAPE only) |
|---|---|---|---|
| US | UST 10Y | `yield_curves_spot` · `country=US` · tenor `10Y` | `yield_curves_real` · `country=US` · tenor `10Y` |
| EA | Bund 10Y | `yield_curves_spot` · `country=DE` · tenor `10Y` | `yield_curves_real` · `country=DE` · tenor `10Y` |
| UK | Gilt 10Y | `yield_curves_spot` · `country=UK` · tenor `10Y` | `yield_curves_real` · `country=UK` · tenor `10Y` |
| JP | JGB 10Y | `yield_curves_spot` · `country=JP` · tenor `10Y` | derived (no linker — `nominal − E[π]` via `overlays/expected-inflation`) |

### Market data per index

| Input | Type | Source connector | Used by |
|---|---|---|---|
| `index_level` | `float` (EOD close) | FRED `SP500` (US); TE `/markets/historical/{SXXP,FTAS,TPX}:IND` (EA/UK/JP) per Pattern 4 | DCF, EY, CAPE |
| `trailing_earnings` | `float` | `shiller` (US); `factset_insight` (PDF, others) | CAPE denom, EY anchor |
| `forward_earnings_est` | `float` | `factset_insight` (primary, weekly PDF) + `yardeni` (secondary, weekly Earnings Squiggles PDF, explicit consent per P2-028) | DCF, EY; dual source enables cross-validation divergence flag |
| `dividend_yield_pct` | `float` decimal | `multpl` (US); index-provider (EA/UK/JP) | Gordon |
| `buyback_yield_pct` | `float` decimal | `spdji_buyback` (US quarterly); `NULL` others | Gordon |
| `cape_ratio` | `float` | computed from `shiller ie_data` (US); synthesized others | CAPE |

> **Connector validation pending Week 3 (CAL-036)**: TE `/markets/historical/*:IND` endpoints not empirically validated for daily EOD reuse. Fallback: skip EA/UK/JP ERP if TE unavailable; US ships independently via FRED `SP500`.

### Parameters (config)

- `growth_horizon_years` = 5 (DCF projection)
- `terminal_growth` = `risk_free_nominal` (DCF anchor)
- `g_sustainable_cap` = 0.06 (Gordon ceiling)
- `min_methods_for_canonical` = 2
- `divergence_threshold_bps` = 400 (triggers `ERP_METHOD_DIVERGENCE`)

### Preconditions

- All 4 NSS risk-free lookups retornam `confidence ≥ 0.50` ou raise `InsufficientDataError`.
- `index_level` ≤ 1 business day stale.
- `cape_ratio` até 30 dias stale aceitável (Shiller releases monthly); > 30 dias → flag `STALE`.
- ≥ 2 dos 4 method-specific inputs disponíveis; senão raise `InsufficientDataError`.
- `methodology_version` of upstream `yield_curves_spot/real` matches major version of runtime (e.g. `NSS_v0.*` compatible within major). Minor version mismatch emits `UPSTREAM_VERSION_DRIFT` flag (−0.05 confidence) but proceeds. Major version mismatch raises `VersionMismatchError`.

## 3. Outputs

5 rows per `(market_index, date)` partilhando `erp_id` UUID:

| Output | Storage | `methodology_version` |
|---|---|---|
| DCF ERP | `erp_dcf` | `ERP_DCF_v0.1` |
| Gordon ERP | `erp_gordon` | `ERP_GORDON_v0.1` |
| Earnings-Yield ERP | `erp_ey` | `ERP_EY_v0.1` |
| CAPE-based ERP | `erp_cape` | `ERP_CAPE_v0.1` |
| Canonical summary | `erp_canonical` | `ERP_CANONICAL_v0.1` |

**Consumers read `erp_canonical.erp_median_bps`**. Method tables são diagnostic / auditoria.

## 4. Algorithm

> Units: all ERP values stored as `erp_bps` INTEGER across per-method and canonical tables, per conventions/units.md §Spreads. Compute in decimal internally; convert at persistence boundary via `int(round(decimal × 10_000))`.

### Formulas

**DCF (`ERP_DCF_v0.1`)** — Damodaran 5Y projection + terminal:

```text
Solve r in:
  P = Σ[t=1..5] (E_0 · (1+g)^t · payout) / (1+r)^t
    +            (E_0 · (1+g)^5 · (1+g_T) · payout) / ((r − g_T) · (1+r)^5)
where
  g   = analyst consensus EPS growth 5Y (FactSet)
  g_T = risk_free_nominal                    (terminal growth anchor)
  payout = dividend_yield + buyback_yield    (fallback: 1 − retention)
ERP_DCF = r − risk_free_nominal
```

Root-find via `scipy.optimize.newton`, `x0 = risk_free + 0.05`, bounded `[0, 0.30]`.

**Gordon (`ERP_GORDON_v0.1`)**:

```text
ERP_Gordon = (dividend_yield + buyback_yield) + g_sustainable − risk_free_nominal
g_sustainable = min(retention · ROE, g_sustainable_cap)
```

**Earnings Yield (`ERP_EY_v0.1`)**:

```text
ERP_EY = (forward_earnings / index_level) − risk_free_nominal
```

**CAPE (`ERP_CAPE_v0.1`)** — real-yield anchored:

```text
CAPE      = index_level / mean(real_earnings, last 10Y)
ERP_CAPE  = (1 / CAPE) − real_risk_free
```

### Pipeline per `(market, date)`

1. Lookup risk-free from `yield_curves_spot` (nominal) + `yield_curves_real` (CAPE only). If `confidence < 0.50`, raise `InsufficientDataError`.
2. Fetch market inputs via connectors; validate freshness.
3. Compute cada method independently. Catch `ConvergenceError` (DCF Newton) → skip method; flag `NSS_FAIL`.
4. `erp_id = uuid4()`; persist per-method rows atomically.
5. Build canonical:
   - `erp_*_bps = int(round(erp_*_pct · 10_000))` para cada método disponível.
   - `erp_median_bps = median(available_bps)`.
   - `erp_range_bps = max(available_bps) − min(available_bps)`.
   - `methods_available = count(available)`.
   - `confidence_canonical = min(method_confidences)`, capped by floor; then deduct `0.05 × (4 − methods_available)` per missing method (aligns with flags.md propagation: cap-then-deduct, additive). Clamp `[0, 1]`.
6. Se `methods_available < min_methods_for_canonical` → não persiste canonical; log CRITICAL.
7. Se `erp_range_bps > divergence_threshold_bps` → flag `ERP_METHOD_DIVERGENCE`.
8. Se `histimpl.xlsx` tem row para `date.month`: compute `xval_deviation_bps = |erp_dcf_bps − damodaran_us_erp_bps|` (US only); flag `XVAL_DRIFT` se `> 20 bps`.

   > **Note**: Damodaran cross-validation applies to US market only. EA/UK/JP rows have `xval_deviation_bps = NULL`.

8.5. **Cross-source forward-earnings divergence** (US only, Week 3.5+): when both FactSet and Yardeni forward EPS estimates are fresh (≤ 7 days), compute `forward_eps_divergence_pct = |factset_eps − yardeni_eps| / mean(factset_eps, yardeni_eps)`. Emit flag `ERP_SOURCE_DIVERGENCE` when `> 5%`. Does not affect canonical ERP computation (use FactSet primary); editorial signal only.

9. Persist canonical row.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | arrays, `median` |
| `scipy` | 1.11 | `optimize.newton` (DCF) |
| `pandas` | 2.1 | timeseries i/o |
| `openpyxl` | 3.1 | Shiller `ie_data.xls`, Damodaran `histimpl.xlsx` |
| `pdfplumber` | 0.11 | FactSet Earnings Insight PDF scrape |
| `sqlalchemy` | 2.0 | persistence |

## 6. Edge cases

Flags → [`conventions/flags.md`](../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| Risk-free NSS missing / `confidence < 0.50` | raise `InsufficientDataError` | n/a |
| DCF Newton não convergiu | catch `ConvergenceError`; skip DCF; flag `NSS_FAIL` (reemit) | method: cap 0.50 |
| FactSet PDF scrape falha | raise `DataUnavailableError` → skip DCF + EY; flag `OVERLAY_MISS` | canonical: −0.20 |
| Shiller `ie_data` > 30 dias | flag `STALE`; compute CAPE anyway | −0.20 |
| Buyback > 1 quarter stale | Gordon uses dividend-only; flag `STALE` no Gordon row | −0.20 |
| `erp_range_bps > 400` | flag `ERP_METHOD_DIVERGENCE` | canonical: −0.10 |
| `|erp_dcf_bps − damodaran_bps| > 20` (when xval disponível) | flag `XVAL_DRIFT` | −0.10 |
| `methods_available < 2` | não persistir canonical; persistir method rows disponíveis | n/a |
| Stored `yield_curves_spot.methodology_version ≠` runtime | raise `VersionMismatchError` | n/a |
| `FACTSET_URL` / `SPDJI_KEY` ausente no `.env` | raise `MissingSecretError` at startup | n/a |
| `histimpl.xlsx` connector unavailable OR date.month not in file | `xval_deviation_bps = NULL`; no `XVAL_DRIFT` flag emitted | no impact |
| `forward_eps_divergence_pct > 5%` (FactSet vs Yardeni, US only) | flag `ERP_SOURCE_DIVERGENCE`; no confidence impact; editorial signal | 0 |
| Market slug unknown (ex: `"SPX500"` typo) | raise `UnknownConnectorError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/erp-daily/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01_02` | SPX=4742.83; UST10Y=0.0415; FactSet+Shiller+buyback fixtures | `dcf_bps≈482`, `gordon_bps≈461`, `ey_bps≈453`, `cape_bps≈495`; `median_bps≈472`; `range_bps≈42`; `methods_available=4` | ±15 bps per method; ±10 bps on median |
| `ea_2024_01_02` | SXXP=478.5; Bund10Y=0.0220 | `median_bps≈525`; `methods_available=4` | ±15 bps |
| `uk_2024_01_02` | FTAS; Gilt10Y | `median_bps≈540`; `methods_available=4` | ±15 bps |
| `jp_2024_01_02` | TPX; JGB10Y; CAPE uses derived `real_rf` | `median_bps≈555`; `methods_available=4` | ±20 bps |
| `us_partial_3methods` | FactSet PDF down | `methods_available=3`; canonical computed; flag `OVERLAY_MISS` | — |
| `us_divergence_2020_03_23` | COVID trough snapshot | `range_bps > 400`; flag `ERP_METHOD_DIVERGENCE` | — |
| `damodaran_xval_2024_01_31` | `histimpl` row for Jan 2024 vs DCF same month | `|erp_dcf_bps − damodaran_bps| < 20`; no `XVAL_DRIFT` | ±20 bps |
| `insufficient_1_method` | Only Shiller available (CAPE solo) | raises `InsufficientDataError` (canonical requires ≥2) | n/a |
| `us_partial_2methods` | Only Gordon + EY available (DCF + CAPE data missing) | `methods_available=2`; canonical computed; flags `OVERLAY_MISS` + method-specific | min-boundary coverage |

## 8. Storage schema

Todas as 5 tabelas partilham um **common preamble** (inlined em cada `CREATE TABLE`, omitido aqui por brevidade):

```sql
-- Common preamble (MANDATORY in all 5 tables):
--   id                    INTEGER PRIMARY KEY AUTOINCREMENT,
--   erp_id                TEXT    NOT NULL,           -- uuid4, shared 5 rows
--   market_index          TEXT    NOT NULL,           -- 'SPX' | 'SXXP' | 'FTAS' | 'TPX'
--   country_code          TEXT    NOT NULL,           -- 'US' | 'EA' | 'UK' | 'JP'
--   date                  DATE    NOT NULL,
--   methodology_version   TEXT    NOT NULL,
--   risk_free_nominal_pct REAL    NOT NULL,           -- from NSS (decimal)
--   confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
--   flags                 TEXT,
--   created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--   UNIQUE (market_index, date, methodology_version)
```

### Method tables

```sql
CREATE TABLE erp_dcf (
    /* + common preamble */
    erp_bps              INTEGER NOT NULL,
    implied_r_pct        REAL NOT NULL,
    earnings_growth_pct  REAL NOT NULL,
    terminal_growth_pct  REAL NOT NULL
);
CREATE INDEX idx_erp_dcf_md ON erp_dcf (market_index, date);

CREATE TABLE erp_gordon (
    /* + common preamble */
    erp_bps              INTEGER NOT NULL,
    dividend_yield_pct   REAL NOT NULL,
    buyback_yield_pct    REAL,
    g_sustainable_pct    REAL NOT NULL
);
CREATE INDEX idx_erp_gordon_md ON erp_gordon (market_index, date);

CREATE TABLE erp_ey (
    /* + common preamble */
    erp_bps              INTEGER NOT NULL,
    forward_pe           REAL NOT NULL,
    forward_earnings     REAL NOT NULL,
    index_level          REAL NOT NULL
);
CREATE INDEX idx_erp_ey_md ON erp_ey (market_index, date);

CREATE TABLE erp_cape (
    /* + common preamble */
    erp_bps                 INTEGER NOT NULL,
    cape_ratio              REAL NOT NULL,
    real_risk_free_pct      REAL NOT NULL,
    real_earnings_10y_avg   REAL NOT NULL
);
CREATE INDEX idx_erp_cape_md ON erp_cape (market_index, date);
```

### Canonical summary

```sql
CREATE TABLE erp_canonical (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    erp_id                TEXT    NOT NULL UNIQUE,     -- FK-equivalent to method rows
    market_index          TEXT    NOT NULL,
    country_code          TEXT    NOT NULL,
    date                  DATE    NOT NULL,
    methodology_version   TEXT    NOT NULL,            -- 'ERP_CANONICAL_v0.1'
    erp_dcf_bps           INTEGER,                      -- NULL se método indisponível
    erp_gordon_bps        INTEGER,
    erp_ey_bps            INTEGER,
    erp_cape_bps          INTEGER,
    erp_median_bps        INTEGER NOT NULL,             -- canonical ERP (bps)
    erp_range_bps         INTEGER NOT NULL,             -- max − min of available
    methods_available     INTEGER NOT NULL CHECK (methods_available BETWEEN 1 AND 4),
    xval_deviation_bps    INTEGER,                      -- NULL quando xval não disponível no date
    confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                 TEXT,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (market_index, date, methodology_version)
);
CREATE INDEX idx_erp_canonical_md ON erp_canonical (market_index, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `integration/cost-of-capital` | L6 | `erp_median_bps` per mature market; composes `ERP + CRP` for country-specific |
| `indices/financial/F1-valuations` | L3 | `erp_median_bps` cross-market + `erp_range_bps` as uncertainty signal |
| `indices/financial/F3-risk-appetite` | L3 | `erp_range_bps` spike → risk-off regime indicator |
| `cycles/financial-fcs` | L4 | `erp_median_bps` historical percentile (valuations weight F1) |
| `integration/diagnostics/bubble-detection` | L6 | `erp_median_bps` inverted em composite bubble score |
| `outputs/editorial` | L7 | direct citation; `erp_range_bps > 400` dispara ângulo editorial "method divergence" |

## 10. Reference

- **Methodology**: [`docs/reference/overlays/erp-daily.md`](../../reference/overlays/erp-daily.md) — Manual dos Sub-Modelos Parte III (caps 7-9).
- **Data sources**: [`docs/data_sources/financial.md`](../../data_sources/financial.md) §§ equity risk premium, CAPE, earnings, buybacks; [`data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) §3 FRED SP500 fresh + §2.3 TE markets SXXP/NKY/DAX/TPX confirmed.
- **Architecture**: [`specs/conventions/patterns.md`](../conventions/patterns.md) §Pattern 4 (TE primary + native overrides para non-US index levels); Pattern 1 Parallel equals (4-methods ERP canonical).
- **Licensing**: [`governance/LICENSING.md`](../../governance/LICENSING.md) §3 attribution strings (Shiller, Damodaran, FRED); Shiller + Damodaran academic free-use + citation required per §2 rows 11-12.
- **Papers**:
  - Damodaran A. (2024), "Equity Risk Premiums: Determinants, Estimation and Implications", NYU Stern (annual update).
  - Shiller R. (2015), *Irrational Exuberance* (3rd ed.), Princeton — CAPE construction.
  - Gordon M. (1959), "Dividends, Earnings, and Stock Prices", *RES* 41(2).
  - Fama E., French K. (2002), "The Equity Premium", *J. Finance* 57(2).
- **Cross-validation**: Damodaran `histimpl.xlsx` monthly (US DCF; target < 20 bps); SPF long-run equity return (via `connectors/spf_philly`) como sanity range (< 100 bps face a SPF mean).
- **Yardeni Research**: Earnings Squiggles methodology (time-weighted consensus current + next year). Weekly PDF publications. **Use requires explicit written consent from Yardeni Research** (P2-028 tracks authorization documentation).

## 11. Non-requirements

- Does not emit country-specific ERP for markets without liquid mature index. Derived country costs live in [`integration/cost-of-capital`](../integration/) — formula `cost_of_equity_country = risk_free_country + β·ERP_mature + CRP_country`.
- Does not emit Portugal, Spain, Italy, nor EA periphery individually — derivam via `EA ERP + country CRP`.
- Does not emit emerging market ERP — EM cost-of-capital sai de `overlays/crp` + `integration/cost-of-capital`.
- Does not pick a "primary" method. Todos os 4 têm standing igual; canonical é median + range. Preferência histórica Damodaran por DCF é monitorizada via `xval_deviation_bps` mas não enforçada.
- Does not consume Damodaran monthly como input — só cross-validation. `overlays/erp-daily` é *computed*, não *consumed* (princípio `compute, don't consume`).
- Does not compute intraday — daily EOD batch; intraday re-pricing fora de escopo v2.
- Does not handle currency conversion — outputs em local-currency decimal; consumer converte se precisar.
- Does not emit forward-projected ERP (ex: ERP em 1Y, 5Y forward) — current-date apenas. Term-structure work lives em `integration/cost-of-capital`.
