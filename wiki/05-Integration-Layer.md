# 05 · Integration Layer

A layer que **compõe** os outputs dos ciclos e sub-models num estado SONAR coerente. É onde o framework ganha poder explicativo — transforma scores independentes numa classificação integrada.

## Três componentes

1. **Matriz 4-way** — padrão canónico do estado macro-financeiro
2. **Quatro diagnósticos aplicados** — bubble, risk appetite, real estate, Minsky fragility
3. **Cost of capital framework** — outputs dos sub-models compostos para valuation cross-border

---

## 1. Matriz 4-way

**Input**: estados dos quatro ciclos (ECS, CCCS, MSC, FCS) + overlays ativos
**Output**: classificação numa das **seis padrões canónicos** ou **cinco configurações críticas**

### Seis padrões canónicos

| # | Padrão | ECS | CCCS | MSC | FCS | Descrição |
|---|---|---|---|---|---|---|
| 1 | **Early Recovery** | 40-55 | <40 | Accommodative | 30-55 | Saída de recessão, BC suporta |
| 2 | **Mid Expansion** | 55-70 | 40-60 | Neutral | 55-75 | Expansão consolidada, balance |
| 3 | **Late Cycle** | 60-70 | 60-80 | Tight | 70-85 | Risks acumulam, BC tightening |
| 4 | **Slowdown** | 45-60 | 50-70 | Tight/Peak | 45-65 | Momentum perdendo, tension |
| 5 | **Recession** | <45 | 70-90+ | Easing | <40 | Contraction synchronized |
| 6 | **Stabilization** | 45-55 | 60-80 (falling) | Accommodative | 30-50 | Bottom-finding |

### Cinco configurações críticas

| # | Configuração | Condição | Risk level |
|---|---|---|---|
| A | **Bubble Warning** | FCS >70 + Bubble Warning overlay active | HIGH |
| B | **Stagflation Trap** | ECS <50 + Stagflation overlay + MSC Tight+Dilemma | HIGH |
| C | **Credit Boom** | CCCS >70 + Boom overlay + ECS >60 | MEDIUM-HIGH |
| D | **Minsky Transition** | CCCS High + Fragility high + MSC turning Tight | HIGH |
| E | **Synchronized Easing** | All cycles declining + MSC Accommodative | MEDIUM (opportunity) |

### Classifier logic

```python
def classify_matriz_4way(state: CycleStates) -> MatrizResult:
    # Check critical configs first (higher priority)
    for config in CRITICAL_CONFIGURATIONS:
        if config.matches(state):
            return MatrizResult(
                classification=config.name,
                type='critical',
                risk_level=config.risk_level,
                confidence=config.confidence(state)
            )

    # Fall through to canonical patterns
    best_match = None
    best_score = 0
    for pattern in CANONICAL_PATTERNS:
        score = pattern.match_score(state)
        if score > best_score:
            best_match = pattern
            best_score = score

    return MatrizResult(
        classification=best_match.name,
        type='canonical',
        confidence=best_score / 100
    )
```

### Transition probabilities

Matriz 4-way tracks transitions historically. Given current pattern, estimates probabilities of transitioning to others over 3/6/12 months.

**April 2026 snapshot (Portugal)**: Pattern 2 (Mid Expansion)
- P(stay Pattern 2 → 6 months): 55%
- P(transition to Pattern 3 Late Cycle): 30%
- P(transition to Pattern 4 Slowdown): 10%
- P(transition to Pattern 5 Recession): 3%
- P(other): 2%

---

## 2. Quatro diagnósticos aplicados

Análises transversais que aplicam múltiplas cycle + sub-model signals.

### Diagnostic 1 — Bubble detection

**Inputs**:
- FCS F1 Valuations component
- CAPE absolute + rolling percentile
- Damodaran-style ERP
- BIS credit-to-GDP gap
- BIS property price gap
- Margin debt / market cap
- IPO activity index
- IPO price vs intrinsic model

**Composite bubble score (0-100)**:
```
bubble_score = (
    0.25 * cape_percentile_score +
    0.15 * erp_inverted_score +
    0.20 * bis_credit_gap_score +
    0.15 * bis_property_gap_score +
    0.10 * margin_debt_score +
    0.10 * ipo_activity_score +
    0.05 * crypto_regime_score
)
```

**Current global April 2026**: 58 (elevated but not euphoric)

### Diagnostic 2 — Risk appetite regime (R1-R4)

**Regimes**:
- **R1 Fear**: VIX >30, credit spreads wide, flight to quality
- **R2 Cautious**: VIX 20-30, mixed signals
- **R3 Normal**: VIX 15-20, neutral positioning
- **R4 Euphoric**: VIX <15, crypto speculation, IPO frenzy

**Current April 2026**: R3 Normal (VIX 17, credit IG 95bps, crypto consolidating)

### Diagnostic 3 — Real estate cycle phase

