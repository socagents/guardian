"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  getIndicator,
  indicatorTypeLabel,
  dbotMeta,
  kindLabel,
  INDICATOR_TYPE_ICON,
  STATUS_TOKENS,
  type IndicatorDetail,
} from "@/lib/api/investigation";
import { glassStyle, Badge, EmptyState, fmtTs } from "@/components/investigation/ui";

/**
 * Investigation → Indicator detail (v0.2.0). The IoC's reputation + enrichment
 * (from Guardian or imported from XSOAR), first/last seen, and every Issue it
 * appears in (cross-case correlation).
 */
export default function IndicatorDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [data, setData] = useState<IndicatorDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getIndicator(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load indicator");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <p className="text-sm text-on-surface-variant p-8 text-center">Loading…</p>;
  if (error) return <p className="text-sm text-error p-8 text-center">{error}</p>;
  if (!data) return <p className="text-sm text-on-surface-variant p-8 text-center">Indicator not found.</p>;

  const dbot = dbotMeta(data.dbot_score);
  let enr: Record<string, unknown> | null = null;
  if (data.enrichment) {
    try {
      const parsed = JSON.parse(data.enrichment);
      enr = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
    } catch {
      enr = null;
    }
  }

  return (
    <div className="max-w-[1400px] mx-auto px-8 py-8 pb-32">
      <Link href="/investigation/indicators" className="text-xs text-on-surface-variant hover:text-on-surface inline-flex items-center gap-1 mb-4">
        <span className="material-symbols-outlined text-[16px]">arrow_back</span> Indicators
      </Link>

      {/* Header */}
      <div className="rounded-2xl p-6 mb-6" style={glassStyle}>
        <div className="flex items-start gap-4">
          <span className="material-symbols-outlined text-2xl text-primary mt-0.5">
            {INDICATOR_TYPE_ICON[data.type] ?? "fingerprint"}
          </span>
          <div className="flex-1 min-w-0">
            <h1 className="font-mono text-xl font-bold text-on-surface break-all">{data.value}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <Badge>{indicatorTypeLabel(data.type)}</Badge>
              <Badge tone={dbot.tone}>
                {dbot.label}
                {data.dbot_score != null ? ` · DBotScore ${data.dbot_score}` : ""}
              </Badge>
              <Badge tone={data.source === "xsoar" ? "text-tertiary border-tertiary/30" : undefined}>
                source: {data.source}
              </Badge>
              <span className="text-[11px] text-on-surface-variant/60">
                first seen {fmtTs(data.first_seen)} · last seen {fmtTs(data.last_seen)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Enrichment */}
      <h2 className="font-headline text-sm font-bold uppercase tracking-widest text-on-surface-variant mb-3">Enrichment</h2>
      {enr ? (
        <div className="rounded-2xl p-5 mb-6" style={glassStyle}>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2.5 text-sm">
            {Object.entries(enr).map(([k, v]) => (
              <div key={k} className="flex gap-3">
                <dt className="text-on-surface-variant uppercase text-[10px] tracking-wider min-w-[110px] pt-0.5 shrink-0">{k}</dt>
                <dd className="text-on-surface break-all">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : data.enrichment ? (
        <pre className="rounded-2xl p-5 mb-6 text-xs text-on-surface overflow-x-auto font-mono" style={glassStyle}>{data.enrichment}</pre>
      ) : (
        <div className="mb-6">
          <EmptyState icon="science" title="No enrichment recorded" hint="Guardian or XSOAR hasn't attached enrichment detail to this indicator yet." />
        </div>
      )}

      {/* Related issues */}
      <h2 className="font-headline text-sm font-bold uppercase tracking-widest text-on-surface-variant mb-3">
        Seen in {data.issues.length} {data.issues.length === 1 ? "issue" : "issues"}
      </h2>
      {data.issues.length === 0 ? (
        <EmptyState icon="report" title="Not linked to any issue yet" />
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {data.issues.map((i) => (
            <Link
              key={i.id}
              href={`/investigation/issues/${i.id}`}
              className="block rounded-xl p-4 transition-all hover:shadow-[0_0_20px_rgba(25,99,179,0.1)]"
              style={glassStyle}
            >
              <div className="flex items-center gap-3">
                <span className="font-medium text-on-surface flex-1 truncate">{i.title}</span>
                <Badge tone={STATUS_TOKENS[i.status]}>{i.status}</Badge>
                <Badge>{kindLabel(i.kind)}</Badge>
                {i.source_ref && <span className="text-[11px] text-on-surface-variant whitespace-nowrap">XSOAR {i.source_ref}</span>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
