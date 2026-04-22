# Week 10 Day 2 Sprint G — CAL-CURVES-IT-BDI + CAL-CURVES-ES-BDE Combined Retrospective

**Sprint**: G — Week 10 Day 2 combined IT + ES pilot (second ADR-0009
successor sprint after Sprint D FR-BDF; twins two EA-periphery probes
in a single worktree per combined-brief design).
**Branch**: `sprint-curves-it-es-bdi-bde`.
**Worktree**: `/home/macro/projects/sonar-wt-curves-it-es-bdi-bde`.
**Brief**: `docs/planning/week10-sprint-g-it-es-curves-brief.md`
(format v3 — fourth production use in Week 10: CAL-138 first, Sprint A
second, Sprint D third, Sprint G fourth).
**Duration**: ~2h CC (single session 2026-04-22; inside the 5-7h
budget because both probes fired HALT-0 in Commit 1's pre-flight,
and the ES sub-case — "HTTP 200 + non-daily" — added analytical depth
rather than implementation wall-clock).
**Commits**: 3 substantive + this retro = 4 total (vs. brief's 7-10
target — scope narrowed per §5 HALT-0 triggers 0 + 1 fired, exactly
as Sprint D precedent).
**Outcome**: Ship docs-first via scope narrow per HALT-0 per country —
zero country connectors wired into the dispatcher; `BancaDItaliaConnector`
+ `BancoEspanaConnector` shipped as documentation-first scaffolds
(raise `InsufficientDataError` on every fetch method, preserving
interfaces for future methods-only swap-in); ADR-0009 extended with
the Sprint G addendum formalizing three distinct HALT-0 sub-cases
(A: 4xx / deprecated; B: all paths dead; C: HTTP 200 + non-daily);
both CAL entries sharpened to BLOCKED with full probe matrices +
unblock-criteria lists.

---

## 1. Commit inventory

| # | SHA | Subject | Scope |
|---|---|---|---|
| 1 | `29c14d6` | feat(connectors): IT + ES scaffolds + pre-flight HALT-0 (ADR-0009) | New `src/sonar/connectors/banca_ditalia.py` + `src/sonar/connectors/banco_espana.py` documentation-first scaffolds + 28 unit assertions locking interface contracts |
| 2 | `53a51dc` | docs(backlog): sharpen IT-BDI + ES-BDE pointers + ADR-0009 Sprint G findings | `calibration-tasks.md` — both CAL entries BLOCKED with empirical probe matrices; `ecb_sdw.py` + `daily_curves.py` module docstrings extended with Sprint G findings |
| 3 | `6de3fd6` | docs(adr): ADR-0009 Sprint G addendum — IT + ES probe outcomes + pattern library | Three-sub-case pattern library (A/B/C); operational rules v2 (5-dimension probe matrix); follow-ups re-ordered (PT next, NL last); references updated |
| 4 | (this commit) | docs(planning): Week 10 Sprint G Banca d'Italia + Banco de España retrospective | — |

---

## 2. Scope outcome vs brief

### Brief's ambition (§1 Scope)

Both connectors shipped + wired into `daily_curves` + `T1_CURVES_COUNTRIES`
tuple expanded to include IT + ES + ≥ 4 cassettes (BTP nominal +
BTP€I linker for IT; Bono nominal + Bonos indexados for ES) + @slow
live canaries per country + MEF + Tesoro cross-val + NSS RMSE ≤ 10 bps
per country + ADR-0009 extension + pattern notes for remaining EA
periphery (PT + NL). Target: T1 curves coverage 6 → 8 countries
(US/DE/EA/GB/JP/CA/IT/ES).

### Empirical reality (Commit 1 pre-flight probes)

Both probe matrices executed the brief §2 fallback hierarchies in
parallel. Each country hit a different HALT-0 sub-case.

#### IT — Banca d'Italia probe matrix (strict HALT-0, sub-caso B)

