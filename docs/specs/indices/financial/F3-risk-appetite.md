# F3 · Risk Appetite — Spec

> Layer L3 · indices/financial · slug: `F3-risk-appetite` · methodology_version: `F3_RISK_APPETITE_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E2)

## 1. Purpose

Quantificar **risk appetite e volatility regime** per `(country, date)` agregando equity vol (VIX / VSTOXX / VXJ), bond vol (MOVE), credit spreads (HY OAS, IG OAS), e Financial Conditions Index (NFCI / CISS). Output `score_normalized ∈ [0, 100]` com **higher = euforia / complacência (low vol, tight spreads, loose FCI)** e **lower = stress (high vol, wide spreads, tight FCI)**. Terceiro componente do FCS (peso 25%); overlap parcial com `cycles/monetary-msc` M4 FCI documentado em §10.

## 2. Inputs

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | business day local | param |
| `vol_equity_index` | `float` | level (VIX/VSTOXX/VXJ etc.); `[5, 100]` | `connectors/fred` (`VIXCLS`); CBOE / Euronext / TSE |
| `move_level` | `float` | bond vol; `[20, 250]` | `connectors/ice_move` (US-only primary) |
| `credit_spread_hy_bps` | `int` | HY OAS local-mkt | `connectors/fred` (`BAMLH0A0HYM2`) |
| `credit_spread_ig_bps` | `int` | IG OAS local-mkt | `connectors/fred` (`BAMLC0A0CM`) |
| `fci_level` | `float` | local FCI z-score | `connectors/fred` (`NFCI` US); `connectors/ecb_sdw` (`CISS` EA) |
| `crypto_vol_level` | `float` | optional; BVOL / DVOL (BTC IV) | `connectors/coinglass` ou `connectors/deribit` |

### Mapping country → volatility / FCI sources

| country_code | Equity vol | Bond vol | HY/IG spreads | FCI |
|---|---|---|---|---|
| US | VIX (`VIXCLS`) | MOVE (ICE) | ICE BofA US HY/IG | Chicago Fed `NFCI` |
| EA | VSTOXX (Euronext) | proxy: Bund vol via FRED options | iBoxx EA HY/IG (FRED proxy `BAMLHE00EHYIOAS`) | ECB `CISS` |
| UK | VFTSE (LSE; sparse) | MOVE proxy (US fallback) | iBoxx GBP HY/IG | none → use NFCI proxy + flag |
| JP | VXJ (Nikkei) | MOVE proxy (US fallback) | sparse local HY; IG via Nomura | BoJ FCI proxy |
| DE / FR / IT / ES / NL / IE | VSTOXX (regional proxy) | EA proxy | iBoxx EA HY/IG | CISS |
| PT | VSTOXX (proxy) | EA proxy | iBoxx EA HY/IG | CISS (EA aggregate) |
| CN / IN / BR / TR / MX | local equity vol where available; else US VIX proxy + flag | US MOVE proxy | EMBI spread (FRED `EMBI_*`) substitui HY | local CB FCI if any; else `NULL` |

> **Non-US handling note**: VIX é US-centric. Para non-US sem vol-index líquido, F3 cai para regional proxy (VSTOXX para EA, VXJ para JP) ou usa US VIX como global risk barometer com flag `VOL_PROXY_GLOBAL` (proposed). EM (Tier 4) defaultam para US VIX + `EM_COVERAGE` cap.

### Preconditions

- `vol_equity_index` daily, freshness ≤ 2 BD; `> 5 d` stale → flag `STALE`.
- `credit_spread_hy_bps` e `credit_spread_ig_bps` daily, ≤ 2 BD stale.
- `fci_level` weekly (NFCI Wednesdays) ou semanal (CISS); `> 14 d` stale → flag `STALE`.
- Histórico ≥ 20Y para z-score (US/EA OK; emerging markets toleram 10Y, flag `INSUFFICIENT_HISTORY`).
- `move_level` only US authoritative; non-US uses proxy → flag `MOVE_PROXY` (proposed).
- ≥ 3 dos 5 components disponíveis; senão raise `InsufficientDataError`.

## 3. Outputs

Single row per `(country_code, date, methodology_version)`:

| Nome | Tipo | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | 0-100 | `f3_risk_appetite` |
| `score_raw` | `float` | weighted z-aggregate | idem |
| `components_json` | `json` | per-component levels + z | idem |
| `vix_level` | `float` | level (or proxy) | idem |
| `move_level` | `float` | level (or proxy) | idem |
| `credit_spread_hy_bps` | `int` | bps | idem |
| `credit_spread_ig_bps` | `int` | bps | idem |
| `fci_level` | `float` | z-score (NFCI/CISS) | idem |
| `lookback_years` | `int` | — | idem |
| `confidence` | `float` | 0-1 | idem |
| `flags` | `str` | CSV | idem |

**Canonical JSON shape**:

```json
{"country": "US", "date": "2026-04-17",
 "score_normalized": 68.5, "score_raw": 1.11,
 "components": {"vix_z": -0.95, "move_z": -0.45,
                "hy_z": -0.85, "ig_z": -0.75, "fci_z": -1.20,
                "vix_level": 14.2, "hy_bps": 312, "ig_bps": 105},
 "confidence": 0.90, "flags": []}
