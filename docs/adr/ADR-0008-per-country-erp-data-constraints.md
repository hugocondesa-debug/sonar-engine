# ADR-0008: Per-country ERP deferral + live Damodaran mature-market fallback

**Status**: Accepted
**Data**: 2026-04-22
**Decisores**: Hugo Condesa
**Consultados**: —

## Contexto

Week 10 Sprint B (`docs/planning/week10-sprint-b-erp-t1-brief.md`) foi
planeado para replicar o padrão ERP US em cinco mercados T1 (DE / GB /
JP / FR / EA-aggregate), substituindo o flag `MATURE_ERP_PROXY_US`
por sinal live per-country. O spec `docs/specs/overlays/erp-daily.md`
exige quatro métodos (DCF / Gordon / Earnings-Yield / CAPE) com
`MIN_METHODS_FOR_CANONICAL = 2` para produzir um `ERPCanonicalResult`.

Pre-flight empírico (2026-04-22) contra TE / FMP / Damodaran revelou
que:

- **TE expõe apenas o closing level** da bolsa via
  `/historical/country/{country}/indicator/stock%20market`. Os símbolos
  canónicos estão estáveis (DAX / UKX / NKY-Nikkei / CAC / SX5E) e
  cobrem multi-decada daily.
- **TE não expõe fundamentals agregados per-market** (dividend yield,
  trailing/forward EPS, CAPE). Probes para `germany/dividend yield`,
  `germany/price earnings`, `germany/earnings per share` devolvem
  array vazio; o catálogo de `/country/germany` não inclui qualquer
  categoria de equity-fundamental para além de `Stock Market`.
- **FMP stable tier** expõe historical-price-eod para tickers
  internacionais (`^GDAXI`, etc.) mas `key-metrics` e `ratios` devolvem
  `[]` para índices — serviço de fundamentals é company-level only.
- **Damodaran** publica anualmente `ctryprem.xlsx` (Country ERP derivado
  da sua composição `mature + country_default_spread × vol_ratio`) e
  mensalmente `implprem/ERP{Mon}{YY}.xlsx` (Implied ERP S&P 500). Nenhum
  destes documentos expõe per-country aggregate fundamentals em forma
  compute-friendly — a própria metodologia do Damodaran para países
  não-US é *composição* a partir do mature-market ERP, não compute
  independente.

