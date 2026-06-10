# Dream Maker Agent Team

> A complete AI workforce that turns specs into deployed software.

## The Team at a Glance

```
  You (Human)
    │
    ├─── Pilot Agent ──── writes specs ──────────────────┐
    │    (interactive)                                    │
    │                                                    ▼
    │                                           specs/ directory
    │                                                    │
    │                                           git push to main
    │                                                    │
    │                                                    ▼
    │                                    ┌── Planning Agent (Delivery Manager)
    │                                    │   decomposes spec → GitHub Issues
    │                                    │   chains dependencies
    │                                    │   adds to Project board
    │                                    │
    │                                    ▼
    │                              GitHub Issues
    │                           (status:ready label)
    │                                    │
    │                                    ▼
    │                         ┌── Dispatch Workflow ──┐
    │                         │  picks eligible issue  │
    │                         │  checks dependencies   │
    │                         │  avoids dir conflicts   │
    │                         └────────┬───────────────┘
    │                                  │
    │                                  ▼
    │                          Coding Agent
    │                    reads issue + spec → code
    │                    runs tests + lint
    │                    opens PR on agent/* branch
    │                                  │
    │                                  ▼
    │                          Review Agent
    │                    reviews diff vs spec
    │                    APPROVE → auto-merge
    │                    FIX_AND_APPROVE → fix + merge
    │                    REQUEST_CHANGES → back to coding
    │                                  │
    │                                  ▼
    │                       Deployment Agent
    │                    detects changed services
    │                    builds + health checks
    │                    auto-fixes failures (3 attempts)
    │                    escalates if stuck
    │                                  │
    │                                  ▼
    │                      Design Validation
    │                    compares merged code vs spec
    │                    ALIGNED → done
    │                    DEVIATION → correction issue
    │                                  │
    │                                  ▼
    │                       Pipeline Health
    │                    monitors all workflows
    │                    self-heals known issues
    │                    alerts on degraded status
    │                                  │
    │                                  ▼
    └─── Slack Notifications ──── #builds, #issues, #tokens
```

---

## Agent Profiles

### 1. Pilot Agent

**Role:** Architect and pipeline operator
**Runtime:** Claude Code (interactive, human-initiated)
**Model:** Claude Opus

| Aspect | Detail |
|--------|--------|
| **What it does** | Authors specs in `specs/`, diagnoses pipeline issues, monitors the Delivery Manager, implements CI/CD changes directly |
| **Input** | Human direction, pipeline health data, codebase state |
| **Output** | Spec files (`specs/*.md`), workflow fixes, pipeline improvements |
| **Boundaries** | Can commit specs and pipeline files. Cannot create issues or assign work. |
| **Escalation** | Asks human when architecture decisions aren't covered by existing specs |

**Key files:**
- `pilot-agent/AGENTS.md` — operating handbook
- `pilot-agent/docs/spec-authoring-guide.md` — how to write specs
- `pilot-agent/docs/handoff-conventions.md` — spec → Delivery Manager handoff
- `pilot-agent/docs/readiness-checklist.md` — spec quality gate

**How it works with the team:**
The Pilot Agent is the only agent that talks directly to you. It writes specs
that the rest of the pipeline consumes. It also monitors and fixes the pipeline
itself — workflows, health checks, agent configurations.

---

### 2. Delivery Manager (Planning Agent)

**Role:** Spec decomposer and project manager
**Runtime:** Claude Code (headless via GitHub Actions)
**Trigger:** Push to `specs/**` on main, or daily cron
**Model:** Claude Opus
**Daily limit:** Configurable (default: 20 runs/day)

| Aspect | Detail |
|--------|--------|
| **What it does** | Reads specs, creates parent + sub-issues, chains dependencies, adds to GitHub Project board |
| **Input** | Spec files from `specs/`, project state (open issues, milestones) |
| **Output** | GitHub Issues with labels, dependencies, project board entries |
| **Boundaries** | Cannot write code. Cannot modify specs. Can only create/edit issues. |
| **Escalation** | Comments on issue + `needs-human` label when spec is ambiguous |

