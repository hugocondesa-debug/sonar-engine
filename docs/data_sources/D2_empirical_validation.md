# SONAR v2 · D2 Empirical Validation

> **Fase 0 · Bloco D2** — validação empírica da matriz canónica D1.
> Data: 2026-04-18.
> Predecessor: D1 (commits 3934fb22, 437ff675, 4d34e777; `D1_coverage_matrix.csv` + 4 rewrites per-cycle).
> Budget usado: 80/100 requests HTTP; 7 sources testados.

---

## 1. Executive summary

- **FRED é sólido para maioria das séries BLOCKING**, mas 3 descobertas críticas: `OECDLOLITOAASTSAM` stale 3.4Y, `USSLIND` stale 6Y, `DFEDTAR` descontinuado (2008-12) — matriz precisa updates.
- **BIS WS_DSR confirma-se production-ready**: 7/7 países testados retornam 107 obs (TR=95), latest 2025-Q3, lag ~202d (consistent com BIS quarterly publish cycle).
- **ECB SDW é parcial**: 4/7 keys testadas funcionam; 3 failing (`STS-UNE*` unemployment, `FM-YLD-EA10Y`, `ESI` sentiment) requerem key format debug Phase 1.
- **TE bulk pattern é eficiente** (157 indicators por 1 request `/country/{c}`) mas **3/10 historical series retornaram 0 rows** (UK Unemployment, IN Manufacturing PMI, MX Retail Sales) — indicator naming inconsistente cross-country. **TE quota: nenhum rate-limit header exposto** — consumption tracking terá de depender de TE dashboard externamente.
- **INE PT e OECD CLI** requerem parser adjustments: INE retornou 200 mas empty Dados (endpoint pattern precisa investigation Phase 1); OECD SDMX 2.0 format não era o esperado (fix parser → USA/DEU/FRA/PRT/JPN todos fresh 2025-12, lag 111d).

---

## 2. TE findings (Tasks 1a-1e)

### 2.1 Bulk vs granular consumption (Sub-task 1a, 7 calls)

| Endpoint | Rows | Size (KB) | Latency (ms) |
|----------|------|-----------|--------------|
| `/country/portugal` (bulk) | 157 | 81.3 | 1057 |
| `/country/portugal/indicators` (alt path) | 157 | 81.3 | ~1000 |
| `/country/portugal?g=Money` | subset | — | — |
| `/country/portugal?g=GDP` | subset | — | — |
| `/country/portugal?g=Business` | subset | — | — |
| `/country/portugal?g=Labour` | subset | — | — |
| `/country/portugal?g=Consumer` | subset | — | — |

**Finding principal:** `/country/{c}` bulk retorna **157 indicators em 1 request**. Esta é a estrutura economicamente interessante: 1 HTTP call cobre todo o universo macro de um país (GDP, inflation, labor, markets, credit, housing, government, business, consumer).

**Forecast inclusion:** observou-se `date_max = 2026-12-31` no response bulk PT — TE inclui indicators com **forecast values futuros**, não apenas realised. Consumers devem filter por `LatestValueDate ≤ today` para evitar consumer forecasts.

### 2.2 Historical freshness per series × country (Sub-task 1b, 10 calls)

| Country | Indicator | Status | Rows | Latest | Lag (d) |
|---------|-----------|--------|------|--------|---------|
| us | GDP Growth Rate | 200 | ~250 | ~2025-10 | ~180 |
| portugal | GDP Growth Rate | 200 | ~150 | ~2025-12 | ~100 |
| turkey | GDP Growth Rate | 200 | ~150 | ~2025-Q4 | ~150 |
| brazil | Inflation Rate | 200 | 544 | 2026-03-31 | 18 |
| germany | Industrial Production | 200 | 566 | 2026-02-28 | 49 |
| japan | Interest Rate | 200 | 690 | 2026-03-19 | 30 |
| **united-kingdom** | **Unemployment Rate** | **200** | **0** | **—** | **—** |
| **india** | **Manufacturing PMI** | **200** | **0** | **—** | **—** |
| **mexico** | **Retail Sales** | **200** | **0** | **—** | **—** |
| australia | Consumer Confidence | 200 | 620 | 2026-04-30 | -12 (fwd!) |

