# SONAR · Plano de Fontes de Dados do Ciclo Económico

**Documento de implementação técnica**
**Autor**: Hugo · 7365 Capital
**Versão**: v1.0 · Abril 2026
**Contexto**: Extensão do schema SONAR para v16 — terceiro ciclo a ser integrado após credit (v13) e monetário (v14-15)
**Âmbito**: Traduzir o Manual do Ciclo Económico (6 partes, 4.178 parágrafos) em pipeline de dados operacional

---

## Executive Summary

Este documento operacionaliza as fontes de dados necessárias para construir o Economic Cycle Score (ECS) para os países do universo SONAR. O objetivo é implementar a medição proposta nos capítulos 7-10 do manual (E1 Activity, E2 Leading, E3 Labor, E4 Sentiment) e alimentar o framework integrado descrito nos capítulos 15-17.

**Três princípios orientadores**:

1. **Reutilização inteligente** — os planos de crédito (v13) e monetário (v14-15) já cobriram integralmente FRED, ECB SDW, Eurostat, OECD SDMX, BIS, BPStat. Este plano concentra-se em **adições distintivas do económico** sem duplicar infraestrutura existente.

2. **Nowcasting como cidadão de primeira classe** — o capítulo 19 do manual dedicou tratamento extenso a Fed GDPNow, NY Fed Nowcast, Sahm Rule automation, Growth-at-Risk. Este plano traduz isso em connectors operacionais, não em consulta pontual.

3. **Alternative data sem over-engineering** — card spending, shipping, news sentiment, job postings são valiosos mas variáveis em disponibilidade/custo. Proposta é Tier 1 MVP sem alternative data, Tier 2 com gradual introdução, Tier 3 institutional-grade.

**Nova cobertura estimada**: 480-650 indicadores adicionais, trazendo SONAR total para ~2.350 signals across 15 countries × 4 cycles.

**Esforço estimado**: 4 semanas para Tier 1 MVP operacional, 8 semanas para Tier 2, 12 semanas para Tier 3.

---

## 1. Âmbito e delimitação

### 1.1 O que este plano cobre

Ficou estabelecido no capítulo 7 que o ciclo económico usa a composição **E1 + E2 + E3 + E4** com pesos **35/25/25/15**. As fontes agrupam-se conforme:

| Layer | Cobertura | Esta secção |
|---|---|---|
| **E1 Activity** | GDP, IP, retail, personal income, employment, composite coincident | §3 |
| **E2 Leading** | Yield curve, credit spreads, PMIs, LEI, OECD CLI, ECRI WLI, permits, orders | §4 |
| **E3 Labor** | NFP, unemployment, Sahm Rule, JOLTS, wages, claims, Beveridge | §5 |
| **E4 Sentiment** | UMich, Conference Board, inflation expectations, ISM, NFIB, EPU, EC ESI, ZEW, Ifo, VIX, Tankan | §6 |
| **Nowcasting** | Fed GDPNow, NY Fed Nowcast, STLENI, ADS Index, weekly indicators | §7 |
| **Alternative data** | Card spending, LinkedIn, shipping, news sentiment | §8 |

### 1.2 O que este plano NÃO cobre (já está em v13-v15)

Os connectors já implementados no SONAR cobrem integralmente as seguintes fontes, referenciadas aqui apenas quando indicador económico específico requer **nova serie** dentro delas:

- **FRED API (v13)** — já operacional. Esta fase adiciona ~80 series específicas económicas.
- **ECB Statistical Data Warehouse (v14)** — já operacional para monetário. Economic adiciona HICP core, unemployment EA, indústria.
- **Eurostat API (v13)** — já operacional. Economic adiciona GDP nacional, labor surveys.
- **OECD SDMX (v13)** — já operacional. Economic adiciona CLI composites, confidence indices.
- **BIS Data Portal (v13)** — já operacional. Economic adiciona property prices, international labor.
- **BPStat/BdP APIs (v14)** — já operacional. Economic adiciona INE Portugal data layer.

### 1.3 Países prioritários (replicando Tier do manual)

| Tier | Países | Cobertura ECS |
|---|---|---|
| **Tier 1 — full** | US, EA aggregate, Germany, UK, Japan | 100% indicators |
| **Tier 2 — good** | France, Italy, Spain, Canada, Australia | ~80% indicators |
| **Tier 3 — limited** | Portugal, Ireland, Netherlands, Sweden, Switzerland | ~60% indicators |
| **Tier 4 — experimental** | China, India, Brazil, Turkey | ~40% indicators, wider confidence |

Portugal permanece em Tier 3 — inclui EA overlay + INE/BdP específico. Consistência com planos anteriores.

---

## 2. Arquitetura de tiers

Mesmo modelo gradual dos dois planos anteriores:

### Tier 1 — MVP (semanas 1-4)

**Critério**: connectors gratuitos, suficientes para publicar ECS Tier 1 countries com confidence razoável.

Deliverables:
- FRED connector estendido com ~80 novas series
- Eurostat connector estendido com GDP/labor EA countries
- OECD CLI connector (composite leading indicators)
- Atlanta Fed GDPNow via FRED `GDPNOW`
- NY Fed Nowcast via scraping/API
- Sahm Rule automated computation
- Conference Board LEI via FRED `USSLIND`
- Portugal layer: INE quarterly GDP + BdP monthly indicators

Resultado: ECS operacional para US, UK, EA aggregate, Germany, Japan. Portugal parcialmente coberto.

### Tier 2 — comunicação (semanas 5-8)

**Critério**: elevação para nível que permite columns de mercado robustas sem gap evidentes.

Deliverables:
- S&P Global PMI coverage expandido (headlines para 20+ países)
- Philly Fed ADS Index daily
- NY Fed GSCPI (Global Supply Chain Pressure Index)
- EPU Index (policyuncertainty.com) Baker-Bloom-Davis
- Michigan 5Y inflation expectations (`MICH`)
- Conference Board Consumer Confidence
- Senior Loan Officer Opinion Survey (SLOOS) quarterly
- Atlanta Fed Wage Growth Tracker
- Fed Beveridge curve dashboard data

Resultado: ECS com alguns leading/sentiment depth. Cobertura geográfica estendida.

### Tier 3 — institutional-grade (semanas 9-12)

**Critério**: alternative data + nowcasting sophistication para decisões institutional.

Deliverables:
- ECRI WLI weekly (subscription)
- LinkedIn Economic Graph (limited access)
- Chetty/Opportunity Insights card spending (public GitHub)
- Bloomberg/Refinitiv for PMI sub-components
- Custom Python ML recession probability model
- Growth-at-Risk backtested framework
- Weekly Economic Index (Lewis-Mertens-Stock) via FRED

Resultado: ECS com nowcasting sophistication comparable a top research desks.

---

## 3. Layer E1 — Activity Indicators

### 3.1 US core E1 — FRED connector extension

Todas as series abaixo via FRED API existente (v13 connector). Adiciona-se apenas à watchlist, sem infraestrutura nova.

