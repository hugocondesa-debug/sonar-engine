# M3 · Market-implied expectations

> Sub-índice do Ciclo Monetário — capítulo 9 do manual (Manual_Ciclo_Monetario_COMPLETO).

### 9.1 Porque importam as expectations
Até agora medimos stance atual (M1) e stance vs rule (M2). Mas stance monetária é parcialmente forward-looking — o que importa para a economia real não é apenas onde está rate hoje, mas a trajetória esperada de rates nos próximos 12-24 meses.

A Woodford insight (Parte I Cap 2.5) é central: um BC que "commits" credibly a manter rates low for 2 anos tem effect similar a cortar rate hoje, mesmo sem mudar rate atual. Inversely, um BC que sinaliza hiking futuro aperta stance today via long rates, mesmo sem mudar short rate.

> *A medição do stance esperado é feita via market-implied expectations — derived from prices de financial instruments que embed future rate paths.*

### 9.2 Fed funds futures — o baseline para US
Fed funds futures são contratos futures cujo payout depende da fed funds rate average durante o mês do contrato. CME trades futures for próximos 24 meses.

**Mecânica básica**

- Current month contract: tracks realized fed funds rate

- Future month contracts: track expected fed funds rate

- Price quote: 100 - implied rate. If Dec 2026 fed funds futures trades at 95.75, implied rate is 4.25%

**Advantages**

- Highly liquid — virtually no price distortion from limited trading

- Daily pricing, real-time indication of market expectations

- Continuous history since 1988

- Directly interpretable: "market expects Fed funds at X% in December"

**CME FedWatch Tool**

Aggregates fed funds futures prices into implied probabilities of rate changes at each FOMC meeting. Widely followed.

**Limitations**

- Only covers ~24 months forward

- Embedded term premium confounds "pure expectations"

- Risk premium can drive wedge between market expectations and futures prices

For longer horizons, use OIS curve.

### 9.3 OIS curves — the instrument for medium-term expectations
Overnight Indexed Swaps (OIS) are swaps where one party pays fixed rate, the other pays geometrical average of overnight rate during the swap period.

**OIS references por BC**

- **US:** OIS referencing SOFR (Secured Overnight Financing Rate), published by NY Fed since 2018. Historical OIS used fed funds reference pre-2022.

- **EA:** €STR (Euro Short-Term Rate), published by ECB since 2019. Historical swaps used EONIA pre-2022.

- **UK:** SONIA (Sterling Overnight Index Average).

- **Japan:** TONA (Tokyo Overnight Average).

OIS curves extend to 10Y or longer. Provide market expectations of overnight rate across horizons.

**Key metrics para o SONAR**

- 1Y OIS rate: expected average overnight rate over next 12 months

- 2Y OIS rate: expected over 24 months

- 2Y vs current: how much hiking/cutting market prices?

**Example for Fed (April 2026)**

> Current fed funds: 4.375% (midpoint)
> 1Y OIS: 4.00% (market prices 37.5bps cutting over 12 months)
> 2Y OIS: 3.75% (market prices 62.5bps cutting over 24 months)
> Interpretation: market expects gradual easing cycle

### 9.4 Inflation-indexed instruments — expectations of real path
Real policy stance depends on real rates, not nominal. Nominal expectations (fed funds futures, OIS) tell only part of story.

**Inflation swaps**

Provide inflation expectations at various horizons. Most liquid: 5Y5Y forward inflation swap — inflation expectation over years 6-10 starting today.

**Inflation-indexed bonds**

TIPS for US, ILBs for UK, BTPi for Italy, Linkers for multiple:

- Yield difference between nominal and inflation-indexed bonds = breakeven inflation

- Provides market inflation expectations

- Most reliable at 5Y and 10Y maturities

**Para o SONAR**

> nominal_1Y_OIS_t = 1Y OIS rate
> breakeven_inflation_1Y_t = 1Y inflation swap rate
> real_1Y_OIS_t = nominal_1Y_OIS_t - breakeven_inflation_1Y_t

Real expected rates are what matter for real economic decisions.

