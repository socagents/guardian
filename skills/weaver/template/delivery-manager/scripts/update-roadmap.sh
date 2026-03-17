#!/usr/bin/env bash
# =============================================================================
# Roadmap Progress Detection + Artifact Regeneration
# =============================================================================
#
# Scans the repository filesystem to detect build progress, updates
# scripts/roadmap-status.json, regenerates docs/architecture.svg,
# and updates the README.md progress table.
#
# Usage:
#   bash delivery-manager/scripts/update-roadmap.sh
#   make roadmap
#
# Compatible with bash 3.2+ (macOS default).
# =============================================================================

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

STATUS_FILE="scripts/roadmap-status.json"
README_FILE="README.md"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Check if a service directory has actual source code (not just config)
has_source_code() {
  local svc_dir="$1"
  local lang="$2"

  if [ ! -d "$svc_dir" ]; then
    return 1
  fi

  case "$lang" in
    Go)
      find "$svc_dir" -name '*.go' -not -path '*/vendor/*' | head -1 | grep -q .
      ;;
    Python)
      find "$svc_dir" -name '*.py' -not -name '__pycache__' | head -1 | grep -q .
      ;;
    TypeScript)
      find "$svc_dir" \( -name '*.ts' -o -name '*.tsx' \) -not -path '*/node_modules/*' | head -1 | grep -q .
      ;;
    *)
      return 1
      ;;
  esac
}

# Check if a service is buildable (has Dockerfile + source)
is_buildable() {
  local svc_dir="$1"
  [ -f "$svc_dir/Dockerfile" ] && return 0
  return 1
}

# Determine service status: complete, in-progress, or not-started
detect_service_status() {
  local name="$1"
  local lang="$2"
  local svc_dir="services/${name}"

  if has_source_code "$svc_dir" "$lang"; then
    if is_buildable "$svc_dir"; then
      echo "complete"
    else
      echo "in-progress"
    fi
  else
    echo "not-started"
  fi
}

# Check infrastructure status based on docker-compose + init scripts
detect_infra_status() {
  local name="$1"

  case "$name" in
    postgresql)
      if grep -q "postgres:" docker-compose.yml 2>/dev/null && [ -f scripts/init-db.sql ]; then
        echo "complete"
      else
        echo "not-started"
      fi
      ;;
    nats)
      if grep -q "nats:" docker-compose.yml 2>/dev/null && [ -f scripts/init-nats.sh ]; then
        echo "complete"
      else
        echo "not-started"
      fi
      ;;
    minio)
      if grep -q "minio:" docker-compose.yml 2>/dev/null && [ -f scripts/init-minio.sh ]; then
        echo "complete"
      else
        echo "not-started"
      fi
      ;;
    lancedb)
      # Embedded in memory-service — check if memory-service has LanceDB code
      if has_source_code "services/memory-service" "Python"; then
        echo "in-progress"
      else
        echo "not-started"
      fi
      ;;
    otel-collector|prometheus|grafana)
      if grep -q "${name}" docker-compose.yml 2>/dev/null; then
        echo "in-progress"
      else
        echo "not-started"
      fi
      ;;
    *)
      echo "not-started"
      ;;
  esac
}

# Detect contracts status
detect_contracts_status() {
  local proto_count
  proto_count=$(find contracts/ -name '*.proto' 2>/dev/null | wc -l | tr -d ' ')

  if [ "$proto_count" -gt 0 ]; then
    # Check for generated code
    if find contracts/ -name '*.pb.go' -o -name '*_pb2.py' 2>/dev/null | head -1 | grep -q .; then
      echo "complete"
    else
      echo "in-progress"
    fi
  elif [ -d "contracts/" ]; then
    echo "in-progress"
  else
    echo "not-started"
  fi
}

# Determine stage status from its component service statuses
# A stage is "complete" if ALL components are complete,
# "in-progress" if ANY component is in-progress or complete,
# "not-started" otherwise.
compute_stage_status() {
  local statuses="$1"
  local has_complete=false
  local has_progress=false
  local all_complete=true

  for s in $statuses; do
    case "$s" in
      complete)
        has_complete=true
        ;;
      in-progress)
        has_progress=true
        all_complete=false
        ;;
      not-started)
        all_complete=false
        ;;
    esac
  done

  if $all_complete && $has_complete; then
    echo "complete"
  elif $has_complete || $has_progress; then
    echo "in-progress"
  else
    echo "not-started"
  fi
}

# ---------------------------------------------------------------------------
# Main detection (bash 3.2 compatible — no associative arrays)
# ---------------------------------------------------------------------------

echo "Detecting roadmap progress..."

