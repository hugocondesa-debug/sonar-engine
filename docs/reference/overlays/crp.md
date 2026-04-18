# Country Risk Premium

> Overlay L2 — Parte IV · Country Risk Premium do Manual dos Sub-Modelos Quantitativos.

## Capítulo 10 · CDS-based approach e a estrutura do country default risk
### 10.1 Porquê country risk premium
Um investidor americano comprando Apple (US) e Samsung (South Korea) enfrenta profiles de risco diferentes. Samsung tem o risco do negócio mais o risco do país — possibilidade de capital controls, expropriação, instabilidade política, crise cambial, default soberano. Samsung não é apenas "como Apple mas com β diferente" — é Apple mais um layer adicional de risco.

O Country Risk Premium (CRP) captura esse layer. É componente da cost of equity que se adiciona ao mature market ERP quando o ativo está num país não-mature.

> *CRP existe porque risk-free rate "verdadeiro" não é homogéneo globalmente. A 10Y Portuguese government bond não é sem risco no sentido em que a 10Y US Treasury é. A diferença — ajustada por equity vs bond risk — é o CRP.*

**Damodaran framework revisitado**

*Cost of Equity = R_f(mature) + β × ERP(mature) + CRP(country)*

Operacionalmente o CRP é flat-applied (mesmo CRP para todos os beta values do country) ou beta-scaled (CRP × λ, onde λ varia por sector/company). SONAR publishes flat CRP by default; users can apply scaling externally if preferred.

### 10.2 Três abordagens canónicas
Damodaran, Bekaert-Harvey e outros estabeleceram três abordagens principais para medir CRP:

**Approach A — Sovereign default spread**

Diferença entre yield de sovereign bond do país (em USD/EUR) e o risk-free rate equivalente (US Treasury / Bund).

- Captures perceived probability of sovereign default

- Direct market-based observation

- Works best with USD-denominated sovereign bonds (eliminates currency)

**Approach B — Sovereign CDS spread**

Credit Default Swap sobre sovereign debt. Paga em caso de default. Spread é o cost of insurance.

- Cleaner measure of default risk than bond spread (no term premium, no liquidity noise)

- Market-based, daily, for countries with liquid CDS

- Standard: 5Y CDS (most liquid tenor)

- Limited to ~30 countries with liquid CDS

**Approach C — Rating-based default spread**

