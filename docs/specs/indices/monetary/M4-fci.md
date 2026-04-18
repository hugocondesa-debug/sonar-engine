# M4 — Financial Conditions Index — Spec

> Layer L3 · index · cycle: monetary · slug: `m4-fci` · methodology_version: `M4_FCI_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E2)

## 1. Purpose

Mede o **stance monetário "as felt by markets"** via composite de credit spreads, equity volatility, yield curve level, FX stress e liquidity. Captura transmissão (does policy reach asset prices?) e sinaliza disconnects (loose markets vs tight policy = transmission breakdown). Mapeia ao sub-index FC (Financial Conditions — Cap 15.5).

## 2. Inputs

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `nfci_chicago` | `float` | Chicago Fed NFCI z-score (US only) | `connectors/fred` (`NFCI`, `ANFCI`) |
| `policy_or_shadow_rate_pct` | `float` (decimal) | from M1 enrichment OR connector | `monetary_m1_effective_rates.shadow_rate_pct` (cross-spec read) OR connectors |
| `gov_10y_yield_pct` | `float` (decimal) | level | `overlays/nss-curves.yield_curves_spot` `10Y` |
| `credit_spread_bps` | `int` | IG OAS or HY OAS | `connectors/fred` (`BAMLH0A0HYM2`, `BAMLC0A0CM`); `connectors/ice_data` (EA HY) |
| `equity_pe_zscore` | `float` | P/E z-score 10Y rolling (PSI-20 PT, SPX US, SXXP EA, FTAS UK, TPX JP) | `overlays/erp-daily` derived; OR `connectors/twelvedata` raw P/E |
| `fx_neer_zscore` | `float` | trade-weighted NEER z-score 10Y | `connectors/ecb_sdw` (`EXR.M.E5.EUR.EN00.A` for EUR), `connectors/fred` (USD `DTWEXBGS`) |
| `mortgage_rate_pct` | `float` (decimal) | new lending rate, MFI | `connectors/ecb_sdw` (`MIR.M.<CC>.B.A22.A.R.A.2250.EUR.N`), `connectors/fred` (US `MORTGAGE30US`) |
| `vol_index` | `float` | VIX (US), VSTOXX (EA/PT), V2X (UK proxy) | `connectors/yahoo_finance` (`^VIX`, `^V2TX`), `connectors/stooq` |
| `country_code` | `str` | ISO α-2 upper | config |
| `date` | `date` | business day local | param |

### Preconditions

- Para US: `NFCI` z-score deve estar disponível (Chicago Fed weekly); senão fallback custom-FCI + flag `OVERLAY_MISS`.
- Para PT/IE/NL/SE/CH (sem NFCI off-the-shelf): construir custom-FCI conforme Cap 10.6 — todos 7 components disponíveis (DFR, 10Y_PT, spread_PT_Bund, PSI-20 P/E, EUR NEER, mortgage_PT, VSTOXX).
- `overlays/nss-curves` row para `(country, date)` com `confidence ≥ 0.50`.
- ≥ 5 dos 7 components disponíveis para custom-FCI; senão raise `InsufficientDataError`.
- Mortgage rate update ≤ 45 dias; senão flag `STALE`.
- VSTOXX / VIX EOD ≤ 1 business day; senão flag `STALE`.
- `methodology_version` dos overlays consumidos bate com runtime ou raise `VersionMismatchError`.

## 3. Outputs

Uma row per `(country_code, date)` em `monetary_m4_fci`.

| Nome | Tipo | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | `[0, 100]` (higher = tighter financial conditions) | column |
| `score_raw` | `float` | z-score (sigma; positive = tighter) | column |
| `fci_level` | `float` | z-score raw (alias `score_raw`) | column |
| `fci_change_12m` | `float` | Δ z-score over 12 months (momentum) | column |
| `fci_provider` | `str` | enum `{NFCI_CHICAGO, CUSTOM_SONAR, IMF_GFSR}` | column |
| `components_available` | `int` | count of available components (1-7) | column |
| `fci_components_json` | `str (JSON)` | per-component z-scores + weights | column |
| `lookback_years` | `int` | years (default 30 — to span pre-2008 + ZLB regime) | column |
| `confidence` | `float` | 0-1 | column |
| `flags` | `str (CSV)` | — | column |
| `methodology_version` | `str` | — | column |

**Canonical JSON shape** (`fci_components_json`) — custom path:

```json
{
  "credit_spread_bps": 320,
  "credit_spread_z": 0.45,
  "vix_or_vstoxx": 18.5,
  "vix_z": -0.20,
  "gov_10y_yield_pct": 0.0335,
  "yield_z": 0.10,
  "fx_neer_z": -0.30,
  "policy_rate_z": 0.85,
  "mortgage_rate_z": 0.55,
  "equity_pe_z": 0.40,
  "weights": {"credit": 0.30, "equity_vol": 0.25, "yield_level": 0.20, "fx": 0.15, "liquidity": 0.10},
  "fc_change_12m_z": 0.18
}
```

## 4. Algorithm

> **Units**: rates em decimal (storage); spreads em integer bps; vol indices em float index points; z-scores em float sigma. `score_normalized` é `[0, 100]` float. Regras em [`conventions/units.md`](../../conventions/units.md).

**Formula** — provider hierarchy:

```text
if country_code == "US" and NFCI available:
    fci_level = NFCI                       # already z-scored by Chicago Fed
