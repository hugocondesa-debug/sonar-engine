# Sprint P — MSC EA L4 First Cross-Country Composite — Retrospective

**Data close**: 2026-04-24 (Week 11 Day 1 early afternoon)
**Branch**: `sprint-p-msc-ea-l4-cross-country`
**Brief**: `docs/planning/week11-sprint-p-msc-ea-l4-cross-country-brief.md`
**Audit**: `docs/backlog/audits/sprint-p-msc-ea-audit.md`
**Parent**: Sprint Q.1.2 (M3 EA survey fallback) + Sprint J (M4 EA-custom) +
Sprint L (M2 EA Taylor gaps)
**Duração efectiva CC**: ~45 min
**Outcome**: **SHIPPED — Tier A + Tier B completos; L4 primeiro cross-country unlock**

---

## §1 Scope delivered

Sprint P ship MSC EA composite agregando M1 + M2 + M3 + M4 EA ⇒ row
`monetary_cycle_scores` @ 2026-04-23 com score 44.17, regime 6-band
`NEUTRAL_ACCOMMODATIVE`, regime 3-band `NEUTRAL`, confidence 0.48, 4/5 inputs
(CS Phase 0-1 sempre ausente). Backfill adicional para 2026-04-21 e 2026-04-22
(3/4 inputs nos dates pré-M3-persist, Policy 1 re-weight graceful).

**L4 coverage**: 1/16 (US only) → 2/16 (US + EA) = **+6pp L4 layer**.

### Commits shipped

| # | Scope | Descrição |
|---|---|---|
| C1 | `docs(backlog)` | Sprint P audit — MSC US pattern + EA inputs + Path A decision |
| C2 | `refactor(pipelines)` | daily_cycles docstring + `MSC_CROSS_COUNTRY_COHORT` constant |
| C3 | `test` | MSC EA composite + country isolation + US regression |
| C4 | `docs(planning)` | Este retrospective |

Commit plan original do brief previa C2 `feat(indices)` builder refactor. Path A
(pure function) confirmado no audit → C2 substituído por thin dispatcher note
em `daily_cycles.py` (zero refactor MSC builder). Redução efectiva de scope.

### Files touched

| Ficheiro                                                           | Natureza        |
|--------------------------------------------------------------------|-----------------|
| `docs/backlog/audits/sprint-p-msc-ea-audit.md`                     | NEW             |
| `src/sonar/pipelines/daily_cycles.py`                              | docstring + new constant |
| `tests/unit/test_cycles/test_monetary_msc.py`                      | +5 EA/isolation/regression test cases |
| `tests/unit/test_pipelines/test_daily_cycles.py`                   | +1 constant assertion test, +1 import |
| `docs/planning/retrospectives/week11-sprint-p-msc-ea-l4-cross-country-report.md` | NEW |

---

## §2 Path A vs Path B decision rationale

Audit §1.2 demonstrou que `compute_msc(session, country_code, observation_date)`
já é função pura cross-country:

- Aceita `country_code` como parâmetro explícito.
- Leituras sub-index (M1/M2/M4) filtradas por `country_code` via
  `M{1,2,4}...Result` tables (Sprint K/L/J respectivos).
- M3 via `IndexValue(index_code='M3_MARKET_EXPECTATIONS', country_code=...)`.
- Regime labels 6-band / 3-band universais, não US-specific.
- Dilemma overlay universal (trigger A genérico, não US-hardcoded).

**Path A** confirmado. Zero refactor do builder. Dispatcher extension limitou-se
a expor `MSC_CROSS_COUNTRY_COHORT: tuple[str, ...] = ("US", "EA")` em
`daily_cycles.py` (separado do legacy `T1_7_COUNTRIES` 7-sovereign tuple para
respeitar 5 test suites existentes que fixam exactly `len == 7`).

Path B teria sido scope 2x brief budget → HALT-0 avoided.

---

## §3 M3 EA persistence — gap bridged

Brief §2.1.2 M3 note reivindicou "M3 is builder-only (no persistence table —
verified Day 1 Tier B)". Audit §2.2 refutou: o DB `index_values` **tem** suporte
para M3 via `persist_many_monetary_results` (persistence.py L1205-1207), e a
persistência é exercida pelo `daily_monetary_indices` pipeline quando M3
DB-backed builder retorna FULL.

Baseline worktree não tinha EA M3 persistido para 2026-04-23 → MSC composed
com 3/4 inputs (score 41.93, M3_MISSING flag). Single-shot remediation via
`daily_monetary_indices --country EA --date 2026-04-23 --backend default`
persistiu M3 EA `M3_EXPINF_FROM_SURVEY` + `SPF_LT_AS_ANCHOR` flags. Re-run MSC
subiu composite para 44.17 com 4/5 inputs.

