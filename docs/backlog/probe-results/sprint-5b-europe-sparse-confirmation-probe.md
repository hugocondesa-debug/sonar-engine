# Sprint 5B — Europa Nórdica/Alpina TE Path 1 confirmation probe (2026-04-26)

**Sprint**: 5B — CH + SE + NO + DK (Europa Nórdica/Alpina subset of T1
sparse cohort), paralelo com 5A APAC (AU + NZ; CC separado).
**Brief**: `docs/planning/week11-sprint-5-l2-curves-t1-sparse-brief.md`
(format v3.4 — Liberal HALT discipline cap explicit ≤2 cohort-wide).
**ADR**: ADR-0009 v2.3 — `/markets/bond` authoritative listing +
multi-prefix canonical + ISO-currency-code falsified.
**Probe date**: 2026-04-26 (window `d1=2024-01-01`, `d2=2026-04-25`).
**Executor**: CC (Claude Code), full autonomy per SESSION_CONTEXT.
**Outcome**: **0 S1 upgrades / 4 S2 HALT-0 confirmed (3rd consecutive
re-probe)**. Liberal HALT cap **triggered** (4 ≥ 3 cohort-wide) →
**sprint-wide HALT** per brief §5.0. Scope-narrow ship: este probe
doc + CAL re-confirmation stamps (Sprint 5B) + ADR-0009 §5B
addendum + retro. Zero T1 curves coverage delta.

---

## 1. Pre-flight HALT #0 mandate

Per brief §2 + ADR-0009 v2.3 canonical cascade:

1. `/markets/bond?c=<key>&format=json` — autoridade final sobre
   universo TE de bonds soberanos por país (filter
   `.[] | select(.Country == "<C>")`).
2. Per-tenor `/markets/historical/<symbol>?d1=...&d2=...` confirmação
   de daily-live cadence + obs depth + latest staleness.
3. Classificação ADR-0009 v2.2 S1/S2:
   - **S1 PASS**: ≥6 distinct tenors daily, each ≥500 obs, latest
     ≤7 days stale, ≥2 short + 2 mid + 2 long structural coverage.
   - **S2 HALT-0**: <6 tenors OR structural mid-tenor gap blocking
     Svensson fit.
4. Liberal HALT discipline cap (brief §5): ≤2 HALT-0 cohort-wide
   → continue + ship rest; ≥3 → sprint-wide HALT, formalizar
   ADR-0009 v3 amendment se systemic TE issue (≥3 alone within
   5B group also triggers since cohort-wide cap is binary).

Empirical state recap pré-Sprint 5B:

- **Sprint T (2026-04-23)** primeiro probe per-tenor TE Path 1: CH=2,
  SE=2, NO=3, DK=2 tenors → todos S2 HALT-0.
- **Sprint T-Retry (2026-04-24)** multi-prefix v2.3 re-sweep: 0/5
  upgrades (NZ +2 short-end via `/markets/bond` ainda <6); CH/SE/NO/DK
  zero delta.
- **Sprint 5B (2026-04-26)** este probe — 3ª confirmação @ T+3 dias.

---

## 2. TE quota pre-check

Brief §5.1 HALT trigger: TE quota >70 % consumption mid-sprint →
HALT, await Hugo decision.

- Baseline pré-Sprint 5B (post Sprint T-Retry, per Sprint T-Retry
  probe doc §6): **~40 % April consumption**.
- Sprint 5B probe call budget: 1 `/markets/bond` + 9
  `/markets/historical` (per-tenor verification across 9 documented
  symbols) = **10 calls**.
- Estimated post-Sprint 5B: **~40-41 %** (well under 70 % HALT
  ceiling and 50 % Sprint T-Retry brief ceiling).

Quota state nominal — zero pressure for Path 2 cohort sprint.

---

## 3. `/markets/bond` authoritative listing — Sprint 5B re-confirmation

Single call filtered to 4 países alvo:

| Country | Symbols returned | Prefix families |
|---|---|---|
| Switzerland | `GSWISS10:IND`, `GSWISS2:GOV` | `GSWISS` |
| Sweden | `GSGB10YR:GOV`, `GSGB2YR:GOV` | `GSGB` |
| Norway | `GNOR10YR:GOV`, `NORYIELD52W:GOV`, `NORYIELD6M:GOV` | `GNOR` + `NORYIELD` |
| Denmark | `GDGB10YR:GOV`, `GDGB2YR:GOV` | `GDGB` |

