# Sprint A — Pre-flight audit (Commit 1)

**Brief**: [`week11-sprint-a-test-hygiene-and-session-state-brief.md`](week11-sprint-a-test-hygiene-and-session-state-brief.md).
**Status**: HALT #0 cleared — proceed.
**Date**: 2026-04-26.

---

## 1. Schema names — canonical alignment confirmed

Verificação directa via `sqlite3 data/sonar-dev.db ".tables"`:

| Camada | Tabela canónica | Presente |
|---|---|---|
| L3 monetary | `monetary_m1_effective_rates` | ✅ |
| L3 monetary | `monetary_m2_taylor_gaps` | ✅ |
| L3 monetary | `monetary_m4_fci` | ✅ |
| L4 monetary | `monetary_cycle_scores` | ✅ |
| L4 economic | `economic_cycle_scores` | ✅ |
| L4 credit | `credit_cycle_scores` | ✅ |
| L4 financial | `financial_cycle_scores` | ✅ |
| L3 financial | `f1_valuations` | ✅ |
| L3 financial | `f2_momentum` | ✅ |
| L3 financial | `f3_risk_appetite` | ✅ |
| L3 financial | `f4_positioning` | ✅ |
| L3 economic | `idx_economic_e1_activity` | ✅ |
| L3 economic | `idx_economic_e3_labor` | ✅ |
| L3 economic | `idx_economic_e4_sentiment` | ✅ |
| Polymorphic | `index_values` (M3_MARKET_EXPECTATIONS, E2_LEADING) | ✅ |

ORM tablename declarations em `src/sonar/db/models.py` confirmam mapping
1:1 com schema canónico. Zero divergência.

---

## 2. Composite readers vs canonical — alignment confirmed

### `compute_msc` (`src/sonar/cycles/monetary_msc.py`)

| Sub-índice | Reader | ORM | Tabela | Match |
|---|---|---|---|---|
| M1 | `_latest_m1` | `M1EffectiveRatesResult` | `monetary_m1_effective_rates` | ✅ |
| M2 | `_latest_m2` | `M2TaylorGapsResult` | `monetary_m2_taylor_gaps` | ✅ |
| M3 | `_latest_m3` | `IndexValue` (`index_code="M3_MARKET_EXPECTATIONS"`) | `index_values` | ✅ |
| M4 | `_latest_m4` | `M4FciResult` | `monetary_m4_fci` | ✅ |
| CS | n/a (Phase 0-1) | — | — | n/a (sempre `None`) |

`MIN_INPUTS = 3` of 5 → MSC requer no mínimo 3 sub-índices presentes.

### `compute_ecs` (`src/sonar/cycles/economic_ecs.py`)

| Sub-índice | Reader | ORM | Tabela | Match |
|---|---|---|---|---|
| E1 | session.query(`E1Activity`) | `E1Activity` | `idx_economic_e1_activity` | ✅ |
| E2 | session.query(`IndexValue`) `index_code="E2_LEADING"` | `IndexValue` | `index_values` | ✅ |
| E3 | session.query(`E3Labor`) | `E3Labor` | `idx_economic_e3_labor` | ✅ |
| E4 | session.query(`E4Sentiment`) | `E4Sentiment` | `idx_economic_e4_sentiment` | ✅ |

`MIN_REQUIRED = 3` of 4 → ECS requer no mínimo 3 sub-índices presentes.

### `compute_cccs` + `compute_fcs`

CCCS lê CS/LC/MS/QS via tabelas dedicadas (`credit_to_gdp_stock`, `credit_to_gdp_gap`, `credit_impulse`, `dsr`) + F3 (`f3_risk_appetite`) + F4 (`f4_positioning`). FCS lê F1/F2/F3/F4 (`f1_valuations`, `f2_momentum`, `f3_risk_appetite`, `f4_positioning`). Sem divergência vs schema canónico.

### `compute_all_cycles` (orchestrator)

Despacha 4 cycles sequencialmente: CCCS → FCS → MSC → ECS. Cada
`InsufficientCycleInputsError` é capturado e registado em `skips`.
`outcome.skips == {}` exige que **todos os 4** cycles computem com
sucesso.

---

## 3. `_seed_all` audit (Issue 1 root cause)