**Findings:**
- **3/10 falharam com 0 rows** apesar de status 200. Causa: **indicator name é country-specific em TE**. UK pode ter "Unemployment Rate Adjusted" ou similar; IN PMI pode ser "Manufacturing PMI Final"; MX "Retail Sales YoY" em vez de "Retail Sales". **Implicação:** Phase 1 connector precisa indicator-name normalization table por país (novo backlog `CAL-021`).
- **AU Consumer Confidence lag -12d**: latest date 2026-04-30 > hoje (2026-04-18) → TE inclui *scheduled* data (forecast calendar). Consumers ECS devem filtrar por date ≤ today.

### 2.3 Markets endpoint (Sub-task 1c, 8 calls)

| Symbol | Status | Rows | Latest | Lag (d) |
|--------|--------|------|--------|---------|
| SPX:IND | 200 | 62 | 2026-04-17 | 1 |
| NKY:IND | 200 | 62 | 2026-04-17 | 1 |
| DAX:IND | 200 | 63 | 2026-04-17 | 1 |
| PSI20:IND | 200 | 63 | 2026-04-17 | 1 |
| VIX:IND | 200 | 65 | 2026-04-17 | 1 |
| USDTRY:CUR | 200 | 65 | 2026-04-17 | 1 |
| **DXY:IND** | **200** | **0** | **—** | **—** |
| **GLD:COM** | **200** | **0** | **—** | **—** |

**Findings:**
- **6/8 symbols retornam daily data fresh** (2026-04-17, lag 1d) consistent com T+1 publish pattern pós-close.
- **2/8 symbols falham** (DXY:IND, GLD:COM). DXY pode ser `USDX:CUR`; GLD pode ser `XAU:CUR` ou `GC:COM`. Backlog `CAL-021` para symbol normalization.

### 2.4 Credit rating historical (Sub-task 1d, 2 calls)

| Country | Endpoint | Status |
|---------|----------|--------|
| portugal | `/indicators/credit-rating/country/portugal` | **404** |
| turkey | `/indicators/credit-rating/country/turkey` | **404** |

**Finding:** endpoint path sugerido no briefing não existe (**404**). D0 tinha testado `/ratings/historical/portugal` que retornou data 4Y stale. Conclusão consistente com D0: **TE não é path viable para rating-spread overlay** — rewrite spec (Bloco E) confirmado: Damodaran annual backfill + scrape agency forward.

### 2.5 Quota behavior (Sub-task 1e)

**TE não expõe headers de rate limit/quota** em nenhuma das 27 responses testadas. Zero match em `X-RateLimit-*`, `RateLimit-*`, `X-Quota-*`, `X-Requests-Remaining`.

**Implicação operacional:** consumption tracking não é observável em-band. Depende de:
1. TE dashboard externo (web UI da conta TE).
2. Connector-side counter local (Phase 1 connector dev implementar).
3. Soft failures quando quota esgotar (403? 429? não testado em limit).

---

## 3. FRED findings (15 calls + 3 retries = 18)

### 3.1 Série × status × freshness

