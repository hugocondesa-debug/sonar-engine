# L4 · Debt Service Ratio (DSR) — Spec

> Layer L3 · indices/credit · slug: `l4-dsr` · methodology_version: `L4_DSR_v0.1`

## 1. Purpose

Compute o **Debt Service Ratio** (Drehmann-Juselius 2015) — fração do rendimento agregado que vai para servir dívida (juros + amortização). Best short-horizon (1-2Y) crisis predictor (AUC 0.89) na literatura empírica. Independente de L1/L2/L3 (não usa credit stock isoladamente — usa debt-to-GDP, lending rate e maturity como inputs separados). Sub-índice canónico do CCCS para Burden Pressure (BP).

## 2. Inputs

| Name | Type | Constraints | Source |
|---|---|---|---|
| `lending_rate_pct` | `float` | annualized weighted average lending rate over outstanding stock, decimal pct (e.g. `0.0345`) | `connectors/bis` (`WS_DSR` derived) primary; `connectors/ecb_sdw` (`MIR`) secondary; `connectors/fred` US |
| `avg_maturity_years` | `float` | residual maturity in years, weighted by outstanding | `connectors/bis` standard assumption (PNFS ~15Y, HH ~18Y, NFC ~10Y); national CB if available |
| `debt_to_gdp_ratio` | `float` | decimal ratio (e.g. `1.45` = 145%) | `connectors/bis` (`WS_TC`) — same source as L1, but as ratio not pct |
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | quarter-end business day | param |
| `segment` | `Literal` | `"PNFS"` (default; total) \| `"HH"` (households) \| `"NFC"` (non-fin corporates) | config; PNFS canonical for CCCS |
| `formula_mode` | `Literal` | `"full"` (canonical Drehmann-Juselius) \| `"o2"` (2nd-order approximation) \| `"o1"` (1st-order, interest-only) | resolver per data availability |

**Country coverage** (per BIS Q1 2026 release):

| Coverage tier | Countries | Notes |
|---|---|---|
| BIS official `WS_DSR` (32) | US, JP, DE, FR, IT, GB, CA, AU, ES, NL, SE, BE, CH, KR, NO, FI, AT, PT, IE, GR, DK, PL, CZ, HU, MX, BR, ZA, RU, TR, IN, ID, CN | direct `formula_mode="full"` consumption |
| BIS HH/NFC breakdown (17) | US, JP, DE, FR, IT, GB, CA, AU, ES, NL, SE, BE, KR, NO, FI, DK, PT | per-segment rows available |
| Approximation (o2) | rest of countries with lending_rate + debt-to-GDP available | flag `DSR_APPROX_O2` |
| Approximation (o1) | only debt-to-GDP + rate available, no maturity | flag `DSR_APPROX_O1` |
| Not coverable | no lending rate published | raise `DataUnavailableError` |

### Preconditions

Invariantes antes da invocação:

- `lending_rate_pct` decimal annualized (e.g. `0.0345` not `3.45`).
- `avg_maturity_years` > 0 e < 50 (sanity); senão `InvalidInputError`.
- `debt_to_gdp_ratio` decimal (e.g. `1.45`); NÃO percent.
- `formula_mode` selected based on data availability resolver (run before this spec).
- `methodology_version` upstream connector = runtime; senão `VersionMismatchError`.
- For `segment="HH"`, denominator should be disposable household income (DHI) where available; fallback to GDP with flag `DSR_DENOMINATOR_GDP`.

## 3. Outputs

Uma row por `(country_code, date, methodology_version, segment)` em `dsr`.

