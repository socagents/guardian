import { NextRequest, NextResponse } from 'next/server';
import { GuardianMCPClient, MCPTool } from '@/lib/mcp-client';
import { GoogleAuth } from 'google-auth-library';
import { callMcpServer } from '@/lib/mcp-proxy';
import { getEffectiveRuntimeConfig } from '@/lib/runtime-config';
import type { EffectiveRuntimeConfig } from '@/lib/runtime-config';
import { classifyRiskTier, isToolGated } from '@/lib/approvals-config';
// Round-13 / Phase 1.3 — system-prompt text extracted to its own
// module. ActionPolicy interface + renderActionPolicyBlock helper +
// the ~680 lines of stable prompt content all live there now. This
// route imports the type + the builder; renderActionPolicyBlock
// stays internal to the system-prompt module.
import {
  buildSystemPromptText,
  type ActionPolicy,
  type ApprovalMode,
  type SkillSummary,
} from '@/lib/system-prompt';
// v0.1.33+: live skills registry → <available_skills> block in the
// system prompt. Fetched once per chat turn before we call into the
// model loop, then threaded through callGemini to all downstream
// model calls so the same registry view is consistent across the turn.
import { fetchSkillsForPrompt } from '@/lib/skills-registry';
// Round-13 / Phase 2 — token-aware budgeting helpers.
import { estimateMessageTokens, estimateTokens } from '@/lib/tokens';
import {
  computeInputBudget,
  resolveContextCap,
} from '@/lib/model-context-caps';
// Round-13 / Phase 4.5 — operator-triggered conversation compaction.
import {
  compactMessages,
  COMPACTION_CHECKPOINT_KIND,
  isCompactionCheckpoint,
  type CompactionInputMessage,
} from '@/lib/compaction';
// Round-13 / Phase 6 — Vertex context caching for the stable system
// prompt. ~25% input-token billing on cached portions.
import { getOrCreateSystemPromptCache } from '@/lib/vertex-cache';
// Round-14 / Phase F — slash command parse-and-dispatch framework.
// Replaces the round-13 ad-hoc `if (message === '/compress')` check.
// Adding a new command becomes one entry in SLASH_COMMANDS below.
import {
  parseSlashCommand,
  dispatchSlashCommand,
  renderSlashHelp,
  type SlashCommand,
} from '@/lib/slash-commands';
// Round-15 / Phase $ — per-turn cost computation. Reads
// usageMetadata from each Gemini call, applies per-model pricing,
// emits SSE event + audit row.
import { computeTurnCostUsd, formatUsd } from '@/lib/model-pricing';
// Round-15 / Phase R — per-tool metadata (readOnly / destructive /
// concurrencySafe / openWorld). Powers approval-card visuals and
// future parallel-batch execution.
import {
  resolveToolMetadata,
  allConcurrencySafe,
  type ToolMetadata,
} from '@/lib/tool-metadata';
// Round-15 / Phase Y — explicit run-status reasons. Every chat
// turn ends with a `RunStatusReason` on the done event so
// operators get a clear "why" instead of silent cutoffs.
import type { RunStatusReason } from '@/lib/run-status';
// Round-15 / Phase S — subagent runner. The model invokes
// `subagent_create` as a synthetic tool; the chat-route intercepts,
// resolves the agent definition from MCP, and runs a tightly-
// scoped sub-loop. Reuses callGemini + the hook framework
// (PreToolUse/PostToolUse fire inside subagents too) + the task
// registry (each subagent run is a task).
import { globMatch } from '@/lib/hooks';
import {
  evaluatePermissionPolicy,
  validatePermissionPolicy,
  type PermissionPolicy,
} from '@/lib/permission-policy';
import { applyTruncation, policyFromEnv as truncationPolicyFromEnv } from '@/lib/evidence-truncation';
// Round-15 / Phase H — operator-registered lifecycle hooks. Loaded
// fresh from the MCP at every event fire-site (PreToolUse,
// PostToolUse, etc.) and dispatched in priority order. A hook may
// deny / allow / ask, replace tool I/O, or inject context.
import { dispatchHooks } from '@/lib/hook-runner';
import type { HookEvent, HookPayload } from '@/lib/hooks';

/**
 * Round-14 / Phase D — best-effort write of an audit row to the MCP.
 * Never throws; failure logs a warning. Called by the chat handler at
 * compaction lifecycle (start / end / failed), context-window warnings,
 * and Vertex cache hits — events that are visible live but had no
 * persisted footprint until now.
 *
 * Action-name conventions (kept in sync with the chat route's emit
 * sites and the observability /events page filter chips):
 *
 *   chat_compaction_start    — operator /compress kicked off
 *   chat_compaction_end      — checkpoint written, summary length etc.
 *   chat_compaction_failed   — summarizer errored or returned empty
 *   chat_context_warning     — guard fired at >=90% utilization
 *   chat_cache_hit           — Vertex cachedContents reused
 */
async function safeAudit(
  action: string,
  args: {
    target?: string;
    status?: 'success' | 'failure';
    durationMs?: number;
    metadata?: Record<string, unknown>;
    trigger?: string;
    // #CHAT-F2 — the authenticated principal (apikey:<id> | user:operator),
    // captured from the middleware-stamped X-Guardian-Actor on the chat
    // request, so chat-path audit rows attribute to the real caller instead
    // of the MCP's default user:operator.
    actor?: string;
  } = {},
): Promise<void> {
  try {
    const headers: Record<string, string> = {};
    if (args.trigger) headers['X-Guardian-Trigger'] = args.trigger;
    if (args.actor) headers['X-Guardian-Actor'] = args.actor;
    await callMcpServer('/api/v1/audit', {
      method: 'POST',
      body: {
        action,
        target: args.target,
        status: args.status,
        duration_ms: args.durationMs,
        metadata: args.metadata ?? {},
      },
      headers: Object.keys(headers).length ? headers : undefined,
    });
  } catch (err) {
    console.warn(
      `chat: audit write for action=${action} failed:`,
      err instanceof Error ? err.message : err,
    );
  }
}

/**
 * Round-15 / Phase $ — sum chat_turn_cost audit rows.
 *
 * Used by the /cost slash command and (via re-import) the
 * /observability/cost page's API. Returns total tokens, total
 * USD, savings (cached vs hypothetical-uncached), and a by-model
 * breakdown.
 */
function sumCostRows(
  rows: Array<{ metadata?: Record<string, unknown> }>,
): {
  calls: number;
  input: number;
  cached: number;
  output: number;
  usd: number;
  savings: number;
  byModel: Record<string, { usd: number; calls: number }>;
} {
  const out = {
    calls: 0,
    input: 0,
    cached: 0,
    output: 0,
    usd: 0,
    savings: 0,
    byModel: {} as Record<string, { usd: number; calls: number }>,
  };
  for (const row of rows) {
    const m = row.metadata ?? {};
    const inputTokens = (m['input_tokens'] as number) ?? 0;
    const cachedTokens = (m['cached_input_tokens'] as number) ?? 0;
    const outputTokens = (m['output_tokens'] as number) ?? 0;
    const usd = (m['cost_usd'] as number) ?? 0;
    const savings =
      ((m['cost_components'] as Record<string, number> | undefined)?.[
        'cached_savings_usd'
      ] ?? 0) || 0;
    const model = (m['model'] as string) ?? 'unknown';
    out.calls += 1;
    out.input += inputTokens;
    out.cached += cachedTokens;
    out.output += outputTokens;
    out.usd += usd;
    out.savings += savings;
    if (!out.byModel[model]) {
      out.byModel[model] = { usd: 0, calls: 0 };
    }
    out.byModel[model].usd += usd;
    out.byModel[model].calls += 1;
  }
  return out;
}

/**
 * Round-15 / Phase $ — extract Gemini usage metadata + record a
 * cost audit row. Best-effort; never blocks the stream.
 *
 * Returns the computed cost so the caller can sum across follow-up
 * calls in a multi-tool turn (the chat-route accumulates and sends
 * a single `turn_cost` SSE event per turn at done time, rather than
 * a separate event per Gemini call).
 */
function extractAndRecordCost(
  response: unknown,
  args: {
    sessionId: string;
    model: string;
    trigger: string | undefined;
    /** 'initial' for the first callGemini in a turn; 'followup'
     *  for tool-result follow-ups; 'budget_summary' for the v0.1.25
     *  partial-summary fallback that fires when the 20-turn loop
     *  exhausts without producing text. Surfaces in audit metadata
     *  so the operator can see how many round-trips a turn cost. */
    callKind: 'initial' | 'followup' | 'budget_summary';
  },
): { usd: number; inputTokens: number; cachedTokens: number; outputTokens: number } {
  const usage = (response as { usageMetadata?: Record<string, unknown> })
    .usageMetadata;
  if (!usage) {
    return { usd: 0, inputTokens: 0, cachedTokens: 0, outputTokens: 0 };
  }
  const inputTokens =
    (usage['promptTokenCount'] as number | undefined) ?? 0;
  const cachedTokens =
    (usage['cachedContentTokenCount'] as number | undefined) ?? 0;
  const outputTokens =
    (usage['candidatesTokenCount'] as number | undefined) ?? 0;
  const cost = computeTurnCostUsd({
    inputTokens,
    cachedInputTokens: cachedTokens,
    outputTokens,
    model: args.model,
  });
  // Audit one row per Gemini call. Fine-grained (vs. one per
  // turn) because a turn can rack up 5-10 calls when tools fire,
  // and operators want per-call cost breakdown for tool-cost
  // attribution. Not high-volume in absolute terms.
  void safeAudit('chat_turn_cost', {
    target: `session:${args.sessionId}`,
    status: 'success',
    metadata: {
      call_kind: args.callKind,
      input_tokens: inputTokens,
      cached_input_tokens: cachedTokens,
      output_tokens: outputTokens,
      uncached_input_tokens: inputTokens - cachedTokens,
      cost_usd: Number(cost.usd.toFixed(6)),
      cost_components: {
        input_usd: Number(cost.components.inputUsd.toFixed(6)),
        cached_input_usd: Number(cost.components.cachedInputUsd.toFixed(6)),
        output_usd: Number(cost.components.outputUsd.toFixed(6)),
        uncached_hypothetical_input_usd: Number(
          cost.components.uncachedHypotheticalInputUsd.toFixed(6),
        ),
        cached_savings_usd: Number(
          (
            cost.components.uncachedHypotheticalInputUsd -
            (cost.components.inputUsd + cost.components.cachedInputUsd)
          ).toFixed(6),
        ),
      },
      model: args.model,
    },
    trigger: args.trigger,
  });
  return {
    usd: cost.usd,
    inputTokens,
    cachedTokens,
    outputTokens,
  };
}

/**
 * Round-15 / Phase S — synthetic tool name the model calls to
 * spawn a subagent. The chat-route's tool-dispatch loop recognizes
 * this name and routes to `runSubagent` instead of MCP dispatch.
 * Listed in the model's tool catalog as a regular function with
 * a documented schema (see SUBAGENT_CREATE_TOOL_SPEC below).
 */
const SUBAGENT_CREATE_TOOL = 'subagent_create';

/** OpenAPI-style schema for `subagent_create`. The model sees this
 *  alongside the regular MCP tools. Args:
 *    agent_name  — required. Resolved against the MCP agent-
 *                  definition store (origin: operator | plugin |
 *                  builtin). Empty/missing returns an error.
 *    prompt      — required. The task the subagent should perform.
 *    parent_id   — optional. The current session id; the chat-route
 *                  fills this in automatically from the loop
 *                  context if absent. */
const SUBAGENT_CREATE_TOOL_SPEC = {
  name: SUBAGENT_CREATE_TOOL,
  description:
    'Spawn a scoped subagent to perform a focused task. The subagent ' +
    'runs with its own system prompt and a curated tool subset (e.g. ' +
    'triage subagent only sees xsoar_list_incidents, enrichment subagent only xsoar_search_indicators). ' +
    'Use when a task needs a different operating posture than this ' +
    "session — don't use it for trivial sub-questions you can answer " +
    'directly. Available agent_name values come from /api/v1/' +
    'agent-definitions; typical examples: case-triage, ' +
    'evidence-collector, asset-context.',
  parameters: {
    type: 'object' as const,
    properties: {
      agent_name: {
        type: 'string' as const,
        description:
          'Name of the agent definition (e.g. "case-triage"). ' +
          'Must exist + be enabled in /api/v1/agent-definitions.',
      },
      prompt: {
        type: 'string' as const,
        description:
          'The task for the subagent. Self-contained — the subagent ' +
          "won't see the parent's prior context.",
      },
    },
    required: ['agent_name', 'prompt'],
  },
};

/** Result of one subagent run, returned to the parent's tool-call
 *  loop as the tool result text. */
interface SubagentRunResult {
  subagent_session_id: string;
  agent_name: string;
  agent_id: string;
  status: 'completed' | 'max_turns_exceeded' | 'failed' | 'denied';
  final_response: string;
  tool_calls_made: Array<{ tool: string; args: Record<string, unknown> }>;
  tool_calls_count: number;
  turns_used: number;
  duration_ms: number;
  error?: string;
}

/** Filter the parent's tool catalog through an agent definition's
 *  tools_allowed / tools_denied globs. Deny wins when both match.
 *  Empty allow list means "no restriction" (still subject to denies). */
function filterToolsForAgent(
  parentTools: Array<{ functionDeclarations: unknown }>,
  toolsAllowed: string[],
  toolsDenied: string[],
): Array<{ functionDeclarations: unknown }> {
  // The Gemini tool catalog is a list of {functionDeclarations: [...]}
  // groups; each declaration has a `.name`. We need to filter the
  // declarations within each group, dropping groups that end up
  // empty.
  const allowGlob = toolsAllowed.length > 0
    ? toolsAllowed.join(',')
    : null;
  const denyGlob = toolsDenied.length > 0
    ? toolsDenied.join(',')
    : null;
  const out: Array<{ functionDeclarations: unknown }> = [];
  for (const group of parentTools) {
    const decls = (group.functionDeclarations as Array<{ name?: string }>) ?? [];
    const filtered = decls.filter((d) => {
      const name = d.name;
      if (!name) return false;
      if (denyGlob && globMatch(name, denyGlob)) return false;
      if (allowGlob && !globMatch(name, allowGlob)) return false;
      return true;
    });
    if (filtered.length > 0) {
      out.push({ functionDeclarations: filtered });
    }
  }
  return out;
}

/**
 * Run a subagent end-to-end. Foreground execution: blocks the
 * caller until the subagent completes, errors, or hits max_turns.
 * Returns the synthesized result the parent's tool-call loop feeds
 * back to the parent model.
 *
 * Reuses Round-15 substrates:
 *   - Phase H hooks: SubagentStart fires before, SubagentEnd after.
 *     PreToolUse/PostToolUse fire INSIDE the subagent's tool loop too.
 *   - Phase T tasks: each subagent run is a Task with progress.
 *   - Phase $ cost tracking: subagent's Gemini calls write
 *     chat_turn_cost rows tagged with the subagent session id.
 *
 * Architecture note: the subagent gets its OWN MCP session
 * (parent_session_id linkage in metadata). Its transcript is
 * persistent and queryable separately, so /sessions can show
 * subagent runs as sidechain transcripts of the parent.
 */
async function runSubagent(args: {
  agentName: string;
  prompt: string;
  parentSessionId: string;
  parentMessage: string;
  trigger: string | undefined;
  parentTools: Array<{ functionDeclarations: unknown }>;
  runtimeConfig: EffectiveRuntimeConfig;
  parentModel: string | undefined;
  mcpClient: GuardianMCPClient;
  sendEvent: (kind: string, data: unknown) => void;
}): Promise<SubagentRunResult> {
  const startedAt = Date.now();

  // Round-15 / Phase H — SubagentStart hook fire-site. A hook
  // can deny ("block any subagent in tenant-X") or no-op.
  const startHook = await fireHookEvent(
    'SubagentStart',
    {
      event: 'SubagentStart',
      sessionId: args.parentSessionId,
      agentName: args.agentName,
      prompt: args.prompt,
      trigger: args.trigger,
    } as never, // HookPayload union extension; cast is benign
    // because the dispatcher only reads `event` from the
    // payload to filter, not field-by-field
    args.trigger,
  );
  if (startHook.decision === 'deny') {
    // #SUB-F1 — record the denied spawn. Pre-fix every pre-start failure
    // (hook deny, not-found, lookup error, disabled) returned before any
    // audit write, so a blocked/failed subagent spawn left no row in the
    // audit log — a forensic blind spot. (The SubagentStart hook's own
    // hook_dispatched row covers the hook decision, not the spawn outcome.)
    void safeAudit('chat_subagent_dispatch_failed', {
      target: `agent:${args.agentName}`,
      status: 'failure',
      trigger: args.trigger,
      metadata: {
        agent_name: args.agentName,
        reason: 'denied_by_subagent_start_hook',
        parent_session_id: args.parentSessionId,
      },
    });
    return {
      subagent_session_id: '',
      agent_name: args.agentName,
      agent_id: '',
      status: 'denied',
      final_response: '',
      tool_calls_made: [],
      tool_calls_count: 0,
      turns_used: 0,
      duration_ms: Date.now() - startedAt,
      error:
        startHook.reason ??
        'Subagent dispatch blocked by a SubagentStart hook.',
    };
  }

  // Resolve the agent definition by name from MCP.
  let agentDef: {
    id: string;
    name: string;
    system_prompt: string;
    tools_allowed: string[];
    tools_denied: string[];
    model: string | null;
    max_turns: number;
    isolation: string;
    enabled: boolean;
  };
  try {
    const resp = await callMcpServer<{
      agent_definition?: typeof agentDef;
    }>(
      `/api/v1/agent-definitions/by-name/${encodeURIComponent(args.agentName)}`,
      {
        method: 'GET',
        headers: args.trigger
          ? { 'X-Guardian-Trigger': args.trigger }
          : undefined,
      },
    );
    if (!resp?.agent_definition) {
      void safeAudit('chat_subagent_dispatch_failed', {
        target: `agent:${args.agentName}`,
        status: 'failure',
        trigger: args.trigger,
        metadata: {
          agent_name: args.agentName,
          reason: 'not_found',
          parent_session_id: args.parentSessionId,
        },
      });
      return {
        subagent_session_id: '',
        agent_name: args.agentName,
        agent_id: '',
        status: 'failed',
        final_response: '',
        tool_calls_made: [],
        tool_calls_count: 0,
        turns_used: 0,
        duration_ms: Date.now() - startedAt,
        error: `Agent definition '${args.agentName}' not found.`,
      };
    }
    agentDef = resp.agent_definition;
  } catch (err) {
    void safeAudit('chat_subagent_dispatch_failed', {
      target: `agent:${args.agentName}`,
      status: 'failure',
      trigger: args.trigger,
      metadata: {
        agent_name: args.agentName,
        reason: 'lookup_error',
        error: err instanceof Error ? err.message : String(err),
        parent_session_id: args.parentSessionId,
      },
    });
    return {
      subagent_session_id: '',
      agent_name: args.agentName,
      agent_id: '',
      status: 'failed',
      final_response: '',
      tool_calls_made: [],
      tool_calls_count: 0,
      turns_used: 0,
      duration_ms: Date.now() - startedAt,
      error: `Agent lookup failed: ${err instanceof Error ? err.message : String(err)}`,
    };
  }
  if (!agentDef.enabled) {
    void safeAudit('chat_subagent_dispatch_failed', {
      target: `agent:${agentDef.id}`,
      status: 'failure',
      trigger: args.trigger,
      metadata: {
        agent_name: args.agentName,
        agent_id: agentDef.id,
        reason: 'disabled',
        parent_session_id: args.parentSessionId,
      },
    });
    return {
      subagent_session_id: '',
      agent_name: args.agentName,
      agent_id: agentDef.id,
      status: 'failed',
      final_response: '',
      tool_calls_made: [],
      tool_calls_count: 0,
      turns_used: 0,
      duration_ms: Date.now() - startedAt,
      error: `Agent '${args.agentName}' is disabled.`,
    };
  }

  // Create a fresh MCP session for the subagent. parent_session_id
  // in metadata is the linkage that lets the chat UI render the
  // subagent transcript as a sidechain of the parent.
  let subagentSessionId: string;
  try {
    const created = await callMcpServer<{
      session?: { id?: string };
    }>('/api/v1/sessions', {
      method: 'POST',
      body: {
        user: 'agent',
        title: `[subagent:${args.agentName}] ${args.prompt.slice(0, 60)}`,
        meta: {
          parent_session_id: args.parentSessionId,
          subagent_origin: 'parent_session',
          agent_name: args.agentName,
          agent_id: agentDef.id,
        },
      },
      headers: args.trigger
        ? { 'X-Guardian-Trigger': args.trigger }
        : undefined,
    });
    subagentSessionId =
      created?.session?.id ?? `s_subagent_${crypto.randomUUID()}`;
  } catch (err) {
    return {
      subagent_session_id: '',
      agent_name: args.agentName,
      agent_id: agentDef.id,
      status: 'failed',
      final_response: '',
      tool_calls_made: [],
      tool_calls_count: 0,
      turns_used: 0,
      duration_ms: Date.now() - startedAt,
      error: `Subagent session create failed: ${err instanceof Error ? err.message : String(err)}`,
    };
  }

  // Round-15 / Phase T — open a task entry for this subagent run.
  // The /tasks UI shows it under kind='subagent' with parent
  // session linkage. Failure to create the task is non-fatal.
  let taskId: string | undefined;
  try {
    const taskResp = await callMcpServer<{
      task?: { id?: string };
    }>('/api/v1/tasks', {
      method: 'POST',
      body: {
        kind: 'subagent',
        title: `${args.agentName}: ${args.prompt.slice(0, 80)}`,
        parent_session_id: args.parentSessionId,
        initial_status: 'running',
        meta: {
          agent_name: args.agentName,
          agent_id: agentDef.id,
          subagent_session_id: subagentSessionId,
        },
      },
      headers: args.trigger
        ? { 'X-Guardian-Trigger': args.trigger }
        : undefined,
    });
    taskId = taskResp?.task?.id;
  } catch {
    // best-effort
  }

  // Persist the subagent's user-message (the prompt the parent gave it).
  await safePersist(
    subagentSessionId,
    { role: 'user', content: args.prompt },
    args.trigger,
  );

  // Round-14 Phase D — audit row for the subagent start.
  void safeAudit('chat_subagent_started', {
    target: `session:${subagentSessionId}`,
    metadata: {
      parent_session_id: args.parentSessionId,
      agent_name: args.agentName,
      agent_id: agentDef.id,
      max_turns: agentDef.max_turns,
      tools_allowed_count: agentDef.tools_allowed.length,
      tools_denied_count: agentDef.tools_denied.length,
    },
    trigger: args.trigger,
  });

  // Filter tools to the agent's scope. The model in the subagent
  // loop only SEES tools that match — it can't even call denied
  // tools because they're not in the catalog.
  const scopedTools = filterToolsForAgent(
    args.parentTools,
    agentDef.tools_allowed,
    agentDef.tools_denied,
  );

  // Stream a `subagent_started` SSE event so the parent's chat UI
  // can render a sidechain progress indicator.
  args.sendEvent('subagent_started', {
    parent_session_id: args.parentSessionId,
    subagent_session_id: subagentSessionId,
    agent_name: args.agentName,
    agent_id: agentDef.id,
    prompt: args.prompt,
    max_turns: agentDef.max_turns,
    tools_count: scopedTools.reduce(
      (acc, g) =>
        acc +
        ((g.functionDeclarations as Array<unknown>)?.length ?? 0),
      0,
    ),
    task_id: taskId,
  });

  // Tool catalog scoped + system instruction overridden — run the loop.
  const subagentSystem: GeminiSystemInstruction = {
    role: 'system',
    parts: [{ text: agentDef.system_prompt }],
  };
  const subagentContents: GeminiContent[] = [
    { role: 'user', parts: [{ text: args.prompt }] },
  ];
  const subagentModel = agentDef.model ?? args.parentModel;
  const finalText: string[] = [];
  const toolCallsMade: Array<{ tool: string; args: Record<string, unknown> }> = [];
  let turnsUsed = 0;
  let status: SubagentRunResult['status'] = 'completed';
  let errorMessage: string | undefined;

  try {
    let response = await callGeminiRaw(
      subagentContents,
      scopedTools,
      args.runtimeConfig,
      subagentSystem,
      subagentModel,
    );

    // Track cost — per-Gemini-call rows tagged with subagent session.
    extractAndRecordCost(response, {
      sessionId: subagentSessionId,
      model: subagentModel ?? args.runtimeConfig.GEMINI_MODEL ?? 'unknown',
      trigger: args.trigger,
      callKind: 'initial',
    });

    for (let step = 0; step < agentDef.max_turns; step++) {
      turnsUsed = step + 1;
      const candidate = response.candidates?.[0];
      const parts: GeminiPart[] = candidate?.content?.parts || [];
      const functionCalls: GeminiFunctionCall[] = [];
      for (const part of parts) {
        if (part.text) {
          finalText.push(part.text);
        }
        if (part.functionCall) {
          functionCalls.push(part.functionCall);
        }
      }
      if (functionCalls.length === 0) break;

      // Update task progress.
      if (taskId) {
        void callMcpServer<unknown>(
          `/api/v1/tasks/${encodeURIComponent(taskId)}/progress`,
          {
            method: 'PATCH',
            body: {
              progress: turnsUsed / agentDef.max_turns,
              progress_label: `turn ${turnsUsed}/${agentDef.max_turns}: ${functionCalls.length} tool(s)`,
            },
            headers: args.trigger
              ? { 'X-Guardian-Trigger': args.trigger }
              : undefined,
          },
        ).catch(() => {});
      }

      subagentContents.push({ role: 'model', parts });
      const responseParts: GeminiPart[] = [];
      for (const call of functionCalls) {
        const toolName = call.name;
        const toolArgs = call.args || {};

        // Defense in depth: re-check scope. The model shouldn't
        // even see denied tools, but if a hook injected a tool
        // call with a different name (rare), reject here.
        const denyGlob = agentDef.tools_denied.length > 0
          ? agentDef.tools_denied.join(',')
          : null;
        const allowGlob = agentDef.tools_allowed.length > 0
          ? agentDef.tools_allowed.join(',')
          : null;
        if (
          (denyGlob && globMatch(toolName, denyGlob)) ||
          (allowGlob && !globMatch(toolName, allowGlob))
        ) {
          const reason = `Tool '${toolName}' is outside the subagent's scope.`;
          args.sendEvent('subagent_tool_blocked', {
            subagent_session_id: subagentSessionId,
            tool: toolName,
            reason,
          });
          // #SUB-F6 — a subagent attempting an out-of-scope tool was SSE-only:
          // never audited, never persisted, so a malicious out-of-scope attempt
          // left no forensic trace once the stream closed. Record it to the
          // audit log AND the subagent's sidechain transcript.
          void safeAudit('subagent_tool_blocked', {
            target: `tool:${toolName}`,
            status: 'failure',
            trigger: args.trigger,
            // #CHAT-F15 — attribute the block to the subagent, not the
            // ambient operator default (the block is a machine-driven event).
            actor: 'agent',
            metadata: {
              subagent_session_id: subagentSessionId,
              parent_session_id: args.parentSessionId,
              agent_name: args.agentName,
              agent_id: agentDef.id,
              tool: toolName,
              reason,
            },
          });
          void safePersist(
            subagentSessionId,
            {
              role: 'tool',
              content: reason,
              tool_call_id: toolName,
              meta: { tool: toolName, blocked_by: 'subagent_scope', status: 'blocked' },
            },
            args.trigger,
          );
          responseParts.push({
            functionResponse: {
              name: toolName,
              response: {
                error: reason,
                blocked_by: 'subagent_scope',
              },
            },
          });
          continue;
        }

        // Stream a sub-tool-call event so the parent UI can show
        // what the subagent's doing in real time.
        args.sendEvent('subagent_tool_call', {
          subagent_session_id: subagentSessionId,
          tool: toolName,
          args: toolArgs,
        });

        let toolResult: { content: Array<{ text?: string }> } | null = null;
        let toolError: Error | null = null;
        try {
          toolResult = await args.mcpClient.callTool(toolName, toolArgs);
        } catch (err) {
          toolError = err instanceof Error ? err : new Error(String(err));
        }

        const rawResultText = toolError
          ? `Error: ${toolError.message}`
          : toolResult?.content[0]?.text ||
            JSON.stringify(toolResult?.content ?? '');
        // v0.2.14 — cap a single live SUBAGENT tool result so one broad XSOAR
        // read (a war-room / incident-list dump on a busy tenant) can't blow
        // the subagent's context window (the Vertex ~1M-token ceiling). The
        // main-agent loop already truncates tool results (see ~L5100 via
        // applyTruncation); the subagent path did NOT, so broad threat-hunter
        // hunts failed with "input token count exceeds the maximum number of
        // tokens allowed". Same evidence-truncation policy (head+tail+marker)
        // the operator already controls via EVIDENCE_TRUNCATION_* env.
        const resultText = toolError
          ? rawResultText
          : String(
              applyTruncation(
                toolName,
                rawResultText,
                truncationPolicyFromEnv(),
              ).output,
            );

        toolCallsMade.push({
          tool: toolName,
          args: toolArgs as Record<string, unknown>,
        });

        // Persist to subagent session.
        await safePersist(
          subagentSessionId,
          {
            role: 'tool',
            content: resultText,
            tool_call_id: toolName,
            meta: {
              tool: toolName,
              args: toolArgs,
              status: toolError ? 'error' : 'success',
            },
          },
          args.trigger,
        );

        args.sendEvent('subagent_tool_result', {
          subagent_session_id: subagentSessionId,
          tool: toolName,
          status: toolError ? 'error' : 'success',
          result: resultText.slice(0, 500),
        });

        responseParts.push({
          functionResponse: {
            name: toolName,
            response: toolError
              ? { error: toolError.message }
              : { result: resultText },
          },
        });
      }
      if (responseParts.length > 0) {
        subagentContents.push({ role: 'user', parts: responseParts });
      }

      // Continue the loop.
      response = await callGeminiRaw(
        subagentContents,
        scopedTools,
        args.runtimeConfig,
        subagentSystem,
        subagentModel,
      );
      extractAndRecordCost(response, {
        sessionId: subagentSessionId,
        model: subagentModel ?? args.runtimeConfig.GEMINI_MODEL ?? 'unknown',
        trigger: args.trigger,
        callKind: 'followup',
      });
    }

    if (turnsUsed >= agentDef.max_turns) {
      // Check whether the FINAL response had text; if not, the
      // last turn was tools-only and we hit the cap mid-flight.
      const lastCandidate = response.candidates?.[0];
      const lastParts: GeminiPart[] = lastCandidate?.content?.parts || [];
      const hasText = lastParts.some((p) => p.text);
      if (!hasText) {
        status = 'max_turns_exceeded';
      } else {
        // Drain final text from the last turn.
        for (const part of lastParts) {
          if (part.text) finalText.push(part.text);
        }
      }
    }
  } catch (err) {
    status = 'failed';
    errorMessage = err instanceof Error ? err.message : String(err);
  }

  const finalResponse = finalText.join('').trim();

  // Persist subagent's final assistant response so the sidechain
  // transcript is complete.
  if (finalResponse) {
    await safePersist(
      subagentSessionId,
      {
        role: 'assistant',
        content: finalResponse,
        meta: {
          model: subagentModel,
          subagent: true,
          parent_session_id: args.parentSessionId,
        },
      },
      args.trigger,
    );
  }

  // Close out the task.
  if (taskId) {
    void callMcpServer<unknown>(
      `/api/v1/tasks/${encodeURIComponent(taskId)}/transition`,
      {
        method: 'POST',
        body: {
          // 'denied' / 'failed' / 'max_turns_exceeded' all map to
          // failure or aborted at the task layer. 'denied' returns
          // early before we get here so it's unreachable; the
          // explicit check would be a TS narrowing error.
          status:
            status === 'completed' ? 'succeeded'
            : status === 'failed' ? 'failed'
            : 'failed', // max_turns_exceeded
          output: errorMessage ?? finalResponse,
        },
        headers: args.trigger
          ? { 'X-Guardian-Trigger': args.trigger }
          : undefined,
      },
    ).catch(() => {});
  }

  // Round-14 Phase D — audit row for the subagent end.
  const auditAction =
    status === 'completed'
      ? 'chat_subagent_completed'
      : 'chat_subagent_failed';
  void safeAudit(auditAction, {
    target: `session:${subagentSessionId}`,
    status: status === 'completed' ? 'success' : 'failure',
    durationMs: Date.now() - startedAt,
    metadata: {
      parent_session_id: args.parentSessionId,
      agent_name: args.agentName,
      agent_id: agentDef.id,
      turns_used: turnsUsed,
      tool_calls_count: toolCallsMade.length,
      max_turns_exceeded: status === 'max_turns_exceeded',
      error: errorMessage,
    },
    trigger: args.trigger,
  });

  // Round-15 / Phase H — SubagentEnd hook (non-decisional).
  void fireHookEvent(
    'SubagentEnd',
    {
      event: 'SubagentEnd',
      sessionId: args.parentSessionId,
      subagentSessionId,
      agentName: args.agentName,
      status,
      finalResponseChars: finalResponse.length,
      toolCallCount: toolCallsMade.length,
      durationMs: Date.now() - startedAt,
      trigger: args.trigger,
    } as never,
    args.trigger,
  );

  args.sendEvent('subagent_completed', {
    parent_session_id: args.parentSessionId,
    subagent_session_id: subagentSessionId,
    agent_name: args.agentName,
    status,
    final_response: finalResponse,
    tool_calls_count: toolCallsMade.length,
    turns_used: turnsUsed,
    duration_ms: Date.now() - startedAt,
    error: errorMessage,
  });

  return {
    subagent_session_id: subagentSessionId,
    agent_name: args.agentName,
    agent_id: agentDef.id,
    status,
    final_response: finalResponse,
    tool_calls_made: toolCallsMade,
    tool_calls_count: toolCallsMade.length,
    turns_used: turnsUsed,
    duration_ms: Date.now() - startedAt,
    error: errorMessage,
  };
}

