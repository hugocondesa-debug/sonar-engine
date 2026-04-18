# E1 · Activity indicators

> Sub-índice do Ciclo Económico — capítulo 7 do manual (Manual_Ciclo_Economico_COMPLETO).

### 7.1 O que são coincident indicators
Coincident indicators medem atividade económica em tempo real — não antecipam nem reflectem o passado, mas descrevem o presente. São os componentes primários do Activity Indicator Score (AIS) introduzido no Cap 4.

A distinção entre coincident e leading indicators é crítica. Coincident captures "onde estamos agora". Leading captures "para onde vamos" (tratados no Cap 8). Lagging captures "onde estivemos" (úteis para confirmation, não tratados em profundidade porque oferecem pouco valor prospectivo).

> *O desafio central do E1 é que indicadores coincidentes têm lags de publicação variáveis. GDP é trimestral (1 mês de lag). Industrial production é mensal (2 semanas). Employment é mensal (primeiro dia do mês seguinte). Retail sales é mensal. Combinar estes diferentes timings é o trabalho do E1.*

### 7.2 GDP — o indicador central mas lento
Real Gross Domestic Product é the gold standard para measuring economic activity. Mas tem dois problemas operacionais significativos:

**Problema 1 — Publicação trimestral com lag**

- US BEA publishes advance Q estimate ~30 days após quarter end

- Second estimate 30 days later

- Final 30 days after that

- Plus annual revisions

- EA Q GDP: ~30 days para flash, ~45 days para second release

**Problema 2 — Heavy revisions**

Q4 2007 GDP initial release was positive. Final revision showed contraction. Similar for Q1 2008. Real-time cycle analysis can't fully trust advance estimates.

**Operational implications**

- GDP is backward-looking even when freshly published

- Requires complement with monthly indicators

- Nowcasting (Cap 19) bridges the lag

**Data sources**

- **FRED series:** GDPC1 (real GDP), GDPC96 (similar)

- **Eurostat:** GDP quarterly, seasonally adjusted

- **OECD:** Cross-country comparable quarterly

- **Monthly GDP (select countries):** Canada, UK, Germany publish monthly GDP estimates

### 7.3 GDP components — decomposição informativa
GDP headline é útil mas decomposição é mais informativa. Four-way NIPA decomposition:

*GDP = C + I + G + (X − M)*

**Consumer spending (C) — ~70% GDP em US**

