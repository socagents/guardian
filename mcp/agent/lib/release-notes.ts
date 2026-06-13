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
