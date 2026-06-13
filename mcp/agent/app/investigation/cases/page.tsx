"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { listCases, createCase, type CaseRow } from "@/lib/api/investigation";
import { glassStyle, StatCard, EmptyState } from "@/components/investigation/ui";

/**
 * Investigation → Cases (v0.1.7 — full-width glass layout).
 *
 * Cases group related Issues (same campaign / actor / root cause). The agent
 * groups Issues via case_create + case_add_issue while investigating; the
 * operator can create cases here. Matches the skills/jobs page standard.
 */
export default function CasesPage() {
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { cases } = await listCases();
      setCases(cases);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load cases");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const totalIssues = useMemo(
    () => cases.reduce((n, c) => n + (c.issue_count ?? 0), 0),
    [cases],
  );

  return (
    <div className="max-w-[1400px] mx-auto px-8 py-8 pb-32 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
        <div>
          <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-2xl text-primary">cases</span>
            Cases
          </h1>
          <p className="text-sm text-on-surface-variant mt-1 ml-9">
            Groups of related Issues — a campaign, an actor, or a shared root cause. Guardian groups them while investigating; you can too.
          </p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="inline-flex items-center gap-1.5 rounded-xl bg-primary text-on-primary px-4 py-2.5 text-sm font-medium hover:opacity-90 transition self-start"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
          New Case
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard icon="cases" label="Cases" value={cases.length} tone="bg-primary/15 text-primary" />
        <StatCard icon="report" label="Grouped issues" value={totalIssues} tone="bg-tertiary/15 text-tertiary" />
        <StatCard
          icon="dataset_linked"
          label="Avg issues / case"
          value={cases.length ? (totalIssues / cases.length).toFixed(1) : "0"}
          tone="bg-secondary/15 text-secondary"
        />
      </div>

      {/* List */}
      {loading ? (
        <p className="text-sm text-on-surface-variant py-12 text-center">Loading…</p>
      ) : error ? (
        <p className="text-sm text-error py-12 text-center">{error}</p>
      ) : cases.length === 0 ? (
        <EmptyState
          icon="cases"
          title="No cases yet"
          hint="When two or more Issues share a campaign, actor, or root cause, group them into a Case — Guardian does this automatically, or you can create one."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {cases.map((c) => (
            <Link
              key={c.id}
              href={`/investigation/cases/${c.id}`}
              className="rounded-2xl p-5 transition-all hover:shadow-[0_0_20px_rgba(25,99,179,0.1)]"
              style={glassStyle}
            >
              <div className="flex items-start gap-3">
                <span className="material-symbols-outlined text-[22px] text-primary mt-0.5 shrink-0">folder_special</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-on-surface truncate">{c.title}</span>
                    <span className="text-[10px] uppercase tracking-wide font-bold rounded-full border border-outline-variant px-2 py-0.5 text-on-surface-variant whitespace-nowrap">
                      {c.issue_count ?? 0} {(c.issue_count ?? 0) === 1 ? "issue" : "issues"}
                    </span>
                  </div>
                  {c.description && <p className="text-xs text-on-surface-variant mt-1.5 line-clamp-2 leading-relaxed">{c.description}</p>}
                  <p className="text-[11px] text-on-surface-variant/60 mt-3">updated {c.updated_at.slice(0, 16).replace("T", " ")}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {showNew && (
        <NewCaseModal onClose={() => setShowNew(false)} onCreated={() => { setShowNew(false); load(); }} />
      )}
    </div>
  );
}

function NewCaseModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!title.trim()) return;
    setSaving(true);
    setErr(null);
    try {
      await createCase({ title: title.trim(), description: description || undefined });
      onCreated();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed");
      setSaving(false);
    }
  };

  const fieldStyle = { border: "0.5px solid var(--glass-border)" };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px] p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-2xl p-6 space-y-4"
        style={{ background: "var(--glass-bg)", backdropFilter: "blur(16px)", border: "0.5px solid var(--glass-border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-headline text-lg font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">create_new_folder</span>
          New Case
        </h2>
        <div className="space-y-1">
          <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Title</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus className="w-full bg-surface-container-highest rounded-xl px-4 py-3 text-sm outline-none text-on-surface focus:ring-1 focus:ring-primary/40" style={fieldStyle} />
        </div>
        <div className="space-y-1">
          <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Description</label>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="w-full bg-surface-container-highest rounded-xl px-4 py-3 text-sm outline-none text-on-surface focus:ring-1 focus:ring-primary/40" style={fieldStyle} />
        </div>
        {err && <p className="text-xs text-error">{err}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="rounded-xl px-4 py-2 text-sm text-on-surface-variant hover:bg-surface-container-highest transition">Cancel</button>
          <button onClick={submit} disabled={saving || !title.trim()} className="rounded-xl bg-primary text-on-primary px-4 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition">{saving ? "Creating…" : "Create"}</button>
        </div>
      </div>
    </div>
  );
}
