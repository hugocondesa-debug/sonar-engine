# F1 · Valuations — Spec

> Layer L3 · indices/financial · slug: `F1-valuations` · methodology_version: `F1_VALUATIONS_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E2)

## 1. Purpose

Quantificar **quão caros estão os asset prices** vs. fundamentals e história, agregando equity (CAPE, Buffett, ERP, fwd P/E), bond term-premium proxy, e real estate (BIS property gap + price/income). Output `score_normalized ∈ [0, 100]` com **higher = mais sobre-valorizado / euforia** — primeiro componente do composite FCS (peso 30%) e input upstream do Bubble Warning overlay (Cap 16).

## 2. Inputs

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | business day local | param |
| `cape_ratio` | `float` | `> 0`, ≤ 60 | `connectors/shiller` (US); `connectors/multpl` ou Barclays/GMO scrape (others) |
| `buffett_ratio` | `float` | `0.2 ≤ x ≤ 3.0`, daily-interpolated GDP | `connectors/fred` (`WILL5000IND` / GDP) |
| `forward_pe` | `float` | `> 0`, ≤ 80 | `connectors/factset_insight` (PDF) ou `connectors/multpl` |
| `erp_median_bps` | `int` | from `overlays/erp-daily.erp_canonical` | overlay L2 |
| `erp_range_bps` | `int` | uncertainty signal | overlay L2 |
| `property_gap_pp` | `float` | percentage points vs trend | `connectors/bis_property` (`bis.org/statistics/pp.htm`) |
| `price_to_income` | `float` | optional Tier 1; INE/Eurostat/OECD | `connectors/oecd_house_price` ou `connectors/ine_pt` |

### Mapping country → equity universe

| country_code | Equity index (CAPE/Buffett source) | ERP market_index lookup |
|---|---|---|
| US | S&P 500 (Shiller `ie_data`) | `SPX` |
| EA / DE / FR / IT / ES / NL / IE | STOXX 600 (Barclays/GMO) | `SXXP` |
| UK | FTSE All-Share (Barclays/GMO) | `FTAS` |
| JP | TOPIX (FactSet PDF) | `TPX` |
| PT | PSI-20 (constructed locally; CAPE synthetic via `connectors/euronext_lisbon`) | falls back para EA `SXXP` |
| CN / IN / BR / TR / MX | best-effort GMO cross-country quarterly; ERP indisponível | none → `OVERLAY_MISS` |

### Preconditions

- `overlays/erp-daily.erp_canonical` row existe para `(market_index, date)` mapeada com `confidence ≥ 0.50`; senão flag `OVERLAY_MISS` e ERP component fica `NULL`.
- `cape_ratio` ≤ 30 dias stale (Shiller release mensal); `> 30 d` → flag `STALE`.
- `buffett_ratio` GDP-source: trimestral, interpolar linear para dailies; FRED `GDP` ≤ 1 trimestre stale.
- BIS `property_gap_pp` é trimestral (release T+90); aceitar até 180 dias; `> 180 d` → flag `STALE`.
- Histórico ≥ 20 anos do connector primário para z-score (CAPE pode usar 40Y para percentile rank — ver §4); senão `INSUFFICIENT_HISTORY` (proposto).
- `methodology_version` da `erp_canonical` row bate com runtime expectations ou raise `VersionMismatchError`.

## 3. Outputs

Single row per `(country_code, date, methodology_version)`:

| Nome | Tipo | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | 0-100 | `f1_valuations` |
| `score_raw` | `float` | weighted z-aggregate | idem |
| `components_json` | `json` | per-component z-scores + raw values | idem |
| `cape_ratio` | `float` | ratio | idem (denormalized for query convenience) |
| `erp_median_bps` | `int` | bps (from overlay) | idem |
| `buffett_ratio` | `float` | ratio | idem |
| `property_gap_pp` | `float` | percentage points | idem |
| `lookback_years` | `int` | — | idem |
| `confidence` | `float` | 0-1 | idem |
| `flags` | `str` | CSV | idem |

**Canonical JSON shape**:

```json
{"country": "US", "date": "2026-04-17",
 "score_normalized": 78.4, "score_raw": 1.71,
 "components": {"cape_z": 1.82, "buffett_z": 1.95, "erp_z": -1.12,
                "fwd_pe_z": 1.40, "property_gap_z": 0.85},
 "confidence": 0.86, "flags": []}
