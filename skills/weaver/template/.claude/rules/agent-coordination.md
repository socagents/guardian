# Agent Coordination Rules

These rules apply to all agents working in this repository.

## Task Discipline

- Work only on your assigned GitHub Issue. Do not expand scope.
- Read all linked spec references before writing code or designs.
- If the issue or spec is unclear, comment on the issue and stop.

## Evidence and Handoff

- Leave structured evidence: summary, files modified, test results, known limitations.
- The review agent evaluates your work based on this evidence.
- No direct agent communication — coordinate through GitHub Issues, PRs, and labels.

## Escalation

- Apply `needs-human` label when blocked by ambiguity, architecture gaps, or repeated failures.
- Do not make architecture decisions not covered by specs.
- Do not attempt workarounds that expand scope.

## Boundaries

- **`drafts/` is design-only.** Only the Pilot Agent may read or write files in
  `drafts/`. No other agent, workflow, script, or production code should reference
  anything in `drafts/`. Design research stays in drafts until the Pilot Agent
  promotes it to a spec in `specs/`.
- Spec and design documents are read-only references (for coding/review agents).
- CI/CD workflow files are managed by operators — do not modify.
  **Exception:** the Pilot Agent may update workflows when directed by the human operator.
- Git operations (`commit`, `push`, `pr create`) are handled by CI workflows,
  **except** the Pilot Agent may `commit` and `push` approved spec files
  (`specs/`) and pilot-agent documentation to complete the handoff to the
  Delivery Manager.
- Do not create issues, assign work, or modify other agents' output.

## Reference Documentation

- `HUMAN_ACTIONS.md` — setup and approval tasks requiring human intervention
- `RESPONSIBILITY_MATRIX.md` — agent roles, workflows, and invocation limits
- `healthcheck/pipeline-health-criteria.md` — automated pipeline health checks
- `AGENTS.md` — agent workforce overview and role descriptions
