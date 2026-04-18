# NSS Yield Curves

> Overlay L2 — Parte II · Yield curves por país do Manual dos Sub-Modelos Quantitativos.

## Capítulo 4 · Metodologia de construção de yield curves
### 4.1 Yield curve — definição operacional
Yield curve é a relação entre yield to maturity e tenor, para um universo específico de instrumentos (tipicamente títulos soberanos) de emissor idêntico. Para SONAR, o output relevante é a yield curve soberana nominal e real, de overnight a 30 anos, para cada país coberto.

A definição é simples; a implementation é que exige rigor. Raw observations são discretas (titulos emitidos têm maturities específicas) e ruidosas (bid-ask spreads, liquidez heterogénea, on-the-run vs off-the-run premium). Transformar estes observables em curve contínua smooth e arbitrage-free requer metodologia.

> *Uma yield curve não é data — é modelo. A escolha de modelo determina o que a curva "diz". Dois bancos centrais podem ter visões diferentes da curva do Bund no mesmo dia, baseadas em diferentes fitting techniques. SONAR adota standard explícito, documentado, replicável.*

### 4.2 Raw points vs parametric fitting
**Raw yield points**

Lista discreta dos yields observados hoje para cada maturity. Ex: 3M = 4.25%, 6M = 4.15%, 1Y = 4.05%, 2Y = 3.85%, etc.

- Advantage: observável direto, sem transformação

- Disadvantage: apenas existe nos pontos observados

- Disadvantage: gaps (ex. 15Y geralmente absent em US)

- Disadvantage: não permite interpolação teoricamente consistente

- Disadvantage: não decomposição level/slope/curvature

**Parametric fitting**

Fit functional form à observed yields. Mais utilizado: Nelson-Siegel (1987) e Nelson-Siegel-Svensson (1994).

- Advantage: curve contínua em todo o tenor range

- Advantage: level/slope/curvature decomposition natural

- Advantage: sparse output (4-6 parâmetros) permite factor modelling

- Advantage: smooth derivative (relevante para forwards)

- Disadvantage: introduz model error

- Disadvantage: ill-suited a curves com features strongly non-smooth

**Splines**

Cubic splines ou B-splines não-paramétricos. Permite fit essencialmente perfeito aos raw yields.

- Advantage: fit exato aos observed points

- Advantage: flexível

- Disadvantage: no economic interpretation do spline

- Disadvantage: extrapolation além de observed tenors unstable

- Disadvantage: pode produzir arbitrage (ver §4.7)

**SONAR default — NSS**

SONAR usa Nelson-Siegel-Svensson como default. Razões: (1) decomposition level/slope/curvature útil para cycle framework; (2) smooth curve estable; (3) arbitrage-free bajo condições razonables; (4) published methodology de várias BCs (Fed H.15 fitting, ECB, BoE), permitindo cross-validation; (5) parcimonioso (4-6 parameters) facilita factor analysis.

### 4.3 Nelson-Siegel model
Nelson-Siegel (1987) propõe:

*y(τ) = β_0 + β_1 · \[(1−e^(−τ/λ))/(τ/λ)\] + β_2 · \[(1−e^(−τ/λ))/(τ/λ) − e^(−τ/λ)\]*

Onde:

- **y(τ):** yield at tenor τ (em anos)

- **β_0:** long-term level factor (asymptote as τ → ∞)

- **β_1:** short-term / slope factor

- **β_2:** medium-term / curvature factor

- **λ:** decay parameter (controls where curvature peaks)

**Interpretação dos factors**

- **β_0 (level):** shift parallel da curve, captura long-run rate regime

- **β_1 (slope):** diferença entre short e long end, captura BC stance

- **β_2 (curvature):** "hump" em mid-tenors, captura expectations shape

**Limitations**

- Struggles with complex shapes (double-hump, steep curves)

- Can produce negative forward rates occasionally

- Single decay parameter λ limits flexibility

### 4.4 Nelson-Siegel-Svensson extension
Svensson (1994) adiciona termo adicional à formulação:

*y(τ) = β_0 + β_1·f_1(τ,λ_1) + β_2·f_2(τ,λ_1) + β_3·f_3(τ,λ_2)*

Onde f_1, f_2, f_3 são as basis functions e há dois decay parameters (λ_1 e λ_2). O termo adicional β_3·f_3(τ,λ_2) permite curves com dois humps — importante para curves complexas como UK Gilts em alguns períodos.

**NSS é SONAR default**

- Fed, ECB, BoE, BoJ todos publicam NSS-fitted curves

- Cross-validation direta com BC outputs

- 6 parâmetros (β_0, β_1, β_2, β_3, λ_1, λ_2) suficientes para maioria dos shapes

- Arbitrage-free em maioria dos fitted regions

- Smooth derivative — forwards well-defined

**NSS estimation**

