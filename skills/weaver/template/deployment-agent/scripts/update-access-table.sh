#!/usr/bin/env bash
# update-access-table.sh — Update README.md access table with live service data
#
# Usage: ./update-access-table.sh [hostname]
# Reads docker compose ps output and updates README.md between ACCESS markers.
#
# Requires: docker compose, jq, perl

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)
README="${REPO_ROOT}/README.md"
HOST="${1:-localhost}"

if [ ! -f "$README" ]; then
  echo "ERROR: README.md not found at ${README}"
  exit 1
fi

# Verify ACCESS markers exist
if ! grep -q '<!-- ACCESS_START -->' "$README"; then
  echo "ERROR: <!-- ACCESS_START --> marker not found in README.md"
  exit 1
fi

# Collect running services
# docker compose ps --format json outputs one JSON object per line
SERVICES_JSON=$(cd "$REPO_ROOT" && docker compose ps --format json 2>/dev/null || echo "")

if [ -z "$SERVICES_JSON" ]; then
  echo "No running services found — skipping access table update"
  exit 0
fi

# Map service names to their health check endpoints from docker-compose.yml
# This is more reliable than regex parsing
declare -A HEALTH_ENDPOINTS
while IFS= read -r line; do
  SVC_NAME=$(echo "$line" | cut -d'|' -f1)
  ENDPOINT=$(echo "$line" | cut -d'|' -f2)
  HEALTH_ENDPOINTS["$SVC_NAME"]="$ENDPOINT"
done < <(cd "$REPO_ROOT" && python3 -c "
import yaml, sys, re
with open('docker-compose.yml') as f:
    dc = yaml.safe_load(f)
for name, svc in dc.get('services', {}).items():
    hc = svc.get('healthcheck', {})
    test = hc.get('test', [])
    if isinstance(test, list):
        test = ' '.join(test)
    m = re.search(r'http://localhost:\d+(/[a-z/_-]+)', str(test))
    if m:
        print(f'{name}|{m.group(1)}')
    else:
        print(f'{name}|/healthz')
" 2>/dev/null || echo "")

# Build the table rows
TABLE_ROWS=""
echo "$SERVICES_JSON" | while IFS= read -r LINE; do
  [ -z "$LINE" ] && continue

  SERVICE=$(echo "$LINE" | jq -r '.Service // .Name // empty' 2>/dev/null)
  STATE=$(echo "$LINE" | jq -r '.State // empty' 2>/dev/null)
  HEALTH=$(echo "$LINE" | jq -r '.Health // empty' 2>/dev/null)

  # Get published port — handle both array and string formats
  PORT=$(echo "$LINE" | jq -r '
    if .Publishers then
      (.Publishers[] | select(.PublishedPort > 0) | .PublishedPort) // empty
    elif .Ports then
      (.Ports | split(",")[0] | split("->")[0] | split(":")[-1] | gsub("[^0-9]";"")) // empty
    else empty end
  ' 2>/dev/null | head -1)

  # Skip init containers, exited containers, and services without ports
  [ -z "$SERVICE" ] && continue
  [ -z "$PORT" ] && continue
  [ "$STATE" = "exited" ] && continue
  echo "$SERVICE" | grep -qE "^(migrations-init|nats-init|minio-init)$" && continue

  # Get health endpoint
  HEALTH_EP="${HEALTH_ENDPOINTS[$SERVICE]:-/healthz}"

  # Status emoji
  if [ "$HEALTH" = "healthy" ]; then
    STATUS="✅ Healthy"
  elif [ "$HEALTH" = "unhealthy" ]; then
    STATUS="❌ Unhealthy"
  elif [ "$STATE" = "running" ]; then
    STATUS="🔄 Running"
  else
    STATUS="⚪ ${STATE}"
  fi

  echo "| ${SERVICE} | http://${HOST}:${PORT} | ${HEALTH_EP} | ${STATUS} |"
done > /tmp/access-table-rows.txt

# Read the rows
ROWS=$(cat /tmp/access-table-rows.txt 2>/dev/null || echo "")

if [ -z "$ROWS" ]; then
  echo "No services with published ports — skipping"
  exit 0
fi

# Build full table
FULL_TABLE="| Service | URL | Health Check | Status |
|---------|-----|--------------|--------|
${ROWS}"

# Replace content between ACCESS markers
# Use a temp file approach for reliability
{
  sed -n '1,/<!-- ACCESS_START -->/p' "$README"
  echo "$FULL_TABLE"
  sed -n '/<!-- ACCESS_END -->/,$p' "$README"
} > /tmp/readme-updated.md

mv /tmp/readme-updated.md "$README"

SVC_COUNT=$(echo "$ROWS" | wc -l | tr -d ' ')
echo "README access table updated with ${SVC_COUNT} services"

# Cleanup
rm -f /tmp/access-table-rows.txt
