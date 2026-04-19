# ECS — Economic Cycle Score (composite) — Spec

> Layer L4 · cycle · slug: `economic-ecs` · methodology_version: `ECS_COMPOSITE_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E3)

## 1. Purpose

Compose the 4 economic sub-indices (E1 Activity, E2 Leading, E3 Labor, E4 Sentiment) numa métrica única `score_0_100 ∈ [0, 100]` por `(country_code, date)`, classificar discrete `regime ∈ {EXPANSION, PEAK_ZONE, EARLY_RECESSION, RECESSION}` com anti-whipsaw hysteresis, e emitir separately o `stagflation_overlay_active` flag (Cap 16). Foundation do cycle layer económico — consumido pelo integration layer (matriz 4-way, cost-of-capital diagnostics) e pelos outputs (editorial, alerts). Base agregation per Cap 15.6 do manual de referência.

## 2. Inputs

| Name | Type | Constraints | Source |
|---|---|---|---|
| `e1_score` | `float` | `[0, 100]`, `confidence ≥ 0.50` | `indices/economic/E1-activity` (`idx_economic_e1_activity`) |
| `e2_score` | `float` | `[0, 100]`, `confidence ≥ 0.50` | `indices/economic/E2-leading` (`idx_economic_e2_leading`) |
| `e3_score` | `float` | `[0, 100]`, `confidence ≥ 0.50` | `indices/economic/E3-labor` (`idx_economic_e3_labor`) |
| `e4_score` | `float` | `[0, 100]`, `confidence ≥ 0.50` | `indices/economic/E4-sentiment` (`idx_economic_e4_sentiment`) |
| `sahm_triggered` | `int` | `0` \| `1` | E3 output column (passthrough) |
| `cpi_yoy` | `float` | decimal YoY; `[-0.05, 0.30]` | `connectors/fred` (`CPIAUCSL` YoY) · `connectors/eurostat` (HICP) |
| `unemployment_rate` | `float` | decimal; `[0, 0.30]` | E3 raw passthrough (`UNRATE` equiv) |
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | business day local to country | param |

### Preconditions

Invariantes antes da invocação — cada sub-index é input independente. Nenhuma dependência entre E1↔E4 (Cap 15.5: paralelo by design).

- **E1 Activity**: row existe em `idx_economic_e1_activity` para `(country_code, date_eom)` com `methodology_version = E1_ACTIVITY_v0.1` **e** `confidence ≥ 0.50`. Senão: índice considerado unavailable → Policy 1 re-weighting.
- **E2 Leading**: idem, `methodology_version = E2_LEADING_v0.2` (post-Bloco E2 bump per D2 USSLIND removal; CAL-023 pending), `confidence ≥ 0.50`.
- **E3 Labor**: idem, `methodology_version = E3_LABOR_v0.1`, `confidence ≥ 0.50`. `sahm_triggered` column lido junto.
- **E4 Sentiment**: idem, `methodology_version = E4_SENTIMENT_v0.1`, `confidence ≥ 0.50`.
- **Stagflation inputs**: `cpi_yoy` ≤ 45 dias stale para mês de `date`; `unemployment_rate` ≤ 45 dias.
- Pelo menos **3** dos 4 sub-indices disponíveis. Senão raise `InsufficientDataError` (nenhuma row persistida) — ver §6.
- `date` é business day local; sub-indices são monthly (`date_eom`) — lookup faz `min(month-end ≤ date)`.
- Stored sub-index `methodology_version` rows batem com runtime constants; senão `VersionMismatchError`.

## 3. Outputs

Uma row por `(country_code, date, methodology_version)` em `economic_cycle_scores`. UUID `ecs_id` permite linkage futura a L5 regime rows (Phase 2+).

| Field | Type | Unit | Storage |
|---|---|---|---|
| `ecs_id` | `str` (UUID v4) | — | `economic_cycle_scores` |
| `score_0_100` | `float` | `[0, 100]` (canonical composite) | idem |
| `regime` | `str` | enum: `EXPANSION` \| `PEAK_ZONE` \| `EARLY_RECESSION` \| `RECESSION` | idem |
| `regime_persistence_days` | `int` | consecutive business days in current regime | idem |
| `e{1..4}_score_0_100` | `float?` | `[0, 100]` component scores; NULL se índice unavailable | idem |
| `e{1..4}_weight_effective` | `float` | `[0, 1]`; reflecte re-weighting (Policy 1) | idem |
| `indices_available` | `int` | `3..4` | idem |
| `stagflation_overlay_active` | `int` | `0` \| `1` (stored boolean) | idem |
| `stagflation_trigger_json` | `str?` (JSON) | `{cpi_yoy, sahm_triggered, unemployment_trend}` when active; NULL otherwise | idem |
| `confidence` | `float` | `[0, 1]` (cap 0.75 quando `indices_available < 4`) | idem |
| `flags` | `str?` (CSV) | tokens em `conventions/flags.md` (lex order) | idem |
| `methodology_version` | `str` | `ECS_COMPOSITE_v0.1` | idem |

**Canonical JSON shape** (materialized via ORM / API):

```json
{
  "ecs_id": "8e2a10f0-7d55-4b4f-9b2e-5f2c9c6f0a01",
  "country": "US", "date": "2026-04-17",
  "score_0_100": 58.3, "regime": "EXPANSION", "regime_persistence_days": 42,
  "components": {"E1": 62.1, "E2": 54.5, "E3": 56.8, "E4": 58.2},
  "weights_effective": {"E1": 0.35, "E2": 0.25, "E3": 0.25, "E4": 0.15},
  "indices_available": 4,
  "stagflation_overlay_active": 0, "stagflation_trigger_json": null,
  "confidence": 0.82, "flags": null,
  "methodology_version": "ECS_COMPOSITE_v0.1"
}
```

## 4. Algorithm

> **Units**: sub-index scores em `[0, 100]` float; CPI YoY e unemployment rate em decimal (`0.031` = 3.1%). Score composite em `[0, 100]` float. Persistence em business days (`int`). Full rules em [`conventions/units.md`](../conventions/units.md).

**Canonical weights** (Cap 15.6):

| Sub-index | Base weight |
|---|---|
| `E1 Activity` | 0.35 |
| `E2 Leading` | 0.25 |
| `E3 Labor` | 0.25 |
| `E4 Sentiment` | 0.15 |

*Placeholder — recalibrate após 24m de production data + walk-forward backtest contra NBER/CEPR (hit-ratio framework; Cap 15.6 + §15.8 robustness checks).*

**Regime bands** (Cap 15.7 — intentionally overlapping PEAK_ZONE ∩ EXPANSION em 55-60; hysteresis disambigua):

| Regime | Raw band |
|---|---|
| `EXPANSION` | `score > 60` |
| `PEAK_ZONE` | `55 ≤ score ≤ 70` |
| `EARLY_RECESSION` | `40 ≤ score < 55` |
| `RECESSION` | `score < 40` |

*Placeholder — recalibrate após 24m of production data contra NBER/CEPR historical dating.*

**Pipeline per `(country, date)`**:

1. Lookup 4 sub-index rows from `idx_economic_e{1..4}_*` for `(country_code, latest month-end ≤ date)`. Validate `methodology_version` + `confidence ≥ 0.50` per sub-index.
2. Build `available` set: índice entra se linha existe e passa gate acima. Se algum levanta `InsufficientDataError` upstream, é tratado como unavailable e `E{i}_MISSING` flag é emitida.
3. If `len(available) < 3`: raise `InsufficientDataError` (no row persisted; log at boundary).
4. **Re-weight proporcionalmente** (Policy 1): `w'_i = w_i / Σ_{j ∈ available} w_j` para i ∈ available; `w'_i = 0` para missing. Exemplo: E4 missing → `(0.35, 0.25, 0.25, 0.0)` → normalized `(0.412, 0.294, 0.294, 0.0)`.
5. Compute `score_0_100 = Σ_{i ∈ available} w'_i · e_i_score`. Clip para `[0, 100]` (defensive, não esperado escapar).
6. **Regime classification with hysteresis** (state machine — anti-whipsaw mandatory per §4 policy):
   - Load previous row: `prev_regime`, `prev_score_0_100`, `prev_regime_persistence_days` from `economic_cycle_scores` for `(country_code, date − 1 business day)`.
   - Compute `raw_regime` from current `score_0_100` per band table (ties go to higher-severity — PEAK_ZONE wins over EXPANSION at 55-60; EARLY_RECESSION wins at 55).
   - **Transition rule**: `regime = raw_regime` **only if** `|score_0_100 − prev_score_0_100| > 5.0` **AND** new raw band observed consecutivamente ≥ 3 business days (persistence buffer tracked on a per-country rolling state; see §6 `PERSISTENCE_BUFFER`).
   - Else: `regime = prev_regime` (sticky); buffer candidate.
   - `regime_persistence_days = prev_regime_persistence_days + 1` se same regime; else `1`.
   - Bootstrap: se não há `prev_*` (first row per country), use raw band directly, `persistence_days = 1`.
