/**
 * Hook dispatcher — Round-15 / Phase H.
 *
 * Loads registered hooks from the MCP-backed store, filters by
 * event + matcher, runs each through its declared transport
 * (command / http / agent), and aggregates the results into a
 * single decision the chat-route consumes.
 *
 * Design notes:
 *
 *   - The runner is **best-effort** by default. A hook that times
 *     out / errors falls through per its `failurePolicy`. The
 *     chat stream NEVER hangs on a hook.
 *   - Hooks run **serially within an event** (priority order),
 *     not in parallel. Reasoning: a low-priority "log to slack"
 *     hook and a high-priority "deny if production target" hook
 *     should NOT both run when the high-priority one denies. In
 *     parallel we'd waste the slack call on a denied turn.
 *   - The first hook that returns `decision: 'deny'` short-
 *     circuits the chain. `'ask'` short-circuits but still runs
 *     subsequent `injectContext`-only hooks (a "deny" beats "ask"
 *     beats "allow" beats "no-op" precedence). For non-decisional
 *     events (PostToolUse, PostCompact, etc.) every hook runs.
 *   - Hooks are loaded fresh from MCP every event firing — no
 *     in-process memoization. A 30s TTL cache could be added
 *     later, but the file is small (~1KB per hook) and the MCP
 *     round-trip is well under 100ms.
 */

import { callMcpServer } from "@/lib/mcp-proxy";
import { deriveMcpBaseUrl } from "@/lib/runtime-config";
import {
  HOOK_EVENTS,
  type Hook,
  type HookEvent,
  type HookPayload,
  type HookResult,
  matchesHook,
  validateHook,
} from "@/lib/hooks";
import { getBuiltinHook } from "@/lib/hook-builtins";

/**
 * The dispatcher's aggregate result. Reflects the highest-precedence
 * decision across all hooks that fired for the event:
 *
 *   `deny` > `ask` > `allow` > undefined
 *
 * The chat-route uses this to decide whether to proceed, surface
 * an approval card, or abort with a reason.
 */
export interface HookAggregateResult {
  decision: "allow" | "deny" | "ask" | undefined;
  /** Reason from the deciding hook (deny > ask > allow precedence).
   *  Surfaced in approval cards / abort messages. */
  reason?: string;
  /** When the deciding hook returned `replace`, the chat-route
   *  swaps this in for the original input/output. Only meaningful
   *  for PreToolUse + PostToolUse. */
  replace?: unknown;
  /** Concatenation of every fired hook's `injectContext`. The
   *  chat-route appends this to the next model turn. */
  injectContext?: string;
  /** Per-hook decisions, useful for audit logging. */
  decisions: Array<{
    hookId: string;
    name: string;
    decision: HookResult["decision"];
    reason?: string;
    durationMs: number;
    error?: string;
  }>;
}

// #HOOK-F2 — dedupe set so a hook that's invalid-but-stored (e.g. a builtin
// with an unknown name, written via direct PATCH) — which validateHook silently
// drops on EVERY event firing — only emits one audit row per process per
// (hookId, event) instead of flooding audit.db on every turn.
const _invalidHookAudited = new Set<string>();

/** #HOOK-F2 — best-effort identity of a stored-but-invalid hook so the dropped
 *  hook is identifiable in the audit row. Pulls id/name/transport-type/builtin
 *  name defensively (the object failed validation, so any field may be absent
 *  or the wrong type). */
function rawHookIdentity(raw: unknown): {
  id: string;
  name: string;
  transportType: string;
  builtinName?: string;
} {
  const h = (raw ?? {}) as Record<string, unknown>;
  const t = (h.transport ?? {}) as Record<string, unknown>;
  return {
    id: typeof h.id === "string" ? h.id : "<unknown>",
    name: typeof h.name === "string" ? h.name : "<unknown>",
    transportType: typeof t.type === "string" ? t.type : "<unknown>",
    builtinName: typeof t.name === "string" ? t.name : undefined,
  };
}