**Fonte**: `tests/integration/test_cycles_composites.py:54-74`.

**Comportamento actual**:
1. Chama `_seed_cccs_inputs` → seeds L1/L2/L3/L4 credit + F3 + F4
   (com history 20 obs) — bem.
2. Chama `_seed_fcs_inputs` → seeds F1 + F2 (F3/F4 reusados do seed
   CCCS quando `include_f4=True`) — bem.

**Falta**:
- M1/M2/M4 rows (`monetary_m1_effective_rates`, `monetary_m2_taylor_gaps`, `monetary_m4_fci`) — MSC requer >= 3 destes 5 (incluindo M3 + CS); CS é sempre `None` em Phase 0-1, logo precisamos de **M1 + M2 + M4 + M3** garantidos para que MSC não dispare `InsufficientCycleInputsError`.
- E1/E3/E4 rows + E2 `IndexValue` row — ECS requer >= 3 dos 4; precisamos seed de E1 + E2 + E3 + E4 (todos 4) por consistência.
- M3 `IndexValue` row (`index_code="M3_MARKET_EXPECTATIONS"`).

**Resultado observado** (run 2026-04-26):

```
FAILED tests/integration/test_cycles_composites.py::TestOrchestratorSmoke::test_us_smoke_end_to_end
  assert outcome.skips == {}
  Left contains 2 more items:
  {'ECS': "Composite requires >= 3 sub-indices; got 0 (missing: ['E1', 'E2', 'E3', 'E4'])",
   'MSC': "Composite requires >= 3 sub-indices; got 0 (missing: ['CS', 'M1', 'M2', 'M3', 'M4'])"}
```

**Diagnóstico**: o orchestrator foi extendido para incluir MSC+ECS
(Week 6+), mas o helper `_seed_all` não foi actualizado. Issue 1 é
`docstring of orchestrator says "persists both rows"` ⟶ fixture
desactualizada vs escopo extendido do orchestrator (4 cycles).

**Plano de fix (Commit 2)**: extender `_seed_all` para popular M1
+ M2 + M4 + M3 (`IndexValue`) + E1 + E2 (`IndexValue`) + E3 + E4 com
score_normalized intermédio (~50.0) + confidence ~0.85 + `r_star_pct`/
`taylor_*`/`fci_*`/`sahm_triggered`/etc fields obrigatórios per
schema constraints. Manter scope cirúrgico (sem refactor de seed
helpers vizinhos).

---

## 4. `_seed_f_rows` audit (Issue 2 — flake hypothesis)

**Fonte**: `tests/unit/test_cycles/test_financial_fcs.py:103-168`.

**Comportamento**:
- Insere F1/F2/F3/F4 rows para um país × data via `session.add` +
  `session.commit()`.
- Aceita `country` e `observation_date` keyword-arg + per-cycle scores
  (`f1`/`f2`/`f3`/`f4`).
- Sem teardown próprio — depende de `db_session` fixture
  function-scoped (em `tests/unit/test_cycles/test_financial_fcs.py:40-50`)
  que cria/destrói engine in-memory + `Base.metadata.create_all` +
  `session.close()` + `engine.dispose()`.

**Reprodução tentada** (run 2026-04-26): full suite 3x sequenciais
não reproduziu `test_us_full_stack` falhando. As falhas observadas:
- `test_us_smoke_end_to_end` — consistent (Issue 1).
- `test_te_indicator.py::test_wrapper_ca_bank_rate_from_cassette` —
  intermitente (Run 1+2 falha; Run 3 outra cassette falha).
- `test_us_full_stack` — **passou nos 3 runs**.

**Hipóteses para flake intermitente**:

1. **Ordem específica de teste** — pytest collects em ordem
   determinística por default (alphabetical by module path), mas
   xdist parallel ou pytest-randomly podem alterar. Sem
   pytest-randomly instalado neste repo (`uv pip list | grep
   randomly` vazio).
2. **Side effect de socket/event loop** — runs full-suite emitem
   "ResourceWarning: unclosed event loop" no final. Possível
   contaminação de ordem-dependente via state global.
3. **fixture `db_session` redefinido** — duas definições idênticas
   (function-scoped) em `test_cycles_composites.py` e
   `test_financial_fcs.py`. Cada teste recebe instância fresh; sem
   shared state esperado.
