# Pipeline Health Criteria — Deterministic Check Specification

> **Purpose**: Define a comprehensive, deterministic set of checks that evaluate
> whether the {{PROJECT_NAME}} agent pipeline is operating correctly. Each check has a clear
> pass/fail condition, severity level, and remediation action. This spec serves
> as the blueprint for an automated health-check script.
>
> **Target**: GitHub Actions + GitHub API + Slack alerts channel (`#alerts`)

---

## 1. Check Categories

The pipeline has six functional layers. Each layer has specific health signals.

| Category | Components | What Can Fail |
|----------|-----------|---------------|
| **Runner** | Self-hosted runner (`{{RUNNER_LABEL}}`) | Offline, busy-stuck, disk full |
| **Dispatch** | `agent-dispatch.yml` | Steps skipped, agent crash, no PR produced |
| **Sweep** | `agent-dispatch-sweep.yml` | Not running, issues accumulating |
| **Review** | `agent-review.yml` | Review not posting, token logging crash, stuck PRs |
| **Notifications** | `agent-slack-notify.yml` | Silent failures, missing alerts |
| **Budget** | `agent-token-tracking.yml`, token logs | Budget exhausted, log corruption |

---

## 2. Health Status Definitions

Each check produces one of four statuses:

| Status | Symbol | Meaning |
|--------|--------|---------|
| **HEALTHY** | 🟢 | All conditions met, operating normally |
| **DEGRADED** | 🟡 | Partial functionality, self-healing expected |
| **UNHEALTHY** | 🟠 | Active problem requiring attention |
| **CRITICAL** | 🔴 | Pipeline broken, no work can proceed |

**Overall pipeline status** = worst status across all checks.

---

## 3. Runner Health Checks

### R1: Runner Online
- **Check**: `gh api repos/{owner}/{repo}/actions/runners` → at least one runner with `status == "online"` and label `{{RUNNER_LABEL}}`
- **Pass**: ≥1 runner online
- **Fail**: 0 runners online
- **Severity**: 🔴 CRITICAL
- **Remediation**: Alert human — runner machine may be down. Check SSH access and GitHub Actions runner service.

### R2: Runner Not Stuck
- **Check**: Runner is `busy == true` AND the oldest in-progress workflow run on `[self-hosted, {{RUNNER_LABEL}}]` started > 90 minutes ago
- **Pass**: No run exceeds 90 minutes
- **Fail**: A run has been active > 90 minutes (stuck agent)
- **Severity**: 🟠 UNHEALTHY
- **Remediation**: Cancel the stuck run via API. The sweep will re-dispatch the issue.

### R3: Runner Disk Space
- **Check**: (Requires runner-side monitoring) Check `/tmp` and worktree disk usage
- **Pass**: > 5GB free
- **Fail**: < 5GB free
- **Severity**: 🟠 UNHEALTHY
- **Remediation**: Clean old worktrees: `git worktree prune` + remove `/tmp/agent-*`

---

## 4. Dispatch Health Checks

### D1: Recent Dispatch Success
- **Check**: At least one `agent-dispatch.yml` run with `conclusion == "success"` in the last 4 hours
- **Pass**: ≥1 successful dispatch in last 4 hours
- **Fail (DEGRADED)**: No successful dispatch in last 4 hours, but there are issues in `status:ready`
- **Fail (HEALTHY)**: No dispatches needed (0 issues in `status:ready` with agent labels)
- **Severity**: 🟡 DEGRADED → 🟠 UNHEALTHY if > 8 hours with ready issues
- **Remediation**: Check dispatch workflow logs. Common causes:
  - Steps skipped after budget check (circular condition bug — should be fixed)
  - Runner offline (see R1)
  - All issues blocked by dependencies

### D2: No Dispatch Step Skips After Budget
- **Check**: For each recent dispatch run, verify that if `budget_ok == true`, the deps, worktree, prompt, and agent steps all ran (not skipped)
- **Pass**: All post-budget steps executed
- **Fail**: Steps skipped despite budget approval
- **Severity**: 🔴 CRITICAL
- **Remediation**: Workflow logic bug — check step `if:` conditions. This was the root cause of the circular self-reference bug.