/** #HOOK-F2 — emit a `hook_invalid` audit row (deduped) so an enabled-but-
 *  never-firing hook is observable instead of silently dropped at fire-time. */
function auditInvalidHook(event: HookEvent, raw: unknown): void {
  const ident = rawHookIdentity(raw);
  const dedupeKey = `${ident.id}::${event}`;
  if (_invalidHookAudited.has(dedupeKey)) return;
  _invalidHookAudited.add(dedupeKey);
  void (async () => {
    try {
      await callMcpServer("/api/v1/audit", {
        method: "POST",
        body: {
          action: "hook_invalid",
          target: `hook:${ident.id}`,
          status: "failure",
          metadata: {
            event,
            name: ident.name,
            transport_type: ident.transportType,
            builtin_name: ident.builtinName,
            note: "stored hook failed validation and is silently dropped at fire-time (it appears enabled but never fires)",
          },
        },
      });
    } catch {
      // Best-effort; a dropped hook must not break dispatch.
    }
  })();
}

/** Fetch all hooks for one event from the MCP store. Returns
 *  empty array when no hooks are registered or the fetch fails. */
async function loadHooks(event: HookEvent): Promise<Hook[]> {
  try {
    const data = await callMcpServer<{ hooks?: unknown[] }>(
      `/api/v1/hooks?event=${encodeURIComponent(event)}`,
      { method: "GET" },
    );
    if (!Array.isArray(data?.hooks)) return [];
    const validated: Hook[] = [];
    for (const raw of data.hooks) {
      const h = validateHook(raw);
      if (h) {
        validated.push(h);
      } else {
        // #HOOK-F2 — surface the dropped hook (deduped) instead of swallowing.
        auditInvalidHook(event, raw);
      }
    }
    // Sort by priority asc (low number runs first), tie-break by id.
    validated.sort(
      (a, b) =>
        (a.priority ?? 100) - (b.priority ?? 100) || a.id.localeCompare(b.id),
    );
    return validated;
  } catch (err) {
    // #75 — do NOT swallow a load failure into an empty list. An empty
    // list is indistinguishable from "no hooks registered", which made a
    // transient MCP outage SILENTLY disable EVERY hook (including
    // block-policy hooks like block-production-writes). Propagate so
    // dispatchHooks can fail CLOSED on decisional events.
    throw new HookLoadError(
      err instanceof Error ? err.message : String(err),
    );
  }
}

/** Run one hook through its transport. Returns the parsed result or
 *  an error. Honors the hook's timeout. Never throws. */
async function runHook(
  hook: Hook,
  payload: HookPayload,
): Promise<{ result: HookResult | null; error?: string; durationMs: number }> {
  const startedAt = Date.now();
  const timeoutMs = hook.timeoutMs ?? 5000;
  try {
    if (hook.transport.type === "command") {
      const r = await runCommandHook(hook.transport, payload, timeoutMs);
      return { result: r, durationMs: Date.now() - startedAt };
    }
    if (hook.transport.type === "http") {
      const r = await runHttpHook(hook.transport, payload, timeoutMs);
      return { result: r, durationMs: Date.now() - startedAt };
    }
    if (hook.transport.type === "builtin") {
      const r = await runBuiltinHook(hook.transport, payload, timeoutMs);
      return { result: r, durationMs: Date.now() - startedAt };
    }
    if (hook.transport.type === "plugin") {
      const r = await runPluginHook(hook.transport, payload, timeoutMs);
      return { result: r, durationMs: Date.now() - startedAt };
    }
    // agent transport — reserved for invoking an MCP tool as a hook
    // handler. Not implemented today; plugin-contributed handlers
    // use the `plugin` transport above.
    return {
      result: null,
      error: "agent transport not implemented (reserved for MCP-tool dispatch)",
      durationMs: Date.now() - startedAt,
    };
  } catch (err) {
    return {
      result: null,
      error: err instanceof Error ? err.message : String(err),
      durationMs: Date.now() - startedAt,
    };
  }
}