| Output | Type | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | z-score (20Y rolling de `dsr_pct`) | column |
| `score_raw` | `float` | DSR em **percent** (e.g. `18.4`) | column |
| `dsr_pct` | `float` | same as `score_raw` (alias) | column |
| `dsr_deviation_pp` | `float` | desvio face à média histórica do país, em pp | column |
| `lending_rate_pct` | `float` | input echoed (decimal) | column |
| `avg_maturity_years` | `float` | input echoed | column |
| `debt_to_gdp_ratio` | `float` | input echoed (decimal) | column |
| `annuity_factor` | `float` | computed `i / (1 − (1+i)^(−s))` (pure number) | column |
| `formula_mode` | `Literal` | `"full"`/`"o2"`/`"o1"` | column |
| `band` | `Literal` | `"baseline"`/`"alert"`/`"critical"` | column |
| `components_json` | `str` (JSON) | — | column |
| `lookback_years` | `int` | rolling window years | column |
| `confidence` | `float` | 0-1 | column |
| `flags` | `str` (CSV) | — | column |

**Canonical components_json shape**:

```json
{
  "lending_rate_pct": 0.0345,
  "avg_maturity_years": 15.0,
  "debt_to_gdp_ratio": 1.45,
  "annuity_factor": 0.0843,
  "interest_burden_pct": 5.00,
  "amort_burden_pct": 7.20,
  "dsr_pct": 12.22,
  "dsr_mean_20y_pct": 16.0,
  "dsr_deviation_pp": -3.78,
  "formula_mode": "full",
  "segment": "PNFS",
  "denominator": "GDP_4Q_sum"
}
```

## 4. Algorithm

> **Units**: `lending_rate_pct` decimal (`0.0345`); `dsr_pct` em **percent display** (`18.4`); `dsr_deviation_pp` em **percentage points**; `debt_to_gdp_ratio` decimal (`1.45`); `annuity_factor` puro número (não percent). Z-score decimal. Full rules em [`conventions/units.md`](../../conventions/units.md).

**Formulas**:

```text
# FULL (Drehmann-Juselius 2015):
annuity_factor = i / (1 − (1 + i)^(−s))
DSR_pct = annuity_factor × (D/Y) × 100

# O2 (2nd-order approximation, ~0.95 corr to full):
DSR_pct ≈ (i × D/Y + (D/Y) / s) × 100

# O1 (1st-order, interest-only, ~0.85 corr to full):
DSR_pct ≈ i × D/Y × 100
```

Where `i` = lending_rate_pct (decimal annualized), `s` = avg_maturity_years, `D/Y` = debt_to_gdp_ratio.

**Pseudocode** (deterministic):

1. Resolve `formula_mode` per data availability:
   - country ∈ BIS `WS_DSR` 32 → `"full"`;
   - else if `lending_rate + debt_to_gdp + avg_maturity` available → `"o2"` + flag `DSR_APPROX_O2`;
   - else if `lending_rate + debt_to_gdp` only → `"o1"` + flag `DSR_APPROX_O1`;
   - else raise `DataUnavailableError`.
2. For BIS-direct countries, prefer reading the BIS-published `dsr_pct` from connector and skip steps 3-4 (still record inputs for transparency).
3. Compute `annuity_factor` per `formula_mode`:
   - `"full"`: `i / (1 − (1+i)^(−s))`;
   - `"o2"`: `i + 1/s`;
   - `"o1"`: `i`.
4. Compute `dsr_pct = annuity_factor × debt_to_gdp_ratio × 100`. Set `score_raw = dsr_pct`.
5. **Historical baseline**: pull rolling 20Y of `dsr_pct` history (computed same `formula_mode` retrospectively); compute `μ`, `σ`. Require ≥ 60 obs (15Y); senão flag `INSUFFICIENT_HISTORY`.
6. `dsr_deviation_pp = dsr_pct − μ`.
7. `score_normalized = (dsr_pct − μ) / σ` clamp `[−5, +5]`.
8. **Band classification** (placeholder thresholds — recalibrate after 5Y of production data per country):
   - `dsr_deviation_pp < +2` → `"baseline"`;
   - `+2 ≤ deviation < +6` → `"alert"`;
   - `deviation ≥ +6` → `"critical"`.
9. Compute `confidence` per §6.
10. Persist row atomically.

## 5. Dependencies

