# M1 · Effective rates e shadow rates

> Sub-índice do Ciclo Monetário — capítulo 7 do manual (Manual_Ciclo_Monetario_COMPLETO).

### 7.1 O que medir — stance em vez de policy rate
A tentação natural ao classificar stance monetária é olhar para a policy rate visível (IORB no Fed, DFR no ECB, Bank Rate no BoE) e compará-la a algum benchmark. Este approach falha fundamentalmente em três situações comuns em economia moderna:

- **Falha 1 — Zero Lower Bound.** Quando policy rate está em 0% e BC está a fazer QE massiva, policy rate visível é uninformativa. Stance real é muito mais accommodative que 0% sugere — QE adiciona accommodation equivalent a vários rate cuts adicionais.

- **Falha 2 — Negative rates.** Quando policy rate é -0.5% (ECB 2019-22), o rate visível pode subestimar stance real porque transmissão é partial (bancos não passam negative rates).

- **Falha 3 — Balance sheet effects.** BC pode estar com rates pausadas mas balance sheet em QT. Stance efetiva pode estar tightening mesmo sem rate moves.

A solução conceptual é medir stance efetiva — uma métrica que incorpora todos os instrumentos (rate + balance sheet + forward guidance) numa única variável comparável ao longo do tempo e entre BCs.

> *A literatura convergiu numa solução: shadow rates.*

### 7.2 Shadow rates — o que são e o que representam
A shadow rate é a policy rate hipotética que, num mundo sem ZLB, produziria o mesmo stance efetivo que a combinação atual de policy rate + QE + forward guidance. Em palavras simples: "Se o BC pudesse ter rate negativa infinitamente, que rate teria hoje para produzir este nível de accommodation?"

Durante 2008-2022, shadow rates para Fed e ECB foram muitas vezes materialmente negativas — às vezes -3% a -5%. Durante QT e hiking 2022-24, shadow rates convergiram com policy rates (porque QE effects reverted).

**Características conceptuais**

- Shadow rate = policy rate quando rates estão em território positivo e sem QE ativa

- Shadow rate \< policy rate quando QE está ativa (adiciona accommodation)

- Shadow rate pode ser significativamente negative (Fed em 2014: policy rate 0-0.25%, shadow rate ~-3%)

- Shadow rate re-converge com policy rate quando QE é retirada

Duas metodologias dominam a literatura para estimar shadow rates: Wu-Xia e Krippner. Ambas derivam shadow rates de term structure models, usando yield curve completa como input.

### 7.3 A metodologia Wu-Xia (2016)
Jing Cynthia Wu (Yale) e Fan Dora Xia (BIS, ex-Fed) publicaram em 2016 o paper Measuring the Macroeconomic Impact of Monetary Policy at the Zero Lower Bound no Journal of Money, Credit and Banking. É a metodologia shadow rate mais citada em literatura empírica.

**Framework**

Shadow Rate Term Structure Model (SRTSM). Observa-se yield curve completa em cada ponto no tempo. O modelo extrai o "shadow short rate" — a rate que seria implied pela yield curve num mundo sem ZLB.

**Intuição técnica**

- Em ambiente normal, yield curve slope reflete expectations de future rates + term premium

- Em ZLB, curve é "censurada" — short rates não podem ir abaixo de zero, mas market pricing de medium-term yields ainda reflete expectations

- SRTSM inverte o problema: dado yield curve observada, infere a shadow rate que racionalizaria a curve

**Inputs**

Yields em múltiplas maturities (3M, 6M, 1Y, 2Y, 5Y, 10Y), daily ou weekly frequency.

**Outputs**

Shadow rate series + confidence intervals.

Fed Wu-Xia shadow rate está publicamente disponível via FRED (série ID: WXSRUS), atualizada mensalmente. Cobertura: US monthly desde 1960.

**Empirical findings**

- Fed: shadow rate atingiu mínimo de -2.99% em May 2014 (durante QE3)

- ECB: shadow rate mínimo de -7.56% em 2020 (combined QE + NIRP)

- BoJ: shadow rate permanentemente negativa desde 1995, mínimos de -6% durante QQE

> **Nota** *Implementação para SONAR: podemos replicar Wu-Xia para qualquer país com yield curve data disponível. Dados-chave: Treasuries US via FRED, bunds via ECB SDW ou Bundesbank, gilts via BoE, JGBs via BoJ/MoF. Implementation requires non-linear Kalman filter estimation — disponível em pacotes Python (pyshadowrate) ou como replicable recipe.*

### 7.4 A metodologia Krippner (2013, 2015)
Leo Krippner (Reserve Bank of New Zealand, ex-fellow na Fed) desenvolveu metodologia alternativa, publicada em Journal of International Money and Finance (2013) e refinada em Zero Lower Bound Term Structure Modeling (Palgrave, 2015).

