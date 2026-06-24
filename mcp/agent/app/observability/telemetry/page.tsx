"use client";

/**
 * /observability/telemetry — #OBS-F17.
 *
 * Opt-in usage-counter posture + counts. Before this page the entire
 * telemetry surface (GET/POST /api/v1/telemetry/*) was MCP-internal and
 * unreachable from the browser. The page reads the status snapshot, lets
 * the operator flip the privacy posture on/off (audited as
 * telemetry_toggled), and shows per-event totals.
 *
 * Privacy posture: telemetry starts OFF. Only events declared in
 * manifest.telemetry.events are ever recorded; event payloads are never
 * shown here (the page only reports counts).
 */

import { useCallback, useEffect, useState } from "react";

const glassCard = {
  background: "var(--glass-bg-strong)",
  backdropFilter: "blur(12px)",
  border: "0.5px solid var(--glass-border)",
} as const;

interface TelemetryStatus {
  enabled: boolean;
  declared_events: string[];
  total_recorded: number;
  counts_by_event: Record<string, number>;
}

export default function TelemetryPage() {
  const [status, setStatus] = useState<TelemetryStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/agent/telemetry", { cache: "no-store" });
      if (!r.ok) throw new Error(`telemetry fetch ${r.status}`);
      setStatus((await r.json()) as TelemetryStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const toggle = useCallback(
    async (next: boolean) => {
      setToggling(true);
      setError(null);
      try {
        const r = await fetch("/api/agent/telemetry/enable", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: next }),
        });
        if (!r.ok) throw new Error(`toggle ${r.status}`);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setToggling(false);
      }
    },
    [refresh],
  );

  const enabled = status?.enabled ?? false;
  const counts = status?.counts_by_event ?? {};
  const declared = status?.declared_events ?? [];
  const sortedEvents = [...declared].sort(
    (a, b) => (counts[b] ?? 0) - (counts[a] ?? 0),
  );

  return (
    <div className="h-screen overflow-y-auto custom-scrollbar">
      <div className="max-w-[1100px] mx-auto px-8 py-8 space-y-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="material-symbols-outlined text-2xl text-primary">
                insights
              </span>
              <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface">
                Telemetry
              </h1>
            </div>
            <p className="text-sm text-on-surface-variant ml-9 max-w-2xl">
              Opt-in, privacy-first usage counters. Off by default. Only
              events declared in the bundle manifest are ever recorded, and
              this page reports counts only — never the event payloads.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="px-3 py-1.5 rounded-xl text-xs font-medium text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-50"
            style={glassCard}
            aria-label="Refresh"
          >
            <span className="material-symbols-outlined text-sm align-middle">
              refresh
            </span>
          </button>
        </div>

        {error && (
          <div className="rounded-xl border border-error/30 bg-error/10 p-3 text-xs text-error">
            {error}
          </div>
        )}

        {/* Posture toggle */}
        <div
          className="rounded-2xl p-5 flex items-center justify-between gap-4"
          style={glassCard}
        >
          <div>
            <p className="font-headline text-sm font-semibold text-on-surface">
              Usage telemetry is {enabled ? "ON" : "OFF"}
            </p>
            <p className="text-xs text-on-surface-variant mt-1 max-w-xl">
              {enabled
                ? "Declared usage events are being counted locally. Toggle off to stop recording; existing counts are kept."
                : "No usage events are being recorded. Toggle on to start counting declared events locally."}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void toggle(!enabled)}
            disabled={toggling || loading}
            className={`px-5 py-2.5 rounded-xl text-sm font-headline font-bold transition-all disabled:opacity-50 ${
              enabled
                ? "text-on-surface-variant hover:text-error"
                : "text-white"
            }`}
            style={
              enabled
                ? { border: "0.5px solid var(--glass-border)" }
                : {
                    background:
                      "linear-gradient(135deg, #1963B3 0%, #2D8DF0 100%)",
                  }
            }
          >
            {toggling ? "Saving…" : enabled ? "Turn off" : "Turn on"}
          </button>
        </div>

        {/* Totals */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-2xl p-5" style={glassCard}>
            <p className="text-[10px] uppercase tracking-wider text-on-surface-variant font-label mb-1">
              Total recorded
            </p>
            <p className="font-headline text-2xl font-bold text-on-surface">
              {(status?.total_recorded ?? 0).toLocaleString()}
            </p>
          </div>
          <div className="rounded-2xl p-5" style={glassCard}>
            <p className="text-[10px] uppercase tracking-wider text-on-surface-variant font-label mb-1">
              Declared events
            </p>
            <p className="font-headline text-2xl font-bold text-on-surface">
              {declared.length}
            </p>
          </div>
          <div className="rounded-2xl p-5" style={glassCard}>
            <p className="text-[10px] uppercase tracking-wider text-on-surface-variant font-label mb-1">
              Posture
            </p>
            <p
              className={`font-headline text-2xl font-bold ${
                enabled ? "text-secondary" : "text-on-surface-variant"
              }`}
            >
              {enabled ? "Enabled" : "Disabled"}
            </p>
          </div>
        </div>

        {/* Per-event counts */}
        <div className="rounded-2xl overflow-hidden" style={glassCard}>
          <div className="px-5 py-3 border-b border-outline-variant/10">
            <h2 className="font-headline text-sm font-semibold text-on-surface">
              Per-event counts ({declared.length})
            </h2>
          </div>
          {loading ? (
            <div className="px-5 py-8 text-center text-xs text-on-surface-variant">
              Loading…
            </div>
          ) : declared.length === 0 ? (
            <div className="px-5 py-8 text-center text-xs text-on-surface-variant">
              No events declared in the manifest.
            </div>
          ) : (
            <ul className="divide-y divide-outline-variant/10">
              {sortedEvents.map((ev) => (
                <li
                  key={ev}
                  className="px-5 py-2.5 flex items-center justify-between gap-4"
                >
                  <code className="font-mono text-xs text-on-surface-variant">
                    {ev}
                  </code>
                  <span className="font-headline text-sm font-semibold text-on-surface tabular-nums">
                    {(counts[ev] ?? 0).toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export const dynamic = "force-dynamic";
