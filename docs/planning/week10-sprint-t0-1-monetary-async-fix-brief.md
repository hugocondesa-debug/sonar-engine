# Sprint T0.1 — Monetary Pipeline Async Lifecycle Fix

**Branch**: `sprint-t0-1-monetary-async-fix`
**Worktree**: `/home/macro/projects/sonar-wt-t0-1-monetary-async-fix`
**Data**: 2026-04-23 Day 3 late afternoon (~18:00 WEST arranque)
**Operator**: Hugo Condesa (reviewer) + CC (executor)
**Budget**: 1-2h solo
**ADR-0010 tier scope**: N/A (refactor-only)
**ADR-0009 v2 TE Path 1 probe**: N/A (no new data fetch)
**Parent**: extends Sprint T0 — closes CAL-MONETARY-SINGLE-EVENT-LOOP

---

## §1 Scope (why)

**Sprint T0 acceptance §5 não atingida em full**: `sonar-daily-monetary-indices.service` ainda failed em systemd invocation pós-merge Sprint T0. Systemd entrou em restart loop 17:37-17:45 WEST antes de timer stop manual.

**Root cause identificada** (triage Day 3 pós-T0):

`src/sonar/pipelines/daily_monetary_indices.py` usa `asyncio.run()` **per-country** no dispatcher (linha 627 em `_live_inputs_builder_factory`, linha 745 em aclose loop). Cada `asyncio.run()` cria+destrói event loop. Connectors (`FredConnector`, `BisConnector`, `TEConnector`) mantêm `httpx.AsyncClient` com transport bound ao loop de criação → loop morto após country #1 → country #2+ falha `RuntimeError: Event loop is closed`.

Comentário linha 735-737 reconhece o bug — "aclose() may crash under asyncio event-loop churn (httpx backend)". Fix historicamente foi apenas try/except warning (linhas 741-748), não cura arquitectural.

**Log evidence (Apr 23 17:37:50-55)**:
```
country=US: monetary_pipeline.duplicate_skipped           ← OK (ran in loop L1)
country=DE: monetary_pipeline.duplicate_skipped           ← OK (ran in fresh loop L2)
country=PT: country_failed error='Event loop is closed'   ← first casualty
country=IT: country_failed error='Event loop is closed'
country=ES: country_failed error='Event loop is closed'
country=FR: country_failed error='Event loop is closed'
country=NL: country_failed error='Event loop is closed'
connector_aclose_error connector=FredConnector error='Event loop is closed'
connector_aclose_error connector=BisConnector error='Event loop is closed'
summary: n_failed=5 → exit 1
```

**Objectivo T0.1**: single event-loop lifecycle. systemd exit 0. Natural fire Apr 24 05:00 UTC verde.

---

## §2 Spec (what)

### 2.1 Single async context — pipeline main

Refactor `src/sonar/pipelines/daily_monetary_indices.py` para padrão canónico Python 3.12:

**Anti-pattern actual**:
```python
def main(date, countries):
    for country in countries:
        builder = _live_inputs_builder_factory(country, ...)  # asyncio.run()
        # persist, summary accounting
    for conn in connectors:
        asyncio.run(conn.aclose())                            # new loop + dead client
```

**Target pattern**:
```python
async def _run_pipeline(date, countries):
    # Single event loop for entire pipeline
    async with contextlib.AsyncExitStack() as stack:
        connectors = await _build_connectors(stack)  # async with aclose lifecycle
        for country in countries:
            try:
                inputs = await _build_inputs(country, date, connectors)
                await _persist_country(country, inputs)
            except Exception as e:
                log.error("monetary_pipeline.country_failed", country=country, error=str(e))
    # AsyncExitStack handles aclose() inside the same loop

def main(date, countries):
    asyncio.run(_run_pipeline(date, countries))  # single run at process entry
```

### 2.2 Connector async context — if not already

Verify `src/sonar/connectors/fred.py`, `bis.py`, `te.py` têm `__aenter__` / `__aexit__` ou são compatíveis com `AsyncExitStack.enter_async_context()`. Se não têm, adicionar wrapper:

```python
class FredConnector:
    async def __aenter__(self):
        self._client = httpx.AsyncClient(...)
        return self
    async def __aexit__(self, exc_type, exc, tb):
        await self._client.aclose()
```

**Scope gate**: se `base.BaseConnector` já define pattern assíncrono, reuse. Se não, implementar em `BaseConnector` + inherit. Evitar duplicar em cada connector.

### 2.3 `_live_inputs_builder_factory` adjustment

Factory actual devolve builder sync (que internamente faz `asyncio.run`). Refactor para devolver **async function** que pode ser `await`ed:

```python
def _live_inputs_builder_factory(country, connectors) -> Callable[[], Awaitable[Inputs]]:
    async def builder() -> Inputs:
        # await connector calls directly, no asyncio.run
        data = await connectors["te"].fetch(...)
        return Inputs(...)
    return builder
```

Pipeline main `await builder()` em vez de `builder()`.

### 2.4 Remove end-of-pipeline aclose loop

Linhas 735-748 (manual `asyncio.run(conn.aclose())` + try/except warning) → **delete**. `AsyncExitStack` gere lifecycle automaticamente. Warning `connector_aclose_error` deixa de ser emit (desejado — evento desaparece porque bug desaparece).

### 2.5 Exit code sanitization — ADR-0011 Principle 3 completion

Critério actual (implícito): `n_failed > 0 → exit 1`.

Critério revisto — exit 0 se:
- `n_persisted + n_skipped + n_duplicate + n_no_inputs > 0` (pipeline produziu output útil OR expected-state skips)
- Apenas infrastructure failures (TE HTTP 500, DB lock, etc.) devem contar como n_failed structural.

Critério actual está a tratar `Event loop is closed` como failure — legítimo porque era bug. Pós-fix, n_failed só deve incrementar em genuine data errors (upstream missing data, TE rate limit, etc.), não errors transient de infra.

Exit policy refinada:
- Exit 0: ≥1 country processed (persist/skip/duplicate/no_inputs all OK)
- Exit 1: pipeline-level uncaught exception (ex: DB connection fail, config missing) OU todos os countries failed com erro não-recuperável

### 2.6 Regression tests

Novos tests em `tests/pipelines/test_daily_monetary_indices.py`:

- `test_async_lifecycle_single_loop`: mock connectors, run pipeline com 3 countries, assert `asyncio.get_event_loop()` retorna same loop within whole run.
- `test_country_failure_isolation`: mock country 2 to raise `RuntimeError`, assert countries 1 + 3 persist OK, summary reflects 1 failure.
- `test_exit_code_success_on_all_duplicate`: all countries return duplicate_skipped, assert process exit 0.
- `test_connector_aclose_lifecycle`: mock AsyncClient, assert aclose called exactly once per connector (via AsyncExitStack).

### 2.7 Systemd verification (ACCEPTANCE CRITICAL)

Após merge, verify NOT only via local CLI but via **systemd invocation** (Sprint T0 acceptance gap):

```bash
sudo systemctl start sonar-daily-monetary-indices.timer
sudo systemctl start sonar-daily-monetary-indices.service
sleep 180
systemctl is-active sonar-daily-monetary-indices.service    # expect: inactive or active
systemctl status sonar-daily-monetary-indices.service --no-pager | grep "Main PID.*status="  # expect: status=0
sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | grep -iE "error|failed|event loop" | head -10  # expect: empty
```

### 2.8 ADR-0011 amendment (retro-insert Principle 6)

Add to `docs/adr/ADR-0011-systemd-service-idempotency.md`:

> **Principle 6 — Async lifecycle discipline**: Pipelines usando connectors async devem ter **single `asyncio.run()` at process entry**. Zero `asyncio.run()` per-country ou per-task. Connectors managed via `AsyncExitStack` + `async with` context. Rationale: `httpx.AsyncClient` (e qualquer transport com transport layer stateful) binds to event loop on first I/O; loop churn kills connector for subsequent calls. Pattern: single entry `asyncio.run(_main())`, dispatcher loop `for country in countries: await process(country, connectors)`.

---

## §3 Commits plan

| Commit | Scope | Ficheiros esperados |
|---|---|---|
| **C1** | refactor: pipeline async lifecycle (AsyncExitStack + single asyncio.run) | `src/sonar/pipelines/daily_monetary_indices.py` |
| **C2** | refactor: connector `__aenter__`/`__aexit__` if needed | `src/sonar/connectors/base.py` ou connectors específicos |
| **C3** | refactor: exit code sanitization (ADR-0011 Principle 3 completion) | `src/sonar/pipelines/daily_monetary_indices.py` |
| **C4** | test: regression coverage async lifecycle | `tests/pipelines/test_daily_monetary_indices.py` |
| **C5** | docs: ADR-0011 amendment Principle 6 + CAL-MONETARY-SINGLE-EVENT-LOOP closure | `docs/adr/ADR-0011-*.md`, `docs/backlog/calibration-tasks.md` |
| **C6** | docs: Sprint T0.1 retrospective | `docs/planning/retrospectives/week10-sprint-t0-1-report.md` |

---

## §4 HALT triggers