/** Apply the failure policy when a hook errored / timed out. Returns
 *  the synthesized HookResult the dispatcher should treat as the
 *  hook's output. */
function applyFailurePolicy(hook: Hook, error: string): HookResult {
  const policy = hook.failurePolicy ?? "warn";
  if (policy === "block") {
    return {
      decision: "deny",
      reason: `Hook \`${hook.name}\` failed: ${error}. Blocking on policy.`,
    };
  }
  if (policy === "warn") {
    console.warn(
      `hooks: hook ${hook.name} (${hook.id}) errored, warn-allow:`,
      error,
    );
  }
  return {};
}

/**
 * v0.5.37 — Notification + PermissionRequest hook recursion defense.
 *
 * Caveat documented in v0.5.32: if an operator installs a Notification
 * hook whose handler creates more notifications (e.g. a Slack-mirror
 * hook that doesn't realize the agent re-fires the hook on its own
 * mirror), the chain can recurse infinitely. v0.5.37 ships a simple
 * in-process suppression: per-event, track the dispatch's id (when
 * available) and skip re-dispatch within a short window.
 *
 * Implementation:
 *   - We key by event + payload-id when one is present
 *     (Notification.notificationId, PermissionRequest.requestId).
 *   - First dispatch fires normally.
 *   - Repeat dispatches with the same key within
 *     `RECURSION_SUPPRESS_MS` get suppressed (silent no-op return,
 *     console.warn to surface the recursion to operators reading the
 *     server logs).
 *   - Keys expire after `RECURSION_SUPPRESS_MS` so the map doesn't
 *     grow unbounded.
 *
 * Not a sophisticated defense — operators who genuinely want a hook
 * to fire 10 times in 100ms on different notifications can disable
 * suppression by setting `HOOK_RECURSION_SUPPRESS_MS=0` in env.
 */
const RECURSION_SUPPRESS_MS = Number(
  globalThis.process?.env?.HOOK_RECURSION_SUPPRESS_MS ?? 5000,
);
const RECENT_DISPATCH_KEYS = new Map<string, number>();

function recursionKey(event: HookEvent, payload: HookPayload): string | null {
  if (event === "Notification") {
    const n = (payload as Extract<HookPayload, { event: "Notification" }>).notificationId;
    return n ? `Notification:${n}` : null;
  }
  if (event === "PermissionRequest") {
    const r = (payload as Extract<HookPayload, { event: "PermissionRequest" }>).requestId;
    return r ? `PermissionRequest:${r}` : null;
  }
  return null; // other events not subject to suppression
}

function pruneOldKeys(now: number): void {
  for (const [k, ts] of RECENT_DISPATCH_KEYS) {
    if (now - ts > RECURSION_SUPPRESS_MS) {
      RECENT_DISPATCH_KEYS.delete(k);
    }
  }
}

/**
 * Execute every hook registered for `event`, aggregate results.
 * Returns `decision: undefined` when no hooks fired or all
 * returned no-op.
 */
/** Raised by loadHooks when the hook store can't be reached (vs. a
 *  legitimately empty hook list). dispatchHooks turns this into a
 *  fail-closed decision for decisional events. */
class HookLoadError extends Error {}

/** Events where a hook can `deny` and thereby BLOCK the operation
 *  (tool call, prompt, compaction, turn, subagent spawn). For these,
 *  a hook-store outage must fail CLOSED — proceeding would silently
 *  bypass a block-policy hook. All other events are non-decisional
 *  (post-hoc / notification): there's nothing to enforce, so an outage
 *  is a no-op. Keep in sync with the deny-consuming fire-sites in
 *  app/api/chat/route.ts. */
const DECISIONAL_EVENTS: ReadonlySet<HookEvent> = new Set<HookEvent>([
  "PreToolUse",
  "UserPromptSubmit",
  "PreCompact",
  "RunStart",
  "SubagentStart",
]);

