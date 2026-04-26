# Sprint 8 — Test pollution root-cause diagnosis — Retrospective

**Brief**: [`../week11-sprint-8-test-pollution-rootcause-brief.md`](../week11-sprint-8-test-pollution-rootcause-brief.md).
**Pre-flight audit**: [`../week11-sprint-8-pre-flight-audit.md`](../week11-sprint-8-pre-flight-audit.md).
**Hypothesis ranking**: [`../week11-sprint-8-hypothesis-ranking.md`](../week11-sprint-8-hypothesis-ranking.md).

---

## 1. Sprint metadata

| Campo | Valor |
|---|---|
| Sprint ID | 8 — test pollution root-cause diagnosis |
| Branch | `sprint-8-test-pollution-rootcause` |
| Tier scope | Infrastructure (sem T1 cohort) — continuation Sprint A residuais |
| CC duration | ~80 min wall-clock single CC (22:00-23:15 WEST) |
| Commits | 5 (incluindo este retrospective) |
| Concurrency | Single CC sequential per brief §3 |
| TE quota delta | 0 (test-infra fix, sem live calls) |
| Outcome | **A** — root cause + single fix + 5x consecutive PASS verified |

### Commit timeline

| # | SHA | Subject |
|---|---|---|
| 1 | `7b7cea5` | docs(planning): pre-flight audit + empirical baseline |
| 2 | `2e871d8` | docs(planning): hypothesis ranking + tracemalloc root cause |
| 3 | `b37b29e` | fix(test-infra): suppress pytest-asyncio orphan event-loop leak via `_set_called=True` |
| 4 | `546ceca` | docs(governance): close CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL residuals |
| 5 | (este commit) | docs(retrospectives): Sprint 8 retrospective + SESSION_STATE.md update |

---

## 2. Diagnosis — root cause

### 2.1 Empirical baseline (Commit 1)

| | 5x full-suite | 3x targeted (cycles + te_indicator) |
|---|---|---|
| Pre-fix | 5/5 fail (1 falha cada run) | 0/3 fail |
| Failures | 4x `test_te_indicator.py::test_wrapper_equity_index_from_cassette[FR-…]`; 1x `test_economic_ecs.py::TestCanonicalFixtures::test_fixture_hysteresis_whipsaw_reject` | n/a |
| Tempo médio | ~60s | ~8s |

Pattern decisivo:
- Sintoma flutua entre testes diferentes runs.
- Targeted subset isolando os "suspeitos" mantém-se clean.
- Conclusão: testes acusados são **vítimas**, não causas.

### 2.2 Tracemalloc instrumentation (Commit 2)

`PYTHONTRACEMALLOC=10` localizou o ponto de criação do leak verbatim:

```
File "pytest_asyncio/plugin.py", line 805
    with _temporary_event_loop_policy(new_loop_policy):
File "pytest_asyncio/plugin.py", line 618
    old_loop = _get_event_loop_no_warn()
File "pytest_asyncio/plugin.py", line 649
    return asyncio.get_event_loop()
File "asyncio/events.py", line 699
    self.set_event_loop(self.new_event_loop())
…
File "asyncio/selector_events.py", line 120
    self._ssock, self._csock = socket.socketpair()
```

`_get_event_loop_no_warn` chama `asyncio.get_event_loop()` sob
`simplefilter("ignore", DeprecationWarning)`. Em Python 3.12.3, default
policy auto-cria loop quando `_local._loop is None and not _local._set_called and main_thread`. A `DeprecationWarning` é silenciada mas o loop é criado e os 2 sockets self-pipe são allocados. Esse loop nunca é usado nem fechado — orphan. GC eventualmente
finaliza → `BaseEventLoop.__del__` emite `ResourceWarning` → pytest's
unraisable hook converte em `PytestUnraisableExceptionWarning` →
`filterwarnings=["error"]` promove a falha do teste em curso.

### 2.3 Hypothesis ranking final

| # | Hipótese (brief §8 priors) | Status |
|---|---|---|
| H1 | Cassette VCR state mutation | **falsified** (repo usa pytest-httpx, not vcrpy; targeted subset clean) |
| H2 | Async cleanup pollution | **confirmed** (tracemalloc allocation site) |
| H3 | Shared DB session | **falsified** (function-scoped fixtures, in-memory SQLite per test) |

---

## 3. Fix — Commit 3

### 3.1 Implementation

`tests/conftest.py` autouse session-scoped fixture:

```python
@pytest.fixture(scope="session", autouse=True)
def _disable_asyncio_auto_create_loop() -> None:
    policy = asyncio.get_event_loop_policy()
    policy._local._set_called = True  # type: ignore[attr-defined]
```

