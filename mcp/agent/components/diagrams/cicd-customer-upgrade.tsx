/**
 * CICD diagram 5/5 — Customer upgrade flow.
 *
 * Visualizes the upgrade-day sequence on the customer host, from
 * download to running stack. Highlights the v0.3.0+ image-digest-
 * pinning contract: containers whose IMAGE DIGEST didn't change
 * between releases stay running (no recreate, no state loss);
 * containers whose digest changed get recreated.
 *
 * Flow (per scenario):
 *
 *   SCENARIO 1 (code-only, minor bump):
 *     - Customer re-runs the EXISTING installer at /opt/guardian
 *     - Installer self-updates the manifest pins
 *     - Compose pulls only changed digests
 *     - Unchanged containers (browser, connectors if untouched) keep running
 *
 *   SCENARIO 2 (code + installer change, MAJOR bump, BC storage):
 *     - Customer downloads new installer from the GitHub release
 *     - Runs ./guardian-installer (default WIPE_VOLUMES=false)
 *     - New compose template applies; named volumes round-trip
 *     - Container state survives (digest-pinning + volume preservation)
 *
 *   SCENARIO 3 (BC-incompatible storage, MAJOR bump):
 *     - Customer downloads new installer
 *     - Runs ./guardian-installer with WIPE_VOLUMES=true
 *     - Operator-manual backup BEFORE the run (no auto-backup)
 *     - Volumes wiped, defaults re-seed at first boot
 *
 * The diagram lays out the customer's actual command sequence with
 * arrows showing what each step does to the running state.
 */

import { DIAGRAM_THEME_CSS, DiagramMarkers } from "./_diagram-theme";

const STYLES = DIAGRAM_THEME_CSS + `
.dgm-root .cust-step {
  fill: var(--dgm-node-fill); stroke: var(--dgm-stroke-strong);
  stroke-width: 1.6;
}
.dgm-root .cust-step-num {
  font-size: 22px; font-weight: 800; fill: var(--dgm-edge-operator);
  font-family: "JetBrains Mono", "SFMono-Regular", monospace;
}
.dgm-root .cust-cmd {
  fill: var(--dgm-bg-2); stroke: var(--dgm-stroke-muted);
  stroke-width: 1; rx: 6;
}
.dgm-root .cust-cmd-text {
  font-size: 11px; font-family: "JetBrains Mono", "SFMono-Regular", monospace;
  fill: var(--dgm-code);
}
.dgm-root .cust-outcome {
  font-size: 11px; fill: var(--dgm-text-soft);
}
`;

