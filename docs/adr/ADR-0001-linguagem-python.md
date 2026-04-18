# ADR-0001: Linguagem Python 3.11+

**Status**: Accepted
**Data**: 2026-04-18
**Decisores**: Hugo Condesa (solo operator)
**Consultados**: Claude chat (anthropic.com), Claude Code (VPS)

## Contexto

SONAR v2 é greenfield rewrite do v1. Linguagem primária tem de suportar ecosystem financeiro maduro (pandas, numpy, scipy, statsmodels), data connectors típicos (FRED API, ECB SDW, BIS), testing property-based (hypothesis) e orquestração razoável. V1 era Python — compatibilidade com knowledge base em [`../reference/`](../reference/) e manuais conceptuais favorece continuidade. Solo operator: talent pool / contratação não é factor decisivo.

Decisão bloqueante para Phase 1 — `pyproject.toml`, CI matrix e constraints de `uv` dependem de versão Python fixa.

## Decisão

Adoptamos **Python 3.11+** como linguagem primária para todo código em `sonar/`. Python 3.12 é versão actual instalada no VPS; CI valida 3.11 como floor. Identifiers, logs e docstrings em inglês; docs estratégicos e commits em PT-PT (ver [`../../CLAUDE.md`](../../CLAUDE.md) §3).

## Alternativas consideradas

- **Python 3.11+** ← escolhida. Ecosystem maduro, v1 compatível, docs externas ricas, type hints expressivos com `mypy --strict`.
- **Julia** — excelente para scientific computing puro; ecosystem connectors financeiros fraco; deploy complexo.
- **R** — statistical libraries sem paralelo; deploy hostile; ecosystem connectors pobre.
- **Rust** — performance excelente; ecosystem scientific imaturo para o scope SONAR; curva ingreme para solo operator.
- **Go** — pipelines rápidos; libraries scientific fracas.

## Consequências

### Positivas

- Ecosystem financeiro/scientific maduro (pandas 2.1+, numpy 1.26+, scipy, statsmodels, scikit-learn disponíveis).
- Type safety via `mypy --strict` + `ruff`; `hypothesis` para property tests.
- `uv` como package manager (10-100× mais rápido que `pip` com `pyproject.toml`).
- Compatibilidade conceptual com v1 facilita consulta de [`../reference/archive/v1-code/`](../reference/archive/v1-code/).

### Negativas / trade-offs aceites

- Performance inferior a Rust/Go em CPU-bound workloads. Aceitável: batch diário, não latency-critical; hot paths podem usar `numpy`/`numba`.
- Deployment ligeiramente mais complexo que single-binary Go. Mitigação: `uv venv` + Docker opcional Phase 3+.

### Follow-ups requeridos

- `pyproject.toml` bootstrap Phase 1 com `python_requires=">=3.11"`.
- CI lint/type/test matrix em 3.12 (VPS) + opcionalmente 3.11 (forward compat).
- Libraries Phase 1: `pandas>=2.1`, `numpy>=1.26`, `sqlalchemy>=2.0`, `alembic`, `typer`, `pytest`, `hypothesis`. `fastapi` em Phase 2+.

## Referências

- [`../BRIEF_FOR_DEBATE.md`](../BRIEF_FOR_DEBATE.md) §1 Language & stack
- [`../../CLAUDE.md`](../../CLAUDE.md) §3 Convenções de linguagem, §6 Tools VPS
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §1 Sucessor v1
