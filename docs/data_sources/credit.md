# SONAR · Plano de Fontes de Dados para Implementação

> **Documento de referência técnica** · 7365 Capital · Abril 2026
> Framework: Manual do Ciclo de Crédito (6 partes, 20 capítulos)
> Contexto: extensão de fontes para além da API Trading Economics já em uso

---

## Objetivo deste documento

Mapear **todas as fontes de dados** necessárias para operacionalizar o framework descrito no manual, além da API Trading Economics já existente. Para cada fonte: o que fornece, como aceder, nível de criticidade, e integração no sistema.

O documento está organizado em **8 camadas funcionais** que espelham a arquitetura do SONAR, seguidas por um plano de implementação em **3 tiers** de prioridade.

---

## Sumário executivo

| Aspeto | Conclusão |
|---|---|
| Cobertura Tier 1 | **100% gratuito**, cobre 80% do framework |
| Chaves adicionais necessárias | Apenas FRED API key (grátis, 5 min de registo) |
| Bloqueadores | Nenhum para MVP; institucionais só para v2+ |
| Tempo estimado MVP | 4 semanas (roadmap na secção final) |
| Custo Tier 1 | €0 (fontes públicas) |
| Custo Tier 3 (opcional) | €60-80k/ano (Bloomberg + Preqin + S&P) |

---

## Camada 1 · Dados de crédito · Núcleo do framework

Esta é a camada sem a qual o SONAR não existe. A `Trading Economics` cobre superficialmente, mas há três fontes primárias que trazem profundidade que a TE não tem.

### 1.1 BIS Data Portal · `data.bis.org`

Fonte oficial e obrigatória para credit-to-GDP gaps, DSR e property prices. A TE reporta muitos destes indicadores, mas quase sempre secundariamente e sem granularidade BIS (breakdown households vs corporates, Q-series vs F-series, séries vintage vs revised).

**Acesso técnico:**
- SDMX REST API v2
- Gratuito, sem API key, sem rate limits publicados
- Formatos: JSON, XML, CSV
- Endpoint base: `https://stats.bis.org/api/v2/data/`
- Documentação: `https://stats.bis.org/api-doc/v2/`

**Datasets-chave para o SONAR:**

| Dataset | Conteúdo | Uso no SONAR |
|---|---|---|
| `WS_TC` | Total credit to PNFS, credit-to-GDP ratios, credit gaps | Cap 7, Cap 8 (L1, L2) |
| `WS_DSR` | Debt service ratios (32 países, breakdown HH/Corp) | Cap 10 (L4) |
| `WS_SPP` | Residential property prices (60+ países) | Cap 14 (housing) |
| `WS_CBPOL` | Central bank policy rates | Ciclo monetário |
| `WS_LBS` | Locational banking statistics | Shadow banking proxy |
| `WS_DEBT_SEC2` | Debt securities issuance | Non-bank credit |
| `WS_XRU` | Effective exchange rates | Currency conditioning |

**Criticidade: ESSENCIAL.** Todo o Cap 7, 8, 10 depende destes dados. O credit gap BIS com λ=400k é literalmente o benchmark regulatório de Basileia III, não uma aproximação. A fórmula DSR Drehmann-Juselius tem 32 países pré-computados no BIS — reconstruí-la a partir de inputs TE é possível mas perde fidelidade.

**Exemplo de chamada:**
```
GET https://stats.bis.org/api/v2/data/BIS,WS_TC,1.0/
    Q.PT.P.A.M.770.A?
    startPeriod=1990-Q1&
    endPeriod=2026-Q1&
    format=jsondata
```

---

### 1.2 ECB Statistical Data Warehouse · `data.ecb.europa.eu`

Fonte autoritativa para toda a euro area. Contém o que nenhuma outra base tem: a **Bank Lending Survey** (BLS) por país, harmonizada, publicada 2-3 semanas após o final do trimestre.

**Acesso técnico:**
- SDMX 2.1 REST API
- Gratuito, sem API key
- Endpoint base: `https://data-api.ecb.europa.eu/service/data/`
- Documentação: `https://data.ecb.europa.eu/help/api/overview`

