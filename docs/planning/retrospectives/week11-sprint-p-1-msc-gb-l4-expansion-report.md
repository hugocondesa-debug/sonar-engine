# Sprint P.1 — MSC GB L4 Expansion — Retrospective

**Data close**: 2026-04-24 (Week 11 Day 1 early afternoon)
**Branch**: `sprint-p-1-msc-gb-l4-expansion`
**Worktree**: `/home/macro/projects/sonar-wt-p-1-msc-gb-l4-expansion`
**Brief**: `docs/planning/week11-sprint-p-1-msc-gb-l4-expansion-brief.md`
**Parent**: Sprint P (MSC EA Path A proven) + Sprint Q.2 (GB M3 FULL via BoE BEI) + Sprint J C5 (GB M4 scaffold)
**Duração efectiva CC**: ~20 min
**Outcome**: **SHIPPED — Tier A completo; L4 third country (US + EA + GB)**

---

## §1 Scope delivered

Sprint P.1 extende `MSC_CROSS_COUNTRY_COHORT` de `("US", "EA")` para
`("US", "EA", "GB")` e ship o row `monetary_cycle_scores` GB @ 2026-04-23
com score 55.87, regime 6-band `NEUTRAL_TIGHT`, regime 3-band `NEUTRAL`,
confidence 0.36 (reweight cap 0.75 batido pela combinação 3/5 inputs + 0.65
M3 confidence), 3/5 inputs (M1+M2+M3; M4 scaffold-only absent + CS Phase 0-1
absent).

**L4 coverage**: 2/16 (US + EA) → 3/16 (US + EA + GB) = **+6pp L4 layer**.
Completes US / EA / GB major developed-economy L4 composite trio.

### Commits plan

Plan original do brief (3 commits) mantido:

| # | Scope | Descrição |
|---|---|---|
| C1 | `refactor(pipelines)` | `MSC_CROSS_COUNTRY_COHORT` extension ("US","EA") → ("US","EA","GB") + docstring + test assertion |
| C2 | `test(cycles)` | `TestMscGbCrossCountry` — composite 3/5 inputs + M3 BEI flag propagation + 3-country isolation |
| C3 | `docs(planning)` | Este retrospective |

### Files touched

| Ficheiro                                                               | Natureza        |
|------------------------------------------------------------------------|-----------------|
| `src/sonar/pipelines/daily_cycles.py`                                  | constant + docstring |
| `tests/unit/test_pipelines/test_daily_cycles.py`                       | constant assertion update |
| `tests/unit/test_cycles/test_monetary_msc.py`                          | +3 GB tests + REWEIGHT_CONFIDENCE_CAP import |
| `docs/planning/retrospectives/week11-sprint-p-1-msc-gb-l4-expansion-report.md` | NEW |

---

## §2 GB inputs matrix (pre-flight)

| Layer | GB state @ 2026-04-23         | Lineage                                        |
|-------|-------------------------------|------------------------------------------------|
| M1    | ✓ persisted (score 68.60)     | Sprint M — BoE Bank Rate via TE primary        |
| M2    | ✓ persisted (score 50.00)     | Sprint M — Taylor gap, OECD EO output gap, TE CPI |
| M3    | ✓ persisted (value 44.11)     | Sprint Q.2 — BoE BEI fitted-implied FULL        |
| M4    | ✗ scaffold (raises)            | Sprint J C5 — 2/5 custom-FCI components only    |

MSC Policy 1 reweight com `min_required = 3 of 5` → GB compoe com 3 inputs
+ emite `M4_MISSING` flag + cap confidence a `REWEIGHT_CONFIDENCE_CAP = 0.75`.

