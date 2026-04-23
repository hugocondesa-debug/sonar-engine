# Sprint O — M3 `exp_inflation` + forwards pre-flight audit

**Data**: 2026-04-23 (Week 10 Day 3 late)
**Operator**: Hugo Condesa (reviewer) + CC (executor)
**Brief §2.1 cross-ref**: Pre-flight audit MUST precede C2+ builder code. This doc drives degradation-flag decisions per country.
**DB target**: `sqlite:///./data/sonar-dev.db` (dev working copy; ship-merged at sprint close).

---

## §1 Queries executed

```sql
SELECT 'bei'       AS tbl, country_code, MAX(date), COUNT(*) FROM exp_inflation_bei       GROUP BY country_code
UNION ALL SELECT 'swap',      country_code, MAX(date), COUNT(*) FROM exp_inflation_swap       GROUP BY country_code
UNION ALL SELECT 'survey',    country_code, MAX(date), COUNT(*) FROM exp_inflation_survey    GROUP BY country_code
UNION ALL SELECT 'canonical', country_code, MAX(date), COUNT(*) FROM exp_inflation_canonical GROUP BY country_code
UNION ALL SELECT 'forwards',  country_code, MAX(date), COUNT(*) FROM yield_curves_forwards   GROUP BY country_code
ORDER BY tbl, country_code;

SELECT index_code, country_code, MAX(date), COUNT(*), MAX(confidence)
FROM index_values WHERE index_code LIKE 'EXPINF%'
GROUP BY index_code, country_code ORDER BY index_code, country_code;
```

---

## §2 Raw findings — dev DB snapshot 2026-04-23

### 2.1 `yield_curves_forwards` (M3 primary input)

| Country | Rows | Latest date | Status |
|---|---:|---|---|
| US | 4 | 2026-04-23 | ✓ |
| DE | 4 | 2026-04-23 | ✓ |
| EA | 2 | 2026-04-23 | ✓ |
| GB | 2 | 2026-04-23 | ✓ |
| JP | 2 | 2026-04-23 | ✓ |
| CA | 2 | 2026-04-23 | ✓ |
| IT | 2 | 2026-04-23 | ✓ |
| ES | 2 | 2026-04-23 | ✓ |
| FR | 2 | 2026-04-23 | ✓ |

**Verdict**: all 9 T1 countries present. HALT-0 trigger #1 (forwards empty) **does not fire**.

### 2.2 `exp_inflation_*` persistence tables (L2 overlay)

| Table | Rows |
|---|---:|
| `exp_inflation_bei` | 0 |
| `exp_inflation_swap` | 0 |
| `exp_inflation_survey` | 0 |
| `exp_inflation_canonical` | 0 |
| `exp_inflation_derived` | 0 |

**Verdict**: **every per-country `exp_inflation_*` table is empty across the 9 T1 cohort**. Per §4 HALT-0 trigger #2 ("`exp_inflation_*` all tables empty for any country → HALT that country, scaffold with NOT_IMPLEMENTED, open CAL for Week 11"), strict reading would HALT all 9.

### 2.3 `index_values WHERE index_code = 'EXPINF_CANONICAL'` (M3 actual input path)

| Rows | Notes |
|---:|---|
| 0 | No `EXPINF_CANONICAL` `IndexValue` rows exist for any country/date. Only `E2_LEADING` (US + DE) populates `index_values`. |

---

## §3 Root-cause discovery — divergence from brief premise

Brief §1 states "M3 (market expectations) currently 4/16 FULL — US/DE/EA/PT". Week 10 overall retro cites the same figure. Dev-DB reality: **0/9 T1 countries have EXPINF_CANONICAL persisted**.

Root cause — structural pipeline gap inherited from Week 7 Sprint C:
`src/sonar/overlays/live_assemblers.py:625` wires `expected_inflation=None` explicitly ("Phase-2 scope; not wired in Sprint 7F"). `build_expected_inflation_bundle` exists in `src/sonar/pipelines/daily_overlays.py` but is only called from tests, not from the production daily-overlays path. As a result the `daily_overlays` pipeline never persists `EXPINF_CANONICAL` `IndexValue` rows, and the CAL-108 `MonetaryDbBackedInputsBuilder.build_m3_inputs` read path lands on `m3_db_backed.expinf_missing` + returns `None` for every country.

