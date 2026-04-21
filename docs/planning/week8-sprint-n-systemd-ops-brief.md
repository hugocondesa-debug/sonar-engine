# Week 8 Sprint N — Systemd Timer/Cron Ops Wiring

**Target**: Ship production deployment infrastructure for 9 daily pipelines via systemd service units + timers. Automated scheduling, logs management, DAG-aware ordering.
**Priority**: HIGH (production readiness blocker; M1 US declared complete but not deployed)
**Budget**: 2-3h CC autonomous
**Commits**: ~6-8
**Base**: branch `sprint-n-systemd-ops` (isolated worktree `/home/macro/projects/sonar-wt-sprint-n`)
**Concurrency**: Parallel to Sprint M CAL cleanup in worktree `sonar-wt-sprint-m`. See §3.

---

## 1. Scope

In:
- `deploy/systemd/` new directory with service + timer units
- **9 daily pipelines** systemd units (one `.service` + `.timer` per):
  1. `sonar-daily-bis-ingestion` (runs first; BIS data source refresh)
  2. `sonar-daily-curves` (NSS curves; depends on FRED data)
  3. `sonar-daily-overlays` (depends on daily-curves for expected-inflation)
  4. `sonar-daily-economic-indices` (depends on daily-curves for E2)
  5. `sonar-daily-monetary-indices` (depends on daily-overlays for M3)
  6. `sonar-daily-credit-indices` (depends on daily-bis-ingestion)
  7. `sonar-daily-financial-indices` (parallel to other indices)
  8. `sonar-daily-cycles` (depends on all 4 index pipelines)
  9. `sonar-daily-cost-of-capital` (depends on daily-overlays for ERP)
- **DAG ordering** via systemd `After=` + `Requires=` directives
- **Schedule design**:
  - BIS ingestion: 05:00 UTC daily (European data ready)
  - daily_curves: 06:00 UTC
  - daily_overlays: 06:30 UTC (depends curves)
  - daily indices (economic/monetary/credit/financial): 07:00 UTC parallel
  - daily_cycles: 08:00 UTC (after indices complete)
  - daily_cost_of_capital: 08:30 UTC
- **Logs handling**:
  - systemd journal integration (structured logs consumable via `journalctl -u <unit>`)
  - Rotation via journal defaults (vs logrotate — decide Commit 1)
  - Stdout/stderr piped to journal + optional file persistence
- **Install/uninstall scripts**:
  - `scripts/install-timers.sh` — copies units to `/etc/systemd/system/`, `systemctl daemon-reload`, enable timers
  - `scripts/uninstall-timers.sh` — disable + stop + remove units
  - Dry-run support per script
- **Documentation**:
  - `docs/ops/systemd-deployment.md` — architecture + install + troubleshoot
  - Update `CLAUDE.md` with systemd ops reference
- **Smoke verification** (no actual enablement this sprint):
  - `systemctl daemon-reload` dry-run
  - Unit file validation via `systemd-analyze verify`
- Retrospective

Out:
- Actual systemd enablement on production VPS (manual step post-sprint; user decides when)
- Email/webhook alerting for pipeline failures (AlertSink concrete impl; Phase 2+)
- Cron fallback units (systemd-only this sprint; cron optional later)
- Monitoring dashboard integration (Prometheus/Grafana Phase 2+)
- Rollback automation (manual via uninstall script sufficient Phase 1)
- Log forwarding to external systems (journald stays local)
- CPU/memory resource limits tuning (conservative defaults Phase 1)

---

## 2. Spec reference

Authoritative-ish (ops spec is NEW, pattern-driven):
- `docs/planning/retrospectives/week7-sprint-g-m1-us-polish-report.md` — AlertSink Protocol interface
- `src/sonar/pipelines/*.py` — 9 pipelines with Typer CLI entry points
- SESSION_CONTEXT §Infraestrutura — VPS + working directory
- SESSION_CONTEXT §Regras operacionais — pre-push gate
- Ubuntu 24.04 systemd defaults (this is Ubuntu VPS)

