# SONAR-Monetary · Plano de Fontes de Dados para Implementação

> **Documento de referência técnica** · 7365 Capital · Abril 2026
> Framework: Manual do Ciclo Monetário (6 partes, 20 capítulos)
> Contexto: documento complementar ao "SONAR Data Sources Implementation Plan" do ciclo de crédito

---

## Objetivo deste documento

Mapear **todas as fontes de dados** necessárias para operacionalizar o framework SONAR-Monetary descrito no manual. Para cada fonte: o que fornece, como aceder, nível de criticidade, e integração no sistema.

O documento está organizado em **7 camadas funcionais** que espelham a arquitetura M1-M4 + overlays do SONAR-Monetary, seguidas por um plano de implementação em **3 tiers** de prioridade.

**Relação com o plano de crédito**: há sobreposição substancial de fontes (FRED, ECB SDW, BIS, Eurostat, Trading Economics, BPStat). Este documento foca apenas nas fontes **distintivas do monetário** ou nas séries específicas dessas fontes partilhadas que são relevantes para o stance, transmissão e expectations.

---

## Sumário executivo

| Aspeto | Conclusão |
|---|---|
| Cobertura Tier 1 | **~95% gratuito**, cobre 80% do framework |
| Chaves adicionais necessárias | FRED API key (partilhada com crédito, já prevista) |
| Séries premium institucionais | CME futures, Bloomberg speech archive (opcional) |
| Tempo estimado MVP | 4 semanas (pode correr em paralelo ao connector credit) |
| Custo Tier 1 | €0 (fontes públicas) |
| Custo Tier 3 (opcional) | €30-50k/ano (CME data, Bloomberg terminal) |

---

## Camada 1 · Shadow rates — o núcleo do M1

Esta camada é **específica do monetário** — não tem equivalente no credit cycle. Cobre a métrica central da Parte III Cap 7 do manual.

### 1.1 Wu-Xia Shadow Rate via Atlanta Fed · `atlantafed.org`

A série canónica para US shadow rate. Produzida pelo Federal Reserve Bank of Atlanta desde 2014, baseada no paper Wu & Xia (2016).

**Status atual (importante):**
A Atlanta Fed **suspendeu updates em Abril 2022** quando o Fed saiu do ZLB. Os updates **só retomarão se e quando ZLB retornar**. Quando o target range está acima de 0-0.25%, o shadow rate é "generally close to the effective fed funds rate".

**Implicações operacionais para o SONAR:**
- Durante períodos não-ZLB (atual): usar fed funds rate directamente como proxy de shadow rate
- Durante ZLB futuro: retomar ingestão da série Atlanta Fed
- Histórico 1960-2022 está disponível como Excel/Matlab download

**Acesso técnico:**
- URL: `atlantafed.org/cqer/research/wu-xia-shadow-federal-funds-rate`
- Formato: Excel e Matlab download direto
- Gratuito, sem chave, sem API
- Histórico desde Janeiro 1960 (Wu-Xia extended back-computed)

**Metodologia:**
Input data são one-month forward rates em n = 1/4, 1/2, 1, 2, 5, 7 e 10 anos, construídos a partir de Nelson-Siegel-Svensson yield curve parameters do Gurkaynak, Sack & Wright (2006) dataset (GSW). Modelo assume shadow rate como função linear de três factores latentes seguindo VAR(1).

**Criticidade: ESSENCIAL para histórico pré-2022.** Para live monitoring, menos crítico (fed funds = shadow quando acima de ZLB).

### 1.2 Jing Cynthia Wu · site pessoal

Autora primária mantém site pessoal com shadow rates para **US + EA + UK**, com diferentes variantes metodológicas.

**Acesso técnico:**
- URL: `sites.google.com/view/jingcynthiawu/shadow-rates`
- Formato: Matlab e Excel download
- Gratuito

**Séries disponíveis:**
- **US**: usando método Wu-Xia (JMCB 2016), 1990-2022
- **EA**: usando método Wu-Xia (2017) que adapta para NIRP regime, 1990-2021
- **UK**: 1990-2021

**Status atual**: como Atlanta Fed, updates suspensos. Retomarão quando ZLB regressar.

**Criticidade: ESSENCIAL para coverage multi-country do histórico.** EA shadow rate atingiu -7.56% em 2020 (documentado no manual Cap 7.3).

### 1.3 Krippner SSR via LJK Macro Finance Analysis · `ljkmfa.com`

Fonte alternativa dominante. Leo Krippner, ex-RBNZ, mantém site ativo com publicação mensal de múltiplos indicators de monetary stance.

**Vantagem crítica face a Wu-Xia: continua a ser atualizado em 2025-2026.**