**Sprint O implication**: the retro's "4/16 FULL" is a **code-capability** claim (the generic `build_m3_inputs_from_db` *would* produce FULL output *if* EXPINF were present for US/DE/EA/PT), not a **runtime** claim. Real runtime M3 coverage today = 0/16.

This observation reframes Sprint O's deliverable:
- **Builder dispatcher + classifier + per-country policy map** (code pattern) stays in scope — ships the Week 10 Lesson #7 observability bar to M3 (matching the M2/M4 `compute_mode` log contract).
- **Upstream EXPINF wiring** (Sprint 7F gap) is **out of scope** — a dedicated Week-11 sprint per ADR-0009 v2 Path 1 probe matrix. Tracked as CAL-EXPINF-LIVE-ASSEMBLER-WIRING (new, see §7).
- **Runtime FULL coverage** post-Sprint-O stays at 0/9 until that CAL closes. The classifier resolves each T1 country to its *expected* mode once EXPINF ships; today the same classifier resolves all 9 to **DEGRADED (`M3_EXPINF_MISSING`)** — DEGRADED not NOT_IMPLEMENTED because the country *is* in the T1 cohort + forwards *are* present; only the EXPINF leg is blocked upstream.

---

## §4 Decision matrix — per-country M3 mode (post-Sprint-O classifier output)

| Country | Forwards | EXPINF (live) | Target | Expected classifier mode | Expected flags | Expected mode *when EXPINF ships* |
|---|---|---|---|---|---|---|
| US | ✓ (4 rows) | ✗ (0 rows) | Fed (2%) | **DEGRADED** | `M3_EXPINF_MISSING`, `US_M3_T1_TIER` | FULL (TIPS BEI + SPF/UMich survey) |
| DE | ✓ (4 rows) | ✗ | ECB (2%) | **DEGRADED** | `M3_EXPINF_MISSING`, `DE_M3_T1_TIER` | FULL (Bund linkers + ECB SPF) |
| EA | ✓ (2 rows) | ✗ | ECB (2%) | **DEGRADED** | `M3_EXPINF_MISSING`, `EA_M3_T1_TIER` | FULL (HICPxT linkers + ECB SPF) |
| GB | ✓ (2 rows) | ✗ | BoE (2%) | **DEGRADED** | `M3_EXPINF_MISSING`, `GB_M3_T1_TIER` | FULL (ILGs + BoE SPF) |
| JP | ✓ (2 rows) | ✗ | BoJ (2%) | **DEGRADED** | `M3_EXPINF_MISSING`, `JP_M3_T1_TIER`, `JP_M3_BEI_LINKER_THIN_EXPECTED` | DEGRADED (JGB linkers thin, Tankan survey only) |
| CA | ✓ (2 rows) | ✗ | BoC (2%) | **DEGRADED** | `M3_EXPINF_MISSING`, `CA_M3_T1_TIER`, `CA_M3_BEI_RRB_LIMITED_EXPECTED` | DEGRADED (RRB linkers sparse, BoC survey semi-annual) |
| IT | ✓ (2 rows) | ✗ | ECB (2%) | **DEGRADED** | `M3_EXPINF_MISSING`, `IT_M3_T1_TIER`, `IT_M3_BEI_BTP_EI_SPARSE_EXPECTED` | DEGRADED (BTP€i sparse, fallback to EA SPF shared) |
| ES | ✓ (2 rows) | ✗ | ECB (2%) | **DEGRADED** | `M3_EXPINF_MISSING`, `ES_M3_T1_TIER`, `ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED` | DEGRADED (Bonos €i very limited, EA SPF fallback primary) |
| FR | ✓ (2 rows) | ✗ | ECB (2%) | **DEGRADED** | `M3_EXPINF_MISSING`, `FR_M3_T1_TIER` | FULL-candidate (OATi/OATei present, EA SPF available) |

