# Review Agent — Process Documentation

> How the Review Agent operates within the multi-agent development system.

## Overview

The Review Agent is the verification stage between coding and merge. It
reviews every PR targeting `main`, checking implementation against the
linked issue, spec, and project quality standards.

## Workflow Sequence

```
Coding Agent opens PR
  → pr-checks.yml runs (lint, build, tests, Playwright)
  → agent-review.yml runs (Claude Code review)
  → Review verdict determined:
      → APPROVE: auto-merge + issue closed
      → FIX_AND_APPROVE: review agent applies fixes → verify → auto-merge
      → REQUEST_CHANGES: issue relabeled status:ready
          → dispatch sweep re-triggers coding agent (every hour)
          → coding agent reads review feedback + applies fixes
      → MANUAL_ATTENTION: human reviewer notified
```

## Workflows

### PR Checks (`pr-checks.yml`)

Runs automated CI checks as independent status checks:

| Job | Status Check | Purpose |
|-----|-------------|---------|
| `lint-and-build` | `pr-checks / Lint & Build` | Lint + compile/build |
| `tests` | `pr-checks / Tests` | Unit and integration tests |
| `playwright` | `pr-checks / Playwright` | E2E browser tests (conditional) |

The Playwright job only runs when the PR has the `needs-playwright` label.

These checks run independently of the Claude review. Branch protection
rules can require these checks to pass before merge.

### Agent Review (`agent-review.yml`)

Runs Claude Code in headless mode to review the PR diff against specs.

**Triggers:**
- `pull_request`: opened, synchronize, reopened, ready_for_review
- `workflow_dispatch`: with `pr_number` input (used by dispatch workflow)

**Draft PRs are skipped.**

**Steps:**
1. Extract PR metadata (agent/human, issue number, agent ID)
2. Checkout PR branch (for potential fix commits)
3. Count review cycles (agent PRs only)
4. Escalate if review limit reached (3 cycles max)
5. Check daily review limit (15 reviews/day)
6. Get PR diff
7. Collect context (PR body, issue body, spec content)
8. Run Claude Code review with extracted prompt
9. Parse verdict
10. If `FIX_AND_APPROVE`: apply automated fixes on PR branch
11. If `FIX_AND_APPROVE`: verify fixes with second Claude pass
12. Post review comment (all verdict paths)
13. Auto-merge if approved (including successful fix-and-approve)
14. Log token usage (aggregated from review + fix + verify passes)
15. Upload artifacts

## Review Verdicts

| Verdict | Meaning | Action |
|---------|---------|--------|
| `APPROVE` | PR meets requirements | Auto-merge, close issue, check for follow-ups |
| `FIX_AND_APPROVE` | Only deterministic issues found | Review agent fixes, verifies, then auto-merges |
| `REQUEST_CHANGES` | Specific issues to fix | Coding agent iterates |
| `MANUAL_ATTENTION` | Needs human judgment | Escalate with `needs-human` label |

## Issue Closure and Follow-up

After a PR is approved and merged, the review workflow handles issue lifecycle:

1. **Issue closure:** Explicitly closes the linked issue and transitions labels
   to `status:done`. This is a backup to GitHub's "Closes #N" auto-close keyword
   in the commit message.

2. **Follow-up detection:** Checks the merged PR body for non-empty "Follow-up
   Items" or "Known Limitations" sections. If the coding agent documented remaining
   work, a follow-up issue is created automatically.

3. **Follow-up issue creation:** The new issue inherits the original's agent and
   layer labels, is set to `status:ready`, and references the original issue and
   PR. The dispatch sweep picks it up for the next agent run.

4. **Traceability:** A comment is added to the original issue linking to the
   follow-up, maintaining a clear audit trail.

### FIX_AND_APPROVE Flow

When the review agent determines that the only issues are deterministic and automatable,
it outputs a fix plan and the `FIX_AND_APPROVE` verdict. The workflow then:

1. **Fix phase**: Runs Claude Code with `fix-prompt.md` on the PR branch. The fix agent
   applies only the changes listed in the fix plan (gitignore rules, scaffold tests,
   missing directories/files, formatting). Commits are authored as
   `kite-review-agent[bot]`.
2. **Verify phase**: Runs Claude Code with `verify-prompt.md` to confirm the fixes are
   clean and no regressions were introduced.
3. **Outcome**: If verification passes → auto-merge. If verification fails → the PR
   comment reports the failure and the PR is NOT merged.

**Fixable issue categories** (only these qualify for `FIX_AND_APPROVE`):

| Category | Examples | Fix Action |
|----------|----------|------------|
| `gitignore` | Committed binaries, missing ignore rules | Add `.gitignore` rules, `git rm --cached` artifacts |
| `missing-tests` | No test files for new packages | Generate minimal scaffold tests |
| `missing-dirs` | Required directories absent | Create directory with README placeholder |
| `missing-files` | No README in new service dirs | Generate from convention |
| `formatting` | Wrong import order, style issues | Run `gofmt`, `ruff format`, `prettier` |