**Acesso técnico:**
- URL: `ljkmfa.com/visitors/`
- Formato: Excel/PDF download
- Gratuito, livre para uso com atribuição

**Séries publicadas (Monetary Policy Stance file):**
- **Shadow Short Rate (SSR)** para 7 economias: US, EA, JP, UK, CA, AU, NZ
- **Effective Monetary Stimulus (EMS)** — agregado complementar
- **Expected Time to Lift-off (ETL)** — tempo esperado até primeiro hike
- Yield curve decompositions
- Inflation swap decompositions

**Metodologia:**
Krippner ANSM(2) com estimated lower bound — 2 factors do yield curve + 1 ZLB constraint. Paper de referência: Krippner (2015) Zero Lower Bound Term Structure Modeling.

**Código Python disponível:**
- GitHub: `github.com/as4456/Leo_Krippner_SSR`
- Permite replicação local para países adicionais
- Requires Bloomberg yield curve data para updates próprios

**Criticidade: ESSENCIAL.** É a fonte única de SSR live em 2026, cobrindo 7 dos 10 BCs principais do SONAR. Cobertura em falta: SNB, PBoC, Riksbank (para estes, usar policy rate como proxy).

### 1.4 Laubach-Williams r-star · NY Fed · `newyorkfed.org`

Estimativa oficial da taxa neutral, input crítico para M1 (shadow rate - r*) e M2 (Taylor Rule).

**Acesso técnico:**
- URL: `newyorkfed.org/research/policy/rstar`
- Publicação: trimestral
- Formato: Excel download + paper with methodology
- Gratuito, sem chave

**Séries disponíveis:**
- **Laubach-Williams (2003) original** — apenas US
- **Holston-Laubach-Williams (HLW)** — US, EA, UK, CA (extended methodology)
- Publicados em múltiplas vintages (original + updates)

**Implicações 2026:**
- US r* atual (Q4 2024): ~0.85% real (acima da estimativa pré-2023 de ~0.5%)
- EA r*: ~0.2% real
- Questão aberta: r* subiu estruturalmente? Controvérsia ativa.

**Criticidade: ESSENCIAL.** r* é input direto do M1_stance_vs_neutral.

### 1.5 Workarounds para Portugal e Cluster 2 EU

Portugal não tem shadow rate ou r* nacional (é ECB-level).

**Workaround 1 — ECB SSR adjusted**:
Take Krippner EA SSR, ajustar por spread PT sovereign e MIR spread.
```
SSR_PT_approx = SSR_EA + α × (PT_spread_vs_Bund) + β × (MIR_PT - MIR_EA_avg)
```
Com α, β calibrados empiricamente (~0.3-0.5 each).

**Workaround 2 — Country-level effective policy stance**:
Construir índice proprietário usando DFR ECB + PT sovereign spread + MIR PT weighted combination. Mais trabalhoso mas mais rigoroso.

**Workaround 3 — PT r* estimation**:
BdP ocasionalmente publica estimates em Working Papers. Alternativa: usar EA r* + 10-30bps country risk premium.

**Criticidade: ESSENCIAL para análise nacional PT.** Workaround 1 suficiente para v1.

---

## Camada 2 · Taylor Rule inputs — M2 layer

Esta camada requer 4 inputs independentes: r* (já coberto), inflation, inflation target, output gap.

### 2.1 Inflation data

Já coberta nos principais datasets:
- **US PCE core**: FRED série `PCEPILFE` (YoY)
- **US CPI core**: FRED série `CPILFESL` (YoY)
- **EA HICP core**: ECB SDW `ICP.M.U2.N.XEF000.4.ANR`
- **UK CPI**: ONS via FRED `GBRCPIALLMINMEI`
- **Japan CPI core**: e-Stat Japan ou FRED `JPNCPIALLMINMEI`

**Já presente no plano de crédito** (Eurostat, FRED). Sem trabalho adicional.

### 2.2 Output gap estimates

**Três fontes principais, frequentemente divergentes:**

| Fonte | Acesso | Cobertura | Frequência |
|---|---|---|---|
| **IMF WEO** | Free download | Global (190+ países) | Semi-anual (Apr, Oct) |
| **OECD Economic Outlook** | Free via SDMX | OECD (37 países) | Semi-anual + interim |
| **CBO** | Free download | US only | Anual + updates |
| **European Commission AMECO** | Free download | EU + associated | Trimestral |

**Acesso técnico:**
- **IMF**: `imf.org/en/Publications/WEO/weo-database` — CSV/Excel download
- **OECD**: SDMX API `sdmx.oecd.org/public/rest/` (já coberto no Tier 2 do plano credit)
- **CBO**: `cbo.gov/data/budget-economic-data` — Excel download
- **AMECO**: `ec.europa.eu/economy_finance/ameco/user/serie/SelectSerie.cfm` — CSV

