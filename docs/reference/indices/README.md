# L3 · Indices

Sub-índices por ciclo. Cada índice é uma **síntese ponderada normalizada** (z-score ou percentil) de uma sub-dimensão do ciclo. Consome raw data (L0), DB (L1) e overlays (L2) e produz output numérico contínuo consumível por L4 (cycles).

## Mapa

| Ciclo | Índices | Fonte |
|---|---|---|
| **Económico** (ECS) | E1 Activity · E2 Leading · E3 Labor · E4 Sentiment | `economic/` |
| **Crédito** (CCCS) | L1 Credit-to-GDP stock · L2 Credit-to-GDP gap · L3 Credit impulse · L4 DSR | `credit/` |
| **Monetário** (MSC) | M1 Effective rates · M2 Taylor gaps · M3 Market expectations · M4 FCI | `monetary/` |
| **Financeiro** (FCS) | F1 Valuations · F2 Momentum · F3 Risk appetite · F4 Positioning | `financial/` |

## Pesos canónicos (referência dos manuais v1)

| Ciclo | E1/L1/M1/F1 | 2 | 3 | 4 |
|---|---|---|---|---|
| ECS | 35% | 25% | 25% | 15% |
| CCCS | ver `credit/` | | | |
| MSC | ver `monetary/` | | | |
| FCS | 30% | 25% | 25% | 20% |

Pesos podem ser recalibrados por país / regime — ver ficheiros individuais.

## Estrutura de cada ficheiro

Cada `indices/<cycle>/<NX>-slug.md` preserva o capítulo original do manual (Parte III). Typical sections:
- Rationale e origem na literatura
- Componentes observáveis (indicadores raw)
- Transformações (Z-score, HP filter, MA, etc.)
- Agregação e ponderação
- Thresholds e calibração
- Cross-country / Portugal specifics
- Caveats e failure modes

## Regra

Sub-índices são **insumos** dos cycle scores (L4), **não** classificadores. Output é contínuo, não discreto.
