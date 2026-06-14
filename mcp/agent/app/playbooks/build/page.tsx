/**
 * Playbook Builder (v0.2.24).
 *
 * Retrieval-augmented authoring: the operator describes a use-case; the agent
 * (via the build_xsoar_playbook skill) grounds a new Cortex XSOAR playbook in
 * the closest real playbooks from the soar-playbooks KB, validates it with
 * playbook_validate, and returns the YAML + cited examples. This page drives
 * that through /api/chat, extracts the playbook YAML, re-validates it via
 * /api/agent/playbooks/validate, and offers a download.
 *
 * The output is a DRAFT. v0.2.26 adds "Deploy + test-run": behind an explicit
 * confirm, the page asks the agent (build_xsoar_playbook skill, Deploy lifecycle)
 * to import the playbook into the connected tenant, run it on a disposable
 * [Guardian test] incident, report the outcome, and close the incident. On a
 * Cortex 8 tenant without the Core REST API integration the import is unavailable,
 * so the agent returns manual-import guidance + still runs the test once imported.
 */

"use client";

import { useCallback, useMemo, useState } from "react";
import { MarkdownContent } from "@/components/markdown-content";

interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  task_count: number;
}

const glass = {
  background: "var(--glass-bg-strong)",
  backdropFilter: "blur(12px)",
  border: "0.5px solid var(--glass-border)",
} as const;
const glassSubtle = {
  background: "rgba(20, 20, 45, 0.25)",
  backdropFilter: "blur(8px)",
  border: "0.5px solid rgba(140, 145, 157, 0.1)",
} as const;

/** Extract the first ```yaml fenced block from a markdown answer. */
function extractYaml(md: string): string | null {
  const m = md.match(/```ya?ml\s*\n([\s\S]*?)```/i);
  return m ? m[1].trim() : null;
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

/** A deploy turn whose answer ends with a confirmation question — the agent
 *  is waiting for the operator to approve the tenant write. The page's own
 *  confirm dialog already captured that approval, so we auto-continue. */
function isAwaitingConfirmation(answer: string): boolean {
  const tail = answer.slice(-240).toLowerCase();
  return /fire it|confirm|proceed\?|shall i|do you want|may i|approve|\?\s*$/.test(tail);
}

export default function PlaybookBuilderPage() {
  const [useCase, setUseCase] = useState("");
  const [product, setProduct] = useState("");
  const [generating, setGenerating] = useState(false);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [validating, setValidating] = useState(false);
  // v0.2.26 — deploy + test-run
  const [deploying, setDeploying] = useState(false);
  const [deployAnswer, setDeployAnswer] = useState("");
  const [confirmDeploy, setConfirmDeploy] = useState(false);

  const yaml = useMemo(() => extractYaml(answer), [answer]);

  const generate = useCallback(async () => {
    const uc = useCase.trim();
    if (!uc) return;
    setGenerating(true);
    setError(null);
    setAnswer("");
    setValidation(null);
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
      const { answer: text } = await readChatStream(r);
      setAnswer(text || "(no response)");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  }, [useCase, product]);

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
      setValidation((await r.json()) as ValidationResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setValidating(false);
    }
  }, [yaml]);

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
        body: JSON.stringify({ message }),
      });
      if (!r.ok) throw new Error(`deploy ${r.status}`);
      let { answer: result, sessionId } = await readChatStream(r);
      // The deploy sequence makes several tenant writes (import, create incident,
      // run, close) and the agent may pause for confirmation before each. The UI
      // confirm dialog already captured the operator's go-ahead for the WHOLE
      // sequence, so auto-approve each pause — up to a few turns so the close /
      // cleanup step always lands.
      for (let i = 0; sessionId && i < 5 && isAwaitingConfirmation(result); i++) {
        const rn = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message:
              "Yes — the operator approved the entire deploy + test-run in the UI. " +
              "Continue ALL remaining steps now without pausing, including closing " +
              "the test incident, then give the final report.",
            session_id: sessionId,
          }),
        });
        if (!rn.ok) break;
        const next = await readChatStream(rn);
        result = next.answer || result;
        sessionId = next.sessionId || sessionId;
      }
      setDeployAnswer(result || "(no response)");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeploying(false);
    }
  }, [yaml]);

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
    <div className="h-screen overflow-y-auto custom-scrollbar">
      <div className="max-w-[1100px] mx-auto px-8 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <div
            className="w-11 h-11 rounded-xl flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, rgba(167,200,255,0.2), rgba(25,99,179,0.12))",
              border: "0.5px solid rgba(167,200,255,0.2)",
            }}
          >
            <span
              className="material-symbols-outlined text-2xl text-primary"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              design_services
            </span>
          </div>
          <div>
            <h1 className="text-xl font-bold text-on-surface">Playbook Builder</h1>
            <p className="text-xs text-on-surface-variant/60">
              Draft a Cortex XSOAR playbook grounded in the ~800 real playbooks in the
              soar-playbooks knowledge base, then deploy + test-run it on a throwaway
              incident in your connected tenant.
            </p>
          </div>
        </div>

        {/* Form */}
        <div className="rounded-2xl p-5 space-y-4" style={glass}>
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
          <div className="flex items-end gap-3 flex-wrap">
            <div className="space-y-1.5 flex-1 min-w-[240px]">
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
              className="px-4 py-2.5 rounded-lg text-sm font-medium bg-primary-container text-on-primary-container disabled:opacity-50 transition-opacity"
            >
              {generating ? "Building…" : "Build playbook"}
            </button>
          </div>
        </div>

        {error ? (
          <div className="rounded-xl border border-error/30 bg-error/10 p-3 text-xs text-error">
            {error}
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
              <div className="rounded-2xl p-4 flex flex-wrap items-center gap-3" style={glass}>
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

            {/* v0.2.26 — deploy confirm (mutates the tenant) */}
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
              <div className="rounded-2xl p-5 space-y-2" style={glass}>
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

            <div className="rounded-2xl p-5" style={glass}>
              <MarkdownContent>{answer}</MarkdownContent>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
