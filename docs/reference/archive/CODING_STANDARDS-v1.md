# SONAR v2 — Coding Standards

Conventions, style, patterns. Intended to be opinionated but not dogmatic — updatable via PR.

---

## 1. Language & version

- **Python 3.11+** required (use f-strings, pattern matching, typed dicts, improved generics)
- Avoid Python 3.12+ specific features until widely adopted in CI images

## 2. Formatting

**Tool**: `ruff format` (Black-compatible)

```toml
# pyproject.toml
[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "lf"
docstring-code-format = true
```

**Line length**: 100 (Python default 88 too restrictive, 120 too wide)

## 3. Linting

**Tool**: `ruff check` com ruleset explicit

```toml
[tool.ruff.lint]
select = [
    "E", "F",    # pycodestyle, pyflakes (basics)
    "W",         # pycodestyle warnings
    "I",         # isort
    "N",         # pep8-naming
    "UP",        # pyupgrade
    "B",         # flake8-bugbear
    "C4",        # flake8-comprehensions
    "DTZ",       # flake8-datetimez
    "ISC",       # implicit-str-concat
    "PIE",       # misc
    "PL",        # pylint subset
    "RET",       # flake8-return
    "SIM",       # flake8-simplify
    "ARG",       # unused arguments
    "PTH",       # use pathlib
    "RUF",       # ruff-specific
]
ignore = [
    "PLR0913",   # too many arguments (sometimes needed for connectors)
    "ISC001",    # conflicts with formatter
]
```

## 4. Type hints

**Mandatory** for all public functions e methods. Recommended for private.

```python
# ✅ Good
def compute_erp(
    market: str,
    date: date,
    method: ERPMethod = ERPMethod.DCF_DAMODARAN,
) -> ERPResult:
    ...

# ❌ Bad
def compute_erp(market, date, method=None):
    ...
```

Type checker: **mypy strict mode**

```toml
[tool.mypy]
strict = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_return_any = true
```

### Common patterns

```python
from typing import Literal, Protocol

# Use Literal for fixed values
Tenor = Literal["3M", "6M", "1Y", "2Y", "5Y", "7Y", "10Y", "20Y", "30Y"]

# Use Protocol for duck typing
class Connector(Protocol):
    name: str
    def fetch(self, **kwargs: Any) -> FetchResult: ...

# Use NewType for domain primitives
from typing import NewType
Bps = NewType("Bps", int)
Percentage = NewType("Percentage", float)
```

## 5. Naming conventions

### General
- `snake_case` for files, functions, variables, methods
- `PascalCase` for classes, type aliases, enums
- `UPPER_SNAKE_CASE` for constants
- `_leading_underscore` for private (by convention; use sparingly)
- `__dunder__` only for Python standard magic methods

### Domain-specific

```python
# Countries: ISO 3166-1 alpha-2 uppercase
country_code: str = "PT"   # ✅
country_code: str = "pt"   # ❌
country_code: str = "Portugal"  # ❌

# Currencies: ISO 4217
currency: str = "EUR"      # ✅

# Dates: prefer date over datetime when time-agnostic
from datetime import date
observation_date: date = date(2026, 4, 17)

# Basis points as integers
spread_bps: int = 35       # ✅ (35 bps)
spread_pct: float = 0.35   # ✅ (0.35% = 35 bps)
# Never mix confusingly

# Tenors as strings matching grid
tenor: Tenor = "10Y"

# Sub-model outputs consistently named
erp_dcf_pct: float      # Always pct for ERP
crp_bps: float          # Always bps for CRP spreads
yield_pct: float        # Always pct for yields
```

## 6. Docstrings

**Style**: Google style (readable, concise)

```python
def compute_erp(
    market: str,
    date: date,
    method: ERPMethod = ERPMethod.DCF_DAMODARAN,
) -> ERPResult:
    """Compute Equity Risk Premium for a market on a given date.

    Uses the method specified. Default is Damodaran's implied ERP via
    5-year DCF with terminal growth = risk-free rate.

    Args:
        market: Market identifier ('US', 'EA', 'UK', 'JP').
        date: Valuation date (typically today or most recent close).
        method: ERP computation method. See ERPMethod enum.

    Returns:
        ERPResult with primary ERP value, cross-check values, confidence,
        and inputs used.

    Raises:
        DataUnavailableError: If required inputs (S&P 500 close, yield
            curve, buyback data) are not available for the given date.
        InvalidInputError: If market is not recognized.

    Example:
        >>> result = compute_erp("US", date(2026, 4, 17))
        >>> result.canonical_erp_pct
        4.82
    """
    ...
```

