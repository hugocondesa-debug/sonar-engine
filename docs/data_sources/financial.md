# SONAR · Plano de Fontes de Dados do Ciclo Financeiro

**Documento de implementação técnica**
**Autor**: Hugo · 7365 Capital
**Versão**: v1.0 · Abril 2026
**Contexto**: Extensão do schema SONAR para v17 — quarto e último ciclo a ser integrado, completando a arquitetura SONAR v1 após credit (v13), monetário (v14-15) e económico (v16)
**Âmbito**: Traduzir o Manual do Ciclo Financeiro (6 partes, 4.817 parágrafos no master) em pipeline de dados operacional

---

## Executive Summary

Este documento operacionaliza as fontes de dados necessárias para construir o Financial Cycle Score (FCS) para os países do universo SONAR. O objetivo é implementar a medição proposta nos capítulos 7-10 do manual (F1 Valuations, F2 Momentum, F3 Risk Appetite, F4 Positioning) e alimentar o framework Bubble Warning overlay + matriz 4-way descritos nos capítulos 15-17, mais os quatro diagnósticos aplicados do capítulo 19 (bubble detection, risk appetite, real estate, Minsky fragility).

**Quatro princípios orientadores**:

1. **Reutilização máxima** — os planos de crédito (v13), monetário (v14-15) e económico (v16) já cobriram FRED, ECB SDW, Eurostat, OECD, BIS, BPStat. Este plano concentra-se em **adições distintivas do financeiro** — CAPE/Shiller data, Damodaran ERP, ICE BofA bond indices, CFTC COT, AAII sentiment, on-chain crypto metrics, Case-Shiller, BIS property/credit gaps.

2. **Crypto nativo, não appendix** — em linha com a decisão de design do Cap 1 e do Cap 19, os dados on-chain (MVRV, NUPL, SOPR, NVT, Puell, funding rates) são integrados organicamente em F1, F3 e F4, não tratados como silo separado. Requer acesso Glassnode ou Coinglass (ambos com tiers gratuitos limitados + pagos).

3. **Os quatro diagnósticos aplicados precisam dados específicos** — bubble detection (CAPE + Buffett + Damodaran + GMO sinais), risk appetite framework (regimes via volatility + spreads + flows), real estate cycle (Case-Shiller + BIS property gap + Portugal INE), Minsky fragility (zombie firms + DSR + interest coverage). Cada diagnóstico requer data layer dedicada.

4. **BIS overlay secundário mas estrutural** — o Bubble Warning overlay do Cap 16 exige credit-to-GDP gap + property gap + DSR per country da BIS. Estes são já parcialmente disponíveis via connector BIS (v13) mas requerem séries específicas adicionais.

**Nova cobertura estimada**: 550-750 indicadores adicionais, trazendo SONAR total para ~2.900-3.100 signals across 15 countries × 4 cycles.

**Esforço estimado**: 5 semanas para Tier 1 MVP operacional (uma semana extra vs os outros três por causa do on-chain crypto layer), 9 semanas para Tier 2, 14 semanas para Tier 3.

---

## 1. Âmbito e delimitação

### 1.1 O que este plano cobre

Ficou estabelecido no capítulo 7-10 que o ciclo financeiro usa a composição **F1 + F2 + F3 + F4** com pesos **30/25/25/20**. As fontes agrupam-se conforme:

| Layer | Cobertura | Esta secção |
|---|---|---|
| **F1 Valuations** | CAPE, Buffett, Damodaran ERP, price-to-book/sales, bond yields, cap rates, MVRV, NUPL | §3 |
| **F2 Momentum / Breadth** | Moving averages, ROC, advance-decline, new highs/lows, Mayer Multiple, cross-asset momentum | §4 |
| **F3 Risk Appetite / Volatility** | VIX, MOVE, credit spreads (HY/IG), FCI, DXY, crypto vol | §5 |
| **F4 Positioning / Flows** | AAII sentiment, Put/Call, COT, fund flows, IPO activity, insider, crypto funding rates | §6 |
| **BIS overlay** | Credit-to-GDP gap, property price gap, DSR household/corporate | §7 |
| **Real estate layer** | Case-Shiller, FHFA, ECB RPPI, INE PT, commercial vacancy, REITs | §8 |
| **On-chain crypto** | Glassnode + Coinglass (MVRV, NUPL, SOPR, NVT, Puell, stablecoin supply, funding) | §9 |
| **Minsky fragility** | Zombie firms share, corporate ICR, refinancing wall, shadow banking | §10 |

### 1.2 O que este plano NÃO cobre (já está em v13-v16)

Os connectors já implementados no SONAR cobrem integralmente:

- **FRED API (v13)** — já operacional. Esta fase adiciona ~120 series específicas financeiras (CAPE, VIX, MOVE, BAML spreads, Case-Shiller, gold, DXY, NFCI, etc.).
- **ECB Statistical Data Warehouse (v14)** — já operacional. Financial adiciona EA financial conditions, EA credit spreads, RPPI (residential property price index).
- **Eurostat API (v13)** — já operacional. Financial adiciona HPI (house price index) per country.
- **OECD SDMX (v13)** — já operacional. Financial adiciona OECD property prices database.
- **BIS Data Portal (v13)** — já operacional. Financial adiciona BIS credit-to-GDP gap series, property gap, DSR.
- **BPStat/BdP APIs (v14)** — já operacional. Financial adiciona INE Portugal house prices, Euribor, PSI-20.

### 1.3 Países prioritários

| Tier | Países | Cobertura FCS |
|---|---|---|
| **Tier 1 — full** | US, EA aggregate, Germany, UK, Japan | 100% indicators |
| **Tier 2 — good** | France, Italy, Spain, Canada, Australia | ~80% indicators |
| **Tier 3 — limited** | Portugal, Ireland, Netherlands, Sweden, Switzerland | ~60% indicators |
| **Tier 4 — experimental** | China, India, Brazil, Turkey | ~40% indicators |

Portugal permanece em Tier 3 — inclui EA overlay + INE/BdP específico + PSI-20 Euronext + Euribor tracking. Local hotspots (Lisboa, Porto, Algarve) tracked separately via INE regional data onde disponível.

### 1.4 Asset class coverage

Ao contrário dos outros três ciclos que são primariamente macro-focused, o financeiro requer coverage por asset class:

| Asset class | Coverage |
|---|---|
| **Equity** | US (S&P 500, Russell 2000, NASDAQ), DM (MSCI EAFE, STOXX 600, FTSE, Nikkei, TSX), EM (MSCI EM), Portugal (PSI-20) |
| **Fixed income** | US Treasuries (all tenors via FRED), EA govt bonds (ECB), UK Gilts, JGBs, HY/IG indices (ICE BofA via FRED), EM sovereign (EMBI) |
| **Real estate** | Case-Shiller (US national + 20-city), FHFA (US purchase-only), ECB RPPI (EA countries), OECD property prices, INE PT regional |
| **Commodities** | Gold (FRED), silver, oil (WTI/Brent), copper, broad commodity index (GSCI/BCOM) |
| **Crypto** | BTC + ETH primary, selected alts via CoinGecko. On-chain primary via Glassnode. Derivatives via Coinglass. |
| **FX** | DXY, EUR/USD, USD/JPY, GBP/USD, EUR/GBP, commodity currencies (AUD, CAD, NOK) |

---

## 2. Arquitetura de tiers

Mesmo modelo gradual dos três planos anteriores, mas com cost profile mais elevado devido a crypto on-chain:

