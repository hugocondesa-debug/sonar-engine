# ADR-0011: Systemd service idempotency + partial-persist recovery

**Status**: Accepted
**Data**: 2026-04-23
**Decisores**: Hugo Condesa (7365 Capital)
**Consultados**: Claude Code (Sprint T0 executor)

## Contexto

Overnight Apr 23 2026 (natural fire via systemd timers shipped Week 8
Sprint N) três serviços daily falharam em cascade:

1. `sonar-daily-curves.service` — exit 1 (07:01) → exit 3 (07:11) →
   systemd abort (07:21).
2. `sonar-daily-monetary-indices.service` — exit 3 (08:10) → systemd
   abort (08:20).
3. `sonar-daily-cost-of-capital.service` — exit 1 (09:40) → systemd
   abort (09:50).

Root cause (post-mortem manhã Apr 23):

- `daily_curves` Run 1 processou US completo — row persistida em
  `yield_curves_spot` com `UNIQUE(country_code, date, methodology_version)` —
  depois crashed (`RetryError[HTTPStatusError]`) antes de IT/ES/FR/PT/NL
  serem tentados.
- Systemd retry (Run 2) re-iniciou o pipeline do início. US re-fetched
  + re-fit + INSERT → violação UNIQUE → `DuplicatePersistError` → exit 3.
- Systemd retry (Run 3) bateu `StartLimitBurst` → abort.
- Downstream: `daily_monetary_indices` tentou ler curves IT/ES/FR/PT/NL
  para Apr 22 → no forwards rows → treated `no_inputs` como fatal →
  exit 3. `daily_cost_of_capital` idem via `InsufficientDataError` no
  NSS spot reader → exit 1.

Gap de design que emergiu: os pipelines foram escritos com a assumpção
implícita **"runs são atómicos: tudo ou nada"**. A realidade produção
é: runs podem ser parciais (partial-persist), retries acontecem
automaticamente, e o retry tem de ser bit-for-bit idempotente. Qualquer
"fatal on duplicate" ou "fatal on upstream-missing" no pipeline é uma
bomba-relógio que vai explodir em produção sob sistemd retry.

A decisão tem de ser tomada agora (não depois) porque:

1. Week 10 Sprint N shipped systemd scheduling para produção — os 9
   daily pipelines estão todos em iminência de natural-fire recorrente.
2. Sprints posteriores (Week 10 M-O) vão adicionar mais pipelines
   (economic cycle full wire, ERP per-country, M3 expansion). Sem
   canonical pattern, cada pipeline novo arrisca o mesmo bug.
3. O ADR canoniza o **como pensar** sobre partial-persist em produção,
   não só o fix pontual. Downstream-consumable como guidance.

## Decisão

Adoptamos **5 princípios não-negociáveis** para qualquer pipeline
scheduled por systemd (e por extensão, qualquer batch pipeline em
produção):

### Princípio 1 — Idempotency per row

Duplicate detection = **skip + continue**, nunca `raise`.

Implementação típica (ordem preferencial):

1. Pre-INSERT existence check por UNIQUE key
   (`SELECT 1 FROM <table> WHERE <unique_cols>`). Se existe, skip +
   `log.info("<pipeline>.skip_existing", …)`.
2. Quando pre-check não é prático (ex: persistência multi-row atómica),
   catch `DuplicatePersistError` no dispatcher + `log.info` +
   continue. Duplicate é **info**, não **error** ou **warning**.

Rationale: systemd retries são frequentes por design. Tratar duplicado
como erro força exit ≠ 0 em runs que deveriam ser no-ops. Pre-check
poupa network + compute (importante para fetchers como FRED/TE/ECB).

### Princípio 2 — Per-country isolation

Dispatcher loop com `try/except Exception as e` **por unit-of-work**
(country, ou country × index, ou country × date — o mais atómico que
o pipeline suporta).

```python
for country in targets:
    try:
        run_one(country, …)
    except Exception as exc:
        log.error("pipeline.country_failed", country=country, error=str(exc))
        failed.append(country)
        continue  # nunca sai do loop por exception num single unit
```

Rationale: Day 3 Apr 23 pattern — US passou Apr 22 mas IT crashed.
No dispatcher old, a exception do IT matou o pipeline todo, perdendo
ES/FR/PT/NL que podiam ter passado. Cada country é independente.

### Princípio 3 — Exit codes sanitized

Exit contract explícito:

