# Spec Readiness Checklist

> Run through this checklist before marking a spec as **Approved**.
> Every item must pass before handoff to the Delivery Manager.

## Required Sections

- [ ] **Title** is a clear, descriptive feature name (not generic)
- [ ] **Summary** is 2-3 sentences that convey what, why, and how
- [ ] **Problem** describes who has the problem and why current state is insufficient
- [ ] **Goals** list concrete, measurable outcomes
- [ ] **Non-Goals** explicitly exclude adjacent features or scope
- [ ] **Functional Requirements** are numbered (FR-1, FR-2, etc.) and testable
- [ ] **Acceptance Criteria** use checkbox format with specific, verifiable conditions

## Recommended Sections

- [ ] **User / System Flow** shows the end-to-end happy path
- [ ] **Work Breakdown Candidates** suggest task decomposition with layers and complexity
- [ ] **Dependencies** list blocking and non-blocking dependencies
- [ ] **Risks / Edge Cases** identify failure modes with mitigations
- [ ] **Testing / Verification Notes** describe how to verify the implementation

## Quality Checks

### Requirements Quality

- [ ] Each functional requirement is independently testable
- [ ] Requirements do not contain implementation instructions (no "use library X" or "implement with pattern Y")
- [ ] Error cases and edge cases are covered in requirements
- [ ] Data formats and schemas are specified where applicable (in code blocks)
- [ ] Requirements are grouped by subsystem when the list exceeds 10 items

### Acceptance Criteria Quality

- [ ] No vague criteria (no "works correctly", "is fast", "handles errors")
- [ ] Each criterion specifies inputs and expected outputs where applicable
- [ ] Negative cases are included (what should NOT happen)
- [ ] Every criterion maps to at least one functional requirement

### Scope Quality

- [ ] Spec covers a single feature (not multiple independent features)
- [ ] Non-Goals are specific enough to prevent scope creep during implementation
- [ ] Work Breakdown tasks are each completable in a single agent session
- [ ] No task in the breakdown exceeds XL complexity (~500K tokens)

### Cross-Reference Quality

- [ ] Related specs are referenced by file path
- [ ] Dependencies reference specific specs or services
- [ ] No circular dependencies with other specs

### Open Questions

- [ ] All open questions include context on why they matter
- [ ] Questions that have been resolved are removed from the Open Questions section and the resolution is reflected in the relevant spec section
- [ ] Remaining open questions do not block implementation of the core feature

## Header Status

- [ ] Status line is set to **Approved** (or **Ready for Review** if awaiting human sign-off)
- [ ] Author and date fields are filled in
- [ ] Last Updated date reflects the most recent change

## Final Check

- [ ] Read the spec from top to bottom as if you have never seen it before — does it make sense?
- [ ] Could the Delivery Manager create issues from this spec without asking clarifying questions?
- [ ] Could a coding agent understand the design intent from this spec?