**Key files:**
- `delivery-manager/AGENTS.md` — operating handbook
- `delivery-manager/CLAUDE.md` — Claude Code instructions
- `delivery-manager/prompts/planning-agent.md` — decomposition prompt
- `delivery-manager/prompts/dependency-validation.md` — dependency audit prompt
- `delivery-manager/templates/` — issue body templates (parent, sub, deviation, draft)
- `delivery-manager/scripts/` — issue creation, dependency linking, project sync

**Decomposition rules:**
1. One parent issue per spec (feature-level)
2. Sub-issues sized S/M (100-250K tokens) — never L/XL
3. Same-directory issues get `Depends on:` chains (prevents merge conflicts)
4. After creating all sub-issues, updates parent body with `#NNN` references
5. Deduplicates against existing open issues

**Workflow:** `agent-planning.yml`

---

### 3. Coding Agent

**Role:** Implementation engineer
**Runtime:** Claude Code or Codex CLI (headless via GitHub Actions)
**Trigger:** Issue labeled `agent:claude-code` or `agent:codex-cli`
**Model:** Claude Opus (Claude Code) or GPT-5.4 (Codex CLI)
**Daily limit:** Configurable (default: 100 issues/day per agent)

| Aspect | Detail |
|--------|--------|
| **What it does** | Reads issue + linked spec, implements code, runs tests/lint, pushes branch |
| **Input** | GitHub Issue with spec reference and acceptance criteria |
| **Output** | Code on `agent/*` branch, PR opened automatically |
| **Boundaries** | Cannot commit directly. Cannot modify specs. Cannot create issues. Works only on assigned issue. |
| **Escalation** | Comments on issue + `needs-human` label when blocked |

**Key files:**
- `coding-agent/AGENTS.md` — operating handbook (context consumption order, execution workflow)
- `coding-agent/config/claude.json` — Claude Code permissions (allow/deny lists)
- `coding-agent/config/codex.toml` — Codex CLI configuration
- `coding-agent/hooks/` — post-edit hooks (auto-format, go build, typecheck)
- `coding-agent/skills/` — 6 implementation skills:
  - `implement-issue.md` — full implementation workflow
  - `prepare-pr.md` — PR preparation and evidence
  - `fix-review-comments.md` — addressing review feedback
  - `add-tests.md` — adding test coverage
  - `add-playwright-test.md` — E2E browser tests
  - `sync-with-issue-spec.md` — spec alignment check
- `coding-agent/scripts/` — test collection, PR summary, change summary

**Execution flow:**
1. Read issue → Read spec → Plan approach
2. Implement code (smallest viable change)
3. Run lint + type checks + tests
4. Generate PR summary with evidence
5. Push to `agent/<issue-number>-<slug>` branch
6. CI opens PR automatically

**Workflow:** `agent-dispatch.yml` (self-chaining queue, up to depth 25)

---

### 4. Review Agent

**Role:** Code reviewer and quality gate
**Runtime:** Claude Code (headless via GitHub Actions)
**Trigger:** PR opened/updated targeting main
**Model:** Claude Opus
**Daily limit:** Configurable (default: 100 reviews/day)

| Aspect | Detail |
|--------|--------|
| **What it does** | Reviews PR diff against linked spec, approves or requests changes, auto-merges approved PRs |
| **Input** | PR diff, linked issue, spec content |
| **Output** | Review verdict (APPROVE / FIX_AND_APPROVE / REQUEST_CHANGES / MANUAL_ATTENTION) |
| **Boundaries** | Cannot write new features. Can only fix deterministic issues (gitignore, formatting, scaffolds). |
| **Escalation** | After 3 review cycles, labels `needs-human` for manual review |