**Diferença fundamental face a Wu-Xia**

- **Wu-Xia:** modela yield curve como function do shadow rate + 2 factors latentes

- **Krippner:** usa estimação mais direta via aproximação "2+1 factor" — 2 factors do yield curve + 1 explicit ZLB constraint

**Vantagens de Krippner**

- Computationally simpler

- More stable across different yield curve shapes

- Produces slightly less volatile estimates during rapid regime changes

**Desvantagens**

- Less theoretically elegant

- Some arbitrage considerations are not fully handled

**Empirical differences**

Wu-Xia e Krippner produce similar shadow rate estimates quase sempre — correlação \>0.95 em sample overlapping. Divergências tendem a ser em períodos de rapid change ou curve distortions (e.g., March 2020 flash crash).

**Disponibilidade**

Krippner publica estimates on seu site pessoal (leo-krippner.com) mensalmente para US, UK, ECB, BoJ, BoC, RBA. Free access.

### 7.5 Shadow rates para países non-major — o problema da cobertura
Shadow rates canónicos (Wu-Xia, Krippner) cobrem major economies. Para Cluster 2 EU (Portugal, Espanha, Itália), não há shadow rate oficial — porque policy rate é ECB-level, não country-level.

**Três workarounds operacionais**

***Workaround 1 — Country-level "effective policy stance"***

Para Portugal especificamente, stance real é função de:

- ECB policy rate (DFR)

- Spread PT sovereign bond (reflects additional premium)

- Domestic MIR (MFI Interest Rates for new lending)

Construímos EPS_PT = DFR_ECB + f(spread PT, MIR PT) como proxy.

***Workaround 2 — Shadow rate do ECB + country adjustment***

Take ECB-level shadow rate (Krippner publica), adjust by país-specific spread component. Simple, reasonably accurate.

***Workaround 3 — Country yield curves directly***

Para países maiores (DE, FR, IT), yield curve nacional é sufficient para estimar shadow rate local via same methodology as Wu-Xia. Mais complex mas mais rigoroso.

> **Nota** *Recomendação SONAR: Workaround 2 para SONAR v1 (simples, implementável rapidamente). Workaround 1 para refinement v2.*

### 7.6 Shadow rates vs real rates — duas métricas complementares
Importante não confundir shadow rate com real rate.

- **Shadow rate** = taxa nominal ajustada para capturar unconventional policy tools. Medida em nominal space.

- **Real rate** = taxa nominal minus inflation expectations. Medida em real space.

São duas dimensões ortogonais. Uma política monetária pode ser:

- Nominal shadow rate elevada mas real rate baixa (alta inflação: Fed 1980 com nominal rate 15% mas expected inflation 12% → real rate 3%)

- Nominal shadow rate baixa mas real rate alta (baixa inflação: Japan 1995 com nominal rate 0.5% mas expected inflation -1% → real rate 1.5%)

> *Para classificação de stance no SONAR, real rate é teoricamente superior porque é o que afeta decisões económicas. Mas operacionalmente, usamos ambas — nominal shadow rate para comparabilidade cross-country, real shadow rate (shadow rate - inflation expectations) para stance económico.*

Inflation expectations proxy: usamos inflation swaps (5Y5Y forward breakeven) ou survey-based expectations (Philadelphia Fed SPF para US, ECB SPF para EA). Avoid CPI itself — é backward-looking.

### 7.7 Implementação operacional no SONAR — M1 layer
A layer M1 no SONAR computa, para cada country / BC:

> M1_nominal_stance_t = shadow_rate_t (Wu-Xia ou Krippner)
> M1_real_stance_t = shadow_rate_t - inflation_expectations_t
> M1_stance_vs_neutral_t = M1_real_stance_t - r_star_t

Onde r_star é a natural rate estimada (Laubach-Williams para US, ECB estimate para EA, equivalents para outros).

**Classification thresholds**

| **M1_stance_vs_neutral** | **Classificação**      |
|--------------------------|------------------------|
| \> +1%                   | Tight                  |
| -1% a +1%                | Neutral                |
| \< -1%                   | Accommodative          |
| \< -2%                   | Strongly Accommodative |

Estes thresholds são calibrados ao histórico empírico — BCs raramente se afastam mais de ±2% do neutral sem razão clara.

**Dashboard output example (Fed, April 2026)**

> Shadow rate (Wu-Xia): 4.25%
> Inflation expectations: 2.40%
> Real shadow rate: 1.85%
> r\* estimate (LW): 0.85%
> M1 stance vs neutral: +1.00%
> Classification: Tight
