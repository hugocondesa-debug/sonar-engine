# SONAR · Data Sources

Planos operacionais de data sourcing por ciclo. Origem: 4 documentos `SONAR_*_Sources_Implementation_Plan.md` do v1, preservados na íntegra.

## Ficheiros

| Ficheiro | Âmbito | Tamanho original |
|---|---|---|
| [`economic.md`](./economic.md) | Fontes para ECS + sub-índices E1-E4 | ~50 KB |
| [`credit.md`](./credit.md) | Fontes para CCCS + sub-índices L1-L4 | ~23 KB |
| [`monetary.md`](./monetary.md) | Fontes para MSC + sub-índices M1-M4 | ~31 KB |
| [`financial.md`](./financial.md) | Fontes para FCS + sub-índices F1-F4 | ~52 KB |

## Relação com connectors

Cada data source listado mapeia (1:1 ou 1:N) a um connector em `sonar/connectors/` — o plano diz **o quê** ir buscar e **porquê**, o connector diz **como**.

## Cobertura overlays (L2)

Os overlays (NSS, ERP, CRP, rating-spread, expected-inflation) consomem dados destes planos de forma cross-cycle:
- **NSS** — raw yields de `monetary.md` + `credit.md` (sovereign)
- **ERP** — equity data, earnings, buybacks de `financial.md`
- **CRP** — CDS / sovereign spreads de `credit.md`
- **Rating-spread** — rating actions de `credit.md`
- **Expected inflation** — breakevens + surveys espalhados por `monetary.md` + `economic.md`

Não há `overlays.md` separado por design: os overlays **reutilizam** fontes já catalogadas nos 4 planos de ciclo.

## Tiers

Os planos classificam cada fonte em:
- **Tier 1 (free)** — FRED, ECB SDW, BIS, Eurostat, central bank sites, IGCP, BPStat, INE…
- **Tier 2 (enhanced)** — Trading Economics shared, FactSet, Glassnode
- **Tier 3 (professional, fund scenario)** — Bloomberg, Refinitiv, Markit CDS, LSEG

MVP (Phase 1) é **Tier 1 apenas**.

## Regra

Adicionar uma fonte nova → atualizar o plano correspondente **antes** de implementar o connector; documentar tier, custo, licensing, rate limits.