**Verdicts:**
| Verdict | Action |
|---------|--------|
| `APPROVE` | Auto-merge PR, close issue, update project board |
| `FIX_AND_APPROVE` | Apply deterministic fixes, verify, merge |
| `REQUEST_CHANGES` | Post review comments, relabel issue to `status:ready`, coding agent re-dispatched |
| `MANUAL_ATTENTION` | Label `needs-human`, notify on Slack |

**Fixable categories** (FIX_AND_APPROVE):
- Missing `.gitignore` entries
- Missing test scaffolds
- Missing directories
- Formatting issues
- Missing file stubs referenced by other code

**Key files:**
- `review-agent/AGENTS.md` — operating handbook
- `review-agent/prompts/review-prompt.md` — main review prompt
- `review-agent/prompts/fix-prompt.md` — deterministic fix prompt
- `review-agent/prompts/fix-changes-prompt.md` — coding agent fix mode
- `review-agent/prompts/verify-prompt.md` — post-fix verification
- `review-agent/docs/review-process.md` — complete process documentation

**Workflow:** `agent-review.yml`

---

### 5. Deployment Agent

**Role:** Build and deploy engineer
**Runtime:** Codex CLI (headless via GitHub Actions)
**Trigger:** Push to main (post-merge)
**Model:** Codex Mini
**Daily limit:** Configurable (default: 100 deployments/day)

| Aspect | Detail |
|--------|--------|
| **What it does** | Detects changed services, builds with Docker Compose, verifies health checks, auto-fixes failures |
| **Input** | Git diff since last deployment, docker-compose.yml |
| **Output** | Built/running services, health check results |
| **Boundaries** | Can modify Dockerfiles and compose files for fixes. Cannot change application code. |
| **Escalation** | After 3 fix attempts, creates GitHub issue with failure details |

**Key files:**
- `deployment-agent/AGENTS.md` — operating handbook
- `deployment-agent/config/codex.toml` — Codex CLI configuration
- `deployment-agent/prompts/deploy-fix-prompt.md` — failure diagnosis prompt
- `deployment-agent/scripts/detect-changes.sh` — service change detection
- `deployment-agent/scripts/update-access-table.sh` — README service table
- `deployment-agent/scripts/update-roadmap-progress.sh` — cognitive progress scoring

**Workflow:** `agent-deploy.yml`

---

## Support Workflows

These workflows don't use AI agents — they're pure GitHub Actions automation.

### Dispatch Sweep (`agent-dispatch-sweep.yml`)
- **Runs:** Every hour
- **Purpose:** Safety net for the self-chaining dispatch
- **Actions:**
  - Resets issues stuck `in-progress` for 2+ hours
  - Restarts dispatch chain if stopped with eligible issues
  - Re-triggers review for orphaned PRs

### Auto-Close Parents (`auto-close-parents.yml`)
- **Runs:** On issue close + daily at 10:00 UTC
- **Purpose:** Closes parent issues when all sub-issues are done
- **Logic:** Scans parent body for `#NNN` references, batch-checks closure status

### PR Checks (`pr-checks.yml`)
- **Runs:** On PR open/update
- **Purpose:** CI gate before review
- **Checks:** Auto-detects language (Go/Python/TypeScript), runs lint + build + tests

### Token Tracking (`agent-token-tracking.yml`)
- **Runs:** After agent workflows + daily
- **Purpose:** Budget management and cost tracking
- **Actions:** Aggregates token logs, alerts at 80% of daily limit, posts daily summary

### Slack Notifications (`agent-slack-notify.yml`)
- **Runs:** On various events
- **Purpose:** Human-attention notifications
- **Channels:**
  - `#builds` — PR merged, CI pass/fail, stale PRs
  - `#issues` — Issue created/closed, escalations, planning summaries
  - `#tokens` — Budget alerts, daily activity digest

