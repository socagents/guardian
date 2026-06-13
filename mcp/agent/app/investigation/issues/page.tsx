"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  listIssues,
  createIssue,
  kindLabel,
  type Issue,
} from "@/lib/api/investigation";
import {
  glassStyle,
  IssueRow,
  StatCard,
  EmptyState,
} from "@/components/investigation/ui";

/**
 * Investigation → Issues (v0.1.7 — full-width glass layout).
 *
 * Lists the local Issues Guardian (origin=agent) and the operator open
 * during investigations. Matches the skills/jobs page standard: max-w-[1400px]
 * container, summary stat cards, filter chips, glass rows. Click a row for the
 * tabbed detail. "New Issue" opens one by hand; the agent opens them via the
 * issue_create MCP tool while investigating.
 */

const STATUS_FILTERS = ["", "open", "investigating", "resolved", "closed"];
const KINDS = ["phishing", "lateral_movement", "access_violation", "malware", "other"];
const SEVERITIES = ["low", "medium", "high", "critical"];

export default function IssuesPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [showNew, setShowNew] = useState(false);

  // Fetch the FULL corpus once; the status filter narrows the displayed list
  // client-side. This keeps the summary stats system-wide accurate (a filter
  // never makes "Total" mean "Total open").
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { issues } = await listIssues();
      setIssues(issues);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load issues");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const stats = useMemo(() => {
    const by = (s: string) => issues.filter((i) => i.status === s).length;
    return {
      total: issues.length,
      open: by("open"),
      investigating: by("investigating"),
      resolved: by("resolved") + by("closed"),
    };
  }, [issues]);

  const filtered = useMemo(
    () => (statusFilter ? issues.filter((i) => i.status === statusFilter) : issues),
    [issues, statusFilter],
  );

  return (
    <div className="max-w-[1400px] mx-auto px-8 py-8 pb-32 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
        <div>
          <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-2xl text-primary">report</span>
            Issues
          </h1>
          <p className="text-sm text-on-surface-variant mt-1 ml-9">
            Guardian&apos;s local investigation records — the agent opens these while it works a case; you can open one by hand too.
          </p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="inline-flex items-center gap-1.5 rounded-xl bg-primary text-on-primary px-4 py-2.5 text-sm font-medium hover:opacity-90 transition self-start"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
          New Issue
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon="inventory_2" label="Total" value={stats.total} tone="bg-primary/15 text-primary" />
        <StatCard icon="folder_open" label="Open" value={stats.open} tone="bg-primary/15 text-primary" />
        <StatCard icon="frame_inspect" label="Investigating" value={stats.investigating} tone="bg-tertiary/15 text-tertiary" />
        <StatCard icon="task_alt" label="Resolved" value={stats.resolved} tone="bg-secondary/15 text-secondary" />
      </div>

      {/* Filter chips */}
      <div className="flex items-center gap-1.5 rounded-2xl p-1.5 w-fit" style={glassStyle}>
        {STATUS_FILTERS.map((s) => (
          <button
            key={s || "all"}
            onClick={() => setStatusFilter(s)}
            className={`rounded-lg px-3 py-1.5 text-[11px] uppercase tracking-wider font-medium transition ${
              statusFilter === s
                ? "bg-secondary-container/40 border border-secondary/40 text-secondary"
                : "border border-transparent text-on-surface-variant hover:text-on-surface hover:bg-white/5"
            }`}
          >
            {s || "all"}
          </button>
        ))}
      </div>

      {/* List */}
      {loading ? (
        <p className="text-sm text-on-surface-variant py-12 text-center">Loading…</p>
      ) : error ? (
        <p className="text-sm text-error py-12 text-center">{error}</p>
      ) : issues.length === 0 ? (
        <EmptyState
          icon="report"
          title="No issues yet"
          hint="Ask Guardian to investigate an incident, or create one by hand. Investigations the agent runs land here automatically."
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="filter_alt_off"
          title={`No ${statusFilter} issues`}
          hint="No issues match this filter — clear it to see all."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filtered.map((i) => (
            <IssueRow key={i.id} issue={i} />
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

  const fieldStyle = { border: "0.5px solid var(--glass-border)" };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px] p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-2xl p-6 space-y-4"
        style={{ background: "var(--glass-bg)", backdropFilter: "blur(16px)", border: "0.5px solid var(--glass-border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-headline text-lg font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">add_circle</span>
          New Issue
        </h2>
        <div className="space-y-1">
          <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            autoFocus
            className="w-full bg-surface-container-highest rounded-xl px-4 py-3 text-sm outline-none text-on-surface focus:ring-1 focus:ring-primary/40"
            style={fieldStyle}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Kind</label>
            <select value={kind} onChange={(e) => setKind(e.target.value)} className="w-full bg-surface-container-highest rounded-xl px-3 py-3 text-sm text-on-surface" style={fieldStyle}>
              {KINDS.map((k) => <option key={k} value={k}>{kindLabel(k)}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Severity</label>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="w-full bg-surface-container-highest rounded-xl px-3 py-3 text-sm text-on-surface" style={fieldStyle}>
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
            className="w-full bg-surface-container-highest rounded-xl px-4 py-3 text-sm outline-none text-on-surface focus:ring-1 focus:ring-primary/40"
            style={fieldStyle}
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
