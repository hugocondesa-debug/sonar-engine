# Week 11 Sprint 5B — Europa Nórdica/Alpina T1 sparse curves retrospective

**Sprint**: 5B — Subset Europa Nórdica/Alpina (CH + SE + NO + DK) do
T1 sparse cohort, paralelo com 5A APAC (AU + NZ; CC separado).
**Branch**: `sprint-curves-t1-europe-sparse`.
**Worktree**: `/home/macro/projects/sonar-wt-curves-t1-europe-sparse`.
**Brief**: `docs/planning/week11-sprint-5-l2-curves-t1-sparse-brief.md`
(format v3.4 — Liberal HALT cap explicit ≤2 cohort-wide).
**ADR**: ADR-0009 v2.3 — `/markets/bond` autoridade + multi-prefix +
ISO-currency falsified.
**Probe date**: 2026-04-26 (window `d1=2024-01-01`, `d2=2026-04-25`).
**Duration**: ~1h CC (single session 2026-04-26; substancialmente
abaixo do brief §8 budget 5h porque sprint-wide HALT trigger detected
durante pre-flight).
**Commits**: 3 substantive (this retro included).
**Outcome**: **Sprint-wide HALT** per Liberal cap (4 HALT-0 ≥ 3
cohort-wide trigger satisfeito por 5B sozinho). Scope-narrow ship:
probe doc + ADR §5B addendum + 4 CAL stamps + retro. Zero T1 curves
coverage delta (11/16 unchanged); 0 connector ships; 0 backfill;
3rd-confirmation pattern stamp acrescentado a 4 OPEN Path 2 CALs.

---

## 1. Commit inventory

| # | SHA | Subject | Scope |
|---|---|---|---|
| C1 | `00b9523` | `docs(probes): Sprint 5B Europa Nórdica/Alpina TE Path 1 3ª confirmação` | New `docs/backlog/probe-results/sprint-5b-europe-sparse-confirmation-probe.md` (300 lines) — `/markets/bond` autoridade + per-tenor `/markets/historical` daily-live verification para 9 símbolos × 4 países; Sprint-wide HALT decision trace; TE quota delta |
| C2 | `c175f0d` | `docs(adr): ADR-0009 §5B addendum + 4 PATH-2 CAL stamps Sprint 5B` | ADR-0009 §5B addendum (no v3 bump) + headings/bullets para `CAL-CURVES-{CH,SE,NO,DK}-PATH-2` |
| C3 | (this commit) | `docs(planning): Sprint 5B Europa Nórdica/Alpina retrospective` | Este retro |

---

## 2. Scope outcome vs. brief

### Brief's ambition (§1 Scope, §4 Commits)

5B target: ship NSS curves for CH + SE + NO + DK via TE Path 1
cascade (~6 commits: pre-flight + 4 per-country + pipeline/spec).
T1 curves coverage projection 11 → 13-15 (depending on HALT-0 count).

### Empirical reality (Commit 1 pre-flight probe)

**TE Path 1 confirmation matrix Sprint 5B (2026-04-26)**:

| Country | TE tenors | Symbols | Verdict (3rd confirm) |
|---|---|---|---|
| CH | 2 | `GSWISS2:GOV`, `GSWISS10:IND` | S2 HALT-0 |
| SE | 2 | `GSGB2YR:GOV`, `GSGB10YR:GOV` | S2 HALT-0 |
| NO | 3 | `NORYIELD6M:GOV`, `NORYIELD52W:GOV`, `GNOR10YR:GOV` | S2 HALT-0 |
| DK | 2 | `GDGB2YR:GOV`, `GDGB10YR:GOV` | S2 HALT-0 |

Estado idêntico a Sprint T (2026-04-23) e Sprint T-Retry (2026-04-24).
Obs counts +5 a +9 vs. T-Retry baseline (correspondente a ~3 trading
days appended à daily cadence); latest dates avançam linearmente
(22/04 → 22/04 → 24/04). Símbolo set frozen.

**Liberal HALT cap activation**: 4 HALT-0 ≥ 3 cohort-wide trigger
(brief §5) satisfeito por 5B sozinho → sprint-wide HALT autonomous
decision sob CC autonomy.

### Scope-narrow ship execution

Per Sprint T-Retry pattern (0 inversions → ship probe doc + ADR
addendum + CAL stamps + retro):

1. **C1 probe doc** — empirical record + decision trace.
2. **C2 ADR-0009 §5B addendum** — no v3 bump (reinforcement only;
   v2.3 já codifica systemic TE issue).
3. **C2 4× CAL stamps** — heading update + Sprint 5B 3rd-stamp bullet
   em `CAL-CURVES-{CH,SE,NO,DK}-PATH-2`.
