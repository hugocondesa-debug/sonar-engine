# Sprint 8 — Hypothesis ranking + root cause confirmação (Commit 2)

**Brief**: [`week11-sprint-8-test-pollution-rootcause-brief.md`](week11-sprint-8-test-pollution-rootcause-brief.md).
**Pre-flight audit**: [`week11-sprint-8-pre-flight-audit.md`](week11-sprint-8-pre-flight-audit.md).
**Status**: causa raiz identificada com PYTHONTRACEMALLOC=10 instrumentation; a fix landa Commit 3.
**Date**: 2026-04-26.

---

## 1. Hipóteses iniciais (brief §8 priors)

| # | Hipótese | Prior brief |
|---|---|---|
| H1 | Cassette VCR state mutation entre tests | favorita brief §8 |
| H2 | Async cleanup pollution (event loop / socket leak) | secundária brief §8 |
| H3 | Shared DB session / engine | terciária brief §8 |

---

## 2. Empirical evidence (Commit 1 baseline)

5x full-suite + 3x targeted runs. Resultado:

| Eixo | Full-suite (5x) | Targeted (cycles + te_indicator, 3x) |
|---|---|---|
| Falhas | 5/5 (1 falha cada) | 0/3 |
| Sintoma | `PytestUnraisableExceptionWarning` (`ResourceWarning: unclosed event loop` + 2 sockets) | n/a |
| Atribuição | 4x `te_indicator equity[FR]`, 1x `economic_ecs whipsaw` | n/a |

Conclusão Commit 1: o sintoma flutua entre testes — sintoma é *consequência*
de leak num teste anterior, não defeito do teste atribuído.

---

## 3. Tracemalloc instrumentation — root cause source

`PYTHONTRACEMALLOC=10 uv run pytest -m "not slow" --no-cov --tb=long` (Commit 2):

Object allocation site verbatim (`/tmp/sprint8-baseline/tracemalloc.log`):

```
File "pytest_asyncio/plugin.py", line 805
    with _temporary_event_loop_policy(new_loop_policy):
File "pytest_asyncio/plugin.py", line 618
    old_loop = _get_event_loop_no_warn()
File "pytest_asyncio/plugin.py", line 649
    return asyncio.get_event_loop()
File "asyncio/events.py", line 699
    self.set_event_loop(self.new_event_loop())
File "asyncio/events.py", line 720
    return self._loop_factory()
File "asyncio/unix_events.py", line 64
    super().__init__(selector)
File "asyncio/selector_events.py", line 66
    self._make_self_pipe()
File "asyncio/selector_events.py", line 120
    self._ssock, self._csock = socket.socketpair()
```

Cada par de sockets `fd=12, fd=13` (`type=1, proto=0`) é **o self-pipe**
(`socket.socketpair()`) instanciado por `_UnixSelectorEventLoop` via
`_make_self_pipe`. O event loop nunca é usado nem fechado — é orphan.

---

## 4. Mecanismo desambiguado

`_temporary_event_loop_policy` (pytest_asyncio/plugin.py:615-626):

```python
@contextlib.contextmanager
def _temporary_event_loop_policy(policy):
    old_loop_policy = _get_event_loop_policy()
    try:
        old_loop = _get_event_loop_no_warn()   # ← line 618
    except RuntimeError:
        old_loop = None
    _set_event_loop_policy(policy)
    try:
        yield
    finally:
        _set_event_loop_policy(old_loop_policy)
        _set_event_loop(old_loop)
```

`_get_event_loop_no_warn` (linhas 641-649) chama `asyncio.get_event_loop()`
sob `simplefilter("ignore", DeprecationWarning)`. Em Python 3.12.3, o
default policy auto-cria um novo loop quando:

```python
# /usr/lib/python3.12/asyncio/events.py:678-699
if (self._local._loop is None and
        not self._local._set_called and
        threading.current_thread() is threading.main_thread()):
    warnings.warn('There is no current event loop', DeprecationWarning, …)
    self.set_event_loop(self.new_event_loop())
```

A `DeprecationWarning` é silenciada pelo wrapper, mas o loop é criado.
Esse loop é capturado em `old_loop`, restaurado em `finally:
_set_event_loop(old_loop)`. Se mais tarde o "current loop" é trocado
por outro mecanismo, o orphan original perde referência → GC →
`BaseEventLoop.__del__` emite `ResourceWarning`.

### Trigger pattern

Tests que chamam `asyncio.run()` (directamente ou indirectamente via
helpers tipo `run_one()`) limpam o "current loop" da default policy
(`Runner.close()` → `events.set_event_loop(None)`). Próxima invocação
de `_temporary_event_loop_policy` cai no auto-create branch nalgum
ponto do encadeamento de fixtures + policy switches.

`run_one()` em `src/sonar/pipelines/daily_overlays.py:597` invoca
`asyncio.run(compute_all_overlays(bundle))`. Tests sync chamam-no
**42 vezes** em `tests/unit/test_pipelines/test_daily_overlays.py`. Cada chamada potencialmente alimenta o ciclo de orphan loops.

