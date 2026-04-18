# SONAR v2 · Data sources — Economic cycle (ECS)

> **Layer scope:** L3 indices `E1-activity`, `E2-leading`, `E3-labor`, `E4-sentiment` + L4 `cycles/economic-ecs`.
> **Phase 0 Bloco D1** — rewrite baseado em `D1_coverage_matrix.csv` (2026-04-18) + D0 audit findings.
> **Status:** doc canónico. Substitui v1 (4 272 linhas totais nos 4 docs) com estrutura uniforme 5-source hierarchy.

Documento alinhado com:
- `docs/specs/cycles/economic-ecs.md` (composite ECS = 0.35·E1 + 0.25·E2 + 0.25·E3 + 0.15·E4)
- `docs/specs/indices/economic/E1..E4.md`
- `docs/data_sources/country_tiers.yaml`
- `docs/data_sources/D1_coverage_matrix.csv`
- `docs/data_sources/D0_audit_report.md`

---

## 1. Overview e hierarquia de fontes

### 1.1 Mandato do ciclo

O Economic Cycle Score (ECS) mede o estado do real economy de um país numa escala 0–100. Consome 4 indices L3:

| Index | Peso ECS | Mandato |
|-------|----------|---------|
| E1-activity | 0.35 | GDP growth + Industrial Production + Retail Sales (output corrente) |
| E2-leading | 0.25 | Yield curve slope + OECD CLI + LEI + PMI Manufacturing (forward-looking) |
| E3-labor | 0.25 | Unemployment + Sahm rule + NFP + JOLTS (labor market depth) |
| E4-sentiment | 0.15 | UMich Consumer Sentiment + ESI Economic Sentiment + VIX (sentiment/risk) |

Normalização per spec `conventions/normalization.md`: `clip(50 + 16.67·z_clamped, 0, 100)`.
Aggregation per spec `conventions/composite-aggregation.md` (Policy 1 fail-mode: re-weight proporcional se 1 sub-index missing; require ≥3/4; confidence cap 0.75 quando re-weighted).

### 1.2 Hierarquia de fontes (5 níveis canónicos)

Conforme `docs/specs/conventions/patterns.md` pattern "hierarchy best-of":

```
1. PRIMARY          TE (Trading Economics)
   └── breadth: /country/{c}/indicators — universo T1-T3
2. OVERRIDE T1      FRED (US) / Central banks nativos (EA, UK, JP, ...)
   └── latência + precisão > TE
3. SECONDARY EU     Eurostat / INE (PT) / Bundesbank (DE) / ECB SDW
   └── released data + vintage semanticamente correcto
4. SECONDARY EM     TCMB (Turkey) / BCB (Brazil) / RBI (India) / ...
   └── central bank nativo onde TE gap
5. TERTIARY         OECD CLI / Shiller (CAPE indirect) / scraped alternative
   └── meta/aggregated data fora da breadth TE
```

**Não usadas no ECS:**
- **BIS** — foco em credit/debt (cycle CCCS) + FX (cross-cycle). Nenhuma série económica mapeada para E1-E4.
- **FMP** — D0+D1 confirmaram `/api/stable/` e `/api/v3/` ambos `403 Legacy Endpoint`. Chave pre-2025-08 sem acesso renovado. **Não utilizável** sem upgrade (decisão Hugo; default = parked P2+).
- **Agency scrapes** — parte de F4-positioning, não E4. VIX aparece em E4 mas via FRED.

### 1.3 Critério de escolha primary vs override

Para cada `(index, country, series)` a decisão flui:

```
If country in FRED_NATIVE_SET and series in FRED_CATALOG:
    primary = FRED
elif country == "PT" and series in INE_NATIVE_SET:
    primary = INE_PT
elif country in ECB_EA_SET and series in ECB_SDW:
    primary = ECB_SDW
elif country == "TR" and series in TCMB_CATALOG:
    primary = TCMB (when endpoint recovered — D1 blocker aberto)
elif country in TE_BREADTH_T1_T3:
    primary = TE
else:
    primary = GAP (flag emitido; confidence cap)
```

---

## 2. Country tier coverage

### 2.1 Tabela de cobertura esperada

