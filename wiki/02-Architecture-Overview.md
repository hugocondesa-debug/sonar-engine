# 02 · Architecture Overview

Short summary of the SONAR architecture. Full technical architecture in [docs/ARCHITECTURE.md](https://github.com/hugocondesa-debug/sonar/blob/main/docs/ARCHITECTURE.md).

## Five layers

```
LAYER 0 — Raw data sources
   (FRED, ECB SDW, BIS, IGCP, Shiller, rating agencies, etc.)
            ↓
LAYER 1 — Sub-models (computed daily)
   (Yield curves, ERP, CRP, rating-to-spread, expected inflation)
            ↓
LAYER 2 — Cycle classification
   (ECS, CCCS, MSC, FCS + overlays)
            ↓
LAYER 3 — Integration
   (Matriz 4-way, diagnostics, cost-of-capital)
            ↓
LAYER 4 — Outputs
   (API, CLI, editorial, alerts, dashboard)
```

## Key design principles

1. **Compute, don't consume** — sub-models são calculados locally, não consumidos
2. **Layered isolation** — cada layer tem interfaces claras
3. **Idempotency** — pipelines reruneáveis sem side effects
4. **Honest uncertainty** — confidence intervals explícitos everywhere
5. **Feedback loops intencionais** — circular dependencies entre layers calibradas historicamente

## Technology stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Database | SQLite (MVP) / PostgreSQL (scale) |
| ORM | SQLAlchemy 2.0 + Alembic |
| HTTP | httpx |
| Testing | pytest + hypothesis |
| Linting | ruff |
| Type check | mypy strict |
| Orchestration | GitHub Actions + APScheduler |
| API | FastAPI (future) |
| Dashboard | Streamlit (MVP) |
| Package | uv |

## Data flow (canonical day)

**06:00** morning data refresh (connectors)
**09:00** sub-model computation
**10:00** cycle classification
**10:30** integration layer
**11:00** outputs (briefing, alerts)

## Database

Schema v18 com tables por layer:
- Raw data (audit trail)
- Indicators per cycle
- Sub-model outputs
- Cycle scores
- Integrated state
- Meta (connectors, runs, calibrations)

## Extensibility

- **Add country**: update `config/countries.yaml` + specific connector if needed
- **Add sub-model**: create `sonar/submodels/<name>/` following pattern
- **Add data source**: subclass `BaseConnector`, register, test

## Testing

- Unit tests em `tests/unit/` (mocked)
- Integration tests em `tests/integration/` (recorded fixtures)
- Property tests em `tests/property/` (hypothesis-based)
- Target: 80%+ coverage core, 75%+ overall

---

*Full architecture: [docs/ARCHITECTURE.md](https://github.com/hugocondesa-debug/sonar/blob/main/docs/ARCHITECTURE.md)*

*Next: [03 · Four Cycles](03-Four-Cycles)*
