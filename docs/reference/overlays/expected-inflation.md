# Expected Inflation

> Overlay L2 — Parte V (caps 16-17) · Expected inflation do Manual dos Sub-Modelos Quantitativos.

## Capítulo 16 · Expected inflation — market-based e surveys
### 16.1 Por que SONAR precisa de expected inflation
Cap 3 estabeleceu os cinco usos de expected inflation: real-nominal conversion, long-term cash flow growth, currency forward expectation, monetary policy expectation, inflation-linked pricing. Este capítulo e o próximo operacionalizam o sub-model.

> *Expected inflation não é observável directly — tem que ser inferida. SONAR combina três approaches: market-based (breakevens, inflation swaps), survey-based (SPF, ECB SPF, Michigan, BoE), e model-based fallback para countries sem market data.*

### 16.2 Market-based — breakeven inflation
**Definition**

*BEI(τ) = nominal_yield(τ) − real_yield(τ)*

Onde real_yield é do inflation-linked bond (TIPS, ILG, BTP€i, etc.). BEI representa inflation rate que would equalize returns between nominal and inflation-linked bonds.

**US TIPS breakevens**

- 5Y, 7Y, 10Y, 20Y, 30Y via FRED

- \`T5YIE\`, \`T7YIE\`, \`T10YIE\`, \`T20YIE\`, \`T30YIE\`

- Daily updates

- Most deeply analyzed inflation expectations globally

**UK ILG breakevens**

- Deepest inflation-linked bond market globally

- Tenors: 3Y, 5Y, 10Y, 15Y, 20Y, 25Y, 30Y, 40Y

- RPI-linked historically (transitioning to CPIH)

- BoE publishes fitted curves daily

**EA country breakevens**

- France OATi (CPI-linked to French CPI)

- France OAT€i (HICP-linked)

- Italy BTP€i (HICP-linked)

- Germany ILB (HICP-linked)

- Spain BEIi (HICP-linked)

- ECB publishes fitted EA aggregate real yield curve

**Japan linkers**

- Limited liquidity post-2013

- BoJ dominant holder

- Breakevens less meaningful

### 16.3 Breakeven inflation caveats
**Caveat 1 — Inflation risk premium**

BEI contains risk premium for inflation uncertainty, not just expected inflation:

*BEI(τ) = E\[π(τ)\] + IRP(τ) − liquidity_premium(τ)*

- Inflation risk premium (IRP): positive, ~20-50bps typically

- Liquidity premium: negative impact on real yields (TIPS less liquid than nominal)

- Net effect: BEI slightly above pure expected inflation

**Caveat 2 — Structural liquidity**

- TIPS liquidity varies by tenor and time

- 30Y TIPS particularly illiquid

- Crisis periods: TIPS liquidity dried up (March 2020)

- Distorts breakeven measurement temporarily

**Caveat 3 — Seasonality in short-dated**

- Short-dated breakevens (\<2Y) affected by seasonal CPI patterns

- Less reliable for pure expected inflation

- 5Y+ cleaner signal

**Caveat 4 — Index composition**

- CPI vs Core CPI vs PCE vs HICP — different indices

- Breakeven linked to specific index

- Not directly comparable across countries

### 16.4 Inflation swaps — the cleaner measure
Inflation swaps são derivatives where one party pays fixed rate, other pays realized inflation. Widely used for hedging and speculation.

**Advantages over breakevens**

- No bond liquidity premium contamination

- Pure inflation expectation (plus risk premium)

- Available for specific tenors cleanly

- 5Y, 10Y, 5y5y forward are standard quotes

- Higher liquidity than longest-dated linkers

**5y5y forward inflation swap — the critical indicator**

*5y5y_forward_swap = (10y_swap_rate × 10 − 5y_swap_rate × 5) / 5*

This measures market's implied inflation between years 5 and 10. BCs watch this intensely as credibility anchor.

**5y5y trajectory insights**

- Fed target 2% → 5y5y should anchor near 2%

- ECB target 2% → 5y5y should anchor near 2%

- Drift above target = credibility erosion

- Drift below target = deflation risk

**Recent history**

- 2013-2019: US 5y5y anchored 1.8-2.2% (credibility intact)

- 2020-2021: brief dip then sharp rise

- 2022 peak: 5y5y touched 2.8% (credibility questioning)

- 2023-2025: gradual return to 2.2-2.5%

- 2026 current: ~2.3%

**EA 5y5y pattern**

- 2014-2021: consistently below target, deflation concerns

- 2022-2023: sharp rise to ~2.5%

- 2024-2026: anchored near 2.1%

### 16.5 Inflation swap sources
**Primary sources**

- Bloomberg (swap rates for most liquid currencies)

- Refinitiv Eikon

- ICAP / Tullett Prebon brokers

**Free alternatives**

- ECB publishes EA inflation swap rates

- FRED has some US inflation swap data

- Federal Reserve H.15 briefly included

- Academic databases periodic publications

**SONAR approach**

- Use ECB SDW for EA inflation swaps

- Bloomberg if available for US, UK, JP

- Otherwise rely on breakevens with IRP adjustment

- Tier 1 MVP: breakevens + estimated swaps

- Tier 2 upgrade: true swap data via professional sources

### 16.6 Survey-based measures
**US — Survey of Professional Forecasters (SPF)**

- Philadelphia Fed publishes quarterly

- \`philadelphiafed.org/research-and-data/real-time-center/survey-of-professional-forecasters/\`

- 10-year-ahead inflation expectation

- Median forecast + full distribution

- Available since 1968

- Smooth, reliable time series

**US — Michigan Consumer Survey**

- University of Michigan surveys consumers

- \`data.sca.isr.umich.edu/\`

- 1-year-ahead and 5-10-year-ahead inflation expectations

- Monthly preliminary + final

- Consumer expectations (not professional) — more volatile

- Available via FRED \`MICH\` and \`MICH5Y\`

**EA — ECB Survey of Professional Forecasters**

- ECB publishes quarterly

- \`ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/\`

- 1Y, 2Y, 5Y-ahead expectations

- Panel of professional forecasters

- Available since 1999

**EA — Consumer Expectations Survey**

- ECB consumer surveys (post-2020)

- Monthly

- New initiative, still building track record

**UK — BoE Decision Maker Panel**

- Quarterly survey of CFOs

- Price expectations and wage expectations

- Useful for corporate-side view

**Japan — BOJ Tankan**

- Quarterly large enterprise survey

- Price expectations 1Y, 3Y, 5Y

- Post-deflation era recovering

### 16.7 Survey vs market-based — which is better
**When surveys preferred**

- Emerging markets without deep linker markets

- Short-horizon (surveys capture recent developments)

- Policy-relevant anchoring (central banks watch surveys)

- Households/consumer-oriented analysis

**When market preferred**

- Mature markets with liquid linkers

- Real-time signal needed

- Market participant perspective

- Forward pricing

**SONAR hybrid approach**

- Use market-based where available (US, UK, France, Germany, Italy primary)

- Use surveys where market-based insufficient

- Publish both for triangulation

- Note divergence as signal

### 16.8 Term structure of expected inflation
Expected inflation is not a single number — it's a term structure:

| **Horizon** | **Primary source**        | **Interpretation**          |
|-------------|---------------------------|-----------------------------|
| 1Y          | Survey primary + short BE | Near-term momentum          |
| 2Y          | Survey + BE               | Policy-relevant horizon     |
| 5Y          | BE + swaps                | Medium-term                 |
| 5y5y        | Forward derived           | Long-term anchor assessment |
| 10Y         | BE + swaps                | Long-term                   |
| 10y10y      | Forward derived           | Ultra-long                  |

**Daily SONAR output**

> {
> "country": "US",
> "date": "2026-04-17",
> "expected_inflation_term_structure": {
> "1y": {"value_pct": 2.45, "source": "Michigan + SPF"},
> "2y": {"value_pct": 2.35, "source": "SPF"},
> "5y": {"value_pct": 2.30, "source": "TIPS breakeven 5Y"},
> "10y": {"value_pct": 2.42, "source": "TIPS breakeven 10Y"},
> "30y": {"value_pct": 2.45, "source": "TIPS breakeven 30Y"}
> },
> "forward_derived": {
> "1y_in_1y": 2.25,
> "5y5y_forward": 2.54,
> "10y10y_forward": 2.48
> },
> "anchoring_assessment": {
> "5y5y_vs_target": 0.54, // 54bps above 2% target
> "anchor_status": "moderately_drifting_high",
> "fed_concern_indicator": true
> }
> }

## Capítulo 17 · Expected inflation cross-country e Portugal
### 17.1 Challenge — most countries não têm inflation-linked markets
US tem TIPS, UK tem ILGs, UE aggregate tem RPPI linkers para Germany/France/Italy. But most countries don't. Portugal doesn't. Most EMs don't. How does SONAR produce expected inflation para esses casos?

### 17.2 Hierarchy of approaches
SONAR applies hierarchy similar to sovereign spread — prefer direct market data, fall back to alternatives:

88. **Direct breakeven (US, UK, Germany, France, Italy, Canada):** use observed BEI

89. **Inflation swap (major currencies):** cleaner signal when available

90. **Regional aggregate + country differential (Portugal, Spain, most EA periphery):** EA aggregate BEI + country-specific inflation differential historical

91. **Survey-based (Japan, most EMs, countries with good statistical institutes):** SPF, IMF WEO, OECD projections

92. **Model-based (stressed EMs, frontier markets):** simple VAR or IMF projections

### 17.3 Portugal specifically
Portugal é excelente exemplo de country Tier 3 para SONAR expected inflation. Sem TIPS-like mercado líquido. Sem inflation swap market local. Como SONAR constrói?

**Components of Portugal expected inflation**

- **Step 1 — EA aggregate breakeven:** ECB publishes via SDW, 5Y-10Y fitted

- **Step 2 — Historical PT-EA inflation differential:** 5-year rolling

- **Step 3 — Cross-check BdP projections:** Banco de Portugal publishes Perspetivas Económicas

- **Step 4 — Cross-check INE current CPI:** INE publica monthly + trend

- **Step 5 — Compute expected inflation PT:** formula applied

**Computation formula**

*E\[π_PT(τ)\] = E\[π_EA(τ)\] + Historical_PT_EA_differential(5Y rolling)*

**Example — April 2026**

> Portugal Expected Inflation 10Y — computation
> Step 1: EA aggregate 10Y BEI = 2.20%
> Step 2: Historical PT-EA differential
> PT HICP 5Y avg: 3.4%
> EA HICP 5Y avg: 3.1%
> PT-EA differential: +0.30 pp
> (during inflation period; historically closer to 0)
> Step 3: BdP projections cross-check
> BdP forecasts 2026-2028: PT CPI gradually returning to 2-2.2%
> Long-run: converging to EA ~2%
> Step 4: INE current trend
> PT headline CPI 2026 YTD: 2.4%
> Core: 2.2%
> Step 5: Compute
> Expected inflation PT 10Y = 2.20% + 0.15% (blended differential)
> = 2.35%
> Confidence interval: 2.15% - 2.55% (wider than US)
> Note: PT differential declining in recent years
> Long-run expect PT ~ EA (currency union convergence)

### 17.4 Portugal-specific adjustments
**Post-Troika normalization factor**

- PT had structural adjustment 2011-2014

- Internal devaluation through wage/price compression

- Post-Troika: gradual normalization

- Should converge to EA average over cycles

**Tourism-driven services inflation**

- PT has persistent upward pressure on services prices

- Housing, restauração, hotéis

- Structural effect ~0.3-0.5pp above EA average

- Offsets converging tendency

**Productivity differential**

- PT productivity growth below EA average historically

- Translates to slightly higher unit labor costs

- Balassa-Samuelson effect modest

### 17.5 EM expected inflation
**Turkey — high inflation regime**

- Survey-based primary source

- IMF WEO projections 10-20% range

- CBRT own forecasts (biased historically)

- Market-based proxies via local currency bond spreads

- SONAR uses consensus econoic forecasters (e.g. FocusEconomics)

**Argentina — hyperinflation context**

- Impossible to anchor forecasts

- IMF program projections

- Consensus forecasts (highly uncertain)

- Wide confidence intervals (±20%)

- Acknowledge limitations

**Brazil — managed inflation regime**

- BCB inflation target (currently 3%)

- IPCA-linked bonds (NTN-B) — excellent real yield data

- Breakeven inflation available 3Y-30Y

- Clean signal for medium-term

- Comparable to US approach

**India — moderate inflation**

- RBI inflation target 4% ±2%

- Limited linker market

- Survey-based primary

- SPF via RBI publishes

- Moderate reliability

**China — low inflation**

- No linker market

- Survey-based

- PBoC projections

- Consumer surveys

- Historical 0-3% range typical

- Deflation concerns post-2023

### 17.6 Cross-country expected inflation snapshot (April 2026)
| **Country**  | **1Y (%)** | **5Y (%)** | **10Y (%)** | **Source**                               |
|--------------|------------|------------|-------------|------------------------------------------|
| US           | 2.45       | 2.30       | 2.42        | Breakevens + SPF                         |
| EA aggregate | 2.15       | 2.10       | 2.20        | EA BEI + ECB SPF                         |
| Germany      | 2.10       | 2.05       | 2.15        | ILB breakevens                           |
| France       | 2.25       | 2.15       | 2.25        | OAT€i breakevens                         |
| Italy        | 2.45       | 2.35       | 2.45        | BTP€i breakevens                         |
| Spain        | 2.25       | 2.20       | 2.30        | EA + diff                                |
| Portugal     | 2.35       | 2.30       | 2.35        | EA + diff                                |
| UK           | 2.65       | 2.50       | 2.85        | ILG breakevens (RPI-linked historically) |
| Japan        | 1.85       | 1.70       | 1.75        | Survey + limited BE                      |
| Canada       | 2.15       | 2.05       | 2.10        | RRB breakevens                           |
| Australia    | 2.45       | 2.40       | 2.55        | TIB breakevens                           |
| China        | 1.80       | 2.00       | 2.10        | Survey + consensus                       |
| India        | 4.25       | 4.00       | 4.15        | Survey + IMF                             |
| Brazil       | 4.15       | 3.85       | 3.80        | NTN-B breakevens                         |
| Mexico       | 3.95       | 3.50       | 3.45        | UDI breakevens + BdM target              |
| Turkey       | 28.50      | 14.00      | 10.00       | Survey + IMF (wide CI)                   |
| Argentina    | 45.00      | 18.00      | 12.00       | Consensus, extreme uncertainty           |

**Key observations**

- Developed markets anchored near 2% target

- UK persistently above due to RPI formula

- Japan still below target despite post-YCC normalization

- EA periphery slight premium to core

- EMs clustered 3-5% typical, except high-inflation outliers

- Turkey, Argentina — hyperinflation regime, wide CI

### 17.7 Expected inflation for currency forward derivation
One key use of cross-country expected inflation: deriving expected currency moves via PPP.

**PPP formula**

*E\[FX\_{n}\] = FX\_{current} × (1 + π_local)^n / (1 + π_foreign)^n*

**Example — EUR/BRL 10-year**

> Current EUR/BRL: 5.85
> Expected inflation BRL 10Y: 3.80%
> Expected inflation EUR 10Y: 2.20%
> Differential: 1.60%/year
> Expected EUR/BRL 10Y forward:
> = 5.85 × (1 + 0.038)^10 / (1 + 0.022)^10
> = 5.85 × 1.452 / 1.242
> = 5.85 × 1.169
> = 6.84
> Expected BRL depreciation: ~17% over 10Y
> Annualized: ~1.6%/year
> This is the PPP expectation, subject to:
> - Deviations short-term (capital flows, oil price, risk-on/off)
> - Structural issues (productivity differential)
> - Policy changes

### 17.8 SONAR publishing framework expected inflation
> {
> "date": "2026-04-17",
> "country": "PT",
> "expected_inflation": {
> "1y": {
> "value_pct": 2.35,
> "confidence_interval": \[2.10, 2.60\],
> "source": "ea_ssa_plus_pt_differential",
> "method_version": "v1.1"
> },
> "5y": {
> "value_pct": 2.30,
> "confidence_interval": \[2.05, 2.55\],
> "source": "ea_breakeven_5y_plus_pt_historical_diff"
> },
> "10y": {
> "value_pct": 2.35,
> "confidence_interval": \[2.15, 2.55\],
> "source": "ea_breakeven_10y_plus_pt_historical_diff"
> },
> "5y5y_forward": {
> "value_pct": 2.40,
> "confidence_interval": \[2.20, 2.60\],
> "source": "derived_from_5y_and_10y"
> }
> },
> "components": {
> "ea_aggregate_bei_5y": 2.10,
> "ea_aggregate_bei_10y": 2.20,
> "pt_ea_historical_differential_5y_rolling_pp": 0.18,
> "bdp_latest_projection_10y": "converging to EA"
> },
> "current_cpi_context": {
> "pt_headline_cpi_latest_pct": 2.40,
> "pt_core_cpi_latest_pct": 2.20,
> "date_cpi_observation": "2026-03-31"
> },
> "fx_forward_implications": {
> "eur_pt_local": 1.00,
> "implied_pt_usd_10y_depreciation_vs_spot": "none (euro)",
> "implied_vs_gbp_10y": "slight appreciation",
> "implied_vs_brl_10y": "appreciation 15%+"
> }
> }

### 17.9 Use cases cross-country
**Use case 1 — Cross-border DCF**

Valuing Brazilian equity in EUR requires:

- Expected BRL inflation (3.8%)

- Expected EUR inflation (2.2%)

- Expected BRL/EUR depreciation (~1.6%/year)

- Cost of equity local BRL

- Present value in EUR

**Use case 2 — Monetary policy credibility**

Comparing 5y5y inflation forward across countries:

- Above 2% target: credibility erosion

- Below 2% target: deflation risk

- Japan post-YCC: gradual anchoring at 1.7%

- EA post-2022: re-anchored near 2%

**Use case 3 — Real yield comparison**

Real yields derived from nominal - expected inflation:

- US real 10Y = 4.25% - 2.42% = 1.83%

- EA real 10Y = 2.45% - 2.20% = 0.25%

- PT real 10Y = 3.15% - 2.35% = 0.80%

- Japan real 10Y = 1.55% - 1.75% = -0.20% (negative real)

**Use case 4 — Editorial angles**

- "Japan real yields negative — what it signals about BoJ credibility"

- "Portugal expected inflation 2.35% — below crisis-era, returning to convergence"

- "Brazil breakeven inflation — what NTN-B tells us about COPOM credibility"

- "PPP-implied forex across 20 currencies — where the big moves lie"

### 17.10 Limitations expected inflation
**Limitation 1 — Risk premium contamination**

- Breakevens contain inflation risk premium ~20-50bps

- True expected inflation probably lower than BEI

- SONAR publishes raw BEI; note this caveat

**Limitation 2 — Survey bias**

- Consumer surveys anchored to recent experience

- Professional surveys may anchor to institutional consensus

- Both have backward-looking bias

**Limitation 3 — Structural breaks**

- Inflation regime changes (2022 inflation shock)

- Historical differentials may not hold

- Models require recalibration

**Limitation 4 — EM uncertainty**

- Political/policy changes can shift inflation rapidly

- Wide confidence intervals warranted

- Tail risk underestimated

**Limitation 5 — Long-horizon uncertainty**

- 30Y forecasts are weak

- 5y5y better anchored theoretically

- But still model-based

- Users should weight short horizons more

> *Expected inflation é o sub-model que mais beneficia de triangulation. Market-based + survey-based + model-based convergence = high confidence. Divergence = signal for deeper investigation. SONAR's value is in making this triangulation systematic and daily.*

**Encerramento da Parte V**

Parte V completou os últimos dois sub-models críticos — rating mapping e expected inflation:

- **Capítulo 13 — Rating agency landscape.** Big Three + DBRS. S&P/Fitch scale, Moody's scale, DBRS scale tabulados. SONAR common scale 0-21 com mapping completo. Consolidation rules (median, conservative split). Local vs foreign currency ratings. Outlook/watch modifiers. Current sovereign ratings snapshot April 2026 (18 countries). Portugal rating trajectory 2005-2026 tabulada — AA- (2005) → BB (2012) → BBB- (2018) → A- (2024-26). Três criticisms honestos. ECB ratings framework e Portugal's ECB collateral journey. Implications for yield cliff at BBB-.

- **Capítulo 14 — Historical default rates.** Moody's Annual Default Study methodology. Sovereign cumulative default rates 1983-2024 tabulados (Aaa-Caa, 1Y-20Y). Corporate default rates broader universe 1920-2024. Sovereign recovery rates catalog (12 historical defaults — Argentina 2001/2014/2020, Greece 2012, Russia 1998, Venezuela 2017+, Ukraine, Sri Lanka, Lebanon, Zambia). Implied default spread formula PD×LGD. Why market spreads \> actuarial — credit risk premium + liquidity + jump-to-default. Elton et al. 2001 decomposition. Rolling calibration approach. CDS cross-validation current snapshot com 8 countries.

- **Capítulo 15 — Rating-to-spread operational table.** CORE OUTPUT TABLE SONAR — 22 rating notches mapped to default spread ranges (AAA 0-15bps → D N/A). Ghana, Bolivia, Portugal examples. Regional adjustments (EA membership -20%, currency union, oil exporters, hyperinflation wider CI). Historical regime variations (low 2012-2019, normalized 2020-22, tight 2023-24, current 2025-26). Decision tree hierarchy 5-level codeblock. Cross-validation all four approaches. Rating actions and SONAR response.

- **Capítulo 16 — Expected inflation market-based e surveys.** Breakeven inflation formula e sources por country (US TIPS, UK ILGs, EA linkers, Japan limited). Four breakeven caveats (inflation risk premium, liquidity, seasonality, index composition). Inflation swaps — cleaner measure. 5y5y forward inflation swap — critical BC credibility indicator. 5y5y trajectory insights historical. Surveys — SPF, Michigan, ECB SPF, BoE DMP, BOJ Tankan. Survey vs market — when each preferred. Term structure 1Y-30Y sources tabulated. Daily JSON output format.

- **Capítulo 17 — Expected inflation cross-country e Portugal.** Hierarchy 5-level para countries sem linker market. Portugal specifically — como SONAR constrói sem TIPS-like mercado. Computation 5-step (EA aggregate BEI + PT-EA historical diff + BdP projections + INE CPI trend + formula). Example April 2026 detailed (EA 2.20% + 0.15% differential = PT 2.35%). Portugal-specific adjustments (post-Troika normalization, tourism services pressure, productivity). EM treatment (Turkey high-inflation, Argentina hyperinflation, Brazil NTN-B clean, India moderate, China low). Cross-country snapshot April 2026 — 17 países com 1Y/5Y/10Y expected inflation. PPP currency derivation example EUR/BRL 10Y (depreciação implícita 17%). JSON publishing interface completo. Four use cases aplicados. Five limitations honestos.

**O que a Parte V entrega**

93. Rating mapping operacional para 22 notches + conversion cross-agency

94. Rating-to-spread tabela calibrada empiricamente

95. Expected inflation cross-country com hierarquia metodológica

96. Portugal specifically com derivação detalhada

97. PPP-based FX expectation derivation

98. Both outputs in consistent JSON interface

**Material editorial potencial**

99. "Portugal rating journey 2005-2026 — os 20 anos em que saímos do junk"

100. "Moody's Annual Default Study — o que 100 anos de defaults nos ensinam"

101. "Rating-to-spread — quando as agências estão à frente e atrás do mercado"

102. "5y5y forward inflation — o number que Lagarde e Powell vêem primeiro"

103. "Expected inflation PT em 2026 — como SONAR constrói sem TIPS"

104. "PPP implied FX cross-currency — onde estão os big moves 10Y forward"

***A Parte VI — Integração e aplicação (capítulos 18-20)** fecha o manual dos sub-modelos. Cap 18 arquitetura SONAR completa integrando ciclos + sub-models como sistema unificado. Cap 19 use cases práticos — Portuguese equity valuation completa, EM cross-border DCF, arbitrage opportunities, asset allocation signals. Cap 20 caveats honestos across all sub-models + bibliografia anotada Damodaran et al. Fecha a v1 operacional do SONAR — quatro ciclos + cinco sub-models documentados integralmente.*

# PARTE VI
**Integração e aplicação**

*Arquitetura unificada, use cases práticos, caveats e bibliografia — o fecho operacional*

**Capítulos nesta parte**

**Cap. 18 ·** Arquitetura SONAR completa — ciclos e sub-models unificados

**Cap. 19 ·** Use cases práticos — da valuation à coluna editorial

**Cap. 20 ·** Caveats transversais e bibliografia anotada
