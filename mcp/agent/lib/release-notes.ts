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