**Required for**:
- All public functions and methods
- All classes
- Complex private functions (anything >15 lines or non-obvious)

**Not required for**:
- Simple private helpers
- Dataclass definitions (types self-documenting)
- Test functions (test name is doc)

## 7. Error handling

### Custom exception hierarchy

```python
# sonar/exceptions.py
class SONARError(Exception):
    """Base SONAR exception."""

class DataError(SONARError):
    """Data-related errors."""

class DataUnavailableError(DataError):
    """Required data is not available."""

class StaleDataError(DataError):
    """Data is available but too old."""

class InvalidInputError(SONARError):
    """Invalid input to computation."""

class ConfigurationError(SONARError):
    """Config/environment error."""

class MethodologyError(SONARError):
    """Methodology constraint violated (e.g., NSS fit failed)."""

class ExternalServiceError(SONARError):
    """External API or service failure."""
```

### Rules

- **Catch specific** exceptions, never bare `except:`
- **Raise with context** — use `raise X from e` to preserve traceback
- **Log before re-raising** at boundaries (connector → module, module → pipeline)
- **Fail loud in dev**, fail gracefully in production via config flag
- Never silently swallow errors

### Pattern

```python
try:
    result = external_api.fetch(...)
except RequestException as e:
    logger.exception("Failed to fetch from %s: %s", api_name, e)
    raise ExternalServiceError(
        f"Connector {api_name} failed to fetch data for {date}"
    ) from e
```

## 8. Logging

**Library**: `structlog` (or stdlib `logging` with JSON formatter)

### Conventions

```python
import structlog
logger = structlog.get_logger(__name__)

# ✅ Good — structured, contextual
logger.info(
    "computed_erp",
    market="US",
    date=date(2026, 4, 17),
    erp_pct=4.82,
    method="dcf_damodaran",
    confidence=0.88,
)

# ❌ Bad — unstructured string
logger.info(f"Computed ERP for US: 4.82% via DCF")
```

### Log levels

| Level | When |
|---|---|
| DEBUG | Verbose operation detail, dev only |
| INFO | Pipeline milestones, significant operations |
| WARNING | Recoverable issues, stale data, wide CI |
| ERROR | Module failures, continuing despite issue |
| CRITICAL | Pipeline-wide failures, operator attention |

### Never log

- API keys or secrets
- Full HTTP responses with sensitive headers
- User PII (if ever applicable)

## 9. Testing

### Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── connectors/
│   ├── submodels/
│   ├── cycles/
│   └── integration/
├── integration/
│   ├── pipelines/
│   └── fixtures/           # Recorded responses via vcrpy
└── property/
    └── ...
```

### Naming

```python
# Test function: test_<what_is_tested>_<under_conditions>
def test_nss_fitter_produces_smooth_curve_for_us_treasury():
    ...

def test_nss_fitter_raises_on_insufficient_data():
    ...
```

### Fixtures

```python
# conftest.py
import pytest

@pytest.fixture
def known_us_yields_2026_04_17() -> dict[str, float]:
    """Known US Treasury yields for 2026-04-17 (reference date)."""
    return {
        "3M": 4.25, "6M": 4.15, "1Y": 4.05,
        "2Y": 3.95, "5Y": 4.10, "10Y": 4.25, "30Y": 4.45,
    }

@pytest.fixture
def sonar_db(tmp_path) -> Session:
    """Ephemeral SQLite for tests."""
    ...
```

### Property tests

```python
from hypothesis import given, strategies as st

@given(
    yields=st.lists(st.floats(min_value=0.0, max_value=0.15), min_size=8, max_size=11)
)
def test_nss_fit_always_produces_reasonable_params(yields):
    """NSS fit should produce params within reasonable ranges for any valid yields."""
    tenors = np.array([0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30, 50][:len(yields)])
    fitter = NSSFitter()
    params = fitter.fit(tenors, np.array(yields))
    assert 0 <= params[0] <= 0.20  # β_0 reasonable level
    # ... more assertions
```

### Coverage

- **Target**: 80%+ overall, 90%+ em core computation
- Measured with `coverage.py` in CI
- Failing coverage check blocks merge

## 10. Git workflow

### Branching

- `main` — always deployable, protected
- `develop` — integration branch (optional, decide early)
- `feature/<short-name>` — new features
- `fix/<short-name>` — bug fixes
- `docs/<short-name>` — documentation only
- `refactor/<short-name>` — restructure without behavior change
- `chore/<short-name>` — tooling, CI, deps

### Commit messages

**Format**: Conventional Commits

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `build`

**Examples**:

```
feat(connectors): add IGCP Portuguese sovereign connector

