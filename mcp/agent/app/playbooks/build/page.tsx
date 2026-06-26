/**
 * Playbook Builder.
 *
 * List-primary object page (mirrors the Skills page): a grid of recorded
 * playbook builds with stat cards + filter tabs + search, plus a slide-in
 * builder panel and a slide-in detail panel.
 *
 * Retrieval-augmented authoring: the operator describes a use-case in the
 * builder panel; the agent (via the build_xsoar_playbook skill) grounds a new
 * Cortex XSOAR playbook in the closest real playbooks from the soar-playbooks
 * KB, validates it with playbook_validate, and returns the YAML + cited
 * examples. The panel drives that through /api/chat, extracts the playbook
 * YAML, re-validates it via /api/agent/playbooks/validate, offers a download,
 * and (behind an explicit confirm) deploys + test-runs it on a throwaway
 * incident in the connected tenant.
 *
 * Every build is recorded to /api/agent/playbook-builds so the grid + stats
 * reflect history. The agent's MCP tools also record server-side, so the UI's
 * own POST/PATCH calls are best-effort — a failed record never blocks the
 * builder flow.
 */

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { MarkdownContent } from "@/components/markdown-content";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  task_count: number;
}

type BuildStatus = "drafted" | "validated" | "deployed" | "tested" | "failed";

// Shape returned by GET/POST/PATCH /api/agent/playbook-builds. The list
// endpoint omits playbook_yaml + deploy_summary (compact rows); the single-
// record endpoints include them. Marked optional here so one type covers both.
interface PlaybookBuild {
  id: string;
  use_case: string;
  product: string | null;
  playbook_name: string | null;
  status: BuildStatus;
  validation_json: string | null;
  test_incident_id: string | null;
  session_id: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  // Present only on the full single-record fetch (GET/POST/PATCH by id).
  playbook_yaml?: string | null;
  deploy_summary?: string | null;
}

// ─── Styles (copied verbatim from the Skills page design system) ─────────────

const glassStyle: React.CSSProperties = {
  background: "var(--glass-bg-strong)",
  backdropFilter: "blur(12px)",
  border: "0.5px solid var(--glass-border)",
};

const panelStyle: React.CSSProperties = {
  background: "var(--glass-bg-elev)",
  backdropFilter: "blur(16px)",
  borderLeft: "0.5px solid var(--glass-border)",
};

const ghostBorder: React.CSSProperties = {
  border: "0.5px solid var(--glass-border)",
};

const glassSubtle: React.CSSProperties = {
  background: "rgba(20, 20, 45, 0.25)",
  backdropFilter: "blur(8px)",
  border: "0.5px solid rgba(140, 145, 157, 0.1)",
};

// ─── Status presentation ─────────────────────────────────────────────────────

const STATUS_META: Record<
  BuildStatus,
  { label: string; className: string; dot: string }
> = {
  drafted: {
    label: "DRAFTED",
    className: "text-on-surface-variant bg-surface-container-high",
    dot: "bg-on-surface-variant/50",
  },
  validated: {
    label: "VALIDATED",
    className: "text-primary border border-primary/30",
    dot: "bg-primary",
  },
  deployed: {
    label: "DEPLOYED",
    className: "text-secondary border border-secondary/30",
    dot: "bg-secondary",
  },
  tested: {
    label: "TESTED",
    className: "text-[#7bdc7b] border border-[#7bdc7b]/30",
    dot: "bg-[#7bdc7b]",
  },
  failed: {
    label: "FAILED",
    className: "text-[#ffb4ab] border border-[#ef4444]/30",
    dot: "bg-[#ef4444]",
  },
};

const FILTER_TABS: { key: "all" | BuildStatus; label: string }[] = [
  { key: "all", label: "All" },
  { key: "drafted", label: "Drafted" },
  { key: "validated", label: "Validated" },
  { key: "deployed", label: "Deployed" },
  { key: "tested", label: "Tested" },
  { key: "failed", label: "Failed" },
];

// ─── Pure helpers (also exercised by the builder flow) ───────────────────────

/**
 * Pick the playbook YAML block from a markdown answer.
 *
 * The agent's answer often contains MORE than one ```yaml fence — it cites
 * example playbooks from the KB, may show a small inputs snippet, etc. Grabbing
 * the FIRST block (the old behaviour) frequently captured a cited example or a
 * fragment instead of the real deliverable. So: among all ```yaml blocks,
 * prefer the one that actually looks like a complete playbook (top-level `id:`
 * or `name:` PLUS one of `tasks:`/`inputs:`/`starttaskid:`); if none match,
 * fall back to the LARGEST block (the playbook is almost always the biggest);
 * if there are no yaml fences at all, return null.
 */
function extractYaml(md: string): string | null {
  const blocks: string[] = [];
  const re = /```ya?ml\s*\n([\s\S]*?)```/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(md)) !== null) {
    blocks.push(m[1].trim());
  }
  if (blocks.length === 0) return null;

  const looksLikePlaybook = (s: string) =>
    /^(id|name):/m.test(s) && /^(tasks|inputs|starttaskid):/m.test(s);

  const playbook = blocks.find(looksLikePlaybook);
  if (playbook) return playbook;

  // No block clearly matched — the largest one is almost certainly the
  // playbook (cited examples are trimmed to a few lines; fragments are tiny).
  return blocks.reduce((a, b) => (b.length > a.length ? b : a));
}

