# Week 10 Day 1+ Sprint C — CAL-M2-T1-OUTPUT-GAP-EXPANSION (OECD EO)

**Target**: Ship OECD Economic Outlook connector for output gap data, upgrading M2 Taylor-gap index from scaffold to live compute across T1 countries. Replaces InsufficientDataError raised by build_m2_{country}_inputs scaffolds (Week 9 precedent).
**Priority**: HIGH (Phase 2 exit criterion; unblocks M2 sub-index cross-country, enabling MSC composite multi-country)
**Budget**: 4-6h CC
**Commits**: ~6-8
**Base**: branch `sprint-m2-output-gap-expansion` (isolated worktree `/home/macro/projects/sonar-wt-m2-output-gap`)
**Concurrency**: PARALELO with Sprint B (per-country ERP in flight). Zero primary file overlap.

**Brief format**: v3

---

## 1. Scope

In (3 tracks):

### Track 1 — OECD Economic Outlook connector (~2h)
- `src/sonar/connectors/oecd_eo.py` NEW — OECD Economic Outlook SDMX-JSON connector
- Endpoint: `https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO/...`
- Key series per country:
  - `EO.{COUNTRY}.GDPV.A` — real GDP annual
  - `EO.{COUNTRY}.GDPVTR.A` — trend GDP (HP-filtered, OECD-official)
  - Derived: `OUTPUT_GAP = (GDPV - GDPVTR) / GDPVTR * 100`
- **Alternative fallback**: IMF WEO (World Economic Outlook) if OECD EO sparse per country
- 15 T1 countries target (US + 6 EA members + GB/JP/CA/AU/NZ/CH/SE/NO/DK)

### Track 2 — M2 builders per-country live wiring (~2-3h)
- `src/sonar/indices/monetary/builders.py` MODIFY — replace `build_m2_{country}_inputs` scaffolds with live assemblers using OECD EO connector
- 7 priority T1 countries (Week 9 M1 expansion scope): CA, AU, NZ, CH, SE, NO, DK
- Plus US/DE/EA/GB/JP/IT/ES/FR/NL/PT already have M2 scaffold; upgrade to live (if viable)
- Flag emissions per country:
  - `{CODE}_M2_OECD_EO_LIVE` — primary path
  - `{CODE}_M2_IMF_WEO_FALLBACK` — fallback path
  - `{CODE}_M2_OUTPUT_GAP_SPARSE` — if empirical gaps

### Track 3 — Pipeline integration + tests (~1-2h)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY — verify M2 country dispatcher invokes live builders
- Cassettes per country (15 × 1 cassette = 15 new)
- Live canaries @pytest.mark.slow per country (15 new canaries)
- Combined wall-clock target ≤ 60s
- Retrospective per v3 format

Out:
- M3 market-expectations per-country (separate sprint; depends curves shipped)
- M4 FCI per-country (depends per-country financial conditions data)
- MSC composite multi-country (separate sprint post M1-M4 uniform)
- Output gap back-testing vs NBER / CEPR recessions (Phase 4 calibration)
- Historical output gap revision tracking (OECD revises each release — Phase 2.5 concern)

---

## 2. Spec reference

Authoritative:
- `docs/specs/indices/monetary/M2-taylor-gaps.md` — M2 methodology + output gap requirement
- `docs/backlog/calibration-tasks.md` — CAL-M2-T1-OUTPUT-GAP-EXPANSION entry
- `src/sonar/indices/monetary/builders.py` — existing M2 scaffolds per country (Week 9)
- `src/sonar/indices/monetary/m2_taylor_gaps.py` — core M2 compute (reuse uniform)
- `docs/planning/retrospectives/week9-sprint-*-report.md` — country-specific M2 deferral context

