# SONAR v2 · Data sources — Financial cycle (FCS)

> **Layer scope:** L3 indices `F1..F4` + L4 `cycles/financial-fcs` + L2 overlay `erp-daily`.
> **Phase 0 Bloco D1** — rewrite baseado em `D1_coverage_matrix.csv` (2026-04-18) + D0 audit.
> **Status:** doc canónico. Substitui v1 financial.md (1 449 linhas).

Documento alinhado com:
- `docs/specs/cycles/financial-fcs.md` (FCS = 0.30·F1 + 0.25·F2 + 0.25·F3 + 0.20·F4).
- `docs/specs/indices/financial/{F1..F4}.md`.
- `docs/specs/overlays/erp-daily.md`.
- `docs/data_sources/country_tiers.yaml`.
- `docs/data_sources/D1_coverage_matrix.csv`.
- `docs/data_sources/D0_audit_report.md`.

---

## 1. Overview e hierarquia de fontes

### 1.1 Mandato do ciclo

O Financial Cycle Score (FCS) mede o estado do financial market cycle (valuations + momentum + risk appetite + positioning).

| Index | Sub-index | Peso FCS | Mandato |
|-------|-----------|----------|---------|
| F1-valuations | V | 0.30 | CAPE / ERP / credit-to-GDP property gap / price-to-rent |
| F2-momentum | M | 0.25 | Trailing returns 3/6/12m + breadth (% above MA200) |
| F3-risk-appetite | RA | 0.25 | VIX + MOVE + IG/HY credit spreads |
| F4-positioning | P | 0.20 | AAII + COT + FINRA margin debt |

**Lookback canónico:** 20Y (financial cycles medium-term; captures ≥2 bubbles).

### 1.2 Hierarquia de fontes (5 níveis)

```
1. PRIMARY          FRED + Shiller (equity valuation historical) + Damodaran (ERP monthly xval)
   └── FRED é canonical para credit spreads, VIX, bond indices
2. OVERRIDE T1      Native markets data (local index providers)
   └── STOXX, FTSE, TOPIX directo when non-US
3. SECONDARY breadth TE markets breadth T1-T3
   └── /markets/historical/{symbol} — daily OHLC for country indices
4. SECONDARY scrapes Ethical scrapes para positioning
   └── AAII, FINRA, CFTC COT, Yahoo (MOVE), agency buyback reports
5. TERTIARY         FMP commodities (quando subscription renovada)
   └── D1 confirmed 403; parked P2+
```

**ERP daily overlay** é entry point crítico para F1 (valuations) + rating-spread xval (monthly Damodaran baseline).

**Não usadas:**
- **BIS** — WS_LBS_D_PUB property prices cross-cycle (F1 property gap secondary), mas não core F*.
- **ECB SDW** — partial (EA credit spreads via FM; IG/HY não primary).

### 1.3 Critério de escolha

```
If series = equity valuations baseline (CAPE, ERP):
    primary = Shiller / Damodaran (canonical sources)
elif series in FRED_CATALOG:
    primary = FRED
elif series is country-specific equity index:
    primary = TE /markets/historical
elif series requires scrape (AAII, FINRA, CFTC, MOVE):
    primary = SCRAPE_AGENCY
else:
    primary = GAP
```

---

## 2. Country tier coverage

### 2.1 Tabela

| Tier | Count | F1 | F2 | F3 | F4 | FCS viável? |
|------|-------|----|----|----|----|------------|
| T1 | 16 | ✓ full (CAPE xval + property) | ✓ full | ✓ full | ~ (US canonical; outros partial) | Sim — full |
| T2 | 30 | ~ equity CAPE derived | ✓ (returns TE breadth) | ~ (vol local; credit spreads EM limitados) | ✗ | Parcial — F4 missing |
| T3 | 43 | ✗ | ~ returns | ✗ | ✗ | Não — confidence ≤0.50 |
| T4 | ~110 | ✗ | ✗ | ✗ | ✗ | Não |

**F4 US-centricity:** AAII, FINRA, CFTC são US-only. Não há equivalente para outros países sem pagar Bloomberg/Refinitiv. F4 MSC para non-US = NULL.

