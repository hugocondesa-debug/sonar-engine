# L3 · Credit Impulse — Spec

> Layer L3 · indices/credit · slug: `l3-credit-impulse` · methodology_version: `L3_CREDIT_IMPULSE_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E2)

## 1. Purpose

Compute o **credit impulse** (Biggs-Mayer-Pick 2010) — segunda derivada do credit stock face ao GDP. Mede a aceleração do credit flow, isto é, contributo marginal do crédito para a procura agregada. Lead 2-4 trimestres face a GDP growth empiricamente. Independente de L2 (não consume HP gap) mas partilha o raw credit stock e GDP nominal usados em L1.

## 2. Inputs

| Name | Type | Constraints | Source |
|---|---|---|---|
| `credit_stock_lcu` | `pd.Series[float]` | quarterly, lcu, ≥ 12 obs (3Y) — fórmula precisa de `t`, `t−4`, `t−8` | `connectors/bis` (`WS_TC`) — same series consumed by L1; alternativamente `indices/credit/L1-credit-to-gdp-stock.components_json.credit_stock_lcu` |
| `gdp_nominal_lcu` | `pd.Series[float]` | quarterly nominal GDP, lcu (NOT 4Q rolling sum here — point quarterly) | `connectors/bis` denom OR `connectors/eurostat`/`fred` |
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | quarter-end business day | param |
| `series_variant` | `Literal` | `"Q"` (default) \| `"F"` (fallback) — must mirror L1 choice for consistency | resolver |
| `smoothing` | `Literal` | `"raw"` \| `"ma4"` (4Q moving avg) | config; default `"ma4"` |
| `segment` | `Literal` | `"PNFS"` (total, default) \| `"HH"` (households) \| `"NFC"` (non-fin corporates) | config; PNFS is canonical for CCCS |

### Preconditions

Invariantes antes da invocação:

- `credit_stock_lcu` e `gdp_nominal_lcu` partilham `(country_code, date)` quarterly grid.
- ≥ 12 obs disponíveis em `[date − 3Y, date]`; senão raise `InsufficientDataError`.
- `series_variant` matches L1 row's variant (read from `credit_to_gdp_stock` for same `country_code, date`); senão flag `L1_VARIANT_MISMATCH`.
- BIS series já FX-adjusted upstream.
- `gdp_nominal_lcu` ponto quarterly (NÃO 4Q sum — diferente de L1: aqui denominador é `GDP_{t−4}` ponto, para normalizar o fluxo).
- `methodology_version` upstream connector = runtime; senão `VersionMismatchError`.

## 3. Outputs

Uma row por `(country_code, date, methodology_version, segment)` em `credit_impulse`.

| Output | Type | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | z-score (20Y rolling) | column |
| `score_raw` | `float` | impulse em **pp of GDP** (e.g. `+1.8`) | column |
| `impulse_pp` | `float` | same as `score_raw` (alias for clarity) | column |
| `flow_t_lcu` | `float` | `Credit_t − Credit_{t−4}` (lcu) | column |
| `flow_t_minus4_lcu` | `float` | `Credit_{t−4} − Credit_{t−8}` (lcu) | column |
| `state` | `Literal` | `"accelerating"` \| `"decelerating"` \| `"neutral"` \| `"contracting"` | column |
| `components_json` | `str` (JSON) | — | column |
| `lookback_years` | `int` | rolling z-score window | column |
| `confidence` | `float` | 0-1 | column |
| `flags` | `str` (CSV) | — | column |

**Canonical components_json shape**:

```json
{
  "credit_t_lcu": 4.532e11,
  "credit_t_minus_4_lcu": 4.412e11,
  "credit_t_minus_8_lcu": 4.310e11,
  "gdp_t_minus_4_lcu": 5.320e10,
  "flow_recent_lcu": 1.20e10,
  "flow_prior_lcu": 1.02e10,
  "delta_flow_lcu": 1.80e9,
  "impulse_pp": 3.38,
  "smoothing": "ma4",
  "segment": "PNFS",
  "series_variant": "Q",
  "rolling_mean_20y_pp": 0.40,
  "rolling_std_20y_pp": 1.85
}
```

## 4. Algorithm

> **Units**: `score_raw` e `impulse_pp` em **percentage points of GDP** (e.g. `+1.8`). Internally LCU stays decimal floats. Z-score decimal. Display layer adiciona `+`/`−` explicit. Full rules em [`conventions/units.md`](../../conventions/units.md).

**Formula** (Biggs-Mayer-Pick 2010, 4Q smoothing variant):

```text
CI_t = [(Credit_t − Credit_{t−4}) − (Credit_{t−4} − Credit_{t−8})] / GDP_{t−4} × 100
     = (Δ_4 Credit_t − Δ_4 Credit_{t−4}) / GDP_{t−4} × 100
     = Δ²_4 Credit_t / GDP_{t−4} × 100