### Design Validation (`agent-design-validation.yml`)
- **Runs:** After PR merge (agent PRs only)
- **Purpose:** Validates merged code aligns with original spec
- **Output:** ALIGNED (pass) or DEVIATION (creates correction issue)

### Pipeline Health (`agent-pipeline-health.yml`)
- **Runs:** Every 5 minutes
- **Purpose:** Monitors all pipeline components
- **Self-healing:** Triggers dispatch, resets stale issues, retries merges, cancels stuck runs
- **Alerts:** Posts to Slack on DEGRADED or UNHEALTHY status

### Roadmap Progress (`agent-roadmap-progress.yml`)
- **Runs:** Daily at 06:00 UTC
- **Purpose:** Cognitive assessment of build progress
- **Output:** Per-deliverable 0-100% scores, updates ROADMAP.md

---

## Pipeline Flow: End to End

```
Spec pushed to main
        │
        ▼
[Planning Workflow] ─── triggers ─── agent-planning.yml
        │
        ├── Reads spec + existing issues
        ├── Creates parent issue
        ├── Creates sub-issues with dependencies
        ├── Adds all to GitHub Project
        └── Triggers dispatch chain
                │
                ▼
[Dispatch Workflow] ─── triggers ─── agent-dispatch.yml
        │
        ├── Checks daily budget
        ├── Finds eligible issues (status:ready, no unresolved deps)
        ├── Directory conflict detection (skips if same dir in-progress)
        ├── Picks highest-priority issue
        ├── Runs coding agent in git worktree
        ├── Pushes agent/* branch
        ├── Opens PR
        ├── Triggers review
        └── Self-chains to next issue (depth ≤ 25)
                │
                ▼
[Review Workflow] ─── triggers ─── agent-review.yml
        │
        ├── Waits for PR checks to pass
        ├── Reads PR diff + issue + spec
        ├── Runs review agent
        ├── APPROVE → auto-merge → close issue
        ├── FIX_AND_APPROVE → fix → verify → merge
        └── REQUEST_CHANGES → relabel → sweep re-dispatches
                │
                ▼ (on merge)
[Deploy Workflow] ─── triggers ─── agent-deploy.yml
        │
        ├── Detects changed services
        ├── Builds affected services
        ├── Verifies health checks
        ├── Auto-fixes failures (3 attempts)
        └── Posts deployment summary
                │
                ▼ (on merge)
[Design Validation] ─── triggers ─── agent-design-validation.yml
        │
        ├── Compares merged code vs spec
        ├── ALIGNED → done
        └── DEVIATION → creates correction issue → re-enters pipeline
```

---

## GitHub Integration

### Labels

| Label | Purpose |
|-------|---------|
| `agent:claude-code` | Dispatch to Claude Code coding agent |
| `agent:codex-cli` | Dispatch to Codex CLI coding agent |
| `status:ready` | Issue ready for agent pickup |
| `status:in-progress` | Agent working on issue |
| `status:in-review` | PR open, review pending |
| `status:pr-open` | PR exists for this issue |
| `status:merged` | PR merged |
| `status:done` | Issue complete |
| `status:blocked` | Blocked by dependency |
| `status:dead-letter` | Failed after max retries |
| `status:planning` | Parent issue (has sub-issues) |
| `needs-human` | Agent escalated to human |
| `complexity:S` | Small task (~100K tokens) |
| `complexity:M` | Medium task (~250K tokens) |
| `complexity:L` | Large task (~400K tokens) |
| `layer:cognitive` | AI/ML service layer |
| `layer:integration` | Gateway/orchestration layer |
| `layer:runtime` | Infrastructure layer |
| `layer:presentation` | UI layer |
| `layer:cross-cutting` | Spans multiple layers |

### GitHub Project Board

Status columns: **Backlog** → **Ready** → **In progress** → **In review** → **Done**

Auto-sync: labels map to project columns via `sync-project-status.sh`.

### Branch Naming

