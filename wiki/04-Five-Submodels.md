# 04 · Five Sub-models

Cinco outputs quantitativos complementares aos ciclos. Diferente de Trading Economics (que mostra indicadores brutos), SONAR **compute** estes outputs localmente daily.

## Sub-model 1 — Yield curves por país

**Output**: curva de juro soberana nominal e real, 11 tenores (3M a 30Y), para 15+ países.

**Methodology**: Nelson-Siegel-Svensson (NSS), fitted to observed sovereign yields, com bootstrap para zero curves e derivation de forwards.

**Output families**:
- Spot curve (fitted yields)
- Zero curve (bootstrap)
- Forward curve (1y1y, 5y5y forward, 10y10y)
- Real curve (direct via linkers OR derived via nominal − expected inflation)
- Swap curve (OIS rates)

**Key countries**:
- **Tier 1**: US, Germany, UK, Japan — excellent BC-published cross-validation
- **Tier 2**: France, Italy, Spain, Canada, Australia
- **Tier 3**: Portugal, Ireland, Netherlands, Sweden, Switzerland
- **Tier 4**: China, India, Brazil, Turkey, Mexico

**Portugal specifics**: via IGCP (primary) + ECB SDW (cross-check) + MTS Portugal (secondary). NSS fit slightly less stable than core due to limited issuance.

**Cross-validation targets**:
- vs Fed Gurkaynak-Sack-Wright: <10bps RMSE all tenors
- vs Bundesbank Svensson: <5bps RMSE
- vs BoE Anderson-Sleath: <10bps

**Full methodology**: [docs/methodology/submodels/yield_curves.md](../docs/methodology/submodels/yield_curves.md)

## Sub-model 2 — ERP diária computada

**Output**: Equity Risk Premium diária para US, EA, UK, Japan via quatro métodos paralelos.

**Methods**:
- **DCF Damodaran** (primary) — 5-year projection + terminal value, solve for implied return
- **Gordon simplified** — payout yield + growth − risk-free
- **Earnings yield simple** — 1/forward PE − risk-free
- **CAPE-based Shiller** — 1/CAPE − real risk-free

**Rationale**: Damodaran publica mensalmente, insuficiente para market timing. SONAR compute daily.

**Key insight**: divergência entre methods é signal:
- DCF vs CAPE >400bps = late-cycle signal
- All methods tight convergence = fair value
- Wide divergence multi-method = regime transition

**April 2026 snapshot** (manual):
- US S&P 500: 4.85%
- STOXX 600: 5.25%
- FTSE All-Share: 5.40%
- TOPIX: 5.55%

**Validation**:
- vs Damodaran monthly: <20bps target at month-end
- vs historical ranges (1960-2026): within reasonable regime
- vs SPF long-run equity: within 100bps

**Full methodology**: [docs/methodology/submodels/erp.md](../docs/methodology/submodels/erp.md)

## Sub-model 3 — Country Risk Premium

**Output**: CRP para 30+ países, daily, em basis points.

**Methodology**: Damodaran hybrid
```
CRP = Default_Spread × (σ_equity / σ_bond)
```

**Default spread sources (hierarchy)**:
1. **5Y CDS** (primary) when liquid — World Government Bonds scrape
2. **Sovereign bond spread** vs risk-free benchmark (fallback)
3. **Rating-based** (see Sub-model 4) when neither available

**Volatility ratio**: country-specific (5Y rolling equity vol / 10Y bond vol) OR Damodaran standard 1.5x.

**April 2026 snapshot** (manual):
- Germany: 0 bps (benchmark)
- Portugal: 54 bps
- Italy: 100 bps
- Spain: 61 bps
- Brazil: 300 bps
- Turkey: 437 bps
- Argentina: 2960 bps

**Portugal CRP trajectory** (remarkable):
- 2007: ~20 bps
- 2012 peak: ~1500 bps
- 2018: ~120 bps
- 2026: ~54 bps

