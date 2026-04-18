# L2 · Credit-to-GDP Gap — Spec

> Layer L3 · indices/credit · slug: `l2-credit-to-gdp-gap` · methodology_version: `L2_CREDIT_GDP_GAP_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E2)

## 1. Purpose

Compute o **credit gap** — desvio do credit-to-GDP ratio (L1) face à sua trajetória de longo prazo. Sub-índice canónico do CCCS para vulnerabilidade estrutural acumulada e o regulatory benchmark de Basileia III (countercyclical capital buffer). Implementação dual: HP filter one-sided λ=400,000 (BIS standard) + Hamilton (2018) regression como controlo anti-look-ahead-bias.

## 2. Inputs

| Name | Type | Constraints | Source |
|---|---|---|---|
| `l1_score_raw` | `pd.Series[float]` | quarterly credit-to-GDP ratio in pct, ≥ 80 obs (20Y) preferível | `indices/credit/L1-credit-to-gdp-stock.score_raw` |
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | quarter-end business day | param |
| `hp_lambda` | `int` | fixed `400000` (Basileia III) | constant |
| `hamilton_horizon` | `int` | `8` quarters (2Y) per Hamilton (2018) | constant |
| `min_history_quarters` | `int` | `40` (10Y minimum); `80` preferível | config |

### Preconditions

Invariantes antes da invocação:

- `l1_score_raw` provém de `credit_to_gdp_stock` com mesmo `(country_code, date, methodology_version=L1_CREDIT_GDP_STOCK_v0.1)`.
- Série quarterly contígua (gaps ≤ 1Q linearmente interpolados upstream); senão raise `InvalidInputError`.
- `len(l1_score_raw[: date]) ≥ min_history_quarters`; senão raise `InsufficientDataError`.
- HP filter aplica-se sobre série em **percent** (não decimal) — input matches L1 unit.
- Filter é **one-sided** (recursive): no momento `date`, only data `≤ date` é usado. Two-sided variant proibido em production (look-ahead bias).
- `methodology_version` upstream = runtime; senão `VersionMismatchError`.

## 3. Outputs

Uma row por `(country_code, date, methodology_version)` em `credit_to_gdp_gap`.

| Output | Type | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | z-score (20Y rolling of gap_pp) | column |
| `score_raw` | `float` | gap em **pp** (percentage points; e.g. `+3.4`) | column |
| `gap_hp_pp` | `float` | HP one-sided gap in pp | column |
| `gap_hamilton_pp` | `float` | Hamilton residual in pp | column |
| `trend_gdp_pct` | `float` | HP-filtered trend ratio in pct | column |
| `hp_lambda` | `int` | constant `400000` | column |
| `concordance` | `Literal` | `"both_above"` \| `"both_below"` \| `"divergent"` (vs ±2pp threshold) | column |
| `components_json` | `str` (JSON) | — | column |
| `lookback_years` | `int` | rolling window years actually used | column |
| `confidence` | `float` | 0-1 | column |
| `flags` | `str` (CSV) | — | column |

**Canonical components_json shape**:

```json
{
  "ratio_pct": 145.21,
  "trend_hp_pct": 141.83,
  "gap_hp_pp": 3.38,
  "gap_hamilton_pp": 4.12,
  "hp_lambda": 400000,
  "hamilton_horizon_q": 8,
  "phase_band": "boom_zone",
  "concordance": "both_above",
  "endpoint_revision_band_pp": [2.0, 4.5]
}
```

## 4. Algorithm

> **Units**: input `l1_score_raw` em **percent** (e.g. `145.21`). Outputs `gap_*_pp` em **percentage points** (e.g. `+3.4`). Z-score decimal. Display layer adiciona sinal `+`/`−` explicit. Full rules em [`conventions/units.md`](../../conventions/units.md).

**HP filter formulation** (one-sided / recursive):

```text
minimize_τ  Σ_t (y_t − τ_t)² + λ · Σ_t [(τ_{t+1} − τ_t) − (τ_t − τ_{t−1})]²
where  λ = 400000  (Ravn-Uhlig: 1600 × 4⁴, credit cycle ~4× business cycle)

