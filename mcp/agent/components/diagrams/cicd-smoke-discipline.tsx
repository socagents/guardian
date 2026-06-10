/**
 * CICD diagram 6/6 — Smoke-testing discipline.
 *
 * Visualizes the v0.5.75 CLAUDE.md addendum (Agent-side headless
 * smoke) that gates a release from `status:in-progress` to
 * `status:released`. Three layers:
 *
 *   1. Label-state machine (top, horizontal) — the GitHub Issue
 *      status:* labels track each release's lifecycle. Five
 *      transitions, each annotated with WHO flips the label:
 *
 *      status:in-progress
 *        → [agent-side headless smoke] →
 *      status:ready-for-testing
 *        → [operator hands-on smoke] →
 *      status:testing-complete
 *        → [operator chat approval] →
 *      status:release-approved
 *        → [git tag + release.yml] →
 *      status:released  (issue auto-closes)
 *
 *   2. Agent-side probe breakdown (middle band) — what the agent
 *      actually does between in-progress + ready-for-testing.
 *      Six rules from the CLAUDE.md addendum, each with the
 *      concrete probe activity.
 *
 *   3. State classification + postmortem loop (bottom row) —
 *      every smoke bullet gets one of three annotations
 *      (✓ ⨯ ?) so the operator sees exactly which bullets the
 *      agent confirmed vs. which still need hands-on. Plus the
 *      postmortem feedback loop: when a bug ships past dev-built
 *      and the operator catches it, the next release ships a
 *      CLAUDE.md addendum naming the smoke-gap.
 *
 * Postmortem-driven discipline growth: v0.5.76 + v0.5.77 were
 * each the result of the v0.5.75 addendum catching a bug it
 * was DESIGNED to catch. The loop is real.
 */

import { DIAGRAM_THEME_CSS, DiagramMarkers } from "./_diagram-theme";

const STYLES = DIAGRAM_THEME_CSS + `
.dgm-root .smoke-chip {
  fill: var(--dgm-node-fill); stroke: var(--dgm-stroke-strong);
  stroke-width: 1.6;
}
.dgm-root .smoke-chip-active {
  fill: var(--dgm-node-fill-strong); stroke: var(--dgm-edge-compose);
  stroke-width: 2;
}
.dgm-root .smoke-chip-final {
  fill: var(--dgm-state-success); fill-opacity: 0.12;
  stroke: var(--dgm-state-success); stroke-width: 2;
}
.dgm-root .smoke-gate {
  fill: var(--dgm-badge-bg); stroke: var(--dgm-state-warn);
  stroke-width: 1.4; stroke-dasharray: 4 3;
}
.dgm-root .smoke-rule {
  fill: var(--dgm-node-fill); stroke: var(--dgm-stroke-muted);
  stroke-width: 1.2;
}
.dgm-root .smoke-rule-num {
  font-size: 18px; font-weight: 800; fill: var(--dgm-edge-compose);
  font-family: "JetBrains Mono", "SFMono-Regular", monospace;
}
.dgm-root .smoke-label {
  font-size: 12px; font-weight: 700; fill: var(--dgm-text-main);
  font-family: "JetBrains Mono", "SFMono-Regular", monospace;
}
.dgm-root .smoke-actor {
  font-size: 10px; letter-spacing: 0.12em; font-weight: 800;
  fill: var(--dgm-text-muted);
}
.dgm-root .smoke-postmortem {
  fill: var(--dgm-bg-2); stroke: var(--dgm-edge-shared);
  stroke-width: 1.6; stroke-dasharray: 8 5;
}
.dgm-root .smoke-class-ok    { fill: var(--dgm-state-success); }
.dgm-root .smoke-class-blocked{ fill: var(--dgm-state-warn); }
.dgm-root .smoke-class-skip  { fill: var(--dgm-text-muted); }
`;

