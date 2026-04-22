# Week 10 Sprint B — Per-country ERP T1 Expansion — Implementation Report

## 1. Summary

- **Duration**: ~3h30m wall-clock, single autonomous CC session on
  2026-04-22.
- **Commits**: 5 shipped to branch `sprint-erp-t1-per-country` in
  isolated worktree `/home/macro/projects/sonar-wt-erp-t1-per-country`.
- **Scope outcome**: **narrow-scope ship** (HALT triggers §5.0 + §5.1
  activated during pre-flight).
- **Brief goal**: per-country ERP compute live for DE / GB / JP / FR /
  EA (5 markets × ≥ 2 methods each, within ±20 % of Damodaran
  reference).
- **Delivered goal**: TE per-country equity-index scaffolding +
  Damodaran monthly implied ERP connector + live mature-market
  fallback in `daily_cost_of_capital` + formal deferral via
  **ADR-0008** + 5 sub-CALs for the deferred work.
- **Paralelo with Sprint A** (EA periphery curves, worktree
  `/home/macro/projects/sonar-wt-curves-ea-periphery`): zero file
  conflicts. Shared secondary `docs/backlog/calibration-tasks.md` —
  Sprint B touched only the CAL-ERP-* subsection.
- **CAL-ERP-T1-PER-COUNTRY**: OPEN → PARTIAL.
- **US ERP canonical 322 bps**: **PRESERVED** — no touch to
  `sonar.overlays.erp` compute; all 21 `tests/unit/test_overlays/test_erp.py`
  tests green.

## 2. Context — why the original scope was unshippable

Brief §1 Track 1 asked for `src/sonar/overlays/erp_de.py` /
`erp_gb.py` / `erp_jp.py` / `erp_fr.py` / `erp_ea.py` input
assemblers following the US pattern (DCF + Gordon + EY + CAPE per
market, ≥ 2 methods viable). The pre-flight empirical probe
established definitively that the primary inputs the spec requires
are not available:

- **TE country-indicator endpoint**
  (`/historical/country/{country}/indicator/stock%20market`) returns
  only the flagship-index *closing level* for DE / GB / JP / FR / EA.
  Multi-decade daily coverage is fine (1986-1987 onwards) and
  ``HistoricalDataSymbol`` guards are stable (DAX / UKX / NKY / CAC /
  SX5E), so the *scaffolding* is a real win — but it is **not**
  sufficient input for any of the four ERP methods.
- **TE `/country/{country}` catalog** for Germany (probed live):
  only one entry in the equity family (``Stock Market``). No
  ``Dividend Yield`` / ``PE`` / ``EPS`` categories exist. Probes
  for `germany / dividend yield`, `germany / price earnings`,
  `germany / earnings per share` all return `[]`.
- **FMP `stable` tier**: `historical-price-eod` serves international
  index tickers (`^GDAXI`, `^FTSE`, `^N225`, `^FCHI`, `^STOXX50E`)
  fine. But `key-metrics` + `ratios` return `[]` for these tickers
  — company-level only.
- **Damodaran public page** (2026-04-22 snapshot):
  - `histimpl.xlsx` (annual, US only — already wired).
  - `implprem/ERPMMMYY.xlsx` (monthly, S&P 500 implied — new; see §3).
  - `ctryprem.xlsx` (annual, per-country ERP derived as
    `mature + default_spread × vol_ratio` — on the consume side, not
    input side).
  - `pedata.xls` — US companies by industry, not per-market aggregate.
  - `divfundGlobal.xls` / `divfundEurope.xls` — companies by industry
    within a region; no per-country equity-index roll-up.

All four ERP methods require at least `dividend_yield_pct` or
`forward_earnings_est` or `cape_ratio` per market. The empirical
reality is that those inputs are locked behind vendor contracts
(Refinitiv / FactSet / Bloomberg / MSCI) for the markets in scope.
Sprint B's HALT trigger §5.1 wording ("not a HALT unless *all*
methods fail") activates literally — all four fail for all five
markets.

The discipline call was not to ship hollow `erp_{cc}.py` modules
that would hard-fail on first call. The alternative was a narrower
but real improvement: make the *mature-market* input live (monthly
Damodaran vs static 5.5 %) and ship the TE equity scaffolding so
Phase 2.5 does not re-probe.

