# Sprint L0-CB-T1-COMPLETION — Central Banks T1 Connectors Fechar Layer

**Branch**: `sprint-l0-cb-t1-completion`
**Worktree**: `/home/macro/projects/sonar-wt-l0-cb-t1-completion`
**Data**: Week 11 Day 1 — arranque ~19:10 WEST
**Budget**: 4-6h
**Priority**: P0 — fecha L0 layer T1 cohort systematic
**Parent**: Strategic pivot — fechar L0→L1→L2→L3 sistematicamente antes de L4

---

## §1 Scope

Fechar **L0 connectors para todos bancos centrais T1**, em vez de incremental ad-hoc. Output: cada T1 country tem connector(s) cobrindo policy rate + yield curves + inflation expectations. L1 populate depois fica trivial.

### Current state L0 central banks (honest inventory)

| Country | CB | Policy rate | Yield curves | Inflation exp | Status |
|---|---|---|---|---|---|
| US | Fed | FRED ✓ | FRED ✓ | FRED BEI + survey ✓ | **complete** |
| EA | ECB | ECB SDW ✓ | ECB SDW ✓ | ECB SDW SPF ✓ | **complete** |
| DE | Bundesbank | ECB proxy | Bundesbank Svensson ✓ | ECB SPF proxy ✓ | **complete** |
| FR/IT/ES/PT/NL | ECB members | ECB proxy | ECB SDW (sovereign) | ECB SPF proxy | **complete via ECB** |
| GB | BoE | ? | BoE yield-curves ✓ (Sprint Q.2/P.2) | BoE BEI ✓ | **partial — policy rate?** |
| JP | BoJ | ? | ? | BoJ Tankan ✓ (Sprint Q.3) | **partial — rate + curves gap** |
| CA | BoC | BoC Valet partial | ? | BoC CES ✓ (Sprint Q.3) | **partial — rate + curves gap** |
| AU | RBA | ? | ? | ? | **zero** |

### Gaps objetivos T1 cohort (12 countries)

**Missing L0 components**:
1. **GB policy rate** — BoE Bank Rate via IADB / dedicated endpoint
2. **JP policy rate** — BoJ uncollateralized overnight rate
3. **JP yield curves** — JGB nominal + inflation-linked (JGBi)
4. **CA policy rate** — BoC overnight rate via Valet
5. **CA yield curves** — Canadian government bond yields via Valet
6. **AU policy rate** — RBA cash rate (Australia **not in current T1 cohort** — verify inclusion scope)
7. **AU yield curves** — ACGB yields (if AU is T1)

### Scope decision — AU inclusion

AU currently in `M3_T1_COUNTRIES`? Per last Tier B inspection Sprint Q.4b — cohort has 10 countries, `NOT_IMPLEMENTED` includes AU. **AU is not M3 T1 today**.

**Decision**: Sprint L0-CB-T1 scope = **GB + JP + CA completion**. AU deferred separate CAL (M3 policy definition needed first).

### Objective

Ship complete L0 for GB + JP + CA:
- Policy rate fetch (BoE / BoJ / BoC)
- Yield curves complete (BoE nominal done P.2, JGB new, Canadian bonds new)
- Writers for each into existing L1 tables (policy_rates, yield_curves_*)
- Zero new L1 tables — reuse existing schemas

---

## §2 Spec

### 2.1 Pre-flight probes (MANDATORY, all 3 sources parallel)

