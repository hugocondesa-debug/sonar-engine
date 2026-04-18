# M2 · Taylor Rule gaps

> Sub-índice do Ciclo Monetário — capítulo 8 do manual (Manual_Ciclo_Monetario_COMPLETO).

### 8.1 Recapitulação — a Taylor Rule original
Revisitamos a fórmula Taylor 1993 para implementação:

*i_t = r\* + π_t + 0.5(π_t − π\*) + 0.5(y_t − y\*\_t)*

Com:

- i_t = policy rate prescrita

- r\* = taxa neutral real

- π_t = inflação atual (CPI YoY)

- π\* = target de inflação (tipicamente 2%)

- (y_t − y\*\_t) = output gap (percent deviation from potential)

- Coefficients: 0.5 para inflation gap, 0.5 para output gap

**Aplicação em Abril 2026 (US)**

Inputs:

- r\* = 0.85% (Laubach-Williams 2024 estimate)

- π_t = 2.6% (PCE core YoY)

- π\* = 2.0%

- y − y\* = +0.5% (slight positive output gap)

Taylor-prescribed rate = 0.85 + 2.6 + 0.5(0.6) + 0.5(0.5) = 4.0%

Fed actual rate = 4.375% (midpoint of 4.25-4.50% range)

Taylor Rule gap = actual - prescribed = 4.375 - 4.0 = +0.375%

> *Interpretation: Fed slightly tighter than Taylor Rule prescribes. Classification: Marginally Tight vs Taylor.*

### 8.2 Variantes críticas da Taylor Rule
A Taylor Rule original foi proposta como descriptive — capture de comportamento Fed 1987-1992. Variantes evoluíram para addressing shortcomings:

**Taylor (1999) — "balanced approach"**

*i_t = r\* + π_t + 0.5(π_t − π\*) + 1.0(y_t − y\*\_t)*

Raised output gap coefficient from 0.5 to 1.0. Empirically, Fed post-1987 seems closer to 1999 than 1993 formulation.

**Taylor Rule with inertia — adds rate smoothing**

*i_t = ρ · i\_{t-1} + (1−ρ) · i^Taylor_t*

Onde ρ (smoothing parameter) ≈ 0.8-0.9. Captures that BCs hate large moves — they smooth.

**Forward-looking Taylor Rule — uses forecast inflation**

*i_t = r\* + π^e\_{t+h} + 0.5(π^e\_{t+h} − π\*) + 0.5(y_t − y\*\_t)*

Onde π^e\_{t+h} é inflation expectations at horizon h (typically 4-8 quarters ahead). Mais realistic — BCs react to future inflation, not current.

**Asymmetric Taylor Rule — different coefficients for tight vs loose**

- Coefficient on inflation gap maior quando π \> π\* (BCs aggressive about overshooting)

- Smaller coefficient quando π \< π\* (BCs reluctant undershooting)

**Financial-conditions-augmented Taylor (Taylor 2013)**

*i_t = r\* + π_t + 0.5(π_t − π\*) + 0.5(y_t − y\*\_t) + 0.25 · FCI_t*

Adds term para financial conditions. Captures Borio's leaning-against-the-wind intuition.

### 8.3 Qual Taylor Rule usar para o SONAR?
Recomendação: computar múltiplas variantes simultaneamente. Cada variante responde a pergunta diferente:

- **Taylor 1993:** "onde estaria stance se BC seguisse regra standard?"

- **Taylor 1999:** "onde estaria stance se BC cared more about output?"

- **Taylor with inertia:** "onde estaria stance smoothed?"

- **Forward-looking:** "onde estaria stance se BC reagisse a forecasts?"

Três ou quatro variantes dão range of plausible stances. Diferenças entre elas indicam policy uncertainty.

> **Nota** *Implementação: computar todas, reportar median + range. Flag outliers (situações onde variantes disagree strongly).*

### 8.4 Estimar os inputs — a parte difícil
Aplicar Taylor Rule parece trivial (uma fórmula de cinco termos) mas a difficulty real reside em estimar os inputs.

**Input 1 — Natural rate (r\*)**

- Laubach-Williams é padrão para US, atualizada trimestralmente, disponível via NY Fed

- Holston-Laubach-Williams extends metodologia para US, EA, UK, CA

- EA r\* atual: ~0.2% real (ECB research)

- PT r\* requer customization (não existe oficial)

**Input 2 — Inflation (π_t)**

- BIS best practice: use core inflation (PCE core for US, HICP ex-energy-food for EA)

- Avoid headline CPI — too volatile

- YoY preferred over MoM annualized

**Input 3 — Inflation target (π\*)**

- Constant 2% for Fed, ECB, BoE, BoJ

- 3% for some EM (RBI India target range 2-6%, mid-point 4%)

- 2.5% for AU

**Input 4 — Output gap (y_t − y\*\_t)**

- Most controversial input — potential output is not observable

- IMF WEO publishes output gap estimates quarterly

- OECD publishes similar

- CBO publishes for US

- Major disagreements — CBO vs IMF vs OECD can differ 1-2pp

> *Para o SONAR: use IMF WEO as primary, OECD as cross-check, flag divergence as uncertainty signal.*