**Problema conhecido** (Cap 8.5 do manual): output gap estimates podem divergir 1-2pp entre fontes. Solução SONAR: usar IMF WEO como primary, OECD como cross-check, flag divergence > 1pp como uncertainty signal.

**Criticidade: ALTA.** Output gap é input crítico mas ruidoso.

### 2.3 NAIRU / potential output adicional

Para refinements da Taylor Rule forward-looking:
- **CBO potential output**: `cbo.gov/publications` — US
- **ECB Eurosystem staff projections**: ECB SDW, potential output estimates
- **OECD potential output**: OECD.Stat

**Criticidade: MÉDIA.** Útil para variantes forward-looking mas não bloqueador.

---

## Camada 3 · Market-implied expectations — M3 layer

Esta é a camada **mais dependente de fontes de mercado**. Algumas gratuitas, outras institucionais.

### 3.1 Fed funds futures · CME Group

A fonte primária para US rate expectations até 24 meses.

**Acesso gratuito limitado:**
- **CME FedWatch Tool**: `cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html` — live probabilities, sem download histórico
- **CBOT Fed funds futures (ZQ)**: preços end-of-day gratuitos via Investing.com, Yahoo Finance
- **Histórico completo**: CME Datamine (pago, ~$200-500/mês por dataset)

**Acesso alternativo via FRED:**
Para estimativas derivadas (não preços directos):
- `DFEDTAR`, `DFEDTARL`, `DFEDTARU` — Fed funds target rate and bounds
- `EFFR` — Effective federal funds rate

**Implementação SONAR recomendada:**
Para MVP, scraper diário do CME FedWatch page captures current implied probabilities sem histórico. Para histórico (requerido para backtest), Quandl/NASDAQ Data Link oferece Fed funds futures end-of-day data gratuitamente ou via plano barato.

**Criticidade: ALTA.** Fed funds futures são o instrumento mais líquido para short-horizon Fed expectations.

### 3.2 OIS curves · €STR, SOFR, SONIA, TONA

OIS curves estendem para 10Y+ — o instrument para medium-term expectations.

**Acesso por moeda:**

**SOFR (US) OIS:**
- ICE Benchmark Administration publishes SOFR daily
- SOFR fixing disponível via FRED: `SOFR`
- SOFR OIS curves (end-of-day): Bloomberg, Refinitiv, ICE Data Services (pago)
- FRED tem `SOFR30DAYAVG`, `SOFR90DAYAVG`, `SOFR180DAYAVG` — useful partial coverage

**€STR (EA) OIS:**
- ECB SDW publica €STR directamente: dataset `EST` (daily fixings since Oct 2019)
- €STR swap curves: ECB SDW `YC` dataset tem yield curves que permitem construção implícita
- European Commission MMSR data agregado

**SONIA (UK) OIS:**
- Bank of England publishes SONIA directly: `bankofengland.co.uk/boeapps/database/`
- BoE series `IUDSOIA` — SONIA daily
- UK yield curves: BoE publicou UK Yield Curves dataset (nominal + real + inflation)

**TONA (JP) OIS:**
- Bank of Japan publishes TONA: `boj.or.jp/en/statistics/market/short/index.htm`
- Menos liquid que outros — dados menos disponíveis

**Recomendação SONAR:**
Para v1, usar `ECB SDW YC` dataset (gratuito, cobertura EA completa, methodology Nelson-Siegel) para derivar OIS curves via swap spreads. Para SOFR/SONIA/TONA, usar BoE published curves e FRED séries derivadas.

**Criticidade: ALTA.** OIS curves são input directo do EP sub-index.

### 3.3 Inflation swaps e breakevens

Para separação de componente real e inflação.

**Via FRED (gratuito):**
- `T5YIE` — 5Y breakeven inflation
- `T10YIE` — 10Y breakeven inflation
- `T5YIFR` — 5Y 5Y forward inflation expectation rate (chave para SONAR)
- `DFII5`, `DFII10` — TIPS yields

**Via ECB SDW (EA):**
- Euro area inflation swaps: `FM.M.U2.EUR.RT.IL.EUR1Y_EA.YLD` e variantes para 2Y, 5Y, 10Y

**Via FRED (EA proxy):**
- `EUR5Y5Y` não existe oficialmente, mas pode ser computado a partir de swap rates e nominal yields

**Criticidade: ALTA.** 5Y5Y forward inflation expectations é métrica crítica de credibility signal (CS sub-index).

### 3.4 Dot plots e forward guidance — FOMC SEP

