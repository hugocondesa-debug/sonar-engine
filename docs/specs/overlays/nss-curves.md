# NSS Yield Curves — Spec

> Layer L2 · overlay · slug: `nss-curves` · methodology_version: `NSS_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E1)

## 1. Purpose

Fit Nelson-Siegel-Svensson (6-param) to observed sovereign yields per country-date and derive four curve families: **spot**, **zero**, **forward**, **real**. Primary risk-free primitive for all downstream valuations (ERP, CRP, cost-of-capital) and slope/curvature signals for cycles (MSC, ECS, CCCS, FCS).

## 2. Inputs

| Name | Type | Constraints | Source |
|---|---|---|---|
| `tenors_years` | `np.ndarray[float]` | ≥6 obs, ∈ grid `[1/12, 3/12, 6/12, 1, 2, 3, 5, 7, 10, 15, 20, 30]` | connector |
| `yields_pct` | `np.ndarray[float]` | len == tenors, ∈ [-5, 30]%, no NaN | connector |
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | business day local to country | param |
| `curve_input_type` | `Literal` | `"par"` \| `"zero"` \| `"linker_real"` | connector |

**Per country-date primary connector** (fallback order, aligned com ADR-0005 country tiers + Pattern 4 TE primary + native overrides):

| Country group | Primary | Secondary | Cross-validation target |
|---|---|---|---|
| T1 US | `connectors/treasury_gov` (par) | `connectors/fred` (DGS*) | Fed GSW NSS <10 bps |
| T1 DE/EA-AAA | `connectors/bundesbank` (Svensson) | `connectors/ecb_sdw` | Bundesbank <5 bps |
| T1 UK | `connectors/boe_yieldcurves` (Anderson-Sleath) | — | BoE <10 bps |
| T1 JP | `connectors/mof_japan` | — | MoF <10 bps |
| T1 FR/IT/ES/NL/CA/AU/CH/NO/SE/NZ | own CB / Treasury | `ecb_sdw` (EA members) / `fred` (mirrors) | <15 bps |
| T1 PT | `connectors/igcp` | `ecb_sdw` (PT 10Y mirror) | ECB SDW <15 bps |
| T2 EMs (CN/IN/BR/MX/TR/ZA/KR/...) | `connectors/te` `/country/{c}/indicators` sovereign yields per tenor (Pattern 4 primary) | native CB where available (BCB/RBI/CBRT/...) | wider CI; target <30 bps vs TE sanity |
| T3+ | `connectors/te` breadth quando disponível; ≥6 tenores required senão raise `InsufficientDataError` | — | no target (EM coverage caveat) |

## 3. Outputs

Four sibling records per `(country, date)`; all share `methodology_version` and `fit_id`.

| Output | Shape | Storage |
|---|---|---|
| Spot curve | `{params: {β0..β3, λ1, λ2}, fitted: {tenor: pct}, rmse_bps, confidence}` | `yield_curves_spot` |
| Zero curve | `{zero_rates: {tenor: pct}, method: "nss_derived" \| "bootstrap"}` | `yield_curves_zero` |
| Forward curve | `{forwards: {"1y1y","1y2y","1y5y","5y5y","10y10y": pct}}` | `yield_curves_forwards` |
| Real curve | `{real_yields: {tenor: pct}, method: "direct_linker" \| "derived"}` | `yield_curves_real` |

Standard output tenors (spot/zero): `["1M","3M","6M","1Y","2Y","3Y","5Y","7Y","10Y","15Y","20Y","30Y"]`.

## 4. Algorithm

**Model**:

```text
y(τ) = β0
     + β1 · (1 − e^(−τ/λ1)) / (τ/λ1)
     + β2 · [(1 − e^(−τ/λ1)) / (τ/λ1) − e^(−τ/λ1)]
     + β3 · [(1 − e^(−τ/λ2)) / (τ/λ2) − e^(−τ/λ2)]