export function CicdSmokeDiscipline() {
  return (
    <div className="dgm-root">
      <style>{STYLES}</style>
      <svg viewBox="0 0 1200 920" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Smoke-testing discipline — label state machine, agent-side probes, postmortem loop, bug-family audit">
        <defs>
          <DiagramMarkers />
        </defs>

        {/* Title */}
        <text x="600" y="42" textAnchor="middle" className="title" fontSize="22">
          Smoke-testing discipline (v0.5.75 reckoning)
        </text>
        <text x="600" y="68" textAnchor="middle" className="detail" fontSize="13">
          How an issue moves from <tspan className="mono">status:in-progress</tspan> to <tspan className="mono">status:released</tspan> — and what gates each transition.
        </text>

        {/* ─── LAYER 1: Label state machine (top horizontal flow) ─── */}
        <text x="60" y="110" className="cicd-track-label">RELEASE LIFECYCLE (LABEL STATE)</text>

        {/* Chips with gates between them */}
        {/* Chip 1 — in-progress */}
        <rect x="40" y="130" width="180" height="60" rx="10" className="smoke-chip" />
        <text x="130" y="156" textAnchor="middle" className="smoke-label">status:in-progress</text>
        <text x="130" y="174" textAnchor="middle" className="smoke-actor">AGENT FLIPS</text>
        <text x="130" y="186" textAnchor="middle" className="muted" fontSize="10">on first commit Refs #N</text>

        {/* Gate A: agent-side smoke */}
        <polygon points="240,130 280,160 240,190 220,160" className="smoke-gate" />
        <text x="250" y="218" textAnchor="middle" className="smoke-actor" fill="var(--dgm-state-warn)">GATE A</text>
        <text x="250" y="232" textAnchor="middle" className="muted" fontSize="10">agent-side</text>
        <text x="250" y="246" textAnchor="middle" className="muted" fontSize="10">end-to-end probes</text>

        {/* Arrow to chip 2 */}
        <path className="edge compose" d="M 220 160 L 220 160 M 280 160 L 290 160" />
        <path className="edge compose" d="M 280 160 L 290 160" />

        {/* Chip 2 — ready-for-testing */}
        <rect x="300" y="130" width="190" height="60" rx="10" className="smoke-chip" />
        <text x="395" y="156" textAnchor="middle" className="smoke-label">status:ready-for-testing</text>
        <text x="395" y="174" textAnchor="middle" className="smoke-actor">AGENT FLIPS</text>
        <text x="395" y="186" textAnchor="middle" className="muted" fontSize="10">after probes pass</text>

        {/* Gate B: operator hands-on */}
        <polygon points="510,130 550,160 510,190 490,160" className="smoke-gate" />
        <text x="520" y="218" textAnchor="middle" className="smoke-actor" fill="var(--dgm-state-warn)">GATE B</text>
        <text x="520" y="232" textAnchor="middle" className="muted" fontSize="10">operator hands-on</text>
        <text x="520" y="246" textAnchor="middle" className="muted" fontSize="10">smoke on phantom-vm</text>

        {/* Chip 3 — testing-complete */}
        <rect x="560" y="130" width="180" height="60" rx="10" className="smoke-chip" />
        <text x="650" y="156" textAnchor="middle" className="smoke-label">status:testing-complete</text>
        <text x="650" y="174" textAnchor="middle" className="smoke-actor">OPERATOR FLIPS</text>
        <text x="650" y="186" textAnchor="middle" className="muted" fontSize="10">via chat / label edit</text>

        {/* Gate C: chat approval */}
        <polygon points="760,130 800,160 760,190 740,160" className="smoke-gate" />
        <text x="770" y="218" textAnchor="middle" className="smoke-actor" fill="var(--dgm-state-warn)">GATE C</text>
        <text x="770" y="232" textAnchor="middle" className="muted" fontSize="10">operator chat</text>
        <text x="770" y="246" textAnchor="middle" className="muted" fontSize="10">approval phrase</text>

        {/* Chip 4 — release-approved */}
        <rect x="810" y="130" width="180" height="60" rx="10" className="smoke-chip-active" />
        <text x="900" y="156" textAnchor="middle" className="smoke-label">status:release-approved</text>
        <text x="900" y="174" textAnchor="middle" className="smoke-actor">OPERATOR FLIPS</text>
        <text x="900" y="186" textAnchor="middle" className="muted" fontSize="10">metadata-only flag</text>

        {/* Gate D: tag push */}
        <polygon points="1010,130 1050,160 1010,190 990,160" className="smoke-gate" />
        <text x="1020" y="218" textAnchor="middle" className="smoke-actor" fill="var(--dgm-state-warn)">GATE D</text>
        <text x="1020" y="232" textAnchor="middle" className="muted" fontSize="10">git tag vX.Y.Z</text>
        <text x="1020" y="246" textAnchor="middle" className="muted" fontSize="10">+ release.yml fires</text>

        {/* Chip 5 — released */}
        <rect x="1060" y="130" width="120" height="60" rx="10" className="smoke-chip-final" />
        <text x="1120" y="156" textAnchor="middle" className="smoke-label">status:released</text>
        <text x="1120" y="174" textAnchor="middle" className="smoke-actor">AGENT FLIPS</text>
        <text x="1120" y="186" textAnchor="middle" className="muted" fontSize="10">+ closes issue</text>

        {/* Arrows between chips */}
        <path className="edge compose" d="M 220 160 L 220 160" />
        <path className="edge compose" d="M 280 160 L 300 160" />
        <path className="edge compose" d="M 490 160 L 560 160" />
        <path className="edge compose" d="M 740 160 L 810 160" />
        <path className="edge compose" d="M 990 160 L 1060 160" />

        {/* ─── LAYER 2: The 6 agent-side probe rules ─── */}
        <text x="60" y="290" className="cicd-track-label">GATE A — AGENT-SIDE PROBES (v0.5.75 CLAUDE.md ADDENDUM)</text>

        {[
          { num: "1", title: "Execute, don't trace", body: "Run the smoke bullet via tunnel + curl/Playwright. Not 'I read the code and it looks right.'" },
          { num: "2", title: "State verification", body: "Every \"X happens\" bullet paired with \"GET shows X persisted in expected shape.\"" },
          { num: "3", title: "E2E probe (connector-system)", body: "Touched connector code? POST /instances/<id>/test + tools/call round-trip. Confirm non-error response." },
        ].map((r, i) => (
          <g key={r.num}>
            <rect x={40 + i * 380} y="310" width="360" height="120" rx="10" className="smoke-rule" />
            <text x={60 + i * 380} y="340" className="smoke-rule-num">{r.num}</text>
            <text x={95 + i * 380} y="340" className="node-title-small">{r.title}</text>
            <foreignObject x={60 + i * 380} y="350" width="330" height="80">
              <div style={{ fontSize: 12, color: "var(--dgm-text-soft)", lineHeight: 1.4, fontFamily: "system-ui, sans-serif" }}>
                {r.body}
              </div>
            </foreignObject>
          </g>
        ))}

        {[
          { num: "4", title: "Dev-cycle gaps LEAD the matrix", body: "Updater/browser fix? Top of matrix: \"only ships at customer release tag.\" Never bury in prose." },
          { num: "5", title: "Inline state classification", body: "Each bullet gets ✓ agent-verified, ⨯ agent-verified-blocked, or ? agent-skipped. Operator sees what's done." },
          { num: "6", title: "Postmortem-driven growth", body: "Operator catches a bug in dev-built code? Next release ships a CLAUDE.md addendum naming the gap." },
        ].map((r, i) => (
          <g key={r.num}>
            <rect x={40 + i * 380} y="450" width="360" height="120" rx="10" className="smoke-rule" />
            <text x={60 + i * 380} y="480" className="smoke-rule-num">{r.num}</text>
            <text x={95 + i * 380} y="480" className="node-title-small">{r.title}</text>
            <foreignObject x={60 + i * 380} y="490" width="330" height="80">
              <div style={{ fontSize: 12, color: "var(--dgm-text-soft)", lineHeight: 1.4, fontFamily: "system-ui, sans-serif" }}>
                {r.body}
              </div>
            </foreignObject>
          </g>
        ))}

        {/* Rule 7 — v0.5.80 addition. Compact full-width strip to keep
            the rest of the layout in place. Bordered with the "shared"
            accent so it visually reads as a discipline ADDITION rather
            than an original rule. */}
        <rect x="40" y="585" width="1120" height="48" rx="10" className="smoke-rule" stroke="var(--dgm-edge-shared)" strokeWidth="1.6" />
        <text x="60" y="615" className="smoke-rule-num" fill="var(--dgm-edge-shared)">7</text>
        <text x="95" y="612" className="node-title-small">Bug-family audit (v0.5.80+)</text>
        <text x="95" y="626" className="node-detail-small" fontSize="11">
          Fixing a connector bug? grep the pattern across sibling connectors + fix all instances in the same release.
        </text>

        {/* ─── LAYER 3: state classification + postmortem loop ───
            All coordinates shifted +45 from the v0.5.79 layout to make
            room for the v0.5.80 Rule 7 strip above. */}
        <text x="60" y="660" className="cicd-track-label">BULLET STATE CLASSIFICATION</text>

        <rect x="40" y="675" width="540" height="190" rx="12" className="smoke-rule" />

        {/* ✓ agent-verified */}
        <circle cx="70" cy="705" r="10" className="smoke-class-ok" />
        <text x="86" y="709" className="node-title-small">✓ agent-verified</text>
        <text x="60" y="727" className="detail" fontSize="12">
          I ran this bullet through the tunnel. The expected result happened.
        </text>
        <text x="60" y="743" className="muted" fontSize="11">
          Example: GET /api/v1/instances/&lt;id&gt; returns secrets.api_key=&quot;***&quot;.
        </text>

        {/* ⨯ agent-verified-blocked */}
        <circle cx="70" cy="775" r="10" className="smoke-class-blocked" />
        <text x="86" y="779" className="node-title-small">⨯ agent-verified-blocked</text>
        <text x="60" y="797" className="detail" fontSize="12">
          I tried but a known gap prevented full verification. Operator hands-on still needed.
        </text>
        <text x="60" y="813" className="muted" fontSize="11">
          Example: updater/main.py fix in dev — won&apos;t ship until customer release tag fires.
        </text>

        {/* ? agent-skipped */}
        <circle cx="70" cy="835" r="10" className="smoke-class-skip" />
        <text x="86" y="839" className="node-title-small">? agent-skipped</text>
        <text x="60" y="855" className="muted" fontSize="11">
          Operator hands-on is the primary verification (UI rendering, theme toggle, etc.).
        </text>

        {/* Postmortem loop panel */}
        <text x="600" y="660" className="cicd-track-label">POSTMORTEM LOOP (RULES 6+7)</text>

        <rect x="600" y="675" width="560" height="190" rx="12" className="smoke-postmortem" />

        {/* Top arrow: bug found */}
        <rect x="620" y="700" width="160" height="40" rx="8" className="smoke-chip" />
        <text x="700" y="723" textAnchor="middle" className="node-title-small" style={{fontSize: 13}}>operator finds bug</text>
        <text x="700" y="735" textAnchor="middle" className="muted" fontSize="10">in dev-built code</text>

        {/* Down arrow */}
        <path className="edge shared" d="M 700 740 L 700 765" />

        {/* Middle: discipline gap named */}
        <rect x="600" y="770" width="240" height="50" rx="8" className="smoke-chip" />
        <text x="720" y="793" textAnchor="middle" className="node-title-small" style={{fontSize: 13}}>identify the smoke gap</text>
        <text x="720" y="807" textAnchor="middle" className="muted" fontSize="10">which rule would have caught it?</text>

        {/* Right arrow */}
        <path className="edge shared" d="M 840 795 L 870 795" />

        {/* Right: CLAUDE.md addendum */}
        <rect x="880" y="770" width="260" height="50" rx="8" className="smoke-chip-active" />
        <text x="1010" y="793" textAnchor="middle" className="node-title-small" style={{fontSize: 13}}>next release ships addendum</text>
        <text x="1010" y="807" textAnchor="middle" className="muted" fontSize="10">CLAUDE.md or docs/CICD.md</text>

        {/* Loop back arrow */}
        <path className="edge shared" d="M 1010 770 Q 1010 730 990 705 L 800 705" />

        {/* Examples annotation */}
        <text x="880" y="840" className="muted" fontSize="11">
          v0.5.76/77/80 are the working examples:
        </text>
        <text x="880" y="855" className="muted" fontSize="10">
          three bugs caught by the discipline; v0.5.80 added Rule 7.
        </text>

        {/* Examples on left side too */}
        <text x="620" y="845" className="muted" fontSize="10">
          v0.5.75 itself was the postmortem for the
        </text>
        <text x="620" y="858" className="muted" fontSize="10">
          v0.5.67/70/73/74 + #48 five-in-a-row stretch.
        </text>
      </svg>
    </div>
  );
}