### 2.2 País-chave por sub-index

| Sub-index | Canonical US | T1 full (non-US) | T1 partial | T2 breadth |
|-----------|--------------|------------------|------------|------------|
| F1 CAPE | Shiller | Derived via TE + local CPI (DE, UK, JP) | FR, IT, ES, CA, AU | via Damodaran monthly |
| F1 ERP | erp-daily overlay | same | — | Damodaran monthly xval |
| F1 property gap | BIS `WS_LBS_D_PUB` | BIS coverage T1 full | — | BIS partial T2 |
| F2 returns | FRED `SP500` | TE /markets/historical {STOXX, FTSE, TOPIX, ...} | — | TE breadth |
| F2 breadth MA200 | GAP (US only via scrape) | — | — | — |
| F3 VIX | FRED `VIXCLS` | — (global proxy) | — | — (global) |
| F3 MOVE | Yahoo `^MOVE` / WSJ scrape | — | — | — |
| F3 IG OAS | FRED `BAMLC0A0CM` | ECB SDW EA (P2) | — | — |
| F3 HY OAS | FRED `BAMLH0A0HYM2` | — | — | — |
| F4 AAII | aaii.com scrape | — | — | — |
| F4 COT | cftc.gov | — | — | — |
| F4 FINRA margin | finra.org | — | — | — |

### 2.3 Degradação T2+

FCS T2 degradado emite apenas F1 (valuation derived) + F2 (returns). F3+F4 NULL. Policy 1 requer ≥3/4 → **fail**. Output: `FCS = NULL, flags = [F3_F4_MISSING, T2_DEGRADED]`.

T1 ex-US: FCS emite com F4 re-weighted out (3/4 valid; confidence = 0.75).

---

## 3. Endpoints por fonte

### 3.1 FRED — financial primary

| Consumer | Series ID | Freq | Notes |
|----------|-----------|------|-------|
| F1 US ERP xval | — | — | Compute via erp-daily overlay |
| F1 US CAPE | — | — | Shiller canonical (CAPE idx ratio, not FRED) |
| F2 US SP500 | `SP500` | Daily | Cash index; preferível para continuity |
| F2 US NASDAQ | `NASDAQCOM` | Daily | — |
| F2 US Russell 2000 | `RU2000PR` | Daily | — |
| F3 VIX | `VIXCLS` | Daily | Shared with E4 sentiment |
| F3 MOVE | — | — | **Not in FRED** — Yahoo scrape |
| F3 IG spread OAS | `BAMLC0A0CM` | Daily | ICE BofA US corporate master |
| F3 HY spread OAS | `BAMLH0A0HYM2` | Daily | ICE BofA US HY master |
| F3 EMBI spread | `BAMLEMCBPIOAS` | Daily | EM corporate — cross-cycle |
| F3 term premium | — | — | ACM monthly (NY Fed site) |

### 3.2 Shiller — Yale (equity valuations canonical)

**URL:** `http://www.econ.yale.edu/~shiller/data/ie_data.xls`
**Auth:** none (static XLS).
**Update:** monthly (Shiller updates ~1st of month).

**Columns extracted:**
- `Date`, `P` (S&P 500 price), `D` (dividends), `E` (earnings), `CPI`, `Rate GS10` (10Y nominal), `CAPE` (computed).

**Computation verifications (spec erp-daily §3):**
- `P / (10Y avg real earnings)` = CAPE
- `earnings_yield = 1 / CAPE`
- `excess_yield_over_10y = earnings_yield - (GS10 real)`

### 3.3 Damodaran — NYU Stern (ERP monthly + xval)

**URL:** `https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html`

**Files consumed:**
- `implpr.xlsx` — implied ERP monthly (US; forward-looking).
- `ctryprem.html` → `ERPMatData.xlsx` — country risk premia (annual; rating-spread overlay consumer).
- `histimpl.xlsx` — historical implied ERP (annual since 1961 US + selected countries).
- `histretSP.xlsx` — historical SP500 returns.

