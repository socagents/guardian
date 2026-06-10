#!/usr/bin/env bash
# =============================================================================
# Dream Maker — Create GitHub Labels
# =============================================================================
#
# Creates all required labels for the agent pipeline in a GitHub repository.
#
# Usage: bash create-labels.sh <owner/repo>
#
# =============================================================================
set -euo pipefail

REPO="${1:?Usage: bash create-labels.sh <owner/repo>}"

create_label() {
  local name="$1" color="$2" desc="$3"
  if gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" 2>/dev/null; then
    echo "  Created: $name"
  else
    echo "  Exists:  $name"
  fi
}

echo "Creating agent labels for $REPO..."
echo ""

# Agent dispatch labels
echo "--- Agent Labels ---"
create_label "agent:claude-code" "7057ff" "Dispatch to Claude Code coding agent"
create_label "agent:codex-cli"   "5319e7" "Dispatch to Codex CLI coding agent"

# Status labels
echo "--- Status Labels ---"
create_label "status:ready"       "0e8a16" "Ready for agent pickup"
create_label "status:in-progress" "fbca04" "Agent working on this issue"
create_label "status:in-review"   "1d76db" "PR open, under review"
create_label "status:pr-open"     "1d76db" "PR exists for this issue"
create_label "status:merged"      "6f42c1" "PR merged"
create_label "status:done"        "0e8a16" "Issue complete"
create_label "status:blocked"     "e4e669" "Blocked by dependency"
create_label "status:dead-letter" "b60205" "Failed after max retries"
create_label "status:planning"    "c5def5" "Parent issue with sub-issues"

# Escalation
echo "--- Escalation Labels ---"
create_label "needs-human"    "d93f0b" "Agent escalated — needs human attention"
create_label "reason:budget"  "e4e669" "Budget limit reached"
create_label "reason:review-limit" "e4e669" "Review cycle limit reached"

# Complexity labels
echo "--- Complexity Labels ---"
create_label "complexity:S"  "c2e0c6" "Small task (~100K tokens, 1-3 files)"
create_label "complexity:M"  "bfdadc" "Medium task (~250K tokens, 3-8 files)"
create_label "complexity:L"  "f9d0c4" "Large task (~400K tokens, 8-15 files)"
create_label "complexity:XL" "ffc1cc" "Extra large (~500K tokens, 15+ files)"

# Layer labels
echo "--- Layer Labels ---"
create_label "layer:cognitive"     "d4c5f9" "AI/ML service layer"
create_label "layer:integration"   "bfd4f2" "Gateway/orchestration layer"
create_label "layer:runtime"       "c5def5" "Infrastructure layer"
create_label "layer:presentation"  "fef2c0" "UI layer"
create_label "layer:cross-cutting" "e6e6e6" "Spans multiple layers"

# Stage labels (for build phases)
echo "--- Stage Labels ---"
for i in $(seq 1 10); do
  create_label "stage:$i" "ededed" "Build stage $i"
done

# Type labels
echo "--- Type Labels ---"
create_label "feature"         "a2eeef" "New feature"
create_label "bug"             "d73a4a" "Bug fix"
create_label "tech-debt"       "e4e669" "Technical debt"
create_label "docs"            "0075ca" "Documentation"
create_label "infra"           "006b75" "Infrastructure"
create_label "follow-up"       "fbca04" "Follow-up from review"
create_label "deviation"       "d93f0b" "Design deviation correction"

echo ""
echo "Done! All labels created for $REPO"