| Tier | Count | E1 | E2 | E3 | E4 | ECS viável? |
|------|-------|----|----|----|----|------------|
| T1 | 16 | ✓ full | ✓ full | ✓ full | ✓ full | Sim — full confidence |
| T2 | 30 | ✓ full | ~ partial (CLI disponível; LEI não; PMI breadth TE ≥60%) | ✓ full | ~ partial (VIX global proxy; ESI só EA; UMich só US) | Sim — com E4 re-weighted |
| T3 | 43 | ✓ full (TE breadth) | ~ reduzida (CLI OECD coverage ~25 países; PMI ad-hoc) | ✓ full | ✗ — apenas VIX global | Marginal — confidence ≤0.60 |
| T4 | ~110 | ~ degradado (GDP annual only frequent) | ✗ — sem leading data | ~ unemployment only | ✗ | Não — flag `COVERAGE_INSUFFICIENT` |

### 2.2 Países com override nativo (precedence sobre TE)

| Country | Native source | Scope override |
|---------|--------------|----------------|
| US | FRED (St. Louis Fed) | Todos os 4 indices — override total |
| EA | ECB SDW | E2 (ESI), parcial E3 (unemployment) |
| DE | Destatis + Bundesbank | E1 (IP monthly), E3 (labor) |
| FR | INSEE | E1, E3 |
| IT | ISTAT | E1, E3 |
| ES | INE ES | E1, E3 |
| NL | CBS | E1, E3 |
| UK | ONS + BoE | E1, E3 |
| JP | e-Stat + MIC | E1 (Tankan separado), E3 |
| CA | StatCan | E1, E3 |
| AU | ABS | E1, E3 |
| NZ | Stats NZ | E1 |
| CH | SECO + BFS | E1, E3 |
| NO/SE | SSB / SCB | E1 |
| PT | **INE PT** (home market) | E1, E3, E4 (indicador de confiança) |
| TR | TCMB (EVDS) | E1 (GDP), E3 (unemployment) — **bloqueado D1** |

### 2.3 Degradação T4

Para países T4 ECS **não é operacional** em MVP. Fluxo:
- Fixture `ecs_components` recebe `NULL` para E2+E4 → Policy 1 re-weight requer ≥3/4 → **fail**.
- Output pipeline emite `ECS = NULL, flags = [COVERAGE_INSUFFICIENT, T4_DEGRADED]`.
- Rationale: T4 scope é rating-spread + CRP apenas (per `country_tiers.yaml`).

---

## 3. Endpoints por fonte

### 3.1 TE — Trading Economics

**Base:** `https://api.tradingeconomics.com`
**Auth:** query param `c={TE_API_KEY}` (chave em `.env`; formato `XXXX:YYYY` mixed-case; **não** OAuth).
**Format:** `f=json` (default XML — sempre passar explicit).
**Plano actual:** indeterminado (Hugo a confirmar); D0 confirmou acesso a 75+ countries breadth.

| Consumer | Endpoint | Rate budget | Cache policy |
|----------|----------|-------------|--------------|
| E1-activity GDP QoQ | `/country/{c}/indicators` filter `Category=GDP` | 1 call per country per 24h | 24h TTL |
| E1-activity Industrial Production | `/country/{c}/indicators` filter `Category=Business` subfilter IP | 1 call per country per 24h | 24h TTL |
| E1-activity Retail Sales | `/country/{c}/indicators` filter `Category=Consumer` | 1 call per country per 24h | 24h TTL |
| E2-leading PMI Manufacturing | `/country/{c}/indicators` filter `Category=Business` subfilter PMI | 1 call per country per 24h | 24h TTL |
| Historical (backfill) | `/historical/country/{c}/indicator/{indicator_name}` | 1 call per series per backfill run | permanent — immutable vintage |

**CategoryGroup relevantes para ECS:**
- `GDP` → E1
- `Business` → E1 (IP) + E2 (PMI)
- `Consumer` → E1 (Retail) + E4 (sentiment indices)
- `Labour` → E3 (unemployment, NFP proxy para non-US)
- `Markets` → E4 (VIX, via index historical)

**Padrão de consumo preferido** (per D0 finding TE-A01 3 492 rows 75 categories para PT):
1. 1× call `/country/{c}` daily → extract latest values para todos os indicators (3 492 rows single response, 450 kB).
2. 1× call `/country/{c}/indicators?g=<group>` quando precisamos filtrar por categoria especifica.
3. Historical series só via `/historical/country/{c}/indicator/{name}` on-demand ou semanal backfill.

Ver D0 §7 para findings complete.