> \# Python pseudocode for NSS fitting
> from scipy.optimize import minimize
> def nss_yield(tau, b0, b1, b2, b3, lam1, lam2):
> t1 = tau / lam1
> t2 = tau / lam2
> factor_1 = (1 - np.exp(-t1)) / t1
> factor_2 = factor_1 - np.exp(-t1)
> factor_3 = (1 - np.exp(-t2)) / t2 - np.exp(-t2)
> return b0 + b1 \* factor_1 + b2 \* factor_2 + b3 \* factor_3
> def fit_nss(tenors, yields):
> \# Initial guess based on observed yields
> x0 = \[yields\[-1\], yields\[0\]-yields\[-1\], 0, 0, 1.5, 5.0\]
> \# Optimization
> result = minimize(
> lambda x: np.sum((nss_yield(tenors, \*x) - yields)\*\*2),
> x0,
> bounds=\[(0, None), (None, None), (None, None),
> (None, None), (0.1, 10), (0.1, 30)\],
> method='L-BFGS-B'
> )
> return result.x

### 4.5 Cubic splines — quando e por que
Splines têm caso de uso quando NSS falha em capturar features específicos:

- Curves com multiple turning points

- Curves com sharp breaks (post-pivot periods)

- When academic precision at observed points is critical

- When forwards at very short or very long tenors especially matter

**SONAR approach — dual fitting**

SONAR fita ambos NSS e cubic spline. NSS é o default output. Spline é available quando user pede, e é usado para validation (deviation between NSS e spline fit é diagnostic).

**Smoothing splines**

Alternative: penalized smoothing splines (Waggoner 1997, Anderson-Sleath 2001). Balance between fit-to-observations and smoothness via regularization parameter. Mais flexível que NSS, mais stable que plain splines.

> **Nota** *BoE uses Anderson-Sleath smoothing spline. Fed uses NSS. ECB uses NSS. Both produce similar curves in most regimes. SONAR publishes NSS as default to align with Fed/ECB convention, plus spline as validation overlay.*

### 4.6 Level / slope / curvature — o insight de factor modeling
Litterman e Scheinkman (1991) mostraram via PCA que ~99% da variance das yield curves é captured por três factors orthogonais:

16. Level factor: parallel shift — explica ~80% da variance

17. Slope factor: steepening/flattening — explica ~15% da variance

18. Curvature factor: butterfly moves — explica ~5% da variance

**Correspondência com NSS parameters**

| **PCA factor** | **NSS parameter**   | **Economic meaning**             |
|----------------|---------------------|----------------------------------|
| Level          | β_0 (approximately) | Long-run rate regime             |
| Slope          | β_1 (approximately) | Monetary stance / BC positioning |
| Curvature      | β_2 (approximately) | Mid-term expectations            |

Esta correspondência não é exata (NSS parameters e PCA factors são related não identical), mas é close enough para interpretive purposes.

**Uso by cycle framework**

- **MSC** usa slope (β_1) primarily — yield curve shape indicador stance

- **ECS** usa slope inverted como leading indicator recession

- **CCCS** usa curvature para detect credit cycle transitions

- **FCS** usa level indirectly via term premium decomposition

### 4.7 Bootstrap methodology — zero curve derivation
Observed yields tipicamente são yields on coupon bonds. Zero-coupon yields (aka spot rates) são diferentes — são yields de pure discount bonds pagando apenas no vencimento.

*P_coupon = Σ (C_t / (1+z_t)^t) + (F / (1+z_T)^T)*

Onde z_t é zero rate em tenor t, C_t é coupon, F é face value. Bootstrap é procedure sequencial para extrair z_t de observed coupon bond prices:

19. Start with shortest maturity bond (z_1 direct)

20. Use z_1 to solve z_2 from next bond

21. Continue to solve z_3, z_4, ... sequentially

22. Each step assumes previous zero rates correct

**Bootstrap na prática**

- Sovereigns tipicamente não têm bond em cada tenor — requires interpolation between available points

- SONAR implementation: fit NSS to coupon yields, derive zero rates from NSS

- Alternative: bootstrap raw, fit NSS to zero rates

- Both approaches produce similar results for standard curves

**Arbitrage-free check**

Zero curve arbitrage-free implica forward rates não-negativos (approximately) e monotonic zero rates em most tenors. SONAR checks post-fit.

### 4.8 Forward curves derivation
Forward rate f(t₁,t₂) é o implied rate entre t₁ e t₂:

*(1 + z\_{t₂})^t₂ = (1 + z\_{t₁})^t₁ × (1 + f(t₁,t₂))^(t₂-t₁)*

Forwards são derivables directly do zero curve. Examples relevantes:

- 1y forward 1y — expected 1-year rate one year from now

- 5y5y forward — expected 5-year rate 5 years from now (critical for expected inflation)

- 10y10y forward — expected 10-year rate 10 years from now (long-run expectation)

**SONAR output**

- Publishes forward curves alongside spot curves

- Standard tenors forward: 1y forwards em 1y, 2y, 5y, 10y; 5y5y forward; 10y10y forward

- Daily updates

- Cross-validated against market-implied forwards (where observable)

### 4.9 Real yield curves
Real yield curve é yield ajustado para expected inflation. Dois approaches:

**Approach A — Direct observation via inflation-linked bonds**

- TIPS (US), ILGs (UK), OATi (France), BTP€i (Italy), ILBs (Germany)

- Yield observado é approximately real yield directly

- Available tenors limited by inflation-linked bond issuance

- US: 5Y, 10Y, 30Y TIPS standard

- UK: broader tenor coverage

- Allows direct construction of real NSS curve

**Approach B — Derived from nominal + expected inflation**

*real_yield(τ) = nominal_yield(τ) − expected_inflation(τ)*

- Necessário when inflation-linked bonds não disponíveis

- Ex: Portugal, most EMs, most smaller markets

- Expected inflation tenor-matched (see Parte V)

- Less reliable but available anywhere

**SONAR hybrid**

- US, UK, Germany, Italy, France: Approach A (direct from linkers)

- Portugal, Japan, most EMs: Approach B (derived)

- Clearly labeled in output metadata

### 4.10 Failure modes e caveats
**Failure mode 1 — Illiquid tenors**

Some tenors rarely traded. 20Y Treasury entre 1986-2020 não emitida. Fitted value extrapolated, may deviate significantly from market reality if tradable.

**Failure mode 2 — Regime transitions**

During sharp rate moves, curves re-price rapidly. NSS fitting lag can miss intraday moves of 20-50bps.

**Failure mode 3 — Non-standard curves**

Curves with unusual features (inverted + humped) can't be captured by NSS 4-parameter. Svensson 6-parameter handles better but still fails extreme cases.

**Failure mode 4 — Benchmark vs off-the-run**

On-the-run bonds (most recently issued at each tenor) typically trade at liquidity premium. NSS fits using all bonds blend this. Fed H.15 uses "constant maturity" yields that interpolate official but still blend premium.

**Failure mode 5 — EM sovereign curves**

Emerging market sovereigns often have limited issuance, idiosyncratic pricing. NSS fits less reliable. Wider confidence intervals warranted.

> *Framework sincero sobre failure modes é mais útil que framework claiming universal applicability. Yield curve fitting é estimation problem, not measurement problem.*

## Capítulo 5 · Fontes de dados e implementation per country
### 5.1 Country coverage SONAR
SONAR yield curve coverage mapeia ao universe dos quatro manuais de ciclos. Prioridade vai para os países Tier 1 e Tier 2; Tier 3-4 têm coverage mais limitada e wider confidence intervals.

| **Tier**              | **Países**                                          | **Coverage quality**          |
|-----------------------|-----------------------------------------------------|-------------------------------|
| Tier 1 — full         | US, Germany, UK, Japan, EA aggregate                | Excellent, BC-published       |
| Tier 2 — good         | France, Italy, Spain, Canada, Australia             | Good via own CB or Treasury   |
| Tier 3 — limited      | Portugal, Ireland, Netherlands, Sweden, Switzerland | Via Eurostat/ECB or IGCP      |
| Tier 4 — experimental | China, India, Brazil, Turkey, Mexico                | Limited tenors, less reliable |

### 5.2 US Treasury — the gold standard
**Primary source — Treasury direct**

