# M4 · Financial Conditions Indices

> Sub-índice do Ciclo Monetário — capítulo 10 do manual (Manual_Ciclo_Monetario_COMPLETO).

### 10.1 The concept — monetary stance as asset price summary
Direct measurement of monetary stance (M1-M3) captures BC-instrument level. But final stance felt by economy é mediated by markets — equity prices, bond yields, credit spreads, exchange rates all respond to stance and transmit it to decisions.

A Financial Conditions Index (FCI) is composite measure of how "tight" or "loose" markets are collectively. Combines multiple market variables into single summary. Provides view of stance from asset-price perspective.

**Porque incluir?**

- Captures transmission quality (does policy rate translate to real economic variables?)

- Incorporates non-policy factors affecting stance (risk premia, term premia)

- Easy to compute, update daily, communicate

FCI é complementary to M1-M3, not substitute.

### 10.2 Chicago Fed National Financial Conditions Index (NFCI)
Launched 2011, Chicago Fed NFCI é standard reference.

**Inputs**

105 variables across three categories:

- **Money markets:** rates, spreads, dispersion

- **Debt markets:** yields, spreads, volumes

- **Equity markets:** prices, volumes, volatility

**Methodology**

Principal component analysis extracts common variation. Standardized to zero mean, unit variance. Positive = tighter, negative = looser.

**History**

Chicago Fed publishes weekly since 2011, back-computed to 1971.

**Interpretation**

- NFCI \> 0: financial conditions tighter than average

- NFCI \< 0: looser than average

- NFCI \> +1: notably tight (recession warning zone historically)

- NFCI \< -1: unusually loose (bubble warning)

**Related: Adjusted NFCI (ANFCI)**

Chicago Fed Adjusted NFCI controls for current economic activity. ANFCI \> 0 = tight after controlling for economy. Better measure de pure financial tightness.

> **Nota** *FRED series: NFCI (raw), ANFCI (adjusted).*

### 10.3 Goldman Sachs Financial Conditions Index
Proprietary Goldman Sachs measure, widely followed. Focus on four components:

- Short-term real interest rate

- Long-term real interest rate

- Equity valuations (inverse: equity premium)

- Trade-weighted US dollar

**Methodology**

Weighted combination calibrated to growth effects of each component.

**Advantage**

More forward-looking, closer tie to GDP growth impacts.

**Disadvantage**

Proprietary, not freely available, subject to methodology changes.

### 10.4 Bloomberg Financial Conditions Index
Bloomberg's daily-updated FCI, available via Bloomberg terminals.

**Focus**

Multiple US and international markets. More comprehensive but less economically interpretable.

**Utility**

Real-time, for market monitoring.

### 10.5 IMF Financial Conditions Index
IMF publishes FCI for major economies in Global Financial Stability Report. Quarterly, less real-time, but cross-country comparable.

Useful para o SONAR for non-US countries where national FCIs are scarce.

### 10.6 Constructing a custom FCI for SONAR
For SONAR to have country-specific FCIs (especially for PT, ES, IT where off-the-shelf FCIs are scarce), construct custom.

**Approach**

Weighted combination of standardized components.

**Standard components**

| **Componente**                        | **Peso** |
|---------------------------------------|----------|
| Policy rate ou shadow rate            | 20%      |
| 10Y government bond yield             | 20%      |
| Credit spread (IG ou HY OAS)          | 15%      |
| Equity market valuation (P/E z-score) | 10%      |
| Trade-weighted exchange rate          | 15%      |
| Mortgage rate                         | 15%      |
| Volatility (VIX or equivalent)        | 5%       |

**Standardização**

Cada component z-scored over 10-year rolling window.

**Aggregation**

Weighted sum. Normalize final value to interpretable scale.

**Result**

Custom FCI comparable across countries.

**Para Portugal especificamente**

- DFR ECB (policy)

- 10Y PT sovereign yield

- Spread PT sovereign vs Bund (periphery risk)

- PSI-20 valuation

- EUR trade-weighted

- PT mortgage rate

- VSTOXX (European vol)

### 10.7 FCI as composite signal vs individual components
Important principle: FCI é signal for stance felt by economy, mas components carry own information.

**Example**

- FCI tightening driven by rising rates + spreads = monetary tightening working

- FCI tightening driven by equity crash + spread blowout = financial stress, likely demands easing response

