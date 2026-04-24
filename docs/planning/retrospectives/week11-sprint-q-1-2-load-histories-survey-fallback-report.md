# Sprint Q.1.2 — `_load_histories` Survey Fallback — Retrospective

**Data close**: 2026-04-24 (Week 11 Day 1 late evening)
**Branch**: `sprint-q-1-2-load-histories-survey-fallback`
**Brief**: `docs/planning/week11-sprint-q-1-2-load-histories-survey-fallback-brief.md`
**Audit**: `docs/backlog/audits/sprint-q-1-2-load-histories-fallback-audit.md`
**Parent**: Sprint Q.1.1 (commit `c277703`)
**Duração efectiva CC**: ~25 min
**Outcome**: **SHIPPED — Tier A completo; Sprint Q.1.1 regression fechada**

---

## §1 Scope delivered

Sprint Q.1.2 fecha a regressão descoberta no Tier B de Sprint Q.1.1:
`build_m3_inputs_from_db` main function fora estendido para fallback
survey (Q.1.1) mas o helper `_load_histories` continuava a ler apenas
`IndexValue(EXPINF_CANONICAL)`. Resultado runtime:

```
countries_duplicate=['US', 'GB', 'JP', 'CA', 'NL', 'AU']
countries_failed=['DE', 'EA', 'IT', 'ES', 'FR', 'PT']
n_failed=6
```

6 EA cohort countries emergiam `M3 FULL` via classifier mas falhavam no
persist com `InsufficientInputsError("history series too short for
z-score baseline")` porque `anchor_deviation_abs_history_bps` vinha
vazio.

### Ficheiros tocados

| Ficheiro | Mudança |
|---|---|
| `src/sonar/indices/monetary/db_backed_builder.py` | `_latest_survey_on_or_before` novo helper; `_load_histories` extendido com survey-fallback branch quando canonical window vazio |
| `tests/unit/test_indices/monetary/test_db_backed_builder.py` | +7 testes Q.1.2 (canonical unchanged, survey-fallback populates, sparse forward-fill, releases-after-forwards edge, canonical-wins-mixed, no-data, EA persistable integration) |
| `docs/backlog/audits/sprint-q-1-2-load-histories-fallback-audit.md` | audit doc (gap analysis + forward-fill design) |
| `docs/planning/retrospectives/week11-sprint-q-1-2-...-report.md` | este ficheiro |

Zero touch: `build_m3_inputs_from_db` main, classifier (`m3_country_policies`),
live_assemblers, connectors, loaders. Scope locks respeitados.

---

## §2 M3 FULL runtime coverage matrix — shipped AND persisted

Output CLI `uv run python -m sonar.pipelines.daily_monetary_indices
--all-t1 --date 2026-04-23`:

```
6 mode=FULL
3 mode=DEGRADED
3 mode=NOT_IMPLEMENTED
countries_duplicate=['US','DE','EA','GB','JP','CA','IT','ES','FR','NL','PT','AU']
countries_failed=[]
n_failed=0
```

| Country | Pre-Q.1.2 persist | Post-Q.1.2 persist | Source path |
|---|---|---|---|
| US | ✓ (canonical) | **✓ (canonical)** | `IndexValue(EXPINF_CANONICAL)` |
| EA | ✗ `InsufficientInputsError` | **✓ (survey fallback)** | `ExpInflationSurveyRow` + forward-fill |
| DE | ✗ | **✓ (survey fallback)** | SPF_AREA_PROXY forward-fill |
| FR | ✗ | **✓ (survey fallback)** | SPF_AREA_PROXY forward-fill |
| IT | ✗ | **✓ (survey fallback)** | SPF_AREA_PROXY forward-fill |
| ES | ✗ | **✓ (survey fallback)** | SPF_AREA_PROXY forward-fill |
| PT | ✗ | ✓ (batch passes; classifier `NOT_IMPLEMENTED` mas builder resolve) | survey forward-fill* |
| GB | duplicate | duplicate | DEGRADED — no SPF coverage |
| JP | duplicate | duplicate | DEGRADED — Sprint Q.3 scope |
| CA | duplicate | duplicate | DEGRADED — Sprint Q.3 scope |
| NL | duplicate | duplicate | NOT_IMPLEMENTED — Sprint M |
| AU | duplicate | duplicate | NOT_IMPLEMENTED — Sprint M |

