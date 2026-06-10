#!/usr/bin/env bash
# =============================================================================
# pipeline-health-check.sh — Automated pipeline health monitoring
# =============================================================================
# Checks Runner (R1-R3), Dispatch (D1-D5), and Sweep (S1-S4) health.
#
# Usage:
#   pipeline-health-check.sh [--json] [--slack] [--category <cat>[,<cat>...]]
#
# Options:
#   --json               Output JSON report (default: human-readable)
#   --slack              Post results to Slack #alerts channel
#   --category <cats>    Run only specified categories (comma-separated)
#                        Valid: runner, dispatch, sweep, review, notifications,
#                               budget, crosscutting
#
# Exit codes:
#   0 = HEALTHY, 1 = DEGRADED, 2 = UNHEALTHY, 3 = CRITICAL
#
# Requires:
#   gh CLI authenticated with repo + actions scope
#
# Spec: healthcheck/pipeline-health-criteria.md
# =============================================================================
set -uo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO="${GITHUB_REPOSITORY:-{{GITHUB_ORG}}/{{GITHUB_REPO}}}"
OUTPUT_JSON=false
POST_SLACK=false
CATEGORIES=()

STATUS_HEALTHY=0
STATUS_DEGRADED=1
STATUS_UNHEALTHY=2
STATUS_CRITICAL=3

RESULTS_FILE=$(mktemp)
trap 'rm -f "$RESULTS_FILE"' EXIT

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)
      OUTPUT_JSON=true
      shift
      ;;
    --slack)
      POST_SLACK=true
      shift
      ;;
    --category)
      IFS=',' read -ra CATEGORIES <<< "${2:?--category requires a value}"
      shift 2
      ;;
    -h|--help)
      sed -n '5,/^# =====/{ /^# =====/d; s/^# \?//; p }' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ ${#CATEGORIES[@]} -eq 0 ]]; then
  CATEGORIES=(runner dispatch sweep review notifications budget crosscutting)
fi

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
worst_status=$STATUS_HEALTHY

status_name() {
  case "$1" in
    0) echo "HEALTHY" ;;
    1) echo "DEGRADED" ;;
    2) echo "UNHEALTHY" ;;
    3) echo "CRITICAL" ;;
  esac
}

status_emoji() {
  case "$1" in
    0) echo "🟢" ;;
    1) echo "🟡" ;;
    2) echo "🟠" ;;
    3) echo "🔴" ;;
  esac
}

update_worst() {
  local s=$1
  if (( s > worst_status )); then
    worst_status=$s
  fi
}

record_check() {
  local id="$1" name="$2" status="$3" message="$4"
  local details remediation
  details="${5:-"{}"}"
  remediation="${6:-""}"
  update_worst "$status"
  jq -cn \
    --arg id "$id" \
    --arg name "$name" \
    --arg status "$(status_name "$status")" \
    --arg message "$message" \
    --argjson details "$details" \
    --arg remediation "$remediation" \
    '{id:$id, name:$name, status:$status, message:$message, details:$details, remediation:$remediation}' \
    >> "$RESULTS_FILE"
}

# Safe gh api wrapper — returns empty JSON on failure
gh_api() {
  local endpoint="$1"
  shift
  local result
  result=$(gh api "$endpoint" "$@" 2>/dev/null) || true
  if [[ -z "$result" ]]; then
    echo '{}'
  else
    echo "$result"
  fi
}

hours_ago() {
  python3 -c "
from datetime import datetime, timedelta, timezone
print((datetime.now(timezone.utc) - timedelta(hours=$1)).strftime('%Y-%m-%dT%H:%M:%SZ'))
"
}

minutes_since() {
  python3 -c "
from datetime import datetime, timezone
t = datetime.fromisoformat('$1'.replace('Z','+00:00'))
print(int((datetime.now(timezone.utc) - t).total_seconds() / 60))
" 2>/dev/null || echo "0"
}

# Safe jq wrapper — returns fallback on parse errors
safe_jq() {
  local fallback="$1"
  shift
  jq "$@" 2>/dev/null || echo "$fallback"
}

# ---------------------------------------------------------------------------
# Runner checks (R1–R3)
# ---------------------------------------------------------------------------
run_runner_checks() {
  # R1: Runner Online
  local runners_json online_count
  runners_json=$(gh_api "repos/$REPO/actions/runners")
  online_count=$(echo "$runners_json" | safe_jq "0" \
    '[.runners // [] | .[] | select(.status == "online" and (.labels[]?.name == "{{RUNNER_LABEL}}"))] | length')

  if (( online_count >= 1 )); then
    record_check "R1" "Runner Online" $STATUS_HEALTHY \
      "${online_count} runner(s) online with {{RUNNER_LABEL}} label" \
      "{\"online_count\": $online_count}"
  else
    record_check "R1" "Runner Online" $STATUS_CRITICAL \
      "No runners online with {{RUNNER_LABEL}} label" \
      "{\"online_count\": 0}"
  fi

  # R2: Runner Not Stuck
  local runs_json since
  since=$(hours_ago 3)
  runs_json=$(gh_api "repos/$REPO/actions/runs?status=in_progress&created=>$since&per_page=50")

  local has_stuck=false stuck_details="[]"
  while IFS= read -r run; do
    [[ -z "$run" || "$run" == "null" ]] && continue
    local run_start run_id run_mins
    run_start=$(echo "$run" | safe_jq "" -r '.created_at // empty')
    run_id=$(echo "$run" | safe_jq "0" -r '.id // 0')
    [[ -z "$run_start" ]] && continue
    run_mins=$(minutes_since "$run_start")
    if (( run_mins > 90 )); then
      has_stuck=true
      stuck_details=$(echo "$stuck_details" | jq \
        --arg id "$run_id" --arg mins "$run_mins" \
        '. + [{run_id: ($id | tonumber), minutes: ($mins | tonumber)}]' 2>/dev/null || echo "$stuck_details")
    fi
  done < <(echo "$runs_json" | safe_jq "" -c '.workflow_runs // [] | .[]')

  if $has_stuck; then
    record_check "R2" "Runner Not Stuck" $STATUS_UNHEALTHY \
      "Run(s) exceeding 90 minutes on self-hosted runner" \
      "{\"stuck_runs\": $stuck_details}"
  else
    record_check "R2" "Runner Not Stuck" $STATUS_HEALTHY \
      "No runs exceeding 90 minutes" \
      "{\"stuck_runs\": []}"
  fi

  # R3: Runner Disk Space (placeholder — requires runner-side access)
  record_check "R3" "Runner Disk Space" $STATUS_HEALTHY \
    "Requires runner-side monitoring — not checkable via API" \
    "{\"note\": \"requires runner-side monitoring\"}"
}

