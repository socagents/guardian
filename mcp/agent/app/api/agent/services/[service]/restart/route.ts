/**
 * Service-restart proxy (#PLAT-F19).
 *
 * POST /api/agent/services/{service}/restart
 *   → POST {updater}/api/v1/services/{service}/restart  (Bearer MCP_TOKEN)
 *
 * The updater's only MANAGED_SERVICES entry is `guardian-agent` (it runs
 * `docker compose restart <service>`); the other stack entries shown in
 * the Settings slide-over (`guardian-mcp (embedded)`, `sqlite (embedded)`)
 * are in-process, not compose services, and are not restartable. We
 * allow-list to avoid proxying arbitrary service names through to the
 * updater. Same MCP_TOKEN proxying pattern as /api/agent/digests.
 */

import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

// Only services the updater actually manages (MANAGED_SERVICES in
// updater/src/main.py). Restarting guardian-agent briefly disconnects
// the operator's UI session — the client confirms before calling this.
const RESTARTABLE = new Set(['guardian-agent']);

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ service: string }> },
) {
  const { service } = await params;
  if (!RESTARTABLE.has(service)) {
    return NextResponse.json(
      { error: `service '${service}' is not restartable`, code: 'not_managed' },
      { status: 400 },
    );
  }

  const updaterUrl =
    process.env.GUARDIAN_UPDATER_URL?.replace(/\/$/, '') ||
    'http://guardian-updater:8090';
  const mcpToken = process.env.MCP_TOKEN || '';

  try {
    const r = await fetch(`${updaterUrl}/api/v1/services/${service}/restart`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${mcpToken}`,
        Accept: 'application/json',
      },
      signal: AbortSignal.timeout(30000),
    });
    return new NextResponse(await r.text(), {
      status: r.status,
      headers: { 'Content-Type': r.headers.get('content-type') ?? 'application/json' },
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : 'updater restart failed' },
      { status: 502 },
    );
  }
}
