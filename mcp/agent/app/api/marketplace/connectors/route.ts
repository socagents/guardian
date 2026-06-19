/**
 * Guardian marketplace endpoint — returns the connectors that ship in
 * this bundle: xsoar, cortex-docs, web.
 * The connectors page (lifted from Spark's workspace UI) calls
 * /api/marketplace/connectors expecting a GitHub-catalog-shaped JSON;
 * in guardian standalone, the catalog IS the bundle, so we serve
 * hand-curated specs derived from the bundle's
 * `connectors/<id>/connector.yaml` files.
 *
 * If a connector ships in the bundle, it's marked `installed`. The
 * "instances" tab on the connectors page is the per-instance config
 * surface — that's where operator credentials live (filled in by the
 * setup form, materialized by the MCP into `connector_instances`).
 */

import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

interface Tool {
  name: string;
  method: string;
  description: string;
  args: Array<{
    name: string;
    type: string;
    description: string;
    required: boolean;
    defaultValue?: string;
  }>;
  outputPath?: string;
}

interface ConfigField {
  display: string;
  name: string;
  type: string;
  required: boolean;
  defaultValue?: string;
  options?: string[];
  // v0.2.30 (#44): explicit render order + conditional visibility (drives
  // the XSOAR form's "Version first; api_id only for v8"). Carried verbatim
  // to the client where CreateInstancePanel sorts + conditionally renders.
  order?: number;
  showWhen?: { field: string; in: string[] };
  description?: string;
}

interface MarketplaceConnector {
  id: string;
  name: string;
  type: string;
  // v0.2.42 — "service" marks an emulated service (e.g. the Splunk
  // mimic) reached by external systems rather than the agent. Absent
  // (or "connector") = a normal tool-calling integration.
  kind?: string;
  version: string;
  publisher: string;
  description: string;
  longDescription: string;
  category: string;
  tags: string[];
  icon: string;
  iconColor: string;
  iconBg: string;
  toolCount: number;
  installs: string;
  installCount: number;
  status: "installed" | "not_installed";
  reliability: string;
  authType: string;
  tools: Tool[];
  config: ConfigField[];
  versions: Array<{ version: string; date: string; changes: string[] }>;
  setupGuide: string;
  dockerImage: string;
  runtime: string;
  sdkLanguage: string;
  sdkPackage: string;
  ingestion: { enabled: boolean; mode: string; description: string };
  topAgents: Array<{ name: string; color: string }>;
}