**Pre-flight requirement**: Commit 1 CC:
1. Read existing M2 methodology + scaffold patterns
2. Probe OECD EO SDMX endpoint availability per country:
   ```bash
   # OECD EO base probe
   curl -s "https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO/A.USA.GDPV+GDPVTR?format=jsondata&startPeriod=2020&endPeriod=2025" | head -100

   # Per country probe (ISO codes)
   for country in USA DEU FRA ITA ESP NLD PRT GBR JPN CAN AUS NZL CHE SWE NOR DNK; do
       echo "=== $country ==="
       curl -s "https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO/A.$country.GDPV+GDPVTR?format=jsondata&startPeriod=2023&endPeriod=2025" | head -30
   done
   ```
3. Document per-country:
   - Data availability (GDPV + GDPVTR both present?)
   - Historical range (OECD typically 1970+ for OECD members)
   - Revision frequency (2x/year typical)
4. Identify gaps — potential alternatives:
   - IMF WEO for non-OECD members (none in T1, but backup)
   - National statistics offices for country-specific trend GDP series
5. Decide OECD EO vs IMF WEO primary:
   - OECD EO: T1 OECD members (all 16 except EA aggregate)
   - EA aggregate: EuroArea total via ECB SDW GDP series + SONAR HP filter
6. Document Commit 1 body; narrow scope if OECD EO incomplete.

---

## 3. Concurrency — PARALELO with Sprint B (third paralelo of Day)

**Sprint C worktree**: `/home/macro/projects/sonar-wt-m2-output-gap`
**Sprint C branch**: `sprint-m2-output-gap-expansion`

**Sprint B (for awareness)**: per-country ERP live paths, worktree `/home/macro/projects/sonar-wt-erp-t1-per-country`, currently em C4 (Pipeline dispatch) — ~25min wall-clock in.

**Sprint A already merged** (f11a043 on main).

**File scope Sprint C**:
- `src/sonar/connectors/oecd_eo.py` NEW (primary)
- `src/sonar/indices/monetary/builders.py` MODIFY (primary — per-country M2 live)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (verify dispatcher + connector lifecycle)
- `tests/unit/test_connectors/test_oecd_eo.py` NEW
- `tests/unit/test_indices/monetary/test_builders.py` EXTEND (M2 per-country tests)
- `tests/integration/test_daily_monetary_*.py` EXTEND (live canaries per country)
- `tests/fixtures/cassettes/oecd_eo/` NEW cassettes per country
- `docs/backlog/calibration-tasks.md` MODIFY (close CAL-M2-T1-OUTPUT-GAP-EXPANSION; open sub-items if gaps)
- `docs/planning/retrospectives/week10-sprint-m2-output-gap-report.md` NEW

