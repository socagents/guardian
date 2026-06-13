"use client";

/**
 * Shared Investigation UI primitives (v0.1.7).
 *
 * One home for the glass-card styling, badges, stat cards, the reusable
 * issue row, the issue-detail tab bar, and the editable field card — so the
 * Issues + Cases list and detail pages stay visually consistent and match
 * the skills/jobs full-width standard (max-w-[1400px], glass morphism,
 * Material-3 semantic tokens). No hex literals; theme-aware tokens only.
 */

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import {
  SEVERITY_TOKENS,
  STATUS_TOKENS,
  kindLabel,
  type Issue,
} from "@/lib/api/investigation";

/** The glass effect skills/jobs use, verbatim (mirrors app/jobs/page.tsx). */
export const glassStyle = {
  background: "var(--glass-bg)",
  backdropFilter: "blur(12px)",
  border: "0.5px solid var(--glass-border)",
} as const;

/** Material-symbol per incident kind — gives each row a recognizable glyph. */
export const KIND_ICON: Record<string, string> = {
  phishing: "phishing",
  lateral_movement: "lan",
  access_violation: "key",
  malware: "bug_report",
  other: "report",
};

/** Compact, human timestamp ("2026-06-13 00:30"). */
export function fmtTs(ts: string): string {
  return ts ? ts.slice(0, 16).replace("T", " ") : "";
}

/**
 * Pull a leading `VERDICT: …` line out of a summary so the detail page can
 * render the disposition as a banner and the prose separately. Returns the
 * raw summary as `body` when no verdict line is present.
 */
export function splitVerdict(summary: string | null): { verdict: string | null; body: string } {
  const s = (summary ?? "").trim();
  if (/^verdict:/i.test(s)) {
    const nl = s.indexOf("\n");
    const line = nl === -1 ? s : s.slice(0, nl);
    const rest = nl === -1 ? "" : s.slice(nl + 1).trim();
    return { verdict: line.replace(/^verdict:\s*/i, "").trim(), body: rest };
  }
  return { verdict: null, body: s };
}

/** A tone that maps a verdict string to a Material-3 token set. */
export function verdictTone(verdict: string): string {
  const v = verdict.toLowerCase();
  if (v.startsWith("true positive")) return "text-error border-error/40 bg-error/10";
  if (v.startsWith("false positive") || v.startsWith("benign")) return "text-on-surface-variant border-outline-variant bg-surface-container-high";
  if (v.startsWith("needs escalation")) return "text-tertiary border-tertiary/40 bg-tertiary/10";
  return "text-primary border-primary/40 bg-primary/10";
}

