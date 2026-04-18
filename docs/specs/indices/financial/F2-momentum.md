# F2 · Momentum — Spec

> Layer L3 · indices/financial · slug: `F2-momentum` · methodology_version: `F2_MOMENTUM_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E2)

## 1. Purpose

Quantificar **momentum e breadth** do mercado de equity primário (e cross-asset overlay) per `(country, date)`: price returns (3M / 6M / 12M), breadth (% stocks > 200d MA), e regime risk-on/off cross-asset. Output `score_normalized ∈ [0, 100]` com **higher = momentum positivo / risk-on / euforia**. Segundo componente do FCS (peso 25%) — coincident regime indicator (manual cap 8).

## 2. Inputs

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | business day local | param |
| `index_level_series` | `pd.Series[float]` | EOD close, ≥ 252 obs (1Y) | `connectors/fred` (US: SP500); `connectors/yahoo` (others) |
| `breadth_pct_above_ma200` | `float` | `[0, 100]` | `connectors/yahoo` (custom calc) ou `connectors/finra_breadth` |
| `cross_asset_returns` | `dict[asset, float]` | 3M return per asset class | `connectors/fred` + `connectors/yahoo` |
| `vol_regime_proxy` | `float` | VIX (US) / VSTOXX (EA) / VXJ (JP) | `connectors/fred` |

### Mapping country → primary equity index

| country_code | Primary index | Secondary | Breadth source |
|---|---|---|---|
| US | S&P 500 (`SP500`) | NDX, RUT | `% S&P 500 > 200d MA` (custom over component holdings) |
| EA | STOXX 600 (`SXXP`) | DAX, CAC | `% STOXX 600 > 200d MA` |
| UK | FTSE All-Share (`FTAS`) | FTSE 100 | best-effort breadth; flag `BREADTH_PROXY` (proposed) |
| JP | TOPIX (`TPX`) | Nikkei 225 | TSE breadth (limited history) |
| DE / FR / IT / ES / NL / IE | local index (DAX/CAC/FTSEMIB/IBEX/AEX/ISEQ) | STOXX 600 fallback | EA breadth (proxy) |
| PT | PSI-20 | STOXX 600 (Tier 3) | EA breadth proxy; flag `BREADTH_PROXY` |
| CN / IN / BR / TR / MX | local benchmark (CSI 300, NIFTY 50, BVSP, BIST 100, MEXBOL) | — | breadth seldom available; component reduced |

### Cross-asset basket (8 aggregates per manual cap 8.5)

`equity, sov_bonds_duration, credit_HY, credit_IG, USD_DXY, commodities (BCOM), crypto (BTC), VIX`.

### Preconditions

- `index_level_series` ≥ 252 trading days (≥1Y) para 12M return; senão raise `InsufficientDataError`.
- Histórico ≥ 20 anos para z-score normalization (Tier 1/2); Tier 3-4 toleram 10Y, flag `INSUFFICIENT_HISTORY` (proposed).
- `breadth_pct_above_ma200` daily; `> 5 d` stale → flag `STALE`.
- Cross-asset returns: cada asset com ≥ 63 obs (3M); missing assets → renorm cross-asset weight.
- `vol_regime_proxy` é coincident con date; > 5 d stale → flag `STALE`.

## 3. Outputs

Single row per `(country_code, date, methodology_version)`:

| Nome | Tipo | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | 0-100 | `f2_momentum` |
| `score_raw` | `float` | weighted z-aggregate | idem |
| `components_json` | `json` | per-component returns + z + breadth | idem |
| `mom_3m_pct` | `float` | decimal return | idem |
| `mom_6m_pct` | `float` | decimal return | idem |
| `mom_12m_pct` | `float` | decimal return | idem |
| `breadth_above_ma200_pct` | `float` | percent (0-100) | idem |
| `cross_asset_score` | `float` | sub-score 0-100 | idem |
| `lookback_years` | `int` | — | idem |
| `confidence` | `float` | 0-1 | idem |
| `flags` | `str` | CSV | idem |

**Canonical JSON shape**:

```json
{"country": "US", "date": "2026-04-17",
 "score_normalized": 71.2, "score_raw": 1.27,
 "components": {"mom_3m_z": 0.95, "mom_6m_z": 1.12, "mom_12m_z": 1.45,
                "breadth_z": 0.85, "cross_asset_z": 0.70,
                "mom_3m_pct": 0.0612, "breadth_pct": 78.4},
 "confidence": 0.88, "flags": []}