**Pre-flight requirement**: Commit 1 CC:
1. Probes systemd version + capabilities on VPS: `systemctl --version`
2. Verifies working directory + Python env paths:
   - `/home/macro/projects/sonar-engine` → actual source
   - `/home/macro/projects/sonar-engine/.venv` OR `uv run` wrapper
   - Pre-existing sonar CLI entry point: `sonar.cli.main:app` (Sprint G)
3. Checks for existing deploy/ or ops/ directories (should be none)
4. Reads each of the 9 pipeline CLI interfaces:
   - `python -m sonar.pipelines.daily_curves --help`
   - Etc. — confirms command-line invocation pattern
5. Reviews SESSION_CONTEXT infraestrutura section for any ops-relevant context

Document pattern decisions in commit body.

Existing assets:
- 9 daily pipelines operational (Sprint B + C + D + earlier)
- `sonar` CLI root Typer app (Sprint G)
- `.env` file at `/home/macro/projects/sonar-engine/.env` with FRED_API_KEY + TE_API_KEY
- Pre-existing `regscraper` user + other systemd services on VPS (don't conflict)

---

## 3. Concurrency — parallel protocol with Sprint M + ISOLATED WORKTREES

**Sprint N operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-n`

Sprint M operates in separate isolated worktree: `/home/macro/projects/sonar-wt-sprint-m`

**Critical workflow**:
1. Sprint N CC starts by `cd /home/macro/projects/sonar-wt-sprint-n`
2. All file operations happen in this worktree
3. Branch name: `sprint-n-systemd-ops`
4. Pushes to `origin/sprint-n-systemd-ops`
5. Final commit: merge to main via PR or direct merge

**File scope Sprint N**:
- `deploy/systemd/*.service` (9 new files)
- `deploy/systemd/*.timer` (9 new files)
- `scripts/install-timers.sh` NEW
- `scripts/uninstall-timers.sh` NEW
- `docs/ops/systemd-deployment.md` NEW
- `CLAUDE.md` small update (systemd ops reference)
- `docs/planning/retrospectives/week8-sprint-n-systemd-ops-report.md` NEW

**Sprint M scope** (for awareness, do NOT touch):
- `src/sonar/scripts/backfill_l5.py`
- `src/sonar/pipelines/daily_overlays.py` (EXPINF sub_indicators split)
- `src/sonar/indices/monetary/db_backed_builder.py` (BEI/SURVEY consumers)
- `docs/backlog/calibration-tasks.md` (formalizes CAL-113 + CAL-backfill-l5)

**Zero file overlap confirmed**. Different domains entirely.

**Merge strategy end-of-sprint**:
- Sprint N: `git checkout main && git merge sprint-n-systemd-ops` (fast-forward if possible)
- Sprint M: `git checkout main && git merge sprint-m-cal-cleanup`
- Order can be independent; both merge cleanly expected

**Push protocol during sprint**:
- Normal commits to `sprint-n-systemd-ops` branch
- Push via `git push origin sprint-n-systemd-ops`
- No rebase needed between sprints (isolated branches)

---

## 4. Commits

### Commit 1 — Pre-flight + deploy/ directory structure

```
feat(deploy): systemd ops directory scaffold + probe

Pre-flight: probe VPS environment. Document in commit body:
- systemctl --version (expected systemd 253+ on Ubuntu 24.04)
- Python path: /home/macro/projects/sonar-engine (via uv)
- sonar CLI entry point confirmed: sonar.cli.main:app
- 9 pipelines verified via --help:
  - daily_bis_ingestion, daily_curves, daily_overlays
  - daily_economic_indices, daily_monetary_indices,
    daily_credit_indices, daily_financial_indices
  - daily_cycles, daily_cost_of_capital

Create deploy/systemd/ directory:
mkdir -p deploy/systemd

Create deploy/systemd/README.md:
"""Systemd service units + timers for SONAR daily pipelines.

Architecture:
- 9 .service units invoke individual pipelines
- 9 .timer units schedule daily runs
- DAG ordering via After= + Wants= directives
- Logs → systemd journal (journalctl -u sonar-<pipeline>)

Schedule:
- 05:00 UTC: bis-ingestion (BIS European data ready)
- 06:00 UTC: curves (NSS fitting; FRED data ready)
- 06:30 UTC: overlays (ERP + CRP + rating + expinf)
- 07:00 UTC: 4 index pipelines (parallel)
- 08:00 UTC: cycles (composites from L4)
- 08:30 UTC: cost-of-capital (ERP-dependent)

Install:
  ./scripts/install-timers.sh --dry-run  # preview
  ./scripts/install-timers.sh --execute  # apply

Uninstall:
  ./scripts/uninstall-timers.sh --execute

Logs:
  journalctl -u sonar-daily-curves.service --since today
  journalctl -u sonar-daily-cycles.service -f  # follow

Troubleshoot:
  systemctl status sonar-daily-curves.timer
  systemctl list-timers sonar-*
"""

No tests; structural commit only.
```

### Commit 2 — Base service unit template + 3 foundation pipelines

```
feat(deploy): systemd service units for bis-ingestion + curves + overlays

Design decision documented in commit body:
- Service type: oneshot (pipelines are one-shot batch jobs; exit 0/non-zero)
- User: macro (matches VPS user)
- WorkingDirectory: /home/macro/projects/sonar-engine
- Environment: EnvironmentFile=/home/macro/projects/sonar-engine/.env
- ExecStart: uv run python -m sonar.pipelines.<pipeline_name>
- StandardOutput/Error: journal
- Restart: on-failure (3 attempts, 10min spacing)

Create deploy/systemd/sonar-daily-bis-ingestion.service:
```
[Unit]
Description=SONAR Daily BIS Ingestion (foundation)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=macro
Group=macro
WorkingDirectory=/home/macro/projects/sonar-engine
EnvironmentFile=/home/macro/projects/sonar-engine/.env
ExecStart=/usr/bin/uv run python -m sonar.pipelines.daily_bis_ingestion --all-t1
StandardOutput=journal
StandardError=journal
TimeoutStartSec=1800

[Install]
WantedBy=multi-user.target
```

Create deploy/systemd/sonar-daily-bis-ingestion.timer:
```
[Unit]
Description=SONAR Daily BIS Ingestion Timer

[Timer]
OnCalendar=*-*-* 05:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

Similar service + timer pairs for:
- sonar-daily-curves (06:00 UTC, --all-t1)
- sonar-daily-overlays (06:30 UTC, --all-t1, After=sonar-daily-curves.service)

Validate via systemd-analyze:
  systemd-analyze verify deploy/systemd/sonar-daily-bis-ingestion.service
  systemd-analyze verify deploy/systemd/sonar-daily-bis-ingestion.timer
  (etc for all 3 pairs)

Tests (shell): systemd-analyze verify passes for all 3 services + timers.
```

### Commit 3 — 4 index pipelines + daily_cycles + daily_cost_of_capital units

```
feat(deploy): systemd units for indices + cycles + cost-of-capital

Create service + timer pairs:

sonar-daily-economic-indices.service + .timer (07:00 UTC, --all-t1)
  After=sonar-daily-curves.service (E2 needs NSS rows)
  After=sonar-daily-overlays.service (E2 via DB-backed builder)

sonar-daily-monetary-indices.service + .timer (07:00 UTC, --all-t1)
  After=sonar-daily-curves.service
  After=sonar-daily-overlays.service (M3 needs EXPINF)

sonar-daily-credit-indices.service + .timer (07:00 UTC, --all-t1)
  After=sonar-daily-bis-ingestion.service

sonar-daily-financial-indices.service + .timer (07:00 UTC, --all-t1)
  After=sonar-daily-overlays.service

sonar-daily-cycles.service + .timer (08:00 UTC, --all-t1)
  After=sonar-daily-economic-indices.service
  After=sonar-daily-monetary-indices.service
  After=sonar-daily-credit-indices.service
  After=sonar-daily-financial-indices.service

sonar-daily-cost-of-capital.service + .timer (08:30 UTC, --all-t1)
  After=sonar-daily-overlays.service

All systemd-analyze verify clean.
Tests (shell): full set verify passes.

6 new service files + 6 new timer files. 9 total service units + 9 timers
(combined with Commit 2).
```

### Commit 4 — Install + uninstall scripts

```
feat(deploy): install/uninstall scripts for systemd timers

Create scripts/install-timers.sh:
#!/usr/bin/env bash
# Installs SONAR systemd timers. Requires sudo.
set -euo pipefail

DRY_RUN=${DRY_RUN:-false}
SYSTEMD_DIR="/etc/systemd/system"
SOURCE_DIR="$(dirname "$0")/../deploy/systemd"

if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
fi

units=(
    sonar-daily-bis-ingestion
    sonar-daily-curves
    sonar-daily-overlays
    sonar-daily-economic-indices
    sonar-daily-monetary-indices
    sonar-daily-credit-indices
    sonar-daily-financial-indices
    sonar-daily-cycles
    sonar-daily-cost-of-capital
)

for unit in "${units[@]}"; do
    echo "Installing: $unit"
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [dry-run] sudo cp $SOURCE_DIR/$unit.service $SYSTEMD_DIR/"
        echo "  [dry-run] sudo cp $SOURCE_DIR/$unit.timer $SYSTEMD_DIR/"
    else
        sudo cp "$SOURCE_DIR/$unit.service" "$SYSTEMD_DIR/"
        sudo cp "$SOURCE_DIR/$unit.timer" "$SYSTEMD_DIR/"
    fi
done

if [[ "$DRY_RUN" == "false" ]]; then
    echo "Reloading systemd..."
    sudo systemctl daemon-reload
    echo "Enabling timers..."
    for unit in "${units[@]}"; do
        sudo systemctl enable --now "$unit.timer"
    done
    echo ""
    echo "Installed 9 SONAR pipeline timers."
    echo "Verify with: sudo systemctl list-timers sonar-*"
else
    echo ""
    echo "Dry-run complete. No changes applied."
fi

Create scripts/uninstall-timers.sh:
Similar but reverse: disable + stop + remove.

Both scripts:
- Bash strict mode (set -euo pipefail)
- --dry-run flag default-safe
- Clear output
- Non-zero exit on errors

Tests (shell): shellcheck passes; dry-run verifies no system changes.
```

### Commit 5 — Documentation + troubleshooting guide

```
docs(ops): systemd deployment architecture + troubleshooting

Create docs/ops/systemd-deployment.md:

## 1. Architecture
- 9 daily pipelines orchestrated via systemd
- Service type: oneshot (pipelines exit after single run)
- Scheduled via systemd timers (OnCalendar UTC)
- DAG-aware ordering via After= directives

## 2. Schedule (UTC)
| Pipeline | Time | Dependency |
|---|---|---|
| bis-ingestion | 05:00 | network-online |
| curves | 06:00 | network-online |
| overlays | 06:30 | curves |
| economic-indices | 07:00 | curves + overlays |
| monetary-indices | 07:00 | curves + overlays |
| credit-indices | 07:00 | bis-ingestion |
| financial-indices | 07:00 | overlays |
| cycles | 08:00 | 4 index pipelines |
| cost-of-capital | 08:30 | overlays |

## 3. Install
    cd /home/macro/projects/sonar-engine
    ./scripts/install-timers.sh --dry-run    # preview
    ./scripts/install-timers.sh --execute    # apply

## 4. Verify
    sudo systemctl list-timers sonar-*       # active timers
    sudo systemctl status sonar-daily-curves.timer
    journalctl -u sonar-daily-curves.service --since today

## 5. Troubleshoot
### Pipeline fails
    journalctl -u sonar-daily-curves.service -n 100
    # Check exit code, error message
    # Re-run manually:
    cd /home/macro/projects/sonar-engine
    uv run python -m sonar.pipelines.daily_curves --all-t1 --date $(date -I -d yesterday)

### Timer not firing
    sudo systemctl list-timers sonar-*
    # Check Next Run column
    # If disabled:
    sudo systemctl enable sonar-daily-curves.timer

### DAG ordering issue
    # Check After= directives in service file
    # Verify predecessor succeeded:
    journalctl -u sonar-daily-curves.service --since today | grep "Succeeded\|Failed"

## 6. Uninstall
    ./scripts/uninstall-timers.sh --dry-run
    ./scripts/uninstall-timers.sh --execute

## 7. Emergency stop (all pipelines)
    sudo systemctl stop 'sonar-daily-*.timer'

## 8. Observability
- Logs: systemd journal (journalctl)
- Structured logs: all pipelines emit structlog JSON → journal
- Failure alerts: sonar health CLI (existing Sprint G)
- Future: Prometheus + Grafana (Phase 2+)

## 9. Security
- Pipelines run as user: macro
- No root privileges required (daemon handles privilege isolation)
- .env file permissions: 0600 (verify before deployment)
- No external network inbound (all outbound: FRED/BIS/TE/ECB/etc.)

Update CLAUDE.md to reference systemd deployment:
- New section "§Systemd ops" pointing to docs/ops/systemd-deployment.md
- Quickstart install command

No tests (documentation only).
```

### Commit 6 — Integration smoke: dry-run install + verify

```
test(deploy): dry-run verification of systemd unit configuration

Create tests/integration/test_systemd_units.sh:
#!/usr/bin/env bash
# Validates all systemd unit files parse correctly.
set -euo pipefail

DEPLOY_DIR="deploy/systemd"

echo "=== Validating systemd service units ==="
for f in "$DEPLOY_DIR"/*.service; do
    systemd-analyze verify "$f" || exit 1
done

echo "=== Validating systemd timer units ==="
for f in "$DEPLOY_DIR"/*.timer; do
    systemd-analyze verify "$f" || exit 1
done

echo "=== Install script dry-run ==="
./scripts/install-timers.sh --dry-run > /tmp/install-dry-run.log 2>&1
if ! grep -q "Dry-run complete" /tmp/install-dry-run.log; then
    echo "ERROR: install-timers.sh dry-run did not complete cleanly"
    exit 1
fi

echo "=== All systemd integration checks passed ==="

Run locally to verify:
  ./tests/integration/test_systemd_units.sh

Update CI (if CI runs on Linux with systemd — skip if not).

Shell script quality: shellcheck passes.

No Python tests this commit.
```

### Commit 7 — Retrospective + merge prep

```
docs(planning): Week 8 Sprint N systemd ops retrospective

File: docs/planning/retrospectives/week8-sprint-n-systemd-ops-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- Architecture decisions:
  - oneshot service type
  - systemd journal logs (no logrotate needed)
  - DAG ordering via After= directives
  - UTC schedule (avoids DST confusion)
- Files shipped:
  - 9 .service units
  - 9 .timer units
  - install + uninstall scripts
  - docs/ops/systemd-deployment.md
  - CLAUDE.md update
- systemd-analyze verify results
- HALT triggers fired / not fired
- Deviations from brief
- Merge strategy: branch sprint-n-systemd-ops → main via fast-forward
- Deployment readiness state:
  - Phase 1 M1 US: pipelines run manually or via new systemd
  - Operator decides when to enable timers (post-merge manual step)
  - Rollback available via uninstall script

Next steps (post-merge):
- Operator runs `sudo ./scripts/install-timers.sh --execute` on VPS
- Verifies first run via `journalctl -u sonar-*`
- Monitors first week daily runs for issues
- Phase 2+: AlertSink concrete delivery (email/webhook for failures)

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git merge sprint-n-systemd-ops
  git push origin main
```

---

## 5. HALT triggers (atomic)

0. **systemd version < required** — Ubuntu 24.04 ships 253+. If VPS has older version, some directives may not work. Commit 1 probe.
1. **Pipeline CLI entry point issues** — `sonar.cli.main:app` must be functional (Sprint G shipped). Verify `--help` works.
2. **uv path differs** — `/usr/bin/uv` assumption may be wrong on VPS. Verify via `which uv`.
3. **Environment file permissions** — `.env` at 0644 would be security issue. Document in retro.
4. **systemd-analyze verify failures** — any warning or error → HALT + fix before commit.
5. **User permissions on /etc/systemd/system/** — install script requires sudo. Can't be fully tested in CC environment; dry-run only.
6. **Shell script shellcheck warnings** — non-errors accepted; errors → fix.
7. **DAG circular dependency** — After= chains should be acyclic. Verify visually.
8. **Coverage regression** — N/A (no Python code; shell/config only).
9. **Pre-push gate fails** — fix before push, no `--no-verify`. Ruff/mypy not relevant for shell/systemd files; pytest should stay green from existing tests.

---

## 6. Acceptance

### Global sprint-end
- [ ] 6-8 commits pushed to branch `sprint-n-systemd-ops`
- [ ] 9 service units + 9 timer units in `deploy/systemd/`
- [ ] All units pass `systemd-analyze verify`
- [ ] `scripts/install-timers.sh` + `scripts/uninstall-timers.sh` shipped
- [ ] Both scripts pass shellcheck
- [ ] `docs/ops/systemd-deployment.md` shipped
- [ ] Integration test script validates setup
- [ ] Retrospective shipped
- [ ] Merge to main strategy documented (user decides when to execute)
- [ ] No `--no-verify`
- [ ] Operator ready to run `install-timers.sh --execute` post-merge

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week8-sprint-n-systemd-ops-report.md`

**Final tmux echo**:
```
SPRINT N SYSTEMD OPS DONE: N commits on branch sprint-n-systemd-ops
9 .service + 9 .timer units shipped + validated
install/uninstall scripts + docs/ops/systemd-deployment.md
systemd-analyze verify: all clean
HALT triggers: [list or "none"]
Merge: git checkout main && git merge sprint-n-systemd-ops
Artifact: docs/planning/retrospectives/week8-sprint-n-systemd-ops-report.md
```

---

## 8. Pre-push gate (mandatory)

```
uv run ruff format --check src/sonar tests    # N/A for this sprint (no Python code); run for completeness
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov          # must stay green from existing tests

# Sprint-specific gate
shellcheck scripts/install-timers.sh scripts/uninstall-timers.sh
for f in deploy/systemd/*.service deploy/systemd/*.timer; do
    systemd-analyze verify "$f" || exit 1
done
```

Full project mypy + ruff passes. No `--no-verify`.

---

## 9. Notes on implementation

### Pure ops sprint
Zero Python code changes. All work in `deploy/` + `scripts/` + `docs/`. Lower cognitive load than typical sprints.

### systemd-only, no cron
Ubuntu 24.04 systemd is robust. Cron adds complexity without benefit.

### UTC schedule
Avoids DST confusion. European data sources (BIS, ECB) publish on UTC schedule anyway. Operator can monitor via journalctl with local timezone translation.

### DAG via After= not Wants=
`After=` means "start after, but run regardless"; `Requires=` would cascade failures. `After=` allows partial success (e.g. daily_cycles runs even if one index failed).

### Journal logs vs logrotate
systemd journal handles rotation natively. Separate logrotate adds complexity without benefit for Phase 1.

### Isolated worktree workflow
Sprint N operates entirely in `/home/macro/projects/sonar-wt-sprint-n`. First commit: `cd` into that directory. All subsequent work there. Branch: `sprint-n-systemd-ops`.

### Merge back to main strategy
Post-sprint-close, user (Hugo) runs:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-n-systemd-ops
git push origin main
```
Fast-forward expected (no main commits during Sprint N since parallel Sprint M is on different branch).

### Sprint M parallel
Runs in `sonar-wt-sprint-m` worktree. Zero overlap per §3. Both merge independently.

---

*End of Week 8 Sprint N systemd ops brief. 6-8 commits. Production deployment infrastructure.*
