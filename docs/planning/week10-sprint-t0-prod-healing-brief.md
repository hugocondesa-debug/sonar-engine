# Sprint T0 — Prod Healing (idempotency + resilience + backfill)

**Branch**: `sprint-t0-prod-healing`
**Worktree**: `/home/macro/projects/sonar-wt-t0-prod-healing`
**Data**: 2026-04-23 Day 3 manhã (~11:00 WEST arranque)
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy per SESSION_CONTEXT)
**Budget**: 3.5-4.5h solo
**ADR-0010 tier scope**: N/A (refactor-only — zero T1/T2 coverage change)
**ADR-0009 v2 TE Path 1 probe**: N/A (no country-data fetch)

---

## §1 Scope (why)

Overnight Apr 23 natural fires **failed em 3 services**:

1. `sonar-daily-curves.service` — exit 1 (07:01) depois exit 3 (07:11) depois systemd abort (07:21).
2. `sonar-daily-monetary-indices.service` — exit 3 (08:10) depois systemd abort (08:20).
3. `sonar-daily-cost-of-capital.service` — exit 1 (09:40) depois systemd abort (09:50).

**Root cause identificada** (diagnose completo §7 verification 2026-04-23 manhã):

- **Partial-persist + non-idempotent retry**: Run 1 de `daily_curves` processou US completo (persisted em `yield_curves_spot` com `UNIQUE(country_code, date, methodology_version)`), depois crashed `RetryError[HTTPStatusError]` antes de IT/ES/FR/PT/NL processarem. Run 2 recomeça do início → re-INSERT US → UNIQUE violation → `daily_curves.duplicate` error → exit 3. Run 3 abortado por systemd.
- **Cascade downstream**: `daily_monetary_indices` tenta ler curves forwards IT/ES/FR/PT/NL para Apr 22 → `m3_db_backed.forwards_missing` (upstream absent) → warnings legítimos. Erro de design: pipeline trata `no_inputs` para countries fora scope M1/M2/M4 EA-per-country (CAL-M2-EA-PER-COUNTRY deferred) como fatal → exit 3.
- **Cascade cost-of-capital**: `insufficient_data: No NSS spot row for country=IT/ES/FR/PT/NL` → raise → exit 1. Mesmo pattern: downstream falha upstream → fatal em vez de skip+continue.

**Shipped Sprints H/I (Day 2) não estão quebrados** — código IT/ES/FR curves built correto em dev. Gap é puramente runtime (partial-persist + fatal error-handling).

**Objectivo T0**: 3 services exit 0 green para natural fire Apr 24. Todos 9 T1 countries (US/DE/EA/GB/JP/CA/IT/ES/FR) com `yield_curves_spot` row para Apr 22 + Apr 23. ADR canónico a prevenir recorrência.

---

## §2 Spec (what)

### 2.1 Schema reference doc (prevent handoff drift)

Novo ficheiro `docs/architecture/db-schema-reference.md` documentando canonical names:

| Entity | Table | Date column | Unique |
|---|---|---|---|
| Curves spot | `yield_curves_spot` | `date` | `(country_code, date, methodology_version)` |
| Curves forwards | `yield_curves_forwards` | `date` | — |
| Curves zero | `yield_curves_zero` | `date` | — |
| M1 effective rates | `monetary_m1_effective_rates` | TBD via `.schema` | TBD |
| M2 Taylor gaps | `monetary_m2_taylor_gaps` | TBD | TBD |
| M3 (builder-only) | — | derives from `yield_curves_forwards` | — |
| M4 FCI | `monetary_m4_fci` | TBD | TBD |
| L4 MSC composite | `monetary_cycle_scores` | TBD | TBD |
| Economic E1/E3/E4 | `idx_economic_e1_activity` / `e3_labor` / `e4_sentiment` | TBD | TBD |
| Cost-of-capital | `cost_of_capital_daily` | TBD | TBD |
| Credit L1-L4 | `credit_cycle_scores` + `credit_*` | TBD | TBD |
| Financial F1-F4 | `f1_valuations` / `f2_momentum` / `f3_risk_appetite` / `f4_positioning` + `financial_cycle_scores` | TBD | TBD |

CC: completar TBDs via `.schema <table>` para cada entity. Single source of truth futuro. Handoff naming gap (`nss_yield_curves_spot`) não recorrerá.

### 2.2 `daily_curves.py` — idempotency + per-country isolation

**Duplicate handling** (persist layer):
- Actual: `raise` em UNIQUE violation → exit 3.
- Target: catch `IntegrityError` específico de `uq_ycs_country_date_method` → log warning `daily_curves.skip_duplicate country=X date=Y` → return `persisted=0, skipped=1`.
- Alternativa cleaner: builder verifica existence com `SELECT 1 FROM yield_curves_spot WHERE country_code=? AND date=? AND methodology_version=?` antes de INSERT. Se exists, skip. (Preferir esta — evita exception handling overhead e limpa logs.)

