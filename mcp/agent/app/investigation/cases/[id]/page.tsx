"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { getCase, SEVERITY_TOKENS, type CaseDetail } from "@/lib/api/investigation";
import {
  glassStyle,
  Badge,
  IssueRow,
  InvestigationTabBar,
  DiagramTab,
  EmptyState,
  fmtTs,
} from "@/components/investigation/ui";
import { MarkdownContent } from "@/components/markdown-content";

/**
 * Investigation → Case detail (v0.1.7 full-width; v0.2.2 tabbed + diagrams).
 *
 * Case metadata over a tabbed body: Issues (the issues grouped under the
 * case), Attack chain (the campaign-level causality SVG), and Relations (the
 * campaign-level STIX graph). Both diagrams are generated on demand by the
 * agent — the case-level companions to the per-issue diagrams — synthesizing
 * across ALL the case's issues.
 */

type Tab = "issues" | "campaign" | "chain" | "relations";
const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "issues", label: "Issues", icon: "report" },
  { key: "campaign", label: "Campaign", icon: "groups" },
  { key: "chain", label: "Attack chain", icon: "account_tree" },
  { key: "relations", label: "Relations", icon: "hub" },
];

/** Parse a JSON array string (techniques) → string[]; tolerant of null/garbage. */
function parseStrList(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const a = JSON.parse(raw);
    return Array.isArray(a) ? a.map(String) : [];
  } catch {
    return [];
  }
}

/** Parse the infrastructure JSON → its shared_indicators list. */
function parseSharedIndicators(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const o = JSON.parse(raw);
    return Array.isArray(o?.shared_indicators) ? o.shared_indicators.map(String) : [];
  } catch {
    return [];
  }
}

