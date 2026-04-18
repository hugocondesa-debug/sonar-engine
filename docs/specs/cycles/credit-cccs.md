# Credit Cycle Composite Score (CCCS) — Spec

> Layer L4 · cycles · slug: `credit-cccs` · methodology_version: `CCCS_COMPOSITE_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E3)

## 1. Purpose

Agregar os 4 sub-índices L3 de `indices/credit/` + cross-cycle inputs de `indices/financial/` num único **Credit Cycle Composite Score ∈ [0, 100]** por `(country_code, date)`, com classificação discreta de regime em 5 fases (REPAIR / RECOVERY / BOOM / SPECULATION / DISTRESS). Primary output do ciclo de crédito; consumido por `integration/matriz-4way` (L6), diagnostics Minsky (L6) e editorial (L7). Simplificação v0.1 do framework Cap 15 (5 sub-indices → 3; QS omitido, ver §11).

## 2. Inputs

### L3 credit inputs (intra-cycle)

| Name | Tipo | Constraints | Source |
|---|---|---|---|
| `l1_row` | `Row(credit_to_gdp_stock)` | `score_normalized` ∈ `[-5,+5]`; `methodology_version="L1_CREDIT_GDP_STOCK_v0.1"` | `indices/credit/L1-credit-to-gdp-stock` |
| `l2_row` | `Row(credit_to_gdp_gap)` | `score_normalized`, `gap_hp_pp`, `phase_band`; version `L2_CREDIT_GDP_GAP_v0.1` | `indices/credit/L2-credit-to-gdp-gap` |
| `l3_row` | `Row(credit_impulse[segment="PNFS"])` | `score_normalized`, `impulse_pp`, `state`; version `L3_CREDIT_IMPULSE_v0.1` | `indices/credit/L3-credit-impulse` |
| `l4_row` | `Row(dsr[segment="PNFS"])` | `score_normalized`, `dsr_deviation_pp`, `band`; version `L4_DSR_v0.1` | `indices/credit/L4-dsr` |

### Cross-cycle inputs (financial cycle)

| Name | Tipo | Constraints | Source |
|---|---|---|---|
| `f3_row` | `Row(f3_risk_appetite)` | `score_normalized ∈ [0,100]`; version `F3_RISK_APPETITE_v0.1` | `indices/financial/F3-risk-appetite` |
| `f4_margin_debt_gdp_pct` | `float` | extraído de `f4_positioning.margin_debt_gdp_pct` column (NOT full F4 score) | `indices/financial/F4-positioning` |

> **Note on F4 extraction**: F4 expõe `margin_debt_gdp_pct` como top-level coluna em `f4_positioning` (tabela §8 de `F4-positioning.md`). v0.1 lê essa coluna directamente em vez de parsear `components_json`. Se `margin_debt_gdp_pct IS NULL` (non-US markets), flag `F4_MARGIN_MISSING` e MS cai para F3-only sub-component (100% F3) dentro de MS.

### Parameters (config)

- `min_core_components` = `3` (CS, LC, MS disponíveis em ≥3 para emitir CCCS canónico)
- `regime_transition_delta_min` = `5.0` (pontos de `score_0_100`)
- `regime_persistence_min_days` = `3` (business days — anti-whipsaw)
- `boom_overlay_l2_gap_threshold_pp` = `+10.0`
- `boom_overlay_l4_dsr_z_threshold` = `+1.5`
- `boom_overlay_score_threshold` = `70.0`
- `reweight_confidence_cap` = `0.75`
- `qs_absent_confidence_cap` = `0.90`

### Preconditions

Invariantes antes da invocação:

- `indices/credit/L1,L2,L3,L4` available com `methodology_version ∈ {L1_CREDIT_GDP_STOCK_v0.1, L2_CREDIT_GDP_GAP_v0.1, L3_CREDIT_IMPULSE_v0.1, L4_DSR_v0.1}` para `(country_code, date_quarter)`.
- `indices/financial/F3` available com `methodology_version="F3_RISK_APPETITE_v0.1"` para `(country_code, date)`.
- `indices/financial/F4` available para `(country_code, date)`; `components_json` parseado OU `margin_debt_gdp_pct` column lido directamente (preferred path).
- CCCS corre em **daily grid**; componentes quarterly (L1-L4) são forward-filled do último quarter-end ≤ `date` com freshness ≤ 1Q.
- `hp_filter_cache` table materializado para L2 (Policy 6) — CCCS NÃO re-executa HP (ver §11).
- Stored `methodology_version` upstream = runtime; senão `VersionMismatchError`.
- `min_core_components` satisfeito; senão raise `InsufficientDataError` (regra Policy 1).

## 3. Outputs

Uma row por `(country_code, date, methodology_version)` em `credit_cycle_scores`:

| Output | Tipo | Unit | Storage |
|---|---|---|---|
| `cccs_id` | `str (uuid4)` | — | column |
| `score_0_100` | `float` | pontos 0-100 | column |
| `regime` | `Literal` | `REPAIR`/`RECOVERY`/`BOOM`/`SPECULATION`/`DISTRESS` | column |
| `regime_persistence_days` | `int` | business days | column |
| `cs_score_0_100`, `lc_score_0_100`, `ms_score_0_100` | `float` | pontos 0-100 | column |
| `qs_score_0_100` | `NULL` (v0.1) | — | column |
| `cs_weight_effective`, `lc_weight_effective`, `ms_weight_effective` | `float` | pesos após re-weight | column |
| `components_available` | `int` | `3` ou `4` | column |
| `l1_contribution_pct`, `l2_contribution_pct`, `l3_contribution_pct`, `l4_contribution_pct` | `float` | audit % pre-QS | column |
| `f3_contribution_pct`, `f4_margin_debt_contribution_pct` | `float` | audit cross-cycle | column |
| `boom_overlay_active` | `bool (int 0/1)` | — | column |
| `boom_trigger_json` | `str (JSON)` | — | column |
| `confidence` | `float` | 0-1 | column |
| `flags` | `str (CSV)` | — | column |

**Canonical JSON shape**:

```json
{"country": "PT", "date": "2026-04-17", "cccs_id": "a1e…",
 "score_0_100": 38.4, "regime": "RECOVERY", "regime_persistence_days": 124,
 "components": {"CS": 31.0, "LC": 42.5, "MS": 45.1, "QS": null},
 "weights_effective": {"CS": 0.44, "LC": 0.33, "MS": 0.22},
 "contribution_pct": {"L1": 12, "L2": 22, "L3": 20, "L4": 13, "F3": 22, "F4_margin": 10},
 "boom_overlay_active": false, "confidence": 0.86, "flags": ["QS_PLACEHOLDER"]}
