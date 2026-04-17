# SONAR v2 — Brief for Debate

Decisões chave que devem ser tomadas **antes** de Phase 1 começar. Cada secção apresenta as opções sem pre-commitment.

Recomendação: passar por cada secção, tomar decisão, criar ADR (Architecture Decision Record) em `docs/architecture/adr/`.

---

## 1. Language & stack

### Python vs alternatives

**Proposta**: Python 3.11+

**Pros**:
- Ecosystem financeiro maduro (pandas, numpy, scipy, statsmodels)
- ML-ready para v4 futuro
- Large talent pool se delegar
- Melhor documentação de APIs (FRED, ECB, etc.) em Python
- Existing v1 provavelmente Python

**Cons**:
- Performance (compared to Rust, Go)
- Deployment slightly more complex than Node/Go
- Type safety less strict than TypeScript

**Alternatives to consider**:
- **Julia**: scientific computing, great for modeling. Small ecosystem para connectors.
- **R**: unmatched statistical libraries. Deployment harder.
- **Rust**: fast, safe. Scientific ecosystem immature.
- **Go**: fast pipelines. Weak scientific libs.

**Decision**: _______ (proposto: Python 3.11+)

---

## 2. Database choice

### SQLite vs PostgreSQL vs DuckDB

**Proposta**: **SQLite** para MVP, migrate to Postgres if needed.

**Critérios**:
- MVP é single-user research → SQLite sufficient
- No concurrent writes → SQLite fine
- DB size provavelmente <10GB → SQLite fine
- Analytical queries → DuckDB melhor, mas SQLite acceptable
- Backup/restore → SQLite trivial (file copy)

| Option | Pros | Cons | When to use |
|---|---|---|---|
| SQLite | Simple, file-based, zero setup | Concurrent writes limited | MVP, research |
| DuckDB | OLAP-optimized, fast analytics | Less mature tooling | Analytical workloads |
| PostgreSQL | Production-grade, concurrent | Overhead, setup | Production, multi-user |

**Decision**: _______ (proposto: SQLite, port to Postgres se/quando necessário)

---

## 3. Orchestration

### Cron vs APScheduler vs Prefect vs Airflow

**Opções** para daily pipeline:

| Tool | Complexity | Features | When to use |
|---|---|---|---|
| **Cron (system)** | Minimal | None (just schedule) | Simple, VPS-hosted |
| **APScheduler** (Python) | Low | In-process, Python-native | Small pipelines |
| **GitHub Actions (scheduled)** | Low-Med | Free cloud, no server | GitHub-heavy workflow |
| **Prefect** | Medium | Flow DAG, observability | Medium complexity |
| **Airflow** | High | Industry standard | Large, enterprise |

**Proposta**:
- **Dev/early prod**: GitHub Actions scheduled (free, no server needed)
- **Mid term**: cron on VPS
- **Later**: Prefect if pipelines become complex (many interdependencies)

**Decision**: _______ (proposto: GitHub Actions initial, VPS + cron quando precisar de controle)

---

## 4. Dashboard technology

### Streamlit vs Dash vs React+FastAPI

**Proposta**: Streamlit for MVP, React para produção se fund launch.

| Option | Time to MVP | Customization | Production-ready |
|---|---|---|---|
| **Streamlit** | Days | Medium | Good for internal tools |
| **Plotly Dash** | Weeks | High | Good |
| **React + FastAPI** | Months | Unlimited | Excellent |
| **Observable notebooks** | Days | Low-Med | Good for demos |

**Proposta concreta**:
- **v1 dashboard**: Streamlit (Phase 7)
- **v2 dashboard**: React only if fund launches OR if Streamlit limitations hit

**Decision**: _______ (proposto: Streamlit MVP)

---

## 5. Licensing

### Proprietary vs Open-core vs Open-source

**Opções**:

1. **Fully proprietary / all rights reserved**
   - Maximum control
   - IP protected
   - Can commercialize later
   - No community contributions
   - Harder to recruit

2. **Source-available (e.g., BUSL, Elastic License)**
   - Code visible but restricted commercial use
   - Middle ground

