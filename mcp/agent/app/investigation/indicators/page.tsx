"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { listIndicators, indicatorTypeLabel, type Indicator } from "@/lib/api/investigation";
import { glassStyle, StatCard, EmptyState, IndicatorRow } from "@/components/investigation/ui";

/**
 * Investigation → Indicators (v0.2.0).
 *
 * IoCs extracted across investigations — Guardian records each indicator it
 * enriches, and imports the indicators XSOAR already extracted when it fetches
 * a case. Deduped by (value, type); click one to see every issue it appears in.
 */

const TYPE_FILTERS = ["", "ip", "domain", "url", "file_hash", "email", "cve", "host", "account"];

export default function IndicatorsPage() {
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { indicators } = await listIndicators();
      setIndicators(indicators);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load indicators");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const stats = useMemo(
    () => ({
      total: indicators.length,
      malicious: indicators.filter((i) => i.dbot_score === 3).length,
      fromXsoar: indicators.filter((i) => i.source === "xsoar").length,
    }),
    [indicators],
  );

  const filtered = useMemo(
    () => (typeFilter ? indicators.filter((i) => i.type === typeFilter) : indicators),
    [indicators, typeFilter],
  );

  return (
    <div className="max-w-[1400px] mx-auto px-8 py-8 pb-32 space-y-8">
      <div>
        <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-2xl text-primary">fingerprint</span>
          Indicators
        </h1>
        <p className="text-sm text-on-surface-variant mt-1 ml-9 max-w-3xl">
          IoCs extracted across investigations — Guardian records each indicator it enriches, and imports the
          indicators XSOAR already extracted when it fetches a case. Deduped; click one to see every issue it appears in.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard icon="fingerprint" label="Indicators" value={stats.total} tone="bg-primary/15 text-primary" />
        <StatCard icon="gpp_bad" label="Malicious" value={stats.malicious} tone="bg-error/15 text-error" />
        <StatCard icon="cloud_download" label="From XSOAR" value={stats.fromXsoar} tone="bg-tertiary/15 text-tertiary" />
      </div>

      <div className="flex items-center gap-1.5 rounded-2xl p-1.5 w-fit flex-wrap" style={glassStyle}>
        {TYPE_FILTERS.map((t) => (
          <button
            key={t || "all"}
            onClick={() => setTypeFilter(t)}
            className={`rounded-lg px-3 py-1.5 text-[11px] uppercase tracking-wider font-medium transition ${
              typeFilter === t
                ? "bg-secondary-container/40 border border-secondary/40 text-secondary"
                : "border border-transparent text-on-surface-variant hover:text-on-surface hover:bg-white/5"
            }`}
          >
            {t ? indicatorTypeLabel(t) : "all"}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-on-surface-variant py-12 text-center">Loading…</p>
      ) : error ? (
        <p className="text-sm text-error py-12 text-center">{error}</p>
      ) : indicators.length === 0 ? (
        <EmptyState
          icon="fingerprint"
          title="No indicators yet"
          hint="As Guardian investigates and enriches IoCs — or imports them from fetched XSOAR cases — they appear here, deduped and linked to the issues they were seen in."
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="filter_alt_off"
          title={`No ${indicatorTypeLabel(typeFilter)} indicators`}
          hint="No indicators match this type — clear the filter."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filtered.map((i) => (
            <IndicatorRow key={i.id} indicator={i} href={`/investigation/indicators/${i.id}`} />
          ))}
        </div>
      )}
    </div>
  );
}