**Full methodology**: [docs/methodology/submodels/crp.md](../docs/methodology/submodels/crp.md)

## Sub-model 4 — Rating-to-spread mapping

**Output**: tabela operacional mapeando rating sovereign para default spread esperado.

**Methodology**:
- Ratings from S&P, Moody's, Fitch, DBRS → SONAR common scale 0-21
- Consolidation via median (conservative on splits)
- Outlook modifiers (+/- 0.25 notches)
- Watch modifiers (+/- 0.5 notches)
- Calibration vs observed market spreads (ICE BofA indices + sovereign observed)

**Core output table (sample)**:
| SONAR notch | Rating | Default spread (bps) |
|---|---|---|
| 21 | AAA | 0-15 |
| 15 | A- | 70-110 |
| 12 | BBB- | 200-290 |
| 10 | BB | 380-540 |
| 7 | B | 850-1200 |
| 4 | CCC | 2000-2800 |
| 1 | C | 5000-7000 |

**Use cases**:
- **Gap-filling** when CDS unavailable
- **Cross-validation** for CDS-implied spreads
- **Arbitrage detection** when market spreads diverge significantly from rating

**Historical default rates** calibrated from Moody's Annual Default Study (1983-2024 sovereign, 1920-2024 corporate).

**Full methodology**: [docs/methodology/submodels/rating_spread.md](../docs/methodology/submodels/rating_spread.md)

## Sub-model 5 — Expected inflation

**Output**: term structure de expected inflation (1Y, 2Y, 5Y, 5y5y forward, 10Y, 30Y) para 17+ países.

**Methodology hierarchy**:
1. **Direct market breakevens** (TIPS US, ILGs UK, BTP€i Italy, etc.)
2. **Inflation swap rates** (EUR, USD, GBP when available)
3. **Synthesized** via regional aggregate + country differential (Portugal approach)
4. **Survey-based** (SPF Philly Fed, Michigan, ECB SPF, BoJ Tankan)
5. **Consensus** forecasts (IMF WEO, OECD, FocusEconomics) for EMs

**Portugal specifically** (no TIPS-like market):
```
E[π_PT(10Y)] = EA_aggregate_BEI + PT-EA_historical_differential
             = 2.20% + 0.15%
             = 2.35% (April 2026 estimate)
```

**5y5y forward** (critical BC credibility indicator):
```
5y5y_forward ≈ [(1 + 10Y_rate)^10 / (1 + 5Y_rate)^5]^(1/5) − 1
```

**Anchoring status**:
- Drift <20bps vs target: well_anchored
- Drift 20-50bps: moderately_anchored
- Drift 50-100bps: drifting
- Drift >100bps: unanchored

**Uses**:
- Real vs nominal conversion
- FX expectation via PPP
- Currency-aware cross-border DCF
- BC credibility assessment

**Full methodology**: [docs/methodology/submodels/expected_inflation.md](../docs/methodology/submodels/expected_inflation.md)

## Integration — cost of capital

Os cinco sub-models compõem-se no **cost of capital framework**:

```
Cost of Equity (nominal, local currency) =
    Risk-free(local, from yield curve)
  + β × ERP(mature market)
  + CRP(country)

Cost of Equity (real) = nominal − expected_inflation(country)

Cost of Equity (foreign currency) = 
    local nominal − expected_FX_depreciation
    where FX depreciation ≈ inflation_differential (via PPP)
```

**Worked example — EDP (Portuguese utility)**:
- Risk-free (Bund 10Y): 2.45%
- ERP EA: 5.25% × β 0.80 = 4.20%
- CRP weighted (international exposure): 0.90%
- **Cost of equity nominal EUR: 7.55%**
- Real: 7.55% − 2.20% = 5.35%

Full use cases in [docs/methodology/submodels/applications.md](../docs/methodology/submodels/applications.md).

---

*Next: [05 · Integration Layer](05-Integration-Layer)*
