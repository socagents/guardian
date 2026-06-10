# Skill: Add Tests

## Purpose

Add test coverage for existing code. Use this when the issue specifically requests
adding tests, or when you identify that existing code lacks adequate coverage.

## When to Use

- The GitHub Issue explicitly asks for test coverage
- You implemented code and need to add tests (step 7 of the execution workflow)
- A review requested additional test coverage

## Expected Inputs

- Target code paths to test (from the issue or your implementation)
- The project's existing test framework and conventions

## Execution Steps

### Phase 1 — Assess

1. Identify the code paths that need test coverage:
   - New functions/methods you implemented
   - Edge cases mentioned in the spec or acceptance criteria
   - Error handling paths

2. Examine existing tests in the project to understand:
   - Test framework used (pytest, go test, vitest, jest, etc.)
   - File naming conventions (e.g., `*_test.go`, `*.test.ts`, `test_*.py`)
   - Test organization (colocated vs. separate test directory)
   - Common patterns (fixtures, mocks, helpers)
   - How to run tests locally

### Phase 2 — Write Tests

3. Create or update test files following the project's conventions.

4. For each test, cover:
   - **Happy path**: expected inputs produce expected outputs
   - **Edge cases**: boundary values, empty inputs, missing fields
   - **Error cases**: invalid inputs, expected failures, error messages
   - **Integration points**: if the code interacts with other modules, test
     that interaction (with mocks if needed)

5. Keep tests focused and readable:
   - One logical assertion per test (or a small, related group)
   - Descriptive test names that explain what is being verified
   - Use the Arrange-Act-Assert pattern

### Phase 3 — Verify

6. Run the full test suite to confirm:
   - New tests pass
   - Existing tests still pass (no regressions)
   - If the project has coverage reporting, check the coverage increase

### Phase 4 — Evidence

7. In your evidence output, include:
   - List of test files created or modified
   - Test commands executed and results
   - Coverage numbers if available

## Expected Outputs

- Test files following project conventions
- All tests passing (new and existing)
- Evidence of test execution in your output
