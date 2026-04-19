# E2 — Leading Indicators — Spec

> Layer L3 · index · cycle: `economic` · slug: `e2-leading` · methodology_version: `E2_LEADING_v0.2`
> Last review: 2026-04-19 (Phase 0 Bloco E2)
> v0.2 rationale (breaking): remove `USSLIND` (Philly Fed State Leading Index) como primary LEI source — descontinuado 2020-02 per D2 empirical (2 268d stale vs 2026-04-19). US E2 LEI = GAP actual pending `CAL-023`. Per `conventions/methodology-versions.md` — MINOR bump porque schema inalterado (fallback source swap).

## 1. Purpose

Compute o sub-índice **Leading** do Economic Cycle Score, agregando 8 indicadores forward-looking (yield curve, credit spreads, PMI new orders, building permits, capex orders, LEI, OECD CLI) numa métrica `[0, 100]` por `(country, date)`. Captura "para onde a economia vai" no horizonte 3-12M. Output canónico consumido por `cycles/economic-ecs` (L4) com peso 25%.

## 2. Inputs

| Name | Type | Constraints | Source |
|---|---|---|---|
| `yield_curve_10y_3m_bps` | `int` | spread em bps (`int`); per `units.md` | `overlays/nss-curves` (`yield_curves_spot`) |
| `credit_spread_hy_oas_bps` | `int` | HY OAS bps | `connectors/fred` (`BAMLH0A0HYM2`) |
| `pmi_manufacturing_new_orders` | `float` | level (50 = neutral) | `connectors/spglobal_pmi` · `connectors/ism` (`NAPMNOI`) |
| `pmi_composite_change` | `float` | MoM change in level | `connectors/spglobal_pmi` |
| `building_permits_yoy` | `float` | YoY % change, decimal | `connectors/fred` (`PERMIT`) · `connectors/eurostat` (building permits) |
| `core_capex_orders_yoy` | `float` | YoY % change non-defense capital goods ex-aircraft | `connectors/fred` (`ANDEV`) |
| `lei_6m_growth` | `float` | 6M annualized % growth Conference Board LEI | **GAP per D2** — `USSLIND` descontinuado 2020 (CAL-023 pending alternative: `USPHCI` Philly Fed ADS, ECRI WLI scrape, ou Conference Board paid). Component marcado `NULL` até resolução; E2 re-weight para 7 components disponíveis. |
| `oecd_cli_6m_growth` | `float` | 6M change in OECD CLI | `connectors/oecd` (`MEI_CLI`) |
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | month-end | param |
| `lookback_years` | `int` | 10 (canonical) · 7 (Tier 4) | config |

### Preconditions

Invariantes antes da invocação:

- ≥5 dos 8 sub-componentes disponíveis para `(country_code, date)`; senão raise `InsufficientDataError`.
- `yield_curves_spot` row existe para `(country_code, date)` com `confidence ≥ 0.50`; senão flag `OVERLAY_MISS` e skip yield-curve component.
- Para Tier 1/2 (US, EA, DE, UK, JP, FR, IT, ES, CA, AU): yield curve component é mandatory; sua ausência reduz `components_available` mas não fail (re-weight).
- Cada componente disponível: ≥ `lookback_years · 12 · 0.8` obs históricas; senão flag `INSUFFICIENT_HISTORY`.
- Stored `nss-curves.methodology_version` row bate com runtime ou `VersionMismatchError`.
- LEI (Conference Board) é US-only; Tier 2-3 países sem LEI usam OECD CLI como single composite.

## 3. Outputs

Uma row por `(country_code, date, methodology_version)`:

| Field | Type | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | `[0, 100]` (50 = neutral, baixo = recession warning) | `idx_economic_e2_leading` |
| `score_raw` | `float` | weighted z-score | idem |
| `components_json` | `str` (JSON) | per-component {raw, z, weight, contribution} | idem |
| `components_available` | `int` | 5..8 | idem |
| `lookback_years` | `int` | 7 ou 10 | idem |
| `confidence` | `float` | `[0, 1]` | idem |
| `flags` | `str` (CSV) | tokens em `conventions/flags.md` | idem |
| `methodology_version` | `str` | `E2_LEADING_v0.2` | idem |

**Canonical JSON shape** (`components_json`):

```json
{
  "yield_curve_10y_3m_bps":      {"raw": -45, "z": -1.20, "weight": 0.25, "contribution": -0.30},
  "credit_spread_hy_oas_bps":    {"raw": 425, "z": 0.40,  "weight": 0.10, "contribution": 0.04},
  "pmi_manufacturing_new_orders":{"raw": 47.2,"z": -0.85, "weight": 0.15, "contribution": -0.13},
  "pmi_composite_change":        {"raw": -0.5,"z": -0.30, "weight": 0.15, "contribution": -0.045},
  "building_permits_yoy":        {"raw": -0.18,"z": -1.10,"weight": 0.10, "contribution": -0.11},
  "core_capex_orders_yoy":       {"raw": 0.012,"z": 0.05, "weight": 0.05, "contribution": 0.0025},
  "lei_6m_growth":               {"raw": -0.04,"z": -1.50,"weight": 0.10, "contribution": -0.15},
  "oecd_cli_6m_growth":          {"raw": -0.012,"z": -0.90,"weight": 0.10, "contribution": -0.09}
}
```

