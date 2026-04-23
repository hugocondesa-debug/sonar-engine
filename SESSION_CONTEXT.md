# SESSION_CONTEXT (in-repo mirror)

Spec target da Week 10 Day 3 R1 retro bundle. A cópia canónica vive no
projecto claude.ai como `SESSION_CONTEXT.md` — este ficheiro é um mirror
local das três secções amendadas na Week 10 close (schema reference,
Week 10 close snapshot, machine discipline) por ordem do retro bundle
spec (`/tmp/session_context_refresh_spec.md`).

**Autoridade**: quando claude.ai SESSION_CONTEXT divergir do conteúdo
abaixo, claude.ai ganha. Este mirror é historical trace + fonte de
referência rápida quando o contexto chat não está à mão.

**Staleness**: snapshots por-week tendem a envelhecer; verificar
`git log` + `docs/planning/retrospectives/` para estado canónico actual.

---

## DB Schema Canonical Reference

**DB path**: `data/sonar-dev.db` (production). `data/sonar.db` +
`data/sonar_phase0.db` = 0-byte placeholders; ignore.

**Canonical table names** (verified Week 10 Day 3 via schema audit).
Source of truth: `docs/architecture/db-schema-reference.md` (which in
turn defers to `alembic/versions/` migrations). Invariant: every
persistent L1-L6 table uses `date` as the date column name (never
`obs_date`, `observation_date`, etc.); Python dataclasses may use
`observation_date` internally but the ORM mapping writes `date`.

