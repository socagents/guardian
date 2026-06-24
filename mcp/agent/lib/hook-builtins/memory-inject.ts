/**
 * Memory auto-inject — Issue #25 (v0.5.26).
 *
 * Fires on UserPromptSubmit, searches the agent's semantic memory for
 * entries relevant to the operator's message, formats the top-K hits
 * into a context block, and returns it via `injectContext` so the
 * chat-route's UserPromptSubmit consumer prepends it to the model's
 * system instruction for this turn.
 *
 * Why this is the third builtin-hook customer (slack-approval was the
 * first, pre-compact-context-warning the second): Octagon's
 * `inject_memory_context()` fires deterministically at the start of
 * Recon — the agent doesn't have to remember to call memory_search.
 * Guardian's chat agent today DOES have to remember, and in practice
 * only does it ~30% of the time. This builtin makes the recall
 * deterministic for operators who install it.
 *
 * Config:
 *   scope        — memory scope to search. Common values:
 *                  'agent' (cross-session knowledge — default),
 *                  'session:<sessionId>' (this conversation only —
 *                  use the magic `__session__` placeholder which the
 *                  builtin replaces with the actual sessionId at
 *                  fire time),
 *                  any operator-defined scope (e.g. 'instance:xsiam-
 *                  prod' if the operator has scoped memory writes
 *                  that way).
 *                  Empty / unset = all scopes (searches every memory).
 *   top_k        — number of memories to inject (1-20, default 5).
 *                  Larger = more cost per turn (those memories
 *                  become input tokens).
 *   min_score    — cosine threshold below which memories are dropped
 *                  (0.0-1.0, default 0.2). Higher = stricter
 *                  relevance.
 *   header       — text rendered above the memory block in the
 *                  injected context. Defaults to "Relevant prior
 *                  memories (from auto-inject hook):".
 *
 * Privacy: the builtin runs in the same process as the chat-route, so
 * "auto-injected memories" are visible to the agent the same way any
 * other system-prompt content is. Operators wanting per-session
 * isolation should use scope='session:__session__' which restricts to
 * the current conversation's memory only.
 */

import type { BuiltinHookSpec } from "./types";
import { callMcpServer } from "@/lib/mcp-proxy";

/**
 * #MEM-F10 — emit a best-effort audit signal when memory injection is SKIPPED.
 * Previously a search error or a zero-hit result both silently returned null
 * (hook-runner treats result=null,error=undefined as a no-op), so the operator
 * had no way to tell that the per-turn memory inject didn't fire. This records
 * a `memory_inject_skipped` row (reason discriminates search_error vs
 * zero_hits) without blocking the hook return — same fire-and-forget shape the
 * notification-emitting builtins use.
 */
function auditMemoryInjectSkipped(
  reason: "search_error" | "zero_hits",
  meta: { sessionId: string; scope: string; topK: number; minScore: number },
): void {
  void (async () => {
    try {
      await callMcpServer("/api/v1/audit", {
        method: "POST",
        body: {
          action: "memory_inject_skipped",
          target: `session:${meta.sessionId}`,
          status: "skipped",
          metadata: {
            reason,
            scope: meta.scope || null,
            top_k: meta.topK,
            min_score: meta.minScore,
          },
        },
      });
    } catch {
      // Signal is best-effort; never let it perturb the turn.
    }
  })();
}

interface MemoryHit {
  key: string;
  value: string;
  scope: string;
  updated_at: string;
  score: number;
}

interface MemorySearchResponse {
  results?: MemoryHit[];
  count?: number;
}

