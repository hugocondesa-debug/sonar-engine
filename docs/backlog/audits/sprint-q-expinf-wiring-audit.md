# Sprint Q — EXPINF live-assembler wiring pre-flight audit

**Data**: Week 11 Day 1 (2026-04-24)
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy)
**Brief**: `docs/planning/week11-sprint-q-cal-expinf-live-assembler-wiring-brief.md`
**Parent audit**: `docs/backlog/audits/sprint-o-m3-exp-inflation-audit.md` (Week 10 Day 3)
**DB target**: `sqlite:///./data/sonar-dev.db` (symlink to `sonar-engine/data/sonar-dev.db`)

---

## §1 Brief premise vs codebase reality — executive summary

The brief (§2.1.3 expected findings + §5.1 item 4 acceptance) anticipates **≥3 countries promotable DEGRADED→FULL post-wiring** (US/EA/GB minimum) because Sprint O §4 decision matrix projected "FULL (Bund linkers + ECB SPF)" for DE, "FULL (HICPxT linkers + ECB SPF)" for EA, "FULL (ILGs + BoE SPF)" for GB once the upstream wiring lands.

Reality (§3 connector inventory): **only the FRED connector surfaces live BEI + survey endpoints, and FRED's BEI/survey paths support country=US exclusively** (`fetch_bei_series`, `fetch_survey_inflation` both raise `ValueError` for non-US codes). Bundesbank / Banca d'Italia / Banco España / Banque de France `fetch_yield_curve_linker` methods are **stubs** raising deferral errors; BoE / BoJ / BoC / ECB SDW expose **no** BEI/SPF endpoints in the connector surface. The `exp_inflation_{bei,swap,survey,derived,canonical}` DB tables exist (alembic 004) but have **no ORM models, no writers, and zero rows** — they are dormant infrastructure, not the canonical EXPINF read path.

**Revised Sprint Q deliverable**: wire the US-only live EXPINF path (FRED BEI + FRED survey → `build_expected_inflation_bundle` → `OverlayBundle.expected_inflation` kwargs → `build_canonical` → `IndexResult(EXPINF_CANONICAL)` → `index_values` → M3 classifier reads row → **US promotes DEGRADED→FULL**). The remaining 8 T1 countries (DE/EA/GB/JP/CA/IT/ES/FR) **stay DEGRADED** — wiring is a no-op for them because no live BEI/survey data is sourceable today. Per-country CAL tickets already exist (Sprint O §7) to land the missing connectors in follow-up sprints.

Realistic Sprint Q scorecard: **1/9 T1 FULL (US) post-merge**. Brief §5.1 item 4 "≥3 FULL" is revised down to "≥1 FULL (US)" — remaining 8 T1 countries correctly stay DEGRADED with existing `M3_EXPINF_MISSING` or `{CC}_M3_BEI_*_EXPECTED` sparsity flags.

---

## §2 Confirmed wiring gap — `live_assemblers.py:625`

### 2.1.1 Locate live_assemblers + verify EXPINF gap

```
$ find src/sonar/ -type f -name "*.py" | xargs grep -l "live_assembler\|live_assemble\|expected_inflation.*=.*None"
src/sonar/pipelines/daily_overlays.py
src/sonar/overlays/live_assemblers.py
```

Single hard-coded None confirmed at `src/sonar/overlays/live_assemblers.py:625` inside `LiveInputsBuilder._run`:

```python
return OverlayBundle(
    country_code=country_code,
    observation_date=observation_date,
    erp=erp,
    crp=crp_kwargs,
    rating=rating_kwargs,
    expected_inflation=None,  # Phase-2 scope; not wired in Sprint 7F.
)
```

Downstream consequence (`src/sonar/pipelines/daily_overlays.py:438-442`):

```python
async def _compute_expected_inflation(bundle: OverlayBundle) -> tuple[IndexResult | None, str | None]:
    if bundle.expected_inflation is None:
        return None, "no inputs provided"
    ...
```

Short-circuits the EXPINF overlay → no `EXPINF_CANONICAL` `IndexResult` → no row persisted to `index_values` → `m3_country_policies.classify_m3_compute_mode` query at line 166 returns None → mode = `DEGRADED` with flag `M3_EXPINF_MISSING`.

