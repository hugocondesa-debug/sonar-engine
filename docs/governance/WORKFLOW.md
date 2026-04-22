# Workflow

Como código e documentação entram no repo. Git, commits, CI, code quality. Complementa [`../../CLAUDE.md`](../../CLAUDE.md) §5 com detalhe processual.

## Branches

- **`main`** — única branch persistente. Solo operator, sem long-lived feature branches.
- **Feature branches** — criar apenas quando (a) Hugo pede explicitamente, OU (b) PR precisa review externo (raro). Naming: `feat/kebab-slug`, `fix/kebab-slug`, `docs/kebab-slug`, `chore/kebab-slug`. Merge via squash + delete após merge.
- **Archive branches** (raro) — preservam estado histórico sem delete (ex: `archive/v1-last-state`). Prefixo `archive/`.

Phase 0-1 opera predominantemente em `main` directo (ADR-0004 — commit gate humano é controlo suficiente para solo operator).

## Commits

**Conventional Commits em PT-PT.**

Formato: `type(scope): subject PT-PT`.

**Types canónicos**: `feat`, `fix`, `docs`, `refactor`, `chore`, `style`, `perf`, `test`, `build`, `ci`.

**Scopes comuns**: `architecture`, `specs`, `overlays`, `indices`, `cycles`, `connectors`, `db`, `pipelines`, `governance`, `adr`, `roadmap`, `glossary`, `migration`, `repo-structure`, `claude`, `pre-commit`, `cleanup`.

Regras de forma:

- Multi-paragraph via `-m` repetido (um `-m` por parágrafo). Nunca `\n` embebido em single `-m`.
- Subject no imperativo/presente em PT: "adicionar X", "corrigir Y", "rewrite Z". Evitar "adicionei X" ou "vou adicionar X".
- Bullets em corpo com `-` (não `*`).

## Git rules (não-negociáveis)

Source: [`../../CLAUDE.md`](../../CLAUDE.md) §5. Recap:

- **Nunca `git commit`** sem autorização explícita do Hugo.
- **Nunca `git push`** sem autorização explícita. Autorização para push é **separada** da autorização para commit.
- Push em checkpoints estratégicos, não por commit — agrupar cluster coerente (Phase 0 exemplo: 6 commits `ba13355..50f469c` num push).
- Force push em `main`: proibido. Mesmo com autorização explícita, pedir dupla confirmação.

## Pull Requests

Solo operator: PRs são maioritariamente auto-review. Quando criar PR:

- Mudanças materiais cross-directory (ex: refactor que toca `docs/specs/` + `sonar/` + `tests/`).
- Experimentações com risco (nova dependency major, schema breaking, renomear package).
- Quando Claude chat recomenda explicitamente PR flow para QC ampliado.

**PR body template**:

- **What**: 1-3 linhas do que muda.
- **Why**: referência a ADR / BRIEF / issue / commit relacionado.
- **Breaking changes**: sim/não + scope se sim.
- **Testing**: pytest + manual checks executados.

## Code quality stack

Source of truth: `pyproject.toml` + `.pre-commit-config.yaml`. Este documento **não duplica** regras de style — aponta para config.

- **`ruff`** — lint + format (substitui black, isort, flake8, pylint). Config em `pyproject.toml` `[tool.ruff]`.
- **`mypy --strict`** — type checking. Config em `pyproject.toml` `[tool.mypy]`.
- **`pytest`** — tests. Phase 1+ com fixtures historical PT obrigatórios.
- **`hypothesis`** — property-based para math-heavy modules (overlays, normalização).
- **`pre-commit`** — hooks em `.pre-commit-config.yaml`: `ruff`, `mypy`, `gitleaks`, `detect-secrets`, `markdownlint`, `taplo`, `shellcheck`, `nbstripout`, `conventional-pre-commit`.

Content v1 de [`../reference/archive/CODING_STANDARDS-v1.md`](../reference/archive/CODING_STANDARDS-v1.md) é histórico — config actual é canonical, vive em código não em docs.