/** Operator escape hatch: when the hook store is briefly unreachable,
 *  prefer availability over the block-policy guarantee. Off by default
 *  (we fail closed). Set GUARDIAN_HOOKS_FAIL_OPEN=true to restore the
 *  pre-#75 behavior of proceeding without hooks on a load failure. */
function hooksFailOpen(): boolean {
  return (process.env.GUARDIAN_HOOKS_FAIL_OPEN ?? "").toLowerCase() === "true";
}

/** #75 — decide what to do when the hook store can't be loaded. */
export function resolveHookLoadFailure(
  event: HookEvent,
  err: unknown,
): HookAggregateResult {
  const cause = err instanceof Error ? err.message : String(err);
  if (hooksFailOpen()) {
    console.warn(
      `hooks: load failed for ${event}; GUARDIAN_HOOKS_FAIL_OPEN=true → ` +
        `proceeding WITHOUT hooks (cause: ${cause})`,
    );
    return { decision: undefined, decisions: [] };
  }
  if (DECISIONAL_EVENTS.has(event)) {
    console.error(
      `hooks: load failed for ${event}; failing CLOSED (deny) so a ` +
        `block-policy hook cannot be silently bypassed. Set ` +
        `GUARDIAN_HOOKS_FAIL_OPEN=true to override. cause: ${cause}`,
    );
    return {
      decision: "deny",
      reason:
        "Hook policy store is unreachable — failing closed so a " +
        "block-policy hook isn't silently bypassed. Retry shortly (or set " +
        "GUARDIAN_HOOKS_FAIL_OPEN=true to proceed without hooks).",
      decisions: [],
    };
  }
  // Non-decisional event (post-hoc / notification): nothing to enforce.
  console.warn(
    `hooks: load failed for non-decisional ${event}; nothing to enforce, ` +
      `proceeding (cause: ${cause})`,
  );
  return { decision: undefined, decisions: [] };
}

export async function dispatchHooks(
  event: HookEvent,
  payload: HookPayload,
): Promise<HookAggregateResult> {
  if (!HOOK_EVENTS.includes(event)) {
    // Defensive: an unknown event name. Treat as no hooks.
    return { decision: undefined, decisions: [] };
  }

  // v0.5.37 recursion suppression for Notification + PermissionRequest.
  if (RECURSION_SUPPRESS_MS > 0) {
    const key = recursionKey(event, payload);
    if (key !== null) {
      const now = Date.now();
      pruneOldKeys(now);
      const last = RECENT_DISPATCH_KEYS.get(key);
      if (last !== undefined && now - last < RECURSION_SUPPRESS_MS) {
        console.warn(
          `hooks: suppressing recursive dispatch of ${event} for ${key} ` +
            `(last fired ${now - last}ms ago; threshold ${RECURSION_SUPPRESS_MS}ms). ` +
            `If this isn't recursion, set HOOK_RECURSION_SUPPRESS_MS=0 to disable.`,
        );
        return { decision: undefined, decisions: [] };
      }
      RECENT_DISPATCH_KEYS.set(key, now);
    }
  }
  let hooks: Hook[];
  try {
    hooks = await loadHooks(event);
  } catch (err) {
    // #75 — hook store unreachable. Fail CLOSED for decisional events
    // (don't silently bypass a block-policy hook); no-op for the rest.
    return resolveHookLoadFailure(event, err);
  }
  // Filter by matcher BEFORE running so we don't waste subprocess
  // spawns on hooks that don't match.
  const eligible = hooks.filter((h) => matchesHook(h, payload));

  let decision: HookAggregateResult["decision"] = undefined;
  let reason: string | undefined;
  let replace: unknown;
  const injectContextChunks: string[] = [];
  const decisions: HookAggregateResult["decisions"] = [];

  for (const hook of eligible) {
    const { result, error, durationMs } = await runHook(hook, payload);
    const effective = result ?? (error ? applyFailurePolicy(hook, error) : {});
    decisions.push({
      hookId: hook.id,
      name: hook.name,
      decision: effective.decision,
      reason: effective.reason,
      durationMs,
      error,
    });
    if (effective.injectContext) {
      injectContextChunks.push(effective.injectContext);
    }
    // Decision precedence: deny > ask > allow > undefined.
    if (effective.decision === "deny") {
      decision = "deny";
      reason = effective.reason;
      replace = effective.replace;
      break; // Short-circuit on deny; subsequent hooks would
      // be wasted work AND can't override a deny.
    }
    // Past this point a `deny` would have broken out; TS narrows
    // `decision` to "allow" | "ask" | undefined, so the redundant
    // !== "deny" checks were rejected.
    if (effective.decision === "ask") {
      decision = "ask";
      reason = effective.reason ?? reason;
      replace = effective.replace ?? replace;
      // Don't break — let injectContext-only hooks behind us still run.
    }
    if (effective.decision === "allow" && decision !== "ask") {
      decision = "allow";
      reason = effective.reason ?? reason;
      replace = effective.replace ?? replace;
    }
  }

  return {
    decision,
    reason,
    replace,
    injectContext: injectContextChunks.join("\n").trim() || undefined,
    decisions,
  };
}