**No other sites wire `expected_inflation=None`** in live/production paths. Tests seed the field via `StaticInputsBuilder` + `build_expected_inflation_bundle` (e.g. `tests/integration/test_daily_overlays_live.py:132-144` for US, 185-199 for DE, 225-239 for PT) — test-only, never exercised from the systemd daily pipeline.

### 2.1.4 Canonical-inflation consumer shape

`OverlayBundle.expected_inflation` is typed `dict[str, Any] | None`, holding **kwargs for `build_canonical`** (`src/sonar/overlays/expected_inflation.py:232`):

```python
def build_canonical(
    *,
    country_code: str,
    observation_date: date_type,
    bei: ExpInfBEI | None = None,
    survey: ExpInfSurvey | None = None,
    bc_target_pct: float | None = None,
) -> ExpInfCanonical: ...
```

The companion assembler `build_expected_inflation_bundle` (`src/sonar/pipelines/daily_overlays.py:312`) accepts raw primitives (`nominal_yields`, `linker_real_yields`, `survey_horizons`, `survey_name`, `survey_release_date`) and emits the kwargs dict directly. Sprint Q must source those primitives from live connectors per country, then compose the kwargs dict and drop it into `OverlayBundle.expected_inflation`.

**No M3 builder signature change needed** — classifier already reads `IndexValue(index_code='EXPINF_CANONICAL')` rows from `index_values`; the fix is wholly upstream at bundle assembly.

---

## §3 EXPINF tables inventory + per-country coverage (§2.1.2 + §2.1.3)

### 3.1 Schema vs ORM vs writers

| Table | Schema (alembic 004) | ORM model (`src/sonar/db/models.py`) | Writers in `src/` | Rows in dev DB |
|---|---:|---:|---:|---:|
| `exp_inflation_bei` | ✓ | **none** | **none** | 0 |
| `exp_inflation_swap` | ✓ | **none** | **none** | 0 |
| `exp_inflation_survey` | ✓ | **none** | **none** | 0 |
| `exp_inflation_derived` | ✓ | **none** | **none** | 0 |
| `exp_inflation_canonical` | ✓ | **none** | **none** | 0 |

**Verdict**: the `exp_inflation_*` schema family is **dormant infrastructure** shipped by migration 004 without ORM, writers, or readers. The brief's §2.3 loader proposal of "Query `exp_inflation_canonical` primary source / Fallback hierarchy: canonical → derived → (BEI + swap synthesis) → survey" **does not match the codebase**. The actual canonical read path for M3 is `index_values` WHERE `index_code='EXPINF_CANONICAL'` (see `m3_country_policies.py:33` import of `EXPINF_INDEX_CODE`).

### 3.2 `index_values` EXPINF coverage

```sql
SELECT country_code, MAX(date), COUNT(*) FROM index_values WHERE index_code='EXPINF_CANONICAL' GROUP BY country_code;
-- 0 rows
```

Zero rows because `_compute_expected_inflation` never emits (per §2 short-circuit).

### 3.3 Supporting upstream data — what Sprint Q can actually feed the EXPINF overlay

| Source | Rows available | T1 countries present | Usable for EXPINF |
|---|---:|---|---|
| `yield_curves_spot` (nominal NSS fits) | 11 countries × 2-4 dates | US/DE/EA/GB/JP/CA/IT/ES/FR/PT/AU | yes (nominal leg for BEI subtraction) |
| `yield_curves_forwards` | same 11 | same | **not consumed by EXPINF** (M3 consumes directly) |
| `yield_curves_real` (linker-derived real) | **4 rows, US only** | US only | yes — but we prefer FRED market BEI (`T5YIE`/`T10YIE`) for US, so this is moot |
| `FredConnector.fetch_bei_series` | live (FRED API) | **US only** (raises ValueError otherwise) | yes — **primary US BEI source** |
| `FredConnector.fetch_survey_inflation` | live (FRED API) | **US only** (MICH + SPF EXPINF10YR) | yes — **primary US survey source** |
| `BundesbankConnector.fetch_yield_curve_linker` | stub — raises `DataUnavailableError` | DE only if implemented | **no** (CAL-CURVES-DE-LINKER open) |
| `BancaDItaliaConnector.fetch_yield_curve_linker` | stub | IT | **no** |
| `BancoEspañaConnector.fetch_yield_curve_linker` | stub | ES | **no** |
| `BanqueDeFranceConnector.fetch_yield_curve_linker` | stub | FR | **no** |
| `EcbSdwConnector` | no BEI / no SPF endpoint (explicit docstring §373: "The `YC` dataflow has no inflation-indexed counterpart") | — | **no** |
| `BoEDatabaseConnector` | `fetch_bank_rate` / `fetch_gilt_10y` / `fetch_balance_sheet` only | — | **no** |
| `BoJConnector` / `BoCConnector` | no inflation endpoints in current surface | — | **no** |
| `TEConnector.fetch_ea_inflation_forecast_aggregate` | live — 12m TE forecast, used by M2 EA; docstring §1982 explicitly defers ECB SPF EXPINF wiring to Phase 2+ | EA | **no** (wrong shape for M3 tenor structure) |