Agent branches: `agent/<issue-number>-<slug>`
Example: `agent/42-add-user-auth`

### Required Secrets

See `.env.example` for the complete list. Run `setup-github-secrets.sh` to provision.

---

## Slack Integration

### Channels

| Channel | Purpose | Events |
|---------|---------|--------|
| `#builds` | Build/deploy status | PR merged, CI pass/fail, deployments, stale PRs |
| `#issues` | Issue lifecycle | Created, closed, labeled, escalations, planning summaries |
| `#tokens` | Cost tracking | Budget alerts (80%+), daily activity digest |

### Notification Priority

| Priority | Treatment | Examples |
|----------|-----------|----------|
| Critical | Immediate + `@channel` | `needs-human` escalation, budget exceeded |
| Warning | Immediate | CI failure, budget at 80%, review cycle 3 |
| Info | Normal | Issue created, PR opened, status change |
| Digest | Daily summary | Token usage, stale PR report |

### Slack App Setup

1. Create a Slack App at https://api.slack.com/apps
2. Add Bot Token Scopes: `chat:write`, `chat:write.customize`
3. Install to workspace
4. Copy Bot User OAuth Access Token → `SLACK_BOT_USER_OAUTH_ACCESS_TOKEN`
5. Create channels, copy channel IDs → `SLACK_BUILD_CHANNEL`, etc.

---

## Self-Hosted Runner Setup

### Automated Setup

```bash
bash dream-maker/scripts/setup-runner.sh
```

This installs all required tools, creates directories, configures agent CLIs,
and optionally registers the GitHub Actions runner. See the script for
`--non-interactive` mode and environment variable overrides.

### Requirements

- Linux (Ubuntu 22.04+ recommended)
- GitHub Actions runner registered with label matching your `{{RUNNER_LABEL}}`

### Installed Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Docker + Compose | Latest | Build and deploy services |
| Node.js | v22 LTS | Agent CLI runtime, UI builds |
| pnpm | Latest | Node package manager |
| Go | 1.22+ | Go service builds |
| Python | 3.12+ | Python service builds, healthcheck |
| gh CLI | Latest | GitHub API operations |
| jq | Latest | JSON processing in workflows |
| Claude Code CLI | Latest | Primary coding/review agent |
| Codex CLI | Latest | Secondary coding agent |
| golangci-lint | Latest | Go linting |
| ruff | Latest | Python linting/formatting |
| mypy | Latest | Python type checking |
| uv | Latest | Python package manager |

### Runner Configuration Files

The `runner-config/` directory contains reference configs:

**`~/.claude/settings.json`** — Claude Code plugins and marketplace config:
```json
{
  "enabledPlugins": {
    "superpowers@claude-plugins-official": true,
    "code-review@claude-plugins-official": true,
    "commit-commands@claude-plugins-official": true,
    "feature-dev@claude-plugins-official": true,
    "security-guidance@claude-plugins-official": true
  }
}
```

**`~/.codex/config.toml`** — Codex CLI global config:
```toml
model = "gpt-5.4"

[projects."/home/runner"]
trust_level = "trusted"
```

### Token Log Directory Structure

Agent workflows write invocation logs to `~/dream-maker-logs/` (configurable).
Each agent type has its own subdirectory:

```
~/dream-maker-logs/
├── claude-code/          # Coding agent (Claude Code) invocations
│   └── 2026-03-16.jsonl  # One line per run
├── codex-cli/            # Coding agent (Codex CLI) invocations
├── planning-agent/       # Planning/decomposition runs
├── review-agent/         # PR review runs
├── validation-agent/     # Post-merge design validation
├── deployment-agent/     # Deploy fix attempts
├── roadmap-progress/     # Cognitive roadmap scoring
└── summaries/            # Daily aggregated summaries
```

**Log format** (one JSON line per invocation):
```json
{
  "timestamp": "2026-03-16T22:56:38Z",
  "agent": "claude-code",
  "tokens_used": 1729557,
  "cost_usd": 1.71,
  "issue": "225",
  "run_id": "23169536672",
  "status": "success"
}
```

