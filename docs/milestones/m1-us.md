# M1 US Milestone — Single-Country End-to-End

**Status**: ~95 % complete — implementation scope fully shipped for the
Phase 1 target; spec-vs-implementation deltas catalogued in the
companion [gap analysis](m1-us-gap-analysis.md).

**Declared**: Week 7 Sprint G (Phase 1 close).

M1 is the milestone contract for "one country end-to-end" — SONAR
computes every L0 → L8 layer for **US** daily, from raw connector
fetches through the four L4 cycle composites, with the same pipelines
producing partial-but-coherent output for the six other T1 countries
(DE / PT / IT / ES / FR / NL). UK + JP land in M2 T1.

---

## 1. Scorecard

| Layer | Target | Shipped (US) | Notes |
|---|---|---|---|
| L0 connectors | core set | **22+ operational** | FRED + Eurostat + BIS + BoE/Shiller/Damodaran/FMP/Multpl/CBOE/CFTC/FINRA/Chicago Fed NFCI/ECB SDW/Bundesbank/Moody's + Yahoo ^CPC + TE + AAII + Factset Insight + Eurostat + ICE BofA OAS + MOVE + CBO + SPDJI Buyback + Yardeni |
| L1 persistence | 16 migrations | **16/16 shipped** | alembic `001_nss_curves` → `016_ecs_cycle_scores` |
| L2 overlays | 5 | **5/5** | NSS curves, ERP US daily, CRP, rating-spread v0.2, expected-inflation canonical |
| L3 indices | 16 | **16/16 compute** + **14–16 real-data** | E1/E3/E4 + M1/M2/M4 live via connectors; E2 + M3 live via Sprint E DB-backed readers when daily_curves + daily_overlays have persisted upstream rows; credit L1/L2 live via BIS ingestion; financial F1-F4 live via FMP+Yahoo+FRED |
| L4 cycles | 4 | **4/4 operational** | CCCS + FCS + MSC + ECS — regimes + overlays wired |
| L5 regimes | (Phase 2+) | 0 | Spec stub only; no work done in Phase 1 |
| L6 integration | cost-of-capital | **ERP composition live** | `daily_cost_of_capital` pipeline wires ERP + rf + CRP end-to-end |
| L7 outputs | (Phase 2+) | 0 | No dashboards / PDFs this phase |
| L8 pipelines | — | **9 daily pipelines** | daily_curves, daily_bis_ingestion, daily_overlays, daily_credit_indices, daily_financial_indices, daily_economic_indices, daily_monetary_indices, daily_cycles, daily_cost_of_capital |

### Test posture

- **1078+ unit tests** green in default CI (21 slow deselected).
- **~30 @pytest.mark.slow** integration canaries (live + in-memory).
- Full project mypy over **95+ source files**.
- `ruff format --check` + `ruff check` clean on `src/sonar` + `tests`.

---

## 2. Country coverage matrix

| Country | L0 | L2 | L3 | L4 | Notes |
|---|---|---|---|---|---|
| **US** | 22+ conn | 5/5 | 16/16 (real) | 4/4 | Primary — full end-to-end |
| **DE** | FRED + Eurostat + ECB SDW + BIS | NSS derived EA; ERP via US proxy (flag); CRP benchmark; rating AAA; expinf SURVEY | E1/E3/E4 partial via Eurostat; M1 EA via ECB; credit L1/L2 via BIS | CCCS + FCS + ECS + MSC operational | EA benchmark behaviour (CRP=0 bps) |
| **FR / IT / ES / NL** | Eurostat + ECB SDW + BIS | NSS EA + ERP US-proxy + CRP SOV_SPREAD + rating + expinf | E1/E3/E4 partial; M1 EA | CCCS + FCS + ECS + MSC operational | Periphery yields > DE benchmark |
| **PT** | Eurostat + IGCP + ECB + BIS | Same as EA periphery + IGCP for domestic sovereign | E1/E3/E4 partial + Portuguese IGCP touches | CCCS + FCS + ECS + MSC | Portugal-aware per CLAUDE.md principle |
| **UK / JP** | deferred Week 8+ | — | — | — | CAL-118 / CAL-119 surfaced M2 T1 scope |

