/**
 * GET /api/agent/update/check  (#CONN-F13)
 *
 * Proxies the guardian-updater's version-check so the About modal can
 * show "running vs latest" and an Upgrade affordance. Same MCP_TOKEN
 * proxying pattern as /api/agent/digests. Degrades to a soft error
 * object (not a 5xx) when the updater is unreachable, so the modal can
 * render "couldn't check for updates" rather than breaking.
 *
 * Upstream shape: { running_version, latest_version, updates_available,
 *   services: {svc: {current_version, current_digest, target_digest,
 *   update, running}}, checked_at, error? }
 */

import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  const updaterUrl =
    process.env.GUARDIAN_UPDATER_URL?.replace(/\/$/, '') ||
    'http://guardian-updater:8090';
  const mcpToken = process.env.MCP_TOKEN || '';
  try {
    const r = await fetch(`${updaterUrl}/api/v1/version/check`, {
      method: 'GET',
      headers: { Authorization: `Bearer ${mcpToken}`, Accept: 'application/json' },
      // Version check hits the GitHub Releases API upstream; give it room.
      signal: AbortSignal.timeout(15000),
      cache: 'no-store',
    });
    return new NextResponse(await r.text(), {
      status: r.status,
      headers: { 'Content-Type': r.headers.get('content-type') ?? 'application/json' },
    });
  } catch (e) {
    return NextResponse.json(
      {
        updates_available: false,
        error: e instanceof Error ? e.message : 'updater unreachable',
      },
      { status: 200 },
    );
  }
}
