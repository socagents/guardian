"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  getIssue,
  updateIssue,
  listCases,
  addIssueToCase,
  kindLabel,
  SEVERITY_TOKENS,
  STATUS_TOKENS,
  type IssueDetail,
  type CaseRow,
} from "@/lib/api/investigation";

/**
 * Investigation → Issue detail (v0.1.3) — the rich investigation layout.
 *
 * Header (title / status + severity controls / kind / origin / XSOAR ref /
 * case), the structured investigation fields (Summary · Scope ·
 * Recommendations · Conclusions · Next steps — operator-editable, what the
 * agent fills via issue_update), and the activity timeline (issue_events —
 * what Guardian did + found, appended via issue_add_event).
 */

const STATUSES = ["open", "investigating", "resolved", "closed"];
const SEVERITIES = ["low", "medium", "high", "critical"];

const SECTIONS: { key: keyof IssueDetail; label: string; icon: string }[] = [
  { key: "summary", label: "Summary", icon: "summarize" },
  { key: "scope", label: "Scope — what's being investigated", icon: "center_focus_strong" },
  { key: "recommendations", label: "Recommendations", icon: "lightbulb" },
  { key: "conclusions", label: "Conclusions", icon: "gavel" },
  { key: "next_steps", label: "Next steps", icon: "checklist" },
];

const EVENT_ICONS: Record<string, string> = {
  action: "bolt",
  finding: "search_insights",
  note: "sticky_note_2",
  conversation: "forum",
};