export const memoryInjectBuiltin: BuiltinHookSpec = {
  name: "memory-inject",
  displayName: "Memory auto-inject",
  description:
    "On every UserPromptSubmit, searches the agent's semantic memory " +
    "for entries relevant to the operator's message and prepends the " +
    "top-K hits to the model's system instruction. Eliminates the " +
    "'agent should have remembered to call memory_search but didn't' " +
    "failure mode.",
  icon: "psychology_alt",
  compatibleEvents: ["UserPromptSubmit"] as const,
  configFields: [
    {
      key: "scope",
      label: "Memory scope",
      type: "string",
      defaultValue: "agent",
      helper:
        "Memory scope to search. 'agent' = cross-session knowledge " +
        "(most common). Use 'session:__session__' to restrict to this " +
        "conversation. Leave empty to search all scopes.",
      placeholder: "agent",
      required: false,
    },
    {
      key: "top_k",
      label: "Top K memories to inject",
      type: "number",
      min: 1,
      max: 20,
      defaultValue: 5,
      helper:
        "Number of memories appended to the system instruction. Larger = " +
        "more cost per turn (memories become input tokens).",
      required: false,
    },
    {
      key: "min_score",
      label: "Minimum cosine score (0.0-1.0)",
      type: "number",
      min: 0,
      max: 1,
      defaultValue: 0.2,
      helper:
        "Drop hits below this score. Higher = stricter relevance. " +
        "0.2 is a permissive default; raise to 0.4+ to reduce noise.",
      required: false,
    },
    {
      key: "header",
      label: "Injected-block header text",
      type: "string",
      defaultValue: "Relevant prior memories (from auto-inject hook):",
      helper:
        "Rendered above the memory list in the system instruction. " +
        "Operators may localize or shorten.",
      required: false,
    },
  ] as const,
  validateConfig(raw) {
    if (raw && typeof raw !== "object") {
      return { ok: false, error: "config must be an object" };
    }
    const cfg = (raw ?? {}) as Record<string, unknown>;
    const out: Record<string, unknown> = {};

    const scope = cfg.scope;
    if (scope === undefined) {
      out.scope = "agent";
    } else if (typeof scope !== "string") {
      return { ok: false, error: "scope must be a string" };
    } else {
      out.scope = scope.trim();
    }

    const topK = cfg.top_k;
    if (topK === undefined) {
      out.top_k = 5;
    } else if (typeof topK !== "number" || topK < 1 || topK > 20) {
      return { ok: false, error: "top_k must be a number in [1, 20]" };
    } else {
      out.top_k = Math.floor(topK);
    }

    const minScore = cfg.min_score;
    if (minScore === undefined) {
      out.min_score = 0.2;
    } else if (typeof minScore !== "number" || minScore < 0 || minScore > 1) {
      return { ok: false, error: "min_score must be a number in [0, 1]" };
    } else {
      out.min_score = minScore;
    }

    const header = cfg.header;
    if (header === undefined) {
      out.header =
        "Relevant prior memories (from auto-inject hook):";
    } else if (typeof header !== "string") {
      return { ok: false, error: "header must be a string" };
    } else {
      out.header = header;
    }

    return { ok: true, config: out };
  },
  async handle(payload, config) {
    if (payload.event !== "UserPromptSubmit") return null;
    const message = payload.message;
    if (!message || typeof message !== "string" || !message.trim()) {
      return null;
    }
    const rawScope = config.scope as string;
    // `__session__` placeholder → substitute the actual sessionId so
    // operators can write `session:__session__` once in their hook
    // config and have it scope to whichever session is firing.
    const resolvedScope = rawScope
      ? rawScope.replace(/__session__/g, payload.sessionId)
      : "";

    let response: MemorySearchResponse;
    try {
      response = await callMcpServer<MemorySearchResponse>(
        "/api/v1/memories/search",
        {
          method: "POST",
          body: {
            query: message,
            limit: config.top_k as number,
            scope: resolvedScope || null,
            min_score: config.min_score as number,
          },
        },
      );
    } catch (err) {
      console.warn(
        "memory-inject: memory search failed:",
        err instanceof Error ? err.message : err,
      );
      // #MEM-F10 — surface the failed inject so it's not silent.
      auditMemoryInjectSkipped("search_error", {
        sessionId: payload.sessionId,
        scope: resolvedScope,
        topK: config.top_k as number,
        minScore: config.min_score as number,
      });
      return null;
    }

    const hits = (response.results ?? []).filter(
      (h) =>
        typeof h.value === "string" && h.value.trim().length > 0,
    );
    if (hits.length === 0) {
      // #MEM-F10 — a zero-hit inject is also a no-op the operator couldn't see.
      auditMemoryInjectSkipped("zero_hits", {
        sessionId: payload.sessionId,
        scope: resolvedScope,
        topK: config.top_k as number,
        minScore: config.min_score as number,
      });
      return null;
    }

    // Format the block. Each memory rendered as a bullet with key +
    // value + score (rounded). Capped at top_k by the search call.
    const lines = hits.map(
      (h) =>
        `  - [${h.key}, score=${h.score.toFixed(2)}] ${h.value.replace(/\s+/g, " ").trim()}`,
    );
    const header = config.header as string;
    const block = `${header}\n${lines.join("\n")}`;
    return { injectContext: block };
  },
};