```

## 4. Algorithm

> **Units**: ratios/decimal storage; `erp_*_bps` int (consumed verbatim); `property_gap_pp` em percentage points (BIS native). Full rules em [`conventions/units.md`](../../conventions/units.md).

**Aggregation** (z-score → linear rescale to 0-100):

```text
component_z = (x_t − μ_20Y) / σ_20Y       # per metric, 20Y rolling window
score_raw   = Σ_i (w_i · component_z_i)    # weighted sum
score_normalized = clip(50 + 16.67 · score_raw, 0, 100)
```

**ERP sign-flip**: ERP is *inversely* related to expensiveness (low ERP = expensive equity). Component z is `−(erp_t − μ) / σ` so that high score = euphoric.

**Component weights** (per `(country, date)`, renormalized if a component is `NULL`):

| Component | Weight | Source | Notes |
|---|---|---|---|
| CAPE z | 0.35 | Shiller / Barclays / GMO | CAPE percentile rank also computed (40Y window) for diagnostic |
| Buffett ratio z | 0.20 | FRED Wilshire/GDP (US); local equiv. else | requires daily GDP interpolation |
| ERP z (sign-flipped) | 0.20 | `erp_canonical.erp_median_bps` | `NULL` for countries sem mature index → renorm |
| Forward P/E z | 0.10 | FactSet / multpl | optional Tier 1; else drop + renorm |
| Property gap z | 0.15 | BIS `property_gap_pp` | quarterly; carry-forward in daily output |

> **Placeholder thresholds — recalibrate after 24m de production data + walk-forward backtest contra Shiller bubble episodes (2000, 2007, 2021)**.

**Pipeline per `(country_code, date)`**:

1. Load `erp_canonical` row para mapped `market_index`; if missing → flag `OVERLAY_MISS`, set ERP component `NULL`.
2. Fetch CAPE, Buffett, fwd P/E, property gap via connectors; validate freshness & ranges.
3. Compute 20Y rolling `(μ, σ)` per component using daily series (carry-forward para inputs trimestrais/mensais).
4. Compute component z-scores; sign-flip ERP.
5. Renormalize weights se algum componente `NULL` (`w_i ← w_i / Σ_avail w_j`).
6. `score_raw = Σ w_i · z_i`; `score_normalized = clip(50 + 16.67·score_raw, 0, 100)`.
7. Compute CAPE percentile rank vs 40Y window (diagnostic only; persisted in `components_json`).
8. Compute `confidence` (see §6); inherit flags from `erp_canonical` per `flags.md` propagation rule.
9. Persist single row to `f1_valuations` table.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | rolling stats, vector ops |
| `pandas` | 2.1 | timeseries i/o, rolling windows, GDP interpolation |
| `scipy` | 1.11 | `stats.percentileofscore` (CAPE percentile rank) |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | `components_json` validation |

No network calls — inputs pre-fetched from connectors / overlay tables.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md). Confidence impact aplicado conforme regra "Convenção de propagação" do `flags.md`.

| Trigger | Handling | Confidence |
|---|---|---|
| `erp_canonical` row ausente para `(market_index, date)` | flag `OVERLAY_MISS`; drop ERP component; renorm | cap 0.60 |
| `erp_canonical.flags` contém `ERP_METHOD_DIVERGENCE` | inherit flag; ERP component still used | −0.05 (hereditary) |
| `cape_ratio > 30 d` stale | flag `STALE`; compute anyway | −0.20 |
| `property_gap_pp > 180 d` stale | flag `STALE`; carry-forward last value | −0.20 |
| `< 20 Y` history disponível | flag `INSUFFICIENT_HISTORY` (proposed); use available window, mínimo 7Y | cap 0.65 |
| Country tier 4 (CN/IN/BR/TR/MX) | flag `EM_COVERAGE`; ERP `NULL`; reduced component set | cap 0.70 |
| Buffett GDP source > 1 quarter stale | flag `STALE` | −0.20 |
| All optional components `NULL` (only CAPE available) | proceed with CAPE-only score; flag `F1_CAPE_ONLY` (proposed) | cap 0.55 |
| `fwd_pe` PDF scrape fail | flag `OVERLAY_MISS`; drop fwd P/E; renorm | −0.10 |
| `score_normalized > 95` sustained ≥ 5 sessions | flag `F1_EXTREME_HIGH` (proposed; informational) | none |
| Stored `erp_canonical.methodology_version ≠` runtime expected | raise `VersionMismatchError` | n/a |
| All inputs missing for `(country, date)` | raise `InsufficientDataError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/F1-valuations/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01_02` | CAPE=33.2, Buffett=1.85, fwd P/E=19.5, ERP_median=472bps, property_gap=4.2pp | `score_normalized ≈ 73`, `cape_z ≈ 1.6`, no flags | ±3 score |
| `us_2000_03_24` | CAPE=44, Buffett=2.10, ERP=−50bps (post-flip high) | `score_normalized > 90`, flag `F1_EXTREME_HIGH` | ±5 |
| `us_2009_03_09` | CAPE=13, Buffett=0.62, ERP_median=820bps, property_gap=−15pp | `score_normalized < 15` (Stress) | ±5 |
| `pt_2024_01_02` | PSI-20 synthetic CAPE=14.5, no Buffett, ERP fallback EA | `score_normalized ≈ 42`, flag `EM_COVERAGE` not set; renorm applied | ±5 |
| `tr_2024_01_02` | Sparse data, no ERP | `score_normalized` bounded; flag `EM_COVERAGE`, `OVERLAY_MISS`; `confidence ≤ 0.55` | — |
| `erp_missing` | Valid CAPE+Buffett, ERP overlay row missing | flag `OVERLAY_MISS`; ERP weight renormed; `confidence ≤ 0.60` | — |
| `cape_only_degenerate` | All components `NULL` except CAPE | flag `F1_CAPE_ONLY`; `confidence ≤ 0.55` | — |
| `version_mismatch` | Stored `erp_canonical.methodology_version = ERP_CANONICAL_v0.0` | raises `VersionMismatchError` | n/a |
| `insufficient_all` | All inputs missing | raises `InsufficientDataError` | n/a |

## 8. Storage schema

```sql
CREATE TABLE f1_valuations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code          TEXT    NOT NULL,
    date                  DATE    NOT NULL,
    methodology_version   TEXT    NOT NULL,                   -- 'F1_VALUATIONS_v0.1'
    score_normalized      REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw             REAL    NOT NULL,
    components_json       TEXT    NOT NULL,                   -- {"cape_z":..,"buffett_z":..,"erp_z":..,"fwd_pe_z":..,"property_gap_z":..,"cape_pctile_40y":..}
    cape_ratio            REAL,
    erp_median_bps        INTEGER,
    buffett_ratio         REAL,
    forward_pe            REAL,
    property_gap_pp       REAL,
    lookback_years        INTEGER NOT NULL,                   -- 20 default; 7-19 for tier-3/4 fallback
    confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                 TEXT,                                -- CSV: STALE,OVERLAY_MISS,EM_COVERAGE,...
    source_overlay        TEXT,                                -- 'erp_canonical:ERP_CANONICAL_v0.1'
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_f1_cd ON f1_valuations (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/financial-fcs` | L4 | `score_normalized` (peso 30% no FCS composite) |
| `integration/diagnostics/bubble-warning` | L6 | `score_normalized > 70` + BIS credit gap > 10pp + `property_gap_pp > 20` → trigger |
| `outputs/editorial` | L7 | `cape_ratio`, `erp_median_bps`, `buffett_ratio` direct citation |
| `cycles/financial-fcs` (transition logic) | L4 | 6M change in `score_normalized` → momentum overlay (Cap 15 §Fase 4) |

## 10. Reference

- **Methodology**: [`docs/reference/indices/financial/F1-valuations.md`](../../../reference/indices/financial/F1-valuations.md) — manual cap 7. Composite formula em `docs/reference/cycles/financial.md` Cap 15.
- **Data sources**: [`docs/data_sources/financial.md`](../../../data_sources/financial.md) §3 (CAPE, Buffett, valuations) + §8 (real estate / BIS property gap); [`data_sources/D2_empirical_validation.md`](../../../data_sources/D2_empirical_validation.md) §3 FRED `SP500` fresh + §8 OECD/BIS property gap accessible.
- **Architecture**: [`specs/conventions/patterns.md`](../../conventions/patterns.md) §Pattern 4 (CAPE + ERP via Shiller/Damodaran academic canonical sources); [`adr/ADR-0005-country-tiers-classification.md`](../../../adr/ADR-0005-country-tiers-classification.md) (F1 T1 full; T2+ CAPE derived com lower confidence).
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §2 rows 11-12 (Shiller + Damodaran academic free-use); §3 canonical attribution strings **required**: `"Shiller, R. J., Yale University"` + `"Damodaran, A., NYU Stern School of Business"`. Consumer emits `ATTRIBUTION_REQUIRED` flag.
- **Papers**:
  - Shiller R. (2015), *Irrational Exuberance* (3rd ed.), Princeton.
  - Damodaran A. (2024), "Equity Risk Premiums: Determinants, Estimation and Implications", NYU Stern.
  - Borio C., Drehmann M. (2009), "Assessing the risk of banking crises — revisited", *BIS Q. Review*.
- **Cross-validation**: GMO 7-year asset class forecasts (qualitative regime check); Damodaran monthly histimpl (already cross-validated upstream em `overlays/erp-daily`).

## 11. Non-requirements

- Does not compute its own ERP — consume `overlays/erp-daily.erp_canonical.erp_median_bps`. Princípio `compute, don't recompute` (cf. `erp-daily.md` §11).
- Does not compute BIS credit gap — esse vive em `indices/credit/L2-credit-to-gdp-gap`. Bubble Warning consome ambos via L6 integration, não cross-imports L3↔L3.
- Does not emit crypto valuations (MVRV, NUPL, NVT, Puell) — out of scope para v0.1; manual cap 7.5 antecipa Phase 2 do roadmap (`F1_VALUATIONS_v0.2`).
- Does not emit commodity nor FX valuations — manual atribui-lhes 10% e 5% respectivamente; deferred para v0.2 quando connectors REER/Big-Mac estiverem operacionais.
- Does not perform CAPE regime-detection (rate-adjusted CAPE, "this time different" tests) — manual cap 7.9 reconhece model risk; ficará em `cycles/financial-fcs` como overlay diagnostic.
- Does not compute country-specific Buffett-equivalents para EM — não há GDP daily-interpolatable confiável; EM rows omitem Buffett component e renormalizam.
- Does not gap-fill across dates — daily batch only; backfill vive em `pipelines/backfill-strategy`.
- Does not emit forecasts (12M-forward expected return per Shiller regression) — out of scope; consumer pode derivar.
