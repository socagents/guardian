"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { listCases, createCase, type CaseRow } from "@/lib/api/investigation";

/**
 * Investigation → Cases (v0.1.3).
 *
 * Cases group related Issues (same campaign / actor / root cause). The agent
 * groups Issues via case_create + case_add_issue during investigations; the
 * operator can create cases here.
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

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="font-headline text-2xl font-bold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">cases</span>
            Cases
          </h1>
          <p className="text-sm text-on-surface-variant mt-1">
            Groups of related Issues. Guardian groups them during investigations; you can too.
          </p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="inline-flex items-center gap-1.5 rounded-xl bg-primary text-on-primary px-4 py-2 text-sm font-medium hover:opacity-90 transition"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
          New Case
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-on-surface-variant py-12 text-center">Loading…</p>
      ) : error ? (
        <p className="text-sm text-error py-12 text-center">{error}</p>
      ) : cases.length === 0 ? (
        <div className="rounded-2xl border border-outline-variant bg-surface-container p-12 text-center">
          <span className="material-symbols-outlined text-4xl text-on-surface-variant/50">cases</span>
          <p className="text-sm text-on-surface-variant mt-2">No cases yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {cases.map((c) => (
            <Link
              key={c.id}
              href={`/investigation/cases/${c.id}`}
              className="rounded-xl border border-outline-variant bg-surface-container hover:bg-surface-container-high transition p-4"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-on-surface">{c.title}</span>
                <span className="text-[11px] rounded-full border border-outline-variant px-2 py-0.5 text-on-surface-variant">
                  {c.issue_count ?? 0} {(c.issue_count ?? 0) === 1 ? "issue" : "issues"}
                </span>
              </div>
              {c.description && <p className="text-xs text-on-surface-variant mt-1 line-clamp-2">{c.description}</p>}
              <p className="text-[11px] text-on-surface-variant/60 mt-2">updated {c.updated_at.slice(0, 16).replace("T", " ")}</p>
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-2xl bg-surface-container-high border border-outline-variant p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="font-headline text-lg font-bold text-on-surface">New Case</h2>
        <div className="space-y-1">
          <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Title</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus className="w-full bg-surface-container-highest rounded-xl px-4 py-3 text-sm outline-none text-on-surface" style={{ border: "0.5px solid var(--glass-border)" }} />
        </div>
        <div className="space-y-1">
          <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Description</label>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="w-full bg-surface-container-highest rounded-xl px-4 py-3 text-sm outline-none text-on-surface" style={{ border: "0.5px solid var(--glass-border)" }} />
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