else:
    # Custom SONAR FCI per Cap 10.6 weights (matched to Cap 15.5 FC sub-index canonical)
    fci_level = 0.30 · z(credit_spread_bps)
              + 0.25 · z(vol_index)         # equity volatility (VIX/VSTOXX)
              + 0.20 · z(gov_10y_yield_pct) # yield curve level
              + 0.15 · z(fx_neer_pct)       # FX stress (signed: appreciation = tight for exporters)
              + 0.10 · z(mortgage_rate_pct) # liquidity / credit transmission
                                            # NOTE: pesos somam 1.00; 30/25/20/15/10

# FC sub-index per Cap 15.5 includes momentum + cross-asset stress:
fci_change_12m   = fci_level − fci_level_{t−252bd}
cross_asset_stress = max(z(credit_spread), z(vol_index)) − min(z(...))   # dispersion

FC_raw = 0.55 · fci_level + 0.25 · fci_change_12m + 0.20 · cross_asset_stress
score_normalized = clip(50 + 16.67 · FC_raw, 0, 100)
score_raw        = fci_level                  # natural z-score sigma
```

`z(x)` = z-score sobre rolling window 30 anos por país.

**Pseudocode** (deterministic):

1. Resolve `fci_provider`: if `country_code == "US"` AND `NFCI_t` ≤ 7 dias old → use Chicago Fed NFCI; else `CUSTOM_SONAR`.
2. **NFCI path**: load `NFCI` z-score; `fci_level = NFCI`. Load `NFCICREDIT`, `NFCIRISK`, `NFCILEVERAGE`, `NFCINONFINLEVERAGE` para enrichment json.
3. **Custom path**: fetch 7 components; per Cap 10.6 weights (20/20/15/10/15/15/5 raw, normalized to FC composite weights 30/25/20/15/10).
   - Validate ≥ 5 components; senão raise `InsufficientDataError`.
   - z-score cada component sobre 30Y window do mesmo país.
   - Aggregate ponderado conforme above.
4. Compute `fci_change_12m = fci_level_t − fci_level_{t−252bd}` (lookup own table).
5. Compute `cross_asset_stress` (dispersion across credit + vol + yield z-scores).
6. Aggregate FC_raw via Cap 15.5 weights (55/25/20).
7. Map to `[0, 100]`. Higher = tighter financial conditions.
8. Compute `confidence` via §6 matrix; inherit upstream flags.
9. Persist row em §8 schema.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | z-score, arrays, max/min |
| `pandas` | 2.1 | timeseries i/o, rolling 252bd window |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network — todos inputs pre-fetched.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| `NFCI` (US) > 7 dias stale | fallback custom-FCI; flag `OVERLAY_MISS,STALE` | −0.20 |
| `nss-curves` 10Y missing | drop yield component; reweight; flag `OVERLAY_MISS` | −0.15 |
| Credit spread connector 404 | drop component; reweight; flag `OVERLAY_MISS` | −0.20 |
| Mortgage rate > 45 dias stale | use most-recent + flag `STALE` | −0.15 |
| Vol index EOD missing | use most-recent ≤ 5 bd + flag `STALE` | −0.15 |
| < 5 components disponíveis para custom path | raise `InsufficientDataError` | n/a |
| `fci_change_12m` undefined (cold-start, < 252 bd history) | set `NULL`; reweight FC_raw `[0.65/0/0.35]` | −0.10 |
| Component z-score |z| > 4 (extreme outlier) | clip a ±4σ; flag `FCI_OUTLIER` (proposed) | −0.05 |
| `fci_change_12m > +1.0σ` em 3 meses (tightening shock) | flag `FCI_TIGHTENING_SHOCK` (proposed); register editorial | informational |
| `fci_change_12m < −1.0σ` em 3 meses (easing shock) | flag `FCI_EASING_SHOCK` (proposed); register editorial | informational |
| `lookback_years < 20` | flag `INSUFFICIENT_HISTORY` (proposed); reduce window | cap 0.70 |
| Country tier 4 (CN/IN/BR/TR/MX) | sparse component coverage; cap | cap 0.60 |
| Stored upstream `methodology_version` ≠ runtime | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored em `tests/fixtures/m4-fci/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2026_04_17_nfci` | NFCI z=−0.45, ANFCI z=−0.30 | `fci_level≈−0.45`, `score_norm≈42` (loose); provider `NFCI_CHICAGO` | ±0.05 σ; ±3 score |
| `us_2008_10_15` (GFC peak) | NFCI z=+3.2 | `fci_level≈+3.2`, `score_norm>95`; flag `FCI_TIGHTENING_SHOCK` | ±0.10 σ |
| `us_2020_03_23` (Covid trough) | NFCI z=+2.5 | `fci_level≈+2.5`, `score_norm>90`; flag `FCI_TIGHTENING_SHOCK` | ±0.10 σ |
| `pt_2026_04_17_custom` | spread_PT_Bund=85bps, PSI-20 P/E z=+0.3, EUR NEER z=−0.2, MIR_PT=0.0335, VSTOXX=20 | provider `CUSTOM_SONAR`, `components_available=7`, `score_norm≈48` | ±5 score |
| `pt_2012_q3` (sovereign crisis) | spread_PT_Bund=1100bps, PSI-20 plunged | `fci_level>+2.5σ`, `score_norm>90` | — |
| `ea_2026_04_17_custom` | spread_HY_EA=380bps, VSTOXX=18, Bund10Y=2.5%, EUR NEER z=−0.1 | `fci_level≈−0.10`, `score_norm≈48` | ±0.10 σ |
| `cold_start_no_12m` | first row, lookback < 12m | `fci_change_12m=NULL`, reweight; persist | — |
| `partial_4_components` | only 4 components disponíveis | raises `InsufficientDataError` | n/a |
| `outlier_clipping` | credit_spread z=+5.5σ | clipped to +4σ; flag `FCI_OUTLIER` | — |

## 8. Storage schema

```sql
CREATE TABLE monetary_m4_fci (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,
    methodology_version      TEXT    NOT NULL,            -- 'M4_FCI_v0.1'
    score_normalized         REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw                REAL    NOT NULL,            -- z-score sigma; alias fci_level
    fci_level                REAL    NOT NULL,            -- z-score sigma
    fci_change_12m           REAL,                        -- delta sigma; NULL cold-start
    fci_provider             TEXT    NOT NULL,            -- 'NFCI_CHICAGO' | 'CUSTOM_SONAR' | 'IMF_GFSR'
    components_available     INTEGER NOT NULL CHECK (components_available BETWEEN 1 AND 7),
    fci_components_json      TEXT    NOT NULL,            -- per-component z + weights + raw values
    lookback_years           INTEGER NOT NULL,
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    source_connector         TEXT    NOT NULL,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_m4_cd ON monetary_m4_fci (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/monetary-msc` | L4 | `score_normalized` (peso ~20% MSC; mapeia FC) |
| `cycles/financial-fcs` | L4 | `fci_level` + components — FCI is also financial-cycle primitive |
| `integration/diagnostics/transmission` | L6 | Divergence FCI loose vs M1-M3 tight → transmission breakdown signal |
| `outputs/editorial` | L7 | `fci_change_12m` + tightening/easing shock flags ("FCI tightened 1.5σ in 3m") |

## 10. Reference

- **Methodology**: [`docs/reference/indices/monetary/M4-fci.md`](../../../reference/indices/monetary/M4-fci.md) — Manual Cap 10 (Financial Conditions Indices).
- **Composite design**: [`docs/reference/cycles/monetary.md`](../../../reference/cycles/monetary.md) Cap 15.5 (Sub-index FC weights 55/25/20) + Cap 15.6 (MSC weights).
- **Custom FCI for Portugal**: Cap 10.6 — components DFR/10Y_PT/spread/PSI-20/NEER/MIR_PT/VSTOXX with weights 20/20/15/10/15/15/5 (normalized to FC composite 30/25/20/15/10).
- **Data sources**: [`docs/data_sources/monetary.md`](../../../data_sources/monetary.md) §4 (FCI) + §4.5 (custom PT FCI); [`data_sources/D2_empirical_validation.md`](../../../data_sources/D2_empirical_validation.md) §3 FRED `NFCI` fresh; ECB SDW CISS dataflow key verify Phase 1 dev (D2 testou ESI key — different dataflow from CISS; CISS key format pendente empirical confirmation).
- **Architecture**: [`specs/conventions/patterns.md`](../../conventions/patterns.md) §Pattern 4 (custom-FCI path para non-US/EA per ADR-0005 T2+); [`adr/ADR-0005-country-tiers-classification.md`](../../../adr/ADR-0005-country-tiers-classification.md) (NFCI_CHICAGO = US T1 only; CUSTOM_SONAR = T1+T2+ where ≥5/7 components).
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §3 (FRED public domain + ECB SDW attribution).
- **Papers**:
  - Brave S., Butters R. A. (2011), "Monitoring Financial Stability: A Financial Conditions Index Approach", *FRB Chicago Economic Perspectives* 35(1) — NFCI methodology.
  - Hatzius J. et al. (2010), "Financial Conditions Indexes: A Fresh Look after the Financial Crisis", *NBER WP 16150* — GS FCI.
  - IMF (2017-2024), *Global Financial Stability Report* — cross-country FCI.
- **Cross-validation**: FRED `NFCI`/`ANFCI` (US weekly); IMF GFSR FCI (US/EA/UK/JP/CN, quarterly); Bloomberg `BFCIUS` (institutional only).

## 11. Non-requirements

- Does not implement Goldman Sachs FCI replication — proprietary; placeholder se replication academic disponível v2.
- Does not implement Bloomberg `BFCIUS` ingestion — Tier 3 institutional data; out of scope v0.1.
- Does not compute principal component analysis on its own components — uses simple weighted z-score per Cap 10.6 transparency principle; PCA reserved for `cycles/financial-fcs` (FCS spec).
- Does not classify monetary stance directly — FCI é "feel" das markets, MSC composite (`cycles/monetary-msc`) integra com M1-M3 para classification.
- Does not separate "policy-driven FCI" vs "market-driven FCI" decomposition — would require structural model; out of scope v0.1.
- Does not handle illiquid markets (frontier EM) — coverage limit in Tier 4; sparse components → `EM_COVERAGE` cap.
- Does not auto-recalibrate weights per BC — fixed Cap 10.6 / Cap 15.5 weights; per-BC customization viola robustness principle (Cap 15.7 armadilha 3).
- Does not compute intra-day FCI — daily EOD; intraday stress monitoring fora de escopo v2.
- Does not emit components individually as separate persisted indices — `fci_components_json` é audit trail; primary contract é `score_normalized` + `fci_level`.
