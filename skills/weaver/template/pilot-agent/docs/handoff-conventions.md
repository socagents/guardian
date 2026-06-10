# Handoff Conventions — Pilot Agent to Delivery Manager

> How specs flow from the Pilot Agent to the Delivery Manager.
> This document defines what the Delivery Manager expects from completed specs.

## The Handoff Model

The handoff is file-based and asynchronous. There is no direct communication
between the Pilot Agent and the Delivery Manager.

```
Pilot Agent                    Delivery Manager
     |                               |
     |  writes spec                   |
     |  human approves                |
     |  commits & pushes to specs/    |
     |-----> committed spec --------->|
     |                                | reads spec
     |                                | creates parent issue
     |  monitors for new issues  <----|
     |  reports status to human       | creates sub-issues
     |                                | populates project board
     |                                |
```

The Pilot Agent commits and pushes approved specs to the `specs/` directory.
The push automatically triggers the Agent – Planning workflow (via `specs/**`
path filter). The Pilot Agent **must** then monitor the workflow run to
completion, verify that Issues were created, and report the results back to
the human. The handoff is not complete until this monitoring step succeeds.

## What the Delivery Manager Expects

### 1. File Location

Specs must be committed under `specs/` in the repository root:

```
specs/user-authentication.md
specs/api-gateway-routing.md
```

The Delivery Manager reads only from this directory. Specs placed
elsewhere will not be processed.

### 2. File Naming

Use lowercase with hyphens. The file name should describe the feature:

```
specs/<feature-name>.md
```

The Delivery Manager uses the file name in issue references:
`Spec: specs/user-authentication.md @ abc1234`

### 3. Required Sections

The Delivery Manager requires these sections to create issues:

| Section | Used For |
|---------|----------|
| Title | Parent issue title: `[Feature] <Title>` |
| Summary | Parent issue summary field |
| Goals | Parent issue scope description |
| Non-Goals | Parent issue out-of-scope field |
| Functional Requirements | Sub-issue scope and acceptance criteria |
| Acceptance Criteria | Both parent and sub-issue acceptance criteria |

Without these sections, the Delivery Manager cannot produce quality issues.

### 4. Recommended Sections

These sections improve issue quality but are not strictly required:

| Section | Used For |
|---------|----------|
| Work Breakdown Candidates | Starting point for sub-issue decomposition |
| Dependencies | Cross-issue dependency links |
| Risks / Edge Cases | Issue notes and edge case callouts |
| Testing / Verification Notes | Sub-issue deliverable expectations |
| Open Questions | Project draft items (not full issues) |

### 5. Spec Status

The spec header should include a status line:

```markdown
> **Status:** Draft | Ready for Review | Approved
```

The Delivery Manager processes specs with status **Approved** (or when
triggered manually for any status). Specs marked **Draft** are typically
not decomposed unless the human requests it.

### 6. Commit SHA

The Delivery Manager records the commit SHA of the spec version it used.
This creates traceability:

```
Spec: specs/user-authentication.md
Commit: abc1234def5678
```

If the spec changes after decomposition, the Delivery Manager may re-read
and update issues. But the original commit SHA is preserved for audit.

## What the Delivery Manager Does with Each Section

### Title → Parent Issue Title

The spec title becomes the parent issue title, prefixed with `[Feature]`:

```
Spec title: "User Authentication via OAuth 2.0"
Issue title: "[Feature] User Authentication via OAuth 2.0"
```

### Summary → Parent Issue Body

The summary goes into the parent issue's Summary field.

### Goals + Non-Goals → Parent Issue Scope

Goals become the parent issue's Scope section. Non-Goals become the
Out of Scope section.

### Functional Requirements → Sub-Issue Scope

Each requirement group (or individual requirements for small specs)
becomes one or more sub-issues. The Delivery Manager quotes the relevant
FR numbers in each sub-issue.

### Acceptance Criteria → Issue Acceptance Criteria

High-level criteria go to the parent issue. Specific criteria are
distributed to relevant sub-issues. The Delivery Manager maps each
criterion to the sub-issue responsible for satisfying it.

### Work Breakdown Candidates → Sub-Issue Decomposition

The Delivery Manager uses the work breakdown table as a starting point.
It may:

- Split large tasks further
- Merge small tasks
- Reorder based on dependencies
- Add tasks the spec did not anticipate (e.g., config, CI integration)

Do not assume the breakdown will be used verbatim. Provide it as guidance.

### Dependencies → Issue Dependencies

Spec-level dependencies become `depends on #N` references in issues.
The Delivery Manager also adds inter-issue dependencies based on the
work breakdown order.

### Open Questions → Project Draft Items

Unresolved questions become draft items on the GitHub Project board
(not full repository issues). They are tagged with `design-gap` and
reference the parent issue.

## Quality Expectations

The Delivery Manager's quality checklist includes:

- Every sub-issue traces back to the spec
- Every sub-issue has testable acceptance criteria
- Dependencies are explicit and acyclic

If the spec has vague requirements or untestable acceptance criteria,
the Delivery Manager will produce lower-quality issues. Invest time
in making requirements precise.

## When Specs Change

If a spec is updated after the Delivery Manager has already created issues:

1. The human or Planning Agent triggers a re-read
2. The Delivery Manager compares the new spec against existing issues
3. It creates new issues for new requirements
4. It flags changed requirements for human review
5. It does NOT automatically close or modify existing issues

Keep specs up to date. Stale specs cause drift between design intent
and implementation.