**Datasets-chave:**

| Dataset | Conteúdo | Uso no SONAR |
|---|---|---|
| `BLS` | Bank Lending Survey (standards, demand, factors) | Cap 11 (QS sub-index) |
| `BSI` | Monetary aggregates (M1, M2, M3), bank credit | Cap 7 cross-check |
| `MIR` | MFI interest rates por segmento e maturidade | Cap 10 (input para DSR) |
| `FCI` | Financial conditions indicators | Cap 17 (ciclo financeiro) |
| `RPP` | Residential property prices harmonizadas 27 EU + UK | Cap 14 (housing EU) |
| `IVF` | Investment fund statistics | Shadow banking EU |
| `FM` | Financial markets (yields, spreads) | Cap 12 cross-check |

**Criticidade: ESSENCIAL para Portugal e Cluster 2.** O Cap 11 inteiro sobre surveys depende disto para cobertura EU. A TE tem alguns dados ECB mas não o BLS — isso é ECB-native.

---

### 1.3 FRED · `api.stlouisfed.org`

Repositório mais completo de dados americanos. Valor indispensável pela curadoria: séries como **Wu-Xia shadow rate** ou **Excess Bond Premium (Gilchrist-Zakrajšek)** não existem em mais lado nenhum.

**Acesso técnico:**
- REST API v2 (v1 ainda funcional)
- Gratuito mas **requer API key desde Novembro 2025**
- Registo em `fredaccount.stlouisfed.org` (5 minutos, gratuito)
- Rate limit: 120 requests/minuto
- Python wrapper: `fredapi` (PyPI)
- Endpoint base: `https://api.stlouisfed.org/fred/`

**Séries-chave para o SONAR:**

| Série ID | Conteúdo | Uso no SONAR |
|---|---|---|
| `DRTSCILM` | SLOOS net % tightening C&I loans large firms | Cap 11 (QS) |
| `DRTSCLCC` | SLOOS tightening credit cards | Cap 11 |
| `BAMLH0A0HYM2` | ICE BofA US HY OAS | Cap 12 (MS) |
| `BAMLC0A0CM` | ICE BofA US IG OAS | Cap 12 (MS) |
| `BAMLEMCBPIOAS` | EM corporate OAS | Cap 12 (EM) |
| `T10Y3M` | Yield curve spread 10Y-3M | Cap 17 (econ cycle) |
| `DFII10` | 10Y real yield (TIPS) | Ciclo monetário |
| `NFCI` | Chicago Fed National FCI | Cap 17 (cross-check) |
| `ANFCI` | Chicago Fed Adjusted NFCI | Cap 17 |
| `EBPNEW` | Excess Bond Premium (Gilchrist-Zakrajšek) | Cap 12 refinement |
| `DGS2`, `DGS10` | Treasury yields | Curve analysis |
| `WALCL` | Fed balance sheet | Ciclo monetário |
| `DRSFRMACBS` | US delinquency rate real estate | Cap 13 (NPL US) |

**Criticidade: ESSENCIAL para o módulo US e para séries sintéticas** (shadow rates, excess bond premium). Fed é o epicentro do Global Financial Cycle — impossível modelar ciclos globais sem esta camada.

---

## Camada 2 · Preços de mercado · Credit spreads e CDS

Crítico para o sub-index **MS (Market Stress)** do CCCS. Cap 12 do manual.

### 2.1 ICE BofA indices · via FRED

Os HY OAS e IG OAS estão publicados gratuitamente via FRED como conveniência — a Fed St Louis licenciou-os ao ICE. Atualização diária com lag de 1 dia.

**Séries já cobertas na Camada 1 via FRED** (repetidas aqui para clareza):

| Série | Nome |
|---|---|
| `BAMLH0A0HYM2` | US High Yield OAS |
| `BAMLC0A0CM` | US Investment Grade OAS |
| `BAMLEMCBPIOAS` | EM Corporate OAS |
| `BAMLHE00EHYIOAS` | Euro HY OAS |
| `BAMLCC0A0CMTRIV` | US Corporate Total Return |