| Entity | Table | Date column | Unique constraint |
|---|---|---|---|
| Curves spot (NSS fit, canonical) | `yield_curves_spot` | `date` | `(country_code, date, methodology_version)` + `(fit_id)` |
| Curves zero | `yield_curves_zero` | `date` | `(country_code, date, methodology_version)` (FK → `yield_curves_spot.fit_id`) |
| Curves forwards | `yield_curves_forwards` | `date` | `(country_code, date, methodology_version)` (FK → `yield_curves_spot.fit_id`) |
| Curves real (linkers) | `yield_curves_real` | `date` | `(country_code, date, methodology_version)` |
| Curves params (legacy) | `yield_curves_params` | — | — |
| Curves fitted (legacy) | `yield_curves_fitted` | — | — |
| Curves raw (L0 tape) | `yield_curves_raw` | `date` | — |
| Curves metadata | `yield_curves_metadata` | — | — |
| M1 effective rates | `monetary_m1_effective_rates` | `date` | `(country_code, date, methodology_version)` |
| M2 Taylor gaps | `monetary_m2_taylor_gaps` | `date` | `(country_code, date, methodology_version)` |
| M3 expectations | **builder-only** (derives from `yield_curves_forwards` + `exp_inflation_canonical` via `MonetaryDbBackedInputsBuilder`; persists via `index_values`) | N/A | N/A |
| M4 FCI | `monetary_m4_fci` | `date` | `(country_code, date, methodology_version)` |
| L4 MSC composite | `monetary_cycle_scores` | `date` | `(country_code, date, methodology_version)` + `(msc_id)` |
| L4 FCS composite | `financial_cycle_scores` | `date` | `(country_code, date, methodology_version)` + `(fcs_id)` |
| L4 CCCS composite | `credit_cycle_scores` | `date` | `(country_code, date, methodology_version)` + `(cccs_id)` |
| L4 ECS composite | `economic_cycle_scores` | `date` | `(country_code, date, methodology_version)` + cycle-id UNIQUE |
| Economic E1 activity | `idx_economic_e1_activity` | `date` | `(country_code, date, methodology_version)` |
| Economic E2 inflation | **builder-only** (persists via `index_values`) | N/A | N/A |
| Economic E3 labor | `idx_economic_e3_labor` | `date` | `(country_code, date, methodology_version)` |
| Economic E4 sentiment | `idx_economic_e4_sentiment` | `date` | `(country_code, date, methodology_version)` |
| Cost of capital (L6) | `cost_of_capital_daily` | `date` | `(country_code, date, methodology_version)` |
| Credit L1 stock | `credit_to_gdp_stock` | `date` | `(country_code, date, methodology_version)` |
| Credit L2 gap | `credit_to_gdp_gap` | `date` | `(country_code, date, methodology_version)` |
| Credit L3 impulse | `credit_impulse` | `date` | `(country_code, date, methodology_version, segment)` |
| Credit L4 DSR | `dsr` | `date` | `(country_code, date, methodology_version, segment)` |
| Credit raw (BIS) | `bis_credit_raw` | `date` | — |
| Financial F1 valuations | `f1_valuations` | `date` | `(country_code, date, methodology_version)` |
| Financial F2 momentum | `f2_momentum` | `date` | `(country_code, date, methodology_version)` |
| Financial F3 risk appetite | `f3_risk_appetite` | `date` | `(country_code, date, methodology_version)` |
| Financial F4 positioning | `f4_positioning` | `date` | `(country_code, date, methodology_version)` |
| CRP canonical | `crp_canonical` | `date` | `(country_code, date, methodology_version)` |
| CRP CDS | `crp_cds` | `date` | — |
| CRP rating | `crp_rating` | `date` | — |
| CRP sov spread | `crp_sov_spread` | `date` | — |
| ERP canonical | `erp_canonical` | `date` | `(market_index, date, methodology_version)` |
| ERP CAPE | `erp_cape` | `date` | — |
| ERP DCF | `erp_dcf` | `date` | — |
| ERP EY | `erp_ey` | `date` | — |
| ERP Gordon | `erp_gordon` | `date` | — |
| Expected inflation canonical | `exp_inflation_canonical` | `date` | `(country_code, tenor, date, methodology_version)` |
| Expected inflation BEI | `exp_inflation_bei` | `date` | — |
| Expected inflation survey | `exp_inflation_survey` | `date` | — |
| Expected inflation swap | `exp_inflation_swap` | `date` | — |
| Expected inflation derived | `exp_inflation_derived` | `date` | — |
| Ratings agency raw | `ratings_agency_raw` | `date` | `(country_code, date, agency, rating_type, methodology_version)` |
| Ratings consolidated | `ratings_consolidated` | `date` | `(country_code, date, rating_type, methodology_version)` |
| Ratings spread calibration | `ratings_spread_calibration` | `calibration_date` | — |
| Generic index persistence | `index_values` | `date` | `(index_code, country_code, date, methodology_version)` |
| L5 meta regimes (scaffold) | `l5_meta_regimes` | `date` | `(country_code, date, methodology_version)` |

**Motivação**: handoff Day 3 Week 10 §7 referenciou `nss_yield_curves_spot`
e `indices_spot` — ambos nomes inexistentes. Esta tabela previne o mesmo
drift em handoffs futuros.

**Verify-on-doubt**:

```
sqlite3 data/sonar-dev.db ".schema <table>"
```

É a fonte autoritária. Alembic migrations em `alembic/versions/` batem.

---

## Week 10 (2026-04-21 a 2026-04-23) — Machine Hardening Week

**Sprints shipped**: 15 (Day 1: 6 | Day 2: 7 | Day 3: 2)
**T1 completion**: ~32% → ~54% (+22pp)
**ADRs canónicos shipped**: 0009 v2, 0010, 0011, 0011 Principle 6 (amendment)

### Day 1 (2026-04-21) — 6 sprints

- Infrastructure baseline
- CAL-138 closure
- Sprint A (EA periphery)
- Sprint B (ERP T1)
- Sprint C (M2 output gap)
- Sprint D (FR BdF)

### Day 2 (2026-04-22) — 7 sprints

- Sprint E (TE cascade IT/ES/FR + ADR-0009 v2 shipping)
- Sprint F (M2 Taylor Rule US + 9 non-EA T1)
- Sprint G (ternary pattern + HALT-0 learning)
- Sprint H (IT+ES TE cascade + ADR-0009 v2 amendment)
- Sprint L (M2 EA aggregate)
- Sprint I (FR TE cascade + ADR-0009 v2 3rd validation)
- Sprint J (M4 FCI T1 expansion — EA members + DE + GB scaffold)