### 3.2 FRED — Federal Reserve Economic Data (St. Louis Fed)

**Base:** `https://api.stlouisfed.org/fred`
**Auth:** query param `api_key={FRED_API_KEY}`
**Format:** `file_type=json`
**Rate limit:** 120 req/min (ample).

| Consumer | Series ID | Frequency | Release latency |
|----------|-----------|-----------|-----------------|
| E1 US GDP QoQ | `GDP` (nominal), `GDPC1` (real chained 2017 USD) | Quarterly | ~30d after quarter end |
| E1 US Industrial Production | `INDPRO` | Monthly | ~15d |
| E1 US Retail Sales | `RSAFS` | Monthly | ~15d |
| E2 yield slope 10Y-2Y | `T10Y2Y` (pre-computed) | Daily | ~1d |
| E2 OECD CLI US | `OECDLOLITOAASTSAM` | Monthly | ~110d (**DEPRECATED per D2 2026-04-18** — série parou 2022-11; usar OECD direct) |
| E2 LEI proxy | `USSLIND` (Philly Fed State Leading Index — **DESCONTINUADO 2020** per D2) | Monthly | — (GAP; `CAL-023`) |
| E2 ISM PMI mirror | `NAPMMPI` (**descontinuado** FRED; usar ISM direct) | — | — |
| E3 US Unemployment | `UNRATE` | Monthly | ~5d after jobs report |
| E3 Sahm Rule | `SAHMREALTIME` (FRED-computed) | Monthly | ~5d |
| E3 NFP | `PAYEMS` (total nonfarm) | Monthly | 1st Friday |
| E3 JOLTS openings | `JTSJOL` | Monthly | ~45d lag |
| E4 UMich sentiment | `UMCSENT` | Monthly | ~25d (preliminary mid-month, final month-end) |
| E4 VIX | `VIXCLS` | Daily | Real-time (prev close) |

**Observation endpoint pattern:**
```
GET /series/observations?series_id={ID}&api_key={K}&file_type=json
    &observation_start=YYYY-MM-DD&observation_end=YYYY-MM-DD
```

**Metadata endpoint** (para descoberta):
```
GET /series?series_id={ID}&api_key={K}&file_type=json
```

### 3.3 OECD — Composite Leading Indicators

**Base:** `https://stats.oecd.org/SDMX-JSON/data/`
**Auth:** none (public).
**Format:** SDMX-JSON.

**Pattern:**
```
GET /MEI_CLI/LOLITOAA.{COUNTRY}.M/all?startTime=YYYY-MM&endTime=YYYY-MM
```
Onde `{COUNTRY}` é código OECD 3-letter (`USA`, `DEU`, `FRA`, `PRT`, ...). Lista completa via endpoint estrutural `SDMX-JSON/dimension/MEI_CLI/`.

**Coverage real:** ~35 countries (M36/G20 + selecionados). T1 cobertura total; T2 parcial; T3 reduzida.

**FRED mirror** (`OECDLOLITOAASTSAM`): DEPRECATED — D2 empirical (2026-04-18) confirma série stale desde 2022-11 (1 264d lag). Usar OECD direct SDMX-JSON 2.0 como primary.

### 3.4 ECB SDW — Statistical Data Warehouse

**Base:** `https://data-api.ecb.europa.eu/service/data`
**Auth:** none (public).
**Format:** query param `format=jsondata` (SDMX-JSON) or default XML.

| Consumer | Dataflow | Key pattern | Notes |
|----------|----------|-------------|-------|
| E4 ESI Economic Sentiment (EA) | `ESI` (DG ECFIN) | `M.{country}.Z.ESI.Z` | Monthly; EA aggregate + members |
| E3 EA Unemployment | `STS` + `UNE_RT_M` | `M.{country}.LTR.TOTAL.PC_ACT.NSA.LTU` | Eurostat mirror |

**Rate limit:** undocumented; comportamento polite (1 req/sec). Public dataset — use liberal.

### 3.5 Eurostat (direto)

**Base:** `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data`
**Auth:** none.
**Format:** JSON-Stat.

| Consumer | Dataset | Notes |
|----------|---------|-------|
| E4 ESI alternativo | `ei_bssi_m_r2` | DG ECFIN confidence indicators |
| E3 Unemployment | `une_rt_m` | Monthly harmonised |
| E1 IP | `sts_inpr_m` | Industrial Production idx |