```

**Pseudocode** (deterministic):

1. Resolve `series_variant` — read from L1 row at `(country_code, date)`; if no L1 row, fallback `"Q"` and flag `L1_VARIANT_MISMATCH`.
2. Load `credit_stock_lcu[date]`, `credit_stock_lcu[date − 4Q]`, `credit_stock_lcu[date − 8Q]`, `gdp_nominal_lcu[date − 4Q]`.
3. Validate: all > 0, no NaN. If any missing → raise `InsufficientDataError`.
4. Compute `flow_recent = credit_t − credit_{t−4}`, `flow_prior = credit_{t−4} − credit_{t−8}`, `delta_flow = flow_recent − flow_prior`.
5. `impulse_pp = delta_flow / gdp_{t−4} × 100`.
6. If `smoothing == "ma4"`: also compute impulse for `date−1Q`, `date−2Q`, `date−3Q`; `impulse_pp = mean` of 4 quarters. Else raw single-quarter value.
7. `score_raw = impulse_pp`.
8. **Z-score normalization**: rolling 20Y of `impulse_pp` history → `μ`, `σ`; `score_normalized = (impulse_pp − μ) / σ` clamp `[−5, +5]`.
9. **State classification** (placeholder thresholds — recalibrate after 5Y of production data):
   - `impulse_pp > +0.5` AND derivative-of-impulse over last 2Q `> 0` → `"accelerating"`;
   - `impulse_pp > +0.5` AND derivative `< 0` → `"decelerating"` (warning: positive but slowing — early warning subtle);
   - `−0.5 ≤ impulse_pp ≤ +0.5` → `"neutral"`;
   - `impulse_pp < −0.5` → `"contracting"`.
10. Compute `confidence` per §6.
11. Persist row atomically.

## 5. Dependencies

| Package | Min version | Use |
|---|---|---|
| `numpy` | 1.26 | finite differences, z-score |
| `pandas` | 2.1 | quarterly resampling, rolling stats |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network calls.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| `< 12 obs` (3Y) — fórmula precisa de `t`, `t−4`, `t−8` | raise `InsufficientDataError` | n/a |
| `< 80 obs` (20Y) para z-score window | flag `INSUFFICIENT_HISTORY`; usar window disponível | −0.20 |
| `gdp_{t−4}` é zero ou negativo (data corruption) | raise `InvalidInputError` | n/a |
| Quarterly jump `|delta_flow / gdp| > 10pp` (write-off / re-classification) | persist; flag `IMPULSE_OUTLIER` | −0.20 |
| L1 variant Q used here mas L1 emitted F-fallback | inherit L1 flag; flag `L1_VARIANT_MISMATCH` | −0.10 |
| L1 inherited `CREDIT_BREAK` | inherit; impulse around break unstable; flag `STRUCTURAL_BREAK` | −0.20 |
| Connector last_fetched > 90 dias face a `date` | flag `STALE` | −0.20 |
| Country tier 4 (EM) | flag `EM_COVERAGE` | cap 0.70 |
| Calibração `state` thresholds expirou (>1Y) | flag `CALIBRATION_STALE` | −0.15 |
| `methodology_version` upstream ≠ runtime | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/l3-credit-impulse/`.

| Fixture | Input | Expected | Tolerance |
|---|---|---|---|
| `pt_2024_q4` | PT credit stock + GDP, smoothing="ma4", segment="PNFS" | `impulse_pp ≈ +0.6`, `state="accelerating"`, `score_normalized ≈ +0.10` | ±0.3pp, ±0.15 z |
| `pt_2009_q4` | PT trough — credit stagnation | `impulse_pp ≈ −1.2`, `state="contracting"` | ±0.5pp |
| `cn_2009_q2` | CN post-stimulus peak — Beijing "torneiras abertas" | `impulse_pp ≈ +12.0`, `state="accelerating"`, `flags="EM_COVERAGE"` | ±2pp |
| `cn_2016_q1` | CN secondary stimulus peak | `impulse_pp ≈ +8.0`, `state="accelerating"` | ±2pp |
| `us_2008_q4` | US Lehman quarter — flow inversion | `impulse_pp ≈ −3.5`, `state="contracting"` | ±1pp |
| `pt_decelerating_2007_q4` | PT 2007 — credit still positive but slowing | `impulse_pp ≈ +1.5`, derivative < 0 → `state="decelerating"` | ±0.5pp |
| `xx_short_history` | only 8 obs (2Y) | raises `InsufficientDataError` | n/a |
| `xx_outlier_synthetic` | engineered 12pp jump from write-off | `flags="IMPULSE_OUTLIER"`, persist | — |
| `pt_2024_segment_HH` | PT households segment only | separate row, segment="HH"; impulse different from PNFS | ±0.5pp |