/** Parse a playbook's `id:`/`name:` to a friendly display name. */
function parsePlaybookName(yaml: string | null): string | null {
  if (!yaml) return null;
  const name = yaml.match(/^name:\s*(.+)$/m);
  if (name) return name[1].trim().replace(/^["']|["']$/g, "");
  const id = yaml.match(/^id:\s*(.+)$/m);
  if (id) return id[1].trim().replace(/^["']|["']$/g, "");
  return null;
}

/** Best-effort parse of a test-incident id from the deploy report. */
function parseIncidentId(answer: string): string | null {
  const m = answer.match(/incident\s*(?:id|#)?\s*[:#]?\s*([0-9]{1,12})\b/i);
  return m ? m[1] : null;
}

/** Heuristic: does the deploy report indicate the run failed? */
function deployIndicatesFailure(answer: string): boolean {
  return /\b(failed|failure|error|could not|couldn't|unable to|import_unavailable)\b/i.test(
    answer,
  );
}

/** Read the /api/chat SSE stream — final assistant answer + the session id. */
async function readChatStream(
  resp: Response,
): Promise<{ answer: string; sessionId: string | null }> {
  const reader = resp.body?.getReader();
  if (!reader) return { answer: "", sessionId: null };
  const dec = new TextDecoder();
  let buf = "";
  let content = "";
  let done = "";
  let sessionId: string | null = null;
  for (;;) {
    const { value, done: streamDone } = await reader.read();
    if (streamDone) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data:")) continue;
      try {
        const d = JSON.parse(line.slice(5).trim());
        if (typeof d.session_id === "string") sessionId = d.session_id;
        if (typeof d.response === "string") done = d.response;
        else if (typeof d.text === "string") content += d.text;
        else if (typeof d.content === "string") content += d.content;
      } catch {
        /* non-JSON keepalive line */
      }
    }
  }
  return { answer: done || content, sessionId };
}

/**
 * A deploy turn whose answer is waiting on the operator's go-ahead before a
 * tenant write — the page's own confirm dialog already captured that approval,
 * so we auto-continue.
 *
 * Tightened: a bare trailing `?` no longer triggers an auto-continue (the agent
 * routinely ends a normal sentence with a question without actually gating on
 * confirmation, which used to burn all 5 auto-continue turns). We now require
 * an explicit deploy-gate phrase in the tail AND a trailing `?`.
 */
function isAwaitingConfirmation(answer: string): boolean {
  const tail = answer.slice(-240).toLowerCase();
  const gate =
    /(approve|confirm|proceed|shall i|do you want me to|may i|fire it)/.test(
      tail,
    );
  return gate && /\?\s*$/.test(tail);
}

// ─── Build card ──────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  return new Date(t).toISOString().slice(0, 10);
}

function BuildCard({
  build,
  onSelect,
}: {
  build: PlaybookBuild;
  onSelect: () => void;
}) {
  const status = STATUS_META[build.status] ?? STATUS_META.drafted;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      className="p-6 rounded-2xl hover:ring-1 hover:ring-primary/20 transition-all cursor-pointer group"
      style={glassStyle}
    >
      {/* Icon + status */}
      <div className="flex justify-between mb-6">
        <div className="w-12 h-12 rounded-xl bg-primary/15 flex items-center justify-center">
          <span className="material-symbols-outlined text-2xl text-primary">
            construction
          </span>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-full font-bold ${status.className}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
          {status.label}
        </span>
      </div>
      <h3 className="font-headline text-lg font-medium text-on-surface mb-1 line-clamp-1">
        {build.playbook_name || "Untitled draft"}
      </h3>
      <p className="text-sm text-on-surface-variant/70 line-clamp-2 mb-6">
        {build.use_case}
      </p>
      {/* Footer */}
      <div className="flex justify-between items-center pt-4 border-t border-outline-variant/30">
        <div className="flex items-center gap-2 min-w-0">
          {build.product ? (
            <span className="text-[10px] px-2 py-0.5 rounded bg-tertiary/10 text-tertiary truncate max-w-[150px]">
              {build.product}
            </span>
          ) : (
            <span className="text-[10px] text-on-surface-variant/40">
              No target product
            </span>
          )}
        </div>
        <span
          className="text-[10px] text-on-surface-variant/60 shrink-0"
          title={build.created_at}
        >
          {relativeTime(build.created_at)}
        </span>
      </div>
    </div>
  );
}

// ─── Builder slide-in panel ──────────────────────────────────────────────────

function BuilderPanel({
  onClose,
  onRecorded,
}: {
  onClose: () => void;
  // Called whenever the panel records/patches a build — the parent refetches
  // so the grid + stats stay current.
  onRecorded: () => void;
}) {
  const [useCase, setUseCase] = useState("");
  const [product, setProduct] = useState("");
  const [generating, setGenerating] = useState(false);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Non-blocking warning when a best-effort record/patch fails. The builder
  // flow continues regardless — the agent records server-side too.
  const [recordWarning, setRecordWarning] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [validating, setValidating] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [deployAnswer, setDeployAnswer] = useState("");
  const [confirmDeploy, setConfirmDeploy] = useState(false);

  // Persisted across the panel's lifetime: the draft's chat session (reused by
  // deploy + recorded on the build) and the recorded build's id (PATCHed as the
  // build progresses through validate → deploy).
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentBuildId, setCurrentBuildId] = useState<string | null>(null);

  const yaml = useMemo(() => extractYaml(answer), [answer]);

  // ── Best-effort recording helpers ──────────────────────────────────────

  const recordDraft = useCallback(
    async (playbookYaml: string, session: string | null) => {
      try {
        const r = await fetch("/api/agent/playbook-builds", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            use_case: useCase.trim(),
            product: product.trim() || undefined,
            playbook_name: parsePlaybookName(playbookYaml) || undefined,
            playbook_yaml: playbookYaml,
            status: "drafted",
            session_id: session || undefined,
          }),
        });
        if (!r.ok) throw new Error(`record draft ${r.status}`);
        const build = (await r.json()) as PlaybookBuild;
        setCurrentBuildId(build.id);
        onRecorded();
      } catch (err) {
        setRecordWarning(
          `Couldn't record this draft to build history (${
            err instanceof Error ? err.message : String(err)
          }). The agent records server-side too.`,
        );
      }
    },
    [useCase, product, onRecorded],
  );

  const patchBuild = useCallback(
    async (patch: Record<string, unknown>) => {
      if (!currentBuildId) return;
      try {
        const r = await fetch(`/api/agent/playbook-builds/${currentBuildId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        if (!r.ok) throw new Error(`update build ${r.status}`);
        onRecorded();
      } catch (err) {
        setRecordWarning(
          `Couldn't update build history (${
            err instanceof Error ? err.message : String(err)
          }). The agent records server-side too.`,
        );
      }
    },
    [currentBuildId, onRecorded],
  );

  // ── Builder flow (preserved orchestration) ─────────────────────────────

  const generate = useCallback(async () => {
    const uc = useCase.trim();
    if (!uc) return;
    setGenerating(true);
    setError(null);
    setRecordWarning(null);
    setAnswer("");
    setValidation(null);
    setDeployAnswer("");
    setCurrentBuildId(null);
    const message =
      `Build a Cortex XSOAR playbook for this use case: ${uc}.` +
      (product.trim() ? ` Target product / integration: ${product.trim()}.` : "") +
      ` Use the build_xsoar_playbook skill: ground it in soar-playbooks examples,` +
      ` validate it with playbook_validate, then present the final playbook YAML in` +
      ` a single \`\`\`yaml code block and cite the example playbooks you used.`;
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (!r.ok) throw new Error(`generate ${r.status}`);
      const { answer: text, sessionId: sid } = await readChatStream(r);
      setAnswer(text || "(no response)");
      if (sid) setSessionId(sid);
      // Record the draft if we got a usable playbook out of the answer.
      const draftYaml = extractYaml(text);
      if (draftYaml) {
        await recordDraft(draftYaml, sid);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  }, [useCase, product, recordDraft]);

  const validate = useCallback(async () => {
    if (!yaml) return;
    setValidating(true);
    setError(null);
    try {
      const r = await fetch("/api/agent/playbooks/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ playbook_yaml: yaml }),
      });
      if (!r.ok) throw new Error(`validate ${r.status}`);
      const result = (await r.json()) as ValidationResult;
      setValidation(result);
      await patchBuild({
        validation_json: JSON.stringify(result),
        status: result.valid ? "validated" : "drafted",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setValidating(false);
    }
  }, [yaml, patchBuild]);

  const deploy = useCallback(async () => {
    if (!yaml) return;
    setConfirmDeploy(false);
    setDeploying(true);
    setError(null);
    setDeployAnswer("");
    const message =
      `Deploy and test-run this playbook in the connected Cortex XSOAR tenant now. ` +
      `The operator has ALREADY approved this deployment in the Guardian UI — proceed ` +
      `without asking for further confirmation. Follow the build_xsoar_playbook skill's ` +
      `Deploy + test-run lifecycle (D1–D7): validate, xsoar_import_playbook, create a ` +
      `[Guardian test] incident, xsoar_run_playbook, read the war room, then close the ` +
      `test incident. If import returns import_unavailable, explain how to import the ` +
      `playbook manually (Settings → Playbooks → Import) and what to do next. Report the ` +
      `imported playbook, the test incident id, the run outcome, and confirm cleanup. ` +
      `Playbook YAML:\n\n\`\`\`yaml\n${yaml}\n\`\`\``;
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          sessionId ? { message, session_id: sessionId } : { message },
        ),
      });
      if (!r.ok) throw new Error(`deploy ${r.status}`);
      let { answer: result, sessionId: sid } = await readChatStream(r);
      if (sid) setSessionId(sid);
      // The deploy sequence makes several tenant writes (import, create
      // incident, run, close) and the agent may pause for confirmation before
      // each. The UI confirm dialog already captured the operator's go-ahead
      // for the WHOLE sequence, so auto-approve each pause — up to a few turns
      // so the close / cleanup step always lands.
      for (let i = 0; sid && i < 5 && isAwaitingConfirmation(result); i++) {
        const rn = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message:
              "Yes — the operator approved the entire deploy + test-run in the UI. " +
              "Continue ALL remaining steps now without pausing, including closing " +
              "the test incident, then give the final report.",
            session_id: sid,
          }),
        });
        if (!rn.ok) break;
        const next = await readChatStream(rn);
        result = next.answer || result;
        sid = next.sessionId || sid;
        if (sid) setSessionId(sid);
      }
      setDeployAnswer(result || "(no response)");
      // Record the deploy outcome.
      const failed = deployIndicatesFailure(result);
      const incidentId = parseIncidentId(result);
      await patchBuild({
        status: failed ? "failed" : "tested",
        deploy_summary: result,
        playbook_name: parsePlaybookName(yaml) || undefined,
        ...(incidentId ? { test_incident_id: incidentId } : {}),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeploying(false);
    }
  }, [yaml, sessionId, patchBuild]);

  const download = useCallback(() => {
    if (!yaml) return;
    const idMatch = yaml.match(/^id:\s*(.+)$/m);
    const name = (idMatch ? idMatch[1] : "playbook").trim().replace(/[^a-z0-9._-]/gi, "_");
    const blob = new Blob([yaml], { type: "text/yaml" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `playbook-${name}.yml`;
    a.click();
    URL.revokeObjectURL(a.href);
  }, [yaml]);

  return (
    <>
      <div
        className="fixed inset-0 bg-black/60 z-40 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className="fixed top-0 right-0 h-full w-[55%] z-50 flex flex-col shadow-[0_0_80px_rgba(0,0,0,0.5)] overflow-hidden animate-[slideInRight_0.3s_ease-out]"
        style={panelStyle}
      >
        {/* Header */}
        <div className="px-8 pt-8 pb-6 border-b border-white/10 shrink-0">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-3xl font-bold font-headline tracking-tight text-on-surface">
                New playbook
              </h2>
              <p className="text-on-surface-variant text-sm mt-1">
                Draft, validate, then deploy + test-run on a throwaway incident.
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/10 rounded-full transition-colors text-on-surface-variant"
              aria-label="Close panel"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-8 py-8 space-y-6 custom-scrollbar">
          {/* Form */}
          <div className="rounded-2xl p-5 space-y-4" style={glassStyle}>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-on-surface-variant">
                What should the playbook do?
              </label>
              <textarea
                value={useCase}
                onChange={(e) => setUseCase(e.target.value)}
                rows={3}
                placeholder="e.g. Investigate a phishing email end to end: extract indicators, enrich them, search the mailbox for similar messages, and delete on confirmation."
                className="w-full rounded-lg p-3 text-sm bg-transparent text-on-surface placeholder:text-on-surface-variant/40 outline-none"
                style={glassSubtle}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-on-surface-variant">
                Product / integration (optional)
              </label>
              <input
                value={product}
                onChange={(e) => setProduct(e.target.value)}
                placeholder="e.g. CrowdStrike Falcon, Microsoft Defender, generic"
                className="w-full rounded-lg p-2.5 text-sm bg-transparent text-on-surface placeholder:text-on-surface-variant/40 outline-none"
                style={glassSubtle}
              />
            </div>
            <button
              onClick={() => void generate()}
              disabled={generating || !useCase.trim()}
              className="w-full px-4 py-2.5 rounded-lg text-sm font-medium bg-primary-container text-on-primary-container disabled:opacity-50 transition-opacity"
            >
              {generating ? "Building…" : "Build playbook"}
            </button>
          </div>

          {error ? (
            <div className="rounded-xl border border-error/30 bg-error/10 p-3 text-xs text-error">
              {error}
            </div>
          ) : null}

          {recordWarning ? (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
              {recordWarning}
            </div>
          ) : null}

          {generating ? (
            <div className="text-center py-12 text-sm text-on-surface-variant/60">
              Grounding in soar-playbooks examples + drafting…
            </div>
          ) : null}

          {/* Result */}
          {answer ? (
            <div className="space-y-4">
              {yaml ? (
                <div className="rounded-2xl p-4 flex flex-wrap items-center gap-3" style={glassStyle}>
                  <span className="text-xs text-on-surface-variant/70">
                    Drafted playbook ({yaml.split("\n").length} lines)
                  </span>
                  <div className="flex-1" />
                  <button
                    onClick={() => void validate()}
                    disabled={validating}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-50"
                    style={glassSubtle}
                  >
                    {validating ? "Validating…" : "Validate structure"}
                  </button>
                  <button
                    onClick={download}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium text-on-surface-variant hover:text-on-surface transition-colors"
                    style={glassSubtle}
                  >
                    Download .yml
                  </button>
                  <button
                    onClick={() => setConfirmDeploy(true)}
                    disabled={deploying}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-primary-container text-on-primary-container disabled:opacity-50 transition-opacity inline-flex items-center gap-1"
                  >
                    <span className="material-symbols-outlined text-sm">rocket_launch</span>
                    {deploying ? "Deploying…" : "Deploy + test-run"}
                  </button>
                </div>
              ) : null}

              {/* Deploy confirm (mutates the tenant) */}
              {confirmDeploy ? (
                <div className="rounded-xl p-4 text-xs border border-amber-500/30 bg-amber-500/10 space-y-2.5">
                  <div className="text-on-surface leading-relaxed">
                    This <strong>imports and runs</strong> the playbook in your connected
                    Cortex XSOAR tenant — on a disposable{" "}
                    <code className="font-mono">[Guardian test]</code> incident that&apos;s
                    auto-closed afterward. On Cortex 8 without the Core REST API integration,
                    Guardian will instead give you manual-import steps, then test-run once
                    it&apos;s imported. Proceed?
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => void deploy()}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium bg-primary-container text-on-primary-container"
                    >
                      Deploy now
                    </button>
                    <button
                      onClick={() => setConfirmDeploy(false)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium text-on-surface-variant hover:text-on-surface transition-colors"
                      style={glassSubtle}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : null}

              {deploying ? (
                <div className="text-center py-8 text-sm text-on-surface-variant/60">
                  Importing + running on a test incident…
                </div>
              ) : null}

              {deployAnswer ? (
                <div className="rounded-2xl p-5 space-y-2" style={glassStyle}>
                  <div className="text-xs font-semibold text-primary uppercase tracking-wider flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-base">rocket_launch</span>
                    Deploy + test-run result
                  </div>
                  <MarkdownContent>{deployAnswer}</MarkdownContent>
                </div>
              ) : null}

              {validation ? (
                <div
                  className={
                    "rounded-xl p-4 text-xs space-y-1 border " +
                    (validation.valid
                      ? "border-green-500/30 bg-green-500/10"
                      : "border-error/30 bg-error/10")
                  }
                >
                  <div className="font-semibold flex items-center gap-2">
                    <span className="material-symbols-outlined text-base">
                      {validation.valid ? "check_circle" : "error"}
                    </span>
                    {validation.valid
                      ? `Structurally valid — ${validation.task_count} tasks`
                      : `Invalid — ${validation.errors.length} error(s)`}
                  </div>
                  {validation.errors.map((e, i) => (
                    <div key={`e${i}`} className="text-error pl-6">• {e}</div>
                  ))}
                  {validation.warnings.map((w, i) => (
                    <div key={`w${i}`} className="text-on-surface-variant/70 pl-6">⚠ {w}</div>
                  ))}
                </div>
              ) : null}

              <div className="rounded-2xl p-5" style={glassStyle}>
                <MarkdownContent>{answer}</MarkdownContent>
              </div>
            </div>
          ) : null}
        </div>
      </aside>
    </>
  );
}

// ─── Build detail slide-in panel ─────────────────────────────────────────────

function BuildDetailPanel({
  buildId,
  onClose,
  onDeleted,
}: {
  buildId: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [build, setBuild] = useState<PlaybookBuild | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "loaded" | "error">(
    "loading",
  );
  const [loadError, setLoadError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoadState("loading");
    setLoadError(null);
    try {
      const r = await fetch(`/api/agent/playbook-builds/${buildId}`, {
        cache: "no-store",
      });
      if (!r.ok) throw new Error(`status ${r.status}`);
      setBuild((await r.json()) as PlaybookBuild);
      setLoadState("loaded");
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
      setLoadState("error");
    }
  }, [buildId]);

  useEffect(() => {
    void load();
  }, [load]);

  const validationResult = useMemo<ValidationResult | null>(() => {
    if (!build?.validation_json) return null;
    try {
      return JSON.parse(build.validation_json) as ValidationResult;
    } catch {
      return null;
    }
  }, [build]);

  const downloadYaml = useCallback(() => {
    if (!build?.playbook_yaml) return;
    const idMatch = build.playbook_yaml.match(/^id:\s*(.+)$/m);
    const name = (idMatch ? idMatch[1] : build.playbook_name || "playbook")
      .trim()
      .replace(/[^a-z0-9._-]/gi, "_");
    const blob = new Blob([build.playbook_yaml], { type: "text/yaml" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `playbook-${name}.yml`;
    a.click();
    URL.revokeObjectURL(a.href);
  }, [build]);

  const handleDelete = useCallback(async () => {
    setDeleting(true);
    try {
      const r = await fetch(`/api/agent/playbook-builds/${buildId}`, {
        method: "DELETE",
      });
      if (!r.ok) throw new Error(`delete ${r.status}`);
      onDeleted();
      onClose();
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
      setDeleting(false);
    }
  }, [buildId, onDeleted, onClose]);

  const status = build ? STATUS_META[build.status] ?? STATUS_META.drafted : null;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/60 z-40 backdrop-blur-[2px] animate-[fadeIn_0.2s_ease-out]"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className="fixed right-0 top-0 h-full w-[55%] z-50 shadow-[0_0_80px_rgba(0,0,0,0.5)] overflow-hidden flex flex-col animate-[slideInRight_0.3s_ease-out]"
        style={panelStyle}
      >
        {/* Header */}
        <header className="p-8 pb-6 border-b border-white/5 shrink-0">
          <div className="flex items-start justify-between mb-6">
            <button
              onClick={onClose}
              className="w-10 h-10 rounded-full flex items-center justify-center bg-white/5 hover:bg-white/10 transition-all active:scale-95 group"
              aria-label="Close panel"
            >
              <span className="material-symbols-outlined text-on-surface-variant group-hover:text-primary-fixed-dim">
                arrow_back
              </span>
            </button>
            <div className="flex items-center gap-2">
              {build?.playbook_yaml ? (
                <button
                  onClick={downloadYaml}
                  className="h-9 px-3 flex items-center gap-1.5 rounded-full bg-white/5 hover:bg-white/10 transition-all active:scale-95 text-xs font-medium text-on-surface-variant hover:text-on-surface"
                  title="Download as .yml file"
                >
                  <span className="material-symbols-outlined text-base">download</span>
                  Download .yml
                </button>
              ) : null}
              <button
                onClick={() => setConfirmDelete(true)}
                disabled={deleting}
                className="h-9 px-3 flex items-center gap-1.5 rounded-full transition-all text-xs font-medium bg-red-500/10 hover:bg-red-500/20 text-red-300 hover:text-red-200 active:scale-95 disabled:opacity-50"
                title="Delete this build record"
              >
                <span className="material-symbols-outlined text-base">delete</span>
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
            {status ? (
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] uppercase tracking-widest font-bold ${status.className}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
                {status.label}
              </span>
            ) : null}
          </div>
          <h2 className="text-3xl font-headline font-bold mb-2 tracking-tight text-on-surface flex items-center gap-3">
            <span className="material-symbols-outlined text-2xl text-primary">
              construction
            </span>
            {build?.playbook_name || "Untitled draft"}
          </h2>
          {build ? (
            <p className="text-xs text-on-surface-variant/60 font-mono">
              {build.created_by ? `${build.created_by} · ` : ""}
              created {build.created_at}
              {build.updated_at !== build.created_at
                ? ` · updated ${build.updated_at}`
                : ""}
            </p>
          ) : null}
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
          {loadState === "loading" ? (
            <div
              className="w-full rounded-xl px-5 py-12 flex flex-col items-center justify-center gap-3 bg-surface-container-lowest"
              style={ghostBorder}
              role="status"
            >
              <span className="material-symbols-outlined text-3xl text-primary-fixed-dim animate-spin">
                progress_activity
              </span>
              <p className="text-sm text-on-surface-variant">Loading build…</p>
            </div>
          ) : loadState === "error" ? (
            <div
              className="w-full rounded-xl px-5 py-10 flex flex-col items-center justify-center gap-3 bg-surface-container-lowest"
              style={ghostBorder}
              role="alert"
            >
              <span className="material-symbols-outlined text-3xl text-error">error</span>
              <p className="text-sm text-on-surface">Couldn&apos;t load this build.</p>
              {loadError ? (
                <p className="text-[11px] text-on-surface-variant/70 font-mono text-center max-w-md">
                  {loadError}
                </p>
              ) : null}
              <button
                onClick={() => void load()}
                className="mt-1 text-xs text-primary-fixed-dim hover:underline font-medium"
              >
                Retry
              </button>
            </div>
          ) : build ? (
            <>
              {/* Use case */}
              <section>
                <div className="text-[10px] uppercase tracking-[0.2em] font-bold text-on-surface-variant/40 mb-3">
                  Use case
                </div>
                <p className="text-sm text-on-surface-variant leading-relaxed">
                  {build.use_case}
                </p>
                {build.product ? (
                  <div className="mt-3 inline-flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded bg-tertiary/10 text-tertiary">
                    <span className="material-symbols-outlined text-sm">extension</span>
                    {build.product}
                  </div>
                ) : null}
                {build.test_incident_id ? (
                  <div className="mt-3 ml-2 inline-flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded bg-primary/10 text-primary">
                    <span className="material-symbols-outlined text-sm">bug_report</span>
                    Test incident #{build.test_incident_id}
                  </div>
                ) : null}
              </section>

              {/* Validation */}
              {validationResult ? (
                <section>
                  <div className="text-[10px] uppercase tracking-[0.2em] font-bold text-on-surface-variant/40 mb-3">
                    Validation
                  </div>
                  <div
                    className={
                      "rounded-xl p-4 text-xs space-y-1 border " +
                      (validationResult.valid
                        ? "border-green-500/30 bg-green-500/10"
                        : "border-error/30 bg-error/10")
                    }
                  >
                    <div className="font-semibold flex items-center gap-2">
                      <span className="material-symbols-outlined text-base">
                        {validationResult.valid ? "check_circle" : "error"}
                      </span>
                      {validationResult.valid
                        ? `Structurally valid — ${validationResult.task_count} tasks`
                        : `Invalid — ${validationResult.errors.length} error(s)`}
                    </div>
                    {validationResult.errors.map((e, i) => (
                      <div key={`e${i}`} className="text-error pl-6">• {e}</div>
                    ))}
                    {validationResult.warnings.map((w, i) => (
                      <div key={`w${i}`} className="text-on-surface-variant/70 pl-6">⚠ {w}</div>
                    ))}
                  </div>
                </section>
              ) : null}

              {/* Playbook YAML */}
              {build.playbook_yaml ? (
                <section>
                  <div className="text-[10px] uppercase tracking-[0.2em] font-bold text-on-surface-variant/40 mb-3">
                    Playbook YAML
                  </div>
                  <pre
                    className="w-full rounded-xl px-5 py-4 text-xs font-mono text-on-surface-variant leading-relaxed overflow-x-auto bg-surface-container-lowest custom-scrollbar"
                    style={ghostBorder}
                  >
                    {build.playbook_yaml}
                  </pre>
                </section>
              ) : null}

              {/* Deploy summary */}
              {build.deploy_summary ? (
                <section>
                  <div className="text-[10px] uppercase tracking-[0.2em] font-bold text-on-surface-variant/40 mb-3">
                    Deploy + test-run result
                  </div>
                  <div className="rounded-2xl p-5" style={glassStyle}>
                    <MarkdownContent>{build.deploy_summary}</MarkdownContent>
                  </div>
                </section>
              ) : null}

              {/* Delete confirm */}
              {confirmDelete ? (
                <section>
                  <div className="rounded-xl p-4 text-xs border border-[#ef4444]/30 bg-[#ef4444]/10 space-y-2.5">
                    <div className="text-on-surface leading-relaxed">
                      Delete this build record permanently? The drafted YAML +
                      deploy report are removed from build history. This does not
                      touch anything already imported into your tenant.
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => void handleDelete()}
                        disabled={deleting}
                        className="px-3 py-1.5 rounded-lg text-xs font-bold bg-[#ef4444]/20 text-[#ffb4ab] hover:bg-[#ef4444]/30 transition-colors disabled:opacity-50"
                      >
                        {deleting ? "Deleting…" : "Delete build"}
                      </button>
                      <button
                        onClick={() => setConfirmDelete(false)}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium text-on-surface-variant hover:text-on-surface transition-colors"
                        style={glassSubtle}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </section>
              ) : null}
            </>
          ) : null}
        </div>
      </aside>
    </>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function PlaybookBuilderPage() {
  const [builds, setBuilds] = useState<PlaybookBuild[]>([]);
  const [loadStatus, setLoadStatus] = useState<"loading" | "loaded" | "error">(
    "loading",
  );
  const [statusFilter, setStatusFilter] = useState<"all" | BuildStatus>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showBuilder, setShowBuilder] = useState(false);
  const [selectedBuildId, setSelectedBuildId] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      const r = await fetch("/api/agent/playbook-builds?order=desc", {
        cache: "no-store",
      });
      if (!r.ok) throw new Error(`status ${r.status}`);
      const body = (await r.json()) as { builds?: PlaybookBuild[] };
      setBuilds(Array.isArray(body.builds) ? body.builds : []);
      setLoadStatus("loaded");
    } catch {
      setLoadStatus("error");
    }
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  // Newest first — the API orders for us, but enforce it defensively so a
  // mixed-order response (or freshly POSTed row) still renders most-recent
  // first.
  const sortedBuilds = useMemo(
    () =>
      [...builds].sort(
        (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
      ),
    [builds],
  );

  const filteredBuilds = useMemo(() => {
    let result = sortedBuilds;
    if (statusFilter !== "all") {
      result = result.filter((b) => b.status === statusFilter);
    }
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      result = result.filter(
        (b) =>
          b.use_case.toLowerCase().includes(q) ||
          (b.product ?? "").toLowerCase().includes(q) ||
          (b.playbook_name ?? "").toLowerCase().includes(q),
      );
    }
    return result;
  }, [sortedBuilds, statusFilter, searchQuery]);

  const stats = useMemo(() => {
    return {
      total: builds.length,
      deployed: builds.filter(
        (b) => b.status === "deployed" || b.status === "tested",
      ).length,
      validated: builds.filter((b) => b.status === "validated").length,
      failed: builds.filter((b) => b.status === "failed").length,
    };
  }, [builds]);

  const tabCount = useCallback(
    (key: "all" | BuildStatus) =>
      key === "all"
        ? builds.length
        : builds.filter((b) => b.status === key).length,
    [builds],
  );

  return (
    <div className="h-screen overflow-y-auto custom-scrollbar">
      <div className="max-w-[1400px] mx-auto px-8 py-8 space-y-8">
        {/* ── Page Header ──────────────────────────────────── */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="material-symbols-outlined text-2xl text-primary">
                construction
              </span>
              <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface">
                Playbook Builder
              </h1>
            </div>
            <p className="text-sm text-on-surface-variant ml-9">
              Draft Cortex XSOAR playbooks grounded in the soar-playbooks knowledge
              base, then deploy + test-run them — every build recorded here.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowBuilder(true)}
              className="text-white px-6 py-2.5 rounded-xl font-bold font-headline flex items-center gap-2 shadow-[0px_20px_40px_rgba(25,99,179,0.15)] active:scale-95 transition-transform"
              style={{
                background: "linear-gradient(135deg, #1963b3 0%, #2d8df0 100%)",
              }}
            >
              <span className="material-symbols-outlined text-lg">add</span>
              New playbook
            </button>
          </div>
        </header>

        {/* ── Summary Strip ────────────────────────────────── */}
        <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl flex items-center gap-4" style={glassStyle}>
            <div className="h-12 w-12 rounded-xl bg-primary/15 flex items-center justify-center text-primary shrink-0">
              <span className="material-symbols-outlined">construction</span>
            </div>
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-wider text-on-surface-variant">
                Total
              </p>
              <p className="text-2xl font-bold font-headline text-on-surface">
                {stats.total}
              </p>
              <p className="text-[11px] text-on-surface-variant/70 truncate">
                Recorded builds
              </p>
            </div>
          </div>
          <div className="p-5 rounded-2xl flex items-center gap-4" style={glassStyle}>
            <div className="h-12 w-12 rounded-xl bg-secondary/15 flex items-center justify-center text-secondary shrink-0">
              <span className="material-symbols-outlined">rocket_launch</span>
            </div>
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-wider text-on-surface-variant">
                Deployed
              </p>
              <p className="text-2xl font-bold font-headline text-secondary">
                {stats.deployed}
              </p>
              <p className="text-[11px] text-on-surface-variant/70 truncate">
                Imported + test-run
              </p>
            </div>
          </div>
          <div className="p-5 rounded-2xl flex items-center gap-4" style={glassStyle}>
            <div className="h-12 w-12 rounded-xl bg-tertiary/15 flex items-center justify-center text-tertiary shrink-0">
              <span className="material-symbols-outlined">fact_check</span>
            </div>
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-wider text-on-surface-variant">
                Validated
              </p>
              <p className="text-2xl font-bold font-headline text-tertiary">
                {stats.validated}
              </p>
              <p className="text-[11px] text-on-surface-variant/70 truncate">
                Structurally valid
              </p>
            </div>
          </div>
          <div className="p-5 rounded-2xl flex items-center gap-4" style={glassStyle}>
            <div className="h-12 w-12 rounded-xl bg-primary/15 flex items-center justify-center text-primary shrink-0">
              <span className="material-symbols-outlined">error</span>
            </div>
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-wider text-on-surface-variant">
                Failed
              </p>
              <p className="text-2xl font-bold font-headline text-primary">
                {stats.failed}
              </p>
              <p className="text-[11px] text-on-surface-variant/70 truncate">
                Deploy / run errors
              </p>
            </div>
          </div>
        </section>

        {/* ── Filter Bar ───────────────────────────────────── */}
        <section className="flex flex-col md:flex-row gap-6 items-center justify-between">
          <div className="flex items-center gap-2 p-1.5 rounded-2xl bg-surface-container-low border border-outline-variant/30 flex-wrap">
            {FILTER_TABS.map((f) => (
              <button
                key={f.key}
                onClick={() => setStatusFilter(f.key)}
                className={`px-5 py-2 rounded-xl text-sm font-medium transition-colors ${
                  statusFilter === f.key
                    ? "bg-secondary-container/40 text-secondary font-bold"
                    : "text-on-surface hover:bg-surface-container-high"
                }`}
              >
                {f.label} ({tabCount(f.key)})
              </button>
            ))}
          </div>
          <div className="relative w-full md:w-80">
            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant">
              search
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search builds..."
              className="w-full bg-surface-container-low py-3 pl-12 pr-4 rounded-xl border border-outline-variant/30 focus:border-primary focus:ring-0 text-sm text-on-surface placeholder:text-on-surface-variant/60"
            />
          </div>
        </section>

        {/* ── Build Grid ───────────────────────────────────── */}
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredBuilds.map((build) => (
            <BuildCard
              key={build.id}
              build={build}
              onSelect={() => setSelectedBuildId(build.id)}
            />
          ))}
          {filteredBuilds.length === 0 && (
            <div className="col-span-3 flex flex-col items-center justify-center py-16 text-center">
              {loadStatus === "loading" ? (
                <>
                  <span className="material-symbols-outlined text-4xl text-on-surface-variant/30 mb-3 animate-spin">
                    progress_activity
                  </span>
                  <p className="text-sm font-bold text-on-surface-variant">
                    Loading builds…
                  </p>
                </>
              ) : builds.length === 0 ? (
                <>
                  <span className="material-symbols-outlined text-4xl text-on-surface-variant/30 mb-3">
                    construction
                  </span>
                  <p className="text-sm font-bold text-on-surface-variant">
                    No playbooks built yet
                  </p>
                  <p className="text-xs text-on-surface-variant/60 mt-1 max-w-sm">
                    Describe a use case and Guardian drafts a Cortex XSOAR playbook
                    grounded in the soar-playbooks knowledge base.
                  </p>
                  <button
                    onClick={() => setShowBuilder(true)}
                    className="text-xs font-bold text-primary-fixed-dim hover:underline mt-3"
                  >
                    Build your first playbook
                  </button>
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-4xl text-on-surface-variant/30 mb-3">
                    search_off
                  </span>
                  <p className="text-sm font-bold text-on-surface-variant">
                    No builds match your filter
                  </p>
                  <button
                    onClick={() => {
                      setStatusFilter("all");
                      setSearchQuery("");
                    }}
                    className="text-xs font-bold text-primary-fixed-dim hover:underline mt-2"
                  >
                    Clear filters
                  </button>
                </>
              )}
            </div>
          )}
        </section>
      </div>

      {/* ── Builder Panel ────────────────────────────────────
          Fixed-positioned OUTSIDE the max-width wrapper, mirroring how
          Skills mounts its create/detail panels. */}
      {showBuilder && (
        <BuilderPanel
          onClose={() => {
            setShowBuilder(false);
            void refetch();
          }}
          onRecorded={() => void refetch()}
        />
      )}

      {/* ── Build Detail Panel ───────────────────────────── */}
      {selectedBuildId && (
        <BuildDetailPanel
          buildId={selectedBuildId}
          onClose={() => setSelectedBuildId(null)}
          onDeleted={() => void refetch()}
        />
      )}

      {/* ── Animations + scrollbar (copied from skills/page.tsx) ──── */}
      <style jsx>{`
        @keyframes slideInRight {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
        @keyframes fadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(140, 145, 157, 0.2);
          border-radius: 10px;
        }
      `}</style>
    </div>
  );
}