### D3: Agent Produces Changes
- **Check**: For successful dispatch runs, the "Commit and push agent work" step has `has_changes == true`
- **Pass**: Agent produced file changes
- **Fail (single)**: Agent produced no changes (quality issue with the specific task/prompt)
- **Fail (pattern)**: 3+ consecutive dispatches with no changes
- **Severity**: 🟡 DEGRADED (single) → 🟠 UNHEALTHY (pattern)
- **Remediation**: Review agent prompts, issue descriptions, and spec content resolution.

### D4: PR Created After Agent Work
- **Check**: For dispatch runs where `has_changes == true`, verify a PR was created
- **Pass**: PR exists with matching branch name
- **Fail**: Changes committed but no PR
- **Severity**: 🟠 UNHEALTHY
- **Remediation**: Check "Create Pull Request" step logs. Common causes:
  - GraphQL permission issue (should use REST API)
  - Branch push failure

### D5: Dependency Check Not Self-Blocking
- **Check**: The "Check dependencies are complete" step's `if:` condition does NOT reference `steps.deps.outputs.*`
- **Pass**: Condition only checks `steps.budget.outputs.budget_ok`
- **Fail**: Self-referencing condition detected
- **Severity**: 🔴 CRITICAL
- **Remediation**: Fix the `if:` condition to remove self-reference. This is a static check — can be run against the YAML file directly.

---

## 5. Sweep Health Checks

### S1: Sweep Running on Schedule
- **Check**: `agent-dispatch-sweep.yml` has a successful or completed run in the last 2 hours
- **Pass**: ≥1 run in last 2 hours
- **Fail**: No runs in last 2 hours
- **Severity**: 🟡 DEGRADED
- **Remediation**: Check if cron schedule is correct. Manually trigger sweep.

### S2: No Accumulating Backlog
- **Check**: Count of open issues with `status:ready` + agent label
- **Pass**: ≤ 3 ready issues (normal pipeline flow)
- **Warn**: 4-8 ready issues (mild backlog)
- **Fail**: > 8 ready issues (sweep not keeping up)
- **Severity**: 🟡 DEGRADED (4-8) → 🟠 UNHEALTHY (> 8)
- **Remediation**: Check dispatch and sweep logs. May need to increase sweep frequency or fix dispatch failures.

### S3: No Stale In-Progress Issues
- **Check**: Count of open issues with `status:in-progress` + agent label, updated > 2 hours ago, with no open PR
- **Pass**: 0 stale in-progress issues
- **Fail**: ≥1 stale in-progress issue
- **Severity**: 🟠 UNHEALTHY
- **Remediation**: The sweep should now auto-reset these (after our fix). If still accumulating, check sweep workflow.

### S4: Sweep Not Continuously Cancelled
- **Check**: Last 3 sweep runs — at least 1 completed (not cancelled)
- **Pass**: ≥1 of last 3 runs completed
- **Fail**: All 3 cancelled (concurrency conflict or rapid triggers)
- **Severity**: 🟡 DEGRADED
- **Remediation**: Check for concurrent sweep triggers. Ensure `cancel-in-progress: true` isn't causing all sweeps to cancel each other.

---

## 6. Review Health Checks

### V1: PRs Get Reviewed Within SLA
- **Check**: All open PRs targeting main have a review-agent comment within 2 hours of creation
- **Pass**: All PRs have review comments or are < 2 hours old
- **Fail**: PR is > 2 hours old with 0 review comments
- **Severity**: 🟠 UNHEALTHY
- **Remediation**: Check if review workflow was triggered. Common causes:
  - PRs created with GITHUB_TOKEN don't trigger `pull_request` events
  - Dispatch workflow didn't call `workflow_dispatch` on review
  - Review agent budget exhausted

### V2: Review Workflow Not Failing
- **Check**: Last 3 `agent-review.yml` runs — at least 2 have `conclusion != "failure"`
- **Pass**: ≤1 failure in last 3 runs
- **Fail**: ≥2 failures in last 3 runs
- **Severity**: 🟠 UNHEALTHY
- **Remediation**: Check which step is failing. Common causes:
  - Token logging crash (should be non-fatal after our fix)
  - Claude CLI auth failure
  - Spec file not found

