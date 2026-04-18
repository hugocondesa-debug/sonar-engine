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

## Referências

- [`../../CLAUDE.md`](../../CLAUDE.md) §5 Git rules (canonical não-negociáveis).
- [`DECISIONS.md`](DECISIONS.md) — quando commit vs quando ADR.
- [`DOCUMENTATION.md`](DOCUMENTATION.md) — onde vive cada tipo de informação.
- [`../adr/README.md`](../adr/README.md) — critério ADR vs commit normal.
