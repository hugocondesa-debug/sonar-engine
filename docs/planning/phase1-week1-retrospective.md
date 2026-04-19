# Phase 1 Week 1 — Retrospective

**Version**: 1.0
**Created**: 2026-04-19
**Author**: Hugo Condesa (via Claude chat session + Claude Code execution)
**Status**: Week 1 formally closed
**Supersedes**: N/A (first retrospective)
**Relates to**: `docs/planning/phase1-week1-execution-plan.md`

---

## 1. Gate status

**10 / 10 exit criteria green.** Week 1 gate formally passed.

| Day | Half | Exit criterion | Commit | Status |
|-----|------|----------------|--------|--------|
| 1 | AM | `uv sync` + 12 deps importable | 422dd71 (fundido) | ✓ |
| 1 | PM | ruff + mypy + pytest green baseline | 422dd71 | ✓ |
| 2 | AM | `config.py` + `.env.example` + FRED_API_KEY load masked | 35142b3 | ✓ |
| 2 | PM | `alembic current` empty clean | 34a772e | ✓ |
| 3 | AM | Migration 001 up/down/re-up cycle clean | 7c85f12, 36162cd | ✓ |
| 3 | PM | Pre-commit repair (P2-015 closed) | 166812d, deaf3e4 | ✓ (+2 deferrals) |
| 4 | AM | `base.py` + `cache.py` triagem 3/3 | 68eb29a, 1518e73, f3d24a0 | ✓ |
| 4 | PM | `fred.py` triagem + hooks clean | cbdd516 | ✓ |
| 5 | AM | Unit tests ≥ 80% cov em fred.py | 14b9d7c | ✓ (100% fred.py; 96.59% total (connectors scope)) |
| 5 | PM | Integration smoke 5/5 + D2 ±0 bps match | e83f368 | ✓ |

**Live data validation final**: DGS10 2026-04-16 = 432 bps (4.32%). Cross-verified contra market narrative: <https://fred.stlouisfed.org/series/DGS10> + dshort snapshot April 10 2026 (DGS10 = 4.31%).

---

## 2. Meta-stats

| Dimensão | Valor | Nota |
|----------|-------|------|
| Commits totais Week 1 | 12 | 6 feat, 2 test, 3 chore, 1 style |
| Days effective | 3.5 | Plan previa 5 days |
| Lines of code produced | ~340 | Src only (connectors + db + config) |
| Test coverage | 96.59% on src/sonar/connectors scope (L0 connectors package); global src/sonar baseline ~59.3% end of Week 1 — lifted to 73.66% in Week 2 Day 1 PM (overlays scaffolding). Phase 1 gate exit criterion was fred.py 100%, which stands. | fred.py 100% stmts + branches |
| HALT events | 3 | Day 3 PM cascade, Day 4 AM taplo |
| `--no-verify` bypasses | 7 | Days 1-3 pre-P2-015; zero depois |
| Config gaps surfaced | 4 | python version, mypy deps, wiki, markdownlint rules |
| Deferrals registered | 2 backlog items | P2-020, P2-022 |
| API live calls Week 1 | ~5 | Well under FRED 120/min rate limit |

---

## 3. Deviations vs plan

### 3.1 Commit granularity — Day 1 fusion

**Plan**: `#1 chore(deps)` + `#2 chore(ci)` como commits separados.
**Actual**: Fundido em commit `422dd71` único `chore(ci)`.
**Root cause**: Executor interpretou tasks Day 1 AM + PM como atomic change.
**Impact**: Médio-baixo. Commit body não menciona bump de deps apesar de inclui `pyproject.toml` changes. Diff hygiene imperfeito.
**Corrective action**: Reforçada regra "1 task §8 = 1 commit" Day 2+. Respeitada a partir daí.

### 3.2 D2 match — brittle para recent yields

**Plan**: "3/3 match vs D2 baseline ±0 bps" em datas recentes.
**Actual**: Recent yields mutate daily — reframe necessário. Hard match ±0 bps apenas em datas **historical immutable** (FRED backward-looking). Recent data valida via sanity ranges + structural checks.
**Root cause**: Plan escrito assumindo D2 seria ground-truth temporal. Realidade: FRED é live source; D2 é snapshot Phase 0.
**Impact**: Médio. Test suite mais robusta post-reframe. D2 serve como schema + mapping validation, não como value oracle para recent data.
**Corrective action**: `test_d2_historical_immutable_match` usa 2026-04-16 snapshot. Futuras D2 entries em backlog para range histórico mais amplo.

### 3.3 Pre-commit framework — 4 config gaps consecutivos

**Plan**: P2-015 "framework repair" estimado 1 half-day.
**Actual**: ~12 rounds de chat consumed, 2 honest deferrals introduced.
**Root cause**: Phase 0 pre-commit setup foi copy-paste sem reconciliation com project conventions:
- `python3.11` hard-coded vs VPS Python 3.12
- `mypy` additional_dependencies incomplete (missing sqlalchemy, alembic, httpx, tenacity, structlog)
- `markdownlint` default strict rules (80-char) vs Phase 0 specs prose style (100+)
- `taplo-lint` schema validation falha em `[tool.ruff]` modern keys