7. **Stagflation overlay** (Cap 16.3 Trigger A adapted, weighted toward SONAR-computable signals):
   - Compute `stagflation_overlay_active = 1` iff **all three** of:
     - `score_0_100 < 55`
     - `cpi_yoy > 0.03`
     - Labor weakness: `sahm_triggered == 1` **OR** `unemployment_rate − unemployment_rate_12m_ago > 0.003` (0.3pp rise)
   - Else `= 0`.
   - Populate `stagflation_trigger_json` quando active: `{"cpi_yoy": 0.041, "sahm_triggered": 1, "unemployment_trend": "rising"}`. NULL caso contrário.
   - Emit `STAGFLATION_OVERLAY_ACTIVE` flag quando true.
8. Compute `confidence`:
   - Base: `confidence = min(e_i.confidence for i in available) · (len(available) / 4)`.
   - Re-weighted cap: se `len(available) < 4`, **cap at 0.75**.
   - Additional impacts per flags (ver §6 / `conventions/flags.md` propagation rules).
9. Persist single row (`ecs_id = uuid4()`) em `economic_cycle_scores` com `methodology_version = ECS_COMPOSITE_v0.1`. Flags sorted lex.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | arrays, weighted sums |
| `pandas` | 2.1 | time-series alignment across sub-indices; business-day calendar |
| `sqlalchemy` | 2.0 | persistence + previous-row lookup |
| `pydantic` | 2.6 | output validation |

