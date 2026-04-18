# L3 · Credit impulse

> Sub-índice do Ciclo de Crédito (CCCS) — capítulo 9 do manual (Manual_Ciclo_Credito_COMPLETO).

### 9.1 Conceito e derivação
O credit impulse, introduzido formalmente por Biggs, Mayer e Pick (2010) no paper "Credit and Economic Recovery: Demystifying Phoenix Miracles", resolve um problema conceptual importante.

> *O problema: é o nível de credit, ou a mudança de credit, que contribui para a procura agregada? A resposta BMP: a contribuição marginal é a segunda derivada — não o credit stock (nível), nem o credit flow (primeira derivada), mas a mudança na taxa de fluxo.*

Por que? Porque a contribuição do crédito para o spending agregado é o flow of new credit, não o stock. E a mudança no spending é determinada pela mudança no flow. Segunda derivada.

### 9.2 A formulação matemática
*Credit Impulse_t = Δ(Credit flow)\_t / GDP\_{t−1} = Δ² Credit_t / GDP\_{t−1}*

Em forma equivalente (sobre 4 trimestres para suavização):

*CI_t = \[(Credit_t − Credit\_{t−4}) − (Credit\_{t−4} − Credit\_{t−8})\] / GDP\_{t−4} × 100*

**Interpretação passo a passo**

- *Credit_t − Credit\_{t−4}* = credit flow últimos 4 trimestres.

- *Credit\_{t−4} − Credit\_{t−8}* = credit flow nos 4 trimestres anteriores.

- Diferença entre os dois = aceleração do flow.

- Dividido por GDP para normalizar.

### 9.3 Por que o credit impulse lidera o ciclo económico
Intuição económica: o PIB cresce porque pessoas / firmas gastam dinheiro. Novo crédito é uma fonte de spending (households compram casas endividando-se, firmas investem com empréstimos). Logo:

*Δ GDP_t ∝ Δ Spending_t ∝ Δ(New credit)\_t = Δ² Credit_t*

Esta proposição é empiricamente robusta. Biggs-Mayer-Pick (2010) mostraram que credit impulse tem lead de 2-4 trimestres face a GDP growth em 15 economias avançadas.

### 9.4 Interpretação dos estados
| **Estado**             | **CI value**       | **Interpretação**      | **Implicação**                |
|------------------------|--------------------|------------------------|-------------------------------|
| Positivo e a acelerar  | CI \> 0 e a subir  | Tailwind crescente     | Aceleração económica provável |
| Positivo a desacelerar | CI \> 0 mas a cair | Perda de momentum      | Warning signal                |
| Zero                   | CI ≈ 0             | Credit flow constante  | Growth neutro do crédito      |
| Negativo               | CI \< 0            | Credit flow a contrair | Headwind ativo                |

O terceiro caso (positivo mas desacelerar) é o mais subtil. Tecnicamente, credit ainda está a expandir — os dados absolutos mostram growth. Mas a segunda derivada já virou. Este é um sinal subtilmente early warning que poucos analistas olham.

### 9.5 O caso chinês — onde o credit impulse é mandatory
Para analisar a China, o credit impulse é provavelmente o indicador single mais importante. Razão: a economia chinesa é literalmente conduzida pelo crédito — via bank loans, shadow banking, LGFV debt, e policy-directed lending. Quando Beijing "abre as torneiras", o primeiro sinal observável é o credit impulse.

**Historicamente**

- Pico credit impulse CN early 2009 → GDP rebound 2009-2010.

- Pico credit impulse CN early 2016 → global reflation 2016-2017.

- Pico credit impulse CN end 2020 → global reflation 2021.

> **Nota** *Para coluna: o credit impulse global (US + EA + CN weighted by GDP) é um indicador quase proprietário de ninguém em Portugal. Seguir este agregado e comentar virages é material diferenciador.*

### 9.6 Variantes e refinamentos
**Variante 1 — Credit impulse por segmento**

Separar households vs corporates. Em algumas economias, os dois segmentos divergem. Um CI corporate positivo + CI household negativo é um sinal específico (investment-led recovery com consumer caution).

**Variante 2 — Moving average smoothing**

CI raw é ruidoso. Aplicar MA(4) trimestres suaviza sem perder lead significativamente.

**Variante 3 — Standardization por country**

Normalizar CI face à sua distribuição histórica no país específico. Útil para comparar across-country.