Summary of Economic Projections (SEP) — Fed's explicit projections.

**Acesso gratuito:**
- URL: `federalreserve.gov/monetarypolicy/fomccalendars.htm`
- Formato: PDF publicado 4x por ano (março, junho, setembro, dezembro)
- SEP data: `federalreserve.gov/monetarypolicy/fomcprojtabl*.htm`

**Processing necessário:**
- Scraping de PDF (manual ou via `pdfplumber` Python)
- Extração: median dot, central tendency, range, individual dots
- Fields: fed funds rate, PCE inflation, core PCE, GDP growth, unemployment

**Alternativa programmatic:**
- Philadelphia Fed mantém series históricas parciais no Real-Time Data Research
- `phil.frb.org/research-and-data/real-time-center/` 

**Criticidade: ALTA.** Dot plot deviation vs market é input do CS sub-index.

### 3.5 ECB rate projections

ECB não publica dot plot equivalente mas publica rate path projections ocasionais.

**Acesso:**
- ECB macroeconomic projections: quarterly, `ecb.europa.eu/pub/projections/html/index.en.html`
- Contém rate assumptions (não commitments) para projeção

**Menos formalizado que Fed dot plot** — deve ser complementado com speech analysis.

### 3.6 Policy surprise indices

Medida de componente *não antecipada* das decisões BC. Computação requer intraday data.

**Fontes:**
- **Kuttner-style**: Change in 3M fed funds futures em janela de 30min à volta do FOMC announcement
- **Gürkaynak-Sack-Swanson**: factor decomposition (target, path, asset factors)
- **Recent academic datasets**: múltiplos papers publicam surprise series

**Acesso operacional:**
- Silvia Miranda-Agrippino mantém public dataset: `silviamirandaagrippino.com/code-data`
- Nakamura-Steinsson dataset também disponível via autores

**Criticidade: MÉDIA.** Útil para detecção de regime shifts, mas não crítica para MVP.

---

## Camada 4 · Financial Conditions Indices — M4 layer

Esta camada tem sobreposição parcial com plano de crédito (já cobrimos NFCI).

### 4.1 Chicago Fed NFCI e ANFCI

Já cobertos no plano de crédito via FRED séries `NFCI`, `ANFCI`.

**Para SONAR-Monetary especificamente**, também utilizar:
- `NFCINONFINLEVERAGE` — non-financial leverage subindex
- `NFCICREDIT` — credit subindex
- `NFCIRISK` — risk subindex
- `NFCILEVERAGE` — overall leverage

**Criticidade: ESSENCIAL.** Já resolvido via FRED.

### 4.2 Goldman Sachs FCI

Proprietário, não disponível publicly. Algumas aproximações via:
- Papers de replicação académica
- GS research notes (para clientes)

**Criticidade: BAIXA.** NFCI suficiente para v1.

### 4.3 Bloomberg Financial Conditions Index (BFCI)

Disponível only via Bloomberg Terminal. Para utilizadores com acesso:
- `BFCIUS <Index>` — US
- `BFCIEU <Index>` — EA

**Criticidade: BAIXA para MVP.** Se já tiver Bloomberg, bonus.

### 4.4 IMF Global Financial Stability Report FCIs

Publicação trimestral com FCIs cross-country.

**Acesso:**
- URL: `imf.org/en/Publications/GFSR`
- Formato: PDF + Excel annex
- Gratuito

**Cobertura:** US, EA, UK, JP, CN, EMs aggregated.

**Criticidade: MÉDIA.** Útil para cross-country FCI comparison.

### 4.5 Custom FCI para Portugal

O manual Cap 10.6 propõe construção custom para PT (não existe off-the-shelf).

**Components necessários (todos gratuitos):**
- DFR ECB — já via ECB SDW
- 10Y PT sovereign yield — ECB SDW `IRS.M.PT.L.L40.CI.0000.EUR.N.Z`
- Spread PT-Bund — computado
- PSI-20 valuation — via Twelve Data (já existente)
- EUR NEER — via ECB SDW `EXR.M.E5.EUR.EN00.A`
- PT mortgage rate — ECB SDW `MIR.M.PT.B.A22.A.R.A.2250.EUR.N`
- VSTOXX — via Yahoo Finance ou Stooq

**Implementation SONAR:**
Construção em Python com z-score standardization (10Y rolling window) e weighted aggregation conforme pesos do manual (20%/20%/15%/10%/15%/15%/5%).

**Criticidade: ALTA para PT coverage.** É o diferenciador distintivo da coluna "A Equação".

---

## Camada 5 · Communication analysis — CS sub-index

Esta é a camada **mais trabalhosa** operacionalmente — requer processamento de texto em quantidades significativas.