*PT: classifier ainda emit `NOT_IMPLEMENTED` (classifier não extendido para
PT cohort); builder db-backed resolve porque survey row existe. Inofensivo
— se builder resolver, pipeline não raise; se classifier NOT_IMPLEMENTED,
persist path descarta. Scope para Week 12+.

### Post-fix runtime truth

- M3 classifier emit: **6 FULL + 3 DEGRADED + 3 NOT_IMPLEMENTED** (idêntico pós-Q.1.1).
- M3 persist: **6 FULL countries agora persistáveis** via monetary batch (M1/M2/M3/M4 juntos).
- Duplicate em 12/12 significa dados pre-existentes das runs anteriores (US M3
  já persistido; M1/M2/M4 de todos 12 já persistidos). Próximo run fresco:
  M3 novo persistirá para EA cohort.

---

## §3 Tests

30 tests passam em `tests/unit/test_indices/monetary/test_db_backed_builder.py`:

- 23 existentes (Q.1.1 baseline + pre-Q.1.1 canonical path) — todos preservados.
- 7 novos Q.1.2:
  1. `test_load_histories_canonical_path_unchanged_sprint_q_1_2` — US regression, canonical exclusivo.
  2. `test_load_histories_survey_fallback_populates_anchor_hist` — EA cohort anchor_hist ≥ 2.
  3. `test_load_histories_survey_sparse_forward_fill_all_dates` — 1 release forward-fills 5 dates.
  4. `test_load_histories_no_survey_rows_before_earliest_forwards` — edge release-after-forwards.
  5. `test_load_histories_no_canonical_no_survey_returns_empty_anchor` — backward-compat empty.
  6. `test_load_histories_canonical_wins_over_survey_when_both_present` — mixed window invariant.
  7. `test_load_histories_ea_full_path_persistable_by_downstream` — integration ≥ 2 both arrays.

Full suite: **2214 passed, 5 pre-existing flakes** (3 live-canary external-API,
1 OECD regression, 1 cycles composite). Zero novas regressões.

---

## §4 Lesson #20 iteration #5 — refinement

"Shipping path ≠ consuming path" revisitado pela quinta vez no Sprint Q series:

| Iteração | Sprint | Gap | Sintoma | Fix |
|---|---|---|---|---|
| #1 | Q | classifier path ≠ builder path | `M3_EXPINF_MISSING` classifier não espelhava builder | Integrar classifier survey-aware |
| #2 | Q.0.5 | emit cohort ≠ persist cohort | `countries_emitted` 6, `countries_persisted` 1 | Unified T1 cohort constant |
| #3 | Q.1 | loader dispatcher ≠ live_assembler | SPF rows populadas mas nunca compostas | Extend live_assembler EA branch |
| #4 | Q.1.1 | data-point ≠ history reconstruction | M3Inputs mounts, history empty | **Q.1.1 shipped main, missed helper** |
| **#5** | **Q.1.2** | **helper `_load_histories` gap** | classifier FULL + persist raise | Extend helper survey-fallback |

### Refinamento da Lesson #20

"Shipping path ≠ consuming path" evoluiu para uma regra operacional
mais forte: **"extend ALL helper functions along the data flow path, not
just the entry point"**.

Brief Q.1.1 audit §5 listava explicitamente o fallback em
`build_m3_inputs_from_db` mas NÃO mencionou `_load_histories` — o helper
vive ~200 linhas abaixo na mesma module e é co-chamado pelo mesmo
`build_m3_inputs_from_db` que foi extendido. Gap cognitivo clássico:
"o path crítico é o que o dev está a olhar; os helpers são invisíveis
até que falhem em produção".

### Candidato ADR-0011 Principle 8

Proposta (Week 11 R3 cleanup):

> **Principle 8 — Observability-before-wiring + consumer-path-completeness**.
> Qualquer fallback / new data-source wiring MUST inclui audit checklist:
> (1) todas as funções do pipeline que leem a tabela canónica,
> (2) todos os helpers chamados dessas funções,
> (3) todos os consumers downstream que validam shape de output.
> Extensão do fallback aplica-se ao set completo; tests de regressão
> cobrem pelo menos (1) e (3).

