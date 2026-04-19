# E4 — Sentiment & Expectations — Spec

> Layer L3 · index · cycle: `economic` · slug: `e4-sentiment` · methodology_version: `E4_SENTIMENT_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E2)

## 1. Purpose

Compute o sub-índice **Sentiment** do Economic Cycle Score, agregando 13 indicadores survey-based de consumer/business expectations (UMich, Conference Board, ISM, NFIB, EPU, EC ESI, ZEW, Ifo, Tankan) + market-based proxies (VIX) + credit sentiment (SLOOS). Output canónico `[0, 100]` por `(country, date)`. Captura "o que economias sentem", complement (não substitute) à hard data. Consumido por `cycles/economic-ecs` (L4) com peso 15% — lowest do composite por noisier nature.

## 2. Inputs

| Name | Type | Constraints | Source |
|---|---|---|---|
| `umich_sentiment_12m_change` | `float` | 12M change in UMich Consumer Sentiment level | `connectors/fred` (`UMCSENT`) |
| `conference_board_confidence_12m_change` | `float` | 12M change in Conference Board Consumer Confidence | `connectors/fred` (`CSCICP03USM665S`) |
| `umich_5y_inflation_exp` | `float` | UMich 5Y inflation expectations level (decimal) | `connectors/fred` (`MICHM5YM5`) |
| `ism_manufacturing` | `float` | ISM Manufacturing PMI level | `connectors/fred` (`NAPM`) · `connectors/ism` |
| `ism_services` | `float` | ISM Services PMI level | `connectors/fred` (`NAPMII`) · `connectors/ism` |
| `nfib_small_business` | `float` | NFIB Small Business Optimism level | `connectors/fred` (`NFIBBTI`) |
| `epu_index` | `float` | Baker-Bloom-Davis EPU index level | `connectors/policyuncertainty` |
| `ec_esi` | `float` | EC Economic Sentiment Indicator level | `connectors/eurostat` (`ei_bsco_q_r2`) · DG ECFIN |
| `zew_expectations` | `float` | ZEW Indicator of Economic Sentiment (DE/EA) | `connectors/zew` (scrape headline) |
| `ifo_business_climate` | `float` | Ifo Business Climate Index level (DE) | `connectors/ifo` (scrape headline) |
| `vix_level` | `float` | VIX close (monthly avg ou EOM) | `connectors/fred` (`VIXCLS`) |
| `tankan_large_mfg` | `float` | Tankan Large Manufacturers DI (JP, quarterly) | `connectors/boj` |
| `sloos_standards_net_pct` | `float` | SLOOS net % banks tightening C&I (US, quarterly) | `connectors/fred` (`DRTSCILM`) |
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | month-end | param |
| `lookback_years` | `int` | 10 (canonical) · 7 (Tier 4) | config |

### Preconditions

Invariantes antes da invocação:

- ≥6 dos 13 sub-componentes disponíveis para `(country_code, date)`; senão raise `InsufficientDataError`.
- Cada componente disponível: ≥ `lookback_years · 12 · 0.8` obs históricas; senão flag `INSUFFICIENT_HISTORY`.
- Component set varia by country (E4 é o único índice com cobertura cross-country materialmente assimétrica):
  - **US-only components**: UMich, Conference Board, UMich 5Y inflation, ISM Mfg, ISM Services, NFIB, SLOOS, EPU US.
  - **EA-canonical components**: EC ESI, ZEW, Ifo (DE), Sentix (omitted MVP).
  - **JP-canonical**: Tankan.
  - **Cross-market**: VIX (proxy global risk sentiment).
- Tankan e SLOOS são quarterly: forward-fill aceitável dentro do quarter; > 100 dias stale → `STALE` flag.
- EPU index: weekly refresh aceitável; > 21 dias stale → `STALE`.
- `date` é month-end calendar.

## 3. Outputs

Uma row por `(country_code, date, methodology_version)`:

| Field | Type | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | `[0, 100]` (50 = neutral) | `idx_economic_e4_sentiment` |
| `score_raw` | `float` | weighted z-score | idem |
| `components_json` | `str` (JSON) | per-component {raw, z, weight, contribution} | idem |
| `components_available` | `int` | 6..13 | idem |
| `lookback_years` | `int` | 7 ou 10 | idem |
| `confidence` | `float` | `[0, 1]` | idem |
| `flags` | `str` (CSV) | tokens | idem |
| `methodology_version` | `str` | `E4_SENTIMENT_v0.1` | idem |

**Canonical JSON shape** (`components_json`):

```json
{
  "umich_sentiment_12m_change":      {"raw": -2.5, "z": -0.40, "weight": 0.10, "contribution": -0.040},
  "conference_board_confidence_12m": {"raw":  1.2, "z":  0.15, "weight": 0.10, "contribution":  0.015},
  "umich_5y_inflation_exp":          {"raw": 0.030,"z":  0.50, "weight": 0.10, "contribution": -0.050},
  "ism_manufacturing":               {"raw": 49.2, "z": -0.20, "weight": 0.10, "contribution": -0.020},
  "ism_services":                    {"raw": 52.5, "z":  0.30, "weight": 0.10, "contribution":  0.030},
  "nfib_small_business":             {"raw": 91.2, "z": -0.60, "weight": 0.05, "contribution": -0.030},
  "epu_index":                       {"raw": 145,  "z":  0.50, "weight": 0.05, "contribution": -0.025},
  "ec_esi":                          {"raw": 95.8, "z": -0.30, "weight": 0.10, "contribution": -0.030},
  "zew_expectations":                {"raw": 12.5, "z":  0.10, "weight": 0.10, "contribution":  0.010},
  "ifo_business_climate":            {"raw": 86.4, "z": -0.45, "weight": 0.05, "contribution": -0.0225},
  "vix_level":                       {"raw": 18.2, "z":  0.10, "weight": 0.05, "contribution": -0.005},
  "tankan_large_mfg":                {"raw": 12.0, "z":  0.40, "weight": 0.05, "contribution":  0.020},
  "sloos_standards_net_pct":         {"raw": 18.5, "z":  0.85, "weight": 0.05, "contribution": -0.0425}
}
```

> **Nota**: o `contribution` field reflete o sign-corrected effect on `score_raw` — alguns componentes são inverted (high raw → bad for sentiment), conforme tabela §4.

## 4. Algorithm

> **Units**: PMI/sentiment levels como `float`; UMich 5Y inflation expectations em decimal (`0.030` = 3.0%); EPU index level como `float`; VIX level como `float`; SLOOS net % como `float` (positive = tightening). Score `[0, 100]` storage canónico. Per `conventions/units.md`.

**Weights** (per Cap 10.10 do manual de referência):

| Component | Weight | Sign convention |
|---|---|---|
| `umich_sentiment_12m_change` | 0.10 | rising → positive z |
| `conference_board_confidence_12m_change` | 0.10 | rising → positive z |
| `umich_5y_inflation_exp` | 0.10 | **inverted** — high = de-anchoring concern → negative z |
| `ism_manufacturing` | 0.10 | level above 50 → positive z |
| `ism_services` | 0.10 | level above 50 → positive z |
| `nfib_small_business` | 0.05 | rising → positive z |
| `epu_index` | 0.05 | **inverted** — high uncertainty → negative z |
| `ec_esi` | 0.10 | rising → positive z |
| `zew_expectations` | 0.10 | positive → positive z |
| `ifo_business_climate` | 0.05 | rising → positive z |
| `vix_level` | 0.05 | **inverted** — high VIX = fear → negative z |
| `tankan_large_mfg` | 0.05 | positive DI → positive z |
| `sloos_standards_net_pct` | 0.05 | **inverted** — high net tightening → negative z |

Total weight sum = 1.00. **Country-specific adjustment**: para non-US, US-only components são skipped e weights re-normalized (ex: PT typically lê EC ESI peso elevado, ZEW/Ifo via EA overlay, omits ISM/UMich/NFIB).

**Pipeline per `(country, date)`**:

1. Fetch each of 13 components from connectors; track `available` set conforme country profile.
2. Para componentes inverted-sign (`umich_5y_inflation_exp`, `epu_index`, `vix_level`, `sloos_standards_net_pct`): **invert sign before z-score**.
3. Compute z-score por componente sobre `lookback_years * 12` meses terminada em `date − 1`.
4. Se `len(available) < 6`: raise `InsufficientDataError`.
5. **Re-normalize weights** sobre o set disponível: `w'_i = w_i / Σ_{j ∈ available} w_j`.
6. `score_raw = Σ_{i ∈ available} w'_i · z_i`.
7. **Map to [0, 100]**: `score_normalized = clip(50 + 16.67 · score_raw, 0, 100)`.
8. Build `components_json`.
9. Compute `confidence` (ver §6).
10. Persist single row na `idx_economic_e4_sentiment`.

