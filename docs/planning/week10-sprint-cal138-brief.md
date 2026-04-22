# Week 10 Day 1-2 Sprint CAL-138 — daily_curves Multi-Country (Cascade Mirror M1)

**Target**: Expand `daily_curves` pipeline from Phase-1-Week-2 US-only to T1 uniform coverage (16 countries) via connector-type-organized cascade. Ship US (existing FRED) + EA members (shared ECB SDMX) + individual T1 (TE-primary yield cascade, analog to M1 pattern). Unblocks overlays/cost-of-capital T1 cascade; resolves production cascade CAL-138.
**Priority**: HIGH (blocks overlays/ERP cross-country; Phase 2 exit criterion)
**Budget**: 5-7h CC (paralelo-ready via connector-type split)
**Commits**: ~10-14 (granular per connector + per country batch)
**Base**: branch `sprint-cal138-curves-multi-country` (isolated worktree `/home/macro/projects/sonar-wt-cal138`)
**Concurrency**: Solo OR paralelo (see §3 decomposition options)

**Brief format**: v3 (first sprint using new pre-merge checklist)

---

## 1. Scope

In (3 connector-type tracks):

### Track A — EA members via ECB SDMX shared connector (~2-3h)
Ship single ECB SDMX connector serving all 6 EA members (DE, PT, IT, ES, FR, NL). Leverages Bundesbank/ECB sovereign yield dataflows.
- `src/sonar/connectors/ecb_sdw.py` EXTEND (if connector exists) OR NEW — `fetch_yield_curve_nominal` + `fetch_yield_curve_linker` per EA member
- ECB SDW dataflow: `FM` (Financial Markets) OR `YC` (Yield Curves — direct ECB NSS fits)
- **Options**:
  - **Option A1**: ECB SDW `YC` direct NSS fits consumed as inputs (fastest — ECB already did NSS fit daily)
  - **Option A2**: ECB SDW `FM` raw quotes + SONAR NSS fit per country (consistency with US FRED path — same methodology)
  - **Recommended**: **A2** for consistency (SONAR's NSS methodology uniform across countries; ECB's fit may differ subtly in β bounds)
- Linker series: inflation-indexed bonds per EA member (DE has `DE10YI`, PT has `PT10YI`, etc. — verify availability)
- If linker unavailable for some EA members, gracefully emit `LINKER_UNAVAILABLE` flag

### Track B — Individual T1 via TE-primary yield cascade (~3-4h)
Ship TE-primary yield cascade for non-EA, non-US T1 countries: GB, JP, CA, AU, NZ, CH, SE, NO, DK (9 countries).
- `src/sonar/connectors/te.py` APPEND — yield curve wrappers per country:
  - `fetch_gb_yield_curve_nominal` (TE GB sovereign yields 1M-30Y)
  - `fetch_jp_yield_curve_nominal` (TE JP sovereign 1M-40Y)
  - `fetch_ca_yield_curve_nominal` (TE CA 1M-30Y)
  - `fetch_au_yield_curve_nominal` (TE AU 1M-30Y)
  - `fetch_nz_yield_curve_nominal` (TE NZ 1M-10Y, shorter tenor spectrum)
  - `fetch_ch_yield_curve_nominal` (TE CH 1M-30Y, may include negative-rate era)
  - `fetch_se_yield_curve_nominal` (TE SE 1M-30Y, negative-rate era 2015-2019)
  - `fetch_no_yield_curve_nominal` (TE NO 1M-10Y)
  - `fetch_dk_yield_curve_nominal` (TE DK 1M-30Y, negative-rate era 2015-2022)
- Source-drift guards per country (HistoricalDataSymbol validation per Sprint 3 Quick Wins discipline)
- Linker data: deferred per country if TE doesn't expose (CAL items opened per-country)
- **Fallback cascade per Sprint L pattern**: TE primary → native connector (BoE/BoJ/BoC/RBA/RBNZ/SNB/Riksbank/Norges Bank/Nationalbanken — partial, some gated) → FRED OECD mirror

