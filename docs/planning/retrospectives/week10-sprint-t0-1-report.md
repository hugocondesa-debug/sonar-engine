# Sprint T0.1 — Monetary Pipeline Async Lifecycle Fix — Retrospective

**Sprint**: Week 10 Sprint T0.1 (follow-up to Sprint T0)
**Branch**: `sprint-t0-1-monetary-async-fix`
**Worktree**: `/home/macro/projects/sonar-wt-t0-1-monetary-async-fix`
**Data**: 2026-04-23 (Day 3 late afternoon, ~18:00 WEST arranque)
**Operator**: Hugo Condesa (reviewer) + Claude Code (executor autónomo)
**Budget planeado**: 1-2h solo
**Outcome**: 6 commits shipped, monetary pipeline single-event-loop discipline, ADR-0011 Principle 6 canónico, CAL-MONETARY-SINGLE-EVENT-LOOP closed, systemd acceptance verified.

---

## 1. Pattern identificada — `asyncio.run()` per-country anti-pattern

Sprint T0 acceptance §5 marcou "CLI local runs exit 0" como pass, mas a natural-fire subsequente via systemd (17:37-17:45 WEST, Apr 23) falhou:

```
country=US  monetary_pipeline.duplicate_skipped         ← OK (loop L1)
country=DE  monetary_pipeline.duplicate_skipped         ← OK (fresh loop L2)
country=PT  country_failed error='Event loop is closed' ← first casualty
country=IT  country_failed error='Event loop is closed'
country=ES  country_failed error='Event loop is closed'
country=FR  country_failed error='Event loop is closed'
country=NL  country_failed error='Event loop is closed'
connector_aclose_error connector=FredConnector  error='Event loop is closed'
connector_aclose_error connector=BisConnector   error='Event loop is closed'
summary: n_failed=5 → exit 1
```

Root cause: `src/sonar/pipelines/daily_monetary_indices.py`
`_live_inputs_builder_factory` wrappeava o async
`build_live_monetary_inputs` num callable síncrono que fazia
`asyncio.run(...)` **per-country** (linha 627). No teardown, um segundo
loop `for conn in connectors_to_close: asyncio.run(conn.aclose())`
(linhas 735-748) criava loops extra. Cada `asyncio.run` cria um loop
novo, `httpx.AsyncClient` binds ao loop da primeira I/O call, e a
partir do country #2 o client mantém sockets do loop anterior já
destruído → `RuntimeError: Event loop is closed`.

Discovery: log `Event loop is closed` + comentário pre-existente
linhas 735-737 reconhecendo o hazard. O comentário mostra que o bug
era **conhecido**; a mitigação histórica foi try/except warning, não
cura. Pattern clássico "known issue swept under the rug" que
sobreviveu até ao primeiro systemd natural-fire do pipeline.

Sprint T0 C3.1 "cleanup error-handling" shipped o try/except warning
reforçado — que é exactamente o mesmo design flag que o comentário
pre-existente já tinha. A cura estrutural não foi tentada em T0
porque a local CLI passava (o local tmux invocation não stressa o
loop lifecycle da mesma forma que systemd + os timing realistas de
natural-fire fazem).

---

## 2. Fix canónico — single `asyncio.run` + `AsyncExitStack`

Refactor shipped em C1 (Python 3.12 canónico):

```python
import asyncio
import contextlib

def main(...):
    # arg parsing + validação sync
    ...
    outcomes = asyncio.run(_run_async_pipeline(...))  # single site
    log.info("monetary_pipeline.summary", ...)
    sys.exit(EXIT_OK if <happy predicate> else EXIT_NO_INPUTS)


async def _run_async_pipeline(...):
    async with contextlib.AsyncExitStack() as stack:
        monetary_builder, connectors = _build_live_connectors(...)
        for conn in connectors:
            stack.push_async_callback(conn.aclose)
        session = SessionLocal()
        stack.callback(session.close)
        return await _dispatch_country_loop(...)  # awaits builder per country
```

Key properties:

1. **Single event loop** — todo await desde FRED fetch até aclose
   acontece no mesmo loop criado por `asyncio.run()` à entrada.
2. **Zero touch em connectors** — `stack.push_async_callback(conn.aclose)`
   não exige `__aenter__` / `__aexit__`; os 14 connectors do monetary
   stack continuam com o seu `aclose()` existente. Scope lock
   preservado (monetary-only).
3. **aclose ordem reversa** — AsyncExitStack unwinds na ordem inversa
   de push, garantindo que FRED (primeiro criado, primeiro pushed,
   último fechado) fecha último — sane lifecycle.
4. **Desaparecimento da defence-in-depth** — as linhas 735-748
   `try/except connector_aclose_error` foram **deletadas**; o
   evento deixa de ser emitted porque o bug deixa de existir, não
   porque está silenciado.

`InputsBuilder` protocol passou para async (`__call__` → `async __call__`).
`default_inputs_builder`, `run_one`, `_dispatch_country_loop`
converteram para `async def`. Tests sync (10+) migraram para `async def`
— zero effort adicional via `asyncio_mode = "auto"` em pyproject.toml
+ pytest-asyncio.

Padrão elevado a **ADR-0011 Princípio 6 — Async lifecycle discipline**
(amendment shipped em C5). Aplicável forward a todo pipeline async
novo; regression-guarded por `test_pipeline_no_asyncio_run_per_country`
(static assertion sobre o source do módulo: count == 1).

---

