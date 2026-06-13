"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { getCase, type CaseDetail } from "@/lib/api/investigation";
import {
  glassStyle,
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

type Tab = "issues" | "chain" | "relations";
const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "issues", label: "Issues", icon: "report" },
  { key: "chain", label: "Attack chain", icon: "account_tree" },
  { key: "relations", label: "Relations", icon: "hub" },
];

export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [data, setData] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("issues");
  // null = idle; otherwise the diagram kind currently regenerating.
  const [regenerating, setRegenerating] = useState<null | "chain" | "relations">(null);

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
      await fetch("/api/agent/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `regen-case-${kind}-${id}`,
          cron: "* * * * *",
          timezone: "UTC",
          run_once: true,
          enabled: true,
          bypass_approvals: true,
          action: { type: "prompt", skill, message },
        }),
      });
      const deadline = Date.now() + 180_000;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 5000));
        try {
          const det = await getCase(id);
          const now = (isChain ? det.attack_chain_svg : det.relations_canvas_svg) ?? "";
          if (now && now !== before) {
            setData(det);
            break;
          }
        } catch {
          /* transient — keep polling */
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "regenerate failed");
    } finally {
      setRegenerating(null);
    }
  };

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
