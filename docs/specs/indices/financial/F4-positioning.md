# F4 · Positioning — Spec

> Layer L3 · indices/financial · slug: `F4-positioning` · methodology_version: `F4_POSITIONING_v0.1`

## 1. Purpose

Quantificar **investor positioning e flows** per `(country, date)`: retail sentiment (AAII bull-bear), options skew (CBOE put/call), futures positioning (CFTC COT non-commercial S&P), margin debt (FINRA % GDP), e IPO activity. Output `score_normalized ∈ [0, 100]` com **higher = positioning bullish extremo (contrarian warning)** e **lower = positioning bearish extremo (contrarian buy)**. Quarto componente do FCS (peso 20%) — manual cap 10 enfatiza utilidade no extremo.

## 2. Inputs

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | business day local | param |
| `aaii_bull_pct` | `float` | `[0, 100]` weekly | `connectors/aaii` (US-only) |
| `aaii_bear_pct` | `float` | `[0, 100]` weekly | `connectors/aaii` |
| `put_call_ratio_total` | `float` | `[0.2, 2.0]` daily | `connectors/cboe` (US); EUREX (EA partial) |
| `cot_noncomm_net_sp500` | `int` | contracts net long; weekly Tue→Fri release | `connectors/cftc_cot` |
| `margin_debt_usd` | `float` | monthly FINRA | `connectors/finra` |
| `gdp_nominal_usd` | `float` | quarterly, daily-interpolated | `connectors/fred` (`GDP`) |
| `ipo_count_30d` | `int` | trailing 30 days | `connectors/renaissance_ipo` |
| `ipo_first_day_return_med` | `float` | trailing 30d median | `connectors/renaissance_ipo` |

### Country coverage caveat

Most positioning data sources são **US-centric**. Para non-US:

| country_code | AAII | Put/Call | COT | Margin | IPO |
|---|---|---|---|---|---|
| US | full | full | full | full | full |
| EA / DE / FR / IT / ES / NL / IE | use AAII as global proxy + flag | EUREX put/call (partial) | CFTC EUR FX COT (proxy) | none | EA IPO sparse |
| UK | AAII proxy + flag | LSE put/call (sparse) | CFTC GBP FX COT | none | LSE IPO via Renaissance |
| JP | AAII proxy + flag | TSE put/call sparse | CFTC JPY FX COT | none | TSE IPO sparse |
| PT / Tier 3 EA | AAII proxy + flag | EUREX proxy | none | none | none → severely degraded |
| CN / IN / BR / TR / MX | none reliable | none reliable | EM FX COT only | none | none → effectively N/A |

**For non-US**: F4 v0.1 emits row apenas se `≥ 2 / 5` components disponíveis; senão raise `InsufficientDataError`. `EM_COVERAGE` cap aplica.

### Preconditions

- `aaii_*_pct` weekly (Wed release); `> 14 d` stale → flag `STALE`.
- `put_call_ratio_total` daily; `> 5 d` stale → flag `STALE`.
- COT weekly Friday release com Tue-as-of date; `> 14 d` stale → flag `STALE`.
- FINRA margin debt monthly (T+15); `> 60 d` stale → flag `STALE`.
- IPO trailing 30d window: cumulative count + median first-day return.
- ≥ 2 dos 5 components disponíveis senão raise `InsufficientDataError`.
- Histórico ≥ 20Y para z-score (AAII desde 1987 OK; COT desde 1995; margin desde 1959 OK).

## 3. Outputs

Single row per `(country_code, date, methodology_version)`:

| Nome | Tipo | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | 0-100 | `f4_positioning` |
| `score_raw` | `float` | weighted z-aggregate | idem |
| `components_json` | `json` | per-component values + z | idem |
| `aaii_bull_minus_bear_pct` | `float` | percentage points | idem |
| `put_call_ratio` | `float` | ratio | idem |
| `cot_noncomm_net_sp500` | `int` | contracts | idem |
| `margin_debt_gdp_pct` | `float` | percent of GDP | idem |
| `ipo_activity_score` | `float` | composite sub-score `[0, 100]` | idem |
| `lookback_years` | `int` | — | idem |
| `confidence` | `float` | 0-1 | idem |
| `flags` | `str` | CSV | idem |

**Canonical JSON shape**:

```json
{"country": "US", "date": "2026-04-17",
 "score_normalized": 72.8, "score_raw": 1.37,
 "components": {"aaii_z": 1.45, "put_call_z": -1.10, "cot_z": 1.65,
                "margin_z": 1.25, "ipo_z": 0.95,
                "aaii_bb_pct": 28.5, "put_call": 0.62,
                "margin_debt_gdp_pct": 2.85},
 "confidence": 0.84, "flags": []}
```

## 4. Algorithm

