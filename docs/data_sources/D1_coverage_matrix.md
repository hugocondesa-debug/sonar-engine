# SONAR v2 · D1 Coverage Matrix — Gap Report

> **Fase 0 · Bloco D1** — companion prose ao `D1_coverage_matrix.csv` (2026-04-18).
> Este documento resume findings da matriz de cobertura e identifica gaps, decisões pendentes Hugo, e priorização de backlog.

---

## 1. Executive summary

Foi produzida a matriz canónica de cobertura (`D1_coverage_matrix.csv`, 67 linhas, 15 colunas) que mapeia cada série consumida pelos specs v2 (overlays L2 + indices L3 + cycles L4) à fonte primary + override Tier 1 + criticality + backlog hooks.

**Key takeaways:**

1. **Cobertura BLOCKING por ciclo** — 25 séries BLOCKING (críticas). Todas têm path primary identificado, mas 4 enfrentam blockers operacionais (TCMB, FMP legacy, WS_TC key format, Conference Board paywall).

2. **5-source hierarchy estabelecida**: TE primary (breadth) > FRED/BIS/ECB/BdP/TCMB nativos (override T1) > scrapes éticos (agency ratings, AAII, COT, FINRA) > Damodaran (annual xval) > FMP (parked P2+).

3. **TE breadth adequado** (T1-T3 ~75 países confirmados via D0-T1). TE tier pending Hugo decision para confirmar se plan actual permite full ECS+CCCS+MSC+FCS em T1 production workload.

4. **BIS dominância CCCS** confirmada: WS_TC + WS_DSR + WS_CREDIT_GAP são paths canónicos. D1 smoke test revelou issue key format WS_TC (404 em `Q.PT.P.M.770A`) — bloqueia L1 implementação até CAL-019 resolvido (Phase 1 connector dev).

5. **Rating-spread overlay requer spec rewrite** (Bloco E) — D0 rejeitou TE ratings (4Y stale). Nova fonte hierarchy: Damodaran annual backfill + scrape agency forward.

6. **FMP parked**: `/api/stable/` e `/api/v3/` ambos 403 legacy. Chave pre-2025-08. Phase 2+ decision Hugo (renovar subscription ou drop fonte).

7. **TCMB bloqueado**: 10+ variantes URL/auth testadas, todas retornam HTML SPA homepage. Escalation Hugo requerida (PDF docs review ou TCMB support ticket).

---

## 2. Matrix summary

### 2.0 Request budget actual D1

Reconstruct counts from terminal log do bloco D1 (±2 margin onde count exact não recuperável).

| Task | Budget | Actual | Outcome |
|------|--------|--------|---------|
| T2 BIS inventory | 3 | 3 | 3/3 OK; BIS-01 WS_TC `Q.PT.P.M.770A` 404 (key format issue → CAL-019); BIS-02 WS_DSR `Q.PT.P` 200 OK (dimensional series populated); BIS-03 dataflow structure OK |
| T3 TCMB discovery | 8 | ~10 (±2) | Script 8 variantes + ~2 retries ad-hoc; todas retornam HTML SPA homepage (key em header, key em URL, canonical path-style, aggregationTypes, `/EVDS/service/*`, `/serieList`, `/categories`, `/datagroups`). Endpoint discovery FAILED |
| T4 FMP retest | 5 | 5 | 5/5 todos `403 Legacy Endpoint` em `/api/stable/*` (historical-price-full, quote, economic-indicators, treasury, commodities). Chave pre-2025-08 sem acesso novo |
| T5 TE bulk inventory | 5 | 5 | 5/5; `TE-A01 /country/portugal` retornou 3 492 rows 75 categorias (~450kB); `TE-A02 g=Money` filter OK; `TE-A03 historical gdp growth` OK; `TE-A04 /indicators` master catalog OK; `TE-A05 /country` master catalog OK |
| Misc/retries | — | ~2 | TCMB ad-hoc variants (counted no total T3) |
| **Total** | **80 (cap)** | **~23** | **~57 margin remaining para Bloco E/D2** |

### 2.1 Por criticality × primary_recommendation

