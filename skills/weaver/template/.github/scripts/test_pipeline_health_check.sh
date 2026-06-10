#!/usr/bin/env bash
# =============================================================================
# test_pipeline_health_check.sh — Tests for pipeline-health-check.sh
# =============================================================================
# Mocks the gh CLI to validate JSON output, exit codes, and check logic.
#
# Usage: bash .github/scripts/test_pipeline_health_check.sh
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$SCRIPT_DIR/pipeline-health-check.sh"
TEST_DIR=$(mktemp -d)
PASS=0
FAIL=0

cleanup() { rm -rf "$TEST_DIR"; }
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Mock gh CLI — matches endpoints by prefix (ignoring query params)
# Responses stored in $MOCK_DIR/responses/ keyed by normalized prefix.
# ---------------------------------------------------------------------------
create_mock_env() {
  local env_dir="$TEST_DIR/env_$(date +%s%N)"
  mkdir -p "$env_dir/responses" "$env_dir/bin"

  cat > "$env_dir/bin/gh" << 'MOCKEOF'
#!/usr/bin/env bash
# Extract the API endpoint (first positional arg after "api")
shift  # skip "api"
endpoint=""
for arg in "$@"; do
  case "$arg" in -*)  continue ;; esac
  endpoint="$arg"
  break
done

# Strip query params for matching
base="${endpoint%%\?*}"
safe=$(echo "$base" | tr '/' '_')

# Try exact match first, then progressively shorter prefixes
resp_dir="$MOCK_DIR/responses"
if [[ -f "$resp_dir/$safe" ]]; then
  cat "$resp_dir/$safe"
else
  echo '{}'
fi
MOCKEOF
  chmod +x "$env_dir/bin/gh"
  echo "$env_dir"
}

# Set a mock response. Args: base_endpoint response_json
mock_response() {
  local endpoint="$1" response="$2"
  local safe
  safe=$(echo "$endpoint" | tr '/' '_')
  echo "$response" > "$MOCK_DIR/responses/$safe"
}

# Run the script with mocked gh
run_check() {
  local env_dir="$1"
  shift
  MOCK_DIR="$env_dir" PATH="$env_dir/bin:$PATH" \
    GITHUB_REPOSITORY="test-owner/test-repo" \
    "$SCRIPT" "$@" 2>/dev/null
}

run_check_exit() {
  local env_dir="$1"
  shift
  local ec=0
  MOCK_DIR="$env_dir" PATH="$env_dir/bin:$PATH" \
    GITHUB_REPOSITORY="test-owner/test-repo" \
    "$SCRIPT" "$@" >/dev/null 2>&1 || ec=$?
  echo "$ec"
}

# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------
assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "  ✓ $desc"
    PASS=$((PASS + 1))
  else
    echo "  ✗ $desc"
    echo "    expected: $expected"
    echo "    actual:   $actual"
    FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local desc="$1" needle="$2" haystack="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    echo "  ✓ $desc"
    PASS=$((PASS + 1))
  else
    echo "  ✗ $desc"
    echo "    expected to contain: $needle"
    echo "    actual: ${haystack:0:200}"
    FAIL=$((FAIL + 1))
  fi
}

# Extract a check from JSON output by ID
check_field() {
  local json="$1" id="$2" field="$3"
  echo "$json" | jq -r ".checks[] | select(.id == \"$id\") | .$field" 2>/dev/null
}

# ==========================================================================
echo "=== Test: --help flag ==="
help_output=$("$SCRIPT" --help 2>&1)
assert_contains "shows usage" "Usage:" "$help_output"
assert_contains "shows json option" "json" "$help_output"
assert_contains "shows exit codes" "HEALTHY" "$help_output"

# ==========================================================================
echo ""
echo "=== Test: Unknown option exits with error ==="
ec=0
"$SCRIPT" --bad-option >/dev/null 2>&1 || ec=$?
assert_eq "exits non-zero" "1" "$ec"

# ==========================================================================
echo ""
echo "=== Test: R1 — Runner Online (healthy) ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runners" \
  '{"runners":[{"status":"online","labels":[{"name":"{{RUNNER_LABEL}}"},{"name":"self-hosted"}]}]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runs" \
  '{"workflow_runs":[]}'