No network calls inside algorithm — all inputs read from upstream index tables + connectors already persisted by pipelines.

## 6. Edge cases

Flags catalog → [`conventions/flags.md`](../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../conventions/exceptions.md). Confidence impact aditivo (floor 0, ceil 1) conforme `flags.md` § Convenção de propagação. Flags sub-index-inherited propagam automaticamente.

| Trigger | Handling | Confidence |
|---|---|---|
| `indices_available < 3` (any combination) | raise `InsufficientDataError`; no persist | n/a |
| Exactly 1 index missing (E1, E2, E3 ou E4) | re-weight per Policy 1; emit `E{N}_MISSING` flag | cap at 0.75 |
| Sub-index row exists mas `confidence < 0.50` | treat as missing; emit `E{N}_MISSING` | cap 0.75 |
| Sub-index `methodology_version` mismatch vs runtime | raise `VersionMismatchError` | n/a |
| Stored ECS `methodology_version ≠` runtime at lookup of `prev_*` | raise `VersionMismatchError` (recompute required) | n/a |
| Bootstrap row (no `prev_*` for country) | regime = raw band; `persistence_days = 1`; flag `REGIME_BOOTSTRAP` | informational |
| `|Δscore| > 5` mas persistence < 3 days | hold `prev_regime`; internal buffer tracked; no flag (expected path) | n/a |
| Hysteresis buffer full 3d but `|Δscore|` dropped ≤ 5 mid-buffer | reset buffer; stay in `prev_regime` | informational via `REGIME_HYSTERESIS_HOLD` |
| Stagflation trigger active | emit `STAGFLATION_OVERLAY_ACTIVE`; populate `stagflation_trigger_json` | informational (none direct; no confidence penalty) |
| Sub-index carries `STALE` flag | inherit into ECS `flags` (propagation rule) | inherit −0.20 |
| Sub-index carries `EM_COVERAGE` (Tier 4) | inherit; ECS row also caps 0.70 by rule | cap 0.70 |
| `cpi_yoy` unavailable / > 45d stale | stagflation overlay set to `0`; emit `STAGFLATION_INPUT_MISSING`; do not fail ECS | −0.05 |
| `unemployment_rate_12m_ago` absent for trend | use `sahm_triggered` alone; emit `STAGFLATION_INPUT_MISSING` if both absent | −0.05 |
| Connector returns NaN / invalid | raise `InvalidInputError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/economic-ecs/`. Each fixture injects 4 sub-index rows + stagflation inputs; expected ECS row + regime + overlay state + flags.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01_02_expansion` | E1=62, E2=55, E3=57, E4=58; CPI=0.028; Sahm=0; Δunemp=0.001 | `score ≈ 58.5`, `regime=EXPANSION`, overlay `0` | ±1 pt |
| `us_2020_03_23_recession` | E1=22, E2=28, E3=18, E4=25; CPI=0.015; Sahm=1 | `score ≈ 23.0`, `regime=RECESSION`, overlay `0` (cpi<3%) | ±1 pt |
| `us_1974_q2_stagflation` | E1=42, E2=38, E3=44, E4=40; CPI=0.115; Sahm=1; Δunemp=0.008 | `score ≈ 41.0`, `regime=EARLY_RECESSION`, overlay `1`, trigger JSON populated | ±1 pt |
| `pt_e4_missing` | E1=55, E2=52, E3=54, E4=N/A | `score ≈ 53.7` (re-weighted 0.412/0.294/0.294/0), `indices_available=3`, flag `E4_MISSING`, confidence cap 0.75 | ±1 pt |
| `insufficient_2_indices` | Apenas E1, E3 disponíveis | raises `InsufficientDataError`; no persist | n/a |
| `hysteresis_whipsaw_reject` | Prev EXPANSION score=62, today score=54 (|Δ|=8 but new band 1 BD) | `regime=EXPANSION` sticky; `regime_persistence_days++`; no flag | — |
| `hysteresis_persistence_met` | 3 consecutive BDs with score<55 after |Δ|>5 | `regime=EARLY_RECESSION` commits; `persistence_days=1` reset | — |
| `bootstrap_first_row` | US 2010-01-01, no prev row | `regime` = raw band, `persistence_days=1`, flag `REGIME_BOOTSTRAP` | — |
| `stagflation_input_missing` | score=50, cpi_yoy NULL | overlay forced `0`; flag `STAGFLATION_INPUT_MISSING`; `−0.05` confidence | — |
| `em_tier4_br_2024_01` | E1/E2/E3 OK (cap 0.70 each); E4 unavailable | `indices_available=3`, flag `E4_MISSING` + `EM_COVERAGE` inherited; confidence cap 0.70 (EM dominates) | — |

## 8. Storage schema

```sql
CREATE TABLE economic_cycle_scores (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    ecs_id                     TEXT    NOT NULL UNIQUE,          -- uuid4
    country_code               TEXT    NOT NULL,
    date                       DATE    NOT NULL,
    methodology_version        TEXT    NOT NULL,                 -- 'ECS_COMPOSITE_v0.1'
    score_0_100                REAL    NOT NULL CHECK (score_0_100 BETWEEN 0 AND 100),
    regime                     TEXT    NOT NULL CHECK (regime IN ('EXPANSION','PEAK_ZONE','EARLY_RECESSION','RECESSION')),
    regime_persistence_days    INTEGER NOT NULL CHECK (regime_persistence_days >= 1),
    -- component scores (NULL se índice unavailable)
    e1_score_0_100             REAL    CHECK (e1_score_0_100 IS NULL OR e1_score_0_100 BETWEEN 0 AND 100),
    e2_score_0_100             REAL    CHECK (e2_score_0_100 IS NULL OR e2_score_0_100 BETWEEN 0 AND 100),
    e3_score_0_100             REAL    CHECK (e3_score_0_100 IS NULL OR e3_score_0_100 BETWEEN 0 AND 100),
    e4_score_0_100             REAL    CHECK (e4_score_0_100 IS NULL OR e4_score_0_100 BETWEEN 0 AND 100),
    -- effective weights (reflecte re-weighting Policy 1; sum = 1.0)
    e1_weight_effective        REAL    NOT NULL CHECK (e1_weight_effective BETWEEN 0 AND 1),
    e2_weight_effective        REAL    NOT NULL CHECK (e2_weight_effective BETWEEN 0 AND 1),
    e3_weight_effective        REAL    NOT NULL CHECK (e3_weight_effective BETWEEN 0 AND 1),
    e4_weight_effective        REAL    NOT NULL CHECK (e4_weight_effective BETWEEN 0 AND 1),
    indices_available          INTEGER NOT NULL CHECK (indices_available BETWEEN 3 AND 4),
    -- stagflation overlay
    stagflation_overlay_active INTEGER NOT NULL DEFAULT 0 CHECK (stagflation_overlay_active IN (0, 1)),
    stagflation_trigger_json   TEXT,                              -- JSON quando active; NULL otherwise
    -- meta
    confidence                 REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                      TEXT,                              -- CSV lex-sorted
    created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_ecs_cd     ON economic_cycle_scores (country_code, date);
CREATE INDEX idx_ecs_regime ON economic_cycle_scores (country_code, regime, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `integration/matriz-4way` | L6 | `score_0_100` + `regime` compostos com CCCS / MSC / FCS para classificação canonical pattern |
| `integration/diagnostics/stagflation` | L6 | `stagflation_overlay_active` + trigger JSON |
| `integration/cost-of-capital` | L6 | `regime` informa risk-free term premium adjustment |
| `cycles/monetary-msc` | L4 (peer) | Dilemma overlay lê `score_0_100 < 55` como growth-weakening side-condition |
| `cycles/credit-cccs` | L4 (peer) | Pattern `RECESSION + CCCS DISTRESS` dispara cross-cycle stress signal |
| `outputs/editorial` | L7 | Regime transitions + Stagflation overlay são ângulos editoriais primários |
| `outputs/alerts` | L7 | Regime transition `EXPANSION → PEAK_ZONE` ou `PEAK_ZONE → EARLY_RECESSION` raise alerts |

## 10. Reference

- **Methodology**: [`docs/reference/cycles/economic.md`](../../reference/cycles/economic.md) — Manual do Ciclo Económico, Parte V Cap 15 (Composite design), Cap 16 (Stagflation overlay), Cap 17 (Matriz 4-way).
- **Indices consumed**: [`docs/specs/indices/economic/README.md`](../../indices/economic/README.md) (E1-E4 overview + canonical weights).
- **Architecture**: [`specs/conventions/patterns.md`](../conventions/patterns.md) §Pattern 4 (TE primary + native overrides upstream per E1-E4); [`adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) (Policy 1 cap 0.75 já aplicado; tier-conditional confidence cap T2 0.85 / T3 0.65 / T4 fail é Phase 1+ integration).
- **Licensing**: [`governance/LICENSING.md`](../../governance/LICENSING.md) §3 (attribution inherited via E1-E4 upstream: FRED/Eurostat/OECD/ECB SDW).
- **D-block evidence**: [`data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) §3 E1-E4 coverage confirmed; E2 v0.2 bump cascades aqui via precondition update.
- **Cross-validation targets**: hit-ratio vs **NBER** (US recession dating) e **CEPR** (EA recession dating) com walk-forward backtest. Pagan-Sossounov agreement target ≥ 87% per reference.
- **Papers**:
  - Burns A., Mitchell W. (1946), *Measuring Business Cycles*, NBER — foundational cycle framework.
  - Sahm C. (2019), "Direct Stimulus Payments to Individuals", Hamilton Project — Sahm Rule labor weakness trigger.
  - OECD (2025), Composite Leading Indicators methodology — CLI cross-check para E2.

## 11. Non-requirements

- Does not compute sub-indices (E1-E4) — those are separate specs under [`docs/specs/indices/economic/`](../../indices/economic/). ECS só agrega + classifica.
- Does not compute stagflation Triggers B/C/D (inflation entrenchment, oil shocks, wage-price spirals) — v0.1 implements Trigger A only (score/CPI/labor composite). Phase 2+ adds full trigger set.
- Does not emit L5 regime table separately — `stagflation_overlay_active` lives as column in `economic_cycle_scores` v0.1. Separate L5 regime tables (with transition probabilities, duration distributions) é Phase 2+.
- Does not backfill historical ECS — `pipelines/backfill-strategy` owns this.
- Does not do intraday re-classification — daily EOD batch; regime é locked para `(country, date)` após persist.
- Does not compute Recovery regime explicitly — Cap 15.7 alternative 6-phase scheme (inclui `Recovery` como "rising from RECESSION") é editorial post-processing, não storage state. 4-state scheme é canonical em v0.1.
- Does not implement matriz 4-way aqui — classificação cross-cycle (ECS × CCCS × MSC × FCS) vive em [`integration/matriz-4way`](../integration/) (Phase 2+).
- Does not enforce regime transition direction — anti-whipsaw é symmetric (applies para upgrades e downgrades).
- Does not expose `prev_regime` / buffer state externally — internal state machine; consumers get only canonical persisted row.
- Does not apply tier-aware confidence cap beyond Policy 1 (re-weight at 0.75) — per-tier caps (T2 0.85, T3 0.65, T4 fail) são Phase 1+ pipeline integration per ADR-0005 §Consequences; ECS spec-level assume sub-indices inherem tier caps upstream.
- Does not re-derive sub-indices post-bump upstream (ex: E2 v0.1 → v0.2 em Bloco E2) — ECS consume sub-index rows verbatim via methodology_version match; precondition E2 aceita v0.2 para compatibility.
