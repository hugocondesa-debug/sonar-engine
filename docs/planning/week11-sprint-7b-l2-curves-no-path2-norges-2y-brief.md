# Sprint 7B — NO 2Y curves Path 2 via Norges Bank DataAPI (CAL-CURVES-NO-PATH-2)

**Tier scope**: T1 ONLY per ADR-0010 (1 país: NO).
**Pattern reference**: ADR-0009 v2.3 — Path 2 entry post-TE-exhaustion confirmed × 3 (Sprint T-Retry + Sprint 5B + cumulative).
**Predecessor success**: Sprint X-NO (Week 9) shipped NorgesBankConnector live for M1; this sprint extends it to curves L2.

---

## 1. Scope

**In**:
- Probe Norges Bank DataAPI `GOVT_GENERIC_RATES` dataflow for 2Y NOK government bond yield
- Endpoint pattern (existing connector convention): `https://data.norges-bank.no/api/data/GOVT_GENERIC_RATES/B.2Y.GBON`
- If 2Y returns observations: extend `NorgesBankConnector` with `fetch_govt_yield(tenor)` method (parameterised by tenor: 2Y, 10Y already live for M4 FCI scaffold)
- Integrate NO into `nss_curves_backfill.py` cohort with NorgesBank as Path 2 source (cascade: TE primary 3 tenors → Norges Bank Path 2 fill 2Y → combine for NSS-degraded fit if 2Y+10Y available; per Hugo NSS criterion 2Y+10Y mandatory rest nice-to-have)
- Update `country_tiers.yaml` NO `curves_path_2_pending: true` → `curves_live: true` (or equivalent flag matching Sprint 5A AU precedent)

**Out**:
- 3Y/5Y/7Y/15Y/20Y/30Y NO tenors (Norges Bank may have additional `GOVT_GENERIC_RATES` keys but mid-curve completeness deferred)
- NSS Svensson 6-tenor floor revision (separate Sprint 7A spec amendment)
- Other Path 2 cohort países (NL/NZ/CH/SE) — separate sprints
- M4 FCI NO upgrade (deferred Sprint X-NO follow-up)

---

## 2. Spec reference + pre-flight

**Authoritative**:
- `src/sonar/connectors/norgesbank.py` (existing live connector, M1 production usage; module docstring lines 1-40 documents `GOVT_GENERIC_RATES / B.10Y.GBON` confirmed live)
- `docs/specs/overlays/nss-curves.md` (NSS methodology + Path 2 cascade integration)
- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` v2.3 (Path 2 discipline — empirical TE exhaustion documented × 3 for NO)
- `docs/backlog/calibration-tasks.md` `CAL-CURVES-NO-PATH-2` (this sprint closes it)
- `tests/unit/test_connectors/test_norgesbank.py` (extension pattern)
- `tests/integration/test_daily_monetary_no.py` (live canary pattern)
- Norges Bank DataAPI public docs: `https://data.norges-bank.no/`

**Pre-flight HALT #0 requirement** (mandatory Commit 1):

CC reads end-to-end:
1. norgesbank.py module docstring (`GOVT_GENERIC_RATES` shape + dimensions)
2. ADR-0009 v2.3 Path 2 discipline
3. CAL-CURVES-NO-PATH-2 entry (closure conditions)
4. nss_curves_backfill.py existing per-country flow (Sprint H/I/M precedent)

**Path 2 probe binary HALT condition**:
- 2Y endpoint `GOVT_GENERIC_RATES/B.2Y.GBON` returns observations → SHIP NSS-degraded NO live
- 2Y endpoint empty / 404 / dimension key invalid → HALT-0 → close CAL-CURVES-NO-PATH-2 as **EXHAUSTED** (Norges Bank confirmed sparse) → file CAL-CURVES-NO-2Y-MISSING for tracking

---

## 3. Concurrency

**Single CC sequential** — no worktree split. Small scope.

**File-level isolation**: not applicable.

**Migration numbers**: NONE expected (data + code only).

---

## 4. Commits

Target ~4-5 commits:

1. **Pre-flight audit** — connector docstring + ADR + CAL reads + Path 2 probe rationale + plan
2. **Norges Bank 2Y probe** — exploratory Norges Bank DataAPI call to `GOVT_GENERIC_RATES/B.2Y.GBON` (one-off script or test) + result reported in commit body verbatim
3. **Connector extension** (only if 2Y available): `NorgesBankConnector.fetch_govt_yield(tenor)` method generic + tests + cassette + live canary
4. **Pipeline integration** (only if 2Y available): nss_curves_backfill.py NO Path 2 cascade entry + RMSE report against TE 3 tenors + Norges Bank 2Y combined
5. **Docs closure**: country_tiers.yaml flag + nss-curves.md country scope appendix update + CAL-CURVES-NO-PATH-2 closed (or amended to EXHAUSTED) + Sprint 7B retrospective

If HALT-0 fired (2Y empty), Commits 3-4 skip; Commit 5 covers docs + retro only.

---

## 5. HALT triggers (atomic)

0. **Pre-flight HALT #0 fail** — connector existing API contract regression OR Norges Bank DataAPI down → HALT, document
1. **2Y endpoint empty / 404 / key invalid** → BINARY HALT — close CAL-CURVES-NO-PATH-2 EXHAUSTED, document Norges Bank sparsity, NO confirmed Path 2 limitation
2. **NSS RMSE > 5bps** post-fit → HALT-0, document fit quality issue
3. **Coverage regression > 3pp** in tests → HALT (no `--no-verify`)
4. **Pre-push gate fail** → fix, no `--no-verify`

---

## 6. Acceptance

**Binary outcome**:

**Path A — 2Y available (success)**:
- [ ] NorgesBankConnector.fetch_govt_yield(tenor) method shipped + tested + cassette
- [ ] NSS-degraded fit NO ships with 2Y+10Y minimum (per Hugo criterion) plus available TE tenors (6M, 1Y if combinable)
- [ ] RMSE ≤ 5bps reported
- [ ] country_tiers.yaml NO flag updated to curves_live
- [ ] nss-curves.md §10 country scope NO row updated
- [ ] CAL-CURVES-NO-PATH-2 closed
- [ ] daily-curves pipeline includes NO post-merge
- [ ] T1 curves coverage 11/16 → 12/16

**Path B — 2Y unavailable (limitation confirmed)**:
- [ ] Norges Bank DataAPI 2Y empty result documented verbatim in Commit 2 body + retrospective
- [ ] CAL-CURVES-NO-PATH-2 amended to EXHAUSTED status
- [ ] CAL-CURVES-NO-2Y-MISSING filed for future tracking (low priority — likely permanent data limitation)
- [ ] country_tiers.yaml NO flag stays curves_path_2_pending OR updates to curves_path_2_exhausted

**Sprint-end (both paths)**:
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] Sprint 7B retrospective shipped

---

## 7. Report-back artifact

Path: `docs/planning/retrospectives/week11-sprint-7b-l2-curves-no-path2-norges-2y-report.md`

Structure:
- Sprint metadata (CC duration, commits, path A or B outcome)
- Probe matrix Norges Bank 2Y verbatim API response + tenor coverage
- If Path A: NSS RMSE table + connector cassettes inventory
- If Path B: limitation rationale + Norges Bank statistics portal observation (manual confirmation ad-hoc — operator may verify post-sprint)
- CAL closures + new CALs filed
- Pattern observations Path 2 vs Sprint M/I (TE) cascade

---

## 8. Notes on implementation

- Existing `B.10Y.GBON` confirmed live per module docstring; tenor dimension is `2Y` per Norges Bank SDMX convention (2-char code)
- Series key pattern observed: `B.{TENOR}.GBON` for `GOVT_GENERIC_RATES` dataflow; tenor encoding likely `2Y` literal but probe must confirm (could be `02Y` zero-padded)
- Connector extension keeps `fetch_govt_yield(tenor)` generic — accepts string tenor + maps to API key; existing `fetch_policy_rate()` pattern reusable
- M4 FCI NO 10Y already in CAL-NO-M4-FCI scope (deferred Sprint X-NO follow-up); this sprint's 2Y addition complements that future M4 work
- Sustainable pacing: target ~2-4h wall-clock single CC (existing infrastructure accelerates significantly vs greenfield Path 2)
