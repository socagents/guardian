#!/usr/bin/env bash
# detect-changes.sh — Detect which services changed since last deployment
#
# Usage: ./detect-changes.sh [last-deployed-sha]
# Output: Space-separated list of affected docker-compose service names
#         Prints "ALL" if infrastructure files changed
#         Prints "NONE" if no service files changed
#
# Exit codes:
#   0 — always (output indicates result)

set -euo pipefail

LAST_SHA="${1:-}"
DEPLOY_STATE_DIR="/home/{{RUNNER_USER}}/kite-deploy"
SHA_FILE="${DEPLOY_STATE_DIR}/last-deployed-sha"

# If no SHA argument, read from state file
if [ -z "$LAST_SHA" ]; then
  if [ -f "$SHA_FILE" ]; then
    LAST_SHA=$(cat "$SHA_FILE")
  fi
fi

# First run — deploy everything
if [ -z "$LAST_SHA" ]; then
  echo "ALL"
  exit 0
fi

# Verify the SHA exists in history (handles force-push or shallow clone)
if ! git cat-file -e "${LAST_SHA}^{commit}" 2>/dev/null; then
  echo "ALL"
  exit 0
fi

# Get changed files since last deployment
CHANGED_FILES=$(git diff --name-only "$LAST_SHA"..HEAD 2>/dev/null || echo "")

if [ -z "$CHANGED_FILES" ]; then
  echo "NONE"
  exit 0
fi

# Infrastructure files that affect ALL services
INFRA_PATTERNS=(
  "docker-compose.yml"
  "scripts/"
  "contracts/"
  "libs/"
  ".env"
)

for PATTERN in "${INFRA_PATTERNS[@]}"; do
  if echo "$CHANGED_FILES" | grep -q "^${PATTERN}"; then
    echo "ALL"
    exit 0
  fi
done

# Extract unique service directories from changed files
# Pattern: services/<service-name>/... → <service-name>
SERVICES=$(echo "$CHANGED_FILES" \
  | grep -oP '^services/\K[^/]+' \
  || true)
SERVICES=$(echo "$SERVICES" | sort -u | tr '\n' ' ' | sed 's/ *$//')

if [ -z "$SERVICES" ]; then
  echo "NONE"
  exit 0
fi

echo "$SERVICES"