**Criticidade: ESSENCIAL, via FRED (gratuito).**

### 2.2 iTraxx Europe / CEMBI / CDX · problema de licenciamento

Os índices de CDS são propriedade de `S&P Global` (adquiriu IHS Markit em 2022) e `ICE`. O acesso real-time requer licença institucional paga.

**Opções caras (institucional):**
- **Bloomberg Terminal** — ~$25k/ano — opção clássica
- **Refinitiv Eikon (LSEG)** — ~$22k/ano — alternativa
- **S&P Market Intelligence** — ~$15k/ano — menor mas útil
- **FactSet** — menos focado em credit

**Alternativa barata:**
Valores de fim-de-dia dos principais tenor spreads (5Y CDX IG, 5Y CDX HY, 5Y iTraxx Main, 5Y iTraxx Crossover) podem ser raspados de:
- Investing.com
- WSJ Markets
- Stooq.com

Sem garantia de qualidade nem cobertura histórica profunda.

**Criticidade: MÉDIA.** O HY OAS (via FRED) já captura o essencial; os CDS adicionam precisão marginal mas não são bloqueadores para MVP.

---

## Camada 3 · Mercados de ações e volatilidade

Para o ciclo financeiro e cross-checks de market stress.

### 3.1 Twelve Data (já tem)

- Cobertura: equity prices, índices, forex, commodities, fundamentals
- Plano Venture: 610 credits/min
- Suficiente para: fechos diários de índices, cotações de ETFs, most equity fundamentals
- Key já ativa: `624f88489cd84146a4ee8d78db3fc01a`

**Criticidade: JÁ RESOLVIDO.**

### 3.2 VIX e term structure

O VIX spot está em FRED (`VIXCLS`). Mas para o ciclo financeiro rigoroso, precisa-se do VIX term structure (VIX, VIX3M, VIX6M) para ver contango/backwardation.

**Fontes alternativas:**
- Yahoo Finance via `yfinance` Python package — gratuito, sem chave, algum risco de instabilidade
- TE — cobertura moderada
- CBOE diretamente — `cboe.com/delayed_quotes` (delayed)

**Criticidade: BAIXA-MÉDIA.** Não bloqueia MVP mas refina v2.

---

## Camada 4 · Housing · Amplificador crítico (Cap 14)

### 4.1 ECB Residential Property Prices (EU harmonizado)

ECB SDW publica `RPP` para 27 países EU harmonizados — cobre Cap 14 integralmente para Portugal e Cluster 2.

**Já na Camada 1.2** via ECB SDW API.

### 4.2 US housing

FRED tem:
- `CSUSHPINSA` — Case-Shiller national
- `USSTHPI` — FHFA
- Sub-indices metropolitanos por ZIP code

**Criticidade: ALTA, via FRED (Camada 1.3).**

### 4.3 Non-EU non-US (UK, CA, AU, JP, CN)

- BIS publica `WS_SPP` para 60+ países, trimestral com lag
- TE cobre mensalmente
- Fontes nacionais: Nationwide UK, Teranet-National Bank Canada, CoreLogic Australia, Japan REIT Association, NBS China

**Criticidade: MÉDIA-ALTA.** Para Portugal e EU é essencial (ECB RPP resolve); para non-EU é BIS + TE.

---

## Camada 5 · Banking sector · NPL, capital, profitability (Cap 13)

### 5.1 EBA Risk Dashboard

Fonte harmonizada EU para NPLs, CET1, coverage ratios, RoE. Publicação trimestral.

**Acesso: PROBLEMA.** A EBA não tem API REST pública. Os dados estão em Excel files no site `eba.europa.eu/risk-and-data-analysis/risk-analysis`.

**Solução:**
- Ingestão via scraping + parsing de xlsx (requer `openpyxl` em Python)
- **Workaround mais elegante:** ECB SDW tem uma versão dos indicators EBA no dataset `SUP_IND`

