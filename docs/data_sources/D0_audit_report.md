# D0 Audit Report — Data Sources state + 4-source discovery preview

**Status**: Phase 0 Bloco D sub-bloco D0 · snapshot 2026-04-18
**Scope**: audit inicial de `docs/data_sources/` + smoke tests contra 4 sources primários (TE, FRED, FMP, TCMB)
**Budget consumido**: 15 HTTP requests (pelo limite do briefing)
**Próximos passos**: D1 matriz completa source × spec (depois de resolver gaps FMP + TCMB + decisão arquitetural TE primary)

## 1. Executive summary

- **`docs/data_sources/` state**: 4 ficheiros bootstrap (Apr 17) totalizando 4.272 linhas. Dominados por FRED (143 menções) + BIS + ECB + Eurostat + OECD. **TE tem apenas 74 menções** apesar de ser intended primary source — gap documental vs decisão arquitetural.
- **TCMB + FMP completamente ausentes** em todos os 4 ficheiros. Turkey com 4 menções esporádicas sem plano de coverage.
- **TE smoke tests**: 5/5 calls 200 OK mas **ratings endpoint está 4 anos stale** (latest `2022-09-09`). TE breadth cobre 157 indicators para PT e 137 para TR em single call — valida hipótese breadth-first.
- **FRED smoke**: excelente freshness (DGS10 em T−2) e error handling limpo. Validação da posição "FRED override para US macro".
- **FMP key é legacy tier** — `/api/v3/*` + `/api/v4/*` retornam 403 "endpoint no longer supported". Migração para `/api/stable/*` necessária antes de D1 poder confirmar cobertura.
- **TCMB URL/auth unclear** — `/service/evds/` retorna HTML (SPA homepage), não JSON. Requer descoberta adicional dos endpoints EVDS correctos antes de D1.

## 2. `data_sources/` state

### 2.1 Inventário quantitativo

| File | Lines | Sections | URLs | FRED refs | TE refs | Turkey | TCMB | FMP |
|---|---|---|---|---|---|---|---|---|
| `economic.md` | 1430 | 17 | 1 | 46 | 23 | 1 | 0 | 0 |
| `credit.md` | 607 | 17 | 10+ | 18 | 14 | 0 | 0 | 0 |
| `monetary.md` | 786 | 16 | 0 | 22 | 8 | 0 | 0 | 0 |
| `financial.md` | 1449 | 21 | 3 | 57 | 29 | 3 | 0 | 0 |
| **Total** | **4272** | 71 | ~15 | **143** | **74** | **4** | **0** | **0** |

Timestamp uniforme (Apr 17 23:44) confirma origem bootstrap conjunto, não evolução orgânica.

### 2.2 Completeness assessment

| Dimensão | Estado | Gap |
|---|---|---|
| Source breadth | FRED + BIS + ECB + Eurostat + OECD + Shiller + Damodaran catalogados | TE subutilizado; FMP + TCMB zero |
| Endpoint specificity | Mix — credit.md tem URLs BIS/ECB/FRED; monetary.md zero URLs | URLs não uniformes entre ficheiros |
| Rate limit docs | Implícito (cache + backoff mentioned) | Sem tabela explícita per source |
| Country tiers | Tier 1/2/3/4 doc em economic.md §1.3 + menções cross-files | Não consolidado num único local |
| Auth/licensing | Bloomberg/Refinitiv marked Tier 3 | TE/FMP/TCMB sem licensing notes |
| Freshness targets | Não explícitos | Deve ser spec-level conforme `conventions/flags.md` §STALE |

### 2.3 Stale references detectadas

- `economic.md:252`: "Bloomberg or Refinitiv needed (Tier 3)" — menciona Tier 3 sem referenciar BRIEF §decisão ainda pendente.
- `credit.md:57`: "Cobre todos os bancos americanos individualmente" — referência órfã sem contexto de source.
- Naming: ocorrências de "Trading Economics" (nome completo) vs "TE" (sigla) não normalizadas. TE aparece literalmente em 74 menções distribuídas entre as duas formas.

### 2.4 Rotulagem dos ficheiros actuais

Os 4 ficheiros são **híbridos entre discovery doc e implementation plan** — descrevem sources, prioridades, custos, e implementation approach (tiers, effort estimado) simultaneamente. Decisão D1: separar claramente discovery (inventory + endpoints + coverage) de implementation plan (connector priority, rate limits, caching strategy).

## 3. Endpoint coverage matrix

### 3.1 Overlays (L2)

