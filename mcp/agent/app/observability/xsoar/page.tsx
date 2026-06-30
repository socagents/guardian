"use client";

import { useCallback, useEffect, useState } from "react";

const glassStyle = {
  background: "var(--glass-bg-strong)",
  backdropFilter: "blur(12px)",
  border: "0.5px solid var(--glass-border)",
} as const;

type Breach = {
  id?: string;
  name?: string;
  severity?: number;
  minutes_to_due?: number;
  overdue?: boolean;
  due_date?: string;
};

type IntegrationItem = {
  brand?: string;
  instance_name?: string;
  enabled?: boolean;
  healthy?: boolean;
  last_error?: string;
};

type InstanceMetrics = {
  instance: string;
  severity: { low: number; medium: number; high: number; critical: number; total: number; sampled: boolean } | null;
  sla: { breaches: number; top: Breach[] } | null;
  integrations: { total: number; unhealthy: number; items: IntegrationItem[] } | null;
  errors?: Record<string, string>;
};

type ApiResponse = {
  ok: boolean;
  no_instance?: boolean;
  error?: string;
  instances: InstanceMetrics[];
};

const SEV_META: Record<string, { label: string; color: string; bg: string }> = {
  critical: { label: "Critical", color: "text-error", bg: "bg-error/15" },
  high: { label: "High", color: "text-tertiary", bg: "bg-tertiary/15" },
  medium: { label: "Medium", color: "text-primary", bg: "bg-primary/15" },
  low: { label: "Low", color: "text-secondary", bg: "bg-secondary/15" },
};

function fmtMinutes(m?: number): string {
  if (m == null) return "—";
  const abs = Math.abs(m);
  const txt = abs >= 1440 ? `${(abs / 1440).toFixed(1)}d` : abs >= 60 ? `${(abs / 60).toFixed(1)}h` : `${Math.round(abs)}m`;
  return m < 0 ? `${txt} overdue` : `in ${txt}`;
}