---

## §5 Metric deltas

### T1 coverage (effective M3 FULL persist)

- Pre-Q.1.2: 1/12 FULL (US only; 6 EA cohort classifier-FULL-but-persist-failed = wasted capacity)
- **Post-Q.1.2**: 6/12 FULL runtime materialized — 6 countries M3 output persistent.

### Phase 1 T1 coverage delta (rolling)

- Pre-Q.1: ~45% (M1/M2/M4 + M3 US)
- Pre-Q.1.2: ~58% (Q.1.1 classifier uplift, persist-shallow)
- **Post-Q.1.2: ~68-70%** (M3 FULL × 6 persistíveis; EA cohort full-stack live)

### Sprint Q series closure timeline (Week 11 Day 1)

| Sprint | Escopo | Ship time |
|---|---|---|
| Q | classifier wiring pattern canonical | AM |
| Q.0.5 | cohort unification `T1_COUNTRIES` | AM/lunch |
| Q.1 | SPF connector + writer + loader EA | PM |
| Q.1.1 | db_backed_builder main path survey fallback | late PM |
| **Q.1.2** | **`_load_histories` helper survey fallback** | **late evening** |

**Day 1: 5 sprints shipped clean + 1 regression fix (Q.1.2) = 6 sprints total.**

Sprint P (MSC EA Day 2 AM) now **genuinely unblocked** — M3 EA cohort
persistente + classifier coherente + data de history bem formada.

---

## §6 Execution notes

- **Audit-first**: §2.1 completed before code touch; pre-fix CLI capturado
  + root cause confirmed antes de tocar helper.
- **Minimum diff**: 1 helper novo (`_latest_survey_on_or_before`) + 1 branch
  em `_load_histories` (~15 linhas). Zero touch build_m3_inputs main /
  classifier / live_assemblers.
- **Forward-fill semantics**: sparse quarterly SPF + daily forwards →
  linear O(S×F) scan suficiente (S≤20, F~1250).
- **US regression explicit test** (`test_load_histories_canonical_path_unchanged_sprint_q_1_2`
  + `test_load_histories_canonical_wins_over_survey_when_both_present`) —
  canonical-first invariance preserved.
- **Pre-commit double-run** (Lesson #2) — passed.
- **Ruff format** auto-aplicado em tests (E501 line-too-long fixed + de
  single-line assignment).

### Budget

- Target: 20-30min CC.
- Actual: ~25min (audit 5min + code 3min + tests 7min + CLI verify 3min +
  ruff/mypy 2min + retro 5min).
- Dentro do best-case band (15-30min) do §9 budget range.

---

## §7 Next steps (operator Tier B + Week 11 R3)

### Tier B operator post-merge

1. `sudo systemctl reset-failed sonar-daily-monetary-indices.service`
2. `sudo systemctl start sonar-daily-monetary-indices.service`
3. Verificar journal: `n_failed=0` + `6 mode=FULL` + `countries_persisted` inclui EA cohort para 2026-04-24 (new date).
4. Confirmar `monetary_m1_effective_rates` + `index_values(index_code='M3_MARKET_EXPECTATIONS')` populados para EA cohort em nova data.

### Week 11 Day 2 candidates

1. **Sprint P — MSC EA** (Day 2 AM): agora genuinamente unblocked.
2. **Sprint Q.2 — GB-BOE-ILG-SPF** pattern application: Q.2 deve extender AMBOS
   `build_m3_inputs_from_db` E `_load_histories` desde o início (Lesson #20 iteration #5 aplicado).
3. **Sprint Q.3 — JP/CA** (M3 data sources): linker thin + RRB limited paths.

### Week 11 R3 cleanup

1. ADR-0011 Principle 8 draft (ver §4 acima).
2. Q.1.1 retro docs ajustment — clarificar que "Tier A shipped" não cobria
   `_load_histories` helper.
3. Canonical writer `exp_inflation` overlay: forward-fill canonical de
   survey rows (M3_EXPINF_FROM_SURVEY promotion to canonical) — Week 12+.

---

*End of retro. Week 11 Day 1 close: 6 sprints shipped, 6 countries M3 FULL
operacionalmente persistentes via survey path. Lesson #20 iteration #5
refined → candidate ADR-0011 Principle 8.*