```

**Fit** (`scipy.optimize.minimize`, `L-BFGS-B`):

```text
x0      = [yields[-1], yields[0] − yields[-1], 0.0, 0.0, 1.5, 5.0]
bounds  = [(0, 0.20), (-0.15, 0.15), (-0.15, 0.15), (-0.15, 0.15), (0.1, 10), (0.1, 30)]
loss(x) = Σ (nss(tenors, *x) − yields)²
```

**Pipeline per country-date**:

1. Fetch raw yields from primary connector; fallback if stale >1 business day.
2. Validate: `len >= 6`, finite, within `[-5%, 30%]`; else raise `InsufficientDataError` / flag.
3. Fit NSS → `(β0, β1, β2, β3, λ1, λ2)`; record `rmse_bps = sqrt(mean((ŷ−y)²)) · 10000`.
4. **Zero curve**: evaluate NSS at standard tenors treated as continuously compounded → zero rates.
5. **Forward curve**: `f(t1,t2) = [((1+z2)^t2) / ((1+z1)^t1)]^(1/(t2−t1)) − 1` for `{1y1y, 1y2y, 1y5y, 5y5y, 10y10y}`.
6. **Real curve**: if country ∈ {US,UK,DE,IT,FR,CA,AU} → fit NSS to linker yields (TIPS/ILGs/OATi/BTP€i/ILBs/RRBs/TIBs); else `real(τ) = nominal(τ) − E[π(τ)]` from `overlays/expected-inflation`.
7. Compute `confidence` (see §6 matrix).
8. Cross-validate vs BC-published where available; record `xval_deviation_bps`.
9. Persist 4 records to §8 tables atomically.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | arrays |
| `scipy` | 1.11 | `optimize.minimize` (L-BFGS-B) |
| `pandas` | 2.1 | i/o |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network; inputs pre-fetched.

## 6. Edge cases

Flags → [`conventions/flags.md`](../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../conventions/exceptions.md). Confidence impact é aplicado conforme regras de `flags.md` § "Convenção de propagação".

| Trigger | Handling | Confidence |
|---|---|---|
| `<6 observations` | raise `InsufficientDataError` | n/a |
| 6-8 obs | 4-param Nelson-Siegel (drop β3, λ2); flag `NSS_REDUCED` | cap 0.75 |
| Optimizer did not converge | raise `ConvergenceError` → linear interp fallback; flag `NSS_FAIL` | cap 0.50 |
| `rmse_bps > 15` (Tier 1) or `> 30` (Tier 4) | keep fit; flag `HIGH_RMSE` | −0.20 |
| `|xval_deviation| > target` | keep fit; flag `XVAL_DRIFT` | −0.10 |
| Forward `< −1%` at tenor > 1Y | flag `NEG_FORWARD`; drop that forward from output | −0.15 (partial) |
| Tenor gap (e.g. no 15-25Y obs) | mark fitted values `EXTRAPOLATED` | −0.10 (affected tenors) |
| Stale input (> 2 business days) | flag `STALE`, emit anyway | −0.20 |
| Multi-hump curve (3+ sign changes in 1st deriv) | flag `COMPLEX_SHAPE` | −0.10 |
| EM regime break (σ(Δy) > 3× 5Y mean) | widen bounds; flag `REGIME_BREAK` | cap 0.60 |
| Country tier 4 | cap confidence regardless; flag `EM_COVERAGE` | cap 0.70 |

## 7. Test fixtures

Stored in `tests/fixtures/nss-curves/` as `<id>.json` pairs.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01_02` | 11 Treasury par yields | `β0 ≈ 0.0415` (= 4.15% display), `rmse_bps < 5`, `fitted_10Y ≈ 0.0388` (= 3.88%) | ±10% β, ±2 bps rmse |
| `de_bund_2024_01_02` | 10 Bund par yields + published Svensson | `|SONAR − Bundesbank| < 5 bps` all tenors | ±5 bps |
| `uk_2024_01_02` | Gilt curve + BoE A-S | `|SONAR − BoE| < 10 bps` for 2Y/5Y/10Y | ±10 bps |
| `pt_2024_01_02` | 7 IGCP OT tenors | `fitted_10Y ≈ ECB SDW PT 10Y ± 15 bps`, `confidence ≥ 0.80` | ±15 bps |
| `pt_sparse_5` | 5 tenors | raises `InsufficientDataError` | n/a |
| `tr_2024_01_02` | TR sparse, high vol | `confidence ≤ 0.70`, flag `EM_COVERAGE` set | — |
| `nss_failure_synthetic` | synthetic multi-hump extreme | `NSS_FAIL` flag, falls back to spline | — |
| `forward_5y5y_us_2024_01_02` | from fixture `us_2024_01_02` | `5y5y ≈ 0.0385 ± 10 bps` (= 3.85% display); matches FRED `T5YIFR` | ±10 bps |
| `real_us_2024_01_02` | TIPS 5/7/10/20/30Y | `real_10Y ≈ 0.0185` (= 1.85%), breakeven `10Y ≈ 0.0220` (= 2.20%) | ±15 bps |

## 8. Storage schema