**Conclusion**: US is the only T1 country with a live EXPINF source path today. DE/EA/GB/JP/CA/IT/ES/FR require new connector work before DEGRADED→FULL is achievable.

---

## §4 Per-country Sprint Q classification (revised matrix)

Column 4 is the Sprint O *aspirational* projection; column 5 is the Sprint Q *shippable* reality.

| Country | Forwards | EXPINF live source | Sprint O projection | Sprint Q shippable | Expected mode post-Q | Flags post-Q |
|---|---|---|---|---|---|---|
| **US** | ✓ | FRED BEI + FRED survey | FULL | **FULL** | **FULL** | `US_M3_T1_TIER`, `M3_FULL_LIVE` |
| DE | ✓ | Bundesbank linker stub | FULL | no-op (wiring unchanged) | DEGRADED | `DE_M3_T1_TIER`, `M3_EXPINF_MISSING` |
| EA | ✓ | no endpoint | FULL | no-op | DEGRADED | `EA_M3_T1_TIER`, `M3_EXPINF_MISSING` |
| GB | ✓ | no endpoint | FULL | no-op | DEGRADED | `GB_M3_T1_TIER`, `M3_EXPINF_MISSING` |
| JP | ✓ | no endpoint | DEGRADED (expected) | no-op | DEGRADED | `JP_M3_T1_TIER`, `JP_M3_BEI_LINKER_THIN_EXPECTED`, `M3_EXPINF_MISSING` |
| CA | ✓ | no endpoint | DEGRADED (expected) | no-op | DEGRADED | `CA_M3_T1_TIER`, `CA_M3_BEI_RRB_LIMITED_EXPECTED`, `M3_EXPINF_MISSING` |
| IT | ✓ | Banca d'Italia stub | DEGRADED (expected) | no-op | DEGRADED | `IT_M3_T1_TIER`, `IT_M3_BEI_BTP_EI_SPARSE_EXPECTED`, `M3_EXPINF_MISSING` |
| ES | ✓ | Banco España stub | DEGRADED (expected) | no-op | DEGRADED | `ES_M3_T1_TIER`, `ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED`, `M3_EXPINF_MISSING` |
| FR | ✓ | Banque de France stub | FULL-candidate | no-op | DEGRADED | `FR_M3_T1_TIER`, `M3_EXPINF_MISSING` |

**Δ vs brief §5.1 item 4 acceptance target**: brief expected ≥3 FULL; Sprint Q delivers 1 FULL (US). Remaining 8 stay DEGRADED correctly with unchanged flag sets.

---

## §5 HALT analysis

### 5.1 Brief §4 HALT triggers evaluated

