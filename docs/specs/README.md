# SONAR · Specs

Specs técnicas operacionais — *o input direto para gerar código*. Complementam (não substituem) a knowledge base em [`docs/reference/`](../reference/).

## Spec vs Reference

| | `docs/specs/` | `docs/reference/` |
|---|---|---|
| **Audiência** | Implementador (humano ou LLM) | Leitor que quer entender |
| **Formato** | Denso, tabelar, deterministic | Narrativo, pedagógico |
| **Tamanho alvo** | 100-250 linhas | Sem limite (origem: manuais v1) |
| **Fonte de verdade para** | Código, schema, testes | Porquê das escolhas metodológicas |
| **Muda quando** | Schema, API, algoritmo mudam | Novos papers, reframes conceptuais |
| **Exemplo** | `specs/overlays/nss-curves.md` | `reference/overlays/nss-curves.md` |

**Regra**: todo módulo em `sonar/` tem um spec. Toda spec aponta para a sua reference.

## Estrutura

```
docs/specs/
├── README.md              # este ficheiro
├── template.md            # template canónico (10+1 secções)
├── conventions/           # contratos partilhados (ler antes de qualquer spec)
│   ├── README.md
│   ├── flags.md
│   ├── exceptions.md
│   ├── units.md
│   └── methodology-versions.md
├── overlays/              # L2 · 5 calculadoras quantitativas
│   ├── nss-curves.md
│   ├── erp-daily.md
│   ├── crp.md
│   ├── rating-spread.md
│   └── expected-inflation.md
├── indices/               # L3 · 16 sub-índices (4 por ciclo)
│   ├── economic/          # E1-4
│   ├── credit/            # L1-4
│   ├── monetary/          # M1-4
│   └── financial/         # F1-4
├── cycles/                # L4 · 4 classificadores
│   ├── economic-ecs.md
│   ├── credit-cccs.md
│   ├── monetary-msc.md
│   └── financial-fcs.md
├── integration/           # L6 · matriz 4-way, cost-of-capital (Phase 2+)
└── pipelines/             # L8 · orchestration (stubs em Phase 0)
    ├── README.md
    ├── daily-curves.md
    ├── daily-overlays.md
    ├── daily-indices.md
    ├── daily-cycles.md
    ├── weekly-integration.md
    └── backfill-strategy.md
```

**Ordem de leitura recomendada**: (1) este README → (2) `conventions/` (contratos) → (3) `template.md` → (4) specs individuais.

## Template obrigatório

Toda spec segue [`template.md`](./template.md) com estas 10 secções, por esta ordem:

1. **Purpose** — 1-3 linhas. O quê + porquê.
2. **Inputs** — tipos, constraints, fonte/connector.
3. **Outputs** — tipos, storage target.
4. **Algorithm** — fórmulas + pseudocódigo numerado.
5. **Dependencies** — libraries com versão mínima.
6. **Edge cases** — bulleted. Cada um com trigger + handling.
7. **Test fixtures** — ≥3 casos input→expected, determinísticos.
8. **Storage schema** — DDL minimal (colunas, tipos, indexes, unique).
9. **Consumers** — quem lê este output (overlays/indices/cycles/integration).
10. **Reference** — link para `docs/reference/` + papers/URLs.

## Convenções

- **Linguagem**: EN predominante (input de código); labels PT aceitáveis.
- **Fórmulas**: ASCII inline (`y(τ) = β0 + β1·f1`) ou bloco com ````text`. LaTeX só se indispensável.
- **Tenores**: sempre strings do grid canónico `"1M","3M","6M","1Y","2Y","3Y","5Y","7Y","10Y","15Y","20Y","30Y"`.
- **Countries**: ISO 3166-1 alpha-2 upper (`PT`, `DE`, `US`). `EA` para euro area.
- **Currencies**: ISO 4217 (`EUR`, `USD`).
- **Basis points vs %**: sufixo no nome — `spread_bps`, `yield_pct`. Não misturar.
- **Datas**: ISO 8601. Storage em UTC; schedule em Europe/Lisbon.
- **Confidence**: float 0-1, sempre presente.
- **Methodology version**: string `"NSS_v1.2"` em todo output; incrementar na spec antes do código.

## Ciclo de vida

1. **Nova spec** → escrever em `docs/specs/<layer>/<slug>.md` seguindo `template.md`.
2. **Revisão** → PR review antes de implementar código.
3. **Implementação** → módulo em `sonar/<layer>/<slug>/`; testes usam fixtures da spec §7.
4. **Alteração algorítmica** → atualizar spec **antes** do código; bump `methodology_version`.
5. **Obsolescência** → mover para `docs/specs/archive/` com nota de replacement.