Sprint Q.0.5 retro `week11-sprint-q-0-5-t1-cohort-unification-report.md`
§3.3 (Discovery #3) já observou padrão semelhante e shippou um fix
parcial (`_stub_main` que monkeypatch `asyncio.run`) **apenas em
`test_daily_monetary_indices.py`**. Outras suites de pipeline tests
nunca receberam o stub.

---

## 5. Hypothesis ranking final

| # | Hipótese | Status | Confidence |
|---|---|---|---|
| H1 | Cassette VCR state mutation | **falsified** Commit 1 §6 (repo usa `pytest-httpx`, não `vcrpy`); targeted subset clean | high |
| H2 | Async cleanup pollution (orphan event loop + sockets) | **confirmed** via tracemalloc allocation site Commit 2 §3 | very high |
| H3 | Shared DB session / engine | **falsified** Commit 1 §5 (function-scoped fixtures, `engine.dispose()` em teardown, in-memory SQLite per test) | high |

---

## 6. Fix design — Commit 3

### Critério de design

- Princípio: address root cause, não o sintoma. Auto-create branch do
  `BaseDefaultEventLoopPolicy.get_event_loop()` é o gerador de orphans.
- Constraint: zero impacto em código de produção; mudança contida ao
  test harness.
- Constraint: zero impacto em testes que dependem de current loop
  legítimo (audit confirmou que nenhum código sonar usa
  `asyncio.get_event_loop()` fora de async functions — e dentro de
  async functions o running loop é retornado sem auto-create).

### Proposta

Adicionar autouse session-scoped fixture em `tests/conftest.py`:

```python
import asyncio
import pytest

@pytest.fixture(scope="session", autouse=True)
def _disable_asyncio_auto_create_loop() -> None:
    """Disable asyncio default policy's auto-create branch in get_event_loop().

    Sprint 8 root cause (PYTHONTRACEMALLOC=10):
    pytest-asyncio's `_get_event_loop_no_warn` calls `asyncio.get_event_loop()`
    which on Python 3.12 still auto-creates a fresh `_UnixSelectorEventLoop`
    when the default policy's `_local._set_called == False`. The orphan
    loop holds two unclosed self-pipe sockets and surfaces as
    `PytestUnraisableExceptionWarning` at GC time, failing a random
    subsequent test under `filterwarnings=error`.

    Force `_set_called=True` once at session start so future
    `get_event_loop()` calls without an explicit `set_event_loop`
    raise `RuntimeError` instead of auto-creating. pytest-asyncio's
    `_temporary_event_loop_policy` already handles `RuntimeError` →
    `old_loop = None`, so the contract is preserved.
    """
    policy = asyncio.get_event_loop_policy()
    policy._local._set_called = True  # type: ignore[attr-defined]
```

### Why this works

1. `policy._local._set_called=True` desabilita o branch de auto-create
   (`if not self._local._set_called` em `events.py:680` falha).
2. `get_event_loop()` agora ou retorna `_local._loop` se estiver
   set, ou levanta `RuntimeError` se `_loop is None`.
3. pytest-asyncio's `_temporary_event_loop_policy` já trata o
   `RuntimeError` (linhas 619-620) → `old_loop = None`. Sem orphan.
4. Tests `async` continuam a funcionar via Runner do pytest-asyncio
   (que cria + fecha próprio loop via `events.set_event_loop` explícito,
   bypassing auto-create).
5. Tests sync que chamam `asyncio.run()` continuam a funcionar (Runner
   interno do `asyncio.run` não usa auto-create).

### Risk surface

| Risk | Mitigation |
|---|---|
| Algum teste depender de `get_event_loop()` auto-create | Audit confirmou zero usos directos em sonar/* fora de async functions |
| pytest-asyncio futuro mudar contrato | Fixture é hot-path defensive; remoção é one-line revert |
| Interacção com `policy._local` private attr | Documentado upstream (cpython source); estável em 3.10+ |

---

## 7. Plano Commit 3

1. Adicionar fixture autouse session-scoped a `tests/conftest.py`.
2. Run 5x consecutive full-suite → verificar zero flakes.
3. Run 3x targeted subset → verificar regressão none.
4. Coverage delta check (alvo: stable).
5. Commit fix + verificação evidence.

Acceptance:
- 5x consecutive full-suite PASS clean.
- 3x targeted subset PASS clean.
- Pre-commit 2x.
- Pre-push gate green.

Outcome esperado: **A** (root cause + single fix).

---

## 8. Fallback plan

Se o fix não resolver 5x consecutive PASS:

1. Adicionar filterwarnings entries específicos:
   ```toml
   "ignore:Exception ignored in.*BaseEventLoop.__del__:pytest.PytestUnraisableExceptionWarning"
   "ignore:Exception ignored in.*<socket\\.socket:pytest.PytestUnraisableExceptionWarning"
   ```
2. Trade-off: filtra também leaks legítimos de user code; documentar como
   KNOWN-BACKGROUND e file CAL retroactivo para audit posterior.

Se fallback também não chegar a 5x clean: outcome **C** (escalation),
file `CAL-TEST-POLLUTION-DIAGNOSED-PHASE25` com hipótese + tracemalloc
evidence.
