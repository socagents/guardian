# Stage B — Multi-Source Defensible Depth

**Status:** design-level (refine before build) — 2026-06-21 · Arc: [arc](2026-06-21-structured-investigation-model-arc.md) · Depends on **A**
**Goal:** Make each investigation reach beyond the XSOAR case — hunt blast radius in telemetry (XQL), write the verdict back to the source case, and recommend containment — so the structured record (A) is backed by multi-source evidence.

## Components

1. **XQL blast-radius hunt wired into the lifecycle.** Extend `xsoar_case_investigation` (the scope/enrich step) so that, when an incident has host/user/IP/hash indicators, the agent: calls `xql_examples_search(intent=…)` for an idiomatic hunt, binds the incident's indicators + time window into the query, optionally confirms syntax via `cortex-docs/xql_lookup`, runs it with `xsiam_run_xql_query`, and records the affected entities into the Stage-A `blast_radius` field + `issue_add_event` evidence. No new connector code — reuses the v0.2.44 XQL surface + the existing xsiam connector. Gracefully degrades when no XSIAM instance is configured (note it, proceed with case data).

2. **`push_verdict_to_xsoar` MCP tool.** When an investigation resolves (verdict set in A), write the structured verdict + key findings back to the upstream XSOAR incident's war room as evidence — via the xsoar connector's `add_entry`/`add_note`/`save_evidence` through the connector-proxy. Guard on `source_ref` non-null. Optionally fold into the resolve step of the skill. This closes the loop so the verdict lives where the SOC works the case.

3. **Containment-recommendation step (recommend-only, approval-gated).** Add a lifecycle step that, for TRUE_POSITIVE incidents, produces a structured **recommended containment** block (isolate host / disable account / block indicator / run playbook) stored on the issue (`recommendations` + a structured `containment` note) — and surfaces the exact tool call the operator could approve (XSIAM EDR isolate, XSOAR block-list/playbook). Execution stays behind the existing approval gate; the agent recommends, the human approves. No auto-containment.

## Reuse / extend
- Reuse: `xql_examples_search` + `xsiam_run_xql_query` + `cortex-docs/xql_lookup` (v0.2.44); xsoar `add_entry/add_note/save_evidence`; the connector-proxy pattern; A's `blast_radius` field + `issue_add_event`.
- Extend: the skill (new scope-hunt + resolve-pushback + containment steps); the judge rubric (cross-source: did the investigation consult ≥2 sources? was containment considered for high/critical TPs?); the seeder (seed incidents that need a telemetry pivot to resolve correctly).
- Build new: `push_verdict_to_xsoar` tool; a small structured `containment` recommendation schema (a JSON note shape) — likely a field/event, not a new table.

## Testing
- pytest for `push_verdict_to_xsoar` (mock connector-proxy; asserts save_evidence called with verdict; no-op when source_ref null).
- Live smoke: a fetched incident → skill runs an XQL hunt (tool_call shows `xql_examples_search` + `xsiam_run_xql_query`) → blast_radius populated → verdict pushed to the XSOAR war room (evidence visible) → containment recommendation present, NOT executed.

## Deploy
Agent-image-only (skill + 1 tool); no connector rebuild. Gate → deploy → live smoke → release.