**Frequency:** monthly (US ERP) + annual (country).
**Usage:** `erp-daily` overlay consome para cross-validation (monthly Damodaran vs computed daily).

### 3.4 multpl.com — scrape (S&P 500 valuation ratios)

**URL:** `https://www.multpl.com/{metric}`

| Metric | URL path | Freq | Notes |
|--------|----------|------|-------|
| S&P 500 EPS trailing | `s-p-500-earnings/table/by-month` | Monthly | Matches Shiller |
| S&P 500 dividend yield | `s-p-500-dividend-yield/table/by-month` | Monthly | — |
| S&P 500 price / book | `s-p-500-price-to-book-value/table/by-year` | Annual | — |
| CAPE | `shiller-pe/table/by-month` | Monthly | Shiller mirror |

**Ethical scrape:** 1 req/min; User-Agent identify; honor robots.txt.

### 3.5 TE — equity markets breadth

**Endpoint:**
```
GET /markets/historical/{symbol}?c={KEY}&f=json
```

| Symbol | Index |
|--------|-------|
| `SPX:IND` | S&P 500 |
| `SX5E:IND` | EURO STOXX 50 |
| `SXXP:IND` | STOXX 600 |
| `UKX:IND` | FTSE 100 |
| `DAX:IND` | DAX |
| `CAC:IND` | CAC 40 |
| `MIB:IND` | FTSE MIB |
| `IBEX:IND` | IBEX 35 |
| `NKY:IND` | Nikkei 225 |
| `TPX:IND` | TOPIX |
| `HSI:IND` | Hang Seng |
| `SPTSX:IND` | S&P TSX (CA) |
| `AS51:IND` | ASX 200 (AU) |
| ...T2 EMs... | — |

**Cobertura:** ~60 country-level índices.

### 3.6 TE — country markets bulk

Alternative pattern: `/markets?country={c}` returns markets breadth snapshot (equities + forex + commodities para country). Used for T1 index discovery.

### 3.7 BIS — property price gap

**Endpoint:** `https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LBS_D_PUB/1.0/{KEY}`

BIS property prices time series — covered ~50 países; quarterly.

### 3.8 ECB SDW — EA credit spreads (secondary)

**Endpoint:** `https://data-api.ecb.europa.eu/service/data/FM/`

EA IG/HY spreads partial — less granular que ICE BofA indices. ICE BofA via FRED é preferível.

### 3.9 Scrape — F3 MOVE

**Source:** Yahoo Finance `^MOVE` ticker OR WSJ.

**Ethical scrape Yahoo:**
```
GET https://query1.finance.yahoo.com/v7/finance/download/%5EMOVE
     ?period1=...&period2=...&interval=1d&events=history
```

Yahoo public CSV endpoint — no auth required para indices públicos. Polite rate.

**Fallback:** WSJ Markets endpoint (scrape HTML — fragile).

### 3.10 Scrape — F4 AAII

**Source:** `https://www.aaii.com/sentimentsurvey`

Weekly (Wed release). CSV download via aaii.com/sentimentsurvey/sent_results endpoint.

Format: Week date + Bullish % + Neutral % + Bearish %.

### 3.11 Scrape — F4 CFTC COT

**Source:** `https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm`

Weekly (Fri release, for Tue data). CSV zips downloadable — historical + current.

Relevant report: Legacy Futures Only (`dea_fut_xls_XXXX.zip`). Columns: market, open interest, commercial long/short, non-commercial long/short.

### 3.12 Scrape — F4 FINRA margin

**Source:** `https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics`

Monthly (~10th each month). HTML table — parse margin debt level + cash balances.

### 3.13 Scrape — buyback yield

**Source:** S&P DJI quarterly buyback report `https://www.spglobal.com/spdji/en/idsenhancedfactsheet/file.pdf?documentId=...`

Quarterly PDF — parse total buybacks SP500 companies + buyback yield.

Alt: compute locally from constituents EPS_diluted changes (Phase 2 P2-015).

### 3.14 FMP — status: 403 legacy

