# Skill: Implement Issue

## Purpose

Full implementation workflow for a GitHub Issue. This is the primary skill for coding
agents and covers the complete cycle from reading the issue to leaving evidence.

## When to Use

- You are assigned a GitHub Issue to implement
- The issue has acceptance criteria and spec references
- This is new work (not a review fix or test-only task)

## Expected Inputs

- GitHub Issue number (from the dispatch context or task prompt)
- Repository with specs and codebase accessible in your workspace

## Execution Steps

### Phase 1 — Understand

1. Read the GitHub Issue body completely. Note:
   - Title and description
   - Acceptance criteria (usually a checklist)
   - Spec references (file paths or links)
   - Dependencies (other issues this depends on)
   - Implementation notes (if any)

2. Read every spec file referenced in the issue. For each spec, extract:
   - Relevant design decisions that affect your implementation
   - Contract definitions (APIs, data models, interfaces)
   - Boundary constraints (what this service/module should NOT do)
   - Testing requirements specific to this area

3. If anything is ambiguous or contradictory between the issue and specs:
   - Add a comment on the issue explaining the ambiguity
   - Stop and wait for clarification

### Phase 2 — Plan

4. List the concrete deliverables from the acceptance criteria.

5. Inspect the codebase to understand:
   - Where the new code should live (directory, module, package)
   - Existing patterns to follow (naming, structure, error handling)
   - Adjacent code that will interact with your changes
   - Existing tests that cover related functionality

6. Write a brief implementation plan (5-10 lines):
   - Which files to create or modify
   - In what order
   - Which tests to add

### Phase 3 — Implement

7. Implement the solution following these constraints:
   - Satisfy every acceptance criterion
   - Follow existing codebase conventions
   - Keep the change minimal — no unrequested features
   - Add comments only for non-obvious logic

8. Add or update tests:
   - Cover new behavior with unit tests
   - If integration tests are appropriate, add those too
   - Follow the project's existing test patterns

### Phase 3.5 — Pre-Commit Checklist

8b. Run through the Pre-Commit Checklist in `coding-agent/AGENTS.md` (or the
    equivalent handbook for your runtime). Verify every item before proceeding.
    This catches the most common review issues: missing tests, committed build
    artifacts, missing required directories, and formatting problems.

### Phase 4 — Verify

9. Run the project's local checks:
   - Build (if applicable)
   - Lint and format
   - Type checks
   - Tests (all relevant suites)
   - Fix any failures before proceeding

### Phase 5 — Evidence

10. Produce the Evidence Contract output (see `coding-agent/AGENTS.md`).

## Expected Outputs

- Modified/created source files in the workspace
- Tests covering new behavior
- All local checks passing
- Structured evidence summary in your final output
