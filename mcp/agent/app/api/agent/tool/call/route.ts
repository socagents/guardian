/**
 * Direct tool invocation — v0.5.74 (issue #47).
 *
 * Bypasses the LLM. Operators type `^toolname arg=val` in the chat
 * input; the chat hook detects the `^` prefix, parses args, and POSTs
 * the parsed shape here instead of `/api/chat`. The response is the
 * raw tool output (or an error) rendered as a JSON code block in the
 * chat transcript.
 *
 * Why a separate route from /api/chat:
 *   - /api/chat is LLM-focused (provider config, streaming SSE, system
 *     prompt, planner). Adding a "no LLM, just invoke this tool" path
 *     would tangle two flows.
 *   - This route MUST work without provider config (the whole point —
 *     gives operators a deterministic test surface on a fresh install
 *     before they've configured Gemini/Vertex).
 *
 * Wire flow:
 *   1. Resolve MCP base + token (same helper /api/agent/* routes use)
 *   2. Open a JSON-RPC session — initialize + notifications/initialized
 *   3. (optional) tools/list to resolve bare names like
 *      "get_cases_and_issues" → "xdr_get_cases_and_issues"
 *   4. tools/call with resolved name + arguments
 *   5. Parse SSE response; return JSON to the caller
 *
 * Auth model:
 *   - This route doesn't do explicit cookie validation because the only
 *     way a browser fetch reaches it is from inside the AuthGate'd UI
 *     (same as every other /api/agent/* route). The MCP_TOKEN attached
 *     to upstream calls is server-side; never reaches the browser.
 *   - NO provider check. NO LLM call. Just dispatch.
 */

import { NextResponse } from 'next/server';
import { resolveMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

interface ToolCallRequest {
  name: string;
  arguments: Record<string, unknown>;
}

interface ToolCallResponse {
  ok: boolean;
  /** The fully-qualified tool name the MCP dispatched. May differ
   *  from what the operator typed if bare-name resolution kicked in
   *  (e.g. "get_cases_and_issues" → "xdr_get_cases_and_issues"). */
  resolved_name: string;
  /** Raw tool result content (the MCP's tools/call result.content[0].text
   *  or the structured payload it returned). String when the tool
   *  returned a single text content; object when structured. */
  result?: unknown;
  /** Present when ok=false. Operator-facing error message. */
  error?: string;
  /** Wall-clock latency including the JSON-RPC handshake. */
  duration_ms: number;
}

/** Build the common MCP headers, conditionally forwarding the
 *  X-Guardian-Actor the Next.js middleware stamped on the inbound request.
 *  #XSOAR-F9/INV-F15 — without forwarding the actor header, the MCP's
 *  TriggerContextMiddleware has nothing to set the actor contextvar from, so
 *  connector_loader falls back to "agent" and ^tool direct-dispatch rows are
 *  indistinguishable from a model-driven call at the actor dimension. */
function mcpHeaders(
  token: string,
  actor: string | null,
  extra: Record<string, string> = {},
): Record<string, string> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
    Accept: 'application/json, text/event-stream',
    ...extra,
  };
  if (actor) headers['X-Guardian-Actor'] = actor;
  return headers;
}

/** Open a JSON-RPC session against the embedded MCP. Returns the session
 *  ID needed for subsequent tools/call etc. */
async function openMcpSession(
  base: string,
  token: string,
  actor: string | null,
): Promise<string> {
  const initBody = JSON.stringify({
    jsonrpc: '2.0',
    id: 1,
    method: 'initialize',
    params: {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'guardian-agent-ui-tool-call', version: '1.0' },
    },
  });
  const resp = await fetch(`${base}/api/v1/stream/mcp`, {
    method: 'POST',
    headers: mcpHeaders(token, actor),
    body: initBody,
    signal: AbortSignal.timeout(10_000),
  });
  if (!resp.ok) {
    throw new Error(
      `MCP initialize failed: ${resp.status} ${await resp.text().catch(() => '')}`,
    );
  }
  const sessionId = resp.headers.get('mcp-session-id') ?? '';
  if (!sessionId) {
    throw new Error('MCP initialize returned no mcp-session-id header');
  }
  // Drain the SSE response body so the session is fully set up before
  // we send the initialized notification. Without this, the MCP may
  // race against the next request.
  try {
    await resp.text();
  } catch {
    // ignore — body drain failure shouldn't block the session
  }
  // Send the initialized notification (no response expected).
  await fetch(`${base}/api/v1/stream/mcp`, {
    method: 'POST',
    headers: mcpHeaders(token, actor, { 'mcp-session-id': sessionId }),
    body: JSON.stringify({
      jsonrpc: '2.0',
      method: 'notifications/initialized',
      params: {},
    }),
    signal: AbortSignal.timeout(5_000),
  }).catch(() => {
    // Notifications don't return responses; a network blip here is
    // recoverable on the next request. Don't fail the whole call.
  });
  return sessionId;
}

