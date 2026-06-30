/**
 * XSOAR operational metrics (v0.2.107, arc R9).
 *
 * Aggregates live KPIs from the connected XSOAR connector instance(s) for the
 * /observability/xsoar surface: open-incident counts by severity, SLA-breach
 * status, and integration health. Runs server-side with the MCP_TOKEN and
 * dispatches the read-only XSOAR connector tools over JSON-RPC via
 * GuardianMCPClient — these are catalog-side reads (no SecretStore access).
 *
 * Resilient by design: per-tool calls use Promise.allSettled so one failing
 * tool (or a connector that doesn't yet expose a newer tool) degrades to a
 * per-panel error instead of a blank page. Renders a clean empty state when no
 * XSOAR instance is configured.
 */
import { NextResponse } from "next/server";
import { GuardianMCPClient, type MCPToolResult } from "@/lib/mcp-client";
import { deriveMcpBaseUrl, getEffectiveRuntimeConfig } from "@/lib/runtime-config";

export const dynamic = "force-dynamic";

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

const SEVERITY = [
  { code: 1, key: "low" },
  { code: 2, key: "medium" },
  { code: 3, key: "high" },
  { code: 4, key: "critical" },
] as const;

export async function GET(): Promise<NextResponse> {
  const cfg = await getEffectiveRuntimeConfig();
  const mcpToken =
    (cfg.MCP_TOKEN || "").trim() || process.env.MCP_TOKEN?.trim() || "";
  if (!mcpToken) {
    return NextResponse.json(
      { ok: false, error: "MCP_TOKEN not configured" },
      { status: 503 },
    );
  }
  const streamUrl =
    (cfg.MCP_URL || "").trim() ||
    process.env.MCP_URL?.trim() ||
    "http://localhost:8080/api/v1/stream/mcp";
  const base = deriveMcpBaseUrl(streamUrl);

  // 1. Discover the enabled XSOAR instance(s).
  let instances: XsoarInstance[] = [];
  try {
    const r = await fetch(`${base}/api/v1/instances?connector_id=xsoar`, {
      headers: { Authorization: `Bearer ${mcpToken}` },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (r.ok) {
      const data = (await r.json()) as { instances?: XsoarInstance[] };
      instances = (data.instances ?? []).filter(
        (i) => i.connector_id === "xsoar" && i.enabled,
      );
    }
  } catch {
    /* fall through to the empty-state response */
  }

  if (instances.length === 0) {
    return NextResponse.json({ ok: true, no_instance: true, instances: [] });
  }

  // GuardianMCPClient uses the second arg verbatim as the Authorization header.
  const client = new GuardianMCPClient(streamUrl, `Bearer ${mcpToken}`);
  const multi = instances.length > 1;

  const perInstance = await Promise.all(
    instances.map(async (inst) => {
      const instArg = multi ? { instance: inst.name } : {};
      const errors: Record<string, string> = {};

      // Open-incident counts by severity — one cheap bucket call each (read total).
      const sevSettled = await Promise.allSettled(
        SEVERITY.map((s) =>
          client.callTool("xsoar_list_incidents", {
            status: [1],
            severity: [s.code],
            page_size: 1,
            ...instArg,
          }),
        ),
      );
      const severity: Record<string, number | null> = {};
      let total = 0;
      let sevHadError = false;
      sevSettled.forEach((res, i) => {
        const key = SEVERITY[i].key;
        if (res.status === "fulfilled") {
          const parsed = parseToolResult<{ total?: number }>(res.value);
          const n = parsed && typeof parsed.total === "number" ? parsed.total : null;
          severity[key] = n;
          if (n != null) total += n;
          else sevHadError = true;
        } else {
          severity[key] = null;
          sevHadError = true;
        }
      });
      if (sevHadError) errors.severity = "one or more severity buckets failed";

      // SLA breaches — open incidents at/over their deadline, most-urgent first.
      let sla: { breaches: number; top: unknown[] } | null = null;
      try {
        const slaRes = await client.callTool("xsoar_sla_breaches", {
          include_breached: true,
          within_hours: 24,
          limit: 8,
          ...instArg,
        });
        const parsed = parseToolResult<{ count?: number; breaches?: unknown[] }>(slaRes);
        if (parsed) {
          sla = { breaches: parsed.count ?? (parsed.breaches?.length ?? 0), top: parsed.breaches ?? [] };
        } else {
          errors.sla = "sla_breaches returned no data (connector may predate this tool)";
        }
      } catch (e) {
        errors.sla = e instanceof Error ? e.message : String(e);
      }

      // Integration health.
      let integrations: {
        total: number;
        unhealthy: number;
        items: Array<{ brand?: string; instance_name?: string; enabled?: boolean; healthy?: boolean; last_error?: string }>;
      } | null = null;
      try {
        const intRes = await client.callTool("xsoar_get_integration_status", { ...instArg });
        const parsed = parseToolResult<{
          integrations?: Array<{ brand?: string; instance_name?: string; enabled?: boolean; healthy?: boolean; last_error?: string }>;
          total?: number;
          unhealthy_count?: number;
        }>(intRes);
        if (parsed) {
          const items = parsed.integrations ?? [];
          integrations = {
            total: parsed.total ?? items.length,
            unhealthy: parsed.unhealthy_count ?? items.filter((x) => x.healthy === false).length,
            items: items.filter((x) => x.healthy === false || x.enabled === false).slice(0, 12),
          };
        } else {
          errors.integrations = "get_integration_status returned no data";
        }
      } catch (e) {
        errors.integrations = e instanceof Error ? e.message : String(e);
      }

      return {
        instance: inst.name,
        severity: { ...severity, total },
        sla,
        integrations,
        errors: Object.keys(errors).length ? errors : undefined,
      };
    }),
  );

  return NextResponse.json({ ok: true, instances: perInstance });
}
