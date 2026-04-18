# M1 — Effective Rates & Shadow Rates — Spec

> Layer L3 · index · cycle: monetary · slug: `m1-effective-rates` · methodology_version: `M1_EFFECTIVE_RATES_v0.1`

## 1. Purpose

Mede o **stance monetário absoluto atual** por país via uma única métrica nominal-equivalente: shadow rate (Wu-Xia / Krippner) que internaliza policy rate + QE/QT + forward guidance, convertida para real e comparada com `r*`. Foundation sub-índice do MSC (mapeia ao sub-index ES — Effective Stance — Cap 15.5).

## 2. Inputs

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `policy_rate_pct` | `float` (decimal) | `[-0.02, 0.30]` | `connectors/fred` (US `DFEDTAR*`/`EFFR`), `connectors/ecb_sdw` (DFR), `connectors/boe_database` (Bank Rate), `connectors/boj` (BoJ), `connectors/bis_cbpol` (fallback) |
| `shadow_rate_pct` | `float` (decimal) | `[-0.10, 0.10]`; opcional (live só durante ZLB) | `connectors/krippner` (US/EA/UK/JP/CA/AU/NZ live), `connectors/wu_xia_atlanta` (US histórico ≤ 2022) |
| `nss_short_end_pct` | `float` (decimal) | `yield_curves_spot.fitted_yields_json["3M"]`; `confidence ≥ 0.50` | `overlays/nss-curves` |
| `expected_inflation_pct` | `float` (decimal) | `5Y` decimal de `expected_inflation_tenors_json` | `overlays/expected-inflation` (canonical) |
| `r_star_pct` | `float` (decimal) | HLW estimate (US/EA/UK/CA), proxy para outros | `connectors/laubach_williams` (NY Fed quarterly) |
| `balance_sheet_pct_gdp_yoy` | `float` (decimal) | YoY change em assets / GDP | `connectors/fred` (`WALCL`), `ecb_sdw` (`ILM`), `boe_database`, `boj` |
| `country_code` | `str` | ISO 3166-1 α-2 upper; `EA` permitido | config |
| `date` | `date` | business day local | param |

### Preconditions

- `overlays/nss-curves` row para `(country, date)` com `confidence ≥ 0.50` ou raise `InsufficientDataError`.
- `overlays/expected-inflation` canonical row para `(country, date)` com `5Y` tenor não-`NULL` (else flag `OVERLAY_MISS` + degrade real-rate confidence).
- `r_star_pct` quarterly fetch ≤ 95 dias; senão flag `CALIBRATION_STALE`.
- Para Portugal (`country_code='PT'`): policy rate = ECB DFR (no national rate); `r_star` = EA HLW + 0 bps (proxy, Cap 7.5 workaround 1); flag `R_STAR_PROXY`.
- Shadow rate live apenas no ZLB; fora do ZLB use `policy_rate_pct` como proxy (`shadow_rate_pct = policy_rate_pct`); diferença material (> 25 bps) com Krippner SSR registada como diagnostic.
- `methodology_version` dos overlays consumidos bate com runtime ou raise `VersionMismatchError`.

## 3. Outputs

Uma row per `(country_code, date)` em `monetary_m1_effective_rates`.

| Nome | Tipo | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | z-score → `[0, 100]` (higher = tighter) | `monetary_m1_effective_rates.score_normalized` |
| `score_raw` | `float` | pp (M1_stance_vs_neutral, ex: `0.0185` = +185 bps tight) | `score_raw` |
| `policy_rate_pct` | `float` | decimal | enrichment column |
| `shadow_rate_pct` | `float` | decimal | enrichment column |
| `real_rate_pct` | `float` | decimal | enrichment column (`shadow − E[π]_5Y`) |
| `r_star_pct` | `float` | decimal | enrichment column |
| `components_json` | `str (JSON)` | — | breakdown ES sub-components |
| `lookback_years` | `int` | years | persisted (default 30) |
| `confidence` | `float` | 0-1 | per `units.md` |
| `flags` | `str (CSV)` | — | per `flags.md` |
| `methodology_version` | `str` | — | `M1_EFFECTIVE_RATES_v0.1` |

**Canonical JSON shape** (`components_json`):

```json
{
  "real_shadow_rate_pct": 0.0185,
  "shadow_rate_minus_rstar_pct": 0.0100,
  "balance_sheet_pct_gdp_yoy": -0.0420,
  "es_subscore_real_shadow": 62.0,
  "es_subscore_rstar_gap": 58.0,
  "es_subscore_balance_sheet": 65.0,
  "weights": {"real_shadow": 0.50, "rstar_gap": 0.35, "balance_sheet": 0.15}
}
```

## 4. Algorithm