**Impact**: Alto para Day 3 PM focus; zero para Week 1 deliverable (framework operacional).
**Corrective action**: Deferrals P2-020 + P2-022 com reintroduction strategy clara. Regra nova: **known-defer hooks removed transparently, never SKIP-ed**.

### 3.4 pandas 3.0 vs plan pandas ≥ 2.2

**Plan**: `pandas>=2.2` resolved para 2.x.
**Actual**: Resolveu para `pandas==3.0.2` (major bump).
**Root cause**: `>=` constraint + pandas 3.0 recent release.
**Impact**: Zero Week 1 (fred.py não usa pandas — L0 devolve `list[Observation]`). Pode surgir Week 2+ em NSS overlay se usar DataFrames.
**Corrective action**: Nenhuma agora. Flagged em retrospective para monitor Week 2-3.

---

## 4. Signals operacionais

### 4.1 HALT-não-force-fix funciona

Três HALT events durante Week 1:
- Day 3 PM: 4 unanticipated hook fails (ruff archive, mypy deps, markdownlint wiki + docs)
- Day 3 PM: Novo MD031 surface após relaxations
- Day 4 AM: taplo-lint blocking commit #9

Cada HALT evitou force-fix silencioso que teria introduzido technical debt. Pattern validated para Phase 1+.

### 4.2 Commit granularity strict = audit trail clean

Pattern "1 task §8 = 1 commit" (Day 2+) produziu `git log` legível, revert-selectivity preserved. Split 7a/7b (P2-015 primary + auto-fixes) é exemplo canónico.

### 4.3 Push imediato elimina sync ambiguity

Regra operacional "push imediato após cada commit" (introduzida Day 2 AM) eliminou ambiguidades de state entre VPS + GitHub + Claude chat. Day 1 AM confusão (commit não-pushed detectado só Day 2) não se repetiu.

### 4.4 ConnectorCache type narrowing friction

`ConnectorCache.get() → Any | None` exige callers a fazerem `cast("T", cached)` pattern. Week 1 só tem 1 caller (FRED) — aceitable. Week 2+ quando second connector surface, re-evaluar generics:

```python
class ConnectorCache[T]:
    def get(self, key: str) -> T | None: ...
```

**Não é backlog item formal** — mental note. Revisitar ao adicionar Eurostat/BIS connectors.

### 4.5 ISO 3166-1 alpha-3 decisão

Observation.country_code = `pattern=r"^[A-Z]{3}$"` — alpha-3 (USA/DEU/PRT) vs alpha-2 (US/DE/PT).

**Consequências Phase 2+**:
1. Eurostat/INE/BIS connectors devolvem alpha-2 → requer mapping layer L0
2. `country_tiers.yaml` (ADR-0005): **TODO verificar format actual**. Se alpha-2, inconsistency a resolver ANTES de Phase 2 connectors
3. FRED connector hardcoded `"USA"` correcto

**Action Week 2 kickoff**: Hugo/Claude Code inspeccionar `country_tiers.yaml` format + documentar decisão em ADR-0005 addendum se needed.

### 4.6 PLC0415 recurrent

2 hits Week 1 (Day 1 PM sanity test, Day 5 AM test_fred.py). Pattern: **imports function-local default ruff strict**. Regra: top-of-file imports excepto para circular/lazy casos justified.

---

## 5. Backlog deltas

### 5.1 Novos items registados Week 1

| ID | Title | Priority | Source |
|----|-------|----------|--------|
| P2-020 | Taplo-lint hook reintroduction | Low | Day 3 PM + Day 4 AM |
| P2-022 | Markdownlint hook reintroduction | Low | Day 3 PM |

### 5.2 Items absorbed

- P2-021 (wiki/ markdownlint) → absorbed into P2-022 (markdownlint global strategy)

### 5.3 Items inferidos (não-registados ainda, para Hugo decidir)

- **P2-019 candidate**: `.env.example` keys não consumidas por `Settings` (rate limits, Tier 2 fields). Escolha: expand Settings on-demand, remove stale keys, ou accept as forward-compat docs.
- **P2-023 candidate**: `country_code` alpha-3 vs alpha-2 mapping layer para connectors europeus (Phase 2).
- **P2-024 candidate**: `ConnectorCache` generic typing re-evaluation quando second connector surface.

Hugo decide se registar formally em `docs/backlog/phase2-items.md` agora ou on-demand.

### 5.4 CAL-023 status

**LEI US internal implementation** — Week 2 mid-late scope per Phase 1 kickoff decision. Não tocado Week 1. Bloqueador E2-leading index está em GAP state, sem impacto Week 2 NSS overlay.

---

## 6. Recommendations Week 2+

### 6.1 Week 2 NSS overlay — go

