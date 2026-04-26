# Week 11 Sprint 5A — T1 sparse curves APAC (AU + NZ) closure-only Retrospective

**Sprint**: 5A APAC subset of CAL-CURVES-T1-SPARSE-PROBES (paralelo ao 5B Europa Nórdica/Alpina, file-isolated per §3 brief).
**Branch**: `sprint-curves-t1-apac`.
**Worktree**: `/home/macro/projects/sonar-wt-curves-t1-apac`.
**Brief**: `docs/planning/week11-sprint-5-l2-curves-t1-sparse-brief.md` §1 5A.
**Predecessor success cited**: ADR-0009 v2.3 ledger Sprint H (IT/ES) + I (FR) + M (PT) + T (AU) + T-Retry (NZ/CH/SE/NO/DK re-confirmed).
**Duration**: ~1.5h CC (single session 2026-04-26; pre-flight audit + Hugo decision + 3 closure commits).
**Outcome**: **Closure-only ship** per Hugo Option B post-audit. Zero novos probes TE, zero novas integrações de connector, zero edits a `te.py` / `daily_curves.py`. AU + NZ outcomes empiricamente fixados em main 0cf8d0d (post Sprint T + Sprint T-Retry merge); 5A scope reduzido a 3 commits docs/yaml para closure formal do tracker T1-SPARSE no L2 NSS overlay.

---

## 1. Commit inventory

| # | SHA | Subject | Scope |
|---|---|---|---|
| 1 | (pre-flight only) | — | Audit pré-commit identificou redundância vs main; surfaced HALT-0 a Hugo antes de qualquer commit |
| 2 | `d0b307e` | chore(governance): country_tiers.yaml curves flags AU+NZ (Sprint 5A) | AU `curves_live: true`; NZ `curves_path_2_pending: true` |
| 3 | `e20f191` | docs(specs): nss-curves §12 country scope appendix (Sprint 5A) | 11/16 shipped + 5/16 deferred; codifica cascade Path 1 → 2 → 3 |
| 4 | (this commit) | docs(planning): Week 11 Sprint 5A APAC closure-only retrospective | — |

---

## 2. Pre-flight audit findings (Commit 1 substituído por surfacing-to-Hugo)

Brief §1 mandata "Probe + ship NSS curves para AU + NZ". Audit empírico contra main 0cf8d0d revelou estado já settled:

### 2.1 AU — already shipped (Sprint T 2026-04-23 merged)

| Artefacto | Localização | Conteúdo |
|---|---|---|
| TE symbols | `src/sonar/connectors/te.py:321-330` | `GACGB` family, 8 tenores 1Y-30Y |
| Pipeline tuple | `src/sonar/pipelines/daily_curves.py:279-291` | `T1_CURVES_COUNTRIES` inclui `"AU"` |
| Dispatcher set | `src/sonar/pipelines/daily_curves.py:296-298` | `CURVE_SUPPORTED_COUNTRIES` inclui `"AU"` |
| Unit tests | `tests/unit/test_connectors/test_te.py:365-382` | `GACGB` symbol assertions vivos |
| Live canary | `tests/integration/test_daily_curves_multi_country.py:170` | AU referenciado no T1 cohort |
| CAL state | `docs/backlog/calibration-tasks.md:3372` | `CAL-CURVES-AU-PATH-2` **CLOSED pre-open** |
| ADR ledger | ADR-0009 Sprint T addendum | T1 coverage 11/16 (AU = primeira sparse-T1 S1 PASS) |

### 2.2 NZ — empirically S2 HALT-0 (Sprint T-Retry 2026-04-24 confirmed)

`docs/backlog/probe-results/sprint-t-retry-multi-prefix-probe.md` (multi-prefix `/markets/bond`-authoritative cascade per ADR-0009 v2.3):

| Tenor | Symbol | n obs | Status |
|---|---|---|---|
| 3M | `GNZGB3M:IND` | 581 | ✓ |
| 6M | `GNZGB6M:IND` | 581 | ✓ |
| 1Y | `GNZGB1:IND` | 531 | ✓ |
| 2Y | `GNZGB2:GOV` | 587 | ✓ |
| 10Y | `GNZGB10:IND` | ~600 | ✓ |
| 3Y / 5Y / 7Y / 15Y / 20Y / 30Y | — | 0 | empty across todas as combinações prefix×suffix×endpoint |

