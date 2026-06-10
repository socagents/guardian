# Skill: Sync with Issue Spec

## Purpose

Ensure your implementation stays aligned with the linked spec as changes evolve.
Use this when a spec has been updated mid-task, or when you need to verify that your
work still satisfies the design intent described in the spec.

## When to Use

- The spec referenced by your GitHub Issue has been updated since you started
- A reviewer flags a spec-alignment concern
- You are unsure whether your implementation matches the spec's design intent
- Before producing your final evidence (as a pre-check)

## Expected Inputs

- GitHub Issue number (with spec file paths or links)
- Your current implementation in the workspace

## Execution Steps

### Phase 1 — Reload Spec

1. Re-read every spec file referenced in the GitHub Issue.
2. Identify any sections that have changed since your last read:
   - New requirements added
   - Requirements removed or relaxed
   - Contracts or interfaces modified
   - Boundary constraints updated

### Phase 2 — Compare

3. For each acceptance criterion in the issue:
   - Trace it to the relevant spec section
   - Confirm your implementation satisfies the spec's current intent
   - Note any mismatches (over-implementation, under-implementation, wrong approach)

4. For each contract or interface defined in the spec:
   - Verify your code implements it correctly
   - Check field names, types, error codes, and behavior match

### Phase 3 — Adjust

5. If mismatches are found:
   - Fix your implementation to match the current spec
   - If the spec change invalidates significant work, comment on the issue
     describing the conflict before proceeding
   - Update tests to reflect any changes

6. If no mismatches are found:
   - Record that sync check passed (include in evidence)

### Phase 4 — Evidence

7. In your evidence output, include:
   - Which spec files were re-read
   - Whether any drift was detected
   - What adjustments were made (if any)
   - Confirmation that implementation matches current spec

## Expected Outputs

- Implementation aligned with the latest version of all referenced specs
- Updated tests if the spec changed
- Sync status included in your evidence summary