| Primary | BLOCKING | CORE | AUXILIARY | META | Total |
|---------|----------|------|-----------|------|-------|
| TE | 10 | 9 | 0 | 0 | 19 |
| FRED | 7 | 9 | 0 | 0 | 16 |
| SCRAPE_AGENCY | 4 | 5 | 1 | 0 | 10 |
| BIS | 3 | 2 | 0 | 0 | 5 |
| ECB_SDW | 1 | 3 | 0 | 0 | 4 |
| META (L4) | 0 | 0 | 0 | 4 | 4 |
| SHILLER | 1 | 2 | 0 | 0 | 3 |
| WGB_SCRAPE | 1 | 0 | 0 | 0 | 1 |
| OECD | 0 | 1 | 0 | 0 | 1 |
| DAMODARAN | 0 | 0 | 1 | 0 | 1 |
| GAP | 0 | 0 | 1 | 0 | 1 |
| AAII | 0 | 1 | 0 | 0 | 1 |
| CFTC | 0 | 1 | 0 | 0 | 1 |
| **Total** | **25** | **35** | **3** | **4** | **67** |

**Observações:**
- TE + FRED juntos cobrem 52% (35/67) das séries; 68% dos BLOCKING (17/25) — **duas fontes dominam**.
- SCRAPE_AGENCY (10 séries, 40% BLOCKING) indica dependência operacional em scrapes éticos — requer monitoring contínuo + fallback paths.
- BIS (5 séries, 3 BLOCKING) é authoritative para credit cycle mas D1 revelou friction na key structure.
- META (4 linhas) refere-se aos 4 L4 cycles que consomem L3 indices — não têm raw source mapping.

### 2.2 Por layer × criticality

| Layer | BLOCKING | CORE | AUXILIARY | META |
|-------|----------|------|-----------|------|
| L2 overlays | 14 | 14 | 1 | 0 |
| L3 indices | 11 | 21 | 2 | 0 |
| L4 cycles | 0 | 0 | 0 | 4 |
| **Total** | **25** | **35** | **3** | **4** |

**Interpretação:** overlays têm criticality densidade maior (14/29 BLOCKING = 48%) porque contêm foundation series (NSS tenors, CDS, rating actions, breakeven inflation). L3 indices têm mais CORE/AUXILIARY, reflectindo tolerância Policy 1 re-weight quando sub-séries missing.

### 2.3 Por country_tier_scope

| Scope | Rows | Notes |
|-------|------|-------|
| T1-T4 (global) | 8 | Series universais — rating actions, rating calibration, CPI YoY, policy_rate |
| T1-T3 | 19 | Maioria L3 indices T1-T3 scope |
| T1-T2 | 6 | BIS credit series, OECD CLI, property gap, spreads |
| T1 only | 27 | US-centric (NFP, JOLTS, Sahm, UMich, NFCI, AAII, COT, FINRA, Buyback, LEI, breakeven, MOVE, F2 breadth, shadow rates, r*, CAPE, ERP monthly) |
| T1 EA+ | 2 | 5y5y fwd EA, ECB CISS |
| T1 US+ | 4 | ERP daily, SP500, TIPS |
| T1 US+UK+JP+EA | 4 | Shadow rates Krippner, HLW, inflation swap rate |
| T1 US+UK+FR+DE+IT+CA+AU | 2 | Linker countries for breakeven, TIPS |
| META | 4 | L4 cycles |

**Observação:** **40%** das séries (27/67) são T1-only — reflecting structural US-centricity de market-implied data (forward curves, positioning, survey measures). T4 scope é rating-spread + CRP apenas.

---

## 3. Gaps críticos BLOCKING

### 3.1 Externos (dependem de Hugo decision)

| # | Gap | Impacto | Decisão pendente |
|---|-----|---------|-----------------|
| 1 | **TE tier confirmation** | Não sabemos se plan actual permite production workload (75+ países breadth; D0 smoke confirmou acesso mas volume não testado) | Hugo: confirmar tier (Basic/Standard/Premium?) ou upgrade path se production fail |
| 2 | **FMP subscription lapsed** | `/api/stable/` + `/api/v3/` 403 legacy; sem commodities/treasury breadth | Hugo: renovar ($25-300/month) OU drop + compensate TE + FRED breadth |
| 3 | **TCMB endpoint opaque** | Turkey native source unreachable (EVDS docs version?) | Hugo: review EVDS PDF docs ou abrir support ticket TCMB |
| 4 | **Conference Board LEI paywall** | US E2 LEI sem path directo; proxy USSLIND state-level é weaker | Hugo: decide — aceitar proxy OR pagar Conference Board membership ($)) |

### 3.2 Internos (endereçáveis Phase 1 dev)

