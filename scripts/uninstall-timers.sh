#!/usr/bin/env bash
# Uninstall SONAR systemd timers (reverse of install-timers.sh).
#
# Usage:
#   ./scripts/uninstall-timers.sh --dry-run   # preview only, no system change
#   ./scripts/uninstall-timers.sh --execute   # apply (requires sudo)
#
# Steps when --execute:
#   1. systemctl disable --now <unit>.timer (one per timer)
#   2. systemctl stop <unit>.service        (terminate any running pass)
#   3. Remove 18 unit files from /etc/systemd/system/
#   4. systemctl daemon-reload

set -euo pipefail

SYSTEMD_DIR="/etc/systemd/system"

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

echo "SONAR systemd uninstall — mode: ${mode}"
echo "Target : ${SYSTEMD_DIR}"
echo

if [[ "${mode}" == "execute" ]]; then
    echo "Disabling + stopping timers..."
    for unit in "${UNITS[@]}"; do
        # || true — disable on a non-existent unit returns non-zero; that
        # is acceptable here (the goal is "ensure not enabled").
        echo "  disable --now ${unit}.timer"
        sudo systemctl disable --now "${unit}.timer" 2>/dev/null || true
        sudo systemctl stop "${unit}.service" 2>/dev/null || true
    done
fi

echo
echo "Removing unit files..."
for unit in "${UNITS[@]}"; do
    for ext in service timer; do
        dst="${SYSTEMD_DIR}/${unit}.${ext}"
        if [[ "${mode}" == "dry-run" ]]; then
            echo "  [dry-run] sudo rm -f ${dst}"
        else
            echo "  rm -f ${dst}"
            sudo rm -f "${dst}"
        fi
    done
done

if [[ "${mode}" == "execute" ]]; then
    echo
    echo "Reloading systemd..."
    sudo systemctl daemon-reload
    echo
    echo "Uninstalled ${#UNITS[@]} SONAR pipeline timers."
    echo "Verify with:"
    echo "  sudo systemctl list-timers 'sonar-*'   # should show nothing"
else
    echo
    echo "Dry-run complete. No changes applied. ${#UNITS[@]} timers would be removed."
    echo "Re-run with --execute to uninstall."
fi
