/**
 * CICD diagram 3/5 — Three change scenarios (decision tree).
 *
 * Visualizes the CLAUDE.md / docs/CICD.md classification of every
 * non-trivial change into one of three scenarios. The classification
 * drives:
 *   - Version bump rule (minor vs MAJOR)
 *   - Customer's required action (re-run existing installer vs
 *     download new installer)
 *   - Volume fate (preserved vs operator-manual-backup-then-wipe)
 *
 * Decision tree (depth 2):
 *
 *   Did the change touch the installer template (installer/** or
 *   release.yml's installer-packing step)?
 *     - NO  → Scenario 1 (code-only)
 *     - YES → Did storage schema change in a backwards-incompatible way?
 *               - NO  → Scenario 2 (code + installer change, BC storage)
 *               - YES → Scenario 3 (BC-incompatible storage)
 *
 * This is the canonical map every release goes through. Mis-classifying
 * a change as Scenario 1 when it's actually Scenario 2 produces broken
 * customer upgrades — they re-run the OLD installer + get the new
 * digests but with the OLD compose-template, which may reference
 * env vars or volumes the new images expect to exist.
 */

import { DIAGRAM_THEME_CSS, DiagramMarkers } from "./_diagram-theme";

const STYLES = DIAGRAM_THEME_CSS + `
.dgm-root .scn-decision {
  fill: var(--dgm-node-fill-strong); stroke: var(--dgm-state-warn);
  stroke-width: 2;
}
.dgm-root .scn-1 { fill: var(--dgm-node-fill); stroke: var(--dgm-state-success); stroke-width: 2.4; }
.dgm-root .scn-2 { fill: var(--dgm-node-fill); stroke: var(--dgm-state-info); stroke-width: 2.4; }
.dgm-root .scn-3 { fill: var(--dgm-node-fill); stroke: var(--dgm-state-error); stroke-width: 2.4; }
.dgm-root .scn-1-text { fill: var(--dgm-state-success); }
.dgm-root .scn-2-text { fill: var(--dgm-state-info); }
.dgm-root .scn-3-text { fill: var(--dgm-state-error); }
.dgm-root .scn-row-label {
  font-size: 11px; font-weight: 800; letter-spacing: 0.08em;
  fill: var(--dgm-text-muted);
}
`;

