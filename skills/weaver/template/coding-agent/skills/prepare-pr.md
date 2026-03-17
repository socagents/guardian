# Skill: Prepare PR

## Purpose

Prepare all evidence and artifacts needed for a clean PR submission. This skill is
typically the last step before the CI workflow creates the PR.

## When to Use

- You have finished implementing and testing your changes
- You need to produce the final evidence package
- The CI workflow will use your output to create the PR

## Expected Inputs

- Completed implementation in the workspace
- Test results from local checks
- The original GitHub Issue for context

## Execution Steps

### Phase 1 — Verify Completeness

1. Re-read the GitHub Issue acceptance criteria.
2. For each criterion, confirm it is satisfied by your implementation.
3. If any criterion cannot be verified, note it explicitly.

### Phase 2 — Run Final Checks

4. Run the full suite of local checks one final time:
   - Build
   - Lint / format
   - Type checks
   - Tests
5. Ensure everything passes. If anything fails, fix it before proceeding.

### Phase 3 — Generate Evidence

6. Produce the Evidence Contract output (see `coding-agent/AGENTS.md`):
   - Summary of changes
   - Files modified (with brief descriptions)
   - Tests and checks executed (with pass/fail)
   - UI notes (if applicable)
   - Known limitations
   - Follow-up items

7. If helper scripts are available, use them:
   - `coding-agent/scripts/summarize-changes.sh` — generates file change summary
   - `coding-agent/scripts/collect-test-results.sh` — captures test output
   - `coding-agent/scripts/generate-pr-summary.sh` — creates PR description

### Phase 4 — Final Output

8. Your final output should be a clean, structured evidence block that the
   review agent can evaluate. The CI workflow will:
   - Commit your changes
   - Create the PR with a description derived from the issue
   - Trigger the review workflow

## Expected Outputs

- All local checks passing
- Structured evidence summary in your final output
- Workspace in a clean state (no temporary or debug files left behind)
