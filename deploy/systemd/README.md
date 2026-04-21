# SONAR systemd deployment units

Production scheduling for the 9 daily SONAR pipelines via systemd
service units + timers. Phase 1 deployment infrastructure shipped in
Week 8 Sprint N.

## Architecture

- 9 `.service` units invoke individual pipelines (oneshot batch jobs).
- 9 `.timer` units schedule the daily runs (UTC calendar events).
- DAG ordering via `After=` directives on the service units.
- Logs land in the systemd journal — `journalctl -u <unit-name>`.
- All units run as user `macro` from
  `/home/macro/projects/sonar-engine` with the canonical `.env` loaded
  via `EnvironmentFile=`.

## Schedule (UTC)

| Unit                              | Time  | Depends on                            |
|-----------------------------------|-------|---------------------------------------|
| `sonar-daily-bis-ingestion`       | 05:00 | `network-online.target`               |
| `sonar-daily-curves`              | 06:00 | `network-online.target`               |
| `sonar-daily-overlays`            | 06:30 | `sonar-daily-curves.service`          |
| `sonar-daily-economic-indices`    | 07:00 | curves + overlays                     |
| `sonar-daily-monetary-indices`    | 07:00 | curves + overlays                     |
| `sonar-daily-credit-indices`      | 07:00 | bis-ingestion                         |
| `sonar-daily-financial-indices`   | 07:00 | overlays                              |
| `sonar-daily-cycles`              | 08:00 | 4 index pipelines                     |
| `sonar-daily-cost-of-capital`     | 08:30 | overlays                              |

The 07:00 indices fan out in parallel (no `After=` between them).

## Install

```bash
cd /home/macro/projects/sonar-engine
./scripts/install-timers.sh --dry-run    # preview
./scripts/install-timers.sh --execute    # apply (requires sudo)
```

## Verify

```bash
sudo systemctl list-timers 'sonar-*'                    # next runs
sudo systemctl status sonar-daily-curves.timer          # one timer
journalctl -u sonar-daily-curves.service --since today  # logs
```

## Uninstall

```bash
./scripts/uninstall-timers.sh --execute
```

See `docs/ops/systemd-deployment.md` for full architecture, install
walkthrough, troubleshooting, and security notes.

## Pre-flight environment (Sprint N probe — 2026-04-21)

- systemd: 255.4 (Ubuntu 24.04 noble)
- `uv`: 0.11.7 at `/home/macro/.local/bin/uv` (NOT `/usr/bin/uv`)
- `.env`: present at `/home/macro/projects/sonar-engine/.env`
  (mode 0664 — should be tightened to 0600 before enabling timers in
  production; see `docs/ops/systemd-deployment.md` §9 Security)
- 9 pipelines verified importable + `--help` clean. CLI conventions:
  - `daily_bis_ingestion` — `--countries CSV` (no date arg; uses
    `--start-date`/`--end-date` defaults of `today-90d` → `today`).
  - `daily_curves` — `--country` (single, required) + `--date` (no
    `--all-t1`; Phase 1 ships US only).
  - 7 others — `--all-t1` + `--date` (required).

## Production enablement

This sprint ships the unit files and install scripts but does **not**
enable them on the VPS. Operator runs the install script post-merge
when they decide to flip the switch.