# Service status detection — plain variables instead of associative arrays
SVC_api_gateway=$(detect_service_status "api-gateway" "Go")
SVC_control_plane=$(detect_service_status "control-plane" "Go")
SVC_agent_runtime=$(detect_service_status "agent-runtime" "Python")
SVC_memory_service=$(detect_service_status "memory-service" "Python")
SVC_tool_execution=$(detect_service_status "tool-execution" "Go")
SVC_plugin_runner=$(detect_service_status "plugin-runner" "Go")
SVC_ui=$(detect_service_status "ui" "TypeScript")
SVC_automation_service=$(detect_service_status "automation-service" "Go")
SVC_media_service=$(detect_service_status "media-service" "Go")
SVC_device_node_service=$(detect_service_status "device-node-service" "Go")
SVC_connector_slack=$(detect_service_status "connector-slack" "Go")
SVC_connector_gmail=$(detect_service_status "connector-gmail" "Go")
SVC_connector_googlechat=$(detect_service_status "connector-googlechat" "Go")
SVC_connector_notion=$(detect_service_status "connector-notion" "Go")

echo "  Service: api-gateway = $SVC_api_gateway"
echo "  Service: control-plane = $SVC_control_plane"
echo "  Service: agent-runtime = $SVC_agent_runtime"
echo "  Service: memory-service = $SVC_memory_service"
echo "  Service: tool-execution = $SVC_tool_execution"
echo "  Service: plugin-runner = $SVC_plugin_runner"
echo "  Service: ui = $SVC_ui"
echo "  Service: automation-service = $SVC_automation_service"
echo "  Service: media-service = $SVC_media_service"
echo "  Service: device-node-service = $SVC_device_node_service"
echo "  Service: connector-slack = $SVC_connector_slack"
echo "  Service: connector-gmail = $SVC_connector_gmail"
echo "  Service: connector-googlechat = $SVC_connector_googlechat"
echo "  Service: connector-notion = $SVC_connector_notion"

# Infrastructure status detection — plain variables
INFRA_postgresql=$(detect_infra_status "postgresql")
INFRA_nats=$(detect_infra_status "nats")
INFRA_minio=$(detect_infra_status "minio")
INFRA_lancedb=$(detect_infra_status "lancedb")
INFRA_otel_collector=$(detect_infra_status "otel-collector")
INFRA_prometheus=$(detect_infra_status "prometheus")
INFRA_grafana=$(detect_infra_status "grafana")

echo "  Infra: postgresql = $INFRA_postgresql"
echo "  Infra: nats = $INFRA_nats"
echo "  Infra: minio = $INFRA_minio"
echo "  Infra: lancedb = $INFRA_lancedb"
echo "  Infra: otel-collector = $INFRA_otel_collector"
echo "  Infra: prometheus = $INFRA_prometheus"
echo "  Infra: grafana = $INFRA_grafana"

# Contracts
CONTRACTS_STATUS=$(detect_contracts_status)
echo "  Contracts: ${CONTRACTS_STATUS}"

# Stage status computation
STAGE1=$(compute_stage_status "$INFRA_postgresql $INFRA_nats $INFRA_minio $CONTRACTS_STATUS")
STAGE2=$(compute_stage_status "$SVC_api_gateway $SVC_control_plane")
STAGE3=$(compute_stage_status "$SVC_agent_runtime")
STAGE4=$STAGE3  # Model/provider is part of agent-runtime
STAGE5=$(compute_stage_status "$SVC_memory_service")
STAGE6=$(compute_stage_status "$SVC_tool_execution $SVC_plugin_runner")
STAGE7=$(compute_stage_status "$SVC_ui")
STAGE8=$(compute_stage_status "$SVC_connector_slack $SVC_connector_gmail $SVC_connector_googlechat $SVC_connector_notion")
STAGE9=$STAGE6  # Plugins depend on tool-execution + plugin-runner
STAGE10=$(compute_stage_status "$SVC_automation_service $SVC_media_service $SVC_device_node_service")

echo ""
echo "Stage statuses: 1=$STAGE1 2=$STAGE2 3=$STAGE3 4=$STAGE4 5=$STAGE5 6=$STAGE6 7=$STAGE7 8=$STAGE8 9=$STAGE9 10=$STAGE10"

# ---------------------------------------------------------------------------
# Write roadmap-status.json
# ---------------------------------------------------------------------------

echo ""
echo "Writing ${STATUS_FILE}..."