Brief §4 HALT-0 foi interpretado conservadoramente ("GB M1/M2/M4 inputs
missing"); pre-flight probe revelou que GB M4 scaffold **intencionalmente
raises** (`build_m4_gb_inputs` — Sprint J C5) para que o pipeline skip
cleanly. MSC ≥ 3 inputs ⇒ composite válido sem HALT. Worst-case §6
("ship with flag") é na prática o default path para GB até
`CAL-M4-{VOL,CREDIT-SPREAD,MORTGAGE}-…` lander.

---

## §3 Acceptance — Tier A

| # | Critério                                                       | Status |
|---|----------------------------------------------------------------|--------|
| 1 | Constant `("US","EA","GB")`                                    | ✓      |
| 2 | GB MSC row persisted 2026-04-23                                | ✓      |
| 3 | GB flags propagated (`M3_EXPINF_FROM_BEI` + `BEI_FITTED_IMPLIED`) | ✓      |
| 4 | US + EA regression unchanged                                   | ✓ (scores pinned: US=55.82, EA=44.17) |
| 5 | Tests pass                                                     | ✓ (58/58 cycles+pipelines subset; pre-existing `test_m3_builders` flake @ event-loop cleanup reproduz em baseline — unrelated) |
| 6 | Pre-commit clean double-run                                    | ✓      |

### Flags GB MSC 2026-04-23

```
BEI_FITTED_IMPLIED,COMM_SIGNAL_MISSING,EXPECTED_INFLATION_CB_TARGET,
GB_BANK_RATE_TE_PRIMARY,GB_BS_GDP_PROXY_ZERO,GB_M2_CPI_TE_LIVE,
GB_M2_FULL_COMPUTE_LIVE,GB_M2_INFLATION_FORECAST_TE_LIVE,
GB_M2_OUTPUT_GAP_OECD_EO_LIVE,INSUFFICIENT_HISTORY,M3_EXPINF_FROM_BEI,
M4_MISSING,R_STAR_PROXY,TAYLOR_VARIANT_DIVERGE
```

Lineage BEI end-to-end preservada: `BEI_FITTED_IMPLIED` + `M3_EXPINF_FROM_BEI`
herdados do row M3, propagados via `compute_msc` flag-union lexicográfico
(linha 350 em `monetary_msc.py`).

---

## §4 Backfill notes — 2026-04-21 / 2026-04-22

`daily_cycles --country GB` para 2026-04-21 e 2026-04-22 não persistiu MSC:
apenas 2 inputs (M1+M2) disponíveis — baseline M3 GB só existe para
2026-04-23 (Sprint Q.2 single-shot backfill). Comportamento esperado per
spec (§4 min_required=3). Não é regressão: estes dates nunca tiveram MSC GB
antes deste sprint. Uma remediação futura (Sprint Q.3+ ou
`CAL-MSC-GB-BACKFILL-BEI-HISTORY`) ship M3 GB para dates anteriores se a
cobertura temporal GB virar requisito.

---

## §5 Velocity + observações

- **Budget 2h, efectivo ~20 min** — pattern replication perfeito (Sprint P
  Path A já provado). Zero scope creep.
- **`compute_msc` pure function** reusable, zero touch do builder. Single
  constant edit + 3 test cases cobriu Tier A.
- **GB M4 scaffold behavior** validado como design-as-intended (Sprint J C5
  raise-on-insufficient). Brief HALT-0 era conservative; real threshold é
  Policy 1 `min_required=3`.
- **Paralelo Q.3**: zero file overlap confirmado post-hoc — P.1 tocou só
  `daily_cycles.py` + MSC tests. Q.3 toca connectors + writer + classifier
  cohort em paths disjoint.

---

## §6 Next — MSC layer roadmap

| Candidato        | Status                                                           | ETA         |
|------------------|------------------------------------------------------------------|-------------|
| MSC JP           | M1+M2+M4 FULL (Sprint M + J), M3 FULL via MoF/JGBi BEI pending | Sprint Q.3 ship → P.2 post-Q.3 |
| MSC CA           | M1+M2+M4 FULL, M3 FULL via BoC BEI pending                      | Sprint Q.3 ship → P.2 post-Q.3 |
| MSC DE/FR/IT/ES/PT | M1+M2 partial, M3 degraded, M4 FULL (Sprint J)                | Sprint P.2+ post M1-per-member audit (separate CAL) |
| MSC AU/NZ/CH/NO/SE/DK | M1+M2+M4 FULL, M3 not implemented                        | Phase 2+     |

Sprint P.1 fecha a "major developed trio" (US + EA + GB). Próximo unlock
natural é JP + CA após Sprint Q.3 (Tankan + BOS) — mesmo pattern de
replicação, budget ~20 min cada post-Q.3.

---

## §7 Lessons (para Lesson Log)

1. **Pre-flight probe > brief pre-emption.** Brief HALT-0 assumia M4
   missing = blocker; dry-run de `compute_msc` revelou Policy 1 reweight
   cobre o caso. Sempre validar compute output antes de HALT.
2. **Scaffold raises são design, não bug.** `build_m4_gb_inputs` raising
   `InsufficientDataError` é o contrato Sprint J C5 — o pipeline skip é
   intencional. Future M4 lander (CAL pending) convertem raise em FULL
   sem tocar MSC.
3. **Pattern replication budget tight.** Sprint P (EA) 45 min; Sprint P.1
   (GB) 20 min — segunda aplicação do mesmo Path A reduz overhead a apenas
   constant + tests + verify. Próximo (JP/CA via P.2) deverá ser similar.

---

*Shipped. L4 cross-country trio completo.*