- Personal Consumption Expenditures (PCE) — FRED \`PCEC96\`

- Three sub-categories: durables, nondurables, services

- Durables (autos, appliances) is most cyclical

- Services is sticky, employment-linked

**Investment (I) — highly cyclical**

- Gross Private Domestic Investment — FRED \`GPDIC1\`

- Components: residential, non-residential structures, equipment, IP products, inventories

- Residential investment particularly leading

- Inventory investment creates cycle amplification

**Government spending (G) — counter-cyclical traditionally**

- Government Consumption Expenditures — FRED \`GCEC1\`

- Infrastructure, defense, health spending

- Less cyclical than C and I

**Net exports (X-M) — external contribution**

- Tradable sector indicator

- Small direct share of GDP (~5% US, 10-30% others)

- But volatile contribution at the margin

- FRED: \`NETEXP\` (nominal), various real measures

**SONAR implementation**

AIS weights give GDP headline 25%, but sub-components are tracked separately as context. Decelerating Investment is stronger signal than decelerating G.

### 7.4 Industrial Production — the manufacturing cycle
IP measures output of mining, manufacturing, and utilities. Mensal, lag de ~2 semanas.

**Historical importance**

- Pre-1980s: manufacturing dominant share of GDP; IP was major cycle indicator

- Post-1980s: services grew; IP less dominant

- Still valuable: manufacturing é most cyclical sector

- NBER still uses IP as major indicator

**Sub-components**

- **Manufacturing:** ~75% of IP

- **Mining:** energy/resources

- **Utilities:** electricity, gas

- **Manufacturing further split by industry:** durables, nondurables, e dezenas de sub-sectors

**Data sources**

- **FRED:** \`INDPRO\` (US total), diversos sub-indices

- **Eurostat:** \`STS.M.I7.W.PROD.NS0010.4.000\` — EA industrial production

- **OECD:** International comparable

- **Banco de Portugal:** IP Portugal specifically

**Capacity utilization — complement**

- Measures how much of available industrial capacity is being used

- FRED: \`TCU\` (Total Capacity Utilization)

- Low capacity utilization signals slack; high signals tight conditions

- Useful companion to IP

### 7.5 Retail sales — consumer pulse
Retail and Food Services Sales measure consumer spending em goods (services are separate). Mensal, ~2 weeks lag.

**Components**

- Autos (very cyclical)

- Building materials

- Electronics

- Clothing

- General merchandise

- Grocery (very stable, not cyclical)

- Restaurants

**Key measures**

- **Headline retail sales:** all retailers

- **Retail sales ex-autos:** remove auto volatility

- **Control group:** excludes autos, gasoline, building materials, food services — more stable measure, used for GDP estimation

**Data sources**

- **FRED:** \`RSXFS\` (retail and food services), \`RSXFSN\` (non-seasonally adjusted), \`RRSFS\` (real retail sales)

- **Eurostat:** Retail trade monthly

**Complement — alternative data**

- Bank of America consumer spending (weekly)

- Chase Spending Pulse

- Visa SpendingPulse

- Much faster than official retail sales

### 7.6 Personal income — the income side
Real personal income less transfer payments is one of NBER's key indicators. Measures household earning capacity, excluding government transfers.

**Why exclude transfers**

Government transfers (Social Security, unemployment benefits) rise during recessions — masking underlying income decline. Excluding them provides cleaner measure of earned income.

**Data sources**

- **FRED:** \`W875RX1\` (real personal income ex transfers)

- Published monthly along with PCE release

- ~2 weeks lag

**Components**

- Wages and salaries (~60% of personal income)

- Proprietor's income

- Rental income

- Dividends and interest

- Other labor income

**SONAR role**

Less prominent in AIS weights (15%) but critical for NBER-style dating. When both GDP and real income ex-transfers are falling, recession signal is strong.

### 7.7 Employment — the labor dimension
Employment measures são crucial, treated em detail in Cap 9. Para E1 (coincident activity), focus em headline employment growth.

**US Non-farm payrolls**

- Monthly release first Friday of month

- Released with lag de 1 week

- Highly scrutinized, market-moving

- FRED: \`PAYEMS\`

**EA employment**

- Quarterly with ~45 days lag

- Less granular than US

- Eurostat: employment total

**UK employment**

- Monthly but with lag de ~6 weeks

- ONS labor market release

**Portugal employment**

- INE monthly employment estimates

- Labor force surveys quarterly

- Variable quality

**AIS weight**

Employment growth YoY weighted 20% in standard AIS — second highest after GDP. Its importance derives from reliability, coverage, and real-time availability.

### 7.8 Composite coincident indicators
Instead of looking at individual series, composites combine them for reduced noise.

**Conference Board Coincident Index**

- Index of 4 series: employment, industrial production, real income, retail sales

- Published monthly

- US only

- Used by NBER as one of the indicators

**Chicago Fed National Activity Index (CFNAI)**

- 85 indicators combined

- Monthly publication

- Z-score interpretation: 0 = trend growth, \>0 = above trend, \<-0.7 = recession zone

- FRED: \`CFNAI\`, \`CFNAIMA3\`

**ADS (Aruoba-Diebold-Scotti) Index**

- Daily business cycle index from Philly Fed

- Based on 6 indicators updated continuously

- URL: philadelphiafed.org/surveys-and-data/real-time-data-research/ads-index

- Negative = below average, positive = above average

**OECD Composite Leading Indicators**

- Despite "leading" in name, includes coincident elements

- Cross-country comparable

- Already mentioned Cap 5

> **Nota** *Para o SONAR, CFNAI é recommended como composite reference para US. Custom AIS permite country-specific weighting.*

### 7.9 GDI (Gross Domestic Income) — the alternative
GDP measures the value of goods and services produced. GDI measures income generated from production. Em teoria they should be equal; empirically they differ by statistical discrepancy.

**Why GDI matters**

- Same conceptual measure as GDP

- Sometimes diverges materially

- Some research suggests GDI is more accurate in real-time

- NBER considers GDI among key indicators

**Recent divergences**

- Q2 2022: GDP showed decline, GDI showed growth — contributed to NBER not dating "recession"

- Q1 2023: similar mixed signals

**Data sources**

- FRED: \`GDI\`, \`A261RX1Q020SBEA\` (real GDI)

- Published with GDP release

**SONAR implementation**

Track both GDP and GDI. Material divergence (\>1pp annualized) flags ambiguity. Useful signal in itself.

### 7.10 Cross-country coincident indicator coverage
**Cluster 1 (Large AEs)**

| **Country** | **Monthly GDP?**  | **Monthly employment?** | **Key composite**          |
|-------------|-------------------|-------------------------|----------------------------|
| US          | No                | Yes (NFP)               | CFNAI, Conference Board CI |
| UK          | Yes (monthly GDP) | Yes                     | UK composite               |
| Japan       | No                | Yes                     | Kabo index                 |
| Canada      | Yes               | Yes                     | Statistics Canada          |
| Australia   | No                | Yes (monthly)           | ABS composite              |

**Cluster 2 (EA periphery)**

- Portugal: quarterly GDP, monthly employment (INE)

- Spain: quarterly GDP, monthly employment (INE)

- Italy: quarterly GDP, monthly employment (ISTAT)

- Greece: quarterly GDP, monthly data quality variable

**Cluster 4 (Commodity exporters)**

- Russia: opacity post-2022

- Brazil: good monthly data (IBGE)

- Norway: good monthly data

- Chile: good monthly data

### 7.11 Data quality considerations
**Real-time vs revised**

Initial releases are often revised substantially. Alfred database (Archival FRED) preserves historical vintages — useful for real-time backtesting.

**Seasonal adjustment**

Most series are published both seasonally adjusted (SA) and non-seasonally adjusted. SA versions are standard. Issues:

- Seasonal factors can fail in unusual circumstances (Covid)

- US X-13 vs ECB Direct Filter Approach — methodology differences

- Recent seasonal pattern breaks may distort SA series temporarily

**Structural breaks**

- Methodology changes (GDP rebasing, industry reclassifications)

- Economic structure changes (services share growing)

- Policy regime changes

- SONAR uses rolling z-scores to partially adjust

### 7.12 SONAR E1 composite construction
> E1_score_t = weighted_average(
> \# Headline measures
> GDP_YoY_growth_t, \# weight 0.25
> IP_YoY_growth_t, \# weight 0.15
> Employment_YoY_growth_t, \# weight 0.20
> Retail_sales_YoY_real_t, \# weight 0.10
> Income_ex_transfers_YoY_t, \# weight 0.15
> PMI_composite_t, \# weight 0.15
> \# All z-scored over 10-year rolling window
> \# Aggregated to E1 score \[0-100\]
> )
> \# Output standardized to 0-100 scale
> \# 50 = neutral (trend growth)
> \# \>50 = above trend
> \# \<50 = below trend
> \# \<30 = recessionary zone
> \# \<20 = severe contraction

**Sub-classification**

- E1 \> 70: Strong Expansion

- E1 60-70: Expansion

- E1 45-60: Near-trend growth

- E1 30-45: Slowdown

- E1 20-30: Recession (mild)

- E1 \< 20: Recession (severe)

**Confidence interval**

Std deviation of AIS over last 12 months provides confidence measure. When individual components diverge widely (IP falling, employment rising), wider confidence band reflects ambiguity.

E1 score is foundation layer. Cap 8-10 build on top via leading indicators, labor depth, and sentiment.
