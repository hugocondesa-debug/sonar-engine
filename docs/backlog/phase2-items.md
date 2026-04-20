# Phase 2+ items — backlog parkado

Items arquiteturais, operacionais e documentacionais deferidos para fases posteriores. Organizados por categoria temática. Cada item: descrição curta · target phase · dependency · critério de activação.

## Sumário por categoria

| Categoria | Count | Target phase dominante |
|---|---|---|
| Arquitectura | 4 | Phase 2-3 |
| Integration & outputs | 3 | Phase 3 |
| Infrastructure | 2 | Phase 4+ |
| Documentation | 3 | Phase 3+ |
| Data reconsiderations | 1 | Phase 3+ |
| Connectors unspeced | 1 | Phase 1-2 |

**14 items total** (P2-001 a P2-014).

## Arquitectura

### P2-001 — L5 Regimes migration (colunas L4 → tabela própria)

**Status**: pending
**Target phase**: Phase 2
**Descrição**: overlay booleans (Stagflation, Boom, Dilemma, Bubble Warning) vivem como colunas em `*_cycle_scores` em v0.1. Phase 2+ reifica como tabela `regimes/` com `active`, `intensity`, `duration_days`, transition probabilities.
**Dependency**: L4 cycles estáveis em produção (≥ 12m observations).
**Critério activação**: Phase 2 arranca OR ≥ 30 regime transitions observadas combinadas em ECS+CCCS+MSC+FCS.
**Decisão pendente**: transition probability model (Markov simples vs HMM vs empirical frequencies). Registar em ADR novo quando activar.

### P2-002 — F3 ↔ M4 reconciliation v0.2

**Status**: conditional
**Target phase**: Phase 2+ (evidence-dependent)
**Descrição**: `indices/monetary/M4-fci` e `indices/financial/F3-risk-appetite` consomem inputs parcialmente sobrepostos (NFCI, CISS, VIX). v0.1 lêem independentemente com z-scores próprios. v0.2 candidate: reconciliar para shared source com single normalization.
**Dependency**: `F3_M4_DIVERGENCE` flag tracked (persistido em v0.2 FCS scope).
**Critério activação**: se `F3_M4_DIVERGENCE` fire > X% de dias em janela rolling 12m (threshold X por definir, placeholder typical 15-20%), abrir RFC + decidir reconciliation. Se fire < X%, manter independentes (observability signal suficiente).

### P2-003 — Postgres migration gate review

