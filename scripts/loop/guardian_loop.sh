#!/usr/bin/env bash
# launchd payload for the Guardian self-learning loop. One invocation = one
# trainer pass. Positively verifies it is the dedicated loop clone, single-flights
# via a lock, resets to clean origin/main, refreshes deps on lockfile drift, opens
# a best-effort+probed IAP tunnel, then runs headless Claude Code (budget +
# wall-clock bounded) against docs/loop/PLAYBOOK.md. Honors DRY_RUN=1.
# Targets macOS /bin/bash 3.2 — no bash-4 features, no empty-array+nounset traps.
set -uo pipefail

# --- 1. Pin guard inputs from the launchd/CLI env BEFORE sourcing loop.env, so
#        loop.env can never redirect the destructive reset to another repo. ---
LOOP_HOME_PINNED="${GUARDIAN_LOOP_HOME:-$HOME/guardian-loop}"
PRIMARY_REPO="${GUARDIAN_PRIMARY_REPO:-/Users/ayman/Documents/Kite/guardian}"
RESOLVED="$(cd "$LOOP_HOME_PINNED" 2>/dev/null && pwd -P || true)"
[ -n "$RESOLVED" ] || { echo "[loop] REFUSE: no clone at $LOOP_HOME_PINNED" >&2; exit 1; }
fail_guard() { echo "[loop] REFUSE: $1 ($RESOLVED)" >&2; exit 2; }