**Inputs**:
- BIS property price gaps (DM + EM)
- Housing affordability (P/income ratio)
- Mortgage rates vs rent yields
- Construction starts
- Portugal specifics: INE house prices, Golden Visa impact, CRE

**Phases**:
- **Early Expansion**: gap <5pp, prices recovering
- **Mid Expansion**: gap 5-10pp, activity normalizing
- **Late Cycle**: gap 10-20pp, affordability deteriorating
- **Warning**: gap >20pp, credit conditions tightening
- **Correction**: gap declining from elevated, price pressure negative

**Portugal April 2026**: Late Cycle (gap ~14pp, affordability stressed but no credit crisis)

### Diagnostic 4 — Minsky fragility

**Inputs**:
- CCCS level + trajectory
- Corporate leverage metrics
- Sovereign debt-to-GDP + trajectory
- DSR (Debt Service Ratio) BIS
- Interest coverage ratios
- FX mismatch (EM specific)

**Fragility composite (0-100)**:
- Hedge finance phase: <30
- Speculative finance phase: 30-60
- Ponzi finance phase: 60-85
- Distress: >85

**Global April 2026**: 52 (speculative but manageable)
**Portugal April 2026**: 45 (comfortable, improved dramatically post-2012)

---

## 3. Cost of capital framework

Composição final dos cinco sub-models numa formula operacional cross-border.

### Base formula

```
Cost of Equity (nominal, local currency) =
    Risk-free(local, from sub-model yield curve)
  + β × ERP(mature market reference, from sub-model ERP)
  + CRP(country, from sub-model CRP)

Cost of Equity (real) =
    Cost of Equity nominal
  − Expected inflation(country, tenor, from sub-model expected inflation)
```

### Cross-border adjustment

For foreign currency DCF:
```
Cost of Equity (target currency) =
    local cost of equity
  − expected FX depreciation (via PPP from expected inflation differential)
```

### Worked example — EDP (Portuguese utility)

**Inputs (April 2026)**:
- Risk-free: Bund 10Y = 2.45% (from SONAR yield curve DE)
- ERP mature (EA): 5.25% (from SONAR ERP EA)
- β EDP: 0.80 (regulated utility)
- Beta-adjusted ERP: 5.25% × 0.80 = 4.20%
- International exposure weighted CRP:
  - 50% Portugal (CRP 54bps)
  - 30% Brazil (CRP 300bps)
  - 20% other (avg 150bps)
  - Weighted CRP: 0.50×54 + 0.30×300 + 0.20×150 = 27 + 90 + 30 = **147bps**
  - But EDP is regulated, dampened by regulatory return → effective ~90bps
- Expected inflation EA 10Y: 2.20% (SONAR expected inflation)

**Cost of Equity EDP (nominal EUR)**:
```
2.45% (Rf) + 4.20% (β×ERP) + 0.90% (CRP) = 7.55%
```

**Cost of Equity EDP (real)**:
```
7.55% − 2.20% = 5.35%
```

This 7.55% nominal EUR is the discount rate for DCF valuation.

### Use cases catalogados

1. **Portuguese equity valuation** — EDP, Galp, JMT, NOS, Navigator, Semapa, BCP, CTT, Mota-Engil
2. **Brazilian bank cross-border DCF** — Itaú, Bradesco, Santander Brasil from EUR perspective
3. **EM sovereign debt pricing** — comparing market yield vs model-implied fair value
4. **Cross-country equity comparison** — US vs EA vs UK vs Japan fair value analysis
5. **Turkish lira deep dive** — unanchored inflation impact on currency expectations
6. **Portugal Golden Visa real estate** — DCF with tourism/speculation scenarios

---

## Output: SONAR integrated state

Daily output for any country:

```json
{
  "country": "PT",
  "date": "2026-04-17",
  "cycles": {
    "economic": {"score": 56, "state": "Mid Expansion"},
    "credit": {"score": 51, "state": "Recovery-Boom transition"},
    "monetary": {"score": 48, "state": "Neutral"},
    "financial": {"score": 61, "state": "Optimism"}
  },
  "overlays_active": [],
  "matriz_4way": {
    "classification": "Mid Expansion",
    "type": "canonical",
    "pattern_number": 2,
    "confidence": 0.82
  },
  "diagnostics": {
    "bubble_score": 58,
    "risk_appetite": "R3 Normal",
    "real_estate_phase": "Late Cycle",
    "minsky_fragility": 45
  },
  "cost_of_capital": {
    "risk_free_10y_pct": 2.45,
    "erp_mature_pct": 5.25,
    "crp_bps": 54,
    "cost_of_equity_nominal_pct": 7.64,
    "cost_of_equity_real_pct": 5.44,
    "expected_inflation_10y_pct": 2.20
  },
  "alert_level": "green",
  "editorial_angles_triggered": []
}
```

---

*Next: [06 · Data Strategy](06-Data-Strategy)*