> **Units**: AAII em percentage points (weekly raw); put/call em ratio; COT em integer contracts; margin debt em **`% of nominal GDP`** (decimal points like `2.85` = 2.85% of GDP); IPO sub-score em `[0, 100]`. Component z-scores adimensionais. Full rules em [`conventions/units.md`](../../conventions/units.md).

**Sign convention** (high score = bullish extreme, contrarian warning):

```text
aaii_bb_pct        →  positive z = bullish (use as-is)
put_call_ratio     →  positive z = bearish (sign-flip: −z)
cot_noncomm_net    →  positive z = speculative long (use as-is)
margin_debt_gdp_pct→  positive z = leveraged exuberance (use as-is)
ipo_activity_score →  positive z = late-cycle euphoria (use as-is)
```

**Aggregation**:

```text
component_z = (x_t − μ_20Y) / σ_20Y         # 20Y rolling
score_raw   = Σ_i w_i · component_z_i        # with put/call sign-flipped
score_normalized = clip(50 + 16.67 · score_raw, 0, 100)
```

**Component weights** (manual cap 10.10, simplified for v0.1):

| Component | Weight | Notes |
|---|---|---|
| AAII bull−bear z | 0.25 | retail sentiment primary |
| Put/Call ratio z (sign-flipped) | 0.25 | options positioning |
| COT non-comm net z (S&P 500) | 0.20 | speculative futures |
| Margin debt / GDP z | 0.20 | leverage indicator |
| IPO activity z | 0.10 | late-cycle marker |

**IPO activity sub-score** (composite for `ipo_activity_score`):

```text
ipo_activity_score = clip(50
                          + 5 · z(ipo_count_30d, 20Y)
                          + 5 · z(ipo_first_day_return_med, 20Y)
                          + 5 · z(unprofitable_ipo_share, 20Y),  # optional
                          0, 100)
```

> **Placeholder thresholds — recalibrate after 24m de production data + walk-forward backtest contra contrarian episodes (2000-Q1, 2007-Q3, 2021-Q4, 2022-Q4)**.

**Pipeline per `(country_code, date)`**:

1. Resolve sources via mapping; load each component for `(country, date)`.
2. For non-US sem AAII directo: use US AAII como global proxy + flag `AAII_PROXY` (proposed).
3. For weekly/monthly inputs: carry-forward last value within freshness window.
4. Compute 20Y rolling z-scores; sign-flip put/call.
5. Renormalize weights se algum `NULL` (mínimo 2/5 obrigatório).
6. Compute `ipo_activity_score` sub-composite.
7. `score_raw = Σ w_i · z_i`; `score_normalized = clip(50 + 16.67·score_raw, 0, 100)`.
8. Detect contrarian extreme: `score_normalized > 85` OR `< 15` → flag `F4_CONTRARIAN_EXTREME` (proposed; editorial trigger).
9. Compute `confidence` (§6); persist single row.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | rolling stats |
| `pandas` | 2.1 | timeseries i/o, resampling |
| `scipy` | 1.11 | `stats.zscore` (optional) |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | `components_json` validation |

No network calls — connectors pre-fetched.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| `< 2 / 5` components disponíveis | raise `InsufficientDataError` | n/a |
| Country sem AAII local (any non-US) | use US AAII proxy; flag `AAII_PROXY` (proposed) | −0.20 |
| Country sem put/call (Tier 2/3 EA) | EUREX proxy ou drop; flag `OVERLAY_MISS` se drop | −0.10 |
| FINRA margin missing | drop margin component; renorm | −0.15 |
| AAII source `> 14 d` stale | flag `STALE`; carry-forward last value | −0.20 |
| COT `> 14 d` stale (week skipped, gov shutdown) | flag `STALE`; carry-forward | −0.20 |
| FINRA margin `> 60 d` stale (release lag) | flag `STALE` | −0.20 |
| `score_normalized > 85` OR `< 15` | flag `F4_CONTRARIAN_EXTREME` (proposed; informational) | none |
| IPO data sparse (no IPOs trailing 30d) | `ipo_activity_score = 50` (neutral); component z=0 | −0.05 |
| `< 20 Y` history disponível | flag `INSUFFICIENT_HISTORY` (proposed); use 10Y mínimo | cap 0.65 |
| Country tier 4 (CN/IN/BR/TR/MX) | flag `EM_COVERAGE`; severely reduced component set; raise `InsufficientDataError` se `< 2/5` | cap 0.60 |
| Stored row methodology version mismatch | raise `VersionMismatchError` | n/a |
| GDP source missing for margin/GDP normalization | drop margin component; renorm | −0.15 |

## 7. Test fixtures

