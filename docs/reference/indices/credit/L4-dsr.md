# L4 · DSR

> Sub-índice do Ciclo de Crédito (CCCS) — capítulo 10 do manual (Manual_Ciclo_Credito_COMPLETO).

### 10.1 Por que DSR supera credit gap para horizonte curto
Drehmann & Juselius (2012 BIS Quarterly; 2014 IJF) documentaram um resultado empiricamente forte: o DSR supera todos os outros indicadores para prever crises bancárias com horizonte 1-2 anos forward.

AUC (Area Under ROC Curve) comparativa para previsão de crises bancárias em painel de 26 países:

| **Indicador**           | **AUC 3-5 anos forward** | **AUC 1-2 anos forward** |
|-------------------------|--------------------------|--------------------------|
| Credit-to-GDP gap (BIS) | 0.84                     | 0.76                     |
| House price gap         | 0.79                     | 0.72                     |
| Credit growth YoY       | 0.73                     | 0.68                     |
| Current account / GDP   | 0.66                     | 0.61                     |
| DSR deviation           | 0.71                     | 0.89                     |

> *Credit gap é melhor para horizonte longo (3-5 anos); DSR é melhor para horizonte curto (1-2 anos). Os dois são complementares, não substitutos.*

### 10.2 A fórmula BIS — derivação
O DSR pretende medir a fração do rendimento que vai para servir dívida. Definição conceptual:

*DSR_t = (Interest payments_t + Amortizations_t) / Income_t*

O problema operacional é que "amortizations" não é diretamente observável agregado. Drehmann-Juselius (2015) desenvolveram uma fórmula tratável usando conceitos standard de finance:

*DSR_t = \[ i_t / (1 − (1 + i_t)^(−s_t)) \] × (D_t / Y_t)*

Onde:

- *i_t* = lending rate média sobre stock de dívida (em decimal, per period).

- *s_t* = maturity residual média do stock (em períodos).

- *D_t / Y_t* = debt-to-income ratio.

### 10.3 Desconstrução da fórmula
O primeiro termo, *i / \[1 − (1+i)^(−s)\]*, é conhecido em finance como annuity factor — a fração do principal de um empréstimo amortizado que tem de ser paga cada período (juros + amortização) assumindo amortização constante.

Exemplo: mortgage de €100k a 3% a 25 anos. Annuity factor mensal = 0.03/12 / \[1 − (1+0.03/12)^(−25·12)\] = 0.00474. Pagamento mensal = €100k × 0.00474 = €474.

Aplicado a um país: se *i = 3%* annualized e *s = 15 anos* maturity média, annuity factor = 0.084. Multiplicado por debt-to-GDP de (digamos) 150% = DSR de 12.6%.

### 10.4 Os três inputs e as suas fontes
**Input 1 — Lending rate (i)**

Precisamos da média ponderada das lending rates sobre o stock de dívida. Ideal: weighted by outstanding debt, por segmento (households vs corporates).

Fontes por ordem de preferência:

- BIS publica diretamente para 32 países como input para o DSR.

- ECB para euro area (diversos breakdowns).

- National central banks (typically in Financial Stability Reports).

- Trading Economics Bank Lending Rate — aproximação razoável.

**Input 2 — Maturity residual (s)**

O mais difícil de obter. BIS assume maturidade fixa e constante para households (~18 anos, typical mortgage weighted) e corporates (~10 anos).

Para o SONAR, recomendação: usar assumptions BIS standard por segmento a menos que haja razão específica para o país (ex. crescimento recente de long-term mortgages em Portugal pode ter subido a maturidade residual acima de 18 anos).

**Input 3 — Debt-to-income (D/Y)**

O mais fácil de obter. BIS publica; ECB publica; Trading Economics publica.

Para a fórmula BIS total PNFS, income é GDP. Para sub-agregados (household DSR), income é disposable household income.

### 10.5 Thresholds empíricos
Drehmann-Juselius identificaram que desvios do DSR face à sua média histórica do país são mais informativos que níveis absolutos (que variam estruturalmente entre países).

| **Desvio DSR face à média (pp)** | **Probabilidade crise 1-2 anos** |
|----------------------------------|----------------------------------|
| \< +2 pp                         | Baseline (~5%)                   |
| +2 a +6 pp                       | Alerta (~30%)                    |
| \> +6 pp                         | Zona crítica (~85%)              |

> **Nota** *Para Portugal: DSR médio histórico ~17-18%. Threshold de alerta em ~20%, zona crítica em ~23-24%. Em 2008-09, o DSR português subiu acima de 22% — totalmente dentro da zona crítica, consistente com a crise subsequente.*

### 10.6 DSR por segmento — o breakdown crítico
BIS publica DSR total PNFS para 32 países. Para 17 países, publica também o breakdown households vs non-financial corporates.

**Por que o breakdown importa**

Um mesmo DSR total pode esconder dinâmicas muito diferentes. Exemplo hipotético:

- **País A:** DSR total 17% = 12% households + 24% corporates.

- **País B:** DSR total 17% = 22% households + 12% corporates.

