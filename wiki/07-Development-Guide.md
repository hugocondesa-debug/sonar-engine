# 07 · Development Guide

Guia prático para contribuir ao SONAR. Ver também [CODING_STANDARDS.md](../docs/CODING_STANDARDS.md) no repo.

## Setup inicial

### Pré-requisitos

- **Python 3.11+** instalado
- **git** configurado
- **uv** (recomendado) ou **pip** para gestão de dependências
- (Opcional) **GitHub CLI** (`gh`) para interação com issues/PRs
- **VS Code** ou editor de eleição

### Instalação

```bash
# 1. Clone do repo
gh repo clone hugocondesa-debug/sonar
cd sonar

# 2. Virtual environment
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate    # Windows

# 3. Install com dev dependencies
uv pip install -e ".[dev]"

# 4. Pre-commit hooks
pre-commit install

# 5. Environment variables
cp .env.example .env
# Edit .env and fill in API keys (FRED, etc.)

# 6. Initialize database
python scripts/init_db.py

# 7. Verify everything works
make check  # runs lint + typecheck + tests
```

### API keys necessárias (MVP)

No `.env`:
```bash
FRED_API_KEY=your_key_from_fredaccountapi
TRADING_ECONOMICS_KEY=optional_shared_key
# Others added as connectors implemented
```

Free registration:
- FRED: https://fred.stlouisfed.org/docs/api/api_key.html
- Trading Economics: shared across planos

## Daily workflow

### Starting new work

```bash
# Pull latest
git checkout main
git pull

# Create feature branch
git checkout -b feature/add-boe-connector

# Work, commit frequently with conventional commits
git add sonar/connectors/boe.py
git commit -m "feat(connectors): add BoE yield curves connector"

# Push and open PR
git push -u origin feature/add-boe-connector
gh pr create --fill
```

### Conventional commits

Format: `<type>(<scope>): <subject>`

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`

Examples:
- `feat(connectors): add IGCP Portuguese sovereign connector`
- `fix(submodels/erp): handle missing buyback data gracefully`
- `docs(methodology): clarify NSS weighting for short end`
- `refactor(db): split models.py into domain files`
- `test(cycles): add property tests for ECS boundaries`

### Pre-commit checks

Runs automatically:
- `ruff` — lint + format
- `mypy` — type check
- `detect-secrets` — secret scanning
- Standard checks — trailing whitespace, EOF, etc.

Manual run:
```bash
pre-commit run --all-files
```

## Testing

### Structure

```
tests/
├── conftest.py           # Shared fixtures
├── unit/                 # Fast, mocked, isolated
│   ├── connectors/
│   ├── submodels/
│   └── cycles/
├── integration/          # End-to-end with fixtures
├── property/             # Hypothesis-based
└── manual_validation/    # Human-in-loop scripts
```

### Running tests

```bash
# All tests
pytest

# Only fast unit tests
pytest tests/unit/

# Specific module
pytest tests/unit/submodels/test_erp.py

# With coverage
pytest --cov=sonar --cov-report=html

# Property tests with hypothesis
pytest tests/property/ --hypothesis-show-statistics

# Integration (slower, network)
pytest tests/integration/ --run-integration
```

### Writing tests

See CODING_STANDARDS.md section 9. Quick example:

```python
import pytest
from datetime import date
from sonar.submodels.erp import compute_erp, ERPMethod

def test_compute_erp_us_dcf_method_reasonable_range(
    fred_client_mock,
    known_us_market_data_2026_04_17,
):
    """ERP DCF for US should be within historical range."""
    result = compute_erp(
        market="US",
        date=date(2026, 4, 17),
        method=ERPMethod.DCF_DAMODARAN,
    )
    assert 2.0 <= result.canonical_erp_pct <= 7.0
    assert result.confidence >= 0.8
