#!/bin/bash
# Audit all sonar-daily-*.service files for scope consistency.
#
# Usage:
#   ./scripts/ops/systemd_audit.sh
#
# Reports: ExecStart line per service, flags entries that hardcode
# --country US (pattern revealed Week 9 Day 4 CAL-138 — daily_curves
# was unknowingly US-only in production for weeks after Sprint N
# systemd timer enable). Flags entries that already use --all-t1 as
# T1-aware.
#
# This script is read-only — prints audit report to stdout; does not
# modify any service file. Operator runs it to confirm no silent
# US-only regression, then acts on findings (typically: update
# offending .service file ExecStart + systemctl daemon-reload).
#
# Exit code: 0 always (informational only; does not fail on findings).

set -euo pipefail

SERVICE_GLOB_PATTERN="/etc/systemd/system/sonar-daily-*.service"

echo "=== Sonar systemd services audit ==="
echo "Date: $(date -u -I)"
echo "Glob: ${SERVICE_GLOB_PATTERN}"
echo ""

shopt -s nullglob
services=(/etc/systemd/system/sonar-daily-*.service)
shopt -u nullglob

if [ ${#services[@]} -eq 0 ]; then
    echo "No services matching ${SERVICE_GLOB_PATTERN} found."
    echo "Either the systemd timers are not installed, or this is not"
    echo "running on the production VPS. Nothing to audit."
    exit 0
fi

hardcoded_count=0
t1_count=0
total_count=0

for f in "${services[@]}"; do
    name=$(basename "$f" .service)
    exec_line=$(grep "^ExecStart" "$f" | sed 's/ExecStart=//')
    flag="[OK]"

    if echo "${exec_line}" | grep -q -- "--country US"; then
        flag="[WARN HARDCODED US]"
        hardcoded_count=$((hardcoded_count + 1))
    elif echo "${exec_line}" | grep -q -- "--all-t1"; then
        flag="[OK T1]"
        t1_count=$((t1_count + 1))
    fi

    total_count=$((total_count + 1))
    echo "${flag} ${name}"
    echo "    ${exec_line}"
done

echo ""
echo "Summary:"
echo "  Total services:       ${total_count}"
echo "  --all-t1 aware:       ${t1_count}"
echo "  --country US hard:    ${hardcoded_count}"
echo ""

if [ "${hardcoded_count}" -gt 0 ]; then
    echo "Services with --country US hardcoded require update per CAL-138."
    echo "See docs/backlog/calibration-tasks.md#CAL-138 for multi-country"
    echo "expansion scope."
fi
