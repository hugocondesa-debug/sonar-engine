# Sprint 8 — Pre-flight audit + empirical baseline (Commit 1)

**Brief**: [`week11-sprint-8-test-pollution-rootcause-brief.md`](week11-sprint-8-test-pollution-rootcause-brief.md).
**Status**: HALT #0 cleared — proceed; HALT #1 (DONE-NULL) NOT triggered (flakes reprodutíveis).
**Date**: 2026-04-26.

---

## 1. Inputs (Sprint A retro §2.2 + brief §2)

Sprint A retrospective §2.2 + §4 cataloguing três famílias de flakes
out-of-scope (closure CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL):

| Família | Pattern Sprint A | Frequência reportada |
|---|---|---|
| `test_te_indicator.py` cassette tests | EA / SE / CA várias parametrizações | ~3-4/5 runs |
| `test_economic_ecs::test_fixture_us_2020_03_23_recession` | Intermittent | ~1/5 |
| `test_credit_cccs::TestComputeCccsEndToEnd::test_happy_full_stack` | Intermittent | ~1/5 |

Hipótese A do brief §8 (cassette VCR mutation) era prior favorita — esta
auditoria a falsifica em §6.

---

## 2. conftest.py + pytest config — leitura completa

### 2.1 Conftest landscape

| Path | Tipo | Conteúdo |
|---|---|---|
| `tests/conftest.py` | root | Placeholder (1-line docstring) |
| `tests/unit/test_connectors/conftest.py` | shared | `tmp_cache_dir` (function-scoped) + `_disable_tenacity_wait` (autouse function-scoped via `monkeypatch`) + `fred_connector` (`pytest_asyncio.fixture` function-scoped, com `aclose()` em teardown) |
| `tests/unit/test_db/conftest.py` | shared | `db_session` (function-scoped, in-memory SQLite, `engine.dispose()` em teardown) + `us_fit_result` (function-scoped) |

Zero scope `module`/`session`/`class` em fixtures partilhadas — todas
function-scoped com teardown explícito.

### 2.2 pytest config (pyproject.toml `[tool.pytest.ini_options]`)

```toml
minversion = "8.0"
asyncio_mode = "auto"          # pytest-asyncio: per-test event loop
addopts = ["-ra", "--strict-markers", "--strict-config",
           "--cov=sonar", "--cov-report=term-missing", "--cov-report=html"]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
markers = ["slow", "integration", "property", "manual"]
filterwarnings = [
  "error",                                  # ⚠️ promove WARNING → ERROR
  "ignore::DeprecationWarning:pandas.*",
  "ignore::PendingDeprecationWarning",
]
```

**Critical interaction**: `filterwarnings = ["error"]` + `asyncio_mode = "auto"`
→ qualquer `ResourceWarning` (incluindo `unclosed event loop` /
`unclosed socket`) é convertido a `pytest.PytestUnraisableExceptionWarning`
e promovido a falha do teste em curso. **Esta interacção é o
mecanismo de surface das flakes Sprint A.**

Sem `pytest-randomly` / `pytest-ordering` / `--randomly-seed`. Ordem
determinística por collection (alfabética por path).

### 2.3 Versões relevantes

| Package | Versão |
|---|---|
| pytest | 9.0.3 |
| pytest-asyncio | 1.3.0 |
| pytest-httpx | 0.36.2 |
| httpx | 0.28.1 |

Default `asyncio_default_fixture_loop_scope` = `function` (pytest-asyncio
1.x). Cada teste `async` recebe um event loop fresh.

---

## 3. Empirical baseline — 5x full-suite

`uv run pytest -m "not slow" --no-cov -q --tb=line` 5x consecutivo,
mesmo working tree, sem alterações entre runs. Logs em
`/tmp/sprint8-baseline/run{1..5}.log`.