## 4. Algorithm

> **Units**: spreads em `int bps` (`yield_curve_*_bps`, `credit_spread_*_bps`); growth rates em decimal (`0.012` = 1.2%); PMI levels como `float`. Score `[0, 100]` storage canónico. Per `conventions/units.md`.

**Weights** (per Cap 8.12 do manual de referência):

| Component | Weight | Sign convention |
|---|---|---|
| `yield_curve_10y_3m_bps` | 0.25 | high spread (steep) → high z (positive for E2) |
| `credit_spread_hy_oas_bps` | 0.10 | **inverted** — high spread → negative z (stress) |
| `pmi_manufacturing_new_orders` | 0.15 | level above 50 → positive z |
| `pmi_composite_change` | 0.15 | positive change → positive z |
| `building_permits_yoy` | 0.10 | high growth → positive z |
| `core_capex_orders_yoy` | 0.05 | high growth → positive z |
| `lei_6m_growth` | 0.10 | positive growth → positive z |
| `oecd_cli_6m_growth` | 0.10 | positive growth → positive z |

**Pipeline per `(country, date)`**:

1. Lookup `yield_curve_10y_3m_bps` from `overlays/nss-curves`. Se `confidence < 0.50` ou row missing: skip + flag `OVERLAY_MISS`.
2. Fetch remaining 7 components from connectors; track `available` set.
3. Para credit spread (HY OAS): **invert sign before z-score** (high spread = financial stress = negative for leading score).
4. Compute z-score por componente sobre `lookback_years * 12` meses terminada em `date − 1`.
5. Se `len(available) < 5`: raise `InsufficientDataError`.
6. **Re-normalize weights** sobre o set disponível: `w'_i = w_i / Σ_{j ∈ available} w_j`.
7. `score_raw = Σ_{i ∈ available} w'_i · z_i`.
8. **Map to [0, 100]**: `score_normalized = clip(50 + 16.67 · score_raw, 0, 100)`.
9. Build `components_json`.
10. Compute `confidence` (ver §6).
11. Persist single row na `idx_economic_e2_leading`.

**Sub-classification (informational, não persistido)**:

- `> 70`: Strong growth ahead
- `55-70`: Modest growth ahead
- `45-55`: Mixed/neutral signals
- `30-45`: Slowdown signaled
- `< 30`: Recession warning — *placeholder threshold, recalibrate after 24m of production data*

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | rolling stats |
| `pandas` | 2.1 | rolling z-score, time-series alignment |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network calls inside the algorithm — connectors + `overlays/nss-curves` pré-fetcham inputs.

## 6. Edge cases

