/**
 * CICD diagram 4/5 — release.yml lifecycle from tag push to GitHub
 * release.
 *
 * Visualizes what happens when the operator runs:
 *   git tag vX.Y.Z && git push origin vX.Y.Z
 *
 * Five sequential phases. Each box names the load-bearing concern:
 *
 *   1. Tag-push detection — release.yml's `on: push: tags: ['v*']`
 *      trigger fires. Workflow_dispatch is an alternative trigger
 *      that runs the same pipeline at HEAD (for ad-hoc rebuilds).
 *
 *   2. Detect changed services — compares HEAD against the previous
 *      tag's source paths. For each service: changed=1 → build,
 *      changed=0 → retag-from-prev (bit-identical to last release;
 *      untouched containers retain in-memory state across this
 *      kind of upgrade per the "untouched services" invariant).
 *
 *   3. Per-service build OR retag — services with changes get rebuilt
 *      against the v0.5.0+ docker buildx pipeline; unchanged services
 *      get a `docker pull` of the previous tag's image + `docker tag`
 *      to the new vX.Y.Z (and minor + latest aliases) + `docker push`.
 *
 *   4. Manifest assembly — release-manifest-vX.Y.Z.env file with one
 *      DIGEST_GUARDIAN_* line per service. Customer's /opt/guardian/.env
 *      is overwritten with this manifest at install time.
 *
 *   5. GitHub release publish — installer binary + manifest + tarball
 *      + manifest.sha256 attached as release assets. The "Guardian
 *      vX.Y.Z" release page is what the customer downloads from.
 *
 * Critically: release.yml is the ONLY workflow that rebuilds
 * guardian-browser. Dev cycle never touches it.
 */

import { DIAGRAM_THEME_CSS, DiagramMarkers } from "./_diagram-theme";

const STYLES = DIAGRAM_THEME_CSS + `
.dgm-root .rel-phase {
  fill: var(--dgm-node-fill); stroke: var(--dgm-stroke-strong);
  stroke-width: 1.6;
}
.dgm-root .rel-phase-hero {
  fill: var(--dgm-node-fill-strong); stroke: var(--dgm-edge-compose);
  stroke-width: 2;
}
.dgm-root .rel-phase-num {
  font-size: 28px; font-weight: 800; fill: var(--dgm-edge-compose);
  font-family: "JetBrains Mono", "SFMono-Regular", monospace;
}
.dgm-root .rel-step {
  font-size: 11px; fill: var(--dgm-text-soft);
}
.dgm-root .rel-step-code {
  font-size: 11px; fill: var(--dgm-code);
  font-family: "JetBrains Mono", "SFMono-Regular", monospace;
}
`;