| Série | Nome | Frequência | Lag | Peso E1 |
|---|---|---|---|---|
| `GDPC1` | Real GDP | Q | 30d | 25% |
| `GDPC96` | Real GDP (alternative vintage) | Q | 30d | — |
| `GDI` | Gross Domestic Income | Q | 30d | — |
| `A261RX1Q020SBEA` | Real GDI | Q | 30d | — |
| `INDPRO` | Industrial Production | M | 2w | 15% |
| `TCU` | Capacity Utilization | M | 2w | — |
| `PAYEMS` | Non-farm Payrolls | M | 1w | 20% |
| `USPRIV` | Private Payrolls | M | 1w | — |
| `CES3000000001` | Manufacturing Payrolls | M | 1w | — |
| `CES2000000001` | Construction Payrolls | M | 1w | — |
| `RSXFS` | Retail and Food Services Sales | M | 2w | 10% |
| `RRSFS` | Real Retail and Food Services Sales | M | 2w | — |
| `RSXFSN` | Retail (non-seasonally adjusted) | M | 2w | — |
| `MRTSSM44X72USS` | Retail Sales ex-autos | M | 2w | — |
| `W875RX1` | Real Personal Income ex-transfers | M | 2w | 15% |
| `PCEC96` | Real PCE | M | 2w | — |
| `GPDIC1` | Real Gross Private Domestic Investment | Q | 30d | — |
| `GCEC1` | Real Government Consumption | Q | 30d | — |
| `NETEXP` | Net Exports (nominal) | Q | 30d | — |

### 3.2 US composite coincident indicators

| Série | Source | Frequência | Uso |
|---|---|---|---|
| `CFNAI` | Chicago Fed National Activity Index | M | Composite benchmark |
| `CFNAIMA3` | CFNAI 3-month Moving Average | M | Smoothed |
| `USSLIND` | Conference Board Coincident Index | M | US-wide composite |

### 3.3 EA core E1 — Eurostat connector extension

Via Eurostat existing connector (v13). Datasets a adicionar à watchlist:

| Dataset | Descrição | Frequência |
|---|---|---|
| `namq_10_gdp` | Quarterly GDP and its components (EA + national) | Q |
| `namq_10_a10` | GDP by industry sector | Q |
| `sts_inpr_m` | Industrial Production monthly | M |
| `sts_trtu_m` | Retail trade volume | M |
| `lfsi_emp_m` | Employment (monthly) | M |
| `une_rt_m` | Unemployment rate monthly | M |
| `ei_bsco_m` | Consumer confidence indicator | M |
| `ei_bsin_m_r2` | Industrial confidence | M |
| `ei_bssi_m_r2` | Services confidence | M |

### 3.4 UK E1 — ONS connector (new)

**Novo connector leve** — UK Office for National Statistics via `https://api.ons.gov.uk/dataset/{dataset-id}`.

| Dataset ID | Descrição | Frequência |
|---|---|---|
| `monthly-gdp` | Monthly GDP estimate (UK unique among AEs) | M |
| `labour-market` | Labor Force Survey monthly | M |
| `retail-sales` | Retail sales monthly | M |
| `industrial-production` | Production index monthly | M |

### 3.5 Japan E1 — Statistics Bureau / BOJ

**Connector tentativo** — Statistics Bureau Japan + BOJ data portal. Menos standardized; scraping podería ser necessário inicialmente, com migração para BOJ API posteriormente.

Indicadores:
- Tankan quarterly business survey (BOJ)
- Industrial production monthly (METI)
- Retail sales monthly (METI)
- Unemployment rate monthly (Stats Bureau)

### 3.6 Portugal E1 — INE + BdP layer

Via BPStat connector existente (v14) + novo INE connector lightweight.

**INE datasets** (via web scraping inicial, API migration later):
- Quarterly GDP (Contas Nacionais Trimestrais)
- Monthly labor force estimate (Inquérito ao Emprego)
- Monthly industrial production
- Monthly retail sales
- Tourism indicators (critical for PT cycle: chegadas, dormidas, rendimento turismo)

### 3.7 OECD cross-country aggregate

Via OECD SDMX existing connector (v13). Datasets a adicionar:

| Dataset | Cobertura | Frequência |
|---|---|---|
| `SNA_TABLE1` | GDP annual cross-country | A |
| `QNA` | Quarterly National Accounts | Q |
| `MEI` | Main Economic Indicators (unified) | M/Q |
| `STLABOUR` | Short-term Labour Statistics | M |

---

## 4. Layer E2 — Leading Indicators

### 4.1 Yield curve — primary leading indicator

Via FRED existing connector. Séries críticas:

| Série | Descrição | Frequência |
|---|---|---|
| `T10Y3M` | 10Y - 3M Treasury spread (NY Fed preferred) | D |
| `T10Y2Y` | 10Y - 2Y Treasury spread (market focus) | D |
| `T10Y5Y` | 10Y - 5Y Treasury spread | D |
| `DGS10` | 10Y Treasury Constant Maturity | D |
| `DGS2` | 2Y Treasury Constant Maturity | D |
| `DGS3MO` | 3M Treasury Bill | D |
| `DFEDTARU` | Federal Funds Upper Target | D |

**Engstrom-Sharpe Near-term Forward Spread (NFS)**: computed internamente (não é série FRED direta). Requer forward rates — available via Fed H.15 release.

### 4.2 Credit spreads — financial stress proxy

Via FRED existing connector:

| Série | Descrição | Frequência |
|---|---|---|
| `BAA10Y` | BAA - 10Y Treasury spread | D |
| `BAMLH0A0HYM2` | ICE BofA US High Yield OAS | D |
| `BAMLC0A0CM` | ICE BofA US IG Corporate OAS | D |
| `BAMLC0A4CBBB` | BBB Corporate OAS | D |
| `BAMLH0A3HYC` | CCC and Lower Rated HY OAS | D |
| `EBP_OA` | Excess Bond Premium (Gilchrist-Zakrajšek) | M |

### 4.3 PMIs — survey-based leading

**S&P Global / ISM** — headline values são públicos on release day. Para component detail (new orders, employment, prices), Bloomberg or Refinitiv needed (Tier 3).

MVP approach — scrape headline values from:

| Source | Frequência | Países |
|---|---|---|
| `ism.ws` | M | US Manufacturing, Services |
| `spglobal.com/market-intelligence` | M | 40+ countries PMIs |
| `tradingeconomics.com` | M | Aggregated PMI dashboard |

FRED proxies when available:
- `NAPM` (ISM Manufacturing historical)
- `NAPMII` (ISM Services historical)

**China-specific** (important given divergences):
- Caixin Manufacturing PMI (monthly, private)
- NBS Official Manufacturing PMI (monthly, state-owned bias)
- Caixin Services PMI
- NBS Non-Manufacturing PMI

### 4.4 Conference Board Leading Economic Index

| Série | Descrição | Frequência |
|---|---|---|
| `USSLIND` | Conference Board LEI (US) | M |

**Component detail** via Conference Board subscription (Tier 3) — para decomposition analysis.

### 4.5 OECD Composite Leading Indicators

Via OECD SDMX existing connector:

