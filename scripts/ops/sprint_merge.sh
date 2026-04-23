#!/bin/bash
# Sprint merge automation — atomic 10-step sequence with HALT gates.
#
# Usage:
#   ./scripts/ops/sprint_merge.sh <branch-name>
#
# Run from the PRIMARY repo (not a linked worktree). The script locates
# the worktree holding <branch-name> and pushes from there, then fast-
# forward-merges origin/<branch> into main and cleans up.
#
# Sequence (every step verified before the next; no bulk cleanup):
#   1. Verify run from primary repo (not linked worktree)
#   2. Verify workspace clean (no untracked or modified files)
#   3. Verify branch exists (locally or in a worktree)
#   4. Push <branch> to origin -u (from its worktree if linked)
#   5. Fetch origin
#   6. Checkout main + pull --ff-only
#   7. Verify fast-forward possible (main is ancestor of origin/<branch>)
#   8. Merge --ff-only origin/<branch>
#   9. Push main
#  10. Cleanup: remove worktree (if linked) + delete local + remote
#      branch + kill tmux session (Week 10 Lesson #4 fix — robust
#      under tmux 20-char session name truncation)
#
# HALT on any failure: exits non-zero with an actionable message. No
# destructive operation ever runs before the preceding verification.
#
# Local-use only (not CI). See docs/governance/WORKFLOW.md §Paralelo
# CC orchestration for context + recovery patterns.

set -euo pipefail

BRANCH="${1:?Usage: $0 <branch-name>}"