**Sub-classification (informational, não persistido)**:

- `> 70`: Strong positive sentiment across board
- `55-70`: Generally positive
- `45-55`: Neutral
- `30-45`: Concerning deterioration
- `< 30`: Widespread pessimism (recession territory) — *placeholder threshold, recalibrate after 24m of production data*

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | rolling stats |
| `pandas` | 2.1 | rolling z-score, time-series alignment |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network calls inside the algorithm — connectors pré-fetcham.

## 6. Edge cases

Flags catalog → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| `< 6` componentes disponíveis | raise `InsufficientDataError` | n/a |
| 6-12 componentes disponíveis | re-weight; flag `E4_PARTIAL_COMPONENTS` | −0.05 per missing (lower than E1-E3 porque sentiment é noisier) |
| Country é non-US: ISM/UMich/NFIB/SLOOS skip | re-weight by country profile (no penalty) | n/a (expected per country tier) |
| EPU > 21 dias stale | flag `STALE` | −0.20 |
| Tankan > 100 dias stale (out-of-quarter) | forward-fill; flag `STALE` | −0.20 |
| SLOOS > 100 dias stale | forward-fill; flag `STALE` | −0.20 |
| ZEW/Ifo scrape failure | skip component; flag `OVERLAY_MISS` | −0.05 |
| Componente individual com `< lookback_years · 12 · 0.8` obs | flag `INSUFFICIENT_HISTORY` | −0.10 (no componente) |
| Sentiment-vs-hard-data divergence: `|E4 − E1| > 30 pts` | flag `E4_SENTIMENT_DIVERGENCE` | informational (none direct) |
| Country tier 4 | `lookback_years=7`; flag `EM_COVERAGE` | cap 0.70 |
| Stored `methodology_version ≠` runtime | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/e4-sentiment/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01` | all US-applicable components, US Jan 2024 | `45 < score_normalized < 60`, `components_available ≥ 10` | ±5 pts |
| `us_2009_03` | GFC trough sentiment | `score_normalized < 25` | — |
| `us_2020_04` | Covid trough | `score_normalized < 30` | — |
| `us_2022_06` | UMich collapse but economy growing | `score_normalized < 40`, flag `E4_SENTIMENT_DIVERGENCE` (vs E1) | — |
| `de_2024_01` | DE: Ifo + ZEW + EC ESI + VIX | `components_available=4`, flag `E4_PARTIAL_COMPONENTS` | — |
| `pt_2024_01` | PT: EC ESI + ZEW + VIX (no PT-specific surveys MVP) | `components_available=3` → raises `InsufficientDataError` | n/a |
| `pt_2024_01_with_overlay` | PT + EA overlay (ESI + ZEW + Ifo + VIX + EPU global) | `components_available=5` → still raises (need ≥6) | n/a |
| `jp_2024_01` | JP: Tankan + VIX + EC ESI (proxy) | `components_available=3` → raises `InsufficientDataError` | n/a |
| `cn_2024_01_em` | CN: minimal sentiment coverage | raises `InsufficientDataError` (Tier 4 sentiment caveat) | n/a |
| `us_partial_zew_ifo_miss` | scrape failed for ZEW + Ifo | `components_available=11`, flag `OVERLAY_MISS` (×2) | — |

> **Note**: PT/JP fixtures intentionally show that E4 has materially weaker country coverage than E1-E3. This is documented gap in `economic/README.md` § Country coverage and reflects the manual's sentiment-as-noisier framing.

## 8. Storage schema

```sql
CREATE TABLE idx_economic_e4_sentiment (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,
    methodology_version      TEXT    NOT NULL,                 -- 'E4_SENTIMENT_v0.1'
    score_normalized         REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw                REAL    NOT NULL,
    components_json          TEXT    NOT NULL,
    components_available     INTEGER NOT NULL CHECK (components_available BETWEEN 6 AND 13),
    lookback_years           INTEGER NOT NULL,
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    source_connectors        TEXT    NOT NULL,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_e4_cd ON idx_economic_e4_sentiment (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/economic-ecs` | L4 | `score_normalized` com peso 0.15 no composite ECS |
| `cycles/economic-ecs` | L4 | `umich_5y_inflation_exp` sub-component → stagflation triggers (Cap 16.6) |
| `integration/matriz-4way` | L6 | E4 contribution para 4-way pattern; sentiment é check em euphoria/dilemma flags |
| `outputs/editorial` | L7 | sentiment narrative, "sentiment vs reality" angle quando `E4_SENTIMENT_DIVERGENCE` activo |

## 10. Reference

- **Methodology**: [`docs/reference/indices/economic/E4-sentiment.md`](../../../reference/indices/economic/E4-sentiment.md) — Cap 10 do manual.
- **Cycle context**: [`docs/reference/cycles/economic.md`](../../../reference/cycles/economic.md) §15.5 + §15.4 + §15.6 + §16.6 (stagflation diagnostics).
- **Data sources**: [`docs/data_sources/economic.md`](../../../data_sources/economic.md) §6 (E4 series catalog) + §6.9 (EPU access); [`data_sources/D2_empirical_validation.md`](../../../data_sources/D2_empirical_validation.md) §3 `UMCSENT`/`VIXCLS` fresh (Conference Board `CSCICP03USM665S` OECD-mirror série não testada D-block — verify freshness Phase 1, potential stale risk per FRED-mirror pattern observed em OECDLOLITOAASTSAM).
- **Architecture**: [`specs/conventions/patterns.md`](../../conventions/patterns.md) §Pattern 4 (global proxy VIX per Pattern 4 matrix).
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §3 (FRED/Eurostat/DG ECFIN attribution); EPU public academic use.
- **Papers**:
  - Baker S., Bloom N., Davis S. (2016), "Measuring Economic Policy Uncertainty", *QJE* 131(4) — EPU index methodology.
  - Curtin R. (2019), "Consumer Expectations: Micro Foundations and Macro Impact", Cambridge — UMich survey methodology.
- **Cross-validation**: SONAR `score_normalized` correlation with single-survey sentiment composites — UMich + Conf Board for US (target ≥ 0.85), EC ESI for EA (target ≥ 0.80) over 2010-2024.

## 11. Non-requirements

Scope boundaries — o que **não** é responsabilidade do E4:

- Does not compute coincident hard activity — `indices/economic/E1-activity`.
- Does not compute leading financial signals (yield curve, credit spreads) — `indices/economic/E2-leading`. (Note: VIX appears in E4 as risk-sentiment proxy, not as leading credit indicator.)
- Does not compute labor-market depth — `indices/economic/E3-labor`.
- Does not aggregate em ECS composite — `cycles/economic-ecs` (P5).
- Does not detect stagflation entrenchment trigger end-to-end — fornece `umich_5y_inflation_exp` como input; trigger compositional vive em `cycles/economic-ecs § stagflation` (Cap 16).
- Does not handle inflation expectations cross-validation BEI vs SURVEY — vive em `overlays/expected-inflation`.
- Does not compute AAII Investor Sentiment Survey ou GDELT news analytics em MVP — Tier 3 only, fora deste spec.
- Does not source full ZEW/Ifo/Sentix component detail (subscription) — MVP usa headline scrape only.
- Does not consume outputs de E1/E2/E3 — paralelo por design (Cap 15.5). (Divergence flag `E4_SENTIMENT_DIVERGENCE` é raised por `cycles/economic-ecs`, não pelo índice.)
- Does not refit weights real-time — pesos static per `methodology_version`; country-specific weight profiles documented em runtime config.
- Does not emit partial output quando `< 6` components — raise early.
- Does not detect political-event-driven sentiment shocks (debt ceiling, shutdowns) explicitly — those manifest no EPU sub-component.
