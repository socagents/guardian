/**
 * Release-notes history — bundled with the UI image so the About
 * modal works offline (customer environments may be air-gapped from
 * GitHub).
 *
 * Authoring contract:
 *   * Newest entry first. The modal renders in array order.
 *   * `version` is bare semver (no "v" prefix) so it compares
 *     directly with /api/agent/version.
 *   * `date` is ISO yyyy-mm-dd of the GHCR publish.
 *   * `highlights` are 3-7 bullets, operator-facing language. No
 *     internal commit shorthand. Aim for ~10-15 words each.
 *   * `categories` is optional structure for security-heavy releases
 *     where bullets-only flattens too much detail.
 *   * `headline` flags become visual badges in the modal — use
 *     sparingly. `security: true` adds a red shield. `breaking: true`
 *     adds a yellow warning.
 *
 * When you cut a release: prepend a new entry here in the same PR
 * that creates the tag. The image rebuilt for that tag will then
 * carry its own notes — no fetch from GitHub required.
 */

export interface ReleaseNote {
  version: string;
  date: string;
  title: string;
  highlights: string[];
  categories?: { name: string; items: string[] }[];
  security?: boolean;
  breaking?: boolean;
}

export const RELEASE_NOTES: ReleaseNote[] = [
  {
    version: "0.17.146",
    date: "2026-06-08",
    title: "Data sources: two-tier validation label — Mapping Validated and Raw Validated.",
    highlights: [
      "The green Mapping Validated pill means we confirmed the vendor's rule populates xdm.* live on a Cortex XSIAM tenant.",
      "New amber Raw Validated pill means the pack isn't installed, but a raw query confirmed our data lands the exact field names the rule reads.",
      "Microsoft Defender for Cloud, Proofpoint CASB, and Azure App Service earn the first Raw Validated pills — proven shape, ready-to-map on install.",
      "Lets us prove content correctness independent of what's installed; a build check forbids a source claiming both tiers.",
    ],
  },
  {
    version: "0.17.145",
    date: "2026-06-08",
    title: "3 newly validated data sources: Cisco ASA, Microsoft Entra ID, Zscaler NSS Weblog.",
    highlights: [
      "Cisco ASA, Microsoft Entra ID, and Zscaler NSS Weblog now carry the green Validated pill — confirmed mapping 42–65 xdm fields on a live XSIAM tenant.",
      "Validated set grows from 37 to 40, each proven end-to-end through the simulate → broker → XQL loop.",
    ],
  },
  {
    version: "0.17.144",
    date: "2026-06-08",
    title: "Data sources: removed 12 action-integration vendors that aren't real data sources.",
    highlights: [
      "A data source must be a real Cortex XSIAM ingest + parse path (a parsing/modeling rule) — not an XSOAR action integration.",
      "Removed CrowdStrike, Sophos ×2, PingOne, Wiz, Rapid7 ×2, SAP, ESET, Snowflake, Veeam, QRadar — they land raw but have no rule to structure them (xdm=0 on the live tenant).",
      "Kept Ping Identity PingFederate — the one with a native Cortex parser + matching dataset.",
    ],
  },
  {
    version: "0.17.143",
    date: "2026-06-07",
    title: "Brand logos for the 13 new vendor data sources.",
    highlights: [
      "CrowdStrike, Sophos, Ping Identity, Wiz, Rapid7, SAP, Snowflake, Veeam, and ESET now show their brand marks in the catalog.",
      "Each logo is the official mark from a license-clean source, embedded inline so the catalog renders offline.",
    ],
  },
  {
    version: "0.17.142",
    date: "2026-06-07",
    title: "13 new high-value vendor data sources (CrowdStrike, Sophos, Wiz, Rapid7, SAP…).",
    highlights: [
      "Added CrowdStrike Falcon, Sophos Central + Firewall, ESET PROTECT, and Ping Identity (PingFederate + PingOne).",
      "Added Wiz (CNAPP), Snowflake, Rapid7 InsightVM + InsightIDR, IBM QRadar, SAP Security Audit Log, and Veeam.",
      "Each field set is derived from the vendor's real Cortex modeling rule and adversarially reviewed for accuracy.",
      "New sources are marked not-yet-validated; each how_to_use names the XSIAM content pack to install.",
    ],
  },
  {
    version: "0.17.141",
    date: "2026-06-07",
    title: "Data-source audit cleanup: vendor casing, Salesforce descriptions, MacOS flag.",
    highlights: [
      "Normalized 3 lowercase vendor strings (microsoft/salesforce/zscaler) so each groups as one tile in Browse Data Sources.",
      "Gave 5 Salesforce sources real descriptions instead of the generic 'CRM Services' category label.",
      "Fixed the macOS source's raw-log-only flag to match its single _raw_log field.",
    ],
  },
  {
    version: "0.17.140",
    date: "2026-06-07",
    title: "Live Telemetry badges turn-cached tool calls.",
    highlights: [
      "A tool call served from the turn-cache (no MCP round-trip) now shows a 'cached' chip in the Live Telemetry timeline.",
      "Makes the v0.17.130/131 dedup visible — you can tell a cache hit from a real dispatch at a glance.",
    ],
  },
  {
    version: "0.17.139",
    date: "2026-06-07",
    title: "Cleanup: Cortex XDR empty-args crash + stale prompt approval line.",
    highlights: [
      "xdr_incidents_list no longer throws on an empty/missing limit — the connector's clamp sites degrade to the default instead of int(None).",
      "Removed a stale 'require approval for Caldera/XSIAM' line from the bundled prompt (gating has been agent-self-modification-only since v0.1.22).",
    ],
  },
  {
    version: "0.17.138",
    date: "2026-06-07",
    title: "Fixed the PAN-OS packs' origin value so the bundle validator is fully green.",
    highlights: [
      "The 6 PAN-OS NGFW packs used an out-of-schema origin: manual; set to origin: bundle.",
      "With v0.17.137, all 294 bundled data sources now pass schema validation on main.",
    ],
  },
  {
    version: "0.17.137",
    date: "2026-06-07",
    title: "Cleaned 4 bundled data sources that failed schema validation.",
    highlights: [
      "Microsoft Defender for Cloud + 2 Tanium sources listed each field 2–3× (a generation artifact) and used an invalid 'number' type; both fixed.",
      "Duplicate fields collapse to one (keeping the most-informative copy); the bundle validator is green on main again.",
    ],
  },
  {
    version: "0.17.136",
    date: "2026-06-07",
    title: "New data sources: Palo Alto Networks NGFW (PAN-OS) firewall — 6 datasets.",
    highlights: [
      "Adds PAN-OS NGFW Traffic, Threat, URL, File Data, GlobalProtect, and HIP Match sources with their real Cortex dataset names and full CEF-key schemas.",
      "Fixes the gap that made the agent invent a non-existent palo_alto_networks_pan_os_raw dataset — it now cites a real PAN-OS source.",
      "Simulate as CEF to the XSIAM Broker (vendor=panw, product=ngfw_cef); the log_type extension splits into the per-type dataset.",
      "Ships not-yet-validated (validated: false) — XDM promotion needs a live-tenant saturation run on the tenant's PAN-OS pack.",
    ],
  },
  {
    version: "0.17.135",
    date: "2026-06-07",
    title: "Chat agent never renders a blank assistant turn after a tool ran.",
    highlights: [
      "A turn that ran tools but came back empty (or whitespace-only) now falls through to a recap of what ran, instead of a silent blank message.",
      "Caught by an export-data-source-as-YAML probe that fetched the schema then returned nothing.",
    ],
  },
  {
    version: "0.17.134",
    date: "2026-06-07",
    title: "Chat agent answers routing questions from installed sources, not native-support knowledge.",
    highlights: [
      "Asked where a vendor's logs land, the agent now answers from the installed data sources only — not from general Cortex knowledge.",
      "If the vendor isn't installed here, it says so plainly instead of citing a plausible-but-wrong dataset name (caught with Palo Alto PAN-OS).",
      "Closes a residual fabrication that survived v0.17.133's deploy verification.",
    ],
  },
  {
    version: "0.17.133",
    date: "2026-06-07",
    title: "Chat agent cites real identifiers from tool results instead of inventing them.",
    highlights: [
      "Field names, dataset names, adversary/scenario names, worker ids, and counts must now come verbatim from an actual tool result — no plausible-looking guesses.",
      "Caught the agent inventing FortiGate fields (FTNTFGTsrcip), a non-existent palo_alto_networks_pan_os_raw dataset, and Caldera APT profiles it never queried.",
      "If a named thing isn't in any tool result, the agent now says it isn't available rather than fabricating a name.",
    ],
  },
  {
    version: "0.17.132",
    date: "2026-06-07",
    title: "Chat agent tool-use discipline: no retry loops, no fabricated results, honest narration.",
    highlights: [
      "The agent no longer re-fires a tool call that already failed the same way — it switches tactics or reports the blocker.",
      "Cortex/XQL queries are composed once via the build_xql_query skill instead of a dozen trial-and-error variants.",
      "If a verification query fails (e.g. quota exceeded), the agent says so instead of inferring an answer from its own inputs.",
      "It no longer narrates 'I am about to call X' for a call it doesn't make, and confirms the id/schedule of jobs and workers it creates.",
    ],
  },
  {
    version: "0.17.131",
    date: "2026-06-07",
    title: "Chat agent stops re-trying a tool call that already failed the same way this turn.",
    highlights: [
      "Once the same tool with the same arguments has failed twice in a turn, further identical calls are short-circuited with a 'don't retry — change approach' answer instead of hitting the backend again.",
      "Catches the soft {ok:false} failures the success-cache couldn't — e.g. an agent that re-ran data_sources_install seven times on a not-found pack.",
      "Stays precise: poll/wait tools are exempt, a retry with different arguments still runs, and a soft-failed read is no longer cached as a success.",
      "Also cleared an internal hygiene issue: the prior cache key's stray NUL-byte separator (harmless at runtime) was replaced with a space.",
    ],
  },
  {
    version: "0.17.130",
    date: "2026-06-07",
    title: "Redundant catalog/knowledge reads in one chat turn no longer cost an MCP round-trip.",
    highlights: [
      "Within one chat turn, an identical read-only call (same tool + args) for static platform metadata is now served from a per-turn cache instead of re-dispatching to the MCP.",
      "Covers the data-source catalog, source schemas, installed vendors, marketplace list, log destinations, settings, skills, knowledge search, field info, and tech stack.",
      "Stays correct: a same-turn catalog or config change clears the snapshot, and two different lookups both run — only verbatim repeats are collapsed.",
      "The cache lives for exactly one message and never crosses turns or operators; the soft v0.17.129 nudge remains as defense in depth.",
    ],
  },
  {
    version: "0.17.129",
    date: "2026-06-07",
    title: "Chat agent auto-retries an empty model turn; stops re-listing the data-source catalog per vendor.",
    highlights: [
      "The agent no longer silently returns 'I didn't generate a response this turn' on an intermittent empty model turn — it auto-retries once before falling back, recovering transparently.",
      "Multi-vendor requests no longer call data_sources_list (the full catalog) once per vendor — seven times in one observed turn — the agent now lists once and reuses, cutting latency.",
    ],
  },
  {
    version: "0.17.128",
    date: "2026-06-07",
    title: "phantom-updater reconciles connector containers to their pins on a timer, not just at startup.",
    highlights: [
      "Per-instance connector containers now track their pinned image digest on a periodic loop (default 5 min; PHANTOM_UPDATER_RECONCILE_INTERVAL_S), not only at updater startup.",
      "Fixes connector containers going stale between updater restarts: a connector pinned to a newer image could keep running an older one — with its newer tools unreachable from chat — until someone manually recreated it.",
      "Same reconcile path the startup + manual endpoints use — compares each phantom-connector-* container's digest to its pin and recreates only the divergent ones, sequentially.",
    ],
  },
  {
    version: "0.17.127",
    date: "2026-06-06",
    title: "Chat agent: routing answers consult how_to_use; simulation confirmations name the worker.",
    highlights: [
      "Data-source routing questions (where does X land, how do I onboard it, will it reach dataset Y) now read the source's how_to_use via data_sources_get_schema before answering — no more guessing the dataset from the vendor/product name, which misleads for renamed vendors and channel-split Windows/Azure sources.",
      "Simulation confirmations now name the worker they started: the no-text fallback recap previously omitted phantom_create_data_worker (a 'simulate Okta to XSIAM' turn recapped only an incidental memory_store). It now counts simulation + catalog/data-source mutations.",
    ],
  },
  {
    version: "0.17.126",
    date: "2026-06-06",
    title: "Scheduled prompt jobs run again; failing jobs back off instead of flooding.",
    highlights: [
      "Scheduled prompt jobs work again: since v0.9.1 the scheduler's loopback call to /api/chat carried no auth and 401'd every time. It now authenticates with the container MCP_TOKEN — the same internal loopback trust the agent's hook-dispatch endpoint uses.",
      "A job that fails persistently (a 401, a provider error) now auto-disables after 10 consecutive failures instead of re-firing every cron tick forever — one leftover test job had logged ~24,000 failed runs. Re-enable it from the job's page once fixed.",
      "Credential-management routes stay blocked even for the internal token — the security invariant is unchanged.",
    ],
  },
  {
    version: "0.17.125",
    date: "2026-06-06",
    title: "XSIAM + Cortex XDR incident / alert / endpoint tools reachable from chat again.",
    highlights: [
      "The agent can now call all 45 XSIAM v0.15.x tools (incidents, alerts, IoCs, endpoints, response, scripts, audit, parsers, datamodel, broker) plus the Cortex XDR tools from chat — they previously returned 'Unknown tool'.",
      "Root cause: those tools' connector.yaml names carried the connector prefix, producing a doubled alias (xsiam_xsiam_incidents_list) so the natural name was never advertised.",
      "The fix de-doubles the legacy alias for every connector and aligns the XSIAM wire names; the 14 long-standing XSIAM XQL/case/dataset tools were unaffected.",
    ],
  },
  {
    version: "0.17.124",
    date: "2026-06-06",
    title: "Every bundled data source now documented; realistic synthetic values; routing validated end-to-end.",
    highlights: [
      "All 288 bundled data sources now carry a how_to_use guide + reverse-engineered field inventory in the drawer — the 251 non-validated sources were reverse-engineered from their vendor parsing/modeling rules (routing literal, gate, XDM inventory, verify query).",
      "Synthetic simulation generates realistic typed values — real IPs, country codes, HTTP methods, ports, hashes per field type — so value-dependent modeling-rule reads fire and far more xdm.* fields populate (O365 general 53→65, SharePoint 38→50).",
      "Routing validated live across all 288 sources: every asserted CEF literal lands in its correct dataset, zero wrong literals. The sweep fixed 6 false routing claims on Windows/Azure channel-split sources.",
      "Prisma Cloud Compute validated end-to-end (29 xdm fields); Imperva WAF schema corrected to use CEF wire keys. Validated set grows 36 → 37.",
      "All 22 previously-validated sources leveled up to a rich vendor-specific how_to_use lead — the 12 thin/empty ones now match the Okta/Alibaba standard.",
    ],
  },
  {
    version: "0.17.123",
    date: "2026-06-04",
    title: "Six cloud-provider data sources validated for XDM: Google Cloud + Microsoft Azure.",
    highlights: [
      "GCP Cloud Logging (52 xdm fields), Cloud DNS (30), Workspace Drive (22), Security Command Center (21), Apigee (10), and Azure Firewall (20) now map XDM live on the tenant. The validated set grows from 30 to 36, each with the green Validated pill.",
      "Cloud Logging maps 52 fields out of deeply-nested protoPayload JSON — proving CEF-over-syslog carries the nested JSON these rules parse, with no HTTP collector needed.",
      "Cloud-provider sources are JSON-native: they map only once the matching content pack is installed in XSIAM, which binds the modeling + parsing rules to the dataset. Each how_to_use makes that prerequisite explicit.",
      "Each validated source ships a how_to_use with the exact CEF header, the modeling-rule gate, the JSON-composite note, and a verify query.",
    ],
  },
  {
    version: "0.17.122",
    date: "2026-06-03",
    title: "Three more marquee data sources validated for XDM: Cisco Firepower, Cisco Duo, Microsoft 365 Defender.",
    highlights: [
      "Cisco Firepower (39 xdm fields), Cisco Duo (54), and Microsoft 365 Defender (40) now route, clear the modeling-rule gate, and map rich XDM — verified live on the tenant. The validated set grows from 27 to 30, each with the green Validated pill.",
      "Every validated source ships a gate-aware how_to_use: the exact CEF header (vendor/product), the modeling-rule gate, and a verify query.",
      "Netskope + GitHub were tested but do NOT map on a stock tenant — their how_to_use records the precise reason and the onboarding each needs (Netskope content pack; GitHub JSON/HTTP-collector path).",
      "Verify XDM over a wide ≥7-day window: synthetic events can carry a timestamp days in the past, so a 24h window can read zero rows even on a clean mapping.",
    ],
  },
  {
    version: "0.17.121",
    date: "2026-06-02",
    title: "Hardening from the v0.17.120 validation retro: tighter schema compaction + verify guidance.",
    highlights: [
      "data_sources_get_schema(compact=true) now also omits false is_array/is_meta — so even a 222-field vendor (FortiGate) sends its full schema to the simulator without truncating.",
      "The stream-to-XSIAM skill gained lesson L24: verify fresh XDM with sort-desc-time, and don't filter on xdm.event.type (firewall/endpoint rules don't set it — they map xdm.event.outcome/event.id).",
      "Confirms the v0.17.120 five map fresh events end-to-end: FortiGate 76, Salesforce 43, SentinelOne 34, Windows 29, Zscaler 17 xdm fields.",
    ],
  },
  {
    version: "0.17.120",
    date: "2026-06-02",
    title: "Five new data sources validated end-to-end for XDM mapping.",
    highlights: [
      "FortiGate, SentinelOne, Microsoft Windows, Zscaler, and Salesforce now map rich xdm.* fields — validated live on your tenant.",
      "Measured coverage: FortiGate 67, Salesforce 32, Windows 27, SentinelOne 25+, Zscaler 17 xdm fields. Green Validated pill on each.",
      "Corrected CEF routing, modeling-rule gate seeds, and how_to_use guidance for all five so the agent simulates them correctly.",
      "data_sources_get_schema gained a compact mode so 100+-field vendors no longer truncate — the fix that unblocked SentinelOne's XDM.",
      "SentinelOne's how_to_use documents the two-event split needed for full XDM (its schema exceeds the UDP MTU).",
    ],
  },
  {
    version: "0.17.119",
    date: "2026-06-01",
    title: "The validated sources' XDM gates are now correct and CI-enforced against the live modeling rules.",
    highlights: [
      "Fixed two validated sources (Alibaba ActionTrail, Azure Kubernetes) whose gate example matched no branch of their modeling rule — so even a correctly-seeded simulation produced 0 XDM.",
      "Each fix flags the gate field and adds a 'Make it map to XDM' section to the source's how_to_use (shown in the data-source drawer) naming the exact gate values.",
      "New CI guard re-derives each gate from the live .xif modeling rule and fails the build if a bundled example no longer clears it — no static vendor→value table to drift.",
      "Across the 22 validated sources: 7 gated (now correct), 1 META (CloudTrail onboarding), 1 computed, 13 map unconditionally.",
      "Completes the XDM-gate arc. Code + content + CI change — re-run your existing installer (Scenario 1).",
    ],
  },
  {
    version: "0.17.118",
    date: "2026-06-01",
    title: "Simulated logs now reliably populate the XDM data model, not just the raw dataset.",
    highlights: [
      "Fixed simulated events landing raw but showing 0 XDM fields — every XSIAM modeling rule gates on a specific field=value, and the agent wasn't always seeding it.",
      "The stream-to-XSIAM skill now MANDATORY-seeds the modeling-rule gate field via observables_dict before firing — proven to take Azure FlowLogs from 0 → 25+ XDM fields over the same CEF path.",
      "It was never a CEF-vs-JSON transport problem — it's the gate field; sources whose gate is a broker-assigned _log_type are documented as needing source onboarding.",
      "Agent-baked skill change — re-run your existing installer (Scenario 1).",
    ],
  },
  {
    version: "0.17.117",
    date: "2026-06-01",
    title: "The agent reliably creates data workers even with large field schemas.",
    highlights: [
      "Fixed a silent stall: 'simulate ServiceNow into XSIAM, verify the fields, then stop the worker' would plan the run, then drop the create-worker call and end the turn with nothing created.",
      "Root cause was a Gemini thinking-model quirk — a tool call with a very large argument (the full ~70-field schema) got serialized as reasoning text instead of a real function call, so the chat loop never dispatched it.",
      "The chat now auto-recovers: when a turn leaks a tool call into its thinking, it retries once with forced function-calling so the call actually runs. Normal turns are untouched.",
      "Code-only change (agent) — re-run your existing installer (Scenario 1).",
    ],
  },
  {
    version: "0.17.116",
    date: "2026-06-01",
    title: "Ask the agent to send logs to XSIAM — it routes to the right dataset, first try, no re-asking.",
    highlights: [
      "Fixed the agent inventing prettified CEF product names (e.g. 'Okta SSO' instead of the literal 'Okta') — which routed events to a dataset nothing parses; it now passes the exact vendor/product from data_sources_get_schema.",
      "phantom_create_data_worker's vendor/product arg docs now spell out the literal-not-display rule + the Okta trap, so the agent gets routing right at the call site.",
      "The agent no longer pauses with 'fire it?' when you already said send/stream/fire — it simulates immediately (the stream-to-XSIAM skill now treats your request as the go-ahead).",
      "Connector + skill change — re-run your existing installer (Scenario 1).",
    ],
  },
  {
    version: "0.17.115",
    date: "2026-06-01",
    title: "Hot-fix: stopping a simulation worker no longer reports a spurious error.",
    highlights: [
      "Fixed phantom_kill_worker, which returned a 'request is not defined' error on every call (a v0.17.114 flatten regression) — the worker did stop, but agent-driven cleanup saw a failure and could leave workers emitting.",
      "Hardened the connector flat-args CI guard to also scan tool bodies for a dropped 'request' reference, so this incomplete-flatten class can't ship again.",
      "Connector-only change — re-run your existing installer (Scenario 1).",
    ],
  },
  {
    version: "0.17.114",
    date: "2026-05-31",
    title: "The agent now reliably calls every connector tool — one flat argument convention.",
    highlights: [
      "Fixed connector tools the agent couldn't call (XQL, field-info, observables, scenarios, lookups): all now take flat args matching connector.yaml, like create_data_worker already did.",
      "26 tools across xsiam / xlog / caldera / cortex-docs reconciled — connector.yaml ⟺ signature ⟺ model identical; each tool's behavior unchanged.",
      "Eliminated the 'proxy expects query, connector expects a request object' validation loop that broke XQL verification.",
      "New CI guard fails the build if any connector tool drifts back to the nested-request shape — consistency stays enforced.",
      "Factory-default contract is CI-enforced: exactly the 22 tested data sources are marked Validated, and a customer install is a clean slate (catalog + connectors + skills + KB as content, nothing installed).",
      "Marketplace vendor logos restored — all 259 catalog packs map to 136 vendors with light+dark logos (the v0.17.25 refresh had deleted the logo set).",
    ],
  },
  {
    version: "0.17.113",
    date: "2026-05-31",
    title: "The agent picks your log destination from the ones you configured — no hardcoded targets.",
    highlights: [
      "Ask to generate logs and the agent resolves WHERE they go from your configured Log Destinations — one match is used automatically, two trigger a question, none offers to create one.",
      "New: the agent can create secretless syslog destinations for you; credentialed ones stay operator-only (REST + UI).",
      "XSIAM webhook credentials are injected server-side — the auth key never passes through the chat.",
      "Works for vendor-faithful simulation over syslog or XSIAM HTTP; no destination address is ever hardcoded.",
      "Docs: /help/user#log-destinations-ux + /help/architecture#log-destinations + a new simulate-to-log-destination journey.",
    ],
  },
  {
    version: "0.17.112",
    date: "2026-05-30",
    title: "Read-tool narration is now reliably gone from the chat.",
    highlights: [
      "Deterministic filter drops 'I'll call X' narration for read-only tool calls — no longer relies on the model obeying a prompt rule (which it ignored in v0.17.111).",
      "Approval-gated actions still show their plain-language heads-up; the live telemetry still shows every call + result.",
    ],
  },
  {
    version: "0.17.111",
    date: "2026-05-30",
    title: "Cleaner chat — the agent stops narrating read-only tool calls.",
    highlights: [
      "Read-only tool calls (lists, lookups, queries) no longer print 'I'll call X' in the chat — they're already shown in the live telemetry.",
      "Approval-gated actions still get a short plain-language heads-up before their approval card.",
    ],
  },
  {
    version: "0.17.110",
    date: "2026-05-30",
    title: "Azure WAF data source passes schema validation.",
    highlights: [
      "Azure WAF's Category classifier field now declares its valid enum values, so all bundled data sources pass schema validation again.",
    ],
  },
  {
    version: "0.17.109",
    date: "2026-05-30",
    title: "API-key Create panel is theme-aware and roomier.",
    highlights: [
      "The Create-Key panel follows the light theme — background and text flip with the theme toggle (was always dark).",
      "Create panel widened to about half the page so the form has room to breathe.",
      "Scopes now render in two columns — pick one without scrolling.",
    ],
  },
  {
    version: "0.17.108",
    date: "2026-05-30",
    title: "Authenticate to the agent API with an API key.",
    highlights: [
      "Mint a scoped, revocable API key in /api-keys and send Authorization: Bearer phantom_ak_… to /api/chat + /api/agent/*.",
      "Coarse scopes: agent:read, agent:write, agent:* — chosen per key at mint time.",
      "Credential routes (providers/instances/api-keys) stay session-only even with agent:* — a leaked key can't mint more keys.",
      "Useful for scripts, schedulers, CI, and programmatic integrations.",
    ],
  },
  {
    version: "0.17.107",
    date: "2026-05-29",
    title: "Data sources: XDM-classifier seeding guidance for chat-driven simulation.",
    highlights: [
      "Validated sources now document the classifier value their modeling rule needs to populate XDM.",
      "Azure WAF gains its Category field; Azure AKS guidance corrected (kube-apiserver, not kube-audit).",
      "stream_simulate_to_xsiam skill: seed-the-classifier + pass-all-fields lessons; stale ~10-cap lesson corrected.",
      "Measured lift: Okta 0→46, Azure Flow Logs 0→48, CyberArk 0→40 XDM.",
    ],
  },
  {
    version: "0.17.106",
    date: "2026-05-29",
    title: "Simulation: the log-generation connector forwards field overrides on the vendor-faithful path.",
    highlights: [
      "The xlog connector now sends observables_dict in the schema_override mutation (it was dropped before).",
      "Completes the v0.17.105 wiring end-to-end: seeded classifier values now reach the synthesized event.",
      "Modeling rules that gate XDM on a classifier field now populate; Okta SSO routes to its own dataset.",
    ],
  },
  {
    version: "0.17.105",
    date: "2026-05-29",
    title: "Simulation: streaming workers honor forced-field overrides (observables_dict).",
    highlights: [
      "Streaming workers now apply observables_dict (the inline generator already did; the worker path dropped it).",
      "Okta SSO now lands: its shared Okta CEF header is split by eventType, which the override now supplies.",
      "Modeling rules that gate XDM on a classifier value now fire when a valid value is seeded.",
      "List-valued field overrides unwrap to the scalar the rule's filter expects.",
    ],
  },
  {
    version: "0.17.104",
    date: "2026-05-29",
    title: "Simulation: nested-JSON fields now generate real objects, not random strings.",
    highlights: [
      "Composite (type:json) fields like Okta actor or AWS WAF httpRequest now simulate as real nested objects.",
      "Dotted-leaf children fold into their parent object, each leaf typed and value-generated.",
      "Composites serialize as compact JSON on the CEF wire so the modeling rule's json_extract_scalar resolves.",
      "Unblocks XDM mapping for every nested-JSON vendor in the validated data-source set.",
    ],
  },
  {
    version: "0.17.103",
    date: "2026-05-29",
    title: "Data sources: consistent simulation guidance across validated sources.",
    highlights: [
      "Every validated data source now opens with a vendor-specific 'how to simulate this' lead.",
      "Jira, ServiceNow, Qualys, and Proofpoint TAP gained the narrative lead the others already had (the discriminator / timestamp gotcha / dominant event shape).",
      "Pure content — no validated technical specific (CEF header, discriminators, formats, ceilings) changed.",
    ],
  },
  {
    version: "0.17.102",
    date: "2026-05-29",
    title: "Fix: data source drawer opens for every catalog dataset.",
    highlights: [
      "Clicking a bundled dataset that cortex-content doesn't enumerate (e.g. Okta's SSO stream) no longer errors — the drawer now reads the bundled YAML.",
      "The schema surfaces (drawer + the agent's data_sources_get_schema tool) resolve any catalog source, not just installed ones.",
      "Both Okta streams (okta_okta_raw 59 fields, okta_sso_raw 52 fields) open with their full schema.",
    ],
  },
  {
    version: "0.17.101",
    date: "2026-05-29",
    title: "Data sources: export any version (versioning arc complete).",
    highlights: [
      "Export any version of a data source's YAML from the History panel — each row has an Export button (downloads <dataset>.v<n>.yaml).",
      "The card's main Export now downloads the current version — after an edit that's the edited content, not the original file (fixes a quiet inconsistency).",
      "Completes the data-source versioning arc: edit (v0.17.99) → history + rollback (v0.17.100) → export-by-version (v0.17.101).",
    ],
  },
  {
    version: "0.17.100",
    date: "2026-05-29",
    title: "Data sources: version history + rollback.",
    highlights: [
      "Every data source now has a History panel — see each version's author, change note, and timestamp, and view any version's full snapshot.",
      "Roll back to any prior version, non-destructively: the chosen version becomes current again while all versions stay in history.",
      "The chat agent can inspect history and roll back too (data_sources_list_versions / data_sources_rollback).",
      "Completes the edit + roll back capability; export-by-version is the last piece of the arc.",
    ],
  },
  {
    version: "0.17.99",
    date: "2026-05-29",
    title: "Data sources: edit any source's guidance, with versioning.",
    highlights: [
      "You can now edit a system (bundled) data source's 'How to simulate' guidance straight from the card — not just your own uploads.",
      "Every edit is versioned: the shipped file is never modified, and the pristine original is preserved as version 1 so nothing is lost.",
      "The chat agent can make the same edits on your behalf via the new data_sources_edit tool (catalog-side, no secrets).",
      "Foundation of the versioning arc — history view + rollback and export-by-version follow in the next releases.",
    ],
  },
  {
    version: "0.17.98",
    date: "2026-05-29",
    title: "Login: tightened the animated capability cycle copy.",
    highlights: [
      "Shortened the login screen's longest rotating phrase ('orchestrate workflows' → 'run workflows') so the cycle reads at an even length.",
    ],
  },
  {
    version: "0.17.97",
    date: "2026-05-29",
    title:
      "Data source guidance: one clean 'how to use' section, no hardcoded broker address.",
    highlights: [
      "The drawer's simulation guidance had two overlapping sections repeating the same CEF routing — merged into one.",
      "Removed the hardcoded lab broker IP/port (10.10.0.8:514); the broker is now described generically since it's per-environment.",
      "Every vendor's specific CEF-header / discriminator / saturation guidance is preserved.",
    ],
  },
  {
    version: "0.17.96",
    date: "2026-05-29",
    title:
      "Installed data sources: vendor logo / name / use-cases / field count now render correctly.",
    highlights: [
      "Fixed Installed-tab cards falling back to a blank vendor (no logo, name, or use-cases) and a stale field count.",
      "Root cause: the per-row enrichment maps were keyed by the short pack id but looked up by the full pack/rule/dataset id, so they never matched.",
      "Completes v0.17.95 — the Installed-card live field-count overlay now actually applies.",
    ],
  },
  {
    version: "0.17.95",
    date: "2026-05-29",
    title:
      "Data source drawer: field-count tiles now match the field table.",
    highlights: [
      "Fixed the drawer's 'Total Fields' / 'Vendor Fields' tiles showing a different number than the field table below them (e.g. 25 vs 45).",
      "The tile counts are now derived from the same fields[] array the table renders — tile == table == Browse badge, always.",
      "The Installed-tab card badge now reads its field count live from the YAML instead of a stale install-time snapshot.",
    ],
  },
  {
    version: "0.17.94",
    date: "2026-05-29",
    title:
      "Data sources: deduped the catalog (342 → 288) + consolidated Amazon into AWS.",
    highlights: [
      "Browse no longer shows duplicate vendor rows — the modeling-rule pipeline had left multiple dirs per (vendor, product, dataset) differing only by a version suffix.",
      "54 directories removed. Each collision kept the validated/tested source, else the most complete schema (e.g. GuardDuty kept its 62-field variant, Slack dropped a 7-field stub).",
      "Version suffixes stripped from every source name (FortiGate_1_3 → FortiGate); the separate version: field is untouched, so no version info is lost.",
      "Amazon ELB folded into the 'Amazon Web Services' card — no more stray single-source 'Amazon' vendor.",
      "CI guard added: the build now fails if duplicate data sources (case-insensitive) or split vendor names ever return.",
    ],
  },
  {
    version: "0.17.93",
    date: "2026-05-28",
    title:
      "Skill: build_xql_query.md disambiguates XDR vs XSIAM tool routing.",
    highlights: [
      "Operator-surfaced when evaluation prompt #2 asked about the XSIAM tenant — agent loaded build_xql_query.md (XDR-targeted by design) and called xdr_*_xql_* tools, hitting the wrong tenant.",
      "Fix: top-of-file callout (above the existing 7-step procedure) gives a substitution rule: XDR → xdr_run_xql_query; XSIAM (*_raw datasets, broker, parsing rules) → xsiam_run_xql_query. Steps 1-3 unchanged (XQL syntax docs are tenant-neutral); only the executor changes.",
      "Bug-family complement to v0.17.88 (which fixed stream_simulate_to_xsiam.md). build_xql_query.md is the second of three skills referencing xdr_*_xql_*; the third (xdr_verify_simulation_telemetry.md) is XDR-only by design.",
    ],
  },
  {
    version: "0.17.92",
    date: "2026-05-28",
    title:
      "xlog hot-fix: phantom_kill_worker flattens its signature — same bug-family as v0.17.76's phantom_create_data_worker.",
    highlights: [
      "Live-discovered during chat-driven ServiceNow smoke (session 8b67819e): agent ran the full discover→fire→verify cycle, then phantom_kill_worker(worker_id=...) failed with 'Missing required argument: request' / 'Unexpected keyword argument: worker_id'. Worker leaked indefinitely.",
      "Root cause same as v0.17.76: Pydantic envelope (request: KillWorkerRequest) wraps the function. MCP-tool dispatch operates on connector.yaml's flat args schema, can't compose Pydantic wrappers. Visible only when cleanup actually fires.",
      "Fix: phantom_kill_worker now takes worker_id: str directly (mirrors v0.17.77's create_data_worker flatten). KillWorkerRequest Pydantic class stays defined for internal use; no agent path traverses it now.",
      "Bug-family audit: phantom_create_data_worker (already flat v0.17.77 ✓), phantom_list_workers (no args ✓), phantom_kill_worker (flat now ✓), phantom_create_scenario_worker still has its envelope — tracked for the next time a scenario smoke surfaces it.",
    ],
  },
  {
    version: "0.17.91",
    date: "2026-05-28",
    title:
      "Browse page: small green 'Validated' pill on the 22 smoke-tested vendor rows.",
    highlights: [
      "Closes the operator-acknowledged third item: at-a-glance discoverability of which entries are end-to-end-tested (v0.17.79 simulation → broker → XSIAM raw landing pipeline).",
      "Plumbing: YamlDataSource gains `validated: bool` field, _load_one + from_doc read it from the YAML, to_catalog_row surfaces it on every Browse row.",
      "UI: CatalogRow TS interface gains validated?: boolean. BrowseRow renders a small green pill next to the pack name when row.validated === true (secondary semantic color, mirrors rawlog/user pill style).",
      "Source data: v0.17.90's content audit already stamped `validated: true` on the 22 vendor YAMLs — v0.17.91 is purely the catalog → UI plumbing.",
    ],
  },
  {
    version: "0.17.90",
    date: "2026-05-28",
    title:
      "Content audit: enriched descriptions + 407 field examples across the 22 validated vendor YAMLs.",
    highlights: [
      "Operator surfaced the gap reviewing the ServiceNow drawer — descriptions were 1-line taglines, field examples sparse ('see message', '{}', 'sample_*' placeholders).",
      "scripts/maintainer/enrich_validated_yamls_v2.py rewrites each YAML in place. Idempotent. Targets the 22 vendors from the v0.17.79 autonomous-smoke list.",
      "Each description is now 2-3 sentences covering what the vendor IS, what its CEF logs typically contain, and which detection scenarios simulation enables. Hand-authored; no LLM generation.",
      "Field examples upgraded via type+name heuristics — ipv4→192.168.1.42, port→443, email→alice@example.com, ts→ISO timestamp, json fields named actor/target/httpRequest get vendor-shaped JSON. Already-good examples preserved.",
      "Also stamps validated:true at the YAML top level so v0.17.91 can render a 'Validated' pill on the Browse page row.",
    ],
  },
  {
    version: "0.17.89",
    date: "2026-05-28",
    title:
      "Drawer: 'How to use' section was invisible because the loader keyed on the wrong id.",
    highlights: [
      "Operator-surfaced reviewing the ServiceNow drawer: no 'How to use' section appeared even though the YAML carries multi-paragraph guidance (added per-vendor in v0.17.79).",
      "Root cause: schema endpoint composed `pack/rule/dataset` and called loader.get_by_id, but the loader's index keys on the YAML's `id:` field (often just the short pack name). Mismatch → returns None → enricher's early-return branch had NO `how_to_use` default → field absent → drawer's truthy-check evaluated false → section silently omitted.",
      "Fix: _enrich_with_vendor_meta now parses the 3-tuple from ds_id and calls loader.get_by_3tuple (the canonical resolver, falls back to get_by_id for legacy callers). Early-return branch now sets `payload.setdefault('how_to_use', '')` so the field is always defined.",
      "Both installed + preview-path drawers benefit. Affects all 22 validated vendors AND any other YAMLs with how_to_use content.",
    ],
  },
  {
    version: "0.17.88",
    date: "2026-05-28",
    title:
      "Skill: stream_simulate_to_xsiam hardens tool selection against the cortex-xdr trap.",
    highlights: [
      "v0.17.87 live smoke uncovered: agent fired CEF events to the right broker-derived dataset (amazon_web_services_aws_cloudtrail_raw ✓) but verified via xdr_run_xql_query — wrong connector, different Cortex tenant, 500 errors.",
      "Root cause: agent catalog exposes both xsiam_run_xql_query AND xdr_*_xql_* tools because both connectors are installed. Skill always showed the right tool in code blocks but didn't explicitly prohibit the wrong family.",
      "Fix: new 'Tool selection' callout above Step 6 with a table contrasting xsiam vs xdr tools + the failure mode. New 'Forbidden' bullet calling out xdr_*_xql_*. Updated reference section to repeat the prohibition.",
      "All 22 validated-vendor smoke paths benefit at once — same skill governs all of them.",
    ],
  },
  {
    version: "0.17.87",
    date: "2026-05-28",
    title:
      "Chat: split reasoning from the final answer; collapsible 'Thinking...' section above each assistant turn.",
    highlights: [
      "Operator-surfaced after Gemini 3.5 Flash smoke: the model's extended-thinking text streamed lumped with the final reply (\"My Thought Process as Phantom MCP Agent...\" before the actual answer to \"hi\").",
      "Root cause: route asked Gemini for thoughts via includeThoughts:true, but the per-part loop emitted every part as text_delta. ThinkingSection component existed and was already collapsible-by-default, but never received data.",
      "Fix: GeminiPart gains thought?:boolean. Route branches on part.thought===true → emits the existing 'thinking' SSE event AND skips finalText, so saved content stays the answer-only transcript. useChat appends thinking deltas to message.reasoning. MessageList renders ThinkingSection above the bubble.",
      "Live-only for now — not persisted to MCP storage. Pre-v0.17.87 sessions and non-thinking models look unchanged (ThinkingSection renders null on empty reasoning).",
    ],
  },
  {
    version: "0.17.86",
    date: "2026-05-28",
    title:
      "Catalog: 'wip' flag for coming-soon models + Gemini 3.5 Flash GA.",
    highlights: [
      "Added wip?: boolean to ModelInfo. All 4 Anthropic entries (Opus 4.7 / Sonnet 4.6 / Haiku 4.5 / claude-code CLI) now flagged wip:true — operator decision to revisit Claude later and focus smoke testing on Gemini.",
      "Chat header dropdown filters wip entries before grouping. /services Models page still surfaces them, rendered with reduced opacity, 'Coming soon' badge, grey status dot, no drill-in arrow, outer wrapper switched from <Link> to <div>.",
      "Gemini 3.5 Flash added at the top of VERTEX_MODELS (released at Google I/O 2026, GA on Vertex AI, 1M context, thinking + tools). No Gemini 3.5 Pro yet — Google released only the Flash tier.",
      "Re-enabling a Claude entry as chat-selectable later is a one-line revert: drop the wip:true line.",
    ],
  },
  {
    version: "0.17.85",
    date: "2026-05-28",
    title:
      "Chat: removed the standalone 'Claude Code' toggle; route selection now follows the model dropdown.",
    highlights: [
      "Operator-surfaced: the chat header's Claude Code button (v0.17.56) became redundant the moment v0.17.82 surfaced 'claude-code' as a selectable model (provider 'anthropic-cli') inside the model dropdown.",
      "Behavior: route is now derived from selected model's provider — anthropic-cli → /api/chat/cli (Claude Code shell-out); anything else → /api/chat (Gemini streaming + tool-call loop). One affordance, no possibility of the two settings disagreeing.",
      "Removed the button + its props from chat-header.tsx; replaced useState/localStorage for chatRoute with a derived computation from overrideProvider in use-chat.ts; cleaned the dead 'chat-route-mode' localStorage key on mount.",
      "chatRoute remains exposed as a read-only derived field on UseChatReturn for telemetry/debug consumers. The send-time URL switch in sendMessage is unchanged — chatRouteRef.current still reads 'claude-code' when the operator picks claude-code from the dropdown.",
    ],
  },
  {
    version: "0.17.84",
    date: "2026-05-28",
    title:
      "CI hot-fix: curl --retry-all-errors for the manifest-fetch step so build-dev-installer survives GitHub API flakiness.",
    highlights: [
      "v0.17.83 blocked on 3 back-to-back Build dev installer failures — all at the same sub-step 'fetch latest stable manifest for updater/browser' returning curl 22 (404) on GET /releases/latest, even though gh release list locally showed the release as isLatest=True.",
      "Root cause: upstream GitHub API eventual-consistency / cache-edge flakiness; the endpoint returned 200 from the same shell ~1s later. Workflow's bare curl had no retry, so a single 404 failed the whole build chain.",
      "Fix: added --retry 5 --retry-delay 5 --retry-all-errors to both curl calls in .github/workflows/build-dev-installer.yml. The --retry-all-errors flag is the key — bare --retry only retries on connection errors + 5xx, NOT on 4xx. Now the workflow survives up to 25s of 4xx flakiness.",
      "Added failure-mode entry #14 to docs/CICD.md catalog so the next agent who hits this recognizes the pattern. v0.17.84's own Build dev installer benefits from the new retry logic since the workflow code used at runtime is the post-push branch state.",
    ],
  },
  {
    version: "0.17.83",
    date: "2026-05-28",
    title:
      "Chat CLI: bypass Claude Code's root-guard via IS_SANDBOX=1 so bypassPermissions works inside the agent container.",
    highlights: [
      "Operator surfaced after the v0.17.81 + v0.17.82 save/Models fixes: CLI route returned 'Claude Code exited with code 1. stderr: --dangerously-skip-permissions cannot be used with root/sudo privileges for security reasons'.",
      "Upstream behavior: @anthropic-ai/claude-code refuses to start with --permission-mode bypassPermissions when process.getuid()===0. The guard's premise ('we can't tell if you're sandboxed') is false for phantom_agent — it IS a sandbox by inspection (Docker, bind-mounts only, ephemeral FS).",
      "Fix: added IS_SANDBOX=\"1\" to the envVars block in app/api/chat/cli/route.ts. Upstream code skips the root-check when this env (or CLAUDE_CODE_BUBBLEWRAP=1) is present — the documented escape hatch for 'operator has asserted sandbox status' per upstream issues #9184 and #58150.",
      "The v0.17.72 code-comment block in chat/cli/route.ts gets a new point 4 documenting the reasoning + linking the upstream issues. Cleaner alternative (drop the whole container to a non-root USER in the Dockerfile) parked as its own refactor.",
    ],
  },
  {
    version: "0.17.82",
    date: "2026-05-28",
    title:
      "Models page: Claude entries now surface when the Anthropic provider is configured.",
    highlights: [
      "Operator-surfaced gap: /services Models page didn't list any Claude entries even with the Anthropic provider configured — closes the loop named as a follow-on in the v0.17.81 entry.",
      "Root cause: app/api/agent/models/route.ts had a hardcoded catalog scoped to Vertex only. The chat header's model dropdown reads the same endpoint, so Claude was missing from the chat picker too.",
      "Fix: added an Anthropic catalog (Opus 4.7 / Sonnet 4.6 / Haiku 4.5 streaming + claude-code CLI shell-out). GET handler now probes resolveAnthropicApiKey + resolveAnthropicCliKey — either non-null result surfaces the full Anthropic catalog.",
      "Operators can now configure Anthropic on /providers, see Claude rows on /services, and pick a Claude model from the chat header's model dropdown before sending a message.",
    ],
  },
  {
    version: "0.17.81",
    date: "2026-05-28",
    title:
      "Hot-fix: Anthropic provider save failed when only the CLI device-code OAuth token was supplied.",
    highlights: [
      "Surfaced via live-chat smoke: pasting Claude Code device-code OAuth into /providers Anthropic → click Save → 400 'failed to save Anthropic configuration'.",
      "Root cause: providers/config PUT required EVERY key in requiredOnCreate to be present. For Anthropic the keys list was ['api_key', 'cli_key'] but the comment + intent was 'either suffices'.",
      "Fix: added mode: 'all' | 'any' to requiredOnCreate. Vertex stays 'all' (project_id + region + serviceAccountJson all required at once). Anthropic now uses 'any' — one of api_key / cli_key is enough.",
      "Operators can now save Anthropic configuration with just the Pro/Max device-code OAuth token. The v0.17.80 stream_simulate_to_xsiam skill live test can resume once a provider is configured.",
    ],
  },
  {
    version: "0.17.80",
    date: "2026-05-28",
    title:
      "New skill: stream_simulate_to_xsiam — end-to-end simulation pipeline with L1-L20 baked in.",
    highlights: [
      "New skills/workflows/stream_simulate_to_xsiam.md walks the agent through the full discover → fire → wait → verify raw landing → verify XDM → cleanup loop.",
      "Bakes in the v0.17.79 broker-route guidance: agent parses how_to_use for the CEF vendor + product literals, NOT the YAML display name. Plus multi-dataset discriminator hints (Okta SSO eventType, O365 Workload, Entra category, AKS category).",
      "20 lessons learned (L1-L20) from the R5 smoke run encoded so the agent doesn't re-discover the routing, MTU, JSON-synthesis, and verification pitfalls per session.",
      "Includes a 22-vendor quick-reference table inline + falls back to data-source YAML's how_to_use for vendors not yet validated.",
      "Skill auto-loads via the agent's marker-driven skills bootstrap (see mcp/agent/CLAUDE.md § Skills bootstrap) on next image refresh.",
    ],
  },
  {
    version: "0.17.79",
    date: "2026-05-28",
    title:
      "Data sources: explicit Cortex XSIAM routing per vendor in how_to_use:",
    highlights: [
      "Surfaced via v0.17.78 autonomous smoke across all 22 validated vendors: the operator's installed XSIAM PRs filter on specific CEF vendor/product literals that frequently differ from the YAML's display name (AWS-CloudTrail's marketing name Amazon Web Services / AWS-CloudTrail derives amazon_web_services_aws_cloudtrail_raw at the broker, but the YAML names amazon_aws_raw).",
      "Fix is docs-only: each validated vendor's how_to_use: now carries a 'Sending these logs to Cortex XSIAM' sub-section with the literal CEF vendor+product that produces the YAML's expected dataset, plus the raw-field discriminator for multi-dataset packs (eventType, Workload, category, RecordType).",
      "Phantom stays destination-neutral — the schema doesn't gain XSIAM-specific fields; the routing guidance lives in operator-facing how_to_use markdown that the drawer's 'How to simulate' section renders (already wired in v0.17.75).",
      "New diagnostic: scripts/maintainer/probe_xsiam_datasets.py enumerates the tenant's actual landing matrix via xsiam_get_datasets + run_xql_query, computes broker-auto-derived names, recommends overrides. Re-runnable against any tenant.",
      "All 22 vendors updated in one bug-family pass via the enhance_validated_vendor_yamls.py script extended with cef_vendor/cef_product/routing_notes keyword args.",
    ],
  },
  {
    version: "0.17.78",
    date: "2026-05-28",
    title:
      "xlog: bug-family fix for `lifespan_context['get_xlog_url']` — works in both agent and per-instance container runtimes.",
    highlights: [
      "Surfaced post v0.17.77: with the flattened signature, the agent's chat path reaches the xlog connector container, but the connector raised KeyError('get_xlog_url'). The xlog tools were copy-pasted from agent-runtime code reading a lifespan_context key the per-instance runtime doesn't populate.",
      "New helper bundles/spark/connectors/xlog/src/_xlog_url_resolver.py with resolve_xlog_url(ctx) — tries agent-runtime lifespan_context first, falls back to per-instance config.get_config().baseUrl from the runtime's contextvar.",
      "Bug-family pass: all 14 lifespan_context['get_xlog_url']() call sites across xlog/src/{workers,field_info,data_faker,scenarios,simulation_runs,observables_catalog}.py converted to resolve_xlog_url(ctx) in one PR.",
      "Behavior preservation: agent-runtime callers see no change (helper tries the lifespan key first); per-instance container callers now work too.",
      "Follow-on: xsiam, cortex-xdr, and other connectors with the same pattern likely have the same gap — `grep -rn 'lifespan_context\\[' bundles/spark/connectors/` catalogs the affected sites.",
    ],
  },
  {
    version: "0.17.77",
    date: "2026-05-28",
    title:
      "xlog: flatten phantom_create_data_worker signature — agent's chat path now reaches the connector end-to-end.",
    highlights: [
      "Sequel to v0.17.76. The agent's MCP proxy is fixed at the connector.yaml boundary, but the connector container's Python tool still rejected the flat args because its signature was `phantom_create_data_worker(request: CreateDataWorkerRequest, ctx: Context)` — FastMCP advertised a single `request` parameter, not the individual fields.",
      "Refactored: phantom_create_data_worker now takes individual keyword args (type, *, destination, count, interval, vendor, product, schema_override, etc., ctx). Function body keeps using request.X accessors by reconstructing CreateDataWorkerRequest inside.",
      "Matches the caldera tool pattern (e.g. caldera_get_abilities_by_tactic(tactic, ctx)) — flat args end-to-end through the agent's proxy.",
      "Bug-family follow-on: every other xlog tool (kill_worker, create_scenario_worker, generate_fake_data_v2, get_field_info, generate_observables, etc.) carries the same Pydantic-model-wrap gap. xsiam, cortex-xdr likely also affected. Open issue tracked in CHANGELOG.",
    ],
  },
  {
    version: "0.17.76",
    date: "2026-05-28",
    title:
      "xlog: fix phantom_create_data_worker arg schema — the agent's proxy now accepts vendor-faithful schema_override end-to-end.",
    highlights: [
      "Bug: agent's phantom_create_data_worker proxy validated args against a stale connector.yaml shape (format, rate_per_second, duration_seconds, observables, destination-as-object) — every meaningful field (type, count, vendor, product, schema_override) was rejected with 'Unexpected keyword argument'.",
      "Root cause: bundles/spark/mcp/src/usecase/connector_loader.py synthesizes the agent-side proxy function from connector.yaml's spec.tools[].args, NOT from the connector's actual Pydantic model. The two had drifted.",
      "Fix: rewrote create_data_worker.args[] in xlog/connector.yaml to match the actual CreateDataWorkerRequest model — type, destination (string), count, interval, vendor, product, version, name, tags, tactic, technique, procedure, fields, datetime_iso, observables_dict, required_fields, schema_override, verify_ssl.",
      "Surfaced via v0.17.75 MCP-tool smoke pass on phantom-vm — the agent's chat path can now actually drive vendor-faithful streaming via the data_sources_get_schema → phantom_create_data_worker(schema_override=...) chain.",
      "Direct-UDP smoke harnesses (the path used through v0.17.75) keep working unchanged — they bypass the proxy.",
    ],
  },
  {
    version: "0.17.75",
    date: "2026-05-28",
    title:
      "Data sources: how_to_use field — operator-facing simulation guidance per vendor, rendered as a collapsible 'How to simulate' section in the drawer.",
    highlights: [
      "New how_to_use: field on each data_source.yaml carries multi-line markdown distilled from L1–L20 lessons earned across 28 vendors smoked through the broker → XSIAM pipeline.",
      "22 bundled YAMLs populated: Okta (× 2) · Alibaba · AWS CloudTrail/Security Hub/WAF · Jira · ServiceNow · CyberArk ISP · Entra ID (audit + sign-in) · O365 (× 5 workloads) · Qualys · ProofPoint Email/TAP · Azure Flow Logs/WAF/AKS.",
      "Each entry covers MR pattern (flat-field / mixed / nested-JSON), composite-field packing instructions, sentinel values, PR-filter quirks, single-event XDM ceiling, sibling-dataset list, and a ready-to-paste datamodel XQL verification snippet.",
      "Detail drawer renders the field as a collapsible 'How to simulate' section between description and use-case pills, using shared MarkdownContent for fenced-code syntax highlighting.",
      "REST schema endpoint overlays how_to_use from the YAML loader onto the install-time response (mirrors v0.17.68 YAML-canonical-for-fields[] pattern). Empty for the 320 unvalidated packs; drawer hides the section when empty.",
    ],
  },
  {
    version: "0.17.74",
    date: "2026-05-27",
    title:
      "Data sources: drop XDM mappings from the schema, fix vendor-prefix example placeholders corpus-wide, cleaner export filename.",
    highlights: [
      "Schema: xdm_mappings dropped entirely — data sources are a vendor-neutral wire-format spec, XDM is a Cortex-specific downstream consumer. Stripped from all 342 bundled YAMLs + the Python loader + the UI drawer + the upload-dialog example.",
      "Examples: replaced the synthesis script's ugly fallback (`Amazon Web Services-httprequest`, `Microsoft-process name`) with name-derived `sample_*` shapes + expanded pattern coverage — ARN, AWS principal/access-key IDs, CEF custom strings, MAC/account/subscription IDs, threat/policy/agent names. 4451 examples rewritten across 316 packs.",
      "Export filename: `<dataset>.yaml` (e.g. `aws_waf_raw.yaml`) instead of the triple-repeating `<pack>__<rule>__<dataset>.yaml`. Cleaner save dialogs for the v0.17.73 Export button.",
      "Stale-example detector in the synthesis script: recognizes the pre-v0.17.74 fallback shape and overwrites it, not just remaining `example_value` entries. Re-runnable safely on a clean corpus (idempotent).",
      "Schema validation: 342/342 packs pass. Zero `<Vendor>-<suffix>` placeholders remain (was 4361 pre-fix).",
    ],
  },
  {
    version: "0.17.73",
    date: "2026-05-27",
    title:
      "Data sources: Export YAML button on every Browse row — download the raw data_source.yaml to fork or share.",
    highlights: [
      "Every row on the Browse tab now has an Export anchor sibling to Install: downloads <pack>__<rule>__<dataset>.yaml straight to disk.",
      "Backed by a new MCP route GET /api/v1/data-sources/{pack}/{rule}/{dataset}/export that returns the raw on-disk YAML verbatim — operator-authored comments + ordering + whitespace preserved (not a round-trip).",
      "Works for both bundled packs (/app/bundle/data-sources/<id>) and user-uploaded packs (/app/data/user_data_sources/<id>) through the same endpoint via the YAML loader's _source_path.",
      "Fork-to-edit workflow: download bundled → tweak locally → upload via the existing user-upload route. Out-of-band sharing: send a vendor spec to a colleague or back up a pack before a refresh.",
      "Auth: session-cookie via middleware (same as the rest of /api/agent/data-sources/*). Bearer-auth gated on the MCP side.",
    ],
  },
  {
    version: "0.17.72",
    date: "2026-05-26",
    title:
      "Claude Code CLI: device-token / OAuth path fixed by porting Kite's working pattern (clearEnv ANTHROPIC_API_KEY + bypassPermissions + claude binary).",
    highlights: [
      "Operator-reported: Claude Code CLI failed silently when only a device token (Max subscription) was saved in /providers — token was getting injected as ANTHROPIC_API_KEY which broke the OAuth flow.",
      "Bug 1 fixed: route was setting BOTH ANTHROPIC_API_KEY and CLAUDE_CODE_OAUTH_TOKEN to the same value. Claude Code prefers the API_KEY path; with a device token in that slot it returned 401. Now sets ONLY CLAUDE_CODE_OAUTH_TOKEN.",
      "Bug 2 fixed: missing --permission-mode bypassPermissions caused stalls at interactive permission prompts in --print mode. Watchdog killed the process before output.",
      "Bug 3 fixed: switched from npx @anthropic-ai/claude-code to /usr/bin/claude (already in the image; matches Kite's DEFAULT_CLAUDE_BACKEND).",
      "New cli-wrapper.ts feature: clearEnv field deletes keys from the inherited env after the envVars overlay — needed because /opt/phantom/.env may have a stale ANTHROPIC_API_KEY that would otherwise shadow the OAuth token.",
    ],
  },
  {
    version: "0.17.71",
    date: "2026-05-26",
    title:
      "Data sources: 7,575 generic 'example_value' placeholders replaced with vendor-realistic synthetic examples corpus-wide.",
    highlights: [
      "Operator-spotted gap from v0.17.70 UI verification — drawer rendered `example_value` in the Example column for ~63% of fields because the mass-polish fallback for type:string was a generic placeholder.",
      "New scripts/synthesize_realistic_examples.py applies a 60+ name-pattern library: meta fields (_vendor, _product, _raw_log) pulled from each pack's own metadata, identifier patterns (uuid, session_id) get stable uuid5-derived values, user/network/cloud/web fields get RFC-safe realistic samples.",
      "Okta's _vendor now shows 'Okta', FortiGate's _product shows 'FortiGate', actor.displayName shows 'John Doe', session_id shows 'sess-abc12345' — everywhere previously 'example_value'.",
      "Stable synthesis: re-running the script produces byte-identical output (fixed uuid5 namespace).",
      "Corpus state after this: 0 generic stubs in examples, 342/342 schema-valid, 12,003 fields total.",
    ],
  },
  {
    version: "0.17.70",
    date: "2026-05-26",
    title:
      "Journeys: split combined install-data-source journey into two focused journeys (data-sources workflow + simulation).",
    highlights: [
      "New `install-data-source` journey (category: data-sources, starter, 2 min) — focused on the management workflow: browse marketplace → preview drawer (Name/Type/Description/Example columns) → install → optional uninstall. New DELETE endpoint documented.",
      "New `simulate-from-installed-data-source` journey (category: simulation, intermediate, 2 min) — focused on log generation: data_sources_list → data_sources_get_schema → phantom_generate_fake_data_v2 (or phantom_create_data_worker for UDP destinations). Two prompts covering both in-chat preview and UDP-destination variants.",
      "New top-level category `data-sources` in journeys.ts CATEGORY_META — distinct from `connectors` (external integrations) and `simulation` (generation). Journeys index page surfaces it as its own first-class tab.",
      "Sibling journeys (generate-firewall-logs, edit-user-data-source) updated to reference the new split pair.",
      "Closes operator-spotted Q1 UX issue from the docs-round-2 arc.",
    ],
  },
  {
    version: "0.17.69",
    date: "2026-05-26",
    title:
      "Arc C closure: per-pack manual review across 342 data sources — 297 files of corrective + vendor-doc polish.",
    highlights: [
      "Pre-existing data bugs fixed: FortiGate eventtime correctly typed integer (NANOseconds not ms); Proofpoint audit.user.email retyped email; Semperis is_rawlog_only flipped + 3 XIF-local artifacts dropped; Barracuda Email message_id retyped string (Message-IDs aren't addressable emails).",
      "Bug-family audit: 16 *_bytes fixes → integer_byte_count, 4 hash retypes, 7 *.email user→email retypes, 21 Ivanti extract_* artifacts dropped, 67 ALL_CAPS XDM_CONST literals dropped across 36 packs.",
      "Name-pattern mechanical type-fixes: 52 fields retyped from string to url/datetime/integer based on suffix patterns.",
      "v0.16.0 cohort re-applied: 1,056 fields across 32 top-vendor packs now carry curated vendor-doc descriptions (Okta, AWS CloudTrail, Azure AD, FortiGate, Sysmon, Cisco ASA, MDE, etc.).",
      "Long-tail mass polish: new scripts/polish_long_tail_fields.py applies a CEF + identity + network + file + time pattern library — 2,220 additional fields polished across 252 packs in one pass.",
      "Corpus state: 12,003 fields across 342 packs, 25 of 26 schema types in active use (was mostly 'string'), 0 XDM leakage, generic stubs reduced from 6,182 to 3,827. Closes #97.",
    ],
  },
  {
    version: "0.17.68",
    date: "2026-05-26",
    title:
      "Data-source drawer: bundled YAML is now canonical (correct types + full dotted-path leaves + Example column).",
    highlights: [
      "Drawer was reading fields from cortex schema.json (top-level only, all typed string, no examples). Now reads the full record from the bundled data_source.yaml — composite types like json show as json, dotted-path leaves like audit.user.email appear under their parent, examples populate.",
      "New Example column in the drawer's Schema Fields table (12-col grid: Name 3 / Type 2 / Description 4 / Example 3). Monospace token with hover tooltip for long JSON composite values.",
      "Backend: _yaml_field_descriptions (descriptions-only overlay) replaced by _yaml_field_records (full per-field record). _extract_and_compose_data_sources prefers YAML when present; cortex schema.json is the fallback for packs without a YAML.",
      "SQLite migration: data_source_fields adds an example column. Idempotent PRAGMA-guarded ALTER (same pattern as v0.17.7's description migration). Installed packs upgrade in place.",
      "ProofpointEmailSecurity drawer goes from 15 fields (all typed string, no examples) to 62 (15 top + 47 leaves, correct types, examples populated). FortiGate from 49 to 222.",
      "Operator-spotted regression from v0.17.67 verification — fixed in the same Arc C arc.",
    ],
  },
  {
    version: "0.17.67",
    date: "2026-05-26",
    title:
      "Arc C tooling iteration 3+4: corpus consistency baseline — every field across 342 packs now carries vendor-neutral 2-sentence description + synthetic-realistic example.",
    highlights: [
      "Every description follows the same 2-sentence shape: <vendor concept>. <wire-shape constraint per type>. — teaches Phantom what form the value must take so modeling rules (Cortex, Splunk, Elastic) succeed.",
      "Zero XDM / XDM_CONST / 'Drives xdm' / 'Maps to xdm' / stranded arrow leakage anywhere in the corpus. data_source.yaml is now vendor-neutral spec; not a Cortex-specific mapping document.",
      "New maintainer script scripts/scrub_descriptions_examples.py: 26 per-type wire-shape templates + synthetic-realistic examples (RFC 5737 IPs, ISO-8601 timestamps, RFC 3849 IPv6, …). Preserves rich existing examples and operator-curated concept text.",
      "draft_composite_corrections.py iteration 3.2: tightened _is_extractor_artifact filter prunes v0.17.25 root-extractor noise (single-char regex fragments, ALL_CAPS enum constants, get_/set_/tmp_ helper locals) — 304 artifact entries dropped across 40 packs, while real vendor fields like Salesforce API_TYPE survive.",
      "Composite descriptions enumerate keys (≤40 keys: inline full list; 40+ keys: defer to dotted-path leaves). Enum descriptions enumerate ALL values (no truncation) per operator directive.",
      "Pack count unchanged at 342; field count 8,928 → 12,102 (+3,174 newly-discovered Pattern-P3 leaves). Schema validation: 342/342 valid. Mechanical baseline ready for per-pack manual review pass.",
    ],
  },
  {
    version: "0.17.66",
    date: "2026-05-26",
    title:
      "Arc C tooling iteration 2: leaf-type inference + array-of-objects classification + enum-forcing + Proofpoint heal.",
    highlights: [
      "Script now propagates XDM-target type hints to LEAVES (not just top-level fields). file.identity.md5 → hash_md5, file.file_name → file_path, etc.",
      "Array-of-objects fields get type:json (was wrongly type:string + is_array:true). computer.network_addresses now correctly typed.",
      "Intrinsic-property forced types: enum_values forces type:enum; regex_pattern forces type:regex. Prevents the v0.17.65 Proofpoint event_type bug from ever recurring.",
      "Heals Proofpoint's event_type: was type:string + enum_values (mismatched in v0.17.65), now type:enum + enum_values (consistent).",
      "Naming-pattern heuristics for leaves: *.md5 → hash_md5, *.mac → mac, *.hostname → host, *.port → integer_port.",
    ],
  },
  {
    version: "0.17.65",
    date: "2026-05-26",
    title:
      "Arc C tooling: scripts/draft_composite_corrections.py maintainer script for the 342-pack composite-correction sweep.",
    highlights: [
      "Maintainer script reads each pack's .xif + schema.json + existing YAML and drafts a Pattern-P3 correction. Output is a draft for human review; not auto-committed.",
      "Handles every XIF pattern in the corpus: field -> nested.path derefs, field -> [] arrays, arraymap with @element sub-paths, JSONPath extracts, [RULE:] blocks with call directives, multi-dataset XIFs, backtick-quoted reserved words, local-variable bindings.",
      "Cross-references against schema.json to filter out local-variable derefs (computed identifiers like get_data). Preserves all existing hand-curated field entries (134 packs would lose 4,644 entries from v0.16.0 vendor-doc work without this preservation).",
      "Validated on 6 fixtures: ProofpointEmailSecurity, AMP, AWS-CloudTrail, Office365 ×5, AzureDevOps, AbnormalSecurity. Full corpus dry-run: 342/342 packs parse cleanly, 2,858 leaves discovered, all YAMLs validate against the schema.",
      "Also adds the missing filter.actions array entry to Proofpoint so it matches the script's discovery shape (15 top-level + 47 leaves; 62 total).",
      "Drafts get regenerated + manually reviewed pack-by-pack in future sessions; single commit will land all reviewed YAMLs at arc closure.",
    ],
  },
  {
    version: "0.17.64",
    date: "2026-05-26",
    title:
      "Arc C: Pattern P3 adoption — Proofpoint dotted-path leaf backfill (revises 1/342).",
    highlights: [
      "Pattern P3 (hybrid) adopted at operator's direction: keep top-level wire entries (composites as type:json with shape example) AND add dotted-path leaf entries for every nested path the modeling rule derefs.",
      "Proofpoint now ships 61 fields total: 15 wire entries (4 scalars + 11 json composites) + 46 dotted-path leaves with per-leaf types (email, host, hash_md5, hash_sha256, boolean, integer_byte_count, etc.).",
      "Both views serve different consumers: the wire-shape entries drive the generator; the dotted-path leaves drive UI granularity, XDM mapping discovery, and future per-leaf generator improvements.",
      "Pattern P3 is the canonical shape going forward. AMP gets the same backfill in v0.17.65; AWS-CloudTrail (already has Pattern B leaves) gets top-level wire entries added in v0.17.66.",
    ],
  },
  {
    version: "0.17.63",
    date: "2026-05-26",
    title:
      "Arc C: AMP / Cisco Secure Endpoint composite-shape correction (2/342).",
    highlights: [
      "16 fields rewritten on AMP/Cisco Secure Endpoint YAML. 8 of 16 fields were misclassified composites.",
      "Composite objects (string → json): computer, file, cloud_ioc, command_line, vulnerabilities, error, threat_hunting, network_info — each with nested-path example showing the modeling-rule shape.",
      "tactics + techniques promoted to type:string is_array:true (modeling rule's arraymap + trim pattern proves string-array semantics).",
      "Scalar descriptions clarified to describe each field's XDM mapping role instead of one extracted property.",
      "Pack description rewritten from 'Uses CISCO AMP Endpoint' to a complete one-paragraph summary.",
    ],
  },
  {
    version: "0.17.62",
    date: "2026-05-26",
    title:
      "Arc C kickoff: data_source schema sync + ProofpointEmailSecurity composite-shape correction (1/342).",
    highlights: [
      "Patched schema drift: data_source.schema.json now declares use_cases (was silently rejected) and accepts branded-recolored / monochrome-brand fidelity values. All 342 bundled packs now pass strict validation.",
      "ProofpointEmailSecurity YAML rewritten: 11 of 15 fields were misclassified — composite objects (msg, msgParts, filter, connection, sm, tls, audit, metadata, parsed_fields, envelope, pps) typed as string with wrong descriptions.",
      "Composite fields now carry type:json with JSON-stringified examples showing nested paths the modeling rule derefs. event_type promoted to enum with message/maillog/audit.",
      "First pack of a 342-pack workstream (tracking issue #97). One pack per release; quality over speed per operator directive.",
      "Runtime generator change defers to R2.2 — for now the YAML is canonical wire-shape documentation visible on the /data-sources drawer.",
    ],
  },
  {
    version: "0.17.61",
    date: "2026-05-25",
    title:
      "Docs arc R2.0e: dropped 'Include rawlog-only' checkbox + removed 'XDM mappings populate in a future release' fallback text.",
    highlights: [
      "Browse-tab toolbar is tighter: Source dropdown (System/User filter) stays, rawlog-only checkbox removed.",
      "Backend ?include_rawlog= query param is unchanged — only the UI toggle came out. Power users can still hit it via curl.",
      "Data-source drawer no longer shows the 'XDM mappings populate in a future release' italic line. When a source has no XDM mappings the section silently omits.",
      "The whole XDM-mappings section is going away in R2.2 (schema migration) — this is the last operator-facing XDM mention in the UI.",
    ],
  },
  {
    version: "0.17.60",
    date: "2026-05-25",
    title:
      "Docs arc R2.0d: System/User origin filter dropdown on /data-sources Browse.",
    highlights: [
      "New Source dropdown on the Browse tab filters between All / System (bundled) / User (operator-uploaded) data sources.",
      "Backend support was already there — catalog rows have carried the optional origin field since v0.13.1. This release just wires the UI dropdown.",
      "Client-side filter applied in the existing grouped useMemo alongside search + use-case chips. Composes cleanly with both.",
      "Backwards-compatible: rows missing the optional origin field are treated as bundle (default for pre-enrichment catalog shapes).",
      "Native select kept simple — 3 options doesn't merit a custom popover dropdown.",
    ],
  },
  {
    version: "0.17.59",
    date: "2026-05-25",
    title:
      "Docs arc R2.0c: journey prerequisites field + integration-neutral language pass on journeys.",
    highlights: [
      "New 'Before you start' callout on each journey detail page lists prerequisite journeys as clickable cards. Guidance-only — Phantom doesn't block execution, but operators landing cold see what setup is missing.",
      "Populated prerequisites on 8 journeys: simulation journeys link to configure-tech-stack; edit-user-data-source links to upload-custom-data-source; CALDERA journeys chain on deploy-caldera-sandcat; validate-detection links to generate-firewall-logs + configure-vertex-provider.",
      "install-data-source-simulate-vendor-logs journey now shows a chat-driven install prompt as step 1 — operators see the install step in the prompts list, not only buried in the howToTest section.",
      "API descriptions in the same journey cleaned of XDM-mapping language. Install body documented as vendor + product (legacy pack/rule/dataset shape still accepted during the migration window).",
      "Cortex/XSIAM mentions remaining in journeys are in integration-explicit journeys (validate-detection, sync-xsiam-issues, etc.) where the context is appropriate.",
    ],
  },
  {
    version: "0.17.58",
    date: "2026-05-25",
    title:
      "Docs arc R2.0b: log-destinations flow diagram added to /help/architecture#log-destinations.",
    highlights: [
      "New SVG flow diagram visualizes the four lanes a /log-destinations request travels: browser → Next.js proxy → MCP (types loader + store + handler registry) → SQLite + SecretStore + external destinations.",
      "Credential boundary is explicit: secrets land in SecretStore (warn-yellow callout), not in log_destinations.db. The MCP agent tools return *** sentinels for every secret slot.",
      "Send path is the only edge crossing the trust boundary — handler_registry → External destinations (orange). Every other write stays inside the container.",
      "Plugin pattern made visible: types_loader + handler_registry both read from bundles/spark/destinations/. Adding a new destination type = ship one spec.yaml + one handler.py.",
      "Theme-aware via DIAGRAM_THEME_CSS — colors swap cleanly on light/dark toggle, no hardcoded hex values.",
    ],
  },
  {
    version: "0.17.57",
    date: "2026-05-25",
    title:
      "Docs arc R2.0: /help/architecture#data-sources rewritten to target state; round-2 integration-neutral language pass.",
    highlights: [
      "Architecture page now describes the cleaned-up data_sources.db schema (2 tables, no pack/rule/dataset columns, no data_source_xdm_mappings table, new example column for composite fields).",
      "id composition shift documented: <vendor>_<product> instead of <pack>_<rule>_<dataset>. Aligns with the dataset-naming convention the agent uses for XQL queries.",
      "Bundled YAMLs reorganized to <vendor>__<product>/ layout with source_provenance block (cortex pack/rule/dataset moves there as build-time forensic info, NOT persisted into the install DB).",
      "Implementation gap blocks mark every place the running code hasn't migrated yet — the migration lands in follow-on sub-releases (R2.1 skill, R2.2 schema migration, R2.3 MCP tools, R2.4 UI cleanup, R2.5 audit).",
      "Round-2 integration-neutral language pass: Cortex/XSIAM/XDR/PANW terms removed from general-purpose paragraphs in /help/user + journeys.ts. They stay only in integration-specific sections.",
    ],
  },
  {
    version: "0.17.56",
    date: "2026-05-25",
    title:
      "Multi-provider arc · A1.2: chat-header toggle for Claude Code mode (one click instead of curl).",
    highlights: [
      "Chat header now carries a Claude Code toggle button. Click it to route the next message through /api/chat/cli (v0.17.54) instead of the default Gemini chat-route.",
      "Toggle state persists in localStorage so the operator's last choice survives page reload.",
      "useChat hook branches the SSE event handler internally — a separate dispatcher parses Claude Code's output / output_raw / done / error events into the message bubble.",
      "stderr tail surfaces in the assistant message when Claude Code exits non-zero or times out, so failures don't disappear silently.",
      "A6 (v0.17.61) will replace this binary toggle with a unified provider dropdown covering Gemini variants, Anthropic API, Codex, OpenAI, and Ollama.",
    ],
  },
  {
    version: "0.17.55",
    date: "2026-05-25",
    title:
      "Multi-provider arc · A1.1: /providers page persists Anthropic API key + Claude Code CLI key into ProviderStore.",
    highlights: [
      "Anthropic card on /providers is now functional — no more WIP greyout. Save button persists API key + CLI key into ProviderStore alongside Vertex.",
      "PUT /api/agent/providers/config now syncs vertex + anthropic in parallel and returns per-provider mcp_sync metadata; 400 if either fails.",
      "Credential cache busts immediately after write — the next chat turn picks up the new keys without the 30s cache wait.",
      "v0.17.54's /api/chat/cli now resolves credentials from the store directly; ANTHROPIC_API_KEY in /opt/phantom/.env stays as a backup path but is no longer required.",
      "Test Connection button stays disabled for Anthropic until A2 lands callAnthropic(). For now, smoke via curl /api/chat/cli.",
    ],
  },
  {
    version: "0.17.54",
    date: "2026-05-25",
    title:
      "Multi-provider arc · A1 first slice: Claude Code CLI shell-out endpoint (Anthropic as a second model option).",
    highlights: [
      "New POST /api/chat/cli — operators can drive a chat turn through Anthropic's Claude Code as a second model option alongside the default Gemini chat-route.",
      "Claude Code is baked into the phantom-agent image (@anthropic-ai/claude-code@^1.0.0), so first invocation is sub-second instead of waiting for an npx download.",
      "New lib/cli-wrapper.ts ports Spark's plugin-runner pattern to Phantom's single-container model — child_process.spawn instead of Docker-in-Docker.",
      "New lib/anthropic-credentials.ts mirrors vertex-credentials: ProviderStore lookup with env-var fallback (ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN).",
      "First sub-release of a multi-provider arc — A1.1 adds ProviderStore persistence for the API key, A1.2 adds a chat-header UI toggle, A2-A6 follow with Anthropic API, Codex CLI, OpenAI API, Ollama, and full provider toggle UI.",
    ],
  },
  {
    version: "0.17.53",
    date: "2026-05-25",
    title:
      "Help docs: integration-neutral language pass (round 1) — Phantom is destination-neutral, not an XSIAM accessory.",
    highlights: [
      "Architecture #data-sources opener rewritten: vendor schemas are 'structured descriptions of what a vendor emits on the wire' — Cortex content is ONE source, not the destination.",
      "User guide #data-sources opener + 'What vendor-faithful means' rewritten: downstream parsing described integration-neutral, with XSIAM listed alongside Splunk TAs, Sentinel parsers, Elastic ingest pipelines.",
      "User guide log-destinations 'Vendor-faithful simulation' reframed: a FortiGate event lands in a vendor-tagged dataset that any FortiGate-aware parser ingests, not just XSIAM.",
      "Connector-specific Sections (XSIAM, Cortex XDR, cortex-content) unchanged — they document specific integrations and should stay specific.",
      "First sub-release of the neutral-language arc. v0.17.54 covers connector-section openers + xlog/CALDERA framing. v0.17.55 covers journeys.ts examples.",
    ],
  },
  {
    version: "0.17.52",
    date: "2026-05-25",
    title:
      "Help docs: Sub-agents deep dive — constraints, REST surface, decision guide, debugging ladder. Phase 2 closes.",
    highlights: [
      "Architecture: Subagents Section repaired (broken opener restored) + new 'Constraints + dispatch model' subsection (target-state framing of the three design choices: foreground-only, bounded depth, tool-scope as security model).",
      "Architecture: new 'REST + UI surface' subsection lists all 6 agent-definition endpoints + the programmatic dispatch route + the UI + observability filter strings.",
      "Architecture: 'Implementation references' source-file index added.",
      "User guide: new 'When to spawn vs ask the parent' subsection — three concrete scenarios subagents are right for plus the inverse.",
      "User guide: new 'Debugging subagents' subsection — five-step ladder using sidechain links, audit filters, blocked-tool events, max_turns cap, cost rollup.",
      "Closes Phase 2 of the customer-doc arc. Phase 3 (per-component audit + sync across all 4 surfaces) starts next: skills, memory, jobs, knowledge, marketplace, log destinations, providers, api keys, approvals, notifications, audit, tasks, plugins, per-connector deep dives.",
    ],
  },
  {
    version: "0.17.51",
    date: "2026-05-25",
    title:
      "Help docs: Hooks deep dive — per-transport end-to-end walkthroughs + debugging ladder.",
    highlights: [
      "Architecture: Hooks Section gains per-transport walkthroughs (builtin/http/command/plugin/agent) with wire-format pseudocode, latency expectations, right-fit use cases.",
      "Architecture: new Fire-site catalog subsection enumerates all 10 fire-sites with payload shape + decision semantics + injectContext role.",
      "Architecture: new REST + UI surface subsection lists every hook endpoint plus /settings/hooks and the /observability/events filters.",
      "User guide: new Debugging hooks subsection — five-step ladder using audit filters, dry-run endpoint, enable toggle, and failure-policy review.",
      "Stripped all version annotations (v0.5.21, Issue #28/25/27/31, v0.5.48, Phase X) from the hooks-ux body. Repaired stranded 'Shipped in' fragment in the plugin transport description and the broken Task Registry opener.",
      "Fifth sub-release of Phase 2. Sub-agents deep dive closes Phase 2 next.",
    ],
  },
  {
    version: "0.17.50",
    date: "2026-05-25",
    title:
      "Help docs: Observability Overview section indexes all 10 surfaces with a 'when to use which' decision tree.",
    highlights: [
      "Architecture: new Observability Overview Section at the top of the Operability group. Lists every /observability/* page with one-line role + deep-link to specs.",
      "Three-layer telemetry diagram explains how the 3 aggregation stores (audit.db / metrics_registry / event_log) differ by cardinality + retention.",
      "Operator decision tree walks 8 common questions to the right surface ('Why did this turn fail?' → /observability/events; 'How long are turns taking?' → /observability/traces; etc.).",
      "Retention + privacy contract documents per-store retention windows + the no-PII sanitization gate.",
      "Fourth sub-release of Phase 2. Hooks + Sub-agents deep dives close Phase 2.",
    ],
  },
  {
    version: "0.17.49",
    date: "2026-05-25",
    title:
      "Help docs: dedicated Backup & Restore section promoted from settings-precedence Scenario 3e.",
    highlights: [
      "User guide: new Backup & Restore Section in the Settings group with six subsections — Backup contents, dry-run preview, dependency-ordered apply, collision semantics, caveats, REST API surface.",
      "settings-precedence Scenario 3e slimmed from a comprehensive walkthrough to a brief cross-link.",
      "Third sub-release of Phase 2. Observability overview + Hooks + Sub-agents deep dives follow.",
    ],
  },
  {
    version: "0.17.48",
    date: "2026-05-25",
    title:
      "Help docs: Setup & First-Run Wiring section closes a long-standing documentation gap.",
    highlights: [
      "Architecture: new Setup & First-Run Wiring section (Foundation group, anchor #setup-wiring) with six subsections — installer-side .env generation, six-step entrypoint seed sequence, first operator login + forced password rotation, provider configuration, connector + instance configuration, and factory reset.",
      "The first-run flow was previously scattered across boot-lifecycle / authentication / secret-store; now has one authoritative explanation.",
      "Second sub-release of Phase 2. Backup/Restore + Observability overview + Hooks + Sub-agents deep dives follow.",
    ],
  },
  {
    version: "0.17.47",
    date: "2026-05-25",
    title:
      "Help docs: dedicated Personality store section in architecture + deep operator walkthrough in user guide.",
    highlights: [
      "Architecture: new Personality Store section under Operability — full schema, REST surface, 3-tier MCP tool surface, chat-consumption notes, audit + history reference, source-file index. Sits next to settings-tuning in the left rail.",
      "Architecture: fixed the broken settings-tuning opener ('exposed 's hardcoded constants…') and rewrote the wiring status to describe live behavior, not a future-phase disclosure.",
      "User guide: settings-personality grew from two paragraphs to four subsections — Persona panel, Tuning panel (all four sliders explained with tuning recommendations), History + Reset, and 'Asking the agent to update the persona' (three example chat prompts).",
      "First sub-release of Phase 2. Setup-wiring + Backup/Restore + Observability overview + Hooks + Sub-agents deep dives follow.",
    ],
  },
  {
    version: "0.17.46",
    date: "2026-05-25",
    title:
      "Help docs: duplicate password-change subsections + stale 'HTTP Basic' auth model resolved. Closes Phase 1 of the doc audit arc.",
    highlights: [
      "Architecture page: auth-identity Operator → UI subsection was stale (described HTTP Basic with UI_USER/UI_PASSWORD env vars); rewrote as a cross-link to the dedicated #authentication section which describes the actual PBKDF2 cookie session.",
      "Architecture page: removed the auth-identity 'VM access (IAP tunnel)' subsection — dev-environment internal context, not customer-facing.",
      "Architecture page rest-api section: 'HTTP Basic auth on the agent side' claim corrected to 'phantom_session cookie' in two places.",
      "User guide: password-change was documented in three places (authentication + profile + settings-precedence); canonicalized to one — authentication is the authoritative walkthrough, the other two cross-link to it.",
      "Closes Phase 1 of the doc audit arc. Phase 2 ahead: dedicated personality, setup-wiring, backup/restore, and observability-overview sections; hooks + sub-agents deep dives.",
    ],
  },
  {
    version: "0.17.45",
    date: "2026-05-25",
    title:
      "Help docs nav — ghost sections surfaced. Architecture + user-guide left rail now covers every rendered section.",
    highlights: [
      "Architecture page: added 7 sections to the left rail nav (image-pinning, tls-proxy, phantom-updater, connector-containers, data-sources, log-destinations, operator-state). They rendered before but were invisible to the sidebar.",
      "Corrected the stale 'Service Stack' label (was '3-Service Stack' — the section actually describes five fixed services).",
      "User guide: added 5 sections to the left rail (profile, upgrades, data-sources, log-destinations-ux, detection-inventory). Same orphan pattern.",
      "Pre-deploy gate: tsc clean + Next.js prod build clean.",
    ],
  },
  {
    version: "0.17.44",
    date: "2026-05-25",
    title:
      "Journey bodies: stripped release-history framing — surviving journeys describe target-state, not 'what was added when'.",
    highlights: [
      "Round-12 / Round-13 / Round-14 / Phase 4.3 / Phase 6 / Phase 3 internal milestone labels removed from journey body text.",
      "Issue tracker references (#22, #23, #26) and commit hash (88e0ae5) citations removed.",
      "Implementation-gap leaks like 'chat-route Gemini wiring lands in a follow-up' cleaned up — operators see the feature as it functions today.",
      "middleware.ts (v0.9.1+) version annotation stripped from backup/restore journey body.",
      "Pre-deploy gate: tsc clean.",
    ],
  },
  {
    version: "0.17.43",
    date: "2026-05-25",
    title:
      "Journeys cleanup — engineering-acceptance-test bundles + obsolete upgrade journey retired.",
    highlights: [
      "Retired the 10-journey 'v0.5.0 test' bundle and the 3-journey 'v0.5.1 test' bundle. These were operator-walkable QA matrices using raw curl + docker exec, not customer workflows. The platform's customer-walkable equivalents already cover the same surfaces in operator language.",
      "Retired the 'Upgrade Phantom from v0.2.x → v0.3.0' journey. No current customer is on v0.2.x.",
      "Removed the 'v050-test' / 'v051-test' filter chip values from the /help/journeys filter strip.",
      "Net diff: -680 lines from journeys.ts.",
      "Body annotation strips (Round-12 / Phase 4.3 / Issue #23 / commit-hash references) ship in v0.17.44.",
    ],
  },
  {
    version: "0.17.42",
    date: "2026-05-25",
    title:
      "User guide subsection titles cleaned — version annotations removed.",
    highlights: [
      "10 subsection titles stripped of (v0.X.Y+) annotations across authentication, chat, jobs, connectors, detection-inventory, plugins, and hooks sections.",
      "Body annotation 'Built-in (v0.5.21+)' inside hooks form description shortened to 'Built-in'.",
      "Knowledge base entry-count line no longer pins to a version range.",
      "Second sub-release of the comprehensive doc audit arc. Body annotations + duplicate password-change subsections cleaned in later sub-releases.",
    ],
  },
  {
    version: "0.17.41",
    date: "2026-05-25",
    title:
      "Architecture page (/help/architecture) rewritten to describe Phantom as it is today, not as it evolved — release annotations and change-history framing stripped.",
    highlights: [
      "Subsection titles no longer carry (v0.X.Y+) annotations. The middleware enforcement, permission policies, Setup widgets, Entry-point plugins, Log Destinations, and XSIAM dataset routing sections describe target state, not version history.",
      "Internal phase + round labels (Phase 5, R12 Phase 11, G-phase, P-phase) removed. Internal Issue tracker references and commit hash citations removed. Customer-facing docs no longer expose engineering project state.",
      "First sub-release of a multi-phase audit arc. v0.17.42 strips annotations from the user guide; v0.17.43 from journeys.ts. After cleanup, Phase 2-5 fill in missing component coverage and expand the REST API reference.",
    ],
  },
  {
    version: "0.17.39",
    date: "2026-05-25",
    title:
      "Login page polish — \"Phantom can …\" capabilities cycle + Phantom logo in the bottom orb row.",
    highlights: [
      "FlippingText cycle re-framed: was \"Powered by [Cortex XSIAM, MITRE ATT&CK, CALDERA, Vertex AI, Gemini, MCP]\"; now \"Phantom can [simulate logs, simulate attacks, create workers, send logs, validate detections, orchestrate workflows]\". Same 6-item count, same cyan typewriter animation, same cursor blink — only the prefix string + words array changed.",
      "Why the change: the brand-name cycle suggested Phantom was a thin shim over third-party products; the capability cycle tells the operator what Phantom actually does for them.",
      "ToolsStackCard bottom-of-page row: the middle (largest) orb's gold bolt glyph is replaced with the actual Phantom logo (/logo.svg, same asset as the sidebar). 4 outer orbs (smart_toy, memory, monitoring, api) keep their existing glyphs + colors.",
      "Sequential-bounce animation, sweeping cyan beam, sparkle effects, ring on the middle orb — all preserved exactly as before. v0.17.39 is a pure visual swap.",
    ],
  },
  {
    version: "0.17.38",
    date: "2026-05-25",
    title:
      "Edit flow for user-uploaded data sources + use-case filter dropdown (replaces the long chip strip).",
    highlights: [
      "Edit flow for user-uploaded data sources — Browse + Installed cards + Detail Drawer all surface an Edit button now. New PUT /api/v1/data-sources/user/{id} endpoint with the same accept_token discipline as upload; created_at preserved + updated_at refreshed on save.",
      "Upload dialog gains an edit mode: opens pre-filled with the existing YAML, runs the same preview → vendor-choice → save flow, submits via PUT instead of POST. The id field is locked — to rename, delete + re-upload.",
      "Installed-list + drawer schema responses now include `origin` so the UI doesn't have to cross-reference the catalog to know which sources are user-uploaded.",
      "Use-case filter dropdown: replaces the v0.17.34 long horizontal chip strip with a Material 3 styled multi-select dropdown. Click the trigger to open a floating panel with checkboxes; selected use cases also render as inline removable pills next to the trigger so the active filter set is visible at a glance.",
      "Dropdown supports search-within-panel (filter 44 use cases by typing), Select-all / Clear-all actions in the header, and a footer hint clarifying the OR semantics (Cisco tagged Firewall + EDR shows under either filter).",
    ],
  },
  {
    version: "0.17.37",
    date: "2026-05-25",
    title:
      "Backup + restore now include data sources — operator-uploaded YAMLs travel + installed packs re-install on the destination.",
    highlights: [
      "Backup zip gained a new `data_sources/` directory: `user/<id>.json` per operator upload + `installed.json` listing every installed pack as a 3-tuple.",
      "Restore reads both: two-phase preview/commit per user upload, then re-runs POST /api/v1/data-sources/install per installed pack.",
      "Bundle YAMLs are NOT exported — they re-arrive in the destination's image. Only the install set + user customizations need to travel.",
      "Restore order updated: personality → instances → skills → memory → knowledge → data_sources → jobs. Data sources before jobs because runtime jobs reference them via the simulate-vendor-logs skill.",
      "Dry-run reports sections_present.data_sources_user + data_sources_installed so operators can verify before committing.",
    ],
  },
  {
    version: "0.17.36",
    date: "2026-05-25",
    title:
      "Data sources inventory audit + comprehensive docs — architecture spec, user guide, new filter-by-use-case journey.",
    highlights: [
      "Audit: 342 packs across 137 vendors, 100% bucketed, 100% use_case-tagged. Only anomaly: MySQL's 2 packs are all rawlog-only (hidden by default).",
      "Architecture page #data-sources gained 5 new subsections: v0.17.x evolution diagram, use-case taxonomy (44 labels), logo pipeline + provenance schema, loader perf benchmark, internal data-flow picture.",
      "User guide gained 3 new subsections: Browse/filter/install workflow, Upload custom data source, Vendor logos + visual conventions.",
      "New journey filter-data-sources-by-use-case walks the click-path for narrowing the 137-vendor catalog via chip filter.",
      "v0.17.37 (upcoming) — backup includes user data sources + install state.",
      "v0.17.38 (upcoming) — user data source EDIT flow.",
    ],
  },
  {
    version: "0.17.35",
    date: "2026-05-25",
    title:
      "Installed cards now use the vendor-level logo (F5ASM/LTM/APM all share F5; Microsoft EntraID/Defender share Microsoft; …) and Tanium + Thinkst white-text logos recolored to navy.",
    highlights: [
      "Backend: catalog + installed-list + drawer endpoints all enrich rows with `vendor_logo_url` — the first sibling-per-vendor that has a logo. Same picker rule as v0.17.28's VendorCard.",
      "Frontend: InstalledCard + DetailDrawer header logo source = `row.vendor_logo_url ?? row.logo_url`. F5ASM card no longer shows per-pack white-text legacy SVG.",
      "Tanium: Wikipedia version had `fill=\"white\"` on the wordmark; recolored to #1A2238 navy. Brand red retained.",
      "Thinkst: same white-text fix.",
      "FortiGate complaint resolved by the vendor_logo_url switch — FortiGate now routes to the Fortinet vendor logo (simple-icons mark) instead of its per-pack legacy SVG.",
    ],
  },
  {
    version: "0.17.34",
    date: "2026-05-25",
    title:
      "Data sources use-case categorization: vendor cards now show product-type labels (F5→WAF/LoadBalancer, Okta→Identity/MFA, CyberArk→PAM, Avaya→Voice, Box→Storage, …) + a filter chip strip to narrow the catalog by use case.",
    highlights: [
      "New `use_cases:` field on every data_source.yaml — 137 vendors curated into 44 canonical labels.",
      "Vendor card badges sourced from use_cases instead of XSIAM platform categories. F5 shows WAF + LoadBalancer; Symantec shows AV + EDR + Email + DLP + CASB; etc.",
      "Filter chip strip above the catalog: click a label to narrow to vendors carrying it. Multiple chips = OR (any-match). Count per chip reflects current row matches.",
      "DetailDrawer use_case pill row (replacing the v0.17.33-hidden Supported Modules slot).",
      "Maintainer-only `scripts/curate_vendor_use_cases.py` is the single source of truth for the mapping. Idempotent — re-run after adding new vendors.",
      "Taxonomy enumerated in CANONICAL_USE_CASES: Network / Firewall / WAF / LoadBalancer / SDWAN / VPN / Proxy / DNS / IDS / DDoS / EDR / AV / Endpoint / Forensics / Identity / MFA / PAM / AD / CIAM / Email / DLP / CASB / Cloud / SaaS / Container / Virtualization / CSPM / Database / Storage / Collab / DevOps / WebServer / AppServer / SIEM / SOAR / XDR / ThreatIntel / Vuln / ASM / CTEM / OS / Honeypot / ICS / PhysSec / Voice / Analytics / Other.",
    ],
  },
  {
    version: "0.17.33",
    date: "2026-05-25",
    title:
      "Data sources drawer UX pass: dropped Tag column, hid Supported Modules, fixed dark-theme blue-on-blue contrast, restyled Install buttons to pill shape with solid fill.",
    highlights: [
      "Schema-Fields table: dropped the per-row vendor/meta Tag column — section headers already convey the grouping. Name 3→4, Description 5→6.",
      "Hid the Supported Modules row in the drawer (XSIAM was the only value for every YAML row — no operator-visible meaning).",
      "Column headers (Name / Type / Description): text-primary → text-on-surface for theme-aware readability.",
      "StatTile count values (Total Fields, Vendor Fields): text-primary → text-on-surface — blue-on-blue in dark mode fixed.",
      "Install buttons (both render sites): rounded-full pill shape with solid bg-primary + on-primary text — WCAG AAA contrast in both themes, M3-style filled CTA.",
      "Uninstall button: matching pill shape, low-opacity error tokens so destructive ≠ primary visually.",
      "v0.17.34 preview: replacing category badges with curated use-case tags (Avaya→Network, Box→Storage, F5→WAF/Load Balancer, Okta→Identity/MFA, …) + filter strip.",
    ],
  },
  {
    version: "0.17.32",
    date: "2026-05-25",
    title:
      "Filled the last 3 vendor-logo gaps — Clearswift, SecureAuth, Semperis. 136 of 136 vendor cards now have logos (100% coverage).",
    highlights: [
      "Clearswift: pulled the official PNG from Wikipedia (Clearswift - A HelpSystems logo).",
      "SecureAuth: fetched their own site SVG and recolored white→navy (#1A2238) so it's visible on the near-white card panel.",
      "Semperis: hand-crafted a clean SVG wordmark in their brand navy (#0F1934) — their site uses an empty inline data-URI for the logo so nothing was fetchable; per operator direction \"if you can't find SVG, create one.\"",
      "Each YAML's logo: block records fidelity: branded / branded-recolored / monochrome-brand / approximation so future maintainers can upgrade lower-fidelity entries when official artwork becomes available.",
      "Standalone library at docs/assets/vendor-logos/ regenerated automatically: 137 files (was 134).",
    ],
  },
  {
    version: "0.17.31",
    date: "2026-05-25",
    title:
      "Sourced 10 more vendor logos from Wikipedia + vendor sites — Arista, Avaya, Brocade, Ivanti, Kiteworks, RSA, Squid, Tigera. 135 of 136 vendor cards now have logos.",
    highlights: [
      "Vendor card logo coverage: 125 → 135 (now 99%).",
      "Still missing (3 vendors): Clearswift, SecureAuth, Semperis. None have public SVG sources; require manual hand-curation from each vendor's brand page.",
      "Wikipedia Commons via MediaWiki API for: Arista, Avaya, Brocade, Ivanti, Kiteworks, Squid (PNG — no SVG exists).",
      "VectorLogoZone for RSA, vendor brand page for Tigera.",
      "Per-URL dedup + 429-retry-with-backoff for polite scraping.",
    ],
  },
  {
    version: "0.17.30",
    date: "2026-05-25",
    title:
      "Data sources page slowness fixed: catalog + logo requests went from 3,400ms each to <1ms via per-root mtime-based scan cache.",
    highlights: [
      "Root cause: DataSourcesYamlLoader re-walked + re-parsed all 342 bundled YAMLs on EVERY request. With v0.17.28's inline-embedded base64 logos, those YAMLs grew large enough that the cumulative parse cost was 1-3s per call.",
      "Fix: per-root scan cache keyed by directory st_mtime_ns. Modifying an existing YAML's contents doesn't bump the parent's mtime (always cache-hit), and add/remove DOES bump mtime (automatic invalidation).",
      "get_by_id() now uses an O(1) dict index rather than a linear scan over list_all().",
      "write_user() + delete_user() explicitly call invalidate() after writes for 1s-quantization safety.",
      "Benchmark: list_all() second call went from 1,076ms to 0.0ms. 125-vendor-card backend cost went from ~135s to <10ms.",
      "First /data-sources load: ~3s. Every subsequent load: instant.",
    ],
  },
  {
    version: "0.17.29",
    date: "2026-05-25",
    title:
      "Sourced 40 missing vendor logos from simple-icons — Apache, Apple, AWS, Cisco-ASR/ISR/Nexus/WLC, Citrix, Dell, F5APM/BigIPAWAF, FortiManager, HashiCorp, Huawei, IBM, Juniper, Kubernetes, Microsoft (IIS/NPS/WSUS), MySQL, NGINX, OktaOAG, Tableau, TrendMicro, VMware, ManageEngine, …",
    highlights: [
      "40 data_source.yaml files got inline base64 SVGs from simple-icons (CC0-1.0).",
      "~12 vendor cards that previously showed the placeholder icon now show their brand logo.",
      "Pack-name → simple-icons slug mapping is hand-curated in scripts/source_missing_vendor_svgs.py for explicit control.",
      "13 packs across ~10 vendors (Arista, Avaya, Barracuda, BeyondTrust, Brocade, HPE, Kiteworks, RSA, Squid, TigeraCalico) aren't on simple-icons and still show placeholder — hand-curated SVGs needed.",
      "Provenance recorded per logo as `source: simpleicons:<slug>` in the YAML.",
    ],
  },
  {
    version: "0.17.28",
    date: "2026-05-25",
    title:
      "Data sources logo pipeline: 21 packs gained inline logos, vendor cards now pick the row with a working logo, catalog stops requesting guaranteed-404 URLs (faster first load).",
    highlights: [
      "F5 / Barracuda / BeyondTrust / Linux vendor cards now show their logos (were placeholder because the first row in the group had no baked SVG).",
      "21 individual data-source cards (BeyondTrust_Password_Safe, F5LTM, FortiManager, CiscoSMA, McAfee*, MicrosoftECM, Symantec*, Infoblox, IronPort, …) start showing their baked logos.",
      "First-page-load is faster: 22 fewer round-trips for guaranteed-404 logo fetches on vendor cards that have no baked SVG.",
      "VendorCard logo selector: rows.find(r => r.logo_url) ?? rows[0]. Card uses whichever pack in the vendor group has a working logo.",
      "Catalog returns logo_url: null when YAML has no inline logo — UI renders the inventory_2 placeholder directly without a request.",
      "21 packs got inline base64 SVG/PNG embedded into their data_source.yaml from the baked tree (one-shot maintainer script per scripts/CLAUDE.md framing). 22 vendors still need external SVG sourcing (Apache, Apple, NGINX, Kubernetes, etc.) — separate research task.",
      "Closes #93.",
    ],
  },
  {
    version: "0.17.27",
    date: "2026-05-25",
    title:
      "Data sources UI fix pass: F5 family groups under F5 card, 67 wrongly-hidden packs visible again, white-on-white logo regression fixed, empty panels show placeholder icon.",
    highlights: [
      "F5LTM, F5APM, F5BigIPAWAF now group under the F5 vendor card (75 packs across 22 vendor families rebucketed to their canonical vendor name).",
      "67 packs with structured fields (Cisco ASR/ISR/SMA/Nexus, Apache, Microsoft NPS/WSUS, Barracuda, BeyondTrust, etc.) become visible in default Browse view — wrong is_rawlog_only flag fixed.",
      "BrowsePackCard logo banner now uses the same constant near-white background as VendorCard / InstalledCard / DetailDrawer (v0.11.1 fix that had been missed for this one component).",
      "Empty-panel-on-404 fix: when a logo URL 404s, the panel renders the placeholder inventory_2 icon instead of an empty box (touches all 4 logo render sites).",
      "Bundle YAMLs can now ship self-contained inline base64 SVGs — new /api/v1/data-sources/inline-logo/<id> route serves them without rebuilding the baked vendor SVG tree.",
      "Closes #92.",
    ],
  },
  {
    version: "0.17.26",
    date: "2026-05-25",
    title:
      "xlog: fixed OverrideSender wire format. CEF/SYSLOG/LEEF workers now emit broker-parseable strings instead of JSON — your XSIAM broker will start routing to <vendor>_<product>_raw datasets again.",
    highlights: [
      "Root-cause bug found during deep E2E smoke: OverrideSender always JSON-encoded the wire payload, regardless of the worker's data_type.",
      "XSIAM brokers parse the CEF/LEEF header on incoming syslog to pick the destination dataset. JSON has no header → broker dropped the data.",
      "New format branching: CEF → syslog-wrapped CEF:0|Vendor|Product|… ; SYSLOG → vendor-product: key=value ; LEEF → LEEF:2.0|Vendor|Product|… ; else → JSON (preserves v0.12.0 behavior).",
      "ArcSight CEF spec compliance: header escapes `\\` and `|`; extension escapes `\\`, `=`, `\\n`. Lists/dicts JSON-stringified inside extension.",
      "22 new pytest cases cover CEF/SYSLOG/LEEF/JSON branches + escaping + record-level SignatureID/Name/Severity hoisting + edge cases. Full xlog suite: 50/50 green.",
      "Closes #91.",
    ],
  },
  {
    version: "0.17.25",
    date: "2026-05-24",
    title:
      "Data sources: refreshed from upstream demisto/content. +82 new packs, +3803 fields, 260 → 342 data sources. Major gap closure for operator-flagged missing products.",
    highlights: [
      "F5 family complete: added F5APM, F5LTM, F5BigIPAWAF (operator stated complaint that F5ASM was the only F5 product).",
      "Cisco family expanded: ASR, ISR, Nexus, SMA, Wireless LAN Controller, cisco-ise (115 fields), cisco-meraki (83 fields).",
      "Web/server stack: Apache (Tomcat, HTTPD), NGINX, IIS, Squid all baked.",
      "Network gear: Arista, Brocade, HPE switches, Juniper SRX, FortiManager, BeyondTrust family.",
      "Cloud/ops: AWS ELB, Kubernetes, MacOS, MicrosoftNPS/WSUS, Tanium, Tableau, MySQL Enterprise, Auditd.",
      "Full pipeline re-run: cortex schema extraction + XDM mapping derivation + .xif alter-intermediate extraction. 100% description coverage maintained across all 342 sources.",
      "82 new packs have logo:null pending vendor SVG sourcing (v0.17.26 candidate).",
    ],
  },
  {
    version: "0.17.24",
    date: "2026-05-24",
    title:
      "Field descriptions Phase 4k: extracted .xif alter intermediates for rawlog packs — +1117 fields. Cisco Catalyst, VMwareVCenter (+184!), FireEyeHX audit, Linux events, MicrosoftIIS — all the syslog-text packs now have rich vendor-faithful field inventories instead of just 2 fields.",
    highlights: [
      "Operator spotted: Cisco Catalyst showed only 2 fields in the drawer despite the vendor emitting dozens.",
      "Root cause: v0.17.9 only caught `xdm.X = <bare raw>` mappings; missed intermediates created via regextract+coalesce in alter clauses.",
      "Fix: new scripts/extract_xif_alter_intermediates.py parses alter blocks, captures vendor field names, derives descriptions from xdm mappings, infers types.",
      "31 packs touched, 1117 fields added. VMwareVCenter +184, VMwareESXi +107, FireEyeHX audit +106, LinuxEventsCollection +78, HuaweiFW +70.",
      "Surfaced separately: 49+ entirely-missing packs upstream (F5APM/F5LTM/F5BigIPAWAF, Cisco ASR/ISR/Nexus/SMA/UCM, Citrix/CitrixADC, BeyondTrust, Juniper SRX, etc.) — v0.17.25 candidate.",
    ],
  },
  {
    version: "0.17.23",
    date: "2026-05-24",
    title:
      "Hot-fix: get_with_schema SELECT was missing the `description` column. v0.17.22 fixed the install path but the SELECT instrumentation gap meant installed packs still returned empty descriptions in the schema endpoint.",
    highlights: [
      "Root cause: v0.17.7 added the column to migration + INSERT + dataclass + to_dict but missed the SELECT. The defensive `'description' in r.keys()` check silently masked it.",
      "Fix: one-line SELECT update. Installed F5ASM rows now serve descriptions correctly from the schema endpoint.",
    ],
  },
  {
    version: "0.17.22",
    date: "2026-05-24",
    title:
      "Hot-fix: F5 ASM install 500 (duplicate date_time field) + sister bug — install was silently dropping ALL field descriptions when going through the bundled-YAML path. Found by operator hands-on smoke.",
    highlights: [
      "Bug 1: F5ASM YAML had `date_time` listed twice (v0.16.x curation error). Install hit SQLite UNIQUE constraint on (data_source_id, field_name) → 500.",
      "Bug 2: _compose_from_user_yaml built DataSourceField without `description` — every install post-v0.17.11 had empty descriptions in the DB. Drawer preview hid the bug via the YAML overlay.",
      "Fix: dedup by field name in _compose_from_user_yaml + pass description through. Removed duplicate from F5ASM YAML. New validator check check_bundled_data_sources_no_duplicate_fields() prevents future drift.",
      "Bug-family audit: only F5ASM had the duplicate. Other 259 YAMLs clean.",
    ],
  },
  {
    version: "0.17.21",
    date: "2026-05-24",
    title:
      "🎯 100% field-description coverage achieved. All 5078 fields across 260 data sources now have descriptions. Phase 4j closes the v0.17.7 → v0.17.21 arc.",
    highlights: [
      "Final 143 fields filled across 74 YAMLs (68 packs). Every long-tail vendor specialty field now documented.",
      "Full arc: 21% baseline → 100% in 15 releases over one day. 4022 new descriptions added on top of v0.16.x's 1056.",
      "Operator-visible: every vendor card's schema preview drawer now shows descriptions for every field. No em-dashes remaining.",
      "8 maintainer-only scripts re-runnable on cortex-content refreshes. Workflow proven end-to-end.",
    ],
  },
  {
    version: "0.17.20",
    date: "2026-05-24",
    title:
      "Field descriptions Phase 4i: long-tail sweep across 41 vendor packs. 372 fields filled in a single release — coverage 89.9% → 97.2%.",
    highlights: [
      "41 pack-level dictionaries: BitSight, CyberArk PAS+EPM, NVIDIA DOCA Argus, Cohesity, Dropbox, GitHub, GitLab, ManageEngine, Microsoft ADFS+EntraID+GraphSecurity, Code42, KnowBe4, KeeperSecurity, BoxÄ Armis, AlibabaActionTrail, etc.",
      "Coverage 97.2% (4935 of 5078 fields). Only 143 remain.",
      "Residual is long-tail specialty fields in tiny packs (1-4 each), Phase 4j cleanup is small.",
    ],
  },
  {
    version: "0.17.19",
    date: "2026-05-24",
    title:
      "Field descriptions arc CLOSES at 89.9% coverage (started today at 21%). Phase 4h ships Duo + Jamf + Atlassian + ExtraHop + Okta + OneLogin — 104 fields filled across 17 packs.",
    highlights: [
      "Coverage 87.8% → 89.9%. Arc target met (started at 21% baseline this morning).",
      "DuoAdminApi 19 — auth factor / eventtype / result / integration / access_device.",
      "ExtraHop 17 complete — Reveal(x) detection schema with MITRE tactics/techniques.",
      "JamfProtect 17 complete — Apple device telemetry + scorecard + insightsStats.",
      "OneLogin 15 complete — system event types + risk_score + otp_device_*.",
      "Okta 12 — system log schema (eventType, target, displayMessage, debugContext).",
      "Jira + Confluence Cloud 18 — Atlassian audit logs.",
      "Final arc stats: 4563 of 5078 fields now have descriptions (89.9%). 515 remaining are long-tail vendor specialty fields, deferred for marginal-ROI follow-ups.",
    ],
  },
  {
    version: "0.17.18",
    date: "2026-05-24",
    title:
      "Field descriptions Phase 4g: 7 highest-impact packs (AzureWAF + AzureAppService + AzureKubernetes + Exchange + Abnormal + McAfee ePO + MongoDB Atlas). 157 fields filled. Coverage 84.7% → 87.8%.",
    highlights: [
      "AzureWAF 43 — Front Door/AppGW WAF schema (requesturi/sslcipher/ruleGroup/wafmode/ruleset variants).",
      "AbnormalSecurity 25 — complete. Email taxonomy: attackVector/attackType/attackedParty/autoRemediated.",
      "AzureAppService 24 — complete. Logic App workflows + AV scan + audit.",
      "AzureKubernetesServices 15 — complete. K8s audit log: AuditId/Stage/Verb/ObjectRef.",
      "MicrosoftExchangeServer 16 — complete. Message tracking schema.",
      "MongoDB Atlas 15 — complete. McAfee ePO 19 — ThreatEventID/Severity/Name/Category.",
      "Microsoft umbrella 234 → 50 (most specialty Azure packs now covered).",
    ],
  },
  {
    version: "0.17.17",
    date: "2026-05-24",
    title:
      "Field descriptions Phase 4f: Cloudflare + Workday + Oracle + Palo Alto Networks (4 vendors bundled, all complete). 122 fields filled. Coverage 82.3% → 84.7%.",
    highlights: [
      "Cloudflare 33 — WAF Logpush HTTP request fields + Zero Trust audit. Complete.",
      "Workday 33 — Sign-on tracking schema with MFA + auth flow + device metadata. Complete.",
      "Oracle 30 — Identity Audit Framework (IAU_*) + Database Unified Auditing + OCI. Complete.",
      "Palo Alto Networks 26 — Prisma Cloud Compute (Defender) + Prisma Cloud CSPM + SaaS Security. Complete.",
      "Coverage approaching 85%. Phase 4g final stretch: Microsoft 148 (specialty), Abnormal Security 25, CyberArk residual 24, McAfee 24.",
    ],
  },
  {
    version: "0.17.16",
    date: "2026-05-24",
    title:
      "Field descriptions Phase 4e: Trend Micro + Claroty + FireEye + Mimecast (4 vendors bundled). 122 fields filled. Coverage 79.9% → 82.3%.",
    highlights: [
      "Claroty 38 — extended CEF custom-string range (cs7-cs22 + their labels, beyond the cs1-cs6 spec). Complete coverage.",
      "Mimecast 34 — Email Security Gateway: Sender/Recipient/MsgId/Subject/Virus + attachment metadata (md5/sha256/fileMime/fileExt) + audit fields. Complete coverage.",
      "Trend Micro 38 — Vision One (mitreMapping/impactScope/indicators/malName/score), Deep Security (TrendMicroDs*), Email Security (deliveryTime/embeddedUrls/policyAction). Near-complete (1 field remaining).",
      "FireEye 12 — HX-pack-specific (event_values, condition, categoryTupleDescription, cs7-cs10).",
      "Phase 4f remaining vendor gaps: Microsoft 148 (specialty), Cloudflare 33, Workday 33, Oracle 30, PAN 26.",
    ],
  },
  {
    version: "0.17.15",
    date: "2026-05-24",
    title:
      "UI: widen data-source drawer to 55% of viewport to match the skill drawer. The previous 480px cap left no room for the new Description column from v0.17.7.",
    highlights: [
      "Click any data source card → drawer now opens at 55% width (~1056px on 1920px viewport) instead of the old 480px cap.",
      "Schema preview table (NAME / TYPE / DESCRIPTION / TAG) no longer compresses; long descriptions like 'Source IPv4 address' fit on one line.",
      "Matches the skill drawer's existing w-[55%] pattern for consistency.",
    ],
  },
  {
    version: "0.17.14",
    date: "2026-05-24",
    title:
      "Field descriptions Phase 4d: Salesforce + Netskope + ServiceNow vendor dictionaries (3 vendors bundled). 162 fields filled. Coverage 76.7% → 79.9%.",
    highlights: [
      "Salesforce 71 — Real-Time Event Monitoring (EventLogFile) including underscore-prefixed raw fields (_METHOD_, _CLIENT_IP_, _RUN_TIME_, _USER_AGENT_, etc.) and standard audit fields.",
      "Netskope 51 — CASB + Network audit log schema (action, srcip, dstip, ccl, risk_level, traffic_type, etc.).",
      "ServiceNow 40 — Transaction log + ITSM table fields (state/impact/urgency/approval/priority/sys_mod_count/etc.).",
      "All three vendors are now FULLY covered. Phase 4e targets Trend Micro (39), Claroty (38), FireEye (41), Mimecast/Workday/Cloudflare/Oracle (~33 each).",
    ],
  },
  {
    version: "0.17.13",
    date: "2026-05-24",
    title:
      "Field descriptions Phase 4c: CyberArk vendor dictionary fills 77 fields (101 → 24). CyberArk Identity, PAS, EPV, EPM, PTA all covered. Coverage 75.2% → 76.7%.",
    highlights: [
      "scripts/apply_cyberark_descriptions.py — ~110 entries citing CyberArk's Identity / PAS / EPV / EPM / PTA schemas.",
      "Identity audit fields: UserName, TargetUser, EntityType, DirectoryServiceUuid, ProxyId, SyncResult etc.",
      "PAS audit fields: timestamp, applicationCode, auditCode, auditType, component, accessMethod etc.",
      "Remaining 24 CyberArk fields are EPM custom event payloads + PAS extension fields — Phase 4d.",
    ],
  },
  {
    version: "0.17.12",
    date: "2026-05-24",
    title:
      "Field descriptions Phase 4b: Microsoft vendor dictionary fills 86 fields (234 → 148). Office 365 audit, Azure activity, Entra ID sign-in, Graph API mail, AKS audit, Defender, WAF — all covered. Coverage 73.5% → 75.2%.",
    highlights: [
      "scripts/apply_microsoft_descriptions.py — ~190 curated entries citing Microsoft Learn schemas.",
      "Microsoft 365 audit common fields (Operation, UserId, Workload, ResultStatus, RecordType, UserType enum) now described across all O365-derived packs.",
      "Azure activity log common fields (subscriptionId, resourceGroupName, operationName, correlationId, level).",
      "Graph API mail fields (isDraft, sentDateTime, hasAttachments, receivedDateTime, from, attachments).",
      "Remaining Microsoft gap is 148 fields (custom AzureWAF/AppService telemetry, AppSentinelsAi extensions) — Phase 4c+.",
    ],
  },
  {
    version: "0.17.11",
    date: "2026-05-24",
    title:
      "Field descriptions Phase 4a: applied 112-entry CEF-standard dictionary, filling 283 more descriptions across 43 YAMLs. Coverage 67.9% → 73.5%. Operator's original cs1/cs2/src/dst questions are now described uniformly across every CEF-emitting vendor.",
    highlights: [
      "scripts/apply_cef_standard_descriptions.py — bakes the ArcSight CEF custom-string/number/header field set per the official spec.",
      "Coverage 73.5% (3733/5078 fields). Phase 4b targets the 1345 vendor-specific gaps (Microsoft 234, CyberArk 101, Salesforce 71, Netskope 51, ServiceNow 40).",
      "src/dst now described across 21 packs each; cs1-cs5 across many vendors; cefDeviceVendor/Product across 15 packs.",
    ],
  },
  {
    version: "0.17.10",
    date: "2026-05-24",
    title:
      "Hot-fix: YAML description overlay was calling loader.get(constructed_id) instead of loader.get_by_3tuple(pack, rule, dataset). v0.17.9 wrote 2394 descriptions into YAMLs correctly but the preview drawer didn't surface them. After this fix, AWS-SecurityHub Id/Title/Description fields show their XDM-derived descriptions in the schema drawer.",
    highlights: [
      "Operator-visible: schema preview drawer now surfaces the 2394 descriptions Phase 3 wrote.",
      "Root cause: v0.17.7's _yaml_field_descriptions() overlay used the wrong loader method.",
      "Phase 4 vendor-doc backfill (originally planned as v0.17.10) renumbers to v0.17.11.",
    ],
  },
  {
    version: "0.17.9",
    date: "2026-05-24",
    title:
      "Field descriptions Phase 3: backfilled 2394 descriptions from XDM mappings — coverage jumped from 21% to 72.1%. AWS-SecurityHub Id/Title/Description fields now show 'Alert original alert ID' / 'Alert name' / 'Alert description' in the schema drawer. Agent now knows what cs1 / spt / dpt / FTNTFGTviruscat etc. MEAN when generating logs.",
    highlights: [
      "scripts/parse_xdm_into_descriptions.py walks 232 .xif files, extracts 4857 raw_field → xdm_canonical mappings across 366 unique XDM names.",
      "Descriptions derived algorithmically: xdm.source.ipv4 → 'Source IPv4', xdm.target.host.fqdn → 'Destination host FQDN' (with abbreviation table for FQDN/IPv4/URL/HTTP/etc.).",
      "188 of 260 YAMLs modified; 2394 new descriptions written.",
      "Preserves the 862 v0.16.x curated descriptions (those are richer than algorithmic — e.g. 'F5 device hostname' for unit_hostname vs generic 'Observer hostname').",
      "1259 fields remain without descriptions (vendor extensions like Office365 UserType, raw CEF custom fields like Checkpoint cs1-cs5, opaque payloads like GoogleCloudLogging textPayload) — Phase 4 (v0.17.10) handles via vendor doc research.",
    ],
  },
  {
    version: "0.17.8",
    date: "2026-05-24",
    title:
      "Field descriptions Phase 2: fetched 232 demisto/content modeling rules (.xif files) carrying canonical xdm.X = raw_field mappings. Phase 3 (v0.17.9) will parse these into the description backfill.",
    highlights: [
      "scripts/fetch_demisto_modeling_rules.py — one-time + re-runnable fetcher; 232/232 fetched, 0 errors via raw.githubusercontent.com CDN.",
      "Stored at scripts/maintainer/modeling_rules/ (2.5MB, maintainer-only, kept OUTSIDE bundles/spark/ so the agent Dockerfile doesn't bake them into customer images).",
      "397 unique xdm.* canonical names spotted across all 232 rules — that's the description-dictionary size for Phase 3.",
      "Sample mappings confirmed: F5ASM cs1=xdm.network.rule (the operator's original bug report), spt=xdm.source.port, dpt=xdm.target.port.",
      "No runtime change in this release; pure maintainer-side data acquisition.",
    ],
  },
  {
    version: "0.17.7",
    date: "2026-05-24",
    title:
      "Field descriptions: schema + UI foundation (Phase 1 of 4). New Description column in the data source drawer; descriptions flow from bundled YAML through cortex extraction overlay. 1056/5078 fields have descriptions today (v0.16.x curation); 4022 will backfill via v0.17.8 → v0.17.10 (demisto/content XDM mappings + vendor docs).",
    highlights: [
      "Drawer adds a Description column (NAME · TYPE · DESCRIPTION · TAG). Empty fields show em-dash until backfill lands.",
      "Field filter now matches name OR description — search 'Source IP' to find src/srcip/source_ip across vendors.",
      "Backend wires description through DataSourceField, SQLite (PRAGMA-guarded migration), insert, row→dataclass, and to_dict.",
      "_yaml_field_descriptions() helper overlays bundled YAML descriptions onto cortex-extracted preview fields — 32 v0.16.x-curated packs already show their descriptions in the uninstalled preview.",
      "Phases 2-4 (v0.17.8 → v0.17.10): fetch demisto/content modeling rules, parse XDM mappings to derive descriptions like 'Source IPv4 address' / 'User session id', fall back to vendor docs for fields without an XDM mapping.",
    ],
  },
  {
    version: "0.17.6",
    date: "2026-05-24",
    title:
      "Data sources: auto-extracted cortex-content fields into the 227 packs v0.16.x didn't manually curate. Browse catalog and drawer field counts now agree across all 259 vendors. Total fields added: 4022.",
    highlights: [
      "Bug operator surfaced: Browse cards showed '0 fields' for ~228 packs (AWS-SecurityHub, MS Sentinel, Cisco, etc.) but the drawer showed real fields — catalog read YAML, drawer read cortex-content schema.json directly.",
      "Fix: scripts/extract_cortex_fields_into_yamls.py walks every YAML with fields:[], reads the matching <rule>_schema.json, maps cortex types → data_source.schema.json types, writes fields back.",
      "227 data_source.yaml files updated, 4022 fields added, avg 17.7 fields per vendor, max 94 (TrendMicroVisionOne).",
      "32 v0.16.x manually-curated vendors stay richer (have product-doc-sourced types like ipv4/port/mac_address) — extraction respects existing fields[] and only touches empty entries.",
      "259/260 data sources now have fields populated; 1 cortex-side schema is genuinely all-meta.",
    ],
  },
  {
    version: "0.17.5",
    date: "2026-05-24",
    title:
      "Docs: bake XSIAM dataset-routing conventions into handler docstrings + spec yamls + help docs + xlog agent prompt. xsiam_http always → phantom_logs_raw; syslog+CEF+broker → <vendor>_<product>_raw. Verified live during operator hands-on smoke; baked in so the agent no longer guesses dataset names when verifying ingestion.",
    highlights: [
      "xsiam_http handler + spec.yaml: documents phantom_logs_raw as the always-landing dataset + canonical XQL verify template.",
      "syslog handler + spec.yaml: documents <vendor>_<product>_raw broker-CEF convention; points at phantom_create_data_worker(type=CEF, vendor=..., product=...) as the production path.",
      "xlog connector's phantom_create_data_worker docstring: teaches the agent the dataset-routing table + ready-to-run XQL verify templates so 'verify the records arrived' becomes one tool call, not a guessing game.",
      "/help/architecture#log-destinations: new XSIAM dataset routing subsection with the full table.",
      "/help/user#log-destinations-ux: new 'Where do my records land in XSIAM?' subsection covering 4 scenarios (HTTP Collector / syslog+CEF+broker / vendor-faithful simulation / non-XSIAM syslog targets).",
    ],
  },
  {
    version: "0.17.4",
    date: "2026-05-24",
    title:
      "Hot-fix: xsiam_http schema. Drops the auth_id field (XSIAM HTTP Collector doesn't take it; was a PAPI envelope leftover that XSIAM rejected). Clarifies source/vendor/product as optional XSIAM tag headers with descriptions. Operator-found during real-world hands-on smoke after the v0.17.3 release.",
    highlights: [
      "Removed auth_id field from the xsiam_http manifest — only URL + auth_key are required now.",
      "Handler no longer emits the x-xdr-auth-id header (which XSIAM was rejecting on Collector endpoints).",
      "source/vendor/product fields kept (optional) and given clear descriptions explaining they're XSIAM tag headers.",
      "Already-saved destinations are SAFE — leftover auth_id sits in config_json but is silently ignored.",
      "Re-editing an existing row shows the new 4-field set; saving fresh cleans up the stale field.",
    ],
  },
  {
    version: "0.17.3",
    date: "2026-05-24",
    title:
      "R6 arc closure — log destinations end-to-end on phantom-vm. 10-section e2e battery (scripts/e2e_v0173_log_destinations.py) PASSES 34/34 against the deployed install: CRUD + UDP probe + secret round-trip + visible_when discriminator + cascade cleanup. New /help/architecture#log-destinations + /help/user#log-destinations-ux + configure-log-destination journey ship the docs.",
    highlights: [
      "scripts/e2e_v0173_log_destinations.py — 10-section e2e battery validating the whole v0.17.x stack.",
      "Result on deploy: 34/34 PASS (catalog, syslog UDP probe with real datagram receipt, webhook+bearer secret roundtrip, xsiam_http+splunk_hec creatable, '***' sentinel preserves, set-default scoped per type, cascade cleanup, visible_when round-trip).",
      "/help/architecture#log-destinations — new spec section with storage schema, handler interface, credential boundary, WEBHOOK_ENDPOINT migration, files-of-record.",
      "/help/user#log-destinations-ux — operator user guide: adding/testing/defaults/agent integration/migration/credential boundary.",
      "journeys.ts: new 'configure-log-destination' starter journey (~2 min).",
      "v0.17.x arc CLOSED. Deferred to v0.18.0: destination_id field on CreateDataWorkerRequest + xlog-side webhook/splunk_hec forwarding (needs connector→MCP callback infra).",
    ],
  },
  {
    version: "0.17.2",
    date: "2026-05-24",
    title:
      "xlog bridge: WEBHOOK_ENDPOINT migration + agent destination workflow (R6 sub-3). Operators upgrading from v0.16.x → v0.17.x get the legacy WEBHOOK_ENDPOINT / WEBHOOK_KEY env vars auto-migrated into an 'XSIAM Default' destination on first boot. The phantom_create_data_worker docstring teaches the agent the 3-step destination-lookup workflow.",
    highlights: [
      "First-boot migration: WEBHOOK_ENDPOINT + WEBHOOK_KEY env vars → 'XSIAM Default' destination, marked is_default=true.",
      "Idempotent — second boot is a no-op; existing xsiam_http destinations preserved.",
      "phantom_create_data_worker docstring rewritten: agent now calls log_destinations_get(name), formats per type (syslog → udp:host:port; xsiam_http → XSIAM_WEBHOOK), then passes the string to xlog.",
      "Legacy destination string field preserved for backwards compat.",
      "+3 migration tests (498 pytest pass total).",
      "Full destination_id Pydantic-field rewrite deferred to v0.18.0 (needs connector→MCP callback infrastructure).",
    ],
  },
  {
    version: "0.17.1",
    date: "2026-05-24",
    title:
      "Log destinations UI page + FormEngine extraction (R6 sub-2). Lands /log-destinations under Integration with full CRUD UI driven by the v0.17.0 backend. New FormEngine component renders any ConfigParam-style fields[] schema with conditional visible_when support (webhook auth-type discriminator works end-to-end).",
    highlights: [
      "/log-destinations page: search + type filter, destinations grouped by type, Test/Edit/Set-Default/Delete per row, two-click delete confirmation.",
      "FormEngine component (mcp/agent/components/form-engine.tsx) extracted as reusable dynamic-form renderer with visible_when discriminator support.",
      "Webhook auth_type dropdown drives field visibility live — pick bearer → only bearer_token shows; pick basic → username+password appear.",
      "Syslog protocol=tls discriminator reveals 3 TLS cert fields conditionally.",
      "Probe button fires real test message + persists outcome + green/red banner inline.",
      "Empty state with CTA; sidebar entry added under Integration → Plugins.",
    ],
  },
  {
    version: "0.17.0",
    date: "2026-05-24",
    title:
      "Log destinations backend foundation (R6 arc opens). Schema-driven yaml manifest pattern: each destination type ships as bundles/spark/destinations/<id>/spec.yaml + handler.py. v1 ships 4 types: syslog (UDP/TCP/TLS), generic HTTP webhook (4 auth modes), XSIAM HTTP Collector, Splunk HEC. Backend-only — UI page lands in v0.17.1.",
    highlights: [
      "New /api/v1/destination-types catalog endpoint exposing the 4 type manifests with full field schemas.",
      "New /api/v1/log-destinations CRUD + /probe + /set-default REST surface; one-default-per-type invariant enforced.",
      "Per-type handler modules implement probe() + send() — registered at MCP boot; missing handler fails boot loudly.",
      "Agent MCP tools log_destinations_list + log_destinations_get registered (READ-ONLY, secrets redacted); write+probe REST-only per credential guardrail.",
      "Secret slots persisted to SecretStore at /agents/phantom/log_destinations/<id>/<slot>; cascade-deleted on row delete; '***' sentinel preserves on PATCH.",
      "+25 new unit tests (492 total pytest pass). UI page lands in v0.17.1, xlog bridge in v0.17.2, E2E battery in v0.17.3.",
    ],
  },
  {
    version: "0.16.2",
    date: "2026-05-23",
    title:
      "v0.16.x arc complete — 32 vendors / 1056 fields. Adds Cisco Umbrella DNS (26 fields) and fixes the v0.16.1 E2E battery to look up schema fields under the correct response key (data_source.fields, not top-level fields). v0.16.1 backend was correct all along — the test had a script-shape bug that reported it as broken.",
    highlights: [
      "Cisco Umbrella Cloud DNS — 26 fields covering domain, categories, action, applications, threats, devices, users.",
      "scripts/e2e_v0161_multi_instance_and_fields.py — schema lookup nested under data_source key. 23/23 PASS on phantom-vm.",
      "v0.16.x arc total: 32 datasets / 1056 fields across IAM, Cloud, Firewall, EDR, SaaS, Web proxy, Email, NDR, DNS categories.",
      "Install path verified working — Okta v2.0 round-trip (catalog → install → schema endpoint) preserves all 34 curated fields.",
      "Multi-instance disabled_tools independence verified — xsiam + cortex-xdr instances carry independent lists with no bleed-over.",
    ],
  },
  {
    version: "0.16.1",
    date: "2026-05-23",
    title:
      "Field coverage extension + install-path fix + E2E battery. 8 more vendors (Sysmon, Windows Events, F5 ASM, Imperva, Akamai, MS Exchange Online/Server, Vectra AI) brings total to 31 datasets / 1030 fields. Install path now respects bundled YAML fields (the v0.16.0 catalog numbers now survive post-install). New scripts/e2e_v0161 battery validates both.",
    highlights: [
      "31 enterprise vendors covered total — adds Sysmon (39), Windows Security Events (38), F5 ASM (27), Imperva (28), Akamai (31), MS Exchange (30), Vectra AI (26).",
      "Install path fix — POST /api/v1/data-sources/install now prefers bundled YAML over cortex-content extraction when fields[] is populated.",
      "Post-install schema endpoint returns the same field set the YAML declares (was 0 pre-v0.16.1).",
      "scripts/e2e_v0161_multi_instance_and_fields.py — E2E battery validating catalog + schema + multi-instance toggle in one run.",
      "1030 total fields across both releases (781 + 249).",
    ],
  },
  {
    version: "0.16.0",
    date: "2026-05-23",
    title:
      "Data source field coverage extension — top 23 vendors get curated fields[] in their bundled data_source.yaml. Pre-fix every bundled source had fields: [] (catalog rendered 0 fields per vendor); now 23 enterprise flagships have meaningful schemas. 781 fields added across IAM, Cloud, Firewall, EDR, SaaS, Web-proxy, Email categories.",
    highlights: [
      "Okta SystemLog (34 fields), Microsoft Entra ID (42 fields), AWS CloudTrail (34), AWS GuardDuty (29), AWS WAF (28).",
      "FortiGate / FortiMail (49 each), Cisco ASA (24), Microsoft 365 Defender (38), Carbon Black Cloud (32), SentinelOne (31).",
      "GitHub Audit (23), Salesforce (28), Slack Audit (23), Zscaler ZPA / NSS Web (44 / 36), Proofpoint TAP (24).",
      "Field names sourced from each vendor's published log-event documentation — match the product's real records.",
      "Codegen helper at scripts/extend_data_source_fields.py — idempotent rerun, _yaml_scalar() quoting prevents date/int/@-leading-name corruption.",
    ],
  },
  {
    version: "0.15.6",
    date: "2026-05-23",
    title:
      "Tool-toggle visibility fix on create form + instance row. The Create Instance modal had no Tools section at all, and the existing-instance chip was a small \"Show Tools (N)\" text link operators routinely missed. Both surfaces now show a prominent enabled-count badge with per-tool checkboxes.",
    highlights: [
      "Create Instance modal: new Tools section with per-tool checkboxes, Enable-all / Disable-all mass actions, live enabled-count badge.",
      "Pre-disable specific tools at create time — flows through to the backend as disabled_tools[] on POST /api/v1/instances.",
      "Existing-instance row: redesigned chip with bold label, color-coded enabled-count badge (green/blue/red), full-width tap target.",
      "Operator now sees the toggle UX in both surfaces without hunting for it.",
      "InstanceStore.create() accepts disabled_tools kwarg; REST validates list-of-strings; createInstance() API client typedef updated.",
    ],
  },
  {
    version: "0.15.5",
    date: "2026-05-23",
    title:
      "Hot-fix: marketplace cards now show live tool counts. The /api/marketplace/connectors endpoint was returning hardcoded toolCount (xsiam: 7, cortex-xdr: 10) instead of reading each connector.yaml. After R4/R5 expanded those to 50/59 the UI cards looked stale. Fixed by overlaying live spec.tools[] at request time.",
    highlights: [
      "GET /api/marketplace/connectors now reads each connector.yaml at request time and overlays the live spec.tools[] + toolCount onto the hardcoded metadata.",
      "Cards on /connectors page now show correct counts: 50 for Cortex XDR, 59 for Cortex XSIAM.",
      "Show Tools panel populates from the live list — all 50/59 toggleable checkboxes render.",
      "Falls back to hardcoded values per-connector if yaml missing (dev mode safety).",
      "Caught by operator UI feedback after R5 closure; the R4.4/R5.4 batteries had only validated the new /api/v1/connectors/<id>/tools endpoint, not the marketplace endpoint the cards read from.",
    ],
  },
  {
    version: "0.15.4",
    date: "2026-05-23",
    title:
      "R5.4 — XSIAM E2E battery + R5 arc closure. Validates the 59-tool XSIAM surface end-to-end. Combined Cortex tool count (XDR + XSIAM): 109 tools across both connectors. Arc complete.",
    highlights: [
      "scripts/e2e_xsiam_tools_battery.py — mirror of XDR battery. Catalog presence + toggle filter probe.",
      "R5 arc COMPLETE: XSIAM 14 → 59 tools across 5 sub-releases.",
      "Combined Cortex tool surface: XDR (50) + XSIAM (59) = 109 tools, all toggleable per-instance via the v0.14.0 Show Tools panel.",
      "XSIAM-unique categories (parsers/datamodel/broker) covered AND integrated with the shared toggle infrastructure.",
    ],
  },
  {
    version: "0.15.3",
    date: "2026-05-23",
    title:
      "R5.3 — XSIAM admin + XSIAM-unique (18 new tools). 13 admin (audit/distribution/exclusions/hash/exploits) mirroring R4.3 + 5 XSIAM-unique (parsers/datamodel/broker) that don't exist in XDR. Total XSIAM tools after R5.3: 59.",
    highlights: [
      "Common admin (13): audit (2), distribution (4), alert-exclusions (3), hash (2), exploits (2).",
      "XSIAM-unique (5): parsers (list, get), datamodel (describe — XSIAM-licensed), broker (list, get).",
      "xsiam_datamodel_describe internally builds XQL with the `datamodel` stage + polls — XDR-only tenants get 'Invalid License - XSIAM' here.",
      "R5.4 next: E2E battery validates all 59 tools against deployed XSIAM instance.",
    ],
  },
  {
    version: "0.15.2",
    date: "2026-05-23",
    title:
      "R5.2 — XSIAM endpoints + response + scripts (18 new tools). Mirrors R4.2's XDR pattern. Total XSIAM tools after R5.2: 41 (was 14 at v0.14.x). Each new tool auto-appears in the v0.14.0 Show Tools toggle panel.",
    highlights: [
      "Endpoints (9): xsiam_endpoints_list_all/get, isolate, unisolate, scan, scan_all, set_alias, retrieve_file, quarantine_file.",
      "Response actions (2): xsiam_response_get_action_status, _get_file_retrieval_details — poll any action_id, harvest file URLs.",
      "Scripts (7): list, get_metadata, run_script, run_snippet, get_execution_status/_results/_result_files.",
      "Path normalization caught during dev: xsiam's Fetcher base_url already has /public_api/v1; tools use bare paths.",
      "All tools required-filter guarded (no accidental tenant-wide actions). scan_all is intentionally separate so it can be disabled.",
    ],
  },
  {
    version: "0.15.1",
    date: "2026-05-23",
    title:
      "R5.1 — XSIAM incidents/alerts/IoC/download (9 new tools). First wave of the XSIAM expansion that mirrors R4.1's XDR additions. All wired to the v0.14.0 Tools toggle panel automatically — appears in Show Tools without any UI changes.",
    highlights: [
      "9 new XSIAM tools: incidents_list, incidents_get_extra_data, incidents_update, alerts_list, alerts_update, ioc_insert_json, ioc_disable, ioc_enable, download_file.",
      "Uses xsiam's Fetcher.send_request() — auth headers + URL normalization consistent with the existing XQL/asset/lookup tools.",
      "Helpers: _xsiam_err, _xsiam_ok, _xsiam_wrap (parallel to XDR's pattern).",
      "Total XSIAM tools after R5.1: 23 (14 existing + 9 new).",
    ],
  },
  {
    version: "0.15.0",
    date: "2026-05-23",
    title:
      "R5.0 — opens the XSIAM arc (mirrors R4's XDR work). Docs-only: data/knowledge/external/paloaltonetworks/cortex-xsiam/action/ populated with 30 endpoint markdown files copied from XDR's tree (xdr_*→xsiam_*) plus 5 XSIAM-unique docs (parsers/datamodel/broker). Subsequent v0.15.1/.2/.3 ship the actual ~47 new xsiam_* tools.",
    highlights: [
      "Vendor knowledge tree at data/knowledge/external/paloaltonetworks/cortex-xsiam/action/ — 35 markdown files cataloged in INDEX.md.",
      "XSIAM-unique categories authored from public API knowledge: parsers (list/get), datamodel (describe — XSIAM-license-gated), broker (list/get).",
      "Common surface (incidents/alerts/endpoints/response/scripts/ioc/download/admin) copied from XDR with xdr_→xsiam_ substitution; same /public_api/v1/... paths.",
      "R5.0 reuses R4.0's per-instance disabled_tools infra — zero new schema or backend changes. XSIAM tools land in the Tools toggle panel automatically as they ship in R5.1/.2/.3.",
      "Arc scope: grow XSIAM from 14 existing tools to ~61 across 5 sub-releases. Builds on R4.0's toggle UX so operators can prune destructive tools per-instance.",
    ],
  },
  {
    version: "0.14.4",
    date: "2026-05-23",
    title:
      "R4.4 — XDR tools E2E battery + R4 arc closure. Validates the 51-tool surface end-to-end on the deployed install — read-only tools called with no-op args + ok=true assertion; destructive tools verified by catalog-presence only; one toggle-filter probe per run validates the v0.14.0 disabled_tools surface. Arc complete.",
    highlights: [
      "scripts/e2e_xdr_tools_battery.py — single-shot, exit-code-driven battery. Classifies each XDR tool as CALL_AND_ASSERT_OK / CATALOG_ONLY / SKIP-needs-context.",
      "Toggle filter probe — disables xdr_assets_list, asserts catalog shows disabled=true, re-enables, asserts back. Single source of truth for the v0.14.0 disabled_tools end-to-end flow.",
      "Destructive tools (isolate, quarantine, blocklist, create / delete) intentionally CATALOG_ONLY — never called by the battery. They're tested by catalog presence + arg shape only; runtime validation belongs to operator hands-on smokes.",
      "R4 arc complete: 8 → 51 XDR tools across 7 categories (incidents / alerts / endpoints / response / scripts / IoC / admin). Per-instance toggle UI. Vendor knowledge tree at data/knowledge/external/.",
      "Tools requiring real per-tenant context (action_id, script_uid, asset_id, incident_id) skip cleanly with 'needs-context' — they're sanity-checked at catalog level, validated by operator workflows in chat.",
    ],
  },
  {
    version: "0.14.3",
    date: "2026-05-23",
    title:
      "R4.3 — XDR admin endpoints: 15 tools across audit / assets / distribution / alert-exclusions / hash analytics / exploits. Total XDR tool count now 51 (was 8 at v0.13.x). Hand-authored from public API knowledge — R4.4's E2E battery validates each against a real XDR tenant.",
    highlights: [
      "Audit (2): xdr_audit_list_management_logs (console actions), xdr_audit_list_agent_logs (per-agent reports).",
      "Asset inventory (2): xdr_assets_list (endpoints + cloud + users by type / risk), xdr_assets_get.",
      "Distribution management (4): list, create, get_url, versions — manage agent installer bundles.",
      "Alert exclusions (3): list, create (XDR filter expression), delete.",
      "Hash analytics (2): get per-tenant intel on a SHA-256, add to global blocklist.",
      "Exploits (2): list (filter by endpoint / CVE), get_details (process chain).",
      "R4.4 next: E2E battery validates all 51 tools against the deployed Cortex_XDR instance + closes the arc.",
    ],
  },
  {
    version: "0.14.2",
    date: "2026-05-23",
    title:
      "R4.2 — XDR endpoints + response + scripts: 18 new tools. The response-action tier of the XDR connector — list endpoints, isolate them, run scripts, retrieve files, poll action status. Wired to v0.14.0's per-instance disabled_tools so operators can prune destructive tools (e.g. xdr_endpoints_scan_all) from the agent's catalog.",
    highlights: [
      "Endpoints (9 tools): list_all, get (filtered), isolate, unisolate, scan, scan_all, set_alias, retrieve_file, quarantine_file. Filters AND together via _build_endpoint_filters helper.",
      "Response action status (2 tools): get_action_status, get_file_retrieval_details — poll any action by id, harvest file URLs from completed retrievals.",
      "Scripts library (7 tools): list, get_metadata, run_script, run_snippet (ad-hoc PowerShell/bash/Python), get_execution_status/_results/_result_files.",
      "All response-action tools refuse when no filter is supplied — accidental tenant-wide actions are blocked. The scan_all tool is intentionally separate so operators can disable it specifically.",
      "Cortex_XDR instance Tools tab now lists 36 entries (existing legacy + R4.1 renames + R4.1 net-new + R4.2). Each gets its own checkbox + state.",
    ],
  },
  {
    version: "0.14.1",
    date: "2026-05-23",
    title:
      "R4.1 — XDR Tools toggle panel goes live + 6 new tools (incidents/alerts update, IoC insert/disable/enable, download) + 6 renames to xdr_<category>_<action>. Legacy names work as aliases through one release cycle. Operators can now disable individual tools per instance via the /connectors Show Tools panel — checkbox UI with optimistic PATCH + audit logging.",
    highlights: [
      "/connectors Show Tools panel replaces static list with checkboxes — toggle individual tools; mass actions Enable all / Disable all; optimistic state with snapback on PATCH failure.",
      "PATCH /api/agent/instances/<id> with {disabled_tools: [...]} audit-logs the change as instance_tool_toggle with added/removed deltas.",
      "Six new XDR tools: xdr_incidents_update, xdr_alerts_update, xdr_ioc_insert_json, xdr_ioc_disable, xdr_ioc_enable, xdr_download_file.",
      "Six rename aliases land: get_cases_and_issues → xdr_incidents_list, get_alerts → xdr_alerts_list, etc. Legacy names remain functional through one release; removed in v0.15.0.",
      "4 new endpoint markdown docs: incidents/update, alerts/update, ioc/disable, ioc/enable.",
      "Fetcher.get_bytes() — new XDR client method for one-shot byte downloads, used by xdr_download_file.",
    ],
  },
  {
    version: "0.14.0",
    date: "2026-05-23",
    title:
      "R4.0 — Cortex XDR docs pull (26 endpoints) + per-instance disabled_tools infrastructure. Backbone for R4: every R4.x release lands new XDR tools that operators can selectively enable/disable per instance via the upcoming Tools tab. v0.14.0 ships the schema, REST surface, and connector-loader filter; the UI tab + first wave of new tools follow in v0.14.1.",
    highlights: [
      "New top-level data/knowledge/external/paloaltonetworks/cortex-xdr/action/ tree with 26 endpoint markdown files (incidents, alerts, endpoints, response, scripts, XQL, IoC, download) generated from ebarti/cortex-xdr-client.",
      "instances.db gains disabled_tools column (JSON list, opt-out default). InstanceStore.update_disabled_tools() with dedupe + Instance.disabled_tools dataclass field.",
      "PATCH /api/v1/instances/{id} now accepts {disabled_tools: [...]} — audit-logged as instance_tool_toggle with added/removed deltas.",
      "New GET /api/v1/connectors/{id}/tools[?instance_id=<id>] introspects connector.yaml's spec.tools[] + surfaces per-tool disabled state for the upcoming Tools tab.",
      "connector_loader.py filters disabled tools before FastMCP registration — agent's catalog never sees them. Log line counts enabled/total per connector.",
      "Existing 8 XDR tools work unchanged; renames + first wave of new tools land in v0.14.1.",
    ],
  },
  {
    version: "0.13.3",
    date: "2026-05-23",
    title:
      "R3.C.3 — E2E test PASSED: user YAML upload → UDP records arrive with declared fields. The capability acceptance criterion for the R3.C arc (declared at v0.13.0) is met on the deployed install. Upload AcmeCorp YAML → catalog includes it → install lifts fields from the YAML → createDataWorker streams 11 records to a UDP listener → every record contains exactly the 5 declared fields (no extras, no missing).",
    highlights: [
      "scripts/e2e_user_yaml_upload_to_syslog.py — full E2E test: UDP listener in xlog container, upload + install + worker + capture + assert. PASSES end-to-end on deployed v0.13.1.",
      "8-step verification: preview → commit → catalog → install → schema → createDataWorker (UDP) → 10s capture → cleanup. Each step asserts unambiguous pass conditions.",
      "Test discovered + corrected xlog GraphQL schema details that the script had assumed wrongly: endpoint at '/' (not '/graphql'), createDataWorker on Query (not Mutation), SchemaOverrideInput's field list is 'vendorFields' (not 'fields').",
      "R3.C arc closure proof — captured UDP datagrams contain exactly the field declarations from the uploaded YAML, validating the loader → install → schema_override → OverrideSender chain end-to-end.",
      "Cleanup verified: worker stops, install uninstalls, user YAML deletes — every step returns success.",
    ],
  },
  {
    version: "0.13.2",
    date: "2026-05-23",
    title:
      "R3.C.2 — UI upload dialog on /data-sources. v0.13.1 shipped the REST endpoints; v0.13.2 puts them behind a button. Operators see 'Upload data source' in the toolbar, paste a YAML, get the validation + similarity prompt ('did you mean Fortinet?'), and commit through the accept-token flow. User-uploaded vendor cards carry a 'User upload' badge.",
    highlights: [
      "New Upload data source button in /data-sources toolbar opens a modal with paste-YAML input + Insert-sample shortcut + image-guidelines disclosure.",
      "Two-phase UX: PREVIEW (validate + similarity check + bundle-collision flag) → CONFIRM (pick create_new or group_under) → COMMIT. Client-side re-preview after group_under rewrites accept_token correctly.",
      "Agent-side proxies for the v0.13.1 endpoints — /api/agent/data-sources/user/preview, /user (POST + GET), /user/[id] (GET + DELETE), /user/[id]/logo.",
      "VendorCard for any vendor with at least one user-uploaded row shows a tertiary-colored 'User upload' badge distinct from category badges.",
      "Catalog row type extension: origin + id fields surface to the UI so it can apply origin-aware styling + future origin filters.",
    ],
  },
  {
    version: "0.13.1",
    date: "2026-05-23",
    title:
      "R3.C.1 — YAML loader becomes canonical + operator upload endpoints. The /data-sources Browse view now reads from the 260 per-source YAMLs (v0.13.0 baked them; v0.13.1 cuts catalog.json out of the loop). Five new REST endpoints let operators upload their own data_source.yaml, with similarity check ('did you mean Fortinet?') and accept-token round-trip. End-user behavior changes from v0.13.0 (which was a no-op).",
    highlights: [
      "Marketplace catalog endpoint /api/v1/data-sources/catalog now reads from the YAMLs via DataSourcesYamlLoader. catalog.json read path deleted (per canonical-state discipline — no stale fallback). UI shape preserved.",
      "5 new REST endpoints: POST /user/preview (validate + similarity), POST /user (commit with accept_token), GET /user (list), GET /user/<id> (detail + doc), DELETE /user/<id>, GET /user/<id>/logo (stream inline base64).",
      "Vendor similarity check (Levenshtein-2 + substring): operator typos like 'Forinet' suggest 'Fortinet' in the upload modal. Pure-Python; no python-Levenshtein C dependency.",
      "Bundle wins on id collision — operators can't override bundled packs; the write endpoint refuses bundle-reserved ids with a clear error.",
      "Install path now branches by origin: user-uploaded sources install fields[] directly from their YAML (no cortex-content extraction); bundled sources still extract via cortex-content.",
      "46 new pytest tests (loader + similarity); total 467 passing.",
    ],
  },
  {
    version: "0.13.0",
    date: "2026-05-23",
    title:
      "R3.C.0 — bundled data sources migrated to per-source YAML format. 260 data_source.yaml files (one per catalog row) land in bundles/spark/data-sources/. data_source.schema.json defines the v1 contract with 26-type field vocabulary including string_short/string_long/json/enum/regex. End-user behavior unchanged; loader switch happens in R3.C.1.",
    highlights: [
      "data_source.yaml v1 schema locked: 3-tuple identity (preserves existing tool compatibility), 26-type field vocab, base64-inline SVG logo (50KB pre-encode for operator uploads), origin: bundle|user, optional XDM mappings.",
      "Migration script writes 260 YAMLs from catalog.json + pack_metadata + vendor_map + vendor_svgs. Idempotent. Maintainer-only.",
      "Validator extension check_bundled_data_sources_yaml_valid schema-validates every YAML against data_source.schema.json at every push. 17 → 18 checks.",
      "Phased rollout: R3.C.0 (v0.13.0) = migration; R3.C.1 = loader switch + upload endpoints; R3.C.2 = similarity check + UI dialog; R3.C.3 = E2E with temp syslog server.",
      "Behavior identical to v0.12.0 for end users — bundled marketplace still loads from catalog.json. YAMLs are baked into image waiting for R3.C.1 loader.",
    ],
  },
  {
    version: "0.12.0",
    date: "2026-05-23",
    title:
      "Vendor-faithful UDP/TCP worker streaming + installed-data-sources surface to the agent. v0.11.5's E2E test exposed two gaps in the marketplace pipeline; v0.12.0 closes both. The realistic 'stream FortiGate logs to udp:host:port' workflow now produces records with FTNTFGT* field names (not Rosetta's generic local_ip/remote_port). The agent's reasoning now bridges marketplace install state and tech stack via a new data_sources_installed_as_vendors MCP tool.",
    highlights: [
      "phantom_create_data_worker MCP tool accepts optional schema_override (the fields[] array from data_sources_get_schema). When supplied with a udp:/tcp: destination, the worker streams vendor-faithful records.",
      "New OverrideSender class in xlog (xlog/app/override_sender.py) — UDP/TCP-aware sender that uses dynamic_schema's existing override engine. Architecturally cleaner than forking rosetta-ce.",
      "End-to-end smoke verified: FortiGate install → schema fetch → createDataWorker with override → 24 UDP datagrams captured, 10/10 FortiGate field names in every record.",
      "New MCP tool data_sources_installed_as_vendors returns installed sources as tech-stack-shaped vendor entries (vendor, product, category, source='installed'). Use AND with phantom_get_technology_stack — agent merges in reasoning.",
      "Backward-compat preserved: workers without schema_override still flow through the existing Sender → Rosetta path. Existing scenario workers unchanged.",
      "Build-dev-installer workflow patched to accept HTTP 401 on cold-start dev-latest tag delete (GitHub Actions workflow_run permission cascade quirk).",
    ],
  },
  {
    version: "0.11.5",
    date: "2026-05-23",
    title:
      "Docs sync for the marketplace UX overhaul — /help/user#data-sources and the install-vendor-data-source journey rewritten to reflect v0.11's vendor-grouped layout, constant neutral panel, drawer preview, and install-from-drawer affordance. Final patch before the customer tag closes the R2 arc.",
    highlights: [
      "user guide #data-sources Browse SubSection rewritten — describes vendor-card layout, full-width tray on expand, drawer preview for uninstalled packs, install-from-drawer flow.",
      "install-data-source-simulate-vendor-logs journey's howToTest steps updated to match v0.11 UI (vendor cards, click row body for preview, install from drawer).",
      "No architecture-page changes needed — v0.11 was presentation-layer + endpoint enrichment. The substrate spec is unchanged.",
      "Pre-tag docs discipline complete; ready for customer release tag.",
    ],
  },
  {
    version: "0.11.4",
    date: "2026-05-23",
    title:
      "Clicking an UNINSTALLED data source now opens the drawer in preview mode. Schema endpoint falls back to cortex-content extraction when the pack isn't in the install store yet, returning the field inventory + an Install CTA in the drawer footer. Drawer's header icon now renders the vendor SVG (was empty for installed packs due to stale cached logo_url). Observability already captures install/uninstall via audit events — no change needed.",
    highlights: [
      "Schema endpoint /api/v1/data-sources/<pack>/<rule>/<dataset>/schema now has a preview fallback path. When the pack isn't installed, it extracts the schema from the cortex-content baked tree (same code install uses) and returns is_preview: true.",
      "Drawer footer branches on is_preview: shows 'Install data source' button + 'Preview · not installed' badge for uninstalled, 'Uninstall' for installed. After install, drawer auto-refetches and flips to installed mode.",
      "logo_url normalized to /api/agent/data-sources/logo/<pack> in both installed + preview paths. Drawer header icon now resolves via vendor_map.yaml → renders the vendor SVG on the constant near-white panel.",
      "handleInstall signature relaxed to accept any {pack_name, rule_name, dataset_name} shape — the drawer can invoke install with a DataSourceWithSchema (preview mode).",
      "Observability: audit.record(action='data_source_install'/'data_source_uninstall') was already wired in v0.8.0. Events surface in /observability via audit_search / audit_recent.",
    ],
  },
  {
    version: "0.11.3",
    date: "2026-05-23",
    title:
      "Two operator-reported issue fixes: (1) ~63 packs showing the placeholder box icon instead of their vendor logo — caused by stale logo_url in catalog.json. Catalog endpoint now overrides logo_url to point at the route for every pack with a vendor mapping. (2) Clicking a vendor card stretched its sibling cards on the same row. ExpandedTray now renders as a full-width grid sibling so siblings stay constant height and subsequent cards push down.",
    highlights: [
      "Catalog enrichment overrides logo_url + logo_type at endpoint serve time. The v0.8.1 bake's null logo_url for 63 packs is no longer authoritative — vendor_map.yaml + vendor_svgs/ guarantee the route can serve every pack.",
      "0 of 259 rows have null logo_url after v0.11.3 (was 63 of 259 on v0.11.2). Corelight, Dragos, F5, Forescout, IBM, Linux, NVIDIA, Oracle, Proofpoint, and ~55 others now show their vendor logo instead of the placeholder.",
      "ExpandedTray extracted from VendorCard. Cards stay constant height; the expanded inner pack list renders as a separate col-span-full grid sibling.",
      "Grid uses grid-flow-row-dense so when a tray inserts a new full-width row, the auto-placer backfills any gap on the same row as the expanded card — siblings stay put, subsequent rows push down.",
      "Both fixes are infrastructure-level — no operator-facing behavior change beyond the visual improvements.",
    ],
  },
  {
    version: "0.11.2",
    date: "2026-05-23",
    title:
      "Wordmark SVG fills now enforce WCAG AA contrast (4.5:1) against the constant near-white logo panel. Fixes vendors whose brand colors looked 'missing' at the rendered 16px text size — Proofpoint light-blue, Portnox cyan, WatchGuard red, Reblaze red, and a dozen others now darken automatically to a legible variant.",
    highlights: [
      "New color-math helpers in scripts/source_vendor_svgs.py: proper sRGB-linearized WCAG 2.1 luminance, contrast ratio calculation, iterative-darken-until-AA-passes algorithm.",
      "render_wordmark_svg() wraps brand color through ensure_wcag_contrast() before emitting the light variant. Dark variant unchanged (UI no longer fetches it).",
      "Sample adjustments: Proofpoint #0098D5 (3.0) → #0079AA (4.58); Portnox #15A0D3 (3.0) → #0F789E (4.70); WatchGuard #E1251B (4.0) → #D52319 (4.84).",
      "Untouched: SimpleIcons monochrome SVGs (render black by default), gilbarbara branded SVGs (multi-color, paths not adjusted), brand colors already passing AA.",
      "135 wordmark SVGs regenerated. The function is the single source of truth — future bakes inherit the contrast enforcement automatically.",
    ],
  },
  {
    version: "0.11.1",
    date: "2026-05-23",
    title:
      "Logo panel fix: constant neutral background that doesn't change with theme. Sidesteps the theme-switch invisibility bug where logos with white text disappeared against light-theme panels (and vice versa) due to Cache-Control + React render races. UI now always fetches the light SVG variant; the near-white panel renders identically in both themes.",
    highlights: [
      "Constant #F7F8FA icon panel — VendorCard, InstalledCard, DetailDrawer all share the same near-white panel background regardless of operator theme.",
      "UI always fetches ?theme=light regardless of active theme — sidesteps the cache desync race when switching themes.",
      "Every previously-invisible vendor now renders cleanly: Barracuda, Corelight, Delinea, Dragos, F5, Forescout (wordmarks); Darktrace, CyberArk, Bitsight, Abnormal Security, Imperva (theme-toggle invisibility).",
      "Dark SVG variants in vendor_svgs/ become dead UI code but stay on disk for backwards compat — a future cleanup could drop them entirely.",
      "Operator-reported smoke gap → fix shipped in same arc as the R2 grouping work.",
    ],
  },
  {
    version: "0.11.0",
    date: "2026-05-23",
    title:
      "Data Sources marketplace redesign — one card per VENDOR instead of per pack. Microsoft's 26 packs collapse into one Microsoft card with category badges (SIEM, Cloud, Network, Email). Click any card → expand inline → install individual data sources. R2 of the three-release marketplace UX overhaul, building on R1's theme-aware logos.",
    highlights: [
      "Vendor-grouped Browse view: ~110 cards instead of 197. Microsoft owns 26 packs (Azure, Defender, Sentinel, etc.) — they share one Microsoft card. Cisco owns 9 — one Cisco card.",
      "Icon-LEFT card layout (112×112 panel) with title + category badges + pack count on the right. Click anywhere on the card to expand inline.",
      "Category badges derived from pack metadata: SIEM, Network, EDR, Cloud, Cloud Provider, IAM, Threat Intel, Email, Vuln, DevOps. Mapped from the verbose Cortex taxonomy via a small lookup table.",
      "Expanded vendor reveals inner pack rows — each with rule/dataset + field count + install button + click-to-detail.",
      "Agentix noise removed: every pack in the catalog supports 'agentix' as a module, so it was always present in every supportedModules pill. v0.11.0's filterAgentix() helper strips it everywhere pills render.",
      "Catalog endpoint enriches each row server-side with vendor_key + vendor_display_name + vendor_primary_color + categories[] — joined from vendor_map.yaml and per-pack pack_metadata.json. Process-cached lookup table; O(1) per row after warmup.",
      "R3 (per-data-source YAML + CRUD operations) is the next release in this arc.",
    ],
  },
  {
    version: "0.10.0",
    date: "2026-05-22",
    title:
      "Theme-aware SVG logos for all 197 packs. v0.9.4 restored 93 missing PNGs but PNGs don't respect theme — Abnormal Security was invisible in dark, AWS GuardDuty invisible in light. v0.10.0 swaps the serving path entirely: every pack now gets light + dark SVG variants, picked by the operator's active theme. Vendor identity captured in vendor_map.yaml as a side-effect for R2's vendor-grouped UI to consume.",
    highlights: [
      "Logo route is now theme-aware: GET /api/v1/data-sources/logo/<pack>?theme=light|dark serves the right SVG variant. UI passes the operator's current theme via the existing useTheme() hook.",
      "vendor_map.yaml — single source of truth mapping 197 packs to 110 canonical vendors. Microsoft owns 26 packs (Azure, Defender, Sentinel all share one Microsoft SVG); Cisco owns 9 (Catalyst, IPS, etc share one Cisco SVG); 83 singleton vendors get their own.",
      "Per-vendor SVG sharing means perfect browser cache locality — load one Microsoft logo and all 16 Microsoft cards render instantly.",
      "Sourcing pipeline: gilbarbara/logos (22 branded light) → SimpleIcons (14 branded light) → demisto/content (49 branded dark) → wordmark fallback (vendor name in brand color) for gaps. All 220 SVGs MIT or CC0 licensed; LICENSES.md tracks provenance per source.",
      "v0.9.3 generic-shield placeholder (sha256 3d95768ef2e0…) is detected by hash + rejected so it never gets reused as 'branded'.",
      "Validator extends to 17 checks: new check_pack_theme_variants_complete() ensures every pack maps to a vendor whose light+dark variants both exist. Future bakes can't silently break the theme-aware contract.",
      "Sets up R2 (vendor-grouped UI + redesigned cards) and R3 (per-data-source YAML + CRUD) to ship cleanly on top.",
    ],
  },
  {
    version: "0.9.5",
    date: "2026-05-22",
    title:
      "Structural guard against the .gitignore silent-drop class of bug. The AI Layer validator now compares files-on-disk against the git index for designated content directories — any drift fails CI with the offending paths named. Closes the v0.8.1 → v0.9.3 regression door.",
    highlights: [
      "v0.9.4 fixed the symptom (93 missing PNGs); v0.9.5 fixes the class (any future bake into a *.ext-blanketed directory without an !-exception now fails the validator instead of silently dropping files for 8 releases).",
      "New check_no_silent_gitignore_drops() in tooling/validate/validate_all.py. For each (directory, glob, label) tuple in SILENT_DROP_GUARDS, compares filesystem rglob against git ls-files filtered by the pattern.",
      "Initial guard: bundles/spark/connectors/cortex-content/baked/ for *.png (the v0.8.1 case). Future content directories add one tuple — no change to the check function.",
      "Both failure modes covered: the pre-v0.9.4 silent-drop case AND the post-v0.9.4 noisy-but-missable untracked-file case both reduce to 'filesystem has file, git index doesn't'.",
      "Positive + negative tested locally: green against HEAD, RED with a deliberate stray PNG, green again after cleanup. Validator total goes from 15/15 to 16/16.",
    ],
  },
  {
    version: "0.9.4",
    date: "2026-05-22",
    title:
      "Critical fix — restores 93 PNG vendor logos that have been broken silently since v0.8.1. Root cause: .gitignore had a blanket *.png rule with exceptions for some directories but NOT for the baked catalog tree, so 93 of v0.8.1's freshly-baked PNG logos never landed in git and therefore never landed in the agent image. After v0.9.4: 171 of 197 packs branded (87%), 0 packs missing logos.",
    highlights: [
      "Root cause: .gitignore line 144 has `*.png` with `!`-exceptions for mcp/agent/public/, installer/, docs/ — but NO exception for bundles/spark/connectors/cortex-content/baked/. v0.8.1's bake wrote 93 PNGs; git add silently skipped all of them.",
      "Symptom: 93 marketplace cards have been showing no vendor logo since v0.8.1 shipped. Earlier releases (v0.8.2 through v0.9.3) carried the regression because no smoke test ever loaded /data-sources in a browser and inspected console for logo 404s.",
      "Fix: add `!bundles/spark/connectors/cortex-content/baked/**/*.png` exception. Commit the 93 untracked PNGs that have existed on the maintainer's local tree since v0.8.1.",
      "Post-v0.9.4 coverage: 171 / 197 branded (87%). 197 / 197 with any logo (100%). The v0.9.3 numbers in the prior release notes were only true on the maintainer's local tree, not on the deployed install — v0.9.4 makes them actually true everywhere.",
      "Discovered by browser console-error scan during v0.9.3 second-round review. The lesson: `find` vs `git ls-files` diff after a file-producing script catches `.gitignore` silently dropping files where `git status` alone misses it.",
    ],
  },
  {
    version: "0.9.3",
    date: "2026-05-22",
    title:
      "Vendor logo coverage. Operator noticed several Data Sources marketplace cards missing logos. Audit: 52 of 197 baked packs (26%) had no logo at all because they're XSIAM modeling-rule-only packs without Integrations/ directories in demisto/content. New maintainer-only fetch script resolves them in 3 tiers: SimpleIcons CDN (CC0), curated Wikipedia Commons URLs for major brands not in SimpleIcons, generic shield fallback for niche vendors. Coverage: 145 → 171 branded (74% → 86%), zero packs now missing any logo.",
    highlights: [
      "New scripts/fetch_vendor_logos.py — idempotent, runs via `python3 scripts/fetch_vendor_logos.py` (re-fetches missing) or `--force` (refresh all). Adapts SimpleIcons SVGs to use currentColor for light + dark theme adaptation.",
      "26 new branded logos added: Microsoft family (×10: ADFS, DHCP, DNS, Defender for Identity, Entra ID, Exchange Server, IIS, Intune, Sysmon, Office), Cisco, F5, Google Chrome, Huawei, IBM, Linux, McAfee, NVIDIA, Oracle, Symantec, Trend Micro, Ubiquiti, VMware (×3), Synopsys.",
      "26 generic shield fallbacks for niche vendors (CyberArk, Forcepoint, Forescout, Dragos, LenelS2, ManageEngine, Nasuni, Netmotion, Portnox, Proofpoint, Reblaze, Trellix, Watchguard, Zscaler, etc.). Better than broken images. Operator can override by dropping a real logo file at the same path.",
      "Final coverage: 171 / 197 packs branded (86%), 0 / 197 missing logos (was 52).",
      "Logo discovery route unchanged — the data-sources logo endpoint already walks `<pack>/Integrations/<int>/<int>_dark.svg` and similar. No API or catalog schema change required.",
    ],
  },
  {
    version: "0.9.2",
    date: "2026-05-22",
    title:
      "Spec-drift cleanup after v0.9.1. The second-round review of the v0.9.1 security fix surfaced one real regression — a server-side fetch in /jobs was still using the pre-v0.4.0 cookie name, so the YAML-issues banner silently failed to render after v0.9.1's middleware turned the latent bug into an active one. Fixed here plus 6 documentation locations that still referenced the old cookie name.",
    highlights: [
      "/jobs page YAML-issues banner works again — fetchYamlIssues was sending phantom_auth=${token} server-side; v0.9.1's middleware rejected it. One-line fix to phantom_session=${token}.",
      "6 doc-drift updates — mcp/agent/CLAUDE.md, docs/CICD.md (2 spots), settings/backup-restore JSDoc, profile/page.tsx JSDoc, and 2 journey descriptions now correctly reference phantom_session + the middleware.ts (v0.9.1+) gate.",
      "AI-LAYER.md phase-tracking table — Phase 3 row now carries the (closed) annotation for #79, matching Phase 1 and Phase 2 rows.",
      "middleware.ts doc-comment — /api/marketplace/connectors documented as an intentional read-only exclusion (the routes serve hardcoded catalog JSON with no secrets), with a forbidden-going-forward warning that the silent exclusion becomes dangerous if those routes ever grow write handlers.",
      "Historical context preserved: CHANGELOG entries, past-tense comments, and the v0.4.0 + v0.9.1 release notes correctly keep their phantom_auth references — they describe the pre-rename state and are immutable historical record.",
    ],
  },
  {
    version: "0.9.1",
    date: "2026-05-22",
    security: true,
    title:
      "Security fix — server-side session cookie enforcement on every /api/agent/* + /api/chat + /api/skills/* endpoint. Pre-v0.9.1 AuthGate gated the BROWSER but not the API; any caller that reached port 3000 could control the agent with NO cookies. New Next.js middleware validates phantom_session against the MCP-side session store on every request. Companion fix: Backup/Restore have been completely broken since v0.4.0 (hardcoded the pre-v0.4.0 cookie name) — now work for the first time on the v0.4.x+ cookie surface.",
    highlights: [
      "Closes #70 — every /api/agent/* mutation endpoint, /api/chat, and /api/skills/* now requires a valid phantom_session cookie. Absence or invalid value → 401.",
      "New Next.js middleware.ts at the server tier. Edge runtime (Next.js 15.1.6). Validates via the same validateSession path /api/auth/status uses — 30s positive cache, ~10ms first-request overhead.",
      "Backup and Restore work for the first time since v0.4.0. Pre-v0.9.1 both routes hardcoded the pre-v0.4.0 cookie name (phantom_auth) and always returned 401. Discovered during the explorer-subagent map of the auth surface.",
      "Exemptions documented + tested: /api/agent/health stays open for Docker compose healthcheck; /api/agent/internal/fire-hook keeps its MCP_TOKEN bearer auth (called by the embedded MCP subprocess, not the browser).",
      "Architecture page #authentication updated to reflect the middleware layer and the corrected phantom_session cookie name throughout (was still saying phantom_auth in places).",
    ],
  },
  {
    version: "0.9.0",
    date: "2026-05-21",
    title:
      "Marketplace Data Sources — fully polished customer release. Bundles v0.8.1-v0.8.4 into one customer-shippable version. Same capability as v0.8.0 with the catalog shipped offline (Browse loads instantly), runtime path scrubbed of external references, /data-sources redesigned to match the rest of the UI, and complete help docs landed. Operators on v0.8.0 see no breaking change — they gain the polished experience.",
    highlights: [
      "Catalog ships in the agent image — Browse loads sub-second with 197 vendor packs / 232 schemas / 145 logos. No runtime network calls.",
      "Full UI redesign of /data-sources from operator mockups — skeleton shimmer loading, glass-pane cards, expandable Browse rows with per-row install, right-slide drawer with stat tiles + sortable field table, ruby-red uninstall modal. Light + dark theme parity.",
      "Help docs landed — /help/architecture#data-sources covers storage / catalog / REST / MCP / skill chain / dynamic schema; /help/user#data-sources covers Browse / Installed / ask-the-agent / what-vendor-faithful-means; new install→simulate journey.",
      "Path traversal defense on the catalog client + 18 unit tests pin the safety contract.",
      "All operator-visible surfaces (UI copy, tool docstrings, marketplace card, release notes) describe the catalog as just shipping with Phantom.",
      "Zero behavior changes from v0.8.0 — pure polish of the existing capability. data_sources.db schema unchanged; no migrations.",
    ],
  },
  {
    version: "0.8.4",
    date: "2026-05-21",
    title:
      "Data Sources help docs landing. The Marketplace Data Sources capability now has full help coverage — architecture section explains the storage model + catalog source + REST surface + skill chain, user-guide section walks Browse + Install + how to ask the agent for vendor-faithful logs, and a new journey takes the operator end-to-end from install through simulation. No code behavior changes — pure doc landing the v0.8.0 closure report flagged.",
    highlights: [
      "/help/architecture#data-sources — new architecture section with 8 subsections covering storage, baked catalog, REST surface, MCP tool surface, skill chain, dynamic schema engine.",
      "/help/user#data-sources — new user-guide section with 4 subsections: Browse, Installed, ask-the-agent prompts, and what vendor-faithful means under the hood.",
      "New journey install-data-source-simulate-vendor-logs walks install FortiGate from Browse → ask agent to simulate → records with vendor field names appear (srcip / dstport / sentbyte).",
      "No code behavior changes — Data Sources continues to work exactly as in v0.8.3.",
    ],
  },
  {
    version: "0.8.3",
    date: "2026-05-21",
    title:
      "Marketplace Data Sources UI redesign — operator-supplied mockups translated into Phantom's React + Material 3 stack. Skeleton shimmer loading, glass-pane cards, expandable Browse pack cards with per-row install, right-slide detail drawer with stat tiles + sortable field table + XDM mappings, ruby-red uninstall modal, notification stack, search-off empty state, error panel. Full light + dark theme support via semantic tokens.",
    highlights: [
      "Full rewrite of /data-sources page (~1100 lines, 13 named components in one file). Every operator-visible surface matches the new mockup design language.",
      "Ambient background glow + glass-pane cards + ghost-border insets bring the page in line with the Obsidian Lens aesthetic.",
      "Skeleton shimmer placeholder cards during catalog load — moving-gradient animation with staggered delays per card. Real cards swap in when data arrives.",
      "Per-row install spinner in Browse: clicking Install on one dataset only spins that row; other rows stay interactive. Notification banner confirms each install (auto-dismiss after 5s for success, sticky for errors).",
      "Detail drawer: 4 stat tiles (field count / vendor fields / style / version with pin dot), supported-modules chip row, sortable schema-fields table grouped by meta vs vendor, XDM mappings section, sticky footer with destructive Uninstall action.",
      "Uninstall modal: dedicated ruby-red destructive flow with structured bullet-list explaining what removal does. Replaces the previous inline window.confirm.",
      "Field-table client-side filter — type to filter the schema's field list without server round-trips. Useful for inspecting 170+ field schemas.",
      "All colors via Material 3 token system (text-primary, bg-surface-container, etc.) — page renders correctly in both light + dark themes from the same DOM, no theme-specific branches.",
    ],
  },
  {
    version: "0.8.2",
    date: "2026-05-21",
    title:
      "Marketplace Data Sources polish — catalog now reads instantly from local files; logos serve through Phantom. Same operator-visible feature set as v0.8.0, with the runtime path simplified to remove all references to remote sources. Path traversal defense + 18 unit tests pin the safety contract.",
    highlights: [
      "Catalog endpoint serves the rolled-up packs/rules from the local bundle. Sub-millisecond response.",
      "Logo route GET /api/agent/data-sources/logo/{pack} streams SVG/PNG bytes with Cache-Control immutable. Logos always render through Phantom — no third-party fetches.",
      "Path traversal defense: any '..' or absolute path on the catalog client raises a clean not-found error. 18 unit tests pin the contract.",
      "End-to-end fidelity verified on the deployed install — install FortiGate (176 fields persisted, pack_version 2.0.16) → generateFakeDataV2 with FortiGate schema_override → records with srcip/dstip/srcport/dstport/action as top-level keys.",
      "Catalog includes 197 packs / 232 schemas / 145 vendor logos. xsiam-only filter applies by design (operator decision #5).",
    ],
  },
  {
    version: "0.8.1",
    date: "2026-05-21",
    title:
      "Marketplace Data Sources catalog ships with Phantom. Browse loads instantly, install is local, logos serve through Phantom. Catalog includes 197 packs / 232 schemas / 145 logos (2.9 MB bundled).",
    highlights: [
      "Catalog ships in the agent image — Browse view loads in under a second.",
      "Install path reads schemas from the local catalog — instant, no network.",
      "Vendor logos served via /api/agent/data-sources/logo/{pack} with browser-cache headers.",
    ],
  },
  {
    version: "0.8.0",
    date: "2026-05-21",
    title:
      "Marketplace Data Sources — full capability shipped. Operators can install vendor schemas extracted from Cortex ModelingRules + ask the chat agent to simulate vendor-faithful logs (FortiGate, PaloAlto, Okta, etc.) that Cortex's stock modeling rules parse into XDM correctly. New /data-sources page + Browse drill-down + xlog dynamic schema + simulate_vendor_logs skill. End-state acceptance check GREEN end-to-end: install FortiGate → 'simulate FortiGate logs' → records with srcip/dstip/srcport/dstport/action as keys.",
    highlights: [
      "End-state acceptance check GREEN on phantom-vm dev-9f1a576: install FortiGate via REST → 176 fields persisted → xlog generateFakeDataV2 with the schema override emits {srcip, dstip, srcport, dstport, proto, action, user, sentbyte, rcvdbyte} — FortiGate's actual field names with plausible values. schemaApplied: true, fallbackReason: null.",
      "New /data-sources page (sidebar Integration > Data Sources). Two tabs: Installed grid (logo cards + field counts + uninstall) and Browse drill-down (vendor catalog from upstream Cortex content with per-row install buttons + 'all installed' status icons).",
      "Five new REST endpoints + three agent-callable MCP tools (data_sources_list / data_sources_get_schema / data_sources_install) + agent-side proxy routes. Catalog state per CLAUDE.md § Catalog boundary — agent IS allowed to mutate.",
      "xlog GraphQL gains generateFakeDataV2(request, schemaOverride) — when schemaOverride is supplied, records' keys match the vendor's actual field names. Backward-compat: existing generate_fake_data query unchanged.",
      "Simulate-vendor-logs skill (bundles/spark/mcp/skills/workflows/) triggers when the operator names a specific vendor in chat. Chains list → schema → v2 → echoes which schema was applied + sample record. Decision tree handles missing data sources + rawlog-only fallback.",
      "Scenario 1 upgrade: code-only, no installer change, no volume wipes. New /app/data/data_sources.db is created on first boot (CREATE TABLE IF NOT EXISTS). Existing connectors/instances/jobs/skills/memory/KB all preserved.",
      "Arc spans 7 commits (v0.7.5 → v0.7.11) + 431 tests pass (+66 over arc-start). Full breakdown in CHANGELOG.md [v0.8.0]. Out of scope: rawlog-only schemas (Phase 1.5), XDM mapping extraction (Phase 5), signed connector registry (#73).",
    ],
  },
  {
    version: "0.7.11",
    date: "2026-05-21",
    title:
      "Phase 4 of the v0.8.0 arc — the agent learns to use installed Data Sources. New simulate_vendor_logs skill triggers when the operator names a specific vendor (\"simulate FortiGate logs\"). The skill chains data_sources_list → data_sources_get_schema → xlog generate_fake_data_v2 with schema_override. New phantom_generate_fake_data_v2 MCP tool exposes the v0.7.10 GraphQL field to the agent.",
    highlights: [
      "phantom_generate_fake_data_v2 MCP tool wraps xlog's generateFakeDataV2 GraphQL. Same FakeDataRequest as v1 + optional schema_override (vendor_fields list extracted from a Data Source). Backward-compat: no override → identical to v1.",
      "Exported from xlog connector + listed in connector.yaml so the agent + tool dispatcher see it. Operator-facing description in connector.yaml documents the typical 3-step chain (list → schema → v2).",
      "New skill in bundles/spark/mcp/skills/workflows/simulate_vendor_logs.md (165 lines). Triggers on phrases like 'simulate FortiGate', 'generate PaloAlto events', 'create Okta audit records'. Falls back to the legacy phantom_generate_fake_data path when the request is generic (no vendor name).",
      "Step-by-step procedure documented + the decision tree for missing data sources (DON'T auto-install — point operator at /data-sources Browse). is_rawlog_only handling explicit (degrade to Rosetta CEF). Field-name preservation discipline spelled out.",
      "End-to-end smoke procedure baked into the skill body: install FortiGate via Browse → chat 'simulate 50 FortiGate logs' → expect vendor-faithful field names like srcip/dstip/srcport/dstport/action.",
      "Arc-completion tag v0.8.0 follows after the post-deploy smoke against v0.7.11 lands GREEN. This is the first commit where 'simulate FortiGate logs' actually produces vendor-faithful records end-to-end via the chat agent.",
    ],
  },
  {
    version: "0.7.10",
    date: "2026-05-21",
    title:
      "xlog learns vendor-faithful log emission. New generate_fake_data_v2 GraphQL query accepts an optional schema_override — top-level keys in the generated records match the Cortex ModelingRule's vendor field names so the matching modeling rule parses them into XDM correctly. Backward-compat preserved: existing generate_fake_data query unchanged. 28 xlog tests pass; +19 new. Phase 3 complete.",
    highlights: [
      "Vendor-faithful logs at the GraphQL layer. Pass {vendor_fields: [{name: 'srcip'}, {name: 'action'}, ...]} as schema_override → generated records use those exact key names instead of Rosetta's generic ones.",
      "Smart value generation: observable_overrides (caller-pinned IPs/users) → explicit type hint (int/bool/datetime/ipv4) → field-name pattern (srcip/srcport/hash/email/...) → short random string fallback. First match wins.",
      "Meta fields (_id/_time/_vendor/etc.) automatically omitted from output — the ModelingRule's XDM mapping populates those at ingestion time, including them in simulated logs would conflict.",
      "Backward-compat preserved: generate_fake_data_v2 with no schema_override delegates to the existing Rosetta path verbatim. fallback_reason field in the response tells you which path fired.",
      "Real FortiGate slice tested: 11-field schema (srcip/dstip/srcport/dstport/proto/action/user/sentbyte/rcvdbyte + 2 meta) → records with IPv4 srcip, action from allow/deny vocabulary, sentbyte as int, meta fields absent.",
      "Phase 3 of v0.8.0 complete. Phase 4 (simulate_vendor_logs skill that chains data_sources_list → data_sources_get_schema → generate_fake_data_v2) ships next, then the arc completes at v0.8.0.",
    ],
  },
  {
    version: "0.7.9",
    date: "2026-05-21",
    title:
      "Browse drill-down lands on /data-sources. Vendor card grid with real logos, grouped + collapsible dataset lists, per-row Install button, search filter, 'include rawlog-only' toggle. New /api/v1/data-sources/catalog endpoint rolls up modeling rules with per-row installed-state overlaid.",
    highlights: [
      "Two tabs on /data-sources: 'Installed (N)' and 'Browse'.",
      "Vendor card grid groups by pack_name. Each card: real vendor logo banner + pack/dataset summary + 'All installed' / 'Some installed' status icon. Click to expand the dataset list inline — Install buttons per dataset.",
      "Catalog endpoint overlays installed-state server-side. The UI never has to merge two API responses to know which rows are already installed — the catalog row carries `installed: true/false` directly.",
      "Search filter + 'include rawlog-only' toggle. Stats line shows 'N packs scanned · M rules · K structured · L rawlog-only' so operators see the discovery scope.",
      "Per-row Install spinner. Clicking Install on one dataset only spins that row — other rows stay clickable.",
    ],
  },
  {
    version: "0.7.8",
    date: "2026-05-21",
    title:
      "Phase 3 of the v0.8.0 Marketplace Data Sources arc opens with the new /data-sources page. Operator can now see installed vendor schemas as logo-banner cards, install by Pack + Rule name, uninstall with cascade-aware confirm, and drill into a per-data-source detail drawer with the full field table. Sidebar entry under Integration. Browse drill-down lands next.",
    highlights: [
      "New /data-sources page (570 lines) — h-screen + max-w-[1400px] cohesion pattern matching skills/knowledge/approvals. Material 'schema' icon header.",
      "Installed grid: 1/2/3-column responsive cards. Real vendor logos served through Phantom when present (FortiGate SVG renders inline). Status chip distinguishes structured ('N vendor fields') from rawlog-only packs.",
      "Detail drawer: 4-tile stat grid + field table sorted meta-first / vendor-second / alphabetical within group. `[]` suffix for array fields. Tag column makes the meta vs vendor distinction visible at a glance.",
      "Install form: Pack name + Rule name (required) + Dataset name (optional). Server-side extraction runs in the same call (Phase 2 contract). Spinner during install, success banner with field-count summary on completion.",
      "Sidebar entry under Integration (between Connectors and Approvals). 'schema' icon. Per operator decision #2 — separate top-level page rather than a tab inside /connectors, because vendor schemas are a different concept from per-instance connector containers.",
      "Bridges the gap until v0.7.9 drill-down: empty-state copy tells the operator to use cortex_search_packs + cortex_list_modeling_rules in chat to discover Pack/Rule names, then type them into the install form.",
    ],
  },
  {
    version: "0.7.7",
    date: "2026-05-21",
    title:
      "Phase 2 of the v0.8.0 Marketplace Data Sources arc completes here. 5 REST endpoints + 3 agent-callable MCP tools + 4 Next.js proxy routes land on top of last commit's storage layer. Operators (or the agent via chat) can now install/list/uninstall vendor schemas — extraction runs server-side, no two-step round-trip required from the UI. 403 tests pass; 17 new.",
    highlights: [
      "Five REST endpoints at /api/v1/data-sources: list (with case-insensitive filter), get one, get one + full schema, install, uninstall. Composite paths use literal slashes (FortiGate/FortiGate_1_3/fortinet_fortigate_raw) — one-to-one with how the operator describes a data source.",
      "Three agent-callable MCP tools: data_sources_list, data_sources_get_schema, data_sources_install. Agent can now respond to 'install the FortiGate data source' by extracting from Cortex content + persisting + recording an audit event in one tool call.",
      "Server-side install flow: POST /install with {pack_name, rule_name} only. The handler dynamically loads the cortex-content connector's public functions (cortex_extract_vendor_schema + cortex_extract_vendor_logo + pack_metadata read) inline, composes the DataSource, and persists. No need for the UI to call the extraction tool first.",
      "Four Next.js proxy routes under app/api/agent/data-sources/* mirror the MCP routes — cookie-auth gate + bearer forwarding. Browser-facing UI in Phase 3 will read/write through these.",
      "Catalog-boundary discipline preserved: per CLAUDE.md § Catalog boundary, data source install state is platform metadata not a secret, so the three new MCP tools ARE agent-callable. Same authority as marketplace_install.",
      "Cross-module singleton lesson worth a code comment: Python caches modules by import name, so 'from src.usecase.X' and 'from usecase.X' create two separate module instances with independent _singleton state. The first test run had 14/17 failures with 'store not initialized' until imports were aligned with production code's 'from usecase.X' (no src. prefix).",
    ],
  },
  {
    version: "0.7.6",
    date: "2026-05-21",
    title:
      "Phase 2 storage layer for the v0.8.0 Marketplace Data Sources arc. New SQLite store data_sources.db with three tables (data_sources / data_source_fields / data_source_xdm_mappings) lands the persistence foundation that the next commit's REST + MCP tool layer will sit on top of. 24 new unit tests pass; 386 total. No UI changes; no agent-visible behavior change yet.",
    highlights: [
      "New SQLite store at /app/data/data_sources.db. Composite ID = <pack>/<rule>/<dataset> — human-readable, deterministic, matches the natural-key the operator uses when describing a data source.",
      "Decoupled from marketplace_store.db on purpose: an operator can uninstall a data source without uninstalling the cortex-content connector that powered its discovery. Different lifecycle, different domain, separate file.",
      "Foreign-key cascade on data_source_fields + data_source_xdm_mappings — deleting a data source drops all dependents in one DELETE, no manual cleanup. Verified by unit test that re-installs with no fields after a previous install with 11 fields + confirms the expanded view has zero stale rows.",
      "Pin/unpin support (is_pinned + pinned_version columns) — operator can pin a data source to a specific pack_version to suppress the Phase 3 UI's update-available prompt. Unpinning clears pinned_version so you never see a stale version-pointing-to-nothing.",
      "Catalog-boundary discipline: this store IS agent-mutable via the upcoming v0.7.7 MCP tools (data_sources_install / data_sources_uninstall). Per CLAUDE.md § Catalog boundary ≠ credential boundary, vendor-schema install state is platform metadata not a secret.",
      "Mid-arc commit per release-readiness gate. No customer v0.8.0 tag fires until arc completion at Phase 4. Build + auto-deploy run automatically; smoke runs against the auto-deployed install.",
    ],
  },
  {
    version: "0.7.5",
    date: "2026-05-21",
    title:
      "Phase 1 of the v0.8.0 Marketplace Data Sources arc — three new extraction tools that turn Cortex ModelingRule schema.json files into the raw vendor field inventory Phantom will use to generate vendor-faithful simulated logs. Foundation only; no UI yet, no operator-visible behavior change yet. Prerequisite for Phases 2-4 (data source store + REST + marketplace UI + xlog dynamic schema + skill integration).",
    highlights: [
      "Three new MCP tools on the cortex-content connector: cortex_extract_vendor_schema (one rule → field inventory with per-dataset structured/rawlog-only flag), cortex_extract_vendor_logo (canonical vendor logo URL with SVG → PNG → Author_image.png search order), cortex_extract_vendor_catalog (walks all 217 modeling rules across the content repo + summarises into marketplace-ready rows).",
      "The pre-build research win: every Cortex ModelingRule already ships a _schema.json describing its expected field inventory. That JSON is exactly the inverse function we want — read it directly instead of parsing the .xif XQL. Cut Phase 1 estimate from 1+ week to 2-3 days.",
      "Operator's 6 design decisions captured in docs/DESIGN-marketplace-data-sources.md: 'Data Sources' naming, separate sidebar page (not under /connectors), drill-down vendor → product → data source, actual vendor logos from the packs (not generated SVG), manual update only, XSIAM-tagged packs only, Rosetta as fallback when no Data Source installed.",
      "Coverage classification: of 217 ModelingRules, 92 XSIAM-tagged packs are 'structured' (explicit vendor fields like srcip, dstip — directly usable in Phase 1) and 71 are 'rawlog-only' (extract via regex from _raw_log — deferred to Phase 1.5). The new is_rawlog_only flag surfaces this so the marketplace UI can display the gap.",
      "21 new unit tests passing on first run (362 total in the pytest suite, up from 341). Tests cover structured packs, rawlog-only packs, multi-dataset packs, legacy string-typed schemas, malformed entries, missing schema.json, SVG-vs-PNG logo precedence, Author_image.png fallback, multi-integration logo discovery, xsiam_only filter, include_rawlog filter, pack_limit cap, and the full marketplace row shape.",
      "Mid-arc commit per CLAUDE.md release-readiness gate: NO customer release tag fires for v0.7.5 — the v0.8.0 tag waits for arc completion (Phase 4). Build + auto-deploy on phantom-vm run automatically; smoke runs against the auto-deployed install.",
    ],
  },
  {
    version: "0.7.4",
    date: "2026-05-21",
    title:
      "Login-page hero image (myrobo.webp) re-encoded from q=100 (lossless, 1.6 MB) to q=82 (172 KB) — 9.5× reduction. PSNR 44.5 dB (well above 40 dB threshold for human-imperceptible difference). Full 1365×2048 dimensions retained. Faster first-paint on every login.",
    highlights: [
      "myrobo.webp: 1665 KB → 173 KB (saves 1.49 MB per login render). The original was over-spec'd at q=100 lossless; q=82 is the standard sweet spot for hero photography.",
      "Added .dockerignore (was missing) so the rollback backup at .image-backups/ doesn't bundle into the docker image and undo the savings. Side benefit: also excludes node_modules + .next from the build context.",
      "Rollback safety: original kept at mcp/agent/.image-backups/myrobo-v0.7.3-original.webp (local-only, gitignored). Restore with `cp .image-backups/myrobo-v0.7.3-original.webp public/img/myrobo.webp`.",
      "PSNR comparison across q=80/82/85/88/90 showed an encoder mode-switch around q=83 — q=82 captures the cliff (size jumps from 172 KB to 283 KB between q=82 and q=85 for only 0.7 dB more quality). This is the natural local minimum of bytes-per-quality-unit.",
      "Login is the first surface every operator sees; cutting the hero image to 173 KB pulls LCP (Largest Contentful Paint) into the snappy range even on constrained networks. First impression of 'fast' or 'slow' forms here.",
    ],
  },
  {
    version: "0.7.3",
    date: "2026-05-21",
    title:
      "UI cohesion follow-up — fix the 2 pages the v0.7.2 pass missed. /jobs and /help/journeys were using max-w-7xl (1280px) while every other standardized page uses max-w-[1400px]. On wide screens the 120px-narrower content showed up as visibly more side padding, breaking the cohesion. Single-line fix per file.",
    highlights: [
      "/jobs page: max-w-7xl → max-w-[1400px] (matches /skills /memory /knowledge /connectors and the 14 pages v0.7.2 standardized).",
      "/help/journeys page: max-w-7xl → max-w-[1400px] (same fix). Operator-friendly cohesion now consistent across all 17 main operator pages.",
      "No functional changes — purely layout cohesion. Pre-deploy gate: tsc + lint + build + pytest 341 tests all green.",
    ],
  },
  {
    version: "0.7.2",
    date: "2026-05-21",
    title:
      "UI cohesion pass — 15 pages standardized to the skills-page layout pattern (max-w-1400 / px-8 / single-line subtitle / icon + title). Settings/personality breadcrumb removed. Critical CSS fix: .input-base class was referenced but undefined, leaving agents + hooks form inputs invisible against the dark panel background.",
    highlights: [
      "15 pages refit to the skills-page layout pattern: /agents · /tasks · /plugins · /approvals · /api-keys · /models · /observability/{detections,connectors,logs,runtime-events} · /settings/{hooks,personality,backup-restore} · /help · /knowledge.",
      "Standardized: h-screen overflow-y-auto outer + max-w-[1400px] mx-auto px-8 py-8 inner + icon+title+single-line-subtitle header. Skills/memory/knowledge/connectors visual rhythm now uniform across the operator-facing surface.",
      "Settings/personality: dropped \"Settings / Personality\" breadcrumb (no other settings/* page had one), swapped PhantomLogo box for the standard psychology material icon.",
      "Observability/detections: converted from inline `style={{padding,maxWidth,margin}}` to Tailwind + added the radar icon. Was previously the only observability sub-page without an icon.",
      "Settings/backup-restore: was max-w-3xl (768px — looked lost on wide screens), bumped to max-w-[1400px] + added backup icon. Now matches the other settings pages.",
      "Critical CSS fix — .input-base class was referenced by 20+ form inputs across /agents and /settings/hooks but never DEFINED. Operator audit: \"agents creation form is one color window with no text fields\" — inputs were in the DOM but transparent against the dark panel. Defined the class globally with theme-aware bg/border/focus.",
      "No functional changes — purely layout cohesion. Chat page deliberately unchanged (full-width is correct for chat).",
    ],
  },
  {
    version: "0.7.1",
    date: "2026-05-21",
    title:
      "Overnight quality pass: extensive smoke of every capability surface (49 UI pages / 86 API routes / 81 MCP tools / 20 skills / 787 KB entries / 109 journeys), 12 doc-quality commits fixing real gaps found, 2 new architecture diagrams (Jobs + Skills subsystems), 2 follow-up issues filed for v0.7.x. No code-level breaking changes; pure quality + docs sync + visual architecture.",
    highlights: [
      "2 new component diagrams in /help/architecture: Jobs subsystem (5-layer fan-in→dispatch→fan-out) + Skills subsystem (source→seed→catalog→activation pipeline). Joins the existing 9 diagrams (chat/memory/knowledge/topology/auth/etc.) for full visual coverage.",
      "API documentation completeness: lib/api-catalog.ts expanded 43 → 112 entries to cover all 86 filesystem routes. Every endpoint now appears in /help/api + OpenAPI 3.0 export (try-it-out form reveals actual response shapes).",
      "Architecture page coverage: 4 new connector sections added (Cortex XDR, Cortex Docs, Cortex Content, Web Browser) with TOC entries. Previously only xlog/CALDERA/XSIAM had dedicated sections; the 4 newer connectors had ≤2 mentions.",
      "/help/cicd now linked from /help index (was operator-discoverable only by typing the URL). Specialty references grid now lists User Journeys + REST API Reference + CI/CD Guide.",
      "/help/journeys: 109 journeys' API references bulk-renamed from /api/v1/* (MCP-internal, ECONNREFUSED for operators) to /api/agent/* (operator-callable). New v0.7.0-capability journey 'xdr-discover-datasets-and-query-v070' walks the full discover→search→query chain. Closes #69.",
      "/help/user knowledge section: corrected 'xql-examples KB has 161 entries' → '787 entries (v0.7.0 expanded from 629)'. Added 'How the agent uses the KB' subsection describing the 4-step chain.",
      "Smoke matrix: 5/5 v0.7.0 bullets GREEN end-to-end · 10/10 KB search probes find v0.7.0 entries top-3 · 49/49 UI pages 200 · chat lifecycle GREEN · 8/8 deep mutation surfaces validated (memory CRUD, hooks CRUD, operator-state KV, notifications, personality, settings, backup auth, KB consistency).",
      "Filed: #68 (phantom-updater missing-container auto-spawn) · #69 (journeys API paths — fixed inline) · stale count cleanups (4→5 services, 3→7 connectors, 11→20 skills, 161→787 KB entries across system-prompt + 4 help files).",
    ],
  },
  {
    version: "0.7.0",
    date: "2026-05-20",
    title:
      "158 new hand-curated + live-tenant-validated XQL examples added to the knowledge base (629 → 787 entries, 25% expansion). Each entry POSTed to xdr_run_xql_query against operator's tenant and confirmed SUCCESS before being written. The 158 includes a 26-entry complex-queries subset designed from official Cortex XQL docs showcasing advanced stages (iploc, search, replacenull, transaction, view) + functions (json_extract_array, format_string, replace, extract_time, ip_to_int, window-comp rank/lag/first_value/last_value, median/list/earliest/latest). New xdr_list_datasets connector tool empirically enumerates available datasets. Validated alerts vs issues as PARALLEL datasets (not rename) — both 2855 rows in 30d, different schemas (flat vs XDM).",
    highlights: [
      "158 new XQL examples (629 → 787 entries) spanning 12 datasets. Coverage of ~35 XQL stages + 30+ functions across simple-to-complex queries.",
      "MITRE ATT&CK coverage across 16+ techniques: T1003 (Mimikatz/LSASS), T1018/T1046 (discovery), T1027 (base64 obfuscation), T1036 (masquerading), T1053 (scheduled tasks), T1059 (PowerShell encoded), T1071.004 (DNS tunneling), T1078 (valid accounts), T1098 (IAM), T1110 (brute force), T1218 (LOLBins), T1543 (services), T1546 (WMI), T1547 (autorun persistence), T1566.001 (Office spearphishing).",
      "New xdr_list_datasets tool: empirically probes 20+ well-known dataset names with `dataset = X | limit 1` + reports which exist in THIS tenant. Works on every XDR tier (XSIAM-license-gated datamodel stage is bypassed). ~30-60s wall time.",
      "alerts vs issues clarified — PARALLEL datasets with the same 2855-row 30d data, different schemas: alerts (flat: alert_id, alert_name, severity, mitre_attack_tactic) vs issues (XDM: xdm.issue.name, xdm.issue.severity, xdm.issue.mitre_tactics). KB now ships queries for both schemas.",
      "Schema-discovery findings recorded for future-tenant query authoring: mitre_attack_tactic is scalar (not array), incidents mitre_tactics_id_and_name IS array, va_cves.os_type is array, endpoints.tags is JSON-string (use json_extract_array), endpoint_isolated is string not bool, xdr_data.event_id is base64 (not Windows event code).",
      "Validation pipeline (build_100_queries.py + build_complex_queries.py + 4 fix-up passes) is reusable: 175 templates → 158 SUCCESS (90% survival rate after schema-correction + syntax-correction passes). XQL dialect findings: join uses `as alias left = alias.right` (no `on` keyword); transaction stage caps at 50 fields per row (project first); date_floor 2nd arg is timezone not unit (use format_timestamp); search stage must come AFTER dataset.",
      "26 complex queries showcase advanced XQL: iploc adds loc_country/loc_city/loc_region columns from action_remote_ip; ip_to_int enables numerical IP sort; format_string for printf-like output; extract_time for hour-of-day patterns; to_epoch + math for time arithmetic; window functions rank()/lag()/first_value()/last_value() for per-host top-N + delta detection; aggregation variants median/list/earliest/latest; stages replacenull/search/transaction/view.",
    ],
  },
  {
    version: "0.6.68",
    date: "2026-05-20",
    title:
      "5 new tenant-tailored probe scenarios designed against operator's actual XDR data (discovered via direct xdr_run_xql_query, not assumed). Probe 33/33 GREEN across 10 categories. 3/5 hit real data on first try; 2/5 surfaced KB-curation gaps for alert-centric queries.",
    highlights: [
      "Discovery: 6 active hosts (3 AKS K8s + ubuntu + 2 Windows xdragent), 3M+ PROCESS events dominated by AKS Linux scripts, real outbound bytes on xdragent (367k/24h), 909 HIGH+CRITICAL alerts in 7d including Mimikatz on xdragent boxes + CVE-2025-68121 on AKS.",
      "Schema gotcha discovered: `event_sub_type` field can't be queried without filtering `event_type` first (XDR's parser requires event_type in schema). LOGIN events for this tenant only accessible via PRESET (`preset = xdr_login_events` / `preset = authentication_story`), not via `dataset = xdr_data | filter event_type = ENUM.LOGIN`.",
      "3/5 prompts hit real data: CVE alerts (1000 rows), xdragent uploads (10 rows top-10), endpoint inventory (13 rows). Mechanics + semantic + data all aligned.",
      "2/5 surfaced KB-curation gaps: credential-dumping prompt picked LSASS process-event query instead of `dataset = alerts` query (0 rows). Severity-count prompt picked a 'broken_widgets' KB entry instead of clean `dataset = alerts | comp count() by severity`.",
      "These are content gaps in the KB, not skill-prompt gaps. Real chat LLM has top-5 matches + `## When to use` text and can correct via synthesis. Probe runs verbatim so can't simulate. Fix path: operator-driven curation pass adding alert-centric examples (future v0.7.x).",
      "No code changes in v0.6.68 — purely test-suite expansion. Probe is now the autonomous regression baseline for the XQL skill capability against this tenant.",
    ],
  },
  {
    version: "0.6.67",
    date: "2026-05-20",
    title:
      "Two fixes from operator session c9c97258. (1) Chat turns now ENABLE Gemini thinking BY DEFAULT — pre-v0.6.67 the chat UI never triggered the extended-reasoning path because `thinking` defaulted to false. Operator's 'agent feels fast' intuition was correct: Gemini 3.1 Pro was running base-model mode. (2) Skill prompt teaches config timeframe = Nd explicitly — agent had written manual epoch math (subtract(current_time(), 259200000)) instead of canonical config timeframe = 3d.",
    highlights: [
      "Thinking-default flip: turnThinking = requestedThinking !== false (was === true). Unset/chat-UI requests now get thinking ON; scheduler-passed thinking:false still disables. callGemini sets thinkingConfig.thinkingBudget = -1 ('use what you need') + includeThoughts = true.",
      "Cost impact bounded: ~28k cached input tokens per turn in session c9c97258 means marginal cost of thinking is the output-side reasoning tokens (~$0.02-0.05/turn). Total chat-session cost up ~10-20% in exchange for materially better synthesis quality.",
      "Skill prompt Step 7 gains the full XQL time-suffix vocabulary table (MS/S/M/H/D/W/MO/Y) + memorize-this common-shapes list (last hour → 1h, last 3 days → 3d, last week → 7d, etc.) + an explicit FORBIDDEN anti-pattern for manual epoch math.",
      "Skill prompt Step 4 adds `config` to the mandatory cortex_xql_lookup terms when the user's question implies a time window. The `config timeframe = ...` stage is canonical XQL but under-represented in KB matches because operators inherit it ambiently.",
      "Operator's third concern (some test prompts not relevant to current XDR data) was a test-prompt-design issue, not a release: ran data discovery, found tenant has AKS + Windows xdragent boxes with NETWORK-heavy telemetry. Future prompts target this shape.",
    ],
  },
  {
    version: "0.6.66",
    date: "2026-05-20",
    title:
      "phantom-updater auto-reconciles per-instance connector containers whose running image digest drifts from the pinned digest. Closes the 'stale connector container' gap — session 26a7fdd3's cortex-xdr was 17h old running v0.6.55 code while the agent was 4 min old on v0.6.63. Fires automatically on phantom-updater startup + exposed as POST /api/v1/connectors/reconcile/digests.",
    highlights: [
      "Why this matters: per-instance connector containers (cortex-xdr, cortex-docs, caldera) are spawned by phantom-updater at instance-create time, then STICK AROUND across dev-cycle deploys because they're not in docker-compose.yml. Every install updates /host/connector-digests.env with new digests but the running containers keep their original image. Operator chat tests then exercise STALE connector code while the agent is current.",
      "_reconcile_connector_digest_drift() walks every running per-instance container, compares running RepoDigest vs pinned digest from /host/connector-digests.env, and recreates drifted ones via the existing start_connector_instance endpoint (stop+remove+pull+spawn+agent-callback as one atomic op).",
      "Lifespan startup schedules the reconcile as a background task ~30s after phantom-updater starts (delay covers agent boot, since the recreate calls back to the agent for container_url). Fire-and-forget — /healthz stays responsive, docker-compose healthcheck doesn't cascade-fail.",
      "Manual trigger: POST /api/v1/connectors/reconcile/digests returns {drifted, recreated, unchanged, failed} arrays. Operators call this when they notice a connector running stale code (behavior doesn't match recent release notes).",
      "Picked the phantom-updater-hook layer (not workflow patch, not installer patch) because phantom-updater IS the component responsible for connector lifecycle. It restarts on every install (docker-compose recreates it when its image digest changes), so the new hook fires automatically on every install — customer AND dev.",
      "Safety: only recreates when running digest ≠ pinned. Matched containers skip. Errors per-container logged but don't abort the loop. Skips locally-built dev images (no registry digest) + containers without INSTANCE_ID label.",
    ],
  },
  {
    version: "0.6.65",
    date: "2026-05-20",
    title:
      "Three defensive tool-layer fixes triggered by operator session 26a7fdd3 ($10.42 across 5 prompts, 60 XDR calls, 42% first-try success). v0.6.63's prompt-level mandates bent under pressure; v0.6.65 makes the wrong-shape calls physically reject with self-routing error messages. (1) timeframe arg rejects relative-time strings like '24h' with Pattern-F-aware error pointing to `config timeframe = 24h`. (2) XDR 'unknown field' responses get auto-suggested canonical names from a 40-entry alias map (bytes_sent → action_total_upload, timestamp → _time, etc.). (3) chat route enforces a 3-iteration cap on consecutive xdr_run_xql_query failures by injecting a STOP directive.",
    highlights: [
      "Session 26a7fdd3 evidence: prompt 4 (data exfil + ASN baseline) burned 18 retries thrashing through field name variants (bytes_sent, action_bytes_sent, action_network_bytes, action_pkts_sent, ...) before hitting the tool budget + giving up. With v0.6.65 the first 'unknown field bytes_sent' response carries `field_suggestions: ['action_total_upload', 'action_total_bytes_sent']` + LLM substitutes correctly on iteration 2.",
      "Fix 1 (Pattern F at tool layer): _iso_to_ms regex matches ^\\d+\\s*(ms|mo|[smhdwy])$ (case-insensitive) and raises a self-documenting ValueError. Pre-v0.6.65: cryptic 'Invalid isoformat string' → multiple guess-retries. Post-v0.6.65: error message IS the recipe → 1-iteration recovery.",
      "Fix 2 (alias map): 40-entry static map of LLM-confusion guesses → canonical XDR names across bytes/time/host/process/user/file/network categories. Plus heuristic suffix fallback for unmapped guesses. fix_hint also routes to cortex_search as the safety net.",
      "Fix 3 (3-iter cap binding): chat route counts consecutive xdr_run_xql_query failures; after 3, injects a __system_stop_directive__ functionResponse with explicit STOP message + summarize-to-operator directive. Counter resets on any SUCCESS so multi-stage skill chains (incident pivot etc.) are unaffected.",
      "What's NOT in v0.6.65: expanding the alias map (40 entries covers the observed cases; future sessions surface more), connector-to-connector auto-call of cortex_search (the fix_hint just routes the LLM to call it), tool-layer Pattern G/H rejects (windowcomp ordering, C-style arithmetic — covered by skill prompt + didn't trip in session 26a7fdd3), skills_read auto-load middleware.",
    ],
  },
  {
    version: "0.6.64",
    date: "2026-05-20",
    title:
      "Phase 3 probe extended with 10 complex SOC analyst prompts across 4 new sub-categories (stats, correlation, hunting, conditional). 28/28 GREEN on chain mechanics against deployed v0.6.63. KB-coverage stratifies: 3 prompts have direct templates (>0.70 score), 5 have related patterns (0.65-0.70), 2 reveal KB gaps (<0.65) in percentile statistics + conditional categorization.",
    highlights: [
      "10 new probe scenarios from the 'complex query prompts' list shared with the operator at v0.6.62: stats (timeline anomaly, failed-login-rate threshold, 99th percentile, rare DLLs, >3σ baseline), correlation (outbound-after-failed-auth, lateral-movement SMB), hunting (T1059.001 PowerShell, T1003.001 LSASS), conditional (endpoint tier categorization).",
      "Strong coverage (>0.70 score, direct KB templates): T1003.001 LSASS (XQL-525, 0.782), T1059.001 PowerShell (XQL-585, 0.709), failed-login-rate (XQL-193, 0.708).",
      "Decent coverage (0.65-0.70, related patterns the LLM must adapt): rare DLLs (0.696), >3σ failed-auth (0.685), lateral-movement SMB (0.677), outbound-after-failed-auth (0.669), per-hour process anomaly (0.668). v0.6.63's named error patterns (F/G/H) become important here.",
      "KB gaps (<0.65, operator-curation opportunity): 99th percentile (0.645 — KB has no percentile examples), endpoint tiering (0.638 — KB has no case/if conditional examples). Good targets for a future v0.7.x KB curation pass.",
      "Important caveat: probe verifies chain MECHANICS (KB returns matches → top-1 executes), NOT synthesis quality. For complex prompts the top-1 is often a simpler version. 28/28 GREEN tells us the substrate works; the LLM's ability to stitch multiple matches + cortex_xql_lookup into multi-stage synthesis is the question only chat tests answer.",
      "Operator next step: chat-test any of the 10 prompts + verify (a) skills_read({file_path: 'workflows/build_xql_query.md'}) is the FIRST tool call (v0.6.63 mandate), (b) knowledge_search is second, (c) the synthesized query reflects the prompt's full complexity.",
    ],
  },
  {
    version: "0.6.63",
    date: "2026-05-20",
    title:
      "Critical fix — build_xql_query skill is now actually loaded by the agent for XQL questions. Operator chat session 17b598aa caught the skill being silently bypassed: LLM saw it in <available_skills> metadata but never called skills_read, so the 7-step procedure never ran. Result: 5 wasted XDR syntax-error iterations on a complex query, ~$0.43 cost vs ~$0.10 if KB-first synthesis had fired.",
    highlights: [
      "Three coupled fixes at three layers so the skip-skill regression can't recur: (1) new SKILL-ROUTING block in system-prompt.ts mandates skills_read({file_path: 'workflows/build_xql_query.md'}) for XQL-relevant requests BEFORE any cortex_xql_lookup / knowledge_search / xdr_run_xql_query. (2) Skill frontmatter description rewritten as a load-first directive (the description is what surfaces to the LLM). (3) Step 1 itself strengthened to mandatory-language matching Step 4's v0.6.56 treatment.",
      "Plus 3 new error patterns to the iteration loop, each pulled from session 17b598aa: Pattern F (Invalid isoformat — wrong arg for timeframe_from), Pattern G (windowcomp by/as clause ordering confusion), Pattern H (XQL doesn't accept C-style arithmetic — must use add/subtract/multiply/divide functions).",
      "Plus a Critical timeframe-arg gotcha in Step 7 explaining when to use config timeframe = 24h in the query body (preferred, 95% of operator examples) vs ISO datetimes in the function args (only when the user named an absolute window).",
      "Real failure-mode story baked into the skill description AND the system-prompt routing block: session 17b598aa named explicitly so the LLM has a concrete cost-of-skipping signal ('~$0.43 in retries that should have cost ~$0.10').",
      "What's NOT in v0.6.63: code-level skill-resolution middleware (deferred — prompt-level routing should be sufficient), the 10 complex-prompt smoke test (v0.6.64 ships that as the next autonomous-loop iteration).",
    ],
  },
  {
    version: "0.6.62",
    date: "2026-05-20",
    title:
      "Autonomous Phase-3 smoke-test loop closes at 18/18 GREEN across 5 categories (investigation, aggregation, time-bounded, composite, edge-case). Two-iteration close: v0.6.61 (skill prompt) + v0.6.62 (widened tenant-universal dataset set to include XSIAM's built-in `alerts` + `issues`). The XQL skill capability is now operator-verifiable end-to-end across 18 diverse query scenarios.",
    highlights: [
      "Probe sequence: run 1 (v0.6.60 baseline) 11G/5Y/2R; run 2 (v0.6.61) 17G/0Y/1R; run 3 (v0.6.62) 18G/0Y/0R. The 5 YELLOWs were placeholder-parameter leaks ($host, $domain) closed by v0.6.61. The 2 REDs were tenant-dataset-not-found 500s — 1 closed by v0.6.61's fallback recipe, the last by v0.6.62 widening the universal set.",
      "UNIVERSAL_DATASETS goes from 3 → 5: added `alerts` (XSIAM's built-in alerts dataset) and `issues` (XSIAM's built-in incident dataset). Surfaced empirically — the probe found XQL-083 had `dataset = alerts` as a viable fallback target that the 3-set didn't recognize.",
      "Skill prompt Pattern A recipe text mirrors the wider universal set so the LLM applies the same fallback discipline as the probe. Pre-v0.6.62 listed 3 universals + 1 non-universal; v0.6.62 lists 5 + names 4 vendor-specific sets to avoid (NGFW, microsoft_windows_raw, ServiceNow, Jira).",
      "Two-line Python + one paragraph of prompt text. The architectural work was v0.6.61's introduction of the tenant-universal concept; v0.6.62 is empirical follow-up — measure which datasets the chain identifies in practice, fix the gap the measurement surfaced.",
      "The autonomous loop the operator asked for: build → deploy → test → measure → fix the gap → re-test → confirm. Closed in 2 iterations (v0.6.61 → v0.6.62). The XQL skill capability arc shipped at v0.6.55 customer release; v0.6.56-v0.6.62 are dev-cycle iterations strengthening the capability against real XDR.",
    ],
  },
  {
    version: "0.6.61",
    date: "2026-05-20",
    title:
      "build_xql_query skill gains parameter-placeholder handling + tenant-fallback recipes for 5 XDR error patterns. Surfaced by the autonomous Phase-3 probe (18 diverse scenarios, 5 categories) — current baseline 11 GREEN / 5 YELLOW / 2 RED. The 5 YELLOWs were all parameter-placeholder leaks ($host, $domain); 2 REDs were tenant-dataset-not-found 500s. v0.6.61 closes both gaps in the skill prompt.",
    highlights: [
      "Phase-3 probe at bundles/spark/kbs/xql-examples/_tools/phase3_probe.py — extends the v0.6.54 retrieval probe with actual xdr_run_xql_query execution. 18 scenarios across investigation, aggregation, time-bounded, composite, edge-case. Per-query verdict GREEN/YELLOW/RED + categorized summary + fix queue.",
      "Skill section 5.5 (NEW + MANDATORY): parameter-placeholder handling. Pre-v0.6.61 the skill had no instructions for $host/$domain/etc. — operator's KB examples carry XSIAM saved-query parameters that fail when passed literal to XDR. v0.6.61 instructs the LLM to either drop the parameterized filter line (user's question broader than example's scope) or substitute the placeholder with a concrete value the user implied.",
      "Iteration loop replaces the generic 'read error → adjust → retry' with 5 named patterns + per-pattern recipes: (A) HTTP 500 / dataset-not-found → fall back to tenant-universal datasets (xdr_data, xdr_login_events, endpoints) or STOP + report missing connector; (B) field-not-found → cortex_search the canonical name; (C) unknown function → re-run cortex_xql_lookup for aliases; (D) arity mismatch → trim optional args; (E) parameter leaked through → back to Step 5.5.",
      "First iteration of the autonomous loop. Next iteration: re-run phase3_probe.py against v0.6.61's deployed install, expect the 5 YELLOWs to potentially convert to GREEN if the chain handles parameters cleanly via the new prompt sections.",
      "What's NOT in v0.6.61: code-level parameter-detection helper (deferred until we see a real LLM mis-handle), xdr_list_datasets MCP tool (cortex-xdr connector enhancement, future).",
    ],
  },
  {
    version: "0.6.60",
    date: "2026-05-20",
    title:
      "Unified event export (schema v2). Session 'Export Events' now includes both persisted messages AND chat_* audit-log events (cache_hit, turn_cost, compaction_*, subagent_*). Closes the dual-button confusion. Closes the last carry-over from v0.6.55 chat test — all 11 operator-feedback items now landed across v0.6.56-v0.6.60.",
    highlights: [
      "Discovered while implementing: the chat route ALREADY persists most wire events to audit_log via safeAudit() — they just weren't surfaced in the export. So the fix was a server-side merge, not the bigger refactor I feared.",
      "10 audit action names map to friendly wire-event types in the export: chat_turn_cost → turn_cost, chat_cache_hit → cache_hit, chat_compaction_{start,end,failed}, chat_context_warning, chat_plan_proposed, chat_plan_failed, chat_subagent_started, chat_subagent_completed. Each event carries the original metadata so the operator can post-process (per-session cost = sum(turn_cost.metadata.cost_usd)).",
      "Schema bumps to version 2. Old consumers pinned on v1 see the change and can re-validate. New payload fields: messages_derived_count, audit_derived_count.",
      "Only intentional exclusion: text_delta (per-token deltas would inflate row count 100× per turn). For per-token forensics use the live-telemetry-panel export.",
      "Tooltips updated: session sidebar 'Export Events' positioned as the post-hoc-friendly path covering everything; live-telemetry export narrowed to 'per-token streaming forensics only'.",
      "Live-telemetry export button stays — initial v0.6.57 plan was removal (operator's original ask), but it still captures text_delta + control events (model, meta, done) we don't audit. Keeping the button + sharpening its tooltip beats removing it and finding out later we lost a useful capability.",
      "Arc closure: 11 feedback items from the operator's first v0.6.55 chat test now all landed across v0.6.56-v0.6.60. Pending only: next behavioral chat test to verify v0.6.56's mandatory cortex_xql_lookup step fires in practice.",
    ],
  },
  {
    version: "0.6.59",
    date: "2026-05-20",
    title:
      "Shared markdown renderer + SQL/XQL syntax highlighting in KB drawer + chat assistant message bubbles. Model-returned markdown (headings, code blocks, tables, lists) now renders properly in chat instead of raw whitespace-pre-wrap text. Operator: 'presenting MD data in the chat session nicely in case the model returned md data'.",
    highlights: [
      "New shared MarkdownContent component at components/markdown-content.tsx centralizes all v0.6.58 overrides + adds SQL/XQL syntax highlighting via react-syntax-highlighter's PrismLight bundle. Languages registered today: sql, xql (sql dialect), python, bash, json, typescript. Adding more = one-line import per language.",
      "KB entry drawer: collapses v0.6.58's 100+ lines of inline overrides to a single <MarkdownContent> call. SQL code blocks now have keyword color tinting (dataset, filter, fields, comp etc. in semantic colors).",
      "Chat assistant message bubble: pre-v0.6.59 rendered the answer as plain whitespace-pre-wrap text. v0.6.55 chat-test transcript showed the model returning a markdown table for endpoint query results — table rendered as pipe characters in a paragraph. v0.6.59 renders proper tables with borders + headings.",
      "Streaming preserves cursor position. During a partial answer (mid-fence ```sql with no closing ``` yet), markdown renders gracefully as plain text until the closing arrives, then re-renders as a highlighted block. No flickering.",
      "Three operator-facing wins: (1) synthesized XQL queries pop visually from surrounding narration, (2) tool result tables render as real tables, (3) bulleted lists and ### sub-headings surface the model's reasoning structure that was lost in pre-v0.6.59 flat rendering.",
      "Bundle cost: ~80KB gzipped JS increase. PrismLight variant + manual language registration keeps it tight — full Prism would be ~250KB.",
      "What's NOT in v0.6.59: unified event export (deferred to v0.6.60 — bigger refactor requiring server-side persistence of streaming events). Behavioral re-verification of v0.6.56's mandatory cortex_xql_lookup step (pending operator's next chat-test).",
    ],
  },
  {
    version: "0.6.58",
    date: "2026-05-20",
    title:
      "Knowledge base pages get a visual lift to match /skills polish. Entry detail drawer renders markdown properly (primary-tint code blocks, tertiary-tint inline code, structured headings) instead of all-monochrome <pre>. Dev-facing notes about 'Tier-3 runtime CRUD' and 'spec patch pending' replaced with operator-language one-liners.",
    highlights: [
      "Entry detail drawer wires ReactMarkdown with custom component overrides. # → bordered headline; ## → primary-tint uppercase section labels (WHEN TO USE, VARIATIONS, SOURCE); ``` ```sql ``` ``` → primary-tint backdrop with border; inline `comp` `xdr_data` → tertiary-tint pills. Pre-v0.6.58 the whole body rendered as identical monospace white-on-glass — operator's 'all white color text' complaint.",
      "Why this matters beyond aesthetics: the SQL query body was visually indistinguishable from surrounding prose. Operators scanning to find 'what does this query actually do?' had to read paragraph-form. v0.6.58's code-block tint makes the scanning task O(1) — eyes go directly to the SQL block.",
      "KB index page: subtitle changed from dev-doc style ('schema-validated, read-only edit under bundles/spark/kbs/ and redeploy') to operator-language ('Curated reference content the agent uses to ground its responses. Semantically searchable via Gemini text-embedding-004').",
      "KB index footer: 4-line internal-doc paragraph about 'Tier-3 runtime CRUD ... spec patch pending ... source-hash change detection' replaced with single line + lightbulb icon ('To add or edit entries, modify the markdown files under bundles/spark/kbs/ and redeploy. Changes are picked up automatically').",
      "Disabled-tab tooltips (Import / Settings) updated similarly: 'Tier-3 runtime CRUD — not yet implemented (spec patch pending)' → 'Not yet available — to add or change entries, edit the markdown files under bundles/spark/kbs/ and redeploy.'",
      "What's NOT in v0.6.58: syntax highlighting within the SQL code block (deferred — primary-tint backdrop differentiates the block visually but no keyword highlighting). Unified event export (operator may push back; pending feedback).",
    ],
  },
  {
    version: "0.6.57",
    date: "2026-05-20",
    title:
      "Wire events panel: turn_cost + text_delta styled consistently, hover-truncation fixed so long previews wrap inline, both export buttons have honest tooltips clarifying that they capture different data (live-telemetry = streaming events, session-events = persisted database state). Second post-v0.6.55 iteration on operator feedback.",
    highlights: [
      "turn_cost now has the payments icon + tertiary tint (sharing the wallet-relevant cost-signal lane with cache_hit). Pre-v0.6.57: neutral grey pill, no icon, visually inconsistent with cache_hit/tool_call.",
      "text_delta intentionally remains iconless — streams many-per-second, an icon would saturate the column. The decision is now in a code comment so future maintainers don't 'fix' it.",
      "Hover-truncation fix: pre-v0.6.57 used HTML title attribute (browser-native tooltip, slow, OS-truncated). v0.6.57 uses CSS group-hover to expand the row inline with whitespace-pre-wrap break-all overflow-visible. Subtle hover-bg lifts the row above siblings so wrap doesn't collide.",
      "Both export buttons (live-telemetry panel + session-sidebar Events) keep their distinct purposes but get honest tooltips. Live = in-memory streaming events (text_delta, cache_hit, turn_cost, model) that aren't persisted server-side. Session = persisted user/tool/assistant messages from the DB. Operator was right that two buttons is confusing; the right fix is clarity, not deletion (they capture different things).",
      "Unified-export refactor (single button that captures both persisted + streaming events) is deferred to v0.6.58+ pending operator feedback on whether dual-button-with-clear-tooltips is acceptable. Real fix requires server-side persistence of streaming events — bigger refactor.",
    ],
  },
  {
    version: "0.6.56",
    date: "2026-05-20",
    title:
      "build_xql_query skill now enforces Step 4 (cortex_xql_lookup) as MANDATORY. Operator's first chat test on v0.6.55 caught the LLM skipping the documentation-lookup step for a simple query — the synthesized query was right but the chain was incomplete, which would break on more complex queries. Plus: KB search UI text accurately describes the embedding model (was misleadingly labeled 'brute-force cosine').",
    highlights: [
      "First post-tag iteration on the XQL skill capability. Operator chat-test session 4edfe87f showed the agent picked the skill + called knowledge_search + executed via xdr_run_xql_query — but skipped cortex_xql_lookup entirely. Pre-v0.6.56 prompt phrasing said 'top 5 by frequency is plenty' which the LLM read as optional.",
      "New mandatory-lookup contract baked into the skill prompt: at least all stages with frequency ≥ 2/5 across the top-5 matches AND the top 3 most-frequent functions. For a typical query, expect 5-9 cortex_xql_lookup calls before synthesis. <3 lookups means corners were cut.",
      "Audit-trail requirement: the output's Evidence Summary MUST list the lookup calls + outcomes ('Looked up filter (HIT — filter narrows results), comp (HIT — aggregation with as and by), ... 6/6 lookups hit'). Summaries that name KB matches without listing lookups = Step 4 was skipped.",
      "KB search UI text accuracy fix: pre-v0.6.56 said 'brute-force cosine over the SqliteKnowledgeBase' (technically correct — no ANN index — but misleading; operators read it as 'no embedding'). v0.6.56 says 'query embedded via text-embedding-004 · cosine similarity ranked across all entries'. Same speed, accurate description.",
      "What's NOT in v0.6.56: event export completeness (v0.6.57), wire events UI consistency + duplicate export button removal (v0.6.57), KB UI redesign (v0.6.58). Tracked as discrete tasks; autonomous iteration continues.",
    ],
  },
  {
    version: "0.6.55",
    date: "2026-05-20",
    title:
      "build_xql_query skill shipped — Phase 2 of the XQL skill capability arc. Operators ask natural-language SOC questions; the agent returns a working Cortex XQL query with full chain-of-evidence + automatic execution + 3-iteration retry. No new code — pure prompt engineering against the v0.6.51-v0.6.54 retrieval primitives.",
    highlights: [
      "Mid-arc release. Per the v0.6.53 use-case-completion gate, NOT a customer tag candidate. Phase 3 (end-to-end verification across the 5 Phase 1 baseline queries) closes the arc.",
      "Single new file: bundles/spark/mcp/skills/workflows/build_xql_query.md. 7-step procedure: knowledge_search → fetch top-5 bodies → extract stages/functions/dataset → cortex_xql_lookup → optional cortex_search for field schema → synthesize query → xdr_run_xql_query with 3-iteration retry on FAIL.",
      "Design decisions baked into the prompt from Phase 1 measurements: use ALL top-5 examples (narrow 0.60-0.73 score spread), ground in summary_content not title (false-positive prevention for set/preset), 'working' = status:SUCCESS (empty results OK), 3-iteration retry cap, same-dataset clustering when 4/5+ matches agree.",
      "No code changes. Every tool the skill calls already exists: knowledge_search (MCP built-in), cortex_xql_lookup + cortex_search (cortex-docs v0.3.2), xdr_run_xql_query (cortex-xdr). The skill MD ships in the agent image via the existing skills-default copy; per-release marker auto-merges into the running volume on first boot.",
      "Auto-surfaces in /skills under the workflows category. The chat agent's on-demand skill loader picks it up via intent matching. If Phase 3 finds the loader doesn't auto-select for XQL questions, that's a Phase 3 system-prompt tweak.",
    ],
  },
  {
    version: "0.6.54",
    date: "2026-05-20",
    title:
      "Phase 1 of the XQL skill capability arc verified end-to-end: 5/5 representative SOC analyst queries return GREEN through the full retrieval chain (KB similarity → top-5 → stage/function extraction → cortex_xql_lookup). 47/48 unique terms (98%) resolved to authoritative Cortex docs. Probe tool committed for re-runnability + as Phase 2's skill-design basis.",
    highlights: [
      "Mid-arc release for the XQL skill capability (v0.6.51 → v0.6.52 → v0.6.53 → v0.6.54 → v0.6.5N). Per the v0.6.53 use-case-completion gate, this is NOT a tag candidate — only arc completion (when the operator can ask the agent to build + execute an XQL query end-to-end) triggers a customer tag.",
      "Phase 1 probe at bundles/spark/kbs/xql-examples/_tools/retrieval_probe.py — exercises the full retrieval chain against the deployed install. 5 baseline test queries covering network hunting, credential/identity, process anomaly, DNS, and geolocation. Average top-1 KB match score: 0.678; 47/48 cortex_xql_lookup terms resolved to docs.",
      "Two quality observations design Phase 2 around: top-5 score spread is narrow (0.60-0.73), so the skill uses ALL top-5 examples for pattern synthesis (not just top-1). cortex_xql_lookup occasionally returns topic-page hits when an XQL term shares a substring with an unrelated topic (set → 'Set up incident scoring'); the skill grounds in summary_content, not just title.",
      "Wiring fix learned during probe development: tool invocation bypassing the LLM goes through POST /api/agent/tool/call on the agent UI port (3000), NOT the MCP transport endpoint. The route does the JSON-RPC handshake internally and unwraps the envelope. Documented in the probe's module docstring so future probes get the wire-up right.",
      "What's NOT in v0.6.54: the build_xql_query skill itself (Phase 2 → v0.6.55+), the XDR-side test loop (Phase 3 → closes the arc), dataset field-info integration (added with the skill). v0.6.54 stops at retrieval verification.",
    ],
  },
  {
    version: "0.6.53",
    date: "2026-05-20",
    title:
      "kb_loader makes schema-required fields enforcing, not advisory. Pre-v0.6.53, docs missing required id/title/category got upserted with empty metadata + a WARNING log. v0.6.52's smoke caught this as xql-examples doc_count=631 not 629 (README + the v0.6.51 source JSON were leaking in as broken docs). Plus: documents the use-case-completion release gate that this fix exemplifies.",
    highlights: [
      "Part of the XQL skill capability arc (v0.6.51 → v0.6.52 → v0.6.53 → ... → v0.6.5N). Not a standalone tag candidate. Per the new use-case-completion gate (docs/CICD.md + CLAUDE.md), mid-arc commits ship through the dev cycle but customer tags only fire at arc completion.",
      "_validate_against_schema now returns (warnings, missing_required) — split out so the caller can branch on required-field failure without parsing warning strings. Upsert loop honors missing_required: skip the doc + counts['invalid'] += 1 + don't add to seen_doc_ids so the reaper removes previously-loaded copies of now-invalid docs.",
      "4 new tests in bundles/spark/mcp/tests/test_kb_loader.py covering: required enforcement, reaping previously-valid-now-invalid docs, no-schema backwards compatibility, and the upsert-call shape. Total pytest: 337 → 341.",
      "Bug-family audit (CLAUDE.md §7): only one validation callsite + zero sibling warn-and-proceed patterns. The bug class is closed in one fix.",
      "Side effect for operators: /observability/events audit_type=knowledge_indexed rows now carry an `invalid` count. Useful signal for catching future corpus-pollution leaks early.",
    ],
  },
  {
    version: "0.6.52",
    date: "2026-05-20",
    title:
      "Schema uniformity across all 629 XQL KB entries + corrected stale auto-deploy phrasing in CLAUDE.md. Old half of the corpus (entries 1-161) was missing the ## When to use / ## Variations / ## Source body sections v0.6.51 standardized on. Backfilled; 100% of the corpus now has analyst-intent text in the embed payload.",
    highlights: [
      "Embedding-quality fix, not aesthetics: the embedder embeds the entire body text. With old entries missing ## When to use, their vectors lived in a different subspace than new entries' — similarity search would systematically prefer new entries even when an old one was the better match. Schema uniformity closes that gap.",
      "Re-runnable, idempotent backfill tool at bundles/spark/kbs/xql-examples/_tools/backfill_old_entries.py. Walks the entries directory; parses existing frontmatter + title + dataset + SQL; appends ## When to use + ## Variations + ## Source using the same heuristic as the v0.6.51 importer. Entries already on the new schema are skipped — running twice is a no-op.",
      "CLAUDE.md auto-deploy phrasing aligned with docs/CICD.md's v0.6.8 contract. Pre-v0.6.52 lines said 'CI does NOT install' + 'install when ready (operator)' but auto-deploy as the last step of build-dev-installer.yml has been live since v0.6.8. The agent was waiting for a deploy that already happened. Five spots in CLAUDE.md updated.",
      "Bug-family audit (CLAUDE.md §7): grep -L for any of the three section headers across all 629 entries returns 0 results post-backfill. Two heuristic-marker phrasings are intentionally distinct ('importer's heuristic' for v0.6.51's 32 entries, 'backfill heuristic' for v0.6.52's 161 entries) so the operator's curation pass can target each population independently.",
      "KB auto-reindexes on next agent boot (SqliteKnowledgeBase detects newer entry mtimes). audit_type=knowledge_indexed row appears in /observability/events post-reindex.",
    ],
  },
  {
    version: "0.6.51",
    date: "2026-05-20",
    title:
      "XQL example KB grew 166 → 629 entries via bulk import of the operator's XSIAM saved-query dataset. 91% of new entries carry operator-authored intent descriptions — the embedder-facing payload is now operator-grade across most of the corpus.",
    highlights: [
      "Pre-loads the KB for the upcoming build_xql_query skill (next release). The skill's retrieval step is bounded by description quality; v0.6.51 seeds the KB with analyst-grade intent text so similarity matching has signal on day one.",
      "Re-runnable converter at bundles/spark/kbs/xql-examples/_tools/import_operator_dataset.py + the source dataset preserved in-repo. Idempotent IDs (deterministic hash of original query id + title) so future re-runs don't churn the working tree.",
      "Description provenance per-entry: 424 from operator's XSIAM-saved-query description field (e.g. 'Display CGO + LOLBINS processes + child processes seen fewer than 10 times'), 7 from //Description: SQL comments in QR-template queries, 32 fall to heuristic (marked in Source for future curation).",
      "Schema validation passes for all 629 entries; only 32 entries flagged for operator-curation review (grep for 'auto-generated by the importer\\'s heuristic').",
      "KB auto-reindexes on next agent boot (SqliteKnowledgeBase detects newer entry mtimes). No manual command needed; audit_type=knowledge_indexed row appears in /observability/events post-reindex.",
    ],
  },
  {
    version: "0.6.50",
    date: "2026-05-20",
    title:
      "Connector instance API responses now include container_url. Field exists in the database + dataclass + is set correctly by phantom-updater's callback — but three serializers were silently dropping it from API responses (HTTP /api/v1/instances + instances_list + instances_get MCP tools).",
    highlights: [
      "Caught during a bug-scan pass: instances_list returned container_url=n/a for all 3 connectors. SQLite query showed the column was populated; the API serializer was dropping the field.",
      "Three sites fixed in coupled change: HTTP serializer in api/instances.py, plus instances_list + instances_get in self_mod_tools.py.",
      "Bonus cleanup: dropped the dead 'updated_at' field that the MCP tools' docstrings promised but the dataclass + schema never delivered — it always returned None via getattr fallback. No more lying about a field that can't be populated.",
      "Write path was always correct: phantom-updater's _agent_set_container_url callback POSTs the URL → PUT handler → SQLite UPDATE all worked. Only the read paths were broken.",
      "Why nobody noticed: pre-v0.5.61 most connectors were in-process style:module (no per-instance container, so container_url was always None — undetectable). With cortex-xdr + cortex-docs + caldera all running as style:container in this install, the field is finally meaningful and the omission visible.",
      "Bug-family audit per CLAUDE.md §7: grep -rn 'container_url' covered all read paths + grep -rn 'updated_at' caught the related dead field. No other sibling sites need fixing.",
    ],
  },
  {
    version: "0.6.49",
    date: "2026-05-19",
    title:
      "v0.6.47's pytest pre-deploy gate command was missing PYTHONPATH=$PWD/src. Running the v0.6.47 command locally produces ModuleNotFoundError: No module named 'usecase' on half the test files. v0.6.49 documents the correct PYTHONPATH prefix.",
    highlights: [
      "The embedded MCP test suite mixes two import styles: 'from src.config.config import Settings' (works without PYTHONPATH) and 'from usecase.approvals_bus import ...' (needs src/ on PYTHONPATH). v0.6.47 only tested with the first style and missed the second.",
      "CI's pytest invocation correctly uses PYTHONPATH=/work/bundles/spark/mcp/src; v0.6.47 documented the local equivalent without that prefix. Caught when I ran the gate locally before pushing v0.6.48.",
      "Fix: 1-line shell command change in both CLAUDE.md gate references (§ Pre-deploy gate full block + § Agent-behavior contracts one-liner). 6-line inline comment in the gate block documents the WHY so the rule's origin is self-contained.",
      "Considered: fix all the 'from usecase.X' imports to use 'from src.X' style across ~30 test files. Rejected — bigger refactor than the docs change, marginal benefit, the import style is a property of the source tree layout.",
      "v0.6.47 → v0.6.49 within ~30 minutes demonstrates the 'fix → smoke → discover → fix again' loop value. Each release captures one concrete lesson; the audit trail grows with the discipline.",
    ],
  },
  {
    version: "0.6.48",
    date: "2026-05-19",
    title:
      "Removed stale phantom-mcp:8080 fallback URL from mcp-proxy.ts. The phantom-mcp service was collapsed into phantom-agent in v0.1.30; the fallback pointed at a service retired ~5 releases ago.",
    highlights: [
      "Pre-v0.1.30 there was a separate phantom-mcp container in the compose network. v0.1.30 collapsed it into a subprocess inside phantom-agent on localhost:8080. The fallback URL in mcp/agent/lib/mcp-proxy.ts:36 stayed pointing at the old hostname.",
      "Production wasn't affected because installer/docker-compose.yml always sets MCP_URL=http://localhost:8080/... in the phantom-agent env block. But if MCP_URL were ever unset for any reason (manual operator edit, runtime-config refresh hiccup), the fallback would have produced EAI_AGAIN: phantom-mcp DNS failures.",
      "Fix: literal default flipped to http://localhost:8080/api/v1/stream/mcp. 13-line inline comment cross-references v0.1.30 (the collapse) + v0.4.0 (TLS rollout where entrypoint.sh may flip http:→https: when TLS_CERT_PEM is set).",
      "Bug-family audit: grep -rn 'phantom-mcp' mcp/agent/ bundles/spark/ — remaining hits are observability-probe URLs in bundles/phantom-agent.bundle.yaml + bundles/observability.contract.yaml (not load-bearing; out of scope for this contained release), plus historical release-notes/journeys references intentionally preserved.",
      "No regression risk — fallback never fired in production. Defensive cleanup for the rare-case future where MCP_URL might be unset.",
    ],
  },
  {
    version: "0.6.47",
    date: "2026-05-19",
    title:
      "pytest added to CLAUDE.md's local pre-deploy gate. Lesson from v0.6.45→v0.6.46: TS gates (tsc + lint + build) let a Python pydantic-default change through without catching its corresponding test break.",
    highlights: [
      "Pre-deploy gate now 4 steps instead of 3: tsc + lint + build (TS-side) + pytest (Python embedded MCP side). Total local runtime ~45-60s, vs an 8-minute CI roundtrip if the test break only surfaces in CI.",
      "Origin documented inline in CLAUDE.md: v0.6.45 changed bundles/spark/mcp/src/config/config.py:37's pydantic default; tests/test_config.py:10 asserted the old value; CI's Build agent pytest step caught it; v0.6.46 fixed assertion. v0.6.47 closes the loop by promoting pytest to the documented gate so future runs catch this locally.",
      "Both gate references updated: § Pre-deploy gate (full block with comment), § Agent-behavior contracts (chained one-liner). Both edits cross-reference v0.6.45/v0.6.46 so the rule's origin is self-documented.",
      "Smoke: any push that touches bundles/spark/mcp/** should run pytest locally first. Failing pytest before push avoids the CI roundtrip + the wasted Build agent / Build connectors compute cycles.",
    ],
  },
  {
    version: "0.6.46",
    date: "2026-05-19",
    title:
      "Test assertion updated to match v0.6.45's xlog_url default change. CI caught the discrepancy via pytest — test still expected the pre-v0.6.45 http:// default.",
    highlights: [
      "v0.6.45 flipped pydantic-settings default xlog_url from http://localhost:8000 to https://localhost:8000. The agent's pytest step in Build agent workflow caught test_settings_defaults asserting the old value. 1 failed, 336 passed.",
      "Fix: update test assertion to 'https://localhost:8000' with inline comment cross-referencing v0.6.45 + v0.6.46 so the test stays self-documenting.",
      "test_settings_from_env (env-override test) deliberately keeps http://example.com:9000 — that test is about the override path, not the default. Mixing schemes across tests is intentional.",
      "Lesson recorded in CHANGELOG: when changing a pydantic-settings default, grep for tests asserting that default value. CLAUDE.md pre-deploy gate (tsc + lint + npm run build) catches TypeScript regressions; the agent-side pytest only runs in CI. Adding 'pytest bundles/spark/mcp/tests/' to the local pre-deploy gate would catch this class of break pre-push.",
      "Bug-family audit: grep -rn 'http://localhost:8000' bundles/spark/mcp/tests/ — only test_settings_from_env (intentional, env-override path) remains. No other dead assertions.",
    ],
  },
  {
    version: "0.6.45",
    date: "2026-05-19",
    title:
      "xlog URL default schemes swept from http to https across 5 files. v0.4.0 made xlog HTTPS-only; v0.6.22 fixed the marketplace synthetic card but missed bundle manifest, observability contract, connector.yaml schema default, pydantic-settings fallback, and connector_probes.py fallback.",
    highlights: [
      "Discovered via grep-sweep during the bug-hunt loop. v0.6.22's release notes called out the marketplace fix but didn't audit sibling files. Bug-family miss similar to the v0.6.37/v0.6.41 audit_recent/audit_search pattern.",
      "Why production mostly didn't break: compose env always sets XLOG_URL=https://xlog:8000 (correct since v0.6.24), so pydantic fallback + probe fallback rarely got hit. The marketplace card was the most common new-instance path and v0.6.22 fixed that one.",
      "But: programmatic xlog instance creation via direct API (no UI) + the probe's final fallback DID hit operators who happened to follow those paths. Symptoms were 'Empty reply from server' against the HTTPS-only listener.",
      "5 surgical edits in v0.6.45: connector.yaml default + description, bundle manifest's 3 internal URLs (REST/GraphQL/healthcheck — externalUrls at localhost:8999 stay http since IAP tunnel terminates TLS), observability contract health probe, pydantic default, probe fallback.",
      "Bug-family audit after fix: grep -rn 'http://xlog' bundles/ mcp/ updater/ — only remaining hits are a Dockerfile comment (descriptive, not load-bearing) and historical release-notes.ts entries (operator-facing history, intentionally preserved).",
      "Smoke: /observability health-probe page no longer shows xlog as down due to scheme mismatch. Programmatic xlog instance creation defaults to https://xlog:8000. Operator-provided baseUrl values still win over all defaults — no behavior change for already-configured instances.",
    ],
  },
  {
    version: "0.6.44",
    date: "2026-05-19",
    title:
      "xdr_get_alerts(alert_ids=[...]) now finds alerts older than 24h. v0.6.40 implementation applied a default 24h creation_time filter unconditionally — silently excluded older alerts even when the operator passed specific IDs.",
    highlights: [
      "Smoke caught it right after v0.6.40 deploy: get_alerts(alert_ids=[40119, 40265]) returned 0 alerts where I had verified 2 alerts during development. The alerts were 2 days old; my default 24h window excluded them. XDR's AND-of-filters semantic killed the lookup.",
      "v0.6.40 docstring claimed time filters 'become advisory' when alert_ids is set — but the code applied them anyway. Docstring/code drift.",
      "Fix: skip time filters when alert_ids is set AND no explicit time was passed. Decision matrix: alert_ids set + no explicit time → skip (search all history); alert_ids + explicit time → apply both (intersect query); alert_ids unset → apply default 24h window.",
      "Lesson: structural review missed this because my dev-time test used recent alert IDs. Caught by re-running smoke days later with aged-out test data. Updating smoke discipline to include 'alert from >24h ago' as a test point for time-windowed tools.",
      "Smoke verified live: get_alerts(alert_ids=[40119, 40265]) returns both alerts post-fix. Regression check: get_alerts(severity=['high']) without alert_ids still applies 24h window unchanged.",
    ],
  },
  {
    version: "0.6.43",
    date: "2026-05-19",
    title:
      "phantom-updater now handles space-bearing instance names (Cortex XDR, Cortex Docs Search). Pre-v0.6.43 the reconcile/start/stop/restart endpoints rejected these as 'invalid path segment' — so existing instances couldn't be re-image-pulled after a connector code change.",
    highlights: [
      "Caught live during v0.6.40 smoke: POST /api/v1/connectors/reconcile returned 'reconciled: [Caldera]' BUT 'failed: [Cortex Docs Search, Cortex XDR]' with HTTP 400 invalid path segment errors. Single-word names passed; space-bearing names failed at the path validator.",
      "Root cause: _validate_path_segments enforces [a-zA-Z0-9_-]+ on instance_name from URL paths. Correct for shell-meta protection, but applied uniformly to operator display names that legitimately contain spaces.",
      "Fix: new _normalize_instance_name(name) — replaces whitespace with underscore. Applied at all 4 endpoint call sites (start, stop, restart, url) BEFORE _validate_path_segments. Validator stays strict (rejects dangerous chars); spaces get pre-translated to match the underscore-bearing form the original create flow produced.",
      "Why this matters for the dev cycle: pre-v0.6.43 there was NO API path to recreate space-bearing instances with the latest pinned image digest. v0.6.38 + v0.6.39 + v0.6.40's connector code changes had no way to land in running cortex-* instances. Post-v0.6.43, reconcile is the one-call upgrade path.",
      "Bug-family audit per CLAUDE.md §7: grep _validate_path_segments updater/ — 4 endpoint sites, all prefixed with normalization. grep 'invalid path segment' mcp/agent/ bundles/ — zero hits, no agent-side mirror of the pattern.",
      "Smoke: POST /api/v1/connectors/reconcile on a stack with 'Cortex XDR' and 'Cortex Docs Search' instances now returns success for both. Idempotent for already-normalized names (Cortex_XDR → Cortex_XDR no-op).",
    ],
  },
  {
    version: "0.6.42",
    date: "2026-05-19",
    title:
      "Chat-route connector_id derivation fixed for hyphenated-id connectors. Pre-v0.6.42, /observability/connectors state machine was missing real failures for cortex-xdr, cortex-docs, cortex-content, xlog, and web — split('_', 1) returned wrong ids.",
    highlights: [
      "Discovered during v0.6.41's bug-hunt loop. Two adjacent lines in chat/route.ts derived connector_id via 'toolName.split(_, 1)[0]'. That works for caldera (prefix matches id) and xsiam (same), but breaks for any connector whose function prefix differs from its id: xdr_*→xdr (id is cortex-xdr), phantom_*→phantom (id is xlog), phantom_web_*→phantom (id is web), cortex_*→cortex (id is cortex-docs OR cortex-content).",
      "Consequences: recordConnectorFailure POSTed to /api/v1/connectors/xdr/_record_failure → 404 → state machine silently missed every cortex-xdr failure. connector_auth_required event emitted with wrong id → chat UI didn't show needs-auth chips for any hyphenated-id connector. recordConnectorSuccess similarly mistargeted, so even after fixing credentials the state wouldn't transition back to 'connected'.",
      "Fix: new deriveConnectorId(toolName) helper at module scope. Dotted form (cortex-xdr.get_alerts) splits on '.' as before. Flat aliases use an explicit longest-prefix mapping table: phantom_web_→web, phantom_→xlog, xdr_→cortex-xdr, caldera_→caldera, xsiam_→xsiam. cortex_ disambiguated by tool-name lookup (small fixed set of 6 cortex-docs tools; everything else cortex-content). Built-in MCP tools (instances_list, audit_recent, jobs_*, etc.) return null — caller skips connector state update.",
      "Maintenance note in CHANGELOG + code: when a new connector ships with a non-identity function-prefix→id mapping, add an entry. Long-term, MCPTool interface should carry connector_id explicitly so this lookup becomes unnecessary. Filed as design debt.",
      "Smoke: cause a cortex-xdr tool to fail (rotate api_key) — /observability/connectors should now transition cortex-xdr to 'failing' + needs-auth chip appears. Same for cortex-docs via cortex_search call.",
      "Bug-family audit: grep '_split.*_', 1' mcp/agent/ — exactly 2 hits, both replaced. Single point of fix.",
    ],
  },
  {
    version: "0.6.41",
    date: "2026-05-19",
    title:
      "Bug-family audit miss from v0.6.37 closed: audit_search + metrics_health also had broken log.search() calls. audit_search raised AttributeError on every invocation; metrics_health silently reported errors_recent=0 regardless of actual error volume.",
    highlights: [
      "Verification of v0.6.37's deployed code revealed the miss: grep 'log.search' inside the running phantom_agent container returned 3 hits, only 1 of which was the v0.6.37 fix. audit_search and metrics_health were still broken.",
      "Root cause: my v0.6.37 bug-family audit grepped for 'audit\\.search' (noun pattern). The actual call pattern in code was 'log.search(...)' — bound variable named 'log', not 'audit'. The grep target was too narrow.",
      "Lesson for future audits: grep for the CALL pattern '\\.method_name(' — not the conceptual noun. Variable names vary (log, audit, client, store, fetcher) but call patterns are consistent.",
      "audit_search additional bug: it accepted a 'q' free-text search param that the underlying API never supported (SqliteAuditLog has no FTS index). v0.6.41 keeps the param but post-filters client-side after fetching with overfetch=limit*4. For typical audit.db sizes (<100K rows), this stays sub-millisecond.",
      "metrics_health silent miscount: 'log.search(limit=200) if hasattr(log, search) else []' fell through to the empty fallback (no .search method exists), then sum() over empty list returned 0. SOC operators using /metrics dashboards have been seeing errors_recent=0 since the metrics_health tool was added — completely silent regression.",
      "Smoke surfaces: audit_search(action='tool_call', limit=10) returns rows; audit_search(q='caldera') confirms post-filter; metrics_health().errors_recent reflects actual failure count.",
    ],
  },
  {
    version: "0.6.40",
    date: "2026-05-19",
    title:
      "New xdr_get_alerts tool — direct alert lookup via XDR's REST API, routing around the broken XQL alerts preset. Live tenant testing showed every preset=xdr_alerts query returning HTTP 500 while /alerts/get_alerts works perfectly.",
    highlights: [
      "Smoke during v0.6.39 development exposed it: every preset=xdr_alerts XQL query returns 500 in this tenant. Tested simplest-possible 'preset = xdr_alerts | limit 1', severity-filter, alert_id_list filter, single equality. All 500. Meanwhile dataset=xdr_data XQL works fine (8855 process events returned).",
      "New tool: get_alerts wraps /public_api/v1/alerts/get_alerts REST endpoint. Args: alert_ids (int list), severity, status, from_time/to_time, limit (max 100), sort_by (creation_time | detection_timestamp). Returns 22-field summary per alert — the fields LLM needs to triage + correlate, not the full ~80-field XDR blob.",
      "Defensive int coercion: XDR rejects alert_id_list strings with 'must contain only integers'. LLMs commonly serialize IDs as strings. Connector now coerces alert_ids=[int(x) for x in alert_ids] silently. Operators pass either form, the API gets what it needs.",
      "Live verification during build: get_alerts(alert_ids=[40119, 40265]) returned both alerts with full forensic detail (T1140 Deobfuscate/Decode, case_ids 1794 + 1795, PowerShell actor). Bonus: confirmed those alert IDs (which operator initially recalled as lateral-movement) are actually credential-gathering signatures — useful correction for the demo report.",
      "Why route around XQL instead of fix: the tenant's XQL alerts preset is broken at the XDR backend; we can't fix it server-side. REST is stable, exposes same data, returns in <1s. For operators who need XQL semantics, xdr_run_xql_query against dataset=xdr_data still works (the bug is preset-specific).",
      "Existing tools unchanged: get_cases_and_issues, get_incident_extra_data, run_xql_query, get_xql_results all preserved. get_alerts is additive.",
    ],
  },
  {
    version: "0.6.39",
    date: "2026-05-19",
    title:
      "xdr_get_cases_and_issues now defaults to modification_time filter (was creation_time). Pre-v0.6.39 returned 0 incidents during an active simulation because XDR clusters new alerts into EXISTING cases — the old filter only matched freshly-created cases, silently missing every update to an older case.",
    highlights: [
      "Live capture (session-e980fc7d, 2026-05-19): agent called xdr_get_cases_and_issues(from_time='2026-05-19T08:06:00Z') after a 20-step Caldera kill chain. Got 0 incidents. XDR case 1872 was real, active, and received 75 alerts during the simulation — but its creation_time was 07:51 (from an earlier morning run), BEFORE the filter window. Filtering on modification_time would have caught all 75.",
      "Operator's instant diagnosis: 'I see new issues being added to the cases that we triggered yesterday no new case has been created.' XDR's case-clustering engine groups new alerts into EXISTING cases by threat fingerprint. A case from last week can receive fresh alerts today.",
      "Fix: three coupled changes in bundles/spark/connectors/cortex-xdr/src/connector.py — new time_field parameter (default modification_time, valid: {creation_time, modification_time}), filter expression uses the chosen field, sort uses the chosen field. applied_filters now surfaces time_field so callers see which semantic was used.",
      "Default change is safe: modification_time is strictly more inclusive than creation_time (every case has mt >= ct). Callers post-v0.6.39 see a strict superset of what they saw pre-v0.6.39. No silent regression.",
      "Skill text updated: bundles/spark/mcp/skills/workflows/xdr_verify_simulation_telemetry.md Step 2 reframed from 'fetch incidents created' to 'fetch incidents touched', example code passes from_time directly and relies on the new default, pre-v0.6.39 client-side filtering recipe removed.",
      "Bug-family audit per CLAUDE.md §7: only cortex-xdr's get_cases_and_issues had this pattern. xsiam's get_cases uses a free-text query string, no equivalent bug.",
    ],
  },
  {
    version: "0.6.38",
    date: "2026-05-19",
    title:
      "Connector containers no longer show as (unhealthy). The HEALTHCHECK CMD in phantom-connector-runtime was calling wget, which doesn't exist in python:3.12-slim's Debian trixie base — every connector container had been reporting unhealthy since v0.5.x with thousands-deep failing-streak counters.",
    highlights: [
      "Operator caught the false-unhealthy labels during v0.6.34 demo prep when scanning docker ps. cortex-xdr connector at FailingStreak=982, cortex-docs at 1645, caldera at 507 — all while the underlying /health endpoint was returning HTTP 200 OK on every probe. Healthcheck CMD itself errored with 'sh: 1: wget: not found' (exit 127). The slim Debian variants strip wget, curl, AND nc.",
      "Why this didn't block anything operationally: phantom-updater routes MCP calls on Container.Up, not Container.Health. The (unhealthy) label was purely cosmetic — every connector tool call succeeded normally. Confused operators, didn't break anything.",
      "Fix: replace wget with python3 -c urllib.request.urlopen. Python is already in the container (it IS a Python container), zero dependency change. Same endpoint, same semantics, just a tool that exists in the image. The phantom-browser/Dockerfile literally has a comment explaining why it skipped HEALTHCHECK ('minimal image without wget, curl, sh, python, or even nc') — the connector-runtime should have read that comment before assuming wget was available.",
      "Bug-family audit per CLAUDE.md §7: grep -rn HEALTHCHECK across the repo. Only phantom-connector-runtime/Dockerfile had the wget bug. All other services either don't define HEALTHCHECK or document why they can't.",
      "Smoke: after auto-deploy lands v0.6.38, all per-instance connector containers should report healthy in docker ps and docker inspect. Also added to smoke discipline: 'grep -v unhealthy in docker ps' for any release touching connector image builds — would have caught this in 2 seconds at any earlier release.",
    ],
  },
  {
    version: "0.6.37",
    date: "2026-05-19",
    title:
      "audit_recent MCP tool now works. Pre-v0.6.37 every call raised AttributeError 'SqliteAuditLog object has no attribute search' — implementation called phantom methods (recent, search) that don't exist. Canonical method is query().",
    highlights: [
      "Caught live in session-82f3ee07: chat agent called audit_recent(limit=1) as a sanity check, got the AttributeError, ignored it (the tool wasn't critical to that workflow). But any operator-driven use case — read last N audit rows during incident response, populate a dashboard, diagnose a tool call — would have been blocked.",
      "Root cause in self_mod_tools.py line 453: 'log.recent(limit=limit) if hasattr(log, \"recent\") else log.search(limit=limit)'. SqliteAuditLog has neither method. The hasattr check returned False, fallback called .search() which also doesn't exist, raised AttributeError. Speculative defense for a duck-typed audit_log interface that doesn't actually exist in this codebase.",
      "Fix: log.query(limit=limit) directly. query() already returns list[dict] via _row_to_dict, so the downstream 'r.to_dict() if hasattr(r, to_dict) else r' redundancy also dropped. Net 12-line change including the explanatory comment.",
      "Bug-family audit (CLAUDE.md §7): grep -rn for other callers expecting .recent/.search on SqliteAuditLog returned zero hits. audit_recent was the sole victim. Clean fix, no sibling code to update.",
      "Smoke 1 (MCP-side): audit_recent(limit=5) from inside the phantom_agent container returns 5 most-recent audit rows. Smoke 2 (chat-side): ask the agent 'show me the 10 most recent audit events' — post-fix the tool result is actual rows instead of an AttributeError.",
    ],
  },
  {
    version: "0.6.36",
    date: "2026-05-19",
    title:
      "PHANTOM_CHAT_MAX_TURNS env var is now actually operator-tunable — added bare-name forwarding to both compose files. v0.6.32's release notes promised this but the plumbing was an audit-miss; setting the var in .env had no effect.",
    highlights: [
      "Discovered during v0.6.35 smoke testing — tried to set PHANTOM_CHAT_MAX_TURNS=2 to deterministically reproduce the dropped-final-response bug; the container kept using the compiled default of 30. The chat-route code reads process.env.PHANTOM_CHAT_MAX_TURNS at line 4190, but docker-compose only passes through env vars explicitly listed in each service's environment: block.",
      "Fix is two lines (one per compose file): - PHANTOM_CHAT_MAX_TURNS added to phantom-agent service's environment block in installer/docker-compose.yml and the dev docker-compose.yml. Bare-name forwarding lets the operator set the var in .env; if unset, the route.ts default-30 path triggers naturally.",
      "Pairs operationally with v0.6.35 — that release is the fix for what happens when the cap is hit; this one is the plumbing that lets operators verify it. Together they close issue #56 (chat-route drop) and issue #57 (plumbing miss).",
      "Smoke 1 (no regression): with PHANTOM_CHAT_MAX_TURNS unset, route uses default 30. Smoke 2 (the actual fix): set =2 in .env, restart phantom_agent, run a 3+ tool query. logDebug 'Recovered N chars of post-budget text from final unprocessed response' visible in docker logs phantom_agent confirms v0.6.35 + v0.6.36 working together.",
      "Per CLAUDE.md contained-release discipline: one concept per release. v0.6.35 = chat-route flushes final response. v0.6.36 = env var actually plumbed. Two releases, one capability complete.",
    ],
  },
  {
    version: "0.6.35",
    date: "2026-05-19",
    title:
      "Chat agent's final deliverable no longer dropped when the turn-budget cap is hit. Caught in a live SOC-simulation session where the Phase 3 XDR cross-reference table vanished after the model spent its budget on the kill-chain walk.",
    highlights: [
      "Live capture (session-e980fc7d, 2026-05-19): agent ran a focused Caldera + Cortex XDR roundtrip, completed all 40 Caldera abilities, fired the final xdr_get_cases_and_issues query — then the session ended with 'I'm now pulling incidents from Cortex XDR...' and nothing after. The cross-reference table the prompt explicitly asked for never reached the operator.",
      "Root cause: the chat-route for-loop processes a model candidate's text + functionCalls at the TOP of each iteration. When iteration N dispatches tools, callGemini() runs at the BOTTOM — and that response is what iteration N+1 would normally process. If N is the last allowed iteration, N+1 never runs, and the response is silently dropped.",
      "Why existing fallbacks missed it: both the budget-summary fallback and synthesizeFallbackText are gated on finalResponse being empty. In this session finalResponse was non-empty (it had Phase 1 + Phase 2 narration); the lost content was the END of the response, not the whole thing. Neither fallback notices 'you got partial text but the model's last word was lost.'",
      "Bug-family confirmation: the subagent loop in the same file (~lines 792-806) already had the equivalent fix — drain the last unprocessed response when turnsUsed >= max_turns. Two sibling loops, one with the patch, one without. Classic CLAUDE.md §7 audit-miss.",
      "Fix: after the chat-route's agent for-loop closes, if exhaustedBudget is true, pull text out of the final response and push it to finalText + stream it as text_delta. Function calls in this last response are intentionally dropped (we can't dispatch them without bumping the cap). Behavior when budget is NOT exhausted is unchanged.",
      "Deterministic repro for smoke: set PHANTOM_CHAT_MAX_TURNS=2 in the agent container, then run a chat query that needs 3+ tool calls plus a summary. Pre-fix: summary text is lost. Post-fix: summary text appears in the chat bubble as text_delta.",
    ],
  },
  {
    version: "0.6.34",
    date: "2026-05-19",
    title:
      "caldera_wait_for_operation_progress now returns a COMPACT summary (<2KB) instead of the full 50KB Caldera blob. LLM was misreading the dense response, hallucinating last_chain_length=40 after seeing chain=2.",
    highlights: [
      "4th run analysis: agent narrated last_chain_length=40 on 2nd wait call after wait #1 returned chain.length=2. LLM was pattern-matching on adversary.atomic_ordering's 20 ability UUIDs × 2 agents in host_group = '40' from the response blob.",
      "Compact response: {done, state, chain_progress: {total_entries, completed_terminal, in_flight, succeeded, failed_parser, expected_total}, recent_abilities, next_call_args}. ~2KB instead of ~50KB.",
      "Exit logic refined: chain.length >= expected_total alone wasn't enough (Caldera queues all 40 links at op start with status=-3 pending). Now requires ALL chain entries to have terminal status {0, 1, -2, -4, -5}.",
      "next_call_args pre-built — agent copies them verbatim to next call. The `done` flag is computed by the connector, not by the LLM. Eliminates the cognitive overhead that caused the misread.",
      "Skill rewrite: while not result['done']: narrate from compact numbers, call with **result['next_call_args']. Mechanical loop, no chain.length math.",
      "Expected post-deploy: agent completes 40-entry chain in 10-15 wait calls, ~12-14 min wall-clock, then real XDR sweep with incident IDs.",
    ],
  },
  {
    version: "0.6.33",
    date: "2026-05-19",
    title:
      "caldera_wait_for_operation_progress was treating state=paused as terminal, but Caldera's atomic planner uses paused BETWEEN ability dispatches. Agent exited polling early thinking chain was done while Caldera still had 14 abilities to fire.",
    highlights: [
      "3rd kill-chain run (post-v0.6.32) appeared clean: 10 wait calls, agent claimed 'all 20 steps executed'. Ground-truth check on Caldera afterward revealed operation still state=running with chain having 40 entries (20 abilities × 2 agents in group=red), and the agent's last wait result was paused with only 6 chain entries.",
      "Caldera's atomic planner toggles paused/running between ability dispatches. v0.6.32 treated paused as terminal → false completion → agent stopped before chain finished → XDR query happened before most events fired → 'Pending Correlation' for every technique.",
      "v0.6.33 removes paused from the terminal set (real terminals: finished, cleanup, out_of_time). New expected_total_abilities param (= adversary atomic_ordering × in-scope agents) gives the wait tool a chain-length completion signal that works around Caldera's auto_close=false (which keeps state='running' forever after chain completes).",
      "Skill rewrites: count red-group agents first, multiply by 20 → expected_total = 40 typical. Wait tool exits when chain_len >= expected_total OR true terminal. Never on paused.",
      "Next run will properly poll the full 40-entry chain (~15-20 wait calls over 12-14 min) AND give XDR a few minutes to correlate before declaring detection coverage.",
    ],
  },
  {
    version: "0.6.32",
    date: "2026-05-19",
    title:
      "Kill-chain orchestration hit the chat handler's hardcoded 20-turn cap because LLMs can't sleep between polls. Fix: new caldera_wait_for_operation_progress tool blocks server-side, plus max-turns cap bumped 20→30 + made env-configurable.",
    highlights: [
      "End-to-end smoke confirmed: agent polled 10 times in 2:40 min then hit the cap with 'Still running. Continuing to poll' as the last message. v0.6.31's strengthened skill text helped (3→10 polls) but couldn't fix the structural issue of LLMs firing tool calls back-to-back when Caldera abilities physically need 30-60s each.",
      "New tool caldera_wait_for_operation_progress blocks inside the connector container for up to 90s, returns as soon as the chain grows or state shifts to terminal. ONE call = ~30-60s wall-clock = 1-2 abilities advance.",
      "Primary chat handler's hardcoded `for step < 20` replaced with MAX_AGENT_TURNS env-driven cap (default 30, clamped to [5, 200]). Operators can tune via PHANTOM_CHAT_MAX_TURNS.",
      "Kill-chain skill Step D rewritten to use the new wait tool as the canonical pattern. Pre-v0.6.32 fallback documented as anti-pattern.",
      "Expected pattern post-deploy: ~22-28 total LLM turns, ~10-14 min wall-clock, all 20 Caldera abilities complete, final per-technique XDR coverage gap analysis. Headroom of 2-8 turns under the new 30 cap.",
    ],
  },
  {
    version: "0.6.31",
    date: "2026-05-19",
    title:
      "Kill-chain skill polling discipline rewritten — LLMs were exiting at 3 polls (2 min) instead of looping the full 10-14 min the 20-step chain needs. Smoke caught it; fix is text, not code.",
    highlights: [
      "End-to-end smoke via /api/chat: agent fired all the right setup tools but only polled caldera_get_operation_by_id 3 times before declaring the chain 'complete' — at 2 minutes 23 seconds, with state still 'running' and 0/20 abilities completed.",
      "Root cause: LLMs naturally synthesize an answer after a few tool calls. The skill's `loop until` pseudo-code wasn't strong enough to override that instinct.",
      "Skill rewrite addresses the LLM-as-reader directly: 'THIS STEP IS LONG-RUNNING — 10 to 14 MINUTES. You MUST poll patiently. Your natural instinct is to synthesize a response. Resist it.' Explicit polling count (15-30 calls), strict exit invariants (state=finished AND chain.length=20 AND all statuses in {0,1,-2}), concrete progress-narration template per poll.",
      "Context-window-bloat warning: 20-30 polls × 50KB each = 1.5MB of tool-result content. Skill instructs summarizing each poll in 1-2 lines max.",
      "Known-broken tool callout: caldera_get_operation_report returns 405 (Caldera v2 API endpoint changed); skill explicitly says don't call it.",
      "Next: re-run the kill chain end-to-end. If polling discipline holds, expect 20+ caldera_get_operation_by_id calls over ~14 min, mid-chain 🛰️ XDR pulses every other poll, and final Step H sweep with per-technique gap analysis.",
    ],
  },
  {
    version: "0.6.30",
    date: "2026-05-19",
    title:
      "cortex-xdr _iso_to_ms accepts numeric epoch (string or int) in addition to ISO timestamps. Pre-v0.6.30 the LLM passing from_time='1779160958000' crashed with 'month must be in 1..12'.",
    highlights: [
      "End-to-end smoke caught this: mid-chain XDR pulse called xdr_get_cases_and_issues(from_time='1779160958000', limit=10). The connector tried datetime.fromisoformat() which parsed the digits as year 1779 month 16 (>12) and raised. The agent saw an error and skipped the pulse.",
      "Common LLM pattern: when the agent captures an epoch value, JSON serialization tends to produce a numeric STRING. The connector's ISO-only parser was strict, so the call failed.",
      "Fix: _iso_to_ms now accepts 3 input shapes — None/empty (default offset), numeric int/float/digit-string (epoch seconds→ms canonicalized), ISO timestamp string (existing path).",
      "Verified locally with 9 test cases — all pass including the actual failure case ('1779160958000' as a string of milliseconds).",
      "Docstring updated to document both shapes so future LLM calls know the contract is permissive.",
    ],
  },
  {
    version: "0.6.29",
    date: "2026-05-19",
    title:
      "reset-admin CLI gains non-interactive --password-stdin + --skip-confirm flags. Pre-v0.6.29 the documented 'docker exec -i ...' flow silently broke under piped stdin; locked-out operators in SSH/CI contexts had no working CLI recovery path.",
    highlights: [
      "Surfaced during a real lockout: operator couldn't remember their May-13 custom password; needed to reset via the CLI in an SSH session (no TTY).",
      "Bug: readline.question() with piped stdin consumes the entire buffer on the first prompt, leaving the password + confirm prompts empty. CLI exits 1 with 'password too short' or 'passwords did not match' — no reset performed.",
      "Workaround that worked but bypassed CLI safety: direct curl to POST /api/v1/ui/auth/admin_reset with bearer auth. Same endpoint the CLI uses; just skips the typed RESET prompt.",
      "v0.6.29 adds --password-stdin (reads new password from stdin; argv never carries it — safe for ps + shell history) and --skip-confirm (bypasses the typed RESET prompt). Both required together for non-interactive use.",
      "Interactive flow unchanged: 'docker exec -it phantom_agent node /app/cli/reset-admin.mjs' still works exactly as before. Non-interactive is automation-only.",
      "Help page updated with copy-pasteable shell snippet for the new flow.",
    ],
  },
  {
    version: "0.6.28",
    date: "2026-05-19",
    title:
      "Chat bubble now visually separates the agent's 'I'll call X tool' narrative from its final answer. Tool-call preamble + interludes render in a muted italic box; final answer renders in normal prominent style.",
    highlights: [
      "Pre-v0.6.28 the assistant bubble mixed tool-call narration with the final answer in one continuous text blob. Operators had to skim past paragraphs of 'I'll call this, now I'll call that...' to find the actual response.",
      "ChatMessage gains boundaryIndices: number[] — positions in content where tool_call SSE events fired during the turn. The useChat hook records content.length at each tool_call.",
      "Message-list renderer uses the LAST boundary as the split: content before is 'narrative' (muted italic box with auto_awesome icon); content after is 'final answer' (normal prominent style).",
      "Backwards compatible: messages without boundaryIndices (historical messages reloaded from MCP storage; or turns that fired no tools) render as a single block like before.",
      "Trade-off: small visual snap on multi-tool turns when later tool_calls retroactively reclassify earlier 'answer' text as 'narrative for the next tool.' Conveys correct info; rare enough that the simple split is worth the cleanness. Per-segment timeline rendering is a future enhancement if needed.",
    ],
  },
  {
    version: "0.6.27",
    date: "2026-05-19",
    title:
      "Kill-chain skill now closes the simulation→detection loop — mid-chain XDR pulses + final XDR sweep with per-technique gap analysis. New reusable skill xdr_verify_simulation_telemetry.",
    highlights: [
      "Pre-v0.6.27 run_phishing_kill_chain fired the 20-step Caldera attack but told the operator to manually check /observability/events + RDP into the host. The agent never queried XDR. Real gap — operators were context-switching to the XDR UI after every kill chain.",
      "New skill xdr_verify_simulation_telemetry (~290 lines) — reusable building block. Two modes: pulse (quick 🛰️ one-liner with top-3 incidents, non-blocking, for mid-simulation) and sweep (exhaustive drill-down + per-technique gap analysis, for post-simulation).",
      "Updated run_phishing_kill_chain: Step B captures op_start_epoch; Step D polling loop now pulses XDR every other poll (~60s); new Step H final-sweep produces the gap analysis. Both XDR steps self-abort cleanly if the cortex-xdr connector isn't configured — kill chain never blocks.",
      "Pulse gives the operator intermediate confidence ('XDR is seeing the chain') while the simulation is still running. Sweep gives the gap analysis ('these 5 of 22 techniques fired; these 2 are coverage holes worth investigating').",
      "Smoke after deploy: type 'check XDR for incidents in the last hour' in chat → standalone sweep. Or type 'Run the phishing kill chain' → full chain with pulse + sweep interleaved.",
    ],
  },
  {
    version: "0.6.26",
    date: "2026-05-19",
    title:
      "v0.6.25 Coverage tab had wrong response shape — MCP returns dict, page expected list. Fixed with Object.values transform + corrected field names.",
    highlights: [
      "MCP's /api/v1/detections/coverage/techniques returns { techniques: { <T-code>: {rules_count, fires_24h/7d/30d, last_fire_at} } } — a DICT keyed by T-code. v0.6.25's page code assigned this to a list-typed state.",
      "Empty-state Coverage tab worked by accident; populated state would have rendered garbage. The bug was latent because no detection data had been synced yet.",
      "Fix: page now does Object.values(coverageBody.techniques) + sorts by fires_30d desc. Field names aligned: rule_count→rules_count, last_seen→last_fire_at. Added separate 24h/7d/30d columns matching MCP's granularity.",
      "Lesson logged: probe the actual response shape after the proxy is wired up, not just trust the route docstring. The MCP docstring said 'per-MITRE-T-code aggregation' without specifying dict-vs-list — I assumed list.",
    ],
  },
  {
    version: "0.6.25",
    date: "2026-05-19",
    title:
      "Detection inventory now has a UI surface — closes a CLAUDE.md rule-6 gap. /observability/detections page + 5 proxy routes + sidebar nav entry, all in one contained release.",
    highlights: [
      "MCP has exposed /api/v1/detections/* since Phase 12. The chat-driven detections_list MCP tool worked, but operators had no UI path — no agent proxy, no observability page, no sidebar entry.",
      "5 new proxy routes (list + single + fires + coverage + sync) — all standard proxyToMcp() with bearer auth attached server-side.",
      "/observability/detections page: Rules tab (table with severity badges, MITRE chips, 24h/7d/30d/total fire counts, filters); Coverage tab (per-MITRE-T-code aggregation).",
      "Sidebar nav entry added in the same release (rule 6a) — `radar` icon under Observability group, between Runtime events and Connectors.",
      "Empty-state guidance points operators at the detection_inventory_sync skill or the POST sync endpoint for seeding.",
    ],
  },
  {
    version: "0.6.24",
    date: "2026-05-19",
    title:
      "v0.6.22 was incomplete — compose XLOG_URL=http://xlog:8000 overrode the code fallback. v0.6.24 flips both compose files (customer + dev) to https://xlog:8000.",
    highlights: [
      "Post-v0.6.22 smoke confirmed /api/agent/health still reported xlog-api: failed and /api/agent/reports still returned 502. The reason: compose's environment block sets XLOG_URL=http://xlog:8000 explicitly, so process.env.XLOG_URL was always populated and the v0.6.22 fallback never kicked in.",
      "The compose comment claimed entrypoint.sh would rewrite XLOG_URL http→https when SSL_CERT_PEM was set. v0.1.34 removed that rewrite block years ago (per the InstanceStore-as-source-of-truth spec). The comment was stale; the env var was wrong.",
      "Fix: change XLOG_URL to https://xlog:8000 in BOTH installer/docker-compose.yml AND docker-compose.yml (dev). InstanceStore overrides still take precedence for operators who set a custom baseUrl.",
      "Lesson on contained-release smoke: ALWAYS run the post-deploy smoke before claiming a fix complete. v0.6.22's local tsc+lint+build green hid the runtime env-override gap. Real verification requires hitting the actual endpoint on phantom-vm.",
    ],
  },
  {
    version: "0.6.23",
    date: "2026-05-19",
    title:
      "docs/CICD.md 'how to add a connector' checklist expanded to 11 edits — covers the v0.6.20 plumbing discipline (release.yml + build-dev-installer.yml). Docs-only follow-up to v0.6.20.",
    highlights: [
      "v0.6.20 closed the latent cortex-xdr plumbing gap retroactively. The commit message promised a docs follow-up; v0.6.23 delivers it.",
      "Added edits #10 (release.yml — 6 sites covering IMAGES array + changed-detection + rebuild force + outputs + build-or-retag step + summary table row) and #11 (build-dev-installer.yml — CONN_IMGS map + resolution loop).",
      "Quick-check command expanded from 2 grep-comparisons to 4 — every connector dir is now verified against manifest.yaml + KNOWN_CONNECTORS + release.yml IMAGES + build-dev-installer.yml CONN_IMGS. Empty output = consistent.",
      "Added a v0.6.20 retrospective subsection narrating how the cortex-xdr v0.5.61-era omission stayed latent for ~16 releases until v0.6.18's connector restart surfaced it.",
    ],
  },
  {
    version: "0.6.22",
    date: "2026-05-19",
    title:
      "/api/agent/reports returned 502 because three xlog URL defaults were stuck on `http://xlog:8000`. xlog has served HTTPS unconditionally since v0.4.0.",
    highlights: [
      "xlog's _resolve_ssl_args() priority 1 is the shared phantom_tls volume — xlog mounts /tls/cert.pem (from phantom-agent's auto-generated cert) and serves HTTPS unconditionally. The architectural truth has been HTTPS-since-v0.4.0; the code defaults never caught up.",
      "Three hardcoded fallback sites: runtime-config.ts:126, reports/route.ts:14, marketplace/connectors/route.ts:139 (operator-facing form default). All three flipped to https.",
      "TLS verification works because the agent's entrypoint sets NODE_EXTRA_CA_CERTS=/tls/cert.pem before Next.js starts. The self-signed cert's SAN includes DNS:xlog. Verified empirically: with the env var set, https://xlog:8000 returns 200; without it, DEPTH_ZERO_SELF_SIGNED_CERT.",
      "Migration: existing operator-configured xlog instances with http://xlog:8000 in their baseUrl will continue to fail — operator needs to edit via /connectors → xlog → Edit. v0.6.22 only changes defaults for NEW instances + the agent-internal fallback chain.",
      "Help docs (architecture page + user guide) updated to reflect HTTPS-since-v0.4.0.",
    ],
  },
  {
    version: "0.6.21",
    date: "2026-05-19",
    title:
      "Fresh installs got 404 on /api/v1/jobs because the route handlers only registered when manifest.yaml declared at least one job. The /jobs/new UI page couldn't create the first job. Catch-22 closed.",
    highlights: [
      "`bundles/spark/manifest.yaml` ships with `jobs: []`. main.py gated scheduler construction + register_job_routes() inside `if defs:`. Empty defs → routes never registered.",
      "Operators hitting /jobs/new for the first time POSTed to /api/v1/jobs and got 404, with no clean error message. The only workaround was editing manifest.yaml by hand or dropping a YAML file into /app/data/jobs/.",
      "Same fix-shape as the v0.3.11 dispatcher fix one block above in main.py. Pre-v0.3.11 the dispatcher had the same conditional gate; that was fixed but the sibling scheduler+routes path was left.",
      "v0.6.21: construct scheduler + register routes + start scheduler unconditionally. The asyncio loop is cheap when there are no jobs to fire (periodic poll). POST /api/v1/jobs mid-process now picks up the new job immediately, no MCP restart.",
      "Verified via post-v0.6.20 broad smoke sweep of all /api/agent/* endpoints — same sweep also surfaced /api/agent/reports 502 + detections UI gap (separate releases coming).",
    ],
  },
  {
    version: "0.6.20",
    date: "2026-05-19",
    title:
      "phantom-connector-cortex-xdr was missing from the release manifest AND the dev-installer digest loop since v0.5.61. Surfaced when an operator restart of cortex-xdr fell to tag-pinning and tried to pull `:dev-<sha>` — a tag that only exists when build-connectors fires for that commit.",
    highlights: [
      "cortex-xdr was added in v0.5.61 with build-connectors.yml properly extended to build the image. But release.yml + build-dev-installer.yml were never updated to include it in the digest-pinning plumbing.",
      "Every customer release manifest since v0.5.61 has shipped without DIGEST_PHANTOM_CONNECTOR_CORTEX_XDR. Every dev manifest since v0.5.61 has shipped without it too.",
      "Didn't surface immediately because the FIRST instance creation happened during a release that had just pushed the connector image, so tag-pinning worked at that moment. The restart that fired today (commit 321d002 = v0.6.18) tried to pull a tag that didn't exist for this dev cycle, and failed.",
      "v0.6.20 adds cortex-xdr to release.yml's IMAGES array, changed-detection, first-release defaults, runtime-rebuild force list, outputs, rebuild-decisions summary table, and a new build-or-retag step (with a first-release fallback that builds from source if PREV_V tag doesn't exist).",
      "Also fixed a pre-existing summary-table gap — cortex-content was missing from the workflow rebuild-decisions table (the decision still HAPPENED, but operators couldn't see it in the summary). Both rows now rendered explicitly.",
      "Forward discipline: when adding a new connector, update release.yml (5 sites) + build-dev-installer.yml (1 site, 2 line changes). A 'how to add a connector' section in docs/CICD.md is the next follow-up.",
    ],
  },
  {
    version: "0.6.19",
    date: "2026-05-19",
    title:
      "Single-instance GET (/api/v1/instances/{id}) now honors ?include_secrets=true — symmetric with the list endpoint. Pre-v0.6.19 the single GET always redacted, even with the right bearer token + query param.",
    highlights: [
      "v0.1.36 added ?include_secrets=true to the LIST endpoint for the backup flow. The single-instance GET handler was missed and kept hard-coding the redact-by-default _instance_to_dict() call.",
      "No customer impact in practice (the UI uses the list endpoint), but the asymmetry blocked future features like single-instance migration export.",
      "Per v0.5.80 audit rule 7: write-style endpoints (POST create, PATCH update, POST test/probe) intentionally left redacted — caller just supplied the secrets in the request body, so echoing redacted '***' is the right security default. Documented in CHANGELOG.",
      "Agent UI proxy needs no change — proxyToMcp already forwards the query string.",
    ],
  },
  {
    version: "0.6.18",
    date: "2026-05-19",
    title:
      "Bug-family audit completion for the v0.6.17 KEK fix — PHANTOM_AGENT_INTERNAL_URL + PHANTOM_TLS_VERIFY were reading from os.environ too, silently ignoring operator .env overrides.",
    highlights: [
      "v0.6.17 fixed PHANTOM_SECRET_KEK by switching to _host_env_get() (reads /host/.env directly). CLAUDE.md § 'Bug-family audit (v0.5.80)' mandates that sibling instances of the same pattern get audited in the same release-discipline window.",
      "Audit found two more hits: _agent_tls_verify() and _resolve_agent_internal_url() both read PHANTOM_AGENT_INTERNAL_URL / PHANTOM_TLS_VERIFY from os.environ. The compose phantom-updater.environment block intentionally doesn't pass them through (v0.5.51 env-block stability invariant), so any operator .env override was a silent no-op.",
      "Dormant rather than active — the defaults always work; no customer impact today. But the override paths were silently broken. v0.6.18 closes the audit.",
      "Three call sites swapped to _host_env_get(). Post-audit grep returns zero hits for the bug-family. PHANTOM_REGISTRY* env reads remain os.environ.get() intentionally (passed through compose for docker login at boot) — documented in CHANGELOG.",
    ],
  },
  {
    version: "0.6.17",
    date: "2026-05-19",
    title:
      "phantom-updater was passing EMPTY PHANTOM_SECRET_KEK to spawned connector containers since v0.5.51, so all instance secrets resolved to empty strings. Layer-6 of the kill-chain unblock chain; fixes 'no apiKey configured' error after v0.6.16.",
    highlights: [
      "After v0.6.16 made dev-cycle connector images flow through, the Caldera connector container pulled the new image — only to fail at the next layer: 'caldera instance has no apiKey configured.' SecretStore actually had a 32-char apiKey.",
      "Host KEK length: 43 (real). Container KEK length: 0 (empty). Connector-runtime log: 'PHANTOM_SECRET_KEK is not set on this connector container.'",
      "Root cause: updater/src/main.py:1860 read PHANTOM_SECRET_KEK from os.environ. But compose phantom-updater.environment INTENTIONALLY doesn't pass it (per v0.5.51's env-block stability invariant — any change there forces phantom-updater recreate). So os.environ.get() returned empty.",
      "Latent since v0.5.51. Surfaced now because v0.6.x finally exercised the connector-container start path end-to-end.",
      "Fix: read PHANTOM_SECRET_KEK from /host/.env via _host_env_get() — same pattern as PHANTOM_VERSION / DIGEST_PHANTOM_* reads. Preserves env-block stability invariant AND propagates KEK correctly.",
      "Six-layer kill-chain unblock chain: v0.6.11/13/14 (agent-URL fix chain) → v0.6.15 (config-key alignment) → v0.6.16 (connector-image flow) → v0.6.17 (secret-decryption propagation). Next: test caldera dispatch + kill chain end-to-end.",
    ],
  },
  {
    version: "0.6.16",
    date: "2026-05-19",
    title:
      "Bring per-connector images into the dev cycle. Pre-v0.6.16 the dev manifest pinned connector digests to the LATEST CUSTOMER RELEASE; build-connectors.yml could push fresh :dev tags but phantom-updater would still pull the stable digest. Same class of issue as v0.6.12 (phantom-updater not in dev cycle) — fixed for one image, repeated for seven.",
    highlights: [
      "Surfaced after v0.6.15: the new Caldera connector image with calderaUrl fallback was pushed to :dev, but when phantom-updater restarted the operator's instance container, it pulled the SAME old v0.6.4 digest. Caldera dispatch still failed.",
      "Root cause: build-dev-installer.yml's connector-digest resolution fetched from the latest stable release manifest, NOT from :dev tags. So /opt/phantom/connector-digests.env always carried customer-release digests.",
      "Fix: build-dev-installer.yml's connector loop now docker-pulls each :dev tag and captures the digest; falls back to stable manifest only when :dev doesn't exist (bootstrap case). Same pattern as agent/xlog/caldera/updater.",
      "Net effect: changes to bundles/spark/connectors/<id>/src/* now flow through to phantom-vm. build-connectors.yml builds → dev manifest carries the digest → connector-digests.env gets it → next instance restart pulls the new image. Closes the dev-cycle gap for the last 7 images.",
      "This is layer-5 of the kill-chain unblock chain (v0.6.11/13/14/15 fixed the agent-URL + config-key path; v0.6.16 fixes the connector-image-flow path).",
    ],
  },
  {
    version: "0.6.15",
    date: "2026-05-19",
    title:
      "Marketplace catalog drift fix: calderaUrl/xlogUrl renamed to baseUrl to match connector.yaml source of truth. UI-created instances were storing the wrong config key; runtime couldn't find it. Layer-4 of the kill-chain-unblock chain.",
    highlights: [
      "After v0.6.14 made reconcile + caldera dispatch path work end-to-end, the caldera connector container came up but errored: 'caldera instance has no baseUrl configured.' Investigation: instance had config.calderaUrl but connector ran config.baseUrl resolution.",
      "Root cause: mcp/agent/app/api/marketplace/connectors/route.ts hard-codes the catalog the UI form renders. Caldera entry said name:'calderaUrl', xlog entry said name:'xlogUrl', but both connectors' connector.yaml schemas say baseUrl. Catalog drifted from the connector source of truth.",
      "Fix part 1: catalog corrected — caldera and xlog entries now declare name:'baseUrl'. Display labels unchanged.",
      "Fix part 2: runtime fallback chains accept the legacy camelCase names so operator instances created pre-v0.6.15 keep working without recreate.",
      "Deeper issue noted: marketplace catalog should be DERIVED from connector.yaml (single source of truth), not hard-coded TypeScript. Filed as follow-up. For now: any new connector entry MUST be checked against its connector.yaml.",
      "This is layer-4 of the kill-chain-unblock fix chain: v0.6.11 SSL_CERT_PEM (wrong signal) → v0.6.13 always-HTTPS → v0.6.14 verify=False default → v0.6.15 config-key alignment. Next: test caldera dispatch end-to-end + kill chain via chat.",
    ],
  },
  {
    version: "0.6.14",
    date: "2026-05-19",
    title:
      "Layer-3 of the agent-URL fix chain: default verify=False on the compose-internal HTTPS URL. v0.6.13 got past TLS handshake; v0.6.14 gets past cert chain verification (which can never succeed against a self-signed cert).",
    highlights: [
      "After v0.6.13 deployed (always-HTTPS): reconcile got 'SSL: CERTIFICATE_VERIFY_FAILED: self-signed certificate.' The call sites read PHANTOM_TLS_VERIFY with default '1' → verify=True against a self-signed cert → never succeeds.",
      "Architectural fact: intra-cluster trust boundary is the docker network alias (only the legitimate phantom-agent container answers on that DNS name), NOT the cert chain. The cert exists to encrypt the wire, not authenticate the host. So verify=False is correct for the default compose-internal URL.",
      "Fix: new _agent_tls_verify() helper. Default URL → verify=False unconditionally. Operator-overridden PHANTOM_AGENT_INTERNAL_URL → honors PHANTOM_TLS_VERIFY env so CA-fronted deployments can opt-in to chain validation.",
      "Two call sites updated to use the helper instead of inline env reads (instance container_url PUT + reconcile's /api/v1/instances fetch).",
      "Three-layer fix chain rolled out across v0.6.11 → v0.6.13 → v0.6.14. Each layer was an empirical discovery from the previous deploy. This is the architectural truth, not a workaround.",
    ],
  },
  {
    version: "0.6.13",
    date: "2026-05-19",
    title:
      "Correction to v0.6.11's TLS detection: the agent is unconditionally HTTPS on port 8080; the previous SSL_CERT_PEM-based check was looking at the wrong signal. v0.6.13 simplifies to always-https. Closes the actual reconcile / per-connector audit issue.",
    highlights: [
      "v0.6.11 added _resolve_agent_internal_url() that derived http vs https from /host/.env's SSL_CERT_PEM. Testing on the new v0.6.12 dev cycle revealed the bug: SSL_CERT_PEM is empty in nearly all installs (the agent's entrypoint auto-generates a self-signed cert at /tls/cert.pem instead).",
      "So v0.6.11 always fell into the http branch on customer + dev installs. Hit the TLS proxy. Got the SAME 'Server disconnected without sending a response' error. Empirically verified: curl http://phantom-agent:8080 → Empty reply; curl -k https://phantom-agent:8080 → TLS handshake succeeds.",
      "v0.6.13 fix: _resolve_agent_internal_url() always returns https://phantom-agent:8080 (or the PHANTOM_AGENT_INTERNAL_URL operator override). No more env-based derivation. The agent is HTTPS in v0.4.0+, period.",
      "Per CLAUDE.md § 'Rule 3 — Derive runtime state from observable evidence, not env vars that mid-process scripts mutate' (v0.4.0 retrospective): v0.6.11 used env (wrong). v0.6.13 uses an architectural fact (phantom-agent:8080 = always HTTPS).",
      "TLS verify=False at call sites is correct because the agent's cert is self-signed; trust boundary is at the compose network edge, not the cert chain.",
      "This unblocks POST /api/v1/connectors/reconcile + per-connector audit URL writes. Next: test reconcile on phantom-vm; recreate Caldera instance; verify caldera tools dispatch; run kill chain.",
    ],
  },
  {
    version: "0.6.12",
    date: "2026-05-19",
    title:
      "Bring phantom-updater into the dev cycle. Customer-release is no longer the only path to test updater changes — fixes the design gap that forced 'approve a customer release just to test untested updater code'.",
    highlights: [
      "Operator caught the design flaw during v0.6.11 testing: pre-v0.6.12 the only way to test phantom-updater code changes was to cut a customer release tag (which then triggered release.yml to build the image). That made customer releases the ITERATION mechanism, not the FINAL step. Violates the 'release only what's verified' principle.",
      "Root cause: there was no build-updater.yml. The 4 per-service dev workflows (agent/xlog/caldera/connectors) rebuild on every source push; updater was conspicuously absent. build-dev-installer.yml fetched updater's digest from the LATEST CUSTOMER RELEASE instead of :dev.",
      "Fix: new .github/workflows/build-updater.yml mirrors build-agent.yml — triggers on updater/** source changes, builds + pushes phantom-updater:dev. build-dev-installer.yml's workflow_run cascade list adds 'Build updater'; the :dev digest resolution loop adds phantom-updater alongside agent/xlog/caldera; the 'fetch from latest stable' block removes phantom-updater (only browser remains there).",
      "Risk: symmetric to agent/xlog/caldera dev builds. A bug in updater could break the dev install on phantom-vm. Mitigation: customer installs are unaffected because release.yml still builds updater independently on tag push. The dev cycle gives us a chance to CATCH bugs before customers do.",
      "Unblocks v0.6.11 testing: phantom-updater's TLS-aware agent URL fix (line 1620 / 1763 / 2036) can finally be exercised on phantom-vm without a customer-release tag. Push triggers rebuild → auto-deploy → reconcile works → caldera recreate works → kill chain fires.",
    ],
  },
  {
    version: "0.6.11",
    date: "2026-05-19",
    title:
      "phantom-updater TLS-incompat fix — was hard-coding http://phantom-agent:8080 for three agent calls (instance container_url update, reconcile, per-connector audit). v0.4.0+ the agent runs behind a TLS proxy on that port so plain HTTP requests failed silently. Closes the last gap in the v0.6.7 architectural chain.",
    highlights: [
      "Surfaced during v0.6.7 connector-digest reconcile testing: operator hit POST /api/v1/connectors/reconcile and got back '502: could not list instances from agent: Server disconnected without sending a response.' That error came from TLS handshake rejection of plain HTTP traffic.",
      "Latent v0.4.0 bug that never surfaced because the instance container_url update path was tolerated by retry semantics, the audit-row writes were fire-and-forget that operators never saw failing, and the reconcile path was net-new and only exercised today.",
      "Fix: new _resolve_agent_internal_url() helper. Derives scheme from observable state per CLAUDE.md § 'Rule 3' (v0.4.0 retrospective): honors PHANTOM_AGENT_INTERNAL_URL env override if explicit, otherwise reads /host/.env's SSL_CERT_PEM (non-empty → https, empty → http).",
      "Three call-site replacements: instance container_url update (line 1620), reconcile instances fetch (line 2036), per-connector container's PHANTOM_AUDIT_URL inheritance (line 1763).",
      "Customer upgrade: install v0.6.11 — phantom-updater gets the new helper. After install, reconcile works on TLS installs, per-connector audit writes route correctly. This is what unblocks the kill-chain end-to-end test: v0.6.7 added the connector-digests reader, v0.6.11 lets phantom-updater actually talk to the agent over TLS.",
    ],
  },
  {
    version: "0.6.10",
    date: "2026-05-19",
    title:
      "Sweep four more display-purpose endpoints to remove default truncation limits, same principle as v0.6.6's chat-session limit fix. Audit log + runtime events + detection fires + benchmark runs all silently truncated past their default ceilings; now unlimited by default with explicit ?limit=N pagination opt-in.",
    highlights: [
      "v0.6.6 codified the rule: display-purpose fetch endpoints have no default limit. v0.6.6 fixed chat session history + session list. Audit revealed four more surfaces with the same anti-pattern.",
      "audit_log.query() — pre-v0.6.10 limit=100 + min(limit, 1000) hard cap → /observability/events audit table silently truncated past 100 rows. Now unlimited by default.",
      "event_log.query() — pre-v0.6.10 limit=100 → runtime events truncated past 100. Now unlimited.",
      "detection_inventory.list_fires() — pre-v0.6.10 limit=100 + min(limit, 1000) cap → recent fires view truncated. Now unlimited. list_rules() also unbounded (was 200/500).",
      "/api/v1/bench/runs + BenchmarkStore.list_recent() — pre-v0.6.10 limit=20 → benchmark history truncated past 20 runs. Now unlimited.",
      "What's still bounded INTENTIONALLY: audit SSE backfill (operational replay; 50/200 stays), personality history (retention cap, not display cap), agent_definitions.max_turns (subagent execution bound).",
    ],
  },
  {
    version: "0.6.9",
    date: "2026-05-19",
    title:
      "Fix /models page rendering empty even when Vertex is fully configured. Route was checking field names from the pre-v0.1.34 provider model that don't exist on the current EffectiveRuntimeConfig.",
    highlights: [
      "Symptom: /models page shows 'configure provider first' even on installs with a working Vertex provider instance + actively-used Gemini chat. /api/agent/models returns [] every time.",
      "Root cause: route checked `cfg.vertexProjectId` + `cfg.vertexServiceAccountJson` — fields that DON'T EXIST on EffectiveRuntimeConfig. Leftover from the pre-v0.1.34 setup.json era. At runtime both were undefined; truthy check always failed.",
      "Fix: check `cfg.GOOGLE_APPLICATION_CREDENTIALS` (populated by resolveVertexCredentialsFromStore from the MCP-side ProviderStore) and `cfg.GEMINI_API_KEY` (direct-API-key auth path). Either path enables the Gemini model catalog.",
      "Verified post-auto-deploy: /api/agent/models now returns 6 model entries (Gemini 3.1 Pro Preview, 3.0 Pro, 2.5 Pro / Flash, etc.) instead of [].",
      "Customer upgrade: install v0.6.9 — no volume changes, no schema changes. /models page renders the catalog immediately after install.",
    ],
  },
  {
    version: "0.6.8",
    date: "2026-05-19",
    title:
      "Auto-deploy + agent-smoke contract — dev iteration collapses build → install → smoke into one continuous workflow. Per-push manual install step is gone. Customer release flow is unchanged.",
    highlights: [
      "Pre-v0.6.8 dev cycle: push → wait for build → operator manually runs `sudo /home/ayman/phantom-installer-dev` → operator pings agent → agent smokes. Three failure modes: (1) operator forgets to re-install, (2) version skew between deployed code and smoke-test target, (3) wasted operator time per push.",
      "v0.6.8 change: build-dev-installer.yml gains a new step after staging the binary. It runs `sudo /home/ayman/phantom-installer-dev` itself. The self-hosted runner IS phantom-vm running as ayman with NOPASSWD sudo (per docs/CICD.md § Install location) — no SSH, no extra credentials.",
      "Customer flow unchanged: customer-release tags still require explicit operator approval in chat. Customer installs still happen via `sudo /opt/phantom/phantom-installer` driven by the customer. Auto-deploy is a dev-cycle-only mechanic.",
      "docs/CICD.md gains two new sections under § Workflow file layout: `Auto-deploy contract (v0.6.8+ — dev cycle only)` codifies the workflow step + safety properties + forbidden list, `Post-auto-deploy agent smoke contract (v0.6.8+)` documents the agent-behavior expectation.",
      "CLAUDE.md § Agent-side headless smoke updated with v0.6.8 timing addendum: smoke now runs against the auto-deployed install (verified-current), structurally eliminating the version-skew risk that motivated the v0.5.75 reckoning.",
      "Trade-off: ~10s recreate window per push instead of operator-chosen timing for re-install. Acceptable for dev iteration; customer flow has no recreate windows at all.",
    ],
  },
  {
    version: "0.6.7",
    date: "2026-05-18",
    title:
      "Architectural cleanup — decouple per-connector image digests from /opt/phantom/.env per the operator config-file separation principle. Closes #55. Operator discovered during v0.6.6 chat testing that the Caldera connector container wasn't starting; root cause was a design violation where connector image refs (which aren't docker-compose substitutions) were being written to .env alongside service credentials.",
    highlights: [
      "The principle (now codified in CLAUDE.md § Operator config-file separation): .env is for service credentials + the 5 core compose-substitution digests that docker-compose interpolates. Per-connector image refs are NOT compose substitutions — they're runtime data phantom-updater uses to spawn dynamic instance containers. They live in a dedicated file at /opt/phantom/connector-digests.env.",
      "phantom-updater change: new reader _read_host_connector_digests_env() reads /host/connector-digests.env. _connector_digest() reads from there. Backward-compat: falls back to /host/.env for the transition window (operators upgrading from pre-v0.6.7), with a one-shot deprecation warning per process.",
      "phantom-installer change: applying the embedded manifest now splits writes — PHANTOM_VERSION + 5 core stack-service digests + everything non-connector stays in .env; DIGEST_PHANTOM_CONNECTOR_* lines route to the new connector-digests.env file. On upgrade from pre-v0.6.7 installs, the existing strip pattern removes legacy connector digests from .env automatically.",
      "build-dev-installer.yml change: the dev manifest now includes the 7 DIGEST_PHANTOM_CONNECTOR_* values pulled from the latest customer release. Without this, dev installs leave operators without connector image refs and phantom-updater can't pull connector images (the bug that surfaced as 'no tool matched caldera_get_all_agents' during v0.6.6 testing).",
      "Customer upgrade: install v0.6.7 — installer applies the new file layout automatically. After install: `sudo ls -la /opt/phantom/connector-digests.env` (NEW file) + `sudo grep ^DIGEST_PHANTOM_CONNECTOR_ /opt/phantom/.env` (should be empty). Recreate any connector instance via /instances and the container should start cleanly.",
      "Stacks on top of v0.6.6 (chat session reliability fixes). v0.6.6 + v0.6.7 can be tagged together; the diff is independent.",
    ],
  },
  {
    version: "0.6.6",
    date: "2026-05-18",
    title:
      "Chat session reliability — remove every default truncation in the transcript loader (compaction is the only context-window manager), surface silent export failures, add live-telemetry export, add operator-visible subagent toggle in the chat header.",
    highlights: [
      "Removed default limits: pre-v0.6.6 the chat data path had THREE different limit defaults (MCP get_history hard-capped at 1000 with default 100; agent transcript loader inherited 100; agent telemetry rehydrate passed ?limit=500; export passed limit=10_000). Long sessions silently lost bubbles on reload. v0.6.6 — every layer defaults to 'no limit'; pagination is an explicit opt-in. The MCP get_history + list_sessions signatures take `limit: int | None = None` and use SQLite LIMIT -1 for unlimited. Agent-side TS callers drop their ?limit= query params. The principle: compaction (`lib/compaction.ts`) is the only legitimate context-window manager. Limits are a pagination knob, never a default ceiling.",
      "Export silent-failure fix: handleExportSession in app/page.tsx swallowed `result.ok === false` with no operator feedback. Click Export → nothing happened. v0.6.6 surfaces failures via window.alert + console.error. A proper toast primitive is a follow-up; window.alert is the chosen unmissable escape hatch.",
      "Live telemetry export (new): the chat DebugPanel (right rail) gains a download button next to Clear. Exports the in-memory toolCalls + events arrays as live-telemetry-{sessionId}-{ts}.json. Captures streaming-only signals (text_delta cadence, run-id boundaries) that the session 'events' export CAN'T see because those aren't persisted to messages. Disabled when both arrays are empty.",
      "Subagent toggle (new): chat header gains a group/person icon toggle. Default ON (current behavior). When OFF: chat route omits SUBAGENT_CREATE_TOOL_SPEC from the catalog the model sees AND gates the dispatcher defensively (synthesizes denied_by:operator_preference if model still invokes it). Persisted to operator_state.db at key chat_subagents_enabled — operator-personal preference per CLAUDE.md three-category state model; survives reload + follows the operator across devices.",
      "Cache shape changes (internal): pre-v0.6.6, getGeminiTools() cached the full declaration list including subagent_create. v0.6.6 caches the BASE list (MCP tools only) and adds subagent_create per-request based on the toggle. Toggling takes effect on the next turn without waiting for cache TTL eviction.",
      "Customer upgrade: install v0.6.6 — no volume changes, no schema changes; secrets + KEK + operator state preserved across the upgrade. Storage backward-compatible. The chat header gains a new toggle button after install. Long chat sessions reload completely. Closes #54. v0.6.5 (installer text fix) still in-flight at status:ready-for-testing — v0.6.6 stacks on top.",
    ],
  },
  {
    version: "0.6.5",
    date: "2026-05-18",
    title:
      "Installer cleanup — fix stale \"Update button in the UI sidebar\" message that referenced a path removed in v0.5.20. Customers now see correct upgrade guidance at the end of every install + upgrade.",
    highlights: [
      "Bug: the phantom-installer's success message has told operators 'Future updates: use the Update button in the UI sidebar (no need to re-run this installer)' since pre-v0.5.20. That UI button was removed in v0.5.20 — there is no in-UI upgrade path; customer upgrades happen via the installer ONLY (per docs/CICD.md § v0.5.20 model correction). Stale message was misleading customers into looking for a button that doesn't exist OR skipping the installer at upgrade time and silently staying on stale code.",
      "Fix: replaced the 2-line stale block at installer/phantom-installer.template.sh:1105-1106 with ~10 lines of correct guidance — 'download the new phantom-installer binary from the GitHub Releases page and run it with sudo on this host. The installer detects the existing install at /opt/phantom and preserves your secrets, KEK material, and operator state across upgrades — only image digests + the docker-compose.yml are refreshed.' Includes the releases URL inline and the 'no in-UI Update button by design' rule.",
      "What does NOT change: installer behavior is identical (still detects /opt/phantom, preserves secrets, refreshes digest manifest in place). Only the closing message text changes. All other docs surfaces (/help/architecture, /help/user#upgrades, docs/CICD.md, docs/cicd-pipeline.svg) were already correct — this was the last live stale 'Update button' reference in the repo.",
      "Customer upgrade: install v0.6.5 — download the new phantom-installer binary from this release page and run with sudo. The corrected closing message will appear at the end of every subsequent install + upgrade.",
      "All other image digests (caldera / xlog / connectors / updater / browser) are byte-identical to v0.6.4 — only phantom-agent + phantom-installer change between v0.6.4 and v0.6.5. Closes #53.",
    ],
  },
  {
    version: "0.6.4",
    date: "2026-05-18",
    title:
      "Hotfix continuation — v0.6.3's fix is correct but the v0.6.0-v0.6.3 vanilla-retag chain needed a content-touch to break out. v0.6.4 finally ships Phantom plugin content to customers.",
    highlights: [
      "Background: v0.6.3 fixed release.yml to pull :dev (overlay-correct) instead of vanilla rebuild when CHANGED=1. But between v0.6.2 → v0.6.3 commits, only workflow + docs files changed (no caldera-content), so detection correctly said 'unchanged' and retagged v0.6.2's (vanilla) digest as v0.6.3.",
      "v0.6.4 fix: adds a marker tag (`v0.6.4-broke-vanilla-retag-chain`) to phantom-master-killchain.yml. The detection fires CHANGED=1, release.yml's v0.6.3 pull-from-:dev logic kicks in, and customers finally get a caldera image with actual Phantom content.",
      "Customer upgrade: install v0.6.4 phantom-installer. Open Caldera UI → Adversaries → confirm 'Phantom: Master Killchain' is visible (with the v0.6.4-broke-vanilla-retag-chain tag in its tags list, which is the marker that proves you're on a real Phantom-content image, not the vanilla chain).",
      "Future v0.6.x patches that don't touch caldera-content will retag v0.6.4's (CORRECT) digest forward — same caldera-state-preservation behavior as designed, just from a non-vanilla baseline.",
      "All other image digests (agent / xlog / connectors / updater / browser) are byte-identical to v0.6.3 — only phantom-caldera changes between v0.6.3 and v0.6.4. Same as the v0.6.0 → v0.6.1 → v0.6.2 → v0.6.3 chain.",
    ],
  },
  {
    version: "0.6.3",
    date: "2026-05-18",
    title:
      "Critical hotfix — FIRST customer release that actually ships Phantom plugin content in the caldera image. v0.5.57 through v0.6.2 all shipped vanilla aymanam-style Caldera.",
    highlights: [
      "If you installed v0.5.57 through v0.6.2, your caldera image is vanilla Caldera with NO Phantom adversaries. v0.6.3 finally ships the actual content. Download + install v0.6.3 to get Phantom Master Killchain / Ransack / Super Spy / Thief / Lateral Movement Sweep + CTID emu plans + phishing v3.3 dropper + T1518.001 modern PSh discovery.",
      "Two layers of bugs were uncovered in release.yml — v0.6.1 fixed detection (the path-mapping missed bundles/spark/caldera-content/), v0.6.2's CHANGED=1 rebuild then ran but produced vanilla output because release.yml's docker build step had no overlay logic (overlay lives only in build-caldera.yml).",
      "v0.6.3 fix: release.yml now pulls the :dev caldera image (which build-caldera.yml correctly builds with the Phantom + CTID overlay) and retags it as :vX.Y.Z. Single source of truth for caldera content. Falls back to vanilla rebuild only if :dev pull fails.",
      "Verification after install: open Caldera UI → Adversaries → confirm \"Phantom: Master Killchain\" + 4 other Phantom adversaries are visible. If missing, you're on a vanilla image — re-run the v0.6.3 installer.",
      "docs/CICD.md failure-mode catalog entry #13 extended with both layers of the bug + the v0.6.3 fix design (\"single source of truth: build-caldera.yml\").",
      "All other image digests (agent / xlog / connectors / updater / browser) are byte-identical to v0.6.2 — only phantom-caldera changes between v0.6.2 and v0.6.3.",
    ],
  },
  {
    version: "0.6.2",
    date: "2026-05-18",
    title:
      "Hotfix — republish caldera image with the v0.6.1 content. v0.6.1's release.yml retagged v0.6.0 caldera digest silently (per-service path detection missed bundles/spark/caldera-content/).",
    highlights: [
      "If you installed v0.6.1, download + install v0.6.2 to get the actual phishing v3.3 + #52 fix content. v0.6.1's caldera image is byte-identical to v0.6.0 — none of the v3.3 phishing dropper or T1518.001 PSh discovery changes shipped.",
      "Root cause: release.yml's per-service detection only watched third_party/caldera/ (the submodule path), missing the content overlay at bundles/spark/caldera-content/. build-caldera.yml already includes both paths, so :dev was fresh, but release.yml's retag-vs-rebuild logic took the retag path.",
      "Fix: CALDERA=$(changed third_party/caldera/ bundles/spark/caldera-content/). Now both paths trigger a customer-release rebuild.",
      "All other image digests (agent / xlog / connectors / updater / browser) are byte-identical to v0.6.1 — only phantom-caldera changes between v0.6.1 and v0.6.2.",
      "docs/CICD.md failure-mode catalog entry #13 added: \"release.yml per-service path-detection misses overlay content directory.\" Prevention: when adding overlay paths to a build-*.yml trigger, ALSO add them to release.yml's detection in the same PR.",
    ],
  },
  {
    version: "0.6.1",
    date: "2026-05-18",
    title:
      "Phantom T1518.001 modern PowerShell discovery (closes #52) + dynamic Caldera-implant detection in the phishing dropper. Curated Ransack success 78.6% → 94.4% (Scenario 1).",
    highlights: [
      "Closes #52 — stockpile T1518.001 abilities (wmic AV + Get-WmiObject Firewalls) systematically fail on Win Server 2022. Replaced with Phantom multi-path discovery: Get-CimInstance SecurityCenter2 + Get-MpComputerStatus Defender + Get-Service/Get-Process filtering for known EDR names (Cortex XDR / CrowdStrike / Sentinel / Defender / Cylance / Sophos / Kaspersky / etc.). Validated: Cortex XDR cyserver enumerated by name on both lab hosts.",
      "Phantom: Identify Firewalls now uses Get-NetFirewallProfile + Get-NetFirewallRule (the original stockpile ability was mis-named — actually queried AV WMI). Returns per-profile Domain/Private/Public state + inbound/outbound rule counts. netsh fallback for hosts without NetSecurity module.",
      "Phishing v3.3 — dynamic Caldera-implant discovery via process-tree walk. v0.6.0 used a hardcoded mars/venus candidate list; v0.6.1 walks the process tree from $PID upward, skipping known interpreters until it finds the first non-interpreter ancestor (the running implant by definition). Immune to operator-renames; works for any sandcat binary name.",
      "Curated Ransack chain success rate 78.6% → 94.4% after #52 fix (4 failures eliminated). Only T1018 nltest-on-workgroup remains (env-dep, not fixable). Master Killchain re-run with v3.3 phishing produced identical 88.6% chain quality + 9 MITRE tactics + 22 techniques. Cortex incident grew 140 → 214 alerts (+74 new from the v3.3 run).",
      "Scenario 1 release — caldera image digest changes (new content baked in), agent + xlog + connectors retain v0.6.0 digests. Re-run the v0.6.1 phantom-installer. Storage backward-compatible. Volumes preserved.",
      "In Caldera UI — Phantom: Ransack (curated) + Phantom: Super Spy (curated) now show modern PowerShell discovery output with actual EDR product names. Phishing ability adapts to whatever name the operator uses for their sandcat binary.",
    ],
  },
  {
    version: "0.6.0",
    date: "2026-05-18",
    title:
      "Major release — Phantom is now a detection-validation platform end-to-end. New Master Killchain, XDR connector, phishing v3.1 dropper, curated adversary catalog (Scenario 2).",
    highlights: [
      "Phantom Master Killchain (curated, 22 steps) — flagship adversary. Combines the v0.5.57 phishing chain + Phantom decoy + PowerKatz. Validated against Cortex XDR: produces 60+ alerts across 7 MITRE tactics (Execution, Persistence, Privilege Escalation, Defense Evasion, Credential Access, Lateral Movement, C2). Use as the standard 'does my lab work' smoke test.",
      "Phishing v3.1 — Office macro drops Caldera implant. The phishing-emailclient-spawn ability now produces the FULL initial-access EDR sub-tree: WINWORD.EXE (renamed cmd, T1036.003) → cmd /c → powershell (simulated VBA macro) → BITS transfer (T1197) → implant binary drop + brief spawn (T1105 + WildFire Malware verdict). Lab-safe: invalid beacon URL means no new paw. Auto-detects venus.exe/mars.exe/sandcat.exe.",
      "Cortex XDR connector — chat agent now queries Cortex cases + issues + runs XQL queries directly. Type ^xdr_get_cases_and_issues / ^xdr_run_xql_query / ^xdr_get_incident_extra_data. Detection-validation feedback loop lives inside Phantom — no more jumping to the XDR console mid-test.",
      "Phantom-curated adversary catalog: Ransack, Super Spy, Thief, Lateral Movement Sweep, Master Killchain. Each bypasses a structural gap in stockpile adversaries (workgroup DNS PTR records, missing decoy files) so they dispatch on a clean lab. Selection guide in docs/caldera-release-plan.md.",
      "^command direct tool invocation — type ^xdr_get_cases_and_issues limit=5 in chat to call any MCP tool, bypassing the LLM. Works without a provider configured. The detection-validation loop is finally usable in dev.",
      "CTID Adversary Emulation Plans (APT29/FIN6/OilRig/etc.) baked into the caldera image. Lab-safe lookalike abilities for techniques Cortex signature-blocks. Cortex KB search via ^cortex_search.",
      "Bug fixes — 7 XDR connector instance creation bugs (v0.5.61-77 chain). Bug-family audit across caldera/xsiam/cortex-content (v0.5.80, CLAUDE.md Rule 7). Connector instance form widget vocabulary expanded to 11 types. Test Connection dirty-tracking fixed. Caldera image now reconciles phantom + ctid emu plugins at startup. /help/cicd page added with 6 SVG diagrams.",
      "Upgrade path: backward-compatible Scenario 2. Volumes preserved. Re-run the new installer (WIPE_VOLUMES=false default). New Caldera adversaries visible in Caldera UI → Adversaries. New XDR connector installs via Marketplace → cortex-xdr.",
    ],
  },
  {
    version: "0.5.80",
    date: "2026-05-17",
    title:
      "Bug-family audit — extend v0.5.77 cortex-xdr fix across caldera/xsiam/cortex-content + CLAUDE.md Rule 7 (closes #51).",
    highlights: [
      "Operator's hands-on caught the gap: ^cortex_search failed with 'no container_url' — same bug family as pre-v0.5.77 cortex-xdr. Their critique was sharp: 'you have tested one connector command, but did not review the rest to fix for the same problem, and they are related.' This release is the postmortem.",
      "Audit results: caldera + xsiam had the same `from usecase.instance_store` pattern that v0.5.77 fixed in cortex-xdr (crashes container-mode tool calls with ModuleNotFoundError). cortex-content's usecase.* refs all had try/except ImportError fallbacks (graceful) but was missing __all__. Operator's cortex_search failure was a SEPARATE bug — cortex-docs instance had never had its container started (v0.5.73 #46-bug-3 family, manually unblocked).",
      "Fixes: caldera/xsiam _get_*_config rewrote to use `from config.config import get_config` (the runtime-native config proxy). __all__ added to caldera (58 tools), xsiam (14 tools), cortex-content (10 tools). The runtime no longer falls back to auto-discovery for any bundle connector.",
      "CLAUDE.md Rule 7 (Bug-family audit) — new addendum to the v0.5.75 smoke discipline: when fixing a connector-system bug, audit sibling connectors for the same pattern in the same release. Identify the bug as a grep expression; run across all connector src/; fix every hit or document why it stays. Forbidden: fixing one connector for a bug class + walking away from the audit.",
      "/help/cicd Smoke Testing Discipline section: 'six rules' → 'seven rules'. 6th diagram (cicd-smoke-discipline.tsx) refactored — Rule 7 added as a full-width strip below the original 6-card grid, bordered with the 'shared' accent so it visually reads as the discipline ADDITION rather than an original rule. viewBox grew 880 → 920.",
      "Page route size: 19.8 kB → 20.2 kB. Same theme support; same scroll-spy.",
      "Forbidden going forward: shipping a connector with `from usecase.*` (use config.config.get_config); fixing a connector-system bug without auditing siblings (Rule 7 is the formal version). The grep test: `grep -rn 'from usecase\\.\\|import usecase\\.' bundles/spark/connectors/*/src/` — any non-fallback-wrapped match is a regression.",
    ],
  },
  {
    version: "0.5.79",
    date: "2026-05-17",
    title:
      "Add Smoke Testing Discipline section + 6th diagram to /help/cicd (closes #50). The operator-observable view of the v0.5.75 CLAUDE.md addendum.",
    highlights: [
      "Operator request: extend the new /help/cicd page with the smoke-testing concept. v0.5.78 covered the BUILD side of CI/CD; this release adds the VERIFICATION discipline that gates a release from status:in-progress to status:released.",
      "New diagram cicd-smoke-discipline.tsx has three layers: (1) label-state machine showing the five status:* labels + who flips each (3 agent-driven, 2 operator-driven); (2) the six rules of agent-side smoke from the v0.5.75 CLAUDE.md addendum laid out as cards; (3) bullet state classification (✓ ⨯ ?) + the postmortem feedback loop with concrete v0.5.75/76/77 examples.",
      "New page section 'Smoke Testing Discipline' inserted between Release Lifecycle and Customer Upgrade in the reading order. Four sub-sections: label-state machine, six rules, bullet state classification table, postmortem loop. Deep-links to the CLAUDE.md addendum for the FORBIDDEN list.",
      "Diagram cap revised from 5 (per #49) to 6 (per #50). The smoke-testing discipline is cross-cutting — applies to every release — and the existing five diagrams don't cover the label state-machine. The 6th diagram fills that gap without overwhelming the page's reference flavor.",
      "/help/cicd route size grew from 15.5 kB to 19.8 kB. Same theme support (light + dark), same TOC scroll-spy pattern. TOC sidebar now shows 8 sections (was 7).",
      "Forbidden going forward: adding a 7th diagram without operator approval (cap is now 6); duplicating the CLAUDE.md addendum's six rules verbatim in the page text (page summarizes; CLAUDE.md is the enforcement contract).",
      "Same dev-cycle gap as v0.5.78: page only ships to the running install after operator re-runs phantom-installer-dev. The agent-side probe is build-side only until then.",
    ],
  },
  {
    version: "0.5.78",
    date: "2026-05-17",
    title:
      "New /help/cicd page — 5 diagrams + operator-facing CI/CD documentation (closes #49). URL-only, deliberately not in the sidebar.",
    highlights: [
      "Distills docs/CICD.md (1000+ lines of engineering reference) into a navigable diagram-driven page readable in under 10 minutes. Five SVG diagrams cover: two installers (dev vs customer), three change scenarios decision tree, build pipeline (path filters + workflow_run cascade), release.yml lifecycle (tag-push to GitHub release), customer upgrade flow.",
      "Page accessible at /help/cicd via direct URL only — deliberately NOT added to the sidebar nav. The page is reference content the operator looks up by name when they need it; bookmarkable, linkable from chat. Adding another nav entry would crowd the primary navigation focused on operational pages (chat, jobs, providers, connectors, etc.).",
      "TOC sidebar with scroll-spy via IntersectionObserver mirrors /help/architecture's pattern. Seven sections grouped by Overview / Foundation / Build & Release / Customer Operations / Reference. Each major section pairs prose context with the relevant diagram.",
      "5 new diagram components under mcp/agent/components/diagrams/cicd-*.tsx use the existing DIAGRAM_THEME_CSS + DiagramMarkers shared theme — same light/dark toggle behavior as the /help/architecture diagrams. Visual consistency across the help pages.",
      "Reference section at the bottom: operator command cheat-sheet (re-run dev installer, run customer installer, force Scenario 3 wipe, check status, view updater logs) plus deep-link callouts to docs/CICD.md's 'Adding a new connector' checklist, failure-mode catalog, PAT recipes, and rollback procedure.",
      "CLAUDE.md rule 6a — 'no new UI page without a sidebar nav entry in the same release' — gets an explicit exception scoped here. The page's export default has an inline doc-comment naming the exception so future maintainers don't 'fix' the missing nav entry. components/sidebar.tsx is intentionally untouched.",
      "Forbidden going forward: adding /help/cicd to the sidebar without operator approval; shipping more than 5 diagrams on this page (operator capped); duplicating verbatim content from docs/CICD.md (the doc is the engineering source; the page links back for deep-dive material).",
    ],
  },
  {
    version: "0.5.77",
    date: "2026-05-17",
    title:
      "Bug 7 in the XDR chain — connector imports `usecase.instance_store` which doesn't exist in the container. Discipline caught two bugs in 30 minutes.",
    highlights: [
      "Discovered seconds after v0.5.76's smoke probe got past the function-prefix bug. The tool call dispatched successfully but the handler crashed with ModuleNotFoundError: No module named 'usecase'.",
      "Root cause: cortex-xdr connector.py (v0.5.61) did `from usecase.instance_store import instance_store` — the agent's Python tree path. Container-style connectors run in a separate container with only /app/{runtime,config,connectors,data} — NO /app/usecase/. Import crashed on every tool call.",
      "The connector-runtime already exposes a container-native config proxy: from config.config import get_config returns a _ConfigProxy over the merged instance config + secrets. _load_instance stashes it on a contextvar at boot. Connectors should use this path, not the agent-side usecase module.",
      "Fix: rewrote _get_xdr_config() to use get_config(). Returns a flat dict with all fields _get_fetcher looks up (api_url, api_id, api_key, pollIntervalSeconds, maxPollAttempts). Operator-actionable ValueError on missing keys so the chat surfaces a clean message via _wrap_xdr_call.",
      "Bug count: this is bug 7 in the XDR connector chain that started with v0.5.61. The new CLAUDE.md smoke discipline (v0.5.75) caught bugs 6 (function-prefix mismatch) and 7 (usecase import) in the SAME 30-minute probe cycle — both pre-existing since v0.5.61, six months latent. The discipline is converting invisible bugs into visible ones at the right moment.",
      "xsiam's connector.py:52 has the same import. Almost certainly broken in container mode — but xsiam runs via the agent's in-process _BUILTIN_LEGACY_TOOLS path, NOT container dispatch. Will be audited separately when xsiam gets its own end-to-end probe.",
      "Forbidden going forward: importing from usecase.* in container-side connector code (use config.config.get_config()); copying code patterns between connectors without verifying runtime-mode compatibility.",
    ],
  },
  {
    version: "0.5.76",
    date: "2026-05-17",
    title:
      "Bug 6 in the XDR chain — function-prefix vs connector-id mismatch (closes #48 amendment). FIRST release where the new smoke discipline caught a bug BEFORE the operator did.",
    highlights: [
      "Discovered during v0.5.75 end-to-end smoke probe — the very first time the new CLAUDE.md 'Agent-side headless smoke' discipline fired. cortex-xdr functions used the 'xdr_' prefix from connector.yaml's functionPrefix, but phantom-connector-runtime's prefix-stripping logic only knew about phantom_<connector_id>_, <connector_id>_, and phantom_ patterns. None matched 'xdr_' for connector_id=cortex-xdr. Container registered tools as xdr_get_cases_and_issues, agent proxy called bare 'get_cases_and_issues', mismatch → 'Unknown tool' on every call.",
      "Fix 1 — connector.py: renamed 4 public functions in cortex-xdr to drop the xdr_ prefix. Bare function names sidestep the strip entirely. The agent still registers xdr_*-prefixed aliases via connector.yaml's functionPrefix; only the container-side registration changes.",
      "Fix 2 — phantom-connector-runtime entrypoint: belt + suspenders. New 4th strip rule auto-detects the longest common prefix among the tool names being registered. Conservative: requires ≥2 names, prefix must end in '_', length ≥3 chars, doesn't double-strip already-handled patterns. For cortex-docs (cortex_search/suggest/fetch_topic/...) the common prefix 'cortex_' is detected + stripped — unblocks the namespace-style alias (cortex-docs.search) end-to-end through the agent → container path.",
      "Same latent bug existed for cortex-content (cortex_ prefix vs cortex-content_ connector_id) + would have surfaced on any future connector whose functionPrefix doesn't match a 'stem'-derived strip rule.",
      "Postmortem-driven discipline growth working: v0.5.75 shipped the CLAUDE.md addendum CLAIMING I'd run agent-side end-to-end probes. v0.5.76 is the first release where I actually did so + the probe caught a bug BEFORE the operator's hands-on. The contract is producing observable behavior change.",
      "Forbidden going forward: adding a connector whose functionPrefix doesn't match <connector_id>_ without verifying the runtime's common-prefix detection covers it; shipping a v0.5.x patch without running the agent-side end-to-end probe (CLAUDE.md rule 3).",
      "Critical observation: this bug existed since v0.5.61 (cortex-xdr connector intro) — six months of latent breakage. The XDR connector was never end-to-end functional, even on customer releases. The discipline gap was equally old; the discipline fix is the same age (today).",
    ],
  },
  {
    version: "0.5.75",
    date: "2026-05-17",
    title:
      "Two latent XDR connector bugs + a CLAUDE.md smoke-discipline reckoning (closes #48). The discipline addendum is the load-bearing change — prevents the next five-in-a-row bug stretch.",
    highlights: [
      "Bug 1: cortex-xdr connector container crashed at boot with 'Functions with *args are not supported as tools'. Root cause: _wrap_xdr_call's wrapper had a *args signature, and the decorator set wrapper.__name__/__doc__ manually instead of using functools.wraps. Without __wrapped__, inspect.signature didn't unwrap to the original typed signature; fastmcp refused to register. Fix: @functools.wraps(fn) + explicit __all__ in connector.py.",
      "Bug 2: agent passed the operator-typed instance display name verbatim to phantom-updater's path validation, which rejects spaces, slashes, accents via ^[a-zA-Z0-9_-]+$. Operator named their instance 'Cortex XDR' → updater rejected 'Cortex%20XDR'/start with HTTP 400. Fix: new _slug_instance_name helper in instances.py; the agent slugs the name before calling updater. Display name in storage stays original; only the docker container name + URL path use the slug.",
      "CLAUDE.md addendum — the meta-fix. Operator caught five basic bugs in a row at hands-on time (v0.5.67/70/73/74 + #48). Root cause was process: my 'headless smoke' had been API-shape checks only (tsc/lint/build), not actual end-to-end execution against phantom-vm. The CLAUDE.md ceremony said status:dev-built → agent runs headless smoke → status:ready-for-testing. I was skipping step 2.",
      "Six new rules in 'Agent-side headless smoke' section: (1) execute each bullet I author through the tunnel, not just trace it; (2) state verification on every X-happens bullet (GET after POST, not just submit-clicked); (3) end-to-end probe required for connector-system changes (POST /instances/<id>/test + tools/call round-trip); (4) dev-cycle gaps LEAD the smoke matrix, never buried in prose; (5) bullets get inline state-classification (✓ agent-verified / ⨯ agent-verified-blocked / ? agent-skipped); (6) postmortem-driven discipline growth — every missed bug spawns a CLAUDE.md addendum.",
      "Forbidden going forward: claiming ready-for-testing without ≥1 end-to-end probe per touched subsystem; burying dev-cycle gaps in prose; authoring 'verify the feature works' bullets without naming the surface + pass signal; skipping state-verification on persistence-touching releases.",
      "Operator-side bonus: instance names with problematic characters (spaces, accents, '#', '/') now work end-to-end. Docker container name is slugged, but the UI display name is the original. Previously the form accepted these but the container never spawned — a silent failure mode that contributed to the v0.5.74 confusion.",
    ],
  },
  {
    version: "0.5.74",
    date: "2026-05-17",
    title:
      "Chat input ^command — direct tool invocation that bypasses the LLM (closes #47). Works without a provider configured.",
    highlights: [
      "New escape hatch: chat messages starting with ^ are treated as direct tool calls, NOT chat messages to the model. Example: ^get_cases_and_issues limit=10 runs the tool directly and returns raw JSON in a code block. No LLM, no system prompt, no planner.",
      "Critical property: works even when no provider (Vertex / Gemini) is configured. Direct dispatch doesn't need an LLM. First-class debug surface for fresh installs — operators can validate connectors before configuring a model.",
      "Syntax supports three arg styles: key=value pairs (^toolname limit=10 status=new), quoted strings for whitespace (^toolname query='dataset = xdr_data | limit 5'), and JSON literals for structured args (^toolname {\"severity\":[\"high\",\"critical\"],\"limit\":3}). Auto-typing: true/false → bool; null → null; integer/decimal → number; everything else stays string (ISO timestamps, UUIDs, IPs survive verbatim).",
      "Bare-name resolution: ^get_cases_and_issues resolves to xdr_get_cases_and_issues (or whichever connector ships that tool). Fully-qualified forms also work: ^cortex-xdr.get_cases_and_issues or ^xdr_get_cases_and_issues. Ambiguous matches return an error naming all candidates.",
      "New backend route POST /api/agent/tool/call talks directly to the MCP's JSON-RPC tools/call surface. Handles the initialize → notifications/initialized → tools/list → tools/call handshake transparently. 150-second timeout (covers XQL polling).",
      "Visual: user-side renders as a monospace pill with a ▸ prefix + 'direct tool call' label. Result renders as a JSON code block with the resolved tool name + duration_ms in the header. Errors get an error-tinted background. Visually distinct from chat bubbles so operators see at a glance 'this bypassed the LLM'.",
      "Use cases: validating a connector instance you just created; testing arg shapes before authoring chat prompts; pre-LLM smoke on a fresh install (deterministic, free, no model tokens); debugging connector container state.",
      "Forbidden going forward: routing ^-commands through the LLM (defeats the point); requiring provider config to call a tool; reusing /api/chat for tool-direct calls (would tangle two flows); auto-coercing args that look like dates/UUIDs/IPs (mangles them).",
    ],
  },
  {
    version: "0.5.73",
    date: "2026-05-17",
    title:
      "Three coupled connector-instance bugs uncovered during XDR end-to-end smoke (closes #46): api_key persisted to config not SecretStore; edit-dialog Test silent; phantom-updater missing cortex-xdr",
    highlights: [
      "Bug 1: CreateInstancePanel.handleSave was sending {config: configValues} — every form value including type:'secret' fields landed in plaintext config_json. Form's masked rendering was purely cosmetic; submit handler didn't honor param.type. v0.5.73 splits config/secrets buckets schema-driven and passes both to the backend.",
      "Bug 2: editFeedback banner rendered at the TOP of the scrolled dialog body while Test button lived in the BOTTOM footer. Operators clicking Test never saw the result — button flashed 'Failed'/'Connected' for 3 seconds then went back to idle. Indistinguishable from silence. v0.5.73 adds a duplicate banner above the footer + ensures every result branch sets feedback (including HTTP-error and probe-success paths that were previously banner-less).",
      "Bug 3: updater/src/main.py KNOWN_CONNECTORS was missing 'cortex-xdr'. v0.5.61 introduced the XDR connector but missed this set — phantom-updater rejected start_connector_instance with HTTP 400, no per-instance container ever spawned, tool calls failed with 'container_url — phantom-updater hasn't started the container yet'. Same family as v0.5.67's manifest.yaml miss.",
      "Pre-existing broken instances (XDR created pre-v0.5.73 with api_key in config) self-migrate via edit dialog → Save Changes (the existing PATCH-side regex correctly classifies api_key as secret). No data loss. Alternative: delete + recreate after v0.5.73 lands.",
      "docs/CICD.md 'Adding a new connector' checklist now 9 items (was 8). New row covers updater/src/main.py:KNOWN_CONNECTORS. Quick-check command extended with a second comm -23 against KNOWN_CONNECTORS so future connector authors catch the gap at commit time.",
      "Live in-cluster repair: I PATCHed the operator's broken XDR instance via /api/v1/instances/<id> — moved api_key from config to SecretStore. Probe flipped from needs-auth to connected. Tools registered after an agent restart. The remaining container-start gap requires v0.5.73's updater image; the operator will see the full end-to-end loop work after re-installing dev-installer.",
      "Forbidden going forward: shipping connector synthetic-cards with type:'secret' fields without verifying handleSave routes them; adding manifest.yaml entries without KNOWN_CONNECTORS; auto-clearing Test Connection feedback (the silent-failure trap).",
    ],
  },
  {
    version: "0.5.72",
    date: "2026-05-17",
    title:
      "XQL examples KB enrichment — 5 Cortex XDR-pattern entries + CONTRIBUTING-style README codifying the three confidence buckets (closes #37)",
    highlights: [
      "The bundled xql-examples KB (bundles/spark/kbs/xql-examples/) grew from 161 to 166 entries. Five new entries target Cortex XDR's dataset=xdr_data schema instead of the pre-v0.5.72 corpus's XSIAM/NGFW shape: 162 (recent alerts by severity), 163 (process events by hostname — the canonical Caldera-validation probe), 164 (incidents with alert counts), 165 (network egress per host — C2 hunt), 166 (process causality chain).",
      "Each entry follows a richer structure than the legacy query-block-only format: When to use (operator phrasings the agent should map here), Variations (common parameter changes), Source (the entry's confidence bucket — operator-validated / vendor-documented / pattern-derived). All five new entries are tagged xdr-pattern + v0.5.72 so the operator can grep for them and replace with operator-validated versions later.",
      "Confidence: all five are vendor-documented / pattern-derived (well-established Cortex XDR Public API patterns) but NOT yet operator-validated against a specific tenant. Each ## Source section makes that explicit. The operator's detection-validation loop (running queries against their XDR tenant) is the path to promoting them.",
      "New bundles/spark/kbs/xql-examples/README.md documents the three confidence buckets so future contributors know how to author without diluting the corpus's 'queries we know work' signal. Also covers entry shape (frontmatter + sections), local verification (docker compose restart + curl knowledge_search), and cross-references to the runtime KB impl + connector wrapper + related skills.",
      "Pairs with v0.5.69 (cortex_kb_search foundation skill — Cortex docs research discipline) + v0.5.61/68/70 (cortex-xdr connector). Together: agent searches Cortex docs → derives + runs XQL → adds validated query back to this KB. The detection-validation research loop has plumbing on both ends now.",
      "Forbidden going forward: adding unvalidated entries without the pattern-derived tag + Source disclaimer; tenant-specific field names without (tenant-specific) marking; promoting pattern-derived to operator-validated without actually running it.",
    ],
  },
  {
    version: "0.5.71",
    date: "2026-05-17",
    title:
      "/providers Test Connection button: dirty-tracking + JSON-touched gate (closes #18 — no more misleading 'no JSON configured' banner on a working install)",
    highlights: [
      "Bug from v0.2.1 upgrade smoke (bupa-engine): operator's Vertex creds were saved + working in chat, but clicking Test Connection on /providers returned 'no Vertex service-account JSON is configured yet'. The button was active immediately on page load even when no field changed; clicking it sent the backend's masked-bullet sentinel as the JSON; the test endpoint correctly refused to probe the sentinel. Misleading error on a working install undermines trust during onboarding.",
      "Fix: new canTestVertex() helper returns {ok, reason}. Checks: Project ID populated → Region populated → JSON populated → JSON differs from loaded value. The reason string becomes the disabled-button tooltip so the operator sees exactly which precondition isn't met ('Paste a Service Account JSON before testing' / 'Re-paste the Service Account JSON to test — the masked sentinel can't be probed').",
      "Brings Test onto the same dirty-tracking model Save Changes already uses (per v0.1.34's untouched-secret round-trip via the *** sentinel). Save can ship the sentinel because the backend treats it as 'leave that slot alone'; Test can't, because it must probe a real JSON. The fix codifies that asymmetry.",
      "Scope: Vertex card only. Anthropic / OpenAI / Ollama Test buttons stay unconditionally disabled (those providers are WIP). When they ship, follow the same canTest<Provider>() pattern documented in CHANGELOG.",
      "Forbidden going forward: making Test Connection accept the masked sentinel (backend correctly rejects; silently skipping would turn Test into a no-op without telling the operator); applying the canTestVertex pattern to WIP providers before they ship.",
    ],
  },
  {
    version: "0.5.70",
    date: "2026-05-17",
    title:
      "Connector instance form: widget vocabulary + Advanced Settings hack removed (cortex-xdr + xsiam now configurable; closes #45)",
    highlights: [
      "Pre-v0.5.70 the instance-creation form had three coupled bugs that made cortex-xdr and xsiam impossible to configure: API URL field had no input element (just a label + parameter-name footnote), the required API ID field was hidden behind a collapsible 'Advanced Settings' disclosure regardless of meaning, and the Create button stayed disabled because the un-fillable URL field never satisfied required-check. Operator screenshot from v0.5.67 hands-on smoke surfaced all three at once.",
      "Root cause #1 (no URL input): ConfigParam.type union was text|secret|boolean|select|array. Synthetic-card config blocks in route.ts use 'url' and 'string' for 12 fields across 4 connectors (xlog, caldera, xsiam, cortex-xdr, cortex-content). renderConfigField switch hit no matching case → returned undefined → label-only ghost. v0.5.70 expands the union to 11 widget types (text/url/string/number/secret/password/textarea/select/radio/multi_select/boolean/array).",
      "Root cause #2 (Advanced split): standardConfig=slice(0,-1) + advancedConfig=slice(-1) was an arbitrary positional hack with the comment '// simulate hidden fields'. cortex-xdr's [api_url, api_key, api_id] → api_id always landed in the collapsed Advanced disclosure. v0.5.70 deleted the entire Advanced Settings UI section + the showAdvanced state. Every field now renders in one unified Configuration section in declaration order; future advanced grouping needs a schema-level flag (widget: 'advanced'), not positional heuristics.",
      "Widget vocabulary now matches connector schema intent: url-typed fields get inputMode='url' (better mobile keyboard); password/secret render masked with eye-toggle reveal; textarea gives multiline + font-mono for JSON service-account blobs; select renders a dropdown for 4+ options; radio renders a chip-style button group for 2-3 options (when options[] is declared); multi_select renders a checkbox chip group with the selection serialized as a JSON array string; boolean is a toggle switch; array is the existing chip-list editor.",
      "Defensive default case: if a future ConfigParam.type lands in the union without a matching switch case (or if a synthetic card uses a type not yet in the union), renderConfigField falls back to a plain text input AND surfaces an error message telling the operator to fix the connector card. No more silent label-only ghosts.",
      "Docs landed in same release: help/architecture#connectors-design has a new 'Setup form widgets (v0.5.70+)' SubSection with the full 11-row widget table; help/user#connectors has a new 'The instance creation form (v0.5.70+)' SubSection at the top of the section in operator-friendly language. connector.schema.json description documents the optional widget keyword + the type→widget derivation rule (forward-looking, not yet wired to UI; UI still reads from synthetic-card config blocks).",
      "Forbidden going forward: re-introducing the slice(-1) Advanced split; adding ConfigParam.type variants without matching renderConfigField cases (the pre-v0.5.70 bug was the union growing silently while the renderer didn't); shipping synthetic cards with widget types the renderer doesn't handle (grep test in CHANGELOG for the canonical check).",
    ],
  },
  {
    version: "0.5.69",
    date: "2026-05-17",
    title:
      "Cortex KB search fully working — ported operator's 1024-line agent-guidance library + fixed fetch_topic multi-level descent (3 new skills + connector v0.3.2)",
    highlights: [
      "Operator pointed at their personal myworkassistant/cortex-assistant/cortex-docs-search skill — discovered the scripts (search.py + fetch_topic.py) were already ported into Phantom's cortex-docs connector in v0.5.55, but the 1024-line agent-guidance layer (SKILL.md + search_patterns.md + api_reference.md) was missing. The connector worked but the discipline for using it well wasn't there.",
      "Ported all three files as Phantom foundation skills: cortex_kb_search (main workflow, ~370 lines, eagerly available), cortex_kb_search_patterns (query-shaping tables + fallback strategies, ~250 lines, loadingMode: on-demand), cortex_kb_api_reference (raw Fluid Topics API spec, ~470 lines, loadingMode: on-demand). The lazy-load pattern keeps the agent context lean for non-Cortex questions.",
      "Main skill teaches: decompose multi-topic requests → strip user language for title-weighted search → use suggest first when verbs are involved (deploy → set up) → product-scope by default → fetch_topic with stub-fallback → cite sources. Plus 20+ user→Palo Alto vocabulary mappings (wipe → isolate, kill process → terminate process, scheduled task → time triggered job, etc.).",
      "Bug fix: fetch_topic_with_fallback was single-level descent only. v0.5.69 adds max_depth (default 2) for multi-level recursion. Dual threshold (operator-supplied 300 chars at top level, tight 50 chars at recursion levels) preserves thin-but-real content. Bare content kept when descent yields nothing instead of replaced with placeholder.",
      "Verified live against three cases: XDR API Reference (732 chars from single-level descent; multi-level not needed but graceful), Stages with forced multi-level stress test (128 → 2755 chars), Stages with default threshold (387 chars bare; no descent, no regression). connector.yaml + connector.py expose the new max_depth arg; connector version 0.3.1 → 0.3.2.",
      "Forbidden going forward: bypassing the connector for direct urllib calls to cortex docs (the connector IS the path); loading the two reference skills eagerly (loadingMode: on-demand for a reason — keep agent context lean); shipping new agent-guidance skills without lazy-loading unless truly broadly relevant.",
    ],
  },
  {
    version: "0.5.68",
    date: "2026-05-17",
    title:
      "Rewrite Cortex XDR connector description + metadata for general-purpose use (not just Caldera-detection-validation framing)",
    highlights: [
      "v0.5.61 shipped the XDR connector with a Caldera-validation-focused description ('read-only counterpart to caldera for detection-validation loop'). Operators reading the marketplace card would conclude the connector only matters if they're driving Caldera attacks. Reality: the XDR connector wraps Cortex XDR's Public API read paths — incidents, alerts, XQL — equally useful for incident triage, threat hunting, investigation reporting.",
      "Rewrite: description leads with 'list incidents and alerts, drill into specific cases, and run XQL queries against the XDR data lake. General-purpose surface for incident response, threat hunting, investigation reporting, and detection coverage validation.' Caldera-validation moved to ONE use case among many.",
      "Tags broadened: removed narrow 'detection' + 'validation' + 'v0.5.61'; added 'siem' + 'alerts' + 'threat-hunting' + 'investigation' + 'incident-response'.",
      "longDescription rewritten to lead with three operator-question examples (triage, alert drill-down, XQL hunt) before mentioning the Caldera pairing. setupGuide step 7 broadened to show three example natural-language queries spanning all 4 tools.",
      "Version bumped 0.1.0 → 0.1.1. No code change — pure metadata rewrite.",
      "Companion to v0.5.67's manifest fix: same operator hands-on smoke surfaced both. Together they polish off the XDR connector's release.",
      "Forbidden going forward: narrowing connector descriptions to a single use case (lead with the API surface, follow with example use cases). Same rule for future connectors.",
    ],
  },
  {
    version: "0.5.67",
    date: "2026-05-17",
    title:
      "Fix Cortex XDR connector install failure (missed manifest.yaml entry in v0.5.61) + new 'Adding a new connector' checklist in docs/CICD.md to prevent recurrence",
    highlights: [
      "Operator hit error 'connector cortex-xdr not found in catalogue' clicking Install on the XDR card. v0.5.61 shipped the connector code + synthetic marketplace card but missed bundles/spark/manifest.yaml:toolConnectors[] entry that the MCP's install endpoint reads.",
      "Phantom has two parallel connector catalogs: bundle catalogue in manifest.yaml drives install; synthetic card list in route.ts drives UI display. They MUST stay in sync. v0.5.61 only updated one.",
      "Fix: added cortex-xdr to manifest.yaml toolConnectors after cortex-content entry (path: ./connectors/cortex-xdr/, version 0.1.0, required: false).",
      "Prevention: new section in docs/CICD.md (after Per-service path-filter contract) enumerates the 8 required edits when adding a new connector: connector.yaml, src/connector.py, Dockerfile, manifest.yaml entry, build-connectors.yml job, connector_probes.py PROBE_IMPLEMENTED + probe block, marketplace/connectors/route.ts synthetic card, connector_loader.py env-var aliases. Plus 2 operator-doc edits (architecture + user help pages) and a quick-check command to catch the manifest/dir mismatch.",
      "Forbidden going forward: shipping the synthetic card (route.ts) without the manifest entry (manifest.yaml) — that's the exact failure v0.5.61 introduced; the two catalogs must stay in sync. Merging connector PRs without running the quick-check command (2 seconds, catches the bug immediately).",
      "Pairs with v0.5.66's entrypoint-hook fix: v0.5.66 ensures Caldera-side plugin activation through volume-shadowed conf; v0.5.67 ensures agent-side connector catalog activation. Together they complete the new-connector path.",
    ],
  },
  {
    version: "0.5.66",
    date: "2026-05-17",
    title:
      "Entrypoint hook ensures phantom + emu plugins enabled across upgrades — fixes v0.5.65 follow-up (volume-shadow on caldera_conf)",
    highlights: [
      "v0.5.65 post-install smoke revealed: even with v0.5.65's plugin-pattern fix correctly baking phantom plugin code into plugins/phantom/data/, Caldera's entrypoint still didn't enable the plugin. Root cause: caldera_conf is ALSO a named volume that shadows the image's modified default.yml. Docker doesn't re-copy named-volume content on image rebuild — the volume's first-install default.yml is frozen forever.",
      "Fix: extend installer/docker-compose.yml's caldera entrypoint to reconcile the plugins list at startup. After the existing user/api_key merge, the script appends phantom + emu to cfg['plugins'] if missing, logs the change, then writes local.yml. Idempotent on subsequent restarts.",
      "Pattern parallels phantom-agent's v0.3.2 skills-bootstrap entrypoint (same marker-driven default-merge for /app/skills/). The two volume-shadow problems (data/ + conf/) get opposite fixes: data/ moved to plugins/<name>/ (outside mount), conf/ stays where it is + entrypoint reconciles at startup.",
      "Operators upgrading from any pre-v0.5.66 release see 'enabled plugin: phantom' + 'enabled plugin: emu' in docker logs caldera on the first post-upgrade restart. Subsequent restarts no-op. Volume preserves the operator's UI-created adversaries/abilities + the api key + the red user creds.",
      "Forbidden going forward: trying to fix conf-volume issues by modifying default.yml in the image (volume shadows it — use the entrypoint pattern); removing the entrypoint's plugin-enable block (breaks upgrades from pre-v0.5.66).",
    ],
  },
  {
    version: "0.5.65",
    date: "2026-05-17",
    title:
      "Fix v0.5.57 'factory state' claim — Phantom Caldera content moved to plugins/phantom/data/ so it survives the caldera_data volume mount (closes #44)",
    highlights: [
      "Smoke-test of v0.5.58-64 discovered: running phantom-caldera's /usr/src/app/data/ contained NONE of the v0.5.57 kill-chain abilities, v0.5.63 CTID adversaries, or v0.5.64 lookalikes — because installer/docker-compose.yml mounts caldera_data:/usr/src/app/data as a named volume that shadows image-baked content at runtime. v0.5.57's 'factory state' claim was aspirational, never validated against a fresh install.",
      "Root cause: Caldera's volume-mount design preserves operator state across container recreates. For NEW content shipped with releases, the correct integration is the plugin pattern (plugins/<name>/data/...), NOT data/. Plugin dirs are outside the volume mount.",
      "Fix: new phantom plugin shell at bundles/spark/caldera-content/plugin/ (hook.py + VERSION.txt + __init__.py). build-caldera.yml overlay rewritten to target third_party/caldera/plugins/phantom/data/ instead of /data/. New workflow step inserts '- phantom' into conf/default.yml's plugins list (NOT local.yml — that's volume-mounted and absent in build context).",
      "Same path-correction applied to v0.5.63's broken emu-enable step (was looking for local.yml, now targets default.yml).",
      "Upgrade caveat: caldera_conf is ALSO volume-mounted, so existing installs with populated conf volumes need a one-time `docker exec ... sed -i '/^- manx$/a- phantom' /usr/src/app/conf/local.yml; docker restart caldera`. Fresh installs auto-enable. Follow-up v0.5.67+ entrypoint hook will automate the upgrade case.",
      "Forbidden going forward: reintroducing data/ overlay pattern for content shipped with releases (use plugins/<name>/data/ — outside volume mount); modifying local.yml in build context (it doesn't exist there — runtime-generated on caldera_conf volume). Always modify default.yml.",
    ],
  },
  {
    version: "0.5.64",
    date: "2026-05-17",
    title:
      "Lab-safe lookalike abilities for techniques Cortex signature-blocks (Powerkatz-lite / Fodhelper-trace / ETW-patch-marker / AMSI-bypass-marker / comsvcs-minidump-trace) — closes #43",
    highlights: [
      "5 new Caldera abilities under bundles/spark/caldera-content/abilities/14-lab-safe-lookalikes/ that emit the syscall/registry/file/process patterns Cortex XDR's signature engine matches against — without achieving the malicious effect. Detection events fire; sandcat agent survives.",
      "Powerkatz-lite (T1003.001): P/Invoke OpenProcess(lsass.exe, PROCESS_VM_READ) → immediate CloseHandle + literal Mimikatz signature strings in PowerShell variable scope for AMSI match. NO memory read.",
      "Fodhelper-trace (T1548.002): registry SET on HKCU\\Software\\Classes\\ms-settings\\Shell\\Open\\command + 500ms wait + cleanup. DOES NOT invoke fodhelper.exe (Cortex's Child Process Protection block point).",
      "ETW-patch-marker (T1562.006): GetModuleHandle(ntdll) + GetProcAddress(EtwEventWrite) — same recon pattern Cortex BTP signatures. NO VirtualProtect call; ETW remains functional.",
      "AMSI-bypass-marker (T1562.001): literal AmsiUtils + amsiInitFailed strings in PowerShell variable scope for AMSI scan match. NO reflective field SET; AMSI active.",
      "Comsvcs-minidump-trace (T1003.001 alt): rundll32 comsvcs.dll MiniDump -1 <path> full — invalid PID makes MiniDump fail BUT Sysmon EID 1 captures the marquee command-line pattern.",
      "New adversary phantom-lookalike-validation chains all 5. Use to confirm Cortex detection coverage without operational compromise. Runtime ~3 min.",
      "Forbidden going forward: lookalikes that achieve the malicious effect (must remain detection-only); burying lookalikes in the main adversary list (dedicated 14-lab-safe-lookalikes/ directory + lookalike tag); lookalike-ifying techniques Cortex doesn't block (no point).",
    ],
  },
  {
    version: "0.5.63",
    date: "2026-05-17",
    title:
      "CTID Adversary Emulation Plans baked into phantom-caldera image (APT29 / FIN6 / OilRig / menuPass / Sandworm / Carbanak) — closes #41",
    highlights: [
      "v0.5.57 audit discovered the emu plugin shell shipped with Caldera 5.3 had 0 abilities + 0 adversaries — actual content lives in a separate CTID repo (center-for-threat-informed-defense/adversary_emulation_library) that wasn't cloned. v0.5.63 extends the build-overlay pattern to populate it.",
      "Two new workflow steps in build-caldera.yml: (1) shallow-clone CTID library + walk both newer (Resources/caldera) and older (Emulation_Plan/CALDERA) directory layouts + copy abilities + adversaries into emu/data/. (2) Idempotently insert '- emu' into Caldera local.yml's plugins list (alphabetical between debrief + fieldmanual).",
      "Graceful degrade: if CTID clone fails (transient network blip, repo URL moved), build continues with a warning rather than blocking. Emu plugin ships empty but stockpile + atomic + phantom adversaries still load.",
      "Operator value: APT29 (2-day chain, 50+ steps each), FIN6 (POS-malware criminal group), OilRig (Iranian APT), menuPass (APT10), Sandworm (NotPetya emulation), Carbanak (financial APT). Each curated, ATT&CK-mapped, well-documented — higher quality than from-scratch authoring.",
      "Forbidden going forward: pinning CTID library to a specific commit (their main is curated, latest is fine for content overlays); enabling additional plugins without populating their data (operator-confusing empty panes); shipping CTID content in a separate phantom-emu image (single phantom-caldera digest preserves the customer-compose discipline).",
    ],
  },
  {
    version: "0.5.61",
    date: "2026-05-17",
    title:
      "Cortex XDR connector — read-only counterpart to caldera for closing the agent-as-operator detection-validation loop. 4 tools (get_cases_and_issues, get_incident_extra_data, run_xql_query, get_xql_results). Closes #36.",
    highlights: [
      "Brand-new per-instance connector at bundles/spark/connectors/cortex-xdr/. Wraps Cortex XDR Public API (/public_api/v1/incidents/* + /public_api/v1/xql/*). Same Cortex auth pattern as XSIAM (Authorization + x-xdr-auth-id headers); unified api_url/api_id/api_key field names from v0.5.59 / #35 so operators don't translate between products.",
      "Tool 1 — xdr_get_cases_and_issues: list incidents with filters by time/endpoint/severity/status. Returns compact summary per incident. Use as the entry point for 'what did Cortex catch on host X in the last 24h'.",
      "Tool 2 — xdr_get_incident_extra_data: drill into one incident — full alerts + network/file artifacts. Use after get_cases_and_issues when an incident looks interesting.",
      "Tool 3 — xdr_run_xql_query: synchronous XQL with bounded polling (default 2 minutes wall time). Returns rows directly when complete; returns execution_id when still running so caller can poll async.",
      "Tool 4 — xdr_get_xql_results: poll an in-flight XQL execution by id. Used after run_xql_query returned PENDING for long queries.",
      "Probe wired in connector_probes.py (PROBE_IMPLEMENTED set). Probe POSTs /incidents/get_incidents with search_to:1 for minimal data transfer; 200 = healthy, 401/403 = creds rejected (is_auth_error=true).",
      "New build-cortex-xdr-connector job in build-connectors.yml with pull-policy: never (the v0.5.60 / #38 pattern). First-ever release on the now-fixed connectors pipeline.",
      "Use case: operator says 'run the v0.5.57 phantom-killchain and tell me what Cortex caught'. Agent fires caldera_create_operation, polls to completion, queries xdr_get_cases_and_issues for the run window, builds per-ATT&CK-technique coverage matrix. The workflow that EPIC #39 codified — manual today via Claude in chat, autonomous in v0.7.x+ via phantom-agent + Gemini.",
      "Forbidden going forward: inventing new auth field names (api_* is the canon for all Cortex products); adding write/action endpoints without operator approval gates; extending synchronous XQL poll past 5 min (long queries should return execution_id for async polling).",
    ],
  },
  {
    version: "0.5.60",
    date: "2026-05-17",
    title:
      "Fix chronic build-connectors --pull 401 (silent since v0.5.11; surfaced as v0.5.59 release-blocker — closes #38)",
    highlights: [
      "Per-connector image builds (xlog/xsiam/caldera/web/cortex-docs/cortex-content) chronically failed with HTTP 401 from GHCR. Race: docker build --pull forces re-fetch of the just-pushed phantom-connector-runtime:dev manifest, but that version is private until associated with dev-latest prerelease (which happens later in the cascade, after the per-connector jobs already tried to pull).",
      "Silent for 5+ release cycles because customer compose pins digests baked at release.yml time, not from the broken dev path. Surfaced as a real release-blocker when v0.5.59 needed XSIAM src/connector.py to actually be in the connector image.",
      "Fix: composite action .github/actions/build-and-push-dev-image/action.yml gains pull-policy input. Default 'always' keeps --pull for first-party Docker Hub bases (python:3.12-slim etc). 'never' skips it for builds whose FROM is a Phantom-own image just built locally in a prior job — the per-connector pattern.",
      "build-connectors.yml updated: all 6 per-connector jobs set pull-policy: never. build-runtime keeps the default 'always' because its base is python:3.12-slim where CVE-fresh pulls are the right call.",
      "After landing: gh workflow run build-connectors.yml force-triggers a fresh run. All 6 per-connector images rebuild with new digests — including v0.5.59's XSIAM image carrying the dual-name _get_fetcher() code. Next build-dev-installer.yml cascade republishes dev-latest with v0.5.58 + v0.5.59 + v0.5.60 all baked coherently.",
      "docs/CICD.md: new failure-mode entry #12 documents the pattern + remediation. Quick-reference table extended.",
      "Forbidden going forward: removing --pull from any first-party base build; auto-associating :dev versions with dev-latest at build-runtime time (broadens partial-release window); expecting build-connectors to auto-trigger on workflow-file edits (path filter narrow per v0.5.12 — use gh workflow run to force-exercise).",
    ],
  },
  {
    version: "0.5.59",
    date: "2026-05-17",
    title:
      "XSIAM connector credentials renamed to api_url / api_id / api_key (uniform with upcoming Cortex XDR connector; legacy papi* names still accepted on read for backwards compat — closes #35)",
    highlights: [
      "Issue #35 standardizes Cortex auth across products. XSIAM's PAPI-specific papiUrl / papiAuthId / papiAuthHeader become api_url / api_id / api_key — same names the upcoming Cortex XDR connector (issue #36, v0.5.60) adopts from day 1. Both products use the same X-Auth-ID + Authorization auth pattern, so the field names converge.",
      "Backwards-compatible read path: existing XSIAM instances created pre-v0.5.59 keep working unchanged. Connector code (_get_fetcher), probe, and coverage cycle all read either name pair, new-name-first. Forced migration is intentionally avoided — instances upgrade lazily when the operator clicks Edit + Save in the connectors form.",
      "UI form labels updated: 'PAPI URL' → 'API URL', 'Auth header' → 'API key', 'Auth ID' → 'API ID' (mcp/agent/app/api/marketplace/connectors/route.ts). New instances save the new names.",
      "Manifest first-time-setup wiring (bundles/spark/manifest.yaml) maps primary-xsiam's instance template LHS keys to the new names. Setup-template variable names (${setup.xsiamPapiUrl} etc.) on the RHS stay — those are setup.json references, not config keys.",
      "Connector loader's manifest-to-settings key map (bundles/spark/mcp/src/usecase/connector_loader.py) maps BOTH legacy AND new names to the same env-var settings attribute slots, so old manifest values translate identically and old env-driven configs keep working.",
      "Tests + docs updated: test_coverage_store happy-path uses new names; missing-config test accepts either wording; ops-edit-xsiam-via-connectors-v0135 journey reflects the rename; cortex_xql_query_authoring skill's troubleshooting matrix mentions both legacy and new error strings.",
      "Forbidden going forward: removing legacy papi* fallback reads (until a major version bump); inventing new name pairs for future Cortex products (use api_*); auto-migrating stored config keys on boot (lazy migration via operator Edit only). v0.5.60 next ships the Cortex XDR connector (#36) using these same names.",
    ],
  },
  {
    version: "0.5.58",
    date: "2026-05-17",
    title:
      "Connector instance create + test feels honest — Create modal closes on success, cortex-docs + cortex-content get real probes (closes #33 + #34)",
    highlights: [
      "Issue #33: Create Instance modal now closes immediately on successful create. handleSave calls onClose() after onCreated() in the success branch. Operator no longer has to click X / Cancel after a successful create.",
      "Issue #33: Removed the in-modal Test Connection affordance entirely — it was the source of the dual-action ambiguity. The per-instance Test Connection button on /connectors is now the canonical surface. ~60 lines of UI + testStatus / createdInstanceId / handleTestConnection state deleted from the CreateInstancePanel component.",
      "Issue #34: PROBE_IMPLEMENTED registry extended from {xlog, caldera, xsiam} to also include cortex-docs + cortex-content. Both connectors talk to unauthenticated public APIs; pre-v0.5.58 they returned probe_implemented:false which the old in-modal Test panel rendered as 'Could not reach the service. Verify your credentials.' — misleading because the connectors have no credentials to verify.",
      "Issue #34: cortex-docs probe — POST {baseUrl}/api/khub/suggest with {inputText:'xql'}. Lightweight, hits docs-cortex.paloaltonetworks.com Fluid Topics API. 4xx is reported as healthy (upstream is up) since real tool calls use a different request shape; only 5xx / connection errors fail the probe.",
      "Issue #34: cortex-content probe — verifies the bundled catalog is present and readable.",
      "Forbidden going forward: re-introducing in-modal Test Connection (the dual-action UX was confusing); probing HTML root pages (brittle to layout changes — probe API endpoints with stable contracts); faking credentials for public-API connectors (misleads operators).",
    ],
  },
  {
    version: "0.5.57",
    date: "2026-05-16",
    title:
      "Caldera kill-chain content is factory state — baked into the phantom-caldera image, auto-loaded on container start. Plus 8 new noisy steps tuned for marquee XDR signals (LSASS comsvcs dump, Defender disable, Run-key + scheduled-task persistence, certutil decode, event-log clear).",
    highlights: [
      "v0.5.55 shipped the kill-chain YAMLs as a bundle; v0.5.57 makes them factory state. Fresh phantom-caldera installs see the adversary preloaded in the UI — zero manual import. The CI workflow (.github/workflows/build-caldera.yml) overlays bundles/spark/caldera-content/ into the caldera build context just before docker build runs; Caldera's data_svc auto-scans /usr/src/app/data/{abilities,adversaries}/* on container start.",
      "Why the build-time overlay (not committed-to-submodule): third_party/caldera/ is a git submodule pointing at upstream mitre/caldera.git. Files committed there become untracked-in-submodule and don't reach our main branch. Overlaying from our own tracked dir (bundles/spark/caldera-content/) is the architectural fix.",
      "Kill chain expanded from 12 to 20 steps. 8 new abilities woven into the existing narrative at narratively-correct points: 3a system-info burst (T1082+T1018, 4-LOLBin volume), 3b network share discovery (T1135), 7 LSASS minidump via comsvcs.dll (T1003.001 — the marquee EDR rule, every modern XDR has a Sysmon EID 10 detection for handles to lsass.exe), 9 Defender real-time disable + 3 exclusion paths (T1562.001), 10 certutil -decode (T1140 LOLBin abuse), 12 Registry Run key persistence (T1547.001), 13 scheduled task /sc onlogon (T1053.005), 20 wevtutil cl Security (T1070.001 — Security 1102 fires unconditionally).",
      "All lab-safe: LSASS .dmp deleted immediately after creation; Defender disable reversible (-DisableRealtimeMonitoring $false); certutil decodes a harmless base64 text string; persistence payloads are no-op log appends; event-log clear is genuinely destructive of audit history but the system stability is unaffected. Each ability's description names its safety mechanism explicitly.",
      "Skill run_phishing_kill_chain rewritten to drive the 20-step chain. ATT&CK frontmatter expanded from 8→11 tactics. Step E (per-step decode) adds 4 headline-step callouts (LSASS dump / Defender / lateral / event-log clear) for the agent to highlight in the operator summary. Cleanup section ships a full PowerShell snippet for reverting all 8 new artefacts (delete user, remove Run-key value, delete scheduled task, restore Defender realtime, remove exclusion paths).",
      "Adversary ID preserved (f81c14fe-6730-4215-bc95-e8eaca1530ab). Existing 12 ability UUIDs preserved. Operators upgrading from v0.5.56 see new entries appear after rebuild; existing operator-created operations referencing the old 12-step adversary still resolve (atomic_ordering is just extended, not replaced).",
      "Detection narrative: marquee atomic alerts at steps 7 (LSASS), 9 (Defender tamper), 14 (lateral), 20 (Security 1102). Sequence alerts across steps 3-5 (discovery burst) and 11-13 (persistence trio). Forbidden going forward: dropping Phantom YAMLs into third_party/caldera/ (submodule trap); adding manual-import instructions to operator-facing docs (auto-load IS the path); auto-undoing Defender disable or event-log clear in cleanup (persistent state is part of the detection scenario).",
    ],
  },
  {
    version: "0.5.56",
    date: "2026-05-16",
    title:
      "New skill run_phishing_kill_chain — agent now drives the v0.5.55 Caldera content end-to-end from a chat prompt (verify prereqs → fire → poll → decode → telemetry summary)",
    highlights: [
      "Pairs with v0.5.55's bundled Caldera content. v0.5.55 shipped the YAMLs; v0.5.56 ships the operator-facing entrypoint — a skill the agent invokes when the operator says 'run the phishing kill chain'.",
      "First skill in bundles/spark/mcp/skills/workflows/. Structured per the foundation skill convention: frontmatter (name, displayName, icon, ATT&CK mapping for 8 tactics 12 techniques), Purpose + When (NOT) to run, 3-step prereq verification, 7-step procedure (A through G), 5-rule Forbidden section, Cleanup guidance, Variations, 12-row Telemetry-signatures handoff table.",
      "loadingMode: on-demand — not auto-loaded into every chat context. Agent fetches when prompt matches the skill's intent. locked: false so operators can fork.",
      "Procedure walks the agent through: caldera_get_all_agents (verify 2 agents in groups red+victim), caldera_get_adversary_by_name (verify 12-step adversary imported), caldera_create_operation (returns paused), caldera_update_operation with state=running+group=red, polling loop with 30s delay, caldera_get_operation_link_result per step (base64 decode → JSON → stdout/stderr/exit_code), final markdown summary.",
      "Skill explicitly handles the Caldera-parser false-negatives on steps 5+6 — the agent tells the operator 'these show ❌ in Caldera but the registry/user telemetry fired correctly; verify Security 4720 + Sysmon EID 13 on the host'.",
      "5 explicit Forbidden constraints baked into the skill markdown: no auto-running bootstraps (modify host security state); no auto-create/modify adversary (drift risk); no auto-delete lateral evidence markers (operator-visible proof); no fire without confirmation (real registry mutations + user creation involved); no false-success reports when status=1 parser FPs are present. These constraints are AS authoritative as the procedure.",
      "Forbidden going forward: promoting the skill to on_load mode (kills operator-intent gating, prompt-injection risk); removing the Forbidden section from skill markdown (safety constraints must travel with the skill); moving skill out of workflows/ category.",
    ],
  },
  {
    version: "0.5.55",
    date: "2026-05-16",
    title:
      "Bundled Caldera kill-chain content: 9 custom abilities + adversary profile under bundles/spark/caldera-content/ — operators get a known-good cross-host phishing → ransomware emulation to exercise SOC detections against",
    highlights: [
      "New directory bundles/spark/caldera-content/ with 9 ability YAMLs (organized by tactic 00-bootstrap through 11-exfiltration) + 1 adversary profile (Phantom phishing → ransomware kill chain, 12 steps). 6 abilities custom; 6 referenced from Caldera's stockpile by UUID.",
      "The 12-step kill chain: phishing emailclient.exe spawn → cmd drops+runs script → workgroup account discovery → cached cred dump → Fodhelper UAC bypass → create local user → REAL lateral via SMB+WMI+WinRM → automated collection (no protected-dir crashes) → archive → DNS beacon → HTTP POST exfil → defacement note. Covers 8 MITRE tactics, 12 techniques.",
      "Cross-host lateral movement (T1021.002) is the headline: real working SMB admin-share mapping, WMI Win32_OperatingSystem query via CIM+Negotiate, WinRM Invoke-Command returning remote hostname/whoami — all confirmed end-to-end via the 10-method auth diagnostic.",
      "Two setup-only bootstrap abilities under 00-bootstrap/ configure the workgroup-auth knobs that make cross-host lateral actually work on Server 2022: LocalAccountTokenFilterPolicy=1, Service\\AllowUnencrypted, Client\\TrustedHosts, SMB firewall, phantomlab admin user. Run once each before the kill chain.",
      "PowerShell wrapping uses base64 -EncodedCommand throughout — Caldera's ability serializer strips whitespace from command: fields, breaking any non-trivial multi-line script. Base64 survives the strip + preserves all formatting/special chars.",
      "Two install paths in the README: quick (paste each YAML into Caldera UI for one-off testing) and durable (volume-mount abilities/ + adversaries/ into the Caldera container's data/ tree, edit installer/docker-compose.yml). Both documented.",
      "Lab-safety constraints called out explicitly: no actual encryption (T1491 drops a note, doesn't encrypt), no real exfil (POSTs to internal Caldera listener, returns 500 — telemetry-only), no real malware (emailclient.exe is renamed signed notepad). Hardcoded creds (phantomlab / Lab26Pass#) chosen to satisfy Windows complexity AND avoid containing the username substring (a Windows password rule that bit our earlier iterations silently).",
      "Forbidden going forward: making any of these abilities singleton (kills repeatability); replacing the base64 wrap with plaintext (Caldera whitespace-strips it); changing the phantomlab password indirection (parameterizing forces runtime fact-injection which complicates install); bundling stockpile abilities (Caldera ships them; duplicating creates drift).",
    ],
  },
  {
    version: "0.5.54",
    date: "2026-05-16",
    title:
      "New /help/architecture#connectors-design section with inline SVG lifecycle diagram (answers 'how do connectors + instances actually work?' end-to-end)",
    highlights: [
      "Operator asked for a dedicated design section covering the full connector/instance lifecycle. v0.5.54 ships it — new nav entry under Connectors & Extensions group, sitting between Hooks Framework and Connector State Machine.",
      "Inline SVG diagram (1100×820, 7 horizontal lanes): Origin → Storage → Validate → Catalog → Configure → Spawn → Runtime. Color-coded by path — blue=bundle, purple=user upload, orange=schema validator (universal join), green=catalog+install+callback, red=SecretStore decryption. Inline = lives next to prose, edits in the same file, no external asset to rot.",
      "Five subsections after the diagram: (1) two origin paths side-by-side; (2) 5-row storage layers table (bundle YAML / user YAML / marketplace.db / instances.db / SecretStore) with content/backed-by/lifecycle columns; (3) 10-step lifecycle walkthrough following cortex-docs from author commit through runtime tool call; (4) 'where the operator sees what' triage table mapping questions → UI/API surfaces; (5) cross-references to the 3 existing connector sections (containers, state, marketplace).",
      "Pattern: summarize + index, do NOT duplicate. The 3 existing sections (#connector-containers, #connector-state, #marketplace-logic) keep their focused depth; #connectors-design is the 'if you read one section, read this' landing page.",
      "Storage-layers table is the day-to-day debugging artifact — when an operator says 'I deleted X and Y is broken', this table maps cause-to-effect across the 5 stores.",
      "Forbidden going forward: replacing inline SVG with external PNG/Excalidraw export (diagrams rot when separated from prose); duplicating content from the 3 existing sections (preserves depth + makes index obvious); removing the storage-layers table.",
    ],
  },
  {
    version: "0.5.53",
    date: "2026-05-16",
    title:
      "All 6 bundle connectors get displayName, tags, and inline SVG logos (fills v0.5.52 nice-to-have gaps; cleans up xsiam stale comment)",
    highlights: [
      "After v0.5.52's logo support landed, operator downloaded xsiam.yaml to test the round-trip and asked 'anything wrong?' Three gaps: no displayName (falling back to 'Xsiam' via id.title()), no tags (no marketplace filtering), no logo (generic icon on every card).",
      "v0.5.53 fills all three across all 6 bundle connectors: xlog (Xlog (synthetic telemetry), 6 tags, green log-stream waveform); caldera (CALDERA (red-team), 5 tags, red bullseye); xsiam (Cortex XSIAM, 6 tags, orange shield with X); web (Web browser, 6 tags, blue browser frame + globe); cortex-docs (Cortex docs (knowledge), 6 tags, indigo open book); cortex-content (Cortex content (playbooks), 6 tags, indigo content-list with orange dots).",
      "Logos are inline SVGs encoded as data:image/svg+xml;base64,… per v0.5.52's contract. Raw SVG sizes 326-686 bytes; encoded data URIs 462-942 chars. Well under the schema's 350,000 cap. Cortex-family (xsiam, cortex-docs, cortex-content) share an indigo+orange palette to signal the family.",
      "Brand discipline: abstract symbology only. No third-party impersonation — caldera uses a generic bullseye not MITRE's mark, xsiam uses a shield+X not Palo Alto's cortex glyph. v0.5.53 forbids future bundle connectors from using real corporate marks.",
      "xsiam.yaml stale-comment fix: lines 15-22 said 'Tool dispatch — module-style with xsiam_ prefix' but the active config (line 30) was style: container. Replaced with current explanation noting the wrapper is stateless + PAPI auth lives in SecretStore. The functionPrefix line itself stays (v0.5.0+ no-op when style is container but preserved for round-trip stability of operator-downloaded YAMLs).",
      "Marketplace API now returns display_name + logo per entry (server-side projection in _connector_summary). UI cards render these directly — no per-card detail fetch needed.",
      "Forbidden going forward: replacing the inline-SVG approach with separate logo files (data-URI-in-YAML rule still applies); third-party brand impersonation in bundle-connector logos; removing functionPrefix from xsiam (preserved for round-trip diff stability).",
    ],
  },
  {
    version: "0.5.52",
    date: "2026-05-16",
    title:
      "Marketplace gets four real surfaces: connector download, real upload-form file picker (replacing the Alpaca mock), logo as base64 data URI embedded in YAML, inline server-side validation errors",
    highlights: [
      "Closes the operator-reported v0.5.51-smoke gap: marketplace was view-only, upload form was 100% mocked (hardcoded Alpaca_unified.yml regardless of what file the operator dropped), and there was no logo story.",
      "DOWNLOAD: new GET /api/v1/marketplace/{id}/download endpoint streams the raw connector.yaml with Content-Disposition save-as. Download button on every marketplace card. Audited as connector_downloaded event.",
      "UPLOAD (real now): replaced MOCK_PARSED_YAML with a real <input type=file> + FileReader + js-yaml client-side parse for preview. All fields (displayName, id, version, description, tags, configSchema, secretSlots, spec.tools, runtime) render from the actually-parsed YAML. Submit POSTs multipart to /api/agent/marketplace/upload, which validates against connector.schema.json server-side + surfaces structured errors inline.",
      "LOGO: new optional `logo: data:image/...;base64,...` field in connector.schema.json. Supported MIME types: SVG (preferred for crispness), PNG, JPEG, GIF, WebP. Max 350,000 chars encoded (~260 KB; client caps RAW at 200 KB). Logo lives INSIDE the YAML — round-trips cleanly on download/upload. Single source of truth, no separate asset to manage.",
      "VALIDATION: server's existing jsonschema validation now surfaces inline above the upload form. Operators see the violating field path, not a generic 400. Client-side caps logo MIME + size BEFORE the multipart round-trip so size/type errors are instant.",
      "Marketplace card improvements: catalog summary now includes display_name (with id.title() fallback) + logo (data URI), so cards render real names + logos without per-card detail fetches.",
      "Forbidden going forward: re-introducing mock data in UploadConnectorPanel; skipping schema validation on upload (server is source of truth); raw logo files separate from YAML (commits to data-URI-in-YAML approach); download without bearer auth.",
    ],
  },
  {
    version: "0.5.51",
    date: "2026-05-16",
    title:
      "phantom-updater now reads PHANTOM_VERSION + DIGEST_PHANTOM_* from /host/.env at runtime (closes the unchanged-image-recreate invariant violation)",
    highlights: [
      "Pre-v0.5.51: phantom-updater was recreated on EVERY stack upgrade even when its own image digest was unchanged, because docker compose's config-hash flipped whenever any stack digest in its 'environment:' block flipped. v0.3.0+'s 'same digest = no recreate' invariant held for xlog + caldera but not phantom-updater.",
      "Fix: new /host/.env cached reader in updater/src/main.py with 30s TTL. Helpers _running_phantom_version(), _stack_digest(svc), _connector_digest(id) replace the 7 os.environ.get callsites. Cache is invalidated immediately by _apply_manifest_to_env so the updater's own manifest writes propagate without latency.",
      "Customer compose strips PHANTOM_VERSION + 5 stack DIGEST_PHANTOM_* + 6 connector DIGEST_PHANTOM_CONNECTOR_* entries from phantom-updater's environment block. Stable env block means stable container config hash means no recreate on upgrades that don't touch phantom-updater's image.",
      "Operator-visible change: phantom-updater in-memory state (compose subprocess handles, ongoing-update SSE state, the .env cache itself) now survives across stack upgrades. Same behavior xlog + caldera already had.",
      "30s cache TTL trade-off: manual /host/.env edits take up to 30s to reflect in API responses. The alternative (parse-on-every-request) would hammer the filesystem on every /api/v1/version/current call. The cache is bypassed on manifest writes so the updater's own changes are zero-latency.",
      "Forbidden going forward: re-adding DIGEST_PHANTOM_* or PHANTOM_VERSION to phantom-updater's environment: block (re-introduces the recreate cycle); reading these via os.environ.get anywhere in updater/src/main.py (grep test must return zero matches); removing the cache-invalidation hook in _apply_manifest_to_env (would briefly return stale values); reading TLS material or secrets from /host/.env (it's metadata, not a free-form key-value store).",
    ],
  },
  {
    version: "0.5.50",
    date: "2026-05-16",
    title:
      "Installer: freshly-prompted GHCR tokens now persist to /opt/phantom/.env (kills the re-prompt-every-run bug)",
    highlights: [
      "Pre-v0.5.50: on every re-run of /home/ayman/phantom-installer-dev with an expired .env-stored token, the installer prompted for a fresh PAT, validated it, used it for docker login + pulls — but NEVER wrote the fresh token back to .env. Next re-run hit the prompt again. Operators were re-pasting tokens on every install.",
      "Fix: new write_env_value helper (sister of existing read_env_value) updates an existing VAR= line in-place via awk-prefix-match, or appends if absent. Re-applies chmod 600. Idempotent.",
      "New call-site at the end of Step 4 (registry credentials), gated on EXISTING_INSTALL == 1 && TOKEN_SOURCE != .env: if the validated token came from env var or interactive prompt, persist it to .env. The .env-source path is the no-op (same value already on disk).",
      "After v0.5.50: first re-run with expired .env token prompts once + persists; subsequent re-runs read the fresh token from .env and proceed without prompt. Operators mint a long-lived PAT once and re-runs stay frictionless until that PAT itself expires.",
      "Forbidden going forward: silent failure on .env write (warned, not swallowed); persisting unvalidated tokens (persist call is AFTER the validation loop); persisting tokens from the .env source (it's already there, no I/O needed).",
    ],
  },
  {
    version: "0.5.49",
    date: "2026-05-16",
    title:
      "Sidebar nav: 9 missing entries added — every shipped page is now reachable from the nav (fixes accumulated v0.5.21-48 navigation gaps)",
    highlights: [
      "While testing v0.5.48 we discovered 9 pages shipped during the Octagon-gap sprint that existed on disk + in the bundle but weren't in components/sidebar.tsx's navEntries. The operator could only reach them by typing the URL directly. v0.5.49 closes this comprehensively.",
      "Command group adds: Agents (/agents — Round-15 Phase S agent registry, icon groups), Tasks (/tasks — Round-15 Phase T worker task registry, icon task_alt).",
      "Integration group adds: Plugins (/plugins — Round-15 Phase X filesystem-discovered plugin tree, icon extension; distinct from the entry-point catalog below).",
      "Observability group adds 5 entries: Runtime events (icon bolt), Connectors telemetry (icon settings_input_component), Cost (v0.5.40 group-by toggle, icon payments), Bench (v0.5.35 benchmark UI, icon speed), Plugins (v0.5.44 entry-point catalog with v0.5.47 install/uninstall + v0.5.48 handler invocation, icon deployed_code).",
      "Settings group adds: Hooks (/settings/hooks — v0.5.21 hook management surface; this was the most-load-bearing gap because operators couldn't reach hook config from nav at all, including v0.5.48 plugin-handler wiring).",
      "Discipline: CLAUDE.md now has Rule 6a — 'No new UI page without a sidebar nav entry in the same PR' — sitting next to Rule 6's 'no backend feature without a UI surface'. The grep test: `find mcp/agent/app -maxdepth 3 -name page.tsx | xargs dirname | sort` vs the `href:` entries in sidebar.tsx. Every page (except redirects + [param] routes) should appear. Reviewers MUST insist on this before merge.",
      "Forbidden going forward: no adding app/<page>/page.tsx without also editing sidebar.tsx; no relying on URL bookmarks as the discovery path for newly-introduced surfaces.",
    ],
  },
  {
    version: "0.5.48",
    date: "2026-05-16",
    title:
      "Plugin-contributed hook handlers are now callable from /settings/hooks (closes the cross-language bridge piece of #29 — entry-point plugin system is end-to-end functional)",
    highlights: [
      "v0.5.31 + v0.5.44 + v0.5.47 shipped discovery + lifecycle for the entry-point plugin system; v0.5.48 closes the LAST piece: plugin-contributed handlers in the phantom.hooks group are now invocable from the agent's hook-runner via a new 'plugin' transport type in /settings/hooks.",
      "Architecture: plugin handlers live in Python (entry-points are a Python-package mechanism); the agent's hook-runner lives in TS. v0.5.48 bridges with HTTP — POST /api/v1/plugin-hooks/{name}/invoke runs the plugin handler in MCP on a thread pool, returns the result back as JSON, the hook-runner translates that to the standard HookResult shape.",
      "Backend: new bundles/spark/mcp/src/usecase/plugin_hook_runner.py (discovery + thread-pool invoker with timeout + exception isolation) + bundles/spark/mcp/src/api/plugin_hook_invoke.py (the HTTP endpoints). Install/uninstall in v0.5.47 now clear the handler cache so newly-installed plugins surface without an MCP restart (hot-reload for plugin-hook handlers; other contribution types still need restart).",
      "Frontend: new HookTransport variant {type:'plugin', handlerName, config?, timeoutS?}, new runPluginHook in lib/hook-runner.ts (fetch with AbortController bounded by hook timeoutMs), new PluginHandlerConfigSection in /settings/hooks (handler dropdown + JSON config textarea + timeout input + Refresh button for post-install).",
      "Plugin author contract: in pyproject.toml declare [project.entry-points.\"phantom.hooks\"] my-handler = \"my_pkg:my_handler\"; the function signature is def my_handler(payload: dict, config: dict) -> dict | None where None=no-op and dict={decision, reason} is a HookResult. Operator config is plugin-defined (no introspection from TS); plugin author documents their own contract.",
      "Operator UX: install plugin at /observability/plugins → visit /settings/hooks → pick 'Plugin handler' transport → select the handler from the dropdown → fill JSON config → save. Hook fires on the next matching event; result feeds the failure-policy path like any other transport.",
      "Security: MCP_TOKEN-only auth on both surfaces. Plugin handlers run in the MCP process with full agent privileges — treat installation with the same care as a vendor library; review source before pip install. Every invocation audits as 'plugin_hook_invoked' with handler name + outcome category (allow/deny/ask/no-op/error).",
      "Forbidden going forward: no skipping the audit row on plugin invocations (every fire MUST land in /observability/events); no expanding the 'agent' transport to dispatch plugin handlers (agent stays reserved for the MCP-tool bridge feature, plugin is the entry-point bridge); no removing the cache-clear on install/uninstall (operators won't accept 'restart phantom-agent to use your new plugin').",
    ],
  },
  {
    version: "0.5.47",
    date: "2026-05-16",
    title:
      "Plugin install + uninstall from /observability/plugins UI (closes the long-deferred lifecycle gap of #29)",
    highlights: [
      "v0.5.44 made discovered plugins visible but left install/uninstall as a docker exec pip ceremony. v0.5.47 closes that gap: a new install form at the top of /observability/plugins runs pip install --user <spec> server-side, plus per-row Uninstall buttons run pip uninstall -y <dist>.",
      "Backend: new bundles/spark/mcp/src/api/plugin_entry_points_routes.py with three endpoints — GET /api/v1/plugin-entries (list), POST /api/v1/plugin-entries/install (body {spec}), DELETE /api/v1/plugin-entries/{dist_name}. All bearer-auth via MCP_TOKEN.",
      "Security: pip runs via asyncio.create_subprocess_exec (no shell), specs validated against shell metacharacters as defense-in-depth, --user install so no system-wide writes, every action audited via record_event('plugin_install' or 'plugin_uninstall') — visible at /observability/events.",
      "Bug fix: v0.5.44 had a latent boot bug — it added a register_plugin_routes(mcp) 1-arg call to main.py while the existing 5-arg function still expected (mcp, loader, memory_store, audit, agent_definition_store). Would TypeError on startup. v0.5.47 replaces that call with register_plugin_entry_points_routes(mcp) calling a separately-named function so the two surfaces (Phase X filesystem plugins, retained / entry-point distributable plugins, new) never collide.",
      "Operator UX: paste spec → click Install → see success note → catalog refreshes. Click Uninstall on any row → confirm → row disappears. Restart phantom-agent for newly-installed package's CONTRIBUTED handlers to become callable; discovery alone doesn't import them (handler-invocation bridge ships in v0.5.48).",
      "Forbidden going forward: no automatic install at MCP boot from config — even an env-controlled INSTALL_PLUGINS=foo would let attacker-controllable env pull arbitrary pypi packages into the agent process. Plugin install is explicit operator action only.",
    ],
  },
  {
    version: "0.5.46",
    date: "2026-05-16",
    title:
      "Per-message Fork-from-here affordance in /chat (closes the long-deferred per-message fork UI piece)",
    highlights: [
      "v0.5.30 shipped the backend from_message_id API; v0.5.36 added session-level Fork. Per-message fork was deferred because it needed MCP message-id propagation from chat-route's persistence to client-side ChatMessage. v0.5.46 closes that propagation.",
      "Wire: RawMessage / TranscriptMessage / ChatMessage all gain optional mcpId?: string. getSessionTranscript maps m.id → mcpId on each transcript row. handleSelectSession's history-build attaches mcpId per ChatMessage.",
      "UI: MessageList's assistant-message rendering renders a hover-revealed 'Fork from here' button (call_split icon) top-right of each bubble when onForkFromMessage is provided AND msg.mcpId is set AND it's not the last (streaming) assistant message. Hidden by default via opacity-0 group-hover:opacity-100.",
      "Handler: new handleForkFromMessage(mcpId) on chat page POSTs to /api/agent/sessions/{activeSessionId}/fork with from_message_id=mcpId, refreshes sidebar, switches to new fork. MCP's fork_session() copies messages up to (and including) that point.",
      "Operator UX: hover any assistant message in a loaded session → Fork button appears top-right → click → new fork opens. Streaming messages don't have mcpId until session reload; session-level Fork from SessionMenu (v0.5.36) still works as coarse alternative.",
      "Forbidden going forward: silent fork that bleeds session-scoped memory across the cut. v0.5.30's fork_session() excludes session:<parent> memory entries from new fork; per-message fork inherits this discipline.",
    ],
  },
  {
    version: "0.5.45",
    date: "2026-05-16",
    title:
      "Sessions sidebar groups forks under their root ancestor's date group (cross-date reorder)",
    highlights: [
      "Pre-v0.5.45 the sidebar grouped sessions by their own timestamp. A fork created today from a Yesterday session landed in Today while the parent stayed in Yesterday — visually disconnected. v0.5.45 fixes it: forks join the ROOT ancestor's group + render parent-first DFS within the group.",
      "Implementation: rootAncestor(session) walks parentId chain (cycle-defended via seen-set), depthOf(session) mirrors v0.5.41's forkDepth. groupSessionsByDate rewritten to decorate + sort on (rootGroup ASC, rootTime DESC, depth ASC, ownTime DESC), then bucket into date groups.",
      "Operator impact: a parent created Yesterday + a fork created Today both render under 'Yesterday' with parent on top and fork indented below. Full tree visible without scrolling between date groups.",
      "Forbidden going forward: removing the cycle defense. Future re-parenting flows might introduce cycles; the seen-set defense is cheap and load-bearing.",
    ],
  },
  {
    version: "0.5.44",
    date: "2026-05-16",
    title:
      "/observability/plugins UI + /api/v1/plugins endpoint — discovery surface visible to operators (closes #29 UI half)",
    highlights: [
      "v0.5.31 shipped plugin discovery scaffolding; v0.5.36 wired log_discovery() at MCP startup. v0.5.44 closes the UI gap: operators browse the discovered plugin catalog without grepping container logs.",
      "Backend: new bundles/spark/mcp/src/api/plugins.py with GET /api/v1/plugins. Walks all 5 reserved groups via discover_all(), returns {groups, total}. Bearer auth via MCP_TOKEN. Discovery failure returns 500; page renders the error inline rather than crashing.",
      "Agent proxy at /api/agent/plugins (same MCP_TOKEN-bearer pattern as bench / hooks proxies).",
      "UI: /observability/plugins page renders one section per group (skills/connectors/hooks/scanners/providers) with per-group label, icon, one-line about + count badge. Per-row table when plugins exist (name, dist_name+version, target). Footer card shows pyproject.toml snippet for plugin authors.",
      "Banner at top explicitly notes 'Discovery only — plugin-contributed handlers are NOT yet invocable.' The bridge work is documented as a separate future release.",
      "Still deferred: plugin install/uninstall from the UI (today: docker exec pip install + MCP restart); plugin-contributed handler invocation (cross-language Node ↔ Python bridge — the meaningful remaining architectural work for v0.5.x or v0.6.x).",
      "Forbidden going forward: auto-install of plugins at MCP boot from a config file. Plugin installation must remain an explicit operator action; auto-install from config is a foot-gun.",
    ],
  },
  {
    version: "0.5.43",
    date: "2026-05-16",
    title:
      "Skills frontmatter model/thinking/permissions now flow through the skills listing API",
    highlights: [
      "v0.5.34 wired job dispatcher's _parse_skill_frontmatter to read skill MD's model/thinking/permissions blocks and apply as fallback defaults. But skills_list_all MCP tool (which feeds /api/agent/skills) ignored those fields. Operators couldn't see what their skill recommends from the UI.",
      "v0.5.43 fix: bundles/spark/mcp/src/usecase/builtin_components/skills_crud.py:_build_record() includes three new fields on every skill record — model (str | null), thinking (bool, default false), permissions (dict | null). Defensive types: malformed YAML falls back to safe defaults, no crashes.",
      "Downstream UI consumers ship incrementally as follow-ups: /skills page rendering 'Recommends Pro + thinking' chip on cards; chat header highlighting recommended model when operator picks a skill; /observability/cost grouping by 'skill-stick-vs-override.' None ship in v0.5.43 — the backend exposure is the load-bearing piece.",
      "Forbidden going forward: silent drift between _parse_skill_frontmatter (v0.5.34) and _build_record (v0.5.43). Both read the same MD frontmatter shape; future field additions must extend BOTH or document why one path is intentionally narrower.",
    ],
  },
  {
    version: "0.5.42",
    date: "2026-05-16",
    title:
      "/observability/bench/compare view — side-by-side run deltas with regression coloring",
    highlights: [
      "v0.5.35 shipped per-run detail at /observability/bench/[run_id]; v0.5.42 closes the comparison loop. Operators pick base + head and see metric deltas + per-case diffs with red/green regression signaling.",
      "Two run selectors populated from /api/agent/bench/runs?limit=100. URL ?base=<id>&head=<id> query params seed the selection. 6 DeltaCards: correctness, avg Jaccard, cost p50/p95, wall p50/p95. Coloring at ≥10% delta = green (improving) / red (regressing); within 10% = neutral. higherIsBetter flag inverts green/red for cost + wall (lower better).",
      "Per-case diff table shows case_id + correctness flip (FIXED / REGRESSED badge) + Jaccard delta + cost delta + wall delta. Per-cell coloring with axis-specific significance thresholds (0.05 Jaccard, $0.0001 cost, 0.5s wall).",
      "Bench list page gets a 'Compare runs' button in the header (compare_arrows icon) linking to /observability/bench/compare so operators don't have to type the URL.",
      "Operator usage: validate router preset trade-offs (Flash X% cheaper but Y% less correct?), regression-test new releases (v0.5.40 vs v0.5.39 same manifest), audit corpus changes (before/after).",
      "Forbidden going forward: silent threshold change. The 10% regression threshold matches v0.5.29 scaffolding's definition; future adjustments must update BOTH places + document rationale.",
    ],
  },
  {
    version: "0.5.41",
    date: "2026-05-16",
    title:
      "/observability/events filter chips for new audit types + sessions tree multi-level rendering",
    highlights: [
      "v0.5.21-40 introduced 5 new audit-event types (tool_denied_by_policy, tool_output_truncated, session_forked, hook_dispatched, memory_stored). /observability/events only had pre-fab chips for round-13 chat-route families. v0.5.41 adds 5 chips — one per new type — so operators don't have to know the action name to filter.",
      "Chips: 'Tool denied by policy' (block icon), 'Tool output truncated' (content_cut), 'Session forked' (call_split), 'Hook dispatched' (webhook), 'Memory stored' (psychology). Each pre-populates the query bar with action:<type> + commits the filter on click.",
      "Sessions tree multi-level rendering: v0.5.38 indented ONE level for any fork. v0.5.41 walks the parentId chain (Map<id, session> lookup) to compute depth, cycle-defended via Set<seen> + capped at 8 levels. Session row uses style marginLeft: depth*16px instead of fixed ml-4.",
      "Scope limits: per-message Fork-from-here affordance still deferred (needs message-id propagation from chat-route's appendMessage to client-side ChatMessage tracking); cross-date-group reordering still deferred (fork created today appears under Today even when parent is in Yesterday).",
      "Forbidden going forward: removing the cycle defense in forkDepth(). Even though v0.5.30's fork-only path can't introduce cycles, future re-parenting flows might — the defense is cheap and load-bearing for UI stability.",
    ],
  },
  {
    version: "0.5.40",
    date: "2026-05-16",
    title:
      "/observability/cost group-by toggle (Provider / Model / Call kind / Session / Job)",
    highlights: [
      "Biggest remaining UI gap from #31's deferred half. v0.5.28's cost-warn builtin handled alerting; this closes the per-axis attribution display. Operators can now answer 'which job costs the most?' / 'which session burned the budget?' at a glance.",
      "/observability/cost gains a Group by pill-button row above the breakdown section. Five axes: Provider, Model, Call kind, Session, Job. Toggle is instant client-side — aggregator computes all five buckets in one pass.",
      "Provider derivation: model prefix match. gemini-* → 'vertex / gemini', claude-* → 'anthropic', gpt-*/o1-* → 'openai', fallback → first segment. No new column added; cheapest viable derivation from existing chat_turn_cost audit rows.",
      "Session derivation: target column ('session:<uuid>' → truncated label). Job derivation: trigger column ('job:<name>' → 'job:foo'; interactive chat → '(interactive chat)'). Both fields already populated by the trigger_context middleware since round-15.",
      "Forbidden going forward: removing the all-axes-in-one-pass discipline. Toggling renders a different bucket but doesn't recompute. Future axes (by skill, by instance) extend the aggregator but stay in one pass.",
    ],
  },
  {
    version: "0.5.39",
    date: "2026-05-16",
    title:
      "New status:ready-for-testing label + two-flavor issue-closure discipline (operator-testable vs auto-closable)",
    highlights: [
      "Pre-v0.5.39 the agent's mechanical labels were in-progress → dev-built → (operator smoke) → testing-complete. The 'agent has verified this end-to-end' state didn't exist — dev-built just meant CI built. Operator did both stages of smoke; redundant work. v0.5.39 introduces status:ready-for-testing for the agent's first-stage verification.",
      "New green label status:ready-for-testing (color 0E8A16). Agent applies AFTER its own headless smoke (API + UI walk through GCP IAP tunnel) passes. Operator then runs second-stage hands-on smoke + flips to testing-complete.",
      "Lifecycle now: status:spec → spec-approved → in-progress → dev-built → ready-for-testing → testing-complete → release-approved → released.",
      "Two issue-closure flavors codified: operator-testable (default for any operator-visible behavior — new UI / API / workflow / dashboard → agent applies ready-for-testing + STOPS) vs auto-closable (bug fixes with deterministic reproducers, doc-only, internal refactors with no observable behavior change → agent closes directly via Closes #N + status:released). Decision rule: when in doubt, operator-testable (over-asking cheap, under-asking risks shipping broken features).",
      "Agent headless smoke discipline documented in docs/CICD.md: setup via GCP IAP tunnel (localhost:3001 → phantom-vm:3000), API smoke via curl over the SSH tunnel, UI smoke via Playwright / Chrome MCP against the tunneled UI. Result reporting includes per-bullet pass/fail, screenshots of verified surfaces, API response excerpts, any unexpected behavior tagged blocking or follow-up.",
      "Mechanical re-label of in-flight: issues #22-32 (the 11 Octagon-gap sprint issues) flipped from status:in-progress to status:ready-for-testing. All add operator-visible behavior; all remain OPEN for the operator's hands-on smoke. The agent will run its own headless smoke as part of the v0.5.39+ sweep work.",
      "Forbidden going forward: applying status:ready-for-testing without running the agent's own smoke first (the label IS the smoke contract — claim-only application regresses to pre-v0.5.39); closing an operator-testable issue without status:released (agent-side smoke doesn't substitute for operator's hands-on validation); agent-driven status:testing-complete (operator-only).",
    ],
  },
  {
    version: "0.5.38",
    date: "2026-05-16",
    title:
      "Sessions sidebar renders fork relationships visually (closes #30 deferred UI piece)",
    highlights: [
      "v0.5.30 stored parent_id + fork_point_message_id on every session row, but /chat sidebar rendered all sessions flat — forked sessions looked identical to their parents. v0.5.38 surfaces the relationship: forks indent ml-4 + show a call_split icon next to the model badge with a tooltip naming the parent's id.",
      "SessionSummary interface gains optional parentId?: string | null. toSessionSummary() in /chat reads parent_id from the v0.5.30 schema. Sidebar's session row rendering branches on isFork = Boolean(session.parentId) to apply indent + icon.",
      "Scope limit: ONE level of indentation. Forks-of-forks appear at the same indent depth as direct children. Deeper tree rendering (multi-level indent + visible connector lines) is a future enhancement. Within-date-group grouping is preserved (groupSessionsByDate); a fork created today appears in Today's group even if parent is in Yesterday's. Cross-group reordering to keep parent + fork adjacent is also future enhancement.",
      "Per-message 'Fork from here' affordance still deferred. Session-level Fork from v0.5.36's SessionMenu forks the full conversation; per-message fork requires UI hook on AssistantMessage + message-id propagation to the fork API. Backend from_message_id parameter exists; only the UI wire is missing.",
      "Forbidden going forward: silent removal of the fork indicator. Future sidebar refactors must preserve the visual signal — without it, operators lose the audit trail in the UI.",
    ],
  },
  {
    version: "0.5.37",
    date: "2026-05-16",
    title:
      "Notification + PermissionRequest hook recursion defense (closes v0.5.32 caveat)",
    highlights: [
      "v0.5.32 wired #28's Notification + PermissionRequest fire-sites with the honest caveat: if an operator installs a Notification hook whose handler creates more notifications, the chain can recurse infinitely. v0.5.37 ships in-process suppression so the worst case is bounded.",
      "Implementation in mcp/agent/lib/hook-runner.ts: RECURSION_SUPPRESS_MS (default 5000, env HOOK_RECURSION_SUPPRESS_MS) + RECENT_DISPATCH_KEYS Map. recursionKey(event, payload) derives 'Notification:<id>' / 'PermissionRequest:<id>' from payload. dispatchHooks checks the key; if seen within the window, logs console.warn with event + key + last-fire delta + opt-out instructions, returns no-op aggregate.",
      "Scope: per-notification id (different notifications still each fire hooks), per-process (Map lives in agent Node process), 5-second default window (small enough for normal traffic, large enough to break sub-second recursion chains). Opt-out: HOOK_RECURSION_SUPPRESS_MS=0.",
      "NOT defended: recursion across DIFFERENT notifications. A Notification hook handler that creates a NEW notification with a different id still fires a fresh hook chain. Catches the common case (mirror-hooks re-firing on their own mirrors); deeper cycle detection requires shared state we don't have today.",
      "Forbidden going forward: silent recursion in any new hook event (e.g. future MemoryStored event must consider handler-driven recursion in its payload definition); removing the console.warn on suppression (operators reading server logs need to see when recursion was suppressed — silent suppression hides bugs).",
    ],
  },
  {
    version: "0.5.36",
    date: "2026-05-16",
    title:
      "Fork-session UI in /chat sidebar + plugin discovery wired at MCP startup",
    highlights: [
      "Two related gap fills. v0.5.30 shipped session-fork backend (schema + API + audit) but deferred UI — operators had to curl the API. v0.5.36 closes the UX gap with a Fork option in the session sidebar's per-row menu. v0.5.31 shipped plugin entry-point discovery but deferred the boot-time log_discovery() call. v0.5.36 wires it.",
      "Fork UI: SessionSidebar's per-row ⋯ menu gains a 'Fork session' entry (call_split icon) when the parent passes onForkSession prop. /chat's page.tsx adds handleForkSession callback that POSTs to /api/agent/sessions/{id}/fork (new proxy route), parses the new session id from the response, refreshes the sidebar, switches the chat pane.",
      "Operator UX: hover session row in sidebar → ⋯ menu → Fork session → backend copies the full message history → sidebar refreshes → chat pane switches to the new fork. Confirm in chat that messages sent now don't appear in the original (fork is independent — v0.5.30's memory-boundary discipline preserved).",
      "Plugin discovery: bundles/spark/mcp/src/main.py adds log_discovery() call after register_bench_routes. Walks all 5 reserved groups (phantom.skills, phantom.connectors, phantom.hooks, phantom.scanners, phantom.providers) and logs per-group counts. Wrapped in try/except so a discovery failure doesn't break MCP boot.",
      "Still deferred: per-message 'Fork from here' affordance (today: forks full conversation; from_message_id API support exists but no UI surface); sessions tree sidebar rendering parent → child relationships (forks appear as siblings in flat sidebar); plugin CONSUMER-side wiring — pip-installed packages can be discovered + counts logged, but their contributed handlers don't yet land in the agent's hook/skill/connector registry. Cross-language handler bridge is its own future release.",
      "Forbidden going forward: fork operations that bleed session-scoped memory across the boundary. v0.5.30 backend explicitly excludes session:<parent> memory from the new fork; future fork-UI affordances must preserve this.",
    ],
  },
  {
    version: "0.5.35",
    date: "2026-05-16",
    title:
      "/observability/bench UI page — operator-visible benchmark run history + per-run detail",
    highlights: [
      "v0.5.29 + v0.5.33 made benchmarks runnable (storage + runner + MCP tool). v0.5.35 closes the loop: operators browse runs without sqlite-digging. New /observability/bench page with run history + run-now form + per-row metrics; per-run detail page at /observability/bench/[run_id] with 5-axis aggregate + per-case table.",
      "Backend HTTP: new bundles/spark/mcp/src/api/bench.py with three endpoints — GET /api/v1/bench/runs (list), GET /api/v1/bench/runs/{id} (detail), POST /api/v1/bench/runs (trigger from UI). Wired into main.py after register_hook_routes — BenchRunStore() instantiated + set_bench_store() singleton so the benchmark_runner module resolves the store via bench_store().",
      "Agent passthroughs: /api/agent/bench/runs + /api/agent/bench/runs/[run_id] proxy to the MCP endpoints (same pattern as /api/agent/hooks/*). MCP_TOKEN bearer auth, no-store cache.",
      "List page: shows run_id + manifest_id + router_preset + 5 per-row metrics (correctness %, avg Jaccard, cost p50, wall p50, cases clean/total). Run-now form: manifest input (bundled id like phantom-soc-v1 or full path) + optional router-preset model override + Run Benchmark button. Synchronous trigger — returns when run completes.",
      "Detail page: aggregate-metrics card (5 axes including cost p50/p95 and wall p50/p95), then per-case table (case_id, correctness ✓/✗/n/a, Jaccard, cost, wall with ⚠ when over max_wall_seconds, error column for infrastructure-errored cases). Operators identify regressions or one-off bad cases at a glance.",
      "Forbidden going forward: silent skipping of infrastructure errors in the UI rate display. The Cases metric shows clean/total so operators see at-a-glance whether infra problems are confounding the rates. Dual-display preserves the per-v0.5.29 discipline of excluding infra errors from rates while keeping their count visible.",
    ],
  },
  {
    version: "0.5.34",
    date: "2026-05-16",
    title:
      "Skill-side frontmatter overrides for model + thinking + permissions (closes deferred halves of #22 + #23)",
    highlights: [
      "v0.5.22 (#22) and v0.5.23 (#23) shipped per-JOB model/thinking/permission overrides but deferred the per-SKILL surface. Operators writing skill MD files would naturally try `model: gemini-2.5-flash` or `thinking: true` in YAML frontmatter and find it does nothing. v0.5.34 wires the skill frontmatter so when a job is bound to a skill (action.skill = 'X'), the skill's frontmatter fields serve as fallback defaults for whichever job fields are unset.",
      "New helper bundles/spark/mcp/src/usecase/job_scheduler.py:_parse_skill_frontmatter(skill_name) -> dict. Reads the skill's MD body, extracts the YAML block between leading --- markers, parses with yaml.safe_load. Returns {} on any parse failure (graceful fallback to 'no skill override').",
      "Dispatch path resolves effective values: effective_model_id = row.model_id ?? skill_frontmatter.get('model'); effective_thinking = row.thinking_enabled OR skill_frontmatter.get('thinking') is True (skill can opt-IN but can't flip an operator's explicit False to True); effective_policy = row.permission_policy ?? skill_frontmatter.get('permissions'). These flow into _dispatch_chat exactly the same way as job-level values.",
      "Frontmatter shape: existing fields (displayName, category, icon, description, source, loadingMode, locked) untouched; three new fields (model, thinking, permissions) are additive. Skill authors can now recommend 'this skill works best on gemini-3.1-pro-preview with thinking on' and have it activate automatically when an unrouted job dispatches the skill.",
      "Precedence chain (narrowest wins): Job-explicit (operator set via /jobs/new) → Skill frontmatter (v0.5.34) → Runtime default (runtimeConfig.GEMINI_MODEL). Operator-explicit always beats skill-author-recommended; skill defaults fill in only when operator didn't set.",
      "Scope limit: v0.5.34 wires the JOB-DISPATCH path only. When an operator invokes a skill DIRECTLY in chat (not via scheduled job), the skill's model: field does NOT take effect today — chat header dropdown / runtime default still wins. The chat-route's skill-load path (where skillsForPrompt is built) doesn't yet read frontmatter for per-turn model selection. That's a follow-up release.",
      "Forbidden going forward: silent override of operator-explicit job fields by skill frontmatter (operator intent wins); use of skill frontmatter as a security boundary (operator-friendly defense in depth, not enforcement — plugin-contributed skills can declare anything; treat as suggestions).",
    ],
  },
  {
    version: "0.5.33",
    date: "2026-05-16",
    title:
      "Bench runner — operators can actually run a benchmark now (Issue #24 deferred-runner gap fill)",
    highlights: [
      "v0.5.29 shipped the bench scaffolding (BenchManifest, CaseScore, scorer, BenchRunStore). v0.5.33 adds the missing piece: the runner. Before today the smoke test for #24 was 'module importable' — that was all that worked. Now operators can run a 3-case sample corpus end-to-end against the chat route.",
      "New module bundles/spark/mcp/src/usecase/benchmark_runner.py. load_manifest(ref) resolves a manifest by path / bundled-corpus id / id-as-subdir. _dispatch_case(case, model_override?, thinking?) async-streams /api/chat SSE, collects text_delta + tool_call + meta cost. run_manifest dispatches every case, scores via the v0.5.29 scorer, records to BenchRunStore. Per-case errors flow into CaseScore.error and are excluded from rate denominators (per v0.5.29's infra-error discipline).",
      "Sample 3-case corpus at bundles/spark/mcp/src/usecase/bench_cases/phantom-soc-v1.yaml. Cases: generate-syslog (1 tool call expected — phantom_create_data_worker), list-scenarios (1 — phantom_list_scenarios), conversational-no-tool (0 tools). Each has prompt + expected_output_match (substring) + expected_tool_calls + max_wall_seconds.",
      "New MCP tool bench_run(manifest, router_preset_model?, thinking_enabled?) — approval-gated risk_tier=soft. Agent invokes from chat ('run the phantom-soc-v1 benchmark'). Returns {run_id, summary}. Registered in _BUILTIN_LEGACY_TOOLS in connector_loader.py.",
      "Operator usage: 'Run the phantom-soc-v1 benchmark' in chat → agent calls bench_run → 3 dispatches → scored summary in chat. Persisted run inspectable via docker exec phantom_agent sqlite3 /app/data/benchmark_runs.db.",
      "Still deferred: /observability/bench UI page (run history + compare + drill-down); CLI binary phantom bench run; larger curated corpus + val/test split; scheduled bench job; regression-flag release-gating integration.",
      "Forbidden going forward: skipping infrastructure-error exclusion in scoring; mutating phantom-soc-v1.yaml corpus without a baseline-rebaseline plan (corpus IS the SLO contract — add new corpora rather than mutate this one).",
    ],
  },
  {
    version: "0.5.32",
    date: "2026-05-16",
    title:
      "Wire up #28 Notification/PermissionRequest fire-sites + #22 thinking → Gemini thinkingConfig (gap-fill release)",
    highlights: [
      "Two items shipped in v0.5.21-31 as named-but-inert — operator installs the feature, tries it, sees nothing happen. v0.5.32 closes both: #28's Notification + PermissionRequest events now have MCP-side fire-sites; #22's thinking_enabled toggle now reaches Gemini's thinkingConfig.",
      "Architecture: hook dispatcher lives TS-side (lib/hook-runner.ts), so MCP-side code paths need a way to trigger it. New helper bundles/spark/mcp/src/usecase/hook_dispatch_callback.py with fire_hook_event_async(event, payload) — fire-and-forget HTTP POST on a daemon thread to the new TS endpoint /api/agent/internal/fire-hook (MCP_TOKEN bearer auth). Failures logged at debug only; never block the caller.",
      "MCP-side fire-sites: notifications.publish() now calls fire_hook_event_async('Notification', ...) after store.publish() succeeds. approvals_bus.request() now calls fire_hook_event_async('PermissionRequest', ...) after the approval row is inserted. Payload shapes match the TS-side HookPayload variants (sessionId/jobId/skillId derived from the contextvar's resolved_origin; risk_tier mapped to riskTier).",
      "Thinking wire: chat/route.ts destructures body.thinking, normalizes to turnThinking: boolean, threads through both callGemini invocations (initial + follow-up). callGemini gains a thinking parameter; when true, sets generationConfig.thinkingConfig = { thinkingBudget: -1, includeThoughts: true }. Flash variants silently ignore; Pro variants honor. Aligns v0.5.22's UI + storage + dispatch path with the actual Gemini behavior.",
      "Recursion caveat for Notification hooks: v0.5.32 ships without recursion defense. If an operator installs a Notification hook whose handler creates more notifications, each new notification fires the hook again. Workaround: don't install Notification hooks whose handlers create new notifications. Cleaner defense (header-based source tagging or per-thread in-hook flag) lands in follow-up if the caveat bites in practice.",
      "Forbidden going forward: notification creation that bypasses the publish endpoint (direct store.publish() calls must route through the API or pair with explicit fire_hook_event_async); firing Notification or PermissionRequest hooks from paths other than the wired choke points (notifications.py / approvals_bus.py).",
    ],
  },
  {
    version: "0.5.31",
    date: "2026-05-15",
    title:
      "Entry-point plugin discovery scaffolding — Octagon-gap Sprint final release (Issue #29 scoped down)",
    highlights: [
      "Issue #29 closes the autonomous Octagon-gap sprint push (11 issues across v0.5.21-31). Original spec was a full plugin lifecycle (entry-point discovery + marketplace UI + pip-install management + hot-reload + plugin detail pages + safety warnings + sandboxed execution). Multi-week effort with real security implications. v0.5.31 ships the DISCOVERY SCAFFOLDING — the contract third-party developers can target while consumer-side wiring (registries reading the discovered plugins) happens in parallel.",
      "New module bundles/spark/mcp/src/usecase/plugin_entry_points.py — distinct from the existing filesystem-based plugin_loader.py (Phase X, directory-discovered). v0.5.31's loader is for pip-installable Python packages that declare contributions via setup.py / pyproject.toml entry_points.",
      "Five reserved group names: phantom.skills, phantom.connectors, phantom.hooks, phantom.scanners, phantom.providers. PluginRef dataclass identifies group + name + dist_name + dist_version + target. discover_plugins(group) walks importlib.metadata.entry_points(group=...). discover_all() across all five. log_discovery() emits boot-time logs + returns per-group counts for telemetry.",
      "Third-party contract — in your pyproject.toml: [project.entry-points.'phantom.skills'] my-skill = 'my_pkg.skills:my_skill_factory'. The agent walks these at boot.",
      "Deferred to follow-up release: actual consumer-side wiring (skill registry / hook store / scanner registry reading discover_plugins results and registering contributed objects); marketplace UI for pip-install-driven management; hot-reload on install (today: install + restart); plugin detail pages + safety warnings + signing/verification; the log_discovery() call wired into MCP main.py startup (v0.5.31 ships the module ready to be called).",
      "Sprint final tally: v0.5.21-31 close 11/11 Octagon-gap sprint issues. Four builtin-hook customers (slack-approval, pre-compact-context-warning, memory-inject, cost-warn-over-budget) prove the v0.5.21 framework was the right shape. Three additive jobs.db migrations (v0.5.22 model_id+thinking, v0.5.23 permission_policy, v0.5.30 sessions parent_id+fork_point) all use the same pragma_table_info probe pattern — volumes preserved across every release.",
      "Forbidden going forward: auto-install of plugins at boot (operator-explicit pip-install action only; auto-discovery from config file is a foot-gun); plugin install via skill / chat-tool (plugins that install plugins is a privilege-escalation vector); bypass of validation when the consumer side lands (plugin manifests go through the same validation as built-in ones).",
    ],
  },
  {
    version: "0.5.30",
    date: "2026-05-15",
    title:
      "Session forking — branch a new session from an existing one's history (Issue #30 scoped down)",
    highlights: [
      "Issue #30's original spec was the full CyberGym session-tree UX: per-message Fork affordance in /chat, sessions tree sidebar with parent→child rendering, archive flag, drill-down detail, per-session memory scope visualization, /observability/events session-created/forked/archived event chips. v0.5.30 ships the BACKEND PRIMITIVE — schema + fork_session() + API + audit — so the data is there. The UI tree + per-message affordance + archive toggle defer to a follow-up release.",
      "Schema: bundles/spark/mcp/src/usecase/session_store.py gets two additive columns on the sessions table — parent_id TEXT + fork_point_message_id TEXT. Both nullable; existing non-fork rows stay NULL. Follows the same pragma_table_info probe migration pattern as the jobs.db model_id / thinking_enabled / permission_policy_json columns.",
      "New method: fork_session(from_session_id, from_message_id?, title?, user?) -> Session | None. Validates parent existence + fork-point belongs-to-parent (returns None on mismatch — surfaces the bug rather than silently forking the wrong slice). Inserts new session with parent_id + fork_point + meta tagged 'forked_from'. Copies messages up-to-and-including fork point (or all when fork-point omitted). Each copy gets a fresh id but preserves original ts so the fork reads chronologically the same way the parent did.",
      "Memory scope boundary (load-bearing): fork_session does NOT copy session:<parent_id>-scoped memory entries into session:<new_id>. Forking is for hypothetical exploration; bleeding parent state defeats it. The `agent` scope is still shared as cross-session knowledge (unchanged), but per-session is genuinely partitioned.",
      "API: POST /api/v1/sessions/{session_id}/fork with body {from_message_id?, title?, user?}. Returns {session: <new>} on 201; 404 when parent not found OR fork-point doesn't belong to it. Audit event session_forked fires with parent_id + fork_point_message_id + messages_copied metadata.",
      "Deferred to follow-up release: /chat per-message Fork affordance + modal; sessions tree sidebar with parent→child rendering + /chat/<session-id> deep-link URLs; archive flag column + UI toggle; MCP tool sessions_fork for agent-driven forking from chat phrasing; /observability/events filter chip for session_forked (events fire today — just no chip UI yet).",
      "Forbidden going forward: bleeding session:<parent_id> memory into the fork (hypothetical-exploration principle); tool-state inheritance across fork (tool state belongs to the running SDK adapter, not the session store — forks start with fresh adapter, message history is what's cloned); automatic session deletion (existing prune_older_than stays operator-driven opt-in).",
    ],
  },
  {
    version: "0.5.29",
    date: "2026-05-15",
    title:
      "Benchmark harness scaffolding — manifest + 5-axis scorer + storage (Issue #24 scoped down)",
    highlights: [
      "Issue #24's original spec was a full benchmark stack: runner, scorer, corpus, CLI, /observability/bench UI with run history + compare + drill-down, weekly auto-run, regression-flag release-gating. Roughly the same scope as v0.5.21-28 combined. v0.5.29 ships the SCAFFOLDING so the data model + scoring + storage are in place; the runner + UI + CLI defer to a future release that gets to focus on bench end-to-end.",
      "Module: bundles/spark/mcp/src/usecase/benchmark.py. BenchCase + BenchManifest Pydantic models (YAML-friendly shape: id, prompt, expected_output_match substring/regex, expected_tool_calls list, max_wall_seconds soft target). CaseScore + BenchSummary dataclasses with the 5 axes: correctness rate, tool-call Jaccard, cost p50/p95, wall p50/p95, infrastructure errors EXCLUDED from rates (conflating infra failures with quality regressions wastes investigation cycles).",
      "Scoring helpers: score_case (substring match for v0.5.29; regex support deferred), jaccard (order-agnostic similarity 0..1), percentile (linear interpolation), summarize (rolls case scores into BenchSummary).",
      "Storage: BenchRunStore sqlite-backed at benchmark_runs.db (NEW file alongside existing memory.db / hooks.db / jobs.db — no schema change to any existing table). Columns: run_id, manifest_id, started_at, completed_at, summary_json, router_preset. Indexed on (manifest_id, started_at DESC) so 'latest run for manifest X' is O(log n).",
      "Deferred to follow-up release: the runner that dispatches each case against the chat-route HTTP endpoint, collects tool calls + response + cost + wall, feeds score_case; an operator-supplied or bundled corpus (manifest YAML format documented in the module docstring); MCP tool bench_run for agent-from-chat firing; /observability/bench page; CLI binary; scheduled bench job; regression-flag release-gate integration.",
      "Forbidden going forward: skipping infrastructure-error exclusion in scoring (cases that fail because chat-route was unreachable are NOT quality regressions); corpus changes without a separate spec issue once the corpus exists (corpus IS the SLO contract; mutations need baseline-rebaseline plans).",
    ],
  },
  {
    version: "0.5.28",
    date: "2026-05-15",
    title:
      "Cost-warn-over-budget builtin — daily cost crossing alarm (Issue #31 scoped down)",
    highlights: [
      "Issue #31's original spec called for a full cost-ledger refactor: new cost_entries sqlite table with per-skill/per-job/per-instance attribution, group-by UI on /observability/cost, top-N tables, cost-limit settings with deny enforcement. That's a multi-week effort. v0.5.28 ships ONLY the operator-trust primitive: the cost-warn-over-budget builtin. The full attribution + UI overhaul moves to a follow-up release.",
      "Builtin: mcp/agent/lib/hook-builtins/cost-warn-over-budget.ts. Compatible with RunEnd. Three operator-configurable fields: threshold_usd (default $10), suppress_repeat_hours (0-24, default 1), notify_category (default 'cost-warning').",
      "On every RunEnd: reads existing chat_turn_cost audit rows since UTC midnight (no new schema; uses the existing audit surface recorded since round-12), sums metadata.cost_usd, compares to threshold. If over AND outside suppression window, fires a severity=warn notification with the per-day rollup.",
      "Registry now has FOUR builtins: slack-approval (v0.5.21), pre-compact-context-warning (v0.5.25), memory-inject (v0.5.26), cost-warn-over-budget (v0.5.28). The /api/agent/hooks/builtins catalog exposes all four; /settings/hooks dropdown picks them up.",
      "What's deferred to the follow-up release (a future tag): cost_entries sqlite table with attribution columns; group-by toggle on /observability/cost (by-Job / by-Skill / by-Instance / by-Session); per-job / per-skill / per-instance cost-limit settings; deny-when-exceeded enforcement (today's primitive is alarm only — deny mode requires operator validation of the alarm pattern first); drill-down detail pages.",
      "Forbidden going forward: new cost data path bypassing chat_turn_cost audit (single source today; any future cost-entries table must write to both during cutover); enforcement (deny-tool-call when over limit) in this builtin (alarm only — deny mode is a separate decision the operator will make in the follow-up).",
    ],
  },
  {
    version: "0.5.27",
    date: "2026-05-15",
    title:
      "Tool-output evidence truncation — keep head + tail, drop the noisy middle",
    highlights: [
      "Issue #32 from the Octagon-gap analysis. Long tool outputs (e.g. xlog_logs_tail(count=1000)) blow the agent's context window with 200K of repetitive log noise that crowds out reasoning AND inflates input-token cost on every subsequent turn until compaction. Octagon hit this in Verify phase and added truncation; v0.5.27 brings the same primitive to Phantom's chat route.",
      "New module mcp/agent/lib/evidence-truncation.ts with TruncationPolicy + applyTruncation(toolName, output, policy). Strings over maxBytes get head + marker + tail; structured returns pass-through by default (truncating mid-JSON breaks the parser); operators wanting structured truncation set applyToStructured=true explicitly.",
      "Chat-route integration: after mcpClient.callTool() returns and before the result is used downstream (functionResponse, tool_result SSE event, history persistence), each text-content entry in result.content[] runs through applyTruncation. Truncated entries get the head + marker + tail; rest pass through. Audit event tool_output_truncated fires with bytes_dropped / bytes_kept / head_kept / tail_kept / max_bytes / content_index metadata for forensic visibility.",
      "Defaults: enabled, maxBytes=16384, headKeep=4096, tailKeep=4096. Marker text: '[... truncated {N} bytes — ask the operator if you need a specific window ...]'. Operators tune via four env vars: EVIDENCE_TRUNCATION_ENABLED, EVIDENCE_TRUNCATION_MAX_BYTES, EVIDENCE_TRUNCATION_HEAD_BYTES, EVIDENCE_TRUNCATION_TAIL_BYTES.",
      "Per-job / per-tool config (e.g. xlog_logs_tail gets 65536, caldera_* stays at default) deferred to a follow-up release once the smoke matrix confirms the env-var defaults are sensible. Today's surface is global — works for the 90% case; tuning lands when there's evidence the 10% needs it.",
      "Forbidden going forward: silent truncation without the audit row (every truncation fires tool_output_truncated, debuggability is non-negotiable); structured returns truncated by default (mid-JSON cuts break parsing); truncation of audit-log / security-sensitive tool outputs in any future per-tool config (forensic surfaces need full content, head+tail is misleading).",
    ],
  },
  {
    version: "0.5.26",
    date: "2026-05-15",
    title:
      "Memory auto-inject builtin hook — deterministic recall on every chat turn",
    highlights: [
      "Issue #25 from the Octagon-gap analysis. Third builtin-hook customer (slack-approval was v0.5.21's first, pre-compact-context-warning was v0.5.25's second). Octagon's inject_memory_context() fires deterministically at the start of Recon; Phantom's agent today has to remember to call memory_search and only does ~30% of the time. v0.5.26 makes it deterministic.",
      "Builtin name: memory-inject, fires on UserPromptSubmit. Four config fields: scope (default 'agent' cross-session; supports __session__ placeholder for current-conversation scope), top_k (1-20 default 5), min_score (0-1 default 0.2), header (customizable text rendered above the injected block).",
      "Flow: on every UserPromptSubmit, extracts operator's message, calls POST /api/v1/memories/search with {query, limit, scope, min_score}, formats top-K hits into a bullet list, returns {injectContext: <block>}. The chat-route's UserPromptSubmit handler has prepended injectContext to the system instruction since Phase H; the new bits in v0.5.26 are just what the builtin contributes.",
      "Why UserPromptSubmit not RunStart: at RunStart the user hasn't submitted the message yet, so there's no search query. UserPromptSubmit has the message + sessionId. The Octagon analog (Recon phase) similarly has the target spec at hand when the inject fires.",
      "Operator economics: enabling this hook means every chat turn searches memory (~30ms cosine over thousands of rows, well under the dispatcher's 5s default timeout) and adds top_k memories to the system instruction (~500-2000 tokens depending on memory size). Cost increase is proportional to top_k and length of stored memories. Operators with very large memory tables should raise min_score to 0.4+ or drop top_k to 3.",
      "Install path: /settings/hooks → Add hook → Built-in → 'Memory auto-inject' → event UserPromptSubmit → tune scope/top_k/min_score → Save. v0.5.26 ships the builtin available; the operator decides whether they want it on (the noise + cost tradeoff is workload-specific).",
      "Registry now has THREE builtins: slack-approval, pre-compact-context-warning, memory-inject. Future releases add: cost-warn-over-budget (Issue #31), rate-limit-by-tool (future), evidence-truncation-hook (alternative path for #32). The catalog at /api/agent/hooks/builtins enumerates them.",
      "Forbidden going forward: silent expansion of injection scopes (a fan-out scope like 'instance:*' requires a separate spec issue — more context per turn = more cost); injection without an audit trail when memory_id is sensitive (sensitivity mark lands as a separate feature; until then, all memories are equally injectable).",
    ],
  },
  {
    version: "0.5.25",
    date: "2026-05-15",
    title:
      "Pre-compact context-usage warning builtin — heads-up before auto-compaction strips early conversation",
    highlights: [
      "Issue #27 from the Octagon-gap analysis. Second builtin-hook customer (slack-approval was first in v0.5.21). Pre-v0.5.25 auto-compaction was silent — operators discovered AFTER the fact that 30 minutes of incident analysis got summarized to three bullets. The PreCompact event was already wired in chat-route since Phase H; the missing piece was a builtin that subscribes to it and warns the operator.",
      "Built into mcp/agent/lib/hook-builtins/pre-compact-context-warning.ts with three operator-configurable fields: threshold_pct (50-95, default 80), suppress_repeat_minutes (0-60, default 5, prevents banner-spam in busy turn clusters), notify_category (default 'context-warning' — operators filter their /notifications page by it).",
      "On PreCompact fire: reads a per-session in-process suppression cache; if within the window, no-ops; otherwise POSTs to /api/v1/notifications with severity=info, the warning text, and the PreCompact payload context (kind manual/auto, message_count, threshold). Records the suppression timestamp.",
      "Non-decisional — does NOT veto compaction. Just announces. Operators who want a 'never compact this session' mode get it via a future extension (a small config option to return decision: 'deny' from the handle()).",
      "Install path: /settings/hooks → Add hook → Transport: Built-in → pick 'Pre-compact context warning' → optionally tune threshold + suppress window → Save. No auto-install on fresh boots (operators decide what noise they want); v0.5.25 trusts the operator's intentional install rather than imposing a default.",
      "Registry growth: BUILTIN_HOOKS now exposes slack-approval AND pre-compact-context-warning. /api/agent/hooks/builtins lists both; /settings/hooks dropdown picks them up automatically. The slack-approval was v0.5.21's first builtin; this is the second; v0.5.26 will add the third (memory auto-inject).",
      "Forbidden going forward: auto-installing the hook without operator opt-in (Phantom doesn't ship hooks the operator didn't ask for); silent compaction in any future chat-route refactor (PreCompact MUST fire so the registered hook works).",
    ],
  },
  {
    version: "0.5.24",
    date: "2026-05-15",
    title:
      "Register Notification + PermissionRequest hook events (forward-compat — fire-sites land later)",
    highlights: [
      "Issue #28 from the Octagon-gap analysis. Small additive release: adds two new event names — Notification + PermissionRequest — to HOOK_EVENTS (lib/hooks.ts), KNOWN_HOOK_EVENTS (bundles/spark/mcp/src/api/hooks.py), and the /settings/hooks event dropdown. Plus SubagentStart + SubagentEnd which existed in lib/hooks.ts since Round-15 / Phase S but weren't in the form's dropdown — audited and fixed together.",
      "Operators can now install hooks against these events from /settings/hooks. Common use cases the events unlock when fire-sites land in a follow-up: routing every error notification through a Slack webhook (HTTP transport pointing at #soc-ops); pager-duty alert on critical approval requests; mirror every approval to an audit pipeline.",
      "Forward-compat caveat: the FIRE-SITES — MCP-side code paths that actually emit the events when a notification is created or an approval is requested — are NOT yet wired. Operators can install hooks today; the hooks WILL register in the SqliteHookStore and appear at /settings/hooks; they just won't fire until the follow-up release adds the dispatcher path (MCP → webhook → agent → hook-runner).",
      "HookPayload discriminated union gains two new shapes: Notification carries notificationId + severity + category + title + body + related (sessionId / jobId / instanceId); PermissionRequest carries requestId + source (chat-tool-call / job-run / skill-invocation) + actor + requestedAction (toolName + arguments) + riskTier.",
      "Why split from the bigger #25 + #27 builtin-hook work: contained-release discipline. #28 is a tiny additive name-registration change; the builtin handlers that USE these events (memory-inject-session-start watches RunStart; pre-compact-context-warning watches PreCompact; future approval-router would watch PermissionRequest) get their own releases where their UI + behavior + tests fit one operator-validation cycle.",
      "Forbidden going forward: firing Notification or PermissionRequest from MCP without a dispatcher path (the fire-site needs to round-trip to the agent's hook-runner via a TBD /api/agent/internal/fire-hook endpoint; direct in-MCP hook dispatch isn't a thing yet).",
    ],
  },
  {
    version: "0.5.23",
    date: "2026-05-15",
    title:
      "Per-job permission policies — declarative tool allowlists enforced by the chat route",
    highlights: [
      "Issue #23 lands as the third Sprint-1 Octagon-gap deliverable. Pre-v0.5.23 every job's dispatched chat turn could call ANY MCP tool — there was no per-job scope check. v0.5.23 adds a declarative permission policy each job carries: three lists (allowed_tools, denied_tools, require_approval) of glob patterns the chat route's tool-dispatch loop consults before each tool fires. A denied call short-circuits to a synthetic tool-error response the model sees as a failed call.",
      "Backend: new lib/permission-policy.ts with the evaluator + lenient validator. jobs.db gets a third additive column (permission_policy_json TEXT) following the v0.5.22 migration pattern. JobRow + add_job + update_job + _dispatch_chat + jobs API + MCP tools (jobs_create / jobs_update) all extended. update_job uses sentinel semantics: None=preserve, {}=clear, non-empty=set.",
      "Chat-route enforcement: chat-route.ts destructures body.permission_policy, runs validatePermissionPolicy(), then before each mcpClient.callTool() in the tool-dispatch loop calls evaluatePermissionPolicy(toolName, policy). On deny: synthesizes a functionResponse with denied_by_policy=true so the model loop sees it as a tool error, emits a tool_call SSE event with status='denied_by_policy', and best-effort audits via tool_denied_by_policy.",
      "Glob syntax: same as HookMatcher.toolGlob — `*` matches any sequence, `?` matches one char, comma-separated lists are OR. Evaluation precedence (narrowest wins): denied → require_approval → allowed (whitelist when non-empty) → allow-by-default. Empty policy = fully permissive (operator opts INTO restrictions, backwards-compatible default).",
      "UI: /jobs/new + /jobs/[id] gain a Permission policy section right below the Model dropdown / Thinking toggle from v0.5.22. Three comma-separated glob inputs (Allowed / Denied / Require approval), inline placeholders showing example globs. ACTIVE badge appears when any field is non-empty.",
      "Docstring discipline (CLAUDE.md rule 9): jobs_create + jobs_update Args sections document the policy shape, glob syntax, evaluation precedence, AND concrete trigger phrases ('only let this job touch xlog tools', 'approve any *_delete this job tries') so the agent sets the right values when the operator phrases the request in chat.",
      "Not a security boundary by itself. The MCP-side approval gate (Phase 11 humanRequired) remains the authoritative defense for destructive tools. Permission policies are an operator-facing scope check that runs BEFORE the approval gate — defense in depth. The CHANGELOG + help-architecture page surface this explicitly.",
      "Per-skill permission policies deferred to a follow-up release (same reasoning as v0.5.22's skill-side model override — skills affect chat-turn dispatches, different code path than scheduled jobs, separate integration window).",
      "Docs: /help/architecture#permission-policies (evaluation precedence + dispatch flow + the security-boundary disclaimer); /help/user#permission-policies (operator-facing guide); journey ops-restrict-job-tools.",
      "Forbidden going forward: bypassing the policy check for 'trusted internal' tools (every tool runs through evaluatePermissionPolicy); silent crash on malformed policy shape (the validator degrades to null = no policy, operator sees unrestricted vs mystery error); per-skill policy without the corresponding chat-turn integration (skills get their own release window).",
    ],
  },
  {
    version: "0.5.22",
    date: "2026-05-15",
    title:
      "Per-job model override + extended-thinking toggle — pick the right model for each job's economics",
    highlights: [
      "Issue #22 lands as the second Sprint-1 Octagon-gap deliverable. Pre-v0.5.22 every job dispatch used the runtime default model (runtimeConfig.GEMINI_MODEL); operators with mixed workloads — say, a nightly summary that needs Pro reasoning AND a high-volume log generator that's fine on Flash — were stuck overpaying for one or underdelivering on the other. v0.5.22 adds a 'Model' dropdown to /jobs/new (and a matching column in jobs.db) so each job picks its own model + an extended-thinking toggle when the picked model supports it.",
      "Scope narrowed during implementation: original spec said 'per-job + per-skill', but skills affect chat-turn dispatches (different code path than scheduled jobs) so the skill-side override moves to v0.5.23+. This isolates the change to one surface (scheduler.dispatch → body.model → chat-route's existing resolveModelName) without forcing a parallel migration on skills frontmatter.",
      "Backend: jobs.db gets an additive ALTER TABLE adding model_id TEXT (nullable — NULL means 'use runtime default') and thinking_enabled INTEGER (default 0). Follows the same migration pattern bypass_approvals used in v0.1.27; pre-migration rows preserve their existing behavior. The chat dispatcher (_dispatch_chat) threads model_id into the chat-route POST body as body.model and thinking_enabled as body.thinking.",
      "UI: /jobs/new + /jobs/[id] gain a Model dropdown right below the Bypass-approvals toggle. Populated from /api/agent/models filtered to chat-kind models. Default is 'Router default (no override)'. Selecting a model that lacks supportsThinking force-disables the Thinking toggle so we don't ship payloads the dispatcher silently ignores.",
      "MCP tools: jobs_create + jobs_update accept model_id + thinking_enabled with full docstrings per CLAUDE.md rule 9 — Args sections name concrete trigger phrases ('run this on flash', 'use gemini-pro for the nightly summary', 'use deep thinking') so the agent picks the right value when the operator phrases the request in chat. update_job uses sentinel semantics: omit/None to preserve, empty string to clear, string to set.",
      "Forward-compat caveat: thinking_enabled is STORED + DISPATCHED today (body.thinking flows through), but the chat-route's Gemini call payload doesn't yet wire body.thinking → thinkingConfig. Visible-fail-no-effect, not crash-fail — operators who enable thinking on a job today see no behavior change until the follow-up release lands the Gemini-side integration. Documented honestly in the docstring + CHANGELOG.",
      "Why this discipline: contained-release principle. v0.5.22 ships the operator-facing surface + the storage that's testable end-to-end (model_id flows through the dispatch and back to chat-route's resolveModelName, which has worked since round-12). The chat-route's thinking integration is its own integration point with its own test surface; combining them in one release would force the operator to test two things in one cycle.",
      "Docs: /help/architecture#model-routing (the resolution chain — per-job override → runtimeConfig.GEMINI_MODEL → hardcoded fallback — plus the dispatch flow diagram); /help/user#model-routing (when to override: cost-driven 'put this volume job on flash', quality-driven 'this analysis needs Pro + thinking'); journey ops-set-job-model-override walks the 3-minute setup.",
      "Forbidden going forward: reading runtimeConfig.GEMINI_MODEL outside resolveModelName() (single source per round-12 discipline); validating model_id at job-create time (model availability can shift between create and dispatch; dispatch-side error handling is the right surface); silent model downgrade on dispatch failure (operator must see 'model X no longer configured' as a clear error, not a quiet fallback).",
    ],
  },
  {
    version: "0.5.21",
    date: "2026-05-15",
    title:
      "Add builtin hook transport — install Slack approval (and future framework hooks) from /settings/hooks with no code",
    highlights: [
      "Issue #26 from the Octagon-gap analysis sprint lands first as the foundation for three follow-ups (#25 auto-inject memory, #27 pre-compact warning, #31 cost-ledger refactor — all want to ship as builtins). Phantom's hook framework now supports four transports: command (subprocess), http (webhook), agent (Phase X plugin slot, still stub), and the new builtin — an in-process TypeScript handler shipped with the agent image, registered in lib/hook-builtins/index.ts, picked by name from /settings/hooks with a dynamic config form.",
      "Operator economics, before vs after: pre-v0.5.21 a Slack approval install meant either pasting a 25-line JSON snippet from lib/slack-approval-hook.ts into /settings/hooks OR deploying a slack-approval-receiver yourself and pointing the http-transport at it. Post-v0.5.21 it's a dropdown pick (Built-in → Slack approval) + filling 'Webhook URL' + optional 'Auth header'. Two clicks instead of twenty.",
      "v0.5.21 ships exactly one builtin — slack-approval — to validate the registry pattern. Future issues add more: #25 contributes memory-inject-session-start / memory-inject-instance-focus / memory-inject-job-run; #27 contributes pre-compact-context-warning; #31 contributes cost-ledger + cost-warn-over-budget. The catalog is enumerable at GET /api/agent/hooks/builtins so the UI dropdown stays in sync with what the image actually ships.",
      "Validator chain: agent-side validateHook (lib/hooks.ts) checks that transport.name resolves in the registry + invokes the spec's validateConfig(transport.config) to confirm shape; bad configs are rejected at write time. MCP-side validator (bundles/spark/mcp/src/api/hooks.py) accepts the broader 'builtin' transport with a name + config object, trusting the agent's richer validator. Dispatch-time defense-in-depth: hook-runner re-validates before calling spec.handle() so a config schema change between releases can't silently misfire.",
      "UI surface in /settings/hooks: transport dropdown gets a 4th option (defaulted on Add hook for new installs); selecting Built-in renders a builtin-name dropdown + a dynamic config form generated from the spec's configFields (six field types supported: string / url / number / boolean / select / secret-ref). List rows render a transport badge — built-in (secondary color), http (primary), cmd (tertiary), agent (neutral) — for at-a-glance auditing.",
      "Backwards compatibility: lib/slack-approval-hook.ts (the legacy JSON-snippet helper) is preserved. Operators who pasted JSON from it before v0.5.21 keep working — they produce http-transport hooks that function identically to the new builtin-transport equivalent. New installs should prefer the builtin path; legacy retirement happens in a future release once operator usage has drained.",
      "Docs: /help/architecture#hooks-transport-types — new subsection explaining when to pick each transport with latency + extensibility tradeoffs; /help/user#hooks-builtin — new subsection introducing the builtin concept with a privilege-boundary callout (builtins run with agent privileges; operators wanting isolation should stay on HTTP); journey ops-install-builtin-hook walks the 3-minute beginner flow.",
      "Forbidden post-v0.5.21: deleting command/http transports (builtin is additive, not a replacement); skipping the dispatch-time validateConfig re-check (drift across releases is real); adding builtins that reach the network with hardcoded URLs (URLs must come from operator config — see slack-approval's webhookUrl); bypassing the type-only import boundary between lib/hook-builtins/types.ts and lib/hooks.ts.",
      "No new dependencies. The builtin spec uses plain TS-typed validator functions matching the existing validateHook pattern; the dynamic UI form renders standard HTML inputs without form libraries. Build stays the same shape; no installer change. Volumes preserved (additive code change, no schema migration).",
    ],
  },
  {
    version: "0.5.20",
    date: "2026-05-15",
    title:
      "Revise CI/CD model: remove UI Update button, S1 uses existing installer, S2/S3 both major bumps via installer flag",
    highlights: [
      "Operator review of v0.5.19 surfaced six model gaps: UI Update button described but doesn't operate, PATCH versioning for S2 lost the new-installer signal, S2 vs S3 was a runtime prompt instead of an installer flag, S3 rollback had partially-automated tar restore steps, path-filter contract didn't emphatically state 'no new image / no new release tag for untouched services,' and the green ↑ arrow in the Dev cycle diagram floated in the wrong gap. Closes #21.",
      "The new model in one paragraph: Scenario 1 (code-only) = MINOR bump within current major (v5.29 → v5.30), customer re-runs their EXISTING installer on disk, volumes preserved. Scenarios 2 + 3 are both MAJOR bumps (v5.29 → v6.0); customer downloads NEW installer. The new installer has a build-time WIPE_VOLUMES flag: S2 builds with =false (preserve), S3 with =true (wipe → fresh defaults). No in-UI Update button at any tier; upgrades happen via installer ONLY.",
      "SVG fixes (5): green ↑ arrow realigned to anchor under 'Install dev binary'; Release cycle Customer-consumes panel rewritten to remove UI Update button and split A=Minor (existing installer) / B=Major (new installer with flag); three scenario cards rewritten with new versioning (S1 MINOR, S2 + S3 both MAJOR) and installer-flag-based volume policy; Scenario 3 rollback card simplified to 'Fully manual · NO automation' with footer 'NO AUTOMATED RESTORE BY DESIGN'; path-filter subtitle changed to 'NO new image · NO new release tag · same digest retagged from prev release' with header emphasis 'UNTOUCHED SERVICES NEVER REBUILD OR RETAG.'",
      "docs/CICD.md: § Change scenarios fully rewritten with new model + new 'WIPE_VOLUMES flag' subsection explaining build-time mechanic; § Decision tree updated for new versioning split; § Scenario implementation status table rewritten (flag-based mechanic is the new future-work item); § Customer onboarding step 7 + § Operator yank procedure scrubbed of UI Update mentions; § Rollback Scenario 3 rewritten as fully manual; § phantom-updater reframed (primary role is now per-instance connector container lifecycle; upgrade endpoints are vestigial); § Per-service path-filter contract gets a new 'untouched services invariant' subsection explicitly stating no new image, no new release tag, same digest retagged.",
      "CLAUDE.md: three-scenario summary table updated (S1 Minor v5.29→v5.30, S2/S3 MAJOR v5.29→v6.0 with WIPE_VOLUMES flag); phantom-updater cross-reference updated to reflect the v0.5.20 reframing.",
      "WIPE_VOLUMES flag is build-time, not runtime: the mechanism distinguishing S2 (keep volumes) from S3 (wipe → fresh defaults) is a flag baked into the installer binary at build time by installer/build-phantom-installer.sh based on the release issue's scenario:* label. The release.yml workflow reads this label and sets the flag at installer-build time. Customer install behavior is deterministic from the binary they downloaded — no runtime confirmation prompts, no escape hatches.",
      "Implementation status: the WIPE_VOLUMES flag mechanic is NOT YET IMPLEMENTED in installer/build-phantom-installer.sh. v0.5.20 ships the documentation contract; the first non-trivial S2 or S3 release will require the implementation work. Today's installer behaves as 'Scenario 1 with baked-in digests' — works for current usage, doesn't yet support the major-bump flag distinction.",
      "Forbidden post-v0.5.20: re-introducing UI Update button in customer-facing docs (not an upgrade path we operate); mixing the new scenario model with the old PATCH-S2 versioning; documenting automated S3 rollback steps (S3 rollback is operator-manual by design); building an interactive UPGRADE confirmation prompt for S3 (the mechanic is a build-time flag, not a runtime prompt).",
      "Third end-to-end exercise of the v0.5.17 spec-driven discipline. Lifecycle proceeded: operator chat described changes → agent opened #21 with full template body → mechanical labels applied → operator verbal authorization → status:spec-approved → implementation with iterative before/after screenshots per operator request → push (Closes #21) → status:in-progress → CI → status:dev-built → smoke matrix posted.",
    ],
  },
  {
    version: "0.5.19",
    date: "2026-05-15",
    title:
      "Update CI/CD diagram + docs to reflect the v0.5.17/v0.5.18 spec-driven workflow",
    highlights: [
      "v0.5.16's SVG showed the build/test/release pipeline as if it stood alone. v0.5.17 added the spec issue lifecycle and v0.5.18 added the area dimension; the diagram was out of date. v0.5.19 makes the visual whole again. Closes #20 (second issue exercised end-to-end under the v0.5.17 spec-driven discipline).",
      "New Section 0 'Spec-driven workflow lifecycle' added at the top of docs/cicd-pipeline.svg, showing the 7-stage state machine that wraps the existing pipeline: spec → spec-approved → in-progress → dev-built → testing-complete → release-approved → released. Each stage rendered as a colored box matching the actual GitHub label color (gray → blue → yellow → cyan → green → orange → purple) with stage number + label name + transition description + AGENT/OPERATOR ownership pill.",
      "Below the 7 stages, an 'anchor panel' (WHERE EACH STAGE ANCHORS IN THE PIPELINE BELOW) shows which downstream section materializes each lifecycle event: in-progress ↓ Dev cycle § git push, dev-built ↓ Dev cycle § staged binary + dev-latest, release-approved ↓ Release cycle § git tag vX.Y.Z, released ↓ Release cycle § GitHub Release publish · closes #N.",
      "viewBox extended from 1200×1740 to 1200×1980 (+240px tall). All existing 6 sections + summary bar shifted down by 240px; layout otherwise unchanged. Diagram now reads top-to-bottom as lifecycle → pipeline.",
      "docs/CICD.md § Visual overview gets a new top row in the section-to-diagram map, plus a closing paragraph clarifying the mental model: the lifecycle is the OUTER state machine; the pipeline sections are the INNER mechanics that fire on lifecycle transitions.",
      "CLAUDE.md cross-reference audit: all 17 docs/CICD.md#... anchors used in CLAUDE.md verified against the 132 headings in docs/CICD.md using GitHub's slug derivation rules. All resolve cleanly — no broken links, no changes needed to CLAUDE.md.",
      "Design choices: new section at the TOP because lifecycle precedes pipeline temporally (issue opens before any code is written); color-match to actual label colors (not pipeline-section colors) so the visual ↔ GitHub tracker correspondence is exact; anchor panel between lifecycle and pipeline (not long arrows running through existing sections) to avoid visual noise; no animation on lifecycle stages (state machine is reference material, not time-lapse).",
      "Forbidden post-v0.5.19: adding new SVG sections without updating the section-to-diagram map in docs/CICD.md (orphaned sections are a UX gap); letting lifecycle stages drift from .github/labels.json (visual ↔ tracker correspondence must stay lockstep); reducing the lifecycle to 'before / during / after' in the visual (the 7 distinct stages each represent an actual decision transition).",
    ],
  },
  {
    version: "0.5.18",
    date: "2026-05-15",
    title:
      "Add area:* label dimension for feature-aligned issue classification",
    highlights: [
      "v0.5.17 shipped a 3-dimension label taxonomy (status:*, component:*, scenario:*). v0.5.18 adds a 4th orthogonal dimension — area:* — for fine-grained, feature-aligned filtering. An issue now carries one of each: e.g., component:agent + area:chat + scenario:1 for a chat UI tweak.",
      "Why a separate dimension: component:* labels predict 'which build workflow fires' (build-pipeline-aligned, coarse). area:* labels predict 'which feature area is affected' (user-surface-aligned, fine). A change to mcp/agent/lib/auth.ts carries BOTH — component:agent (build target) + area:auth (feature surface). The two dimensions compose orthogonally without overloading either.",
      "19 new area:* labels (teal #14B8A6, distinct from component:* blue): area:chat, area:skills, area:memory, area:knowledge, area:jobs, area:instances, area:approvals, area:api-keys, area:observability, area:settings, area:models, area:providers, area:personality, area:backup-restore, area:rest-api, area:profile, area:factory-reset, area:password-reset, area:auth. All synced live to the repo via .github/scripts/sync-labels.sh.",
      "Items from operator's list already covered by existing component:* labels (NOT recreated): connectors, installer, help documents (help-pages), user journeys. These remain in component:* because they're build-pipeline boundaries, not feature areas WITHIN the agent.",
      "docs/CICD.md § Spec-driven workflow gains a new 'Area' subsection: the 19-label table, common label combinations (showing how all four dimensions compose), and the rationale for keeping component:* and area:* orthogonal.",
      "CLAUDE.md responsibility #3 expanded: at issue creation I apply ALL relevant labels across all four dimensions (one scenario:*, any component:*, any area:*). When unsure which area:* applies, default to the most user-visible surface affected.",
      "First release end-to-end under the v0.5.17 spec-driven discipline. Closes #19. The 7-stage lifecycle was exercised: chat description → agent opens issue with full spec → mechanical labels applied → operator verbal authorization → status:spec-approved → implement → push (Closes #19) → status:in-progress / status:dev-built / status:testing-complete / status:release-approved → tag → status:released + issue closes.",
      "Pre-existing area: ui label (with space after colon) survives from pre-v0.5.17 — left alone, coexists but isn't actively used. Migration deferred to future spec issue if anyone wants to clean up.",
      "Forbidden post-v0.5.18: conflating component:* and area:* dimensions (they answer different questions, both should be applied); creating area:agent or similar that duplicates component:* (the agent isn't a feature area); creating component:chat or similar that duplicates area:* (chat isn't a build target); adding new area:* labels without a spec issue (same discipline as any other change).",
    ],
  },
  {
    version: "0.5.17",
    date: "2026-05-14",
    title:
      "Spec-driven workflow Phase 1: every non-trivial change starts as a GitHub Issue",
    highlights: [
      "v0.5.16 visualized the existing pipeline. v0.5.17 adds one upstream step — an Issue that documents the spec BEFORE the work begins, with labels tracking lifecycle, classified by component + scenario, closed automatically at release time. The pipeline mechanics that follow (build, install, smoke, approval, tag, release) are unchanged.",
      "21 labels in 3 orthogonal dimensions, defined in .github/labels.json + applied via .github/scripts/sync-labels.sh: Status (7, exactly one at a time — spec → spec-approved → in-progress → dev-built → testing-complete → release-approved → released, with color gradient from gray to purple). Component (9, zero or more — mirrors per-service path-filter scopes). Scenario (5, exactly one — mirrors docs/CICD.md change scenarios, colors match the SVG diagram).",
      "Issue template at .github/ISSUE_TEMPLATE/release.md pre-applies status:spec. Body sections (Summary / Why / What ships / Smoke-test bullets / Forbidden / Cross-references) mirror the CHANGELOG entry structure 1:1 — issue body becomes the CHANGELOG entry at release time with minor wording edits.",
      "docs/CICD.md gets a new top-level 'Spec-driven workflow' section: full mechanics, lifecycle states, label taxonomy rationale per dimension, trivial-change escape hatch criteria, auto-promotion design decision, cross-reference patterns between issues + commits + release.yml, backfill policy (none — start fresh from v0.5.17), forbidden patterns.",
      "CLAUDE.md adds the spec-driven workflow as Agent-Behavior Contract #1 (alongside pre-deploy gate, smoke-test bullet contract, approval phrasing, post-tag closure deliverable, documentation discipline). 6 responsibilities codified: verify/open issue before non-trivial work, Refs #N / Closes #N in commits, mechanical-status labels at right transitions, smoke matrix to chat AND issue, trivial escape hatch, release-approved as metadata-only.",
      "Auto-promotion design: Option A (label is metadata only; chat approval still mandatory) for v0.5.17. Option C (label → confirmation PR → operator merges → tag) deferred to v0.6.0+. Option B (label auto-triggers tag) explicitly forbidden — misclick risk on customer releases is too high.",
      "Operator owns human-decision labels (spec-approved, testing-complete, release-approved). Agent owns mechanical-transition labels (in-progress, dev-built, released). Split prevents the agent from auto-promoting past gates the operator hasn't crossed.",
      "Trivial-change escape hatch: scenario:trivial label bypasses full spec body + smoke-test bullets + release-notes entry. Still respects contained-release discipline (one commit, one CHANGELOG one-liner) and pre-deploy gate (tsc + lint + npm run build). Honest use: typo fixes, comment cleanup, whitespace, README badges. Not trivial: any behavior change, however small.",
      "Forbidden post-v0.5.17: pushing non-trivial code to main without an open issue (skip-spec-and-fill-in-later reverts to pre-v0.5.17 workflow); mixing status labels (lifecycle is single-state); building auto-tagging off status:release-approved before v0.6.0+ (Option B is too risky); granting agents permission to apply operator-owned status labels (human decisions stay human).",
    ],
  },
  {
    version: "0.5.16",
    date: "2026-05-14",
    title:
      "Add visual CI/CD pipeline diagram to docs/CICD.md",
    highlights: [
      "v0.5.13-v0.5.15 documented the pipeline + scenarios + mechanics in 1684 lines of prose. v0.5.16 adds a single SVG diagram (docs/cicd-pipeline.svg) as a scannable visual overview that complements the text. The diagram is the scaffold; the doc has the detail.",
      "Six-section comprehensive diagram: (1) Dev cycle with OPERATOR + CI/CD swim lanes, animated flow arrows showing pipeline direction. (2) Release cycle from git tag through release.yml to customer (UI Update button OR re-download installer). (3) Three change scenarios as a decision tree — diamond at center, three color-coded outcome cards (green/blue/red for Scenarios 1/2/3). (4) GHCR per-version access matrix (PAT type × tag type → HTTP response). (5) Rollback & recovery — four side-by-side paths. (6) Path-filter contract + REBUILT/UNCHANGED diagnostic legend.",
      "Color semantics: blue = controlled (operator + dev cycle), indigo = integration/core (CI workflows), green = success (Scenario 1, customer pull working), amber = autonomous/cross-cutting (factory reset, dev-latest prerelease), red = danger (Scenario 3 breaking change). Designed to be scannable from 4 feet (color + shape) AND zoomable for word-level detail.",
      "docs/CICD.md gets a new 'Visual overview' section at the top — just after Contents — that embeds the SVG + provides a section-to-diagram map so readers can correlate visual region with the corresponding text section.",
      "Standalone SVG: no HTML wrapper, no external dependencies, no build-time generation. Renders in any modern browser or markdown viewer. 41 KB, 707 lines, hand-authored.",
      "Maintenance contract: when the pipeline changes substantively (new workflow file, scenario boundary moves, GHCR access model shifts), update cicd-pipeline.svg in the same release that updates the prose. Symmetric with the CLAUDE.md ↔ release-notes.ts ↔ help-pages discipline — visual + textual descriptions stay in lockstep.",
      "Forbidden post-v0.5.16: letting the SVG drift from the text (stale diagrams actively mislead); embedding the SVG in CLAUDE.md (visual belongs in docs/CICD.md alongside mechanics; CLAUDE.md cross-references); generating the SVG from Mermaid or a build script (hand-authored gives controllable semantic color + animation without adding a build dependency).",
    ],
  },
  {
    version: "0.5.15",
    date: "2026-05-14",
    title:
      "Close the remaining 7 documentation gaps (9-15) in docs/CICD.md — audit complete",
    highlights: [
      "v0.5.14 closed audit gaps 1-8; v0.5.15 finishes the job by adding the remaining 7 sections. Some are immediately actionable (build cache observability with concrete commands, runner capacity thresholds), some are future-work design sketches (image signing, beta channel), some are policy codification (deprecation lifecycle). +412 lines to docs/CICD.md (1272 → 1684).",
      "Deprecation policy (NEW top-level section): 3-stage lifecycle (announce → warn → remove) with minimum windows (≥30 days announce-to-warn, ≥90 days announce-to-remove). Where announcements live, Stage 2 warning mechanisms per surface type (UI banners, MCP docstrings, API headers, installer warnings), Stage 3 removal as MAJOR version bump per Scenario 3. Forbidden: removing without lifecycle, shortening windows under 'urgency,' announcing without naming replacement path.",
      "Tag immutability + accidental tag deletion recovery (NEW subsection in Rollback): tag-immutability rules, recovery procedure if a published tag gets accidentally deleted (recover commit SHA from GitHub Release / workflow run / git reflog → recreate → push → verify customer flow).",
      "Pre-release / beta channel (NEW top-level future-work section): design sketch for when we want trusted-beta-customer access — vX.Y.Z-beta.N tag pattern, prerelease + NOT-latest marking, phantom-updater channel-awareness. Status today: not implemented; defer until first beta-program demand.",
      "Build cache observability (NEW top-level section, immediately actionable): where Docker layer + buildx + npm caches live on the self-hosted runner, inspection commands (docker system df, docker buildx du, etc.), symptom-to-cause table for cache problems, cleanup recipes (safe daily prune, aggressive old-version-tag removal, build-cache-only prune), monitoring thresholds (>80% urgent, >90% investigate retention).",
      "Self-hosted runner capacity (NEW subsection in phantom-vm runner prerequisites): current state (one runner), when to add a second (queue depth >3 jobs for >5 min, recurrent operator-reported delays), topology options (same-VM vs separate-VM), failover plan if phantom-vm goes down.",
      "Image signing, SBOM, provenance (NEW top-level future-work section): design sketch for when enterprise demand triggers — cosign keyless signing via OIDC, syft for SBOM, slsa-github-generator for SLSA L3 provenance. Operational impact estimate (~30-60s added to release.yml). Forbidden: signing with repo-secret keypair, install-time SBOM generation, jumping to SLSA L3 without intermediate levels.",
      "CI/CD pipeline observability (NEW top-level section): status today (no automated alerting; manual via gh run list + workflow log + GITHUB_STEP_SUMMARY + dev-latest body), what's missing (failed-build alerting, dashboards, build-time regression tracking, quota tracking, dev-latest aging alerts, opt-in install telemetry), implementation paths with effort estimates, when-to-implement triggers.",
      "Audit complete: all 15 gaps from the v0.5.13 retrospective are now closed. docs/CICD.md is 1684 lines (was 770 at v0.5.13, +119%). 28 top-level sections cover every CI/CD area needed for operations + future-work documentation.",
      "Forbidden post-v0.5.15: removing any of the new sections to 'trim the doc' (each codifies a discipline or anticipates a real-world need); implementing future-work items without corresponding doc updates; letting CHANGELOG entries accumulate without cross-referencing codified policies (e.g., deprecation entries MUST link docs/CICD.md § Deprecation policy); routing customer CI/CD observability into our infrastructure without opt-out + privacy review.",
    ],
  },
  {
    version: "0.5.14",
    date: "2026-05-14",
    title:
      "Close the 8 highest-priority documentation gaps in docs/CICD.md",
    highlights: [
      "v0.5.13 extracted CI/CD mechanics to docs/CICD.md. v0.5.14 fills 8 gaps an audit revealed afterward — areas where the doc described what we have today but missed material an operator (or future me) would need when something nontrivial happens. +502 lines to docs/CICD.md; +13 lines of cross-references to CLAUDE.md.",
      "Customer onboarding flow (NEW top-level section in docs/CICD.md): prerequisites the customer brings (Linux VM, Docker, RAM/disk, outbound HTTPS), end-to-end download → install → first-login → password-change path, what customers DON'T need (no GitHub Actions access, no gh CLI), and operator-side delivery responsibilities. Closes the 'first-install was implicit' gap.",
      "PAT recipes (NEW subsection): concrete generation steps for customer PAT (read:packages only, classic OR fine-grained) and operator PAT (read:packages + repo, classic recommended), rotation procedure, and 'what wrong scope looks like'. Closes the 'PAT was a black box' gap.",
      "Rollback procedure (NEW top-level section): customer-side rollback for Scenarios 1+2 (re-run older installer, volumes preserved), Scenario 3 (manual backup-restore — expensive by design), operator-side yank procedure (gh release edit --draft), recovery from release.yml partial failure (re-dispatch or delete+retag). Closes the 'we shipped a bad release, what now?' gap.",
      "phantom-updater in the release loop (NEW top-level section): the architectural piece previously underspecified. Source location, MCP_TOKEN auth + PAT auth for GHCR pulls, 5 API endpoints, update detection mechanics (GitHub Releases API polling + manifest fetch + per-service digest comparison), V1 scope constraints (no rollback, no volume snapshots, no self-update), which 3 services updater manages, scenario-aware behavior.",
      "build-and-push-dev-image composite action (NEW subsection): inputs, outputs, the 4 steps, and why composite-vs-reusable-workflow. Shared by build-xlog/agent/caldera/connectors. Closes the 'name-dropped but opaque' gap.",
      "Monorepo release invariant (NEW subsection): all 11 images (5 stack + 6 connector) ship in lockstep at the same vX.Y.Z. Mixed-version manifests are not supported by phantom-installer or phantom-updater. Codified to prevent the next person from trying to violate it.",
      "PR cycle vs main-push cycle (NEW subsection): table comparing what fires on pull_request events (docker build + tests + lint, NO :dev push, NO dev-latest republish, NO installer staging) vs push to main (full pipeline). When to use each in single-operator practice.",
      "CI/CD failure modes + recovery playbook (NEW top-level section): 11 actual failure modes we've hit, plus a quick-reference table. Each entry: symptom → cause → remediation → prevention. Closes the 'each new failure took 30-90 minutes first time' gap — future encounters should resolve in <5 min.",
      "Forbidden post-v0.5.14: removing the failure-mode catalog (its value depends on accumulating real entries with resolutions); adding catalog entries without the symptom-cause-remediation-prevention shape; re-implementing customer onboarding steps in CLAUDE.md (source-of-truth is docs/CICD.md); treating rollback as customer-facing UX (today it's an operator runbook); granting customers repo scope 'for convenience'.",
    ],
  },
  {
    version: "0.5.13",
    date: "2026-05-14",
    title:
      "CI/CD pipeline extracted to docs/CICD.md, with the three change scenarios codified",
    highlights: [
      "Operator-driven discipline correction: CLAUDE.md previously mixed agent-behavior contracts (when I MUST ask, what I MUST share) with pipeline mechanics (workflow files, image tags, GHCR access). v0.5.13 separates them. docs/CICD.md (NEW, ~770 lines) is now the authoritative CI/CD reference; CLAUDE.md (trimmed from 1157 → 717 lines, −38%) keeps agent-behavior contracts only.",
      "Three change scenarios codified in docs/CICD.md (identical for dev prereleases and customer releases): Scenario 1 = code-only / installer unchanged / patch bump / volumes preserved / customer uses UI Update button. Scenario 2 = code + installer change / backwards-compatible / patch bump / volumes preserved / customer downloads new installer. Scenario 3 = backwards-incompatible storage schema / MAJOR version bump / customer types UPGRADE to confirm volume backup + wipe.",
      "Decision tree at docs/CICD.md § Decision tree walks 'what did the change touch?' → 'which scenario?'. Before planning any new release, classify the scenario and follow that scenario's discipline.",
      "Factory reset (cross-cutting) is documented as the manual operator path available across all three scenarios — wipes volumes, preserves .env, re-runs the installer, gated behind FACTORY RESET confirmation. Distinct from Scenario 3's automatic backup-and-wipe (which is required by the incompatibility of the new release).",
      "Scenario 3 implementation status: contract documented, code NOT implemented. The INCOMPATIBLE_FROM flag, backup-then-wipe logic, UPGRADE confirmation prompt — all documented as the target. When the first backwards-incompatible release is needed (likely v1.0.0 or v2.0.0), the implementation has a clear blueprint at docs/CICD.md § Scenario implementation status.",
      "Mental model the split enforces: CLAUDE.md is 'instructions to the AI agent about how to be a good collaborator'; docs/CICD.md is 'instructions to humans (including the AI) about how the pipeline actually works'. When pipeline mechanics change, update docs/CICD.md. When agent-behavior changes, update CLAUDE.md. Most changes update both.",
      "All 6 workflow file headers updated to reference docs/CICD.md instead of CLAUDE.md sections. Future maintainers see the actual reference file.",
      "Forbidden post-v0.5.13: moving agent-behavior contracts (smoke-test bullets, post-tag closure report, approval phrasing) out of CLAUDE.md — those are intentionally kept where the agent reads them; bundling new CI/CD mechanics into CLAUDE.md instead of docs/CICD.md (the split is the discipline, not a one-time refactor); implementing Scenario 3 without backup logic (the backup-to-disk path is non-negotiable); adding a Scenario 3 bypass flag (UPGRADE confirmation is the only path).",
    ],
  },
  {
    version: "0.5.12",
    date: "2026-05-14",
    title:
      "No unnecessary image rebuilds — narrow path-filter triggers + digest-pinned base images",
    highlights: [
      "v0.5.11's diagnostic exposed a real bug it didn't cause: per-service workflows' path filters listed `.github/workflows/build-<svc>.yml` AND `.github/actions/build-and-push-dev-image/**`. Editing a workflow's COMMENT HEADER (or the shared composite action) re-triggered the build. `docker build --pull` then fetched fresh upstream base layers, producing different image digests despite zero service source changes. Concrete impact: `phantom-xlog` and `phantom-caldera` recreated unnecessarily on the v0.5.11 cycle, costing caldera in-memory state.",
      "Option A (path-filter narrowing): every build-<svc>.yml `paths:` now contains ONLY that service's source paths. Self-references and composite-action references removed. Workflow header / composite action edits no longer trigger rebuilds. Trade-off: legitimate workflow-file edits (security fixes, etc.) piggyback on the next source change; use `gh workflow run build-<svc>.yml` to force-exercise before that.",
      "Option B (base-image digest pinning): every Dockerfile we control now references its FROM images by content digest (e.g., `FROM python:3.12-slim@sha256:401f6e1a…`). 8 FROM lines across 5 Dockerfiles: mcp/agent (3 stages: node 20-alpine + python 3.12-slim ×2), xlog (python 3.12), updater (python 3.12-slim), phantom-browser (chromedp/headless-shell), phantom-connector-runtime (python 3.12-slim). Source-unchanged rebuilds produce identical content → identical digest → no container recreate.",
      "Together: workflow runs are no-ops without source change (path filter skips) AND produce content-deterministic digests when source DOES change (digest-pinned bases). The diagnostic continues to surface any deviation.",
      "CLAUDE.md § Base-image digest pinning (NEW): why pinning matters with the concrete v0.5.11 xlog drift example, update cadence (deliberate, ~30-60 days or CVE-triggered, NOT automatic), procedure (the docker pull + docker inspect recipe), inventory of all pinned bases, and the caldera carve-out.",
      "Caldera carve-out: third_party/caldera is a MITRE upstream submodule we don't control, so its Dockerfile (`FROM node:23`, `FROM debian:bookworm-slim`) can't be digest-pinned without forking. Mitigation: path-filter narrowing limits caldera rebuilds to deliberate submodule pin updates, which is the only legitimate trigger. Forking is documented as a future option if drift becomes a real operator problem.",
      "Customer impact: none today. Customers run customer release tags built via release.yml's conditional rebuild + retag-from-prev path, which has always been digest-stable for unchanged services. v0.5.12 fixes the parallel dev cycle to have the same property. Customer releases gain the digest-pinned bases automatically when release.yml runs on a v*.*.* tag built from the v0.5.12 commit or later.",
      "Forbidden post-v0.5.12: re-adding self-path or composite-action triggers to build-<svc>.yml paths (the property they violate is the load-bearing one); reverting any Dockerfile's pinned FROM to a floating tag (reintroduces --pull drift); skipping the base-image refresh on cadence (pinned bases don't auto-patch CVEs — pair with a security-feed subscription for the bases we use).",
    ],
  },
  {
    version: "0.5.11",
    date: "2026-05-14",
    title:
      "CI/CD pipeline contracts made explicit + REBUILT/UNCHANGED diagnostic for every dev build",
    highlights: [
      "Operator-reported confusion during the v0.5.10 install: the compose output showed 'Pulled' for caldera and xlog, which read as 'those images were rebuilt this run' — but per-service workflow path filters had correctly skipped them (their last builds were two days old). System was already correct; the visibility was bad. v0.5.11 makes the rebuild decisions auditable at every dev build.",
      "New diagnostic step in build-dev-installer.yml: before deleting the prior dev-latest, download its release-manifest-dev.env asset and compare per-service digests against the new manifest. Classify each service as 🆕 FIRST-BUILD / ✓ UNCHANGED / 🔨 REBUILT / 📦 STABLE-ADVANCED (updater/browser only). Emit the table to three surfaces: workflow log, GITHUB_STEP_SUMMARY (renders on the run page), and the dev-latest release body.",
      "CLAUDE.md § Per-service path-filter contract (NEW): table mapping each build-<svc>.yml to its path-filter scope, the 'no source change = no rebuild = no container recreate' invariant stated explicitly, and a subsection explaining docker compose pull's 'Pulled' output is NOT a fresh build (manifest-verify for cached digests is ~1s; real fetches are minutes). The followup docker compose up is the forensic indicator (Running/Healthy = container kept; Started/Recreated = container replaced).",
      "CLAUDE.md § Smoke-test bullet contract (NEW): every successful build-dev-installer.yml run, I share a 5-15 bullet smoke-test matrix with the operator in chat (NOT in the prerelease body, NOT in release-notes.ts — durable docs describe SHIPPED state, not testing process). Scope is CUMULATIVE — covers every unreleased commit since the last vX.Y.Z, grows monotonically until release approval. Source of truth: the unreleased CHANGELOG entries.",
      "CLAUDE.md § Post-tag closure deliverable (NEW): after release.yml reports success, I produce a 5-section release closure report in chat — help docs landed, journeys landed, release notes landed, image digests published, operator review checklist. Source of truth: git diff vX.Y.Z-1..vX.Y.Z on help/journeys/release-notes files. Forbidden: skipping for 'small releases' (most likely to ship stale docs); populating from imagination (open /help/... and verify rendering first).",
      "Workflow file headers expanded: every build-<svc>.yml + release.yml gets a 'CI/CD step N of 3' navigation block + explicit DON'T list (no unconditional triggers, no workflow_dispatch shortcuts bypassing paths filters, no removal of the diagnostic step). build-caldera.yml gets the strongest warning because caldera's in-memory state is the highest-stakes consumer of the invariant.",
      "What v0.5.11 explicitly does NOT do: change the per-service path filters (already correct), move smoke bullets to a durable surface (operator preference keeps them in chat), reduce the workflow files to skeletal docs (header expansions are targeted, operational comments stay).",
      "Forbidden post-v0.5.11: removing the rebuild-decision diagnostic ('the table is the verification mechanism, not decoration'); adding workflow_dispatch shortcuts that rebuild multiple services at once ('cross-cutting rebuilds belong to release.yml's tag-driven path'); skipping the post-tag closure report because the release was 'small' ('small releases are the most likely to ship with stale docs'); making the closure report customer-facing ('it's an internal review aid; customers consume CHANGELOG + release-notes.ts, not this report').",
    ],
  },
  {
    version: "0.5.10",
    date: "2026-05-14",
    title:
      "Installer's token validation accepts OCI image indexes (not just legacy Docker v2)",
    highlights: [
      "v0.5.8's validate_ghcr_token() probe shipped with an Accept header listing only application/vnd.docker.distribution.manifest.v2+json. That works for customer release tags (built by plain docker build in release.yml, single-arch) but FAILS for :dev tags (built via build-<svc>.yml's composite action which produces OCI image indexes).",
      "GHCR refuses to serve a manifest in a format the client says it can't accept and returns 404 with the explicit error body 'OCI index found, but Accept header does not support OCI indexes'. v0.5.8 surfaced this 404 as 'token failed validation' even though the token was correct, the scope was correct, and docker compose pull at step 7 would have succeeded.",
      "First install attempt against v0.5.9's dev-latest prerelease hit this — operator saw 'Token from /opt/phantom/.env failed validation against ghcr.io' with a fresh, valid read:packages PAT. Direct GHCR probe with the same token from a workstation returned HTTP 200 for :dev. The Accept header was the only thing different.",
      "Fix: expand the probe's Accept header to all four standard manifest media types — OCI image index, OCI image manifest, Docker manifest list (multi-arch v2), Docker manifest v2 (single-arch). docker compose pull has always accepted all four; the validation probe is just catching up.",
      "Why the mismatch was invisible until now: pre-v0.5.8 there was no validation step (docker compose pull handled both formats natively, papering over the format assumption). Customer release tags happened to keep the legacy format (release.yml uses plain docker build), so a customer-flow installer never tripped the narrow Accept header. The dev cycle was the first time v0.5.8's probe ran against an OCI image index — that's exactly when it broke.",
      "Customer impact: none today. Customers running phantom-installer with customer release tags were never affected — their tags validate fine with the narrow Accept header. v0.5.10 becomes customer-visible only the day release.yml flips to buildx-style multi-arch builds; at that point, v0.5.10's wider Accept header silently survives the change.",
      "Forbidden post-v0.5.10: re-narrowing the Accept header to one media type 'because we control the build pipeline'. The control is brittle — a single CI tweak (switching to buildx, enabling --platform, adding a sidecar attestation, etc.) flips the format silently. Accept all four standard types; let the registry serve what it actually has.",
    ],
  },
  {
    version: "0.5.9",
    date: "2026-05-13",
    title:
      "Dev image versions pullable by operator PAT via a dev-latest GitHub prerelease",
    highlights: [
      "Pre-v0.5.9 the operator's dev install on phantom-vm failed at docker compose pull even when v0.5.8's registry-token probe succeeded: a PAT with read:packages (and even repo + read:packages) returned 404 for ghcr.io/kite-production/phantom-agent:dev while :vX.Y.Z worked. Root cause: GHCR enforces pull access per IMAGE VERSION, not per package or token scope alone.",
      "How GHCR per-version access actually works: a package version becomes org-readable when the workflow run that publishes it ALSO creates a GitHub Release. Customer vX.Y.Z versions get this via release.yml's gh release create. Dev :dev versions, published by per-service build-<svc>.yml workflows that don't create releases, stayed scoped to the publishing workflow's GITHUB_TOKEN — invisible to any third-party PAT regardless of scope.",
      "The fix: build-dev-installer.yml publishes a GitHub Release marked --prerelease with tag dev-latest after each successful dev build. The :dev image versions inherit pull permission from this prerelease, so the operator's PAT (the same kind customers use, with read:packages) can now pull :dev from phantom-vm.",
      "release.yml deletes dev-latest when a real customer vX.Y.Z release publishes — so the dev prerelease never lingers alongside a customer release on the Releases page. Gated on success() so workflow_dispatch reruns still clean up; idempotent (gh release view probe before delete) so a missing prerelease doesn't fail the release run.",
      "dev-latest is a stable tag (not dev-<sha>): operators only ever consume the most recent dev build, and the release body embeds the SHA + image digests so forensics stay intact. Per-SHA prereleases would pile up on the Releases page without observable benefit; release.yml's cleanup step has a fixed target (one gh release delete call).",
      "Operator-facing commands unchanged: git push origin main → wait for build-dev-installer.yml → sudo /home/ayman/phantom-installer-dev on phantom-vm. The fix is entirely in the access layer — what was a confusing 404 at pull time becomes a clean install.",
      "CLAUDE.md adds a new 'GHCR per-version access' subsection codifying the access semantics + why the prerelease is non-negotiable. Tables out which PAT type (customer-style read:packages vs operator repo + read:packages) can pull which version (customer release vs dev prerelease).",
      "Forbidden post-v0.5.9: removing the prerelease step from build-dev-installer.yml (load-bearing — the access mechanism, not cosmetic). Marking the package public to 'fix' this (inverts the intentional security boundary — customers see their releases, operators see dev builds + releases). Manually deleting dev-latest between releases (breaks phantom-installer-dev on phantom-vm until the next build-dev-installer run republishes it). Marking dev-latest as latest and forgetting to revert (makes the dev binary surface in customer gh release download results).",
    ],
  },
  {
    version: "0.5.8",
    date: "2026-05-13",
    title:
      "Installer validates the registry token before use; re-prompts if stale",
    highlights: [
      "Operator-reported: after running sudo /home/ayman/phantom-installer-dev on phantom-vm post-v0.5.7, step 7's docker compose pull failed with 'denied: denied' from GHCR. Cause: the token in /opt/phantom/.env was the ephemeral ghs_ token from a prior auto-deploy run (~hours-old; GitHub App installation tokens TTL is ~1 hour). Installer blindly reused the stale token through steps 4-6, failed at step 7 with a confusing error.",
      "Pre-v0.5.7 auto-deploy masked this lifecycle problem (CI always injected a fresh secrets.GITHUB_TOKEN per run). v0.5.7's 'CI builds, operator installs' correctly surfaced the bug. v0.5.8 fixes it.",
      "Installer step 4 now validates the captured token against GHCR before continuing: exchange the PAT at ghcr.io/token for a per-image pull bearer, then HEAD-probe ghcr.io/v2/kite-production/phantom-agent/manifests/dev. HTTP 200 = good; 403 = scope missing; 401 = bad token. Probe adds ~1-2 seconds; pre-v0.5.8 'trust + fail at step 7' wasted minutes per failed run.",
      "On validation failure, the installer RE-PROMPTS the operator for a fresh PAT (cap: 3 attempts). Three failure modes caught early instead of at step 7: expired token (ephemeral ghs_ lifetimes), wrong scope (a repo-only PAT can't pull packages — needs read:packages), revoked token (operator rotated PAT externally).",
      "If no TTY is available (non-interactive run, e.g. scripted automation), the installer dies with a clear message: 'provide PHANTOM_REGISTRY_TOKEN=… or update .env's PHANTOM_REGISTRY_TOKEN line'. No silent failure.",
      "Forbidden post-v0.5.8: skipping the validation step via a --no-validate flag (the GHCR probe is cheap and protects every install). Auto-rotating the token in .env when the operator pastes a fresh PAT at the prompt (the operator chooses their token-strategy — fine-grained PAT vs classic PAT vs external secret manager — and writes it to .env when they're ready). Caching the validated bearer across runs (sub-second overhead means caching is unnecessary).",
    ],
  },
  {
    version: "0.5.7",
    date: "2026-05-13",
    title:
      "Dev workflow no longer auto-deploys: CI builds, operator installs",
    highlights: [
      "Operator-driven design correction: the dev workflow (formerly deploy-dev-installer.yml) used to run sudo ./phantom-installer-dev on phantom-vm after every successful image build, automatically installing the new dev bytes. v0.5.7 retires that behavior. The workflow is renamed build-dev-installer.yml and only BUILDS + stages the dev installer binary; the operator drives every install on phantom-vm.",
      "Why retire auto-deploy: doesn't match the customer flow (customers download phantom-installer, run it manually), takes upgrade timing away from the operator, and short-circuits explicit upgrade-from-prior-version testing. The new contract: CI builds + stages the binary at /home/ayman/phantom-installer-dev on phantom-vm + uploads as workflow artifact. Operator runs sudo /home/ayman/phantom-installer-dev when ready to test.",
      "Workflow rename: deploy-dev-installer.yml → build-dev-installer.yml. Job 'Deploy on phantom-vm' replaced with 'Stage dev installer at /home/ayman/phantom-installer-dev'. Atomic stage via cp + mv so the operator can't observe a partial binary even if the workflow is in flight when they run the installer.",
      "CLAUDE.md updates: 'What this means operationally' describes the build-then-operator-install flow; 'Build & release workflow (MANDATORY)' codifies four rules — CI builds, CI never installs, IAP tunnel is smoke-test-only, releases need explicit chat approval. Workflow file layout table reflects per-service builds + build-dev-installer.yml. Approval-gates table makes the operator's install an explicit step. docker-compose.yml header comment corrected (the repo-root compose is dev-workstation only, NOT CI).",
      "Operator's new dev cycle: git push origin main → per-service builds rebuild changed images → build-dev-installer.yml stages fresh binary at /home/ayman/phantom-installer-dev → operator SSH's to phantom-vm + runs sudo /home/ayman/phantom-installer-dev → smoke-test via browser → ASK FOR APPROVAL → git tag vX.Y.Z → release.yml fires.",
      "Customer impact: none. Customers were never affected by the dev auto-deploy path. Customer flow has always been 'download phantom-installer, run it' and remains unchanged.",
      "Forbidden post-v0.5.7: re-introducing an auto-deploy step in build-dev-installer.yml or any successor workflow (CI builds, operator installs — full stop). Adding a 'auto-install on workflow_dispatch' bypass (the operator dispatches the build manually if they want a fresh installer; they still run the install themselves). Pushing fixes-that-bypass-installer onto phantom-vm via tar+scp or sshpass git pull (the dev-installer IS the install path; if it can't install something, fix the installer, not work around it).",
    ],
  },
  {
    version: "0.5.6",
    date: "2026-05-13",
    title:
      "Factory-reset depends on the installer being part of the install — refuses cleanly when it isn't",
    highlights: [
      "Operator-reported: sudo /opt/phantom/phantom-factory-reset --dry-run printed a warning and prompted for typed 'YES' to proceed without auto-recovery. Two root causes: (1) the installer binary was never persisted into $INSTALL_DIR/ after install — it lived wherever the operator ran it from (~/, /tmp/, runner workspace). After install, /opt/phantom/ had docker-compose.yml + .env + the two recovery scripts but not the installer that produced them. (2) Factory-reset offered a 'proceed without auto-recovery' workaround. That's the wrong shape: the installer is part of the shipped package; its absence is an install-integrity violation, not a bypass scenario.",
      "Installer self-installs to $INSTALL_DIR/ at the end of every successful install. After the stack-healthy check (step 7 epilogue), the installer copies its own binary to $INSTALL_DIR/$(basename $0). The basename preserves the flavor: phantom-installer-dev lands at /opt/phantom/phantom-installer-dev; phantom-installer lands at /opt/phantom/phantom-installer. Idempotent on re-run; fails-soft if the copy can't happen (the rest of the install already succeeded).",
      "Factory-reset HARD-FAILS when the installer binary is missing. No more warn + prompt + bypass. The error message names the missing path, explains that the installer ships with the package and self-installs on first run, and gives an explicit recovery path: download a fresh installer from the GitHub Release, run it (which self-installs), then re-run factory-reset. Applies to both --dry-run and real-run modes — missing installer is the same problem in either path. No --force / --skip-recovery flag to reintroduce the v0.3.x 'silent fallback' pattern v0.4.0 codified the absence of.",
      "Customer impact on upgrade: customers on v0.5.5 → v0.5.6 self-install the binary on the next installer run. From that point forward, phantom-factory-reset runs cleanly. Operators who attempt phantom-factory-reset BEFORE upgrading to v0.5.6 hit the new hard error pointing them at the upgrade path — which is correct.",
      "Forbidden post-v0.5.6: adding a --force flag to phantom-factory-reset that bypasses the installer-presence check. The install package is the contract — the installer is a peer of the recovery scripts, not optional. Persisting the installer ANYWHERE other than $INSTALL_DIR/ (the binary lives where the rest of the install lives, period). Making factory-reset 'fall back' to manual recovery instructions — if the install is incomplete, factory-reset stops and tells the operator to fix the install first.",
    ],
  },
  {
    version: "0.5.5",
    date: "2026-05-13",
    title:
      "Last in-image credential removed — DEFAULT_ADMIN_PASSWORD migrated from auth-defaults.ts to .env",
    security: true,
    highlights: [
      "Operator-stated requirement: no credentials in any Phantom image, full stop. Pre-v0.5.5 audit found exactly one violation — the literal 'phantom-admin-CHANGE-ME' in mcp/agent/lib/auth-defaults.ts:65, baked into the phantom-agent image and passed to the entrypoint's seed routine. v0.5.5 closes the gap.",
      "Installer auto-generates a random per-install bootstrap password (openssl rand -base64 24, 24 chars) into PHANTOM_DEFAULT_ADMIN_PASSWORD in /opt/phantom/.env. The agent's entrypoint sources it from env at seed time. The seed path fails-loud if the env var is empty on a fresh install — refuses to seed an empty hash; operator must re-run the installer (which auto-generates) or use sudo /opt/phantom/phantom-reset-admin-password to set credentials interactively.",
      "The DEFAULT_ADMIN_PASSWORD constant is gone from auth-defaults.ts. ADMIN_USERNAME, SESSION_COOKIE_NAME, SESSION_TTL_SECONDS stay — usernames aren't credentials, cookie names aren't secrets, TTLs are constants. Audit shape post-v0.5.5: docker exec phantom_agent grep -r phantom-admin-CHANGE-ME /app → no matches.",
      "Backward-compatible upgrade. Existing v0.4.0–v0.5.4 customers upgrading to v0.5.5: SecretStore already holds the operator's password hash; seed returns 'already_initialized'; env var ignored. On the next installer run PHANTOM_DEFAULT_ADMIN_PASSWORD gets back-filled into .env (harmless — only consulted if SecretStore is ever wiped). Fresh installs of v0.5.5 boot with a per-install random password printed in three places: installer epilogue banner, agent's first-boot docker logs banner, and /opt/phantom/.env.",
      "Lost the random value before completing the forced first-login change? Run sudo /opt/phantom/phantom-reset-admin-password from the host (v0.5.3+ utility). The factory-reset path also restores access: phantom-factory-reset wipes SecretStore but preserves .env, so the post-reset seed uses whatever value is in .env (back-filled by the installer, never wiped).",
      "Operator-facing UI updated: /profile banner text, auth-flows diagram, help/user First-Time-Login subsection (rewritten for v0.5.5), help/architecture #authentication subsection, auth-first-time-login journey (new test step: verify no image ships a baked admin password), ops-factory-reset-host-utility journey (post-reset login uses env-sourced value).",
      "Forbidden post-v0.5.5: reintroducing any hardcoded credential into any Phantom image (auth-defaults.ts, entrypoint.sh, or any source file we control). Adding a 'silent fallback' to the literal phantom-admin-CHANGE-ME if PHANTOM_DEFAULT_ADMIN_PASSWORD is empty (the fail-loud is the contract — silent fallbacks landed us in v0.3.x regressions). Storing PHANTOM_DEFAULT_ADMIN_PASSWORD anywhere other than .env (it's not in SecretStore because the SecretStore consumes it during init; it's not in the image because that's the whole point of v0.5.5).",
    ],
  },
  {
    version: "0.5.4",
    date: "2026-05-13",
    title:
      "Installer hotfix — .env rewrite now idempotent across the comment header, not just the value lines",
    highlights: [
      "Operator-reported. cat /opt/phantom/.env on a phantom-vm with ~25 dev-installer runs showed ~25 stale '# ─── Digest manifest (managed by phantom-installer vdev-XXXXX) ──' header blocks accumulated at the bottom of the file. Only the last block had its values; the rest were orphan headers. Pre-v0.5.4 the strip step targeted only ^PHANTOM_VERSION= and ^DIGEST_PHANTOM_ lines; the 3–4 line comment header above them was untouched, so every re-run added a fresh header without removing the old ones.",
      "Fix shape: extended the sed strip patterns in both installer paths (installer/phantom-installer.template.sh and installer/install.sh) to also delete the comment header lines. Matches the canonical 4-line block emitted by phantom-installer AND the 3-line variant install.sh emits, so a .env that's been touched by both flavors gets cleaned the same way. Added an awk pass after the strip to collapse consecutive blank lines, so the cleanup of N orphan headers doesn't leave N blank gaps in the file.",
      "Effect on existing installs: on the next installer run after v0.5.4 deploys, the strip removes ALL accumulated stale headers and the awk pass collapses the resulting empty lines. After one re-run, .env returns to the clean shape the original first install had. No customer action required beyond the standard re-install. Customers using the in-app updater pick the fix up automatically.",
      "Read-only-safe for any operator-added comments outside the canonical Digest-manifest block. The strip patterns are pinned to the exact header text the installers themselves emit, so a customer who added their own '# ─── My company-specific notes ──' block above the manifest survives the rewrite untouched.",
      "Forbidden post-v0.5.4: shipping a new installer that strips manifest VALUES without ALSO stripping the matching comment header block in the same step. The two are emitted as a unit, they must be stripped as a unit. Treat the comment+value block as the smallest unit of .env manifest-managed state.",
    ],
  },
  {
    version: "0.5.3",
    date: "2026-05-13",
    title:
      "Host-side recovery utilities — phantom-factory-reset + phantom-reset-admin-password",
    highlights: [
      "Operator-driven. v0.5.2 fresh-state hygiene exposed a related pain point: the only way to test a fresh install was to manually type the wipe-and-reinstall recipe from CLAUDE.md, and the only way to reset a forgotten password was to memorize a docker-exec one-liner. Both work, neither is friendly. v0.5.3 ships these as two named host-side scripts that mirror each other's invocation shape: sudo /opt/phantom/phantom-<utility>.",
      "phantom-factory-reset. Host-side script that returns Phantom to its fresh-shipped state. Lists every phantom_* docker volume (with approximate size), asks the operator to type 'FACTORY RESET' as a typed-confirmation guardrail, stops the stack, wipes the volumes, and re-runs the installer so the recovery brings containers back up. Preserves /opt/phantom/.env so PHANTOM_SECRET_KEK + registry credentials survive across the reset — re-installs are fast (no image pulls). Flags: --yes (skip prompt, for scripted use), --dry-run (show plan without wiping), --help. Host-side by physical necessity: a container can't delete the docker volume it's mounting (the daemon refuses with 'volume in use'), so factory reset MUST operate from outside the container boundary.",
      "phantom-reset-admin-password. Host-side wrapper around the in-container CLI at /app/cli/reset-admin.mjs. v0.4.0 deliberately put the credential-write logic inside the agent image (SecretStore + audit machinery, same code path as /profile's change-password flow); v0.5.3 adds the host wrapper for operator-UX consistency with phantom-factory-reset. The wrapper validates the agent container is running, then exec-replaces itself with the docker-exec invocation. Credential-write logic stays inside the container — single source of truth, no parallel host-side implementation (the v0.4.0 retrospective rule).",
      "Both scripts ship in BOTH installer distribution paths. The single-file phantom-installer binary embeds them via heredoc (same pattern as docker-compose.yml — see installer/build-phantom-installer.sh's __INSTALLER_FACTORY_RESET_SH__ + __INSTALLER_RESET_PASSWORD_SH__ markers). The multi-file install kit copies them verbatim via release.yml's 'Pack customer install kit' step. After install, they live at /opt/phantom/phantom-factory-reset and /opt/phantom/phantom-reset-admin-password — chmod 755, ready to invoke under sudo.",
      "Retired: scripts/reset_admin.sh. Was a dev-side convenience that lived only in the repo (never shipped to customers). v0.5.3 consolidates on the installer/ canonical paths so the same script the customer runs is also the one the operator uses during dev. Architecture page references updated; the v0.4.0 'ops-cli-reset-admin-password' journey rewritten for the v0.5.3 path (the docker-exec form is still documented as the underlying implementation, since the wrapper is intentionally thin).",
      "New 'ops-factory-reset-host-utility' journey under category=ops. Walks an operator through the typed-confirmation guardrail, the --dry-run flag, the per-volume wipe progress, the installer re-run at the end, and the verification matrix (memory 0/0, api-keys empty, /notifications 0/0, journey-tested marks gone, .env preserved). Pairs with the existing ops-cli-reset-admin-password journey so both recovery paths have first-class documentation in /help/journeys.",
      "Build pipeline. installer/build-phantom-installer.sh gained FACTORY_RESET_SH + RESET_ADMIN_SH env vars (with defaults pointing at the installer/ paths). release.yml's 'Build phantom-installer' step inherits the defaults from the working directory. deploy-dev-installer.yml's 'Build phantom-installer-dev' step inherits the same way. No workflow changes needed beyond the install-kit packing step.",
      "Forbidden post-v0.5.3: reintroducing the pre-v0.4.0 parallel host-side password reset implementation (the one that auto-detected username from setup.json and wrote PBKDF2 hashes via python+sqlite from the host); the v0.5.3 wrapper delegates to the in-container CLI which delegates to the same /api/v1/ui/auth/admin_reset endpoint the UI uses — single source of truth, single audit trail. Adding a --reset-volumes flag to the installer (v0.4.0's separation-of-responsibilities rule still applies: installer = image deployment, factory-reset = state management). Implementing factory-reset INSIDE the container (architecturally impossible as documented above).",
    ],
  },
  {
    version: "0.5.2",
    date: "2026-05-13",
    title:
      "Fresh-state hygiene — strip mock data, drop nonexistent workspace dimension, wire api-keys page to real backend",
    highlights: [
      "Operator-driven fix. Fresh installs in v0.5.1 still showed three categories of fake state: the example-vendor plugin auto-seeded 3 memory entries + 3 agent definitions + 1 skill at every boot; the notifications page rendered a hardcoded 12-row mock array with 'Stock Trading' / 'Job Research' workspace labels; the api-keys page was 100% mock with 4 fake keys, an invented 3-tier permissions taxonomy, and a workspace-scope dimension that doesn't exist on the backend. v0.5.2 strips all three so a fresh install reads as genuinely empty across every operator-named surface.",
      "Plugin defaults flipped to opt-in. bundles/spark/plugins/example-vendor/manifest.yaml now ships enabled: false. The plugin remains discoverable as a live reference for the contribution shape (1 skill + 3 memory_seeds + 3 agent definitions — the cleanest end-to-end example we have), but its contributions no longer fire automatically. Operators wanting the demo content flip enabled: true + restart. Pre-v0.5.2 the plugin was on by default, which conflicted with v0.5.0's minimal-default-state requirement.",
      "Notifications page is no longer a demo. Deleted the 158-line NOTIFICATIONS hardcoded fallback array; the page now renders the live /api/agent/notifications result and nothing else. Tab counts (All / Unread / Approvals / Alerts / System) are derived from the live source filtered against matchesTab, not hardcoded — fresh installs correctly read 0 across every tab instead of the legacy '8 unread'. Footer shifted from 'Showing 0 of 23' to 'Showing 0 of 0' (derived from source.length). Removed the workspace filter button + state + the per-notification workspace chip — Phantom is single-tenant, the dropdown's 'All Workspaces' label was misleading.",
      "API keys page wired to real backend. 803-line pure-mock page rewritten against /api/v1/api_keys (which already existed and was fully functional — the frontend mock just never used it). Removed the invented 3-tier permissions taxonomy (Full / Read+Execute / Read-only); replaced with the real advisory scopes the backend persists (audit:read, settings:read/write, approvals:resolve, tools:call, * for admin equivalent). Removed the workspace scope dimension (backend doesn't have one). Removed the expiration dropdown (backend keys are valid until revoked, not time-boxed). Removed the Recent Usage detail panel (backend stores last_used_at as a single timestamp, not a request history). Wired create → POST returns plaintext once; revoke → DELETE.",
      "Skills page workspace cleanup. Removed two sections from the skill-detail panel that had no backend wiring: 'Workspace Assignment' (toggle workspaces on/off per skill) and 'Workspace Overrides' (per-workspace override config). Both ported over from Spark's multi-tenant skill UI; Phantom is single-tenant so they rendered a permanent decorative placeholder ('All workspaces using platform defaults') for every skill forever. Removed the WsToggle component, the workspaces and overrides fields from the SkillDef interface, and the corresponding stub entries from all 20+ hardcoded fallback skill cards.",
      "Sidebar deduplication. /notifications was listed twice — once nested inside the Integration nav group, once as a standalone footer link (the cross-cutting bell icon pattern). The Integration-group entry is gone; the footer entry stays. Added a code comment explaining the rule so the next nav change doesn't reintroduce the duplicate: cross-cutting utilities (notifications, theme, profile) live in the footer; domain pages live in groups.",
      "Customer impact. Operators on v0.5.1 upgrading to v0.5.2: their existing operator state (memory entries, instances, api keys minted via REST, jobs, marks, bookmarks) survives unchanged — none of it was sourced from the example-vendor plugin or the notifications/api-keys mocks. Fresh installs on v0.5.2 boot into a genuinely empty state across every operator-named surface (memory 0/0, notifications 0/0, api keys empty-state, no skills outside the bundle-default set, no agent_definitions outside what the bundle includes). This is the 'first install = blank canvas' state the v0.5.0 operator brief described.",
      "Forbidden post-v0.5.2: re-enabling example-vendor in the shipped manifest (stays opt-in; flip the flag if you want the demo); hardcoded UI counts ('of 23', '8 unread') in operator-facing pages — counts must derive from the live data source so fresh installs read '0 of 0'; mock-data fallbacks in pages that have real backend endpoints (the api-keys 803-line mock pattern is exactly what to avoid — when the backend exists, the page wires to it directly with an empty state for the no-data case, no 'demo fallback'); workspace-scoped UI affordances anywhere except the dead-but-unreachable connectors-page code (which doesn't surface to operators today and is a known follow-up cleanup).",
    ],
  },
  {
    version: "0.5.1",
    date: "2026-05-13",
    title:
      "Operator workflow state — third canonical-state category, migrate journey-tested + metrics-bookmarks from browser localStorage to MCP",
    highlights: [
      "Operator-driven fix. Two pre-v0.5.1 UI surfaces (journey-tested marks at localStorage key phantom.help.tested-journeys; metrics bookmarks at spark.observability.metrics.bookmarks.v1) persisted operator workflow state in the browser only. That violated v0.4.0's canonical-state discipline rule 1 and produced four operator-visible failure modes: volume wipes didn't clear the state, cross-device + cross-browser inconsistency, missing from /api/agent/backup. v0.5.1 collapses to ONE canonical home in MCP — same pattern v0.4.0 used for auth + v0.5.0 used for marketplace.",
      "New canonical home: operator_state.db (SQLite key-value at /app/data/operator_state.db). Untyped at the SQL layer; per-key shape owned by the hook. Adding a new operator workflow concern is zero schema migration — just pick a new key. Multi-user ready: when v0.4.0's roadmap multi-user lands, add a user_id column + scope to (user_id, key) primary key. Same migration shape sessions used.",
      "New API surface: GET/PUT/DELETE /api/v1/operator-state/{key} + Next.js proxy at /api/agent/operator-state/[key]. Audit-emitting (operator_state_set / operator_state_delete) so the operator's 'what marks did I set when' history is captured alongside everything else.",
      "Both affected hooks rewritten as server-backed with optimistic UI + fire-and-forget PUT. External contract unchanged (toggle, setTested, reset, count, hydrated for the journeys hook; addCurrent + remove for bookmarks). The journeys page + the metrics bookmarks panel are caller-unchanged. Internal: load from server on mount, persist via PUT on every mutation.",
      "One-shot localStorage → server migration on first mount. Operators upgrading from v0.5.0 don't lose their marks: the hook detects server-empty + localStorage-non-empty, persists the legacy data to the server, deletes the localStorage key, then never reads it again. Idempotent. Subsequent loads hit the server-returns-list happy path.",
      "Dead-code purge. Deleted mcp/agent/components/chat/chat-session-context.tsx (the v0.2.x-flagged dead ChatSessionProvider that was STILL polluting browser localStorage with a phantom.chat.sessions.v1 key on every page load even though zero React components consumed the context). The mount was removed from app/layout.tsx. The actual chat session state has lived in /api/v1/sessions (server-side) the whole time; the localStorage shadow was just confusing operators who saw it in DevTools.",
      "Three-category state model codified. CLAUDE.md amended with the 'Operator workflow state — the third category (v0.5.1)' subsection under the existing 'Agent credential guardrail (MANDATORY)'. Captures the four-question taxonomy for any future UI surface that needs to persist state: (1) Secret? → SecretStore + REST-only. (2) Platform metadata? → marketplace.db / instances.db. (3) Operator-personal progress that should follow them across devices? → operator_state.db. (4) Device-local UI pref? → localStorage (this one stays legitimate). If you find yourself writing localStorage for #3, that's a regression.",
      "New /help/architecture#operator-state section + 3 v0.5.1 acceptance test journeys (filter chip 'v0.5.1 test'). Operator can verify: tested-journey marks survive page refresh + sync cross-window (same admin user), volume wipe correctly clears them, one-shot migration runs once + invisibly on upgrade from v0.5.0, localStorage is no longer being written to post-migration.",
      "Forbidden post-v0.5.1: writing operator workflow state to localStorage (the runtime contract is server-side; the legacy keys never read again after first-mount migration). Re-introducing the ChatSessionProvider dead-code pattern (was unused, now deleted; bring it back only if a real consumer materializes). Adding agent tools to read operator state without a justified use case (default-closed; the operator's worklist isn't the agent's concern).",
      "Customer impact: existing operators with localStorage marks see no UX change — migration runs invisibly on next page visit. Volume wipes now correctly clear journey-tested + metrics-bookmarks along with everything else, restoring the v0.4.0 wipe-contract the operator's mental model expects.",
    ],
  },
  {
    version: "0.5.0",
    date: "2026-05-12",
    title:
      "Connector consistency — marketplace canonical home, universal container-mode, schema validation, user-uploaded connectors, 4 new agent tools",
    breaking: true,
    highlights: [
      "BREAKING release. Pre-v0.5.0 the connector domain had the same shape v0.4.0 cleaned up in auth: install state split between marketplace_installs.json (Next.js) and instance presence (MCP); functionality half-wired (install button existed but didn't gate anything); invisible auto-migration (_auto_migrate materialized primary-* instances at every boot from env vars); 3 runtime styles (module/class/container) with only 1 of 6 connectors using container. v0.5.0 applies the canonical-state discipline rules CLAUDE.md codified after v0.4.0.",
      "Marketplace canonical home in MCP. Install state moves from /app/data/marketplace_installs.json (Next.js-written) into /app/data/marketplace.db (SQLite, MCP-owned). Routes: GET /api/v1/marketplace (catalogue + install state), POST /api/v1/marketplace/<id>/install, POST .../uninstall (409 if instances), DELETE /api/v1/marketplace/<id> (403 for bundle, deletes user). The Next.js routes become thin proxies. One-shot migration on first boot reads the legacy JSON, imports each row with origin='bundle', then deletes the JSON file. Idempotent on subsequent boots.",
      "Single connector schema. bundles/spark/connectors/connector.schema.json (Draft 2020-12) covers id, version, source.{language,entrypoint}, runtimeMapping (container-only enum), configSchema, secretSlots[].{name,description,required}, spec.tools[]. usecase/connector_schema.py loads + validates at boot. Drift fails fast with a path-into-the-field error. Bundle connectors + user-uploaded connectors validate against the same file. Closes the schema-by-example drift trap (v0.1.x slot-name camelCase/snake_case, v0.1.27 missing version field, v0.3.x silent style typo).",
      "Universal container-mode. All 6 connectors (caldera, cortex-content, cortex-docs, web, xlog, xsiam) now run as per-instance phantom-connector-<id>-<name> containers — each their own image, each their own crash + resource + dep isolation. The 5 module-style YAMLs flipped; the missing cortex-content Dockerfile added; module + class branches deleted from connector_loader.py (~70 LoC). New build-connectors.yml workflow produces :dev tags for dev iteration; release.yml extended to publish the 6th connector image alongside the existing 5.",
      "Install gate is functional. Instance creation now requires the connector be marketplace-installed first — 409 connector_not_installed if not. _AUTO_MIGRATION is deleted entirely (Rule 2 of canonical-state discipline: delete legacy paths in the same release). Fresh installs come up with zero instances, all 6 connectors visible in the marketplace as 'available, not installed'. Per the operator brief, this is the new default state.",
      "User-uploaded connectors + system/user distinction. POST /api/v1/marketplace/upload accepts a multipart connector.yaml, validates against schema, rejects bundle-id collisions + existing-user-id collisions, requires an 'image' field (the OCI reference to the user's pre-published connector container), writes to /app/data/user_connectors/<id>/. DELETE /api/v1/marketplace/<id> deletes user connectors (with instance-count 409 protection); bundle connectors are 403-rejected (image-baked, undeletable). phantom-updater extended to pass image_ref through to docker.run so user connectors don't need to be in KNOWN_CONNECTORS.",
      "4 new agent tools — catalog operations only, NOT credential operations. marketplace_list (read-only catalogue + install state), marketplace_install (idempotent flip), marketplace_uninstall (409 if instances), connector_upload (validates + writes user YAML). These sit on the CATALOG side of the credential boundary the v0.4.0 guardrail codifies. The agent helps the operator manage the marketplace; instance creation (which carries secrets) stays operator-only. CLAUDE.md amended with a new 'Catalog boundary ≠ credential boundary' section explaining the distinction and the 2-question test for future MCP tools.",
      "Customer impact on upgrade: existing v0.4.x customer installs carry their state in the phantom_data volume. v0.5.0's upgrade migration runs once at boot, iterates instances.db, and auto-installs every connector with existing instances (origin='bundle'). Customer experience: no change — the 3 connectors they were using (typically caldera/xsiam/xlog) stay installed, their instances stay live, their tools stay registered. The marketplace page now shows them as 'installed' with the auto-installed timestamp. Volume-wipe case boots cleanly into the 'zero instances, 6 available connectors' default state.",
      "Forbidden post-v0.5.0: the pre-v0.5.0 marketplace_installs.json file (do not write to it — the MCP route is the canonical surface); runtimeMapping.style: 'module' or 'class' (deleted from the schema enum, validator rejects); _AUTO_MIGRATION-style env-var-to-instance auto-creation (the explicit install + instance create flow is the contract); hardcoding new connectors into phantom-updater's KNOWN_CONNECTORS set (use the image_ref body field for user uploads).",
    ],
  },
  {
    version: "0.4.0",
    date: "2026-05-12",
    title:
      "Auth redesign — SecretStore-only model, default-credentials boot, spark login UI, per-service CI builds",
    breaking: true,
    highlights: [
      "BREAKING release. Pre-v0.4.0 the admin password lived in five overlapping places (SecretStore + UI_USER/UI_PASSWORD env + setup.json + .env.generated + the flat phantom_auth=1 cookie). Every fix shipped against that surface broke something else — v0.3.20 KEK mismatch, v0.3.22 .env.generated cleanup, v0.3.27 empty SA JSON. The migration code between the stores was the entire source of the pain. v0.4.0 collapses to ONE storage home (SecretStore for credentials, auth_sessions.db for sessions) and deletes every fallback path. Setup page is gone. Default credentials are seeded on first boot (admin / phantom-admin-CHANGE-ME, also printed to docker logs on the seed boot). The forced password change happens at /profile. The forgot-password CLI is on the host.",
      "Auth contract: SecretStore /ui/auth/admin/{password_hash, credentials_changed} for credentials (PBKDF2-HMAC-SHA256 / 600k iter / AES-GCM at rest); auth_sessions.db for server-side session tokens; phantom_session cookie (HttpOnly + Secure + SameSite=Strict + Max-Age=7200, 2-hour absolute expiry, no remember-me). Per-source-IP rate limit (5 failures/60s → 60s lockout, in-memory). All auth events audited: login_success/login_failed, password_changed_ui, password_changed_cli.",
      "Agent credential guardrail (security hardening). The chat agent has NO MCP tools that read, write, mint, or rotate credentials. 9 tools removed from the agent's catalog: providers_{create,update,delete}, instances_{create,update,delete}, api_keys_{create,rotate,revoke}. They remain at the REST surface for the operator UI; the agent simply has no handle to them. The system prompt block tells the agent the boundary so refusals are polite and consistent. CLAUDE.md mandates this rule going forward — adding any new credential-touching MCP tool requires explicit reconsideration.",
      "Login UI port from spark-platform. components/auth/login-screen.tsx replaced wholesale with the spark login page per operator direction ('use the exact components and animations'). Animated WavyBackground (simplex-noise) + decorative robot character on the left half + 3-column form|divider|description grid + animated cyan glow divider + FlippingText typewriter cycling Phantom-relevant tool names. Branding swapped to Phantom-themed copy ('Cortex XSIAM, MITRE ATT&CK, CALDERA, Vertex AI, Gemini, MCP' / 'Continuous SOC simulation').",
      "Reset CLI for the forgot-password case. New mcp/agent/cli/reset-admin.mjs (host-side wrapper at scripts/reset_admin.sh): docker exec phantom_agent node /app/cli/reset-admin.mjs prompts for new password (terminal echo masked) after a 'Type RESET' ceremony, writes to SecretStore, revokes all sessions, audits as actor=cli:<hostname>. Operator restarts the agent container to flush in-memory caches.",
      "Per-service CI builds (lands in the same release). Monolithic build.yml (608 lines) replaced with four focused workflows + composite action: build-xlog.yml, build-agent.yml, build-caldera.yml (path-filter triggers — only changed services rebuild), deploy-dev-installer.yml (workflow_run on any build OR push to installer/**). Two installer binaries from the IDENTICAL script body — only the digest manifest differs. Customer installer = phantom-installer (release.yml, semver digests). Dev installer = phantom-installer-dev (build-flow workflows, :dev digests). Caldera in particular benefits: its container state on phantom-vm now survives pushes that only touched the agent.",
      "Installer cleanup. Deleted installer/reset-ui-password.sh (358 lines, obsolete — replaced by the image-baked reset-admin.mjs). phantom-installer.template.sh: smarter sudo elevation (skips re-exec when INSTALL_DIR writable + docker reachable); post-install banner shows default credentials + change-at-profile flow + forgot-password CLI; old setup-wizard messaging removed. Installer accepts OUTPUT_NAME env var so build-phantom-installer.sh produces 'phantom-installer-dev' for the dev variant.",
      "Customer impact on upgrade: existing v0.3.x customer installs carry their state in the phantom_data volume. v0.4.0 boot finds the existing password hash in SecretStore and skips default-seeding — login continues to work with the customer's existing credentials. Old setup.json / .env.generated / .setup_complete files are NOT deleted by v0.4.0; they're simply never read. Volume-wipe case (operator drops the volume) boots cleanly into the default-credentials path with the post-install banner.",
      "Total code change: +3338 added / -4896 deleted = net -1558 lines across 8 commits. The unusual signature of a clean-break refactor — more came out than went in. 588 lines of dead code purged: deleted setup page surfaces, deleted MCP /api/v1/setup endpoint (zero callers post-Phase 11), deleted lib modules (setup-cleanup, setup-flag, setup-mcp-push, settings-resolve), deleted caldera-creds writer module (zero callers).",
      "Forbidden post-v0.4.0: invoking docker compose up -d / down -v / force-recreate over the IAP tunnel for testing or deploy. The phantom-installer is the contract per CLAUDE.md's 'Local-mirrors-customer deploy flow' rule. Volume management (e.g. wiping for a clean-break test) remains a manual operator step using docker volume rm — installers never touch volumes.",
    ],
  },
  {
    version: "0.3.27",
    date: "2026-05-11",
    title:
      "Approval-mode narrative fix — chat agent no longer promises cards in bypass sessions",
    highlights: [
      "Operator-reported bug, surfaced by triage of an exported session transcript: the agent confidently said 'Pending your approval — the card should appear below.' immediately after six destructive jobs_delete calls had ALREADY executed in ~50ms. No approval cards were ever created. The session was in bypass mode — the whole point of bypass is auto-execute with audit-only recording — and the agent's narrative was disconnected from the operational reality.",
      "Root cause: the chat system prompt (mcp/agent/lib/system-prompt.ts STABLE_SYSTEM_PROMPT_TAIL) hardcoded the narration recipe 'Pending your approval — the card should appear below' into the cached TAIL string. The TAIL ships identical bytes every turn regardless of session.metadata.approval_mode. So the agent reads the manual-mode recipe even when the operator has set the session dropdown to bypass, then dutifully promises cards that the bypass header just told the MCP NOT to render. The MCP-side gate was correct all along; the bug is purely in what the agent SAYS, not in what the agent DOES.",
      "Fix shape: new renderApprovalModeBlock(mode) in lib/system-prompt.ts emits a '## CRITICAL - Approval mode for this session' block with mode-specific narration recipes. Manual mode: promise the card. Bypass mode: warn about immediate execution. buildSystemPromptText accepts approvalMode and inserts the block between persona/skills and the cached TAIL — TAIL stays cacheable, only the new ~50-token block varies. callGemini accepts approvalMode and threads it through every call site in the turn (initial + follow-up + budget-exhausted summary). TAIL example #2 reworded to point at the dynamic block instead of baking in a single recipe — same teaching, no lie.",
      "Type cleanup: ApprovalMode = 'manual' | 'bypass' union moved to lib/system-prompt.ts and imported by app/api/chat/route.ts. The chat route used to declare a local copy; both ends now reference the same import — single source of truth in line with the v0.3.26 clean-design discipline.",
      "Why this isn't a one-line 'if bypass, skip the promise' patch: the narration is the agent's UX contract with the operator ('I'll do X, here's what happens next'). Stripping the next-step sentence would leave the agent saying 'I'll delete the job.' and then the result appearing — no story for the operator. The mode-aware recipe replaces the lie with the truth: 'Bypass mode is on, so this will execute immediately.' Same UX shape (narrate intent, set expectations, then act), correct content per mode.",
      "Migration impact: PATCH release. SELECTIVE recreation — phantom-agent rebuilds; other services retag from v0.3.26 with identical content digests. No data migration. No API breakage. Architecture page #setup-wiring + the new session-approval-mode section refreshed in the same commit. Visible operator change: in bypass-mode sessions the agent now says 'Bypass mode is on, so this will execute immediately' before destructive calls instead of 'Pending your approval'. Manual-mode sessions look unchanged.",
    ],
  },
  {
    version: "0.3.26",
    date: "2026-05-11",
    title:
      "Clean design — no hardcoded skill dict anywhere; frontmatter is the only contract",
    highlights: [
      "Operator-driven clean-design release. v0.3.25 stopped the bleeding from the divergent-truth bug; v0.3.26 finishes the cleanup the operator asked for: no hardcoded skill dict anywhere, frontmatter in each .md file is the single contract, what you see in /skills is what the agent uses.",
      "Three changes: (1) skills_crud._build_record passes through every frontmatter field load_simulation_skills needs — keywords, complexity, duration, attack_type, caldera_required, devices_required, prerequisites, outputs, tactics, techniques. Missing fields return falsy defaults; filter_skills treats absence as 'no constraint'. (2) _HARDCODED_ENRICHMENT deleted entirely (122 lines of hardcoded fiction gone). get_skill_metadata reads disk via skills_crud.get_all_skills() and passes through frontmatter-derived fields directly. (3) port_scan_detection.md got the schema by example — keywords/complexity/attack_type/etc. now declared in YAML frontmatter where they always should have been.",
      "Runtime cleanup on phantom-vm: the operator authorized 'delete them like manual now' so v0.3.26 also rm'd 20 legacy non-bundle skill files from /app/skills/. Skills like midnight_butterfly, ink_and_foil, xsiam_top20_coverage, purple_team_exercise — accumulated from earlier bundle versions but no longer in the current bundle source. Post-cleanup state: 14 skills total (13 bundle scenarios + foundation + 1 plugin example), exactly matching bundles/spark/mcp/skills/.",
      "Going forward — the contract: to add a new skill, create bundles/spark/mcp/skills/<category>/<name>.md with YAML frontmatter declaring whatever metadata fields the skill needs. Build + deploy. The skill appears in /skills, skills_list_all, load_simulation_skills, and the chat agent's <available_skills> block — automatically, from the single .md file. No dict to update. No second source of truth. No drift.",
      "Migration impact: PATCH release. SELECTIVE recreation — phantom-agent rebuilds; other services retag from v0.3.25. On phantom-vm specifically: runtime /app/skills/ already cleaned (34 → 14 active). Operator's .deleted/ denylist preserved (5 entries from earlier UI deletions; protects against future bundle re-introduction). For fresh installs: skills_seed copies clean 14-skill set from /app/mcp/skills-default. Backwards-compatible: load_simulation_skills API unchanged.",
    ],
  },
  {
    version: "0.3.25",
    date: "2026-05-11",
    title:
      "Fix divergent-truth bug — load_simulation_skills now reads disk (no more hardcoded fiction)",
    highlights: [
      "Operator-reported bug: deleted skill (everything_is_now) was reportedly still showing in chat agent response. Investigation found a deeper issue — there were TWO skill-listing tools returning DIFFERENT sets: skills_list_all (disk scan, correctly excludes .deleted/) vs load_simulation_skills (hardcoded Python dict in simulation_skills.py with skill names + file_paths that don't exist on disk). Pre-existing v0.1.x bug.",
      "9 fictional skills the hardcoded dict claimed existed: Ransomware Attack (scenarios/ransomware_attack.md), Credential Theft APT (scenarios/credential_theft_apt.md), Port Scan Detection (scenarios/port_scan.md), Device Vendor & Product Catalog, CALDERA Adversary Selection Guide. None exist on disk. When the chat agent called load_simulation_skills and then tried to skills_read the 'available' skill, it got file-not-found errors.",
      "Fix: get_skill_metadata() now scans disk via skills_crud.get_all_skills() (same canonical path skills_list_all uses with the .deleted/ exclusion from v0.3.8). Baseline metadata comes from disk + frontmatter; the hardcoded dict (renamed to _HARDCODED_ENRICHMENT) becomes ENRICHMENT-ONLY for keywords/attack_type/complexity/duration/prerequisites — overlay applied only for known skills, silently dropped for skills not on disk.",
      "Enrichment-dict cleanup: 2 keys renamed to match canonical filenames so keywords actually apply (ransomware_attack → ransomware_double_extortion; port_scan → port_scan_detection). 3 zombie entries (device_vendor_catalog, credential_theft_apt, caldera_adversary_selection_guide) left in the dict but silently dropped at merge — they'd auto-revive if a similarly-named skill is added later.",
      "Post-fix invariant: both skills_list_all AND load_simulation_skills now return the same on-disk set (modulo load_simulation_skills's filtering). Deleted skills are gone from both. Operator-added skills appear in both. The divergent-truth class of bug is closed.",
      "Migration impact: PATCH release. SELECTIVE recreation — only phantom-agent rebuilds; other services retag from v0.3.24 with identical content digests. No breaking changes to load_simulation_skills's API — same args, same response shape, only the source data changes from hardcoded-dict to disk-truth. After deploy, the chat agent's 'list skills' response reflects the real on-disk state.",
    ],
  },
  {
    version: "0.3.24",
    date: "2026-05-11",
    title:
      "Docs sync for the setup-cleanup migration (v0.3.20–v0.3.23)",
    highlights: [
      "Documentation discipline release. v0.3.20-v0.3.23 shipped the setup-cleanup migration end-to-end (PBKDF2 hash write + credential strip + file delete + .env.generated cleanup + CI smoke fix) but skipped the canonical-docs update. v0.3.24 closes that gap — same pattern as v0.3.16 (architecture-page sync for v0.3.10-v0.3.15 features).",
      "Architecture page #setup-wiring: new SubSection 'Legacy file cleanup migration (v0.3.20+)' added after the existing 'Implementation status (v0.1.34 ships the spec)' subsection. Documents the four-release migration arc (credential migration → empty-shell delete → .env.generated cleanup → CI smoke fix), including a code block showing the post-migration end-state /app/runtime/ listing and explanation of the `migration: {stripped: [...]}` receipt in the login response.",
      "User help page #first-run: new paragraph under 'Scenario 2 — Upgrade preserves everything' describing the v0.3.20+ first-login migration receipt for operators upgrading from v0.1.x. Links to the architecture-page SubSection for design detail.",
      "Migration impact: PATCH release. NO runtime code paths change — only the help pages render new content. SELECTIVE recreation: only phantom-agent rebuilds; other services retag from v0.3.23 with identical content digests. Backwards-compatible: existing deep links to /help/architecture#setup-wiring and /help/user continue to resolve; new content is purely additive.",
    ],
  },
  {
    version: "0.3.23",
    date: "2026-05-11",
    title:
      "CI smoke fix — T9.2 picks manifest jobs (no more false `deploy: failure` status)",
    highlights: [
      "Fixes the persistent T9.2 jobs manual-trigger flake. Since v0.3.19, every build showed `deploy compose stack: failure` even when the deploy itself succeeded — only the post-deploy smoke probe was failing. Operator-visible signal was misleading.",
      "Root cause: T9.2 picked the alphabetically-first job and POSTed to /api/v1/jobs/<name>/run. On phantom-vm that first job was 'Say hi back' — an operator-created runtime YAML chat job. Chat-action jobs dispatch through the agent's chat handler which requires Vertex. With the long-standing stale-Vertex-provider KEK-mismatch, chat jobs return status=failed → T9.2 fails. Was 100% reproducible because that specific job sorted first.",
      "Fix: smoke now prefers MANIFEST-declared jobs over runtime YAML jobs. Manifest jobs are bundle-declared, stable across deployments, and shaped as tool_call actions that don't depend on Vertex. Smoke picks the first manifest-source job; falls back to overall jobs[0] only if no manifest jobs exist (edge case).",
      "Diagnostic improvement: pre-v0.3.23 the failure message was just `status=failed` — zero signal about which job dispatched. v0.3.23 surfaces the picked job name in failure messages: `T9.2 manual trigger of 'continuous-coverage-cycle': status=failed`. Future debugging starts from a known reference point.",
      "Migration impact: PATCH release. No runtime code paths change — only the post-deploy smoke probe. The script ships in the agent image; agent rebuilds, other services retag from v0.3.22 with identical content digests. After v0.3.23 deploys, CI's `deploy compose stack` job shows success (assuming nothing else broke) instead of the misleading `failure` state.",
      "Note: this does NOT fix the underlying Vertex KEK-mismatch — that's still an operator-driven fix (approve the Vertex cleanup card at /approvals + re-add via Setup). v0.3.23 just stops the smoke from amplifying it into a deploy-status false alarm.",
    ],
  },
  {
    version: "0.3.22",
    date: "2026-05-11",
    title:
      ".env.generated cleanup — last on-disk home for operator credentials eliminated",
    highlights: [
      "Completes the legacy-credentials elimination. v0.3.20 + v0.3.21 deleted setup.json from phantom-vm. v0.3.21's post-deploy smoke surfaced a second copy of the same problem: /app/runtime/.env.generated still on disk, 2.7K bytes, still sourced by entrypoint.sh at boot — putting UI_PASSWORD, GOOGLE_APPLICATION_CREDENTIALS (full Vertex SA JSON inline), GEMINI_MODEL, etc. back into process.env where the runtime-config fallback chain picks them up.",
      "Pre-v0.1.34 the setup form's writeRuntimeSetup wrote BOTH setup.json and .env.generated. v0.1.34 deleted writeRuntimeSetup entirely but on-disk artifacts from earlier installs persisted. v0.3.20/v0.3.21 cleaned setup.json; v0.3.22 cleans the symmetric .env.generated leftover.",
      "Same FIELDS_TO_STRIP as v0.3.20 (UI creds, Vertex creds, connector secrets, GEMINI_MODEL, defaultLogFormat, PHANTOM_TLS_VERIFY) plus XLOG_URL (env-only legacy; InstanceStore is now canonical).",
      "Bundle-internal coordination keys PRESERVED: MCP_HOST, MCP_PATH, MCP_PORT, MCP_TRANSPORT. These aren't operator credentials — they're docker-compose-shaped runtime config the entrypoint reads from process.env to wire the embedded MCP's HTTP listener. Stripping them would break the listener. MCP_TOKEN + MCP_URL were already excluded by the pre-v0.1.34 writer.",
      "File-delete when empty: same .setup_complete-gated delete logic as v0.3.21. If the strip pass leaves the file with zero remaining assignments (only blank lines / comments), fs.unlink. Otherwise rewrite atomically with surviving lines.",
      "Trigger: piggybacks on the same login-time migration as v0.3.20/v0.3.21. migrateLegacyCredentials now runs three strip steps — setup.json (v0.3.20), setup.json file-delete (v0.3.21), .env.generated (v0.3.22). Login response's migration.stripped array now includes env:<KEY> entries (prefixed to distinguish from setup.json strips).",
      "After v0.3.22 deploys + next login on phantom-vm: ls /app/runtime/ shows ONLY .setup_complete (25 bytes — the canonical signal). UI_PASSWORD, full SA JSON, all connector creds have no on-disk plaintext home anywhere; they live exclusively in SecretStore/ProviderStore/InstanceStore/settings_store with KEK-backed AES-GCM at rest.",
      "Migration impact: PATCH release. SELECTIVE recreation — phantom-agent rebuilds; other services retag from v0.3.21 with identical content digests. Rollback safe: entrypoint sources .env.generated only if file exists; missing file falls through to docker env defaults; stores remain populated.",
    ],
  },
  {
    version: "0.3.21",
    date: "2026-05-11",
    title:
      "setup.json file-delete after migration — completes v0.3.20's spec-compliance work",
    highlights: [
      "Completes v0.3.20. v0.3.20 stripped operator credentials from setup.json but left a tiny shell (one or two fields + outer metadata + migratedAt timestamp). v0.3.21 finishes the job: after migration leaves the file credential-empty AND .setup_complete exists, the file is DELETED entirely.",
      "Why this matters: per /help/architecture#setup-wiring, 'A small flag file may exist holding only the setup-completed boolean, but it MUST NOT carry any operator credentials' — and the canonical flag is .setup_complete (presence-only), NOT setup.json. Leaving setup.json (even empty) preserves a file an operator might check for credentials and find suspicious. Spec compliance is 'setup.json doesn't exist post-setup-complete.'",
      "Added PHANTOM_TLS_VERIFY to FIELDS_TO_STRIP. It's an env-managed runtime knob (set via docker env, NOT via the setup form); the legacy setup.json copy was dead data. The agent's existing fallback in getEffectiveRuntimeConfig reads it from process.env directly.",
      "File-delete is gated on .setup_complete existing — we don't race-delete during pre-setup boot. The form POST handler stamps .setup_complete after materializing instances; once that flag is present, subsequent migrations can safely unlink setup.json knowing the canonical signal is in place.",
      "After v0.3.21 deploys: next successful login on phantom-vm migrates remaining PHANTOM_TLS_VERIFY, deletes setup.json, ls /app/runtime/ shows only .setup_complete. Idempotent re-runs find no file → quiet no-op.",
      "Migration impact: PATCH release. SELECTIVE recreation — only phantom-agent rebuilds; other services retag from v0.3.20. Backwards-compatible: pre-setup boot still works (gate prevents race delete); post-setup boot with v0.3.20-migrated shell completes cleanup in one login. Rollback to v0.3.20 image is safe — missing setup.json hits the same fallback chain that empty-shell setup.json hits.",
    ],
  },
  {
    version: "0.3.20",
    date: "2026-05-11",
    title:
      "setup.json plaintext-credentials migration — finishes v0.1.34's setup-wiring spec drift",
    highlights: [
      "Closes the spec drift surfaced during the v0.3.19 smoke session: /app/runtime/setup.json was still carrying operator-typed credentials in plaintext (UI_PASSWORD, full Vertex SA JSON, every connector secret) — a direct violation of /help/architecture#setup-wiring which mandates 'No setup.json with operator-typed values.' v0.1.34 migrated Vertex + xlog to their proper stores but didn't strip the legacy mirror. v0.3.20 finishes that job.",
      "Trigger: on the next successful legacy-plaintext login, the route now ALSO writes a PBKDF2-HMAC-SHA256 hash to SecretStore (/ui/auth/<user>/password_hash, 600k iterations, AES-GCM-encrypted at rest), writes setupUiUser/geminiModel/defaultLogFormat to settings_store, and strips the 20+ now-redundant plaintext fields from setup.json. Migrated fields are documented in FIELDS_TO_STRIP at setup-cleanup.ts with their canonical home (ProviderStore primary-vertex, InstanceStore primary-xsiam, SecretStore (caldera), settings_store.setupUiUser, etc.).",
      "Best-effort + idempotent: each migration step is wrapped in try/except; failure is logged but doesn't block the login. Hash-write skipped if already set. settings_update is set-if-different. Field-strip is no-op for missing keys. Worst case: next login retries.",
      "New read path: lib/settings-resolve.ts (new file) fetches setupUiUser/geminiModel/defaultLogFormat from settings_store with a 30s in-memory cache (same pattern as vertex-credentials.ts). Runtime-config now reads store-first, falls back to setup.json only when the store is empty. Pre-setup boot still works because settings_store returns empty on cache miss and the fallback chain finds the manifest defaults.",
      "What was NOT done: the pre-setup form path still writes to setup.json as a bootstrap dump-bag (the setup form POST handler walks manifest.bindsInstances + bindsProviders to write the proper stores, but the form payload itself lands in setup.json first). v0.3.21 can lift that to a transient in-memory artifact. Also setup.json isn't fully deleted yet — v0.3.20 strips known-migrated fields and leaves the outer shell + a migratedAt timestamp.",
      "Operator-visible effect: on your next login you'll get the standard success response plus a one-time `migration: {stripped: [...]}` field. After the migration runs, cat /app/runtime/setup.json shows only the outer shell — all 20+ plaintext credential fields are gone. /api/v1/metrics and runtime behavior unchanged.",
      "Migration impact: PATCH release. SELECTIVE recreation — only phantom-agent rebuilds; other services retag from v0.3.19 with identical content digests. Rollback safety: migration is gated on usedLegacy === true; each step is wrapped in try/except. Reverting to v0.3.19 image is safe — the now-empty setup.json shell stays valid; legacy fallback path resumes reading from it (finds nothing → uses defaults).",
    ],
  },
  {
    version: "0.3.19",
    date: "2026-05-11",
    title:
      "Cache-layer tests for cortex-content/_github_client (11 cases — TTL, corruption, path safety)",
    highlights: [
      "Test-only release. Closes the last remaining test-coverage gap in the v0.3.x cluster: the file-backed TTL cache layer in cortex-content/_github_client.py. v0.3.19 adds 11 focused tests covering the cache contract — round-trip, TTL expiry, corruption resilience, path-traversal safety, sharded directory layout, and IO-failure isolation.",
      "Scope decision: cache layer only, no urllib mocking. Mocking urllib.request is intrusive and bears little resemblance to real HTTP failure modes (transient 502s, redirects, content-encoding). The cache layer is where silent-corruption bugs hide and is pure-Python with deterministic inputs — unit tests are cheap and high-value there.",
      "Coverage groups: round-trip + isolation (4 cases — write/read/distinct-keys/deterministic-paths), TTL behavior (3 cases — backdated-mtime expires entry, zero-TTL disables cache, negative-TTL clamped to zero), corruption + IO robustness (3 cases — corrupt JSON returns None, envelope shape, path-traversal safety via SHA256 hashing, sharded 2-char subdirs), read-failure isolation (1 case — file IO error logs warning + returns None instead of propagating).",
      "Uses the same synthetic-package import as test_cortex_content_index_kb.py to sidestep the connector-src vs MCP-src namespace collision. Both test files share the _cortex_test_pkg synthetic name so the connector module loads once and reuses.",
      "Migration impact: test-only — no runtime code paths change. Image rebuild identical to v0.3.18. SELECTIVE recreation: only phantom-agent rebuilds with the new test file; other services retag from v0.3.18 with identical content digests.",
    ],
  },
  {
    version: "0.3.18",
    date: "2026-05-11",
    title:
      "Unit tests for the tool_dispatcher singleton (7 cases — lifecycle + log signals)",
    highlights: [
      "Test-only release. Closes the last meaningful test-coverage gap from this v0.3.x cluster: the v0.3.11 tool_dispatcher singleton module. Pre-v0.3.18 the singleton was integration-tested only through agent_batch_propose's connector-dispatch cases — a regression in set_tool_dispatcher / get_tool_dispatcher would have been caught eventually but with an opaque 'batch test broke' failure. v0.3.18 adds direct unit tests with 1-line diagnostics.",
      "7 cases: initial-state-is-None, set-installs-dispatcher, set-None-clears, set-overrides-existing, installed-dispatcher-is-awaitable (validates the Awaitable[Any] return-shape contract), set-emits-log-signal ('tool_dispatcher installed' at INFO), clear-emits-log-signal ('tool_dispatcher cleared').",
      "The boot-log signal 'tool_dispatcher installed' is documented in the v0.3.16 architecture page (#tool-dispatch section) as the operator-visible confirmation that v0.3.11's singleton is wired. A logging refactor that silently dropped that line would break operator smoke-test grep patterns without breaking any other test. v0.3.18 closes that gap by asserting the log message directly.",
      "Fixture isolation: _reset_singleton is autouse and resets the module-level holder before AND after each test. Same pattern as test_agent_batch_propose's fixture; prevents the 'test passes alone but breaks in suite' failure mode.",
      "Migration impact: test-only — no runtime code paths change. Image rebuild identical to v0.3.17. SELECTIVE recreation: only phantom-agent rebuilds with the new test file; other services retag from v0.3.17 with identical content digests.",
    ],
  },
  {
    version: "0.3.17",
    date: "2026-05-11",
    title:
      "Prometheus metrics for cortex-content/index_kb (symmetric with v0.3.15 batch metrics)",
    highlights: [
      "Closes the symmetric observability gap from v0.3.15. That release added Prometheus metrics for agent_batch_propose; the companion feature cortex-content/index_kb (v0.3.9) had no metrics either. v0.3.17 fixes that with the same emission pattern.",
      "phantom_cortex_content_index_runs_total{pack=<name>,result=succeeded|partial|failed} — one inc per index_kb call. partial = some indexed, some errored; failed = errors with zero successful indexes. Operators alert on result=failed aggregations and use the pack label to rank flaky packs.",
      "phantom_cortex_content_indexed_docs_total{action=insert|update|unchanged} — one inc per document inside a pack-index call. insert/update mean a Vertex embedding was generated; unchanged means source_hash dedupe skipped the embed step. Splits new-content rate from cache-hit rate.",
      "Same emission shape as v0.3.15: lazy registry lookup, try/except silent-fail wrappers, counters pre-declared in manifest.observability.metrics[] so dashboards see them as 0-valued counters before any index call fires.",
      "4 new pytest cases (test_metrics_emitted_on_successful_index / doc_counter_distinguishes_unchanged / run_counter_records_failed_on_full_failure / silent_when_registry_unavailable). Autouse fixture installs a fresh MetricsRegistry per test.",
      "Closes the feature → tests → metrics → docs pattern that v0.3.10-v0.3.16 established for agent_batch_propose: now cortex-content/index_kb has feature (v0.3.9) + tests (v0.3.14) + metrics (v0.3.17) + docs (v0.3.16 architecture-page sync).",
      "Migration impact: PATCH release. SELECTIVE recreation — only phantom-agent rebuilds; other services retag from v0.3.16 with identical digests. Backwards-compatible: new metrics appear in /api/v1/metrics as 0-valued counters immediately post-upgrade.",
    ],
  },
  {
    version: "0.3.16",
    date: "2026-05-11",
    title:
      "Architecture-page sync — agent_batch_propose, tool_dispatcher, yaml-issues, batch metrics",
    highlights: [
      "Documentation-discipline release. v0.3.10 through v0.3.15 added agent_batch_propose, the tool_dispatcher singleton, the yaml-issues endpoint, and batch metrics WITHOUT touching the canonical architecture spec at /help/architecture. Per CLAUDE.md's docs-discipline rule, the architecture page IS the platform spec — every operator-visible feature must be reflected there or the spec drifts from reality. v0.3.16 closes that gap.",
      "Four new SubSections inserted into existing top-level sections (no navigation restructure, no broken operator-facing deep links): 'Batch propose — one card for N actions (v0.3.10+)' under #approvals; 'Process-wide tool_dispatcher singleton (v0.3.11+)' under #tool-dispatch; 'YAML load-issue surfacing (v0.3.13+)' under #jobs-subsystem; 'Prometheus metrics — registry + emission' under #logs-events-traces.",
      "Each SubSection covers the why-this-exists motivation, the implementation key points, and the operator-facing surfaces (endpoints, boot-log signals, metric names with their label conventions). Total ~150 lines of new prose across the 5200-line page.",
      "The trade-off explicitly weighed in v0.3.15's stop-summary was 'large file → tedious to navigate'. In practice the actual edit work was 4 targeted insertions at well-known section boundaries — cost-effective once the operator-value framing made it clear this isn't speculative polish but a required documentation step.",
      "Migration impact: PATCH release. No runtime code paths change — only the /help/architecture page renders new content. SELECTIVE recreation: only phantom-agent rebuilds; other services retag from v0.3.15 with identical digests. Backwards-compatible: existing deep links continue to resolve; new SubSections are purely additive.",
    ],
  },
  {
    version: "0.3.15",
    date: "2026-05-11",
    title:
      "Prometheus metrics for agent_batch_propose — proposals, per-action, size histogram",
    highlights: [
      "Observability release. v0.3.10/v0.3.11 shipped agent_batch_propose with full audit-log integration but no Prometheus metrics — operators with a Grafana dashboard couldn't see batch traffic, approve-vs-deny ratio, or per-tool usage at a glance. v0.3.15 closes that gap with 3 new metric families.",
      "phantom_batch_proposals_total{approved=true|false} — every agent_batch_propose call increments once. Reveals batch usage AND the deny-rate over time.",
      "phantom_batch_actions_total{tool=<name>,result=success|fail} — one inc per individual action inside a batch. The tool label reveals which tools dominate batch traffic; result splits success vs failure for per-tool reliability dashboards. An action returning {error: ...} counts as fail, distinguishing per-tool flakiness from per-tool usage.",
      "phantom_batch_size — histogram of batch sizes with custom count-buckets (1, 2, 3, 5, 10, 25) matching the v0.3.10 25-action cap. Observed on both approve and deny paths (a denied 3-action batch is meaningful telemetry). Lazy-registered on first call since manifest pre-registration only handles counters.",
      "Silent-fail on metrics errors: the emission helpers wrap every metric call in try/except — metrics failures must NEVER affect the tool's primary path. The agent's batch result is correct regardless of whether observability collected the data point.",
      "4 new pytest cases (test_metrics_emitted_on_approve / on_deny / fail_on_error_dict / silent_when_registry_unavailable). The fixture's _reset_caches now installs a fresh MetricsRegistry per test so counter state doesn't bleed between tests.",
      "Migration impact: PATCH release. SELECTIVE recreation — only phantom-agent rebuilds; other services retag from v0.3.14 with identical digests. Backwards-compatible: new metrics appear in GET /api/v1/metrics as 0-valued counters immediately post-upgrade. No API shape changes, no required operator action.",
    ],
  },
  {
    version: "0.3.14",
    date: "2026-05-11",
    title:
      "Test coverage for cortex-content/index_kb (11 cases — validation, dispatch, dedupe, flat-file rules)",
    highlights: [
      "Test-only release. Same shape as v0.3.12 (which added 15 tests for agent_batch_propose). v0.3.9 shipped cortex-content/index_kb with end-to-end smoke verification only — no unit-test coverage of the behavior contracts. v0.3.14 adds 11 pytest cases that defend the tool against future regressions.",
      "Coverage groups: 5 validation cases (empty pack_name/empty kb_name/unknown rule_type/KB unavailable/missing pack_metadata), 2 happy-path cases (single modeling rule with all 3 files indexes cleanly with correct content composition + metadata; source_hash dedupe lands re-runs in `unchanged` count not `indexed`), 2 partial-failure cases (no ModelingRules dir → not an error; rate limit during list_dir → captured in errors[] but loop continues), 2 flat-file correlation-rule cases (flat <rule>.yml with optional .xql counterpart; orphan yml without xql still indexes cleanly).",
      "Path resolution: the cortex-content connector lives in a sibling bundle directory under either bundles/spark/connectors/cortex-content/src/ (source tree) or /app/bundle/connectors/cortex-content/src/ (container). The test uses a candidate-list lookup that resolves either layout, so the same file passes both locally and in CI.",
      "Mocking: GitHubClient is fully mocked via a _make_client_mock() helper that accepts dicts of {path: response} per public method plus optional _raises overrides for path-keyed exceptions. The KB singleton is replaced with a _StubKB whose upsert records calls so tests assert doc_id, content composition, metadata, and source_hash. The connector's bare-name _get_client() lookup resolves through the module's __dict__, so monkeypatch.setattr(connector, '_get_client', ...) cleanly redirects without refactoring the connector module.",
      "Migration impact: test-only — no runtime code paths change. Image rebuild identical to v0.3.13. SELECTIVE recreation: only phantom-agent rebuilds with the new test file; other services retag from v0.3.13 with identical digests. The cortex-content connector runs unchanged at runtime; only the test surface grows.",
    ],
  },
  {
    version: "0.3.13",
    date: "2026-05-11",
    title:
      "YAML-load failures move from docker compose logs to /jobs UI + /api/v1/jobs/yaml-issues",
    highlights: [
      "Hygiene release. Pre-v0.3.13 every boot emitted 6+ WARN-level lines like 'YAML job load failed for /app/data/jobs/<file>: action.type must be one of tool_call|prompt, got log — skipping'. These leftover YAMLs from earlier schema versions trained operators to ignore the WARN level (the opposite of what an enterprise log signal should do) and buried remediation guidance in docker compose logs.",
      "Per the platform's UX contract — issues belong in /observability and the UI, NOT in docker compose logs — v0.3.13 surfaces YAML-load failures via a new endpoint + UI banner on /jobs. The boot log now emits ONE INFO line summarizing the count.",
      "Backend: load_yaml_jobs() collects per-file failures into scheduler.yaml_load_issues (list of {path, basename, error, mtime}) instead of WARN-logging each. New bearer-auth endpoint GET /api/v1/jobs/yaml-issues returns the list, proxied through the agent at /api/agent/jobs/yaml-issues.",
      "UI: when yaml-issues count > 0, /jobs renders a yellow banner above the summary cards with a collapsible details panel showing each failed file's basename + error. Operators fix the YAML in place (docker exec phantom_agent vi /app/data/jobs/<basename>) or delete stale files. Read-only — no auto-quarantine, no auto-delete; the data files belong to the operator.",
      "Tests: two new pytest cases assert (a) two distinct failure modes both land in yaml_load_issues with all contract fields, (b) empty list when all files load cleanly (UI banner suppression contract).",
      "Migration impact: PATCH release. SELECTIVE recreation — only phantom-agent rebuilds; other services retag from v0.3.12 with identical digests. Backwards-compatible: no data shape changes. Operators with malformed YAMLs see the banner appear on /jobs (which were already failing — v0.3.13 just makes the failure visible). Boot log goes from N WARN lines to 1 INFO line.",
    ],
  },
  {
    version: "0.3.12",
    date: "2026-05-11",
    title:
      "Test coverage for agent_batch_propose (15 cases — validation, dispatch routes, bypass lifecycle)",
    highlights: [
      "Test-only release. Closes the technical-debt gap from v0.3.10/v0.3.11 — those shipped agent_batch_propose with no unit-test coverage (verification was end-to-end smoke only). v0.3.12 adds tests/test_agent_batch_propose.py with 15 pytest cases that exercise the tool's behavior contracts so future changes don't silently regress.",
      "Coverage groups: 8 validation cases (empty/oversize/malformed/missing-field/non-dict-args/nested-propose/approvals_resolve/unknown-tool), 3 built-in dispatch cases (happy path 2× / partial-success / exception-caught), 2 deny+bypass-contextvar cases (denied batch leaves no side effects; bypass contextvar reset on exception via try/finally), 3 connector-tool dispatch cases (v0.3.11 path via tool_dispatcher singleton, pre-flight registry check, mixed built-in+connector batch), 1 approval-card payload shape (asserts the contract the UI's batch render branch depends on).",
      "Test infrastructure uses the same fixture pattern as test_approval_gate.py — per-test InProcessApprovalsBus against tmp_path, auto-approve helper via background task with 0.05s delay (well under the 1s bus timeout), LRU-cache + module-state cleanup in fixture teardown so tests are order-independent.",
      "For v0.3.11 connector-tool tests, the private connector_loader._reload_state singleton is monkeypatched with a fake tool_registry, and the dispatcher is replaced with a stub that records calls. Isolates the test from the full MCP boot path while still exercising the dispatch routing logic end-to-end.",
      "Migration impact: test-only — no runtime code paths change. Image rebuild identical to v0.3.11 (tests run inside the agent image during the build's test-mcp-server job, which is the same image that gets deployed). SELECTIVE recreation: only phantom-agent rebuilds with the new test file; other services retag from v0.3.11 with identical digests.",
    ],
  },
  {
    version: "0.3.11",
    date: "2026-05-11",
    title:
      "agent_batch_propose now dispatches to connector tools (xsiam.*, caldera.*, web.*, etc.)",
    highlights: [
      "Closes the v0.3.10 deferral: batch_propose can now include connector tools, not just built-in self-mod ops. Two dispatch routes per action — built-in tools take the v0.3.10 fast path (direct call); connector tools go through the unified tool_dispatcher (same fastmcp.Client path the job scheduler uses), which preserves per-instance contextvar setup, Pydantic marshalling, and CallToolResult unwrapping.",
      "New tool_dispatcher singleton module (set_tool_dispatcher / get_tool_dispatcher) — same pattern as set_scheduler / get_scheduler. main.py constructs it unconditionally at boot after register_all_tools and installs it so it's available regardless of whether the bundle declared any cron jobs (pre-v0.3.11 the dispatcher only existed inside the `if defs:` scheduler branch).",
      "Validation extended: non-builtin tools are pre-flight-checked against the live tool_registry (via the connector_loader._reload_state singleton) — if a connector isn't configured (no instance), its tools aren't registered, and a batch referencing them fails fast with a descriptive error instead of dispatching to a missing tool at execution time.",
      "Hard exclusions preserved (v0.3.10): agent_batch_propose itself (no nesting), approvals_resolve (logical loop). Everything else in the registry is batchable; reads are technically allowed but rarely useful inside a batch.",
      "Use cases v0.3.11 enables: 'send 10 different synthetic alerts to test detection coverage' → batch of xsiam.send_webhook_log; 'run my 3 attack scenarios in sequence' → batch of caldera.create_operation; 'index F5APM + Okta + CiscoESA + AWS packs into my KB' → batch of cortex-content/index_kb. The operator sees the whole plan on one approval card; on approve, the executor flips the bypass contextvar and dispatches each action.",
      "Migration impact: PATCH release. SELECTIVE recreation — only phantom-agent rebuilds; xlog/caldera/browser/updater retag from v0.3.10 with identical digests. Backwards-compatible: v0.3.10 batches (built-in-only) work identically; pre-v0.3.11 callers that referenced non-builtin tools got a clean error envelope, v0.3.11 callers get the action executed. The UI render is unchanged — connector tool names appear in the action list with the same row format as built-ins.",
    ],
  },
  {
    version: "0.3.10",
    date: "2026-05-11",
    title:
      "agent_batch_propose — one approval card for N actions",
    highlights: [
      "NEW: agent_batch_propose MCP tool bundles N self-modification actions into ONE approval ceremony. Closes the operator pain reported during v0.3.7 smoke testing: the agent created 5 jobs at once but the operator had to approve each separately, and cards 4-5 timed out by the time card 3 cleared. The agent now calls agent_batch_propose([{tool: 'jobs_create', args: {...}}, ...]) once; ONE approval card appears with the whole plan inline; on approve, the executor flips the bypass contextvar and dispatches each action sequentially (audit-only, no further UI ceremony).",
      "Whitelist: 17 batchable tools across Tier 2/3/4 self-mod ops — jobs_*, personality_*, settings_*, notifications_dismiss_*, instances_delete, providers_delete, skills_delete, api_keys_create/rotate/revoke. Explicitly excluded: agent_batch_propose itself (no nesting), approvals_resolve (loop hazard). Connector tools (web.*, xsiam.*) are out of scope for v0.3.10 — deferred to v0.3.11+ for the per-instance contextvar plumbing.",
      "Eager validation BEFORE the approval card: actions must be a non-empty list of ≤25 items, each {tool: str, args: dict}, with tool in the whitelist. Validation errors return a clean error envelope (no approval card fired) so the agent can self-correct without burning operator attention on a malformed plan.",
      "Per-action partial success: per_action_results: [{tool, args, ok, result?, error?}] shape lets the operator see exactly what worked vs. didn't. A single bad action doesn't abort the loop — the operator can decide whether to re-run the failed subset without losing the work that did succeed.",
      "UI: approval-card.tsx renders a 'Proposed batch (N actions)' list view when approval.tool === 'agent_batch_propose'. Each row shows the tool name + top-2 args via the existing buildArgSummary helper. List is scroll-capped at max-h-64 so a 25-action batch doesn't blow out the chat layout. Below the list, the MCP-side summary string ('batch of 5 actions: 5× jobs_create') renders as italic context. The standard approve/deny buttons, raw-args expander, and tier styling are unchanged.",
      "Architecture: reuses the existing approval row (just encodes the batch in args.actions[]) instead of introducing a new 'batch' approval kind. No DB schema migration, no new approval-bus state, no refactor of the per-tool gates — just one new meta-tool + a UI render branch. Pre-v0.3.10 approval cards render identically; the batch detector falls through cleanly when tool !== 'agent_batch_propose'.",
      "Migration impact: PATCH release. SELECTIVE recreation — only phantom-agent rebuilds; xlog, caldera, browser, updater retag from v0.3.9 with identical digests. Fully backwards-compatible: the agent doesn't have to use agent_batch_propose; single-action approval continues unchanged.",
    ],
  },
  {
    version: "0.3.9",
    date: "2026-05-11",
    title:
      "cortex-content KB indexing — semantic search across XSIAM marketplace packs",
    highlights: [
      "NEW: cortex-content/index_kb tool walks one pack's ModelingRules + ParsingRules + CorrelationRules and upserts each into the agent's knowledge_search KB (kb_name='cortex-content'). After indexing, the agent semantic-searches 'XDM rule for cisco_esa' or 'detection for okta brute-force' via the standard knowledge_search tool instead of round-tripping through cortex-content/list_*/get_* per pack.",
      "Composition: each rule becomes one KB document with doc_id=<pack>/<type>/<rule_name>. Content is a composed markdown blob — .xif (XQL code), .yml (rule metadata), and _schema.json (dataset → field types) inlined as fenced code blocks. Semantic search keys on the intent + implementation + output-shape together. Source_hash dedupe means re-indexing is cheap (only re-embeds rules whose content actually changed).",
      "Scope: one pack per call (typically 1-5 rules per pack, seconds to a minute). No bulk-index-everything intentionally — keeps per-call latency bounded so agent-driven indexing stays responsive. Operators sequentially index the ~26 packs that ship ModelingRules as needed; idempotency means it's safe to re-run.",
      "Integration: zero new infrastructure. Uses the existing SqliteKnowledgeBase singleton at /app/data/kb.db (partitioned by kb_name), the existing VertexEmbedder (or TextHash fallback when Vertex creds are degraded), and the existing knowledge_search tool. Same connector-imports-usecase pattern that xsiam's xql_rag_service uses.",
      "Flat-file correlation rules: some packs ship CorrelationRules as flat <rule>.yml files (no directory). The tool handles both shapes — directory rules go through _index_one_rule (xif + yml + schema); flat correlation rules go through _index_one_correlation_flat (yml + optional xql).",
      "Migration impact: PATCH release. SELECTIVE recreation — only phantom-agent rebuilds (embeds the updated connector + marketplace entry); xlog, caldera, browser, updater retag from v0.3.8 with identical digests. Backwards-compatible: the 9 existing cortex-content tools are unchanged; index_kb is purely additive.",
    ],
  },
  {
    version: "0.3.8",
    date: "2026-05-11",
    title:
      "Skill-deletion survives release upgrades + jobs_create idempotency hint + self-mod docstring audit round 2",
    highlights: [
      "FIX: skills the operator deleted in the UI now stay deleted across release upgrades. Pre-v0.3.8 every new image rebuilt the .deleted/ skill from baked defaults during the marker-driven seed merge (the v0.3.2 mechanism that auto-rolls new image-baked default skills out to existing volumes). v0.3.8 walks /app/skills/.deleted/ after the cp -r merge and removes any basename match from the active category dirs — the .deleted/ directory becomes a per-operator denylist that survives release hops. Operator-created skills (no image-default counterpart) are unaffected; image-default skills the operator did NOT delete still get the latest version on upgrade. To revive a deleted skill: docker exec phantom_agent mv /app/skills/.deleted/<basename>.md /app/skills/<category>/<basename>.md.",
      "FIX: jobs_create docstring now advises the agent to call jobs_list first before minting. Operator reported duplicate jobs for the same skill (skill-email-malware-15min + skill-email-malware-15min-1) emerging from follow-up clarification messages being re-interpreted as new requests. The architectural fix is the v0.3.10 plan-then-batch flow; v0.3.8 is the soft fix (idempotency hint in docstring → fewer duplications today).",
      "MCP tool docstring audit round 2: the remaining six self-mod tools (settings_update, instances_delete, providers_delete, api_keys_create / api_keys_rotate / api_keys_revoke) get the same parameter-clarity treatment that jobs_create/jobs_update received in v0.3.7. Each docstring now describes (a) what the tool does in operator language, (b) the risk-tier approval semantics and the fact that THESE tools have no bypass_approvals knob — only jobs_create/jobs_update do, (c) the canonical id shape from the corresponding *_list tool (not the display label), (d) the difference from sibling tools where overlap exists (rotate vs revoke, providers_delete vs instances_delete). settings_update also gets the full 7-key overridable allow-list inline so the agent stops guessing arbitrary settings and tripping rejected[].",
      "Migration impact: PATCH release. SELECTIVE recreation — only phantom-agent rebuilds (entrypoint.sh + docstrings); xlog, caldera, browser, updater retag from v0.3.7 with identical digests. No operator action required.",
    ],
  },
  {
    version: "0.3.7",
    date: "2026-05-11",
    title:
      "cortex-content connector + SecretStore hardening + chat dropdown pre-session render + jobs page redirect + docstring audit",
    highlights: [
      "NEW: cortex-content connector — XSIAM/XSOAR content packs bundled with Phantom. 9 tools (list_packs, search_packs, get_pack + list/get for ModelingRules/ParsingRules/CorrelationRules). All reads are local — no network. The agent uses these as references when authoring or updating XDM data models for the operator's tenant — instead of guessing XDM paths (the failure mode that produced the wrong xdm.network.bytes / xdm.network.lb.* / xdm.email.body mappings in v0.3.7 model-authoring), it grounds each mapping against the canonical pack implementation. Surfaces in /marketplace as a v0.3.7 connector ready to install.",
      "SECURITY: PHANTOM_SECRET_KEK is now REQUIRED. Pre-v0.3.7 the SecretStore silently fell back to plaintext-on-disk mode when the env var was unset, with only a startup warning. The fallback caused Vertex SA JSON and other sensitive blobs to land cleartext under /app/data/secrets/ on manual deploys that bypassed the installer. v0.3.7+ refuses to construct with a clear remediation message naming both fixes: generate a KEK (openssl rand -base64 32) OR set the new PHANTOM_SECRET_KEK_ALLOW_PLAINTEXT=1 escape hatch to explicitly opt into plaintext mode. Customer impact: zero — phantom-installer always generates a fresh KEK at first-install time, so installer flows never hit this path. Only manual deploys are affected.",
      "MCP tool docstring audit closes the v0.3.6 gap: agents don't set parameters that aren't documented even when those parameters exist in the function signature. jobs_create.bypass_approvals (the per-job auto-approve toggle) and jobs_create.action.skill (pin a specific skill to a chat-action job) are both wired through the backend but were absent from the docstring; the agent never set them. v0.3.7 updates both with full descriptions including concrete trigger phrases ('don't ask me each time', 'schedule a daily bruteforce_vpn_to_lateral simulation') so the agent picks them up via standard tool introspection. Same audit deferred to v0.3.8 for api_keys_*, settings_update, instances_delete, providers_delete.",
      "CLAUDE.md gains rule #9 in Documentation discipline: when a UI form field is added to a system-management page, the matching MCP tool's docstring MUST be updated in the same PR. Includes an audit checklist (identify matching tool, confirm field flows through backend, update Args section + example payload + trigger phrases). Prevents the v0.3.6 gap class from returning.",
      "UX: chat approval-mode dropdown now renders BEFORE the operator sends their first message. Pre-v0.3.7 it was gated on sessionId && onApprovalModeChange — meaning the dropdown only appeared after the first turn streamed through (under the default 'manual' mode by then). Operator's pre-session choice is captured in a ref and written to the new session's metadata once the first message creates a session.",
      "UX: deleting a job from the job-details view (/jobs/[id]) now redirects to /jobs automatically. Pre-v0.3.7 the delete handler called router.refresh() regardless of which view it was called from; fine on the list view (row disappears) but on the detail view it left the operator on a 404'd or stale page. New JobActions prop redirectOnDeleteTo lets the detail view opt into the redirect explicitly.",
      "Migration impact: PATCH release. SELECTIVE recreation per the v0.3.0 digest-pinning architecture — only phantom-agent rebuilds (embeds the new cortex-content connector + SecretStore change + UI fixes + manifest update + docstring audit). xlog, caldera, browser, updater retag from v0.3.6 with identical content digests. One operator-action requirement for manual deploys without PHANTOM_SECRET_KEK: either generate a KEK or set PHANTOM_SECRET_KEK_ALLOW_PLAINTEXT=1; installer flows never need this.",
    ],
  },
  {
    version: "0.3.6",
    date: "2026-05-10",
    title:
      "Chat sidebar shows operator sessions again — server-side scheduled-job filter + expression index",
    highlights: [
      "Symptom on bupa-engine: navigating away from the chat page and back showed an empty (or near-empty) session sidebar even with 1500+ operator-driven conversations in history. Live diagnostic against the running stack: 4565 sessions in sessions.db, of which 3059 were scheduled-job-driven (recurring jobs that fire chat dispatch with X-Phantom-Trigger: job:* — chat-route marks them with meta.scheduled_by=<job-name>) and 1506 were operator-driven. The default 50-row fetch was 100% scheduled.",
      "Root cause: the chat page used a client-side post-fetch filter (humanOnly.filter(s => !meta.scheduled_by)) on the default 50-row response. As soon as scheduled-job churn dominated the most recent 50 rows (which happens within hours on a daily-cron install), the filter dropped everything and the sidebar went empty. The localStorage-based ChatSessionProvider was unrelated dead code (zero consumers in the codebase) — actual session state is API-backed via /api/v1/sessions. Bumping the row limit was a shortcut that would only defer the problem; the right fix moves the filter to the SQL layer.",
      "Fix: SqliteSessionStore.list_sessions gains an exclude_scheduled bool param. When true, adds `json_extract(meta_json, '$.scheduled_by') IS NULL` to the WHERE clause — SQLite's JSON1 (bundled in Python's stdlib sqlite3 module) does the per-row pointer evaluation. The cognitive.py route reads exclude_scheduled from query params and forwards. The Next.js listChatSessions client now takes a ListChatSessionsParams object; the chat page calls with excludeScheduled: true on both mount and refresh, and the post-fetch humanOnly.filter shortcut is removed entirely (~12 lines of duplicated code deleted). Same dual-surface pattern jobs/instances/providers already use; chat-sessions was the last surface with a client-side filter shortcut.",
      "Performance: an expression-based index on json_extract(meta_json, '$.scheduled_by') added to the schema in _init_schema(). Without this, the WHERE clause forces a SCAN on sessions — fine at 4K rows, painful at 50K. The index lets SQLite use a range scan that touches only scheduled_by IS NULL rows. CREATE INDEX IF NOT EXISTS is idempotent — runs on first v0.3.6 boot against existing customer databases, ~50ms on a 4565-row table, no downtime/migration script/operator action.",
      "Test coverage: net new bundles/spark/mcp/tests/test_session_store.py with 8 tests — baseline behavior (no filter), user= filter unchanged, exclude_scheduled drops scheduled rows, exclude_scheduled keeps rows with other meta keys (approval_mode, model_override), exclude_scheduled keeps rows with empty/None meta, exclude_scheduled composes with user=, default exclude_scheduled=False preserves old behavior (jobs page, audit views), end-to-end replication of the bupa-engine pathology. Pre-v0.3.6 the bundles/spark/mcp/tests/ folder had NO session_store tests at all despite the store being touched by 7+ code paths — filling that gap was part of the clean fix.",
      "Migration impact: PATCH release. SELECTIVE recreation per the v0.3.0 digest-pinning architecture — only phantom-agent rebuilds; xlog, caldera, browser, updater retag from v0.3.5 with identical content digests. caldera state, xlog streaming workers, browser cache, updater state all preserved. The new schema index runs on first boot in-place; no data migration, no operator action.",
    ],
  },
  {
    version: "0.3.5",
    date: "2026-05-10",
    title:
      "Eliminate phantom_create_*_worker retry-storms — enumerated field whitelist + Strawberry per-field error pass-through + XQL skill polish",
    highlights: [
      "Diagnosed empirically across 13 chat-test sessions: the agent was retrying phantom_create_data_worker / phantom_create_scenario_worker 4-5 times per scenario before landing on a payload the GraphQL schema would accept. Root cause was a chain of three things — (a) the agent couldn't enumerate which rosetta fields exist (only had naming convention strings, not the whitelist), (b) when it occasionally invented a near-miss field like 'sessionState' that doesn't exist (rosetta has session_start, session_end, service_state etc.), the GraphQL response wrapped a 400+ char payload echo around the actionable 'Did you mean' suggestion, so the agent had to binary-search by dropping fields, and (c) the cortex_xql_query_authoring skill went off-script when XSIAM was unconfigured, calling other XSIAM tools that failed with the same root cause. Live probes against rosetta confirmed it has 1169 fields — the fields ARE there, the discovery + error-surfacing chain was broken.",
      "Fix #1: phantom_get_field_info now returns the enumerated whitelist on the no-log_type call. New 'available_fields' block in the response carries the full rosetta field list in both UPPER_SNAKE_CASE form (for required_fields enum) and camelCase form (for observables_dict keys), plus a count. Pre-v0.3.5 the agent had to call again with a specific log_type to get the whitelist (which the test corpus shows it never did), or guess the camelCase transformation. The whitelist on the no-arg call closes the gap.",
      "Fix #2: Strawberry per-field error pass-through in xlog's GraphQL client. Added simplify_strawberry_error() that strips the giant input-echo prefix from wrapped variable validation errors, leaving just the path + actionable detail. BEFORE: 'Variable $steps got invalid value {<400-char echo>} at steps[0].logs[0].observablesDict; Field sessionState is not defined by type WorkerObservablesInput. Did you mean sessionStart, sessionType, serviceState, leaseState, or sessionEnd?' AFTER: 'at steps[0].logs[0].observablesDict: Field sessionState is not defined by type WorkerObservablesInput. Did you mean sessionStart, sessionType, serviceState, leaseState, or sessionEnd?'. Same info, dramatically shorter, suggestion list visible up front. Agent can self-correct in 1 retry instead of 4. Pass-through-safe for non-wrapper errors (flat Pydantic, syntax, network).",
      "Fix #3: removed xsiam_get_xql_doc tool. Bundled xql_doc.md was never actually shipped (resources/ folder didn't exist in the connector source), so the tool only ever returned 'xql_doc.md not found'. The connector.yaml description for the tool already self-deprecated it ('Prefer the generic knowledge_search built-in for new code'). v0.3.1's cortex-docs/xql_lookup is the universal-access replacement (no XSIAM credentials required, public Palo Alto docs API, covers all Cortex products). The cortex_xql_query_authoring skill already routes there.",
      "Fix #4: cortex_xql_query_authoring skill Failure handling table extended with two rows — xsiam_get_datasets returning 'no API key configured' (don't retry via other XSIAM tools; ask the operator for the dataset name; mention XSIAM tools as side note pointing to /providers), and xsiam_get_xql_doc returning 'xql_doc.md not found' (don't call; use cortex-docs/xql_lookup). Catches the e673b6bb failure mode where the agent went off-script and called XSIAM tools that all failed with the same root cause.",
      "Migration impact: PATCH release. SELECTIVE recreation per the v0.3.0 digest-pinning architecture — only phantom-agent rebuilds (embeds the bundled MCP skill text + the xlog connector code + the xsiam connector code); xlog, caldera, browser, updater all retag from v0.3.4 with identical content digests. caldera red-team operation state, xlog streaming workers, browser cache, updater state all preserved. Skills volume retains operator-edited skills via the v0.3.2 marker-driven auto-merge. v0.3.6 will tackle the chat-session-loss bug (sessions disappearing on UI navigation) — separate code area, separate investigation.",
    ],
  },
  {
    version: "0.3.4",
    date: "2026-05-10",
    title:
      "Skills page bug fixes — delete works again + cards show frontmatter displayName",
    highlights: [
      "Bug fix: deleting a skill from /skills no longer fails with 'Unexpected non-whitespace character after JSON at position 2'. Root cause was a parameter-name mismatch between the Phase-11 gated wrapper at usecase/builtin_components/self_mod_tools.py:skills_delete (which was registered with FastMCP and exposed as the connector_loader's bound entrypoint) and the underlying skills_crud.skills_delete function. The wrapper's signature called the parameter 'name'; the underlying function and the legacy MCP Tool inputSchema both expected 'file_path'. FastMCP auto-derives a Pydantic validator from each tool's signature, so when /api/skills DELETE handed the validator the documented `{file_path: ...}` shape, Pydantic rejected it as 'Unexpected keyword argument' and the error string ('2 validation errors for call[skills_delete]...') got returned as the tool's content text. The Next.js side then JSON.parse'd the error string and threw on the literal `2` at byte index 2 — confusing diagnostic, one-line fix. Fix: rename wrapper parameter `name` → `file_path` to match underlying function + legacy schema; add comprehensive comment so this doesn't regress.",
      "Architectural sub-fix exposed by the parameter rename: with the validator no longer rejecting the call, execution reached gate_and_execute() — which then blocked for the gate's default 5-minute timeout waiting on operator approval that never came (operator was clicking Delete on /skills, not visiting /approvals). New error was parseable JSON, but UX was strictly worse than the original — 5-min spinner replacing an instant error. Initial attempt sent X-Phantom-Approval-Bypass: 1 from the Next.js side, relying on the trigger_context middleware to set a contextvar gate_and_execute reads; empirically the contextvar does NOT propagate from Starlette middleware into FastMCP's streamable-HTTP tool dispatcher (suspected cause: FastMCP runs tool dispatch in a child asyncio task whose context was captured before the middleware ran). Cleaner architectural fix: add bundles/spark/mcp/src/api/skills.py with REST endpoints (GET/POST /api/v1/skills, GET/PUT/DELETE /api/v1/skills/{file_path:path}) that call skills_crud directly, bypassing the gated wrapper structurally. Same dual-surface pattern jobs/instances/providers/settings/etc. already use — skills were the last destructive resource without its REST counterpart. Next.js /api/skills DELETE now proxies to /api/v1/skills/<path> via proxyToMcp() instead of calling the MCP tool. Phase-11 gated skills_delete wrapper unchanged in purpose: still catches chat-driven self-mod (its actual reason for existing); REST endpoint carries operator-direct UI traffic. Audit row records actor=user:operator so post-hoc review distinguishes operator-driven from agent-driven activity.",
      "Bug fix: /skills page cards now show the operator-friendly displayName (e.g. 'Cortex XQL query authoring') as the primary card title with the canonical snake_case name (e.g. 'cortex_xql_query_authoring') as a small monospace subtitle below it. Pre-v0.3.4 the SkillCard JSX rendered `skill.name` only — which is the canonical identifier the agent's chat-prompt sees and that skill-binding jobs reference, but it's NOT the operator-friendly label. The displayName has been correctly populated in the MCP's skills_list_all output for several releases (extracted from MD frontmatter `display_name:` field with fallback to first H1, then filename stem) and the page's liveRowToSkillDef mapper assigned it to skill.displayName, but the JSX render never used it — only Download/Delete tooltips and Disable/Enable aria-labels did. Fix: invert the visual emphasis — h3 displays displayName in headline font; canonical name moves to a smaller monospace line under it (still grep-able when troubleshooting 'agent says it can't find the skill X'). The category label moves down one line.",
      "Migration impact: PATCH release. SELECTIVE recreation per the v0.3.0 digest-pinning architecture — phantom-agent rebuilds (it embeds the new api/skills.py REST module + main.py wiring + Next.js proxy refactor + page.tsx displayName fix + the original parameter-rename fix in self_mod_tools.py); xlog, caldera, browser, updater all retag from v0.3.3 with identical content digests. caldera red-team operation state, xlog streaming workers, browser cache, updater state all preserved. In-flight chat sessions are dropped on the phantom-agent recreation but skills + jobs + connectors persist (they're volume-backed).",
    ],
  },
  {
    version: "0.3.3",
    date: "2026-05-10",
    title:
      "reset-ui-password.sh: auto-detect UI_USER from setup.json + prominent username banner before password prompt",
    highlights: [
      "Targeted patch to the password-reset recovery tool. Pre-v0.3.3 the script defaulted to a hardcoded username 'phantom' — fine as a documentation placeholder, wrong for any install whose UI_USER was set to something else during setup wizard. Result was a silent-bug class: reset wrote a hash for 'phantom', login failed for the actual operator (e.g. 'ayman') with 401 because the agent's login route enforces single-user mode by rejecting any username that doesn't match the configured UI_USER BEFORE checking the password hash. Audit event landed for the wrong user; failure looked like a typo. Surfaced during v0.3.2 smoke testing on a real customer-state install (bupa-engine).",
      "Fix: layered username resolution. Order: (1) --user explicit override, (2) UI_USER from /app/runtime/setup.json inside the container — same file the agent's auth code reads, so script + verify path always agree by construction, (3) UI_USER from container env (legacy fallback), (4) hardcoded 'phantom' (last resort, warned about loudly because it almost never matches a real install's configured operator).",
      "Prominent resolved-username banner before password prompt — printed even when --user is passed explicitly, so an operator who mistyped --user gets a chance to abort with Ctrl-C before typing the password. The banner shows username + source (setup.json / env / fallback) + container, plus a hard-warning that the agent's login route enforces UI_USER and any other username 401s before hash check.",
      "Updated success message: now shows resolved username + source + hash file path + audit event name, plus a curl-based diagnostic command isolating browser-cookie issues from real verify-path failures (the same probe pattern I had to construct manually during the v0.3.2 diagnostic).",
      "Updated --help to explain the auto-detect behavior + clarify when --user is needed (almost never).",
      "Updated header docstring with a 'Username resolution (v0.3.3+)' section documenting the resolution order + why pre-v0.3.3 'phantom' was wrong + the architectural reason single-user enforcement happens at the Next.js login route layer (the MCP-side hash store IS multi-user-ready).",
      "Migration impact: NO image rebuilds. The reset script is shipped as (a) a heredoc embedded in the phantom-installer binary, (b) a standalone GH Release asset, (c) a file in the install kit tarball. release.yml regenerates all three with the fixed script. Customers downloading v0.3.3+ get the fix automatically; operators with existing v0.3.x installs can either re-run the v0.3.3 phantom-installer (refreshes /opt/phantom/reset-ui-password.sh) or drop the standalone asset in place. Existing passwords are NOT affected — fix only applies to future invocations of the reset tool.",
      "Selective recreation: v0.3.2 → v0.3.3 hop only regenerates the phantom-installer binary; xlog/caldera/agent/browser/updater all retag from v0.3.2 with identical content digests per the v0.3.0 digest-pinning architecture. Effectively zero-downtime for customer in-memory state.",
    ],
  },
  {
    version: "0.3.2",
    date: "2026-05-10",
    title:
      "Upgrade-ergonomics patch — skills auto-merge per release + FORCE_SKILLS_SYNC wired into customer compose + cortex-docs in /marketplace",
    highlights: [
      "Skills auto-merge: entrypoint.sh §1 now uses a per-release marker file (phantom_mcp_skills/.seeded_version) to drive automatic merges of new image-baked default skills into existing customer volumes. Pre-v0.3.2, new releases' skills never propagated to populated volumes — operators had to docker exec cp -r /app/mcp/skills-default/* /app/skills/ manually after every upgrade. v0.3.2 makes this automatic on first boot of each new release. The merge is still MERGE-not-REPLACE: customer-created skills + retired-but-on-disk legacy skills stay. Operator deletions of default skills stick across same-version restarts; they only re-introduce on the NEXT release upgrade (which is the right semantic — upgrading is opting into the new release's defaults).",
      "FORCE_SKILLS_SYNC=1 finally works on customer installs. v0.2.5 wired the env-var into the dev compose at the repo root, but never propagated to installer/docker-compose.yml. Customers using the documented `FORCE_SKILLS_SYNC=1 docker compose up -d --force-recreate phantom-agent` operator override hit a silent no-op. v0.3.2 adds the bare-name forwarding to the phantom-agent environment: block in the customer compose. With the marker-driven auto-merge above, this override is now rarely needed; primary use case is 'operator deleted a default skill on v0.3.x and wants it back without waiting for the next release'.",
      "cortex-docs connector now surfaces in /marketplace. v0.3.1 shipped the connector inside the bundle, but the marketplace endpoint (mcp/agent/app/api/marketplace/connectors/route.ts) hand-curates a list of 4 hardcoded connectors (xlog, caldera, xsiam, web) and the new entry was missing. v0.3.2 adds the 5th entry — cortex-docs, publisher kite-production, category Security, with full per-tool docs + 3 config fields + setup guide + v0.3.1 changelog. Operators can now find cortex-docs in /marketplace, click 'Add instance', save with defaults (Cortex docs API is public — no required config), and the cortex-docs/* tools advertise on next refresh.",
      "Architectural principle reinforced: connector instances are operator-created via the UI, NOT auto-migrated by the installer. v0.3.2 deliberately does NOT add an env-var auto-migration entry for cortex-docs (an earlier proposal that was walked back). Existing instances are preserved across upgrades; new instances are never created by the upgrade itself. The legacy auto-migration entries on caldera/xsiam/xlog (which auto-create instances from env vars on first boot) are left alone for backward compat but new connectors follow the modern pattern (web in v0.1.27, cortex-docs in v0.3.1) — consistent operator-consent flow: marketplace → install → operator-driven instance creation.",
      "Migration impact — v0.3.1 → v0.3.2: SELECTIVE recreation per the digest-pinning architecture. Only phantom-agent rebuilds (it embeds the entrypoint refactor + marketplace addition); xlog/caldera/browser/updater retain v0.3.1 content digests and keep running with in-memory state intact. Skills auto-merge fires on first boot of v0.3.2 — operator's /skills page populates with anything they were missing from prior releases without losing customer-created ones. cortex-docs becomes findable in /marketplace.",
      "Migration impact — v0.2.x or v0.1.x → v0.3.2: same one-time container recreation as the v0.2.x → v0.3.x boundary in v0.3.0. Volumes preserved. Skills auto-merge fires on first boot — no more docker exec workaround required to see the latest skill set. Operator finds cortex-docs in /marketplace, decides whether to install. See installer/MIGRATION-FROM-V02X.md for the full v0.2.x migration story (still applies; v0.3.2 just makes the post-migration skills experience automatic).",
      "Implementation footprint: 3 files. entrypoint.sh §1 refactored (one-time refactor with comprehensive comments explaining the marker contract). installer/docker-compose.yml gains one env-var line. marketplace route gains one connector entry (109 lines: 6 tools + 3 config fields + setup guide + version history matching the existing xlog/caldera/xsiam/web shape). No image rebuilds beyond phantom-agent are needed; release.yml's conditional rebuild logic retags everything else from v0.3.1 with identical digests, so the v0.3.1 → v0.3.2 hop preserves caldera/xlog/browser/updater in-memory state.",
    ],
  },
  {
    version: "0.3.1",
    date: "2026-05-10",
    title:
      "New cortex-docs connector + cortex_xql_query_authoring skill — Cortex docs lookup for XQL query authoring",
    highlights: [
      "New tool connector: cortex-docs. Wraps four upstream scripts from the operator's cortex-deep-search_sharable skill kit (search.py, fetch_topic.py, xql_lookup.py, research_planner.py — all preserved verbatim under the connector's src/ directory). Six tools exposed under the cortex-docs/ namespace: cortex-docs/search (full-text Cortex docs search across XDR/XSIAM/XSOAR/Cloud/AgentiX/Xpanse/XQL with auto product detection), cortex-docs/suggest (autocomplete), cortex-docs/xql_lookup (focused XQL stage/function lookup with stage-aware ranking heuristics), cortex-docs/fetch_topic (full topic content), cortex-docs/fetch_toc (publication TOC), cortex-docs/deep_research (heavyweight 1-3min multi-section research planner — reserve for whitepapers, partner briefings, migration guides, NOT for query authoring).",
      "Connector is module-style (in-process Python). The upstream scripts are stdlib-only (urllib + json + re), so zero extra Python deps and no daemon needed. The connector layer adds a thin SystemExit-translation wrapper so the upstream scripts' sys.exit(1) HTTP-error paths produce structured {ok: false, error} returns instead of taking down phantom-agent on a transient docs-API blip. 15 unit tests cover the wrapper contract; live-API smoke during development returned canonical dedup/filter/arrayindexof topics with full URLs in <2 seconds.",
      "New foundation skill: cortex_xql_query_authoring. Six-step workflow that bridges the operator's internal example-query KB with Palo Alto's official Cortex docs: (1) restate query intent, (2) embedding-search operator KB for ~5 similar examples, (3) extract stages/functions from those examples, (4) call cortex-docs/xql_lookup per stage/function (parallelized when supported), (5) author the query using KB examples as pattern prior + cortex-docs lookups as syntax reference, (6) emit with per-stage/function citations. The skill is also clear about what it doesn't do — when no KB examples exist, it tells the operator and offers an explicit cortex-docs/deep_research follow-up rather than firing it on the default path (wall-clock cost).",
      "Required no configuration: the Cortex docs API is public, no credentials. Optional plannerModel config flows through to cortex-docs/deep_research's LLM-driven planner; absent ANTHROPIC_API_KEY the planner falls back to its built-in heuristic plan and works fully offline-of-LLM. Required: false in the bundle manifest — agent functions without cortex-docs (query authoring falls back to operator-KB-only mode with a confidence note).",
      "First release that exercises the v0.3.0 digest-pinning pipeline for a brand-new connector image. release.yml's per-connector image build matrix gained phantom-connector-cortex-docs; the manifest gained DIGEST_PHANTOM_CONNECTOR_CORTEX_DOCS; the customer compose forwards the new digest to phantom-updater. Customers upgrading v0.3.0 → v0.3.1 see SELECTIVE recreation: phantom-agent (which embeds the new connector code + skill) is the only stack-tier service that recreates; xlog, caldera, browser, updater retain their content digests and keep running with in-memory state intact. The architecture pays off on the very next connector we add.",
      "Operator visibility: cortex-docs surfaces in /observability/connectors via the standard connector state-machine integration. Each cortex_search and cortex_xql_lookup invocation appears in the live tool-call log; the digest-pinning panel above the connectors list now shows phantom-connector-cortex-docs alongside the other 4 per-instance connector images.",
      "Upstream source preservation: the scripts in /Users/ayman/Documents/Coding/myworkassistant/cortex-deep-search_sharable/ are NOT modified. The connector keeps a verbatim copy under bundles/spark/connectors/cortex-docs/src/, so future upstream re-syncs are a `cp -f` away. The bundled references (output_schema.md, planning_prompts.md, xql_lookup.md) are also copied alongside the scripts for in-skill citation.",
    ],
  },
  {
    version: "0.3.0",
    date: "2026-05-10",
    title:
      "Image digest pinning — content-aware container recreation. Major release; new installer required.",
    breaking: true,
    highlights: [
      "MAJOR (breaking change): v0.3.0 replaces tag-based image references with content-digest pinning across the entire customer stack. Each `image:` line in the customer compose changes from `image: ghcr.io/.../svc:${PHANTOM_VERSION}` to `image: ghcr.io/.../svc@${DIGEST_PHANTOM_<SVC>}`. Container recreation now tracks IMAGE CONTENT (sha256), not version label — caldera retains in-memory red-team operation state, xlog retains streaming workers, phantom-agent retains in-flight chat sessions across upgrades that don't change the affected service's source. Pre-v0.2.x had every release recreate all 5 containers (because the version-tag string changed even when retagged from the previous version's same-byte image); v0.3.0+ recreates only services whose digest actually moved.",
      "Customer-facing flow: download the v0.3.x phantom-installer binary from the GitHub Release for the version you want to install. Each binary is SEALED to one version (the digest manifest is embedded at build time), so to install vN you download the vN binary. The `--upgrade-to N.N.N` flag now errors out if N.N.N doesn't match the binary's stamp — operators hit a clear message pointing at the right binary download. Pre-v0.3.0 phantom-installer binaries CANNOT install or upgrade to v0.3.0+; the migration is a one-way step.",
      "v0.2.x → v0.3.0 migration: ONE-TIME recreation of all 5 containers (the compose file's image-ref shape changes from tag-based to digest-based, so docker compose treats every service as a spec change). Volumes preserved (operator data, secrets store, KEK, GHCR token, on-disk caldera + xlog state). In-memory state lost during this single hop — caldera red-team operations, xlog streaming workers, in-flight chat sessions. Subsequent v0.3.x → v0.3.x+1 upgrades retain in-memory state for unchanged services. The phantom-installer detects the v0.2.x state automatically and prints an explicit migration banner; see installer/MIGRATION-FROM-V02X.md for the full step-by-step.",
      "The release manifest: each release publishes release-manifest-vX.Y.Z.env as a GitHub Release asset, listing PHANTOM_VERSION + 10 DIGEST_PHANTOM_* keys (5 stack services + 5 per-instance connector images). Same content is embedded into the phantom-installer binary at build time so installs are fully self-contained — no runtime fetch from GitHub Releases needed. The Release asset exists separately so phantom-updater can fetch it during in-app upgrades and external automation can pin programmatically.",
      "Phantom-updater redesigned: the in-app 'Update now' button now drives a manifest-based upgrade flow. Resolves target via GitHub Releases API → fetches release-manifest-vTARGET.env → compares each service's current digest vs target → pulls only changed images by digest → applies manifest to /host/.env → docker compose up -d --no-deps <changed services>. Compose sees the new digests as spec changes for the affected services only; selective recreation is automatic. Per-instance connector containers also use digest pinning (fail-loud tag-fallback for diagnostic visibility).",
      "Operator visibility: /observability/connectors gains an 'Image digests' panel with two sub-tables — 5 stack-tier service rows (digest/legacy badge + 12-char-truncated digest with full-digest tooltip) and per-instance connector rows. The /api/agent/version endpoint now returns an optional `digests` map (backward-compatible: pre-v0.3.0 callers reading only .version still work). New /api/agent/digests endpoint returns the comprehensive view: stack-tier digests + per-instance connector digests proxied to phantom-updater. About modal's release-history view shows the running version + an 'Image versions' expandable.",
      "Bundled fixes from the unreleased v0.2.5 (these were prepared during the v0.2.4→v0.2.5 cycle but never tagged independently — they ship under v0.3.0): FORCE_SKILLS_SYNC=1 now actually flows through to the container (was a documented-but-broken no-op since v0.1.33 because the variable was declared in entrypoint.sh but missing from the compose environment: block); .env.vm cleanup (the multi-line GOOGLE_APPLICATION_CREDENTIALS JSON pattern documented as the canonical Google Cloud SDK path-reference form); VM_REMOTE_REPO documented to point at the runner workspace; CLAUDE.md approval-gates table making 'build = no approval, smoke test = no approval, release tag = yes approval' explicit; canonical IAP tunnel port mappings with +1 offset (3000→3001, MCP 8080→8081, Caldera 8888→8889, xlog 8999→9000); enterprise-discipline mandates in CLAUDE.md (pre-build context refresh, quality-first principle, observability verification during smoke test).",
      "Architecture: the new /help/architecture#image-pinning section is the canonical spec for digest pinning — covers the manifest, install/upgrade flow, per-instance connector pinning, and operator visibility. The CLAUDE.md 'Image digest pinning contract' section documents the dev/customer compose split (repo-root docker-compose.yml uses tag-based :local refs for build.yml deploy-compose; installer/docker-compose.yml uses digest refs for customer installs) and lists the 'must update together' files — anyone touching image-pinning code in one file should expect to update the others.",
      "Implementation: 8 files in the digest-pinning core (release.yml + installer template + compose + build script + updater main.py + agent /api/agent/{version,digests} routes + observability/connectors page) for 1,560 insertions / 204 deletions. Plus this release's docs touch CLAUDE.md, CHANGELOG.md, release-notes.ts, the architecture page, .env.example, MIGRATION-FROM-V02X.md, the user guide, and journeys.ts. End-to-end change with no follow-up debt — partial digest pinning would be worse than no digest pinning, so v0.3.0 ships the full architecture.",
    ],
  },
  {
    version: "0.2.4",
    date: "2026-05-10",
    title:
      "Skill-catalog curation — bootstrap_dataset_fields + 12 stale skills retired + display names refreshed + analytics-rules audit + 2 new standalone scenarios (port_scan_detection, large_file_upload_exfil)",
    highlights: [
      "New: foundation/bootstrap_dataset_fields utility skill. Solves XSIAM's chicken-and-egg problem: you cannot model or field-map a dataset that has never received data. Configuring an XSIAM ingestion broker for vendor_proofpoint_tap_raw and immediately opening the field-mapping UI shows nothing — XSIAM hasn't seen any rows yet. The skill seeds each dataset in the operator's stack with ~100 events containing the maximum relevant set of fields from xlog's catalog. After running, every dataset has populated rows with realistic field shapes; field-mapping work can proceed.",
      "Bootstrap skill mechanics: reads phantom_get_technology_stack, picks a curated field template per data-source class (firewall, EDR, NDR, proxy, email-gateway, DNS, WAF, load-balancer, VPN, cloud, SaaS), fires xlog.create_data_worker once per stack entry — count: 100, interval: 0.1, duration_seconds: 10. All workers in parallel; total wall-clock ~10 seconds regardless of stack size. For a 13-source stack: 1,300 events covering 13 datasets in 10 seconds.",
      "Field templates are starting opinions, not hard rules. Operators can edit any class's field set via /skills → Save (the skill MD lives at /app/skills/foundation/bootstrap_dataset_fields.md); the agent picks up the change on next invocation. If a class isn't covered (operator has a stack class outside the templates), the agent falls back to a minimal-fields recipe and surfaces a warning at the end.",
      "Skill catalog curation — image-baked list trimmed from 21 to 13. Kept set: 10 v0.2.2 vendor-agnostic attack-scenario skills + the new bootstrap_dataset_fields utility + 2 new standalone analytics-rules-coverage scenarios (port_scan_detection, large_file_upload_exfil). Retired: 7 pre-v0.1.33 evocatively-named scenarios (alpha_and_omega, crossroads, everything_is_now, ink_and_foil, knock_knock, midnight_butterfly, sic_mundus_creatus_est), 2 foundation stubs (create_device_topology, generate_shared_iocs — 270-byte placeholders), 2 validation skills (xsiam_top20_coverage and validate_ioc_correlation — superseded by per-skill rule-trigger tables in the v0.2.2 batch), 1 aspirational workflow (purple_team_exercise).",
      "Analytics-rules audit — network 5-tuple baseline backfilled across every kept network-relevant stage. Operator feedback after running through XSIAM analytics rules: 'the minimum I should see in any network event is source IP, source port, protocol, user, hostname when those make sense for the data source class.' The v0.2.2 batch had src_ip + dst_ip + dst_port populated in most stages but was missing src_port and/or protocol in some — common omission because synthetic data still parses, but it weakens correlation queries. v0.2.4 audits all 10 v0.2.2 scenarios + the bootstrap field templates and backfills. Stages updated: dns_tunneling_c2 (Stages 1+2), phishing_to_cloud_takeover (Stage 2 proxy), web_app_to_webshell_to_exfil (Stages 1+2 WAF), recon_to_account_probe (Stage 3 WAF), insider_saas_data_exfil (Stage 3 firewall), bootstrap_dataset_fields (DNS, WAF, load-balancer templates).",
      "New: scenarios/port_scan_detection — three-pattern reconnaissance skill focused exclusively on port-scan detection. Stage 1: horizontal scan (one source → many internal IPs on the same port — the 'find all SSH boxes' sweep). Stage 2: vertical scan (one source → one internal IP across many ports — port enumeration). Stage 3: distributed scan (many sources → many destinations on common service ports — slow stealth scan). Each stage emits firewall events with the full 5-tuple plus optional WAF events for layer-7-visible probes. Triggers Port Scan Detection (single-source variant), Port Scan Vertical, Distributed Port Scan rules. ~600 events in ~3 minutes wall-clock.",
      "New: scenarios/large_file_upload_exfil — three-pattern exfiltration skill focused on large outbound uploads. Stage 1: workstation → file-sharing service bulk upload (proxy-visible HTTPS). Stage 2: server → file-sharing service bulk upload (anomalous direction — web servers should rarely initiate outbound to personal cloud). Stage 3: SaaS bulk-download → personal-cloud re-upload (M365 OneDrive download then Dropbox upload from same workstation). Each stage emits proxy + firewall events with bytes_sent in the 5-50 MB range, category: file-sharing, dropbox.com/drive.google.com destinations. Triggers Data Exfiltration to Personal Cloud Storage (Rule #20), Anomalous Outbound Volume from Server, Bulk SaaS Download Pattern.",
      "Display names refreshed across all kept skills to 2-4 word human-readable phrases. 'Brute force → VPN compromise → Lateral movement' becomes 'VPN brute force chain'; 'Phishing → Credential harvest → Cloud takeover' becomes 'Phishing cloud takeover'; etc. The model-facing canonical name (snake_case file basename) stays the same — that's what the agent's chat-prompt sees and what skill-binding jobs reference. Only the human-facing UI label changes; refresh is automatic on upgrade.",
      "Migration impact: fresh installs (v0.2.4+) ship 13 skills total, all realistic for current xlog. Existing installs upgrading retain whatever's seeded in their phantom_mcp_skills named volume — deletions don't auto-remove from populated volumes. Operators wanting a clean slate: docker compose down -v (destructive), surgical docker exec rm of specific old skills, or FORCE_SKILLS_SYNC=1 (merge — adds new templates but doesn't remove files not in the image; old scenarios stay unless explicitly removed).",
    ],
  },
  {
    version: "0.2.3",
    date: "2026-05-09",
    title:
      "Truncation fix — maxOutputTokens cap removed entirely; new wire-event trace export",
    highlights: [
      "Truncation fix — maxOutputTokens cap removed entirely. The chat handler hardcoded `maxOutputTokens: 4096` on every Gemini API call (three callsites in app/api/chat/route.ts). Gemini 3.1 Pro Preview's natural output ceiling is 65,536 tokens — Phantom was capping at 6.25% of that. Multi-step responses with rich tool-output narration (the v0.1.36 backup/restore plans, the v0.2.2 attack-chain skill executions, anything with multiple stages of explanation) routinely hit the cap mid-sentence. v0.2.3 removes the cap entirely at all three callsites — Gemini now decides its own output length, same as the working Trevor_-_Bot Slack integration that uses the same MCP server.",
      "Context-budget reservation (`reservedOutput` in the chat route, used to trim INPUT context to leave room for output) bumps from 4096 to 65536 to match the model's natural ceiling. INPUT-side accounting (how much context we trim to fit), NOT an output cap. Gemini still writes as much as the response needs.",
      "v0.1.28 raised the tool-result REPLAY ceiling from 500 bytes to 1 MiB — INPUT-side concern. The OUTPUT-side maxOutputTokens cap was never touched in v0.1.28 and is what bit operators on multi-stage skill executions. v0.2.3 closes the symmetry.",
      "Wire-event trace export (new) — operator complaint: the live telemetry panel shows wire events (tool_call, tool_result, meta, model) but the existing markdown/json/yaml exports only contain persisted message turns. v0.2.3 adds a new `events` format to /api/v1/sessions/{id}/export that derives a flat event-list timeline from messages + meta — same data the live telemetry panel reconstructs after a session reload, exposed as JSON. Includes user_message, assistant_text, tool_call, tool_result events with timestamps + meta.",
      "Streaming-only events (text_delta chunks, cache_hit details, turn_cost, done) are NOT included in the trace export — those are SSE-stream-only and never persisted. For those, capture from the live SSE stream during execution. Documented in the export's payload note field.",
      "UI plumbing — the chat-header export dropdown now shows two sections: \"Session transcript\" (yaml/json/markdown, existing behavior) and \"Wire-event trace\" (Events JSON, new). Same divider + section-header pattern in the session-sidebar per-session menu. Downloaded file lands as session-<id>.events.json so it's distinguishable from the full-session JSON export at a glance.",
      "Internal lesson — the cap was an artifact of pre-Vertex-cache-era constraints. Predates v0.1.7's cachedContent.create() and v0.1.25's 429 backoff — the days when every output token was a full per-call cost concern. With prefix caching, multi-MB tool replays, and 1M-token context windows on modern Gemini models, that cap solved a problem no longer load-bearing.",
    ],
  },
  {
    version: "0.2.2",
    date: "2026-05-09",
    title:
      "Scenario-skill overhaul — 10 new vendor-agnostic, field-specific attack-simulation skills replacing the v0.1.33 advanced batch",
    highlights: [
      "Replaces the 12 v0.1.33 advanced attack-scenario skills (`ransomware_double_extortion`, `apt_long_dwell_espionage`, `business_email_compromise`, etc.) with 10 new skills designed to match xlog's actual vendor/product/observable inventory. The v0.1.33 batch was aspirationally sophisticated — encoding chains the platform couldn't realistically simulate end-to-end. v0.2.2's replacements are realistic for current xlog, vendor-agnostic in their language, and field-specific in their recipes.",
      "Vendor-agnostic body language — skills speak data-source CLASSES (firewall, EDR, NDR, proxy, email-gateway, DNS, WAF, VPN, SaaS, cloud) and resolve to the operator's actual vendor/product at runtime via `phantom_get_technology_stack`. Same skill works on any customer stack — Palo Alto + F5 + Vectra + MDE on one deployment, CrowdStrike + Fortinet + ExtraHop + Defender on the next, no skill-body changes needed.",
      "Field-specific recipes — every stage names exact xlog field keys (from the 1,169-field catalog) populated with realistic values that fire the targeted XSIAM analytics rules. Each stage carries a 'Field semantics' block explaining WHY each field matters and what value range fires the analytic.",
      "10 new skills, total ~3,010 lines of structured runbook content: bruteforce_vpn_to_lateral, phishing_to_cloud_takeover, dns_tunneling_c2, web_app_to_webshell_to_exfil, malicious_email_to_endpoint_persistence, oauth_consent_to_cloud_pivot, lolbin_lateral_movement, recon_to_account_probe, insider_saas_data_exfil, cloud_privilege_escalation. Each triggers 2-6 XSIAM analytics rules; together they cover all 20 rules in xsiam_top20_coverage.",
      "Format scaffolding — every skill includes: pre-flight (call `phantom_get_technology_stack` once, build category lookup), narrative thread (shared IPs/hosts/users/sessions across all stages so analysts can pivot end-to-end), per-stage verification, 'If missing from stack' graceful degradation, tear-down (`xlog.list_workers` + `kill_worker`), and adapting-per-deployment footer.",
      "What stays untouched: the 7 pre-v0.1.33 evocatively-named scenarios (alpha_and_omega, crossroads, everything_is_now, ink_and_foil, knock_knock, midnight_butterfly, sic_mundus_creatus_est) remain — they're operator-known names and weren't part of the batch the overhaul targeted. The validation/xsiam_top20_coverage skill stays at its v0.1.33 form; refreshing it to point at the new vendor-agnostic recipes is queued for follow-up.",
      "Migration: fresh installs (v0.2.2+) ship 22 skills total in the image (24 - 12 + 10), all realistic for current xlog. Existing installs upgrading retain whatever was originally seeded in their phantom_mcp_skills volume; the 12 v0.1.33 deletions don't auto-remove from populated volumes. Operators who want a clean slate can `docker compose down -v` (drops volume — destructive) or `docker exec phantom_agent rm /app/skills/scenarios/<file>.md` for surgical removal.",
    ],
  },
  {
    version: "0.2.1",
    date: "2026-05-09",
    title:
      "Recovery tool self-heal — agent endpoint + UI download + installer GH-release fallback",
    highlights: [
      "Closes the v0.1.34 → v0.1.36 upgrade-path gap: customers using an OLDER phantom-installer binary with `--upgrade-to 0.1.36` got every container-side v0.1.36 feature (backup/restore, sidebar reorg, connector refactor) but did NOT get the new reset-ui-password.sh recovery tool on disk because their old installer's template doesn't have the heredoc block. v0.2.1 makes that recoverable in three layered ways without forcing a fresh installer download.",
      "Layer 1 — agent image bakes the recovery tool. Dockerfile now includes `COPY installer/reset-ui-password.sh /app/tools/reset-ui-password.sh`, and a new auth-gated route `GET /api/agent/recovery/reset-ui-password` serves the bytes. Any customer who upgrades the agent image to v0.2.1+ via any path gets this endpoint, including those running `phantom-installer --upgrade-to` with their old v0.1.34 binary.",
      "Layer 2 — UI affordance. /settings/backup-restore grew a Recovery tools section with a Download reset-ui-password.sh button. One click downloads the script; the page shows the `install -m 755 reset-ui-password.sh /opt/phantom/` one-liner so operators land it correctly. No installer re-download required.",
      "Layer 3 — installer template self-check. After the heredoc extraction, the v0.2.1+ installer checks the script is present + non-empty + not a leftover `__INSTALLER_RESET_PASSWORD_SH__` placeholder. If any of those fail, it curls the script from the GitHub release for the version being installed (`https://github.com/.../releases/download/v<VER>/reset-ui-password.sh`). Future-looking insurance against any template change that accidentally breaks the heredoc — auto-heals from the release without operator action. Air-gapped install? curl fails, operator gets a clear pointer at the in-product UI fallback (which doesn't need external network).",
      "Standalone release asset. release.yml now uploads reset-ui-password.sh + .sha256 as GitHub Release assets alongside the existing 4 installer artifacts. Direct wget path: `curl -L -o reset-ui-password.sh https://github.com/.../releases/download/v0.2.1/reset-ui-password.sh && sudo install -m 755 reset-ui-password.sh /opt/phantom/`",
      "v0.1.34 → v0.1.36 customers: upgrade further to v0.2.1 (any path), then visit Settings → Backup & Restore → Recovery tools → Download. One click + `sudo install -m 755 ...` lands them with a working recovery tool. No need to re-download the phantom-installer binary.",
    ],
  },
  {
    version: "0.1.36",
    date: "2026-05-09",
    title:
      "Backup & Restore + admin-page reorg + caldera/xsiam InstanceStore refactor + forgot-password CLI + drift check",
    highlights: [
      "Backup & Restore (`/settings/backup-restore`) — a single Download button produces phantom-backup-<timestamp>.zip carrying the deployment's complete operator-owned state: personality blob, connector instances + cleartext secrets (so the destination's PHANTOM_SECRET_KEK can re-encrypt on restore), runtime job definitions, memory entries (without dim-bound embedding BLOBs — the destination re-embeds), all skill MD files preserving category structure, and knowledge bundle docs for reference. The Restore flow is two-step: upload zip → preview manifest + section counts via dry_run=true → click Apply. Restore order is dependency-aware: personality → instances+secrets → skills → memory → knowledge (no-op, image-baked) → jobs (last, so runtime jobs referencing connector tools have their instances enabled by then).",
      "Backup security model: cleartext secrets in the zip are intentional — the operator's PHANTOM_SECRET_KEK doesn't need to match across deployments because the destination re-encrypts under its own KEK on write. The manifest carries an explicit warning, the UI surfaces it next to the Download button. 100 MB upload cap on restore (size check before parsing). Auth-gated via the phantom_auth cookie; the MCP-side cleartext secret read path is bearer-gated `/api/v1/instances?include_secrets=true`, mirroring v0.1.34's ProviderStore detail-endpoint pattern. Restore is upsert-or-skip by default (Personality always overwrites; everything else preserves existing entries unless ?force=true).",
      "Backup is fault-tolerant per-section: a failing MCP endpoint emits a `backup_warnings[]` entry in the manifest rather than killing the whole backup. Restore's dry_run mode lets operators preview the plan without writing anything, and the response shape (`{applied: {section: count}, skipped: {...}, errors: [...], warnings: [...]}`) makes partial-restore outcomes easy to diagnose.",
      "Sidebar reorganization — Models + Providers + Backup & Restore consolidated under the **Settings** group. Pre-v0.1.36 the **Command** group held a mix of \"every-session\" surfaces (Chat, Skills, Memory, Knowledge, Jobs) and \"once-and-rarely-touch\" admin surfaces (Models, Providers); the mental-model split was wrong. After: Command holds the day-to-day actions; Settings holds Services, Models, Providers, Personality, Backup & Restore. No backend changes — sidebar's findActiveGroupId walker handles the move automatically.",
      "Connector tool-call refactor — caldera + xsiam join xlog on the InstanceStore-backed pattern. v0.1.34 brought xlog onto single-source-of-truth (lifespan resolver, no env fallback, no probe-then-flip), but caldera + xsiam shipped that release \"partially conformed\" — probes used InstanceStore correctly, tool-call code still imported `from config.config import get_config` and read env-driven pydantic settings. v0.1.36 closes that gap. Caldera's connector.py grew a single-chokepoint `_get_caldera_config()` helper that runs on every `_caldera_request()`; all ~30 caldera tools transparently migrate. XSIAM's connector.py grew a parallel `_get_xsiam_config()` used by the PAPI fetcher (every `xql.*` + `get_issues` + `get_endpoint_alerts` tool), the `xsoar_command` tool (playgroundId), and the `send_webhook_log` tool (webhookEndpoint + webhookKey). All three callsites of the deleted `get_config()` import migrated. Net effect: a `/connectors` edit on caldera baseUrl/apiKey, or any of the six xsiam fields, propagates to the next tool call immediately — no MCP restart, no env-var stamping, no probe-vs-tool-call divergence.",
      "Visible side effect for misconfigured deployments: the new resolvers raise rather than fall back to env. A deployment that was quietly running on env-driven config without a populated InstanceStore now surfaces as `caldera instance has no apiKey configured` (or the xsiam equivalent) on first tool call. The fix is to populate the instance via `/connectors`, which is the spec — but it's a visible change for anyone who never went through the setup form for those connectors. Same principle as v0.1.34's retirement of setup.json: no silent self-healing, the gap surfaces explicitly so it can be fixed at the source.",
      "Forgot-UI-password CLI shipped in the install kit. `reset-ui-password.sh` is a small shell script alongside `phantom-installer` — run it on the VM where the stack lives, it prompts for username + new password (interactively, with confirmation, no echo) or accepts --username + --password-file for non-interactive use. Reads MCP_TOKEN from the running phantom_agent container's /proc/1/environ via `docker exec` (so the operator never has to know it). POSTs to MCP /api/v1/ui/auth/password with the JSON body piped via stdin (--data-binary @-) so the password never appears on the command line. Recovery from a forgotten password no longer requires `docker compose down -v` (which would also wipe job history, audit log, instance configs) or manual SQLite surgery. Documentation lands in /help/user as Scenario 3d.",
      "VM compose drift check (pre-deploy gate, MANDATORY for contributors). The v0.1.34 TLS smoke test caught a stale VM compose by accident — docker-compose.yml on phantom-vm had drifted from the canonical local file by weeks, xlog and caldera lacked the /tls volume mount despite the local file having it, `docker compose up -d --force-recreate` didn't help because the VM's spec was stale. `scripts/check-vm-compose.sh` makes the check explicit: opens an IAP tunnel, fetches the remote compose via SSH, `cmp -s` against the local file, exit 0 if identical, exit 1 with a unified diff if drifted. CLAUDE.md's pre-deploy gate now mandates running this script before any tar+scp sync to the VM, alongside the existing tsc --noEmit + npm run lint + npm run build gate. Plus a sync-hygiene note: COPYFILE_DISABLE=1 tar --no-xattrs ... so AppleDouble sidecars (`._<filename>`) don't pollute VM hash audits.",
      "Architecture page at /help/architecture#connector-state updated to reflect the completed state — caldera + xsiam tool-call paths are now documented as InstanceStore-backed alongside xlog, with the deferred-from-v0.1.34 paragraph removed. Four new operator journeys land in journeys.ts: ops-edit-caldera-via-connectors-v0135, ops-edit-xsiam-via-connectors-v0135, ops-reset-ui-password-cli-v0135, and ops-backup-restore-roundtrip-v0136.",
    ],
  },
  {
    version: "0.1.34",
    date: "2026-05-09",
    title: "Setup architecture refactor — ProviderStore + InstanceStore + flag file replace setup.json",
    highlights: [
      "Setup architecture refactor — the headline change. setup.json is no longer the master store for operator-typed credentials. Each input now lives in its canonical home: UI password → SecretStore /ui/auth/<user>/password_hash (PBKDF2-HMAC-SHA256). Vertex provider → ProviderStore (config + serviceAccountJson). Connector configs → InstanceStore. TLS material → /tls/cert.pem + /tls/key.pem on the shared volume. Setup-completed flag → /app/runtime/.setup_complete (presence-only marker). writeRuntimeSetup, serializeEnv, and .env.generated are deleted — no code path writes them anymore. Legacy installs auto-migrate: the first isSetupRequired call after upgrade reads the legacy setupComplete:true field and writes the new flag file in its place. /help/architecture#setup-wiring is the canonical specification; CLAUDE.md mandates checking it before any change to setup-adjacent code.",
      "/providers page goes direct to ProviderStore. GET calls MCP /api/v1/providers?provider_id=vertex, returns Project ID + Region in cleartext and the service-account JSON as the *** redaction sentinel. PUT calls MCP PUT /api/v1/providers/{id} for partial updates (or POST to create the primary-vertex instance on first save). Untouched secret slots round-trip as *** and are preserved server-side. The 30-second cache on chat-handler-side vertex-cred resolution is invalidated on every successful PUT, so updates take effect within milliseconds. Two operator-visible bugs from earlier in v0.1.34 are resolved by the refactor: 'UI_PASSWORD is required' on Save (writeRuntimeSetup is gone), and the read-only JSON textarea (readOnly attribute removed, onChange strips bullets on type/paste).",
      "Plugin-contributed skills. Skills installed via plugin packages live under bundles/spark/mcp/skills/plugins/<vendor>/*.md and surface in /skills under a new \"Plugins\" filter pill. Vendor-qualified canonical names (<vendor>.<skill-name>) so two plugins with the same short name don't collide. Path is authoritative — even if the plugin's frontmatter declares category: foundation, the skill buckets under Plugins.",
      "Skills page polish. Total / Enabled / Categories widgets are now derived live from /api/skills (pre-fix were hardcoded {total: 11} and quietly wrong as the on-disk count drifted). New \"Import skill\" button next to Create. Removed the Production-Cluster-Alpha workspace selector that belonged to Spark workspaces, not a single-instance Phantom agent. Skill detail panel auto-loads body on open with a 3-state machine (loading/loaded/error) so the loading shell doesn't flash on cached re-opens.",
      "Help pages use the screen. /help/architecture and /help/user lifted from max-w-[920px]/max-w-3xl to max-w-[1400px] with px-10 padding. Sidebar fonts bumped, page heading text-base → text-xl. New collapsible nav rail with chevron toggle and per-page localStorage state. Stays on the same page when collapsed.",
      "Single-shot setup. /setup is now first-install-only. Page renders when no setup-completed flag; POST /api/setup returns 409 if the flag exists. No merge semantics, no dirty tracking, no re-run path. Post-install edits live in /profile (UI password), /providers (Vertex), /connectors (instance configs).",
      "Pre-deploy gate codified. v0.1.33 shipped a Next.js Route contract violation that passed tsc + lint but failed next build. CLAUDE.md now mandates ALL THREE (tsc + lint + build) before sync-to-VM. Companion fix: chat detects placeholder Vertex credentials (client_email: \"REPLACE_WITH_...\", template private_key) before they hit Node's PEM decoder; operator sees \"Credentials look like a template — replace with a real GCP service account key in Settings → Providers\" in job-run-failed notifications instead of a decoder traceback every five minutes.",
      "TLS smoke test on phantom-vm surfaced + fixed a deployment-only gotcha: when docker-compose.yml adds a volume mount to a service, plain docker compose up -d keeps existing containers and silently skips the new mount. Required force-recreate to attach. After sync + force-recreate, all three services on TLS, cert consistent across /tls mounts, agent → xlog over HTTPS works end-to-end via the connector.",
      "Connector URL resolution refactor: same single-source-of-truth principle the setup refactor applied to providers, now extended to xlog connector URLs. Operators edit baseUrl via /connectors → InstanceStore updated → next tool call, next health probe, next /api/agent/reports proxy all read the new value. Three workarounds removed: entrypoint.sh probe-then-flip on XLOG_URL (silently mutated process env), connector_probes.py probe-then-flip on xlog (silently retried with opposite scheme), and runtime-config's process.env.XLOG_URL primary read (env was the source of truth, not InstanceStore). All replaced with InstanceStore reads. Caldera + xsiam tool-call paths still env-driven; refactoring those is v0.1.35 follow-up.",
      "Test Connection actually tests now. Pre-fix the /providers page Test button POSTed to /api/agent/providers/vertex/test which didn't exist; the page interpreted the 404 as soft-success 'Saved — validated at chat runtime' and placeholder JSON got a green badge. New route does real OAuth2 token exchange via google-auth-library against oauth2.googleapis.com — Google's verbatim error passes through (invalid_grant, etc.), only local OpenSSL PEM-decode failures get a translated 'JSON key invalid' message per operator preference. Caldera probe upgraded from unauthenticated GET / to authenticated GET /api/v2/health with KEY header — wrong API keys now caught at probe time, not first tool call.",
      "Sign-out + bfcache hardening (security): pre-fix, clicking browser Back after Sign-out restored the cached authenticated page from the browser's back-forward cache (bfcache) with stale React state, letting operators see their old profile / providers / etc. content even though the cookie was cleared server-side. AuthGate now listens for pageshow with event.persisted=true (bfcache restore) and visibilitychange (tab return), forces state reset + re-validation. /api/auth/status and /api/auth/logout responses carry Cache-Control: no-store, no-cache, must-revalidate, private. AuthGate's status fetch uses cache: 'no-store'. Defense in depth: server says don't cache, browser is told not to cache, React component re-validates on bfcache restore.",
    ],
  },
  {
    version: "0.1.33",
    date: "2026-05-09",
    title: "Skills overhaul — YAML frontmatter, full CRUD, chat-aware, job binding",
    highlights: [
      "YAML frontmatter is now the metadata source of truth for skills. Every skill MD starts with a ---delimited block carrying name, displayName, category, description, icon, source, loadingMode, locked, and ATT&CK tactics. Backend parses it on every skills_list_all call; /api/skills returns the rich shape; the skills page fetches live and replaces its hardcoded fallback. New MDs added to disk now appear in the UI automatically — no more drift from skills landing on disk but not in the page array.",
      "Full CRUD from /skills. The detail panel grew Download (live MD as .md), Save (textarea edits via PUT /api/skills — backend writes a .md.bak first), and Delete (soft-delete to /app/skills/.deleted/). Locked skills (locked: true frontmatter) render Delete as disabled. Footer Create Skill button now actually creates: display name auto-derives the filename, category dropdown is the four valid values, Submit composes minimal frontmatter and POSTs. UI-driven CRUD lands on the volume immediately — no FORCE_SKILLS_SYNC, no container restart.",
      "Chat agent is skill-aware. Every chat turn's system prompt includes an ## AVAILABLE SKILLS block listing every installed skill's name, displayName, category, description, ATT&CK tactics. ~2-3KB total for 23 skills (vs ~50-150KB if we shipped bodies). The model picks a skill by intent and calls skills_read to pull the full body when applying it. Implementation: lib/skills-registry.ts + lib/system-prompt.ts::renderSkillsBlock.",
      "Jobs can bind to a specific skill. Prompt-action jobs grew an optional Skill dropdown in /jobs/new. Default \"Let agent decide\" preserves old behavior (model picks). Picking a specific skill makes the run deterministic — the scheduler resolves the MD body at fire time and prepends it to the prompt inside <skill name=\"…\">…</skill> tags. Useful for reproducible scheduled exercises that should always run the same runbook regardless of model drift.",
      "Every scheduled job run now publishes a notification. Two new manifest topics: job-run-completed (info) and job-run-failed (warning), payload {job_name, run_id, trigger, action_name, duration_ms, summary, error?}. Skipped runs (cron-cap squelching) don't emit. Two more topics declared for future use: approval-requested, marketplace-install.",
      "12 new heavy-volume attack-scenario skills modeling complete kill chains: ransomware double extortion (LockBit-style ~1.5k events), APT long-dwell espionage (~3k events), insider-threat data theft, supply-chain npm compromise, M365 cloud account takeover, phishing credential harvest campaign (~6k events), web app SQLi → RCE, living-off-the-land LOLBin attacks, cryptojacking xmrig botnet, business email compromise, Kubernetes container escape, DDoS volumetric layer-7 (~13k events). Plus xsiam_top20_coverage cataloging the 20 highest-feasibility Cortex XSIAM analytics alerts XLOG can trigger directly.",
      "Documentation discipline rule codified in CLAUDE.md. Every release MUST refresh: help/architecture (services + ports + every inter-service connection with auth class), help/user (operator-visible features tagged with the version that introduced them), journeys.ts (user journeys for new flows), the skills page array (until the dynamic-load refactor in this release made it auto-sync), and CHANGELOG.md. Checklist runs before asking for release approval, parallel to the build-on-VM rule.",
      "Plus the v0.1.32-series operator UX fixes folded in: jobs export/import as separate flows, Edit job in the kebab menu, /profile sign-out + password change polish (autoComplete attributes for password managers, symmetric whitespace strip in set/verify), EnvSecretStore overlay (env vars shadow stored secrets at read time without overwriting), xlog kill_worker MCP tool (precise vs `docker compose restart xlog`), approval card UX (preamble + always-visible key args), marketplace install decoupled from instances.",
    ],
  },
  {
    version: "0.1.31",
    date: "2026-05-07",
    title: "Web connector containerized (Phase 2 — first connector flipped to per-instance container)",
    highlights: [
      "Architecture: the web connector flips from in-process Python module to per-instance MCP-over-HTTP container. When an operator creates a web instance via /connectors, phantom-updater pulls phantom-connector-web from GHCR and starts a container named `phantom-connector-web-<instance>` on the compose network. The agent's MCP loader generates a proxy that forwards tool calls to the container's MCP endpoint at `http://phantom-connector-web-<instance>:9000/mcp`. Customer impact: web tools behave identically; isolation gain is that one bad navigate can't leak Playwright/CDP state into the agent process anymore.",
      "Lifecycle: POST /api/v1/instances now returns runtime_style + container_start details when the connector is container-style. DELETE stops the container before removing the row. The instance store gains live `container_url` propagation — when phantom-updater starts a container it calls back to PUT /api/v1/instances/{id}/container_url and the agent automatically re-binds the proxy closures (no agent restart). 858ms reload vs the 30+ second container restart that v0.1.30's design would have required.",
      "Other 3 connectors (xlog, xsiam, caldera) stay in-process this release. Their per-connector images keep building and shipping (so the upgrade is still atomic across all 10 images), but their connector.yaml runtimeMapping.style stays `module`. Phased migration: v0.1.32 → xsiam, v0.1.33 → xlog, v0.1.34 → caldera, then v0.2.0 drops the in-process loader entirely. Operators see no behavior change for those three.",
      "5 bugs caught and fixed during pre-release smoke test on phantom-vm: (1) `_connector_runtime_style()` referenced `os` without importing → POST /api/v1/instances 500'd after creating the row. (2) Container proxy used `**kwargs` which FastMCP rejects → agent crashed on boot the moment any container-style instance existed. Replaced with a `compile() + exec`-synthesized proxy whose signature mirrors `connector.yaml` args (one parameter per declared arg, types mapped from yaml types to Python annotations). (3) Runtime instance_store_client SELECT'd `config`/`secret_refs` but the agent schema uses `config_json`/`secrets_json` → container crash-looped under Docker restart policy. (4) phantom-updater's HTTPS callbacks to the agent didn't honor PHANTOM_TLS_VERIFY → CERTIFICATE_VERIFY_FAILED on every container_url callback after the v0.1.27 TLS work. Now reads the env var like the agent's own internal calls do. (5) set_container_url updated the DB but didn't trigger a tool-registry reload → cached proxy closures kept feeding `container_url=None` to tool calls until operator restarted the agent. Now invokes `reload_tools_now()` after the row update; PUT response carries new `tools_reloaded` + `tool_counts` for visibility.",
      "End-to-end smoke validated on phantom-vm: POST /api/v1/instances → 201 with container_start success → phantom-connector-web-smoke up + healthy → /health 200 → container_url propagates → tool reload re-binds → web.list_sessions through agent proxy returns `{}` → web.navigate (with `trusted: true` to bypass approval) through agent proxy → connector container → CDP → phantom-browser → real fetch of example.com returns `{url, status, title, session_id, load_time_ms}`. Full chain works.",
      "Operator-facing change: customer compose now needs phantom-updater wired to call back to the agent over the same internal URL the agent reaches itself on. The customer install kit will set `PHANTOM_AGENT_INTERNAL_URL=https://phantom-agent:8080` + `PHANTOM_TLS_VERIFY=0` on the updater service. Existing v0.1.30 installs without those env vars work fine for the 3 in-process connectors; web instances created on those installs hang waiting for container_url callback unless the operator adds the env vars and restarts updater.",
      "Reference docs: docs/spec-per-instance-connector-containers.md gets a new \"Phase 2 lessons learned\" section covering the 5 bugs, the schema-drift risk between agent and runtime, the FastMCP signature-introspection constraint, and the container_url propagation race that motivated the reload-on-set wiring.",
    ],
  },
  {
    version: "0.1.30",
    date: "2026-05-07",
    title: "Per-instance connector container foundation (Phase 1, dormant)",
    highlights: [
      "Architecture: Phase 1 of the v0.2 per-instance connector container migration ships in this release as DORMANT INFRASTRUCTURE. No customer-visible behavior change. Every existing connector (xlog, xsiam, caldera, web) keeps loading in-process via connector_loader.py exactly as in v0.1.29. The new container-based runtime is wired end-to-end but no connector instance opts into it yet — that's Phase 2 (v0.1.31, web connector first).",
      "New images on GHCR (5 added): phantom-connector-runtime (FastMCP base + SecretStore client + audit forwarder + boot entrypoint) and the 4 per-connector images phantom-connector-{xlog,xsiam,caldera,web} that inherit from it. Operators don't need to pull or run any of these — the existing customer install path keeps working with 5 images. The new ones become useful starting v0.1.31.",
      "Schema: connector.yaml's runtimeMapping.style accepts a new `container` value alongside the existing `module` (default). Container-style connectors run as their own MCP-server containers reachable from the agent via MCP-over-HTTP; the agent's loader becomes a routing proxy. instance_store.db gains a `container_url` column (idempotent SQLite migration, mirrors the v0.1.15 enabled-column pattern) populated by phantom-updater when the container starts.",
      "Lifecycle: phantom-updater gains 4 new endpoints — POST /api/v1/connectors/{id}/instances/{name}/{start,stop,restart} + GET .../status — that operate on per-instance connector containers via Docker SDK. Image pulls retry with exponential backoff (1s→2s→4s→8s→16s, 5 attempts) and fall back to local cache for offline-deploy scenarios. Returns image_pull: 'pulled' vs 'cached' so audit can distinguish.",
      "Reference docs: docs/spec-per-instance-connector-containers.md (the architectural spec, ~650 lines) + bundles/spark/connectors/_runtime/ (working reference skeleton with Dockerfile, connector.yaml, demo tool) + agent-bundle-architecture.md gains a new Connector Runtime Model section comparing v0.1 in-process vs v0.2 per-instance container with a phase-by-phase migration table.",
      "Integration testing on phantom-vm caught two real bugs that would have hit Phase 2: (1) the runtime entrypoint's prefix-stripping logic only handled `phantom_<id>_*` and `phantom_*` prefixes — xsiam's `xsiam_*` and caldera's `caldera_*` would have advertised 73 tools with prefix still attached. Fix: 3-prefix list with `<id>_` in the middle. (2) The fallback module-scan was using `callable(val)` which matched Pydantic Request classes as if they were tools. Fix: tighten to `inspect.isfunction or iscoroutinefunction`.",
      "What's NOT in this release: no connector instance has runtime: container yet. Operators upgrading from v0.1.29 → v0.1.30 see ZERO behavior change. The /connectors UI doesn't yet expose container-lifecycle controls (those land alongside Phase 2 in v0.1.31 when web flips). A connector author who copies the _runtime/ skeleton can write a third-party container-mode connector today, but the marketplace listing for it requires Phase 4 work (v0.2.0).",
    ],
  },
  {
    version: "0.1.29",
    date: "2026-05-07",
    title: "Per-service conditional rebuild — caldera state preserved on phantom updates",
    highlights: [
      "Fix: release.yml now diffs source paths between the previous tag and the current one, then per-image either rebuilds (source changed) or retags the previous version's image with the new tag (source unchanged). Customer impact: when a release only touches phantom-agent, caldera/xlog/updater/browser images get the new version tag pointing at the SAME digest as the previous version. `docker compose pull` sees no digest change for those services, `docker compose up -d` leaves them running untouched, and stateful containers like caldera (live implants, ongoing operations) keep their state across the upgrade.",
      "Source path mapping per image: phantom-agent → mcp/agent/ + bundles/spark/; phantom-xlog → xlog/; phantom-caldera → third_party/caldera/ submodule; phantom-updater → updater/; phantom-browser → phantom-browser/. Changes outside any of these (release.yml, docs, .github, root README) trigger zero rebuilds — every service retags, costing ~30s of pull+tag+push per service vs. ~3-10min of rebuild+push.",
      "v0.1.29 itself is the validation of the new logic: only .github/workflows/release.yml changed, so all 5 services should retag from v0.1.28 → v0.1.29. The workflow run's job summary table makes the rebuild-vs-retag decision auditable per release; operators can see at a glance whether the conditional logic correctly identified what changed.",
      "Edge cases handled: first release with no previous tag (rebuild everything); workflow_dispatch re-runs (compares HEAD to previous tag); caldera submodule pointer change (counts as third_party/caldera/ source change → caldera rebuilds); pre-release tags (rc/alpha) excluded from the previous-tag lookup. The fetch-depth: 0 added to checkout adds ~5-10s to each release run — acceptable for the conditional-build win.",
    ],
  },
  {
    version: "0.1.28",
    date: "2026-05-06",
    title: "Tool-replay ceiling raised to 1 MiB (was 500 bytes)",
    highlights: [
      "Fix: Tool results in chat replay are no longer truncated to 500 bytes. The pre-v0.1.28 cap was a v0.1.0-era artifact from before Vertex caching existed; it directly caused the model to relay truncation stubs (\"…[result truncated, N more bytes — call X again to retrieve in full]\") back to operators instead of synthesizing answers, since calling the tool again returned the same big payload that re-truncated to the same 500 bytes. Concrete impact: `phantom_get_field_info` (~17 KB field catalog) was being clipped to 3% of its content; `phantom_get_technology_stack` (~1.5 KB) to 33%. Now retains up to 1 MiB per replayed tool result — covers every known phantom tool output with ~62x headroom.",
      "Why 1 MiB and not unlimited: this is a SAFETY VALVE for the pathological \"tool returns 100 MB blob\" case, not a budget cap. Phantom's largest known tool output is ~17 KB, well under the cap. The truncation message was rewritten too — the misleading \"call X again to retrieve in full\" hint is replaced with a clearer \"only the head is retained on replay\" so the model knows it's a replay artifact, not a recovery suggestion.",
      "Cost story: the original 500-byte cap existed to defend against per-turn prompt cost when Vertex caching wasn't available. v0.1.7 added cachedContent.create() for the system prompt; Gemini 2.5/3 then added implicit prefix caching that bills any append-only matching prefix at ~25%. So tool replays in append-only chat history bill at cached rate by default — the cap was solving a problem that's no longer load-bearing.",
      "Diagnostic: every time the 1 MiB ceiling fires, the chat handler logs `chat: tool replay ceiling fired for <toolName> (content was N bytes, kept first 1 MiB)` so operators can see in container logs whether the safety valve ever actually engages on real workloads. Expected to be never under normal use.",
    ],
  },
  {
    version: "0.1.27",
    date: "2026-05-06",
    title: "Personality approval fix + web connector + per-session/job approval bypass",
    highlights: [
      "Fix: `personality_patch` now triggers the inline approval card in chat. Before v0.1.27 the patch tool aliased its gate to `personality_update` to share the manifest entry — that satisfied the MCP-side gate but broke the chat-side `isToolGated()` check (which keys on the agent-facing tool name). The chat thought patches weren't gated, didn't arm the approval-card poll loop, and the operator saw the chat hang silently for 5 minutes. `personality_patch` now has its own `humanRequired[]` entry and the gate uses the actual tool name — approval rows + audit trail correctly distinguish patches from full-replace updates.",
      "New: `web` connector — headless-browser tools for the agent (`navigate`, `get_text`, `get_html`, `screenshot`, `click`, `fill`, `wait_for`, `extract_links`, `close_session`, `list_sessions`). Useful for IOC pivots, threat-intel portals, vendor advisories, \"go read this CVE writeup and summarize.\" Uses Playwright Python over CDP to a profile-gated `phantom-browser` sidecar (Phantom-built image based on chromedp/headless-shell) — keeps Chromium binaries out of the agent image. `get_text` defaults to Trafilatura's main-content extractor so the LLM doesn't pay for nav-bar/footer noise.",
      "New: per-session and per-job approval bypass mode. The chat header has a dropdown (`Manual approvals` / `Bypass approvals`) that persists in `session.metadata.approval_mode`; the job edit form has a `Bypass approval prompts` slider that persists in the new `bypass_approvals` jobs-table column (with SQLite migration for existing rows). When bypass is ON, the MCP-side gate auto-approves humanRequired tools instead of blocking on operator confirmation — audit rows still record every fired tool with `auto_approved=true` + the bypass source (`bypass:<chat:sid|job:name>`), so post-hoc review surfaces what ran. Useful for routine recurring jobs you trust; off by default everywhere.",
      "Plumbing: bypass flows via a new `X-Phantom-Approval-Bypass` header → trigger_context middleware → `_current_approval_bypass` contextvar → gate_and_execute. Sources: scheduler dispatch reads the new column and sends the header for jobs with bypass=true; chat handler reads `session.metadata.approval_mode` (30s server-side cache) and forwards on every MCP call when `bypass`; bypass also propagates from any inbound chat request that already carries the header (chained-job → chat dispatch case).",
      "New: `web.navigate` is approval-gated by default in the manifest. Every page fetch shows the inline approval card with the URL — bypass mode skips it. Other web.* tools (get_text, click, fill, etc.) operate on already-loaded pages and are NOT gated; the navigation that opened the page was already confirmed. Edge case: a click can re-navigate to a URL outside the allow-list — the `allowed_domains` config on the connector instance is the safety net for that.",
      "New: chip-list editor for `allowed_domains` in the connector instance form. Replaces the raw JSON-array text input with concrete chips you can add (Enter or comma-separated) or remove (× on each chip). Comes with a description-under-input affordance so the operator sees what each field does without consulting docs.",
      "Profile-gated: `phantom-browser` does NOT auto-start with `docker compose up`. Bring it up explicitly when you want web access: `docker compose --profile browser up -d phantom-browser`. Then create a `web` connector instance via /connectors → the agent picks up `web.*` on the next refresh.",
      "No instance is auto-created. The connector_loader's instance-gating means the web tools don't advertise until at least one instance exists — same model as caldera/xsiam/xlog. No env-var auto-migration entry was added: web access should be an explicit operator decision, not a default-on capability.",
      "Phantom-browser image notes (lessons learned during pre-release smoke test on phantom-vm): (1) chromedp/headless-shell's entrypoint already adds `--remote-debugging-port=9223` + `--remote-debugging-address=0.0.0.0` + `--no-sandbox` + `--use-gl=angle` and runs socat 9222→9223; the Dockerfile's CMD must NOT duplicate any of those or Chromium errors with 'Multiple targets are not supported'. (2) User-agent overrides with spaces/parens get word-split by the chromedp wrapper's `exec ... \"$@\"` and cause the same multi-target error — the default UA ships fine. (3) Chromium's DevTools enforces a Host-header check (`localhost` or IP only) that no flag disables — the connector code resolves the configured hostname to a container IP at connect time before handing it to Playwright, so `cdp_url: http://phantom-browser:9222` works even though Playwright's raw call would fail. (4) `--remote-allow-origins=*` is added but only relaxes WebSocket Origin checks, not the HTTP Host check (those are separate guards). (5) chromedp/headless-shell is too slim for HEALTHCHECK probes — no wget/curl/sh/python/nc — so we trust the Docker `running` status and let the agent's `_ensure_browser` give an operator-actionable error on first navigate() call when the sidecar is wedged.",
    ],
  },
  {
    version: "0.1.26",
    date: "2026-05-06",
    title: "Inline approval card scoped by origin + customer-issue cleanup",
    highlights: [
      "Refinement: chat-side approval poll loop now scopes to `origin=chat:<sessionId>` (using the v0.1.24 origin column). A job-fired approval landing in the same MCP runtime won't trigger a spurious inline card in an unrelated chat thread anymore. Adds `?origin=` query parameter to the /api/v1/approvals listing endpoint.",
      "Issue 4: `phantom_create_data_worker.destination` is now optional with default `XSIAM_WEBHOOK`. Customer's `hourly-f5-waf-asm-logs` job had been failing with `request.destination Field required` because the agent created the job without specifying destination. Now jobs created without explicit destination route to the platform's webhook by default.",
      "Issue 5: scheduler auto-disables jobs whose target tool isn't registered (e.g. customer's `continuous-coverage-cycle` referenced `coverage_cycle_run` from unshipped Phase 12 work and was firing daily forever, polluting audit). Failed-with-`references unknown tool`-error → enabled=0 + clear last_error. Re-enable via PATCH after the tool ships.",
      "Issues 7+8: friendlier error messages for Vertex embedding failures in `memory_search` / `knowledge_search`. The raw `vertex embed: 404 <!DOCTYPE html>...` blob is replaced with operator-actionable guidance pointing at the three common causes (wrong model name in the region, wrong project_id in GOOGLE_APPLICATION_CREDENTIALS, Vertex AI API not enabled). 401/403/429 each get their own targeted message.",
    ],
  },
  {
    version: "0.1.25",
    date: "2026-05-06",
    title: "Vertex 429 backoff + tool-budget summary + xlog probe-instead-of-assume",
    highlights: [
      "Fix: xlog SSL record-layer failure on the upgrade path. The agent's entrypoint used to assume `cert reused → xlog is on HTTPS now` and flipped XLOG_URL to https:// accordingly. False on customers who upgraded before xlog had restarted into TLS — agent talks HTTPS, xlog answers HTTP, OpenSSL hits `[SSL] record layer failure (_ssl.c:1010)` and 16+ scheduled jobs fail silently every 5 min. v0.1.25 actively probes xlog's port at startup and picks the protocol from the response.",
      "Fix: settings_get one-character bug. Was calling `s.snapshot()` but the store method is `s.describe()` — every settings_get call returned `'SqliteSettingsStore' object has no attribute 'snapshot'`. The agent now reads runtime settings cleanly.",
      "New: Vertex/Gemini 429 retry with exponential backoff + jitter. Bursty agent load (multiple 5-min-cron jobs overlapping with chat traffic) hits per-project quota. Pre-v0.1.25, every 429 surfaced as `Gemini API error: 429 ...` to chat or `RuntimeError: chat error event: Vertex AI error: 429` to scheduled jobs. Now wraps every Vertex/Gemini call site with up to 5 retries (initial 2s, ×2, ±1s jitter) — non-429 errors propagate immediately so real bugs aren't masked.",
      "New: tool-budget partial summary fallback. When the chat loop runs through all 20 turns without producing any text (model spent the whole budget on tool calls), v0.1.25 fires one more no-tools call asking the model to summarize its findings — operators get a useful recap instead of a silent dead-end.",
      "Pattern source: 429 backoff and budget summary are ports from a separate Slack-bot agent we run; the same Vertex/Gemini contract underpins both. The xlog probe is original to this codebase.",
    ],
  },
  {
    version: "0.1.24",
    date: "2026-05-06",
    title: "Approvals know where they came from (origin column + UI filter)",
    highlights: [
      "Schema: every approval row now records its `origin` — the surface that initiated the request. Format: `chat:<session_id>` for chat-driven, `job:<job_name>` for scheduler-fired, `api` for REST/MCP direct, `operator` for UI-initiated, `unknown` for legacy rows. Migration adds the column to existing approvals.db with `unknown` defaults.",
      "Plumbing: the bus reads origin from the existing X-Phantom-Trigger contextvar (already plumbed for audit). Chat handler now defaults trigger to `chat:<sessionId>` for interactive turns; job-triggered chats keep their existing `job:<name>` trigger. No new headers, no parallel contextvar.",
      "/approvals UI: Pending tab hides chat-origin rows by default — those are meant to resolve inline in the chat session that requested them (next release). New 'Include chat-origin' toggle reveals them with a (N hidden) hint so operators know when there's something to flip on. Resolved tab still shows everything for audit.",
      "What's NOT in this release: the inline chat approval card itself. v0.1.25 adds it — the chat thread will subscribe to its own session's approvals via SSE and render an Approve/Deny card in-line. Until then, chat-origin pendings still go through the (N hidden) overflow path on the /approvals page.",
      "Inspired by OpenClaw's turn-source model (`approval-turn-source.ts`, `channel-approval-auth.ts`) — where every approval carries a turn-source channel and resolves in the same surface that initiated the request, with implicit-same-chat authorization as the default.",
    ],
  },
  {
    version: "0.1.23",
    date: "2026-05-06",
    title: "Personality is markdown-only + agent prompt actually reads it + docs catch-up",
    breaking: true,
    highlights: [
      "Personality refactor: dropped the structured 'tone' (responseStyle, proactivity, confidence) and 'thinking' (logicDepth, planningDepth, delegationStyle) knobs from /settings/personality. They were never consumed by the system prompt anyway and drifted out of sync with the markdown editor. The persona markdown is now the single source of truth.",
      "Bug fix: `personalityMd` is now actually wired into the system prompt as an OPERATOR-DEFINED PERSONA section. Pre-v0.1.23, editing the markdown saved to SQLite but had zero effect on agent responses — only `actionPolicy` reached the prompt. Operators editing the markdown now actually see behavioral changes.",
      "New tool: `personality_patch(updates)` — atomic shallow-merge update for the persona blob. Lets the agent safely change just `personalityMd` (or any subset) without wiping the rest. Same approval gate as `personality_update`.",
      "Migration: no action needed. Old blobs with the dropped fields silently pass through the store; the UI no longer renders them; the prompt no longer reads them. The `breaking: true` flag is conservative — there's no functional regression unless you depended on those keys appearing in API responses.",
      "Docs: /help/user picked up substantial updates covering everything shipped in v0.1.16-v0.1.22 — the approvals scope change, the caldera password handoff (setup-form to running-container bridge), per-instance trusted flag, the upgrade flow with --upgrade-to, plus the persistent-sandcat install pattern (Windows scheduled tasks + Linux systemd) so the agent doesn't die on logoff.",
      "deploy-caldera-sandcat journey rewritten to document the persistent install (scheduled task / systemd) instead of the foreground spawn that dies with the logon session.",
    ],
  },
  {
    version: "0.1.22",
    date: "2026-05-06",
    title: "Approvals scoped to agent self-modification only",
    highlights: [
      "Policy change: approvals now ONLY fire when the agent is modifying its own runtime state (jobs, personality, settings, notifications). Simulation tools (caldera `create_operation`) and SIEM-write tools (xsiam `send_webhook_log`) no longer require operator approval — they're explicit operator intent at the chat level, and gating them again at tool-call time added friction without safety value.",
      "What this means in practice: 'launch a caldera adversary' or 'push a synthetic xsiam log' now run inline in chat without any approval prompt.",
      "What still requires approval: `jobs_create`, `jobs_update`, `jobs_run_now`, `personality_update`, `settings_update`, `notifications_dismiss(_all)`, `approvals_resolve`. These are all 'agent changing what the operator owns' — gate stays.",
      "Per-instance `trusted: true` flag from v0.1.20 still works for any future per-instance gating decisions you make. Drop the bare tool name back into bundles/spark/manifest.yaml's humanRequired list to re-gate any of the removed tools for a specific deployment.",
    ],
  },
  {
    version: "0.1.21",
    date: "2026-05-06",
    title: "Installer `--upgrade-to` flag actually survives sudo re-exec",
    highlights: [
      "Fix: `./phantom-installer --upgrade-to 0.1.21` now works. Pre-v0.1.21 the arg parser consumed the flag with `shift`, leaving `$@` empty by the time the script re-execed under sudo, so the second invocation fell back to the binary's stamped version. Customers saw 'Already at v<old> — no version change needed' even though they explicitly asked to upgrade.",
      "The fix captures argv into an `ORIGINAL_ARGS` array BEFORE the parser runs, then passes that array to the sudo re-exec. Flags now propagate correctly across the privilege escalation.",
      "Bare `./phantom-installer` (no flag) was always working — the auto-bump path uses the binary's stamped version, which doesn't depend on argv. So this only affected explicit `--upgrade-to` invocations.",
      "If you're upgrading from an older installer, the binary on disk still has the bug — grab a fresh `phantom-installer` from the v0.1.21 release page, then bare-invoke (`sudo ./phantom-installer`) which auto-bumps to 0.1.21 cleanly. From v0.1.21+ forward, `--upgrade-to` will work as documented.",
    ],
  },
  {
    version: "0.1.20",
    date: "2026-05-06",
    title: "Approvals don't crash on Context args + per-instance trusted flag",
    highlights: [
      "Fix: `Object of type Context is not JSON serializable` no longer breaks approval requests. The framework occasionally injects FastMCP `Context` objects into tool kwargs; pre-v0.1.20 those crashed `json.dumps` in the approval row writer, the row never landed, and the agent saw a 500. Now non-JSON values are coerced to a stable `<TypeName>` string at serialize time so the audit trail remains intact.",
      "New: per-instance `trusted: true` flag bypasses the human-approval gate. Set this in a connector instance's config to mark it as a lab/sandbox connector — tool calls (e.g. caldera create_operation) skip the operator-approval prompt entirely. Production instances leave it unset (default false) so the manifest's humanRequired list still fires.",
      "Set the trusted flag via the existing PATCH /api/v1/agent/instances/{id} endpoint, or by adding `\"trusted\": true` to the instance config JSON. UI affordance lands in v0.1.21.",
    ],
  },
  {
    version: "0.1.19",
    date: "2026-05-06",
    title: "Updater restart endpoint actually restarts (not just `up -d`)",
    highlights: [
      "Fix: the /api/v1/services/{svc}/restart endpoint now calls `docker compose restart` instead of `docker compose up -d --no-deps`. The latter is a no-op for an already-running healthy container with unchanged config — the HTTP response was 200 but nothing actually bounced.",
      "Net effect: setting a new caldera password in the setup form now genuinely auto-restarts caldera, the entrypoint re-runs, and `[caldera-init] applied operator creds from /operator-creds/caldera.yaml` shows up in the logs without manual intervention.",
      "This is the third (and last) layer of the auto-restart bug discovered after v0.1.16: v0.1.17 fixed the URL path, v0.1.18 fixed the compose project name, v0.1.19 fixes the compose verb. Customers should upgrade past v0.1.16/v0.1.17/v0.1.18 to v0.1.19 for clean auto-restart.",
    ],
  },
  {
    version: "0.1.18",
    date: "2026-05-06",
    title: "Updater respects compose project name",
    highlights: [
      "Fix: phantom-updater now passes `--project-name` to its `docker compose up -d` calls — without it, compose derived the project from /host (the updater's view of the install dir) and conflicted with the actual project (`phantom`) on the container_name pin, returning a 500 to the agent.",
      "v0.1.17 fixed the path mismatch (404) but uncovered THIS — the request reached the updater, the updater spawned compose, compose 409'd on `Container caldera already in use by …`. Now the project name is auto-detected from the updater's own `com.docker.compose.project` label so no env-var stamping is needed.",
      "Note: v0.1.18 alone returns 200 from the restart endpoint, but the underlying `docker compose up -d` call is a no-op for an already-running healthy container — the actual auto-restart story is completed in v0.1.19.",
    ],
  },
  {
    version: "0.1.17",
    date: "2026-05-06",
    title: "Caldera auto-restart after setup-save (bug fix)",
    highlights: [
      "Fix: setting a new caldera password in the setup form now auto-restarts the caldera container — previously the warning 'auto-restart didn't run' fired and you had to run `docker compose restart caldera` by hand.",
      "Root cause: agent was POSTing to /v1/services/caldera/restart on phantom-updater, but the route is /api/v1/services/caldera/restart. 404 → warning surfaced even though everything else (volume, bridge file, caldera entrypoint) was wired correctly.",
      "Customers running v0.1.16 with the customer installer can upgrade to 0.1.17 to skip the manual restart step.",
    ],
  },
  {
    version: "0.1.16",
    date: "2026-05-06",
    title: "Setup re-run prefills, caldera password bridge, About dialog",
    security: true,
    highlights: [
      "Setup form now prefills with everything you typed last time — secret-bearing fields come back as '***' (type new values to rotate, leave '***' to keep).",
      "🚨 Caldera login fixed: the operator password from the setup form now actually reaches caldera's auth (was diverging from .env, leaving you locked out at 401).",
      "Setup leak fixes: MCP_TOKEN no longer surfaces via /api/setup/status; webhookKey + apiKey are properly masked.",
      "Dead MCP_URL + MCP_TOKEN form fields removed (they were bundle-internal and ignored on submit).",
      "XSIAM webhookEndpoint now actually prefills (was missing a binding in spark/manifest.yaml).",
      "About dialog accessible from sidebar — icon + popover menu (About / What's new / Release history). Long-form notes open in new browser tabs.",
      "About modal centers correctly on the viewport (was clipped inside the sidebar's containing-block). Popover background also respects the light/dark theme switch.",
    ],
  },
  {
    version: "0.1.15",
    date: "2026-05-05",
    title: "Instances tab is fully functional",
    highlights: [
      "Connector instances now render in /connectors → Instances (was always empty)",
      "Edit any instance — config + credentials. Type new values over the masked '***' to rotate secrets.",
      "Test Connection actually probes the upstream with the operator's config; dry-run mode lets you test form values before saving.",
      "xsiam probe wired — POST to xql/get_datasets with your real PAPI auth, returns connected/needs-auth/failed.",
      "One active instance per connector — try to enable a second and the UI shows a clear conflict banner.",
      "Workspace UI cleared from the page (single-tenant doesn't need it).",
    ],
  },
  {
    version: "0.1.14",
    date: "2026-05-04",
    title: "Deep-smoke audit fixes (security + UX)",
    security: true,
    highlights: [
      "🚨 Security: provider config no longer returns Vertex JSON / API keys in plaintext. Sensitive values masked as '***'.",
      "/health no longer reports 'degraded' under TLS-by-default — self-probe now uses the internal HTTP loopback port.",
      "/reports page actually returns data — proxy now attaches the xlog API key.",
      "New page: /observability/runtime-events — surfaces the rt.tool.failed and rt.simulation.* event feed.",
      "Connector probe button actually probes (xlog, caldera) instead of just resetting state.",
      "Audit list endpoint includes a `total` field for pagination.",
      "Memory route `/api/agent/memory/[id]` renamed to `/[key]` to match what the path-param actually carries.",
      "/agent-definitions redirects to /agents.",
    ],
  },
  {
    version: "0.1.13",
    date: "2026-05-04",
    title: "Installer auto-bumps to its stamped version",
    highlights: [
      "`./phantom-installer` (no flag) now upgrades to whatever version the binary itself is stamped at.",
      "Older installer + newer pinned version → warning, no silent downgrade. Use --upgrade-to to force.",
      ".env missing the PHANTOM_VERSION line is now appended (was a silent sed no-op).",
      "Same image content as v0.1.12 — this release is solely the installer-binary fix.",
    ],
  },
  {
    version: "0.1.12",
    date: "2026-05-04",
    title: "Job schedule UI redesign",
    highlights: [
      "Jobs `/jobs/new` page replaces 7-mode picker with 4 cleaner modes: Run now, Run at, Repeating, Custom cron.",
      "'Repeating' is `Every N <unit>` where unit ∈ minutes/hours/days — far more flexible than hourly/daily/weekly.",
      "Live warning when an interval doesn't divide evenly (e.g. every 7 minutes creates uneven gaps at the hour boundary).",
      "Mode tiles include help text so 'Run now means run once' reads at a glance.",
      "Existing jobs unaffected — UI-only change.",
    ],
  },
  {
    version: "0.1.11",
    date: "2026-05-04",
    title: "TLS-by-default + UX fixes",
    highlights: [
      "Stack now serves HTTPS automatically on first boot via auto-generated self-signed cert.",
      "Setup form lets operators paste a CA-signed PEM (custom mode) or keep the auto-cert (self-signed mode).",
      "Jobs detail page no longer hangs ~60s on first load (SSR fetch ordering fix).",
      "Live activity feed honors dark theme correctly (was hardcoded for light).",
      "MCP→xlog tool calls no longer fail with 'Server disconnected' under TLS.",
      "New observability event `rt.tool.failed` for every MCP tool that raises.",
      "MCP_TOKEN integrity protected from legacy `.env.generated` files.",
    ],
  },
  {
    version: "0.1.10",
    date: "2026-04-29",
    title: "Baseline before the TLS-by-default chain",
    highlights: [
      "Last release before the TLS-by-default + Instances + installer-UX rework rounds.",
      "Setup-form pipeline materializes connector instances from operator-supplied config.",
      "Embedded MCP serves on port 8080 with bearer-token auth (MCP_TOKEN).",
      "Customer install kit packs `phantom-installer` + per-version compose YAML.",
    ],
  },
];

/** Convenience: fetch the entry for a specific version, if present. */
export function findRelease(version: string): ReleaseNote | undefined {
  return RELEASE_NOTES.find((r) => r.version === version);
}

/** Convenience: most-recent entry — used as a fallback when the
 *  running version doesn't appear in the static history (e.g. dev
 *  builds, or a release that ships before the notes get committed). */
export function latestRelease(): ReleaseNote {
  return RELEASE_NOTES[0];
}