### 5.1 FOMC speeches e minutes

**Fed speeches arquivo:**
- URL: `federalreserve.gov/newsevents/speeches.htm`
- Histórico: disponível desde 1996 na íntegra
- Formato: HTML web pages
- Pode ser scraped com `BeautifulSoup` ou `scrapy`

**FOMC minutes:**
- URL: `federalreserve.gov/monetarypolicy/fomccalendars.htm`
- Publicadas ~3 semanas após cada meeting
- Formato: HTML + PDF

**FOMC statements (decisions):**
- Same URL, publicadas immediately after meeting
- Short (1-2 pages), mas high-signal

**Processing pipeline sugerido:**
1. Daily scraper de federalreserve.gov para novo conteúdo
2. Store em database (PostgreSQL full-text search ou Elasticsearch)
3. Hawkish/dovish scoring via:
   - Rule-based keyword matching (baseline)
   - FinBERT ou similar financial NLP model (v2)
   - LLM-based classification (v3)
4. Aggregation em "communication hawkishness index"

**Criticidade: ALTA para reaction function prediction.** Cap 19.9 do manual descreve este processo.

### 5.2 ECB speeches e press conferences

**ECB speeches:**
- URL: `ecb.europa.eu/press/key/speeches/html/index.en.html`
- Histórico completo desde 1998
- Formato: HTML
- Multiple speakers (President, VP, Executive Board, national governors)

**Press conferences:**
- URL: `ecb.europa.eu/press/pressconf/html/index.en.html`
- Full transcripts desde 1998
- Include Q&A sections (high-information)

**ECB Monetary Policy Account (equivalente a FOMC minutes):**
- Published ~4 weeks after Governing Council meeting
- URL: `ecb.europa.eu/press/accounts/html/index.en.html`

**Criticidade: ALTA.** Para Portugal via ECB, é a fonte primária.

### 5.3 BoE speeches, minutes, voting records

**Unique advantage**: BoE publishes individual voting records for each MPC meeting, allowing direct dissent analysis.

**Acesso:**
- URL: `bankofengland.co.uk/monetary-policy/monetary-policy-summary-and-minutes`
- Voting records em each minutes document
- Individual speeches: `bankofengland.co.uk/news/speeches`

**Criticidade: MÉDIA.** Mais acessível que Fed/ECB, menor coverage no SONAR.

### 5.4 BoJ communications

**Less structured** — BoJ publica policy statements, opinion summaries, speeches.

**Acesso:**
- Statements: `boj.or.jp/en/mopo/mpmdeci/mpr_2024/index.htm`
- Summaries of Opinions: same area
- Governor speeches: `boj.or.jp/en/about/press/koen_index.htm`

**Special consideration**: BoJ communications são notoriously opaque. NLP approaches less reliable.

**Criticidade: BAIXA-MÉDIA.** Informal pragmatism em BoJ dificulta prediction automation.

### 5.5 Speech sentiment models e datasets

**Pre-built datasets:**
- **Apel & Grimaldi (2014)** — hawkish/dovish lexicon
- **Hansen, McMahon, Prat (2018)** — FOMC transparency study datasets
- **Husted, Rogers, Sun (2020)** — Fed communication uncertainty index

**NLP models:**
- **FinBERT** (financial BERT variant): pretrained em financial texts
- **Large language models** (Claude, GPT-4) for zero-shot classification — more expensive but more accurate

**Implementation recommendation:**
Start with rule-based lexicon (Apel-Grimaldi), upgrade to FinBERT as v2, LLM-based as v3 quando orçamento permitir.

---

## Camada 6 · Central bank balance sheets

### 6.1 Fed balance sheet data

**Via FRED:**
- `WALCL` — Total Assets of Federal Reserve Banks (weekly, since 2002)
- `WSHOTSL` — Treasury holdings
- `WSHOMCB` — MBS holdings
- `WAML1TOTL` — Total assets maturity breakdown

**Fed H.4.1 Release:**
- URL: `federalreserve.gov/releases/h41/current/`
- Weekly, extremely detailed
- XML, CSV, JSON formats
- Gratuito

**Criticidade: ALTA.** Balance sheet stance é componente directo do ES sub-index.

### 6.2 ECB balance sheet data

**Via ECB SDW:**
- Dataset `ILM` (ILM - IRLS) — Eurosystem consolidated balance sheet
- Weekly releases (Tuesday afternoons)

**Via ECB weekly financial statement:**
- URL: `ecb.europa.eu/press/pr/wfs/shared/html/index.en.html`
- Week-by-week breakdown
- APP and PEPP holdings separately

**Criticidade: ALTA.** QT via passive roll-off é tracked aqui.