```

## 4. Algorithm

> **Units**: componentes internos em z-score (L3 `score_normalized`) → mapped para `[0, 100]` via min-max scaling `score_component = clip(50 + 16.67·z, 0, 100)` (consistente com F3/F4). CCCS final é `float [0, 100]`. Contribuições em `%` display. Thresholds de overlay em `pp` (gap) e z-score. Full rules em [`conventions/units.md`](../conventions/units.md).

### Composite formula (v0.1)

```text
CCCS = w_CS · CS + w_LC · LC + w_MS · MS      (QS omitted in v0.1)

Nominal weights (sum = 0.99, QS = 0.10 omitted and redistributed):
  w_CS = 0.44
  w_LC = 0.33
  w_MS = 0.22

Sub-components (each ∈ [0, 100] after z→pts mapping):
  CS = 0.30·pts(L1.z) + 0.50·pts(L2.z) + 0.20·pts(L4.z)
  LC = 0.60·pts(L3.z) + 0.40·pts(L4.z)
  MS = 0.70·F3.score_normalized + 0.30·pts(z_20Y(F4.margin_debt_gdp_pct))

where pts(z) = clip(50 + 16.67·z, 0, 100).
```

> **Design note — L4 double-use (CS ∩ LC)**: L4 DSR contribui simultaneamente para CS (peso 0.20 dentro de CS = efectivo 0.088 no CCCS) e para LC (peso 0.40 dentro de LC = efectivo 0.132 no CCCS). Total L4 footprint ≈ 22% do CCCS. Intencional — DSR informa tanto *stress level* (burden estrutural) como *lending conditions* (capacidade de servir dívida molda oferta/procura). Alternativa disjoint (CS=L1+L2, LC=L3+L4) rejeitada por atribuir L4 apenas a lending — subestima papel de burden em stress agregado per Cap 15 BP 30% dominance (AUC 0.82). Cap 15.6 weights (SS 25, BP 30, FM 15) ~= CS 44 + LC 33 aqui com L4 cross-weighting.

### Regime classification (Cap 16 phase scheme)

```text
REPAIR       : score_0_100 <  30
RECOVERY     : 30 ≤ score  <  50
BOOM         :  50 ≤ score <  70
SPECULATION  :  70 ≤ score ≤  85
DISTRESS     : score > 85  (post-downturn — informational; not a stock-flow phase)
```

### Anti-whipsaw hysteresis

```text
regime transition(t-1 → t) requires BOTH:
  (a) |score_t − score_{t-1}| > regime_transition_delta_min (= 5.0 pts)
  (b) new regime criterion satisfied for ≥ regime_persistence_min_days (= 3 BD)

