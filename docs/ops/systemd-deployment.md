# SONAR systemd deployment

Production scheduling for the 9 daily SONAR pipelines via systemd
service units + timers. Shipped Week 8 Sprint N.

## 1. Architecture

- 9 daily pipelines orchestrated as systemd `oneshot` services.
- Schedule via systemd `.timer` units (UTC `OnCalendar=`).
- DAG-aware ordering via `After=` directives (no cascading failures
  via `Requires=` — partial-success is acceptable).
- Logs land in the systemd journal; `journalctl -u <unit>`.
- All units run as user `macro` from
  `/home/macro/projects/sonar-engine` with the canonical `.env`
  loaded via `EnvironmentFile=`.

## 2. Schedule (UTC)

| Unit                              | Time  | Depends on                                   |
|-----------------------------------|-------|----------------------------------------------|
| `sonar-daily-bis-ingestion`       | 05:00 | `network-online.target`                      |
| `sonar-daily-curves`              | 06:00 | `network-online.target`                      |
| `sonar-daily-overlays`            | 06:30 | `sonar-daily-curves.service`                 |
| `sonar-daily-economic-indices`    | 07:00 | curves + overlays                            |
| `sonar-daily-monetary-indices`    | 07:00 | curves + overlays                            |
| `sonar-daily-credit-indices`      | 07:00 | bis-ingestion                                |
| `sonar-daily-financial-indices`   | 07:00 | overlays                                     |
| `sonar-daily-cycles`              | 08:00 | 4 index pipelines                            |
| `sonar-daily-cost-of-capital`     | 08:30 | overlays                                     |

The 07:00 indices fan out concurrently (no `After=` between them).
Schedule is UTC to sidestep DST; published European data sources
(BIS, ECB) publish on UTC schedules anyway.

## 3. Install

```bash
cd /home/macro/projects/sonar-engine
./scripts/install-timers.sh --dry-run    # preview
./scripts/install-timers.sh --execute    # apply (requires sudo)
```

`--execute` does:

1. Copy 18 unit files (`*.service` + `*.timer`) to
   `/etc/systemd/system/`.
2. `systemctl daemon-reload`.
3. `systemctl enable --now <unit>.timer` for all 9 timers.

The script aborts before touching `/etc/systemd/system/` if any of
the 18 source unit files is missing — fail-fast on partial deploy.

## 4. Verify

```bash
sudo systemctl list-timers 'sonar-*'                    # next runs
sudo systemctl status sonar-daily-curves.timer          # one timer
journalctl -u sonar-daily-curves.service --since today  # logs
journalctl -u 'sonar-daily-*' --since today             # all logs today
```

The first useful indicator is `Next:` on each timer (should match
the UTC slots in §2). After the first natural fire window, look at
`journalctl -u sonar-daily-curves.service` for an exit message
(structlog JSON line ending in `pipeline.complete` or similar).

## 5. Troubleshoot

### Pipeline fails

```bash
journalctl -u sonar-daily-curves.service -n 200
```

Last ~200 lines from the most recent run. Look for the structlog
error event + Python traceback (oneshot exit code is captured by
systemd; non-zero triggers the `Restart=on-failure` cooldown).

Re-run manually:

```bash
cd /home/macro/projects/sonar-engine
uv run python -m sonar.pipelines.daily_curves --country US \
    --date $(date -u -I -d yesterday)
```

### Timer not firing

```bash
sudo systemctl list-timers 'sonar-*'
```

If a timer is missing or shows no `Next:`, re-enable it explicitly:

```bash
sudo systemctl enable --now sonar-daily-curves.timer
```

### DAG ordering issue

```bash
sudo systemctl show sonar-daily-cycles.service \
    --property=After --property=Wants
```

To verify a predecessor actually succeeded:

```bash
journalctl -u sonar-daily-economic-indices.service --since today \
    | grep -E "Succeeded|Failed|Result"
```

`Result=success` on a `Succeeded` line means clean exit; anything
else (`Result=exit-code`, `Result=signal`) is a failure that the
`Restart=on-failure` policy will retry up to `StartLimitBurst=2`
times within `StartLimitIntervalSec=3600`s before giving up.

## 6. Uninstall

```bash
./scripts/uninstall-timers.sh --dry-run
./scripts/uninstall-timers.sh --execute
```

