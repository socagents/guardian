#!/usr/bin/env bash
# Phantom — VM compose drift check
#
# Compares the canonical local docker-compose.yml against the file
# currently deployed on phantom-vm at $VM_REMOTE_REPO/docker-compose.yml.
# Run before sync-to-VM so a stale VM compose can never silently mask
# a local change (e.g. a new volume mount that doesn't take effect
# until the VM compose actually carries the declaration).
#
# Why this exists: during the v0.1.34 TLS smoke test, the VM's
# docker-compose.yml had drifted from the canonical local file by
# weeks — xlog and caldera lacked the /tls volume mount despite the
# local file having it. force-recreate didn't help because the VM
# spec was stale. The drift was invisible until the smoke test caught
# it accidentally. This script makes the check explicit + automatic.
#
# v0.3.0+ NOTE — this script checks the REPO-ROOT docker-compose.yml
# (the dev compose, used by build.yml deploy-compose on phantom-vm)
# against the file at $VM_REMOTE_REPO. The repo-root compose still
# uses tag-based image references (`image: xlog:local`). The CUSTOMER
# compose at installer/docker-compose.yml uses digest pinning and is
# NOT what runs on phantom-vm — it ships in the customer install kit.
# So this drift check is the right shape for the dev/CI flow but
# would not make sense for customer installs.
#
# For a customer-side drift check, the relevant question is "does my
# /opt/phantom/.env have the digests the manifest says?". That's a
# separate audit; the customer compose's fail-loud fallback
# (`@${DIGEST_*:-sha256:invalid_digest_run_installer_first}`) already
# surfaces this on `docker compose up` if anything's missing.
#
# Behavior:
#   - Reads VM credentials from .env.vm (same convention as the rest
#     of the dev workflow).
#   - Opens an IAP tunnel, runs `cat $VM_REMOTE_REPO/docker-compose.yml`
#     over SSH, diffs against the local file.
#   - Exit 0 if identical, exit 1 if drifted (with a unified diff on
#     stderr).
#   - --quiet to suppress the diff body (just status + summary).
#
# CLAUDE.md adds this to the pre-deploy gate: run this script before
# tar+scp so the operator catches drift at planning time, not at
# debug time.

set -euo pipefail

QUIET=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --quiet|-q) QUIET=1; shift ;;
    --help|-h)
      cat <<EOF
Usage: $0 [--quiet]

Compare local docker-compose.yml to the deployed copy on phantom-vm.

Exit codes:
  0  identical — sync-to-VM is safe
  1  drifted   — VM is out of date with local; sync first

Reads VM credentials from .env.vm (VM_NAME, VM_ZONE, VM_PROJECT,
VM_USER, VM_PASSWORD, VM_LOCAL_SSH_PORT, VM_REMOTE_REPO).
EOF
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

# ─── Locate repo root + load .env.vm ──────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV_FILE="$REPO_ROOT/.env.vm"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env.vm not found at $ENV_FILE" >&2
  echo "       This file holds the dev VM coordinates (gitignored)." >&2
  exit 2
fi

# Read just the variables we need — `source .env.vm` would choke on
# the JSON service-account block at the bottom of that file (the
# format isn't pure shell). Pull the keys we need with grep+cut.
read_env() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-
}

VM_NAME="$(read_env VM_NAME)"
VM_ZONE="$(read_env VM_ZONE)"
VM_PROJECT="$(read_env VM_PROJECT)"
VM_USER="$(read_env VM_USER)"
VM_PASSWORD="$(read_env VM_PASSWORD)"
VM_LOCAL_SSH_PORT="$(read_env VM_LOCAL_SSH_PORT)"
VM_REMOTE_REPO="$(read_env VM_REMOTE_REPO)"

for var in VM_NAME VM_ZONE VM_PROJECT VM_USER VM_PASSWORD VM_LOCAL_SSH_PORT VM_REMOTE_REPO; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var missing from $ENV_FILE" >&2
    exit 2
  fi
done

# ─── Pre-flight: required tools ───────────────────────────────────

