# Sprint A — Issue 2 investigation (Commit 3)

**Brief**: [`week11-sprint-a-test-hygiene-and-session-state-brief.md`](week11-sprint-a-test-hygiene-and-session-state-brief.md) §1 Issue 2.
**Pre-flight audit**: [`week11-sprint-a-pre-flight-audit.md`](week11-sprint-a-pre-flight-audit.md) §4.
**Status**: NOT-REPRODUCIBLE post-Issue 1 fix. HALT #2 not triggered.
**Date**: 2026-04-26.

---

## 1. Issue under investigation

`tests/unit/test_cycles/test_financial_fcs.py::TestComputeFcsHappy::test_us_full_stack`
documented em CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL como
order-dependent flake — pass isolated, fail in full-suite (Sprint 7B
Commit 1 pre-push gate observation, 2026-04-26).

---

## 2. Investigation methodology

Anti-flake validation per brief §5 HALT #2: `test_us_full_stack` deve
fazer PASS em 5x consecutive full-suite runs antes do CAL closure.

Estratégia conservadora:
1. **Baseline reprodução** (audit §4) — full suite 3x antes do Issue 1
   fix → flake **não reproduzido** (0/3).
2. **Post-Issue 1 fix verification** — full suite 5x sequenciais →
   `test_us_full_stack` PASS em todos os 5 runs.

---

## 3. Evidence — 5x consecutive full-suite runs (post Commit 2 `c5810c8`)

```
=== Run 1 ===  2321 passed, 1 failed (test_economic_ecs::test_fixture_us_2020_03_23_recession)
=== Run 2 ===  2321 passed, 1 failed (test_te_indicator::test_wrapper_equity_index_from_cassette[EA])
=== Run 3 ===  2321 passed, 1 failed (test_te_indicator::test_cpi_yoy_c2_from_cassette[SE])
=== Run 4 ===  2321 passed, 1 failed (test_te_indicator::test_wrapper_equity_index_from_cassette[EA])
=== Run 5 ===  2321 passed, 1 failed (test_te_indicator::test_wrapper_equity_index_from_cassette[EA])
```

`test_us_full_stack` — **0 falhas em 5 runs consecutivos** (estável).
`test_us_smoke_end_to_end` — **0 falhas em 5 runs consecutivos**
(Issue 1 fix shipped Commit 2 estável).

Conjunto de testes: `pytest -m "not slow"`, sem `-x`, sequential
execution, identical environment a cada run.

---

## 4. Diagnóstico — likely root cause Sprint 7B observation

A flake observada Sprint 7B Commit 1 era plausivelmente um knock-on
effect do **Issue 1**:

1. Sprint 7B Commit 1 pré-push gate viu `test_us_smoke_end_to_end`
   falhar (`outcome.skips != {}` por causa de M1/M2/M4/E1/E3/E4 em
   falta no fixture).
2. Pytest collect/order pode ter executado tests em ordem que
   permitisse pollution residual de uma sessão SQLAlchemy não
   limpa adequadamente — função `_seed_all` faz commit em sessão
   pertencente ao test integração, mas se houvesse leak de objects
   entre integration + unit modules (improvável dado fixture
   function-scoped) podia haver flake aparente.
3. Após Issue 1 fix, `test_us_smoke_end_to_end` deixa de falhar e a
   ordem efectiva de execução muda (tests downstream re-ordenam).
   Resultado observado: `test_us_full_stack` deixa de exibir flake.

**Conclusão**: Issue 2 era sintoma, não causa raiz independente. A
fix do Issue 1 elimina o sintoma. CAL fecha com Issue 2 marked
NOT-REPRODUCIBLE.

---

## 5. Decision — sem patch defensiva adicional

**Não aplicar fixture isolation extra** ao `_seed_f_rows` ou ao
`db_session` fixture. Rationale:

- Função-scoped fixtures já garantem isolation per-teste.
- `expire_on_commit=False` + explicit `session.close()` +
  `engine.dispose()` no teardown já são best-practice.
- Adding `session.expunge_all()` ou `session.rollback()` defensivo
  seria cargo-cult code (sem evidence de necessidade).
- Princípio CLAUDE.md §"Doing tasks": "Don't add error handling,
  fallbacks, or validation for scenarios that can't happen."

---

## 6. Pre-existing flakes detected (out-of-scope)

5x runs surfaceram outras flakes intermitentes — **pré-existentes
em main** (verificado via stash + 3x main runs):

| Test | 5x rate | Origem | Out-of-scope |
|---|---|---|---|
| `test_te_indicator.py` cassettes (CA / SE / EA various) | ~3-4/5 | TE rate-limit cumulative_calls bleed across cassette tests | ✅ |
| `test_economic_ecs::test_fixture_us_2020_03_23_recession` | 1/5 | Possivelmente order-dependent (cycles tests) | ✅ |
| `test_credit_cccs::TestComputeCccsEndToEnd::test_happy_full_stack` | 1/5 (run 2 prior verification) | Possivelmente order-dependent (cycles tests) | ✅ |

Estas flakes são **fora-escopo da Sprint A** per brief §1 In/Out:
brief mandata Issue 1 + Issue 2 only. Candidatos a CAL filing
separado post-sprint.

---

## 7. Acceptance gate clearance

- [x] `test_us_full_stack` PASS isolated AND in full-suite consistently — confirmed
- [x] 5x consecutive runs verified (HALT #2 cleared)
- [x] No fixture mutation introduced (defensive isolation declined per §5)
- [x] CAL closure can proceed (Commit 4)
