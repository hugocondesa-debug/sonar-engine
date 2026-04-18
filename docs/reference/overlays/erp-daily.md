# ERP Daily

> Overlay L2 — Parte III · ERP diária computada do Manual dos Sub-Modelos Quantitativos.

## Capítulo 7 · Teoria do implied Equity Risk Premium
### 7.1 O que é ERP — quatro definições distintas
Equity Risk Premium (ERP) é conceito fundamental em finanças, mas tem múltiplas definições operacionais que os analistas frequentemente confundem. SONAR adopta definições explícitas e documenta qual computa.

**Definição 1 — Historical ERP (realized)**

Média aritmética ou geométrica do excess return de equities sobre risk-free rate em período histórico longo.

*ERP_historical = mean(R_equity − R_risk_free) over N years*

- Vantagem: simples, observável directly

- Disadvantage: depende do período escolhido (1926+ nos EUA dá ~5-7%; 1870+ dá ~4-5%)

- Disadvantage: backward-looking, não forward-looking

- Disadvantage: survivorship bias (US exceptional historically)

**Definição 2 — Expected ERP (forward-looking)**

Expectativa ex-ante do excess return futuro de equities sobre risk-free.

- É o que verdadeiramente importa para asset allocation

- Não observável directly — tem que ser inferido

- Pode ser inferred via (a) historical extrapolation, (b) implied from prices, (c) surveys

**Definição 3 — Required ERP (ex ante compensation)**

O excess return que investidores exigem para manter equities. Framework CAPM assumes this equals expected.

- Em equilibrium, required = expected

- Em disequilibrium, prices adjust até required = expected

**Definição 4 — Implied ERP (market-derived)**

ERP implícito nos current prices assuming standard pricing model (DDM, DCF).

*P = Σ (CF_t / (1 + r_f + ERP)^t)*

Solve for ERP given P (observed price), CF_t (projected cash flows), r_f (observed risk-free).

- Forward-looking (uses current prices)

- Market-based (aggregates collective investor views)

- Updates daily (prices update daily)

- SONAR choice — this is what we compute

> *Damodaran publicou desde 2000 a sua implied ERP methodology. SONAR não reinventa — adopta a framework, mas computa diariamente em vez de mensalmente. A diferença não é metodológica; é operacional.*

### 7.2 Damodaran's implied ERP framework
Aswath Damodaran (NYU Stern) popularizou este approach. Publica mensalmente para S&P 500. Método base:

**Gordon constant growth model simplified**

*P = Dividends_next_year / (r − g)*

Onde r é required return, g é perpetual growth rate. Rearranging:

*r = D/P + g*

Isto é, required return = dividend yield + growth rate. Se r = risk_free + ERP:

*ERP = D/P + g − risk_free*

**Limitations Gordon model**

- Assumes constant growth rate forever — unrealistic

- Only captures dividends, not buybacks

- Needs long-run growth assumption

- Useful for orientation but not precise

**DCF-based implied ERP (Damodaran main method)**

Damodaran's full method:

38. Take current S&P 500 level as present value

39. Project dividends + buybacks 5 years forward using analyst estimates

40. Apply terminal growth = current 10Y Treasury yield (proxy for perpetual growth)

41. Solve for discount rate that equates PV to current level

42. ERP = discount rate − risk-free rate

**Formulaic**

> \# Solve for r in:
> P_0 = sum(CF_t / (1+r)^t for t in 1..5) + Terminal_Value / (1+r)^5
> \# Where:
> \# P_0 = S&P 500 current level
> \# CF_t = projected dividends + buybacks in year t
> \# Terminal_Value = CF_5 \* (1 + g) / (r - g)
> \# g = current risk-free rate (perpetual growth)
> \# r = implied required return (solve for this)
> \# Then:
> \# ERP = r - risk_free_10y

### 7.3 Components of Damodaran's framework
**Input 1 — Current index level**

- S&P 500 close (daily)

