# Architectural patterns

Três padrões emergiram durante specs P3-P5 por convergência independente. Formalizados aqui como **frozen contracts** — novas overlays/indices/cycles aplicam um destes padrões quando scope corresponder.

## Scope

Aplicam-se a overlays (L2) e indices (L3) onde múltiplos methods ou tabelas coexistem. Cycles (L4) usam fail-mode de [`composite-aggregation.md`](composite-aggregation.md), não os padrões aqui.

## Padrão 1: Parallel equals

### Definição

Múltiplos methods com **standing epistémico igual** calculam o mesmo output em unidades idênticas. Canonical = agregação estatística + range exposto como uncertainty signal.

### Quando aplicar

- Todos os methods têm validade teórica comparável (não há "primário").
- Output é contínuo em unidades naturais (bps, decimal, pp).
- Divergência entre methods é sinal editorial útil (não ruído).

### Template estrutural

```
methods: [method_a, method_b, ..., method_n]
  ↓ cada um produz output em mesma unidade
canonical = median(outputs)  # ou mean conforme spec
range = max(outputs) − min(outputs)
flag: METHOD_DIVERGENCE quando range > threshold
```

### Exemplo canónico

[`../overlays/erp-daily.md`](../overlays/erp-daily.md): 4 methods (DCF, Gordon, EY, CAPE) com standing igual. Canonical = `median_bps`. `range_bps` exposto. Flag `ERP_METHOD_DIVERGENCE` quando `range > 400 bps`.

### Contra-exemplo

[`../overlays/crp.md`](../overlays/crp.md): methods têm quality gradient (CDS preferível a sovereign spread preferível a rating-implied). Este é **Hierarchy best-of**, não Parallel equals.

## Padrão 2: Hierarchy best-of

### Definição

Methods têm **quality gradient conhecido**. Canonical = primeiro disponível na ordem; restantes persistidos lado-a-lado para audit e fallback automático.

### Quando aplicar

- Um method é epistemicamente superior (market-based > model-based > rating-based).
- Coverage dos methods varia por country/date (method A disponível em US+EA, method B também em EM, method C sempre disponível).
- Fallback deve ser automático mas auditável.

### Template estrutural

```
methods_ordered: [best, middle, worst]
  ↓ avaliar disponibilidade per (country, date)
canonical = first_available(methods_ordered)
method_used: TEXT NOT NULL  # qual method alimentou canonical
all methods persistidos lado-a-lado em columns
```

### Exemplo canónico

[`../overlays/crp.md`](../overlays/crp.md): CDS > sovereign spread > rating-implied.
[`../overlays/expected-inflation.md`](../overlays/expected-inflation.md): BEI > SWAP > DERIVED (PT path) > SURVEY.
`method_used` persistido; fallback silencioso OK (coverage gap conhecido, não erro).

### Contra-exemplo

[`../overlays/erp-daily.md`](../overlays/erp-daily.md): 4 methods têm standing igual; median canonical, não first-available. Este é Parallel equals.

## Padrão 3: Versioning per-table

### Definição

Múltiplas tabelas relacionadas com **cadências de bump divergentes**. Cada tabela emite `methodology_version` independente, permitindo evolução desincronizada.

### Quando aplicar

- Outputs do overlay espalham por ≥ 2 tabelas.
- Alterações conceptuais diferentes afectam tabelas diferentes (ex: lookup table mudou; formula não).
- Re-backfill seletivo por tabela é preferível a rebackfill global.

### Template estrutural

```
overlay emite 2+ tabelas:
  table_a · methodology_version: VERSION_A_v{MAJOR}.{MINOR}
  table_b · methodology_version: VERSION_B_v{MAJOR}.{MINOR}
  table_c · methodology_version: VERSION_C_v{MAJOR}.{MINOR}

bumps independentes:
  - A bump quando lookup A muda
  - B bump quando formula B muda
  - C bump quando calibration C muda
```

### Exemplo canónico

[`../overlays/rating-spread.md`](../overlays/rating-spread.md): 3 versions distintas:

- `RATING_AGENCY_v0.1` — per-agency raw lookup; bump quando agency altera rating scale.
- `RATING_SPREAD_v0.1` — consolidated cross-agency; bump quando consolidation rule muda.
- `RATING_CALIBRATION_v0.1` — global notch→spread; quarterly recalibration from Moody's + ICE BofA.

### Contra-exemplo

[`../overlays/nss-curves.md`](../overlays/nss-curves.md): 4 tabelas (spot/zero/forward/real) mas **mesma** `methodology_version` (`NSS_v0.1`). Todas bumps juntas porque dependem da mesma fit. Single version suficiente.

## Padrão 4: TE primary + native overrides

### Definição

L0 connectors de macro/markets data usam **Trading Economics como primary breadth source** (`/country/{c}` bulk endpoint cobre 75+ países × 150+ indicators/call) com **overrides nativos por (série, país) quando satisfazem triggers explícitos**. Native override substitui TE silenciosamente; TE é fallback auditável.

### Quando aplicar

- Série é consumida por specs L2-L3 para ≥ 2 países.
- Existe ≥ 1 fonte nativa (FRED, BIS, ECB SDW, Eurostat, BPstat, central bank direct) que satisfaz ≥ 1 override trigger vs TE.
- TE breadth cobre pelo menos T2+T3 (~46+43 países) para a série.

### Template estrutural

```
primary: TE /country/{c}/indicators
  ↓ loaded bulk daily 1 req per country
override_matrix:
  (series, country) → native_connector
    └── activated per override_triggers (ver abaixo)
connector resolution:
  if (series, country) in override_matrix:
      data = native_connector.fetch(...)
      flag(source_used: native)
  else:
      data = te_bulk_cache.get(country, series)
      flag(source_used: TE)
```

### Override triggers

| Trigger | Descrição | Exemplo |
|---------|-----------|---------|
| **Freshness gap** | Nativo publica T+N com N < TE lag observado em D2 | FRED VIXCLS T+1 vs TE VIX:IND T+1 (parity — no override); Eurostat `une_rt_m` DE T+21 vs TE Unemployment Rate DE possibly T+30 (override) |
| **Depth gap** | Nativo expõe granularidade que TE agrega ou não calcula | FRED `T10Y2Y` pre-computed slope vs TE spot yields por tenor (override FRED); FRED TIPS real yields `DFII*` (TE não expõe TIPS) |
| **Authoritativeness** | Série tem only one authoritative source canónica | Fed policy rate = FRED `FEDFUNDS` / `DFEDTARU`+`DFEDTARL`; ECB policy rate = ECB SDW `FM`; BIS debt service ratio = BIS `WS_DSR` — TE não é source of truth semântico |
| **TE broken/mismatch** | TE retorna 0 rows / wrong indicator name cross-country (D2 finding) | UK Unemployment Rate TE 0 rows → override Eurostat `une_rt_m geo=UK` |

### Matriz domínio × primary × override

| Domínio | TE primary? | Native override principal | Trigger dominante |
|---------|-------------|--------------------------|-------------------|
| Macro indicators (GDP, CPI, IP, retail, unemployment) | ✓ breadth | FRED (US), Eurostat (EA), INE (PT quando discovery resolve) | Freshness + authoritativeness per country |
| Yield curves (sovereign tenors) | ~ ponto-a-ponto | FRED `DGS*` (US), Bundesbank Svensson (DE), BoE A-S (UK), MoF (JP) | Depth (Svensson/A-S pre-fitted) + authoritativeness |
| FX | ✓ `/markets/{pair}:CUR` | — (TE é sufficient; FRED `DEXUSEU` etc. overlap) | — |
| Commodities | ✓ `/markets/{sym}:COM` | FRED (WTI `DCOILWTICO`, gold `GOLDAMGBD228NLBM`) | Freshness (FRED delayed vs TE real-time) |
| Equity indices | ✓ `/markets/{sym}:IND` | FRED `SP500` (US only) | Authoritativeness US; TE breadth mandatory non-US |
| Credit spreads (OAS) | ✗ não confiável | FRED `BAMLC0A0CM`/`BAMLH0A0HYM2` (ICE BofA) | Depth + authoritativeness (ICE licensed) |
| Rating actions | ✗ stale D0 | Damodaran annual + agency scrape forward | TE broken (4Y stale) + authoritativeness |
| Central bank decisions (policy rate) | ~ breadth | FRED US, ECB SDW EA, native CB direct | Authoritativeness canonical |
| Economic calendar (release dates) | ✓ `/calendar` | — | — (TE é canonical) |
| Positioning data (AAII, COT, FINRA) | ✗ | aaii.com / cftc.gov / finra.org scrapes | TE não cobre |
| On-chain crypto | ✗ | Out-of-scope Phase 1 | — |
| Survey data (SPF, UMich) | ~ breadth | FRED (UMCSENT, EXPINF10YR), ECB SPF direct | Depth + authoritativeness |