**Criticidade: MÉDIA.** EBA aggregados via ECB SDW chegam para narrativa macro.

### 5.2 FDIC US banking data

- API REST pública e gratuita
- Endpoint: `banks.data.fdic.gov/api`
- Cobre todos os bancos americanos individualmente
- NPL ratios, Tier 1 capital, RoA agregados e por banco

**Criticidade: ALTA para US.** Gratuito e granular.

### 5.3 SNL Financial / S&P Global (institucional)

Para granularidade bank-level cross-country. Ouro-standard mas caro (~$15-20k/ano).

**Criticidade: BAIXA para SONAR v1.** Granularidade bank-level é luxury.

---

## Camada 6 · Contas nacionais e agregados macro

Base para GDP no denominador do credit ratio, context do ciclo económico, sincronização cross-country.

### 6.1 Eurostat API

- Gratuito, REST API
- Cobre 27 estados EU + UK, EFTA
- SDMX 2.1
- Endpoint: `ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/`
- **É melhor que TE para EU** porque é a fonte original harmonizada

**Datasets-chave:**

| Dataset | Conteúdo | Uso |
|---|---|---|
| `namq_10_gdp` | GDP nominal/real trimestral | Denominador credit ratio |
| `prc_hicp_midx` | HICP consumer prices | Inflação |
| `une_rt_q` | Unemployment rate | Ciclo económico |
| `bop_c6_q` | Current account | Sync cross-country |
| `gov_10q_ggnfa` | Government finance | Fiscal stance |
| `nasq_10_nf_tr` | Household income disposable | DSR denominator |

**Criticidade: ALTA.** Substitui TE para EU com vantagem.

### 6.2 OECD.Stat

Publica Economic Outlook database com forecasts, gaps, output gaps, labour market cross-country harmonizados.

- API REST via SDMX
- Endpoint: `sdmx.oecd.org/public/rest/`
- Gratuito, sem chave

**Datasets:**
- `EO` — Economic Outlook (forecasts)
- `MEI` — Main Economic Indicators
- `QNA` — Quarterly National Accounts

**Criticidade: MÉDIA.** Adiciona depth cross-country e forecasts oficiais.

### 6.3 IMF Data API

- `International Financial Statistics` (IFS)
- `World Economic Outlook` (WEO)
- `Financial Soundness Indicators` (FSI)
- Cobertura global 190+ países
- API SDMX REST
- Endpoint: `dataservices.imf.org/REST/SDMX_JSON.svc/`
- Gratuito, sem chave

**Criticidade: MÉDIA.** Critical para cobertura EM.

---

## Camada 7 · Portugal específico

O SONAR tem ambição nacional, por isso vale a pena fontes dedicadas a Portugal.

### 7.1 Banco de Portugal · BPStat

BPStat (`bpstat.bportugal.pt`) tem **API JSON** (recentemente lançada, 2024).

**Cobertura:**
- Estatísticas monetárias e financeiras
- Balance of payments
- Empréstimos por sector
- NPL doméstico
- **Inquérito aos Bancos sobre o Mercado de Crédito**
- Preços imobiliários

**Acesso:**
- Endpoint: `bpstat.bportugal.pt/data/v1/`
- Gratuito, sem chave
- Formato: JSON

**Criticidade: ALTA.** O `Inquérito aos Bancos sobre o Mercado de Crédito` é único e subutilizado — está exclusivamente aqui. Cap 11.7 do manual identifica isto como ângulo editorial original.

### 7.2 INE · Instituto Nacional de Estatística

- API JSON em `ine.pt/ine/api`
- Dados harmonizados PT:
  - Preços habitacionais (desde 2009)
  - CPI
  - GDP
  - Contas nacionais
  - Mercado de trabalho
- Gratuito

**Criticidade: MÉDIA.** Muito duplica Eurostat mas com frequência mais tempestiva para Portugal.

---

## Camada 8 · Dados alternativos e "dark matter" (Cap 19)

