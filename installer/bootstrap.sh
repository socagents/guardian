#!/usr/bin/env bash
# Phantom — clean-VM bootstrap helper.
#
# For first-time installs on a fresh machine. Run this BEFORE install.sh.
#
# What it does:
#   1. Pre-flight: verifies docker + docker compose are present.
#   2. Prompts for PHANTOM_VERSION (defaults to "latest" floating tag).
#   3. Prompts for registry credentials (GHCR user + token).
#   4. Auto-generates four secrets with `openssl rand`:
#        MCP_TOKEN, PHANTOM_SECRET_KEK, CALDERA_API_KEY, XLOG_API_KEY,
#        CALDERA_RED_PASSWORD
#   5. Writes .env in the current directory (chmod 600).
#   6. Offers to run ./install.sh immediately.
#
# Idempotency: if .env already exists this script refuses to overwrite
# it. To re-run, delete .env first (back up the secrets you want to keep).
#
# Non-interactive mode: set PHANTOM_NONINTERACTIVE=1 and supply ALL
# values via env vars before invoking. Useful for CI/automation.

set -euo pipefail
cd "$(dirname "$0")"

# ─── Cosmetics ────────────────────────────────────────────────────────
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
  C_BOLD=$'\033[1m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m'; C_DIM=$'\033[2m'; C_RESET=$'\033[0m'
else
  C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_DIM=""; C_RESET=""
fi