### 9.5 O FOMC "dot plot" — Fed's own projections
Fed publishes Summary of Economic Projections (SEP) four times a year (after FOMC meetings in March, June, September, December). Includes dot plot — each FOMC participant's projection of appropriate fed funds rate at year-end for next 3 years + longer run.

**Utilidade**

- Shows explicit intent of policy committee

- Range of dots reveals internal disagreement

- Evolution across SEPs tracks shifting committee view

**Reading the dots**

- Median dot: typical forecast

- Range of dots: uncertainty

- Dispersion of dots: internal consensus (tight = agreement; wide = disagreement)

**April 2026 latest SEP (March 2026)**

- End 2026 median: 4.00% (implies 37.5bps cuts over next 8 months)

- End 2027 median: 3.50%

- Longer-run median: 3.00% (higher than pre-2020 estimates around 2.5%)

- Range end-2026: 3.50% to 4.50%

ECB doesn't publish equivalent. Does publish rate projection plots occasionally but less formalized. BoE publishes "conditioning path" in Monetary Policy Reports.

### 9.6 Discrepancy analysis — market vs BC projections
A critical signal for SONAR: when market-implied expectations diverge from BC's own projections, something interesting is happening.

**Two flavors of discrepancy**

***Market more dovish than Fed dots***

- Interpretation: market believes Fed will eventually capitulate, cut faster than Fed says

- Historical pattern: often happens late in hiking cycles

- Signal: potential policy turning point

***Market more hawkish than Fed dots***

- Interpretation: market believes Fed is behind the curve, will have to hike more

- Historical pattern: often happens during inflation shocks

- Signal: credibility stress

**Recent example**

Q1 2022 — Fed's March SEP showed gradual hiking path. Market pricing showed much more aggressive path. Market was right — Fed accelerated aggressively after March meeting.

> **Nota** *For SONAR: track gap between 2Y OIS and Fed 2Y dot median. Large gap is early warning.*

### 9.7 Policy surprise indices
A specialized approach: measure unexpected component of monetary policy via instrument price moves around FOMC announcements.

**Methodology**

Calculate change in 3M-ahead fed funds futures prices in narrow window (30 minutes) around FOMC announcement. Change reflects pure policy surprise (markets already priced expected decision before announcement).

**Literature foundations**

- Kuttner (2001) pioneered

- Refined por Gürkaynak-Sack-Swanson (2005, 2007)

- Major literature

**Decomposition into factors**

- **Target surprise:** unexpected rate decision itself

- **Path surprise:** unexpected forward guidance (future rate path)

- **Action surprise:** unexpected QE or balance sheet news

For SONAR: policy surprises on decision days are high-information events. SONAR should log these and treat as regime change markers if surprises exceed ±20bps.

### 9.8 Implementation in SONAR — M3 layer
> M3_expected_path_t = 1Y OIS rate - current policy rate
> M3_path_deviation_vs_BC_t = 1Y OIS - BC 1Y projection
> \# Real metrics
> M3_real_expected_path_t = real 1Y OIS (nominal - inflation breakeven)
> M3_expected_real_neutral_t = M3_real_expected_path_t - r_star_t
> \# Policy surprise
> M3_recent_surprise_t = policy surprise on last decision day

**Classification overlays M1 and M2**

- If M1 shows Tight stance AND M3 shows market expects cutting: transition to Neutral

- If M1 shows Accommodative AND M3 shows market expects hiking: transition to Tight

- If M1 = M3 directional: stable stance

### 9.9 Limitations of market-implied expectations
- **Term premium embedment:** prices reflect both expectations and term premium. Term premium varies over time. Not a pure expectations measure.

- **Risk premium distortions:** especially during stress, market pricing can be affected by liquidity and risk aversion, distorting implied rates.

- **Investor base composition:** futures markets dominated by specific participant groups. Expectations reflect their views, not "consensus" of economy.

- **Illiquidity at longer horizons:** OIS beyond 5Y is less liquid. Price moves can reflect positioning rather than views.

> *Para SONAR: market-implied expectations são one signal of many, not definitive truth. Cross-validate with other measures.*