## CI (GitHub Actions)

Dois workflows em `.github/workflows/` (bootstrap preservado):

- **`ci.yml`** — lint + format + type check + tests em PR/push `main`. Bloqueia merge se red.
- **`daily-pipeline.yml`** — cron `0 5 * * 1-5` (06:00 Lisbon, weekdays). Phase 1 activa; Phase 0 é stub.

Ambos correm com `uv` + Python 3.12 (ADR-0001).

## Breaking changes

Regra binária: quando qualquer mudança toca **frozen territory**, é breaking:

- [`../specs/conventions/`](../specs/conventions/) — qualquer edição (flags, exceptions, units, methodology-versions). PR dedicado + ADR ou actualização de spec de convention.
- **DB schema** (Alembic migration com rename/drop/type change) → bump `methodology_version` MAJOR + full rebackfill plan.
- **API pública** (Phase 3+ FastAPI) → versioning semântico (`/v1` → `/v2`), não aliasing in-place.

Sem excepções: zero quick fixes a FROZEN contracts em commits "cosméticos".

## Release tags (Phase 1+)

SemVer com prefix `sonar-v`:

- `sonar-v0.1.0` — primeira Phase 1 vertical slice complete (NSS + E1-E4 + ECS end-to-end para US + PT).
- `sonar-v0.2.0` — Phase 2 milestone (5 overlays + 16 indices + 4 cycles cobertos).
- `sonar-v1.0.0` — Phase 3 production-ready (L6 integration + L7 outputs).

Tags anotadas (`git tag -a sonar-vX.Y.Z -m "..."`) com release notes curtas. Push de tag separado (`git push origin sonar-vX.Y.Z`) após autorização.

## Paralelo CC orchestration (Week 9+ pattern)

Section added 2026-04-22 after Week 9 produziu 6 merge recoveries +
Day 0 Week 10 um 7º. Codifica o protocolo de paralelo CC que emergiu
dos Sprints S/T/V/W/X — isolated worktrees + alphabetical merge order
+ CC delegation para rebases mecânicos.

### When paralelo is appropriate

- 2+ sprints independentes com file overlap mínimo (apenas append
  zones partilhadas, sem edits ao mesmo corpo de função).
- Ambas com scope claro + HALT triggers atómicos + spec reference.
- Operator bandwidth para monitorizar 2 tmux sessions em paralelo.
- Velocity gain > merge overhead (observado Week 9: ~30% ganho,
  ~15% overhead — net +15%).

### Isolated worktrees mandatory

Cada sprint paralelo corre num worktree linked dedicado para evitar
branch-switching em `main`:

- Path convention: `/home/macro/projects/sonar-wt-<suffix>`
- Criado via `scripts/ops/sprint_setup.sh <branch>` (worktree + env
  copy + tmux session, tudo num comando).
- Branch naming: `sprint-<letter-suffix>-<theme>` (e.g.
  `sprint-y-dk-connector`). Suffix deriva o path do worktree.

### Append-zone conventions

Paralelo sprints partilham ficheiros append-only por convenção. Cada
sprint apenas adiciona ao fim; nunca edita linhas de outras sprints.
Lista canónica Week 9:

- `src/sonar/connectors/te.py` — country wrappers append end-of-file.
- `src/sonar/connectors/fred.py` — FRED OECD series constants append.
- `src/sonar/indices/monetary/builders.py` — builders via bookmark
  comments.
- `src/sonar/pipelines/daily_monetary_indices.py` —
  `MONETARY_SUPPORTED_COUNTRIES` tuple union-merge.
- `src/sonar/config/r_star_values.yaml` — per-country keys merge
  cleanly por chave distinta.
- `src/sonar/config/bc_targets.yaml` — idem.
- `docs/backlog/calibration-tasks.md` — CAL items append end.

Quando um append zone novo emerge, documentar nesta lista no retro.