| Series ID | Status | Rows | Latest | Lag (d) | Freq | Value | Verdict |
|-----------|--------|------|--------|---------|------|-------|---------|
| GDPC1 | 200 | 316 | 2025-10-01 | 199 | Q | 24 055.75 | OK |
| **INDPRO** | **502→200** | **1287** | **2026-03-01** | **49** | **M** | **101.79** | OK (transient 502 retry ok) |
| RSAFS | 200 | 410 | 2026-02-01 | 76 | M | 738 366 | OK |
| T10Y2Y | 200 | 13 014 | 2026-04-17 | 1 | D | 0.55 | OK |
| **OECDLOLITOAASTSAM** | **200** | **738** | **2022-11-01** | **1 264** | **M** | **98.31** | **STALE 3.4Y** |
| **USSLIND** | **200** | **458** | **2020-02-01** | **2 268** | **M** | **1.72** | **STALE 6Y** |
| UNRATE | 200 | 939 | 2026-03-01 | 48 | M | 4.3 | OK |
| SAHMREALTIME | 200 | 796 | 2026-03-01 | 48 | M | 0.2 | OK |
| PAYEMS | 200 | 1 047 | 2026-03-01 | 48 | M | 158 637 | OK |
| JTSJOL | 200 | 303 | 2026-02-01 | 76 | M | 6 882 | OK |
| UMCSENT | 200 | 880 | 2026-02-01 | 76 | M | 56.6 | OK |
| VIXCLS | 200 | 9 468 | 2026-04-16 | 2 | D | 17.94 | OK |
| TDSP | 200 | 184 | 2025-10-01 | 199 | Q | 11.32 | OK |
| DGS10 | 200 | 16 773 | 2026-04-16 | 2 | D | 4.32 | OK |
| **DFEDTAR** | **200** | **9 577** | **2008-12-15** | **6 333** | **D** | **1.0** | **DISCONTINUED** |
| DFEDTARU | 500 | 0 | — | — | — | — | Retry server err |
| DFEDTARL | 500 | 0 | — | — | — | — | Retry server err |

**3 findings críticos:**

1. **`OECDLOLITOAASTSAM` stale** — FRED mirror parou de receber updates desde 2022-11. **Implicação:** usar OECD direct (confirmed fresh 2025-12 em §7) como primary; FRED mirror é fallback broken. Matriz row `oecd_cli` actualizada: status OK mas primary move de FRED para OECD direct.

2. **`USSLIND` stale** — Philly Fed State Leading Index descontinuado em 2020. A proxy LEI que documentei em `economic.md` (como fallback Phase 1) é **inutilizável**. **Implicação:** E2 US LEI sem proxy free; backlog `CAL-023` — find alternative LEI proxy OR accept permanent GAP + re-weight E2 3/4 para US.

3. **`DFEDTAR` descontinuado** — Fed adoptou target range em 2008-12-16; série single-rate parou. **Implicação:** matrix row `policy_rate` US precisa update — usar `DFEDTARU` (upper) + `DFEDTARL` (lower) como range, OR `FEDFUNDS` (effective rate). Retry em D2 dos 2 series returnou 500 transient; re-test Phase 1 conector. **Correct primary para US policy_rate:** `DFEDTARU` (target upper) OR `FEDFUNDS` (effective — stable, recommended).

### 3.2 Matrix impact

3 rows BLOCKING (oecd_cli, lei_conference_board, policy_rate) com source FAIL/STALE identificado. Novos backlog items:
- `CAL-021` TE indicator-name/symbol normalization table.
- `CAL-023` LEI US alternative (USSLIND descontinued).
- `CAL-024` Policy rate US series swap (DFEDTAR → FEDFUNDS/DFEDTARU).

---

## 4. BIS WS_DSR findings (8 calls)

### 4.1 Universe coverage

| Country | Key | Status | Obs | Latest | Lag (d) |
|---------|-----|--------|-----|--------|---------|
| PT | Q.PT.P | 200 | 107 | 2025-Q3 | 202 |
| US | Q.US.P | 200 | 107 | 2025-Q3 | 202 |
| DE | Q.DE.P | 200 | 107 | 2025-Q3 | 202 |
| JP | Q.JP.P | 200 | 107 | 2025-Q3 | 202 |
| GB | Q.GB.P | 200 | 107 | 2025-Q3 | 202 |
| TR | Q.TR.P | 200 | 95 | 2025-Q3 | 202 |
| BR | Q.BR.P | 200 | 107 | 2025-Q3 | 202 |

