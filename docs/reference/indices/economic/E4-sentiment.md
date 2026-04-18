# E4 · Consumer e business sentiment

> Sub-índice do Ciclo Económico — capítulo 10 do manual (Manual_Ciclo_Economico_COMPLETO).

### 10.1 Por que sentiment matter
Sentiment indicators capture expectations — como consumers e firms pensam sobre economy. Matter porque:

35. **Expectations drive decisions.** Consumer planning major purchase checks confidence. Firm planning hiring checks business confidence.

36. **Sentiment often leads activity.** Confidence collapses precede spending declines; optimism precedes hiring.

37. **Sentiment is survey-based, timely.** Published rapidly, no accounting lag.

38. **Sentiment captures fears/hopes not in hard data.** Uncertainty, political concerns, expectations about future — all in sentiment surveys.

**Caveat important**

Sentiment is noisy. Political events, media coverage, specific concerns can shift sentiment without accompanying real economic change. Should not be sole input.

> *Para SONAR, sentiment é complement a hard data, not substitute. Valid corroborating signal, weak as sole signal.*

### 10.2 US consumer sentiment — two major surveys
**University of Michigan Consumer Sentiment Index**

- Monthly survey, ~500 households

- Two releases: preliminary (mid-month), final (end of month)

- Historical since 1946

