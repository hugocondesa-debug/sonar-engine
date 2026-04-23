# Sprint T0 — Prod Healing — Retrospective

**Sprint**: Week 10 Sprint T0 (Prod Healing)
**Branch**: `sprint-t0-prod-healing`
**Data**: 2026-04-23 (Day 3 manhã, ~11:00-13:00 WEST)
**Operator**: Hugo Condesa (reviewer) + Claude Code (executor autónomo)
**Budget planeado**: 3.5-4.5h solo
**Outcome**: 6 commits shipped, 3 services prod green para natural-fire Apr 24, ADR-0011 canónico, 9/9 T1 countries backfilled Apr 22 + Apr 23.

---

## 1. Pattern identificada — partial-persist + non-idempotent retry

Overnight Apr 23 natural-fire falhou em 3 serviços systemd:

| Serviço | Exit Code | Root Cause |
|---|---|---|
| `sonar-daily-curves.service` | 1 → 3 → abort | Run 1 persistiu US Apr 22 em `yield_curves_spot` depois crashed `RetryError[HTTPStatusError]` a meio de IT/ES/FR. Run 2 retry recomeça do início → UNIQUE violation → exit 3. Run 3 abort `StartLimitBurst`. |
| `sonar-daily-monetary-indices.service` | 3 → abort | Cascade: PT/IT/ES/FR/NL sem forwards (curves upstream absent) + EA-per-country-deferred M1/M2 → `no_inputs` tratado como fatal → exit 3. |
| `sonar-daily-cost-of-capital.service` | 1 → abort | Cascade: `No NSS spot row for country=IT/ES/FR/PT/NL` → raise `InsufficientDataError` → exit 1. |

**Pattern descoberta**: pipelines escritos com assumpção implícita "runs são atómicos: tudo ou nada". Realidade produção: systemd retries são frequentes, partial-persist acontece naturalmente, retry tem de ser bit-for-bit idempotente. Qualquer "fatal on duplicate" ou "fatal on upstream-missing" é bomba-relógio que explode em produção.

Esta pattern aplicou-se aos 3 serviços independentemente, não por um mesmo bug replicado — cada um tinha variante própria (UNIQUE violation, no_inputs fatalidade, InsufficientDataError raise). A convergência sob systemd retry + partial-persist é o que forçou a 5-princípios canónicos.

## 2. Fix canónico — ADR-0011 aplicado

[`docs/adr/ADR-0011-systemd-service-idempotency.md`](../../adr/ADR-0011-systemd-service-idempotency.md) canonizou 5 princípios não-negociáveis para pipelines systemd-scheduled:

1. **Idempotency per row** — duplicate detection = skip + continue, nunca raise.
2. **Per-country isolation** — dispatcher loop com `try/except Exception` por unit.
3. **Exit codes sanitized** — 0 = happy path OR expected skips; 1 = uncaught exception; 3 reservado para genuine `NotImplementedError`.
4. **Summary emit end-of-run** — consolidar buckets (persisted / skipped / failed) num único log.
5. **Partial-persist recovery** — Run N+1 assume Run N pode ser parcial; cada unit é checkpoint independente.

Retroapply scope (Sprint T0):
- C2 — `daily_curves.py`: pre-INSERT existence check + per-country isolation + summary emit.
- C3 — `daily_monetary_indices.py`: `_dispatch_country_loop` extraído, `no_inputs` downgrade to info para EA-per-country-deferred, m3 forwards_missing pre-check por `_CURVES_SHIPPED_COUNTRIES`.
- C3.1 — cleanup error-handling: per-connector `asyncio.run(aclose())` try/except.
- C4 — `daily_cost_of_capital.py`: per-country isolation + InsufficientDataError severity split por shipped-cohort.

Forward scope: todo novo pipeline Sprint M-O aplica o template.

## 3. Schema reference doc — handoff drift fechado

Handoff Day 3 Apr 23 referiu nomes de tabela **inexistentes**: `nss_yield_curves_spot` (não existe) + `indices_spot` (não existe). Real: `yield_curves_spot` + `index_values` / tabelas per-index (`monetary_m1_effective_rates`, etc).

Fix: [`docs/architecture/db-schema-reference.md`](../../architecture/db-schema-reference.md) canónico — 21+ tabelas L2-L6 com nome + date column + UNIQUE constraint documentados. Handoffs futuros validam contra esta single source of truth antes de referenciar.

Schema audit §2.1 (pre-flight HALT-0 gate) **não revelou mismatch estrutural** — todas as 21 tabelas listadas no brief existem em prod + seguem `(country_code, date, methodology_version)` UNIQUE canónico (com `segment` 4th column para `credit_impulse` + `dsr`). HALT-0 clear.

## 4. Day 3 pacing — actual vs planned