| Package | Min version | Use |
|---|---|---|
| `numpy` | 1.26 | annuity factor compute, z-score |
| `pandas` | 2.1 | quarterly resampling, rolling stats |
| `sdmx1` | 2.16 | BIS `WS_DSR` upstream (connector) |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network calls.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| Country sem `WS_DSR` mas with rate + D/Y + maturity | use `"o2"` formula; flag `DSR_APPROX_O2` | −0.10 |
| Country sem maturity data | use `"o1"` formula; flag `DSR_APPROX_O1` | −0.20 |
| Country sem lending_rate available | raise `DataUnavailableError` | n/a |
| `lending_rate_pct < 0` (negative rate jurisdictions JP/CH/EA pre-2022) | accept; annuity formula still valid for tiny `i`; flag `DSR_NEG_RATE` | −0.05 |
| `avg_maturity_years` outside `(0, 50]` | raise `InvalidInputError` | n/a |
| Lookback `< 60 obs` (15Y) | flag `INSUFFICIENT_HISTORY`; use available window | −0.20 |
| Segment `HH` requested but no DHI denominator → fallback GDP | flag `DSR_DENOMINATOR_GDP` | −0.10 |
| BIS-published DSR diverges > 1pp from SONAR-computed (sanity) | persist BIS; flag `DSR_BIS_DIVERGE` | −0.10 |
| Calibração `band` thresholds expirou (>1Y) | flag `CALIBRATION_STALE` | −0.15 |
| Connector last_fetched > 90 dias face a `date` | flag `STALE` | −0.20 |
| Country tier 4 (EM) | flag `EM_COVERAGE` | cap 0.70 |
| `methodology_version` upstream ≠ runtime | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/l4-dsr/`.

| Fixture | Input | Expected | Tolerance |
|---|---|---|---|
| `pt_2024_q4_pnfs` | `i=0.0345`, `s=15`, `D/Y=1.45`, formula=full | `annuity_factor ≈ 0.0843`, `dsr_pct ≈ 12.2`, `dsr_deviation_pp ≈ −2.0`, `band="baseline"` | ±0.3pp dsr |
| `pt_2009_q4_pnfs` | crisis-era inputs (`i=0.055`, `s=15`, `D/Y=1.95`) | `dsr_pct ≈ 22.5`, `dsr_deviation_pp ≈ +6.5`, `band="critical"` | ±0.5pp |
| `au_2024_q4_pnfs` | Australia 2024 (`i=0.062`, `s=18`, `D/Y=2.05`) | `dsr_pct ≈ 22.0`, `dsr_deviation_pp ≈ +4.0`, `band="alert"` | ±0.5pp |
| `kr_2024_q4_hh` | KR households segment (`i=0.041`, `s=18`, `D/Y=1.05`) | `dsr_pct ≈ 14.0`, `band="alert"` (deviation +5) | ±0.5pp |
| `us_2024_q4_pnfs` | US 2024 BIS-direct read | `dsr_pct ≈ 15.5` matches BIS published ≤1pp | ±1pp |
| `xx_no_maturity` | only `i + D/Y` | `formula_mode="o1"`, `flags="DSR_APPROX_O1"`, confidence cap 0.70 | — |
| `jp_2020_q4_neg_rate` | `i = −0.001` | `flags="DSR_NEG_RATE"`, dsr small but valid | — |
| `xx_invalid_maturity` | `s = 60` | raises `InvalidInputError` | n/a |
| `tr_2024_q4_pnfs` | TR with high rate | `flags="EM_COVERAGE"`, confidence cap 0.70 | — |

## 8. Storage schema

```sql
CREATE TABLE dsr (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,                  -- quarter-end
    methodology_version      TEXT    NOT NULL,                  -- 'L4_DSR_v0.1'
    segment                  TEXT    NOT NULL CHECK (segment IN ('PNFS','HH','NFC')),
    score_normalized         REAL    NOT NULL,                  -- z-score
    score_raw                REAL    NOT NULL,                  -- dsr in percent
    dsr_pct                  REAL    NOT NULL,                  -- alias for score_raw
    dsr_deviation_pp         REAL    NOT NULL,                  -- vs 20Y country mean
    lending_rate_pct         REAL    NOT NULL,                  -- decimal annualized
    avg_maturity_years       REAL    NOT NULL,
    debt_to_gdp_ratio        REAL    NOT NULL,                  -- decimal (1.45 = 145%)
    annuity_factor           REAL    NOT NULL,
    formula_mode             TEXT    NOT NULL CHECK (formula_mode IN ('full','o2','o1')),
    band                     TEXT    NOT NULL CHECK (band IN ('baseline','alert','critical')),
    denominator              TEXT    NOT NULL,                  -- 'GDP_4Q_sum' | 'DHI_4Q_sum'
    components_json          TEXT    NOT NULL,
    lookback_years           INTEGER NOT NULL,
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    source_connector         TEXT    NOT NULL,                  -- 'bis_ws_dsr' | 'computed_o2'
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version, segment)
);
CREATE INDEX idx_l4_dsr_cd ON dsr (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/credit-cccs` | L4 | `score_normalized` (segment="PNFS") → BP sub-index dominant component (55% within BP); `dsr_deviation_pp` → 2D classifier burden-axis (BURDEN HIGH if > +2pp); `band="critical"` → burden override "Late-stage Boom — burden warning" |
| `outputs/editorial` | L7 | `dsr_pct` per country comparative table; `band="critical"` triggers angle "DSR — onde taxas mais altas estão a criar stress" |
| `integration/diagnostics/bubble-detection` | L6 | `band="critical"` ∧ L2 `phase_band ∈ {boom_zone, danger_zone}` → bubble watch escalate |
| `integration/cost-of-capital` | L6 | `lending_rate_pct` echo as input to country effective rate (where overrides nominal yield) |

## 10. Reference

- **Methodology**: [`docs/reference/indices/credit/L4-dsr.md`](../../../reference/indices/credit/L4-dsr.md) — Manual Cap 10.
- **Data sources**: [`docs/data_sources/credit.md`](../../../data_sources/credit.md) § Camada 1.1 (BIS `WS_DSR`) + § 1.2 (ECB `MIR`).
- **Papers**:
  - Drehmann M., Juselius M. (2012), "Do debt service costs affect macroeconomic and financial stability?", BIS Quarterly Review.
  - Drehmann M., Juselius M. (2014), "Evaluating early warning indicators of banking crises", *IJF* 30(3) — AUC 0.89 horizonte 1-2Y.
  - Drehmann M., Juselius M., Korinek A. (2015), "Going with the flows: New borrowing, debt service and the transmission of credit booms", BIS WP 520.
- **Cross-validation**: BIS published `WS_DSR` series for 32 countries; tolerance ≤ 1pp on Tier 1.

## 11. Non-requirements

- Does **not** estimate the credit gap — L2 owns trend-cycle decomposition.
- Does **not** estimate the credit impulse — L3 owns 2nd derivative.
- Does **not** model floating-rate vs fixed-rate split — `lending_rate_pct` is weighted average over stock; floating-rate transmission lag is implicit.
- Does **not** model interest rate forecasts (DSR forward path) — that is `cycles/monetary-msc` × cross-cycle integration in L6.
- Does **not** disaggregate by lender (banks vs non-banks) — only borrower segment (PNFS / HH / NFC) is exposed.
- Does **not** publish bank-side metrics (NIM, RoE, NPL) — those live em `indices/credit/extended/bank-health` (Phase 2+).
- Does **not** consume L1/L2/L3 outputs — by design L4 is independent for cross-validation purposes (DSR can fire critical even when gap is neutral, as in 2024 rate-hike regime).
- Does **not** compute country-specific maturity dynamics — uses BIS standard assumptions (`HH ~18Y, NFC ~10Y`); refinements live em country-override config (Phase 2+).