### 8.1 JST Macrohistory Database

- URL: `macrohistory.net/database`
- CSV descarregável
- 18 economias, 1870-2020, 48 variáveis
- Actualização anual
- Sem API mas é estático — ingestão é one-shot
- Licença: livre para uso com atribuição

**Criticidade: ESSENCIAL para validação do framework.** Sem isto, não há forma de testar o classifier em 150 anos de história. É o que dá credibilidade académica.

**Variáveis relevantes para SONAR:**
- `tloans` — total loans
- `tmort` — mortgage loans
- `tbus` — business loans
- `gdp` — GDP nominal
- `hpnom` — house prices nominal
- `ltrate` — long-term rate
- `stir` — short-term rate
- `cpi` — consumer prices
- `debtgdp` — government debt-to-GDP

### 8.2 Private credit tracking

- **Preqin** (institucional, pago ~$20k/ano) — ouro-standard
- **BIS Global Liquidity** reports — parcial, gratuito
- **Bloomberg** — se já tiver

Private credit cresceu de $200bn para $1.7tn entre 2010-24, invisível ao BIS oficial. Cap 19.4 do manual identifica isto.

**Criticidade: BAIXA para v1.** Documentar a limitação é mais honesto que tentar capturar imperfeitamente.

### 8.3 Shadow banking proxies

- FSB (`fsb.org`) publica `Global Monitoring Report on Non-Bank Financial Intermediation` anualmente
- IMF Global Financial Stability Report chapters
- PDF apenas — ingestão manual

**Criticidade: BAIXA.** Anual e PDF-based; incorporar como narrativa, não como série.

---

## Plano de implementação em 3 Tiers

### Tier 1 · MVP do connector

**Característica: 100% gratuito, cobre 80% do framework.**

| # | Fonte | Acesso | Papel no SONAR | Prioridade |
|---|---|---|---|---|
| 1 | BIS SDMX API | Público, sem chave | Credit gap, DSR, property prices | 🔴 Crítica |
| 2 | ECB SDW SDMX | Público, sem chave | BLS, MIR, BSI, RPP para EU | 🔴 Crítica |
| 3 | FRED API v2 | Key grátis obrigatória | SLOOS, HY OAS, IG OAS, shadow rate | 🔴 Crítica |
| 4 | Eurostat API | Público, sem chave | GDP nominal, contas nacionais EU | 🟠 Alta |
| 5 | BPStat API | Público | Inquérito BdP, dados PT específicos | 🟠 Alta |
| 6 | JST Database | Download CSV | Backtest histórico 150 anos | 🟠 Alta |
| 7 | Twelve Data | Key paga (já tem) | Equity, FX, commodities, yields | ✅ Já ativo |

### Tier 2 · Depth cross-country

**Característica: também gratuito, complementa o Tier 1.**

| # | Fonte | Acesso | Papel |
|---|---|---|---|
| 8 | OECD SDMX | Público | Output gaps, forecasts cross-country |
| 9 | IMF Data API | Público | IFS, WEO, FSI para EM coverage |
| 10 | INE PT API | Público | Dados PT alta frequência |
| 11 | FDIC API | Público | Granularidade banking US |
| 12 | Yahoo Finance | via `yfinance` | VIX term structure, cross-check |
| 13 | EBA via ECB SUP_IND | Público | NPL, capital ratios EU harmonizado |

### Tier 3 · Institucional

**Característica: caro, para v2+ ou quando fund institucional lançar.**

| # | Fonte | Custo estimado | Papel |
|---|---|---|---|
| 14 | Bloomberg Terminal | ~$25k/ano | CDS, iTraxx, CDX, commodities depth |
| 15 | Refinitiv Eikon | ~$22k/ano | Alternativa a Bloomberg |
| 16 | S&P Capital IQ | ~$15k/ano | Granularidade bank-level |
| 17 | Preqin | ~$20k/ano | Private credit tracking |
| 18 | SNL Financial | Included S&P | Banking granular cross-country |

---

## Roadmap cronológico (4 semanas para MVP)

