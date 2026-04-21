#!/usr/bin/env bash
# Install SONAR systemd timers for the 9 daily pipelines.
#
# Usage:
#   ./scripts/install-timers.sh --dry-run   # preview only, no system change
#   ./scripts/install-timers.sh --execute   # apply (requires sudo)
#
# Steps when --execute:
#   1. Copy 18 unit files (9 .service + 9 .timer) to /etc/systemd/system/
#   2. systemctl daemon-reload
#   3. systemctl enable --now <unit>.timer  (one per timer)

set -euo pipefail

SYSTEMD_DIR="/etc/systemd/system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="${SCRIPT_DIR}/../deploy/systemd"

UNITS=(
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

mode=""
case "${1:-}" in
    --dry-run) mode="dry-run" ;;
    --execute) mode="execute" ;;
    *)
        echo "Usage: $0 --dry-run | --execute" >&2
        exit 2
        ;;
esac

# Verify source files exist before promising anything.
missing=0
for unit in "${UNITS[@]}"; do
    for ext in service timer; do
        src="${SOURCE_DIR}/${unit}.${ext}"
        if [[ ! -f "${src}" ]]; then
            echo "ERROR: missing unit file: ${src}" >&2
            missing=$((missing + 1))
        fi
    done
done
if [[ "${missing}" -ne 0 ]]; then
    echo "ABORT: ${missing} unit file(s) missing." >&2
    exit 1
fi

echo "SONAR systemd install — mode: ${mode}"
echo "Source : ${SOURCE_DIR}"
echo "Target : ${SYSTEMD_DIR}"
echo

for unit in "${UNITS[@]}"; do
    for ext in service timer; do
        src="${SOURCE_DIR}/${unit}.${ext}"
        dst="${SYSTEMD_DIR}/${unit}.${ext}"
        if [[ "${mode}" == "dry-run" ]]; then
            echo "  [dry-run] sudo cp ${src} ${dst}"
        else
            echo "  cp ${src} -> ${dst}"
            sudo cp "${src}" "${dst}"
        fi
    done
done

if [[ "${mode}" == "execute" ]]; then
    echo
    echo "Reloading systemd..."
    sudo systemctl daemon-reload

    echo "Enabling timers..."
    for unit in "${UNITS[@]}"; do
        echo "  enable --now ${unit}.timer"
        sudo systemctl enable --now "${unit}.timer"
    done

    echo
    echo "Installed ${#UNITS[@]} SONAR pipeline timers."
    echo "Verify with:"
    echo "  sudo systemctl list-timers 'sonar-*'"
    echo "  journalctl -u sonar-daily-curves.service --since today"
else
    echo
    echo "Dry-run complete. No changes applied. ${#UNITS[@]} timers ready."
    echo "Re-run with --execute to install."
fi