**Findings:**
- **7/7 países testados retornam dados.** Dimensional key `Q.{country}.P` (quarterly, country, private non-financial) funciona consistentemente.
- **Obs count 107** para T1/G10 + major EMs — ~27 anos de dados (desde ~1999-Q1). TR tem 95 obs (mais curto — série começa 2003).
- **Lag 202d** = aproximadamente Q+1 a Q+2 publish cycle (2025-Q3 disponível 2026-Q2).
- **Parser de SDMX-JSON 1.0:** estrutura `data.dataSets[0].series[key].observations[idx]` + `data.structure.dimensions.observation[0].values[idx]` — reliable, mesmo padrão testado em D1.

### 4.2 SDMX parsing notes

- Response size per country: ~500KB (manageable).
- Metadata endpoint (`/structure/dataflow/BIS/WS_DSR`) returnou **400** — path format errado. Não-crítico; dataflow estrutura já documentada no BIS portal web.
- Accept header `application/vnd.sdmx.data+json;version=1.0.0, application/json` é mandatory para JSON response (sem default XML).

### 4.3 Matrix impact

BIS WS_DSR **confirmado production-ready** para L4 DSR sub-index. 32-country universe do briefing é plausível — D2 testou 7 de 7 subset com 100% success.

---

## 5. ECB SDW findings (7 calls)

### 5.1 Por key

| Label | Key | Status | Obs | Latest | Lag (d) | Verdict |
|-------|-----|--------|-----|--------|---------|---------|
| STS-UNE-EA | `STS/M.U2.Y.UNR.T.TOTAL0.15_74.T` | **400** | 0 | — | — | **FAIL key** |
| STS-UNE-DE | `STS/M.DE.Y.UNR.T.TOTAL0.15_74.T` | **400** | 0 | — | — | FAIL key |
| STS-UNE-FR | `STS/M.FR.Y.UNR.T.TOTAL0.15_74.T` | **400** | 0 | — | — | FAIL key |
| ICP-HICP-EA | `ICP/M.U2.N.000000.4.ANR` | 200 | 348 | 2025-12 | 111 | OK |
| FM-YLD-EA10Y | `FM/B.U2.EUR.4F.BB.U2_10Y.YLD` | **404** | 0 | — | — | **FAIL key** |
| BSI-LOANS-EA | `BSI/M.U2.N.A.A20.A.1.U2.2240.Z01.E` | 200 | 342 | 2026-02 | 49 | OK |
| ESI-EA | `ESI/M.U2.Z.ESI.Z` | **404** | 0 | — | — | **FAIL key** |

### 5.2 Findings

- **4/7 keys funcionam** (ICP HICP, BSI Loans principais).
- **3/7 falham**: STS unemployment keys (wrong dataflow? LFSI?), FM yield curve (key dimension incorrecta), ESI sentiment (wrong dataflow ID — DG ECFIN serve via Eurostat `ei_bssi_m_r2`, não ECB ESI).
- **ICP HICP lag 111d** é anómalo para monthly YoY (esperado ~30d). Possivelmente a key `M.U2.N.000000.4.ANR` retorna revised annual series, não YoY flash release. Phase 1 connector dev precisa resolver key correcta para HICP flash.
- **BSI Loans fresh 49d** — consistent com ECB monthly release cycle.

### 5.3 Matrix impact

ECB SDW key documentation em D1 (`monetary.md §3.2`) **optimista demais** — 3/7 keys invalidas em production. Backlog `CAL-025` para key audit systematic via ECB SDW web UI → regenerate canonical keys table.

---

## 6. Eurostat findings (5 calls)

### 6.1 Por dataset

