"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  listIssues,
  createIssue,
  kindLabel,
  SEVERITY_TOKENS,
  STATUS_TOKENS,
  type Issue,
} from "@/lib/api/investigation";

/**
 * Investigation → Issues (v0.1.3).
 *
 * Lists the local Issues Guardian (origin=agent) and the operator
 * (origin=operator) open during investigations. Click an issue for the
 * rich detail layout. "New Issue" lets the operator open one by hand; the
 * agent opens them via the issue_create MCP tool during investigations.
 */

const STATUSES = ["", "open", "investigating", "resolved", "closed"];
const KINDS = ["phishing", "lateral_movement", "access_violation", "malware", "other"];
const SEVERITIES = ["low", "medium", "high", "critical"];

export default function IssuesPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { issues } = await listIssues(statusFilter ? { status: statusFilter } : undefined);
      setIssues(issues);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load issues");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="font-headline text-2xl font-bold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">report</span>
            Issues
          </h1>
          <p className="text-sm text-on-surface-variant mt-1">
            Guardian&apos;s local investigation records. The agent opens these while
            investigating; you can open them by hand too.
          </p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="inline-flex items-center gap-1.5 rounded-xl bg-primary text-on-primary px-4 py-2 text-sm font-medium hover:opacity-90 transition"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
          New Issue
        </button>
      </div>

      <div className="flex items-center gap-2 mb-5 mt-4">
        {STATUSES.map((s) => (
          <button
            key={s || "all"}
            onClick={() => setStatusFilter(s)}
            className={`rounded-full px-3 py-1 text-xs font-medium border transition ${
              statusFilter === s
                ? "border-primary text-primary bg-primary/10"
                : "border-outline-variant text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            {s ? s : "all"}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-on-surface-variant py-12 text-center">Loading…</p>
      ) : error ? (
        <p className="text-sm text-error py-12 text-center">{error}</p>
      ) : issues.length === 0 ? (
        <div className="rounded-2xl border border-outline-variant bg-surface-container p-12 text-center">
          <span className="material-symbols-outlined text-4xl text-on-surface-variant/50">report</span>
          <p className="text-sm text-on-surface-variant mt-2">
            No issues yet. Ask Guardian to investigate an incident, or create one.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {issues.map((i) => (
            <Link
              key={i.id}
              href={`/investigation/issues/${i.id}`}
              className="block rounded-xl border border-outline-variant bg-surface-container hover:bg-surface-container-high transition p-4"
            >
              <div className="flex items-center gap-3">
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium border ${STATUS_TOKENS[i.status] ?? ""}`}>
                  {i.status}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium border ${SEVERITY_TOKENS[i.severity] ?? ""}`}>
                  {i.severity}
                </span>
                <span className="text-[11px] text-on-surface-variant rounded-full border border-outline-variant px-2 py-0.5">
                  {kindLabel(i.kind)}
                </span>
                <span className="flex-1 truncate font-medium text-on-surface">{i.title}</span>
                {i.source_ref && (
                  <span className="text-[11px] text-on-surface-variant">XSOAR #{i.source_ref}</span>
                )}
                <span className="text-[11px] text-on-surface-variant/70">
                  {i.origin === "agent" ? "🤖" : "👤"} {i.updated_at.slice(0, 16).replace("T", " ")}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {showNew && (
        <NewIssueModal
          onClose={() => setShowNew(false)}
          onCreated={() => {
            setShowNew(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function NewIssueModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("other");
  const [severity, setSeverity] = useState("medium");
  const [scope, setScope] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!title.trim()) return;
    setSaving(true);
    setErr(null);
    try {
      await createIssue({ title: title.trim(), kind, severity, scope: scope || undefined });
      onCreated();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed");
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-2xl bg-surface-container-high border border-outline-variant p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-headline text-lg font-bold text-on-surface">New Issue</h2>
        <div className="space-y-1">
          <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            autoFocus
            className="w-full bg-surface-container-highest rounded-xl px-4 py-3 text-sm outline-none text-on-surface"
            style={{ border: "0.5px solid var(--glass-border)" }}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Kind</label>
            <select value={kind} onChange={(e) => setKind(e.target.value)} className="w-full bg-surface-container-highest rounded-xl px-3 py-3 text-sm text-on-surface" style={{ border: "0.5px solid var(--glass-border)" }}>
              {KINDS.map((k) => <option key={k} value={k}>{kindLabel(k)}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Severity</label>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="w-full bg-surface-container-highest rounded-xl px-3 py-3 text-sm text-on-surface" style={{ border: "0.5px solid var(--glass-border)" }}>
              {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>
        <div className="space-y-1">
          <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Scope (what to investigate)</label>
          <textarea
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            rows={3}
            className="w-full bg-surface-container-highest rounded-xl px-4 py-3 text-sm outline-none text-on-surface"
            style={{ border: "0.5px solid var(--glass-border)" }}
          />
        </div>
        {err && <p className="text-xs text-error">{err}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="rounded-xl px-4 py-2 text-sm text-on-surface-variant hover:bg-surface-container-highest transition">Cancel</button>
          <button onClick={submit} disabled={saving || !title.trim()} className="rounded-xl bg-primary text-on-primary px-4 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition">
            {saving ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
