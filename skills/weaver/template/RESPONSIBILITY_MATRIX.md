# Agent Responsibility Matrix

> Source of truth for agent roles, actions, and Slack notification routing.
> All notifications target the **{{SLACK_WORKSPACE}}** Slack workspace.

## Agents Overview

| Agent | Runtime | Trigger | Scope |
|-------|---------|---------|-------|
| **Planning Agent** | Claude Code (headless) | Push to `specs/**` / Cron (daily 06:00 UTC) / manual | Decomposes build stages into issues |
| **Coding Agent** | Claude Code / Codex CLI | Issue label (`agent:*`) | Implements issue in isolated branch |
| **Review Agent** | Claude Code (headless) | PR opened/updated on `main` | Reviews diffs, approves/requests changes |
| **Pilot Agent** | Claude Code (interactive) | Human-initiated | Authors specs, diagnoses/fixes pipeline issues, monitors Delivery Manager |
| **Delivery Manager** | Claude Code (interactive) | Human-initiated | Translates specs into GitHub Issues + Project board |
| **Token Tracker** | GitHub Actions (shell) | Workflow completion / cron | Aggregates token usage, budget alerts |
| **PR Checks** | GitHub Actions (shell) | PR opened/updated | Lint, build, test gate |

---

## Responsibility Matrix (RACI)

| Action | Planning | Coding | Review | Design | Delivery Mgr | Human |
|--------|----------|--------|--------|--------|--------------|-------|
| Read specs | C | C | I | **R** | C | **A** |
| Write specs | — | — | — | **R** | — | **A** |
| Create issues | **R** | — | — | — | **R** | **A** |
| Assign agent labels | **R** | — | — | — | **R** | **A** |
| Write code | — | **R** | — | — | — | **A** |
| Run tests | — | **R** | I | — | — | I |
| Create PR | — | **R** (via CI) | — | — | — | I |
| Review PR | — | — | **R** | — | — | **A** |
| Approve/merge PR | — | — | **R** | — | — | **A** |
| Close issue (post-merge) | — | — | **R** | — | I | **A** |
| Create follow-up issue | — | — | **R** | — | I | **A** |
| Escalate to human | **R** | **R** | **R** | — | — | **A** |
| Track tokens | I | I | I | — | — | **A** |
| Manage project board | — | — | — | — | **R** | **A** |
| Budget alerts | — | — | — | — | — | **A** |

> **R** = Responsible (does the work), **A** = Accountable (approves), **C** = Consulted, **I** = Informed

---

## Slack Notification Routing

### Channel: `#builds` (`{{SLACK_BUILD_CHANNEL_ID}}`)

Build and deployment notifications for merged code.

| Event | Trigger | Message Format | Agent Source |
|-------|---------|----------------|--------------|
| PR merged to main | `pull_request.closed` + merged | 🚀 commit SHA, title, author, links | Review Agent (auto-merge) or Human |
| CI checks passed | `check_suite.completed` | ✅ PR #, check names, duration | PR Checks workflow |
| CI checks failed | `check_suite.completed` | ❌ PR #, failed check, log link | PR Checks workflow |
| Agent PR created | `pull_request.opened` (branch `agent/*`) | 🤖 agent ID, issue #, branch, PR link | Coding Agent (via Dispatch) |
| Agent PR auto-merged | `pull_request.closed` + merged + `agent/*` | 🤖✅ agent, issue #, merge SHA | Review Agent |

### Channel: `#issues` (`{{SLACK_ISSUES_CHANNEL_ID}}`)

Issue lifecycle and project board updates.

| Event | Trigger | Message Format | Agent Source |
|-------|---------|----------------|--------------|
| Issue created | `issues.opened` | 📋 title, author, labels, project link | Human / Planning Agent |
| Issue labeled | `issues.labeled` | 🏷️ issue #, label added, current labels | Human / Planning Agent |
| Issue assigned to agent | `issues.labeled` (`agent:*`) | 🤖 agent assignment, issue #, title | Human / Planning Agent |
| Issue closed | `issues.closed` | ✅ issue #, close reason, linked PR | Review Agent (post-merge) / Human |
| Follow-up issue created | `issues.opened` (`follow-up:` prefix) | 📋 follow-up #, original issue #, outstanding items | Review Agent |
| Issue reopened | `issues.reopened` | 🔄 issue #, title | Human |
| Issue comment added | `issue_comment.created` | 💬 issue #, commenter, snippet | Any agent / Human |
| Needs-human escalation | `issues.labeled` (`needs-human`) | 🚨 issue #, reason, agent, action link | Any agent |
| Kanban: status changed | Project item field change | 📌 issue #, old status → new status | Delivery Manager / Automation |

### Channel: `#issues` — Planning Summary

| Event | Trigger | Message Format | Agent Source |
|-------|---------|----------------|--------------|
| Planning run complete | `workflow_run` (Planning) | 🤖 ready/in-progress/needs-human counts | Slack Notifier |

### Channel: `#builds` — Stale PRs

| Event | Trigger | Message Format | Agent Source |
|-------|---------|----------------|--------------|
| Stale agent PRs | Cron (daily 09:00 UTC) | 📋 open agent PR list | Slack Notifier |

### Channel: `#tokens` (`{{SLACK_TOKENS_CHANNEL_ID}}`)

Agent activity and budget notifications.

