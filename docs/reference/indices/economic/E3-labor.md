# E3 · Labor market depth

> Sub-índice do Ciclo Económico — capítulo 9 do manual (Manual_Ciclo_Economico_COMPLETO).

### 9.1 Porquê labor deserve layer dedicada
Labor market foi introduzida no E1 via non-farm payrolls growth. Mas labor market contém multi-dimensional information não captured em single metric. Dedicamos layer completo (E3) porque:

31. **Labor market é coincident e leading simultaneamente.** NFP employment é coincident mas initial claims, hours worked, temporary help are leading.

32. **Multiple dimensions captured.** Unemployment rate, employment-to-population ratio, labor force participation, wage growth, job openings, quits, hires — each tells different story.

33. **Labor has policy relevance.** Fed dual mandate makes labor data critical for monetary policy — and therefore for economic cycle dynamics.

34. **Recession signals are often labor-related.** Sahm Rule (unemployment 3M MA \> 12M min + 0.5pp) is highly reliable recession signal.

> *Labor market data has lower revision volatility than GDP, quicker publication, and more granular coverage. Makes it core to real-time cycle analysis.*

### 9.2 The two main labor surveys (US context)
US labor data comes from two distinct surveys, often giving slightly different answers.

**Establishment Survey (Current Employment Statistics)**

- Surveys ~145,000 businesses and government agencies

- Provides nonfarm payrolls, earnings, hours

- Published first Friday of month

- Seasonally adjusted series are market standard