### Rebase protocol

- Paralelo sprints mergem a `main` em ordem alfabética da branch
  (Week 9 confirmou empiricamente).
- A 2ª branch rebasa post-1ª-merge — **esperado, não falha**.
- Rebase típico Week 9: 5-9 ficheiros em union-merge, 15-25 min
  CC wall-clock.
- CC delegation pattern: operator cria worktree com a branch por
  rebase, arranca CC com prompt rebase-specific ("preserve every
  entry from both branches; re-sort `__all__` alphabetically;
  keep country-key order stable"). Mechanical, barato, correcto.

### Merge discipline

Regras codificadas após Week 9 lessons (retrospective §5 Lesson 1):

**DO**:

- `./scripts/ops/sprint_merge.sh <branch>` para a sequência completa.
- Verificar cada step do script antes do próximo (`set -euo pipefail`).
- Cleanup de worktree + branches **apenas** após merge confirmado em
  origin/main.
- Brief format v3 com §10 Pre-merge checklist + §11 Merge execution
  + §12 Post-merge verification.

**DON'T**:

- Executar merge + cleanup como bloco shell único (Pattern B
  orphaned W-SE em 2026-04-17).
- Apagar worktree antes de merge verificado.
- Assumir que a branch já está pushed. Sempre explicit
  `git push -u origin <branch>` (Pattern A — 2 occurrences Week 9-10).
- Saltar pre-merge workspace cleanliness check (Pattern D — Day 0
  Week 10 docs/staging/).

### Recovery patterns (Week 9 → Day 0 Week 10 inventory)

**Pattern A — Branch not pushed to origin**:

```
git branch --list <branch>           # confirm local exists
git log --oneline <branch> | head    # confirm commits
git push -u origin <branch>          # push + set tracking
./scripts/ops/sprint_merge.sh <branch>
```

**Pattern B — Cleanup-before-merge orphaned commits**:

```
git reflog | head -20                # find orphan SHA
git branch recovery <SHA>            # recreate branch
# then re-run normal merge flow
./scripts/ops/sprint_merge.sh recovery
```

**Pattern C — Rebase needed (paralelo 2ª branch)**:

```
cd <branch-worktree>
git fetch origin
git rebase origin/main
# resolve via CC delegation — union-merge append zones
git push --force-with-lease origin <branch>
./scripts/ops/sprint_merge.sh <branch>
```

**Pattern D — Untracked working tree blocks merge**:

```
git status --short                   # inventory what's there
git stash -u                         # OR
git clean -fd                        # OR
git add -A && git commit -m "..."    # whichever fits
./scripts/ops/sprint_merge.sh <branch>
```

### Metric monitoring

Tracking merge incidents por retrospective (§Lessons, raiz + recovery
time):

- Week 9 baseline: 6 incidentes / 10 sprints = 60% incident rate
  (unacceptable — motivated this section).
- Week 10+ target (improvement phase): ≤ 3 / 15 = 20%.
- Week 11+ steady state: ≤ 1 / 10 = 10%.

Meta redundante com CAL-138 retro disciplina: incidentes
documentados com root cause + recovery time permitem curvas de
aprendizagem comparáveis cross-sprint.

## Referências

- [`../../CLAUDE.md`](../../CLAUDE.md) §5 Git rules (canonical não-negociáveis).
- [`DECISIONS.md`](DECISIONS.md) — quando commit vs quando ADR.
- [`DOCUMENTATION.md`](DOCUMENTATION.md) — onde vive cada tipo de informação.
- [`../adr/README.md`](../adr/README.md) — critério ADR vs commit normal.
- [`../planning/brief-format-v3.md`](../planning/brief-format-v3.md) — template de brief com §10-12 mandatórios.
- `scripts/ops/sprint_merge.sh` — atomic merge com HALT gates (10 steps).
- `scripts/ops/sprint_setup.sh` — worktree + tmux helper para abertura de sprint.
