# GitHub Project Field Mapping

> Reference document for the "Assistants" GitHub Project (Project #1).
> Used by Delivery Manager scripts and agents to populate project fields.

## Project Details

- **Owner:** {{GITHUB_ORG}}
- **Project Number:** 1
- **Project Title:** Assistants
- **URL:** https://github.com/users/{{GITHUB_ORG}}/projects/1

## Field Inventory

### Built-in Fields

| Field | Type | Notes |
|-------|------|-------|
| Title | Text | Auto-populated from issue title |
| Assignees | People | Auto-populated from issue assignees |
| Labels | Labels | Auto-populated from issue labels |
| Linked pull requests | PRs | Auto-populated |
| Milestone | Milestone | Auto-populated from issue milestone |
| Repository | Text | Auto-populated |
| Reviewers | People | Auto-populated from PR reviewers |
| Parent issue | Issue | Auto-populated from sub-issue relationships |
| Sub-issues progress | Progress | Auto-calculated |

### Custom Single-Select Fields

| Field | Options | Default |
|-------|---------|---------|
| **Status** | Backlog, Ready, In progress, In review, Done | Backlog |
| **Priority** | P0, P1, P2 | P1 |
| **Size** | XS, S, M, L, XL | — |
| **Layer** | Cognitive, Integration, Runtime, Presentation, Cross-cutting | — |
| **Agent** | claude-code, codex-cli, planning-agent, review-agent | — |
| **Complexity** | S, M, L, XL | — |
| **Build Stage** | Stage 1 through Stage 10 | — |

### Custom Text/Number Fields

| Field | Type | Purpose |
|-------|------|---------|
| **Estimate** | Number | Estimated effort (hours or story points) |
| **Estimated Tokens** | Number | Estimated token consumption for the task |
| **Actual Tokens** | Number | Tokens actually consumed |
| **Spec** | Text | Spec file path (repo-relative) |
| **Spec Commit** | Text | Commit SHA of the spec version used |
| **Notes** | Text | Operational notes (DM or human use) |

### Date Fields

| Field | Type | Purpose |
|-------|------|---------|
| **Start date** | Date | When work begins |
| **Target date** | Date | Deadline or target completion |

## Population Defaults

When the Delivery Manager creates issues, use these defaults:

### Parent Issues

| Field | Value |
|-------|-------|
| Status | Ready |
| Priority | P1 |
| Layer | Inferred from spec area |
| Spec | Spec file path |
| Spec Commit | Current commit SHA |

### Sub-Issues

| Field | Value |
|-------|-------|
| Status | Backlog |
| Priority | P1 (unless clearly higher) |
| Layer | Inferred from task type |
| Complexity | Inferred from estimated size |
| Spec | Spec file path |
| Spec Commit | Current commit SHA |
| Agent | Leave blank (dispatch assigns based on labels) |

### Draft Items

| Field | Value |
|-------|-------|
| Status | Backlog |
| Notes | Source and type of draft item |

## Status Mapping

The project Status field maps to the task lifecycle:

| Lifecycle State | Project Status | Issue Label |
|----------------|---------------|-------------|
| Planning | Backlog | `status:planning` |
| Ready | Ready | `status:ready` |
| In Progress | In progress | `status:in-progress` |
| PR Open | In progress | `status:pr-open` |
| In Review | In review | `status:in-review` |
| Done | Done | `status:done` |
| Blocked | (use label) | `status:blocked` |

Note: "Blocked" is tracked via the `status:blocked` label rather than a
project Status option. This allows issues to retain their workflow position
(e.g., "Ready" or "In progress") while being flagged as blocked.

## Recommended Views

### Board View

- Group by: Status
- Columns: Backlog → Ready → In progress → In review → Done
- Filter: (none — show all)

### Table View

- Columns: Title, Status, Priority, Layer, Complexity, Agent,
  Build Stage, Spec, Spec Commit, Target date, Parent issue,
  Sub-issues progress
- Sort: Priority (P0 first), then Status

### Roadmap View (optional)

- Date field: Target date
- Group by: Build Stage
- Show: Items with Target date set