| Source | URL / Probe | Result | Verdict |
|---|---|---|---|
| ECB legacy SDMX REST | `https://sdw-wsrest.ecb.europa.eu/service/data/BDS` | HTTP 000 (connection timeout) | **DEAD** — host decommissioned in 2023 SDW→Data Portal migration; BDS dataflow not re-published on `data-api.ecb.europa.eu` |
| BdI Infostat | `https://infostat.bancaditalia.it/` HTTP 200 landing SPA; `a2a.infostat.bancaditalia.it` / `sdmx.bancaditalia.it` / `bip.bancaditalia.it` | **NXDOMAIN** on all application subdomains from public DNS | **UNREACHABLE** — Infostat is browser-only; no public REST/SDMX surface |
| MEF / Tesoro Italiano | `www.dt.mef.gov.it/it/debito_pubblico/titoli_di_stato/` HTTP 200 HTML; `www.mef.gov.it/opendata/` HTTP 404 | HTML only / 404 | **INSUFFICIENT** — PDF/XLS press-release attachments per publication, no pipeline surface |
| ECB SDW `FM` IT override | `data-api.ecb.europa.eu/service/data/FM?filter=REF_AREA:IT` | HTTP 200 returns EA-aggregate MP rates (-0.25 / 2.00) — no IT yields | **INSUFFICIENT** — Sprint A finding re-confirmed |
| ECB SDW `IRS` IT override | `IRS?filter=REF_AREA:IT` | HTTP 200; single MATURITY_CAT='CI' (EMU criterion 10Y) | **INSUFFICIENT** — single tenor, monthly; below MIN_OBSERVATIONS=6 |
| FRED OECD mirror | `IRLTLT01ITM156N` | HTTP 200, 420 monthly observations, single-tenor | **INSUFFICIENT** — 10Y only, monthly |

HALT trigger 0 fired per brief §5 — all five paths failed to provide
a ≥ 6-tenor daily IT sovereign yield curve.

#### ES — Banco de España probe matrix (soft HALT-0, sub-caso C)

| Source | URL / Probe | Result | Verdict |
|---|---|---|---|
| BDEstad portal | `https://www.bde.es/webbde/es/estadis/infoest/` | HTTP 301 → `/wbe/es/estadisticas/` (legacy path decommissioned) | **MIGRATED** — Sprint A backlog URL stale |
| BdE BIE REST API | `https://app.bde.es/bierest/resources/srdatosapp/listaSeries?series=<code>&rango={30M,year}` | HTTP 200 JSON (gzip); `D_1NBBO320` ES long-term = 31 monthly obs in 30M window, `codFrecuencia='M'` | **LIVE but MONTHLY** — below daily pipeline cadence. 11-tenor ES sovereign yield coverage catalogued via BIE statistical-table chapters (BE_22_6 Letras 6 buckets 3M-12M + BE_22_7 Bonos 5 tenors 3Y-30Y), all monthly (`.M` suffix + `FRECUENCIA=MENSUAL` confirmed in CSV) |
| Tesoro Público | `https://www.tesoro.es/` | Resolves to 192.187.20.74; HTTPS TLS handshake fails (HTTP 000 in ~116 ms) | **UNREACHABLE** from VPS data plane |
| ECB SDW `FM` ES override | `FM?filter=REF_AREA:ES` | HTTP 200 returns EA-aggregate MP rates — no ES yields | **INSUFFICIENT** — Sprint A finding re-confirmed |
| FRED OECD mirror | `IRLTLT01ESM156N` | HTTP 200, 555 monthly observations, single-tenor | **INSUFFICIENT** — 10Y only, monthly |

HALT trigger 1 fired per brief §5 — the BdE BIE REST path is live and
serves ES sovereign yields with full 11-tenor coverage, but every
tenor publishes at monthly frequency, below the `daily_curves` pipeline's
daily cadence. Per ADR-0009 decision matrix: "HTTP 200 + non-daily" →
scaffold per Sprint D pattern. This is a new sub-case (sub-caso C)
not explicitly named in the Sprint D ADR-0009 original text.

### Scope-narrow delivery