| Event | Trigger | Message Format | Agent Source |
|-------|---------|----------------|--------------|
| Limit alert (80%+) | `workflow_run` (Token Tracking) | ⚠️ agent, invocations/limit, link to alert issue | Slack Notifier |
| Daily activity summary | `workflow_run` (Token Tracking) | 📊 per-agent invocations/limit, tokens, cost, progress bars | Slack Notifier |

---

## Notification Priority Levels

| Priority | Slack Treatment | Examples |
|----------|----------------|----------|
| 🚨 **Critical** | Immediate, `@channel` mention | `needs-human` escalation, budget exceeded |
| ⚠️ **Warning** | Immediate, no mention | CI failure, budget at 80%, review cycle 3 |
| 📋 **Info** | Batched OK | Issue created, PR opened, status change |
| 📊 **Digest** | Daily summary | Token usage, stale PR report |

---

## Agent → GitHub Actions Mapping

| Agent Role | Workflow File | Runs On | Daily Limit |
|------------|---------------|---------|-------------|
| Planning Agent | `agent-planning.yml` | `self-hosted, {{RUNNER_LABEL}}` | 5 runs/day |
| Coding Agent | `agent-dispatch.yml` | `self-hosted, {{RUNNER_LABEL}}` | 10 issues/day |
| Review Agent | `agent-review.yml` | `self-hosted, {{RUNNER_LABEL}}` | 15 reviews/day |
| Validation Agent | `agent-design-validation.yml` | `self-hosted, {{RUNNER_LABEL}}` | 5 validations/day |
| Token Tracker | `agent-token-tracking.yml` | `ubuntu-latest` | — |
| Dispatch Sweep | `agent-dispatch-sweep.yml` | `ubuntu-latest` | — |
| Slack Notifier | `agent-slack-notify.yml` | `ubuntu-latest` | — |
| Pipeline Health | `agent-pipeline-health.yml` | `self-hosted, {{RUNNER_LABEL}}` | — |
| PR Checks | `pr-checks.yml` | `self-hosted, {{RUNNER_LABEL}}` | — |

---

## GitHub Project Kanban Sync

**Project:** Assistants (#1) — `{{GITHUB_PROJECT_ID}}`

### Status Field Mapping

| Kanban Column | Option ID | Trigger | Slack Channel |
|---------------|-----------|---------|---------------|
| **Backlog** | `f75ad846` | Issue created (default) | `#issues` |
| **Ready** | `61e4505c` | Planning agent triages / `status:ready` label | `#issues` |
| **In progress** | `47fc9ee4` | Agent dispatched / `status:in-progress` label | `#issues` |
| **In review** | `df73e18b` | PR opened / `status:in-review` label | `#issues` |
| **Done** | `98236657` | PR merged / `status:merged` label / issue closed | `#issues` + `#builds` |

### Label → Kanban Auto-Sync Rules

| Label Applied | Project Status Set To | Slack Notification |
|---------------|----------------------|-------------------|
| `status:ready` | Ready | 📌 Issue ready for agents |
| `agent:claude-code` | In progress | 🤖 Agent assigned |
| `agent:codex-cli` | In progress | 🤖 Agent assigned |
| `status:in-progress` | In progress | 🔨 Work started |
| `status:in-review` | In review | 👀 PR under review |
| `status:pr-open` | In review | 👀 PR opened |
| `status:merged` | Done | ✅ PR merged |
| `needs-human` | (unchanged) | 🚨 Escalation |
| `status:blocked` | (unchanged) | ⚠️ Blocked |
| `status:dead-letter` | (unchanged) | 💀 Dead letter |

---

## Secrets Required

| Secret | Environment | Used By | Purpose |
|--------|-------------|---------|---------|
| `SLACK_BOT_USER_OAUTH_ACCESS_TOKEN` | `dev` | `agent-slack-notify.yml` | Slack Bot OAuth token |
| `SLACK_BUILD_CHANNEL` | `dev` | `agent-slack-notify.yml` | `#builds` channel (`{{SLACK_BUILD_CHANNEL_ID}}`) |
| `SLACK_ISSUES_CHANNEL` | `dev` | `agent-slack-notify.yml` | `#issues` channel (`{{SLACK_ISSUES_CHANNEL_ID}}`) |
| `SLACK_TOKENS_CHANNEL` | `dev` | `agent-slack-notify.yml` | `#tokens` channel (`{{SLACK_TOKENS_CHANNEL_ID}}`) |
| `GITHUB_TOKEN` | (auto) | All workflows | GitHub API access |
| `PROJECT_TOKEN` | — | Project sync workflow | PAT with `project` scope (if needed) |

---

## Smoke Test Checklist

Run these to verify the full notification pipeline:

```bash
# 1. Slack channel connectivity
#    Post a test message to both channels via Slack API

# 2. Issue CRUD → #issues notification
gh issue create --repo {{GITHUB_ORG}}/{{GITHUB_REPO}} --title "[Smoke Test] $(date +%s)"
#    Verify: message appears in #issues

# 3. Project kanban sync
gh project item-add 1 --owner {{GITHUB_ORG}} --url <issue-url>
gh project item-edit --project-id {{GITHUB_PROJECT_ID}} --id <item-id> \
  --field-id PVTSSF_lAHOD-jens4BRSVIzg_KJKM --single-select-option-id 61e4505c
#    Verify: item moves to Ready column

# 4. Build merge → #builds notification
#    Merge a PR and verify notification in #builds

# 5. Escalation → #issues notification
gh issue edit <number> --add-label needs-human --repo {{GITHUB_ORG}}/{{GITHUB_REPO}}
#    Verify: 🚨 escalation message in #issues
```
