/**
 * Detections bulk-upsert proxy — v0.6.25.
 *
 * POST /api/agent/detections/sync
 *   Body (JSON): {
 *     issues: [
 *       { rule_id, rule_name, severity, technique?, last_fired, ... },
 *       ...
 *     ]
 *   }
 *
 * Used by external tooling that pre-fetches issues from XSIAM/SIEM
 * outside the standard detection_inventory_sync skill flow. Most
 * operators won't hit this directly — the skill is the canonical
 * path.
 */

import { proxyToMcp } from '@/lib/mcp-proxy';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  return proxyToMcp(request, '/api/v1/detections/sync');
}