- FRED: \`PAYEMS\`, \`AHETPI\`, \`AWHAE\`

**Household Survey (Current Population Survey)**

- Surveys ~60,000 households

- Provides unemployment rate, employment, labor force participation

- Published same day as establishment survey

- Includes self-employed

- FRED: \`UNRATE\`, \`CIVPART\`, \`EMRATIO\`

**Sources of divergence**

- Self-employed growth (captured in household, not establishment)

- Multiple job holders (counted once in household, twice in establishment)

- Sampling differences

- Response rates

**Which to use when**

- For aggregate employment growth: Establishment survey (larger sample, more accurate)

- For unemployment rate: Household survey (only source)

- For labor force participation: Household survey

- When surveys diverge materially: uncertainty signal, track both

### 9.3 Non-farm payrolls — the headline
NFP é the single most-watched US economic indicator. Market-moving, closely analyzed.

**Key sub-categories**

- **Private payrolls:** excludes government, cleaner measure of private economy

- **Manufacturing:** cyclical sector, leading properties

- **Construction:** interest-rate sensitive

- **Services:** employment-dominant, less cyclical than goods-producing

- **Temporary help:** leading indicator — firms cut temps first, hire temps first in recovery

**Interpretation**

- Normal monthly NFP growth (US): 150-250K

- Above trend: 250K+ (tight labor market)

- Below trend: 100K or below (slowing)

- Negative: contractionary (recession signal)

- Breakeven (keep up with population): ~90-120K monthly

**Revisions**

NFP revisions can be substantial. Initial month 1 release revised in month 2 and month 3. QCEW benchmark revisions annual can reveal major shifts post-hoc.

### 9.4 Unemployment rate — the public facing number
Unemployment rate is the single most-familiar economic number for the public. But technical definition matters.

**Definition**

U-3 (standard): unemployed divided by labor force. Labor force = employed + actively seeking work.

**Alternative measures**

- **U-6:** includes marginally attached + part-time for economic reasons. More comprehensive

- **U-1:** long-term unemployed (\>15 weeks)

- **U-5:** U-3 + discouraged workers

**Interpretation**

- US NAIRU estimate pós-Covid: ~4.0-4.5%

- Below NAIRU: tight labor market, wage pressures building

- Above NAIRU: slack, disinflationary

- Trend in unemployment rate matters more than level

**Sahm Rule**

Claudia Sahm (2019) showed that 3-month moving average of unemployment rate rising 0.5pp above 12-month minimum is highly reliable recession signal.

*Sahm = (UR_3MA_t) − min(UR_3MA\_{t-11 to t}) \>= 0.5*

- Triggered in every US recession since 1970

- No false positives in that period

- Advantage: near real-time (1-month lag)

- FRED: \`SAHMCURRENT\`

> *Sahm Rule é among most important labor market-based recession indicators. Should be closely tracked no SONAR.*

### 9.5 Employment-to-population ratio
Alternative to unemployment rate. Less sensitive to labor force participation changes.

**Definition**

Employed persons divided by total population (16+ in US).

**Advantages**

- Not affected by whether discouraged workers give up job search

- Direct measure of how much of population is employed

- Less distorted by retirement demographic trends (over time)

**Recent data**

- US pre-Covid peak: ~61%

- Covid low: 51.3% (April 2020)

- 2024-25 recovery: ~60%

- FRED: \`EMRATIO\`

**Interpretation**

- Rising: more people finding work

- Falling: people dropping out or not getting hired

- Prime age (25-54): often more informative, removes demographic noise

### 9.6 Labor force participation
LFPR mede pessoas na labor force (working or actively looking) como share of population. Captures labor supply.

**Trends**

- US LFPR: long-term decline (demographic aging)

- Covid drop was significant (early retirement wave)

- Partial recovery since 2022

- Prime-age LFPR (25-54) more cyclical

**Cyclical vs structural**

- Cyclical: recession reduces LFPR, recovery increases it

- Structural: demographic trends, education, retirement patterns

- Separating these is challenging

**Data sources**

- FRED: \`CIVPART\` (total), \`LNS11300060\` (prime-age)

- Published monthly with Household Survey

### 9.7 Wage growth — the inflation link
Wage growth has dual role: indicator of labor market tightness AND driver of services inflation.

**Key measures**

- **Average Hourly Earnings (AHE):** monthly, from Establishment Survey. FRED: \`AHETPI\` (production workers), \`CES0500000003\` (all employees)

- **Employment Cost Index (ECI):** quarterly, measures total compensation. Preferred by Fed. FRED: \`ECIWAG\`

- **Atlanta Fed Wage Growth Tracker:** median wage growth for continuously employed. Controls for composition

- **Compensation per hour:** from productivity releases, quarterly

**Interpretation**

- Wage growth below 2.5%: disinflationary labor market

- 2.5-3.5%: moderate

- 3.5-4.5%: firm labor market

- 4.5%+: tight labor market, potential inflation pressure

- Real wage growth (nominal - inflation): productivity link

**Phillips Curve context**

Traditional Phillips Curve: tight labor market → wage growth → inflation. Post-2000 relationship weakened but reasserted 2021-22. Wage growth signals tight labor market.

### 9.8 JOLTS data — vacancies and turnover
Job Openings and Labor Turnover Survey (JOLTS) provides monthly data on job openings, hires, quits, layoffs. Published 1-month lag.

**Key measures**

- **Job openings:** unfilled positions. FRED: \`JTSJOL\`

- **Hires:** new employment starts

- **Quits:** voluntary separations. Leading indicator — people only quit when confident about finding another job. FRED: \`JTSQUL\`

- **Layoffs:** involuntary separations

**Job openings to unemployed ratio**

- 1:1 = balanced

- 2:1 = tight labor market (2021-22 reached this)

- \<0.5:1 = significant slack (2009 reached 0.2:1)

- 2024-25: ~1.0-1.2:1 (normalizing from tight)

**Quits rate**

% of employed who quit each month. When people feel confident, they quit. Leading indicator of wage pressure and labor market tightness.

- Normal: 2.0-2.5%

- Tight labor market: \>3.0% (2021-22)

- Weak labor market: \<2.0% (2009)

### 9.9 Beveridge curve — structural view
Beveridge curve plots unemployment rate vs job vacancies. Normally negative relationship — high unemployment + low vacancies, vice versa.

**Normal position**

Economy moves along the curve — recessions shift up-right (high unemployment, low vacancies), recovery shifts down-left.

**Outward shift (problematic)**

Curve shifts outward = more vacancies AND unemployment simultaneously. Signals structural mismatch — skills gap, geographic mismatch, etc. Typically means NAIRU has risen.

**Post-Covid era**

- Covid shifted curve outward significantly

- Led to high vacancies and elevated unemployment simultaneously 2021-22

- Debate: structural change in labor market or temporary?

- Partially resolved by 2024-25 — curve shifting back inward

**SONAR use**

Monitor Beveridge curve position. Outward shift = NAIRU estimate needs revision upward. Inward shift = labor market healing.

### 9.10 Initial and continuing claims
Weekly unemployment insurance claims — fastest labor market signal.

**Initial claims**

- New unemployment applications each week

- Leading indicator

- FRED: \`ICSA\` (seasonally adjusted)

- Normal range: 200-250K

- Rising above 300K: warning

**Continuing claims**

- People currently on unemployment benefits

- Captures duration of unemployment

- FRED: \`CCSA\`

- Lags initial claims by 1 week

**Real-time signal**

Claims are released every Thursday, high-frequency. First to show labor market stress. Particularly valuable.

### 9.11 Productivity — the long-run anchor
Labor productivity = output per hour worked. Long-run driver of potential growth.

**Measurement**

- BLS quarterly release of non-farm productivity

- Calculation: GDP / hours worked

- Volatile quarterly, more meaningful over time

- FRED: \`OPHNFB\` (output per hour)

**Trend**

- Long-term US: ~1.5-2.0% productivity growth

- Post-Covid possibly acceleration (AI? permanent remote work gains?)

- Productivity growth = potential GDP growth (long-run)

**Cyclical behavior**

- Productivity typically declines early in recessions

- Recovers strongly in early expansion

- Labor hoarding affects measurement

**SONAR use**

Productivity is less for real-time cycle dating. More for setting potential growth assumption used in output gap calculations.

### 9.12 Cross-country labor market data
**EA data**

- Eurostat publishes monthly unemployment

- Quarterly employment

- Quarterly wage growth (labor costs)

- Less granular than US JOLTS

**UK**

- ONS Labor Market Statistics

- Monthly, comparable to US data

- Wage growth important indicator

**Japan**

- MIC monthly Labor Force Survey

- Lower-quality real-time than US data

- Wage growth trending positive finally (2024-25 shunto wage rounds strong)

**Portugal**

- INE quarterly Labor Force Survey

- Monthly unemployment estimates

- IEFP unemployment registration data

### 9.13 SONAR E3 composite construction
> E3_score_t = weighted_combination(
> \# Headline measures
> unemployment_rate_12M_change_z, \# weight 0.15
> sahm_rule_trigger, \# binary +1/-1, weight 0.20
> \# Broader measures
> employment_population_ratio_12M_z, \# weight 0.10
> prime_age_LFPR_12M_change_z, \# weight 0.05
> \# Wages
> ECI_YoY_growth_z, \# weight 0.10
> Atlanta_Fed_wage_tracker_YoY_z, \# weight 0.05
> \# JOLTS
> openings_unemployed_ratio_z, \# weight 0.10
> quits_rate_z, \# weight 0.05
> \# Leading
> initial_claims_4wk_avg_z, \# weight 0.10
> temp_help_employment_YoY_z, \# weight 0.10
> \# All z-scored, combined to 0-100
> )
> \# Interpretation:
> \# \>70: Robust labor market
> \# 55-70: Healthy labor market
> \# 45-55: Neutral
> \# 30-45: Weakening labor market
> \# \<30: Deteriorating rapidly (recession mode)

**Special flags**

- Sahm Rule triggered: elevate recession probability significantly

- Beveridge curve outward shift: note structural issue, adjust NAIRU

- Wage growth \> 4%: potential inflation signal for monetary policy interaction