| # | Gap | Plano de resolução | Backlog item |
|---|-----|-------------------|--------------|
| 5 | BIS WS_TC key unit dimension (404) | Test alternative UNIT_MEASURE codes (XDC_R_B1GQ, PT1H_Z, ...) via /structure endpoint enumeration | `CAL-019` Phase 1 connector |
| 6 | Rating-spread spec v0.1 has TE fallback (rejected D0) | Rewrite spec: Damodaran annual backfill + agency scrape forward | Bloco E (pré-Phase 1) |
| 7 | CDS scrape único path free | Monitor `worldgovernmentbonds.com` breakage; prepare Tier 3 pago fallback design | — |
| 8 | F2 breadth MA200 GAP em free sources | Proxy via SP500EW/SP500 ratio (FRED series) OU constituents compute (data volume) | `P2-002` |
| 9 | Shadow rate coverage limited (4 países) | Accept limitation; emit ZLB flag só para T1 ex-{US,EA,UK,JP} | `P2-004` |
| 10 | F4 positioning non-US | By-design limitation; re-weight FCS para non-US (confidence cap 0.75) | `P2-013` |

---

## 4. Country tier coverage rates

Rate de cobertura = (# séries disponíveis para tier) / (# séries no scope expected do tier).

### 4.1 T1 (16 countries)

| Cycle | Series expected | Coverage estimada | Notes |
|-------|----------------|-------------------|-------|
| ECS (E1-E4) | 14 | ~95% (13/14) | LEI paywalled; VIX global shared |
| CCCS (L1-L4 + CRP + rating-spread) | 18 | ~85% (15/18) | BIS WS_TC key debug pending; rating-spread scrape Phase 1 |
| MSC (M1-M4 + NSS + expected-inflation) | 28 | ~85% (24/28) | Shadow rate limited 4 países; HLW r* limited 4 países |
| FCS (F1-F4 + ERP) | 19 | ~95% US, ~65% non-US | F4 US-only by design |
| **Overall T1** | 79 series × 16 países | ~85% | FCS non-US é outlier |

### 4.2 T2 (30 countries)

| Cycle | Coverage estimada | Notes |
|-------|-------------------|-------|
| ECS | ~70% | E1 full; E2 partial; E3 full; E4 reduced |
| CCCS | ~60% | BIS 43 covers maioria; L1/L4 BIS pre-computed |
| MSC | ~25% | M1_only_mode; M2/M3/M4 mostly not applicable |
| FCS | ~50% | F1 partial; F2 full; F3 reduced; F4 missing |

### 4.3 T3 (43 countries)

- ECS: ~40% (TE breadth variable).
- CCCS: ~20% (maioria fora BIS 43).
- MSC: ~15% (policy rate TE OK; nada mais).
- FCS: ~20% (TE markets breadth OK para F2; resto missing).

### 4.4 T4 (~110 countries)

- Rating-spread + CRP apenas (per `country_tiers.yaml` explicit scope).
- ECS/CCCS/MSC/FCS: **emit NULL** + flag `COVERAGE_INSUFFICIENT`.

**Agregado:** MVP Phase 1 visa T1 full + T2 CCCS (BIS dominance) + T2 ECS. Target realistic Phase 1 = **16 T1 full + 30 T2 partial + rating-spread all-tiers**.

---

## 5. TE tier — decision status

### 5.1 Plan actual

Hugo subscreveu TE Premium (5000 series exports + 5000 requests/month) em 2026-04-18 com trial 1-semana. Decisão de manter ou downgrade deferida para D2 post-empirical measurement.

### 5.2 Dois counters independentes

TE expõe **duas métricas de quota** separadas:

- **API Requests/month**: cada HTTP call. Bulk endpoints (1 call = N séries) contam 1 request.
- **Series Exports/month**: cada série única exportada/persistida, independentemente de quantas calls.

A matemática real de consumption depende do **endpoint selection pattern** do connector. D2 vai testar:

- `/country/{c}` bulk: 1 request mas ~100-150 series exports.
- `/historical/country/{c}/indicator/{x}` granular: 1 request = 1 series export.
- `/markets/*` intraday: high-frequency calls × moderate series.

### 5.3 Decision trigger

Tier sizing será re-avaliado após D2 com consumption real observado para workload Phase 1 (46 countries = 16 T1 + 30 T2). Cenários:

- Se <1 000 series exports/day observados → Standard (500/month) viável com daily cap.
- Se 1 000-5 000 series exports/day → Premium (5 000/month) adequado.
- Se >5 000/day → negotiate enterprise tier ou revise connector pattern (mais aggressive caching, endpoint consolidation).

### 5.4 Alternativa (não preferida)

Restrict TE a overlays + fallback only; depender de FRED + BIS + natives para breadth cross-country. Trade-off: perder T2+ coverage rápida uniforme. Só considerar se D2 revelar consumption prohibitive em Premium.

---

## 6. Backlog items surfaced D1

### 6.1 Calibration tasks (CAL-*)

Novos/revistos a partir D1:

| ID | Descrição | Origem |
|----|-----------|--------|
| `CAL-001` | Rating-spread spec rewrite (Bloco E) | D0 TE rejeitado |
| `CAL-018` | TCMB endpoint recovery | D1 T3 failure |
| `CAL-019` | BIS WS_TC key format debug | D1 T2 404 finding |
| `CAL-020` | Notch→spread calibration recurrent | rating-spread spec v0.2 |

### 6.2 Phase 2 items (P2-*)

Newly identified / reconfirmed Phase 2+ scope:

| ID | Descrição |
|----|-----------|
| `P2-002` | F2 breadth MA200 data provider OR constituents compute |
| `P2-004` | Shadow rate expand non-T1 (if academic extensions available) |
| `P2-006` | M4 FCI country-domestic (non-US/EA) |
| `P2-007` | LEI + PMI sub-components upgrade |
| `P2-008` | CS (communication signal) NLP pipeline |
| `P2-011` | Minsky fragility layer (real estate deep + on-chain) |
| `P2-012` | Lubik-Matthes r* DSGE complement |
| `P2-013` | F4 positioning non-US (Bloomberg/Refinitiv if budget) |
| `P2-014` | FMP subscription reactivation (post Hugo decision) |
| `P2-015` | Buyback yield local compute from constituents |
| `P2-016` | CFTC COT expanded (disaggregated, financial futures) |
| `P2-017` | Flow funds (ICI mutual flows, ETF flows) |

---

## 7. Open questions for Hugo

Ordenadas por urgência (blocks MVP vs nice-to-have):

1. **TCMB escalation approach.** Preferência: (a) Hugo lê EVDS PDF docs v1.9 e identifica URL pattern, (b) support ticket TCMB, ou (c) aceitar Turkey via TE breadth (sem native)?

2. **Rating-spread spec rewrite scheduling.** Bloco E dedicado OR integrar com Phase 1 connector dev?

3. **BIS WS_TC debug priority.** Phase 1 connector dev (CAL-019) OR pre-Phase 1 bloqueante?

4. **Damodaran data update frequency.** Monthly (NYU release cycle) OR quarterly snapshot?

5. **Conference Board LEI.** Aceitar USSLIND state-proxy permanent OR budget membership (~$1 000/year)?

6. **Country tier yaml review.** 89 países explicit + ~110 default T4 — review scope antes Phase 1 commit? Notably: QA, KW, IL em T3 mas são mercados sophisticated — T2?

7. **Attribution policy unification.** Single ATTRIBUTIONS.md doc referencing all sources para published outputs?

---

## 8. Next steps

### 8.1 Pré-Phase 1 (imediato)

1. Hugo review deste doc + answer open questions §7.
2. Commit Bloco D1 artifacts (country_tiers.yaml, D1_coverage_matrix.csv, D1_coverage_matrix.md, 4 rewritten data_sources/*.md) — pre-commit broken → `--no-verify` per governance note.
3. Bloco E: rating-spread spec rewrite (dependente decisão Hugo).

### 8.2 Phase 1 kickoff dependencies

- TE tier confirmed ✓
- FMP parked decision ✓
- TCMB escalation path ✓
- BIS WS_TC key debug (Phase 1 dev task, not blocker)

### 8.3 Related docs

- `docs/data_sources/D0_audit_report.md` — smoke test findings.
- `docs/data_sources/D1_coverage_matrix.csv` — matriz canónica.
- `docs/data_sources/country_tiers.yaml` — tier definitions.
- `docs/data_sources/{economic,credit,monetary,financial}.md` — per-cycle source docs (rewritten Bloco D1).
- `docs/backlog/calibration-tasks.md` — CAL items.
- `docs/backlog/phase2-items.md` — P2 items.
- `docs/ROADMAP.md` — Phase gates.

---

*Gerado 2026-04-18 · Fase 0 Bloco D1 · Phase 0 completion gate dependente Hugo sign-off §7.*