**5/12 tenores; mid-curve (3Y/5Y/7Y) estructuralmente vazio**. < `MIN_OBSERVATIONS=6` codebase floor (Svensson: 9; NS-reduced: 6). `_DEFERRAL_CAL_MAP["NZ"] = "CAL-CURVES-NZ-PATH-2"` já live em `daily_curves.py:315`.

### 2.3 Brief baseline mismatch — documentation

Brief §6 acceptance afirmava `T1 curves coverage 9/16 → 13-15/16`. State real em main 0cf8d0d era **11/16** (US/DE/EA/GB/JP/CA + IT/ES/FR/PT + **AU**). Mismatch atribuível a:

1. **SESSION_CONTEXT staleness** — brief drafted citando Sprint H/I (IT/ES/FR cohort 2026-04-22) como predecessor mais recente, mas Sprint M (PT, 2026-04-23) + Sprint T (AU/NZ/CH/SE/NO/DK, 2026-04-23) + Sprint T-Retry (multi-prefix re-sweep, 2026-04-24) já tinham aterrado e merged antes do brief commit (0cf8d0d, 2026-04-26).
2. **Brief threshold inconsistente com codebase**: brief §2 HALT-0 trigger é "<4 tenores"; codebase `MIN_OBSERVATIONS=6` (NS-reduced). NZ a 5 tenores cleara o brief threshold mas falha o codebase floor — discrepância surfaced no audit como decision request.
3. **Brief framing TE Path 1**: descrição §8 "TE generic indicator API search '{country} government bond yield {tenor}Y'" não reflecte o pattern canónico ADR-0009 v2.3 (`/markets/bond` authoritative + `/markets/historical` per-tenor sweep). Não-bloqueante porque Hugo Option B skipou re-probes.

Hugo decision Option B (closure-only, no TE probes) post-audit fechou o gap docs-only sem desperdício de quota nem trabalho redundante.

---

## 3. HALT triggers (per brief §5)

| # | Trigger | Fired? | Outcome |
|---|---|---|---|
| 0 | Pre-flight HALT #0 — TE Path 1 returns <4 tenors | **Surfaced** (interpreted) | AU = redundância (já shipped) ⇒ HALT-0 substantivo "trabalho já completo"; NZ = 5 tenores empirical (Sprint T-Retry) com mid-curve estrutural vazio ⇒ HALT-0 substantivo "Path 1 exhausted, Path 2 pending". 2 HALT-0 dentro do cap Liberal cohort (≤2). |
| 1 | TE quota >70 % consumption | No | 0 calls feitas; quota delta = 0; baseline ~35 % per Sprint T-Retry doc |
| 2 | TE invalid token / schema drift | N/A | Não invocado |
| 3 | NSS fit RMSE > 5 bps post-probe | N/A | Sem fits novos |
| 4 | Coverage regression > 3pp | No | Coverage main 11/16 mantida; sem deltas de pipeline |
| 5 | Pre-push gate fail | No | Pre-commit 2x verde em ambos commits 2 + 3; pytest unit -x não corrido (yaml/md only); pre-existing asyncio cleanup flake `test_snb.py::test_multi_series_filtering` confirmado pre-existente em main e passa em isolation (Sprint D/H/I retro precedent) |
| 6 | Concurrent file conflict 5A vs 5B | No | File-level isolation respeitada — 5A tocou apenas `country_tiers.yaml` + `nss-curves.md` + retro; 5B opera em CH/SE/NO/DK rows yaml + `daily_curves.py` te.py se ship via Path 2; bookmark zones AU/NZ vs CH/DK/NO/SE não-overlapping |

Liberal HALT discipline: 2 HALT-0 substantivos surfaced (AU redundância + NZ confirmação) — **dentro do cap ≤2** mas com character distinto (não probe-failures novos, sim audit-failures vs brief baseline). Sprint-wide HALT NÃO fired. Hugo Option B accepted partial closure.