### 6.3 BoE balance sheet

**Via BoE Database:**
- URL: `bankofengland.co.uk/boeapps/database/`
- Weekly bank return
- Asset Purchase Facility (APF) separately disclosed

### 6.4 BoJ balance sheet

**Via BoJ statistics:**
- URL: `boj.or.jp/en/statistics/boj/other/ac/index.htm`
- Monthly balance sheet summary
- Extremely large (~125% GDP) — outlier for monitoring

### 6.5 PBoC balance sheet

**Via PBoC:**
- URL: `pbc.gov.cn/en/3688066/index.html`
- Monthly, sometimes delayed
- Less transparent than major BCs

---

## Camada 7 · Trading Economics — cobertura agregada

Já coberta no plano de crédito. Para SONAR-Monetary especificamente, séries-chave incluem:

- **Central bank policy rates** — 150+ países, atualizadas live
- **Interest rates futures** — agregados principais
- **Currency values** — todas major pairs
- **Government bond yields** — yields principais por país
- **Central bank balance sheets** — para países onde acesso directo é complicado

**Criticidade: JÁ RESOLVIDO** (key já ativa `624f88489cd84146a4ee8d78db3fc01a`).

---

## Plano de implementação em 3 Tiers

### Tier 1 · MVP do connector SONAR-Monetary

**Característica: ~95% gratuito, cobre 80% do framework.**

| # | Fonte | Acesso | Papel no SONAR-Monetary | Prioridade |
|---|---|---|---|---|
| 1 | Krippner SSR (`ljkmfa.com`) | Público, download mensal | SSR live para 7 BCs (US, EA, JP, UK, CA, AU, NZ) | 🔴 Crítica |
| 2 | Wu-Xia histórico (Atlanta Fed + Wu site) | Público, download one-time | Backtest histórico shadow rates | 🔴 Crítica |
| 3 | FRED API v2 | Key grátis (já prevista) | PCE, CPI, breakevens, WALCL, NFCI, ANFCI, DFII | 🔴 Crítica |
| 4 | ECB SDW SDMX | Público, sem chave | €STR, HICP core, ILM, MIR, YC dataset | 🔴 Crítica |
| 5 | Laubach-Williams r* (NY Fed) | Público | r* US e HLW multi-country | 🔴 Crítica |
| 6 | IMF WEO output gap | Público, semi-anual | Taylor Rule input | 🟠 Alta |
| 7 | FOMC SEP scraper | Público, 4x/ano | Dot plot deviation vs market | 🟠 Alta |
| 8 | BoE Database | Público | SONIA, UK yields, APF data | 🟠 Alta |
| 9 | BIS SDMX (WS_CBPOL) | Público (já no plano credit) | Policy rates 40+ countries | ✅ Já ativo |
| 10 | Trading Economics | Key paga (já tem) | Cross-country policy rates backup | ✅ Já ativo |

### Tier 2 · Communication analysis e expectations depth

**Característica: requer processing pipelines mais complexas.**

| # | Fonte | Acesso | Papel |
|---|---|---|---|
| 11 | Fed speeches/minutes scraper | Público | CS sub-index, reaction function |
| 12 | ECB speeches/accounts scraper | Público | ECB reaction function |
| 13 | BoE minutes + voting records | Público | BoE most transparent dissent analysis |
| 14 | Miranda-Agrippino policy surprises | Público | Regime shift detection |
| 15 | Apel-Grimaldi hawkish-dovish lexicon | Público | Baseline NLP scoring |
| 16 | AMECO output gap (EC) | Público | Cross-check vs IMF |
| 17 | BoJ statements scraper | Público | Japan monetary cycle |
| 18 | FinBERT financial NLP | Open source | Advanced text classification |

### Tier 3 · Institutional

**Característica: caro, para v2+ ou coverage completa.**

| # | Fonte | Custo estimado | Papel |
|---|---|---|---|
| 19 | CME Datamine fed funds futures | ~$300-600/mês | Intraday futures data, policy surprises |
| 20 | Bloomberg Terminal | ~$25k/ano | OIS curves todas as moedas, BFCI, CDS |
| 21 | Refinitiv Eikon | ~$22k/ano | Alternativa a Bloomberg |
| 22 | Citi/GS FCI custom feeds | Institutional | Proprietary FCIs |
| 23 | LLM API para speech analysis | ~$500-2000/mês | High-quality text classification |

---

## Roadmap cronológico (4 semanas para MVP, pode correr em paralelo ao credit)

### Semana 1 — Setup shadow rates e r-star