### Track C — Pipeline refactor + CLI expansion (~1-2h)
Refactor `daily_curves.py` from single-country `run_us` to multi-country dispatch.
- Add `--all-t1` CLI flag (mirrors other 8 pipelines)
- Remove hardcoded US-only check (line 78 `if country != "US"`)
- Country-aware connector dispatch in pipeline:
  - US → `fred.fetch_yield_curve_nominal` (existing `run_us`)
  - DE/PT/IT/ES/FR/NL → `ecb_sdw.fetch_yield_curve_nominal(country)`
  - GB/JP/CA/AU/NZ/CH/SE/NO/DK → `te.fetch_{country}_yield_curve_nominal` + native fallback
- NSS fit applied uniform across all countries (existing `fit_nss` logic)
- Persistence uniform: `NSSYieldCurveSpot` per country per date
- Cassettes + live canaries per country (16 countries × 1 canary each)
- systemd service update `sonar-daily-curves.service` — change `--country US` to `--all-t1`

### Track D — CAL closures + retrospective (~30min)
- CAL-138 closed with resolution summary
- CAL-137 weekly canary wiring (BIS surveillance, deferred from Day 0)
- New CAL items for gaps: linker-per-country deferred items, negative-rate-era yield conventions, etc.
- Retrospective per v3 format

Out:
- T2 expansion (Phase 2.5 scope)
- M3 market-expectations per-country wiring (depends on curves shipped, separate sprint Week 10 Day 3+)
- ERP per-country (separate sprint Week 10+)
- Backtest of NSS fits cross-country (Phase 4 calibration)

---

## 2. Spec reference

Authoritative:
- `docs/specs/overlays/nss-curves.md` — NSS methodology (US-centric language, applies uniform cross-country)
- `docs/backlog/calibration-tasks.md` — CAL-138 entry (Day 0 Commit 7 context)
- `src/sonar/overlays/nss_curves/` — existing NSS fit code (reuse as-is)
- `src/sonar/pipelines/daily_curves.py` — current US-only pipeline (refactor target)
- `src/sonar/connectors/fred.py` — US FRED yield curve pattern (reference)
- `src/sonar/connectors/te.py` — TE-primary cascade pattern (reference for Track B)
- `src/sonar/indices/monetary/builders.py` — M1 cascade pattern (mirror structure for curves)
- Week 9 sprint retros — connector idioms per country (empirical findings per country)
- **brief-format-v3.md** — this brief's template

**Pre-flight requirement**: Commit 1 CC:
1. **Read CAL-138 entry** to confirm scope + required work
2. **Inventory existing ECB SDW connector state**:
   ```bash
   ls src/sonar/connectors/ | grep -i ecb
   grep -l "ECBSDWConnector\|ecb_sdw" src/sonar/
   ```
3. **Probe ECB SDW dataflows**:
   - YC dataflow: `curl -s "https://data-api.ecb.europa.eu/service/data/YC?format=jsondata&startPeriod=2024-12-01&endPeriod=2024-12-31" | head -100`
   - FM dataflow: `curl -s "https://data-api.ecb.europa.eu/service/data/FM?format=jsondata&startPeriod=2024-12-01&endPeriod=2024-12-31" | head -100`
4. **Probe TE yield curve availability per country**:
   ```bash
   set -a && source .env && set +a
   for country in united-kingdom japan canada australia new-zealand switzerland sweden norway denmark; do
       echo "=== $country ==="
       curl -s "https://api.tradingeconomics.com/historical/country/$country/indicator/government bond 10y?c=$TE_API_KEY&format=json&d1=2024-12-01&d2=2024-12-05" | jq '.[0]'
   done
   ```
5. **Verify linker series availability per EA member** (via FRED OECD mirrors OR ECB SDW):
   - DE linker (DE10YI OR similar)
   - PT linker (limited historical, may require fallback)
   - IT linker (BTP€I series via ECB SDW)
   - ES linker (Bonos indexados via ECB SDW)
   - FR linker (OATi/OATei via ECB SDW)
   - NL linker (DSL indexed via ECB SDW — limited)

Document findings Commit 1 body.

---

## 3. Concurrency — paralelo decomposition

**Primary option — SINGLE SPRINT SOLO** (budget 5-7h):
- Single worktree `sonar-wt-cal138`
- Sequential Track A → Track B → Track C → Track D
- Operator monitors periodically

