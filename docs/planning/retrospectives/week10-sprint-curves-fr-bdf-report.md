# Week 10 Day 1+ Sprint D — CAL-CURVES-FR-BDF Pilot Retrospective

**Sprint**: D — Week 10 Day 1+ CAL-CURVES-FR-BDF (first national-CB
integration for EA periphery; pilot for four follow-on sprints
IT-BDI / ES-BDE / PT-BPSTAT / NL-DNB).
**Branch**: `sprint-curves-fr-bdf`.
**Worktree**: `/home/macro/projects/sonar-wt-curves-fr-bdf`.
**Brief**: `docs/planning/week10-sprint-d-fr-bdf-brief.md` (format v3 —
third production use in Week 10; CAL-138 first + Sprint A second).
**Duration**: ~1.5h CC (single session 2026-04-22, well under the
3-4h budget because HALT-0 fired in Commit 1's pre-flight probe —
identical shape to Sprint A).
**Commits**: 3 substantive + this retro = 4 total (vs. brief's 5-7
target).
**Outcome**: Ship docs-first via scope narrow per HALT-0 — zero
country connectors wired into the dispatcher; `BanqueDeFranceConnector`
shipped as a documentation-first scaffold (raises
`InsufficientDataError` on every fetch method, preserving the
interface for a future methods-only swap-in); ADR-0009 formalizes the
probe-first discipline for the four successor sprints; CAL entry
marked BLOCKED with probe matrix; successor CAL entries annotated
with the ADR-mandated pre-flight discipline.

---

## 1. Commit inventory

| # | SHA | Subject | Scope |
|---|---|---|---|
| 1 | `2151381` | feat(connectors): Banque de France scaffold + pre-flight HALT-0 (2026-04-22) | New `src/sonar/connectors/banque_de_france.py` (documentation-first scaffold) + 14 unit assertions on the interface contract + constants surface |
| 2 | `5db6d38` | docs(backlog): sharpen FR-BDF pointer + ADR-0009 pre-flight discipline for successor sprints | `calibration-tasks.md` — FR BLOCKED with full probe matrix; IT/ES/PT/NL annotated with ADR-0009 probe mandate + 4-5h budget; NL-DNB flagged highest-risk. `ecb_sdw.py` + `daily_curves.py` module docstrings extended with Sprint D empirical finding |
| 3 | `cbc74dc` | docs(adr): ADR-0009 national-CB connectors for EA periphery — pattern inversion | New `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` — "probe before scaffolding" discipline, 4 alternatives, consequences, follow-ups |
| 4 | (this commit) | docs(planning): Week 10 Sprint D Banque de France retrospective | — |

---

## 2. Scope outcome vs brief

### Brief's ambition (§1 Scope)

Banque de France connector shipped + wired into `daily_curves` +
`T1_7_COUNTRIES` expanded to include FR + 2 cassettes
(`oat_nominal_2024_12_31.json`, `oatei_linker_2024_12_31.json`) +
@slow live canary FR 2024-12-31 + Trésor 10Y cross-val + NSS RMSE
≤ 10 bps + ADR-00XX + pattern notes for four successors.

### Empirical reality (Commit 1 pre-flight probe)

The Commit 1 probe executed the brief §9 fallback hierarchy
(BdF primary → AFT → TE → FRED) and documented each outcome:

| Source | URL / Probe | Result | Verdict |
|---|---|---|---|
| BdF legacy SDMX REST | `https://webstat.banque-france.fr/ws_wsfr/rest/data/BDF.TITRES/D.OAT.10Y.R` | HTTP 404 on every dataflow/series permutation | **DEAD** — decommissioned in BdF → OpenDatasoft migration mid-2024 |
| BdF OpenDatasoft explore API | `https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets?limit=100` | `total_count = 1` — only `tableaux_rapports_preetablis` exposed; yield-adjacent file is `Taux_indicatifs_et_OAT_Archive.csv` (8 tenors {1M, 3M, 6M, 9M, 12M, 2Y, 5Y, 30Y}, no 10Y, end-of-period monthly, publication frozen 2024-07-11) | **INSUFFICIENT** — frequency + tenor-completeness both fail |
| AFT (Agence France Trésor) | `https://www.aft.gouv.fr/` + `/en/oat-yields-history` | HTTP 403 behind Cloudflare managed-challenge (`cf-mitigated: challenge`) | **UNREACHABLE** programmatically |
| TE `fetch_fr_yield_curve_nominal` | `src/sonar/connectors/te.py` — `TE_YIELD_CURVE_SYMBOLS` | Not shipped CAL-138 (FR exposes `GFRN10:IND` 10Y-only via `/markets/historical`) | **INSUFFICIENT** — single-tenor, below `MIN_OBSERVATIONS = 6` |
| FRED OECD mirror | `IRLTLT01FRM156N` via `api.stlouisfed.org/fred/series` | 10Y monthly only | **INSUFFICIENT** |

**HALT trigger 0 fired per brief §5** — all four paths failed to
provide a ≥ 6-tenor daily FR sovereign yield curve.

### Scope-narrow delivery