| Trigger | Fires? | Reasoning |
|---|---|---|
| HALT-0 "All 9 T1 have zero EXPINF coverage" (exp_inflation_* tables empty) | **false positive** | Tables are dormant infrastructure, not the canonical read path. M3 reads `index_values`. Brief mis-specified source. |
| HALT-0 "EXPINF table schemas incompatible" | no | Schemas are consistent across the 5 tables (UUID + country + date + methodology_version + JSON bodies). |
| HALT-material "live_assemblers.py doesn't exist or structure different" | **partial** | live_assemblers.py exists at expected path but **factual premise about available BEI/survey connectors for DE/EA/GB/FR is wrong** — Sprint Q rescoped to US-only wiring in-session rather than deferring the whole sprint. Decision justified below. |
| HALT-material "M3 builder signature doesn't accept expected_inflation" | no | Builder reads from `index_values`; no signature coupling at the builder surface. |
| HALT-material "EXPINF loader produces nonsensical values" | TBD | Will evaluate empirically during C2-C3 via US backfill smoke; if FRED returns negative BEI the test suite catches it. |
| HALT-scope "new EXPINF connectors" | respected | Sprint Q adds **zero** new connectors; only wires the already-shipped FRED BEI/survey endpoints into LiveConnectorSuite. |
| HALT-scope "touch E1/E3/E4" | respected | Out of scope — no touch. |
| HALT-scope "back-modify Sprint O classifier extensively" | respected | No classifier changes expected; the classifier is correct as-is — it reads `index_values`, and once the US row appears it returns FULL automatically. |

### 5.2 Rescope decision — US-only wiring (rationale)

Brief §7 "Audit-first discipline" permits pause+report-before-proceed when audit reveals different structure than Sprint O claimed. Brief §9 "ship partial (C1-C4 + backfill partial) + retro documenting residual gaps for Sprint Q.1 continuation" also permits partial delivery. Rescope to US-only because:

1. **US FULL is achievable today** — FRED BEI + survey connectors exist + are tested elsewhere in the codebase (`fetch_bei_series`, `fetch_survey_inflation` called from tests but never wired to live_assemblers).
2. **Per-country BEI/survey connector work is explicitly out of scope** (§4 scope lock: "Zero new connectors").
3. **Post-Q pattern holds** — once the DE/EA/GB/FR connectors land in future sprints, only the per-country branch of the new US loader needs extending; the wiring plumbing into `OverlayBundle.expected_inflation` is shared.
4. **Tier A acceptance §5.1 item 4 must be revised downward** ("≥1 FULL (US)" instead of "≥3 FULL"); retro documents the gap.
5. **Tier B systemd verification is unaffected** — the command still emits `m3_compute_mode` 9 times per run; one is FULL, eight are DEGRADED with existing flags.

---

## §6 Implementation plan derived from audit

### 6.1 C2 — `exp_inflation_loader.py`

New module `src/sonar/indices/monetary/exp_inflation_loader.py` exposes:

```python
async def load_live_exp_inflation_kwargs(
    country_code: str,
    observation_date: date,
    *,
    fred: FredConnector | None,
) -> dict[str, Any] | None:
    """Return `build_canonical` kwargs dict for (country, date), or None if no live source."""
```

- `country_code == "US"` + `fred is not None` → call `fred.fetch_bei_series("US", date)` + `fred.fetch_survey_inflation("US", date)`; compose `ExpInfBEI` (via `compute_bei_us`) + `ExpInfSurvey` (via `compute_survey_us`); return `{"country_code": "US", "observation_date": date, "bei": ..., "survey": ..., "bc_target_pct": 0.02}`.
- Any other country → return `None` (graceful fallback, classifier emits `M3_EXPINF_MISSING`).
- Gracefully handle `DataUnavailableError`, `ValueError`, `httpx.HTTPError` → log at `info` level, return `None`.

The **`ExpInflationInput` dataclass + multi-source fallback hierarchy from brief §2.3** is dropped in this revision — the kwargs-dict shape is already the contract at `OverlayBundle.expected_inflation: dict[str, Any] | None`; adding a wrapper dataclass is premature abstraction.

### 6.2 C3 — live_assemblers refactor

- Add `fred: FredConnector | None = None` to `LiveConnectorSuite` (dataclass field).
- In `LiveInputsBuilder._run`, replace line 625 `expected_inflation=None` with:

```python
expinf_kwargs = None
try:
    expinf_kwargs = await load_live_exp_inflation_kwargs(
        country_code, observation_date, fred=self._connectors.fred,
    )
except _ConnectorErrors as exc:
    log.warning("live_assemblers.expinf_error", country=country_code, error=str(exc))
```

- In `daily_overlays._live_inputs_builder_factory` (line 696-702), add `fred=fred` to the `LiveConnectorSuite(...)` call.

### 6.3 C4 — M3 classifier

