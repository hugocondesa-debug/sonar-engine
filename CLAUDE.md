# CLAUDE.md

Contexto operacional para Claude Code no repo SONAR v2. Ler antes de qualquer task.

## 1. Identidade do projecto

SONAR v2 é motor analítico de ciclos macroeconómicos e overlays quantitativos para 7365 Capital. Arquitectura 9-layer: L0 `connectors/` → L1 `db/` → L2 `overlays/` → L3 `indices/` → L4 `cycles/` → L5 `regimes/` → L6 `integration/` → L7 `outputs/` → L8 `pipelines/`. Phase actual: Phase 1 Week 3.5 em curso (ERP US brief + L3 indices brief merged 2026-04-20; overlays NSS/rating-spread/expected-inflation/CRP/ERP live; pipeline daily-cost-of-capital live). Operator solo: Hugo Condesa.

## 2. Fonte de verdade — ordem de consulta

Quando houver dúvida factual ou algorítmica:

1. `docs/specs/` — source of truth operacional (25 specs: 5 overlays + 16 indices + 4 cycles).
2. `docs/specs/conventions/` — contratos partilhados: `flags.md`, `exceptions.md`, `units.md`, `methodology-versions.md`.
3. `docs/ARCHITECTURE.md` — visão 9-layer, dependências cross-cycle, padrões arquiteturais.
4. `docs/reference/` — knowledge base v1 (manuais completos), contextual/histórico.

Nunca inventar. Se specs não cobrem, perguntar ao Hugo.

## 3. Convenções de linguagem

- **Código Python, naming, logs, API, identifiers**: inglês.
- **Docs estratégicos, commits (Conventional Commits), conversação**: português europeu (PT-PT).
- **Nunca misturar numa mesma unidade** — docstring EN + inline comment PT é violação. Ou tudo EN ou tudo PT por unidade coesa.

## 4. Convenções operacionais não-negociáveis

- **Compute, don't consume**: calcular overlays e indices localmente a partir de raw data. Nunca copy-paste de outputs externos (Damodaran ERP mensal, Bloomberg CRP, Bundesbank fitted curves, Shiller CAPE published). Published sources = cross-validation contínua (`XVAL_DRIFT` flag), não input primário.
- **Specs-first**: nenhum módulo em `sonar/` sem spec correspondente em `docs/specs/` aprovado. Template obrigatório em `docs/specs/template.md` (10 secções + §11 opcional).
- **Frozen contracts**: `docs/specs/conventions/` é breaking-change territory. Alteração exige PR dedicado e review explícito — nunca editar no meio de outro changeset.
- **Placeholders declarados**: todo threshold empiricamente ungrounded (weights, bands, calibration intervals) tem de ser marcado `placeholder — recalibrate after Nm of production data`. `N` entre 12m (overlays) e 60m (credit phase bands).
- **Methodology versioning**: mudança algorítmica faz bump de `methodology_version` (`{MODULE}_{VARIANT?}_v{MAJOR}.{MINOR}`) **antes** de tocar código. MAJOR = schema/formula breaking → full rebackfill.

## 5. Git — regras não-negociáveis

- **Nunca `git commit`** sem autorização explícita do Hugo. Autorização é frase tipo "commita", "podes commit", "commit X".
- **Nunca `git push`** sem autorização explícita. Autorização separada da de commit.
- **Branch padrão**: `main`. Branches feature só quando Hugo pedir explicitamente.
- **Commits em PT-PT**, Conventional Commits: `docs(scope): descrição`, `feat(scope): ...`, `fix(scope): ...`, `refactor(scope): ...`, `chore(scope): ...`.
- **Scopes comuns**: `architecture`, `specs`, `overlays`, `indices`, `cycles`, `connectors`, `db`, `pipelines`, `governance`, `adr`.
- **Multi-paragraph commit messages**: `-m` repetido (um por parágrafo), não `\n` embebido.

## 6. Tools disponíveis no VPS

- `python3` (3.12.3) — nunca `python2` assumido.
- `uv` (0.11.7) — package manager oficial. Nunca `pip install` directo; sempre `uv add` / `uv pip install` / `uv sync`.
- `pytest` — tests.
- `ruff` — lint + format (substitui black, isort, flake8).
- `mypy` — type check.
- `sqlite3` — DB MVP Phase 0-1.
- `gh` CLI — autenticado como `hugocondesa-debug` via HTTPS (não precisa PAT local).
- `tmux` — sessão persistente chamada `sonar`.
- `git` — main branch, origin HTTPS.

## 7. O que NÃO fazer