/** Parse SSE response body looking for the JSON-RPC result frame.
 *  Streamable-HTTP MCP responses for a single request look like:
 *
 *    event: message
 *    data: {"jsonrpc":"2.0","id":N,"result":{...}}
 *
 *  We just grab the first `data:` line that parses as JSON-RPC. */
function parseFirstJsonRpcFrame(sseBody: string): {
  ok: boolean;
  payload?: unknown;
  error?: { code: number; message: string };
} {
  for (const block of sseBody.split('\n\n')) {
    for (const line of block.split('\n')) {
      if (!line.startsWith('data: ')) continue;
      const raw = line.slice(6);
      try {
        const parsed = JSON.parse(raw) as {
          jsonrpc?: string;
          id?: unknown;
          result?: unknown;
          error?: { code: number; message: string };
        };
        if (parsed.error) return { ok: false, error: parsed.error };
        if (parsed.result !== undefined) return { ok: true, payload: parsed.result };
      } catch {
        // not JSON; ignore — could be a heartbeat
      }
    }
  }
  return { ok: false, error: { code: -32000, message: 'No JSON-RPC frame in response' } };
}

/** Resolve a bare tool name (e.g. "get_cases_and_issues") against the
 *  MCP's registered tool list. Returns the first match — if multiple
 *  tools share the bare-name suffix, an error is returned naming the
 *  ambiguity so the operator can disambiguate. */
async function resolveBareName(
  base: string,
  token: string,
  sessionId: string,
  bareName: string,
  actor: string | null,
): Promise<{ resolved?: string; error?: string }> {
  const resp = await fetch(`${base}/api/v1/stream/mcp`, {
    method: 'POST',
    headers: mcpHeaders(token, actor, { 'mcp-session-id': sessionId }),
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 99,
      method: 'tools/list',
      params: {},
    }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!resp.ok) {
    return { error: `tools/list failed: ${resp.status}` };
  }
  const text = await resp.text();
  const frame = parseFirstJsonRpcFrame(text);
  if (!frame.ok || !frame.payload) {
    return { error: 'could not list tools to resolve bare name' };
  }
  const tools =
    (frame.payload as { tools?: Array<{ name: string }> })?.tools ?? [];

  // Exact match wins.
  const exact = tools.find((t) => t.name === bareName);
  if (exact) return { resolved: exact.name };

  // Suffix match: any tool whose name ends with ".<bare>" (connector-
  // namespaced) or "_<bare>" (functionPrefix style).
  const matches = tools.filter(
    (t) => t.name === bareName ||
      t.name.endsWith(`.${bareName}`) ||
      t.name.endsWith(`_${bareName}`),
  );
  if (matches.length === 0) {
    return {
      error: `no tool matched "${bareName}"; try the fully-qualified name (e.g. "xsoar.get_incident" or "xsoar_get_incident")`,
    };
  }
  if (matches.length > 1) {
    return {
      error: `ambiguous tool name "${bareName}" — matched: ${matches
        .map((m) => m.name)
        .join(', ')}. Use a fully-qualified name.`,
    };
  }
  return { resolved: matches[0].name };
}

