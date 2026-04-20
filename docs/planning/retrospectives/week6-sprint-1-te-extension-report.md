# Week 6 Sprint 1 — TE Pro Extension (Fallback for FRED Delisted + DE Sentiment)

**Brief:** `docs/planning/week6-sprint-1-te-extension-brief.md`
**Duration:** ~2h (2026-04-20)
**Commits:** 5 (c4 telemetry integrated into c1; see §9)
**Status:** SPRINT CLOSED

---

## 1. Summary

Extended `connectors/te.py` with a generic indicator fetcher +
country-name map + 5 CAL-targeted convenience wrappers, then wired it
into the E4 Sentiment builder as a secondary source for the series
FRED delisted (US ISM Mfg, ISM Svc, NFIB) and for DE-specific sentiment
(Ifo + ZEW). Live integration smoke confirms the quality uplift:

- US E4: 6/13 components → **≥ 9/13** with TE fallback
- DE E4: 3/13 components → **≥ 5/13** with TE fallback

Pre-flight probe closed one CAL empirically without code: TE's US
"Consumer Confidence" series is sourced from University of Michigan,
not Conference Board. Wiring it would double-count the UMich slot, so
CAL-093 closes as "not resolvable by TE" (staleness accepted).

## 2. Commits

| # | SHA | Title | Gate |
|---|-----|-------|------|
| 1 | `a2b86a6` | feat(connectors): TE generic indicator fetcher + country map + call counter | green |
| 2 | `d1cd3ac` | feat(connectors): TE convenience wrappers per CAL-092/086 | green |
| 3 | `8e59498` | feat(indices): E4 Sentiment builder TE fallback wiring | green |
| 4 | _folded into c1_ | TE call counter + telemetry (see §9) | n/a |
| 5 | `1d9b032` | test(integration): E4 Sentiment with TE fallback US + DE live smoke | green |
| 6 | _this doc_ | docs(planning): retrospective + close CAL-092/086/093 | pending |

Pre-push gate (`ruff format --check + ruff check + mypy + pytest`) ran
clean before every push. No `--no-verify`. Concurrent MSC brief in
tmux `sonar-l3` leaked 3 untracked files into ruff scope late in C2;
scoped my gate to `src/sonar/connectors src/sonar/indices/economic` +
`tests/unit/{test_connectors,test_indices/economic}` per Sprint 1
concurrency precedent. Full-project mypy stayed green.

## 3. CAL resolutions

### Closed this sprint

- **CAL-092** — FRED ISM/NFIB delisted fallback. TE fetches both
  PMIs + NFIB live; CAL-082 (direct ISM scraper) + CAL-091 (NFIB
  scraper) become unnecessary as long as TE Pro access holds.
- **CAL-086** — DE Ifo + ZEW sentiment. TE fetches both live;
  dedicated `connectors/{zew,ifo}.py` scrapers become unnecessary.
- **CAL-093** — Conference Board Consumer Confidence. **Closed as
  not-resolvable-by-TE**. TE's US "Consumer Confidence" is UMich-
  sourced; substituting would double-count. OECD CLI stale proxy
  stays in place for the CB slot. Re-open if/when a true CB feed
  (Nasdaq Data Link, scrape with ToS review) surfaces.

### Opened this sprint

None. All findings tracked within the existing CAL items or absorbed
into retrospective notes.

## 4. TE indicator coverage validation

| CAL slot | TE country | TE indicator | Source (TE field) | Validated |
|----------|-----------|--------------|-------------------|-----------|
| US ISM Mfg | `united states` | `business confidence` | ISM | live canary + cassette |
| US ISM Svc | `united states` | `non manufacturing pmi` | ISM | cassette |
| US NFIB | `united states` | `nfib business optimism index` | NFIB | cassette |
| US Consumer Confidence | `united states` | `consumer confidence` | **UMich (not CB)** | cassette — see CAL-093 note |
| DE Ifo Business Climate | `germany` | `business confidence` | Ifo Institute | cassette |
| DE ZEW Economic Sentiment | `germany` | `zew economic sentiment index` | ZEW | cassette |

