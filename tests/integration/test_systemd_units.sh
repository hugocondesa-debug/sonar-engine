#!/usr/bin/env bash
# Sprint N integration smoke — validates the systemd deployment surface
# without touching the real /etc/systemd/system/ tree.
#
# Checks:
#   1. All 18 unit files in deploy/systemd/ pass `systemd-analyze verify`
#      (no warnings, no errors).
#   2. install-timers.sh --dry-run completes with the success sentinel
#      and lists every one of the 9 unit names.
#   3. uninstall-timers.sh --dry-run completes with the success sentinel.
#   4. Both scripts pass shellcheck (use the local install via uv tool
#      install shellcheck-py if /usr/bin/shellcheck is absent).
#
# Usage:
#   ./tests/integration/test_systemd_units.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_DIR="${REPO_ROOT}/deploy/systemd"
SCRIPTS_DIR="${REPO_ROOT}/scripts"

EXPECTED_UNITS=(
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

# ---- 1. systemd-analyze verify ---------------------------------------------

echo "=== 1. systemd-analyze verify on all unit files ==="
verify_failures=0
for f in "${DEPLOY_DIR}"/*.service "${DEPLOY_DIR}"/*.timer; do
    out=$(systemd-analyze verify "$f" 2>&1 || true)
    if [[ -n "$out" ]]; then
        echo "  FAIL: $f"
        printf '    %s\n' "${out//$'\n'/$'\n'    }"
        verify_failures=$((verify_failures + 1))
    else
        echo "  ok: $(basename "$f")"
    fi
done
if [[ "$verify_failures" -ne 0 ]]; then
    echo "ABORT: ${verify_failures} unit file(s) failed systemd-analyze verify."
    exit 1
fi

# ---- 2. install-timers.sh dry-run ------------------------------------------

echo
echo "=== 2. install-timers.sh --dry-run ==="
install_log=$(mktemp -t sonar-install-dry-XXXXXX)
trap 'rm -f "${install_log}"' EXIT
"${SCRIPTS_DIR}/install-timers.sh" --dry-run > "${install_log}" 2>&1

if ! grep -q "Dry-run complete" "${install_log}"; then
    echo "FAIL: install-timers.sh dry-run did not emit 'Dry-run complete' sentinel"
    cat "${install_log}"
    exit 1
fi
echo "  sentinel ok: 'Dry-run complete'"

for unit in "${EXPECTED_UNITS[@]}"; do
    if ! grep -q "${unit}.service" "${install_log}"; then
        echo "FAIL: install-timers.sh dry-run missing reference to ${unit}.service"
        exit 1
    fi
done
echo "  9 unit names referenced ok"

# ---- 3. uninstall-timers.sh dry-run ----------------------------------------

echo
echo "=== 3. uninstall-timers.sh --dry-run ==="
uninstall_log=$(mktemp -t sonar-uninstall-dry-XXXXXX)
trap 'rm -f "${install_log}" "${uninstall_log}"' EXIT
"${SCRIPTS_DIR}/uninstall-timers.sh" --dry-run > "${uninstall_log}" 2>&1
if ! grep -q "Dry-run complete" "${uninstall_log}"; then
    echo "FAIL: uninstall-timers.sh dry-run did not emit 'Dry-run complete' sentinel"
    cat "${uninstall_log}"
    exit 1
fi
echo "  sentinel ok: 'Dry-run complete'"

# ---- 4. shellcheck ---------------------------------------------------------

echo
echo "=== 4. shellcheck on install + uninstall scripts ==="
if ! command -v shellcheck >/dev/null 2>&1; then
    echo "  shellcheck not on PATH; install via 'uv tool install shellcheck-py'"
    exit 1
fi
shellcheck \
    "${SCRIPTS_DIR}/install-timers.sh" \
    "${SCRIPTS_DIR}/uninstall-timers.sh" \
    "${BASH_SOURCE[0]}"
echo "  shellcheck clean"

echo
echo "=== All systemd integration checks passed ==="