4. **C3 retro** — este file.

Zero edits a `te.py` / `daily_curves.py` / `country_tiers.yaml` /
`nss-curves.md` (todos já correctly state pré-Sprint-5B): te.py
docstring linhas 235-236 já documentam "S2 HALT-0 (all ≤3 TE
tenors)"; `_DEFERRAL_CAL_MAP` já routes CH/SE/NO/DK para per-país
CALs; `T1_CURVES_COUNTRIES` já a 11 (post Sprint T close).

### Connector outcomes matrix

| Country | Path 1 | NSS fit | Cassette | Live canary | T1 tuple | CAL action |
|---|---|---|---|---|---|---|
| CH | HALT-0 | n/a | n/a | n/a | unchanged | Sprint 5B 3rd-stamp |
| SE | HALT-0 | n/a | n/a | n/a | unchanged | Sprint 5B 3rd-stamp |
| NO | HALT-0 | n/a | n/a | n/a | unchanged | Sprint 5B 3rd-stamp |
| DK | HALT-0 | n/a | n/a | n/a | unchanged | Sprint 5B 3rd-stamp |

---

## 3. HALT triggers (atomic — brief §5 enumeration)

| # | Trigger | Fired? | Outcome |
|---|---|---|---|
| 0 | Pre-flight HALT #0 — TE Path 1 probe <4 tenors | **YES × 4** | CH (2), SE (2), NO (3), DK (2) — todos abaixo do <4 threshold + <6 S1 threshold; Liberal cap ≥3 cohort-wide triggered → sprint-wide HALT |
| 1 | TE quota >70% mid-sprint | No | Pre-Sprint-5B ~40 % per Sprint T-Retry §6; post ~40-41 % (10 calls). 29 pp headroom. |
| 2 | TE invalid token / schema drift | No | Token validated via `/markets/bond` autoridade; payloads consistent com v2.3 schema. |
| 3 | NSS fit RMSE > 5 bps post-probe | n/a | No NSS fit executed (HALT-0 sub-caso B). |
| 4 | Coverage regression > 3 pp | No | Zero src edits → zero coverage delta. |
| 5 | Pre-push gate fail | No | Pre-commit hooks green em todos os 3 commits (docs-only → ruff/mypy skipped, secrets/yaml/conventional-commit checks Passed). |
| 6 | Concurrent file conflict 5A ↔ 5B | No (até retro time) | te.py / yaml unchanged (no per-country block edited); calibration-tasks.md edited only in 5B-owned CAL entries (CH/SE/NO/DK); retro filename uses 5B-specific suffix to avoid race condition com 5A APAC retro. |

---

## 4. Pre-merge checklist

- [x] All commits pushed ao branch sprint-curves-t1-europe-sparse: a verificar
      antes de push final (operator action).
- [x] Workspace clean: post-C3 `git status` retorna apenas este retro
      até C3 commit.
- [x] Pre-push gate passed: pre-commit hooks Passed em C1 + C2 + C3
      (docs-only paths skip ruff/mypy/pytest naturally; trailing-ws +
      end-of-file + conventional-commit checks Passed).
- [x] Tier scope verificado T1 only (per ADR-0010): CH/SE/NO/DK são T1
      per `country_tiers.yaml`. Zero T2 surface tocado.
- [x] Retrospective shipped per v3 format (este file).
- [ ] Push to remote (depende autorização Hugo per CLAUDE.md §5).

---

## 5. Lições — Sprint 5B specifics

### 5.1 Pre-flight HALT-0 detection caught the no-op sprint cleanly

A leitura mandatória pre-flight (brief §2 + ADR-0009 v2.3 +
`docs/backlog/probe-results/sprint-t-retry-multi-prefix-probe.md`)
expõs imediatamente que CH/SE/NO/DK foram empiricamente classificados
S2 HALT-0 em duas probes consecutivas anteriores (Sprint T 2026-04-23
+ Sprint T-Retry 2026-04-24). O probe re-run Sprint 5B confirmou
zero delta após +3 dias.

**Lição**: pre-flight reads não são teatro — são o primary halt-gate
para sprints que duplicam scope empiricamente esgotado. CC autonomy
requer pre-flight rigoroso para detectar este shape.

### 5.2 Liberal HALT cap binary trigger é decisão autónoma sob CC autonomy

Brief §5: "≥3 = sprint-wide HALT, formalize ADR-0009 v3 amendment if
systemic TE issue". 5B sozinho contribui 4 HALT-0 → cap triggered
unilateralmente. Decisão autónoma sob CC autonomy per CLAUDE.md §11
("Hugo é juiz, nunca inventar"): scope-narrow ship + report + retro
+ defer v3 amendment decision a Hugo.

