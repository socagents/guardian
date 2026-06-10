# Contributing to {{PROJECT_NAME}}

This repository is the monorepo for the {{PROJECT_NAME}} and the agent workforce that builds it. Keep changes tightly scoped to the assigned GitHub Issue, follow the linked spec documents, and prefer the smallest viable implementation.

## Development Principles

- Read the GitHub Issue and every referenced spec before changing code.
- Work only inside the issue scope. Do not refactor unrelated code or change CI workflows.
- Follow existing patterns in the relevant service before creating new ones.
- Run the relevant build, lint, type-check, and test commands before opening or updating a PR.

## Local Development Setup

1. Install the core tooling:
   - `git`
   - `docker` with Docker Compose support
   - `make`
   - `go`
   - `python` 3.11+ and `uv`
   - `node` 20+ and `pnpm`
   - `buf`
   - `golangci-lint`
2. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

3. Start shared infrastructure:

   ```bash
   make up
   ```

4. Verify the stack is healthy:

   ```bash
   make verify
   ```

For a more detailed local workflow, see [docs/local-dev-guide.md](docs/local-dev-guide.md).

## Branch Naming

Use the standard branch format for agent and human implementation work:

```text
agent/<agent-id>/<issue>-<slug>
```

Examples:

- `agent/codex-cli/16-repo-docs`
- `agent/claude-code/42-memory-indexing`

Use a short, kebab-case slug that matches the issue intent.

## Commit Messages

Write concise, imperative commit messages. Prefer this format:

```text
<type>(<scope>): <summary>
```

Examples:

- `docs(repo): add contribution and local development guides`
- `feat(api-gateway): validate auth headers before routing`
- `fix(agent-runtime): handle empty tool results`

Recommended commit types are `docs`, `feat`, `fix`, `test`, `refactor`, and `chore`.

## Pull Request Workflow

### Agent-Generated PRs

- Delivery Manager or a human assigns an issue and applies the agent label.
- The dispatch workflow creates an isolated `agent/...` branch and opens the PR through CI.
- The coding agent implements the issue, runs local checks, and leaves structured evidence in its final output.
- The review agent evaluates the PR, requests changes or approves, and the automation pipeline handles merge when requirements are satisfied.

### Human-Authored PRs

- Create a branch using the same naming convention where practical.
- Link the GitHub Issue in the PR description.
- Reference the exact spec file and section used for implementation.
- Fill out the repository PR template completely, including acceptance criteria coverage and test results.
- Wait for required checks and review approval before merge.

## Before Opening or Updating a PR

Run the checks relevant to the files you changed.

### Repository Infrastructure

```bash
make up
make verify
```

### Go Services

```bash
go build ./...
go test ./... -race
golangci-lint run
```

### Python Services

```bash
uv sync --extra dev
pytest
ruff check .
ruff format --check .
mypy .
```

### TypeScript UI

```bash
pnpm install
pnpm lint
pnpm test
pnpm build
```

### Proto Contracts

```bash
buf lint
buf generate
```

If your change affects multiple areas, run the checks for each affected area. Do not open a PR with known failing local checks unless the issue is explicitly blocked and documented.

## PR Content Requirements

Every PR should include:

- The linked issue number
- The spec reference used for the implementation
- A short summary of what changed and why
- Acceptance criteria coverage
- Commands executed and whether they passed
- UI evidence when the UI changed, otherwise `N/A`
- Known limitations, otherwise `None`

The repository template in `.github/PULL_REQUEST_TEMPLATE.md` is the required format.

## Coordination and Escalation

- If the issue or spec is ambiguous, stop and ask for clarification on the issue.
- If you are blocked by missing infrastructure, secrets, or an architectural gap, document the blocker and apply `needs-human`.
- Do not install new dependencies or expand the architecture without explicit issue or spec support.
