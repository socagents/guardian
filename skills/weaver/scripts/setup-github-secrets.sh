#!/usr/bin/env bash
# =============================================================================
# Dream Maker — GitHub Secrets Setup
# =============================================================================
#
# Reads secrets from .env and provisions them as GitHub repository secrets
# (and optionally environment secrets for the 'dev' environment).
#
# Usage:
#   bash scripts/setup-github-secrets.sh              # uses .env in current dir
#   bash scripts/setup-github-secrets.sh /path/to/.env # uses specified file
#   bash scripts/setup-github-secrets.sh --dry-run     # preview without setting
#
# Prerequisites:
#   - gh CLI installed and authenticated
#   - .env file with values filled in (copy from .env.example)
#
# =============================================================================
set -euo pipefail

# --- Parse arguments --------------------------------------------------------

DRY_RUN=false
ENV_FILE=".env"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    *) ENV_FILE="$arg" ;;
  esac
done

# --- Validate prerequisites -------------------------------------------------

if ! command -v gh &>/dev/null; then
  echo "ERROR: gh CLI not found. Install from https://cli.github.com"
  exit 1
fi

if ! gh auth status &>/dev/null; then
  echo "ERROR: gh CLI not authenticated. Run: gh auth login"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found."
  echo "Copy .env.example to .env and fill in your values first."
  exit 1
fi

# --- Load .env file ---------------------------------------------------------

# Source the env file (only exports lines matching KEY=VALUE, ignoring comments)
set -a
while IFS='=' read -r key value; do
  # Skip comments and empty lines
  [[ -z "$key" || "$key" =~ ^# ]] && continue
  # Trim whitespace
  key=$(echo "$key" | xargs)
  value=$(echo "$value" | xargs)
  # Skip if value is a placeholder
  if [[ "$value" == *"xxxx"* || "$value" == *"XXXXXXXXX"* || -z "$value" ]]; then
    echo "SKIP: $key (placeholder value, not set)"
    continue
  fi
  export "$key=$value"
done < "$ENV_FILE"
set +a

# --- Resolve repo -----------------------------------------------------------

REPO="${GITHUB_ORG:-}/${GITHUB_REPO:-}"
if [[ "$REPO" == "/" ]]; then
  echo "ERROR: GITHUB_ORG and GITHUB_REPO must be set in $ENV_FILE"
  exit 1
fi

echo "============================================"
echo "Dream Maker — GitHub Secrets Setup"
echo "============================================"
echo "Repository: $REPO"
echo "Env file:   $ENV_FILE"
echo "Dry run:    $DRY_RUN"
echo "============================================"
echo ""

# --- Helper function --------------------------------------------------------

set_secret() {
  local name="$1"
  local value="$2"
  local env="${3:-}"  # optional environment name

  if [[ -z "$value" || "$value" == *"xxxx"* || "$value" == *"XXXXXXXXX"* ]]; then
    echo "  SKIP  $name (no value)"
    return
  fi

  if $DRY_RUN; then
    local masked="${value:0:4}...${value: -4}"
    if [[ -n "$env" ]]; then
      echo "  [DRY] Would set $name = $masked (environment: $env)"
    else
      echo "  [DRY] Would set $name = $masked"
    fi
    return
  fi

  if [[ -n "$env" ]]; then
    echo "$value" | gh secret set "$name" --repo "$REPO" --env "$env"
    echo "  SET   $name (environment: $env)"
  else
    echo "$value" | gh secret set "$name" --repo "$REPO"
    echo "  SET   $name"
  fi
}

# --- Set repository secrets -------------------------------------------------

echo "Setting repository secrets..."
echo ""

set_secret "PROJECT_PAT" "${PROJECT_PAT:-}"

echo ""

# --- Set environment secrets (dev) ------------------------------------------

echo "Setting environment secrets (dev)..."
echo ""

# Create dev environment if it doesn't exist (gh doesn't have a create command,
# but setting a secret in an env auto-creates it)

set_secret "SLACK_BOT_USER_OAUTH_ACCESS_TOKEN" "${SLACK_BOT_USER_OAUTH_ACCESS_TOKEN:-}" "dev"
set_secret "SLACK_BUILDS_WEBHOOK"              "${SLACK_BUILDS_WEBHOOK:-}"              "dev"
set_secret "SLACK_BUILD_CHANNEL"               "${SLACK_BUILD_CHANNEL:-}"               "dev"
set_secret "SLACK_ISSUES_CHANNEL"              "${SLACK_ISSUES_CHANNEL:-}"              "dev"
set_secret "SLACK_TOKENS_CHANNEL"              "${SLACK_TOKENS_CHANNEL:-}"              "dev"

echo ""

# --- Summary ----------------------------------------------------------------

echo "============================================"
if $DRY_RUN; then
  echo "Dry run complete. No secrets were modified."
  echo "Remove --dry-run to apply changes."
else
  echo "Secrets provisioned successfully!"
  echo ""
  echo "Verify with: gh secret list --repo $REPO"
  echo "Env secrets: gh secret list --repo $REPO --env dev"
fi
echo "============================================"
