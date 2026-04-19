# E1 — Activity (Coincident) — Spec

> Layer L3 · index · cycle: `economic` · slug: `e1-activity` · methodology_version: `E1_ACTIVITY_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E2)

## 1. Purpose

Compute o sub-índice **Activity** do Economic Cycle Score, agregando 6 indicadores coincident (hard data) numa única métrica `[0, 100]` por `(country, date)`. Foundation layer do ECS — captura "onde a economia está agora", não onde vai (E2) nem o que sente (E4). Output canónico consumido por `cycles/economic-ecs` (L4) com peso 35%.

## 2. Inputs

| Name | Type | Constraints | Source |
|---|---|---|---|
| `gdp_yoy` | `float` | YoY % change real GDP, decimal | `connectors/fred` (`GDPC1`) · `connectors/eurostat` (`namq_10_gdp`) |
| `industrial_production_yoy` | `float` | YoY % change real IP | `connectors/fred` (`INDPRO`) · `connectors/eurostat` (`sts_inpr_m`) |
| `employment_yoy` | `float` | YoY % change non-farm payrolls (headline employment) | `connectors/fred` (`PAYEMS`) · `connectors/eurostat` (`lfsi_emp_m`) · `connectors/ons` (UK) |
| `retail_sales_real_yoy` | `float` | YoY % change real retail | `connectors/fred` (`RRSFS`) · `connectors/eurostat` (`sts_trtu_m`) |
| `personal_income_ex_transfers_yoy` | `float` | YoY % change real personal income ex transfers | `connectors/fred` (`W875RX1`); EA: derived/proxy |
| `pmi_composite` | `float` | level (50 = neutral) | `connectors/spglobal_pmi` · `connectors/ism` (US) |
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | month-end (monthly cadence) | param |
| `lookback_years` | `int` | 10 (canonical) · 7 (Tier 4) | config (`indices/economic/README.md`) |

### Preconditions

Invariantes antes da invocação:

- ≥4 dos 6 sub-componentes disponíveis para `(country_code, date)`; senão raise `InsufficientDataError`.
- Cada componente disponível tem ≥ `lookback_years · 12 · 0.8` observações históricas para z-score robusto; senão flag `INSUFFICIENT_HISTORY` e cap confidence.
- Connectors fornecem séries already seasonally-adjusted (SA) onde aplicável; YoY computado upstream.
- `date` é month-end calendar (não business day — frequência mensal canónica).
- Schema da tabela `idx_economic_e1_activity` migrada à `methodology_version` runtime; senão `VersionMismatchError`.
- GDP é trimestral (lag de 30d); para meses sem GDP release, usa-se o último valor publicado (forward-fill com flag `STALE` se >90 dias).

## 3. Outputs

Uma row por `(country_code, date, methodology_version)`:

| Field | Type | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | `[0, 100]` (50 = trend) | `idx_economic_e1_activity` |
| `score_raw` | `float` | weighted-mean z-score | idem |
| `components_json` | `str` (JSON) | per-component {raw, z, weight, contribution} | idem |
| `components_available` | `int` | 1..6 | idem |
| `lookback_years` | `int` | 7 ou 10 | idem |
| `confidence` | `float` | `[0, 1]` | idem |
| `flags` | `str` (CSV) | tokens em `conventions/flags.md` | idem |
| `methodology_version` | `str` | `E1_ACTIVITY_v0.1` | idem |

**Canonical JSON shape** (`components_json`):

```json
{
  "gdp_yoy":                       {"raw": 0.024, "z": 0.45, "weight": 0.25, "contribution": 0.1125},
  "employment_yoy":                {"raw": 0.018, "z": 0.30, "weight": 0.20, "contribution": 0.0600},
  "industrial_production_yoy":     {"raw": 0.011, "z": 0.10, "weight": 0.15, "contribution": 0.0150},
  "pmi_composite":                 {"raw": 51.2,  "z": 0.20, "weight": 0.15, "contribution": 0.0300},
  "personal_income_ex_transfers":  {"raw": 0.022, "z": 0.40, "weight": 0.15, "contribution": 0.0600},
  "retail_sales_real_yoy":         {"raw": 0.013, "z": 0.15, "weight": 0.10, "contribution": 0.0150}
}
```

## 4. Algorithm

> **Units**: ratios/growth rates em decimal (`0.024` = 2.4% YoY), per `conventions/units.md`. PMI como `float` level. Score `[0, 100]` é display-friendly mas storage canónico (não bps).

**Weights** (per Cap 7.12 do manual de referência; ver `reference/indices/economic/E1-activity.md`):

| Component | Weight |
|---|---|
| `gdp_yoy` | 0.25 |
| `employment_yoy` | 0.20 |
| `industrial_production_yoy` | 0.15 |
| `pmi_composite` | 0.15 |
| `personal_income_ex_transfers_yoy` | 0.15 |
| `retail_sales_real_yoy` | 0.10 |

**Pipeline per `(country, date)`**:

1. Fetch each of 6 components from connectors; track `available` set.
2. Para cada componente disponível: compute z-score numa janela rolling de `lookback_years * 12` meses terminada em `date − 1` (excluir current point para evitar look-ahead).
3. Se `len(available) < 4`: raise `InsufficientDataError` (não persistir).
4. **Re-normalize weights** sobre o set disponível: `w'_i = w_i / Σ_{j ∈ available} w_j`.
5. `score_raw = Σ_{i ∈ available} w'_i · z_i` (weighted z-score).
6. **Map to [0, 100]**: `score_normalized = clip(50 + 16.67 · score_raw, 0, 100)` (3σ ≈ ±50 pontos do centro; mapping documentado em `economic/README.md`).
7. Build `components_json` com `{raw, z, weight, contribution}` per available component.
8. Compute `confidence` (ver §6 matrix).
9. Persist single row na `idx_economic_e1_activity` com `methodology_version = E1_ACTIVITY_v0.1`.