| Run | Tempo | Falhas | Teste sintoma |
|---|---|---|---|
| 1 | 71.17s | 1 | `test_te_indicator.py::test_wrapper_equity_index_from_cassette[FR-te_equity_france_2024_01_02.json-CAC]` |
| 2 | 63.50s | 1 | `test_economic_ecs.py::TestCanonicalFixtures::test_fixture_hysteresis_whipsaw_reject` |
| 3 | 62.98s | 1 | `test_te_indicator.py::test_wrapper_equity_index_from_cassette[FR-te_equity_france_2024_01_02.json-CAC]` |
| 4 | 49.98s | 1 | `test_te_indicator.py::test_wrapper_equity_index_from_cassette[FR-te_equity_france_2024_01_02.json-CAC]` |
| 5 | 50.73s | 1 | `test_te_indicator.py::test_wrapper_equity_index_from_cassette[FR-te_equity_france_2024_01_02.json-CAC]` |

**Aggregate**: 5/5 runs com 1 falha cada; 4/5 atribuídas a `test_te_indicator
equity[FR]`, 1/5 a `test_economic_ecs whipsaw`. Nunca duas falhas no mesmo
run. Nunca zero falhas.

### 3.1 Traceback canónico

Excerpt verbatim (`run1.log` linhas 1-23, padrão idêntico em runs 2-5):

```
ResourceWarning: unclosed <socket.socket fd=12, family=1, type=1, proto=0>
ResourceWarning: unclosed <socket.socket fd=13, family=1, type=1, proto=0>

Traceback (most recent call last):
  File "/usr/lib/python3.12/asyncio/base_events.py", line 726, in __del__
    _warn(f"unclosed event loop {self!r}", ResourceWarning, source=self)
ResourceWarning: unclosed event loop <_UnixSelectorEventLoop running=False closed=False debug=False>

The above exception was the direct cause of the following exception:
pytest.PytestUnraisableExceptionWarning: Exception ignored in: <function BaseEventLoop.__del__ ...>

ExceptionGroup: multiple unraisable exception warnings (3 sub-exceptions)
```

Padrão estável: `ExceptionGroup` com 2-3 sub-exceptions — 2 sockets + 1
event loop. Origem das ResourceWarnings é `BaseEventLoop.__del__` (ou
seja, GC finaliza um event loop que ainda tinha sockets abertos).

### 3.2 Mecanismo

1. Teste anterior cria event loop (e.g. via `asyncio.run()` mascarado em
   chamada sync) sem `loop.close()` explícito.
2. Loop fica órfão (sem referência forte) após retornar.
3. Algures depois, GC fire `BaseEventLoop.__del__` durante a execução de
   um teste subsequente.
4. `__del__` emite `ResourceWarning`.
5. pytest `unraisableexception.collect_unraisable` agarra a warning e
   converte em `PytestUnraisableExceptionWarning`.
6. `filterwarnings = ["error"]` promove a `ERROR` → falha do teste em
   curso.
7. Por o teste que GC fires é não-determinístico, o sintoma flutua.

---

## 4. Empirical baseline — 3x targeted subset

`uv run pytest tests/unit/test_cycles/ tests/unit/test_connectors/test_te_indicator.py -m "not slow" --no-cov -q --tb=line` 3x consecutivo.

| Run | Tempo | Resultado |
|---|---|---|
| 1 | 8.25s | 304 passed, 31 deselected, **0 failures** |
| 2 | 8.08s | 304 passed, 31 deselected, **0 failures** |
| 3 | 8.17s | 304 passed, 31 deselected, **0 failures** |

**Conclusão**: zero flakes no subset alvo isolado. Os testes
`test_te_indicator equity[FR]` + `test_economic_ecs::*` + `test_credit_cccs::*`
PASSAM consistentemente em isolamento.

---

## 5. Categorisação de flakes — diagnostic conclusion

| Eixo | Evidência | Conclusão |
|---|---|---|
| Shared DB session pollution | `db_session` fixture function-scoped, in-memory SQLite per test, `engine.dispose()` em teardown | ❌ Não é a causa |
| Cassette VCR state mutation | Não há `vcrpy`; tests usam `pytest-httpx` (`httpx_mock.add_response` per-test) | ❌ Hipótese A do brief §8 falsificada |
| Module-level mutable shared | `sonar.db.session` engine module-level, mas function-scoped fixtures não dependem dele para o subset alvo | ❌ Não é a causa |
| **Async cleanup pollution** | Traceback `BaseEventLoop.__del__` → `unclosed event loop` + sockets; targeted subset (sem pipelines/overlays) zero flakes | ✅ **Causa raiz** |