### V3: Reviews Produce Verdicts
- **Check**: For completed review runs, the "Parse review decision" step produced a verdict (approve/request-changes/fix-and-approve/manual)
- **Pass**: All completed reviews have a verdict
- **Fail**: Review completed but no verdict parsed
- **Severity**: 🟡 DEGRADED
- **Remediation**: Check review prompt and Claude output format. The verdict extraction regex may need updating.

### V4: Approved PRs Get Merged
- **Check**: PRs with an "APPROVE" review comment from review-agent are merged within 1 hour
- **Pass**: All approved PRs merged or < 1 hour old
- **Fail**: Approved PR not merged after 1 hour
- **Severity**: 🟠 UNHEALTHY
- **Remediation**: Check auto-merge step. Common causes:
  - PROJECT_PAT expired or missing
  - Branch protection rules blocking merge
  - Merge conflict

### V5: Request-Changes PRs Get Re-dispatched
- **Check**: Issues with `status:ready` that were reset by review (have a "Changes Requested" comment on their PR) get re-dispatched within 2 hours
- **Pass**: Re-dispatched or < 2 hours since review
- **Fail**: Issue stuck after review rejection for > 2 hours
- **Severity**: 🟡 DEGRADED
- **Remediation**: Check sweep is picking up these issues. The issue should have `status:ready` after review rejection.

---

## 7. Notification Health Checks

### N1: Slack Notifications Firing
- **Check**: `agent-slack-notify.yml` has at least one successful run in the last 24 hours (assuming pipeline activity)
- **Pass**: ≥1 success or no pipeline events to notify about
- **Fail**: Pipeline events occurred but no notifications sent
- **Severity**: 🟡 DEGRADED
- **Remediation**: Check workflow triggers. Common causes:
  - Events created by GITHUB_TOKEN are suppressed (need PROJECT_PAT for merge/close)
  - Slack webhook URL expired
  - Workflow filter not matching event type

### N2: No Silent Notification Failures
- **Check**: `agent-slack-notify.yml` runs don't consistently skip or fail
- **Pass**: Last 5 runs: ≤2 skipped, 0 failures
- **Fail**: >2 skipped or any failures
- **Severity**: 🟡 DEGRADED
- **Remediation**: Check skip conditions and Slack API errors in logs.

---

## 8. Budget Health Checks

### B1: Daily Budget Not Exhausted
- **Check**: For each agent (claude-code, codex-cli, review-agent), read today's token log and compare to daily budget
- **Pass**: All agents < 80% of daily budget
- **Warn**: Any agent at 80-99% of budget
- **Fail**: Any agent at 100% (budget exhausted)
- **Severity**: 🟡 DEGRADED (80-99%) → 🟠 UNHEALTHY (100%)
- **Remediation**: Wait for UTC midnight reset. If recurring, increase budget or optimize prompts.

### B2: Token Logs Not Corrupted
- **Check**: All `.jsonl` files in `/home/{{RUNNER_USER}}/kite-token-logs/*/` are valid JSONL (each line parses as JSON)
- **Pass**: All files valid
- **Fail**: Any file has unparseable lines
- **Severity**: 🟡 DEGRADED
- **Remediation**: Clean corrupted lines. Check which workflow is writing bad data.

### B3: Token Logs Not Oversized
- **Check**: No individual `.jsonl` file exceeds 1MB
- **Pass**: All files < 1MB
- **Fail**: Any file > 1MB (will cause git push failures)
- **Severity**: 🟠 UNHEALTHY
- **Remediation**: Archive or truncate old log files. Check for runaway logging.

---

## 9. Cross-Cutting Health Checks

### X1: Issue-to-Merge Cycle Time
- **Check**: Measure time from `status:in-progress` label addition to PR merge for recently closed issues
- **Pass**: Median cycle time < 4 hours
- **Warn**: Median 4-8 hours
- **Fail**: Median > 8 hours
- **Severity**: 🟡 DEGRADED (4-8h) → 🟠 UNHEALTHY (> 8h)
- **Remediation**: Identify bottleneck (dispatch queue, agent runtime, review, merge).

### X2: No Issues Stuck > 24 Hours
- **Check**: No open issue with `status:in-progress` or `status:ready` (with agent label) has been in that state for > 24 hours
- **Pass**: All active issues < 24 hours
- **Fail**: Any issue stuck > 24 hours
- **Severity**: 🟠 UNHEALTHY
- **Remediation**: Manual investigation. Possible causes:
  - Dependency cycle (issues depending on each other)
  - Repeated review rejection (max cycle limit)
  - Agent producing no changes