4. **`expire_on_commit=False` divergência** — confirmado em ambos
   os fixtures, sem divergência.

**Plano de fix (Commit 3)**:

Estratégia conservadora — confirmar reprodução antes de patch:

1. Run full suite mais 5x (em condições idênticas) → caso `test_us_full_stack` falhe, capturar full traceback; caso não falhe em ≥5 runs, declarar Issue 2 não-reproduzível e fechar com observação evidence-based.
2. Se reproduzido: aplicar isolation defensiva (`session.expunge_all()` antes do teardown, `engine.dispose()` antes de fixture re-yield, ou wrap em `try/finally`).
3. Se não reproduzido: documentar status no CAL closure (Issue 2 marked NOT-REPRODUCIBLE post-`_seed_all` Issue 1 fix; pre-push gate desbloqueia).

Anti-flake validation requerida pelo brief §5 HALT #2:
`test_us_full_stack` PASS em **5x consecutive full-suite runs** antes do CAL closure.

---

## 5. WORKFLOW.md current state — insertion-point analysis

**Fonte**: `docs/governance/WORKFLOW.md` (239 linhas, dump 2026-04-26).

**Secções existentes** (top-level):
1. Branches
2. Commits
3. Git rules (não-negociáveis)
4. Pull Requests
5. Code quality stack
6. CI (GitHub Actions)
7. Breaking changes
8. Release tags (Phase 1+)
9. Paralelo CC orchestration (Week 9+ pattern)
10. Referências

**Conflito potencial** (HALT #6): "Paralelo CC orchestration"
documenta `sprint_setup.sh` + `sprint_merge.sh` + worktrees + rebase
protocol + recovery patterns. **Sem secção "Session state"**.
SESSION_STATE.md mandate é addition pura (não substitui paralelo
orchestration).

**Insertion point recomendado**: nova secção `## SESSION_STATE update mandate`
**após "Paralelo CC orchestration"** e **antes de "Referências"**.
Rationale: governance flow → branches → commits → git rules → PRs →
code quality → CI → breaking changes → release tags → paralelo →
**session state mandate** → references. Ordem narrativa: do quotidiano
para o estratégico/governance-cross-conversation.

**Field schema**: incluir tabela canónica dos campos esperados em
SESSION_STATE.md (Phase / last-sprint / coverage / Path 2 cohort /
active CALs / test infrastructure / TE quota / pipelines / worktrees
/ next sprint candidates).

---

## 6. Plan — commits sequence

| # | Track | Commit | Acceptance gate |
|---|---|---|---|
| 1 | — | Pre-flight audit (este doc) | Doc shipped |
| 2 | T1 | Fix `_seed_all` Issue 1 | `test_us_smoke_end_to_end` PASS isolated + full-suite |
| 3 | T1 | Fix Issue 2 (`test_us_full_stack` flake) — patch OR document NOT-REPRODUCIBLE | 5x consecutive PASS |
| 4 | T1 | CAL closure | `CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL` marked DONE |
| 5 | T2 | Ship `docs/SESSION_STATE.md` | Doc shipped per brief §8 schema |
| 6 | T2 | Amend `WORKFLOW.md` mandate | Section + field schema documented |
| 7 | — | Sprint A retrospective | Per brief §7 structure |

**Concurrency**: single CC sequential — sem worktree split (brief §3).

**Pre-existing failures inheritance**: `test_te_indicator.py` cassette
flakes (CA + SE) são fora-escopo desta sprint. Documentar sob §6 da
retrospective como observação (não-bloqueio) — separate CAL filing
candidate post-sprint se persistir.

---

## 7. HALT trigger status

| HALT | Status |
|---|---|
| #0 Pre-flight (este doc) | ✅ cleared |
| #1 Issue 1 fix doesn't make test pass | pending Commit 2 |
| #2 Issue 2 fix doesn't stabilise 5x | pending Commit 3 |
| #3 New tests regress | monitor every commit |
| #4 Coverage regression > 3pp | monitor every commit |
| #5 Pre-push gate fail | monitor every push |
| #6 WORKFLOW mandate conflicts | ✅ no conflict identified (insertion-point clear) |

**Begin Commit 2**: `_seed_all` fix.