log() { echo "[sprint_merge] $*"; }
halt() {
    echo "[HALT] $*" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Step 1 — verify run from primary repo
# ---------------------------------------------------------------------------
log "Step 1/10: verify run from primary repo (not a linked worktree)"
GIT_DIR_ABS="$(git rev-parse --absolute-git-dir)"
GIT_COMMON_DIR_ABS="$(cd "$(git rev-parse --git-common-dir)" && pwd)"
if [ "$GIT_DIR_ABS" != "$GIT_COMMON_DIR_ABS" ]; then
    halt "Running inside a linked worktree ($GIT_DIR_ABS). Run from the primary repo root."
fi
REPO_ROOT="$(git rev-parse --show-toplevel)"
log "  ✓ Primary repo: $REPO_ROOT"

# ---------------------------------------------------------------------------
# Step 2 — verify workspace clean
# ---------------------------------------------------------------------------
log "Step 2/10: verify workspace clean"
if [ -n "$(git status --porcelain)" ]; then
    git status --short
    halt "Workspace has untracked or modified files. Clean first: git stash OR git clean -fd OR commit."
fi
log "  ✓ Workspace clean"

# ---------------------------------------------------------------------------
# Step 3 — verify branch exists (locally or in a worktree)
# ---------------------------------------------------------------------------
log "Step 3/10: verify branch $BRANCH exists"
if ! git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    halt "Branch $BRANCH not found locally or in any worktree."
fi
log "  ✓ Branch $BRANCH exists"

# Locate worktree that holds this branch (empty string if branch is in primary repo)
WORKTREE_FOR_BRANCH=""
WT_LINES="$(git worktree list --porcelain)"
if printf '%s\n' "$WT_LINES" | grep -q "^branch refs/heads/$BRANCH$"; then
    WORKTREE_FOR_BRANCH="$(printf '%s\n' "$WT_LINES" \
        | awk -v b="refs/heads/$BRANCH" '
            /^worktree / { path = substr($0, 10) }
            $0 == "branch " b { print path; exit }
        ')"
    if [ "$WORKTREE_FOR_BRANCH" = "$REPO_ROOT" ]; then
        WORKTREE_FOR_BRANCH=""
    fi
fi

# ---------------------------------------------------------------------------
# Step 4 — push branch to origin
# ---------------------------------------------------------------------------
log "Step 4/10: push $BRANCH to origin -u"
if [ -n "$WORKTREE_FOR_BRANCH" ]; then
    log "  Branch lives in worktree: $WORKTREE_FOR_BRANCH"
    (cd "$WORKTREE_FOR_BRANCH" && git push -u origin "$BRANCH")
else
    git push -u origin "$BRANCH"
fi
log "  ✓ Branch pushed to origin"

# ---------------------------------------------------------------------------
# Step 5 — fetch origin
# ---------------------------------------------------------------------------
log "Step 5/10: fetch origin"
git fetch origin
log "  ✓ Origin fetched"

# ---------------------------------------------------------------------------
# Step 6 — checkout main + pull --ff-only
# ---------------------------------------------------------------------------
log "Step 6/10: checkout main + pull --ff-only"
git checkout main
git pull origin main --ff-only
log "  ✓ Main up-to-date"

# ---------------------------------------------------------------------------
# Step 7 — verify fast-forward possible
# ---------------------------------------------------------------------------
log "Step 7/10: verify fast-forward possible (main ancestor of origin/$BRANCH)"
if ! git merge-base --is-ancestor HEAD "origin/$BRANCH"; then
    cat >&2 <<EOF
[HALT] Main is not an ancestor of origin/$BRANCH. Rebase needed:

    cd <branch-worktree>
    git fetch origin
    git rebase origin/main
    # resolve conflicts
    git push --force-with-lease origin $BRANCH

Then re-run: $0 $BRANCH
EOF
    exit 1
fi
log "  ✓ Fast-forward possible"

# ---------------------------------------------------------------------------
# Step 8 — merge --ff-only
# ---------------------------------------------------------------------------
log "Step 8/10: merge origin/$BRANCH --ff-only"
git merge --ff-only "origin/$BRANCH"
log "  ✓ Merge complete"

# ---------------------------------------------------------------------------
# Step 9 — push main
# ---------------------------------------------------------------------------
log "Step 9/10: push main to origin"
git push origin main
log "  ✓ Main pushed"

# ---------------------------------------------------------------------------
# Step 10 — cleanup: worktree + local branch + remote branch
# ---------------------------------------------------------------------------
log "Step 10/10: cleanup worktree + branches"
if [ -n "$WORKTREE_FOR_BRANCH" ] && [ -d "$WORKTREE_FOR_BRANCH" ]; then
    git worktree remove --force "$WORKTREE_FOR_BRANCH"
    log "  ✓ Worktree removed: $WORKTREE_FOR_BRANCH"
else
    log "  - No worktree to remove"
fi

if git branch -d "$BRANCH" >/dev/null 2>&1; then
    log "  ✓ Local branch deleted: $BRANCH"
elif git branch -D "$BRANCH" >/dev/null 2>&1; then
    log "  ✓ Local branch force-deleted: $BRANCH"
else
    log "  - Local branch already gone"
fi

if git push origin --delete "$BRANCH" >/dev/null 2>&1; then
    log "  ✓ Remote branch deleted: origin/$BRANCH"
else
    log "  - Remote branch already gone"
fi

# ---------------------------------------------------------------------------
# tmux session cleanup (Week 10 Lesson #4 fix)
#
# Prior behaviour left tmux session alive after worktree removal — session
# pointed to a non-existent path and accumulated across sprints (Day 3
# morning found 2 orphans from Day 2). Kill any session whose name
# matches the sprint prefix, robust under tmux's 20-char truncation.
#
# Prefix derivation: "sprint-" (7 chars) + first 13 chars of the part of
# BRANCH after "sprint-". Matches the session name that sprint_setup.sh
# creates via `echo "$BRANCH" | tr -c 'a-zA-Z0-9' '-' | cut -c1-20`.
# ---------------------------------------------------------------------------
SPRINT_ID="${BRANCH#sprint-}"
SESSION_PREFIX="sprint-${SPRINT_ID:0:13}"

if ! command -v tmux >/dev/null 2>&1; then
    log "  - tmux not installed; no session cleanup to attempt"
else
    MATCHING_SESSIONS="$(tmux ls 2>/dev/null | awk -F: '{print $1}' | grep "^${SESSION_PREFIX}" || true)"
    if [ -z "$MATCHING_SESSIONS" ]; then
        log "  - No tmux session to clean for $SESSION_PREFIX"
    else
        while IFS= read -r session; do
            [ -z "$session" ] && continue
            if tmux kill-session -t "$session" 2>/dev/null; then
                log "  ✓ tmux session killed: $session"
            else
                log "  - tmux kill-session no-op for: $session"
            fi
        done <<< "$MATCHING_SESSIONS"
    fi
fi

# ---------------------------------------------------------------------------
# Final state
# ---------------------------------------------------------------------------
echo
log "=== Sprint merge COMPLETE: $BRANCH ==="
echo
git log --oneline -5
echo
git worktree list
echo