- **0** — happy path OR expected skips OR duplicate (idempotent re-run).
- **1** — uncaught exception ou todos os units failed de forma
  genuína (não recuperável).
- **3** — spec deviation (`NotImplementedError` genuíno num path que
  devia estar implementado). Reservado, não usar para duplicados.

Corollary: "partial success" (alguns países persistiram, outros
skipped por upstream absent) → exit **0**. Operators inspeccionam logs
+ `sonar status` para drilldown; exit code comunica pipeline-ran-OK,
não coverage-complete.

### Princípio 4 — Summary emit end-of-run

Log `<pipeline>.summary` end-of-run com:

```
persisted=N skipped=M failed=K
countries_ok=[…]
countries_skipped=[…]
countries_failed=[…]
```

Rationale: diagnose post-hoc de runs systemd sem intervention. Log é
o único artefacto disponível — `journalctl -u <service> --since …`
deve dar aos operators o picture completo sem precisar re-run.

### Princípio 5 — Partial-persist recovery

**Run N+1 assume que o state deixado por Run N pode ser parcial.**

Consequências:

- Cada unit (country × index × date) é um checkpoint independente.
- Não há "flush final" que comita tudo junto. Cada unit comita quando
  termina.
- Re-runs são **sempre safe**. Run 2 em cima de Run 1 (partial) é
  normal, não excepcional.
- Se um pipeline tem dependências cross-unit (ex: M3 precisa de
  forwards de multiple countries), o dependente resolve-se at-read-time
  — não assume completude do produtor.

### Princípio 6 — Async lifecycle discipline

**Pipelines que usam connectors async têm de ter exactly um
`asyncio.run()` à entrada do processo.** Zero `asyncio.run()`
per-country, per-task, ou per-connector aclose. Connectors async
são registados num `contextlib.AsyncExitStack` (ou equivalente
`async with`) para garantir que o loop que os criou é o mesmo que
executa o `aclose()` no unwind.

Pattern canónico:

```python
import asyncio
import contextlib

def main(...):
    # arg parsing, validação sync
    ...
    outcomes = asyncio.run(_run_async_pipeline(...))  # single site, process entry
    log.info("pipeline.summary", ...)
    sys.exit(EXIT_OK if <happy predicate> else EXIT_NO_INPUTS)


async def _run_async_pipeline(...):
    async with contextlib.AsyncExitStack() as stack:
        connectors = _build_connectors(...)
        for conn in connectors:
            stack.push_async_callback(conn.aclose)
        # dispatcher loop awaits inputs per country no mesmo loop
        for country in targets:
            await run_one(country, ..., connectors=...)
```

Rationale: `httpx.AsyncClient` (e qualquer transport async com
transport-layer stateful — `aiohttp.ClientSession`, `asyncpg.Pool`,
etc.) **binds to the event loop on first I/O**. Criar/destruir loops
mata o transport bound ao loop anterior: o próximo `await` crasha
com `RuntimeError: Event loop is closed` ou similar. Anti-pattern
típico é `asyncio.run()` dentro de um wrapper síncrono chamado em
loop — cada chamada cria um loop novo, o cliente persiste sockets
do loop anterior, e a partir da segunda iteração tudo crasha.

O `AsyncExitStack.push_async_callback(conn.aclose)` garante que o
`aclose()` executa **dentro do loop que criou o client**, no reverse
order de registration, no unwind do `async with` — exactamente onde
os sockets ainda são válidos. Isto elimina o try/except
`connector_aclose_error` defensivo (antes era defence in depth
contra o anti-pattern; depois não há anti-pattern, não há erro).

Evidence de prod (Sprint T0.1 Apr 23 2026):

```
country=US  monetary_pipeline.duplicate_skipped       ← loop L1 OK
country=DE  monetary_pipeline.duplicate_skipped       ← loop L2 OK
country=PT  country_failed error='Event loop is closed' ← L1 transport dead
country=IT  country_failed error='Event loop is closed'
country=ES  country_failed error='Event loop is closed'
country=FR  country_failed error='Event loop is closed'
country=NL  country_failed error='Event loop is closed'
connector_aclose_error connector=FredConnector error='Event loop is closed'
summary: n_failed=5 → exit 1
```

Sprint T0.1 shipped o fix em `daily_monetary_indices.py` e este
princípio é retro-inserido como obrigação canónica para todo
pipeline async novo. Regression guard: `test_pipeline_no_asyncio_run_per_country`
conta `asyncio.run(` no source do módulo e falha se > 1 site existir.

---