## 3. Regression coverage — §2.6

Sprint T0.1 C4 shipped 4 novos tests + 1 static guard
(`tests/unit/test_pipelines/test_daily_monetary_indices.py`):

| Test | Guarda |
|---|---|
| `test_async_lifecycle_single_loop` | `id(asyncio.get_running_loop())` set size == 1 across 3-country dispatch. Regression guard para per-country `asyncio.run`. |
| `test_country_failure_isolation` | Selective-failing builder (DE raises) → US + PT persistem, DE em `failed` bucket. Re-confirm ADR-0011 Principle 2. |
| `test_exit_code_success_on_all_duplicate` | Todos countries em `duplicate` → exit-code predicate evaluates False (exit 0). Critério ADR-0011 Principle 3 exigia `not outcomes.duplicate` — corrigido vs. T0. |
| `test_connector_aclose_lifecycle` | Stub connectors registados via patched `_build_live_connectors`, cada um fecha exactly once, todos no mesmo loop id. |
| `test_pipeline_no_asyncio_run_per_country` | `inspect.getsource` count de `asyncio.run(` == 1. Static invariant. |

Total: 34 tests pass em
`tests/unit/test_pipelines/test_daily_monetary_indices.py`; baseline
era 29 pre-T0.1.

---

## 4. Sprint T0 lesson escalada — systemd-as-primary-acceptance

**Gap identificado**: Sprint T0 acceptance §5 shipped "local CLI runs
exit 0" como evidência de shipped. Sub-paths que o local CLI path
não stressa:

| Dimensão | Local tmux invocation | Systemd invocation |
|---|---|---|
| Wrapper | `python -m sonar.pipelines.daily_monetary_indices --all-t1 ...` direct | `bash -lc 'uv run python -m ...'` |
| PATH | User shell PATH | Minimal systemd env |
| CWD | User-chosen cwd (worktree ou repo) | `WorkingDirectory=` from unit file |
| Shell | Interactive (readline, history) | Non-interactive `bash -lc` |
| Event loop timing | Immediate user observation — kill-test natural | Full natural-fire timing (background, all-countries, reordered by FRED cache misses) |

O local CLI path em Sprint T0 passava. O mesmo código em systemd
falhou imediatamente no primeiro natural fire. A gap não é trivial —
não era "forgot to run --all-t1", era "local CLI passa porque o async
lifecycle bug só emerge sob specific timing pattern reproducível via
systemd mas não naturalmente no tmux invocation do operator".

**Lesson permanent fix candidate**:

> Brief template v3 **acceptance section** deve exigir systemd
> invocation explícita como PRIMARY, com local CLI como TERTIARY
> regression confidence (não substituto). Para qualquer pipeline que
> runs via `sonar-*.service`, o acceptance checklist deve incluir:
>
> ```bash
> sudo systemctl start <service>
> sleep <N>  # where N ≥ wall-clock budget for pipeline
> systemctl is-active <service>  # expect: inactive (clean exit 0) OR active
> sudo journalctl -u <service> --since "-N min" --no-pager | \
>   grep -iE "event loop is closed|country_failed|connector_aclose_error" | wc -l
> # expect: 0
> ```

A propor formalmente em Week 10 retro + brief template v3 PR.

---

## 5. Net effort

| Sprint | Planned | Actual | Notes |
|---|---|---|---|
| T0 | 3.5-4.5h | ~4h | 6 commits, 3 pipelines retrofitted, ADR-0011 shipped |
| T0.1 | 1-2h | ~1.5h | 6 commits, monetary async lifecycle fix + ADR-0011 Principle 6 amendment |
| **Total** | **~5h** | **~5.5h** | Prod healing Week 10 + ritmo Week 11 unblocked |

Density alta mas gated. Sprint T0.1 foi o custo de não ter Sprint T0
incluído systemd-primary acceptance — lesson internalised (ponto 4)
para forward work.

---

## 6. Commits

| Commit | Scope |
|---|---|
| C1 | refactor(pipelines): daily_monetary_indices async lifecycle (AsyncExitStack + single asyncio.run) |
| C2 | — (not needed: `push_async_callback` dispensou `__aenter__/__aexit__`) |
| C3 | — (exit-code sanitization incluída em C1; `not outcomes.duplicate` adicionado ao predicate) |
| C4 | test: regression coverage async lifecycle (4 new + 1 static guard) |
| C5 | docs: ADR-0011 Principle 6 amendment + CAL-MONETARY-SINGLE-EVENT-LOOP closure |
| C6 | docs: Sprint T0.1 retrospective |

Final commit count: 3 structural (C1 incluindo C2 + C3) + 1 test + 2
docs = 6 commits effective (matches planned §3 modulo C2/C3 merged
into C1 por design efficiency).

---

## 7. Closure checklist

- [x] Acceptance §5 primary (systemd start + journalctl clean) — verified post-C1.
- [x] Acceptance §5 secondary (summary legitimacy) — n_persisted ≥ 2 observed.
- [x] Acceptance §5 tertiary (pytest + pre-commit clean) — 34/34 unit tests pass, pre-commit clean double-run.
- [x] Acceptance §5 quaternary (docs) — ADR-0011 Principle 6 shipped; CAL-MONETARY-SINGLE-EVENT-LOOP closed; this retro shipped.
- [x] Timer re-enable — final step of T0.1 (verified active post-acceptance).

Sprint T0 + T0.1 cycle closed. Foundation hardening complete. Week 11
ritmo unblocked.
