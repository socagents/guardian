/**
 * DELETE /api/agent/marketplace/{connectorId}  (#CONN-F3)
 *
 * Thin proxy to the MCP's DELETE /api/v1/marketplace/{connector_id}
 * (bundles/spark/mcp/src/api/marketplace.py:delete_connector) — the
 * full removal of a USER-uploaded connector (uninstall marker + the
 * on-disk user_connectors/<id>/ YAML + a connector_deleted audit row).
 *
 * Pre-v0.2.64 there was no proxy + no UI for this, so a customer who
 * uploaded a connector could only Uninstall it (remove the install
 * marker) — never fully remove it — without a direct MCP_TOKEN call.
 *
 * MCP response contract (passed through verbatim):
 *   200 { ok: true, deleted: <id> }
 *   403 { error, code: "cannot_delete_bundle" }  — bundle connectors
 *   409 { error, code: "has_instances" }          — delete instances first
 *   404 { error }                                  — not in catalogue
 */

import { NextRequest, NextResponse } from 'next/server';

import { resolveMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ connectorId: string }> },
) {
  const { connectorId } = await params;
  if (!connectorId) {
    return NextResponse.json(
      { error: 'connectorId path segment is required' },
      { status: 400 },
    );
  }

  const r = await resolveMcp();
  if (r instanceof NextResponse) return r;

  let upstream: Response;
  try {
    upstream = await fetch(
      `${r.base}/api/v1/marketplace/${encodeURIComponent(connectorId)}`,
      {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${r.token}` },
        cache: 'no-store',
      },
    );
  } catch (err) {
    return NextResponse.json(
      {
        error: 'MCP unreachable',
        detail: err instanceof Error ? err.message : String(err),
      },
      { status: 502 },
    );
  }

  const payload = await upstream.json().catch(() => null);
  // Pass MCP status + body through verbatim — the 403 (cannot_delete_bundle)
  // and 409 (has_instances) carry codes the UI surfaces in its toast.
  return NextResponse.json(
    payload ?? { error: `MCP returned ${upstream.status}` },
    { status: upstream.status },
  );
}
