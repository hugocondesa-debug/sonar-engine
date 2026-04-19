# Phase 1 Week 1 — Execution Plan

**Version**: 1.0
**Created**: 2026-04-19
**Author**: Hugo Condesa (via Claude chat session)
**Status**: Approved for execution
**Executor**: Claude Code (VPS `sonar-prod`, session `sonar`)
**Supersedes**: N/A (Phase 1 kickoff)
**Superseded by**: Will be superseded by Week 1 retrospective + Week 2 plan (fim sexta)

---

## 0. Purpose & how to use this document

Este ficheiro é o **brief táctico** para a primeira semana de Phase 1 do SONAR engine. Destina-se a:

1. **Claude Code** — seguir Day-by-Day schedule (§6) com exit criteria binários.
2. **Hugo** — decisão go/no-go diária; Week 1 gate review sexta.
3. **Phase 1 retrospective** — artefacto reproduzível para comparar plano vs execução.

**Scope**: infraestrutura baseline + L0 FRED connector piloto + schema NSS persisted. **Não**: NSS overlay implementation (Week 2-3), TE observation mode (Week 2+), outros overlays.

---

## 1. Context & gate posture

Phase 0 fechou 2026-04-19 00:35 com 19 commits. Gate satisfeito:

- ✓ Specs-first (25 specs + 4 cycles + 6 pipelines + 5 ADRs + 8 conventions)
- ✓ Data discovery closure (D0-D4)
- ✓ Country tiers formalized (ADR-0005)
- ✓ Architectural patterns frozen (4 patterns)
- ✓ TE Premium active; secrets canonical
- ✓ Methodology versioning (3 bumps Phase 0)

Phase 1 kickoff (chat session 2026-04-19) aprovou:

- **CAL-023 (LEI US)**: opção (c) internal LEI de componentes FRED nativos. Scoped para Phase 1 mid-late (semanas 3-4). **Não bloqueia Week 1.**
- **Week 1 scope**: Track A (infra + FRED piloto) conforme schedule §6.

---

## 2. Assumptions (sobrescrever se erradas antes de arrancar Claude Code)

| # | Assumption | Se errada, acção |
|---|------------|------------------|
| A1 | `src/sonar/` **não existe** no repo; Claude Code cria greenfield | Review estrutura existente antes de Day 1 |
| A2 | `pyproject.toml` existe baseline (uv.lock committed `8e2f430`) mas deps minimais | Merge cuidadoso do bloco §4 em vez de overwrite |
| A3 | SQLite dev path: `./data/sonar-dev.db` dentro do repo, **gitignored** | Ajustar `DATABASE_URL` em `.env` |
| A4 | `FRED_API_KEY` já está em `/home/macro/projects/sonar-engine/.env` | **Day 1 blocker**: Hugo regista em https://fred.stlouisfed.org/docs/api/api_key.html (1 min) |
| A5 | SQLAlchemy 2.0 moderno (async-capable, `Mapped[...]` syntax) | Downgrade para 1.x requer re-spec models.py |
| A6 | Claude Code tem autorização continuada `--dangerously-skip-permissions` para Week 1 | Hugo reautoriza se sessão tmux resetar |

---

## 3. Architecture — `src/` layout

```
sonar-engine/
├── src/
│   └── sonar/
│       ├── __init__.py
│       ├── config.py             # Pydantic settings (.env loader)
│       ├── connectors/           # L0
│       │   ├── __init__.py
│       │   ├── base.py           # BaseConnector ABC + Observation model
│       │   ├── fred.py           # FRED implementation
│       │   └── cache.py          # diskcache wrapper
│       ├── db/                   # L1
│       │   ├── __init__.py
│       │   ├── models.py         # SQLAlchemy declarative
│       │   └── session.py        # engine + sessionmaker
│       ├── overlays/             # L2 (Week 2-3)
│       │   └── __init__.py
│       └── utils/
│           ├── __init__.py
│           └── logging.py        # structlog config
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_yield_curves.py
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_connectors/
│   │   └── test_db/
│   ├── integration/
│   │   ├── __init__.py
│   │   └── test_fred_smoke.py
│   └── fixtures/
│       └── fred_responses/       # pytest-httpx cassettes
├── data/                         # gitignored (SQLite dev)
├── .pre-commit-config.yaml       # repaired Day 3
├── .env.example                  # committed (zero secrets)
├── pyproject.toml
├── alembic.ini
├── uv.lock
└── CLAUDE.md                     # existing pointer
```

