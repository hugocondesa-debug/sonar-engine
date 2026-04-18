# Calibration tasks — backlog

Placeholders declarados em specs P3-P5 a recalibrar empiricamente quando production data atingir horizonte mínimo. Agrupados por horizonte (acção ordenada) + spec owner (rastreabilidade).

**Convenção**: cada placeholder em specs marcado `placeholder — recalibrate after Nm`. Este inventário consolida todos os placeholders catalogados com ID estável `CAL-NNN`.

## Sumário

**20 itens catalogados** (inventory real via grep). SESSION_CONTEXT estimava ~40; reality revelou ~20 após exclusão de fixtures, non-requirements e duplicados.

| Horizonte | Count | Categorias |
|---|---|---|
| Recurring 3m | 1 | rating-spread anchor values |
| 12m | 1 | overlay threshold (CRP CDS liquidity) |
| 18m | 3 | overlays (CRP vol_ratio, CRP rating-CDS, rating-spread modifier weights) |
| 24m | 10 | index bands (E1-E4), cycle weights (MSC), general README (economic + monetary) |
| 60m per country | 5 | credit phase bands (L1-L4 + credit README) |

## Activação

Phase 4 "Calibração Empírica & Scale" é gate primário ([`../ROADMAP.md`](../ROADMAP.md) §Phase 4). Items individuais podem activar antes se spec owner (Hugo) tiver fundamento empírico suficiente (evidence-based, documentado em ADR ou spec bump).

## Recurring 3m — rating-spread anchor values

Única categoria recurring (não one-shot). Quarterly recalibration a partir de Moody's Annual Default Study + ICE BofA observed spreads.

| ID | Spec | Placeholder | Valor actual | Critério recalibração |
|---|---|---|---|---|
| CAL-020 | `overlays/rating-spread.md:143` | Anchor values notch→bps | notch 21→10 / 18→35 / 15→90 / 12→245 / 9→600 / 6→1325 / 3→3250 / 0→N/A (April 2026 snapshot) | Every 3m vs published spreads |

## Horizonte 12m — overlay thresholds (rápidos)

Items com ≥ 250 observações diárias em 12m, recalibráveis empiricamente cedo.

| ID | Spec | Placeholder | Valor actual | Critério recalibração |
|---|---|---|---|---|
| CAL-001 | `overlays/crp.md:39` | CDS liquidity threshold (bid-ask cutoff) | 15 bps | Distribuição empírica de bid-ask em 12m production |

## Horizonte 18m — overlay parameters

| ID | Spec | Placeholder | Valor actual | Critério recalibração |
|---|---|---|---|---|
| CAL-002 | `overlays/crp.md:41` | `vol_ratio_bounds` (σ_equity/σ_bond clamp) | (1.2, 2.5) | Distribuição empírica vol_ratio em 18m |
| CAL-003 | `overlays/crp.md:43` | `rating_cds_divergence_threshold_pct` para flag `RATING_CDS_DIVERGE` | 50% (\|cds − rating_implied\| / cds > 0.50) | Observação de false positives em 18m |
| CAL-004 | `overlays/rating-spread.md:103` | Modifier weights outlook/watch | ±0.25 / ±0.50 notches | Ex-post rating action transitions em 18m |

## Horizonte 24m — index bands + cycle weights

O horizonte dominante. 10 items: 4 index band thresholds (E1-E4), 2 cycle weights/internals (MSC), 1 index M1 classification, 1 Taylor rule ρ, 2 general READMEs (economic, monetary).

