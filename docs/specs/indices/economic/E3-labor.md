# E3 — Labor Market Depth — Spec

> Layer L3 · index · cycle: `economic` · slug: `e3-labor` · methodology_version: `E3_LABOR_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E2)

## 1. Purpose

Compute o sub-índice **Labor** do Economic Cycle Score, agregando 10 indicadores multi-dimensionais de labor market — Sahm Rule discrete trigger, unemployment dynamics, employment-population, wage growth, JOLTS turnover, weekly claims, temp help. Output canónico `[0, 100]` por `(country, date)`. Captura tanto coincident como leading propriedades do labor market. Consumido por `cycles/economic-ecs` (L4) com peso 25%.

## 2. Inputs

| Name | Type | Constraints | Source |
|---|---|---|---|
| `unemployment_rate_12m_change` | `float` | pp change vs 12m ago, decimal (`0.005` = +0.5pp) | `connectors/fred` (`UNRATE`) · `connectors/eurostat` (`une_rt_m`) |
| `sahm_rule_value` | `float` | U-3 3MA − min(3MA, last 12m); decimal pp | computed (FRED `SAHMCURRENT` proxy) |
| `employment_population_ratio_12m_z` | `float` | 12M change z-scored | `connectors/fred` (`EMRATIO`) |
| `prime_age_lfpr_12m_change` | `float` | pp change | `connectors/fred` (`LNS11300060`) |
| `eci_yoy_growth` | `float` | YoY % growth Employment Cost Index | `connectors/fred` (`ECIWAG`) — quarterly |
| `atlanta_fed_wage_yoy` | `float` | YoY % growth Atlanta Fed Wage Tracker | `connectors/atlanta_fed` |
| `openings_unemployed_ratio` | `float` | JOLTS openings / unemployed | `connectors/fred` (`JTSJOL` ÷ unemployed level) |
| `quits_rate` | `float` | quits / employment, monthly | `connectors/fred` (`JTSQUL`) |
| `initial_claims_4wk_avg` | `float` | thousands per week, 4-wk MA | `connectors/fred` (`IC4WSA`) |
| `temp_help_employment_yoy` | `float` | YoY % change temp help payrolls | `connectors/fred` (`TEMPHELPS`) |
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | month-end | param |
| `lookback_years` | `int` | 10 (canonical) · 7 (Tier 4) | config |

### Preconditions

Invariantes antes da invocação:

- ≥6 dos 10 sub-componentes disponíveis para `(country_code, date)`; senão raise `InsufficientDataError`.
- Unemployment rate é mandatory (necessário para Sahm computation); sua ausência é fail.
- Cada componente disponível: ≥ `lookback_years · 12 · 0.8` obs históricas; senão flag `INSUFFICIENT_HISTORY`.
- JOLTS é US-only operationally; EA equivalent (`jvs_q_nace2`) tem cobertura parcial e quarterly cadence — para non-US, JOLTS components skip permitido.
- ECI é quarterly (US): para meses sem release, forward-fill com `STALE` flag se >100 dias.
- `date` é month-end calendar.
- Schema migrada à `methodology_version` runtime; senão `VersionMismatchError`.

## 3. Outputs

Uma row por `(country_code, date, methodology_version)`:

| Field | Type | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | `[0, 100]` (50 = neutral, alto = robust labor) | `idx_economic_e3_labor` |
| `score_raw` | `float` | weighted z-score (Sahm contributes via discrete trigger) | idem |
| `sahm_triggered` | `int` | 0 ou 1 — Sahm Rule binary signal | idem |
| `components_json` | `str` (JSON) | per-component {raw, z, weight, contribution} | idem |
| `components_available` | `int` | 6..10 | idem |
| `lookback_years` | `int` | 7 ou 10 | idem |
| `confidence` | `float` | `[0, 1]` | idem |
| `flags` | `str` (CSV) | tokens | idem |
| `methodology_version` | `str` | `E3_LABOR_v0.1` | idem |

**Canonical JSON shape** (`components_json`):

```json
{
  "sahm_rule":                      {"raw": 0.32,  "trigger": 0, "z": -0.85, "weight": 0.20, "contribution": -0.17},
  "unemployment_rate_12m_change":   {"raw": 0.004, "z": 0.40,    "weight": 0.15, "contribution": 0.06},
  "employment_population_ratio":    {"raw": 0.001, "z": 0.10,    "weight": 0.10, "contribution": 0.01},
  "prime_age_lfpr_12m_change":      {"raw": 0.002, "z": 0.30,    "weight": 0.05, "contribution": 0.015},
  "eci_yoy_growth":                 {"raw": 0.038, "z": 0.50,    "weight": 0.10, "contribution": 0.05},
  "atlanta_fed_wage_yoy":           {"raw": 0.041, "z": 0.45,    "weight": 0.05, "contribution": 0.0225},
  "openings_unemployed_ratio":      {"raw": 1.05,  "z": 0.20,    "weight": 0.10, "contribution": 0.02},
  "quits_rate":                     {"raw": 0.022, "z": -0.10,   "weight": 0.05, "contribution": -0.005},
  "initial_claims_4wk_avg":         {"raw": 235,   "z": -0.30,   "weight": 0.10, "contribution": -0.03},
  "temp_help_employment_yoy":       {"raw": -0.012,"z": -0.55,   "weight": 0.10, "contribution": -0.055}
}
```

## 4. Algorithm

> **Units**: rates/changes em decimal (`0.004` = 0.4pp); claims em thousands (raw integer); JOLTS ratios como `float`. Score `[0, 100]` storage canónico. Sahm binary trigger é `int` (0/1). Per `conventions/units.md`.

**Weights** (per Cap 9.13 do manual de referência):

| Component | Weight | Sign convention |
|---|---|---|
| `sahm_rule_value` | 0.20 | **discrete trigger**: high z + binary signal — Sahm > 0.5pp emits `triggered=1` |
| `unemployment_rate_12m_change` | 0.15 | **inverted** — rising UR → negative z |
| `employment_population_ratio_12m_z` | 0.10 | rising → positive z |
| `prime_age_lfpr_12m_change` | 0.05 | rising → positive z |
| `eci_yoy_growth` | 0.10 | wage growth → positive z (pro-labor strength) |
| `atlanta_fed_wage_yoy` | 0.05 | idem |
| `openings_unemployed_ratio` | 0.10 | high ratio = tight market → positive z |
| `quits_rate` | 0.05 | high quits = confidence → positive z |
| `initial_claims_4wk_avg` | 0.10 | **inverted** — rising claims → negative z |
| `temp_help_employment_yoy` | 0.10 | rising temp help → positive z (leading hire signal) |

**Pipeline per `(country, date)`**:

1. Fetch each of 10 components from connectors; track `available` set.
2. **Compute Sahm Rule** internally (mandatory, US-canonical):
   - `ur_3ma = rolling_mean(UNRATE, 3)`
   - `ur_12min = rolling_min(ur_3ma, 12)`
   - `sahm_value = ur_3ma_t − ur_12min_t`
   - `sahm_triggered = 1 if sahm_value >= 0.005 else 0` (0.5pp threshold)
3. Para componentes inverted-sign (`unemployment_rate_12m_change`, `initial_claims_4wk_avg`): **invert sign before z-score**.
4. Compute z-score por componente sobre `lookback_years * 12` meses terminada em `date − 1`.
5. Sahm component contribution combina z-score + discrete bonus: se `sahm_triggered=1`, add `−1.0` to its z (additional penalty); senão use plain z.
6. Se `len(available) < 6`: raise `InsufficientDataError`.
7. **Re-normalize weights** sobre o set disponível.
8. `score_raw = Σ_{i ∈ available} w'_i · z_i`.
9. **Map to [0, 100]**: `score_normalized = clip(50 + 16.67 · score_raw, 0, 100)`.
10. Build `components_json`; persist `sahm_triggered` separadamente (high-priority alert downstream).
11. Compute `confidence` (ver §6).
12. Persist single row na `idx_economic_e3_labor`.