**Nenhum in-flight M3 build introduzido** — teria sido refactor cross-country
com risk US regression. Documentação do contract `M3 is a DB-persisted sub-
index` via audit + tests que validam flags propagation (Tier B #4).

### Backfill mais antigo — 2026-04-21/22

M3 builder falhou para 2026-04-22 (`history series too short for z-score
baseline — InsufficientInputsError`) e 2026-04-21 (`no inputs provided`). Não
bloqueante Sprint P — MSC compose graceful via 3/4 inputs; score 41.93
consistente nos dois dates. Investigação de histórico M3 EA pré-2026-04-22 fica
fora de scope (Sprint Q.1.3 ou backfill task futura).

---

## §4 Acceptance evidence

### Tier A — todos ✅

1. **Audit doc shipped** — `docs/backlog/audits/sprint-p-msc-ea-audit.md` (cobre MSC US pattern, EA input availability, Path A decision, HALT review).
2. **MSC EA builder logic implemented** — Path A confirmed; `compute_msc` unchanged. Dispatcher extension via new `MSC_CROSS_COUNTRY_COHORT` constant.
3. **Dispatcher extended EA cohort** — constant + docstring update em `daily_cycles.py` (zero novo flag CLI; callers usam `--country EA`).
4. **CLI exit 0, EA row persisted** — `python -m sonar.cycles.orchestrator --country EA --date 2026-04-23` exit 0, row em `monetary_cycle_scores` (score 44.17, NEUTRAL_ACCOMMODATIVE).
5. **US regression unchanged** — pre-existing `(US, 2026-04-23)` row preservada via unique constraint; builder tests US passam inalterados.
6. **Regression tests pass** — 55 tests passed (MSC + daily_cycles suites).
7. **Pre-commit clean double-run** — trim whitespace, ruff, ruff-format, mypy, secrets all Passed em 2 runs consecutivos.

### Tier B — evidence

1. **Systemd `sonar-daily-cycle-scores` verify** — não aplicável (sprint P não altera systemd; dispatcher permanece schedulable via `--country EA` single-shot invocations).
2. **DB verify 2 rows @ 2026-04-23** — ✅ (US + EA confirmados via SQL query).
3. **EA regime sanity check** — ✅ `NEUTRAL_ACCOMMODATIVE` alinhado com ECB policy stance 2026-04 (DFR moderadamente acomodatícia; FCI EA-custom @ 0.0 muito acomodatício; anchoring neutro).
4. **Flags include M3 survey-fallback markers** — ✅ `M3_EXPINF_FROM_SURVEY`, `SPF_LT_AS_ANCHOR` presentes em `monetary_cycle_scores.flags`. (`SPF_AREA_PROXY` ausente é correcto — EA é target directo do ECB_SPF, não proxy.)

---

## §5 HALT review — post-hoc

| HALT trigger                                | Disparado? | Notas |
|---------------------------------------------|:----------:|-------|
| HALT-0: EA M2/M4 rows missing               | ✗          | Ambos presentes 2026-04-23 |
| HALT-0: MSC US-hardcoded (Path B 2x scope)  | ✗          | Path A confirmado no audit |
| HALT-material: US regression                | ✗          | Builder untouched; tests pass |
| HALT-material: M3 in-flight build fails EA  | ✗ (N/A)    | M3 via persisted row, não in-flight |
| HALT-material: M4 EA-custom scaffold partial| ✗          | FULL score 0.0 válido (condições acomodatícias) |
| HALT-scope: MSC DE/FR/IT/ES tentation       | ✗          | Mantido fora; Sprint P.1+ separate |
| HALT-scope: L5+ layer extension tentation   | ✗          | L5 graceful insufficient-data skip |
| HALT-scope: sub-index builder refactor      | ✗          | Zero toque M1/M2/M3/M4 builders |

Zero HALT activo. Green disciplined ship.

---

## §6 Surprises + learnings

### 6.1 Brief §2.1.2 M3 note contradiz-se

Brief afirma em §1 "M3 EA: Anchoring via SPF now FULL persisted (Q.1.2)" mas
§2.1.2 diz "M3 is builder-only (no persistence table)". A realidade é que M3
**tem** persistência via `index_values` (Sprint Q.1.x path). Audit §2.2 resolveu
reconciliando: M3 é DB-persisted; baseline worktree apenas precisava de
single-shot `daily_monetary_indices` run para popular 2026-04-23.

**Lição**: briefs com claims internamente inconsistentes merecem audit-first
verification. Esta foi a terceira vez (Sprint O, Sprint Q.1.1, agora Sprint P)
que audit-first evitou misdirected refactor.

### 6.2 T1_7_COUNTRIES tightly locked

6 test suites fixam exactly `T1_7_COUNTRIES == ("US", "DE", "PT", "IT", "ES",
"FR", "NL")` com `len == 7`. Extender esse tuple para incluir EA teria cascateado
breaks cross-pipeline. Solução: constant separada `MSC_CROSS_COUNTRY_COHORT`.
Alinha com Sprint Q.0.5 unification strategy (`T1_COUNTRIES` em
`daily_monetary_indices`) mas defer'd para `CAL-COHORT-CONSTANT-CLEANUP`
(Week 12+).

### 6.3 US MSC row stale pre-Sprint-P

Pre-existing `(US, 2026-04-23)` row tem `m3_score_0_100=NULL` + `M3_MISSING`
flag porque foi persistida antes de US M3 ser backfilled. **Não é regressão
Sprint P** — é estado histórico. Unique constraint bloqueia re-compute. Aceite
como baseline; builder logic unchanged é o acceptance real de "US regression
unchanged".

### 6.4 Path A foi a hipótese correcta — confirmada rápido

Brief estimava "best case 2h: Path A clean" e "worst 4h: Path B refactor".
Audit confirmou Path A em ~10 min de leitura de código. Tempo poupado aplicado
a teste adicional de country isolation (prevê contra hipotético regresso onde
filter por `country_code` seria accidentally dropped).

---

## §7 L4 coverage matrix — post-Sprint-P

| Country | M1 | M2 | M3 | M4 | MSC (L4) | Status |
|---------|:--:|:--:|:--:|:--:|:--------:|:------:|
| US      | ✅ | ✅ | ✅ | ✅ | ✅       | FULL   |
| EA      | ✅ | ✅ | ✅ | ✅ | ✅ **(NEW)** | FULL ← **Sprint P unlock** |
| DE      | —  | —  | ⚠  | ✅ | ✗        | M1 audit pending (CAL-M1-PER-EA-MEMBER) |
| IT/ES/FR| —  | —  | ⚠  | ✅ | ✗        | Same |
| PT      | —  | —  | ⚠  | ✅ | ✗        | Same (M3 degraded) |
| NL/AU   | —  | —  | —  | —  | ✗        | Curves absent |
| GB/JP/CA| —  | —  | ⚠  | ⚠  | ✗        | M4 scaffold |

L4 MSC: **2/16 countries** (+6pp vs 1/16 pre-Sprint-P).

---

## §8 Next steps unblocked

1. **Sprint P.1+** — MSC DE/FR/IT/ES/PT per-member (Week 11 Day 3+). Bloqueado
   em CAL-M1-PER-EA-MEMBER audit (M1 per-member vs EA aggregate semantics).
2. **CAL-COHORT-CONSTANT-CLEANUP** (Week 12+) — unificar `T1_7_COUNTRIES`
   legado com `T1_COUNTRIES` Sprint Q.0.5 tuple; remover
   `MSC_CROSS_COUNTRY_COHORT` se redundante.
3. **M3 EA backfill histórico** — 2026-04-21/22 tinham M3 ausente; investigate
   ECB_SPF history coverage (fora de scope Sprint P; possível Sprint Q.1.3).
4. **L5 EA** — actualmente graceful skip por `InsufficientL4DataError` (1/4
   cycles). Desbloqueado quando CCCS/FCS/ECS EA shipping (Phase 2+).
5. **M1 EA re-audit** — `EA_M1_POLICY_LENIENT` flag (N/A agora) + comparação
   com M1 per-member ECB NCBs para P.1+ refinement.

---

## §9 T1 scorecard delta

**Pre-Sprint-P** (Sprint Q.1.2 close):
- L4 coverage: 1/16 = 6.3%
- T1 overall: ~68-70%

**Post-Sprint-P**:
- L4 coverage: 2/16 = 12.5% (+6pp)
- T1 overall: ~70-72% (+1-2pp)
- **Strategic win**: primeiro cross-country L4 composite valida pattern
  replication pipeline para Sprint P.1+ per-member expansion.

---

## §10 Time budget

Brief budget: 4h. Actual: ~45 min.

| Fase                              | Tempo       |
|-----------------------------------|-------------|
| Pre-flight (pwd/branch/brief/DB)  | ~3 min      |
| Audit MSC US + decide Path A      | ~10 min     |
| Audit doc writing                 | ~8 min      |
| M3 EA repopulate + MSC re-run     | ~5 min      |
| Dispatcher extension + tests      | ~10 min     |
| CLI acceptance runs + DB verify   | ~3 min      |
| Pre-commit double-run             | ~2 min      |
| Retro doc                         | ~4 min      |

Scope tight + Path A confirmed fast = massive budget underrun. Best-case
scenario do brief executado.

---

*End Sprint P retrospective. L4 first cross-country composite shipped disciplined.
MSC EA NEUTRAL_ACCOMMODATIVE @ 2026-04-23.*