> **Units**: rates em decimal storage/compute (ex `0.0425`); display layer converte para %. `score_normalized` é float `[0,100]`. `score_raw` em pp decimal. Regras em [`conventions/units.md`](../../conventions/units.md).

**Formula**:

```text
real_shadow_rate     = shadow_rate − E[π_5Y]
stance_vs_neutral    = real_shadow_rate − r*                      # Cap 7.7
balance_sheet_signal = − Δ(BS_to_GDP, 12m)                         # contraction → positive (tight)

ES_raw = 0.50 · z(real_shadow_rate)
       + 0.35 · z(stance_vs_neutral)
       + 0.15 · z(balance_sheet_signal)

score_normalized = clip(50 + 16.67 · ES_raw, 0, 100)              # 3σ ≈ ±50
score_raw        = stance_vs_neutral                                # natural unit (pp)
```

`z(x)` = z-score sobre rolling window 30 anos do mesmo país (default; ver §6 fallback).

**Pseudocode** (deterministic):

1. Load `policy_rate_pct` from primary connector for `(country_code, date)`.
2. Resolve `shadow_rate_pct`: `connectors/krippner` se disponível para `(country, date)` AND `policy_rate_pct ≤ 0.005` (ZLB regime); else `shadow_rate_pct = policy_rate_pct`.
3. Lookup `expected_inflation_pct = expected_inflation_canonical.expected_inflation_tenors_json["5Y"]`.
4. Compute `real_shadow_rate = shadow_rate_pct − expected_inflation_pct`.
5. Lookup `r_star_pct` (HLW most-recent ≤ 95 dias). For PT: `r_star_PT = r_star_EA`; emit flag `R_STAR_PROXY`.
6. Compute `stance_vs_neutral = real_shadow_rate − r_star_pct` (`score_raw`).
7. Compute `balance_sheet_signal = − (BS/GDP_t − BS/GDP_{t-12m})`.
8. Compute z-score de cada componente sobre window de `lookback_years = 30` anos do próprio país (cobre ZLB regime + pre-2008).
9. Aggregate ES_raw (Cap 15.5 ES weights: 50/35/15).
10. Map z → `[0, 100]` via `clip(50 + 16.67·z, 0, 100)`.
11. Compute `confidence` via §6 matrix; inherit upstream flags.
12. Persist row em §8 schema.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | rolling z-score, arrays |
| `pandas` | 2.1 | timeseries i/o, rolling windows |
| `scipy` | 1.11 | optional KalmanFilter (replicar Wu-Xia se quiser fit local) |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network — inputs pre-fetched via overlays + connectors L0/L1.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md). Propagação conforme § "Convenção de propagação".

| Trigger | Handling | Confidence |
|---|---|---|
| `nss-curves` missing / `confidence < 0.50` | raise `InsufficientDataError` | n/a |
| `expected-inflation` canonical missing | use `inflation_yoy` proxy + flag `OVERLAY_MISS` | cap 0.60 |
| `r_star` quarterly fetch > 95 dias | use most-recent + flag `CALIBRATION_STALE` | −0.15 |
| `shadow_rate_pct` (Krippner) age > 35 dias durante ZLB | use cache + flag `STALE` | −0.20 |
| Krippner vs policy rate diverge > 25 bps em regime non-ZLB | flag `SHADOW_DIVERGE` (proposed) — emit policy rate, log diagnostic | −0.05 |
| Country sem HLW r* (PT, IE, NL, ...) | use EA proxy + flag `R_STAR_PROXY` (proposed) | cap 0.75 |
| Country tier 4 (CN, IN, BR, TR, MX) | r* = fixed 1.5% real proxy; flag `EM_COVERAGE` | cap 0.60 |
| `lookback_years` < 30 disponível | use `min(available, 20)`; flag `INSUFFICIENT_HISTORY` (proposed) | cap 0.70 |
| Balance sheet data missing (BoJ delayed) | drop BS component; reweight `[0.55/0.45/0]`; flag `OVERLAY_MISS` | −0.10 |
| Stored upstream `methodology_version` ≠ runtime | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored em `tests/fixtures/m1-effective-rates/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2026_04_17` | DFEDTAR=4.375%, E[π_5Y]=0.0240, r*=0.0085, BS YoY=−4.2% | `score_raw≈0.0100`, `score_normalized≈62`, classification `Neutral-Tight` (placeholder — recalibrate after Nm) | ±5 bps raw, ±5 norm |
| `us_zlb_2014_05` | DFEDTAR=0.001, Wu-Xia SSR=−0.0299, E[π_5Y]=0.0220, r*=0.0050 | `real_shadow≈−0.0519`, `stance_vs_neutral≈−0.0569`, `score_normalized<25` (Strongly Accommodative) | ±10 bps |
| `ea_2026_04_17` | DFR=2.0%, E[π_5Y]=0.0210, EA r*=0.0020, BS YoY=−6% | `score_raw≈−0.0050`, `score_normalized≈48` | ±5 bps |
| `pt_2026_04_17` | DFR=2.0%, PT 5Y BEI=0.0215, r*_EA=0.0020 (proxy) | inherits EA; flag `R_STAR_PROXY`; `confidence≤0.75` | — |
| `jp_2024_03_15` | BoJ exit YCC; policy=0.001 → 0.005, BS=125% GDP | `score_normalized<35` (Accommodative, normalizing) | — |
| `r_star_stale_120d` | HLW age = 120 dias | flag `CALIBRATION_STALE`; `confidence ≤ 0.85` | — |
| `insufficient_history_pt_15y` | PT data 15Y only | flag `INSUFFICIENT_HISTORY`; window=15Y; `confidence ≤ 0.70` | — |