**Secondary option — PARALELO 2-WAY** (velocity + overhead trade-off):
- **Sprint CAL-138-A**: EA members via ECB SDW (worktree `sonar-wt-cal138-ea`, ~3h)
- **Sprint CAL-138-B**: Individual T1 via TE cascade (worktree `sonar-wt-cal138-t1`, ~4h)
- Final integration (pipeline refactor + CLI) by whichever finishes first
- Shared file append zones: `te.py` (Track B only), `ecb_sdw.py` (Track A only), `daily_curves.py` (both modify — rebase expected)
- Rebase cost: ~15-25min via CC delegation (Week 9 pattern)

**Recommended**: **Solo sequential** — CAL-138 has coordinated refactor (pipeline CLI + dispatch) that benefits from single mental model. Paralelo marginal gain.

Branch: `sprint-cal138-curves-multi-country`
Worktree: `/home/macro/projects/sonar-wt-cal138`

**Worktree sync**:
```bash
cd /home/macro/projects/sonar-wt-cal138 && git pull origin main
```

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed: `git log origin/sprint-cal138-curves-multi-country` shows expected N commits
- [ ] Workspace clean: `git status` returns no modifications
- [ ] Pre-push gate passed: ruff + mypy + pytest green
- [ ] Branch tracking set: `git branch -vv` shows [origin/sprint-cal138-curves-multi-country]
- [ ] Cassettes shipped: 1 cassette per new country live canary
- [ ] systemd service update documented in commit body for operator VPS-side

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-cal138-curves-multi-country
```

---

## 4. Commits

### Commit 1 — Pre-flight + ECB SDW connector setup

```
feat(connectors): pre-flight CAL-138 + ECB SDW yield curve extension

Pre-flight empirical probes (document Commit 1 body):

1. ECB SDW state:
   - Connector exists: [yes/no]
   - Dataflows probed: YC + FM
   - Response format: [SDMX-JSON per probe]
   - Auth: public

2. TE yield curve per country (9 countries):
   [per country — HistoricalDataSymbol returned + historical range + reasonable-value sanity check]

3. EA linker series availability:
   - DE: [series ID + source]
   - PT: [series ID + source OR "limited, fallback needed"]
   - IT: [BTP€I via ECB SDW]
   - ES: [Bonos indexados via ECB SDW]
   - FR: [OATi/OATei via ECB SDW]
   - NL: [DSL indexed via ECB SDW — limited]

Extend src/sonar/connectors/ecb_sdw.py:

async def fetch_yield_curve_nominal(
    self,
    country: str,
    observation_date: date,
) -> dict[str, YieldCurvePoint]:
    """Fetch nominal sovereign yield curve for EA member country.

    Supported countries: DE, PT, IT, ES, FR, NL.
    Returns dict {tenor_label: YieldCurvePoint} for tenors 1M-30Y.
    """

async def fetch_yield_curve_linker(
    self,
    country: str,
    observation_date: date,
) -> dict[str, YieldCurvePoint]:
    """Fetch inflation-indexed bond yields for EA member country.

    Returns empty dict + logs flag if country has no linker series
    (DE/FR/IT have linkers; PT/ES/NL limited).
    """

Tests (tests/unit/test_connectors/test_ecb_sdw.py):
- Unit: fetch_yield_curve_nominal DE happy path (mocked SDMX-JSON)
- Unit: country validation (rejects non-EA-member with ValueError)
- Unit: fetch_yield_curve_linker returns empty for countries without linker
- @pytest.mark.slow live canary: DE yield curve 2024-12-31, assert ≥ 8 tenors

Cassettes: tests/fixtures/cassettes/ecb_sdw/
- yield_curve_nominal_de_2024_12_31.json
- yield_curve_linker_de_2024_12_31.json

Coverage ecb_sdw.py extensions ≥ 90%.
```

### Commit 2 — EA periphery extensions (PT/IT/ES/FR/NL)

```
feat(connectors): ECB SDW yield curves PT/IT/ES/FR/NL

Extend ecb_sdw.py supported countries + per-country dataflow mapping.

Tests:
- Unit: happy path per country (PT/IT/ES/FR/NL)
- Unit: linker availability per country (emit flag if unavailable)
- @pytest.mark.slow live canaries per country

Cassettes per country.
```

### Commit 3 — TE yield curve wrappers (GB/JP/CA/AU/NZ)

```
feat(connectors): TE fetch_{gb,jp,ca,au,nz}_yield_curve_nominal wrappers

