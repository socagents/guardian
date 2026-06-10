#!/usr/bin/env bash
# =============================================================================
# Cognitive Roadmap Progress Scorer
# =============================================================================
#
# Uses Claude to assess actual source code against ROADMAP.md deliverables.
# Produces per-deliverable and per-stage percentage scores, then updates
# ROADMAP.md, README.md progress table, and scripts/roadmap-status.json.
#
# Usage:
#   bash deployment-agent/scripts/update-roadmap-progress.sh
#
# Requires: claude (Claude Code CLI), jq, perl
#
# Called by the daily agent-roadmap-progress.yml workflow (not on every deploy).
# =============================================================================

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

ROADMAP_FILE="ROADMAP.md"
README_FILE="README.md"
STATUS_FILE="scripts/roadmap-status.json"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# ---------------------------------------------------------------------------
# Step 1: Collect project inventory for Claude
# ---------------------------------------------------------------------------

echo "=== Collecting project inventory ==="

# Build a compact inventory of what exists in each service directory
INVENTORY_FILE=$(mktemp)

{
  echo "# Project Source Code Inventory"
  echo "# Generated: ${TIMESTAMP}"
  echo ""

  # Services
  for svc_dir in services/*/; do
    svc_name=$(basename "$svc_dir")
    echo "## Service: ${svc_name}"
    echo "Directory: ${svc_dir}"

    if [ ! -d "$svc_dir" ]; then
      echo "Status: directory missing"
      echo ""
      continue
    fi

    # File count by type
    go_count=$(find "$svc_dir" -name '*.go' -not -path '*/vendor/*' 2>/dev/null | wc -l | tr -d ' ')
    py_count=$(find "$svc_dir" -name '*.py' -not -name '__pycache__' -not -path '*/__pycache__/*' 2>/dev/null | wc -l | tr -d ' ')
    ts_count=$(find "$svc_dir" \( -name '*.ts' -o -name '*.tsx' \) -not -path '*/node_modules/*' 2>/dev/null | wc -l | tr -d ' ')
    proto_count=$(find "$svc_dir" -name '*.proto' 2>/dev/null | wc -l | tr -d ' ')

    echo "Files: Go=${go_count} Python=${py_count} TypeScript=${ts_count} Proto=${proto_count}"

    has_dockerfile="no"
    [ -f "${svc_dir}Dockerfile" ] && has_dockerfile="yes"
    echo "Dockerfile: ${has_dockerfile}"

    # List all source files (compact)
    echo "Source files:"
    find "$svc_dir" \( -name '*.go' -o -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.proto' \) \
      -not -path '*/vendor/*' -not -path '*/node_modules/*' -not -path '*/__pycache__/*' \
      2>/dev/null | sort | sed 's/^/  /' || true

    # Show key file contents (main entry points, limited to first 80 lines each)
    for entry in "${svc_dir}cmd/server/main.go" "${svc_dir}main.go" "${svc_dir}app/main.py" \
                 "${svc_dir}src/app/page.tsx" "${svc_dir}src/app/layout.tsx" \
                 "${svc_dir}internal/server/server.go" "${svc_dir}internal/handler/handler.go"; do
      if [ -f "$entry" ]; then
        echo ""
        echo "--- ${entry} (first 80 lines) ---"
        head -80 "$entry"
        echo "--- end ---"
      fi
    done

    echo ""
  done

  # Contracts
  echo "## Contracts"
  echo "Directory: contracts/"
  if [ -d "contracts/" ]; then
    proto_files=$(find contracts/ -name '*.proto' 2>/dev/null | wc -l | tr -d ' ')
    echo "Proto files: ${proto_files}"
    echo "Files:"
    find contracts/ -name '*.proto' 2>/dev/null | sort | sed 's/^/  /' || true

    # Show proto file contents (limited)
    find contracts/ -name '*.proto' 2>/dev/null | head -10 | while read -r pf; do
      echo ""
      echo "--- ${pf} (first 50 lines) ---"
      head -50 "$pf"
      echo "--- end ---"
    done
  else
    echo "Status: directory missing"
  fi

  echo ""

  # Infrastructure files
  echo "## Infrastructure"
  for f in docker-compose.yml scripts/init-db.sql scripts/init-nats.sh scripts/init-minio.sh; do
    if [ -f "$f" ]; then
      echo "--- ${f} (first 40 lines) ---"
      head -40 "$f"
      echo "--- end ---"
    else
      echo "${f}: missing"
    fi
  done

  # Migrations
  echo ""
  echo "## Database Migrations"
  find services/ -path '*/migrations/*.sql' 2>/dev/null | sort | sed 's/^/  /' || echo "  none found"

} > "$INVENTORY_FILE"

INVENTORY_SIZE=$(wc -c < "$INVENTORY_FILE" | tr -d ' ')
echo "  Inventory collected: ${INVENTORY_SIZE} bytes"

# ---------------------------------------------------------------------------
# Step 2: Extract deliverable list from ROADMAP.md
# ---------------------------------------------------------------------------

echo "=== Extracting deliverables from ROADMAP.md ==="

DELIVERABLES_FILE=$(mktemp)

# Extract numbered deliverable rows (lines matching "| N.N |")
grep -E '^\| [0-9X]+\.[0-9]+ \|' "$ROADMAP_FILE" > "$DELIVERABLES_FILE" || true

DELIVERABLE_COUNT=$(wc -l < "$DELIVERABLES_FILE" | tr -d ' ')
echo "  Found ${DELIVERABLE_COUNT} deliverables"

# ---------------------------------------------------------------------------
# Step 3: Send to Claude for cognitive scoring
# ---------------------------------------------------------------------------

echo "=== Sending to Claude for cognitive progress scoring ==="

PROMPT_FILE=$(mktemp)
RESULT_FILE=$(mktemp)

cat > "$PROMPT_FILE" << 'PROMPT_HEADER'
You are a progress auditor for the {{PROJECT_NAME}} AI platform. Your job is to score
each deliverable's completion percentage (0-100) by examining the actual
source code inventory against what the roadmap says should exist.

SCORING RULES:
- 0%: Nothing exists for this deliverable
- 5-15%: Only scaffolding/boilerplate exists (hello-world, empty handlers, placeholder pages)
- 20-40%: Partial implementation (some real logic, but core functionality missing)
- 50-70%: Core functionality works but incomplete (missing features, no tests, hardcoded values)
- 80-90%: Mostly complete (works, has tests, minor gaps)
- 100%: Fully implemented and production-ready

Be STRICT. A scaffold with placeholder TODO comments is 5-10%, not 50%.
A service that builds and has health checks but no real business logic is 10-15%.
Only score high if you see actual implementation of the described capability.

OUTPUT FORMAT: Return ONLY valid JSON, no markdown fences, no commentary.
The JSON must have this structure:
{
  "scored_at": "<ISO timestamp>",
  "deliverables": {
    "1.1": {"score": <0-100>, "reason": "<one line>"},
    "1.2": {"score": <0-100>, "reason": "<one line>"},
    ...
  },
  "stages": {
    "1": <0-100 average of stage 1 deliverables>,
    "2": <0-100>,
    ...
    "10": <0-100>
  },
  "cross_cutting": {
    "X.1": {"score": <0-100>, "reason": "<one line>"},
    ...
  },
  "infrastructure": {
    "postgresql": <0-100>,
    "nats": <0-100>,
    "minio": <0-100>,
    "lancedb": <0-100>,
    "otel-collector": <0-100>,
    "prometheus": <0-100>,
    "grafana": <0-100>
  },
  "overall": <0-100 weighted average>
}

PROMPT_HEADER

{
  echo ""
  echo "=== ROADMAP DELIVERABLES ==="
  cat "$DELIVERABLES_FILE"
  echo ""
  echo "=== SOURCE CODE INVENTORY ==="
  cat "$INVENTORY_FILE"
} >> "$PROMPT_FILE"

# Call Claude Code CLI for the cognitive scoring
if command -v claude >/dev/null 2>&1; then
  claude -p "$(cat "$PROMPT_FILE")" --output-format text > "$RESULT_FILE" 2>/dev/null
elif command -v anthropic >/dev/null 2>&1; then
  anthropic messages create --model claude-sonnet-4-20250514 \
    --max-tokens 4096 \
    -f "$(cat "$PROMPT_FILE")" > "$RESULT_FILE" 2>/dev/null
else
  echo "ERROR: Neither 'claude' nor 'anthropic' CLI found. Cannot run cognitive scoring."
  echo "Install Claude Code CLI: npm install -g @anthropic-ai/claude-code"
  rm -f "$INVENTORY_FILE" "$DELIVERABLES_FILE" "$PROMPT_FILE" "$RESULT_FILE"
  exit 1
fi

# Validate JSON output
if ! jq empty "$RESULT_FILE" 2>/dev/null; then
  # Try to extract JSON from within the response (Claude sometimes wraps it)
  grep -o '{.*}' "$RESULT_FILE" | jq empty 2>/dev/null && \
    grep -o '{.*}' "$RESULT_FILE" > "${RESULT_FILE}.clean" && \
    mv "${RESULT_FILE}.clean" "$RESULT_FILE" || {
    echo "ERROR: Claude did not return valid JSON. Raw output:"
    head -20 "$RESULT_FILE"
    rm -f "$INVENTORY_FILE" "$DELIVERABLES_FILE" "$PROMPT_FILE" "$RESULT_FILE"
    exit 1
  }
fi

echo "  Scoring complete"

# ---------------------------------------------------------------------------
# Step 4: Update ROADMAP.md with per-deliverable scores
# ---------------------------------------------------------------------------

echo "=== Updating ROADMAP.md ==="

# For each deliverable, update the progress column
while IFS= read -r line; do
  # Extract deliverable ID (e.g., "1.1", "X.3")
  DEL_ID=$(echo "$line" | grep -oE '[0-9X]+\.[0-9]+' | head -1)
  [ -z "$DEL_ID" ] && continue

  # Get score from JSON
  if [[ "$DEL_ID" == X.* ]]; then
    SCORE=$(jq -r ".cross_cutting.\"${DEL_ID}\".score // 0" "$RESULT_FILE")
  else
    SCORE=$(jq -r ".deliverables.\"${DEL_ID}\".score // 0" "$RESULT_FILE")
  fi

  # Replace "| 0% |" with "| <score>% |" for this deliverable's row
  # Match the pattern: "| <ID> | <description> | <old_progress> |"
  perl -i -pe "s/^(\\| ${DEL_ID} \\|[^|]+\\|)\\s*\\d+%\\s*\\|/\$1 ${SCORE}% |/" "$ROADMAP_FILE"

done < "$DELIVERABLES_FILE"

# Update infrastructure scores
for infra in postgresql nats minio lancedb otel-collector prometheus grafana; do
  SCORE=$(jq -r ".infrastructure.\"${infra}\" // 0" "$RESULT_FILE")
  # Infrastructure rows use component name, not numbered IDs
  DISPLAY_NAME=""
  case "$infra" in
    postgresql)     DISPLAY_NAME="PostgreSQL 16" ;;
    nats)           DISPLAY_NAME="NATS 2.10 + JetStream" ;;
    minio)          DISPLAY_NAME="MinIO" ;;
    lancedb)        DISPLAY_NAME="LanceDB" ;;
    otel-collector) DISPLAY_NAME="OTel Collector" ;;
    prometheus)     DISPLAY_NAME="Prometheus" ;;
    grafana)        DISPLAY_NAME="Grafana" ;;
  esac
  perl -i -pe "s/^(\\| ${DISPLAY_NAME} \\|)\\s*\\d+%\\s*\\|/\$1 ${SCORE}% |/" "$ROADMAP_FILE"
done

echo "  ROADMAP.md updated"

# ---------------------------------------------------------------------------
# Step 5: Update README.md progress table
# ---------------------------------------------------------------------------

echo "=== Updating README.md progress table ==="

STAGE_NAMES=(
  "Foundations, Contracts, Repo Layout"
  "API Gateway + Control Plane"
  "Agent Runtime"
  "Model + Provider Services"
  "Memory Service"
  "Tool Execution + Skills"
  "UI"
  "Connectors, Routing, Delivery"
  "Plugins + Extensions"
  "Automation, Devices, Media, Hardening"
)

# Build the new progress table
TABLE_FILE=$(mktemp)
{
  echo "| Stage | Name | Progress | Key Deliverables |"
  echo "|-------|------|----------|------------------|"

  for i in $(seq 1 10); do
    SCORE=$(jq -r ".stages.\"${i}\" // 0" "$RESULT_FILE")
    NAME="${STAGE_NAMES[$((i-1))]}"

    # Read key deliverables from current README (preserve them)
    KEY_DELIVS=$(grep -E "^\| ${i} \|" "$README_FILE" | sed 's/.*| [0-9]*% |//' | sed 's/|$//' | tr -d ' ' || echo "")
    if [ -z "$KEY_DELIVS" ]; then
      # Fallback: read from ROADMAP progress summary
      KEY_DELIVS=$(grep -E "^\| ${i} \|" "$ROADMAP_FILE" | head -1 | awk -F'|' '{print $5}' | sed 's/^ *//;s/ *$//')
    fi

    echo "| ${i} | ${NAME} | ${SCORE}% | ${KEY_DELIVS} |"
  done
} > "$TABLE_FILE"