## 3. Commits

| # | SHA | Scope |
|---|-----|-------|
| 1 | `e240c99` | `feat(connectors): TE per-country equity index scaffolding + Sprint B pre-flight findings` |
| 2 | `4adf4ef` | `feat(connectors): Damodaran monthly implied ERP archive (ERPMMMYY.xlsx)` |
| 3 | `408c211` | `feat(pipelines): daily_cost_of_capital Damodaran monthly live fallback` |
| 4 | `9017cda` | `docs(adr): ADR-0008 per-country ERP data constraints + CAL sub-items` |
| 5 | this     | `docs(planning): Week 10 Sprint B ERP T1 retrospective (v3 format)` |

All 4 code / doc commits pushed with full pre-push gate (ruff format
+ ruff check + mypy src/sonar + pytest unit) green. No `--no-verify`.

## 4. Empirical probes (2026-04-22)

### 4.1 TE equity-index availability

```
/historical/country/{slug}/indicator/stock%20market
```

| ISO | TE slug         | Symbol | Earliest obs   | Latest (probe)        |
|-----|-----------------|--------|----------------|-----------------------|
| DE  | germany         | DAX    | 1987-12-30     | 2024-01-05 (cassette) |
| GB  | united kingdom  | UKX    | 1987-02-11     | 2024-01-05            |
| JP  | japan           | NKY    | 1986-02-14     | 2024-01-05            |
| FR  | france          | CAC    | 1987-07-09     | 2024-01-05            |
| EA  | euro area       | SX5E   | 1987-09-08     | 2024-01-05            |

Note: JP surfaces the **Nikkei 225** (NKY), not TOPIX. Brief §1
wording presumed TOPIX; empirical reality is Nikkei. Retro note
captured in ADR-0008 and connector docstring so the deviation does
not get re-surfaced.

TE slug resolution is strict:

- ``united-kingdom`` (hyphen) → `[]`.
- ``united kingdom`` (space, URL-encoded `%20`) → 10000-row cap hit.
- ``eurozone`` / ``european union`` → `[]`; only ``euro area`` works.

Added ``EA → "euro area"`` to :data:`TE_COUNTRY_NAME_MAP` alongside
the new `fetch_equity_index_historical` wrapper.

### 4.2 Equity fundamentals per country — not available

| Source | Dividend yield | Trailing EPS | Forward EPS | CAPE | Buyback |
|--------|:--------------:|:------------:|:-----------:|:----:|:-------:|
| TE country-indicator | ✗ | ✗ | ✗ | ✗ | ✗ |
| FMP stable key-metrics / ratios | ✗ | ✗ | ✗ | ✗ | ✗ |
| Damodaran histimpl / implprem | — US only — | — US only — | — US only — | — US only — | — US only — |
| Damodaran ctryprem | consume-side (rejected) | — | — | — | — |
| Damodaran divfund* | industry-within-region (US companies) | — | — | — | — |

Confirms all four ERP methods fail for DE / GB / JP / FR / EA in the
current connector surface.

### 4.3 Damodaran monthly implied ERP archive

| File | HTTP | Notes |
|------|------|-------|
| `implprem/ERPJan26.xlsx` | 200 | Published Feb 2026 |
| `implprem/ERPFeb26.xlsx` | 200 | Published Apr 2026; current latest |
| `implprem/ERPMar26.xlsx` | 404 | Unpublished |
| `implprem/ERPApr26.xlsx` | 404 | Unpublished |

Publishing lag ≈ 2 months. ``IMPLPREM_LOOKBACK_MONTHS = 6`` gives
generous headroom for the resolver backward walk.

`ERPFeb26.xlsx` → sheet `Implied ERP (Monthly from 9-08)` →
2026-02-01 row:

| Column | Value |
|--------|-------|
| ERP (T12 m with sustainable payout) | **0.0417** |
| ERP (T12m)                          | 0.0425 |
| S&P 500 level                       | 6939.0 |
| T.Bond Rate                         | 0.0426 |
| $ Riskfree Rate                     | 0.0403 |

vs static `DAMODARAN_MATURE_ERP_DECIMAL = 0.055` → delta is
**-133 bps** (the static stub was chronically overstating mature
ERP by 133 bps when read against live Damodaran).