| Dataset | Descrição | Frequência |
|---|---|---|
| `MEI_CLI` | Composite Leading Indicators | M |
| `MEI_CLI_AMPLITUDE_ADJUSTED` | CLI amplitude adjusted | M |
| `MEI_CLI_TREND_RESTORED` | CLI trend restored | M |

**Chave operacional**: extrair sub-series per country (37 members + aggregates like EA, OECD, G7, Asia-5).

### 4.6 Building permits e orders

Via FRED existing connector:

| Série | Descrição | Frequência |
|---|---|---|
| `PERMIT` | Building Permits (total private) | M |
| `HOUST` | Housing Starts | M |
| `PERMIT1` | Permits for 1-unit structures | M |
| `DGORDER` | Durable Goods Orders | M |
| `NEWORDER` | Manufacturers' New Orders | M |
| `ANDEV` | Orders non-defense capital goods ex-aircraft | M |
| `M0602AUSM027SBEA` | Core capex shipments | M |

### 4.7 Initial jobless claims — weekly leading

Via FRED existing connector:

| Série | Descrição | Frequência |
|---|---|---|
| `ICSA` | Initial Claims (seasonally adjusted) | W |
| `CCSA` | Continued Claims | W |
| `IC4WSA` | Initial Claims 4-week average | W |

**Frequência semanal é raro e valioso** — released every Thursday, minimal lag.

### 4.8 ECRI Weekly Leading Index

**Tier 3 only** — ECRI is commercial subscription. Tier 1/2 relies on publicly-disclosed crisis-era calls. Tier 3 considera full WLI time series.

URL: `businesscycle.com`

---

## 5. Layer E3 — Labor Market Depth

### 5.1 Headline unemployment — US

Via FRED existing connector:

| Série | Descrição | Frequência |
|---|---|---|
| `UNRATE` | Unemployment Rate (U-3) | M |
| `U6RATE` | U-6 Unemployment Rate | M |
| `LNS11300060` | Prime-age Labor Force Participation | M |
| `CIVPART` | Total Labor Force Participation | M |
| `EMRATIO` | Employment-Population Ratio | M |
| `LNS11300002` | Prime-age Employment-Population Ratio | M |

### 5.2 Sahm Rule — automation

**Critical operational feature** — capítulo 19 do manual destacou Sahm Rule como the single most reliable recession indicator.

Série pré-computada:

| Série | Descrição | Frequência |
|---|---|---|
| `SAHMCURRENT` | Real-time Sahm Rule Recession Indicator | M |
| `SAHMREALTIME` | Sahm Rule using real-time data | M |

**SONAR internal computation**:
```python
def compute_sahm_rule(unrate_series, window_short=3, window_long=12):
    """
    Sahm Rule: 3M MA of U-3 rate minus minimum of U-3 3M MA
    over past 12 months. Trigger at >= 0.5pp.
    """
    ur_3ma = unrate_series.rolling(window=window_short).mean()
    ur_12min = ur_3ma.rolling(window=window_long).min()
    sahm = ur_3ma - ur_12min
    trigger = sahm >= 0.5
    return sahm, trigger
```

**Alert**: Sahm Rule trigger é flagship SONAR alert — push notification to core system.

### 5.3 JOLTS — vacancies e flows

Via FRED existing connector:

| Série | Descrição | Frequência |
|---|---|---|
| `JTSJOL` | Job Openings | M |
| `JTSHIL` | Hires | M |
| `JTSQUL` | Quits | M |
| `JTSLDL` | Layoffs and Discharges | M |
| `JTSTSL` | Total Separations | M |

**Computed ratio**: Job Openings / Unemployed = labor market tightness proxy. Important since 2021-22 reached 2:1 (unprecedented).

### 5.4 Wages

Via FRED existing connector:

| Série | Descrição | Frequência |
|---|---|---|
| `AHETPI` | Average Hourly Earnings (production) | M |
| `CES0500000003` | Average Hourly Earnings (all employees) | M |
| `ECIWAG` | Employment Cost Index — Wages | Q |
| `ECIALLCIV` | Employment Cost Index — Total Compensation | Q |

**Atlanta Fed Wage Growth Tracker** (separate connector):
- URL: `atlantafed.org/chcs/wage-growth-tracker`
- Tracks median wage growth for continuously employed
- Important methodology — controls for composition changes
- Monthly publication
- Downloadable Excel + API via Atlanta Fed

### 5.5 Beveridge curve analysis

**Computed visualization**, não série única. Usa:
- `JTSJOR` (Job Openings Rate as % of employment)
- `UNRATE` (Unemployment Rate)

Plot joins these, SONAR computes curve position vs historical normal. Outward shift = structural concern signal.

### 5.6 Productivity (long-run anchor)

Via FRED:

| Série | Descrição | Frequência |
|---|---|---|
| `OPHNFB` | Nonfarm Business Output per Hour | Q |
| `COMPNFB` | Nonfarm Business Compensation per Hour | Q |
| `ULCNFB` | Unit Labor Cost Nonfarm Business | Q |

### 5.7 EA labor — Eurostat extension

| Dataset Eurostat | Descrição |
|---|---|
| `une_rt_m` | Unemployment rate monthly by country |
| `lfsi_emp_m` | Employment monthly |
| `lc_lci_r2_a` | Labor Cost Index annual |
| `earn_nt_net` | Net earnings |
| `jvs_q_nace2` | Job vacancy statistics |

### 5.8 Portugal labor — INE + IEFP

- INE Inquérito ao Emprego (quarterly LFS)
- IEFP monthly unemployment registration
- Eurostat harmonized unemployment PT
- BPStat wage growth indicators

---

## 6. Layer E4 — Sentiment

### 6.1 US consumer sentiment — dual source

Via FRED existing connector:

| Série | Descrição | Frequência |
|---|---|---|
| `UMCSENT` | UMich Consumer Sentiment | M |
| `UMCSENTSM` | UMich Current Conditions | M |
| `UMCSENTE` | UMich Consumer Expectations | M |
| `MICH` | UMich 1Y Inflation Expectations | M |
| `MICHM5YM5` | UMich 5Y Inflation Expectations | M |
| `CSCICP03USM665S` | Conference Board Consumer Confidence | M |

### 6.2 NY Fed Survey of Consumer Expectations

**Novo connector** — NY Fed publishes SCE monthly via web + Excel downloads.

URL: `newyorkfed.org/microeconomics/sce`

Variables:
- 1Y inflation expectations
- 3Y inflation expectations
- 5Y inflation expectations
- Housing expectations
- Job search expectations
- Earnings expectations
- Household spending expectations

Frequency: M. Published ~10th of each month.

### 6.3 US business sentiment

Via FRED + Institute for Supply Management:

| Série | Descrição | Frequência |
|---|---|---|
| `NAPM` | ISM Manufacturing PMI | M |
| `NAPMII` | ISM Services PMI | M |
| `NAPMNOI` | ISM Manufacturing New Orders | M |
| `NFIBBTI` | NFIB Small Business Optimism | M |
| `NFIBPRICES` | NFIB Price Plans | M |

### 6.4 SLOOS — Senior Loan Officer Opinion Survey

**Quarterly survey, important leading indicator**. Released ~1 month after quarter-end.

URL: `federalreserve.gov/data/sloos.htm`

