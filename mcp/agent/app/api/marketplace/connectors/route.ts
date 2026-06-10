/**
 * Phantom marketplace endpoint — returns the three connectors that ship in
 * this bundle: xlog, caldera, xsiam. The connectors page (lifted from
 * Spark's workspace UI) calls /api/marketplace/connectors expecting a
 * GitHub-catalog-shaped JSON; in phantom standalone, the catalog IS the
 * bundle, so we serve hand-curated specs derived from the bundle's
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
}

interface MarketplaceConnector {
  id: string;
  name: string;
  type: string;
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

const PHANTOM_CONNECTORS: MarketplaceConnector[] = [
  // ── xlog ────────────────────────────────────────────────────────────────
  {
    id: "xlog",
    name: "xlog",
    type: "tool",
    version: "1.2.0",
    publisher: "kite-production",
    description:
      "Synthetic security log generation engine. Produces SYSLOG/CEF/JSON streams to webhooks, XSIAM, or files.",
    longDescription:
      "xlog is the log-generation backend for Phantom SOC simulation. It exposes a GraphQL API that the agent calls to spin up workers (port-scan, brute-force, malware-c2, exfil scenarios) which emit RFC-compliant logs into your downstream sink — XSIAM PAPI, webhook, or local file. Built on the rosetta-ce library.",
    category: "Security",
    tags: ["soc", "logs", "simulation", "xsiam"],
    icon: "data_object",
    iconColor: "#00f5ff",
    iconBg: "rgba(0, 245, 255, 0.12)",
    toolCount: 12,
    installs: "bundle-internal",
    installCount: 1,
    status: "installed",
    reliability: "stable",
    authType: "Bearer token",
    tools: [
      {
        name: "create_format_worker",
        method: "POST",
        description: "Spin up a worker that emits N logs/min in the given format (SYSLOG/CEF/JSON) to a sink.",
        args: [
          { name: "format", type: "enum", description: "SYSLOG | CEF | JSON", required: true },
          { name: "rate", type: "int", description: "logs per minute", required: true, defaultValue: "60" },
          { name: "sink", type: "url", description: "destination (webhook URL, XSIAM PAPI, or file://)", required: true },
        ],
      },
      {
        name: "create_scenario_worker",
        method: "POST",
        description: "Run a named scenario from scenarios/ready/*.json (port-scan, brute-force, etc.).",
        args: [
          { name: "scenario", type: "string", description: "scenario filename without .json", required: true },
        ],
      },
      {
        name: "list_workers",
        method: "GET",
        description: "List active log-generation workers with status/uptime.",
        args: [],
      },
      {
        name: "stop_worker",
        method: "POST",
        description: "Halt an active worker.",
        args: [{ name: "id", type: "string", description: "worker id", required: true }],
      },
      {
        name: "generate_coverage_report",
        method: "POST",
        description: "Run XQL queries against the configured XSIAM tenant and emit a coverage table.",
        args: [],
      },
    ],
    config: [
      // v0.6.15 — renamed `xlogUrl` → `baseUrl` to match the canonical
      // field name in bundles/spark/connectors/xlog/connector.yaml
      // (configSchema.properties.baseUrl). Same drift pattern as
      // caldera; same fix. Display name "xlog URL" stays.
      // v0.6.22 — default changed from http://xlog:8000 → https://...
      // xlog has served HTTPS on port 8000 unconditionally since
      // the v0.4.0 TLS rollout (mounts /tls/cert.pem from the shared
      // phantom_tls volume; uses TLS via priority-1 in its
      // _resolve_ssl_args). Pre-v0.6.22 operators who accepted the
      // http default got "Empty reply from server" at probe time +
      // reports proxy 502 indefinitely.
      { display: "xlog URL", name: "baseUrl", type: "url", required: true, defaultValue: "https://xlog:8000" },
      { display: "API Token", name: "apiToken", type: "secret", required: true },
    ],
    versions: [
      { version: "1.2.0", date: "2026-04-29", changes: ["Bearer auth on every request", "XQL coverage report tool"] },
      { version: "1.1.0", date: "2026-03-15", changes: ["Scenario worker CRUD", "Webhook sink support"] },
    ],
    setupGuide:
      "Set XLOG_URL to your xlog service (default https://xlog:8000) and XLOG_API_KEY to the matching bearer token.",
    dockerImage: "ghcr.io/kite-production/xlog:1.2.0",
    runtime: "python",
    sdkLanguage: "Python",
    sdkPackage: "phantom-spark-xlog-connector",
    ingestion: { enabled: true, mode: "push", description: "Worker logs are pushed to the configured sink" },
    topAgents: [{ name: "phantom-soc-simulation", color: "#00f5ff" }],
  },
  // ── caldera ─────────────────────────────────────────────────────────────
  {
    id: "caldera",
    name: "Caldera",
    type: "tool",
    version: "5.3.0",
    publisher: "MITRE / kite-production",
    description:
      "MITRE Caldera — adversary emulation platform. Run operations, list abilities, drive red-team scenarios.",
    longDescription:
      "Caldera connector wraps Caldera 5.3's v2 REST API. The agent can list abilities, start/stop operations, and stream operation results. Used in Phantom for end-to-end attack-chain simulation alongside xlog for realistic telemetry.",
    category: "Security",
    tags: ["red-team", "mitre", "attack-emulation"],
    icon: "shield",
    iconColor: "#ff5f8a",
    iconBg: "rgba(255, 95, 138, 0.12)",
    toolCount: 9,
    installs: "bundle-internal",
    installCount: 1,
    status: "installed",
    reliability: "stable",
    authType: "API key (KEY: header)",
    tools: [
      {
        name: "list_abilities",
        method: "GET",
        description: "List all Caldera abilities with their MITRE ATT&CK technique mappings.",
        args: [],
      },
      {
        name: "list_adversaries",
        method: "GET",
        description: "List all adversary profiles available in this Caldera tenant.",
        args: [],
      },
      {
        name: "start_operation",
        method: "POST",
        description: "Kick off a Caldera operation against a group with a chosen adversary.",
        args: [
          { name: "name", type: "string", description: "operation name", required: true },
          { name: "adversary_id", type: "string", description: "adversary id", required: true },
          { name: "group", type: "string", description: "agent group", required: true, defaultValue: "red" },
        ],
      },
      {
        name: "list_operations",
        method: "GET",
        description: "List active and completed operations.",
        args: [],
      },
    ],
    config: [
      // v0.6.15 — renamed `calderaUrl` → `baseUrl` to match the
      // canonical field name in bundles/spark/connectors/caldera/
      // connector.yaml (configSchema.properties.baseUrl). Pre-v0.6.15
      // the catalog drifted from the connector's actual schema, so
      // operator-created instances stored `calderaUrl` while the
      // connector code at runtime tried `baseUrl` / `caldera_url` /
      // `url` and never found a match → "caldera instance has no
      // baseUrl configured." Display name "Caldera URL" stays.
      { display: "Caldera URL", name: "baseUrl", type: "url", required: true, defaultValue: "http://caldera:8888" },
      { display: "API Key", name: "apiKey", type: "secret", required: true },
      { display: "Red user", name: "redUser", type: "string", required: false, defaultValue: "red" },
      { display: "Red password", name: "redPassword", type: "secret", required: false },
    ],
    versions: [{ version: "5.3.0", date: "2026-04-23", changes: ["v2 REST API", "Bearer KEY auth"] }],
    setupGuide:
      "Provision a Caldera 5.3 instance, create an API key under Settings, and supply CALDERA_URL + CALDERA_API_KEY.",
    dockerImage: "aymanam/caldera:5.3.0",
    runtime: "python",
    sdkLanguage: "Python",
    sdkPackage: "phantom-spark-caldera-connector",
    ingestion: { enabled: false, mode: "pull", description: "Tools pull operation results on demand" },
    topAgents: [{ name: "phantom-soc-simulation", color: "#ff5f8a" }],
  },
  // ── xsiam ───────────────────────────────────────────────────────────────
  {
    id: "xsiam",
    name: "Cortex XSIAM",
    type: "tool",
    version: "1.0.0",
    publisher: "Palo Alto Networks / kite-production",
    description:
      "Palo Alto Cortex XSIAM connector — execute XQL queries via PAPI, run remote scripts in the issue war room.",
    longDescription:
      "Bridges Phantom to your Cortex XSIAM tenant. The agent can run XQL queries, fetch detection results, list incidents, and execute remote scripts inside the war-room runtime. Used by validation skills to confirm that ingested logs actually triggered the expected XQL detections.",
    category: "Security",
    tags: ["siem", "xql", "cortex", "detection"],
    icon: "query_stats",
    iconColor: "#1f7bff",
    iconBg: "rgba(31, 123, 255, 0.12)",
    toolCount: 7,
    installs: "bundle-internal",
    installCount: 1,
    status: "installed",
    reliability: "stable",
    authType: "PAPI bearer + auth-id",
    tools: [
      {
        name: "execute_xql_query",
        method: "POST",
        description: "Run an XQL query against the XSIAM tenant and return rows.",
        args: [
          { name: "query", type: "string", description: "XQL query text", required: true },
          { name: "tenant_id", type: "string", description: "XSIAM tenant id", required: false },
        ],
      },
      {
        name: "list_incidents",
        method: "GET",
        description: "List recent XSIAM incidents.",
        args: [],
      },
      {
        name: "execute_remote_script",
        method: "POST",
        description: "Run a script in the issue war room.",
        args: [
          { name: "script", type: "string", description: "script content", required: true },
        ],
      },
    ],
    config: [
      // v0.5.59 (issue #35): renamed from papiUrl/papiAuthHeader/papiAuthId
      // to api_url/api_key/api_id for uniformity with the Cortex XDR connector
      // (issue #36). Connector code + probe accept both name pairs at read
      // time, so existing instances keep working through the rename.
      { display: "API URL", name: "api_url", type: "url", required: true },
      { display: "API key", name: "api_key", type: "secret", required: true },
      { display: "API ID", name: "api_id", type: "string", required: true },
      { display: "Playground ID", name: "playgroundId", type: "string", required: true },
    ],
    versions: [{ version: "1.0.0", date: "2026-04-15", changes: ["Initial PAPI integration"] }],
    setupGuide:
      "In XSIAM, create a PAPI key with detection-read + remote-script-exec scopes, then supply CORTEX_MCP_PAPI_* env values.",
    dockerImage: "ghcr.io/kite-production/phantom-mcp:latest",
    runtime: "python",
    sdkLanguage: "Python",
    sdkPackage: "phantom-spark-xsiam-connector",
    ingestion: { enabled: false, mode: "pull", description: "Queries run on demand" },
    topAgents: [{ name: "phantom-soc-simulation", color: "#1f7bff" }],
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
      "Lets the agent reach the public web for IOC pivots, vendor advisories, threat-intel portal scraping, and 'go read this CVE writeup' requests. Talks to phantom-browser (a profile-gated sidecar) over Chrome DevTools Protocol via Playwright Python. The Allowed Domains list is the primary safety control — restrict the agent to vetted hosts. By default web.navigate is approval-gated; use the chat-header dropdown or a job's bypass slider to opt out per session/job.",
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
        defaultValue: "http://phantom-browser:9222",
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
          "Connects to phantom-browser sidecar via Playwright over CDP; profile-gated so it doesn't auto-start",
          "Trafilatura-powered readable text extraction",
          "allowed_domains hostname allow-list with .example.com suffix wildcard support",
          "web.navigate approval-gated by default; bypass via chat-header dropdown or job bypass slider",
        ],
      },
    ],
    setupGuide:
      "1) Bring up the sidecar: `docker compose --profile browser up -d phantom-browser`. 2) Click 'Add instance', leave cdp_url as the default. 3) Set Allowed Domains to your vetted threat-intel + vendor-doc hosts (use `.example.com` to match all subdomains). 4) Save. The agent will see web.* tools on its next refresh.",
    dockerImage: "ghcr.io/kite-production/phantom-browser:latest",
    runtime: "python",
    sdkLanguage: "Python",
    sdkPackage: "phantom-spark-web-connector",
    ingestion: {
      enabled: false,
      mode: "pull",
      description: "Pages are fetched on demand by the agent — no continuous ingestion.",
    },
    topAgents: [{ name: "phantom-soc-simulation", color: "#a855f7" }],
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
          "SystemExit-translation wrapper at the integration boundary so transient docs-API outages produce structured error returns instead of crashing phantom-agent",
          "Bundles cortex_xql_query_authoring foundation skill — six-step KB-search → stage/function-extraction → cortex-docs lookup → query-authoring workflow",
          "deep_research uses ANTHROPIC_API_KEY when available; falls back to built-in heuristic planner with no LLM dependency",
        ],
      },
    ],
    setupGuide:
      "1) Click 'Add instance' on the cortex-docs row. 2) Leave the defaults — the Cortex docs API is public, no credentials needed. 3) Save. The agent will see cortex-docs.* tools on the next refresh and the cortex_xql_query_authoring skill becomes operational. 4) (Optional) Set plannerModel to a Claude model id if you want cortex-docs/deep_research to use LLM-driven planning instead of the heuristic fallback.",
    dockerImage: "ghcr.io/kite-production/phantom-connector-cortex-docs:latest",
    runtime: "python",
    sdkLanguage: "Python",
    sdkPackage: "phantom-spark-cortex-docs-connector",
    ingestion: {
      enabled: false,
      mode: "pull",
      description: "Cortex docs are fetched on demand per tool call — no continuous ingestion.",
    },
    topAgents: [{ name: "phantom-soc-simulation", color: "#fa582d" }],
  },
  // ── cortex-content (v0.3.9) ──────────────────────────────────────────────
  {
    id: "cortex-content",
    name: "Cortex Content",
    type: "tool",
    version: "0.3.9",
    publisher: "kite-production",
    description:
      "Cortex content catalog bundled with Phantom — XSIAM/XSOAR content packs, ModelingRules, ParsingRules, CorrelationRules. Ten tools for listing/searching packs, fetching rule bundles, plus index_kb to embed pack content into the agent's semantic-search KB.",
    longDescription:
      "Gives the chat agent a reference for canonical XSIAM content. When operators ask 'show me how Cortex models cisco_esa_raw' or 'pull the F5APM modeling rule so I can adapt it', the agent uses cortex-content/get_modeling_rule to fetch the three-file bundle (.xif + .yml + _schema.json) from the local catalog. The agent uses these as references when authoring or updating data models for the operator's tenant — instead of guessing XDM paths (which produces broken parsers, as the v0.3.7 model-authoring session showed), it can ground each mapping against the canonical implementation. v0.3.9 adds cortex_index_kb which walks a pack's rules and upserts each into the agent's knowledge_search KB (kb_name='cortex-content'), enabling semantic search across the ~200 packs that ship ModelingRules without round-tripping through list/get tools per rule. Idempotent — source_hash dedupe means re-indexing is cheap. All reads are local file reads; no network calls.",
    category: "Security",
    tags: ["cortex", "xsiam", "xdm", "modeling-rules", "parsing-rules", "correlation-rules", "kb-embedding", "v0.3.9"],
    icon: "library_books",
    iconColor: "#1963b3",
    iconBg: "rgba(25, 99, 179, 0.12)",
    toolCount: 10,
    installs: "bundle-internal",
    installCount: 0,
    status: "installed",
    reliability: "stable",
    authType: "None — local catalog bundled with Phantom.",
    tools: [
      {
        name: "list_packs",
        method: "internal — pack listing",
        description:
          "List all packs in the bundled catalog, optionally filtered by supportedModules. Returns name + description + version + supportedModules per pack.",
        args: [
          { name: "supported_module", type: "string", description: "Filter by supportedModules (e.g. 'xsiam', 'agentix').", required: false },
          { name: "limit", type: "integer", description: "Max packs per page (default 100, max 500).", required: false },
          { name: "offset", type: "integer", description: "Pagination offset (default 0).", required: false },
        ],
      },
      {
        name: "search_packs",
        method: "GET + fuzzy match",
        description: "Fuzzy-search packs by name/description/keywords/categories.",
        args: [
          { name: "query", type: "string", description: "Search term — vendor / log source / category.", required: true },
          { name: "limit", type: "integer", description: "Max results (default 20, max 100).", required: false },
        ],
      },
      {
        name: "get_pack",
        method: "internal — pack lookup",
        description: "Fetch pack_metadata.json + top-level file tree + README for one pack.",
        args: [
          { name: "pack_name", type: "string", description: "Exact pack name (e.g. 'F5APM').", required: true },
        ],
      },
      {
        name: "list_modeling_rules",
        method: "internal — ModelingRules listing",
        description: "List ModelingRules directories under a pack with their datasets parsed from _schema.json.",
        args: [
          { name: "pack_name", type: "string", description: "Pack to list ModelingRules under.", required: true },
        ],
      },
      {
        name: "get_modeling_rule",
        method: "internal — three-file bundle",
        description:
          "Fetch the three-file bundle for ONE modeling rule: .xif (XQL code), .yml (metadata), _schema.json (dataset → field-type schema).",
        args: [
          { name: "pack_name", type: "string", description: "Pack containing the rule.", required: true },
          { name: "rule_name", type: "string", description: "Modeling rule directory name (usually same as pack name).", required: true },
        ],
      },
      {
        name: "list_parsing_rules",
        method: "internal — ParsingRules listing",
        description: "List ParsingRules directories under a pack.",
        args: [
          { name: "pack_name", type: "string", description: "Pack to list ParsingRules under.", required: true },
        ],
      },
      {
        name: "get_parsing_rule",
        method: "internal — three-file bundle",
        description: "Fetch .xif + .yml + _schema.json for one parsing rule.",
        args: [
          { name: "pack_name", type: "string", description: "Pack containing the rule.", required: true },
          { name: "rule_name", type: "string", description: "Parsing rule directory name.", required: true },
        ],
      },
      {
        name: "list_correlation_rules",
        method: "internal — CorrelationRules listing",
        description: "List CorrelationRules directories under a pack.",
        args: [
          { name: "pack_name", type: "string", description: "Pack to list CorrelationRules under.", required: true },
        ],
      },
      {
        name: "get_correlation_rule",
        method: "internal — .yml + .xql",
        description: "Fetch the .yml metadata + .xql query for one correlation rule.",
        args: [
          { name: "pack_name", type: "string", description: "Pack containing the rule.", required: true },
          { name: "rule_name", type: "string", description: "Correlation rule name.", required: true },
        ],
      },
    ],
    config: [],
    setupGuide:
      "No setup required. The Cortex content catalog is bundled with Phantom and read from local files — no configuration, no network, no credentials.",
    versions: [
      {
        version: "0.3.7",
        date: "2026-05-11",
        changes: [
          "Initial release — fetch surface only.",
          "9 tools for listing/searching packs.",
          "ModelingRules + ParsingRules + CorrelationRules fetch + cache.",
          "v0.3.8 will add semantic embedding (cortex-content KB via Vertex gemini-embedding-001).",
        ],
      },
    ],
    dockerImage: "ghcr.io/kite-production/phantom-mcp:latest",
    runtime: "python",
    sdkLanguage: "Python",
    sdkPackage: "phantom-spark-cortex-content-connector",
    ingestion: {
      enabled: false,
      mode: "pull",
      description: "Pack content fetched on demand per tool call; cached locally for 24h by default.",
    },
    topAgents: [{ name: "phantom-soc-simulation", color: "#1963b3" }],
  },

  // ── cortex-xdr (v0.5.61 base, v0.5.68 description rewrite) ───────────────
  {
    id: "cortex-xdr",
    name: "Cortex XDR",
    type: "tool",
    version: "0.1.1",
    publisher: "Palo Alto Networks / kite-production",
    description:
      "Cortex XDR API wrapper — list incidents and alerts, drill into specific cases, and run XQL queries against the XDR data lake. General-purpose interface for incident response, threat hunting, investigation reporting, and detection coverage validation.",
    longDescription:
      "Phantom's interface to your Cortex XDR tenant's Public API. The chat agent can answer operator questions like 'show me unresolved high-severity incidents in the last 24 hours', 'pull the alerts from incident <id>', or 'run XQL: dataset=xdr_data | filter agent_hostname=\"xdragent\" and event_type=ENUM.PROCESS | dedup actor_process_image_name | limit 50'. Four tools cover the core read paths: get_cases_and_issues (incident listing with filters by time, endpoint, severity, status), get_incident_extra_data (full alerts + network/file artifacts for a specific incident), run_xql_query (synchronous XQL with bounded polling — returns rows when complete or execution_id for long queries), and get_xql_results (poll an in-flight async execution). Same Cortex Public API family + Authorization + x-xdr-auth-id auth pattern as XSIAM; unified api_url / api_id / api_key field names per v0.5.59 / #35. Use cases: incident response (triage + drill-down), threat hunting (XQL ad-hoc queries), investigation reporting (incident details + related artifacts), and detection coverage validation (combine with Phantom's caldera connector — fire attacks, then query XDR for what fired). Read-only: no write/action endpoints in v0.1.x (isolate endpoint, run remote script, etc. deferred behind an explicit approval gate in a future release).",
    category: "Security",
    tags: ["cortex", "xdr", "edr", "siem", "incidents", "alerts", "xql", "threat-hunting", "investigation", "incident-response"],
    icon: "shield_lock",
    iconColor: "#ef4444",
    iconBg: "rgba(239, 68, 68, 0.12)",
    toolCount: 4,
    installs: "bundle-internal",
    installCount: 0,
    status: "installed",
    reliability: "stable",
    authType: "XDR Advanced API Key + auth-id",
    tools: [
      {
        name: "get_cases_and_issues",
        method: "POST /incidents/get_incidents",
        description: "List Cortex XDR incidents (cases) and the alerts (issues) within them. Supports filters by time, endpoint, severity, status.",
        args: [
          { name: "from_time", type: "string", description: "ISO timestamp lower bound. Default: 24h ago.", required: false },
          { name: "to_time", type: "string", description: "ISO timestamp upper bound. Default: now.", required: false },
          { name: "endpoint", type: "string", description: "Filter by endpoint hostname.", required: false },
          { name: "severity", type: "array", description: "Subset of ['low','medium','high','critical'].", required: false },
          { name: "status", type: "array", description: "Subset of XDR status values.", required: false },
          { name: "limit", type: "integer", description: "Max incidents (default 50, max 100).", required: false },
        ],
      },
      {
        name: "get_incident_extra_data",
        method: "POST /incidents/get_incident_extra_data",
        description: "Drill into one incident — full alerts, network/file artifacts, related users/hosts.",
        args: [
          { name: "incident_id", type: "string", description: "From a prior get_cases_and_issues hit.", required: true },
          { name: "alerts_limit", type: "integer", description: "Cap on alerts returned (default 50).", required: false },
        ],
      },
      {
        name: "run_xql_query",
        method: "POST /xql/start_xql_query + poll /xql/get_query_results",
        description: "Execute an XQL query synchronously against the XDR data lake. Returns rows if complete within the poll window, or execution_id if still running.",
        args: [
          { name: "query", type: "string", description: "XQL query text.", required: true },
          { name: "tenant_ids", type: "array", description: "Optional multi-tenant scope.", required: false },
          { name: "timeframe_from", type: "string", description: "ISO timestamp lower bound.", required: false },
          { name: "timeframe_to", type: "string", description: "ISO timestamp upper bound. Default: now.", required: false },
        ],
      },
      {
        name: "get_xql_results",
        method: "POST /xql/get_query_results",
        description: "Retrieve results from an in-flight XQL query by execution_id.",
        args: [
          { name: "execution_id", type: "string", description: "From a prior run_xql_query call.", required: true },
          { name: "limit", type: "integer", description: "Max rows (default 1000, max 10000).", required: false },
        ],
      },
    ],
    // v0.5.61 (issue #36): unified api_url / api_id / api_key field names
    // matching v0.5.59 / issue #35's XSIAM rename. Both connectors share
    // the same Cortex Public API auth model — operators don't translate.
    config: [
      { display: "API URL", name: "api_url", type: "url", required: true },
      { display: "API key", name: "api_key", type: "secret", required: true },
      { display: "API ID", name: "api_id", type: "string", required: true },
    ],
    versions: [
      { version: "0.1.0", date: "2026-05-17", changes: ["Initial connector — 4 tools: get_cases_and_issues, get_incident_extra_data, run_xql_query, get_xql_results. Closes #36."] },
      { version: "0.1.1", date: "2026-05-17", changes: ["Description + metadata rewritten to focus on general-purpose Cortex XDR API use (incident response, threat hunting, investigation reporting) rather than just Caldera-detection validation. Tags broadened (added siem/threat-hunting/investigation/incident-response; removed v0.5.61 + the narrow detection/validation focus)."] },
    ],
    setupGuide:
      "1) In the Cortex XDR console, navigate to Settings → Configurations → API Keys. 2) Generate a key with 'Advanced' security level (required for x-xdr-auth-id header path). 3) Copy the api_id (integer next to the key), api_key (long alphanumeric — paste raw, no 'Bearer' prefix), and api_url (format: https://api-yourtenant.xdr.us.paloaltonetworks.com). 4) Click 'Add instance' on the Cortex XDR card. 5) Paste, save. 6) Click 'Test Connection' on the new instance card — green check means creds valid. 7) Try natural-language queries via chat: 'show me unresolved high-severity incidents in the last 24h', 'pull the alerts from incident <id>', 'run XQL to count process events on hostname X yesterday'. The agent picks the right tool (get_cases_and_issues / get_incident_extra_data / run_xql_query) automatically based on your question.",
    dockerImage: "ghcr.io/kite-production/phantom-connector-cortex-xdr:latest",
    runtime: "python",
    sdkLanguage: "Python",
    sdkPackage: "phantom-spark-cortex-xdr-connector",
    ingestion: {
      enabled: false,
      mode: "pull",
      description: "Incidents + XQL results fetched on demand per tool call. No background polling.",
    },
    topAgents: [{ name: "phantom-soc-simulation", color: "#ef4444" }],
  },
];

/**
 * v0.15.5 — overlay live `spec.tools[]` from each connector.yaml on top
 * of the hardcoded metadata. Pre-v0.15.5 the toolCount + tools[] arrays
 * here were hand-maintained and drifted (operator-visible counts were
 * stale after R4/R5 expanded XDR/XSIAM from 8/14 → 50/59 tools).
 *
 * Resolution order for the bundle dir:
 *   1. /app/bundle/connectors/<id>/connector.yaml   (production, image-mounted)
 *   2. <repo>/bundles/spark/connectors/<id>/connector.yaml  (local dev)
 *
 * If neither exists OR the YAML parse fails, fall back to the hardcoded
 * tools[] + toolCount for that entry so the UI stays functional.
 */
async function loadLiveTools(connectorId: string): Promise<Tool[] | null> {
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
      const doc = yaml.load(text) as { spec?: { tools?: Array<Record<string, unknown>> } };
      const yamlTools = doc?.spec?.tools;
      if (!Array.isArray(yamlTools)) return null;
      const out: Tool[] = [];
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
        out.push({ name, method, description, args });
      }
      return out;
    } catch {
      // try next candidate
    }
  }
  return null;
}

export async function GET() {
  // Build a deep copy so concurrent requests don't see each other's overlay
  const out = PHANTOM_CONNECTORS.map((c) => ({ ...c, tools: [...c.tools] }));
  await Promise.all(
    out.map(async (c) => {
      const live = await loadLiveTools(c.id);
      if (live && live.length > 0) {
        c.tools = live;
        c.toolCount = live.length;
      }
    }),
  );
  return NextResponse.json(out);
}