### Tier 1 — MVP (semanas 1-5)

**Critério**: connectors gratuitos + one tier pago crypto (Glassnode Advanced ~$29/mês ou Coinglass básico gratuito), suficientes para publicar FCS para Tier 1 countries.

Deliverables:
- FRED connector estendido com ~120 novas series financeiras
- Shiller data direct download pipeline (shillerdata.com)
- Damodaran monthly scrape pipeline (NYU Stern)
- BIS credit/property gap connector extension
- AAII sentiment weekly scrape
- CFTC COT weekly download
- Coinglass basic tier (free): funding rates, open interest, long/short ratios
- Glassnode Advanced tier OR basic free: MVRV, NUPL, SOPR basic set
- Case-Shiller via FRED (monthly)
- NFCI via FRED (weekly)

**Custo estimado**: $29-$99/mês (Glassnode Advanced) + Trading Economics key (já ativo, shared com outros planos).

### Tier 2 — Enhanced (semanas 6-9)

Adiciona:
- NY Fed CMDI (Corporate Bond Market Distress Index) scrape
- Office of Financial Research FSI scrape
- Cross-country housing via OECD database
- Commercial real estate via NCREIF (parcialmente free)
- Enhanced crypto on-chain (Glassnode Professional se orçamento permitir, ~$399/mês)
- Insider transactions via SEC EDGAR (free)
- IPO calendar scrape

**Custo adicional**: $300-$400/mês se Glassnode Professional. Caso contrário, Tier 2 mantém custo ~$29-99/mês.

### Tier 3 — Professional (semanas 10-14)

Adiciona:
- Bloomberg Terminal integration (~$24k/ano) para MOVE, breadth, cross-asset institutional
- Refinitiv (~$22k/ano) como alternativa
- ICE Data Services direct para bond index constituents
- Professional REIT data
- Glassnode Institutional tier se orçamento permitir
- LSEG Datastream para historical cross-asset

**Custo adicional**: $25k-$50k/ano. Justificado apenas se o SONAR passar de personal brand para institutional-grade fund.

**Recomendação**: implementar Tier 1 agora. Avaliar Tier 2 com base em tração editorial. Tier 3 apenas quando fund launch.

---

## 3. F1 Valuations — fontes detalhadas

### 3.1 CAPE (Shiller)

**Fonte primária**: `shillerdata.com/data.htm`
- Download Excel `ie_data.xls` mensalmente
- Contém CAPE + companion data (earnings, dividends, prices, long rate, CPI) desde 1871
- Robert Shiller mantém updates mensais
- Custo: gratuito
- Atualização: mensal (typically primeiro dia útil do mês seguinte)

**Fonte backup via FRED**:
- Série `MULTPL/SHILLER_PE_RATIO_MONTH` (multpl.com re-publicado)

**Pipeline implementation**:
```python
# Download script
url = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
df = pd.read_excel(url, sheet_name='Data', skiprows=7)
# Parse columns: Date, P, D, E, CPI, Rate GS10, CAPE
# Store in financial_valuations_equity with indicator_code='cape_us'
```

**Country coverage**: US primário. Barclays publica CAPE para países europeus anualmente. StarCapital (agora GMO) atualiza CAPE cross-country trimestralmente — scrape periódico.

**FRED CAPE series**:
- `MULT_SHILLER_PE_RATIO_MONTH` — Shiller PE
- Store também earnings yield (inverse)

### 3.2 Buffett indicator

**Fonte primária**: FRED
- Total Market Cap proxy: `WILL5000IND` (Wilshire 5000 Total Market Full Cap Index)
- GDP: `GDP` (quarterly, nominal)
- Alternative: Wilshire 5000 Price Index `WILL5000PR`

**Formula**:
```
buffett_indicator = WILL5000IND / GDP
```

**Atualização**: Wilshire daily, GDP quarterly. Interpolate GDP for daily Buffett.

**Cross-country Buffett**:
- UK: FTSE All-Share / UK GDP
- Germany: DAX cap / Germany GDP
- Japan: TOPIX / Japan GDP
- Proxies via World Bank / IMF cross-country market cap data

### 3.3 Damodaran implied ERP

**Fonte primária**: `pages.stern.nyu.edu/~adamodar/`
- Monthly update — Aswath Damodaran publica sempre início de cada mês
- Ficheiro `histimpl.xlsx` com historical implied ERP + components
- Contains: S&P 500 level, dividends + buybacks, expected growth, risk-free rate, implied ERP

**Pipeline**:
```python
# Monthly scrape
url = "https://pages.stern.nyu.edu/~adamodar/pc/implprem/histimpl.xlsx"
df = pd.read_excel(url, sheet_name='Historical Impl Premiums')
# Store implied_erp, implied_return, risk_free_rate
```

**Custo**: gratuito.

**Series armazenadas**:
- `damodaran_implied_erp_us`
- `damodaran_implied_return_us`
- `damodaran_risk_free_rate`
- `damodaran_sp500_level`

### 3.4 Outros valuations metrics (FRED)

| Indicador | FRED series | Freq | Notas |
|---|---|---|---|
| S&P 500 PE ratio | via multpl.com scrape | Daily | Not in FRED directly |
| S&P 500 price-to-book | via multpl.com scrape | Monthly | — |
| S&P 500 price-to-sales | via multpl.com scrape | Monthly | — |
| S&P 500 dividend yield | `MULT_SP500_DIV_YIELD_MONTH` | Monthly | Via multpl on FRED |
| 10Y Treasury yield | `DGS10` | Daily | Standard |
| 30Y Treasury yield | `DGS30` | Daily | — |
| 3-month Treasury | `DTB3` | Daily | — |
| TIPS 10Y | `DFII10` | Daily | Real yield |
| Break-even inflation 10Y | `T10YIE` | Daily | (DGS10 - DFII10) |
| Corporate AAA yield | `AAA` | Monthly | Moody's |
| Corporate BAA yield | `BAA` | Monthly | Moody's |

### 3.5 Equity market cap aggregates (for Buffett + ratios)

| Series | FRED code | Notes |
|---|---|---|
| Wilshire 5000 FullCap | `WILL5000IND` | Daily, primary |
| Wilshire 5000 PriceCap | `WILL5000PR` | Daily |
| Wilshire 5000 Mid-Cap | `WILLMIDCAPPR` | Daily |
| Wilshire 5000 Small-Cap | `WILLSMLCAPPR` | Daily |
| MSCI USA (ETF proxy) | via Yahoo Finance scraping | Daily |

### 3.6 Real estate valuations

| Indicador | Fonte | Notas |
|---|---|---|
| Case-Shiller National | FRED `CSUSHPISA` | Monthly, seasonally adjusted |
| Case-Shiller 20-City | FRED `SPCS20RSA` | Monthly |
| FHFA Purchase-Only | FRED `USSTHPI` | Quarterly |
| Zillow Home Value Index | zillow.com research | Monthly |
| Median home price / median income | BLS + Census derived | Monthly-derived |
| REIT FTSE NAREIT | via FRED `FBARBOND` family, or Yahoo IYR ETF proxy | Daily |
| Cap rates REITs | NAREIT quarterly publication | Quarterly |

### 3.7 Bond valuations (term premium, real yields)

**Term premium** — Kim-Wright from NY Fed:
- URL: `newyorkfed.org/research/data_indicators/term-premia-tabs`
- Download CSV periodically
- Series: 10Y term premium estimate

**Adrian-Crump-Moench (ACM)** term premium:
- Alternative methodology, also from NY Fed

