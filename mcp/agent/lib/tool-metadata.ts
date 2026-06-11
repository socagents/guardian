/**
 * Tool metadata table — Round-15 / Phase R.
 *
 * Adapted from SnowAgent's Tool contract (snow-agent-complete/snow-
 * agent/06-tools-permissions/Tool.ts), which carries `readOnly`,
 * `destructive`, `openWorld`, `concurrencySafe` flags inline on the
 * tool definition. Guardian's MCP tools come from the FastMCP
 * connector loader and don't expose these flags in their schemas;
 * this curated table fills the gap.
 *
 * Why a table instead of pushing flags into manifest's tool specs:
 *
 *   - Adding fields to `bundles/spark/connectors/<id>/connector.yaml`
 *     forces every connector author to know the agent-runtime
 *     vocabulary.
 *   - Many tools are already deployed; backfilling 80 tool specs is
 *     a churn-heavy diff per connector.
 *   - The metadata is fundamentally agent-runtime concerns, not
 *     contract concerns — it changes meaning as the chat-route's
 *     orchestration policies evolve.
 *
 * What the chat-route uses each flag for:
 *
 *   readOnly         — affects nothing today. Future: skip the
 *                      audit-row write for read-only calls (they're
 *                      already in tool_call audit), reducing audit
 *                      log volume.
 *   destructive      — surfaces a red border on the approval card.
 *                      Round-12 Phase 11 already gates these via
 *                      manifest.approvals.humanRequired[]; this is
 *                      the visual.
 *   openWorld        — the tool can trigger external side effects
 *                      (Slack post, webhook fire). Currently visual
 *                      only — amber border on approval card.
 *   concurrencySafe  — Phase R parallel batch: when the model
 *                      fires N tools in one turn AND ALL of them
 *                      are concurrencySafe, the chat-route
 *                      `Promise.all`s them instead of running
 *                      serially. Cuts latency for read-heavy turns.
 *
 * Defaults (when a tool isn't in the table):
 *   readOnly: false        — assume it might write
 *   destructive: false     — assume not unless we know
 *   openWorld: false       — assume self-contained
 *   concurrencySafe: false — fail-safe: assume serial-only
 */

export interface ToolMetadata {
  readOnly: boolean;
  destructive: boolean;
  openWorld: boolean;
  concurrencySafe: boolean;
  /** Optional one-line description shown on hover in the approval
   *  card. Free text; just operator-facing context. */
  hint?: string;
}

const DEFAULT_METADATA: ToolMetadata = {
  readOnly: false,
  destructive: false,
  openWorld: false,
  concurrencySafe: false,
};

/**
 * Curated metadata table. Keyed by tool name (legacy flat AND v1.2
 * namespaced — both register the same metadata). Operator-facing,
 * so don't list low-level helpers — only tools the model is
 * realistically going to call.
 */