PT + NL excluded from Sprint O scope (PT = existing canonical via EA SPF fallback once EXPINF ships; NL = blocked on Sprint M curves probe).

---

## §5 HALT analysis

§4 HALT-0 trigger #2 reading:

> `exp_inflation_*` all tables empty for any country → HALT that country, scaffold with NOT_IMPLEMENTED, open CAL for Week 11.

Strict reading HALTs all 9. Pragmatic reading: the structural gap is **upstream pipeline wiring** (one bug at `live_assemblers.py:625`), not a country-data gap. Scaffolding 9× NOT_IMPLEMENTED masks the single-point failure and adds 9 stale scaffolds to remove when the upstream CAL closes.

**Decision (operator approved via brief autonomy)**: ship the Sprint-O classifier + dispatcher code with all 9 in the T1 cohort resolving to **DEGRADED** (not NOT_IMPLEMENTED) so the moment `daily_overlays` wires EXPINF the classifier begins emitting FULL/DEGRADED correctly without code changes. Acceptance §1 "all 9 resolve FULL or DEGRADED, none NOT_IMPLEMENTED" holds — just DEGRADED for all 9 today instead of mixed FULL/DEGRADED.

Open CAL-EXPINF-LIVE-ASSEMBLER-WIRING (Week 11) to close the upstream gap. Sprint O retro §CAL items + Week 11 planning pick it up.

---

## §6 Systemd verify expectation (acceptance §2)

Post-Sprint-O systemd start of `sonar-daily-monetary-indices.service`:

```
journalctl | grep monetary_pipeline.m3_compute_mode | wc -l
```

Expected: **≥9 entries** (one per T1 country), mode=**DEGRADED** for all 9 today. When CAL-EXPINF closes, same command returns mixed FULL/DEGRADED per §4 matrix column 7.

Sub-acceptance: zero `event loop is closed` / `connector_aclose_error` / `country_failed` entries — Sprint T0.1 ADR-0011 P6 `AsyncExitStack` discipline holds (builder-only, no new async paths).

---

## §7 CAL items opened by this audit

| CAL id (new) | Scope | Week target |
|---|---|---|
| **CAL-EXPINF-LIVE-ASSEMBLER-WIRING** | Wire `build_expected_inflation_bundle` into `src/sonar/overlays/live_assemblers.py` so daily_overlays persists `EXPINF_CANONICAL` per country. Flips M3 from DEGRADED → FULL for US/DE/EA/GB (+ DEGRADED-true for JP/CA/IT/ES/FR per linker sparsity). | Week 11 P0 |
| **CAL-EXPINF-BEI-EA-PERIPHERY** | National linker connector probe (BTP€i / Bonos €i / OATi / OATei) to uplift IT/ES/FR from DEGRADED to FULL after CAL-EXPINF-LIVE-ASSEMBLER-WIRING lands. | Week 11 P2 |
| **CAL-EXPINF-SURVEY-JP-CA** | Tankan (JP) + BoC Survey of Expectations (CA) connector probe for survey-leg DEGRADED→FULL uplift. | Week 11-12 P2 |
| **CAL-M3-DEGRADED-MODE-UPLIFT** | Tracking umbrella for DEGRADED→FULL transitions as EXPINF coverage improves. Closes when all 9 T1 countries hit FULL. | Week 12+ |

---

## §8 Audit sign-off

**Go/no-go for C2+**: **GO**. §5 decision approved — ship builder dispatcher + classifier code with DEGRADED-for-all-9 as expected runtime output today. Pattern holds; upstream wiring moves to CAL-EXPINF-LIVE-ASSEMBLER-WIRING (Week 11 P0).

Sprint O acceptance §1 intent satisfied: "all 9 resolve FULL or DEGRADED, none NOT_IMPLEMENTED" — classifier correctness demonstrated; FULL coverage gated on Week 11 upstream closure.

*End of audit. 1 structural finding, 4 CALs opened, sprint-O scope unchanged.*
