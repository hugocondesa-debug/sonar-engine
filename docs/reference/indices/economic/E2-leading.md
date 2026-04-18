# E2 · Leading indicators

> Sub-índice do Ciclo Económico — capítulo 8 do manual (Manual_Ciclo_Economico_COMPLETO).

### 8.1 O objetivo dos leading indicators
Leading indicators antecipam turns no ciclo económico. Idealmente, signalam changes em activity 3-12 months before activity itself changes. São fundamentais para cycle analysis porque coincident indicators são, by definition, late.

A literatura identifica várias categorias de leading indicators, each with different lead times and reliability:

- **Financial (fastest to respond):** yield curve, credit spreads, equity valuations

- **Survey-based (forward-looking):** PMIs, business confidence, consumer confidence

- **Construction (interest-sensitive):** building permits, housing starts

- **Orders (demand signal):** new orders, unfilled orders

- **Composite indices:** Conference Board LEI, OECD CLI, ECRI WLI

> *Nenhum indicador leading é perfeito. Cada tem false positives e negatives. SONAR combina múltiplos para robustness.*

### 8.2 Yield curve — the king of leading indicators
Yield curve inversion (short rate \> long rate) é o mais célebre leading indicator de recession. Funciona com extraordinary reliability.

**Track record**

- Every US recession since 1960 precedida por yield curve inversion

- Average lead time: 12-18 months from inversion to recession

- False positives rare (arguably 1966 inversion sem recession)

- False negatives: none documented

**Key measures**

- **10Y - 3M Treasury spread:** NY Fed's preferred measure for recession probability model. FRED: \`T10Y3M\`