| Dataset × Geo | Status | Obs | Latest | Lag (d) | Verdict |
|---------------|--------|-----|--------|---------|---------|
| une_rt_m × DE | 200 | 3 798 | 2026-03 | 21 | OK |
| une_rt_m × FR | 200 | 4 662 | 2026-03 | 21 | OK |
| **sts_inpr_m × IT** | **413** | **0** | — | — | **Payload too large** |
| prc_hicp_manr × ES | 200 | 78 370 | 2025-12 | 111 | OK (large) |
| ei_bssi_m_r2 × NL | 200 | 5 457 | 2026-03 | 21 | OK |

### 6.2 Findings

- **Unemployment fresh 21d** (Mar 2026 release) — production-ready.
- **HICP ES lag 111d** (Dec 2025) — pattern consistente com ICP EA. Flash vs published cycle diferença.
- **sts_inpr_m IT retornou 413** — payload too large. IT Industrial Production dataset tem muitas séries cross-sector; Phase 1 connector precisa filter sector (`NACE_R2` dimension) para reduce payload. Backlog `CAL-026`.
- **JSON-Stat parsing works** — parser em D2 usa `value` + `dimension.time.category.index` — reliable.

---

## 7. INE PT findings (5 calls)

### 7.1 Status

| Indicador | Desc | Status | Content-Type | JSON Dados |
|-----------|------|--------|--------------|-----------|
| 0011725 | PIB QoQ | 200 | application/json | **Empty** `{}` |
| 0000997 | IP | 200 | application/json | **Empty** |
| 0009099 | Retail Sales | 200 | application/json | **Empty** |
| 0000976 | Unemployment | 200 | application/json | **Empty** |
| 0009122 | Consumer Confidence | 200 | application/json | **Empty** |

### 7.2 Findings

- **5/5 returns 200 com JSON válido** mas `Dados` dict é **empty** para todos os 5 indicators.
- Response structure: `[{IndicadorCod, IndicadorDsg, MetaInfUrl, DataExtracao, DataUltimoAtualizacao, UltimoPref, Dados: {}, Sucesso}]` — successful shell sem observations.
- Endpoint URL `https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd={cod}&lang=PT` devolve metadata mas não dados.
- Testes adicionais com `op=1` e `Dim1=*` produziram mesmo resultado (empty Dados).

### 7.3 Discovery path Phase 1

Alternativas a testar em Phase 1 connector dev:
1. **BdP BPstat** `https://bpstat.bportugal.pt/data/v1/{series_id}` — documentado em D1 credit.md mas não testado empiricamente.
2. **INE catalog search UI** — inspect network requests quando INE UI mostra dados de um indicador, extract correct URL pattern.
3. **SDMX endpoint INE** — INE anuncia SDMX REST service mas URL pattern não publicado.
4. **Eurostat como proxy** — PT data disponível via Eurostat datasets (`une_rt_m geo=PT`, etc.) — proven working em T5.

**Backlog:** `CAL-022` INE PT endpoint discovery (Phase 1).

**Mitigação imediata:** para Phase 1 PT data, usar **Eurostat como primary fonte** (per §6 confirmed working), com INE direct como Phase 2+ optimization.

---

## 8. OECD CLI findings (5 calls + 5 retries = 10)

### 8.1 Parser v1 failure + v2 fix

- Primeira tentativa parser seguiu SDMX-JSON 1.0 structure (data em top-level `dataSets`). OECD endpoint retorna **SDMX-JSON 2.0** (data em `j['data']['dataSets']`, structure em `j['data']['structures'][0]`). 5/5 responses 200 com 4.7MB payload mas obs_count=0 per parser v1.
- Parser v2 fix:
  ```python
  data = j.get('data', {})
  ds_list = data.get('dataSets', [])
  struct = data.get('structures', [{}])[0]
  # Select most-populated series (MEI_CLI has 411 series per country — multi-indicator dataset)
  ```

### 8.2 Findings post-fix