- \`treasury.gov/resource-center/data-chart-center/interest-rates/Pages/TextView.aspx\`

- Daily Treasury Par Yield Curve Rates

- Constant maturity tenors: 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y

- Atualização daily ~4pm ET

- Free access, XML/CSV available

**Secondary source — FRED**

- **DGS1MO, DGS3MO, DGS6MO, DGS1, DGS2, DGS3, DGS5, DGS7, DGS10, DGS20, DGS30:** Treasury constant maturity at each tenor

- **DFII5, DFII7, DFII10, DFII20, DFII30:** TIPS (real) yields

- **T5YIE, T7YIE, T10YIE, T20YIE, T30YIE:** breakeven inflation

- **T5YIFR, T10YFF:** 5-year, 5-year forward breakeven

**Fed NSS published curves**

- Gurkaynak-Sack-Wright (2007) publish fitted NSS parameters

- Available at \`federalreserve.gov/data/nominal-yield-curve.htm\`

- Excellent cross-validation for SONAR NSS fit

- Daily historical depth back to 1961

**SONAR implementation**

> \# Daily pipeline
> 1. Fetch Treasury par yields (11 tenors) from Treasury.gov
> 2. Fetch TIPS yields (5 tenors) from FRED
> 3. Fit NSS to nominal par yields → β_0, β_1, β_2, β_3, λ_1, λ_2
> 4. Fit NSS to real yields (TIPS)
> 5. Compute zero curve via bootstrap + NSS
> 6. Compute forward curve (1y forwards, 5y5y, 10y10y)
> 7. Store in yield_curves table with methodology='NSS'
> 8. Cross-check against Gurkaynak-Sack-Wright published NSS

### 5.3 German Bund — EA risk-free benchmark
**Primary source — Bundesbank**

- \`bundesbank.de/en/statistics/time-series-databases\`

- Fitted Svensson term structure published daily

- Zero coupon yields available

- Data back to 1972

- XML / CSV download available

**Secondary source — ECB Statistical Data Warehouse**

- Already covered by SONAR ECB connector (v14)

- EA-wide AAA sovereign yield curve

- Germany-specific via Bundesbank

**FRED backup**

- **IRLTLT01DEM156N:** 10Y government bond yield Germany, monthly

- Daily via ECB SDW preferred

**Why Bund é critical**

Bund yield curve serve como risk-free benchmark para todos os EA sovereigns. Spreads vs Bund são core metric para CRP periphery computation. Bund forward curve é primary input para ECB stance inference.

### 5.4 UK Gilts
**Primary source — Bank of England**

- \`bankofengland.co.uk/statistics/yield-curves\`

- BoE publica fitted Anderson-Sleath smoothing spline curves daily

- Nominal, real (from ILGs), inflation expectations

- Historical data back to 1979

- Free download

**ILG market especialmente rico**

- UK has long history of index-linked gilts (since 1981)

- Tenor coverage mais completa que TIPS (3Y to 50Y)

- Best available real yield curve globally

- BoE publishes daily fitted real curve

**SONAR usage**

- Direct fit to Gilt yields

- Cross-validate against BoE Anderson-Sleath output

- Real curve directly from ILG observed yields

- Breakeven inflation UK via (nominal - real) directly

### 5.5 Japan JGBs
**Primary source — Ministry of Finance Japan**

- \`mof.go.jp/english/policy/jgbs/reference/interest_rate/index.htm\`

- Daily JGB yields published

- Tenors: 1Y-40Y

- CSV available

**BoJ complementary data**

- \`boj.or.jp/en/statistics/market/\` — rate data

- BoJ publishes yield curve analyses periodically

- Critical post-YCC exit 2024 for tracking normalization

**JGB specifics**

- Largest sovereign bond market outside US

- Inflation-linked JGBs exist but limited liquidity

- Ultra-long tenors (30Y, 40Y) active

- Post-YCC transition creates unique curve shapes

**SONAR implementation**

- JGB nominal curve NSS-fitted

- Real yield primarily derived (not observed) due to inflation-linked illiquidity

- Special attention to 10Y — the YCC target until 2024

### 5.6 Portugal sovereign
**Primary source — IGCP**

- \`igcp.pt\` — Instituto de Gestão da Tesouraria e do Crédito Público

- Government debt management agency of Portugal

- Daily secondary market yields for Portuguese OT (Obrigações do Tesouro)

- Tenors: 2Y, 5Y, 10Y, 15Y, 30Y standard

**Secondary sources**

- Bloomberg aggregated (requires Terminal)

- Refinitiv (requires subscription)

- ECB SDW — euro area government yields by country

- CBP (Central de Bancos de Portugal) data

**ECB SDW series para Portugal**

- **IRS.M.PT.L.L40.CI.0000.EUR.N.Z:** PT 10Y govt yield monthly

- **Secondary market daily via MTS Portugal platform:** preferred for daily updates

**Portugal-specific challenges**

- Limited number of bond issues compared to core sovereigns

- Liquidity gaps in certain tenors

- Issuance calendar irregular

- NSS fit slightly more unstable than Bund

**SONAR output for PT**

- NSS-fitted curve using IGCP + ECB + MTS data

- Standard tenors 2Y, 5Y, 10Y, 15Y, 30Y

- Interpolation to other tenors (3M, 6M, 1Y, 3Y, 7Y, 20Y)

- Wider confidence intervals than Bund

- Real yield derived (no liquid PT linker market)

### 5.7 Other EA periphery — Italy, Spain, Greece, Ireland
**Italy — BTPs**

- Tesoro Italia issues comprehensive BTP curve

- BTP€i inflation-linked exists — real yields observable

- MTS Italy for secondary market

- Largest EA periphery sovereign market

- ECB SDW excellent coverage

- Italian yields + BTP-Bund spread closely tracked

**Spain — Bonos/Obligaciones**

- Tesoro España data

- Secondary market via SENAF

- BE (Banco de España) publishes daily

- Inflation-linked Bonos exist but limited

**Greece — GGB**

- Historical volatility during sovereign crises

- Post-2018 much more stable

- HDAT for secondary market data

- ECB SDW coverage

**Ireland — Irish gilts**

- NTMA (National Treasury Management Agency)

- Smaller market but liquid in benchmark tenors

**Common SONAR approach for EA periphery**

- NSS fit per country

- Spread vs Bund tracked explicitly (critical for CRP)

- Cross-validation with ECB SDW

- Update daily

### 5.8 Canada, Australia, other DM
**Canada**

- Bank of Canada publishes daily yield curve

- \`bankofcanada.ca/rates/interest-rates/\`

- Real Return Bonds (RRBs) allow direct real yield

- Tenors 2Y-30Y well covered

**Australia**

- RBA publishes daily

- \`rba.gov.au/statistics/tables/\`

- Treasury Indexed Bonds (TIBs) for real yield

- Coverage up to 20Y typical

**Switzerland**

- SNB publishes yield curve

- \`snb.ch/en/iabout/stat/statpub/zirepo/id/statpub_zirepo_current\`

- Negative rates extensively historical

- Useful reference for global negative rate analysis

**Sweden, Norway, Denmark**

- Each CB publishes daily

- Riksbank (Sweden), Norges Bank (Norway), Nationalbanken (Denmark)

- Norway especially interesting — oil wealth fund affects curve

### 5.9 Emerging markets — experimental tier
**China**

- China Central Depository & Clearing

- PBOC publishes benchmark curves

- Local currency (CGB) primary

- US-dollar sovereign bonds also tradeable

- Bloomberg/Refinitiv preferred for comprehensive data

**India**

- RBI publishes daily

- Large domestic bond market

- G-Sec yields via CCIL (Clearing Corporation of India)

- Tenors 3M-30Y

**Brazil**

- Brazilian Treasury (Tesouro)

- Multiple instrument types: LTN, NTN-F, NTN-B (inflation-linked)

- NTN-B especially rich real yield data (rare for EM)

- ANBIMA publishes reference rates

**Turkey**

- Türkiye Cumhuriyet Merkez Bankası (CBRT)

- Extreme volatility periods require special handling

- Linker market via TÜFE-endeksli

**EM curve challenges**

- Limited issuance in certain tenors

- Currency volatility creates measurement noise

- Political risk spikes create discontinuities

- NSS fits less stable

- SONAR applies wider confidence intervals

- Updates less reliable

### 5.10 Swap curves as alternative
Em alguns casos, swap curves são mais liquid que sovereign curves. Especially relevant para short and intermediate tenors.

**Swap curves for:**

- EUR: OIS (€STR-based) + EURIBOR swaps

- USD: SOFR swaps (post-LIBOR)

- GBP: SONIA swaps

- JPY: TONAR swaps

- CHF: SARON swaps

**Uso no SONAR**

- Cross-validation com sovereign curves

- Short-end benchmark (OIS typically cleaner que T-bill)

- Swap-sovereign spread é risk indicator

- OIS curves especially clean — benchmark for risk-free

### 5.11 Data pipeline architecture
> SONAR Yield Curve Data Pipeline
> Daily 06:00 Lisbon:
> - Fetch previous day's close data from all Tier 1/2 sources
> - NSS fit per country (10-15 countries)
> - Bootstrap to zero curves
> - Derive forward curves
> - Store in yield_curves table
> Daily 09:00 Lisbon (post-EU open):
> - Refresh EA / UK / CH curves with morning data
> - Update MSC yield curve inputs
> Daily 16:00 Lisbon (post-US open):
> - Refresh US / CA curves with early afternoon data
> - Update cross-validation against Fed H.15
> Schedule:
> - Near real-time: not required for SONAR's use case
> - End-of-day quality: essential
> - Historical backfill: 20+ years for Tier 1, 10+ for Tier 2
> Validation:
> - Cross-check NSS fit against BC-published NSS (Fed, Bundesbank)
> - Flag fits with RMSE \> 5bps
> - Flag forward rates that imply negative rates \>1Y out
> - Flag curves with unusual shapes (multi-hump)

## Capítulo 6 · Outputs operacionais — spot, forward, zero, real
### 6.1 O conjunto de outputs
Cada country coverage produz um conjunto de outputs consolidados diariamente. Standard tenors cobrem overnight até 30 anos, com focus em tenors mais commonly used para valuation e analysis.

**Standard tenor grid**

- Overnight (aproximada pela policy rate ou €STR/SOFR)

- 1M, 3M, 6M (money market)

- 1Y, 2Y, 3Y, 5Y, 7Y (intermediate)

- 10Y, 15Y, 20Y, 30Y (long-term)

**Output families**

23. **Spot yield curve:** yields observados (fitted NSS) em cada tenor

24. **Zero yield curve:** zero coupon equivalents via bootstrap

25. **Forward curve:** implied forwards em tenors key

26. **Real yield curve:** inflation-adjusted via linkers ou derived

27. **Swap yield curve:** OIS/SOFR-based where relevant

### 6.2 Spot curve output
**Format**

> {
> "country": "PT",
> "date": "2026-04-17",
> "curve_type": "sovereign_nominal_spot",
> "methodology": "NSS_v1.2",
> "parameters": {
> "beta_0": 3.85,
> "beta_1": -1.20,
> "beta_2": 1.50,
> "beta_3": -0.80,
> "lambda_1": 1.5,
> "lambda_2": 8.5
> },
> "fitted_yields": {
> "3M": 2.68,
> "6M": 2.74,
> "1Y": 2.82,
> "2Y": 2.95,
> "3Y": 3.05,
> "5Y": 3.18,
> "7Y": 3.25,
> "10Y": 3.35,
> "15Y": 3.55,
> "20Y": 3.70,
> "30Y": 3.78
> },
> "fit_quality": {
> "rmse_bps": 3.2,
> "max_deviation_bps": 5.8,
> "observations_used": 11
> },
> "confidence": 0.88
> }

**Consumption**

- Cycle framework: MSC uses slope, ECS uses 10Y-2Y inversion

- Sub-models: ERP computation uses 10Y risk-free, CRP uses spread vs Bund

- Standalone use: bond valuation, DCF discount rates

### 6.3 Zero curve output
Zero curve é o set de zero-coupon yields em cada tenor. Derived via bootstrap from spot curve. Usado para pricing arbitrary cash flow streams.

**Format**

> {
> "country": "PT",
> "date": "2026-04-17",
> "curve_type": "sovereign_zero",
> "zero_rates": {
> "3M": 2.68,
> "6M": 2.73,
> "1Y": 2.81,
> "2Y": 2.93,
> "5Y": 3.15,
> "10Y": 3.28,
> "30Y": 3.72
> },
> "methodology": "NSS_bootstrap",
> "linked_spot_curve_id": "PT_2026-04-17_NSS"
> }

**Properties**

- Zero rates \< coupon rates tipicamente (reinvestment risk absent)

- Small differences for short tenors, meaningful for long tenors

- Used primarily for technical valuation work

### 6.4 Forward curve output
**Standard forward tenors**

| **Forward tenor** | **Notation** | **Meaning**                       |
|-------------------|--------------|-----------------------------------|
| 1Y in 1Y          | 1y1y         | 1-year rate starting in 1 year    |
| 1Y in 2Y          | 1y2y         | 1-year rate starting in 2 years   |
| 1Y in 5Y          | 1y5y         | 1-year rate starting in 5 years   |
| 5Y in 5Y          | 5y5y         | 5-year rate starting in 5 years   |
| 10Y in 10Y        | 10y10y       | 10-year rate starting in 10 years |
| 3M in 6M          | 3m6m         | 3-month rate starting in 6 months |

**5y5y especialmente crítico**

5y5y forward inflation expectation é canonical BC credibility indicator. SONAR computes daily via:

*5y5y_forward_BE = (10y_BE × 10 − 5y_BE × 5) / 5*

Onde BE é breakeven inflation. Similarly for rates. This is one of the most watched numbers in global finance.

**Format**

> {
> "country": "US",
> "date": "2026-04-17",
> "curve_type": "nominal_forwards",
> "forwards": {
> "1y1y": 3.85,
> "1y2y": 3.75,
> "1y5y": 3.60,
> "5y5y": 3.55,
> "10y10y": 3.50
> },
> "breakeven_inflation_forwards": {
> "5y": 2.35,
> "10y": 2.42,
> "5y5y": 2.49
> }
> }

### 6.5 Real yield curve output
**Countries with direct real yield observation**

| **Country** | **Linker instrument** | **Tenors observable** | **Depth**           |
|-------------|-----------------------|-----------------------|---------------------|
| US          | TIPS                  | 5Y, 7Y, 10Y, 20Y, 30Y | Deep, liquid        |
| UK          | ILGs                  | 3Y-50Y                | Deepest real market |
| Germany     | ILBs                  | 5Y, 10Y, 15Y, 30Y     | Moderate            |
| Italy       | BTP€i                 | 5Y, 10Y, 15Y, 30Y     | Moderate            |
| France      | OATi                  | 5Y, 10Y, 20Y, 30Y     | Moderate            |
| Canada      | RRBs                  | 5Y, 10Y, 30Y          | Small               |
| Australia   | TIBs                  | 5Y, 10Y, 20Y          | Small               |

**Derived real yields for others**

- Portugal, Japan, Spain, most EMs

- Real = nominal − expected_inflation

- Tenor-matched: 10Y real PT = 10Y nominal PT − 10Y expected inflation PT

- Less reliable but available anywhere

- Wider confidence intervals marked

**Format**

> {
> "country": "US",
> "date": "2026-04-17",
> "curve_type": "real_yield_curve",
> "methodology": "direct_from_TIPS",
> "real_yields": {
> "5Y": 1.85,
> "7Y": 1.92,
> "10Y": 2.02,
> "20Y": 2.18,
> "30Y": 2.25
> },
> "breakeven_inflation_implied": {
> "5Y": 2.30,
> "7Y": 2.38,
> "10Y": 2.45,
> "20Y": 2.48,
> "30Y": 2.45
> }
> }

### 6.6 Swap curves output
**Why include swap curves**

- OIS curves são cleaner risk-free em short-end

- Swap spreads over sovereign indicate banking risk

- Post-LIBOR cessation, RFR swaps (SOFR, €STR, SONIA) são standard

- Liquidity often higher than equivalent sovereign in certain tenors

**Standard swap curves SONAR**

- USD: SOFR OIS (overnight), SOFR swaps (1Y-30Y)

- EUR: €STR OIS, EURIBOR swaps (LIBOR alternatives)

- GBP: SONIA OIS, SONIA swaps

- JPY: TONAR OIS

- CHF: SARON OIS

**Swap spread tracking**

*swap_spread(τ) = sovereign_yield(τ) − swap_rate(τ)*

Negative or compressed swap spreads indicate banking stress or collateral shortage. Tracked as financial stability indicator.

### 6.7 Output delivery schema
**Database schema**

> CREATE TABLE yield_curves (
> id INTEGER PRIMARY KEY AUTOINCREMENT,
> country_code TEXT NOT NULL,
> date DATE NOT NULL,
> curve_type TEXT NOT NULL, -- sovereign_nominal, sovereign_real, swap, zero
> methodology TEXT NOT NULL, -- NSS_v1.2, spline_v1, etc.
> nss_params JSON, -- β_0, β_1, β_2, β_3, λ_1, λ_2
> fitted_yields JSON, -- {"3M": 2.68, "6M": 2.74, ...}
> fit_rmse_bps REAL,
> fit_max_deviation_bps REAL,
> observations_count INTEGER,
> confidence REAL,
> source TEXT,
> updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
> UNIQUE(country_code, date, curve_type, methodology)
> );
> CREATE TABLE yield_curve_forwards (
> id INTEGER PRIMARY KEY AUTOINCREMENT,
> country_code TEXT NOT NULL,
> date DATE NOT NULL,
> curve_type TEXT NOT NULL,
> forwards JSON, -- {"1y1y": 3.85, "5y5y": 3.55, ...}
> breakeven_forwards JSON,
> updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
> UNIQUE(country_code, date, curve_type)
> );
> CREATE INDEX idx_yc_country_date ON yield_curves(country_code, date);
> CREATE INDEX idx_yc_type_date ON yield_curves(curve_type, date);

**API endpoints (internal SONAR)**

- GET /yc/{country}/latest → latest curves all types

- GET /yc/{country}/{date} → curves on specific date

- GET /yc/{country}/{date}/{tenor} → single yield

- GET /yc/{country}/history/{tenor}/{start}/{end} → time series

- GET /yc/forwards/{country}/latest → all forwards

### 6.8 Update frequency e freshness
| **Country tier**              | **Update frequency** | **Latency after market close** |
|-------------------------------|----------------------|--------------------------------|
| Tier 1 (US, DE, UK, JP)       | Daily                | 1-2 hours                      |
| Tier 2 (EA periphery, CA, AU) | Daily                | 2-4 hours                      |
| Tier 3 (PT, smaller DM)       | Daily                | 4-6 hours                      |
| Tier 4 (EM)                   | Daily where possible | Same-day or next-day           |

**Freshness metadata**

- Every output tagged with data_as_of timestamp

- Users can filter for freshness

- Stale curves flagged explicitly

### 6.9 Validation framework
**Internal validation**

- NSS fit RMSE \< 5bps in most cases

- Forward rates non-negative in overwhelming majority

- Zero curve monotonic in most periods

- Historical continuity — no jumps \> 100bps day-to-day except on major policy dates

**External cross-validation**

- US: SONAR NSS vs Fed Gurkaynak-Sack-Wright

- Germany: SONAR NSS vs Bundesbank Svensson

- UK: SONAR NSS vs BoE Anderson-Sleath

- Cross-validation agreement typically \< 10bps at all tenors

**Sanity checks**

- Spread Bund-Bund = 0 always

- Spread PT-Bund \> 0 in calm periods, widens in stress

- 10Y \> 2Y in normal periods (positive slope)

- Real yields \> -3% in DM, \> -5% in stress

- Inflation expectations 5y5y anchored near BC targets in stable regimes

### 6.10 Historical depth
| **Country** | **Historical depth available**   |
|-------------|----------------------------------|
| US          | 1961 (Fed Gurkaynak-Sack-Wright) |
| Germany     | 1972 (Bundesbank)                |
| UK          | 1979 (BoE)                       |
| Japan       | 1984 (JGB market)                |
| France      | 1989 (OAT market)                |
| Italy       | 1991 (BTP market)                |
| Portugal    | 1998 (post-euro convergence)     |
| Other EA    | Varies, mostly 1990s+            |
| Canada      | 1986                             |
| Australia   | 1992                             |
| China       | 2002 (CGB market maturity)       |
| Brazil      | 1996                             |

**Historical backtest value**

- 60+ years US history covers most rate regimes

- 50+ years Germany covers Bretton Woods aftermath

- Multiple monetary policy cycles tested

- Inflation regime changes (1970s, 2020s)

- ZLB periods (Japan 1999+, US/EA 2008+, 2020+)

### 6.11 Consumption by SONAR cycle framework
**Monetary Cycle (MSC)**

- Yield curve slope (10Y-2Y) — primary stance indicator

- 2Y yield — proxy for BC rate expectations

- 5y5y forward — credibility anchor assessment

- Yield curve shape changes over time — policy response

**Economic Cycle (ECS)**

- 10Y-3M spread — canonical US recession predictor

- 10Y-2Y in EA — comparable signal

- Curve inversion depth and duration

- Real yields — growth expectation proxy

**Credit Cycle (CCCS)**

- Swap spreads — banking risk

- Sovereign spreads vs risk-free — sovereign credit risk

- Curvature factor — mid-cycle transitions

**Financial Cycle (FCS)**

- Risk-free rate level — valuation discount factor

- Real yields — equity valuation input

- Term premium decomposition — risk-taking metric

### 6.12 Consumption by sub-models (self-referential)
**ERP sub-model uses yield curves**

- 10Y nominal risk-free — ERP denominator

- 10Y real risk-free — real ERP computation

- Forward rates — multi-period ERP projections

**CRP sub-model uses yield curves**

- Spread vs mature benchmark (Bund for EA, Treasury for global USD)

- Short end for FX-hedged comparisons

- Long end for strategic CRP

**Rating-to-spread uses yield curves**

- Calibration: observed spreads vs rating = implied default probability

- Historical backtest: did spreads predict subsequent defaults?

**Expected inflation uses yield curves**

- Nominal - real = breakeven inflation

- Forward breakevens = expected inflation path

- 5y5y forward = anchor assessment

> *Yield curves são foundation layer de todos os outputs SONAR. Accuracy aqui propaga em accuracy everywhere downstream. Por isso o rigor metodológico é non-negotiable.*

**Encerramento da Parte II**

Parte II estabeleceu a metodologia, fontes e outputs operacionais dos yield curves por país:

- **Capítulo 4 — Metodologia.** Raw points vs parametric fitting vs splines. Nelson-Siegel original (1987) com formula completa. Nelson-Siegel-Svensson extension (1994) com 6 parâmetros. SONAR default é NSS alinhado com Fed, ECB, BoE convention. Cubic splines como backup/validation. Level/slope/curvature decomposition via PCA (Litterman-Scheinkman 1991) e correspondência com NSS parameters. Bootstrap methodology para zero curves. Forward curves derivation. Real yield curves duas abordagens (direct via linkers vs derived via nominal - expected inflation). Failure modes honestos — illiquid tenors, regime transitions, non-standard shapes, EM curves.

- **Capítulo 5 — Fontes de dados per country.** Coverage mapping aos 15+ países SONAR. US Treasury (Treasury.gov + FRED + Fed NSS). German Bund (Bundesbank + ECB SDW). UK Gilts (BoE Anderson-Sleath + ILGs best real market globally). Japan JGBs (MoF + BoJ, post-YCC transition). Portugal sovereign (IGCP + ECB SDW + MTS Portugal) com specific challenges (limited issuance, liquidity gaps, NSS slightly unstable). Italy (BTPs + BTP€i), Spain, Greece, Ireland. Canada (RRBs), Australia (TIBs), Switzerland (negative rates histórico). China, India, Brazil (NTN-B rich), Turkey (extreme volatility). Swap curves alternativas (SOFR, €STR, SONIA). Data pipeline architecture diária.

- **Capítulo 6 — Outputs operacionais.** Standard tenor grid (overnight a 30Y, 11 tenors). Cinco output families: spot / zero / forward / real / swap. Format completo em JSON para cada. Forward tenors standard incluindo o crítico 5y5y para BC credibility. Real yield com tabela de countries com linkers directos vs derived. Swap curves pós-LIBOR. Database schema SQL para yield_curves + yield_curve_forwards tables. API endpoints internos. Update frequency tier-based. Validation framework (RMSE \< 5bps, cross-validation vs BC NSS). Historical depth tabulado (60 anos US, 50 anos Germany). Consumption mapping pelos ciclos e pelos outros sub-models.

**Outputs essenciais da Parte II**

28. NSS methodology documentada e replicável

29. Coverage de 15+ países com tier-based quality

30. Cinco output families daily (spot, zero, forward, real, swap)

31. Validation vs BC-published NSS

32. Consumption clara pelos ciclos e sub-models

**Material editorial potencial**

33. "A curva PT do IGCP vs a curva PT derivable do SONAR — que differences importam?"

34. "Level, slope, curvature: as três dimensões que explicam 99% das yield curves"

35. "5y5y forward inflation — o number que o BCE vê primeiro"

36. "BoE's Anderson-Sleath vs Fed's NSS — duas philosophias de yield curve fitting"

37. "Real yields Portugal em 2026 — tradução do framework SONAR"

***A Parte III — ERP diária computada (capítulos 7-9)** aborda a primeira grande inovação do SONAR sub-models: calcular Equity Risk Premium diariamente, substituindo a publicação mensal do Damodaran. Cap 7 implied ERP theory — Gordon growth model, DCF approach, earnings yield approach. Cap 8 implementation técnica com S&P 500 + analyst estimates + buyback-adjusted payout + growth assumptions e análogos para mercados EA/UK/Japan. Cap 9 validation — contra Damodaran monthly, contra historical ERP, backtest de signal quality para market timing.*

# PARTE III
**ERP diária computada**

*Implied ERP theory, implementação S&P 500 e análogos, validação*

**Capítulos nesta parte**

**Cap. 7 ·** Teoria do implied Equity Risk Premium

**Cap. 8 ·** Implementação técnica — S&P 500 e análogos

**Cap. 9 ·** Validação e signal quality