| ID | Spec | Placeholder | Valor actual | Critério recalibração |
|---|---|---|---|---|
| CAL-005 | `indices/economic/E1-activity.md:95` | Band "Recession (mild)" threshold | score 20-30 | NBER/CEPR historical alignment |
| CAL-006 | `indices/economic/E2-leading.md:103` | Band "Recession warning" threshold | score < 30 | NBER/CEPR alignment |
| CAL-007 | `indices/economic/E3-labor.md:116` | Band "Deteriorating rapidly" threshold | score < 30 | NBER/CEPR alignment + Sahm trigger events |
| CAL-008 | `indices/economic/E4-sentiment.md:125` | Band "Widespread pessimism" threshold | score < 30 | NBER/CEPR alignment |
| CAL-009 | `indices/economic/README.md:58` | Pesos ECS + thresholds gerais (umbrella) | Cap 15.6 weights (0.35/0.25/0.25/0.15) | Walk-forward backtest vs NBER/CEPR; hit-ratio ≥ 87% Pagan-Sossounov |
| CAL-010 | `indices/monetary/M1-effective-rates.md:134` | Classification bands (fixture `us_2026_04_17` sample) | "Neutral-Tight" threshold (score≈62) | Regime change events (2004-06/2013/2014/2019/2022) |
| CAL-011 | `indices/monetary/M2-taylor-gaps.md:80` | Taylor rule inertia `ρ` | 0.85 | Backtest per BC via Phase 9 harness |
| CAL-012 | `indices/monetary/README.md:77` | Pesos MSC + thresholds gerais (umbrella) | Cap 15.6 weights | Walk-forward backtest vs monetary regime changes (Fed hike/taper/easing/cut/hiking) |
| CAL-013 | `cycles/monetary-msc.md:34` | CS internal weights (dot plot / dissent / NLP) | 40/25/35 | Backtest quando CS connectors speced (P2-014) |
| CAL-014 | `cycles/monetary-msc.md:44` | MSC composite weights | `{m1:0.30, m2:0.15, m3:0.25, m4:0.20, cs:0.10}` | Walk-forward vs regime changes; Cap 15.6 hit-ratio |

## Horizonte 60m per country — credit phase bands

Dataset BIS curto (trimestral, ~30-40 anos per country mas regime changes infrequentes). 5 items.

| ID | Spec | Placeholder | Valor actual | Critério recalibração |
|---|---|---|---|---|
| CAL-015 | `indices/credit/L1-credit-to-gdp-stock.md:89` | `structural_band` per country level | `<50% sub-financialized; 50-100% intermediate; 100-150% advanced typical; 150-200% highly financialized; >200% outlier` | Distribuição per country em 5Y |
| CAL-016 | `indices/credit/L2-credit-to-gdp-gap.md:95` | Phase band thresholds | (per spec) | BIS crisis events + Moody's default study alignment |
| CAL-017 | `indices/credit/L3-credit-impulse.md:91` | State classification thresholds | (per spec) | Credit cycle transitions historical |
| CAL-018 | `indices/credit/L4-dsr.md:118` | Band classification thresholds | (per spec) | DSR peak events (2009 PT, 2012 ES, etc.) |
| CAL-019 | `indices/credit/README.md:139` | Phase bands gerais Cap 15.8 (umbrella) | (per spec) | BIS crisis chronicle + country-specific regime dating |

## Não-categorizado por horizonte

Zero items. Todos os 20 têm horizonte explícito no spec.

## Workflow de recalibração

1. Item reaches activation window (production data ≥ horizonte).
2. Spec owner (Hugo) corre backtest com harness ([`../ROADMAP.md`](../ROADMAP.md) §Phase 2 scope) contra benchmark específico do item.
3. Decisão: manter valor OR recalibrar.
4. Se recalibra:
   - Bump `methodology_version` MINOR (weight/threshold change).
   - Selective rebackfill per country.
   - Actualiza spec + regista ADR se trade-off relevante.
   - Este ficheiro: status `done`, link commit + valor final.
5. Se mantém: status `done (validated)`, rationale + backtest link.

## Exclusões documentadas (não são CAL items)

Items encontrados em grep mas **não catalogáveis** como calibration tasks one-shot:

- `overlays/rating-spread.md:143` — anchor values são recurring 3m, catalogados separadamente como **CAL-020**.
- `indices/monetary/M2-taylor-gaps.md:213` — non-requirement sobre ρ auto-recalibration, duplica CAL-011.
- `indices/monetary/M4-fci.md:210` — scope expansion (Goldman FCI replication), não recalibração.
- `cycles/credit-cccs.md:209` — nome de test fixture `xx_qs_placeholder`, não placeholder de threshold.

## Referências

- [`../ROADMAP.md`](../ROADMAP.md) §Phase 4 Calibração Empírica
- [`../specs/conventions/methodology-versions.md`](../specs/conventions/methodology-versions.md) — bump rules
- [`../specs/conventions/normalization.md`](../specs/conventions/normalization.md) — lookbacks per cycle
- [`../specs/conventions/composite-aggregation.md`](../specs/conventions/composite-aggregation.md) — Policy 1 + cycle weights