Scrapes daily OT yields from IGCP website.
Implements BaseConnector interface.
Tests with recorded fixtures.

Part of Phase 2.
```

```
fix(submodels/erp): handle missing buyback data gracefully

When S&P DJI hasn't published latest quarter, use previous
quarter's yield and flag with reduced confidence.

Closes #42.
```

### PRs

- One logical change per PR
- Include tests
- Update docs if behavior changes
- CI must pass
- Self-review before requesting review (at minimum for solo work)
- Squash-merge to keep history clean (or rebase — decide early)

## 11. Documentation

### Code comments

- Explain **why**, not **what** (code shows what)
- Mention trade-offs, gotchas, references to papers
- Link to methodology docs for complex math

```python
# ✅ Good — explains why
# Use Newton-Raphson with initial guess from analyst consensus
# Bisection is slower but more robust; uncomment if convergence issues:
# r = brentq(npv, 0.02, 0.20)
r = newton(npv, x0=0.08, fprime=npv_derivative)

# ❌ Bad — states what
# Compute r using Newton-Raphson
r = newton(npv, x0=0.08)
```

### README per module

Each `sonar/<module>/` should have a brief `README.md` explaining:
- Purpose
- Key files and their roles
- External dependencies (APIs, data sources)
- Link to methodology doc

## 12. Dependencies

### Philosophy

- **Pin dependencies** in lockfile
- **Minimize transitive deps** — audit new additions
- **Prefer stdlib** when reasonable
- **Prefer fewer-maintainer deps with more stars** for critical path
- **Security**: `pip-audit` in CI, Dependabot enabled

### Adding a dependency

Ask:
1. Do we really need it? Can stdlib or existing dep cover?
2. Is it actively maintained (commits last 6 months)?
3. Does it have a license compatible with ours?
4. How big is its dep tree?
5. Is there a simpler alternative?

## 13. Performance

### Guidelines

- **Profile before optimizing** — use `cProfile`, `py-spy`
- **Premature optimization** is real risk — don't over-engineer
- **Async** for I/O-bound (connectors, HTTP) via `httpx.AsyncClient`
- **numpy/pandas** for numeric ops (not pure Python loops)
- **Cache** expensive computations via `functools.lru_cache` or disk cache
- **Batch** database operations (bulk_insert vs individual)

### Anti-patterns

```python
# ❌ Bad — per-row DB commit
for row in data:
    db.session.add(row)
    db.session.commit()

# ✅ Good — bulk insert
db.session.bulk_insert_mappings(Model, data)
db.session.commit()
```

## 14. Security

### Credentials

- **Never commit** secrets, API keys, tokens
- `.env` always gitignored
- Use pre-commit hooks: `detect-secrets` or `gitleaks`
- GitHub secret scanning enabled
- If accidentally committed: rotate immediately, purge git history if necessary

### External data

- **Validate all inputs** — don't trust scraped HTML
- **Sanitize** before DB insert (SQLAlchemy parametrized queries help)
- **Rate limit** requests to respect source's ToS
- **User-Agent header** identifying SONAR (respect robots.txt)

### Dependencies

- `pip-audit` in CI
- Dependabot PRs reviewed weekly
- Major version upgrades gated

## 15. AI-assisted development

### When using Claude Code, Copilot, etc.

- **Review every suggestion** — don't blind-accept
- **Understand before accepting** — if you can't explain it, don't commit it
- **Test AI-generated code** — treat as if from a junior dev
- **Don't commit secrets** into AI prompts (they go into context)
- **Credit sources** where appropriate (especially for complex algorithms)

### Explicit markers

If significant AI assistance used:

```python
# Note: Implementation derived from Claude-assisted design,
# reviewed and tested by Hugo 2026-04-XX.
def complex_algorithm(...):
    ...
```

Optional, but useful for future maintenance.

---

## Tooling summary

```toml
# pyproject.toml relevant sections

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
# See section 3 above

[tool.ruff.format]
# See section 2 above

[tool.mypy]
strict = true
python_version = "3.11"

[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra --strict-markers --cov=sonar --cov-report=term-missing"
testpaths = ["tests"]
markers = [
    "slow: slow tests (require network or heavy computation)",
    "integration: integration tests requiring external services",
]

[tool.coverage.run]
source = ["sonar"]
omit = ["*/tests/*", "*/migrations/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, types-requests]

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: debug-statements
```

---

*Coding standards v0.1 — updatable via PR with review.*
