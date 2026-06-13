"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { getCase, type CaseDetail } from "@/lib/api/investigation";
import { glassStyle, IssueRow, EmptyState, fmtTs } from "@/components/investigation/ui";
import { MarkdownContent } from "@/components/markdown-content";

/**
 * Investigation → Case detail (v0.1.7 — full-width glass layout). Case
 * metadata over the Issues grouped under it (each links to the tabbed issue
 * detail, rendered with the same row as the Issues list for consistency).
 */
export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [data, setData] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getCase(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load case");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <p className="text-sm text-on-surface-variant p-8 text-center">Loading…</p>;
  if (error) return <p className="text-sm text-error p-8 text-center">{error}</p>;
  if (!data) return <p className="text-sm text-on-surface-variant p-8 text-center">Case not found.</p>;

  return (
    <div className="max-w-[1400px] mx-auto px-8 py-8 pb-32">
      <Link href="/investigation/cases" className="text-xs text-on-surface-variant hover:text-on-surface inline-flex items-center gap-1 mb-4">
        <span className="material-symbols-outlined text-[16px]">arrow_back</span> Cases
      </Link>

      {/* Header */}
      <div className="rounded-2xl p-6 mb-6" style={glassStyle}>
        <div className="flex items-start gap-4">
          <span className="material-symbols-outlined text-2xl text-primary mt-0.5">folder_special</span>
          <div className="flex-1 min-w-0">
            <h1 className="font-headline text-2xl font-bold tracking-tight text-on-surface">{data.title}</h1>
            {data.description && (
              <div className="text-sm mt-2">
                <MarkdownContent compact>{data.description}</MarkdownContent>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2 mt-3 text-[11px] text-on-surface-variant">
              <span className="rounded-full border border-outline-variant px-2 py-0.5 uppercase tracking-wide font-bold">{data.status}</span>
              <span className="inline-flex items-center gap-1">
                <span className="material-symbols-outlined text-[14px]">report</span>
                {data.issues.length} {data.issues.length === 1 ? "issue" : "issues"}
              </span>
              <span className="text-on-surface-variant/60">updated {fmtTs(data.updated_at)}</span>
            </div>
          </div>
        </div>
      </div>

      <h2 className="font-headline text-sm font-bold uppercase tracking-widest text-on-surface-variant mb-3">Issues in this case</h2>
      {data.issues.length === 0 ? (
        <EmptyState
          icon="report"
          title="No issues grouped here yet"
          hint="Assign an issue to this case from the issue's detail page (the Case control in its header), or let Guardian group related Issues during an investigation."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {data.issues.map((i) => (
            <IssueRow key={i.id} issue={i} />
          ))}
        </div>
      )}
    </div>
  );
}
