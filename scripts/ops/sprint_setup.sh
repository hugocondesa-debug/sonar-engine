#!/bin/bash
# Sprint setup — create worktree + copy .env + stage brief + prepare tmux.
#
# Usage:
#   ./scripts/ops/sprint_setup.sh <branch-name> [<tmux-session-name>] \
#       [--brief <path>]
#
# Effects:
#   1. Resolves brief via convention glob (or explicit --brief flag) and
#      verifies it exists in main BEFORE worktree creation (Week 10
#      Lesson #1 fix — prevents silent no-brief worktree).
#   2. Creates a new branch <branch-name> off main in a linked worktree
#      at /home/macro/projects/sonar-wt-<suffix>.
#   3. Copies the primary repo's .env into the worktree with 0600 perms.
#   4. Copies the resolved brief into <worktree>/docs/planning/ so CC
#      sees it at sprint arranque (eliminates manual cp step).
#   5. Creates (or reuses) a detached tmux session rooted at the worktree.
#
# Brief resolution:
#   - If --brief <path> provided, use that path verbatim (relative to
#     primary repo root or absolute).
#   - Else glob docs/planning/week*-sprint-<sprint_id>-*brief.md in the
#     primary repo. Zero matches = HALT; multiple matches = HALT (ask
#     operator to disambiguate with explicit --brief).
#   - <sprint_id> is <branch-name> with leading "sprint-" stripped.
#
# Suffix derivation: strips a leading "sprint-" and trailing "-connector"
# from <branch-name>. Override worktree path with WT_PATH=<abs-path>.
# Override tmux session name with the optional second argument.
#
# Pairs with sprint_merge.sh to cover the full sprint lifecycle. Local-
# use only. Safe to re-run: aborts cleanly if the worktree already
# exists; reuses the tmux session if already running.

set -euo pipefail

log() { echo "[sprint_setup] $*"; }
halt() {
    echo "[HALT] $*" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Argument parsing — supports positional BRANCH + TMUX_SESSION_OVERRIDE plus
# optional --brief <path> flag (Week 10 Lesson #1 fix).
# ---------------------------------------------------------------------------
BRANCH=""
TMUX_SESSION_OVERRIDE=""
BRIEF_PATH=""

while [ $# -gt 0 ]; do
    case "$1" in
        --brief)
            [ $# -ge 2 ] || halt "--brief requires a path argument."
            BRIEF_PATH="$2"
            shift 2
            ;;
        --brief=*)
            BRIEF_PATH="${1#--brief=}"
            shift
            ;;
        -h|--help)
            sed -n '2,32p' "$0"
            exit 0
            ;;
        *)
            if [ -z "$BRANCH" ]; then
                BRANCH="$1"
            elif [ -z "$TMUX_SESSION_OVERRIDE" ]; then
                TMUX_SESSION_OVERRIDE="$1"
            else
                halt "Unexpected extra argument: $1"
            fi
            shift
            ;;
    esac
done

[ -n "$BRANCH" ] || halt "Usage: $0 <branch-name> [tmux-session-name] [--brief <path>]"

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
# Brief pre-flight (Week 10 Lesson #1 fix)
#
# Resolve and verify brief exists in the primary repo BEFORE creating the
# worktree. Prevents the silent no-brief worktree pattern that burdened
# Week 10 with ~25 min cumulative manual cp operations.
# ---------------------------------------------------------------------------
SPRINT_ID_FOR_BRIEF="${BRANCH#sprint-}"