At each new t, RE-FIT trend over [t_0, t]; record τ_t (one-sided estimate).
```

**Hamilton (2018) regression**:

```text
y_t = β0 + β1·y_{t−h} + β2·y_{t−h−1} + β3·y_{t−h−2} + β4·y_{t−h−3} + ε_t
with h = 8 (2Y horizon)
gap_hamilton_t = ε_t  (forecast residual; no λ tuning, no endpoint bias)
```

**Pseudocode** (deterministic):

1. Pull `l1_score_raw` series from `credit_to_gdp_stock` for `country_code`, range `[date − 25Y, date]`.
2. Validate: ≥ `min_history_quarters` obs, monotonic dates, no NaN.
3. **HP path**: fit one-sided HP recursively up to `date`; record `trend_hp_pct[date]`. Use `statsmodels.tsa.filters.hp_filter.hpfilter` per t-slice (cache per country); `gap_hp_pp = ratio_pct − trend_hp_pct`.
4. **Hamilton path**: regress `y_t = X·β + ε` with `X = [1, y_{t-8}, y_{t-9}, y_{t-10}, y_{t-11}]` over rolling window; `gap_hamilton_pp = ε[date]`.
5. `score_raw = mean(gap_hp_pp, gap_hamilton_pp)` (canonical credit gap reported = average; both stored separately for diagnostic).
6. **Z-score normalization**: rolling window 20Y of `score_raw` history → `μ`, `σ`; `score_normalized = (score_raw − μ) / σ` clamp `[−5, +5]`.
7. **Concordance flag**: if both `gap_hp_pp > +2` AND `gap_hamilton_pp > +2` → `"both_above"`; if both `< +2` → `"both_below"`; else `"divergent"` (set `flag GAP_DIVERGENT`).
8. **Phase band** (placeholder thresholds — recalibrate after 5Y of production data per country):
   - `gap_hp_pp < −5` → `"deleveraging"`;
   - `−5 ≤ gap < +2` → `"neutral"`;
   - `+2 ≤ gap < +10` → `"boom_zone"` (CCyB activation regulatory threshold);
   - `gap ≥ +10` → `"danger_zone"`.
9. **Endpoint revision band**: re-run two-sided HP retrospectively (only stored for diagnostic, NEVER consumed downstream in production); if `|two_sided − one_sided| > 3pp`, flag `HP_ENDPOINT_REVISION`.
10. Compute `confidence` per §6.
11. Persist row atomically.

## 5. Dependencies

| Package | Min version | Use |
|---|---|---|
| `numpy` | 1.26 | arrays, regression matrices |
| `pandas` | 2.1 | quarterly resampling, rolling stats |
| `statsmodels` | 0.14 | `hp_filter.hpfilter`, OLS for Hamilton |
| `scipy` | 1.11 | sparse linear algebra (HP large-λ solver) |
| `sqlalchemy` | 2.0 | persistence |

No network calls.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| `< 40 obs` (10Y) | raise `InsufficientDataError` | n/a |
| 40-79 obs | compute both methods; flag `INSUFFICIENT_HISTORY` | −0.20 |
| HP fit fails (sparse solver non-convergent) | raise `ConvergenceError` → fallback Hamilton-only; flag `HP_FAIL` | cap 0.50 |
| Hamilton regression rank-deficient (constant series last 11Q) | fallback HP-only; flag `HAMILTON_FAIL` | cap 0.50 |
| Both methods disagree (`gap_hp` vs `gap_hamilton` differ > 5pp) | persist; flag `GAP_DIVERGENT` | −0.10 |
| Endpoint revision band > 3pp (one-sided vs two-sided) | persist; flag `HP_ENDPOINT_REVISION` | −0.10 |
| L1 input flagged `CREDIT_F_FALLBACK` | inherit; persist; flag inherited | −0.10 |
| L1 input flagged `CREDIT_BREAK` | inherit; HP unstable around break — also flag `STRUCTURAL_BREAK` | −0.20 |
| Calibração thresholds (`±2pp`, `±10pp`) expirou (>1Y review) | flag `CALIBRATION_STALE` | −0.15 |
| Country tier 4 (EM) with high-vol series | flag `EM_COVERAGE`; widen acceptance bands | cap 0.70 |
| Upstream `methodology_version ≠` runtime | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/l2-credit-to-gdp-gap/`.

| Fixture | Input | Expected | Tolerance |
|---|---|---|---|
| `pt_2024_q4` | PT credit ratio 1990-2024 | `gap_hp_pp ≈ −2.5`, `gap_hamilton_pp ≈ −1.8`, `score_raw ≈ −2.2`, `phase_band="neutral"`, `concordance="both_below"` | ±1.5pp gap, ±0.20 z |
| `pt_2009_q4` | PT credit ratio truncated to 2009 (boom peak) | `gap_hp_pp ≈ +14.0`, `phase_band="danger_zone"`, `concordance="both_above"` | ±2pp |
| `us_2007_q3` | US credit ratio truncated to 2007 (pre-crisis) | `gap_hp_pp ≈ +9.5`, `gap_hamilton_pp ≈ +11.0`, `phase_band="boom_zone"`, `flags=""` | ±2pp |
| `cn_2016_q1` | CN credit ratio (post-stimulus) | `gap_hp_pp ≈ +25.0`, `phase_band="danger_zone"`, `flags="EM_COVERAGE"` | ±5pp |
| `pt_1995_short` | Only 32 obs (8Y) | raises `InsufficientDataError` | n/a |
| `xx_divergent_synthetic` | engineered HP-Hamilton divergence ~7pp | `flags="GAP_DIVERGENT"`, `concordance="divergent"` | — |
| `xx_endpoint_revision_synthetic` | recent regime change shifts trend | `flags="HP_ENDPOINT_REVISION"` | — |
| `pt_2009_inherited_break` | PT 2009 run with L1 `CREDIT_BREAK` set | flags inherit `CREDIT_BREAK,STRUCTURAL_BREAK`; confidence ≤ 0.55 | — |

