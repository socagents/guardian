/**
 * GET /api/agent/update/status  (#CONN-F13)
 *
 * Proxies the guardian-updater's in-progress flag so the UI can
 * re-attach after a reload (or detect an update started elsewhere)
 * without opening a second SSE stream. Short timeout — this is polled.
 *
 * Upstream shape: { in_progress: boolean }
 */

import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  const updaterUrl =
    process.env.GUARDIAN_UPDATER_URL?.replace(/\/$/, '') ||
    'http://guardian-updater:8090';
  const mcpToken = process.env.MCP_TOKEN || '';
  try {
    const r = await fetch(`${updaterUrl}/api/v1/update/status`, {
      method: 'GET',
      headers: { Authorization: `Bearer ${mcpToken}`, Accept: 'application/json' },
      signal: AbortSignal.timeout(3000),
      cache: 'no-store',
    });
    return new NextResponse(await r.text(), {
      status: r.status,
      headers: { 'Content-Type': r.headers.get('content-type') ?? 'application/json' },
    });
  } catch {
    // Updater unreachable → treat as "not updating" so the UI stays usable.
    return NextResponse.json({ in_progress: false }, { status: 200 });
  }
}