### 3.6 INE PT — Instituto Nacional de Estatística (Portugal)

**Base:** `https://www.ine.pt/ine/xportal/xmain?xpid=INE&xpgid=ine_indicadores`
**Auth:** none (public data service).
**Format:** JSON via `web_api/data/indicador` path.

| Consumer | Indicador | Notes |
|----------|-----------|-------|
| E1 PT GDP QoQ | `0011725` (PIB em volume) | Quarterly; flash estimate + final |
| E1 PT IP | `0000997` | Monthly |
| E1 PT Retail Sales | `0009099` (IVC) | Monthly |
| E3 PT Unemployment | `0000976` | Monthly (ILO method) |
| E4 PT Consumer Confidence | `0009122` | Monthly |

**Path:** para descoberta sistemática ver INE catalog search endpoint — backlog item P2-013.

### 3.7 TCMB EVDS — Turkey

**Status D1:** **BLOCKED**. D0+D1 discovery (10 calls) retornaram HTML SPA homepage em todas as variantes testadas (key em header, key em URL param, key em canonical path-style, canonical com aggregationTypes, `/EVDS/service/*` alternative root, `/serieList`, `/categories`, `/datagroups`). Nenhuma combinação URL+auth produziu JSON.

**Endpoint (por docs):**
```
GET https://evds2.tcmb.gov.tr/service/evds/series={code}-{code2}&startDate=DD-MM-YYYY&endDate=DD-MM-YYYY&type=json
Authorization: via header `key: {TCMB_API_KEY}`
```

**Series relevantes (quando endpoint recuperado):**
- E1 Turkey GDP: `TP.YSKGSYH.F`
- E1 Turkey IP: `TP.SABS*` family
- E3 Turkey unemployment: `TP.ISSIZLIK`

**Mitigação actual:** para Turkey usar TE primary (`/country/turkey/indicators`) — breadth completa confirmada D0. Bloqueio nativo não afecta MVP (Turkey é T2; TE breadth suficiente).

**Backlog:** escalate Hugo → pedir TCMB support OU ler PDF docs EVDS v1.9 completo para descobrir URL pattern correto. Item `CAL-018` (Phase 4).

### 3.8 Shiller — Online data (Yale)

**Base:** `http://www.econ.yale.edu/~shiller/data/ie_data.xls`
**Auth:** none. Static XLS file.
**Relevância ECS:** apenas VIX via F3/E4 cross-reference (CAPE é F1-valuations, não E4).

---

## 4. Série catalog — por index

Legenda: `Pri` = primary recommendation; `Ovr` = override Tier 1; `Freq` = frequency; `Lat` = release latency (dias); `Spec` = consumer spec canónico.

### 4.1 E1 — Activity

| Série | Pri | Ovr | Freq | Lat | Spec § |
|-------|-----|-----|------|-----|--------|
| `gdp_qoq` | TE `/country/{c}/indicators` (Cat=GDP) | FRED `GDP/GDPC1` (US); INE `0011725` (PT); TCMB `TP.YSKGSYH.F` (TR) | Q | 30 | E1 §2.1 |
| `industrial_production` | TE `/country/{c}/indicators` (Cat=Business) | FRED `INDPRO` (US); INE `0000997` (PT) | M | 15 | E1 §2.2 |
| `retail_sales` | TE `/country/{c}/indicators` (Cat=Consumer) | FRED `RSAFS` (US); INE `0009099` (PT) | M | 15 | E1 §2.3 |

**Computation:**
- `gdp_qoq_annualized = ((gdp_q / gdp_q_1)^4 - 1) × 100` (US BEA convention).
- `ip_yoy = (ip_m / ip_m_12) - 1`.
- `retail_yoy = (rsafs_m / rsafs_m_12) - 1` (aplicar deflator CPI se nominal).

**Edge cases** (per E1 spec §6): vintage revisions (backfill reload 3 vintages Q→Q-1→Q-2); quarter straddle detection; holiday-adjusted months.

### 4.2 E2 — Leading Indicators

