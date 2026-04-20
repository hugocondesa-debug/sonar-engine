# Spec Sweep CRP+ERP — Execution Brief (v2)

**Target**: Pre-Week 3.5 implementation
**Priority**: HIGH (blocker to Week 3.5 brief)
**Budget**: 20–30 min CC autonomous
**Commits**: 1 (specs + backlog consolidated)
**Base**: main HEAD

---

## 1. Scope

In:
- `docs/specs/overlays/crp.md` — swap twelvedata/yfinance → FMP+TE for vol_ratio data
- `docs/specs/overlays/erp-daily.md` — add Yardeni Earnings Forecasts as secondary forward-earnings source
- `docs/backlog/calibration-tasks.md` — close CAL-039
- `docs/backlog/phase2-items.md` — create P2-028 (Yardeni explicit consent documentation)

Out: no code changes. Pure doc + backlog.

---

## 2. Spec reference

- `docs/specs/conventions/units.md`, `flags.md` — unchanged
- SESSION_CONTEXT §Decision authority (spec changes = HIGH priority, single commit acceptable)

---

## 3. Commits

### Commit 1/1 — consolidated spec sweep + backlog

#### crp.md

§2 inputs — **replace** the two rows referencing twelvedata + yfinance:

Find (approximate):
```
| `equity_returns_daily` | vol | `pd.Series` | `connectors/twelvedata` (PSI-20, IBEX, FTSE MIB, BOVESPA, …); 5Y rolling, ≥ 750 obs. **Phase 2+ verify ToS** — twelvedata tier/licensing não validado em D-block. |
| `bond_returns_daily` | vol | `pd.Series` | `connectors/te` / `yfinance` sovereign long-bond price series; 5Y rolling, ≥ 750 obs. **Phase 2+ verify** — yfinance scrape estability não validado em D-block. |
```

Replace with:
```
| `equity_returns_daily` | vol | `pd.Series` | `connectors/fmp` (S&P 500, DAX, CAC, FTSE, NKY, SXXP, PSI-20, IBEX, FTSE MIB, BOVESPA, ...) — Ultimate tier, 30Y+ historical daily EOD; 5Y rolling window, ≥ 750 obs. |
| `bond_returns_daily` | vol | `pd.Series` | `connectors/te` sovereign 10Y yield historical — daily yield changes as bond return proxy; 5Y rolling, ≥ 750 obs. |
```

Append footnote after the §2 inputs table:
```
> **vol_ratio activation** (revised 2026-04-20): country-specific `σ_equity / σ_bond` via FMP Ultimate + TE historical yields is the default from Week 3.5 onward. `damodaran_standard_ratio = 1.5` remains fallback when connector unavailable or data insufficient (< 750 obs), flag `CRP_VOL_STANDARD`. Closes CAL-039.
```

#### erp-daily.md

§2 market data — find the row for `forward_earnings_est`:
```
| `forward_earnings_est` | `float` | `factset_insight` | DCF, EY |
```

Replace:
```
| `forward_earnings_est` | `float` | `factset_insight` (primary, weekly PDF) + `yardeni` (secondary, weekly Earnings Squiggles PDF, explicit consent per P2-028) | DCF, EY; dual source enables cross-validation divergence flag |
```

§4 pipeline — find step 8 (Damodaran xval). **Insert** new step 8.5 (renumber subsequent):
```
8.5. **Cross-source forward-earnings divergence** (US only, Week 3.5+): when both FactSet and Yardeni forward EPS estimates are fresh (≤ 7 days), compute `forward_eps_divergence_pct = |factset_eps − yardeni_eps| / mean(factset_eps, yardeni_eps)`. Emit flag `ERP_SOURCE_DIVERGENCE` when `> 5%`. Does not affect canonical ERP computation (use FactSet primary); editorial signal only.
```

§6 edge cases — append row:
```
| `forward_eps_divergence_pct > 5%` (FactSet vs Yardeni, US only) | flag `ERP_SOURCE_DIVERGENCE`; no confidence impact; editorial signal | 0 |
```

§10 Reference — under "Papers / Data providers" or similar section, append:
```
- **Yardeni Research**: Earnings Squiggles methodology (time-weighted consensus current + next year). Weekly PDF publications. **Use requires explicit written consent from Yardeni Research** (P2-028 tracks authorization documentation).
```

#### calibration-tasks.md

Find entry `### CAL-039 — Equity/bond vol data source validation`. **Append** to that entry:
```
**Status**: CLOSED 2026-04-20 — resolved via FMP Ultimate (equity historical) + TE historical yields (bond vol proxy) pivot. Neither twelvedata nor yfinance needed. Country-specific vol_ratio activates Week 3.5.
```