# Replace content between PROGRESS markers in README
if grep -q "PROGRESS_START" "$README_FILE" 2>/dev/null; then
  awk -v tablefile="$TABLE_FILE" '
    /<!-- PROGRESS_START -->/ {
      print
      while ((getline line < tablefile) > 0) print line
      close(tablefile)
      skip=1
      next
    }
    /<!-- PROGRESS_END -->/ { skip=0 }
    !skip { print }
  ' "$README_FILE" > "${README_FILE}.tmp"
  mv "${README_FILE}.tmp" "$README_FILE"
  echo "  README.md updated"
else
  echo "  Warning: PROGRESS markers not found in README.md"
fi

rm -f "$TABLE_FILE"

# Also update ROADMAP.md progress summary table
ROADMAP_TABLE=$(mktemp)
{
  echo "| Stage | Name | Progress | Key Deliverables |"
  echo "|-------|------|----------|------------------|"

  for i in $(seq 1 10); do
    SCORE=$(jq -r ".stages.\"${i}\" // 0" "$RESULT_FILE")
    NAME="${STAGE_NAMES[$((i-1))]}"
    KEY_DELIVS=$(grep -E "^\| ${i} \|" "$ROADMAP_FILE" | head -1 | awk -F'|' '{print $5}' | sed 's/^ *//;s/ *$//')
    echo "| ${i} | ${NAME} | ${SCORE}% | ${KEY_DELIVS} |"
  done
} > "$ROADMAP_TABLE"

