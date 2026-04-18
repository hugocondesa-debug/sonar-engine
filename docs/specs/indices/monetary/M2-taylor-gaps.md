# M2 — Taylor Rule Gaps — Spec

> Layer L3 · index · cycle: monetary · slug: `m2-taylor-gaps` · methodology_version: `M2_TAYLOR_GAPS_v0.1`

## 1. Purpose

Mede a **divergência da policy rate face a benchmarks rule-based**. Computa quatro variantes Taylor (1993, 1999, with-inertia, forward-looking), expõe `actual − prescribed` em pp, e agrega via median/range para sinalizar consistência (ou divergência) com framework convencional. Mapeia ao sub-index RD (Rule Deviation — Cap 15.5).

## 2. Inputs

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `policy_rate_pct` | `float` (decimal) | `[-0.02, 0.30]` | mesmo input que M1 (`fred`/`ecb_sdw`/`boe_database`/`boj`/`bis_cbpol`) |
| `inflation_yoy_pct` | `float` (decimal) | core inflation YoY | `connectors/fred` (US `PCEPILFE`), `connectors/eurostat` (`prc_hicp_manr` ex-energy-food), `connectors/ons_uk`, `connectors/estat_japan` |
| `inflation_target_pct` | `float` (decimal) | per BC fixed (config `bc_targets.yaml`) | config |
| `inflation_forecast_h` | `float` (decimal) | survey/SPF projection at h=4-8 quarters; from `overlays/expected-inflation` `2Y` tenor | `overlays/expected-inflation` |
| `output_gap_pct` | `float` (decimal) | `[-0.15, 0.15]`; primary IMF WEO | `connectors/imf_weo` (semi-anual), `connectors/oecd_eo`, `connectors/cbo` (US) |
| `output_gap_xcheck_pct` | `float` (decimal) | secondary source for divergence flag | `connectors/oecd_eo` / `connectors/ameco` |
| `r_star_pct` | `float` (decimal) | shared with M1; HLW or fallback | `connectors/laubach_williams` |
| `prev_period_policy_rate_pct` | `float` (decimal) | for inertia variant; previous month observation | own table lag |
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | business day local | param |

### Preconditions

- `r_star_pct` quarterly fetch ≤ 95 dias; senão flag `CALIBRATION_STALE`. PT/IE/NL → EA r* proxy + flag `R_STAR_PROXY`.
- `output_gap_pct` semi-anual; cobertura: stale acceptável até 200 dias; senão flag `STALE`.
- Para `inflation_target_pct`: `bc_targets.yaml` retorna 0.02 (Fed/ECB/BoE/BoJ/BoC), 0.025 (RBA midpoint), 0.03 (BCB/Banxico), 0.04 (RBI midpoint); CN/TR/AR não têm target operativo → emite só Taylor 1993 com π* = 0.02 sandbox + flag `NO_TARGET`.
- `inflation_forecast_h` (forward-looking variant) requer `expected_inflation_canonical.expected_inflation_tenors_json["2Y"]` não-NULL; senão skip variant + flag `OVERLAY_MISS`.
- `prev_period_policy_rate_pct` (inertia variant) requer ≥1 obs anterior em `monetary_m2_taylor_gaps`; senão skip variant para primeira data.
- ≥ 2 das 4 variantes computadas; senão raise `InsufficientDataError`.
- `methodology_version` dos overlays consumidos bate com runtime ou raise `VersionMismatchError`.

## 3. Outputs

Uma row per `(country_code, date)` em `monetary_m2_taylor_gaps`.

| Nome | Tipo | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | z-score → `[0, 100]` (higher = tighter vs rule) | column |
| `score_raw` | `float` | pp (`actual − taylor_implied`); positivo = tighter | column |
| `taylor_implied_pct` | `float` | decimal (median dos 4 variantes) | column |
| `taylor_gap_pp` | `float` | pp decimal (alias de `score_raw`) | column |
| `taylor_uncertainty_pp` | `float` | range entre variantes (max − min) | column |
| `r_star_source` | `str` | enum `{HLW, HOLSTON_LAUBACH_WILLIAMS, FIXED_2PCT, EA_PROXY}` | column |
| `output_gap_source` | `str` | enum `{IMF_WEO, OECD, CBO, AMECO}` | column |
| `components_json` | `str (JSON)` | per-variant prescribed + gap | column |
| `lookback_years` | `int` | years (default 30) | column |
| `confidence` | `float` | 0-1 | column |
| `flags` | `str (CSV)` | — | column |
| `methodology_version` | `str` | — | column |