SONAR should track both FCI total e components. Decomposition is informative.

### 10.8 FCI time dynamics — stance evolution
Key behaviors to track:

- **Rapid FCI tightening** (e.g., 1 standard deviation increase em 4 weeks): policy or market shock. Historically predictive of economic slowdown 6-12 months ahead.

- **Persistent FCI looseness** (several years \> -1 SD): potencialmente "easy financial conditions fuel future imbalances". Borio-style concern.

- **Divergence FCI vs policy stance:** FCI loose while M1-M3 suggest tight (or vice versa) signals transmission breakdown.

### 10.9 Implementation in SONAR — M4 layer
For each country:

> M4_FCI_t = standardized FCI value
> M4_FCI_change_12M_t = FCI change over 12 months
> M4_FCI_components_t = breakdown (rates, spreads, equity, FX, vol)

**Classification**

- M4_FCI \> +1: Tight financial conditions

- M4_FCI in \[-1, +1\]: Neutral

- M4_FCI \< -1: Loose financial conditions

- M4_FCI \< -2: Notably loose

**Regime transition flags**

- FCI change \> +1 SD in 3 months: "tightening shock"

- FCI change \< -1 SD in 3 months: "easing shock"

### 10.10 FCI limitations
- **Backward-looking on some components:** equity valuation uses current price / trailing earnings. Not forward-looking.

- **Home-bias:** FCIs constructed for specific countries reflect domestic market characteristics. Global FCIs average countries but lose specificity.

- **Composition drift:** variables in FCI can become less relevant over time as financial structure evolves.

- **Mapping to economy:** FCI moves are meaningful only insofar as they transmit to real activity. This relationship é variable.

**Encerramento da Parte III**

A Parte III entregou o módulo de medição operacional do SONAR-Monetary. Quatro camadas, cada uma capturando dimensão distinta do stance:

- **Capítulo 7 — M1: Shadow rates e effective stance.** Wu-Xia e Krippner methodologies para measuring stance total (rate + QE + forward guidance). Shadow rate vs real rate distinction. Implementation for major BCs e workaround for smaller countries.

- **Capítulo 8 — M2: Taylor Rule gaps.** Original Taylor 1993 formulation e variantes (1999, inertia, forward-looking, financial-augmented). Gap between actual policy e rule-prescribed policy. Historical validation (strong pre-2008, weaker in regime transitions).

- **Capítulo 9 — M3: Market-implied expectations.** Fed funds futures, OIS curves, inflation swaps, policy surprise indices. Discrepancy analysis (market vs BC projections). Key early warning signal in stance classification.

- **Capítulo 10 — M4: Financial Conditions Indices.** NFCI, GS FCI, Bloomberg FCI, IMF FCI. Custom FCI construction for countries without off-the-shelf versions. FCI as composite signal of transmission success.

**Arquitetura de sinais combinados**

- M1 mede current absolute stance

- M2 mede stance relative to rule

- M3 mede expected stance trajectory

- M4 mede stance felt by markets

Combinação dos quatro produces composite monetary stance score (MSC), o equivalente monetário do CCCS do manual anterior. Cap 15 na Parte V agrega estas medições.

**Material de coluna disponível da Parte III**

52. "A shadow rate do ECB em 2020: -7.5% — o que isso significava realmente." Técnico-pedagógico.

53. "O dot plot vs o mercado — onde diverge, algo acontece." Signal interpretação.

54. "Taylor Rule em 2022: Fed atrasou-se em 400bps." Analítica retroactive.

55. "O FCI Português — construído do zero." Original, diferenciador.

56. "Quando o shadow rate de Krippner e Wu-Xia discordam — o que dizem." Técnico-advanced.

***A Parte IV — Transmissão (capítulos 11-14)** é onde a policy passa para a economia real via markets e decisões. Canal de taxa de juro e expectativas, canal de crédito (ponte com manual anterior), canal de asset prices e wealth, e canal de câmbio e spillovers internacionais.*

# PARTE IV
**Transmissão**

*Rates, crédito, asset prices, câmbio — os quatro canais*

**Capítulos nesta parte**

**Cap. 11 ·** Canal de taxa de juro e expectativas

**Cap. 12 ·** Canal de crédito — a ponte com o manual anterior

**Cap. 13 ·** Canal de asset prices e wealth

**Cap. 14 ·** Canal de câmbio e spillovers internacionais