`--execute` does:

1. `systemctl disable --now <unit>.timer` for all 9 timers.
2. `systemctl stop <unit>.service` to terminate any in-flight pass.
3. Remove 18 unit files from `/etc/systemd/system/`.
4. `systemctl daemon-reload`.

The script tolerates "unit not found" in step 1-2 so it's safe to
run repeatedly or against a partial install.

## 7. Emergency stop (all pipelines)

```bash
sudo systemctl stop 'sonar-daily-*.timer'    # cancel future fires
sudo systemctl stop 'sonar-daily-*.service'  # cancel any in-flight
```

This leaves the units installed and enabled — re-enable individual
timers with `systemctl start` when ready, or use the uninstall
script for a clean teardown.

## 8. Observability

- **Logs**: systemd journal. Pipelines emit structlog JSON which
  systemd captures verbatim through `StandardOutput=journal` /
  `StandardError=journal`.
- **Health**: `sonar health` CLI (Sprint G) summarises last-known
  freshness across the persisted index/cycle tables.
- **Alerting**: `AlertSink` Protocol stub exists in
  `src/sonar/alerts/`; concrete delivery (email, webhook) is Phase
  2+ scope. Until then operator monitors via `journalctl` ad-hoc or
  via `sonar health` weekly.
- **Future**: Prometheus + Grafana when Phase 2 telemetry lands.

## 9. Security

- **User**: `macro` (no root required to run pipelines; only the
  install/uninstall scripts need `sudo` for the `systemctl` calls
  and copies into `/etc/systemd/system/`).
- **`.env` permissions**: must be `0600` before enabling timers in
  production. Pre-flight Sprint N probe found `0664` on the working
  copy — operator MUST run:

  ```bash
  chmod 0600 /home/macro/projects/sonar-engine/.env
  ```

  before `install-timers.sh --execute`. systemd does not enforce
  file permissions on `EnvironmentFile=` but a group-readable
  secrets file is a Phase-1 audit fail.
- **Network**: outbound only (FRED, BIS, ECB SDW, TE, FMP, etc.).
  No inbound network surface introduced.
- **Privilege isolation**: systemd runs services as the configured
  `User=` after the daemon dispatches; no setuid required.

## 10. Schedule rationale

- **05:00 UTC bis-ingestion**: BIS publishes Q-end data with a
  multi-day lag, but the SDMX endpoint stabilises overnight in
  European business hours.
- **06:00 UTC curves**: FRED daily releases (UST yields)
  publish around 21:00 ET (≈ 02:00 UTC next day); 06:00 UTC gives a
  4h cushion.
- **06:30 UTC overlays**: 30-min cushion after curves so EXPINF can
  read the freshly-persisted NSS forwards.
- **07:00 UTC indices** (4-way fan-out): all four index families
  start at the same OnCalendar slot; systemd serialises only on the
  `After=` predecessor relation. Wall-clock ~5-15 min each in
  practice, so indices typically all complete by 07:30.
- **08:00 UTC cycles**: 30-min cushion after the 07:00 + 30-min
  indices window. L4 reads all four index families; L5 reads the L4
  rows.
- **08:30 UTC cost-of-capital**: overlays must be settled (it reads
  CRP + rating-spread + EXPINF). Independent of indices/cycles, so
  the slot just chose post-cycles for log clarity.

## 11. Known limitations / Phase 2+ scope

- No alerting on failures yet (operator-driven monitoring).
- No Prometheus/Grafana wiring (manual `journalctl`).
- No template units (per-country `@.service`) — would let
  `daily_curves` cleanly serve more than just US once the pipeline
  gains `--all-t1` support.
- Email/webhook integration via `AlertSink` concrete impl is Phase 2.
- DST transitions handled by UTC scheduling; if local-time semantics
  ever matter, systemd's `OnCalendar=` supports `Europe/Lisbon` etc.
  out of the box.

## 12. Sprint N references

- Brief: `docs/planning/week8-sprint-n-systemd-ops-brief.md`
- Retrospective: `docs/planning/retrospectives/week8-sprint-n-systemd-ops-report.md`
- Unit inventory: `deploy/systemd/`
- Install/uninstall: `scripts/install-timers.sh` + `scripts/uninstall-timers.sh`
- Integration smoke: `tests/integration/test_systemd_units.sh`