**Status**: pending (conditional)
**Target phase**: Phase 2 final gate
**Descrição**: 4 gates documentados em [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §10 e [`../adr/ADR-0003-db-path-sqlite-postgres.md`](../adr/ADR-0003-db-path-sqlite-postgres.md): (a) multi-user, (b) concurrent writes, (c) DB > 30 GB, (d) cloud 24/7. Phase 2 final tem review formal.
**Dependency**: Phase 2 scope complete.
**Critério activação**: gate review produz ADR novo — "Postgres migration decided" OR "SQLite retained Phase 3+".

### P2-004 — Cross-cycle composite `matriz-4way` (L6)

**Status**: pending
**Target phase**: Phase 3
**Descrição**: L6 integration layer com classificação canonical `ECS × CCCS × MSC × FCS → 16 estados canónicos + outliers`. Directório `docs/specs/integration/` actualmente vazio.
**Dependency**: L4 cycles em produção ≥ 6m.
**Critério activação**: Phase 3 arranca.

## Integration & outputs

### P2-005 — L6 `cost-of-capital` composite

**Status**: pending
**Target phase**: Phase 3
**Descrição**: composite per country `cost_of_equity_country = risk_free_country + β·ERP_mature + CRP_country`. β sourcing documentado (placeholder — decisão entre raw/Blume/Vasicek adjusted).
**Dependency**: overlays NSS + ERP + CRP estáveis (Phase 2 complete).

### P2-006 — L6 `diagnostics/` composites

**Status**: pending
**Target phase**: Phase 3
**Descrição**: 4 composites diagnostic em [`../specs/integration/`](../specs/integration/) (a criar Phase 3): `bubble-detection` (FCS + BIS credit gap + property gap), `minsky-fragility` (CCCS + DSR z-score), `real-estate-cycle` (property gap + mortgage rates + CRE REIT), `risk-appetite-regime` (F3 + VIX + credit spreads).

### P2-007 — L7 outputs rich (CLI + API + editorial + alerts + dashboard)

**Status**: pending
**Target phase**: Phase 3
**Descrição**: 5 sub-systems — Typer CLI completo, FastAPI JSON endpoints, editorial pipeline (angle detection + briefing generator + markdown templates para Substack), alerts (threshold breach, regime shift via email/Telegram), Streamlit dashboard MVP interno.
**Dependency**: L4 + L6 estáveis.
**Decisão pendente**: BRIEF §4 dashboard tech (Streamlit MVP confirmed; React Phase 4+ conditional).

## Infrastructure

### P2-008 — MCP server exposure (Cloudflare tunnel)

**Status**: pending
**Target phase**: Phase 4+
**Descrição**: `cloudflared` tunnel preservado em `/etc/cloudflared/` (inactive). Hostnames `sonar.hugocondesa.com` + `mcp.hugocondesa.com`. Reactivate quando L7 outputs em produção.
**Dependency**: L7 FastAPI + MCP server implementado.
**Critério activação**: autorização explícita do Hugo + L7 estável.

### P2-009 — React/TypeScript dashboard produção

**Status**: conditional
**Target phase**: Phase 4+
**Descrição**: substituto Streamlit MVP. Conditional a (a) fund launch OR (b) Streamlit limitations hit (performance, embedding, multi-user).
**Decisão pendente**: ADR novo quando activar.

## Documentation

### P2-010 — README.md raiz rewrite

**Status**: pending
**Target phase**: Phase 3+ (quando repo for considerado para público)
**Descrição**: `README.md` actual tem 3 refs stale detectadas no Bloco 4a: linha 92 (`sonar/submodels/`), linha 118 e 149 (`CODING_STANDARDS.md`). Phase 3+ rewrite quando repo visibility re-avaliada.
**Dependency**: ADR de licensing (BRIEF §5) + visibility (BRIEF §11).

### P2-011 — Wiki público sync

**Status**: pending
**Target phase**: Phase 3+
**Descrição**: `wiki/` no repo (v1 legacy, 9 ficheiros com naming pré-rename) ≠ GitHub Wiki do repo. Sync manual quando conteúdo conceptual for aberto publicamente.
**Dependency**: decisão licensing (BRIEF §5, ADR futuro).

### P2-012 — ASCII DAG alignment (cosmético)

**Status**: micro-débito
**Target phase**: oportunista
**Descrição**: diagrama DAG em `ARCHITECTURE.md §6` tem caracteres box-drawing (`├`, `│`, `└`, `─`) ligeiramente desalinhados após edit B6 do Bloco 1 (rename `L1 L2 L3 L4` → `credit/L1 credit/L2 credit/L3 credit/L4`). Monospaced renderers continuam legíveis; débito registado mas não bloqueante.

## Data reconsiderations

### P2-013 — DuckDB analytics read-only

**Status**: conditional
**Target phase**: Phase 3+ (reconsideration)
**Descrição**: DuckDB considerado e rejeitado para MVP em [`../adr/ADR-0003-db-path-sqlite-postgres.md`](../adr/ADR-0003-db-path-sqlite-postgres.md) (maturity SQLAlchemy menor, migration path indirecto). Reconsideration Phase 3+ para read-only analytics sobre dados persistidos — ADR novo nessa altura.
**Dependency**: dados persistidos em Postgres OR SQLite (Phase 2 gate decidido).

## Connectors unspeced

### P2-014 — Communication Signal connectors

**Status**: pending
**Target phase**: Phase 1+ (MSC CS component)
**Descrição**: `connectors/central_bank_nlp`, `connectors/fed_dissent`, `connectors/dot_plot` mencionados em [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §6 call-out "CS de MSC" mas não speced. Em Phase 0-1, `COMM_SIGNAL_MISSING` é expected default; MSC aplica Policy 1 re-weight sem bloquear.
**Dependency**: Phase 1 MSC em produção com `COMM_SIGNAL_MISSING` baseline; Phase 2+ decide se CS merece specs formais ou continua opcional.

## Tooling

### P2-021 — wiki/ markdownlint discipline (ABSORBED INTO P2-022)

**Status**: absorbed into P2-022 (Day 3 PM same block)
**Descrição original**: `wiki/` é GitHub Wiki subtree bidirectional-synced; escopo era CI-side markdownlint strategy apenas para wiki/. Markdownlint hook completely removed em P2-022; wiki/ scope cai dentro dessa decisão bigger. Retain entry para rastreabilidade histórica.

### P2-022 — Markdownlint hook reintroduction

**Status**: pending
**Target phase**: Phase 2+ (low priority, docs quality)
**Descrição**: Markdownlint hook removido Day 3 PM Phase 1 Week 1 (commit #7) após 4 config gaps consecutivos surfaced durante P2-015 repair validation:

- MD013 line-length conflict (projecto 100-char vs default 80-char).
- MD024/033/036/040/041 various strictness rules incompatible com specs style (cross-refs longos, tables com embedded links).
- MD031 fence blanks surfaced após primeira round de relaxations applied.
- Additional MD013 prose line violations em `README.md` + `docs/specs/pipelines/` post-exclude `wiki/`.

**Root cause**: tooling setup Phase 0 bootstrap sem reconciliation com project prose conventions. Phase 0 content inclui specs com cross-refs longos, tables com embedded links, README bootstrap narrative.

**Reintroduction strategy Phase 2+**:
- (a) Define project markdown convention FIRST (line length, heading structure, fence conventions, list blanks); document em `conventions/markdown.md` (novo).
- (b) Generate `.markdownlint.yaml` matching convention exactly.
- (c) Reformat Phase 0 + Phase 1 existing content to conform (scope: ~30+ line edits across 5+ files + README.md).
- (d) Reintroduce hook only após (a)+(b)+(c) complete.

**Scope absorbed**: P2-021 (wiki/ CI-side markdownlint) cai dentro desta decisão — mesma hook, mesmo processo.

**Effort estimate**: 1-2 days (mostly content reformat).
**Priority**: Low. Docs-quality concern, não operational blocker.
**Safety consideration**: MD rules não detectam code issues; P2-015 security hooks (detect-secrets + gitleaks) são the real protection layer.

### P2-020 — Taplo-lint hook reintroduction

**Status**: pending (hook REMOVED Day 4 AM Phase 1 Week 1)
**Target phase**: Phase 2+ (low priority)
**Descrição**: Taplo-lint hook REMOVED em minor commit precedente ao connectors cache (Day 4 AM) após block de commit #9 por pre-existing schema violations em ruff config keys em `pyproject.toml`. Matches P2-022 (markdownlint) precedent — hook removed honestly em vez de SKIP pattern que degradaria framework transparency.

**Root cause**: taplo default schema validation não reconhece algumas keys de ruff config modernas (linter subset tables `[tool.ruff.lint]` + `[tool.ruff.lint.per-file-ignores]` + `[tool.ruff.lint.isort]`). Pre-existent desde Phase 0 bootstrap (confirmed D4 hotfix pass + P2-015 Day 3 PM validation).

**Kept operational**: `taplo-format` hook continua active (format discipline preserved). `taplo-lint` removed only.

**Reintroduction strategy Phase 2+**:
- (a) Migrate ruff config de `pyproject.toml` para `ruff.toml` dedicated file (separa concerns; taplo-lint scoped a non-ruff TOML).
- (b) Configure taplo schema override via `taplo.toml` com custom schema accepting ruff keys.
- (c) Evaluate se `taplo-format` sozinho (sem lint) é suficiente — lint catch-rate vs format-only.

**Effort estimate**: 30-60 min once strategy chosen.
**Priority**: Low. TOML files são config-only, zero executable risk. `taplo-format` preserva discipline.

**Operational rationale**: known-defer hook blocking real commits recurrently = framework fragility. Remove hook transparently > establish SKIP=X pattern (two-tier fake vs real hooks distinction degrades commit gate credibility).

## Workflow de desparking

1. Item reaches target phase OR critério satisfeito.
2. Item escalated: PR dedicado cria spec (se aplicável) OR ADR (se decisão estrutural) OR código (se implementation).
3. Este ficheiro actualiza: status pending → in-progress → done.
4. Item `cancelled`: rationale obrigatório + preserva-se no registo.

## Referências

- [`../ROADMAP.md`](../ROADMAP.md) §Phase 2-4 + §Não-fases
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §10 Out-of-scope
- [`../BRIEF_FOR_DEBATE.md`](../BRIEF_FOR_DEBATE.md) — decisões pendentes que alimentam items
- [`calibration-tasks.md`](calibration-tasks.md) — sister doc, calibração empírica

## P2-019: `.env.example` stale keys reconciliation

**Target phase**: Phase 2+ (low priority)
**Descrição**: `.env.example` herdou de Phase 0 bootstrap keys que `sonar.config.Settings` Phase 1 não consome: rate limits, Tier 2 overrides, notifications, feature flags. Pydantic `extra="ignore"` silencia keys em runtime — benigno mas cria documentação drift (developer copia `.env.example` → `.env`, set valores em keys stale, expectation falsa de efeito operacional).
**Root cause**: Phase 0 `.env.example` foi escrito antes de `Settings` class existir (Day 2 AM Phase 1). Keys reflectem intenção de features, não state actual.
**Opções Phase 2+**:
- (a) Expand `Settings` on-demand conforme features consumirem keys (default recomendado).
- (b) Remove keys stale do `.env.example` agora; re-adicionar quando Settings support emergir.
- (c) Accept como forward-compatible documentation (zero acção).
**Recomendação**: (a). Quando primeiro overlay/pipeline precisar rate limit config, add field a `Settings` + documentar em `.env.example` comment.
**Effort estimate**: trivial (on-demand).
**Priority**: Low. Operational drift apenas; zero functional impact.
**Trigger**: first overlay ou pipeline que precise config externa (ex: rate limits para Eurostat Phase 2).

## P2-023: Country code ISO 3166-1 convention reconciliation (alpha-3 → alpha-2)

**Target phase**: Phase 2 (Week 2 kickoff decision)
**Descrição**: Inconsistency detectada Week 1 retrospective entre `Observation.country_code` (alpha-3, `^[A-Z]{3}$`) e `country_tiers.yaml` + CLAUDE.md §3 convention (alpha-2). FRED connector Phase 1 hardcoded `"USA"` alpha-3 per `Observation` schema, divergindo da canonical convention Phase 0.
**Root cause**: Commit Week 1 `68eb29a` (BaseConnector + Observation) introduziu pattern alpha-3 sem consulta a CLAUDE.md §3 ou ADR-0005. Phase 0 convention canonical é alpha-2 (documented em `country_tiers.yaml` header + CLAUDE.md §3).
**Evidence**:
- `country_tiers.yaml` linha 30-35: `- iso_code usa ISO 3166-1 alpha-2 uppercase (convenção CLAUDE.md §3).` → entries tipo `{ iso_code: US, country: United States }`.
- `Observation.country_code: pattern=r"^[A-Z]{3}$"` Week 1 commit `68eb29a`.
- FRED connector Week 1 commit `cbdd516`: `country_code="USA"` hardcoded.
**Decisão recomendada**: **Opção A — revert `Observation` para alpha-2**.
- Governance: CLAUDE.md §3 é source of truth Phase 0; commit Week 1 introduziu inconsistency sem ADR.
- Simplicity: 1 pattern change + 3 string updates vs mapping layer permanente.
- Re-alignment, não breaking change: zero production data ainda.
**Scope concreto Opção A**:
- `src/sonar/connectors/base.py`: `pattern=r"^[A-Z]{2}$"` + update docstring.
- `src/sonar/connectors/fred.py`: `country_code="US"` (remover "A").
- `tests/unit/test_connectors/test_fred.py`: update assertions `"USA"` → `"US"`.
- `tests/integration/test_fred_smoke.py`: update similar.
- Migration: `yield_curves_raw.country_code String(3)` → `String(2)` via Alembic migration 002 (forward-only; zero dados Phase 1).
- ADR addendum opcional: ADR-0005 +1 paragraph documentando alpha-2 convention definitivo.
**Alternative rejeitada**:
- Opção B (manter alpha-3 + mapping layer): complexity permanente para cada connector europeu Phase 2+; ADR-0005 addendum obrigatório; zero benefit functional.
**Effort estimate**: 30-45 min (pattern change + 4 file updates + migration 002 + triagem).
**Priority**: **High** — blocker para Phase 2 European connectors (Eurostat devolve alpha-2; FRED connector inconsistent com tiers file).
**Trigger**: Week 2 Day 1 AM, antes de NSS overlay dev arrancar. Rationale: NSS overlay vai usar `country_tiers.yaml` para scope decision + `Observation.country_code` em pipeline — convention deve estar aligned ANTES.

**Status**: CLOSED 2026-04-19 in 5d514b8
**Verification**: chat acceptance §9 PASS (cov flat 96.59%, 6 files)

## P2-024: `ConnectorCache` generic typing re-evaluation

**Target phase**: Phase 2+ (low priority)
**Descrição**: Phase 1 `ConnectorCache.get() → Any | None` exige callers a fazer explicit `cast("T", cached)` pattern. Single-caller scenario (FRED Week 1) aceitable — quando segundo connector surface (Eurostat/BIS Phase 2+), pattern repete → candidato para generic typing.
**Root cause**: Design decision Week 1 priorizou simplicity + zero premature generalization. Acceptable para piloto single-connector.
**Evidence Week 1**: commit `cbdd516` (FRED) introduz explicit cast pattern:
```python
cached = self.cache.get(key)
if cached is not None:
    return cast("list[Observation]", cached)
```
**Opção proposta**:
```python
class ConnectorCache[T]:
    def get(self, key: str) -> T | None: ...
    def set(self, key: str, value: T, ttl: int = ...) -> None: ...
```
**Trade-offs**:
- Pro: type safety em caller site, zero `cast()` rituals.
- Con: single cache instance tipicamente armazena single T; se connector precisa cache múltiplos types (raw obs + metadata + fitted params), generic single-T força múltiplas instâncias.
- Mitigation: sub-caches per type (ex: `self.obs_cache: ConnectorCache[list[Observation]]` + `self.meta_cache: ConnectorCache[dict]`).
**Decisão pending**: esperar até segundo connector para avaliar utility real vs complexity added. Premature generalization risk se decidir agora.
**Effort estimate**: 1-2h refactor + test updates quando decidido.
**Priority**: Low. Aesthetic/DX, zero functional impact.
**Trigger**: add este item a Week 2+ planning agenda quando Eurostat connector specification iniciar.

## P2-026: `treasury_gov` connector for US primary (NSS spec alignment)

**Status**: OPEN
**Priority**: LOW
**Descrição**: nss-curves.md §2 T1 US: primary = `connectors/treasury_gov`
(par yields daily), secondary = `connectors/fred` DGS*. Week 1 shipped
only FRED. Week 2 NSS uses FRED as primary de facto (spec non-compliant
but functionally equivalent at T+1).
**Rationale**: FRED H.15 lags 1 business day; treasury.gov XML/CSV is
same-day refresh. Upgrade path clean, zero spec change.
**Deferral trigger**: any use case requiring same-day US yields
(currently none in Phase 1).

---

## P2-027: Drop orphan Week 1 yield_curves_{raw,params,fitted,metadata} tables

**Status**: OPEN
**Priority**: LOW
**Descrição**: Migration 001 (`001_nss_schema`) created the legacy
`yield_curves_{raw,params,fitted,metadata}` family. Migration 002
(`5c63876`) introduced the spec §8 canonical family
`yield_curves_{spot,zero,forwards,real}`, which is now the only persistence
target for L2 NSS outputs. The Week 1 tables coexist but have zero
production callers as of Day 3 AM.
**Rationale**: Two table families storing semantically overlapping NSS
fit data is dead-weight schema; a future migration should drop the four
orphan tables once callers are confirmed gone.
**Deferral trigger**: Pipeline L8 design phase (`pipelines/daily-curves`).
That session will enumerate the full set of writers/readers; if no module
references `YieldCurveRaw`/`YieldCurveParams`/`YieldCurveFitted`/
`YieldCurveMetadata` SQLAlchemy classes, schedule migration 003 to drop.
**Acceptance**: `git grep -E "YieldCurve(Raw|Params|Fitted|Metadata)"`
returns only the model definitions in `src/sonar/db/models.py` plus
the migration scripts.

---

## P2-028: Yardeni Research explicit written consent documentation

**Status**: OPEN
**Priority**: HIGH (blocker — upgrade if 30 days elapse without documentation)
**Rationale**: Yardeni Research copyright explicit prohibits reproduction/derivative use without explicit written consent. Hugo undertakes direct email outreach to obtain consent for internal SONAR use (7365 Capital analytical framework). Authorization assumed granted pre-implementation per Hugo decision 2026-04-20; formal paper trail required.
**Deliverable**: `docs/governance/licensing/yardeni-consent-YYYY-MM-DD.md` with email correspondence excerpt, granted scope, any restrictions, expiration if applicable.
**Trigger for upgrade**:
- 30+ days elapse from 2026-04-20 without documentation: → HIGH blocker (rollback Yardeni connector + remove derived data before any consumer boundary).
- Yardeni denies consent or imposes restrictive terms: → scope reconsideration (FactSet + Damodaran only path, remove Yardeni from ERP spec).
**Owner**: Hugo.

---

## P2-029: Codecov upload re-introduction

**Status**: OPEN — deferred
**Priority**: LOW
**Rationale**: Codecov v4 tokenless upload was removed in commit
`bd276cd` (CI saga fix #3) because the action rejects uploads without
a repo token despite `fail_ci_if_error: false`. Coverage tracking now
lives in `docs/planning/phase1-coverage-policy.md` local gates. If
Phase 2 adds external coverage dashboards or PR-comment coverage
annotations, re-introduce the step with a repo secret token.
**Deliverable**: restore `- uses: codecov/codecov-action@v4` step in
`.github/workflows/ci.yml` test-unit job with `token:
${{ secrets.CODECOV_TOKEN }}`. Validate coverage.xml upload end-to-end
at least once.
**Trigger for activation**: external coverage reporting becomes a
team requirement (currently single-operator project — local gates
sufficient).
**Owner**: Hugo.

---

## P2-030: GitHub Actions version maintenance (setup-uv@v3, Node 24, etc.)

**Status**: OPEN
**Priority**: LOW
**Rationale**: CI saga close audit (`e16f0ed`) flagged cosmetic
deferrals:
- `astral-sh/setup-uv@v2` → `v3` (one major version behind; @v2 works
  correctly but loses the newer `enable-cache: true` ergonomics).
- Multiple actions annotated "Node.js 20 deprecated" by GitHub —
  forced migration to Node 24 default on 2026-06-02. Affected:
  `actions/checkout@v4`, `actions/setup-python@v5`,
  `astral-sh/setup-uv@v2`, `gitleaks/gitleaks-action@v2`.
**Deliverable**: single hygiene-sweep PR bumping all GHA versions +
enabling `enable-cache: true` on setup-uv. Validate no behaviour
regression across the 6 CI jobs.
**Trigger for activation**: (a) before 2026-06-02 Node 24 forced
migration, or (b) any Phase 2 workflow change that would otherwise
touch `ci.yml` anyway — bundle the bumps in.
**Owner**: Hugo.

---
