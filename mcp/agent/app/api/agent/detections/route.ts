/**
 * Detections inventory proxy — v0.6.25.
 *
 * Surfaces the MCP's /api/v1/detections endpoint (declared in
 * bundles/spark/mcp/src/api/detections.py) to the UI. The MCP has
 * had this endpoint since Phase 12; the agent proxy + the
 * /observability/detections page closed in v0.6.25 to satisfy
 * CLAUDE.md § "Documentation discipline" rule 6 ("no backend
 * feature without a UI surface").
 *
 * GET /api/agent/detections
 *   Query params (forwarded verbatim):
 *     - severity   filter to one severity bucket
 *     - technique  filter to one MITRE T-code (e.g. T1059.001)
 *     - limit      max rows (default 100; v0.6.10 made underlying
 *                  store accept -1 for unlimited)
 *
 * Returns:
 *   { rules: [...], count: N }
 *
 * Side endpoints (separate route files in this dir):
 *   - /detections/sync                       POST upsert batch
 *   - /detections/[rule_id]                  GET single rule
 *   - /detections/[rule_id]/fires            GET recent fires
 *   - /detections/coverage/techniques        GET MITRE coverage
 */

import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  return proxyToMcp(request, '/api/v1/detections');
}