**Delta vs. Sprint T-Retry 2026-04-24**: zero. Símbolo set, contagem,
prefix families — todos idênticos. TE bond universe para estes 4
países permanece estável across 3 probes em 3 dias (2026-04-23 →
2026-04-24 → 2026-04-26).

---

## 4. Per-tenor daily-live verification

Cada um dos 9 símbolos enumerados em §3 verificado individualmente
via `/markets/historical/<symbol>?d1=2024-01-01&d2=2026-04-25`:

| Symbol | Tenor | n obs | Latest close date | Latest close |
|---|---|---|---|---|
| `GSWISS2:GOV` | 2Y | 586 | 2026-04-24 | 1.126 % |
| `GSWISS10:IND` | 10Y | 585 | 2026-04-24 | 0.709 % |
| `GSGB2YR:GOV` | 2Y | 582 | 2026-04-24 | 2.291 % |
| `GSGB10YR:GOV` | 10Y | 591 | 2026-04-24 | 2.031 % |
| `GDGB2YR:GOV` | 2Y | 594 | 2026-04-24 | 3.208 % |
| `GDGB10YR:GOV` | 10Y | 600 | 2026-04-24 | 2.308 % |
| `GNOR10YR:GOV` | 10Y | 584 | 2026-04-24 | 3.281 % |
| `NORYIELD52W:GOV` | ~1Y | 589 | 2026-04-24 | 4.288 % |
| `NORYIELD6M:GOV` | 6M | 587 | 2026-04-24 | 4.587 % |

Todos os 9 símbolos:

- ≥500 obs (range 582–600) — clearance threshold ADR-0009 v2.2.
- Latest 2026-04-24 (2 dias stale @ probe time, comfortably ≤7 day
  staleness window).
- Daily-live cadence preserved (Sprint T baseline: ~580–600 obs ao
  longo de 24 meses ≈ 25 obs/mês).

Conclusão §4: nenhuma degradação de feed; nenhuma suspensão; nenhum
novo símbolo. Estado empírico congelado vs. Sprint T-Retry.

---

## 5. Per-country classification — Sprint 5B verdict

| Country | Sprint T (2026-04-23) | Sprint T-Retry (2026-04-24) | Sprint 5B (2026-04-26) | Threshold | Verdict |
|---|---|---|---|---|---|
| CH | 2 (2Y, 10Y) | 2 (2Y, 10Y) | **2 (2Y, 10Y)** | <4 brief §5.0 / <6 S1 | **S2 HALT-0** |
| SE | 2 (2Y, 10Y) | 2 (2Y, 10Y) | **2 (2Y, 10Y)** | <4 / <6 | **S2 HALT-0** |
| NO | 3 (6M, 52W, 10Y) | 3 (6M, 52W, 10Y) | **3 (6M, 52W, 10Y)** | <4 / <6 | **S2 HALT-0** |
| DK | 2 (2Y, 10Y) | 2 (2Y, 10Y) | **2 (2Y, 10Y)** | <4 / <6 | **S2 HALT-0** |

**4/4 países S2 HALT-0** — confirmed for the 3rd consecutive probe.

Aggregate cohort statistic (Sprint 5B + paralelo 5A APAC, assumindo
NZ permanece S2 HALT-0 per Sprint T-Retry empirical state): mínimo
**4 HALT-0** within Sprint 5B alone (sprint-wide HALT cap ≥ 3
**triggered**); cohort-wide total ≥4 HALT-0 (well above brief §5
Liberal cap).

---

## 6. HALT decision — sprint-wide

Brief §5 enumera:

> **Liberal HALT discipline cap**: ≤2 HALT-0 across cohort = continue
> + ship rest; ≥3 = sprint-wide HALT, formalize ADR-0009 v3
> amendment if systemic TE issue.

Sprint 5B contributes 4 HALT-0 (sozinho ≥3) → **sprint-wide HALT
trigger satisfeito** independentemente do resultado paralelo 5A
APAC.

**Decisão**: scope-narrow ship per Sprint T-Retry pattern (commit
inventory: probe doc + CAL stamps + ADR addendum + retro). Skip
brief §4 commits 2-5 (CH/SE/NO/DK connector ships) — nenhum país
PASS para shipar.