3. **Open-core (MIT/Apache + proprietary premium)**
   - Core open, value-add services paid
   - Hard to define the line
   - Community effect possible

4. **Fully open-source (MIT, Apache 2.0, GPL)**
   - Community contributions
   - IP not defensible directly
   - Monetize via services

**Context**:
- SONAR's moat is methodology + calibration + daily operation, not code itself
- Manuals are clearly proprietary (Hugo's IP)
- Code could be open with differentiated service offering
- Fund strategy would be proprietary regardless

**Decision**: _______ (proposto: proprietary inicial, considerar open-core quando maduro)

---

## 6. Dependency management

### pip vs Poetry vs uv

| Tool | Speed | Ecosystem | Maturity |
|---|---|---|---|
| **pip + requirements.txt** | Medium | Universal | Mature |
| **Poetry** | Medium | Python | Mature |
| **uv** (Astral) | **Very fast** | Growing | Newer but stable |
| **pdm** | Fast | Python | Mature |

**Proposta**: **uv** — massively faster, compatible com pyproject.toml, emerging as Python standard.

**Decision**: _______ (proposto: uv)

---

## 7. Code quality tools

### Ruff vs Black + isort + flake8 + pylint

**Proposta**: **Ruff** (single tool replacing many)

| Tool | Role | Recommendation |
|---|---|---|
| **Ruff** | Linter + formatter | ✅ Use |
| **mypy** | Type checker | ✅ Use |
| **pytest** | Testing | ✅ Use |
| **hypothesis** | Property testing | ✅ Use |
| **pre-commit** | Git hook runner | ✅ Use |
| **detect-secrets or gitleaks** | Secret scanning | ✅ Use |
| Black | Formatter | ⛔ Replaced by ruff format |
| isort | Import sort | ⛔ Replaced by ruff |
| flake8 | Linter | ⛔ Replaced by ruff |
| pylint | Linter | ⛔ Ruff sufficient |

**Decision**: _______ (proposto: ruff + mypy + pytest + hypothesis + pre-commit)

---

## 8. Secrets & config management

### Proposta

**Local dev**:
- `.env` file (gitignored)
- Loaded via `python-dotenv`
- `pydantic-settings` for typed config

**CI/CD**:
- GitHub Actions secrets
- Encrypted variables

**Production (eventual)**:
- Cloud provider secrets manager OR
- HashiCorp Vault OR
- Just encrypted file with key management

**Pre-commit hook**:
- `detect-secrets` or `gitleaks` to prevent credential commits

**Decision**: _______ (proposto: .env + pydantic-settings + GH Actions secrets)

---

## 9. Testing strategy

### Unit vs Integration vs Property-based ratios

**Proposta**:
- **Unit tests**: 80%+ coverage em core computation (sub-models, cycles)
- **Integration tests**: principal pipelines end-to-end com fixtures
- **Property tests**: hypothesis-based em math-heavy modules
- **Manual validation**: scripts em `tests/manual_validation/` para human-in-loop

**Coverage targets**:
- Core modules: 80%+
- Connectors: 70%+ (network-dependent)
- Outputs: 60%+
- Overall: 75%+

**Decision**: _______ (proposto: as above)

---

## 10. Deployment scenario (current stage)

### Laptop vs VPS vs Cloud-native

**Proposta inicial**: **Developer laptop + scheduled cloud CI**

- Development local (laptop)
- Daily pipeline scheduled on GitHub Actions (free tier)
- Outputs cached em local DB + mirror em cloud storage
- Dashboard local via Streamlit

**Migration path**:
1. Add VPS ($20-40/mo) quando precisar 24/7 uptime
2. Add cloud storage (S3/B2) para backups
3. Move to container orchestration se fund-scale

**Decision**: _______ (proposto: laptop + GH Actions MVP)

---

## 11. Repository visibility

### Private vs Public

**Proposta**: **Private** até decisão de licensing final.

**Considerations**:
- Private = control, mas limita community feedback
- Public = potential for contributions, but reveals approach
- Sensitive credentials NEVER in repo regardless

**Decision**: _______ (proposto: private para Phase 0-3, reavaliar)

---

## 12. Monorepo vs polyrepo

### All-in-one vs separate repos

**Opções**:

1. **Monorepo** (single `sonar/` repo)
   - Everything together: code + docs + dashboard + scripts
   - Pros: easier refactoring, single source of truth
   - Cons: one repo grows large, mixing concerns

2. **Polyrepo** (multiple repos)
   - `sonar-core`, `sonar-dashboard`, `sonar-docs`, etc.
   - Pros: clear boundaries, independent versioning
   - Cons: coordination overhead, duplication

**Proposta**: **Monorepo** com sub-folders (dashboard can extract later if needed)

**Decision**: _______ (proposto: monorepo)

---

## 13. Naming & branding

### "SONAR" clarification

**Current**: "SONAR" acronym backronym: **S**ystematic **O**bservatory of **N**ational **A**ctivity and **R**isk

**Alternatives considered**:
- Keep current name (strong, established)
- Rename if conflict with SonarQube (developer tool) causes confusion

**Naming decision**: _______ (proposto: keep SONAR, add tagline)

### Repo name

**Options**:
- `sonar` (current)
- `sonar-core`
- `sonar-engine`
- `7365capital-sonar`

**Decision**: _______ (proposto: `sonar` or `sonar-engine` to distinguish from SonarQube)

---

## 14. Documentation strategy

### Where does methodology live?

**Options**:

1. **Code repo `docs/`** (proposed)
   - Single source of truth
   - Versioned with code
   - Can export to Wiki

2. **GitHub Wiki primary**
   - Separate from code
   - Harder to version
   - Easier for non-devs

3. **External documentation site** (ReadTheDocs, etc.)
   - Professional look
   - Additional build step

**Proposta**: Code repo `docs/` as source, export to GitHub Wiki automated

**Decision**: _______ (proposto: repo docs + automated wiki sync)

---

## 15. AI assistance workflow

### How to leverage AI tools safely

**Options**:

1. **Claude Code** (CLI): for developer tasks, runs locally
2. **Claude chat** (web/app): for discussions, architecture
3. **GitHub Copilot**: inline code completion
4. **Custom integration**: MCP servers, LLM for content generation

**Recommended workflow**:
- Architecture discussions here (chat) → ADRs in repo
- Implementation via Claude Code (with guardrails)
- Copilot optional for velocity
- Documentation generation assisted but human-reviewed
- **Never commit AI output without review**

**Decision**: _______ (proposto: Claude Code + Claude chat + manual review)

---

## 16. Editorial content workflow

### How SONAR feeds "A Equação"

**Options**:

1. **Manual**: SONAR generates data, Hugo writes column manually
2. **Semi-automated**: SONAR generates daily briefing, angles, chart starters; Hugo edits and finalizes
3. **Fully automated**: SONAR drafts column; Hugo approves/edits

**Proposta**: Semi-automated (option 2)

- SONAR's role: data, context, chart generation, angle suggestion
- Hugo's role: voice, editorial judgment, final framing
- Never auto-publish

**Decision**: _______ (proposto: semi-automated)

---

## Summary decision matrix

Fill in as decisions are made:

| # | Decision | Choice | ADR # | Date |
|---|---|---|---|---|
| 1 | Language | | | |
| 2 | Database | | | |
| 3 | Orchestration | | | |
| 4 | Dashboard | | | |
| 5 | Licensing | | | |
| 6 | Dep manager | | | |
| 7 | Code quality | | | |
| 8 | Secrets | | | |
| 9 | Testing | | | |
| 10 | Deployment | | | |
| 11 | Visibility | | | |
| 12 | Repo structure | | | |
| 13 | Naming | | | |
| 14 | Docs | | | |
| 15 | AI workflow | | | |
| 16 | Editorial | | | |

---

## Next step

Após decisões principais tomadas (minimum items 1, 2, 6, 7, 10, 11):
1. Criar ADRs correspondentes
2. Finalize `pyproject.toml` template
3. Start Phase 0 proper