export default function IssueDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [issue, setIssue] = useState<IssueDetail | null>(null);
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [det, cl] = await Promise.all([getIssue(id), listCases()]);
      setIssue(det);
      setCases(cl.cases);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load issue");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const patch = async (body: Parameters<typeof updateIssue>[1]) => {
    if (!issue) return;
    try {
      await updateIssue(id, body);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "update failed");
    }
  };

  if (loading) return <p className="text-sm text-on-surface-variant p-8 text-center">Loading…</p>;
  if (error) return <p className="text-sm text-error p-8 text-center">{error}</p>;
  if (!issue) return <p className="text-sm text-on-surface-variant p-8 text-center">Issue not found.</p>;

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <Link href="/investigation/issues" className="text-xs text-on-surface-variant hover:text-on-surface inline-flex items-center gap-1 mb-4">
        <span className="material-symbols-outlined text-[16px]">arrow_back</span> Issues
      </Link>

      {/* Header */}
      <div className="rounded-2xl border border-outline-variant bg-surface-container p-5 mb-5">
        <div className="flex items-start gap-3">
          <span className="material-symbols-outlined text-primary mt-0.5">report</span>
          <div className="flex-1">
            <h1 className="font-headline text-xl font-bold text-on-surface">{issue.title}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-2 text-[11px]">
              <span className="rounded-full border border-outline-variant px-2 py-0.5 text-on-surface-variant">{kindLabel(issue.kind)}</span>
              <span className="rounded-full border border-outline-variant px-2 py-0.5 text-on-surface-variant">
                {issue.origin === "agent" ? "opened by Guardian" : "opened by operator"}
              </span>
              {issue.source_ref && (
                <span className="rounded-full border border-outline-variant px-2 py-0.5 text-on-surface-variant">XSOAR #{issue.source_ref}</span>
              )}
              <span className="text-on-surface-variant/60">updated {issue.updated_at.slice(0, 16).replace("T", " ")}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 mt-4">
          <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Status</label>
          <select value={issue.status} onChange={(e) => patch({ status: e.target.value as IssueDetail["status"] })} className={`rounded-full px-3 py-1 text-xs font-medium border ${STATUS_TOKENS[issue.status] ?? ""}`}>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Severity</label>
          <select value={issue.severity} onChange={(e) => patch({ severity: e.target.value as IssueDetail["severity"] })} className={`rounded-full px-3 py-1 text-xs font-medium border ${SEVERITY_TOKENS[issue.severity] ?? ""}`}>
            {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <CaseAssigner issue={issue} cases={cases} onAssigned={load} />
        </div>
      </div>

      {/* Structured investigation fields */}
      <div className="space-y-3">
        {SECTIONS.map((sec) => (
          <EditableSection
            key={sec.key as string}
            icon={sec.icon}
            label={sec.label}
            value={(issue[sec.key] as string | null) ?? ""}
            onSave={(v) => patch({ [sec.key]: v } as Parameters<typeof updateIssue>[1])}
          />
        ))}
      </div>

      {/* Activity timeline */}
      <div className="mt-6">
        <h2 className="font-headline text-sm font-bold text-on-surface mb-3 flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-primary">timeline</span>
          Activity — what Guardian did
        </h2>
        {issue.events.length === 0 ? (
          <p className="text-sm text-on-surface-variant">No activity recorded yet.</p>
        ) : (
          <ol className="space-y-2">
            {issue.events.map((ev) => (
              <li key={ev.id} className="flex gap-3 rounded-xl border border-outline-variant bg-surface-container p-3">
                <span className="material-symbols-outlined text-[18px] text-on-surface-variant mt-0.5">
                  {EVENT_ICONS[ev.type] ?? "circle"}
                </span>
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-[11px] text-on-surface-variant">
                    <span className="font-medium uppercase tracking-wide">{ev.type}</span>
                    <span>{ev.ts.slice(0, 19).replace("T", " ")}</span>
                  </div>
                  <p className="text-sm text-on-surface whitespace-pre-wrap mt-0.5">{ev.content}</p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

function EditableSection({
  icon,
  label,
  value,
  onSave,
}: {
  icon: string;
  label: string;
  value: string;
  onSave: (v: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container p-4">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-xs font-bold text-on-surface flex items-center gap-1.5">
          <span className="material-symbols-outlined text-[16px] text-on-surface-variant">{icon}</span>
          {label}
        </h3>
        {!editing && (
          <button onClick={() => setEditing(true)} className="text-[11px] text-primary hover:underline">
            edit
          </button>
        )}
      </div>
      {editing ? (
        <div className="space-y-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={4}
            autoFocus
            className="w-full bg-surface-container-highest rounded-lg px-3 py-2 text-sm outline-none text-on-surface"
            style={{ border: "0.5px solid var(--glass-border)" }}
          />
          <div className="flex justify-end gap-2">
            <button onClick={() => { setDraft(value); setEditing(false); }} className="text-[11px] text-on-surface-variant hover:underline">cancel</button>
            <button onClick={() => { onSave(draft); setEditing(false); }} className="text-[11px] text-primary font-medium hover:underline">save</button>
          </div>
        </div>
      ) : value ? (
        <p className="text-sm text-on-surface whitespace-pre-wrap">{value}</p>
      ) : (
        <p className="text-sm text-on-surface-variant/50 italic">—</p>
      )}
    </div>
  );
}

function CaseAssigner({ issue, cases, onAssigned }: { issue: IssueDetail; cases: CaseRow[]; onAssigned: () => void }) {
  const assign = async (caseId: string) => {
    if (!caseId) return;
    await addIssueToCase(caseId, issue.id);
    onAssigned();
  };
  return (
    <div className="flex items-center gap-2 ml-auto">
      <label className="text-[10px] uppercase tracking-widest text-on-surface-variant">Case</label>
      {issue.case ? (
        <Link href={`/investigation/cases/${issue.case.id}`} className="text-xs text-primary hover:underline rounded-full border border-primary/40 bg-primary/10 px-3 py-1">
          {issue.case.title}
        </Link>
      ) : (
        <select
          defaultValue=""
          onChange={(e) => assign(e.target.value)}
          className="rounded-full px-3 py-1 text-xs border border-outline-variant text-on-surface-variant bg-surface-container-high"
        >
          <option value="">unassigned…</option>
          {cases.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
        </select>
      )}
    </div>
  );
}