Budget checks count invocations (lines) per day to enforce daily limits.
Token tracking aggregates these logs for daily Slack summaries.

### Post-Setup Authentication

After running `setup-runner.sh`:

```bash
gh auth login              # GitHub CLI — required
claude auth                # Claude Code — required for coding/review agents
export OPENAI_API_KEY=...  # Codex CLI — required if using Codex agent
```

---

## Healthcheck System

The pipeline includes a Python-based health monitoring system that runs every
5 minutes and checks 25+ health criteria across 7 categories:

| Category | Checks | What It Monitors |
|----------|--------|-----------------|
| Runner (R) | R1-R3 | Self-hosted runner online, disk space, agent CLIs |
| Dispatch (D) | D1-D5 | Recent dispatch success, no skipped steps, queue depth |
| Sweep (S) | S1-S4 | Sweep running, stale issue detection, chain restarts |
| Review (V) | V1-V5 | Review running, no stuck PRs, merge success |
| Notifications (N) | N1-N2 | Slack notifications firing, no silent failures |
| Budget (B) | B1-B3 | Under daily limits, token tracking running |
| Cross-cutting (X) | X1-X4 | Workflow YAML valid, no concurrent conflicts |

**Self-healing actions** (rate-guarded):
- Trigger dispatch when ready issues have no active dispatch
- Reset stale in-progress issues (stuck 2+ hours)
- Retry merge on approved but unmerged PRs
- Cancel stuck workflow runs (>90 minutes)

---

## Customization Guide

### Adapting for your tech stack

1. **Edit `.claude/rules/`** — add rules for your languages/frameworks
2. **Edit `coding-agent/hooks/`** — add post-edit hooks for your formatters
3. **Edit `pr-checks.yml`** — add/modify CI checks for your build system
4. **Edit `coding-agent/config/`** — adjust allowed/denied CLI commands

### Adapting for your workflow

1. **Edit `RESPONSIBILITY_MATRIX.md`** — adjust agent roles and limits
2. **Edit `delivery-manager/prompts/planning-agent.md`** — customize decomposition rules
3. **Edit `review-agent/prompts/review-prompt.md`** — customize review criteria
4. **Edit `agent-slack-notify.yml`** — customize notification routing

### Removing agents you don't need

Each agent is modular. To remove one:
1. Delete its directory
2. Remove its workflow from `.github/workflows/`
3. Remove its entries from `RESPONSIBILITY_MATRIX.md`
4. Update `AGENTS.md` to remove references

### Adding new agents

1. Create `<agent-name>/AGENTS.md` with operating handbook
2. Add prompts in `<agent-name>/prompts/`
3. Create a workflow in `.github/workflows/agent-<name>.yml`
4. Register in `RESPONSIBILITY_MATRIX.md`
5. Add Slack routing if needed

---

## Safety Mechanisms

| Mechanism | Purpose |
|-----------|---------|
| **Directory conflict detection** | Prevents two agents from editing the same service simultaneously |
| **Dependency checking** | Issues aren't dispatched until dependencies are closed |
| **Daily budget limits** | Caps agent invocations per day to control costs |
| **Review cycle limit** | Escalates to human after 3 review rounds |
| **Deployment retry limit** | Escalates after 3 failed fix attempts |
| **Concurrency groups** | Prevents duplicate workflow runs from rapid events |
| **GITHUB_TOKEN anti-recursion** | PRs created by agents don't trigger infinite loops |
| **Dispatch sweep** | Hourly safety net catches stuck or orphaned work |
| **Pipeline health checks** | 5-minute monitoring with self-healing |
| **Rate-guarded remediation** | Self-healing actions rate-limited to prevent cascading |

---

*Dream Maker v1.0 — extracted from the Kite Platform agent workforce*