D0+D1 confirmaram `/api/stable/*` e `/api/v3/*` ambos 403 com chave actual.

**Planned usage (when subscription renewed):**
- `/api/stable/commodities` — commodities list + quotes.
- `/api/stable/historical-price-full/CLUSD` — WTI crude historical.
- `/api/stable/historical-price-full/GCUSD` — gold.
- `/api/stable/treasury` — US treasury yield curve.

**Status:** parked Phase 2+ `P2-014`. MVP uses TE `/markets/historical/{commodity}` para commodities breadth.

---

## 4. Série catalog — por index / overlay

### 4.1 F1 — Valuations

| Série | Pri | Ovr | Freq | Lat |
|-------|-----|-----|------|-----|
| `damodaran_erp_monthly` | Damodaran `implpr.xlsx` | — | M | 30 |
| `bis_property_price_gap` | BIS `WS_LBS_D_PUB` | — | Q | 60 |
| (via overlay) CAPE | Shiller | — | M | 30 |
| (via overlay) earnings_yield | Shiller / multpl | — | M | 30 |

**F1 composite per spec §3:** weights {CAPE: 0.35, ERP: 0.25, property_gap: 0.25, price_to_rent: 0.15}.

**CAPE T2+ derivation:** para non-US T1 usar TE price series × locally-computed real earnings (requires CPI + historical earnings). Phase 1 limitation: only US+DE+UK+JP + EA aggregate fiaveis.

### 4.2 F2 — Momentum

| Série | Pri | Ovr | Freq | Lat |
|-------|-----|-----|------|-----|
| `equity_returns_3m_6m_12m` | FRED `SP500` (US) + TE breadth (other); compute trailing returns | — | D | 1 |
| `breadth_pct_above_ma200` | **GAP** US only — scrape S&P DJI or data provider | — | D | — |

**F2 returns computation:**
```
ret_3m = (px_t / px_{t-63}) - 1   # business days
ret_6m = (px_t / px_{t-126}) - 1
ret_12m = (px_t / px_{t-252}) - 1
F2_momentum_raw = 0.50·ret_12m + 0.30·ret_6m + 0.20·ret_3m  # per spec §3
```

**Breadth gap:** MA200 breadth não disponível em FREE sources. Options:
1. Scrape stockcharts.com (`$SPXA200R`) — fragile, non-industrial.
2. Compute localmente from constituents (requires 500 individual stocks — large data volume).
3. Proxy via equal-weighted / cap-weighted ratio (FRED SP500EW vs SP500).
4. Backlog `P2-002` — acquire data provider.

### 4.3 F3 — Risk appetite

| Série | Pri | Ovr | Freq | Lat |
|-------|-----|-----|------|-----|
| `move_index` | Yahoo `^MOVE` / WSJ | — | D | 1 |
| `ig_credit_spread_oas` | FRED `BAMLC0A0CM` | ECB SDW EA partial | D | 1 |
| `hy_credit_spread_oas` | FRED `BAMLH0A0HYM2` | — | D | 1 |
| (via E4) VIX | FRED `VIXCLS` | — | D | 1 |

**F3 composite per spec §3:** weights {VIX: 0.30, MOVE: 0.20, IG: 0.25, HY: 0.25}.

**Shared series with E4 (VIX):** single load, consumed por ambos cycles.

### 4.4 F4 — Positioning

| Série | Pri | Freq | Lat |
|-------|-----|------|-----|
| `aaii_bull_bear_spread` | aaii.com scrape | W | 1 |
| `cftc_cot_net_positioning` | cftc.gov scrape | W | 4 |
| `finra_margin_debt` | finra.org scrape | M | 10 |

**F4 is US-only:** spec §2 documents by-design. For non-US countries F4 = NULL; re-weight F1+F2+F3 (total 0.80; normalized to {0.375, 0.3125, 0.3125}).

### 4.5 Overlay L2 — ERP daily