| Overlay | Primary inputs | TE | FRED | FMP | TCMB | Primary rec |
|---|---|---|---|---|---|---|
| `nss-curves` | Sovereign yields 3M-30Y | `/country/{c}` (Gov Bond indicators) | `DGS*` (US), `IR*` (world) | — | `TP.AKFAT.EUR` (rates) | **TE** breadth; **FRED/BoE/Bundesbank** Tier 1 override |
| `erp-daily` | S&P 500 + earnings + buybacks + CAPE | `/markets/{symbol}` | `SP500` | `/api/stable/...` ? (legacy tier issue) | — | **Shiller + FRED** primary; **FMP** contingent post-migration |
| `crp` | CDS 5Y + vol ratio | `/indicators/credit-rating/` (indirecto) | nenhum CDS | nenhum CDS | nenhum CDS | **WGB scrape** primary (único path sem licensing Markit) |
| `rating-spread` | Rating actions × 4 agências | `te_ratings` spec-referenced fallback (**4Y stale**) | — | — | — | Agency direct primary; TE **inutilizável** para freshness |
| `expected-inflation` | HICP / TIPS / swaps / surveys | `/country/{c}?indicators=Inflation` | `T5YIE`, `T10YIE`, `CPIAUCSL` | — | `TP.FG.J0` (CPI) | **FRED** US; **ECB** EA; **TE** global breadth; **TCMB** Turkey |

### 3.2 Indices (L3) — dominant sources per cycle

| Cycle | FRED role | TE role | FMP role | TCMB role | Principal gap |
|---|---|---|---|---|---|
| Economic (E1-E4) | dominant US | breadth global (GDP, IP, CPI, UR) | — | essencial Turkey | PMI data depth (TE has, FRED has) |
| Credit (L1-L4) | FRED H15 rates | secondary (credit-to-GDP mentioned) | — | `TP.KTP*` credit Turkey | **BIS not in 4 sources** — direct API required |
| Monetary (M1-M4) | dominant (DFEDTAR, FEDFUNDS) | policy rate breadth | — | `TP.AOFOPO03`, `TP.ABK*` | Shadow rate (Krippner, Wu-Xia) direct |
| Financial (F1-F4) | dominant FCI | index levels breadth | **commodities** (CLUSD, GCUSD) post-migration | `TP.DK.USD`, `TP.MK.CUM*` | On-chain crypto (Glassnode), COT (CFTC) |

### 3.3 Cycles (L4)

Consomem L3 + overlays. Sem dependência raw data directa — mapping a fontes é delegado.

### 3.4 Gaps críticos (não cobertos pelos 4 sources)

1. **BIS** — credit-to-GDP, DSR, property gap — núcleo do CCCS + Bubble Warning. API própria: `https://stats.bis.org/api/v2/`. Não no scope D0 mas crítico D1.
2. **CDS sovereign** (TE, FRED, FMP, TCMB não servem) — WGB scrape only free option.
3. **Rating agency feeds directos** — `sp_ratings/moodys_ratings/fitch_ratings/dbrs_ratings` connectors não existem; TE fallback confirmado inviável (stale 4Y).
4. **On-chain crypto** (F3, F4) — Glassnode, Coinglass. Fora dos 4 sources alvo.
5. **CFTC COT** (F4 positioning) — CFTC direct. Fora dos 4 sources.

## 4. Smoke test findings

### 4.1 Per-source summary

| Source | Calls | Success | Status | Observations |
|---|---|---|---|---|
| TE | 5 | 4/5 | 4× 200, 1× 404 expected | Breadth confirmada; **ratings 4Y stale** bloqueia fallback speced |
| FRED | 3 | 2/3 + 1 expected error | 2× 200, 1× 400 clean | Freshness excelente (T−2 DGS10); error handling estruturado |
| FMP | 3 | **0/3** | 3× 403 | Key legacy tier; endpoints `/api/v3/*` + `/api/v4/*` descontinuados |
| TCMB | 2 | **0/2** | 2× 200 mas HTML | URL/auth incorrecta; `/service/evds/` é homepage SPA |
| Extras | 2 | diagnostic | — | Confirmaram natureza dos errors FMP + TCMB |

### 4.2 TE quirks observados

- Campo `LatestValueDate` retorna `2026-12-31` para alguns indicators de PT e TR — sugere **forecast values embedded** no catalog (não só observed data). Implicação: parsing tem de distinguir actuals de forecasts.
- Ratings endpoint retorna campo `Rating` como string (`"BBB+"`, `"Aa1"`) — consistente com `rating-spread` spec.
- Historical endpoint retorna `DateTime` como ISO datetime, não date (quarterly PT GDP: `2024-12-31T00:00:00`) — parsing simples.
- Malformed endpoint retorna **HTML 404** (não JSON error) — connector tem de diferenciar content-type antes de parse.