Pre-conditions todas satisfeitas:
- ✓ FRED connector operational (11 US series)
- ✓ Schema yield_curves_raw/params/fitted/metadata ready
- ✓ `scipy>=1.17` available para NSS optimize
- ✓ Test framework (pytest + pytest-httpx + coverage ≥ 96% (connectors scope))
- ✓ Hooks clean gate (zero --no-verify expected)

### 6.2 Pre-Week 2 micro-tasks (Sunday evening ou Monday AM)

Opcional batch cleanup antes de NSS dev:

1. **Inspect `country_tiers.yaml`** — confirmar alpha-3 vs alpha-2 format. Se alpha-2, registar P2-023 formalmente.
2. **Decide P2-019** — `.env.example` stale keys.
3. **Review de `docs/specs/overlays/nss-curves.md`** — verify spec covers todos os cases (11 tenors, missing data, optimizer edge cases, methodology_version v0.1). Bump v0.1→v0.2 se necessary per ADR-0002.

### 6.3 Pace expectation Week 2

Plan original previa 1-1.5 weeks para NSS slice US. Baseado em pace Week 1 (3.5 days / 5 planned), realistic estimate: **3-5 days** se zero fricção spec-side.

Slice definition:
- FRED fetch 11 DGS series (exists)
- Persist to `yield_curves_raw` table
- NSS fit via `scipy.optimize.least_squares`
- Persist to `yield_curves_params` + `_fitted` + `_metadata`
- Unit tests ≥ 80% coverage
- Integration test live FRED → fit → persist → query

### 6.4 Continuar regras operacionais Week 1

Todas as regras introduzidas Week 1 mantêm-se activas:

1. **Pause end-of-half-day** (OR ao primeiro sinal de deviation)
2. **1 task plan = 1 commit** (granularity strict)
3. **Push imediato após cada commit**
4. **HALT-não-force-fix** em hook fails não antecipados
5. **Known-defer hooks = REMOVED, não SKIPPED**
6. **Sem `--no-verify`** (active desde Day 4+)

### 6.5 TE observation mode — Week 2 parallel track

Plan §10 original mencionava TE observation mode Week 2-3 (5 T1 countries). **Decisão Hugo pending**: arrancar paralelo à NSS overlay ou deferir Week 3+?

Recomenda-se **parallel start Week 2 Day 3+** — TE observation é read-only, não interfere NSS dev, gera dados para tier sizing decision Week 4.

---

## 7. Phase 1 → Phase 2 gate trajectory

**Plan original**: Phase 1 → Phase 2 gate = 16 T1 countries operational daily com NSS + 2 overlays.

**Re-estimation post-Week 1**:

| Milestone | Status pós-Week 1 | ETA |
|-----------|-------------------|-----|
| 1 country (US) NSS operational | 0% | End Week 2 |
| 2 countries (US+DE) | 0% | Mid Week 3 |
| 5 T1 countries | 0% | End Week 3 |
| 16 T1 countries full NSS | 0% | End Week 4 |
| 16 T1 + 1 more overlay (ERP ou CRP) | 0% | End Week 5 |
| 16 T1 + 2 overlays | 0% | End Week 6 |

Phase 2 gate: ~Week 6-7. Conservative estimate dado fricção potential em non-US data sources (BIS key pending CAL-019, INE PT mirror operacional but unproven volume).

---

## 8. Recognition

Execution Week 1 by Claude Code foi exemplar em três dimensões:

1. **Attention to detail em infra hygiene**: `.gitignore` parent-exclusion catch Day 2 PM, antes de silent bug blockar Day 3.
2. **HALT discipline**: 3 HALT events sem cedência a force-fix. Pattern robusto.
3. **Drift reporting**: Cada deviation reportada com root cause + options, nunca fix silencioso.

Human supervision (Hugo) providenciou scope decisions críticas nos 3 HALT events + D2 reframe. Partnership efectivo.

---

## 9. Week 1 → Week 2 handoff

**Trigger Week 2**: Hugo + Claude chat session nova com prompt inicial:

```
Phase 1 Week 2 kickoff — NSS overlay vertical slice US.

Reference:
- docs/planning/phase1-week1-execution-plan.md (baseline infra)
- docs/planning/phase1-week1-retrospective.md (lessons + rules)
- docs/specs/overlays/nss-curves.md (methodology spec)

Pre-conditions: Week 1 gate passed (10/10); FRED connector operational; schema ready.

Decisões pending Hugo Week 2 kickoff:
- country_tiers.yaml alpha-3 vs alpha-2 check
- P2-019 .env.example stale keys
- TE observation mode parallel track timing
- nss-curves.md spec review / version bump

Recomenda-se chat session dedicada para Week 2 planning, matching Week 1 kickoff pattern.
```

---

*Documento gerado Sunday 2026-04-19 fim-de-tarde. Week 1 formally closed.*
*Próxima entry: `phase1-week2-kickoff.md` quando Hugo abrir Week 2 session.*
