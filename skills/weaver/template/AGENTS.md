# {{PROJECT_NAME}} — Agent Instructions

## Project Overview

{{PROJECT_NAME}} is a microservices platform for AI agent orchestration — managing sessions,
tool execution, memory, plugins, and multi-channel UI. The platform spans Go,
Python, and TypeScript services coordinated through gRPC contracts.

This repository (`{{GITHUB_ORG}}/{{GITHUB_REPO}}`) hosts both the agent workforce that
builds {{PROJECT_NAME}} and the platform source code itself.

## Architecture

Nine services across five layers:

| Service | Layer | Language | Purpose |
|---------|-------|----------|---------|
| `api-gateway` | Integration | Go | HTTP/gRPC gateway, request routing, auth |
| `control-plane` | Integration | Go | Session orchestration, agent lifecycle |
| `tool-execution` | Integration | Go | Sandboxed tool runner |
| `plugin-runner` | Integration | Go | Plugin lifecycle management |
| `agent-runtime` | Cognitive | Python | LLM agent execution, tool calling |
| `memory-service` | Cognitive | Python | Vector storage with LanceDB |
| `automation-service` | Runtime | Go | Workflow automation engine |
| `media-service` | Runtime | Go | File processing pipeline |
| `ui` | Presentation | TypeScript | Next.js web interface |

All inter-service communication uses gRPC. Contracts live in `contracts/`.

## Repository Structure

```
contracts/              Proto/gRPC service contracts (buf-managed)
services/               Platform microservices (one dir per service)
specs/                  Spec conventions and templates
coding-agent/           Coding agent handbooks, skills, scripts, config
pilot-agent/            Pilot agent handbook and docs (design + pipeline ops)
delivery-manager/       Delivery manager handbook, templates, scripts
review-agent/           Review agent prompts and docs
deployment-agent/       Deployment agent handbook, prompts, scripts, config
.github/workflows/      CI/CD and agent orchestration workflows
.github/ISSUE_TEMPLATE/ Issue templates for agent tasks and features
.claude/rules/          Path-scoped coding rules (auto-loaded by Claude Code)
```

## Build & Test Commands

### Go Services (`services/api-gateway/`, `services/control-plane/`, etc.)

```bash
go build ./...                    # Build
go test ./... -race               # Test with race detection
golangci-lint run                 # Lint
```

### Python Services (`services/agent-runtime/`, `services/memory-service/`)

```bash
uv sync                          # Install dependencies
pytest                            # Test
ruff check . && ruff format .     # Lint and format
mypy .                            # Type check
```

### TypeScript UI (`services/ui/`)

```bash
pnpm install                      # Install dependencies
pnpm build                        # Build
pnpm test                         # Test (Vitest)
pnpm lint                         # Lint (ESLint)
npx playwright test               # E2E tests
```

### Proto Contracts (`contracts/`)

```bash
buf lint                          # Lint proto files
buf generate                      # Generate code from protos
buf breaking --against .git#branch=main  # Check backwards compatibility
```

## Coding Standards

- **Strict typing everywhere**: Go strict error handling, Python type hints + mypy,
  TypeScript strict mode. No `any`, no untyped exceptions.
- **File size**: keep files under ~500 LOC. Split when complexity grows.
- **Error handling**: Go — wrap errors with `fmt.Errorf("context: %w", err)`.
  Python — typed exceptions. TypeScript — explicit error boundaries.
- **Testing**: Go table-driven tests. Python pytest with fixtures. TypeScript Vitest
  unit + Playwright E2E. Target 80%+ coverage on new code.
- **Comments**: brief comments for non-obvious logic only. Code should be self-documenting.
- **Naming**: Go — PascalCase exports, camelCase internal. Python — snake_case.
  TypeScript — camelCase variables, PascalCase components/types.

## Spec References

**Implementation specs** (used by agents) live in `specs/` in this repo.
Always read the spec referenced in your issue before implementing.

**Architecture specs** (read-only background context) live in the
[research repository](https://github.com/{{GITHUB_ORG}}/research) under `kite/`:

| Spec | Covers |
|------|--------|
| `replication-plan.md` | 10-stage build plan and milestones |
| `deployment-architecture.md` | Service inventory and boundaries |
| `contracts-spec.md` | gRPC/proto contracts and versioning |
| `workforce-orchestration.md` | Agent roles, task lifecycle, coordination |
| `agent-interaction-protocol.md` | Communication format, handoff patterns |
| `cicd-agent-integration.md` | GitHub Actions workflow details |

These research specs are background references — do not confuse them with the
`specs/` files in this repo, which are the ones linked in GitHub Issues.

## Agent Coordination

- **Spec-driven**: read all referenced specs before writing code or creating designs.
- **Issue-scoped**: work only on the assigned GitHub Issue. Do not expand scope.
- **Evidence-based**: leave structured output (summary, files modified, test results,
  known limitations) so the review agent can evaluate your work.
- **No direct agent communication**: coordinate through GitHub Issues, PRs, and labels.
- **Escalate when blocked**: add a comment on the issue and apply `needs-human` label.
  Do not guess scope or make architecture decisions not covered by specs.

## Boundaries

**Always do:**
- Read the issue and linked specs before starting
- Follow existing code patterns and conventions
- Run lint, type checks, and tests before finishing
- Leave structured evidence of your work

**Ask first / escalate:**
- Architecture decisions not covered by specs
- Installing new dependencies not in the issue
- Changes affecting multiple services or layers
- Security-sensitive modifications

**Never do:**
- Modify spec or design documents (read-only references — except the Pilot Agent,
  which authors and commits specs)
- Modify CI/CD workflow files (managed by operators) —
  **exception:** the Pilot Agent may update workflows when directed by the human operator
- Run `git commit`, `git push`, or `gh pr create` (CI handles git operations) —
  **exception:** the Pilot Agent may commit and push approved specs (`specs/`)
  and pilot-agent docs to complete the handoff to the Delivery Manager
- Refactor code outside the task scope
- Create new GitHub Issues or modify other agents' work
