"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  getCase,
  kindLabel,
  SEVERITY_TOKENS,
  STATUS_TOKENS,
  type CaseDetail,
} from "@/lib/api/investigation";

/**
 * Investigation → Case detail (v0.1.3). Case metadata + the Issues grouped
 * under it (each links to the rich issue layout).
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
    <div className="mx-auto max-w-4xl px-6 py-8">
      <Link href="/investigation/cases" className="text-xs text-on-surface-variant hover:text-on-surface inline-flex items-center gap-1 mb-4">
        <span className="material-symbols-outlined text-[16px]">arrow_back</span> Cases
      </Link>

      <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 mb-5">
        <div className="flex items-start gap-3">
          <span className="material-symbols-outlined text-primary mt-0.5">cases</span>
          <div className="flex-1">
            <h1 className="font-headline text-xl font-bold text-on-surface">{data.title}</h1>
            {data.description && <p className="text-sm text-on-surface-variant mt-1 whitespace-pre-wrap">{data.description}</p>}
            <div className="flex items-center gap-2 mt-2 text-[11px] text-on-surface-variant">
              <span className="rounded-full border border-outline-variant px-2 py-0.5">{data.status}</span>
              <span>{data.issues.length} {data.issues.length === 1 ? "issue" : "issues"}</span>
              <span className="text-on-surface-variant/60">updated {data.updated_at.slice(0, 16).replace("T", " ")}</span>
            </div>
          </div>
        </div>
      </div>

      <h2 className="font-headline text-sm font-bold text-on-surface mb-3">Issues in this case</h2>
      {data.issues.length === 0 ? (
        <p className="text-sm text-on-surface-variant">No issues grouped here yet. Assign issues from an issue&apos;s detail page.</p>
      ) : (
        <div className="space-y-2">
          {data.issues.map((i) => (
            <Link
              key={i.id}
              href={`/investigation/issues/${i.id}`}
              className="block rounded-xl border border-outline-variant bg-surface-container hover:bg-surface-container-high transition p-4"
            >
              <div className="flex items-center gap-3">
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium border ${STATUS_TOKENS[i.status] ?? ""}`}>{i.status}</span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium border ${SEVERITY_TOKENS[i.severity] ?? ""}`}>{i.severity}</span>
                <span className="text-[11px] text-on-surface-variant rounded-full border border-outline-variant px-2 py-0.5">{kindLabel(i.kind)}</span>
                <span className="flex-1 truncate font-medium text-on-surface">{i.title}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