**Sprint B file scope** (for awareness, DO NOT TOUCH):
- `src/sonar/overlays/erp/` (primary)
- `src/sonar/pipelines/daily_cost_of_capital.py` (primary)
- `src/sonar/connectors/te.py` APPEND (equity index wrappers — **concurrent append zone possible if Sprint C needs TE for output gap fallback, but shouldn't**)

**Potential overlap zones**:
- `src/sonar/connectors/te.py` — Sprint B appends equity wrappers; Sprint C likely doesn't touch (OECD EO separate connector). **If Sprint C needs TE fallback, coordinate via rebase**.
- `src/sonar/indices/monetary/builders.py` — Sprint C primary; Sprint B doesn't touch M2 builders. **Zero overlap expected**.
- `src/sonar/pipelines/daily_monetary_indices.py` — Sprint C dispatcher work; Sprint B touches daily_cost_of_capital.py only. **Zero overlap**.
- `docs/backlog/calibration-tasks.md` — both modify; union-merge trivial.

**Rebase expected minor**: alphabetical merge priority → Sprint B ships before Sprint C if B finishes first. Sprint C rebases CAL file union-merge.

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed
- [ ] Workspace clean
- [ ] Pre-push gate green
- [ ] Branch tracking set
- [ ] Cassettes + canaries green
- [ ] Output gap values cross-checked vs OECD EO published estimates

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-m2-output-gap-expansion
```

---

## 4. Commits

### Commit 1 — Pre-flight + OECD EO connector scaffold

```
feat(connectors): OECD Economic Outlook SDMX connector + pre-flight

Pre-flight findings (Commit 1 body):
- OECD EO SDMX endpoint reachability: [per probe]
- Per-country data availability matrix:
  - USA: GDPV + GDPVTR present [YES/NO, historical range]
  - DEU/FRA/ITA/ESP/NLD/PRT: [per country]
  - GBR/JPN/CAN/AUS/NZL: [per country]
  - CHE/SWE/NOR/DNK: [per country]
- Data frequency: Annual (A) primary; Quarterly (Q) if available
- Revision frequency: 2x/year (May + November releases typical)
- EA aggregate handling: via `EA19`, `EA20`, or derived U2

Create src/sonar/connectors/oecd_eo.py:

"""OECD Economic Outlook SDMX connector.

Public data — no auth required. SDMX-JSON REST API.
Provides real GDP (GDPV) + trend GDP (GDPVTR) per country for output gap derivation.

Empirical probe findings (Commit 1):
- Base URL: https://sdmx.oecd.org/public/rest/data/
- Dataflow: OECD.ECO.MAD,DSD_EO@DF_EO
- Key pattern: {frequency}.{country_iso3}.{indicator}
- Indicators: GDPV (real GDP), GDPVTR (trend GDP), NAIRU (equilibrium unemployment)
- Format: SDMX-JSON
"""

OECD_EO_UA: Final = "SONAR/2.0 (m2-output-gap; https://github.com/hugocondesa-debug/sonar-engine)"
OECD_EO_BASE_URL: Final = "https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO/"

class OECDEOConnector(BaseConnector):
    """OECD Economic Outlook SDMX API."""

    CONNECTOR_ID = "oecd_eo"
    USER_AGENT = OECD_EO_UA

    async def fetch_gdp_series(
        self,
        country_iso3: str,  # "USA", "DEU", etc.
        indicator: str,  # "GDPV", "GDPVTR"
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[OECDEOObservation]:
        """Fetch annual GDP series from OECD EO.

        Returns list of observations for given country + indicator.
        Handles SDMX-JSON parsing.
        Raises DataUnavailableError if country + indicator unreachable.
        """

    async def fetch_output_gap(
        self,
        country_iso3: str,
        observation_year: int,
        history_years: int = 10,
    ) -> list[OutputGapObservation]:
        """Convenience: fetch GDPV + GDPVTR, compute output_gap.

        Returns annualized output_gap percent per year.
        Persistence: separate concern (builders.py).
        """

Tests:
- Unit: connector instantiation + URL building
- Unit: fetch_gdp_series USA happy path (mocked SDMX-JSON)
- Unit: fetch_output_gap computes gap correctly from GDPV + GDPVTR
- Unit: 404 → DataUnavailableError
- Unit: empty response → DataUnavailableError
- @pytest.mark.slow live canary: USA output_gap 2024 from OECD EO

Cassettes:
- tests/fixtures/cassettes/oecd_eo/usa_gdpv_gdpvtr_2024.json

Coverage oecd_eo.py ≥ 85%.
```

### Commit 2 — OECD EO per-country fetch + connector validation

```
feat(connectors): OECD EO per-country validation 16 T1 + ISO3 mapping

Extend oecd_eo.py with ISO3 country mapping:

OECD_EO_ISO_MAP: Final = {
    "US": "USA",
    "DE": "DEU",
    "FR": "FRA",
    "IT": "ITA",
    "ES": "ESP",
    "NL": "NLD",
    "PT": "PRT",
    "GB": "GBR",
    "JP": "JPN",
    "CA": "CAN",
    "AU": "AUS",
    "NZ": "NZL",
    "CH": "CHE",
    "SE": "SWE",
    "NO": "NOR",
    "DK": "DNK",
}

EA handling special case — OECD EO uses EA19/EA20/EURO_AREA variants; confirm
during probe + hardcode mapping.

Per-country helper:
async def fetch_country_output_gap(
    self,
    country_iso2: str,
    observation_date: date,
    history_years: int = 10,
) -> list[OutputGapObservation]:
    """Convenience per ISO2 code.

    Maps iso2 → iso3 via OECD_EO_ISO_MAP.
    Raises ValueError if iso2 not in map.
    """

Tests:
- Unit: fetch_country_output_gap per T1 country (mocked)
- Unit: ValueError for non-T1 iso2
- @pytest.mark.slow live canaries for 3-4 sample countries (US + DE + JP)

Cassettes per country.

Coverage maintained.
```

### Commit 3 — M2 builders per-country live wiring (Week 9 countries)

```
feat(indices): M2 live wiring for 7 Week-9 T1 countries

Upgrade build_m2_{country}_inputs scaffolds from Week 9 country sprints
to live OECD EO integration. Priority countries: CA, AU, NZ, CH, SE, NO, DK.

Per country, replace scaffold raising InsufficientDataError with:

async def build_m2_ca_inputs(
    fred: FredConnector,
    te: TEConnector,
    observation_date: date,
    *,
    oecd_eo: OECDEOConnector | None = None,
) -> M2Inputs:
    """Build M2 CA inputs via OECD EO output gap.

    Cascade:
    1. OECD EO primary — CA_M2_OECD_EO_LIVE flag
    2. IMF WEO fallback — CA_M2_IMF_WEO_FALLBACK flag (if OECD gap)
    3. Raise InsufficientDataError if both unavailable
    """
    flags = []
    output_gap = None

    if oecd_eo:
        try:
            obs = await oecd_eo.fetch_country_output_gap(
                "CA", observation_date
            )
            if obs:
                output_gap = obs[-1].value  # most recent annual
                flags.append("CA_M2_OECD_EO_LIVE")
        except (DataUnavailableError, ConnectorError):
            flags.append("CA_M2_OECD_EO_UNAVAILABLE")

    if output_gap is None:
        raise InsufficientDataError(
            "CA M2 requires output gap; OECD EO unavailable."
        )

    # Build M2Inputs per spec (reuse existing US/DE logic)
    ...

Replicate pattern for:
- build_m2_au_inputs (AU)
- build_m2_nz_inputs (NZ)
- build_m2_ch_inputs (CH)
- build_m2_se_inputs (SE)
- build_m2_no_inputs (NO)
- build_m2_dk_inputs (DK)

Tests per country — unit (happy + unavailable + fallback) + @pytest.mark.slow
canaries.

Coverage builders.py M2 per-country paths ≥ 90%.
```

### Commit 4 — M2 builders per-country live wiring (pre-Week-9 countries)

```
feat(indices): M2 live wiring for remaining T1 countries

Upgrade M2 for pre-Week-9 T1 countries where scaffold exists but not yet live:
- US (if not already live from Phase 1)
- DE, FR, IT, ES, NL, PT, EA (EA members + aggregate)
- GB, JP

Per country, upgrade from scaffold to live or enhance existing US path.

EA aggregate special case:
- Uses ECB SDW GDP aggregate + SONAR HP filter if OECD EO lacks EA aggregate
- Or uses OECD EO EA19/EA20 directly if available

Tests per country — unit + @pytest.mark.slow canaries.

Coverage maintained.
```

### Commit 5 — Pipeline integration + connector lifecycle

```
feat(pipelines): daily_monetary_indices OECD EO connector integration

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Add OECDEOConnector to _build_live_connectors():
   - Instantiate + include in connectors_to_close lifecycle
   - Pass to builders per country

2. Verify M2 country dispatcher routes to live builders:
   - Before: scaffolds raised InsufficientDataError
   - After: live OECD EO path + flag emission

3. --all-t1 execution validates:
   - US + 6 EA members + 9 non-EA T1 = 16 countries
   - Per country: M2 persistence attempted; InsufficientDataError caught
     + logged + skipped gracefully (per --all-t1 mode)

Integration smoke @slow:
tests/integration/test_daily_monetary_m2_multicountry.py:

@pytest.mark.slow
def test_daily_monetary_m2_t1_all_countries():
    """Full pipeline for 16 T1 countries M2 2024-12-31.

    Expected:
    - ≥ 12 countries persist M2 row (OECD EO typically covers all T1 except edge cases)
    - Flag {CODE}_M2_OECD_EO_LIVE present
    - M2 output_gap values reasonable (-5% ≤ gap ≤ +5% typical)"""

Wall-clock ≤ 60s combined.

Coverage maintained.
```

### Commit 6 — CAL closures + retrospective

```
docs(planning+backlog): Sprint C M2 T1 output gap retrospective

CAL-M2-T1-OUTPUT-GAP-EXPANSION CLOSED (resolution):
- OECD EO connector shipped
- M2 live for 7 Week-9 priority countries (CA/AU/NZ/CH/SE/NO/DK)
- M2 live for pre-Week-9 countries (DE/FR/IT/ES/NL/PT/EA/GB/JP + US)
- 16 T1 countries M2 operational

New CAL items if any gaps:
- CAL-M2-EA-AGGREGATE-GDP (if EA aggregate output gap problematic)
- CAL-M2-REVISION-TRACKING (Phase 2.5 — OECD revises 2x/year; audit drift)

Retrospective per v3 format:
docs/planning/retrospectives/week10-sprint-m2-output-gap-report.md

Content:
- OECD EO connector outcome (data quality per country)
- M2 output gap per country (values + historical context 2008/2020 recession markers)
- Cross-val vs OECD published output_gap estimates
- Flag emissions matrix per country
- Coverage delta
- Production impact: daily_monetary_indices M2 live for 16 T1 countries (previously scaffold)
- MSC composite multi-country now unblocked (next sprint candidate)
- §10 pre-merge checklist + §11 merge via script
- Paralelo with Sprint B: zero file conflicts (separate domains)
- Paralelo with Sprint A (shipped earlier Day 1): independent
```

---

## 5. HALT triggers (atomic)

0. **OECD EO empirical probe reveals sparse per-country coverage** — scope narrow; open CAL-M2-{COUNTRY}-SPARSE per country lacking.
1. **OECD EO SDMX format unexpected** — if API returns structure different than probed, investigate. HALT + surface.
2. **EA aggregate unavailable in OECD EO** — use ECB SDW GDP + SONAR HP filter OR scope narrow EA from sprint.
3. **Output gap values implausible** — if gap outside [-10%, +10%] typical range, investigate data source. HALT.
4. **HP filter / trend methodology divergence** — OECD uses own HP filter parameters; document + document deviation from M2 spec if any.
5. **TE equity probe conflict** (Sprint B zone) — Sprint C should NOT touch te.py. If scope requires, coordinate via rebase.
6. **Cassette count < 10** — HALT.
7. **Live canary wall-clock > 70s combined** — optimize OR split.
8. **Pre-push gate fails** — fix before push.
9. **No `--no-verify`**.
10. **Coverage regression > 3pp** — HALT.
11. **Push before stopping** — script mandates; brief v3 §10.
12. **Sprint B file conflict** — CAL file union-merge trivial; te.py if C needs, coordinate.
13. **US M2 regression** — if existing US M2 compute breaks post-refactor, HALT + fix.

---

## 6. Acceptance

### Global sprint-end
- [ ] OECD EO connector shipped + tested (15 T1 countries mapped)
- [ ] M2 live for 7 Week-9 priority countries (CA/AU/NZ/CH/SE/NO/DK)
- [ ] M2 live for pre-Week-9 T1 countries (10 additional: DE/FR/IT/ES/NL/PT/EA/GB/JP + verify US)
- [ ] 16 T1 countries M2 operational
- [ ] Pipeline integration OECD EO connector lifecycle
- [ ] Cassettes ≥ 10 shipped
- [ ] Live canaries ≥ 10 @pytest.mark.slow PASS combined ≤ 60s
- [ ] CAL-M2-T1-OUTPUT-GAP-EXPANSION CLOSED with commit refs
- [ ] Coverage oecd_eo.py ≥ 85%, builders.py M2 paths ≥ 90%
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] §10 Pre-merge checklist executed
- [ ] Merge via `sprint_merge.sh`
- [ ] Retrospective shipped per v3 format

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-m2-output-gap-report.md`

**Final tmux echo**:
```
SPRINT C M2 OUTPUT GAP DONE: N commits on branch sprint-m2-output-gap-expansion

OECD EO connector shipped. M2 live for N T1 countries (target 16):
  [list per country with values + flag per country]

Output gap values 2024:
  US: [value]% (flag: M2_OECD_EO_LIVE)
  DE: [value]%
  ...

Cross-val vs OECD published estimates: [within tolerance]

CAL-M2-T1-OUTPUT-GAP-EXPANSION CLOSED.

Production impact: daily_monetary_indices M2 index live across T1 (previously scaffold).
MSC composite multi-country unblocked (next sprint candidate Week 10 Day 2 or Week 11).

Paralelo context:
- Sprint A (shipped earlier Day 1): EA periphery curves HALT-narrow
- Sprint B (in flight): per-country ERP T1 live paths

Merge: ./scripts/ops/sprint_merge.sh sprint-m2-output-gap-expansion

Artifact: docs/planning/retrospectives/week10-sprint-m2-output-gap-report.md
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

Live canaries (@pytest.mark.slow) run explicitly during Commits 1+2+5.

---

## 9. Notes on implementation

### OECD EO vs alternatives
OECD EO is authoritative for output_gap (official HP-filter with consistent methodology cross-country). IMF WEO viable but less frequent updates. National statistics offices country-specific but non-uniform.

### Revision behavior
OECD EO revises historical values 2x/year. M2 compute uses most-recent estimate (not vintage). Future Phase 2.5: revision tracking (CAL-M2-REVISION-TRACKING).

### EA aggregate handling
EA aggregate output_gap may require:
- OECD EO EA19/EA20 if available
- ECB SDW GDP aggregate + SONAR HP filter (consistent methodology)
- Derived from member-country aggregation (weighted average)

Probe determines best path.

### Per-country historical coverage
OECD EO typically 1970+ for OECD members. Smaller markets (NZ, CH) may start later. Document per country.

### Paralelo discipline (3rd paralelo of Day 1)
Sprint A merged. Sprint B in flight. Sprint C is 3rd paralelo.

File scopes zero primary overlap:
- Sprint B: overlays/erp/, daily_cost_of_capital.py, te.py (equity wrappers)
- Sprint C: connectors/oecd_eo.py, indices/monetary/builders.py M2 paths, daily_monetary_indices.py

Shared secondary: docs/backlog/calibration-tasks.md. Union-merge trivial.

### MSC composite unlock
Post-sprint, all 4 M-indices (M1, M2, M3, M4) candidate for cross-country composite:
- M1: shipped Week 9 (16 countries)
- M2: THIS SPRINT (16 countries target)
- M3: Phase 2 pending (depends curves shipped T1 uniform — CAL-CURVES-EA-PERIPHERY-* open)
- M4: FCI per country — Phase 2.5 scope

M2 ship unblocks MSC multi-country when M3/M4 catch up (Week 11+).

### Script merge
Dogfooded Day 1 Week 10. If HALT, surface + do not intervene manually.

---

*End of Sprint C brief. 6-8 commits. OECD EO connector + M2 live 16 T1 countries. Paralelo-ready with Sprint B.*