jq -n \
  --arg ts "$TIMESTAMP" \
  --arg gw "$SVC_api_gateway" \
  --arg cp "$SVC_control_plane" \
  --arg ar "$SVC_agent_runtime" \
  --arg ms "$SVC_memory_service" \
  --arg te "$SVC_tool_execution" \
  --arg pr "$SVC_plugin_runner" \
  --arg ui "$SVC_ui" \
  --arg auto "$SVC_automation_service" \
  --arg media "$SVC_media_service" \
  --arg dn "$SVC_device_node_service" \
  --arg cslack "$SVC_connector_slack" \
  --arg cgmail "$SVC_connector_gmail" \
  --arg cgchat "$SVC_connector_googlechat" \
  --arg cnotion "$SVC_connector_notion" \
  --arg pg "$INFRA_postgresql" \
  --arg nats "$INFRA_nats" \
  --arg minio "$INFRA_minio" \
  --arg lance "$INFRA_lancedb" \
  --arg otel "$INFRA_otel_collector" \
  --arg prom "$INFRA_prometheus" \
  --arg graf "$INFRA_grafana" \
  --arg contracts "$CONTRACTS_STATUS" \
  --arg s1 "$STAGE1" --arg s2 "$STAGE2" --arg s3 "$STAGE3" \
  --arg s4 "$STAGE4" --arg s5 "$STAGE5" --arg s6 "$STAGE6" \
  --arg s7 "$STAGE7" --arg s8 "$STAGE8" --arg s9 "$STAGE9" \
  --arg s10 "$STAGE10" \
  '{
    last_updated: $ts,
    services: {
      "api-gateway":        { status: $gw,     stage: 2,  language: "Go",         port: 8080  },
      "control-plane":      { status: $cp,     stage: 2,  language: "Go",         port: 50050 },
      "agent-runtime":      { status: $ar,     stage: 3,  language: "Python",     port: 50051 },
      "memory-service":     { status: $ms,     stage: 5,  language: "Python",     port: 50052 },
      "tool-execution":     { status: $te,     stage: 6,  language: "Go",         port: 50053 },
      "plugin-runner":      { status: $pr,     stage: 6,  language: "Go",         port: 50056 },
      "ui":                 { status: $ui,     stage: 7,  language: "TypeScript", port: 3000  },
      "automation-service": { status: $auto,   stage: 10, language: "Go",         port: 50054 },
      "media-service":      { status: $media,  stage: 10, language: "Go",         port: 50057 },
      "device-node-service":{ status: $dn,     stage: 10, language: "Go",         port: 50055 },
      "connector-slack":    { status: $cslack, stage: 8,  language: "Go",         port: 50061 },
      "connector-gmail":    { status: $cgmail, stage: 8,  language: "Go",         port: 50063 },
      "connector-googlechat":{ status: $cgchat,stage: 8,  language: "Go",         port: 50065 },
      "connector-notion":   { status: $cnotion,stage: 8,  language: "Go",         port: 50066 }
    },
    infrastructure: {
      postgresql:     { status: $pg },
      nats:           { status: $nats },
      minio:          { status: $minio },
      lancedb:        { status: $lance },
      "otel-collector": { status: $otel },
      prometheus:     { status: $prom },
      grafana:        { status: $graf }
    },
    contracts: { status: $contracts, stage: 1 },
    stages: {
      "1": $s1, "2": $s2, "3": $s3, "4": $s4, "5": $s5,
      "6": $s6, "7": $s7, "8": $s8, "9": $s9, "10": $s10
    }
  }' > "$STATUS_FILE"

echo "  Written: ${STATUS_FILE}"

# ---------------------------------------------------------------------------
# Regenerate architecture SVG
# ---------------------------------------------------------------------------

echo ""
echo "Regenerating architecture SVG..."
python3 scripts/generate-architecture-svg.py

# ---------------------------------------------------------------------------
# Update README progress table
# ---------------------------------------------------------------------------

echo ""
echo "Updating README progress table..."

# Build the new progress table using a temp file (bash 3.2 compatible)
TABLE_FILE=$(mktemp)
{
  echo "| Stage | Name | Status |"
  echo "|-------|------|--------|"

  idx=0
  for status in "$STAGE1" "$STAGE2" "$STAGE3" "$STAGE4" "$STAGE5" \
                "$STAGE6" "$STAGE7" "$STAGE8" "$STAGE9" "$STAGE10"; do
    idx=$((idx + 1))
    case "$status" in
      complete)    emoji="✅ Complete" ;;
      in-progress) emoji="🔄 In Progress" ;;
      *)           emoji="⬜ Not Started" ;;
    esac
    case "$idx" in
      1)  name="Foundations, Contracts, Repo Layout" ;;
      2)  name="API Gateway + Control Plane" ;;
      3)  name="Agent Runtime" ;;
      4)  name="Model + Provider Services" ;;
      5)  name="Memory Service" ;;
      6)  name="Tool Execution + Skills" ;;
      7)  name="UI" ;;
      8)  name="Connectors, Routing, Delivery" ;;
      9)  name="Plugins + Extensions" ;;
      10) name="Automation, Devices, Media, Hardening" ;;
    esac
    echo "| ${idx} | ${name} | ${emoji} |"
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
  echo "  Updated: ${README_FILE}"
else
  echo "  Warning: PROGRESS markers not found in ${README_FILE}, skipping"
fi

rm -f "$TABLE_FILE"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "✅ Roadmap update complete"
echo "   Status file: ${STATUS_FILE}"
echo "   SVG diagram: docs/architecture.svg"
echo "   README:      ${README_FILE}"