Per the Sprint A + CAL-138 precedents ("Future briefs should phrase
acceptance in shape-independent terms so scope-narrow does not break
the checklist"), Sprint D ships:

1. **Documentation-first scaffold** — `src/sonar/connectors/banque_de_france.py`
   captures the probe matrix in the module docstring (≈ 65 lines of
   empirical findings with URLs, HTTP codes, verdicts). The
   `BanqueDeFranceConnector` class implements the full
   `BaseConnector` + curves-analog interface
   (`fetch_series`, `fetch_yield_curve_nominal`,
   `fetch_yield_curve_linker`, `aclose`) but every fetch method
   short-circuits with `InsufficientDataError` citing the CAL pointer
   + probe date + findings summary. Constants
   (`BDF_BASE_URL`, `BDF_PROBE_DATE`, `BDF_PROBE_FINDINGS`,
   `FR_CAL_POINTER`) surface the probe state at tool-tip depth for
   future-me. The interface is frozen so a future implementation is a
   pure-methods delta.
2. **Backlog + connector-surface sharpening** — `CAL-CURVES-FR-BDF`
   marked BLOCKED with full probe matrix, unblock-criteria list
   (BdF API restore / licensed feed / browser-automation shim), and
   budget inflated 3-4h → 4-6h for any future re-attempt. The four
   successor entries (`CAL-CURVES-IT-BDI` / `CAL-CURVES-ES-BDE` /
   `CAL-CURVES-PT-BPSTAT` / `CAL-CURVES-NL-DNB`) annotated with
   ADR-0009 probe discipline + 4-5h budget + narrow-scope fallback
   template. `ecb_sdw.py` + `daily_curves.py` module docstrings cite
   the Sprint D outcome so the context surfaces at pipeline-log
   triage depth without grep'ing the backlog.
3. **ADR-0009** — `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md`
   formalizes "probe before scaffolding" discipline, four
   alternatives (probe-first chosen, HALT umbrella /
   EA-aggregate-permanent / browser-shim-first rejected with reasons),
   consequences (positive: artefact-per-sprint, interface frozen,
   empirical baseline; negative: 30-50 % budget inflation Week 11+,
   FR on proxy indefinitely, risk of ≥ 2 HALT-0 gates per-country
   signal), and four follow-ups (probe-ordered successor sprints,
   Phase 2+ alternative-data-source track, template.md update,
   retro mapping 4-unblock-conditions ↔ work-items).

No connector wired into the dispatcher. No new cassettes, no new live
canaries, no `T1_7_COUNTRIES` tuple expansion. Production behaviour
is unchanged relative to Sprint A close.

### Connector outcomes matrix

| Country | Nominal path | Linker path | Status (post Sprint D) |
|---|---|---|---|
| PT | Banco de Portugal BPstat (probe-first required) | `LINKER_UNAVAILABLE` permanent | `CAL-CURVES-PT-BPSTAT` OPEN — ADR-0009 probe mandate, 4-5h, probe-risk moderate |
| IT | Banca d'Italia BDS (probe-first required) | BTP€i via BDS (probe bundled) | `CAL-CURVES-IT-BDI` OPEN — ADR-0009 probe mandate, 4-5h, probe-risk moderate |
| ES | Banco de España SeriesTemporales (probe-first required) | Bonos-i post-2014 (probe bundled) | `CAL-CURVES-ES-BDE` OPEN — ADR-0009 probe mandate, 4-5h, probe-risk moderate |
| FR | Banque de France Webstat (**BLOCKED** — scaffold shipped Sprint D) | OATei via Webstat (blocked upstream of linker path) | `CAL-CURVES-FR-BDF` **BLOCKED** — ADR-0009 pilot |
| NL | DNB Statistics (probe-first required — **HIGH RISK** OpenDatasoft-migrated) | `LINKER_UNAVAILABLE` permanent | `CAL-CURVES-NL-DNB` OPEN — ADR-0009 probe mandate, 4-5h, probe-risk elevated |

### Linker coverage

Unchanged from Sprint A close. `fetch_yield_curve_linker` remains
rejecting for all periphery countries in `ecb_sdw.py` with the
per-country CAL pointer; Sprint D scaffold preserves the linker
stub for FR behind the same `InsufficientDataError` gate because
the nominal-path block invalidates any real-curve composition
regardless of linker quality. OATei is nominally the best-in-class
EA-periphery linker (full tenor spectrum 1998+) but this
advantage is moot until the nominal source is restored.

---

## 3. HALT triggers

| # | Trigger | Fired? | Outcome |
|---|---|---|---|
| 0 | BdF API + AFT + TE + FRED all fail | **YES** | HALT-0 on every probed path. Scope narrow to scaffold + CAL BLOCKED + ADR-0009 + retro. Sprint A / CAL-138 precedents followed |
| 1 | BdF API requires authentication | N/A | Authentication not reached — endpoint returns 404 before any auth challenge |
| 2 | SDMX format unexpected | N/A | Endpoint decommissioned; no SDMX payload to parse |
| 3 | Per-tenor series codes not discoverable | N/A | Catalog exposes only one archive dataset, not per-tenor series |
| 4 | OATei linker series sparse | N/A | Nominal gap upstream of linker scope |
| 5 | NSS fit convergence failure FR specific | N/A | No NSS fit executed |
| 6 | Cassette count < 2 | N/A | Zero cassettes shipped — scope-narrow path records no HTTP surface to mock |
| 7 | Live canary wall-clock > 30s | N/A | No canary shipped |
| 8 | Pre-push gate fails | No | ruff format + ruff check + mypy src/sonar + pytest on connectors + integration all green on every commit |
| 9 | No `--no-verify` | No | Standard discipline |
| 10 | Coverage regression > 3pp | Not applicable | Scaffold adds 14 unit tests covering 100 % of the new module (stub behaviour); no source LOC removed from existing modules |
| 11 | Push before stopping | Pending | §10 pre-merge checklist + §11 `sprint_merge.sh` executed at end of this retro |
| 12 | Sprint C file conflict | No | Zero primary-file overlap; Sprint C works on `connectors/oecd_eo.py` + `indices/monetary/builders.py` + `daily_monetary_indices.py`; Sprint D works on `connectors/banque_de_france.py` + `connectors/ecb_sdw.py` + `pipelines/daily_curves.py` + `adr/` + `backlog/`. Shared: `docs/backlog/calibration-tasks.md` — union-merge trivial |
| 13 | FR cross-val deviation > 20 bps vs Trésor | N/A | No fit executed to cross-val |

---

## 4. Pre-merge checklist (brief v3 §10) — third production use

- [ ] All commits pushed — executed at end of this retro commit sequence.
- [x] Workspace clean — `git status` returns no modifications after
      this retro commit lands.
- [x] Pre-push gate passed — ruff (format + check), mypy project,
      pytest on relevant suites green on every commit. Full unit run
      surfaces pre-existing asyncio-cleanup flakiness unrelated to
      this sprint (confirmed also present on `main` at `e78f204`).
- [x] Branch tracking — set by `git push -u` on first push
      (worktree branch is `sprint-curves-fr-bdf`).
- [x] Cassettes / canaries — N/A for scope-narrow path; brief §6
      counts assumed a working BdF HTTP surface which HALT-0
      invalidated. Scaffold ships with 14 hermetic unit assertions
      covering interface contract + error-raising behaviour.
- [x] systemd service — unchanged (Sprint A already covered the
      deferral routing; T1 tuple unchanged → no daemon-reload needed).
- [x] Paralelo discipline — zero primary-file overlap with Sprint C
      (`connectors/oecd_eo.py` + `indices/monetary/builders.py` +
      `daily_monetary_indices.py` are Sprint C's primary scope;
      Sprint D touched `connectors/banque_de_france.py` +
      `connectors/ecb_sdw.py` + `pipelines/daily_curves.py` +
      `docs/adr/` + `docs/backlog/` + `docs/planning/retrospectives/`).

### Merge execution (brief v3 §11)

Operator runs:

```bash
./scripts/ops/sprint_merge.sh sprint-curves-fr-bdf
```

Third production use of `sprint_merge.sh`. First two uses (CAL-138,
Sprint A) succeeded.

---

## 5. Brief format v3 — third-use lessons

- ✓ **§10 pre-merge checklist still valuable** — third consecutive
  scope-narrow sprint (CAL-138 → Sprint A → Sprint D) where the
  checklist's explicit push / workspace-clean / paralelo-discipline
  items kept the 1.5h path honest.
- ✓ **§5 HALT-0 compositional with §9 fallback hierarchy** — the
  Sprint D brief already anticipated HALT-0 on the "all four paths
  fail" condition and §9 made the probe order crisp; Commit 1 executed
  the probes sequentially and HALT-0 was the correct autonomous
  response without bespoke decision-tree reasoning.
- ~ **§6 acceptance criteria still scope-fixed** — the brief listed
  "≥ 8 tenors nominal", "≥ 3 linker", "RMSE ≤ 10 bps",
  "cross-val ≤ 20 bps", "2 cassettes", "live canary PASS" as
  acceptance gates; HALT-0 invalidates all of them. Same criticism
  as CAL-138 + Sprint A retros: future briefs want outcome-based
  phrasing ("at least one country shipped full-impl **or** CAL
  BLOCKED with probe matrix + ADR + retro").
- ~ **§9 fallback hierarchy under-specified TE state** — the brief
  wrote "TE fetch_fr_yield_curve_nominal (if shipped Sprint CAL-138)"
  but CAL-138 retro had already documented FR as unshipped
  (GFRN10 single-tenor). Future briefs should check upstream sprint
  retros + pre-lock empirical state of fallbacks before drafting
  the fallback hierarchy.
- **New for v4 recommendation**: §4 Commit 1 template could include
  an explicit "scaffold-path vs full-impl-path" bifurcation in the
  commit body template so HALT-0 outcomes slot into the brief
  seamlessly. Today the scaffold-path requires the Claude Code
  session to improvise the structural decision (rescue the CAL +
  ADR + retro from the probe finding); a template bifurcation would
  make that path first-class.

---

## 6. Pattern notes for four successor sprints (ADR-0009 mandate)

### Recommended execution order (by migration risk)

1. **IT-BDI** (probe risk: moderate). Banca d'Italia BDS
   `infostat.bancaditalia.it` SDMX 2.1 / CSV. No known platform
   migration in 2024; historically stable public API. Highest-value
   target because IT has the widest EA-periphery sovereign-spread
   range (post-2011 crisis / 2018 Lega / 2022 energy-war).
2. **ES-BDE** (probe risk: moderate). Banco de España
   `SeriesTemporales` / BE-Series. Portal migrated multiple times
   but not to OpenDatasoft; probe with full Sprint D §9 hierarchy
   on Commit 1.
3. **PT-BPSTAT** (probe risk: low-moderate). Banco de Portugal
   `bpstat.bportugal.pt/data/v1` — native REST, not known to be
   migration-affected. Lowest probe risk of the four; candidate for
   "easiest win after IT".
4. **NL-DNB** (probe risk: **elevated**). DNB migrated to OpenDatasoft
   mid-2024 — **same platform** that revealed the BdF tenor gap.
   Probability ≥ 0.5 that probe returns similar monthly-archive-only
   surface. Schedule last; budget full 4-5h for scaffold path; consider
   bundling with a licensed-feed track if HALT-0 confirms.

### Commit 1 probe checklist per sprint (ADR-0009)

Execute the probe matrix first, then decide scaffold-vs-full-impl:

```bash
# 1. Base-URL reachability
curl -s -I "<cb_public_url>" -A "SONAR/2.0"
# 2. Catalog / dataset discovery
curl -s "<catalog_api>" | python3 -m json.tool | head -50
# 3. Per-tenor series discovery (or: dataset introspection)
curl -s "<series_or_dataset_endpoint>" -A "SONAR/2.0" | head -50
# 4. Fallback: TE native symbol + FRED OECD mirror (already probed
#    Sprint CAL-138; verify still current)
```

Decision table:

| Probe outcome | Scope |
|---|---|
| HTTP 200 + ≥ 6 tenors + daily + public | Full impl per Bundesbank analog — connector + dispatch + cassettes + canary + retro |
| HTTP 200 + < 6 tenors OR non-daily | Scaffold per Sprint D pattern — document the gap + CAL BLOCKED + ADR-0009 addendum |
| HTTP 4xx OR deprecated | Scaffold per Sprint D pattern — document decommission + unblock criteria |

### Shared deliverables across the four successors

- Each sprint's `src/sonar/connectors/{bank_slug}.py` (even in scaffold
  path) shares the Sprint D module-docstring shape: (i) 1-para context,
  (ii) probed paths bulleted with URL + HTTP + verdict, (iii) unblock
  criteria, (iv) references section linking this ADR + the per-country
  retro.
- Each sprint amends this ADR-0009's §Consequências follow-ups with a
  1-line entry recording its probe outcome (HALT-0 / partial / full).
- Backlog entry format: BLOCKED if HALT-0; CLOSED with commit refs
  if full impl; SUPERSEDED by per-tenor sub-items if partial.
- Retro per v3 format in `docs/planning/retrospectives/week10-sprint-curves-{cc}-{cb}-report.md`.

---

## 7. Production impact

**None relative to Sprint A close**. The 06:00 UTC
`sonar-daily-curves.service` iterates
`T1_7_COUNTRIES = ("US", "DE", "PT", "IT", "ES", "FR", "NL")` as
before; PT/IT/ES/FR/NL continue to emit `InsufficientDataError`
with the Sprint-A-installed per-country CAL pointers. FR continues
on the `EA_AAA_PROXY_FALLBACK` path in `daily_overlays` + downstream
cascade. The sharpened docstring + CAL entry improve operator
triage — the pipeline log's CAL pointer now lands on an entry that
explains the BLOCKED state in one read, and ADR-0009 is one link away.

Cascade unchanged: `daily_cost_of_capital` uses the EA-aggregate ERP
proxy for FR runs; the `MATURE_ERP_PROXY_FR` / `EA_AAA_PROXY_FALLBACK`
flags on persisted rows already encode the gap.

Future unblocks and their production deltas:

- **Option (a) — BdF restores per-tenor daily feed**: FR curve lands
  same day as connector methods swap (no `T1_7` change; no
  `_DEFERRAL_CAL_MAP` change; `BanqueDeFranceConnector` dispatcher
  branch added alongside Bundesbank; `CAL-CURVES-FR-BDF` → CLOSED;
  overlays cascade gains FR per-country signal at next 07:30 WEST run).
- **Option (b) — Licensed feed provisioned**: similar to (a) but
  through a new connector (`bloomberg.py` / `refinitiv.py`); scaffold
  module kept for reference.
- **Option (c) — Browser-automation shim for AFT**: riskiest
  operationally (adds a headful Chromium to the ops surface); only
  justified if IT/ES/PT/NL also HALT-0.

---

## 8. Final tmux echo

```
SPRINT D FR BANQUE DE FRANCE DONE: 4 commits on branch sprint-curves-fr-bdf

Countries shipped: 0 of 1 (scope-narrow per HALT-0 — all four brief §9
  fallback paths failed).

Pre-flight probe findings (Commit 1 body):
- BdF legacy SDMX REST (ws_wsfr/rest/data/): HTTP 404 — decommissioned
  mid-2024 in BdF → OpenDatasoft migration.
- BdF OpenDatasoft explore API: total_count=1, single dataset exposes
  an 8-tenor monthly archive CSV (no 10Y; frozen 2024-07-11).
- AFT (www.aft.gouv.fr): HTTP 403 Cloudflare-challenged; headless
  unreachable.
- TE fetch_fr_yield_curve_nominal: never shipped CAL-138 (FR =
  GFRN10:IND 10Y-only, below MIN_OBSERVATIONS=6).
- FRED OECD mirror IRLTLT01FRM156N: 10Y monthly only.

Empirical conclusion: no viable ≥ 6-tenor daily FR sovereign yield
curve on the public data plane as of 2026-04-22. Pattern assumption
that BdF would mirror Bundesbank inverted.

Artefacts shipped (scope-narrow):
- src/sonar/connectors/banque_de_france.py — documentation-first
  scaffold; BaseConnector + curves-analog interface preserved;
  all fetch methods raise InsufficientDataError with probe matrix.
- 14 unit assertions locking the interface contract (pre-push gate
  green).
- docs/backlog/calibration-tasks.md — CAL-CURVES-FR-BDF BLOCKED with
  probe matrix + unblock criteria; IT-BDI / ES-BDE / PT-BPSTAT /
  NL-DNB annotated with ADR-0009 pre-flight discipline + 4-5h budget.
- docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md — probe-
  first discipline, 4 alternatives, consequences, 4 follow-ups.
- src/sonar/connectors/ecb_sdw.py + src/sonar/pipelines/daily_curves.py
  module docstrings sharpened with Sprint D empirical finding.

HALT triggers fired: [0]. Composed cleanly per Sprint A + CAL-138
precedents; scope narrowed autonomously within brief §5 + CLAUDE.md
§11 ("Hugo é juiz, nunca inventar") — Sprint A docs-only precedent +
Sprint D scaffold-first extension. No dispatcher wiring because
dispatching through the stub would surface the same error one layer
deeper without changing pipeline outcome.

Brief format v3 third-use: §10 pre-merge checklist + §11 sprint_merge.sh
hook valuable; §6 acceptance criteria still scope-fixed; §9 fallback
hierarchy needed upstream-state verification (TE "if shipped CAL-138"
was already known unshipped at brief-write time).

Production impact: unchanged vs Sprint A close. FR remains on
EA-AAA proxy fallback. Pattern validated for 4 follow-on sprints
(ADR-0009 mandate: probe before scaffolding, 4-5h each, NL-DNB
highest risk per OpenDatasoft-migration cluster).

Paralelo with Sprint C (M2 output gap): zero primary file conflicts;
shared docs/backlog/calibration-tasks.md union-merge trivial.

Merge: ./scripts/ops/sprint_merge.sh sprint-curves-fr-bdf

Artifact: docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md
```