**Per-country isolation** (dispatcher):
- Actual: qualquer exception num country mata pipeline inteiro.
- Target: dispatcher loop com `try/except Exception as e` por country. Log `daily_curves.country_failed country=X error=...`. Continua para próximo country.
- Exit code: 0 se ≥1 country persisted ou skipped_duplicate com sucesso. 1 apenas se **todos** countries failed com exceção não-recuperável.

**Pipeline summary emit**:
- End-of-run info log com `daily_curves.summary persisted=N skipped=M failed=K countries_ok=[...] countries_failed=[...]`. Facilita diagnose futuro.

### 2.3 `daily_monetary_indices.py` — exit code sanitization

**no_inputs handling**:
- Actual: PT/IT/ES/FR/NL → `no_inputs` para M1/M2/M4 → contabiliza como failure → exit 3.
- Target: `no_inputs` é **estado esperado** para EA members (M1/M2/M4 per-country ainda não implementados, CAL-M2-EA-PER-COUNTRY deferred Phase 2+). Log info `monetary_pipeline.expected_no_inputs country=X indices=[m1,m2,m4] reason=per_country_ea_deferred`. Não contribui para exit code.
- Criterion revisto: exit 0 se pipeline corre até ao fim sem exception estrutural. Exit 1 **apenas** se uncaught exception (não `no_inputs`, não `builder_skipped`).

**m3 forwards_missing**:
- Actual: warning emit, mas combinado com no_inputs monetary parece contribuir para exit 3 noise.
- Target: explicit downgrade to `info` level em countries onde curves upstream é esperado absent. Warning mantém-se para countries T1 shipped onde curves devia estar (US/DE/EA/GB/JP/CA/IT/ES/FR) — sinal genuíno de problema upstream.

### 2.4 `daily_cost_of_capital.py` — resilience

**Duplicate k_e**:
- Actual: `cost_of_capital.duplicate country=US/DE error='k_e already persisted...'` → contribui para exit 1.
- Target: skip+continue pattern. Log info, não error.

**insufficient_data upstream**:
- Actual: `No NSS spot row for country=IT/ES/FR/PT/NL` → raise → exit 1.
- Target: skip country, continue pipeline. Log warning para T1 countries shipped (IT/ES/FR — sinal genuíno se curves falhou upstream) vs info para countries não-shipped (PT/NL — expected).

### 2.5 Manual backfill Apr 22 + Apr 23

Após §2.2 shipped e merged, correr manual:

```bash
cd /home/macro/projects/sonar-engine
uv run python -m sonar.pipelines.daily_curves --all-t1 --date 2026-04-22
uv run python -m sonar.pipelines.daily_curves --all-t1 --date 2026-04-23
uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-22
uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23
uv run python -m sonar.pipelines.daily_cost_of_capital --all-t1 --date 2026-04-22
uv run python -m sonar.pipelines.daily_cost_of_capital --all-t1 --date 2026-04-23
```

Verify:
```bash
sqlite3 data/sonar-dev.db "SELECT country_code, MAX(date) AS latest, COUNT(*) AS n FROM yield_curves_spot GROUP BY country_code ORDER BY country_code;"
```

Expected: 9 T1 countries com `latest = 2026-04-23`. PT/NL ausentes (expected — Sprint M unshipped).

### 2.6 ADR-0011 — Systemd service idempotency + partial-persist recovery

Novo `docs/adr/ADR-0011-systemd-service-idempotency.md`. Canonical pattern para todas as future pipelines:

- **Principle 1**: Idempotency per row. Duplicate detection = skip+continue, nunca raise.
- **Principle 2**: Per-country isolation. Dispatcher loop com per-country try/except. Pipeline-level exit 0 se ≥1 unit succeeded.
- **Principle 3**: Exit codes sanitized. Exit 0 = happy path OR expected skips. Exit 1 = uncaught exception. Exit 3 reservado para spec deviation (NotImplementedError genuíno).
- **Principle 4**: Summary emit end-of-run. `pipeline.summary persisted=N skipped=M failed=K` para diagnose post-hoc.
- **Principle 5**: Partial-persist recovery. Run N+1 assume state from Run N pode ser parcial. Cada unit de trabalho (country × index × date) é checkpoint independente.

Affects: `daily_curves`, `daily_monetary_indices`, `daily_cost_of_capital` (Sprint T0 scope). Apply to future pipelines (economic, ERP, M3 expansion).

---

## §3 Commits plan

| Commit | Scope | Ficheiros esperados |
|---|---|---|
| **C1** | docs: ADR-0011 draft + schema reference doc | `docs/adr/ADR-0011-systemd-service-idempotency.md`, `docs/architecture/db-schema-reference.md` |
| **C2** | refactor: `daily_curves.py` idempotency + per-country isolation + summary emit | `sonar/pipelines/daily_curves.py`, eventual `sonar/dal/curves_dal.py` |
| **C3** | refactor: `daily_monetary_indices.py` exit-code sanitization + m3 forwards warn downgrade | `sonar/pipelines/daily_monetary_indices.py` |
| **C4** | refactor: `daily_cost_of_capital.py` duplicate + insufficient_data resilience | `sonar/pipelines/daily_cost_of_capital.py` |
| **C5** | ops: manual backfill Apr 22 + Apr 23 verification + SESSION_CONTEXT schema naming fix | logs + SESSION_CONTEXT.md update |
| **C6** | docs: Sprint T0 retrospective | `docs/planning/week10-sprint-t0-retrospective.md` |