if [ -z "$BRIEF_PATH" ]; then
    # Convention glob: docs/planning/week*-sprint-<sprint_id>-*brief.md
    shopt -s nullglob
    BRIEF_MATCHES=("$REPO_ROOT"/docs/planning/week*-sprint-"${SPRINT_ID_FOR_BRIEF}"-*brief.md)
    shopt -u nullglob

    if [ ${#BRIEF_MATCHES[@]} -eq 0 ]; then
        cat >&2 <<EOF
[HALT] No brief found matching docs/planning/week*-sprint-${SPRINT_ID_FOR_BRIEF}-*brief.md
[HALT] Expected shape: docs/planning/week10-sprint-${SPRINT_ID_FOR_BRIEF}-<slug>-brief.md
[HALT] Steps:
[HALT]   1. Upload brief via scp into docs/planning/
[HALT]   2. Commit to main + push
[HALT]   3. Re-run: $0 $BRANCH
[HALT]
[HALT] OR supply --brief <path> for a non-convention location.
EOF
        exit 1
    fi

    if [ ${#BRIEF_MATCHES[@]} -gt 1 ]; then
        echo "[HALT] Multiple briefs match, ambiguous:" >&2
        printf '[HALT]   %s\n' "${BRIEF_MATCHES[@]}" >&2
        echo "[HALT] Use --brief <path> to disambiguate." >&2
        exit 1
    fi

    BRIEF_PATH="${BRIEF_MATCHES[0]}"
else
    # Explicit --brief: resolve relative to REPO_ROOT if not absolute.
    case "$BRIEF_PATH" in
        /*) : ;;
        *) BRIEF_PATH="$REPO_ROOT/$BRIEF_PATH" ;;
    esac
fi

[ -f "$BRIEF_PATH" ] || halt "Brief not found: $BRIEF_PATH"
log "  ✓ Brief located: $BRIEF_PATH"

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
# Stage brief into worktree (Week 10 Lesson #1 fix)
# ---------------------------------------------------------------------------
WORKTREE_BRIEF_DIR="$WT_PATH/docs/planning"
mkdir -p "$WORKTREE_BRIEF_DIR"
cp "$BRIEF_PATH" "$WORKTREE_BRIEF_DIR/"
log "  ✓ Brief staged in worktree: $WORKTREE_BRIEF_DIR/$(basename "$BRIEF_PATH")"

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
# DB canonical link (Week 10 Lesson #14 fix)
#
# `git worktree add` checks out tracked placeholder files under data/,
# leaving `data/sonar-dev.db` as a 0-byte stub in the worktree. Pre-flight
# audits (sqlite3 queries, schema diffs, coverage checks) then silently
# return empty — forcing the operator to manually symlink into the primary
# repo's live DB before CC can start. This step automates that.
#
# Three scenarios:
#   (a) primary DB exists + worktree DB absent       → symlink
#   (b) primary DB exists + worktree DB = 0-byte stub → remove stub, symlink
#   (c) primary DB exists + worktree DB is real file → WARN, preserve
# ---------------------------------------------------------------------------
PRIMARY_DB="${REPO_ROOT}/data/sonar-dev.db"
WORKTREE_DB="${WT_PATH}/data/sonar-dev.db"

if [[ -f "$PRIMARY_DB" ]]; then
    mkdir -p "${WT_PATH}/data"

    # Remove 0-byte stub if present; preserve any real file (warn only).
    if [[ -f "$WORKTREE_DB" ]] && [[ ! -L "$WORKTREE_DB" ]]; then
        DB_SIZE=$(stat -c%s "$WORKTREE_DB")
        if [[ "$DB_SIZE" -eq 0 ]]; then
            rm "$WORKTREE_DB"
        else
            log "  - WARNING: non-zero file at $WORKTREE_DB, not overwriting"
            log "            If this is a stale copy, remove manually and re-run"
        fi
    fi

    # Create symlink only if target slot is empty (preserves case (c)).
    if [[ ! -e "$WORKTREE_DB" ]]; then
        ln -sf "$PRIMARY_DB" "$WORKTREE_DB"
        log "  ✓ DB symlinked: data/sonar-dev.db -> $PRIMARY_DB"
    fi
else
    log "  - WARNING: canonical DB not found at $PRIMARY_DB"
    log "            Worktree data/ may be empty; audit queries will fail"
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