| Série | Pri | Ovr | Freq | Lat | Spec § |
|-------|-----|-----|------|-----|--------|
| `yield_curve_slope_10y_2y` | FRED `T10Y2Y` (US pre-computed); derived from NSS overlay (other countries) | — | D | 1 | E2 §2.1 |
| `oecd_cli` | OECD SDMX `MEI_CLI/LOLITOAA.{C}.M` (SDMX-JSON 2.0) | — (FRED `OECDLOLITOAASTSAM` DEPRECATED per D2) | M | ~110 | E2 §2.2 |
| `lei_conference_board` | SCRAPE Conference Board (US only — paywall) | GAP per D2 — `USSLIND` descontinuado 2020; `CAL-023` alternative | M | — | E2 §2.3 |
| `pmi_manufacturing` | TE `/country/{c}/indicators` subfilter PMI | FRED `NAPMMPI` (**deprecated** — descontinuado 2017); ISM direct scrape (backlog) | M | 2 | E2 §2.4 |

**Computation slope:** feed da overlay `nss-curves` (ver `monetary.md §4.2` — NSS emits smooth curve; ECS consome ponto 10Y - 2Y).

**LEI status:** Conference Board LEI full (US) é paywalled desde ~2020 (membership). Proxy antigamente viable via `USSLIND` (Philly Fed state leading index) DESCONTINUADO 2020 per D2 empirical (2026-04-18). US E2 LEI = GAP actual — CAL-023 pendente (alternatives: Philly Fed ADS index `USPHCI`, Conference Board scrape paid, ECRI Weekly Leading Index scrape). Marker `BLOCKING` update per next CSV revision.

**PMI**: TE breadth confirma PMI Manufacturing headline para 60+ countries. Sub-components (New Orders, Employment, Prices) geralmente paywalled S&P Global — Phase 2 backlog P2-007.

### 4.3 E3 — Labor Market Depth

| Série | Pri | Ovr | Freq | Lat | Spec § |
|-------|-----|-----|------|-----|--------|
| `unemployment_rate` | TE `/country/{c}/indicators` Cat=Labour | FRED `UNRATE` (US); Eurostat `une_rt_m` (EA); TCMB `TP.ISSIZLIK` (TR) | M | 5 | E3 §2.1 |
| `sahm_rule_triggered` | FRED `SAHMREALTIME` (US only direct) | Derived locally: `sahm = UR_3mo_avg - min(UR_3mo_avg, trailing_12m)` | M | 5 | E3 §2.2 |
| `nfp_change` | TE `/country/us/indicators/non-farm-payrolls` | FRED `PAYEMS` first-diff (US only) | M | 2 | E3 §2.3 |
| `jolts_openings` | FRED `JTSJOL` (US only) | — | M | 45 | E3 §2.4 |

**US-specific scope:** NFP + JOLTS + Sahm são US-only por design — E3 spec §3 tolera missing para non-US (re-weight remaining 2/4 sub-components).

**Sahm rule trigger:** `sahm ≥ 0.50 pp → recession signal` (Claudia Sahm 2019 methodology). Spec E3 §4 requires realtime feed (retroactively revised vintages não usáveis).

### 4.4 E4 — Sentiment

| Série | Pri | Ovr | Freq | Lat | Spec § |
|-------|-----|-----|------|-----|--------|
| `umich_sentiment` | FRED `UMCSENT` (US primary) | TE `/country/us/indicators` Cat=Consumer subfilter Michigan | M | 25 | E4 §2.1 |
| `esi_economic_sentiment` | ECB SDW `ESI.M.{C}.Z.ESI.Z` | Eurostat `ei_bssi_m_r2` | M | 25 | E4 §2.2 |
| `vix_index` | FRED `VIXCLS` (daily close) | TE `/markets/historical/VIX:IND` | D | 1 | E4 §2.3 (cross-ref F3) |

**VIX dual role:** primário para F3-risk-appetite (financial cycle) + secundário para E4 (sentiment proxy global quando UMich/ESI indisponíveis). Single raw load; ambos cycles consomem de `markets_timeseries` table.

---

## 5. Fallback hierarchy

### 5.1 Árvore de decisão por série

```
Para cada (series, country):
    1. IF country has native_connector AND series in native_catalog:
         → native (FRED / INE PT / ECB SDW / TCMB / ...)
    2. ELIF country in TE_breadth AND series covered in TE:
         → TE /country/{c}/indicators
    3. ELIF series has global_fallback (e.g. VIX global, OECD CLI):
         → global source
    4. ELSE:
         → emit flag {SERIES}_{COUNTRY}_MISSING; index consumes degraded
```

### 5.2 Exemplos concretos (6 células)

