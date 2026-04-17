# 03 · Four Cycles

SONAR classifica macro state via **quatro ciclos interagindo**. Cada ciclo tem score 0-100 e overlay específico.

## ECS — Economic Cycle Score

**Purpose**: classificar expansão / contração económica

**Components (E1-E4, weights 35/25/25/15)**:
- **E1 Activity** (35%) — GDP, IP, retail, employment, income
- **E2 Leading** (25%) — yield curve, credit spreads, PMIs, LEI, OECD CLI
- **E3 Labor** (25%) — NFP, unemployment, Sahm Rule, JOLTS, wages, claims
- **E4 Sentiment** (15%) — UMich, Conference Board, EPU, ESI, Ifo, ZEW, VIX

**States**:
- Expansion (>60)
- Peak zone (55-70)
- Early recession (40-55)
- Recession (<40)

**Overlay**: Stagflation
Ativo quando: ECS <55 + monthly CPI >3% YoY + labor weakness emerging.

**Full manual**: [docs/methodology/cycles/economic/](../docs/methodology/cycles/economic/)

## CCCS — Credit Cycle Score

**Purpose**: classificar fase do credit cycle (Minsky-inspired)

**Components**:
- Credit expansion metrics (growth vs GDP)
- Leverage (corporate, household, sovereign)
- Delinquency + charge-off trends
- Bank lending standards (SLOOS-type)
- Credit spreads (sovereign + corporate)

**States**:
- Repair (<30)
- Recovery (30-50)
- Boom (50-70)
- Speculation / Late boom (70-85)
- Distress (>85 after downturn)

**Overlay**: Boom
Ativo quando: CCCS >70 + rapid credit expansion + DSR elevated + BIS credit gap >10pp.

**Full manual**: [docs/methodology/cycles/credit/](../docs/methodology/cycles/credit/)

## MSC — Monetary Stance Composite

**Purpose**: classificar BC stance (accommodative / neutral / tight)

**Components**:
- Policy rate vs neutral rate
- Yield curve slope (**uses sub-model yield curves!**)
- BC balance sheet metrics
- Forward guidance signals
- Real rates

**States**:
- Accommodative (<40)
- Neutral (40-60)
- Tight (>60)

**Overlay**: Dilemma
Ativo quando: inflation >target + growth weakening + BC pressured (stagflation-like).

**Full manual**: [docs/methodology/cycles/monetary/](../docs/methodology/cycles/monetary/)

## FCS — Financial Cycle Score

**Purpose**: classificar financial cycle (valuations / momentum / risk / positioning)

**Components (F1-F4, weights 30/25/25/20)**:
- **F1 Valuations** (30%) — CAPE, Buffett, **Damodaran-style ERP (uses sub-model!)**, P/E, real estate
- **F2 Momentum** (25%) — price momentum, breadth, cross-asset
- **F3 Risk Appetite** (25%) — VIX, MOVE, credit spreads, FCI, crypto vol
- **F4 Positioning** (20%) — AAII, P/C, COT, flows, margin debt, IPO activity

**States**:
- Stress (<30)
- Caution (30-55)
- Optimism (55-75)
- Euphoria (>75)

**Overlay**: Bubble Warning
Ativo quando: FCS >70 + BIS credit gap >10pp + BIS property gap >20% (medium-term overlay).

**Full manual**: [docs/methodology/cycles/financial/](../docs/methodology/cycles/financial/)

## Interactions — why four, not one

Ciclos não são paralelos independentes — interagem:

### Typical sequences

```
Recovery pattern:
  MSC Accommodative → ECS Expansion → CCCS Recovery → FCS Optimism

Boom pattern:
  ECS Expansion + CCCS Boom + FCS Euphoria → vulnerability accumulates

Bust pattern:
  MSC Tight → CCCS Distress → ECS Recession → FCS Stress
```

### Cross-cycle information

- MSC tightness → ECS transition to peak zone (6-18 months lag)
- CCCS Boom → FCS Euphoria often coincident
- FCS Stress → ECS Recession (financial cycle leads real cycle)
- ECS Recession → MSC Easing (BC reaction function)

### Matriz 4-way

Integration via matriz 4-way (ver [05 · Integration Layer](05-Integration-Layer)):
- **Six canonical patterns** (e.g., Mid Expansion, Late Cycle, Recession)
- **Five critical configurations** (e.g., Bubble, Stagflation Trap)

## Portugal application

Todos os quatro ciclos computados para Portugal:

Current state April 2026 (from manuais):
- **ECS**: 56 (Mid Expansion)
- **CCCS**: 51 (Recovery-Boom transition)
- **MSC**: 48 (ECB Neutral)
- **FCS**: 61 (Optimism)
- **Pattern**: Mid Expansion (Pattern 2)
- **Overlays active**: none
- **Alert level**: green

Historical Portugal trajectory:
- **2005**: Stable expansion pre-crisis
- **2008-2012**: ECS Recession + CCCS Distress + MSC Accommodative + FCS Stress
- **2012-2014**: Troika era, gradual stabilization
- **2017-2020**: Recovery consolidated
- **2020**: COVID shock brief recession
- **2021-2022**: Recovery + inflation shock
- **2023-2026**: Normalization

---

*Next: [04 · Five Sub-models](04-Five-Submodels)*