**Pipeline**:
```python
# Monthly scrape NY Fed term premium
```

### 3.8 Crypto valuations (Glassnode + Coinglass)

**Glassnode indicators para F1**:
- `market/mvrv` — MVRV ratio
- `market/mvrv_less_155` — MVRV less 155 moving average
- `market/price_drawdown_relative` — drawdown from ATH
- `indicators/nupl` — Net Unrealized Profit/Loss (BTC)
- `market/realized_price` — realized price
- `indicators/sopr` — Spent Output Profit Ratio
- `indicators/puell_multiple` — Puell Multiple
- `addresses/min_1_count` — active addresses
- `transactions/transfers_volume_sum` — transfer volume USD
- `blockchain/nvt_ratio` — NVT ratio

**Access**: Glassnode Studio + Advanced API tier. Free tier covers ~40% of indicators at daily resolution. Advanced ($29/mo) covers most at higher resolution.

**BTC specifically**:
- MVRV Z-Score (>7 = top, <0 = bottom)
- NUPL (>0.75 = euphoria)
- SOPR (persistent >1 = greed)
- Puell Multiple (>4 = miner capitulation risk at peaks)

**ETH specifically**:
- Similar metrics adapted
- ETH/BTC ratio
- DeFi TVL locked

**Aggregation**:
```
crypto_valuation_score = weighted_z(
    mvrv_z * 0.30 +
    nupl_z * 0.25 +
    sopr_z * 0.20 +
    puell_z * 0.15 +
    realized_ratio_z * 0.10
)
```

---

## 4. F2 Momentum / Breadth — fontes

### 4.1 Price momentum

**Fonte**: FRED para indices primary + Yahoo Finance scrape para ETF proxies

| Asset | FRED/Yahoo | Momentum measures |
|---|---|---|
| S&P 500 | `SP500` | 50-day MA, 200-day MA, ROC 12M, ROC 6M |
| Russell 2000 | via Yahoo `^RUT` | Same |
| NASDAQ | `NASDAQCOM` | Same |
| DAX | via Yahoo `^GDAXI` | Same |
| STOXX 600 | via Yahoo `^STOXX` | Same |
| Nikkei 225 | `NIKKEI225` | Same |
| PSI-20 | via Euronext or Yahoo | Same |
| Gold | `GOLDAMGBD228NLBM` | Same |
| Oil WTI | `DCOILWTICO` | Same |
| DXY | `DTWEXBGS` | Same |

**Derived momentum indicators**:
- MA crossovers (50/200 golden/death cross)
- ROC (rate of change) 3M, 6M, 12M
- Relative strength vs benchmark
- Mayer Multiple for BTC (price / 200D MA)

### 4.2 Breadth — S&P 500

**Critical breadth indicators** (requer dados per-stock ou already-aggregated):

| Indicador | Fonte | Freq |
|---|---|---|
| Advance-Decline line NYSE | via Barchart API (paid) or WSJ scrape | Daily |
| % stocks above 50D MA | Barchart or FinViz scrape | Daily |
| % stocks above 200D MA | Barchart or FinViz scrape | Daily |
| New 52W highs - new lows | WSJ or FINRA Data | Daily |
| McClellan Oscillator | Computed from A-D | Daily |
| Hindenburg Omen | Computed from breadth | Daily |

**Free sources**:
- `stockcharts.com/freecharts/breadthindex.html` (scrapable)
- FINRA monthly short interest data
- Barchart free tier limited

**Paid options**:
- Barchart API ($99/mo basic)
- TradingView via scraping (ToS restricted)

**Implementation**: scrape stockcharts.com + FinViz screener results daily.

### 4.3 Cross-asset momentum

Score combining momentum across equity / bonds / commodities / crypto:
```python
cross_asset_momentum = mean_z_score([
    sp500_12m_roc,
    us_treasuries_total_return_12m,
    gold_12m_roc,
    btc_12m_roc,
    dxy_12m_roc
])
```

### 4.4 Crypto momentum (Coinglass)

**Free tier**:
- `coinglass.com/api/` — basic endpoints
- Funding rates history
- Open interest history
- Long/short ratio

**Paid**: Coinglass Pro ($39/mo) for API access + historical.

**Indicators**:
- BTC 200D MA position (Mayer Multiple)
- ETH/BTC ratio trend
- Altcoin season index
- BTC dominance

---

## 5. F3 Risk Appetite / Volatility — fontes

### 5.1 VIX e equity volatility

**Primary source FRED**:
- `VIXCLS` — VIX daily close
- `VIX9D` — short-term 9-day VIX (custom series)
- `VIX3M` — 3-month VIX
- `VIX6M` — 6-month VIX

**Derived**:
- VIX term structure (VIX9D / VIX / VIX3M / VIX6M curve)
- VIX percentile rank 5Y rolling

**International**:
- VSTOXX (Euro Stoxx 50 vol): via Euronext or Yahoo
- Nikkei volatility index VXJ: via Reuters or scraping
- MOVE: Bloomberg primary (requires Terminal). Alternative: scrape ICE website (limited history).

### 5.2 Credit spreads

**HY spreads via FRED**:
- `BAMLH0A0HYM2` — ICE BofA US High Yield OAS (daily)
- `BAMLHE00EHYIOAS` — ICE BofA Euro HY OAS
- `BAMLH0A1HYBB` — BB spreads specifically
- `BAMLH0A2HYB` — B spreads
- `BAMLH0A3HYC` — CCC spreads (most stressed)

**IG spreads via FRED**:
- `BAMLC0A0CM` — ICE BofA US IG OAS
- `BAMLC0A4CBBB` — BBB IG
- `BAMLC0A1CAAA` — AAA IG
- `BAMLEMCBPIOAS` — EM corporate spreads

**Sovereign spreads**:
- German bund: `IRLTLT01DEM156N`
- Italy BTP: `IRLTLT01ITM156N`
- Spain: `IRLTLT01ESM156N`
- Portugal: `IRLTLT01PTM156N`
- Spreads computed vs Bund

### 5.3 Financial Conditions Indices

**FRED-available**:
- `NFCI` — Chicago Fed National Financial Conditions Index (weekly)
- `ANFCI` — Adjusted NFCI (residual after macro controls)
- `NFCIRISK` — Risk sub-index
- `NFCICREDIT` — Credit sub-index
- `NFCILEVERAGE` — Leverage sub-index
- `NFCINONFINLEVERAGE` — Non-financial leverage

**EA alternative**:
- Composite Indicator of Systemic Stress (CISS) via ECB SDW
- `CISS.D.U2.Z0Z.4F.EC.SS_CI.IDX`

**Bloomberg FCI**:
- Requires Terminal. Skip in Tier 1.

**Goldman Sachs FCI**:
- Proprietary. Not available direct. Used via Goldman research.

### 5.4 Safe haven indicators

| Indicador | FRED | Notas |
|---|---|---|
| Gold | `GOLDAMGBD228NLBM` | Daily |
| USD broad index | `DTWEXBGS` | Daily |
| JPY/USD | `DEXJPUS` | Daily |
| CHF/USD | `DEXSZUS` | Daily |
| 10Y Treasury yield | `DGS10` | Daily, declining = flight to quality |
| 2s10s spread | `T10Y2Y` | Daily, yield curve |

### 5.5 Crypto risk appetite

**Via Glassnode**:
- `indicators/realized_profit_loss_ratio`
- `market/price_volatility` — BTC realized volatility
- `supply/stablecoin_supply_ratio`