| Série × Country | Primary | Fallback | Flag se ambos faltam |
|-----------------|---------|----------|----------------------|
| `gdp_qoq × US` | FRED `GDPC1` | TE `/country/us/indicators` | `GDP_US_MISSING` |
| `gdp_qoq × PT` | INE `0011725` | TE `/country/portugal/indicators` | `GDP_PT_MISSING` |
| `gdp_qoq × TR` | TE (TCMB blocked) | — | `GDP_TR_MISSING` |
| `gdp_qoq × BR` | TE `/country/brazil/indicators` | BCB SGS (Phase 2+) | `GDP_BR_MISSING` |
| `unemployment × EA` | ECB SDW `STS/UNE_RT_M` | Eurostat direct | `UNR_EA_MISSING` |
| `vix × any` | FRED `VIXCLS` | TE `/markets/VIX:IND` | `VIX_MISSING` (global) |

### 5.3 Override conditions

Per CSV column `override_condition`:

- **FRED US override:** sempre activo para US quando série em FRED catalog (latência menor + revisões vintage nativas).
- **INE PT override:** activo apenas quando delay TE ≥ 3 dias relative a INE (Portugal é home market — freshness matter).
- **ECB SDW EA override:** activo para EA aggregate (TE reporta only country-level, não aggregate).
- **TCMB TR override:** PARKED — quando endpoint recuperado, activar.

### 5.4 Policy 1 re-weight at composite

Quando sub-index falha (todas sub-séries missing → index = NULL), ECS re-weight:

```
valid_indices = {I where I.score is not None}
if len(valid_indices) < 3: return None  # fail
weights = original_weights[valid_indices] / sum(original_weights[valid_indices])
ECS = sum(w × I.score for I, w in valid_indices)
confidence = min(0.75, base_confidence)  # cap
```

Ver `docs/specs/conventions/composite-aggregation.md` Policy 1.

---

## 6. Known gaps e backlog items

### 6.1 Gaps críticos (BLOCKING na matrix)

| Gap | Impacto | Mitigação curto-prazo | Backlog item |
|-----|---------|----------------------|--------------|
| TCMB endpoint indisponível | E1+E3 Turkey sem path nativo | TE breadth suficiente; flag `TCMB_NATIVE_MISSING` informativo | `CAL-018` |
| Conference Board LEI paywall | E2 US LEI sem path directo | GAP — `USSLIND` descontinuado 2020 per D2; alternatives pendentes | `CAL-023` + `P2-007` |
| S&P Global PMI sub-components paywall | E2 PMI só headline | Usar headline; sub-comps Phase 3+ | `P2-007` |
| OECD CLI country coverage | E2 ~T2+ parcial; T3 sem CLI | Re-weight E2 sem CLI | `P2-009` (multi-source LEI composite) |

### 6.2 Gaps de qualidade (CORE na matrix)

| Gap | Descrição | Mitigação |
|-----|-----------|-----------|
| TE categoria inconsistente cross-country | Category "Business" contém IP+PMI+Capacity misturado | Filtro textual em indicator_name (não robusto) → backlog `P2-010` refactor TE normalization |
| FRED revisão vintage | PAYEMS revisto mensalmente 2 prior months | Backfill 3 vintages + snapshot por vintage | Coberto em `conventions/methodology-versions.md` (spec E3) |
| Shiller CAPE disponibilidade offline | ie_data.xls às vezes 404 (Yale server) | Local cache 24h + staleness alert | Spec `erp-daily` §7 (financial.md) |

### 6.3 Out-of-scope Phase 0 / Phase 1

Por decisão explícita (ver `ROADMAP.md`):

- **Alternative data** (Google Trends, satellite, credit card, mobility) — roteado para Phase 2 `P2-003`.
- **Nowcasting models** (GDPNow, NY Fed Nowcast, Atlanta Fed) — Phase 3 `P2-011` (ECS cross-validation). MVP usa released quarterly GDP sem nowcasting overlay.
- **PMI sub-components** — Phase 3 `P2-007`.
- **Survey data granular** (UMich sub-items; Conference Board consumer confidence components) — Phase 3.

### 6.4 Calibration tasks dependentes

Ver `docs/backlog/calibration-tasks.md`:

- `CAL-002` — lookback economic 10Y confirm para µ/σ z-score (baseline; revisar quando história real disponível).
- `CAL-003` — weights E1 0.35 / E2 0.25 / E3 0.25 / E4 0.15 empirical validation (out-of-sample H2 2026).
- `CAL-018` — TCMB endpoint recovery.

