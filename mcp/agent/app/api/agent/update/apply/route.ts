/**
 * POST /api/agent/update/apply  (#CONN-F13)
 *
 * SSE pass-through to the guardian-updater's POST /api/v1/update — the
 * push-button in-place stack upgrade. Streams `phase` / `pull_progress`
 * / `error` events to the About-modal progress panel. The updater holds
 * an update lock for the whole run (returns 409 if one is already
 * active), so the UI re-attaches via GET /api/agent/update/status rather
 * than a second stream.
 *
 * runtime: 'nodejs' is REQUIRED — the edge runtime buffers the response
 * body and the stream never reaches the browser (same constraint as
 * /api/agent/audit/stream). request.signal is forwarded so closing the
 * modal aborts the upstream connection cleanly; the updater's own
 * `finally` releases its lock independently, so the update itself isn't
 * interrupted just because the operator navigated away.
 */

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(request: Request) {
  const updaterUrl =
    process.env.GUARDIAN_UPDATER_URL?.replace(/\/$/, '') ||
    'http://guardian-updater:8090';
  const mcpToken = process.env.MCP_TOKEN || '';
  if (!mcpToken) {
    return new Response('MCP_TOKEN not configured', { status: 503 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${updaterUrl}/api/v1/update`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${mcpToken}` },
      signal: request.signal,
    });
  } catch (err) {
    return new Response(
      err instanceof Error ? err.message : 'updater unreachable',
      { status: 502 },
    );
  }

  // 409 (already in progress) + any non-stream error: pass the body
  // through so the UI can show "an update is already running".
  if (!upstream.ok || !upstream.body) {
    return new Response(await upstream.text().catch(() => ''), {
      status: upstream.status || 502,
      headers: { 'Content-Type': upstream.headers.get('content-type') ?? 'application/json' },
    });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'X-Accel-Buffering': 'no',
    },
  });
}
