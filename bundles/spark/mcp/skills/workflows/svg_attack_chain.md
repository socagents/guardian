---
name: svg_attack_chain
displayName: Draw an attack-chain SVG diagram
category: workflows
description: '**LOAD WHEN PRODUCING AN ATTACK-CHAIN / CAUSALITY DIAGRAM FOR AN INVESTIGATION.** When you resolve an XSOAR case investigation (or the operator asks for a diagram of an Issue), call `skills_read({file_path: "workflows/svg_attack_chain.md"})` to get the SVG template + rules, emit a SELF-CONTAINED SVG of the attack chain (ordered tactic-colored stages connected by technique-labelled arrows), and store it with `issue_set_attack_chain(issue_id, svg)`. The SVG is rendered sandboxed (as an <img> data-URI) on the Issue''s Attack-chain tab — so it MUST be self-contained: inline styles + a single inline <style> block only, NO <script>, NO external fonts / images / links.'
icon: account_tree
source: platform
loadingMode: on-demand
locked: false
attack: []
---

# Skill: Draw an attack-chain SVG diagram

## When to use

At the **end of an investigation**, once you have the verdict + the entity ledger + the ATT&CK techniques, draw the **attack chain** and attach it with `issue_set_attack_chain(issue_id, svg)`. The `xsoar_case_investigation` skill calls for this at resolve time. Also use it when the operator (re)generates the diagram for an Issue.

An attack chain is the **causal sequence** of the attack mapped onto **MITRE ATT&CK** — each stage is one tactic (color-coded), each transition is the technique that moved the attacker forward — left to right, ending in impact.

## Hard rules (rendered sandboxed as an `<img>`)

The UI renders your SVG via `<img src="data:image/svg+xml,…">`. Scripts never run and external resources never load. So:

- **Self-contained styling**: inline `fill=`/`stroke=` attributes AND/OR a single inline `<style>` block at the top. Declarative CSS animations + SMIL `<animate>` DO play in `<img>` (only scripting is blocked) — use them for subtle motion. NO web fonts (`font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif"`).
- **Own background** — full-canvas `<rect>` first, dark palette below.
- **NO `<script>`, `<foreignObject>`, `<image>`, external `<a href>`/`xlink:href`.** XML-escape every label (`&`→`&amp;`, `<`→`&lt;`, `>`→`&gt;`, `"`→`&quot;`).
- Under ~256 KB. Start `<svg …>`, end `</svg>`.

## Layout (give labels room — don't clip)

- **viewBox** `0 0 W 360`. `W = 80 + stages×250` (4 stages → 1080). Wide pitch so technique labels never collide with nodes.
- **Nodes**: rounded rects **180 wide × 104 tall**, top y=120, **250px pitch** (node N x = 40 + N×250) → a **70px gap** between nodes for the arrow + its label. Each node carries: a **tactic tag** (small pill, top), a **bold entity/stage label**, and a **detail line** (the IoC/value).
- **Arrows** sit in the gap: a `<line>` (or animated dashed line) from node N's right edge (x+180) to node N+1's left edge, `marker-end="url(#arrow)"`, with the **technique id + name** label centered ABOVE it (font-size 10) — it fits in the 70px gap because you keep it terse (`T1105` / `Ingress Tool Transfer`, stacked on two short lines if needed).
- **Tactic legend** (top-right): small swatches mapping the tactics used → their colors.
- **Attribution strip** (bottom, above verdict): `Attribution: <actor/campaign or "unattributed">`.
- **Verdict strip** (very bottom): the one-line `VERDICT: …`.
- 3–6 stages. Collapse detail into the node.

## Tactic palette (color-code each node by its ATT&CK tactic)

Use the fill/stroke for the node's tactic; list the ones you used in the legend.

```
initial-access      fill #14304f stroke #4a90d9   (TA0001)
execution           fill #123f41 stroke #3fb0a8   (TA0002)
persistence         fill #2e2350 stroke #9b6fd4   (TA0003)
priv-escalation     fill #3f3214 stroke #d4a93f   (TA0004)
defense-evasion     fill #2a2e3a stroke #8c95a8   (TA0005)
credential-access   fill #14424f stroke #3fb0c8   (TA0006)
discovery           fill #1d2a4a stroke #5b8fd5   (TA0007)
lateral-movement    fill #442e14 stroke #e0843f   (TA0008)
command-and-control fill #1d244a stroke #5b6fd5   (TA0011)
exfiltration        fill #421d3a stroke #d44f9b   (TA0010)
impact              fill #3a1d2b stroke #c0556f   (TA0040)
background #0e1729 · title/label text #e2eeff · detail/tag text #a9c3ee
edge #6b86b0 · verdict(TP) #ff9db0 · verdict(benign/FP) #a9c3ee
```

## Template (fill from YOUR investigation; reflow x by stage count)