export function CicdCustomerUpgrade() {
  return (
    <div className="dgm-root">
      <style>{STYLES}</style>
      <svg viewBox="0 0 1200 760" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Customer upgrade flow — download, install, container reconciliation">
        <defs>
          <DiagramMarkers />
        </defs>

        {/* Title */}
        <text x="600" y="42" textAnchor="middle" className="title" fontSize="22">
          Customer upgrade flow
        </text>
        <text x="600" y="68" textAnchor="middle" className="detail" fontSize="13">
          Image-digest pinning: unchanged digests = container stays running. Changed digests = container recreates.
        </text>

        {/* Step 1 — Download (only Scenario 2 + 3) */}
        <rect x="60" y="100" width="240" height="180" rx="12" className="cust-step" />
        <text x="80" y="130" className="cust-step-num">1</text>
        <text x="180" y="155" textAnchor="middle" className="cicd-card-title" style={{fontSize: 15}}>Download (S2/S3 only)</text>
        <text x="180" y="180" textAnchor="middle" className="cust-outcome">From the GitHub release page:</text>
        <rect x="80" y="195" width="200" height="20" className="cust-cmd" />
        <text x="180" y="209" textAnchor="middle" className="cust-cmd-text">guardian-installer</text>
        <text x="180" y="234" textAnchor="middle" className="muted" fontSize="11">+ release-manifest-vX.Y.Z.env</text>
        <text x="180" y="250" textAnchor="middle" className="muted" fontSize="11">+ install.tar.gz + sha256</text>
        <text x="180" y="270" textAnchor="middle" className="state-success-fill" fontSize="11">Scenario 1: skip — reuse existing</text>

        {/* Step 2 — Run installer */}
        <rect x="340" y="100" width="280" height="180" rx="12" className="cust-step" />
        <text x="360" y="130" className="cust-step-num">2</text>
        <text x="480" y="155" textAnchor="middle" className="cicd-card-title" style={{fontSize: 15}}>Run installer</text>
        <rect x="360" y="170" width="240" height="20" className="cust-cmd" />
        <text x="480" y="184" textAnchor="middle" className="cust-cmd-text">sudo ./guardian-installer</text>
        <text x="480" y="210" textAnchor="middle" className="cust-outcome">Extract payload to /opt/guardian</text>
        <text x="480" y="226" textAnchor="middle" className="cust-outcome">+ overwrite /opt/guardian/.env</text>
        <text x="480" y="242" textAnchor="middle" className="cust-outcome">with manifest digest pins</text>
        <rect x="360" y="252" width="240" height="20" className="cust-cmd" />
        <text x="480" y="266" textAnchor="middle" className="cust-cmd-text">WIPE_VOLUMES=true # S3 only</text>

        {/* Step 3 — docker compose pull */}
        <rect x="660" y="100" width="240" height="180" rx="12" className="cust-step" />
        <text x="680" y="130" className="cust-step-num">3</text>
        <text x="780" y="155" textAnchor="middle" className="cicd-card-title" style={{fontSize: 15}}>docker compose pull</text>
        <rect x="680" y="170" width="200" height="20" className="cust-cmd" />
        <text x="780" y="184" textAnchor="middle" className="cust-cmd-text">cd /opt/guardian</text>
        <rect x="680" y="195" width="200" height="20" className="cust-cmd" />
        <text x="780" y="209" textAnchor="middle" className="cust-cmd-text">docker compose pull</text>
        <text x="780" y="234" textAnchor="middle" className="cust-outcome">Only images whose digest</text>
        <text x="780" y="250" textAnchor="middle" className="cust-outcome">changed since last install</text>
        <text x="780" y="266" textAnchor="middle" className="cust-outcome">actually pull bytes</text>

        {/* Step 4 — docker compose up */}
        <rect x="940" y="100" width="220" height="180" rx="12" className="cust-step" />
        <text x="960" y="130" className="cust-step-num">4</text>
        <text x="1050" y="155" textAnchor="middle" className="cicd-card-title" style={{fontSize: 15}}>docker compose up -d</text>
        <rect x="960" y="170" width="180" height="20" className="cust-cmd" />
        <text x="1050" y="184" textAnchor="middle" className="cust-cmd-text">--remove-orphans</text>
        <text x="1050" y="212" textAnchor="middle" className="cust-outcome">For each service:</text>
        <text x="1050" y="228" textAnchor="middle" className="cust-outcome">same digest? → keep running</text>
        <text x="1050" y="244" textAnchor="middle" className="cust-outcome">new digest? → recreate</text>
        <text x="1050" y="266" textAnchor="middle" className="state-success-fill" fontSize="11">in-memory state preserved</text>

        {/* Arrows between steps */}
        <path className="edge operator" d="M 300 190 L 340 190" />
        <path className="edge operator" d="M 620 190 L 660 190" />
        <path className="edge operator" d="M 900 190 L 940 190" />

        {/* Lower section — outcomes per scenario */}
        <text x="600" y="335" textAnchor="middle" className="cicd-track-label">VOLUME + CONTAINER OUTCOMES (PER SCENARIO)</text>

        {/* Scenario 1 outcome */}
        <rect x="60" y="360" width="360" height="220" rx="12" className="cust-step" stroke="var(--dgm-state-success)" strokeWidth="2.2" />
        <text x="80" y="388" className="cicd-card-title" style={{fontSize: 15}}>SCENARIO 1 — code-only</text>
        <text x="80" y="412" className="cust-outcome">Re-run existing installer → same compose template applies.</text>
        <text x="80" y="430" className="cust-outcome">Updated agent image digest = guardian-agent recreates.</text>
        <text x="80" y="448" className="cust-outcome">Unchanged browser/connector digests = those containers</text>
        <text x="80" y="466" className="cust-outcome">keep running (in-memory state preserved).</text>
        <rect x="80" y="482" width="320" height="20" className="cust-cmd" />
        <text x="240" y="496" textAnchor="middle" className="cust-cmd-text">DIGEST_GUARDIAN_BROWSER identical → no recreate</text>
        <text x="80" y="528" className="state-success-fill" fontSize="12" fontWeight="700">Result:</text>
        <text x="140" y="528" className="cust-outcome" fontSize="12">all named volumes preserved.</text>
        <text x="80" y="548" className="state-success-fill" fontSize="12" fontWeight="700">Customer downtime:</text>
        <text x="220" y="548" className="cust-outcome" fontSize="12">single agent container restart (~30s).</text>
        <text x="80" y="568" className="state-success-fill" fontSize="12" fontWeight="700">Re-onboard required:</text>
        <text x="230" y="568" className="cust-outcome" fontSize="12">no.</text>

        {/* Scenario 2 outcome */}
        <rect x="440" y="360" width="360" height="220" rx="12" className="cust-step" stroke="var(--dgm-state-info)" strokeWidth="2.2" />
        <text x="460" y="388" className="cicd-card-title" style={{fontSize: 15}}>SCENARIO 2 — code + installer change</text>
        <text x="460" y="412" className="cust-outcome">Download new installer; default flag preserves volumes.</text>
        <text x="460" y="430" className="cust-outcome">New compose template applies (may add/rename env vars).</text>
        <text x="460" y="448" className="cust-outcome">All named volumes round-trip; data survives.</text>
        <rect x="460" y="464" width="320" height="20" className="cust-cmd" />
        <text x="620" y="478" textAnchor="middle" className="cust-cmd-text">WIPE_VOLUMES=false (default)</text>
        <text x="460" y="510" className="state-info-fill" fontSize="12" fontWeight="700">Result:</text>
        <text x="520" y="510" className="cust-outcome" fontSize="12">volumes preserved via installer flag.</text>
        <text x="460" y="530" className="state-info-fill" fontSize="12" fontWeight="700">Customer downtime:</text>
        <text x="600" y="530" className="cust-outcome" fontSize="12">full stack restart (~2 min).</text>
        <text x="460" y="550" className="state-info-fill" fontSize="12" fontWeight="700">Re-onboard required:</text>
        <text x="612" y="550" className="cust-outcome" fontSize="12">no.</text>

        {/* Scenario 3 outcome */}
        <rect x="820" y="360" width="340" height="220" rx="12" className="cust-step" stroke="var(--dgm-state-error)" strokeWidth="2.2" />
        <text x="840" y="388" className="cicd-card-title" style={{fontSize: 15}}>SCENARIO 3 — BC-incompatible</text>
        <text x="840" y="412" className="cust-outcome">Operator MUST back up before running.</text>
        <text x="840" y="430" className="cust-outcome">No automatic backup is performed.</text>
        <rect x="840" y="446" width="300" height="20" className="cust-cmd" />
        <text x="990" y="460" textAnchor="middle" className="cust-cmd-text">docker run --rm -v ... busybox tar ...</text>
        <text x="840" y="488" className="cust-outcome">Then run with WIPE_VOLUMES=true.</text>
        <text x="840" y="516" className="state-error-fill" fontSize="12" fontWeight="700">Result:</text>
        <text x="900" y="516" className="cust-outcome" fontSize="12">named volumes destroyed; defaults re-seed.</text>
        <text x="840" y="536" className="state-error-fill" fontSize="12" fontWeight="700">Customer downtime:</text>
        <text x="980" y="536" className="cust-outcome" fontSize="12">stack restart + re-setup (~10 min).</text>
        <text x="840" y="556" className="state-error-fill" fontSize="12" fontWeight="700">Re-onboard required:</text>
        <text x="992" y="556" className="cust-outcome" fontSize="12">yes (admin password, providers).</text>

        {/* Bottom invariant */}
        <rect x="60" y="610" width="1080" height="110" rx="12" className="rel-phase-hero" stroke="var(--dgm-edge-shared)" strokeWidth="2" fill="var(--dgm-node-fill-strong)" />
        <text x="600" y="640" textAnchor="middle" className="cicd-card-title" style={{fontSize: 15, fill: "var(--dgm-edge-shared)"}}>
          The load-bearing invariant
        </text>
        <text x="600" y="662" textAnchor="middle" className="detail" fontSize="13">
          docker compose treats &quot;same image digest&quot; as &quot;no change&quot; — the container keeps running across the upgrade.
        </text>
        <text x="600" y="682" textAnchor="middle" className="muted" fontSize="11">
          For unchanged services, release.yml&apos;s retag-from-prev path produces a BIT-IDENTICAL image. compose recognizes the
        </text>
        <text x="600" y="698" textAnchor="middle" className="muted" fontSize="11">
          same digest + leaves the container alone. guardian-browser + connector containers preserve in-memory state across releases that don&apos;t touch their code.
        </text>
      </svg>
    </div>
  );
}