/** Lightweight Gemini caller used by the subagent runner — separate
 *  from `callGemini` because the subagent has its own
 *  systemInstruction (the agent's system_prompt) instead of the
 *  full ActionPolicy-based one the main chat-route uses. */
async function callGeminiRaw(
  contents: GeminiContent[],
  tools: Array<{ functionDeclarations: unknown }>,
  runtimeConfig: EffectiveRuntimeConfig,
  systemInstruction: GeminiSystemInstruction,
  modelOverride?: string,
) {
  const payload: GeminiCallPayload = {
    contents,
    tools,
    systemInstruction,
    // v0.2.3 — no maxOutputTokens cap; Gemini uses model's natural max.
  };
  const modelName = resolveModelName(modelOverride, runtimeConfig);
  if (runtimeConfig.GEMINI_API_KEY) {
    try {
      return await callGeminiWithApiKey(payload, runtimeConfig, modelName);
    } catch (error) {
      if (
        runtimeConfig.GOOGLE_APPLICATION_CREDENTIALS &&
        isInvalidGeminiApiKeyError(error)
      ) {
        return callGeminiWithVertex(payload, runtimeConfig, modelName);
      }
      throw error;
    }
  }
  if (runtimeConfig.GOOGLE_APPLICATION_CREDENTIALS) {
    return callGeminiWithVertex(payload, runtimeConfig, modelName);
  }
  throw new Error(
    'No model provider is configured. Add a Vertex AI or Gemini API provider at /providers, then retry — the subagent uses the same provider as the main chat agent.',
  );
}

/**
 * v0.6.42 — derive the connector_id from an agent-facing tool name.
 * Returns null for tools that don't belong to any connector (built-in
 * MCP tools like instances_list, audit_recent, etc.).
 *
 * Handles both modern dotted form ("xsoar.get_incident" → "xsoar")
 * and flat aliases ("xsoar_get_incident" → "xsoar").
 *
 * Pre-v0.6.42 this was an inline `toolName.split('_', 1)[0]` which
 * produced wrong connector_ids for connectors whose function prefix
 * differs from their id:
 *   guardian_web_navigate      → "guardian"  WRONG (id is "web")
 *   cortex_search             → "cortex"   WRONG (id is "cortex-docs")
 *
 * Resulting bug: connector failures + successes recorded against
 * non-existent connector_ids ("guardian", "cortex"); the
 * connector_auth_required UI event fired with the wrong id; the
 * /observability/connectors state machine missed real failures for
 * xsoar, cortex-docs, and web.
 *
 * The prefix-to-id mapping below is hardcoded against bundles/spark/
 * connectors/*\/connector.yaml's `functionPrefix` field. When a new
 * connector ships with a non-identity prefix mapping, this function
 * needs an entry. Long-term: the MCPTool interface should carry
 * connector_id explicitly so we don't need this lookup.
 */
function deriveConnectorId(toolName: string): string | null {
  // Modern dotted form: "<connector>.<tool>"
  if (toolName.includes('.')) {
    return toolName.split('.', 2)[0];
  }
  // Flat aliases — order matters (longer prefixes first).
  if (toolName.startsWith('guardian_web_')) return 'web';
  if (toolName.startsWith('xsoar_')) return 'xsoar';
  // cortex-docs is the only surviving `cortex_`-prefixed connector
  // (cortex-content was removed in the XSOAR pivot).
  if (toolName.startsWith('cortex_')) return 'cortex-docs';
  // Tools that aren't connector-namespaced (e.g. instances_list,
  // audit_recent, jobs_create, marketplace_install — built-in MCP
  // tools that don't belong to any connector). Caller should skip
  // connector state updates for these.
  return null;
}

/**
 * Round-15 / Phase M — record a connector failure in the MCP-side
 * state store. Best-effort; never blocks the stream. The chat-
 * route uses message-string heuristics to classify auth vs. other
 * errors because the MCP tool wrapper doesn't yet expose typed
 * errors.
 */
async function recordConnectorFailure(
  connectorId: string,
  args: { error: string; isAuthError: boolean; trigger: string | undefined },
): Promise<void> {
  try {
    await callMcpServer<unknown>(
      `/api/v1/connectors/${encodeURIComponent(connectorId)}/_record_failure`,
      {
        method: 'POST',
        body: { error: args.error, is_auth_error: args.isAuthError },
        headers: args.trigger
          ? { 'X-Guardian-Trigger': args.trigger }
          : undefined,
      },
    );
  } catch {
    // The internal record endpoint may not exist on older deploys;
    // that's fine — Phase M's API surface already provides probe/
    // disable/enable, and the state will refresh on the next
    // operator action.
  }
}

/** Round-15 / Phase M — record a successful tool call. */
async function recordConnectorSuccess(
  connectorId: string,
  trigger: string | undefined,
): Promise<void> {
  try {
    await callMcpServer<unknown>(
      `/api/v1/connectors/${encodeURIComponent(connectorId)}/_record_success`,
      {
        method: 'POST',
        body: {},
        headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
      },
    );
  } catch {
    // Same rationale as recordConnectorFailure.
  }
}

/**
 * Round-15 / Phase H — fire a hook event and emit a single
 * `hook_dispatched` audit row summarizing the per-hook decisions.
 *
 * The chat-route shape is "fire-and-forget for non-decisional events"
 * (PostToolUse, PostCompact, RunEnd) and "fire-and-await for
 * decisional events" (PreToolUse, UserPromptSubmit, PreCompact,
 * RunStart). Callers pass `awaitDecision: true` for the latter.
 *
 * Failure is swallowed; a broken hook can't crash the chat. The
 * dispatcher itself applies each hook's `failurePolicy` for transport
 * errors; this helper handles the meta-failure of the dispatcher
 * itself failing (network blip to MCP, malformed hook records).
 */
async function fireHookEvent(
  event: HookEvent,
  payload: HookPayload,
  trigger: string | undefined,
): Promise<{
  decision: 'allow' | 'deny' | 'ask' | undefined;
  reason?: string;
  replace?: unknown;
  injectContext?: string;
}> {
  try {
    const result = await dispatchHooks(event, payload);
    if (result.decisions.length > 0) {
      // Best-effort audit of the dispatch itself. We log the per-
      // hook decisions in metadata so an operator can answer "which
      // hook denied this turn?" without re-running.
      void safeAudit('hook_dispatched', {
        target: payload.event,
        status: result.decision === 'deny' ? 'failure' : 'success',
        metadata: {
          event,
          // v0.5.24: not all payloads have sessionId (Notification +
          // PermissionRequest carry related.sessionId optionally
          // instead). Narrow before reading.
          session_id:
            'sessionId' in payload && typeof payload.sessionId === 'string'
              ? payload.sessionId
              : undefined,
          hooks_fired: result.decisions.length,
          decision: result.decision ?? 'no-op',
          reason: result.reason,
          per_hook: result.decisions.map((d) => ({
            id: d.hookId,
            name: d.name,
            decision: d.decision,
            duration_ms: d.durationMs,
            error: d.error,
          })),
        },
        trigger,
      });
    }
    return {
      decision: result.decision,
      reason: result.reason,
      replace: result.replace,
      injectContext: result.injectContext,
    };
  } catch (err) {
    console.warn(
      `chat: dispatchHooks(${event}) failed:`,
      err instanceof Error ? err.message : err,
    );
    return { decision: undefined };
  }
}

/**
 * Best-effort persistence to the MCP session store. Each call swallows
 * its own errors with a console warning so a session-store outage
 * never blocks the chat stream from reaching the user.
 *
 * Persistence shape (matches Spark's chat-history convention):
 *   - role='user' ............... the inbound message
 *   - role='tool' (one each) .... each tool_call/result pair, with
 *                                 meta={ tool, args } and
 *                                 tool_call_id={ tool name }
 *   - role='assistant' .......... the final composed text response
 *
 * On a brand-new session (no incoming session_id), we PATCH the title
 * to a 60-char preview of the first user message after the turn
 * completes, so the sidebar shows something meaningful.
 */
