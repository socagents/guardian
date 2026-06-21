# Stage C — Campaign / Cross-Incident Analytics

**Status:** design-level (refine before build) — 2026-06-21 · Arc: [arc](2026-06-21-structured-investigation-model-arc.md) · Depends on **A, B**
**Goal:** Lift structured single-incident records (A) into fleet/campaign intelligence — roll related incidents into typed campaigns, match them to playbooks, link related cases, and infer indicator relationships — so an analyst sees the bigger picture, not one alert at a time.

## Components

1. **Case-level campaign rollup.** Extend `cases` with structured rollup fields: `campaign_summary`, `threat_actor`, `infrastructure` (JSON: shared IOCs), `techniques` (aggregated from member issues' `technique_mappings`), `severity_rollup`. A `case_rollup(case_id)` tool synthesizes these from member issues (techniques union, IOC intersection, max severity, verdict mix). UI: case detail gains a Campaign tab.

2. **Playbook-match table.** `playbook_matches(issue_id, playbook_doc_id, score, matched_criteria)` — when the agent routes an investigation through a soc-investigation/soar-playbooks KB playbook, record the structured link so cases can be typed by playbook and queried ("all ransomware-playbook incidents"). Tool: `issue_match_playbook(issue_id, playbook_doc_id, score, matched_criteria)`.

3. **Cross-case "related-to" edges.** A `case_relationships(source_case_id, target_case_id, relationship_type, note)` table (sibling / escalation / reopen / same-campaign) + tools `case_relate` / `case_related`. Lets the model link a new case to a prior campaign.

4. **Relationship inference.** On indicator relationship updates, traverse the existing `relationships` graph (domain→IP→C2) and SUGGEST missing edges + auto-link sibling issues/cases that share IOCs or techniques (suggest, agent confirms — no silent writes). Tool: `infer_relationships(issue_id|indicator_id)` returns ranked suggestions.

## Reuse / extend
- Reuse: A's `technique_mappings` (campaign technique union + technique→incidents), the existing `relationships` + `indicators` tables, `cases` + `indicator_relate`, the on-demand-regen UI pattern, the SVG case-level diagram tools.
- Extend: `cases` schema (rollup columns); the skill (after resolving an issue that belongs to a campaign, run `case_rollup` + suggest `case_relate`); the judge (campaign coherence dimension).
- Build new: `playbook_matches` + `case_relationships` tables + their tools; `infer_relationships` (graph traversal, pure Python over the store); the Campaign UI tab.

## Testing
- pytest: rollup aggregation (techniques union, severity max, IOC intersection); playbook-match + case-relationship CRUD; `infer_relationships` traversal on a seeded graph (domain→IP→C2 suggests domain→C2).
- Live smoke: two related issues in a case → `case_rollup` produces campaign summary + technique union; `infer_relationships` suggests the transitive C2 link; technique→incidents query spans the campaign.

## Deploy
Agent-image-only. Gate → deploy → live smoke → release.