---

## 4. Pre-merge checklist (brief v3 §10 — fifth-class scope)

- [ ] All commits pushed — pendente: rebase onto origin/main 2395d47 + push
- [x] Workspace clean post-Commit-4 (this retro lands as Commit 4)
- [x] Pre-push gate per commit — pre-commit 2x (Hugo mandate); ruff/mypy skipped (no python edits); pytest unit não-applicable
- [x] Pre-existing asyncio flake confirmed in isolation pass — não bloqueante (Sprint D/H/I precedent)
- [x] Branch tracking — set on push
- [x] Tier scope verified T1 only — AU + NZ ambos T1 per `country_tiers.yaml`; ADR-0010 compliance absoluta (zero T2 surface tocada)
- [x] Cassettes / canaries — N/A; AU canary já vive em `test_daily_curves_multi_country.py` desde Sprint T merge; NZ canary não-aplicável (HALT-0)
- [x] systemd service — unchanged (zero deltas a `T1_CURVES_COUNTRIES` ⇒ no daemon-reload needed)
- [x] Paralelo discipline — file-isolation 5A vs 5B respeitada por design (zero overlap em yaml rows / te.py append zones / spec sections)

---

## 5. Brief format observations — Sprint 5A specifics

- ✓ **Pre-flight HALT #0 disciplina valor demonstrado**: o audit pré-commit catched o brief baseline staleness ANTES de qualquer commit ou TE call. Sem o HALT #0 mandate, o CC teria provavelmente burnt ~50 TE quota calls re-probing AU + NZ para reproduzir findings 2 dias velhas. Discipline ADR-0009 v2 (probe-first) compensou.
- ~ **Brief baseline staleness**: brief autorado 2026-04-26 mas referenciando snapshot Sprint H/I (2026-04-22) sem reflexão das sprints M/T/T-Retry intervenientes (2026-04-23 / 24). Recomendação format v6: brief drafting deve incluir um "current state" snapshot read-only de `T1_CURVES_COUNTRIES` + last 5 commits a `te.py` antes de fixar §1 scope, evitando assumir state pre-merge stale.
- ~ **Brief §2 vs §8 endpoint inconsistency**: §2 mandata "TE generic indicator API: search '{country} government bond yield {tenor}Y'" (indicator-name-search shape), enquanto §8 nota "TE generic indicator handles 2-30Y tenors via `te:get_indicator_data(country, indicator)`". O pattern canónico Sprint H/I/M/T/T-Retry usa `/markets/historical` Bloomberg symbols + `/markets/bond` authoritative listing — diferente endpoint family. Format v6: alinhar brief §2/§8 com ADR-0009 v2.3 cascade exacta.
- ~ **Brief §6 acceptance threshold ambiguity**: "T1 curves coverage 9/16 → 13-15/16" assume baseline pre-Sprint-T (9/16 era state pos Sprint I). Acceptance phrased em coverage-delta absoluto fica frágil a baseline drift; phrasing por-país-shape-independent (per Sprint G/H precedent) seria mais robusto: "≥0 dos 6 países sparse shipped (acceptable per Liberal HALT)".
- ✓ **Liberal HALT discipline cap ≤2 HALT-0**: applicado correctamente em Sprint 5A. AU "trabalho redundante" + NZ "empirical confirmation" = 2 HALT-0 não-novel (não probe-failures inéditos), surfaced + Hugo decision Option B accepted = closure-only ship sem gates novos.

---

## 6. Production impact

**None relative to Sprint T-Retry close (2026-04-24 06:00 UTC `sonar-daily-curves.service`)**. Pipeline daily-curves itera `T1_CURVES_COUNTRIES = (US, DE, EA, GB, JP, CA, IT, ES, FR, PT, AU)` como já estava; zero deltas a connector wiring, dispatch logic, ou systemd unit files. Os deferrals NL/NZ/CH/SE/NO/DK continuam a emitir `InsufficientDataError` com pointers CAL respectivos; `--all-t1` skip behaviour inalterado.

