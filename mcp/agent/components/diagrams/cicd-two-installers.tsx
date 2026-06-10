/**
 * CICD diagram 1/5 — Two Installers (dev vs customer).
 *
 * Visualizes the load-bearing "local-mirrors-customer" design principle
 * from docs/CICD.md § The two installers:
 *   - Same install ceremony (extract → write /opt/guardian/.env → docker
 *     compose pull + up -d → optional first-time setup)
 *   - Same compose template shape (installer/docker-compose.yml)
 *   - Same install location (/opt/guardian)
 *   - Same env-file format
 *
 *   - Different ONLY in which image digests get baked at build time:
 *       dev-installer:      :dev tags resolved at build-dev-installer.yml time
 *       customer-installer: content digests pinned by release.yml at tag time
 *
 * The customer installer has zero knowledge of dev — no flags, no
 * branches, no toggles. That symmetry is what makes "smoke test the
 * dev install path" equivalent to "smoke test the customer install
 * path." Diagram surfaces the symmetry by placing dev + customer
 * side-by-side with a SHARED middle column showing the parts they
 * both produce identically.
 */

import { DIAGRAM_THEME_CSS, DiagramMarkers } from "./_diagram-theme";

const STYLES = DIAGRAM_THEME_CSS + `
.dgm-root .cicd-track-label {
  font-size: 14px; font-weight: 800; letter-spacing: 0.12em;
  fill: var(--dgm-text-soft);
}
.dgm-root .cicd-card-title {
  font-size: 17px; font-weight: 780; fill: var(--dgm-text-main);
}
.dgm-root .cicd-divider {
  stroke: var(--dgm-stroke-muted); stroke-width: 1.2; stroke-dasharray: 6 6;
}
.dgm-root .cicd-shared-fill {
  fill: var(--dgm-edge-shared); fill-opacity: 0.10;
  stroke: var(--dgm-edge-shared); stroke-width: 1.4;
}
.dgm-root .cicd-diff-fill {
  fill: var(--dgm-edge-info); fill-opacity: 0.10;
  stroke: var(--dgm-state-info); stroke-width: 1.4;
}
`;