Otherwise: regime_t = regime_{t-1}  (sticky).
regime_persistence_days increments on every BD where regime unchanged.
```

### Boom overlay (Cap 15/16 late-stage warning)

```text
boom_overlay_active = (
     score_0_100 > 70.0
 AND l2_row.gap_hp_pp > +10.0
 AND l4_row.score_normalized > +1.5       # DSR z-score elevated
)
```

`boom_trigger_json` materializa os três valores + thresholds para auditoria. L5 regimes table (`credit_regimes`) é Phase 2+; v0.1 apenas persiste o bool + JSON.

### Pipeline per `(country_code, date)`

1. Resolve L1-L4 rows via forward-fill from latest quarter-end ≤ `date` (freshness ≤ 1Q; else raise `StaleDataError` + `STALE` inherited).
2. Resolve F3 row (same `date`) + F4 `margin_debt_gdp_pct` column (same `date`). If F4 margin NULL → flag `F4_MARGIN_MISSING`; set MS = F3.score_normalized (100% F3 fallback).
3. Validate `min_core_components`: count available ∈ {CS, LC, MS} ≥ 3. If any single sub-component unavailable:
   - Re-weight restantes proporcionalmente; emit `{CS,LC,MS}_MISSING` flag.
   - Cap confidence ≤ `reweight_confidence_cap` (0.75).
   - If count < 3 → raise `InsufficientDataError`.
4. Map each L1-L4 `score_normalized` z-score → points via `pts(z)`.
5. Compute CS, LC, MS per formulas above (intra-sub-component weights).
6. Compute `score_0_100 = Σ w_i · subcomponent_i` (w effective, post-reweight).
7. Derive `*_contribution_pct` for L1..L4, F3, F4_margin for audit (sum ≈ 100%).
8. Classify regime via hysteresis: read previous `regime` + `regime_persistence_days` from `credit_cycle_scores` for `(country_code, date − 1 BD)`; apply transition rules §4.
9. Compute `boom_overlay_active` + `boom_trigger_json`.
10. Inherit flags from all 4 L3 credit rows + F3 + F4 (CSV union per `conventions/flags.md` § propagação). Append `QS_PLACEHOLDER` (always in v0.1).
11. Compute `confidence` per §6 matrix; cap per Policy 1 (re-weight) and Policy 2 (QS absent).
12. Persist row atomically with `cccs_id = uuid4()`, `methodology_version="CCCS_COMPOSITE_v0.1"`.

## 5. Dependencies

| Package | Min version | Use |
|---|---|---|
| `numpy` | 1.26 | arithmetic, clip, z-score |
| `pandas` | 2.1 | forward-fill quarterly → daily, rolling |
| `sqlalchemy` | 2.0 | read L1-L4, F3-F4 rows; persist `credit_cycle_scores` |
| `pydantic` | 2.6 | `boom_trigger_json`, `components_json` validation |
| `python-uuid` (stdlib) | — | `cccs_id` |

No network calls — all upstream rows come from SONAR tables (read-only).

## 6. Edge cases

Flags → [`conventions/flags.md`](../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../conventions/exceptions.md). Confidence propagation per `flags.md` § "Convenção de propagação".

| Trigger | Handling | Confidence |
|---|---|---|
| `components_available < 3` (of CS, LC, MS) | raise `InsufficientDataError` | n/a |
| CS unavailable (any of L1/L2/L4 missing AND CS uncomputable) | re-weight `w_LC, w_MS` proportionally; flag `CS_MISSING` | cap 0.75 |
| LC unavailable (L3 + L4 both missing) | re-weight; flag `LC_MISSING` | cap 0.75 |
| MS unavailable (F3 missing; F4 is optional sub-component) | re-weight; flag `MS_MISSING` | cap 0.75 |
| F4 `margin_debt_gdp_pct IS NULL` (non-US) | MS := F3.score_normalized (100%); flag `F4_MARGIN_MISSING` | −0.05 |
| QS omitted (always in v0.1) | `qs_score_0_100 = NULL`; flag `QS_PLACEHOLDER` | cap 0.90 |
| L2 `gap_hp_pp > +10pp` AND L4 z > +1.5 AND `score > 70` | `boom_overlay_active=1`; no confidence impact; flag `CCCS_BOOM_OVERLAY` | informational |
| Regime change attempted but Δscore ≤ 5 OR persistence < 3 BD | sticky — keep previous regime; flag `REGIME_HYSTERESIS_HOLD` | informational |
| Upstream component flagged `CREDIT_BREAK` or `STRUCTURAL_BREAK` | inherit + propagate | −0.20 (inherited) |
| Upstream component flagged `INSUFFICIENT_HISTORY` | inherit; cap propagates | cap 0.65 |
| Upstream component flagged `EM_COVERAGE` | inherit; cap propagates | cap 0.70 |
| Upstream component flagged `DSR_APPROX_O1` / `_O2` | inherit | −0.10 / −0.20 (inherited) |
| Upstream component flagged `HP_FAIL` or `HAMILTON_FAIL` | inherit; cap 0.50 propagates to CCCS | cap 0.50 |
| L1/L2/L3/L4 latest quarter-end > 1Q stale face a `date` | raise `StaleDataError`; do not persist | n/a |
| F3 missing for `(country, date)` | MS uncomputable → `MS_MISSING` path (above) | cap 0.75 |
| Stored row `methodology_version ≠` runtime | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/credit-cccs/`. Each fixture = `input_*.json` (upstream L1..L4 + F3 + F4 echoed) + `expected_*.json`.

