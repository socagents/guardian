# Spec Authoring Guide

> Detailed guidance for writing specs that the Delivery Manager can decompose
> into actionable GitHub Issues for coding agents.

## Audience

Your specs will be read by:

1. **The Delivery Manager** — to create GitHub Issues
2. **Coding agents** — to understand design intent during implementation
3. **The Review Agent** — to verify PRs match the design
4. **Humans** — for oversight and architectural decisions

Write for all four audiences. Be precise enough for machines, clear enough
for humans.

## Section-by-Section Guide

### Title

Use a clear, descriptive feature name. Avoid generic names.

| Good | Bad |
|------|-----|
| User Authentication via OAuth 2.0 | Auth Update |
| API Gateway Rate Limiting | Gateway Changes |
| Memory Service Vector Search | Service Improvements |

### Summary (Required)

Two to three sentences. A reader who reads only this section should understand
what the spec is about, why it matters, and roughly what it involves.

**Template:** "[Feature] enables [who] to [do what] by [how]. This addresses
[problem] and supports [goal]."

### Problem (Required)

Describe the problem from the user's or system's perspective. Include:

- Who experiences the problem?
- What happens today (the current state)?
- Why is the current state insufficient?
- What is the cost of not solving this?

Avoid jumping to solutions in this section. Describe the problem, not the fix.

### Goals (Required)

List concrete, measurable outcomes. Each goal should be verifiable.

**Good goals:**
- "Reduce API response latency to under 200ms at p99"
- "Support 10,000 concurrent WebSocket connections per node"
- "Enable users to configure plugins without editing YAML files"

**Bad goals:**
- "Make it faster" (not measurable)
- "Improve the user experience" (not specific)
- "Support more users" (not quantified)

### Non-Goals (Required)

Explicitly list what this spec does NOT cover. This prevents scope creep
during implementation. Think about adjacent features a reader might assume
are included.

**Template:** "This spec does NOT cover: [list of exclusions with brief
reasons]."

Every spec must have Non-Goals. If you cannot think of any, you have not
thought about scope boundaries carefully enough.

### User / System Flow (Recommended)

Show how the feature works end to end. Use one of:

- **Numbered steps** for simple linear flows
- **Sequence diagrams** (Mermaid syntax) for multi-actor interactions
- **State diagrams** for state machines

Always show the happy path first, then variations and error paths.

### Functional Requirements (Required)

The core of the spec. Rules for writing good requirements:

1. **Number every requirement** (FR-1, FR-2, etc.) so the Delivery Manager
   can reference specific items in issues
2. **One requirement per bullet** — do not combine multiple behaviors
3. **Make each requirement testable** — if you cannot write a test for it,
   rewrite it
4. **Group by subsystem** when the list exceeds 10 items
5. **Include error behavior** — what happens when things go wrong?
6. **Specify data formats** — use code blocks for schemas, payloads, headers

**Good requirement:**
> FR-3: The gateway MUST return HTTP 429 with a `Retry-After` header when
> a client exceeds 100 requests per minute. The header value MUST be the
> number of seconds until the rate limit resets.

**Bad requirement:**
> FR-3: Handle rate limiting appropriately.

### UI / UX Notes (If Applicable)

Include when the feature has a user-facing interface. Describe:

- Layout and component structure
- User interactions and state transitions
- Error states and loading states
- Accessibility requirements

Remove this section entirely if the feature is backend-only or internal.

### Acceptance Criteria (Required)

These are the conditions the Delivery Manager and Review Agent use to verify
the feature is complete. Rules:

1. **Use checkbox format** (`- [ ] Criterion`)
2. **Each criterion must be independently verifiable**
3. **Specify inputs and expected outputs** where applicable
4. **Include negative cases** (what should NOT happen)
5. **Reference specific requirements** (e.g., "FR-3 is satisfied")

**Good criterion:**
> - [ ] `POST /api/auth/login` with valid credentials returns 200 with
>   a JWT containing `sub`, `iat`, and `exp` claims

**Bad criterion:**
> - [ ] Login works correctly

### Work Breakdown Candidates (Recommended)

Suggest how the feature could be decomposed into implementation tasks.
The Delivery Manager uses this as a starting point (it may adjust).

For each candidate task, include:

| Column | Purpose |
|--------|---------|
| Task description | What to implement |
| Layer | Which system layer (cognitive, integration, runtime, presentation, cross-cutting) |
| Estimated complexity | S / M / L / XL |
| Dependencies | Which other tasks must complete first |

Guidelines:
- Each task should be completable in a single coding-agent session
- If a task exceeds XL (~500K tokens), split it further
- Avoid tasks that span multiple layers unless truly inseparable
- Order tasks to minimize blocking dependencies

### Dependencies (Recommended)

List dependencies on:

- Other specs (by file path)
- External APIs or services
- Infrastructure prerequisites
- Data or schema requirements

Be explicit about whether a dependency is blocking (must exist before this
feature can be implemented) or non-blocking (nice to have, but work can start).

### Risks / Edge Cases (Recommended)

Anticipate what could go wrong. For each risk:

- Describe the scenario
- Assess likelihood and impact
- Propose a mitigation strategy

Common risk categories:
- Performance under load
- Data consistency during failures
- Security attack vectors
- External service unavailability
- Backward compatibility breaks

### Testing / Verification Notes (Recommended)

Tell the coding agent how to verify the implementation:

- What unit tests are needed?
- What integration tests are needed?
- Are there manual verification steps?
- Is special test data or fixtures required?
- Are there external services to mock?

### Open Questions (If Applicable)

Record design decisions that are not yet resolved. For each question:

- State the question clearly
- Explain why it matters (what depends on the answer)
- Note any current best guesses

The Delivery Manager creates Project draft items from open questions.
Remove questions from this section once they are resolved (move the
resolution into the relevant spec section).

## Cross-Referencing Specs

When a spec depends on or relates to another spec:

- Reference by file path: `specs/api-gateway-routing.md`
- Add to the Dependencies section if it is a blocking dependency
- Add to the footer's companion specs list for general reference

## Spec Size Guidelines

| Spec Size | Typical Scope | Work Breakdown |
|-----------|--------------|----------------|
| Small | Single component or API endpoint | 2-4 tasks |
| Medium | One service feature end to end | 4-8 tasks |
| Large | Cross-service feature | 8-12 tasks |
| Too Large | Multiple independent features | Split into separate specs |

If a spec's Work Breakdown exceeds 12 tasks, consider splitting it.

## Updating Specs

Specs are living documents. When updating:

1. Update the `Last Updated` date in the header
2. Change the Status if applicable (e.g., back to `Draft` for major changes)
3. Make targeted edits — do not rewrite from scratch unless the design
   fundamentally changed
4. If acceptance criteria changed, note what changed and why
5. Commit the update — the Delivery Manager will re-read the spec
