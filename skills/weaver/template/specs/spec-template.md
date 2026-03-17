# [Feature Name]

> **Status:** Draft | Ready for Review | Approved
> **Author:** [name or agent]
> **Created:** YYYY-MM-DD
> **Last Updated:** YYYY-MM-DD

## 1. Summary

<!-- 2-3 sentences describing the feature at a high level. -->
<!-- A reader should understand what this spec is about after reading only this section. -->

## 2. Problem

<!-- What problem does this feature solve? Who experiences the problem? -->
<!-- Why is the current state insufficient? -->

## 3. Goals

<!-- What does success look like? List concrete, measurable outcomes. -->

- Goal 1
- Goal 2

## 4. Non-Goals

<!-- What is explicitly excluded from this feature? -->
<!-- Non-Goals prevent scope creep. Be specific about adjacent features you will NOT build. -->

- Non-Goal 1
- Non-Goal 2

## 5. User / System Flow

<!-- How does the feature work end to end? -->
<!-- Use numbered steps, a sequence diagram, or a flowchart. -->
<!-- Show the happy path first, then variations and error paths. -->

1. Step 1
2. Step 2
3. Step 3

## 6. Functional Requirements

<!-- Detailed, numbered requirements. Each requirement should be independently testable. -->
<!-- Group by subsystem or concern if the list is long. -->

### 6.1 [Subsystem or Concern A]

- **FR-1**: [Requirement description]
- **FR-2**: [Requirement description]

### 6.2 [Subsystem or Concern B]

- **FR-3**: [Requirement description]
- **FR-4**: [Requirement description]

## 7. UI / UX Notes

<!-- Design and interaction notes, if applicable. -->
<!-- Include wireframes, mockups, or layout descriptions. -->
<!-- Remove this section if the feature has no user-facing interface. -->

## 8. Acceptance Criteria

<!-- Testable conditions for this feature to be considered complete. -->
<!-- Each criterion must be verifiable — avoid vague language like "works correctly". -->

- [ ] Criterion 1 — [specific, testable condition]
- [ ] Criterion 2 — [specific, testable condition]
- [ ] Criterion 3 — [specific, testable condition]

## 9. Work Breakdown Candidates

<!-- Suggested decomposition into implementation tasks. -->
<!-- The Delivery Manager uses this to create GitHub Issues. -->
<!-- Each candidate should be independently implementable. -->

| # | Task | Layer | Est. Complexity | Dependencies |
|---|------|-------|----------------|--------------|
| 1 | [Task description] | [layer] | S / M / L / XL | — |
| 2 | [Task description] | [layer] | S / M / L / XL | Task 1 |
| 3 | [Task description] | [layer] | S / M / L / XL | — |

Layer values: `cognitive`, `integration`, `runtime`, `presentation`, `cross-cutting`

Complexity guide:
- **S** (~100K tokens): Simple changes, config, docs — 1-3 files
- **M** (~250K tokens): One module or service component — 3-8 files
- **L** (~400K tokens): Multiple components with tests — 8-15 files
- **XL** (~500K tokens): Cross-service integration — 15+ files

## 10. Dependencies

<!-- Other specs, services, or systems this feature depends on. -->
<!-- Reference spec files by path. -->

| Dependency | Type | Notes |
|-----------|------|-------|
| `specs/other-spec.md` | Spec | Must be implemented before this feature |
| Service X API | External | Required for integration |

## 11. Risks / Edge Cases

<!-- Known risks, failure modes, and edge cases. -->
<!-- Include mitigation strategies where possible. -->

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| [Risk description] | Low / Med / High | Low / Med / High | [Mitigation strategy] |

## 12. Testing / Verification Notes

<!-- How should the implementation be verified? -->
<!-- What types of tests are needed? What test data or fixtures are required? -->
<!-- Include any special testing considerations (external services, timing, etc.). -->

- Unit tests: [what to cover]
- Integration tests: [what to cover]
- Manual verification: [steps, if applicable]

## 13. Open Questions

<!-- Unresolved design decisions. -->
<!-- The Delivery Manager creates Project draft items from these. -->
<!-- Remove this section once all questions are resolved. -->

| # | Question | Context | Resolution |
|---|----------|---------|------------|
| 1 | [Question] | [Why this matters] | Pending |
| 2 | [Question] | [Why this matters] | Pending |

---

<!-- Companion specs: list related spec files for cross-reference -->
<!-- Example: specs/api-gateway-routing.md, specs/contracts-spec.md -->
