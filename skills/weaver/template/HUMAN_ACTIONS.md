# Human Actions

This file lists setup and approval work that still requires a human before
development can run cleanly. Items marked ✅ are complete.

## GitHub Repository Setup
- ✅ Confirm `main` is the default branch.
- Configure branch protection or rulesets for `main`.
- Require pull requests before merge.
- Require required status checks before merge (`pr-checks / Lint & Build`, `pr-checks / Tests`).
- Decide whether Claude review counts as approval or whether human approval remains mandatory.
- Decide whether squash merge is the only allowed merge strategy (currently auto-merge uses squash).
- Decide whether merge queue is needed now or later.

## GitHub Project Setup
- Confirm the `Assistants` project fields.
- Recommended fields: `Status`, `Priority`, `Owner`, `Area`, `Target release`, `Target date`, `Risk`, `Effort`.
- Create core views: `Backlog`, `In Progress`, `Roadmap`, `Release vNext`, `Bugs`.
- Define milestone naming for releases and delivery phases.

## Repository Metadata
- ✅ Create issue templates for agent tasks.
- ✅ Create a pull request template (`.github/PULL_REQUEST_TEMPLATE.md`).
- Add `CODEOWNERS`.
- ✅ Define agent-related labels (`agent:*`, `status:*`, `layer:*`, `complexity:*`).
- Define labels for `feature`, `bug`, `tech-debt`, `docs`, `infra`, `release-blocker`, `research`.

## Actions And Environments
- ✅ Create `dev` GitHub environment.
- ✅ Add `PROJECT_PAT` secret (created 2026-03-12).
- ✅ Add `SLACK_BOT_USER_OAUTH_ACCESS_TOKEN` secret.
- ✅ Add `SLACK_BUILD_CHANNEL`, `SLACK_ISSUES_CHANNEL`, `SLACK_TOKENS_CHANNEL` secrets.
- Decide whether `staging` and `prod` environments are needed now.
- Decide who can approve protected deployments.

## Workflow Inventory (all operational)
- ✅ `agent-planning.yml` — decompose specs into issues (with dedup guard)
- ✅ `agent-dispatch.yml` — dispatch coding agents to issues
- ✅ `agent-dispatch-sweep.yml` — catch orphaned ready issues every hour
- ✅ `agent-review.yml` — review PRs, auto-merge on approval
- ✅ `pr-checks.yml` — lint, build, test, Playwright
- ✅ `agent-token-tracking.yml` — aggregate token logs, budget alerts
- ✅ `agent-design-validation.yml` — post-merge spec alignment validation
- ✅ `agent-pipeline-health.yml` — automated pipeline health checks
- ✅ `agent-slack-notify.yml` — escalation, stale PRs, planning summary, budget alerts, token summary

## Release Process
- Decide the first release naming scheme.
- Decide whether releases are milestone-based, semantic versions, or both.
- Decide who approves releases.
- Decide whether release notes are generated automatically from PR labels.

## Agent Governance
- ✅ Role split: Claude Code (primary coding), Codex CLI (configured).
- ✅ Agents cannot create labels, milestones, or workflow files (enforced by CLAUDE.md boundaries).
- ✅ Escalation: agents add `needs-human` label → Slack notification.
- ✅ Invocation limits: Planning 5/day, Coding 10/day, Review 15/day, Validation 5/day, Deployment 15/day.
- Confirm which actions always require human approval (currently: architecture decisions, new dependencies, multi-service changes).

## Known Pipeline Behaviors
- **Concurrency cancellation**: dispatch runs share one concurrency group. If 3+ issues
  dispatch simultaneously, pending runs get cancelled. The sweep workflow (every hour)
  catches and re-triggers orphaned issues.
- **Review feedback loop**: when review requests changes, the issue is relabeled to
  `status:ready` and the sweep re-dispatches the coding agent. Max delay: ~1h.
- **GITHUB_TOKEN anti-recursion**: PRs/events created with GITHUB_TOKEN don't trigger
  other workflows. The dispatch workflow uses `workflow_dispatch` to explicitly trigger
  the review workflow after creating a PR.
- **Invocation logging**: all agent types log each invocation to
  `/home/{{RUNNER_USER}}/kite-token-logs/<agent>/<date>.jsonl` (one line per run).
  Budget checks count lines to enforce daily limits (not token sums).

## Before Development Starts
- ✅ Create the first milestone.
- ✅ Create the first set of issues with acceptance criteria (via planning agent).
- ✅ Assign initial ownership via agent labels.
- ✅ Run first changes through the full pipeline (branch → PR → review → merge validated).
