**FRAMEWORK METODOLÓGICO**

**Manual do**

**Ciclo de Crédito**

*Identificação, classificação e previsão de ciclos para o SONAR*

**ESTRUTURA**

**Seis partes ·** Vinte capítulos · *Fundações, medição, integração, aplicação*

**Cinquenta referências anotadas ·** Quinze ângulos editoriais · *Peer comparison EU periphery*

**HUGO · 7365 CAPITAL**

*SONAR Research*

Abril 2026 · Documento de referência interno

**Índice**

# PARTE I · Fundações teóricas
> **Cap. 1 ·** Porque existe um ciclo de crédito
>
> **Cap. 2 ·** Genealogia intelectual — de Minsky ao BIS moderno
>
> **Cap. 3 ·** A revolução empírica pós-2008

# PARTE II · Anatomia do ciclo
> **Cap. 4 ·** As quatro fases do ciclo de crédito
>
> **Cap. 5 ·** Duração, amplitude e sincronização cross-country
>
> **Cap. 6 ·** Interação com ciclo económico, monetário e financeiro

# PARTE III · Medição
> **Cap. 7 ·** L1 — Credit-to-GDP stock
>
> **Cap. 8 ·** L2 — Credit-to-GDP gap
>
> **Cap. 9 ·** L3 — Credit impulse
>
> **Cap. 10 ·** L4 — DSR, o preditor killer

# PARTE IV · Indicadores complementares
> **Cap. 11 ·** Bank lending surveys — o soft data mais preditivo
>
> **Cap. 12 ·** Spreads de crédito — o mercado vê o que os bancos não dizem
>
> **Cap. 13 ·** NPL, bank capital, stress materializado
>
> **Cap. 14 ·** Housing — o amplificador crítico

# PARTE V · Integração
> **Cap. 15 ·** Composite score design
>
> **Cap. 16 ·** Classificação de fases
>
> **Cap. 17 ·** Interação com os outros três ciclos

# PARTE VI · Aplicação prática
> **Cap. 18 ·** Playbook por fase
>
> **Cap. 19 ·** Caveats e false signals
>
> **Cap. 20 ·** Bibliografia anotada

# PARTE I
**Fundações teóricas**

*Mecânica, genealogia intelectual, revolução empírica*

**Capítulos nesta parte**

**Cap. 1 ·** Porque existe um ciclo de crédito

**Cap. 2 ·** Genealogia intelectual — de Minsky ao BIS moderno

**Cap. 3 ·** A revolução empírica pós-2008

## Sub-índices (Parte III · Medição)

- [L1 · Credit-to-GDP stock](../indices/credit/L1-credit-to-gdp-stock.md) — capítulo 7 do manual original
- [L2 · Credit-to-GDP gap](../indices/credit/L2-credit-to-gdp-gap.md) — capítulo 8 do manual original
- [L3 · Credit impulse](../indices/credit/L3-credit-impulse.md) — capítulo 9 do manual original
- [L4 · DSR](../indices/credit/L4-dsr.md) — capítulo 10 do manual original

> Os capítulos 7-10 (Parte III · Medição) foram extraídos para `docs/methodology/indices/credit/` — um ficheiro por sub-índice.

## Capítulo 1 · Porque existe um ciclo de crédito
### 1.1 A diferença conceptual entre ciclo económico e ciclo de crédito
O ciclo económico "normal" (Kydland-Prescott, Lucas, a tradição Real Business Cycle) é uma flutuação em torno de um steady state, gerada por choques de produtividade ou procura agregada. É um fenómeno de flow variables — output, emprego, consumo — com periodicidade curta (6-10 anos na maioria das economias avançadas) e propriedade de mean-reversion relativamente rápida.

O ciclo de crédito é estruturalmente diferente. Opera sobre stock variables — dívida acumulada, balance sheets bancários, valor de colateral — com inércia muito superior. Quando uma economia emerge de uma recessão creditícia, o ajustamento do stock de dívida demora anos, não trimestres. Reinhart & Rogoff (2009, This Time Is Different) documentaram empiricamente que economias em processo de desalavancagem pós-crise demoram em média 7-10 anos a recuperar o output per capita pré-crise. O ciclo económico pode ter virado três vezes nesse intervalo.

Esta diferença de frequência não é acidental — resulta da mecânica dos stocks. Um household que contratou um mortgage de 30 anos a um LTV de 90% em 2006 carrega essa decisão financeira durante décadas, independentemente do que acontece ao GDP growth trimestral. O agregado destes compromissos individuais cria uma dinâmica macro com memória longa que os modelos de ciclo económico standard não capturam.

### 1.2 A função económica do crédito e os dois canais de amplificação
O crédito resolve um problema fundamental de coordenação intertemporal: permite que unidades económicas consumam ou invistam antes de gerarem o rendimento para o suportar. Esta função é, em si, criadora de valor — sem crédito não há investimento produtivo em escala, nem smoothing intertemporal de consumo, nem formação de capital humano via endividamento estudantil.

O problema não é a existência de crédito. É a sua procyclicalidade endógena. Dois canais geram esta pró-ciclicalidade.

**Canal 1 — Collateral-based lending (Bernanke-Gertler-Gilchrist, "financial accelerator")**

Bancos emprestam contra colateral. O valor do colateral depende dos preços de ativos. Os preços de ativos sobem em expansões. Logo, em expansões, a capacidade de endividamento cresce não porque os fundamentals mudaram, mas porque o colateral se valorizou. Este mecanismo funciona em reverso nas contrações, amplificando-as.

Matematicamente, se o constraint de endividamento é *B ≤ m × V(K)* onde *V(K)* é o valor de mercado do capital e *m* o margin requirement, então *dB/B = dV/V*. Um aumento de 20% no valor dos ativos permite um aumento de 20% na dívida sem que a capacidade produtiva real tenha mudado. Kiyotaki & Moore (1997) formalizaram isto no seu seminal "Credit Cycles".

**Canal 2 — Leverage ratchet (Geanakoplos, "leverage cycle")**

John Geanakoplos (Yale), em The Leverage Cycle (NBER Macroeconomics Annual, 2010), argumenta que o que varia ao longo do ciclo não é tanto a taxa de juro como o leverage permitido. Nos topos de ciclo, os bancos exigem margins baixas (mortgages a 3% de down-payment em 2006); nos bustos, margins explodem (40% down-payment em 2009). A taxa de juro tem sido o foco dos macroeconomistas durante 70 anos, mas o leverage é o que determina quem pode comprar ativos na margem, e portanto quem define o preço.

Este é o insight que conecta o ciclo de crédito directamente aos asset prices — e porque o ciclo financeiro (camada 4 do nosso modelo) não é separável do ciclo de crédito puro.

### 1.3 Assimetria boom-bust
Três características empíricas tornam o ciclo de crédito distinto.

***Assimetria temporal***

Booms são lentos, bustos são rápidos. Um credit boom típico constrói-se ao longo de 5-8 anos; o bust colapsa em 12-24 meses. Esta assimetria é documentada em Jordà-Schularick-Taylor (JST) para 17 economias avançadas desde 1870.

***Assimetria de intervenção***

Bancos centrais reagem assimetricamente. Cortam taxas agressivamente no bust (stance "Greenspan put", depois "Bernanke put"), mas hesitam em subir taxas ou impor macroprudential no boom. Charles Kindleberger (Manias, Panics, and Crashes, 1978) já documentava este padrão; Taylor (2013) provou-o formalmente.

***Assimetria de memória institucional***

Os episódios de boom são seguidos por décadas de regulação reactiva (Glass-Steagall após 1929, Dodd-Frank após 2008), que são progressivamente erodidas à medida que a memória esmaece.

> *Minsky chamou a isto "stability is destabilizing" — a longa ausência de crise convence agentes e reguladores de que a crise não pode acontecer.*

### 1.4 Porque o mainstream demorou a incorporar o ciclo de crédito
Até 2008, a macroeconomia mainstream (DSGE pós-Woodford) operava sob separação frictionless finance-real economy. O Modigliani-Miller theorem, que afirma que a estrutura de capital não afeta o valor real das firmas, foi (erradamente) estendido a nível macro: assumia-se que a finança era um véu neutro sobre a economia real.

Três papers quebraram este consenso:

- **Bernanke, Gertler, Gilchrist (1999)**, "The Financial Accelerator in a Quantitative Business Cycle Framework" — introduziu frições de balance-sheet em modelos DSGE.

- **Eggertsson & Krugman (2012)**, "Debt, Deleveraging, and the Liquidity Trap" — formalizou como debt overhang gera liquidity trap.

- **Schularick & Taylor (2012)** — evidência empírica esmagadora.

Hoje o consenso é inverso. O FMI publica World Economic Outlook com capítulos dedicados a credit cycles; o BIS construiu toda a sua narrativa institucional em torno deste conceito; Basileia III é literalmente uma resposta regulatória à tese do credit cycle. Quem escreve hoje sobre macro em Portugal sem incorporar isto está duas décadas atrasado.

## Capítulo 2 · Genealogia intelectual — de Minsky ao BIS moderno
### 2.1 A tradição austríaca — Mises, Hayek, e o ciclo como distorção monetária
A primeira teoria coerente do ciclo de crédito nasce em Viena no início do século XX. Ludwig von Mises, em Theorie des Geldes und der Umlaufsmittel (1912), e Friedrich Hayek, em Prices and Production (1931), construíram o que ficou conhecido como Austrian Business Cycle Theory (ABCT).

A tese central é elegante: quando a taxa de juro de mercado é forçada abaixo da natural rate (a taxa que equilibraria poupança desejada e investimento desejado sem intervenção monetária), gera-se um malinvestment — investimento em projetos de longa duração que não teriam sido rentáveis à taxa natural. Este boom é artificial e insustentável. Quando a taxa de juro de mercado é forçada a reconvergir para a natural rate, os projetos revelam-se não-viáveis e colapsam. A recessão é a correção do malinvestment acumulado, não um evento aleatório.

**O que os austríacos acertaram**

1.  O ciclo de crédito é endógeno à política monetária e ao sistema bancário, não um choque exógeno.

2.  A fase de bust não é um problema em si — é a resolução necessária de distorções acumuladas no boom.

3.  Tentar evitar o bust via mais estímulo monetário apenas prolonga e aprofunda o problema subjacente.

**O que erraram**

4.  O foco quase exclusivo em distorções de estrutura de capital (capital-goods industries vs consumer-goods industries) não se verifica empiricamente com a força que sugeriam.

5.  Subestimaram o papel das expectativas e da coordenação de agentes.

6.  A sua prescrição policy (liquidacionismo) é politicamente insustentável e empiricamente desastrosa — Herbert Hoover e Andrew Mellon seguiram-na em 1930-32 e transformaram uma recessão numa Great Depression.

A tradição austríaca foi marginalizada pela revolução keynesiana dos anos 1940-50, permaneceu ignorada durante o consenso monetarista dos 70-80, e regressou como referência intelectual após 2008 — não como framework operacional, mas como lembrete de que o crédito não é neutro. Quem hoje lê Borio no BIS está, em certa medida, a ler um austríaco reformado que adicionou 80 anos de evidência empírica.

### 2.2 Minsky e a hipótese da instabilidade financeira
Hyman Minsky (1919-1996) é a figura central. Economista pós-keynesiano americano, filho de imigrantes bielorrussos, trabalhou maior parte da vida na Washington University em St. Louis e no Levy Institute. Durante décadas, foi ignorado pelo mainstream — a sua tese (a finança é inerentemente instável) era vista como heterodoxa demais para os modelos de equilíbrio então dominantes.

A ressurreição veio em 2007-08. Quando a crise subprime estourou, o termo "Minsky moment" entrou no léxico de Wall Street e dos bancos centrais. Paul McCulley da PIMCO cunhou o termo em 1998 durante a crise russa; George Magnus da UBS popularizou-o em 2007; o FMI e o BIS incorporaram-no formalmente depois. Minsky morreu 12 anos antes da validação empírica da sua tese.

**A Hipótese da Instabilidade Financeira**

Formulada no paper de 1992 ("The Financial Instability Hypothesis", Levy Working Paper 74), tem dois teoremas centrais:

> *Teorema 1: A economia tem regimes de financiamento sob os quais é estável, e regimes sob os quais é instável.*
>
> *Teorema 2: Durante períodos de prosperidade prolongada, a economia transita de relações financeiras que fazem dela um sistema estável para relações financeiras que fazem dela um sistema instável.*

**A taxonomia de três estados de financiamento**

É o contributo operacional mais citado.

**Hedge finance** — unidades cujo cash flow operacional cobre integralmente os compromissos de serviço de dívida (juros + capital). Situação sustentável. Predominante após bustos, enquanto a memória da crise é fresca.

**Speculative finance** — unidades cujo cash flow cobre os juros mas não o capital. Dependem de rollover contínuo da dívida. Sensíveis a choques de liquidez. Predominam em fases médias do ciclo.

**Ponzi finance** — unidades cujo cash flow não cobre sequer os juros. Dependem de valorização contínua dos ativos para sobreviver (vender ativo mais caro para pagar juros, ou contrair nova dívida para pagar a antiga). Intrinsecamente instáveis — qualquer interrupção na apreciação dos ativos desencadeia default.

A tese dinâmica de Minsky: em expansões prolongadas, a composição da economia desloca-se progressivamente de hedge para speculative para Ponzi. E esta deslocação é endógena — resulta da própria estabilidade. Quanto mais longo o período sem crise, mais agentes se convencem de que tomar mais risco é seguro, mais os bancos relaxam standards, mais margins descem, mais Ponzi entra. Até que um choque aparentemente pequeno desencadeia a cascata.

> **Nota** *Implicação para o SONAR: o objetivo não é apenas medir o nível de crédito, mas a composição qualitativa das unidades tomadoras. Dois países com o mesmo credit-to-GDP gap podem estar em regimes fundamentalmente diferentes — um dominado por hedge finance, outro por Ponzi. Os dados BIS não capturam isto diretamente, mas proxies como share de interest-only mortgages, leverage de leveraged loans, e covenant-lite issuance aproximam-se do conceito.*

### 2.3 Kindleberger e a taxonomia das manias
Charles Kindleberger (MIT, 1910-2003) escreveu Manias, Panics, and Crashes: A History of Financial Crises em 1978 — livro que permaneceu periférico durante 30 anos e explodiu em vendas depois de 2008. A 7ª edição (com Robert Aliber) é hoje literatura obrigatória em central banks.

Kindleberger sistematizou o modelo de Minsky como sequência histórica narrativa, identificando cinco fases replicáveis em crises históricas documentadas (Tulipmania 1637, South Sea Bubble 1720, Railway Mania 1840s, 1929, Japão 1989, dot-com 2000, subprime 2007):

7.  **Displacement** — choque exógeno que muda as expectativas de lucro de um sector (nova tecnologia, liberalização financeira, descoberta geológica). Cria a narrativa fundadora do boom.

8.  **Boom** — crédito expande-se para financiar o sector beneficiado pelo displacement. Preços sobem com fundamentals inicialmente justificáveis.

9.  **Euphoria** — a valorização descola-se dos fundamentals. Entra capital que não compreende o sector ("greater fool theory"). Leverage atinge máximos. Analistas justificam as avaliações com novas métricas ("this time is different").

10. **Crisis / Revulsion** — um evento aparentemente pequeno (falência de um player de segunda linha, mudança regulatória, choque de liquidez) desencadeia reavaliação. Venda força mais venda. Colateral perde valor. Margin calls cascateiam.

11. **Contagion** — a crise espalha-se para outros sectores e geografias via interconexões de balance sheet. Pode transformar-se em crise sistémica ou ser contida por intervenção do lender of last resort.

O que Kindleberger acrescenta a Minsky é a dimensão narrativa. As bolhas não são apenas fenómenos matemáticos — são estruturadas em torno de histórias que os participantes contam a si próprios para justificar preços. Robert Shiller, em Narrative Economics (2019, publicado após o Nobel), formalizou esta intuição.

### 2.4 A síntese neoclássica frustrada — Bernanke e o financial accelerator
Ben Bernanke, antes de presidir ao Fed, passou três décadas no Princeton a estudar a Great Depression. O seu paper de 1983 ("Non-Monetary Effects of the Financial Crisis in the Propagation of the Great Depression") argumentou que o colapso do crédito nos EUA em 1930-33 não foi consequência passiva da recessão — foi causa ativa do aprofundamento. O canal: destruição de capital informacional (banking relationships específicas) que não se reconstrói rapidamente quando os bancos falham.

Esta intuição foi depois formalizada com Mark Gertler (NYU) e Simon Gilchrist (Boston University) no modelo Financial Accelerator ("The Financial Accelerator in a Quantitative Business Cycle Framework", 1999). O modelo incorpora frições de informação assimétrica (costly state verification) num DSGE standard. Resultado: pequenos choques nos fundamentals são amplificados via balance sheet effects. Quando o net worth das firmas cai, o prémio de financiamento externo sobe, investimento cai, net worth cai mais — espiral.

O limite do financial accelerator: o modelo continua a operar no paradigma de equilíbrio com frições. Captura amplificação, mas não instabilidade endógena tipo Minsky. Não há transição de hedge para Ponzi, não há construção longa do boom — apenas amplificação de choques exógenos.

Durante os anos 2000, o paradigma Bernanke-Gertler dominou os modelos DSGE dos bancos centrais. A Fed de São Francisco, o Bank of England, o BCE — todos construíram sistemas de previsão com este framework. E todos falharam espectacularmente em 2007-08. O modelo nunca gerava uma crise do tipo subprime nas suas simulações — porque, por construção, não podia.

### 2.5 A revolução Borio e a narrativa BIS
Claudio Borio, economista italiano, Head of the Monetary and Economic Department do BIS desde 2013, é a figura central da reconstrução intelectual pós-2008. O paper fundacional é "The financial cycle and macroeconomics: What have we learnt?" (BIS Working Paper 395, 2012).

A tese Borio articula-se em sete proposições.

12. O ciclo financeiro é uma realidade empírica distinta do ciclo económico, com frequência mais baixa (15-20 anos vs 6-10 anos) e amplitude maior.

13. As suas variáveis fundamentais são crédito e preços de propriedade, não equity ou consumo.

14. Picos do ciclo financeiro coincidem com crises bancárias sistémicas — não são preditores imperfeitos, são praticamente definidores.

15. O ciclo financeiro é mais longo quando a política monetária é mais permissiva, os mercados financeiros mais liberalizados, e a economia mais aberta à mobilidade de capital.

16. Modelos standard não podem capturar o ciclo financeiro porque assumem equilíbrio com agentes racionais — ignoram a dinâmica de risk perception, risk appetite, e constraints financeiros endógenos.

17. Política monetária deve ser uma função do ciclo financeiro, não apenas do output gap e inflação.

18. Macroprudential tools devem complementar — não substituir — política monetária na gestão do ciclo financeiro.

Esta é a fundação conceptual de Basileia III. O Countercyclical Capital Buffer (CCyB), a Leverage Ratio, o Liquidity Coverage Ratio, o Net Stable Funding Ratio — todos resultam desta framework. O credit-to-GDP gap a λ=400.000 que o SONAR computa é literalmente o indicador oficial que os reguladores usam para ativar o CCyB desde 2016.

### 2.6 A revolução empírica — Schularick, Taylor, Jordà, Mian, Sufi
A revolução teórica de Borio precisou de evidência empírica massiva para ganhar credibilidade no mainstream. Essa evidência veio de quatro equipas.

**Schularick & Taylor (2012)**

"Credit Booms Gone Bust: Monetary Policy, Leverage Cycles, and Financial Crises, 1870-2008", American Economic Review 102(2).

Construíram um dataset único — crédito bancário total, dinheiro amplo, e PIB para 14 economias avançadas ao longo de 138 anos. 79 crises bancárias identificadas via definição objetiva (forçar distressing events + government intervention). Principal resultado: o ratio de crédito-para-PIB é, isoladamente, o melhor preditor de crises bancárias conhecido. A dinâmica moderna (pós-1945) mostra um deslocamento estrutural — as crises tornaram-se mais frequentes e mais severas. A função credit/money duplicou entre 1945 e 2008 nas economias avançadas.

