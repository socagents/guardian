export interface ChatMessage {
  /**
   * Round-14 / Phase G — `'system'` is reserved for in-thread markers
   * the chat handler persists to the messages table (today: compaction
   * checkpoints with `meta.kind === 'compaction-checkpoint'`). The
   * MessageList renders these as horizontal dividers, NOT as bubble
   * rows. Anything other than the recognized system kinds is filtered
   * out before reaching the message list.
   */
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  /** Optional metadata bag attached to system markers. Carries
   *  `kind`, `messages_summarized`, `summary_chars`, etc. for
   *  compaction checkpoints. */
  meta?: Record<string, unknown>;
  /** v0.5.46 — MCP-side message id when this row was loaded from
   *  persistence (vs streamed live). Used by per-message
   *  Fork-from-here in MessageList → POST /api/agent/sessions/{id}/fork
   *  with from_message_id=this.mcpId. */
  mcpId?: string;
  /** v0.6.28 — content-position offsets where tool_call events fired
   *  during this assistant turn, in chronological order. The text
   *  AFTER the LAST boundary index is the "final answer"; everything
   *  before is "preamble narrative" (tool-call announcements,
   *  thinking-out-loud, transitions between tool calls). The chat UI
   *  renders the two zones with different visual treatment so the
   *  operator can skim the final answer without parsing the agent's
   *  narration. Undefined / empty array = no tool calls fired = the
   *  entire content is the answer. Live-streamed messages have this;
   *  historical messages loaded from MCP storage don't (graceful
   *  fallback to single-blob rendering in message-list.tsx). */
  boundaryIndices?: number[];
  /** v0.17.87 — reasoning / extended-thinking text emitted by the
   *  model when generationConfig.thinkingConfig.includeThoughts is on.
   *  The chat route streams these as `thinking` SSE events; use-chat
   *  appends them here; message-list renders them via ThinkingSection
   *  (collapsed by default) ABOVE the bubble's answer body.
   *  #CHAT-F28 (v0.2.79) — now also persisted: the chat route stores the
   *  turn's accumulated reasoning on the assistant row's meta.reasoning,
   *  and the transcript loader rehydrates it here, so a session loaded
   *  from history re-renders its Thinking section. */
  reasoning?: string;
}

export interface ChatMeta {
  run_id: string;
  session_id: string;
  agent_id: string;
}

export interface ChatSSEEvent {
  type:
    | "meta"
    | "text_delta"
    | "thinking"
    | "tool_call"
    | "tool_result"
    /**
     * Phase 11 self-modification — emitted by the chat route when a
     * gated MCP tool creates a pending approval row (chat-route's
     * pollForNewApproval detected it and is racing against
     * bus.wait_async). Frontend renders an inline ApprovalCard.
     */
    | "approval_pending"
    | "run_completed"
    | "usage"
    | "error"
    | "done"
    /**
     * Round-12 — model resolution event. Surfaces which model
     * actually handled the turn (operator override vs runtime default).
     * Already emitted by the chat route; added here so the union
     * is exhaustive for typed switches.
     */
    | "model"
    /**
     * Round-13 / Phase 4.5 + Phase 5 — operator-triggered (/compress)
     * and auto-budget-edge conversation compaction. The chat handler
     * fires `compaction_start` before kicking off the summarizer,
     * `compaction_end` with stats once the checkpoint is persisted,
     * or `compaction_failed` if the summarizer errored.
     */
    | "compaction_start"
    | "compaction_end"
    | "compaction_failed"
    /**
     * Round-13 / Phase 3.1 — context-window guard. Fired when the
     * estimated input + reserved-output tokens crosses ~90% of the
     * model's context cap. Phase A.2 turns this into an inline
     * "you should /compress" suggestion banner.
     */
    | "context_warning"
    /**
     * Round-13 / Phase 6 — Vertex cachedContents hit. Fired when
     * Vertex reports `usageMetadata.cachedContentTokenCount > 0`,
     * meaning the system-prompt cache was reused on this turn (~25%
     * input-token billing on the cached portion). Phase A.4 surfaces
     * this as a cyan dot on the model-selector chip.
     */
    | "cache_hit"
    /**
     * Round-14 / Phase F.2 — `/clear` slash command. The chat route
     * ended the prior session and minted a fresh one; the new
     * session_id is in the event payload so the UI can swap its
     * active session pointer without a page reload.
     */
    | "session_cleared"
    /**
     * Round-14 / Phase F.4 — `/model <name>` slash command persisted
     * a per-session preferred_model. The next turn's `model` event
     * carries the resolved value; this event is just a write-receipt.
     */
    | "model_preference_changed"
    /**
     * Round-15 / Phase P — `/plan <prompt>` slash command lifecycle.
     * `plan_started` fires immediately; the model is composing the
     * plan. `plan_proposed` fires when the plan text is ready —
     * payload includes the plan markdown + the source prompt.
     */
    | "plan_started"
    | "plan_proposed"
    /**
     * Round-15 / Phase M — connector auth required. Fires when the
     * chat-route classifies a tool error as auth-related (401/403,
     * "expired", "invalid token"). The connector is transitioned
     * to `needs-auth` server-side; this event lets the chat UI
     * surface a needs-auth chip without polling
     * /observability/connectors.
     */
    | "connector_auth_required"
    /**
     * Round-15 / Phase $ — per-turn cost summary. Fires once per
     * turn at done time with input/cached/output token totals and
     * USD cost. Per-call audit rows already landed under
     * action:chat_turn_cost.
     */
    | "turn_cost"
    /**
     * Round-15 / Phase S — subagent lifecycle events. The model
     * called subagent_create; the chat-route's runSubagent emits
     * these as the subagent makes progress. The chat UI renders
     * a sidechain activity card in the thread to show what the
     * subagent is doing without leaving the parent's flow.
     */
    | "subagent_started"
    | "subagent_tool_call"
    | "subagent_tool_result"
    | "subagent_tool_blocked"
    | "subagent_completed"
    /**
     * v0.17.54+ — emitted by /api/chat/cli (Claude Code shell-out
     * endpoint), NOT by the main /api/chat route. The CLI route
     * streams stdout from `claude-code --print --output-format json`;
     * each parseable line becomes an `output` event carrying the
     * parsed JSON, and each non-parseable line becomes `output_raw`
     * with the line text. The chat-route's tool-call pipeline is not
     * involved on this path. v0.17.56 (A1.2) wires the chat UI's
     * /providers toggle to drive between the two routes from a single
     * sendMessage call site.
     */
    | "output"
    | "output_raw";
  data: string;
  id: number;
}

/** Parse a raw SSE event block (separated by double newlines) into a ChatSSEEvent. */
export function parseSSEEvent(raw: string): ChatSSEEvent | null {
  const lines = raw.split("\n");
  let id = 0;
  let type = "unknown";
  let data = "";

  for (const line of lines) {
    if (line.startsWith("id: ")) id = parseInt(line.slice(4), 10);
    else if (line.startsWith("event: ")) type = line.slice(7);
    else if (line.startsWith("data: ")) data = line.slice(6);
  }

  if (!type || type === "unknown") return null;
  return { type: type as ChatSSEEvent["type"], data, id };
}