export function CicdTwoInstallers() {
  return (
    <div className="dgm-root">
      <style>{STYLES}</style>
      <svg viewBox="0 0 1200 720" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Dev installer vs customer installer — what's shared, what differs">
        <defs>
          <DiagramMarkers />
        </defs>

        {/* Title */}
        <text x="600" y="42" textAnchor="middle" className="title" fontSize="22">
          Two Installers, One Ceremony
        </text>
        <text x="600" y="68" textAnchor="middle" className="detail" fontSize="13">
          Same compose shape · Same /opt/guardian layout · Same env-file format · Different image digests baked at build time
        </text>

        {/* Track labels */}
        <text x="170" y="110" textAnchor="middle" className="cicd-track-label">DEV INSTALLER</text>
        <text x="600" y="110" textAnchor="middle" className="cicd-track-label" fill="var(--dgm-edge-shared)">SHARED</text>
        <text x="1030" y="110" textAnchor="middle" className="cicd-track-label">CUSTOMER INSTALLER</text>

        {/* DEV column — top: source */}
        <rect x="40" y="130" width="260" height="100" rx="12" className="node-shape" />
        <text x="170" y="158" textAnchor="middle" className="cicd-card-title">build-dev-installer.yml</text>
        <text x="170" y="180" textAnchor="middle" className="node-subtitle">resolves :dev tags</text>
        <text x="170" y="200" textAnchor="middle" className="node-detail-small">→ DIGEST_GUARDIAN_AGENT=&lt;today&apos;s :dev&gt;</text>
        <text x="170" y="216" textAnchor="middle" className="node-detail-small">+ updater/browser from stable</text>

        {/* SHARED column — top */}
        <rect x="380" y="130" width="440" height="100" rx="12" className="cicd-shared-fill" />
        <text x="600" y="158" textAnchor="middle" className="cicd-card-title">manifest.env (DIGEST_* pins)</text>
        <text x="600" y="180" textAnchor="middle" className="node-detail">Both installers produce ONE env file with the same key set;</text>
        <text x="600" y="198" textAnchor="middle" className="node-detail">only the digest VALUES differ. Same format, same parser.</text>

        {/* CUSTOMER column — top */}
        <rect x="900" y="130" width="260" height="100" rx="12" className="node-shape" />
        <text x="1030" y="158" textAnchor="middle" className="cicd-card-title">release.yml on vX.Y.Z tag</text>
        <text x="1030" y="180" textAnchor="middle" className="node-subtitle">pins content digests</text>
        <text x="1030" y="200" textAnchor="middle" className="node-detail-small">→ DIGEST_GUARDIAN_AGENT=&lt;sha256:...&gt;</text>
        <text x="1030" y="216" textAnchor="middle" className="node-detail-small">+ updater/browser rebuilt or retagged</text>

        {/* Down arrows */}
        <path className="edge muted" d="M 170 230 L 170 270" />
        <path className="edge muted" d="M 1030 230 L 1030 270" />

        {/* DEV — middle: package */}
        <rect x="40" y="280" width="260" height="80" rx="12" className="node-shape" />
        <text x="170" y="308" textAnchor="middle" className="cicd-card-title">guardian-installer-dev</text>
        <text x="170" y="332" textAnchor="middle" className="node-subtitle">self-extracting binary</text>
        <text x="170" y="350" textAnchor="middle" className="muted" fontSize="11">staged at /home/$USER/guardian-installer-dev</text>

        {/* CUSTOMER — middle: package */}
        <rect x="900" y="280" width="260" height="80" rx="12" className="node-shape" />
        <text x="1030" y="308" textAnchor="middle" className="cicd-card-title">guardian-installer</text>
        <text x="1030" y="332" textAnchor="middle" className="node-subtitle">self-extracting binary</text>
        <text x="1030" y="350" textAnchor="middle" className="muted" fontSize="11">attached to GHCR release vX.Y.Z</text>

        {/* SHARED — middle: install ceremony (the load-bearing box) */}
        <rect x="380" y="270" width="440" height="240" rx="14" className="cicd-shared-fill" />
        <text x="600" y="296" textAnchor="middle" className="cicd-card-title">Install ceremony (identical)</text>
        <text x="600" y="316" textAnchor="middle" className="detail" fontSize="12">
          1. Extract installer payload to /opt/guardian
        </text>
        <text x="600" y="334" textAnchor="middle" className="detail" fontSize="12">
          2. Write manifest.env → /opt/guardian/.env (DIGEST_* pins)
        </text>
        <text x="600" y="352" textAnchor="middle" className="detail" fontSize="12">
          3. docker login ghcr.io (operator&apos;s PAT)
        </text>
        <text x="600" y="370" textAnchor="middle" className="detail" fontSize="12">
          4. docker compose pull (only changed digests pull)
        </text>
        <text x="600" y="388" textAnchor="middle" className="detail" fontSize="12">
          5. docker compose up -d --remove-orphans
        </text>
        <text x="600" y="406" textAnchor="middle" className="detail" fontSize="12">
          6. (first-time only) prompt for admin password
        </text>
        <text x="600" y="424" textAnchor="middle" className="muted" fontSize="11">
          Same compose template (installer/docker-compose.yml).
        </text>
        <text x="600" y="442" textAnchor="middle" className="muted" fontSize="11">
          Same /opt/guardian location. Same volume names.
        </text>
        <text x="600" y="476" textAnchor="middle" className="node-subtitle" fontSize="13">
          Customer installer has ZERO knowledge of dev —
        </text>
        <text x="600" y="494" textAnchor="middle" className="node-subtitle" fontSize="13">
          no flags, no branches, no toggles.
        </text>

        {/* Down arrows from package to ceremony */}
        <path className="edge muted" d="M 170 360 L 170 410 Q 170 440 200 440 L 380 440" />
        <path className="edge muted" d="M 1030 360 L 1030 410 Q 1030 440 1000 440 L 820 440" />

        {/* Bottom — running stack (shared) */}
        <rect x="380" y="540" width="440" height="100" rx="12" className="cicd-shared-fill" />
        <text x="600" y="568" textAnchor="middle" className="cicd-card-title">Running stack</text>
        <text x="600" y="592" textAnchor="middle" className="node-subtitle">5 containers + N per-instance connector containers</text>
        <text x="600" y="612" textAnchor="middle" className="muted" fontSize="11">guardian-agent · xlog · caldera · guardian-updater · guardian-browser (profile-gated)</text>
        <text x="600" y="628" textAnchor="middle" className="muted" fontSize="11">Same image set on dev + customer; only the digest VALUES differ.</text>

        {/* Down arrow from ceremony to running */}
        <path className="edge muted" d="M 600 510 L 600 540" />

        {/* Vertical separators */}
        <path className="cicd-divider" d="M 340 130 L 340 660" />
        <path className="cicd-divider" d="M 860 130 L 860 660" />

        {/* Legend */}
        <rect x="40" y="670" width="1120" height="40" rx="8" className="badge" />
        <circle cx="70" cy="690" r="6" className="cicd-shared-fill" />
        <text x="85" y="694" className="legend-text">Shared — identical on both installers</text>
        <rect x="430" y="684" width="14" height="14" rx="3" className="node-shape" />
        <text x="455" y="694" className="legend-text">Track-specific — only the indicated installer produces this</text>
      </svg>
    </div>
  );
}