const GUARDIAN_CONNECTORS: MarketplaceConnector[] = [
  // ── xsoar ───────────────────────────────────────────────────────────────
  {
    id: "xsoar",
    name: "Cortex XSOAR",
    type: "tool",
    version: "0.1.0",
    publisher: "Palo Alto Networks / kite-production",
    description:
      "Cortex XSOAR connector — monitor and investigate cases (incidents): list, fetch full case data, read the War Room, add entries/notes, update fields, manage evidence, and close incidents. Supports XSOAR 6 (on-prem) and XSOAR 8 / Cortex cloud.",
    longDescription:
      "Guardian's interface to your Cortex XSOAR tenant. The chat agent monitors cases opened on XSOAR, fetches full case data, summarizes and investigates, documents findings, and updates/closes cases. Thirteen tools cover the incident-investigation lifecycle: list and get incidents, read the War Room timeline, add entries and investigation notes, update incident fields, save and search evidence, enumerate incident types and fields, search threat indicators, and close incidents once the investigation is documented. The connector auto-detects the platform: when an API key ID is supplied it speaks the XSOAR 8 / Cortex cloud dialect (x-xdr-auth-id header, /xsoar/public/v1 path prefix, api-<fqdn> base); otherwise it speaks XSOAR 6 on-prem (single API key in the Authorization header against the server base URL).",
    category: "Security",
    tags: ["xsoar", "cortex", "soar", "cases", "incident-response"],
    icon: "shield",
    iconColor: "#6366f1",
    iconBg: "rgba(99, 102, 241, 0.12)",
    toolCount: 13,
    installs: "bundle-internal",
    installCount: 0,
    status: "installed",
    reliability: "stable",
    authType: "XSOAR API key (v6 or v8/Cortex)",
    tools: [],
    config: [
      // v0.2.30 (#44): Version is the FIRST field; selecting it drives which
      // other fields apply. v6 = on-prem (API key only); v8 = Cortex cloud
      // (also needs the API key ID). api_id is shown + required ONLY for v8.
      { display: "Version", name: "version", type: "select", required: true, options: ["v6", "v8"], defaultValue: "v8", order: 0, description: "XSOAR generation. v6 = on-prem (single API key in the Authorization header). v8 = Cortex cloud / XSOAR 8 (also needs the API key ID below)." },
      { display: "API URL", name: "api_url", type: "url", required: true, order: 1 },
      { display: "API key ID", name: "api_id", type: "string", required: true, order: 2, showWhen: { field: "version", in: ["v8"] }, description: "Cortex API key ID (sent as x-xdr-auth-id) — XSOAR 8 / cloud only." },
      { display: "API key", name: "api_key", type: "secret", required: true, order: 3 },
      { display: "Playground / War Room ID", name: "playground_id", type: "string", required: false, order: 4, description: "Investigation ID used to execute commands. Required for run_command and the get/set/append-list tools (both v6 and v8). Find it in the XSOAR UI: open the Playground (or any War Room) and copy the investigation ID from the URL." },
      { display: "Verify SSL", name: "verify_ssl", type: "boolean", required: false, defaultValue: "true", order: 5 },
    ],
    versions: [
      {
        version: "0.1.0",
        date: "2026-06-10",
        changes: [
          "Initial release — 13 tools covering the incident-investigation lifecycle (list/get incidents, War Room, entries/notes, field updates, evidence, indicator search, close).",
          "Supports XSOAR 6 (on-prem: single API key in the Authorization header) and XSOAR 8 / Cortex cloud (API key + key id via x-xdr-auth-id header, /xsoar/public/v1 path prefix). Auto-detected from whether an API key ID is supplied.",
        ],
      },
    ],
    setupGuide:
      "1) Mint an XSOAR API key. XSOAR 6 (on-prem): Settings → Integrations → API Keys → Get Your Key — copy the key, leave the API key ID blank, and set the API URL to your server base (https://<server>). XSOAR 8 / Cortex cloud: Settings → Configurations → API Keys → New Key with a role that can read and update incidents — copy both the key and its numeric ID, and set the API URL to https://api-<your-fqdn>. 2) Click 'Add instance' on the Cortex XSOAR card. 3) Paste the API URL, API key, and (XSOAR 8 only) the API key ID; leave Verify SSL on unless your tenant uses a self-signed cert. 4) Save, then click 'Test Connection' — a green check means the agent can reach your cases. 5) Ask the agent in chat: 'show me the open incidents' or 'investigate incident <id> and document your findings'.",
    dockerImage: "ghcr.io/kite-production/guardian-connector-xsoar:latest",
    runtime: "python",
    sdkLanguage: "Python",
    sdkPackage: "guardian-spark-xsoar-connector",
    ingestion: { enabled: false, mode: "pull", description: "Cases fetched on demand per tool call. No background polling." },
    topAgents: [{ name: "guardian-agent", color: "#6366f1" }],
  },
  // ── xsiam (v0.2.0) ───────────────────────────────────────────────────────
  {
    id: "xsiam",
    name: "Cortex XSIAM",
    type: "tool",
    version: "0.2.0",
    publisher: "Palo Alto Networks / kite-production",
    description:
      "Cortex XSIAM connector — investigation (XQL queries, incidents, alerts, issues, assets, audit, datamodel) and EDR response (endpoint isolate/scan/quarantine, script execution, IOC + hash blocklisting) over the Cortex public API.",
    longDescription:
      "Guardian's interface to your Cortex XSIAM tenant. The chat agent hunts across the data lake with XQL, triages incidents and alerts, pivots on assets and issues, reads audit logs, and — when a case calls for containment — takes EDR response actions directly: isolate or scan an endpoint, quarantine a file, run a script or snippet, and blocklist a hash or IOC. 54 tools span the investigate-to-respond lifecycle. Authentication is the Cortex public-API key pair (an API key id sent as the x-xdr-auth-id header plus the API key as the Authorization header); the connector appends /public_api/v1 to your tenant API host. Every write/response tool is approval-gated by the connector wrapper, and the one destructive lookup mutation (remove_lookup_data) is denied outright.",
    category: "Security",
    tags: ["xsiam", "cortex", "siem", "xql", "edr", "incident-response"],
    icon: "siren",
    iconColor: "#f97316",
    iconBg: "rgba(249, 115, 22, 0.12)",
    toolCount: 54,
    installs: "bundle-internal",
    installCount: 0,
    status: "installed",
    reliability: "stable",
    authType: "Cortex XSIAM API key (api_id + api_key)",
    tools: [],
    config: [
      { display: "API URL", name: "api_url", type: "url", required: true },
      { display: "API key ID", name: "api_id", type: "string", required: true },
      { display: "API key", name: "api_key", type: "secret", required: true },
    ],
    versions: [
      {
        version: "0.2.0",
        date: "2026-06-15",
        changes: [
          "Initial Guardian release — 54 tools covering XSIAM investigation (XQL, incidents, alerts, issues, assets, audit, datamodel, parsers, broker) and EDR response (endpoint isolate/unisolate/scan/quarantine/retrieve-file, script run/snippet, IOC insert/disable/enable, hash blocklist, alert exclusions).",
          "Ported from the Phantom XSIAM connector, minus its simulation-only pieces (synthetic webhook log injection + the removed xql-examples KB RAG tools). Auth is the Cortex public-API key pair (api_id → x-xdr-auth-id, api_key → Authorization).",
        ],
      },
    ],
    setupGuide:
      "1) Mint a Cortex XSIAM API key: Settings → Configurations → API Keys → New Key, with a role that can read incidents/alerts and (for response actions) manage endpoints. Copy both the key and its numeric ID. 2) Find your tenant API host — the base looks like https://api-<your-fqdn>.xdr.<region>.paloaltonetworks.com; the connector appends /public_api/v1. 3) Click 'Add instance' on the Cortex XSIAM card. 4) Paste the API URL (the host), the API key ID (api_id), and the API key (api_key). 5) Save, then click 'Test Connection'. 6) Ask the agent in chat: 'run an XQL query for failed logins in the last hour', 'list the open XSIAM incidents', or 'isolate endpoint <id>' (response actions are approval-gated).",
    dockerImage: "ghcr.io/kite-production/guardian-connector-xsiam:latest",
    runtime: "python",
    sdkLanguage: "Python",
    sdkPackage: "guardian-spark-xsiam-connector",
    ingestion: { enabled: false, mode: "pull", description: "Data fetched on demand per tool call. No background polling." },
    topAgents: [{ name: "guardian-agent", color: "#f97316" }],
  },
  // ── web (v0.1.27) ────────────────────────────────────────────────────────
  {
    id: "web",
    name: "Web Browser",
    type: "tool",
    version: "0.1.0",
    publisher: "kite-production",
    description:
      "Headless browser tools — fetch web pages, extract text/links, screenshot, click, fill forms. Backed by a profile-gated chromedp/headless-shell sidecar.",
    longDescription:
      "Lets the agent reach the public web for IOC pivots, vendor advisories, threat-intel portal scraping, and 'go read this CVE writeup' requests. Talks to guardian-browser (a profile-gated sidecar) over Chrome DevTools Protocol via Playwright Python. The Allowed Domains list is the primary safety control — restrict the agent to vetted hosts. By default web.navigate is approval-gated; use the chat-header dropdown or a job's bypass slider to opt out per session/job.",
    category: "Security",
    tags: ["browser", "scraping", "intel", "v0.1.27"],
    icon: "language",
    iconColor: "#a855f7",
    iconBg: "rgba(168, 85, 247, 0.12)",
    toolCount: 10,
    installs: "bundle-internal",
    installCount: 0,
    status: "installed",
    reliability: "preview",
    authType: "None (internal CDP)",
    tools: [
      {
        name: "navigate",
        method: "goto",
        description: "Open a URL in a new or existing page. Approval-gated by default.",
        args: [
          { name: "url", type: "string", description: "Absolute URL to navigate to.", required: true },
          { name: "session_id", type: "string", description: "Reuse a tab across calls; omit for one-shot.", required: false },
        ],
      },
      {
        name: "get_text",
        method: "innerText + readability",
        description: "Extract main-content text (Trafilatura), or document.body.innerText. Token-efficient for LLM consumption.",
        args: [
          { name: "session_id", type: "string", description: "Page handle.", required: true },
          { name: "mode", type: "string", description: "'readable' | 'body' | 'markdown'.", required: false },
        ],
      },
      {
        name: "screenshot",
        method: "page.screenshot",
        description: "Capture base64 PNG of the page (or JPEG for smaller payload).",
        args: [{ name: "session_id", type: "string", description: "Page handle.", required: true }],
      },
      {
        name: "click",
        method: "page.click",
        description: "Click an element matched by CSS / text= / role= selector.",
        args: [
          { name: "session_id", type: "string", description: "Page handle.", required: true },
          { name: "selector", type: "string", description: "Playwright selector.", required: true },
        ],
      },
      {
        name: "fill",
        method: "page.fill",
        description: "Type a value into an input/textarea matched by selector.",
        args: [
          { name: "session_id", type: "string", description: "Page handle.", required: true },
          { name: "selector", type: "string", description: "Playwright selector.", required: true },
          { name: "value", type: "string", description: "Text to fill in.", required: true },
        ],
      },
      {
        name: "extract_links",
        method: "querySelectorAll a[href]",
        description: "Return all links on the page with text + href + host.",
        args: [{ name: "session_id", type: "string", description: "Page handle.", required: true }],
      },
    ],
    config: [
      {
        display: "CDP URL",
        name: "cdp_url",
        type: "text",
        required: true,
        defaultValue: "http://guardian-browser:9222",
      },
      {
        display: "Default timeout (ms)",
        name: "default_timeout_ms",
        type: "text",
        required: false,
        defaultValue: "30000",
      },
      {
        display: "User-Agent override",
        name: "user_agent",
        type: "text",
        required: false,
      },
      {
        display: "Allowed Domains",
        name: "allowed_domains",
        type: "array",
        required: false,
        defaultValue: "[]",
      },
      {
        display: "Block resource types",
        name: "block_resource_types",
        type: "array",
        required: false,
        defaultValue: "[]",
      },
      {
        display: "Default extractor mode",
        name: "extractor_mode",
        type: "select",
        required: false,
        defaultValue: "readable",
        options: ["readable", "body", "markdown"],
      },
    ],
    versions: [
      {
        version: "0.1.0",
        date: "2026-05-06",
        changes: [
          "Initial release — 10 tools (navigate, get_text, get_html, screenshot, click, fill, wait_for, extract_links, close_session, list_sessions)",
          "Connects to guardian-browser sidecar via Playwright over CDP; profile-gated so it doesn't auto-start",
          "Trafilatura-powered readable text extraction",
          "allowed_domains hostname allow-list with .example.com suffix wildcard support",
          "web.navigate approval-gated by default; bypass via chat-header dropdown or job bypass slider",
        ],
      },
    ],
    setupGuide:
      "1) Bring up the sidecar: `docker compose --profile browser up -d guardian-browser`. 2) Click 'Add instance', leave cdp_url as the default. 3) Set Allowed Domains to your vetted threat-intel + vendor-doc hosts (use `.example.com` to match all subdomains). 4) Save. The agent will see web.* tools on its next refresh.",
    dockerImage: "ghcr.io/kite-production/guardian-browser:latest",
    runtime: "python",
    sdkLanguage: "Python",
    sdkPackage: "guardian-spark-web-connector",
    ingestion: {
      enabled: false,
      mode: "pull",
      description: "Pages are fetched on demand by the agent — no continuous ingestion.",
    },
    topAgents: [{ name: "guardian-agent", color: "#a855f7" }],
  },
  // ── cortex-docs (v0.3.1) ─────────────────────────────────────────────────
  {
    id: "cortex-docs",
    name: "Cortex Docs",
    type: "tool",
    version: "0.3.1",
    publisher: "kite-production",
    description:
      "Search and lookup against the public Palo Alto Networks Cortex documentation (XDR / XSIAM / XSOAR / Cortex Cloud / AgentiX / Xpanse / XQL). Six tools for full-text search, autocomplete, focused XQL stage/function lookup, full-topic fetch, TOC enumeration, and heavyweight multi-section research planning.",
    longDescription:
      "Bridges the agent's query-authoring path with authoritative Palo Alto Cortex documentation. The flagship tool, cortex-docs/xql_lookup, is the focused syntax-reference shortcut: given a stage or function name (dedup, alter, arrayindexof, json_extract_scalar, etc.) it searches Cortex docs with stage-aware query expansion, ranks results against authority heuristics that boost canonical reference pages over release-notes coverage, and returns an answer-ready payload with title + summary + reader URL + source citation in <2 seconds. Pairs with the cortex_xql_query_authoring foundation skill, which orchestrates a six-step workflow: restate intent → embedding-search the operator's KB for similar examples → extract stages/functions → call cortex-docs/xql_lookup per term → author the query using KB examples as pattern prior + cortex docs as syntax reference → emit with per-stage citations. The connector is module-style Python with no required configuration (the Cortex docs API is public). The heavyweight cortex-docs/deep_research tool runs a multi-section research planner for actual deliverables (whitepapers, partner briefings, migration guides) — uses ANTHROPIC_API_KEY when available, falls back to a built-in heuristic plan otherwise. Reserve it for explicit multi-section deliverables; the standard query-authoring path uses xql_lookup instead.",
    category: "Security",
    tags: ["cortex", "xql", "documentation", "research", "palo-alto", "v0.3.1"],
    icon: "menu_book",
    iconColor: "#fa582d",
    iconBg: "rgba(250, 88, 45, 0.12)",
    toolCount: 6,
    installs: "bundle-internal",
    installCount: 0,
    status: "installed",
    reliability: "stable",
    authType: "None (public Cortex docs API)",
    tools: [
      {
        name: "search",
        method: "POST /api/khub/clustered-search",
        description:
          "Full-text search across Cortex public docs. Auto-detects product mentions in the query when product is omitted; supports explicit scope.",
        args: [
          { name: "query", type: "string", description: "Free-text search string. Use Cortex product vocabulary for best recall.", required: true },
          { name: "product", type: "string", description: "Optional product scope: agentix, xdr, xsiam, xsoar, xql, cloud, dspm, cspm, ciem, xpanse.", required: false },
          { name: "per_page", type: "integer", description: "Results per page (1-100; default 20).", required: false },
          { name: "page", type: "integer", description: "1-based page number.", required: false },
        ],
      },
      {
        name: "suggest",
        method: "POST /api/khub/suggest",
        description: "Autocomplete suggestions for a partial query. Useful for disambiguating noisy operator input.",
        args: [
          { name: "input_text", type: "string", description: "Partial search text (e.g. 'filter st').", required: true },
          { name: "product", type: "string", description: "Optional product scope (same vocabulary as search).", required: false },
        ],
      },
      {
        name: "xql_lookup",
        method: "search + rank + fetch_topic_with_fallback",
        description:
          "Focused XQL stage or function lookup. Stage-aware query expansion + ranks canonical reference pages above release notes; auto-children fallback for DITA stub topics.",
        args: [
          { name: "term", type: "string", description: "Stage or function name (e.g. dedup, arrayindexof). Strips leading 'stage'/'function'/'xql' noise prefixes.", required: true },
          { name: "kind", type: "string", description: "'auto' (default; inferred from name), 'stage', or 'function'.", required: false },
          { name: "product", type: "string", description: "Product scope: xql (default — all XQL products), xdr, xsiam, agentix, cloud.", required: false },
          { name: "per_page", type: "integer", description: "Search-result page size (default 8).", required: false },
          { name: "suggest", type: "boolean", description: "Include autocomplete suggestions for the cleaned term (default false).", required: false },
        ],
      },
      {
        name: "fetch_topic",
        method: "GET /api/khub/maps/{map_id}/topics/{topic_id}",
        description: "Fetch full topic content given a map_id + topic_id from a prior search hit. Auto-children fallback for stub DITA containers.",
        args: [
          { name: "map_id", type: "string", description: "Publication ID from a search hit.", required: true },
          { name: "topic_id", type: "string", description: "Topic ID within that publication.", required: true },
          { name: "max_chars", type: "integer", description: "Truncation ceiling for content (default 12000).", required: false },
        ],
      },
      {
        name: "fetch_toc",
        method: "GET /api/khub/maps/{map_id}/pages",
        description: "Fetch the full table of contents for a Cortex docs publication.",
        args: [{ name: "map_id", type: "string", description: "Publication ID.", required: true }],
      },
      {
        name: "deep_research",
        method: "plan → search → fetch → gap-check → synthesize",
        description:
          "Heavyweight (1-3 min) multi-section research planner. Reserve for whitepapers, partner briefings, migration guides. NOT for query authoring.",
        args: [
          { name: "request", type: "string", description: "Research deliverable request, e.g. 'Create a partner briefing about Cortex XDR incident response'.", required: true },
          { name: "max_sections", type: "integer", description: "Cap on planned sections (default 8).", required: false },
          { name: "hits_per_section", type: "integer", description: "Max docs hits per section (default 4).", required: false },
          { name: "enable_gap_check", type: "boolean", description: "Run gap-check + retry pass for weak-coverage sections (default false).", required: false },
        ],
      },
    ],
    config: [
      {
        display: "Cortex docs base URL",
        name: "baseUrl",
        type: "text",
        required: false,
        defaultValue: "https://docs-cortex.paloaltonetworks.com",
      },
      {
        display: "Planner model (cortex-docs/deep_research only)",
        name: "plannerModel",
        type: "text",
        required: false,
        defaultValue: "",
      },
      {
        display: "Per-request timeout (seconds)",
        name: "requestTimeoutSeconds",
        type: "text",
        required: false,
        defaultValue: "30",
      },
    ],
    versions: [
      {
        version: "0.3.1",
        date: "2026-05-10",
        changes: [
          "Initial release — 6 tools (search, suggest, xql_lookup, fetch_topic, fetch_toc, deep_research)",
          "Wraps four upstream scripts from cortex-deep-search_sharable, preserved verbatim (search.py, fetch_topic.py, xql_lookup.py, research_planner.py)",
          "Module-style Python connector — stdlib-only (urllib + json + re), no daemon, zero extra deps",
          "SystemExit-translation wrapper at the integration boundary so transient docs-API outages produce structured error returns instead of crashing guardian-agent",
          "Bundles cortex_xql_query_authoring foundation skill — six-step KB-search → stage/function-extraction → cortex-docs lookup → query-authoring workflow",
          "deep_research uses ANTHROPIC_API_KEY when available; falls back to built-in heuristic planner with no LLM dependency",
        ],
      },
    ],
    setupGuide:
      "1) Click 'Add instance' on the cortex-docs row. 2) Leave the defaults — the Cortex docs API is public, no credentials needed. 3) Save. The agent will see cortex-docs.* tools on the next refresh and the cortex_xql_query_authoring skill becomes operational. 4) (Optional) Set plannerModel to a Claude model id if you want cortex-docs/deep_research to use LLM-driven planning instead of the heuristic fallback.",
    dockerImage: "ghcr.io/kite-production/guardian-connector-cortex-docs:latest",
    runtime: "python",
    sdkLanguage: "Python",
    sdkPackage: "guardian-spark-cortex-docs-connector",
    ingestion: {
      enabled: false,
      mode: "pull",
      description: "Cortex docs are fetched on demand per tool call — no continuous ingestion.",
    },
    topAgents: [{ name: "guardian-agent", color: "#fa582d" }],
  },
];