if grep -q "PROGRESS_START" "$ROADMAP_FILE" 2>/dev/null; then
  awk -v tablefile="$ROADMAP_TABLE" '
    /<!-- PROGRESS_START -->/ {
      print
      while ((getline line < tablefile) > 0) print line
      close(tablefile)
      skip=1
      next
    }
    /<!-- PROGRESS_END -->/ { skip=0 }
    !skip { print }
  ' "$ROADMAP_FILE" > "${ROADMAP_FILE}.tmp"
  mv "${ROADMAP_FILE}.tmp" "$ROADMAP_FILE"
  echo "  ROADMAP.md progress summary updated"
fi

rm -f "$ROADMAP_TABLE"

# ---------------------------------------------------------------------------
# Step 6: Update roadmap-status.json
# ---------------------------------------------------------------------------

echo "=== Updating roadmap-status.json ==="

OVERALL=$(jq -r '.overall // 0' "$RESULT_FILE")

jq -n \
  --arg ts "$TIMESTAMP" \
  --argjson scores "$(cat "$RESULT_FILE")" \
  '{
    last_updated: $ts,
    overall_progress: $scores.overall,
    stages: $scores.stages,
    deliverables: $scores.deliverables,
    cross_cutting: $scores.cross_cutting,
    infrastructure: $scores.infrastructure
  }' > "$STATUS_FILE"

echo "  roadmap-status.json updated"

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

rm -f "$INVENTORY_FILE" "$DELIVERABLES_FILE" "$PROMPT_FILE" "$RESULT_FILE"

echo ""
echo "=== Progress scoring complete ==="
echo "  Overall: ${OVERALL}%"
echo "  Files updated: ROADMAP.md, README.md, scripts/roadmap-status.json"