## 8. Storage schema

```sql
CREATE TABLE credit_impulse (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,
    methodology_version      TEXT    NOT NULL,                  -- 'L3_CREDIT_IMPULSE_v0.1'
    segment                  TEXT    NOT NULL CHECK (segment IN ('PNFS','HH','NFC')),
    score_normalized         REAL    NOT NULL,                  -- z-score
    score_raw                REAL    NOT NULL,                  -- impulse in pp of GDP
    impulse_pp               REAL    NOT NULL,                  -- alias for score_raw
    flow_t_lcu               REAL    NOT NULL,                  -- Credit_t − Credit_{t−4}
    flow_t_minus4_lcu        REAL    NOT NULL,                  -- Credit_{t−4} − Credit_{t−8}
    delta_flow_lcu           REAL    NOT NULL,
    gdp_t_minus4_lcu         REAL    NOT NULL,
    series_variant           TEXT    NOT NULL CHECK (series_variant IN ('Q','F')),
    smoothing                TEXT    NOT NULL CHECK (smoothing IN ('raw','ma4')),
    state                    TEXT    NOT NULL,                  -- 'accelerating'|'decelerating'|'neutral'|'contracting'
    components_json          TEXT    NOT NULL,
    lookback_years           INTEGER NOT NULL,
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    source_connector         TEXT    NOT NULL,                  -- 'bis_ws_tc'
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version, segment)
);
CREATE INDEX idx_l3_ci_cd ON credit_impulse (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/credit-cccs` | L4 | `score_normalized` (segment="PNFS") → FM sub-index dominant component (50% within FM); `state` → 2D classifier flow-axis input |
| `cycles/credit-cccs` (classifier) | L4 | `impulse_pp > 0 for last 2Q` → FLOW POSITIVE; `< 0 for last 2Q` → FLOW NEGATIVE |
| `indices/economic/E2-leading` | L3 | `score_normalized` como leading indicator de GDP growth (lead 2-4Q) |
| `outputs/editorial` | L7 | CN segment `state="accelerating"` dispara coverage "credit impulse chinês antecipa global reflation" |
| `integration/diagnostics/global-financial-cycle` | L6 | aggregate impulse (US + EA + CN GDP-weighted) → global credit impulse |

## 10. Reference

- **Methodology**: [`docs/reference/indices/credit/L3-credit-impulse.md`](../../../reference/indices/credit/L3-credit-impulse.md) — Manual Cap 9.
- **Data sources**: [`docs/data_sources/credit.md`](../../../data_sources/credit.md) § Camada 1.1 (BIS `WS_TC`) + § 6.1 (Eurostat `namq_10_gdp`); [`data_sources/D2_empirical_validation.md`](../../../data_sources/D2_empirical_validation.md) §4 BIS WS_TC dependency + §6 Eurostat GDP fresh.
- **Architecture**: [`adr/ADR-0005-country-tiers-classification.md`](../../../adr/ADR-0005-country-tiers-classification.md) (L3 scope follows L1 inheritance; tier-4 degraded).
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §3 (BIS CC-BY-4.0 + Eurostat CC-BY-4.0).
- **Backlog**: `CAL-019` (BIS WS_TC key pending) afecta L3 via credit_stock_lcu input.
- **Papers**:
  - Biggs M., Mayer T., Pick A. (2010), "Credit and Economic Recovery: Demystifying Phoenix Miracles", DNB WP 218.
  - Mian A., Sufi A. (2018), "Credit Supply and Housing Speculation", NBER WP 24823 (segment breakdown rationale).
- **Cross-validation**: BIS does NOT publish credit impulse directly; cross-check vs DB Research / Goldman Sachs published series for US, EA, CN where available; tolerance ≤ 0.5pp.

## 11. Non-requirements

- Does **not** apply HP filter — purely 2nd derivative; trend-cycle decomposition is L2's job.
- Does **not** classify cycle phase — emits state (acceleration direction); phase requires stock × flow joint, lives em `cycles/credit-cccs`.
- Does **not** publish a real *future* GDP forecast despite the lead — leading-indicator signal lives em `indices/economic/E2-leading` consumer.
- Does **not** disaggregate by lender type (banks vs non-banks vs bond issuance) — sub-aggregates em `indices/credit/extended/` (Phase 2+).
- Does **not** smooth across the segment boundary (PNFS = HH + NFC) — emits separate rows per segment, downstream may aggregate.
- Does **not** consume L2 output — by design L3 is independent of HP gap to avoid circular signals (gap up → impulse up → gap up further).
- Does **not** estimate the *level* of credit flow — only the second derivative; flow level lives em L1 components.
- Does **not** emit alerts directly — `state="decelerating"` is informational; alerting lives em `cycles/credit-cccs` and `outputs/editorial`.