async function safePersist(
  sessionId: string,
  payload: {
    role: 'user' | 'assistant' | 'tool' | 'system';
    content: string;
    tool_call_id?: string;
    meta?: Record<string, unknown>;
  },
  trigger?: string,
): Promise<void> {
  try {
    await callMcpServer(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/messages`,
      {
        method: 'POST',
        body: payload,
        // Forward X-Guardian-Trigger so the MCP-side audit row that
        // gets written for this message append carries the same
        // trigger tag as the originating chat turn (e.g. `job:foo`).
        headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
      },
    );
  } catch (err) {
    console.warn(
      `chat: failed to persist ${payload.role} message to session ${sessionId}:`,
      err instanceof Error ? err.message : err,
    );
  }
}

interface PersistedMessage {
  role: string;
  content: string;
  tool_call_id?: string;
  created_at?: string;
  // Phase 4.5 — meta carries `kind: 'compaction-checkpoint'` and the
  // covers-until timestamp on synthesized checkpoint messages. Other
  // persisted messages may also use meta (model name on assistant
  // rows, tool args on tool rows) but those are read elsewhere.
  meta?: Record<string, unknown>;
}

/**
 * Render a persisted message into the exact text that will end up in
 * the prompt. Used both for cost estimation (Phase 2.3 token-budget
 * walk) and for the final emit pass below. Centralizing the
 * truncation rules in one helper means the cost estimate can never
 * drift from what we actually send.
 *
 * Returns `null` for messages we'd drop (system rows, empty content).
 */
function renderMessageForReplay(
  m: PersistedMessage,
): { kind: 'tool' | 'turn'; text: string } | null {
  if (m.role === 'system') return null;
  const content = (m.content ?? '').trim();
  if (!content) return null;
  if (m.role === 'tool') {
    // v0.1.28 — was TOOL_RESULT_MAX = 500. The 500-byte cap landed in
    // commit 159d199 ("Phase 1.1: Restore tool rows in chat replay")
    // when the chat plane had no Vertex caching and per-turn prompt
    // cost was a real worry. The world changed:
    //   - v0.1.7 wired Vertex cachedContent.create() for the system
    //     prompt (lib/system-prompt.ts), cutting input billing on the
    //     stable prefix to ~25%.
    //   - Gemini 2.5/3 added implicit prefix caching: any turn whose
    //     prompt-prefix bytes match the previous turn's bill at the
    //     cached rate automatically. Append-only chat history (which
    //     this codebase always is) qualifies for free.
    // Net effect: tool replays paid full price 100% of the time
    // pre-caching; today they bill at ~25% cached for every turn
    // except the first-after-cache-expiry. The 500-byte cap was
    // defending against a cost problem that's no longer load-bearing,
    // and it had the user-visible cost of cutting `xsiam_get_dataset_fields`
    // (17KB) and `xsiam_get_xql_examples` (1.5KB) to 3% and 33%
    // of their actual content on replay — directly observed in
    // session-2d3831d4.md where the model relayed the truncation stub
    // back to the operator instead of synthesizing an answer.
    //
    // 1 MiB ceiling here is a SAFETY VALVE, not a budget cap: catches
    // pathological "tool returns a 100 MB blob" cases without
    // affecting any real guardian workload. Guardian's largest known
    // tool output (`xsiam_get_dataset_fields` field catalog) is ~17 KB,
    // ~62x under this cap.
    //
    // If you find yourself wanting to LOWER this, instead first check:
    //   1. Is your turn paying full price? Look at chat_turn_cost
    //      audit rows — if `cached_input_tokens` is a healthy fraction
    //      of `input_tokens`, caching is working and the cap isn't
    //      the lever.
    //   2. Is one specific tool actually returning multi-MB outputs?
    //      Cap that tool's output at the source, not here.
    const TOOL_REPLAY_HARD_CAP_BYTES = 1_048_576; // 1 MiB
    const toolName = m.tool_call_id ?? '<unknown tool>';
    let body = content;
    if (body.length > TOOL_REPLAY_HARD_CAP_BYTES) {
      const elided = body.length - TOOL_REPLAY_HARD_CAP_BYTES;
      body =
        `${body.slice(0, TOOL_REPLAY_HARD_CAP_BYTES).trimEnd()}` +
        `…[truncated +${elided.toLocaleString()} bytes; this tool's full ` +
        `result was visible to the model in the original turn, only the ` +
        `head is retained on replay because the result exceeded the 1 MiB ` +
        `safety ceiling]`;
      // Rare path — every fire is worth a log line so we can see in
      // production whether the ceiling ever actually engages.
      console.warn(
        `chat: tool replay ceiling fired for ${toolName} ` +
          `(content was ${content.length.toLocaleString()} bytes, ` +
          `kept first ${TOOL_REPLAY_HARD_CAP_BYTES.toLocaleString()})`,
      );
    }
    return { kind: 'tool', text: `[Tool ${toolName} returned: ${body}]` };
  }
  return { kind: 'turn', text: content };
}

// Phase 3.2 — Session-history fetch fallback.
//
// Module-level memo keyed by sessionId. On a fetch success, we store
// the raw chronological messages with a 5s expiry. On a fetch failure,
// we fall back to the cached value (if any) so a transient MCP blip
// doesn't drop the agent's memory of the conversation mid-turn.
//
// 5s is the right TTL window: long enough to absorb back-to-back
// turns without re-fetching (a typical chat-pace round-trip is
// ~3-5s including model think time), short enough that
// freshly-persisted messages from the in-flight turn show up on the
// next call. Bigger TTLs would risk staleness; smaller TTLs would
// barely help during clustered turns.
//
// Cache key is sessionId only — message content is the same regardless
// of model, so two turns of the same session with different models
// share the cache. The budget walk runs per-turn against `raw`, so
// per-model differences materialize at the rendering layer, not the
// fetch layer.
//
// Note: this is a per-process cache. Guardian runs as a single Next.js
// server, so per-process is per-instance. If we ever scale-out the
// agent (multiple replicas behind a load balancer), this cache will
// silently de-dup per-replica, not globally — fine for short-TTL data
// like this.
interface HistoryCacheEntry {
  raw: PersistedMessage[];
  expiresAt: number;
}
const HISTORY_CACHE_TTL_MS = 5_000;
const historyCache = new Map<string, HistoryCacheEntry>();

/** Fetch raw persisted messages for a session, with in-process memo
 *  + fallback-on-failure. Returns the chronological message array
 *  (oldest-first) or [] if no cache and fetch fails.
 */
async function fetchSessionMessagesWithCache(
  sessionId: string,
  trigger: string | undefined,
): Promise<PersistedMessage[]> {
  const now = Date.now();
  const cached = historyCache.get(sessionId);
  if (cached && cached.expiresAt > now) {
    return cached.raw;
  }

  try {
    // Phase 2.4 — paginate the GET. We ask for newest-first
    // (`ascending=false`) so a long session never loses its most
    // recent turns; reversed client-side for the budget walk.
    const data = await callMcpServer<{ messages?: PersistedMessage[] }>(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/messages?limit=300&ascending=false`,
      {
        method: 'GET',
        headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
      },
    );
    const newestFirst = Array.isArray(data?.messages) ? data.messages : [];
    const raw = newestFirst.length === 0 ? [] : [...newestFirst].reverse();
    historyCache.set(sessionId, { raw, expiresAt: now + HISTORY_CACHE_TTL_MS });
    return raw;
  } catch (err) {
    // Fall back to cached if any. Operator-visible difference: an
    // intermittent MCP blip used to wipe the agent's memory of the
    // conversation for that one turn ("yesterday it remembered, today
    // it doesn't"). Now we silently use the slightly-stale snapshot
    // and the operator sees continuity.
    if (cached) {
      console.warn(
        `chat: history fetch for ${sessionId} failed; using cached snapshot:`,
        err instanceof Error ? err.message : err,
      );
      return cached.raw;
    }
    console.warn(
      `chat: failed to load session history for ${sessionId} — proceeding without context:`,
      err instanceof Error ? err.message : err,
    );
    return [];
  }
}

/**
 * Round-14 / Phase F.4 — read the session's persisted `preferred_model`
 * (set via the `/model <name>` slash command). Memoized for 30s per
 * session so the read doesn't add an MCP round-trip to every turn —
 * the operator only changes models once per cluster of turns, so the
 * TTL is generous without risking visible staleness.
 *
 * The chat handler resolves the effective model as:
 *   header-dropdown override (requestedModel)
 *   ?? session.metadata.preferred_model
 *   ?? runtimeConfig.GEMINI_MODEL
 *
 * Returns undefined when no preference is set (or the fetch fails —
 * the resolution chain just falls through to the runtime default).
 */
interface PreferredModelCacheEntry {
  value: string | undefined;
  expiresAt: number;
}
const PREFERRED_MODEL_CACHE_TTL_MS = 30_000;
const preferredModelCache = new Map<string, PreferredModelCacheEntry>();

async function loadSessionPreferredModel(
  sessionId: string,
  trigger: string | undefined,
): Promise<string | undefined> {
  const now = Date.now();
  const cached = preferredModelCache.get(sessionId);
  if (cached && cached.expiresAt > now) return cached.value;
  try {
    const data = await callMcpServer<{
      session?: { meta?: Record<string, unknown> };
    }>(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'GET',
      headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
    });
    const raw = data?.session?.meta?.['preferred_model'];
    const value =
      typeof raw === 'string' && raw.trim().length > 0 ? raw.trim() : undefined;
    preferredModelCache.set(sessionId, {
      value,
      expiresAt: now + PREFERRED_MODEL_CACHE_TTL_MS,
    });
    return value;
  } catch (err) {
    // Best-effort. A failure just means we use the runtime default.
    if (cached) return cached.value;
    console.warn(
      `chat: failed to read preferred_model for ${sessionId}:`,
      err instanceof Error ? err.message : err,
    );
    return undefined;
  }
}

/**
 * v0.1.27 — read the session's persisted `approval_mode` (set via the
 * chat-header dropdown or the /approval slash command). Mirrors the
 * preferred_model cache pattern: 30s TTL, best-effort fall-through.
 *
 * Values:
 *   'manual' (default): every gated tool call shows an inline approval
 *     card and blocks until the operator clicks Approve.
 *   'bypass': the chat handler attaches X-Guardian-Approval-Bypass: 1
 *     to every MCP call, so gated tools auto-approve (still recording
 *     audit rows with auto_approved=true).
 *
 * Anything other than 'bypass' resolves to manual — the default-secure
 * posture. Empty / missing metadata = manual.
 *
 * v0.3.27+: the type itself moved to lib/system-prompt.ts so the
 * prompt builder and the chat handler agree on the literal union.
 * Imported from there at the top of this file.
 */

interface ApprovalModeCacheEntry {
  value: ApprovalMode;
  expiresAt: number;
}
const APPROVAL_MODE_CACHE_TTL_MS = 30_000;
const approvalModeCache = new Map<string, ApprovalModeCacheEntry>();

async function loadSessionApprovalMode(
  sessionId: string,
  trigger: string | undefined,
): Promise<ApprovalMode> {
  const now = Date.now();
  const cached = approvalModeCache.get(sessionId);
  if (cached && cached.expiresAt > now) return cached.value;
  try {
    const data = await callMcpServer<{
      session?: { meta?: Record<string, unknown> };
    }>(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'GET',
      headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
    });
    const raw = data?.session?.meta?.['approval_mode'];
    const value: ApprovalMode = raw === 'bypass' ? 'bypass' : 'manual';
    approvalModeCache.set(sessionId, {
      value,
      expiresAt: now + APPROVAL_MODE_CACHE_TTL_MS,
    });
    return value;
  } catch (err) {
    if (cached) return cached.value;
    console.warn(
      `chat: failed to read approval_mode for ${sessionId}:`,
      err instanceof Error ? err.message : err,
    );
    return 'manual';
  }
}

/** Invalidate the approval-mode cache for a session. Currently unused
 *  externally — the dropdown PATCHes via the proxy route, then the
 *  next chat turn naturally re-reads after the 30s TTL elapses. Kept
 *  as a non-exported helper in case the dropdown needs immediate
 *  consistency in a future patch (e.g. "switch to bypass NOW for the
 *  in-flight turn"). Cannot be `export`ed from a Next.js route file —
 *  the App Router rejects non-method exports. */
function invalidateSessionApprovalModeCache(sessionId: string): void {
  approvalModeCache.delete(sessionId);
}
// Suppress "unused" lint until a caller materializes; harmless.
void invalidateSessionApprovalModeCache;

/** Invalidate the preferred-model cache for a session. Called by the
 *  /model handler after a PATCH so the same turn (or the next one)
 *  reads the freshly-set value instead of the stale cached one. */
function invalidateSessionPreferredModelCache(sessionId: string): void {
  preferredModelCache.delete(sessionId);
}

/** Fetch the prior persisted messages for a session and convert them to
 *  Gemini-compatible content blocks. Returns [] if the session is
 *  brand-new or the fetch fails (best-effort — a missing history
 *  shouldn't block the turn).
 *
 *  Round-12 fixed "the agent doesn't remember what we just talked
 *  about" by replaying messages here. Round-13 / Phase 2.3 makes the
 *  replay token-budgeted: instead of a fixed N-message slice, we walk
 *  newest-to-oldest accumulating estimated tokens until we hit the
 *  model's input budget (computed from its context cap minus output
 *  reserve, with a 30% safety margin for tokenizer drift). Phase 3.2
 *  layers a 5s in-process cache + fallback-on-failure underneath, so
 *  intermittent MCP blips don't wipe the agent's memory mid-turn.
 *
 *  Why budget-walk instead of message-count: a single 50k-token tool
 *  result used to consume the entire history slice silently; now it
 *  just consumes its proportional share of the budget and the rest of
 *  the conversation continues to fit. Long sessions with mostly small
 *  turns get *more* context, not less.
 */
/**
 * Phase 5 — auto-compaction hooks. Optional callbacks that
 * loadSessionHistory uses to summarize the dropped portion of history
 * when the budget walk would otherwise discard it. If `summarize` is
 * absent, behavior falls through to Phase 2.3's hard truncation.
 */
interface AutoCompactionHooks {
  /** Wraps an LLM call. Receives instructions + transcript, returns
   *  the model's summary text. Provider-agnostic; caller wires this
   *  to its summarizer of choice. */
  summarize?: (instructions: string, transcript: string) => Promise<string>;
  /** Persists the auto-compaction checkpoint so subsequent turns
   *  honor it via the existing checkpoint-aware path (Phase 4.5).
   *  Skip if you only want this turn to benefit (e.g., dry-run). */
  persistCheckpoint?: (
    summary: string,
    coversUntil: string,
    messagesSummarized: number,
  ) => Promise<void>;
  /** Live-telemetry hook. The chat route wires this to sendEvent so
   *  /observability/pipeline + the live-telemetry panel surface
   *  compaction activity in real-time. */
  onCompactionEvent?: (
    kind: 'start' | 'end' | 'failed',
    stats?: Record<string, unknown>,
  ) => void;
}

/** Threshold for auto-compaction: only fire if we'd otherwise drop
 *  this many messages. Below this, hard truncation is fine —
 *  summarizing 2-3 messages costs more than it saves. */
const AUTO_COMPACT_MIN_DROPPED = 5;

async function loadSessionHistory(
  sessionId: string,
  trigger: string | undefined,
  modelName: string | undefined,
  hooks?: AutoCompactionHooks,
): Promise<GeminiContent[]> {
  // Phase 3.2: cached fetch with fallback. Pure data-shape conversion
  // happens below; the rest of the function is unchanged.
  const fetched = await fetchSessionMessagesWithCache(sessionId, trigger);
  if (fetched.length === 0) return [];

  // Phase 4.5 — checkpoint awareness. Find the LATEST compaction-
  // checkpoint message; if present, slice the replay from it forward.
  // The checkpoint's content is the summary, persisted as role=system
  // with meta.kind=compaction-checkpoint. We render it as a single
  // user-role observation so Gemini's user/model alternation stays
  // valid and the model treats the summary as "what happened before
  // this turn." Anything BEFORE the checkpoint is conceptually
  // already-summarized and gets dropped from replay; the disk
  // transcript is unchanged.
  let raw: PersistedMessage[] = fetched;
  let priorCheckpointSummary: string | null = null;
  for (let i = fetched.length - 1; i >= 0; i--) {
    if (isCompactionCheckpoint(fetched[i])) {
      priorCheckpointSummary = fetched[i].content;
      raw = fetched.slice(i + 1); // everything after the checkpoint
      break;
    }
  }

  try {
    // Phase 2.3: token-budgeted walk. Compute the input budget for
    // this turn's model (cap × 0.7 - output reserve, with an 8k floor
    // for very small models). Walk raw newest-to-oldest, estimate
    // each message's rendered cost via renderMessageForReplay() so
    // tool-row truncation is reflected, and stop accumulating when
    // we'd exceed budget. Slice from there.
    //
    // Phase 4.5 — if a compaction checkpoint exists, pre-allocate
    // its token cost from the budget and emit it as the first
    // user-role message in `contents`. The budget walk over `raw`
    // (the post-checkpoint tail) gets a shrunk budget so the
    // checkpoint + replay together fit.
    let checkpointText = priorCheckpointSummary
      ? `[Earlier in this conversation, summarized via /compress: ${priorCheckpointSummary}]`
      : null;
    let checkpointTokens = checkpointText
      ? estimateMessageTokens(checkpointText)
      : 0;
    const budget = Math.max(
      0,
      computeInputBudget(modelName) - checkpointTokens,
    );
    let usedTokens = 0;
    let firstKeptIdx = raw.length;
    for (let i = raw.length - 1; i >= 0; i--) {
      const rendered = renderMessageForReplay(raw[i]);
      if (!rendered) continue;
      const cost = estimateMessageTokens(rendered.text);
      if (usedTokens + cost > budget) break;
      usedTokens += cost;
      firstKeptIdx = i;
    }

    // ── Phase 5 — auto-compaction at the budget edge ──────────
    //
    // If the budget walk would drop AT LEAST AUTO_COMPACT_MIN_DROPPED
    // messages AND we have a summarizer hook, summarize the dropped
    // portion into a checkpoint instead of letting it fall off.
    //
    // Phase 5.2 — tool-pair preservation: snap firstKeptIdx forward
    // past any consecutive tool rows so the cut point lands on a
    // user/assistant boundary. Otherwise the replay would start with
    // tool results whose `[Tool X returned: ...]` rendering would
    // imply preceding context the model has no record of.
    while (
      firstKeptIdx < raw.length &&
      firstKeptIdx > 0 &&
      raw[firstKeptIdx - 1].role === 'tool'
    ) {
      // The message AT firstKeptIdx is what we keep; the message
      // BEFORE it is the one that just got dropped. If that dropped
      // message is a tool row, push the cut earlier (smaller
      // firstKeptIdx) so the tool burst is fully in the summary.
      firstKeptIdx--;
    }

    const droppedCount = firstKeptIdx;
    if (
      droppedCount >= AUTO_COMPACT_MIN_DROPPED &&
      hooks?.summarize !== undefined
    ) {
      hooks.onCompactionEvent?.('start', {
        kind: 'auto',
        messages_to_summarize: droppedCount,
      });

      try {
        // Build the summarizer input. If a /compress checkpoint
        // already exists for this session, prepend it as a synthetic
        // "earlier summary" so the new auto-checkpoint covers
        // EVERYTHING from the conversation start through firstKeptIdx
        // — the new checkpoint then supersedes the prior one cleanly.
        const summaryInput: CompactionInputMessage[] = [];
        if (priorCheckpointSummary) {
          summaryInput.push({
            role: 'system',
            content: `[Prior compaction summary]\n${priorCheckpointSummary}`,
            created_at: undefined,
          });
        }
        summaryInput.push(...raw.slice(0, firstKeptIdx));

        const result = await compactMessages(
          summaryInput,
          hooks.summarize,
        );
        if (!result) {
          throw new Error('summarizer returned empty');
        }

        // Phase 5.3 — fire-and-forget persist. The next turn picks up
        // this checkpoint via Phase 4.5's discovery loop, so the
        // amortization kicks in on the FOLLOWING request, not this
        // one. await is best-effort: persist failure logs but doesn't
        // block the current turn.
        if (hooks.persistCheckpoint) {
          try {
            await hooks.persistCheckpoint(
              result.summary,
              result.coversUntil,
              result.messagesSummarized,
            );
          } catch (persistErr) {
            console.warn(
              `chat: auto-compaction checkpoint persist failed:`,
              persistErr instanceof Error ? persistErr.message : persistErr,
            );
          }
        }

        // Replace this turn's checkpointText with the freshly-
        // produced summary so it takes effect immediately. Drop the
        // dropped portion from raw (firstKeptIdx becomes 0).
        checkpointText = `[Compaction summary covering ${result.messagesSummarized} prior messages: ${result.summary}]`;
        checkpointTokens = estimateMessageTokens(checkpointText);
        raw = raw.slice(firstKeptIdx);
        firstKeptIdx = 0;

        hooks.onCompactionEvent?.('end', {
          kind: 'auto',
          messages_summarized: result.messagesSummarized,
          summary_chars: result.summary.length,
        });
      } catch (err) {
        // Phase 5.4 — fallback. Summarizer failure shouldn't block
        // the chat turn. Log + emit a `failed` event + fall through
        // to the existing Phase 2.3 hard-truncation behavior (the
        // dropped messages just don't get replayed; same as before
        // Phase 5).
        console.warn(
          `chat: auto-compaction failed; falling back to hard truncation:`,
          err instanceof Error ? err.message : err,
        );
        hooks?.onCompactionEvent?.('failed', {
          error: err instanceof Error ? err.message : String(err),
        });
      }
    }

    const slice = raw.slice(firstKeptIdx);
    const contents: GeminiContent[] = [];

    if (checkpointText) {
      contents.push({
        role: 'user',
        parts: [{ text: checkpointText }],
      });
    }

    // Phase-1.1 (now via renderMessageForReplay): tool rows are
    // INCLUDED in the replay, truncated, wrapped as
    // `[Tool <name> returned: <truncated>]`. Consecutive tool rows
    // coalesce into one user-role message via flushToolNotes() below.
    let pendingToolNotes: string[] = [];
    const flushToolNotes = () => {
      if (pendingToolNotes.length === 0) return;
      contents.push({
        role: 'user',
        parts: [{ text: pendingToolNotes.join('\n') }],
      });
      pendingToolNotes = [];
    };

    for (const m of slice) {
      const rendered = renderMessageForReplay(m);
      if (!rendered) continue;
      if (rendered.kind === 'tool') {
        pendingToolNotes.push(rendered.text);
        continue;
      }
      // Non-tool: flush any pending tool notes before us so they
      // appear in the right narrative position, then emit.
      flushToolNotes();
      const geminiRole = m.role === 'assistant' ? 'model' : 'user';
      contents.push({
        role: geminiRole,
        parts: [{ text: rendered.text }],
      });
    }
    // Trailing tool notes (rare — turn ended mid-tool) still flushed.
    flushToolNotes();
    return contents;
  } catch (err) {
    // Don't fail the turn — a missing history just means the agent
    // operates statelessly for this turn. Log so we can detect
    // patterns of failure.
    console.warn(
      `chat: failed to load session history for ${sessionId} — proceeding without context:`,
      err instanceof Error ? err.message : err,
    );
    return [];
  }
}

const GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta';
const VERTEX_API_BASE = 'https://aiplatform.googleapis.com/v1';

type GeminiFunctionCall = {
  name: string;
  args?: Record<string, unknown>;
};

type GeminiPart = {
  text?: string;
  // v0.17.87 — set to `true` by Gemini when the part is reasoning output
  // (engaged by generationConfig.thinkingConfig.includeThoughts = true).
  // The chat route emits these via the SSE `thinking` event instead of
  // `text_delta`, and they're excluded from the saved `.content` so the
  // operator's transcript shows reasoning collapsed-by-default and the
  // final answer cleanly.
  thought?: boolean;
  functionCall?: GeminiFunctionCall;
  functionResponse?: {
    name: string;
    response: Record<string, unknown>;
  };
};

type GeminiSystemInstruction = {
  role: 'system';
  parts: Array<{ text: string }>;
};

type GeminiContent = {
  role: 'user' | 'model';
  parts: GeminiPart[];
};

type DebugStep = {
  time: string;
  stage: string;
  detail: string;
};

type GeminiToolSet = Array<{ functionDeclarations: unknown }>;

// v0.6.6 — cache the BASE declarations (MCP tools only). The synthetic
// `subagent_create` tool is appended per-request based on the operator's
// `chat_subagents_enabled` preference. Pre-v0.6.6 the cache stored the
// full set including subagent_create, which made toggling impossible
// without a TTL-based cache flush.
let cachedBaseDecls: unknown[] | null = null;
let cachedBaseDeclsAt = 0;
let cachedBaseDeclsCount = 0;

/**
 * Read the operator's `chat_subagents_enabled` preference from operator-state.
 * v0.6.6 — defaults to `true` (subagents enabled), matching pre-v0.6.6 behavior.
 * Operator can flip via the chat header toggle (UI) or PUT
 * /api/v1/operator-state/chat_subagents_enabled directly (API).
 *
 * Failures fall back to enabled — the toggle is an opt-out, so if the
 * read fails (operator_state.db not yet seeded, network blip, etc.)
 * we preserve the documented default behavior.
 */
async function readSubagentsEnabled(): Promise<boolean> {
  try {
    const result = await callMcpServer<{ value?: unknown }>(
      `/api/v1/operator-state/${encodeURIComponent('chat_subagents_enabled')}`,
    );
    const raw = result?.value;
    // operator_state stores the value as the JSON-decoded shape the
    // hook chose. The UI persists either `true` / `false` directly
    // or `{ enabled: <bool> }`; accept both. Any other shape (or
    // missing) → default true.
    if (typeof raw === 'boolean') return raw;
    if (raw && typeof raw === 'object' && 'enabled' in (raw as Record<string, unknown>)) {
      const v = (raw as Record<string, unknown>).enabled;
      return typeof v === 'boolean' ? v : true;
    }
    return true;
  } catch {
    return true;
  }
}

/**
 * Read the operator's default model from operator-state (`default_model`).
 * Mirrors readSubagentsEnabled. The model detail page sets this via
 * PUT /api/v1/operator-state/default_model {value: {provider, model}}.
 * Returns the model id string, or undefined if unset/unreadable (→ caller
 * falls back to GEMINI_MODEL). Never throws.
 */
async function readDefaultModel(): Promise<string | undefined> {
  try {
    const result = await callMcpServer<{ value?: unknown }>(
      `/api/v1/operator-state/${encodeURIComponent('default_model')}`,
    );
    const raw = result?.value;
    if (raw && typeof raw === 'object' && 'model' in (raw as Record<string, unknown>)) {
      const m = (raw as Record<string, unknown>).model;
      return typeof m === 'string' && m.length > 0 ? m : undefined;
    }
    return undefined;
  } catch {
    return undefined;
  }
}

// ─── Empty-response fallback ──────────────────────────────────────────
//
// Build a context-aware message when the model finishes a turn without
// emitting any text (only function calls). Replaces the earlier
// hard-coded "No model response was returned. Review the tool results
// above or try a smaller request." string — that text was unhelpful in
// the most common case (model called tools successfully but didn't
// narrate, e.g. after an approval-gated jobs_create where the post-
// approval response is sometimes a bare functionCall with no text).
//
// Distinguishes three Gemini finishReason cases:
//   STOP       — the model chose to stop (most common when text is empty
//                after tools succeed). We summarize what ran.
//   MAX_TOKENS — output got truncated. We say so explicitly so the
//                operator knows to ask a smaller question.
//   SAFETY     — content was blocked. Surface that vs. silent.
//   RECITATION — same family; surface explicitly.
/**
 * Issue #17 — pre-tool-call preamble synthesis.
 *
 * Render a one-line "I'll run <tool> with <key args>" string for the
 * chat thread when the model emitted a function call without any
 * accompanying text. Goal: the operator never sees an approval card
 * pop out of nowhere; there's always at least a server-synthesized
 * sentence above it explaining what's about to happen.
 *
 * Argument summarization rules (kept simple on purpose):
 *   - Pick at most 4 args to surface inline (the rest live in the
 *     approval card's expandable "Raw arguments").
 *   - Prefer human-meaningful keys when present: name, prompt,
 *     description, cron, instance_id, connector_id, url, query —
 *     anything that gives the operator a clue about the action.
 *   - Truncate any single value to 80 chars so the preamble stays
 *     readable; never show secret-looking keys (api_key, password,
 *     token, secret) — those go to the args expander, not the
 *     plain-text chat history.
 *   - For `subagent_create` and other meta-tools, prefer their
 *     `task` / `goal` field when present.
 *
 * Returns null when there's nothing useful to say (e.g. no args at
 * all). The caller skips the sendEvent in that case rather than
 * emit "I'll run X with no arguments."
 */
const _PREFERRED_ARG_KEYS = [
  'name', 'task', 'goal', 'prompt', 'description', 'cron',
  'connector_id', 'instance_id', 'instance_name',
  'url', 'query', 'pattern', 'format', 'destination',
  'session_id', 'tool_name', 'reason',
];
const _SECRET_LOOKING_KEYS = /^(api_?key|password|secret|token|bearer|kek|jwt)$/i;

function _summarizeArgValue(value: unknown): string {
  if (value === null || value === undefined) return '∅';
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed.length > 80 ? `${trimmed.slice(0, 77)}…` : trimmed;
  }
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    const inner = value.length === 0 ? '' : `${value.length} item${value.length === 1 ? '' : 's'}`;
    return `[${inner}]`;
  }
  if (typeof value === 'object') {
    const keys = Object.keys(value as Record<string, unknown>);
    return keys.length === 0 ? '{}' : `{${keys.slice(0, 3).join(', ')}${keys.length > 3 ? ', …' : ''}}`;
  }
  return String(value).slice(0, 80);
}

function formatToolPreamble(
  toolName: string,
  args: Record<string, unknown>,
): string | null {
  const allKeys = Object.keys(args);
  if (allKeys.length === 0) {
    // No args — just announce the tool. Useful for things like
    // approvals_list_pending, list_workers, etc., where the act of
    // calling IS the entire intent.
    return `I'll call \`${toolName}\`.`;
  }
  // Filter out secret-looking keys before deciding what to surface.
  const safeKeys = allKeys.filter((k) => !_SECRET_LOOKING_KEYS.test(k));
  // Order: preferred keys first (in their declared order), then
  // remaining safe keys alphabetically. Cap at 4.
  const preferred = _PREFERRED_ARG_KEYS.filter((k) => safeKeys.includes(k));
  const remaining = safeKeys
    .filter((k) => !preferred.includes(k))
    .sort();
  const surface = [...preferred, ...remaining].slice(0, 4);
  if (surface.length === 0) {
    // Everything was secret-looking. Don't leak through the preamble.
    return `I'll call \`${toolName}\` (arguments hidden — credentials).`;
  }
  const parts = surface.map((k) => `${k}=\`${_summarizeArgValue(args[k])}\``);
  const more = safeKeys.length > surface.length
    ? ` (+ ${safeKeys.length - surface.length} more)`
    : '';
  return `I'll call \`${toolName}\` with ${parts.join(', ')}${more}.`;
}

function synthesizeFallbackText(
  toolCalls: Array<{ tool: string; args: Record<string, unknown>; result: string; error?: string }>,
  finishReason: string | undefined,
): string {
  // Tool-flow specific: certain tool names map cleanly to "X happened"
  // confirmations. Operators care most about whether the side-effecting
  // call (jobs_create, instances_create, …) succeeded; everything else
  // is preamble (memory_search, *_get).
  const SIDE_EFFECT_TOOLS = new Set([
    'jobs_create', 'jobs_update', 'jobs_delete', 'jobs_run_now',
    'personality_update', 'personality_reset',
    'settings_update', 'settings_reset',
    'instances_create', 'instances_update', 'instances_delete',
    'providers_create', 'providers_update', 'providers_delete',
    'api_keys_create', 'api_keys_rotate', 'api_keys_revoke',
    'memory_store', 'notifications_dismiss', 'approvals_resolve',
    // v0.17.127 — catalog mutations the operator cares about confirming.
    // Previously omitted: a turn that installed a connector recapped only
    // `memory_store`, hiding the actual action. This set is hand-maintained
    // — when a new operator-meaningful side-effecting tool ships, add it
    // here so the no-text fallback recap names it.
    'marketplace_install', 'marketplace_uninstall', 'connector_upload',
  ]);

  const sideEffects = toolCalls.filter((tc) => SIDE_EFFECT_TOOLS.has(tc.tool));

  // Truncation / safety prefixes — these go FIRST so the operator sees
  // the limit cause before the recap.
  if (finishReason === 'MAX_TOKENS') {
    if (sideEffects.length > 0) {
      const list = sideEffects.map((tc) => `\`${tc.tool}\``).join(', ');
      return `✓ Completed ${list} but my reply was cut off by the token limit. Ask me to summarize what was done if you need more detail.`;
    }
    return '⚠ My response hit the token limit before I could finish. Try a more focused request.';
  }
  if (finishReason === 'SAFETY' || finishReason === 'RECITATION') {
    return `⚠ My response was blocked (\`${finishReason}\`). Try rephrasing your request.`;
  }

  // Normal STOP-with-no-text case: model finished cleanly but had nothing
  // to say. Recap what actually ran.
  if (sideEffects.length > 0) {
    const list = sideEffects.map((tc) => `\`${tc.tool}\``).join(', ');
    const verb = sideEffects.length === 1 ? 'change' : 'changes';
    return `✓ Done. Applied ${sideEffects.length} ${verb}: ${list}. Let me know if you need a summary or next steps.`;
  }
  if (toolCalls.length > 0) {
    // Read-only flow: the agent looked things up but didn't act. Most
    // often this means the model had no follow-up (e.g. the lookup was
    // its own answer to a previous question that already got responded
    // to). Less alarming phrasing than the original.
    return `I checked ${toolCalls.length} tool${toolCalls.length === 1 ? '' : 's'} but didn't generate a follow-up message. Let me know what you'd like next.`;
  }
  // No tools, no text — genuinely empty turn. Likely a transient model
  // hiccup. Ask the user to retry.
  return 'I didn\'t generate a response this turn. Please try again or rephrase your request.';
}

// ─── Approval-poll helpers (Phase 11 — chat-driven self-mod UX) ────

interface ApprovalRow {
  id: string;
  tool: string;
  namespaced: string;
  actor: string | null;
  risk_tier?: string;
  created_at: string;
  args: Record<string, unknown>;
  status: string;
}

/**
 * Get current pending approval IDs from the MCP. Used as a snapshot
 * just before a gated tool call so the polling loop can detect the
 * NEW row created by that call (rather than reacting to unrelated
 * pending rows).
 */
/**
 * Fetch the set of currently-pending approval IDs.
 *
 * v0.1.26: accepts an optional sessionId and scopes the listing to
 * `origin=chat:<sessionId>` so the chat-side poll loop only sees
 * approvals THIS chat session created. Without the filter, a
 * job-fired approval (origin=job:<name>) landing concurrently would
 * appear in the snapshot diff and the chat UI would render an
 * inline card for an approval the operator can't actually act on
 * from this surface.
 *
 * Falls back to unfiltered listing when sessionId is omitted —
 * keeps the v0.1.25 fast-path callers working unchanged.
 */
async function fetchPendingApprovalIds(
  sessionId?: string,
): Promise<Set<string>> {
  try {
    const params = new URLSearchParams({ status: 'pending' });
    if (sessionId) params.set('origin', `chat:${sessionId}`);
    const resp = await callMcpServer<{ approvals?: ApprovalRow[] }>(
      `/api/v1/approvals?${params.toString()}`,
      { method: 'GET', timeoutMs: 5000 },
    );
    return new Set((resp.approvals ?? []).map((a) => a.id));
  } catch {
    return new Set<string>();
  }
}

/**
 * Race against the bus.wait_async block: poll /api/v1/approvals every
 * 250ms looking for a new pending row matching the just-called tool.
 * Calls onFound(row) at most ONCE then exits. Also exits on signal
 * abort (tool call resolved, no need to keep polling) or after
 * MAX_POLL_MS (the operator never approved; the chat will see the
 * timeout via the original tool call's wait_async).
 */
async function pollForNewApproval({
  signal,
  snapshot,
  toolName,
  onFound,
  sessionId,
}: {
  signal: AbortSignal;
  snapshot: Set<string>;
  toolName: string;
  onFound: (row: ApprovalRow) => void;
  /** v0.1.26: scopes the poll to chat:<sessionId> so a job-fired
   *  approval landing concurrently doesn't trigger a spurious card
   *  in the wrong chat thread. */
  sessionId?: string;
}): Promise<void> {
  const MAX_POLL_MS = 6_000; // ~24 polls. The MCP gate would fire by then.
  const POLL_INTERVAL_MS = 250;
  const deadline = Date.now() + MAX_POLL_MS;
  let found = false;
  // v0.1.26: server-side origin filter when sessionId is known.
  // Falls back to unfiltered ?status=pending for backwards-compat
  // (older callers that don't have a session in scope).
  const params = new URLSearchParams({ status: 'pending' });
  if (sessionId) params.set('origin', `chat:${sessionId}`);
  const url = `/api/v1/approvals?${params.toString()}`;
  while (!signal.aborted && Date.now() < deadline && !found) {
    try {
      const resp = await callMcpServer<{ approvals?: ApprovalRow[] }>(
        url,
        { method: 'GET', timeoutMs: 2000 },
      );
      for (const row of resp.approvals ?? []) {
        if (snapshot.has(row.id)) continue;
        // Match by tool name (and bare-name forms): the gate uses
        // tool=bare in self_mod_tools.py, so the pending row's
        // `tool` field will equal the toolName the chat passed.
        if (row.tool === toolName || row.namespaced === toolName) {
          onFound(row);
          found = true;
          break;
        }
      }
    } catch {
      // Transient — retry on next tick.
    }
    if (found || signal.aborted) break;
    await new Promise((resolve) => {
      const t = setTimeout(resolve, POLL_INTERVAL_MS);
      signal.addEventListener('abort', () => {
        clearTimeout(t);
        resolve(undefined);
      });
    });
  }
}

const UNSUPPORTED_GEMINI_SCHEMA_KEYS = new Set([
  '$id',
  '$schema',
  'additionalItems',
  'additionalProperties',
  'const',
  'contains',
  'default',
  'dependentRequired',
  'dependentSchemas',
  'else',
  'examples',
  'exclusiveMaximum',
  'exclusiveMinimum',
  'if',
  'maxProperties',
  'minProperties',
  'not',
  'pattern',
  'patternProperties',
  'propertyNames',
  'then',
  'title',
  'unevaluatedItems',
  'unevaluatedProperties',
]);

function sanitizeSchema(
  schema: Record<string, unknown>,
  defs: Record<string, unknown> = {},
  depth = 0,
  processing: Set<string> = new Set()
): Record<string, unknown> {
  if (depth > 10) {
    return { type: 'object', description: 'Complex schema (truncated)' };
  }

  const localSchema = { ...schema };

  for (const key of UNSUPPORTED_GEMINI_SCHEMA_KEYS) {
    delete localSchema[key];
  }

  if ('$defs' in localSchema && typeof localSchema.$defs === 'object' && localSchema.$defs) {
    Object.assign(defs, localSchema.$defs as Record<string, unknown>);
    delete localSchema.$defs;
  }

  if ('definitions' in localSchema && typeof localSchema.definitions === 'object' && localSchema.definitions) {
    Object.assign(defs, localSchema.definitions as Record<string, unknown>);
    delete localSchema.definitions;
  }

  if ('$ref' in localSchema && typeof localSchema.$ref === 'string') {
    const ref = localSchema.$ref;
    const refName = ref.split('/').pop() || ref;
    delete localSchema.$ref;

    if (processing.has(refName)) {
      return { type: 'object', description: `Recursive reference to ${refName}` };
    }

    const resolved = defs[refName];
    if (resolved && typeof resolved === 'object') {
      processing.add(refName);
      const merged = sanitizeSchema(resolved as Record<string, unknown>, defs, depth + 1, new Set(processing));
      processing.delete(refName);
      return merged;
    }

    return { type: 'string', description: `Reference to ${refName}` };
  }

  const complexKeys = ['oneOf', 'anyOf', 'allOf'] as const;
  let hasComplex = false;
  for (const key of complexKeys) {
    if (key in localSchema) {
      delete localSchema[key];
      hasComplex = true;
    }
  }

  if (hasComplex) {
    return {
      ...localSchema,
      type: 'object',
      description: `${(localSchema.description as string) || 'Complex variant'} (simplified)`,
    };
  }

  if (typeof localSchema.properties === 'object' && localSchema.properties) {
    const props = localSchema.properties as Record<string, unknown>;
    for (const [key, value] of Object.entries(props)) {
      if (value && typeof value === 'object') {
        props[key] = sanitizeSchema(value as Record<string, unknown>, defs, depth + 1, new Set(processing));
      }
    }
  }

  if (typeof localSchema.items === 'object' && localSchema.items) {
    localSchema.items = sanitizeSchema(
      localSchema.items as Record<string, unknown>,
      defs,
      depth + 1,
      new Set(processing)
    );
  }

  return localSchema;
}

async function getGeminiTools(
  mcpClient: GuardianMCPClient,
  runtimeConfig: EffectiveRuntimeConfig,
  logDebug: (stage: string, detail: string) => void,
  subagentsEnabled: boolean,
): Promise<GeminiToolSet> {
  const parsedToolCacheTtl = Number(runtimeConfig.MCP_TOOL_CACHE_TTL_MS || 300000);
  const mcpToolCacheTtlMs = Number.isFinite(parsedToolCacheTtl) && parsedToolCacheTtl > 0
    ? parsedToolCacheTtl
    : 300000;
  const now = Date.now();

  // v0.6.6 — base declarations are cached (TTL-bound). The synthetic
  // `subagent_create` tool is appended PER REQUEST based on
  // `subagentsEnabled` so the toggle takes effect immediately on the
  // next turn without waiting for cache eviction.
  let baseDecls = cachedBaseDecls;
  if (baseDecls && now - cachedBaseDeclsAt < mcpToolCacheTtlMs) {
    logDebug('mcp', `Loaded ${cachedBaseDeclsCount} cached base tool schemas`);
  } else {
    const mcpTools = await mcpClient.listTools();
    logDebug('mcp', `Loaded ${mcpTools.length} tools from MCP`);
    baseDecls = mcpTools.map((tool: MCPTool) => {
      const rawSchema = (tool.inputSchema || {}) as Record<string, unknown>;
      return {
        name: tool.name,
        description: tool.description || '',
        parameters: sanitizeSchema(rawSchema),
      };
    });
    cachedBaseDecls = baseDecls;
    cachedBaseDeclsAt = now;
    cachedBaseDeclsCount = baseDecls.length;
    logDebug('mcp', `Cached ${cachedBaseDeclsCount} base tool schemas`);
  }

  // Round-15 / Phase S — append the synthetic `subagent_create`
  // function so the model sees it as just-another-tool. The
  // chat-route's tool dispatch loop intercepts calls to this
  // name and routes them to runSubagent (no MCP round-trip).
  // v0.6.6 — gated by the operator's `chat_subagents_enabled`
  // preference. When false, the spec is omitted and the model
  // sees a catalog without subagent_create.
  const declarations = subagentsEnabled
    ? [...baseDecls, SUBAGENT_CREATE_TOOL_SPEC]
    : [...baseDecls];

  logDebug(
    'mcp',
    `Tool catalog: ${declarations.length} schemas` +
      (subagentsEnabled ? ' (incl. subagent_create)' : ' (subagents disabled)'),
  );
  return [{ functionDeclarations: declarations }];
}

type GeminiCallPayload = {
  contents: GeminiContent[];
  tools: Array<{ functionDeclarations: unknown }>;
  systemInstruction?: GeminiSystemInstruction;
  // v0.2.3 — generationConfig is now optional with no default fields.
  // Previously the chat handler hardcoded `maxOutputTokens: 4096` here,
  // which capped Gemini's output at 6% of the model's natural ceiling
  // (~65K tokens for gemini-3.1-pro-preview). Multi-step responses with
  // rich tool-output narration routinely hit the cap and truncated mid-
  // sentence (the v0.1.36 backup/restore plan, the v0.2.2 attack-chain
  // skill executions, etc). The Trevor_-_Bot Slack integration that
  // shares this MCP server doesn't set the cap and handles long
  // responses fine; bringing Guardian's chat handler onto the same
  // pattern. Now caller-overridable via an optional explicit
  // maxOutputTokens; default = unset = let Gemini use the model max.
  generationConfig?: {
    maxOutputTokens?: number;
    // v0.5.32 / wire-up for v0.5.22's thinking_enabled. When the
    // caller passes `thinking: true`, callGemini sets thinkingConfig
    // here with `thinkingBudget: -1` (Gemini's "use what you need"
    // signal). Flash variants silently ignore; Pro variants honor.
    thinkingConfig?: {
      thinkingBudget: number;
      includeThoughts?: boolean;
    };
  };
  // v0.17.117 — forced function-calling. mode:'ANY' makes Gemini MUST
  // return a functionCall part (no text-only / thought-only turn). Used by
  // the leaked-tool-call recovery path (issue #114): when a thinking model
  // serializes a large tool call as `thought` text instead of a structured
  // functionCall (dropping it + ending the turn), we retry with mode:'ANY'
  // + thinking off to force a clean structured call.
  toolConfig?: {
    functionCallingConfig: {
      mode: 'AUTO' | 'ANY' | 'NONE';
    };
  };
};

function resolveVertexLocation(modelName: string) {
  if (modelName.toLowerCase().includes('gemini-3') || modelName.toLowerCase().includes('experimental')) {
    return 'global';
  }
  return 'us-central1';
}

/**
 * Detect placeholder / sample / fake GCP service-account credentials.
 *
 * Without this guard, the GoogleAuth client downstream attempts a JWT
 * sign() on a fake `private_key`, Node's OpenSSL decoder throws
 * `error:1E08010C:DECODER routines::unsupported`, and that bubbles to
 * the operator as a cryptic Node error. Job runs in particular emit
 * a `job-run-failed` notification on every fire — noisy and unhelpful.
 *
 * We catch the obvious shapes pre-flight and turn the failure into a
 * clear operator-actionable message. The detection is intentionally
 * conservative — false positives would block legitimate operators with
 * unusual but valid keys, so we only flag patterns where the input
 * could not possibly authenticate.
 *
 * Returns a reason string when placeholder is detected, or null when
 * the credentials at least pass surface-level validity checks (a real
 * key could still fail at sign-time for other reasons; that's the auth
 * library's job to surface with its own errors).
 */
// Module-internal — Next.js 15's `route.ts` files reject arbitrary
// exports as "does not match the required types of a Next.js Route."
// Only HTTP-method handlers (GET / POST / etc.) and the documented
// route-config exports (dynamic / runtime / revalidate / etc.) are
// allowed. Keep this helper local; if it ever needs unit tests, move
// it to `lib/chat-credentials.ts` and import from there.
function detectPlaceholderCredential(
  credentials: Record<string, unknown> | null,
): string | null {
  if (!credentials) return null;

  // Required structural fields that any real GCP service-account JSON has.
  // Missing any of these is a hard placeholder signal.
  const required = ['type', 'project_id', 'private_key', 'client_email'] as const;
  for (const field of required) {
    if (typeof credentials[field] !== 'string' || !(credentials[field] as string).trim()) {
      return `GOOGLE_APPLICATION_CREDENTIALS missing required field: ${field}`;
    }
  }

  const privateKey = String(credentials.private_key);
  // Real PKCS#8 RSA keys start with `-----BEGIN PRIVATE KEY-----` and
  // contain a base64 blob of ~1500-2000 chars. A real key body is at
  // least ~600 chars between the BEGIN/END markers (smaller P-256/P-384
  // keys aren't used by GCP service accounts as of writing).
  if (!privateKey.includes('BEGIN PRIVATE KEY') && !privateKey.includes('BEGIN RSA PRIVATE KEY')) {
    return 'GOOGLE_APPLICATION_CREDENTIALS private_key is not in PEM format';
  }
  // Strip the markers + newlines and check the base64 body length.
  const body = privateKey
    .replace(/-----BEGIN [A-Z ]+ KEY-----/g, '')
    .replace(/-----END [A-Z ]+ KEY-----/g, '')
    .replace(/[\r\n\\]/g, '')
    .trim();
  // Real GCP keys' base64 body is ~1600+ chars. Anything less is fake.
  // We also catch the literal string "fake" which is the most common
  // placeholder value in sample env files.
  if (body.length < 200 || /^fake$/i.test(body) || /^placeholder/i.test(body)) {
    return (
      'GOOGLE_APPLICATION_CREDENTIALS private_key looks like a placeholder ' +
      `(${body.length} chars between BEGIN/END markers; real keys are ~1600+ chars). ` +
      'Set GEMINI_API_KEY for direct API access, or replace with a real GCP service-account JSON.'
    );
  }
  // Common sample client_email patterns — the `@y.com` style we saw in
  // the wild on guardian-vm, plus `@example.com`, `@test.com`.
  const clientEmail = String(credentials.client_email);
  if (
    /^[^@]+@y\.com$/i.test(clientEmail) ||
    /@example\.com$/i.test(clientEmail) ||
    /@test\.com$/i.test(clientEmail)
  ) {
    return (
      `GOOGLE_APPLICATION_CREDENTIALS client_email looks like a placeholder (${clientEmail}). ` +
      'Replace with a real GCP service-account JSON or use GEMINI_API_KEY instead.'
    );
  }
  return null;
}

function parseCredentialsInput(input: string) {
  const trimmed = input.trim();
  if (!trimmed) {
    return { credentials: null, keyFile: null };
  }

  if (trimmed.startsWith('{')) {
    // The downstream GoogleAuth library accepts the parsed JSON as
    // `any` — we keep it loose here so existing call sites (project_id,
    // client_email lookups) don't need extra type assertions.
    let parsed: ReturnType<typeof JSON.parse>;
    try {
      parsed = JSON.parse(trimmed);
    } catch (error) {
      throw new Error(`GOOGLE_APPLICATION_CREDENTIALS JSON parse failed: ${String(error)}`);
    }
    // v0.1.34 — placeholder guard. See detectPlaceholderCredential
    // above for the rationale. Throwing here means callGeminiWithVertex
    // never reaches the GoogleAuth code path, so the OpenSSL decoder
    // error never surfaces. The operator (or scheduled job) sees a
    // clean message instead.
    const placeholderReason = detectPlaceholderCredential(
      typeof parsed === 'object' && parsed !== null ? parsed : null,
    );
    if (placeholderReason) {
      throw new Error(placeholderReason);
    }
    return { credentials: parsed, keyFile: null };
  }

  return { credentials: null, keyFile: trimmed };
}

/**
 * Transient network-failure codes that are safe to retry on a model call.
 *
 * Node's fetch (undici) throws `TypeError: fetch failed` for socket-level
 * failures — the real code lives on `err.cause`, NOT the top-level
 * message. The loop-killer in the autonomous investigation runs was
 * `UND_ERR_SOCKET` ("other side closed"): Vertex drops the long
 * `generateContent` connection under bursty/throttled load, undici
 * surfaces it as a bare `fetch failed`, and the old rate-limit-only
 * predicate let it fall straight through to a fatal
 * `chat error event: fetch failed`.
 */
const TRANSIENT_NETWORK_CODES = new Set([
  'UND_ERR_SOCKET', // socket closed mid-request — the loop-killer
  'UND_ERR_CONNECT_TIMEOUT',
  'UND_ERR_HEADERS_TIMEOUT',
  'UND_ERR_BODY_TIMEOUT',
  'ECONNRESET',
  'ECONNREFUSED',
  'ETIMEDOUT',
  'EPIPE',
  'EAI_AGAIN', // transient DNS failure
]);

/**
 * Returns the transient network code if `err` (or anything in its
 * `cause` chain) is a retryable socket-level failure, else null.
 *
 * We walk the whole cause chain so a code buried two levels deep still
 * matches, and treat a bare `fetch failed` / `socket hang up` /
 * `other side closed` as transient because undici only throws those for
 * network errors — HTTP error statuses don't throw, they return a
 * non-ok response (handled separately by the 429 string predicate).
 */
function transientNetworkCode(err: unknown): string | null {
  const seen = new Set<unknown>();
  let cur: unknown = err;
  while (cur instanceof Error && !seen.has(cur)) {
    seen.add(cur);
    const rawCode = (cur as { code?: unknown }).code;
    const code = typeof rawCode === 'string' ? rawCode : null;
    if (code && TRANSIENT_NETWORK_CODES.has(code)) {
      return code;
    }
    const m = cur.message.toLowerCase();
    if (
      m.includes('fetch failed') ||
      m.includes('socket hang up') ||
      m.includes('other side closed') ||
      m.includes('econnreset')
    ) {
      return code ?? 'fetch failed';
    }
    cur = (cur as { cause?: unknown }).cause;
  }
  return null;
}

/**
 * v0.1.25 / v0.1.4-hardening — Vertex/Gemini model-call retry wrapper.
 *
 * Retries two classes of transient failure with exponential backoff +
 * jitter:
 *   1. 429 / RESOURCE_EXHAUSTED — Vertex per-minute quota under bursty
 *      agent load (overlapping cron jobs + chat traffic). Pre-v0.1.25 a
 *      429 bubbled straight to the operator / scheduled jobs as
 *      `chat error event: Vertex AI error: 429`. [v0.1.25]
 *   2. Transient socket resets — UND_ERR_SOCKET / ECONNRESET / connect
 *      + body timeouts that undici surfaces as a bare `fetch failed`.
 *      These killed EVERY autonomous investigation run pre-v0.1.4: the
 *      agent opened a Guardian Issue, then a mid-investigation model
 *      call hit a socket reset that the rate-limit-only predicate didn't
 *      cover, so the whole turn died with `fetch failed`. [v0.1.4]
 *
 * Any other error propagates immediately so real bugs aren't masked.
 * `generateContent` has no Vertex-side side effects, so retrying a POST
 * is safe (worst case re-bills one generation on a rare mid-body reset).
 *
 * Backoff pattern ported from the blackhat-noc Slack bot's
 * `send_message_with_backoff` (initial 2s, x2 each retry, 0–1s jitter,
 * max 5 retries).
 */
async function withModelCallRetry<T>(
  fn: () => Promise<T>,
  opts: { maxRetries?: number; initialDelayMs?: number; label?: string } = {},
): Promise<T> {
  const maxRetries = opts.maxRetries ?? 5;
  let delayMs = opts.initialDelayMs ?? 2000;
  let attempt = 0;
  while (true) {
    try {
      return await fn();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const isRateLimit =
        msg.includes('429') ||
        msg.includes('RESOURCE_EXHAUSTED') ||
        msg.includes('Resource exhausted') ||
        msg.toLowerCase().includes('rate limit');
      const netCode = isRateLimit ? null : transientNetworkCode(err);
      if ((!isRateLimit && !netCode) || attempt >= maxRetries) {
        throw err;
      }
      attempt += 1;
      const jitterMs = Math.floor(Math.random() * 1000);
      const sleepMs = delayMs + jitterMs;
      const reason = isRateLimit ? '429/quota' : `transient network (${netCode})`;
      // eslint-disable-next-line no-console
      console.warn(
        `[chat] ${opts.label ?? 'gemini'} hit ${reason}; retry ${attempt}/${maxRetries} in ${sleepMs}ms`,
      );
      await new Promise((r) => setTimeout(r, sleepMs));
      delayMs *= 2; // exponential
    }
  }
}

async function callGeminiWithApiKey(
  payload: GeminiCallPayload,
  runtimeConfig: EffectiveRuntimeConfig,
  modelName: string,
) {
  if (!runtimeConfig.GEMINI_API_KEY) {
    throw new Error('GEMINI_API_KEY is required for the Gemini API call.');
  }

  return withModelCallRetry(
    async () => {
      const response = await fetch(
        `${GEMINI_API_BASE}/models/${encodeURIComponent(modelName)}:generateContent?key=${runtimeConfig.GEMINI_API_KEY}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        },
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Gemini API error: ${response.status} ${errorText}`);
      }

      return response.json();
    },
    { label: `gemini-api-key:${modelName}` },
  );
}

async function callGeminiWithVertex(
  payload: GeminiCallPayload,
  runtimeConfig: EffectiveRuntimeConfig,
  modelName: string,
) {
  if (!runtimeConfig.GOOGLE_APPLICATION_CREDENTIALS) {
    throw new Error('GOOGLE_APPLICATION_CREDENTIALS is required for Vertex AI.');
  }

  const { credentials, keyFile } = parseCredentialsInput(runtimeConfig.GOOGLE_APPLICATION_CREDENTIALS);
  const auth = new GoogleAuth({
    credentials: credentials || undefined,
    keyFile: keyFile || undefined,
    scopes: ['https://www.googleapis.com/auth/cloud-platform'],
  });

  const projectId =
    credentials?.project_id || (await auth.getProjectId());

  if (!projectId) {
    throw new Error('Vertex AI requires a project_id in GOOGLE_APPLICATION_CREDENTIALS.');
  }

  const location = resolveVertexLocation(modelName);
  const accessToken = await auth.getAccessToken();

  if (!accessToken) {
    throw new Error('Failed to obtain Vertex AI access token.');
  }

  // ── Phase 6 — Vertex context caching for the system prompt ───
  //
  // Try to swap the inline systemInstruction for a cached resource
  // reference. Cached input tokens are billed at ~25% — for a 13k
  // system prompt sent on every turn, that's the kind of saving
  // that makes a difference at scale.
  //
  // OPT-IN VIA ENV: gated behind `GUARDIAN_VERTEX_CACHE=1`. The
  // initial deploy of Phase 6 broke the CI smoke-test's manual-job
  // path on gemini-3.1-pro-preview — the model accepts the
  // cachedContents create call but rejects subsequent
  // generateContent requests that reference the cache (the
  // preview-channel SDK quirk). Rather than enable globally and
  // discover edge cases per-model, ship the helper off-by-default
  // and let an operator turn it on once they've validated their
  // model+region combination supports it. Direct API key path is
  // unaffected either way (Phase 6 only touches Vertex).
  let requestPayload: GeminiCallPayload | (Omit<GeminiCallPayload, 'systemInstruction'> & { cachedContent: string }) = payload;
  const cacheEnabled = process.env.GUARDIAN_VERTEX_CACHE === '1';
  const systemPromptText =
    payload.systemInstruction?.parts
      ?.map((p) => ('text' in p && p.text) || '')
      .join('') ?? '';
  if (cacheEnabled && systemPromptText) {
    try {
      const cacheName = await getOrCreateSystemPromptCache({
        systemPromptText,
        modelName,
        projectId,
        location,
        accessToken,
      });
      if (cacheName) {
        // Vertex rejects payloads that include BOTH cachedContent
        // and a matching systemInstruction. Drop the inline copy
        // when we're referencing the cache.
        const { systemInstruction: _omit, ...rest } = payload;
        void _omit;
        requestPayload = { ...rest, cachedContent: cacheName };
      }
    } catch (err) {
      // Belt-and-suspenders: any unexpected error from the cache
      // helper falls through to the inline path. The helper itself
      // already returns null on most failure modes, but if a
      // helper-level invariant ever throws, we don't want it to
      // poison the chat turn.
      console.warn(
        'vertex-cache: unexpected error, falling back to inline systemInstruction:',
        err instanceof Error ? err.message : err,
      );
    }
  }

  return withModelCallRetry(
    async () => {
      const response = await fetch(
        `${VERTEX_API_BASE}/projects/${encodeURIComponent(projectId)}/locations/${location}` +
          `/publishers/google/models/${encodeURIComponent(modelName)}:generateContent`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(requestPayload),
        },
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Vertex AI error: ${response.status} ${errorText}`);
      }

      return response.json();
    },
    { label: `vertex:${modelName}@${location}` },
  );
}

function isInvalidGeminiApiKeyError(error: unknown) {
  return (
    error instanceof Error &&
    (error.message.includes('API_KEY_INVALID') || error.message.includes('API key not valid'))
  );
}

/**
 * Phase-11.1 — operator-tunable routing policy. The chat handler
 * fetches it once per request from /api/v1/personality and passes it
 * to callGemini so the per-turn system prompt reflects the operator's
 * current configuration. Falls back to sensible defaults when the
 * personality store doesn't yet have the field (older blobs that
 * pre-date this commit).
 */
// ActionPolicy interface + renderActionPolicyBlock + the static system
// prompt text all live in lib/system-prompt.ts now (extracted in
// round-13 / Phase 1.3 to give the prompt a clean cache boundary and
// to drop ~700 lines of static narrative out of route.ts).
const DEFAULT_ACTION_POLICY: ActionPolicy = {
  localCategories: [
    'jobs',
    'settings',
    'personality',
    'instances',
    'providers',
    'approvals',
    'notifications',
    'skills',
    'api-keys',
    'memory',
    'knowledge',
  ],
  externalCategories: ['xsiam', 'xdr', 'web', 'cortex'],
  askWhenUnsure: true,
  confirmLocalActions: 'approve-card',
  confirmExternalActions: 'soft',
};

/**
 * v0.1.23: returns the two pieces of personality the system prompt
 * builder needs — actionPolicy (safety rails) + personalityMd
 * (operator-defined persona markdown). One MCP fetch, both consumers
 * use the result.
 */
interface PersonalityForPrompt {
  policy: ActionPolicy;
  personalityMd: string | null;
}

async function fetchPersonalityForPrompt(): Promise<PersonalityForPrompt> {
  try {
    const resp = await callMcpServer<{ personality?: Record<string, unknown> }>(
      '/api/v1/personality',
      { method: 'GET', timeoutMs: 4000 },
    );
    const blob = (resp?.personality ?? {}) as Record<string, unknown>;
    const raw = blob['actionPolicy'];
    let policy: ActionPolicy = DEFAULT_ACTION_POLICY;
    if (raw && typeof raw === 'object') {
      const p = raw as Partial<ActionPolicy>;
      policy = {
        localCategories: Array.isArray(p.localCategories) ? p.localCategories : DEFAULT_ACTION_POLICY.localCategories,
        externalCategories: Array.isArray(p.externalCategories) ? p.externalCategories : DEFAULT_ACTION_POLICY.externalCategories,
        askWhenUnsure: typeof p.askWhenUnsure === 'boolean' ? p.askWhenUnsure : DEFAULT_ACTION_POLICY.askWhenUnsure,
        confirmLocalActions: ['approve-card', 'soft', 'off'].includes(p.confirmLocalActions as string)
          ? (p.confirmLocalActions as ActionPolicy['confirmLocalActions'])
          : DEFAULT_ACTION_POLICY.confirmLocalActions,
        confirmExternalActions: ['approve-card', 'soft', 'off'].includes(p.confirmExternalActions as string)
          ? (p.confirmExternalActions as ActionPolicy['confirmExternalActions'])
          : DEFAULT_ACTION_POLICY.confirmExternalActions,
      };
    }
    const md = blob['personalityMd'];
    const personalityMd = typeof md === 'string' && md.trim() ? md : null;
    return { policy, personalityMd };
  } catch {
    return { policy: DEFAULT_ACTION_POLICY, personalityMd: null };
  }
}

/** Back-compat shim: callers that only need the policy can keep calling
 *  fetchActionPolicy() — internally goes through the same fetch.  */
async function fetchActionPolicy(): Promise<ActionPolicy> {
  return (await fetchPersonalityForPrompt()).policy;
}


/**
 * Resolve which model to actually call.
 *
 * Priority: per-request override (from chat header dropdown) →
 * runtime config (env / setup form) → hardcoded fallback.
 *
 * Until round-12 the per-request override was silently dropped at
 * request parsing — `body.model` was declared in the type but never
 * destructured. Operator: "I changed the model in the dropdown and
 * the response still felt like Gemini 3.1." Was correct: every
 * request used `runtimeConfig.GEMINI_MODEL || 'gemini-3.1-pro-preview'`
 * regardless of selection. This helper now does the resolution and is
 * the only place model-name selection happens.
 */
function resolveModelName(
  modelOverride: string | undefined,
  runtimeConfig: EffectiveRuntimeConfig,
): string {
  return modelOverride
    || runtimeConfig.defaultModel
    || runtimeConfig.GEMINI_MODEL
    || 'gemini-3.1-pro-preview';
}

/**
 * Minimal Gemini call for one-shot summarization (Phase 4.5
 * /compress). No tools, no system memory/KB instructions, no chat
 * history — just the summarization prompt + transcript. Returns the
 * model's text reply.
 *
 * Lives alongside callGemini() rather than being a parameterization of
 * it because the use case is genuinely different: callGemini sets up
 * the full agent persona, fetches MCP tools, etc; this one wants the
 * lightest possible call. Inlining via callGemini would inflate the
 * compaction request to ~15kb of system prompt for no benefit and
 * waste tokens that should be going to the summary.
 */
async function summarizeViaGemini(
  systemInstructionText: string,
  userContent: string,
  runtimeConfig: EffectiveRuntimeConfig,
  modelOverride?: string,
): Promise<string> {
  const payload: GeminiCallPayload = {
    contents: [{ role: 'user', parts: [{ text: userContent }] }],
    tools: [],
    systemInstruction: {
      role: 'system',
      parts: [{ text: systemInstructionText }],
    },
    // v0.2.3 — no maxOutputTokens cap on the partial-summary fallback
    // path either. Previously capped at 2048 (even smaller than the
    // main loop's 4096). The summary is supposed to recap a full
    // tool-budget-exhausted investigation; truncating it at 2K tokens
    // defeated its purpose.
  };
  const modelName = resolveModelName(modelOverride, runtimeConfig);
  let result: { candidates?: Array<{ content?: { parts?: GeminiPart[] } }> };
  if (runtimeConfig.GEMINI_API_KEY) {
    try {
      result = await callGeminiWithApiKey(payload, runtimeConfig, modelName);
    } catch (error) {
      if (
        runtimeConfig.GOOGLE_APPLICATION_CREDENTIALS &&
        isInvalidGeminiApiKeyError(error)
      ) {
        result = await callGeminiWithVertex(payload, runtimeConfig, modelName);
      } else {
        throw error;
      }
    }
  } else if (runtimeConfig.GOOGLE_APPLICATION_CREDENTIALS) {
    result = await callGeminiWithVertex(payload, runtimeConfig, modelName);
  } else {
    throw new Error(
      'No model provider is configured for the conversation summarizer. Add a Vertex AI or Gemini API provider at /providers.',
    );
  }
  const parts = result.candidates?.[0]?.content?.parts ?? [];
  return parts
    .map((p) => ('text' in p && p.text) || '')
    .join('')
    .trim();
}

async function callGemini(
  contents: GeminiContent[],
  tools: Array<{ functionDeclarations: unknown }>,
  runtimeConfig: EffectiveRuntimeConfig,
  actionPolicy: ActionPolicy,
  modelOverride?: string,
  // v0.1.23: operator-defined persona markdown. Threaded through so
  // the system prompt can include the operator's persona block. Null
  // / empty → no persona block (no-op). See system-prompt.ts.
  personalityMd?: string | null,
  // v0.1.33+: live skills registry, injected as <available_skills>
  // block in the system prompt. The model uses these to decide
  // which skill (if any) to apply for the user's request, then
  // calls skills_read to pull the full body. Empty / undefined →
  // no skills block in the prompt this turn.
  skillsForPrompt?: SkillSummary[] | null,
  // v0.3.27+: session approval mode. Selects the narration recipe in
  // the system prompt's approval-mode block so the agent's promises
  // about cards/gating match the MCP-side bypass header attached to
  // this turn's MCP calls. Default 'manual' = card-promising recipe.
  approvalMode: ApprovalMode = 'manual',
  // v0.5.32 — wire for v0.5.22's thinking_enabled. When true, sets
  // generationConfig.thinkingConfig.thinkingBudget = -1 so Gemini's
  // Pro variants use their extended-reasoning path (Flash variants
  // silently ignore). Defaults to false (no thinking config).
  thinking: boolean = false,
  // v0.17.117 — when true, set toolConfig.functionCallingConfig.mode='ANY'
  // so Gemini is forced to emit a structured functionCall (no text-only or
  // thought-only turn). Used by the leaked-tool-call recovery retry in the
  // chat parts loop (issue #114). Default false = normal AUTO behavior
  // (model freely decides text answer vs tool call).
  forceToolUse: boolean = false,
) {
  const systemInstruction: GeminiSystemInstruction = {
    role: 'system',
    parts: [
      {
        text: buildSystemPromptText(actionPolicy, personalityMd, skillsForPrompt, approvalMode),
      },
    ],
  };

  const payload: GeminiCallPayload = {
    contents,
    tools,
    systemInstruction,
    // v0.2.3 — no maxOutputTokens cap; Gemini uses model's natural max.
    ...(thinking
      ? {
          generationConfig: {
            thinkingConfig: {
              thinkingBudget: -1, // -1 = "use what you need" (Gemini API).
              includeThoughts: true,
            },
          },
        }
      : {}),
    // v0.17.117 — force a structured functionCall on the recovery retry.
    ...(forceToolUse
      ? { toolConfig: { functionCallingConfig: { mode: 'ANY' as const } } }
      : {}),
  };

  const modelName = resolveModelName(modelOverride, runtimeConfig);

  if (runtimeConfig.GEMINI_API_KEY) {
    try {
      return await callGeminiWithApiKey(payload, runtimeConfig, modelName);
    } catch (error) {
      if (runtimeConfig.GOOGLE_APPLICATION_CREDENTIALS && isInvalidGeminiApiKeyError(error)) {
        return callGeminiWithVertex(payload, runtimeConfig, modelName);
      }
      throw error;
    }
  }

  if (runtimeConfig.GOOGLE_APPLICATION_CREDENTIALS) {
    return callGeminiWithVertex(payload, runtimeConfig, modelName);
  }

  // v0.4.0 — operator-friendly message. Replaces the pre-v0.4.0 error
  // that surfaced internal env-var names. The Vertex setup page is
  // gone; operators configure providers at /providers post-login.
  throw new Error(
    'No model provider is configured. Add a Vertex AI or Gemini API provider at /providers, then try again.',
  );
}

/**
 * Round-15 / Phase P — system prompt for /plan mode.
 *
 * Instructs the model to enumerate the steps it would take WITHOUT
 * actually invoking any tools. The output goes into the chat thread
 * verbatim so the operator can review before approving.
 *
 * Format requirements:
 *
 *   - Numbered steps (1., 2., 3., ...).
 *   - Each step names the tool it would invoke and the args.
 *   - Each step has a one-line "why" explaining the operator's
 *     intent (not a tool-doc paste).
 *   - Risk callouts on destructive steps (XSIAM dataset/lookup
 *     writes against shared tenants, XSIAM PAPI writes).
 *
 * Patterned on SnowAgent's plan-mode instructions
 * (snow-agent-complete/snow-agent/06-tools-permissions/),
 * adapted for Guardian's SOC vocabulary.
 */
const PLAN_MODE_INSTRUCTIONS = `You are in PLAN MODE. The operator
asked you to enumerate the steps you would take WITHOUT actually
calling any tools. Output a numbered plan in plain markdown.

Each step MUST include:

  1. The tool name you'd invoke (use Guardian's actual tool names —
     xsiam.run_xql_query, xdr.get_cases_and_issues,
     xsiam.get_asset_by_id, xsiam.add_lookup_data, etc).
  2. The key arguments you'd pass (don't paste full schemas; just
     the operator-relevant fields like XQL query, dataset name,
     case id, lookup name).
  3. One sentence explaining WHY this step is part of the plan.
  4. A risk callout if the step is destructive (writes to a real
     SOC tool, creates or mutates a dataset, adds lookup rows on
     a real tenant). Use **Risk:** prefix.

Format:

\`\`\`
## Proposed plan

1. **xsoar.list_incidents** — query "status:active severity:High",
   last 24h, newest first
   *Why: surfaces the open high-severity cases that need triage so
   the investigation targets the right incident first.*

2. **xsoar.get_incident** — incident id from the top hit in step 1
   *Why: pulls the full case record (fields, labels, owner, linked
   indicators) so the investigation works from the real data.*

3. **xsoar.get_war_room** — investigation id == the incident id
   *Why: reads the existing analyst narrative and evidence so we
   build on prior work instead of duplicating it.*

4. **xsoar.search_indicators** — IOC values pulled from the case
   *Why: enriches the indicators with XSOAR's threat-intel verdicts
   and related-incident links before recommending a disposition.*

5. **xsoar.add_note** — incident id from step 2, the investigation
   summary as markdown
   *Why: documents the findings inline on the case record.*
   **Risk:** writes a war-room entry to a real case. Keep it factual
   and evidence-grounded — it becomes part of the case audit trail.

... (etc)

## Notes

- Estimated duration: ~15m
- Tools that might require approval: 1 (xsiam.add_lookup_data — writes lookup rows)
- Recommended: review step 4's lookup name before approving — the
  rows land in a shared tenant lookup.
\`\`\`

Do NOT call any tools. Do NOT emit text outside the structured plan.
Do NOT include code blocks for the plan content itself (just the
Format example shows a code block; YOUR output is the markdown
inside the example, not wrapped).`;

/**
 * Round-14 / Phase F — slash command registry.
 *
 * Each entry's handler receives a SlashCommandContext with everything
 * the chat handler exposes (sessionId, trigger, sendEvent, controller,
 * runtimeConfig, requestedModel/Provider). Handlers MUST close the
 * controller before returning — the framework doesn't auto-close so
 * a handler that wants to leave the stream open can do so.
 *
 * Adding a new command: append a SlashCommand here. Both the dispatch
 * (parseSlashCommand → dispatchSlashCommand inside POST) and the help
 * listing (`/help` reading SLASH_COMMANDS via renderSlashHelp) pick it
 * up automatically.
 */
const SLASH_COMMANDS: readonly SlashCommand[] = [
  // ── /compress ──────────────────────────────────────────────────
  // Round-13 / Phase 4.5. Operator-triggered compaction. Body is
  // the same logic that previously lived as an inline if-branch in
  // POST; only the surrounding closure changes (now reads its
  // dependencies from `ctx` instead of POST-handler locals).
  {
    name: 'compress',
    description: 'Summarize prior turns into a checkpoint to free up context budget.',
    handler: async (ctx) => {
      const { sessionId, trigger, runtimeConfig, requestedModel, sendEvent, controller } = ctx;
      // Round-15 / Phase H — PreCompact hook fire-site. A hook may
      // veto compaction (e.g. "audit policy: don't compact this
      // session, the full transcript is needed").
      const preCompact = await fireHookEvent(
        'PreCompact',
        {
          event: 'PreCompact',
          sessionId,
          kind: 'manual',
          messageCount: 0,
          trigger,
        },
        trigger,
      );
      if (preCompact.decision === 'deny') {
        sendEvent('text_delta', {
          text:
            preCompact.reason ??
            'Compaction blocked by a PreCompact hook.',
        });
        sendEvent('done', { session_id: sessionId });
        controller.close();
        return;
      }
      sendEvent('compaction_start', { session_id: sessionId });
      // Round-14 / Phase D.1 — persist a chat_compaction_start audit
      // row so /observability/events captures the lifecycle even if
      // the SSE stream gets disconnected before compaction_end fires.
      await safeAudit('chat_compaction_start', {
        target: `session:${sessionId}`,
        metadata: { kind: 'manual', trigger: 'slash:/compress' },
        trigger,
      });
      const compactStartedAt = Date.now();
      try {
        // Fetch full prior history (up to 1000 messages — far more
        // than the 300-msg replay cap, since we WANT to compact the
        // long-tail). This is the only path that asks for >300.
        let priorMessages: CompactionInputMessage[] = [];
        try {
          const data = await callMcpServer<{
            messages?: CompactionInputMessage[];
          }>(
            `/api/v1/sessions/${encodeURIComponent(sessionId)}/messages?limit=1000&ascending=true`,
            {
              method: 'GET',
              headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
            },
          );
          priorMessages = Array.isArray(data?.messages) ? data.messages : [];
        } catch (err) {
          console.warn(
            `chat: /compress fetch history failed for ${sessionId}:`,
            err instanceof Error ? err.message : err,
          );
        }

        // Drop the just-persisted '/compress' user message itself
        // and any earlier checkpoint messages from the input —
        // they shouldn't be summarized (the checkpoint IS the
        // prior summary, and /compress isn't conversation).
        const summarizable = priorMessages.filter((m) => {
          if (m.role === 'user' && m.content.trim() === '/compress') return false;
          if (isCompactionCheckpoint(m)) return false;
          return true;
        });

        if (summarizable.length === 0) {
          sendEvent('text_delta', {
            text: 'Nothing to compact yet — the session has no prior turns.',
          });
          sendEvent('compaction_end', {
            session_id: sessionId,
            messages_summarized: 0,
            skipped: true,
          });
          // Phase D.1 — record the no-op as well so the operator can
          // see /compress invocations even when they didn't compact
          // anything. The skipped flag lets observability filters
          // distinguish "operator pressed it but nothing happened"
          // from "real compactions".
          await safeAudit('chat_compaction_end', {
            target: `session:${sessionId}`,
            status: 'success',
            durationMs: Date.now() - compactStartedAt,
            metadata: { skipped: true, messages_summarized: 0, kind: 'manual' },
            trigger,
          });
          sendEvent('done', {
            session_id: sessionId,
            status_reason: 'compaction_completed' satisfies RunStatusReason,
            skipped: true,
          });
          controller.close();
          return;
        }

        const result = await compactMessages(summarizable, (instructions, transcript) =>
          summarizeViaGemini(instructions, transcript, runtimeConfig, requestedModel),
        );

        if (!result) throw new Error('summarizer returned empty');

        // Persist the checkpoint as a system-role message with
        // meta.kind=compaction-checkpoint. loadSessionHistory's
        // checkpoint-aware slicing kicks in on the next turn.
        await safePersist(
          sessionId,
          {
            role: 'system',
            content: result.summary,
            meta: {
              kind: COMPACTION_CHECKPOINT_KIND,
              covers_until: result.coversUntil,
              messages_summarized: result.messagesSummarized,
            },
          },
          trigger,
        );

        sendEvent('text_delta', {
          text:
            `**Compacted ${result.messagesSummarized} prior message(s).** ` +
            `Future turns in this session will start from this summary:\n\n` +
            result.summary +
            `\n\n*The full transcript is preserved in the session ` +
            `record and remains exportable; only the in-memory replay ` +
            `is shortened.*`,
        });
        sendEvent('compaction_end', {
          session_id: sessionId,
          messages_summarized: result.messagesSummarized,
          summary_chars: result.summary.length,
          covers_until: result.coversUntil,
        });
        // Phase D.1 — durable audit row for the successful compaction.
        // metadata.summary_chars + messages_summarized give the
        // observability page enough to compute "tokens saved" without
        // re-fetching the checkpoint message.
        await safeAudit('chat_compaction_end', {
          target: `session:${sessionId}`,
          status: 'success',
          durationMs: Date.now() - compactStartedAt,
          metadata: {
            kind: 'manual',
            messages_summarized: result.messagesSummarized,
            summary_chars: result.summary.length,
            covers_until: result.coversUntil,
          },
          trigger,
        });
        // Round-15 / Phase H — PostCompact hook fire-site.
        // Non-decisional (the compaction already landed). Hooks
        // typically forward summary text to an external archive or
        // emit notifications.
        void fireHookEvent(
          'PostCompact',
          {
            event: 'PostCompact',
            sessionId,
            kind: 'manual',
            messagesSummarized: result.messagesSummarized,
            summaryChars: result.summary.length,
            durationMs: Date.now() - compactStartedAt,
            trigger,
          },
          trigger,
        );
        sendEvent('done', {
          session_id: sessionId,
          status_reason: 'compaction_completed' satisfies RunStatusReason,
          messages_summarized: result.messagesSummarized,
        });
      } catch (err) {
        console.error(
          `chat: /compress failed for ${sessionId}:`,
          err instanceof Error ? err.message : err,
        );
        sendEvent('error', {
          error: `Compaction failed: ${err instanceof Error ? err.message : String(err)}`,
          code: 'COMPACTION_FAILED',
        });
        // Phase D.1 — failure rows so the operator can see
        // compaction_failed cases when looking at observability.
        await safeAudit('chat_compaction_failed', {
          target: `session:${sessionId}`,
          status: 'failure',
          durationMs: Date.now() - compactStartedAt,
          metadata: {
            kind: 'manual',
            error: err instanceof Error ? err.message : String(err),
          },
          trigger,
        });
      }
      controller.close();
    },
  },

  // ── /clear ─────────────────────────────────────────────────────
  // End the current session (preserves transcript + audit history)
  // and create a fresh one. Emits `session_cleared` with the new
  // session_id so the chat UI can swap its active session pointer
  // without a full reload. On a brand-new session (operator just
  // opened the chat), it's a no-op — there's nothing to clear.
  {
    name: 'clear',
    description: 'End this session and start a fresh one. Transcript stays exportable.',
    handler: async (ctx) => {
      const { sessionId, isNewSession, trigger, sendEvent, controller } = ctx;
      if (isNewSession) {
        sendEvent('text_delta', {
          text: 'This session is brand-new — nothing to clear yet.',
        });
        sendEvent('done', { session_id: sessionId });
        controller.close();
        return;
      }

      // End the current session. Failure is non-fatal: even if the
      // end call doesn't land, the new session will still be created
      // and the operator gets the desired effect (fresh context).
      try {
        await callMcpServer(
          `/api/v1/sessions/${encodeURIComponent(sessionId)}/end`,
          {
            method: 'POST',
            body: {},
            headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
          },
        );
      } catch (err) {
        console.warn(
          `chat: /clear: end-session failed for ${sessionId}:`,
          err instanceof Error ? err.message : err,
        );
      }

      // Create a fresh session. If MCP is unreachable we synthesize
      // a local id so the UI still gets a clean slate; subsequent
      // turns will lazy-create properly when MCP recovers.
      let newSessionId: string;
      try {
        const created = await callMcpServer<{ session?: { id?: string } }>(
          '/api/v1/sessions',
          {
            method: 'POST',
            body: { user: 'operator', title: null, meta: {} },
            headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
          },
        );
        newSessionId = created?.session?.id ?? `s_${crypto.randomUUID()}`;
      } catch (err) {
        console.warn(
          'chat: /clear: failed to create replacement session:',
          err instanceof Error ? err.message : err,
        );
        newSessionId = `s_${crypto.randomUUID()}`;
      }

      sendEvent('session_cleared', {
        previous_session_id: sessionId,
        session_id: newSessionId,
      });
      sendEvent('text_delta', {
        text: `Started a fresh session. The previous transcript is still in the sidebar and exportable.`,
      });
      sendEvent('done', { session_id: newSessionId });
      controller.close();
    },
  },

  // ── /help ──────────────────────────────────────────────────────
  // List the available commands. Built from the SLASH_COMMANDS
  // table itself so it stays in sync without a separate doc.
  {
    name: 'help',
    description: 'Show this list of slash commands.',
    handler: async (ctx) => {
      const { sessionId, sendEvent, controller } = ctx;
      sendEvent('text_delta', { text: renderSlashHelp(SLASH_COMMANDS) });
      sendEvent('done', { session_id: sessionId });
      controller.close();
    },
  },

  // ── /cost ──────────────────────────────────────────────────────
  // Round-15 / Phase $ — show token + USD cost rollups. Aggregates
  // chat_turn_cost audit rows for THIS session and today's
  // overall total. The /observability/cost page has the full
  // multi-dimensional view; this is the in-chat quick check.
  {
    name: 'cost',
    description:
      'Show token + USD cost for this session and today.',
    handler: async (ctx) => {
      const { sessionId, trigger, sendEvent, controller } = ctx;
      try {
        // Pull two windows: this session, and today (since
        // midnight UTC).
        const sessionRowsP = callMcpServer<{
          events?: Array<{ metadata?: Record<string, unknown> }>;
        }>(
          `/api/v1/audit?action=chat_turn_cost&target=session:${encodeURIComponent(sessionId)}&limit=1000`,
          {
            method: 'GET',
            headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
          },
        );
        const todayMidnight = new Date();
        todayMidnight.setUTCHours(0, 0, 0, 0);
        const todayIso = todayMidnight.toISOString();
        const todayRowsP = callMcpServer<{
          events?: Array<{ metadata?: Record<string, unknown> }>;
        }>(
          `/api/v1/audit?action=chat_turn_cost&since=${encodeURIComponent(todayIso)}&limit=1000`,
          {
            method: 'GET',
            headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
          },
        );
        const [sessionData, todayData] = await Promise.all([
          sessionRowsP,
          todayRowsP,
        ]);
        const sessionTotals = sumCostRows(sessionData?.events ?? []);
        const todayTotals = sumCostRows(todayData?.events ?? []);
        const lines: string[] = [
          '**Cost summary**',
          '',
          `**This session** (${sessionTotals.calls} call${sessionTotals.calls === 1 ? '' : 's'}):`,
          `  • Input tokens: ${sessionTotals.input.toLocaleString()} (${sessionTotals.cached.toLocaleString()} cached)`,
          `  • Output tokens: ${sessionTotals.output.toLocaleString()}`,
          `  • Total: **${formatUsd(sessionTotals.usd)}**${sessionTotals.savings > 0 ? ` (saved ${formatUsd(sessionTotals.savings)} via Vertex caching)` : ''}`,
          '',
          `**Today (UTC)** (${todayTotals.calls} call${todayTotals.calls === 1 ? '' : 's'} across all sessions):`,
          `  • Input tokens: ${todayTotals.input.toLocaleString()} (${todayTotals.cached.toLocaleString()} cached)`,
          `  • Output tokens: ${todayTotals.output.toLocaleString()}`,
          `  • Total: **${formatUsd(todayTotals.usd)}**${todayTotals.savings > 0 ? ` (saved ${formatUsd(todayTotals.savings)} via Vertex caching)` : ''}`,
        ];
        if (Object.keys(todayTotals.byModel).length > 1) {
          lines.push('', '**Today by model:**');
          for (const [model, m] of Object.entries(todayTotals.byModel).sort(
            (a, b) => b[1].usd - a[1].usd,
          )) {
            lines.push(`  • \`${model}\`: ${formatUsd(m.usd)} (${m.calls} call${m.calls === 1 ? '' : 's'})`);
          }
        }
        lines.push(
          '',
          '_Pricing source: Vertex AI public pricing as of 2026-05. Per-call audit rows in [/observability/events](/observability/events) (filter `action:chat_turn_cost`). Full rollups in [/observability/cost](/observability/cost)._',
        );
        sendEvent('text_delta', { text: lines.join('\n') });
        sendEvent('done', { session_id: sessionId });
      } catch (err) {
        sendEvent('error', {
          error: `Cost lookup failed: ${err instanceof Error ? err.message : String(err)}`,
          code: 'COST_LOOKUP_FAILED',
        });
      }
      controller.close();
    },
  },

  // ── /tasks ─────────────────────────────────────────────────────
  // Round-15 / Phase T — list active and recent tasks for THIS
  // session. Operator can also visit /tasks for the full registry.
  // No args today; future args could filter by kind ("/tasks
  // hunt" → only hunt tasks).
  {
    name: 'tasks',
    description: 'Show active background tasks (long-running XQL hunts, evidence-collection jobs, etc).',
    handler: async (ctx) => {
      const { sessionId, trigger, sendEvent, controller } = ctx;
      try {
        const data = await callMcpServer<{ tasks?: Array<{
          id: string;
          kind: string;
          status: string;
          title: string;
          progress: number;
          progress_label: string | null;
          parent_session_id: string | null;
          created_at: string;
        }> }>(
          `/api/v1/tasks?active_only=1&limit=50`,
          {
            method: 'GET',
            headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
          },
        );
        const tasks = data.tasks ?? [];
        if (tasks.length === 0) {
          sendEvent('text_delta', {
            text:
              'No active background tasks.\n\n' +
              '_Tasks appear here when long-running work is spawned ' +
              "(long-running XQL hunts, evidence-collection jobs, etc). See [/tasks](/tasks) for the full registry including completed and failed tasks._",
          });
        } else {
          // Render a table-style summary the operator can act on.
          // Tasks tied to THIS session bubble to the top.
          tasks.sort((a, b) => {
            const aMine = a.parent_session_id === sessionId ? 0 : 1;
            const bMine = b.parent_session_id === sessionId ? 0 : 1;
            return aMine - bMine || a.created_at.localeCompare(b.created_at);
          });
          const lines = tasks.map((t) => {
            const pct = Math.round(t.progress * 100);
            const own = t.parent_session_id === sessionId ? '★ ' : '  ';
            const label = t.progress_label
              ? ` — ${t.progress_label}`
              : '';
            return `${own}\`${t.kind}\` **${t.title}** — ${t.status} (${pct}%)${label}`;
          });
          sendEvent('text_delta', {
            text:
              `**${tasks.length} active task${tasks.length === 1 ? '' : 's'}** ` +
              `(★ = spawned by this session)\n\n` +
              lines.join('\n') +
              `\n\nVisit [/tasks](/tasks) to see completed tasks or abort running ones.`,
          });
        }
        sendEvent('done', { session_id: sessionId });
      } catch (err) {
        sendEvent('error', {
          error: `Failed to fetch tasks: ${err instanceof Error ? err.message : String(err)}`,
          code: 'TASKS_LIST_FAILED',
        });
      }
      controller.close();
    },
  },

  // ── /plan <prompt> ─────────────────────────────────────────────
  // Round-15 / Phase P — plan mode. The operator types
  // "/plan investigate the auth-spray alerts on host X"; the agent
  // composes a step-by-step plan WITHOUT executing any tools.
  // The operator then sees the plan, can approve it (executes the
  // run), revise it, or cancel.
  //
  // Why: today's per-tool inline approval cards (Round-12 Phase 11)
  // work great for ONE tool, but an investigation that fires 12 tools
  // across XSIAM + XDR + web is 12 prompt cards. Plan mode
  // collapses that to ONE: agent presents the plan, operator
  // approves once, all 12 tools execute without further prompts.
  //
  // Implementation: this handler emits a `plan_proposed` SSE event
  // with the model's plan text. The chat UI renders an inline
  // PlanCard that the operator can approve. Approval re-sends the
  // ORIGINAL prompt with a session-flag that signals "skip
  // per-tool approvals — the plan was approved." See
  // `lib/system-prompt.ts` for the planning instructions appended
  // to the system prompt.
  {
    name: 'plan',
    argHint: '<prompt>',
    description:
      'Plan a multi-step workflow without executing tools. Approve once to run the whole plan.',
    handler: async (ctx) => {
      const {
        args,
        sessionId,
        trigger,
        runtimeConfig,
        requestedModel,
        sendEvent,
        controller,
      } = ctx;
      const prompt = args.trim();
      if (!prompt) {
        sendEvent('text_delta', {
          text:
            'Usage: `/plan <prompt>` — e.g. `/plan investigate the auth-spray alerts on host X and verify with XQL`. ' +
            'The agent will propose the steps it would take; you can approve to run.',
        });
        sendEvent('done', { session_id: sessionId });
        controller.close();
        return;
      }
      sendEvent('plan_started', { session_id: sessionId, prompt });
      try {
        // The planning system prompt instructs the model to enumerate
        // its anticipated tool calls in a structured form. We use a
        // separate summarizer-style call (no tools wired) so the
        // model can't accidentally execute anything mid-plan.
        const planText = await summarizeViaGemini(
          PLAN_MODE_INSTRUCTIONS,
          prompt,
          runtimeConfig,
          requestedModel,
        );
        if (!planText) {
          throw new Error('plan generation returned empty');
        }
        // Persist the plan as a system message so it shows in the
        // chat thread + transcript. Tagged `kind: 'plan-proposed'`
        // for future filtering.
        await safePersist(
          sessionId,
          {
            role: 'system',
            content: planText,
            meta: {
              kind: 'plan-proposed',
              source_prompt: prompt,
              proposed_at: new Date().toISOString(),
            },
          },
          trigger,
        );
        sendEvent('plan_proposed', {
          session_id: sessionId,
          plan_text: planText,
          source_prompt: prompt,
        });
        sendEvent('text_delta', { text: planText });
        sendEvent('text_delta', {
          text:
            '\n\n---\n\n' +
            '**To execute this plan**: send the original prompt without `/plan` ' +
            '(e.g. `' +
            (prompt.length > 60 ? prompt.slice(0, 60) + '…' : prompt) +
            '`). ' +
            "I'll run the steps; tier-2+ tools may still surface individual approval cards.\n\n" +
            '**To revise**: tell me what to change ("plan again but skip step 3").\n\n' +
            '**To cancel**: just send a different prompt; the plan goes away.',
        });
        // Audit: durable record of the plan for /observability
        // queries. Stored separately from the persisted system
        // message so operators don't need to reconstruct from
        // transcripts.
        await safeAudit('chat_plan_proposed', {
          target: `session:${sessionId}`,
          status: 'success',
          metadata: {
            source_prompt: prompt,
            plan_chars: planText.length,
            model:
              requestedModel || runtimeConfig.GEMINI_MODEL,
          },
          trigger,
        });
        sendEvent('done', { session_id: sessionId });
      } catch (err) {
        console.error(
          `chat: /plan failed for ${sessionId}:`,
          err instanceof Error ? err.message : err,
        );
        sendEvent('error', {
          error: `Plan generation failed: ${err instanceof Error ? err.message : String(err)}`,
          code: 'PLAN_FAILED',
        });
        await safeAudit('chat_plan_failed', {
          target: `session:${sessionId}`,
          status: 'failure',
          metadata: {
            source_prompt: prompt,
            error: err instanceof Error ? err.message : String(err),
          },
          trigger,
        });
      }
      controller.close();
    },
  },

  // ── /model <name> ──────────────────────────────────────────────
  // Persist a per-session preferred model. Persists into
  // session.metadata.preferred_model via PATCH; the chat handler
  // reads it on subsequent turns via loadSessionPreferredModel.
  //   /model            → show the current preference (or runtime default)
  //   /model auto       → clear the preference
  //   /model <name>     → set to <name> (e.g., gemini-2.5-pro)
  {
    name: 'model',
    argHint: '<name>',
    description: 'Override the model for this session. `/model auto` clears.',
    handler: async (ctx) => {
      const { args, sessionId, trigger, runtimeConfig, sendEvent, controller } = ctx;
      const arg = args.trim();

      // No-arg: report the current preference.
      if (arg === '') {
        const current = await loadSessionPreferredModel(sessionId, trigger);
        sendEvent('text_delta', {
          text: current
            ? `Current model preference: \`${current}\` (session override)`
            : `No session override. Using runtime default: \`${runtimeConfig.GEMINI_MODEL}\``,
        });
        sendEvent('done', { session_id: sessionId });
        controller.close();
        return;
      }

      // `/model auto` or `/model default` clears the override.
      const clearing = arg.toLowerCase() === 'auto' || arg.toLowerCase() === 'default';
      const newValue = clearing ? null : arg;

      try {
        await callMcpServer(
          `/api/v1/sessions/${encodeURIComponent(sessionId)}`,
          {
            method: 'PATCH',
            body: { metadata: { preferred_model: newValue } },
            headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
          },
        );
        invalidateSessionPreferredModelCache(sessionId);
        sendEvent('model_preference_changed', {
          session_id: sessionId,
          preferred_model: newValue,
        });
        sendEvent('text_delta', {
          text: clearing
            ? `Cleared model override. Future turns will use the runtime default (\`${runtimeConfig.GEMINI_MODEL}\`).`
            : `Set model preference to \`${arg}\` for this session. Takes effect on the next turn.`,
        });
        sendEvent('done', { session_id: sessionId });
      } catch (err) {
        console.error(
          `chat: /model failed for ${sessionId}:`,
          err instanceof Error ? err.message : err,
        );
        sendEvent('error', {
          error: `Failed to update model preference: ${err instanceof Error ? err.message : String(err)}`,
          code: 'MODEL_PREFERENCE_FAILED',
        });
      }
      controller.close();
    },
  },
];

// v0.17.130 (#127) — turn-scoped tool-result memoization.
//
// The soft system-prompt nudge shipped in v0.17.129 (#126) asked the model to
// "call marketplace_list at most once per turn." It didn't hold: live smoke
// still showed the model re-listing the catalog (and re-running knowledge_search)
// 3-4x within a single user turn. A prose nudge can't *guarantee* the model
// obeys, so this is the mechanical backstop — a per-turn cache that returns the
// already-fetched result for an identical (tool, args) call instead of
// re-dispatching to the MCP.
//
// Scope: ONE user message (the cache is declared inside the POST handler, NOT
// module-level — it must never leak a catalog snapshot across turns or users).
//
// Semantics: REPEATABLE-READ within a turn. The allowlist below is static
// platform metadata whose value cannot change mid-turn *except* via an explicit
// catalog/config mutation — and `invalidatesTurnCache()` clears the snapshot the
// moment such a mutation runs, so a same-turn install→re-list still sees fresh
// data. Different args ⇒ different key ⇒ both calls dispatch (e.g. schema for
// source A then source B), so no capability is lost — only verbatim repeats are
// short-circuited.
const TURN_CACHEABLE_TOOLS = new Set<string>([
  'marketplace_list',
  'settings_get',
  'skills_read',
  'knowledge_search',
]);

// Catalog / config / credential mutations change what the cacheable reads
// return, so they invalidate the whole turn snapshot. Kept as a name-prefix
// predicate rather than an exhaustive list: a false positive only costs a cache
// clear (still correct), while the explicit prefixes cover every agent-reachable
// mutation that touches the static-read surface above.
function invalidatesTurnCache(toolName: string): boolean {
  return /^(marketplace_(install|uninstall)|connector_upload|settings_set|providers_(create|update|delete)|instances_(create|update|delete)|api_keys_)/.test(
    toolName,
  );
}

// Deterministic JSON for cache keys: object keys sorted so {a,b} and {b,a} hash
// identically; arrays keep order; primitives pass through. Avoids treating two
// semantically-identical arg objects as distinct calls.
function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value) ?? 'null';
  }
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(',')}]`;
  }
  const obj = value as Record<string, unknown>;
  return `{${Object.keys(obj)
    .sort()
    .map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`)
    .join(',')}}`;
}

// v0.17.131 (#129) — detect the {ok:false} failure envelope Guardian MCP tools
// return on a SOFT failure (not an exception). marketplace_install and many
// others report "not found" / "already exists" / "extraction failed" this way,
// so a model that retries the identical failing call loops invisibly past the
// toolError path (observed: marketplace_install ×7 on a not-found pack). Only
// the explicit "ok": false envelope counts — never a tool whose output merely
// contains the word "error" — to avoid false-positive loop-breaking.
function resultFailureText(result: unknown): string | null {
  try {
    const content = (result as { content?: Array<{ text?: unknown }> })?.content;
    if (!Array.isArray(content)) return null;
    for (const part of content) {
      const text = typeof part?.text === 'string' ? part.text : '';
      if (!text || !/"ok"\s*:\s*false/.test(text)) continue;
      const m = text.match(/"error"\s*:\s*"((?:[^"\\]|\\.)*)"/);
      return (m ? m[1] : text).slice(0, 280);
    }
  } catch {
    /* non-JSON / unexpected shape — treat as non-failure */
  }
  return null;
}

