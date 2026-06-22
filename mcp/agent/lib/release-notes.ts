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

// [guardian v0.1.0] Retired: the upstream Phantom release history
// (0.1.x–0.17.x entries) — Guardian is a new product whose history
// starts at v0.1.0; the inherited entries described removed subsystems.

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
    version: "0.2.52",
    date: "2026-06-22",
    title: "Hooks fail closed — a hook-store outage no longer silently disables policy.",
    security: true,
    highlights: [
      "Policy hooks no longer fail OPEN: if the hook store was briefly unreachable the dispatcher used to treat it as 'no hooks' and let the turn through, silently disabling block-policy hooks. A load failure now fails CLOSED on the events that can block an action (PreToolUse, UserPromptSubmit, PreCompact, RunStart, SubagentStart) — denied with a clear reason instead of slipping through.",
      "Non-blocking events (post-hoc, notifications) still proceed on an outage — there's nothing to enforce there.",
      "Escape hatch for availability-over-policy: set GUARDIAN_HOOKS_FAIL_OPEN=true to restore the previous proceed-without-hooks behavior.",
    ],
  },
  {
    version: "0.2.51",
    date: "2026-06-22",
    title: "Approval gating for high-impact actions — endpoint response, egress, skill authoring.",
    security: true,
    highlights: [
      "XSIAM response/EDR actions now require operator approval before running: endpoint isolate/unisolate/scan/scan-all, script + arbitrary-snippet execution, file quarantine, hash blocklist, IOC push/disable/enable, alert exclusions, dataset/distribution create. Enforced on the chat AND autonomous jobs paths (a bypass session/job records an auto_approved audit row). Read/investigation tools are unaffected.",
      "Outbound webhook export now actually gates: export_to_webhook was listed as approval-required but the gate never fired for built-in tools, so external data egress could happen unconfirmed. Fixed. webhook_preview stays read-only.",
      "Creating or editing a skill now requires approval (skills_create / skills_update join skills_delete behind the gate) — skill files are instructions the agent trusts next turn — and every create is audited (skill_created).",
    ],
  },
  {
    version: "0.2.50",
    date: "2026-06-22",
    title: "Audit coverage — every consequential action now leaves a trace.",
    security: true,
    highlights: [
      "Built-in tools are now audited: investigation, memory, jobs, knowledge, sessions and skills tools previously wrote no tool_call row, so a session or job using only built-ins was invisible in /observability/events + /traces. They now emit the same row connector tools do (actor, status, duration, argument names — never values).",
      "Job edits are audited: changing a job — and especially toggling bypass-approvals (which arms unattended auto-approval) — now records a job_updated event with the changed fields.",
      "Backup + restore audited and locked down: backup_exported + restore_applied events are written, and both endpoints are now session-only (API keys can't reach them, matching the credential routes). Restore force=true now actually overwrites a colliding instance instead of silently failing.",
      "Skill deletions are audited (skill_deleted), symmetric with the existing skill-edit audit.",
    ],
  },
  {
    version: "0.2.49",
    date: "2026-06-21",
    title: "In-product help refresh — clearer guides, complete journeys + API reference.",
    highlights: [
      "User Journeys catalog now lists every category — the Authentication and Connectors click-paths were previously hidden; added journeys for the investigation Assessment/Report/Campaign tabs and STIX export.",
      "REST API reference completed: added the investigation export endpoints (issue/case STIX bundles, generated report, related-case lookup) and gave the observability endpoints real descriptions.",
      "Every help page (User Guide, Architecture, API, Journeys) rewritten to plain present-tense descriptions of current behavior; the Architecture page gained an Investigation-tools reference and a capability-oriented module overview.",
    ],
  },
  {
    version: "0.2.48",
    date: "2026-06-21",
    title: "Export + interop — STIX 2.1, report templates, opt-in webhook handoff.",
    highlights: [
      "STIX 2.1 export: export_issue_stix / export_case_stix (+ a one-click Export STIX 2.1 on the Report + Campaign tabs) emit a standard bundle — incident/campaign + ATT&CK techniques + indicators + relationships — for any TIP/SIEM. Deterministic, pure assembly.",
      "Report templates: generate_investigation_report now takes a template — technical (full, default), executive (brief), or ioc-list (machine-pasteable); generate_campaign_report renders the case level.",
      "Outbound handoff (opt-in + approval-gated): export_to_webhook POSTs the verdict + report + IOCs + STIX to an operator-configured webhook. Off by default (until you set GUARDIAN_WEBHOOK_URL), sends only to your configured URL, asks for approval before every send. webhook_preview shows what would be sent first.",
      "Completes the structured-investigation arc (A–D): a machine-readable verdict, backed by multi-source evidence, rolled into campaigns, and now portable to the rest of your stack.",
    ],
  },
  {
    version: "0.2.47",
    date: "2026-06-21",
    title: "Campaign / cross-incident analytics — roll up, type by playbook, link & infer.",
    highlights: [
      "Campaign rollup: new case_rollup synthesizes a Case from its member issues (combined ATT&CK techniques, shared infrastructure — indicators on >1 issue — overall severity, verdict mix) and shows it on the case's new Campaign tab (Roll-up button, or automatic when Guardian resolves an incident in a campaign).",
      "Type investigations by playbook: issue_match_playbook records which KB playbook an investigation followed, so cases are queryable by playbook (e.g. all ransomware-playbook incidents).",
      "Link related campaigns: typed cross-case edges (case_relate / case_related) connect a case to a prior one — sibling / escalation / reopen / same-campaign — surfaced on the Campaign tab.",
      "Relationship inference (suggest-only): infer_relationships walks the indicator graph to suggest missing transitive edges (domain→IP→C2 ⇒ domain→C2) and sibling issues sharing a technique/indicator. Guardian suggests; the analyst confirms — no silent writes.",
      "The autonomous loop + judge now roll campaigns up and weigh campaign coherence.",
    ],
  },
  {
    version: "0.2.46",
    date: "2026-06-21",
    title: "Multi-source defensible depth — telemetry hunt, verdict pushback, containment rec.",
    highlights: [
      "Verdict pushback: new push_verdict_to_xsoar writes a resolved Issue's structured verdict + findings back to the upstream XSOAR incident's war room as pinned evidence — the disposition lives where the SOC works the case. Goes through the approval gate + audit; no-op for standalone Issues.",
      "XQL telemetry blast-radius hunt: the investigation skill pivots into XSIAM (xql_examples_search → xsiam_run_xql_query) to find the other hosts/accounts a bad indicator touched, and folds them into the structured blast radius. Degrades gracefully when no XSIAM instance is configured.",
      "xsiam_run_xql_query now takes lookback_hours (default 0.5 = backward-compatible 30 min; up to 7 days) + polls to completion — so blast-radius hunts scope days, not minutes.",
      "Containment recommendations (recommend-only): for true positives Guardian attaches a structured isolate-host / disable-account / block-indicator / run-playbook step with the exact action to approve. It never auto-contains — containment runs only when you approve it.",
      "Autonomous loop deepened: investigations now hunt telemetry + push the verdict back; the judge weighs cross-source depth and whether containment was considered for high/critical true positives.",
    ],
  },
  {
    version: "0.2.45",
    date: "2026-06-21",
    title: "Structured investigation outcome — verdict, blast radius, ATT&CK, report.",
    highlights: [
      "Investigation Issues gain a structured outcome: a verdict from a fixed set (true/false positive, benign, needs escalation, inconclusive), a 0-100% confidence, and a blast-radius object (hosts/accounts/data the attack touched). The Assessment tab renders the verdict chip, confidence meter, and blast-radius groups.",
      "ATT&CK technique mappings: confirmed techniques are recorded as structured rows (id + tactic + manifestation + evidence) and shown as chips — not only in prose. A cross-incident lookup answers 'which incidents involved this technique'.",
      "New Report tab: assembles the verdict, blast radius, techniques, indicators, and timeline into one shareable markdown report — generate/regenerate on demand.",
      "The agent does it automatically: the xsoar_case_investigation skill sets the structured verdict, maps techniques, and generates the report at resolve; the autonomous judge scores against the structured record; the Block-close-without-verdict hook accepts either the structured verdict or the legacy VERDICT: line.",
      "Backward-safe: existing investigations.db upgrades in place; the large report rides only on the issue-detail read.",
    ],
  },
  {
    version: "0.2.44",
    date: "2026-06-21",
    title: "XQL knowledge base + authoring skill for Cortex XSIAM.",
    highlights: [
      "New xql-examples knowledge base: 201 curated Cortex XSIAM XQL examples — reusable patterns + per-vendor alert-mapping queries, plus a new ATT&CK-aligned IR/threat-hunting set (48 hunts, technique-tagged). Browse at /knowledge; search from chat with knowledge_search.",
      "New xql_examples_search tool: finds example queries by intent and enriches each with the XQL stage syntax + dataset field lists it uses — author a query without a lookup per stage.",
      "New cortex_xql_query_authoring skill: chains the example KB with live Palo Alto Cortex docs (cortex-docs/xql_lookup) to compose pattern- and syntax-correct XQL.",
      "Investigation pivot: mid-case, go from an incident's indicators to XQL hunts that scope blast radius across XSIAM datasets, runnable via xsiam_run_xql_query.",
    ],
  },
  {
    version: "0.2.43",
    date: "2026-06-21",
    title: "XSOAR playbook tools — fixed end-to-end on fetched incidents.",
    highlights: [
      "run_playbook now works on a freshly-fetched, not-yet-investigated incident — it opens the war room the way the XSOAR UI does (the path the autonomous investigation loop relies on).",
      "run_playbook accepts a playbook id OR name — it resolves the id to the display name XSOAR's setPlaybook needs, so the id from import_playbook just works.",
      "import_playbook now returns the imported playbook's id + name (was blank) — hand them straight to run_playbook.",
      "get_playbook_state now lists every task (id, name, state, type), not just counts — see task-by-task progress and find a waiting manual task's id for complete_task.",
      "Verified against a live XSOAR 6 tenant: all 27 connector tools pass end-to-end (import → assign → run → monitor → complete).",
    ],
  },
  {
    version: "0.2.42",
    date: "2026-06-20",
    title: "Emulated services in the marketplace — first up: Splunk.",
    highlights: [
      "New marketplace kind: emulated SERVICES (alongside connectors). A service runs as a container Guardian publishes on a host port so an EXTERNAL system reaches it — the agent never calls it.",
      "Splunk (Emulated) ships as the first one: it speaks the splunkd REST API the XSOAR SplunkPy integration uses, returning simulated notable events. Point a real SplunkPy instance at it (host = your Guardian host, port 8089, unsecure=true).",
      "splunk-search + fetch-incidents + the Indicator Hunting playbook run end-to-end against the mimic with no real Splunk server.",
      "The mimic emits a rotating stream of notables on a fixed time grid (~1/min), so each XSOAR fetch picks up NEW simulated incidents (varied rules/urgencies/domains) while re-queries dedup cleanly.",
      "Services show a 'Service' badge + a Services filter on /connectors; they advertise zero agent tools and skip the agent's Test Connection (they're reached by external systems, not the agent).",
      "XSOAR connector gains 4 operational tools: check an integration instance's health + last fetch error, re-run its Test button, read its fetch-run history (diagnose a failing fetch from Guardian, not by reading XSOAR logs), and monitor a running playbook's per-task state to confirm it ran to success.",
      "Every SplunkPy command that uses the splunkd REST API (search, job-create/results/status/share, get-indexes, submit-event, notable-update) now round-trips against the Splunk mimic — verified with the real splunklib SDK.",
    ],
  },
  {
    version: "0.2.41",
    date: "2026-06-19",
    title: "New skill: simulate Splunk incidents in XSOAR.",
    highlights: [
      "Added the simulate_splunk_incidents workflow skill — creates synthetic Splunk incidents in XSOAR as if SplunkPy fetched + mapped them from Splunk ES.",
      "Covers all three Splunk incident types (Notable Generic, Finding, Investigation) with the exact post-mapping field names + valid select values baked in.",
      "Creates incidents with the MAPPED XSOAR fields (splunkurgency, splunkstatus, splunkdisposition, notableid, …), not the raw Splunk fields — so cases drive the Splunk layouts/playbooks.",
      "Requires the SplunkPy pack installed on the target tenant; the skill probes once and tells you if it isn't. Verified live on the v6 tenant.",
    ],
  },
  {
    version: "0.2.40",
    date: "2026-06-19",
    title: "Chat sidebar: your own conversations are findable again.",
    highlights: [
      "Autonomous-loop sessions are hidden from the chat session rail by default, so operator conversations aren't buried under scheduled-job churn.",
      "Scheduled-job sessions are now tagged at create time (not turn end), so even failed/timed-out ticks are correctly hidden.",
      "A boot backfill tags pre-existing loop sessions too, so the historical flood clears — reversible + idempotent.",
      "New 'Automated sessions' toggle under New Chat: HIDDEN (default) vs SHOWN to inspect loop runs. Remembered per browser.",
    ],
  },
  {
    version: "0.2.39",
    date: "2026-06-19",
    title: "Autonomous loop: fixed the silent timeouts behind empty sessions.",
    highlights: [
      "Root cause: the investigation loop's chat turn hit a hard 300s timeout (~60% of ticks), saving the prompt but not the assistant turn — so the session opened to just the seed prompt.",
      "The chat-action timeout is now configurable (JOB_CHAT_ACTION_TIMEOUT_S) and defaults to 20 min, so long investigations actually finish.",
      "Interrupted ticks no longer leave silent empty sessions: the session is closed and shows a '⚠️ Investigation interrupted' banner explaining it'll resume next tick.",
      "Next up: filtering autonomous-loop sessions out of the chat sidebar so your own conversations are easy to find.",
    ],
  },
  {
    version: "0.2.38",
    date: "2026-06-17",
    title: "API reference completed — every endpoint now fully documented.",
    highlights: [
      "Filled 65 placeholder ('schema is a follow-up') entries with real request bodies, params, response shapes, and risk tiers on /help/api.",
      "Added 28 endpoints that weren't listed at all — including the full Investigation surface (cases, issues, indicators) under a new 'Investigation' API category.",
      "Every entry was reconciled against its actual route handler + the embedded-MCP handler it forwards to — no guessed schemas.",
      "Fixed providers/config: was mislabeled POST; it's GET (read, secrets redacted) + PUT (write credentials, now flagged credential-tier).",
      "The OpenAPI 3.0 export (GET /api/agent/openapi) now reflects the complete 138-endpoint catalog. Docs only — no behavior change.",
    ],
  },
  {
    version: "0.2.37",
    date: "2026-06-16",
    title: "Help docs reconciled — architecture, user guide, journeys, API caught up.",
    highlights: [
      "Architecture: restored the XSIAM connector section (it was wrongly marked retired but returned in v0.2.27 as a 54-tool connector); fixed false 'no bundled KB' claims (6 KBs ship); documented the v0.2.31–36 XSOAR connector refinements.",
      "User guide: new 'Evidence on XSOAR 6 vs 8' explainer; corrected connector count/wording.",
      "Journeys: added starter 'Create an XSOAR instance' and 'Create a Cortex XSIAM instance' walkthroughs.",
      "API reference: fixed mislabeled catalog entries (instance test, connector lifecycle action, get-single-instance) + a real /api/chat schema. No behavior change — docs only.",
    ],
  },
  {
    version: "0.2.36",
    date: "2026-06-16",
    title: "Connector read-path polish: leaner XSIAM results + XSOAR v8 evidence read.",
    highlights: [
      "XSIAM tools no longer attach the full raw API response to every result (44 sites) — pure token bloat nothing consumed; results are now just the projected fields.",
      "xsoar_search_evidence now works on XSOAR 8: since Cortex 8's /evidence/search doesn't return tag-based evidence, it reads the war room filtered to the 'evidence' tag. Evidence is now listable on both v6 and v8.",
      "No installer change; xsiam + xsoar connector images rebuild.",
    ],
  },
  {
    version: "0.2.35",
    date: "2026-06-15",
    title: "XSOAR evidence: save_evidence works on v6 + compact evidence search.",
    highlights: [
      "Fixed save_evidence on XSOAR 6 — it used the entry-tag path, which optimistic-locked and never round-tripped into the evidence board; v6 now uses the formal POST /evidence (verified create → search).",
      "search_evidence returns a compact summary per item {id, entry_id, incident_id, description, marked_by, marked_date, tags} instead of the raw verbose record.",
      "Cortex 8 keeps the tag path (its /evidence POST isn't on the public API); documented that v8 /evidence/search won't list tag-based evidence (it's UI-only there).",
      "No installer change.",
    ],
  },
  {
    version: "0.2.34",
    date: "2026-06-15",
    title: "XSOAR indicator search actually filters now (+ compact, scored results).",
    highlights: [
      "Fixed a real bug: xsoar_search_indicators sent its query in a {filter:{…}} envelope, but /indicators/search takes a flat body — so XSOAR ignored the query, size AND page and returned the whole unfiltered store. Queries now actually filter.",
      "type:IP returns IPs, reputation:Bad / verdict:Malicious returns malicious indicators, size is honored. Verified live on the v6 tenant.",
      "Results are now a compact summary per indicator {id, type, value, score, reputation, source, …} instead of raw verbose store objects — much smaller payloads, score/reputation surfaced directly.",
      "Bug-family audited all xsoar tools; search_evidence (same pattern) tracked as a follow-up. No installer change.",
    ],
  },
  {
    version: "0.2.33",
    date: "2026-06-15",
    title: "Sharper XSOAR investigations — platform reference skill + lighter read path.",
    highlights: [
      "New xsoar_platform_reference skill: the agent now has an authoritative War Room / !command catalog + exact incident & indicator query-syntax tables, so it stops probing syntax variants and stops web-searching XSOAR concepts.",
      "'List active incidents + severity breakdown' now uses one query per severity bucket instead of a dozen syntax-variant calls; 'what is the War Room / what does !Print do' is answered from the skill, not a web search.",
      "Read-only requests (list / show / summarize / count) take a lighter path — no full local Issue/Case is created unless you actually enrich, decide a verdict, or write to the case.",
      "Skill content only — no installer change. Re-run your existing installer.",
    ],
  },
  {
    version: "0.2.32",
    date: "2026-06-15",
    title: "XSOAR v8 one-click playbook import via the Core REST API.",
    highlights: [
      "Playbook import into a Cortex 8 tenant now works one-click when the Core REST API integration is installed (previously always reported 'import unavailable').",
      "The connector imports via core-api-post /playbook/save (run in the instance's playground) when the direct v6 endpoint 405s; verified live on Cortex 8.",
      "Requires the Core REST API integration + the instance's playground_id; otherwise a clear guided-manual message. XSOAR 6 import is unchanged.",
    ],
  },
  {
    version: "0.2.31",
    date: "2026-06-15",
    title: "Fix: XSOAR list tools now actually create lists.",
    highlights: [
      "set_list / append_to_list now create a list if it doesn't exist (use !createList instead of !setList, which only updates existing lists).",
      "List writes now report real failures instead of returning ok=true when the underlying command errored.",
      "Found during the live XSOAR v6 smoke; affected both v6 and v8. No installer change.",
    ],
  },
  {
    version: "0.2.30",
    date: "2026-06-15",
    title: "Smarter XSOAR create form — Version first, version-aware fields.",
    highlights: [
      "The XSOAR instance form now leads with the Version dropdown; the fields below adapt to your choice.",
      "API key ID appears only for v8 (v6 uses the API key alone) — it's hidden, not-required, and not submitted for v6.",
      "Added the previously-missing Playground / War Room ID field — needed to run commands + the list tools on both versions.",
      "No installer change — re-run your existing installer.",
    ],
  },
  {
    version: "0.2.29",
    date: "2026-06-15",
    title: "Two tenants, one connector — multi-active instances + XSOAR v6/v8.",
    highlights: [
      "A connector can now run multiple enabled instances at once — e.g. an XSOAR 6 (on-prem) and an XSOAR 8 (cloud) tenant live simultaneously.",
      "The agent picks which tenant a tool acts on via an 'instance' argument, inferred from your request; ambiguous calls error with the valid choices instead of hitting the wrong tenant.",
      "Creating an XSOAR instance now has an explicit Version dropdown (v6 / v8) instead of inferring from api_id.",
      "Single-instance connectors are unchanged. No installer change — re-run your existing installer.",
    ],
  },
  {
    version: "0.2.28",
    date: "2026-06-15",
    title: "Connector instances start reliably + tell you what happened.",
    highlights: [
      "Creating an instance now shows explicit feedback: success closes the dialog, an error gets a red banner, and a container that needs a moment shows a 'still starting' notice.",
      "Connector containers self-heal — a container that failed to start is restarted automatically within ~5 minutes, instead of staying down.",
      "Fixed hyphenated connector ids (cortex-docs) being dropped from container reconcile + the digests listing.",
      "No installer change — re-run your existing installer; volumes preserved.",
    ],
  },
  {
    version: "0.2.27",
    date: "2026-06-15",
    title: "Cortex XSIAM connector — investigation + EDR response.",
    highlights: [
      "New Cortex XSIAM connector in the marketplace — add an instance with your tenant API host + the Cortex public-API key pair, then investigate and respond from chat (mirrors XSOAR).",
      "54 tools: XQL queries, incidents/alerts/issues, assets, audit, datamodel — plus EDR response (endpoint isolate/scan/quarantine, script execution, IOC + hash blocklisting).",
      "Every write/response tool is approval-gated; the destructive remove_lookup_data is denied outright.",
    ],
  },
  {
    version: "0.2.26",
    date: "2026-06-14",
    title: "Deploy + test-run playbooks — close the builder loop.",
    highlights: [
      "Playbook Builder gains a Deploy + test-run button: import a drafted playbook into your XSOAR tenant, run it on a throwaway test incident, see the outcome, and auto-close the incident.",
      "New xsoar_import_playbook connector tool — approval-gated, uses the instance API key.",
      "Generation-aware: direct one-click import on XSOAR 6 (or Cortex 8 + Core REST API); on a plain Cortex 8 tenant Guardian gives manual-import guidance and still runs the test.",
    ],
  },
  {
    version: "0.2.25",
    date: "2026-06-14",
    title: "Knowledge detail pages show the full entry count + render code and tables.",
    highlights: [
      "Large KBs now show their true entry count (mitre-attack-enterprise: 697, soar-playbooks: 798) with a Load more button to browse them all.",
      "MITRE code snippets in entry bodies render as code blocks instead of raw <code> text.",
      "Agent comparison tables now render as real tables in chat and the KB drawer (GitHub-flavored markdown).",
    ],
  },
  {
    version: "0.2.24",
    date: "2026-06-14",
    title: "Playbook Builder — draft a Cortex XSOAR playbook from a use-case.",
    highlights: [
      "New /playbooks/build page: describe what a playbook should do and the agent drafts it, grounded in the ~800 real playbooks in the soar-playbooks KB.",
      "Every draft is structurally validated (required fields + task-graph integrity) and downloadable as YAML, with the example playbooks cited.",
      "The first generative use of the knowledge layer — the agent uses real playbooks as worked examples.",
      "Output is a draft to review + import into Cortex XSOAR; the builder never deploys to a tenant.",
    ],
  },
  {
    version: "0.2.23",
    date: "2026-06-14",
    title: "Sharper KB grounding — specialist matrices stay out of IT investigations' context.",
    highlights: [
      "With six KBs, the per-turn context occasionally pulled an ICS or Mobile technique into an IT case; that's fixed.",
      "Passive context now excludes the specialist ecosystems (OT/Mobile/AI); the agent still searches them directly when a case calls for it.",
      "Configurable per deployment via manifest.context.passiveExcludeEcosystems.",
    ],
  },
  {
    version: "0.2.22",
    date: "2026-06-14",
    title: "MITRE ATT&CK ICS + Mobile knowledge bases complete the matrix family.",
    highlights: [
      "New mitre-attack-ics KB (97 docs): the ATT&CK for ICS / OT matrix — SCADA, PLC, HMI attacks.",
      "New mitre-attack-mobile KB (124 docs): the ATT&CK for Mobile matrix (Android/iOS).",
      "Same generator + baked embeddings as ATT&CK Enterprise; six bundled KBs now, ~1,973 docs total.",
      "Always loaded; scope to mitre-attack-enterprise or the ecosystem tag for IT-only investigations.",
    ],
  },
  {
    version: "0.2.21",
    date: "2026-06-14",
    title: "SOAR Playbooks knowledge base — ~800 Cortex XSOAR response playbooks.",
    highlights: [
      "New soar-playbooks KB: ~800 out-of-the-box Cortex XSOAR playbooks from the MIT-licensed demisto/content repo (SOC-relevant packs, ~77 products).",
      "Search by what a playbook DOES — the embedded text is a reviewed description; the raw playbook YAML is kept in each entry.",
      "Dual-labeled by product/pack and investigation-type, both filterable with the tag chips.",
      "The agent can now find an existing response playbook during a case; later, these are worked examples for building playbooks.",
    ],
  },
  {
    version: "0.2.20",
    date: "2026-06-14",
    title: "Filter knowledge bases by tag — tactic, platform, and more.",
    highlights: [
      "Open any KB on /knowledge and click tag filter chips to narrow the entries (e.g. Windows credential-access techniques).",
      "Both browsing and semantic search respect the selected tags (AND filter).",
      "Big MITRE KBs are now easy to navigate by tactic/platform; the substrate also powers the upcoming playbook KB's product/use-case labels.",
      "The agent's knowledge_search can now scope a search by tag too.",
    ],
  },
  {
    version: "0.2.19",
    date: "2026-06-14",
    title: "MITRE ATLAS (AI security) is now a built-in knowledge base.",
    highlights: [
      "New mitre-atlas KB: the ATT&CK-style framework for attacks on AI/ML systems — prompt injection, model evasion, data poisoning, agent hijacking.",
      "227 docs: 170 techniques + sub-techniques plus 57 real-world AI-incident case studies.",
      "AI techniques cross-link to their ATT&CK Enterprise mapping; embeddings baked in (zero Vertex calls at boot).",
      "Guardian now grounds investigations of AI-targeting incidents — apt as it's itself an AI agent.",
    ],
  },
  {
    version: "0.2.18",
    date: "2026-06-14",
    title: "Full MITRE ATT&CK Enterprise is now a built-in knowledge base (~697 techniques).",
    highlights: [
      "New mitre-attack-enterprise KB: the complete ATT&CK Enterprise matrix — every technique + sub-technique, with detection analytics and mitigations.",
      "Generated faithfully from the official MITRE STIX bundle (v19.1); regenerates on each MITRE release.",
      "Embeddings baked into the bundle, so all ~697 docs load instantly with zero Vertex calls at boot.",
      "Investigations now ground in the authoritative technique definition; soc-investigation stays as the curated 'how to investigate' guide.",
      "ATT&CK® © The MITRE Corporation, reproduced under the ATT&CK Terms of Use.",
    ],
  },
  {
    version: "0.2.17",
    date: "2026-06-14",
    title: "Knowledge bases can ship embeddings baked in — large KBs install in seconds, not minutes.",
    highlights: [
      "Infrastructure keystone for the knowledge-base expansion (full MITRE ATT&CK, ATLAS, SOAR playbooks).",
      "A KB can ship pre-computed embeddings in the bundle, so it loads with zero Vertex calls at boot.",
      "Baked vectors are trusted only when the model + dimensions match the runtime embedder — otherwise it re-embeds (self-healing).",
      "New authoring tool kb_embed.py bakes embeddings into a KB at build time.",
    ],
  },
  {
    version: "0.2.16",
    date: "2026-06-14",
    title: "SOC Investigation knowledge base — the agent now grounds cases in curated tradecraft.",
    highlights: [
      "New bundled knowledge base 'soc-investigation' (30 docs): 20 MITRE ATT&CK technique investigation guides + 10 IR playbooks.",
      "The /knowledge page is no longer empty — browse all 30 entries and search them semantically (Vertex text-embedding-004).",
      "Every investigation now consults the KB first: technique manifestation signals, ordered investigation steps, and the matching response playbook.",
      "Knowledge vs memory: knowledge is curated, read-only reference shipped in the bundle; memory is the agent's mutable, accumulated org facts.",
    ],
  },
  {
    version: "0.2.15",
    date: "2026-06-13",
    title: "Docs synced with the harness after a 20-incident end-to-end test.",
    highlights: [
      "Architecture page now documents the autonomous investigation loop (seeder → loop → judge), the self-improving judge with rollback, and subagent tool-result truncation.",
      "User guide gains an 'Autonomous investigation loop' section under Jobs, incl. how to review/roll back autonomous skill edits.",
      "list_integrations documented as the discovery step in the XSOAR tool family.",
    ],
  },
  {
    version: "0.2.14",
    date: "2026-06-13",
    title: "Subagent investigations scale on busy tenants.",
    highlights: [
      "Subagent tool results are now truncated like the main agent's — a single broad XSOAR read can no longer blow the subagent's context window (the Vertex 1M-token limit).",
      "Threat-hunter blast-radius hunts and other subagent investigations now complete on busy tenants instead of failing on overflow.",
    ],
  },
  {
    version: "0.2.13",
    date: "2026-06-13",
    title: "Guardian can now discover which SOAR integrations + commands are available.",
    highlights: [
      "New xsoar_list_integrations tool: lists the integrations configured on the Cortex XSOAR tenant and the commands each one exposes.",
      "Pairs with run_command — the agent learns which !commands actually exist (and their arguments) instead of guessing.",
      "Filter to one integration with brand=... to get full command argument specs.",
    ],
  },
  {
    version: "0.2.12",
    date: "2026-06-13",
    title: "Autonomous investigation self-improvement — with audited, reversible skill edits.",
    security: true,
    highlights: [
      "The investigation loop now evaluates its own resolved cases against a SOC rubric and improves the investigation skill automatically (the new guardian-investigation-judge).",
      "Every skill edit — operator OR agent — now writes a timestamped rollback snapshot under skills/.history and a skill_updated audit row visible in /observability/events.",
      "The judge is tightly scoped (reads investigations + edits only the investigation skill) and bounded (one additive, lifecycle-preserving edit per run).",
    ],
  },
  {
    version: "0.2.11",
    date: "2026-06-13",
    title: "Investigation loop hardening + codification.",
    highlights: [
      "The Issues list can now filter to only incident-tracking Issues (source_ref_not_null) and sort oldest-first — used by the autonomous loop to deterministically pick the oldest open case.",
      "The investigation-loop + incident-seeder jobs are now codified in scripts/bootstrap_loop_jobs.sh, so the loop survives a fresh install / volume wipe.",
      "The loop now groups related incidents into Cases as it investigates.",
    ],
  },
  {
    version: "0.2.10",
    date: "2026-06-13",
    title: "Connector instance config edits take effect immediately.",
    highlights: [
      "Editing a connector instance's config or secrets (e.g. XSOAR playground_id, a URL, an API key) now applies within seconds — no manual container restart.",
      "Saving the instance form recreates the connector container so it re-reads the new config at boot.",
      "Only fires when config/secrets actually changed and the instance is enabled; renames and tool-toggles don't trigger a restart.",
    ],
  },
  {
    version: "0.2.9",
    date: "2026-06-13",
    title: "Hooks & policies now reliably match connector tools.",
    security: true,
    highlights: [
      "Fixed: hook tool-globs, job permission policies, and subagent tool scopes silently missed connector tools the model named in dotted form (xsoar.close_incident vs xsoar_close_incident).",
      "The 'Block close without verdict' hook now actually denies a no-verdict close — with an audit row.",
      "A subagent's deny glob now reliably blocks the connector tools it shouldn't reach (privilege-scoping gap closed).",
      "Tool globs everywhere are now separator-insensitive — author them with either '.' or '_'.",
    ],
  },
  {
    version: "0.2.8",
    date: "2026-06-13",
    title: "Tasks page — clearer purpose + modernized presentation.",
    highlights: [
      "The /tasks page now states what it's for: long-running background work the agent or you spawned (enrichment sweeps, compactions, subagent hunts, hook runs).",
      "Added summary cards (total/running/succeeded/failed) and a cleaner status filter.",
      "Slimmer task rows with status + kind badges; progress, abort, and details retained.",
    ],
  },
  {
    version: "0.2.7",
    date: "2026-06-13",
    title: "Agents page modernized — subagent CRUD with a tabbed, scoped-tools editor.",
    highlights: [
      "The /agents page gets summary cards, origin + name filters, and slimmer definition rows.",
      "The create/edit drawer is wider and tabbed: Definition · Tools (allow/deny globs) · Execution.",
      "Define a subagent (e.g. a threat-hunting agent) with a scoped tool catalog, then the chat agent can spawn it.",
    ],
  },
  {
    version: "0.2.6",
    date: "2026-06-13",
    title: "Fixes — /jobs page loads, job chat sessions render, hooks UI polish.",
    highlights: [
      "Fixed the /jobs page 'unable to load jobs' error (a stale session-cookie name in the server-side fetch).",
      "Chat sessions created by scheduled jobs now show the real request + response (the skill body collapses into a chip).",
      "Hooks editor drawer widened to ~50%; the title description renders as a compact subtitle.",
    ],
  },
  {
    version: "0.2.5",
    date: "2026-06-13",
    title: "Two built-in incident-response hooks — verdict gate + malicious-indicator flag.",
    highlights: [
      "Block close without verdict: denies xsoar_close_incident when the Guardian Issue has no recorded VERDICT — install from /settings/hooks, no code.",
      "Flag malicious indicator: injects a confirmed-bad flag when an enrichment returns DBotScore 3, nudging containment.",
      "Both are in-process built-ins (no subprocess, no host scripts) and never touch secrets — install via dropdown + a tool glob.",
    ],
  },
  {
    version: "0.2.4",
    date: "2026-06-13",
    title: "Hooks page modernized — stat cards, filters, tabbed editor.",
    highlights: [
      "The /settings/hooks page gets summary cards (total / enabled / disabled / fail-closed) and an event + name filter.",
      "Hook rows are slimmer — event, transport, and fail-closed at a glance.",
      "The create/edit drawer is now a glass panel with tabbed fields (Metadata · Matching · Transport · Execution).",
      "Pure UI polish — no change to the hook engine, transports, or events.",
    ],
  },
  {
    version: "0.2.3",
    date: "2026-06-13",
    title: "Investigation diagram hardening — no more silent spinners.",
    highlights: [
      "Generate/Regenerate now reports an error instead of spinning silently for 3 minutes if the agent run fails.",
      "Diagram-SVG sanitizer hardened to also strip <foreignObject> and unquoted event handlers.",
      "Small correctness + documentation-accuracy fixes from a post-release code review.",
    ],
  },
  {
    version: "0.2.2",
    date: "2026-06-13",
    title: "Case-view diagrams — campaign-level attack chain + relations canvas.",
    highlights: [
      "Case detail is now tabbed: Issues · Attack chain · Relations.",
      "The Attack chain tab draws one causal diagram across all the case's issues — the campaign kill-chain.",
      "The Relations tab draws one STIX graph over the union of the case's indicators — the shared infrastructure, techniques, and actors.",
      "Both generate on demand, the same way as the per-issue diagrams.",
    ],
  },
  {
    version: "0.2.1",
    date: "2026-06-13",
    title: "Relations canvas — STIX indicator attribution + a relationship graph per issue.",
    highlights: [
      "New Relations tab on each issue: a STIX graph of its indicators and how they relate to techniques, malware, campaigns, and actors.",
      "Guardian attributes indicators — resolves-to, indicates, uses, attributed-to — using STIX verbs that round-trip with XSOAR + MITRE ATT&CK.",
      "Each indicator's detail now lists its relationships (source → verb → target).",
      "Draw the relations canvas on demand from the tab, just like the attack chain.",
    ],
  },
  {
    version: "0.2.0",
    date: "2026-06-13",
    title: "Indicators — a deduped IoC record across investigations.",
    highlights: [
      "New Investigation → Indicators page: every IoC Guardian sees, deduped by value + type.",
      "Guardian records the IoCs it enriches and imports the indicators XSOAR already extracted on case fetch.",
      "Click an indicator to see its reputation, enrichment, and every issue it appears in (cross-case correlation).",
      "Each issue gains an Indicators tab; per-issue-type layouts tailor the view to phishing / malware / lateral-movement / access-violation.",
    ],
  },
  {
    version: "0.1.10",
    date: "2026-06-13",
    title: "Attack-chain diagrams — tactic colors, MITRE mapping, attribution, animation.",
    highlights: [
      "Attack chains are now color-coded by ATT&CK tactic, with a legend.",
      "Each stage shows its tactic; each arrow shows the technique id + name (no more clipped labels).",
      "Adds an attribution line (actor/campaign) and subtle animated arrows.",
    ],
  },
  {
    version: "0.1.9",
    date: "2026-06-13",
    title: "Investigation text renders as markdown; Activity is filterable.",
    highlights: [
      "Issue fields + activity + case descriptions now render as formatted markdown (like the chat window).",
      "Activity timeline: filter by event type (action / finding / note) and sort oldest/newest.",
    ],
  },
  {
    version: "0.1.8",
    date: "2026-06-13",
    title: "Attack-chain diagrams — Guardian draws the causality chain.",
    highlights: [
      "Each investigation gets an SVG attack chain on the issue's 'Attack chain' tab.",
      "Generated automatically when an investigation resolves; regenerate on demand.",
      "Shows the causal path: entry → pivots → action → impact, with technique-labelled arrows.",
      "Rendered sandboxed (SVG-in-img) so agent-produced markup can never execute.",
    ],
  },
  {
    version: "0.1.7",
    date: "2026-06-13",
    title: "Investigation pages redesigned — full-width, tabbed, faster cases.",
    highlights: [
      "Issues + Cases pages now full-width with summary stats, filter chips, and glass cards (matching Skills/Jobs).",
      "Issue detail split into tabs: Overview · Assessment · Activity · Attack chain.",
      "Issue summaries show a derived VERDICT banner at a glance.",
      "Cases list loads much faster — the per-case issue count is now one query instead of N+1.",
    ],
  },
  {
    version: "0.1.6",
    date: "2026-06-13",
    title: "Investigation skill — scope the blast radius before resolving.",
    highlights: [
      "Investigations now enumerate blast radius in-investigation instead of deferring it to next-steps.",
      "Every confirmed-bad indicator/principal is pivoted outward (other affected hosts + co-sighting cases).",
      "Each Issue states scope as a one-line count ('seen on N hosts / M cases') or 'contained to this host'.",
    ],
  },
  {
    version: "0.1.5",
    date: "2026-06-12",
    title: "Investigation skill hardening — sharper, more complete case write-ups.",
    highlights: [
      "Investigation skill now teaches the full XSOAR tool surface (enrich_indicator, run_command, lists, playbooks).",
      "Every investigation builds an IoC/principal ledger — no case resolves with indicators left un-enriched.",
      "Resolution gate: a case isn't 'resolved' while competing root causes are undiscriminated.",
      "Each Issue leads with an explicit VERDICT line + MITRE ATT&CK technique tags.",
      "Fixed a frontmatter bug that silently disabled the skill's auto-load trigger in chat.",
    ],
  },
  {
    version: "0.1.4",
    date: "2026-06-12",
    title: "Agent chat resilience — long investigations survive transient Vertex socket resets.",
    highlights: [
      "Scheduled investigation jobs no longer die mid-run with 'chat error event: fetch failed'.",
      "Model-call retry now covers transient socket resets (UND_ERR_SOCKET / ECONNRESET / timeouts), not just 429 quota.",
      "Same exponential backoff + jitter as the existing 429 retry; real errors still surface immediately.",
    ],
  },
  {
    version: "0.1.3",
    date: "2026-06-12",
    title: "Investigation module — local Issues & Cases for every investigation.",
    highlights: [
      "New Investigation area (sidebar): Issues + Cases — Guardian's own record of its investigations.",
      "Guardian opens a local Issue when it works a case, logs each step + finding, and records the verdict.",
      "Rich issue layout: summary, scope, recommendations, conclusions, next steps + an activity timeline.",
      "Group related Issues into Cases; create Issues + Cases yourself too.",
      "guardian-updater reconcile/digests no longer crashes when a connector image was pruned.",
    ],
  },
  {
    version: "0.1.2",
    date: "2026-06-12",
    title: "XSOAR action toolset — run commands, enrich indicators, manage lists, create cases.",
    highlights: [
      "XSOAR connector grows to 21 tools: run any !command in a configured playground War Room.",
      "Enrich IPs/URLs/domains/files/CVEs → DBotScore reputation, inline in chat.",
      "Manage XSOAR Lists (allow/block) — read, overwrite, append.",
      "Create incidents and run playbooks on cases directly from Guardian.",
      "New optional playground_id field on the XSOAR instance powers the command tools.",
    ],
  },
  {
    version: "0.1.1",
    date: "2026-06-12",
    title: "Default chat-model picker — set a default model on Settings → Models.",
    highlights: [
      "Set a default chat model on Settings → Models; new chats use it automatically (no more 'auto').",
      "Chat dropdown chip shows 'Default — <model>' when an operator default is active.",
      "Per-chat model override still works; the next new chat resets to the default.",
      "Resolution chain: per-chat override → operator default → GEMINI_MODEL env → hardcoded fallback.",
    ],
  },
  {
    version: "0.1.0",
    date: "2026-06-11",
    title: "Guardian initial release — AI incident-investigation agent for Cortex XSOAR.",
    highlights: [
      "Guardian debuts: an AI agent that monitors, investigates, documents, and closes Cortex XSOAR cases.",
      "New XSOAR connector — 13 tools for the case lifecycle; supports XSOAR 6 and XSOAR 8 / Cortex cloud.",
      "Focused roster: XSOAR + Cortex docs + web research. XSIAM, Cortex XDR, content catalog, and XQL removed.",
      "IR agent semantics: an investigation system prompt driving monitor → fetch → investigate → update/close.",
      "Two XSOAR skills — case investigation (end-to-end) and case triage — plus Cortex-docs research skills.",
      "Credential guardrail intact: the agent holds no credential tools; secret management stays REST-only.",
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