| Série | Pri | Ovr | Freq | Lat |
|-------|-----|-----|------|-----|
| `sp500_index_close` | FRED `SP500` | TE `SPX:IND` | D | 1 |
| `trailing_12m_eps` | Shiller `ie_data.xls` | multpl.com scrape | M | 30 |
| `cape_ratio` | Shiller ie_data.xls | Derived local | M | 30 |
| `dividend_yield` | Shiller / multpl | — | M | 30 |
| `buyback_yield` | S&P DJI quarterly report scrape | Compute from constituents (P2+) | Q | 60 |

**ERP daily computation** (spec §3):
```
earnings_yield = trailing_12m_eps / sp500_close
implied_erp_daily = earnings_yield + growth_assumption - risk_free_rate_real
# with growth = 2% real steady-state; risk_free = US TIPS 10Y
```

**Daily granularity rationale:** EPS fixed (monthly update); price daily; risk-free daily — permit daily ERP emit.

**Xval (spec §5):** compare daily ERP vs Damodaran monthly ERP; emit warning se |daily_avg_month - damodaran| > 100 bps.

---

## 5. Fallback hierarchy

### 5.1 Árvore de decisão FCS

```
Para cada (series, country):
    1. IF series in FRED AND (country == US OR mirror):
         → FRED
    2. ELIF series is canonical equity valuation:
         → Shiller / Damodaran
    3. ELIF series is country-specific index:
         → TE /markets/historical
    4. ELIF series requires scrape (F4, MOVE, buybacks):
         → ethical scrape
    5. ELSE:
         → flag + GAP
```

### 5.2 Policy 1 re-weight FCS

F4 missing para non-US → re-weight:
```
valid = {F1, F2, F3}
weights_valid = {0.30, 0.25, 0.25}  # total 0.80
re-weighted = {F1: 0.375, F2: 0.3125, F3: 0.3125}
FCS = sum
confidence = min(0.75, base)
flag = [F4_MISSING, FCS_REWEIGHTED_NONUS]
```

Se ≥2 sub-indices missing → `FCS = NULL`, flag `COVERAGE_INSUFFICIENT`.

### 5.3 Override conditions

- **FRED US override sempre** (latência + quality).
- **Shiller canonical** para CAPE — jamais substituir sem cross-check.
- **Damodaran monthly** é xval baseline; NÃO é primary daily path.
- **TE breadth** — T2+ equity indices; T1 ex-US aceita TE quando native provider unavailable.
- **FMP PARKED** — não activar até subscription renovada (Hugo decision).

---

## 6. Known gaps e backlog

### 6.1 Gaps críticos (BLOCKING)

| Gap | Impacto | Mitigação | Backlog |
|-----|---------|-----------|---------|
| FMP 403 legacy | Commodities + treasury breadth | TE breadth commodities (partial) | `P2-014` |
| MA200 breadth scrape | F2 US breadth path fragile | Proxy ratio SP500EW/SP500 | `P2-002` |
| F4 non-US equivalent | Design-limited | By-design; Phase 2 Bloomberg | `P2-013` |
| CAPE T1 ex-US | Coverage limited | Derived via TE + local CPI (manual) | `P2-010` |

### 6.2 Gaps de qualidade (CORE)

- **Shiller monthly vs daily ERP:** EPS monthly → ERP stepfunction daily. Spec §4 smooths via forward-fill + warn.
- **ICE BofA licensing:** redistribution restricted; SONAR internal-use OK under FRED TOS (FRED redistributes com license).
- **COT weekly lag:** COT for Tue-of-prev-week released Fri — 4-day lag; mitigate by explicit vintage tracking.
- **Buyback quarterly release timing:** ~60 dias lag; forward-fill monthly stub + warn.

### 6.3 Out-of-scope Phase 0 / Phase 1

- **Minsky fragility layer** (housing + real estate + on-chain crypto) — Phase 3+ `P2-011`. MVP: F1 property gap only.
- **Real estate deep layer** (commercial, REIT, valuation metrics) — Phase 3.
- **On-chain crypto** — Phase 4+.
- **CME/CFTC expanded positioning** (futures commercial, disaggregated COT) — Phase 2 `P2-016`.
- **Flow funds** (ICI mutual fund flows, ETF flows) — Phase 2 `P2-017`.