**Key insight (HALT #2/#3/#7 probe):** TE labels the *headline* ISM PMI
and the *Ifo Business Climate* both as "Business Confidence" under
their respective countries. The identity is disambiguated via the
`Source` field on the catalogue endpoint; same label, different country
→ different institute → different series. Naming fragility noted for
future-TE-schema-drift monitoring.

## 5. E4 quality delta (live smoke, 2026-04-20)

| Country | Pre-sprint | With TE fallback | Delta | New flags |
|---------|-----------|-------------------|-------|-----------|
| US | 6/13 | ≥ 9/13 | +3 | TE_FALLBACK_{ISM_MFG, ISM_SVC, NFIB} |
| DE | 3/13 | ≥ 5/13 | +2 | TE_FALLBACK_{IFO, ZEW} |
| PT/IT/ES/FR/NL | unchanged | unchanged | 0 | n/a |
| JP | 0/13 | 0/13 | 0 | CAL-087 Tankan still pending |

Live smoke wall-clock: ~15s for both countries combined. Five TE
calls per run (3 US + 2 DE); sprint total ~18 calls (below 20 target).

## 6. TE rate-limit status

- Sprint usage: ~18 TE calls (probes + cassettes + smoke × 2 runs).
- Monthly budget: 10,000 Pro calls.
- Projected daily refresh (5 indicators × 7 countries where applicable):
  ~25 calls/day = ~750/month. Well within buffer.
- Production readiness: `TEConnector.get_call_count()` exposes the
  counter; structlog emits `te.call` per fetch with cumulative total.
  A dedicated daily "TE calls today" log-summary is deferred (future
  CAL if telemetry proves insufficient).

## 7. HALT triggers

- **#0 (pre-flight spec deviation)**: E4 spec §2 lists TE as
  non-primary but not excluded. No deviation worth aborting.
- **#2 (country name mapping)**: risk neutralised empirically during
  probe. TE accepts `"united states"`, `"germany"`, etc. verbatim.
- **#3 (indicator name format)**: fired softly — brief-assumed names
  like `"ism manufacturing pmi"` don't exist; the headline is under
  `"business confidence"`. Resolved within the 15-min window.
- **#5 (ISM not in TE)**: did not fire — ISM Mfg + Svc both confirmed
  under TE catalogue.
- **#6 (NFIB not in TE)**: did not fire — `"nfib business optimism
  index"` confirmed.
- **#7 (Ifo/ZEW name edge cases)**: Ifo resolved as
  `"business confidence"` (under germany). ZEW as declared.
- **#8 (CB in TE)**: fired — TE's CC feed is UMich, not CB. Resolution:
  close CAL-093 with documented limitation; don't wire the duplicate.
- **#9 (pre-push gate)**: not fired.
- **#10 (concurrent MSC touches te.py)**: not fired — MSC stayed on
  monetary stack per its brief.

## 8. Deviations from brief

- **Commit count**: 5 effective commits, not 5-7. Commit 4 (TE call
  counter + telemetry) was implemented inside Commit 1 because the
  counter needed to be instance-level from the first fetch. Brief
  structure preserved via docstring + §9.
- **CAL-093 resolution**: closed as "not resolvable by TE" rather
  than fully resolved — CB CCI requires a different source path.
- **Live smoke assertion thresholds**: US baseline 6/13 → expected
  ≥ 10/13 per brief; actual ≥ 9/13 (CB CC stays stale/null depending
  on OECD freeze date). DE baseline 3/13 → expected ≥ 7/13; actual
  ≥ 5/13 because the additional 2 slots beyond Ifo + ZEW (UMich US-only
  proxies, EPU US-only) remain off-country. Both deltas still
  material.

## 9. Commit 4 note — telemetry folded into c1

The brief scoped Commit 4 as a separate "TE call counter + rate-limit
telemetry" commit. Implementing it there would have required rebasing
over Commit 1 to backfill `_call_count` into the constructor, so the
counter ships inside Commit 1 alongside `fetch_indicator`. All brief
deliverables for c4 shipped:

- `self._call_count: int = 0` instance attr
- Incremented inside `fetch_indicator` on every successful fetch
- `get_call_count()` + `reset_call_count()` methods
- `structlog.info("te.call", indicator=..., country=...,
  cumulative_calls=...)` per fetch
- 2 unit tests covering increment + reset

Documented here so the retro commit count stays accurate (5, not 6).

## 10. Sprint readiness for downstream work

- E4 US + DE composites can now run at materially better fidelity.
- ECS composite (Week 6 Sprint 2) can use US E4 with 9/13 components
  (weight sum ~0.70 available) → confidence ≥ 0.75 baseline achievable.
- CAL-082 + CAL-091 can be deprioritized: TE coverage is production-
  grade. Keep as backup plan documentation.
- CAL-087 (JP Tankan) still required when JP enters T1.

*End of retrospective. Sprint CLOSED 2026-04-20.*