```

## 4. Algorithm

> **Units**: vol indices em level (annualized %); spreads em **`int bps`** (per `units.md` §Spreads); FCI em z-score (native NFCI/CISS scale). Component z-scores adimensionais. Full rules em [`conventions/units.md`](../../conventions/units.md).

**Aggregation** (sign-flip *all* components — high vol/spreads/tight FCI = stress, devem reduzir score):

```text
component_z_signed = − (x_t − μ_20Y) / σ_20Y      # negation makes high-vol → low-score
score_raw          = Σ_i w_i · component_z_signed_i
score_normalized   = clip(50 + 16.67 · score_raw, 0, 100)
```

**Component weights** (manual cap 9.9, simplified for v0.1):

| Component | Weight | Notes |
|---|---|---|
| Equity vol z (VIX / regional proxy) | 0.30 | primary risk-appetite gauge |
| Bond vol z (MOVE / proxy) | 0.15 | rate uncertainty layer |
| HY OAS z | 0.20 | credit risk premium primary |
| IG OAS z | 0.15 | early-warning credit signal |
| FCI z (NFCI / CISS) | 0.20 | composite financial conditions |

**Crypto vol** (BTC/ETH IV) é **opcional v0.1** e não conta para weights — guardado em `components_json` como diagnostic. Promovido a peso explicito em v0.2.

> **Placeholder thresholds — recalibrate after 24m de production data + walk-forward backtest contra Bloom (2009) uncertainty episodes + NBER recession dating**.

**Pipeline per `(country_code, date)`**:

1. Resolve sources via mapping table; load each component for `(country, date)`.
2. For non-US sem MOVE/VIX directos: fallback para proxy + flag `VOL_PROXY_GLOBAL` ou `MOVE_PROXY`.
3. Compute 20Y rolling `(μ, σ)` per component; sign-flip z-scores.
4. Renormalize weights se algum componente `NULL` (mínimo 3/5 obrigatório).
5. `score_raw = Σ w_i · z_i`; `score_normalized = clip(50 + 16.67·score_raw, 0, 100)`.
6. Detect divergence vs `cycles/monetary-msc.M4_FCI` se já existe row para `(country, date)`: se `|F3 − M4_inverted| > 20` → flag `F3_M4_DIVERGENCE` (proposed).
7. Compute `confidence` (§6); persist single row.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | rolling stats |
| `pandas` | 2.1 | timeseries i/o |
| `scipy` | 1.11 | `stats.zscore` (optional) |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | `components_json` validation |

No network calls — connectors pre-fetched.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| `< 3 / 5` components disponíveis | raise `InsufficientDataError` | n/a |
| Country sem vol-index local (UK partial / EM) | use US VIX como global proxy; flag `VOL_PROXY_GLOBAL` (proposed) | −0.15 |
| Country sem MOVE local | use US MOVE como proxy; flag `MOVE_PROXY` (proposed) | −0.10 |
| FCI source missing (UK/JP/EM) | drop FCI; renorm weights; flag `OVERLAY_MISS` | −0.15 |
| `vix_level > 50` (extreme stress) | accepted; informational; flag `F3_STRESS_EXTREME` (proposed) | none |
| `credit_spread_hy_bps > 1000` | accepted; flag `F3_STRESS_EXTREME` (proposed) | none |
| Spread source `> 5 d` stale | flag `STALE` | −0.20 |
| FCI weekly source `> 14 d` stale | flag `STALE`; carry-forward | −0.20 |
| `< 20 Y` history disponível | flag `INSUFFICIENT_HISTORY` (proposed); use 10Y mínimo | cap 0.65 |
| Country tier 4 | flag `EM_COVERAGE`; reduced component set; EMBI substitui HY | cap 0.70 |
| `|F3 − inverted M4 FCI| > 20` (when both exist) | flag `F3_M4_DIVERGENCE` (proposed; informational, editorial trigger) | none |
| Stored row methodology version mismatch | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored in `tests/fixtures/F3-risk-appetite/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01_02` | VIX=13.2, MOVE=110, HY=320bps, IG=105bps, NFCI=−0.45 | `score_normalized ≈ 68`, no flags | ±3 |
| `us_2008_10_15` | VIX=68, MOVE=240, HY=1850bps, IG=520bps, NFCI=+3.5 | `score_normalized < 5`; flag `F3_STRESS_EXTREME` | ±3 |
| `us_2020_03_18` | Covid peak — VIX=82, MOVE=170, HY=1100bps | `score_normalized < 8`; flag `F3_STRESS_EXTREME` | ±3 |
| `ea_2024_01_02` | VSTOXX=14.5, EA HY=380bps, CISS=0.18 | `score_normalized ≈ 65`; MOVE proxied | flag `MOVE_PROXY` set |
| `pt_2024_01_02` | VSTOXX proxy, EA spreads, CISS | `score_normalized ≈ 65`; flag `MOVE_PROXY`; `confidence ≤ 0.85` | — |
| `tr_2024_01_02` | Local vol unavailable, US VIX proxy, EMBI spread | flags `VOL_PROXY_GLOBAL`, `EM_COVERAGE`, `MOVE_PROXY`; `confidence ≤ 0.55` | — |
| `insufficient_2_components` | Only VIX + HY available (2/5) | raises `InsufficientDataError` | n/a |
| `m4_divergence_synthetic` | F3=70, inverted M4 FCI=45 | flag `F3_M4_DIVERGENCE` | — |
| `version_mismatch` | Stored row v0.0 | raises `VersionMismatchError` | n/a |

## 8. Storage schema

```sql
CREATE TABLE f3_risk_appetite (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,
    methodology_version      TEXT    NOT NULL,                -- 'F3_RISK_APPETITE_v0.1'
    score_normalized         REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw                REAL    NOT NULL,
    components_json          TEXT    NOT NULL,
    vix_level                REAL,
    move_level               REAL,
    credit_spread_hy_bps     INTEGER,
    credit_spread_ig_bps     INTEGER,
    fci_level                REAL,
    crypto_vol_level         REAL,                             -- diagnostic only v0.1
    components_available     INTEGER NOT NULL CHECK (components_available BETWEEN 3 AND 5),
    lookback_years           INTEGER NOT NULL,
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_f3_cd ON f3_risk_appetite (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/financial-fcs` | L4 | `score_normalized` (peso 25% no FCS composite) |
| `cycles/monetary-msc` | L4 | shares FCI (M4) — see §10 overlap note; canonical FCI lives in M4 |
| `regimes/risk-on-off` | L5 | composite z + VIX/HY signal |
| `outputs/editorial` | L7 | `vix_level`, `credit_spread_hy_bps`, `fci_level` direct citation |

## 10. Reference

- **Methodology**: [`docs/reference/indices/financial/F3-risk-appetite.md`](../../../reference/indices/financial/F3-risk-appetite.md) — manual cap 9.
- **Data sources**: [`docs/data_sources/financial.md`](../../../data_sources/financial.md) §5 (VIX, MOVE, spreads, FCI); [`data_sources/D2_empirical_validation.md`](../../../data_sources/D2_empirical_validation.md) §3 `VIXCLS` fresh; MOVE via Yahoo scrape per LICENSING §7 (não FRED — externa ICE data license).
- **Architecture**: [`specs/conventions/patterns.md`](../../conventions/patterns.md) §Pattern 4 (VIX/MOVE scrape Yahoo para non-US/EM); [`adr/ADR-0005-country-tiers-classification.md`](../../../adr/ADR-0005-country-tiers-classification.md) (VOL_PROXY_GLOBAL flag + tier-4 cap).
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §3 (FRED ICE BofA attribution + Chicago Fed NFCI + ECB CISS) + §7 Yahoo scrape ethics para MOVE.
- **Overlap with `cycles/monetary-msc.M4_FCI`**: M4 é o **canonical FCI** computation per country (Layer 1 do MSC). F3 *consume* o `fci_level` raw como input, mas mantém z-score normalization próprio (20Y rolling vs M4's MSC-specific window). Os dois indices reportam dimensões diferentes — M4 stance monetária via condições financeiras agregadas; F3 risk appetite ciclo financeiro. **Recommended**: future v0.2 → F3 reads `M4_FCI.fci_level` directamente em vez de `connectors/fred(NFCI)` para consistência cross-cycle. Documentado em `cycles/financial-fcs` Cap 15 §integração.
- **Papers**:
  - Bloom N. (2009), "The Impact of Uncertainty Shocks", *Econometrica* 77(3).
  - Adrian T., Boyarchenko N., Giannone D. (2019), "Vulnerable Growth", *AER* 109(4).
  - Hollo D., Kremer M., Lo Duca M. (2012), "CISS — A Composite Indicator of Systemic Stress", *ECB WP 1426*.
- **Cross-validation**: NBER stress dating; ECB CISS published; Chicago Fed NFCI weekly.

## 11. Non-requirements

- Does not compute its own FCI from primitives — consume `connectors/fred(NFCI)` ou `connectors/ecb_sdw(CISS)`. Canonical FCI per country vive em `cycles/monetary-msc.M4_FCI`.
- Does not emit safe-haven demand decomposition (USD/JPY/CHF/Gold flows) — manual cap 9.5 atribui apenas 15%; deferred para v0.2.
- Does not emit crypto-specific risk metrics como peso explicito (funding rates, liquidations, BTC put/call) — manual cap 9.7 deferred para v0.2; v0.1 keeps `crypto_vol_level` apenas como diagnostic field em `components_json`.
- Does not emit VIX term-structure (VIX/VXV ratio, contango/backwardation) — pertence a `regimes/vol-regime` (Phase 5).
- Does not classify regimes (risk-on / risk-off / crisis) — F3 emite contínuo; classification vive em `regimes/risk-on-off`.
- Does not compute country-specific FCI for tier-3/4 sem CB-published FCI — usa CISS/NFCI proxy + flag.
- Does not gap-fill across dates — daily batch only.
- Does not perform real-time intraday VIX tracking — daily EOD apenas.