**Hipótese B do brief §8 confirmada**: async cleanup leak (event loop +
sockets pendentes) escoado por GC durante teste subsequente; sintoma
atribuído ao teste em curso pelo mecanismo
`filterwarnings=error` + `PytestUnraisableExceptionWarning`.

---

## 6. Falsifications — cassette / VCR hypothesis

Hipótese A do brief §8 ("cassette VCR state mutation entre tests") é
**falsificada**:

1. Repo usa `pytest-httpx` (`httpx_mock`), não `vcrpy`. Cada teste
   chama `httpx_mock.add_response(...)` per-test sem state global.
2. Subset incluindo `test_te_indicator.py` completo isoladamente: 3/3
   PASS. Se fosse cassette mutation, falharia em isolamento.
3. Falhas atribuídas a `test_te_indicator equity[FR]` ocorrem com o
   teste a passar funcionalmente (cassette parsed correctamente,
   asserts cumpridos) — a falha é exclusivamente `ExceptionGroup` de
   ResourceWarnings injectadas via unraisable hook.

---

## 7. Pollution origin — bisect priors

Targeted subset (cycles + te_indicator) = 0 flakes; full-suite = 5/5
flakes. A diferença é tudo o resto: connectors restantes, overlays, db,
pipelines, indices, cli, scripts, regimes, helpers.

Suspeitos prioritários para bisect (Commit 2):

1. **`tests/unit/test_pipelines/`** — pipelines `daily_*.main()` chamam
   `asyncio.run(...)` internamente. Sprint Q.0.5 retro §3.3 documenta
   esse pattern como causa conhecida de unraisable warnings; fix
   shipped foi `_stub_main` que monkeypatch ambos `_run_async_pipeline`
   E `asyncio.run`. Contagem actual: `_stub_main` aplicado em
   `test_daily_monetary_indices.py`. Outras suites de pipeline tests
   (test_daily_curves, test_daily_overlays, test_daily_economic_indices,
   test_daily_cycles, test_daily_bis_ingestion, test_daily_cost_of_capital,
   test_m3_builders) podem ter o mesmo pattern sem o stub.

2. **`tests/unit/test_overlays/`** + **`tests/unit/test_indices/`** —
   overlays / indices podem instanciar connectors directamente em
   tests sync sem aclose() proper.

3. **`tests/unit/test_connectors/`** (excepto `test_te_indicator.py`)
   — outros connector tests com fixtures async menos estritas.

Bisect order proposto Commit 2: directory-level. Run subset com cycles
+ te_indicator + pipelines, depois + overlays, etc., até reproduzir 5/5
falhas → narrow down ao directório suspeito.

---

## 8. HALT-status

| HALT | Trigger | Status |
|---|---|---|
| #0 | conftest fixture lifecycle unrecognisable | ✅ Cleared |
| #1 | DONE-NULL — zero flakes em 5x + 3x | ❌ Não cleared (5/5 flakes) → proceed Commit 2 |
| #2-#5 | Apply later commits | n/a |

---

## 9. Brief §6 acceptance gate (parcial Commit 1)

- [x] Sprint A retro §2.2 read end-to-end
- [x] Conftest.py inventory (3 files) + scope analysis
- [x] pytest config snapshot (filterwarnings=error key finding)
- [x] 5x full-suite empirical baseline executed + matrix recorded
- [x] 3x targeted subset baseline executed + matrix recorded
- [x] Falsified Hipótese A (cassette VCR mutation)
- [x] Confirmed Hipótese B (async cleanup pollution)
- [x] HALT #0 + HALT #1 evaluated; proceed Commit 2 hypothesis ranking

---

## 10. Output paths

| Artefacto | Path |
|---|---|
| Audit doc | `docs/planning/week11-sprint-8-pre-flight-audit.md` (este) |
| Run logs | `/tmp/sprint8-baseline/run{1..5}.log`, `targeted_run{1..3}.log` (efémero) |
| Brief | `docs/planning/week11-sprint-8-test-pollution-rootcause-brief.md` |
| Sprint A retro | `docs/planning/retrospectives/week11-sprint-a-test-hygiene-and-session-state-report.md` §2.2 |