// ─── Command transport ──────────────────────────────────────────────

async function runCommandHook(
  transport: Extract<Hook["transport"], { type: "command" }>,
  payload: HookPayload,
  timeoutMs: number,
): Promise<HookResult | null> {
  // Lazy import — `child_process` isn't available on the Edge
  // runtime. Guardian's chat route uses Node runtime (default).
  const { spawn } = await import("node:child_process");
  // #HOOK-F14 — resolve `secret:<ref>` env values via the MCP
  // SecretStore (audited) BEFORE entering the Promise executor (which
  // is synchronous and can't await). Fail-closed: an unresolvable ref
  // contributes nothing rather than leaking a raw env var.
  const resolvedEnv = await resolveSecretEnv(transport.env ?? {});
  return new Promise((resolve, reject) => {
    const env = { ...process.env, ...resolvedEnv };
    const proc = spawn(transport.command, {
      shell: true,
      cwd: transport.cwd,
      env,
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let settled = false;
    const settle = (fn: () => void) => {
      if (settled) return;
      settled = true;
      fn();
    };
    const timer = setTimeout(() => {
      proc.kill("SIGKILL");
      settle(() =>
        reject(new Error(`hook command timed out after ${timeoutMs}ms`)),
      );
    }, timeoutMs);
    proc.stdout.on("data", (b) => (stdout += b.toString()));
    proc.stderr.on("data", (b) => (stderr += b.toString()));
    proc.on("error", (err) => {
      clearTimeout(timer);
      settle(() => reject(err));
    });
    proc.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        settle(() =>
          reject(
            new Error(
              `hook command exited ${code}: ${stderr.slice(0, 200)}`,
            ),
          ),
        );
        return;
      }
      // Empty stdout = no-op (treat as {}). Otherwise parse JSON.
      const trimmed = stdout.trim();
      if (!trimmed) {
        settle(() => resolve({}));
        return;
      }
      try {
        settle(() => resolve(JSON.parse(trimmed) as HookResult));
      } catch (err) {
        settle(() =>
          reject(
            new Error(
              `hook stdout was not valid JSON: ${err instanceof Error ? err.message : err}`,
            ),
          ),
        );
      }
    });
    proc.stdin.write(JSON.stringify(payload));
    proc.stdin.end();
  });
}

// ─── HTTP transport ─────────────────────────────────────────────────

async function runHttpHook(
  transport: Extract<Hook["transport"], { type: "http" }>,
  payload: HookPayload,
  timeoutMs: number,
): Promise<HookResult | null> {
  // #HOOK-F14 — resolve `secret:<ref>` header values via the MCP
  // SecretStore (audited), fail-closed on a miss.
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(await resolveSecretEnv(transport.headers ?? {})),
  };
  const resp = await fetch(transport.url, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`hook HTTP ${resp.status}: ${text.slice(0, 200)}`);
  }
  // Empty body is no-op.
  const text = await resp.text();
  if (!text.trim()) return {};
  try {
    return JSON.parse(text) as HookResult;
  } catch (err) {
    throw new Error(
      `hook HTTP body was not valid JSON: ${err instanceof Error ? err.message : err}`,
    );
  }
}