---

## §4 HALT triggers

**HALT-0 (structural schema mismatch)**:
- Se `.schema <table>` revelar que algum builder persiste em tabela cujo nome **não existe** em prod DB (ex: builder usa `monetary_m3_expectations` mas tabela não existe) → STOP. Report. Hugo decide: table migration OR builder refactor.

**HALT-material (spec deviation)**:
- Se após §2.2 + §2.3 + §2.4 refactor, manual backfill §2.5 **ainda falhar** para IT/ES/FR/US/DE (countries shipped) → STOP. Root cause = upstream data genuinely missing, não pipeline bug. Report.
- Se schema reference doc revelar que M1/M2/M4 têm tabela com column name inconsistente (ex: `obs_date` em M1, `observation_date` em M2) → STOP. Flag schema standardization CAL.

**HALT-scope**:
- Qualquer item demandar country-data probe (PT curves, NL curves, novo indicador) → STOP. Defer a Sprint M/O.
- Qualquer item demandar connector novo → STOP. Out of scope T0.
- Qualquer item demandar migration (ALTER TABLE) → STOP. ADR novo primeiro.

**HALT-security**: standard (secret leak, unauthorized external call).

---

## §5 Acceptance

**Services green** (correr em sequência no fim):
```bash
sudo systemctl start sonar-daily-curves.service && sleep 120 && systemctl is-active sonar-daily-curves.service
sudo systemctl start sonar-daily-monetary-indices.service && sleep 120 && systemctl is-active sonar-daily-monetary-indices.service
sudo systemctl start sonar-daily-cost-of-capital.service && sleep 120 && systemctl is-active sonar-daily-cost-of-capital.service
```
Expected: `active` or `inactive` (com clean exit 0) em todos. Zero `failed`.

**Journal clean**:
```bash
sudo journalctl -u sonar-daily-curves.service --since "<T0 acceptance time>" --no-pager | grep -iE "error|exception|traceback" | head -20
```
Expected: zero ERROR level (warnings OK). Idem monetary + cost-of-capital.

**DB coverage** (curves 9 T1 countries):
```bash
sqlite3 data/sonar-dev.db "SELECT country_code, MAX(date) AS latest, COUNT(*) AS n FROM yield_curves_spot GROUP BY country_code ORDER BY country_code;"
```
Expected: US/DE/EA/GB/JP/CA/IT/ES/FR com `latest >= 2026-04-22`. PT/NL ausentes (acceptable).

**Docs shipped**: ADR-0011 + schema reference doc + T0 retrospective present.

**Pre-commit**: `uv run pre-commit run --all-files` clean.

**Git state**: main fast-forward clean após merge, worktree removido, tmux session killed.

---

## §6 Retro scope (Week 10 lesson #6)

Documentar em `docs/planning/week10-sprint-t0-retrospective.md`:

1. **Pattern identificada**: partial-persist + non-idempotent retry. Causou 3 service failures overnight.
2. **Fix canónico**: ADR-0011 — 5 principles. Retro-aplicar a Sprint M/O futuros.
3. **Handoff naming gap**: handoff Day 3 referiu `nss_yield_curves_spot` / `indices_spot` — ambos wrong. Schema ref doc prevent recorrência.
4. **Day 3 pacing adjustment**: T0 consumiu ~4h manhã. Pair A reduzido a Sprint M solo afternoon. Sprint O desloca Day 4. Net: -1 sprint velocity Day 3, +ADR canónico + prod green.
5. **Servicel-level observation window**: propor tuning `StartLimitIntervalSec` + `StartLimitBurst` no systemd unit files (actualmente aborta após 2 retries em ~10min — razoável mas vale explicitar).
6. **M3 insight**: builder-only pattern (DB-backed via `yield_curves_forwards`). Relevante para Sprint O futuro — M3 expansion é puro builder extension, zero schema migration.

---

## §7 Execution notes

- **Começa por §2.1 schema audit** — revelará eventual HALT-0 early, não blocked até ao fim.
- **§2.2 C2 é o commit mais crítico** — testa idempotency via manual re-run `daily_curves` para US Apr 22 (expect: skip, exit 0). Se funcionar, princípio validated.
- **§2.5 backfill não persiste PT/NL** — não são shipped. Não é HALT, é expected.
- **Pre-commit double-run** entre cada commit (Week 10 lesson Day 2 #2).
- **tmux cleanup** no `sprint_merge.sh` Step 10 quando shipped.

---

*End of brief. Production-grade discipline. Ship sustainable.*