say()  { printf "%s%s%s\n" "$C_BOLD" "$*" "$C_RESET"; }
info() { printf "%s→%s %s\n" "$C_DIM" "$C_RESET" "$*"; }
ok()   { printf "%s✓%s %s\n" "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf "%s!%s %s\n" "$C_YELLOW" "$C_RESET" "$*" >&2; }
die()  { printf "%s✗%s %s\n" "$C_RED" "$C_RESET" "$*" >&2; exit 1; }

# ─── Pre-flight: required tools ───────────────────────────────────────
say ""
say "Phantom bootstrap — clean-VM install helper"
say "==========================================="
say ""

info "Checking required tools…"
command -v docker >/dev/null 2>&1 \
  || die "docker not found in PATH. Install Docker Engine + compose plugin first.
       https://docs.docker.com/engine/install/"

if ! docker compose version >/dev/null 2>&1; then
  die "'docker compose' v2 plugin not available.
       https://docs.docker.com/compose/install/"
fi

command -v openssl >/dev/null 2>&1 \
  || die "openssl not found. Required to generate secrets."

ok "docker, docker compose, openssl all present"

# Verify the docker daemon is actually reachable (not just the CLI).
if ! docker info >/dev/null 2>&1; then
  die "docker daemon not reachable. Start it with:
       sudo systemctl start docker     (Linux)
       open -a Docker                  (macOS)
   And ensure your user is in the 'docker' group:
       sudo usermod -aG docker \$USER && newgrp docker"
fi
ok "docker daemon reachable"

# ─── Idempotency guard ────────────────────────────────────────────────
if [[ -f .env ]]; then
  warn ".env already exists in $(pwd)."
  warn "Refusing to overwrite. Delete it first if you want to re-bootstrap."
  warn "(Back up any secrets you need: \`cat .env > /tmp/phantom-env.bak\`)"
  exit 1
fi

# ─── Helpers for prompts ──────────────────────────────────────────────
NONINTERACTIVE="${PHANTOM_NONINTERACTIVE:-0}"

# prompt VARNAME "Question?" "default-value"
# - In interactive mode: shows the question + default, reads from tty.
# - In non-interactive mode: takes the value from env or default.
# - Always assigns to the named global var.
prompt() {
  local varname="$1" question="$2" default="${3:-}"
  local existing="${!varname:-}"

  if [[ -n "$existing" ]]; then
    info "$varname (from environment): $existing"
    return
  fi

  if [[ "$NONINTERACTIVE" == "1" ]]; then
    if [[ -z "$default" ]]; then
      die "Non-interactive mode but $varname has no value and no default."
    fi
    eval "$varname=\$default"
    info "$varname (default): $default"
    return
  fi

  local prompt_str="$question"
  [[ -n "$default" ]] && prompt_str="$prompt_str [$default]"
  read -r -p "$prompt_str: " value </dev/tty
  if [[ -z "$value" ]]; then
    value="$default"
  fi
  if [[ -z "$value" ]]; then
    die "$varname is required and no default is set."
  fi
  eval "$varname=\$value"
}

# prompt_secret VARNAME "Question?"
# Same as prompt but reads silently (no echo) for tokens/passwords.
prompt_secret() {
  local varname="$1" question="$2"
  local existing="${!varname:-}"

  if [[ -n "$existing" ]]; then
    info "$varname (from environment): <hidden, $((${#existing})) chars>"
    return
  fi

  if [[ "$NONINTERACTIVE" == "1" ]]; then
    die "Non-interactive mode but $varname is unset (no default for secrets)."
  fi

  local value
  read -r -s -p "$question: " value </dev/tty
  printf '\n'
  if [[ -z "$value" ]]; then
    die "$varname cannot be empty."
  fi
  eval "$varname=\$value"
}

# ─── Collect inputs ───────────────────────────────────────────────────
say ""
say "1) Image version"
say ""
echo "   Which Phantom version do you want to install?"
echo "   - Use a pinned version like 0.1.0 (recommended for production)"
echo "   - Use 'latest' to track the most recent release (testing only)"
echo ""
prompt PHANTOM_VERSION "Version" "latest"

say ""
say "2) GHCR registry credentials"
say ""
echo "   The image registry is private. You need:"
echo "   - The bot account username (default: kite-deploy-bot)"
echo "   - A classic PAT with read:packages scope"
echo ""
prompt PHANTOM_REGISTRY_USER "GHCR username" "kite-deploy-bot"
prompt_secret PHANTOM_REGISTRY_TOKEN "GHCR token (input hidden)"

if [[ "$PHANTOM_REGISTRY_TOKEN" == "ghp_REPLACE_WITH_TOKEN_FROM_ONBOARDING" ]] \
   || [[ ${#PHANTOM_REGISTRY_TOKEN} -lt 30 ]]; then
  die "That doesn't look like a valid GitHub PAT. Tokens start with 'ghp_'
       and are 40+ chars. Bootstrap aborted."
fi

# ─── Generate secrets ─────────────────────────────────────────────────
say ""
say "3) Auto-generating runtime secrets"
say ""
info "Generating MCP_TOKEN…"
MCP_TOKEN="$(openssl rand -hex 32)"
info "Generating PHANTOM_SECRET_KEK (AES-256 key for SecretStore)…"
PHANTOM_SECRET_KEK="$(openssl rand -base64 32)"
info "Generating CALDERA_API_KEY…"
CALDERA_API_KEY="$(openssl rand -hex 16)"
info "Generating XLOG_API_KEY…"
XLOG_API_KEY="$(openssl rand -hex 32)"
info "Generating CALDERA_RED_PASSWORD…"
CALDERA_RED_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"
info "Generating PHANTOM_DEFAULT_ADMIN_PASSWORD (v0.5.5+ bootstrap admin)…"
PHANTOM_DEFAULT_ADMIN_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"

ok "Secrets generated. They'll be written to .env (chmod 600)."

say ""
say "4) Caldera operator account"
say ""
echo "   The red-team driver account inside Caldera. The username can be"
echo "   anything; the password we just auto-generated above."
echo ""
prompt CALDERA_RED_USER "Caldera red-team username" "red"

# ─── Write .env ───────────────────────────────────────────────────────
say ""
say "5) Writing .env"
say ""

# Use a temp file then mv for atomicity (so a partial write doesn't
# leave a half-baked .env behind).
TMP_ENV="$(mktemp)"
trap 'rm -f "$TMP_ENV"' EXIT

cat > "$TMP_ENV" <<EOF
# Phantom — generated by bootstrap.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ).
# Edit by hand if needed; install.sh + the updater both read from here.

# ─── Image version ─────────────────────────────────────────────────────
PHANTOM_VERSION=$PHANTOM_VERSION

# ─── GHCR registry credentials ─────────────────────────────────────────
PHANTOM_REGISTRY_USER=$PHANTOM_REGISTRY_USER
PHANTOM_REGISTRY_TOKEN=$PHANTOM_REGISTRY_TOKEN

# ─── Internal MCP coordination token ───────────────────────────────────
MCP_TOKEN=$MCP_TOKEN

# ─── Encryption-at-rest KEK for SecretStore ────────────────────────────
# WARNING: losing this makes existing stored secrets unrecoverable.
# Back this up alongside your other deployment credentials.
PHANTOM_SECRET_KEK=$PHANTOM_SECRET_KEK

# ─── Bootstrap admin password (v0.5.5+) ────────────────────────────────
# Seeded into SecretStore on first boot. Forced change at /profile on
# first login makes this irrelevant after one login. Pre-v0.5.5 was
# hardcoded in the phantom-agent image; v0.5.5 moves it here so no
# credential is baked anywhere in any image.
PHANTOM_DEFAULT_ADMIN_PASSWORD=$PHANTOM_DEFAULT_ADMIN_PASSWORD

# ─── Caldera ───────────────────────────────────────────────────────────
CALDERA_RED_USER=$CALDERA_RED_USER
CALDERA_RED_PASSWORD=$CALDERA_RED_PASSWORD
CALDERA_API_KEY=$CALDERA_API_KEY

# ─── xlog ──────────────────────────────────────────────────────────────
XLOG_API_KEY=$XLOG_API_KEY

# ─── Operator config (filled in via /providers + /instances after login) ─
# Leaving these blank is fine. v0.4.0+ — the agent boots with default
# admin credentials (admin / value of PHANTOM_DEFAULT_ADMIN_PASSWORD
# above, also shown in the post-install message) and the operator
# configures providers + connector instances via the UI after signing
# in and rotating the default password at /profile.
EOF

mv "$TMP_ENV" .env
chmod 600 .env
trap - EXIT
ok ".env written ($(wc -l < .env) lines, mode 600)"

# ─── Optional: run install.sh ─────────────────────────────────────────
say ""
say "6) Ready to install"
say ""
echo "   Bootstrap complete. Next step is to run ./install.sh which will:"
echo "     - docker login ghcr.io (using PHANTOM_REGISTRY_TOKEN)"
echo "     - docker compose pull"
echo "     - docker compose up -d"
echo "     - wait for phantom-agent to become healthy"
echo ""

if [[ "$NONINTERACTIVE" == "1" ]]; then
  RUN_INSTALL="${PHANTOM_AUTO_INSTALL:-yes}"
else
  read -r -p "Run ./install.sh now? [Y/n]: " RUN_INSTALL </dev/tty
  RUN_INSTALL="${RUN_INSTALL:-y}"
fi

case "${RUN_INSTALL,,}" in
  y|yes|true|1)
    info "Running ./install.sh…"
    exec ./install.sh
    ;;
  *)
    ok "Skipping install. Run ./install.sh when ready."
    say ""
    say "   Saved secrets for your records:"
    say ""
    say "   PHANTOM_VERSION=$PHANTOM_VERSION"
    say "   CALDERA_RED_USER=$CALDERA_RED_USER"
    say "   CALDERA_RED_PASSWORD=$CALDERA_RED_PASSWORD"
    say ""
    say "   Other secrets are in .env. Browser login URL will be"
    say "   http://<this-host>:3000 after install completes."
    ;;
esac
