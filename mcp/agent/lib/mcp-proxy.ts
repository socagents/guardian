/**
 * Shared helpers for /api/agent/* proxy routes that forward to the
 * embedded MCP at /api/v1/* with bearer auth attached server-side.
 *
 * Pattern: every proxy route has the same boilerplate (resolve
 * MCP_URL + token, forward the request, pass response through).
 * This module centralizes it so each route file is just 5 lines.
 */

import { NextResponse } from 'next/server';

import { deriveMcpBaseUrl, getEffectiveRuntimeConfig } from '@/lib/runtime-config';

export interface McpResolved {
  base: string;
  token: string;
}

/**
 * Resolve the MCP base URL + bearer token. Returns either the
 * resolved values or a NextResponse error to return immediately.
 */
export async function resolveMcp(): Promise<McpResolved | NextResponse> {
  const config = await getEffectiveRuntimeConfig();
  const mcpToken =
    (config.MCP_TOKEN || '').trim() || process.env.MCP_TOKEN?.trim() || '';
  if (!mcpToken) {
    return NextResponse.json(
      { error: 'MCP_TOKEN not configured' },
      { status: 503 },
    );
  }
  const mcpUrl =
    (config.MCP_URL || '').trim() ||
    process.env.MCP_URL?.trim() ||
    // v0.6.48 — fallback URL updated to match v0.1.30+ architecture.
    // Pre-v0.1.30 the MCP ran as a separate `guardian-mcp` container
    // on the compose network; v0.1.30 collapsed it into a subprocess
    // inside `guardian-agent` listening on localhost:8080. The old
    // `http://guardian-mcp:8080/...` fallback pointed at a service
    // that's been retired for ~5 releases — if it ever fired in
    // production (both config.MCP_URL AND process.env.MCP_URL must
    // be unset, which is rare since the installer always sets the env
    // var), the request would fail with EAI_AGAIN: guardian-mcp.
    // entrypoint.sh in v0.4.0+ also flips the scheme to https:
    // when TLS_CERT_PEM is set; but the literal default below stays
    // http: because that's what the compose env sets.
    'http://localhost:8080/api/v1/stream/mcp';
  const base = deriveMcpBaseUrl(mcpUrl);
  if (!base) {
    return NextResponse.json({ error: 'bad MCP URL' }, { status: 500 });
  }
  return { base, token: mcpToken };
}

/**
 * Forward a request to the MCP, preserving query string + body.
 * `path` is the /api/v1/* portion (e.g. "/api/v1/audit" or
 * "/api/v1/jobs/foo/run"). Returns a NextResponse.
 */
export async function proxyToMcp(
  request: Request,
  path: string,
  options: { method?: string; body?: string | null } = {},
): Promise<NextResponse> {
  const r = await resolveMcp();
  if (r instanceof NextResponse) return r;

  const url = new URL(request.url);
  const upstreamUrl = `${r.base}${path}${url.search}`;
  const method = options.method ?? request.method;

  // For non-GET methods, forward the request body unless an explicit
  // body is given. For GETs we don't propagate body (HTTP semantics).
  let body: string | null = null;
  if (options.body !== undefined) {
    body = options.body;
  } else if (method !== 'GET' && method !== 'HEAD') {
    try {
      body = await request.text();
    } catch {
      body = null;
    }
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${r.token}`,
  };
  const ct = request.headers.get('content-type');
  if (ct && body !== null) {
    headers['Content-Type'] = ct;
  } else if (body !== null) {
    headers['Content-Type'] = 'application/json';
  }
  // #API-F18/OBS-F8 — forward the principal the middleware attributed
  // (X-Guardian-Actor) + the trigger so the MCP-side audit row records WHO
  // made the change (apikey:<id> | user:operator) instead of a hardcoded
  // user:operator. Both are set on the incoming request by middleware.ts.
  const fwdActor = request.headers.get('x-guardian-actor');
  if (fwdActor) headers['X-Guardian-Actor'] = fwdActor;
  const fwdTrigger = request.headers.get('x-guardian-trigger');
  if (fwdTrigger) headers['X-Guardian-Trigger'] = fwdTrigger;

  try {
    const resp = await fetch(upstreamUrl, {
      method,
      headers,
      body: body !== null ? body : undefined,
      signal: AbortSignal.timeout(15000),
    });
    const text = await resp.text();
    return new NextResponse(text, {
      status: resp.status,
      headers: {
        'Content-Type':
          resp.headers.get('content-type') ?? 'application/json',
      },
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'proxy fetch failed' },
      { status: 502 },
    );
  }
}

/**
 * Server-initiated REST call to the embedded MCP. Use this when an
 * agent route needs to talk to the MCP without forwarding an
 * inbound request — for example, /api/chat creating + appending to
 * a session as a side effect of a model turn.
 *
 * Returns the parsed JSON response on 2xx, throws on non-2xx or
 * network failure. Callers should treat this as best-effort and
 * decide per-call whether to fail hard or continue.
 *
 * Differences from `proxyToMcp`:
 *   - No inbound Request to forward; you supply method + body
 *   - Returns parsed JSON (callers don't need to re-parse)
 *   - Throws instead of returning a NextResponse (chat-route style)
 */
export async function callMcpServer<T = unknown>(
  path: string,
  init: {
    method?: string;
    body?: unknown;
    timeoutMs?: number;
    /**
     * Custom headers merged into the request. Reserved names
     * (Authorization, Content-Type) take precedence over extras
     * to keep the bearer + JSON contract intact. Used by the
     * chat route to forward X-Guardian-Trigger so MCP-side audit
     * rows inherit the trigger tag.
     */
    headers?: Record<string, string>;
  } = {},
): Promise<T> {
  const r = await resolveMcp();
  if (r instanceof NextResponse) {
    // resolveMcp returns NextResponse only on missing config — surface
    // that as a thrown error so chat-route can catch + log + continue.
    const detail = await r.json().catch(() => ({}));
    throw new Error(
      `MCP unavailable: ${(detail as { error?: string })?.error ?? 'misconfigured'}`,
    );
  }
  const { base, token } = r;
  const method = init.method ?? 'GET';
  const body =
    init.body === undefined
      ? undefined
      : typeof init.body === 'string'
        ? init.body
        : JSON.stringify(init.body);
  // Spread extras first so reserved names cleanly override.
  const headers: Record<string, string> = { ...(init.headers ?? {}) };
  headers['Authorization'] = `Bearer ${token}`;
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  const resp = await fetch(`${base}${path}`, {
    method,
    headers,
    body,
    signal: AbortSignal.timeout(init.timeoutMs ?? 10000),
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`MCP ${method} ${path} → ${resp.status} ${text}`);
  }
  return (await resp.json()) as T;
}