- **10Y - 2Y Treasury spread:** more traded, market focus. FRED: \`T10Y2Y\`

- **10Y - 5Y:** useful secondary

- **Near-term forward spread (NFS):** 6-quarter ahead forward minus current 3M — Engstrom-Sharpe (2018) arguedly superior predictor

**Interpretation**

- Curve steep (10Y-3M \> 150bps): Early expansion, BC accommodative

- Curve normal (50-150bps): Middle expansion, BC neutral

- Curve flat (0-50bps): Late expansion, BC tightening

- Curve inverted (\< 0bps): Recession warning, BC in late tightening

- Curve steepening from inversion: Often recession already started

**Recent example 2022-23**

- May 2022: 10Y-2Y inverted briefly

- July 2022: 10Y-2Y sustained inversion

- October 2022: 10Y-3M inverted

- 2023: deepest inversion since 1980s

- 2024-25: steepening (normalizing) without formal NBER recession dating

- Framework challenged — longest inversion ever without subsequent recession

> *Yield curve remains high-value indicator but 2022-25 period raises questions about whether structural changes (Fed balance sheet size, risk-free rate composition) altered its significance.*

### 8.3 Credit spreads — financial stress proxy
Credit spreads (corporate yields over Treasuries) capture market assessment of corporate credit risk. Leading indicator of recession because credit market stress precedes economic stress.

**Key measures**

- **BAA - 10Y Treasury spread:** traditional measure. FRED: \`BAA10Y\`

- **High Yield OAS:** ICE BofA US High Yield Option-Adjusted Spread. FRED: \`BAMLH0A0HYM2\`

- **Investment Grade OAS:** FRED: \`BAMLC0A0CM\`

- **Excess bond premium (Gilchrist-Zakrajšek):** purged of default risk component, more informative

**Interpretation**

- Spreads narrow: benign conditions, investor confidence high

- Spreads widening: warning signal

- Spreads spike: crisis mode

- HY OAS \> 600bps: recession territory

- HY OAS \> 1000bps: severe distress

**Lead time**

Shorter than yield curve — typically 3-6 months from spread widening to economic impact. Useful complement.

### 8.4 Purchasing Managers Indices (PMIs)
PMIs são survey-based indicators of current business conditions. Despite being current-conditions surveys, they have strong leading properties because firms respond to current pipelines that precede final sales.

**Main PMI providers**

- **S&P Global (formerly IHS Markit):** Most widely used, covers 40+ countries. Monthly, first week

- **ISM (US only):** Institute for Supply Management. Longest US history

- **China Caixin (also NBS official):** Private alternative to Chinese official PMI

**Manufacturing PMI**

Most commonly cited. 50 is threshold between expansion and contraction.

- Sub-components: new orders, production, employment, supplier deliveries, inventories

- New orders is most leading — reflects future production

- Average level matters: 45-50 = mild contraction; \<45 = significant contraction; 50-55 = modest expansion

**Services PMI**

Now more important than manufacturing PMI given services dominance. US ISM services PMI, EA services PMI, UK services PMI all tracked closely.

**Composite PMI**

Weighted combination of manufacturing and services. Most relevant for full economy signal.

**Country coverage**

- US: ISM Manufacturing, ISM Services, S&P Global flash and final

- EA: S&P Global Manufacturing, Services, Composite

- UK: S&P Global UK PMIs

- Japan: Jibun Bank PMIs (S&P Global)

- China: Caixin and official NBS PMIs

- Individual EA countries: Germany, France, Italy, Spain PMIs

- Portugal: not published by major providers

**Free access**

- Headline values publicly available on release day

- Detailed component data typically paid

- Trading Economics aggregates many

- FRED has some historical series

### 8.5 Conference Board Leading Economic Index (LEI)
Conference Board LEI é a composite de 10 leading indicators, published monthly. US only mas replicated internationally.

**Components**

- Average weekly hours, manufacturing

- Average weekly initial claims for unemployment insurance

- Manufacturers' new orders, consumer goods and materials

- ISM New Orders Index

- Manufacturers' new orders, non-defense capital goods excluding aircraft

- Building permits, new private housing units

- S&P 500 Index of stock prices

- Leading Credit Index

- Interest rate spread (10Y Treasury - FFR)

- Average consumer expectations for business conditions

**Interpretation**

- 6-month growth rate: if negative for 3+ consecutive months, strong recession signal

- Diffusion index: % of components increasing. \<50% warning

- Recession calls based on LEI often precede NBER dating by 3-6 months

**Track record**

Leading properties well-documented. False positive ratio ~20% across history. Reliable as complement to yield curve.

**Data sources**

- Conference Board: conference-board.org

- Historical FRED: \`USSLIND\`

- Free headline numbers; detailed subscription required

### 8.6 OECD Composite Leading Indicators (cross-country)
Already mentioned Cap 5 for cycle dating. Also functions as leading indicator.

**Methodology**

- Country-specific composition

- 6-8 leading series per country

- Bry-Boschan algorithm for turning point detection

- Published monthly, approximately 2-month lag

**Countries covered**

- 37 OECD members

- Plus selected non-members (China, India, Russia, Brazil)

- Aggregates: OECD total, Euro Area, G7, major 5 Asia

**Signal interpretation**

- CLI above trend and rising: expansion accelerating

- CLI above trend but falling: slowdown approaching

- CLI below trend and falling: contraction deepening

- CLI below trend but rising: recovery starting

**SONAR role**

Primary cross-country leading indicator. Enables comparable analysis across the 6 clusters.

### 8.7 ECRI Weekly Leading Index (WLI)
Economic Cycle Research Institute publishes WLI weekly. Proprietary but summary values public.

**Methodology**

- Weekly frequency (unusual for macro)

- Composite of multiple leading series

- Exact composition proprietary

- Growth rate published weekly

**Track record**

- Historically reliable leading indicator

- False positive 2011 (predicted recession that didn't materialize)

- Correct on major turns (2007 early, 2020 early)

**Access**

- ECRI website publishes headline WLI values

- Detailed access requires subscription

- Reports commercially available

### 8.8 Building permits e housing starts — the construction leading indicator
Construction is interest-rate-sensitive and plans-ahead, making permits strongly leading.

**Why leading**

- Permits precede starts by 1-2 months

- Starts precede completions by 6-12 months

- Plans reflect expected future demand

- Interest rate changes affect permits within weeks

**Data sources**

- **FRED:** \`PERMIT\` (total permits), \`HOUST\` (housing starts)

- **Census Bureau:** monthly release

- **Eurostat:** building permits quarterly for EA

**Interpretation**

- Permits YoY \> 10%: expanding housing cycle

- Permits YoY negative: housing slowing

- Permits YoY \< -20%: severe housing contraction, recession signal

- 2022-23 example: permits YoY -25% preceded visible slowdown

### 8.9 New orders — demand signal
Manufacturers' new orders reveal demand pipeline before it translates to production.

**Measures**

- **Durable goods orders:** volatile but important. FRED: \`DGORDER\`

- **Core capital goods orders (ex-defense ex-aircraft):** proxy for business investment intent

- **Manufacturing ISM new orders:** survey-based, included in LEI

**Interpretation**

- Orders rising: current production may lag but will follow

- Orders falling: production will follow within 2-3 months

- Core capex orders: best single predictor of business investment

### 8.10 Financial indicators — equity, volatility, commodities
**Equity market**

- S&P 500 is component of Conference Board LEI

- Sustained decline (\>10% over 3 months) = potential recession signal

- Deep bear market (\>20% decline) historically precedes or coincides with recession

- But: many false signals — market declines often don't lead to recession (1987, 1998, 2022 first half)

**VIX volatility**

- VIX \> 25 sustained: market stress

- VIX \> 30: significant stress

- VIX \> 40: crisis mode

- Useful as risk sentiment indicator, not pure leading indicator

**Commodity prices**

- Copper ("Dr. Copper"): traditionally leading of industrial activity

- Oil: leading for industrial economies (supply shocks)

- Commodities broadly: CRB Index, Bloomberg Commodity Index

- Role diminished somewhat in services-dominant economies

**Dollar index (DXY)**

- Strong dollar often coincides with Fed tightening

- Dollar surge historically stress signal for EMs

- Less useful as domestic leading indicator

### 8.11 Jobless claims — weekly labor market pulse
Initial jobless claims são published weekly — one of few truly weekly economic indicators.

**Properties**

- Fast release (weekly, Thursday)

- Fresh data (1-week lag)

- Leading indicator of unemployment

- FRED: \`ICSA\` (seasonally adjusted)

**Interpretation**

- Normal range US: ~200-250K per week

- Above 300K: warning signal

- Above 400K: consistent with recession

- During Covid April 2020: peaked 6.6M weekly (extreme outlier)

**SONAR use**

Weekly pulse check for labor market direction. Leads unemployment rate by 2-4 weeks typically. Included in Conference Board LEI.

### 8.12 SONAR E2 composite construction
> E2_score_t = weighted_combination(
> \# Financial leading
> yield_curve_10Y_3M_z, \# weight 0.25
> credit_spread_HY_z, \# weight 0.10
> \# Survey-based
> PMI_manufacturing_new_orders_z, \# weight 0.15
> PMI_composite_z, \# weight 0.15
> \# Construction
> building_permits_YoY_z, \# weight 0.10
> \# Orders
> core_capex_orders_YoY_z, \# weight 0.05
> \# Composite
> LEI_6M_growth_z, \# weight 0.10
> OECD_CLI_6M_growth_z, \# weight 0.10
> \# All z-scored, combined to 0-100
> )
> \# E2 interpretation:
> \# \>70: Strong growth ahead
> \# 55-70: Modest growth ahead
> \# 45-55: Mixed/neutral signals
> \# 30-45: Slowdown signaled
> \# \<30: Recession warning

**Probability mapping**

Combined with E1 state, leading indicators inform transition probabilities:

- E1 Expansion + E2 \<30: 40% probability of Slowdown within 6M

- E1 Expansion + E2 \<20: 60% probability of Slowdown within 6M

- E1 Slowdown + E2 \<30: 50% probability of Recession within 6M

- E1 Recession + E2 \>45: 40% probability of Recovery within 3M

These probabilities are backtested against historical base rates. Used as inputs to probabilistic cycle classification.