```bash
cd /home/macro/projects/sonar-wt-l0-cb-t1-completion
source .env

# === GB BoE Bank Rate ===
# BoE IADB was Akamai-blocked per Sprint Q.2. Alternative: BoE statistics
# Bank Rate series code: IUDBEDR
curl -s -I "https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp" | head -5
# OR the content-store approach like Sprint Q.2
curl -s -I "https://www.bankofengland.co.uk/-/media/boe/files/statistics/baserate.xlsx" | head -5

# === JP BoJ policy rate ===
# BoJ statistics — uncollateralized overnight call rate target
# Likely CSV/Excel download from boj.or.jp/en/statistics/boj
curl -s -I "https://www.boj.or.jp/en/statistics/boj/fm/juchi/juchi.csv" | head -5

# === JP JGB yield curves ===
# MOF (Ministry of Finance) publishes JGB yields daily
curl -s -I "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcm.csv" | head -5
# OR BoJ financial markets interest rate data
curl -s -I "https://www.boj.or.jp/en/statistics/market/short/fmrate/fmrate.csv" | head -5

# === CA BoC policy rate + bond yields via Valet ===
# Valet already used for CES in Sprint Q.3
curl -s "https://www.bankofcanada.ca/valet/observations/V39079/csv" | head -10  # overnight target rate
curl -s "https://www.bankofcanada.ca/valet/observations/BD.CDN.2YR.DQ.YLD/csv" | head -10  # 2Y GoC
```

Document findings in `docs/backlog/probe-results/sprint-l0-cb-t1-probe.md`:
- Per source: status (accessible / 4xx / needs-workaround)
- Data format (CSV/JSON/XML/scrape)
- Historical depth
- Update frequency

### 2.2 Fan-out implementation

**3 connectors new or extended**:

#### GB — extend `boe_database.py` OR new `boe_policy_rates.py`
```python
class BoePolicyRateConnector:
    async def fetch_bank_rate_history(self, date_start, date_end) -> list[PolicyRateObs]:
        """Fetch BoE Bank Rate history."""
```

#### JP — `boj_policy.py` + `jgb_yield_curves.py` (2 new modules)
```python
class BojPolicyRateConnector:
    async def fetch_overnight_call_target(self, date_start, date_end) -> list[PolicyRateObs]:
        """BoJ uncollateralized overnight call rate target."""

class JgbYieldCurvesConnector:
    async def fetch_jgb_spot_curve(self, date_start, date_end) -> list[YieldCurveObs]:
        """JGB nominal zero-coupon yields via MOF daily CSV."""
```

#### CA — extend `boc_valet.py` (added Q.3) with rate + yields fetchers
```python
class BocValetConnector:
    # existing: fetch_ces_inflation_expectations (Q.3)
    # add:
    async def fetch_overnight_target(self, date_start, date_end) -> list[PolicyRateObs]:
        """BoC policy rate via Valet series V39079."""

    async def fetch_goc_yields(self, date_start, date_end) -> list[YieldCurveObs]:
        """Government of Canada bond yields via Valet."""
```

### 2.3 Writer integration

Reuse existing writers:
- Policy rates → existing `policy_rates` table (or whatever name — audit in §2.1 with `.schema`)
- Yield curves nominal → `yield_curves_raw` or `yield_curves_spot` (follow Sprint P.2 BoE pattern)

**Zero new L1 tables**. Strict reuse.

### 2.4 Backfill scripts

3 scripts (one per country-domain):

```bash
scripts/ops/backfill_gb_policy_rate.py  # GB Bank Rate 2020-2026
scripts/ops/backfill_jp_policy_and_curves.py  # BoJ rate + JGB curves 2020-2026
scripts/ops/backfill_ca_policy_and_curves.py  # BoC rate + GoC curves 2020-2026
```

Pattern per Sprint P.2. Idempotent via ADR-0011 P1.

### 2.5 Verification

```bash
# Post-backfill L0/L1 state
sqlite3 data/sonar-dev.db "
SELECT 'GB policy' AS k, COUNT(*), MIN(date), MAX(date) FROM policy_rates WHERE country_code='GB'
UNION ALL
SELECT 'JP policy', COUNT(*), MIN(date), MAX(date) FROM policy_rates WHERE country_code='JP'
UNION ALL
SELECT 'CA policy', COUNT(*), MIN(date), MAX(date) FROM policy_rates WHERE country_code='CA'
UNION ALL
SELECT 'JP curves', COUNT(*), MIN(date), MAX(date) FROM yield_curves_raw WHERE country_code='JP'
UNION ALL
SELECT 'CA curves', COUNT(*), MIN(date), MAX(date) FROM yield_curves_raw WHERE country_code='CA';"
```

