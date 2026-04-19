# L1 · Credit-to-GDP Stock — Spec

> Layer L3 · indices/credit · slug: `l1-credit-to-gdp-stock` · methodology_version: `L1_CREDIT_GDP_STOCK_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E2)

## 1. Purpose

Compute o stock total de crédito ao private non-financial sector (PNFS) em proporção do GDP nominal — base level estrutural do ciclo de crédito (CCCS). Primary primitive consumido por L2 (HP gap) e L3 (credit impulse). Output canónico: BIS Q-series (total credit) com fallback para F-series (bank-only) quando Q indisponível.

## 2. Inputs

| Name | Type | Constraints | Source |
|---|---|---|---|
| `credit_stock_lcu` | `pd.Series[float]` | quarterly, lcu (local currency units), ≥ 80Y rolling history (320 obs) preferível, FX-adjusted | `connectors/bis` (`WS_TC` Q-series primary; F-series fallback) |
| `gdp_nominal_lcu` | `pd.Series[float]` | quarterly nominal GDP, lcu, **4Q rolling sum** computed | `connectors/bis` (denominator embebido em `WS_TC`) ou `connectors/eurostat` (`namq_10_gdp`) / `connectors/fred` (`GDP*`) |
| `country_code` | `str` | ISO 3166-1 α-2 upper (`PT`, `DE`, `US`, `EA`, …) | config |
| `date` | `date` | quarter-end business day local | param |
| `series_variant` | `Literal` | `"Q"` (total credit, default) \| `"F"` (bank-only fallback) | resolver per country |
| `gdp_vintage_mode` | `Literal` | `"production"` (last revised) \| `"backtest"` (real-time vintage) | config |

**Country coverage** (per BIS Q1 2026 release):

| Tier | Series | Countries | Notes |
|---|---|---|---|
| 1 | Q + F + DSR | US, JP, DE, FR, IT, GB, CA, AU, ES, NL, SE, BE, CH, KR, NO, FI, AT, PT, IE, GR, DK, NZ, CZ, HU, PL, IL, MX, BR, ZA, IN, ID, MY, RU, TR, SA, AR, CN, HK, SG, TH | 40 economies BIS Q-series |
| 2 | F-only fallback | EE, LV, LT, LU, SI, SK, HR | bank credit only; flag `CREDIT_F_FALLBACK` |
| 3 | not covered | rest of EM | raise `DataUnavailableError` |

### Preconditions

Invariantes antes da invocação:

- `credit_stock_lcu` e `gdp_nominal_lcu` partilham `(country_code, date)` quarterly grid; gaps ≤ 1Q toleráveis (linear interp upstream).
- BIS series já FX-adjusted para crédito FX (Hungria CHF, Polónia CHF) — no FX adjustment downstream.
- Government debt EXCLUÍDO do numerador (PNFS-only).
- Inter-bank lending excluído (BIS-side).
- `gdp_nominal_lcu` rolling 4Q-sum, NÃO ponto-a-ponto (sazonalidade-killer).
- `methodology_version` da row connector bate com runtime; senão raise `VersionMismatchError`.
- `series_variant="Q"` quando country ∈ Tier 1; `"F"` apenas se Q ausente >2Q stale.

## 3. Outputs

Uma row por `(country_code, date, methodology_version)` em `credit_to_gdp_stock`.

| Output | Type | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | z-score (20Y rolling) | column |
| `score_raw` | `float` | percent (e.g. `145.3` = 145.3%) | column |
| `components_json` | `str` (JSON) | — | column |
| `lookback_years` | `int` | years | column |
| `confidence` | `float` | 0-1 | column |
| `flags` | `str` (CSV) | — | column |
| `methodology_version` | `str` | — | column |

**Canonical components_json shape**:

```json
{
  "credit_stock_lcu": 4.532e11,
  "gdp_4q_sum_lcu": 3.121e11,
  "ratio_pct": 145.21,
  "series_variant": "Q",
  "gdp_vintage_mode": "production",
  "rolling_mean_20y_pct": 168.4,
  "rolling_std_20y_pct": 22.7,
  "structural_band": "advanced_economy_typical"
}
```

## 4. Algorithm

> **Units**: `score_raw` em **percent display** (`145.3`, NÃO `1.453`) por consistência com BIS publication. `score_normalized` decimal z-score. Spreads não aplicam aqui. Full rules em [`conventions/units.md`](../../conventions/units.md).

**Formula** (BIS canonical):

```text
CtG_t = Total_Credit_PNFS_t / GDP_nominal_4Q_sum_t × 100
```

**Pseudocode** (deterministic):

1. Resolve `series_variant`: try Q-series; if `DataUnavailableError` OR last obs > 2Q stale → fall back to F-series + flag `CREDIT_F_FALLBACK`.
2. Load `credit_stock_lcu[date]` and `gdp_nominal_lcu` rolling 4Q sum centred at `date`.
3. Validate: both > 0, no NaN, non-negative growth jumps `< 50%` quarter (else flag `CREDIT_BREAK`).
4. Compute `ratio_pct = credit_stock_lcu / gdp_4q_sum_lcu × 100`.
5. Set `score_raw = ratio_pct`.
6. Pull rolling history: `history = ratio_pct[date − 20Y : date]`. Require ≥ 60 obs (15Y of quarters); else flag `INSUFFICIENT_HISTORY` and use available window with `lookback_years = floor(len/4)`.
7. Compute `μ = mean(history)`, `σ = std(history, ddof=1)`.
8. `score_normalized = (ratio_pct − μ) / σ` (clamp output `[−5, +5]`).
9. Classify `structural_band` per country level (placeholder bands `<50% sub-financialized; 50-100% intermediate; 100-150% advanced typical; 150-200% highly financialized; >200% outlier` — recalibrate after 5Y of production data).
10. Compute `confidence` per §6 matrix.
11. Persist to §8 schema atomically with `methodology_version="L1_CREDIT_GDP_STOCK_v0.1"`.

## 5. Dependencies

| Package | Min version | Use |
|---|---|---|
| `numpy` | 1.26 | rolling stats, z-score |
| `pandas` | 2.1 | quarterly resampling, rolling 4Q sums |
| `sdmx1` | 2.16 | BIS SDMX REST queries (upstream connector) |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network calls inside the algorithm — connectors pre-fetch.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md). Confidence propagation per `flags.md` § "Convenção de propagação".

| Trigger | Handling | Confidence |
|---|---|---|
| Q-series indisponível para country | fall back to F-series; flag `CREDIT_F_FALLBACK` | cap 0.75 |
| F-series também indisponível | raise `DataUnavailableError`; no row | n/a |
| `< 60 obs` na rolling window (< 15Y) | compute z-score com obs disponíveis; flag `INSUFFICIENT_HISTORY` | −0.20 |
| Quarterly jump > 50% (likely write-off ou re-classification) | persist; flag `CREDIT_BREAK` | −0.15 |
| GDP vintage mismatch entre `production` requested mas só `backtest` disponível | persist; flag `STALE` | −0.20 |
| Connector last_fetched > 90 dias face a `date` | flag `STALE` (`OVERLAY_MISS` se totalmente ausente) | −0.20 |
| Country tier 4 / EM com cobertura BIS limitada | flag `EM_COVERAGE` | cap 0.70 |
| Calibração `structural_band` thresholds expirou (>1Y desde último review) | flag `CALIBRATION_STALE` | −0.15 |
| `methodology_version` upstream ≠ runtime | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/l1-credit-to-gdp-stock/`. Cada fixture = `input_*.json` + `expected_*.json`.