| Fixture | Input | Expected | Tolerance |
|---|---|---|---|
| `pt_2026_q1` | PT snapshot Cap 15.8 — L1 z≈−1.1, L2 gap≈−2.5, L3 impulse≈+0.6, L4 dev≈+2.1, F3=65, F4 margin NULL | `score_0_100 ≈ 38`, `regime="RECOVERY"`, `qs_score_0_100=NULL`, flags contain `QS_PLACEHOLDER,F4_MARGIN_MISSING` | ±3 pts |
| `pt_2012_q3_peak` | PT 2012 crisis — L2 gap≈+14, L4 dev≈+7, L3 impulse≈−3 | `score_0_100 > 80`, `regime ∈ {SPECULATION, DISTRESS}`, `boom_overlay_active=1` (if score>70+gap+DSR satisfied) | ±4 pts |
| `us_2007_q3` | US pre-GFC — L2 gap≈+9.5, L4 z≈+1.6, F3≈55 | `score_0_100 > 70`, `regime="SPECULATION"`, `boom_overlay_active=1` | ±4 pts |
| `us_2009_q1` | US post-GFC trough | `regime="REPAIR"` (after 2-quarter persistence lag), `score < 25` | ±5 pts |
| `cn_2016_q1` | CN stimulus — L2 gap≈+25, L3≈+8 | `score_0_100 > 80`, flag `EM_COVERAGE` inherited, `boom_overlay_active=1` | ±5 pts |
| `pt_reweight_ms_missing` | F3 + F4 both unavailable (synthetic) | `MS_MISSING` flag, `cs_weight_effective + lc_weight_effective ≈ 1.00`, confidence ≤ 0.75 | — |
| `pt_reweight_cs_missing` | L1 + L2 + L4 row missing (synthetic; L3 present via standalone path → CS uncomputable) | raise `InsufficientDataError` (CS missing forces count<3 because LC needs L4) OR re-weight if L3 alone carries LC | see note |
| `pt_regime_sticky` | score_t=49, score_{t-1}=52, regime_{t-1}=BOOM | `regime_t="BOOM"` (sticky); Δ=3<5, persistence rule | — |
| `pt_whipsaw_rejection` | score oscillates 48↔52 across 5 BDs | `regime` stays constant; `regime_persistence_days` increments; flag `REGIME_HYSTERESIS_HOLD` | — |
| `xx_qs_placeholder` | any valid input | `qs_score_0_100 IS NULL` AND `QS_PLACEHOLDER` ∈ flags always | invariant |
| `xx_stale_l4` | L4 > 2Q old | raises `StaleDataError` | n/a |
| `xx_version_mismatch` | stored `CCCS_COMPOSITE_v0.0` | raises `VersionMismatchError` | n/a |