- Via FRED \`SP500\` ou Yahoo Finance

- No contention

**Input 2 — Cash flows (dividends + buybacks)**

- Most contested input

- Dividend yield: historical ~2% S&P 500 recent

- Buyback yield: historical 2-4% S&P 500 recent

- Total payout yield (D+B)/P: 4-6% typical

- Source: S&P DJI data, Fed Z.1 Flow of Funds, Bloomberg

**Input 3 — Growth projections**

- Short-term (1-5 years): bottom-up analyst estimates (FactSet, IBES)

- Long-term (perpetual): tied to risk-free rate (per Damodaran convention)

- Alternative long-term: GDP growth, or GDP nominal growth

**Input 4 — Risk-free rate**

- Damodaran uses 10Y Treasury

- Some alternatives use 30Y Treasury

- SONAR yield curve output direct input

**Input 5 — Iteration method**

- Solve r via numerical iteration (Newton-Raphson, bisection)

- Initial guess: 8%

- Converges in few iterations

### 7.4 Alternative approaches — earnings yield
**Simple earnings yield**

*ERP_simple = (1/PE_forward) − risk_free*

Earnings yield (inverse of PE) minus risk-free rate. Intuitive simplification.

- Advantage: simple, observable directly

- Disadvantage: assumes earnings = cash flows (ignore reinvestment)

- Disadvantage: no growth accounted explicitly

- Disadvantage: forward PE uses analyst forecasts (can be biased)

**Shiller adjusted**

*ERP_CAPE = (1/CAPE) − real_risk_free*

Uses CAPE (cyclically adjusted PE) as denominator. SONAR's manual financeiro Cap 7 tracked CAPE; same input here.

- Uses average of 10 years real earnings

- Smooths cyclical earnings fluctuations

- Reflects real (not nominal) returns

- SONAR publishes CAPE-based ERP alongside Damodaran-style

**Fama-French 3-factor implied**

Decomposes returns into market factor + size factor + value factor. Implied ERP can be extracted but complex.

- Academic standard

- Not used in SONAR operational output (too complex for daily)

### 7.5 The three SONAR ERP outputs
SONAR publishes três versões de ERP, each with different strengths:

**ERP_1 — Gordon simplified**

*ERP_gordon = (D+B)/P + g_longterm − risk_free_10y*

- Simples, easy to interpret

- Uses payout yield (dividends + buybacks) + long-term growth

- Long-term growth = 10Y Treasury yield (Damodaran convention)

- Updated daily

**ERP_2 — DCF full (Damodaran method)**

- Solve-for-r via 5-year projection + terminal value

- Uses analyst estimates year 1-5

- Most rigorous

- Updated daily (inputs that update daily)

**ERP_3 — Earnings yield simple**

*ERP_simple = (1/PE_forward) − risk_free_10y*

- Quick sanity check

- Useful for cross-validation

- Updated daily

**SONAR canonical output**

ERP_2 (DCF full) é o primary output. ERP_1 e ERP_3 publicados como validation overlays. Triangulation quando diferem significantly.

### 7.6 Historical behavior of implied ERP
Implied ERP (Damodaran method) desde 1960:

| **Periodo**    | **ERP range** | **Contexto**                    |
|----------------|---------------|---------------------------------|
| 1960s          | 3.0-4.5%      | Era high growth confidence      |
| 1970s          | 4.5-7.0%      | Stagflation risk premium        |
| 1980s          | 3.5-5.5%      | Volcker era, gradual re-rating  |
| 1990s          | 2.0-4.0%      | Dot-com bubble compressed ERP   |
| 2000-2002      | 2.5-4.5%      | Dot-com crash re-expanded       |
| 2003-2007      | 3.5-4.5%      | Steady pre-crisis               |
| 2008-2010      | 5.5-7.0%      | GFC elevated uncertainty        |
| 2011-2019      | 4.5-6.5%      | Post-GFC persistent elevated    |
| 2020           | 6.0-7.0%      | COVID shock                     |
| 2021           | 4.5-5.5%      | Compressed during Euphoria      |
| 2022-2023      | 5.0-6.5%      | Inflation shock, Fed tightening |
| 2024-2025      | 4.5-5.5%      | Post-inflation normalization    |
| 2026 (current) | ~4.5-5.0%     | AI bubble concerns              |

**Key patterns**

- ERP compresses during bubbles (dot-com, 2021)

- ERP expands during crises (2008, 2020)

- Historical median ~4.5-5.0%

- Extremes rare — 2% or 7% indicate exceptional

**Forward return correlation**

- Low ERP (\<3%) historically precedes low 10Y returns

- High ERP (\>6%) historically precedes high 10Y returns

- Correlation modest (~0.4) but consistent

- ERP not market-timing tool, but calibration tool

### 7.7 ERP for different markets
SONAR computes ERP for multiple mature markets além de US.

**US (S&P 500) — primary**

- Most rigorous implementation

- Deepest data

- Most validation against Damodaran monthly

**Europe (STOXX 600 / Euro STOXX 50)**

- Equivalent Damodaran method applied

- Risk-free: Bund 10Y

- Cash flows: STOXX earnings via FactSet EA

- Different historical levels (~0.5-1% higher than US)

**UK (FTSE 100 / FTSE All-Share)**

- Similar approach

- Risk-free: Gilt 10Y

- UK equity tends to have higher dividend yield, lower growth

**Japan (TOPIX / Nikkei 225)**

- Adjusted for Japan's equity culture

- Historical buyback rates lower

- Risk-free: JGB 10Y (but complicated by YCC history)

- Post-2013 governance reforms increasing dividend + buyback

**Emerging markets**

- ERP computation trickier

- CRP overlays separately (see Parte IV)

- Total required return = mature ERP + CRP for EM

- EM-specific implied ERP available but lower reliability

### 7.8 ERP vs real vs nominal
ERP é typically nominal (risk-free is nominal). Pode ser converted:

*ERP_real = (1 + ERP_nominal) / (1 + expected_inflation) − 1*

Approximately: ERP_real ≈ ERP_nominal (since ERP is excess over risk-free, and inflation affects both similarly).

- For most purposes, ERP nominal = ERP real (approximately)

- Minor differences exist (Jensen's inequality for continuous compounding)

- SONAR publishes nominal as default

### 7.9 Theory caveats
**Caveat 1 — Analyst estimate bias**

Analyst earnings estimates historically biased optimistic, especially long-term. Kim-Shin (2014) document ~300bps bias vs realized over 5-year horizons.

- SONAR applies haircut to analyst estimates

- 15-20% downward adjustment to aggregate top-down estimates

- Documented methodology

- Reduces ERP estimates by 50-80bps typically

**Caveat 2 — Buyback future**

Buyback rates highly variable. Tax policy changes can flip behavior. Assuming current rates continue adds uncertainty.

**Caveat 3 — Growth terminal assumption**

Terminal growth = risk-free rate (Damodaran) é assumption, not truth. Alternative assumptions (GDP growth nominal) can give different results.

**Caveat 4 — Survivorship and index composition**

S&P 500 changes composition. Current composition more tech-heavy than historical. This affects implied ERP comparability to historical.

> *ERP é model output, not observable truth. O valor vem de calibrated analysis, not of claiming precision. SONAR publishes com confidence intervals explicitly reflecting these caveats.*

## Capítulo 8 · Implementação técnica — S&P 500 e análogos
### 8.1 S&P 500 implementation
**Data inputs required daily**

| **Input**                       | **Source**                      | **Update frequency** |
|---------------------------------|---------------------------------|----------------------|
| S&P 500 level                   | FRED SP500 / Yahoo ^GSPC        | Daily                |
| S&P 500 trailing dividend yield | FRED MULT_SP500_DIV_YIELD_MONTH | Monthly              |
| S&P 500 buyback yield           | S&P DJI publication             | Quarterly            |
| Analyst EPS estimates 1-5Y      | FactSet/IBES/Refinitiv          | Monthly              |
| 10Y Treasury yield              | SONAR yield curve / FRED DGS10  | Daily                |
| Trailing 12M earnings           | S&P DJI / WSJ                   | Quarterly            |

**Daily computation**

> def compute_erp_daily(date):
> \# Daily inputs
> sp500 = get_fred('SP500', date)
> treasury_10y = get_sonar_yc('US', date, tenor='10Y')
> \# Slower-moving inputs (latest available)
> dividend_yield = get_fred('MULT_SP500_DIV_YIELD_MONTH', date) \# monthly
> buyback_yield = get_sp_dji_buyback_yield(date) \# quarterly
> payout_yield = dividend_yield + buyback_yield
> \# Analyst estimates (monthly update)
> eps_year1 = get_factset_eps_estimate(date, horizon=1)
> eps_year2 = get_factset_eps_estimate(date, horizon=2)
> eps_year3 = get_factset_eps_estimate(date, horizon=3)
> eps_year4 = get_factset_eps_estimate(date, horizon=4)
> eps_year5 = get_factset_eps_estimate(date, horizon=5)
> \# Apply bias haircut (optional but recommended)
> HAIRCUT = 0.15
> eps_year1_adj = eps_year1 \* (1 - HAIRCUT \* 0.2) \# less haircut near-term
> eps_year5_adj = eps_year5 \* (1 - HAIRCUT \* 1.0) \# more haircut long-term
> \# Compute total payout per year (earnings × payout ratio)
> payout_ratio = payout_yield / (trailing_eps / sp500)
> cash_flows = \[eps_year_i_adj \* payout_ratio for i in 1..5\]
> \# Terminal value: perpetual growth = risk_free
> terminal_growth = treasury_10y / 100
> cf_year5 = cash_flows\[4\]
> \# Solve for r (implied required return)
> def npv(r):
> tv = cf_year5 \* (1 + terminal_growth) / (r - terminal_growth)
> present = sum(cash_flows\[t\] / (1+r)\*\*(t+1) for t in range(5))
> present += tv / (1+r)\*\*5
> return present - sp500
> r_implied = bisect(npv, 0.02, 0.20)
> \# ERP = implied return - risk-free
> erp = r_implied - treasury_10y / 100
> return {
> 'date': date,
> 'sp500': sp500,
> 'treasury_10y': treasury_10y,
> 'implied_return': r_implied \* 100,
> 'erp_pct': erp \* 100,
> 'methodology': 'damodaran_full_v1.2',
> 'inputs_used': {...}
> }

**Validation steps post-compute**

- ERP in reasonable range (2% to 8% typical)

- Delta from previous day \< 100bps (absent market shocks)

- Cross-check against ERP_Gordon and ERP_simple

- Flag if RMSE of three methods \> 150bps

### 8.2 Source data pipeline
**Analyst estimates — FactSet/IBES**

- Primary source for bottom-up earnings

- FactSet Earnings Insight: aggregate S&P 500 estimates

- Monthly report publication

- Scrape methodology + historical database required

- Alternative: IBES via Refinitiv (paid)

**S&P DJI buyback data**

- S&P Dow Jones Indices publica quarterly

- \`spglobal.com/spdji/en/\` — reports available

- Buyback yield as % market cap

- Latest available lags ~45 days behind quarter end

**Trailing earnings — Bloomberg / WSJ**

- S&P 500 trailing 12M EPS (GAAP and operating)

- WSJ / Barron's publica weekly

- FactSet aggregated

**Fallback when primary sources fail**

- Use prior month's analyst estimates

- Extrapolate trailing dividend yield

- Flag output as "estimated inputs"

- Wider confidence interval

### 8.3 STOXX 600 / Euro STOXX implementation
**Adjustments for EA**

- **Risk-free:** Bund 10Y (via SONAR yield curve)

- **Index:** STOXX 600 (broader) or Euro STOXX 50 (blue chips)

- **Dividend yield:** historically higher than US (~3% vs 1.5%)

- **Buyback:** less prevalent than US (~1.5% vs 2-4%)

- **Total payout:** comparable to US (~4-5%)

- **Analyst estimates:** FactSet EA, IBES

- **Currency:** EUR throughout

**Historical EA ERP**

- Tends to be 50-100bps higher than US ERP

- Reflects EA structural concerns (political, regulatory)

- Less growth component

- EA ERP 2026 estimate: ~5.0-5.5%

### 8.4 FTSE UK implementation
**UK specifics**

- **Index:** FTSE 100 + FTSE All-Share

- **Risk-free:** Gilt 10Y

- **Dividend yield UK:** historically high ~3.5-4.5%

- **Buyback UK:** lower than US

- **Currency:** GBP

**FTSE characteristics**

- Heavy weighting in old-economy sectors (energy, banks, miners)

- Low growth expectation

- Value-tilted historically

- ERP UK typically similar or slightly higher than US

### 8.5 Japan implementation
**TOPIX + Nikkei 225**

- **Risk-free:** JGB 10Y (post-YCC exit clean)

- **Payout yield:** growing — corporate governance reforms increasing

- **Historical context:** Decades of deflation distorted traditional metrics

**Japan ERP patterns**

- Historical: elevated ERP reflecting deflation

- Post-Abenomics (2013+): compressed

- Post-YCC (2024+): normalizing

- 2026 estimate: ~5-6%

### 8.6 Cross-market ERP comparison
SONAR publishes cross-market ERP chart daily. Useful for:

- Identifying cheap/expensive markets

- Supporting asset allocation decisions

- Cross-country equity fund analysis

- Macro-tourist investment decisions

**Current (April 2026) cross-market ERP snapshot**

| **Market**     | **Risk-free 10Y** | **Payout yield** | **Implied return** | **ERP** |
|----------------|-------------------|------------------|--------------------|---------|
| US S&P 500     | 4.25%             | 4.2%             | 9.1%               | 4.85%   |
| STOXX 600      | 2.45%             | 4.8%             | 7.7%               | 5.25%   |
| FTSE All-Share | 4.10%             | 5.1%             | 9.5%               | 5.40%   |
| TOPIX          | 1.55%             | 3.5%             | 7.1%               | 5.55%   |

Interpretation: Japan appears cheapest on ERP basis, UK most expensive on historical basis. US fairly valued. These are snapshots — evolve daily.

### 8.7 ERP and CAPE relationship
SONAR also publishes CAPE-derived ERP (see Cap 7 financial manual Cap 7). Two views:

**ERP_CAPE = 1/CAPE − real_risk_free**

Current CAPE ~35 → 1/CAPE ~2.86%. Real risk-free ~2% → ERP_CAPE ~0.86%.

Muito compressed. Shiller's perspective: forward returns likely low.

**Why ERP_DCF \> ERP_CAPE currently**

- DCF uses forward-looking earnings (analyst estimates)

- CAPE uses trailing 10-year smoothed earnings (captures regime)

- Analyst estimates optimistic (~5-10%/year earnings growth)

- Earnings growth has outpaced smoothed trailing

- Divergence = ~400bps currently

**Interpretation**

- If analyst estimates hold, ERP is OK at 4.5-5%

- If earnings revert to CAPE-implied, returns much lower

- Divergence is diagnostic of late-cycle

- Historical: divergence this wide occurred pre-2000, pre-2007

> *ERP publishing both methods is not accident — it's a feature. Divergence tells you something fundamental about market's earnings assumptions vs historical reversion. Narrow ERP_DCF + narrow ERP_CAPE = fairly valued. Narrow ERP_DCF + wide ERP_CAPE = late-cycle.*

## Capítulo 9 · Validação e signal quality
### 9.1 Cross-validation framework
SONAR's ERP computation is new — must be validated. Three sources of cross-validation:

**Source 1 — Damodaran monthly publication**

- Gold standard benchmark

- SONAR's daily should match Damodaran monthly (end-of-month)

- Target: within 20bps of Damodaran monthly ERP

- Larger deviations indicate methodology differences

**Source 2 — Shiller CAPE-based long-term**

- Historical long-term ERP ~4-5% for US

- SONAR output should be in same ballpark

- Significant divergence requires investigation

**Source 3 — SPF (Survey of Professional Forecasters)**

- Institutional investor expectations surveys

- Philadelphia Fed SPF 10-year equity return expectation

- Less precise but triangulates

- Published quarterly

### 9.2 Backtesting signal quality
Critical question: does ERP have predictive power? Test historically.

**Backtest methodology**

43. Compute ERP daily since 1960

44. Correlate ERP with subsequent 10Y S&P 500 real returns

45. Expectation: lower ERP → lower future returns

46. Higher ERP → higher future returns

47. Effect size and significance measured

**Expected results**

| **Starting ERP percentile** | **Subsequent 10Y real S&P return** |
|-----------------------------|------------------------------------|
| \< 20th (very compressed)   | 0-3% annualized                    |
| 20-40th                     | 3-6%                               |
| 40-60th (median)            | 5-8%                               |
| 60-80th                     | 7-10%                              |
| \> 80th (very expanded)     | 9-13%                              |

**Interpretation**

- ERP has modest but real predictive power

- Correlation between starting ERP and future returns ~0.40-0.55

- Better for 10-year horizons than 1-year

- Not market-timing tool, but calibration tool

### 9.3 Signal quality at extremes
ERP particularly informative at extremes:

**Compressed ERP (\< 3%)**

- Historical occurrences: 1960s, late 1990s, 2021

- Subsequent 10Y returns: typically low (0-3% real)

- Signal strength: HIGH — 80%+ hit rate

- Current (April 2026): DCF method shows 4.8%, CAPE method shows 0.9%

- Divergence creates uncertainty

**Expanded ERP (\> 6%)**

- Historical occurrences: 1970s, 2009, 2020

- Subsequent 10Y returns: typically high (9-13% real)

- Signal strength: HIGH — 85%+ hit rate

- Current (April 2026): neither method shows extreme expansion

**Mid-range ERP (4-5%)**

- Historically most common (~50% of time)

- Subsequent returns: wide range (3-9%)

- Signal strength: LOWER

- Context dependent — need to cross-reference cycle framework

### 9.4 Combining with cycle framework
ERP signal strength enhanced when combined with SONAR cycle classifications:

**Combination 1 — ERP compressed + FCS Euphoria**

- Maximum warning signal

- Historical: 2000 dot-com, 2007 pre-crisis, 2021

- Subsequent: severe corrections (30-50%+)

- SONAR alert level: red/severe

**Combination 2 — ERP expanded + FCS Stress**

- Bullish combination

- Historical: 2009, 2020 March

- Subsequent: strong recoveries (40-100%+ 2Y)

- SONAR alert: opportunity signal

**Combination 3 — ERP mid + MSC Accommodative**

- Benign environment

- Historical: 2013-2018 typical

- Sustainable positioning

**Combination 4 — ERP compressed + MSC Tight**

- Transition warning

- Double-headwind setup

- Rate discounting pressure + valuation compression risk

- Historical: 2022

- SONAR alert: caution

### 9.5 ERP volatility characteristics
**Daily volatility**

- ERP daily changes typically \< 20bps

- Larger changes flag data issues or market shocks

- Monthly changes ~50-100bps typical

- Annual changes 100-300bps typical

**Regime-dependent**

- Bull markets: ERP drifts downward slowly

- Bear markets: ERP spikes upward quickly

- Crisis: ERP can jump 200bps in weeks

- Recovery: ERP normalizes over 12-18 months

### 9.6 Sensitivity analysis
ERP is sensitive to input assumptions. SONAR documents sensitivity:

**Sensitivity to growth assumption**

- +1% terminal growth → ERP drops by ~70-100bps

- -1% terminal growth → ERP rises by ~70-100bps

- Largest single sensitivity

**Sensitivity to buyback assumption**

- +1% buyback yield → ERP rises by ~80bps

- Current buyback rates critical input

**Sensitivity to analyst bias haircut**

- No haircut → ERP ~50bps higher than with 15% haircut

- 20% haircut → ERP ~60bps lower than no haircut

- Choice of haircut is methodological judgment

**Sensitivity to risk-free choice**

- Using 30Y vs 10Y → ERP differ by ~20-30bps

- Using real risk-free vs nominal → bigger impact

- SONAR convention: 10Y nominal

### 9.7 Methodology version control
SONAR ERP methodology will evolve. Version control essential:

**v1.0 (initial)**

- Damodaran DCF base

- No haircut to analyst estimates

- 10Y Treasury risk-free

**v1.1 (backtesting feedback)**

- Add 15% haircut to aggregate analyst estimates

- Optional CAPE cross-check output

**v1.2 (current)**

- Tenor-graded haircut (less near-term, more long-term)

- Include buyback from S&P DJI directly

- Output uncertainty intervals

**v2.0 (planned)**

- Machine learning adjustment to analyst estimates

- Sector decomposition of ERP

- Real-time intraday updates

**Documentation standard**

- Historical ERP backfilled with current methodology

- Methodology changes documented

- Users can request historical with specific version

### 9.8 Publishing interface
**Daily SONAR ERP output**

> {
> "date": "2026-04-17",
> "country": "US",
> "erp_outputs": {
> "erp_dcf_damodaran": {
> "value_pct": 4.82,
> "method": "damodaran_full_v1.2",
> "confidence": 0.88
> },
> "erp_gordon_simple": {
> "value_pct": 5.15,
> "method": "gordon_constant_growth",
> "confidence": 0.75
> },
> "erp_earnings_yield_simple": {
> "value_pct": 4.45,
> "method": "1_over_forward_pe_minus_riskfree",
> "confidence": 0.80
> },
> "erp_cape_shiller": {
> "value_pct": 0.92,
> "method": "cape_inverse_minus_real_rf",
> "confidence": 0.82
> }
> },
> "canonical_erp": {
> "value_pct": 4.82,
> "method_used": "erp_dcf_damodaran",
> "cross_validation_range": \[4.45, 5.15\],
> "divergence_flag": "DCF_vs_CAPE_wide" // signals late-cycle
> },
> "inputs": {
> "sp500_level": 5850,
> "treasury_10y": 4.25,
> "trailing_dividend_yield": 1.52,
> "buyback_yield_estimated": 2.65,
> "aggregate_eps_1y_fwd": 260,
> "aggregate_eps_5y_fwd": 385
> },
> "historical_context": {
> "erp_30day_avg": 4.95,
> "erp_ytd_avg": 4.78,
> "erp_5y_avg": 5.22,
> "current_percentile_5y": 25
> },
> "state_flag": "moderate_compression"
> }

### 9.9 Use cases and editorial applications
**Use case 1 — Market regime assessment**

Weekly ERP tracking provides feel for market regime. Drifting compression over months signals late-cycle. Sharp expansion signals crisis.

**Use case 2 — Valuation discipline**

When doing individual stock DCFs, use SONAR ERP current as discount rate premium. Ensures consistency with market's implicit pricing.

**Use case 3 — Asset allocation signals**

- ERP \< 3%: reduce equity overweight

- ERP \> 6%: increase equity overweight

- Cross-reference with cycle framework

**Use case 4 — Editorial pieces**

- "ERP em 2026 — abaixo da mediana histórica"

- "Quando ERP compress + FCS Euphoria — as três vezes históricas"

- "A divergência ERP_DCF vs ERP_CAPE em 2026 — o que Shiller nos diria"

- "Cross-market ERP — Japão a 5.5%, Europa a 5.2%, US a 4.8%"

**Use case 5 — Fund communications**

When 7365 Capital launches fund, quarterly letters reference ERP compression levels. Transparent macro positioning rationale.

### 9.10 Limitations honestos
**Limitation 1 — Not a market timing tool**

- ERP doesn't predict short-term moves

- Can stay compressed for years (late 1990s)

- Can stay expanded for years (post-2008)

**Limitation 2 — Methodology-dependent**

- Different methods give different numbers

- SONAR publishes three methods

- Divergence itself is signal

**Limitation 3 — Input quality**

- Garbage in, garbage out

- Analyst estimates particularly suspect

- Buyback forecasts uncertain

- Terminal growth assumption judgmental

**Limitation 4 — Index composition changes**

- S&P 500 composition evolves

- Tech-heavy index now vs 1960s

- Historical comparability imperfect

**Limitation 5 — Regime changes**

- Interest rate regime affects "normal" ERP

- Post-2008 low rates → potentially structurally different

- AI era productivity gains → potentially different

> *ERP compputada diariamente é underrated technology. Damodaran conveys the methodology; SONAR operationalizes it at the frequency that real decisions require. Combined com cycle framework, é one of the most valuable outputs in the SONAR universe.*

**Encerramento da Parte III**

Parte III estabeleceu a primeira grande inovação operacional do SONAR sub-models — o ERP computado diariamente:

- **Capítulo 7 — Teoria.** Quatro definições distintas de ERP (historical, expected, required, implied). SONAR choice: implied, market-derived, daily. Gordon constant growth model (simplified). DCF full approach (Damodaran). Cinco inputs componentes: index level, cash flows (dividends + buybacks), growth projections, risk-free, iteration. Earnings yield alternative. Shiller CAPE-based. Três outputs SONAR em paralelo: ERP_1 Gordon, ERP_2 DCF full (primary), ERP_3 earnings yield simple. Historical behavior 1960-2026 tabulado. Cross-market coverage (US, EA, UK, Japan). Real vs nominal discussion. Quatro theory caveats honestos (analyst bias, buyback future, terminal growth, index composition).

- **Capítulo 8 — Implementation técnica.** S&P 500 data inputs tabulados por source e frequency. Python pseudocode completo para daily computation com bisection solver. Source pipeline detalhado (FactSet/IBES analyst estimates, S&P DJI buyback, WSJ/FactSet trailing earnings). Adjustments por market — STOXX 600, FTSE, TOPIX. Cross-market ERP snapshot April 2026 (US 4.85%, STOXX 5.25%, FTSE 5.40%, TOPIX 5.55%). ERP vs CAPE relationship crítica — DCF 4.82% vs CAPE 0.92% implies 400bps divergência diagnostic de late-cycle.

- **Capítulo 9 — Validação e signal quality.** Three cross-validation sources (Damodaran monthly benchmark target \<20bps, Shiller long-term, SPF surveys). Backtest signal quality — starting ERP percentile vs subsequent 10Y returns tabulado. Signal strength em extremes (\<3% e \>6%) HIGH 80%+ hit rate, mid-range signal strength LOWER. Combinação com cycle framework — ERP compressed + FCS Euphoria = maximum warning, ERP expanded + FCS Stress = opportunity. Sensitivity analysis (growth, buyback, haircut, risk-free). Methodology version control v1.0 → v2.0 planned. Daily publishing interface JSON completo. Five use cases (regime assessment, valuation discipline, allocation signals, editorial, fund communications). Five limitations honestos.

**O que a Parte III entrega**

48. ERP computado DIARIAMENTE (vs Damodaran mensal)

49. Três métodos paralelos com triangulation

50. Cross-market coverage (US, EA, UK, Japan)

51. Validation framework rigoroso

52. Signal quality documented via backtest

53. Combination with cycle framework quadruplicates utility

**Material editorial potencial**

54. "ERP diário — o que Damodaran nos daria se publicasse diariamente"

55. "DCF vs CAPE ERP em 2026 — a divergência que Shiller reconheceria"

56. "Cross-market ERP — onde estão as oportunidades em Abril 2026"

57. "Quando ERP compresses + FCS Euphoria — as três vezes na história"

58. "Analyst estimate bias — quanto devemos haircut em 2026?"

***A Parte IV — Country Risk Premium (capítulos 10-12)** aborda o segundo output crítico: como medir o country risk premium para 30+ países. Cap 10 CDS-based approach (quando disponível), Cap 11 sovereign spread approach (when CDS ilíquido), Cap 12 volatility ratio synthesis (Damodaran-style) combinando default risk com equity-vs-bond volatility per country. Output final operacional para Portugal, Italy, Spain, Greece, Turkey, Brazil, India, China, Mexico e outros — essencial para cross-border cost of equity.*

# PARTE IV
**Country Risk Premium**

*CDS-based, sovereign spread, volatility ratio — output operacional 30+ países*

**Capítulos nesta parte**

**Cap. 10 ·** CDS-based approach e a estrutura do country default risk

**Cap. 11 ·** Sovereign spread approach quando CDS ilíquido

**Cap. 12 ·** Volatility ratio synthesis — operational output per country