**Design rationale**: `src/` layout (não flat) permite `uv run` + import testing sem install editável dodgy. Separação 1:1 com camadas L0-L2 facilita Phase 2 expansion sem refactor estrutural.

---

## 4. `pyproject.toml` — Phase 1 dependency block

```toml
[project]
name = "sonar-engine"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    # HTTP + resilience
    "httpx>=0.27",
    "tenacity>=9.0",

    # Data
    "numpy>=2.0",
    "pandas>=2.2",
    "scipy>=1.14",                 # NSS fit (scipy.optimize)

    # Validation + settings
    "pydantic>=2.9",
    "pydantic-settings>=2.5",

    # Persistence
    "sqlalchemy>=2.0",
    "alembic>=1.13",

    # Observability + CLI
    "structlog>=24.0",
    "typer>=0.12",

    # Cache
    "diskcache>=5.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-asyncio>=0.24",
    "pytest-httpx>=0.32",
    "ruff>=0.7",
    "mypy>=1.13",
    "pre-commit>=4.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "B", "UP", "SIM", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_ignores = true
disallow_any_explicit = false     # httpx json parsing pragmatism

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "--strict-markers --cov=sonar --cov-report=term-missing"

[tool.coverage.run]
source = ["src/sonar"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

---

## 5. Alembic migration 001 — schema NSS

Quatro sibling tables per `docs/specs/overlays/nss-curves.md`.

### Design decisions

| Decisão | Racional |
|---------|----------|
| `yield_bps` como `Integer` (basis points) | Determinismo exacto; evita float equality issues em testes; 1 bp precision suficiente para macro |
| `methodology_version` em params/fitted/metadata | Permite re-runs com v0.2 vs v0.1 coexistindo; suporta A/B comparison; alinha com ADR-0002 |
| `UniqueConstraint(country, date, tenor, source)` em `raw` | Múltiplas sources por mesma obs (FRED + BIS) permitidas; reconciliation layer em L1 decide canonical |
| `flags_json` em `params` | Liga a `conventions/flags.md` sem colunas ad-hoc; schema forward-compatible |
| `run_id` (UUID4) em `metadata` | Provenance trace cross-tables para debugging |
| `Numeric(10, 6)` para betas/tau | NSS params magnitude ~[-0.1, 0.1], precision suficiente sem float drift |

### Migration code

```python
# alembic/versions/001_initial_yield_curves.py
"""initial yield curves schema

Revision ID: 001_nss_schema
Revises:
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa

revision = "001_nss_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "yield_curves_raw",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("country_code", sa.String(3), nullable=False),
        sa.Column("observation_date", sa.Date, nullable=False),
        sa.Column("tenor_years", sa.Numeric(6, 3), nullable=False),
        sa.Column("yield_bps", sa.Integer, nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_series_id", sa.String(100)),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "country_code", "observation_date", "tenor_years", "source",
            name="uq_raw_obs",
        ),
    )
    op.create_index(
        "ix_raw_country_date", "yield_curves_raw",
        ["country_code", "observation_date"],
    )

    op.create_table(
        "yield_curves_params",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("country_code", sa.String(3), nullable=False),
        sa.Column("observation_date", sa.Date, nullable=False),
        sa.Column("beta0", sa.Numeric(10, 6), nullable=False),
        sa.Column("beta1", sa.Numeric(10, 6), nullable=False),
        sa.Column("beta2", sa.Numeric(10, 6), nullable=False),
        sa.Column("beta3", sa.Numeric(10, 6), nullable=False),
        sa.Column("tau1", sa.Numeric(10, 6), nullable=False),
        sa.Column("tau2", sa.Numeric(10, 6), nullable=False),
        sa.Column("rmse_bps", sa.Numeric(8, 3)),
        sa.Column("n_observations", sa.Integer, nullable=False),
        sa.Column("methodology_version", sa.String(10), nullable=False),
        sa.Column("flags_json", sa.JSON),
        sa.Column(
            "fitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "country_code", "observation_date", "methodology_version",
            name="uq_params",
        ),
    )

    op.create_table(
        "yield_curves_fitted",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("country_code", sa.String(3), nullable=False),
        sa.Column("observation_date", sa.Date, nullable=False),
        sa.Column("tenor_years", sa.Numeric(6, 3), nullable=False),
        sa.Column("fitted_yield_bps", sa.Integer, nullable=False),
        sa.Column("methodology_version", sa.String(10), nullable=False),
        sa.UniqueConstraint(
            "country_code", "observation_date", "tenor_years", "methodology_version",
            name="uq_fitted",
        ),
    )
    op.create_index(
        "ix_fitted_country_date", "yield_curves_fitted",
        ["country_code", "observation_date"],
    )

    op.create_table(
        "yield_curves_metadata",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("country_code", sa.String(3), nullable=False),
        sa.Column("observation_date", sa.Date, nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("methodology_version", sa.String(10), nullable=False),
        sa.Column("optimizer_status", sa.String(20)),
        sa.Column("optimizer_iterations", sa.Integer),
        sa.Column("input_sources_json", sa.JSON),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_metadata_run", "yield_curves_metadata", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_metadata_run", "yield_curves_metadata")
    op.drop_table("yield_curves_metadata")
    op.drop_index("ix_fitted_country_date", "yield_curves_fitted")
    op.drop_table("yield_curves_fitted")
    op.drop_table("yield_curves_params")
    op.drop_index("ix_raw_country_date", "yield_curves_raw")
    op.drop_table("yield_curves_raw")
```

### SQLAlchemy models (`src/sonar/db/models.py`)

```python
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class YieldCurveRaw(Base):
    __tablename__ = "yield_curves_raw"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(3))
    observation_date: Mapped[date] = mapped_column(Date)
    tenor_years: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    yield_bps: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(50))
    source_series_id: Mapped[str | None] = mapped_column(String(100))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class YieldCurveParams(Base):
    __tablename__ = "yield_curves_params"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(3))
    observation_date: Mapped[date] = mapped_column(Date)
    beta0: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    beta1: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    beta2: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    beta3: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    tau1: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    tau2: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    rmse_bps: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    n_observations: Mapped[int] = mapped_column(Integer)
    methodology_version: Mapped[str] = mapped_column(String(10))
    flags_json: Mapped[dict | None] = mapped_column(JSON)
    fitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class YieldCurveFitted(Base):
    __tablename__ = "yield_curves_fitted"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(3))
    observation_date: Mapped[date] = mapped_column(Date)
    tenor_years: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    fitted_yield_bps: Mapped[int] = mapped_column(Integer)
    methodology_version: Mapped[str] = mapped_column(String(10))


class YieldCurveMetadata(Base):
    __tablename__ = "yield_curves_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(3))
    observation_date: Mapped[date] = mapped_column(Date)
    run_id: Mapped[str] = mapped_column(String(36))
    methodology_version: Mapped[str] = mapped_column(String(10))
    optimizer_status: Mapped[str | None] = mapped_column(String(20))
    optimizer_iterations: Mapped[int | None] = mapped_column(Integer)
    input_sources_json: Mapped[dict | None] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

---

## 6. FRED connector — skeleton

Piloto L0. Scope Week 1 é **read-only, single-series, async, cached, retried**. Bulk concurrency e cross-country fan-out ficam para Phase 2.

### `src/sonar/connectors/base.py`

```python
from abc import ABC, abstractmethod
from datetime import date

from pydantic import BaseModel, Field


class Observation(BaseModel):
    country_code: str = Field(pattern=r"^[A-Z]{3}$")
    observation_date: date
    tenor_years: float = Field(gt=0, le=50)
    yield_bps: int
    source: str
    source_series_id: str


class BaseConnector(ABC):
    @abstractmethod
    async def fetch_series(
        self, series_id: str, start: date, end: date
    ) -> list[Observation]: ...

    @abstractmethod
    async def aclose(self) -> None: ...
```

### `src/sonar/connectors/fred.py`

```python
from datetime import date, datetime
from typing import Any

import diskcache
import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.base import BaseConnector, Observation

log = structlog.get_logger()

# US Treasury constant maturity series → tenor_years
# Source: docs/data_sources/D2_empirical_validation.md (validated)
FRED_US_TENORS: dict[str, float] = {
    "DGS1MO": 1 / 12,
    "DGS3MO": 0.25,
    "DGS6MO": 0.5,
    "DGS1": 1.0,
    "DGS2": 2.0,
    "DGS3": 3.0,
    "DGS5": 5.0,
    "DGS7": 7.0,
    "DGS10": 10.0,
    "DGS20": 20.0,
    "DGS30": 30.0,
}


class FredConnector(BaseConnector):
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(
        self, api_key: str, cache_dir: str, timeout: float = 30.0
    ) -> None:
        self.api_key = api_key
        self.cache = diskcache.Cache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(
        self, series_id: str, start: date, end: date
    ) -> dict[str, Any]:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
        }
        r = await self.client.get(self.BASE_URL, params=params)
        r.raise_for_status()
        return r.json()

    async def fetch_series(
        self, series_id: str, start: date, end: date
    ) -> list[Observation]:
        cache_key = f"fred:{series_id}:{start.isoformat()}:{end.isoformat()}"
        if cache_key in self.cache:
            log.debug("fred.cache_hit", series=series_id)
            return self.cache[cache_key]

        tenor = FRED_US_TENORS.get(series_id)
        if tenor is None:
            raise ValueError(f"Unknown FRED series mapping: {series_id}")

        raw = await self._fetch_raw(series_id, start, end)
        observations: list[Observation] = []
        for obs in raw.get("observations", []):
            if obs["value"] == ".":  # FRED sentinel for missing
                continue
            observations.append(
                Observation(
                    country_code="USA",
                    observation_date=datetime.fromisoformat(obs["date"]).date(),
                    tenor_years=tenor,
                    yield_bps=int(round(float(obs["value"]) * 100)),  # pct → bps
                    source="FRED",
                    source_series_id=series_id,
                )
            )

        self.cache.set(cache_key, observations, expire=86400)  # 24h
        log.info("fred.fetched", series=series_id, n=len(observations))
        return observations

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
```

### Design notes

- **FRED sentinel `.`** filtrado (NaN representation; documented FRED behaviour).
- **pct → bps** com `int(round(...))` para determinismo; evita float equality drift em tests.
- **Cache 24h** — match daily update cadence FRED.
- **Rate limit gestão global** deferred para Phase 2 (candidate backlog item P2-016). Week 1 usa single-series fetches; FRED allows 120/min per key, folga ampla.
- **Tenor mapping hard-coded** com source D2 — evita mapping drift silencioso.

---

## 7. Day-by-Day schedule — exit criteria binários

| Day | Task | Exit criterion |
|-----|------|----------------|
| **1 AM** | `uv sync` com deps Phase 1; merge `pyproject.toml` §4 | `uv sync` succeeds; `uv run python -c "import httpx, scipy, alembic, sqlalchemy, diskcache, structlog"` OK |
| **1 PM** | Ruff + mypy + pytest configs; `tests/conftest.py` stub; 1 dummy test | `uv run pytest` green; `uv run ruff check src tests` clean; `uv run mypy src` clean |
| **2 AM** | `src/sonar/config.py` (Pydantic settings + `.env` loader); `.env.example` committed | `FRED_API_KEY` loads OK; `.env.example` commitado sem secrets reais |
| **2 PM** | `alembic init`; `env.py` aponta para SQLite dev path `./data/sonar-dev.db` | `alembic current` OK (empty state) |
| **3 AM** | Migration 001 (§5); `src/sonar/db/models.py` + `session.py` | `alembic upgrade head` cria 4 tables; `alembic downgrade base` reverte clean; SQLite file gitignored |
| **3 PM** | Pre-commit repair (P2-015): `detect-secrets` baseline + `gitleaks` hook; `.pre-commit-config.yaml` funcional | Hook dispara em secret test injectado; `pre-commit run --all-files` green em baseline |
| **4 AM** | `connectors/base.py` + `connectors/cache.py` | `mypy` clean |
| **4 PM** | `connectors/fred.py` (§6) | `mypy` clean; module imports sem erro |
| **5 AM** | Unit tests FRED com `pytest-httpx` mock; cobertura ≥ 80% em `fred.py` | `pytest tests/unit/test_connectors/ --cov=sonar.connectors` ≥ 80% |
| **5 PM** | Integration smoke `test_fred_smoke.py`: fetch `DGS10` last 30d; validate D2 match | 3/3 match vs D2 baseline (DGS10, DGS2, DGS1MO em datas seleccionadas) |

**Week 1 gate (sexta)**: 10/10 exit criteria verdes. Se falha Day 5 integration → reopen, não avança para Week 2 NSS.

---

## 8. Commits plan — Conventional Commits

Expectável 8-10 commits `main` directo (solo operator, per `CLAUDE.md §5`; PRs entram em Phase 2 com CI).

| # | Tipo | Scope | Descrição |
|---|------|-------|-----------|
| 1 | `chore` | deps | `pyproject.toml` Phase 1 deps + tooling configs |
| 2 | `chore` | ci | Ruff + mypy + pytest baseline configs |
| 3 | `feat` | config | `src/sonar/config.py` Pydantic settings + `.env.example` |
| 4 | `feat` | db | Alembic init + `env.py` SQLite dev setup |
| 5 | `feat` | db | Migration 001 yield_curves schema (4 sibling tables) |
| 6 | `feat` | db | SQLAlchemy 2.0 models + session factory |
| 7 | `chore` | security | Pre-commit framework repair (closes P2-015) |
| 8 | `feat` | connectors | BaseConnector ABC + Observation pydantic model |
| 9 | `feat` | connectors | FRED L0 connector + disk cache |
| 10 | `test` | connectors | FRED unit tests (pytest-httpx) + integration smoke + D2 validation |

---

## 9. Risks & mitigations

| Risk | Probabilidade | Impacto | Mitigação |
|------|---------------|---------|-----------|
| FRED `DGS20` gap 1986-1993 + 2010-2020 | Alta | Baixo Week 1 | Documented em D2; smoke test usa last 30d. NSS overlay Week 2-3 terá flag handling |
| `diskcache` + async httpx race conditions | Média | Médio | Cache synchronous (thread-safe mas não async-native); wrap em `asyncio.to_thread` se surgir em prod hot path; não é issue Week 1 |
| Pre-commit `detect-secrets` baseline false positives em specs | Média | Baixo | `--exclude-files 'docs/'` no primeiro pass; audit selectivo |
| SQLite Numeric precision drift cross-platform | Baixa | Baixo | `yield_bps` é Integer (determinístico); Numeric só em fit results, tolerância ±0.001 |
| Hetzner SSH stability long Claude Code sessions | Baixa | Alto | `tmux` session `sonar` persistente; autosave de checkpoints em `docs/planning/session-log.md` |
| FRED API key rate limit (120/min) excedido | Muito baixa | Médio | Week 1 só single-series fetches (~11 series max); folga 10x |
| `uv sync` conflict entre deps novas e uv.lock Phase 0 | Média | Baixo | Se conflito: `rm uv.lock && uv lock` (Phase 0 lock era bootstrap; regenerar OK) |

---

## 10. Week 1 → Week 2 handoff

Week 2 arranca segunda com:

1. **NSS overlay vertical slice US** — implementar `overlays/nss-curves.md` end-to-end
2. Uso do FRED connector Week 1 como input
3. `scipy.optimize` NSS fit (Nelson-Siegel-Svensson)
4. Persist nas 4 sibling tables schema Week 1
5. Test fixtures vindos directos do spec

**Pre-condition Week 2**: Week 1 gate 10/10 green. Se falha parcial, Week 2 delay 1-2 dias.

---

## 11. Referências cruzadas

- `SESSION_CONTEXT.md` — overview estratégico Phase 0 → Phase 1
- `docs/specs/overlays/nss-curves.md` — spec fonte schema §5
- `docs/data_sources/D2_empirical_validation.md` — validação tenor mapping §6
- `docs/specs/conventions/flags.md` — `flags_json` schema
- `docs/adr/ADR-0002-methodology-versioning.md` — `methodology_version` column
- `docs/adr/ADR-0005-country-tiers.md` — T1 = US (Week 1 scope)
- `backlog/calibration-tasks.md` — CAL-023 (LEI US) deferred; CAL-024 (US policy rate swap) in-flight

---

*Documento vivo. Atualizar status no fim de cada day (Day N complete + deviations observed). Retrospective integrada em Week 1 gate review sexta.*
