/**
 * XSOAR operational metrics (v0.2.107, arc R9).
 *
 * Aggregates live KPIs from the connected XSOAR connector instance(s) for the
 * /observability/xsoar surface: open-incident counts by severity, SLA-breach
 * status, and integration health. Runs server-side with the MCP_TOKEN and
 * dispatches the read-only XSOAR connector tools over JSON-RPC — these are
 * catalog-side reads (no SecretStore access).
 *
 * Resilience contract (learned the hard way — the first cut hung the route):
 *   - GuardianMCPClient.callTool has NO internal timeout, and its session is
 *     stateful, so we use a FRESH client per call (no shared-session race) and
 *     race each call against a hard timeout. A slow/hung tool degrades to a
 *     per-panel error instead of hanging the whole request.
 *   - Per-tool Promise.allSettled so one failing tool doesn't sink the others.
 *   - Clean empty state when no XSOAR instance is configured.
 */
import { NextResponse } from "next/server";
import { GuardianMCPClient, type MCPToolResult } from "@/lib/mcp-client";
import { deriveMcpBaseUrl, getEffectiveRuntimeConfig } from "@/lib/runtime-config";

export const dynamic = "force-dynamic";

const TOOL_TIMEOUT_MS = 12_000;

type XsoarInstance = { connector_id: string; name: string; enabled: boolean };

function parseToolResult<T>(r: MCPToolResult | undefined): T | null {
  if (!r || r.isError) return null;
  if (r.structuredContent !== undefined) return r.structuredContent as T;
  const text = r.content?.[0]?.text;
  if (!text) return null;
  try {
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}

/**
 * One tool call on a FRESH client (no shared JSON-RPC session) with a hard
 * timeout. Resolves to the parsed result, or null on error/timeout — never
 * hangs and never throws.
 */
async function safeCall<T>(
  streamUrl: string,
  authHeader: string,
  name: string,
  args: Record<string, unknown>,
): Promise<T | null> {
  const client = new GuardianMCPClient(streamUrl, authHeader);
  const timeout = new Promise<null>((resolve) => setTimeout(() => resolve(null), TOOL_TIMEOUT_MS));
  try {
    const result = await Promise.race([client.callTool(name, args), timeout]);
    return parseToolResult<T>(result ?? undefined);
  } catch {
    return null;
  }
}

const SEV_BY_CODE: Record<number, "low" | "medium" | "high" | "critical"> = {
  1: "low",
  2: "medium",
  3: "high",
  4: "critical",
};

export async function GET(): Promise<NextResponse> {
  const cfg = await getEffectiveRuntimeConfig();
  const mcpToken = (cfg.MCP_TOKEN || "").trim() || process.env.MCP_TOKEN?.trim() || "";
  if (!mcpToken) {
    return NextResponse.json({ ok: false, error: "MCP_TOKEN not configured" }, { status: 503 });
  }
  const streamUrl =
    (cfg.MCP_URL || "").trim() ||
    process.env.MCP_URL?.trim() ||
    "http://localhost:8080/api/v1/stream/mcp";
  const authHeader = `Bearer ${mcpToken}`;
  const base = deriveMcpBaseUrl(streamUrl);

  // 1. Discover the enabled XSOAR instance(s).
  let instances: XsoarInstance[] = [];
  try {
    const r = await fetch(`${base}/api/v1/instances?connector_id=xsoar`, {
      headers: { Authorization: authHeader },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (r.ok) {
      const data = (await r.json()) as { instances?: XsoarInstance[] };
      instances = (data.instances ?? []).filter((i) => i.connector_id === "xsoar" && i.enabled);
    }
  } catch {
    /* fall through to the empty-state response */
  }

  if (instances.length === 0) {
    return NextResponse.json({ ok: true, no_instance: true, instances: [] });
  }

  const multi = instances.length > 1;

  const perInstance = await Promise.all(
    instances.map(async (inst) => {
      const instArg = multi ? { instance: inst.name } : {};
      const errors: Record<string, string> = {};

      // Three concurrent, independently-timed-out calls.
      const [incidentsParsed, slaParsed, intParsed] = await Promise.all([
        safeCall<{ incidents?: Array<{ severity?: number }>; total?: number }>(
          streamUrl,
          authHeader,
          "xsoar_list_incidents",
          { status: [1], page_size: 200, ...instArg },
        ),
        safeCall<{ count?: number; breaches?: unknown[] }>(
          streamUrl,
          authHeader,
          "xsoar_sla_breaches",
          { include_breached: true, within_hours: 24, limit: 8, ...instArg },
        ),
        safeCall<{
          integrations?: Array<{ brand?: string; instance_name?: string; enabled?: boolean; healthy?: boolean; last_error?: string }>;
          total?: number;
          unhealthy_count?: number;
        }>(streamUrl, authHeader, "xsoar_get_integration_status", { ...instArg }),
      ]);

      // Severity — counted from the open-incident page; `total` is the exact
      // open count (the page is capped at 200, so for a very large queue the
      // per-severity split is of the most-recent 200; the total stays exact).
      let severity: { low: number; medium: number; high: number; critical: number; total: number; sampled: boolean } | null = null;
      if (incidentsParsed) {
        const counts = { low: 0, medium: 0, high: 0, critical: 0 };
        const rows = incidentsParsed.incidents ?? [];
        for (const row of rows) {
          const key = SEV_BY_CODE[Number(row.severity)];
          if (key) counts[key] += 1;
        }
        const total = typeof incidentsParsed.total === "number" ? incidentsParsed.total : rows.length;
        severity = { ...counts, total, sampled: total > rows.length };
      } else {
        errors.severity = "xsoar_list_incidents failed or timed out";
      }

      let sla: { breaches: number; top: unknown[] } | null = null;
      if (slaParsed) {
        sla = { breaches: slaParsed.count ?? (slaParsed.breaches?.length ?? 0), top: slaParsed.breaches ?? [] };
      } else {
        errors.sla = "xsoar_sla_breaches failed or timed out (a connector predating this tool returns no data)";
      }

      let integrations: {
        total: number;
        unhealthy: number;
        items: Array<{ brand?: string; instance_name?: string; enabled?: boolean; healthy?: boolean; last_error?: string }>;
      } | null = null;
      if (intParsed) {
        const items = intParsed.integrations ?? [];
        integrations = {
          total: intParsed.total ?? items.length,
          unhealthy: intParsed.unhealthy_count ?? items.filter((x) => x.healthy === false).length,
          items: items.filter((x) => x.healthy === false || x.enabled === false).slice(0, 12),
        };
      } else {
        errors.integrations = "xsoar_get_integration_status failed or timed out";
      }

      return {
        instance: inst.name,
        severity,
        sla,
        integrations,
        errors: Object.keys(errors).length ? errors : undefined,
      };
    }),
  );

  return NextResponse.json({ ok: true, instances: perInstance });
}