export default function XsoarOpsPage() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/agent/observability/xsoar", { cache: "no-store" });
      const body = (await r.json()) as ApiResponse;
      if (!r.ok || body.ok === false) throw new Error(body.error || `xsoar metrics fetch ${r.status}`);
      setData(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="p-8 max-w-[1400px] mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className="material-symbols-outlined text-2xl text-primary">security</span>
            <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface">XSOAR Operational Metrics</h1>
          </div>
          <p className="text-sm text-on-surface-variant ml-9 max-w-2xl">
            Live KPIs read directly from the connected XSOAR instance(s): open incidents by severity, SLA-breach status, and
            integration health. Read-only — no actions taken on the tenant.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="px-4 py-2 rounded-xl text-xs font-medium text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-50"
          style={glassStyle}
        >
          <span className="material-symbols-outlined text-base align-middle mr-1">{loading ? "progress_activity" : "refresh"}</span>
          Refresh
        </button>
      </div>

      {error && <div className="rounded-xl border border-error/30 bg-error/10 p-3 text-xs text-error">{error}</div>}

      {data?.no_instance && (
        <div className="rounded-2xl p-8 text-center" style={glassStyle}>
          <span className="material-symbols-outlined text-4xl text-on-surface-variant mb-2 block">link_off</span>
          <p className="text-sm text-on-surface-variant">
            No enabled XSOAR connector instance. Configure one on the{" "}
            <a href="/connectors" className="text-primary hover:underline">Connectors</a> page to see operational metrics here.
          </p>
        </div>
      )}

      {loading && !data && <div className="text-sm text-on-surface-variant ml-9">Loading XSOAR metrics…</div>}

      {data?.instances?.map((inst) => (
        <div key={inst.instance} className="space-y-4">
          {data.instances.length > 1 && (
            <div className="flex items-center gap-2 ml-1">
              <span className="material-symbols-outlined text-base text-on-surface-variant">dns</span>
              <span className="font-mono text-sm text-on-surface">{inst.instance}</span>
            </div>
          )}

          {/* Open incidents by severity */}
          <div>
            <div className="flex items-center gap-2 mb-2 ml-1">
              <span className="material-symbols-outlined text-base text-on-surface-variant">bar_chart</span>
              <span className="font-label uppercase tracking-wider text-xs text-on-surface-variant">Open incidents by severity</span>
              {inst.errors?.severity && <span className="text-xs text-tertiary">({inst.errors.severity})</span>}
              {inst.severity?.sampled && (
                <span className="text-xs text-on-surface-variant">(split of the 200 most recent; total is exact)</span>
              )}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {(["critical", "high", "medium", "low"] as const).map((k) => {
                const meta = SEV_META[k];
                const v = inst.severity ? inst.severity[k] : null;
                return (
                  <div key={k} className="rounded-2xl p-4" style={glassStyle}>
                    <div className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-label uppercase tracking-wider ${meta.bg} ${meta.color} mb-2`}>
                      {meta.label}
                    </div>
                    <div className={`font-mono text-3xl font-bold ${meta.color}`}>{v == null ? "—" : v}</div>
                  </div>
                );
              })}
              <div className="rounded-2xl p-4" style={glassStyle}>
                <div className="inline-block px-2 py-0.5 rounded-full text-[10px] font-label uppercase tracking-wider bg-white/5 text-on-surface-variant mb-2">
                  Total open
                </div>
                <div className="font-mono text-3xl font-bold text-on-surface">{inst.severity ? inst.severity.total : "—"}</div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* SLA breaches */}
            <div className="rounded-2xl p-5" style={glassStyle}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-base text-tertiary">warning</span>
                  <span className="font-label uppercase tracking-wider text-xs text-on-surface-variant">SLA breaches</span>
                </div>
                {inst.sla && (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-mono ${inst.sla.breaches > 0 ? "bg-error/15 text-error" : "bg-secondary/15 text-secondary"}`}>
                    {inst.sla.breaches} breaching/due
                  </span>
                )}
              </div>
              {inst.errors?.sla && <p className="text-xs text-tertiary mb-2">{inst.errors.sla}</p>}
              {inst.sla && inst.sla.top.length > 0 ? (
                <div className="space-y-1.5">
                  {inst.sla.top.map((b, i) => (
                    <div key={b.id ?? i} className="flex items-center justify-between gap-2 text-xs">
                      <span className="font-mono text-on-surface-variant shrink-0">#{b.id}</span>
                      <span className="text-on-surface truncate flex-1">{b.name || "(no name)"}</span>
                      <span className={`font-mono shrink-0 ${b.overdue ? "text-error" : "text-tertiary"}`}>{fmtMinutes(b.minutes_to_due)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                inst.sla && !inst.errors?.sla && <p className="text-xs text-on-surface-variant">No incidents breaching or due within 24h.</p>
              )}
            </div>

            {/* Integration health */}
            <div className="rounded-2xl p-5" style={glassStyle}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-base text-primary">integration_instructions</span>
                  <span className="font-label uppercase tracking-wider text-xs text-on-surface-variant">Integration health</span>
                </div>
                {inst.integrations && (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-mono ${inst.integrations.unhealthy > 0 ? "bg-error/15 text-error" : "bg-secondary/15 text-secondary"}`}>
                    {inst.integrations.unhealthy} / {inst.integrations.total} unhealthy
                  </span>
                )}
              </div>
              {inst.errors?.integrations && <p className="text-xs text-tertiary mb-2">{inst.errors.integrations}</p>}
              {inst.integrations && inst.integrations.items.length > 0 ? (
                <div className="space-y-1.5">
                  {inst.integrations.items.map((it, i) => (
                    <div key={`${it.instance_name}-${i}`} className="flex items-center justify-between gap-2 text-xs">
                      <span className="text-on-surface truncate flex-1">{it.brand || it.instance_name}</span>
                      <span className={`font-mono shrink-0 ${it.healthy === false ? "text-error" : it.enabled === false ? "text-on-surface-variant" : "text-secondary"}`}>
                        {it.healthy === false ? "error" : it.enabled === false ? "disabled" : "ok"}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                inst.integrations && !inst.errors?.integrations && <p className="text-xs text-secondary">All integrations healthy.</p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