```

## 4. Algorithm

> **Units**: returns em decimal (`0.0612` = 6.12%); breadth `[0, 100]` percent literal; z-scores adimensionais. Full rules em [`conventions/units.md`](../../conventions/units.md).

**Aggregation**:

```text
mom_Nm_pct  = (P_t − P_{t-Nm}) / P_{t-Nm}        # raw return horizons
component_z = (x_t − μ_20Y) / σ_20Y               # z-score per component
score_raw   = Σ_i w_i · component_z_i
score_normalized = clip(50 + 16.67 · score_raw, 0, 100)
```

**Component weights** (per `(country, date)`, renormalized se algum `NULL`):

| Component | Weight | Notes |
|---|---|---|
| Price 3M return z | 0.20 | short-term momentum (Jegadeesh-Titman) |
| Price 6M return z | 0.20 | medium-horizon |
| Price 12M return z | 0.20 | long-horizon (academic standard) |
| Breadth (`% > 200d MA`) z | 0.20 | participation quality |
| Cross-asset risk-on z | 0.20 | regime overlay (manual cap 8.5) |

**Cross-asset risk-on sub-score** (per manual cap 8.5):

```text
risk_on_signal = sign(equity_3m) − sign(VIX_3m)     # −2 risk-off … +2 risk-on
                + sign(commodities_3m) − sign(USD_3m)
                + sign(credit_HY_3m) (spread tightening flipped)
cross_asset_z = standardize(risk_on_signal, 20Y)
```

> **Placeholder thresholds — recalibrate after 24m de production data + walk-forward backtest contra Pagan-Sossounov bear/bull dating**.

**Pipeline per `(country_code, date)`**:

1. Fetch `index_level_series` from primary connector; validate length & freshness.
2. Compute `mom_3m_pct, mom_6m_pct, mom_12m_pct` from EOD closes.
3. Fetch `breadth_pct_above_ma200`; if proxy fallback used (PT/EM) → flag `BREADTH_PROXY`.
4. Compute cross-asset risk-on signal from 8-asset basket; flag `CROSS_ASSET_PARTIAL` (proposed) se `< 6` assets disponíveis.
5. Z-score cada componente vs 20Y rolling stats.
6. Renormalize weights se `NULL`; aggregate to `score_raw`.
7. `score_normalized = clip(50 + 16.67·score_raw, 0, 100)`.
8. Detect breadth divergence: `score_normalized > 70` AND `breadth_z < −0.5` → flag `BREADTH_DIVERGENCE` (proposed).
9. Compute `confidence` (§6); persist single row.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | rolling stats, sign |
| `pandas` | 2.1 | timeseries, rolling windows, returns |
| `scipy` | 1.11 | `stats.zscore` (optional) |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | `components_json` validation |

No network calls — connectors pre-fetched daily.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| `index_level_series < 252 obs` | raise `InsufficientDataError` | n/a |
| Index level `NULL` para `t-Nm` (gap) | forward-fill ≤ 5 BD; senão `STALE` flag + skip horizon | −0.10 per horizon |
| Breadth source unavailable (PT/IE/EM) | use EA proxy; flag `BREADTH_PROXY` (proposed) | −0.15 |
| Cross-asset basket `< 6 / 8` assets | drop missing; flag `CROSS_ASSET_PARTIAL` (proposed); renorm | −0.10 |
| `< 20 Y` history disponível | flag `INSUFFICIENT_HISTORY` (proposed); use 10Y mínimo | cap 0.65 |
| Country tier 4 | flag `EM_COVERAGE`; reduced cross-asset; breadth `NULL` | cap 0.70 |
| Breadth narrowing AND score high | flag `BREADTH_DIVERGENCE` (proposed; informational + editorial trigger) | none |
| Single-day return ` |Δ| > 10%` (extreme event) | accept (not error); informational only | none |
| `vol_regime_proxy` missing | drop VIX from cross-asset; renorm | −0.05 |
| Stored row methodology version mismatch | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/F2-momentum/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01_02` | SP500 series + breadth=72% + cross-asset risk-on | `score_normalized ≈ 70`, `mom_12m_pct ≈ 0.24` | ±3 score |
| `us_2009_03_09` | Stress trough — 12M return ≈ −0.45, breadth=8% | `score_normalized < 10` | ±5 |
| `us_2021_11_08` | Late-Euphoria — high score, breadth narrowing to 60% from 85% | flag `BREADTH_DIVERGENCE` | — |
| `pt_2024_01_02` | PSI-20 + EA breadth proxy | flag `BREADTH_PROXY`; `confidence ≤ 0.75` | — |
| `cn_2024_01_02` | CSI 300 + 4/8 cross-asset assets | flag `CROSS_ASSET_PARTIAL`, `EM_COVERAGE`; `confidence ≤ 0.65` | — |
| `insufficient_180d` | Index series 180 obs only | raises `InsufficientDataError` | n/a |
| `gap_filled_index` | 3 BD gap mid-series | forward-filled, no flag | — |
| `extreme_day` | Single −12% session (Covid) | accepted, no error | — |