- [ ] Implementar scraper mensal de Krippner SSR (ljkmfa.com)
- [ ] Download histórico Wu-Xia (Atlanta Fed + Wu site) — one-time
- [ ] Download Laubach-Williams r* (NY Fed)
- [ ] Schema v15 do SONAR com tabelas monetary_stance
- [ ] Implementar computação M1_stance_vs_neutral

**Entregáveis:**
- `connectors/krippner.py`
- `connectors/wu_xia_historical.py`
- `connectors/laubach_williams.py`
- M1 layer operacional para 7 BCs

### Semana 2 — Taylor Rule e M2 layer

- [ ] Connector IMF WEO output gap
- [ ] Implementação 4 variantes Taylor Rule (1993, 1999, inertia, forward-looking)
- [ ] Computação M2_gap para cada BC
- [ ] Validação contra dados históricos (US 2003-2005 Taylor gap test)

**Entregáveis:**
- `computation/taylor_rules.py`
- `connectors/imf_weo.py`
- M2 layer com 4 variantes

### Semana 3 — Market expectations (M3) e FCI (M4)

- [ ] FRED ingestion de breakevens, real yields, curve points
- [ ] ECB SDW YC dataset para €STR curves
- [ ] FOMC SEP scraper (PDF processing)
- [ ] Custom PT FCI construction
- [ ] M3 layer agregation
- [ ] M4 layer com custom PT FCI

**Entregáveis:**
- `connectors/fred_monetary.py`
- `connectors/ecb_sdw_monetary.py`
- `scrapers/fomc_sep.py`
- `computation/custom_fci_pt.py`
- M3 e M4 layers operacionais

### Semana 4 — MSC agregation e dashboard

- [ ] Agregação 5 sub-indices em MSC (pesos 30/25/20/15/10)
- [ ] Dilemma detector (4 triggers)
- [ ] Dashboard SONAR-Monetary prototype
- [ ] Cross-country comparison (10 BCs)
- [ ] Integração com CCCS do credit cycle

**Entregáveis:**
- `computation/msc.py`
- `computation/dilemma_detector.py`
- Dashboard v1 com MSC live
- Report canónico Portugal (paralelo ao credit report)

---

## Integração com o SONAR schema v15

Extensão ao schema do plano credit:

```sql
-- Nova tabela: monetary_stance_indicators
CREATE TABLE monetary_stance_indicators (
    id INTEGER PRIMARY KEY,
    bc_id TEXT,                    -- 'Fed', 'ECB', 'BoE', 'BoJ', ...
    date DATE,
    layer TEXT,                    -- 'M1', 'M2', 'M3', 'M4'
    indicator TEXT,                -- 'shadow_rate', 'taylor_1993_gap', '1Y_OIS', ...
    value REAL,
    source TEXT,                   -- 'Krippner', 'Wu-Xia', 'FRED', ...
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Nova tabela: monetary_sub_indices
CREATE TABLE monetary_sub_indices (
    id INTEGER PRIMARY KEY,
    bc_id TEXT,
    date DATE,
    ES REAL,  -- Effective Stance [0-100]
    RD REAL,  -- Rule Deviation
    EP REAL,  -- Expected Path
    FC REAL,  -- Financial Conditions
    CS REAL,  -- Credibility Signal
    MSC REAL, -- Composite [0-100]
    dilemma_flag BOOLEAN,
    dilemma_type TEXT  -- 'A', 'B', 'C', 'D' or NULL
);

-- Nova tabela: communication_scores
CREATE TABLE communication_scores (
    id INTEGER PRIMARY KEY,
    bc_id TEXT,
    speaker TEXT,
    date DATE,
    speech_url TEXT,
    hawkishness_score REAL,  -- [-1, +1]
    methodology TEXT,  -- 'keyword', 'finbert', 'llm'
    excerpt_hawkish TEXT,  -- key hawkish phrases
    excerpt_dovish TEXT    -- key dovish phrases
);

-- Nova tabela: policy_decisions
CREATE TABLE policy_decisions (
    id INTEGER PRIMARY KEY,
    bc_id TEXT,
    decision_date DATE,
    rate_before REAL,
    rate_after REAL,
    rate_change_bps INTEGER,
    dissent_count INTEGER,
    surprise_bps REAL,  -- Kuttner-style if available
    statement_url TEXT,
    hawkishness_shift REAL  -- vs previous statement
);
```

---

## Questões abertas para decisão futura

### D1 — Shadow rates live durante non-ZLB
Krippner cobre 7 BCs live; Wu-Xia suspenso. Durante períodos non-ZLB, policy rate ≈ shadow rate. **Recomendação:** usar policy rate como default, Krippner SSR quando disponível, sinalizar quando divergem > 25bps.