- FRED: \`UMCSENT\`

- Components: Current conditions (40%), Expectations (60%)

**Conference Board Consumer Confidence**

- Monthly survey, ~3,000 households

- Larger sample than UMich

- Historical since 1967

- FRED: \`CSCICP03USM665S\`

- Components: Present situation, Future expectations

**Why two surveys**

- Different sample sizes

- Different question wording

- Sometimes diverge — UMich often more negative about inflation

- Using both gives triangulation

**Interpretation**

- UMich normal range: 80-100

- UMich \> 100: strong consumer confidence

- UMich \< 80: concerning

- UMich \< 70: recession-era levels (2008-09, 2022 briefly)

- Conference Board similar scale

**Post-Covid anomaly**

- UMich collapsed 2022 despite economy growing

- Inflation concerns dominated, not actual deterioration

- UMich sometimes diverges from reality - expressive of public mood

- Reminded economists to treat as one signal, not definitive

### 10.3 Consumer expectations — specifically
Within surveys, expectations component is more leading than current conditions.

**Michigan 5-year inflation expectations**

- Consumer expectations of inflation over next 5 years

- Fed watches closely as anchor check

- FRED: \`MICH\`

- Historical: 2.5-3%

- Post-Covid: temporarily spiked above 3% then settled

- Levels above 3.5% sustained concern

**Michigan 1-year inflation expectations**

- Short-term expectations

- More noisy but useful

- FRED: \`MICH1Y\`

**New York Fed Survey of Consumer Expectations (SCE)**

- Monthly, inflation expectations (1Y, 3Y, 5Y)

- Additional questions on spending, job confidence, home prices

- Complement to Michigan

**Role in Fed decisions**

Consumer inflation expectations are monitored by Fed to check anchoring. Stable expectations = Fed can be patient. Rising expectations = Fed must act to prevent de-anchoring.

### 10.4 Business sentiment — PMIs revisited
PMIs already covered Cap 8 as leading indicators. Here we focus on their sentiment dimension.

**Key sentiment aspects of PMIs**

- Forward-looking components (new orders, business expectations)

- Employment intentions

- Pricing intentions

- Inventory intentions

**ISM surveys (US)**

- ISM Manufacturing PMI — more cyclical

- ISM Services PMI — broader economic indicator

- Both provide sentiment dimensions alongside activity measures

- Market-moving on release

**NFIB Small Business Optimism**

- National Federation of Independent Business survey

- Monthly

- Reflects small business conditions

- Small firms often more cyclical than large

- FRED: \`SBIN\`

**Senior Loan Officer Opinion Survey (SLOOS)**

- Fed quarterly survey of bank lending standards

- Business credit conditions

- Consumer credit conditions

- Strong leading indicator when standards tighten

### 10.5 Economic Policy Uncertainty (EPU) index
Baker-Bloom-Davis (2016) developed EPU based on news text analysis + policy expiration + forecaster disagreement.

**Components**

- News articles mentioning economic policy uncertainty

- Tax code provisions set to expire

- Forecaster disagreement on key variables

**Historical data**

- Website: policyuncertainty.com

- Data 1985-present

- Updated monthly

- Also: Global EPU, country-specific EPU

**Interpretation**

- Normal range ~100

- Crisis periods: 200+

- Peak 2011 US debt ceiling, Covid 2020, Brexit

- High EPU → lower investment, higher precautionary savings

**Evidence**

Baker-Bloom-Davis document that EPU 1 std dev increase reduces GDP by 0.5-1% over 18 months. Robust relationship.

### 10.6 European sentiment surveys
**EC Economic Sentiment Indicator (ESI)**

- Monthly, published by European Commission

- Composite of 5 sub-indicators: industry, services, consumer, retail, construction

- All EA countries

- Long historical: 1985+

**ZEW Indicator of Economic Sentiment**

- Monthly survey of financial analysts (not consumers)

- Germany and EA

- Very forward-looking (6-month expectations)

- Market-moving in Germany

- FRED: \`EURONEXTGDPRGRW\`

**Ifo Business Climate Index**

- Monthly German business survey

- Widely watched, long history

- Two components: current situation, expectations

- Traditional German economic barometer

**Sentix Economic Index**

- Monthly investor sentiment

- EA and individual countries

- Forward-looking

**INSEE Monthly Business Climate (France)**

- French version of Ifo-equivalent

- Multiple sectors

### 10.7 Asia-Pacific sentiment
**Japan Tankan**

- Bank of Japan's quarterly business survey

- Very detailed, historically important

- Large manufacturers business conditions is key number

- Currently released March, June, September, December

**China PMIs**

- Caixin (private) and NBS (official)

- Manufacturing and Services

- Often diverge — different samples (Caixin smaller firms, NBS large state-owned)

**Korean surveys**

- Bank of Korea Business Survey Index

- Korea Development Institute Economic Survey

### 10.8 Credit sentiment and financial sentiment
**VIX and market-based sentiment**

- VIX: implied volatility of S&P 500 options

- High VIX = fear; low VIX = complacency

- FRED: \`VIXCLS\`

- Weekly/daily available

**AAII Investor Sentiment Survey**

- American Association of Individual Investors

- Weekly survey of bullish/bearish/neutral

- Useful contrarian indicator at extremes

**Credit sentiment via SLOOS**

- Already mentioned

- Provides perspective on credit conditions from lenders

- Combines with spreads for fuller picture

### 10.9 Sentiment e recession prediction
Sentiment alone is weak recession predictor but adds value in combination.

**Empirical findings**

- Sentiment collapse alone: ~40% recession within 12 months

- Sentiment collapse + yield curve inversion: ~75%

- Sentiment collapse + rising unemployment claims: ~85%

- Sentiment + other indicators: highly predictive

**False signals**

- Political events can collapse sentiment without recession

- Media coverage amplifies

- 2011 debt ceiling: sentiment crashed, no recession

- 2013 government shutdown: similar

> *Sentiment é strongest when corroborated by multiple other signals. Weakest as standalone signal. Treat as part of ensemble.*

### 10.10 SONAR E4 composite construction
> E4_score_t = weighted_combination(
> \# US consumer
> umich_sentiment_12M_change_z, \# weight 0.10
> conference_board_confidence_12M_z, \# weight 0.10
> \# Expectations
> umich_5Y_inflation_exp_z, \# weight 0.10 (inverted - high = bad)
> \# US business
> ism_manufacturing_z, \# weight 0.10
> ism_services_z, \# weight 0.10
> nfib_small_business_z, \# weight 0.05
> \# US uncertainty
> EPU_index_inverted_z, \# weight 0.05
> \# Europe
> EC_ESI_z, \# weight 0.10
> ZEW_expectations_z, \# weight 0.10
> ifo_business_climate_z, \# weight 0.05
> \# Financial sentiment
> VIX_level_inverted_z, \# weight 0.05
> \# Japan
> tankan_large_manufacturers_z, \# weight 0.05
> \# Credit
> sloos_standards_inverted_z, \# weight 0.05
> \# All z-scored, combined to 0-100
> )
> \# Interpretation:
> \# \>70: Strong positive sentiment across board
> \# 55-70: Generally positive sentiment
> \# 45-55: Neutral sentiment
> \# 30-45: Concerning sentiment deterioration
> \# \<30: Widespread pessimism (recession territory)

**Regional breakdown**

For country-specific analysis, appropriate regional indicators weighted more heavily. PT would emphasize EU ESI.

### 10.11 E1-E4 integration — the Economic Cycle Score
> ECS_t = weighted_average(
> E1_activity_score_t, \# weight 0.35
> E2_leading_score_t, \# weight 0.25
> E3_labor_score_t, \# weight 0.25
> E4_sentiment_score_t \# weight 0.15
> )
> \# ECS ∈ \[0, 100\]

**Why these weights**

- E1 weighted highest — coincident measures of actual economy

- E2 and E3 weighted equally — both critical for forward-looking

- E4 weighted lowest — useful but noisier, ensemble role

**Derivation**

Weights calibrated against historical hit rate em identifying NBER peaks/troughs with 3-6M lead time. Similar methodology to CCCS e MSC.

**Phase classification from ECS**

- ECS \> 70: Strong Expansion

- ECS 55-70: Expansion

- ECS 45-55: Near-trend

- ECS 30-45: Slowdown

- ECS 20-30: Recession (mild)

- ECS \< 20: Recession (severe)

**Cross-validation**

- Compare SONAR ECS-based dating to NBER dating 1960-present

- Target: 90%+ agreement on phase classification at month-level

- When disagreements occur, examine component contributions

A Parte IV examina mecanismos de transmissão que o E1-E4 captures — multiplicador fiscal, labor dynamics, wealth effects, business investment. Complement de medição com understanding.

**Encerramento da Parte III**

Parte III entregou o módulo de medição operacional do SONAR-Economic. Quatro camadas:

- **Capítulo 7 — E1 Activity indicators.** GDP e seus components (C+I+G+NX), Industrial Production, Retail Sales (com control group), Personal Income ex-transfers, Employment. Composite coincident indicators (CFNAI, Conference Board CI, ADS Index). GDI como alternative a GDP. Cross-country data quality. AIS composite com pesos 25/20/15/15/15/10.

- **Capítulo 8 — E2 Leading indicators.** Yield curve (10Y-3M Engstrom-Sharpe, 10Y-2Y), credit spreads (HY OAS, GZ), PMIs (new orders components), Conference Board LEI (10 components), OECD CLI, ECRI WLI, building permits, new orders, equity/volatility/commodities, initial claims. E2 composite com 8 inputs.

- **Capítulo 9 — E3 Labor market depth.** Two surveys (Establishment + Household), NFP details, unemployment rate (U-3 + alternatives), Sahm Rule destacada, employment-population ratio, LFPR, wage growth (AHE + ECI + Atlanta Fed tracker), JOLTS (openings, quits, hires, layoffs), Beveridge curve, initial/continuing claims, productivity. E3 composite com 10 inputs.

- **Capítulo 10 — E4 Sentiment.** US consumer (UMich + Conference Board), inflation expectations (Michigan 5Y, NY Fed SCE), US business (ISM, NFIB, SLOOS), EPU uncertainty index, European (EC ESI, ZEW, Ifo, Sentix, INSEE), Asia-Pacific (Tankan, China PMIs), credit/financial sentiment (VIX, AAII). E4 composite com 13 inputs.

- **Integração: ECS = 0.35·E1 + 0.25·E2 + 0.25·E3 + 0.15·E4.** Score \[0-100\] que mapeia para 6 fases. Calibração contra NBER historical.

**Material editorial potencial da Parte III**

39. "A Sahm Rule — como Claudia Sahm nos deu o sinal mais fiável de recessão." Biográfico-técnico.

40. "Porque o PMI ainda importa em 2026 — e o que dizer das divergências entre Caixin e NBS." China-specific.

41. "JOLTS é o indicador que a Fed lê antes de decidir — o que diz em 2026." Policy-relevant.

42. "O que a curva de rendimentos diz em 2026 — inverted 650 dias sem recessão." Current anomaly.

***A Parte IV — Transmissão e amplificação (capítulos 11-14)** examina como shocks propagam-se através da economia. Cap 11 multiplicador fiscal (debates empíricos e Blanchard-Leigh reviewed). Cap 12 labor market dynamics (Beveridge revisitado, hysteresis, matching function). Cap 13 consumer wealth effect (Permanent Income Hypothesis, credit constraints, MPC distribution). Cap 14 business investment accelerator (complementar ao financial accelerator do manual credit).*

# PARTE IV
**Transmissão e amplificação**

*Multiplicador fiscal, labor dynamics, wealth effects, investment accelerator*

**Capítulos nesta parte**

**Cap. 11 ·** Multiplicador fiscal e automatic stabilizers

**Cap. 12 ·** Labor market dynamics — matching, hysteresis, Beveridge

**Cap. 13 ·** Consumer wealth effect e heterogeneous MPC

**Cap. 14 ·** Business investment accelerator