Stored in `tests/fixtures/F4-positioning/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01_02` | AAII bb=+18, P/C=0.78, COT_net=+85k, margin/GDP=2.6%, IPO=42 | `score_normalized ≈ 65`, no flags | ±3 |
| `us_2021_11_03` | AAII bb=+45, P/C=0.55, COT_net=+180k, margin/GDP=3.5%, IPO heavy | `score_normalized > 88`; flag `F4_CONTRARIAN_EXTREME` | ±3 |
| `us_2009_03_06` | AAII bb=−51, P/C=1.45, COT_net=−120k, margin/GDP=1.5%, IPO=2 | `score_normalized < 12`; flag `F4_CONTRARIAN_EXTREME` | ±3 |
| `ea_2024_01_02` | AAII US proxy, EUREX P/C, no COT, no margin, sparse IPO | `score_normalized ≈ 55`; flags `AAII_PROXY`, `OVERLAY_MISS`; `confidence ≤ 0.65` | — |
| `pt_2024_01_02` | AAII US proxy only, EUREX P/C only (2 components) | `score_normalized` computed; flags `AAII_PROXY`, `EM_COVERAGE` set false (Tier 3); `confidence ≤ 0.60` | — |
| `tr_2024_01_02` | < 2 components | raises `InsufficientDataError`; flag `EM_COVERAGE` would apply | n/a |
| `cot_skipped_week` | COT > 14d stale (gov shutdown) | flag `STALE`; carry-forward used; `confidence ≤ 0.75` | — |
| `version_mismatch` | Stored row v0.0 | raises `VersionMismatchError` | n/a |

## 8. Storage schema

```sql
CREATE TABLE f4_positioning (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code                TEXT    NOT NULL,
    date                        DATE    NOT NULL,
    methodology_version         TEXT    NOT NULL,           -- 'F4_POSITIONING_v0.1'
    score_normalized            REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw                   REAL    NOT NULL,
    components_json             TEXT    NOT NULL,
    aaii_bull_minus_bear_pct    REAL,
    put_call_ratio              REAL,
    cot_noncomm_net_sp500       INTEGER,
    margin_debt_gdp_pct         REAL,
    ipo_activity_score          REAL,
    components_available        INTEGER NOT NULL CHECK (components_available BETWEEN 2 AND 5),
    lookback_years              INTEGER NOT NULL,
    confidence                  REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                       TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_f4_cd ON f4_positioning (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/financial-fcs` | L4 | `score_normalized` (peso 20% no FCS composite) |
| `outputs/editorial` | L7 | `aaii_bull_minus_bear_pct`, `margin_debt_gdp_pct` direct citation; `F4_CONTRARIAN_EXTREME` editorial trigger |
| `regimes/sentiment-extremes` | L5 | extreme-tail labels (`> 85` or `< 15`) |

## 10. Reference

- **Methodology**: [`docs/reference/indices/financial/F4-positioning.md`](../../../reference/indices/financial/F4-positioning.md) — manual cap 10.
- **Data sources**: [`docs/data_sources/financial.md`](../../../data_sources/financial.md) §6 (AAII, P/C, COT, margin, IPO).
- **Papers**:
  - Brown G., Cliff M. (2004), "Investor Sentiment and the Near-Term Stock Market", *J. Empirical Finance* 11(1).
  - Han B. (2008), "Investor Sentiment and Option Prices", *RFS* 21(1).
  - Bekaert G., Hoerova M., Lo Duca M. (2013), "Risk, Uncertainty, and Monetary Policy", *J. Monetary Econ.* 60.
- **Cross-validation**: AAII published weekly summary; cftc.gov COT releases; finra.org margin debt monthly statistics.

## 11. Non-requirements

- Does not compute crypto positioning (exchange flows, ETF flows, funding rates, on-chain HODLer behavior) — manual cap 10.6 antecipa Phase 2 (`F4_POSITIONING_v0.2`).
- Does not emit institutional positioning decomposition (13F filings, hedge fund crowded trades, CTA exposure) — manual cap 10.7 deferred; data largely subscription-only e delayed.
- Does not emit insider transactions (Form 4 SEC) — manual cap 10.9 deferred para v0.2 (requires SEC EDGAR scrape pipeline).
- Does not compute composite sentiment indices commercial (CNN F&G, GS RAI) — F4 reconstroi composite próprio; commercial usados apenas como xval em testing.
- Does not emit fund flows (ICI weekly) como component — relevante mas data freshness inconsistent; deferred para v0.2.
- Does not perform contrarian signal classification (categorical "extreme bullish / bearish") — emite contínuo; classification vive em `regimes/sentiment-extremes`.
- Does not gap-fill across dates — daily batch only; weekly/monthly inputs carry-forward dentro freshness window.
- Does not compute country-specific positioning para non-US sem AAII equivalent local — usa US AAII como global proxy com `AAII_PROXY` flag.