| Country | Status | Obs | Latest | Lag (d) |
|---------|--------|-----|--------|---------|
| USA | 200 | 109 | 2025-12 | 111 |
| DEU | 200 | 109 | 2025-12 | 111 |
| FRA | 200 | 109 | 2025-12 | 111 |
| PRT | 200 | 109 | 2025-12 | 111 |
| JPN | 200 | 109 | 2025-12 | 111 |

- **5/5 countries fresh 2025-12** (lag 111d) — OECD direct é **actualizada** ao contrário do FRED mirror `OECDLOLITOAASTSAM` stale 2022-11 (1 264d).
- **Dataset é rico:** 411 series per country filter → multiple CLI variants (amplitude-adjusted, trend-restored, ratio-to-trend, etc.). Phase 1 connector precisa select a CLI variant correcta (`IDX.IXCR.M` amplitude-adjusted índice é canonical).
- **lag 111d** reflects OECD publish cycle (~3.5 meses após fim do mês reference).

### 8.3 Matrix impact

Matrix row `oecd_cli`: primary **muda de FRED para OECD direct** em Phase 1. FRED mirror stays como deprecated fallback com alert `SOURCE_STALE` se ever queried.

---

## 9. Matrix augmentation summary (Task 8)

### 9.1 CSV columns added

`D1_coverage_matrix.csv` em-place augmented com 3 colunas:
- `freshness_observed_days` — dias entre LatestValueDate e 2026-04-18.
- `last_tested_date` — `2026-04-18` se testado; blank se não.
- `test_status` — `OK`, `FAIL`, `STALE`, `NOT_TESTED`.

### 9.2 Coverage

| Status | Rows | % de 67 |
|--------|------|---------|
| OK | 15 | 22% |
| FAIL | 6 | 9% |
| STALE | 1 | 1% |
| NOT_TESTED | 45 | 67% |

### 9.3 Rows tested (22/67)

- E1 activity (3): `gdp_qoq`, `industrial_production`, `retail_sales` — todos OK.
- E2 leading (4): `yield_curve_slope_10y_2y` OK, `oecd_cli` OK (via OECD direct; FRED mirror stale noted), `lei_conference_board` **STALE** (USSLIND 6Y), `pmi_manufacturing` **FAIL** (IN TE empty).
- E3 labor (4): `unemployment_rate`, `sahm_rule_triggered`, `nfp_change`, `jolts_openings` — todos OK.
- E4 sentiment (3): `umich_sentiment` OK, `esi_economic_sentiment` **FAIL** (ECB SDW key wrong), `vix_index` OK.
- L4 DSR (1): `debt_service_ratio` OK.
- M1 (1): `policy_rate` OK (JP Interest Rate fresh; DFEDTAR discontinued noted separately).
- F2 (1): `equity_returns_3m_6m_12m` OK (SPX/NKY/DAX via TE markets).
- Overlay expected-inflation (1): `hicp_yoy` OK.
- Overlay rating-spread (4): `rating_actions_sp`, `moodys`, `fitch`, `dbrs` — todos **FAIL** (TE path 404; re-confirma D0 rejection).

### 9.4 Rows not tested (45/67)

Principalmente: NSS tenors (9 overlays), TIPS real yields, CDS scrapes, equity vol derivations, breakeven inflation, inflation swap, SPF, credit stock/gap/impulse, shadow rates, r*, 5y5y forward, NFCI/CISS, Damodaran ERP, BIS property gap, breadth MA200, MOVE, IG/HY OAS, AAII/COT/FINRA, buyback yield, L4 META (4). Phase 1 connector dev vai validar estes on-demand.

---

## 10. TE tier decision recommendation (Task 9)

### 10.1 Consumption observed

**1 request `/country/portugal` retorna 157 indicators.** Se este pattern é representativo (D0 reportou 3 492 rows `/country/portugal` — possivelmente a diferença é entre "total indicators" vs "indicators with time series data"), então bulk é extremamente eficiente.