**ADR-0009 v3 amendment NÃO formalizado neste sprint** porque:

1. ADR-0009 v2.3 (Sprint T-Retry, 2026-04-24) já codifica
   formalmente o systemic TE issue — `/markets/bond` autoridade,
   multi-prefix canonical, ISO-currency-code falsified, structural
   mid-tenor-gap signal documentado.
2. Sprint 5B é **3rd consecutive empirical confirmation** do v2.3
   model — reinforça o ADR existente, não introduz nova regra.
3. Bump v2.3 → v3.0 sem nova regra material seria methodology
   versioning theatre (CLAUDE.md §4 "frozen contracts"); melhor
   shipar como addendum-stamp de v2.3 reinforcement.

Hugo é juiz se v3 bump justificado pós-Path-2 cohort sprint Week
11+ — neste momento os 5 Path 2 CALs (NL + NZ + CH + SE + NO + DK)
estão OPEN com Sprint T-Retry stamps; Sprint 5B só adiciona um 3º
stamp empírico aos 4 deste cohort.

---

## 7. Sprint 5B downstream actions (post-probe)

| Country | Path 1 | Action | Commits |
|---|---|---|---|
| CH | HALT-0 2 tenors (3rd confirm) | Skip C2-C5. Stamp `CAL-CURVES-CH-PATH-2` Sprint 5B. | C2 stamps |
| SE | HALT-0 2 tenors (3rd confirm) | Skip C2-C5. Stamp `CAL-CURVES-SE-PATH-2` Sprint 5B. | C2 stamps |
| NO | HALT-0 3 tenors (3rd confirm) | Skip C2-C5. Stamp `CAL-CURVES-NO-PATH-2` Sprint 5B. | C2 stamps |
| DK | HALT-0 2 tenors (3rd confirm) | Skip C2-C5. Stamp `CAL-CURVES-DK-PATH-2` Sprint 5B. | C2 stamps |

### 7.1 te.py changes — none

`TE_YIELD_CURVE_SYMBOLS` already excludes CH/SE/NO/DK; module
docstring (lines 235-236) already documents "S2 HALT-0 (all ≤3 TE
tenors)". Zero code edit required.

### 7.2 `daily_curves.py` changes — none

`T1_CURVES_COUNTRIES` already at 11 countries (US/DE/EA/GB/JP/CA/IT/ES/FR/PT/AU
post Sprint T close). `_DEFERRAL_CAL_MAP` already routes CH/SE/NO/DK
to per-country `CAL-CURVES-{X}-PATH-2`. Zero code edit required.

### 7.3 `country_tiers.yaml` changes — none

`curves_live: false` already correctly set for CH/SE/NO/DK per Sprint
T-Retry close.

### 7.4 `nss-curves.md` country scope appendix — none required

§2 já lista CH/NO/SE em "T1 FR/IT/ES/NL/CA/AU/CH/NO/SE/NZ" tier
group; tier scope unaffected por Path 1 vs. Path 2 routing decision.

### 7.5 Documentation deliverables — Commit 2 + Commit 3

- C2 stamps in `docs/backlog/calibration-tasks.md`: 4 CAL entries
  receive Sprint 5B re-confirmation line (3rd stamp post Sprint T +
  Sprint T-Retry).
- C2 ADR-0009 §5B addendum stamp (no version bump): empirical
  confirmation reinforcing v2.3 codification.
- C3 retrospective: `docs/planning/retrospectives/week11-sprint-5-l2-curves-t1-sparse-report.md`
  (5B subset — 5A APAC may merge separately or Hugo may consolidate).

---

## 8. Pattern library — Sprint 5B observations

### 8.1 State stability across 3 probes (3-day window)

CH/SE/NO/DK TE bond universe é structurally frozen — três probes
em três dias (2026-04-23 / 2026-04-24 / 2026-04-26) retornaram o
exato mesmo símbolo set (CH=2, SE=2, NO=3, DK=2) com obs counts
+5 a +9 por símbolo (correspondente a ~3 trading days de novos
dados daily appended) e latest dates avançando linearmente
(22/04 → 22/04 → 24/04). **Zero structural delta**.

Implicação pattern-library: para sparse-T1 países onde TE Path 1
fails by structural coverage gap (não por intermittent feed
issues), a confirmação re-probe convergência é trivial — daily
cadence apenas avança numericamente, símbolo set é estável.