# --- 2. Destructive-path DENY checks (ALWAYS enforced, even under DRY_RUN) ---
PRIMARY_RESOLVED="$(cd "$PRIMARY_REPO" 2>/dev/null && pwd -P || echo __none__)"
[ "$RESOLVED" != "$PRIMARY_RESOLVED" ] || fail_guard "clone is the primary working repo"
case "$RESOLVED" in "$HOME/Documents"/*|"$HOME/Documents") fail_guard "clone is under ~/Documents (TCC risk)";; esac

# --- 3. Positive-identity ALLOW checks (real runs only; relaxed for DRY_RUN test) ---
if [ "${DRY_RUN:-0}" != "1" ]; then
  [ "$(basename "$RESOLVED")" = "guardian-loop" ] || fail_guard "clone dir is not named guardian-loop"
  git -C "$RESOLVED" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail_guard "not a git work tree"
  git -C "$RESOLVED" remote get-url origin 2>/dev/null | grep -q 'kite-production/guardian' || fail_guard "origin is not kite-production/guardian"
  [ -f "$RESOLVED/.guardian-loop/IS_LOOP_CLONE" ] || fail_guard "missing .guardian-loop/IS_LOOP_CLONE sentinel — run loop_bootstrap.sh"
fi

cd "$RESOLVED" || { echo "[loop] cannot cd $RESOLVED" >&2; exit 1; }

# --- 4. Now safe to load config/secrets (API keys/model/tunnel/budget — NOT the clone home) ---
ENV_FILE="$RESOLVED/scripts/loop/loop.env"
if [ -f "$ENV_FILE" ]; then set -a; # shellcheck disable=SC1090
  . "$ENV_FILE"; set +a; fi

mkdir -p "$RESOLVED/.guardian-loop/logs"
TS="$(date +%Y%m%d-%H%M%S)"
LOG="$RESOLVED/.guardian-loop/logs/cycle-$TS.log"

# --- 5. Single-flight lock (mkdir is atomic; macOS has no util-linux flock) ---
LOCK="$RESOLVED/.guardian-loop/.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +360 2>/dev/null)" ]; then
    echo "[loop] reclaiming stale lock (>6h)" | tee -a "$LOG"; rm -rf "$LOCK"; mkdir "$LOCK"
  else
    echo "[loop] another pass is running; skipping this fire" >&2; exit 0
  fi
fi
TUNNEL_UP=0
cleanup() {
  [ "$TUNNEL_UP" = "1" ] && "$RESOLVED/scripts/guardian_tunnels.sh" stop >>"$LOG" 2>&1 || true
  rm -rf "$LOCK"
  return 0
}
trap cleanup EXIT

# --- 6. Reset to clean origin/main; never reset on a stale ref ---
echo "[loop] $TS starting in $RESOLVED; reset to clean origin/main" | tee -a "$LOG"
if ! git fetch origin main 2>&1 | tee -a "$LOG"; then
  echo "[loop] git fetch failed — aborting (won't run on a stale ref)" | tee -a "$LOG"; exit 1
fi
git checkout -B main origin/main 2>&1 | tee -a "$LOG"   # deterministic clean main even if left detached/dirty
git reset --hard origin/main     2>&1 | tee -a "$LOG"
git clean -fd                    2>&1 | tee -a "$LOG"   # NEVER add -x: would nuke .venv/node_modules/logs (all gitignored)

# --- 7. Refresh deps if lockfiles drifted since last bootstrap ---
HASH_FILE="$RESOLVED/.guardian-loop/deps.hash"
CUR_HASH="$(cat mcp/agent/package-lock.json bundles/spark/mcp/requirements.txt updater/requirements.txt 2>/dev/null | shasum | awk '{print $1}')"
if [ "${DRY_RUN:-0}" != "1" ] && { [ ! -f "$HASH_FILE" ] || [ "$CUR_HASH" != "$(cat "$HASH_FILE" 2>/dev/null)" ]; }; then
  echo "[loop] dependency lockfiles changed; refreshing deps" | tee -a "$LOG"
  "$RESOLVED/scripts/loop/loop_bootstrap.sh" --deps-only >>"$LOG" 2>&1 \
    || echo "[loop] WARN: dep refresh failed; gate may run against stale deps" | tee -a "$LOG"
fi

# --- 8. Best-effort IAP tunnel; trusted ONLY after a reachability probe of the AGENT port ---
if [ "${LOOP_USE_TUNNEL:-1}" = "1" ] && [ -f "$RESOLVED/.env.vm" ]; then
  echo "[loop] opening best-effort IAP tunnel" | tee -a "$LOG"
  if "$RESOLVED/scripts/guardian_tunnels.sh" start >>"$LOG" 2>&1 \
     && curl -sk -m 8 -o /dev/null "${GUARDIAN_BASE:-https://localhost:3001}/" 2>/dev/null; then
    TUNNEL_UP=1
  else
    echo "[loop] tunnel unavailable/unreachable; proceeding repo-only" | tee -a "$LOG"
    "$RESOLVED/scripts/guardian_tunnels.sh" stop >>"$LOG" 2>&1 || true
  fi
fi
if [ "$TUNNEL_UP" = "1" ]; then
  TUNNEL_NOTE="A live-stack IAP tunnel IS reachable this pass at \$GUARDIAN_BASE."
else
  TUNNEL_NOTE="No live-stack tunnel this pass — use repo-only audits."
fi
PROMPT="You are running the Guardian self-learning loop as an UNATTENDED scheduled trainer pass on the operator's local machine. Follow docs/loop/PLAYBOOK.md exactly, top to bottom. Do exactly one coherent unit this pass. Never push on a red gate or a checker rejection. $TUNNEL_NOTE"

CLAUDE_BIN="${CLAUDE_BIN:-claude}"
MODEL="${CLAUDE_LOOP_MODEL:-claude-fable-5}"
BUDGET_NOTE=""; [ -n "${LOOP_MAX_BUDGET_USD:-}" ] && BUDGET_NOTE="--max-budget-usd $LOOP_MAX_BUDGET_USD "

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "[loop] DRY_RUN — tunnel_up=$TUNNEL_UP — would run:" | tee -a "$LOG"
  echo "$CLAUDE_BIN --print --model $MODEL ${BUDGET_NOTE}--dangerously-skip-permissions \"<PLAYBOOK prompt>\"" | tee -a "$LOG"
  exit 0
fi

# --- 9. Run claude with budget flag + a wall-clock watchdog (macOS lacks `timeout`) ---
echo "[loop] launching headless claude -p (model=$MODEL, tunnel_up=$TUNNEL_UP); log: $LOG" | tee -a "$LOG"
if [ -n "${LOOP_MAX_BUDGET_USD:-}" ]; then
  "$CLAUDE_BIN" --print --model "$MODEL" --max-budget-usd "$LOOP_MAX_BUDGET_USD" --dangerously-skip-permissions "$PROMPT" >>"$LOG" 2>&1 &
else
  "$CLAUDE_BIN" --print --model "$MODEL" --dangerously-skip-permissions "$PROMPT" >>"$LOG" 2>&1 &
fi
CLAUDE_PID=$!
( sleep "${LOOP_MAX_SECONDS:-3600}"
  if kill -0 "$CLAUDE_PID" 2>/dev/null; then
    echo "[loop] watchdog: pass exceeded ${LOOP_MAX_SECONDS:-3600}s; terminating" | tee -a "$LOG"
    kill -TERM "$CLAUDE_PID" 2>/dev/null; sleep 10; kill -KILL "$CLAUDE_PID" 2>/dev/null
  fi ) &
WATCHDOG_PID=$!
wait "$CLAUDE_PID"; STATUS=$?
kill "$WATCHDOG_PID" 2>/dev/null || true
echo "[loop] $TS finished; claude exit=$STATUS" | tee -a "$LOG"
exit "$STATUS"