export function Badge({ tone, children }: { tone?: string; children: ReactNode }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide border whitespace-nowrap ${
        tone ?? "border-outline-variant text-on-surface-variant"
      }`}
    >
      {children}
    </span>
  );
}

export function OriginChip({ origin }: { origin: "agent" | "operator" }) {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-on-surface-variant">
      <span className="material-symbols-outlined text-[14px]">
        {origin === "agent" ? "smart_toy" : "person"}
      </span>
      {origin === "agent" ? "Guardian" : "Operator"}
    </span>
  );
}

export function StatCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: string;
  label: string;
  value: number | string;
  tone?: string;
}) {
  return (
    <div className="p-5 rounded-2xl flex items-center gap-4" style={glassStyle}>
      <div className={`h-12 w-12 rounded-xl flex items-center justify-center shrink-0 ${tone ?? "bg-primary/15 text-primary"}`}>
        <span className="material-symbols-outlined text-[22px]">{icon}</span>
      </div>
      <div className="min-w-0">
        <div className="font-headline text-2xl font-bold text-on-surface leading-none">{value}</div>
        <div className="text-[11px] uppercase tracking-widest text-on-surface-variant mt-1 truncate">{label}</div>
      </div>
    </div>
  );
}

/** The reusable issue list row — used by the Issues list AND the Case detail. */
export function IssueRow({ issue }: { issue: Issue }) {
  const { verdict } = splitVerdict(issue.summary);
  return (
    <Link
      href={`/investigation/issues/${issue.id}`}
      className="block rounded-xl p-5 transition-all hover:shadow-[0_0_20px_rgba(25,99,179,0.1)]"
      style={glassStyle}
    >
      <div className="flex items-start gap-4">
        <span className="material-symbols-outlined text-[22px] text-on-surface-variant/70 mt-0.5 shrink-0">
          {KIND_ICON[issue.kind] ?? "report"}
        </span>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-on-surface truncate">{issue.title}</p>
          <div className="flex items-center gap-2 mt-2 flex-wrap text-[11px] text-on-surface-variant">
            <Badge tone={STATUS_TOKENS[issue.status]}>{issue.status}</Badge>
            <Badge tone={SEVERITY_TOKENS[issue.severity]}>{issue.severity}</Badge>
            <Badge>{kindLabel(issue.kind)}</Badge>
            <OriginChip origin={issue.origin} />
            {issue.source_ref && (
              <span className="inline-flex items-center gap-0.5">
                <span className="material-symbols-outlined text-[13px]">tag</span>
                XSOAR {issue.source_ref}
              </span>
            )}
            {verdict && (
              <span className="inline-flex items-center gap-1 text-on-surface-variant/80">
                <span className="material-symbols-outlined text-[13px]">gavel</span>
                {verdict.length > 48 ? `${verdict.slice(0, 48)}…` : verdict}
              </span>
            )}
          </div>
        </div>
        <span className="text-[11px] text-on-surface-variant/60 whitespace-nowrap mt-0.5 hidden sm:block">
          {fmtTs(issue.updated_at)}
        </span>
        <span className="material-symbols-outlined text-on-surface-variant/40 mt-0.5">chevron_right</span>
      </div>
    </Link>
  );
}

/** Stateful tab bar (mirrors the AgentTabBar pattern) for the issue detail. */
export function InvestigationTabBar<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: T; label: string; icon: string }[];
  active: T;
  onChange: (t: T) => void;
}) {
  return (
    <nav className="flex items-center gap-6 border-b border-white/10 mb-6 overflow-x-auto">
      {tabs.map((t) => {
        const isActive = t.key === active;
        return (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(t.key)}
            className={`relative flex items-center gap-1.5 pb-3 text-sm font-label uppercase tracking-widest transition-colors whitespace-nowrap ${
              isActive
                ? "text-secondary border-b-2 border-secondary font-bold"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">{t.icon}</span>
            {t.label}
          </button>
        );
      })}
    </nav>
  );
}

/** An operator-editable investigation field rendered inside a glass card. */
export function EditableSection({
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
    <div className="rounded-2xl p-5" style={glassStyle}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-bold uppercase tracking-widest text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-on-surface-variant">{icon}</span>
          {label}
        </h3>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
          >
            <span className="material-symbols-outlined text-[14px]">edit</span>
            edit
          </button>
        )}
      </div>
      {editing ? (
        <div className="space-y-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={6}
            autoFocus
            className="w-full bg-surface-container-highest rounded-xl px-4 py-3 text-sm outline-none text-on-surface focus:ring-1 focus:ring-primary/40"
            style={{ border: "0.5px solid var(--glass-border)" }}
          />
          <div className="flex justify-end gap-3">
            <button
              onClick={() => {
                setDraft(value);
                setEditing(false);
              }}
              className="text-[11px] text-on-surface-variant hover:underline"
            >
              cancel
            </button>
            <button
              onClick={() => {
                onSave(draft);
                setEditing(false);
              }}
              className="text-[11px] text-primary font-medium hover:underline"
            >
              save
            </button>
          </div>
        </div>
      ) : value ? (
        <p className="text-sm text-on-surface whitespace-pre-wrap leading-relaxed">{value}</p>
      ) : (
        <p className="text-sm text-on-surface-variant/50 italic">Not recorded yet.</p>
      )}
    </div>
  );
}

/** A centered empty/placeholder state inside a glass card. */
export function EmptyState({
  icon,
  title,
  hint,
  children,
}: {
  icon: string;
  title: string;
  hint?: string;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-2xl p-12 text-center flex flex-col items-center gap-2" style={glassStyle}>
      <span className="material-symbols-outlined text-5xl text-on-surface-variant/40">{icon}</span>
      <p className="font-headline text-base text-on-surface mt-1">{title}</p>
      {hint && <p className="text-sm text-on-surface-variant max-w-md">{hint}</p>}
      {children}
    </div>
  );
}