País B tem risco de consumption shock muito superior (household leverage alto). País A tem risco de investment shock (corporate leverage alto). Recomendação policy e posicionamento asset allocation divergem.

Para o SONAR: sempre que disponível, usar o breakdown. Para os 15 países sem breakdown, sinalizar esta limitação no dashboard.

### 10.7 Aproximação quando dados estão incompletos
Se um país não está nos 32 do BIS mas queremos construir DSR aproximado:

**Aproximação de 1ª ordem**

*DSR_t ≈ i_t × (D_t / Y_t)*

(ignora amortizations, captura só interest burden). Correlação com DSR full fórmula em backtest: ~0.85. Bom proxy.

**Aproximação de 2ª ordem**

*DSR_t ≈ i_t × (D_t / Y_t) + (D_t / Y_t) / s_t*

(assume amortização linear, usa maturity standard). Correlação com DSR full: ~0.95. Próximo de bom.

**Recomendação SONAR**

- Países BIS (32): usar DSR oficial direto.

- Países não-BIS mas com data suficiente: computar aproximação de 2ª ordem.

- Países sem data suficiente: usar apenas debt-to-income growth como proxy (informação mais limitada mas ainda útil).

### 10.8 Por que o DSR brilha em regimes de subida de taxas
Aqui está a razão técnica pela qual DSR é tão poderoso agora (2024-25). Taxas de juro subiram materialmente em 2022-23. Mas o credit stock não caiu — apenas parou de crescer. O que isto implica para DSR?

*Δ DSR_t ≈ Δi_t × (D_t / Y_t) + i_t × Δ(D_t / Y_t)*

Primeiro termo: mudança da rate × stock de dívida. Segundo termo: rate × mudança do stock.

Em 2022-23 globalmente: primeiro termo explodiu (taxas +300-500bps), segundo termo foi próximo de zero ou ligeiramente positivo. Resultado: DSRs subiram materialmente mesmo sem credit boom.

**Países em zona crítica DSR em 2024 (BIS Q3 data)**

| **País**  | **DSR actual** | **Baseline histórica** | **Desvio** |
|-----------|----------------|------------------------|------------|
| Austrália | ~22% (PNFS)    | ~18%                   | +4 pp      |
| Noruega   | ~15% (HH)      | ~11%                   | +4 pp      |
| Korea     | ~14% (HH)      | ~9%                    | +5 pp      |
| Portugal  | ~18% (PNFS)    | ~16%                   | +2 pp      |
| Suécia    | ~13% (HH)      | ~9%                    | +4 pp      |

> *O DSR é onde o next leg do stress está visível primeiro. Os credit gaps estão normais em muitos países (longo período de desalavancagem pós-2012), mas os DSRs estão a explodir. É uma vulnerabilidade nova, não identificada pelos indicadores tradicionais. Material de coluna fresco.*

**Encerramento da Parte III**

Fecha-se o módulo de medição. O que o SONAR agora sabe fazer conceptualmente:

- **L1** — mede o stock absoluto (contexto estrutural). Usa BIS Q-series (total credit PNFS) como primary; F-series apenas como fallback.

- **L2** — mede desvios cíclicos. Dual reporting HP λ=400,000 + Hamilton (2018). Sinal de alta confiança quando ambos concordam — reduz false positive rate de ~23% para ~8%.

- **L3** — mede momentum do flow. Credit impulse Biggs-Mayer-Pick como segunda derivada do stock. Lead de 2-4 trimestres face a GDP growth.

- **L4** — mede burden real. DSR Drehmann-Juselius com fórmula completa para 32 países BIS; aproximações de 2ª ordem para cobertura alargada. AUC 0.89 para horizonte 1-2 anos — o preditor mais poderoso isoladamente.

**Material de coluna disponível a partir da Parte III**

47. "Por que Basileia III usa λ=400,000 — e o que isso diz sobre monetary vs credit cycles." Pedagógico técnico, acessível ao leitor qualificado.

48. "O indicador que o mercado ignora — credit impulse chinês antecipa tudo." Ângulo China, conjuntural, alta atualidade.

49. "DSR — como taxas mais altas estão a criar stress onde ninguém olha." Tese forte, diferenciadora, sustentada em dados BIS 2024.

50. "Portugal em 2009 — quando o DSR previu o que os economistas negavam." Olhar retrospectivo, aplicação do framework ao caso nacional.

***A Parte IV — Indicadores complementares (capítulos 11-14)** adiciona as camadas de soft data (bank lending surveys), market data (spreads de crédito), e lagging validation (NPL, housing).*

# PARTE IV
**Indicadores complementares**

*Surveys, spreads, NPL, housing — as camadas não-BIS*

**Capítulos nesta parte**

**Cap. 11 ·** Bank lending surveys — o soft data mais preditivo

**Cap. 12 ·** Spreads de crédito — o mercado vê o que os bancos não dizem

**Cap. 13 ·** NPL, bank capital, stress materializado

**Cap. 14 ·** Housing — o amplificador crítico
