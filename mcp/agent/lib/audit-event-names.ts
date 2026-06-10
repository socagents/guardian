/**
 * Standard observability event-name aliases — Round-15 / Phase Y.
 *
 * Round-14 Phase D introduced guardian-specific audit action names
 * (chat_compaction_*, chat_context_warning, chat_cache_hit). Round-15
 * Phase H + T + P + M + $ added more (hook_dispatched, task_*,
 * chat_plan_*, connector_*, chat_turn_cost).
 *
 * This file documents the mapping from those guardian-internal names
 * to the SnowAgent / OTel-conventional standard event names. Useful
 * when:
 *   - Forwarding to external observability (Datadog, OTel collector)
 *   - Querying across heterogeneous deploys with different vendor
 *     conventions
 *   - Operators familiar with SnowAgent's event names looking up
 *     the equivalent Guardian action
 *
 * The mapping is consultative — Guardian continues to write the
 * guardian-internal names as the canonical action column; this file
 * provides the OTel-friendly form for downstream consumers. A future
 * phase can wire the mapping into an OTel exporter that re-emits
 * audit rows under the standard names.
 *
 * Adapted from SnowAgent's standard event names
 * (snow-agent-complete/snow-agent/13-observability-policy-auth/).
 */

export const AUDIT_EVENT_NAME_ALIASES: Record<string, string> = {
  // Run lifecycle (Phase H wired hook events; this maps the audit
  // names to OTel-conventional dot.namespaced form).
  hook_dispatched: "agent.hook.dispatched",

  // Compaction lifecycle (Round-13 Phase 4.5 + Round-14 Phase D.1).
  chat_compaction_start: "agent.context.compaction.started",
  chat_compaction_end: "agent.context.compaction.completed",
  chat_compaction_failed: "agent.context.compaction.failed",

  // Context guard (Round-13 Phase 3.1).
  chat_context_warning: "agent.context.warning",

  // Vertex caching (Round-13 Phase 6 + Round-14 Phase D.3).
  chat_cache_hit: "agent.model.cache.hit",

  // Plan mode (Round-15 Phase P).
  chat_plan_proposed: "agent.plan.proposed",
  chat_plan_failed: "agent.plan.failed",

  // Cost tracking (Round-15 Phase $).
  chat_turn_cost: "agent.model.cost",

  // Task registry (Round-15 Phase T).
  task_created: "agent.task.created",
  task_started: "agent.task.started",
  task_completed: "agent.task.completed",
  task_failed: "agent.task.failed",
  task_aborted: "agent.task.aborted",
  task_pending: "agent.task.pending",
  task_transitioned: "agent.task.transitioned",

  // Connector state machine (Round-15 Phase M).
  connector_failed: "agent.connector.failed",
  connector_auth_required: "agent.connector.auth_required",
  connector_disabled: "agent.connector.disabled",
  connector_enabled: "agent.connector.enabled",
  connector_probed: "agent.connector.probed",

  // Hooks (Round-15 Phase H lifecycle).
  hook_upsert: "agent.hook.upsert",
  hook_enabled: "agent.hook.enabled",
  hook_disabled: "agent.hook.disabled",
  hook_deleted: "agent.hook.deleted",

  // Plugins (Round-15 Phase X).
  plugins_reloaded: "agent.plugins.reloaded",

  // Subagents (Round-15 Phase S).
  chat_subagent_started: "agent.subagent.started",
  chat_subagent_completed: "agent.subagent.completed",
  chat_subagent_failed: "agent.subagent.failed",
  agent_definition_upsert: "agent.definition.upsert",
  agent_definition_enabled: "agent.definition.enabled",
  agent_definition_disabled: "agent.definition.disabled",
  agent_definition_deleted: "agent.definition.deleted",

  // Existing guardian families — pre-Round-15. Surface them here
  // so downstream consumers see consistent dot-namespaced names.
  tool_call: "agent.tool.call",
  approval_requested: "agent.approval.requested",
  approval_resolved: "agent.approval.resolved",
};

/** Inverse mapping: standard name → guardian action. Used by
 *  observability importers that need to translate. */
export const AUDIT_STANDARD_TO_GUARDIAN: Record<string, string> = (() => {
  const out: Record<string, string> = {};
  for (const [guardian, std] of Object.entries(AUDIT_EVENT_NAME_ALIASES)) {
    out[std] = guardian;
  }
  return out;
})();

/** Resolve a guardian action name to its standard form, or pass
 *  through if no mapping exists. */
export function toStandardEventName(action: string): string {
  return AUDIT_EVENT_NAME_ALIASES[action] ?? action;
}

/** Resolve a standard event name to its guardian form. Identity
 *  fallback for unknown names. */
export function toGuardianActionName(standard: string): string {
  return AUDIT_STANDARD_TO_GUARDIAN[standard] ?? standard;
}
