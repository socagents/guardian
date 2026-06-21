# Plan — Architecture page cleanup (`app/help/architecture/page.tsx`)

**Goal:** The canonical system spec reads as a clean description of the system **as it is now** — services, ports, inter-service wiring, data model, tool catalog, credential guardrail — with **no version stamps, no "Implementation gap" subsections, no fix narration**. Architectural content is preserved; only the release archaeology is removed.

**Scope:** ~6,800-line page. Audit found **112 version markers** (8 comment blocks, 11 subsection titles, ~82 inline) + retired-subsystem comment blocks + several "Implementation gap"-style dev asides. Code cross-check confirmed the page is **accurate** (9 investigation tables, 4 connectors + 1 emulated service, 6–7 bundled KBs all match the code) — so this is strip + 3 small adds, not a rewrite.

## Policy
- Strip every inline `(vX.Y.Z)` / `[guardian vX.Y.Z]` marker; rewrite the sentence to present tense, keeping the technical content.
- Delete retired-subsystem comment blocks (xlog / caldera / data-sources / log-destinations) — last traces of removed simulation features.
- Remove the `[v0.2.27] RESTORED` annotation on the XSIAM connector → plain current-state description.
- Note: markers here span the whole codebase's history (v0.1.x … v0.17.x, v0.5.1, v0.7.1, v0.6.10, v0.3.0, v0.1.23) — all go.

## Tasks

1. **Delete dev comment blocks** (~8): the removed-simulation JSDoc/JSX comments near the connector + data-source sections and at end-of-file.

2. **Strip version stamps from SubSection titles** (~11): Multiple-enabled-instances-per-connector; Turn-scoped read cache; Failed-call loop breaker; the investigation/structured-outcome titles; KB titles; etc. → plain titles.

3. **Investigation `#investigation` section** — the densest cluster:
   - Schema `<Pre>` block: drop the per-column version comments (`-- … (v0.2.45, nullable)` → `-- … (nullable)`); prefix with "The investigation store has nine tables:" (present-tense framing).
   - The capability bullets currently split by release ("**Indicators** (v0.2.0–v0.2.1) — …", "**Structured outcome** (v0.2.45) — …", "**Multi-source depth** (v0.2.46) —", "**Campaign analytics** (v0.2.47) —", "**Export / interop** (v0.2.48) —"): **reorganize into one capability-centric list** with no version narrative.
   - REST subsection: strip the `, v0.2.45` / `v0.2.47` / `v0.2.48` stamps from the endpoint descriptions; keep the routes.
   - UI subsection: "Assessment tab (v0.2.45 structured outcome — …" → "Assessment tab displays the structured outcome — …".
   - The MCP-tools paragraph currently says "thirty-two MCP tools" but does not enumerate them.

4. **Knowledge-pipeline section**: strip the per-KB version stamps (soc-investigation, mitre-attack-enterprise/ics/mobile, mitre-atlas, soar-playbooks, xql-examples) + the `kbs/ # … (v0.2.16+, …)` tree comment; keep each KB's name + purpose.

5. **Misc inline stamps**: "Every skill edit is audited + versioned (v0.2.12)" → drop marker; "The v0.1.3 Investigation module adds…" → "The Investigation module provides…"; v0.2.29 instance-guard sentence → present tense.

6. **Adds (3, current-state completeness)**:
   - A present-tense Investigation **preamble** before the Store subsection summarizing the module's capabilities (Issues/Cases, structured verdict, ATT&CK mappings, diagrams, indicators+STIX, campaign rollup, STIX export).
   - An **Investigation Tools** subsection listing the ~20 investigation tools (issue_*, case_*, case_rollup, indicator_*, push_verdict_to_xsoar, infer_relationships, export_issue_stix/export_case_stix, generate_investigation_report/generate_campaign_report, webhook_preview/export_to_webhook) with one-line each — closes the data-model↔capability gap.
   - A one-line **catalog-domain** clarification in the Store subsection (why the agent may read/write investigation data: it's analysis metadata, never secrets) — and note that `export_to_webhook` is the lone approval-gated outbound.

## Verification
- `grep -nE '\(v[0-9]|guardian v0|Implementation gap|RESTORED|Phase [0-9]' app/help/architecture/page.tsx` → 0 (or only legitimate product nouns).
- Inter-service wiring claims still present (agent→MCP loopback bearer, proxy paths) — do not delete those.
- `npx tsc --noEmit` + eslint clean; spot-read `#investigation`, `#connectors`, `#knowledge`.