**Amendment candidate (não codificado, observação apenas)**: após
≥2 confirmações S2 HALT-0 em probes consecutivos, eliminar
re-probe mandatory cycle e proceder directamente para Path 2
cohort sprint. Sprint T-Retry → Sprint 5B é o 1º exemplo onde a
3ª probe seria desnecessária se esta heurística estivesse
codificada (custo evitado: ~10 TE calls + ~30 min CC time).

### 8.2 ADR-0009 v2.3 robustez empírica

v2.3 codificada Sprint T-Retry teve a 1ª aplicação prática com
Sprint 5B — `/markets/bond` autoridade re-validada, ISO-currency
não-probada (já falsificada Sprint T-Retry), multi-prefix
sweep não-necessário porque `/markets/bond` conclusivo. Pattern
library é ortogonal a re-probe rate quando a base ADR está sólida.

### 8.3 Path 2 cohort sprint priorization (Week 11+)

Os 4 países 5B classificados Sprint 5B + 1 NZ (5A) + NL (Sprint M
residual) totalizam 6 OPEN Path 2 CALs:

| País | Estimate | Reusable infra | Trigger país-específico |
|---|---|---|---|
| DK | 1-2h | `NationalbankenConnector` (Sprint Y-DK) | Lowest cost; CD-rate vs discount divergence handling pré-shipped |
| CH | 2-3h | `SnbConnector` (Sprint V-CH) | Negative-rate-era handling pré-shipped |
| SE | 2-3h | `RiksbankConnector` (Sprint W-SE) | Negative-rate-era handling pré-shipped |
| NO | 2-3h | `NorgesbankConnector` (Sprint X-NO) | Multi-prefix dual-family TE precedent |
| NL | 3-5h | new `DnbConnector` from scratch | OpenDatasoft platform risk per Sprint D BdF precedent |
| NZ | 2-3h | new RBNZ scraper | No prior monetary infra |

Total Week 11+ Path 2 budget projection: **12-19h CC** (alinhado
com Sprint T retro §5.3 estimate).

---

## 9. Aggregated verdict

| Country | TE tenors (Sprint 5B) | Brief §5.0 threshold (<4) | ADR v2.2 S1 threshold (<6) | Verdict | CAL action |
|---|---|---|---|---|---|
| CH | 2 | Fail | Fail | S2 HALT-0 (3rd) | `CAL-CURVES-CH-PATH-2` stamp Sprint 5B |
| SE | 2 | Fail | Fail | S2 HALT-0 (3rd) | `CAL-CURVES-SE-PATH-2` stamp Sprint 5B |
| NO | 3 | Fail | Fail | S2 HALT-0 (3rd) | `CAL-CURVES-NO-PATH-2` stamp Sprint 5B |
| DK | 2 | Fail | Fail | S2 HALT-0 (3rd) | `CAL-CURVES-DK-PATH-2` stamp Sprint 5B |

**S1 upgrade rate Sprint 5B: 0/4 = 0 %** (alinhado com Sprint
T-Retry worst-case; alinhado com ADR-0009 v2.3 expected after
multi-prefix exhaustion).

**Liberal HALT cohort cap (≥3 across cohort)**: triggered by 5B
alone (4 HALT-0). Sprint-wide HALT is the autonomous decision
per brief §5.

---

## 10. TE quota Sprint 5B actuals

| Item | Calls |
|---|---|
| `/markets/bond` autoridade | 1 |
| `/markets/historical/<symbol>` per-tenor verification | 9 |
| **Total Sprint 5B probe** | **10** |

Baseline pré-Sprint 5B: ~40 %. Post-Sprint 5B: ~40-41 %. Headroom
até 70 % HALT ceiling: ~29 pp. Suficiente para 6-país Path 2 cohort
sprint Week 11+ sem pressão.

---

*End of probe doc. Sprint 5B re-confirms Sprint T + Sprint T-Retry
classifier verdicts for 3rd consecutive time (4/4 S2 HALT-0). Liberal
HALT cap triggered at 4 ≥ 3 cohort-wide → sprint-wide HALT per brief
§5 → scope-narrow ship (probe doc + CAL stamps + ADR addendum +
retro). Zero T1 coverage delta. Path 2 cohort sprint Week 11+
empirically over-justified post 3 confirmations.*