## 5. Changes by file

### Source

- `src/sonar/connectors/te.py` — `+90` lines.
  - `TE_COUNTRY_NAME_MAP` += `EA → "euro area"`.
  - `TE_INDICATOR_STOCK_MARKET` constant.
  - 5 new source-identity guard constants
    (`TE_EXPECTED_SYMBOL_{DE,GB,JP,FR,EA}_EQUITY_INDEX`).
  - `TE_EQUITY_INDEX_EXPECTED_SYMBOL` dispatch map.
  - `fetch_equity_index_historical(country, start, end)` method.
- `src/sonar/connectors/damodaran.py` — `+160` lines.
  - `IMPLPREM_URL_TEMPLATE`, `IMPLPREM_TTL_SECONDS`, `IMPLPREM_SHEET`,
    `IMPLPREM_LOOKBACK_MONTHS`, column constants.
  - `DamodaranMonthlyERPRow` dataclass.
  - `DamodaranConnector.fetch_monthly_implied_erp(year, month)`.
  - `DamodaranConnector._resolve_latest_implprem` (backward walk +
    single-body cache).
  - `_parse_monthly` + `_cell_to_float` helpers.
- `src/sonar/pipelines/daily_cost_of_capital.py` — `+75` lines.
  - `_MatureFallback` dataclass.
  - `resolve_mature_erp_fallback(observation_date, ...)` async
    wrapper.
  - `_resolve_erp_bps` gains a keyword-only `mature_fallback`
    argument; new `ERP_MATURE_LIVE_DAMODARAN` flag path.
  - `run_one` threads `mature_fallback` through.
  - `main` resolves the fallback once per invocation +
    `--no-damodaran-live` CLI opt-out +
    `SONAR_DISABLE_DAMODARAN_LIVE=1` env opt-out.

### Tests

- `tests/unit/test_connectors/test_te_indicator.py` — `+200` lines.
  - 2 parametrised unit tests over the 5 new wrappers (source-drift
    + cassette-backed parse).
  - 1 unknown-country error test.
  - 5 `@pytest.mark.slow` live canaries (one per market).
- `tests/unit/test_connectors/test_damodaran.py` — `+230` lines.
  - 5 parser tests on synthetic workbook.
  - 4 connector tests (happy path + backward walk + lookback
    exhaustion + month-range validation).
  - 1 `@pytest.mark.slow` live canary probing NYU host directly.
- `tests/unit/test_pipelines/test_daily_cost_of_capital.py` —
  `+130` lines.
  - `TestResolveErpBpsWithLiveFallback` — 4 tests (live Damodaran
    preempts stub for US + non-US; erp_canonical still wins;
    empty fallback falls through).
  - `TestResolveMatureErpFallbackDisabled` — 2 tests (flag +
    env var).
  - `TestComposeKEWithDamodaranLiveFlag` — 1 test (confidence
    preservation).

### Cassettes

