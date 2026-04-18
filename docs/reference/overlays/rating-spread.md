# Rating-to-Spread Mapping

> Overlay L2 — Parte V (caps 13-15) · Rating mapping do Manual dos Sub-Modelos Quantitativos.

## Capítulo 13 · Rating agency landscape e escala comum
### 13.1 O universo das rating agencies
Credit rating agencies atribuem opinions sobre creditworthiness de emitentes e instrumentos. Para sovereign debt, quatro agências dominam globalmente — as "Big Three" (S&P, Moody's, Fitch) mais DBRS Morningstar. Outras menores (Scope Ratings, R&I, JCR) têm reconhecimento regional.

Para SONAR operacional, o output crítico é: dada uma rating sovereign, qual default probability implied e qual spread correspondente. O capítulo 14 e 15 operacionalizam essa mapping; este capítulo estabelece a foundation.

> *As rating agencies são contestadas após 2008 por falhas em corporate e sovereign ratings. Mas permanecem o standard institucional. Regulatory frameworks (Basel, Solvency II, investment mandates) referenciam-nas. Operacionalmente, SONAR tem que trabalhar com elas — critically but professionally.*

### 13.2 Big Three — escalas de rating
**Standard & Poor's / Fitch scale**

| **Grade**        | **Scale**       | **Description**                     |
|------------------|-----------------|-------------------------------------|
| Investment grade | AAA             | Highest, minimal credit risk        |
| Investment grade | AA+, AA, AA-    | Very strong                         |
| Investment grade | A+, A, A-       | Strong but more susceptible         |
| Investment grade | BBB+, BBB, BBB- | Adequate; lowest investment grade   |
| Speculative      | BB+, BB, BB-    | Less vulnerable near term           |
| Speculative      | B+, B, B-       | More vulnerable                     |
| Substantial risk | CCC+, CCC, CCC- | Currently vulnerable                |
| Near default     | CC              | Highly vulnerable                   |
| Default imminent | C               | Bankruptcy filed, payments continue |
| Default          | D               | In default                          |

**Moody's scale**

| **Grade**        | **Scale**        | **S&P/Fitch equivalent** |
|------------------|------------------|--------------------------|
| Investment grade | Aaa              | AAA                      |
| Investment grade | Aa1, Aa2, Aa3    | AA+, AA, AA-             |
| Investment grade | A1, A2, A3       | A+, A, A-                |
| Investment grade | Baa1, Baa2, Baa3 | BBB+, BBB, BBB-          |
| Speculative      | Ba1, Ba2, Ba3    | BB+, BB, BB-             |
| Speculative      | B1, B2, B3       | B+, B, B-                |
| Substantial risk | Caa1, Caa2, Caa3 | CCC+, CCC, CCC-          |
| Near default     | Ca               | CC                       |
| In default       | C                | D                        |

**DBRS scale**

DBRS uses similar letter grading to S&P/Fitch:

- AAA, AAH, AAM, AAL, ... (where H = high, M = mid, L = low)

- Example: AA (high) equivalent to AA+, AA equivalent to AA, AA (low) equivalent to AA-

- Thirteen notches investment grade similar to S&P

- Adopted by ECB as official agency for EA collateral framework

### 13.3 SONAR common scale
SONAR converts all ratings to integer common scale for operational simplicity:

| **SONAR notch** | **S&P/Fitch** | **Moody's** | **DBRS**   | **Category**       |
|-----------------|---------------|-------------|------------|--------------------|
| 21              | AAA           | Aaa         | AAA        | Prime              |
| 20              | AA+           | Aa1         | AA (high)  | High grade         |
| 19              | AA            | Aa2         | AA         | High grade         |
| 18              | AA-           | Aa3         | AA (low)   | High grade         |
| 17              | A+            | A1          | A (high)   | Upper medium       |
| 16              | A             | A2          | A          | Upper medium       |
| 15              | A-            | A3          | A (low)    | Upper medium       |
| 14              | BBB+          | Baa1        | BBB (high) | Lower medium       |
| 13              | BBB           | Baa2        | BBB        | Lower medium       |
| 12              | BBB-          | Baa3        | BBB (low)  | Lower medium IG    |
| 11              | BB+           | Ba1         | BB (high)  | Speculative        |
| 10              | BB            | Ba2         | BB         | Speculative        |
| 9               | BB-           | Ba3         | BB (low)   | Speculative        |
| 8               | B+            | B1          | B (high)   | Highly speculative |
| 7               | B             | B2          | B          | Highly speculative |
| 6               | B-            | B3          | B (low)    | Highly speculative |
| 5               | CCC+          | Caa1        | CCC (high) | Substantial risk   |
| 4               | CCC           | Caa2        | CCC        | Substantial risk   |
| 3               | CCC-          | Caa3        | CCC (low)  | Substantial risk   |
| 2               | CC            | Ca          | CC         | Near default       |
| 1               | C             | C           | C          | Default imminent   |
| 0               | D / SD        | C / D       | D          | In default         |

**Consolidation rules**

- Sovereign rating: median of available agency ratings (S&P, Moody's, Fitch, DBRS)

- If split: use most conservative (lowest notch)

- Update when any agency changes rating

- Track all four agencies separately + consolidated median

### 13.4 Local currency vs foreign currency rating
Sovereign ratings distinguem two dimensions críticas:

**Foreign currency (FC) rating**

- Rating on debt denominated in foreign currency (typically USD or EUR)

- Reflects ability to access hard currency

- Lower (worse) than LC rating typically

- Relevant for international investors

**Local currency (LC) rating**

- Rating on debt denominated in country's own currency

- Reflects willingness/ability to repay in own currency

- Sovereign can print local currency — lower default risk ceteris paribus

- Higher (better) than FC rating typically

- Relevant for domestic investors

**When they differ significantly**

- EMs with hard currency reserves constraints

- Countries with capital controls

- Currency unions (EA) — LC rating moot for individual countries

- Argentina historically: LC much higher than FC

- Turkey: LC slightly higher than FC

- Brazil: LC notably higher than FC

**SONAR publishes both**

- FC rating for USD-denominated analysis

- LC rating for local currency analysis

- Default to FC unless explicitly local currency context

### 13.5 Outlook and credit watch
**Rating modifier information**

- **Positive outlook:** upgrade possible within 6-24 months

- **Stable outlook:** rating unlikely to change near term

- **Negative outlook:** downgrade possible within 6-24 months

- **Developing outlook:** direction uncertain

- **CreditWatch / Review:** more active signal — change expected within 90 days

**SONAR modifier incorporation**

- Positive outlook: weight rating as if 0.25 notches higher

- Negative outlook: weight rating as if 0.25 notches lower

- CreditWatch: adjust by 0.5 notches in indicated direction

- Captures forward-looking information from agencies

- Separate output field, user choose whether to apply

### 13.6 Current sovereign ratings snapshot (April 2026)
| **Country**  | **S&P** | **Moody's** | **Fitch** | **DBRS**  | **SONAR notch** |
|--------------|---------|-------------|-----------|-----------|-----------------|
| US           | AA+     | Aaa         | AA+       | AAA       | 20.5            |
| Germany      | AAA     | Aaa         | AAA       | AAA       | 21              |
| UK           | AA      | Aa3         | AA-       | AA (high) | 19              |
| Japan        | A+      | A1          | A         | A (high)  | 16.5            |
| France       | AA-     | Aa2         | AA-       | AA (high) | 18.5            |
| Italy        | BBB     | Baa3        | BBB       | BBB       | 12.75           |
| Spain        | A       | Baa1        | A-        | A         | 15.5            |
| Portugal     | A-      | A3          | A-        | A (low)   | 15              |
| Greece       | BBB-    | Baa3        | BBB-      | BBB (low) | 12              |
| Ireland      | AA      | Aa3         | AA-       | AA        | 19              |
| Poland       | A-      | A2          | A-        | A (low)   | 15.5            |
| Brazil       | BB      | Ba2         | BB        | BB        | 10              |
| Mexico       | BBB     | Baa2        | BBB-      | BBB       | 12.67           |
| Turkey       | B+      | B1          | B+        | B (high)  | 8               |
| Argentina    | CCC     | Ca          | CCC       | CCC       | 3               |
| China        | A+      | A1          | A+        | A (high)  | 17              |
| India        | BBB-    | Baa3        | BBB-      | BBB (low) | 12              |
| South Africa | BB-     | Ba2         | BB-       | BB (low)  | 9.33            |

**Observations**

- US split rating (AA+ S&P/Fitch, AAA Moody's/DBRS)

- Portugal A- após upgrade 2024 — significant improvement

- Italy BBB — investment grade by 2 notches only

- Argentina CCC — near distress but not default

- Turkey B+ — below investment grade by 5 notches

### 13.7 Rating trajectory — Portugal case study
| **Year** | **S&P** | **Moody's** | **Fitch** | **Trajectory**        |
|----------|---------|-------------|-----------|-----------------------|
| 2005     | AA-     | Aa2         | AA        | Pre-crisis            |
| 2009     | A+      | Aa2         | AA        | GFC start             |
| 2011 Jan | A-      | A1          | A+        | Deteriorating         |
| 2011 Jul | BBB-    | Ba2         | BB+       | Junk territory (S&P)  |
| 2012     | BB      | Ba3         | BB+       | Troika bailout        |
| 2014     | BB      | Ba2         | BB+       | Still junk            |
| 2017     | BB+     | Ba1         | BBB-      | IG by Fitch           |
| 2018     | BBB-    | Baa3        | BBB       | IG by all three       |
| 2021     | BBB     | Baa2        | BBB       | Continued improvement |
| 2024     | A-      | A3          | A-        | Current A level       |
| 2026     | A-      | A3          | A-        | Stable                |

**Spread implications of Portugal trajectory**

- 2005 (AA-): spread vs Bund ~10bps

- 2012 (BB): spread vs Bund ~1200bps

- 2018 (BBB-): spread vs Bund ~200bps

- 2026 (A-): spread vs Bund ~70bps

- Rating-to-spread relationship empirically validated

### 13.8 Rating criticisms
**Criticism 1 — Late in crises**

- Lehman Brothers rated A+ days before bankruptcy

- AAA-rated CDOs defaulted 2007-2008

- Greek downgrades lagged market repricing 2010-2011

- Reactive rather than proactive

**Criticism 2 — Issuer-paid model**

- Conflict of interest — agencies paid by rated entities

- Rating shopping — issuers choose favorable agency

- Big Three dominance limits competition

**Criticism 3 — Sovereign specific**

- Sovereign ratings have political dimensions

- Downgrades of Western sovereigns politically sensitive

- Inconsistency between sovereigns

**SONAR response**

- Use ratings as one input, not sole determinant

- Triangulate with CDS, bond spreads, fundamentals

- Track rating deltas (signal value in changes)

- Flag when market spreads diverge materially from rating

- Document agency biases historically

### 13.9 ECB ratings framework
ECB uses credit ratings for collateral framework (ECAF). Consequential for EA sovereigns:

**ECB eligibility**

- AAA to BBB- (investment grade): standard eligibility

- Below BBB-: ineligible for standard operations

- Specific exceptions for countries in IMF programs (historical)

- Affects bond market dynamics

**Portugal's ECB collateral journey**

- Pre-2011: standard eligibility

- 2011-2014: special waiver during program

- Post-2017 (BBB-): back to standard

- 2024+ (A-): well within standard eligibility

**Implications for yields**

- Eligible sovereigns benefit from ECB collateral demand

- Loss of eligibility → yield spike

- This creates rating cliff effect at BBB-

## Capítulo 14 · Historical default rates e recovery
### 14.1 O Moody's Annual Default Study
Moody's publishes annually comprehensive study of historical default rates por rating class. Period 1920-current. Largest longitudinal dataset de default behavior. Critical reference for rating-to-spread calibration.

**Key methodology**

- Cumulative default rates — % of issuers rated at given grade that defaulted within N years

- Marginal default rates — % defaulting each year

- Recovery rates — recoveries on defaulted instruments

- By sector: sovereigns, corporate investment grade, high yield, structured

> *Moody's data desde 1920 inclui Great Depression, WW2, post-war boom, stagflation, Volcker, dot-com, GFC, COVID. É arguably the richest default dataset ever compiled. SONAR's rating-to-spread mapping calibrates against these numbers directly.*

### 14.2 Sovereign default rates — Moody's
**Cumulative sovereign default rates (1983-2024)**

| **Rating** | **1Y** | **5Y** | **10Y** | **20Y** |
|------------|--------|--------|---------|---------|
| Aaa        | 0.00%  | 0.00%  | 0.00%   | 0.00%   |
| Aa         | 0.00%  | 0.10%  | 0.30%   | 0.80%   |
| A          | 0.10%  | 0.50%  | 1.00%   | 2.50%   |
| Baa        | 0.20%  | 1.50%  | 3.00%   | 6.50%   |
| Ba         | 0.80%  | 7.00%  | 15.00%  | 25.00%  |
| B          | 2.50%  | 20.00% | 35.00%  | 45.00%  |
| Caa-C      | 15.00% | 50.00% | 65.00%  | 75.00%  |

**Corporate default rates (broader universe, 1920-2024)**

| **Rating** | **1Y** | **5Y** | **10Y** |
|------------|--------|--------|---------|
| Aaa        | 0.00%  | 0.10%  | 0.50%   |
| Aa         | 0.02%  | 0.25%  | 1.00%   |
| A          | 0.06%  | 0.60%  | 2.00%   |
| Baa        | 0.18%  | 1.80%  | 4.50%   |
| Ba         | 1.10%  | 8.00%  | 17.00%  |
| B          | 4.00%  | 22.00% | 38.00%  |
| Caa-C      | 16.00% | 45.00% | 60.00%  |

**Observations**

- Sovereign default rates generally lower than corporate (sovereigns can print)

- Exception: Caa-C sovereigns default at similar rates (both distressed)

- Investment grade (Baa and above) default rates very low

- Dramatic step-down from Ba to Baa (investment grade cliff)

### 14.3 Recovery rates on sovereign defaults
**Historical sovereign recovery rates (selected defaults)**

| **Country** | **Default year** | **Recovery rate**       |
|-------------|------------------|-------------------------|
| Argentina   | 2001             | ~30%                    |
| Argentina   | 2014 (technical) | ~60%                    |
| Argentina   | 2020             | ~55%                    |
| Greece      | 2012 (PSI)       | ~24%                    |
| Russia      | 1998             | ~30%                    |
| Venezuela   | 2017+            | \<10%                   |
| Ukraine     | 2015             | ~60%                    |
| Ukraine     | 2022             | ~15% (still unresolved) |
| Ecuador     | 2020             | ~65%                    |
| Lebanon     | 2020             | ~30%                    |
| Sri Lanka   | 2022             | TBD, est. 40-50%        |
| Zambia      | 2020             | ~50%                    |

**Sovereign recovery patterns**

- Average sovereign recovery: ~35-45%

- Wide dispersion by case

- Political stability at default time matters

- Currency regime matters (dollarized harder to restructure)

- Moody's standard assumption: 40% recovery for modeling

- SONAR adopts 40% as baseline, adjusts by country specifics

### 14.4 Implied default spread from default probabilities
**The core formula**

*PD × LGD = Spread (approximately)*

Onde:

- PD = probability of default (annualized)

- LGD = loss given default (1 - recovery rate)

- Spread = required credit spread over risk-free

**Example calculations**

> Rating Baa (BBB equivalent):
> Annual PD ~ 0.18% (corporate) or 0.20% (sovereign)
> LGD ~ 60% (1 - 40% recovery)
> Implied annual spread ~ 0.20% × 0.60 = 0.12% = 12 bps
> BUT observed market spreads for BBB typically 100-200 bps
> Difference = credit risk premium + liquidity premium
> Rating Ba (BB equivalent):
> Annual PD ~ 1.10%
> LGD ~ 60%
> Implied annual spread ~ 1.10% × 0.60 = 0.66% = 66 bps
> BUT observed market spreads for BB typically 250-450 bps
> Much larger gap between pure actuarial and market
> Rating B:
> Annual PD ~ 4.00%
> LGD ~ 60%
> Implied annual spread ~ 4.00% × 0.60 = 2.40% = 240 bps
> Observed market spreads for B typically 500-700 bps

**Why market spreads \> actuarial spreads**

- Credit risk premium: investors demand compensation for uncertainty of losses, not just expected losses

- Liquidity premium: less liquid bonds carry additional spread

- Jump-to-default risk: possibility of sudden deterioration

- Historical variation risk

- Institutional demand/supply imbalances

- Regulatory capital treatment

- Tax treatment differences

- Gap between pure actuarial and market typically 2-4x

### 14.5 Credit risk premium empirical evidence
Academic studies quantify the gap between actuarial and market spreads:

**Elton et al. (2001)**

- Decomposed corporate bond spreads

- Expected default losses: ~25% of spread

- Tax effect: ~35% of spread

- Systematic risk premium: ~40% of spread

- Methodology refined by subsequent studies

**Huang-Huang (2012)**

- Structural credit risk models

- Actuarial risk ~30-50% of observed spreads

- Remainder = risk premium

**Implications for SONAR**

- Use observed market spreads as basis for rating-to-spread mapping

- Don't "correct" for risk premium — market spreads are what investors demand

- Acknowledge this gap in documentation

- Track actuarial vs market divergence over time

### 14.6 Rating-to-spread empirical mapping
SONAR calibra table using observed market spreads by rating class, not pure actuarial calculations.

**Data sources for calibration**

- ICE BofA indices by rating (AA, A, BBB, BB, B, CCC)

- Bloomberg Barclays indices by rating

- Sovereign bond spreads by rating (EMBI+ stratified)

- Historical averages over multiple cycles

**Rolling calibration**

- Use 5-year rolling average of observed spreads

- Smooths cyclical distortions

- Captures structural changes gradually

- Updated monthly

### 14.7 Cross-validation with CDS
Rating-to-spread mapping should be consistent with CDS-based spreads.

**Validation approach**

- For countries with both CDS and SONAR rating: compare

- Rating-implied spread should be within 50% of CDS

- Persistent divergence indicates agency rating lag or market overreaction

- Use CDS when available (more market-responsive)

- Use rating-based when CDS unavailable

**Current validation snapshot (April 2026)**

| **Country**   | **SONAR notch** | **Rating-implied spread (bps)** | **CDS 5Y (bps)** | **Consistency**              |
|---------------|-----------------|---------------------------------|------------------|------------------------------|
| Germany (21)  | AAA             | 10-15                           | 9                | ✓ consistent                 |
| France (18.5) | AA-             | 25-35                           | 30               | ✓ consistent                 |
| US (20.5)     | AA+/Aaa         | 15-25                           | 28               | ✓ close                      |
| Italy (12.75) | BBB             | 150-250                         | 68               | ↔ market tighter than rating |
| Portugal (15) | A-              | 60-100                          | 35               | ↔ market tighter than rating |
| Greece (12)   | BBB-            | 200-350                         | 85               | ↔ market tighter             |
| Brazil (10)   | BB              | 300-500                         | 180              | ↔ market tighter             |
| Turkey (8)    | B+              | 500-700                         | 280              | ↔ market tighter             |

**Pattern — market spreads tighter than rating-implied**

- Common pattern in benign periods (2026)

- Market prices in optimistic scenario

- ECB support for EA sovereigns depresses spreads

- Fed rate cuts depressed EM spreads

- Rating-implied = more conservative estimate

**When reversed**

- Stress periods: CDS widens faster than ratings change

- 2011-12 EA crisis: CDS widely above rating-implied

- 2020 COVID: similar pattern briefly

## Capítulo 15 · Rating-to-spread operational table
### 15.1 The SONAR operational table
This is the core operational output of this sub-model. Dada uma rating sovereign, produz implied spread. Used when CDS and sovereign bond spread not available, or as triangulation input.

**SONAR rating-to-spread table (April 2026 calibration)**

| **SONAR notch** | **Rating equivalent** | **Default spread (bps)** | **Range** |
|-----------------|-----------------------|--------------------------|-----------|
| 21              | AAA / Aaa             | 0-15                     | 0-20      |
| 20              | AA+ / Aa1             | 15-25                    | 10-30     |
| 19              | AA / Aa2              | 20-35                    | 15-40     |
| 18              | AA- / Aa3             | 25-45                    | 20-55     |
| 17              | A+ / A1               | 35-60                    | 25-70     |
| 16              | A / A2                | 50-80                    | 40-95     |
| 15              | A- / A3               | 70-110                   | 55-130    |
| 14              | BBB+ / Baa1           | 100-150                  | 85-180    |
| 13              | BBB / Baa2            | 140-210                  | 120-250   |
| 12              | BBB- / Baa3           | 200-290                  | 170-340   |
| 11              | BB+ / Ba1             | 280-400                  | 230-470   |
| 10              | BB / Ba2              | 380-540                  | 310-620   |
| 9               | BB- / Ba3             | 500-700                  | 400-800   |
| 8               | B+ / B1               | 650-900                  | 520-1050  |
| 7               | B / B2                | 850-1200                 | 700-1400  |
| 6               | B- / B3               | 1100-1550                | 900-1800  |
| 5               | CCC+ / Caa1           | 1500-2100                | 1200-2500 |
| 4               | CCC / Caa2            | 2000-2800                | 1600-3300 |
| 3               | CCC- / Caa3           | 2700-3800                | 2200-4500 |
| 2               | CC / Ca               | 3500-5000                | 3000-6500 |
| 1               | C                     | 5000-7000                | 4500-9000 |
| 0               | D                     | N/A (default occurred)   | —         |

**Table structure explanation**

- Central value: median of recent 5-year observed spreads at that rating

- Range: typical 25th-75th percentile

- Extended range: ±50% to capture regime variations

- Updated quarterly with new data

- Adjustments for EA vs EM sovereign distinctions

### 15.2 Application examples
**Example 1 — Ghana (no liquid CDS)**

- SONAR ratings: S&P CCC+, Moody's Ca, Fitch CCC

- Median SONAR notch: ~4 (CCC)

- Rating-implied spread: 2000-2800 bps

- Central estimate: 2400 bps

- Applied to CRP with vol ratio: ~3700 bps CRP Ghana

**Example 2 — Bolivia (no liquid CDS)**

- SONAR ratings: S&P BB-, Moody's B1, Fitch B

- Median SONAR notch: ~8 (B+)

- Rating-implied spread: 650-900 bps

- Central estimate: 750 bps

- Applied to CRP: ~1100-1200 bps CRP Bolivia

**Example 3 — Portugal (CDS available, cross-check)**

- SONAR notch 15 (A-): rating-implied 70-110 bps

- CDS 5Y: 35 bps

- CDS \< rating-implied — market tighter than rating

- SONAR uses CDS (primary), rating as cross-check

- Note discrepancy for editorial angle

### 15.3 Regional adjustments
SONAR adjusts base table for regional characteristics.

**EA membership adjustment**

- EA sovereigns benefit from ECB support framework

- Reduces effective default spread by ~20%

- Particularly at BBB- / BBB level

- Applied automatically for EA countries

**Currency union adjustment**

- Countries in currency unions: slight spread reduction

- Currency risk eliminated for members

- Applied to ECCU, CEMAC, WAEMU, EA

**Oil exporter adjustment**

- Major oil exporters with fiscal buffers

- Saudi Arabia, UAE, Qatar, Kuwait

- Spreads tighter than rating implies

- ~30-50bps reduction at A range

**Hyperinflation adjustment**

- Countries with hyperinflation: CDS/bond less meaningful

- Turkey, Argentina, Venezuela

- Wider confidence intervals

- Actuarial default probabilities particularly uncertain

### 15.4 Historical regime variations
**Low spread regime (2012-2019)**

- QE globalmente depressed all risk premia

- BBB sovereigns spreads 80-150bps typical

- Rating-to-spread table calibrated lower

**Normalized regime (2020-2022)**

- Taper-tantrum concerns

- BBB sovereigns 150-250bps

- Closer to historical norms

**Tight regime (2023-2024)**

- Fed QT, ECB QT

- Spreads widened

- BBB sovereigns 200-300bps

**Current regime (2025-2026)**

- Modest easing cycle

- Spreads compressed again

- BBB sovereigns 140-210bps (current calibration)

**Recalibration frequency**

- Table updated quarterly

- Major regime shifts trigger mid-quarter update

- Users can request historical calibration for backtest

### 15.5 Decision tree applied
> country_default_spread_hierarchy(country):
> \# Level 1: Liquid 5Y CDS
> if cds_liquid(country) and cds_5y_available(country):
> spread = cds_5y_spread(country)
> source = "CDS"
> confidence = 0.90
> \# Level 2: USD-denominated sovereign bond
> elif usd_sovereign_available(country):
> spread = usd_sovereign_spread(country) - LIQUIDITY_PREMIUM_EST
> source = "bond_spread"
> confidence = 0.80
> \# Level 3: Local currency bond adjusted
> elif local_sovereign_available(country) and fx_expectation_known(country):
> spread = local_spread(country) - expected_fx_depreciation(country)
> source = "bond_local_adjusted"
> confidence = 0.70
> \# Level 4: Rating-based from SONAR table
> elif sonar_rating_available(country):
> spread = sonar_rating_table(country)
> source = "rating_based"
> confidence = 0.65
> \# Level 5: Regional fallback
> else:
> spread = regional_average_spread(country_region(country))
> source = "regional_fallback"
> confidence = 0.50
> return {
> 'spread_bps': spread,
> 'source': source,
> 'confidence': confidence
> }

### 15.6 Cross-validation all four approaches
When all four sources available (CDS, bond spread, rating, multiple agencies), SONAR publishes comparison:

> {
> "country": "PT",
> "date": "2026-04-17",
> "spread_sources": {
> "cds_5y": 35,
> "bond_spread_10y_vs_bund": 70,
> "rating_implied_sp": 90,
> "rating_implied_moodys": 90,
> "rating_implied_fitch": 90,
> "rating_implied_dbrs": 90,
> "rating_implied_sonar_median": 90,
> "rating_implied_range": \[70, 110\]
> },
> "canonical": {
> "value_bps": 35,
> "source": "cds_5y_primary",
> "confidence": 0.90
> },
> "divergence_analysis": {
> "cds_vs_rating_bps": -55,
> "flag": "market_tighter_than_rating",
> "explanation": "Typical in benign periods, ECB support"
> }
> }

### 15.7 Rating actions and SONAR response
**Upgrade scenarios**

- Agency upgrades by one notch

- SONAR notch updates (possibly median moves if multi-agency)

- Spread expectation updates

- If CDS hasn't adjusted yet, basis opportunity flagged

- Historical: upgrades typically follow 20-50bps tightening in CDS

**Downgrade scenarios**

- Agency downgrades by one notch

- SONAR updates rating-implied spread

- CDS typically already wider by time downgrade occurs

- Rating-CDS convergence in following weeks

**Rating on CreditWatch Negative**

- SONAR applies 0.5 notch adjustment downward

- Rating-implied spread widens accordingly

- Flag for monitoring

- Alert if triggers alert threshold

**Editorial opportunity**

- Rating actions are news events

- SONAR can frame in context

- "Moody's upgraded Portugal to A3 — o que isso significa em spread"

- Editorial voice via framework