### 4.3 FRED quirks observados

- Observations endpoint retorna `value` como string (mesmo para numericos: `"4.32"`) — connector tem de converter.
- `realtime_start` / `realtime_end` presentes em todas as responses — vintage tracking built-in.
- Missing values codificados como `"."` (ponto). Connector tem de filtrar.

### 4.4 FMP critical issue

API key retorna `"Error Message": "Legacy Endpoint : Due to Legacy endpoints being no longer supported - This endpoint is only available for legacy users who have valid subscriptions prior August 31, 2025."`

Implicação: key actual é **pré-Aug 31 2025** mas os endpoints `/api/v3/*` + `/api/v4/*` foram descontinuados. Migração para `/api/stable/*` requerida — confirmar se a mesma key funciona no novo namespace antes de commitar FMP role em D1.

### 4.5 TCMB critical issue

URL `https://evds2.tcmb.gov.tr/service/evds/` retorna HTML (homepage SPA) em vez de JSON API response. Duas hipóteses:

1. Path API correcto é diferente (ex: `/service/evds/series/<code>` vs `/service/evds/?series=<code>`).
2. Authentication é OAuth token em header, não API key em query param.

EVDS documentation PDF (https://evds2.tcmb.gov.tr/help/videos/EVDS_Web_Service_Usage_Guide.pdf) precisa review antes de D1 clarificar formato. Alternativas: OECD + BIS + TE para coverage Turkey temporariamente.

## 5. Séries críticas sem cobertura aparente

Catalogadas aqui para priorização D1-D2:

### 5.1 Core pricing primitives

| Série | Spec | Estado |
|---|---|---|
| CDS 5Y sovereign per country | `overlays/crp` | WGB scrape único path free; FMP/TE não servem |
| Inflation swap rates EUR/USD/GBP | `overlays/expected-inflation` | ECB SDW + FRED (US); Bloomberg Tier 3 UK/JP |
| Sovereign linker curves (TIPS, ILGs, OATi) | `overlays/expected-inflation` | FRED + ECB; Bloomberg UK/JP |

### 5.2 Credit cycle structural

| Série | Spec | Estado |
|---|---|---|
| BIS credit-to-GDP ratio + gap (λ=400k) | `indices/credit/L1`, `L2` | BIS direct API (não nos 4 sources) |
| BIS DSR (Drehmann-Juselius) 32 countries | `indices/credit/L4` | BIS direct |
| BIS property price gap | `cycles/financial-fcs` Bubble Warning | BIS direct |

### 5.3 Labour market depth

| Série | Spec | Estado |
|---|---|---|
| Sahm Rule components (3mo avg UR minus 12mo low) | `indices/economic/E3` | FRED derivável; TE passthrough |
| JOLTS (job openings, quits, layoffs) | `indices/economic/E3` | FRED dominant; zero alternativa free |
| Beveridge curve | `indices/economic/E3` | FRED derivável |

### 5.4 Financial positioning

| Série | Spec | Estado |
|---|---|---|
| AAII investor sentiment (retail) | `indices/financial/F4` | AAII direct scrape |
| CFTC COT (institutional futures positioning) | `indices/financial/F4` | CFTC direct |
| FINRA margin debt | `indices/financial/F4` | FINRA direct |
| Flow data (ICI fund flows) | `indices/financial/F4` | ICI direct |

### 5.5 On-chain crypto

| Série | Spec | Estado |
|---|---|---|
| BTC/ETH MVRV, SOPR, NUPL | `indices/financial/F3`, `F4` | Glassnode Tier 2 (paid) |
| Funding rates, open interest | `indices/financial/F3` | Coinglass free-tier possível |

## 6. TE vs nativos — observações preliminares

### 6.1 Breadth wins

TE single call a `/country/{c}` retorna 157 indicators para PT, 137 para TR. FRED exige múltiplas chamadas (series metadata per indicator). **Para coverage multi-country, TE tem vantagem operacional clara**.

### 6.2 Freshness — mixed picture

- TE `historical/country/X/indicator/GDP` latest `2024-12-31` — plausível para quarterly.
- TE `ratings/historical/portugal` latest `2022-09-09` — **4 ANOS stale**. Inutilizável para rating-spread overlay em daily pipeline.
- TE `country/X` com `LatestValueDate = 2026-12-31` — ambíguo (forecasts embedded).
- FRED `DGS10` em T−2 (2026-04-16 observado 2026-04-18) — gold standard freshness.

### 6.3 Implicação arquitetural preliminar

**TE primary is defensible para indicators macros multi-country** (GDP, CPI, UR, retail, IP, etc.). **TE NOT defensible para ratings** (stale) nem para **high-freq rates** (latency operacional, FRED ganha). `rating-spread` spec precisa revisão: "TE fallback" deve ser removido, `sp_ratings/moodys_ratings/fitch_ratings/dbrs_ratings` connectors elevados a primary obrigatórios.

## 7. Recommendations para D1

### 7.1 Prioritization

**P0 (bloqueantes)**:

1. **FMP key migration** — confirmar se key legacy funciona em `/api/stable/*` ou requer nova subscription. Sem isso, FMP role em D1 não pode ser determinado.
2. **TCMB URL discovery** — descobrir endpoint correto EVDS (review PDF docs, possivelmente OAuth). Sem isso, Turkey coverage em D1 fica limitado a TE passthrough.
3. **Decisão TE ratings** — confirmar com Hugo se TE ratings 4Y stale é showstopper (remove de `rating-spread` spec) ou aceitável (fallback em emergência, com flag).

**P1 (importantes)**:

4. **BIS API integration** — adicionar BIS como 5º source primário. É essencial para CCCS (credit-to-GDP, DSR) e FCS (property gap) — sem alternativa.
5. **TE indicators catalog extraction** — correr `/country/{c}` em T1 + T2 countries para gerar mapping completo `indicator_name → spec consumer`.
6. **FRED series canonical list** — enumerar exactamente quais séries FRED cada overlay/index consome; actualmente disperso em specs.

**P2 (nice to have)**:

7. **WGB CDS scrape POC** — validar viabilidade + ethical rate.
8. **Agency rating connectors design** — 4 connectors custom, parseable pages.
9. **AAII / CFTC / FINRA** — scrape-tier connectors para L7+ positioning specs.

### 7.2 Order of attack D1

1. Resolver P0 #1-#3 (FMP, TCMB, TE ratings policy).
2. Expandir scope D1 de 4 sources para **5 sources** (add BIS). Reestimar budget requests.
3. Produzir matriz completa spec × source com anotações `primary`, `override`, `fallback`, `missing`.
4. Rewrite dos 4 files em `docs/data_sources/` separando discovery (catalog) de implementation plan (connectors priority).
5. Entregar D1 como novo commit único (não overwrite D0 audit).

## 8. Open questions para Hugo (decisão antes de D1)

1. **TE ratings 4Y stale** — accepta-se como "informative history, not live fallback" (stripping de `rating-spread` spec fallback reference)? Ou escalamos para ADR novo?
2. **FMP migration** — é aceitável renovar/upgrade subscription para `/api/stable/*` agora (Phase 0), ou adiar para Phase 2+ e aceitar FMP fora do D1 scope?
3. **TCMB** — se URL discovery falhar, aceitas coverage Turkey só via TE passthrough (com `TURKEY_TCMB_FALLBACK` flag) até Phase 1+?
4. **BIS como 5º source primário** — aprova adicionar ao scope Bloco D ou mantém os 4 originais + BIS como separate track?
5. **Scope D1** — budget estimado 30-50 requests across 5-7 sources. Confirma ou ajusta?
6. **Separação docs/data_sources/ em discovery vs implementation** — approva rewrite em D1 ou mantém híbrido actual?
7. **Rename `docs/data_sources/` → ?** — discovery + implementation merit separar em 2 directórios (ex: `docs/data_discovery/` + `docs/data_plans/`)? Ou keep unified?

## 9. Artefactos produzidos D0

- Este ficheiro: `docs/data_sources/D0_audit_report.md`
- `/tmp/smoke_tests.py` — script de smoke tests (15 calls, sem secrets hardcoded; pode migrar para `scripts/` Phase 1+).

## 10. Não produzido (out of scope D0)

- Edits a specs existentes (`docs/specs/overlays/*.md`, etc.) — spec review é **Bloco E**, não D.
- Rewrite dos 4 ficheiros `data_sources/*.md` — é **D1** após resolver open questions.
- Connector design / implementation — **Phase 1+**.
- Rate limit empirical benchmarking — **D2+**.

---

*D0 audit · Phase 0 Bloco D · 2026-04-18*