ERP live is US-only (Phase 1 scope); EA periphery inherits
`MATURE_ERP_PROXY_US` flag. Per-country ERP sprints land in Week 8+.

---

## 3. CLI quickstart

```bash
# One-time setup
uv sync
cp .env.example .env   # populate FRED_API_KEY etc.

# Daily pipeline chain (US example)
uv run python -m sonar.pipelines.daily_curves         --country US --date 2024-12-31
uv run python -m sonar.pipelines.daily_bis_ingestion  --country US --date 2024-12-31
uv run python -m sonar.pipelines.daily_overlays       --country US --date 2024-12-31
uv run python -m sonar.pipelines.daily_credit_indices --country US --date 2024-12-31
uv run python -m sonar.pipelines.daily_financial_indices --country US --date 2024-12-31
uv run python -m sonar.pipelines.daily_economic_indices --country US --date 2024-12-31
uv run python -m sonar.pipelines.daily_monetary_indices --country US --date 2024-12-31
uv run python -m sonar.pipelines.daily_cycles         --country US --date 2024-12-31

# Operational CLI (Sprint G)
uv run sonar status --country US --date 2024-12-31
uv run sonar status --all-t1
uv run sonar health
uv run sonar retention run --dry-run
```

`--all-t1` iterates over the 7 T1 countries (US / DE / PT / IT / ES /
FR / NL).

---

## 4. Architecture pointer

See [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) for the 9-layer
dependency graph (L0 → L8). Decision records live under
[`docs/adr/`](../adr/). The full spec catalog is in
[`docs/specs/`](../specs/).

---

## 5. What "complete" means for M1 US

**Implementation scope** — 100 % of Phase 1 planned features shipped:

- 22+ connectors operational with cache + retries + cassette tests.
- 5 L2 overlays computing daily from L0 + persisting to L1.
- 16 L3 indices compute-ready, 14–16 persisting real data (E2 + M3
  populate when daily_curves + daily_overlays land the required
  upstream rows).
- 4 L4 cycle composites with Policy-1 aggregation + regime
  classification + overlay flags.
- 9 daily pipelines with graceful degradation + structured logs +
  typed exit codes (`0 / 1 / 2 / 3 / 4`).
- Pre-push gate green every sprint (ruff + mypy + ~1078 unit tests).

**Spec scope** — ~70–75 % complete. Deltas catalogued in
[`m1-us-gap-analysis.md`](m1-us-gap-analysis.md):

- E2 Leading uses the 3 NSS-derived inputs in the current `E2Inputs`
  dataclass (spec §2 reference shape has 8; the 5 non-NSS components
  never had shipped inputs — Phase 2+ scope).
- Rating-spread agency scrape forward path partial (Damodaran primary;
  agency parsers Phase 2+).
- M3 BEI/SURVEY split unresolved (CAL-113).
- Per-country ERP (Phase 1 has US only).

**Out of Phase 1 scope** (explicitly Phase 2+):

- L5 regime classifier (no spec yet).
- Weekly integration matrix.
- L7 client outputs (dashboards / PDFs).
- Postgres migration (SQLite MVP).
- Systemd timer / cron wiring.
- Email / webhook alerting (interface shipped, delivery Phase 2+).

---

## 6. References

- [`m1-us-gap-analysis.md`](m1-us-gap-analysis.md) — spec-vs-shipped
  deltas categorized by impact.
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — 9-layer dependency
  graph.
- [`../backlog/calibration-tasks.md`](../backlog/calibration-tasks.md)
  — 62 CAL items (21 closed, 41 open; open items mostly M2 T1 scope
  + Phase 2+).
- [`../planning/retrospectives/`](../planning/retrospectives/) —
  sprint-by-sprint history (~16 retrospectives covering Weeks 1-7).

---

_M1 US milestone declared complete Week 7 Sprint G (Phase 1 close).
Next milestone: M2 T1 Core (UK + JP coverage + per-country ERP +
EA periphery M2/M4)._