Documentation cascade improvements (Sprint 5A delta):

- `country_tiers.yaml` agora carrega curves coverage flags machine-readable (operator pode `yq '.tiers.T1[] | select(.curves_live)'` para enumerar shipped countries sem grep'ing código).
- `nss-curves.md` §12 appendix tira o burden de manutenção do tracker fora do ADR-0009 ledger histórico — appendix é state-snapshot Phase 2+, ADR é history.

---

## 7. CAL state (post-Sprint-5A)

| CAL | State | Sprint que fechou | Notes |
|---|---|---|---|
| `CAL-CURVES-AU-PATH-2` | CLOSED pre-open Sprint T | Sprint T 2026-04-23 | First sparse-T1 S1 PASS; sem novo work em 5A |
| `CAL-CURVES-NZ-PATH-2` | OPEN Week 11+ | n/a (re-confirmed Sprint T-Retry 2026-04-24) | Path 2 RBNZ cascade candidate; flag `curves_path_2_pending: true` em yaml |
| `CAL-CURVES-T1-SPARSE-PROBES` (parent) | Partially closed | Sprint 5A via 5A APAC + 5B Europa Nórdica em paralelo | 5A entrega 0 novos países shipped + 1 confirmed-deferral; 5B reportará separadamente |

---

## 8. TE quota delta

**0 calls** during Sprint 5A. Deliberate preservation — todos os outcomes empiricamente fixados em probe-results docs Sprint T (2026-04-23) + Sprint T-Retry (2026-04-24). Quota baseline post-Retry ~35 % April consumed; Sprint 5A não alterou.

---

## 9. Final tmux echo

```
SPRINT 5A APAC AU+NZ DONE: 3 commits on branch sprint-curves-t1-apac

Outcome: closure-only ship per Hugo Option B post-audit.
Zero novos probes TE; zero TE quota burn.

Pre-flight audit findings:
- AU: ALREADY SHIPPED via Sprint T 2026-04-23 (TE GACGB family,
  8 tenores; CAL-CURVES-AU-PATH-2 CLOSED pre-open).
- NZ: empirically S2 HALT-0 confirmado Sprint T-Retry 2026-04-24
  (5/12 tenores; mid-curve 3Y/5Y/7Y estructuralmente empty;
  CAL-CURVES-NZ-PATH-2 OPEN Week 11+ via RBNZ Path 2).

Brief baseline mismatch documented:
- Brief §6 assumed 9/16 baseline; actual main 0cf8d0d state was 11/16.
- Brief §2/§8 TE endpoint description (indicator-name-search) didn't
  match ADR-0009 v2.3 canonical (/markets/bond + /markets/historical).
- Brief §2 HALT-0 threshold (<4 tenors) inconsistent with codebase
  MIN_OBSERVATIONS=6 floor.

Artefacts shipped (closure-only):
- d0b307e chore(governance): country_tiers.yaml curves flags AU+NZ.
- e20f191 docs(specs): nss-curves §12 country scope appendix
  (11/16 shipped + 5/16 deferred + Path 1→2→3 cascade).
- (this commit) docs(planning): Sprint 5A retrospective.

Production impact: unchanged vs Sprint T-Retry close (T1 coverage
11/16; no daemon-reload needed; 5 deferrals still raise
InsufficientDataError with CAL pointers).

HALT triggers fired: [0]×2 substantively (AU redundância + NZ
empirical re-confirmation), within Liberal cap ≤2.
TE quota delta: 0 calls.

Paralelo with 5B Europa Nórdica: file-level isolation respeitada por
design (yaml rows AU/NZ vs CH/SE/NO/DK; spec §12 appendix written
once em 5A, 5B amends incrementalmente se needed).

ADR-0010 compliance: AU + NZ ambos T1; zero T2 surface added.

Merge: rebase onto origin/main 2395d47 + git push origin
sprint-curves-t1-apac (no sprint_merge.sh — closure-only scope).

Artifact: docs/planning/retrospectives/week11-sprint-5a-l2-curves-t1-apac-report.md
```