## 8. Storage schema

```sql
CREATE TABLE f2_momentum (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,
    methodology_version      TEXT    NOT NULL,                -- 'F2_MOMENTUM_v0.1'
    score_normalized         REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw                REAL    NOT NULL,
    components_json          TEXT    NOT NULL,
    mom_3m_pct               REAL,
    mom_6m_pct               REAL,
    mom_12m_pct              REAL,
    breadth_above_ma200_pct  REAL,
    cross_asset_score        REAL,
    primary_index            TEXT    NOT NULL,                -- 'SPX' | 'SXXP' | 'PSI20' | ...
    lookback_years           INTEGER NOT NULL,
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_f2_cd ON f2_momentum (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/financial-fcs` | L4 | `score_normalized` (peso 25% no FCS composite) |
| `cycles/financial-fcs` (transition) | L4 | 6M change → momentum overlay (Cap 15 §Fase 4); breaks Stress→Caution path |
| `outputs/editorial` | L7 | `mom_12m_pct`, `breadth_above_ma200_pct` direct citation; `BREADTH_DIVERGENCE` editorial trigger |
| `regimes/risk-on-off` | L5 | `cross_asset_score` as regime label input |

## 10. Reference

- **Methodology**: [`docs/reference/indices/financial/F2-momentum.md`](../../../reference/indices/financial/F2-momentum.md) — manual cap 8.
- **Data sources**: [`docs/data_sources/financial.md`](../../../data_sources/financial.md) §4 (momentum / breadth) + §5 (cross-asset); [`data_sources/D2_empirical_validation.md`](../../../data_sources/D2_empirical_validation.md) §3 FRED `SP500` fresh; **breadth MA200 data gap confirmed D-block** (free source não existe).
- **Architecture**: [`specs/conventions/patterns.md`](../../conventions/patterns.md) §Pattern 4 (TE markets breadth para non-US indices); [`adr/ADR-0005-country-tiers-classification.md`](../../../adr/ADR-0005-country-tiers-classification.md) (breadth `BREADTH_PROXY` flag + cap 0.75 non-US/EM per tier degradation).
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §3 (FRED attribution; TE markets attribution recommended).
- **Backlog**: [`backlog/phase2-items.md`](../../../backlog/phase2-items.md) `P2-002` — F2 breadth MA200 data provider OR constituents compute (Phase 2+ decision).
- **Papers**:
  - Jegadeesh N., Titman S. (1993), "Returns to Buying Winners and Selling Losers", *J. Finance* 48(1).
  - Asness C., Frazzini A., Pedersen L. (2013), "Quality Minus Junk", *J. Financial Econ.*.
  - Pagan A., Sossounov K. (2003), "A Simple Framework for Analysing Bull and Bear Markets", *J. Applied Econometrics*.
- **Cross-validation**: NBER bull/bear dating; CBOE breadth statistics.

## 11. Non-requirements

- Does not compute crypto-specific momentum (Mayer Multiple, funding rates, on-chain) — manual cap 8.6 antecipa Phase 2 (`F2_MOMENTUM_v0.2`).
- Does not compute real estate momentum (Case-Shiller MoM, FHFA) — manual cap 8.7 atribui apenas 5%; deferred para v0.2.
- Does not perform technical pattern recognition (golden/death cross, ADX, McClellan oscillator) — manual cap 8.2/8.3 são diagnostic; F2 v0.1 cobre apenas ROC + breadth pct.
- Does not date bull/bear markets — algorithmic dating Pagan-Sossounov vive em `regimes/bull-bear-dating` (Phase 5).
- Does not emit volume / distribution-day analysis — manual cap 8.8 fora de escopo v0.1.
- Does not compute its own VIX — consumed via connector como cross-asset input only; F3 é o owner do volatility composite.
- Does not gap-fill across dates — daily batch only.