**Canonical JSON shape** (`components_json`):

```json
{
  "taylor_1993_prescribed_pct": 0.040,
  "taylor_1993_gap_pp": 0.00375,
  "taylor_1999_prescribed_pct": 0.0425,
  "taylor_1999_gap_pp": 0.00125,
  "taylor_inertia_prescribed_pct": 0.0420,
  "taylor_inertia_gap_pp": 0.00175,
  "taylor_forward_prescribed_pct": 0.038,
  "taylor_forward_gap_pp": 0.00575,
  "median_gap_pp": 0.00275,
  "range_pp": 0.0045,
  "weights_in_RD": {"t1993": 0.30, "t1999": 0.25, "tforward": 0.30, "tinertia": 0.15}
}
```

## 4. Algorithm

> **Units**: rates em decimal storage/compute (ex `0.0438`); gaps em pp decimal (ex `+0.00375` = +37.5 bps). Display layer converte. `score_normalized` é `[0, 100]` float. Regras em [`conventions/units.md`](../../conventions/units.md).

**Formula** (canonical Taylor 1993 + variantes):

```text
T1993:   i* = r* + π + 0.5·(π − π*)            + 0.5·(y − y*)
T1999:   i* = r* + π + 0.5·(π − π*)            + 1.0·(y − y*)
Tinertia: i* = ρ · i_{t−1} + (1−ρ) · T1993       , ρ = 0.85 (placeholder — recalibrate after Nm)
Tforward: i* = r* + π_h + 0.5·(π_h − π*)        + 0.5·(y − y*)         , h = 6 quarters

gap_v = policy_rate − i*_v          for v ∈ {1993, 1999, inertia, forward}
median_gap = median(gap_v)           # = score_raw
range_gap  = max(gap_v) − min(gap_v)

# Aggregate to RD sub-index per Cap 15.5 weights
RD_raw = 0.30·z(gap_1993) + 0.25·z(gap_1999) + 0.30·z(gap_forward) + 0.15·z(gap_inertia)
score_normalized = clip(50 + 16.67 · RD_raw, 0, 100)
```

`z(x)` = z-score sobre rolling window 30 anos do mesmo país (ver §6 fallback).

**Pseudocode** (deterministic):