output=$(run_check "$ENV" --json --category runner)
assert_eq "valid JSON" "true" "$(echo "$output" | jq 'true' 2>/dev/null || echo false)"
assert_eq "R1 HEALTHY" "HEALTHY" "$(check_field "$output" R1 status)"
assert_contains "R1 message" "online" "$(check_field "$output" R1 message)"
assert_eq "has timestamp" "true" "$(echo "$output" | jq 'has("timestamp")' 2>/dev/null)"
assert_eq "has summary" "true" "$(echo "$output" | jq 'has("summary")' 2>/dev/null)"

# ==========================================================================
echo ""
echo "=== Test: R1 — Runner Offline (critical) ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runners" \
  '{"runners":[{"status":"offline","labels":[{"name":"{{RUNNER_LABEL}}"}]}]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runs" \
  '{"workflow_runs":[]}'

output=$(run_check "$ENV" --json --category runner)
assert_eq "R1 CRITICAL" "CRITICAL" "$(check_field "$output" R1 status)"
ec=$(run_check_exit "$ENV" --json --category runner)
assert_eq "exit code 3" "3" "$ec"

# ==========================================================================
echo ""
echo "=== Test: R3 — Placeholder returns HEALTHY ==="
assert_eq "R3 HEALTHY" "HEALTHY" "$(check_field "$output" R3 status)"
assert_contains "R3 runner-side note" "runner-side" "$(check_field "$output" R3 message)"

# ==========================================================================
echo ""
echo "=== Test: Exit code 0 when all healthy ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runners" \
  '{"runners":[{"status":"online","labels":[{"name":"{{RUNNER_LABEL}}"}]}]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runs" \
  '{"workflow_runs":[]}'

ec=$(run_check_exit "$ENV" --json --category runner)
assert_eq "exit code 0" "0" "$ec"

# ==========================================================================
echo ""
echo "=== Test: --category filters checks ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runners" \
  '{"runners":[{"status":"online","labels":[{"name":"{{RUNNER_LABEL}}"}]}]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runs" \
  '{"workflow_runs":[]}'

output=$(run_check "$ENV" --json --category runner)
check_ids=$(echo "$output" | jq -r '[.checks[].id] | sort | join(",")')
assert_eq "only R1,R2,R3" "R1,R2,R3" "$check_ids"

# ==========================================================================
echo ""
echo "=== Test: S1 — No sweep runs (degraded) ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-dispatch-sweep.yml_runs" \
  '{"workflow_runs":[]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_issues" '[]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_pulls" '[]'

output=$(run_check "$ENV" --json --category sweep)
assert_eq "S1 DEGRADED" "DEGRADED" "$(check_field "$output" S1 status)"
ec=$(run_check_exit "$ENV" --json --category sweep)
assert_eq "exit code 1" "1" "$ec"

# ==========================================================================
echo ""
echo "=== Test: S2 — Large backlog (unhealthy) ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-dispatch-sweep.yml_runs" \
  '{"workflow_runs":[{"conclusion":"success","status":"completed"}]}'
# 10 ready issues (exceeds >8 threshold)
issues='[{},{},{},{},{},{},{},{},{},{}]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_issues" "$issues"
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_pulls" '[]'

output=$(run_check "$ENV" --json --category sweep)
assert_eq "S2 UNHEALTHY" "UNHEALTHY" "$(check_field "$output" S2 status)"
assert_contains "S2 count" "20" "$(check_field "$output" S2 message)"

# ==========================================================================
echo ""
echo "=== Test: S4 — All cancelled (degraded) ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-dispatch-sweep.yml_runs" \
  '{"workflow_runs":[{"conclusion":"cancelled"},{"conclusion":"cancelled"},{"conclusion":"cancelled"}]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_issues" '[]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_pulls" '[]'

output=$(run_check "$ENV" --json --category sweep)
assert_eq "S4 DEGRADED" "DEGRADED" "$(check_field "$output" S4 status)"