export function CicdChangeScenarios() {
  return (
    <div className="dgm-root">
      <style>{STYLES}</style>
      <svg viewBox="0 0 1200 760" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Three change scenarios decision tree — classifying a release as scenario 1, 2, or 3">
        <defs>
          <DiagramMarkers />
        </defs>

        {/* Title */}
        <text x="600" y="42" textAnchor="middle" className="title" fontSize="22">
          Three change scenarios: classify before tagging
        </text>
        <text x="600" y="68" textAnchor="middle" className="detail" fontSize="13">
          Every release falls into one. The scenario sets the version bump, customer action, and volume fate.
        </text>

        {/* Decision diamond 1 */}
        <polygon points="600,110 760,180 600,250 440,180" className="scn-decision" />
        <text x="600" y="170" textAnchor="middle" className="node-title-small">Touched the installer?</text>
        <text x="600" y="190" textAnchor="middle" className="muted" fontSize="11">installer/** OR release.yml install-kit step</text>
        <text x="600" y="208" textAnchor="middle" className="muted" fontSize="11">OR docker-compose.yml template</text>

        {/* Arrow: NO → Scenario 1 */}
        <path className="edge muted" d="M 440 180 L 280 180 L 280 320" />
        <rect x="220" y="170" width="40" height="20" rx="4" className="badge" />
        <text x="240" y="184" textAnchor="middle" className="edge-label-text-small">NO</text>

        {/* Arrow: YES → Decision 2 */}
        <path className="edge muted" d="M 760 180 L 900 180 L 900 290" />
        <rect x="850" y="170" width="40" height="20" rx="4" className="badge" />
        <text x="870" y="184" textAnchor="middle" className="edge-label-text-small">YES</text>

        {/* Decision diamond 2 */}
        <polygon points="900,290 1060,360 900,430 740,360" className="scn-decision" />
        <text x="900" y="350" textAnchor="middle" className="node-title-small">BC-incompatible storage?</text>
        <text x="900" y="370" textAnchor="middle" className="muted" fontSize="11">SecretStore KEK change, DB schema</text>
        <text x="900" y="388" textAnchor="middle" className="muted" fontSize="11">migration that can&apos;t be auto-handled</text>

        {/* Arrow: Decision 2 NO → Scenario 2 */}
        <path className="edge muted" d="M 740 360 L 620 360 L 620 470" />
        <rect x="560" y="350" width="40" height="20" rx="4" className="badge" />
        <text x="580" y="364" textAnchor="middle" className="edge-label-text-small">NO</text>

        {/* Arrow: Decision 2 YES → Scenario 3 */}
        <path className="edge muted" d="M 1060 360 L 1090 360 L 1090 470" />
        <rect x="1100" y="350" width="40" height="20" rx="4" className="badge" />
        <text x="1120" y="364" textAnchor="middle" className="edge-label-text-small">YES</text>

        {/* SCENARIO 1 */}
        <rect x="100" y="320" width="360" height="280" rx="14" className="scn-1" />
        <text x="280" y="354" textAnchor="middle" className="scn-1-text" style={{fontSize: 22, fontWeight: 800}}>SCENARIO 1</text>
        <text x="280" y="378" textAnchor="middle" className="node-subtitle">Code-only · installer unchanged</text>

        <text x="120" y="412" className="scn-row-label">VERSION BUMP</text>
        <text x="280" y="412" textAnchor="middle" className="node-title-small">minor (v5.29 → v5.30)</text>

        <text x="120" y="450" className="scn-row-label">CUSTOMER ACTION</text>
        <text x="280" y="468" textAnchor="middle" className="detail" fontSize="12">Re-run EXISTING installer on disk</text>
        <text x="280" y="484" textAnchor="middle" className="muted" fontSize="11">/opt/guardian/guardian-installer</text>
        <text x="280" y="500" textAnchor="middle" className="muted" fontSize="11">(no fresh download required)</text>

        <text x="120" y="528" className="scn-row-label">VOLUME FATE</text>
        <text x="280" y="546" textAnchor="middle" className="state-success-fill" fontSize="13">Preserved</text>
        <text x="280" y="562" textAnchor="middle" className="muted" fontSize="11">unchanged containers stay running;</text>
        <text x="280" y="578" textAnchor="middle" className="muted" fontSize="11">in-memory state survives the upgrade</text>

        {/* SCENARIO 2 */}
        <rect x="480" y="470" width="280" height="280" rx="14" className="scn-2" />
        <text x="620" y="504" textAnchor="middle" className="scn-2-text" style={{fontSize: 22, fontWeight: 800}}>SCENARIO 2</text>
        <text x="620" y="528" textAnchor="middle" className="node-subtitle">Code + installer · BC storage</text>

        <text x="500" y="562" className="scn-row-label">VERSION BUMP</text>
        <text x="620" y="582" textAnchor="middle" className="node-title-small">MAJOR (v5.29 → v6.0)</text>

        <text x="500" y="610" className="scn-row-label">CUSTOMER ACTION</text>
        <text x="620" y="628" textAnchor="middle" className="detail" fontSize="12">Download NEW installer</text>
        <text x="620" y="644" textAnchor="middle" className="muted" fontSize="11">flag: WIPE_VOLUMES=false (default)</text>

        <text x="500" y="672" className="scn-row-label">VOLUME FATE</text>
        <text x="620" y="690" textAnchor="middle" className="state-success-fill" fontSize="13">Preserved (via installer flag)</text>
        <text x="620" y="706" textAnchor="middle" className="muted" fontSize="11">new compose template applies;</text>
        <text x="620" y="722" textAnchor="middle" className="muted" fontSize="11">named volumes round-trip</text>

        {/* SCENARIO 3 */}
        <rect x="960" y="470" width="220" height="280" rx="14" className="scn-3" />
        <text x="1070" y="504" textAnchor="middle" className="scn-3-text" style={{fontSize: 22, fontWeight: 800}}>SCENARIO 3</text>
        <text x="1070" y="528" textAnchor="middle" className="node-subtitle">BC-incompat storage</text>

        <text x="975" y="562" className="scn-row-label">VERSION BUMP</text>
        <text x="1070" y="582" textAnchor="middle" className="node-title-small">MAJOR</text>

        <text x="975" y="610" className="scn-row-label">CUSTOMER ACTION</text>
        <text x="1070" y="628" textAnchor="middle" className="detail" fontSize="11">Download NEW installer</text>
        <text x="1070" y="642" textAnchor="middle" className="muted" fontSize="10">WIPE_VOLUMES=true</text>

        <text x="975" y="668" className="scn-row-label">VOLUME FATE</text>
        <text x="1070" y="686" textAnchor="middle" className="state-error-fill" fontSize="13">Wiped → defaults</text>
        <text x="1070" y="702" textAnchor="middle" className="muted" fontSize="10">backup BEFORE upgrade is</text>
        <text x="1070" y="716" textAnchor="middle" className="muted" fontSize="10">operator-manual (no auto-backup)</text>
      </svg>
    </div>
  );
}