Extend src/sonar/connectors/te.py with yield curve wrappers for 5 T1
non-EA, non-negative-rate countries.

Per country:
- HistoricalDataSymbol probe-validated (source-drift guard)
- Tenor spectrum: 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y (20Y/30Y optional)
- NZ shorter spectrum (1M-10Y only)

Tests per country — unit + @pytest.mark.slow canaries.

Cassettes: tests/cassettes/connectors/te_{country}_yield_curve_*.json
```

### Commit 4 — TE yield curve wrappers with negative-rate era (CH/SE/DK) + NO

```
feat(connectors): TE fetch_{ch,se,no,dk}_yield_curve_nominal wrappers

4 Nordic/Alpine countries including 3 negative-rate era (CH/SE/DK).

Per country:
- HistoricalDataSymbol probe-validated
- Negative value preservation (2014-2022 era depending on country)
- Flag emissions per cascade pattern (Sprint V-CH/W-SE/Y-DK precedent):
  - CH_YIELD_NEGATIVE_ERA_DATA
  - SE_YIELD_NEGATIVE_ERA_DATA
  - DK_YIELD_NEGATIVE_ERA_DATA
- NO standard positive-only (never negative-rate era)

Tests per country — including historical negative-era canary.

Cassettes per country.
```

### Commit 5 — Pipeline refactor daily_curves.py multi-country dispatch

```
refactor(pipelines): daily_curves multi-country dispatch

Remove US-only hardcoded check.
Add country-aware connector dispatch:
- US → fred.fetch_yield_curve_nominal
- DE/PT/IT/ES/FR/NL → ecb_sdw.fetch_yield_curve_nominal(country)
- GB/JP/CA/AU/NZ/CH/SE/NO/DK → te.fetch_{country}_yield_curve_nominal + FRED OECD fallback

Add --all-t1 CLI flag.
Preserve --country <X> single-country flag (backward compat).

NSS fit uniform across countries (reuse existing fit_nss + derive_zero_curve +
derive_forward_curve logic).

Linker handling per country:
- US: TIPS via FRED (existing)
- EA members: per-country linker via ECB SDW OR fallback to DERIVED method
- Other T1: deferred per country (emit LINKER_UNAVAILABLE flag)

Unit tests:
- Pipeline dispatch for each connector type
- --all-t1 iterates 16 T1 countries
- --country single-country still works (US, DE, GB, etc.)

Integration test @slow:
- tests/integration/test_daily_curves_multi_country.py
- Full pipeline execution for 3 sample countries (US, DE, GB) — one per connector type
- Assert NSSYieldCurveSpot row per country

Coverage daily_curves.py ≥ 90%.
```

### Commit 6 — CLI + service file documentation

```
chore(pipelines): daily_curves --all-t1 flag + service file update note

Add --all-t1 flag documentation to pipeline CLI help.

systemd service update documented for operator VPS-side:
/etc/systemd/system/sonar-daily-curves.service
  ExecStart change: --country US → --all-t1
  Comment update: "# T1 uniform coverage (16 countries) via --all-t1 flag."

Operator command (post-merge):
  sudo sed -i 's|--country US|--all-t1|' /etc/systemd/system/sonar-daily-curves.service
  sudo sed -i 's|# Phase 1 Week 2 scope — US only.*|# T1 uniform coverage (16 countries) via --all-t1 flag per CAL-138.|' /etc/systemd/system/sonar-daily-curves.service
  sudo systemctl daemon-reload

No repo changes (service file lives on VPS).
```

### Commit 7 — Cassettes + live canaries full suite

```
test: yield curve cassettes + live canaries for 15 new T1 countries

Add cassettes for:
- ECB SDW: 6 EA members × yield curve + linker (12 cassettes)
- TE: 9 non-EA T1 countries × yield curve nominal (9 cassettes)
- Total 21 new cassettes

Live canaries (@pytest.mark.slow):
- tests/integration/test_daily_curves_multi_country.py (expanded)
- 1 canary per country (15 canaries)
- Combined suite wall-clock target ≤ 60s

Coverage maintained.
```

### Commit 8 — CAL closures + new CAL items

```
docs(backlog): CAL-138 CLOSED + new CAL items for linker gaps

Close:
- CAL-138 curves multi-country — resolved via Sprint CAL-138 (commits [SHAs])