**Sub-classification (informational, não persistido como column)**:

- `score_normalized > 70`: Strong Expansion
- `60-70`: Expansion
- `45-60`: Near-trend
- `30-45`: Slowdown
- `20-30`: Recession (mild) — *placeholder threshold, recalibrate after 24m of production data*
- `< 20`: Recession (severe)

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | arrays, rolling stats |
| `pandas` | 2.1 | rolling z-score, time-series alignment |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network calls inside the algorithm — connectors pré-fetcham série mensal completa para z-score window.

## 6. Edge cases

Flags catalog → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md). Confidence impact aplicado conforme `flags.md` § "Convenção de propagação".

| Trigger | Handling | Confidence |
|---|---|---|
| `< 4` componentes disponíveis | raise `InsufficientDataError` | n/a |
| 4-5 componentes disponíveis | re-weight; flag `E1_PARTIAL_COMPONENTS` | −0.10 per missing |
| Componente individual com `< lookback_years · 12 · 0.8` obs | flag `INSUFFICIENT_HISTORY` | −0.10 (no componente) |
| GDP forward-filled `>90` dias | flag `STALE` | −0.20 |
| PMI ausente para Tier 3 (PT, IE, NL, ...) | skip PMI; re-weight; flag `E1_PARTIAL_COMPONENTS` | −0.10 |
| GDP/GDI material divergence (`>1pp` annualized) | manter GDP; flag `E1_GDP_GDI_DIVERGENCE` | −0.05 |
| Country tier 4 (CN, IN, BR, TR) | usar `lookback_years=7`; flag `EM_COVERAGE` | cap 0.70 |
| Stored `methodology_version ≠` runtime | raise `VersionMismatchError` | n/a |
| Connector retorna NaN inesperado | raise `InvalidInputError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/e1-activity/` as `<id>.json`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01` | all 6 components, US Jan 2024 | `score_normalized ≈ 58 ± 4`, `components_available=6`, `confidence ≥ 0.85` | ±4 pts |
| `us_2009_03` | trough of GFC | `score_normalized < 20`, no flags except `STALE` allowed | — |
| `us_2020_04` | Covid trough | `score_normalized < 15`, severe contraction zone | — |
| `us_2022_06` | Covid recovery, mid-cycle | `45 < score_normalized < 65` | ±5 pts |
| `ea_2012_06` | EA debt crisis | `score_normalized < 30` | — |
| `pt_2023_06` | partial: no PMI | `components_available=5`, flag `E1_PARTIAL_COMPONENTS` | — |
| `cn_2024_01_em` | CN, Tier 4 | `confidence ≤ 0.70`, flag `EM_COVERAGE` | — |
| `insufficient_3_only` | only 3 components | raises `InsufficientDataError` | n/a |
| `gdp_gdi_divergence_2022_q2` | US Q2 2022 (GDP −0.6%, GDI +1.4%) | flag `E1_GDP_GDI_DIVERGENCE` | — |

## 8. Storage schema

```sql
CREATE TABLE idx_economic_e1_activity (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,                 -- month-end
    methodology_version      TEXT    NOT NULL,                 -- 'E1_ACTIVITY_v0.1'
    score_normalized         REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw                REAL    NOT NULL,                 -- weighted z-score
    components_json          TEXT    NOT NULL,                 -- {component: {raw,z,weight,contribution}}
    components_available     INTEGER NOT NULL CHECK (components_available BETWEEN 4 AND 6),
    lookback_years           INTEGER NOT NULL,                 -- 7 or 10
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,                              -- CSV (lex order)
    source_connectors        TEXT    NOT NULL,                  -- CSV: fred,eurostat,...
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_e1_cd ON idx_economic_e1_activity (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/economic-ecs` | L4 | `score_normalized` com peso 0.35 no composite ECS |
| `integration/matriz-4way` | L6 | E1 contribution para 4-way cross-cycle pattern (Cap 17) |
| `outputs/editorial` | L7 | `score_normalized` + `components_json` para drill-down dashboards |

## 10. Reference

- **Methodology**: [`docs/reference/indices/economic/E1-activity.md`](../../../reference/indices/economic/E1-activity.md) — Cap 7 do manual.
- **Cycle context**: [`docs/reference/cycles/economic.md`](../../../reference/cycles/economic.md) §15.5 (sub-index structure) + §15.4 (normalization Layer 1).
- **Data sources**: [`docs/data_sources/economic.md`](../../../data_sources/economic.md) §3 (E1 series catalog); [`data_sources/D2_empirical_validation.md`](../../../data_sources/D2_empirical_validation.md) §3 FRED core series fresh.
- **Architecture**: [`specs/conventions/patterns.md`](../../conventions/patterns.md) §Pattern 4 (TE primary + native overrides); [`adr/ADR-0005-country-tiers-classification.md`](../../../adr/ADR-0005-country-tiers-classification.md) (tier scope).
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §3 (FRED/Eurostat attribution).
- **Cross-validation**: Chicago Fed CFNAI (`CFNAIMA3`); ADS Index (Philly Fed). Targets: SONAR `score_normalized` correlation com CFNAI ≥ 0.80 over 2000-2024. (Nota: Conference Board Coincident Index `USSLIND` descontinuado 2020 per D2 — removido desta lista.)

## 11. Non-requirements

Scope boundaries — o que **não** é responsabilidade do E1:

- Does not compute leading-style projections (3-12M ahead) — vive em `indices/economic/E2-leading`.
- Does not interpret labor-market depth (Sahm Rule, JOLTS, claims) — `indices/economic/E3-labor`.
- Does not measure sentiment ou expectations — `indices/economic/E4-sentiment`.
- Does not aggregate em ECS composite — vive em `cycles/economic-ecs` (P5).
- Does not classify recession phase — phase mapping (Strong Expansion, Slowdown, Recession) é responsabilidade do cycle layer (L4), não do índice.
- Does not handle GDP nowcasting (GDPNow, NY Fed Nowcast, STLENI) — vive em `pipelines/nowcast-economic` (futuro).
- Does not detect stagflation — `cycles/economic-ecs` § stagflation triggers (Cap 16).
- Does not refit weights real-time — pesos são static per `methodology_version`; recalibração é bump MAJOR/MINOR via `conventions/methodology-versions.md`.
- Does not emit partial output quando `< 4` components — raise early, no stub rows.
- Does not consume outputs de E2/E3/E4 — os 4 indices são paralelos por design (Cap 15.5).
