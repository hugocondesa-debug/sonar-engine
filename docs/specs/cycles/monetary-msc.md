# Monetary Stance Composite (MSC) — Spec

> Layer L4 · cycle · slug: `monetary-msc` · methodology_version: `MSC_COMPOSITE_v0.1`

## 1. Purpose

Agrega os 4 sub-índices monetários L3 (M1 ES, M2 RD, M3 EP, M4 FC) + um Communication Signal (CS) directo de connectors num composite `[0, 100]` (**higher = tighter**) por `(country_code, date)`, classifica em 6-band (canónico manual Cap 15.8) + 3-band (consumer convenience), e emite Dilemma overlay boolean (Cap 16 trigger A: price-stability vs financial-stability). Primitivo central do eixo monetário da matriz 4-way, input para cost-of-capital e sinal de trigger para diagnóstico Minsky do CCCS.

## 2. Inputs

MSC lê **duas tiers** de inputs para o mesmo `(country_code, date)`.

### Tier 1 — via L3 indices (pre-computed upstream)

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `m1_score` | `float` | `[0, 100]`; `confidence ≥ 0.50` | `indices/monetary/M1-effective-rates.score_normalized` (ES — effective stance) |
| `m2_score` | `float` | `[0, 100]`; `confidence ≥ 0.50` | `indices/monetary/M2-taylor-gaps.score_normalized` (RD — rule deviation) |
| `m3_score` | `float` | `[0, 100]`; `confidence ≥ 0.50` | `indices/monetary/M3-market-expectations.score_normalized` (EP — market-implied path + anchor) |
| `m4_score` | `float` | `[0, 100]`; `confidence ≥ 0.50` | `indices/monetary/M4-fci.score_normalized` (FC — financial conditions) |
| `m3_anchor_status` | `str` | enum `{well_anchored, moderately_anchored, drifting, unanchored, NULL}` | M3 enrichment (passthrough de `overlays/expected-inflation`) — consumed para Dilemma trigger |
| `m3_anchor_deviation_bps` | `int` | signed; `NULL` para `NO_TARGET` | idem |

### Tier 2 — CS (Communication Signal) directo de connectors

CS não é um L3 index (ver `indices/monetary/README.md §MSC preview`: os 5 sub-indices canónicos do manual são ES/RD/EP/FC/CS e SONAR v1 P4 implementou apenas os 4 primeiros). MSC consome os componentes quantitativos de CS directamente:

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `cs_hawkish_score` | `float` | `[0, 100]` z-mapped; NLP sentiment do latest FOMC / ECB GovC / BoE MPC / BoJ statement | `connectors/central_bank_nlp` *(to be specified — Phase 2+ connector)* |
| `fed_dissent_count` | `int` | `[0, 7]`; número de votos dissentes na última decisão (Fed-specific; BoE MPC equivalent) | `connectors/fed_dissent` OR raw parse das FOMC minutes *(to be specified)* |
| `dot_plot_drift_bps` | `int` | signed; `median(dot_plot) − market-implied forward` no mesmo horizon | `connectors/fomc_sep` (Fed) / `connectors/boe_mpc_projections` (BoE) *(to be specified)* |

Os três componentes CS são agregados em `cs_score_0_100` (weights internos 40/25/35, placeholder — manual Cap 15.5 lista 30/25/20/15/10 dentro de CS mas SONAR v0.1 simplifica para os 3 quantitativos computáveis). Resultado normalized `[0, 100]`, higher = tighter communication stance.

### Cross-cycle (optional, Dilemma overlay only)

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `ecs_score` | `float` | `[0, 100]`; economic cycle score | `cycles/economic-ecs.score_normalized` *(L4 peer, Phase 2+)* |

### Parameters (config)

