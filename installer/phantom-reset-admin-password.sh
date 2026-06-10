#!/usr/bin/env bash
# Phantom admin-password reset (v0.5.3+)
#
# Host-side utility. Forgot the admin password? Run this from the host.
# It validates the stack is up, then execs the in-container CLI that
# does the actual SecretStore write + session revocation + audit log.
#
# Usage:
#
#   sudo /opt/phantom/phantom-reset-admin-password
#
# # Why this script exists
#
# Pre-v0.5.3 the operator-facing command was a literal docker-exec
# invocation:
#
#   docker exec -it phantom_agent node /app/cli/reset-admin.mjs
#
# That string is awkward to type, easy to mistype (especially under
# stress at 3 AM when an operator is actually locked out), and gives
# customers a worse experience than the factory-reset script. v0.5.3
# adds this thin wrapper so both recovery utilities have the same
# operator-facing shape:
#
#   sudo /opt/phantom/phantom-factory-reset            ← wipe state
#   sudo /opt/phantom/phantom-reset-admin-password     ← reset password
#
# # Why this script is host-side BUT still delegates into the container
#
# v0.4.0 deliberately put the credential-write logic inside the
# phantom-agent image (`/app/cli/reset-admin.mjs`) so the SecretStore
# write contract lives in ONE place — same code path used by the
# /profile UI's change-password flow, same audit machinery, same
# session-revocation behavior. CLAUDE.md's canonical-state discipline
# Rule 1 ("one state surface = one storage home") applies to code
# paths too: shipping a parallel host-side implementation would mean
# every future auth fix has to be applied twice. The wrapper is the
# right shape — operator-facing ergonomics on the host, credential
# logic inside the boundary that already owns it.
#
# # What you can pre-empt
#
# Set PHANTOM_CONTAINER if you renamed the agent container (default:
# phantom_agent). Set PHANTOM_INSTALL_DIR if your install lives
# somewhere other than /opt/phantom — the script reads .env from
# there to surface a clear error if the stack is misconfigured.

set -euo pipefail

CONTAINER="${PHANTOM_CONTAINER:-phantom_agent}"
INSTALL_DIR="${PHANTOM_INSTALL_DIR:-/opt/phantom}"

# ─── Helpers ────────────────────────────────────────────────────────────
info() { printf '\033[36m→\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# ─── Pre-flight ─────────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  die "'docker' not found in PATH. Install docker (or sudo) and re-run."
fi

if ! docker ps >/dev/null 2>&1; then
  die "Cannot reach docker daemon. Run this script with sudo, OR add your
       user to the docker group (sudo usermod -aG docker \$USER, then re-login)."
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  warn "Container '$CONTAINER' is not running."
  if [[ -f "$INSTALL_DIR/docker-compose.yml" ]]; then
    warn "Bring the stack up first, then re-run this script:"
    warn ""
    warn "    sudo docker compose -f $INSTALL_DIR/docker-compose.yml up -d"
    warn ""
  else
    warn "I also don't see $INSTALL_DIR/docker-compose.yml — is Phantom installed?"
    warn "If you renamed the container, set PHANTOM_CONTAINER=<name> and re-run."
  fi
  die "Cannot reset password while the agent is offline (the in-container
       CLI does the actual write — no parallel host-side implementation
       by design)."
fi

# ─── Run the in-container CLI ───────────────────────────────────────────
# `-it` requests an interactive TTY so:
#  - Password input is masked (Node's readline TTY mode).
#  - The 'Type RESET to confirm' prompt accepts stdin.
#  - Ctrl-C in the CLI cleanly aborts the reset.
#
# We exec-replace this shell with docker exec so the CLI's exit code
# propagates back to the calling shell unchanged.
info "Running in-container reset CLI"
exec docker exec -it "$CONTAINER" node /app/cli/reset-admin.mjs