Open:
- CAL-LINKER-PT (PT limited historical inflation-indexed coverage)
- CAL-LINKER-NL (NL DSL linker limited data)
- CAL-LINKER-NON-EA-T1 (linker deferred for GB/JP/CA/AU/NZ/CH/SE/NO/DK — no TE-accessible linker; FRED OECD fallback partial)

Close (from Day 0 deferral):
- CAL-137 BIS v2 weekly canary — add weekly canary script to systemd (separate commit)

Update calibration-tasks.md top-of-file:
- Post-CAL-138 count
- Phase 2 exit criteria progress (curves T1 uniform achieved ✓)
```

### Commit 9 — Retrospective per v3 format

```
docs(planning): Week 10 Day 1-2 Sprint CAL-138 retrospective

File: docs/planning/retrospectives/week10-sprint-cal138-report.md

Per v3 format (includes §10 pre-merge checklist executed + §11 merge via script).

Content:
- Duration + commits + scope
- Connector outcomes matrix (16 countries: 1 US / 6 EA via ECB / 9 via TE)
- NSS fit quality per country (RMSE bps per country from live canaries)
- Linker coverage per country
- Negative-rate era validation for CH/SE/DK yields
- Flag emissions matrix
- Coverage delta
- HALT triggers (fired / not fired)
- CAL evolution
- Production impact: overlays cascade now functional T1-wide tomorrow 07:30 WEST
- Merge script dogfooded (first use of sprint_merge.sh)
- Lessons vs v3 template experience
```

---

## 5. HALT triggers (atomic)

0. **ECB SDW connector state uncertain** — if connector exists partial, extend vs rewrite decision; HALT and surface.
1. **TE yield curve empirical probe fails** — if TE returns unexpected format OR missing HistoricalDataSymbol, scope narrow to available countries.
2. **ECB linker data limited** — if PT/ES/NL linker empirical lookup confirms sparse data, scope to DE/FR/IT linkers + DERIVED fallback for others.
3. **NSS fit convergence failure** for specific country — negative-rate era fits may exceed β0 bounds (CAL-030 existing); emit flag + log + skip country (non-HALT).
4. **Tenor spectrum mismatch** — countries with shorter spectra (NZ 1M-10Y) need fit with fewer tenors; validate `fit_nss` handles ≥ 5 tenors minimum.
5. **Linker unavailability** — emit `LINKER_UNAVAILABLE` + `REAL_CURVE_DERIVED_ONLY` flags per country; not a HALT.
6. **Cassette count < 20** — coverage gap; HALT.
7. **Live canary wall-clock > 90s** — optimize (parallel canary execution) OR split suite.
8. **Pre-push gate fails** — fix before push, full mypy mandatory.
9. **No `--no-verify`** — standard discipline.
10. **Coverage regression > 3pp** → HALT.
11. **systemd service update** — document in commit body, operator executes VPS-side post-merge. Do NOT execute from CC session.
12. **Paralelo split activated mid-sprint** — if solo single-sprint proves infeasible, HALT + propose paralelo split in next commit body.

---

## 6. Acceptance

### Global sprint-end
- [ ] ECB SDW connector serves 6 EA members (DE/PT/IT/ES/FR/NL)
- [ ] TE yield wrappers ship for 9 countries (GB/JP/CA/AU/NZ/CH/SE/NO/DK)
- [ ] 3 negative-rate countries (CH/SE/DK) yield curve validated (historical era)
- [ ] `daily_curves.py` supports `--all-t1` + per-country dispatch
- [ ] NSS fit applied uniform across 16 T1 countries
- [ ] Cassettes ≥ 20 shipped
- [ ] Live canaries ≥ 15 @pytest.mark.slow PASS combined ≤ 90s
- [ ] systemd service update command documented (operator executes)
- [ ] CAL-138 CLOSED with commit refs
- [ ] CAL-137 BIS weekly canary wired (if scope; otherwise deferred + documented)
- [ ] Coverage ecb_sdw.py + te.py extensions ≥ 90%
- [ ] daily_curves.py ≥ 90%
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] **Pre-merge checklist §10 executed**
- [ ] **Merge via sprint_merge.sh** (first production use)
- [ ] Retrospective shipped per v3 format

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-cal138-report.md`