```

## Common tasks

### Adding a new connector

1. Copy `templates/sonar/connectors/base.py` pattern
2. Subclass `BaseConnector`
3. Implement `fetch()`, `validate()`, `store()`
4. Write unit tests (mocked HTTP)
5. Register in `sonar/connectors/__init__.py`
6. Add to daily pipeline schedule
7. Document in `docs/data_sources/`
8. Open PR

### Adding a new country

1. Edit `config/countries.yaml` — add country with tier, currency, etc.
2. Check which connectors support the country
3. If specific local connector needed, implement it
4. Add PSI-20-equivalent equity index for vol ratio
5. Test sub-models produce output for the country
6. Update wiki cobertura table

### Adding a new sub-model

Major undertaking. Steps:
1. Document methodology in `docs/methodology/submodels/`
2. Create `sonar/submodels/<name>/` directory
3. Implement component methods
4. Write orchestrator
5. Add database tables via Alembic migration
6. Write comprehensive tests
7. Wire into daily pipeline
8. Add API endpoint
9. Add to dashboard
10. Document in wiki

### Debugging data issue

1. Check logs: `logs/sonar-<date>.log`
2. Query raw data tables: `sqlite3 data/sonar.db`
3. Check connector run: `SELECT * FROM connector_runs WHERE connector='...' ORDER BY started_at DESC LIMIT 10;`
4. Cross-validate: run `scripts/validate_connectors.py --connector=<name>`
5. Compare with source directly via curl/browser
6. Check flags: `SELECT * FROM <table> WHERE flags IS NOT NULL;`

### Running daily pipeline manually

```bash
# Full pipeline
sonar-cli pipeline daily

# Specific date (for backfill)
sonar-cli pipeline daily --date=2026-04-15

# Dry run (no DB writes)
sonar-cli pipeline daily --dry-run

# Specific module only
sonar-cli pipeline daily --modules=yield_curves,erp
```

## Environments

### Development

- Local machine
- SQLite in `data/sonar.db`
- Logs to console + `logs/`
- Dashboard via `streamlit run dashboards/streamlit/Home.py`

### CI (GitHub Actions)

- Ubuntu runner
- Ephemeral SQLite
- Mocked external APIs in unit tests
- Real APIs in weekly validation job only

### Production (future)

- VPS (Hetzner, DO) ou cloud
- Systemd or Prefect for scheduling
- Encrypted cloud backup
- Monitoring dashboard

## Debugging tools

### Python

```bash
# pdb debugger
pytest -x --pdb tests/unit/

# Rich tracebacks (install rich)
python -c "from rich.traceback import install; install()"

# Profiler
python -m cProfile -o profile.stats scripts/daily_pipeline.py
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(20)"

# Memory profiler
pip install memory-profiler
python -m memory_profiler scripts/daily_pipeline.py
```

### Database

```bash
# Interactive
sqlite3 data/sonar.db

# Schema
sqlite3 data/sonar.db ".schema"

# Specific table
sqlite3 data/sonar.db ".schema yield_curves"

# Query
sqlite3 data/sonar.db "SELECT country_code, date, fit_rmse_bps FROM yield_curves WHERE date > '2026-04-01' ORDER BY country_code, date LIMIT 50;"
```

### Logs

```bash
# Tail today's log
tail -f logs/sonar-$(date +%Y-%m-%d).log

# Search for errors
grep -E "ERROR|CRITICAL" logs/sonar-*.log

# Structured queries on JSON logs (if using structlog)
jq 'select(.level == "ERROR")' logs/sonar-*.log
```

## Documentation

### Updating methodology

Methodology docs em `docs/methodology/` são **source of truth**. Ao mudar implementação:

1. Update methodology doc
2. Increment methodology version
3. Add migration for database if schema changes
4. Update tests
5. Update wiki pages if user-facing

### Updating wiki

Wiki mirror em `docs/wiki/` (if sync setup). Alternativamente, edit directly no GitHub Wiki UI e pull changes para `docs/wiki/` via cron.

### ADRs (Architecture Decision Records)

Para mudanças significativas de arquitetura:

```bash
# Template
cp docs/architecture/adr/template.md docs/architecture/adr/00NN-your-decision.md

# Edit, commit, merge via PR
```

## Release process

### Versioning

**Semantic versioning**: MAJOR.MINOR.PATCH
- MAJOR: breaking API changes
- MINOR: new features, backwards-compatible
- PATCH: bug fixes

Pre-1.0, everything is 0.x.y.

### Tagging

```bash
# After PR merged to main
git checkout main
git pull
git tag -a v0.3.0 -m "Release 0.3.0 — Phase 3 complete"
git push origin v0.3.0
```

### Changelog

Maintain `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/).

## Getting help

- Check `docs/` directory first
- Search GitHub Issues
- Open new Issue with template
- Architecture questions: open Discussion

---

*Next: [99 · Glossary](99-Glossary)*
