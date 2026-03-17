# Skill: Fix Review Comments

## Purpose

Address review feedback on an existing PR. The review agent (or a human reviewer) has
requested changes. This skill guides you through understanding, applying, and verifying
the requested fixes.

## When to Use

- A PR you worked on received a "Changes Requested" review
- The review agent posted feedback comments on the PR
- You are re-dispatched to the same issue after a review cycle
  (the review workflow relabels the issue to `status:ready`, and the
  dispatch sweep re-triggers you automatically)

## Expected Inputs

- GitHub Issue number (same as the original task)
- PR number with review comments
- Review feedback (in PR comments or review body)

## Execution Steps

### Phase 1 — Understand the Feedback

1. Read the review comments on the PR carefully. For each comment:
   - Identify what specific change is requested
   - Understand why the reviewer flagged it
   - Determine if it is within the original issue scope

2. Re-read the original GitHub Issue and linked specs to confirm the
   reviewer's feedback aligns with the acceptance criteria.

3. If any feedback is unclear or seems to conflict with the spec:
   - Add a reply on the specific PR comment asking for clarification
   - Stop and wait — do not guess what the reviewer meant

### Phase 2 — Apply Fixes

4. For each actionable review comment:
   - Make the requested change
   - If the fix requires modifying tests, update them
   - Keep changes scoped to the review feedback only

5. Do NOT introduce new features or refactoring beyond what the
   review requested. The goal is to resolve the review, not expand scope.

### Phase 3 — Verify

6. Run the same local checks as the original implementation:
   - Build, lint, type checks, tests
   - Ensure nothing regressed

### Phase 4 — Evidence

7. Produce an updated Evidence Contract output that includes:
   - Which review comments were addressed
   - What changed in response to each
   - Updated test results

## Expected Outputs

- Modified files addressing each review comment
- All local checks still passing
- Updated evidence summary referencing the review feedback