## 8. Storage schema

```sql
CREATE TABLE credit_cycle_scores (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    cccs_id                         TEXT    NOT NULL UNIQUE,       -- uuid4 per (country, date) row
    country_code                    TEXT    NOT NULL,              -- ISO α-2
    date                            DATE    NOT NULL,              -- business day (daily grid)
    methodology_version             TEXT    NOT NULL,              -- 'CCCS_COMPOSITE_v0.1'
    -- canonical score
    score_0_100                     REAL    NOT NULL CHECK (score_0_100 BETWEEN 0 AND 100),
    regime                          TEXT    NOT NULL CHECK (regime IN ('REPAIR','RECOVERY','BOOM','SPECULATION','DISTRESS')),
    regime_persistence_days         INTEGER NOT NULL,
    -- sub-component scores
    cs_score_0_100                  REAL,                           -- credit stress composite
    lc_score_0_100                  REAL,                           -- lending conditions
    ms_score_0_100                  REAL,                           -- market stress (cross-cycle)
    qs_score_0_100                  REAL,                           -- NULL in v0.1 (QS_PLACEHOLDER)
    cs_weight_effective             REAL    NOT NULL,
    lc_weight_effective             REAL    NOT NULL,
    ms_weight_effective             REAL    NOT NULL,
    components_available            INTEGER NOT NULL CHECK (components_available BETWEEN 3 AND 4),
    -- intra-CCCS component breakdown for audit
    l1_contribution_pct             REAL,
    l2_contribution_pct             REAL,
    l3_contribution_pct             REAL,
    l4_contribution_pct             REAL,
    f3_contribution_pct             REAL,                           -- cross-cycle indices/financial
    f4_margin_debt_contribution_pct REAL,
    -- overlays (Cap 15/16)
    boom_overlay_active             INTEGER NOT NULL DEFAULT 0 CHECK (boom_overlay_active IN (0,1)),
    boom_trigger_json               TEXT,                           -- {"score":72.4,"gap_pp":11.2,"dsr_z":1.7,...}
    -- meta
    confidence                      REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                           TEXT,                           -- CSV
    created_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_cccs_cd ON credit_cycle_scores (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `integration/matriz-4way` | L6 | CCCS `regime` compõe matriz 4-way com ECS (economic) / MSC (monetary) / FCS (financial) — 16 estados per Cap 17.1 |
| `integration/diagnostics/minsky-fragility` | L6 | `score_0_100 > 70` AND L4 DSR `band="critical"` AND F3 elevado → Minsky fragility alert (Cap 17.4 feedback loop) |
| `integration/diagnostics/bubble-detection` | L6 | `boom_overlay_active=1` AND F1 valuation extreme → bubble watch escalate |
| `outputs/editorial` | L7 | Portugal CCCS trajectory (2007 → 2012 peak → 2026) é flagship editorial; `regime` + `score_0_100` + `boom_overlay_active` citados directamente |
| `regimes/credit-regimes` *(Phase 2+)* | L5 | `regime` + `regime_persistence_days` → regime-conditioned state table |

## 10. Reference

- **Methodology**: [`docs/reference/cycles/credit-cccs.md`](../../reference/cycles/credit-cccs.md) — Manual Ciclo de Crédito Parte V, Caps 15 (composite), 16 (phase classification), 17 (cross-cycle interactions).
- **Data sources**: [`docs/data_sources/credit.md`](../../data_sources/credit.md) (L1-L4 upstream) + `data_sources/financial.md` (F3, F4 upstream).
- **Architecture**: [`specs/conventions/patterns.md`](../conventions/patterns.md) §Pattern 2 (Hierarchy best-of inherited from CRP overlay cascade) + §Pattern 4 (TE primary + native overrides upstream); [`adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) (BIS 43 universe aligned T1+T2 majority; T3+ fora → L1-L4 raise `DataUnavailableError` → CCCS `InsufficientDataError` per Policy 1).
- **Licensing**: [`governance/LICENSING.md`](../../governance/LICENSING.md) §3 (BIS CC-BY-4.0 + ECB/Eurostat + FRED via L3 upstream).
- **D-block evidence**: [`data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) §4 BIS WS_DSR 7/7 OK (L4 production-ready); WS_TC key pending (CAL-019 Phase 1 affects L1-L2-L3 — CCCS inheritance via `StaleDataError` se L1-L4 quarterly refresh falhar).
- **Papers**:
  - Drehmann M., Borio C., Tsatsaronis K. (2010), "Anchoring countercyclical capital buffers", BIS WP 317 (CCyB gap threshold logic).
  - Drehmann M., Juselius M. (2014), "Evaluating early warning indicators of banking crises", *IJF* 30(3) (DSR 0.89 AUC 1-2Y).
  - Jordà Ò., Schularick M., Taylor A. (2017), "Macrofinancial History and the New Business Cycle Facts" (JST sample, 45 crises backtest).
  - Minsky H. (1986), *Stabilizing an Unstable Economy* (hysteresis + Minsky cycle phasing informs SPECULATION → DISTRESS transition).
- **Cross-validation**: BIS early-warning panel (gap + DSR composite threshold) + IMF GFSR historical crisis dating. Target: CCCS > 70 em pelo menos 1 dos 4 trimestres pre-crisis em ≥ 80% dos 45 crisis episodes JST (walk-forward, one-sided).

## 11. Non-requirements

Scope boundaries. O que este componente **não** faz — pertence a outro módulo ou está fora de escopo v0.1:

- Does **not** compute HP filter directly — consumed from L2 via `hp_filter_cache` table (Policy 6); CCCS lê `l2_row.gap_hp_pp` pré-computado. Refactor do HP solver vive em L2; bug fixes propagam via `L2_CREDIT_GDP_GAP_v0.1` → `v0.2` bump.
- Does **not** include QS (Qualitative Signal — ECB BLS, Fed SLOOS, BdP surveys) in v0.1 — Phase 2+ via `indices/credit/extended/surveys/`. `qs_score_0_100` permanece `NULL`; flag `QS_PLACEHOLDER` sempre emitida. QS peso nominal de 10% (Cap 15.6) é omitido e redistribuído proporcionalmente entre CS/LC/MS (pesos v0.1 somam 0.99 pela renormalização 25+30+15 = 70, CS=44 LC=33 MS=22).
- Does **not** disaggregate CCCS por segment (HH vs NFC). L3/L4 expõem segments mas CCCS v0.1 usa apenas `segment="PNFS"`. Segment-level CCCS em Phase 2+.
- Does **not** emit country-conditional CCCS (standalone vs conditional-to-US/EA per Cap 17.5). Apenas *standalone*; Global Financial Cycle conditioning vive em `integration/matriz-4way`.
- Does **not** classify matriz 4×4 entre credit + economic (Cap 17.1 16 estados). Esse cruzamento vive em `integration/matriz-4way` (L6); CCCS apenas emite o eixo credit.
- Does **not** compute `regime_probabilities` (prob dist over 5 phases). Emite apenas a fase discreta após hysteresis. Probabilistic phase inference é Phase 2+.
- Does **not** backfill historical CCCS antes de 20Y de L1-L4 history disponível. Countries com séries < 15Y herdam `INSUFFICIENT_HISTORY` cap e CCCS pode não ser emitido para early dates — per-country cutoff gerido em `pipelines/backfill-strategy`.
- Does **not** persist L5 `credit_regimes` table (regime duration, transition matrix) — Phase 2+ spec; v0.1 apenas emite `regime` + `regime_persistence_days` inline em `credit_cycle_scores`.
- Does **not** re-fetch L1-L4 ou F3-F4 raw inputs — puro L3/L3-to-L4 aggregator sobre SONAR tables. Connector calls vivem upstream.
- Does **not** emit alerts editoriais — `boom_overlay_active=1` é informational trigger; narrativa + thresholds de alerta vivem em `outputs/editorial` playbook.
- Does **not** apply tier-aware confidence cap beyond Policy 1 + QS absent cap — per-tier integration (T2 0.85 / T3 fail / T4 fail) é Phase 1+ pipeline layer per ADR-0005 §Consequences; CCCS assume L1-L4 input rows herdam `EM_COVERAGE` upstream quando applicable.

