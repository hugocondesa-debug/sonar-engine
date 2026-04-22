# Week 10 Day 3 Sprint A — CAL-CURVES-EA-PERIPHERY (superseded) Retrospective

**Sprint**: A — Week 10 Day 3 CAL-CURVES-EA-PERIPHERY (5 EA periphery members via ECB SDW extension).
**Branch**: `sprint-curves-ea-periphery`.
**Worktree**: `/home/macro/projects/sonar-wt-curves-ea-periphery`.
**Brief**: `docs/planning/week10-sprint-a-ea-periphery-brief.md` (format v3 — second production use).
**Duration**: ~1.5h CC (single session 2026-04-22, well under the 4-5h budget because HALT-0 + HALT-1 fired in Commit 1's pre-flight probe).
**Commits**: 2 substantive + this retro = 3 total (vs. brief's 5-7 target).
**Outcome**: Ship docs-only via scope narrow per HALT-0 + HALT-1 — zero country connectors added; umbrella CAL decomposed into five per-country items each tracked individually.

---

## 1. Commit inventory

| # | SHA | Subject | Scope |
|---|---|---|---|
| 1 | `85ffeb2` | feat(connectors): ECB SDW sharpen EA periphery deferrals per 2026-04-22 probe | Module-docstring empirical findings + `PERIPHERY_CAL_POINTERS` + per-country CAL pointer in ecb_sdw/daily_curves/te error messages + updated unit + integration tests |
| 2 | `dd44247` | docs(backlog): supersede CAL-CURVES-EA-PERIPHERY with 5 per-country items | Umbrella marked SUPERSEDED with original scope preserved; five new CAL entries (PT/IT/ES/FR/NL) with per-country national-CB data paths + estimates + priority ordering |
| 3 | (this commit) | docs(planning): Week 10 Sprint A EA periphery retrospective | — |

---

## 2. Scope outcome vs brief

### Brief's ambition (§1 Scope)

Five EA periphery member curves (PT/IT/ES/FR/NL) via ECB SDW connector extension, mirroring CAL-138's DE pattern. T1_7_COUNTRIES tuple expansion + dispatcher routing + cassettes + live canaries + CAL closure.

### Empirical reality (Commit 1 probes)

The Commit 1 pre-flight re-ran the ECB SDW probes across `YC`, `FM`, and `IRS` dataflows:

| Dataflow | `REF_AREA` coverage | Tenors per PT/IT/ES/FR/NL | Fit-viable? |
|---|---|---|---|
| `YC`  | `{U2}` only (confirmed by 10 824-row dump filtered) | 0 | No (HALT-0 trigger) |
| `FM`  | `{U2, DK, GB, JP, SE, US}` (confirmed via `lastNObservations=1` dump across all 115 series) | 0 | No (HALT-1 trigger — the brief's fallback path fails) |
| `IRS` | All 19 EA members including PT/IT/ES/FR/NL, monthly 10Y Maastricht convergence rate | 1 (single 10Y point) | No (`MIN_OBSERVATIONS=6` for NSS) |

CAL-138 retro already documented the `YC` finding. Sprint A's probe contribution is confirming the `FM` fallback is equally empty for periphery — which the brief's HALT-0 had assumed would work. With both primary and fallback empirically infeasible, the only remaining path is national-CB connectors (analog to `BundesbankConnector` for DE). That is out of scope for a 4-5h sprint that assumed a shared-connector extension.

### Scope-narrow delivery

Per the CAL-138 HALT-1 precedent ("Future briefs should phrase acceptance in shape-independent terms so scope-narrow does not break the checklist"), Sprint A ships:

1. **Connector-surface documentation of the empirical finding** — `ecb_sdw.py` module docstring now captures the 2026-04-22 probe verdict explicitly, with a new `PERIPHERY_CAL_POINTERS` module constant and sharpened per-country error messages (`fetch_yield_curve_nominal` / `fetch_yield_curve_linker`) that cite the specific per-country CAL for PT/IT/ES/FR/NL.
2. **Pipeline deferral map update** — `daily_curves._DEFERRAL_CAL_MAP` routes each periphery country to its per-country CAL item instead of the umbrella.
3. **CAL supersession** — `CAL-CURVES-EA-PERIPHERY` marked SUPERSEDED in the backlog (original scope preserved); five successor CAL items opened with per-country data paths, estimates (3-4h each), priority ranking (FR pilot → IT → ES → PT → NL), and linker-scope absorption.

No country connectors ship. No new cassettes, no new live canaries, no tuple expansion. Production behaviour is unchanged relative to CAL-138 close.

### Connector outcomes matrix

| Country | Nominal path | Linker path | Status (post Sprint A) |
|---|---|---|---|
| PT | Banco de Portugal BPstat (deferred) | LINKER_UNAVAILABLE permanent | `CAL-CURVES-PT-BPSTAT` open |
| IT | Banca d'Italia BDS (deferred) | BTP€i via BDS (deferred) | `CAL-CURVES-IT-BDI` open |
| ES | Banco de España SeriesTemporales (deferred) | Bonos-i post-2014 (deferred) | `CAL-CURVES-ES-BDE` open |
| FR | Banque de France Webstat (deferred, **pilot**) | OATei via Webstat (deferred) | `CAL-CURVES-FR-BDF` open — priority |
| NL | DNB Statistics (deferred) | LINKER_UNAVAILABLE permanent | `CAL-CURVES-NL-DNB` open |

### Linker coverage

Unchanged from CAL-138 close. `fetch_yield_curve_linker` remains rejecting for all periphery countries; the error message now cites the per-country CAL rather than the umbrella. PT and NL are annotated as permanent `LINKER_UNAVAILABLE` (no public indexed-bond universe); FR/IT/ES carry partial linker programmes folded into their respective per-country sprints.

---

## 3. HALT triggers

| # | Trigger | Fired? | Outcome |
|---|---|---|---|
| 0 | ECB SDW YC dataflow lacks per-country | **YES** | Confirmed via `YC?startPeriod=…` REF_AREA dump — only `U2`. Triggered fallback to FM probe (brief §2 pre-flight step 4) |
| 1 | Any country lacks ≥ 6 tenors | **YES (all 5)** | FM dataflow REF_AREA probe: {U2, DK, GB, JP, SE, US} — zero EA periphery. IRS dataflow gives 1 point (10Y) per country, below MIN_OBSERVATIONS. Neither brief path is feasible |
| 2 | Linker universally unavailable | N/A | No connectors shipped — linker paths absorbed into per-country successor CALs |
| 3 | ECB SDW rate limits | No | Probes under 30 requests total |
| 4 | Sprint B file conflict | No | Zero primary-file overlap; paralelo discipline held (Sprint B still in flight on `sonar-wt-erp-t1`) |
| 5 | NSS fit convergence failure | N/A | No NSS fits run |
| 6 | Cassette count < 10 | N/A | Zero cassettes — scope-narrow path does not ship connector HTTP surface (nothing to record) |
| 7 | Live canary wall-clock > 40s | N/A | Zero canaries |
| 8 | Pre-push gate fails | No | `ruff format --check` / `ruff check` / `mypy src/sonar` / `pytest tests/unit/test_connectors/test_ecb_sdw.py tests/unit/test_connectors/test_te.py tests/integration/test_daily_curves_multi_country.py -m "not slow and not live"` all green across both commits |
| 9 | No `--no-verify` | No | Standard discipline |
| 10 | Coverage regression > 3pp | Not applicable | No source LOC added to covered modules (error-message branches are covered by the new parametrised unit tests) |
| 11 | Push before stopping | Pending | §10 pre-merge checklist + §11 `sprint_merge.sh` executed after this retro |

---

## 4. Pre-merge checklist (brief v3 §10) — second production use

- [ ] All commits pushed — executed at end of this retro commit sequence.
- [x] Workspace clean — `git status` returns no modifications after Commit 3 lands.
- [x] Pre-push gate passed — ruff (format + check), mypy project, pytest on all touched test files green on every commit.
- [x] Branch tracking — will be set by `git push -u` on first push (confirmed worktree branch is `sprint-curves-ea-periphery`).
- [x] Cassettes / canaries — N/A for scope-narrow path; brief's §6 cassette + canary counts assumed 5 country connectors which HALT-1 invalidated.
- [x] systemd service — unchanged (CAL-138 already flipped `--all-t1`; T1_7 tuple unchanged so no daemon-reload needed).
- [x] Paralelo discipline — zero file overlap with Sprint B (`src/sonar/overlays/erp/` is Sprint B's primary scope; this sprint only touched connectors + pipelines + backlog + planning).

### Merge execution (brief v3 §11)

Operator runs:

```bash
./scripts/ops/sprint_merge.sh sprint-curves-ea-periphery
```

Second production use of `sprint_merge.sh`. First use (CAL-138) succeeded.

---

## 5. Brief format v3 — second-use lessons

- ✓ **§10 pre-merge checklist still valuable** — forcing explicit push / workspace-clean / service-update / paralelo discipline confirmation is exactly what kept the 1.5h path honest instead of drifting into speculative connector stubs.
- ✓ **§5 HALT triggers 0 + 1 composed cleanly** — the brief already anticipated the "YC lacks per-country → scope narrow to FM + SONAR NSS fit" path; the probe simply invalidated that fallback too, which HALT-1 ("any country lacks ≥ 6 tenors → skip per CAL-138 precedent") absorbed without needing a bespoke response.
- ~ **§6 acceptance criteria still scope-fixed** — 5 connector extensions / 10+ cassettes / 5+ canaries / tuple expansion. Same criticism as the CAL-138 retro: future briefs want outcome-based phrasing ("at least one country shipped **or** per-country CAL items opened with data paths") to survive probe-invalidation cleanly.
- **New for v4 recommendation**: §2 "Pre-flight requirement" should explicitly enumerate the **probe outcomes that each block the brief's primary / fallback / scope-narrow paths**. Sprint A's pre-flight hit the brief's pre-flight checklist but the brief didn't spell out "if FM per-country coverage is also empty, the fallback path is dead → decompose umbrella CAL". A v4 pre-flight table could have each probe row flagged with the outcome it enables or rules out.

---

## 6. Production impact

**None relative to CAL-138 close**. The 06:00 UTC `sonar-daily-curves.service` iterates `T1_7_COUNTRIES = ("US", "DE", "PT", "IT", "ES", "FR", "NL")` as before; PT/IT/ES/FR/NL continue to emit `InsufficientDataError` with (now per-country) CAL pointers. `daily_overlays` stays on `EA_AAA_PROXY_FALLBACK` for the periphery members until the first per-country connector lands (FR-BDF pilot is the priority).

The sharper CAL pointers improve operator triage — the structlog warning now cites `CAL-CURVES-FR-BDF` for FR instead of the umbrella, so the next unblocking sprint is one CAL lookup away in the backlog.

---

## 7. Final tmux echo

```
SPRINT A EA PERIPHERY DONE: 3 commits on branch sprint-curves-ea-periphery

Countries shipped: 0 of 5 (scope-narrow per HALT-0 + HALT-1).
Outcome: empirical finding + umbrella CAL decomposition.

Pre-flight probe findings (Commit 1 body):
- ECB SDW YC dataflow: REF_AREA = {U2} only
- ECB SDW FM dataflow: REF_AREA in {U2, DK, GB, JP, SE, US} — no
  EA periphery sovereign series
- ECB SDW IRS dataflow: monthly 10Y Maastricht convergence rate
  per country (insufficient for NSS MIN_OBSERVATIONS=6)

Empirical conclusion: PT/IT/ES/FR/NL require national-CB
connectors (BundesbankConnector analog). Out of scope for a
4-5h ECB-SDW-extension sprint.

CAL closures + openings:
- CAL-CURVES-EA-PERIPHERY  SUPERSEDED (original scope preserved)
- CAL-CURVES-FR-BDF        OPEN (pilot — 3-4h)
- CAL-CURVES-IT-BDI        OPEN (3-4h)
- CAL-CURVES-ES-BDE        OPEN (3-4h)
- CAL-CURVES-PT-BPSTAT     OPEN (3-4h; LINKER_UNAVAILABLE perm)
- CAL-CURVES-NL-DNB        OPEN (3-4h; LINKER_UNAVAILABLE perm)

Connector-surface sharpening:
- sonar.connectors.ecb_sdw.PERIPHERY_CAL_POINTERS constant added
- fetch_yield_curve_nominal + fetch_yield_curve_linker cite the
  per-country CAL for PT/IT/ES/FR/NL
- daily_curves._DEFERRAL_CAL_MAP routes per-country
- tests: 10 new parametrised unit assertions on the error path;
  integration periphery dispatch test updated to expect
  per-country pointer

HALT triggers fired: 0 + 1. Composed cleanly per CAL-138 precedent;
scope narrowed autonomously within brief §5 + CLAUDE.md §11
("Hugo é juiz, nunca inventar").

Brief format v3 second-use: §10 pre-merge checklist + §11
sprint_merge.sh hook both valuable; §6 acceptance criteria
still scope-fixed — same v4 recommendation as CAL-138 retro.

Production impact: unchanged vs CAL-138 close. FR-BDF is the
pilot — first per-country national-CB connector ships against
CAL-CURVES-FR-BDF next (budget 3-4h CC, standalone sprint).

Paralelo with Sprint B ERP: zero file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-curves-ea-periphery

Artifact: docs/planning/retrospectives/week10-sprint-ea-periphery-report.md
```
