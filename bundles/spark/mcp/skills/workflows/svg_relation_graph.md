---
name: svg_relation_graph
displayName: Draw a STIX relations-canvas SVG
category: workflows
description: '**LOAD WHEN DRAWING THE RELATIONS CANVAS FOR AN ISSUE.** When the operator (re)generates the Relations canvas, call `skills_read({file_path: "workflows/svg_relation_graph.md"})`, build a SELF-CONTAINED SVG of the issue''s indicators and the STIX relationships between them and ATT&CK techniques / malware / campaigns / threat-actors, and store it with `issue_set_relation_graph(issue_id, svg)`. Read the data with `indicators_list(issue_id=…)` + `indicator_get(id)` (which returns each indicator''s relationships). Rendered sandboxed (<img> data-URI): inline styles + a single <style> block only, NO <script>, NO external refs.'
icon: hub
source: platform
loadingMode: on-demand
locked: false
attack: []
---

# Skill: Draw a STIX relations-canvas SVG

## When to use

When the operator clicks **Regenerate** on an Issue's **Relations** tab (or asks for the relations canvas). It visualizes the issue's **indicators** and the STIX **relationships** between them and other entities (other IoCs, ATT&CK techniques, malware, campaigns, threat-actors) — the graph complement to the attack chain.

## Gather the data first

1. `indicators_list(issue_id="<the issue id>")` → the issue's IoCs (value, type, dbot_score).
2. For each, `indicator_get(id)` → its `relationships` (each: `relationship_type`, `target_value`, `target_type`) and the issues it appears in.
3. (If thin) record relationships first with `indicator_relate(...)` — e.g. domain `resolves-to` ip, indicator `indicates` malware, `attributed-to` a threat-actor, `uses` a technique.

## Hard rules (rendered sandboxed as an `<img>`)

Same contract as `svg_attack_chain`: SELF-CONTAINED — inline styles + a single inline `<style>` block; own background `<rect>`; NO `<script>` / `<foreignObject>` / `<image>` / external refs; XML-escape every label; `font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif"`; under ~256 KB; declarative CSS/SMIL animation is OK (it plays in `<img>`).

## Layout — layered columns by STIX node type

Relation graphs have crossing edges, so use a **deterministic layered (column) layout**, not force-directed:

- **viewBox** `0 0 1100 H` where `H = 120 + max(rows)*70`.
- **Columns** by node type, left → right (place a node in the leftmost column its role fits):
  1. **Indicators** (the issue's IoCs) — x≈40, type-colored.
  2. **Techniques / Malware / Tools** (what the IoCs indicate / use) — x≈400.
  3. **Campaigns / Intrusion-sets / Threat-actors** (attribution) — x≈760.
- **Nodes**: rounded rects ~250 wide × 48 tall, stacked vertically 70px apart per column; a small type tag + the value/name (truncate long hashes).
- **Edges**: a `<line>`/`<path>` from source node → target node, `marker-end` arrow, the **STIX relationship verb** as a small label at the edge midpoint (`resolves-to`, `indicates`, `attributed-to`, `uses`, `communicates-with`). Curve or offset labels to reduce overlap.
- **Legend** (top-right): node-type → color. **Title** top-left: `Relations — <issue short title>`.

## Palette (by STIX node type; dark, self-contained)

```
background #0e1729 · title/label #e2eeff · detail/tag #a9c3ee · edge #6b86b0
indicator       fill #14304f stroke #4a90d9
attack-pattern  fill #123f41 stroke #3fb0a8   (MITRE technique)
malware / tool  fill #3a1d2b stroke #c0556f
campaign / intrusion-set / threat-actor  fill #2e2350 stroke #9b6fd4
identity / vulnerability  fill #3f3214 stroke #d4a93f
```

## Template (fill from YOUR data; reflow rows by node count)

```svg
<svg viewBox="0 0 1100 360" xmlns="http://www.w3.org/2000/svg" font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">
  <style>.edge{stroke-dasharray:5 4;animation:flow 1.3s linear infinite}@keyframes flow{to{stroke-dashoffset:-18}}.tag{font-size:9px;font-weight:700;letter-spacing:.04em}</style>
  <rect width="1100" height="360" fill="#0e1729"/>
  <defs><marker id="rg-a" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L7,3 L0,6 Z" fill="#6b86b0"/></marker></defs>
  <text x="36" y="40" fill="#e2eeff" font-size="18" font-weight="700">Relations — &lt;issue short title&gt;</text>
  <g transform="translate(900,28)" class="tag" fill="#a9c3ee">
    <rect x="0" y="0" width="11" height="11" rx="2" fill="#14304f" stroke="#4a90d9"/><text x="16" y="9">Indicator</text>
    <rect x="0" y="18" width="11" height="11" rx="2" fill="#123f41" stroke="#3fb0a8"/><text x="16" y="27">Technique</text>
    <rect x="0" y="36" width="11" height="11" rx="2" fill="#2e2350" stroke="#9b6fd4"/><text x="16" y="45">Actor</text>
  </g>

  <!-- col 1: indicator -->
  <g><rect x="36" y="96" width="250" height="48" rx="10" fill="#14304f" stroke="#4a90d9" stroke-width="1.4"/>
    <text x="48" y="116" class="tag" fill="#cfe0ff">DOMAIN</text>
    <text x="48" y="132" fill="#e2eeff" font-size="12">acme-1ogin.com</text></g>
  <!-- edge: indicates -->
  <text x="343" y="112" fill="#a9c3ee" font-size="9" text-anchor="middle">indicates</text>
  <line class="edge" x1="286" y1="120" x2="396" y2="120" stroke="#6b86b0" stroke-width="1.8" marker-end="url(#rg-a)"/>
  <!-- col 2: attack-pattern -->
  <g><rect x="396" y="96" width="250" height="48" rx="10" fill="#123f41" stroke="#3fb0a8" stroke-width="1.4"/>
    <text x="408" y="116" class="tag" fill="#bdeee8">ATTACK-PATTERN</text>
    <text x="408" y="132" fill="#e2eeff" font-size="12">T1566.002 Spearphishing Link</text></g>
  <text x="703" y="112" fill="#a9c3ee" font-size="9" text-anchor="middle">attributed-to</text>
  <line class="edge" x1="646" y1="120" x2="756" y2="120" stroke="#6b86b0" stroke-width="1.8" marker-end="url(#rg-a)"/>
  <!-- col 3: threat-actor -->
  <g><rect x="756" y="96" width="250" height="48" rx="10" fill="#2e2350" stroke="#9b6fd4" stroke-width="1.4"/>
    <text x="768" y="116" class="tag" fill="#d9c8f5">THREAT-ACTOR</text>
    <text x="768" y="132" fill="#e2eeff" font-size="12">unattributed</text></g>
</svg>
```

## Procedure

1. Gather indicators + their relationships (above). If there are no relationships yet, record the obvious ones with `indicator_relate` first (domain→ip resolves-to; indicator→technique uses/indicates; →actor attributed-to).
2. Assign each node to its column by type; stack rows; reflow y = `96 + row*70`. Widen the viewBox height for more rows.
3. Draw edges with the **STIX verb** label at the midpoint; keep the `.edge` flow animation subtle.
4. XML-escape labels; truncate long hashes/URLs.
5. Call `issue_set_relation_graph(issue_id="<id>", svg="<the full SVG>")`. Fix + retry on error.

## Case-level (campaign) variant — v0.2.2

When the operator (re)generates the relations canvas on a **Case** (not a single Issue), draw the **campaign-level** STIX graph spanning ALL issues in the case:

1. `case_get(case_id="<id>")` → read the case + its `issues[]`. For each issue, `indicators_list(issue_id=…)` + `indicator_get(id)` to gather the union of indicators and their relationships across the whole case.
2. Draw ONE layered graph over that union — the shared infrastructure / techniques / actors that tie the case's issues together. Indicators seen in multiple issues are the campaign's connective tissue; place them once and let edges from several issues converge on them.
3. Same columns / palette / safety rules as the issue-level canvas.
4. Store with **`case_set_relation_graph(case_id="<id>", svg="<the full SVG>")`** (NOT `issue_set_relation_graph`). It renders on the Case detail's **Relations** tab.

## Cross-references

- **Companion**: `svg_attack_chain` (causal/temporal) — this is the relational/STIX view. Same render path, storage shape, and safety contract.
- Edges come from `indicator_relate` (STIX verbs verbatim, round-trip with the SOAR's EntityRelationship + MITRE ATT&CK).