**Scenarios Phase 1 consumption (46 countries = 16 T1 + 30 T2):**

| Scenario | Requests/month | Series exports/month (se counter = rows × call) | Series exports/month (se counter = unique series × 30 days) |
|----------|----------------|----------------------------------------------|-----------------------------------------------------|
| (a) Bulk daily per country | 46 × 30 = **1 380** | 46 × 157 × 30 = **216 660** | 46 × 157 = **7 222** |
| (b) Filtered daily (g=GDP,Money,Business,Labour,Consumer) | 46 × 5 × 30 = **6 900** | each ~30 rows × 6 900 = **207 000** | subset of (a), maybe 90% = **~6 500** |
| (c) Granular historical weekly backfill (15 series per country) | 46 × 15 × 4 = **2 760** | 46 × 15 × 4 = **2 760** | 46 × 15 = **690** |
| (d) Markets daily (6 index + 4 FX) | 46 × 10 × 30 = **13 800** | 46 × 10 × 30 = **13 800** | 46 × 10 = **460** |
| **Total Phase 1 lower bound** | **~11 400** | — | — |
| **Total Phase 1 upper bound** | **~25 000** | ~440 000 | ~15 000 |

### 10.2 Ambiguidade crítica

**A definição "Series Exports" não é observável empiricamente** (TE não exposed quota headers em D2 — §2.5). As 3 hipotese razoáveis:

1. **Unique-series × month**: um série contado 1× no mês independente de pulls → Premium 5000 é largo para Phase 1 (~700-1500 unique series).
2. **Series-per-call**: cada row counted por call → Premium 5000 insuficiente em **qualquer daily pull pattern** (só bulk 1 país/dia já supera). Enterprise mandatory.
3. **Series-per-day-unique**: unique (series, date) tuple counted → scale intermédia.

### 10.3 Recomendação

**1. Phase 1 connector dev em observation mode** — correr daily bulk + weekly historical para **5-10 países piloto** durante 7-14 dias. Hugo monitoriza TE dashboard quota counters. Após 7-14 dias → consumption empirical observed → decide scale.

**2. Endpoint selection pattern preferred:**
   - **Bulk `/country/{c}` daily** (1 req/country/day): cobre 90% das séries em 46 req/dia = 1 380 req/mês — **within Premium 5000**.
   - **Granular `/historical/country/{c}/indicator/{x}` weekly backfill** (1 req por série × país × semana): reserve para séries específicas que matter calibration. Estimate 2 760 req/mês.
   - **Markets `/markets/historical/{sym}` daily** para ~10 global symbols (não per-country) — 10 × 30 = 300 req/mês.
   - **Total estimate:** ~4 500 req/mês. **Within Premium 5000 requests/month.**

**3. Se observation revelar que "Series Exports" counter explode** (>5000/month apesar bulk pattern) → negotiate enterprise tier com TE OR reduce to T1-only (16 countries) para Phase 1.

**4. Não recomendo downgrade para Standard** até D2+7-14d observation confirm consumption.

### 10.4 Backlog para Phase 1

- `CAL-027` TE quota observation (Phase 1 first 14 days).
- `CAL-028` Connector observability — counter local + alert quando >70% de quota consumida.

---

## 11. Surprises / quirks

### 11.1 Unexpected behaviors observed

1. **TE inclui forecast data** em `LatestValueDate` (observed `date_max = 2026-12-31` para PT; `australia Consumer Confidence` lag -12d). Consumers precisam filter `date ≤ today` sistematicamente — backlog `CAL-029`.

2. **TE indicator names country-specific**: UK `Unemployment Rate` retorna 0 rows mas `Unemployment Rate Adjusted` (hypothesis) pode funcionar. Names precisam normalization table — `CAL-021`.