// Poll/wait tools legitimately re-issue the SAME (tool, args) call many times
// (e.g. guardian_web_wait_for) and may transiently report a
// not-yet-ready state — they must never be short-circuited by the failed-call
// loop-breaker below.
function isPollTool(toolName: string): boolean {
  return /_wait|wait_for|_poll/i.test(toolName);
}

export async function POST(request: NextRequest) {
  const encoder = new TextEncoder();

  // Trigger attribution — set by upstream callers (today: the
  // job_scheduler when it fires a chat-action job; future: per-
  // operator session attribution). Forwarded to every downstream
  // MCP call so audit rows tag with the same trigger.
  //
  // v0.1.24: this also drives the approvals bus's `origin` column
  // (so chat-origin approvals can resolve via inline card; job
  // and other origins land in /approvals). For interactive chat
  // turns, we default to "chat:<sessionId>" right after sessionId
  // is resolved below — that way the operator typing in the UI
  // also gets a stable origin in audit + approvals tables.
  let trigger = request.headers.get('x-guardian-trigger') || undefined;
  // #CHAT-F2 — the principal the middleware attributed (apikey:<id> |
  // user:operator). Threaded into chat-path audit so turns attribute to the
  // real caller, not the MCP's hardcoded user:operator default.
  const actor = request.headers.get('x-guardian-actor') || undefined;

  const stream = new ReadableStream({
    async start(controller) {
      // SSE wire format aligned with Spark's parseSSEEvent (lib/api/chat.ts):
      // each frame is a named event with a JSON-encoded `data:` line.
      // Spark's parser returns null if the `event:` line is absent, so the
      // earlier "data: {type, ...}" shape guardian shipped pre-#5 was being
      // silently dropped by the new chat UI — that's the chat-no-response
      // bug. Send named events here; the hook reads `event.type` to switch.
      let eventCounter = 0;
      const sendEvent = (type: string, dataObj: unknown) => {
        eventCounter += 1;
        const dataLine = `data: ${typeof dataObj === 'string' ? dataObj : JSON.stringify(dataObj)}`;
        controller.enqueue(
          encoder.encode(`id: ${eventCounter}\nevent: ${type}\n${dataLine}\n\n`),
        );
      };

      try {
        const {
          message,
          session_id: incomingSessionId,
          model: requestedModel,
          provider: requestedProvider,
          permission_policy: requestedPolicy,
          thinking: requestedThinking,
        } = (await request.json()) as {
          message?: string;
          session_id?: string;
          model?: string;
          provider?: string;
          // v0.5.23 / Issue #23 — per-request permission policy. The
          // scheduler attaches this on job-driven dispatches; chat
          // header has no UI for it today (operators set it on the
          // job; chat turns are unrestricted by default).
          permission_policy?: unknown;
          // v0.5.32 — wire for v0.5.22's thinking_enabled. The
          // scheduler attaches this when the job's thinking_enabled
          // is true; chat-route now threads it into callGemini's
          // generationConfig.thinkingConfig.
          thinking?: unknown;
        };
        // Normalize the policy through the validator. Bad shapes
        // degrade to `null` (no policy) rather than throw — the
        // validator's lenient mode matches the rest of the route's
        // best-effort discipline.
        const turnPolicy = validatePermissionPolicy(requestedPolicy);
        // v0.6.67 — chat turns DEFAULT to thinking enabled. Operator
        // observation at v0.6.66 release time: "I feel the agent
        // response pretty fast, I wanted to make sure we actually
        // using gemini 3.1 and highest reasoning level". Pre-v0.6.67
        // this was `requestedThinking === true` — only enabled when
        // the scheduler explicitly passed `thinking: true` for jobs.
        // Chat-UI requests don't pass the field, so chat turns ran
        // WITHOUT thinkingConfig — Gemini 3.1 Pro's extended-reasoning
        // path was never engaged.
        //
        // v0.6.67 flips the default: chat turns get thinking ON unless
        // the caller EXPLICITLY passes `thinking: false`. Scheduler
        // calls that pass `thinking: false` still disable it (cost-
        // controlled job runs); calls that pass `thinking: true` still
        // enable it. The semantic for "unset" changes from OFF → ON.
        //
        // Effect: callGemini sets generationConfig.thinkingConfig.
        // thinkingBudget = -1 ("use what you need") + includeThoughts
        // = true. On Pro variants this engages the extended-reasoning
        // path with auto budget; on Flash variants it's silently
        // ignored. Cost impact bounded by Vertex's context cache —
        // the operator's session c9c97258 showed ~28k cached input
        // tokens per turn, so the marginal cost of thinking is the
        // output-side reasoning tokens (~$0.02-0.05 per turn).
        const turnThinking = requestedThinking !== false;

        if (!message) {
          sendEvent('error', { error: 'Message is required' });
          controller.close();
          return;
        }

        // Resolve the session id: if the client supplied one, reuse it
        // (subsequent turns of an existing chat). Otherwise lazy-create
        // a session in the MCP store so the chat shows up in the
        // sidebar / sessions list and is exportable.
        //
        // The session-store call is best-effort: if MCP is unreachable
        // we still synthesize a local id so the stream completes and
        // the user sees a response — they just won't get persistence
        // for that turn (and a warning is logged server-side).
        let sessionId: string;
        let isNewSession = false;
        // v0.2.40 — tag job-driven sessions as scheduled AT CREATE TIME.
        // Previously `meta.scheduled_by` was only stamped by the
        // auto-title PATCH at turn END (see ~the isNewSession block
        // below), so a turn that timed out / errored mid-flight never
        // got tagged — leaving ~200 untagged orphan loop sessions that
        // the sidebar's exclude_scheduled filter couldn't hide. Stamping
        // it on the create call closes that gap: the tag lands before
        // any turn work, independent of how the turn ends.
        const jobTriggerMatch = trigger?.match(/^job:(.+)$/);
        const scheduledByAtCreate = jobTriggerMatch ? jobTriggerMatch[1] : null;
        if (incomingSessionId) {
          sessionId = incomingSessionId;
        } else {
          try {
            const created = await callMcpServer<{
              session?: { id?: string };
            }>('/api/v1/sessions', {
              method: 'POST',
              body: {
                user: 'operator',
                title: null,
                meta: scheduledByAtCreate
                  ? { scheduled_by: scheduledByAtCreate }
                  : {},
              },
              headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
            });
            const id = created?.session?.id;
            if (id) {
              sessionId = id;
              isNewSession = true;
            } else {
              sessionId = `s_${crypto.randomUUID()}`;
            }
          } catch (err) {
            console.warn(
              'chat: failed to create session in MCP store, using local id:',
              err instanceof Error ? err.message : err,
            );
            sessionId = `s_${crypto.randomUUID()}`;
          }
        }

        // v0.1.24: default trigger to chat:<sessionId> for interactive
        // chats. Job-triggered chats already have trigger set by the
        // upstream scheduler ("job:<name>"); we only fill in the chat
        // origin if no upstream trigger was provided.
        if (!trigger) {
          trigger = `chat:${sessionId}`;
        }

        // #CHAT-F1 — audit the turn START. Previously the first audit row
        // for a turn was chat_turn_cost (emitted at the END), so a turn
        // that errored before the first Gemini call (auth/setup/hook deny,
        // provider unreachable) left NO trace in /observability/events.
        // Fire-and-forget; the turn proceeds regardless.
        void safeAudit('chat_turn_started', {
          target: `session:${sessionId}`,
          status: 'success',
          metadata: {
            session_id: sessionId,
            new_session: isNewSession,
            model: requestedModel ?? 'default',
            provider: requestedProvider ?? 'default',
          },
          trigger,
          actor,
        });

        const turnStartedAt = Date.now();
        sendEvent('meta', {
          run_id: `r_${crypto.randomUUID()}`,
          session_id: sessionId,
          agent_id: 'guardian-soc-ir',
        });

        // Round-15 / Phase H — RunStart hook fire-site. Hooks can
        // abort the entire turn (`decision: 'deny'`) before the
        // user message is persisted, keeping the audit trail clean.
        // Common use: "block all chat in tenant-X during a freeze
        // window."
        const runStartHook = await fireHookEvent(
          'RunStart',
          { event: 'RunStart', sessionId, trigger },
          trigger,
        );
        if (runStartHook.decision === 'deny') {
          sendEvent('error', {
            error:
              runStartHook.reason ??
              'Chat turn blocked by a RunStart hook.',
            code: 'HOOK_DENIED_RUN_START',
          });
          controller.close();
          return;
        }

        // Round-15 / Phase H — UserPromptSubmit hook fire-site. Hooks
        // can inject context (e.g. "the active incident is INC-1234"),
        // replace the message (rare; mostly redaction), or deny.
        // Fires BEFORE persistence so a denied prompt isn't
        // permanently archived.
        const userPromptHook = await fireHookEvent(
          'UserPromptSubmit',
          { event: 'UserPromptSubmit', sessionId, message, trigger },
          trigger,
        );
        if (userPromptHook.decision === 'deny') {
          sendEvent('error', {
            error:
              userPromptHook.reason ??
              'Prompt blocked by a UserPromptSubmit hook.',
            code: 'HOOK_DENIED_PROMPT',
          });
          controller.close();
          return;
        }
        // If a hook returned `replace`, swap it in. Useful for
        // redaction: "scrub UUIDs before sending to the model."
        const effectiveMessage =
          typeof userPromptHook.replace === 'string'
            ? userPromptHook.replace
            : message;

        // Persist the user's inbound message before we start the model
        // loop. Doing it here (vs after the turn) means a partial /
        // crashed turn still leaves a record of what was asked.
        // We persist the EFFECTIVE message (post-hook-replace) so
        // the transcript matches what the model sees.
        await safePersist(sessionId, { role: 'user', content: effectiveMessage }, trigger);

        // Stash hook-injected context for the model loop to append
        // to the system instruction on this turn. Empty string when
        // no hooks contributed.
        const hookInjectedContext = userPromptHook.injectContext ?? '';

        // ── Round-14 / Phase F — slash command dispatch ────────────
        //
        // Replaces the round-13 inline `/compress` if-block with a
        // framework-routed table lookup. Adding a new command is one
        // entry in SLASH_COMMANDS (above this function) — no plumbing
        // here. Handlers own their own controller lifetime; the
        // framework only catches uncaught errors and emits a fallback
        // `error` event so a crashed handler can't leave the UI
        // hanging.
        //
        // Slash commands always short-circuit the normal chat-turn
        // path: there's no "/compress AND keep chatting" — the
        // command IS the turn.
        const parsed = parseSlashCommand(message);
        if (parsed) {
          const [_slashBaseConfig, slashDefaultModel] = await Promise.all([
            getEffectiveRuntimeConfig(),
            readDefaultModel(),
          ]);
          const runtimeConfig = { ..._slashBaseConfig, defaultModel: slashDefaultModel };
          await dispatchSlashCommand(parsed, SLASH_COMMANDS, {
            args: parsed.args,
            sessionId,
            isNewSession,
            trigger,
            runtimeConfig,
            requestedModel,
            requestedProvider,
            sendEvent,
            controller,
          });
          return;
        }

        const logDebug = (_stage: string, _detail: string) => {
          // Debug events were a guardian-specific concept (the old chat
          // page rendered them in a "Live telemetry" sidecar). Spark's
          // chat UI has its own thinking-section component; suppress
          // these for now rather than emit them as malformed Spark events.
        };

        // Operator's default model (operator_state.db) and subagents
        // preference are read in parallel to avoid two sequential round-trips.
        const [_baseRuntimeConfig, defaultModel, subagentsEnabled] = await Promise.all([
          getEffectiveRuntimeConfig(),
          readDefaultModel(),
          readSubagentsEnabled(),
        ]);
        // Shallow-copy so we can attach defaultModel without mutating the
        // cached/shared config object. Every resolveModelName() call in
        // this request receives the same runtimeConfig, so one population
        // covers all four call sites (callGeminiRaw, summarizeViaGemini,
        // callGemini, and the main-loop effectiveModel).
        const runtimeConfig = { ..._baseRuntimeConfig, defaultModel };

        // v0.1.27 — resolve approval bypass for this turn. Two sources:
        //   (a) the inbound request already carries
        //       `X-Guardian-Approval-Bypass` (a job dispatch from the
        //       scheduler with bypass_approvals=true), OR
        //   (b) session.metadata.approval_mode === 'bypass' (the chat
        //       UI dropdown set it).
        // Either source activates bypass for this turn. Stored on every
        // downstream MCP call so the trigger_context middleware on the
        // MCP side flips the contextvar gate_and_execute reads.
        const bypassFromInbound =
          (request.headers.get('x-guardian-approval-bypass') || '')
            .trim()
            .toLowerCase() === '1' ||
          (request.headers.get('x-guardian-approval-bypass') || '')
            .trim()
            .toLowerCase() === 'true';
        const sessionApprovalMode = isNewSession
          ? 'manual'
          : await loadSessionApprovalMode(sessionId, trigger);
        const approvalBypass = bypassFromInbound || sessionApprovalMode === 'bypass';
        // v0.3.27 — derive the narration mode passed to the system
        // prompt. Mirrors `approvalBypass` exactly so the agent's
        // promised UX (card vs. immediate-execute) matches what the
        // MCP-side gate will actually do this turn. Pre-v0.3.27 the
        // prompt only knew the manual recipe, so agents in bypass
        // mode would tell the operator "Pending your approval — the
        // card should appear below" while six destructive calls had
        // already executed — see session-0dda58d5 triage.
        const approvalMode: ApprovalMode = approvalBypass ? 'bypass' : 'manual';

        logDebug('mcp', `Connecting to MCP at ${runtimeConfig.MCP_URL}`);
        // Compose the extraHeaders dict so the MCP client attaches it
        // to every tool dispatch. Reserved-name precedence inside
        // GuardianMCPClient.headers() ensures Content-Type / Authorization
        // / mcp-* aren't accidentally clobbered if extras collide.
        const mcpExtraHeaders: Record<string, string> = {};
        if (trigger) mcpExtraHeaders['X-Guardian-Trigger'] = trigger;
        if (approvalBypass) mcpExtraHeaders['X-Guardian-Approval-Bypass'] = '1';
        const mcpClient = new GuardianMCPClient(
          runtimeConfig.MCP_URL,
          runtimeConfig.MCP_TOKEN,
          // Forward X-Guardian-Trigger + (when active)
          // X-Guardian-Approval-Bypass to every MCP tool dispatch so
          // audit rows for tools called during this chat inherit the
          // trigger tag AND so the MCP-side gate_and_execute reads the
          // bypass contextvar. The MCP's trigger_context middleware
          // sets both contextvars.
          Object.keys(mcpExtraHeaders).length > 0 ? mcpExtraHeaders : undefined,
        );
        if (approvalBypass) {
          // Surface the bypass status to the UI as a meta-event so the
          // chat UI can render the "Bypass ON" badge for this turn.
          // Idempotent — UI tracks the per-turn flag and updates the
          // badge accordingly.
          sendEvent('approval_mode', { mode: 'bypass' });
        }
        const tools = await getGeminiTools(
          mcpClient,
          runtimeConfig,
          logDebug,
          subagentsEnabled,
        );

        // Round-14 / Phase F.4 — resolve the effective model for this
        // turn. Priority chain:
        //   1. Header-dropdown override (requestedModel) — operator
        //      explicitly picked this model for this turn.
        //   2. Session preference (set via /model <name> on a prior
        //      turn, persisted in session.metadata.preferred_model).
        //   3. Runtime default (runtimeConfig.GEMINI_MODEL) — applied
        //      as a fallback inside resolveModelName / computeInputBudget
        //      when this value is undefined.
        //
        // We only consult the session pref when the operator didn't
        // pass a header override, so the header always wins. The
        // session pref also doesn't fire on brand-new sessions —
        // there's nothing to read yet, and saving the round-trip
        // matters on the cold-start path.
        const effectiveRequestedModel: string | undefined =
          requestedModel ??
          (isNewSession
            ? undefined
            : await loadSessionPreferredModel(sessionId, trigger));

        // Round-12 fix: build conversation context from prior persisted
        // messages so Gemini sees the running thread, not just the
        // latest user turn. For brand-new sessions or fetch failures,
        // history is empty and we fall back to single-turn behavior.
        // The user's CURRENT message was already persisted (line above
        // via safePersist) — so the load typically returns it as the
        // last entry. Two defensive cases below:
        //  1. New sessions: skip the history load (the persist may not
        //     have committed yet for our just-created session).
        //  2. The persist may have failed silently (safePersist swallows
        //     errors), in which case history won't have the current
        //     message — we manually append.
        // Phase 2.3 — pass the resolved model name so the history
        // walk knows the input-token budget. effectiveRequestedModel
        // already collapses header-override + session-pref + default.
        const historyModelName = effectiveRequestedModel || runtimeConfig.GEMINI_MODEL;
        const history = isNewSession
          ? []
          : await loadSessionHistory(sessionId, trigger, historyModelName, {
              // Phase 5 — auto-compaction hooks. If history would
              // exceed the model's input budget, summarize the
              // dropped portion via Gemini, persist as a checkpoint
              // for amortization, and surface activity to live
              // telemetry.
              summarize: (instructions, transcript) =>
                summarizeViaGemini(
                  instructions,
                  transcript,
                  runtimeConfig,
                  effectiveRequestedModel,
                ),
              persistCheckpoint: async (
                summary,
                coversUntil,
                messagesSummarized,
              ) => {
                await safePersist(
                  sessionId,
                  {
                    role: 'system',
                    content: summary,
                    meta: {
                      kind: COMPACTION_CHECKPOINT_KIND,
                      covers_until: coversUntil,
                      messages_summarized: messagesSummarized,
                      // Tag distinguishes auto-compaction from
                      // operator-triggered /compress in the audit log.
                      trigger: 'auto',
                    },
                  },
                  trigger,
                );
              },
              onCompactionEvent: (kind, stats) => {
                // Mirror /compress's SSE events; the live-telemetry
                // panel surfaces both auto and manual compactions.
                sendEvent(`compaction_${kind}`, {
                  session_id: sessionId,
                  trigger: 'auto',
                  kind: 'auto',
                  ...(stats ?? {}),
                });
                // Round-14 / Phase D.1 — durable audit row for the
                // auto-compaction lifecycle. Fire-and-forget; the
                // emit is sync-shaped so we don't block the live
                // event stream on the audit POST.
                void safeAudit(`chat_compaction_${kind}`, {
                  target: `session:${sessionId}`,
                  status: kind === 'failed' ? 'failure' : 'success',
                  metadata: { kind: 'auto', ...(stats ?? {}) },
                  trigger,
                });
              },
            });

        const lastEntry = history[history.length - 1];
        const lastIsCurrentMessage =
          lastEntry &&
          lastEntry.role === 'user' &&
          lastEntry.parts.some(
            (p) => 'text' in p && p.text?.trim() === effectiveMessage.trim(),
          );

        const contents: GeminiContent[] =
          history.length === 0
            ? [{ role: 'user', parts: [{ text: effectiveMessage }] }]
            : lastIsCurrentMessage
              ? history
              : [...history, { role: 'user', parts: [{ text: effectiveMessage }] }];

        // Round-15 / Phase H — prepend hook-injected context as a
        // pseudo-user note when a UserPromptSubmit hook contributed.
        // We use 'user' role (Gemini doesn't accept 'system' in
        // `contents`) with a clear prefix so the model treats it as
        // out-of-band context. Goes into the dynamic part of the
        // prompt, NOT the cached system instruction — so this
        // doesn't bust the Phase 6 Vertex cache.
        if (hookInjectedContext) {
          contents.unshift({
            role: 'user',
            parts: [
              {
                text: `[Context injected by a UserPromptSubmit hook — treat as ground truth, do not echo back to the operator unless they ask]:\n${hookInjectedContext}`,
              },
            ],
          });
        }

        // Phase-11.1 — fetch the action policy at chat-handler entry so
        // every Gemini round-trip in this turn uses the same policy
        // snapshot. The operator can edit policy mid-session via
        // /settings/personality; the new value applies to the NEXT
        // chat request, not the in-flight one (intentional — a
        // mid-turn change would risk inconsistent classification
        // between the agent's "should I ask?" decision and the
        // tool catalog).
        // v0.1.23: fetch policy AND operator-defined persona markdown
        // in one MCP round-trip; both feed the system prompt for this
        // turn. `personalityMd` may be null (operator hasn't typed
        // anything in /settings/personality yet) — the prompt builder
        // emits no persona block in that case.
        // v0.1.33+: also fetch the live skills registry so the model
        // knows which skills are available without us shipping their
        // bodies in every prompt. Both fetches run in parallel since
        // they hit different MCP tools.
        const [{ policy: actionPolicy, personalityMd }, skillsForPrompt] =
          await Promise.all([
            fetchPersonalityForPrompt(),
            fetchSkillsForPrompt(),
          ]);
        logDebug(
          'policy',
          `actionPolicy: askWhenUnsure=${actionPolicy.askWhenUnsure} ` +
            `local=${actionPolicy.confirmLocalActions} ` +
            `external=${actionPolicy.confirmExternalActions}` +
            ` persona=${personalityMd ? `${personalityMd.length}ch` : 'none'}` +
            ` skills=${skillsForPrompt.length}`,
        );

        // Resolve which model is *actually* going to be called (override
        // wins, then runtime config, then hardcoded fallback). Log it
        // and emit an SSE `model` event so the chat UI's live telemetry
        // panel surfaces the actual model — not the configured default.
        // Operator round-12: "I switched models in the dropdown but it
        // still felt like Gemini 3.1." Was correct: the override was
        // never read. Now it is, and this event proves which one ran.
        const effectiveModel = resolveModelName(effectiveRequestedModel, runtimeConfig);
        logDebug('model', `Sending prompt to ${effectiveModel}` +
          (effectiveRequestedModel ? ` (operator/session override)` : ` (runtime default)`));
        sendEvent('model', {
          model: effectiveModel,
          provider: requestedProvider || 'auto',
          // `override` is true when EITHER the header dropdown OR a
          // persisted /model session pref displaced the runtime default.
          // `override_source` lets the UI distinguish without changing
          // the boolean's existing meaning.
          override: Boolean(effectiveRequestedModel),
          override_source: requestedModel
            ? 'header'
            : effectiveRequestedModel
              ? 'session'
              : 'none',
        });

        // ── Phase 3.1 — Context-window guard ─────────────────────
        //
        // Estimate total request token cost (input + reserved output)
        // and compare to the model's context cap. Fail fast with a
        // structured error if we'd overflow; warn via debug event if
        // we're near the edge so the operator can act before the next
        // turn (start a new session, run compaction, etc).
        //
        // The estimates are conservative — see lib/tokens.ts notes —
        // so the >99% threshold is unlikely to over-block. Real
        // overflows still get caught at the provider; this is just
        // earlier, with a clearer error.
        const ctxCap = resolveContextCap(effectiveModel);
        const systemTokens = estimateTokens(
          // v0.3.27 — include approvalMode so the budgeting estimate
          // matches the prompt callGemini will actually send. The
          // bypass block is the longer of the two variants, so a
          // mode-blind estimate would under-count by ~50 tokens in
          // bypass sessions.
          buildSystemPromptText(actionPolicy, personalityMd, skillsForPrompt, approvalMode),
        );
        const toolsTokens = estimateTokens(JSON.stringify(tools ?? []));
        const contentsTokens = contents.reduce((acc, msg) => {
          const text = msg.parts
            .map((p) => ('text' in p && p.text) || '')
            .join('');
          return acc + estimateMessageTokens(text);
        }, 0);
        // v0.2.3 — was `4096` to match a now-removed
        // `maxOutputTokens: 4096` cap below. With the cap gone, the
        // model can output up to its natural ceiling (~65,536 for
        // gemini-3.1-pro-preview). We reserve THAT much room in the
        // input-side context budget so the model never gets squeezed
        // by an oversize prompt that leaves no room to respond. This
        // is INPUT-side accounting (how much we trim the prompt to
        // fit), NOT an output cap. Gemini still writes as much as the
        // response naturally needs.
        const reservedOutput = 65536;
        const totalRequired =
          systemTokens + toolsTokens + contentsTokens + reservedOutput;
        const utilization = totalRequired / ctxCap;

        if (utilization >= 0.99) {
          // Hard block — Vertex would error out anyway, this gives a
          // structured signal the chat UI can surface.
          sendEvent('error', {
            error:
              `Context window full: estimated ${totalRequired.toLocaleString()} ` +
              `tokens vs cap ${ctxCap.toLocaleString()} (${(utilization * 100).toFixed(1)}%). ` +
              `Start a new chat or wait for compaction (Phase 5) to land.`,
            code: 'CONTEXT_NEAR_FULL',
            tokens_estimated: totalRequired,
            tokens_cap: ctxCap,
            tokens_breakdown: {
              system: systemTokens,
              tools: toolsTokens,
              contents: contentsTokens,
              output_reserve: reservedOutput,
            },
          });
          controller.close();
          return;
        }
        if (utilization >= 0.90) {
          // Soft warn — emit a debug event so the live-telemetry
          // panel can surface it without blocking the turn.
          logDebug(
            'context',
            `near-cap: ${(utilization * 100).toFixed(1)}% ` +
              `(${totalRequired.toLocaleString()} / ${ctxCap.toLocaleString()})`,
          );
          sendEvent('context_warning', {
            tokens_estimated: totalRequired,
            tokens_cap: ctxCap,
            utilization,
          });
          // Round-14 / Phase D.2 — durable audit row. The
          // observability page can grep for action:chat_context_warning
          // to see "which sessions are crowding their context window."
          // Fire-and-forget so the audit POST doesn't add latency to
          // the in-flight turn.
          void safeAudit('chat_context_warning', {
            target: `session:${sessionId}`,
            metadata: {
              tokens_estimated: totalRequired,
              tokens_cap: ctxCap,
              utilization: Number(utilization.toFixed(4)),
              model: effectiveModel,
            },
            trigger,
          });
        }

        let response = await callGemini(contents, tools, runtimeConfig, actionPolicy, effectiveRequestedModel, personalityMd, skillsForPrompt, approvalMode, turnThinking);
        logDebug('model', 'Received initial response');

        // Round-15 / Phase $ — record cost for the initial Gemini
        // call. Subsequent tool-result follow-ups (in the for-loop
        // below) record their own rows. We accumulate the total in
        // `turnTotalCostUsd` and emit a single turn_cost SSE event
        // at done time so the chat UI can show "this turn cost $X"
        // without having to sum events.
        let turnTotalCostUsd = 0;
        let turnTotalTokens = { input: 0, cached: 0, output: 0 };
        {
          const c = extractAndRecordCost(response, {
            sessionId,
            model: effectiveModel,
            trigger,
            callKind: 'initial',
          });
          turnTotalCostUsd += c.usd;
          turnTotalTokens.input += c.inputTokens;
          turnTotalTokens.cached += c.cachedTokens;
          turnTotalTokens.output += c.outputTokens;
        }

        // Phase 6.3 — surface cache hits to live telemetry. Vertex
        // returns `usageMetadata.cachedContentTokenCount` on any
        // response that referenced a cached resource. Zero / absent
        // means we sent the inline system prompt (cache create
        // failed or wasn't tried — direct API key path doesn't use
        // caching at all). Operators see this in the live-telemetry
        // panel as proof the optimization is engaged.
        const usage = (response as { usageMetadata?: Record<string, unknown> })
          .usageMetadata;
        const cachedTokens =
          (usage?.['cachedContentTokenCount'] as number | undefined) ?? 0;
        if (cachedTokens > 0) {
          const promptTokens =
            (usage?.['promptTokenCount'] as number | undefined) ?? 0;
          sendEvent('cache_hit', {
            cached_tokens: cachedTokens,
            prompt_tokens: promptTokens,
            // promptTokenCount includes cached + uncached input;
            // subtract to surface what we actually paid full-price
            // for this turn.
            full_price_input_tokens: promptTokens - cachedTokens,
            model: effectiveModel,
          });
          // Round-14 / Phase D.3 — durable cache-hit audit row with
          // token-savings stats so operators can chart Vertex caching
          // ROI over time. cached_tokens is what billed at ~25%;
          // savings_tokens approximates "what we'd otherwise have
          // paid full price for" (cached × 0.75, the inverse of the
          // 25% billing rate).
          void safeAudit('chat_cache_hit', {
            target: `session:${sessionId}`,
            metadata: {
              cached_tokens: cachedTokens,
              prompt_tokens: promptTokens,
              full_price_input_tokens: promptTokens - cachedTokens,
              savings_tokens_est: Math.floor(cachedTokens * 0.75),
              model: effectiveModel,
            },
            trigger,
          });
        }

        let finalText: string[] = [];
        let toolCalls: Array<{ tool: string; args: Record<string, unknown>; result: string; error?: string }> = [];

        // v0.1.25: track whether the loop exited because we ran out of
        // tool-call budget (vs. clean break with no further function
        // calls). If exhausted AND finalText is empty after the loop,
        // we'll fire one more no-tools call asking the model to
        // summarize what it learned so the operator gets SOMETHING
        // instead of a silent dead-end.
        let exhaustedBudget = true;

        // v0.17.117 — leaked-tool-call recovery counter (issue #114).
        // Gemini thinking models occasionally serialize a LARGE pending
        // tool call (e.g. xsiam_add_lookup_data with a ~3,900-token
        // rows payload) as `thought` text instead of a structured
        // functionCall part. The call is then dropped and the turn ends
        // silently — the operator sees the plan but no tool runs. When we
        // detect that (a thought part carrying Gemini's `default_api`
        // function-call marker, with zero structured functionCalls this
        // turn), we retry the SAME turn with forced function-calling
        // (toolConfig mode:'ANY') + thinking off so the model emits a clean
        // structured call. Bounded so a pathological double-leak can't loop.
        let leakRecoveryAttempts = 0;
        const MAX_LEAK_RECOVERY = 2;
        // v0.17.129 (#125) — bound the genuinely-empty-turn auto-retry.
        let emptyTurnRetries = 0;
        const MAX_EMPTY_TURN_RETRIES = 1;

        // v0.17.130 (#127) — turn-scoped memo for idempotent reads. Declared
        // OUTSIDE the step loop so a catalog/schema/knowledge result fetched in
        // an early agent step is reused by later steps in THIS user message
        // instead of re-dispatching to the MCP. Per-message scope (never
        // module-level) so no snapshot leaks across turns or operators. See
        // TURN_CACHEABLE_TOOLS / invalidatesTurnCache above the POST handler.
        const turnToolCache = new Map<string, unknown>();

        // v0.17.131 (#129) — per-message failure ledger: identical (tool, args)
        // call key -> { count, error }. After MAX_IDENTICAL_FAILS failures of the
        // SAME call this turn, further identical dispatches are short-circuited
        // with a "change approach" payload, breaking deterministic retry loops.
        const turnFailedCalls = new Map<string, { count: number; error: string }>();
        const MAX_IDENTICAL_FAILS = 2;

        // v0.6.32 — bumped from 20 → 30 + configurable via env. The
        // 20-turn cap was hit empirically by long investigation loops:
        // a 20-step evidence-collection sweep × ~2 tool calls per turn
        // (poll + XDR pulse) needed ~15-20 turns just for the wait
        // phase, plus 5-10 turns for prereqs + setup + final sweep.
        // v0.6.32 pairs the bump with polling tools that internalize
        // the 30-60s wait per step — so each turn now advances the
        // hunt by 1-2 steps (vs a noop poll). 30 turns covers a
        // 20-step evidence-collection sweep with room to spare.
        // Operators can tune via env var.
        const MAX_AGENT_TURNS = (() => {
          const raw = process.env.GUARDIAN_CHAT_MAX_TURNS;
          if (!raw) return 30;
          const n = parseInt(raw, 10);
          return Number.isFinite(n) && n >= 5 && n <= 200 ? n : 30;
        })();

        for (let step = 0; step < MAX_AGENT_TURNS; step++) {
          const candidate = response.candidates?.[0];
          const parts: GeminiPart[] = candidate?.content?.parts || [];

          // v0.17.112 — suppress read-tool narration in the chat stream.
          // Models habitually emit "I'll call `log_destinations_list`." as
          // response text right before a tool call. Every call + its result
          // is already in the live telemetry, so that prose only duplicates
          // what the operator already sees. Pre-scan this turn's tool calls:
          // if the turn makes calls and ALL of them are non-gated (read /
          // auto-approved), drop the accompanying text parts — they're pure
          // narration. Gated calls keep their text (the why-line for the
          // approval card); plain-answer turns (no calls) keep their text.
          // Deterministic: does NOT depend on the model obeying a
          // "don't narrate" system-prompt rule (which it ignores — the
          // v0.17.111 prompt carve-out alone did not suppress this).
          const turnCalls: GeminiFunctionCall[] = parts
            .filter((p) => p.functionCall)
            .map((p) => p.functionCall as GeminiFunctionCall);
          let suppressReadNarration = false;
          if (turnCalls.length > 0) {
            const gatedFlags = await Promise.all(
              turnCalls.map((c) => isToolGated(c.name).catch(() => false)),
            );
            suppressReadNarration = gatedFlags.every((g) => g === false);
          }

          const functionCalls: GeminiFunctionCall[] = [];
          // v0.17.117 — track whether a tool call leaked into the thinking
          // channel this turn (Gemini serialized it as `thought` text
          // rather than a structured functionCall). `default_api` is
          // Gemini's function-call namespace marker and never appears in
          // legitimate reasoning prose. See issue #114.
          let leakedToolCallInThought = false;
          for (const part of parts) {
            if (part.text) {
              if (part.thought === true) {
                // v0.17.87 — reasoning part. Stream as `thinking` so the
                // UI's ThinkingSection picks it up and renders collapsed
                // above the answer. Excluded from finalText so the saved
                // .content stays the clean answer-only transcript.
                sendEvent('thinking', { text: part.text });
                if (!leakedToolCallInThought && /default_api/.test(part.text)) {
                  leakedToolCallInThought = true;
                }
              } else if (suppressReadNarration) {
                // v0.17.112 — read-tool narration; drop it (the call is
                // already shown in the live telemetry). Not pushed to
                // finalText so the saved transcript stays clean too.
              } else {
                finalText.push(part.text);
                // Spark's hook switches on `event.type === 'text_delta'`.
                sendEvent('text_delta', { text: part.text });
              }
            }
            if (part.functionCall) {
              functionCalls.push(part.functionCall);
            }
          }

          if (functionCalls.length === 0) {
            // v0.17.117 — the model INTENDED a tool call but serialized it
            // into its thinking channel instead of emitting a structured
            // functionCall (large-argument calls trigger this on Gemini
            // thinking models). Retry the SAME turn once with forced
            // function-calling (toolConfig mode:'ANY') + thinking off so
            // Gemini emits a clean structured call, then re-process via
            // `continue`. Bounded by MAX_LEAK_RECOVERY so a pathological
            // double-leak can't loop. `contents` here is still the
            // pre-turn state (the leaked response hasn't been appended
            // yet), so the retry re-attempts the identical turn. Issue #114.
            if (leakedToolCallInThought && leakRecoveryAttempts < MAX_LEAK_RECOVERY) {
              leakRecoveryAttempts++;
              logDebug(
                'model',
                `Tool call leaked into thinking channel; retrying with forced function-calling (attempt ${leakRecoveryAttempts}/${MAX_LEAK_RECOVERY})`,
              );
              response = await callGemini(
                contents,
                tools,
                runtimeConfig,
                actionPolicy,
                effectiveRequestedModel,
                personalityMd,
                skillsForPrompt,
                approvalMode,
                false, // thinking off — force the model to commit to the call
                true, // forceToolUse — toolConfig.functionCallingConfig.mode = 'ANY'
              );
              continue;
            }
            // v0.17.129 (#125) — genuinely empty turn: no tool calls AND no
            // text produced anywhere this turn. An intermittent model hiccup
            // that otherwise surfaces "I didn't generate a response this turn"
            // and forces the user to retry by hand (observed in a UI smoke:
            // an identical prompt failed once, then worked on resend). Re-
            // invoke the SAME turn once (normal config) before giving up —
            // `contents` is still the pre-turn state, so this re-attempts
            // identically. Bounded by MAX_EMPTY_TURN_RETRIES.
            if (finalText.length === 0 && emptyTurnRetries < MAX_EMPTY_TURN_RETRIES) {
              emptyTurnRetries++;
              logDebug(
                'model',
                `Empty model turn (no text, no tool calls); auto-retrying (attempt ${emptyTurnRetries}/${MAX_EMPTY_TURN_RETRIES})`,
              );
              response = await callGemini(
                contents,
                tools,
                runtimeConfig,
                actionPolicy,
                effectiveRequestedModel,
                personalityMd,
                skillsForPrompt,
                approvalMode,
                turnThinking,
              );
              continue;
            }
            logDebug('model', 'No tool calls requested');
            exhaustedBudget = false;
            break;
          }

          // Issue #17 — server-side fallback preamble.
          //
          // The system prompt instructs the model to narrate every
          // gated tool call ("I'll do X with these args, approval
          // below") but Gemini doesn't always comply — sometimes it
          // emits a function call with zero accompanying text. When
          // that happens, the operator sees the approval card pop
          // out of nowhere and has to expand "Raw arguments" to
          // figure out what's about to happen. That defeats the
          // entire point of the approval gate.
          //
          // Defense-in-depth: if the model produced no text in this
          // turn, synthesize a one-line preamble per planned tool
          // call and stream it BEFORE the dispatch loop kicks off.
          // The approval_pending event still carries the structured
          // args (improved card UI uses them too), but this puts
          // human-readable context in the chat thread first.
          //
          // We only synthesize when finalText is empty — if the
          // model DID narrate, we don't add a duplicate preamble.
          if (finalText.length === 0) {
            for (const call of functionCalls) {
              // v0.17.112 — only synthesize a preamble for GATED calls
              // (the approval card needs the human context). Non-gated
              // reads stay silent — no preamble — matching the read-tool
              // narration filter above. Without this, a read-only turn
              // whose narration we just suppressed would fall through to
              // here (finalText empty) and get a synthesized preamble,
              // re-introducing exactly the narration we removed.
              const gatedCall = await isToolGated(call.name).catch(() => false);
              if (!gatedCall) continue;
              const preamble = formatToolPreamble(call.name, call.args || {});
              if (preamble) {
                sendEvent('text_delta', { text: preamble + '\n\n' });
              }
            }
          }

          contents.push({ role: 'model', parts });

          const responseParts: GeminiPart[] = [];
          for (const call of functionCalls) {
            const toolName = call.name;
            let toolArgs = call.args || {};
            const toolStartedAt = Date.now();
            logDebug('tool', `Calling ${toolName}`);
            const toolCallId = `tc_${crypto.randomUUID()}`;

            // v0.5.23 / Issue #23 — Permission policy enforcement.
            // Evaluate per-turn policy (set by the job dispatcher via
            // body.permission_policy) before the tool fires. A `deny`
            // short-circuits to a synthetic tool-error response the
            // model sees as a failed call; an `ask` falls through to
            // the standard approval card path (the existing Phase-11
            // gate handles it). Audit every deny so the operator can
            // reconstruct why a job's tools were blocked.
            const policyEval = evaluatePermissionPolicy(toolName, turnPolicy);
            if (policyEval.decision === 'deny') {
              const reason =
                policyEval.reason ?? 'Denied by job permission policy';
              sendEvent('tool_call', {
                tool_call_id: toolCallId,
                tool: toolName,
                args: toolArgs,
                status: 'denied_by_policy',
                reason,
              });
              responseParts.push({
                functionResponse: {
                  name: toolName,
                  response: {
                    error: reason,
                    denied_by_policy: true,
                    matched_list: policyEval.matchedList,
                    matched_pattern: policyEval.matchedPattern,
                  },
                },
              });
              toolCalls.push({
                tool: toolName,
                args: toolArgs,
                result: '',
                error: reason,
              });
              // Best-effort audit row (don't block on failure).
              void callMcpServer('/api/v1/audit', {
                method: 'POST',
                body: {
                  action: 'tool_denied_by_policy',
                  target: `tool:${toolName}`,
                  status: 'denied',
                  metadata: {
                    session_id: sessionId,
                    tool_name: toolName,
                    matched_list: policyEval.matchedList,
                    matched_pattern: policyEval.matchedPattern,
                  },
                },
              }).catch(() => {});
              continue; // skip the normal dispatch path
            }

            // Round-15 / Phase S — subagent_create interception.
            // The model invokes this synthetic tool to spawn a
            // scoped subagent. Bypass the standard MCP dispatch +
            // approval-poll path and route to runSubagent. The
            // result is fed back to the model as a regular
            // tool_result so the parent's reasoning loop continues
            // normally.
            if (toolName === SUBAGENT_CREATE_TOOL) {
              // v0.6.6 — defense-in-depth gate. If the operator has
              // disabled subagents, the model SHOULDN'T see this
              // tool in its catalog. But if it tries anyway (cached
              // catalog from prior turn, or model hallucinated the
              // tool), synthesize a clean denied response instead
              // of running a sidechain.
              if (!subagentsEnabled) {
                const deniedMsg =
                  'Subagent spawning is disabled by operator preference ' +
                  '(chat_subagents_enabled=false). Re-enable in the chat ' +
                  'header toggle to use subagent_create.';
                sendEvent('tool_call', {
                  id: toolCallId,
                  name: toolName,
                  arguments: toolArgs,
                  status: 'pending',
                });
                sendEvent('tool_result', {
                  tool_call_id: toolCallId,
                  name: toolName,
                  status: 'error',
                  error: deniedMsg,
                });
                responseParts.push({
                  functionResponse: {
                    name: toolName,
                    response: { error: deniedMsg, denied_by: 'operator_preference' },
                  },
                });
                continue;
              }
              const agentName = String(
                (toolArgs as Record<string, unknown>)['agent_name'] ?? '',
              ).trim();
              const subPrompt = String(
                (toolArgs as Record<string, unknown>)['prompt'] ?? '',
              ).trim();
              if (!agentName || !subPrompt) {
                const errMsg =
                  'subagent_create requires both `agent_name` and `prompt`.';
                sendEvent('tool_call', {
                  id: toolCallId,
                  name: toolName,
                  arguments: toolArgs,
                  status: 'pending',
                });
                sendEvent('tool_result', {
                  tool_call_id: toolCallId,
                  name: toolName,
                  status: 'error',
                  error: errMsg,
                });
                responseParts.push({
                  functionResponse: {
                    name: toolName,
                    response: { error: errMsg },
                  },
                });
                continue;
              }
              sendEvent('tool_call', {
                id: toolCallId,
                name: toolName,
                arguments: toolArgs,
                status: 'pending',
                metadata: resolveToolMetadata(toolName),
              });
              const subResult = await runSubagent({
                agentName,
                prompt: subPrompt,
                parentSessionId: sessionId,
                parentMessage: message,
                trigger,
                parentTools: tools,
                runtimeConfig,
                parentModel: effectiveRequestedModel,
                mcpClient,
                sendEvent,
              });
              const resultText = JSON.stringify({
                status: subResult.status,
                final_response: subResult.final_response,
                turns_used: subResult.turns_used,
                tool_calls_count: subResult.tool_calls_count,
                tools_called: subResult.tool_calls_made.map((t) => t.tool),
                subagent_session_id: subResult.subagent_session_id,
                duration_ms: subResult.duration_ms,
                error: subResult.error,
              });
              sendEvent('tool_result', {
                tool_call_id: toolCallId,
                name: toolName,
                status: subResult.status === 'completed' ? 'success' : 'error',
                result: resultText,
              });
              toolCalls.push({
                tool: toolName,
                args: toolArgs as Record<string, unknown>,
                result: resultText,
                error: subResult.error,
              });
              responseParts.push({
                functionResponse: {
                  name: toolName,
                  response: { result: resultText },
                },
              });
              continue;
            }

            // Round-15 / Phase H — PreToolUse hook fire-site. Hooks
            // can deny the call (block on policy), ask (force the
            // approval card even for soft-tier tools), or replace
            // the args (e.g. inject a tenant scope before xsiam
            // calls hit the wrong tenant). Fires BEFORE the
            // approval-card poll loop so a hook deny short-circuits
            // the whole gating flow.
            const preToolHook = await fireHookEvent(
              'PreToolUse',
              {
                event: 'PreToolUse',
                sessionId,
                toolName,
                args: toolArgs as Record<string, unknown>,
                trigger,
              },
              trigger,
            );
            if (preToolHook.decision === 'deny') {
              // Synthesize a tool result the model will see as a
              // failure, with the hook's reason as the error. The
              // model can then explain to the operator what was
              // blocked and why.
              const hookReason =
                preToolHook.reason ?? 'Tool call blocked by a PreToolUse hook.';
              sendEvent('tool_call', {
                id: toolCallId,
                name: toolName,
                arguments: toolArgs,
                status: 'pending',
              });
              sendEvent('tool_result', {
                tool_call_id: toolCallId,
                name: toolName,
                status: 'error',
                error: hookReason,
              });
              toolCalls.push({
                tool: toolName,
                args: toolArgs as Record<string, unknown>,
                result: '',
                error: hookReason,
              });
              responseParts.push({
                functionResponse: {
                  name: toolName,
                  response: {
                    error: hookReason,
                    blocked_by: 'pre_tool_use_hook',
                  },
                },
              });
              continue;
            }
            // If a hook returned `replace`, swap in the new args.
            // The model sees the original; the tool runs with the
            // hook-modified version. Useful for "scope every xsiam
            // call to the active incident's tenant_id".
            if (
              preToolHook.replace &&
              typeof preToolHook.replace === 'object'
            ) {
              toolArgs = preToolHook.replace as typeof toolArgs;
            }

            // Round-15 / Phase R — resolve tool metadata once per
            // call. The chat UI uses metadata.destructive/openWorld
            // to color the approval card border; metadata.readOnly
            // is informational; metadata.concurrencySafe is the
            // gating contract for future parallel batch execution
            // (deferred to a follow-up — see allConcurrencySafe
            // export). The metadata is denormalized onto every
            // tool_call event so the UI doesn't need a parallel
            // table lookup.
            const toolMetadata: ToolMetadata = resolveToolMetadata(toolName);

            sendEvent('tool_call', {
              id: toolCallId,
              name: toolName,
              arguments: toolArgs,
              status: 'pending',
              // Phase R metadata — UI reads `destructive` (red
              // border), `openWorld` (amber border), `readOnly`
              // (no border + relaxed approval policy in future
              // phases). `concurrencySafe` is hint-only for now.
              metadata: toolMetadata,
            });

            // Phase 11 — agent self-modification UX. If the tool is
            // listed in manifest.approvals.humanRequired[], the MCP-
            // side gate creates a pending row and blocks on
            // bus.wait_async until the operator resolves. Without
            // intervention the chat stream just hangs for up to 5
            // minutes while the agent appears stuck.
            //
            // Race the tool call against a poll loop that watches
            // /api/v1/approvals?status=pending. When a new row appears
            // (one whose id wasn't present before we made the call),
            // emit an `approval_pending` SSE event so the UI can
            // render an inline approval card while the call still
            // blocks on bus.wait_async. After the operator clicks
            // Approve in the card, the bus resolution unblocks the
            // tool call, the result flows through normally, and the
            // tool_result event finishes the cycle.
            const gated = await isToolGated(toolName).catch(() => false);
            let approvalPollAbort: AbortController | null = null;
            if (gated) {
              approvalPollAbort = new AbortController();
              // Snapshot existing pending IDs so we can detect just
              // the NEW row created by this tool call. v0.1.26:
              // scope to chat:<sessionId> so concurrent job-fired
              // approvals don't enter the snapshot diff.
              const before = await fetchPendingApprovalIds(sessionId).catch(
                () => new Set<string>(),
              );
              // Don't await — fire-and-forget poll loop. It self-
              // terminates either when it finds the new row or when
              // the AbortController fires (post-resolution).
              void pollForNewApproval({
                signal: approvalPollAbort.signal,
                snapshot: before,
                toolName,
                sessionId,
                onFound: (row) => {
                  sendEvent('approval_pending', {
                    tool_call_id: toolCallId,
                    approval_id: row.id,
                    tool: toolName,
                    args: toolArgs,
                    risk_tier: row.risk_tier ?? classifyRiskTier(toolName),
                    created_at: row.created_at,
                  });
                },
              });
            }

            let result;
            let toolError: Error | null = null;
            let servedFromCache = false; // v0.17.140 (#128): telemetry-badge a turn-cache hit
            // v0.17.130 (#127) — turn-cache short-circuit. For an idempotent
            // read whose identical (tool, args) result was already fetched this
            // user message, reuse it instead of re-dispatching to the MCP. Only
            // the network dispatch is skipped — truncation + the tool_result
            // event below still run so the model sees the result for THIS step.
            const turnCallKey = `${toolName} ${stableStringify(toolArgs)}`;
            const turnCacheKey = TURN_CACHEABLE_TOOLS.has(toolName)
              ? turnCallKey
              : null;
            const priorFails = turnFailedCalls.get(turnCallKey)?.count ?? 0;
            if (turnCacheKey && turnToolCache.has(turnCacheKey)) {
              // Cast to callTool's own return type so `result` keeps the same
              // shape it has on the live-dispatch path (the cache is typed
              // `unknown` to stay tool-agnostic).
              result = turnToolCache.get(turnCacheKey) as Awaited<
                ReturnType<typeof mcpClient.callTool>
              >;
              servedFromCache = true;
              approvalPollAbort?.abort();
              logDebug(
                'mcp',
                `turn-cache hit: ${toolName} — reused this-turn result, skipped redundant MCP dispatch`,
              );
            } else if (!isPollTool(toolName) && priorFails >= MAX_IDENTICAL_FAILS) {
              // v0.17.131 - this exact (tool, args) call already failed
              // MAX_IDENTICAL_FAILS times this turn. Stop re-dispatching and
              // hand the model a synthetic {ok:false} payload telling it to
              // change approach. Breaks deterministic retry loops (install x7)
              // without touching poll/wait tools or distinct-argument retries.
              approvalPollAbort?.abort();
              const prior = turnFailedCalls.get(turnCallKey)?.error ?? 'previous attempt failed';
              result = {
                content: [
                  {
                    type: 'text',
                    text: JSON.stringify({
                      ok: false,
                      error: prior,
                      note: `This identical call (same tool + arguments) has already failed ${priorFails} times this turn. Do NOT retry it; use different arguments, a different tool, or stop and report the blocker to the operator.`,
                    }),
                  },
                ],
              } as Awaited<ReturnType<typeof mcpClient.callTool>>;
              logDebug(
                'mcp',
                `turn-fail short-circuit: ${toolName} failed ${priorFails}x this turn, not re-dispatching`,
              );
            } else {
              try {
                result = await mcpClient.callTool(toolName, toolArgs);
              } catch (err) {
                toolError = err instanceof Error ? err : new Error(String(err));
              } finally {
                // Stop polling regardless of how the call ended (success,
                // tool error, approval denial). Cleanup is idempotent.
                approvalPollAbort?.abort();
              }
              // v0.17.131 - record failures (exception OR {ok:false} envelope)
              // so the next identical call increments toward the short-circuit.
              const failText = toolError
                ? (toolError.message || 'tool error').slice(0, 280)
                : resultFailureText(result);
              if (failText) {
                turnFailedCalls.set(turnCallKey, { count: priorFails + 1, error: failText });
              }
              // Cache only genuine successes - never an {ok:false} result.
              if (turnCacheKey && !toolError && result && !resultFailureText(result)) {
                turnToolCache.set(turnCacheKey, result);
              }
              // A catalog/config mutation invalidates the static-read snapshot
              // so a same-turn re-read sees fresh state, not the pre-mutation one.
              if (!toolError && invalidatesTurnCache(toolName)) {
                turnToolCache.clear();
              }
            }

            // v0.5.27 / Issue #32 — evidence truncation. The MCP tool
            // result is { content: [{type, text}, ...] }. We truncate
            // each text content entry that exceeds maxBytes — head +
            // marker + tail. Structured non-text content passes
            // through. Audit every truncation so operators see where
            // it fired.
            if (
              result &&
              typeof result === 'object' &&
              'content' in result &&
              Array.isArray((result as { content?: unknown[] }).content) &&
              !toolError
            ) {
              const truncationPolicy = truncationPolicyFromEnv();
              const contentArr = (result as { content: Array<Record<string, unknown>> }).content;
              for (let i = 0; i < contentArr.length; i++) {
                const part = contentArr[i];
                if (typeof part?.text !== 'string') continue;
                const truncation = applyTruncation(toolName, part.text, truncationPolicy);
                if (truncation.truncated) {
                  contentArr[i] = { ...part, text: truncation.output };
                  void callMcpServer('/api/v1/audit', {
                    method: 'POST',
                    body: {
                      action: 'tool_output_truncated',
                      target: `tool:${toolName}`,
                      status: 'success',
                      metadata: {
                        session_id: sessionId,
                        tool_name: toolName,
                        bytes_dropped: truncation.bytesDropped,
                        bytes_kept: truncation.bytesKept,
                        head_kept: truncation.headKept,
                        tail_kept: truncation.tailKept,
                        max_bytes: truncationPolicy.maxBytes,
                        content_index: i,
                      },
                    },
                  }).catch(() => {});
                }
              }
            }

            if (toolError || !result) {
              // Round-15 / Phase H — PostToolUseFailure hook fire-site.
              // Non-decisional. Hooks may forward the failure to an
              // external incident channel ("xsiam tool errored on
              // session X").
              void fireHookEvent(
                'PostToolUseFailure',
                {
                  event: 'PostToolUseFailure',
                  sessionId,
                  toolName,
                  args: toolArgs as Record<string, unknown>,
                  error:
                    toolError?.message ?? 'tool returned no result',
                  durationMs: Date.now() - toolStartedAt,
                  trigger,
                },
                trigger,
              );
              const errMsg =
                toolError?.message ?? 'tool returned no result';

              // Round-15 / Phase M — record the failure in the
              // connector state machine. We classify auth errors
              // by message-string heuristic (401, 403, "auth",
              // "expired", "invalid token") because the MCP-side
              // tool wrapper today doesn't expose a structured
              // error type. The connector id is the first segment
              // of the tool name (`<connector>.<tool>`); legacy
              // flat aliases get split on `_`.
              const isAuthError = /\b(401|403|unauth|forbidden|invalid (token|api key|credentials|auth)|expired|reauth|needs.?auth)\b/i.test(
                errMsg,
              );
              // v0.6.42 — use the helper. Pre-v0.6.42 inline
              // split('_', 1)[0] returned wrong connector_ids for
              // connectors whose function prefix differs from their
              // id (xdr_*, guardian_*, guardian_web_*, cortex_*).
              const connectorId = deriveConnectorId(toolName);
              if (connectorId) {
                void recordConnectorFailure(connectorId, {
                  error: errMsg,
                  isAuthError,
                  trigger,
                });
                if (isAuthError) {
                  // Surface to chat UI so operator sees a needs-
                  // auth chip on /connectors without having to
                  // open the page.
                  sendEvent('connector_auth_required', {
                    connector_id: connectorId,
                    tool_name: toolName,
                    session_id: sessionId,
                  });
                }
              }

              sendEvent('tool_result', {
                tool_call_id: toolCallId,
                name: toolName,
                status: 'error',
                error: errMsg,
              });
              toolCalls.push({
                tool: toolName,
                args: toolArgs as Record<string, unknown>,
                result: '',
                error: errMsg,
              });
              responseParts.push({
                functionResponse: {
                  name: toolName,
                  response: { error: errMsg },
                },
              });
              continue;
            }

            let resultText =
              result.content[0]?.text || JSON.stringify(result.content);
            logDebug('tool', `Result from ${toolName} (${resultText.length} chars)`);

            // Round-15 / Phase H — PostToolUse hook fire-site. Hook
            // may replace the result (scrub sensitive output before
            // the model sees it) or no-op. We await this one because
            // a `replace` has to land before the result event fires.
            const postToolHook = await fireHookEvent(
              'PostToolUse',
              {
                event: 'PostToolUse',
                sessionId,
                toolName,
                args: toolArgs as Record<string, unknown>,
                result: resultText,
                durationMs: Date.now() - toolStartedAt,
                trigger,
              },
              trigger,
            );
            if (typeof postToolHook.replace === 'string') {
              resultText = postToolHook.replace;
            }

            sendEvent('tool_result', {
              tool_call_id: toolCallId,
              name: toolName,
              status: 'success',
              result: resultText,
              cached: servedFromCache,
            });

            // Round-15 / Phase M — record success in connector state.
            // A successful call after a failure transitions the
            // connector back to `connected`; subsequent successes
            // are O(1) updates.
            // v0.6.42 — use the helper. Pre-v0.6.42 inline
            // split('_', 1)[0] returned wrong connector_ids for
            // hyphenated-id connectors.
            const successConnectorId = deriveConnectorId(toolName);
            if (successConnectorId) {
              void recordConnectorSuccess(successConnectorId, trigger);
            }

            toolCalls.push({
              tool: toolName,
              args: toolArgs as Record<string, unknown>,
              result: resultText,
            });

            responseParts.push({
              functionResponse: {
                name: toolName,
                response: {
                  result: resultText,
                },
              },
            });

          }

          if (responseParts.length > 0) {
            contents.push({
              role: 'user',
              parts: responseParts,
            });
          }

          logDebug('model', 'Sending tool results to model');
          // Use the same operator-selected model for follow-up calls
          // so the entire turn — initial prompt and tool round-trips —
          // runs on one model. Mixing models within a turn would
          // confuse the assistant's continuation logic.
          response = await callGemini(
            contents,
            tools,
            runtimeConfig,
            actionPolicy,
            effectiveRequestedModel,
            personalityMd,
            skillsForPrompt,
            approvalMode,
            turnThinking,
          );
          logDebug('model', 'Received follow-up response');
          // Round-15 / Phase $ — record cost for the follow-up.
          {
            const c = extractAndRecordCost(response, {
              sessionId,
              model: effectiveModel,
              trigger,
              callKind: 'followup',
            });
            turnTotalCostUsd += c.usd;
            turnTotalTokens.input += c.inputTokens;
            turnTotalTokens.cached += c.cachedTokens;
            turnTotalTokens.output += c.outputTokens;
          }
        }

        // v0.5.134 / v0.6.35 — drain the last unprocessed response on
        // budget exhaustion.
        //
        // The for-loop above processes a candidate's text + functionCalls
        // at the TOP of each iteration. When the loop dispatches tools
        // in iteration N, it calls callGemini() at the BOTTOM — and the
        // response from THAT call is what iteration N+1 would normally
        // process. If iteration N is the last allowed iteration
        // (step = MAX_AGENT_TURNS - 1), N+1 never runs, and the
        // response is silently dropped.
        //
        // Empirically (session-e980fc7d.md, 2026-05-19), that response
        // often contains the operator's actual deliverable: the final
        // answer the model wrote AFTER seeing the last batch of tool
        // results. Phase 3 of a kill-chain demo lost its XDR cross-
        // reference table because of this — the operator saw the run
        // narrative but not the final summary.
        //
        // The subagent loop already handles this case (lines ~792-806
        // above). The chat route was missing the equivalent fix —
        // same root cause, sibling regression. Per CLAUDE.md §7
        // bug-family audit, the chat-route fix mirrors the subagent's,
        // with the additional responsibility of streaming text_delta
        // events so the recovered text appears in the live UI
        // (subagent doesn't stream).
        //
        // Function calls in this final response are intentionally
        // dropped — we can't dispatch them without bumping the cap,
        // and the deliverable text is what matters most. If the final
        // response also lacks text, the budget-summary fallback below
        // handles the "still nothing to show" case.
        if (exhaustedBudget) {
          const finalCandidate = response.candidates?.[0];
          const finalParts: GeminiPart[] = finalCandidate?.content?.parts || [];
          let recoveredChars = 0;
          for (const part of finalParts) {
            if (part.text) {
              finalText.push(part.text);
              sendEvent('text_delta', { text: part.text });
              recoveredChars += part.text.length;
            }
          }
          if (recoveredChars > 0) {
            logDebug(
              'model',
              `Recovered ${recoveredChars} chars of post-budget text ` +
                `from final unprocessed response`,
            );
          }
        }

        let finalResponse = finalText.join('\n').trim();

        // v0.1.25 — tool-budget exhaustion summary. If the loop ran
        // for 20 turns without producing any text, fire one more
        // no-tools call asking the model to summarize what it found.
        // Gives the operator partial value instead of a dead-end.
        // Pattern ported from blackhat-noc Slack bot's "Budget exhausted"
        // fallback. Only fires when both conditions hold:
        //   - exhaustedBudget (loop hit the 20-turn cap)
        //   - finalResponse is empty (model produced zero text across
        //     all turns; if it produced anything, respect that)
        if (exhaustedBudget && !finalResponse) {
          logDebug(
            'model',
            `Tool budget exhausted (${toolCalls.length} tool calls, 0 text); ` +
              `firing summary fallback`,
          );
          contents.push({
            role: 'user',
            parts: [{
              text:
                'Tool budget reached. Summarize your findings so far for the ' +
                'operator, even if the investigation is incomplete. Do not ' +
                'call any more tools.',
            }],
          });
          try {
            // Pass `[]` for tools — model can't call more even if it
            // wants to. Belt-and-suspenders against a model that
            // ignores the prompt instruction.
            const summary = await callGemini(
              contents,
              [],
              runtimeConfig,
              actionPolicy,
              effectiveRequestedModel,
              personalityMd,
              skillsForPrompt,
              approvalMode,
            );
            const summaryParts: GeminiPart[] =
              summary.candidates?.[0]?.content?.parts || [];
            for (const part of summaryParts) {
              if (part.text) {
                finalText.push(part.text);
                sendEvent('text_delta', { text: part.text });
              }
            }
            finalResponse = finalText.join('\n').trim();
            // Cost record for the summary call (separate from the
            // turn's main accounting).
            const c = extractAndRecordCost(summary, {
              sessionId,
              model: effectiveModel,
              trigger,
              callKind: 'budget_summary',
            });
            turnTotalCostUsd += c.usd;
            turnTotalTokens.input += c.inputTokens;
            turnTotalTokens.cached += c.cachedTokens;
            turnTotalTokens.output += c.outputTokens;
          } catch (err) {
            logDebug(
              'model',
              `Tool-budget summary fallback failed: ${
                err instanceof Error ? err.message : String(err)
              }`,
            );
            // Falls through to synthesizeFallbackText below.
          }
        }

        if (!finalResponse || !finalResponse.trim()) {
          // v0.17.135 (#132) — also catch a WHITESPACE-ONLY finalResponse, not
          // just a strictly-empty one. A turn that ran read tools (e.g. dataset
          // review: xsiam_get_datasets + xsiam_get_dataset_fields) but came back with " " was
          // truthy, slipped past `!finalResponse`, and rendered as a blank
          // assistant message. `.trim()` routes it into the recap below.
          //
          // Gemini sometimes returns turns that are 100% function calls
          // and 0% text, especially after approval-gated tool round-
          // trips: the model emits the tool call, the gate blocks for
          // human approval, and the post-approval response can be a
          // bare functionCall with no narration. Across the whole loop
          // that leaves finalText empty.
          //
          // The old fallback ("No model response was returned. Review
          // the tool results above…") was technically accurate but
          // unhelpful — operators couldn't tell whether anything
          // actually ran or what to do next. Build a context-aware
          // recap instead, then PERSIST it so a session reload doesn't
          // show a blank assistant turn.
          //
          // We pull `finishReason` off the last candidate to
          // distinguish "model just chose silence" (STOP) from
          // truncation (MAX_TOKENS) from safety blocks (SAFETY) — the
          // last two warrant different operator advice.
          const lastCandidate = response.candidates?.[0] as
            | { finishReason?: string }
            | undefined;
          const finishReason = lastCandidate?.finishReason;
          finalResponse = synthesizeFallbackText(toolCalls, finishReason);
          sendEvent('text_delta', { text: finalResponse });
        }

        // Persist tool round-trips first, then the assistant's final
        // text. Order matches the on-screen render order so an export
        // reads top-to-bottom like the chat. Each call is best-effort
        // and isolated, so one failure doesn't drop the rest.
        for (const tc of toolCalls) {
          await safePersist(sessionId, {
            role: 'tool',
            content: tc.result,
            tool_call_id: tc.tool,
            meta: { tool: tc.tool, args: tc.args },
          }, trigger);
        }
        // Always persist an assistant row when there was anything to
        // show — including the synthesized fallback above. This means
        // on session reload, "No model response" sessions now render
        // the recap instead of going blank.
        if (finalResponse) {
          await safePersist(sessionId, {
            role: 'assistant',
            content: finalResponse,
            // Tag the persisted assistant message with which model
            // produced it. The MCP audit row written for this append
            // inherits the meta, so /observability/events shows
            // `chat_append` rows with the model name attached —
            // operator can grep `action:chat_append` and see which
            // models were used per turn.
            meta: {
              model: effectiveModel,
              model_override: Boolean(effectiveRequestedModel),
              model_override_source: requestedModel
                ? 'header'
                : effectiveRequestedModel
                  ? 'session'
                  : 'none',
              provider: requestedProvider || 'auto',
            },
          }, trigger);
        }

        // Auto-title brand-new sessions from the first user message.
        // 60 chars matches the column width Spark uses in the sidebar.
        //
        // NOTE (v0.2.40): `meta.scheduled_by` is now stamped at session
        // CREATE (see scheduledByAtCreate above) so job sessions are
        // tagged even when the turn fails before reaching this point.
        // This block only auto-titles; it no longer carries the tag.
        if (isNewSession) {
          const trimmed = message.trim();
          const preview =
            trimmed.length > 60 ? `${trimmed.slice(0, 60).trimEnd()}…` : trimmed;
          if (preview) {
            try {
              await callMcpServer(
                `/api/v1/sessions/${encodeURIComponent(sessionId)}`,
                {
                  method: 'PATCH',
                  body: { title: preview },
                  headers: trigger ? { 'X-Guardian-Trigger': trigger } : undefined,
                },
              );
            } catch (err) {
              console.warn(
                `chat: failed to auto-title session ${sessionId}:`,
                err instanceof Error ? err.message : err,
              );
            }
          }
        }

        // Round-15 / Phase $ — emit a turn_cost SSE event so the
        // chat UI can render "this turn cost $X.XX" inline. The
        // per-call audit rows already landed; this is just the
        // turn-level summary.
        sendEvent('turn_cost', {
          session_id: sessionId,
          cost_usd: Number(turnTotalCostUsd.toFixed(6)),
          input_tokens: turnTotalTokens.input,
          cached_input_tokens: turnTotalTokens.cached,
          output_tokens: turnTotalTokens.output,
          model: effectiveModel,
        });

        // Round-15 / Phase H — RunEnd hook fire-site. Non-decisional;
        // fires after the final response has been composed and
        // persisted but before the stream closes. Hooks typically
        // emit external notifications ("turn N completed in this
        // session, X tool calls").
        void fireHookEvent(
          'RunEnd',
          {
            event: 'RunEnd',
            sessionId,
            finalResponseChars: finalResponse.length,
            toolCallCount: toolCalls.length,
            durationMs: Date.now() - turnStartedAt,
            trigger,
          },
          trigger,
        );

        // Round-15 / Phase Y — surface the run status reason on
        // done. Determined by inspecting how the tool loop exited:
        //   - normal completion (model emitted final text)
        //   - max_turns_exceeded (loop hit the 20-step cap)
        //   - max_output_truncation (final response was synthesized
        //     because Gemini truncated; chat-route's fallback
        //     narration kicked in)
        // The current chat-route doesn't expose the loop's actual
        // exit cause, so we conservatively classify by the final
        // response shape: empty/synthesized = max_output_truncation,
        // present = completed.
        const runStatusReason: RunStatusReason = !finalResponse
          ? 'max_output_truncation'
          : 'completed';

        sendEvent('done', {
          response: finalResponse,
          toolCalls,
          status_reason: runStatusReason,
          duration_ms: Date.now() - turnStartedAt,
        });
      } catch (error) {
        console.error('Chat API error:', error);
        // Spark's hook reads error event.data as a plain string into the
        // assistant bubble, so emit a string here (not a JSON object).
        // Round-14 / Phase F — defensive: a slash-command handler that
        // already closed the controller would make this enqueue throw
        // ("Invalid state: Controller is already closed"), and that
        // throw would propagate out of the start() callback, tearing
        // down the response BEFORE any queued events flushed to the
        // wire. Swallow it — the close already happened; this error
        // event is best-effort.
        try {
          sendEvent(
            'error',
            error instanceof Error ? error.message : 'Unknown error',
          );
        } catch {
          // already closed by a slash-command handler — fine.
        }
      } finally {
        // Round-14 / Phase F — slash-command handlers own their own
        // close (they may want to leave the stream open across awaits;
        // some emit a long sequence of events and close at the end).
        // The unconditional close here used to throw "Invalid state:
        // Controller is already closed" on the post-dispatch return
        // path, and the synchronous throw torpedoed any events that
        // were enqueued-but-not-yet-flushed. Swallow it.
        try {
          controller.close();
        } catch {
          // already closed by a handler — events already enqueued
          // before that close are still delivered.
        }
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
    },
  });
}