### Exemplo canónico

Economic cycle ECS consume unemployment rate em 46 países (T1+T2). Pattern 4 em acção:

- 46 países × 1 daily bulk `/country/{c}` call → populate TE cache.
- Override matrix:
  - US → FRED `UNRATE` (authoritativeness + freshness T+5 vs TE variable)
  - EA aggregate → ECB SDW `STS` dataflow (TE não expõe aggregate)
  - DE, FR, IT, ES, etc. → Eurostat `une_rt_m` (freshness T+21 confirmed D2)
  - UK → Eurostat ou ONS direct (TE returnou 0 rows D2)
  - PT → Eurostat mirror (INE broken D2)
  - T2 EMs (BR, IN, MX, etc.) → TE primary (native connectors Phase 2+)
- Consumer L3 spec `E3-labor` recebe unified series; flag `source_used` persistido por audit.

### Evidence base

- [`../../data_sources/D1_coverage_matrix.csv`](../../data_sources/D1_coverage_matrix.csv) — 67 rows matriz canónica (15 cols D1 + 3 cols D2 freshness).
- [`../../data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) — 22 rows tested; D2 confirmou 3 override triggers (freshness, depth, authoritativeness) empiricamente.

### Consequences + trade-offs

- **TE é single-point-of-failure para breadth T2-T3**. Se TE rate limit hit OR outage, override matrix cobre T1 full mas T2+T3 degradado → flag `COVERAGE_TE_DEGRADED` + Policy 1 re-weight.
- **Override matrix maintenance overhead**: per `(série, país)` entry requires spec + validation. Governance: maintained em `data_sources/*.md` per cycle; changes require PR dedicado.
- **Silent override**: connector switch primary→native sem alert (by design — fallback automatic). Audit via `source_used` column em raw tables.

### Contra-exemplo

L4 cycle aggregation (ECS, CCCS, MSC, FCS): consome L3 indices, não raw data. Pattern 4 não aplica — cycles usam fail-mode de [`composite-aggregation.md`](composite-aggregation.md) Policy 1.

### FROZEN status

Alterações à lista de override triggers OR à tabela domínio×override requerem PR dedicado (consistente com Patterns 1-3). Adicionar (`série`, `país`) entries à override matrix em `data_sources/*.md` não é breaking change ao Pattern 4 per se; é operacional.

## Quando NÃO aplicar nenhum dos 4

Padrão simples (single method, single table, single version, single source) é o default. Forçar um padrão onde scope não justifica adiciona complexidade sem valor.

## Referências

- [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) §7 — padrões emergidos
- [`../overlays/erp-daily.md`](../overlays/erp-daily.md) — Parallel equals canónico
- [`../overlays/crp.md`](../overlays/crp.md), [`../overlays/expected-inflation.md`](../overlays/expected-inflation.md) — Hierarchy best-of
- [`../overlays/rating-spread.md`](../overlays/rating-spread.md) — Versioning per-table
- [`../../data_sources/D1_coverage_matrix.csv`](../../data_sources/D1_coverage_matrix.csv), [`../../data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) — TE primary + native overrides evidence
- [`methodology-versions.md`](methodology-versions.md) — formato e bump rules
- [`proxies.md`](proxies.md) — proxy vs fallback distinction