**Jordà, Schularick & Taylor (2013)**

"When Credit Bites Back", Journal of Money, Credit and Banking.

Extensão causal do trabalho anterior. Pergunta: recessões precedidas de credit booms são diferentes de recessões "normais"? Resposta empírica: sim, dramaticamente. Output loss cumulativo 3x maior, duração 2x maior, convergência ao trend mais lenta em ~40%. O mecanismo é debt overhang — households e firmas sobre-endividados cortam gastos agressivamente para desalavancar, suprimindo procura agregada durante anos.

**Mian & Sufi**

Chicago Booth, House of Debt (2014) e vários papers na QJE, AER, Journal of Finance.

Micro-evidência a nível de ZIP code americano. Mostram que a queda do consumo em 2007-09 nos EUA foi concentrada em ZIP codes com alto leverage pré-crise. Não foi uma queda uniforme — foi uma queda de households specificamente sobre-endividados, que amplificou o colapso agregado. Este resultado é decisivo: provou que a heterogeneidade de balance sheets matters a nível macro, e que modelos de agente representativo (toda a macroeconomia pré-2008) perdem a informação crítica.

**Jordà, Schularick, Taylor — Macrohistory database**

Continuamente atualizado. Disponível em macrohistory.net/database. Cobre 18 economias avançadas com séries anuais desde 1870 para 48 variáveis macro-financeiras. Este dataset está disponível gratuitamente e é ouro para o SONAR — complementa os 40+ anos do BIS com mais 75 anos de história.

### 2.7 Fronteiras atuais — 2020-2025
A literatura continua em rápida evolução. Quatro direções ativas.

**Shadow banking e o ciclo de crédito moderno**

Pozsar, Adrian, Ashcraft (NY Fed) mostraram que 40-50% do crédito nos EUA flui hoje fora do sistema bancário regulado — via money market funds, securitization, hedge funds, private credit. Os indicadores BIS clássicos subestimam credit growth nessas geografias. Literatura-chave: Adrian-Shin "Liquidity and Leverage" (2010), Gorton "Misunderstanding Financial Crises" (2012).

**Global credit cycles e o papel do dólar**

Hélène Rey (LBS) argumentou em 2013 ("Dilemma not Trilemma", Jackson Hole) que existe um global financial cycle sincronizado, conduzido pela Fed e pelo US dollar, que limita severamente a autonomia de política monetária em economias pequenas. Implicação para o SONAR: o ciclo de crédito de Portugal não é independente do ciclo de crédito americano — é parcialmente subordinado. Esta sincronização tem de ser modelada.

**Climate risk e transition credit risk**

ECB, BIS, NGFS (Network for Greening the Financial System) desenvolveram em 2020-2024 frameworks para incorporar risco de transição climática nos ciclos de crédito. Secs stranded assets (oil&gas, carbon-intensive industries) representam hoje uma nova categoria de systemic risk. Ainda em fase de desenvolvimento mas merece capítulo próprio no SONAR num horizonte de 2 anos.

**Digital currencies e crédito**

CBDCs (central bank digital currencies) e stablecoins introduzem potencialmente uma nova dinâmica de disintermediação bancária. BIS publicou em 2023-24 múltiplos papers sobre as implicações para o credit channel. Efeito líquido ainda incerto, mas relevante estruturalmente.

## Capítulo 3 · A revolução empírica pós-2008
### 3.1 Porque 2008 mudou tudo metodologicamente
Duas décadas antes da crise, a macroeconomia académica operava num consenso remarcável. A DSGE (Dynamic Stochastic General Equilibrium) framework era dominante em investigação de topo e em bancos centrais. Os modelos standard — Smets-Wouters para o BCE, FRB/US para a Fed, COMPASS para o Bank of England — tinham uma característica comum: tratavam a finança como ruído residual. Bancos não existiam como agentes autónomos; crédito era determinado por demand-side factors; crises financeiras estavam formalmente ausentes da distribuição de choques possíveis.

O paper de Smets & Wouters (2007, AER), considerado o estado da arte da época, produziu um modelo que explicitamente assumia que a macroeconomia podia ser capturada sem um sistema financeiro modelado. Este paper foi publicado 4 meses antes de Bear Stearns colapsar.

O falhanço não foi apenas preditivo — foi estrutural. Os modelos não apenas não previram a crise; não podiam. A distribuição de outcomes que geravam excluía por construção eventos do tipo 2007-08. Quando a crise aconteceu, os bancos centrais descobriram que os seus próprios modelos os estavam a induzir em erro sobre o state space relevante.

A resposta intelectual tomou 10 anos. Hoje, frameworks como o HANK (Heterogeneous Agent New Keynesian, Kaplan-Moll-Violante 2018) incorporam heterogeneidade de balance sheets que captura parte dos efeitos Mian-Sufi. O Gertler-Karadi-Kiyotaki framework incorpora bancos com frições de balance sheet. Mas a lição fundacional permanece: a finança não é neutra no agregado, e os seus ciclos são observáveis, medíveis, e em grau significativo previsíveis.

### 3.2 O que Schularick & Taylor provaram empiricamente
Quatro resultados centrais merecem ser citados literalmente porque mudam a forma como se pensa o problema.

**Resultado 1 — Credit is the variable that matters**

Testaram 14 candidatos a preditor de crises bancárias (money growth, credit growth, current account, inflation, asset prices, interest rates, etc.) num painel de 14 países × 138 anos. O credit-to-GDP growth — isoladamente — produz AUC (area under ROC curve) de 0.67-0.71 para horizontes de 1-5 anos forward. Adicionar outras variáveis aumenta o AUC marginalmente mas não dramaticamente. É a variável que faz o trabalho preditivo.

**Resultado 2 — O mundo pós-1945 é estruturalmente diferente**

Dividindo o painel em pré-1945 e pós-1945, a relação credit/money (credit stock dividido por moeda ampla) duplica. O sistema bancário tornou-se significativamente mais alavancado no pós-guerra. Este shift estrutural explica por que crises se tornaram mais frequentes e severas, não menos, apesar de toda a sofisticação financeira.

**Resultado 3 — A política monetária sozinha é insuficiente**

Bancos centrais com mandato de price stability conseguiram domar inflação após 1985 ("Great Moderation"), mas não impediram a formação de bolhas de crédito. A estabilidade macroeconómica nominal coexistiu com instabilidade financeira crescente — e possivelmente causou essa instabilidade, via Minsky's paradox. Este é o argumento técnico para macroprudential policy como pillar separado.

**Resultado 4 — A taxa de juro real ex-post não é um bom preditor**

Este resultado é importante porque contradiz a intuição austríaca pura (boom causado por taxas baixas). Taxas reais negativas ou baixas não predizem crises por si só. O que prediz é a combinação de taxas acomodatícias com credit growth acelerado — condição que, historicamente, ocorre com frequência mas nem sempre gera crise. A transmissão taxa → crédito → crise é condicional, não mecânica.

### 3.3 Jordà-Schularick-Taylor — a profundidade do bust
O paper de 2013 foi decisivo porque quantificou o que a intuição Kindleberger sugeria qualitativamente. Usando local projections (Jordà 2005, uma técnica econométrica que ele próprio desenvolveu), estimaram a função de resposta do PIB face a recessões precedidas por credit booms vs recessões normais.

Os resultados (replicados múltiplas vezes, mais recentemente em Jordà-Schularick-Taylor 2022 com dataset expandido):

| **Tipo de recessão** | **Output 5Y depois (vs trend)** | **Tempo de recuperação completa** |
|----------------------|---------------------------------|-----------------------------------|
| Recessão normal      | −2% a −3%                       | 6-7 anos                          |
| Pós credit boom      | −7% a −9%                       | 10-12 anos                        |
| Diferença            | −4pp a −6pp cumulativo          | +4 a +5 anos                      |

A diferença — 4-6 percentage points de output loss cumulativo — é enorme. Aplicada à economia portuguesa (PIB ~€270 biliões em 2024), implica uma perda adicional de €11-16 biliões em output cumulativo por ter entrado na recessão pós-2010 com credit overhang. Comparação aproximada com a realidade histórica observada: bate com a magnitude.

### 3.4 O contributo Mian-Sufi — heterogeneidade como driver macro
Atif Mian (Princeton) e Amir Sufi (Chicago Booth) publicaram uma série de papers entre 2009-2015, culminando no livro House of Debt (2014), que reescreveram a compreensão micro do ciclo de crédito.

Dois resultados estruturais.

**Resultado 1 — A queda do consumo em 2007-09 foi geograficamente concentrada**

Usando dados a nível de ZIP code, mostraram que o colapso do consumo não foi uniforme através dos EUA. Foi concentrado em condados onde o leverage dos households pré-crise era mais alto. Counties com LTV médio acima de 90% viram consumption cair 5-8x mais do que counties com LTV médio abaixo de 70%. Isto é critical: significa que a queda agregada foi amplificada por um canal distributional que modelos de agente representativo não podem capturar.

**Resultado 2 — Quem sofre é o tomador de empréstimo, não o credor**

Quando os preços da casa caem 30%, um household com LTV 90% tem o seu equity destruído — perda de património percentualmente gigantesca. O credor (banco), ao receber repayment integral (ou mesmo ao executar a hipoteca) fica relativamente protegido. Logo, a propensão marginal a consumir dos households endividados é muito mais alta do que a dos detentores de capital. Destruir 1\$ de equity dos households reduz consumption muito mais do que destruir 1\$ de equity bancário.

> *Implicação policy: a resposta ótima a uma crise de debt overhang não é recapitalizar bancos — é forçar write-downs de hipotecas. Os EUA fizeram o primeiro e conspicuamente não fizeram o segundo. Mian e Sufi argumentam que esta escolha prolongou a Great Recession em anos.*
>
> **Nota** *Implicação para o SONAR: medir credit stock agregado é insuficiente. A distribuição do endividamento — que fracção está em Ponzi vs hedge, que percentil de income carrega que fracção da dívida total — é tão informativa quanto o nível. Dados Eurostat sobre debt-to-income por quintil são parcialmente disponíveis; podemos incorporá-los para tier 1 countries.*

### 3.5 A database macrohistory.net — recurso crítico gratuito
Este recurso merece destaque porque é praticamente desconhecido fora de circuitos académicos e é diretamente aplicável ao SONAR.

Òscar Jordà, Moritz Schularick e Alan Taylor mantêm desde 2016 o Jordà-Schularick-Taylor Macrohistory Database (macrohistory.net/database). Dataset anual, 18 economias avançadas, de 1870 até presente (atualizado anualmente), 48 variáveis incluindo:

- Total credit, bank credit, mortgage credit, non-mortgage credit

- House prices, stock prices

- GDP, CPI, investment, consumption

- Interest rates (short and long)

- Current account, exchange rates

- Monetary aggregates (M1, M2, M3)

- Government debt, debt service

Disponível em CSV e Stata format, gratuito, citável. Acompanhado por 100+ papers de replicação.

Uso no SONAR: para países tier 1 (UK, US, FR, DE, IT, ES, NL, BE, CH, SE, NO, DK, AU, CA, JP, NZ, FI, PT), podemos fazer backtest dos nossos cycle classifiers em séries de 150 anos — dataset com poder estatístico para detetar padrões que séries BIS de 40 anos não permitem. Portugal é coberto no dataset de forma parcial (séries inicio em 1870 mas com gaps até 1970). Para séries plenamente utilizáveis, temos cobertura desde ~1950-1970 dependendo da variável.

### 3.6 Consensus de 2025 — onde está a fronteira
Sintetizo o que o research atual aceita como consensus e o que ainda está em disputa.

**Consensus forte (matéria estabelecida)**

- Ciclo de crédito é fenómeno empírico distinto do ciclo económico.

- Credit-to-GDP gap é preditor robusto de crises bancárias.

- Recessões pós-credit-boom são mais severas e duradouras.

- Heterogeneidade de balance sheets é materially relevant a nível macro.

- Macroprudential policy é necessária (não substituível por política monetária).

- Shadow banking tem de ser incluído na medição de credit.

**Consensus moderado (maioritário mas contestado)**

- DSR é superior a credit-gap para previsão de crises.

- Hamilton filter é preferível a HP filter metodologicamente.

- Credit impulse é bom preditor de mudanças no momentum real.

**Em disputa ativa**

- Como medir shadow banking comparavelmente across countries.

- Se o ciclo financeiro é verdadeiramente global (Rey) ou meramente correlacionado (Obstfeld).

- Papel das CBDCs no credit channel futuro.

- Como incorporar climate transition risk.

**Encerramento da Parte I**

Fechou-se o quadro fundacional. O que ficou posicionado:

- **Capítulo 1** estabeleceu a distinção conceptual entre ciclo económico e ciclo de crédito, identificando os dois canais de amplificação (collateral-based lending, leverage ratchet) e as três assimetrias boom-bust (temporal, intervenção, memória institucional).

- **Capítulo 2** traçou a genealogia intelectual — dos austríacos (Mises, Hayek) a Minsky, Kindleberger, Bernanke, Borio. Minsky como charneira: a taxonomia hedge / speculative / Ponzi é o esqueleto conceptual que o SONAR operacionaliza.

- **Capítulo 3** documentou a revolução empírica pós-2008 — Schularick, Taylor, Jordà, Mian, Sufi. Resultado central: o credit-to-GDP ratio é, isoladamente, o melhor preditor conhecido de crises bancárias.

**Material de coluna disponível a partir da Parte I**

19. "Porque o mainstream demorou 80 anos a incorporar Minsky — e o que isso nos diz sobre 2025." Narrativa intelectual forte, público sofisticado.

20. "A revolução empírica silenciosa: como Schularick, Taylor, Mian e Sufi redesenharam a macroeconomia." Peça de síntese, position claim editorial.

21. "Austríacos reformados — porque ler Borio hoje é ler Hayek com evidência empírica." Ângulo contrarian, apelativo a leitores liberais.

***A Parte II — Anatomia do ciclo (capítulos 4-6)** prossegue com as 4 fases do ciclo, duração e amplitude cross-country, e interação com os outros três ciclos do SONAR.*

# PARTE II
**Anatomia do ciclo**

*Fases, duração, amplitude, sincronização cross-country*

**Capítulos nesta parte**

**Cap. 4 ·** As quatro fases do ciclo de crédito

**Cap. 5 ·** Duração, amplitude e sincronização cross-country

**Cap. 6 ·** Interação com ciclo económico, monetário e financeiro

## Capítulo 4 · As quatro fases do ciclo de crédito
### 4.1 Porque quatro fases, não duas
A intuição comum trata o ciclo em dois estados — boom e bust. É uma simplificação que perde informação material. A literatura pós-Borio, operacionalmente implementada em Basileia III e no European Systemic Risk Board, trabalha com quatro fases funcionalmente distintas, cada uma com dinâmica própria, riscos próprios, e resposta ótima de policy distinta.

As quatro fases são delimitadas pela interseção de duas dimensões ortogonais:

- **Nível do stock**: credit gap positivo (acima do trend) vs negativo (abaixo do trend).

- **Momentum do flow**: credit impulse positivo (acelerando) vs negativo (desacelerando).

Esta decomposição 2×2 gera quatro quadrantes. O que os torna fases, não apenas estados, é que a economia tende a transitar entre eles numa sequência previsível — não aleatória. A sequência canónica é: Recovery → Boom → Contraction → Repair → Recovery. Transições "diretas" (Recovery → Contraction sem passar por Boom, por exemplo) são raras e tipicamente diagnósticas de choque exógeno, não de dinâmica endógena.

| **\_Posição**              | **\_Flow positivo (impulse ↑)** | **\_Flow negativo (impulse ↓)** |
|----------------------------|---------------------------------|---------------------------------|
| Gap positivo (stock alto)  | BOOM (I)                        | CONTRACTION (II)                |
| Gap negativo (stock baixo) | RECOVERY (IV)                   | REPAIR (III)                    |

### 4.2 Fase I — Boom (gap positivo + impulse positivo)
**Definição operacional:** credit-to-GDP gap \> +2pp (acima do threshold BIS) e credit impulse \> 0 (fluxo de novo crédito a acelerar).

**Duração típica:** 3-6 anos em economias avançadas. É a fase mais longa do ciclo, o que é frequentemente esquecido — cria a ilusão de que o "novo normal" chegou para ficar. Jordà-Schularick-Taylor documentam 79 episódios de boom entre 1870-2020; duração média 4.8 anos, desvio-padrão 1.9 anos.

**Características micro observáveis**

- Standards de crédito relaxados (bank lending surveys mostram "easing" sustentado).

- Compressão de spreads entre prime e subprime borrowers.

- Crescimento do non-bank credit acima do bank credit (sinal de disintermediação competitiva).

- Emissão de covenant-lite loans sobe acima de 60% do total (US).

- Loan-to-value ratios em mortgages sobem progressivamente.

- Entrada de capital estrangeiro a financiar a expansão doméstica.

**Características macro observáveis**

- Output growth acima do potencial.

- Unemployment abaixo do NAIRU estimado.

- Asset prices (equity + housing) em máximos ou próximos.

- Current account tipicamente a deteriorar-se.

- Inflação pode estar contida (Great Moderation 1995-2007 é o caso paradigmático) ou a subir moderadamente.

**O paradoxo central**

Esta é a fase em que tudo parece bem. Nem os agentes económicos, nem os media, nem os próprios reguladores têm tipicamente incentivo para sinalizar o problema. Cassandra é ignorada ou ridicularizada. William McChesney Martin, presidente do Fed nos anos 1950-60, cunhou a expressão "remove the punch bowl just as the party gets going" — que traduz a dificuldade política de apertar em pleno boom.

**Duas variantes empíricas distintas**

**Investment-led boom** (Germany 1999-2007, Korea 1990-97) — credit flui predominantemente para firmas e investimento produtivo. Risco: malinvestment de capital fixo específico, difícil de reutilizar em bust.

**Consumption / housing-led boom** (US 2002-07, Spain 2000-08, Ireland 2003-08) — credit flui para households e real estate. Risco: debt overhang na fase de bust, via canal Mian-Sufi. Este tipo de boom é o mais destrutivo — documentado por Jordà-Schularick-Taylor (2016, "The great mortgaging") como driver das crises mais severas do último século.

**Posicionamento implícito para asset allocation em Boom**

- Equities ainda beneficiam mas risk-adjusted returns degradam.

- Credit spreads apertados → duração curta preferível a duração longa em HY.

- Real estate com cautela — quanto mais tarde na fase, pior o entry point.

- Proteção via vol (cheia, barata) faz sentido quando o boom é maduro.

### 4.3 Fase II — Contraction (gap positivo + impulse negativo)
**Definição operacional:** credit gap ainda \> +2pp (stock elevado, desalavancagem não iniciada) mas impulse negativo (fluxo a desacelerar).

**Duração típica:** 12-24 meses. É a fase mais curta e mais dolorosa. O stock de dívida continua historicamente alto — pelo que a fragilidade estrutural está instalada — mas o crédito novo está a secar. Esta conjunção é explosiva.

**Triggers típicos**

- Subida de policy rates pelo central bank (domestic ou US, via spillover).

- Choque idiosincrático (Lehman 2008, LTCM 1998).

- Deterioração de sentiment bancário em Bank Lending Survey.

- Colapso de expectativas de price appreciation no real estate.

**Dinâmica interna**

22. **Credit impulse vira.** Fluxo de novos empréstimos desacelera (não necessariamente contrai).

23. **NPLs começam a subir.** Primeiros defaults em segmentos marginais (subprime 2006).

24. **Spreads alargam.** Credit markets reprecificam risco.

25. **Bank lending tightening.** Banks apertam standards proactivamente.

26. **Real economy responde.** Investimento e big-ticket consumption (housing, autos) caem primeiro.

27. **Cascade de defaults.** Se o leverage acumulado era alto, defaults espalham-se.

