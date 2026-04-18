**FRAMEWORK QUANTITATIVO**

**Manual dos**

**Sub-Modelos Quantitativos**

*Os cinco outputs derivados dos ciclos — yield curves, ERP, CRP, rating-spread, expected inflation — com calibração diária e cobertura cross-country*

**ESTRUTURA**

**Seis partes ·** Vinte capítulos · *Fundações, yield curves, ERP, CRP, rating+inflação, integração*

**Cinco outputs operacionais ·** 15+ países cobertos · *Daily updates onde dados permitem*

**Framework Damodaran extended ·** NSS yield curves · *Portugal deep dive — do CRP crisis ao CRP normalizado*

**Bibliografia anotada ·** Use cases completos · *EDP DCF worked example, Brazilian bank cross-border*

**HUGO · 7365 CAPITAL**

*SONAR Research · Quinto manual · Fecho arquitetural da v1*

Abril 2026 · Documento de referência interno

**Índice**

# PARTE I · Fundações
> **Cap. 1 ·** Os cinco outputs complementares aos ciclos
>
> **Cap. 2 ·** Cost of capital cross-border — do CAPM ao framework integrado
>
> **Cap. 3 ·** Moeda funcional e ajustamentos inflação-câmbio

# PARTE II · Yield curves por país
> **Cap. 4 ·** Metodologia de construção de yield curves
>
> **Cap. 5 ·** Fontes de dados e implementation per country
>
> **Cap. 6 ·** Outputs operacionais — spot, forward, zero, real

# PARTE III · ERP diária computada
> **Cap. 7 ·** Teoria do implied Equity Risk Premium
>
> **Cap. 8 ·** Implementação técnica — S&P 500 e análogos
>
> **Cap. 9 ·** Validação e signal quality

# PARTE IV · Country Risk Premium
> **Cap. 10 ·** CDS-based approach e a estrutura do country default risk
>
> **Cap. 11 ·** Sovereign spread approach quando CDS ilíquido
>
> **Cap. 12 ·** Volatility ratio synthesis — operational output per country

# PARTE V · Rating mapping e Expected inflation
> **Cap. 13 ·** Rating agency landscape e escala comum
>
> **Cap. 14 ·** Historical default rates e recovery
>
> **Cap. 15 ·** Rating-to-spread operational table
>
> **Cap. 16 ·** Expected inflation — market-based e surveys
>
> **Cap. 17 ·** Expected inflation cross-country e Portugal

# PARTE VI · Integração e aplicação
> **Cap. 18 ·** Arquitetura SONAR completa — ciclos e sub-models unificados
>
> **Cap. 19 ·** Use cases práticos — da valuation à coluna editorial
>
> **Cap. 20 ·** Caveats transversais e bibliografia anotada

# PARTE I
**Fundações**

*Os cinco outputs, cost of capital cross-border, moeda funcional*

**Capítulos nesta parte**

**Cap. 1 ·** Os cinco outputs complementares aos ciclos

**Cap. 2 ·** Cost of capital cross-border — do CAPM ao framework integrado

**Cap. 3 ·** Moeda funcional e ajustamentos inflação-câmbio

## Overlays L2 — ficheiros por overlay

- [NSS Yield Curves](./nss-curves.md) — Parte II · Yield curves por país
- [ERP Daily](./erp-daily.md) — Parte III · ERP diária computada
- [Country Risk Premium](./crp.md) — Parte IV · Country Risk Premium
- [Rating-to-Spread Mapping](./rating-spread.md) — Parte V (caps 13-15) · Rating mapping
- [Expected Inflation](./expected-inflation.md) — Parte V (caps 16-17) · Expected inflation



---

# PARTE I · Fundações transversais

## Capítulo 1 · Os cinco outputs complementares aos ciclos
### 1.1 O que o SONAR é — e o que não é
Nos quatro manuais anteriores, o SONAR foi estabelecido como framework de classificação de quatro ciclos interagindo: económico, de crédito, monetário e financeiro. Cada ciclo com score composite (ECS, CCCS, MSC, FCS), overlays dedicados (Stagflation, Boom, Dilemma, Bubble Warning) e integração via matriz 4-way.

Este manual estabelece que o SONAR não é plataforma de visualização de indicadores — não é competir com Trading Economics ou CEIC. O SONAR é motor analítico com dois pilares distintos:

1.  **Classificação de ciclo em tempo real + forecast.** Já coberto pelos quatro manuais anteriores.

2.  **Outputs quantitativos derivados, úteis per se.** Este manual. Cinco outputs independentes que consomem dados do mesmo universo, mas produzem resultados autónomos relevantes para análise de investimento.

> *Os cinco sub-modelos deste manual não são derivados dos ciclos — são outputs paralelos. Um CAPE está relacionado com o FCS, mas um yield curve do Bund não é input primário do MSC; é output autónomo que o MSC consome. A distinção importa arquiteturalmente.*

### 1.2 Os cinco sub-modelos identificados
**Sub-modelo 1 — Yield curves por país**

Curva de juro soberana nominal e real, por país coberto, de overnight a 30Y. Output para todos os tenores relevantes (3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y) com interpolação Nelson-Siegel-Svensson (NSS) ou splines cúbicas onde dados o permitam. Complementa o sub-modelo ERP (risk-free input) e o CRP (sovereign spread input).

- Razão de ser: a yield curve é primitivo do valuation de qualquer ativo

- Output standalone: independente dos ciclos, mas essencial para valuation cross-border

- Usado pelos ciclos (MSC usa shape da curva), mas é output per se

**Sub-modelo 2 — ERP diária computada**

Equity Risk Premium calculado pelo SONAR diariamente, não consumido de Damodaran mensalmente. Implied ERP via Gordon growth model + DCF approach sobre S&P 500 (e análogos para outros mercados desenvolvidos). Permite detetar em alta frequência mudanças no pricing de risco.

- Razão de ser: Damodaran publica mensalmente — insuficiente para market timing

- ERP diária permite deteção precoce de regime changes em risk pricing

- Metodologia própria documentável e replicável

- Cross-market: US, EA, UK, Japan separadamente

**Sub-modelo 3 — Country Risk Premium computado**

CRP para 30+ países, calculado pelo SONAR usando metodologia híbrida: default spread (via sovereign CDS ou sovereign bond spread vs risk-free) multiplicado por volatility ratio (equity vol / bond vol do país). Output operacional para ajustar cost of equity em mercados emergentes ou peripheral DM.

- Razão de ser: emerging markets e DM periphery exigem ajustamento explícito

- Portugal, Grécia, Italy: CRP relevante vs core EA

- EM: Turkey, Brazil, Argentina, India: CRP substantial

- Metodologia inspirada em Damodaran mas computada pelo SONAR

**Sub-modelo 4 — Rating-to-spread mapping**