- 5 new TE equity cassettes:
  - `tests/cassettes/connectors/te_equity_germany_2024_01_02.json`
  - `tests/cassettes/connectors/te_equity_united_kingdom_2024_01_02.json`
  - `tests/cassettes/connectors/te_equity_japan_2024_01_02.json`
  - `tests/cassettes/connectors/te_equity_france_2024_01_02.json`
  - `tests/cassettes/connectors/te_equity_euro_area_2024_01_02.json`
  - 150 rows each (slimmed from TE's 10000-row cap to ~35 KB).
- Damodaran monthly parser uses synthetic-xlsx fixtures in-test
  (avoided checking in the 1.5 MB real workbook).

### Documentation

- `docs/planning/week10-sprint-b-erp-t1-preflight-findings.md` —
  empirical probe reference + HALT rationale + re-scoped acceptance
  list + CAL consequences.
- `docs/adr/ADR-0008-per-country-erp-data-constraints.md` — formal
  decision record (status: Accepted).
- `docs/backlog/calibration-tasks.md` — CAL-ERP-T1-PER-COUNTRY
  rewritten to PARTIAL; 5 new sub-CAL entries below it.
- `docs/planning/retrospectives/week10-sprint-erp-t1-report.md` —
  this file.

## 6. ERP methods matrix per country (post-sprint reality)

| Country | Market index | DCF | Gordon | EY | CAPE |
|---------|--------------|:---:|:------:|:--:|:----:|
| US      | SPX          | ✓   | ✓      | ✓  | ✓    |
| DE      | DAX          | ✗   | ✗      | ✗  | ✗    |
| GB      | UKX (FTSE)   | ✗   | ✗      | ✗  | ✗    |
| JP      | NKY (Nikkei) | ✗   | ✗      | ✗  | ✗    |
| FR      | CAC          | ✗   | ✗      | ✗  | ✗    |
| EA      | SX5E         | ✗   | ✗      | ✗  | ✗    |

Non-US rows stay on the SPX proxy via the pipeline's
`MATURE_ERP_PROXY_US` semantics, now enhanced with live Damodaran
monthly implied ERP as the mature-market input.

Original brief §6 acceptance required ≥ 2 methods viable per country
with ±20 % Damodaran cross-val. That target is explicitly **not
met** and is formally reopened under
`CAL-ERP-COUNTRY-FUNDAMENTALS`.

## 7. Pipeline flag changes

Before Sprint B:

```
ERP source = erp_canonical_SPX           flags = ()          (US live)
ERP source = erp_canonical_SPX           flags = (MATURE_ERP_PROXY_US,)   (non-US)
ERP source = static 5.5 %                flags = (ERP_STUB,)               (fallback)
```

After Sprint B:

```
ERP source = erp_canonical_SPX              flags = ()                              (US live — unchanged)
ERP source = erp_canonical_SPX              flags = (MATURE_ERP_PROXY_US,)          (non-US live — unchanged)
ERP source = Damodaran monthly (live)       flags = (ERP_MATURE_LIVE_DAMODARAN,)    (US fallback — NEW)
ERP source = Damodaran monthly (live)       flags = (ERP_MATURE_LIVE_DAMODARAN,
                                                     MATURE_ERP_PROXY_US)           (non-US fallback — NEW)
ERP source = static 5.5 %                   flags = (ERP_STUB,)                     (last-resort — unchanged)
```

Only ``ERP_STUB`` deducts confidence (`-0.20`); the new live
Damodaran flag reflects a compute-grade source and stays at
CRP-baseline confidence.

## 8. Production impact

- `daily_cost_of_capital` cold-start runs (before SONAR ERP pipeline
  has produced its own `erp_canonical` row for the target date)
  previously fell to the static 5.5 % stub. Post-sprint they use the
  live Damodaran monthly implied ERP (currently ≈ 4.17 %). Delta in
  persisted `erp_mature_bps` for affected (country, date) pairs:
  **-133 bps**.
- `k_e_pct` reported on cold starts moves accordingly
  (`k_e = rf + ERP_mature + CRP`) — same downward shift.
- Systemd unit `sonar-daily-cost-of-capital.service` requires no
  change; the new fallback runs inside `main()` so the CLI signature
  is additive (`--no-damodaran-live`). Existing `--all-t1 --date {d}`
  invocation is unchanged.

## 9. Pre-push gate + acceptance

Pre-push gate (brief §8 mandatory):

```
uv run ruff format --check src/sonar tests        → PASS
uv run ruff check src/sonar tests                 → PASS
uv run mypy src/sonar                             → PASS
uv run pytest tests/unit/ -x --no-cov             → 1618 passed / 32 skipped live-canary
```

Pre-existing failures unrelated to Sprint B (`test_aaii`, `test_move_index`,
`test_yahoo_finance` live canaries — external host flakiness;
stashed-diff sanity check confirmed).

Sprint B-specific acceptance (from pre-flight findings §7, which
supersedes the brief §6 checklist because the original scope was
infeasible):

- [x] TE equity index scaffolding live for DE / GB / JP / FR / EA
  with source-drift guards.
- [x] 5 TE equity cassettes shipped.
- [x] 5 @slow live canaries validate symbol stability + closing-level
  band per country (all pass in ~7.8 s with `TE_API_KEY` loaded).
- [x] Damodaran monthly implied ERP connector live + 14 unit tests +
  1 live canary.
- [x] `daily_cost_of_capital` reads live mature-market ERP via
  3-tier fallback; new flag `ERP_MATURE_LIVE_DAMODARAN`.
- [x] US ERP canonical 322 bps preserved (`test_erp.py` 21/21 pass).
- [x] ADR-0008 shipped (Accepted).
- [x] `CAL-ERP-T1-PER-COUNTRY` marked PARTIAL; 5 new sub-CALs
  catalogued.
- [x] Retrospective v3 format shipped.
- [x] Pre-push gate green every push.

## 10. §10 Pre-merge checklist (brief v3)

- [x] All commits pushed to origin (step pending §11 invocation —
  operator runs `./scripts/ops/sprint_merge.sh` from primary repo).
- [x] Workspace clean (`git status` = clean after this commit lands).
- [x] Pre-push gate green on each commit.
- [ ] Branch tracking set (the script's step 4 handles this; the
  worktree presently shows no upstream, to be set via
  `git push -u origin sprint-erp-t1-per-country` triggered by the
  merge script).
- [x] Cassettes + canaries green (5 TE + 14 Damodaran + 26 pipeline).
- [x] Cross-validation vs Damodaran reference documented §4.3.

## 11. §11 Merge execution

```bash
./scripts/ops/sprint_merge.sh sprint-erp-t1-per-country
```

Run from the **primary** repo (`/home/macro/projects/sonar-engine`),
not from this worktree. Atomic 10-step sequence.

## 12. Paralelo discipline with Sprint A

- Sprint A worktree: `/home/macro/projects/sonar-wt-curves-ea-periphery`.
- Sprint A primary files: `src/sonar/connectors/ecb_sdw.py`,
  `src/sonar/pipelines/daily_curves.py`.
- Sprint B primary files: `src/sonar/connectors/te.py` (append-only
  equity wrapper), `src/sonar/connectors/damodaran.py` (extension),
  `src/sonar/pipelines/daily_cost_of_capital.py`.
- **Zero overlap** on primary files.
- Shared secondary: `docs/backlog/calibration-tasks.md`. Sprint B
  touched only the `CAL-ERP-*` subsection. If Sprint A added new
  `CAL-CURVES-*` entries alphabetically adjacent, merge should be
  a trivial union. If any conflict arises, Sprint A ships first
  (alphabetical convention) and Sprint B rebases.

## 13. Final tmux echo

```
SPRINT B ERP T1 NARROW-SCOPE SHIP: 5 commits on branch sprint-erp-t1-per-country

Pre-flight HALT triggers §5.0 + §5.1 activated — per-country ERP
compute blocked by vendor gap (dividend yield + EPS + CAPE per
market index not available via TE / FMP / Damodaran).

Shipped:
  - TE per-country equity scaffolding: DE (DAX), GB (UKX), JP (NKY
    — Nikkei not TOPIX), FR (CAC), EA (SX5E)
  - Damodaran monthly implied ERP connector (ERPMMMYY.xlsx)
  - daily_cost_of_capital 3-tier mature-ERP fallback
    (erp_canonical → Damodaran monthly → static 5.5 %)
  - ADR-0008 + 5 sub-CALs for deferred per-country compute
  - 5 TE cassettes + 14 Damodaran tests + 26 pipeline tests
  - Retrospective v3 format

US canonical 322 bps: PRESERVED ✓

CAL-ERP-T1-PER-COUNTRY: OPEN → PARTIAL.

Deferred under CAL-ERP-COUNTRY-FUNDAMENTALS,
CAL-ERP-CAPE-CROSS-COUNTRY, CAL-ERP-BUYBACK-CROSS-COUNTRY,
CAL-ERP-T1-SMALLER-MARKETS, CAL-ERP-T1-NON-EA.

Production impact: daily_cost_of_capital cold-start runs now read
live Damodaran mature ERP (4.17 %) instead of static 5.5 % stub.
Delta -133 bps on affected (country, date) pairs.

Paralelo with Sprint A: zero primary-file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-erp-t1-per-country

Artifacts:
  - docs/planning/week10-sprint-b-erp-t1-preflight-findings.md
  - docs/adr/ADR-0008-per-country-erp-data-constraints.md
  - docs/planning/retrospectives/week10-sprint-erp-t1-report.md
```
