#!/bin/bash
# Sprint setup — create worktree + copy .env + prepare tmux session.
#
# Usage:
#   ./scripts/ops/sprint_setup.sh <branch-name> [<tmux-session-name>]
#
# Effects:
#   1. Creates a new branch <branch-name> off main in a linked worktree
#      at /home/macro/projects/sonar-wt-<suffix>.
#   2. Copies the primary repo's .env into the worktree with 0600 perms.
#   3. Creates (or reuses) a detached tmux session rooted at the worktree.
#
# Suffix derivation: strips a leading "sprint-" and trailing "-connector"
# from <branch-name>. Override worktree path with WT_PATH=<abs-path>.
# Override tmux session name with the optional second argument.
#
# Pairs with sprint_merge.sh to cover the full sprint lifecycle. Local-
# use only. Safe to re-run: aborts cleanly if the worktree already
# exists; reuses the tmux session if already running.

set -euo pipefail

BRANCH="${1:?Usage: $0 <branch-name> [tmux-session-name]}"
TMUX_SESSION_OVERRIDE="${2:-}"

log() { echo "[sprint_setup] $*"; }
halt() {
    echo "[HALT] $*" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------
GIT_DIR_ABS="$(git rev-parse --absolute-git-dir)"
GIT_COMMON_DIR_ABS="$(cd "$(git rev-parse --git-common-dir)" && pwd)"
if [ "$GIT_DIR_ABS" != "$GIT_COMMON_DIR_ABS" ]; then
    halt "Running inside a linked worktree ($GIT_DIR_ABS). Run from the primary repo root."
fi
REPO_ROOT="$(git rev-parse --show-toplevel)"
REPO_PARENT="$(cd "$REPO_ROOT/.." && pwd)"

if [ ! -f "$REPO_ROOT/.env" ]; then
    halt ".env not found at $REPO_ROOT/.env — create it before running sprint_setup."
fi

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    halt "Branch $BRANCH already exists. Use a different name or delete the existing branch."
fi

# ---------------------------------------------------------------------------
# Derive worktree path + tmux session name
# ---------------------------------------------------------------------------
SUFFIX="${BRANCH#sprint-}"
SUFFIX="${SUFFIX%-connector}"
WT_PATH="${WT_PATH:-$REPO_PARENT/sonar-wt-$SUFFIX}"

if [ -z "$TMUX_SESSION_OVERRIDE" ]; then
    TMUX_SESSION="$(echo "$BRANCH" | tr -c 'a-zA-Z0-9' '-' | cut -c1-20)"
else
    TMUX_SESSION="$TMUX_SESSION_OVERRIDE"
fi

if [ -e "$WT_PATH" ]; then
    halt "Worktree path already exists: $WT_PATH — remove it first or set WT_PATH=<other>."
fi

# ---------------------------------------------------------------------------
# Create worktree + branch
# ---------------------------------------------------------------------------
log "Creating worktree: $WT_PATH (new branch $BRANCH off main)"
git -C "$REPO_ROOT" worktree add -b "$BRANCH" "$WT_PATH" main
log "  ✓ Worktree + branch ready"

# ---------------------------------------------------------------------------
# Copy .env (0600)
# ---------------------------------------------------------------------------
log "Copying .env with 0600 perms"
cp "$REPO_ROOT/.env" "$WT_PATH/.env"
chmod 0600 "$WT_PATH/.env"
log "  ✓ .env ready"

# ---------------------------------------------------------------------------
# Create / reuse tmux session
# ---------------------------------------------------------------------------
if ! command -v tmux >/dev/null 2>&1; then
    log "  - tmux not installed; skipping session step"
elif tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    log "  - tmux session '$TMUX_SESSION' already exists; reusing"
else
    log "Creating tmux session: $TMUX_SESSION"
    tmux new-session -d -s "$TMUX_SESSION" -c "$WT_PATH"
    log "  ✓ tmux session created"
fi

# ---------------------------------------------------------------------------
# Final state
# ---------------------------------------------------------------------------
echo
log "=== Sprint setup COMPLETE ==="
log "Worktree:  $WT_PATH"
log "Branch:    $BRANCH"
log "tmux:      tmux attach -t $TMUX_SESSION"
echo
log "Next:"
log "  tmux attach -t $TMUX_SESSION"
log "  claude --dangerously-skip-permissions"
echo