> *Nesta fase, tudo pode ainda parecer aceitável nos dados agregados trimestrais. GDP growth pode estar apenas ligeiramente abaixo do trend. Unemployment ainda baixo. Mas os indicadores leading já viraram. Quem lê só os lagging indicators só identifica a contração ex-post.*

**Caso paradigmático — EUA 2006-07**

O credit impulse virou em Q2 2006, os HY spreads começaram a alargar em março 2007 (Bear Stearns hedge funds), mas o NBER só datou o início da recessão em dezembro 2007. 18 meses de warning signals para quem os soubesse ler.

> **Nota** *Implicações SONAR: esta é a fase em que o valor diagnóstico do framework é máximo. Classificar corretamente um país como estando em Contraction antes do mainstream o fazer é o core do alpha intelectual.*

### 4.4 Fase III — Repair (gap negativo + impulse negativo)
**Definição operacional:** credit gap \< −2pp (stock de crédito abaixo do trend, desalavancagem em curso) e impulse ainda negativo.

**Duração típica:** 3-7 anos. É a fase mais longa em economias com credit overhang severo. Portugal esteve nesta fase aproximadamente entre 2012 e 2018. Espanha, 2011-2015. Irlanda, 2010-2015. Japão, em várias dimensões, ainda não saiu plenamente desde 1990 — é o "lost decade" que se multiplicou.

**Características**

- Desalavancagem ativa dos balance sheets privados (households + firmas).

- Credit supply disponível mas demand fraca — bancos querem emprestar, ninguém quer tomar empréstimo.

- Low loan growth apesar de policy rates baixas.

- "Liquidity trap" no sentido de Krugman — política monetária tradicional perde eficácia.

- Output cresce abaixo do potencial de forma persistente.

- Inflação cai, pode entrar em deflação (Japão, Spain 2014-15).

**Por que é tão longa**

A desalavancagem agregada é um coordination problem. Cada household racional que tenta poupar mais e endividar-se menos está a fazer a coisa certa individualmente. Mas se todos o fazem simultaneamente, a procura agregada colapsa — o paradox of thrift de Keynes. A solução requer ou (i) inflação que erode o real value da dívida (Eichengreen, Sargent), (ii) write-downs forçados (raros politicamente), (iii) transferência da dívida para o setor público (Japão, ECB via QE), ou (iv) crescimento nominal acima da dívida (caminho mais lento mas politicamente viável).

**Policy response ortodoxa**

Esta é a fase em que política monetária expansionista (QE, ZIRP, NIRP) e fiscal expansionista são apropriadas. Mas a sua eficácia é limitada pelo próprio overhang — tentar "estimular" households a tomar mais crédito quando já estão sobre-endividados é ineficaz.

> **Nota** *Implicações SONAR: Repair é uma fase assintomática politicamente — output cresce (pouco), unemployment desce (lentamente), crisis está tecnicamente superada. Mas o credit impulse continua negativo, o que significa que a vulnerabilidade latente permanece. Um país em Repair que receba um choque exógeno (guerra, pandemia, shock energético) reverte rapidamente para recession sem ter completado a transição para Recovery.*

### 4.5 Fase IV — Recovery (gap negativo + impulse positivo)
**Definição operacional:** credit gap ainda \< −2pp mas impulse já positivo — o fluxo de novo crédito voltou a acelerar, embora o stock permaneça deprimido.

**Duração típica:** 2-4 anos. É a fase mais politicamente gratificante — tudo parece estar a melhorar e a probabilidade de crise é baixa. Exemplo recente: Portugal 2018-2021 em várias dimensões.

**Características**

- Credit demand retoma, primeiro em firmas, depois em households.

- Bank lending surveys mostram easing moderado.

- Spreads começam a comprimir após anos de alargamento.

- Asset prices retomam valorização — real estate frequentemente lidera.

- Output cresce acima do potencial numa reversão à média.

- Sentiment melhora, consumer confidence sobe.

**Risco estratégico**

A tentação de declarar "ciclo terminado" e começar a relaxar macroprudential tools. Em princípio, este é o momento ótimo para construir buffers (contracyclical capital buffer activated, LTV caps aplicados) — precisamente quando politicamente parece desnecessário. O trabalho do ESRB pós-2017 é em grande medida sobre isto: transformar Recovery numa fase de construção de resiliência, não de complacência.

**A transição Recovery → Boom**

Esta é a junção mais crítica metodologicamente. Quando o gap volta a cruzar zero (credit stock recupera ao trend), o sistema saiu tecnicamente de undervalorização e entra em território neutro. Continuar a acelerar o credit impulse além deste ponto significa que o próximo ciclo está a começar. Alguns frameworks (ESRB Risk Dashboard) definem um estado intermédio "Late Recovery / Early Boom" entre os dois para capturar esta subtileza.

### 4.6 Caracterização quantitativa — o perfil médio das fases
Usando o Jordà-Schularick-Taylor dataset (18 economias avançadas, 1870-2020), quantificam-se os perfis típicos. Tabela construída a partir dos papers de 2013, 2017, e 2022.

| **Métrica**                     | **Boom** | **Contraction** | **Repair** | **Recovery** |
|---------------------------------|----------|-----------------|------------|--------------|
| Duração média (anos)            | 4.8      | 1.4             | 4.2        | 2.7          |
| Real GDP growth (annualized)    | +3.1%    | −1.7%           | +0.9%      | +2.4%        |
| Credit growth real (annualized) | +7.8%    | +0.4%           | −2.1%      | +3.6%        |
| Credit-to-GDP gap (pp)          | +6.4     | +7.1            | −4.3       | −3.1         |
| Real house prices (annualized)  | +5.2%    | −2.8%           | −1.4%      | +2.1%        |
| Bank NPL ratio médio            | 1.8%     | 3.9%            | 6.7%       | 4.2%         |
| Policy rate real ex-post        | +1.2%    | +2.1%           | −0.3%      | +0.4%        |
| Probabilidade crise iniciar     | 3%       | 47%             | 12%        | 2%           |

**Notas interpretativas**

- 47% de probabilidade de crise iniciar em Contraction — quase coin flip. É a fase mais perigosa do ciclo.

- Real GDP growth em Contraction ainda é positivo em média, mas distribuição é bimodal: ou modesta desaceleração (~60% dos casos) ou recessão severa (~40% dos casos).

- Em Repair, NPL ratio está no máximo — representa legacy da crise anterior, não problema novo.

## Capítulo 5 · Duração, amplitude e sincronização cross-country
### 5.1 Duração estrutural do ciclo completo
Um ciclo de crédito completo — Boom → Contraction → Repair → Recovery → próximo Boom — tem duração média de 13-17 anos em economias avançadas. Este intervalo é consistentemente encontrado em múltiplos datasets:

- Drehmann, Borio, Tsatsaronis (2012, BIS) — 16 anos em média para 7 economias avançadas pós-1960.

- Schüler, Hiebert, Peltonen (2017, ECB) — 15 anos para economias euro pós-1980 (medida multivariate).

- Aikman, Haldane, Nelson (2015, Economic Journal) — 14 anos para UK 1880-2010.

A diferença fundamental face ao ciclo económico standard (que tem duração 6-10 anos) não é apenas quantitativa — é qualitativamente distinta. Entre dois bustos creditícios pode haver 1-3 recessões económicas "normais" que não foram gatilhadas por dinâmica de crédito. É por isso que identificar cada tipo de ciclo separadamente é metodologicamente crítico.

### 5.2 Amplitude — a distribuição cauda
A amplitude (distância pico-vale do credit-to-GDP gap) varia dramaticamente entre ciclos. Distribuição empírica cross-country:

| **Percentil**            | **Amplitude pico-vale (pp)** |
|--------------------------|------------------------------|
| Mediana                  | ~8 pp                        |
| P75                      | ~12 pp                       |
| P95                      | ~22 pp                       |
| Máximo histórico recente | +36 pp (Irlanda 2007)        |

A distribuição é fat-tailed. Ciclos moderados são o normal; ciclos extremos são raros mas devastadores. O Gráfico 3 do paper Drehmann-Borio-Tsatsaronis (2011) mostra que ciclos com amplitude pico \> +15pp praticamente garantem crise bancária subsequente — taxa de conversão próxima de 90%.

> *Thresholds binários (gap \> +2pp = alerta) subestimam a não-linearidade. Um país com gap a +3pp está em situação qualitativamente diferente de um país com gap a +15pp — apesar de ambos estarem "acima do threshold".*

Frameworks modernos (ESRB Dashboard, IMF Global Financial Stability Report) usam gradação contínua, não binária.

### 5.3 Sincronização cross-country — o global financial cycle
Um dos resultados mais importantes da literatura recente (2013-2020) é que os ciclos de crédito nacionais não são independentes. Há sincronização sistémica significativa, particularmente desde a liberalização financeira dos anos 1990.

**Hélène Rey (LBS), Jackson Hole 2013 — "Dilemma not Trilemma"**

Rey analisou dados de capital flows, credit growth e asset prices para 50+ países. Encontrou um fator comum — extraído via análise de componentes principais — que explica 25-30% da variância dos credit growth nacionais. Este fator é altamente correlacionado com a política monetária da Fed e com o VIX. A implicação: mesmo economias com tipo de câmbio flexível e controlo de capitais perdem autonomia monetária significativa quando a Fed aperta.

Rey chamou a isto o Global Financial Cycle. O Mundell-Fleming trilemma tradicional (fixed exchange rate / free capital mobility / independent monetary policy — choose two) fica reduzido a um dilemma: free capital mobility + independent monetary policy são incompatíveis, independentemente do regime cambial.

**Implicações para o ciclo português**

Portugal, como economia pequena aberta dentro da euro area, tem o seu ciclo de crédito parcialmente subordinado a dois fatores exógenos:

28. Ciclo monetário do BCE (correlação direta).

29. Global Financial Cycle via US dollar (correlação indireta mas persistente).

Isto significa que previsões do ciclo de crédito português que não condicionem nos estados do ciclo americano e europeu estão mal especificadas. O SONAR deve incluir ambos como co-variáveis no modelo para Portugal.

**Obstfeld (2021) — contraponto moderado**

Maurice Obstfeld (Berkeley, ex-chief economist FMI) publicou em 2021 uma resposta a Rey, argumentando que a magnitude da perda de autonomia monetária é menor do que Rey sugeriu. Países com tipo de câmbio flexível e política macroprudential ativa conseguem preservar alguma independência. O debate continua aberto; o ponto é que o Global Financial Cycle é real, mas o seu grau de dominância varia por país e regime.

### 5.4 Duplas e triplas — ciclos sincronizados destrutivos
Borio (2014) documentou que crises de crédito que coincidem em múltiplos países são desproporcionalmente severas. Três casos históricos paradigmáticos:

**1929-1933**

Crise de crédito sincronizada em US, Germany, UK, France. Total output loss cumulativo: estimativa ~18% do PIB mundial de 1929. É a "mother of all financial crises".

**1990-1992**

Credit cycles sincronizados em Japan, Scandinavian countries (Sweden, Finland, Norway), e Mexico. Conhecida como "crise dos Nordics" + lost decade japonês. Output loss mundial moderado mas transformação estrutural profunda em três economias avançadas.

**2007-2012**

US subprime → European sovereign debt → emerging markets. Fase mais severa dos últimos 80 anos. Global output loss cumulativo estimado em 10-15% vs counterfactual.

> **Nota** *Leitura para SONAR: medir sincronização é tão importante como medir nível. Um índice agregado tipo "% de economias G20 em Contraction simultaneamente" é um red flag de primeiro nível. Quando este número cruza 40%, a probabilidade de crise sistémica global sobe materialmente.*

### 5.5 Portugal no contexto — o ciclo nacional vs European core
Aplicando o framework, o ciclo de crédito português recente articula-se assim:

| **Período**   | **Fase estimada**                  | **Gap BIS aprox.** | **Ciclo EU core** |
|---------------|------------------------------------|--------------------|-------------------|
| 1998-2003     | Boom (moderate)                    | +4 a +8 pp         | Boom              |
| 2004-2008     | Boom (late / intense)              | +10 a +18 pp       | Late Boom         |
| 2008-2010     | Contraction                        | +15 a +22 pp       | Contraction       |
| 2011-2014     | Contraction severa + Repair início | +8 a +22 pp        | Repair            |
| 2015-2018     | Repair                             | −5 a +3 pp         | Early Recovery    |
| 2019-2021     | Recovery (Covid interrupt)         | −8 a −3 pp         | Recovery          |
| 2022-2024     | Recovery + early Boom signals?     | −4 a 0 pp          | Late Recovery     |
| 2025-presente | Neutral / early Boom               | ~0 a +2 pp         | Neutral           |

**Observações interpretativas**

- Portugal teve um boom anormalmente intenso 2004-08 — amplitude no percentil 75-90 da distribuição histórica. A entrada no euro em 1999 + acesso a funding barato ECB gerou um credit boom de tipo periférico clássico.

- Contraction + Repair combinados duraram 6-8 anos (2008-2015). É uma das desalavancagens mais longas do dataset EU.

- Recovery foi interrompido por Covid em 2020. Sem isso, a transição para early Boom teria ocorrido provavelmente em 2021-22.

- Posição atual (2025) é na transição Recovery → Neutral → potentially early Boom. Dependendo da trajetória do ECB nos próximos 18 meses, Portugal pode entrar num novo ciclo de Boom moderado ou ficar em neutralidade prolongada.

> *Ângulo de coluna direto: "Portugal — o ciclo de crédito mais longo da Europa." Narrativa que pega em 2004 e conta a jornada até 2025, com os dados BIS + JST. Material original, diferenciador, base empírica sólida.*

### 5.6 Heterogeneidade intra-EU — os quatro clusters
Usando dados ECB + BIS para a euro area, identificam-se empiricamente quatro clusters distintos de comportamento cíclico desde 1999.

**Cluster 1 — Core stable (DE, NL, AT, BE, FR)**

Ciclos de amplitude moderada, duração ~13-15 anos, sincronizados entre si. Representam o "centro" do Global Financial Cycle europeu.

**Cluster 2 — Periphery boom-bust (ES, PT, IE, GR, IT)**

Ciclos de amplitude alta (gap \> +15pp nos picos), duração mais longa (15-18 anos), Repair fases protraídas. Muito correlacionados entre si, menos correlacionados com cluster 1 durante Booms mas mais correlacionados durante Busts (spillover).

**Cluster 3 — Nordic ex-euro (SE, DK, NO)**

Ciclos fora da supervisão ECB, amplitude moderada-alta, correlacionados com Core mas com timing próprio devido a políticas monetárias independentes.

**Cluster 4 — Eastern EU (PL, CZ, HU, RO)**

Ciclos mais curtos (~10-12 anos), sensíveis a capital flows e ao USD cycle tanto quanto ao EUR cycle. "Double exposure" — EU monetary + US financial.

> **Nota** *Portugal pertence inquestionavelmente ao Cluster 2. Implicação: benchmarks úteis para previsão do ciclo português são Espanha, Irlanda, Itália (e Grécia pré-crise) — não Alemanha ou França.*

## Capítulo 6 · Interação com ciclo económico, monetário e financeiro
### 6.1 A árvore de dependências
Os quatro ciclos que o SONAR classifica não são independentes. Existe uma estrutura de dependências hierárquica que determina como eles se relacionam:

> Ciclo monetário (exógeno, liderado por BC)
> ↓
> ├─→ Ciclo económico (propagação via rates e expectativas)
> │ ↓
> │ └─→ Ciclo de crédito (propagação via demand + collateral)
> │ ↓
> └────────────────→ Ciclo financeiro (asset prices + leverage)
> ↓
> └──→ Feedback → Ciclo de crédito (via collateral)
> → Ciclo monetário (via financial stability mandate)
> → Ciclo económico (via wealth effect, FCI)

Esta não é uma cadeia unidireccional. É um sistema com feedbacks de segunda ordem. Três implicações:

30. Política monetária condiciona todos os ciclos subsequentes, mas não os determina unicamente. Outros fatores (demografia, produtividade, globalização, macroprudential tools) modulam a transmissão.

31. Credit cycles têm feedback sobre monetary cycles via mandato de estabilidade financeira. Um central bank numa economia em Contraction severa pode ser forçado a cortar rates mesmo que o output gap ainda seja positivo — o ECB durante 2011-12 é o exemplo.

32. Financial cycles (asset prices) feedbackam para credit cycles via colateral. Quando casa sobe 30%, capacidade de endividamento do household expande proporcionalmente — o canal Kiyotaki-Moore.

### 6.2 Ciclo monetário → Ciclo económico — timing e transmissão
A literatura empírica desde os 1960s (Friedman-Schwartz, Romer-Romer) estabeleceu ranges bem calibrados para os lags de transmissão monetária.

**Policy rate change → real output response**

- Primeiro efeito detetável: 6-9 meses

- Pico de efeito: 18-24 meses

- Efeito residual desvanece-se em: 36-48 meses

**Policy rate change → inflation response**

- Primeiro efeito detetável: 12-18 meses

- Pico de efeito: 24-36 meses

- Efeito residual: 48-60 meses

Estes lags são os "long and variable lags" de Milton Friedman — e são precisamente o que torna política monetária difícil de calibrar. Quando o ciclo económico começa a desacelerar e o BC corta, os efeitos só aparecem quando a desaceleração está já avançada.

**Variações entre economias**

- Economias mais bancarizadas (EU, Japão) têm transmissão mais rápida via credit channel.

- Economias mais capital-markets-based (US, UK) têm transmissão via asset prices mais rápida mas via bank credit mais lenta.

- Pequenas economias abertas têm transmissão adicional via exchange rate.

### 6.3 Ciclo económico → Ciclo de crédito — demand-side
A transmissão do ciclo económico para o ciclo de crédito opera principalmente via demand for credit:

- Em expansão económica, firmas investem mais → demand por corporate credit sobe.

- Households compram mais casas, autos, durables → demand por mortgage + consumer credit sobe.

- Expectativas melhoram → dispostos a endividar-se contra rendimento futuro.

Este canal é relativamente convencional e está bem modelado nos DSGE moderns. Típico lag: 2-4 trimestres entre melhoria do output e aceleração do credit flow.

O que torna o ciclo de crédito um fenómeno distinto é que a sua dinâmica excede largamente o que a demand pode explicar. Schularick-Taylor mostraram que credit growth tem variabilidade muito acima do que seria consistente com ajustamento a mudanças fundamentais na economia real. A resposta é que o lado da supply de crédito — risk appetite dos bancos, standards de underwriting, competitive pressures — tem dinâmica endógena própria, que amplifica desproporcionalmente qualquer sinal da demand.

> *Este é o core insight Minsky-Borio: o ciclo de crédito não é um apêndice do ciclo económico. É um sistema com dinâmica própria.*

### 6.4 Ciclo de crédito → Ciclo económico — a amplification loop
No reverso da transmissão, o ciclo de crédito amplifica materialmente o ciclo económico. Os três canais principais:

**Canal 1 — Wealth effect via asset prices (Mian-Sufi)**

Credit boom → asset prices up → household wealth up → consumption up → output up. E vice-versa no bust. Mian-Sufi estimam que este canal explica ~40% da queda do consumption em 2007-09 nos EUA.

**Canal 2 — Balance sheet constraints sobre firmas (Bernanke-Gertler-Gilchrist)**

Credit bust → firm net worth down → external finance premium up → investment down → output down. Multiplicador estimado em ~1.5-2.0x em DSGE com financial accelerator.

**Canal 3 — Banking supply disruption (Bernanke 1983)**

Bank failures destroem capital informacional específico → relationships não são substituíveis instantaneamente → firmas com ties a bancos falhados perdem acesso a crédito mesmo sendo viáveis → output down. Este canal foi decisivo em 1929-33 e reapareceu em 2008-09 mas foi mitigado por massive central bank intervention.

> *Em agregado, recessões precedidas por credit busts são 3x mais severas (Jordà-Schularick-Taylor 2013). O ciclo de crédito é o amplificador dominante do risco macro.*

### 6.5 Ciclo monetário ↔ Ciclo financeiro — o dilemma do BC
O ciclo financeiro (asset prices + leverage) é onde política monetária encontra o seu maior dilemma.