| Fixture | Input | Expected | Tolerance |
|---|---|---|---|
| `pt_2024_q4` | BIS Q-series PT credit_stock + EA GDP | `score_raw ≈ 145.0`, `score_normalized ≈ −1.10` (post-deleveraging), `series_variant="Q"`, `flags=""` | ±2pp ratio, ±0.10 z |
| `us_2024_q4` | BIS Q-series US | `score_raw ≈ 155.0`, `score_normalized ≈ +0.15` | ±2pp, ±0.10 |
| `cn_2024_q4` | BIS Q-series CN | `score_raw ≈ 220.0`, `score_normalized ≈ +2.10`, `flags="EM_COVERAGE"` | ±5pp, ±0.20 |
| `ee_2024_q4` | F-series only (Estonia) | `series_variant="F"`, `flags="CREDIT_F_FALLBACK"` | — |
| `pt_1995_q1_short_history` | only 8Y of obs | `flags="INSUFFICIENT_HISTORY"`, `lookback_years=8`, `confidence ≤ 0.65` | — |
| `xx_unavailable` | nem Q nem F | raises `DataUnavailableError` | n/a |
| `ar_2023_q4_break` | jump +60% intra-Q | `flags="CREDIT_BREAK"`, persist anyway | — |

## 8. Storage schema

