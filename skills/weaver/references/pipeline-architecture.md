# Dream Maker Pipeline Architecture

## Agent Roles

| Agent | Runtime | Trigger | What It Does |
|-------|---------|---------|-------------|
| Pilot Agent | Claude Code (interactive) | Human | Authors specs, manages pipeline |
| Planning Agent | Claude Code (headless) | Push to specs/ | Decomposes specs → issues |
| Coding Agent | Claude Code / Codex CLI | Issue labeled agent:* | Implements issues → PRs |
| Review Agent | Claude Code (headless) | PR opened/updated | Reviews diffs, auto-merges |
| Deployment Agent | Codex CLI (headless) | Push to main | Builds + deploys services |

## Workflow Files

| Workflow | Purpose | Trigger |
|----------|---------|---------|
| agent-dispatch.yml | Self-chaining issue dispatcher | workflow_dispatch |
| agent-review.yml | PR review + auto-merge | workflow_dispatch |
| agent-planning.yml | Spec → issues decomposition | push to specs/ |
| agent-deploy.yml | Build + deploy services | push to main |
| agent-dispatch-sweep.yml | Hourly safety net | schedule (hourly) |
| agent-pipeline-health.yml | 25+ health checks | schedule (5min) |
| agent-slack-notify.yml | Slack notifications | various events |
| agent-token-tracking.yml | Budget + cost tracking | workflow_run |
| agent-design-validation.yml | Post-merge spec alignment | pull_request |
| agent-roadmap-progress.yml | Cognitive progress scoring | schedule (daily) |
| auto-close-parents.yml | Auto-close parent issues | issues.closed |
| pr-checks.yml | CI gate (lint/build/test) | pull_request |

## Required GitHub Secrets

| Secret | Scope | Purpose |
|--------|-------|---------|
| PROJECT_PAT | repo | GitHub Project board operations |
| SLACK_BOT_USER_OAUTH_ACCESS_TOKEN | env:dev | Slack Bot API |
| SLACK_BUILD_CHANNEL | env:dev | #builds channel ID |
| SLACK_ISSUES_CHANNEL | env:dev | #issues channel ID |
| SLACK_TOKENS_CHANNEL | env:dev | #tokens channel ID |

## Required Labels

Create these labels in the GitHub repo:

```
agent:claude-code    — Dispatch to Claude Code
agent:codex-cli      — Dispatch to Codex CLI
status:ready         — Ready for agent pickup
status:in-progress   — Agent working
status:in-review     — PR under review
status:pr-open       — PR exists
status:merged        — PR merged
status:done          — Complete
status:blocked       — Blocked by dependency
status:dead-letter   — Failed after max retries
status:planning      — Parent issue
needs-human          — Escalated to human
complexity:S         — Small (~100K tokens)
complexity:M         — Medium (~250K tokens)
complexity:L         — Large (~400K tokens)
layer:cognitive      — AI/ML layer
layer:integration    — Gateway layer
layer:runtime        — Infrastructure layer
layer:presentation   — UI layer
layer:cross-cutting  — Spans layers
```

## Runner Requirements

- Ubuntu 22.04+ (Linux)
- Docker + Docker Compose
- Node.js v22 LTS + pnpm
- Go 1.22+ (if using Go)
- Python 3.12+ + uv + ruff + mypy
- Claude Code CLI (@anthropic-ai/claude-code)
- Codex CLI (@openai/codex)
- gh CLI (authenticated)
- jq, curl, git

## Token Log Structure

```
~/dream-maker-logs/
├── claude-code/          # Coding agent runs
├── codex-cli/            # Codex coding agent runs
├── planning-agent/       # Spec decomposition
├── review-agent/         # PR reviews
├── validation-agent/     # Design validation
├── deployment-agent/     # Deploy fixes
├── roadmap-progress/     # Progress scoring
└── summaries/            # Daily aggregates
```

## Safety Mechanisms

1. Directory conflict detection — prevents concurrent edits to same service
2. Dependency checking — issues dispatched only when deps are closed
3. Daily budget limits — caps per-agent invocations
4. Review cycle limit (3) — escalates to human
5. Deploy retry limit (3) — escalates to human
6. Concurrency groups — prevents duplicate workflow runs
7. GITHUB_TOKEN anti-recursion — no infinite loops
8. Dispatch sweep (hourly) — catches stuck work
9. Pipeline health (5-min) — self-healing
10. Rate-guarded remediation — prevents cascading