If any issue falls outside these categories, `REQUEST_CHANGES` or `MANUAL_ATTENTION`
is used instead.

## Context Provided to Claude

The review prompt receives:

| Context | Source |
|---------|--------|
| Review checklist | `review-agent/prompts/review-prompt.md` |
| PR description | GitHub PR body |
| Linked issue | GitHub issue body (agent PRs) |
| Spec content | First 200 lines of referenced spec file |
| PR diff | Full diff from `gh pr diff` |

## Review Feedback Loop (REQUEST_CHANGES → Re-dispatch)

When the review verdict is `REQUEST_CHANGES`:

1. Review agent posts feedback as a PR comment
2. Review workflow relabels the source issue to `status:ready`
   (removes `status:pr-open` and `status:in-progress`)
3. The dispatch sweep (`agent-dispatch-sweep.yml`, runs every hour)
   detects the orphaned `status:ready` + `agent:*` issue
4. Sweep removes and re-adds the agent label, triggering dispatch
5. Coding agent re-runs with the PR and review feedback available

The coding agent's `fix-review-comments` skill guides it through
reading review feedback, applying fixes, and re-verifying.

**Note:** The sweep runs hourly at :15. Issues with existing PRs
(needing fix cycles) are prioritized over new work. Use manual
`workflow_dispatch` on the sweep workflow for immediate re-trigger.

## Escalation Rules

### Agent PRs — Review Cycle Limit

After 3 review cycles without approval, the review agent:
1. Adds `needs-human` and `reason:review-limit` labels to the source issue
2. Posts an escalation comment on the PR
3. Stops reviewing — human takes over

### Manual Attention Verdict

When Claude determines the PR needs human judgment:
1. Posts `MANUAL_ATTENTION` comment with explanation
2. Adds `needs-human` label to the source issue
3. Does NOT auto-merge

## Daily Invocation Limit

| Parameter | Value |
|-----------|-------|
| Daily limit | 15 reviews/day |
| Gate mechanism | Line count in JSONL log (`wc -l`) |
| Limit check | Before each review |
| Logging | `/home/{{RUNNER_USER}}/kite-token-logs/review-agent/{DATE}.jsonl` |
| Alert threshold | 80% of daily limit (via token-tracking workflow) |

The gate is **invocation count**, not token sum. Each review run appends one
compact JSONL line to the daily log file. The workflow counts lines before
starting a new review; if the count reaches `DAILY_REVIEW_LIMIT` (set in
`agent-review.yml`), reviews are skipped until the next day.

Token usage is still tracked per-invocation for cost reporting, but it does
not gate reviews.

Token usage from all three phases (review, fix, verify) is aggregated in the daily log.

## PR Template

The PR template at `.github/PULL_REQUEST_TEMPLATE.md` structures PR
descriptions for optimal review. Sections:

- **Linked Issue** — connects PR to the work item
- **Spec Reference** — file path, commit SHA, section
- **Summary of Changes** — what and why
- **Acceptance Criteria Covered** — checkboxes from the issue
- **Tests Executed** — commands and results
- **UI Evidence** — screenshots or Playwright report
- **Known Limitations** — anything not fully validated

## Auto-Merge Criteria

A PR is auto-merged when ALL of these are true:
- Review verdict is `APPROVE` or `FIX_AND_APPROVE` (with successful verification)
- Daily invocation limit is not exhausted
- Review cycle limit not reached (agent PRs)
- PR is not a draft

**Budget-exempt merge path:** If a PR was approved in a previous review run
but auto-merge failed (e.g., empty `PROJECT_PAT`, transient error), re-triggering
the review workflow will detect the prior APPROVE comment and proceed directly
to auto-merge — even if the daily review limit is reached. This prevents
approved PRs from getting permanently stuck.

Auto-merge uses squash merge and deletes the source branch.

## Automatic Retry on Infrastructure Failure

When a review run fails due to infrastructure issues (not a verdict), the
workflow automatically re-queues the source issue for retry:

1. The `failure()` handler detects the job failure
2. Checks that the issue isn't already escalated (`needs-human`)
3. Resets the source issue to `status:ready`
4. Posts a retry comment with a link to the failed run
5. The hourly dispatch sweep picks up the re-queued issue

This prevents PRs from getting permanently stuck after transient failures
such as `E2BIG` (argument too long), OOM, or missing secrets.

**Note:** Retry only applies to agent PRs with a linked issue. Human PRs
and budget-exhaustion skips are not retried (budget resets daily).

## Status Checks for Branch Protection

The following status checks can be required in branch protection rules:

| Check | Source |
|-------|--------|
| `pr-checks / Lint & Build` | `pr-checks.yml` |
| `pr-checks / Tests` | `pr-checks.yml` |
| `pr-checks / Playwright` | `pr-checks.yml` (conditional) |

## Agent Message Format

Review comments use structured HTML headers for machine parsing:

```html
<!-- AGENT_MSG agent=review-agent action=approve issue=#42 -->
<!-- AGENT_MSG agent=review-agent action=fix-and-approve issue=#42 -->
<!-- AGENT_MSG agent=review-agent action=request-changes issue=#42 -->
<!-- AGENT_MSG agent=review-agent action=manual-attention issue=#42 -->
<!-- AGENT_MSG agent=review-agent action=escalate -->
```

Other agents (and the review cycle counter) parse these to understand
review outcomes without NLP.

## Artifacts

Each review run uploads:

| Artifact | Contents | Retention |
|----------|----------|-----------|
| `review-output-{run_id}` | Claude output (review + fix + verify JSONL) + PR diff patch + review result | 30 days |
| `test-results-{run_id}` | Test results + coverage | 14 days |
| `playwright-report-{run_id}` | Playwright HTML report | 14 days |
| `playwright-screenshots-{run_id}` | Screenshot PNGs | 14 days |

## Required Secrets and Permissions

| Secret/Permission | Purpose |
|-------------------|---------|
| `GITHUB_TOKEN` | PR comments, cycle counting, label management |
| `PROJECT_PAT` | Auto-merge, project board sync (must trigger downstream events) |
| Claude Code auth | Device-code auth stored on runner at `~/.config/claude/` |
| Self-hosted runner | `{{RUNNER_LABEL}}` label required |

No additional API keys are needed — Claude Code uses device-code
authentication configured on the runner.

**Important:** `PROJECT_PAT` is used for auto-merge (not `GITHUB_TOKEN`)
because merges done with `GITHUB_TOKEN` don't trigger downstream workflows
like slack-notify due to GitHub's anti-recursion rule.

## Troubleshooting

### PR approved but not merged

**Symptom:** PR has an APPROVE comment from the review agent but wasn't merged.

**Cause:** Auto-merge step failed — usually because `PROJECT_PAT` secret was
empty or unavailable at the time of the run.

**Fix:** Re-trigger the review workflow. The budget-exempt merge path detects
the prior APPROVE comment and merges without running Claude again:
```bash
gh workflow run "Agent – Review" -f pr_number=<PR_NUMBER>
```

### Budget exhausted — reviews skipped

**Symptom:** All Claude steps skipped with "Review agent daily review limit reached".

**Cause:** The daily review limit (15 reviews/day) was reached by earlier reviews.

**Fix:** Wait for limit reset (midnight UTC). For urgent PRs, manually merge:
```bash
gh pr merge <PR_NUMBER> --squash --delete-branch
```

### "Argument list too long" (exit code 126)

**Symptom:** Claude Code step fails with `E2BIG` or exit code 126.

**Cause:** PR diff exceeds the OS `ARG_MAX` limit (~2MB).

**Fix:** Already handled — the workflow truncates diffs to 150KB. If it recurs,
the truncation threshold may need lowering. Check the diff size in the workflow logs.

### Review failed — issue re-queued

**Symptom:** Issue comment says "Review Failed — Re-queued".

**Cause:** Infrastructure failure during review (OOM, network, etc.). The
workflow automatically reset the issue to `status:ready` for retry.

**Action:** No action needed — the dispatch sweep will re-trigger automatically.
Check the linked run URL in the comment to diagnose the root cause.

### Stuck PRs with no review activity

**Symptom:** PR sits open with no review comment for hours.

**Cause:** Dispatch didn't trigger the review workflow, or the review run was
cancelled by concurrency.

**Fix:** Manually trigger:
```bash
gh workflow run "Agent – Review" -f pr_number=<PR_NUMBER>
```

## File Inventory

| File | Purpose |
|------|---------|
| `.github/workflows/agent-review.yml` | Claude Code review workflow (review + fix + verify) |
| `.github/workflows/pr-checks.yml` | CI checks (lint, build, test, Playwright) |
| `.github/workflows/agent-design-validation.yml` | Post-merge spec alignment validation |
| `.github/workflows/agent-dispatch-sweep.yml` | Hourly sweep for orphaned/stale issues |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR description template |
| `/home/{{RUNNER_USER}}/kite-token-logs/` | Host-persisted invocation + token logs (one JSONL per agent per day) |
| `.github/scripts/sync-project-status.sh` | Project board status sync helper |
| `review-agent/prompts/review-prompt.md` | Review phase prompt (verdict + fix plan) |
| `review-agent/prompts/fix-prompt.md` | Fix phase prompt (apply deterministic fixes) |
| `review-agent/prompts/verify-prompt.md` | Verify phase prompt (confirm fixes are clean) |
| `review-agent/docs/review-process.md` | This document |