---

## 7. Licensing status

| Fonte | Licença | Uso permitido | Observações |
|-------|---------|--------------|-------------|
| TE | Commercial (tier a confirmar Hugo) | Internal-only per TE TOS; redistribution proibida | **Pending Hugo:** plan tier (Basic/Standard/Premium?) |
| FRED | Public domain (Fed policy) | Sem restrições | ✓ safe |
| OECD CLI | CC-BY-4.0 | Redistribution com atribuição | ✓ safe |
| ECB SDW | Re-use condições ECB (similar CC-BY) | Attribution required | ✓ safe |
| Eurostat | Eurostat re-use (CC-BY-4.0 equivalente) | Attribution "Source: Eurostat" | ✓ safe |
| INE PT | Open Data PT (CC-BY-compatible) | Attribution "Fonte: INE PT" | ✓ safe |
| TCMB EVDS | Free for academic/research; commercial unclear | Pending docs review | Escalate Hugo se commercial use |
| Shiller (Yale) | Academic free-use | Attribution "Shiller, R. Yale" required | ✓ safe |
| Conference Board LEI | Proprietary (paywalled) | **Não redistribuir** | Usar Philly Fed proxy |

**Stance editorial 7365 Capital:** todas séries feed em outputs públicos (reports) citam fonte. Outputs internos (dashboard, signals) operam dentro ToS TE.

---

## 8. Cross-refs

### 8.1 Specs consumer

- `docs/specs/indices/economic/E1-activity.md` — consumidor principal de §4.1.
- `docs/specs/indices/economic/E2-leading.md` — consumidor principal de §4.2.
- `docs/specs/indices/economic/E3-labor.md` — consumidor principal de §4.3.
- `docs/specs/indices/economic/E4-sentiment.md` — consumidor principal de §4.4.
- `docs/specs/cycles/economic-ecs.md` — composite L4 (consome E1-E4).

### 8.2 Outros cycles que leem E* sub-indices cross-cycle

- `docs/specs/cycles/credit-cccs.md` §5 — CCCS cross-cycle reads ECS trend (early warning).
- `docs/specs/cycles/monetary-msc.md` §5 — MSC consulta E1 GDP via r* gap (M2).
- `docs/specs/cycles/financial-fcs.md` §5 — FCS lê E4 VIX (shared series).

### 8.3 Overlays que partilham séries

- `docs/specs/overlays/nss-curves.md` — NSS emite yield curve; E2 consome slope 10Y-2Y (derived).
- `docs/specs/overlays/expected-inflation.md` — consume CPI; E1/E3/E4 não consomem directo mas mesma fonte TE (evitar double-call via cache).

### 8.4 Conventions

- `docs/specs/conventions/normalization.md` — fórmula score.
- `docs/specs/conventions/composite-aggregation.md` — Policy 1 re-weight.
- `docs/specs/conventions/flags.md` — flags emitidos por este doc: `GDP_{C}_MISSING`, `UR_{C}_MISSING`, `PMI_HEADLINE_ONLY`, `TCMB_NATIVE_MISSING`, `COVERAGE_INSUFFICIENT`, `T4_DEGRADED`.
- `docs/specs/conventions/methodology-versions.md` — vintage management.

### 8.5 Architecture

- `docs/ARCHITECTURE.md` §L0-L4 — layer contracts.
- `docs/adr/ADR-0002-nine-layer-architecture.md` — rationale.
- `docs/adr/ADR-0003-db-path-sqlite-postgres.md` — storage contract para timeseries table `e_indices`.

### 8.6 Governance e backlog

- `docs/governance/DATA.md` — data handling rules.
- `docs/backlog/calibration-tasks.md` — `CAL-002`, `CAL-003`, `CAL-018`.
- `docs/backlog/phase2-items.md` — `P2-003`, `P2-007`, `P2-009`, `P2-010`, `P2-011`, `P2-013`.
- `docs/data_sources/D0_audit_report.md` — TE/FRED/FMP/TCMB smoke findings.
- `docs/data_sources/D1_coverage_matrix.csv` — matrix canónica.
- `docs/data_sources/country_tiers.yaml` — tier assignments.

---

*Última revisão: 2026-04-18 (Phase 0 Bloco D1 rewrite).*