```sql
CREATE TABLE credit_to_gdp_stock (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code          TEXT    NOT NULL,
    date                  DATE    NOT NULL,                    -- quarter-end
    methodology_version   TEXT    NOT NULL,                    -- 'L1_CREDIT_GDP_STOCK_v0.1'
    score_normalized      REAL    NOT NULL,                    -- z-score
    score_raw             REAL    NOT NULL,                    -- ratio in percent (145.3)
    components_json       TEXT    NOT NULL,
    series_variant        TEXT    NOT NULL CHECK (series_variant IN ('Q', 'F')),
    gdp_vintage_mode      TEXT    NOT NULL CHECK (gdp_vintage_mode IN ('production', 'backtest')),
    lookback_years        INTEGER NOT NULL,
    structural_band       TEXT,                                 -- 'advanced_economy_typical' | ...
    confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                 TEXT,                                 -- CSV
    source_connector      TEXT    NOT NULL,                    -- 'bis_ws_tc'
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_l1_cgs_cd ON credit_to_gdp_stock (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `indices/credit/L2-credit-to-gdp-gap` | L3 | `score_raw` (raw ratio) → HP filter input |
| `indices/credit/L3-credit-impulse` | L3 | `components_json.credit_stock_lcu` + `gdp_4q_sum_lcu` → 2nd derivative |
| `cycles/credit-cccs` | L4 | `score_normalized` → SS sub-index (25% within sub-index after L2 weighting) |
| `outputs/editorial` | L7 | `score_raw` + `structural_band` para narrative cross-country |

## 10. Reference

- **Methodology**: [`docs/reference/indices/credit/L1-credit-to-gdp-stock.md`](../../../reference/indices/credit/L1-credit-to-gdp-stock.md) — Manual Ciclo de Crédito Cap 7.
- **Data sources**: [`docs/data_sources/credit.md`](../../../data_sources/credit.md) § Camada 1.1 (BIS `WS_TC`); [`data_sources/D2_empirical_validation.md`](../../../data_sources/D2_empirical_validation.md) §4 BIS WS_TC key format pending (CAL-019 Phase 1 dev); WS_DSR 7/7 countries OK confirming BIS SDMX v1 reliability.
- **Architecture**: [`adr/ADR-0005-country-tiers-classification.md`](../../../adr/ADR-0005-country-tiers-classification.md) (BIS 43-country universe aligns com T1-T2 ADR-0005 scope; T3+ fora BIS → `DataUnavailableError` tier-4 degraded).
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §3 (BIS CC-BY-4.0 attribution).
- **Backlog**: [`backlog/calibration-tasks.md`](../../../backlog/calibration-tasks.md) `CAL-019` — BIS WS_TC key unit format debug.
- **Papers**:
  - Drehmann M., Borio C., Tsatsaronis K. (2010), "Anchoring countercyclical capital buffers", BIS WP 317.
  - Schularick M., Taylor A. (2012), "Credit Booms Gone Bust", *AER* 102(2).
  - Jordà Ò., Schularick M., Taylor A. (2017), "Macrofinancial History and the New Business Cycle Facts", JST Macrohistory.
- **Cross-validation**: BIS published `data.bis.org` UI; tolerance ≤ 1pp ratio.

## 11. Non-requirements

- Does **not** apply HP filter — L2 owns trend-cycle decomposition.
- Does **not** compute second derivative / momentum — L3 owns that path.
- Does **not** estimate debt service burden — L4 owns DSR formula.
- Does **not** disaggregate household vs corporate credit — sub-aggregates live em `indices/credit/extended/` (Phase 2+).
- Does **not** FX-adjust foreign-currency credit (BIS already does in `WS_TC`); raw connector pre-cleans.
- Does **not** emit pre-1970 series — JST `tloans` reservado para `pipelines/backfill-strategy` (annual frequency, separate spec).
- Does **not** classify cycle phase — only emits a level + z-score; phase classification lives em `cycles/credit-cccs`.
- Does **not** expose vintage-by-vintage GDP revisions — `gdp_vintage_mode` chooses one mode per row; vintage history is connector responsibility.