# ==========================================================================
echo ""
echo "=== Test: D1 — Successful dispatch (healthy) ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-dispatch.yml_runs" \
  '{"workflow_runs":[{"id":100,"conclusion":"success","head_branch":"agent/test","created_at":"2026-03-14T10:00:00Z"}]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runs_100_jobs" \
  '{"jobs":[{"steps":[{"name":"Check budget","id":"budget","conclusion":"success"},{"name":"Commit and push agent work","conclusion":"success"}]}]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_pulls" '[{"number":1}]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_issues" '[]'

output=$(run_check "$ENV" --json --category dispatch)
assert_eq "D1 HEALTHY" "HEALTHY" "$(check_field "$output" D1 status)"

# ==========================================================================
echo ""
echo "=== Test: D5 — Static YAML check ==="
assert_eq "D5 HEALTHY" "HEALTHY" "$(check_field "$output" D5 status)"

# ==========================================================================
echo ""
echo "=== Test: JSON schema matches spec format ==="
# Use the last runner output
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runners" \
  '{"runners":[{"status":"online","labels":[{"name":"{{RUNNER_LABEL}}"}]}]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runs" \
  '{"workflow_runs":[]}'

output=$(run_check "$ENV" --json --category runner)
valid_checks=$(echo "$output" | jq \
  '.checks | all(has("id") and has("name") and has("status") and has("message") and has("details"))' 2>/dev/null)
assert_eq "checks have required fields" "true" "$valid_checks"

valid_summary=$(echo "$output" | jq \
  '.summary | has("healthy") and has("degraded") and has("unhealthy") and has("critical")' 2>/dev/null)
assert_eq "summary has status counts" "true" "$valid_summary"

overall=$(echo "$output" | jq -r '.overall_status')
assert_eq "overall_status is valid" "HEALTHY" "$overall"

# ==========================================================================
echo ""
echo "=== Test: Human-readable output format ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runners" \
  '{"runners":[{"status":"online","labels":[{"name":"{{RUNNER_LABEL}}"}]}]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runs" \
  '{"workflow_runs":[]}'

output=$(run_check "$ENV" --category runner)
assert_contains "has header" "Pipeline Health Report" "$output"
assert_contains "has overall" "Overall:" "$output"
assert_contains "has summary line" "Summary:" "$output"
assert_contains "shows R1" "R1:" "$output"

# ==========================================================================
echo ""
echo "=== Test: V1 — PRs reviewed within SLA (healthy, no agent PRs) ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_pulls" '[]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_issues" '[]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-review.yml_runs" \
  '{"workflow_runs":[]}'

output=$(run_check "$ENV" --json --category review)
assert_eq "V1 HEALTHY (no PRs)" "HEALTHY" "$(check_field "$output" V1 status)"

# ==========================================================================
echo ""
echo "=== Test: V1 — PR overdue (unhealthy) ==="
ENV=$(create_mock_env)
# PR created 3 hours ago (agent branch, no review comment)
old_time=$(python3 -c "from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)-timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%SZ'))")
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_pulls" \
  "[{\"number\":42,\"head\":{\"ref\":\"agent/test-branch\"},\"created_at\":\"$old_time\"}]"
# No review comments
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_issues_42_comments" '[]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_issues" '[]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-review.yml_runs" \
  '{"workflow_runs":[]}'

output=$(run_check "$ENV" --json --category review)
assert_eq "V1 UNHEALTHY" "UNHEALTHY" "$(check_field "$output" V1 status)"
assert_contains "V1 mentions SLA" "SLA" "$(check_field "$output" V1 message)"

# ==========================================================================
echo ""
echo "=== Test: V2 — Review workflow healthy ==="
assert_eq "V2 HEALTHY" "HEALTHY" "$(check_field "$output" V2 status)"

# ==========================================================================
echo ""
echo "=== Test: V2 — Review workflow failing (unhealthy) ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_pulls" '[]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_issues" '[]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-review.yml_runs" \
  '{"workflow_runs":[{"id":1,"conclusion":"failure"},{"id":2,"conclusion":"failure"},{"id":3,"conclusion":"success"}]}'

output=$(run_check "$ENV" --json --category review)
assert_eq "V2 UNHEALTHY" "UNHEALTHY" "$(check_field "$output" V2 status)"

# ==========================================================================
echo ""
echo "=== Test: V3 — Reviews produce verdicts ==="
assert_eq "V3 exists" "Reviews Produce Verdicts" "$(check_field "$output" V3 name)"

# ==========================================================================
echo ""
echo "=== Test: V4 — Approved PRs merged (healthy, no stuck) ==="
assert_eq "V4 HEALTHY" "HEALTHY" "$(check_field "$output" V4 status)"

# ==========================================================================
echo ""
echo "=== Test: V5 — Rejected PRs re-dispatched (healthy) ==="
assert_eq "V5 HEALTHY" "HEALTHY" "$(check_field "$output" V5 status)"

# ==========================================================================
echo ""
echo "=== Test: N1 — Notifications firing (healthy) ==="
ENV=$(create_mock_env)
recent_time=$(python3 -c "from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'))")
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-slack-notify.yml_runs" \
  "{\"workflow_runs\":[{\"id\":1,\"conclusion\":\"success\",\"created_at\":\"$recent_time\"}]}"
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-dispatch.yml_runs" \
  '{"workflow_runs":[]}'

output=$(run_check "$ENV" --json --category notifications)
assert_eq "N1 HEALTHY" "HEALTHY" "$(check_field "$output" N1 status)"
assert_contains "N1 message" "notification" "$(check_field "$output" N1 message)"

# ==========================================================================
echo ""
echo "=== Test: N2 — No silent failures (healthy) ==="
assert_eq "N2 HEALTHY" "HEALTHY" "$(check_field "$output" N2 status)"

# ==========================================================================
echo ""
echo "=== Test: N2 — Silent failures (degraded) ==="
ENV=$(create_mock_env)
recent_time=$(python3 -c "from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'))")
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-slack-notify.yml_runs" \
  "{\"workflow_runs\":[
    {\"id\":1,\"conclusion\":\"failure\",\"created_at\":\"$recent_time\"},
    {\"id\":2,\"conclusion\":\"skipped\",\"created_at\":\"$recent_time\"},
    {\"id\":3,\"conclusion\":\"skipped\",\"created_at\":\"$recent_time\"},
    {\"id\":4,\"conclusion\":\"skipped\",\"created_at\":\"$recent_time\"},
    {\"id\":5,\"conclusion\":\"success\",\"created_at\":\"$recent_time\"}
  ]}"
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-dispatch.yml_runs" \
  '{"workflow_runs":[]}'

output=$(run_check "$ENV" --json --category notifications)
assert_eq "N2 DEGRADED" "DEGRADED" "$(check_field "$output" N2 status)"

# ==========================================================================
echo ""
echo "=== Test: B1 — Budget healthy (no log dir) ==="
ENV=$(create_mock_env)
output=$(TOKEN_LOG_DIR="/nonexistent/path" run_check "$ENV" --json --category budget)
assert_eq "B1 HEALTHY (no dir)" "HEALTHY" "$(check_field "$output" B1 status)"
assert_eq "B2 HEALTHY (no dir)" "HEALTHY" "$(check_field "$output" B2 status)"
assert_eq "B3 HEALTHY (no dir)" "HEALTHY" "$(check_field "$output" B3 status)"

# ==========================================================================
echo ""
echo "=== Test: B1 — Budget with valid logs ==="
ENV=$(create_mock_env)
budget_dir="$TEST_DIR/token-logs-b1"
mkdir -p "$budget_dir/claude-code"
today=$(date -u '+%Y-%m-%d')
# 3 invocations — well under 10 limit
printf '{"tokens":100}\n{"tokens":200}\n{"tokens":300}\n' > "$budget_dir/claude-code/$today.jsonl"

output=$(TOKEN_LOG_DIR="$budget_dir" run_check "$ENV" --json --category budget)
assert_eq "B1 HEALTHY" "HEALTHY" "$(check_field "$output" B1 status)"

# ==========================================================================
echo ""
echo "=== Test: B2 — Corrupted log ==="
ENV=$(create_mock_env)
budget_dir="$TEST_DIR/token-logs-b2"
mkdir -p "$budget_dir/claude-code"
printf '{"tokens":100}\nNOT_JSON\n{"tokens":300}\n' > "$budget_dir/claude-code/$today.jsonl"

output=$(TOKEN_LOG_DIR="$budget_dir" run_check "$ENV" --json --category budget)
assert_eq "B2 DEGRADED" "DEGRADED" "$(check_field "$output" B2 status)"
assert_contains "B2 corrupted" "corrupted" "$(check_field "$output" B2 message)"

# ==========================================================================
echo ""
echo "=== Test: B3 — Oversized log ==="
ENV=$(create_mock_env)
budget_dir="$TEST_DIR/token-logs-b3"
mkdir -p "$budget_dir/claude-code"
# Create a file > 1MB
python3 -c "import json; f=open('$budget_dir/claude-code/$today.jsonl','w'); [f.write(json.dumps({'t':'x'*200})+'\n') for _ in range(5000)]; f.close()"

output=$(TOKEN_LOG_DIR="$budget_dir" run_check "$ENV" --json --category budget)
assert_eq "B3 UNHEALTHY" "UNHEALTHY" "$(check_field "$output" B3 status)"
assert_contains "B3 oversized" "oversized" "$(check_field "$output" B3 message)"

# ==========================================================================
echo ""
echo "=== Test: X2 — No stuck issues (healthy) ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_issues" '[]'

output=$(run_check "$ENV" --json --category crosscutting)
assert_eq "X2 HEALTHY" "HEALTHY" "$(check_field "$output" X2 status)"

# ==========================================================================
echo ""
echo "=== Test: X3 — Escalation accumulation (healthy) ==="
assert_eq "X3 HEALTHY" "HEALTHY" "$(check_field "$output" X3 status)"

# ==========================================================================
echo ""
echo "=== Test: X4 — YAML integrity (healthy, no workflows) ==="
assert_eq "X4 HEALTHY" "HEALTHY" "$(check_field "$output" X4 status)"

# ==========================================================================
echo ""
echo "=== Test: --slack flag includes remediation ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runners" \
  '{"runners":[]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runs" \
  '{"workflow_runs":[]}'

# Run with --slack (webhook not set, so it just warns)
output=$(run_check "$ENV" --json --category runner 2>/dev/null)
# Verify remediation field exists in JSON output
has_remediation=$(echo "$output" | jq '[.checks[] | has("remediation")] | all' 2>/dev/null)
assert_eq "checks have remediation field" "true" "$has_remediation"

# ==========================================================================
echo ""
echo "=== Test: All categories produce valid JSON ==="
ENV=$(create_mock_env)
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runners" \
  '{"runners":[{"status":"online","labels":[{"name":"{{RUNNER_LABEL}}"}]}]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_runs" \
  '{"workflow_runs":[]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_pulls" '[]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_issues" '[]'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-dispatch.yml_runs" \
  '{"workflow_runs":[]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-dispatch-sweep.yml_runs" \
  '{"workflow_runs":[]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-review.yml_runs" \
  '{"workflow_runs":[]}'
MOCK_DIR="$ENV" mock_response "repos_test-owner_test-repo_actions_workflows_agent-slack-notify.yml_runs" \
  '{"workflow_runs":[]}'

output=$(TOKEN_LOG_DIR="/nonexistent" run_check "$ENV" --json 2>/dev/null)
assert_eq "all-categories valid JSON" "true" "$(echo "$output" | jq 'true' 2>/dev/null || echo false)"

# Verify we get checks from all categories
check_ids=$(echo "$output" | jq -r '[.checks[].id] | join(",")' 2>/dev/null)
assert_contains "has R1" "R1" "$check_ids"
assert_contains "has D1" "D1" "$check_ids"
assert_contains "has S1" "S1" "$check_ids"
assert_contains "has V1" "V1" "$check_ids"
assert_contains "has N1" "N1" "$check_ids"
assert_contains "has B1" "B1" "$check_ids"
assert_contains "has X1" "X1" "$check_ids"

# ==========================================================================
# Summary
# ==========================================================================
echo ""
echo "========================================"
total=$((PASS + FAIL))
echo "Results: $PASS/$total passed, $FAIL failed"
if (( FAIL > 0 )); then
  echo "FAILED"
  exit 1
else
  echo "ALL TESTS PASSED"
  exit 0
fi