**Sub-classification (informational, não persistido)**:

- `> 70`: Robust labor market
- `55-70`: Healthy
- `45-55`: Neutral
- `30-45`: Weakening
- `< 30`: Deteriorating rapidly (recession mode) — *placeholder threshold, recalibrate after 24m of production data*

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | rolling stats, Sahm computation |
| `pandas` | 2.1 | rolling z-score, time-series alignment |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network calls inside the algorithm.

## 6. Edge cases

Flags catalog → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| `< 6` componentes disponíveis | raise `InsufficientDataError` | n/a |
| 6-9 componentes disponíveis | re-weight; flag `E3_PARTIAL_COMPONENTS` | −0.10 per missing |
| Unemployment rate ausente | raise `InsufficientDataError` (Sahm não computável) | n/a |
| Sahm Rule triggered (`sahm_value ≥ 0.5pp`) | flag `E3_SAHM_TRIGGERED`; alert P0 (downstream) | none direct (sinal informacional, não confidence penalty) |
| JOLTS unavailable (non-US, EA partial) | skip JOLTS components; flag `E3_PARTIAL_COMPONENTS` | −0.10 per missing |
| ECI > 100 dias stale | forward-fill; flag `STALE` | −0.20 |
| Claims weekly source `> 14` dias stale | flag `STALE` | −0.20 |
| Componente individual com `< lookback_years · 12 · 0.8` obs | flag `INSUFFICIENT_HISTORY` | −0.10 (no componente) |
| Country tier 4 | `lookback_years=7`; flag `EM_COVERAGE` | cap 0.70 |
| Stored `methodology_version ≠` runtime | raise `VersionMismatchError` | n/a |
| Beveridge curve outward shift detected (companion diagnostic) | informational only — flag emitted by `cycles/economic-ecs`, not E3 | n/a (out of scope) |