Expected: each ≥1000 rows, 2020-2026 coverage.

---

## §3 Commits plan

| # | Scope | Files |
|---|---|---|
| C1 | docs(probes): L0 CB T1 probe results (GB rate + JP rate/curves + CA rate/curves) | `docs/backlog/probe-results/sprint-l0-cb-t1-probe.md` |
| C2 | feat(connectors): BoE policy rate | `src/sonar/connectors/boe_policy_rates.py` OR extend |
| C3 | feat(connectors): BoJ policy + JGB yield curves | `src/sonar/connectors/boj_policy.py`, `jgb_yield_curves.py` |
| C4 | feat(connectors): BoC policy + GoC yields (Valet extension) | `src/sonar/connectors/boc_valet.py` extend |
| C5 | feat(ops): backfill scripts GB/JP/CA policy rates + curves | `scripts/ops/backfill_{gb,jp,ca}_*.py` |
| C6 | test: 3 connector test suites | `tests/unit/test_connectors/` |
| C7 | ops: backfill executed (no commit) | — |
| C8 | docs(planning): Sprint L0-CB-T1 retrospective | `docs/planning/retrospectives/...` |

---

## §4 HALT triggers

**HALT-0 per-source** (ship partial acceptable):
- BoE Bank Rate requires scrape → open `CAL-GB-POLICY-SCRAPE` Week 12+, ship JP+CA only
- JGB data MOF blocked → fallback BoJ statistics, if also blocked → open `CAL-JP-CURVES-SCRAPE`
- Valet series codes wrong → retry with correct codes, 30min budget internal

**Partial ship OK**: 2 of 3 countries shipping clean > forcing all-or-nothing. Document HALT per-country, open CAL.

**HALT-material**:
- Zero regressions accepted (US/EA/GB-BEI/JP-Tankan/CA-CES paths unchanged)
- Existing writer schemas incompatible → audit first, may need schema migration = scope exit

**HALT-scope**:
- Zero new L1 tables — reuse existing schemas. If existing schema mismatch → stop + document, don't silently migrate.
- Zero L2+ work — this sprint is L0/L1 only.
- AU explicitly excluded (defer)
- Nordic countries (CH/SE/NO/DK/NZ) explicitly excluded (not in T1 cohort)

---

## §5 Acceptance

### Tier A
1. Probe doc shipped all 3 countries
2. Connectors implemented (or partial per HALT)
3. Backfill rows persisted ≥1000 per source shipped
4. Verification query §2.5 passes for all shipped countries
5. Tests pass for shipped connectors
6. Zero regression (Sprint Q.2/Q.3 paths intact)
7. Pre-commit clean double-run

### Tier B
Systemd — not applicable (no pipeline change). Next sprint (L1 populate full M1 per-country) consumes this.

---

## §6 Time budget

Arranque ~19:10 WEST. Hard cap 00:00 WEST (5h).

Realistic:
- Probe 30min (all 3 parallel)
- 3 connectors 60min each = 3h sequential OR parallel via audit-first workflow
- Backfill + verify 30min
- Tests 30min
- Commits + retro 30min

Best 4h. Worst 5h with 1 HALT-0.

**Partial ship target**: ≥2 of 3 countries (GB/JP/CA). Ship 1 = still Sprint L0 partial, document properly.

---

## §7 Scope locks

- **NO L2 overlay work** (NSS fits, forwards derivation — Sprint L2-NEXT scope)
- **NO L3 work** (M1/M2/M4 builders — Sprint L3-NEXT scope)
- **NO L4 MSC work** (obvious)
- **NO test of downstream M3 impact** (next sprint)
- **NO documentation refactor** (the Lesson #20 cascade unification CAL stays deferred)

---

*Focused L0 close. Ship connectors sistematicamente por CB. Pattern for subsequent L1/L2/L3 sprints.*