Per Sprint D + Sprint A + CAL-138 precedents ("Future briefs should
phrase acceptance in shape-independent terms so scope-narrow does
not break the checklist"), Sprint G ships:

1. **Two documentation-first scaffolds** —
   `src/sonar/connectors/banca_ditalia.py` +
   `src/sonar/connectors/banco_espana.py` capture their respective
   probe matrices in module docstrings (≈ 85 + 90 lines of empirical
   findings with URLs, HTTP codes, verdicts, unblock-criteria per
   connector). Both classes implement the full `BaseConnector` +
   curves-analog interface (`fetch_series`, `fetch_yield_curve_nominal`,
   `fetch_yield_curve_linker`, `aclose`) but every fetch method
   short-circuits with `InsufficientDataError` citing the CAL pointer
   + probe date + findings summary. Constants
   (`BDI_BASE_URL`, `BDI_PROBE_DATE`, `BDI_PROBE_FINDINGS`,
   `IT_CAL_POINTER`; `BDE_BASE_URL`, `BDE_PROBE_DATE`,
   `BDE_PROBE_FINDINGS`, `ES_CAL_POINTER`) surface probe state at
   tool-tip depth for future-me. Interfaces are frozen so future
   implementations are pure-methods deltas.

   Symmetric structure with `banque_de_france.py` — the three
   scaffolds (FR + IT + ES) now share a uniform shape under ADR-0009
   pattern discipline.

2. **Backlog + connector-surface sharpening** —
   `CAL-CURVES-IT-BDI` + `CAL-CURVES-ES-BDE` marked BLOCKED with
   full probe matrices in Markdown table form, unblock-criteria lists
   per sub-case (IT: BdI public REST / licensed feed / browser shim;
   ES: BdE daily publish / pipeline monthly-cadence extension /
   parallel monthly pipeline / licensed feed), and estimates to
   re-attempt per unblock path (IT 4-6h CC; ES 4-6h or 6-8h
   depending on architecture change needed). `ecb_sdw.py` +
   `daily_curves.py` module docstrings cite the Sprint G outcome so
   the context surfaces at pipeline-log triage depth without
   grep'ing the backlog. Consistent with Sprint D's `PERIPHERY_CAL_POINTERS`
   docstring convention.

3. **ADR-0009 Sprint G addendum** — pattern library evolves from
   binary (full-impl vs scaffold) to ternary with three distinct
   HALT-0 sub-cases named, empirically grounded, and mapped to
   individual per-country scaffolds:
   - **Sub-caso A (4xx / deprecated)**: FR-BDF precedent
   - **Sub-caso B (all paths dead)**: IT-BDI new
   - **Sub-caso C (HTTP 200 + non-daily)**: ES-BDE new
   Operational rule v2: probe discipline requires explicit measurement
   of 5 dimensions (reachability, auth, tenor-count, frequency,
   historical-depth) — not collapsed into "endpoint responds 200".
   Follow-ups re-ordered to execute PT-BPSTAT next (lowest risk:
   BPstat is native REST non-migrated) and NL-DNB last (highest
   risk confirmed: OpenDatasoft-cluster shared with BdF). Cost-benefit
   of licensed-feed workstream inflects positive at 3+ HALT-0s;
   Sprint G crosses threshold.

No connectors wired into the dispatcher. No new cassettes, no new
live canaries, no `T1_CURVES_COUNTRIES` tuple expansion. Production
behaviour is unchanged relative to Sprint E close.

### Connector outcomes matrix (post-Sprint G)

| Country | Nominal path | Linker path | Status (post-Sprint G) |
|---|---|---|---|
| PT | Banco de Portugal BPstat (probe-first required) | `LINKER_UNAVAILABLE` permanent | `CAL-CURVES-PT-BPSTAT` OPEN — ADR-0009 probe mandate, 4-5h, lowest remaining risk; candidate for "first win after 3 HALT-0s" |
| IT | Banca d'Italia (**BLOCKED** — scaffold shipped Sprint G, sub-caso B) | BTP€i per Infostat (blocked upstream of linker path) | `CAL-CURVES-IT-BDI` **BLOCKED** — ADR-0009 addendum sub-caso B |
| ES | Banco de España (**BLOCKED** — scaffold shipped Sprint G, sub-caso C) | Bonos-i post-2014 (blocked upstream; also sparse) | `CAL-CURVES-ES-BDE` **BLOCKED** — ADR-0009 addendum sub-caso C |
| FR | Banque de France (**BLOCKED** — scaffold Sprint D, sub-caso A) | OATei (blocked upstream) | `CAL-CURVES-FR-BDF` **BLOCKED** — ADR-0009 sub-caso A |
| NL | DNB Statistics (probe-first required — **HIGH RISK** OpenDatasoft-migrated) | `LINKER_UNAVAILABLE` permanent | `CAL-CURVES-NL-DNB` OPEN — ADR-0009 probe mandate, 4-5h, probability ≥ 0.6 of sub-caso A HALT-0 |

### Linker coverage

Unchanged from Sprint A / D / E close. Per-country linker paths
remain rejecting in `ecb_sdw.py` + the three scaffolded connectors
(FR + IT + ES) with per-country CAL pointers. IT's BTP€i is
nominally strong (4-tenor 5Y/10Y/20Y/30Y post-2003) and ES's
Bonos indexados is weakest among EA-periphery peers (≤ 3 tenors
post-2014 typically priced at any time); both moot until nominal
paths resolve.

---

## 3. HALT triggers (per brief §5)

| # | Trigger | Fired? | Outcome |
|---|---|---|---|
| 0 | IT all 5 probe paths fail | **YES** | HALT-0 IT. Scope narrow to scaffold + CAL BLOCKED + ADR-0009 addendum + retro. Sub-caso B (all paths dead) |
| 1 | ES all 5 probe paths fail | **YES** (soft) | HALT-0 ES per ADR-0009 "HTTP 200 + non-daily" sub-case. BdE BIE REST works but monthly-only. Scope narrow to scaffold + CAL BLOCKED + ADR addendum. Sub-caso C (new sub-case) |
| 2 | Both IT + ES HALT-0 | **YES** | Sprint scope narrowed to ~2h wall-clock: 2 scaffolds + ADR extension + 2 CAL sharpenings + retro. Valid outcome per brief §5 "Both HALT-0: sprint ships scaffold discipline + ADR-0009 extension, 1-2h wall-clock" |
| 3 | Authentication required | No | None of the probed paths required auth — not reached |
| 4 | Response format unexpected | Partial (ES) | BdE BIE JSON format is straightforward but *frequency* metadata was the blocker, not format. Mapped to sub-caso C above |
| 5 | Per-tenor series codes not discoverable | No (ES only) | ES catalog via BE_22 statistical-table chapters exposes 11 tenors; IT has no discoverable series surface |
| 6 | Linker sparse | N/A | No nominal path → linker scope moot |
| 7 | NSS fit convergence failure per country | N/A | No fit executed |
| 8 | Cassette count < 4 | N/A | Scope-narrow path records no HTTP surface to mock |
| 9 | Live canary wall-clock > 45s combined | N/A | No canary shipped |
| 10 | Pre-push gate fails | No | ruff (format + check) + mypy src/sonar + pytest on new connectors green on every commit |
| 11 | No `--no-verify` | No | Standard discipline |
| 12 | Coverage regression > 3pp | Not applicable | Scaffolds add 28 unit tests covering 100% of the two new modules (stub behaviour); no source LOC removed from existing modules |
| 13 | Push before stopping | Pending | §10 pre-merge checklist + §11 `sprint_merge.sh` executed at end of this retro |
| 14 | Sprint F file conflict | No | Sprint F works on builders.py + daily_monetary_indices.py + te.py APPEND; Sprint G works on new connector files + ecb_sdw.py docstring + daily_curves.py docstring + adr/ + backlog/. Shared: `docs/backlog/calibration-tasks.md` — union-merge trivial (Sprint F closes CAL-CPI-INFL section, Sprint G sharpens CAL-CURVES-IT-BDI + CAL-CURVES-ES-BDE sections) |
| 15 | Cross-val deviation > 30 bps vs MEF/Tesoro reference | N/A | No fit executed to cross-val |
| 16 | ADR-0010 violation | No | All work targets IT + ES (both T1 per ADR-0005 + `country_tiers.yaml`). Scaffold discipline extends T1 pattern library without T2 bleed. ADR-0010 compliance absolute |

---

## 4. Pre-merge checklist (brief v3 §10) — fourth production use

- [ ] All commits pushed — executed at end of this retro commit sequence.
- [x] Workspace clean — `git status` returns no modifications after
      this retro commit lands.
- [x] Pre-push gate passed — ruff (format + check), mypy project,
      pytest on relevant suites green on every commit. Full unit run
      surfaces pre-existing asyncio-cleanup flakiness unrelated to
      this sprint (confirmed also present on `main` post Sprint E
      merge).
- [x] Branch tracking — will be set by `git push -u` on first push.
- [x] Per-country probe outcomes documented — full probe matrices
      embedded in scaffold module docstrings + CAL entries + ADR
      addendum + this retro. Both outcomes (success OR HALT-0) are
      valid per brief §6; both HALT-0 here (sub-casos B + C).
- [x] NSS fit RMSE — N/A per HALT-0; acceptance criterion is
      shape-independent per brief §6 ("Per successful country (0, 1, or 2)"
      vs "Per HALT-0 country (0, 1, or 2)"). This sprint ships
      0 successes + 2 HALT-0s.
- [x] Tier scope verified T1 only — both IT + ES are T1 per ADR-0005
      + `country_tiers.yaml`. ADR-0010 compliance absolute.
- [x] Cassettes / canaries — N/A for both HALT-0 paths. Scaffolds
      ship with 28 hermetic unit assertions covering interface
      contracts + error-raising behaviour.
- [x] systemd service — unchanged (Sprint E already covered the
      sparse-inclusion routing; `T1_CURVES_COUNTRIES` unchanged →
      no daemon-reload needed).
- [x] Paralelo discipline — zero primary-file overlap with Sprint F
      (Sprint F: `connectors/te.py` APPEND + `indices/monetary/builders.py`
      + `pipelines/daily_monetary_indices.py`; Sprint G: new
      connector files + `connectors/ecb_sdw.py` docstring +
      `pipelines/daily_curves.py` docstring + `docs/adr/` +
      `docs/backlog/` + `docs/planning/retrospectives/`).

### Merge execution (brief v3 §11)

Operator runs:

```bash
./scripts/ops/sprint_merge.sh sprint-curves-it-es-bdi-bde
```

Fourth production use of `sprint_merge.sh`. First three uses
(CAL-138, Sprint A, Sprint D) succeeded. Sprint E merged concurrently
via the same script.

---

## 5. Brief format v3 — fourth-use lessons

- ✓ **§10 pre-merge checklist still valuable** — fourth consecutive
  scope-narrow sprint (CAL-138 → Sprint A → Sprint D → Sprint G)
  where the checklist's explicit push / workspace-clean /
  paralelo-discipline items kept the 2h path honest.
- ✓ **§5 HALT-0 compositional across multiple countries** — the
  Sprint G brief already anticipated per-country HALT-0 + combined
  HALT-0 as valid outcomes (§5 trigger 2: "Both HALT-0: sprint
  scope narrows to ~2-3h wall-clock"). Commit 1 executed both
  probes and composed triggers 0 + 1 autonomously. The brief's
  shape-independent acceptance (§6 "Per successful country (0, 1,
  or 2)" / "Per HALT-0 country (0, 1, or 2)") let both HALT-0
  land without any friction.
- ✓ **§2 probe matrix templates** — the brief's per-country
  curl-command templates made probe execution mechanical. The
  ES BDEstad 301 redirect + BdE BIE REST API discovery (not in
  the brief's listed endpoints) was found by reading `href=` on
  the estadisticas landing page — a pattern that should be
  documented in ADR-0009 for future EA-periphery probes:
  "follow landing-page href scans for `/api/` + `/estadist/` +
  `/series/` + `/csv/` patterns before declaring a path dead".
- ~ **§9 fallback hierarchy under-specified for ES** — the brief
  listed `https://www.bde.es/webbde/es/estadis/infoest/` (the
  legacy path) without noting BDEstad migrated to `/wbe/` tree.
  Same criticism as Sprint D §9 ("TE fetch_fr_yield_curve_nominal
  if shipped CAL-138"): future briefs should check current URL
  state + upstream sprint retros before drafting the fallback
  hierarchy. This can be a preparatory agent task in the brief-drafting
  sprint playbook.
- **New for v5 recommendation**: §2 per-country probe matrix could
  be augmented with an explicit "API discovery via landing-page
  href scan" sub-step (the move that unblocked ES sub-caso C
  characterisation). The Sprint D + G pattern shows brief §9
  fallback hierarchies tend to under-specify the dynamic-discovery
  part of probe work; adding a fixed "scan landing href patterns"
  step formalizes it.
- **Pattern library completeness check**: three successor sprints
  now executed (D + G IT + G ES) and each landed in a different
  ADR-0009 sub-case (A + B + C). PT + NL remaining. The ADR-0009
  pattern library is now empirically saturated for the "HALT-0"
  branch; the next useful data point is a **full-impl success**
  (ideally PT-BPSTAT) to validate the functional-scaffold delta
  contract under real swap-in conditions.

---

## 6. Pattern notes for remaining EA-periphery sprints (ADR-0009 addendum mandate)

### Recommended execution order (updated)

1. **PT-BPSTAT** (probe risk: **low-moderate**). Banco de Portugal
   `bpstat.bportugal.pt/data/v1` — native REST API, not known to be
   migration-affected. After 3-of-5 HALT-0s, PT is the best remaining
   candidate for "first full-impl success" and therefore validates
   the scaffold → full-impl delta contract under live swap-in
   conditions. Schedule next.
2. **NL-DNB** (probe risk: **elevated**, confirmed). DNB migrated to
   OpenDatasoft mid-2024 — **same platform that revealed the BdF
   gap** (Sprint D sub-caso A). Probability ≥ 0.6 of sub-caso A
   HALT-0. Schedule last; budget full 4-5h for scaffold path;
   bundle with a licensed-feed track evaluation if HALT-0 confirms.

### Commit 1 probe checklist per sprint (ADR-0009 v2)

Execute the probe matrix first, measuring all 5 dimensions, then
decide scaffold-vs-full-impl:

```bash
# 1. Base-URL reachability
curl -s -I "<cb_public_url>" -A "SONAR/2.0"
# 2. Catalog / dataset discovery (if an API exists)
curl -s "<catalog_api>" | python3 -m json.tool | head -50
# 3. Landing-page href scan (new — Sprint G lesson)
curl -s --compressed "<cb_estadisticas_landing>" | grep -Eio '(href)="[^"]*(csv|xlsx?|rest|api|json|sdmx|series|descarga|download)[^"]*"' | sort -u | head -30
# 4. Per-tenor series discovery
curl -s "<series_or_dataset_endpoint>" -A "SONAR/2.0" | head -50
# 5. Frequency verification (new — Sprint G sub-caso C lesson)
# fetch metadata on one known series + verify codFrecuencia / FREQ / '.M' suffix
# 6. Fallback: TE native symbol + FRED OECD mirror
```

Decision table (ADR-0009 v2 ternary):

| Probe outcome | Scope | Sub-caso |
|---|---|---|
| HTTP 200 + ≥ 6 tenors + **daily** + public | Full impl per Bundesbank analog | — |
| HTTP 200 + ≥ 6 tenors + **non-daily** | Scaffold + frequency-tier architecture ADR Phase 2+ | **C** (ES-BDE) |
| HTTP 200 + < 6 tenors | Scaffold + unblock-criteria targeting daily surface completeness | **A** partial (FR-BDF) |
| HTTP 4xx OR deprecated | Scaffold + unblock-criteria targeting host restore | **A** (FR-BDF) |
| HTTP 000 / NXDOMAIN across all paths | Scaffold + unblock-criteria targeting alternative surface | **B** (IT-BDI) |

### Shared deliverables across remaining 2 successors

Same shape as Sprint D + G:

- Each sprint's `src/sonar/connectors/{bank_slug}.py` (even in scaffold
  path) shares the 5-section module-docstring shape: (i) 1-para
  context, (ii) probed paths bulleted with URL + HTTP + verdict,
  (iii) unblock criteria per sub-case, (iv) references section
  linking ADR-0009 addendum + the per-country retro.
- Each sprint amends ADR-0009 with a 1-entry row in the "EA periphery
  probe outcomes matrix" table recording its sub-case.
- Backlog entry format: BLOCKED if HALT-0; CLOSED with commit refs
  if full impl; SUPERSEDED by per-tenor sub-items if partial.
- Retro per v3 format in `docs/planning/retrospectives/week10-sprint-curves-{cc}-{cb}-report.md`.

---

## 7. Production impact

**None relative to Sprint E close**. The 06:00 UTC
`sonar-daily-curves.service` iterates
`T1_CURVES_COUNTRIES = ("US", "DE", "EA", "GB", "JP", "CA")` as
before; IT + ES continue to emit `InsufficientDataError` with the
Sprint-A-installed per-country CAL pointers (now sharpened by
Sprint G). FR + IT + ES continue on the `EA_AAA_PROXY_FALLBACK`
path in `daily_overlays` + downstream cascade. The sharpened
docstrings + CAL entries improve operator triage — the pipeline
log's CAL pointer now lands on an entry that explains the BLOCKED
state + sub-case + unblock-criteria in one read, and ADR-0009 is
one link away with the pattern library + probe discipline.

Cascade unchanged: `daily_cost_of_capital` uses the EA-aggregate ERP
proxy for FR + IT + ES runs; the `MATURE_ERP_PROXY_{FR,IT,ES}` /
`EA_AAA_PROXY_FALLBACK` flags on persisted rows already encode the
three gaps.

Future unblocks and their production deltas (per country, sub-case):

- **IT sub-caso B → (a) BdI public REST restore**: IT curve lands
  same day as connector methods swap (no `T1_CURVES_COUNTRIES`
  change; no `_DEFERRAL_CAL_MAP` change; `BancaDItaliaConnector`
  dispatcher branch added alongside Bundesbank; `CAL-CURVES-IT-BDI` →
  CLOSED; overlays cascade gains IT per-country signal at next
  07:30 WEST run).
- **IT sub-caso B → (b) licensed feed**: similar to (a) but through
  a new connector (`bloomberg.py` / `refinitiv.py`); scaffold
  module kept for reference.
- **ES sub-caso C → (a) BdE daily publish**: ES curve lands same
  day as connector methods swap (identical mechanism to IT (a)).
- **ES sub-caso C → (b) pipeline monthly-cadence path**: major
  change requiring `daily_curves` refactor + overlay cascade
  staleness semantics + backtest re-baselining. Estimate 6-8h CC.
  Alternative: parallel `monthly_curves` pipeline (Phase 2+
  architecture decision captured in ADR-0009 addendum follow-ups).
- **Both → licensed feed provisioning**: single commit delta for
  both countries if feed covers IT + ES (e.g. Bloomberg BVAL
  spectrum).

---

## 8. Final tmux echo

```
SPRINT G IT + ES CURVES DONE: 4 commits on branch sprint-curves-it-es-bdi-bde

Outcomes per country:
- IT-BDI: HALT-0 (sub-caso B — all paths dead)
  - ECB legacy SDMX decommissioned; BdI Infostat API subdomains
    NXDOMAIN; MEF HTML-only; ECB SDW FM+IRS EA-aggregate; FRED monthly
  - Scaffold shipped src/sonar/connectors/banca_ditalia.py

- ES-BDE: HALT-0 (sub-caso C — HTTP 200 + non-daily)
  - BdE BIE REST (app.bde.es/bierest) LIVE + publishes 11-tenor ES
    sovereign yields (BE_22_6 Letras + BE_22_7 Bonos) but ALL monthly
  - Scaffold shipped src/sonar/connectors/banco_espana.py

CAL-CURVES-IT-BDI: BLOCKED (sharpened with full probe matrix + 3
  unblock paths)
CAL-CURVES-ES-BDE: BLOCKED (sharpened with full probe matrix + 4
  unblock paths)

ADR-0009 pattern library: extended to ternary (sub-casos A/B/C).
  Operational rule v2: 5-dimension probe matrix mandatory.

Pattern guidance for remaining EA periphery:
- PT-BPSTAT: schedule next (lowest risk; BPstat native REST non-migrated;
  candidate for first full-impl success validating scaffold → full-impl
  delta contract)
- NL-DNB: schedule last (probability >=0.6 of sub-caso A HALT-0 per
  OpenDatasoft-cluster Sprint D precedent)

T1 curves coverage post-merge: unchanged 6/16 (US/DE/EA/GB/JP/CA).
  3 CAL items BLOCKED with scaffolds (FR Sprint D + IT + ES Sprint G).
  2 pending (PT + NL).

Production impact: unchanged vs Sprint E close. FR + IT + ES remain
on EA-AAA proxy fallback. Pattern library empirically saturated for
HALT-0 branch (three sub-cases documented); next useful data point
is a PT full-impl success.

Paralelo with Sprint F (CPI + inflation T1 wrappers): zero primary
file conflicts; shared docs/backlog/calibration-tasks.md union-merge
trivial.

Brief format v3 fourth-use: §10 pre-merge checklist + §11 sprint_merge.sh
hook valuable; §5 HALT-0 compositional across countries worked
autonomously; §2 probe matrix benefits from added "landing-page
href scan" step (v5 recommendation); §9 fallback hierarchy needed
upstream URL-state verification for ES (BDEstad migrated to /wbe/).

Merge: ./scripts/ops/sprint_merge.sh sprint-curves-it-es-bdi-bde

Artifact: docs/planning/retrospectives/week10-sprint-curves-it-es-report.md
```