// ─── Builtin transport ──────────────────────────────────────────────

/**
 * Dispatch a builtin hook by name through the registry in
 * `lib/hook-builtins/`. Builtins run in-process — no subprocess spawn,
 * no HTTP round-trip — so we still honor the hook's `timeoutMs` via an
 * AbortController the spec receives in its `options`. Specs that ignore
 * the signal are still bounded by Promise.race against the timer.
 *
 * Defense-in-depth re-validation: even though `validateHook` re-validated
 * the config at load time, we re-check here before dispatch so a spec
 * whose schema changed between releases doesn't silently run with stale
 * fields. The cost is microseconds; the protection is real.
 */
async function runBuiltinHook(
  transport: Extract<Hook["transport"], { type: "builtin" }>,
  payload: HookPayload,
  timeoutMs: number,
): Promise<HookResult | null> {
  const spec = getBuiltinHook(transport.name);
  if (!spec) {
    throw new Error(
      `builtin '${transport.name}' is not registered in this image`,
    );
  }
  const validated = spec.validateConfig(transport.config);
  if (!validated.ok) {
    throw new Error(
      `builtin '${transport.name}' config invalid: ${validated.error}`,
    );
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const handlePromise = spec.handle(payload, validated.config, {
      signal: controller.signal,
      timeoutMs,
    });
    // Race against the timer in case the spec ignores the signal.
    const timeoutPromise = new Promise<HookResult | null>((_, reject) => {
      controller.signal.addEventListener(
        "abort",
        () =>
          reject(
            new Error(`builtin '${transport.name}' timed out after ${timeoutMs}ms`),
          ),
        { once: true },
      );
    });
    return await Promise.race([handlePromise, timeoutPromise]);
  } finally {
    clearTimeout(timer);
  }
}

// ─── Plugin-transport runner (v0.5.48) ──────────────────────────────

/**
 * Invoke a plugin-contributed handler via the MCP-side bridge.
 *
 * Plugin handlers live in Python (entry-point `guardian.hooks`). The
 * hook-runner is TypeScript. We bridge by HTTP: POST the payload + the
 * operator's config to `/api/v1/plugin-hooks/{name}/invoke` on the
 * MCP, get back `{ok, result, duration_ms, ...}`, and translate that
 * into the standard HookResult shape.
 *
 * Wire: agent's internal loopback to MCP runs over the same env vars
 * the rest of `lib/mcp-proxy.ts` uses (MCP_URL + MCP_TOKEN). We can't
 * reuse `mcp-proxy.ts` directly because it's designed for the agent →
 * MCP request-response of /api/agent/* surface; the hook bridge is a
 * different shape (raw POST with a bearer header).
 *
 * Timeout: the agent passes `timeoutMs / 1000` as the MCP's
 * `timeout_s` and ALSO arms an AbortController on the fetch so a hung
 * connection doesn't outlive the hook's own bound.
 *
 * Result translation:
 *   - ok=true, result=null   → null (no-op, same as not registering)
 *   - ok=true, result=dict   → dict cast to HookResult
 *   - ok=false               → throw with the error string; the
 *                              outer runner converts that into the
 *                              failure-policy response.
 */