export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [data, setData] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("issues");
  // null = idle; otherwise the diagram kind currently regenerating.
  const [regenerating, setRegenerating] = useState<null | "chain" | "relations">(null);
  // v0.2.47 — true while a one-shot case_rollup job is in flight.
  const [rollingUp, setRollingUp] = useState(false);

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

  // Regenerate a campaign-level diagram: fire a one-shot agent job (the same
  // scheduler pattern as the issue diagrams) that reads the case + its issues
  // and draws the synthesized SVG via the matching skill, then poll the case
  // until the relevant SVG field changes. Heavy op (a full agent turn).
  const regenerate = async (kind: "chain" | "relations") => {
    if (!data || regenerating) return;
    setRegenerating(kind);
    const isChain = kind === "chain";
    const before = (isChain ? data.attack_chain_svg : data.relations_canvas_svg) ?? "";
    const skill = isChain ? "svg_attack_chain" : "svg_relation_graph";
    const message = isChain
      ? `Regenerate the campaign-level attack chain for Guardian Case ${id}. ` +
        `First call case_get(case_id="${id}") to read the case + its issues, then ` +
        `read each issue's conclusions/activity. Per the svg_attack_chain skill's ` +
        `case-level (campaign) variant, draw ONE self-contained SVG synthesizing the ` +
        `attack across the case's issues and store it with ` +
        `case_set_attack_chain(case_id="${id}", svg="<the full svg>"). ` +
        `Do only this — do not change any other field.`
      : `Regenerate the campaign-level STIX relations canvas for Guardian Case ${id}. ` +
        `First call case_get(case_id="${id}") to read the case + its issues, then ` +
        `indicators_list(issue_id=…) + indicator_get(id) across the issues to gather ` +
        `the union of indicators and their relationships. Per the svg_relation_graph ` +
        `skill's case-level (campaign) variant, draw ONE self-contained layered SVG of ` +
        `the campaign's indicators and their STIX relationships and store it with ` +
        `case_set_relation_graph(case_id="${id}", svg="<the full svg>"). ` +
        `Do only this — do not change any other field.`;
    try {
      // Unique suffix avoids colliding with a prior one-shot job (scheduler
      // 400s on a duplicate name — the v0.2.3 silent-spinner trigger).
      const resp = await fetch("/api/agent/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `regen-case-${kind}-${id}-${before.length}`,
          cron: "* * * * *",
          timezone: "UTC",
          run_once: true,
          enabled: true,
          bypass_approvals: true,
          action: { type: "prompt", skill, message },
        }),
      });
      // fetch() does NOT throw on 4xx/5xx — check explicitly so a failed job
      // surfaces an error instead of a silent 3-minute poll to the deadline.
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error((detail as { error?: string })?.error ?? `regenerate failed (${resp.status})`);
      }
      const deadline = Date.now() + 180_000;
      let updated = false;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 5000));
        try {
          const det = await getCase(id);
          const now = (isChain ? det.attack_chain_svg : det.relations_canvas_svg) ?? "";
          if (now && now !== before) {
            setData(det);
            updated = true;
            break;
          }
        } catch {
          /* transient — keep polling */
        }
      }
      if (!updated) {
        try { setData(await getCase(id)); } catch { /* ignore */ }
        setError("Regenerate timed out — the diagram may not have updated (the agent run may have failed). Try again.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "regenerate failed");
    } finally {
      setRegenerating(null);
    }
  };

  // v0.2.47 — roll up the campaign on demand: a one-shot agent job that calls
  // case_rollup (synthesizes the technique union / shared infrastructure /
  // severity / verdict mix from member issues) + infer_relationships, then poll
  // the case until the rollup populates. Mirrors the diagram-regenerate pattern.
  const runRollup = async () => {
    if (!data || rollingUp) return;
    setRollingUp(true);
    const before = data.campaign_summary ?? "";
    const message =
      `Roll up the campaign for Guardian Case ${id}. Call ` +
      `case_rollup(case_id="${id}") to synthesize the ATT&CK technique union, ` +
      `shared infrastructure, max severity, and verdict mix from the member issues ` +
      `and persist it on the case. Then call infer_relationships(issue_id="<a member ` +
      `issue id from case_get>") to surface sibling issues/cases — if a clear prior ` +
      `related campaign exists, SUGGEST a case_relate (do not auto-create it). Report ` +
      `what you rolled up. Do only this — change no other field.`;
    try {
      const resp = await fetch("/api/agent/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `case-rollup-${id}-${before.length}`,
          cron: "* * * * *",
          timezone: "UTC",
          run_once: true,
          enabled: true,
          bypass_approvals: true,
          action: { type: "prompt", skill: "xsoar_case_investigation", message },
        }),
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error((detail as { error?: string })?.error ?? `rollup failed (${resp.status})`);
      }
      const deadline = Date.now() + 180_000;
      let updated = false;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 5000));
        try {
          const det = await getCase(id);
          if ((det.campaign_summary ?? "") !== before || det.techniques) {
            setData(det);
            updated = true;
            break;
          }
        } catch {
          /* transient — keep polling */
        }
      }
      if (!updated) {
        try { setData(await getCase(id)); } catch { /* ignore */ }
        setError("Rollup timed out — the agent run may have failed. Try again.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "rollup failed");
    } finally {
      setRollingUp(false);
    }
  };

  if (loading) return <p className="text-sm text-on-surface-variant p-8 text-center">Loading…</p>;
  if (error) return <p className="text-sm text-error p-8 text-center">{error}</p>;
  if (!data) return <p className="text-sm text-on-surface-variant p-8 text-center">Case not found.</p>;

  const campaignTechniques = parseStrList(data.techniques);
  const sharedInfra = parseSharedIndicators(data.infrastructure);
  const hasRollup = !!(data.campaign_summary || campaignTechniques.length || sharedInfra.length);

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

      {/* Tabs */}
      <InvestigationTabBar tabs={TABS} active={tab} onChange={setTab} />

      {tab === "issues" && (
        data.issues.length === 0 ? (
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
        )
      )}

      {tab === "campaign" && (
        <div className="grid grid-cols-1 gap-4">
          <div className="flex justify-end">
            <button
              onClick={runRollup}
              disabled={rollingUp}
              className="inline-flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/10 px-3 py-1.5 text-[11px] font-medium text-primary hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className={`material-symbols-outlined text-[14px] ${rollingUp ? "animate-spin" : ""}`}>
                {rollingUp ? "progress_activity" : hasRollup ? "refresh" : "auto_awesome"}
              </span>
              {rollingUp ? "Rolling up…" : hasRollup ? "Re-roll up" : "Roll up campaign"}
            </button>
          </div>

          {!hasRollup ? (
            <EmptyState
              icon="groups"
              title="No campaign rollup yet"
              hint="A campaign rollup synthesizes the member issues into one picture — the ATT&CK technique union, the shared infrastructure, the max severity, and the verdict mix. Click Roll up campaign (a full agent pass — about a minute), or Guardian rolls it up when it resolves an issue that belongs to a campaign."
            />
          ) : (
            <>
              <div className="rounded-2xl p-5" style={glassStyle}>
                <div className="flex items-center gap-2 mb-3">
                  <span className="material-symbols-outlined text-[18px] text-on-surface-variant">groups</span>
                  <span className="text-[10px] uppercase tracking-widest text-on-surface-variant">Campaign</span>
                </div>
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  {data.severity_rollup && (
                    <Badge tone={SEVERITY_TOKENS[data.severity_rollup as keyof typeof SEVERITY_TOKENS]}>
                      {data.severity_rollup}
                    </Badge>
                  )}
                  {data.threat_actor && (
                    <span className="inline-flex items-center gap-1 rounded-lg border border-tertiary/40 bg-tertiary/10 px-2.5 py-1 text-[11px] text-tertiary">
                      <span className="material-symbols-outlined text-[14px]">person_alert</span>
                      {data.threat_actor}
                    </span>
                  )}
                  <span className="text-[11px] text-on-surface-variant/70">{data.issues.length} member issue(s)</span>
                </div>
                {data.campaign_summary && (
                  <p className="text-sm text-on-surface">{data.campaign_summary}</p>
                )}
              </div>

              {campaignTechniques.length > 0 && (
                <div className="rounded-2xl p-5" style={glassStyle}>
                  <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-3">ATT&amp;CK techniques (union)</div>
                  <div className="flex flex-wrap gap-2">
                    {campaignTechniques.map((t) => (
                      <Link
                        key={t}
                        href={`/investigation/issues`}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-tertiary/40 bg-tertiary/10 px-2.5 py-1 text-[11px] text-tertiary font-mono"
                      >
                        <span className="material-symbols-outlined text-[14px]">lan</span>{t}
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {sharedInfra.length > 0 && (
                <div className="rounded-2xl p-5" style={glassStyle}>
                  <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-3">Shared infrastructure (IOCs on ≥2 issues)</div>
                  <div className="flex flex-wrap gap-1.5">
                    {sharedInfra.map((v) => (
                      <span key={v} className="rounded-md bg-surface-container-highest border border-outline-variant px-2 py-0.5 text-[11px] font-mono text-on-surface">
                        {v}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {data.related.length > 0 && (
                <div className="rounded-2xl p-5" style={glassStyle}>
                  <div className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-3">Related cases</div>
                  <div className="grid grid-cols-1 gap-2">
                    {data.related.map((r, i) => (
                      <div key={i} className="flex flex-wrap items-center gap-2 text-sm">
                        <Badge>{r.relationship_type}</Badge>
                        <span className="text-[11px] text-on-surface-variant/60">{r.direction}</span>
                        {r.other_case ? (
                          <Link href={`/investigation/cases/${r.other_case.id}`} className="text-secondary hover:underline">
                            {r.other_case.title ?? r.other_case.id}
                          </Link>
                        ) : (
                          <span className="text-on-surface-variant/60">(case deleted)</span>
                        )}
                        {r.note && <span className="text-[11px] text-on-surface-variant/70">— {r.note}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {tab === "chain" && (
        <DiagramTab
          svg={data.attack_chain_svg}
          icon="account_tree"
          title="Campaign attack chain"
          alt="Campaign attack-chain diagram"
          emptyHint="The campaign-level attack chain synthesizes the attack across ALL issues in this case (shared actor / infrastructure / kill-chain). Generate it on demand — a full agent pass over the case's issues (about a minute)."
          busy={regenerating === "chain"}
          disabled={regenerating !== null}
          onRegenerate={() => regenerate("chain")}
        />
      )}

      {tab === "relations" && (
        <DiagramTab
          svg={data.relations_canvas_svg}
          icon="hub"
          title="Campaign relations canvas"
          alt="Campaign STIX relations canvas"
          emptyHint="The campaign-level STIX graph spans the indicators of ALL issues in this case, showing the shared infrastructure, techniques, and actors that tie them together. Generate it on demand (about a minute)."
          busy={regenerating === "relations"}
          disabled={regenerating !== null}
          onRegenerate={() => regenerate("relations")}
        />
      )}
    </div>
  );
}