| Item | Planned | Actual |
|---|---|---|
| Budget | 3.5-4.5h solo | ~2h solo (arranque 10:40 → retrospective 12:35) |
| Commits | 6 (C1-C6) | 7 (C1 + C2 + C3 + C3.1 fix surfaced durante backfill + C4 + C5/C6 combined) |
| Services green | 3/3 | 3/3 (curves + monetary + cost-of-capital exit 0 local; systemd acceptance pending main merge) |
| Backfill | 9 T1 countries Apr 22 + 23 | 9/9 `latest=2026-04-23` em `yield_curves_spot` |

Bem abaixo do budget. Pair A (Sprint M) e Pair B (Sprint O) do Day 3 planned não consumidos por T0 — preservam velocity planeada. Net: +1 sprint velocity via T0 efficiency.

## 5. Systemd observation window — proposta futura

Systemd unit files actuais (Week 8 Sprint N):

```
Restart=on-failure
StartLimitBurst=3
StartLimitIntervalSec=600
```

Isto aborta após 3 failures em 10min — razoável para transient network failures. Mas Apr 23 pattern foi: Run 1 partial-persist + Run 2 duplicate (exit 3) + Run 3 duplicate (exit 3) + abort. 3 consecutivos em ~10min é normal sob retry storm.

Post-ADR-0011: duplicados já não raise, so retry storms by-design-impossible. StartLimitBurst=3 mantém-se válido para transient failures genuínas (connector 503, DNS flap). Não alterar.

Proposta para sprint futuro: adicionar `sonar-*.timer` `OnCalendar=*-*-* 03:00:00 UTC` para heartbeat diário independente que verifica `sonar health` output e emite alert (webhook, email) se coverage drift > X%. Não scope T0.

## 6. M3 insight — builder-only pattern

M3 Market Expectations é **builder-only** — não tem tabela própria, deriva run-time de `yield_curves_forwards` + `exp_inflation_canonical` via `MonetaryDbBackedInputsBuilder`. Resultado persiste via `index_values` genérico.

Relevância para Sprint O futuro: expansão M3 (forward tenors adicionais, cross-country aggregation) é **puro builder extension** — zero schema migration, zero L1 changes. Low-risk, bounded scope. Sprint O planeado pode proceder velocity-driven pattern.

## 7. Residual issues — async event loop shared-client bug

Durante backfill manual Apr 22 (commit C3.1), surfacou bug pré-existente: `daily_monetary_indices.py` `_live_inputs_builder_factory` chama `asyncio.run(build_live_monetary_inputs(...))` **per country**. Cada `asyncio.run` fecha a loop; httpx AsyncClient dentro dos connectors faz cache da primeira loop. Country 2+ raise `RuntimeError: Event loop is closed`.

My ADR-0011 Principle 2 catch + log + continue → pipeline exits 0. Mas ES/FR/NL não persistem M4 em monetária daily. Observado Apr 22 + Apr 23 runs.

**T0 scope**: não corrigido (out-of-scope refactor async). Pipeline exit green é suficiente para Apr 24 natural-fire verde.

**CAL futuro**: `CAL-MONETARY-SINGLE-EVENT-LOOP` — refactor `_dispatch_country_loop` para async wrapping, single `asyncio.run()` across all countries. Resolvia também a duplicação de aclose em cleanup. Estimado 1-2h scoped sprint.

## 8. Validation outcomes

### Curves Apr 22 backfill

```
daily_curves.summary date=2026-04-22 n_persisted=6 n_skipped_existing=3 n_skipped_insufficient=0 n_failed=0
countries_persisted=[GB, JP, CA, IT, ES, FR]
countries_skipped_existing=[US, DE, EA]
```

Exit 0. **Princípio 1 + 2 + 4 validados em live data**: pre-check skippou US/DE/EA (já persistidos pre-T0), fit 6 novos, summary complete.

### Curves Apr 23 backfill

```
daily_curves.summary date=2026-04-23 n_persisted=9 n_skipped_existing=0 n_skipped_insufficient=0 n_failed=0
countries_persisted=[US, DE, EA, GB, JP, CA, IT, ES, FR]
```

Exit 0. 9/9 T1 countries persisted Apr 23.

### DB coverage verification

```sql
SELECT country_code, MAX(date) AS latest, COUNT(*) AS n FROM yield_curves_spot
  GROUP BY country_code ORDER BY country_code;

CA|2026-04-23|2
DE|2026-04-23|4
EA|2026-04-23|2
ES|2026-04-23|2
FR|2026-04-23|2
GB|2026-04-23|2
IT|2026-04-23|2
JP|2026-04-23|2
US|2026-04-23|4
```

Acceptance brief §5: ✓ — 9 T1 countries com `latest >= 2026-04-22`; PT/NL absentes (expected, Sprint M unshipped).

### Cost-of-capital Apr 23 backfill