- `weights = {"m1": 0.30, "m2": 0.15, "m3": 0.25, "m4": 0.20, "cs": 0.10}` — placeholder, Cap 15.6 canonical; sum = 1.00. Recalibrate após 24m production + walk-forward backtest contra regime changes identificados (2004-06 Fed hike, 2013 taper, 2014 ECB easing, 2019 Fed cut, 2022 hiking).
- `min_inputs = 3` — ≥3 dos 5 `{M1, M2, M3, M4, CS_direct}` disponíveis; senão raise `InsufficientDataError`.
- `regime_bands_6 = [(0,20,"STRONGLY_ACCOMMODATIVE"), (20,35,"ACCOMMODATIVE"), (35,50,"NEUTRAL_ACCOMMODATIVE"), (50,65,"NEUTRAL_TIGHT"), (65,80,"TIGHT"), (80,100,"STRONGLY_TIGHT")]` — manual Cap 15.8.
- `regime_bands_3 = [(0,40,"ACCOMMODATIVE"), (40,60,"NEUTRAL"), (60,100,"TIGHT")]` — consumer convenience.
- `hysteresis_delta_pts = 5` — transição entre bands requer `|Δscore| > 5`.
- `hysteresis_persistence_days = 3` — persistência ≥ 3 business days após threshold cross.
- `dilemma_msc_threshold = 60` — MSC `score > 60` (tight) é pré-requisito Trigger A.
- `dilemma_ecs_threshold = 55` — ECS `< 55` (weakening growth) é pré-requisito Trigger A.
- `reweight_confidence_cap = 0.75` — cap quando `inputs_available < 5`.

### Preconditions

- ≥ 3 dos 5 inputs `{M1, M2, M3, M4, CS_direct}` presentes em storage com `confidence ≥ 0.50` para `(country_code, date)`; senão raise `InsufficientDataError`.
- Todos os L3 índices consumidos partilham `(country_code, date)` e `date` é business day local.
- `methodology_version` de cada L3 row bate com runtime expected (`M1_EFFECTIVE_RATES_v0.1`, `M2_TAYLOR_GAPS_v0.1`, `M3_MARKET_EXPECTATIONS_v0.1`, `M4_FCI_v0.1`); senão raise `VersionMismatchError`.
- **CS connectors são Phase 2+**: em Phase 0-1 (bootstrap), `cs_hawkish_score`, `fed_dissent_count`, `dot_plot_drift_bps` são `NULL`; MSC funciona com 4 inputs (M1/M2/M3/M4) via re-weight (flag `COMM_SIGNAL_MISSING`, confidence cap 0.75). Não bloqueia rollout inicial.
- Para Dilemma trigger: `m3_anchor_status` lido de M3 enrichment (passthrough de `overlays/expected-inflation`). ECS é best-effort — se `cycles/economic-ecs` não existir ainda para `(country_code, date)`, Dilemma é emitido com `DILEMMA_NO_ECS` flag e `dilemma_overlay_active = 0`.

## 3. Outputs

Uma row per `(country_code, date)` em `monetary_cycle_scores`.

| Nome | Tipo | Unit | Storage |
|---|---|---|---|
| `score_0_100` | `float` | `[0, 100]` (higher = tighter) | `score_0_100` |
| `regime_6band` | `str` | enum 6-band (manual canonical) | `regime_6band` |
| `regime_3band` | `str` | enum 3-band (consumer convenience) | `regime_3band` |
| `regime_persistence_days` | `int` | days na current band após última transition | `regime_persistence_days` |
| `m{1..4}_score_0_100`, `cs_score_0_100` | `float` | per-input normalized | enrichment |
| `m{1..4}_weight_effective`, `cs_weight_effective` | `float` | effective (post re-weight) | enrichment |
| `inputs_available` | `int` | `[3, 5]` | enrichment |
| `cs_hawkish_score`, `fed_dissent_count`, `dot_plot_drift_bps` | various | audit | enrichment |
| `dilemma_overlay_active` | `int (0/1)` | boolean | `dilemma_overlay_active` |
| `dilemma_trigger_json` | `str (JSON)` | `NULL` se inactive | `dilemma_trigger_json` |
| `confidence` | `float` | `[0, 1]` | per `units.md` |
| `flags` | `str (CSV)` | — | per `flags.md` |
| `methodology_version` | `str` | — | `MSC_COMPOSITE_v0.1` |

**Canonical JSON shape** (`dilemma_trigger_json` when active):

