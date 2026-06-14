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
