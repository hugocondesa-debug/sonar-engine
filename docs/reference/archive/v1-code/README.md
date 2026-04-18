# v1 Code Archive

Ficheiros de código do SONAR v1 preservados para inspecção conceptual.
**Não são código de produção v2**. v2 é greenfield rewrite — ver
`docs/ARCHITECTURE.md` para arquitectura canónica.

Preservados aqui por poderem conter ideias reaproveitáveis (patterns
de connector, decisões de schema) durante Phase 1 implementation.
Tratar como leitura histórica, não como blueprint.

## Ficheiros

- `connectors-base-v1.py` — v1 BaseConnector. v2 define novo em `sonar/connectors/` Phase 1.
- `db-schema-v18.sql` — v1 schema SQL raw. v2 usa SQLAlchemy 2.0 + Alembic migrations.

## Quando remover

Quando Phase 2 completa (L2-L4 todos implementados em v2), este directório
pode ser removido — lessons já absorvidas.