Key variables (separate FRED series):
- `DRTSCILM` — Net % banks tightening C&I loan standards (large/medium firms)
- `DRTSCIS` — Net % tightening C&I (small firms)
- `DRSCLCI` — Net % reporting stronger demand for C&I loans
- `DRTSCLCC` — Net % tightening credit card standards
- `DRTSCLNR` — Net % tightening residential mortgage standards

### 6.5 EU sentiment — Eurostat + DG ECFIN

Via Eurostat connector + DG ECFIN (European Commission) data portal:

| Dataset | Descrição |
|---|---|
| `ei_bsco_m` | Consumer Confidence Indicator EA |
| `ei_bsin_m_r2` | Industrial Confidence EA |
| `ei_bssi_m_r2` | Services Confidence EA |
| `ei_bsbu_m_r2` | Retail Confidence EA |
| `ei_bsco_q_r2` | Economic Sentiment Indicator (ESI) |

### 6.6 ZEW, Ifo, Sentix — Germany deep sentiment

**Subscription data** mostly, but headlines public.

- ZEW Indicator of Economic Sentiment (monthly): `zew.de`
- Ifo Business Climate Index (monthly): `ifo.de/en`
- Sentix Economic Index (monthly): `sentix.de`

Tier 2: scrape headline values. Tier 3: full subscription for component detail.

### 6.7 Japan Tankan

**Quarterly**, Bank of Japan publishes:
- URL: `boj.or.jp/en/statistics/tk`
- Key measure: Large Manufacturers Business Conditions DI
- Released March, June, September, December

### 6.8 VIX e market sentiment

Via FRED:

| Série | Descrição | Frequência |
|---|---|---|
| `VIXCLS` | VIX Close | D |
| `VXNCLS` | Nasdaq 100 Volatility | D |

### 6.9 Economic Policy Uncertainty

**Baker-Bloom-Davis EPU Index** (Cap 10 do manual):

URL: `policyuncertainty.com`

Datasets:
- US EPU (daily since 1985)
- Global EPU (monthly)
- Country-specific EPU for 20+ countries
- News-based, policy-expirations-based, and disagreement-based components

API: download CSVs. MVP: weekly refresh.

---

## 7. Nowcasting Layer (dedicated — parallel ao Cap 19)

### 7.1 Atlanta Fed GDPNow — primary US nowcast

**Access via FRED** (preferred — standardized):

| Série FRED | Descrição |
|---|---|
| `GDPNOW` | Atlanta Fed GDPNow current quarter estimate |

**Properties** (confirmed via search Apr 2026):
- Methodology: synthesizes bridge equation + factor model + Bayesian VAR
- Aggregates 13 subcomponents using BEA chain-weighting
- Average absolute error 0.77pp (2011:Q3–2025:Q2)
- RMSE 1.17pp
- Updated 5-6 times per month
- Release schedule available at `atlantafed.org/cqer/research/gdpnow`

**Alternative access (vintages)**:
- ALFRED: `alfred.stlouisfed.org/series?seid=GDPNOW` — preserves real-time vintages (essential for backtesting)
- Atlanta Fed Excel tracking file: `atlantafed.org/-/media/documents/cqer/researchcq/gdpnow/RealGDPTrackingSlides.pdf`
- EconomyNow mobile app (interface only)
- Trading Economics aggregation: `tradingeconomics.com/united-states/gdpnow-fed-data.html`

### 7.2 NY Fed Nowcast

**Methodology: Dynamic Factor Model** (Giannone-Reichlin-Small).

URL: `newyorkfed.org/research/policy/nowcast`

