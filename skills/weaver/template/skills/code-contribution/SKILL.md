---
name: code-contribution
description: Use when contributing code in the {{PROJECT_NAME}} repo. Covers the required workflow for branch creation, implementation, commit hygiene, push, pull request handling, waiting for merge, and monitoring GitHub Actions until build and deploy status are known.
---

# Code Contribution

Use this skill for any implementation task in the `{{PROJECT_NAME}}` repository.

## Goal
Ship changes through the repository workflow without bypassing GitHub controls.

## Required Workflow
1. Confirm the task is tied to an issue, milestone, or clearly stated scoped request.
2. Sync with the current default branch state before starting work.
3. Create or switch to a dedicated branch for the task.
4. Make only the requested change set.
5. Verify the local result if local checks exist.
6. Commit in small, understandable units.
7. Push the branch to origin.
8. Open or update a pull request.
9. Monitor GitHub Actions for build, test, and deploy outcomes.
10. Do not consider the task complete until the required checks have passed or a failure is documented.

## Branch Rules
- Never commit directly to `main`.
- One branch should map to one feature, fix, or narrowly scoped workstream.
- If unrelated work is discovered, open a follow-up issue instead of widening the branch scope.

## Commit Rules
- Keep commits small and reviewable.
- Commit messages should explain intent, not just files changed.
- Do not mix refactors, bug fixes, workflow changes, and feature work in one commit unless they are inseparable.

## Pull Request Rules
- Link the PR to the relevant issue when possible.
- Summarize the user-visible change, technical change, and any risks.
- Call out missing tests, missing secrets, or missing environment dependencies explicitly.
- If the PR is not ready, keep it as draft.

## Actions Monitoring
Treat GitHub Actions as authoritative.

Check for:
- lint success
- test success
- build success
- deploy success if deployment is part of the workflow

If a workflow fails:
- inspect the failing job
- identify whether the problem is code, configuration, secrets, environment, or external dependency
- fix it if within scope
- otherwise report the blocker clearly

## Merge Behavior
- Wait for required checks and required approvals.
- Do not self-approve around branch rules.
- After merge, verify the final post-merge workflow state if the repo deploys from `main`.

## Completion Criteria
The task is complete only when all of the following are true:
- code is pushed
- pull request is created or updated
- required checks are green, or a blocker is recorded
- deploy result is known if applicable
- smoke test is queued or completed when release risk justifies it

## When To Use Other Resources
- Use [smoke-test](skills/smoke-test/SKILL.md) after deployment or before release confidence is needed.

## Repo-Specific Notes
- The repo may be administered by Codex while planning and review may be driven by Claude Code.
- If role boundaries conflict with branch protections or GitHub permissions, escalate instead of working around them.