```json
{
  "trigger": "A_price_vs_financial_stability",
  "msc_score": 68.5,
  "m3_anchor_status": "drifting",
  "m3_anchor_deviation_bps": 72,
  "ecs_score": 48.0,
  "ecs_source": "cycles/economic-ecs",
  "editorial_angle": "ECB tight stance + inflation drifting + weakening growth"
}
```

## 4. Algorithm

> **Units**: MSC score em `float [0, 100]`; weights em decimal; thresholds em pts (unit-less score); Dilemma deviations em `_bps` integer signed. Regras em [`conventions/units.md`](../conventions/units.md) §Confidence, §Spreads.

**Formula** — canonical composite (Cap 15.6):

```text
MSC_t = 0.30 · M1_t  +  0.15 · M2_t  +  0.25 · M3_t  +  0.20 · M4_t  +  0.10 · CS_t

# Re-weight on missing input (Policy 1):
present = {i : score_i available, confidence_i ≥ 0.50}
require |present| ≥ 3  else raise InsufficientDataError
w_effective_i = w_nominal_i / sum(w_nominal_j for j in present)   # renormalize to 1.00
MSC_t = sum( w_effective_i · score_i for i in present )

# Clip (should be redundant given inputs ∈ [0,100]):
score_0_100 = clip(MSC_t, 0, 100)
```

**Pseudocode** (deterministic):

1. Lookup `(country_code, date)` rows em `monetary_m1_effective_rates`, `monetary_m2_taylor_gaps`, `monetary_m3_market_expectations`, `monetary_m4_fci`. Validate `methodology_version` ∈ expected set; confidence ≥ 0.50.
2. Lookup Tier 2 CS components via connectors (when available Phase 2+). Compute `cs_score_0_100 = clip(0.40·z_map(cs_hawkish_score) + 0.25·z_map(fed_dissent_count) + 0.35·z_map(dot_plot_drift_bps), 0, 100)`. If ≥ 1 CS component missing/stale, emit `COMM_SIGNAL_MISSING` + skip CS entirely (treat tier as absent).
3. Build `present` set; assert `|present| ≥ 3` else raise `InsufficientDataError`.
4. For each missing input `i ∈ {M1, M2, M3, M4, CS}`, emit corresponding `{i}_MISSING` flag (`M1_MISSING`, `M2_MISSING`, `M3_MISSING`, `M4_MISSING`, `COMM_SIGNAL_MISSING`).
5. Compute `w_effective_i` via proportional re-weight on `present`.
6. Compute `MSC_t = Σ w_effective_i · score_i`.
7. Resolve `regime_6band` and `regime_3band` from `score_0_100` via band tables.
8. **Hysteresis**: lookup previous row `(country_code, date − 1 bd)` in `monetary_cycle_scores`.
   - If same band → `regime_persistence_days += 1`.
   - If different band AND `|score_t − score_{t−1}| ≤ 5` → **hold previous band** (anti-whipsaw); `regime_persistence_days += 1`; emit `REGIME_HYSTERESIS_HOLD` flag.
   - If different band AND `|Δ| > 5` AND transition streak `≥ 3 bd` → commit transition; `regime_persistence_days = 1`.
   - Cold-start (no previous row) → commit band; `regime_persistence_days = 1`.
9. **Dilemma overlay (Cap 16 Trigger A — price vs financial stability)**:
   - IF `score_0_100 > 60` (tight) AND `m3_anchor_status ∈ {"drifting","unanchored"}` AND `ecs_score < 55` → `dilemma_overlay_active = 1`; populate `dilemma_trigger_json`.
   - IF ECS row indisponível para `(country_code, date)` → `dilemma_overlay_active = 0`; emit `DILEMMA_NO_ECS` flag (informational — re-evaluation deferred until CCCS/ECS ships).
   - Outros triggers (B FX pressure, C inflation-unemployment, D framework) são Phase 2+ — fora de escopo v0.1.