Characteristics (Cap 19 detail):
- ~36 data series (smaller than GDPNow's 150+)
- Updates weekly
- Less volatile, more structural
- Factor decomposition available

**Access strategy**:
- No FRED series direct (NY Fed publishes own platform)
- Web scraping for current value + download historical Excel
- Weekly refresh schedule

### 7.3 St. Louis Fed Economic News Index

**Nowcast alternativo** — useful cross-validation.

| Série FRED | Descrição |
|---|---|
| `STLENI` | St. Louis Fed Economic News Index: Real GDP Nowcast |

Methodology: uses economic content from key monthly economic data releases. Produces quarterly GDP nowcast.

### 7.4 Weekly Economic Index (Lewis-Mertens-Stock)

**Unique weekly frequency** — one of the few macro indicators updated weekly.

| Série FRED | Descrição |
|---|---|
| `WEI` | Weekly Economic Index | W |

Useful for mid-quarter updates when monthly data not yet arrived.

### 7.5 Philly Fed ADS Index

**Daily** business cycle indicator.

URL: `philadelphiafed.org/surveys-and-data/real-time-data-research/ads-index`

Characteristics:
- 6 coincident indicators combined continuously
- Daily update
- Scale: 0 = average growth, negative = below average
- Useful for cross-validation of weekly/monthly data

### 7.6 Sahm Rule real-time

Covered §5.2. Re-emphasized here as nowcasting priority.

### 7.7 NY Fed recession probability model

**Yield curve-based recession probability** — capítulo 19.

URL: `newyorkfed.org/research/capital_markets/ycfaq.html`

Methodology: probit regression of NBER recessions on 10Y-3M yield curve spread.

Access:
- Monthly update
- Published as Excel spreadsheet
- SONAR replicates internally using FRED `T10Y3M`

Internal computation (paralleling NY Fed method):
```python
def ny_fed_recession_prob(t10y3m_avg_spread):
    """
    NY Fed probit model simplified.
    Constants from public NY Fed methodology documentation.
    """
    import scipy.stats as st
    alpha = -0.5333
    beta = -0.6334
    # alpha and beta from NY Fed methodology paper
    probability = st.norm.cdf(alpha + beta * t10y3m_avg_spread)
    return probability
```

### 7.8 Growth-at-Risk framework

**Adrian-Boyarchenko-Giannone 2019** — AER. Dedicated section Cap 19.

Implementation:
- Quantile regression of GDP growth on financial conditions (NFCI via FRED `NFCI`)
- Outputs full distribution of expected growth
- Key metric: 10th percentile (Growth-at-Risk)

Internal Python module — implementation via:
```python
import statsmodels.formula.api as smf

def growth_at_risk_qregression(gdp_growth, nfci, quantiles=[0.05, 0.10, 0.25, 0.50, 0.75]):
    """
    Quantile regression for Growth-at-Risk framework.
    """
    results = {}
    for q in quantiles:
        model = smf.quantreg('gdp_growth ~ nfci', data).fit(q=q)
        results[q] = model
    return results
```

### 7.9 SONAR custom recession probability model

**8-input composite** (capítulo 19.11):

```python
sonar_recession_prob_6M = weighted_average(
    sahm_rule_probability,           # weight 0.25
    yield_curve_ny_fed_model_prob,   # weight 0.20
    lei_6m_growth_probability,       # weight 0.15
    growth_at_risk_10pct,            # weight 0.10
    ecri_wli_growth_sign,            # weight 0.10
    pmi_composite_probability,       # weight 0.10
    consumer_sentiment_prob,         # weight 0.05
    credit_spread_hy_probability,    # weight 0.05
)
```

Validation target: backtest 1970-present, target 85%+ hit rate, <15% false positive rate.

---

## 8. Alternative Data

### 8.1 Card spending — consumption real-time

**Commercial providers** (Tier 2/3):
- Bloomberg consumer spending trackers (subscription)
- Visa SpendingPulse (subscription)
- Bank of America institute spending (public reports, limited API)
- Chase Spending Pulse (limited public access)

**Public alternative** — Chetty/Opportunity Insights:
- URL: `github.com/OpportunityInsights/EconomicTracker`
- Daily/weekly data since 2020
- Card spending, employment, time use
- CC BY license
- **Recommended Tier 2** — high value, public access

### 8.2 Job postings — labor demand real-time

**LinkedIn Economic Graph**:
- URL: `economicgraph.linkedin.com`
- Restricted access, research partnerships
- Tier 3 only for proprietary data
- Public reports sometimes available

**Indeed Hiring Lab**:
- URL: `hiringlab.org`
- Published analyses, limited raw data
- Useful supplementary analysis

**Conference Board Help Wanted Online**:
- Discontinued 2018, replaced by newer measures
- Historical data useful for longer backtests

### 8.3 Shipping / logistics

**Container shipping**:
- Baltic Dry Index — daily, via public trackers
- Shanghai Containerized Freight Index
- Harpex (Hamburg-based)
- Drewry World Container Index

**Trucking**:
- Cass Freight Index monthly — `cassinfo.com`
- ATA (American Trucking Associations) — subscription

**Railroad**:
- Association of American Railroads weekly data — public

### 8.4 NY Fed Global Supply Chain Pressure Index

**Important specific indicator** — referenced Cap 16 (Stagflation diagnosis):

URL: `newyorkfed.org/research/policy/gscpi`

| Série | Descrição |
|---|---|
| `GSCPI` | NY Fed Global Supply Chain Pressure Index | M |

- Integrates data from multiple countries, commodities, shipping
- Monthly frequency
- Z-score interpretation (>2 = extreme stress)

### 8.5 News sentiment

**EPU Index** já coberto §6.9.

**Additional news analytics**:
- GDELT (Global Database of Events, Language, and Tone) — public, but massive
- Bloomberg news sentiment — commercial

**MVP recommendation**: rely on EPU + headline-based pattern matching. Tier 3: invest in Bloomberg access.

### 8.6 Electricity e fuel consumption

**US energy data**:
- EIA (Energy Information Administration) weekly data
- Public API
- Useful industrial activity proxy

**EU energy**:
- ENTSO-E Transparency Platform (electricity)
- Commercial weekly natural gas data

---

## 9. Schema SQL — v16 extension

### 9.1 Overview

Extensão do schema SONAR de v15 (monetário) para v16 (económico).

**Convention**: todas as tables novas prefixadas `economic_*` para disambiguation.

### 9.2 Core tables

```sql
-- ============================================================
-- v16: Economic Cycle tables
-- ============================================================

-- E1-E4 raw indicators (one table per sub-index family)
CREATE TABLE IF NOT EXISTS economic_indicators_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country TEXT NOT NULL,
    date TEXT NOT NULL,             -- ISO date
    series_code TEXT NOT NULL,      -- e.g., PAYEMS, GDPC1, T10Y3M
    series_name TEXT,
    value REAL,
    unit TEXT,
    source TEXT NOT NULL,           -- FRED, Eurostat, OECD, BPStat, NYFed, ...
    frequency TEXT,                 -- D, W, M, Q, A
    layer TEXT NOT NULL,            -- E1, E2, E3, E4
    vintage_date TEXT,              -- for ALFRED revisions
    fetched_at TEXT NOT NULL,
    UNIQUE(country, date, series_code, vintage_date)
);

CREATE INDEX IF NOT EXISTS idx_econ_raw_country_date ON economic_indicators_raw(country, date);
CREATE INDEX IF NOT EXISTS idx_econ_raw_series ON economic_indicators_raw(series_code);
CREATE INDEX IF NOT EXISTS idx_econ_raw_layer ON economic_indicators_raw(layer);

-- Z-scored indicators (10-year rolling window)
CREATE TABLE IF NOT EXISTS economic_indicators_zscored (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country TEXT NOT NULL,
    date TEXT NOT NULL,
    series_code TEXT NOT NULL,
    raw_value REAL,
    z_score REAL,
    percentile REAL,
    rolling_mean REAL,
    rolling_std REAL,
    window_years INTEGER DEFAULT 10,
    computed_at TEXT NOT NULL,
    UNIQUE(country, date, series_code)
);

CREATE INDEX IF NOT EXISTS idx_econ_zscored_country_date
    ON economic_indicators_zscored(country, date);

-- Sub-indices E1-E4 computed
CREATE TABLE IF NOT EXISTS economic_sub_indices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country TEXT NOT NULL,
    date TEXT NOT NULL,
    cluster TEXT,                   -- 1-6 per Cap 6
    e1_activity REAL,               -- [0, 100]
    e2_leading REAL,                -- [0, 100]
    e3_labor REAL,                  -- [0, 100]
    e4_sentiment REAL,              -- [0, 100]
    ecs REAL,                       -- ECS = 0.35·E1 + 0.25·E2 + 0.25·E3 + 0.15·E4
    confidence REAL,                -- [0, 1]
    data_freshness_days INTEGER,
    phase TEXT,                     -- Expansion, Slowdown, Recession, Recovery
    phase_sub_classification TEXT,  -- Strong, Mild, Late, etc.
    momentum TEXT,                  -- positive, stable, negative
    stagflation_flag INTEGER,       -- 0 or 1
    computed_at TEXT NOT NULL,
    UNIQUE(country, date)
);

CREATE INDEX IF NOT EXISTS idx_econ_subidx_country_date
    ON economic_sub_indices(country, date);

-- ECS historical (time series per country)
CREATE TABLE IF NOT EXISTS ecs_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country TEXT NOT NULL,
    date TEXT NOT NULL,
    ecs REAL NOT NULL,
    phase TEXT,
    nber_dating TEXT,               -- for US: NBER recession? (T/F)
    cepr_dating TEXT,               -- for EA: CEPR recession? (T/F)
    oecd_cli_state TEXT,            -- OECD CLI position
    ecri_wli_sign TEXT,             -- for comparison
    UNIQUE(country, date)
);
```

### 9.3 Nowcasting tables

```sql
-- ============================================================
-- Nowcasting history (paralelo ao recession probability models)
-- ============================================================

CREATE TABLE IF NOT EXISTS nowcast_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    country TEXT NOT NULL,
    nowcast_source TEXT NOT NULL,   -- GDPNow, NYFed, STLENI, WEI, ADS, Sahm
    target_quarter TEXT,            -- e.g., "2026Q1"
    gdp_growth_nowcast REAL,        -- annualized % change
    gdp_growth_actual REAL,         -- filled after release
    forecast_error REAL,            -- actual - nowcast
    vintage_date TEXT,              -- when nowcast was made
    UNIQUE(date, country, nowcast_source, target_quarter, vintage_date)
);

CREATE INDEX IF NOT EXISTS idx_nowcast_country_date
    ON nowcast_history(country, date);

-- Recession probability models
CREATE TABLE IF NOT EXISTS recession_probability_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    country TEXT NOT NULL,
    model_name TEXT NOT NULL,       -- NYFed_ProbIt, Sahm, SONAR_Composite, GaR
    horizon_months INTEGER,         -- 6, 12, 18, 24
    probability REAL,               -- [0, 1]
    inputs_json TEXT,               -- JSON with input values for reproducibility
    triggered INTEGER,              -- 0 or 1 if threshold crossed
    computed_at TEXT NOT NULL,
    UNIQUE(date, country, model_name, horizon_months)
);

CREATE INDEX IF NOT EXISTS idx_recprob_country_date
    ON recession_probability_models(country, date);

-- Sahm Rule specific tracking
CREATE TABLE IF NOT EXISTS sahm_rule_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    country TEXT NOT NULL,
    unrate REAL,
    unrate_3ma REAL,
    unrate_12month_min REAL,
    sahm_value REAL,                -- U-rate 3MA minus 12M min
    triggered INTEGER,              -- 0 or 1 (>= 0.5)
    UNIQUE(date, country)
);

CREATE INDEX IF NOT EXISTS idx_sahm_country_date
    ON sahm_rule_history(country, date);
```

### 9.4 Beveridge curve + Stagflation diagnostics

```sql
-- Beveridge curve positioning
CREATE TABLE IF NOT EXISTS beveridge_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    country TEXT NOT NULL,
    unemployment_rate REAL,
    job_openings_rate REAL,         -- as % of employment + openings
    position_vs_historical REAL,    -- signed distance from normal curve
    interpretation TEXT,            -- along_curve, outward_shift, inward_shift
    UNIQUE(date, country)
);

-- Stagflation trigger history
CREATE TABLE IF NOT EXISTS stagflation_triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    country TEXT NOT NULL,
    trigger_a_classical INTEGER,    -- inflation + unemployment + low growth
    trigger_b_emerging INTEGER,     -- momentum-based
    trigger_c_entrenchment INTEGER, -- expectations + wages + core
    trigger_d_supply_shock INTEGER, -- oil + core + growth decline
    stagflation_score REAL,         -- max of 4 trigger scores
    flag_active INTEGER,            -- 0 or 1
    UNIQUE(date, country)
);
```

### 9.5 4-way integration table

```sql
-- ============================================================
-- Cross-cycle integration (connects economic + credit + monetary + financial)
-- ============================================================

CREATE TABLE IF NOT EXISTS integrated_cycle_position (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    country TEXT NOT NULL,
    
    -- Economic cycle (this project)
    ecs REAL,
    economic_phase TEXT,
    
    -- Credit cycle (v13 project)
    cccs REAL,
    credit_phase TEXT,
    
    -- Monetary cycle (v14-15 project)
    msc REAL,
    monetary_phase TEXT,
    
    -- Financial cycle (future)
    fcs REAL,
    financial_phase TEXT,
    
    -- Integrated diagnostics
    canonical_pattern TEXT,         -- Pattern 1-6 per Cap 17
    configuration_type TEXT,        -- standard, divergent, stagflation, etc.
    stagflation_flag INTEGER,       -- from economic
    dilemma_flag INTEGER,           -- from monetary
    boom_flag INTEGER,              -- from credit
    euphoria_flag INTEGER,          -- from financial
    
    historical_precedents INTEGER,  -- count of similar configurations
    base_rate_continued_expansion REAL,
    base_rate_slowdown REAL,
    base_rate_recession REAL,
    
    alert_level TEXT,               -- green, yellow, orange, red
    
    UNIQUE(date, country)
);

CREATE INDEX IF NOT EXISTS idx_integrated_country_date
    ON integrated_cycle_position(country, date);
```

### 9.6 Migration script

```sql
-- v15 → v16 migration
BEGIN TRANSACTION;

-- Verify prerequisites
SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='monetary_stance_history';
-- Must return 1 (v15 prerequisite)

-- Execute all CREATE TABLE statements above

-- Update schema version
UPDATE schema_version SET version = 16 WHERE singleton = TRUE;

COMMIT;
```

---

## 10. Roadmap 4-week implementation

### Semana 1 — FRED extension + E1 core

**Foco**: E1 Activity para US via FRED.

Tasks:
- Extend FRED connector watchlist com ~80 new series (listed §3.1)
- Implement E1 composite weighting per Cap 7
- Z-score computation on 10-year rolling window
- Unit tests against known historical periods (2008, 2020)
- Initial validation: Covid recession correctly classified

Deliverable: E1 score para US 1960-presente.

### Semana 2 — E2 Leading + Sahm Rule

**Foco**: Leading indicators + labor market signals.

Tasks:
- FRED yield curve series (T10Y3M, T10Y2Y, etc.)
- Credit spreads (BAA10Y, HY OAS)
- Conference Board LEI (USSLIND)
- OECD CLI via existing OECD connector
- **Sahm Rule automation** (SAHMCURRENT + internal computation)
- Initial claims weekly tracker (ICSA)
- Building permits (PERMIT, HOUST)

Deliverable: E2 + E3 Sahm component operational. Alert system for Sahm trigger.

### Semana 3 — E3 JOLTS + E4 sentiment

**Foco**: Complete labor depth + sentiment layer.

Tasks:
- JOLTS series (openings, quits, hires, layoffs)
- Atlanta Fed Wage Growth Tracker
- UMich sentiment (UMCSENT) + inflation expectations (MICH)
- Conference Board Confidence
- ISM Manufacturing + Services
- EPU Index (Baker-Bloom-Davis) via scraping
- SLOOS quarterly credit conditions
- NY Fed SCE (inflation expectations monthly)

Deliverable: E3 + E4 complete for US. ECS compute for US 1960-present.

### Semana 4 — Cross-country + nowcasting

**Foco**: Extension to EA aggregate + Tier 1 countries + nowcasting layer.

Tasks:
- Eurostat extension for EA GDP/labor/confidence
- ONS connector lightweight (UK)
- BOJ scraping minimal (Japan)
- INE + BPStat extension (Portugal)
- GDPNow from FRED (`GDPNOW`)
- NY Fed Nowcast (scraping)
- STLENI (St. Louis Fed Economic News Index)
- Weekly Economic Index (WEI)
- SONAR recession probability model (8-input composite)
- Growth-at-Risk initial implementation

Deliverable: ECS operational Tier 1 (US, UK, EA, Germany, Japan). Portugal partial. Nowcasting panel populated.

### Validação final semana 4

**Backtest target**:
- US ECS vs NBER dating 1970-2023: 88%+ agreement
- Sahm Rule: triggered in all NBER recessions, no false positives
- SONAR composite recession probability: > 50% triggered in all US recessions 1970-present
- Nowcast GDPNow + NYFed cross-validation: tracking within 1pp historically

---

## 11. Anexo A — URLs consolidados

### A.1 US federal sources
- FRED API: `fred.stlouisfed.org`
- ALFRED (archival vintages): `alfred.stlouisfed.org`
- BEA: `bea.gov`
- BLS: `bls.gov`
- Census: `census.gov`
- Federal Reserve H.15: `federalreserve.gov/releases/h15`
- Atlanta Fed GDPNow: `atlantafed.org/cqer/research/gdpnow`
- Atlanta Fed Wage Tracker: `atlantafed.org/chcs/wage-growth-tracker`
- NY Fed Nowcast: `newyorkfed.org/research/policy/nowcast`
- NY Fed SCE: `newyorkfed.org/microeconomics/sce`
- NY Fed Yield Curve: `newyorkfed.org/research/capital_markets/ycfaq.html`
- NY Fed GSCPI: `newyorkfed.org/research/policy/gscpi`
- NY Fed Recession Probability: via NY Fed research data
- Philly Fed ADS: `philadelphiafed.org/surveys-and-data/real-time-data-research/ads-index`
- Philly Fed SPF: `philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters`
- Chicago Fed CFNAI: via FRED `CFNAI`, `CFNAIMA3`
- St. Louis Fed SLOOS: `federalreserve.gov/data/sloos.htm`
- St. Louis Fed Economic News Index: via FRED `STLENI`

### A.2 European sources
- Eurostat: `ec.europa.eu/eurostat`
- ECB SDW: `sdw.ecb.europa.eu`
- European Commission DG ECFIN: `ec.europa.eu/economy_finance/db_indicators`
- ZEW: `zew.de`
- Ifo: `ifo.de/en`
- Sentix: `sentix.de`
- UK ONS: `ons.gov.uk` (API at `api.ons.gov.uk`)

### A.3 Other major economies
- BOJ: `boj.or.jp/en/statistics/tk` (Tankan)
- Statistics Bureau Japan: `stat.go.jp`
- Bank of Canada: `bankofcanada.ca/rates/indicators`
- Reserve Bank of Australia: `rba.gov.au/statistics`
- China NBS: `stats.gov.cn`
- Caixin: via S&P Global

### A.4 Portugal specific
- BPStat (BdP): `bpstat.bportugal.pt`
- INE: `ine.pt`
- IEFP: `iefp.pt`

### A.5 International
- OECD: `data.oecd.org`
- IMF: `imf.org/en/Data`
- IMF WEO: `imf.org/en/Publications/WEO`
- BIS: `bis.org/statistics`

### A.6 Research/commercial
- Conference Board: `conference-board.org`
- ECRI: `businesscycle.com`
- Atlanta Fed EconomyNow app: iOS + Android
- EPU Index: `policyuncertainty.com`
- Opportunity Insights: `opportunityinsights.org` + `github.com/OpportunityInsights/EconomicTracker`
- LinkedIn Economic Graph: `economicgraph.linkedin.com`
- Indeed Hiring Lab: `hiringlab.org`
- Trading Economics: `tradingeconomics.com`

### A.7 PMI providers
- S&P Global: `spglobal.com/market-intelligence`
- ISM: `ism.ws`

### A.8 Alternative data
- Cass Freight Index: `cassinfo.com`
- Baltic Exchange: `balticexchange.com`
- EIA (energy): `eia.gov`
- ENTSO-E: `transparency.entsoe.eu`

---

## 12. Anexo B — Setup checklist

### B.1 Dependencies

```
# Python packages (incremental to monetary/credit)
pip install requests pandas numpy sqlalchemy statsmodels
pip install yfinance        # for some market data
pip install beautifulsoup4  # for scraping
pip install selenium        # for dynamic pages (NY Fed Nowcast)
pip install scipy           # for statistics
pip install scikit-learn    # for ML components
pip install openpyxl        # for Excel download processing
```

### B.2 Environment variables

```bash
# Already in place from monetary/credit plans:
FRED_API_KEY=xxx  # st.louis fed
OECD_USER_AGENT=xxx  # OECD SDMX
BPSTAT_API_TOKEN=xxx  # banco de portugal

# New for economic cycle:
ATLANTA_FED_USER_AGENT="SONAR Research/1.0 (hugo@7365capital.pt)"
PHILLY_FED_USER_AGENT="SONAR Research/1.0"
CONFERENCE_BOARD_API=optional  # Tier 3 subscription
ECRI_API=optional  # Tier 3 subscription
```

### B.3 SQLite schema migration

```bash
cd ~/sonar
sqlite3 sonar.db < migrations/v15_to_v16.sql
# Verify: SELECT version FROM schema_version; → should return 16
```

### B.4 Cron schedule

```cron
# Daily (morning, high-frequency indicators)
0 8 * * * /usr/bin/python3 ~/sonar/fetch_yield_curve.py
0 8 * * * /usr/bin/python3 ~/sonar/fetch_credit_spreads.py
0 8 * * * /usr/bin/python3 ~/sonar/fetch_vix.py
0 8 * * * /usr/bin/python3 ~/sonar/fetch_philly_fed_ads.py

# Weekly (Thursday — claims release)
0 15 * * 4 /usr/bin/python3 ~/sonar/fetch_initial_claims.py
0 10 * * 5 /usr/bin/python3 ~/sonar/fetch_weekly_economic_index.py

# Monthly — NFP (first Friday)
0 9 1-7 * 5 /usr/bin/python3 ~/sonar/fetch_nfp_release.py
0 9 1-7 * 5 /usr/bin/python3 ~/sonar/compute_sahm_rule.py  # critical
0 9 1-7 * 5 /usr/bin/python3 ~/sonar/check_sahm_alert.py

# Monthly — various mid-month
0 9 10 * * /usr/bin/python3 ~/sonar/fetch_nyfed_sce.py
0 9 14 * * /usr/bin/python3 ~/sonar/fetch_retail_sales.py
0 9 15 * * /usr/bin/python3 ~/sonar/fetch_industrial_production.py

# GDPNow updates (5-6x per month, better run more frequently)
0 10 * * * /usr/bin/python3 ~/sonar/fetch_gdpnow.py

# NY Fed Nowcast (weekly, Friday)
0 12 * * 5 /usr/bin/python3 ~/sonar/fetch_nyfed_nowcast.py

# Quarterly — GDP release (~end of quarter month 1-3)
0 9 27-30 1,4,7,10 * /usr/bin/python3 ~/sonar/fetch_gdp_release.py
0 9 10 2,5,8,11 * /usr/bin/python3 ~/sonar/fetch_sloos.py

# Daily ECS computation (integration)
0 11 * * * /usr/bin/python3 ~/sonar/compute_ecs.py
0 11 * * * /usr/bin/python3 ~/sonar/compute_integrated_position.py
```

### B.5 Alert triggers

Critical alerts to push immediately:

| Alert | Condition | Priority |
|---|---|---|
| **Sahm Rule** | sahm_value >= 0.5 | **P0** |
| **Yield curve inversion** | T10Y3M < 0 sustained 5 days | **P0** |
| **GDPNow crash** | GDPNow falls > 1pp in single update | P1 |
| **Stagflation flag** | Any trigger A-D activates | P1 |
| **ECS phase change** | Classification shifts | P1 |
| **Recession probability** | SONAR composite >= 50% | P1 |
| **LEI 6M growth** | Negative 3 consecutive months | P2 |
| **Claims spike** | ICSA > 4-week avg by 20%+ | P2 |

### B.6 Data quality checks

Pre-computation validation:
```python
def validate_economic_indicator(country, date, series_code, value):
    # 1. Value not NaN
    # 2. Value within historical 5-sigma band (flag outliers)
    # 3. Date not future
    # 4. Date not too stale (>90 days for monthly series)
    # 5. Series exists in metadata
    # Return (valid, warning_list)
```

Post-aggregation validation:
```python
def validate_ecs(country, date, ecs_value, sub_indices):
    # 1. ECS in [0, 100]
    # 2. All sub-indices in [0, 100]
    # 3. ECS approximately equals weighted sum
    # 4. Sub-indices consistency (labor + sentiment extremes flag)
    # 5. Historical continuity (no single-month >20pt changes without explanation)
    # Return (valid, warnings, suggestions)
```

### B.7 Testing checklist — acceptance criteria

Pre-Tier 1 release:
- [ ] 1970-2023 US data loads without errors
- [ ] E1-E4 composites compute for every month
- [ ] ECS series reasonably smooth (no jumps > 20pts without cause)
- [ ] Sahm Rule fires in every NBER recession 1970-present
- [ ] Sahm Rule zero false positives 1970-2020
- [ ] Yield curve inversion precedes every recession 1970-present
- [ ] ECS below 30 during every NBER recession
- [ ] ECS above 55 during every NBER expansion middle
- [ ] Backtest hit ratio NBER dating: 85%+ agreement at month level
- [ ] EA data loads for 2000-2023
- [ ] CEPR-dated EA recessions (2008-09, 2011-13, 2020) captured
- [ ] Portugal data loads via BPStat + INE
- [ ] Portugal 2011-13 crisis clearly recessionary per ECS
- [ ] Nowcasting cross-validates GDPNow vs NYFed vs STLENI (within 1pp historical)
- [ ] Growth-at-Risk distribution matches published IMF GFSR figures

Post-release monitoring:
- [ ] Daily ECS updates for Tier 1 countries
- [ ] Weekly Sahm Rule + yield curve review
- [ ] Monthly phase classification review
- [ ] Quarterly backtest against new data
- [ ] Annual weight recalibration

---

## 13. Métricas de sucesso

### Cobertura quantitativa — alvo

| Métrica | Tier 1 MVP | Tier 2 | Tier 3 |
|---|---|---|---|
| Series FRED ativas | +80 | +120 | +150 |
| Eurostat datasets | +10 | +15 | +20 |
| Países com ECS computado | 5 | 10 | 15 |
| Nowcasting sources | 3 (GDPNow, NYFed, Sahm) | 6 | 9 |
| Alternative data streams | 0 | 2 | 5 |
| Recession probability models | 3 | 5 | 8 |
| **Indicadores totais** | **~250** | **~380** | **~520** |

### Cobertura qualitativa — validação contra literature

- Sahm Rule triggered em 100% NBER recessions 1970-presente (target)
- Yield curve inversion precedeu 100% recessions com >6 mês lead (target)
- ECS sub-30 durante 100% NBER recessions (target)
- ECS sub-30 durante 0% NBER expansions (target, ex-outliers)
- GDPNow vs actual GDP: média de abs(error) < 1.5pp (literature benchmark)

### Performance metrics operacional

- Refresh freshness Tier 1: < 1 dia data stale
- Sahm Rule alert latency: < 24h após NFP release
- GDPNow sync latency: < 4h após Atlanta Fed release
- ECS computation time: < 5s para single-country full series
- System uptime target: 99%+

---

## 14. Risk register

### 14.1 Dependência de FRED API

**Risk**: Downtime FRED ou mudança de limits.

**Mitigation**: keep 30-day rolling cache. ALFRED vintages preservation. Multiple redundancies via Eurostat/OECD for non-US series.

### 14.2 GDPNow methodology change

**Risk**: Atlanta Fed altera metodologia (happened in 2025 — per search, updated from pure bridge equation to bridge + BVAR).

**Mitigation**: monitor Atlanta Fed research updates. Keep legacy computation alongside. Document vintage differences in nowcast_history table.

### 14.3 Scraping fragility

**Risk**: Web scraping NY Fed Nowcast, PMIs, etc. breaks quando sites update.

**Mitigation**: wrap scraping em try/except with specific error codes. Fallback to manual spreadsheet parsing. Tier 3: subscribe to APIs onde disponível.

### 14.4 Portugal data gaps

**Risk**: INE/BPStat não fornece alguns indicators necessários.

**Mitigation**: Portugal already Tier 3 with wider confidence. Use EA overlays where domestic data gaps. Document known gaps in data_freshness_days.

### 14.5 Structural breaks

**Risk**: Post-Covid patterns break z-score normalization (rolling 10-year window contaminated).

**Mitigation**: Rolling window já é adaptation. For Covid period (2020-2021), optional "regime-switching" mode that treats these as outliers. Future: explicit regime-switching model.

### 14.6 Sahm Rule deanchoring

**Risk**: Sahm Rule may become less reliable in novel cycle dynamics (labor hoarding post-Covid may delay trigger).

**Mitigation**: Present Sahm alongside alternative labor signals. Backtest continuously. If breaks observed, add secondary triggers.

---

## 15. Open questions

**Q1**: Should we invest in ECRI WLI subscription Tier 3? — depends on whether 19 editorial angles identify WLI as essential.

**Q2**: LinkedIn Economic Graph access — realistic ROI for the brand vs cost?

**Q3**: Should Growth-at-Risk be exposed in SONAR dashboard explicitly, or remain internal?

**Q4**: For Portugal, how much INE data to fetch via scraping vs wait for official API (ETA unclear)?

**Q5**: AI capex wave — should SONAR track specifically (NVIDIA orders, hyperscaler capex reports) as separate high-signal series?

**Q6**: Should we implement regime-switching for stagflation detection (Bayesian approach), or keep rule-based triggers from Cap 16?

**Q7**: How to handle revisions — should ECS history show real-time vintage (vs. all-revised)?

---

## 16. Conclusão

Este plano operacionaliza o Manual do Ciclo Económico em pipeline implementável em 4-12 semanas conforme Tier. A filosofia é consistente com os planos de crédito e monetário: reutilização inteligente de connectors existentes, adições focadas onde o ciclo económico requer especificamente, e atenção particular ao nowcasting (que é diferencial do ciclo económico vs os outros três).

**Três princípios operacionais reafirmados**:

1. **Framework first, data second** — o manual define o que medir; este plano diz onde e como.
2. **Incremental — não big-bang** — Tier 1 publicable em 4 semanas; Tier 3 completo em 12 semanas.
3. **Honesty sobre limitations** — data quality, structural breaks, false positives explicitly tracked.

**Após implementação**, o SONAR-Economic torna-se operacional para publicação de columns e análise quantitativa. Junto com SONAR-Credit e SONAR-Monetary, forma 75% do framework SONAR completo. O quarto e último ciclo (financeiro) fecha a arquitetura.

---

**— fim do documento —**

*7365 Capital · SONAR Research · Abril 2026*