1. Load `policy_rate_pct`, `inflation_yoy_pct`, `output_gap_pct`, `r_star_pct` for `(country_code, date)`.
2. Resolve `inflation_target_pct` from `config/bc_targets.yaml`. Skip + flag `NO_TARGET` para CN/TR/AR.
3. Cross-check output gap: if `|imf_weo − oecd| > 0.01` (1pp) → flag `OUTPUT_GAP_DIVERGE` (proposed); use IMF as primary.
4. Compute `T1993_prescribed = r* + π + 0.5·(π − π*) + 0.5·(y − y*)`.
5. Compute `T1999_prescribed = r* + π + 0.5·(π − π*) + 1.0·(y − y*)`.
6. Compute `Tinertia_prescribed = 0.85·prev_policy_rate + 0.15·T1993_prescribed`.
7. Compute `Tforward_prescribed = r* + π_h + 0.5·(π_h − π*) + 0.5·(y − y*)`, com `π_h = expected_inflation_canonical["2Y"]`.
8. For each available variant, `gap_v = policy_rate − T_v`.
9. `median_gap_pp = np.median(available_gaps)`; `range_pp = max − min`.
10. Compute z-score de cada gap_v sobre 30Y window do mesmo país.
11. Aggregate via Cap 15.5 weights → `RD_raw` → `score_normalized`.
12. If `range_pp > 0.01` (1pp) → flag `TAYLOR_VARIANT_DIVERGE` (proposed); interpretation: "regime transition" per Cap 8.9.
13. Persist row em §8 schema.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | median, z-score, range |
| `pandas` | 2.1 | timeseries i/o, lag for inertia |
| `pyyaml` | 6.0 | `bc_targets.yaml` config load |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network — inputs pre-fetched.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| `output_gap_pct` missing OR > 200 dias stale | drop dependency; variantes skip se requerem; flag `STALE` | −0.20 |
| `|imf_weo − oecd_output_gap| > 1pp` | flag `OUTPUT_GAP_DIVERGE` (proposed); use IMF + log range | −0.10 |
| `r_star` quarterly age > 95 dias | use most-recent + flag `CALIBRATION_STALE` | −0.15 |
| `r_star` indisponível para país | fallback `FIXED_2PCT` (Taylor original 2% real); flag `R_STAR_PROXY` | cap 0.65 |
| `inflation_forecast_h` missing | skip Tforward variant; flag `OVERLAY_MISS`; reweight RD | −0.10 |
| `prev_policy_rate` missing (cold-start) | skip Tinertia; reweight | −0.05 |
| `range_pp > 0.01` (1pp entre variantes) | flag `TAYLOR_VARIANT_DIVERGE` (proposed) — "regime transition" warning | −0.10 |
| `< 2` variantes computadas | raise `InsufficientDataError` | n/a |
| ZLB era (policy_rate ≈ 0 + Taylor prescribes negative) | accept negative `T_prescribed`; computa gap normalmente; flag `ZLB_REGIME` (proposed) | −0.05 |
| Country sem operative target (CN/TR/AR) | use π* = 0.02 sandbox; flag `NO_TARGET` | cap 0.50 |
| Country tier 4 | wider z-score window (use `min(available, 15)`) + cap | cap 0.60 |
| `lookback_years < 20` | flag `INSUFFICIENT_HISTORY` (proposed) | cap 0.70 |
| Stored upstream `methodology_version` ≠ runtime | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored em `tests/fixtures/m2-taylor-gaps/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2026_04_17` | policy=0.04375, π_core=0.026, π*=0.02, y−y*=+0.005, r*=0.0085, π_h=0.024 | `T1993≈0.040`, `gap_1993≈+0.00375`, `median≈+0.00275`, `score_norm≈54` | ±5 bps gap; ±5 score |
| `us_2003_06` (Greenspan loose era) | policy=0.01, π=0.022, y−y*=+0.005, r*=0.02 | `T1993≈0.0381`, `gap≈−0.0281` (substantially looser than rule); `score_norm≈25` | ±10 bps |
| `us_2022_06` (Fed catch-up era) | policy=0.0163, π_core=0.048, y−y*=+0.01, r*=0.005 | gap negativo grande (~ −0.035); flag `TAYLOR_VARIANT_DIVERGE` se range>1pp | — |
| `ea_2026_04_17` | DFR=0.02, π_core=0.022, π*=0.02, y=−0.003, r*=0.002 | `T1993≈0.0231`, `gap≈−0.0031` | ±5 bps |
| `pt_2026_04_17` | DFR=0.02, π_core_PT=0.025, EA r*=0.002, EA y=−0.003 | inherits EA prescribed; flag `R_STAR_PROXY`; `confidence ≤ 0.75` | — |
| `output_gap_diverge_us_2024` | IMF=+0.005, OECD=−0.012 | flag `OUTPUT_GAP_DIVERGE`; primary IMF | — |
| `cn_no_target` | policy=0.034, π=0.02 | flag `NO_TARGET`; `confidence ≤ 0.50` | — |
| `cold_start_no_inertia` | first row for country | skip Tinertia; ≥ 3 variantes; persist | — |
| `r_star_proxy_fixed` | country sem HLW | fallback `FIXED_2PCT`; flag `R_STAR_PROXY` | cap 0.65 |

## 8. Storage schema