## Alternativas consideradas

- **Opção A** ← escolhida. 5 princípios canónicos retrofitted em
  Sprint T0 para curves / monetary / cost-of-capital, aplicados
  forward a toda nova pipeline. Rationale: corrige bug imediato
  (3 services broken overnight) + estabelece disciplina duradoura +
  sem cost de migration estrutural.

- **Opção B — "transacção atómica end-of-run"**. Rejeitada. Requer
  refactor profundo dos builders para acumular todos os inserts num
  `session` único e commit at-end. Incompativel com `session.flush()`
  em `persist_nss_fit_result` (forwards/zero precisam de FK para
  `spot.fit_id` que só existe após flush). Também não resolve o bug
  fundamental: se Run 1 crashed a meio, Run 2 re-inicia do início e
  tem de ser idempotente regardless.

- **Opção C — "lock file para prevenir concurrent runs"**. Rejeitada.
  Systemd já garante single-instance per service. O problema não é
  concurrency, é retry-after-crash. Lock file é solução para problema
  errado.

- **Opção D — disable systemd retries** (`Restart=no`). Rejeitada. A
  retry policy actual (`Restart=on-failure`, `StartLimitBurst=3`,
  `StartLimitIntervalSec=600`) é razoável para recuperar de falhas
  transientes de network (FRED/TE timeout, DNS flap). Remover retries
  empurra o burden para alerting + manual-restart — pior DX para
  operator solo.

---

## Consequências

### Positivas

- Re-runs são sempre safe e produzem logs coherentes.
- Partial-persist (Run 1 crashed a meio) é recuperável por Run 2 sem
  intervention.
- Exit codes comunicam pipeline-ran-OK vs pipeline-broken, não coverage-
  status. Journal observability fica limpa (zero ERROR noise em runs
  correctos).
- Template reutilizável para Sprints M-O (economic full wire, ERP per-
  country, M3 expansion) — cada pipeline novo segue os 5 princípios.
- Expected-skip countries (EA periphery sem curves) já não geram
  exit ≠ 0 e não levam systemd a abort.

### Negativas / trade-offs aceites

- Operators têm de olhar para `<pipeline>.summary` + `sonar status`
  para coverage (exit code por si só é insuficiente). Aceite — já era
  true-in-practice; ADR apenas formaliza.
- Código de dispatcher tem mais ruído (per-country try/except +
  summary emit). Aceite — custo linear no número de pipelines,
  paga-se uma vez.
- Pre-INSERT existence check adiciona uma query SELECT por unit —
  overhead negligível (indexed lookup).
- Distinção "duplicate OK" vs "duplicate suspicious" é perdida — se
  Run 2 encontra um monte de duplicates inesperados (ex: operator
  assumiu wipe-and-reload), não há sinal. Aceite: auditoria é via
  `MAX(date)` + `COUNT(*)` por país na DB, não via exit code.

### Follow-ups requeridos

- Sprint T0 C2-C4: retrofit `daily_curves`, `daily_monetary_indices`,
  `daily_cost_of_capital` aos 5 princípios.
- Sprint T0 C5: backfill manual Apr 22 + Apr 23 para validar o novo
  código em produção contra `yield_curves_spot` UNIQUE.
- Sprints M/O (+ futuros): aplicar template aos novos pipelines.
  Pattern: dispatcher com per-country isolation + summary emit é
  obrigatório.
- Systemd tuning (Week 10 retrospective item): validar que
  `StartLimitIntervalSec=600s` + `StartLimitBurst=3` é o compromise
  certo. Se retries continuarem a abortar sob falhas legítimas (rare),
  esticar para 1800s + 5.

---

## Referências

- `docs/planning/week10-sprint-t0-prod-healing-brief.md` — brief
  operacional Sprint T0 (canonical spec deste ADR).
- `docs/planning/retrospectives/week10-sprint-n-systemd-retro.md` —
  Sprint N retro (systemd wiring Week 8 shipped).
- `docs/architecture/db-schema-reference.md` — tabelas + UNIQUE
  constraints canónicos (Principle 1 depende deste doc).
- `docs/ops/systemd-deployment.md` — ops operacional actual.
- `src/sonar/pipelines/daily_curves.py` — reference implementation dos
  5 princípios (Sprint T0 C2).
- `src/sonar/pipelines/daily_monetary_indices.py` — idem (Sprint T0 C3).
- `src/sonar/pipelines/daily_cost_of_capital.py` — idem (Sprint T0 C4).