### 6.4 Calibration tasks

- `CAL-006` — FCS weights validation.
- `CAL-011` — CAPE Z-score lookback 20Y appropriate vs 30Y alternative.
- `CAL-012` — ERP daily-vs-Damodaran xval threshold tuning.
- `CAL-020` — notch→spread calibration (quarterly) — rating-spread tie-in.

---

## 7. Licensing status

| Fonte | Licença | Uso |
|-------|---------|-----|
| FRED | Public domain (FRED redistributes ICE BofA, ICE DJI series) | Sem restrições no FRED mirror |
| Shiller (Yale) | Academic free | Attribution |
| Damodaran (NYU Stern) | Academic free | Attribution |
| multpl.com | Website — ethical scrape | Attribution |
| TE | Commercial (tier pending) | Internal-only |
| BIS | CC-BY-4.0 | Attribution |
| Yahoo Finance | Terms — scrape public tickers OK | Polite rate |
| AAII | Public survey; redistribution limited | Attribution; internal research OK |
| CFTC | Public data — free | Attribution |
| FINRA | Public stats — free | Attribution |
| S&P DJI | Proprietary (buyback reports) | Scrape headlines/totals; no full PDF redistribution |
| FMP | Commercial (subscription lapsed) | N/A — parked |

**ICE BofA caveat:** FRED tem license to redistribute ICE indices publicly. Downstream SONAR outputs that quote specific level values are covered. Citation "Source: FRED" adequate.

---

## 8. Cross-refs

### 8.1 Specs consumer

- `docs/specs/indices/financial/F1-valuations.md`.
- `docs/specs/indices/financial/F2-momentum.md`.
- `docs/specs/indices/financial/F3-risk-appetite.md`.
- `docs/specs/indices/financial/F4-positioning.md`.
- `docs/specs/cycles/financial-fcs.md`.
- `docs/specs/overlays/erp-daily.md`.

### 8.2 Outros cycles

- `cycles/economic-ecs.md E4` — consume VIX (shared FRED `VIXCLS`).
- `cycles/credit-cccs.md L2/CRP` — CRP consume equity vol from F2 raw returns.
- `cycles/monetary-msc.md M3` — ERP real-rate via expected-inflation overlay (cross-layer).

### 8.3 Overlays partilhados

- `erp-daily` emits daily ERP → F1 valuations primary; rating-spread xval baseline.
- `nss-curves` (monetary.md) — provides TIPS real yields para ERP computation.
- `expected-inflation` (monetary.md) — provides π_e para real rate conversion.

### 8.4 Conventions

- `conventions/normalization.md` — z-score lookback 20Y.
- `conventions/composite-aggregation.md` — Policy 1 F4-missing re-weight.
- `conventions/patterns.md` — "parallel equals" ERP daily (6 sub-components equally weighted para ERP formula inputs).
- `conventions/flags.md` — emitidos: `F4_MISSING`, `FCS_REWEIGHTED_NONUS`, `BREADTH_PROXY`, `CAPE_STALE`, `COT_LAG_HIGH`, `ERP_XVAL_DIVERGE`, `FMP_LEGACY_403`.

### 8.5 Architecture / ADRs

- `docs/ARCHITECTURE.md §L3 financial`.
- `docs/adr/ADR-0002` — nine-layer.

### 8.6 Governance / backlog

- `docs/backlog/calibration-tasks.md` — `CAL-006`, `CAL-011`, `CAL-012`, `CAL-020`.
- `docs/backlog/phase2-items.md` — `P2-002` (breadth), `P2-010` (CAPE T1 ex-US), `P2-011` (Minsky), `P2-013` (positioning non-US), `P2-014` (FMP), `P2-015` (buybacks local compute), `P2-016` (COT expanded), `P2-017` (flow funds).
- `docs/data_sources/D0_audit_report.md` — FMP legacy finding.
- `docs/data_sources/D1_coverage_matrix.csv` — rows 12-16 (ERP daily), 55-64 (F1-F4).

---

*Última revisão: 2026-04-18 (Phase 0 Bloco D1 rewrite).*