10. Compute `confidence = min(inputs_confidences) · (inputs_available / 5)`; apply flag-based deltas per `flags.md §Convenção de propagação`; cap at `reweight_confidence_cap = 0.75` quando `inputs_available < 5`.
11. Inherit flags de cada input L3 (CSV union, lexicographic order).
12. Persist row em §8 schema.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | weighted sum, clip |
| `pandas` | 2.1 | previous-row lookup, persistence lag |
| `sqlalchemy` | 2.0 | persistence + L3 reads |
| `pydantic` | 2.6 | output validation |
| `pyyaml` | 6.0 | `config/msc_weights.yaml` (future recalibration) |

No network — todos inputs pre-computed em L3 + L0 connectors.

## 6. Edge cases

Flags → [`conventions/flags.md`](../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../conventions/exceptions.md). Propagação conforme § "Convenção de propagação".

| Trigger | Handling | Confidence |
|---|---|---|
| `< 3` inputs disponíveis (dos 5) | raise `InsufficientDataError` | n/a |
| M1 missing | emit `M1_MISSING`; re-weight restantes | cap 0.75 |
| M2 missing | emit `M2_MISSING`; re-weight | cap 0.75 |
| M3 missing | emit `M3_MISSING`; re-weight | cap 0.75 |
| M4 missing | emit `M4_MISSING`; re-weight | cap 0.75 |
| CS components não disponíveis (Phase 0-1 default) | emit `COMM_SIGNAL_MISSING`; re-weight para 4 inputs | cap 0.75 |
| Input row `confidence < 0.50` | treat as missing; re-weight + flag `{INPUT}_MISSING` | cap 0.75 |
| Score transition `|Δ| ≤ 5` vs previous bd | hold previous band; flag `REGIME_HYSTERESIS_HOLD` | −0.05 |
| Score transition committed before `3 bd` persistence | hold previous band; flag `REGIME_HYSTERESIS_HOLD` | −0.05 |
| `ecs_score` unavailable AND MSC would trigger Dilemma | `dilemma_overlay_active = 0`; flag `DILEMMA_NO_ECS` | informational |
| `m3_anchor_status = NO_TARGET` (CN/TR/AR via M3) | Dilemma Trigger A skipped (anchor undefined) | informational |
| Stored L3 `methodology_version` ≠ runtime expected | raise `VersionMismatchError` | n/a |
| Cold-start (no prior row for country) | commit band; `regime_persistence_days = 1` | no impact |
| L3 input flag propagation (ex: `R_STAR_PROXY,EM_COVERAGE,NO_TARGET`) | inherit to MSC row flags column | per `flags.md` |
| All 5 inputs present but country tier 4 (CN/IN/BR/TR/MX) | inherit `EM_COVERAGE`; composite computed normally | cap 0.60 (via inheritance) |

## 7. Test fixtures

Stored em `tests/fixtures/monetary-msc/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2026_04_17_full5` | M1=62, M2=54, M3=45, M4=42, CS=55 | `score≈52.15`; `regime_6band=NEUTRAL_TIGHT`; `regime_3band=NEUTRAL`; `dilemma=0`; `inputs_available=5` | ±0.5 pts |
| `us_2026_04_17_no_cs` | M1-M4 only (Phase 0-1) | re-weight sum `0.30/0.15/0.25/0.20 → /0.90`; flag `COMM_SIGNAL_MISSING`; `confidence ≤ 0.75` | ±0.5 pts |
| `ea_2011_q2_dilemma` | M1=62, M2=60, M3=65, M4=58, CS=55; anchor=drifting (+80bps); ECS=45 | `score≈61.2`; `dilemma_overlay_active=1`; trigger=A; editorial angle emitido | ±0.5 pts |
| `pt_2012_q3_crisis_inherit` | PT M1/M2 com `R_STAR_PROXY`; M4 `EM_COVERAGE` via spread; CS missing | inherit flags; `confidence ≤ 0.75`; regime transition committed | — |
| `jp_2014_zlb_accommodative` | M1=18, M2=25 (negative Taylor gap), M3=22, M4=35, CS=20 | `score≈24.5`; `regime_6band=ACCOMMODATIVE`; `regime_3band=ACCOMMODATIVE`; `dilemma=0` | ±0.5 pts |
| `us_2022_hiking_strong_tight` | M1=85, M2=78, M3=82, M4=70, CS=80 | `score≈80.05`; `regime_6band=STRONGLY_TIGHT`; `regime_3band=TIGHT` | ±0.5 pts |
| `regime_held_whipsaw` | prev band `NEUTRAL_TIGHT` score=51; today score=49.5 (`|Δ|=1.5 ≤ 5`) | hold previous band; flag `REGIME_HYSTERESIS_HOLD`; `regime_persistence_days += 1` | — |
| `regime_transition_committed` | prev `NEUTRAL_TIGHT` score=52; 3 bd streak with score=66, 68, 70 (`|Δ|>5` sustained) | transition to `TIGHT`; `regime_persistence_days = 1` | — |
| `insufficient_2_inputs` | Only M1 + M4 (M2/M3/CS all missing) | raises `InsufficientDataError` | n/a |
| `dilemma_no_ecs` | score=68, anchor=drifting, ECS row absent | `dilemma_overlay_active=0`; flag `DILEMMA_NO_ECS` | — |
| `cn_no_target_no_dilemma` | CN score=62, anchor_status=NULL (`NO_TARGET`) | Trigger A skipped; `dilemma=0`; no `DILEMMA_NO_ECS` flag either | — |