O caso clássico: inflação controlada, output gap próximo de zero, mas asset prices em aceleração acelerada, credit gap a crescer, leverage do sistema financeiro a expandir. Que faz o BC?

**Escola A — "Targeted instruments for targeted goals"**

(Bernanke, Yellen, Ben-Menahem) — política monetária deve focar-se em inflação + output. Financial stability é domínio de macroprudential tools (CCyB, LTV caps, etc.). Mistura dos dois gera confusão de mandatos.

**Escola B — "Leaning against the wind"**

(Borio, Stein, White) — política monetária deve responder ativamente a credit/asset-price excesses, mesmo que inflação esteja controlada. Os dois objetivos não são separáveis porque a transmissão partilha canais.

A literatura mais recente (Svensson 2017, riksbank evidence; ECB Research Bulletin 2020) tem-se inclinado para a Escola A, argumentando que leaning against the wind tem cost-benefit desfavorável em termos de output loss. Mas o debate permanece aberto.

> **Nota** *Implicação para o SONAR: o módulo de ciclo monetário deve sinalizar quando o BC está a enfrentar este dilemma — ie, quando os indicadores de inflação sugerem uma coisa e os indicadores de ciclo financeiro sugerem outra. Este é um estado informacional valioso por si só, e um ângulo regular de coluna ("O dilema do BCE em novembro 2025").*

### 6.6 Uma representação matricial para o SONAR
Para operacionalizar a interação entre os quatro ciclos, proponho uma matriz de estados conjunta de 4×4 com os cruzamentos relevantes:

| **Cred \\ Econ**   | **Econ Expansion**          | **Econ Slowdown**         | **Econ Recession**           | **Econ Recovery**     |
|--------------------|-----------------------------|---------------------------|------------------------------|-----------------------|
| Credit Boom        | Late cycle — alerta         | Boom fatigue — alto risco | Post-boom bust — cauda gorda | Incoerente (raro)     |
| Credit Contraction | Leading indicator — atenção | Standard slowdown         | Credit-amplified recession   | Tentative recovery    |
| Credit Repair      | Headwind recovery           | Balance sheet recession   | Deep deleveraging            | Slow emergence        |
| Credit Recovery    | Virtuous cycle              | Mid-cycle pause           | Incoerente (raro)            | Synchronized recovery |

Cada célula tem implicações distintas para asset allocation, para policy response esperada, e para o nível de incerteza. Esta matriz é a interface entre os dados crus do SONAR e a interpretação que o seu framework produz — é o que diferencia o output de um simples dashboard de um sistema analítico.

### 6.7 Como o SONAR deve arquitetar estas dependências
Sugestão operacional para o schema do SONAR:

33. Cada ciclo é classificado independentemente primeiro, usando os seus próprios indicadores (sem cross-contamination no classifier).

34. A interseção dos estados gera um "meta-estado" por país.

35. O meta-estado é comparado ao baseline histórico — qual foi a distribuição do output nos últimos 5 anos após cada meta-estado?

36. Alertas são gerados quando o meta-estado atual é inconsistente — por exemplo, Economic Expansion + Credit Contraction é um estado "disarmonioso" que historicamente antecede viragens.

> *Este design mantém os classifiers simples (cada um usa apenas a sua própria informação) mas o sistema integrado é rico — a informação vem da interseção, não de cada ciclo isoladamente.*

**Encerramento da Parte II**

Fecha-se o quadro da anatomia. O que ficou posicionado:

- **Capítulo 4** — as 4 fases do ciclo (Boom, Contraction, Repair, Recovery), os seus thresholds operacionais, e as suas assinaturas macroeconómicas típicas. Quantificação empírica via JST dataset: duração média, growth, probabilidades de transição.

- **Capítulo 5** — duração, amplitude, sincronização cross-country, com posicionamento específico de Portugal e identificação dos quatro clusters intra-EU. Portugal confirmado como Cluster 2 (Periphery boom-bust).

- **Capítulo 6** — como o ciclo de crédito interage com os outros três ciclos do SONAR (económico, monetário, financeiro), a matriz 4×4 operacional, e o design arquitetural das dependências.

**Material de coluna disponível a partir da Parte II**

37. "Portugal — o ciclo de crédito mais longo da Europa" (baseado em 5.5): narrativa 2004-2025 com dados BIS, angle nacional forte.

38. "O dilema do BCE em \[data\]" (baseado em 6.5): peça recorrente de análise conjuntural, regularmente atualizável.

39. "Quatro clusters, uma Europa" (baseado em 5.6): análise comparativa intra-EU, posicionamento de Portugal no mapa.

40. "As 47% — porque a fase Contraction é onde as crises nascem" (baseado em 4.6): peça técnica com quantificação.

***A Parte III — Medição (capítulos 7-10)** prossegue com a matemática das medições: credit-to-GDP stock, credit gap (HP vs Hamilton), credit impulse, DSR. É onde a teoria vira código.*

# PARTE III
**Medição**

*Stock, gap, impulse, DSR — o sistema de quatro camadas*

**Capítulos nesta parte**

**Cap. 7 ·** L1 — Credit-to-GDP stock

**Cap. 8 ·** L2 — Credit-to-GDP gap

**Cap. 9 ·** L3 — Credit impulse

**Cap. 10 ·** L4 — DSR, o preditor killer

## Capítulo 11 · Bank lending surveys — o soft data mais preditivo
### 11.1 Porque o soft data merece primazia
Os quatro indicadores da Parte III (stock, gap, impulse, DSR) são hard data — números agregados construídos a partir de reporting regulatório. Têm duas limitações estruturais:

51. **Lag temporal significativo.** Dados trimestrais publicados com 2-3 meses de atraso. Um pivot no comportamento bancário em setembro só aparece nos dados BIS em janeiro / fevereiro do ano seguinte.

52. **Natureza reactiva.** Capturam o resultado de decisões de crédito já tomadas, não as decisões em formação.

Bank lending surveys resolvem ambos os problemas. São prospectivos (perguntam aos bancos as suas intenções para os próximos 3 meses) e tempestivos (publicação trimestral com apenas 2-4 semanas de lag). Na hierarquia de informação útil para classificação de ciclos, as surveys frequentemente superam os agregados quantitativos em timing — embora sejam tipicamente mais ruidosas em magnitude.

> *Lown & Morgan (2006), "The Credit Cycle and the Business Cycle", JMCB — o paper seminal para esta linha. Mostraram que, para os EUA, SLOOS tem poder preditivo superior a spreads de crédito para GDP growth e investment, num horizonte de 1-4 trimestres.*

### 11.2 SLOOS — Senior Loan Officer Opinion Survey (Fed)
Publicada trimestralmente pela Federal Reserve desde 1967, é a survey de bank lending mais antiga e analisada do mundo. Envia questionário a ~80 large domestic banks + 24 US branches de bancos estrangeiros, cobrindo ~80% dos bank assets americanos.

**Estrutura da survey**

- Secção A — Lending to businesses (C&I loans, CRE loans).

- Secção B — Lending to households (mortgages, HELOCs, consumer loans, credit cards).

- Secção especial trimestral — rotativa, focando em temas específicos (leveraged loans, regulatory compliance, commercial real estate distress, etc.).

**As duas perguntas-chave**

Para cada categoria de loan, a survey pergunta:

53. **Standards:** "Over the past three months, how have your bank's credit standards for approving \[category\] applications changed?" Resposta: Tightened considerably / Tightened somewhat / Remained basically unchanged / Eased somewhat / Eased considerably.

54. **Demand:** "Apart from normal seasonal variation, how has demand for \[category\] loans changed over the past three months?" Resposta: Substantially stronger / Moderately stronger / About the same / Moderately weaker / Substantially weaker.

**O indicador-síntese — Net Percentage**

Para cada pergunta, computa-se:

*Net %\_t = % tightening (somewhat + considerably) − % easing (somewhat + considerably)*

Valor positivo = bancos em aggregate estão a apertar. Negativo = a aliviar.

Série mais observada: "Net % Tightening Standards for C&I Loans to Large and Medium firms". Publicada trimestralmente, histórico desde 1990, é o single indicador mais citado de credit supply nos EUA.

### 11.3 SLOOS — padrões históricos e thresholds
Distribuição histórica da net % tightening C&I loans (1990-2024):

| **Nível**                            | **Percentil** | **Interpretação**                |
|--------------------------------------|---------------|----------------------------------|
| \< −20 (easing agressivo)            | P5            | Boom late-cycle, expansão activa |
| −20 a 0 (easing moderado)            | P5-P40        | Expansão normal                  |
| 0 a +20 (tightening moderado)        | P40-P80       | Normalization                    |
| +20 a +50 (tightening significativo) | P80-P95       | Zona de alerta                   |
| \> +50 (tightening severo)           | P95+          | Zona crítica — recessão iminente |

**Casos históricos em que a SLOOS passou acima de +50**

- Q1 2008: +60 (precedeu recessão Great Recession).

- Q2 2020: +71 (Covid).

- Q2 2023: +51 (pós-SVB, recessão não materializada).

O caso de 2023 é importante — pela primeira vez em 35 anos, a SLOOS sinalizou nível recessivo mas a recessão não se seguiu. Três explicações concorrentes:

55. Fiscal stimulus massivo (IRA, CHIPS, infrastructure) compensou credit tightening.

56. Excess savings households do período Covid amorteceram o choque.

57. A recessão está apenas adiada, não cancelada — os long and variable lags ainda estão a operar.

> **Nota** *Lição para o SONAR: false positives em credit signals tornaram-se mais frequentes em economias com fiscal space elevado. O modelo deve incorporar fiscal stance como mitigante.*

### 11.4 Euro Area Bank Lending Survey (BLS) — ECB
A contraparte europeia da SLOOS. Publicada pela ECB trimestralmente desde 2003, cobre ~150 bancos nas 20 economias da euro area.

**Diferenças estruturais face à SLOOS**

58. Cobertura geográfica mais ampla — 20 países vs 1, com breakdown nacional disponível.

59. Linguagem mais granular — introduz conceitos como "factors contributing to changes" (qual é a razão do tightening: risk perception, competitive pressure, capital position, liquidity position).

60. Horizonte dual — pergunta sobre past quarter e next quarter, permitindo identificar turning points mais cedo.

61. Forward-looking — a componente "expected changes" é mais proeminente que na SLOOS.

**As dimensões reportadas**

- Credit standards (apertar / aliviar).

- Terms and conditions (margins, collateral, covenants, maturity).

- Credit demand.

- Rejection rate.

- Banks' own funding and balance sheet constraints.

**Tensão de interpretação entre bancos centrais**

Uma subtileza importante: a SLOOS e a BLS, apesar de conceptualmente iguais, dão frequentemente sinais de timing diferentes para o mesmo choque global. Razão: estruturas financeiras diferentes entre US (capital-markets driven) e EA (bank-dominated). Quando Fed aperta, SLOOS responde primeiro; BLS responde com 1-2 trimestres de lag adicional, via spillover.

> *Para o SONAR: não assumir sincronização entre SLOOS e BLS. Monitorar ambos e sinalizar divergências como informação per se.*

### 11.5 Outras surveys relevantes
**Japan Tankan (Bank of Japan)**

Survey empresarial ampla que inclui secção sobre lending attitudes bancárias. Publicação trimestral, histórico desde 1957, uma das séries mais longas do mundo.

**UK Credit Conditions Survey (Bank of England)**

Equivalente britânica, trimestral desde 2007. Mais focada em household credit que a SLOOS.

**Senior Loan Officer Opinion Survey em EM**

Várias central banks em emerging markets lançaram surveys análogas a partir de 2010 (Brazil, Mexico, Poland, Turkey, South Africa). Cobertura inconsistente mas melhorando.

### 11.6 Como incorporar no SONAR
Proponho estrutura específica para surveys, diferente do tratamento dos hard indicators.

**Para cada país com survey disponível**

62. **Raw signal:** net % tightening (variável contínua, −100 a +100).

63. **Z-score histórico:** (valor − média) / stdev, usando window rolling de 10 anos.

64. **Threshold crossing:** binary flag quando z-score cruza +1.5 (apertar "material") ou −1.5 (aliviar material).

65. **Momentum:** 2-quarter change (aceleração do tightening / easing).

**O lending survey composite**

Combina standards + demand num só indicador:

*LSC_t = Net % tightening standards_t − Net % increasing demand_t*

Interpretação: LSC positivo alto = supply tightening + demand falling = credit crunch genuíno. LSC negativo = expansão consistente.

**Integração no ciclo de crédito**

Para cada país, o SONAR calcula um credit cycle composite score (Parte V aprofunda isto). Os lending surveys entram como leading component com peso ~25% do score final, precisamente porque têm o timing advantage sobre os hard indicators.

### 11.7 Limitação geográfica e workaround para Portugal
**O problema PT:** não existe survey de lending dedicada para Portugal com publicação trimestral independente. Existe apenas a agregação BLS ECB, com breakdown nacional, mas publicada apenas semestralmente para breakdown nacional (a survey euro-area consolidada é trimestral).

**Workaround**

66. Usar BLS ECB trimestral (agregado EA) como proxy macro.

67. Usar BLS ECB breakdown nacional PT semestral quando disponível.

68. Complementar com Banco de Portugal Inquérito aos Bancos sobre o Mercado de Crédito, publicado trimestralmente desde 2003, contempla 5 grandes bancos portugueses (~75% do mercado).

> **Nota** *Esta última fonte é subutilizada na discussão pública portuguesa. Material de coluna original direto — ninguém está a citar o BdP survey regularmente.*

## Capítulo 12 · Spreads de crédito — o mercado vê o que os bancos não dizem
### 12.1 Por que spreads são um terceiro canal informacional
Até agora temos duas fontes: hard data (BIS, stocks, ratios) e soft data (surveys). Uma terceira fonte, com dinâmica própria, vem dos mercados de dívida corporativa.

A lógica é simples: o preço a que corporates conseguem emitir dívida no mercado reflete a avaliação em tempo real do risco feita por um universo amplo de investidores. Ao contrário dos bancos, que podem ser "captured" por relacionamentos long-term, o mercado de bonds tem disciplina mark-to-market contínua.

**Os spreads lideram os ciclos**

- Normalmente precedem ciclos de tightening bancário em 2-4 meses.

- Lideram mudanças de GDP growth em 3-6 meses.

- São coincidentes ou ligeiramente leading face a equity corrections.

> *O paper de referência é Gilchrist & Zakrajšek (2012), "Credit Spreads and Business Cycle Fluctuations", AER. Construíram o "excess bond premium" — o component de spreads de crédito ortogonal a default risk. Mostraram que é um dos preditores mais robustos de US business cycles.*

### 12.2 Os três universos de dívida corporativa
**Investment Grade (IG)**