## 7. Test fixtures

Stored in `tests/fixtures/e3-labor/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01` | all 10 components, US Jan 2024 | `score_normalized ≈ 60 ± 5`, `sahm_triggered=0`, `components_available=10` | ±5 pts |
| `us_2009_01` | GFC peak unemployment | `score_normalized < 25`, `sahm_triggered=1`, flag `E3_SAHM_TRIGGERED` | — |
| `us_2020_05` | Covid trough | `score_normalized < 15`, `sahm_triggered=1` | — |
| `us_2024_07_sahm_trip` | Sahm just triggered (UR rises +0.5pp) | `sahm_triggered=1`, flag `E3_SAHM_TRIGGERED`, score drops materially | — |
| `us_2022_06` | tight labor market post-Covid | `score_normalized > 70`, `openings_unemployed_ratio > 1.8` | — |
| `ea_2024_01` | EA, no JOLTS, no Atlanta Fed | `components_available=7`, flag `E3_PARTIAL_COMPONENTS` | — |
| `pt_2023_01` | PT, no JOLTS, no Atlanta Fed, no temp-help YoY | `components_available=6`, flag `E3_PARTIAL_COMPONENTS` | — |
| `cn_2024_01_em` | CN Tier 4 | `confidence ≤ 0.70`, flag `EM_COVERAGE` | — |
| `insufficient_5_only` | only 5 components | raises `InsufficientDataError` | n/a |

## 8. Storage schema