## 8. Storage schema

```sql
CREATE TABLE monetary_m1_effective_rates (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code          TEXT    NOT NULL,
    date                  DATE    NOT NULL,
    methodology_version   TEXT    NOT NULL,                -- 'M1_EFFECTIVE_RATES_v0.1'
    score_normalized      REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw             REAL    NOT NULL,                -- pp (decimal); stance_vs_neutral
    policy_rate_pct       REAL    NOT NULL,                -- decimal
    shadow_rate_pct       REAL    NOT NULL,                -- decimal; = policy_rate fora do ZLB
    real_rate_pct         REAL    NOT NULL,                -- decimal; shadow − E[π_5Y]
    r_star_pct            REAL    NOT NULL,                -- decimal
    components_json       TEXT    NOT NULL,                -- ES sub-components + weights
    lookback_years        INTEGER NOT NULL,                -- default 30
    confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                 TEXT,                            -- CSV ordem lexicográfica
    source_connector      TEXT    NOT NULL,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_m1_cd ON monetary_m1_effective_rates (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/monetary-msc` | L4 | `score_normalized` (peso ~30% MSC; mapeia ES) |
| `integration/matriz-4way` | L6 | stance contribution para classification monetary × credit |
| `outputs/editorial` | L7 | `score_raw` em pp + classification ("Tight/Neutral/Accommodative") |

## 10. Reference

- **Methodology**: [`docs/reference/indices/monetary/M1-effective-rates.md`](../../../reference/indices/monetary/M1-effective-rates.md) — Manual Cap 7 (Effective rates & shadow rates).
- **Composite design**: [`docs/reference/cycles/monetary.md`](../../../reference/cycles/monetary.md) Cap 15.5 (Sub-index ES weights 50/35/15) + Cap 15.6 (MSC weights).
- **Data sources**: [`docs/data_sources/monetary.md`](../../../data_sources/monetary.md) §1 (Shadow rates) + §1.4 (HLW r*) + §6 (balance sheets).
- **Papers**:
  - Wu J. C., Xia F. D. (2016), "Measuring the Macroeconomic Impact of Monetary Policy at the Zero Lower Bound", *JMCB* 48(2-3).
  - Krippner L. (2015), *Zero Lower Bound Term Structure Modeling*, Palgrave.
  - Holston K., Laubach T., Williams J. C. (2017), "Measuring the Natural Rate of Interest: International Trends and Determinants", *JIE* 108.
- **Cross-validation**: Atlanta Fed `WXSRUS` (US monthly, suspenso ≥ Apr 2022); Krippner `ljkmfa.com` (live 7 BCs); HLW NY Fed (quarterly).

## 11. Non-requirements

- Does not refit Wu-Xia / Krippner SRTSM internally — consome Krippner / Wu-Xia diretamente como connectors L0; replicar fit é spec futura `connectors/wu_xia_replication`.
- Does not derive `r*` — leitura directa de NY Fed HLW; estimação própria é spec futura `overlays/r-star-derived`.
- Does not classify Dilemma — flag computed em `cycles/monetary-msc` (Cap 16) com inputs M1 + CCCS + inflation + FX.
- Does not emit intra-day — daily EOD batch; rate decisions tracked separately em `policy_decisions` table.
- Does not cover `policy surprise` measurement — pertence a M3 (`overlays/policy-surprise` futuro).
- Does not handle EA-aggregate vs national breakdown beyond PT proxy — IT/ES periphery seguem mesma lógica EA-anchor + spread (futuro).
- Does not substitute BC official communication ("hawkish dot plot") — quantitative-only; communication scoring é spec futura `connectors/communication-nlp`.
- Does not auto-detect ZLB regime — operator define `zlb_threshold_pct = 0.005` em config; switch rule em §4 step 2.