export function CicdReleaseLifecycle() {
  return (
    <div className="dgm-root">
      <style>{STYLES}</style>
      <svg viewBox="0 0 1200 720" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="release.yml lifecycle from tag push to GitHub release publish">
        <defs>
          <DiagramMarkers />
        </defs>

        {/* Title */}
        <text x="600" y="42" textAnchor="middle" className="title" fontSize="22">
          release.yml lifecycle: tag → build/retag → manifest → release
        </text>
        <text x="600" y="68" textAnchor="middle" className="detail" fontSize="13">
          The ONLY workflow that rebuilds guardian-browser. Customer downloads from the GitHub release at the end.
        </text>

        {/* Trigger — top */}
        <rect x="350" y="100" width="500" height="68" rx="12" className="rel-phase-hero" />
        <text x="600" y="128" textAnchor="middle" className="cicd-card-title">
          git tag vX.Y.Z && git push origin vX.Y.Z
        </text>
        <text x="600" y="148" textAnchor="middle" className="muted" fontSize="11">
          (or workflow_dispatch for ad-hoc rebuilds at HEAD)
        </text>

        {/* Down arrow */}
        <path className="edge operator" d="M 600 168 L 600 200" />

        {/* Phase 1 — Detect changed services */}
        <rect x="60" y="210" width="220" height="160" rx="12" className="rel-phase" />
        <text x="80" y="240" className="rel-phase-num">1</text>
        <text x="170" y="266" textAnchor="middle" className="cicd-card-title" style={{fontSize: 15}}>Detect changes</text>
        <text x="170" y="288" textAnchor="middle" className="rel-step">Diff HEAD against the</text>
        <text x="170" y="304" textAnchor="middle" className="rel-step">previous tag&apos;s source paths.</text>
        <text x="170" y="328" textAnchor="middle" className="rel-step-code">CHANGED_AGENT=&lt;0|1&gt;</text>
        <text x="170" y="344" textAnchor="middle" className="rel-step-code">CHANGED_BROWSER=&lt;0|1&gt;</text>
        <text x="170" y="360" textAnchor="middle" className="rel-step-code">...</text>

        {/* Phase 2 — Build/retag per service */}
        <rect x="300" y="210" width="280" height="320" rx="12" className="rel-phase" />
        <text x="320" y="240" className="rel-phase-num">2</text>
        <text x="440" y="266" textAnchor="middle" className="cicd-card-title" style={{fontSize: 15}}>Build or retag (per service)</text>
        <text x="440" y="288" textAnchor="middle" className="rel-step">For each of 9 service images:</text>
        <text x="320" y="320" className="rel-step state-info-fill" fontWeight="700">changed=1</text>
        <text x="320" y="336" className="rel-step-code">docker buildx build</text>
        <text x="320" y="352" className="rel-step-code">+ docker push :vX.Y.Z</text>
        <text x="320" y="368" className="rel-step-code">+ tag latest, vX.Y</text>
        <text x="320" y="400" className="rel-step state-success-fill" fontWeight="700">changed=0</text>
        <text x="320" y="416" className="rel-step-code">docker pull :vPREV</text>
        <text x="320" y="432" className="rel-step-code">+ docker tag :vX.Y.Z</text>
        <text x="320" y="448" className="rel-step-code">+ docker push</text>
        <text x="320" y="464" className="rel-step muted">→ BIT-IDENTICAL to prior tag</text>
        <text x="320" y="488" className="rel-step muted">→ customer compose recognizes</text>
        <text x="320" y="504" className="rel-step muted">same digest = no recreate</text>
        <text x="320" y="520" className="rel-step muted">→ untouched containers&apos; state survives</text>

        {/* Phase 3 — Manifest assembly */}
        <rect x="600" y="210" width="280" height="220" rx="12" className="rel-phase" />
        <text x="620" y="240" className="rel-phase-num">3</text>
        <text x="740" y="266" textAnchor="middle" className="cicd-card-title" style={{fontSize: 15}}>Manifest assembly</text>
        <text x="740" y="288" textAnchor="middle" className="rel-step">Resolve each pushed image to</text>
        <text x="740" y="304" textAnchor="middle" className="rel-step">its content digest (sha256:...).</text>
        <text x="740" y="328" textAnchor="middle" className="rel-step muted">writes:</text>
        <text x="740" y="346" textAnchor="middle" className="rel-step-code">release-manifest-vX.Y.Z.env</text>
        <text x="740" y="374" textAnchor="middle" className="rel-step muted">contents:</text>
        <text x="740" y="390" textAnchor="middle" className="rel-step-code">DIGEST_GUARDIAN_AGENT=sha256:...</text>
        <text x="740" y="406" textAnchor="middle" className="rel-step-code">DIGEST_GUARDIAN_BROWSER=sha256:...</text>
        <text x="740" y="422" textAnchor="middle" className="rel-step-code">DIGEST_GUARDIAN_UPDATER=...</text>

        {/* Phase 4 — GHCR access propagation (per-version access semantics) */}
        <rect x="900" y="210" width="240" height="220" rx="12" className="rel-phase" />
        <text x="920" y="240" className="rel-phase-num">4</text>
        <text x="1020" y="266" textAnchor="middle" className="cicd-card-title" style={{fontSize: 15}}>GHCR per-version access</text>
        <text x="1020" y="288" textAnchor="middle" className="rel-step">Each new image VERSION becomes</text>
        <text x="1020" y="304" textAnchor="middle" className="rel-step">org-readable when associated</text>
        <text x="1020" y="320" textAnchor="middle" className="rel-step">with a GitHub Release.</text>
        <text x="1020" y="346" textAnchor="middle" className="rel-step muted">gh release create vX.Y.Z</text>
        <text x="1020" y="362" textAnchor="middle" className="rel-step muted">→ flips :vX.Y.Z access</text>
        <text x="1020" y="378" textAnchor="middle" className="rel-step muted">from private to org-readable</text>
        <text x="1020" y="406" textAnchor="middle" className="state-warn-fill" fontSize="11">customer PAT (read:packages)</text>
        <text x="1020" y="422" textAnchor="middle" className="state-warn-fill" fontSize="11">can pull only after this step</text>

        {/* Phase 5 — Publish release */}
        <rect x="300" y="560" width="600" height="120" rx="12" className="rel-phase-hero" />
        <text x="320" y="592" className="rel-phase-num">5</text>
        <text x="600" y="612" textAnchor="middle" className="cicd-card-title">GitHub release publish</text>
        <text x="600" y="636" textAnchor="middle" className="rel-step">Attaches as release assets:</text>
        <text x="600" y="654" textAnchor="middle" className="rel-step-code">
          guardian-installer · release-manifest-vX.Y.Z.env · install.tar.gz · manifest.sha256
        </text>
        <text x="600" y="672" textAnchor="middle" className="muted" fontSize="11">
          Customer browses to github.com/.../releases/tag/vX.Y.Z + downloads the installer
        </text>

        {/* Arrows between phases */}
        <path className="edge compose" d="M 280 290 L 300 290" />
        <path className="edge compose" d="M 580 360 L 600 320" />
        <path className="edge compose" d="M 880 320 L 900 320" />
        <path className="edge compose" d="M 600 430 Q 600 510 600 560" />

        {/* Side annotation: This is when updater + browser actually rebuild */}
        <rect x="60" y="430" width="220" height="120" rx="10" className="badge" />
        <text x="170" y="458" textAnchor="middle" className="state-warn-fill" fontSize="12" fontWeight="700">
          ⚠ Critical reminder
        </text>
        <text x="170" y="480" textAnchor="middle" className="rel-step">guardian-browser</text>
        <text x="170" y="496" textAnchor="middle" className="rel-step">rebuilds ONLY here, never on dev push.</text>
        <text x="170" y="518" textAnchor="middle" className="muted" fontSize="11">A fix in guardian-browser/ only</text>
        <text x="170" y="534" textAnchor="middle" className="muted" fontSize="11">reaches customers when this fires.</text>
      </svg>
    </div>
  );
}
