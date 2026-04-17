# SONAR v1 → v2 Migration Plan

Plano para arquivar o repo atual (`hugocondesa-debug/sonar`) e arrancar fresh.

---

## Princípios

1. **Nada do v1 perdido** — tudo preservado como referência histórica
2. **Aprendizagens documentadas** — "what worked, what didn't" escrito
3. **Data migrate se útil** — historical DB pode migrar se schema compatível
4. **Code não migrate by default** — v2 é greenfield rewrite
5. **Manuais SIM migrate** — IP conceptual é o core asset

---

## Phase 0.1 — Archive v1

### Passo 1 — Final snapshot v1

```bash
# Local clone atual
cd /path/to/sonar-v1-local
git status                    # ensure clean
git pull                      # latest
git log --oneline -20 > LAST_COMMITS.txt
git branch -a > BRANCHES.txt
du -sh .                      # size check
```

### Passo 2 — Exportar learnings

Criar documento `v1_learnings.md` respondendo:

**What worked well?**
- Que connectors funcionaram bem?
- Que metodologia de classificação foi validated?
- Que decisões arquiteturais pagaram dividends?
- Que data sources provaram reliable?

**What didn't work?**
- Technical debt identificado
- Scope creep
- Abstractions que não escalaram
- Data sources que falharam

**What changed in scope?**
- v1 escopo vs v2 escopo claro
- Why the rewrite (specific reasons)
- Lessons for v2 architecture

**Migrable artifacts**:
- List of connectors to re-implement (with priority)
- List of SQL queries/views useful
- List of research notebooks with insights
- List of historical DB data worth migrating

### Passo 3 — GitHub archive

```bash
# Opção A — rename + archive (mantém URL)
# Na UI do GitHub:
#   Settings → General → Rename → "sonar-v1-archive"
#   Settings → General → Danger Zone → "Archive this repository"

# Opção B — move para nova org (se tiveres org separada)
#   Settings → General → Transfer ownership
```

**Archived repo**:
- Read-only
- URL preserved
- Can still view/clone but no pushes
- Listed in profile as "Archived"

### Passo 4 — Backup local

```bash
# Full clone backup
git clone --mirror https://github.com/hugocondesa-debug/sonar.git sonar-v1-mirror-2026-04-17.git

# Bundle file (portable, single file)
git bundle create sonar-v1-2026-04-17.bundle --all

# Store safely
mv sonar-v1-mirror-2026-04-17.git ~/backups/
mv sonar-v1-2026-04-17.bundle ~/backups/

# Encrypt if sensitive
gpg -c sonar-v1-mirror-2026-04-17.git.tar
```

### Passo 5 — Data export

Se v1 tinha database:
```bash
# SQLite export
sqlite3 sonar.db ".dump" > sonar_v1_2026-04-17.sql

# CSV per table (for future analysis)
for table in $(sqlite3 sonar.db ".tables"); do
    sqlite3 -csv -header sonar.db "SELECT * FROM $table" > exports/$table.csv
done

# Parquet format (compact, analysis-ready)
python -c "
import pandas as pd, sqlite3
conn = sqlite3.connect('sonar.db')
for table in pd.read_sql_query(\"SELECT name FROM sqlite_master WHERE type='table'\", conn)['name']:
    df = pd.read_sql_query(f'SELECT * FROM {table}', conn)
    df.to_parquet(f'exports/{table}.parquet')
"
```

---

## Phase 0.2 — Create v2 repo

### Passo 1 — Decide repo name

Options (decide in BRIEF_FOR_DEBATE):
- `sonar` (if archive renamed to `sonar-v1-archive`)
- `sonar-engine`
- `sonar-v2`

### Passo 2 — Initialize

```bash
# Create on GitHub via UI or gh CLI
gh repo create hugocondesa-debug/sonar \
  --private \
  --description "Motor analítico de ciclos macro + sub-modelos quantitativos" \
  --gitignore Python \
  --license "" \  # Decide licensing separately

# Local clone
gh repo clone hugocondesa-debug/sonar
cd sonar
```

### Passo 3 — Bootstrap from this bundle

```bash
# Copy contents from /mnt/user-data/outputs/sonar-v2-bootstrap/
# ... to repo root

# Commit structure
git add .
git commit -m "Initial bootstrap — structure, docs, templates"
git push
```

### Passo 4 — Enable GitHub features

```bash
# Enable issues, projects, wiki, discussions
gh repo edit hugocondesa-debug/sonar \
  --enable-issues \
  --enable-projects \
  --enable-wiki \
  --enable-discussions
```

### Passo 5 — Branch protection

Via UI: Settings → Branches → Branch protection rules:
- Pattern: `main`
- Require pull request before merging
- Require status checks (CI)
- Require conversation resolution
- Include administrators (yourself too)
- Restrict pushes

### Passo 6 — Secrets setup (for CI)

Via UI: Settings → Secrets and variables → Actions

Add (gradually as needed):
- `FRED_API_KEY`
- `ECB_ACCESS` (if needed)
- `TRADING_ECONOMICS_KEY` (shared)
- Future: additional API keys

