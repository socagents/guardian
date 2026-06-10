/**
 * CICD diagram 2/5 — Build pipeline trigger model.
 *
 * Visualizes how `git push origin main` cascades through:
 *
 *   - 3 per-service workflows (build-agent, build-connectors,
 *     build-updater) each gated by a path filter on the
 *     source paths it owns. A push touching only mcp/agent/** triggers
 *     ONLY build-agent (updater/connectors stay untouched + retain
 *     their previous :dev digest).
 *
 *   - workflow_run trigger: build-dev-installer fires automatically
 *     after ANY of the three per-service workflows finishes, even if
 *     only one ran. It re-resolves :dev tags into digests + republishes
 *     the dev-installer binary as the `dev-latest` GitHub prerelease.
 *
 *   - guardian-browser DOESN'T rebuild on dev. The dev-installer
 *     pulls its digest from the latest customer release manifest
 *     ("STABLE-ADVANCED" carve-out). Fixes that touch
 *     guardian-browser/ only reach customers on a customer release
 *     tag, not on dev push.
 *
 * This is the load-bearing diagram for understanding why some fixes
 * (agent/connectors/updater) ship to dev immediately + others
 * (browser) need a customer release tag to reach operators.
 */

import { DIAGRAM_THEME_CSS, DiagramMarkers } from "./_diagram-theme";

const STYLES = DIAGRAM_THEME_CSS + `
.dgm-root .pipe-trigger {
  fill: var(--dgm-node-fill-strong); stroke: var(--dgm-edge-operator);
  stroke-width: 2;
}
.dgm-root .pipe-job {
  fill: var(--dgm-node-fill); stroke: var(--dgm-stroke-strong);
  stroke-width: 1.6;
}
.dgm-root .pipe-installer {
  fill: var(--dgm-node-fill-strong); stroke: var(--dgm-edge-compose);
  stroke-width: 2;
}
.dgm-root .pipe-skipped {
  fill: var(--dgm-bg-1); stroke: var(--dgm-text-muted);
  stroke-width: 1.4; stroke-dasharray: 6 5;
}
.dgm-root .pipe-pathfilter {
  font-size: 11px; fill: var(--dgm-text-muted);
  font-family: "JetBrains Mono", "SFMono-Regular", monospace;
}
`;