Find entry `### CAL-044 — ERP overlay full implementation`. **Append**:
```
**Unblock update 2026-04-20**: FactSet PDF scrape path confirmed tractable + Yardeni secondary source enabled (P2-028 consent path). multpl + spdji scrapers risk-accepted per Hugo. Week 3.5 Sub-sprint 3.5B implements full 4-method ERP US.
```

#### phase2-items.md

Append new entry (in numeric order after existing P2-02X):

```
## P2-028: Yardeni Research explicit written consent documentation

**Status**: OPEN
**Priority**: HIGH (blocker — upgrade if 30 days elapse without documentation)
**Rationale**: Yardeni Research copyright explicit prohibits reproduction/derivative use without explicit written consent. Hugo undertakes direct email outreach to obtain consent for internal SONAR use (7365 Capital analytical framework). Authorization assumed granted pre-implementation per Hugo decision 2026-04-20; formal paper trail required.
**Deliverable**: `docs/governance/licensing/yardeni-consent-YYYY-MM-DD.md` with email correspondence excerpt, granted scope, any restrictions, expiration if applicable.
**Trigger for upgrade**:
- 30+ days elapse from 2026-04-20 without documentation: → HIGH blocker (rollback Yardeni connector + remove derived data before any consumer boundary).
- Yardeni denies consent or imposes restrictive terms: → scope reconsideration (FactSet + Damodaran only path, remove Yardeni from ERP spec).
**Owner**: Hugo.
```

---

### Commit msg

```
docs(specs): FMP+TE pivot for CRP vol_ratio + Yardeni addition to ERP

crp.md §2:
- Drop twelvedata (paid tier unavailable) + yfinance (TOS commercial-use restriction)
- Add FMP Ultimate (equity historical daily, 30Y+) + TE historical 10Y yields
  (bond vol proxy via daily yield changes)
- vol_ratio activates country-specific by default Week 3.5+; damodaran_standard
  remains fallback only

erp-daily.md §2, §4, §6, §10:
- Add Yardeni Earnings Forecasts as secondary forward-earnings source
  (dual-source cross-validation with FactSet)
- New pipeline step 8.5: forward_eps_divergence_pct flag ERP_SOURCE_DIVERGENCE
  when FactSet vs Yardeni disagree > 5% (US only; editorial signal)
- Yardeni use requires explicit written consent (P2-028)

Backlog:
- CAL-039 CLOSED (vol_ratio data unblocked via FMP+TE)
- CAL-044 unblock note added (Week 3.5 Sub-sprint 3.5B)
- P2-028 NEW HIGH (Yardeni consent documentation; 30-day upgrade trigger)

No methodology_version bumps — data-source swaps and additive dual-source
path are spec §2 changes, not compute changes.
```

---

## 4. HALT triggers

1. CAL-039 or CAL-044 entries not found in calibration-tasks.md at expected location — halt, clarify path
2. Spec edits introduce units/flags inconsistency with conventions/ — halt
3. Commit pre-hook fails on markdown linting of modified sections — halt, do NOT force-fix

---

## 5. Acceptance

- [ ] 1 commit pushed, main HEAD matches remote
- [ ] 4 files modified: crp.md, erp-daily.md, calibration-tasks.md, phase2-items.md
- [ ] `grep -c "twelvedata\|yfinance" docs/specs/overlays/crp.md` returns 0
- [ ] `grep -c "Yardeni" docs/specs/overlays/erp-daily.md` returns ≥ 2
- [ ] `grep -c "P2-028" docs/backlog/phase2-items.md` returns ≥ 1
- [ ] `grep -A 2 "CAL-039" docs/backlog/calibration-tasks.md | grep -i "CLOSED"` returns match
- [ ] All hooks pass clean (no --no-verify)

---

## 6. Report-back artifact export

**Mandatory artifact export** (tmux buffer truncates long reports):

Write full report to `/home/macro/projects/sonar-engine/docs/planning/retrospectives/week3-5-spec-sweep-report.md` — include all report-back content per §7 below. Commit this file in the same push (add to the spec-sweep commit OR separate `docs(planning):` commit — CC judgement).

After push, echo to tmux stdout:
```
REPORT ARTIFACT: docs/planning/retrospectives/week3-5-spec-sweep-report.md
```

This makes report durable in git + scp-retrievable without relying on tmux scroll-back.

---

## 7. Report-back content (for artifact + brief tmux summary)

1. Commit SHA(s) + `git log --oneline -2`
2. Diff stats per file
3. Verification greps from §5
4. Any interpretation beyond verbatim
5. Timer vs 20–30 min budget

Paste brief 5-line summary to tmux; full content lives in artifact file.

---

*End of brief.*