### Day 3 (2026-04-23) — 2 sprints (foundation hardening)

- Sprint T0 (prod healing — ADR-0011 + idempotency refactor 3 services)
- Sprint T0.1 (monetary async lifecycle fix — ADR-0011 Principle 6
  amendment)

### Permanent fixes shipped Day 3 R1 bundle

- **Lesson #1**: `sprint_setup.sh` brief pre-flight check + auto-cp
  brief to worktree.
- **Lesson #2**: Pre-commit double-run convention formalized in brief
  format v3.1 §8.
- **Lesson #4**: `sprint_merge.sh` Step 10 tmux session cleanup (robust
  sob 20-char truncation).
- **Lesson #5**: `docs/templates/cc-arranque-prompt.md` canonical CC
  arranque template (pre-flight CWD + branch + brief verify).
- **Lesson #7**: Brief format v3.1 §6 systemd verification clause
  (local CLI exit 0 NOT sufficient — systemctl is-active + journalctl
  + summary + timer re-enable mandatory).

### Open items → Week 11

- Sprint M (curves PT+NL probe TE Path 1) — Day 4 manhã.
- Sprint O (M3 T1 expansion) — Day 4 afternoon, paralelo com M.
- `CAL-TE-QUOTA-TELEMETRY` deferred Week 11+ (HEAD quota probe + alert).
- E1/E3/E4 expansion planning (M-indices adjacent coverage).
- Curves T1 sparse probes (AU/NZ/CH/SE/NO/DK) planning.

---

## Machine Discipline (updated Week 10 close)

### Workflow automation