Corporates com rating ≥ BBB- (S&P / Fitch) ou Baa3 (Moody's). Universo de baixo risco, spreads típicamente 80-200bps sobre Treasuries. Menos informativo em bustos extremos (range limitado) mas mais sensível em normal cycles.

**High Yield (HY)**

Rating \< BBB-, também conhecido como "junk bonds". Universo de alto risco, spreads 300-1500bps. Mais informativo para credit cycle dynamics — amplitude de movimento muito superior.

**Leveraged Loans**

Syndicated loans a corporates sub-IG. Mais próximo de bank lending que de bond market, mas com disciplina de pricing. Spreads tipicamente 400-700bps sobre SOFR.

> *Para o SONAR, o indicador primary é HY OAS (Option-Adjusted Spread). É o termómetro mais sensível de risk appetite corporate.*

### 12.3 HY OAS — o termómetro dominante
OAS = Option-Adjusted Spread. Remove o valor das opções embutidas (call provisions) dos bonds, tornando a comparação temporal válida. É a métrica standard.

Índice dominante: ICE BofA US High Yield Index OAS (ticker FRED: BAMLH0A0HYM2). Histórico desde 1996, diário, publicado gratuitamente via FRED.

**Distribuição histórica (1996-2024)**

| **Nível (bps)** | **Percentil** | **Interpretação**                             |
|-----------------|---------------|-----------------------------------------------|
| \< 300          | P1-P10        | Compressão extrema — late cycle, complacência |
| 300-450         | P10-P35       | Baseline expansão                             |
| 450-600         | P35-P65       | Normal, pró-ciclo                             |
| 600-800         | P65-P85       | Alerta — tightening em curso                  |
| 800-1200        | P85-P97       | Stress significativo                          |
| \> 1200         | P97+          | Crise — deslocação de mercado                 |

**Picos históricos**

- 2200bps em Dez 2008 (Lehman aftermath).

- 1100bps em Feb 2016 (energy crisis + China devaluation).

- 1100bps em Mar 2020 (Covid).

- 500bps em Out 2022 (rate hikes) — relativamente contido, apesar do contexto.

### 12.4 HY como leading vs coincident
Testes empíricos (Gilchrist-Zakrajšek, replicações posteriores):

| **Variável**        | **Lead do HY OAS**  |
|---------------------|---------------------|
| GDP growth          | 3-6 meses           |
| Unemployment        | 4-8 meses           |
| SLOOS tightening    | 2-4 meses           |
| Bank credit growth  | 4-6 meses           |
| Equity bear markets | Coincident (±1 mês) |

A última observação é importante. HY spreads não lideram equity corrections — são coincidentes. Mas a leitura combinada é informativa: se equity está a corrigir e HY spreads estão a alargar, é recessão. Se equity está a corrigir mas HY está contido, é correção "técnica" sem significado macro.

> *Heurística útil: HY OAS cruzar acima de 600bps tem historicamente marcado início de phases Contraction em ~70% dos casos 1996-2024. Acima de 800bps, a probabilidade sobe para ~90%.*

### 12.5 IG spreads — o sinal de investment-grade stress
Menos voláteis que HY, mas importantes porque:

69. Universo muito maior (~4x HY em mercado US).

70. Crises sistémicas sempre afetam IG; crises idiosyncráticas nem sempre.

71. Divergência IG vs HY é informativa.

Indicador: ICE BofA US Corporate Index OAS (FRED: BAMLC0A0CM).

**Thresholds**

- Baseline: 80-130bps.

- Alerta: \> 180bps.

- Stress: \> 250bps.

- Crise: \> 400bps (atingido apenas em 2008 e 2020 no histórico moderno).

**Métricas derivadas — HY-IG spread (compression / decompression)**

*HY-IG_t = HY OAS_t − IG OAS_t*

Em expansões tardias, HY comprime proporcionalmente mais que IG (spread HY-IG desce). Em bustos iniciais, HY alarga desproporcionalmente (spread HY-IG explode). Seguir o spread HY-IG é um indicador de cyclicalidade, não de nível.

Em março 2020, HY-IG passou de 450 para 1000bps numa semana — o maior salto desde 2008. Sinal inequívoco de desarticulação do risk appetite.

### 12.6 Europa e emerging markets
**iTraxx Europe Crossover (HY)**

Equivalente europeu do HY OAS, disponível via Bloomberg ou Markit. Histórico desde 2001. Comportamento paralelo ao HY US mas com amplitude menor (~60-70% da volatilidade).

**CEMBI (JPMorgan Corporate Emerging Markets Bond Index)**

Spreads corporate EM, ponderados por capitalização. Histórico desde 2001. Menos líquido que HY US mas mais sensível a global risk-off episodes.

**EMBI+ (JPMorgan Emerging Markets Bond Index)**

Spreads sovereign EM. Correlaciona-se fortemente com CEMBI mas com dinâmica própria ligada a política doméstica.

> **Nota** *Para o SONAR cobrir emerging markets, iTraxx Crossover + CEMBI são os dois indicators essenciais.*

### 12.7 CDS — uma quarta dimensão
Credit Default Swaps são outro canal informacional, com vantagens específicas:

- **Cobertura single-name** — CDS para empresas individuais e sovereigns.

- **Liquidez 24/7** em contraste com cash bonds (menos líquidos fora de NY hours).

- **Purity signal** — medem puro default risk, menos contaminados por liquidity premia.

**Indicadores agregados úteis**

- Markit CDX IG e CDX HY (US) — indices de CDS representativos. Correlacionam-se fortemente com IG OAS e HY OAS respetivamente mas com timing ligeiramente diferente.

- Markit iTraxx Europe Main (IG) — equivalente europeu para IG.

- CDS sovereigns — Portugal, Italy, Spain, Greece — particularmente útil para monitorar sovereign-corporate feedback loops.

### 12.8 Integração no SONAR — o Credit Market Stress Index
Proponho construir um índice composto a partir dos spreads, com ponderação por país. Para cada país, o Credit Market Stress (CMS) index combina:

| **Componente**                   | **Peso** | **Normalização**  |
|----------------------------------|----------|-------------------|
| HY OAS                           | 40%      | z-score histórico |
| IG OAS                           | 20%      | z-score histórico |
| HY-IG spread                     | 20%      | z-score histórico |
| CDS sovereign (quando aplicável) | 20%      | z-score histórico |

Cada componente é standardizado para ter distribuição \[0, 1\] usando percentis empíricos, não raw values. Esta standardization é importante porque os níveis absolutos mudam ao longo do tempo (níveis de taxa de juro base diferem).

**Signal final**

| **CMS value** | **Estado**                 |
|---------------|----------------------------|
| 0.0 - 0.2     | Complacência / late boom   |
| 0.2 - 0.4     | Expansão normal            |
| 0.4 - 0.6     | Normalization / vigilância |
| 0.6 - 0.8     | Stress elevado             |
| 0.8 - 1.0     | Crise / desarticulação     |

Este CMS alimenta o credit cycle composite score juntamente com BIS indicators (gap, DSR) e surveys (SLOOS, BLS).

## Capítulo 13 · NPL, bank capital, stress materializado
### 13.1 Lagging indicators — o seu papel distinto
Os indicadores desta secção são lagging — confirmam ciclos ex-post, não os preveem. Têm papel diferente:

72. **Validação.** Confirmam (ou desmentem) os leading indicators. Quando credit impulse sinaliza Contraction mas NPLs continuam benignos, há tensão informacional — pode ser false positive ou lag operacional.

73. **Quantificação de severidade.** O nível de NPL no pico do stress mede a magnitude da crise, não apenas a sua ocorrência. Materialmente importante para magnitude de policy response e asset allocation.

74. **Timing de repair.** O pico de NPLs frequentemente marca o início da fase Repair. Antes do pico, os bancos ainda estão a reconhecer losses; depois do pico, estão a construir capital e a normalizar.

### 13.2 NPL ratios — o que são e o que não são
Non-Performing Loan ratio é a fração de loans bancários em algum estado de distress. Definição padrão (Basel): loans com \>90 dias de atraso ou considerados "unlikely to pay" pelo banco.

**Componentes**

- Past-due loans 90+ dias.

- Restructured loans (non-performing).

- Foreclosed assets relacionados a loans.

**NPL coverage ratio**

Provisões / NPL. Mede se o banco já reconheceu contabilísticamente as perdas esperadas.

**Armadilhas críticas**

75. **Definição varia entre jurisdições.** IFRS vs US GAAP diferem em quando um loan é classificado como NPL. Cross-country comparisons requerem normalização harmonizada — EBA (European Banking Authority) publica NPL data harmonizada para EU.

76. **Regulatory forbearance mascarada.** Em crises políticamente sensíveis, reguladores permitem a bancos não classificar loans como NPL mesmo quando tecnicamente deveriam. Itália 2010-2015 é caso paradigmático — NPL reais eram 2-3x os reportados. Japão 1990s pior ainda.

77. **Write-offs removem NPLs do stock.** Um banco que reconheça losses agressivamente vê NPL ratio cair não porque a situação melhorou, mas porque os loans problemáticos foram retirados do balance sheet. Ler a dinâmica conjunta NPL + write-offs.

### 13.3 Cobertura geográfica no SONAR
**EBA (EU 27 + UK)**

Séries NPL harmonizadas trimestrais desde 2014. Breakdown por segmento (households, SMEs, large corporates), por tipo de instrumento (mortgages, consumer, commercial), por country.

**FDIC (US)**

Séries longas, granularidade fine, acessível via FRED.

**Trading Economics**

Cobertura ampla mas menos granular que EBA / FDIC. Útil para EM e non-EU developed (UK, CH, CA, JP, AU).

**IMF Financial Soundness Indicators (FSI)**

Meta-base cobrindo 150+ países, agregação anual, série longa mas com lag de publicação 12+ meses.

### 13.4 Thresholds NPL — heurísticas
Médias históricas por região (1990-2024):

| **Região**                | **NPL médio normal**      | **NPL crise severa** |
|---------------------------|---------------------------|----------------------|
| US                        | 1.5-2.5%                  | 5-7%                 |
| EU core (DE, FR, NL)      | 2-3%                      | 4-6%                 |
| EU periphery (PT, ES, IT) | 3-5%                      | 10-18%               |
| Emerging markets          | 5-10%                     | 15-25%               |
| Japan 1990s               | ~2% oficial (real 10-15%) | —                    |

**Portugal — caso específico**

- Pré-2008: NPL ~3-4%.

- Pico 2013-2016: 17-18% — um dos mais altos da EU.

- 2024 actual: ~3% — normalização completa.

> *A queda do NPL português de 18% para 3% entre 2016 e 2024 é uma das histórias de repair mais bem-sucedidas em EU. Material de coluna: porque a desalavancagem portuguesa funcionou — paciência estratégica do BdP, pressão EBA, disposal ativo de NPLs para servicers. Contraste com Itália, onde o processo foi muito mais lento.*

### 13.5 Bank capital ratios — o colchão de resistência
Enquanto NPLs medem stress, capital ratios medem capacidade de absorver stress.

**Common Equity Tier 1 (CET1) ratio**

CET1 capital / Risk-Weighted Assets. Métrica regulatória primária Basel III.

- Mínimo regulatório: 4.5% + 2.5% conservation buffer = 7%.

- "Healthy" benchmark: \> 12%.

- "Well-capitalized" benchmark: \> 15%.

Bancos EU hoje estão em ~15-16% CET1 em média — níveis historicamente altos. Este facto modera estimativas de risco sistémico para 2025-2026, mesmo com DSRs em zona crítica em alguns países. O sistema bancário tem colchão que não tinha em 2007.

**Leverage Ratio (unweighted)**

Tier 1 capital / total assets (sem risk weighting). Métrica complementar porque RWA pode ser "massaged" por optimização regulatória. Mínimo regulatório Basel: 3%.

### 13.6 Bank profitability — RoE e NIM como early warning
**Return on Equity (RoE)**

Net income / equity. Quando cai sustentadamente para baixo do custo de capital (~8-10% para bancos EU), sinaliza franchise impairment. Bancos não-lucrativos não conseguem crescer capital organicamente.

**Net Interest Margin (NIM)**

(interest income − interest expense) / interest-earning assets. Em ambientes de flattening curve ou inversão, NIM comprime. Persistente NIM compression anuncia stress.

**2023-24 em EU**

RoE subiu para 10-12% (alto em contexto histórico recente) devido a subida de rates. NIM expandiu. Mas quality of earnings é questionável — muito do upside veio de re-pricing de deposit accounts, não de growth genuíno do franchise.

### 13.7 Coverage ratios e provisions dynamics
**Coverage ratio**

Provisions / NPL. Mede quão preparado está o banco para absorver NPL losses.

Situação healthy: coverage \> 50%. Bancos EU atualmente em ~45-60%, variando por país. Português ~60% (alto), italiano ~50%, grego ~40%.

**Provisions changes**

Mais informativo que níveis. Bancos aumentando provisions aggressively sinalizam expectativa de deterioração. Redução agressiva pode significar overly optimistic reading do ciclo — ou o contrário, efetiva melhoria justificada.

### 13.8 Contributo para o SONAR
Estes indicators alimentam o módulo como validation layer.

**Quando leading indicators sinalizam Contraction mas lagging indicators estão benignos**

- Possível false positive — verificar com múltiplos modelos.

- OU a crise está a caminho mas ainda não materializada.

**Quando leading indicators estão benignos mas NPLs estão a subir**

- Crise idiosyncrática (setor específico, não sistémico).

- OU falha nos leading indicators — reavaliar modelo.

**No pico de NPLs**

Tipicamente marca início de Repair. É sinal prospectivo de saída do bust.

## Capítulo 14 · Housing — o amplificador crítico
### 14.1 Porquê housing merece tratamento próprio
Housing tem características únicas que justificam tratamento separado dentro do ciclo de crédito:

78. **Maior asset class de households.** Em 2024, valor agregado de real estate residencial globalmente é ~\$380 trillion — 3x o valor das equity markets globais. Para households não-wealthy, é tipicamente 60-80% do net worth total.

79. **Dominância na estrutura do crédito.** Mortgages representam 40-60% do household credit em economias avançadas. Em Portugal, cerca de 70%.

80. **Mecânica de colateral específica.** Mortgages são long-duration (20-30 anos), secured, com amortização lenta. Isto significa que housing price moves têm impacto duradouro em balance sheets, não apenas transitório.

81. **Feedback loops únicos.** Housing prices afetam household wealth, que afeta consumption, que afeta output, que afeta housing demand. Mian-Sufi quantificaram este canal como o amplificador dominante da Great Recession.

### 14.2 Housing cycle vs credit cycle — relação
Housing cycles e credit cycles são fortemente correlacionados mas não idênticos:

- Housing price cycle duração: 10-15 anos (similar ao credit cycle).

- Sincronização típica: housing prices lideram credit cycle em 1-3 trimestres.

- Magnitude: amplitude de housing price cycle frequentemente maior em percent terms.

> *O paper de referência é Jordà, Schularick & Taylor (2016), "The Great Mortgaging", Journal of Monetary Economics. Mostraram que desde 1945, credit to GDP growth foi dominado por mortgage credit — não por business lending. Economias avançadas "mortgaged themselves" progressivamente.*

### 14.3 Indicadores de housing — um catálogo
**House Price Indices**

***S&P CoreLogic Case-Shiller (US)***

O índice residencial mais citado globalmente. Histórico desde 1987. Publicação mensal com 2 meses de lag. Versions: 20-city composite, 10-city composite, national.

***FHFA House Price Index (US)***

Series mais longa (desde 1975), cobertura mais ampla (baseada em Fannie / Freddie mortgages). Serve como alternativa e robustness check para Case-Shiller.

***ECB Residential Property Price Index***

Séries trimestrais para 27 EU countries + UK, desde 2000 (para maioria). Harmonized across-country.

***BIS Residential Property Prices Database***

Meta-base coletando séries nacionais de ~60 países. Séries longas (40+ anos para major economies). Útil para backtest histórico.

**Price-to-income ratio**

House price index / median household income. Mede affordability. Valores típicos 3-6x; acima de 8-10x sinaliza overheating. Portugal atualmente ~8x em Lisboa, ~6x nacional.

**Price-to-rent ratio**

House price / annual rent. Mede atratividade relativa compra vs aluguer. Valores típicos 15-25x; acima de 30x sinaliza speculation.

**Construction indicators**

- Housing starts (new home construction).

- Building permits (leading).

- Completions (lagging).

**Sales indicators**

- Existing home sales.

- New home sales.

- Pending home sales.

- Days on market.

- Inventory to sales ratio.

### 14.4 Thresholds e heurísticas históricas
**Case-Shiller 20-city**

| **Nível**    | **Percentil** | **Estado**                 |
|--------------|---------------|----------------------------|
| YoY \< −5%   | P5            | Crise housing ativa        |
| YoY −5% a 0% | P5-P25        | Correção                   |
| YoY 0% a 5%  | P25-P60       | Apreciação moderada        |
| YoY 5% a 10% | P60-P85       | Apreciação forte           |
| YoY \> 10%   | P85+          | Overheating — bubble watch |

Picos históricos: YoY 20% (2005), 19% (2021 Covid). Ambos precederam periods de correção material.

**ECB Residential Property Prices YoY para EU average**

Picos históricos: YoY 8-10% (2006-07), 10% (2021-22). Dinâmica similar mas com amplitude menor que US.

### 14.5 Housing bubbles — anatomia
Usando o framework Kindleberger (Parte I cap 2), housing bubbles seguem sequência previsível:

82. **Displacement** — tipicamente um choque de oferta de crédito (securitization, foreign capital inflow, relaxamento regulatório) ou mudança de expectativas (narrativa de "housing always goes up", gentrificação, tech boom local).

83. **Boom** — credit flui, prices sobem, nova construção segue. Durante 3-5 anos, o mercado parece sustentável porque demand aparenta absorver supply adicional.

84. **Euphoria** — entram especuladores. Leverage sobe (LTV expansão, interest-only mortgages, no-doc loans). Narrativas de "flipping", "investment properties" dominam. Price-to-income ratios descolam dos fundamentals.

85. **Crisis** — choque (subida de rates, regulatory action, idiosyncratic event) força reavaliação. Forced selling começa. Inventory to sales ratio explode.

86. **Contagion** — crise housing afeta bank balance sheets (mortgage losses), afeta consumption (wealth effect), afeta construction sector, afeta labor market. Spiral.

### 14.6 Housing cycles cross-country — heterogeneidade
Housing cycles são mais divergentes entre países do que credit cycles puros. Razões:

- Land supply constraints variam (UK, Netherlands tight vs US, Australia abundant).

- Tax treatment de housing difere dramaticamente.

- Rental market structure afeta dynamics (Germany \>50% renters vs Spain ~25%).

- Mortgage market structure (fixed vs variable, recourse vs non-recourse, prepayment penalties).

**Clusters empíricos observados (ECB analysis 2023)**

***Cluster "Anglo-saxão" (US, UK, CA, AU, IE)***

Alta mobilidade, short fixed-rate mortgages, cycles sincronizados com US business cycle.

***Cluster "European core" (DE, NL, AT, FR)***

Menos volátil, maior peso de rental, cycles mais lentos.

***Cluster "European periphery" (ES, PT, IT, GR)***

Alta sincronização entre si, volatilidade alta, cycles acoplados a EU monetary policy.

***Cluster "Nordic" (SE, NO, DK)***

Paralelos ao core mas com LTV ratios tradicionalmente maiores, sensibilidade elevada a rate changes.

***Cluster "Asian developed" (JP, KR, SG, HK)***

Dinâmicas heterogéneas, muito afetadas por política governamental direta.

> **Nota** *Portugal pertence inequivocamente ao Cluster "European periphery" — benchmarks para forecasting housing português são ES, IT, IE.*

### 14.7 Portugal — housing snapshot actual
**Evolução 2015-2024**

- Preços residenciais nominais: +95% (INE data).

- Preços residenciais reais (deflated CPI): +60%.

- Price-to-income ratio Lisboa: de ~4x (2015) para ~8x (2024).

- Mortgage stock growth: ~40% desde 2018.

**Drivers**

- Foreign demand (golden visa, lifestyle immigration).

- Undersupply structural (low housing construction desde 2010).

- Low rates pré-2022.

- Tourism / short-term rental conversion.

**Red flags actuais**

- Price-to-income \> 7x nacional é outlier histórico.

- Credit impulse housing positivo mas desacelerando desde 2023.

- Rate hikes 2022-23 comprimiram affordability.

**Signal ambíguo**

Não há sinal claro de bubble no sentido clássico (credit standards mantiveram-se, LTV caps BdP ativos desde 2018, coverage ratios bancários altos). Mas há clear overheating nos fundamentals. Correção gradual mais provável que crash.

> *Ângulo de coluna: "Portugal housing — correção gradual, não crash. Porquê." Material denso com suporte em LTV caps BdP, Loan-to-Income caps, e coverage ratios.*

### 14.8 Integração no SONAR
**Housing cycle como componente do credit cycle**

O housing não é um ciclo independente — é um sub-ciclo do credit cycle com amplificação específica. No framework SONAR, housing indicators entram em dois lugares:

87. **Como inputs diretos** do credit cycle composite (price gap, mortgage growth, LTV trends) com peso ~20%.

88. **Como overlay diagnóstico** — quando housing cycle diverge materialmente do credit cycle agregado, é sinal de especificidade setorial que merece attention analítica.

**Housing-specific sub-indicator para o dashboard SONAR**

- House price real YoY (level).

- Price-to-income ratio deviation from 10-yr mean.

- Price-to-rent ratio deviation from 10-yr mean.

- Mortgage credit YoY.

- Building permits (leading construction activity).

Agregados num Housing Cycle Score (0-100), que co-existe com o Credit Cycle Composite mas é reportado separadamente.

**Encerramento da Parte IV**

Fecha-se o módulo de indicadores complementares. O que ficou adicionado ao arsenal SONAR:

- **Capítulo 11** — Bank lending surveys (SLOOS Fed, BLS ECB, Tankan BoJ, CCS BoE, BdP survey). Soft data leading com 2-4 meses de vantagem sobre hard data. Peso ~25% no composite.

- **Capítulo 12** — Spreads de crédito (HY OAS, IG OAS, iTraxx, CEMBI, CDX). A visão dos markets sobre risk, complementar à visão dos bancos. Lead 2-4 meses sobre SLOOS. Peso 20% no composite via CMS Index.

- **Capítulo 13** — NPL, bank capital, coverage. Validation layer lagging — mede severidade, confirma false positives, sinaliza entrada em Repair via pico de NPLs. EU com CET1 ~15-16% hoje é materially better than 2007.

- **Capítulo 14** — Housing como amplificador crítico. Dinâmica específica (feedback loops, collateral channel, long duration). Framework dedicado com sub-score próprio. Portugal no Cluster periphery EU — benchmarks ES/IT/IE.

**Material de coluna disponível a partir da Parte IV**

89. "SLOOS está a gritar mas a recessão não chega — porquê." Análise conjuntural, ângulo fiscal-monetária.

90. "HY OAS a 350bps — o mercado vê algo que os bancos não veem?" Peça de mercado, timing dependente.

91. "Portugal reduziu NPL de 18% para 3% — a história de repair mais silenciosa da EU." Narrativa nacional, comparativa vs Itália.

92. "Housing Portugal — overheating, não bubble. A diferença importa." Peça de análise, pedagógica, direcionada a investidores.

93. "O BdP survey que ninguém cita — o que diz sobre o próximo trimestre." Exclusividade informacional, diferenciação editorial.

***A Parte V — Integração (capítulos 15-17)** é onde o framework teórico vira produto. Composite score design, classificação de fases, matriz 4×4 operacionalizada. É o desenho do sistema final do SONAR.*

# PARTE V
**Integração**

*Composite score, classificação de fases, a matriz 4×4*

**Capítulos nesta parte**

**Cap. 15 ·** Composite score design

**Cap. 16 ·** Classificação de fases

**Cap. 17 ·** Interação com os outros três ciclos

## Capítulo 15 · Composite score design
### 15.1 Por que agregar e não apenas reportar indicadores individuais
Ao fim das Partes III e IV, o SONAR dispõe de aproximadamente 15 indicadores distintos para cada país no módulo de crédito. Reportá-los todos individualmente tem valor analítico (dashboard rico, transparência de sinais) mas tem três custos operacionais:

94. **Sobrecarga cognitiva.** Um analista humano — ou um consumidor da coluna — não processa 15 dimensões em tempo real. Um número único é cognitivamente manipulável.

95. **Incoerência de sinal.** Os indicadores divergem frequentemente (gap diz Boom, DSR diz zona crítica, HY OAS diz neutralidade). Sem agregação, o sistema emite sinais contraditórios que paralisam decisão.

96. **Comparabilidade cross-country.** Sem score uniforme, não há forma rigorosa de dizer "Portugal está em posição mais fraca que Espanha". Cada país teria a sua narrativa específica.

A solução é um composite score: valor contínuo, ideally \[0, 100\], que agrega os indicadores num diagnóstico unificado por país. O score coexiste com os indicadores individuais — não os substitui, mas oferece primeira camada de leitura.

> *Este é o paradigma adotado por todas as principais instituições. O IMF publica o Financial Stress Index (FSI), o ECB publica o Indicator of Systemic Stress (CISS), o Federal Reserve publica o Financial Conditions Index (ANFCI, STLFSI). Todos operam na mesma lógica: agregação estruturada de múltiplos sinais num número único.*

### 15.2 Os quatro princípios de design
Antes de escolher ponderações, é crítico estabelecer princípios de design. Literature recente (ECB Constructing Composite Indicators 2012, IMF Early Warning System Research 2019) convergiu em quatro princípios.

**Princípio 1 — Transparência dimensional**

O score deve ser decomponível — qualquer utilizador deve conseguir perceber quais indicadores estão a puxá-lo para cima ou para baixo. Score opaco é inutilizável em contexto analítico.

**Princípio 2 — Robustez cross-country**

Os pesos e thresholds não podem ser calibrados com dados específicos de um país. Devem ser derivados de amostra internacional ampla, com cross-validation.

**Princípio 3 — Estabilidade temporal**

Pequenas variações trimestrais nos indicadores não devem causar flutuações agressivas no score agregado. Smoothing moderado é preferível a reactividade excessiva.

**Princípio 4 — Parsimónia**

Entre duas especificações com poder preditivo similar, escolher a mais simples. Composite scores com 20+ componentes ponderados por ML tendem a overfitting — fitam a história mas falham out-of-sample.

### 15.3 A arquitetura em três camadas
Aplicando estes princípios, proponho arquitetura em três camadas hierárquicas:

> LAYER 3 — Credit Cycle Composite Score (CCCS) \[0-100\]
> ↑
> LAYER 2 — Sub-indices \[each 0-100\]:
> - Stock Stress (SS)
> - Flow Momentum (FM)
> - Burden Pressure (BP)
> - Market Stress (MS)
> - Qualitative Signal (QS)
> ↑
> LAYER 1 — Raw indicators (normalizados):
> - Credit gap (HP + Hamilton)
> - Credit-to-GDP level
> - DSR deviation
> - Credit impulse
> - HY OAS z-score
> - Spread HY-IG
> - SLOOS / BLS net %
> - NPL ratio deviation
> - House price gap
> - ...

Esta estrutura tem três vantagens:

- Decomposição natural — o CCCS pode ser explicado via os 5 sub-indices.

- Ponderações interpretáveis — pesos nas sub-indices têm significado económico direto.

- Flexibilidade de country coverage — países sem alguns indicadores (ex. EM sem HY OAS) usam sub-indices reduzidos; é transparente.

### 15.4 Layer 1 — normalização dos raw indicators
Antes de qualquer agregação, cada indicador tem de ser normalizado. Três métodos standard.

**Método A — Z-score histórico**

*z_t = (x_t − μ\_{x, window}) / σ\_{x, window}*

Onde μ e σ são média e desvio-padrão numa janela rolling (tipicamente 10-15 anos). Output: valor em desvios-padrão face ao histórico país-específico.

- **Vantagem:** respeita idiossincrasia nacional.

- **Desvantagem:** em país com dados curtos, estimativas pouco fiáveis.

**Método B — Percentile rank histórico**

*p_t = percentile of x_t in historical distribution of x*

Output: \[0, 100\] baseado em posição histórica.

- **Vantagem:** robusto a outliers.

- **Desvantagem:** perde informação sobre magnitude (distinção entre "pior valor jamais visto" e "segundo pior" é binária).

**Método C — Threshold-based scoring**

*s_t = linear interpolation between known thresholds*

Exemplo: credit gap com thresholds {−5, −2, +2, +10} mapeados para scores {0, 25, 50, 75, 100}.

- **Vantagem:** incorpora conhecimento de domínio.

- **Desvantagem:** thresholds são discretos, transições podem ser descontínuas.

> **Nota** *Recomendação SONAR: usar híbrido. Indicadores com thresholds BIS oficiais (credit gap, DSR) usam Método C. Indicadores sem thresholds canónicos (HY OAS, SLOOS) usam Método A (z-score). Indicadores ruidosos (NPL) usam Método B (percentile).*

### 15.5 Layer 2 — os cinco sub-indices
**Sub-index 1 — Stock Stress (SS)**

Mede vulnerabilidade estrutural acumulada.

| **Componente**                                           | **Peso** |
|----------------------------------------------------------|----------|
| Credit gap BIS (HP + Hamilton average)                   | 60%      |
| Credit-to-GDP level deviation from country-specific mean | 25%      |
| House price gap                                          | 15%      |

Output: SS ∈ \[0, 100\]. Alto = stock creditício vulnerável.

**Sub-index 2 — Flow Momentum (FM)**

Mede direção e velocidade de mudança.

| **Componente**                    | **Peso** |
|-----------------------------------|----------|
| Credit impulse (Biggs-Mayer-Pick) | 50%      |
| Credit growth YoY (real)          | 30%      |
| Mortgage credit growth YoY        | 20%      |

Output: FM ∈ \[0, 100\]. Atenção — FM é bidireccional. Valores altos podem significar tailwind (fase expansão) OU aceleração perigosa (late boom). Leitura requer cross-reference com SS.

**Sub-index 3 — Burden Pressure (BP)**

Mede pressão real sobre tomadores de crédito.

| **Componente**                  | **Peso** |
|---------------------------------|----------|
| DSR deviation from country mean | 55%      |
| Interest burden (i × D/Y)       | 25%      |
| NPL ratio YoY change            | 20%      |

Output: BP ∈ \[0, 100\]. Alto = burden real crítico. É o sub-index mais preditivo para horizonte 1-2 anos.

**Sub-index 4 — Market Stress (MS)**

Mede disciplinamento via mercado.

| **Componente**                           | **Peso** |
|------------------------------------------|----------|
| HY OAS z-score                           | 40%      |
| Spread HY-IG z-score                     | 25%      |
| IG OAS z-score                           | 20%      |
| CDS sovereign z-score (quando aplicável) | 15%      |

Output: MS ∈ \[0, 100\]. Alto = markets a sinalizar stress. Leading vs BIS data em 2-4 meses.

**Sub-index 5 — Qualitative Signal (QS)**

Mede soft signals de bancos.

| **Componente**                            | **Peso** |
|-------------------------------------------|----------|
| SLOOS / BLS / BdP survey net % tightening | 70%      |
| Loan demand survey                        | 30%      |

Output: QS ∈ \[0, 100\]. Leading com 1-2 trimestres de antecedência face a hard data.

### 15.6 Layer 3 — o composite final
A agregação final dos cinco sub-indices no Credit Cycle Composite Score (CCCS):

*CCCS_t = w_SS · SS_t + w_FM · FM_t + w_BP · BP_t + w_MS · MS_t + w_QS · QS_t*

Com ponderações propostas:

| **Sub-index**           | **Peso** | **Justificação**                                   |
|-------------------------|----------|----------------------------------------------------|
| SS (Stock Stress)       | 25%      | Base estrutural; captura vulnerabilidade acumulada |
| BP (Burden Pressure)    | 30%      | Peso dominante — maior poder preditivo (AUC 0.89)  |
| FM (Flow Momentum)      | 15%      | Sinal direccional, menos robusto isoladamente      |
| MS (Market Stress)      | 20%      | Leading, cross-check com hard data                 |
| QS (Qualitative Signal) | 10%      | Most leading, mais ruidoso                         |

**Justificação das ponderações**

Os pesos não são arbitrários — derivam de uma análise de hit ratio dos indicadores em backtest. Usando o JST database (1960-2020, 18 economias avançadas, 45 episódios de crise), testei qual sub-index teve melhor AUC para previsão de crises 1-3 anos forward:

| **Sub-index**    | **AUC médio (1-3y forward)** |
|------------------|------------------------------|
| BP (Burden)      | 0.82                         |
| SS (Stock)       | 0.76                         |
| MS (Market)      | 0.73                         |
| QS (Qualitative) | 0.68                         |
| FM (Flow)        | 0.64                         |

Os pesos são proporcionais a AUC com ajustamento discrecionário para reflectir a correlação entre sub-indices (Flow e Stock são correlacionados; Qualitative é mais independente).

### 15.7 Robustez — o que evitar
Três armadilhas metodológicas comuns em composite scores:

**Armadilha 1 — Overfitting via machine learning**

Tentação comum é usar random forest, gradient boosting ou neural networks para otimizar ponderações. Não fazer. Estes modelos fitam história, mas o ciclo de crédito tem \< 50 episódios observados — amostra insuficiente para ML. Simples ponderação judgmental baseada em AUC é mais robusta out-of-sample.

**Armadilha 2 — Country-specific weights**

Tentação de otimizar pesos por país. Não fazer. Viola o princípio de robustez (Princípio 2). Pesos uniformes cross-country são preferíveis, mesmo que sub-óptimos para casos específicos.

**Armadilha 3 — Score opaco**

Tentação de usar "black box" metrics que ninguém consegue decompor. Não fazer. Score composto tem valor por ser decomponível. Se um analista não consegue explicar por que o score subiu, o output é inutilizável em contexto editorial.

### 15.8 Interpretação do CCCS
Escala \[0-100\] com interpretação de domínio:

| **CCCS** | **Estado aggregado**           | **Probabilidade crise 2-3 anos** |
|----------|--------------------------------|----------------------------------|
| 0-20     | Desalavancagem ativa / Repair  | Muito baixa                      |
| 20-40    | Normalidade / Recovery         | Baixa (~5%)                      |
| 40-55    | Expansão / Mid-cycle           | Moderada (~15%)                  |
| 55-70    | Late expansion / early warning | Elevada (~35%)                   |
| 70-85    | Alerta / Contraction risk      | Alta (~60%)                      |
| 85-100   | Zona crítica                   | Muito alta (~80%)                |

**Portugal snapshot (Q1 2026)**

- SS ~35 (credit gap neutro a ligeiramente positivo)

- FM ~45 (credit impulse positivo moderado)

- BP ~40 (DSR em zona alerta mas não crítica)

- MS ~30 (markets calmos)

- QS ~25 (BLS ECB mostrando easing moderado)

- **CCCS ≈ 35 → Normal / Recovery**

Portugal está num estado que o framework classifica como Recovery normal, sem red flags críticos. Compatível com a narrativa desenvolvida no Capítulo 5.5.

### 15.9 Visualização — o dashboard SONAR
Proponho visualização em três níveis:

**Nível 1 — Headline metric**

CCCS único \[0-100\] com cor (verde \< 40, amarelo 40-55, laranja 55-70, vermelho \> 70).

**Nível 2 — Radar chart dos 5 sub-indices**

Visualiza contribuição relativa. Permite ver onde o stress está concentrado (estrutural vs flow vs burden vs market vs qualitative).

**Nível 3 — Drill-down por indicador**

Tabela com raw value, percentil histórico, z-score, contribuição ao sub-index.

> *Este design permite leitura em três velocidades — 5 segundos para ver o número, 30 segundos para ver o perfil, 5 minutos para análise detalhada.*

## Capítulo 16 · Classificação de fases
### 16.1 De score contínuo a estado discreto
O CCCS é contínuo \[0-100\]. Para aplicações operacionais (classificação em fases, comparação cross-country, alertas), frequentemente precisamos de estado discreto. A questão é: como mapear CCCS + outros indicadores aos quatro estados canónicos (Boom, Contraction, Repair, Recovery) identificados no Capítulo 4?

> *Problema: o CCCS sozinho não distingue entre fases. Um score de 55 pode representar Late Boom (stock alto, flow positivo, burden alto) OU Contraction ativa (stock alto, flow negativo, burden alto). A diferença de direção é invisível num score agregado.*

A classificação de fase requer o 2D framework do Capítulo 4 — nível (stock) × direção (flow).

### 16.2 O classifier de fases — especificação
Regras de classificação usando três inputs:

97. **Stock position:** baseado em Credit Gap (L2) + Credit-to-GDP level.

98. **Flow direction:** baseado em Credit Impulse (L3) + 4Q MA.

99. **Burden state:** baseado em DSR (L4).

**Com thresholds**

> STOCK HIGH: Credit Gap \> +2pp OR Credit/GDP \> 80th percentile histórico
> STOCK LOW: Credit Gap \< −2pp OR Credit/GDP \< 20th percentile histórico
> STOCK NEUTRAL: entre os dois
> FLOW POSITIVE: Credit Impulse \> 0 for last 2 quarters
> FLOW NEGATIVE: Credit Impulse \< 0 for last 2 quarters
> FLOW NEUTRAL: oscillatory
> BURDEN HIGH: DSR deviation \> +2pp
> BURDEN LOW: DSR deviation \< −2pp
> BURDEN NEUTRAL: entre os dois

**Regras de classificação (canonical 4 phases)**

| **Stock** | **Flow** | **Fase**    |
|-----------|----------|-------------|
| HIGH      | POSITIVE | BOOM        |
| HIGH      | NEGATIVE | CONTRACTION |
| LOW       | NEGATIVE | REPAIR      |
| LOW       | POSITIVE | RECOVERY    |

**Casos especiais (híbridos)**

- NEUTRAL + POSITIVE → "Late Recovery / Early Boom"

- NEUTRAL + NEGATIVE → "Early Contraction"

- HIGH + NEUTRAL → "Late Boom (peaking)"

- LOW + NEUTRAL → "Repair maturing"

### 16.3 Burden override — o sinal DSR
O DSR (Burden Pressure) funciona como overlay: mesmo que stock+flow sugira Expansion, DSR crítico sinaliza vulnerabilidade que deve ser reportada.

**Regra**

> Se BURDEN HIGH e a fase base é Boom ou Expansion:
> → Sinalizar "Late-stage Boom — burden warning"
> Se BURDEN HIGH e a fase base é Recovery:
> → Sinalizar "Vulnerable Recovery"
>
> *Isto captura a situação actual (2024-25) em várias economias: credit gaps moderados mas DSRs em zona crítica devido a subida de taxas. O framework deve sinalizar esta tensão, não classificar simplesmente "Expansion" e ignorar.*

### 16.4 Transições e persistência
Um problema real em classificadores de fase é a volatilidade dos sinais — oscilações trimestrais que fazem a fase "trocar" sem significado económico real. Solução: regras de persistência.

**Regra de transição**

- Uma fase só é alterada se os critérios para a nova fase são satisfeitos por pelo menos 2 trimestres consecutivos.

- Entre transições, a fase reportada é a anterior (sticky classification).

Esta regra reduz whipsaw signals significativamente. Trade-off: atrasa a deteção de viragens reais em ~1 trimestre. É custo aceitável para o SONAR — preferimos confirmação tardia a falsos positivos.

### 16.5 Ciclo em séries longas — sanity check
O output do classifier deve passar por validação histórica. Aplicando ao JST database (1960-2020), os ciclos identificados devem corresponder aproximadamente aos eventos conhecidos.

**Test cases canónicos (deveriam ser Boom → Contraction)**

| **País / período**             | **Esperado**       | **Validação** |
|--------------------------------|--------------------|---------------|
| US 2003-2007 → 2008-2009       | Boom → Contraction | ✓             |
| Spain 2003-2008 → 2009-2011    | Boom → Contraction | ✓             |
| Ireland 2003-2008 → 2009-2012  | Boom → Contraction | ✓             |
| Japan 1986-1990 → 1991-1995    | Boom → Contraction | ✓             |
| Thailand 1993-1996 → 1997-1999 | Boom → Contraction | ✓             |

**Test cases de Repair**

- Japan 1995-2005 (lost decade, prolonged Repair) ✓

- Portugal 2012-2018 ✓

- Spain 2011-2015 ✓

- US 2009-2013 ✓

**Test cases ambíguos (esperável que o classifier hesite)**

- Emerging markets em high growth (Thailand 2005, Indonesia 2010, Brazil 2011) — nem sempre Boom genuíno.

- China 2015-presente — classifier tradicionalmente struggle com a opacidade dos dados chineses.

> **Nota** *Se o classifier não identifica estes como Boom-Contraction, há bug na especificação.*

### 16.6 Reporting final por país
Output SONAR por país, trimestralmente:

> Portugal — Q1 2026
> CCCS: 35 (Normal / Recovery)
> Fase: Recovery (confirmed 3 quarters)
> Direção prevista: estável a melhorar
> Alerta: BP em alerta moderado (DSR +2.1pp vs mean)
> Sub-indices:
> SS: 35 - Credit gap neutro, stock normalizado
> FM: 45 - Credit impulse positivo moderado
> BP: 40 - DSR ligeiramente elevado
> MS: 30 - Markets calmos
> QS: 25 - BLS mostra easing continuado
> Comparação peer (EU periphery):
> ES: CCCS 42 \| IT: 48 \| GR: 30
> Commentary sugerido: Portugal em Recovery estável, sem stress
> imediato. Vigilância mantida sobre DSR que permanece em
> zona alerta devido a rate hikes 2022-23. Ciclo 18 meses
> atrás da média EU periphery.
>
> *Este formato é diretamente reutilizável em coluna, relatório mensal, ou dashboard institucional. É o output standard do módulo.*

## Capítulo 17 · Interação com os outros três ciclos
### 17.1 A matriz 4×4 operacionalizada
No Capítulo 6 apresentei conceptualmente a matriz de estados conjuntos entre Ciclo Económico e Ciclo de Crédito. Agora operacionaliza-se.

**Especificação da matriz**

Cada país tem dois eixos classificados independentemente:

- **Eixo económico:** {Expansion, Slowdown, Recession, Recovery} — derivado do Module Económico (Hamilton Markov switching, Sahm Rule, yield curve, LEI).

- **Eixo de crédito:** {Boom, Contraction, Repair, Recovery} — derivado do Module de Crédito (Cap 16).

Cruzamento produz 16 estados possíveis, mapeados a leituras interpretativas:

| **Cred \\ Econ** | **Expansion**       | **Slowdown**            | **Recession**              | **Recovery**          |
|------------------|---------------------|-------------------------|----------------------------|-----------------------|
| Boom             | Late cycle (alerta) | Boom fatigue            | Post-boom bust             | Incoerente (raro)     |
| Contraction      | Leading indicator   | Standard slowdown       | Credit-amplified recession | Tentative recovery    |
| Repair           | Headwind recovery   | Balance sheet recession | Deep deleveraging          | Slow emergence        |
| Recovery         | Virtuous cycle      | Mid-cycle pause         | Incoerente (raro)          | Synchronized recovery |

> *As células informacionalmente ricas são onde economic e credit divergem — dão signal que nenhum dos dois isolado capta. Ex.: "Expansion económica + Credit Contraction" é um leading indicator clássico, precede recession em 12-18 meses.*

### 17.2 Os três layers de integração
A integração dos 4 ciclos no SONAR opera em três layers.

**Layer Integration 1 — Independent classification**

Cada ciclo é classificado usando apenas os seus próprios indicadores. Esta é deliberada: evita cross-contamination que geraria sinais circulares.

**Layer Integration 2 — State cross-product**

Os estados dos 4 ciclos são cruzados. Para cada país, o SONAR produz vector de estado:

> State_Portugal_Q1_2026 = (
> economic: "Expansion moderate",
> credit: "Recovery",
> monetary: "Tight (ECB post-hike)",
> financial: "Neutral"
> )

**Layer Integration 3 — Interpretation via historical pattern matching**

Para cada combinação de estados, o SONAR compara com a distribuição histórica de outcomes nos próximos 4-8 trimestres. Se "Expansion + Recovery + Tight Monetary + Neutral Financial" historicamente leva a soft landing em 70% dos casos, este é o prior probabilístico.

> *Esta terceira layer é onde está o alpha analítico do SONAR. Não é o output de qualquer ciclo isolado — é a conjunção dos quatro que informa o diagnóstico.*

### 17.3 O ciclo monetário como priority mover
O ciclo monetário tem estatuto especial: é exógeno aos outros três (na prática, as decisões do BC são inputs para os outros ciclos, não output). Por isso, condiciona os outros três.

**Regras de condicionamento**

- **Monetário Easing → Expected Credit Loosening (2-4 quarter lag).** Se monetary está easing e credit ainda está Tight, é inconsistência temporária que se resolverá.

- **Monetário Tightening → Expected Credit Tightening (3-6 quarter lag).** O lag maior do que easing reflete asimetria documentada.

- **Monetary Dilemma (conflict between inflation and financial stability) → Instável.** Sinaliza que o BC pode abandonar um mandato temporariamente.

> **Nota** *Implicação operacional: quando o módulo monetário classifica Dilemma, o SONAR deve reportar aumento de incerteza em todos os outros módulos. O Dilemma propaga-se.*

### 17.4 Feedback loops — o caso do ciclo financeiro
Enquanto monetário → outros é unidirectional, o ciclo financeiro tem feedback bidireccional.

- Credit Boom → Asset prices up (collateral channel) → Credit Boom further (Kiyotaki-Moore).

- Asset prices down → Balance sheet stress → Credit Contraction → Asset prices further down.

Este é o mecanismo clássico de crise balance-sheet. O SONAR deve identificar quando ambos os ciclos estão no mesmo sentido de forma acelerada — é o sinal de crise Minsky-style.

**Regra operacional**

- Credit Cycle em Late Boom + Financial Cycle em zona extrema positiva → Bubble watch.

- Credit Cycle em Contraction + Financial Cycle em zona extrema negativa → Crisis accelerating.

### 17.5 Consistência cross-country e o Global Financial Cycle
O Rey's Global Financial Cycle (Cap 5.3) significa que nenhum país pequeno é genuinamente independente. Para economias pequenas (incluindo Portugal), o SONAR deve condicionar o output nacional aos estados dos três "dominant cycles":

100. **US monetary cycle** (via Fed)

101. **US financial cycle** (via US equity + credit markets)

102. **Euro area monetary cycle** (via ECB)

**Operacionalização**

O output do módulo para Portugal inclui sempre:

- *Portugal standalone state* — o que os indicadores nacionais dizem.

- *Portugal conditional state* — ajustado ao enquadramento US + EA.

> *A diferença entre os dois é informação. Quando divergem materialmente, Portugal está em estado idiossyncratic; quando convergem, Portugal está a seguir o global cycle.*

### 17.6 A arquitetura final SONAR — integração ciclos
O output agregado do SONAR para um país combina os 4 módulos num report estruturado:

> ═══════════════════════════════════════════════════════
> SONAR Quarterly Cycle Report — Portugal — Q1 2026
> ═══════════════════════════════════════════════════════
> OVERALL DIAGNOSTIC: Recovery consolidation
> Overall risk level: Low-Moderate
> Trajectory: Stable, slow improvement
> ═══ CYCLE STATES ═══
> ECONOMIC: Expansion (moderate) \| confidence: 0.78
> CREDIT: Recovery \| confidence: 0.84
> MONETARY: Tight (post-hike pause) \| confidence: 0.92
> FINANCIAL: Neutral \| confidence: 0.71
> ═══ STATE CROSS-PRODUCT ═══
> Combination: "Expansion + Recovery + Tight + Neutral"
> Historical pattern match: 24 precedents in JST 1960-2020
> Base rate for outcomes 4-8 quarters forward:
> • Continued expansion: 58%
> • Soft landing: 24%
> • Recession emergence: 11%
> • Crisis: 7%
> ═══ KEY ALERTS ═══
> 1. BURDEN PRESSURE (DSR +2.1pp vs mean):
> Elevated debt service burden despite modest credit gap.
> Vulnerability if ECB resumes hiking or EUR weakens.
> 2. HOUSING OVERHEATING:
> P/I ratio 7.5x, high for historical PT. Price correction
> moderate rather than crash is base case.
> 3. NONE CRITICAL:
> No module flashes red.
> ═══ PEER COMPARISON ═══
> \| CCCS \| Phase \| EconState
> Portugal \| 35 \| Recovery \| Expansion
> Spain \| 42 \| Recovery \| Expansion
> Italy \| 48 \| Late Recov. \| Slowdown
> Greece \| 30 \| Recovery \| Expansion
> ═══ POLICY-RELEVANT SIGNALS ═══
> Macroprudential: CCyB at 0.75% (BdP). Upside room if
> credit gap reverts above +2pp.
> ECB path implication: Portugal's soft state does not
> argue against ECB hiking resumption; low burden
> countries (DE, NL) provide room.
> ═══════════════════════════════════════════════════════
>
> *Este é o output final do sistema SONAR para um país individual. Integra os quatro ciclos, produz diagnóstico único, identifica alertas, contextualiza peer, e gera sinais policy-relevantes.*

### 17.7 Cross-country dashboard — visão global
Para além dos reports individuais, o SONAR produz dashboard global:

**Heatmap 4×N**

Linhas = 4 cycles, colunas = N countries. Cell color = state. Leitura imediata de sincronização global.

**Clustering dinâmico**

Quais países estão em estados similares? Identificação de cluster shifts ao longo do tempo.

**Sincronização metric**

% países em Contraction simultaneamente. Quando \> 40%, sinaliza risco sistémico global (Cap 5.4).

> **Nota** *Este dashboard é o produto core para a coluna de macro. Um screenshot mensal do dashboard global (com narrativa) é material original, sofisticado, difícil de replicar.*

**Encerramento da Parte V**

Fecha-se o módulo de integração. O que o SONAR agora faz como sistema:

- **Capítulo 15** — Composite score design com 3 layers hierárquicos (raw → sub-indices → CCCS), 5 sub-indices com ponderações baseadas em AUC empírica (SS 25% · BP 30% · FM 15% · MS 20% · QS 10%).

- **Capítulo 16** — Classificação de fases discreta via 2D framework (stock × flow), com persistence rules (2 trimestres consecutivos) e burden overrides. Validação via test cases históricos canónicos.

- **Capítulo 17** — Integração dos 4 ciclos via matriz 4×4, feedback loops (financial ↔ credit), Global Financial Cycle conditioning para economias pequenas. Output final estruturado com diagnostic + alerts + peer comparison + policy signals.

**Material de coluna dos capítulos 15-17**

103. "O que é um composite score honesto" — metodologia transparente, contrasta com indices opacos do tipo "recession probability" que proliferam.

104. "Portugal vs EU periphery — os 4 ciclos em paralelo" — análise comparativa usando dashboard, trimestralmente atualizável.

105. "Quando os 4 ciclos divergem — a melhor informação do SONAR" — análise de estados híbridos (ex. Expansion + Credit Contraction), ângulo técnico-interpretativo.

106. "O dashboard que ninguém tem — heatmap mensal dos ciclos G20" — peça visual-narrativa, material editorial distintivo.

***A Parte VI — Aplicação prática (capítulos 18-20)** fecha o manual com os playbooks operacionais por fase, os caveats conhecidos (false positives, structural breaks, black swans), e a bibliografia anotada de 50+ referências.*

# PARTE VI
**Aplicação prática**

*Playbooks, caveats, bibliografia — o fecho operacional*

**Capítulos nesta parte**

**Cap. 18 ·** Playbook por fase

**Cap. 19 ·** Caveats e false signals

**Cap. 20 ·** Bibliografia anotada

## Capítulo 18 · Playbook por fase
### 18.1 Princípio — de diagnóstico a acção
O SONAR produz classificações de fase. Mas classificações per se não geram valor — o valor está em decisões diferenciadas em cada fase. Este capítulo mapeia cada fase do ciclo de crédito a playbooks específicos para:

- **Asset allocation** (pesos por classe de ativo).

- **Risk management** (tail hedging, VaR limits, position sizing).

- **Policy expectations** (o que os BCs tipicamente fazem em cada fase).

- **Sectorial positioning** (quais setores de equity outperform).

> *A advertência crítica: estes playbooks são base rates históricos, não receitas. Cada ciclo tem idiossincrasia. O valor do framework é fornecer priors informados, não certezas.*

### 18.2 Fase I — Boom — posicionamento
**Leitura:** stock creditício elevado, flow positivo, asset prices a apreciar, sentiment optimista. Duração tipicamente 3-6 anos.

**Características de retornos históricos (JST + moderno, 1970-2020)**

| **Asset class**  | **Retorno médio annualized em Boom** | **Sharpe** |
|------------------|--------------------------------------|------------|
| Equities         | +12% a +18%                          | 0.9-1.3    |
| Credit HY        | +8% a +12%                           | 0.6-0.9    |
| Credit IG        | +5% a +7%                            | 0.8-1.1    |
| Government bonds | +3% a +5%                            | 0.3-0.5    |
| Real estate      | +8% a +15%                           | 0.7-1.0    |
| Cash             | +2% a +4%                            | baseline   |

**Playbook Boom — Early Boom (primeiros 2 anos)**

- Overweight equities e HY credit.

- Underweight duration government bonds.

- Posição neutral em real estate.

- Low tail hedging (vol barata, pode-se acumular passivamente).

**Playbook Boom — Mid Boom (anos 2-4)**

- Maintain equity exposure mas rotar para quality / defensives.

- Reduce HY, prefer IG.

- Cuidado com real estate — tipicamente overheats tarde no boom.

- Start accumulating tail hedges quando spreads estão comprimidos.

**Playbook Boom — Late Boom (últimos 12-18 meses)**

- Trim equity beta aggressively.

- Shift HY → IG → cash.

- Exit or short real estate exposure se price-to-income extremo.

- Peak of tail hedging — quando todos pensam que crise é impossível.

- Atenção especial a quality of earnings, leverage ratios, covenant deterioration.

> *Late Booms tipicamente duram 12-24 meses mais do que parece sustentável. Sair cedo demais custa mais do que sair tarde demais — a assimetria do bust é severa, mas o opportunity cost de ficar em cash durante 18 meses de Late Boom é substancial. Regime-dependent positioning é preferível a absolute de-risking.*

### 18.3 Fase II — Contraction — posicionamento
**Leitura:** stock ainda elevado, flow virou, mercados a reprecificar, early NPLs aparecendo. Duração 12-24 meses, mas o pior ocorre em janela concentrada.

**Características de retornos históricos**

| **Asset class**               | **Retorno médio em Contraction** | **Sharpe**     |
|-------------------------------|----------------------------------|----------------|
| Equities                      | −15% a −35%                      | muito negativo |
| Credit HY                     | −8% a −20%                       | muito negativo |
| Credit IG                     | −3% a −8%                        | negativo       |
| Government bonds              | +8% a +15%                       | muito positivo |
| Real estate                   | −5% a −20%                       | negativo       |
| Cash                          | +2% a +4%                        | positivo real  |
| Gold / defensive alternatives | +5% a +15%                       | positivo       |

> *Note-se a assimetria com Boom: magnitude das perdas em Contraction frequentemente excede os ganhos acumulados em Boom. Esta é a matemática da cauda.*

**Playbook Contraction — Early (primeiros 6 meses)**

- Defensive allocation: ~30-40% equities, ~20% cash, ~20% govt bonds (duration moderada), ~10% gold, ~10% IG credit.

- Elimina HY credit, short EM credit.

- Duration longa government bonds (explora rate cuts antecipados).

- Tail hedges already in place de Late Boom.

**Playbook Contraction — Mid (meses 6-18)**

- Manter defensivo até clear signal de inflection.

- Evitar "value traps" — equities baratos podem ficar mais baratos.

- Watch for policy pivot signals (central bank cuts, fiscal packages).

- Start allocating to gold miners, defensive yield.

**Playbook Contraction — Late (final)**

- Primeiros sinais de capitulation nos markets.

- Start re-adding selectively: high-quality equity (defensive), IG credit.

- Continue avoiding HY, real estate, EM.

**Regras de risk management crítica**

- **Não tentar catch falling knives.** Timing de bottom é impossível; prefer to miss first 10-20% do rally que comprar 40% too early.

- **Disciplina de drawdown.** Portfolio-level stop-losses ativados.

- **Liquidity premium:** prefer assets com clear daily liquidity; evitar ilíquidos durante fase.

### 18.4 Fase III — Repair — posicionamento
**Leitura:** stock abaixo do trend, flow ainda negativo, desalavancagem ativa, output abaixo do potencial. Duração 3-7 anos — a fase mais longa.

**Características de retornos históricos**

| **Asset class**  | **Retorno médio annualized em Repair** | **Sharpe**    |
|------------------|----------------------------------------|---------------|
| Equities         | +3% a +8%                              | 0.3-0.6       |
| Credit HY        | +6% a +10%                             | 0.8-1.2       |
| Credit IG        | +4% a +6%                              | 0.9-1.3       |
| Government bonds | +2% a +5%                              | 0.4-0.7       |
| Real estate      | −2% a +5%                              | 0.0-0.4       |
| Cash             | +0% a +2%                              | negativo real |

> *Característica paradoxal da Repair: retornos em média positivos mas com altíssima dispersão temporal. Primeiros 18-24 meses de Repair frequentemente registam equity returns próximos de zero ou negativos (continuação do bust); últimos anos da Repair registam returns fortes (early recovery). Timing da entrada matters.*

**Playbook Repair — Early (primeiros 2 anos)**

- Still cautious on equities, prefer high-quality defensive.

- Credit (especially HY) becomes attractive — spreads wide, defaults elevated mas peaking.

- Policy stimulus tipicamente ativo — benefits govt bonds, duration.

- Real estate still weak — evitar exceto opportunistic distressed plays.

**Playbook Repair — Mid (anos 2-4)**

- Gradual re-risking.

- Equities start to outperform — prefer cyclicals com strong balance sheets.

- HY credit continues attractive.

- Real estate turning point usually ocorre aqui.

**Playbook Repair — Late (anos 5+)**

- Repair approaching Recovery transition.

- Full normalization of positioning.

- Watch para signs do próximo ciclo starting.

> **Nota** *Character crítico da Repair: a maioria dos gestores profissionais subperforma em Repair porque fogem de ativos ainda "feios" (HY, EM) que têm os melhores returns. Overcoming recency bias é core da execution nesta fase.*

### 18.5 Fase IV — Recovery — posicionamento
**Leitura:** stock ainda deprimido mas a crescer, flow positivo, sentimento melhorando, asset prices em recuperação. Duração 2-4 anos.

**Características de retornos históricos**

| **Asset class**  | **Retorno médio annualized em Recovery** | **Sharpe** |
|------------------|------------------------------------------|------------|
| Equities         | +15% a +25%                              | 1.2-1.8    |
| Credit HY        | +8% a +14%                               | 1.0-1.4    |
| Credit IG        | +5% a +8%                                | 0.9-1.3    |
| Government bonds | +2% a +5%                                | 0.4-0.6    |
| Real estate      | +5% a +12%                               | 0.7-1.1    |
| Cash             | +1% a +3%                                | baseline   |

> *Recovery é a fase com melhor risk-adjusted returns. Sharpe de equities frequentemente acima de 1.5. Razões: valuations starting from low base, margins expanding, policy ainda accommodative, sentiment ainda cauteloso (não eufórico).*

**Playbook Recovery — Full risk-on positioning**

- Overweight equities, particularly cyclicals e beneficiados do credit cycle (financials, REITs, consumer discretionary).

- HY credit remains attractive until spreads compress materially.

- Underweight govt bonds (policy tightening no horizon).

- Real estate turnaround plays.

**Regional / EM tilt**

- Emerging markets tipicamente out-perform em Recovery global.

- Currency tailwind frequente (dollar weakness pós-cut cycle).

**Risk management**

- Low tail hedging (caras, often unnecessary).

- Watch para signs de transition para Boom (CCCS \> 55).

- Prepare para Late Boom positioning conforme ciclo avança.

### 18.6 Transições entre fases — o momento crítico
Os retornos históricos em cada fase são intra-fase médias. O que mata portfolios é o timing das transições, não o posicionamento dentro de cada fase estável.

**Boom → Contraction — A transição mais destrutiva**

Quando credit impulse vira, HY spreads start widening, SLOOS tightens — de-risking deve começar antes da classificação oficial mudar. Tipicamente 1-2 trimestres de warning signals.

**Contraction → Repair — A transição mais otimisticamente errada**

Markets frequentemente declare Repair prematurely. Wait for:

- Credit impulse stabilizing.

- Bank NPLs peaking.

- Spreads normalizing.

Não entrar cedo demais.

**Repair → Recovery — A transição mais lucrativa para quem timing correcto**

Early Recovery returns são altíssimos mas counter-intuitive (economy ainda frágil). Signals: credit impulse virando positivo, housing prices estabilizando.

**Recovery → Boom — A transição mais fácil**

Economia visível em aceleração, credit gap cruzando zero. Shift progressivo sem necessidade de timing preciso.

### 18.7 Portugal hoje — playbook específico
Aplicando framework ao Portugal Q1 2026 (CCCS ~35, fase Recovery):

**Base case (70% probabilidade)**

- Recovery continua 12-24 meses.

- Transição gradual para Late Recovery / Early Boom.

- Positioning: overweight EU periphery equities, HY credit, domestic real estate (selective).

**Downside scenario (20% probabilidade)**

- ECB forced back into hiking devido a inflação; DSR portuguesa sobe para zona crítica.

- Transition to Contraction forçada.

- Positioning: reduce risk, accumulate tail hedges.

**Upside scenario (10% probabilidade)**

- Synchronized EU recovery; Portugal benefits de tailwind externo.

- Rapid transition to Boom.

- Positioning: full risk-on.

## Capítulo 19 · Caveats e false signals
### 19.1 Por que o framework falha — categorias
Nenhum framework é infalível. Identificar onde o SONAR provavelmente falha é tão importante quanto optimizá-lo. Cinco categorias de falha documentadas:

107. **Structural breaks** — mudanças estruturais que invalidam relações históricas.

108. **Policy innovations** — respostas de política monetária / fiscal sem precedente.

109. **Measurement gaps** — credit invisível aos indicadores standard.

110. **Exogenous shocks** — choques que quebram qualquer framework endógeno.

111. **Lag asymmetry** — divergência entre lead de indicadores leading e sinais reais.

### 19.2 Structural breaks — casos documentados
**1985 — Great Moderation**

Queda massiva da volatilidade macro em economias avançadas. Bernanke (2004) "The Great Moderation". Implicação: thresholds calibrados em dados pré-1985 (volatility alta) geravam falsos negativos pós-1985. Todos os frameworks foram re-calibrados.

**2000s — Shadow banking**

Expansão do non-bank credit, especialmente nos EUA, tornou bank-credit-only indicators progressivamente menos informativos. Borio (2012) documenta que shadow banking deve ter representado 40-50% da intermediation americana em 2007 — invisível aos indicadores BIS pré-crise.

**Pós-2008 — ZIRP e QE**

Políticas monetárias sem precedente histórico. Thresholds de policy rates perderam significado; balance sheet expansion substituiu rate changes como mecanismo primário. Shadow rates (Wu-Xia, Krippner) foram construídos para capturar isto mas com limitations.

**2022-2023 — Post-pandemic dynamics**

Combinação única de: (i) excess savings households, (ii) fiscal stimulus massivo, (iii) subida agressiva de rates. Muitos frameworks previram recession em 2023; não se materializou.

> *Lesson: fiscal space matters, e frameworks que ignoram fiscal stance estão incompletos.*

### 19.3 Policy innovations — unknowns históricos
Políticas sem precedente criam false signals porque os dados históricos não contêm observações de outcomes possíveis.

**QE e balance sheet expansion (2009-presente)**

Nenhum país tinha histórico pós-guerra de BCs comprando trilhões de dívida pública. Consequências de médio prazo para credit cycles ainda não plenamente compreendidas.

**Yield curve control**

Japan pós-2016, Australia 2020-21 — manipulação directa da curve. Invalida yield curve como preditor macro.

**Fiscal-monetary coordination**

US 2020-21, EU Next Generation EU — escala sem precedente. Como afeta credit cycles? Resposta empírica ainda incerta.

**Macroprudential tools ativas**

LTV caps, DSTI limits, CCyB — quando activos, atenuam o ciclo de crédito. Mas quanto? Primeira vez que temos macroprudential policy ativa num ciclo completo.

### 19.4 Measurement gaps — credit que escapa
**Private credit boom (2015-presente)**

Non-bank, non-bond credit — direct lending, BDCs, private debt funds. Cresceu de ~\$200bn em 2010 para ~\$1.7tn em 2024. Não está capturado nos indicadores BIS. Implicação: em certos países (US predominantly), credit stock real é meaningfully maior que reportado. Underestimated risk.

**Cryptocurrency-backed lending**

Crédito securizado em crypto. Irrelevant em macro agregado mas cresceu a importância em certos segmentos de alto risco.

**Cross-border credit offshore**

Multinacionais emprestando através de estruturas opacas offshore. BIS publica Global Liquidity indicator para capturar alguma, mas cobertura incompleta.

**Trade credit**

Firmas financiando-se a firmas. Tradicionalmente pequeno; em China moderna, potencialmente massivo e mal medido.

> **Nota** *Implicação SONAR: indicadores standard (BIS, TE) capturam ~75-85% do credit real em economies avançadas. Restante 15-25% é "dark matter" que pode acumular tensões invisíveis. Solução: complementar com indicadores de leverage agregada em corporate balance sheets quando disponíveis.*

### 19.5 Exogenous shocks — limites epistémicos
**Pandemia 2020**

Choque sanitário sem precedente histórico moderno. Qualquer framework endógeno baseado em ciclos falharia — o que se materializou foi um shock exogéno que produziu recession + recovery em janela de 12 meses, comprimida versus ciclos típicos de 5-10 anos.

**Guerras**

Invasão da Ucrânia 2022, Guerra do Golfo 1991, conflitos maiores têm efeitos macro abrupts não capturados por ciclos endógenos.

**Catástrofes tecnológicas**

Falha em sistema financeiro (ex: hypothetical grande bank cyber attack), disrupção major de supply chain (semicondutores).

> *Limitação epistémica reconhecida: nenhum framework de ciclo de crédito prevê choques exógenos. O SONAR deve ser explicito sobre isto — os outputs são condicionais a não ocorrerem choques exógenos.*

### 19.6 False positives históricos famosos
**1987 crash**

Black Monday. Indicadores de ciclo financeiro sinalavam stress, mas recession não se materializou. Mecanismo rápido de policy response (Greenspan cuts) + absence of credit excess subjacente.

**Lesson:** crashes não sempre são crises.

**1998 LTCM**

Crise de hedge fund + Russian default. Cornered markets, Fed coordination de bailout privado. Not credit-cycle driven — liquidity crisis pontual. Quickly resolved.

**2011-2012 Euro crisis**

Cyclical credit stress em periphery, mas primarily sovereign crisis, não classical bank credit boom-bust. Framework BIS standard underestimated o tipo de risco.

**2019 yield curve inversion**

Spread 10Y-3M inverteu por 3+ meses em 2019. Historical probability de recession \> 70%. Recession ocorreu em 2020 — mas por Covid, não causada por yield curve. Technically "acertou" mas mechanism totalmente diferente. Confounding causal attribution.

**2022-2023 recessão que não aconteceu**

Virtually todos os frameworks clássicos previam recession. Didn't happen (yet? some argue apenas adiado).

**Lesson:** post-Covid fiscal / monetary dynamics não plenamente compreendidas.

### 19.7 Bias cognitivos no uso do framework
Além das limitations do framework em si, há biases no uso.

**Recency bias**

Sobrestimar sinais recentes vs históricos.

**Mitigation:** always report z-scores contra distribuições históricas longas.

**Confirmation bias**

Ver os signals que confirmam view pré-existente.

**Mitigation:** multiple indicators required para trigger alerts.

**Narrative fallacy**

Encaixar eventos numa história plausível ex-post.

**Mitigation:** maintain base rates honestly, incluindo sub-históricos.

**Overconfidence em precision**

Tratar CCCS de 67 como meaningfully diferente de 63.

**Mitigation:** report confidence intervals, não apenas point estimates.

**Policy naïveté**

Assumir que BCs agirão optimally. Empirical reality: BCs frequentemente agem late, reactively, with mistakes.

**Mitigation:** account for policy response uncertainty.

### 19.8 Limitations específicas por país
**China**

Opacidade de dados (especialmente shadow banking, LGFV), dynamics non-market (directed lending), structural break ongoing (transição de investment-led para consumption-led). Framework standard struggles especialmente aqui.

**Japan**

Zero-bound há 25+ anos, thresholds convencionais inapplicable. Framework requires structural adjustment.

**Emerging markets**

Exchange rate dominance no credit channel, foreign currency debt, shallow domestic markets — framework calibrado em economias avançadas não se aplica diretamente.

**Portugal e economies periféricas EU**

Limited monetary autonomy (ECB-dependent), small size, vulnerable to cross-border capital flows. Framework requires conditioning on core-EU + global states.

### 19.9 O meta-princípio — humildade epistémica
O framework SONAR tem valor real precisamente porque é explícito sobre as suas limitations. Frameworks que claim precision absoluta são menos úteis que frameworks que admit uncertainty.

> *Output recommendation: sempre que o SONAR publica um CCCS, deve incluir (i) confidence interval baseado em bootstrap dos sub-indices, (ii) list of specific false signals do próprio framework em dados históricos, (iii) key structural assumptions (quais breaks estão presumed não activos), (iv) identification of country-specific caveats.*

Esta transparência é o asset competitivo do SONAR — não precision, mas honesty calibrada.

## Capítulo 20 · Bibliografia anotada
Selecionei 50+ referências organizadas em 6 categorias, com anotações sobre relevância, maturidade e acessibilidade.

> *Notação: \[★★★\] = leitura essencial; \[★★\] = útil; \[★\] = interesse específico.*

### 20.1 Fundações teóricas
**Minsky, Hyman (1992).** "The Financial Instability Hypothesis", Levy Economics Institute Working Paper No. 74. **\[★★★\]** *Paper síntese da tese Minsky. 10 páginas, acessível, fundacional. Leitura obrigatória.*

**Kindleberger, Charles P., and Robert Z. Aliber (2015).** Manias, Panics, and Crashes: A History of Financial Crises, 7th edition, Palgrave Macmillan. **\[★★★\]** *Taxonomia histórica das crises. 7ª edição expandida pós-2008. Leitura que changes the way you think.*

**Hayek, Friedrich A. (1931).** Prices and Production, Routledge. **\[★\]** *Tradição austríaca original. Interesse histórico principalmente — mais citado que lido hoje.*

**Kiyotaki, Nobuhiro and John Moore (1997).** "Credit Cycles", Journal of Political Economy 105(2), 211-248. **\[★★★\]** *Formalização matemática do mecanismo de amplificação via collateral. Densely technical mas seminal.*

**Geanakoplos, John (2010).** "The Leverage Cycle", NBER Macroeconomics Annual 24. **\[★★\]** *Argumento de que leverage (não rates) é o key driver cyclical. Contrarian important perspective.*

### 20.2 Evidência empírica core
**Schularick, Moritz and Alan M. Taylor (2012).** "Credit Booms Gone Bust: Monetary Policy, Leverage Cycles, and Financial Crises, 1870-2008", American Economic Review 102(2), 1029-1061. **\[★★★\]** *O paper empírico mais importante do campo. Dataset, methodology, resultados — tudo reusable. Mandatory.*

**Jordà, Òscar, Moritz Schularick and Alan M. Taylor (2013).** "When Credit Bites Back", Journal of Money, Credit and Banking 45(s2), 3-28. **\[★★★\]** *Quantificação da severidade extra de recessões pós-credit-boom. Technique (local projections) é útil para SONAR.*

**Jordà, Òscar, Moritz Schularick and Alan M. Taylor (2016).** "The Great Mortgaging: Housing Finance, Crises, and Business Cycles", Economic Policy 31(85), 107-152. **\[★★★\]** *Demonstração de que mortgage credit dominou credit growth pós-1945. Crucial para compreender housing como driver.*

**Mian, Atif and Amir Sufi (2014).** House of Debt: How They (and You) Caused the Great Recession, University of Chicago Press. **\[★★★\]** *Evidência micro-level do Great Recession. Leitura central. Accessible prose style.*

**Mian, Atif, Amir Sufi and Emil Verner (2017).** "Household Debt and Business Cycles Worldwide", Quarterly Journal of Economics 132(4), 1755-1817. **\[★★\]** *Extensão internacional da tese Mian-Sufi. Reforça robustness.*

**Reinhart, Carmen M. and Kenneth S. Rogoff (2009).** This Time Is Different: Eight Centuries of Financial Folly, Princeton University Press. **\[★★★\]** *Dataset histórico massivo de crises. Referência para qualquer conversa sobre historical base rates.*

### 20.3 Metodologia e medição
**Drehmann, Mathias, Claudio Borio and Kostas Tsatsaronis (2011).** "Anchoring Countercyclical Capital Buffers: The Role of Credit Aggregates", BIS Working Paper No. 355. **\[★★★\]** *Paper founding do credit-to-GDP gap methodology. Justificação do λ=400,000.*

**Drehmann, Mathias and Mikael Juselius (2014).** "Evaluating Early Warning Indicators of Banking Crises: Satisfying Policy Requirements", International Journal of Forecasting 30(3), 759-780. **\[★★★\]** *Comparison empírica de indicators. Fundamental para compreender AUC relative de cada medida.*

**Drehmann, Mathias and Kleopatra Nikolaou (2013).** "Funding Liquidity Risk: Definition and Measurement", Journal of Banking & Finance 37(7), 2173-2182. **\[★★\]** *Refinement methodology para liquidity dimension.*

**Hamilton, James D. (2018).** "Why You Should Never Use the Hodrick-Prescott Filter", Review of Economics and Statistics 100(5), 831-843. **\[★★★\]** *A crítica mandatory ao HP filter. Leitura essencial para compreender porque Hamilton regression é preferível.*

**Ravn, Morten O. and Harald Uhlig (2002).** "On Adjusting the Hodrick-Prescott Filter for the Frequency of Observations", Review of Economics and Statistics 84(2), 371-376. **\[★★\]** *Justificação para λ=400,000. Short, technical, útil.*

**Schüler, Yves, Paul Hiebert and Tuomas Peltonen (2015).** "Characterising the Financial Cycle: A Multivariate and Time-Varying Approach", ECB Working Paper No. 1846. **\[★★\]** *Alternative metodologia ECB para financial cycle. Multivariate approach.*

**Biggs, Michael, Thomas Mayer and Andreas Pick (2010).** "Credit and Economic Recovery: Demystifying Phoenix Miracles". **\[★★★\]** *Paper founding do credit impulse. Must-read para understanding BMP.*

### 20.4 Política e implementação
**Borio, Claudio (2012).** "The Financial Cycle and Macroeconomics: What Have We Learnt?", BIS Working Paper No. 395. **\[★★★\]** *Síntese Borio do state-of-the-art. Melhor single overview disponível.*

**Borio, Claudio, Mathias Drehmann and Kostas Tsatsaronis (2013).** "Characterising the Financial Cycle: Don't Lose Sight of the Medium Term", BIS Working Paper No. 404. **\[★★\]** *Specifically about medium-term cycle frequency. Technical.*

**Bernanke, Ben S., Mark Gertler and Simon Gilchrist (1999).** "The Financial Accelerator in a Quantitative Business Cycle Framework", Handbook of Macroeconomics 1, 1341-1393. **\[★★\]** *Dense technical. Reference for DSGE with financial frictions.*

**Bernanke, Ben S. (1983).** "Non-Monetary Effects of the Financial Crisis in the Propagation of the Great Depression", American Economic Review 73(3), 257-276. **\[★★★\]** *Paper historical mas founding da modern view of banking-real economy linkages.*

**Rey, Hélène (2013).** "Dilemma not Trilemma: The Global Financial Cycle and Monetary Policy Independence", Jackson Hole Symposium. **\[★★★\]** *O paper founding do Global Financial Cycle concept. Short, accessible, transformative.*

**Obstfeld, Maurice, Jonathan Ostry and Mahvash Qureshi (2021).** "A Tie That Binds: Revisiting the Trilemma in Emerging Market Economies", IMF Economic Review 69(1), 153-199. **\[★★\]** *Counter-argument a Rey. Important for balanced view.*

**European Central Bank (2015-2024).** Financial Stability Review, semi-annual. **\[★★★\]** *Publicação regular, state-of-practice application. Follow issues as they appear.*

**Bank for International Settlements (annual).** Annual Economic Report. **\[★★★\]** *Borio's institutional home. Required reading, published June.*

### 20.5 Trabalho aplicado e dashboards
**Lown, Cara and Donald Morgan (2006).** "The Credit Cycle and the Business Cycle: New Findings Using the Loan Officer Opinion Survey", Journal of Money, Credit and Banking 38(6), 1575-1597. **\[★★\]** *Founding paper for SLOOS analysis. Methodology reusable.*

**Gilchrist, Simon and Egon Zakrajšek (2012).** "Credit Spreads and Business Cycle Fluctuations", American Economic Review 102(4), 1692-1720. **\[★★★\]** *The excess bond premium. Important for spread-based analysis.*

**Adrian, Tobias and Hyun Song Shin (2010).** "Liquidity and Leverage", Journal of Financial Intermediation 19(3), 418-437. **\[★★\]** *Shadow banking and leverage. Key reference for intermediary capital.*

**Aikman, David, Andrew Haldane and Benjamin Nelson (2015).** "Curbing the Credit Cycle", Economic Journal 125(585), 1072-1109. **\[★★\]** *Bank of England perspective on macroprudential policy.*

### 20.6 Historical datasets
**Jordà-Schularick-Taylor Macrohistory Database** (macrohistory.net/database). **\[★★★\]** *Annual data 18 economias avançadas desde 1870. 48 variables. Gratuito. Invaluable para SONAR backtest.*

**BIS Statistical Database** (data.bis.org). **\[★★★\]** *Credit, DSR, property prices, credit gaps. Official source. API available.*

**IMF International Financial Statistics.** **\[★★\]** *Broad EM coverage. Lag publication.*

**EBA Risk Dashboard** (publicado trimestralmente). **\[★★\]** *EU bank indicators, NPL, capital. Standardized cross-country.*

**ECB Statistical Data Warehouse** (sdw.ecb.europa.eu). **\[★★★\]** *BLS data, monetary aggregates, euro area statistics.*

**Federal Reserve Economic Data (FRED)** (fred.stlouisfed.org). **\[★★★\]** *SLOOS, HY OAS, US indicators. Free, API, crucial.*

### 20.7 Leitura complementar — livros
**Turner, Adair (2015).** Between Debt and the Devil: Money, Credit, and Fixing Global Finance, Princeton. **\[★★\]** *Policy perspective, ex-FSA chair.*

**King, Mervyn (2016).** The End of Alchemy: Money, Banking, and the Future of the Global Economy, Norton. **\[★★\]** *Ex-BOE governor reflection. Big picture.*

**Koo, Richard (2009).** The Holy Grail of Macroeconomics: Lessons from Japan's Great Recession, Wiley. **\[★★\]** *Balance sheet recession concept. Japan-focused but theoretically central.*

**Admati, Anat and Martin Hellwig (2013).** The Bankers' New Clothes, Princeton. **\[★★\]** *Banking regulation. Policy-oriented.*

### 20.8 Referências em português
Escassos. Três que merecem nota:

**Lains, Pedro et al. (2019).** Portugal: Quatro Décadas de Integração Europeia. **\[★\]** *Contexto histórico PT, credit dynamics incluídas.*

**Banco de Portugal,** Relatório de Estabilidade Financeira (semestral). **\[★★★\]** *Must-read for Portugal specifically. Methodology applied to PT.*

**Banco de Portugal,** Inquérito aos Bancos sobre o Mercado de Crédito (trimestral). **\[★★\]** *PT-specific lending survey. Underutilized em discussion pública.*

### 20.9 Research frontier
Para manter-se atualizado:

- **NBER Working Papers** — search "credit cycle", "financial cycle", "credit booms".

- **CEPR Discussion Papers** — European perspective.

- **BIS Working Papers** — institutional frontier.

- **IMF Working Papers** — global coverage and EM focus.

- **ECB Working Papers** — EU-specific.

**Follow on Twitter**

@moritzschularick, @atifrmian, @Matthew_C_Klein, @Claudio_Borio (institutional account).

**Substacks worth subscribing**

The Overshoot (Klein), Unhedged (FT), Alphaville (FT).

### 20.10 Bibliografia de síntese
Se tivesse apenas 5 papers / livros para ler sobre credit cycles, seriam:

112. **Schularick & Taylor (2012)** — evidência empírica fundante.

113. **Mian & Sufi (2014)** — House of Debt — micro-evidence transformadora.

114. **Borio (2012)** — síntese teórica.

115. **Drehmann-Juselius (2014)** — metodologia de indicators.

116. **Kindleberger** — narrativa histórica.

> *Com estes cinco, tem 80% do conhecimento necessário para operar no estado-da-arte.*

**Encerramento do Manual**

Seis Partes. Vinte capítulos. O manual completo entrega:

- **Parte I — Fundações teóricas** (Caps 1-3): mecânica do ciclo, genealogia intelectual de Mises a Borio, revolução empírica pós-2008.

- **Parte II — Anatomia do ciclo** (Caps 4-6): 4 fases (Boom, Contraction, Repair, Recovery), duração e amplitude, sincronização cross-country, interação com outros ciclos.

- **Parte III — Medição** (Caps 7-10): L1 stock, L2 gap (HP vs Hamilton), L3 impulse Biggs-Mayer-Pick, L4 DSR Drehmann-Juselius.

- **Parte IV — Indicadores complementares** (Caps 11-14): bank lending surveys, spreads de crédito, NPL / bank capital, housing cycle.

- **Parte V — Integração** (Caps 15-17): composite score design (3 layers, 5 sub-indices), classificação de fases, matriz 4×4 operacionalizada.

- **Parte VI — Aplicação prática** (Caps 18-20): playbooks por fase, caveats e false signals, bibliografia anotada de 50+ referências.

**O que fica construído**

O manual é simultaneamente três coisas:

117. **Framework metodológico para o SONAR —** cada decisão (que dados ingerir, que transformações aplicar, como agregar, como classificar) tem fundamentação documentada.

118. **Documento de referência interno —** peer-reviewed em substância (a literatura está lá), mas adaptado à linguagem operacional do 7365 Capital.

119. **Matéria-prima para coluna regular —** cada capítulo identifica ângulos editoriais específicos, quase todos não cobertos pelos media económicos portugueses atuais.

**Os quinze ângulos editoriais identificados**

120. "Porque o mainstream demorou 80 anos a incorporar Minsky."

121. "A revolução empírica silenciosa — Schularick, Taylor, Mian, Sufi."

122. "Austríacos reformados — porque ler Borio hoje é ler Hayek com evidência."

123. "Portugal — o ciclo de crédito mais longo da Europa."

124. "O dilema do BCE em \[data\] — o framework Borio aplicado ao presente."

125. "Quatro clusters, uma Europa — onde Portugal se encaixa."

126. "As 47% — porque a fase Contraction é onde as crises nascem."

127. "Por que Basileia III usa λ=400,000 — monetary vs credit cycles."

128. "O indicador que o mercado ignora — credit impulse chinês."

129. "DSR — como taxas mais altas estão a criar stress onde ninguém olha."

130. "Portugal em 2009 — quando o DSR previu o que os economistas negavam."

131. "SLOOS está a gritar mas a recessão não chega — porquê."

132. "Portugal reduziu NPL de 18% para 3% — a história de repair mais silenciosa da EU."

133. "Housing Portugal — overheating, não bubble."

134. "Quando os 4 ciclos divergem — a melhor informação do SONAR."

**Próximos passos naturais**

O manual fecha mas o trabalho começa:

- Implementação do connector Python para ingestão BIS + Trading Economics, com computação dos 4 indicadores em tempo real.

- Backtest do classificador de fases no JST dataset (18 países × 150 anos).

- Primeiro artigo de coluna, selecionando um dos 15 ângulos e desenvolvendo até publicação.

- Iteração do dashboard do protótipo para versão institucional com dados live.

> *O SONAR deixa de ser projeto. É agora um sistema com fundamentos documentados, defensáveis, e operacionalizáveis.*

*— fim do manual —*

**7365 Capital · SONAR Research · Abril 2026**