### 8.5 O problema do output gap na era pós-Covid
Output gap estimation became particularly problematic 2020-2024. Covid recession + fiscal stimulus + supply disruptions made "potential output" concept wobble.

49. **Supply disruptions.** Potential output typically assumes stable productivity trend. Supply chain disruptions + immigration changes temporarily lowered "realistic" potential, but dominant framework treated it as short-run supply shock.

50. **Labor market.** Workers exited labor force during Covid. Was this structural (reducing potential) or cyclical (will return)? Answer matters for gap estimation.

51. **Fiscal dominance.** US fiscal stimulus 2020-21 was ~25% of GDP cumulative. Some filtered through to aggregate demand; some went to savings. Stretch of potential vs stimulation of demand unclear.

Consequence for Taylor Rule: output gap input became unreliable 2020-24. Taylor Rule prescribed rates varied wildly depending on input choice. Fed used communication more than Taylor-style rules during this period.

> **Nota** *Lesson learned: Taylor Rule works well in "normal" times. During regime transitions, complement with other measures.*

### 8.6 Gap between actual policy and Taylor Rule — interpretation
Taylor Rule gap = Actual rate - Taylor prescribed rate.

| **Gap**            | **Interpretation**              | **Typical duration** |
|--------------------|---------------------------------|----------------------|
| Gap \> +1%         | Substantially tighter than rule | Rare, 2-3 months     |
| Gap +0.5% to +1%   | Moderately tighter              | Normal (overshoot)   |
| Gap -0.5% to +0.5% | Rule-consistent                 | Most common          |
| Gap -1% to -0.5%   | Moderately looser               | Normal (undershoot)  |
| Gap \< -1%         | Substantially looser than rule  | Rare, crisis periods |

**Key insight**

Gap alone is not diagnosis. Gap direction + duration matters.

- Positive gap e rising = tightening beyond rule = aggressive stance

- Positive gap e falling = re-converging to rule = normalizing stance

- Negative gap e falling = loosening beyond rule = stimulative

- Negative gap e rising = re-converging to rule = less stimulative

Patterns historically predictive: large negative gap followed by positive gap correlates with policy turning points (recession transitions, inflation acceleration).

### 8.7 Historical validation — did Taylor Rule describe actual policy?
Test against historical US data 1987-2024:

**Pre-2008 (Greenspan era)**

- Taylor Rule with r\* = 2% (pre-ZLB assumption) and 0.5 coefficients

- Fitted actual policy with R² ~0.7

- Gap typically ±0.25%

- Major divergences: 2003-2005 (Fed held rates too low relative to Taylor — Taylor argued this contributed to housing bubble)

**Post-2008 to 2015 (ZLB era)**

- Taylor Rule prescribed negative rates

- Fed stuck at ZLB + QE

- Gap ranged -2% to -4% (Fed much looser than Taylor implied)

- QE was non-Taylor response

**Post-2015 to 2019 (normalization era)**

- Fed hiked slowly, remained below Taylor-prescribed rate

- Persistent negative gap ~-1%

**2020-2024 (pandemic era)**

- Taylor Rule prescribed steep hikes by mid-2021

- Fed delayed until March 2022

- Peak gap: -3.5% in 2022 (Fed far below prescribed)

- Rapid catch-up Q2 2022-Q4 2023

> *Lesson: Taylor Rule has been a useful benchmark but Fed deviates meaningfully during regime transitions. Gap is informative about BC choices, not just mechanical errors.*

### 8.8 Taylor Rule for non-Fed BCs — adaptations
**ECB**

- r\* = 0.2% (ECB estimate 2024)

- π\* = 2.0% symmetric

- π = HICP core YoY

- Output gap = EA aggregate (IMF WEO)

**BoE**

- r\* = 0.5% (BoE working paper estimate)

- π\* = 2.0%

- π = CPI YoY (UK target)

- Output gap = UK (OBR estimate)

**BoJ**

- Taylor Rule has less relevance — BoJ frequently ignored Taylor for decades

- BoJ's behavior more explainable by discretionary framework

- Still worth computing as comparative benchmark

**PBoC**

- Taylor Rule fundamentally inapplicable — PBoC has multiple tools, multi-objective

- Use as rough benchmark but expect large deviations

- Consider PBoC-specific reaction function estimates from literature

### 8.9 M2 implementation in SONAR
For each covered BC, SONAR computes:

> M2_Taylor_1993_gap_t = actual_rate_t - Taylor_1993_prescribed_t
> M2_Taylor_1999_gap_t = actual_rate_t - Taylor_1999_prescribed_t
> M2_Taylor_inertia_gap_t = actual_rate_t - Taylor_inertia_prescribed_t
> M2_Taylor_forward_gap_t = actual_rate_t - Taylor_forward_prescribed_t
> M2_aggregate_gap_t = median(M2_Taylor_1993, M2_1999, M2_inertia, M2_forward)
> M2_uncertainty_t = range(M2_four_variants)

**Classification**

- M2_aggregate \> +1%: Tight vs rule

- M2_aggregate in \[-1%, +1%\]: Rule-consistent

- M2_aggregate \< -1%: Loose vs rule

When uncertainty \> 1%: flag "regime transition" — BC operating outside normal rule-based framework.