```sql
CREATE TABLE yield_curves_spot (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code          TEXT    NOT NULL,
    date                  DATE    NOT NULL,
    methodology_version   TEXT    NOT NULL,
    fit_id                TEXT    NOT NULL,               -- uuid shared across sibling tables
    beta_0                REAL    NOT NULL,
    beta_1                REAL    NOT NULL,
    beta_2                REAL    NOT NULL,
    beta_3                REAL,                            -- NULL if 4-param fit
    lambda_1              REAL    NOT NULL,
    lambda_2              REAL,
    fitted_yields_json    TEXT    NOT NULL,                -- {"3M":2.68,...}
    observations_used     INTEGER NOT NULL,
    rmse_bps              REAL    NOT NULL,
    xval_deviation_bps    REAL,                            -- vs BC-published
    confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                 TEXT,                            -- CSV: NSS_REDUCED,HIGH_RMSE,...
    source_connector      TEXT    NOT NULL,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_ycs_cd ON yield_curves_spot (country_code, date);

CREATE TABLE yield_curves_zero (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code          TEXT    NOT NULL,
    date                  DATE    NOT NULL,
    methodology_version   TEXT    NOT NULL,
    fit_id                TEXT    NOT NULL,
    zero_rates_json       TEXT    NOT NULL,              -- {"3M":0.0268,"6M":0.0273,...}
    derivation            TEXT    NOT NULL CHECK (derivation IN ('nss_derived', 'bootstrap')),
    confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                 TEXT,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (fit_id) REFERENCES yield_curves_spot(fit_id) ON DELETE CASCADE,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_ycz_cd ON yield_curves_zero (country_code, date);

CREATE TABLE yield_curves_forwards (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code          TEXT    NOT NULL,
    date                  DATE    NOT NULL,
    methodology_version   TEXT    NOT NULL,
    fit_id                TEXT    NOT NULL,
    forwards_json         TEXT    NOT NULL,              -- {"1y1y":0.0385,"5y5y":0.0355,...}
    breakeven_forwards_json TEXT,                         -- only where linkers exist
    confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                 TEXT,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (fit_id) REFERENCES yield_curves_spot(fit_id) ON DELETE CASCADE,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_ycf_cd ON yield_curves_forwards (country_code, date);

CREATE TABLE yield_curves_real (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code          TEXT    NOT NULL,
    date                  DATE    NOT NULL,
    methodology_version   TEXT    NOT NULL,
    fit_id                TEXT    NOT NULL,
    real_yields_json      TEXT    NOT NULL,              -- {"5Y":0.0185,"10Y":0.0202,...}
    method                TEXT    NOT NULL CHECK (method IN ('direct_linker', 'derived')),
    linker_connector      TEXT,                           -- NULL if derived
    confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                 TEXT,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (fit_id) REFERENCES yield_curves_spot(fit_id) ON DELETE CASCADE,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_ycr_cd ON yield_curves_real (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `overlays/erp-daily` | L2 | risk-free rate (10Y nominal spot per market) |
| `overlays/crp` | L2 | sovereign spread vs benchmark (Bund/UST) |
| `overlays/expected-inflation` | L2 | 5y5y breakeven forward; real-nominal decomposition |
| `indices/monetary/M1-effective-rates` | L3 | short-end (3M, 1Y) |
| `indices/monetary/M3-market-expectations` | L3 | 1y1y, 2y1y, 5y5y forwards |
| `indices/economic/E2-leading` | L3 | 10Y−2Y slope (recession signal) |
| `indices/credit/L2-credit-to-gdp-gap` | L3 | discount factor for DSR |
| `indices/financial/F1-valuations` | L3 | term premium decomposition |
| `cycles/monetary-msc` | L4 | β1 (slope), β2 (curvature) as stance factors |
| `integration/cost-of-capital` | L6 | discount-rate curve per country |

## 10. Reference

- **Methodology**: [`docs/reference/overlays/nss-curves.md`](../../reference/overlays/nss-curves.md) — caps 4-6 do Manual dos Sub-Modelos.
- **Data sources**: [`docs/data_sources/monetary.md`](../../data_sources/monetary.md) § yield curves; [`data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) §3 FRED DGS* fresh; §8 OECD CLI (related forward curves).
- **Architecture**: [`adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) (tier scope); [`specs/conventions/patterns.md`](../conventions/patterns.md) §Pattern 4 (TE primary + native overrides).
- **Licensing**: [`governance/LICENSING.md`](../../governance/LICENSING.md) §3 (FRED/Bundesbank/BoE/MoF attribution).
- **Papers**:
  - Nelson C., Siegel A. (1987), "Parsimonious Modeling of Yield Curves", *Journal of Business* 60(4).
  - Svensson L. (1994), "Estimating and Interpreting Forward Interest Rates", *NBER WP 4871*.
  - Gurkaynak R., Sack B., Wright J. (2007), "The U.S. Treasury Yield Curve: 1961 to the Present", *JME* 54(8).
  - Litterman R., Scheinkman J. (1991), "Common Factors Affecting Bond Returns", *J. Fixed Income* 1(1).
- **Cross-validation**: Fed GSW (US, daily), Bundesbank Svensson (DE, daily), BoE Anderson-Sleath (UK, daily).

## 11. Non-requirements

- Does not interpolate across dates — that lives in `specs/pipelines/daily-curves.md` (gap-filling).
- Does not refit intra-day — daily batch only; intraday re-pricing is out of scope for v2.
- Does not handle currency conversion of yields — FX primitives live in `overlays/expected-inflation` (PPP) and `integration/cost-of-capital`.
- Does not emit partial outputs when `InsufficientDataError` triggers — raise early, no stub rows.
- Does not expose raw NSS parameters as a consumption API — only the four curve families (spot/zero/forward/real). `β_i`, `λ_i` are diagnostic, not public contract.
- Does not fit inflation-linked curves in markets without linker issuance — those countries go through the *derived* path (nominal − E[π]).
- Does not replace BC-published curves where mandated by regulation/reporting — SONAR output is analytic, not authoritative for accounting.