**No change**. Classifier already does the right thing: reads `index_values(EXPINF_CANONICAL)`, returns FULL if row present + confidence ≥ threshold. Once US row lands via C3, classifier returns FULL for US automatically.

### 6.4 C5 — regression tests

Tests under `tests/unit/test_pipelines/test_expinf_wiring.py`:

- `test_load_live_exp_inflation_us_full_path` — mock `FredConnector` returns BEI + survey observations → loader returns valid kwargs dict with `bei` + `survey` populated.
- `test_load_live_exp_inflation_us_bei_only` — survey fetch raises `DataUnavailableError` → loader returns kwargs with `bei` only, `survey=None`.
- `test_load_live_exp_inflation_non_us_returns_none` — any country other than US → returns `None`.
- `test_load_live_exp_inflation_fred_none_returns_none` — `fred=None` → returns `None`.
- `test_load_live_exp_inflation_http_error_returns_none` — `httpx.HTTPError` propagates as `None` (graceful).
- `test_live_assemblers_wires_expinf_for_us` — build `LiveConnectorSuite` with fake FRED → `OverlayBundle.expected_inflation` is non-None for US.
- `test_live_assemblers_non_us_expinf_stays_none` — assembler with FRED returns `None` for DE/EA/GB (graceful).

Brief's "9-country parametric" test dropped — no coverage to parametrize, and asserting 8 DEGRADED outcomes adds no signal over the single non-US test.

### 6.5 C6 — backfill + verify

```bash
for date in 2026-04-21 2026-04-22 2026-04-23 2026-04-24; do
  uv run python -m sonar.pipelines.daily_overlays --all-t1 --date "$date" --backend live ...
  uv run python -m sonar.pipelines.daily_monetary_indices --indices m3 --all-t1 --date "$date"
done
```

Order matters — daily_overlays must run first to persist EXPINF_CANONICAL rows before the M3 classifier reads them.

Verify:

```bash
sqlite3 data/sonar-dev.db "SELECT country_code, COUNT(*) FROM index_values WHERE index_code='EXPINF_CANONICAL' GROUP BY country_code;"
# Expected: US with 4 rows (one per date).
```

### 6.6 C7 — CAL ledger updates

- Close `CAL-EXPINF-LIVE-ASSEMBLER-WIRING` with a note "US-only wiring shipped; DE/EA/GB/FR/JP/CA/IT/ES deferred pending per-country connector work".
- Open (or reaffirm) per-country connector CALs:
  - `CAL-EXPINF-DE-BUNDESBANK-LINKER` — Bundesbank inflation-linked Bund series (`BBSSY` family per existing stub docstring).
  - `CAL-EXPINF-EA-ECB-SPF` — ECB SDW SPF endpoint (explicit deferral in `ecb_sdw.py:373` + `te.py:1982`).
  - `CAL-EXPINF-GB-BOE-ILG-SPF` — BoE inflation-linked gilts + BoE SPF.
  - `CAL-EXPINF-FR-BDF-OATI-LINKER` — OATi/OATei.
  - `CAL-EXPINF-EA-PERIPHERY-LINKERS` (already open per Sprint O §7 — reaffirm).

ADR-0011 Principle 8 (observability-before-wiring anti-pattern): **defer** — the US-only shippability already validates the pattern Sprint O established; writing a principle now would be over-promoted. Revisit if E1/E3/E4 sprints hit the same premise gap.

---

## §7 Audit sign-off

**Go/no-go for C2+**: **GO with rescope** — ship US-only wiring; retro documents the reality gap vs brief; CALs opened for per-country followup.

Revised Tier A acceptance targets:

1. Audit doc present ≥60 lines — this file ✓.
2. EXPINF loader implementation present — C2.
3. `expected_inflation=None` hard-code count = 0 in `live_assemblers.py` — C3.
4. **`uv run python -m sonar.pipelines.daily_monetary_indices --indices m3 --all-t1 --date 2026-04-23 | grep -c FULL` ≥ 1** (revised down from ≥3) — US only.
5. Bash wrapper smoke passes — C6.
6. Regression suite clean — C5.
7. Pre-commit clean double-run — standard.

*End of audit. 1 structural finding (brief premise mismatch), 1 shippable wiring (US), 5 CAL tickets reaffirmed/opened.*