### Semana 1 — Setup e ingestão BIS + ECB

- [ ] Registo FRED API key (5 min)
- [ ] Estrutura schema v14 do SONAR incorporando novas fontes
- [ ] Implementar connector BIS SDMX (`WS_TC`, `WS_DSR`, `WS_SPP`)
- [ ] Implementar connector ECB SDW (`BLS`, `MIR`, `BSI`, `RPP`)
- [ ] Ingestão countries: PT, ES, IT, DE, FR, US, UK, CN
- [ ] Testes: valores BIS batem com o que está em `data.bis.org` UI

**Entregáveis:**
- `connectors/bis.py`
- `connectors/ecb_sdw.py`
- Schema v14 SQLite
- ~1.500 séries ingeridas

### Semana 2 — Computação L1-L4

- [ ] Implementar L1: credit-to-GDP stock (dual Q/F series)
- [ ] Implementar L2: credit gap dual HP (λ=400k one-sided) + Hamilton (h=8)
- [ ] Implementar L3: credit impulse Biggs-Mayer-Pick
- [ ] Implementar L4: DSR Drehmann-Juselius fórmula completa + aproximações 1ª/2ª ordem
- [ ] Validação contra dados BIS pré-publicados para os 32 países com DSR

**Entregáveis:**
- `computation/layers.py`
- `computation/filters.py` (HP, Hamilton)
- Backtest report DSR vs BIS published

### Semana 3 — Integração FRED e market data

- [ ] Connector FRED com gestão de key
- [ ] Ingestão SLOOS (`DRTSCILM`), HY OAS, IG OAS
- [ ] Computação sub-indice MS (Market Stress)
- [ ] Computação sub-indice QS (Qualitative Signal)
- [ ] Integração Eurostat para GDP cross-check

**Entregáveis:**
- `connectors/fred.py`
- `connectors/eurostat.py`
- Sub-indices MS, QS computados

### Semana 4 — CCCS e classificador de fases

- [ ] Agregação dos 5 sub-indices no CCCS (pesos 25/30/15/20/10)
- [ ] Classifier de fases (2D stock × flow) com persistence rules
- [ ] Burden override logic
- [ ] Validação contra JST dataset (18 países, 1960-2020, 45 episódios de crise)
- [ ] Backtest: test cases canónicos (US 2003-09, Spain 2003-11, Ireland 2003-12, Japan 1986-95)

**Entregáveis:**
- `computation/cccs.py`
- `computation/classifier.py`
- Backtest report com hit rates
- Dashboard v1 com dados live

---

## Integração com o SONAR schema v14

Proposta de extensão ao schema atual (v13 → v14):

```sql
-- Nova tabela: data_sources
CREATE TABLE data_sources (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,            -- 'bis', 'ecb_sdw', 'fred', ...
    tier INTEGER,                -- 1, 2, 3
    access_type TEXT,            -- 'public', 'key_required', 'institutional'
    base_url TEXT,
    auth_method TEXT,            -- 'none', 'bearer', 'query_param'
    rate_limit_per_min INTEGER,
    last_success_ts TIMESTAMP,
    enabled BOOLEAN DEFAULT 1
);

-- Nova tabela: source_series_mapping
CREATE TABLE source_series_mapping (
    id INTEGER PRIMARY KEY,
    sonar_indicator_id INTEGER,
    source_id INTEGER,
    source_series_key TEXT,      -- ex: 'BAMLH0A0HYM2' ou 'BIS,WS_TC,1.0/Q.PT...'
    priority INTEGER,            -- 1 = primary, 2 = fallback
    transformation TEXT,         -- 'raw', 'yoy', 'zscore_10y', etc
    FOREIGN KEY (source_id) REFERENCES data_sources(id)
);

-- Nova tabela: ingestion_log
CREATE TABLE ingestion_log (
    id INTEGER PRIMARY KEY,
    source_id INTEGER,
    series_key TEXT,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT,                 -- 'success', 'partial', 'failed'
    records_added INTEGER,
    error_msg TEXT,
    FOREIGN KEY (source_id) REFERENCES data_sources(id)
);
```