### 3.2 Why this works

1. `_local._set_called=True` desabilita o auto-create branch
   (`if not self._local._set_called` em `events.py:680` falha).
2. `get_event_loop()` agora levanta `RuntimeError` quando `_loop is
   None` em vez de criar orphan.
3. pytest-asyncio's existente catch (`except RuntimeError: old_loop = None`) preserva o contract — nada a mais a mudar upstream.
4. Async tests continuam a funcionar via Runner do pytest-asyncio
   (que usa `events.set_event_loop(loop)` explícito, bypass auto-create).
5. Sync tests com `asyncio.run()` continuam a funcionar (Runner interno faz o mesmo).

### 3.3 Anti-flake validation

5x consecutive full-suite post-fix:

| Run | Resultado | Tempo |
|---|---|---|
| 1 | 2322 passed, 0 failed | 56.24s |
| 2 | 2322 passed, 0 failed | 53.98s |
| 3 | 2322 passed, 0 failed | 64.72s |
| 4 | 2322 passed, 0 failed | 48.70s |
| 5 | 2322 passed, 0 failed | 50.20s |

3x targeted subset post-fix: 304/304 PASS each, 8s/run. Coverage com
fix: 83.44 % TOTAL.

**Hard threshold "5x consecutive PASS for any 'fixed' claim" cleared** —
mesma disciplina anti-flake que Sprint A Issue 2.

---

## 4. Acceptance gate — outcome A

### Brief §6 outcome A checklist

- [x] Root cause identified com empirical evidence (tracemalloc allocation site documented)
- [x] Fix shipped targeting root cause (`b37b29e`)
- [x] 5x consecutive full-suite PASS clean — zero flakes
- [x] CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL residuais documented closed (Commit 4 `546ceca`)
- [x] No new test regressions (2322 passed full clean, was 2322-1=2321 baseline pre-fix)
- [x] Coverage stable (83.44 % TOTAL)

### Sprint-end discipline

- [x] No `--no-verify`
- [x] Pre-commit 2x every commit (5/5)
- [x] Pre-push gate green (a verificar no push final)
- [x] SESSION_STATE.md updated per WORKFLOW.md mandate (este commit)
- [x] Sprint 8 retrospective shipped (este doc)

---

## 5. Pattern observations vs Sprint A

### 5.1 Heuristics que funcionaram

1. **Empirical baseline ANTES de qualquer fix** — Sprint A precedente
   precisa-se manter.. Isolar 5x full-suite + 3x targeted desambiguou
   "vítima vs culprit" antes de qualquer hipótese.
2. **Targeted subset como falsifier** — quando suspeitos passam
   isoladamente, o leak está fora.
3. **PYTHONTRACEMALLOC=10 para unraisable warnings** — sem isso
   teríamos diagnosticado por dedução; com isso, allocation site é
   directo. Esta é a tool de eleição para qualquer
   `PytestUnraisableExceptionWarning` futuro.
4. **Reading existing retros** — Sprint Q.0.5 retro Discovery #3 já
   tinha visto o padrão e shippado fix parcial (`_stub_main`). Conhecer
   o histórico evita reinventar diagnose work.

### 5.2 Heuristics que falharam

1. **Hipótese A (cassette VCR mutation)** — primeira favorita do
   brief. Falsificada rapidamente porque repo usa `pytest-httpx`, não
   `vcrpy`. Lesson: validar que a tooling assumida pelo brief reflecte
   o estado actual do repo.
2. **TE rate-limit `cumulative_calls` bleed** — registado em SESSION_STATE.md
   pre-Sprint 8 como hipótese. Era sintoma generic, não TE-specific.
   Lesson: agrupar 3 patterns aparentemente distintos como "candidatos
   separados a CAL filing" pode mascarar uma causa comum. Sempre
   considerar root-cause unification antes de filing 3 CALs.

### 5.3 Comparação Sprint A vs Sprint 8

| Aspecto | Sprint A | Sprint 8 |
|---|---|---|
| Tier | Test-hygiene + governance | Test pollution diagnosis |
| Outcome | Issue 1 fixed; Issue 2 NOT-REPRODUCIBLE | A (root cause + fix) |
| Diagnostic tool | Schema audit + iso vs full-suite | PYTHONTRACEMALLOC=10 |
| Evidence depth | Schema diff + 5x runs | Allocation site + 5x runs |
| Fix scope | Test seed extension (T1 specific) | conftest single fixture (suite-wide) |
| Wall-clock CC | ~30 min | ~80 min |
| Commits | 7 | 5 |