## 8. Storage schema

```sql
CREATE TABLE credit_to_gdp_gap (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,                  -- quarter-end
    methodology_version      TEXT    NOT NULL,                  -- 'L2_CREDIT_GDP_GAP_v0.1'
    score_normalized         REAL    NOT NULL,                  -- z-score
    score_raw                REAL    NOT NULL,                  -- avg(gap_hp, gap_hamilton) in pp
    gap_hp_pp                REAL    NOT NULL,                  -- one-sided HP gap
    gap_hamilton_pp          REAL    NOT NULL,                  -- Hamilton residual
    trend_gdp_pct            REAL    NOT NULL,                  -- HP-filtered trend ratio (pct)
    hp_lambda                INTEGER NOT NULL DEFAULT 400000,
    hamilton_horizon_q       INTEGER NOT NULL DEFAULT 8,
    concordance              TEXT    NOT NULL CHECK (concordance IN ('both_above','both_below','divergent')),
    phase_band               TEXT    NOT NULL,                  -- 'deleveraging'|'neutral'|'boom_zone'|'danger_zone'
    components_json          TEXT    NOT NULL,
    lookback_years           INTEGER NOT NULL,
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    source_connector         TEXT    NOT NULL,                  -- 'l1_credit_gdp_stock'
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_l2_cgg_cd ON credit_to_gdp_gap (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/credit-cccs` | L4 | `score_normalized` → SS sub-index dominant component (60% within SS); `phase_band` → 2D classifier stock-axis input |
| `cycles/credit-cccs` (classifier) | L4 | `gap_hp_pp` direto para STOCK HIGH/LOW threshold (±2pp) |
| `outputs/editorial` | L7 | `phase_band` + `concordance` para narrative ("HP e Hamilton concordam em zona Boom") |
| `integration/diagnostics/bubble-detection` | L6 | `gap_hp_pp > +10pp` AND L4 `dsr_deviation > +6pp` AND F1 valuation extreme → bubble alert |

## 10. Reference

- **Methodology**: [`docs/reference/indices/credit/L2-credit-to-gdp-gap.md`](../../../reference/indices/credit/L2-credit-to-gdp-gap.md) — Manual Cap 8.
- **Data sources**: [`docs/data_sources/credit.md`](../../../data_sources/credit.md) § Camada 1.1 (BIS `WS_TC` gaps cross-validation); [`data_sources/D2_empirical_validation.md`](../../../data_sources/D2_empirical_validation.md) §4 BIS findings.
- **Architecture**: [`adr/ADR-0005-country-tiers-classification.md`](../../../adr/ADR-0005-country-tiers-classification.md) (L2 scope = T1-T2 BIS universe; tier-4 raise `DataUnavailableError` inherited from L1).
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §3 (BIS CC-BY-4.0).
- **Backlog**: `CAL-019` (BIS WS_TC key pending) afecta L1 input → L2 fail propagado via `InsufficientDataError`.
- **Papers**:
  - Drehmann M., Borio C., Tsatsaronis K. (2010), "Anchoring countercyclical capital buffers", BIS WP 317.
  - Drehmann M., Juselius M. (2014), "Evaluating early warning indicators of banking crises", *IJF* 30(3).
  - Hamilton J. (2018), "Why You Should Never Use the Hodrick-Prescott Filter", *RES* 100(5).
  - Ravn M., Uhlig H. (2002), "On Adjusting the Hodrick-Prescott Filter for the Frequency of Observations", *RES* 84(2).
- **Cross-validation**: BIS published gap (`data.bis.org` `WS_TC` gap variable) — target ≤ 0.5pp deviation on Tier 1 economies.

## 11. Non-requirements

- Does **not** publish a real-time *two-sided* HP gap — that variant is computed only as diagnostic for `HP_ENDPOINT_REVISION` flag and never persisted as `score_raw`.
- Does **not** estimate Beveridge-Nelson decomposition — third method optional in `indices/credit/extended/` for long-history countries (Phase 2+).
- Does **not** fit country-specific HP λ — `400000` is fixed (Basileia III regulatory parameter).
- Does **not** classify cycle *phase* (Boom/Contraction/Repair/Recovery) — that requires stock × flow joint, lives em `cycles/credit-cccs`.
- Does **not** consume L4 DSR or L3 impulse — purely L1-derived; cross-cycle integration lives downstream.
- Does **not** emit alerts directly — flag emission per Edge cases only; alerts live em `outputs/editorial` and `cycles/credit-cccs` decision rules.
- Does **not** backfill historical revisions of the BIS-published gap — SONAR computes its own gap; BIS values are cross-validation reference, not consumed.