## 8. Storage schema

```sql
CREATE TABLE monetary_cycle_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msc_id TEXT NOT NULL UNIQUE,                          -- uuid4 correlation
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    methodology_version TEXT NOT NULL,                    -- 'MSC_COMPOSITE_v0.1'
    score_0_100 REAL NOT NULL CHECK (score_0_100 BETWEEN 0 AND 100),
    regime_6band TEXT NOT NULL,                           -- STRONGLY_ACCOMMODATIVE | ACCOMMODATIVE | NEUTRAL_ACCOMMODATIVE | NEUTRAL_TIGHT | TIGHT | STRONGLY_TIGHT
    regime_3band TEXT NOT NULL,                           -- ACCOMMODATIVE | NEUTRAL | TIGHT (consumer convenience)
    regime_persistence_days INTEGER NOT NULL,
    -- component scores (normalized)
    m1_score_0_100 REAL,
    m2_score_0_100 REAL,
    m3_score_0_100 REAL,
    m4_score_0_100 REAL,
    cs_score_0_100 REAL,                                  -- direct from connectors (Tier 2)
    m1_weight_effective REAL NOT NULL,
    m2_weight_effective REAL NOT NULL,
    m3_weight_effective REAL NOT NULL,
    m4_weight_effective REAL NOT NULL,
    cs_weight_effective REAL NOT NULL,
    inputs_available INTEGER NOT NULL CHECK (inputs_available BETWEEN 3 AND 5),
    -- CS breakdown for audit
    cs_hawkish_score REAL,
    fed_dissent_count INTEGER,
    dot_plot_drift_bps INTEGER,
    -- overlays
    dilemma_overlay_active INTEGER NOT NULL DEFAULT 0,
    dilemma_trigger_json TEXT,
    -- meta
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags TEXT,                                           -- CSV ordem lexicográfica
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_msc_cd ON monetary_cycle_scores (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `integration/matriz-4way` | L6 | `regime_3band` (eixo monetary) + `score_0_100` gradient; `dilemma_overlay_active` como modifier |
| `integration/cost-of-capital` | L6 | `score_0_100` stance feeds risk-free normalization (tight stance → forward-path-adjusted discount) |
| `cycles/credit-cccs` | L4 (peer) | MSC tight persistent (`regime_3band="TIGHT"` AND `regime_persistence_days ≥ 90`) → trigger para Minsky transition diagnostic (late-cycle easing detection) |
| `outputs/editorial` | L7 | Dilemma overlay é angle editorial (ex: ECB em Portugal post-2022); `regime_3band` + `score_0_100` em narrative |
| `integration/diagnostics/regime-shift` | L6 | `REGIME_HYSTERESIS_HOLD` após streak longo indica transição em curso; input para scenario planning |

## 10. Reference

- **Methodology**: [`docs/reference/cycles/monetary.md`](../../reference/cycles/monetary.md) Caps 15 (MSC composite design — 15.3 arquitectura em 3 layers, 15.5 sub-indices, 15.6 pesos canónicos, 15.7 robustness, 15.8 bands, 15.10 MSC×CCCS matriz) + 16 (Dilemma overlay — 16.2 operational triggers, 16.7 dilemma_score computation).
- **Upstream specs L3**: [`M1`](../indices/monetary/M1-effective-rates.md), [`M2`](../indices/monetary/M2-taylor-gaps.md), [`M3`](../indices/monetary/M3-market-expectations.md), [`M4`](../indices/monetary/M4-fci.md).
- **Overlays consumed indirectly via M3**: [`expected-inflation`](../overlays/expected-inflation.md) (anchor_status for Dilemma).
- **Data sources**: [`docs/data_sources/monetary.md`](../../data_sources/monetary.md) §7 (communication signals — NLP, dissent rate, dot plot — Tier 2/3 Phase 2+).
- **Conventions**: [`flags`](../conventions/flags.md) · [`exceptions`](../conventions/exceptions.md) · [`units`](../conventions/units.md) · [`methodology-versions`](../conventions/methodology-versions.md).
- **Papers**:
  - Borio C. (2014), "The financial cycle and macroeconomics: What have we learnt?", *JBF* 45 — Dilemma Trigger A theoretical basis.
  - Rey H. (2013), "Dilemma not Trilemma: The Global Financial Cycle and Monetary Policy Independence", *Jackson Hole* — Dilemma Trigger B (Phase 2+).
  - Taylor J. B. (1993/1999), Clarida-Galí-Gertler (2000), Holston-Laubach-Williams (2017) — upstream via M1/M2.
- **Cross-validation**: Manual Cap 15.8 "Major BCs — Abril 2026 snapshot" (Fed ~58, ECB ~48, BoE ~62, BoJ ~28) serve como sanity baseline; historical Dilemma cases (Cap 16.3: Fed Jun-Dec 2023, ECB Mar-Jun 2011, BoJ 2022-2023) validam trigger sensitivity.

## 11. Non-requirements

- Does not run NLP on central bank statements directly — consumes pre-computed `cs_hawkish_score` from `connectors/central_bank_nlp` (Phase 2+); hawkish/dovish scoring model lives upstream.
- Does not forecast monetary policy path — only classifies current stance for `(country_code, date)`. Reaction function prediction (Cap 19) é scope de `integration/diagnostics/reaction-function`.
- Does not recompute M1-M4 sub-indices — consumes `score_normalized` pre-computed em L3 tables; re-weight is on the MSC composite, not on L3 sub-component weights.
- Does not implement Dilemma Triggers B (FX pressure), C (inflation-unemployment stagflation), D (framework inconsistency) — Phase 2+ scope. Only Trigger A (price vs financial stability / Borio setup) é emitido em v0.1.
- Does not classify Dilemma type beyond boolean + `trigger` label — severity scoring (`dilemma_score_t` of Cap 16.7) é feature futura.
- Does not cross-write M1-M4 tables — read-only on upstream L3.
- Does not emit partial rows when `InsufficientDataError` triggers — raise early, no stub persistence.
- Does not handle multi-country aggregation (ex: "G7 MSC") — single `(country_code, date)` only; peer comparison (Cap 15.9 Nível 3) vive no dashboard layer.
- Does not auto-recalibrate `weights` per BC — fixed Cap 15.6 global weights; per-BC customization viola robustness principle (Cap 15.7 armadilha 3). Future recalibration é spec bump (MINOR) via walk-forward backtest.
- Does not emit intraday — daily EOD batch; policy decisions tracked separately em `policy_decisions` table.
- Does not substitute BC official communication framework (FOMC SEP, ECB MPA narrative) — SONAR é analytical; official communiqués são cross-check only.
- Does not backfill pre-1995 — M1 shadow rate series sparse; M2 Taylor requires HLW r* (starts ~1961 US, later others); coverage limit via `lookback_years` em L3.