Map sovereign rating (from S&P, Moody's, Fitch) to implied default spread using historical default rates.

- Available for almost every country

- Less precise than market-based

- Useful when CDS and bond spreads unavailable

- Parte V detalha esta approach

**SONAR hybrid**

SONAR uses:

59. CDS spread when available and liquid (~30 countries)

60. Sovereign bond spread when CDS illiquid (major DM)

61. Rating-based default spread when neither available (frontier markets)

62. Then applies volatility ratio adjustment (Damodaran)

### 10.3 CDS mechanics briefly
Credit Default Swap é contrato derivado onde protection buyer paga periodic premium ao protection seller, em troca de pagamento lump sum caso ocorra credit event sobre reference entity (neste caso, sovereign).

**Key features**

- Tenor: standard 5Y (most liquid), also 1Y, 3Y, 7Y, 10Y

- Currency: USD convention (some in EUR)

- Quoted in basis points per year

- Credit events: failure to pay, restructuring, repudiation/moratorium

- Recovery rate: standard assumption ~40% for sovereigns (recovery after default)

**Default probability implied**

*PD_annual ≈ CDS_spread / (1 − Recovery_Rate)*

With R=40%: 100bps CDS → ~1.67% annual default probability. 500bps → ~8.3% annual. 2000bps (distress) → ~33% annual.

**CDS market liquidity**

- Largest CDS markets: US, Germany, France, UK, Japan, Italy, Spain, Brazil, Mexico, Turkey, China

- Medium liquidity: Portugal, Greece, Ireland, Poland, Hungary, Czech Republic, Russia (pre-2022), South Africa

- Limited liquidity: most frontier markets

- No liquid CDS: many small frontier and low-income countries

### 10.4 SONAR CDS data pipeline
**Primary sources**

- **Markit / IHS Markit (now S&P Global):** industry standard, subscription required

- **Bloomberg Terminal:** CDS page per country, subscription (\$24k/year)

- **Refinitiv Eikon:** equivalent coverage, subscription

- **World Government Bonds:** worldgovernmentbonds.com — free, end-of-day, covers ~45 countries

- **ECB CDS series:** EA countries via ECB SDW (limited historical)

- **DB Research, JPM research:** published CDS reports (free but lag)

**SONAR Tier 1 approach**

For SONAR Tier 1 (pragmatic MVP), use worldgovernmentbonds.com free scrape. Covers 40+ sovereigns. Daily updates. 5Y CDS standard.

> \# Daily CDS scrape pipeline
> import requests
> from bs4 import BeautifulSoup
> def fetch_sovereign_cds_wgb():
> """Scrape sovereign 5Y CDS from worldgovernmentbonds.com"""
> url = "http://www.worldgovernmentbonds.com/sovereign-cds/"
> response = requests.get(url, headers=HEADERS)
> soup = BeautifulSoup(response.content, 'html.parser')
> cds_data = {}
> table_rows = soup.find_all('tr')
> for row in table_rows:
> cols = row.find_all('td')
> if len(cols) \>= 3:
> country = cols\[0\].text.strip()
> cds_5y_bps = parse_bps(cols\[2\].text)
> cds_data\[country\] = cds_5y_bps
> return cds_data

**Countries covered by free CDS sources (typical)**

| **Tier**     | **Countries with liquid 5Y CDS**                                |
|--------------|-----------------------------------------------------------------|
| DM core      | US, Germany, France, UK, Netherlands, Austria, Belgium, Finland |
| DM periphery | Italy, Spain, Portugal, Greece, Ireland                         |
| DM other     | Japan, Canada, Australia, Sweden, Norway, Denmark, Switzerland  |
| EM stable    | Poland, Czech Republic, Hungary, Israel, Chile, Malaysia        |
| EM large     | China, Brazil, Mexico, South Africa, Indonesia, Philippines     |
| EM stressed  | Turkey, Argentina, Egypt, Pakistan, Colombia                    |

### 10.5 Translating CDS to default spread
CDS 5Y em bps é quase directamente o sovereign default spread. Small adjustments para:

- **Basis risk:** CDS-bond spread pode differ modestly (typically 10-30bps)

- **Restructuring clauses:** different CDS contracts (CR, MMR, MR) slightly different

- **Currency:** USD vs EUR CDS pode differ if FX risk significant

- **Tenor:** 5Y is standard; term structure exists but 5Y typically used

**SONAR convention**

- Use 5Y CDS as default_spread directly (minor adjustments ignored for simplicity)

- Document which CDS source and contract type used

- Flag when basis \> 50bps vs sovereign bond spread (anomaly)

### 10.6 Current CDS levels (April 2026)
Representative snapshot — will evolve daily:

| **Country**  | **5Y CDS (bps)** | **Implied PD annual** | **Context**                        |
|--------------|------------------|-----------------------|------------------------------------|
| US           | 28               | 0.47%                 | Benchmark, slightly elevated       |
| Germany      | 9                | 0.15%                 | Very tight                         |
| UK           | 22               | 0.37%                 | Post-fiscal issues                 |
| Japan        | 15               | 0.25%                 | Low despite debt                   |
| France       | 30               | 0.50%                 | Political uncertainty              |
| Italy        | 68               | 1.13%                 | Periphery typical                  |
| Spain        | 42               | 0.70%                 | Improved                           |
| Portugal     | 35               | 0.58%                 | Investment grade, ECB support      |
| Greece       | 85               | 1.42%                 | Improved from crisis but periphery |
| Ireland      | 28               | 0.47%                 | Near core                          |
| Poland       | 55               | 0.92%                 | EM stable                          |
| Brazil       | 180              | 3.00%                 | EM elevated                        |
| Mexico       | 120              | 2.00%                 | EM moderate                        |
| Turkey       | 280              | 4.67%                 | EM stressed                        |
| Argentina    | 1850             | 30.83%                | Distress territory                 |
| China        | 48               | 0.80%                 | Low despite politics               |
| India        | 85               | 1.42%                 | EM good                            |
| South Africa | 205              | 3.42%                 | EM moderate stress                 |

**Observations from snapshot**

- US CDS \>0 reflects post-2024 fiscal concerns

- Germany remains lowest — safe haven

- Portugal CDS 35bps is remarkable — substantial improvement from crisis era (1000+bps in 2012)

- Argentina in distress — near-certain restructuring

- Turkey elevated reflects monetary policy concerns

### 10.7 CDS volatility and extreme periods
**CDS historical trajectory — Portugal**

| **Period** | **Portugal 5Y CDS range** | **Context**                      |
|------------|---------------------------|----------------------------------|
| 2006-2008  | 5-20 bps                  | Pre-crisis, euro convergence     |
| 2008-2010  | 30-150 bps                | Post-GFC concerns                |
| 2011-2012  | 300-1800 bps              | Sovereign debt crisis peak       |
| 2013-2016  | 200-400 bps               | Troika era                       |
| 2017-2020  | 50-100 bps                | Post-Troika recovery             |
| 2021-2023  | 20-60 bps                 | ECB QE support, investment grade |
| 2024-2026  | 25-45 bps                 | Normalized                       |

Portugal CDS trajectory é ilustrativa. CDS spikes durante crisis são fast and dramatic — 1800bps em 2012 = market pricing serious default probability. Recovery também dramatic — back to 30-50bps by 2021.

**CDS spread in crises**

- 2008 GFC: DM CDS 20→150+bps

- 2011-12 EA crisis: periphery CDS 300→1800bps

- 2020 COVID: sharp but brief spike

- 2022 Ukraine/inflation: modest widening

- 2024 (fiscal concerns): US CDS rose notably

### 10.8 CDS and market-implied vs actual
CDS provides market-implied default probability. But defaults actually occur less often than CDS suggest ("credit risk premium" embedded).

**Historical recovery rates**

- Sovereign defaults 1980-2020: ~40% recovery average (varies widely)

- Greece 2012: ~30% recovery (haircut ~70%)

- Argentina 2001, 2014, 2020: varying

- Russia 1998: ~30%

- Venezuela 2017+: near-zero

**Default rates vs CDS predictions**

- Actual defaults 1980-2020: ~1.5% annual for BB-rated sovereigns

- CDS-implied: ~3-5% annual for BB CDS levels

- Difference = credit risk premium (~200-300bps typical)

**SONAR treatment**

- Use CDS as proxy for market's view of credit risk

- Acknowledge contains risk premium beyond pure PD

- Don't "correct" for this — market prices are what matter for CRP

- Investor requires compensation for perceived risk, not actuarial risk

### 10.9 Portugal CDS-based CRP computation
**Step-by-step**

63. Portugal 5Y CDS = 35 bps (April 2026)

64. Subtract US CDS (benchmark mature) = 28 bps

65. Incremental default spread PT = 35 - 28 = 7 bps

66. Alternative: use absolute Portugal CDS as spread = 35 bps

67. Damodaran convention: absolute, not incremental

68. Applied to volatility ratio (see Cap 12) to get CRP

**Portugal default spread = 35 bps**

Por si só, apenas 35bps de default spread parece modest. Mas ajustado por volatility ratio (tipicamente ~1.5x for PT), CRP aproxima 50-60bps. Para um investidor discountando Portuguese equity cash flows, isso é material — representa ~10-15% do total cost of equity.

### 10.10 EM countries — elevated CRPs
**Current estimation (April 2026)**

| **Country** | **5Y CDS** | **Default spread (bps)** | **Est. CRP (w/ vol ratio ~1.5x)** |
|-------------|------------|--------------------------|-----------------------------------|
| Portugal    | 35         | 35                       | ~50-55                            |
| Italy       | 68         | 68                       | ~100                              |
| Spain       | 42         | 42                       | ~63                               |
| Greece      | 85         | 85                       | ~130                              |
| Poland      | 55         | 55                       | ~85                               |
| Mexico      | 120        | 120                      | ~180                              |
| Brazil      | 180        | 180                      | ~270                              |
| Turkey      | 280        | 280                      | ~420                              |
| Argentina   | 1850       | 1850                     | ~2800                             |

These preliminary estimates are refined in Cap 12 where volatility ratios per country are detailed.

### 10.11 CDS caveats
**Caveat 1 — Liquidity variability**

- Small country CDS can be wide-quoted (bid-ask 20-30bps)

- Trades infrequently — observed spread may stale

- SONAR flags illiquid CDS with wider confidence intervals

**Caveat 2 — Political/systemic disconnection**

- CDS can decouple from underlying risk in rare cases

- Speculative activity in stressed EM CDS can amplify/distort

- Russia 2022: CDS effectively disrupted by sanctions

**Caveat 3 — Market manipulation history**

- CDS market had episodes of manipulation

- Largest: JPMorgan "London Whale" 2012 affected corporate CDS

- Sovereign CDS less susceptible but not immune

**Caveat 4 — Survivorship**

- Countries with most stressed CDS often get bailed out or restructure

- CDS provides less insight into tail outcomes (redenomination, capital controls) than default

**Caveat 5 — Contract specification differences**

- CR14 vs CR07 restructuring clauses matter for developing economies

- USD vs EUR CDS different

- SONAR standardizes on USD CDS with CR14 (where applicable) or CR07 (older)

## Capítulo 11 · Sovereign spread approach quando CDS ilíquido
### 11.1 Quando CDS não é suficiente
CDS líquido cobre ~30-40 países. Fora desse universo, SONAR precisa de abordagem alternativa. E mesmo nos países com CDS líquido, o sovereign bond spread fornece validation cross-check valiosa.

Sovereign spread approach usa a diferença de yield entre o sovereign bond do país e o equivalent risk-free benchmark — ajustando por currency e tenor.

> *CDS pricing e bond spread pricing devem convergir em equilíbrio (no-arbitrage). Divergence persistente indica market friction — liquidity premium, repo specialness, regulatory capital treatment. Tracking both allows SONAR to triangulate.*

### 11.2 Sovereign spread definição
Para país com sovereign USD-denominated bonds (tipicamente EMs):

*Spread_USD(country, tenor) = Yield_country_USD(tenor) − Yield_Treasury(tenor)*

Para EA countries (sem USD sovereigns líquidos):

*Spread_EUR(country, tenor) = Yield_country_EUR(tenor) − Yield_Bund(tenor)*

Para UK (GBP), Japan (JPY): use local risk-free benchmark.

**Why USD-denominated preferred for EMs**

- Eliminates currency risk from spread calculation

- Purely reflects credit risk

- Comparable across countries using common numeraire

- Sovereigns with USD debt: Mexico, Brazil, Turkey, Argentina, Indonesia, South Africa, many EMs

**Challenge for local-currency-only sovereigns**

- Some countries issue only local currency

- India primarily (limited USD sovereigns)

- China similar

- Requires separating credit from currency — harder

### 11.3 EMBI and EMBI+
JP Morgan Emerging Market Bond Index (EMBI+) is standard benchmark for EM sovereign USD bonds.

**EMBI structure**

- Weighted index of USD-denominated EM sovereigns

- Multiple variants: EMBI Global, EMBI Global Diversified, EMBIG+

- Countries weighted by issuance size (EMBI Global) or capped (Diversified)

- Spreads published daily

**SONAR uses**

- EMBI Global Diversified as EM aggregate CRP benchmark

- Individual country spreads from EMBIG constituents

- Access via Bloomberg (JPM CEMBRD Index), or published reports

- Free alternative: individual sovereign yields scraped and compared

### 11.4 EA sovereign spreads
EA countries share currency (euro), sharing Bund as risk-free benchmark.

**Methodology**

*Spread_EUR(country) = Yield_EUR_sovereign(country) − Yield_Bund*

**Standard tenors for EA spreads**

- 10Y (most common, benchmark)

- 2Y (monetary policy sensitive)

- 5Y (middle)

**Current snapshot (April 2026)**

| **Country** | **10Y yield (%)** | **vs Bund (bps)** | **5Y CDS** | **Convergence**     |
|-------------|-------------------|-------------------|------------|---------------------|
| Germany     | 2.45              | 0 (benchmark)     | 9          | —                   |
| Netherlands | 2.55              | 10                | 12         | ✓ close             |
| Finland     | 2.58              | 13                | 13         | ✓ close             |
| Austria     | 2.62              | 17                | 15         | ✓ close             |
| France      | 2.75              | 30                | 30         | ✓                   |
| Belgium     | 2.72              | 27                | 22         | ✓ close             |
| Ireland     | 2.68              | 23                | 28         | ≈                   |
| Spain       | 3.18              | 73                | 42         | ↔ spread wider      |
| Portugal    | 3.15              | 70                | 35         | ↔ spread wider      |
| Italy       | 3.85              | 140               | 68         | ↔ spread much wider |
| Greece      | 3.45              | 100               | 85         | ↔ close             |

**Observations**

- Bond spread typically wider than CDS for periphery

- Reflects liquidity premium + term premium

- Italy 140bps spread vs 68bps CDS = 72bps liquidity/risk layer

- Core EA countries (Germany adjacent): spread ≈ CDS

### 11.5 Emerging markets sovereign spreads
Para EMs, sovereign spread via USD-denominated bonds vs US Treasury.

**Current EM snapshot (April 2026, indicative)**

| **Country**  | **USD 10Y yield (%)** | **vs UST 10Y (bps)** | **5Y CDS** | **Basis**              |
|--------------|-----------------------|----------------------|------------|------------------------|
| Poland       | 5.25                  | 100                  | 55         | ~45bps basis           |
| Hungary      | 5.85                  | 160                  | 95         | ~65bps basis           |
| Romania      | 6.45                  | 220                  | 135        | ~85bps basis           |
| Mexico       | 5.95                  | 170                  | 120        | ~50bps basis           |
| Brazil       | 7.25                  | 300                  | 180        | ~120bps basis          |
| Turkey       | 7.95                  | 370                  | 280        | ~90bps basis           |
| South Africa | 7.45                  | 320                  | 205        | ~115bps basis          |
| Indonesia    | 6.15                  | 190                  | 115        | ~75bps basis           |
| Colombia     | 7.25                  | 300                  | 195        | ~105bps basis          |
| Argentina    | 15.45                 | 1120                 | 1850       | inverted (CDS \> bond) |

**Key patterns**

- Bond-CDS basis positive (bond spread \> CDS) in most EMs

- Reflects liquidity premium of cash bonds + term premium

- Argentina inverted — distress, CDS pricing default more aggressively than bond

- SONAR uses CDS when available, bond spread as cross-check

### 11.6 Term structure of country spreads
Country default spread is not flat across tenors.

**Typical term structure**

- Short end (1-2Y): tight — low near-term default risk

- Medium (5-7Y): widening — uncertainty grows

- Long (10-30Y): widest typically

**Exceptions**

- Distressed countries: inverted — highest short end (near-term default probability)

- Argentina historically — 1Y \> 5Y \> 10Y

- Signals imminent default risk

**SONAR convention**

- 5Y as primary tenor for CRP computation

- 10Y as long-term assessment

- Flag inversions as distress indicator

### 11.7 Sources para sovereign spreads
**Primary — Bloomberg Terminal**

- Comprehensive sovereign bond data

- USD and local currency

- Daily updates

- Historical depth

- Cost: \$24k/year

**Alternative — Refinitiv Eikon**

- Similar coverage

- Cost: \$22k/year

**Free alternatives**

- World Government Bonds (worldgovernmentbonds.com) — free, daily, 50+ countries

- Investing.com sovereign rates — free

- TradingEconomics (existing SONAR connector) — paid tier, good coverage

- ECB SDW — EA sovereigns

- FRED — limited sovereign coverage outside US

**SONAR Tier 1 approach**

- TradingEconomics (existing) + WGB scrape (free) = primary

- Bloomberg/Refinitiv if budget available = upgrade

- Gap-fill from individual country data (central bank reports)

### 11.8 Bond-CDS basis trading
Divergence between bond spread and CDS spread creates "basis" — opportunity for arbitrage but also signal for SONAR.

**Basis = Bond spread − CDS spread**

- Positive basis (bond \> CDS): bond market pricing more risk, or liquidity premium in bond

- Negative basis (bond \< CDS): CDS market pricing more risk, or technical pressure on CDS

- Zero basis: theoretical no-arbitrage equilibrium

**What basis tells us**

- **Persistent positive basis:** bond market deeper, CDS participants specialized

- **Widening basis:** stress building, divergence between cash and synthetic markets

- **Negative basis:** usually post-crisis or restructuring scenario

- **Very negative basis:** restructuring near-certain, CDS panicking

**SONAR basis tracking**

- Daily computation basis for all countries with both CDS and bond

- Historical database of basis

- Alert when basis \> 2 std deviations from historical

- Part of financial stability monitoring

### 11.9 Local currency sovereign yields
Para análise em local currency, sovereign yields local são relevantes but differ from USD spreads.

*Local_yield = USD_yield + Expected_FX_depreciation + Currency_risk_premium*

**Example Brazil**

- USD 10Y Brazil sovereign: 7.25%

- BRL 10Y Brazil sovereign: 11.85%

- Difference (460bps): expected BRL depreciation + currency risk premium

- Expected BRL depreciation 10Y: ~350bps (inflation differential)

- Currency risk premium: ~110bps

**When to use local vs USD**

- USD yield: international investor perspective

- Local yield: domestic investor perspective

- Cross-border equity: match to cash flow currency

- SONAR publishes both, user chooses

### 11.10 Implementação SONAR para países sem CDS líquido
**Países Tier 3 scenarios**

- **Frontier markets sem CDS:** Ghana, Kenya, Pakistan, Vietnam — usar bond spread ou rating-based

- **CIS countries:** Kazakhstan, Uzbekistan — mixed availability

- **Caribbean / Central America:** limited CDS, use bond spread when USD-denominated bonds exist

- **MENA:** Gulf states have CDS, some North Africa doesn't

**Decision tree**

> country_default_spread(country):
> \# Priority 1: Liquid CDS available
> if cds_liquid(country):
> return cds_5y_spread(country)
> \# Priority 2: USD-denominated sovereign bonds
> if usd_sovereign_available(country):
> return usd_sovereign_10y_spread(country) - expected_liquidity_premium
> \# Priority 3: Local currency sovereign + FX adjustment
> if local_sovereign_available(country):
> return local_10y_yield(country) - expected_fx_depreciation(country) - us_treasury_10y
> \# Priority 4: Rating-based fallback (Parte V)
> return rating_based_default_spread(country)

### 11.11 SONAR sovereign spread output format
> {
> "date": "2026-04-17",
> "country": "PT",
> "sovereign_spread_analysis": {
> "cds_5y_bps": 35,
> "cds_source": "worldgovernmentbonds.com",
> "cds_liquidity": "moderate",
> "sovereign_bond_10y": {
> "yield_eur_pct": 3.15,
> "risk_free_10y_bund": 2.45,
> "spread_vs_bund_bps": 70
> },
> "basis_bond_minus_cds_bps": 35,
> "basis_historical_avg_bps": 20,
> "basis_alert": "moderately wider than historical",
> "default_spread_canonical_bps": 35,
> "default_spread_methodology": "cds_5y_primary",
> "confidence": 0.85,
> "term_structure_spreads": {
> "2y_bps": 18,
> "5y_bps": 35,
> "10y_bps": 52,
> "shape": "normal_upward"
> }
> }
> }

## Capítulo 12 · Volatility ratio synthesis — operational output per country
### 12.1 De default spread para CRP — o ajustamento Damodaran
Os capítulos 10 e 11 estabeleceram como calcular default spread via CDS ou sovereign bond. Mas default spread não é directly CRP. É default risk associated with sovereign debt, not equity risk.

Damodaran propôs ajustar default spread via volatility ratio:

*CRP = Default_Spread × (σ_equity_local / σ_bond_local)*

Onde σ é volatility relevant to local market. Logic: if equity is more volatile than bonds by factor X, then equity risk premium should be scaled by X relative to bond spread.

> *A intuição Damodaran: sovereign CDS spread mede default risk sobre debt. Equity é subordinate to debt e typically more volatile. Ratio equity-bond volatility scales default spread to equity-relevant risk premium.*

### 12.2 Volatility ratio computation
**Components needed**

- **σ_equity:** annualized volatility of local equity index (e.g. PSI-20, MICEX, BOVESPA)

- **σ_bond:** annualized volatility of local sovereign bond index or individual long bond

- **Window:** 3-5 year rolling

- **Frequency:** daily returns

**Typical volatility ratios**

| **Country category**    | **σ_equity** | **σ_bond** | **Ratio** |
|-------------------------|--------------|------------|-----------|
| Mature DM (US)          | 15%          | 8%         | 1.88      |
| Mature DM (Germany)     | 14%          | 7%         | 2.00      |
| EA periphery (Portugal) | 18%          | 12%        | 1.50      |
| EA periphery (Italy)    | 19%          | 13%        | 1.46      |
| Stable EM (Poland)      | 22%          | 12%        | 1.83      |
| Large EM (Brazil)       | 25%          | 15%        | 1.67      |
| Stressed EM (Turkey)    | 28%          | 18%        | 1.56      |

**Observations**

- Ratio typically 1.3-2.0

- Lower for periphery EA (bonds also volatile due to spread risk)

- Higher for mature DM (bonds stable, equity normal volatile)

- Varies over time — crisis periods compress ratio (both volatile)

### 12.3 Damodaran's standard ratio
Damodaran simplifies by using a standard ratio of ~1.5-1.7x for EMs in his published work, with occasional adjustments. The rationale: volatility measurements are noisy, and a standard multiplier captures the essential relationship.

**SONAR dual approach**

69. Compute country-specific volatility ratio (rigorous, time-varying)

70. Apply Damodaran standard 1.5x if country-specific noisy or data inadequate

71. Publish both — transparent documentation

### 12.4 CRP operational formula
*CRP_country = Default_Spread_country × (σ_equity_country / σ_bond_country)*

**Sequenced computation**

72. Get default spread (Cap 10-11)

73. Get volatility ratio (Cap 12.2)

74. Multiply to get CRP

75. Compute confidence intervals

76. Publish daily

**Example — Portugal April 2026**

> Portugal CRP computation:
> Default spread = 35 bps (CDS 5Y)
> PSI-20 annual volatility (5Y rolling) = 18.2%
> PT sovereign bond volatility (5Y rolling) = 11.8%
> Volatility ratio = 18.2 / 11.8 = 1.54
> CRP_PT = 35 × 1.54 = 53.9 bps
> Confidence interval (wide due to volatility noise):
> CRP_PT range: 42-68 bps
> Alternative (Damodaran standard):
> CRP_PT alt = 35 × 1.5 = 52.5 bps
> Canonical SONAR output: 54 bps
> (arithmetic average rounded, within confidence range)

### 12.5 CRP operational output — 30 countries
SONAR publishes daily CRP for 30+ countries. Indicative snapshot (April 2026):

| **Country**    | **Default spread (bps)** | **Vol ratio** | **CRP (bps)** |
|----------------|--------------------------|---------------|---------------|
| Germany        | 0 (benchmark)            | —             | 0 (mature)    |
| Netherlands    | 3                        | 1.90          | ~6            |
| France         | 21                       | 1.65          | ~35           |
| UK             | 13                       | 1.80          | ~25           |
| US             | 0 (benchmark global USD) | —             | 0 (mature)    |
| Canada         | 5                        | 1.70          | ~9            |
| Australia      | 8                        | 1.75          | ~14           |
| Japan          | 6                        | 1.40          | ~8            |
| Switzerland    | 4                        | 1.85          | ~7            |
| Italy          | 68                       | 1.46          | ~100          |
| Spain          | 42                       | 1.45          | ~61           |
| Portugal       | 35                       | 1.54          | ~54           |
| Greece         | 85                       | 1.55          | ~130          |
| Ireland        | 28                       | 1.40          | ~39           |
| Poland         | 55                       | 1.83          | ~100          |
| Hungary        | 95                       | 1.85          | ~175          |
| Czech Republic | 45                       | 1.60          | ~72           |
| Romania        | 135                      | 1.70          | ~230          |
| China          | 48                       | 1.75          | ~84           |
| India          | 85                       | 2.00          | ~170          |
| South Korea    | 32                       | 1.65          | ~53           |
| Brazil         | 180                      | 1.67          | ~300          |
| Mexico         | 120                      | 1.55          | ~186          |
| Colombia       | 195                      | 1.70          | ~331          |
| Chile          | 75                       | 1.60          | ~120          |
| Peru           | 115                      | 1.65          | ~190          |
| Turkey         | 280                      | 1.56          | ~437          |
| South Africa   | 205                      | 1.80          | ~369          |
| Indonesia      | 115                      | 1.65          | ~190          |
| Egypt          | 380                      | 1.80          | ~684          |
| Argentina      | 1850                     | 1.60          | ~2960         |

**CRP as percentage of expected return**

Portugal CRP de 54bps aplicado a 10-year perspective:

- Typical cost of equity PT (expressed in EUR) ≈ 8.5%

- CRP is 54bps of this = ~6% of cost of equity

- Not trivial but not dominant

Turkey CRP de 437bps:

- Typical cost of equity Turkey (USD terms) ≈ 14%

- CRP is 437bps = ~31% of cost of equity

- Substantial — drives valuation of Turkish equity significantly

### 12.6 CRP temporal dynamics
**How CRP evolves**

- Slow-moving in stable periods

- Jumps during crises

- Compressions during benign periods

- Reflects market's aggregate risk assessment

**Portugal CRP over time**

| **Period**   | **Portugal CRP (bps)** | **Context**                          |
|--------------|------------------------|--------------------------------------|
| 2007         | ~20                    | Pre-crisis, near-zero periphery risk |
| 2012 peak    | ~1500                  | Sovereign debt crisis extreme        |
| 2014         | ~250                   | Troika active                        |
| 2018         | ~120                   | Post-Troika                          |
| 2020 (Covid) | ~80                    | ECB supports                         |
| 2021         | ~45                    | IG rating back                       |
| 2023         | ~60                    | Inflation shock                      |
| April 2026   | ~54                    | Normalized                           |

**Brazil CRP over time**

| **Period**           | **Brazil CRP (bps)** | **Context**                 |
|----------------------|----------------------|-----------------------------|
| 2002 (election fear) | ~1200                | Lula election uncertainty   |
| 2007-2008            | ~200                 | Pre-crisis stability        |
| 2010-2013            | ~150                 | Commodity boom              |
| 2015-2016            | ~500                 | Political crisis, recession |
| 2019-2020            | ~250                 | Pre/Covid                   |
| 2024-2025            | ~280                 | Fiscal concerns             |
| April 2026           | ~300                 | Continuing concerns         |

### 12.7 Regional CRP aggregates
SONAR publishes regional CRP aggregates (equal-weighted or GDP-weighted).

**Regional snapshots**

- **EA mature:** ~20-40bps (Germany, Netherlands, France, Austria)

- **EA periphery:** ~50-130bps (Portugal, Spain, Italy, Greece)

- **DM non-EA:** ~10-25bps (US, UK, Canada, Australia, Japan, Switzerland)

- **CEE (Central/Eastern Europe):** ~75-175bps (Poland, Hungary, Czech, Romania)

- **Latin America:** ~190-330bps (Mexico, Brazil, Colombia, Chile, Peru)

- **Emerging Asia:** ~80-190bps (China, India, Korea, Indonesia, Malaysia)

- **Frontier/Stressed:** ~400-3000bps (Turkey, Egypt, South Africa, Argentina)

### 12.8 CRP in valuation practice
**Cost of equity with CRP**

*k_e(country) = R_f(mature) + β × ERP(mature) + CRP(country)*

Example — Portuguese equity modeled in EUR:

> Portuguese equity (e.g. EDP utility stock):
> R_f (Bund 10Y) = 2.45%
> ERP mature (SONAR US/EA avg) = 5.0%
> β (EDP) = 0.85
> CRP Portugal = 54 bps = 0.54%
> k_e = 2.45% + 0.85 × 5.0% + 0.54%
> = 2.45% + 4.25% + 0.54%
> = 7.24%
> Compare to flat mature market approach (ignoring CRP):
> k_e naive = 2.45% + 0.85 × 5.0% = 6.70%
> CRP adds 54bps to discount rate
> Impact on DCF terminal value: ~10-15% reduction for long-duration cash flows

**Sensitivity demonstration**

- Turkish equity: CRP 437bps = 4.37% on cost of equity

- In Turkey USD DCF: this component essential

- Ignoring CRP systematically overvalues Turkish equity by 30%+

### 12.9 CRP controversies and alternatives
**Alternative A — Flat beta × CRP**

- Multiply CRP by country beta to international equity (usually ~1)

- Small adjustment in most cases

**Alternative B — Lambda exposure**

- Damodaran's lambda — company-specific exposure to country risk

- Export-heavy company in stressed country: lambda \< 1 (benefits offset some country risk)

- Domestic-focused company in stressed country: lambda \> 1 (fully exposed)

- SONAR doesn't publish lambda — too company-specific

- Users can apply externally

**Alternative C — Implied CRP**

- Solve for CRP implied by market prices of country equity vs mature market

- Reverse-engineer

- Alternative view — what market actually prices in

- SONAR may add in v2 methodology

**Alternative D — Ibbotson country premium**

- Historical equity returns country vs mature market

- Backward-looking

- Survivorship issues

- Not SONAR choice

### 12.10 CRP for Portugal — deep dive
**Portugal-specific factors in CRP**

- **EU/EA membership:** structural support limits CRP ceiling

- **ECB TPI (Transmission Protection Instrument):** anti-fragmentation tool limits extreme spread blowouts

- **Rating trajectory:** A- (S&P 2024+) vs BB-/BB+ during crisis

- **Debt trajectory:** declining debt/GDP (~102% 2024) from 2014 peak 132%

- **External balance:** tourism-driven current account surplus supports currency externally

**Portugal-Italy-Spain comparison**

|                       | **Portugal** | **Italy** | **Spain** |
|-----------------------|--------------|-----------|-----------|
| Credit rating (S&P)   | A-           | BBB       | A         |
| 5Y CDS (bps)          | 35           | 68        | 42        |
| 10Y-Bund spread (bps) | 70           | 140       | 73        |
| Vol ratio             | 1.54         | 1.46      | 1.45      |
| CRP (bps)             | 54           | 100       | 61        |
| Debt/GDP (%)          | ~102         | ~140      | ~105      |
| Rating trajectory     | Improving    | Stable    | Stable    |

**Insights**

- Portugal has lower CRP than Italy despite similar debt

- Reflects trajectory + external balance

- Spain remarkably tight — perhaps too tight, watch for widening

- Historical periphery ranking: Greece \> Italy \> Portugal \> Spain

### 12.11 SONAR CRP publishing interface
> {
> "date": "2026-04-17",
> "country": "PT",
> "crp_analysis": {
> "default_spread_bps": 35,
> "default_spread_source": "cds_5y_primary",
> "volatility_components": {
> "equity_vol_annualized_pct": 18.2,
> "equity_index": "PSI-20",
> "bond_vol_annualized_pct": 11.8,
> "bond_instrument": "PT 10Y sovereign",
> "window_years": 5,
> "vol_ratio": 1.54
> },
> "crp_bps": 54,
> "crp_range_bps": \[42, 68\],
> "crp_damodaran_standard_bps": 53, // using 1.5x
> "confidence": 0.85,
> "methodology_version": "v1.3",
> "historical_context": {
> "crp_30day_avg_bps": 56,
> "crp_90day_avg_bps": 55,
> "crp_1y_avg_bps": 52,
> "crp_5y_avg_bps": 75,
> "current_percentile_5y": 35
> },
> "regional_comparison": {
> "ea_periphery_avg_bps": 86,
> "pt_vs_periphery_pct_of_avg": 63 // PT below periphery average
> }
> }
> }

### 12.12 CRP caveats and limitations
**Caveat 1 — Vol ratio noisy**

- 3-5 year rolling windows still subject to regime effects

- Crisis periods compress ratios artificially

- SONAR publishes both country-specific and Damodaran standard

**Caveat 2 — CRP captures country-average risk**

- Doesn't distinguish sector exposure

- Export-oriented companies face different risk than domestic-focused

- Lambda adjustment (Damodaran) would help but too company-specific

- Users apply judgment

**Caveat 3 — Tail risk underestimation**

- CDS and volatility fail to capture true tail events

- Argentine default 2001, 2020 — CDS widened but didn't predict magnitudes

- Russia 2022 — sanctions effectively destroyed asset value beyond CDS

- Framework is useful for normal ranges, imperfect for tails

**Caveat 4 — Currency confusion**

- CRP in USD-denominated analysis: clean

- CRP in local currency: needs separate currency risk premium handling

- SONAR publishes USD-based CRP as default

- Local currency CRP available with separate currency adjustment

**Caveat 5 — Data quality varies**

- CDS for Germany: high quality, liquid

- CDS for Greece: moderate quality

- CDS for Argentina: distressed, less meaningful

- CDS for Egypt: low liquidity, wider quoted

- Confidence intervals reflect this

> *CRP é um dos outputs mais práticamente úteis do SONAR. Para qualquer analista fazendo DCF cross-border, o CRP Portugal vs CRP Turkey vs CRP Brasil determina em grande parte whether investment makes sense. Publicar diariamente este output é value real.*

**Encerramento da Parte IV**

Parte IV completou o segundo output crítico do SONAR sub-models — o Country Risk Premium:

- **Capítulo 10 — CDS-based approach.** Why CRP é necessário para cross-border investing. Três abordagens canónicas (sovereign spread, CDS, rating-based). CDS mechanics — 5Y tenor standard, USD convention, recovery 40% typical, PD implied via spread/(1-R). CDS market liquidity mapping por tier. Pipeline sources (Markit subscription, Bloomberg, worldgovernmentbonds.com free scrape). CDS to default spread translation. Current snapshot April 2026 com 18 países tabulados (US 28, Germany 9, Portugal 35, Italy 68, Turkey 280, Argentina 1850). Portugal CDS historical trajectory 2006-2026 (5bps pre-crisis → 1800bps 2012 → 35bps 2026). CDS vs actual defaults — credit risk premium embedded ~200-300bps. Cinco caveats honestos.

- **Capítulo 11 — Sovereign spread approach.** When CDS insufficient. USD-denominated spread vs UST. EA spread vs Bund. EMBI+ benchmark. EA sovereign current snapshot April 2026 com observations (bond spread typically wider than CDS for periphery). EM sovereign snapshot com USD 10Y yields vs UST (Poland 100bps, Brazil 300bps, Argentina 1120bps). Term structure of country spreads (normal upward, inverted = distress). Sources primary/alternative/free. Bond-CDS basis explanation e tracking for financial stability. Local currency vs USD sovereign yields. Decision tree para países sem CDS líquido. JSON output format completo.

- **Capítulo 12 — Volatility ratio synthesis.** Damodaran adjustment from default spread → CRP via volatility ratio (σ_equity/σ_bond). Typical vol ratios tabulated 1.3-2.0 por country type. Dual approach — country-specific OR Damodaran standard 1.5x. Sequenced computation. Portugal example worked (35 × 1.54 = 54 bps CRP). CRP OPERATIONAL TABLE PARA 30 PAÍSES com default spread, vol ratio e CRP. Temporal dynamics — Portugal CRP 2007-2026 (20 → 1500 → 54), Brazil CRP evolution. Regional aggregates. Cost of equity example Portuguese equity detalhado (CRP adds 54bps = ~6% of cost of equity). Portugal deep dive com factors estruturais (EA membership, TPI, rating trajectory, debt declining, tourism surplus). Comparison Portugal-Italy-Spain tabulada. Quatro alternatives methodologies. JSON publishing interface completo. Cinco caveats honestos.

**O que a Parte IV entrega**

77. CRP para 30+ países com methodology transparente

78. Triangulation CDS / sovereign spread / rating-based

79. Volatility ratio synthesis Damodaran-style

80. Historical context e regional comparisons

81. Portugal deep dive especialmente relevante

82. Output JSON daily operacional

**Material editorial potencial**

83. "CRP Portugal hoje vs 2012 — a jornada de 1500bps a 54bps"

84. "Portugal-Italy-Spain — as três periferias que divergiram"

85. "Turkey CRP 437bps — o que significa para Turkish equity valuations"

86. "Bond-CDS basis — os spreads que divergem e o que isso nos diz"

87. "Cost of equity cross-border em 2026 — framework aplicado a 10 países"

***A Parte V — Rating mapping e Expected inflation (capítulos 13-17)** aborda os últimos dois sub-modelos. Cap 13 rating agency landscape (S&P, Moody's, Fitch, DBRS conversion). Cap 14 historical default rates e rating-to-spread calibration (Moody's Annual Default Study). Cap 15 operational rating-to-spread table SONAR. Cap 16 expected inflation — market-based breakevens, inflation swaps, survey-based. Cap 17 expected inflation cross-country e Portugal specifically without TIPS-like market. Esta parte tem 5 capítulos (vs 3 standard) pela natureza combinada dos dois sub-modelos.*

# PARTE V
**Rating mapping e Expected inflation**

*Rating agency landscape, default rates, spread mapping, expected inflation cross-country*

**Capítulos nesta parte**

**Cap. 13 ·** Rating agency landscape e escala comum

**Cap. 14 ·** Historical default rates e recovery

**Cap. 15 ·** Rating-to-spread operational table

**Cap. 16 ·** Expected inflation — market-based e surveys

**Cap. 17 ·** Expected inflation cross-country e Portugal