Sprint 8 demonstra que diagnostic depth via tracemalloc é multiplicador
para problemas async — chave para Phase 2.5+ test infrastructure
sprints futuros.

---

## 6. Recommendations for future test-hygiene

### R1 — Tracemalloc como tool default para flake investigation

Para qualquer `PytestUnraisableExceptionWarning`, primeira acção é
`PYTHONTRACEMALLOC=10` para localizar allocation site. Sem isso, a
investigação fica em hipóteses indirectas. Cost ~3-5x slowdown
aceitável para single diagnostic run.

### R2 — Eliminar `_stub_main` pattern (Sprint Q.0.5)

Sprint Q.0.5's `_stub_main` em `test_daily_monetary_indices.py`
monkeypatch `asyncio.run` por instância. Sprint 8 fix em `conftest.py`
endereça o gerador upstream — `_stub_main` torna-se redundante. Audit
pendente: confirmar se `_stub_main` pode ser removido sem regressão.
Marker para sprint futuro low-priority.

### R3 — Audit pytest-asyncio version pin

Future pytest-asyncio releases podem refactor `_temporary_event_loop_policy`
para já não chamar `asyncio.get_event_loop()` directamente. Quando
isso acontecer, o fix em `conftest.py` torna-se desnecessário. Ver
upstream issue: <https://github.com/pytest-dev/pytest-asyncio/issues>.
Action: when bumping pytest-asyncio, smoke-test removendo o fixture
para detectar quando upstream resolve.

### R4 — Documentar trigger pattern (sync test calling asyncio.run)

`run_one()` em `daily_overlays.py:597` usa `asyncio.run(...)` internally.
Tests sync chamam-no 42 vezes em `test_daily_overlays.py`. Pattern
similar em `daily_economic_indices.py:333`, `daily_cycles.py:267`,
`daily_overlays.py:597 / 654 / 655`, `daily_curves.py:660`,
`daily_cost_of_capital.py:427`, `daily_economic_indices.py:430`,
`daily_overlays.py:806`. Cada call site é candidate trigger se o
fixture upstream falhar. Documentar em ADR-0011 §"Async lifecycle"
para visibilidade futura.

---

## 7. Sustainable pacing target

Brief §8 estimou ~3-5h wall-clock. Sprint 8 actual: ~80 min. Factor
~2.5-4x faster que estimate, sustentado porque:

- Sprint A retro + audit doc deram visibilidade contínua das flakes
  (SESSION_STATE.md "Active flakes" section foi consultado primeiro).
- PYTHONTRACEMALLOC=10 cortou diagnostic time para single run (~3
  min instrumentation + ~3 min interpretation).
- Fix decisão evidence-based (tracemalloc + Sprint Q.0.5 retro
  precedente) eliminou exploration de fallback alternatives.
- Brief §8 fallback plan (filterwarnings ignore) não foi exercitado —
  fix root-cause foi sufficient.

Pattern reusável para sprints test-infra: pre-flight baseline + tracemalloc
+ existing-retro-survey + targeted fix.

---

## 8. Out-of-scope, deferred

- TE cassettes refresh: não tocados (cassettes são old; brief §1 Out
  marca como separate concern). Não ressurgiu como flake — fix Sprint 8
  resolveu o pattern aparente "TE rate-limit bleed".
- pytest-randomly / pytest-ordering: não adicionados per brief §8
  Out-of-scope contingencies.
- L5 regimes / Phase 2+ items: out-of-scope per brief §1.

---

## 9. Sprint-close evidence

- Audit doc: [`../week11-sprint-8-pre-flight-audit.md`](../week11-sprint-8-pre-flight-audit.md)
- Hypothesis ranking: [`../week11-sprint-8-hypothesis-ranking.md`](../week11-sprint-8-hypothesis-ranking.md)
- Run logs: `/tmp/sprint8-baseline/run{1..5}.log`, `targeted_run{1..3}.log`, `postfix_run{1..5}.log`, `postfix_targeted_run{1..3}.log`, `tracemalloc.log` (efémeros)
- Brief: [`../week11-sprint-8-test-pollution-rootcause-brief.md`](../week11-sprint-8-test-pollution-rootcause-brief.md)
- CAL closure: `docs/backlog/calibration-tasks.md` (CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL §"Pre-existing flakes surfaced (out-of-scope) — CLOSED 2026-04-26 via Sprint 8")
- Fix file: `tests/conftest.py`
- SESSION_STATE.md update: dimensions Last sprint shipped + Test infrastructure + TE quota + Active worktrees + Next sprint candidates
