---
name: smoke-test
description: Use when verifying that an {{PROJECT_NAME}} change deployed correctly and the most important user-facing or system-critical flows still work. Covers focused smoke testing after CI/CD runs, merges, and releases.
---

# Smoke Test

Use this skill after deployment, before release signoff, or when validating that a merged change did not break core flows.

## Goal
Run a short, high-signal verification pass that confirms the system is alive and the main path still works.

## What A Smoke Test Is
A smoke test is not a full regression suite. It is a focused validation of the most critical workflows and failure signals.

## Minimum Workflow
1. Identify the environment to test.
2. Confirm the expected version, branch, or deployment is live.
3. Run the smallest set of checks that prove the main flow works.
4. Capture pass, fail, or blocked status.
5. If a failure appears, stop broad testing and log the failure clearly.

## Default Smoke Test Areas
Pick the relevant subset for the change:
- application is reachable
- authentication or access path works
- primary user journey completes
- critical API endpoint responds successfully
- obvious error states are absent
- logs, health checks, or deployment status show no immediate incident

## Reporting
Record:
- environment tested
- version or PR under test
- scenarios checked
- result for each scenario
- blockers, failures, or confidence limits

## Failure Handling
- If a core path fails, treat the release or deploy as suspect.
- Report the smallest reproducible failure.
- Distinguish between code defect, deploy defect, config defect, and environment outage when possible.

## Scope Discipline
- Keep smoke tests short.
- Prefer 3 to 7 high-value checks over broad exploratory work.
- If deeper coverage is needed, recommend a broader functional or regression pass instead of expanding the smoke test indefinitely.

## Relation To CI/CD
Smoke tests complement CI. A green pipeline does not replace a smoke test for user-visible or environment-specific risk.

## Repo-Specific Notes
- Use this skill after merges that trigger deployment.
- Use this skill before marking release-critical work as complete.
- If there is no deployed environment yet, record that smoke testing is blocked by missing infrastructure.