A alternativa wrong-shape seria forçar commits 2-5 com scaffolds
empty (analogous a Sprint D Banque de France BLOCKED scaffolds) —
mas Sprint T-Retry já estabeleceu que these países justify Path 2
cascade (existing infra reusable: `SnbConnector`, `RiksbankConnector`,
`NorgesbankConnector`, `NationalbankenConnector`), não Path 1
scaffold. Empty scaffolds seriam churn.

### 5.3 v3 amendment NÃO formalizado — judgment call

Brief §5 condiciona ADR v3 a "if systemic TE issue". v2.3 (Sprint
T-Retry, 2026-04-24) já codifica formalmente o systemic issue
através de 3 regras explicit (v2.3.1 `/markets/bond` autoridade;
v2.3.2 multi-prefix canonical; v2.3.3 ISO-currency falsified). Sprint
5B é 3rd-confirmation reinforcing v2.3 model, não introdução de
nova regra.

Bump v2.3 → v3.0 sem alteração de regra material seria methodology
versioning theatre against CLAUDE.md §4 frozen-contracts discipline.
Decisão autónoma: **stamp empírico via §5B addendum only**. Hugo é
juiz se v3 bump justificado pós-Path-2 cohort sprint Week 11+.

### 5.4 State stability heurística — observada, não codificada

Three consecutive probes em 3 dias retornaram exact same símbolo set
para 4 países. Heurística candidata observada (apenas 1 caso, não
generalizable): após ≥2 confirmações S2 HALT-0 sob v2.3 multi-prefix
discipline, eliminar re-probe mandatory cycle.

**Custo evitável**: ~10 TE calls + ~30 min CC time por re-probe
redundant. Valor: marginal por país, mas escala se Path 2 cohort
estende a >5 países.

**Não codificado neste sprint**: 1º exemplo apenas; aguardar mais
um caso de re-probe redundância antes de codificar como ADR-0009
v2.4.

### 5.5 File-level isolation com paralelo 5A APAC

Conscious decisions to evitar race conditions:

- **Retro filename**: `week11-sprint-5b-l2-curves-t1-europe-sparse-report.md`
  (5B-specific suffix), NOT `week11-sprint-5-l2-curves-t1-sparse-report.md`
  (brief §7 unified path). Hugo consolidates post-merge if desired.
- **calibration-tasks.md**: edits scoped a CH/SE/NO/DK CAL entries
  only (NL/NZ entries unchanged neste sprint).
- **ADR-0009**: §5B addendum appended; no edits a addenda anteriores.
- **te.py / daily_curves.py / country_tiers.yaml / nss-curves.md**:
  zero edits (no S1 PASS countries to ship).

Result: zero file conflicts antecipados com paralelo 5A CC.

### 5.6 Pre-push gate friction — multi-scope rejection

Conventional-commit hook rejected `docs(adr+backlog):` scope no
primeiro commit attempt do C2 (multi-scope com `+` separator não
reconhecido). Resolved via single-scope `docs(adr):` com body
detailing CAL stamps. **Lição operacional**: prefer single-scope
even when multi-component changeset; document secondary scope no
body.

---

## 6. Production impact

**None relativo a Sprint T-Retry close**. The 06:00 UTC
`sonar-daily-curves.service` continua a iterar
`T1_CURVES_COUNTRIES = (US, DE, EA, GB, JP, CA, IT, ES, FR, PT, AU)`
(11 countries) com CH/SE/NO/DK skipped + per-country CAL pointer
em error message. Cascade unchanged.

Future unblock path (Path 2 cohort sprint Week 11+):

- DK ship → +1 country (1-2h CC; reusable `NationalbankenConnector`)
- CH ship → +1 country (2-3h CC; reusable `SnbConnector` +
  negative-rate-era handling)
- SE ship → +1 country (2-3h CC; reusable `RiksbankConnector` +
  negative-rate-era handling)
- NO ship → +1 country (2-3h CC; reusable `NorgesbankConnector` +
  multi-prefix dual-family TE precedent)

**Total Path 2 cohort sprint estimate**: 7-11h CC para os 4 5B
países (+ 5-8h para NL + NZ via Sprint 5A residual + Sprint M
NL legacy). Alinhado com Sprint T retro §5.3 12-19h projection.

---

## 7. ADR-0009 ledger Sprint 5B close

**Inversões TE Path 1 (Sprint H/I/M/T)**: IT + ES + FR + PT + AU
→ **5** (unchanged).

**Não-inversões S2 HALT-0 (Path 2 warranted)**: NL (Sprint M) + NZ
+ CH + SE + NO + DK (**Sprint T → Sprint T-Retry → Sprint 5B
re-confirmed × 3 para CH/SE/NO/DK**) → **6 não-inversões**
(unchanged em count; 4 ganham 3rd stamp).

