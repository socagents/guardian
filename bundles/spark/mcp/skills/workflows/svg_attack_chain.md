---
name: svg_attack_chain
displayName: Draw an attack-chain SVG diagram
category: workflows
description: '**LOAD WHEN PRODUCING AN ATTACK-CHAIN / CAUSALITY DIAGRAM FOR AN INVESTIGATION.** When you resolve an XSOAR case investigation (or the operator asks for a diagram of an Issue), call `skills_read({file_path: "workflows/svg_attack_chain.md"})` to get the SVG template + rules, emit a SELF-CONTAINED SVG of the attack chain (ordered nodes: entry → host/account → action → impact, connected by labelled arrows), and store it with `issue_set_attack_chain(issue_id, svg)`. The SVG is rendered sandboxed (as an <img> data-URI) on the Issue''s Attack-chain tab — so it MUST be self-contained: inline styles/attributes only, its own background, NO <script>, NO external fonts / images / links.'
icon: account_tree
source: platform
loadingMode: on-demand
locked: false
attack: []
---

# Skill: Draw an attack-chain SVG diagram

## When to use

At the **end of an investigation**, once you have the verdict and the entity ledger, draw the **attack chain** — the ordered path the attack took across entities — and attach it to the Issue with `issue_set_attack_chain(issue_id, svg)`. The `xsoar_case_investigation` skill calls for this at resolve time. Also use it when the operator asks to (re)generate the diagram for an Issue.

An attack chain is **not** a network map. It is the **causal sequence**: how the attack started, what it touched, what it did, and the impact — left to right, one step per arrow.

## Hard rules (the SVG is rendered sandboxed as an `<img>`)

The UI renders your SVG via `<img src="data:image/svg+xml,…">`. That sandbox means **scripts never run and external resources never load**. So the SVG MUST be **self-contained**:

- **Inline styling only** — `fill=`, `stroke=`, `font-size=` attributes (or a single inline `<style>` block). NO external CSS, NO web fonts (use `font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif"`).
- **Its own background** — draw a full-canvas `<rect>` first (the page background won't show through). Use the dark palette below so it reads on Guardian's UI.
- **NO `<script>`, NO `<foreignObject>`, NO `<image>`, NO external `<a href>`, NO `xlink:href` to URLs.** (The store strips `<script>`/`on*` anyway, but don't emit them.)
- **XML-escape every label**: `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`, `"` → `&quot;`. An unescaped `&` breaks the whole SVG.
- Keep it under ~256 KB (you will be far under). Start with `<svg …>` and end with `</svg>`.

## Layout

- **viewBox** `0 0 W 300` where `W = 60 + nodes×220` (so 4 nodes → ~940). Height 300 fits one row + a title + a verdict strip.
- **Title** top-left: `Attack chain — <incident short title>`.
- **Nodes**: rounded rects, 180 wide × 96 tall, top at y=92, 220px horizontal pitch. Each node = one stage of the chain. Two text lines: a bold label (the entity/action) and a smaller detail (the IoC/value).
- **Arrows**: a `<line>` from node N's right edge to node N+1's left edge with `marker-end="url(#arrow)"`, and a small label above it naming the technique/protocol (e.g. `SMB`, `T1021.002`, `beacon`, `exfil`).
- **Verdict strip** bottom-left: the one-line VERDICT (TRUE POSITIVE — …).
- 3–6 nodes is the sweet spot. Collapse detail into the node; don't crowd.

## Palette (dark, self-contained)

```
background   #0e1729
node fill    #1b2a44     node stroke #3f6fb0
title text   #e2eeff     label text  #e2eeff     detail text #a9c3ee
arrow/edge   #5b9bd5
impact node  fill #3a1d2b stroke #c0556f   (use for the final "impact" stage)
verdict text #ff9db0  (true positive)  /  #a9c3ee  (benign / false positive)
```

## Template (fill the labels from YOUR investigation)

```svg
<svg viewBox="0 0 940 300" xmlns="http://www.w3.org/2000/svg" font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">
  <rect x="0" y="0" width="940" height="300" fill="#0e1729"/>
  <defs>
    <marker id="ac-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L7,3 L0,6 Z" fill="#5b9bd5"/>
    </marker>
  </defs>
  <text x="28" y="40" fill="#e2eeff" font-size="18" font-weight="700">Attack chain — Lateral movement WS-12 &#8594; DC-01</text>

  <!-- Node 1 -->
  <g>
    <rect x="28" y="92" width="180" height="96" rx="14" fill="#1b2a44" stroke="#3f6fb0" stroke-width="1.5"/>
    <text x="118" y="132" fill="#e2eeff" font-size="13" font-weight="700" text-anchor="middle">Workstation</text>
    <text x="118" y="154" fill="#a9c3ee" font-size="11" text-anchor="middle">WS-12 (10.10.4.12)</text>
  </g>
  <!-- edge 1 -> 2 -->
  <text x="234" y="132" fill="#a9c3ee" font-size="10" text-anchor="middle">SMB / T1021.002</text>
  <line x1="208" y1="140" x2="248" y2="140" stroke="#5b9bd5" stroke-width="2" marker-end="url(#ac-arrow)"/>

  <!-- Node 2 -->
  <g>
    <rect x="248" y="92" width="180" height="96" rx="14" fill="#1b2a44" stroke="#3f6fb0" stroke-width="1.5"/>
    <text x="338" y="132" fill="#e2eeff" font-size="13" font-weight="700" text-anchor="middle">Domain Admin auth</text>
    <text x="338" y="154" fill="#a9c3ee" font-size="11" text-anchor="middle">T1078.002</text>
  </g>
  <text x="454" y="132" fill="#a9c3ee" font-size="10" text-anchor="middle">admin share</text>
  <line x1="428" y1="140" x2="468" y2="140" stroke="#5b9bd5" stroke-width="2" marker-end="url(#ac-arrow)"/>

  <!-- Node 3 (impact) -->
  <g>
    <rect x="468" y="92" width="180" height="96" rx="14" fill="#3a1d2b" stroke="#c0556f" stroke-width="1.5"/>
    <text x="558" y="132" fill="#e2eeff" font-size="13" font-weight="700" text-anchor="middle">Domain Controller</text>
    <text x="558" y="154" fill="#a9c3ee" font-size="11" text-anchor="middle">DC-01 (10.10.0.5)</text>
  </g>

  <text x="28" y="262" fill="#ff9db0" font-size="13" font-weight="700">VERDICT: TRUE POSITIVE — unauthorized Domain-Admin lateral movement (severity 4)</text>
</svg>
```

## Procedure

1. From the investigation, list the chain stages in order (entry/origin → pivots → action → impact). Map each confirmed entity/step to one node; map each transition to one labelled arrow (technique id or protocol).
2. Compute the width: `W = 60 + nodes×220`; set the viewBox and the last node's x accordingly. Re-flow the x positions (node N x = 28 + N×220).
3. Fill labels from real values in the ledger — **XML-escape them**. Use the impact palette for the final stage. Put the one-line VERDICT in the bottom strip.
4. Call `issue_set_attack_chain(issue_id="<the Issue id>", svg="<the full SVG>")`.
5. If the tool returns an error (not SVG / too large), fix it and retry — do not leave the Issue without a diagram when you had the evidence to draw one.

## Cross-references

- **Driver**: `xsoar_case_investigation` — calls this skill at resolve time (Step 6).
- The diagram complements the **Activity** timeline (chronological log) with a **causal** view; both live on the Issue.