---

## Questões abertas para decisão futura

### D1 — Preferência Tier 2 vs prioridade MVP
O Tier 2 pode ser ingerido em paralelo ao Tier 1 ou deixado para depois do MVP. **Recomendação:** MVP primeiro, Tier 2 após validação dashboard.

### D2 — CDS pricing
Decidir se vale o investimento em Bloomberg ou se HY OAS via FRED é suficiente para v1. **Recomendação:** FRED suficiente até ter o fund institucional a pagar.

### D3 — EBA ingestão
Scraping de xlsx vs usar ECB SDW `SUP_IND` agregado. **Recomendação:** SUP_IND (mais fácil, suficientemente granular).

### D4 — Update frequency
Cron diário vs weekly vs on-demand? **Recomendação:** Diário para séries diárias (HY OAS, yields, FX); weekly para séries trimestrais (BIS, ECB BLS) — agenda cron inteligente.

### D5 — Data warehousing
Manter SQLite ou migrar para Postgres/TimescaleDB? **Recomendação:** SQLite até 10M records, depois migrar.

---

## Anexo A · Lista consolidada de URLs e endpoints

| Fonte | Base URL | Auth | Docs |
|---|---|---|---|
| BIS | `https://stats.bis.org/api/v2/` | Nenhuma | `stats.bis.org/api-doc/v2/` |
| ECB SDW | `https://data-api.ecb.europa.eu/service/data/` | Nenhuma | `data.ecb.europa.eu/help/api/overview` |
| FRED | `https://api.stlouisfed.org/fred/` | API key | `fred.stlouisfed.org/docs/api/` |
| Eurostat | `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/` | Nenhuma | `ec.europa.eu/eurostat/web/sdmx-web-services/rest-sdmx-2.1` |
| OECD | `https://sdmx.oecd.org/public/rest/` | Nenhuma | `data.oecd.org/api/sdmx-json-documentation/` |
| IMF | `https://dataservices.imf.org/REST/SDMX_JSON.svc/` | Nenhuma | `datahelp.imf.org/knowledgebase/articles/630877` |
| BPStat | `https://bpstat.bportugal.pt/data/v1/` | Nenhuma | BPStat docs site |
| INE PT | `https://www.ine.pt/ine/api/` | Nenhuma | INE API portal |
| FDIC | `https://banks.data.fdic.gov/api/` | Nenhuma | `banks.data.fdic.gov/docs/` |
| Twelve Data | `https://api.twelvedata.com/` | API key (já tem) | `twelvedata.com/docs` |
| JST Macrohistory | `http://macrohistory.net/database/` | Nenhuma | Download directo CSV |

---

## Anexo B · Checklist de setup

### Pré-requisitos

- [ ] Python 3.11+ no ambiente SONAR
- [ ] Packages: `requests`, `pandas`, `sdmx1`, `fredapi`, `openpyxl`, `yfinance`
- [ ] SQLite atual (schema v13) operacional
- [ ] Backup completo da base actual antes de migração v14

### Credenciais a obter

- [ ] **FRED API key** — Registo em `fredaccount.stlouisfed.org` (grátis, obrigatório)
- [ ] (Opcional) Bloomberg access se já tiver via empresa

### Verificações iniciais

- [ ] Testar BIS API com query simples: PT credit gap último trimestre
- [ ] Testar ECB API com BLS PT último trimestre disponível
- [ ] Testar FRED API com HY OAS hoje
- [ ] Testar Eurostat API com GDP PT último trimestre
- [ ] Testar BPStat API com inquérito crédito PT último trimestre

---

## Histórico de versões

| Versão | Data | Autor | Alterações |
|---|---|---|---|
| 0.1 | 2026-04-16 | Hugo + SONAR Research | Draft inicial — 8 camadas, 3 tiers, 4-week roadmap |

---

**Documento de trabalho interno · 7365 Capital · SONAR Research · Abril 2026**