# ---------------------------------------------------------------------------
# Dispatch checks (D1–D5)
# ---------------------------------------------------------------------------
run_dispatch_checks() {
  local since runs_json success_count

  # D1: Recent Dispatch Success
  since=$(hours_ago 4)
  runs_json=$(gh_api "repos/$REPO/actions/workflows/agent-dispatch.yml/runs?created=>$since&per_page=20")
  success_count=$(echo "$runs_json" | safe_jq "0" \
    '[.workflow_runs // [] | .[] | select(.conclusion == "success")] | length')

  if (( success_count >= 1 )); then
    record_check "D1" "Recent Dispatch Success" $STATUS_HEALTHY \
      "${success_count} successful dispatch(es) in last 4 hours" \
      "{\"success_count\": $success_count}"
  else
    local ready_issues ready_count
    ready_issues=$(gh_api "repos/$REPO/issues?labels=status:ready,agent:claude-code&state=open&per_page=1")
    ready_count=$(echo "$ready_issues" | safe_jq "0" 'if type == "array" then length else 0 end')

    if (( ready_count == 0 )); then
      ready_issues=$(gh_api "repos/$REPO/issues?labels=status:ready,agent:codex-cli&state=open&per_page=1")
      ready_count=$(echo "$ready_issues" | safe_jq "0" 'if type == "array" then length else 0 end')
    fi

    if (( ready_count == 0 )); then
      record_check "D1" "Recent Dispatch Success" $STATUS_HEALTHY \
        "No dispatches needed — 0 ready issues with agent labels" \
        "{\"success_count\": 0, \"ready_issues\": 0}"
    else
      local since_8h runs_8h success_8h
      since_8h=$(hours_ago 8)
      runs_8h=$(gh_api "repos/$REPO/actions/workflows/agent-dispatch.yml/runs?created=>$since_8h&per_page=20")
      success_8h=$(echo "$runs_8h" | safe_jq "0" \
        '[.workflow_runs // [] | .[] | select(.conclusion == "success")] | length')

      if (( success_8h == 0 )); then
        record_check "D1" "Recent Dispatch Success" $STATUS_UNHEALTHY \
          "No successful dispatch in 8+ hours with ${ready_count} ready issue(s)" \
          "{\"success_count\": 0, \"ready_issues\": $ready_count, \"hours_checked\": 8}"
      else
        record_check "D1" "Recent Dispatch Success" $STATUS_DEGRADED \
          "No successful dispatch in last 4 hours with ${ready_count} ready issue(s)" \
          "{\"success_count\": 0, \"ready_issues\": $ready_count, \"hours_checked\": 4}"
      fi
    fi
  fi

  # D2: No Dispatch Step Skips After Budget
  local recent_runs
  recent_runs=$(gh_api "repos/$REPO/actions/workflows/agent-dispatch.yml/runs?per_page=5")
  local d2_status=$STATUS_HEALTHY d2_message="All post-budget steps executed in recent runs"
  local d2_details='{"checked_runs": 0, "skipped_runs": []}'
  local checked=0

  while IFS= read -r run_id; do
    [[ -z "$run_id" || "$run_id" == "null" ]] && continue
    local jobs_json budget_ok
    jobs_json=$(gh_api "repos/$REPO/actions/runs/$run_id/jobs")

    budget_ok=$(echo "$jobs_json" | safe_jq "" -r \
      '.jobs // [] | .[0].steps // [] | .[] |
      select(.name | test("budget"; "i")) |
      .conclusion // "unknown"' | head -1)

    if [[ "$budget_ok" == "success" ]]; then
      checked=$((checked + 1))
      local skipped_steps
      skipped_steps=$(echo "$jobs_json" | safe_jq "" -r \
        '[.jobs // [] | .[0].steps // [] | .[] |
         select(.name | test("deps|worktree|prompt|agent"; "i")) |
         select(.conclusion == "skipped") |
         .name] | join(", ")')

      if [[ -n "$skipped_steps" ]]; then
        d2_status=$STATUS_CRITICAL
        d2_message="Steps skipped after budget approval in run $run_id: $skipped_steps"
        d2_details=$(jq -cn --arg id "$run_id" --arg steps "$skipped_steps" \
          '{checked_runs: 1, skipped_runs: [{run_id: ($id | tonumber), skipped_steps: $steps}]}')
        break
      fi
    fi
  done < <(echo "$recent_runs" | safe_jq "" -r '.workflow_runs // [] | .[].id')

  d2_details=$(echo "$d2_details" | jq --argjson n "$checked" '.checked_runs = $n' 2>/dev/null || echo "$d2_details")
  record_check "D2" "No Dispatch Step Skips After Budget" $d2_status "$d2_message" "$d2_details"

  # D3: Agent Produces Changes
  local completed_runs
  completed_runs=$(gh_api "repos/$REPO/actions/workflows/agent-dispatch.yml/runs?status=completed&per_page=10")

  local no_change_streak=0 max_streak=0 total_checked=0
  while IFS= read -r run_id; do
    [[ -z "$run_id" || "$run_id" == "null" ]] && continue
    local jobs_json commit_step
    jobs_json=$(gh_api "repos/$REPO/actions/runs/$run_id/jobs")

    commit_step=$(echo "$jobs_json" | safe_jq "" -r \
      '.jobs // [] | .[0].steps // [] | .[] |
      select(.name | test("[Cc]ommit|push.*agent|agent.*work"; "")) |
      .conclusion // "unknown"' | head -1)

    if [[ -n "$commit_step" ]]; then
      total_checked=$((total_checked + 1))
      if [[ "$commit_step" == "success" ]]; then
        no_change_streak=0
      else
        no_change_streak=$((no_change_streak + 1))
        if (( no_change_streak > max_streak )); then
          max_streak=$no_change_streak
        fi
      fi
    fi
  done < <(echo "$completed_runs" | safe_jq "" -r '.workflow_runs // [] | .[].id')

  if (( max_streak >= 3 )); then
    record_check "D3" "Agent Produces Changes" $STATUS_UNHEALTHY \
      "${max_streak} consecutive no-change dispatches detected" \
      "{\"consecutive_no_changes\": $max_streak, \"runs_checked\": $total_checked}"
  elif (( max_streak >= 1 )); then
    record_check "D3" "Agent Produces Changes" $STATUS_DEGRADED \
      "${max_streak} consecutive no-change dispatch(es)" \
      "{\"consecutive_no_changes\": $max_streak, \"runs_checked\": $total_checked}"
  else
    record_check "D3" "Agent Produces Changes" $STATUS_HEALTHY \
      "Agents producing changes in recent dispatches" \
      "{\"consecutive_no_changes\": 0, \"runs_checked\": $total_checked}"
  fi

  # D4: PR Created After Agent Work
  local d4_status=$STATUS_HEALTHY d4_message="All agent changes have corresponding PRs"
  local d4_details='{"missing_prs": []}'

  while IFS= read -r run_line; do
    [[ -z "$run_line" || "$run_line" == "null" ]] && continue
    local run_id head_branch
    run_id=$(echo "$run_line" | safe_jq "" -r '.id')
    head_branch=$(echo "$run_line" | safe_jq "" -r '.head_branch // empty')
    [[ -z "$head_branch" ]] && continue

    local jobs_json commit_ok
    jobs_json=$(gh_api "repos/$REPO/actions/runs/$run_id/jobs")
    commit_ok=$(echo "$jobs_json" | safe_jq "" -r \
      '.jobs // [] | .[0].steps // [] | .[] |
      select(.name | test("[Cc]ommit|push.*agent|agent.*work"; "")) |
      select(.conclusion == "success") |
      .name' | head -1)

    if [[ -n "$commit_ok" ]]; then
      local pr_count
      pr_count=$(gh_api "repos/$REPO/pulls?head=${REPO%%/*}:$head_branch&state=all&per_page=1" |
        safe_jq "0" 'if type == "array" then length else 0 end')

      if (( pr_count == 0 )); then
        d4_status=$STATUS_UNHEALTHY
        d4_message="Changes committed but no PR for branch $head_branch"
        d4_details=$(echo "$d4_details" | jq --arg b "$head_branch" --arg id "$run_id" \
          '.missing_prs += [{branch: $b, run_id: ($id | tonumber)}]' 2>/dev/null || echo "$d4_details")
      fi
    fi
  done < <(echo "$completed_runs" | safe_jq "" -c '.workflow_runs // [] | .[:5] | .[]')

  record_check "D4" "PR Created After Agent Work" $d4_status "$d4_message" "$d4_details"

  # D5: Dependency Check Not Self-Blocking (static YAML check)
  local workflow_file=".github/workflows/agent-dispatch.yml"
  local d5_status=$STATUS_HEALTHY d5_message="No self-referencing step conditions found"
  local d5_details='{}'

  if [[ -f "$workflow_file" ]]; then
    local self_refs
    self_refs=$(python3 << 'PYEOF' 2>/dev/null || true
import yaml, sys

try:
    with open(".github/workflows/agent-dispatch.yml") as f:
        wf = yaml.safe_load(f)
except Exception:
    sys.exit(0)

issues = []
for job_name, job in (wf.get("jobs") or {}).items():
    steps = job.get("steps") or []
    for step in steps:
        step_id = step.get("id", "")
        condition = str(step.get("if", ""))
        if step_id and f"steps.{step_id}." in condition:
            issues.append(f"{job_name}/{step_id}: references own outputs in if condition")

for i in issues:
    print(i)
PYEOF
)

    if [[ -n "$self_refs" ]]; then
      d5_status=$STATUS_CRITICAL
      d5_message="Self-referencing step condition detected: $self_refs"
      d5_details=$(jq -cn --arg refs "$self_refs" '{self_references: $refs}')
    fi
  else
    d5_message="Workflow file not found — skipped"
    d5_details='{"note": "agent-dispatch.yml not found"}'
  fi

  record_check "D5" "Dependency Check Not Self-Blocking" $d5_status "$d5_message" "$d5_details"
}

# ---------------------------------------------------------------------------
# Sweep checks (S1–S4)
# ---------------------------------------------------------------------------
run_sweep_checks() {
  # S1: Sweep Running on Schedule
  local since runs_json run_count active_count
  since=$(hours_ago 2)
  runs_json=$(gh_api "repos/$REPO/actions/workflows/agent-dispatch-sweep.yml/runs?created=>$since&per_page=5")
  run_count=$(echo "$runs_json" | safe_jq "0" \
    '[.workflow_runs // [] | .[] | select(.conclusion == "success" or .status == "completed")] | length')
  active_count=$(echo "$runs_json" | safe_jq "0" \
    '[.workflow_runs // [] | .[] | select(.status == "in_progress")] | length')

  if (( run_count >= 1 || active_count >= 1 )); then
    record_check "S1" "Sweep Running on Schedule" $STATUS_HEALTHY \
      "Sweep ran in last 2 hours (${run_count} completed, ${active_count} active)" \
      "{\"completed\": $run_count, \"active\": $active_count}"
  else
    record_check "S1" "Sweep Running on Schedule" $STATUS_DEGRADED \
      "No sweep runs in last 2 hours" \
      "{\"completed\": 0, \"active\": 0}"
  fi

  # S2: No Accumulating Backlog
  local ready_cc ready_codex cc_count codex_count ready_count
  ready_cc=$(gh_api "repos/$REPO/issues?labels=status:ready,agent:claude-code&state=open&per_page=100")
  ready_codex=$(gh_api "repos/$REPO/issues?labels=status:ready,agent:codex-cli&state=open&per_page=100")
  cc_count=$(echo "$ready_cc" | safe_jq "0" 'if type == "array" then length else 0 end')
  codex_count=$(echo "$ready_codex" | safe_jq "0" 'if type == "array" then length else 0 end')
  ready_count=$((cc_count + codex_count))

  if (( ready_count <= 6 )); then
    record_check "S2" "No Accumulating Backlog" $STATUS_HEALTHY \
      "${ready_count} ready issue(s) — normal pipeline flow" \
      "{\"ready_count\": $ready_count}"
  elif (( ready_count <= 12 )); then
    record_check "S2" "No Accumulating Backlog" $STATUS_DEGRADED \
      "${ready_count} ready issues — mild backlog" \
      "{\"ready_count\": $ready_count}"
  else
    record_check "S2" "No Accumulating Backlog" $STATUS_UNHEALTHY \
      "${ready_count} ready issues — sweep not keeping up" \
      "{\"ready_count\": $ready_count}"
  fi

  # S3: No Stale In-Progress Issues
  local in_progress_cc in_progress_codex
  in_progress_cc=$(gh_api "repos/$REPO/issues?labels=status:in-progress,agent:claude-code&state=open&per_page=100")
  in_progress_codex=$(gh_api "repos/$REPO/issues?labels=status:in-progress,agent:codex-cli&state=open&per_page=100")

  local stale_issues=0 stale_details="[]"
  local issues_json
  for issues_json in "$in_progress_cc" "$in_progress_codex"; do
    while IFS= read -r issue; do
      [[ -z "$issue" || "$issue" == "null" ]] && continue
      local issue_num updated_at mins
      issue_num=$(echo "$issue" | safe_jq "0" -r '.number')
      updated_at=$(echo "$issue" | safe_jq "" -r '.updated_at // empty')
      [[ -z "$updated_at" ]] && continue

      mins=$(minutes_since "$updated_at")
      if (( mins > 120 )); then
        local pr_count
        pr_count=$(gh_api "repos/$REPO/pulls?state=open&per_page=100" |
          safe_jq "0" --argjson num "$issue_num" \
          '[.[]? | select(.title | test("#" + ($num | tostring); ""))] | length')

        if (( pr_count == 0 )); then
          stale_issues=$((stale_issues + 1))
          stale_details=$(echo "$stale_details" | jq \
            --argjson num "$issue_num" --argjson mins "$mins" \
            '. + [{issue_number: $num, minutes_stale: $mins}]' 2>/dev/null || echo "$stale_details")
        fi
      fi
    done < <(echo "$issues_json" | safe_jq "" -c '.[]?')
  done

  if (( stale_issues == 0 )); then
    record_check "S3" "No Stale In-Progress Issues" $STATUS_HEALTHY \
      "No stale in-progress issues" \
      "{\"stale_count\": 0}"
  else
    record_check "S3" "No Stale In-Progress Issues" $STATUS_UNHEALTHY \
      "${stale_issues} in-progress issue(s) stale > 2 hours with no open PR" \
      "{\"stale_count\": $stale_issues, \"stale_issues\": $stale_details}"
  fi

  # S4: Sweep Not Continuously Cancelled
  local last3_runs completed_count cancelled_count total_last3
  last3_runs=$(gh_api "repos/$REPO/actions/workflows/agent-dispatch-sweep.yml/runs?per_page=3")
  completed_count=$(echo "$last3_runs" | safe_jq "0" \
    '[.workflow_runs // [] | .[] | select(.conclusion != "cancelled")] | length')
  cancelled_count=$(echo "$last3_runs" | safe_jq "0" \
    '[.workflow_runs // [] | .[] | select(.conclusion == "cancelled")] | length')
  total_last3=$(echo "$last3_runs" | safe_jq "0" \
    '.workflow_runs // [] | length')

  if (( completed_count >= 1 )); then
    record_check "S4" "Sweep Not Continuously Cancelled" $STATUS_HEALTHY \
      "${completed_count} of last ${total_last3} sweep runs completed" \
      "{\"completed\": $completed_count, \"cancelled\": $cancelled_count}"
  else
    record_check "S4" "Sweep Not Continuously Cancelled" $STATUS_DEGRADED \
      "All last ${total_last3} sweep runs were cancelled" \
      "{\"completed\": 0, \"cancelled\": $cancelled_count}"
  fi
}

# ---------------------------------------------------------------------------
# Review checks (V1–V5)
# ---------------------------------------------------------------------------
run_review_checks() {
  # V1: PRs Get Reviewed Within SLA
  local prs_json threshold
  prs_json=$(gh_api "repos/$REPO/pulls?state=open&per_page=100")
  threshold=$(hours_ago 2)

  local overdue_count=0 overdue_details="[]"
  while IFS= read -r pr; do
    [[ -z "$pr" || "$pr" == "null" ]] && continue
    local pr_num pr_branch created_at
    pr_branch=$(echo "$pr" | safe_jq "" -r '.head.ref // ""')
    [[ "$pr_branch" != agent/* ]] && continue

    pr_num=$(echo "$pr" | safe_jq "0" -r '.number')
    created_at=$(echo "$pr" | safe_jq "" -r '.created_at // empty')
    [[ -z "$created_at" ]] && continue

    local age_mins
    age_mins=$(minutes_since "$created_at")
    (( age_mins <= 120 )) && continue

    # Check for review comments
    local comments has_review
    comments=$(gh_api "repos/$REPO/issues/$pr_num/comments?per_page=50")
    has_review=$(echo "$comments" | safe_jq "false" \
      '[.[]? | select(.user.login == "github-actions[bot]" or .user.login == "github-actions") |
       select(.body[:200] | ascii_downcase | contains("review"))] | length > 0')

    if [[ "$has_review" != "true" ]]; then
      overdue_count=$((overdue_count + 1))
      overdue_details=$(echo "$overdue_details" | jq \
        --argjson num "$pr_num" --argjson mins "$age_mins" \
        '. + [{pr_number: $num, age_minutes: $mins}]' 2>/dev/null || echo "$overdue_details")
    fi
  done < <(echo "$prs_json" | safe_jq "" -c '.[]?')

  if (( overdue_count == 0 )); then
    record_check "V1" "PRs Reviewed Within SLA" $STATUS_HEALTHY \
      "All open agent PRs reviewed within 2-hour SLA"
  else
    record_check "V1" "PRs Reviewed Within SLA" $STATUS_UNHEALTHY \
      "${overdue_count} PR(s) unreviewed past 2-hour SLA" \
      "{\"overdue_count\": $overdue_count, \"overdue_prs\": $overdue_details}" \
      "Trigger review: gh workflow run agent-review.yml -f pr_number=<N>"
  fi

  # V2: Review Workflow Not Failing
  local review_runs failures failure_count total_recent
  review_runs=$(gh_api "repos/$REPO/actions/workflows/agent-review.yml/runs?per_page=5")
  total_recent=$(echo "$review_runs" | safe_jq "0" '.workflow_runs // [] | length')

  if (( total_recent == 0 )); then
    record_check "V2" "Review Workflow Not Failing" $STATUS_HEALTHY \
      "No review runs to analyze"
  else
    failure_count=$(echo "$review_runs" | safe_jq "0" \
      '[.workflow_runs // [] | .[:3] | .[] | select(.conclusion == "failure")] | length')
    if (( failure_count <= 1 )); then
      record_check "V2" "Review Workflow Not Failing" $STATUS_HEALTHY \
        "${failure_count} of last 3 review runs failed (threshold: ≤1)"
    else
      record_check "V2" "Review Workflow Not Failing" $STATUS_UNHEALTHY \
        "${failure_count} of last 3 review runs failed" \
        "{\"failure_count\": $failure_count}" \
        "Check review workflow logs — token logging, Claude CLI, or spec resolution."
    fi
  fi

  # V3: Reviews Produce Verdicts
  local completed_reviews success_count completed_count
  completed_reviews=$(echo "$review_runs" | safe_jq "" -c \
    '[.workflow_runs // [] | .[:3] | .[] | select(.conclusion == "success" or .conclusion == "failure")]')
  completed_count=$(echo "$completed_reviews" | safe_jq "0" 'length')
  success_count=$(echo "$completed_reviews" | safe_jq "0" \
    '[.[] | select(.conclusion == "success")] | length')

  if (( completed_count == 0 )); then
    record_check "V3" "Reviews Produce Verdicts" $STATUS_HEALTHY \
      "No completed review runs to analyze"
  elif (( success_count > 0 )); then
    record_check "V3" "Reviews Produce Verdicts" $STATUS_HEALTHY \
      "${success_count}/${completed_count} review runs completed successfully"
  else
    record_check "V3" "Reviews Produce Verdicts" $STATUS_DEGRADED \
      "0/${completed_count} review runs succeeded — verdicts may be missing" \
      "{\"completed\": $completed_count, \"successes\": 0}" \
      "Check review prompt and Claude output format. Verdict regex may need updating."
  fi

  # V4: Approved PRs Get Merged
  local v4_stuck=0 v4_details="[]"
  local merge_threshold
  merge_threshold=$(hours_ago 1)

  while IFS= read -r pr; do
    [[ -z "$pr" || "$pr" == "null" ]] && continue
    local pr_num pr_branch
    pr_branch=$(echo "$pr" | safe_jq "" -r '.head.ref // ""')
    [[ "$pr_branch" != agent/* ]] && continue

    pr_num=$(echo "$pr" | safe_jq "0" -r '.number')
    local comments
    comments=$(gh_api "repos/$REPO/issues/$pr_num/comments?per_page=50")

    local approved_at
    approved_at=$(echo "$comments" | safe_jq "" -r \
      '[.[]? | select(
        (.user.login == "github-actions[bot]" or .user.login == "github-actions") and
        (.body[:500] | ascii_downcase | contains("approve"))
       ) | .created_at] | first // empty')

    if [[ -n "$approved_at" ]]; then
      local approve_mins
      approve_mins=$(minutes_since "$approved_at")
      if (( approve_mins > 60 )); then
        v4_stuck=$((v4_stuck + 1))
        v4_details=$(echo "$v4_details" | jq \
          --argjson num "$pr_num" --arg at "$approved_at" \
          '. + [{pr_number: $num, approved_at: $at}]' 2>/dev/null || echo "$v4_details")
      fi
    fi
  done < <(echo "$prs_json" | safe_jq "" -c '.[]?')

  if (( v4_stuck == 0 )); then
    record_check "V4" "Approved PRs Merged" $STATUS_HEALTHY \
      "No approved PRs stuck unmerged"
  else
    record_check "V4" "Approved PRs Merged" $STATUS_UNHEALTHY \
      "${v4_stuck} approved PR(s) unmerged >1 hour" \
      "{\"stuck_count\": $v4_stuck, \"stuck_prs\": $v4_details}" \
      "Check auto-merge step. May need PROJECT_PAT or branch protection fix."
  fi

  # V5: Request-Changes PRs Get Re-dispatched
  local ready_issues v5_stuck=0 v5_details="[]"
  ready_issues=$(gh_api "repos/$REPO/issues?labels=status:ready&state=open&per_page=100")
  local redispatch_threshold
  redispatch_threshold=$(hours_ago 2)

  while IFS= read -r issue; do
    [[ -z "$issue" || "$issue" == "null" ]] && continue
    local has_agent updated_at
    has_agent=$(echo "$issue" | safe_jq "false" \
      '[.labels[]?.name | select(startswith("agent:"))] | length > 0')
    [[ "$has_agent" != "true" ]] && continue

    updated_at=$(echo "$issue" | safe_jq "" -r '.updated_at // empty')
    [[ -z "$updated_at" ]] && continue

    local update_mins
    update_mins=$(minutes_since "$updated_at")
    if (( update_mins > 120 )); then
      local issue_num
      issue_num=$(echo "$issue" | safe_jq "0" -r '.number')
      v5_stuck=$((v5_stuck + 1))
      v5_details=$(echo "$v5_details" | jq \
        --argjson num "$issue_num" --argjson mins "$update_mins" \
        '. + [{issue_number: $num, minutes_waiting: $mins}]' 2>/dev/null || echo "$v5_details")
    fi
  done < <(echo "$ready_issues" | safe_jq "" -c '.[]?')

  if (( v5_stuck == 0 )); then
    record_check "V5" "Rejected PRs Re-dispatched" $STATUS_HEALTHY \
      "No ready issues stuck >2 hours after review"
  else
    record_check "V5" "Rejected PRs Re-dispatched" $STATUS_DEGRADED \
      "${v5_stuck} ready issue(s) waiting >2 hours for re-dispatch" \
      "{\"stuck_count\": $v5_stuck, \"stuck_issues\": $v5_details}" \
      "Check sweep — should pick up ready issues with agent labels."
  fi
}

# ---------------------------------------------------------------------------
# Notification checks (N1–N2)
# ---------------------------------------------------------------------------
run_notification_checks() {
  # N1: Slack Notifications Firing
  local notify_runs since_24h recent_runs success_count
  since_24h=$(hours_ago 24)
  notify_runs=$(gh_api "repos/$REPO/actions/workflows/agent-slack-notify.yml/runs?per_page=20")

  success_count=0
  local recent_count=0
  while IFS= read -r run; do
    [[ -z "$run" || "$run" == "null" ]] && continue
    local run_created
    run_created=$(echo "$run" | safe_jq "" -r '.created_at // empty')
    [[ -z "$run_created" ]] && continue
    local run_mins
    run_mins=$(minutes_since "$run_created")
    if (( run_mins <= 1440 )); then  # 24 hours
      recent_count=$((recent_count + 1))
      local conclusion
      conclusion=$(echo "$run" | safe_jq "" -r '.conclusion // ""')
      [[ "$conclusion" == "success" ]] && success_count=$((success_count + 1))
    fi
  done < <(echo "$notify_runs" | safe_jq "" -c '.workflow_runs // [] | .[]')

  if (( success_count >= 1 )); then
    record_check "N1" "Slack Notifications Firing" $STATUS_HEALTHY \
      "${success_count} notification(s) sent in last 24h"
  else
    # Check if there was pipeline activity
    local dispatch_runs dispatch_recent
    dispatch_runs=$(gh_api "repos/$REPO/actions/workflows/agent-dispatch.yml/runs?per_page=5")
    dispatch_recent=0
    while IFS= read -r run; do
      [[ -z "$run" || "$run" == "null" ]] && continue
      local run_created run_mins
      run_created=$(echo "$run" | safe_jq "" -r '.created_at // empty')
      [[ -z "$run_created" ]] && continue
      run_mins=$(minutes_since "$run_created")
      (( run_mins <= 1440 )) && dispatch_recent=$((dispatch_recent + 1))
    done < <(echo "$dispatch_runs" | safe_jq "" -c '.workflow_runs // [] | .[]')

    if (( dispatch_recent == 0 )); then
      record_check "N1" "Slack Notifications Firing" $STATUS_HEALTHY \
        "No pipeline activity in 24h — no notifications expected"
    else
      record_check "N1" "Slack Notifications Firing" $STATUS_DEGRADED \
        "Pipeline active but no notifications fired in 24h" \
        "{\"dispatch_activity\": $dispatch_recent, \"notification_successes\": 0}" \
        "Check Slack webhook URL, workflow triggers, and event types."
    fi
  fi

  # N2: No Silent Notification Failures
  local last5 skipped_count failed_count total_last5
  last5=$(echo "$notify_runs" | safe_jq "" -c '[.workflow_runs // [] | .[:5] | .[]]')
  total_last5=$(echo "$last5" | safe_jq "0" 'length')
  skipped_count=$(echo "$last5" | safe_jq "0" '[.[] | select(.conclusion == "skipped")] | length')
  failed_count=$(echo "$last5" | safe_jq "0" '[.[] | select(.conclusion == "failure")] | length')

  if (( total_last5 == 0 )); then
    record_check "N2" "No Silent Notification Failures" $STATUS_HEALTHY \
      "No notification runs to analyze"
  elif (( failed_count == 0 && skipped_count <= 2 )); then
    record_check "N2" "No Silent Notification Failures" $STATUS_HEALTHY \
      "Last ${total_last5} runs: ${skipped_count} skipped, 0 failures"
  else
    local issues=""
    (( failed_count > 0 )) && issues="${failed_count} failures"
    if (( skipped_count > 2 )); then
      [[ -n "$issues" ]] && issues+=", "
      issues+="${skipped_count} skipped"
    fi
    record_check "N2" "No Silent Notification Failures" $STATUS_DEGRADED \
      "Last ${total_last5} notification runs: ${issues}" \
      "{\"failed\": $failed_count, \"skipped\": $skipped_count}" \
      "Check skip conditions and Slack API errors."
  fi
}

# ---------------------------------------------------------------------------
# Budget checks (B1–B3)
# ---------------------------------------------------------------------------
TOKEN_LOG_DIR="${TOKEN_LOG_DIR:-/home/{{RUNNER_USER}}/kite-token-logs}"

run_budget_checks() {
  # B1: Daily Budget Not Exhausted
  local today
  today=$(date -u '+%Y-%m-%d')
  local warnings="" exhausted=""
  local b1_details='{}'

  if [[ ! -d "$TOKEN_LOG_DIR" ]]; then
    record_check "B1" "Daily Budget Not Exhausted" $STATUS_HEALTHY \
      "Token log directory not found — budget tracking may not be active" \
      "{\"note\": \"$TOKEN_LOG_DIR not found\"}"
  else
    local has_issues=false
    local agents_checked=0

    for agent_dir in "$TOKEN_LOG_DIR"/*/; do
      [[ ! -d "$agent_dir" ]] && continue
      local agent_name
      agent_name=$(basename "$agent_dir")
      [[ "$agent_name" == "summaries" ]] && continue

      local log_file="$agent_dir/${today}.jsonl"
      [[ ! -f "$log_file" ]] && continue

      agents_checked=$((agents_checked + 1))
      local invocations limit pct
      invocations=$(wc -l < "$log_file" 2>/dev/null || echo 0)
      invocations=$((invocations + 0))  # trim whitespace

      # Default limits per agent
      case "$agent_name" in
        claude-code)       limit=10 ;;
        codex-cli)         limit=10 ;;
        review-agent)      limit=15 ;;
        planning-agent)    limit=5 ;;
        validation-agent)  limit=5 ;;
        *)                 limit=10 ;;
      esac

      if (( limit > 0 )); then
        pct=$(( invocations * 100 / limit ))
      else
        pct=0
      fi

      if (( pct >= 100 )); then
        has_issues=true
        exhausted+="${agent_name}: ${invocations}/${limit}; "
      elif (( pct >= 80 )); then
        has_issues=true
        warnings+="${agent_name}: ${invocations}/${limit}; "
      fi
    done

    if [[ -n "$exhausted" ]]; then
      record_check "B1" "Daily Budget Not Exhausted" $STATUS_UNHEALTHY \
        "Budget exhausted: ${exhausted%%; }" \
        "{\"exhausted\": \"${exhausted%%; }\"}" \
        "Wait for UTC midnight reset, or increase daily limit."
    elif [[ -n "$warnings" ]]; then
      record_check "B1" "Daily Budget Not Exhausted" $STATUS_DEGRADED \
        "Budget warning (>80%): ${warnings%%; }" \
        "{\"warnings\": \"${warnings%%; }\"}"
    else
      record_check "B1" "Daily Budget Not Exhausted" $STATUS_HEALTHY \
        "All agents within daily limits (<80%)" \
        "{\"agents_checked\": $agents_checked}"
    fi
  fi

  # B2: Token Logs Not Corrupted
  if [[ ! -d "$TOKEN_LOG_DIR" ]]; then
    record_check "B2" "Token Logs Not Corrupted" $STATUS_HEALTHY \
      "Token log directory not found — skipped"
  else
    local corrupted="" corrupt_count=0

    for agent_dir in "$TOKEN_LOG_DIR"/*/; do
      [[ ! -d "$agent_dir" ]] && continue
      local agent_name
      agent_name=$(basename "$agent_dir")
      [[ "$agent_name" == "summaries" ]] && continue

      for log_file in "$agent_dir"/*.jsonl; do
        [[ ! -f "$log_file" ]] && continue
        local line_num=0
        while IFS= read -r line; do
          line_num=$((line_num + 1))
          [[ -z "$line" ]] && continue
          if ! echo "$line" | jq empty 2>/dev/null; then
            corrupt_count=$((corrupt_count + 1))
            corrupted+="${agent_name}/$(basename "$log_file"):${line_num}; "
            break  # One error per file is enough
          fi
        done < "$log_file"
      done
    done

    if (( corrupt_count == 0 )); then
      record_check "B2" "Token Logs Not Corrupted" $STATUS_HEALTHY \
        "All token log files are valid JSONL"
    else
      record_check "B2" "Token Logs Not Corrupted" $STATUS_DEGRADED \
        "${corrupt_count} corrupted log file(s): ${corrupted%%; }" \
        "{\"corrupt_count\": $corrupt_count}" \
        "Clean corrupted lines. Check which workflow writes bad data."
    fi
  fi

  # B3: Token Logs Not Oversized
  if [[ ! -d "$TOKEN_LOG_DIR" ]]; then
    record_check "B3" "Token Logs Not Oversized" $STATUS_HEALTHY \
      "Token log directory not found — skipped"
  else
    local oversized="" oversized_count=0

    for agent_dir in "$TOKEN_LOG_DIR"/*/; do
      [[ ! -d "$agent_dir" ]] && continue
      local agent_name
      agent_name=$(basename "$agent_dir")
      [[ "$agent_name" == "summaries" ]] && continue

      for log_file in "$agent_dir"/*.jsonl; do
        [[ ! -f "$log_file" ]] && continue
        local file_size
        file_size=$(stat -c%s "$log_file" 2>/dev/null || stat -f%z "$log_file" 2>/dev/null || echo 0)
        if (( file_size > 1000000 )); then
          oversized_count=$((oversized_count + 1))
          local size_mb
          size_mb=$(python3 -c "print(f'{$file_size / 1000000:.1f}')" 2>/dev/null || echo "?")
          oversized+="${agent_name}/$(basename "$log_file") (${size_mb}MB); "
        fi
      done
    done

    if (( oversized_count == 0 )); then
      record_check "B3" "Token Logs Not Oversized" $STATUS_HEALTHY \
        "All token log files under 1MB"
    else
      record_check "B3" "Token Logs Not Oversized" $STATUS_UNHEALTHY \
        "${oversized_count} oversized log file(s): ${oversized%%; }" \
        "{\"oversized_count\": $oversized_count}" \
        "Archive or truncate old log files."
    fi
  fi
}

# ---------------------------------------------------------------------------
# Cross-cutting checks (X1–X4)
# ---------------------------------------------------------------------------
run_crosscutting_checks() {
  # X1: Issue-to-Merge Cycle Time
  local closed_issues
  closed_issues=$(gh_api "repos/$REPO/issues?state=closed&labels=status:done&per_page=20&sort=updated&direction=desc")
  local issue_count
  issue_count=$(echo "$closed_issues" | safe_jq "0" 'if type == "array" then length else 0 end')

  if (( issue_count == 0 )); then
    record_check "X1" "Issue-to-Merge Cycle Time" $STATUS_HEALTHY \
      "No recently closed issues to measure cycle time"
  else
    # Compute cycle times from created_at to closed_at for recent issues
    local cycle_times=()
    while IFS= read -r issue; do
      [[ -z "$issue" || "$issue" == "null" ]] && continue
      local created closed
      created=$(echo "$issue" | safe_jq "" -r '.created_at // empty')
      closed=$(echo "$issue" | safe_jq "" -r '.closed_at // empty')
      [[ -z "$created" || -z "$closed" ]] && continue

      local cycle_mins
      cycle_mins=$(python3 -c "
from datetime import datetime
c = datetime.fromisoformat('$created'.replace('Z','+00:00'))
d = datetime.fromisoformat('$closed'.replace('Z','+00:00'))
print(int((d - c).total_seconds() / 60))
" 2>/dev/null || echo "")
      [[ -n "$cycle_mins" && "$cycle_mins" -gt 0 ]] && cycle_times+=("$cycle_mins")
    done < <(echo "$closed_issues" | safe_jq "" -c '.[]?')

    if (( ${#cycle_times[@]} == 0 )); then
      record_check "X1" "Issue-to-Merge Cycle Time" $STATUS_HEALTHY \
        "No cycle time data available"
    else
      # Calculate median
      local median_mins
      median_mins=$(printf '%s\n' "${cycle_times[@]}" | sort -n | awk '{a[NR]=$1} END{print a[int((NR+1)/2)]}')
      local median_hours
      median_hours=$(python3 -c "print(f'{$median_mins / 60:.1f}')" 2>/dev/null || echo "?")

      if (( median_mins < 240 )); then  # < 4 hours
        record_check "X1" "Issue-to-Merge Cycle Time" $STATUS_HEALTHY \
          "Median cycle time: ${median_hours}h (${#cycle_times[@]} issues)" \
          "{\"median_hours\": $median_hours, \"sample_size\": ${#cycle_times[@]}}"
      elif (( median_mins < 480 )); then  # 4-8 hours
        record_check "X1" "Issue-to-Merge Cycle Time" $STATUS_DEGRADED \
          "Median cycle time: ${median_hours}h — above 4h target" \
          "{\"median_hours\": $median_hours, \"sample_size\": ${#cycle_times[@]}}" \
          "Identify bottleneck: dispatch queue, agent runtime, review, or merge."
      else
        record_check "X1" "Issue-to-Merge Cycle Time" $STATUS_UNHEALTHY \
          "Median cycle time: ${median_hours}h — well above 4h target" \
          "{\"median_hours\": $median_hours, \"sample_size\": ${#cycle_times[@]}}" \
          "Identify bottleneck: dispatch queue, agent runtime, review, or merge."
      fi
    fi
  fi

  # X2: No Issues Stuck > 24 Hours
  local stuck_count=0 stuck_details="[]"
  local threshold_24h
  threshold_24h=$(hours_ago 24)

  for label in "status:in-progress" "status:ready"; do
    local issues_json
    issues_json=$(gh_api "repos/$REPO/issues?labels=$label&state=open&per_page=100")

    while IFS= read -r issue; do
      [[ -z "$issue" || "$issue" == "null" ]] && continue
      local has_agent
      has_agent=$(echo "$issue" | safe_jq "false" \
        '[.labels[]?.name | select(startswith("agent:"))] | length > 0')
      [[ "$has_agent" != "true" ]] && continue

      local updated_at update_mins
      updated_at=$(echo "$issue" | safe_jq "" -r '.updated_at // empty')
      [[ -z "$updated_at" ]] && continue
      update_mins=$(minutes_since "$updated_at")

      if (( update_mins > 1440 )); then  # 24 hours
        local issue_num
        issue_num=$(echo "$issue" | safe_jq "0" -r '.number')
        stuck_count=$((stuck_count + 1))
        stuck_details=$(echo "$stuck_details" | jq \
          --argjson num "$issue_num" --arg status "$label" --argjson mins "$update_mins" \
          '. + [{issue_number: $num, status: $status, minutes_stuck: $mins}]' 2>/dev/null || echo "$stuck_details")
      fi
    done < <(echo "$issues_json" | safe_jq "" -c '.[]?')
  done

  if (( stuck_count == 0 )); then
    record_check "X2" "No Issues Stuck >24h" $STATUS_HEALTHY \
      "No agent issues stuck longer than 24 hours"
  else
    record_check "X2" "No Issues Stuck >24h" $STATUS_UNHEALTHY \
      "${stuck_count} issue(s) stuck >24 hours" \
      "{\"stuck_count\": $stuck_count, \"stuck_issues\": $stuck_details}" \
      "Investigate: dependency cycles, repeated rejections, or agent failures."
  fi

  # X3: Review Escalation Accumulation
  local needs_human_issues nh_count
  needs_human_issues=$(gh_api "repos/$REPO/issues?labels=needs-human&state=open&per_page=100")
  nh_count=$(echo "$needs_human_issues" | safe_jq "0" 'if type == "array" then length else 0 end')

  if (( nh_count <= 2 )); then
    record_check "X3" "Escalation Accumulation" $STATUS_HEALTHY \
      "${nh_count} issue(s) needing human attention" \
      "{\"count\": $nh_count}"
  elif (( nh_count <= 5 )); then
    record_check "X3" "Escalation Accumulation" $STATUS_DEGRADED \
      "${nh_count} issues needing human attention (threshold: ≤2)" \
      "{\"count\": $nh_count}" \
      "Human must triage escalated issues."
  else
    record_check "X3" "Escalation Accumulation" $STATUS_UNHEALTHY \
      "${nh_count} issues needing human attention (>5 = unhealthy)" \
      "{\"count\": $nh_count}" \
      "Urgent: human triage needed — agents are blocked on decisions."
  fi

  # X4: Workflow YAML Integrity
  local x4_violations="" x4_count=0 x4_worst=$STATUS_HEALTHY

  for workflow_file in .github/workflows/agent-*.yml; do
    [[ ! -f "$workflow_file" ]] && continue
    local wf_name
    wf_name=$(basename "$workflow_file")

    # Anti-pattern 1: Self-referencing step conditions
    local self_refs
    self_refs=$(python3 << PYEOF 2>/dev/null || true
import yaml, sys
try:
    with open("$workflow_file") as f:
        wf = yaml.safe_load(f)
except Exception:
    sys.exit(0)

for job_name, job in (wf.get("jobs") or {}).items():
    steps = job.get("steps") or []
    for step in steps:
        step_id = step.get("id", "")
        condition = str(step.get("if", ""))
        if step_id and f"steps.{step_id}." in condition:
            print(f"{wf_name}/{job_name}/{step_id}: self-referencing condition")
PYEOF
)
    if [[ -n "$self_refs" ]]; then
      x4_count=$((x4_count + 1))
      x4_violations+="CRITICAL: $self_refs; "
      x4_worst=$STATUS_CRITICAL
    fi

    # Anti-pattern 2: Fatal logging in always() steps
    if grep -qP 'if:\s+always\(\)' "$workflow_file" 2>/dev/null; then
      local fatal_always
      fatal_always=$(python3 << PYEOF 2>/dev/null || true
import yaml, sys
try:
    with open("$workflow_file") as f:
        wf = yaml.safe_load(f)
except Exception:
    sys.exit(0)

for job_name, job in (wf.get("jobs") or {}).items():
    steps = job.get("steps") or []
    for step in steps:
        condition = str(step.get("if", ""))
        run_block = str(step.get("run", ""))
        if "always()" in condition and ("set -euo pipefail" in run_block or run_block.startswith("set -e")):
            name = step.get("name", step.get("id", "unknown"))
            print(f"{wf_name}/{name}: set -e in always() step")
PYEOF
)
      if [[ -n "$fatal_always" ]]; then
        x4_count=$((x4_count + 1))
        x4_violations+="DEGRADED: $fatal_always; "
        (( x4_worst < STATUS_DEGRADED )) && x4_worst=$STATUS_DEGRADED
      fi
    fi

    # Anti-pattern 3: Old token parsing pattern
    if grep -q 'select(.type == "usage")' "$workflow_file" 2>/dev/null; then
      x4_count=$((x4_count + 1))
      x4_violations+="DEGRADED: $wf_name uses deprecated token parsing; "
      (( x4_worst < STATUS_DEGRADED )) && x4_worst=$STATUS_DEGRADED
    fi
  done

  if (( x4_count == 0 )); then
    record_check "X4" "Workflow YAML Integrity" $STATUS_HEALTHY \
      "No anti-patterns detected in workflow files"
  else
    record_check "X4" "Workflow YAML Integrity" $x4_worst \
      "${x4_count} anti-pattern(s) detected: ${x4_violations%%; }" \
      "{\"violation_count\": $x4_count}" \
      "Fix workflow YAML anti-patterns per violation details."
  fi
}

# ---------------------------------------------------------------------------
# Run selected check categories
# ---------------------------------------------------------------------------
for cat in "${CATEGORIES[@]}"; do
  case "$cat" in
    runner)        run_runner_checks ;;
    dispatch)      run_dispatch_checks ;;
    sweep)         run_sweep_checks ;;
    review)        run_review_checks ;;
    notifications) run_notification_checks ;;
    budget)        run_budget_checks ;;
    crosscutting)  run_crosscutting_checks ;;
    *)             echo "Unknown category: $cat" >&2 ;;
  esac
done

# ---------------------------------------------------------------------------
# Build report
# ---------------------------------------------------------------------------
timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

healthy_count=$(grep -c '"HEALTHY"' "$RESULTS_FILE" || true)
degraded_count=$(grep -c '"DEGRADED"' "$RESULTS_FILE" || true)
unhealthy_count=$(grep -c '"UNHEALTHY"' "$RESULTS_FILE" || true)
critical_count=$(grep -c '"CRITICAL"' "$RESULTS_FILE" || true)

overall=$(status_name $worst_status)

report=$(jq -cn \
  --arg ts "$timestamp" \
  --arg overall "$overall" \
  --argjson healthy "${healthy_count:-0}" \
  --argjson degraded "${degraded_count:-0}" \
  --argjson unhealthy "${unhealthy_count:-0}" \
  --argjson critical "${critical_count:-0}" \
  --slurpfile checks "$RESULTS_FILE" \
  '{
    timestamp: $ts,
    overall_status: $overall,
    checks: $checks,
    summary: {
      healthy: $healthy,
      degraded: $degraded,
      unhealthy: $unhealthy,
      critical: $critical
    }
  }')

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
if $OUTPUT_JSON; then
  echo "$report"
else
  echo "🏥 Pipeline Health Report — $timestamp"
  echo ""
  echo "Overall: $(status_emoji $worst_status) $overall"
  echo ""

  while IFS= read -r check; do
    [[ -z "$check" ]] && continue
    local_id=$(echo "$check" | jq -r '.id')
    local_name=$(echo "$check" | jq -r '.name')
    local_status=$(echo "$check" | jq -r '.status')
    local_message=$(echo "$check" | jq -r '.message')

    case "$local_status" in
      HEALTHY)   local_emoji="🟢" ;;
      DEGRADED)  local_emoji="🟡" ;;
      UNHEALTHY) local_emoji="🟠" ;;
      CRITICAL)  local_emoji="🔴" ;;
    esac

    echo "$local_emoji $local_id: $local_name"
    echo "   $local_message"
  done < "$RESULTS_FILE"

  echo ""
  echo "Summary: ${healthy_count}🟢 ${degraded_count}🟡 ${unhealthy_count}🟠 ${critical_count}🔴"
fi

# ---------------------------------------------------------------------------
# Slack posting
# ---------------------------------------------------------------------------
if $POST_SLACK; then
  slack_url="${SLACK_WEBHOOK_URL:-}"
  if [[ -z "$slack_url" ]]; then
    echo "::warning::--slack requested but SLACK_WEBHOOK_URL not set" >&2
  else
    slack_text="🏥 Pipeline Health Alert — $timestamp\n\nOverall: $(status_emoji $worst_status) $overall\n\n"
    while IFS= read -r check; do
      [[ -z "$check" ]] && continue
      cs=$(echo "$check" | jq -r '.status')
      if [[ "$cs" != "HEALTHY" ]]; then
        ci=$(echo "$check" | jq -r '.id')
        cn=$(echo "$check" | jq -r '.name')
        cm=$(echo "$check" | jq -r '.message')
        cr=$(echo "$check" | jq -r '.remediation // empty')
        case "$cs" in
          DEGRADED)  ce="🟡" ;;
          UNHEALTHY) ce="🟠" ;;
          CRITICAL)  ce="🔴" ;;
        esac
        slack_text+="$ce $ci: $cn\n   $cm\n"
        if [[ -n "$cr" ]]; then
          slack_text+="   Remediation: $cr\n"
        fi
      fi
    done < "$RESULTS_FILE"
    slack_text+="\nSummary: ${healthy_count}🟢 ${degraded_count}🟡 ${unhealthy_count}🟠 ${critical_count}🔴"

    curl -s -X POST "$slack_url" \
      -H 'Content-type: application/json' \
      -d "{\"text\": \"$(echo -e "$slack_text")\"}" \
      > /dev/null 2>&1 || echo "::warning::Failed to post to Slack" >&2
  fi
fi

exit $worst_status