for tool in gcloud sshpass diff; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: '$tool' not in PATH" >&2
    exit 2
  fi
done

LOCAL_COMPOSE="$REPO_ROOT/docker-compose.yml"
[[ -f "$LOCAL_COMPOSE" ]] || { echo "ERROR: $LOCAL_COMPOSE missing" >&2; exit 2; }

# ─── Open IAP tunnel ──────────────────────────────────────────────

# Kill any leftover tunnels; concurrent ones on the same local port
# would queue requests unpredictably.
pkill -f "start-iap-tunnel.*$VM_NAME.*$VM_LOCAL_SSH_PORT" 2>/dev/null || true
sleep 1

gcloud compute start-iap-tunnel "$VM_NAME" 22 \
  --local-host-port="localhost:$VM_LOCAL_SSH_PORT" \
  --zone="$VM_ZONE" --project="$VM_PROJECT" \
  > /tmp/check-vm-compose-iap.log 2>&1 &
TUNNEL_PID=$!

# Cleanup on exit so we don't leak tunnels across runs.
cleanup() {
  kill "$TUNNEL_PID" 2>/dev/null || true
  wait "$TUNNEL_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Give the tunnel a moment to bind. The tunnel command exits non-zero
# if the bind fails, which our wait-for-readiness loop catches as a
# port-not-listening state.
for _ in $(seq 1 10); do
  sleep 1
  if nc -z localhost "$VM_LOCAL_SSH_PORT" 2>/dev/null; then
    break
  fi
done

# ─── Pull the remote compose ──────────────────────────────────────

REMOTE_COMPOSE="$(mktemp)"
trap 'rm -f "$REMOTE_COMPOSE"; cleanup' EXIT INT TERM

if ! SSHPASS="$VM_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -o PubkeyAuthentication=no \
  -o PreferredAuthentications=password \
  -p "$VM_LOCAL_SSH_PORT" \
  "$VM_USER@localhost" \
  "cat $VM_REMOTE_REPO/docker-compose.yml" \
  > "$REMOTE_COMPOSE" 2>/dev/null
then
  echo "ERROR: failed to read $VM_REMOTE_REPO/docker-compose.yml on VM" >&2
  exit 2
fi

# ─── Diff ─────────────────────────────────────────────────────────

if cmp -s "$LOCAL_COMPOSE" "$REMOTE_COMPOSE"; then
  echo "✓ docker-compose.yml on $VM_NAME matches local — sync-to-VM is safe."
  exit 0
fi

LOCAL_LINES=$(wc -l < "$LOCAL_COMPOSE")
REMOTE_LINES=$(wc -l < "$REMOTE_COMPOSE")

cat <<EOF >&2
✗ docker-compose.yml has DRIFTED between local and $VM_NAME.

  local  ($LOCAL_LINES lines): $LOCAL_COMPOSE
  remote ($REMOTE_LINES lines): $VM_USER@$VM_NAME:$VM_REMOTE_REPO/docker-compose.yml

EOF

if [[ "$QUIET" -eq 0 ]]; then
  echo "  Unified diff (local → remote):" >&2
  echo "  ─────────────────────────────────────────────────────" >&2
  diff -u "$LOCAL_COMPOSE" "$REMOTE_COMPOSE" | sed 's/^/  /' >&2 || true
  echo "  ─────────────────────────────────────────────────────" >&2
  echo >&2
fi

cat <<'EOF' >&2
  Sync the local file to the VM before continuing the deploy:

    SSHPASS="$VM_PASSWORD" sshpass -e scp \
      -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o PubkeyAuthentication=no -o PreferredAuthentications=password \
      -P "$VM_LOCAL_SSH_PORT" \
      ./docker-compose.yml \
      "$VM_USER@localhost:$VM_REMOTE_REPO/docker-compose.yml"

  Then `docker compose up -d --force-recreate` on the VM if any volume
  mount or env block changed (otherwise compose treats existing
  containers as up-to-date and won't apply the new spec).
EOF

exit 1