Flags catalog → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| `< 5` componentes disponíveis | raise `InsufficientDataError` | n/a |
| 5-7 componentes disponíveis | re-weight; flag `E2_PARTIAL_COMPONENTS` | −0.10 per missing |
| Yield curve overlay missing / `confidence < 0.50` | skip yield-curve component; flag `OVERLAY_MISS` | cap 0.60 |
| Yield curve overlay carries `STALE` flag | inherit `STALE` no E2 row | inherit −0.20 |
| LEI ausente para non-US (Tier 2/3) | skip; re-weight; flag `E2_PARTIAL_COMPONENTS` | −0.10 |
| LEI US via proxy (quando CAL-023 resolve) | emit `LEI_US_PROXY` + `PROXY_APPLIED` per `proxies.md` registry | −0.10 (multiplicativo) |
| LEI US = GAP (estado actual post-D2; USSLIND descontinued) | skip LEI; re-weight E2 por 7 components; flag `E2_PARTIAL_COMPONENTS` até CAL-023 | −0.10 |
| OECD CLI lag > 90 dias | flag `STALE` | −0.20 |
| Componente individual com `< lookback_years · 12 · 0.8` obs | flag `INSUFFICIENT_HISTORY` | −0.10 (no componente) |
| Country tier 4 | `lookback_years=7`; flag `EM_COVERAGE` | cap 0.70 |
| Stored `methodology_version ≠` runtime | raise `VersionMismatchError` | n/a |
| `nss-curves.methodology_version` mismatch | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/e2-leading/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01` | all 8 components, US Jan 2024 | `40 < score_normalized < 55` (inverted curve regime), `components_available=8` | ±5 pts |
| `us_2007_06` | pre-GFC, yield curve inverted | `score_normalized < 35` | — |
| `us_2009_06` | early recovery, curve steep | `score_normalized > 60`, momentum positive | — |
| `us_2020_03` | Covid trough | `score_normalized < 25`, flag `STALE` aceitável | — |
| `us_2023_07` | Yield curve deeply inverted, PMI weak, equities rallied | `score_normalized < 45` | ±5 pts |
| `ea_2024_01` | EA, 7 components (no LEI) | `components_available=7`, flag `E2_PARTIAL_COMPONENTS` | — |
| `pt_2024_01` | PT, no PMI, no LEI; 6 components | `components_available=6`, flag `E2_PARTIAL_COMPONENTS` | — |
| `nss_overlay_miss` | yield-curve overlay row absent | flag `OVERLAY_MISS`, `components_available=7` | — |
| `insufficient_4_only` | only 4 components | raises `InsufficientDataError` | n/a |

## 8. Storage schema

```sql
CREATE TABLE idx_economic_e2_leading (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,
    methodology_version      TEXT    NOT NULL,                 -- 'E2_LEADING_v0.2'
    score_normalized         REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw                REAL    NOT NULL,
    components_json          TEXT    NOT NULL,
    components_available     INTEGER NOT NULL CHECK (components_available BETWEEN 5 AND 8),
    lookback_years           INTEGER NOT NULL,
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    source_connectors        TEXT    NOT NULL,                  -- CSV: nss-curves,fred,oecd,...
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_e2_cd ON idx_economic_e2_leading (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/economic-ecs` | L4 | `score_normalized` com peso 0.25 no composite ECS |
| `cycles/economic-ecs` | L4 | yield-curve sub-component → recession probability sub-model (Cap 19.6, NY Fed probit) |
| `integration/matriz-4way` | L6 | E2 contribution para 4-way pattern (Cap 17) |
| `outputs/editorial` | L7 | yield-curve regime narrative; `components_json` drill-down |

## 10. Reference

- **Methodology**: [`docs/reference/indices/economic/E2-leading.md`](../../../reference/indices/economic/E2-leading.md) — Cap 8 do manual.
- **Cycle context**: [`docs/reference/cycles/economic.md`](../../../reference/cycles/economic.md) §15.5 + §15.4 + §15.6.
- **Data sources**: [`docs/data_sources/economic.md`](../../../data_sources/economic.md) §4 (E2 series catalog) + §7 (nowcasting context); [`data_sources/D2_empirical_validation.md`](../../../data_sources/D2_empirical_validation.md) §3 `USSLIND` **STALE 6Y** (2020-02 last update) + OECD CLI via SDMX-JSON 2.0 direct fresh (`OECDLOLITOAASTSAM` FRED mirror stale 2022-11 deprecated).
- **Architecture**: [`specs/conventions/patterns.md`](../../conventions/patterns.md) §Pattern 4 (TE primary + native overrides para non-US); [`adr/ADR-0005-country-tiers-classification.md`](../../../adr/ADR-0005-country-tiers-classification.md) (OECD CLI T1-T2 scope).
- **Proxies**: [`specs/conventions/proxies.md`](../../conventions/proxies.md) — `LEI_US_PROXY` entry (decision pending CAL-023).
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §3 (FRED/OECD/ICE BofA attribution).
- **Backlog**: [`backlog/calibration-tasks.md`](../../../backlog/calibration-tasks.md) `CAL-023` — US E2 LEI alternative source (USPHCI, ECRI WLI, Conference Board scrape).
- **Cross-validation**: NY Fed recession probability model (probit on `T10Y3M`); **Conference Board LEI 6M growth signal indisponível sem paid subscription** (paywall confirmed D2; proxy path pending); OECD CLI turning-point detection (Bry-Boschan).

## 11. Non-requirements

Scope boundaries — o que **não** é responsabilidade do E2:

- Does not compute the yield-curve fit itself — vive em `overlays/nss-curves` (consume only).
- Does not compute coincident activity (GDP, IP, employment, retail) — `indices/economic/E1-activity`.
- Does not compute labor-market depth — `indices/economic/E3-labor`.
- Does not compute sentiment ou expectations — `indices/economic/E4-sentiment`.
- Does not aggregate em ECS composite — `cycles/economic-ecs` (P5).
- Does not produce explicit recession probability — esse é output de `cycles/economic-ecs` § recession probability sub-model, não do índice.
- Does not run nowcasting models (GDPNow, NY Fed Nowcast, STLENI) — `pipelines/nowcast-economic`.
- Does not handle ECRI WLI (commercial subscription) em Tier 1/2 MVP — Tier 3 only, fora do scope deste spec.
- Does not refit weights real-time — pesos são static per `methodology_version`.
- Does not emit partial output quando `< 5` components — raise early.
- Does not detect curve regime breaks beyond inheriting `nss-curves` flags (`REGIME_BREAK`, `NSS_FAIL`).
- Does not use `USSLIND` (Philly Fed State Leading Index) como LEI source — **rejected em D2 empirical** (2026-04-18: latest observation 2020-02, 2 268d stale). Per v0.2 bump: LEI US = GAP pending CAL-023 alternative selection (USPHCI, ECRI WLI, Conference Board paid).