**HALT-0 (structural)**:
- Se connectors (Fred/Bis/TE) tiverem state sharing cross-request que impede `async with` pattern (ex: auth token refresh depende de state mutável) → STOP. Report. Hugo decide refactor broader.
- Se refactor quebrar outros pipelines que importam `_live_inputs_builder_factory` (ex: backfill scripts) → STOP. Inventariar dependentes primeiro.

**HALT-material**:
- Se pós-C1+C2+C3 systemd service ainda failed com event loop error → STOP. Root cause different from diagnose, precisa inspeção adicional.
- Se AsyncExitStack pattern introduzir latency > 2x baseline actual → STOP. Performance regression unexpected.

**HALT-scope**:
- Qualquer item demandar connector rewrite completo → STOP. Out of scope T0.1.
- Qualquer item demandar migration DB → STOP.
- Tocar em `daily_curves.py` ou `daily_cost_of_capital.py` → STOP (scope lock monetary-only).

**HALT-security**: standard.

---

## §5 Acceptance

**Primary (systemd health)**:
```bash
sudo systemctl start sonar-daily-monetary-indices.timer
sudo systemctl start sonar-daily-monetary-indices.service
sleep 180
systemctl is-active sonar-daily-monetary-indices.service       # expect: inactive (exit 0) OR active
sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
  grep -iE "event loop is closed|connector_aclose_error|country_failed" | wc -l  # expect: 0
```

**Secondary (summary legitimacy)**:
```bash
sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
  grep "monetary_pipeline.summary"
# Expected: n_persisted>=2 OR n_duplicate>=2 (US + DE at minimum), n_failed=0, n_no_inputs covers EA members expected skip
```

**Tertiary (regression safety)**:
- `uv run pytest tests/pipelines/test_daily_monetary_indices.py -v` — all pass, coverage delta positive
- `uv run pre-commit run --all-files` — clean

**Quaternary (docs)**:
- ADR-0011 Principle 6 shipped
- CAL-MONETARY-SINGLE-EVENT-LOOP marked closed em `docs/backlog/calibration-tasks.md`
- Retro shipped

**Full 3-service systemd verify (after merge)**:
```bash
sudo systemctl start sonar-daily-curves.service && sleep 120 && systemctl is-active sonar-daily-curves.service
sudo systemctl start sonar-daily-monetary-indices.service && sleep 180 && systemctl is-active sonar-daily-monetary-indices.service
sudo systemctl start sonar-daily-cost-of-capital.service && sleep 120 && systemctl is-active sonar-daily-cost-of-capital.service
```
Expected: all three = `inactive` (clean exit 0) OR `active`.

**Timer re-enable** (after acceptance passes):
```bash
sudo systemctl start sonar-daily-monetary-indices.timer
systemctl is-active sonar-daily-monetary-indices.timer  # expect: active
```
(Timer foi stopped manually em 17:45 WEST para interromper restart loop. Re-enable é final step of T0.1.)

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week10-sprint-t0-1-report.md`:

1. **Pattern identificada**: `asyncio.run()` per-country anti-pattern. Discovery via log `Event loop is closed` + comentário pre-existente linha 735.
2. **Fix canónico**: Single `asyncio.run()` + `AsyncExitStack` + connector `async with`. Shipped em T0.1, elevado a ADR-0011 Principle 6.
3. **Sprint T0 lesson escalada**: CC acceptance §5 marcou "local runs exit 0" como passed, mas systemd invocation path não foi verified. Gap: local CLI usa `python -m sonar.pipelines.daily_monetary_indices` directamente; systemd usa wrapper `bash -lc 'uv run python -m ...'`. O wrapper altera env (PATH, CWD, shell). Sprint T0 acceptance deveria ter incluído systemd invocation explicitamente.
4. **Lesson permanent fix candidate**: brief template v3 acceptance section deve ter "systemd OR CLI both" se pipeline runs via service. Propor em Week 10 retro.
5. **Net effort**: T0 (3.5h planned, ~4h actual) + T0.1 (1-2h) = ~5.5h total para prod healing Week 10. Alta density mas gating para ritmo Week 11.

---

## §7 Execution notes

- **Zero `asyncio.run()` per-country** — hard rule. Se aparecer alguma ocorrência no refactor final, C1 not done.
- **Tests first for C4** — faz `test_async_lifecycle_single_loop` falhar contra código actual antes de refactor, assert passa pós-refactor. Proof.
- **AsyncExitStack import**: `from contextlib import AsyncExitStack`. Standard library Python 3.12.
- **Pre-commit double-run** (Week 10 Day 2 lesson #2).
- **tmux cleanup** no sprint_merge.sh Step 10.
- **Systemd verify como PRIMARY acceptance** — não aceitar "shipped" sem `systemctl is-active` clean.

---

*End of brief. Ship and close T0 cycle. Foundation hardening complete.*