```sql
CREATE TABLE idx_economic_e3_labor (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,
    methodology_version      TEXT    NOT NULL,                 -- 'E3_LABOR_v0.1'
    score_normalized         REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw                REAL    NOT NULL,
    sahm_triggered           INTEGER NOT NULL CHECK (sahm_triggered IN (0, 1)),
    sahm_value               REAL,                              -- raw Sahm value (decimal pp)
    components_json          TEXT    NOT NULL,
    components_available     INTEGER NOT NULL CHECK (components_available BETWEEN 6 AND 10),
    lookback_years           INTEGER NOT NULL,
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    source_connectors        TEXT    NOT NULL,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_e3_cd ON idx_economic_e3_labor (country_code, date);
CREATE INDEX idx_e3_sahm ON idx_economic_e3_labor (country_code, sahm_triggered, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/economic-ecs` | L4 | `score_normalized` com peso 0.25 no composite ECS |
| `cycles/economic-ecs` | L4 | `sahm_triggered` → recession probability sub-model (Cap 19.5, weight 0.25 in 8-input composite) |
| `integration/matriz-4way` | L6 | E3 contribution para 4-way pattern |
| `outputs/alerts` | L7 | `sahm_triggered=1` → P0 push notification (Cap 19; data_sources B.5) |
| `outputs/editorial` | L7 | labor narrative; Sahm + JOLTS drill-down |

## 10. Reference

- **Methodology**: [`docs/reference/indices/economic/E3-labor.md`](../../../reference/indices/economic/E3-labor.md) — Cap 9 do manual.
- **Cycle context**: [`docs/reference/cycles/economic.md`](../../../reference/cycles/economic.md) §15.5 + §15.4 + §15.6.
- **Data sources**: [`docs/data_sources/economic.md`](../../../data_sources/economic.md) §5 (E3 series catalog) + §5.2 (Sahm automation) + §B.5 (Sahm alert priority P0); [`data_sources/D2_empirical_validation.md`](../../../data_sources/D2_empirical_validation.md) §3 `UNRATE`/`SAHMREALTIME`/`PAYEMS`/`JTSJOL` fresh.
- **Architecture**: [`specs/conventions/patterns.md`](../../conventions/patterns.md) §Pattern 4; [`adr/ADR-0005-country-tiers-classification.md`](../../../adr/ADR-0005-country-tiers-classification.md) (NFP/JOLTS/Sahm são US-only by design — T1 scope).
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §3 (FRED/Eurostat/Atlanta Fed attribution).
- **Papers**: Sahm C. (2019), "Direct Stimulus Payments to Individuals", Brookings — Sahm Rule construction. Diamond P., Mortensen D., Pissarides C. (DMP) on matching theory (Cap 12.2 reference).
- **Cross-validation**: FRED `SAHMCURRENT` (real-time Sahm) — SONAR internal computation must match within ±0.05pp; NBER recession dating 1970-present (Sahm triggered in every recession, zero false positives target).

## 11. Non-requirements

Scope boundaries — o que **não** é responsabilidade do E3:

- Does not compute coincident headline activity (GDP, IP, retail) — `indices/economic/E1-activity`.
- Does not compute leading financial signals (yield curve, credit spreads) — `indices/economic/E2-leading`.
- Does not compute sentiment ou expectations — `indices/economic/E4-sentiment`.
- Does not aggregate em ECS composite — `cycles/economic-ecs` (P5).
- Does not interpret Beveridge curve position — `cycles/economic-ecs` § structural diagnostics (Cap 12.3).
- Does not compute productivity, ULC, NAIRU estimates — fora de scope (long-run anchors live em `integration/potential-growth`, futuro).
- Does not handle wage-inflation Phillips Curve interaction — `integration/matriz-4way` cross-cycle pattern.
- Does not emit recession probability directly — Sahm trigger é *input* a `cycles/economic-ecs § recession_prob_model`, não output deste índice.
- Does not refit weights real-time — pesos static per `methodology_version`.
- Does not emit partial output quando `< 6` components — raise early.
- Does not consume outputs de E1/E2/E4 — paralelo por design (Cap 15.5).