/** Title-case a snake_case field name, upper-casing known acronyms so a
 *  generated label reads like a curated one (playground_id → "Playground ID",
 *  api_url → "API URL"). Used only for config fields the hardcoded list
 *  doesn't already name. */
const _ACRONYMS = new Set(["api", "url", "id", "ssl", "cdp", "ms", "uri", "tls", "ip"]);
function humanizeFieldName(name: string): string {
  return name
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((w) => (_ACRONYMS.has(w.toLowerCase()) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

/** Map a connector.yaml configSchema property type onto a form-widget type. */
function mapConfigType(t: unknown): string {
  switch (typeof t === "string" ? t : "") {
    case "boolean":
      return "boolean";
    case "array":
      return "array";
    case "integer":
    case "number":
      return "string";
    default:
      return "string";
  }
}

interface LiveMeta {
  tools: Tool[];
  /** Config fields derived from configSchema.properties + secretSlots. */
  config: ConfigField[];
  version: string | null;
}

/**
 * v0.15.5 — overlay live metadata from each connector.yaml on top of the
 * hardcoded entries. Pre-v0.15.5 the toolCount + tools[] arrays here were
 * hand-maintained and drifted (operator-visible counts went stale whenever a
 * connector's tool surface expanded).
 *
 * v0.1.2 — the SAME drift bit config fields: a connector adding a config field
 * (e.g. xsoar's `playground_id`) never surfaced in the UI because `config` was
 * hardcoded here. The overlay now also derives `config` from
 * `configSchema.properties` + `secretSlots` and reads the live `version`, so a
 * new field appears in the instance form on the next dev/release cycle without
 * touching this file. Caller MERGES live config fields the hardcoded list
 * doesn't already name (preserving curated labels for existing fields).
 *
 * Resolution order for the bundle dir:
 *   1. /app/bundle/connectors/<id>/connector.yaml   (production, image-mounted)
 *   2. <repo>/bundles/spark/connectors/<id>/connector.yaml  (local dev)
 *
 * If neither exists OR the YAML parse fails, returns null and the caller falls
 * back to the hardcoded entry so the UI stays functional.
 */
async function loadLiveMeta(connectorId: string): Promise<LiveMeta | null> {
  const fs = await import("fs/promises");
  const path = await import("path");
  const yaml = await import("js-yaml");

  const candidates = [
    `/app/bundle/connectors/${connectorId}/connector.yaml`,
    path.resolve(
      process.cwd(),
      "..",
      "..",
      "bundles",
      "spark",
      "connectors",
      connectorId,
      "connector.yaml",
    ),
    // Inside the build at agent's working dir (cwd=mcp/agent in dev)
    path.resolve(process.cwd(), "bundles", "spark", "connectors", connectorId, "connector.yaml"),
  ];

  for (const p of candidates) {
    try {
      const text = await fs.readFile(p, "utf-8");
      const doc = yaml.load(text) as {
        version?: unknown;
        configSchema?: {
          required?: unknown;
          properties?: Record<string, { type?: unknown; default?: unknown; enum?: unknown[] }>;
        };
        secretSlots?: Array<{ name?: unknown; required?: unknown }>;
        spec?: { tools?: Array<Record<string, unknown>> };
      };
      const yamlTools = doc?.spec?.tools;
      if (!Array.isArray(yamlTools)) return null;

      const tools: Tool[] = [];
      for (const t of yamlTools) {
        const name = typeof t.name === "string" ? t.name : null;
        if (!name) continue;
        const method =
          typeof t.method === "string"
            ? t.method.startsWith("GET")
              ? "GET"
              : t.method.startsWith("PUT")
                ? "PUT"
                : t.method.startsWith("DELETE")
                  ? "DELETE"
                  : t.method.startsWith("POST")
                    ? "POST"
                    : "POST"
            : "POST";
        const description =
          typeof t.description === "string"
            ? t.description.trim().split("\n")[0].slice(0, 220)
            : "";
        const args: Tool["args"] = [];
        if (Array.isArray(t.args)) {
          for (const a of t.args as Array<Record<string, unknown>>) {
            const aname = typeof a.name === "string" ? a.name : null;
            if (!aname) continue;
            args.push({
              name: aname,
              type: typeof a.type === "string" ? a.type : "string",
              description: typeof a.description === "string" ? a.description : "",
              required: a.required === true,
              defaultValue:
                typeof a.defaultValue === "string"
                  ? a.defaultValue
                  : typeof a.default === "string"
                    ? a.default
                    : undefined,
            });
          }
        }
        tools.push({ name, method, description, args });
      }

      // Derive config fields: configSchema.properties (non-secret) + secretSlots.
      const config: ConfigField[] = [];
      const required = Array.isArray(doc?.configSchema?.required)
        ? (doc.configSchema!.required as unknown[]).filter((x): x is string => typeof x === "string")
        : [];
      const props = doc?.configSchema?.properties ?? {};
      for (const [key, prop] of Object.entries(props)) {
        // A JSON-Schema `string` property with a non-empty `enum` renders
        // as a native dropdown (type:"select" + options[]), mirroring the
        // web connector's curated extractor_mode field — but derived purely
        // from connector.yaml with no hardcoding. mapConfigType() collapses
        // every non-boolean/non-array type to "string", so enum-as-dropdown
        // is the one shape it can't express on its own.
        const propType = typeof prop?.type === "string" ? prop.type : "";
        const enumValues = Array.isArray(prop?.enum) ? prop.enum : [];
        const isEnumString =
          (propType === "string" || propType === "") && enumValues.length > 0;
        config.push({
          display: humanizeFieldName(key),
          name: key,
          type: isEnumString ? "select" : mapConfigType(prop?.type),
          required: required.includes(key),
          defaultValue:
            prop?.default !== undefined ? String(prop.default) : undefined,
          ...(isEnumString ? { options: enumValues.map(String) } : {}),
        });
      }
      if (Array.isArray(doc?.secretSlots)) {
        for (const slot of doc.secretSlots) {
          const sname = typeof slot?.name === "string" ? slot.name : null;
          if (!sname) continue;
          config.push({
            display: humanizeFieldName(sname),
            name: sname,
            type: "secret",
            required: slot?.required === true,
          });
        }
      }

      const version = typeof doc?.version === "string" ? doc.version : null;
      return { tools, config, version };
    } catch {
      // try next candidate
    }
  }
  return null;
}

export async function GET() {
  // Build a deep copy so concurrent requests don't see each other's overlay
  const out = GUARDIAN_CONNECTORS.map((c) => ({ ...c, tools: [...c.tools], config: [...c.config] }));
  await Promise.all(
    out.map(async (c) => {
      const live = await loadLiveMeta(c.id);
      if (!live) return;
      if (live.tools.length > 0) {
        c.tools = live.tools;
        c.toolCount = live.tools.length;
      }
      if (live.version) c.version = live.version;
      // Append any live config field the hardcoded entry doesn't already
      // name. This surfaces NEW config fields (e.g. xsoar.playground_id)
      // without clobbering the curated display/type of existing fields.
      if (live.config.length > 0) {
        const known = new Set(c.config.map((f) => f.name));
        for (const f of live.config) {
          if (!known.has(f.name)) c.config.push(f);
        }
      }
    }),
  );
  return NextResponse.json(out);
}