```sql
CREATE TABLE monetary_m2_taylor_gaps (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,
    methodology_version      TEXT    NOT NULL,            -- 'M2_TAYLOR_GAPS_v0.1'
    score_normalized         REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw                REAL    NOT NULL,            -- pp (decimal); median gap
    taylor_implied_pct       REAL    NOT NULL,            -- decimal; median prescribed
    taylor_gap_pp            REAL    NOT NULL,            -- pp; alias score_raw
    taylor_uncertainty_pp    REAL    NOT NULL,            -- range max−min entre variantes
    variants_available       INTEGER NOT NULL CHECK (variants_available BETWEEN 1 AND 4),
    r_star_source            TEXT    NOT NULL,            -- 'HLW' | 'HOLSTON_LAUBACH_WILLIAMS' | 'FIXED_2PCT' | 'EA_PROXY'
    output_gap_source        TEXT    NOT NULL,            -- 'IMF_WEO' | 'OECD' | 'CBO' | 'AMECO'
    components_json          TEXT    NOT NULL,            -- per-variant prescribed + gap
    lookback_years           INTEGER NOT NULL,
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    source_connector         TEXT    NOT NULL,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_m2_cd ON monetary_m2_taylor_gaps (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/monetary-msc` | L4 | `score_normalized` (peso ~15% MSC; mapeia RD) |
| `outputs/editorial` | L7 | `taylor_gap_pp` + `taylor_uncertainty_pp` ("Fed 37.5 bps tighter than Taylor 1993") |
| `integration/diagnostics/regime-shift` | L6 | `range_pp > 1pp` como warning de regime transition |

## 10. Reference

- **Methodology**: [`docs/reference/indices/monetary/M2-taylor-gaps.md`](../../../reference/indices/monetary/M2-taylor-gaps.md) — Manual Cap 8 (Taylor Rule gaps).
- **Composite design**: [`docs/reference/cycles/monetary.md`](../../../reference/cycles/monetary.md) Cap 15.5 (Sub-index RD weights 30/25/30/15) + Cap 15.6 (MSC weights).
- **Data sources**: [`docs/data_sources/monetary.md`](../../../data_sources/monetary.md) §2 (Taylor Rule inputs) — IMF WEO, OECD, AMECO output gaps.
- **Papers**:
  - Taylor J. B. (1993), "Discretion versus Policy Rules in Practice", *CRCS* 39.
  - Taylor J. B. (1999), "A Historical Analysis of Monetary Policy Rules", *NBER WP 6768*.
  - Clarida R., Galí J., Gertler M. (2000), "Monetary Policy Rules and Macroeconomic Stability", *QJE* 115(1) — forward-looking variant.
  - Holston K., Laubach T., Williams J. C. (2017), "Measuring the Natural Rate of Interest", *JIE* 108.
- **Cross-validation**: Atlanta Fed *Taylor Rule Utility* (US monthly historical); Bundesbank Monthly Report Taylor estimates (EA periodically).

## 11. Non-requirements

- Does not estimate r* — leitura directa de NY Fed HLW (M1 também consome); estimação própria é spec futura `overlays/r-star-derived`.
- Does not estimate output gap — consome IMF WEO + OECD + CBO + AMECO via connectors L0; potential output computation é spec futura.
- Does not implement asymmetric Taylor (different α tight vs loose) — Cap 8.2 variant; spec futura `M2-taylor-asymmetric` se backtest justificar.
- Does not implement Taylor 2013 financial-augmented — requires FCI feedback loop com M4; spec futura `M2-taylor-fci-augmented`.
- Does not classify discretionary vs rule-based behavior beyond `range_pp` flag — qualitative judgment fica em editorial layer.
- Does not handle PBoC (multi-tool, multi-objective) — Cap 8.8: emit best-effort com flag `EM_COVERAGE`; PBoC reaction function spec separada.
- Does not auto-recalibrate ρ (inertia smoothing) per BC — fixed 0.85 placeholder; recalibrar via Phase 9 backtest.
- Does not emit pre-1990 fixtures — Greenspan-era datasets só desde ~1987; coverage limit em `lookback_years` automatic.
