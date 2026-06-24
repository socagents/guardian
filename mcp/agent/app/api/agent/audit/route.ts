/**
 * Audit query proxy — used by the SparkActivityTimeline component.
 */

import { NextResponse } from 'next/server';

import { deriveMcpBaseUrl, getEffectiveRuntimeConfig } from '@/lib/runtime-config';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const config = await getEffectiveRuntimeConfig();
  const mcpToken =
    (config.MCP_TOKEN || '').trim() || process.env.MCP_TOKEN?.trim() || '';
  if (!mcpToken)
    return NextResponse.json({ error: 'MCP_TOKEN not configured' }, { status: 503 });
  // #API-F19 — getEffectiveRuntimeConfig() always returns a non-empty
  // MCP_URL (defaults to localhost:8080 in runtime-config.ts), so the old
  // hardcoded `guardian-mcp:8080` third fallback was dead code that pinned a
  // stale compose service name. Resolve from config (env still wins inside
  // getEffectiveRuntimeConfig for this bundle-internal key).
  const mcpUrl = (config.MCP_URL || '').trim() || process.env.MCP_URL?.trim() || '';
  const base = mcpUrl ? deriveMcpBaseUrl(mcpUrl) : '';
  if (!base)
    return NextResponse.json({ error: 'bad MCP URL' }, { status: 500 });
  const url = new URL(request.url);
  try {
    const r = await fetch(`${base}/api/v1/audit${url.search}`, {
      headers: { Authorization: `Bearer ${mcpToken}` },
      signal: AbortSignal.timeout(10000),
    });
    const text = await r.text();
    return new NextResponse(text, {
      status: r.status,
      headers: {
        'Content-Type':
          r.headers.get('content-type') ?? 'application/json',
      },
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'fetch failed' },
      { status: 502 },
    );
  }
}