**Final tmux echo**:
```
SPRINT CAL-138 DONE: N commits on branch sprint-cal138-curves-multi-country

Curves multi-country shipped:
- US (existing FRED) ✓
- EA members: DE, PT, IT, ES, FR, NL via ECB SDW ✓
- Individual T1: GB, JP, CA, AU, NZ, CH, SE, NO, DK via TE ✓
Total: 16 T1 countries

NSS fit applied uniform. Linker coverage: US TIPS + DE/FR/IT full, PT/ES/NL limited,
other T1 deferred (CAL-LINKER-NON-EA-T1).

Negative-rate era validated: CH (93m), SE (58m), DK (86m).

Pipeline refactored: --all-t1 flag + country-aware dispatch.

systemd service operator actions:
  sudo sed -i 's|--country US|--all-t1|' /etc/systemd/system/sonar-daily-curves.service
  sudo systemctl daemon-reload

CAL-138 CLOSED. CAL-LINKER-* opened for deferred linker gaps.

HALT triggers fired: [list or "none"]

**Dogfooded sprint_merge.sh**: [first use outcome — success OR surface issues]

Merge executed: ./scripts/ops/sprint_merge.sh sprint-cal138-curves-multi-country

Production impact: tomorrow 07:30 WEST sonar-daily-overlays.service will execute
T1 cascade end-to-end (previously blocked US-only per CAL-138).

Artifact: docs/planning/retrospectives/week10-sprint-cal138-report.md
```

---

## 8. Pre-push gate (mandatory)

```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov
```

Full project mypy. No `--no-verify`.

Live canaries (@pytest.mark.slow) run explicitly during Commits 3+4+7.

---

## 9. Notes on implementation

### Connector-type organization mirrors M1 cascade
Week 9 M1 monetary expansion used 3 connector types successfully:
- FRED OECD mirror (structural — all T1 countries have FRED fallback)
- TE-primary cascade (9/9 countries canonical)
- Native connectors (BoC/RBA/Riksbank/Norges Bank/Nationalbanken success; others gated/blocked)

Curves follow same tiered approach but simplified:
- US: FRED direct (existing, US-privileged — only country with full FRED yield spectrum + TIPS)
- EA: ECB SDW shared (consistent EA monetary union)
- Other T1: TE primary (vindicated Week 9); native fallback deferred (not all have yield curves via native API)

### Why not native fallback for curves?
Week 9 natives were Policy Rate focused. Yield curve spectrum (full tenor) via native connectors is complex:
- BoC Valet: yields available, but requires multi-series assembly
- RBA: yields in separate CSV tables, complex parse
- Riksbank Swea: yields in separate series, requires exploration
- etc.

**Pragmatic decision**: TE-primary for non-EA T1 yields. Native expansion Phase 2.5+.

### ECB SDW shared connector scale
6 EA members × ~10 tenors × daily = 60 series fetches per pipeline run. ECB SDW API rate-limits generous (public, no key). Cache layer reuses existing base connector pattern.

### Linker handling graceful
Not all T1 countries have inflation-indexed bonds at all tenors. Strategy:
- US: full (TIPS 5Y-30Y via FRED)
- DE/FR/IT: decent coverage via ECB SDW
- PT/ES/NL: limited (partial coverage flag)
- GB: has IL gilts but TE may not expose; TBD probe
- Others T1: defer, emit `LINKER_UNAVAILABLE` + `REAL_CURVE_DERIVED_ONLY` flags

Real curve compute falls back to DERIVED method (BEI-style) when linker unavailable.

### Post-merge operator actions
Service file update + daemon-reload VPS-side. Documented in Commit 6 + retro. Operator executes:
```bash
sudo sed -i 's|--country US|--all-t1|' /etc/systemd/system/sonar-daily-curves.service
sudo systemctl daemon-reload
sudo systemctl start sonar-daily-curves.service  # manual trigger to validate
journalctl -u sonar-daily-curves.service -f  # monitor
```

Tomorrow 07:30 WEST overlays.service will cascade T1-wide.

### Brief format v3 first use
Sections §10 (pre-merge checklist), §11 (merge execution), §12 (post-merge verification) new vs v2. Sprint CAL-138 is canary for format. Lessons from first use inform v3 refinement.

---

*End of Week 10 Sprint CAL-138 brief. 9+ commits. 16 T1 countries curves operational. First use of sprint_merge.sh script + brief format v3.*