export const TOOL_METADATA_TABLE: Record<string, ToolMetadata> = {
  // ── XSOAR read-only / informational ───────────────────────────
  // These fetch case (incident) data without mutating anything.
  // concurrencySafe so the agent can fan out reads (e.g. pull
  // several incidents in parallel while triaging a queue).

  xsoar_list_incidents: {
    readOnly: true,
    destructive: false,
    openWorld: false,
    concurrencySafe: true,
    hint: "Lists XSOAR incidents (cases) with filters.",
  },
  xsoar_get_incident: {
    readOnly: true,
    destructive: false,
    openWorld: false,
    concurrencySafe: true,
    hint: "Fetches full data for one XSOAR incident.",
  },
  xsoar_get_war_room: {
    readOnly: true,
    destructive: false,
    openWorld: false,
    concurrencySafe: true,
    hint: "Reads the War Room entry timeline for an incident.",
  },
  xsoar_list_incident_types: {
    readOnly: true,
    destructive: false,
    openWorld: false,
    concurrencySafe: true,
  },
  xsoar_get_incident_fields: {
    readOnly: true,
    destructive: false,
    openWorld: false,
    concurrencySafe: true,
  },
  xsoar_search_indicators: {
    readOnly: true,
    destructive: false,
    openWorld: false,
    concurrencySafe: true,
    hint: "Searches XSOAR threat indicators.",
  },
  xsoar_search_evidence: {
    readOnly: true,
    destructive: false,
    openWorld: false,
    concurrencySafe: true,
    hint: "Searches the evidence board for an incident.",
  },
  xsoar_health_check: {
    readOnly: true,
    destructive: false,
    openWorld: false,
    concurrencySafe: true,
    hint: "Probes XSOAR API reachability + auth.",
  },

  // ── XSOAR state-changing (case mutations) ─────────────────────
  // These write to the operator's XSOAR tenant — add entries/notes,
  // update fields, store evidence, close cases. Destructive so the
  // operator sees the red border AND humanRequired gates them. Not
  // concurrencySafe: two writes to the same case can race.

  xsoar_add_entry: {
    readOnly: false,
    destructive: true,
    openWorld: false,
    concurrencySafe: false,
    hint: "Posts a War Room entry to an incident.",
  },
  xsoar_add_note: {
    readOnly: false,
    destructive: true,
    openWorld: false,
    concurrencySafe: false,
    hint: "Adds an investigation note to an incident.",
  },
  xsoar_update_incident: {
    readOnly: false,
    destructive: true,
    openWorld: false,
    concurrencySafe: false,
    hint: "Updates incident fields (severity, owner, status, custom).",
  },
  xsoar_save_evidence: {
    readOnly: false,
    destructive: true,
    openWorld: false,
    concurrencySafe: false,
    hint: "Saves an entry to the incident's evidence board.",
  },
  xsoar_close_incident: {
    readOnly: false,
    destructive: true,
    openWorld: false,
    concurrencySafe: false,
    hint: "Closes an XSOAR incident with a resolution.",
  },

  // ── Self-modification (Phase 11) ─────────────────────────────
  // These mutate Guardian's own state. Always destructive=true so
  // the operator sees the red border AND humanRequired gates them.

  jobs_create: {
    readOnly: false,
    destructive: false,
    openWorld: false,
    concurrencySafe: false,
    hint: "Creates a scheduled chat-action job.",
  },
  jobs_update: {
    readOnly: false,
    destructive: false,
    openWorld: false,
    concurrencySafe: false,
  },
  jobs_delete: {
    readOnly: false,
    destructive: true,
    openWorld: false,
    concurrencySafe: false,
    hint: "Deletes a scheduled job. Irreversible.",
  },
  personality_update: {
    readOnly: false,
    destructive: false,
    openWorld: false,
    concurrencySafe: false,
  },
  personality_reset: {
    readOnly: false,
    destructive: true,
    openWorld: false,
    concurrencySafe: false,
    hint: "Resets the agent persona to bundle defaults.",
  },
  settings_update: {
    readOnly: false,
    destructive: false,
    openWorld: false,
    concurrencySafe: false,
  },
  settings_reset: {
    readOnly: false,
    destructive: true,
    openWorld: false,
    concurrencySafe: false,
  },
  api_keys_create: {
    readOnly: false,
    destructive: false,
    openWorld: false,
    concurrencySafe: false,
    hint: "Mints a new operator-scoped API key. Plaintext shown once.",
  },
  api_keys_rotate: {
    readOnly: false,
    destructive: true, // old key is invalidated
    openWorld: false,
    concurrencySafe: false,
  },
  api_keys_revoke: {
    readOnly: false,
    destructive: true,
    openWorld: false,
    concurrencySafe: false,
  },

  // Memory writes
  memory_store: {
    readOnly: false,
    destructive: false,
    openWorld: false,
    concurrencySafe: false,
  },
  memory_search: {
    readOnly: true,
    destructive: false,
    openWorld: false,
    concurrencySafe: true,
  },
  memory_list: {
    readOnly: true,
    destructive: false,
    openWorld: false,
    concurrencySafe: true,
  },
  memory_delete: {
    readOnly: false,
    destructive: true,
    openWorld: false,
    concurrencySafe: false,
  },
};

/** Resolve metadata for a tool. Tries the exact tool name, then
 *  the legacy form (replacing `.` with `_`), then the namespaced
 *  form, then falls through to the default. */
export function resolveToolMetadata(toolName: string): ToolMetadata {
  if (TOOL_METADATA_TABLE[toolName]) {
    return TOOL_METADATA_TABLE[toolName];
  }
  // Try the alternate namespacing: v1.2 namespaced
  // `<connector>.<tool>` ↔ legacy `<connector>_<tool>`.
  if (toolName.includes(".")) {
    const flat = toolName.replace(/\./g, "_");
    if (TOOL_METADATA_TABLE[flat]) return TOOL_METADATA_TABLE[flat];
  } else if (toolName.includes("_")) {
    // Try replacing the FIRST underscore with a dot (most common
    // pattern: connector_tool → connector.tool).
    const idx = toolName.indexOf("_");
    const dotted =
      toolName.slice(0, idx) + "." + toolName.slice(idx + 1);
    if (TOOL_METADATA_TABLE[dotted]) return TOOL_METADATA_TABLE[dotted];
  }
  return DEFAULT_METADATA;
}

/** Helper for the chat-route's parallel-batch decision: returns
 *  true when ALL of the given tool calls are concurrencySafe. */
export function allConcurrencySafe(toolNames: string[]): boolean {
  if (toolNames.length === 0) return false;
  return toolNames.every((n) => resolveToolMetadata(n).concurrencySafe);
}
