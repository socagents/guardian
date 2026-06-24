/**
 * Soft-deleted skills list proxy (#SKILL-F15).
 *
 * GET /api/skills/deleted → GET /api/v1/skills/deleted
 *
 * Returns restorable (soft-deleted) skills — files the operator deleted,
 * which delete_skill moved to /app/skills/.deleted/. Powers the in-product
 * restore affordance so recovery no longer requires docker cp / exec.
 */

import { proxyToMcp } from "@/lib/mcp-proxy";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  return proxyToMcp(request, "/api/v1/skills/deleted");
}