export function CicdBuildPipeline() {
  return (
    <div className="dgm-root">
      <style>{STYLES}</style>
      <svg viewBox="0 0 1200 760" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Build pipeline trigger model — path-filtered per-service workflows + workflow_run cascade">
        <defs>
          <DiagramMarkers />
        </defs>

        {/* Title */}
        <text x="600" y="42" textAnchor="middle" className="title" fontSize="22">
          Build pipeline: path filters + workflow_run cascade
        </text>
        <text x="600" y="68" textAnchor="middle" className="detail" fontSize="13">
          A push to main triggers only the services whose paths changed. dev-installer republishes once any upstream finishes.
        </text>

        {/* TRIGGER node — top center */}
        <rect x="450" y="100" width="300" height="74" rx="14" className="pipe-trigger" />
        <text x="600" y="130" textAnchor="middle" className="cicd-card-title" style={{fontSize: 16}}>git push origin main</text>
        <text x="600" y="152" textAnchor="middle" className="node-subtitle">commit touches one or more source paths</text>

        {/* Lane labels */}
        <text x="60" y="220" className="cicd-track-label">PATH FILTERS</text>
        <text x="60" y="430" className="cicd-track-label">DEV CASCADE</text>
        <text x="60" y="640" className="cicd-track-label">CUSTOMER ONLY</text>

        {/* 3 per-service workflows */}
        {[
          { x: 150, name: "build-agent.yml", paths: "mcp/agent/** OR bundles/spark/**", image: "guardian-agent:dev" },
          { x: 480, name: "build-connectors.yml", paths: "bundles/spark/connectors/**", image: "guardian-connector-*:dev" },
          { x: 810, name: "build-updater.yml", paths: "updater/**", image: "guardian-updater:dev" },
        ].map((s) => (
          <g key={s.name}>
            <rect x={s.x} y="240" width="240" height="110" rx="12" className="pipe-job" />
            <text x={s.x + 120} y="268" textAnchor="middle" className="cicd-card-title" style={{fontSize: 14}}>{s.name}</text>
            <text x={s.x + 120} y="290" textAnchor="middle" className="pipe-pathfilter">{s.paths}</text>
            <text x={s.x + 120} y="320" textAnchor="middle" className="node-subtitle">{s.image}</text>
            <text x={s.x + 120} y="338" textAnchor="middle" className="muted" fontSize="10">push to GHCR</text>
          </g>
        ))}

        {/* Arrows from trigger to each job */}
        <path className="edge operator" d="M 550 174 Q 480 200 270 240" />
        <path className="edge operator" d="M 600 174 L 600 240" />
        <path className="edge operator" d="M 650 174 Q 720 200 930 240" />

        {/* dev-installer cascade — single workflow_run target */}
        <rect x="280" y="450" width="640" height="90" rx="14" className="pipe-installer" />
        <text x="600" y="478" textAnchor="middle" className="cicd-card-title">build-dev-installer.yml (workflow_run cascade)</text>
        <text x="600" y="500" textAnchor="middle" className="node-subtitle">re-resolves :dev tags into digests + writes manifest.env</text>
        <text x="600" y="520" textAnchor="middle" className="muted" fontSize="11">
          → publishes `dev-latest` GitHub prerelease · stages /home/$USER/guardian-installer-dev on self-hosted runner
        </text>

        {/* Arrows from each job to dev-installer */}
        <path className="edge compose" d="M 270 350 Q 290 400 400 450" />
        <path className="edge compose" d="M 600 350 L 600 450" />
        <path className="edge compose" d="M 930 350 Q 910 400 800 450" />

        {/* STABLE-ADVANCED carve-out — bottom row, dashed boxes */}
        <rect x="60" y="600" width="500" height="120" rx="12" className="pipe-skipped" />
        <text x="310" y="628" textAnchor="middle" className="cicd-card-title" style={{fontSize: 14}}>guardian-browser</text>
        <text x="310" y="650" textAnchor="middle" className="node-subtitle">NOT built on dev cycle</text>
        <text x="310" y="672" textAnchor="middle" className="muted" fontSize="11">dev-installer pulls its digest from the latest</text>
        <text x="310" y="688" textAnchor="middle" className="muted" fontSize="11">customer release manifest (STABLE-ADVANCED)</text>
        <text x="310" y="708" textAnchor="middle" className="state-warn-fill" fontSize="11" fontFamily='"JetBrains Mono", monospace'>
          fixes here need a vX.Y.Z customer tag to reach operators
        </text>

        <rect x="640" y="600" width="500" height="120" rx="12" className="pipe-job" />
        <text x="890" y="628" textAnchor="middle" className="cicd-card-title" style={{fontSize: 14}}>release.yml (on tag push)</text>
        <text x="890" y="650" textAnchor="middle" className="node-subtitle">git tag vX.Y.Z && git push origin vX.Y.Z</text>
        <text x="890" y="672" textAnchor="middle" className="muted" fontSize="11">rebuilds ALL 9 images (or retags unchanged ones)</text>
        <text x="890" y="688" textAnchor="middle" className="muted" fontSize="11">incl. guardian-browser</text>
        <text x="890" y="708" textAnchor="middle" className="state-success-fill" fontSize="11" fontFamily='"JetBrains Mono", monospace'>
          this is when browser fixes actually ship
        </text>

        {/* Arrow from dev-installer down to stable advanced (to indicate "pulls from") */}
        <path className="edge muted" d="M 350 540 Q 320 570 310 600" />
        <text x="240" y="580" className="edge-label-text" fontSize="11">pulls digests from</text>

        {/* Legend */}
        <rect x="40" y="730" width="1120" height="20" rx="6" className="badge" />
        <line x1="60" y1="740" x2="90" y2="740" className="edge operator" markerEnd="" />
        <text x="100" y="744" className="legend-text">trigger</text>
        <line x1="240" y1="740" x2="270" y2="740" className="edge compose" markerEnd="" />
        <text x="280" y="744" className="legend-text">workflow_run cascade</text>
        <line x1="490" y1="740" x2="520" y2="740" className="edge muted" markerEnd="" />
        <text x="530" y="744" className="legend-text">references stable digests</text>
        <rect x="780" y="734" width="14" height="12" rx="3" className="pipe-skipped" />
        <text x="800" y="744" className="legend-text">dashed = not rebuilt on dev cycle</text>
      </svg>
    </div>
  );
}
