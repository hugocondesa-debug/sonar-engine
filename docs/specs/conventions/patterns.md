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

## Quando NÃO aplicar nenhum dos 3

Padrão simples (single method, single table, single version) é o default. Forçar um padrão onde scope não justifica adiciona complexidade sem valor.

## Referências

- [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) §7 — padrões emergidos
- [`../overlays/erp-daily.md`](../overlays/erp-daily.md) — Parallel equals canónico
- [`../overlays/crp.md`](../overlays/crp.md), [`../overlays/expected-inflation.md`](../overlays/expected-inflation.md) — Hierarchy best-of
- [`../overlays/rating-spread.md`](../overlays/rating-spread.md) — Versioning per-table
- [`methodology-versions.md`](methodology-versions.md) — formato e bump rules
