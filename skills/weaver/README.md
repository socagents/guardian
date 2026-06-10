# WEAVER

Weaver packages the Dream Maker skill: a turnkey agentic CI/CD system that turns approved specs into planned issues, implemented code, reviewed pull requests, and deployment-ready changes.

At its core, Weaver is a reusable setup bundle for teams that want a spec-driven software pipeline run by coordinated AI agents instead of a single coding assistant. The skill gathers project and runner details, provisions the repository, installs the agent tooling on a self-hosted runner, wires up GitHub Actions workflows, and leaves behind a working template where humans write specs and the agent workforce handles delivery.

## What Weaver Sets Up

- Five coordinated agent roles: Pilot, Planning, Coding, Review, and Deployment.
- A spec-driven workflow where committed specs are decomposed into GitHub issues and dispatched automatically.
- A self-hosted runner setup for Claude Code, Codex CLI, GitHub CLI, Docker, and supporting tools.
- Slack notifications for builds, issue flow, and token usage.
- Pipeline health monitoring, self-healing checks, and budget guardrails.

## Repository Contents

```txt
SKILL.md         Interactive setup skill and operating flow
references/      Documentation describing the agent team and bundle structure
runner-config/   Runner-side reference configuration
scripts/         Repository bootstrap, labels, and runner setup scripts
template/        Drop-in project template with workflows, agent docs, prompts, and scaffolds
```

## How the Skill Works

1. Collect project identity, runner access, tech stack, Slack, and budget limits.
2. Create or open the target GitHub repository.
3. Copy the bundled template into that repo and replace placeholders.
4. Create labels, provision secrets, and configure the self-hosted runner.
5. Verify the workflows and hand off a pipeline where specs drive implementation.

## Key Ideas Behind the Bundle

- `prepare the repo once, then let agents operate repeatedly`
- `keep project-specific scaffolding in template/, not in the skill logic`
- `separate human-written specs from agent execution responsibilities`
- `treat pipeline health as a first-class concern, not an afterthought`

## Intended Use

Weaver is the infrastructure layer for teams that want autonomous engineering inside GitHub. It is best suited for greenfield or heavily standardized repos where:

- specs are the source of truth for feature intent
- issues can be decomposed and chained automatically
- coding and review agents should work within strict operational guardrails
- a self-hosted runner is available for agent tooling

## Prerequisites

- GitHub access with permissions to create and administer repositories
- `gh` CLI installed and authenticated
- A Linux or Ubuntu self-hosted runner reachable over SSH
- Optional Slack workspace for notifications

## Next Step

This repository currently contains the skill package itself, not an initialized project tree. Use the bundled skill, scripts, and template to bootstrap a target project repository when you are ready to deploy the workflow.