### Passo 7 — Wiki initialization

Via GitHub UI: navigate to Wiki tab, create first page. Use content from `/mnt/user-data/outputs/sonar-v2-bootstrap/wiki/`.

---

## Phase 0.3 — Migrate assets

### Manuais v1

Source: `/mnt/user-data/outputs/manual_*/` no teu workspace atual
Destination: `docs/methodology/` no v2 repo

```bash
# In your local v2 clone
mkdir -p docs/methodology/{cycles,submodels}

# Credit cycle manual
cp /path/to/v1/manuals/Manual_Ciclo_Credito_COMPLETO.docx \
   docs/methodology/cycles/credit_manual.docx
# ... etc

# Or convert to markdown if preferred
pandoc Manual_Ciclo_Credito_COMPLETO.docx -o credit_manual.md
```

### Data plans

Source: `SONAR_*_Data_Sources_Implementation_Plan.md`
Destination: `docs/data_sources/`

```bash
cp /path/to/v1/plans/SONAR_Data_Sources_Implementation_Plan.md \
   docs/data_sources/credit_plan.md
# ... etc
```

### Research notebooks

Source: v1 repo `notebooks/` (if existed)
Destination: `notebooks/archived/v1/`

Move, don't delete. Insights may be useful.

### Useful code snippets

From v1, extract:
- Well-tested connectors (if any) → adapt to new base class
- SQL views (if any) → adapt to new schema
- Helper functions → curate for v2

**Don't migrate**:
- Whole `src/` wholesale
- Old schemas
- Unclear or untested code

---

## Phase 0.4 — Learnings documentation

### `docs/migration/v1_learnings.md` structure

```markdown
# SONAR v1 → v2 — Learnings

**Date**: 2026-04-MM
**Author**: Hugo

## Timeline v1

- Started: [date]
- Major milestones: ...
- Ended: 2026-04-MM (archived)

## Technical summary

### Stack
- Language: Python
- Database: ...
- Orchestration: ...
- Dashboard: ...

### Modules built
1. ...
2. ...

### Modules partial
1. ...
2. ...

## What worked

[Strengths to carry forward]

## What didn't work

[Anti-patterns to avoid]

## Why rewrite (not refactor)

[Specific reasons]

## Scope evolution

### v1 scope (original)
[Description]

### v1 scope (as built)
[Description]

### v2 scope (refined)
[From current conversation / manuals]

## Migrated assets

- [ ] Manuais (5 × 6 parts)
- [ ] Data plans (5)
- [ ] Historical database (optional)
- [ ] Specific connector code (X of Y)
- [ ] Research notebooks (N archived)

## Not migrated (and why)

- Old code in `src/engine/` — replaced by new architecture
- Old schema — rewritten from scratch
- Old dashboard — Streamlit v2 is cleaner

## First v2 priorities

Based on v1 experience:
1. ...
2. ...
3. ...
```

---

## Phase 0.5 — Parallel running (optional)

If v1 has valuable historical data being generated:

1. Keep v1 archive READ-only
2. Extract historical state to CSV/Parquet
3. Import to v2 DB once Phase 1 complete
4. Gradually move all computation to v2
5. Retire v1 fully once v2 validated

**Critério para retirement**:
- v2 reproduces v1's key outputs
- Data migrated fully
- v2 has passed 30 days of stable operation

---

## Phase 0.6 — Communication

If v1 was shared externally:
- Notify users (if any)
- Publish blog post / Substack about rewrite
- Editorial angle: "Porque reescrevi o SONAR do zero" (great content!)

---

## Checklist

```
[ ] PAT revogado (SECURITY_NOTICE)
[ ] v1 snapshot feito (commits, branches docs)
[ ] v1 learnings documented
[ ] v1 database exportada (SQL dump + CSV + Parquet)
[ ] v1 repo renamed to sonar-v1-archive
[ ] v1 repo archived (read-only)
[ ] v1 local backup em ~/backups/
[ ] v2 repo criado (private)
[ ] v2 bootstrap bundle committed
[ ] v2 wiki inicializada
[ ] v2 branch protection configurada
[ ] v2 secrets setup (FRED_API_KEY)
[ ] Manuais v1 migrados → docs/methodology/
[ ] Data plans v1 migrados → docs/data_sources/
[ ] v1_learnings.md escrito
[ ] BRIEF_FOR_DEBATE resolvido (all decisions taken)
[ ] ADRs iniciais escritos (at minimum: #1-#6)
[ ] Phase 1 kickoff agendado
```

## Timeline

Estimate: **1 semana intensiva** para completar Phase 0.1-0.6 se focado.

Break-down:
- Day 1: v1 archive + security cleanup + learnings doc
- Day 2: v2 repo creation + bootstrap + wiki setup
- Day 3: Manuais migration + data plans migration
- Day 4: BRIEF_FOR_DEBATE resolution + ADRs
- Day 5: Phase 1 planning + first commits

---

*Migration plan v0.1 — execute once BRIEF_FOR_DEBATE decisions finalized.*
