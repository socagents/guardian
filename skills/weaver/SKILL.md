---
name: dream-maker
description: "Set up a complete AI agent workforce that turns specs into deployed software. Use this skill whenever the user wants to: create a new project with AI agents, set up an agentic CI/CD pipeline, bootstrap a spec-driven development workflow, get a team of coding/review/deploy agents working on their project, or mentions 'dream maker'. This is a full turnkey setup — it creates the GitHub repo, installs all agent tools on a runner, configures Slack notifications, commits all workflow files, and leaves the user with a working pipeline where they just write specs and agents do the rest."
---

# Dream Maker

Set up a complete AI agent workforce from scratch. The user answers a few
questions, and you handle everything: create the repo, configure the runner,
provision secrets, commit all files, and verify the pipeline works.

## What Gets Created

A GitHub repository with:
- **5 AI agents** (Pilot, Planning, Coding, Review, Deployment) orchestrated through 12 GitHub Actions workflows
- **Spec-driven development** — write a spec, agents decompose it into issues, implement code, review PRs, deploy services
- **Slack notifications** across 3 channels (#builds, #issues, #tokens)
- **Pipeline health monitoring** with self-healing (25+ automated checks)
- **Budget tracking** with daily limits and cost alerts
- **Safety mechanisms** — directory conflict detection, dependency chains, review cycle limits, concurrency groups

## Prerequisites

Before starting, the user needs:
- A GitHub account with permissions to create repos
- `gh` CLI installed and authenticated locally
- A self-hosted runner machine (Linux/Ubuntu) accessible via SSH
- A Slack workspace (optional but recommended)

If they don't have these yet, help them understand what's needed before proceeding.

## Setup Flow

### Phase 1: Gather Information

Ask these questions one at a time. Provide sensible defaults where possible.

**Question 1 — Project identity:**
> What's your project called? And what GitHub org (or username) should I create the repo under?
>
> Examples: "Acme Platform" under "acme-dev", or "My App" under your GitHub username

Extract: `PROJECT_NAME`, `GITHUB_ORG`, `GITHUB_REPO` (suggest kebab-case of project name)

**Question 2 — Runner access:**
> Where is your self-hosted runner? I need SSH access to install the agent tools (Claude Code CLI, Codex CLI, Docker, etc.)
>
> Give me: hostname/IP, SSH port (default 22), username, and how to authenticate (password or key)

Extract: `RUNNER_HOST`, `RUNNER_PORT`, `RUNNER_USER`, `RUNNER_AUTH`

**Question 3 — Slack (optional):**
> Do you have a Slack workspace for notifications? If yes, I'll need:
> - Bot User OAuth Access Token (from a Slack App)
> - Channel IDs for #builds, #issues, and #tokens channels
>
> If you don't have this set up yet, I can skip it and you can add it later.

Extract: `SLACK_BOT_TOKEN`, `SLACK_BUILD_CHANNEL`, `SLACK_ISSUES_CHANNEL`, `SLACK_TOKENS_CHANNEL`

**Question 4 — Tech stack:**
> What languages/frameworks will your project use? This helps me configure the right coding rules and CI checks.
>
> Options: Go, Python, TypeScript/Next.js, Proto/gRPC, or a combination

Extract: `TECH_STACK` (list of languages)

**Question 5 — Daily budget limits:**
> How many requests per day should each agent type be allowed? This is a safety
> guardrail to prevent runaway costs — agents stop when they hit the limit.
>
> | Agent | What it does | Default |
> |-------|-------------|---------|
> | **Coding** | Issues dispatched per agent per day (Claude Code + Codex) | 100 |
> | **Review** | PR reviews per day | 100 |
> | **Planning** | Spec decomposition runs per day | 20 |
> | **Validation** | Design validation runs per day | 50 |
> | **Deploy** | Deployment runs per day | 100 |
>
> Just hit Enter to use the defaults, or give me custom numbers.

Extract: `LIMIT_CODING` (default: 100), `LIMIT_REVIEW` (default: 100),
`LIMIT_PLANNING` (default: 20), `LIMIT_VALIDATION` (default: 50),
`LIMIT_DEPLOY` (default: 100)

**Question 6 — Runner label:**
> What label should your GitHub Actions runner use? This identifies your runner in workflows.
>
> Default: `dream-maker`

Extract: `RUNNER_LABEL` (default: `dream-maker`)

### Phase 2: Create and Configure Repository

After gathering all answers, execute these steps. Announce each phase to the user.

#### 2.1 Create the GitHub repository

```bash
gh repo create {{GITHUB_ORG}}/{{GITHUB_REPO}} --private --clone
cd {{GITHUB_REPO}}
git checkout -b main
```

If the repo already exists, clone it instead:
```bash
gh repo clone {{GITHUB_ORG}}/{{GITHUB_REPO}}
cd {{GITHUB_REPO}}
```

#### 2.2 Initialize the repository using the bundled script

The `SKILL_DIR` variable refers to the directory containing this SKILL.md file.
All template files, scripts, and config are bundled inside this skill package.

Run the init script to copy template files, replace placeholders, and strip unused tech stack rules:

```bash
bash ${SKILL_DIR}/scripts/init-repo.sh \
  --project-name "${PROJECT_NAME}" \
  --github-org "${GITHUB_ORG}" \
  --github-repo "${GITHUB_REPO}" \
  --runner-label "${RUNNER_LABEL}" \
  --runner-user "${RUNNER_USER}" \
  --target-dir "$(pwd)" \
  --slack-workspace "${SLACK_WORKSPACE:-your-workspace}" \
  --slack-build-channel "${SLACK_BUILD_CHANNEL:-CHANGEME}" \
  --slack-issues-channel "${SLACK_ISSUES_CHANNEL:-CHANGEME}" \
  --slack-tokens-channel "${SLACK_TOKENS_CHANNEL:-CHANGEME}" \
  --tech-stack "${TECH_STACK}" \
  --limit-coding "${LIMIT_CODING:-100}" \
  --limit-review "${LIMIT_REVIEW:-100}" \
  --limit-planning "${LIMIT_PLANNING:-20}" \
  --limit-validation "${LIMIT_VALIDATION:-50}" \
  --limit-deploy "${LIMIT_DEPLOY:-100}"
```

#### 2.3 Create GitHub labels

```bash
bash ${SKILL_DIR}/scripts/create-labels.sh "${GITHUB_ORG}/${GITHUB_REPO}"
```

#### 2.4 Customize for tech stack (if needed)

The init script already removes unused `.claude/rules/` and `coding-agent/hooks/`
based on the tech stack. You may also want to:

- **Update `pr-checks.yml`** — remove CI jobs for unused languages
- **Update `CLAUDE.md`** — adjust build & test commands to match the user's stack

#### 2.5 Set up GitHub secrets

```bash
# PROJECT_PAT — they'll need to create this manually
echo "You'll need a GitHub PAT with 'repo' and 'project' scopes."
echo "Create one at: https://github.com/settings/tokens"
read -rp "Paste your PAT: " PROJECT_PAT

gh secret set PROJECT_PAT --repo "${GITHUB_ORG}/${GITHUB_REPO}" --body "$PROJECT_PAT"
```

For Slack (if configured):
```bash
gh secret set SLACK_BOT_USER_OAUTH_ACCESS_TOKEN \
  --repo "${GITHUB_ORG}/${GITHUB_REPO}" --env dev \
  --body "$SLACK_BOT_TOKEN"

gh secret set SLACK_BUILD_CHANNEL \
  --repo "${GITHUB_ORG}/${GITHUB_REPO}" --env dev \
  --body "$SLACK_BUILD_CHANNEL"

gh secret set SLACK_ISSUES_CHANNEL \
  --repo "${GITHUB_ORG}/${GITHUB_REPO}" --env dev \
  --body "$SLACK_ISSUES_CHANNEL"

gh secret set SLACK_TOKENS_CHANNEL \
  --repo "${GITHUB_ORG}/${GITHUB_REPO}" --env dev \
  --body "$SLACK_TOKENS_CHANNEL"
```

#### 2.6 Initial commit and push

```bash
git add -A
git commit -m "dream-maker: initialize agent workforce pipeline

Complete CI/CD pipeline with 5 AI agents, 12 workflows,
pipeline health monitoring, and Slack notifications.

Agents: Pilot, Planning, Coding, Review, Deployment
Workflows: dispatch, review, planning, deploy, health, slack, and more
"

git push -u origin main
```

### Phase 3: Configure the Runner

SSH to the runner and set everything up.

#### 3.1 Copy and run the setup script

```bash
# Copy setup files from the skill package to the runner
scp -P ${RUNNER_PORT} ${SKILL_DIR}/scripts/setup-runner.sh ${RUNNER_USER}@${RUNNER_HOST}:/tmp/
scp -P ${RUNNER_PORT} -r ${SKILL_DIR}/runner-config/ ${RUNNER_USER}@${RUNNER_HOST}:/tmp/

# Run setup (non-interactive with env vars)
ssh -p ${RUNNER_PORT} ${RUNNER_USER}@${RUNNER_HOST} \
  "GITHUB_RUNNER_URL=https://github.com/${GITHUB_ORG}/${GITHUB_REPO} \
   GITHUB_RUNNER_LABEL=${RUNNER_LABEL} \
   bash /tmp/setup-runner.sh"
```

The script will prompt for a runner registration token. Guide the user:
> Go to https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/settings/actions/runners/new
> and copy the registration token.

#### 3.2 Authenticate agent CLIs on the runner

```bash
ssh -p ${RUNNER_PORT} ${RUNNER_USER}@${RUNNER_HOST}

# Inside the runner:
gh auth login                # GitHub CLI
claude auth                  # Claude Code CLI
export OPENAI_API_KEY=...    # For Codex CLI (user provides key)
```

Walk the user through each authentication step.

#### 3.3 Verify the runner

```bash
ssh -p ${RUNNER_PORT} ${RUNNER_USER}@${RUNNER_HOST} \
  "claude --version && codex --version && gh auth status && docker --version"
```

### Phase 4: Verify the Pipeline

#### 4.1 Check runner is online

```bash
gh api repos/${GITHUB_ORG}/${GITHUB_REPO}/actions/runners \
  --jq '.runners[] | "\(.name) — \(.status)"'
```

#### 4.2 Create a test spec

Create a minimal spec to verify the full pipeline flow:

```bash
cat > specs/hello-world.md << 'EOF'
# Hello World Service

> **Status:** Approved
> **Author:** Dream Maker
> **Created:** $(date +%Y-%m-%d)

## 1. Summary

Create a minimal hello-world service that responds to HTTP requests.
This spec validates the Dream Maker pipeline is working end to end.

## 2. Problem

We need to verify the agent pipeline works correctly.

## 3. Goals

- Create a simple HTTP server that returns "Hello, World!"
- Verify all pipeline stages: planning → dispatch → code → review → deploy

## 4. Non-Goals

- Production readiness
- Authentication or authorization

## 5. User / System Flow

1. Client sends GET request to /hello
2. Server responds with "Hello, World!" and status 200

## 6. Functional Requirements

### 6.1 HTTP Server

- **FR-1**: Create an HTTP server listening on port 8080
- **FR-2**: Respond to GET /hello with "Hello, World!" and status 200
- **FR-3**: Respond to GET /health with status 200 for health checks

## 8. Acceptance Criteria

- [ ] Server starts and listens on port 8080
- [ ] GET /hello returns "Hello, World!" with status 200
- [ ] GET /health returns status 200

## 9. Work Breakdown Candidates

| # | Task | Layer | Est. Complexity | Dependencies |
|---|------|-------|-----------------|--------------|
| 1 | Create hello-world HTTP server | runtime | S | — |

EOF

git add specs/hello-world.md
git commit -m "spec: hello world (pipeline verification)"
git push
```

#### 4.3 Monitor the pipeline

```bash
# Watch for the planning workflow to start
gh run list --repo ${GITHUB_ORG}/${GITHUB_REPO} --limit 5

# Check if issues were created
gh issue list --repo ${GITHUB_ORG}/${GITHUB_REPO}
```

Tell the user:
> I've pushed a test spec. The planning agent should pick it up within a minute
> and create issues. Then the dispatch workflow will assign a coding agent.
> Watch the action runs and Slack channels — you should see the full pipeline
> in action within 10-15 minutes.

### Phase 5: Handoff

Present a summary to the user:

```
============================================
  Dream Maker Setup Complete!
============================================

Repository:  https://github.com/${GITHUB_ORG}/${GITHUB_REPO}
Runner:      ${RUNNER_HOST} (label: ${RUNNER_LABEL})
Slack:       ${SLACK_CONFIGURED ? "Connected" : "Not configured"}
Pipeline:    Test spec pushed — monitoring...

Your agent team is ready:
  - Pilot Agent: you (interactive, writes specs)
  - Planning Agent: decomposes specs → issues
  - Coding Agent: implements issues → PRs
  - Review Agent: reviews PRs → auto-merge
  - Deployment Agent: builds + deploys

Next steps:
  1. Watch the hello-world spec flow through the pipeline
  2. Write your first real spec: cp specs/spec-template.md specs/my-feature.md
  3. Push to main and let the agents build your dream

Docs:
  - AGENTS.md — how the agents work
  - RESPONSIBILITY_MATRIX.md — roles and Slack routing
  - HUMAN_ACTIONS.md — remaining setup items
  - specs/spec-template.md — spec authoring template
============================================
```

## Error Handling

Throughout the setup, things can go wrong. Handle these gracefully:

- **SSH connection fails**: Check hostname, port, credentials. Offer to try again.
- **gh CLI not authenticated**: Run `gh auth login` first.
- **Runner registration fails**: Token may be expired. Guide user to generate a new one.
- **Docker not available on runner**: The setup script installs it, but the user may need to log out and back in for group membership.
- **Claude CLI auth fails**: The user needs an Anthropic API key or Claude account.
- **GitHub repo already exists**: Clone instead of create. Ask before overwriting files.
- **Secrets already set**: `gh secret set` overwrites silently — this is fine.

## Important Notes

- Never store credentials in files or commit them. Use `gh secret set` and environment variables only.
- The self-hosted runner is a security-sensitive component — only the repo owner should have SSH access.
- If the user doesn't have a runner machine, suggest using a cloud VM (DigitalOcean, AWS EC2, etc.) with Ubuntu 22.04+.
- All agent workflows use `GITHUB_TOKEN` which is auto-provided — no extra setup needed for basic operations.
- The `PROJECT_PAT` is only needed for GitHub Project board operations. If they don't use Projects, it can be skipped.