### X3: Review Escalation Accumulation
- **Check**: Count of open issues with `needs-human` label
- **Pass**: ≤ 2 issues needing human attention
- **Warn**: 3-5 issues
- **Fail**: > 5 issues
- **Severity**: 🟡 DEGRADED (3-5) → 🟠 UNHEALTHY (> 5)
- **Remediation**: Human must triage escalated issues.

### X4: Workflow YAML Integrity
- **Check**: Static analysis of workflow files for known anti-patterns:
  - Self-referencing step conditions (e.g., `steps.X.outputs.Y` in step X's `if:`)
  - Missing `|| true` on non-critical label operations
  - `set -euo pipefail` in `if: always()` steps (should be non-fatal)
  - Token parsing using old `select(.type == "usage")` pattern
- **Pass**: No anti-patterns detected
- **Fail**: Anti-pattern found
- **Severity**: 🔴 CRITICAL (self-ref) / 🟡 DEGRADED (others)
- **Remediation**: Fix the specific anti-pattern in the workflow YAML.

---

## 10. Check Execution Plan

### Frequency

| Check Group | Frequency | Trigger |
|-------------|-----------|---------|
| Runner (R1-R3) | Every 30 min | Cron |
| Dispatch (D1-D5) | Every hour | Cron + on sweep |
| Sweep (S1-S4) | Every 2 hours | Cron |
| Review (V1-V5) | Every hour | Cron + on PR events |
| Notifications (N1-N2) | Every 6 hours | Cron |
| Budget (B1-B3) | Every 4 hours | Cron |
| Cross-cutting (X1-X4) | Every 4 hours | Cron |

### Output Format

Each check run produces a JSON report:

```json
{
  "timestamp": "2026-03-13T12:00:00Z",
  "overall_status": "UNHEALTHY",
  "checks": [
    {
      "id": "R1",
      "name": "Runner Online",
      "status": "HEALTHY",
      "message": "1 runner online ({{GITHUB_ORG}})",
      "details": {}
    },
    {
      "id": "V1",
      "name": "PRs Get Reviewed Within SLA",
      "status": "UNHEALTHY",
      "message": "PR #80 open 14 hours with no review comment",
      "details": {
        "pr_number": 80,
        "age_hours": 14,
        "review_comments": 0
      }
    }
  ],
  "summary": {
    "healthy": 18,
    "degraded": 2,
    "unhealthy": 1,
    "critical": 0
  }
}
```

### Alert Routing

| Status | Action |
|--------|--------|
| 🟢 HEALTHY | No alert (log only) |
| 🟡 DEGRADED | Post to `#alerts` every 4 hours if persists |
| 🟠 UNHEALTHY | Post to `#alerts` immediately |
| 🔴 CRITICAL | Post to `#alerts` immediately + apply `needs-human` to affected issues |

### Alert Message Format

```
🏥 Pipeline Health Alert — {timestamp}

Overall: {status_emoji} {overall_status}

{for each non-healthy check:}
{status_emoji} {check_id}: {check_name}
   {message}
   Remediation: {remediation_summary}

Summary: {healthy}🟢 {degraded}🟡 {unhealthy}🟠 {critical}🔴
```

---

## 11. Self-Healing Actions

When `--heal` is enabled, the health check takes automatic corrective action
for known-fixable problems. All actions are **rate-guarded** to prevent
repeated firing.

### Heal Actions

| Trigger Check | Action | Rate Guard | Description |
|--------------|--------|-----------|-------------|
| S2/D1: Backlog or no recent dispatch | `trigger_dispatch` | 10 min | Triggers `Agent – Dispatch` if ready issues exist and no dispatch is running |
| S3: Stale in-progress issues (>2h) | `reset_stale_issue` | 30 min/issue | Resets `status:in-progress` → `status:ready` for re-dispatch |
| V4: Approved PR not merged (>1h) | `retry_merge` | 15 min/PR | Retries `gh pr merge --squash` on the approved PR |
| R2: Stuck runner (>90 min run) | `cancel_stuck_run` | 1 hour/run | Cancels the stuck workflow run |

### Rate-Guard Mechanism

Each action+target pair has a cooldown file in `/tmp/healthcheck-heal/`.
If the action was taken within the cooldown period, it is skipped.
This prevents the health check (running every 5 min) from spamming
the same corrective action.

Cooldown files are cleared on runner restart, which is safe because
a restart clears stale state that may have caused the issue.

### Heal Report

All healing actions are logged in the JSON report under `heal_actions`:

```json
{
  "heal_actions": [
    {
      "action": "trigger_dispatch",
      "target": "5 ready issues",
      "success": true,
      "message": "Triggered fresh dispatch"
    }
  ]
}
```

Slack alerts include a `🔧 Self-Healing` section showing what was fixed.

---

## 12. Implementation Notes

### Data Sources

All checks use the GitHub API exclusively — no runner-side access needed
(except R3 which requires a runner-side agent or monitoring tool).

Key API endpoints:
- `GET /repos/{owner}/{repo}/actions/runners` — runner status
- `GET /repos/{owner}/{repo}/actions/runs` — workflow runs (filter by workflow)
- `GET /repos/{owner}/{repo}/issues` — issue labels and timestamps
- `GET /repos/{owner}/{repo}/pulls` — PR status and comments
- `GET /repos/{owner}/{repo}/issues/{number}/comments` — issue/PR comments
- `GET /repos/{owner}/{repo}/contents//home/{{RUNNER_USER}}/kite-token-logs/` — budget logs

### Implementation Approach

The health check should be implemented as:

1. **GitHub Actions workflow** (`agent-pipeline-health.yml`) running on `ubuntu-latest`
   - Uses `gh` CLI for all API calls (authenticated via `PROJECT_PAT`)
   - Runs on schedule (see frequency table above)
   - Posts results to `#alerts` Slack channel via webhook or `gh` API

2. **Standalone bash script** (`.github/scripts/pipeline-health-check.sh`)
   - Can be run locally or in CI
   - Accepts `--json` flag for machine-readable output
   - Accepts `--slack` flag to post results to Slack
   - Returns exit code: 0 = healthy, 1 = degraded, 2 = unhealthy, 3 = critical

### Static Checks (X4)

These can run without API access — they parse workflow YAML files directly:

```bash
# Check for self-referencing step conditions
for WORKFLOW in .github/workflows/agent-*.yml; do
  # Extract step IDs and their if conditions
  # Flag any step whose if: references its own step ID
done

# Check for fatal logging steps
# Find steps with if: always() that also have set -euo pipefail

# Check for old token parsing patterns
grep -n 'select(.type == "usage")' .github/workflows/agent-*.yml
```

---

## 12. Severity Decision Matrix

Use this matrix when a check is ambiguous about severity:

| Factor | Increases Severity | Decreases Severity |
|--------|-------------------|-------------------|
| Duration | Problem persists > 2 hours | Problem < 30 minutes |
| Scope | Affects all issues/PRs | Affects single issue/PR |
| Self-healing | No auto-recovery path | Sweep/cron will fix |
| Data loss | Token logs corrupted | Only logging affected |
| Blocking | No issues can dispatch | Some issues still flowing |
| Pattern | Recurring failure | First occurrence |

---

## 13. Quick Reference — Healthy Pipeline Baseline

A fully healthy pipeline looks like this:

```
✅ Runner:     1+ online, not stuck, sufficient disk
✅ Dispatch:   ≥1 success in last 4h (if issues exist), no step skips
✅ Sweep:      Running hourly, ≤3 ready issues, 0 stale in-progress
✅ Review:     All PRs reviewed within 2h, ≤1 failure in last 3 runs
✅ Notify:     Firing on events, no silent failures
✅ Budget:     All agents < 80% daily budget, logs valid
✅ Pipeline:   Median cycle time < 4h, no issues stuck > 24h
✅ YAML:       No anti-patterns in workflow files
```

An unhealthy pipeline has ANY of these red flags:

```
🔴 Runner offline — nothing can run
🔴 Dispatch steps skipping after budget OK — logic bug
🟠 PR unreviewed > 2 hours — review pipeline broken
🟠 Issues stuck in-progress > 2 hours — sweep not catching
🟠 Budget exhausted — agents blocked until reset
🟠 Token logs > 1MB — git push will fail
🟡 Backlog > 8 ready issues — throughput bottleneck
🟡 Sweep not running — accumulation risk
```
