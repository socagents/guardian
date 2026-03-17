# Skill: Add Playwright Test

## Purpose

Add browser-based end-to-end tests using Playwright. Use this when the issue involves
UI changes or when acceptance criteria require verifying browser behavior.

## When to Use

- The GitHub Issue involves UI or frontend changes
- Acceptance criteria require browser-level verification
- A review requested E2E test coverage for a UI feature

## Expected Inputs

- UI feature or page to test (from the issue)
- Running application accessible on the local host
- Playwright installed on the host machine

## Execution Steps

### Phase 1 — Assess

1. Identify what needs browser-level testing:
   - User flows described in the issue or spec
   - UI components that were created or modified
   - Interactive behavior (forms, navigation, state changes)

2. Check the project's existing Playwright setup:
   - Config file (`playwright.config.ts` or `playwright.config.js`)
   - Existing E2E test files and their location
   - Base URL and test server configuration
   - If no Playwright setup exists, create a minimal config

### Phase 2 — Write Tests

3. Create test files following the project's E2E conventions:
   - Use descriptive `test.describe` and `test` blocks
   - Test user-visible behavior, not implementation details
   - Use accessible selectors (roles, labels, text) over CSS selectors

4. For each test scenario:
   - Navigate to the relevant page
   - Perform the user action
   - Assert the expected outcome (visible text, URL change, element state)
   - Clean up any test data if needed

5. Keep tests reliable:
   - Wait for elements to be visible before interacting
   - Use Playwright's auto-waiting where possible
   - Avoid hard-coded timeouts (use `waitForSelector` or `expect` with timeout)
   - Make tests independent — no shared state between tests

### Phase 3 — Verify

6. Run the Playwright tests locally:
   - Start the application if not already running
   - Execute: `npx playwright test <test-file>`
   - If tests fail, fix them before proceeding
   - Run in headed mode for debugging if needed: `npx playwright test --headed`

7. If the project has screenshot or visual comparison tests, update
   snapshots as needed.

### Phase 4 — Evidence

8. In your evidence output, include:
   - List of E2E test files created or modified
   - Test commands executed and results
   - Any screenshots taken during testing (if applicable)
   - Note if the test requires a running application server

## Expected Outputs

- Playwright test files following project conventions
- All E2E tests passing locally
- Evidence of test execution in your output

## Notes

- Playwright tests run locally on the host machine
- The application must be accessible (typically localhost) during test execution
- If Playwright is not installed, run: `npx playwright install --with-deps`