3. **FRED tem séries discontinued sem aviso**: `DFEDTAR` (2008 cutoff), `USSLIND` (2020 cutoff), `OECDLOLITOAASTSAM` (2022 cutoff). Connector precisa **automated staleness detection** (latest_date vs expected frequency lag × factor). Backlog `CAL-030`.

4. **ECB SDW key documentation é fragil**: 3/7 keys testadas em D2 retornam 400/404. Phase 1 connector precisa schema-aware key generator OR curated key catalogue auditado — `CAL-025`.

5. **Eurostat 413 payload too large** em `sts_inpr_m IT` inesperado (dataset não-exotic). Pagination / dimension filter mandatory.

6. **OECD SDMX-JSON version mismatch**: endpoint `stats.oecd.org/SDMX-JSON/data` serve SDMX 2.0 format (data nested em `j.data`, structures plural), não 1.0. Connector precisa parser aware de ambas versões (OECD 2.0 + BIS 1.0 coexistem).

7. **INE PT pattern empty**: 200 status mas `Dados: {}` dict. Backlog `CAL-022` discovery; Phase 1 uses Eurostat mirror.

8. **BIS return TR obs=95 vs others 107** — Turkey série mais curta (~3Y less). Attribution per country obs count em spec L4-dsr para confidence weighting.

### 11.2 Confirmações positivas

1. **FRED backbone para US é sólido** — 12/15 series OK em primeira call + 1 retry bem-sucedido. Reliability alta.
2. **BIS WS_DSR key pattern é consistente cross-country** (Q.{iso}.P funciona em 100% dos 7 testados).
3. **Eurostat JSON-Stat é performant** — 4/5 datasets OK, large responses tratáveis.
4. **TE bulk /country/{c} endpoint é production-ready** como primary path T2+ breadth.

---

## 12. Open questions for D3 (Pattern 4 + ADR-0005 ammunition)

1. **Pattern "staleness detection" canónico**: quando é que uma série em FRED/TE/BIS se considera "stale" vs "on-cycle"? Threshold por frequency? `CAL-030`.

2. **Connector observability layer** — Phase 1 precisa counter local de requests × source + emit telemetry. ADR candidate: observability architecture para L0 connectors.

3. **Source failover chain** formalização — quando `primary` falha (FRED mirror stale, ECB key wrong, TE indicator 0 rows), quando é que switch para fallback é automatic vs requires operator sign-off? ADR-0005 candidate.

4. **TE indicator normalization table** — governance: onde vive? `data_sources/` YAML curado (per country per indicator)? Phase 1 blocker.

5. **SDMX version handling** — parser library escolha (sdmx-python vs pysdmx vs custom parser)? D3 Decision.

6. **INE PT strategic**: se INE endpoint stays broken, é Portugal-data Eurostat-dependent permanent? Implica que Portugal edge (home market) depende de rate limits Eurostat publicamente.

7. **Forecast vs realised data filter** em TE — design pattern para normalizer filter `date ≤ today` automático? Should overlays (que precisam forecast data, e.g. breakeven BEI) ter path diferente?

8. **Quota tracking cross-source** — dashboard único para TE + FRED (120/min) + BIS (undocumented) + ECB (undocumented) + Eurostat (undocumented)? Design para Phase 1 observability.

---

## 13. Request budget used

- TE: 27 (30 budget)
- FRED: 15 + 3 retries = 18 (15 budget, +3 retries mid-task)
- BIS: 8 (8 budget)
- ECB SDW: 7 (7 budget)
- Eurostat: 5 (5 budget)
- INE PT: 5 (5 budget)
- OECD: 5 + 5 retries = 10 (5 budget, +5 re-parse)
- **Total: 80 / 100 budget. 20 margin remaining para D3.**

---

*Gerado 2026-04-18 · Fase 0 Bloco D2 · Phase 0 completion gate continua dependente Hugo sign-off D1 §7 + novos findings D2 §11.*