- **Não tocar user `regscraper`** (uid 1005, projecto separado, 3 tmux sessions activas). Reading ok; writing/killing não.
- **Não reinstalar Postgres** — removido em Phase 0. Postgres é Phase 2+ (ver `docs/ARCHITECTURE.md` §10).
- **Não reactivar cloudflared** — preservado em `/etc/cloudflared/` mas inactive. Reactivação é Phase 2+ condicional a autorização.
- **Não partilhar secrets** em chat nem em commits. `.env` é `.gitignore`d sempre. Nunca `cat .env` em output visível.
- **Não web_fetch a URLs arbitrários** — respeitar rate limits das APIs externas (FRED, BIS, ECB SDW, etc.). Cache + retries exponential sempre que possível.
- **Não assumir que um spec existe** — verificar com `ls docs/specs/<layer>/` antes de referenciar. Criar stub antes de referenciar em spec vizinho.
- **Não usar `pip` directo** — sempre via `uv`.
- **Não commitar ficheiros gerados** — `data/`, `.venv/`, `__pycache__/`, `*.pyc`, notebooks output (`nbstripout`), build artifacts.

## 8. SESSION_CONTEXT — pointer

Contexto conversacional detalhado (log de sessões Claude chat, decisões históricas, infra setup) é **canónico external ao repo**, mantido no projecto claude.ai como `SESSION_CONTEXT.md`. Hugo actualiza-o via paste dos retrospectives de phase-close. Claude Code **não tem acesso directo** a esse ficheiro.

**Historical snapshots in-repo**: `docs/status/week{N}-close-state.md` — per-phase snapshots (NÃO canónicos, reference only) preservam estado em transições importantes. São artefactos históricos, não session bridges live.

**Rationale**:
- External canonical evita stale in-repo files (5-week staleness observado Week 4-9).
- Hugo mantém Project Knowledge (claude.ai) como single source of truth para sessões Claude chat.
- Historical snapshots agregam valor retrospectivo sem burden canonicality.

Se precisares de contexto histórico não presente em `docs/` nem nos snapshots `docs/status/`, perguntar ao Hugo — não inventar.

## 9. Estado actual

**Phase 1 Week 7 CLOSED — M1 US milestone ~95 %** (implementation 100 %;
spec 70-75 %, deltas em `docs/milestones/m1-us-gap-analysis.md`).

Component status (Week 7 Sprint G, 2026-04-21):

- **L0 connectors**: 22+ operacionais.
- **L1 persistence**: 16 migrations; SQLite MVP (Postgres = Phase 2+).
- **L2 overlays**: 5/5 (NSS, ERP US, CRP, rating-spread v0.2, expinf).
- **L3 indices**: 16/16 compute + 14-16 real-data (E2 + M3 via
  DB-backed readers — Sprint E CAL-108).
- **L4 cycles**: 4/4 (CCCS + FCS + MSC + ECS).
- **L5 regimes**: Phase 2+ (spec pendente).
- **L6 integration**: ERP composition live.
- **L7 outputs**: Phase 2+ (sem dashboards / PDFs).
- **L8 pipelines**: 9 daily pipelines operacionais.
- **CLI operacional**: `sonar status` + `sonar health` + `sonar retention`
  shipped em Sprint G.

Cobertura: US primário + DE/PT/IT/ES/FR/NL parcial (via Eurostat + ECB
SDW + BIS). UK + JP = M2 T1 Core (Week 8+). Retrospectives em
`docs/planning/retrospectives/` (~16 files cobrindo Weeks 1-7). Ver
`docs/milestones/m1-us.md` para scorecard + quickstart.

Próximos (M2 T1 Core / Phase 2+ transição): UK + JP connectors, per-country
ERP (EA + UK + JP), agency scrape forward (CAL-115), L5 regime
classifier spec, Postgres migration. (systemd timer ops shipped Week
8 Sprint N — ver §10 Systemd ops.)

## 10. Systemd ops

Production scheduling para os 9 daily pipelines via systemd (Sprint N,
Week 8). Unit files em `deploy/systemd/`; install/uninstall scripts
em `scripts/`. Ver `docs/ops/systemd-deployment.md` para arquitectura
+ schedule + troubleshooting completo.

Quickstart (operator):

```bash
# pre-flight: tighten .env perms (currently 0664 — group-readable)
chmod 0600 /home/macro/projects/sonar-engine/.env

# install (preview first)
cd /home/macro/projects/sonar-engine
./scripts/install-timers.sh --dry-run
./scripts/install-timers.sh --execute

# verify
sudo systemctl list-timers 'sonar-*'
journalctl -u sonar-daily-curves.service --since today
```

Schedule (UTC): 05:00 bis → 06:00 curves → 06:30 overlays → 07:00 four
indices (parallel) → 08:00 cycles → 08:30 cost-of-capital. DAG via
`After=` (não cascade-fail; partial success OK).

**NÃO enabled em produção sem autorização explícita do Hugo.** Sprint N
deixa o sistema wire-ready; o flip do switch é decisão operacional
post-merge.

## 11. Regra-resumo

Quando em dúvida: **specs são canónicos, Hugo é juiz, nunca inventar, nunca commitar sem aprovação**.