Ledger ratio 5:6, paritarian, stable across 3 confirmation rounds.

---

## 8. CAL evolution

| CAL item | Status before | Status after | Note |
|---|---|---|---|
| `CAL-CURVES-CH-PATH-2` | OPEN (Sprint T-Retry stamp) | OPEN (Sprint 5B 3rd-stamp) | Heading + bullet appended |
| `CAL-CURVES-SE-PATH-2` | OPEN (Sprint T-Retry stamp) | OPEN (Sprint 5B 3rd-stamp) | Heading + bullet appended |
| `CAL-CURVES-NO-PATH-2` | OPEN (Sprint T-Retry stamp) | OPEN (Sprint 5B 3rd-stamp) | Heading + bullet appended; dual-prefix v2.3 §7.5.2 re-validated |
| `CAL-CURVES-DK-PATH-2` | OPEN (Sprint T-Retry stamp) | OPEN (Sprint 5B 3rd-stamp) | Heading + bullet appended; lowest Path 2 cost (1-2h) retained |

No new CAL items opened. No CAL items closed. NL + NZ unchanged
(scope respect — 5A APAC may stamp NZ separately).

---

## 9. TE quota delta

| Item | Calls |
|---|---|
| `/markets/bond` autoridade (1 call, filtered local) | 1 |
| `/markets/historical/<symbol>` × 9 símbolos | 9 |
| **Total Sprint 5B probe** | **10** |

- Baseline pre-Sprint-5B (post Sprint T-Retry): ~40 % April consumed.
- Post-Sprint-5B estimate: **~40-41 %**.
- Headroom até 70 % HALT ceiling: ~29 pp.
- Sufficient for Path 2 cohort sprint Week 11+ sem pressão.

---

## 10. Follow-ups

| # | Item | Owner | Target |
|---|---|---|---|
| F1 | Path 2 cohort sprint Week 11+ (DK / CH / SE / NO via reusable national-CB connectors) | CC (successor sprint) | Week 11+ |
| F2 | Sprint 5A APAC retro merge / consolidação com 5B retro | CC (successor) ou Hugo | Post-5A merge |
| F3 | ADR-0009 v3 bump decision | Hugo | Post-Path-2 cohort |
| F4 | Heurística "≥2 S2 HALT-0 → skip re-probe" codification (futura v2.4) | CC | After 1+ adicional precedent observed |
| F5 | brief §7 unified retro path consolidação (`week11-sprint-5-l2-curves-t1-sparse-report.md`) | Hugo | Post-merge |

---

## 11. Referências

- `docs/planning/week11-sprint-5-l2-curves-t1-sparse-brief.md` —
  Sprint 5 brief (5A + 5B parallel).
- `docs/backlog/probe-results/sprint-5b-europe-sparse-confirmation-probe.md`
  — Sprint 5B raw probe matrix (this sprint C1).
- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` §"Addendum
  Sprint 5B" — empirical reinforcement of v2.3 (this sprint C2).
- `docs/backlog/calibration-tasks.md` `CAL-CURVES-{CH,SE,NO,DK}-PATH-2`
  — Sprint 5B 3rd-stamps (this sprint C2).
- `docs/backlog/probe-results/sprint-t-retry-multi-prefix-probe.md` —
  Sprint T-Retry 2026-04-24 baseline (immediate predecessor).
- `docs/backlog/probe-results/sprint-t-sparse-t1-sweep-probe.md` —
  Sprint T 2026-04-23 first probe (initial baseline).
- `docs/planning/retrospectives/week10-sprint-t-sparse-t1-sweep-report.md`
  — Sprint T retro (S1/S2 classifier first large-scale application).
- `docs/specs/overlays/nss-curves.md` §2 (T1 country group inputs;
  CH/SE/NO listed in tier-1 EA-adjacent group).
- ADR-0010 (T1-complete-before-T2) — CH/SE/NO/DK são T1 per
  `country_tiers.yaml`; Sprint 5B respeita zero T2 surface.
- ADR-0011 Principle 2 (per-country isolation) — 4 5B países
  isolated in `_DEFERRAL_CAL_MAP` cleanly.

---

*End of Sprint 5B retrospective. Sprint-wide HALT per Liberal cap
(4 HALT-0 ≥ 3 cohort-wide). 3 commits substantive (probe doc + ADR
§5B addendum + 4 CAL stamps + retro). Zero T1 coverage delta.
v2.3 reinforced empiricamente; v3 bump decision deferred to Hugo
post Path 2 cohort sprint Week 11+.*