Tabela operacional mapeando rating sovereign (S&P, Moody's, Fitch, DBRS convertidos a escala comum) para default spread em bps. Necessário quando CDS não está disponível ou líquido. Historical default rates + recovery rates determinam o mapping.

- Razão de ser: muitos países não têm CDS líquido

- Rating-based default spread é second-best mas universal

- Tabela calibrada com Moody's default history

- Atualizada quando rating changes ocorrem

**Sub-modelo 5 — Inflação esperada por país**

Expected inflation forward-looking, calculada via combinação de breakeven inflation (TIPS vs Treasury nominal nos países com mercado TIPS-like), inflation swaps (5Y, 10Y quando líquidos), e surveys profissionais (SPF, BoE/ECB surveys) quando market-based não disponível. Output essencial para ajustar cost of capital em USD/EUR quando moeda funcional do ativo é outra.

- Razão de ser: valuation em moeda local precisa de inflação esperada local

- Fisher equation: nominal rate = real rate + expected inflation

- Cross-border DCF requires inflation-adjusted discount rates

- Breakeven inflation (market) + SPF (survey) triangulated

### 1.3 Como os cinco sub-modelos se compõem
O arranjo arquitetural é importante. Os cinco outputs não são paralelos independentes — eles compõem-se hierarquicamente na maior parte dos use cases:

> Use case canónico: Cost of equity for Portuguese equity investment
> Layer 1 — Yield curve Portugal
> └─\> 10Y PT sovereign yield = 3.20%
> Layer 2 — Risk-free decomposition
> ├─\> 10Y Bund yield = 2.50% (risk-free proxy EA)
> └─\> PT spread vs Bund = 70bps (country default spread)
> Layer 3 — Country Risk Premium
> ├─\> Default spread component = 70bps
> ├─\> Volatility ratio PT equity vs PT bond = 1.4x
> └─\> CRP = 70bps × 1.4 = ~100bps
> Layer 4 — Mature market ERP
> └─\> Implied ERP US = 4.80% (SONAR daily computation)
> (assumed as mature market baseline)
> Layer 5 — Expected inflation adjustment (if relevant)
> ├─\> PT expected inflation 10Y = 2.20%
> └─\> EA expected inflation 10Y = 2.00%
> (adjustment = 0.20% differential if modeling in real terms)
> Cost of equity PT (nominal EUR):
> = Risk-free (Bund) + ERP_US + CRP_PT
> = 2.50% + 4.80% + 1.00%
> = 8.30%
> Cost of equity PT (real EUR):
> = 8.30% - 2.20%
> = 6.10%
>
> *A análise cross-border sem este framework é impossível de replicar com rigor. Damodaran publica mensalmente, mas analistas profissionais precisam de outputs diários consistentes. O SONAR entrega isso.*

### 1.4 Relação com os quatro ciclos SONAR
**Consumidor principal — Financial Cycle (FCS)**

O FCS do Cap 7 consome ERP como input primário em F1 (Valuations). A ERP diária permite FCS atualizar em frequência mais alta do que mensal. O CRP para países não-core determina se assessment é aplicável.

**Consumidor secundário — Monetary Cycle (MSC)**

O MSC do manual monetário usa yield curve shape (level, slope, curvature) como input. Nelson-Siegel-Svensson decomposition produz estes três factors limpos. Parte III deste manual fornece-os.

**Consumidor terciário — Credit Cycle (CCCS)**

O CCCS não consome diretamente estes outputs, mas o rating-to-spread mapping é primitivo para tracking de sovereign credit quality que afeta CCCS periphery.

**Consumidor implícito — Economic Cycle (ECS)**

O ECS usa expected inflation para distinguir real vs nominal em alguns indicators. O output do Sub-modelo 5 feed direto.

**Circularidade controlada**

Há alguma circularidade. O MSC afeta yield curve (obvious) e yield curve é usada para MSC shape inputs. Mas isto é como Economia funciona — uma rate cut do BC afeta o overnight, que propaga ao longo da curva, que é lida como "accommodative stance" pelo MSC. O framework aceita esta reflexão; calibração histórica valida.

### 1.5 Outputs standalone — uso independente dos ciclos
Os cinco sub-modelos têm valor per se, fora do contexto de cycle classification:

**Uso 1 — Valuation cross-border DCF**

- Analista valuating Portuguese equity needs risk-free EUR, CRP PT, ERP matured market

- SONAR fornece as três inputs consistentes

- Alternativa: coligir manualmente Bloomberg (cost), Damodaran (monthly), múltiplas fontes

- SONAR collapse to single daily feed

**Uso 2 — Bond portfolio management**

- Yield curves cross-country em formato NSS permitem factor decomposition rigorous

- Level/slope/curvature factors para PCA portfolio construction

- Real yield curves separadas de nominal

**Uso 3 — Inflation-linked products**

- Expected inflation cross-country permite breakeven comparisons

- Inflation-protected bonds vs nominal arbitrage

- Inflation swap pricing input

**Uso 4 — Credit analysis**

- Rating-to-spread mapping permits repricing scenarios

- If rating changes from A+ to A-, mapping shows implied spread change

- Ferramenta para sovereign credit stress tests

**Uso 5 — Macro strategist commentary**

- "Em Portugal, o cost of equity subiu 50bps trimestralmente" — SONAR sabe

- "A ERP implícita no S&P 500 atingiu 4.2%, mínimo desde 2007" — SONAR sabe

- "Brazil's CRP caiu 80bps com o rating upgrade" — SONAR sabe

- Editorial voice poderosa

### 1.6 Posicionamento face a peers
**Bloomberg Terminal**

- Fornece todos estes outputs separadamente

- Custo: \$24k/ano

- Pontos fortes: liquidez real-time, coverage amplo

- Pontos fracos: outputs dispersos, metodologia opaque, não combine bem com cycle framework

**Damodaran free resources**

- ERP, CRP, rating spread mapping todos publicados mensalmente

- Custo: gratuito

- Pontos fortes: metodologia documentada, estabelecida academicamente, reputation

- Pontos fracos: mensal (insuficiente para trading), US-centric, não cross-integrated

**Refinitiv/Eikon**

- Similar ao Bloomberg, slightly cheaper

- Custo: \$22k/ano

**SONAR Sub-Modelos**

- Cinco outputs em formato integrado

- Custo operacional: gratuito a baixo (data sources free, compute local)

- Pontos fortes: daily, cross-integrated with cycle framework, metodologia própria documentada

- Pontos fracos: construir-por-construir, calibração requer backtest

> *Não é sobre ser melhor que Bloomberg. É sobre construir framework integrado onde cycle classification + derived outputs formam pipeline coherent, algo que Bloomberg e Damodaran separadamente não oferecem.*

### 1.7 Arquitetura técnica — como os cinco se encaixam
> SONAR Data Layer
> (FRED, ECB, BIS, Shiller, Glassnode, etc.)
> │
> ▼
> ┌────────────────────────────────┐
> │ Sub-model computation │
> │ (this manual — five modules) │
> │ │
> │ 1. Yield curves (per country) │
> │ 2. ERP daily (S&P500, etc.) │
> │ 3. CRP (30+ countries) │
> │ 4. Rating→Spread mapping │
> │ 5. Expected inflation │
> └────────────────────────────────┘
> │
> ▼
> ┌───────────────────────────────────────┐
> │ Cycle classification consumers │
> │ │
> │ ECS (economic) ◄─ inflation exp. │
> │ CCCS (credit) ◄─ rating→spread │
> │ MSC (monetary) ◄─ yield curve │
> │ FCS (financial) ◄─ ERP daily, CRP │
> └───────────────────────────────────────┘
> │
> ▼
> Integrated SONAR v1 framework
> (matriz 4-way + overlays)
> │
> ▼
> Editorial pipeline + decisions
> (columns, fund strategy, alerts)

### 1.8 Roadmap do manual
Este manual tem seis Partes seguindo a metodologia estabelecida:

- **Parte I — Fundações (Caps 1-3):** este capítulo de setup, depois cost of capital cross-border theory, depois moeda funcional e ajustamentos inflação-câmbio.

- **Parte II — Yield curves (Caps 4-6):** Nelson-Siegel-Svensson methodology, data sources per country, outputs operacionais (spot/forward/zero/real).

- **Parte III — ERP diária (Caps 7-9):** implied ERP theory (Gordon, DCF, earnings yield approaches), implementation technical, validation contra Damodaran monthly e historical.

- **Parte IV — Country Risk Premium (Caps 10-12):** CDS-based approach, sovereign spread approach, volatility ratio synthesis, 30+ country operational output.

- **Parte V — Rating mapping + Inflação esperada (Caps 13-17):** rating agency landscape, spread mapping methodology, operational table, breakeven inflation, inflation swaps, cross-country expected inflation.

- **Parte VI — Integração e aplicação (Caps 18-20):** SONAR architecture integrated, use cases practical, caveats honestos e bibliografia anotada.

> *Este é o quinto manual SONAR — o primeiro não-cycle. Após ele, a arquitetura v1 terá documentação para os quatro ciclos + os cinco sub-modelos, totalizando framework de nine modules integrated.*

## Capítulo 2 · Cost of capital cross-border — do CAPM ao framework integrado
### 2.1 O CAPM clássico — e porque é insuficiente
O Capital Asset Pricing Model (Sharpe 1964, Lintner 1965) estabelece o framework básico para cost of equity:

*E(R_i) = R_f + β_i × (E(R_m) − R_f)*

Onde R_f é risk-free rate, β_i é beta do ativo ao mercado, e (E(R_m) − R_f) é Equity Risk Premium. Simples, elegante, amplamente ensinado.

**Limitações quando aplicado cross-border**

- **Limitação 1 — Qual mercado?** CAPM assume mercado único. Mas global capital é integrado — um investidor PT investe globalmente. Qual β usar? Qual ERP usar? Local, regional, global?

- **Limitação 2 — Qual R_f?** R_f deveria ser ativo sem risco default. Mas PT 10Y não é sem risco default. Bund 10Y sim (approximately). Qual usar para ativo PT? Framework precisa resolver.

- **Limitação 3 — Country risk ignorado.** Dois ativos idênticos em países diferentes têm risk distinto. CAPM padrão não captura isso. Requires CRP overlay.

- **Limitação 4 — Moeda funcional.** Ativo Turkey modelado em lira tem cost of capital dominado por inflação esperada Turkey. Modelado em USD, parte desse componente desaparece (absorvido no câmbio esperado). CAPM não trata explicitamente.

### 2.2 Framework expandido — Damodaran e sucessores
Aswath Damodaran popularizou framework extended para cross-border:

*Cost of Equity = R_f(mature) + β × ERP(mature) + CRP(country)*

Onde:

- R_f(mature): risk-free rate do mercado mature onde o investor is based (typically US Treasury ou German Bund)

- ERP(mature): equity risk premium do mercado mature (tipicamente US)

- CRP(country): country risk premium additional para o país do ativo

**Why this extension works**

- Separa risk-free component (global, fungible) de country component

- CRP absorves o incremental risk de investir em país non-mature

- Conceptually clean: CRP = 0 para mature markets (US, Germany, Japan, UK, etc.)

- CRP \> 0 para EMs e DM periphery

**Remaining issues**

- Beta scaling question — some investors scale CRP by β (more risk-averse sectors higher), others apply flat

- Currency question — does framework apply to local currency cost of equity or USD-translated?

- Both approaches defendable; SONAR adopts flat application unless explicit scaling requested

### 2.3 Moeda funcional e Fisher equation
Fisher equation (Irving Fisher 1930):

*(1 + i_nominal) = (1 + r_real) × (1 + π_expected)*

Aproximadamente:

*i_nominal ≈ r_real + π_expected*

**Cross-border implication**

Dois analistas modelando Turkish equity:

- Analista A modela em USD: cost of equity USD ~= 9% (US risk-free + ERP + CRP Turkey)

- Analista B modela em TRY: cost of equity TRY = cost of equity USD + expected TRY depreciation

- Se expected TRY depreciation = 15% annually (inflation differential), cost of equity TRY ~= 24%

- Both são correct — but must be consistent with cash flows modeling currency

> *The fatal mistake is mixing currencies: using USD cost of capital with TRY cash flows, or vice versa. Essential that currency of discount rate matches currency of cash flows.*

**When moeda funcional matters most**

- Emerging markets com high inflation (Turkey, Argentina historicamente)

- Countries outside major currency blocs (USD, EUR, JPY, GBP)

- Long-horizon DCFs where inflation differential accumulates

- Real estate especially (tends to be modeled in local currency with inflation)

### 2.4 Real vs nominal — segunda dimensão
Além de currency, há também a escolha real vs nominal:

**Real approach**

- Cash flows em real terms (deflated by expected inflation)

- Discount rate em real terms (nominal - expected inflation)

- Useful para long-term planning, strategic analysis

- Avoids inflation distortion cross-period

**Nominal approach**

- Cash flows em nominal terms (as reported)

- Discount rate em nominal terms (as observed)

- Standard para financial markets analysis

- Matches accounting conventions

**Hybrid / inflation-linked approach**

- Cash flows grown by CPI explicitly

- Discount at real rate

- Rigorously tracks inflation pass-through

- Useful para real estate, commodities, utilities

### 2.5 Os cinco sub-modelos ligados ao cost of capital
Cada um dos cinco sub-modelos preenche uma peça no puzzle de cost of capital cross-border:

| **Sub-modelo**        | **Componente do cost of capital**               |
|-----------------------|-------------------------------------------------|
| Yield curves          | R_f por país + term structure                   |
| ERP diária            | E(R_m) - R_f para mercados matured              |
| Country Risk Premium  | CRP para ajustar non-mature markets             |
| Rating-spread mapping | Default spread quando CDS não disponível        |
| Expected inflation    | Converte nominal ↔ real, ajusta moeda funcional |

**Framework completo**

> Cost of equity (nominal local currency) =
> R_f(local) + β × ERP(mature) + CRP(country)
> where:
> R_f(local) = yield curve output at relevant tenor
> ERP(mature) = SONAR implied ERP output (US or EU mature)
> CRP(country) = SONAR CRP output for country
> β = asset-specific beta (supplied externally)
> Cost of equity (real local) =
> Cost of equity (nominal) - Expected inflation (local)
> Cost of equity (foreign currency, e.g. USD) =
> Cost of equity (local nominal) - Expected FX depreciation
> where Expected FX depreciation ≈
> Expected inflation differential (local - foreign)

### 2.6 Why daily frequency matters
Damodaran updates monthly. Bloomberg shows real-time but disaggregated. Why does SONAR insist on daily computed integrated output?

**Market timing value**

- ERP compressions signal late-cycle risk

- Monthly data misses 20+ trading days of signal

- Short-term ERP changes of 50-100bps routine

- Missing them = missing alpha

**Event response**

- Elections, policy shifts, earnings surprises move ERP

- Mass monthly update misses response window

- Daily ERP tracks real-time regime changes

**Editorial timing**

- "ERP atingiu mínimo em 3 anos após Fed dovish turn" — needs daily

- "CRP Portugal caiu 20bps intraweek após S&P upgrade" — needs daily

- Monthly publication misses editorial opportunities

**Trading operational**

- Options pricing uses implicit risk premia

- Mergers and acquisitions DCF needs current cost of capital

- Monthly data is insufficient for transactional work

### 2.7 Validation framework
Como garantimos que SONAR sub-modelos produzem outputs corretos?

**Cross-validation with industry sources**

- ERP daily deve aproximar Damodaran monthly (within reasonable error)

- CRP deve aproximar Bloomberg sovereign CDS spreads

- Yield curves deve aproximar Bloomberg curves (mature markets)

- Rating-to-spread should calibrate to Moody's historical defaults

- Expected inflation should be consistent with market-implied breakevens

**Historical backtest**

- Apply framework historical (2000-2025)

- Test whether outputs match known historical events

- 2008 crisis: ERP spike, CRP widening expected

- 2022 inflation shock: nominal rates up, real rates modest

**Internal consistency**

- Fisher equation should hold approximately

- Cross-country rates should be arbitrage-free (adjusting for currency)

- Rating-to-spread should have reasonable curvature

### 2.8 Output delivery principles
**Principle 1 — Transparent methodology**

Every output traceable to inputs. Calculation logic documented. Users can replicate. Distinguishes SONAR from black-box commercial alternatives.

**Principle 2 — Daily update**

All five outputs refresh daily (where data permits). Weekly/monthly updates for inputs that don't have daily data (Shiller monthly, SPF quarterly).

**Principle 3 — Confidence intervals**

Outputs produced with confidence intervals reflecting data quality. ERP US may be high confidence, CRP Zimbabwe necessarily wide.

**Principle 4 — Version consistency**

Methodology changes versioned. Historical backtests recomputed. Users know which methodology generated which output date.

> *Transparency é o asset competitivo real. Bloomberg entrega números; SONAR entrega números + methodology + reproducibility. Diferença material para editorial e institutional use.*

## Capítulo 3 · Moeda funcional e ajustamentos inflação-câmbio
### 3.1 O que é moeda funcional
Accounting standards (IAS 21, ASC 830) definem moeda funcional como "currency of the primary economic environment in which the entity operates" — a moeda predominantemente usada por uma entidade nas suas operações principais.

Para SONAR purposes, moeda funcional é a moeda em que cash flows são efectivamente gerados. Isto tem implicações diretas no cost of capital.

**Examples**

- **EDP (Portuguese utility):** functional currency EUR (most revenues EUR, some BRL from Brazil)

- **Galp Energia:** mixed — USD for oil, EUR for downstream retail; consolidated functional EUR

- **Jerónimo Martins:** mixed EUR (Portugal) + PLN (Poland, Biedronka major); consolidated EUR

- **Apple:** USD globally (~40% revenues US, most pricing in USD)

- **Petrobras:** USD (oil priced USD) despite Brazilian ops and BRL reporting

### 3.2 Por que moeda funcional importa para SONAR
**Cost of capital mismatch problem**

Investor USD discounting EUR cash flows (de EDP, p.e.) with USD cost of capital produces wrong answer. Two valid approaches:

3.  Discount EUR cash flows with EUR cost of capital, then translate to USD at spot (correct)

4.  Translate EUR cash flows to USD using expected FX path, then discount with USD cost of capital (also correct if FX path is right)

The wrong approach: translate at spot only, discount with mismatched cost of capital. This is widespread in unsophisticated DCFs.

> *Inflation differentials drive FX expectations long-term. If currency is expected to depreciate 3%/year due to inflation differential, that 3% must appear somewhere — in cash flow growth rate, in discount rate, or in FX forward. Omission creates silent modeling error.*

**SONAR approach**

SONAR outputs should permit both modeling approaches:

- Output cost of capital IN each relevant currency

- Output expected inflation IN each relevant currency

- Output yield curves IN each relevant currency

- Let analyst choose modeling approach

- But ensure consistency — same country's components must not be mixed from different methodologies

### 3.3 Expected inflation — por que essencial
Inflação esperada é input crítico para:

**Uso 1 — Real vs nominal conversion**

*real rate = nominal rate − expected inflation*

Converter yield curve nominal para real requires expected inflation. Essential when comparing real returns cross-country.

**Uso 2 — Long-term cash flow growth**

Em DCF com horizontes 10+ anos, cash flow growth deve incluir inflation. Terminal value especially sensitive to long-run inflation assumption.

**Uso 3 — Currency forward expectation**

Expected FX depreciation aproximate inflation differential (purchasing power parity long-run):

*E\[Δ FX\] ≈ π_expected(local) − π_expected(foreign)*

**Uso 4 — Monetary policy expectation**

Central bank reactions forecast benefits from expected inflation — a rising expected inflation increases probability of rate hikes.

**Uso 5 — Inflation-linked products pricing**

TIPS, inflation swaps, RPI-linked bonds — all require expected inflation input.

### 3.4 Measuring expected inflation — three approaches
**Approach A — Market-based (breakeven)**

Breakeven inflation = nominal yield − real (TIPS) yield.

- **Direct observation:** market's implicit expected inflation

- **Advantages:** market-tested, real-time, forward-looking

- **Disadvantages:** contains inflation risk premium, liquidity distortions, institutional hedging demand

- **Available:** US (TIPS), UK (ILGs), EA (some countries), Japan (small market)

**Approach B — Survey-based**

SPF (Survey of Professional Forecasters in US), ECB SPF, BoE survey, University of Michigan consumer expectations.

- **Direct observation:** what actual forecasters expect

- **Advantages:** free of market distortions, longer horizons available, cross-country comparable

- **Disadvantages:** lagged (quarterly typically), may anchor on past

- **Available:** US, EA, UK, Japan, Canada, Australia, some EMs via OECD

**Approach C — Model-based**

Extract expected inflation from VAR or structural models.

- **Direct observation:** none — computed from observables

- **Advantages:** can be applied anywhere, theoretically grounded

- **Disadvantages:** model-dependent, requires calibration

**SONAR approach — hybrid A+B**

Use market breakevens where available and liquid. Complement with surveys where market data absent. For EMs, rely on surveys (OECD, IMF WEO) + IMF inflation projections.

### 3.5 Portugal specifically — inflation expectation challenges
Portugal não tem sovereign TIPS-like mercado líquido. ECB breakevens cobrem EA aggregate but not PT specifically. How does SONAR handle?

**Building PT expected inflation**

- Start with EA aggregate breakeven (ECB SPF 5-year-ahead)

- Adjust with PT historical inflation differential (average last 5 years)

- Cross-check with Banco de Portugal projections

- Cross-check with INE current CPI trend

- Generate 1Y, 5Y, 10Y expected inflation for PT

**Uncertainty tracking**

- Mark PT expected inflation with wider confidence intervals

- Note that PT data is derived (not directly observed)

- Adjust when EA-wide breakeven diverge significantly

### 3.6 Expected inflation as function of time
Expected inflation is not single number — it's term structure. Markets distinguish:

- 1-year-ahead inflation expectation (short-term, sensitive to current CPI momentum)

- 5-year-ahead inflation expectation (medium-term, trend-sensitive)

- 5y5y forward inflation expectation (long-term, anchoring assessment)

- 10-year-ahead inflation expectation (long-term)

**5y5y forward — the critical indicator**

BCs watch 5y5y forward inflation expectation. It measures market's inflation expectation between 5 and 10 years out — long enough to be largely inflation anchor, short enough to be market-based.

- **5y5y anchored near target:** credibility intact

- **5y5y drifting above target:** credibility erosion signal

- **5y5y drifting below target:** deflation risk signal (Japan-like)

> **Nota** *Daily 5y5y computation via inflation swaps is critical output for BC credibility assessment. SONAR computes this from observed swap curves and publishes daily.*

### 3.7 FX expectations — the PPP benchmark
Purchasing Power Parity (PPP) suggests exchange rates adjust to eliminate international price differences. Long-run relationship; frequent deviations short-run.

*E\[FX\_{t+n}\] = FX_t × (1 + π_local)^n / (1 + π_foreign)^n*

Or approximately:

*Expected FX depreciation rate ≈ π_local − π_foreign*

**When this works**

- Long horizons (5+ years)

- Freely floating currencies

- No capital controls

- Stable relative productivity growth

**When this fails**

- Short-term (speculative flows dominate)

- Managed/pegged currencies

- Commodity exporters (terms of trade dominates)

- Crisis periods (flight to quality)

**SONAR implementation**

- Compute implied FX path from inflation differentials for each currency pair

- Flag when spot FX diverges significantly from PPP implied

- Useful for long-horizon cross-border valuation

- Not useful for short-term trading FX

### 3.8 Operational consequences for sub-models
**Yield curves**

Each country's nominal curve + expected inflation = real curve. SONAR publishes both. Users choose based on application.

**ERP**

ERP is fundamentally real or nominal? SONAR computes nominal ERP for matured markets. Real ERP derivable by subtracting real vs nominal discount in the same period.

**CRP**

CRP is primarily default/credit risk, not inflation. Hence CRP is largely invariant to nominal/real distinction (except to the extent that default risk and inflation both stem from fiscal policy issues).

**Rating-spread mapping**

Rating-spread is currency-invariant (spreads in bps over risk-free, same in USD or EUR terms approximately). Minor adjustments for depth of market but negligible.

**Expected inflation**

Directly this sub-model — and the one that enables all currency and real-terms conversions.

### 3.9 Documentation standard
Cada output SONAR inclui:

- Value

- Currency / numeraire

- Real vs nominal flag

- Tenor (when applicable)

- Computation date

- Methodology version

- Confidence indicator

> {
> "output_id": "ERP_SP500_IMPLIED",
> "date": "2026-04-17",
> "value_pct": 4.82,
> "currency": "USD",
> "nominal_or_real": "nominal",
> "tenor_years": null, // ERP is not tenor-specific
> "methodology_version": "v1.2",
> "confidence": 0.85,
> "inputs_used": \[
> "sp500_level", "analyst_eps_estimates",
> "dividend_yield", "buyback_yield", "risk_free_10y"
> \]
> }
>
> *Documentation rigor is the scholarly standard that distinguishes research-grade from hack outputs. SONAR maintains this standard because editorial authority depends on it.*

**Encerramento da Parte I**

Parte I estabeleceu as fundações para os cinco sub-modelos quantitativos SONAR:

- **Capítulo 1 — Os cinco outputs complementares.** Definição explícita dos cinco sub-modelos (yield curves, ERP diária, CRP, rating-spread mapping, expected inflation). Clarificação de que SONAR não é plataforma de indicadores ao estilo Trading Economics, mas motor analítico com dois pilares (cycle classification + derived outputs). Como os cinco compõem para cost of capital cross-border. Uso standalone fora dos ciclos. Posicionamento vs Bloomberg, Damodaran, Refinitiv.

- **Capítulo 2 — Cost of capital cross-border.** CAPM clássico e suas quatro limitações para cross-border. Framework Damodaran extended (R_f mature + β × ERP mature + CRP country). Fisher equation e por que moeda funcional é critical. Real vs nominal distinção. Como os cinco sub-modelos se encaixam no framework de cost of capital. Por que daily frequency matters. Validation framework via cross-source. Output delivery principles (transparent methodology, daily update, confidence intervals, version consistency).

- **Capítulo 3 — Moeda funcional e ajustamentos inflação-câmbio.** Definição de moeda funcional com exemplos portugueses (EDP, Galp, Jerónimo Martins). Cost of capital mismatch problem. Expected inflation como input crítico para cinco usos distintos. Three approaches to measuring expected inflation (market-based breakevens, survey-based SPF, model-based). Portugal specifically — como SONAR constrói expected inflation PT sem TIPS-like mercado líquido. Term structure de expected inflation (1Y, 5Y, 5y5y forward, 10Y). FX expectations via PPP. Documentation standard para outputs.

**O que a Parte I estabeleceu**

5.  SONAR tem arquitetura bi-pilar: cycles + sub-models

6.  Cinco sub-models identificados com razão de ser individual

7.  Cost of capital cross-border é o framework integrador

8.  Moeda funcional determina consistent modeling approach

9.  Daily frequency é valor competitivo real

10. Documentation standard rigoroso é non-negotiable

**Material editorial potencial da Parte I**

11. "Cost of capital Portugal — o que Damodaran's ERP + CRP nos dizem em 2026."

12. "O CAPM está morto? O framework cross-border de Damodaran e porque importa para investidores PT."

13. "Moeda funcional — o erro silencioso na maioria das valuations portuguesas cross-border."

14. "Fisher equation em 2026 — o que real rates nos dizem sobre mercado de bonds."

15. "PPP forecasting — porque euro deveria apreciar contra dólar a long-run."

***A Parte II — Yield curves por país (capítulos 4-6)** aborda a construção dos yield curves soberanos: Cap 4 a metodologia Nelson-Siegel-Svensson com decomposition em level/slope/curvature, Cap 5 as fontes de dados por país (US Treasury, Bund, JGB, Gilts, PT sovereign), Cap 6 os outputs operacionais (spot curves, forward curves, zero curves, real vs nominal, tenor standard 3M-30Y).*

# PARTE II
**Yield curves por país**

*Nelson-Siegel-Svensson, fontes per country, outputs operacionais*

**Capítulos nesta parte**

**Cap. 4 ·** Metodologia de construção de yield curves

**Cap. 5 ·** Fontes de dados e implementation per country

**Cap. 6 ·** Outputs operacionais — spot, forward, zero, real


---

# PARTE VI · Integração e aplicação

## Capítulo 18 · Arquitetura SONAR completa — ciclos e sub-models unificados
### 18.1 A arquitetura v1 consolidada
Cinco manuais depois, SONAR v1 está arquiteturalmente completo. Quatro ciclos (económico, crédito, monetário, financeiro) classificam macro state em tempo real. Cinco sub-modelos (yield curves, ERP, CRP, rating-to-spread, expected inflation) produzem outputs quantitativos operacionais. Matriz 4-way + diagnostics aplicados integram os ciclos. Framework cost-of-capital cross-border integra os sub-models. Este capítulo mostra como tudo se conjuga.

> *SONAR não é plataforma de indicadores. É motor analítico onde cycle classification informa valuation inputs, e valuation inputs informam cycle classification. Circular mas intencional — economia moderna funciona assim.*

### 18.2 Data flow — a hierarquia completa
> SONAR v1 — Data flow hierarchy
> LAYER 0 — Raw data sources
> ├── FRED (US data, extended global)
> ├── ECB SDW (EA data)
> ├── BIS (global sovereign, credit, property)
> ├── Eurostat (EA + EU non-euro)
> ├── OECD SDMX
> ├── BPStat / INE (Portugal specific)
> ├── Shiller data (CAPE)
> ├── Glassnode / Coinglass (crypto)
> ├── CFTC COT (positioning)
> ├── FactSet / IBES (earnings estimates)
> ├── S&P DJI (buybacks)
> ├── Moody's / S&P / Fitch / DBRS (ratings)
> ├── CDS sources (WGB, Bloomberg)
> ├── IGCP (Portuguese sovereign)
> ├── Central banks (Fed, ECB, BoE, BoJ, SNB, RBA, BoC)
> └── Trading Economics (catch-all)
> LAYER 1 — Sub-models (this manual)
> ├── Yield curves per country (15+ countries)
> ├── ERP diária (US, EA, UK, JP)
> ├── Country Risk Premium (30+ countries)
> ├── Rating-to-spread mapping
> └── Expected inflation term structure
> LAYER 2 — Cycle classification (four previous manuals)
> ├── ECS (Economic Cycle Score) + Stagflation overlay
> ├── CCCS (Credit Cycle Score) + Boom overlay
> ├── MSC (Monetary Stance Composite) + Dilemma overlay
> └── FCS (Financial Cycle Score) + Bubble Warning overlay
> LAYER 3 — Integration
> ├── Matriz 4-way (six canonical patterns, five critical configs)
> ├── Lead-lag relationships
> ├── Four applied diagnostics (bubble, risk appetite, real estate, Minsky)
> └── Cross-cycle forecast
> LAYER 4 — Applications
> ├── Cross-border valuation (DCF with SONAR inputs)
> ├── Portfolio construction (playbooks by cycle state)
> ├── Editorial pipeline (22+ angles catalogued)
> ├── Alert system (threshold breaches, regime shifts)
> └── Fund strategy (A Equação / 7365 Capital)

### 18.3 Feedback loops intencionais
O framework não é puramente hierarchical — há feedbacks by design:

**Feedback 1 — Yield curve ↔ MSC**

- Yield curve slope é key input para MSC stance

- MSC classification informa interpretation de curve shape

- Exemplo: curve inversion pode ser "tight monetary" ou "recession imminent" — cycle framework helps disambiguate

**Feedback 2 — ERP ↔ FCS**

- ERP é F1 valuation input para FCS

- FCS Euphoria informs whether ERP compression é late-cycle warning ou secular shift

- Combination ERP compressed + FCS Euphoria = red flag (documented historically)

**Feedback 3 — CRP ↔ CCCS periphery**

- CRP for EA periphery reflects credit cycle dynamics

- Periphery CCCS Boom/Contraction moves CRP historically

- Portugal 2011-2014: CCCS Contraction → CRP 1500bps; CCCS Recovery → CRP 54bps

**Feedback 4 — Expected inflation ↔ MSC**

- Expected inflation informs BC reaction function (MSC)

- MSC stance affects inflation expectations via credibility

- Well-anchored 5y5y = MSC framework credible

- Drifting 5y5y = MSC credibility erosion

**Feedback 5 — Rating ↔ CCCS sovereign**

- Sovereign rating changes affect CCCS periphery

- Debt dynamics under CCCS Contraction drives ratings down

- Portugal 2011-12 illustrative

### 18.4 Unified database schema
SONAR v1 schema finaliza em v17 (incluindo os sub-models). Core tables:

> -- CORE TABLES (exemplo simplificado)
> -- Sub-model outputs
> CREATE TABLE yield_curves (
> country_code, date, curve_type, methodology,
> nss_params JSON, fitted_yields JSON, confidence
> );
> CREATE TABLE erp_daily (
> country_code, date,
> erp_dcf_pct, erp_gordon_pct, erp_simple_pct, erp_cape_pct,
> canonical_erp_pct, confidence, inputs_json
> );
> CREATE TABLE country_risk_premium (
> country_code, date, default_spread_bps, vol_ratio,
> crp_bps, crp_range_bps, source, confidence
> );
> CREATE TABLE rating_spread_mapping (
> sonar_notch, rating_equivalent,
> spread_central_bps, spread_range_bps, calibration_date
> );
> CREATE TABLE expected_inflation (
> country_code, date, tenor_years,
> value_pct, confidence_interval_json, source, methodology_version
> );
> -- Cycle outputs (already covered in prior schemas)
> -- ecs_score, cccs_score, msc_score, fcs_score
> -- + overlay flags (stagflation, boom, dilemma, bubble_warning)
> -- + matriz_4way_pattern
> -- Integration
> CREATE TABLE sonar_integrated_state (
> country_code, date,
> ecs_score, cccs_score, msc_score, fcs_score,
> canonical_pattern TEXT,
> active_overlays JSON,
> alert_level TEXT,
> yield_curve_level, yield_curve_slope, yield_curve_curvature,
> erp_current_pct, crp_current_bps,
> expected_inflation_10y_pct,
> confidence REAL,
> updated_at TIMESTAMP
> );
> CREATE INDEX idx_integrated_country_date ON sonar_integrated_state(country_code, date);

### 18.5 API unified interface
SONAR v1 API endpoints consolidados:

**Cycle endpoints**

- GET \`/sonar/cycles/{country}/latest\` → all four cycle scores + overlays

- GET \`/sonar/cycles/{country}/matrix\` → 4-way matrix position + pattern

- GET \`/sonar/cycles/{country}/history?from&to\` → time series

- GET \`/sonar/cycles/diagnostics/{country}/{date}\` → four applied diagnostics

**Sub-model endpoints**

- GET \`/sonar/yc/{country}/latest\` → yield curves (nominal, zero, forward, real)

- GET \`/sonar/erp/{market}/latest\` → ERP all methods

- GET \`/sonar/crp/{country}/latest\` → CRP + components

- GET \`/sonar/rating/{country}/latest\` → ratings + implied spread

- GET \`/sonar/inflation/{country}/latest\` → expected inflation term structure

**Integrated endpoints**

- GET \`/sonar/integrated/{country}/latest\` → all outputs combined

- GET \`/sonar/cost_of_capital/{country}?beta={x}\` → cost of equity computed

- GET \`/sonar/alerts/active\` → current alerts all countries

- GET \`/sonar/edit_angles/available\` → editorial angles ready for development

**Cross-cutting endpoints**

- GET \`/sonar/compare/{countries}/{metric}\` → cross-country comparison

- GET \`/sonar/backtest/{scenario}\` → historical backtesting

- GET \`/sonar/forecast/{country}/{horizon}\` → predictive output

### 18.6 Data pipeline orchestration
SONAR v1 daily pipeline orchestration:

> SONAR Daily Pipeline (Lisbon timezone)
> 06:00 — Crypto on-chain refresh (Glassnode, Coinglass)
> → feeds FCS F3 (risk appetite), F4 (positioning)
> 07:00 — FRED sync (US data)
> → feeds ECS E1-E4, CCCS, MSC (US), FCS F1 (valuations)
> 07:15 — ECB SDW sync (EA data)
> → feeds EA cycles + EA sovereign curves
> 07:30 — BIS sync (credit, property gaps)
> → feeds FCS Bubble Warning + CCCS
> 08:00 — Shiller CAPE update (if month-start)
> → feeds FCS F1 valuations
> 08:30 — Damodaran ERP update (if month-start) for cross-check
> → validates SONAR ERP daily computation
> 09:00 — YIELD CURVE computation all countries
> → produces sub-model output \#1
> 09:15 — ERP daily computation all markets
> → produces sub-model output \#2
> 09:30 — CRP computation all countries
> → produces sub-model output \#3
> 09:45 — Rating-to-spread table application
> → produces sub-model output \#4
> 10:00 — Expected inflation computation all countries
> → produces sub-model output \#5
> 10:15 — CYCLE SCORES recomputation
> → ECS, CCCS, MSC, FCS
> 10:30 — OVERLAYS evaluation
> → Stagflation, Boom, Dilemma, Bubble Warning
> 10:45 — MATRIZ 4-WAY classification + canonical pattern
> → integrated state
> 11:00 — FOUR DIAGNOSTICS computation
> → bubble detection, risk appetite, real estate, Minsky
> 11:15 — ALERTS evaluation
> → threshold breaches, regime shifts, transitions
> 11:30 — PUBLISHING to API
> → integrated state available
> 12:00 — POST-publishing: editorial angle generation
> → review which angles triggered by today's data
> Events during day:
> - Cental bank announcements trigger MSC re-evaluation
> - Rating actions trigger Rating + CRP + CCCS updates
> - Major market moves trigger FCS + ERP intraday refresh

### 18.7 Consumers de SONAR outputs
Quem consome e como:

**Consumidor 1 — Editorial pipeline (A Equação)**

- Daily cycle snapshot for weekly column

- 22+ angle templates auto-triggered by data

- Charts auto-generated from integrated_state

- Editor Hugo writes, SONAR feeds quantitative content

**Consumidor 2 — Cross-border valuation**

- Portuguese analyst valuating foreign equity

- International analyst valuating Portuguese equity

- Input: company-specific β and cash flows

- SONAR output: r_f, ERP, CRP, expected inflation → cost of capital

**Consumidor 3 — Portfolio management**

- Asset allocation signals from playbooks

- Tactical adjustments based on cycle transitions

- Risk management via alert level

- Sector rotation via cycle-specific playbooks

**Consumidor 4 — Academic research**

- Historical backtests

- Cross-country comparisons

- Methodology replication

- Data transparency supports peer review

**Consumidor 5 — Fund (7365 Capital future)**

- Core analytics for discretionary macro fund

- Quarterly letter templates

- Client communication with institutional rigor

- Alpha generation via cross-cycle integration

### 18.8 The v1 achievement
SONAR v1 representa completeness operacional para um escopo bem-definido:

**Escope fechado**

105. Quatro ciclos macro com classification + forecasting

106. Cinco sub-models quantitativos complementares

107. Cobertura 15+ países (Tier 1-3) + 4 experimental (Tier 4)

108. Daily updates onde datos permitem

109. Documentação completa dos cinco manuais

110. Planos de fontes de dados para four cycles

111. Methodology transparente e version-controlled

**Claims feitos**

- Probabilistic classification de cycle states cross-country

- Transition probability estimation

- Historical precedent matching

- Cross-cycle integration via matriz 4-way

- Cost of capital output per country daily

- Cross-border DCF inputs available

**Claims NÃO feitos**

- Precise timing prediction

- Universally optimal allocation

- Substitute for qualitative judgment

- Immunity from regime changes

- Comprehensive coverage of all countries

- Real-time (intraday) updates for most outputs

### 18.9 Roadmap v2 — what's next
**v2.1 — Dashboard interativo multi-ciclo**

- HTML/React prototype

- Four cycle scores + sub-model outputs visualizados

- Matriz 4-way map visual

- Alerts highlighted

- Historical animation

**v2.2 — Backtesting automation**

- Framework applied historically systematically

- Out-of-sample validation

- Alpha generation documented

- Strategy comparison vs benchmarks

**v2.3 — Alert system operacional**

- Regime shift detection automated

- Threshold breach notifications

- Editorial pipeline integration

- Portfolio impact estimation

**v2.4 — Additional sub-models**

- Sector-level CRP decomposition

- Factor model integration (Fama-French 5-factor)

- Sovereign default probability via structural models

- FX equilibrium models (BEER, FEER)

**v2.5 — EM expansion**

- Frontier market coverage deepening

- Alternative data sources

- Currency regime classification

- Political risk scoring

**v3 — Multi-asset strategy engine**

- Portfolio construction automation

- Risk parity with SONAR signals

- Backtesting at portfolio level

- Transaction cost integration

- Fund deployment ready

> *v1 operacional, v2 em roadmap. O framework evolve mas core contribution — quatro ciclos integrados com cinco sub-models consistentes — é established.*

## Capítulo 19 · Use cases práticos — da valuation à coluna editorial
### 19.1 Dois tipos de use cases
Os use cases SONAR dividem-se em dois grupos complementares:

**Tipo A — Use cases quantitativos**

- Valuation (DCF, multiples adjustment)

- Portfolio construction e asset allocation

- Risk management

- Arbitrage detection

- Hedging decisions

**Tipo B — Use cases editoriais**

- Column framing (A Equação)

- Audience-building via quantitative authority

- Market commentary with rigorous base

- Institutional positioning

- Fund communication ready

Este capítulo trabalha use cases concretos de ambos os tipos.

### 19.2 Use case quantitativo — Portuguese equity valuation (EDP detailed)
EDP - Energias de Portugal é blue chip português, utility integrada, presente em Portugal + Espanha + Brasil + US renewables + UK + Germany.

**Step 1 — Yield curve (risk-free)**

> SONAR yield curve PT April 2026:
> 10Y nominal: 3.15%
> 10Y real (derived): 0.80%
> But EDP functional currency is EUR.
> Risk-free for EUR DCF: Bund 10Y or PT 10Y?
> Damodaran convention: use Bund as mature risk-free,
> add PT CRP separately.
> Risk-free EUR 10Y (SONAR): Bund = 2.45%

**Step 2 — ERP**

> SONAR ERP for EA markets April 2026:
> ERP_DCF (STOXX 600): 5.25%
> ERP_Gordon: 5.40%
> ERP_simple: 4.95%
> Canonical ERP_EA: 5.25%
> For EDP (listed in Euronext Lisbon):
> Use EA ERP as base mature market ERP.

**Step 3 — Country Risk Premium**

> SONAR CRP Portugal April 2026:
> Default spread (CDS 5Y): 35 bps
> Vol ratio (PSI-20 vs PT 10Y): 1.54
> CRP: 54 bps = 0.54%
> But EDP has international operations:
> - Portugal + Spain: 50%
> - Brazil: 20%
> - US/North America: 15%
> - UK + Europe: 15%
> Weighted CRP exposure:
> 0.50 × 0.54% (PT) +
> 0.20 × 3.00% (BR) +
> 0.15 × 0.00% (US mature) +
> 0.15 × 0.20% (UK/EU mixed)
> = 0.27% + 0.60% + 0.00% + 0.03%
> = 0.90%
> Operational CRP for EDP (exposure-weighted): ~90 bps

**Step 4 — Beta**

- EDP beta historical vs STOXX 600: 0.75-0.85

- Regulated utility business → lower beta

- Brazil exposure → partially higher beta

- Use β = 0.80 (external input)

**Step 5 — Cost of equity**

> Cost of Equity EDP:
> = R_f(Bund 10Y) + β × ERP(EA) + CRP(weighted)
> = 2.45% + 0.80 × 5.25% + 0.90%
> = 2.45% + 4.20% + 0.90%
> = 7.55%
> Compare to naive approach (using PT 10Y as risk-free,
> ignoring CRP, flat EA ERP):
> = 3.15% + 0.80 × 5.25%
> = 3.15% + 4.20%
> = 7.35%
> SONAR approach adds 20bps (0.27%) due to proper decomposition.

**Step 6 — Cross-check with inflation**

> Expected inflation EUR 10Y: 2.20% (EA aggregate)
> Real cost of equity EDP:
> = Nominal - Expected inflation
> = 7.55% - 2.20%
> = 5.35% real
> For EDP cash flows modeled in real terms,
> discount at 5.35%. For nominal cash flows, discount at 7.55%.
> Currency: EUR throughout (EDP reports EUR).

**Step 7 — Cost of debt**

> EDP debt yield observations:
> Recent bond issues 5-10Y EUR: 4.0-4.8%
> Credit rating EDP: BBB (S&P)
> Spread vs Bund: ~150-200bps for BBB corporate EUR
> Bund 10Y: 2.45%
> Implied: 2.45% + 175bps = 4.20% cost of debt pre-tax
> Effective tax rate: ~25% Portugal
> After-tax cost of debt: 4.20% × (1-0.25) = 3.15%

**Step 8 — WACC**

> EDP WACC computation:
> Equity value: €15B
> Debt value: €18B (net debt)
> Total enterprise value: €33B
> Equity weight: 45%
> Debt weight: 55%
> WACC = 0.45 × 7.55% + 0.55 × 3.15%
> = 3.40% + 1.73%
> = 5.13%
> For DCF of EDP enterprise value,
> use 5.13% WACC as discount rate.

**Step 9 — Terminal growth assumption**

> Terminal growth assumption:
> - EU long-term GDP growth: 1.0-1.5%
> - EA inflation target: 2.0%
> - Nominal EU growth: 3.0-3.5%
> - EDP's mature geographies → grow with economy
> - Brazil → premium to EU growth
> - Weighted nominal growth: ~3.5%
> Terminal growth = 3.5% (nominal)
> Given WACC 5.13% and g 3.5%, sustainable spread = 1.63%
> (positive — WACC \> g, DCF valid)

**Step 10 — Assembling the DCF**

> EDP DCF 10-year projection + terminal:
> Year 1-5: Analyst forecasts
> Year 6-10: Converge to terminal
> Terminal: CF × (1+g) / (WACC-g)
> Current EDP market cap: €15B
> SONAR DCF fair value: €14.5-16.5B (range)
> Current trade: modest premium to fair value
> Action: Hold or underweight vs benchmark
> (Actual numbers indicative; real DCF requires full model.)
> KEY SONAR VALUE:
> - Each cost of capital input is daily-updated
> - Cross-checked against multiple sub-models
> - Transparent methodology
> - Rigorous treatment of PT vs EA risk-free
> - Proper CRP weighting for international exposure

### 19.3 Use case quantitativo — Brazilian bank cross-border DCF
Investor EUR-based valuing Itaú Unibanco (Brazilian banking behemoth). Currency: BRL domestic; fund EUR. Two approaches possible.

**Approach A — Model in BRL, translate**

> Step 1: Risk-free BRL
> SONAR Brazil yield curve:
> 10Y NTN-F (nominal): 11.85%
> 10Y NTN-B (real): 6.25%
> 10Y expected inflation: 3.85%
> Use 11.85% nominal risk-free BRL.
> Step 2: ERP Brazilian equity
> SONAR EA ERP base: 5.25%
> Plus Brazilian equity-specific:
> Brazilian mature equity market premium ~5.5-6%
> Step 3: CRP Brazil
> SONAR CRP Brazil: 300bps = 3.00%
> Step 4: Beta Itaú
> vs MSCI Brazil: 1.05
> vs regional financial sector: 1.10
> Use 1.05
> Step 5: Cost of equity BRL
> = 11.85% + 1.05 × 5.50% + 3.00%
> = 11.85% + 5.78% + 3.00%
> = 20.63%
> Cost of equity BRL: ~20.6%
> Step 6: Project BRL cash flows
> Use BRL earnings, BRL growth rates
> Step 7: Discount at BRL cost of equity
> Present value BRL
> Step 8: Translate to EUR at spot
> Present value EUR = PV BRL / EUR/BRL spot

**Approach B — Model in EUR directly**

> Step 1: Project BRL cash flows
> (same as Approach A Step 6)
> Step 2: Translate year by year to EUR
> Using PPP-implied forward path:
> Expected BRL depreciation/year = 1.6%
> (from SONAR expected inflation differential)
> Year 1 FX: current × 1.016
> Year 2 FX: current × 1.016²
> ...
> Step 3: EUR cost of capital
> Risk-free EUR (Bund 10Y): 2.45%
> ERP EA: 5.25%
> CRP Brazil: 3.00%
> Beta: 1.05
> k_e EUR = 2.45% + 1.05 × 5.25% + 3.00%
> = 2.45% + 5.51% + 3.00%
> = 10.96%
> Step 4: Discount translated EUR cash flows at 10.96%
> Present value EUR directly
> BOTH APPROACHES SHOULD YIELD IDENTICAL PV
> (if PPP holds over horizon)
> DIFFERENCE FROM NAIVE APPROACH:
> Naive: Discount BRL CFs at EUR cost of capital 7%
> → massive overvaluation (20%+ too high)

**The silent error highlighted**

- Naive DCF: using 7% EUR cost of capital with BRL cash flows

- Ignores 1.6%/year BRL depreciation — embedded 16% over 10 years

- Ignores 3% CRP premium

- Ignores inflation differential

- Result: systematic overvaluation ~30-40% of Brazilian equity

- SONAR framework prevents this

### 19.4 Use case quantitativo — arbitrage detection
**Scenario — Portugal CDS vs rating divergence**

SONAR detecta:

- Portugal CDS 5Y: 35 bps

- Portugal SONAR rating-implied: 90 bps

- Divergence: 55 bps

- Rating vs CDS historical divergence average: 20 bps

- Current divergence: 2.75 std dev from historical

**Interpretation e action**

- Market pricing PT risk much tighter than agencies

- Either: agencies behind curve → upgrade coming

- Or: market too optimistic → CDS may widen

- Historical: agencies typically lag — upgrade more likely

- Action: position for continued CDS tightness ou upgrade

**Alternative scenario — Italy 2011**

- Italy rating was still A at start of crisis

- CDS widened from 100bps to 500bps in weeks

- Rating-implied spread ~60-80 bps

- Divergence: 400+ bps

- Market was ahead of agencies

- Subsequent downgrades to BBB

- Lesson: when divergence reversed, agencies catch up

### 19.5 Use case quantitativo — cycle-informed allocation
**April 2026 SONAR integrated state — Portugal**

> SONAR Integrated State — Portugal — April 2026
> Cycles:
> ECS: 56 (Expansion, mid-cycle)
> CCCS: 51 (Recovery-Boom transition)
> MSC: 48 (ECB Neutral)
> FCS: 61 (Optimism)
> Overlays: none active
> Canonical pattern: Mid Expansion (Pattern 2)
> Sub-models:
> Yield curve 10Y: 3.15% (nominal), 0.80% (real)
> ERP EA: 5.25%
> CRP PT: 54bps
> Expected inflation 10Y: 2.35%
> Rating: A- stable
> Alert level: green
> Playbook implications (from Cap 18 financial manual):
> Equity allocation: moderate overweight Portugal-linked
> Bond allocation: neutral duration
> Defensive sectors: neutral
> Risk-on sectors: slight overweight
> Hedging: minimal
> Cash: moderate

**Cross-cycle tactical signals**

- ECB approaching easing cycle → extend duration Portuguese bonds

- CCCS transitioning to Boom → overweight domestic-focused PT cyclicals

- FCS Optimism mid-cycle → participate but watch for Euphoria transition

- No Bubble Warning → current valuations sustainable

### 19.6 Use case editorial — A Equação column
**Template de coluna — "Portugal 2026 vs 2007"**

Using SONAR integrated state, editor can structure column:

> Column structure — "Portugal 2026 vs 2007"
> Lead:
> "Em 2007, Portugal tinha rating A-/A+, CDS ~15bps,
> spread vs Bund 10bps, CCCS em Boom, FCS em Euphoria late-stage.
> Em 2026, Portugal também tem rating A-, mas com configuração
> muito diferente."
> Data table (from SONAR):
> Metric \| 2007 \| 2026 \| Change
> Rating (S&P) \| A- \| A- \| Same
> CDS 5Y (bps) \| 15 \| 35 \| +20bps
> Bund spread (bps)\| 10 \| 70 \| +60bps
> CCCS \| 85 \| 51 \| Dramatic reduction
> FCS \| 78 \| 61 \| Lower
> Debt/GDP (%) \| 68 \| 102 \| +34pp
> ECS \| 55 \| 56 \| Similar
> CRP (bps) \| 20 \| 54 \| +34bps
> Analysis:
> Same rating, different reality.
> Debt structurally higher, but coming down.
> CCCS no longer Boom — sustainable.
> FCS in Optimism mid-cycle, not Late-Euphoria.
> 2007 was late-cycle pre-crisis — now early-mid cycle.
> Risk profile different.
> Implication:
> Não, não vamos repetir 2008-2014.
> Framework sinaliza sustentabilidade, não exuberância.
> (SONAR evidence \> intuitive pattern matching)
> Editorial voice: rigor + contrarian (against "crisis repeat" narrative)

**Template de coluna — "Os quatro diagnósticos aplicados a 2026"**

> Column structure — "Os quatro diagnósticos aplicados a 2026"
> Lead:
> "Cada uma das quatro lentes do SONAR — bubble detection,
> risk appetite, real estate, Minsky fragility — diz-nos
> algo diferente sobre 2026. Aqui está a leitura de cada uma."
> Section 1 — Bubble Detection
> CAPE 35 (94th percentile historical)
> Buffett indicator elevated
> Damodaran ERP compressed
> Shiller forward return implies ~0-3% real 10Y
> Conclusion: pocket bubble (AI-specific), not systemic
> Section 2 — Risk Appetite Framework
> VIX 15, HY OAS 320bps, compressed
> Regime: Risk-on healthy (R1-R2)
> Institutional positioning: balanced
> Conclusion: healthy but late mid-cycle
> Section 3 — Real Estate Cycle
> US housing: post-correction stable
> EA housing: moderate
> Portugal housing: Lisboa/Porto elevated but outside bubble territory
> Commercial RE: bifurcated (office stressed, data centers euphoric)
> Conclusion: complex bifurcation, not binary
> Section 4 — Minsky Fragility
> Zombie firms ~15% of listed
> Shadow banking growing but contained
> Private credit expanding
> DSR household declining (positive)
> Conclusion: moderate fragility, specific pockets
> Integration:
> Four lenses mostly aligned moderate-risk mid-cycle.
> AI-pocket bubble + CRE bifurcation are specific vulnerabilities.
> Systemic crisis not indicated.
> 2007-type setup: not present.
> 2000-type setup: tech pocket present, not systemic.
> Conclusion:
> Ativo management needed.
> Benchmark allocation inappropriate.
> Quality bias, avoid speculative edges.
> Prepare for late-cycle transition 2027-2028.

### 19.7 Use case editorial — regime shift coluna
SONAR detects regime transitions automatically. Each creates editorial opportunity.

**Exemplo — BCE transições para Accommodative**

> Event: ECB cuts rates from 2.75% to 2.50%, signals further cuts
> SONAR response:
> MSC transitions from Neutral (52) to Accommodative (45)
> Yield curve: steepening
> Expected inflation: anchored at 2.2%
> Bund 10Y: -15bps
> Peripheral spreads: -8bps (PT, -5bps Italy, etc.)
> Editorial trigger:
> "A transição monetária do BCE — o que muda para os nossos ativos"
> Content:
> Historical precedents (4 previous EA easing cycles)
> Playbook: equity overweight, duration extend, HY credit attractive
> Portugal specifically: mortgage relief for Euribor-indexed holders
> Sectors: REITs, utilities benefit; banks neutral
> Currency: EUR weakness typical
> Length: 800-1200 words
> Charts: 2-3 from SONAR
> Tone: rigorous, actionable

**Exemplo — rating upgrade Moody's Portugal**

> Event: Moody's upgrades Portugal from A3 to A2
> SONAR response:
> SONAR notch: 15 → 16
> Rating-implied spread: 90bps → 65bps
> CRP unchanged immediately (CDS 35bps)
> Divergence reduced (55bps → 30bps)
> Alert: rating convergence event
> Editorial trigger:
> "Portugal A2 — o que a subida da Moody's significa operacionalmente"
> Content:
> Historical trajectory (tabulated journey)
> Implications for cost of capital (~25bps reduction implied)
> Impact on debt servicing
> Which sectors benefit most
> Next rating catalyst watch
> Value:
> Transformation of news into quantitative analysis
> Positions author as primary source vs secondary
> Builds audience among institutional

### 19.8 Use case editorial — cross-country comparison columns
SONAR cross-country enables rigorous comparisons.

**Template — "PT vs IT vs ES — as três periferias em 2026"**

> Column structure
> Thesis: "Periferias divergiram dramaticamente post-2012.
> SONAR mostra as diferenças."
> Data table:
> Metric \| PT \| IT \| ES
> Rating S&P \| A- \| BBB \| A
> CDS 5Y \| 35 \| 68 \| 42
> Spread Bund \| 70 \| 140 \| 73
> CRP \| 54 \| 100 \| 61
> ECS \| 56 \| 52 \| 62
> CCCS \| 51 \| 55 \| 58
> FCS \| 61 \| 58 \| 64
> Debt/GDP \| 102% \| 140% \| 105%
> Rating trajectory\| ↑ \| → \| →
> 10Y nominal \| 3.15% \| 3.85% \| 3.18%
> Analysis:
> Italy worst positioned (highest debt, mid-pack ratings,
> biggest spread)
> Portugal improved most dramatically post-Troika
> Spain steady, similar to PT
> Greece separate story (lower notch)
> Equity implications:
> PT equity: quality, favorable cycle
> IT equity: higher risk premium, selective value
> ES equity: similar PT, more liquid
> Bond implications:
> Portugal bonds: best sovereign value
> Italy bonds: higher yield but higher risk
> Spain bonds: similar PT with lower credit risk
> Editorial angle: "Portugal's Silent Victory" or
> "Italy's Structural Challenge"

### 19.9 Use case — fund communications
When 7365 Capital launches fund, quarterly letters reference SONAR framework.

**Template — quarterly letter SONAR-framed**

> Letter structure:
> I. Macro thesis (SONAR-derived)
> "Our SONAR framework classified markets in Q1 2026 as
> \[specific pattern\]. We interpret this as \[implication\]."
> II. Current positioning rationale
> "Given SONAR integrated state:
> - ECS at 56 (Mid-cycle)
> - FCS at 61 (Optimism, not Euphoria)
> - CCCS Recovery-Boom transition
> - No overlays active
> Our positioning reflects \[allocation\]."
> III. Changes this quarter
> "From Q4 2025 to Q1 2026:
> - FCS rose from 57 to 61
> - MSC eased from 52 to 48
> - Expected inflation 10Y declined from 2.45% to 2.35%
> These shifted our \[adjustments\]."
> IV. Forward-looking
> "Key monitoring points Q2 2026:
> - FCS transition to Euphoria (threshold 75)
> - Rate cut expectations
> - CCCS Boom threshold (70)
> - BC communication signals"
> V. Honest acknowledgment
> "SONAR framework has limitations.
> Our positioning reflects our interpretation of data,
> not certainty about outcomes."
> Professional tone throughout.

## Capítulo 20 · Caveats transversais e bibliografia anotada
### 20.1 Caveats cross-cutting em todos os sub-models
**Caveat universal 1 — Model risk**

- Cada sub-model é model-based estimate

- Models assume functional forms that may not hold

- NSS assumes level-slope-curvature sufficient

- DCF assumes growth stabilizes at risk-free rate perpetually

- Reality more complex than any model

**Caveat universal 2 — Regime change risk**

- Calibrations based on historical regimes

- Structural breaks invalidate past relationships

- Post-2008 low-rate regime different

- Post-2022 inflation regime different

- Post-AI regime possibly different

- Rolling calibrations adapt gradually, miss discontinuous shifts

**Caveat universal 3 — Data quality gradient**

- US / Germany / UK: excellent data

- EA periphery / major EM: good data

- Smaller EM: limited depth

- Frontier markets: spotty

- Confidence intervals reflect this gradient

**Caveat universal 4 — Circular dependencies**

- ERP feeds FCS; FCS informs interpretation of ERP

- Expected inflation feeds MSC; MSC affects inflation

- Sub-models feed cycle scores; cycle scores inform sub-model context

- Not problematic, but non-independence

**Caveat universal 5 — Institutional constraints**

- Some outputs depend on BC behavior (yield curves shaped by policy)

- Rating agencies subject to criticism

- Market data subject to manipulation historically

- Framework inherits these institutional limitations

### 20.2 Sub-model-specific caveats revisited
**Yield curves**

- NSS fits fail on non-standard shapes

- Illiquid tenors extrapolated

- Real yields for Portugal derived (not observed)

- EM curves less reliable

**ERP**

- Analyst estimate bias persistent

- Buyback forecasts uncertain

- Terminal growth assumption judgmental

- Multiple methods can diverge 100+ bps

**CRP**

- Vol ratio computation noisy

- Country-specific risks (tail) underestimated

- CDS liquidity varies

- Basis bond-CDS persistent

**Rating-to-spread**

- Agencies criticized for lagging

- Market spreads can diverge substantially

- Historical default rates average over cycles

- Current spreads reflect regime

**Expected inflation**

- Breakevens contain risk premium

- Surveys backward-looking

- 5y5y forward is derived, not observed

- Portugal expected inflation synthesized (not direct)

### 20.3 Methodology evolution — transparency
**Principle — open book methodology**

SONAR's competitive advantage is transparency, not secrecy. Every computation documented. Users replicate. Errors identifiable.

**Version control commitment**

- Every methodology change versioned

- Historical data backfilled with current methodology

- Users can request specific version backfill

- Changelog maintained publicly

- Major changes announced

**Peer review approach**

- Methodology documents available

- Published in manuals (this is one)

- Editorial pieces explain applications

- Criticism welcomed and incorporated

### 20.4 Bibliografia anotada — foundational papers
> *Notação: \[★★★\] = leitura essencial; \[★★\] = útil; \[★\] = interesse específico.*

**Damodaran, Aswath (various, continuously updated).** Implied ERP and related resources. NYU Stern. **\[★★★\]** *Primary reference throughout. Free resources at pages.stern.nyu.edu.*

**Damodaran, Aswath (2012).** Investment Valuation: Tools and Techniques for Determining the Value of Any Asset. Wiley. **\[★★★\]** *Comprehensive valuation reference. 3rd edition standard.*

**Nelson, Charles R. and Andrew F. Siegel (1987).** "Parsimonious Modeling of Yield Curves." Journal of Business 60(4): 473-489. **\[★★★\]** *The foundational paper for NSS methodology. Essential.*

**Svensson, Lars E.O. (1994).** "Estimating and Interpreting Forward Interest Rates: Sweden 1992-1994." NBER Working Paper 4871. **\[★★★\]** *Extension of Nelson-Siegel. Foundation for NSS extended model.*

**Gurkaynak, Refet S., Brian Sack and Jonathan H. Wright (2007).** "The U.S. Treasury Yield Curve: 1961 to the Present." Journal of Monetary Economics 54(8): 2291-2304. **\[★★★\]** *Fed-published NSS-fitted US curve. Historical depth and methodology.*

**Litterman, Robert and José Scheinkman (1991).** "Common Factors Affecting Bond Returns." Journal of Fixed Income 1(1): 54-61. **\[★★★\]** *PCA decomposition of yield curves. Level-slope-curvature framework.*

**Anderson, Nicola and John Sleath (2001).** "New Estimates of the UK Real and Nominal Yield Curves." Bank of England Quarterly Bulletin Winter 2001. **\[★★\]** *BoE Anderson-Sleath smoothing spline methodology.*

### 20.5 Bibliografia — ERP and equity pricing
**Fernandez, Pablo (annual).** "Market Risk Premium and Risk-Free Rate used for X countries in 2024: A survey." IESE Business School working papers. **\[★★\]** *Annual survey of ERP and risk-free assumptions by practitioners globally.*

**Mehra, Rajnish and Edward C. Prescott (1985).** "The Equity Premium: A Puzzle." Journal of Monetary Economics 15(2): 145-161. **\[★★\]** *Classic paper on historical ERP being too high. Still debated.*

**Fama, Eugene F. and Kenneth R. French (2002).** "The Equity Premium." Journal of Finance 57(2): 637-659. **\[★★★\]** *Important paper showing historical ERP likely overestimates expected.*

**Shiller, Robert J. (2000, 2005, 2015).** Irrational Exuberance. Princeton University Press. **\[★★★\]** *CAPE methodology and historical context.*

**Campbell, John Y. and Robert J. Shiller (1988).** "The Dividend-Price Ratio and Expectations of Future Dividends and Discount Factors." Review of Financial Studies 1(3): 195-228. **\[★★\]** *Foundation for CAPE approach.*

### 20.6 Bibliografia — Country Risk Premium
**Damodaran, Aswath (2003).** "Measuring Company Exposure to Country Risk: Theory and Practice." Journal of Applied Finance 13(2): 63-76. **\[★★★\]** *Lambda framework for country risk exposure.*

**Bekaert, Geert and Campbell R. Harvey (1995).** "Time-Varying World Market Integration." Journal of Finance 50(2): 403-444. **\[★★\]** *Market integration and country-specific pricing.*

**Erb, Claude B., Campbell R. Harvey and Tadas E. Viskanta (1996).** "Political Risk, Economic Risk, and Financial Risk." Financial Analysts Journal 52(6): 29-46. **\[★★\]** *ICRG ratings and subsequent equity returns.*

### 20.7 Bibliografia — credit ratings and default
**Moody's Investors Service (annual).** Annual Default Study. Moody's Analytics. **\[★★★\]** *Gold standard for default probability data. Updated annually.*

**Standard & Poor's (annual).** Sovereign Defaults and Rating Transition Data, 2024 Update. **\[★★★\]** *Comprehensive sovereign default database.*

**Elton, Edwin J., Martin J. Gruber, Deepak Agrawal and Christopher Mann (2001).** "Explaining the Rate Spread on Corporate Bonds." Journal of Finance 56(1): 247-277. **\[★★★\]** *Classic decomposition of corporate bond spreads.*

**Huang, Jing-Zhi and Ming Huang (2012).** "How Much of the Corporate-Treasury Yield Spread is Due to Credit Risk?" Review of Asset Pricing Studies 2(2): 153-202. **\[★★\]** *Structural credit risk model decomposition.*

**Reinhart, Carmen M. and Kenneth S. Rogoff (2009).** This Time Is Different: Eight Centuries of Financial Folly. Princeton University Press. **\[★★★\]** *Historical sovereign defaults comprehensive. Essential.*

### 20.8 Bibliografia — expected inflation and breakevens
**D'Amico, Stefania, Don H. Kim and Min Wei (2018).** "Tips from TIPS: The Informational Content of Treasury Inflation-Protected Security Prices." Journal of Financial and Quantitative Analysis 53(1): 395-436. **\[★★★\]** *Decomposition of TIPS breakevens into expected inflation and risk premium.*

**Chernov, Mikhail and Philippe Mueller (2012).** "The Term Structure of Inflation Expectations." Journal of Financial Economics 106(2): 367-394. **\[★★\]** *Term structure model of inflation expectations.*

**Ang, Andrew, Geert Bekaert and Min Wei (2007).** "Do Macro Variables, Asset Markets or Surveys Forecast Inflation Better?" Journal of Monetary Economics 54(4): 1163-1212. **\[★★★\]** *Comparison of forecasting methods for inflation.*

**Hördahl, Peter and Oreste Tristani (2010).** "Inflation Risk Premia in the US and the Euro Area." ECB Working Paper 1270. **\[★★\]** *Cross-border inflation risk premium analysis.*

**Breedon, Francis and Jagjit S. Chadha (1997).** "The Information Content of the Inflation Term Structure." Journal of Macroeconomics 19(4): 633-648. **\[★★\]** *UK inflation term structure analysis.*

### 20.9 Bibliografia — cost of capital cross-border
**Sharpe, William F. (1964).** "Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk." Journal of Finance 19(3): 425-442. **\[★★★\]** *The foundational CAPM paper. Nobel prize-winning work.*

**Stulz, Rene M. (1995).** "Globalization, Corporate Finance, and the Cost of Capital." Journal of Applied Corporate Finance 12(3): 8-25. **\[★★\]** *International cost of capital framework.*

**Bekaert, Geert, Campbell R. Harvey and Christian Lundblad (2007).** "Liquidity and Expected Returns: Lessons from Emerging Markets." Review of Financial Studies 20(6): 1783-1831. **\[★★\]** *EM liquidity and cost of capital.*

### 20.10 Bibliografia — Fisher equation and real rates
**Fisher, Irving (1930).** The Theory of Interest. Macmillan. **\[★★\]** *Fisher equation foundation.*

**Mishkin, Frederic S. (1990).** "What Does the Term Structure Tell Us About Future Inflation?" Journal of Monetary Economics 25(1): 77-95. **\[★★\]** *Term structure as inflation predictor.*

### 20.11 Bibliografia — PPP and FX
**Rogoff, Kenneth (1996).** "The Purchasing Power Parity Puzzle." Journal of Economic Literature 34(2): 647-668. **\[★★★\]** *Comprehensive survey of PPP literature.*

**Frenkel, Jacob A. (1976).** "A Monetary Approach to the Exchange Rate: Doctrinal Aspects and Empirical Evidence." Scandinavian Journal of Economics 78(2): 200-224. **\[★★\]** *Monetary approach to exchange rates.*

**Meese, Richard A. and Kenneth Rogoff (1983).** "Empirical Exchange Rate Models of the Seventies: Do They Fit Out of Sample?" Journal of International Economics 14(1-2): 3-24. **\[★★\]** *Famous random walk challenge to FX models.*

### 20.12 Bibliografia — Portugal specific
**Banco de Portugal (semianual).** Relatório de Estabilidade Financeira. **\[★★★\]** *Essential for Portugal financial system analysis.*

**Banco de Portugal (semianual).** Perspetivas Económicas. **\[★★★\]** *Economic outlook with projections.*

**IGCP (monthly).** Portuguese Government Debt — Monthly Report. **\[★★★\]** *Primary source for Portuguese sovereign data.*

### 20.13 Resources e data sources
- **Damodaran's website:** pages.stern.nyu.edu/~adamodar — free, comprehensive, monthly updated

- **Shiller data:** shillerdata.com — CAPE and historical data

- **FRED:** fred.stlouisfed.org — St Louis Fed, free

- **ECB SDW:** sdw.ecb.europa.eu — free

- **BIS:** bis.org/statistics — free

- **World Government Bonds:** worldgovernmentbonds.com — free CDS data

- **Bundesbank:** bundesbank.de — Svensson yield curves

- **BoE:** bankofengland.co.uk — Anderson-Sleath curves

- **Fed H.15:** federalreserve.gov/releases/h15/ — daily rates

- **US Treasury:** treasury.gov — constant maturity rates

- **IGCP:** igcp.pt — Portuguese sovereign data

- **BPStat:** bpstat.bportugal.pt — Portuguese statistics

### 20.14 The meta-principle — honest calibration
Os cinco sub-models SONAR partilham filosofia comum — metodologia transparente, calibração honesta, acknowledgment das limitações. Isto contrasta com black-box approaches comerciais.

**What SONAR claims**

- Probabilistic, model-based outputs daily

- Cross-validated against industry sources

- Transparent methodology reproducible

- Confidence intervals honestly reflecting uncertainty

- Integration with cycle framework creates unique value

**What SONAR does NOT claim**

- Precision beyond stated confidence

- Universal applicability

- Substitute for qualitative judgment

- Immunity from model risk

- Real-time intraday precision

> *SONAR v1 está completo. Quatro ciclos + cinco sub-models + matriz 4-way + diagnosticos aplicados + cost-of-capital framework integrado. Documentação extensa. Methodology transparente. Honest calibration. O próximo capítulo é execução — dashboard v2, fund launch, editorial pipeline operacional. Mas o framework está pronto.*

**Encerramento do Manual dos Sub-Modelos**

Seis Partes. Vinte capítulos. 5.235+ parágrafos dedicados aos cinco sub-models quantitativos SONAR:

- **Parte I — Fundações** (Caps 1-3): os cinco sub-models identificados, cost of capital cross-border theory, moeda funcional e inflação-câmbio ajustamentos. Positioning face a Bloomberg, Damodaran, Refinitiv.

- **Parte II — Yield curves por país** (Caps 4-6): Nelson-Siegel-Svensson methodology, fontes per country (15+ países), outputs operacionais (spot, zero, forward, real, swap). Level-slope-curvature decomposition.

- **Parte III — ERP diária computada** (Caps 7-9): implied ERP theory (Gordon, DCF, earnings yield), implementação técnica S&P 500 + análogos EA/UK/Japan, validação contra Damodaran monthly e backtest signal quality. ERP substituiu dependência mensal Damodaran.

- **Parte IV — Country Risk Premium** (Caps 10-12): CDS-based + sovereign spread + volatility ratio synthesis Damodaran-style. CRP operational table para 30+ países. Portugal deep dive (CRP 20bps pre-crisis → 1500bps 2012 → 54bps 2026).

- **Parte V — Rating mapping e Expected inflation** (Caps 13-17, cinco capítulos): rating agency landscape com SONAR common scale 0-21, historical default rates Moody's, rating-to-spread operational table, expected inflation market-based + surveys + modelos, Portugal specifically sem TIPS-like mercado.

- **Parte VI — Integração e aplicação** (Caps 18-20): arquitetura SONAR completa integrando ciclos + sub-models, use cases práticos (EDP DCF detalhado, Brazilian bank cross-border, arbitrage detection, cycle-informed allocation, editorial templates), caveats transversais e bibliografia anotada com 30+ references categorizadas.

**Outputs operacionais da v1**

112. Yield curves (spot, zero, forward, real, swap) para 15+ países daily

113. ERP diária (DCF, Gordon, simple, CAPE) para US, EA, UK, JP

114. CRP daily para 30+ países

115. Rating-to-spread mapping para 22 rating notches

116. Expected inflation term structure para 17+ países

117. Cost of equity cross-border computable via simple API call

**SONAR v1 — o marco completo**

Com este manual, a arquitetura SONAR v1 está operacionalmente completa:

118. Quatro ciclos: económico, crédito, monetário, financeiro — todos documentados

119. Cinco sub-models: yield curves, ERP, CRP, rating-spread, expected inflation — este manual

120. Matriz 4-way + overlays + four applied diagnostics — integration layer

121. Cost of capital cross-border framework — application layer

122. Pipeline operacional diário — schedule documentado

123. Editorial pipeline com 22+ ângulos — content layer

124. Five complete Word manuals + four data source plans + master consolidated versions

**Estatística final**

| **Módulo** | **Manual** | **Master** | **Plano dados** | **Parágrafos** |
|------------|------------|------------|-----------------|----------------|
| Crédito    | ✓          | ✓          | ✓               | 2.251          |
| Monetário  | ✓          | ✓          | ✓               | 2.928          |
| Económico  | ✓          | ✓          | ✓               | 4.178          |
| Financeiro | ✓          | ✓          | ✓               | 4.920          |
| Sub-Models | ✓          | pending    | pending         | 5.235+         |
| Total      | 5          | 4          | 4               | ~19.500        |

**Material editorial consolidado — 27+ ângulos total**

Combinando os ângulos dos cinco manuais:

125. "Portugal 2026 vs 2007 — lições do framework SONAR integrado"

126. "Os quatro diagnósticos aplicados a 2026 — bubble, risk, real estate, Minsky"

127. "AI bubble debate — o que a matriz 4-way nos diz"

128. "ERP diário — o que Damodaran nos daria se publicasse diariamente"

129. "Cost of equity Portugal em 2026 — framework completo aplicado"

130. "CRP Portugal hoje vs 2012 — a jornada de 1500bps a 54bps"

131. "Rating A- Portugal vs A- US — what the rating doesn't capture"

132. "5y5y forward inflation — the number that Lagarde and Powell see first"

133. "PPP implied FX — onde estão os big moves cross-currency 10Y forward"

134. "Yield curve Portugal — do BdP raw à curva NSS operacional"

135. "Level, slope, curvature — as três dimensões que explicam 99% das curves"

136. "Portugal real yield em 2026 — 0.80% em EUR, o que significa"

137. "Moeda funcional — o erro silencioso em DCFs cross-border"

138. "Shiller CAPE vs Damodaran ERP — quando divergem, algo acontece"

139. "Cross-market ERP — Japan 5.5%, Europe 5.25%, US 4.85% em 2026"

140. "Fisher em 2026 — real rates tell us sobre the Fed's credibility"

141. "Italy 140bps vs Portugal 70bps — the periphery gap that widened"

142. "Bond-CDS basis — os spreads que divergem e o que isso nos diz"

143. "Moody's Default Study — o que 100 anos de defaults nos ensinam"

144. "Quando SONAR alerta — as cinco combinations que precedem crises"

145. "Expected inflation cross-country em 2026 — o mapa global"

146. "Recovery rates on sovereign defaults — Argentina, Greece, Ukraine histórias"

147. "Cross-border DCF — Brazilian banco avaliado em EUR, o framework completo"

148. "O framework Damodaran em 2026 — aplicado cross-country systematically"

149. "CDS vs rating vs market spread — quando as três divergem"

150. "Portugal rating journey 2005-2026 — the 20 years we left the junk"

151. "SONAR's five outputs — the ones that should be daily not monthly"

**Próximos passos naturais — v2**

152. **Plano de fontes de dados dos sub-models:** documento markdown paralelo aos quatro planos de ciclos, específico para Shiller, Damodaran, BIS, rating agencies, Glassnode, CFTC, inflation swaps, expected inflation computation.

153. **Master consolidado sub-models:** merge das 6 Partes num único ficheiro Word com capa global, TOC completo, dividers entre Partes (paralelo aos quatro masters dos ciclos).

154. **Dashboard SONAR v2 multi-ciclo + sub-models:** protótipo HTML cristalizando visualmente toda a arquitetura v1.

155. **Primeira coluna de teste editorial:** desenvolver um dos 27+ ângulos até draft publicável.

156. **Backtesting automation:** validation systemático do framework v1 contra históricos, identificando alpha generation potential.

> *Com este quinto manual, SONAR v1 está arquiteturalmente completo. Documentação + metodologia + outputs operacionais + Portugal-aware + cross-border capable. O framework pronto para operação — dashboard, editorial pipeline, eventual fund launch. Este é o fundamento.*

*— fim do manual dos sub-modelos —*

*— fim da arquitetura SONAR v1 —*

**7365 Capital · SONAR Research · Abril 2026**