Todos os quatro métodos do `ERPInput` (DCF / Gordon / EY / CAPE) falham
para DE / GB / JP / FR / EA no estado actual porque os inputs primários
(earnings, dividend yield, CAPE ratio) não estão disponíveis. O HALT
trigger §5.1 do Sprint B ("Dividend / earnings data unavailable per
country — not a HALT unless all methods fail") activa-se literalmente:
todos os métodos falham em todos os cinco mercados.

A política SONAR "compute, don't consume" (CLAUDE.md §4) proíbe
ingerir directamente tabelas per-country ERP publicadas (Damodaran
ctryprem.xlsx) como input primário — reserva essas fontes para
cross-validation (`XVAL_DRIFT` flag). A decisão empurra a Sprint B
para um de dois caminhos:

- **Pausa total** — HALT + reabrir CAL para Phase 2.5 quando houver
  connectores de fundamentals per-market (Refinitiv / FactSet /
  Bloomberg).
- **Narrow-scope ship** — entregar scaffolding + melhoria parcial que
  *move o sinal live-ward* sem violar os princípios.

Este ADR documenta a segunda via e formaliza o que fica deferred.

## Decisão

Week 10 Sprint B entrega uma versão narrow-scoped composta por três
commits de código (+ documentação + retro + CAL). Per-country ERP
compute é deferido.

**Adoptamos**:

1. **TE per-country equity-index connector**
   (`fetch_equity_index_historical`) como scaffolding wire-ready, com
   source-identity guards (DAX / UKX / NKY / CAC / SX5E) — Phase 2.5
   consome este wrapper directamente quando connectors de fundamentals
   aterrarem.
2. **Damodaran monthly implied ERP** (`fetch_monthly_implied_erp`)
   como input "live" — Damodaran computa mensalmente o implied ERP do
   S&P 500 a partir do estado de mercado; consumimos **uma** métrica
   computed por ele, não uma tabela pre-packaged. Mantém o espírito
   de "compute don't consume" na margem: a nossa composição k_e
   continua a ser independente, mas o input mature-market passa de
   static 5.5 % para o valor live mensal.
3. **Resolver three-tier** em `daily_cost_of_capital.py`:
   `erp_canonical` (SONAR-computed) → Damodaran-monthly-live →
   static-5.5 %. Novo flag `ERP_MATURE_LIVE_DAMODARAN` distingue o
   segundo nível do static.
4. **Rejeitamos per-country 4-method compute** para DE / GB / JP / FR /
   EA neste sprint. Reabrimos como `CAL-ERP-T1-PER-COUNTRY` (PARTIAL)
   + sub-CALs para fundamentals connectors.

## Alternativas consideradas

- **Opção A — Narrow-scope ship via live mature-market + scaffolding**
  ← escolhida. Entrega valor real (live mature-market ERP) + prepara o
  terreno para Phase 2.5 (scaffolding + empirical doc). Respeita
  "compute, don't consume" (consumimos uma métrica, não uma tabela
  per-country).
- **Opção B — HALT total + reabrir CAL sem entregar código**. Preserva
  pureza metodológica mas deixa `DAMODARAN_MATURE_ERP_DECIMAL = 0.055`
  static como fallback permanente, o que é manifestamente stale
  (Damodaran Feb 2026 live ≈ 4.17 % vs static 5.5 %, 133 bps off).
  Rejeitada: o custo de não shippar o scaffolding + live-mature é maior
  do que o ganho de pureza.
- **Opção C — Ship per-country ERP consumindo Damodaran `ctryprem.xlsx`**
  directamente como tabela per-country. Rejeitada — viola
  "compute, don't consume" (CLAUDE.md §4). Damodaran ctryprem.xlsx
  permanece no lado de cross-validation, não de input primário.
- **Opção D — Mock per-country fundamentals com valores históricos
  de referência** (ex: dividend yield EA = 3.5 % static, forward EPS =
  trailing × global-growth). Rejeitada — nem é compute nem é consume,
  é fabrication. Qualquer ERP derivado seria artefacto, não sinal.

## Consequências

### Positivas

- `daily_cost_of_capital` deixa de reportar 5.5 % stale como mature
  ERP quando a SONAR ERP pipeline não correu ainda — passa a reflectir
  o valor Damodaran mais recente (Feb 2026 ≈ 4.17 %).
- Consumer A (MCP/API) que faça `sonar.cost_of_capital(country="DE")`
  recebe um k_e que varia mensalmente (via Damodaran) em vez de
  nunca variar até a SONAR ERP pipeline rodar.
- TE equity scaffolding com source-drift guards dá a Phase 2.5 um
  connector pronto; eliminar a probe empírica da próxima sprint.
- Pre-flight findings + ADR + retro deixam o contexto estável por
  escrito — próximo CC não reinventa a análise.

### Negativas / trade-offs aceites

- Per-country ERP compute continua a ser um buraco — `MATURE_ERP_PROXY_US`
  continua presente para non-US. Phase 2 exit criterion "per-market ERP
  live paths" NÃO é satisfeito.
- Adicionamos dependência transitiva (leve) no Damodaran NYU host —
  a fallback é graceful (connector error → static stub) mas a
  expectativa é que o host fique disponível.
- O flag `ERP_MATURE_LIVE_DAMODARAN` não deduz confidence, mesmo
  quando o valor vem de fora da SONAR compute chain. Justificação:
  Damodaran é o próprio autor da metodologia implied-ERP que a SONAR
  replica para US, portanto o valor mensal dele é epistemicamente
  equivalente ao da SONAR (não um "stub").

### Follow-ups requeridos

- `CAL-ERP-T1-PER-COUNTRY` passa de OPEN → PARTIAL com scope narrow;
  criados novos CALs dependentes:
  - `CAL-ERP-COUNTRY-FUNDAMENTALS` — connectors para dividend yield,
    trailing/forward EPS, CAPE per market index (Refinitiv / FactSet /
    Bloomberg / MSCI).
  - `CAL-ERP-CAPE-CROSS-COUNTRY` — CAPE requer ≥ 10Y smoothed-earnings.
  - `CAL-ERP-BUYBACK-CROSS-COUNTRY` — buyback yield sparse / zero
    outside US.
  - `CAL-ERP-T1-SMALLER-MARKETS` — IT / ES / NL / PT extension.
  - `CAL-ERP-T1-NON-EA` — CA / AU / NZ / CH / SE / NO / DK extension.
- `docs/specs/overlays/erp-daily.md` §4 devia eventualmente captar
  que não-US depende de inputs não disponíveis — follow-up dedicado
  quando Phase 2.5 ship.
- `docs/milestones/m1-us-gap-analysis.md` pode referenciar este ADR
  para fechar a T1 uniformity gap formally.

## Referências

- Pre-flight findings: `docs/planning/week10-sprint-b-erp-t1-preflight-findings.md`
- Sprint B brief: `docs/planning/week10-sprint-b-erp-t1-brief.md`
- Sprint B retro: `docs/planning/retrospectives/week10-sprint-erp-t1-report.md`
- Spec afectado: `docs/specs/overlays/erp-daily.md`
- Backlog: `docs/backlog/calibration-tasks.md` §CAL-ERP-T1-PER-COUNTRY
- Commits: `feat(connectors): TE per-country equity index scaffolding`;
  `feat(connectors): Damodaran monthly implied ERP archive`;
  `feat(pipelines): daily_cost_of_capital Damodaran monthly live fallback`
- Convenção "compute, don't consume": `CLAUDE.md` §4
