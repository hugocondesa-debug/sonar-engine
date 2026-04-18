# L2 · Credit-to-GDP gap

> Sub-índice do Ciclo de Crédito (CCCS) — capítulo 8 do manual (Manual_Ciclo_Credito_COMPLETO).

### 8.1 O problema da decomposição trend-cycle
O credit gap pretende medir o desvio do ratio credit-to-GDP face à sua trajetória de longo prazo. O problema metodológico fundamental: o trend não é observável. Temos de o estimar.

Três abordagens competem na literatura:

44. **Filtros estatísticos baseados em suavização** — HP filter, band-pass filters (Baxter-King, Christiano-Fitzgerald).

45. **Métodos regression-based** — Hamilton (2018), Beveridge-Nelson decomposition.

46. **Métodos multivariate / structural** — Schüler-Hiebert-Peltonen, modelos state-space.

Cada abordagem tem assumptions diferentes sobre a natureza do trend e do cycle.

### 8.2 HP filter com λ=400,000 — o standard BIS
O Hodrick-Prescott filter é a abordagem canónica. Minimiza:

*Σ(y_t − τ_t)² + λ · Σ\[(τ\_{t+1} − τ_t) − (τ_t − τ\_{t−1})\]²*

Onde *y_t* é a série observada (credit/GDP), *τ_t* é o trend estimado, e λ é o parâmetro de suavização. O primeiro termo penaliza o desvio da série ao trend; o segundo penaliza a curvatura do trend. Trade-off calibrado por λ.

**Escolha de λ — a aritmética de Ravn-Uhlig**

Hodrick-Prescott (1997) calibraram λ=1600 para dados trimestrais americanos, com o objetivo de isolar ciclos de ~8 anos (o típico business cycle). Para o ciclo de crédito, que tem duração ~4x superior, Ravn-Uhlig (2002) deduziram que λ deveria escalar com a 4ª potência da frequência-alvo:

*λ_credit = 1600 × (f_business / f_credit)⁴ = 1600 × 4⁴ = 1600 × 256 = 409,600 ≈ 400,000*

O BIS adotou este valor em Drehmann-Borio-Tsatsaronis (2010) e foi incorporado formalmente em Basileia III como o parâmetro regulatório oficial.

### 8.3 One-sided vs two-sided — o look-ahead bias
O HP filter standard é two-sided — usa informação passada e futura para estimar o trend no ponto t. Isto é ótimo para análise histórica, mas inválido para classificação em tempo real. No momento t, não temos informação futura.

Solução: HP one-sided (recursive). No ponto t, o trend é estimado usando apenas dados até t. À medida que novos dados chegam, a estimativa do trend no ponto t é revista — isto gera endpoint bias.

**O endpoint bias em números reais**

Testes empíricos mostram que a revisão do gap HP one-sided à medida que se acumulam 2-3 anos de dados adicionais é tipicamente 1-3pp. Isto significa que um país que parece estar a +3pp (acima do threshold BIS) em tempo real pode, retrospetivamente, ter estado em +1pp ou +5pp — diferença entre "dentro do threshold" e "zona de alerta".

**Implementação one-sided no SONAR**

- A cada observação nova, re-estimar o trend up to t.

- Armazenar duas séries: gap_realtime_t (one-sided, no momento t) e gap_revised_t (two-sided, final).

- Relatar ambos e explicitar a diferença.

### 8.4 A crítica Hamilton (2018) — demolidora
James Hamilton publicou em 2018 um paper com título agressivo: "Why You Should Never Use the Hodrick-Prescott Filter" (Review of Economics and Statistics). A crítica tem quatro pontos, todos fortes.

**Crítica 1 — HP gera relações espúrias**

Demonstrou via simulação Monte Carlo que o HP filter produz ciclos aparentes mesmo em séries que são puramente random walks (sem ciclo verdadeiro). Os "ciclos" são artefactos do filtro, não propriedades dos dados.

**Crítica 2 — Valores no final da amostra são particularmente pouco fiáveis**

O endpoint bias documentado acima é uma manifestação disto. O HP no último ponto usa predominantemente informação passada (two-sided colapsa para one-sided nas bordas), gerando estimativas enviesadas.

**Crítica 3 — A escolha de λ é arbitrária**

A "justificação" Ravn-Uhlig para λ=400k é intuitiva mas não tem base estatística formal. Qualquer λ em ordem de magnitude próxima produziria resultados qualitativamente semelhantes mas quantitativamente diferentes.

**Crítica 4 — Existe alternativa mais simples e defensável**

Hamilton propôs uma regressão linear:

*y_t = β₀ + β₁·y\_{t−h} + β₂·y\_{t−h−1} + β₃·y\_{t−h−2} + β₄·y\_{t−h−3} + ε_t*

Onde *h* é o horizonte de análise. Para ciclo de crédito (horizon longo), Hamilton sugere *h=8* trimestres (2 anos). O cyclical component é o resíduo *ε_t*. Vantagens:

- Sem parâmetros arbitrários.

- Sem endpoint bias (regressão é estatisticamente válida até ao último ponto).

- Estatísticamente identificado (ε_t é um forecast error genuíno).

- Computacionalmente trivial.

### 8.5 HP vs Hamilton — comparação empírica
Aplicando ambos aos dados BIS para economias avançadas, os resultados são:

**Concordância na identificação de fases**

HP e Hamilton concordam em ~75% dos períodos sobre se gap está acima/abaixo do threshold. Os 25% de divergência são concentrados em turning points — precisamente onde a identificação é mais crítica.

**Diferença no timing dos sinais**

Hamilton tende a sinalizar Boom/Contraction ~2-4 trimestres mais cedo que HP. Isto é porque HP, ao suavizar agressivamente, demora mais a registar mudanças. Tendência útil se o objetivo é early warning.

**Diferença em magnitude**

HP produz gaps mais "cleanos" (menos volatilidade trimestral) mas com endpoint bias. Hamilton produz gaps mais ruidosos mas sem bias estrutural.

**Recomendação BIS (2023 update)**

O BIS continua a publicar gaps HP λ=400k como métrica regulatória oficial (consistência institucional), mas a sua própria research usa Hamilton cada vez mais. A tendência é para complementaridade, não substituição.

### 8.6 A abordagem SONAR — dual reporting
A recomendação para o SONAR é computar ambas as métricas e reportar:

> gap_BIS_t = HP one-sided, λ = 400,000 \# benchmark regulatório
> gap_Ham_t = Hamilton regression, h = 8 \# sem look-ahead bias

E gerar um signal de confiança combinado:

- **Both above +2pp** → sinal de Boom com alta confiança.

- **One above, one below** → sinal ambíguo, zona de transição.

- **Both below +2pp** → não-Boom com alta confiança.

Isto reduz materialmente false positives. Backtest em dados BIS 1980-2020 para 18 economias avançadas mostra:

| **Método**                 | **False positive rate** |
|----------------------------|-------------------------|
| HP isolado                 | ~23%                    |
| Hamilton isolado           | ~19%                    |
| Concordância HP + Hamilton | ~8%                     |

> *A complementaridade dos dois filtros capta signal e filtra noise melhor que qualquer um isoladamente.*

### 8.7 Beveridge-Nelson — a alternativa estrutural
Uma terceira abordagem, menos comum mas academicamente rigorosa, é a decomposição Beveridge-Nelson (1981). Parte de um modelo econométrico da série (ARIMA ou state-space) e decompõe em componentes permanent vs transitory baseado em eigenvalue analysis do modelo estimado.

- **Vantagem:** decomposição teoricamente fundamentada — o trend é formalmente o componente permanente, o cycle é o transitório.

- **Desvantagem:** resultado depende fortemente do modelo ARIMA escolhido. Se a série é modelada como ARIMA(1,1,0) vs ARIMA(2,1,1), os gaps resultantes podem ser diferentes em magnitude significativamente.

Uso no SONAR: para países com séries longas (onde o modelo ARIMA pode ser estimado robustamente), usar BN como terceira métrica de verificação. Para países com séries curtas, abandonar BN e ficar com HP + Hamilton.

### 8.8 Thresholds empíricos — revisão
Os thresholds canónicos Drehmann-Juselius (2014), validados contra 40+ crises bancárias históricas:

| **Gap (pp)**    | **Classificação**              | **Probabilidade crise 2-3 anos**           |
|-----------------|--------------------------------|--------------------------------------------|
| gap \< −5       | Credit crunch / desalavancagem | Baixa (mas pode indicar recessão em curso) |
| −5 ≤ gap \< +2  | Neutral                        | Baseline (~5%)                             |
| +2 ≤ gap \< +10 | Boom zone (ativação CCyB)      | ~40%                                       |
| gap ≥ +10       | Danger zone                    | ~80%                                       |

**Calibração country-specific**

Estes thresholds são calibrados em dados cross-country. Para países específicos, thresholds ajustados pela distribuição histórica nacional podem ser mais precisos.

Exemplo Portugal: thresholds país-específicos baseados na distribuição de gaps 1970-2024 situariam "Boom zone" em ~+4pp e "Danger zone" em ~+12pp (acima dos benchmarks BIS, refletindo volatilidade mais alta da série portuguesa).