async function runPluginHook(
  transport: Extract<Hook["transport"], { type: "plugin" }>,
  payload: HookPayload,
  timeoutMs: number,
): Promise<HookResult | null> {
  const mcpUrl = process.env.MCP_URL?.trim();
  const mcpToken = process.env.MCP_TOKEN?.trim();
  if (!mcpUrl || !mcpToken) {
    throw new Error(
      "plugin hook transport requires MCP_URL and MCP_TOKEN env vars",
    );
  }
  // deriveMcpBaseUrl extracts the origin (e.g. http://localhost:8080)
  // from MCP_URL=http://localhost:8080/api/v1/stream/mcp. We add the
  // /api/v1 prefix ourselves so we don't depend on MCP_URL's path.
  const origin = deriveMcpBaseUrl(mcpUrl);
  if (!origin) throw new Error(`bad MCP_URL: ${mcpUrl}`);
  const url = `${origin}/api/v1/plugin-hooks/${encodeURIComponent(transport.handlerName)}/invoke`;
  const timeoutS = transport.timeoutS ?? Math.max(1, Math.floor(timeoutMs / 1000));

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${mcpToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        payload,
        config: transport.config ?? {},
        timeout_s: timeoutS,
      }),
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(
        `plugin '${transport.handlerName}' fetch aborted after ${timeoutMs}ms`,
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  // Parse body even on non-2xx — MCP returns structured errors.
  let body: {
    ok?: boolean;
    result?: HookResult | null;
    error?: string;
    duration_ms?: number;
    handler?: string;
  };
  try {
    body = await resp.json();
  } catch {
    throw new Error(
      `plugin '${transport.handlerName}' returned non-JSON response (HTTP ${resp.status})`,
    );
  }

  if (!body.ok) {
    throw new Error(
      body.error || `plugin '${transport.handlerName}' invoke failed (HTTP ${resp.status})`,
    );
  }
  return body.result ?? null;
}

// ─── Secret resolution ──────────────────────────────────────────────

/**
 * Resolve `secret:<ref>` values in env / headers maps. A `secret:<ref>`
 * is resolved through the MCP SecretStore (an AUDITED read — see
 * #HOOK-F14 / api/secrets.py) instead of the agent's raw process.env.
 * Values that don't start with `secret:` are passed through verbatim.
 *
 * #HOOK-F14 — this previously read `secret:<X>` straight out of
 * `process.env[X]`, an UNMANAGED env var that was never minted or
 * tracked by the SecretStore and left no audit trail. That widened
 * the trust boundary the SecretStore exists to enforce. We now POST
 * the ref to `/api/v1/secrets/resolve` (MCP_TOKEN bearer; the same
 * principal already trusted to read instance/provider secrets) and
 * use the store's resolved value.
 *
 * Fail-closed: if the ref can't be resolved from the store (missing
 * secret, malformed path, MCP unreachable), we contribute NOTHING for
 * that key (drop it) and warn — rather than leaking an unmanaged env
 * var. This matches the fail-closed posture of v0.2.52/59. A hook that
 * genuinely needs a non-store value should use a literal, not a
 * `secret:` ref.
 */
export async function resolveSecretEnv(
  raw: Record<string, string>,
): Promise<Record<string, string>> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(raw)) {
    if (typeof v === "string" && v.startsWith("secret:")) {
      const ref = v.slice("secret:".length);
      const resolved = await resolveSecretRef(ref);
      if (resolved === null) {
        // Fail-closed: drop the key. The spawned shell / outbound
        // request sees no value for it (better than a stale/unmanaged
        // env var leaking through).
        console.warn(
          `[hook-runner] secret ref ${JSON.stringify(
            ref,
          )} did not resolve via the SecretStore; dropping (fail-closed)`,
        );
        continue;
      }
      out[k] = resolved;
    } else {
      out[k] = v;
    }
  }
  return out;
}

/**
 * Resolve one `<ref>` (the part after `secret:`) via the MCP
 * SecretStore. Returns the value on success, or null on any failure
 * (missing secret, bad ref, MCP unreachable). NEVER throws — callers
 * fail-closed on null. The value is never logged here.
 */
async function resolveSecretRef(ref: string): Promise<string | null> {
  try {
    const body = await callMcpServer<{ value?: string }>(
      "/api/v1/secrets/resolve",
      { method: "POST", body: { ref } },
    );
    return typeof body.value === "string" ? body.value : null;
  } catch {
    // callMcpServer throws on non-2xx (e.g. 404 not_found / 400 bad_ref)
    // and on transport errors. All of those are fail-closed cases.
    return null;
  }
}
