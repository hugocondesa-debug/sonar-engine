# L1 · Credit-to-GDP stock

> Sub-índice do Ciclo de Crédito (CCCS) — capítulo 7 do manual (Manual_Ciclo_Credito_COMPLETO).

### 7.1 A definição canónica BIS
O ponto de partida é aparentemente trivial mas cheio de armadilhas práticas. A definição do BIS para o credit-to-GDP ratio é:

*CtG_t = Total credit to PNFS_t / Nominal GDP\_{t, 4Q sum} × 100*

Cada elemento desta fórmula tem decisões metodológicas que afetam materialmente o resultado.

### 7.2 O numerador — Total credit to private non-financial sector
A variável-chave é total credit to the private non-financial sector (PNFS), que o BIS define como a soma de três componentes:

41. **Loans from domestic banks** — empréstimos concedidos por instituições depositárias residentes.

42. **Loans from non-bank financial institutions** — insurance, pension funds, finance companies, credit unions.

43. **Debt securities issued by non-financial sector** — bonds emitidos por firmas e, em alguns países, por municipalities.

**Exclusões importantes**

- Governo central e governos locais (excluídos do "private").

- Firmas financeiras (são intermediários, não tomadores finais).

- Inter-bank lending.

- Cross-border lending em alguns casos (o BIS tem ambas as séries).

**Sub-agregados úteis**

- Credit to households — particularmente mortgage vs non-mortgage.

- Credit to non-financial corporations — core business lending.

- Total credit = sum dos dois.

### 7.3 As duas variantes BIS — Q vs F
O BIS publica duas versões do credit stock que diferem materialmente.

**Q-series (all sectors providing credit)**

- Inclui bank + non-bank + bond issuance.

- É a "total credit" definition.

- Cobertura: 44 economias.

**F-series (banks only)**

- Apenas credit provided by domestic banks.

- Histórico mais longo (algumas séries desde 1940s).

- Cobertura: 90+ economias.

A diferença entre Q e F é estruturalmente importante. Em economias com mercados de capitais desenvolvidos (US, UK), a divergência é enorme:

| **País**      | **Bank credit / GDP (F)** | **Total credit / GDP (Q)** | **Diferença** |
|---------------|---------------------------|----------------------------|---------------|
| US 2024       | ~50%                      | ~155%                      | 105 pp        |
| UK 2024       | ~75%                      | ~155%                      | 80 pp         |
| Japan 2024    | ~115%                     | ~185%                      | 70 pp         |
| Germany 2024  | ~85%                      | ~145%                      | 60 pp         |
| Portugal 2024 | ~95%                      | ~145%                      | 50 pp         |

> **Nota** *Para o SONAR: usar sempre Q quando disponível. F subestima o credit stock em economias com capital markets ativos, o que enviesa o credit gap para baixo e subestima riscos. Usar F apenas quando Q não está disponível (economias menores, emergentes) ou para backtests pré-1970.*

### 7.4 O denominador — Nominal GDP
O GDP no denominador tem três decisões metodológicas.

**Decisão 1 — Nominal ou real?**

BIS usa nominal GDP. Isto é crítico e frequentemente mal compreendido. O ratio é nominal-over-nominal — credit em unidades monetárias correntes dividido por GDP em unidades monetárias correntes. Assim, efeitos de inflação cancelam parcialmente no ratio, e é esta propriedade que torna a série comparável ao longo do tempo.

**Decisão 2 — 4-quarter rolling sum ou ponto-a-ponto?**

BIS usa soma rolling de 4 trimestres. Isto suaviza sazonalidade (crítico para países com ciclos de produção sazonais) e reduz volatilidade artificial do ratio.

**Decisão 3 — Revised ou real-time?**

GDP é revisto múltiplas vezes. Para backtest honesto, usar vintage real-time (dado disponível no momento t, não dado revisto). Para análise histórica, usar final revised.

> *O SONAR deve implementar ambos os modes: "production" usa GDP revised (último disponível); "backtest" usa GDP vintage (como estava no momento). Os thresholds BIS foram calibrados com dados revistos, mas na prática usamos dados não-revistos em tempo real. O endpoint bias entre os dois pode ser material (~1-2pp no gap).*

### 7.5 Interpretação do nível — o que o absoluto diz
O nível absoluto do credit-to-GDP ratio não é, isoladamente, diagnóstico de risco. Dois equivalentes com significados diferentes:

- **Suíça com CtG ~250%** — sistema bancário estruturalmente grande servindo economia open + wealth management. Não é "stressed" — é "size structurally different".

- **China com CtG ~220%** — subiu de ~120% em 2008 para 220% em 2024. A dinâmica, não o nível, é o alarme.

**Heurística para leitura de níveis cross-country**

| **CtG level** | **Leitura estrutural típica**                  |
|---------------|------------------------------------------------|
| \< 50%        | Economia sub-financeirizada (emerging)         |
| 50-100%       | Desenvolvimento financeiro intermédio          |
| 100-150%      | Economia avançada típica                       |
| 150-200%      | Economia altamente financeirizada              |
| \> 200%       | Outlier estrutural (CH) ou stress latente (CN) |

Para Portugal hoje (~145%): enquadra-se no range normal para economia EU avançada. O que é diagnóstico não é este número, é a sua trajetória desde 2010 (pico 205%) — ou seja, o que interessa é o gap, não o stock.

### 7.6 Armadilhas de medição a evitar
Cinco erros comuns em implementações do ratio credit-to-GDP:

**Erro 1 — Usar M3 ou money aggregates em vez de credit**

M3 mede liabilities do sistema bancário (deposits), não credit extended. Em economias modernas, a divergência é enorme — bancos financiam credit via wholesale funding, não apenas depósitos. Série errada.

**Erro 2 — Usar government debt no numerador**

Government debt é parte da dívida agregada mas segue dinâmica política, não Minsky. Modelos que misturam os dois produzem resultados enviesados.

**Erro 3 — Não ajustar por exchange rate em crédito denominado em moeda estrangeira**

Crítico em emerging markets. Hungria em 2008 tinha ~30% do household credit em CHF. Quando o CHF apreciou 40% vs HUF, o stock em moeda doméstica explodiu overnight sem novo crédito ser emitido. BIS ajusta-se para isto na série Q; implementações caseiras frequentemente não.

**Erro 4 — Ignorar write-offs na série**

Após bustos, bancos fazem write-offs massivos de NPLs. Isto reduz o stock de credit nos dados, não porque houve deleveraging genuíno mas porque houve reconhecimento contabilístico. A série BIS lida com isto via uma metodologia específica; alternativas podem sub-estimar o stock efetivo.

**Erro 5 — GDP trimestral vs anual**

Algumas séries reportam credit trimestral mas GDP anual. Dividir um pelo outro dá ratio errado. Tem de ser ambos trimestrais (ou ambos anuais).

### 7.7 Séries longas — o contributo JST
Para backtest de modelos SONAR com séries longas, o Jordà-Schularick-Taylor database é o recurso. Cobertura (anual, desde 1870, 18 economias avançadas):

- Total loans (banks + non-banks, quando disponível).

- Mortgage loans vs non-mortgage loans (separação desde 1870 em vários países).

- GDP nominal.

Limitações: frequência anual, não trimestral. Para períodos pré-1960, Q (total credit) não está disponível — apenas F (bank credit).

> **Nota** *Recomendação operacional para o SONAR: para dados trimestrais (1970-presente) usar BIS Q-series como primary; para dados anuais longos (1870-1970) usar JST database para backtest; para emerging markets sem cobertura BIS usar BIS F-series + Trading Economics para complementar.*