**Via Coinglass**:
- Aggregate open interest across exchanges
- Perpetual funding rate BTC/ETH
- Liquidation data (long vs short liquidations)

**Computed**:
- Crypto fear & greed index (alternative.me has free API)

---

## 6. F4 Positioning / Flows — fontes

### 6.1 AAII sentiment

**Source**: `aaii.com/sentimentsurvey/sent_results`
- Weekly survey of AAII members
- Bull / Neutral / Bear percentages
- Free access but requires membership for historical data
- Alternative: AAII publishes current week freely

**Pipeline**:
```python
# Weekly scrape Thursday evening
# AAII typically publishes Wed 6pm ET
url = "https://www.aaii.com/sentimentsurvey/sent_results"
# Parse bull/neutral/bear percentages
# Store weekly in sentiment table
```

**Derived**:
- Bull - Bear spread
- Extreme bullish flag (Bull > +30%)
- Extreme bearish flag (Bear > +40%)
- 4-week moving average smoothing

### 6.2 Put/Call ratios

**Source**: CBOE
- `cboe.com/us/options/market_statistics/` — daily data
- Equity put/call ratio
- Index put/call ratio
- Total put/call ratio

**FRED has limited historical**: check `SKEW` as complement.

**Pipeline**:
- Daily scrape CBOE statistics page

### 6.3 CFTC Commitment of Traders