### D2 — Output gap source
IMF WEO vs OECD vs AMECO frequently divergem. **Recomendação:** IMF WEO primary (global coverage), AMECO secondary for EA-specific. Flag divergence > 1pp como uncertainty.

### D3 — Communication NLP pipeline
Rule-based vs FinBERT vs LLM. **Recomendação:** v1 rule-based (baseline), v2 FinBERT (melhor accuracy), v3 LLM (production quality mas custo).

### D4 — CDS e institutional market data
Bloomberg/Refinitiv para OIS curves completas vs workarounds gratuitos. **Recomendação:** workarounds até fund institucional, depois Bloomberg.

### D5 — BC coverage
10 BCs principais vs apenas 4-5 para MVP. **Recomendação:** MVP cobre Fed, ECB, BoE, BoJ (essenciais) + PT como proxy EA. Tier 2 adiciona SNB, BoC, RBA, PBoC, Riksbank, Norges.

### D6 — Speech ingestion strategy
Daily scraping vs batch monthly. **Recomendação:** batch semanal (Friday) cobre ~95% de valor, minimiza complexity.

---

## Anexo A · Lista consolidada de URLs e endpoints (monetário-específicos)

| Fonte | Base URL | Auth | Uso principal |
|---|---|---|---|
| Atlanta Fed Wu-Xia | `atlantafed.org/cqer/research/wu-xia-shadow-federal-funds-rate` | Nenhuma | Histórico SSR US |
| Jing Cynthia Wu | `sites.google.com/view/jingcynthiawu/shadow-rates` | Nenhuma | SSR US, EA, UK histórico |
| LJK Krippner | `ljkmfa.com/visitors/` | Nenhuma | SSR live 7 BCs |
| NY Fed r-star | `newyorkfed.org/research/policy/rstar` | Nenhuma | Laubach-Williams r* |
| ECB SDW OIS | `data-api.ecb.europa.eu/service/data/YC` | Nenhuma | EA OIS curves |
| BoE Database | `bankofengland.co.uk/boeapps/database/` | Nenhuma | SONIA, UK yields |
| BoJ Statistics | `boj.or.jp/en/statistics/` | Nenhuma | Japan rates, balance sheet |
| PBoC English | `pbc.gov.cn/en/3688066/index.html` | Nenhuma | China monetary data |
| Fed H.4.1 | `federalreserve.gov/releases/h41/current/` | Nenhuma | Fed balance sheet weekly |
| FOMC SEP | `federalreserve.gov/monetarypolicy/fomcprojtabl*.htm` | Nenhuma | Dot plots |
| Fed speeches | `federalreserve.gov/newsevents/speeches.htm` | Nenhuma | Speech scraping |
| ECB speeches | `ecb.europa.eu/press/key/speeches/html/index.en.html` | Nenhuma | ECB communication |
| IMF WEO | `imf.org/en/Publications/WEO/weo-database` | Nenhuma | Output gap |
| AMECO | `ec.europa.eu/economy_finance/ameco/` | Nenhuma | EU output gap |
| Miranda-Agrippino | `silviamirandaagrippino.com/code-data` | Nenhuma | Policy surprises |

---

## Anexo B · Checklist de setup

### Pré-requisitos (complementar ao plano credit)

- [ ] Python 3.11+ já instalado
- [ ] Packages adicionais: `pdfplumber` (SEP scraping), `beautifulsoup4`, `scrapy`, `transformers` (FinBERT futuro)
- [ ] Storage adicional para speeches archive (~5-10 GB)
- [ ] Schema v14 (crédito) já aplicado — estender para v15 com tabelas monetárias

### Credenciais

- [ ] **FRED API key** — mesma do plano credit, não necessita nova
- [ ] Nenhuma chave adicional para Tier 1

### Verificações iniciais

- [ ] Descarregar última file Krippner de `ljkmfa.com/visitors/` (manual)
- [ ] Download Wu-Xia Excel da Atlanta Fed
- [ ] Testar FRED query para `WXSRUS`, `NFCI`, `T5YIFR`
- [ ] Testar ECB SDW query para yield curve dataset `YC`
- [ ] Scraper test para uma FOMC SEP page

---

## Histórico de versões

| Versão | Data | Autor | Alterações |
|---|---|---|---|
| 0.1 | 2026-04-17 | Hugo + SONAR Research | Draft inicial — 7 camadas funcionais, 3 tiers, 4-week roadmap |

---

**Documento de trabalho interno · 7365 Capital · SONAR Research · Abril 2026**

*Ver também: "SONAR Data Sources Implementation Plan" (ciclo de crédito) — fontes partilhadas BIS, Eurostat, BPStat, FRED, Trading Economics detalhadas nesse documento.*
