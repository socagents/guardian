# Stage D — Export + Interop

**Status:** design-level (refine before build) — 2026-06-21 · Arc: [arc](2026-06-21-structured-investigation-model-arc.md) · Depends on **A, C**
**Goal:** Make the structured investigation/campaign record portable — exportable as STIX, renderable from report templates, and pushable to external ticketing/webhooks — so Guardian's findings flow into the wider SOC ecosystem.

## Components

1. **STIX 2.1 bundle export.** `export_issue_stix(issue_id)` / `export_case_stix(case_id)` — assemble a STIX bundle from the structured record: an `incident`/`grouping` object + `attack-pattern` (from `technique_mappings`), `indicator`/`observed-data` (from indicators), `malware`/`threat-actor`/`campaign` (from C's rollup), and `relationship` objects (from the relationships graph + technique links). Returns the JSON bundle; optionally stores it. Pure assembly over A/C data (no new external calls).

2. **Report templates.** Generalize A's `generate_investigation_report` to support named templates (`executive`, `technical`, `ioc-list`) — `generate_investigation_report(issue_id, template="technical")` — each a markdown skeleton filled from the structured record. A case-level `generate_campaign_report(case_id)` for the C rollup.

3. **Ticket / webhook handoff.** A generic outbound: on resolve (or on demand), POST the structured verdict + report + IOCs to a configured webhook (operator-configured URL + auth in instance config / a connector). Keep it **opt-in + approval-gated** (it sends data externally — gated like every outbound action). Stretch: a thin Jira/ServiceNow shape.

## Reuse / extend
- Reuse: A's `report` + structured fields, A's `technique_mappings`, C's campaign rollup + relationships, the connector/instance-config pattern for the webhook target, the approval gate for outbound.
- Extend: `generate_investigation_report` (template param); the skill (offer STIX export / ticket handoff at resolve when configured).
- Build new: `export_issue_stix`/`export_case_stix` (STIX assembly, pure Python); the report-template renderer; the webhook outbound (approval-gated) + its config surface.

## Safety
- STIX export is read/assemble only (safe).
- Webhook/ticket handoff **sends data to an external system** → approval-gated, opt-in, target from operator config only (never from observed content). Surface what will be sent before sending.

## Testing
- pytest: STIX bundle shape validates (required object types + relationships present); template rendering fills sections; webhook payload assembly (mock transport; no real send in tests).
- Live smoke: a resolved structured issue → STIX bundle parses + contains the attack-patterns/indicators/relationships; `technical` + `executive` reports render; webhook handoff is offered but requires approval.

## Deploy
Agent-image-only (export/templates) + possibly a small connector/config for the webhook. Gate → deploy → live smoke → release.