```svg
<svg viewBox="0 0 1040 360" xmlns="http://www.w3.org/2000/svg" font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">
  <style>
    .flow { stroke-dasharray: 6 5; animation: dash 1.1s linear infinite; }
    @keyframes dash { to { stroke-dashoffset: -22; } }
    .pulse { animation: pulse 2.2s ease-in-out infinite; }
    @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: .62 } }
    .tac { font-size: 9px; font-weight: 700; letter-spacing: .04em; }
  </style>
  <rect x="0" y="0" width="1040" height="360" fill="#0e1729"/>
  <defs>
    <marker id="ac-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L7,3 L0,6 Z" fill="#6b86b0"/>
    </marker>
  </defs>
  <text x="40" y="46" fill="#e2eeff" font-size="19" font-weight="700">Attack chain — &lt;incident short title&gt;</text>

  <!-- legend (top-right): one entry per tactic used -->
  <g transform="translate(720,30)" class="tac" fill="#a9c3ee">
    <rect x="0" y="0" width="11" height="11" rx="2" fill="#14304f" stroke="#4a90d9"/><text x="16" y="9">Initial Access</text>
    <rect x="0" y="18" width="11" height="11" rx="2" fill="#442e14" stroke="#e0843f"/><text x="16" y="27">Lateral Movement</text>
    <rect x="0" y="36" width="11" height="11" rx="2" fill="#3a1d2b" stroke="#c0556f"/><text x="16" y="45">Impact</text>
  </g>

  <!-- Stage 1 (x=40) -->
  <g>
    <rect x="40" y="120" width="180" height="104" rx="14" fill="#14304f" stroke="#4a90d9" stroke-width="1.5"/>
    <rect x="52" y="132" width="96" height="16" rx="8" fill="#4a90d9" opacity=".22"/>
    <text x="58" y="144" class="tac" fill="#cfe0ff">INITIAL ACCESS</text>
    <text x="130" y="178" fill="#e2eeff" font-size="13" font-weight="700" text-anchor="middle">Public Web Server</text>
    <text x="130" y="200" fill="#a9c3ee" font-size="11" text-anchor="middle">web-prod-01 :8080</text>
  </g>
  <!-- edge 1->2 (animated, technique label stacked above) -->
  <text x="255" y="160" fill="#a9c3ee" font-size="10" text-anchor="middle" font-weight="700">T1190</text>
  <text x="255" y="172" fill="#a9c3ee" font-size="9"  text-anchor="middle">Exploit Public App</text>
  <line class="flow" x1="220" y1="184" x2="282" y2="184" stroke="#6b86b0" stroke-width="2" marker-end="url(#ac-arrow)"/>

  <!-- Stage 2 (x=290) -->
  <g>
    <rect x="290" y="120" width="180" height="104" rx="14" fill="#123f41" stroke="#3fb0a8" stroke-width="1.5"/>
    <rect x="302" y="132" width="78" height="16" rx="8" fill="#3fb0a8" opacity=".22"/>
    <text x="308" y="144" class="tac" fill="#bdeee8">EXECUTION</text>
    <text x="380" y="178" fill="#e2eeff" font-size="13" font-weight="700" text-anchor="middle">PHP Web Shell</text>
    <text x="380" y="200" fill="#a9c3ee" font-size="11" text-anchor="middle">www-data</text>
  </g>
  <text x="505" y="160" fill="#a9c3ee" font-size="10" text-anchor="middle" font-weight="700">T1105</text>
  <text x="505" y="172" fill="#a9c3ee" font-size="9"  text-anchor="middle">Ingress Tool Xfer</text>
  <line class="flow" x1="470" y1="184" x2="532" y2="184" stroke="#6b86b0" stroke-width="2" marker-end="url(#ac-arrow)"/>

  <!-- Stage 3 (impact, x=540) -->
  <g class="pulse">
    <rect x="540" y="120" width="180" height="104" rx="14" fill="#3a1d2b" stroke="#c0556f" stroke-width="1.5"/>
    <rect x="552" y="132" width="58" height="16" rx="8" fill="#c0556f" opacity=".22"/>
    <text x="558" y="144" class="tac" fill="#ffc6d2">IMPACT</text>
    <text x="630" y="178" fill="#e2eeff" font-size="13" font-weight="700" text-anchor="middle">Ransomware</text>
    <text x="630" y="200" fill="#a9c3ee" font-size="11" text-anchor="middle">T1486</text>
  </g>

  <text x="40" y="300" fill="#a9c3ee" font-size="11">Attribution: unattributed (no actor/campaign match)</text>
  <text x="40" y="326" fill="#ff9db0" font-size="13" font-weight="700">VERDICT: TRUE POSITIVE — &lt;one-line disposition&gt; (severity N)</text>
</svg>
```

## Procedure

1. From the investigation, list the chain stages in order. For EACH stage pick its **ATT&CK tactic** (→ node color) + the entity/value; for EACH transition pick the **technique id + short name** (→ the arrow label).
2. Set `W = 80 + stages×250`; reflow node x = `40 + N×250`; arrow gap is the 70px between nodes.
3. Build the legend from ONLY the tactics you used. Add the **attribution** line (name the actor/campaign if your research supports it, else "unattributed"). Add the one-line **VERDICT**.
4. XML-escape all labels. Keep the `.flow` dash animation on arrows + `.pulse` on the impact node (subtle).
5. Call `issue_set_attack_chain(issue_id="<the Issue id>", svg="<the full SVG>")`. If it errors (not SVG / too large), fix + retry.

## Cross-references

- **Driver**: `xsoar_case_investigation` — calls this at resolve time (Step 6). The technique/tactic mapping comes from the investigation's MITRE conclusions.
- Complements the **Activity** timeline (chronological) with a **causal, ATT&CK-mapped** view.