**Source**: `cftc.gov/MarketReports/CommitmentsofTraders/`
- Weekly reports (Friday for Tuesday's data)
- Free, comprehensive
- Multiple categories: financial futures, agricultural, metals, energy

**Key COT data**:
- S&P 500 futures (CME)
- Treasury futures (CBOT)
- Gold futures (COMEX)
- Oil futures (NYMEX)
- DXY futures (ICE)
- VIX futures (CBOE)
- Bitcoin futures (CME)

**Traders categories**:
- Commercial (hedgers) — "smart money"
- Non-commercial (speculators) — trend followers
- Retail (small non-reportable)

**Download format**: Excel/CSV per category per week.

**Library**: `cot_reports` Python package simplifies download.

### 6.4 Fund flows

**ICI (Investment Company Institute)**:
- `ici.org/research/stats` — weekly flows (mutual funds)
- Monthly and weekly data
- Equity vs bond vs money market vs hybrid

**ETF flows**:
- ETF.com: some free data
- Bloomberg Terminal: primary
- Alternative: track major ETF AUM changes (SPY, QQQ, TLT, GLD, VGK etc.) via Yahoo Finance

**TrimTabs**: paid service ($200+/mo) for comprehensive flows.

### 6.5 Margin debt

**Source**: FINRA
- `finra.org/investors/learn-to-invest/advanced-investing/margin-statistics`
- Monthly release (approximately 15th of following month)
- NYSE margin debt + free credit balances

**Pipeline**: monthly scrape FINRA stats.

### 6.6 IPO activity

**Source**: Renaissance Capital + SEC filings
- `renaissancecapital.com/IPO-Center/Pricings` — IPO calendar and performance
- SEC EDGAR for S-1 filings count

**Metrics**:
- Monthly IPO count
- Monthly IPO proceeds
- IPO first-day return (quality proxy)
- Unprofitable IPO share
- Unicorn IPOs

### 6.7 Insider transactions

**Source**: SEC EDGAR
- Form 4 filings (buys/sells by insiders)
- Free via EDGAR full-text search
- Open Insider website (`openinsider.com`) aggregates — scrapable

**Derived**:
- Insider buy/sell ratio
- Cluster buying (3+ insiders same company)
- Extreme selling periods

### 6.8 Crypto positioning

**Via Coinglass**:
- BTC perpetual funding rate (aggregate across exchanges)
- ETH perpetual funding rate
- BTC futures premium (basis)
- Open interest total
- Leveraged long vs short

**Via Glassnode**:
- `supply/lth_vs_sth` — long-term vs short-term holders
- `indicators/hodl_waves`
- `market/coin_days_destroyed`

---

## 7. BIS overlay — credit & property gaps

### 7.1 BIS Credit-to-GDP gap

**Source**: `bis.org/statistics/c_gaps.htm`
- Published quarterly
- 43 economies covered
- Downloadable CSV

**Series** per country:
- Credit gap (deviation from HP trend, λ=400,000)
- Credit-to-GDP ratio level
- Property price gap
- DSR (debt service ratio) household
- DSR corporate
- Combined assessment

**Via connector BIS (v13 existente)**:
```python
# Extension to existing BIS connector
bis_series = [
    'C:B:M:770:A:P:D:A',  # Total credit non-financial sector / GDP
    'C:B:M:5R:A:P:D:A',   # Credit-to-GDP gap
    'DSR:H:M:770:A:100',  # Household DSR
    'DSR:P:M:770:A:100',  # Private sector DSR
    'PP:N:M:770:A:628',   # Property prices nominal
    'PP:R:M:770:A:628',   # Property prices real
]
```

**Threshold operationalization** (Cap 16):
- Credit gap > 2pp = early warning
- Credit gap > 10pp = significant warning
- Credit gap > 20pp = extreme
- Property gap > 10% = elevated
- Property gap > 20% = significant
- Property gap > 40% = extreme

### 7.2 BIS Property prices

**Source**: `bis.org/statistics/pp.htm`
- Quarterly + annual
- 60 economies
- Nominal and real
- Free CSV download

### 7.3 BIS DSR

**Source**: `bis.org/statistics/dsr.htm`
- Quarterly
- Household + corporate + combined
- 32 economies

### 7.4 Country coverage priority for BIS overlay

| Country | Credit gap | Property gap | DSR |
|---|---|---|---|
| US | ✓ | ✓ | ✓ |
| EA aggregate | ✓ | ✓ | ✓ |
| Germany | ✓ | ✓ | ✓ |
| UK | ✓ | ✓ | ✓ |
| Japan | ✓ | ✓ | ✓ |
| France | ✓ | ✓ | ✓ |
| Italy | ✓ | ✓ | ✓ |
| Spain | ✓ | ✓ | ✓ |
| Canada | ✓ | ✓ | ✓ |
| Australia | ✓ | ✓ | ✓ |
| Portugal | ✓ | ✓ | ✓ |
| Ireland | ✓ | ✓ | ✓ |
| Netherlands | ✓ | ✓ | ✓ |
| Sweden | ✓ | ✓ | ✓ |
| China | ✓ | partial | partial |
| Brazil, Turkey | partial | partial | limited |

---

## 8. Real estate layer

### 8.1 US real estate

| Indicator | Source | Freq |
|---|---|---|
| Case-Shiller National SA | FRED `CSUSHPISA` | Monthly |
| Case-Shiller 20-City | FRED `SPCS20RSA` | Monthly |
| Case-Shiller 10-City | FRED `SPCS10RSA` | Monthly |
| FHFA Purchase-Only | FRED `USSTHPI` | Quarterly |
| New home sales | FRED `HSN1F` | Monthly |
| Existing home sales | FRED `EXHOSLUSM495S` | Monthly |
| Housing starts | FRED `HOUST` | Monthly |
| Building permits | FRED `PERMIT` | Monthly |
| Median home price | FRED `MSPUS` | Quarterly |
| Homeownership rate | FRED `RHORUSQ156N` | Quarterly |
| 30Y mortgage rate | FRED `MORTGAGE30US` | Weekly |
| 30Y-10Y mortgage spread | Derived | Weekly |
| Housing affordability index | FRED `FIXHAI` | Monthly |

### 8.2 Portugal real estate específico

**INE (Instituto Nacional de Estatística)**:
- `ine.pt` — Índice de Preços da Habitação (IPH)
- Quarterly, national + regional (NUTS II)
- Residential and commercial

**BPStat (Banco de Portugal)**:
- Housing credit data
- Mortgage rates (Euribor-indexed)

**Confidencial Imobiliário**:
- Private market data, subscription required
- Lisboa, Porto detailed breakdowns
- Skip Tier 1, consider Tier 2

**Golden Visa tracking**:
- SEF (Serviço de Estrangeiros e Fronteiras) statistics
- Monthly publication

### 8.3 EA real estate

**ECB RPPI**:
- Residential Property Price Index via ECB SDW
- Quarterly
- Per country

**Eurostat HPI**:
- House Price Index
- Annual + quarterly

### 8.4 Commercial real estate

**Source options**:
- NAREIT: `reit.com/data-research` — REIT data aggregated (free)
- NCREIF: partially free, full data subscription
- CBRE, JLL, Cushman Wakefield: research reports (free but not API)
- Green Street Advisors: professional ($)

**Key CRE indicators**:
- Office vacancy rate
- Retail vacancy rate
- Industrial vacancy rate
- Multifamily cap rates
- Data center cap rates

**Data centers specifically (AI surge)**:
- REIT ETF DLR, EQIX via Yahoo Finance
- Synergy Research data (subscription)
- JLL Data Center reports (free quarterly)

---

## 9. On-chain crypto layer

### 9.1 Glassnode integration

**Account tiers**:
- Free: limited to 10 basic metrics, daily data only
- Advanced ($29/mo): ~100 metrics, weekly/daily
- Professional ($399/mo): ~400 metrics, all resolutions
- Institutional ($799+/mo): all metrics, historical depth

**Recommendation for Tier 1**: Advanced tier sufficient for F1/F3/F4 integration.

**Core endpoint**: `api.glassnode.com/v1/metrics/`

**Priority metrics for MVP**:

| Category | Endpoint | Purpose |
|---|---|---|
| Market | `market/mvrv` | MVRV ratio |
| Market | `market/price_drawdown_relative` | Drawdown tracking |
| Indicators | `indicators/nupl` | Net Unrealized P/L |
| Indicators | `indicators/sopr` | Spent Output Profit Ratio |
| Indicators | `indicators/puell_multiple` | Puell Multiple |
| Indicators | `indicators/realized_profit_loss_ratio` | P/L ratio |
| Indicators | `indicators/reserve_risk` | Reserve Risk |
| Addresses | `addresses/active_count` | Active addresses |
| Addresses | `addresses/new_non_zero_count` | New non-zero |
| Addresses | `addresses/accumulation_balance` | Accumulation addresses |
| Transactions | `transactions/transfers_volume_sum` | Transfer volume |
| Blockchain | `blockchain/nvt_ratio` | NVT ratio |
| Supply | `supply/sth_lth_realized_value_ratio` | STH/LTH ratio |
| Supply | `supply/lth_net_change` | LTH net change |
| Mining | `mining/hash_rate_mean` | Hash rate |
| Derivatives | `derivatives/futures_funding_rate_perpetual` | Funding rate |

**Cross-asset**: BTC + ETH primary. Advanced tier includes LTC, SOL limited. Professional adds comprehensive altcoin coverage.

**Pipeline**:
```python
import glassnode

client = glassnode.Client(api_key=GLASSNODE_KEY)

# Daily batch update
for metric in PRIORITY_METRICS:
    df = client.get(metric, asset='BTC', since=last_update_date)
    store_in_db('onchain_btc', metric, df)
```

### 9.2 Coinglass integration

**Tiers**:
- Free: limited rate-limit, basic endpoints
- Pro ($39/mo): API access + historical
- Enterprise: institutional

**Recommendation**: Free tier + scraping for Tier 1 MVP. Pro later if needed.

**Priority endpoints**:
- `/api/futures/fundingRate` — per exchange, all coins
- `/api/futures/openInterest` — aggregate + per exchange
- `/api/futures/longShortRatio` — retail long/short ratio
- `/api/futures/liquidation` — liquidation data
- `/api/spot/grayscalePremium` — Grayscale premium/discount
- `/api/option/maxPain` — options max pain

### 9.3 CoinGecko (supplementary)

**Free tier**: generous, rate-limited but functional
- Price history per coin
- Market cap per coin
- Trading volume
- Developer activity

**Use**: altcoin coverage, broad market snapshot, less critical metrics.

### 9.4 Crypto fear & greed index

**Source**: `alternative.me/crypto/fear-and-greed-index`
- Free API
- Daily update
- Score 0-100
- Based on volatility + momentum + social media + dominance + trends

**Integration**: component of F3 crypto-specific.

---

## 10. Minsky fragility layer

### 10.1 Zombie firms data

**Source options**:
- BIS Working Paper 951: zombie firms methodology
- OECD zombie firms database (annual)
- BIS Quarterly Review periodic updates
- Direct computation from Compustat (paid)

**Methodology (BIS)**:
- Firm ≥10 years old
- Interest coverage ratio <1 for 3+ consecutive years
- Tobin's Q below median

**Proxies available free**:
- Russell 3000 free cash flow negative share (FINRA)
- Corporate net debt / EBITDA distribution (Bloomberg/Refinitiv paid, otherwise SEC filings)

**Pragmatic approach for Tier 1**: track aggregate corporate debt service coverage via FRED proxies:
- Non-financial corporate debt / GDP: `BCNSDODNS` / `GDP`
- Corporate interest coverage proxy via S&P 500 aggregate

### 10.2 Corporate ICR / leverage

**Aggregate metrics via FRED**:
- `NCBDBIQ027S` — Non-financial corporate business debt
- `NCBCMDPMVCE` — Non-financial corporate business credit
- `BCNSDODNS` — Non-financial corporate business debt securities + loans

**Derived**:
- Corporate debt / GDP
- Corporate debt / corporate revenues (requires BEA NIPA data)
- Corporate DSR via BIS

### 10.3 High Yield refinancing wall

**Source**: S&P Global Ratings publishes quarterly
- `spglobal.com/ratings` — refinancing schedule reports
- Moody's similar
- Free access to reports

**Pipeline**: quarterly scrape. Sum maturities by year for next 5 years.

### 10.4 Shadow banking growth

**Source**: Financial Stability Board (FSB) Global Shadow Banking Monitoring Report
- Annual publication
- Free
- Cross-country

**Intermediate proxies**:
- Money market fund assets (FRED `MMMFFAQ027S`)
- Non-bank financial intermediation growth
- Private credit market size (Preqin + PitchBook paid)

### 10.5 SONAR Minsky composite implementation

From Cap 19:
```python
minsky_fragility_score = weighted_z_combination({
    # Financial system leverage (30%)
    'nonbank_leverage_z': 0.10,
    'shadow_banking_growth_z': 0.10,
    'hedge_fund_gross_exposure_z': 0.10,
    
    # Interest coverage (25%)
    'zombie_firms_percent': 0.10,
    'corporate_icr_weakness': 0.10,
    'hy_refinancing_wall': 0.05,
    
    # Debt service ratios (20%)
    'household_dsr': 0.07,
    'corporate_dsr': 0.07,
    'bis_combined_measure': 0.06,
    
    # Speculative behavior (15%)
    'meme_stock_activity': 0.05,
    'crypto_funding_rate_extreme': 0.05,
    'options_speculation': 0.05,
    
    # System fragility (10%)
    'bank_risk_metrics': 0.04,
    'contagion_indicators': 0.03,
    'interconnectedness': 0.03,
})
```

---

## 11. Schema v17 extensions

### 11.1 New tables

```sql
-- Financial valuations layer
CREATE TABLE financial_valuations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    asset_class TEXT NOT NULL,  -- equity, bonds, real_estate, crypto, commodities, fx
    indicator_code TEXT NOT NULL,
    date DATE NOT NULL,
    value REAL NOT NULL,
    z_score REAL,
    percentile_rank REAL,
    source TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, asset_class, indicator_code, date)
);

-- Financial momentum layer
CREATE TABLE financial_momentum (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    indicator_code TEXT NOT NULL,
    date DATE NOT NULL,
    value REAL NOT NULL,
    z_score REAL,
    source TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, asset_class, indicator_code, date)
);

-- Financial risk appetite layer
CREATE TABLE financial_risk_appetite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    indicator_code TEXT NOT NULL,
    date DATE NOT NULL,
    value REAL NOT NULL,
    z_score REAL,
    percentile_rank REAL,
    source TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, indicator_code, date)
);

-- Financial positioning layer
CREATE TABLE financial_positioning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    indicator_code TEXT NOT NULL,
    date DATE NOT NULL,
    value REAL NOT NULL,
    z_score REAL,
    extreme_flag INTEGER,  -- 1 if extreme bullish, -1 if extreme bearish, 0 otherwise
    source TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, asset_class, indicator_code, date)
);

-- BIS overlay data
CREATE TABLE financial_bis_overlay (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    credit_gdp_gap_pp REAL,
    property_gap_pct REAL,
    dsr_household REAL,
    dsr_corporate REAL,
    dsr_combined REAL,
    warning_level TEXT,  -- none, amber, red, severe
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date)
);

-- On-chain crypto layer
CREATE TABLE financial_onchain (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin TEXT NOT NULL,  -- BTC, ETH, etc.
    indicator_code TEXT NOT NULL,
    date DATE NOT NULL,
    value REAL NOT NULL,
    z_score REAL,
    source TEXT NOT NULL,  -- glassnode, coinglass, etc.
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(coin, indicator_code, date)
);

-- FCS composite output
CREATE TABLE financial_cycle_score (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    fcs REAL NOT NULL,  -- 0-100
    f1_valuations REAL NOT NULL,
    f2_momentum REAL NOT NULL,
    f3_risk_appetite REAL NOT NULL,
    f4_positioning REAL NOT NULL,
    state TEXT NOT NULL,  -- euphoria, optimism, caution, stress
    sub_state TEXT,  -- early, mid, late
    momentum TEXT,  -- rising, stable, falling
    confidence REAL,
    bubble_warning_level TEXT,  -- none, amber, red, severe
    bis_medium_term_status TEXT,
    crypto_specific_flag INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date)
);

-- Asset-class FCS complementar
CREATE TABLE financial_asset_fcs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    date DATE NOT NULL,
    asset_fcs REAL NOT NULL,
    state TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, asset_class, date)
);

-- Four applied diagnostics output
CREATE TABLE financial_applied_diagnostics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    bubble_detection_score REAL,
    risk_appetite_regime INTEGER,  -- 1 to 4
    real_estate_cycle_phase TEXT,
    minsky_fragility_score REAL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date)
);

-- Indexes for performance
CREATE INDEX idx_financial_val_country_date ON financial_valuations(country_code, date);
CREATE INDEX idx_financial_val_class_date ON financial_valuations(asset_class, date);
CREATE INDEX idx_financial_mom_country_date ON financial_momentum(country_code, date);
CREATE INDEX idx_financial_risk_country_date ON financial_risk_appetite(country_code, date);
CREATE INDEX idx_financial_pos_country_date ON financial_positioning(country_code, date);
CREATE INDEX idx_financial_bis_country_date ON financial_bis_overlay(country_code, date);
CREATE INDEX idx_financial_onchain_coin_date ON financial_onchain(coin, date);
CREATE INDEX idx_financial_fcs_country_date ON financial_cycle_score(country_code, date);
```

### 11.2 Connector extensions

| Connector | Extension |
|---|---|
| FRED (existing) | Add ~120 financial series (CAPE, VIX, MOVE, BAML spreads, Case-Shiller, gold, NFCI) |
| ECB SDW (existing) | Add RPPI, CISS, EA financial conditions |
| Eurostat (existing) | Add HPI per country |
| BIS (existing) | Add credit gap, property gap, DSR series |
| BPStat/INE (existing) | Add IPH, PSI-20, Euribor |
| **NEW: shiller_connector** | Direct Excel download from shillerdata.com |
| **NEW: damodaran_connector** | Monthly scrape NYU Stern |
| **NEW: multpl_connector** | Daily scrape multpl.com for PE/PB/PS/divyield |
| **NEW: aaii_connector** | Weekly scrape AAII sentiment |
| **NEW: cftc_cot_connector** | Weekly COT report download |
| **NEW: finra_connector** | Monthly margin debt scrape |
| **NEW: cboe_connector** | Daily put/call ratios |
| **NEW: nyfed_connector** | Term premium + CMDI scrape |
| **NEW: glassnode_connector** | Daily API calls for priority metrics |
| **NEW: coinglass_connector** | Daily funding rates + OI |
| **NEW: coingecko_connector** | Altcoin coverage |
| **NEW: fng_connector** | Crypto fear & greed daily |
| **NEW: naReit_connector** | Monthly REIT data |
| **NEW: ici_connector** | Weekly fund flows |
| **NEW: openinsider_connector** | Daily insider transactions |
| **NEW: renaissance_ipo_connector** | Monthly IPO calendar |

---

## 12. Implementation roadmap — 5 semanas Tier 1

### Semana 1 — F1 Valuations foundation

**Deliverables**:
- Shiller data connector operacional (CAPE downloaded + parsed)
- Damodaran monthly pipeline (histimpl.xlsx parsed)
- Multpl.com daily scrape (PE, PB, PS, div yield)
- FRED extended: Wilshire 5000, GDP for Buffett computation
- Case-Shiller + FHFA via FRED
- Corporate AAA/BAA yields via FRED
- 10Y real yield (TIPS) + breakeven
- `financial_valuations` table populated for US equity class

**Validation**: CAPE historical trace matches Shiller website. Buffett indicator spot-checks.

### Semana 2 — F2 Momentum + F3 Risk Appetite

**Deliverables**:
- Moving averages computed para all major indices (50D, 200D)
- VIX + VIX term structure via FRED
- ICE BofA HY + IG spreads via FRED (all relevant series)
- Chicago Fed NFCI components
- EA CISS via ECB SDW
- `financial_momentum` + `financial_risk_appetite` tables populated

**Validation**: VIX current read matches CBOE. HY spread matches ICE publication.

### Semana 3 — F4 Positioning + BIS overlay

**Deliverables**:
- AAII weekly scrape operacional
- CFTC COT downloader operacional
- FINRA margin debt monthly
- CBOE put/call daily
- BIS connector extended: credit gap, property gap, DSR for 14 countries
- `financial_positioning` + `financial_bis_overlay` populated

**Validation**: AAII latest matches their published report. COT data matches cftc.gov.

### Semana 4 — Crypto on-chain + real estate

**Deliverables**:
- Glassnode Advanced account setup
- Priority metrics pipeline (MVRV, NUPL, SOPR, Puell, NVT)
- Coinglass free tier scrape (funding, OI, liquidations)
- Alternative.me fear & greed
- CoinGecko altcoin coverage
- NAREIT monthly REIT data
- `financial_onchain` populated
- Case-Shiller updated
- INE Portugal quarterly scrape

**Validation**: MVRV trace matches Glassnode Studio. BTC funding rate matches Coinglass website.

### Semana 5 — Composite FCS + Bubble Warning + diagnostics

**Deliverables**:
- FCS composite computation (F1×0.30 + F2×0.25 + F3×0.25 + F4×0.20)
- State classification logic (Euphoria > 75 / Optimism 55-75 / Caution 30-55 / Stress < 30)
- Bubble Warning overlay (FCS conditions + BIS conditions joint)
- Four applied diagnostics:
  - Bubble detection composite
  - Risk appetite regime classifier
  - Real estate cycle phase classifier
  - Minsky fragility composite
- `financial_cycle_score` + `financial_applied_diagnostics` populated
- Cross-cycle integration with ECS/MSC/CCCS (matriz 4-way output)
- Validation against historical episodes (2000, 2007, 2020, 2021)

**Validation**: FCS peaks match historical bubbles (>75 in 2000, 2007, 2021). Stress <30 in 2008-09, briefly 2020. Backtest 87% agreement with Pagan-Sossounov (reproduce claim from Cap 15).

---

## 13. Tier 2 — semanas 6-9

**Enhancements**:
- Semana 6: NY Fed CMDI + OFR FSI scraping
- Semana 7: OECD cross-country housing expansion
- Semana 8: SEC EDGAR insider transactions pipeline + Renaissance IPO
- Semana 9: Enhanced crypto (Glassnode Professional if budget allows) + commercial RE (NAREIT detailed + CBRE reports)

---

## 14. Tier 3 — semanas 10-14

**Professional-grade**:
- Bloomberg Terminal integration (MOVE, institutional breadth, FCI Bloomberg)
- LSEG Datastream (historical cross-asset deep)
- ICE Data Services direct for bond constituents
- Green Street Advisors for CRE
- Preqin for private credit/private equity

**Budget threshold**: ~$50k/ano. Justificado apenas para fund launch.

---

## 15. Portugal-specific additions

Apesar de PT estar em Tier 3 cobertura, algumas adições específicas são valiosas:

### 15.1 PSI-20 Euronext

- Euronext API (some free, some paid tiers)
- Daily close, volume, breadth
- Index constituents + weights (monthly rebalance)

### 15.2 INE detalhado

- IPH trimestral national + NUTS II
- Lisboa, Porto, Algarve specific
- Rental price index
- Tourism statistics (occupancy rates, arrivals)

### 15.3 BdP housing statistics

- Mortgage flow per month
- Variable vs fixed rate mortgage share
- Euribor indexation tracking
- Credit to households breakdown

### 15.4 Golden Visa SEF tracking

- Monthly visa grants
- Investment threshold analysis
- Geographic distribution of investment

### 15.5 Tourism-housing nexus (distinctive for PT)

- Airbnb listings via AirDNA (paid) ou scraping alternatives
- Alojamento Local registrations (Turismo de Portugal)
- Hotel capacity + occupancy

---

## 16. Editorial pipeline integration

Com o manual + plano de dados, 22+ ângulos editoriais (do Cap 20 do manual) ficam operacionalmente prontos para materialization.

### 16.1 High-value angles priorizados

| Ângulo | Dados necessários | Tier |
|---|---|---|
| "AI bubble debate — matriz 4-way" | F1, F2, concentration metrics | 1 |
| "Portugal 2026 vs 2007 — framework integrado" | BIS overlay + FCS + CCCS | 1 |
| "CAPE 35 em 2026 — Shiller's warning" | F1 valuations Shiller | 1 |
| "Os quatro diagnósticos aplicados" | All four diagnostics | 1 |
| "Bubble Warning 2026 status per country" | Joint FCS + BIS | 1 |
| "Crypto MVRV 2026 — where are we?" | On-chain Glassnode | 1 |
| "Real estate bifurcation post-Covid" | Case-Shiller + commercial RE | 2 |
| "Minsky fragility em 2026" | Full Minsky composite | 2 |
| "Wealth effect de $100T" | Household wealth + MPCs | 2 |
| "Soros reflexivity applied to AI" | Qualitative + F1/F2 | 1 |

### 16.2 Automation de alerts

SONAR pode gerar alerts quando:
- FCS crosses state boundary (Euphoria/Optimism/Caution/Stress)
- Bubble Warning level changes (none → amber → red → severe)
- BIS credit gap crosses threshold
- AAII extreme sentiment (>30 or <-10)
- CFTC extreme positioning
- Crypto MVRV extreme (>3.5 or <1.0)
- VIX regime change

Cada alert pode trigger editorial angle + data visualization automático.

---

## Anexo A — URLs e endpoints específicos

### A.1 Primary data sources

| Source | URL | Cost | Update |
|---|---|---|---|
| Shiller CAPE data | `www.econ.yale.edu/~shiller/data/ie_data.xls` | Free | Monthly |
| Damodaran ERP | `pages.stern.nyu.edu/~adamodar/pc/implprem/histimpl.xlsx` | Free | Monthly |
| Multpl PE/PB/PS | `multpl.com/*-ratio/table/by-month` | Free scrape | Daily |
| AAII sentiment | `aaii.com/sentimentsurvey/sent_results` | Free | Weekly |
| CFTC COT | `cftc.gov/MarketReports/CommitmentsofTraders/index.htm` | Free | Weekly |
| FINRA margin | `finra.org/investors/learn-to-invest/advanced-investing/margin-statistics` | Free | Monthly |
| CBOE put/call | `cboe.com/us/options/market_statistics/` | Free | Daily |
| NY Fed term premium | `newyorkfed.org/research/data_indicators/term-premia-tabs` | Free | Monthly |
| BIS credit/property | `bis.org/statistics/c_gaps.htm` + `/pp.htm` + `/dsr.htm` | Free | Quarterly |
| Case-Shiller | FRED `CSUSHPISA` | Free | Monthly |
| Glassnode | `api.glassnode.com/v1/metrics/` | $29-$799/mo | Daily |
| Coinglass | `coinglass.com/api/` | Free + $39/mo | Daily |
| CoinGecko | `api.coingecko.com/api/v3/` | Free + paid | Daily |
| Fear & Greed | `alternative.me/crypto/fear-and-greed-index/` | Free | Daily |
| Chicago NFCI | FRED `NFCI` | Free | Weekly |
| ICE HY/IG | FRED `BAMLH0A0HYM2` etc. | Free | Daily |
| VIX | FRED `VIXCLS` | Free | Daily |
| NAREIT REIT | `reit.com/data-research` | Free | Monthly |
| SEC EDGAR insider | `sec.gov/cgi-bin/browse-edgar` | Free | Daily |
| Open Insider | `openinsider.com` | Free scrape | Daily |
| Renaissance IPO | `renaissancecapital.com/IPO-Center/Pricings` | Free | Daily |
| Atlanta Fed GDPNow | FRED `GDPNOW` | Free | Daily |
| OECD property DB | `stats.oecd.org` — Prices | Free | Quarterly |
| Eurostat HPI | `ec.europa.eu/eurostat` — prc_hpi | Free | Quarterly |
| ECB RPPI | ECB SDW (existing connector) | Free | Quarterly |
| INE Portugal IPH | `ine.pt` | Free | Quarterly |
| FSB Shadow Banking | `fsb.org/work-of-the-fsb/` | Free | Annual |

### A.2 Optional Tier 2/3 sources

| Source | URL | Cost |
|---|---|---|
| Bloomberg Terminal | bloomberg.com | $24k/year |
| Refinitiv Eikon | refinitiv.com | $22k/year |
| S&P Capital IQ | spglobal.com/marketintelligence | $18k/year |
| Preqin (private credit) | preqin.com | $15k+/year |
| NCREIF (commercial RE) | ncreif.org | $5k+/year |
| Green Street (CRE) | greenstreet.com | $25k+/year |
| ETF.com Pro | etf.com | $1k-5k/year |
| TrimTabs | trimtabs.com | $2.4k+/year |
| Barchart API | barchart.com | $99-499/mo |

---

## Anexo B — Checklist de setup

### Credenciais necessárias (Tier 1 MVP)

- [ ] FRED API key (já ativa — partilhada com outros planos)
- [ ] Glassnode account — Advanced tier ($29/mo)
- [ ] ECB SDW (já ativo — partilhado)
- [ ] Trading Economics key (já ativa — partilhada)
- [ ] BIS SDMX access (já ativo — partilhado)

### Pré-requisitos técnicos

- [ ] Python 3.11+ com pandas, requests, sqlalchemy
- [ ] `fredapi` library (existing)
- [ ] `openpyxl` for Excel parsing (Shiller, Damodaran)
- [ ] `beautifulsoup4` + `lxml` for HTML scraping (AAII, multpl, NY Fed)
- [ ] `cot_reports` library for CFTC
- [ ] `requests-cache` for polite scraping
- [ ] `glassnode` Python client (`pip install glassnode`)
- [ ] Cron jobs or scheduled Python scripts para daily/weekly/monthly tasks

### Verificações iniciais

- [ ] Shiller ie_data.xls downloads e parses correctly
- [ ] Damodaran histimpl.xlsx latest month matches website
- [ ] CAPE current value matches multpl.com current read
- [ ] VIX FRED latest value within 0.1 of CBOE publication
- [ ] AAII latest week percentages match aaii.com
- [ ] BIS credit gap Portugal matches BIS CSV download
- [ ] Glassnode MVRV latest value matches Glassnode Studio
- [ ] Case-Shiller National latest matches FRED publication
- [ ] HY OAS latest matches ICE BofA publication
- [ ] NFCI latest matches Chicago Fed website

### Backfill periods

- [ ] F1 Valuations: 30 years historical (back to 1995)
- [ ] F2 Momentum: 20 years historical (back to 2005)
- [ ] F3 Risk Appetite: 25 years historical (back to 2000 for VIX + spreads)
- [ ] F4 Positioning: 20 years historical (AAII back to 1987, COT back to 2000)
- [ ] BIS overlay: 40 years historical where available
- [ ] On-chain crypto: since inception (BTC 2013+, ETH 2016+)
- [ ] Real estate: 25 years historical
- [ ] Minsky layer: 20 years historical

### Production schedule

| Task | Frequency | Timing |
|---|---|---|
| FRED daily sync | Daily | 07:00 Lisbon |
| Multpl scrape | Daily | 07:30 Lisbon |
| CBOE P/C scrape | Daily | 08:00 Lisbon (after US close) |
| Glassnode on-chain | Daily | 06:00 Lisbon |
| Coinglass funding | Daily | 06:15 Lisbon |
| AAII weekly | Weekly Thursday | 07:00 Lisbon |
| CFTC COT | Weekly Friday | 22:00 Lisbon |
| Shiller CAPE | Monthly 1st Wed | 09:00 Lisbon |
| Damodaran ERP | Monthly 1st | 09:30 Lisbon |
| FINRA margin | Monthly mid | 10:00 Lisbon |
| BIS quarterly | Quarterly end+45d | 10:30 Lisbon |
| Case-Shiller | Monthly last Tuesday | 14:30 Lisbon |
| FCS recompute | Daily | 09:00 Lisbon post-data |
| Bubble Warning check | Daily | 09:15 Lisbon |
| Four diagnostics | Daily | 09:30 Lisbon |

---

## Anexo C — Arquitetura SONAR v17 consolidada

Com este plano, o schema SONAR atinge versão 17 e completa operacionalmente a arquitetura v1 — quatro ciclos com manual (4/4), master consolidado (4/4) e plano de dados (4/4).

### Contagem final de indicadores

| Ciclo | Indicadores Tier 1 | Indicadores Tier 2 | Indicadores Tier 3 |
|---|---|---|---|
| Crédito (v13) | 180 | 280 | 420 |
| Monetário (v14-15) | 220 | 350 | 520 |
| Económico (v16) | 480 | 650 | 900 |
| **Financeiro (v17)** | **550** | **750** | **1.050** |
| **Total SONAR v1** | **1.430** | **2.030** | **2.890** |

### Países cobertos

15 países em Tier 1-3 (US, EA aggregate, Germany, UK, Japan, France, Italy, Spain, Canada, Australia, Portugal, Ireland, Netherlands, Sweden, Switzerland) + 4 experimental (China, India, Brazil, Turkey).

### Custos operacionais consolidados

| Item | Custo mensal Tier 1 | Custo mensal Tier 2 | Custo anual Tier 3 |
|---|---|---|---|
| Trading Economics | (shared) | (shared) | (shared) |
| Glassnode Advanced | $29 | $29 | $99 Institutional |
| Glassnode Professional | — | $399 | — |
| Coinglass Pro | — | $39 | — |
| Barchart API | — | $99 | — |
| Bloomberg Terminal | — | — | $24.000 |
| LSEG Datastream | — | — | $22.000 |
| Outros professional | — | — | $15.000 |
| **Total** | **~$29/mês** | **~$570/mês** | **~$60-70k/ano** |

### Roadmap global SONAR v1 → v2

**v1 (atingido com este plano)**:
- Quatro ciclos documentados (14.000+ parágrafos)
- Quatro masters consolidados
- Quatro planos de fontes de dados
- Schema v17 com ~1.430 indicadores Tier 1

**v2 (next)**:
- Dashboard interativo multi-ciclo (4 FCS/ECS/CCCS/MSC + overlays)
- Backtesting automation framework
- Alert system operacional
- Editorial pipeline com automation de charts
- Cross-cycle correlation tracking
- Global synchronization monitor
- Portugal-specific deep dive products

---

## Conclusão

Este plano completa a quarta data layer da arquitetura SONAR v1. Uma vez implementados os tiers, o framework estará integralmente operacional para gerar classificações sistemáticas dos quatro ciclos simultaneamente, produzir Bubble Warnings fundamentados, aplicar os quatro diagnósticos sobre qualquer país coberto, e alimentar pipeline editorial de "A Equação".

A escolha entre Tier 1 MVP (~$29/mês) e Tier 2 ($570/mês) deve ser feita à luz da tração editorial e da proximidade de fund launch. Tier 1 é suficiente para proof-of-concept e primeiras 12-24 colunas. Tier 2 eleva a qualidade dos datasets institucionais. Tier 3 apenas se justifica quando há AUM para amortizar.

O próximo passo operacional natural, após este plano estar implementado, é **v2 — dashboard interativo multi-ciclo** que cristalize visualmente a arquitetura SONAR v1 completa.

---

*Documento elaborado em Abril 2026 · 7365 Capital · SONAR Research*
*Paralelo aos planos de crédito (v13), monetário (v14-15) e económico (v16)*
*Fecha a arquitetura SONAR v1 — quatro ciclos, quatro manuais, quatro planos*