- `scripts/ops/sprint_setup.sh` — brief pre-flight + auto-stage
  (Week 10 Lesson #1 fix; backward compatible; supports `--brief
  <path>` for non-convention locations).
- `scripts/ops/sprint_merge.sh` — atomic 10-step merge with worktree +
  tmux cleanup Step 10 (Week 10 Lesson #4 fix; prefix-based session
  match robust to tmux's 20-char truncation).

### Brief format v3.1 (Week 10 Day 3 amendments)

- Header: `ADR-0010 tier scope`, `ADR-0009 v2 TE Path 1 probe`,
  `Systemd services affected` (required fields).
- §2 pre-flight probe matrix (TE Path 1 mandatory for country-data —
  ADR-0009 v2).
- §6 invocation context requirements (systemctl is-active + journalctl
  + summary + timer clauses if systemd-invoked — Week 10 Lesson #7).
- §8 pre-commit double-run convention (Week 10 Lesson #2).
- §13 dependencies + CAL interactions (new mandatory section).

### CC arranque discipline

- Use `docs/templates/cc-arranque-prompt.md` como canonical CC startup
  template.
- Pre-flight CWD verify (Week 10 Lesson #5 fix) — previne stale-CWD
  surviving post-merge worktree removal.
- Acceptance §6 NEVER claimed without systemd verify if applicable
  (Week 10 Lesson #7).

### ADRs shipped Week 10

- **ADR-0009 v2**: TE Path 1 mandatory for country-data probes.
  Empirical probe-before-scaffold discipline. Validated Day 2 Sprint H
  + Sprint I.
- **ADR-0010**: T1 complete before T2 expansion (scope lock). Phase 2-4
  T1 ONLY (16 countries). T2 Phase 5+ earliest Q3 2027.
- **ADR-0011**: Systemd service idempotency (Principles 1-5) — row-level
  idempotency, per-country isolation, exit code sanitization, summary
  emit, partial-persist recovery.
- **ADR-0011 Principle 6** (amendment): Async lifecycle discipline —
  single `asyncio.run()` at process entry, connectors via
  `AsyncExitStack` + `async with` context. Prevents event-loop churn
  killing `httpx.AsyncClient` instances bound to dead loops.
- **ADR-0011 Principle 7** (Sprint V Day 3 late): Worktree data
  lifecycle — worktrees MUST symlink `data/sonar-dev.db` to primary.
  `sprint_setup.sh` automates the 3-scenario handler (absent /
  0-byte / real file). Operator may deviate (copy + isolated DB) for
  destructive schema experiments — scenario (c) WARN-preserves.

### Sprint V shipped (Week 10 Day 3 late — R2 bundle)

Four new lessons emerged Day 3 late afternoon + evening; permanent
fixes shipped as R2 bundle mirroring R1 pattern.

- **Lesson #11** — Empty commit prevention
  (`.pre-commit-config.yaml`). Local `no-empty-commits` hook at
  commit-msg stage rejects empty staged tree with actionable
  re-stage message. Guards merge / cherry-pick / revert via
  `MERGE_HEAD` / `CHERRY_PICK_HEAD` / `REVERT_HEAD` guards.
- **Lesson #12** — Brief format v3.1 → v3.2
  (`docs/planning/brief-format-v3.md`). §6 systemd clause split
  into Tier A (CC pre-merge scope: local CLI + `bash -lc` wrapper
  smoke + tests + worktree-local grep) and Tier B (operator
  post-merge scope within 24h: `sudo systemctl start` + journalctl
  + is-active + timer re-enable).
- **Lesson #13** — Auto-commit watcher investigation
  (`docs/governance/auto-commit-watcher-investigation.md`). Forensic
  baseline: no user systemd / cron / inotify / git-hook / plugin
  evidence on VPS. H1 (parallel CC instance via second tmux
  session) is the high-confidence hypothesis. Three options (A
  disable / B canonize / C scope-limit) with explicit
  when-to-pick + action + risk framing. **Decision deferred** —
  operator reviews at Week 11 triage (CAL-WATCHER-DECISION).
- **Lesson #14** — Worktree DB auto-link
  (`scripts/ops/sprint_setup.sh` + ADR-0011 Principle 7). Script
  automates the symlink step between tmux setup and Final state
  print; 3-scenario handler (absent / 0-byte / real file);
  sandbox-tested before ship.

### Sprint Z shipped (Week 10 Day 3 late night — Lesson #15 amendment)

One additional lesson emerged during Sprint V arranque itself and was
deferred to Sprint Z for clean scoping; permanent fix shipped Day 3
late night paralelo com Sprint T.

- **Lesson #15** — Brief filename convention enforcement
  (`docs/planning/brief-format-v3.md` v3.2 → v3.3 +
  `docs/templates/cc-arranque-prompt.md` +
  `scripts/ops/sprint_setup.sh`). Brief filename MUST follow
  `week<NN>-<sprint_id>-brief.md` with sprint_id exact literal (no
  abbreviation). Author-side first gate via brief format v3.3
  convention; tooling-side second gate via `sprint_setup.sh` glob +
  enhanced HALT diagnostic. Sprint V arranque surfaced the gap when
  the uploaded filename dropped `-permanent-fixes`, breaking the
  Lesson #1 fix glob match.

### Total lessons Week 10

12 lessons discovered across Day 1-3. 11 shipped permanent fix (9
code/ops + 2 documentation/governance). 1 investigation-only
(#13 watcher) pending operator decision.

- Lessons #1-#7: R1 bundle Day 3 — `sprint_setup.sh` + `sprint_merge.sh`
  + `brief-format-v3.md` v3 → v3.1 + `cc-arranque-prompt.md`.
- Lessons #11-#14: R2 bundle Day 3 late — `.pre-commit-config.yaml`
  + `brief-format-v3.md` v3.1 → v3.2 + auto-commit watcher
  investigation + `sprint_setup.sh` DB auto-link + ADR-0011
  Principle 7.
- Lesson #15: Sprint Z Day 3 late night — `brief-format-v3.md`
  v3.2 → v3.3 + `cc-arranque-prompt.md` filename-aware +
  `sprint_setup.sh` HALT diagnostic enhancement.

---

*Last mirror refresh: 2026-04-23 Week 10 Day 3 late night — Sprint Z (Lesson #15).*