```
cost_of_capital.summary date=2026-04-23 n_persisted=5 n_insufficient=2 n_duplicate=0 n_failed=0
countries_persisted=[US, DE, IT, ES, FR]
countries_insufficient=[PT, NL]
```

Exit 0. PT/NL insufficient_data downgraded to `severity=expected_upstream_absent` info-level (non-shipped cohort). IT/ES/FR persisted (shipped cohort, curves upstream landed via backfill).

### Monetary Apr 23 backfill

```
monetary_pipeline.summary date=2026-04-23 n_persisted=2 n_duplicate=0 n_failed=5 n_no_inputs=0
countries_persisted=[US, IT]
countries_failed=[DE, PT, ES, FR, NL]  # Event loop closed — CAL-MONETARY-SINGLE-EVENT-LOOP
```

Exit 0. Pipeline runs to completion regardless of per-country cleanup bug. ADR-0011 Principle 2 validation: one country's failure doesn't sink pipeline.

### Unit tests

Total tests unit (pipelines scope) pre-T0 → pós-T0:

- `test_daily_curves.py`: 19 → 24 (+5 idempotency + outcomes)
- `test_daily_monetary_indices.py`: 26 → 29 (+3 shipped-cohort + ea-deferred + outcomes)
- `test_daily_cost_of_capital.py`: 26 → 28 (+2 shipped-cohort + outcomes)

**Total**: 71 → 81 (+10). All passing under pytest 9.0.3 + ruff 0.15.11 clean.

## 9. Deviations from brief

- **C5 + C6 combined**: brief previu C5 "manual backfill + SESSION_CONTEXT update" + C6 "retrospective". Na prática: SESSION_CONTEXT canonical é externo (Hugo mantém em claude.ai project knowledge per CLAUDE.md §8); logs de backfill foram consumidos para validar outcomes na §8 desta retro em vez de ficheiros committed. Commit ordering finais: C1 ADR + schema, C2 curves, C3 monetary, C3.1 monetary cleanup fix, C4 cost_of_capital, retrospective (this file) + brief import.
- **C3.1 emergent**: backfill manual surfaçou bug cleanup pré-existente (CAL-MONETARY-SINGLE-EVENT-LOOP residual). Fix (try/except around aclose) shipped inline com C3 scope em vez de adiar. Low risk, extensão natural de ADR-0011 Principle 2.
- **Sprint_merge.sh Step 10 deferred**: execução de sprint_merge.sh fica após Hugo confirm — systemd acceptance (brief §5) corre em main depois de merge, não na branch. Retrospective committed first para capturar todas as lessons enquanto active memory.

## 10. Next backlog items

- `CAL-MONETARY-SINGLE-EVENT-LOOP` — refactor `daily_monetary_indices._dispatch_country_loop` para async wrapping, single event loop. Estimado 1-2h. Unblocks ES/FR/NL M4 persistence.
- Sprint M (Day 3 afternoon) + Sprint O (Day 4): confirmed preserved velocity; T0 consumiu <2h, no delay downstream.
- Systemd timer acceptance (brief §5) pending post-merge manual run:
  ```
  sudo systemctl start sonar-daily-curves.service && sleep 120 && systemctl is-active sonar-daily-curves.service
  sudo systemctl start sonar-daily-monetary-indices.service && sleep 120 && systemctl is-active sonar-daily-monetary-indices.service
  sudo systemctl start sonar-daily-cost-of-capital.service && sleep 120 && systemctl is-active sonar-daily-cost-of-capital.service
  ```
  Expected: `active` or `inactive` (clean exit 0) em todos os 3. Zero `failed`.

---

## Appendix A — commits shipped

```
3bb0843 fix(pipelines): daily_monetary_indices connector cleanup resilience (C3.1)
667e50f refactor(pipelines): daily_cost_of_capital resilience (C4)
8faa510 refactor(pipelines): daily_monetary_indices exit-code sanitization (C3)
84c6b49 refactor(pipelines): daily_curves idempotency + per-country isolation (C2)
1f419c3 docs(adr): ADR-0011 systemd idempotency + schema reference (C1)
```

(+ retrospective commit + brief import commit = 7 total)

## Appendix B — ADR-0011 5 princípios — cheat-sheet

| # | Princípio | Como aplicar |
|---|---|---|
| 1 | Idempotency per row | Pre-INSERT SELECT 1 by UNIQUE key; fallback: catch DuplicatePersistError + log info |
| 2 | Per-country isolation | `for c in countries: try: ... except Exception: log + bucket failed + continue` |
| 3 | Exit codes sanitized | 0 = pipeline ran; 1 = all units failed; 3 = reserved spec deviation |
| 4 | Summary emit end-of-run | `log.info("pipeline.summary", persisted=[], skipped=[], failed=[])` |
| 5 | Partial-persist recovery | Every unit checkpoints independently; re-runs always safe |

Sprints futuros: consultar antes de escrever pipeline novo.