export async function POST(request: Request): Promise<NextResponse<ToolCallResponse>> {
  const start = Date.now();

  let body: ToolCallRequest;
  try {
    body = (await request.json()) as ToolCallRequest;
  } catch {
    return NextResponse.json(
      {
        ok: false,
        resolved_name: '',
        error: 'request body must be JSON',
        duration_ms: Date.now() - start,
      },
      { status: 400 },
    );
  }
  if (!body.name || typeof body.name !== 'string') {
    return NextResponse.json(
      {
        ok: false,
        resolved_name: '',
        error: 'name is required (string)',
        duration_ms: Date.now() - start,
      },
      { status: 400 },
    );
  }
  const args =
    typeof body.arguments === 'object' && body.arguments !== null
      ? (body.arguments as Record<string, unknown>)
      : {};

  const r = await resolveMcp();
  if (r instanceof NextResponse) {
    return r as NextResponse<ToolCallResponse>;
  }
  const { base, token } = r;

  // #XSOAR-F9/INV-F15 — the Next.js middleware stamps the authenticated
  // principal on x-guardian-actor before this route runs. Forward it to the
  // MCP on every fetch so the direct-dispatch tool_call rows attribute to the
  // real operator/principal instead of falling back to "agent".
  const actor = request.headers.get('x-guardian-actor');

  let sessionId: string;
  try {
    sessionId = await openMcpSession(base, token, actor);
  } catch (err) {
    return NextResponse.json(
      {
        ok: false,
        resolved_name: body.name,
        error: err instanceof Error ? err.message : 'session open failed',
        duration_ms: Date.now() - start,
      },
      { status: 502 },
    );
  }

  // Resolve the tool name. If the operator typed a fully-qualified
  // name (contains "." or "_" prefix that matches), exact match works
  // first try in resolveBareName.
  let resolvedName = body.name;
  const resolution = await resolveBareName(base, token, sessionId, body.name, actor);
  if (resolution.error) {
    return NextResponse.json(
      {
        ok: false,
        resolved_name: body.name,
        error: resolution.error,
        duration_ms: Date.now() - start,
      },
      { status: 404 },
    );
  }
  resolvedName = resolution.resolved!;

  // Issue the actual tools/call.
  const callResp = await fetch(`${base}/api/v1/stream/mcp`, {
    method: 'POST',
    headers: mcpHeaders(token, actor, {
      'mcp-session-id': sessionId,
      // #CHAT-F24/OBS-F3/API-F12 — mark this as an operator-typed ^tool
      // direct dispatch so the MCP-side tool_call audit row is
      // distinguishable from a model-driven call (which carries the
      // chat/job trigger). TriggerContextMiddleware reads this header.
      // #XSOAR-F9/INV-F15 — mcpHeaders also forwards X-Guardian-Actor so the
      // row attributes to the real principal, not the "agent" fallback.
      'X-Guardian-Trigger': 'operator:direct',
    }),
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 100,
      method: 'tools/call',
      params: { name: resolvedName, arguments: args },
    }),
    // Tool calls can take a while (XQL polling defaults to 40 × 3s = 2 min).
    // #CDW-F1 — raised 150s → 300s so a full deep_research run (advertised
    // 1–3 min, occasionally longer) returns its complete deliverable via the
    // ^tool path instead of hitting a proxy timeout mid-run. deep_research is
    // the only tool that runs past ~2 min; the connector container keeps its
    // own internal polling caps so this is purely the proxy ceiling.
    signal: AbortSignal.timeout(300_000),
  });
  if (!callResp.ok) {
    return NextResponse.json(
      {
        ok: false,
        resolved_name: resolvedName,
        error: `tools/call HTTP ${callResp.status}: ${await callResp.text().catch(() => '')}`,
        duration_ms: Date.now() - start,
      },
      { status: 502 },
    );
  }
  const sseText = await callResp.text();
  const frame = parseFirstJsonRpcFrame(sseText);
  if (!frame.ok) {
    return NextResponse.json(
      {
        ok: false,
        resolved_name: resolvedName,
        error: frame.error?.message ?? 'tools/call returned no frame',
        duration_ms: Date.now() - start,
      },
      { status: 502 },
    );
  }

  // tools/call wraps the actual result in `{content: [{type, text}], isError?}`.
  // Try to surface a useful shape: parse the first text content as JSON
  // if possible (most Guardian tools return JSON strings); fall back to
  // the raw text. Carry isError through to ok=false when set.
  const payload = frame.payload as {
    content?: Array<{ type: string; text?: string }>;
    isError?: boolean;
    structuredContent?: unknown;
  };
  const isError = Boolean(payload?.isError);
  let result: unknown = payload;
  if (payload?.structuredContent !== undefined) {
    result = payload.structuredContent;
  } else if (Array.isArray(payload?.content) && payload.content[0]?.text) {
    const text = payload.content[0].text;
    try {
      result = JSON.parse(text);
    } catch {
      result = text;
    }
  }

  return NextResponse.json({
    ok: !isError,
    resolved_name: resolvedName,
    result,
    error: isError
      ? typeof result === 'string'
        ? result
        : JSON.stringify(result)
      : undefined,
    duration_ms: Date.now() - start,
  });
}
