/**
 * Block-close-without-verdict — Guardian IR builtin (v0.2.5).
 *
 * Fires on PreToolUse for `xsoar_close_incident` (set the hook's tool glob to
 * `xsoar_close_incident`). Before the close lands, it looks up the local
 * Guardian Issue tracking that XSOAR incident (by `source_ref`) and DENIES the
 * close when the Issue has no recorded `VERDICT:` line in its summary — the
 * single most damaging analyst mistake is closing an incident with no recorded
 * disposition. The skill (`xsoar_case_investigation`) writes the leading
 * `VERDICT:` line at resolve; this enforces it deterministically instead of
 * trusting the model to remember.
 *
 * Catalog-vs-credential boundary: this builtin reads ONLY investigation
 * metadata over the in-process MCP REST surface (`GET /api/v1/issues`) — never
 * a SecretStore value. It is on the catalog/workflow side of the guardrail.
 *
 * Default is conservative: if NO Guardian Issue tracks the incident, the close
 * is ALLOWED (the incident isn't a Guardian-tracked investigation — not this
 * hook's concern). Set `block_if_untracked` to also deny closes of incidents
 * Guardian never opened an Issue for.
 *
 * Pair with `failurePolicy: block` (fail-closed) so a lookup error doesn't let
 * an un-vetted close slip through.
 */

import type { BuiltinHookSpec } from "./types";
import { callMcpServer } from "@/lib/mcp-proxy";

interface IssueRow {
  id: string;
  source_ref: string | null;
  summary: string | null;
  status: string;
}
interface IssuesResponse {
  issues?: IssueRow[];
}

/** True when the summary leads with (or contains) a `VERDICT:` line — the
 *  disposition marker the investigation skill writes at resolve. */
function hasVerdict(summary: string | null | undefined): boolean {
  if (!summary) return false;
  return /^\s*VERDICT\s*:/im.test(summary);
}

/** Pull the incident ref(s) the close targets. xsoar_close_incident takes
 *  `incident_ids` (array); we also accept a bare `incident_id` for safety. */
function extractIncidentRefs(args: Record<string, unknown>): string[] {
  const out: string[] = [];
  const ids = args.incident_ids;
  if (Array.isArray(ids)) {
    for (const v of ids) if (v != null) out.push(String(v));
  }
  const single = args.incident_id ?? args.id;
  if (single != null) out.push(String(single));
  return Array.from(new Set(out));
}

export const blockCloseWithoutVerdictBuiltin: BuiltinHookSpec = {
  name: "block-close-without-verdict",
  displayName: "Block close without verdict",
  description:
    "On PreToolUse for xsoar_close_incident, denies the close when the local " +
    "Guardian Issue tracking that incident has no recorded VERDICT: line. " +
    "Enforces a documented disposition before any incident is closed. Set the " +
    "hook's tool glob to xsoar_close_incident and use failurePolicy: block.",
  icon: "gavel",
  compatibleEvents: ["PreToolUse"] as const,
  configFields: [
    {
      key: "block_if_untracked",
      label: "Also block when no Guardian Issue tracks the incident",
      type: "boolean",
      defaultValue: false,
      helper:
        "Off (default): closes of incidents Guardian never opened an Issue for " +
        "are allowed. On: deny unless a tracked Issue with a VERDICT exists " +
        "(strictest — every close must trace to a Guardian investigation).",
      required: false,
    },
  ] as const,
  validateConfig(raw) {
    if (raw && typeof raw !== "object") {
      return { ok: false, error: "config must be an object" };
    }
    const cfg = (raw ?? {}) as Record<string, unknown>;
    const v = cfg.block_if_untracked;
    if (v !== undefined && typeof v !== "boolean") {
      return { ok: false, error: "block_if_untracked must be a boolean" };
    }
    return { ok: true, config: { block_if_untracked: v === true } };
  },
  async handle(payload, config) {
    if (payload.event !== "PreToolUse") return null;
    // Defensive: only act on the close tool even if the operator's glob is broad.
    if (!/close_incident/i.test(payload.toolName)) return null;

    const refs = extractIncidentRefs(payload.args ?? {});
    if (refs.length === 0) {
      // No incident id in the args — can't evaluate; don't block on a shape we
      // don't understand (failurePolicy still governs hard errors).
      return null;
    }

    const blockIfUntracked = config.block_if_untracked === true;

    // Read the Issue list once (catalog metadata; no secret). Throwing here
    // lets the hook's failurePolicy (block) fail-closed.
    const resp = await callMcpServer<IssuesResponse>("/api/v1/issues", {
      method: "GET",
    });
    const issues = resp.issues ?? [];

    for (const ref of refs) {
      const tracked = issues.filter((i) => i.source_ref === ref);
      if (tracked.length === 0) {
        if (blockIfUntracked) {
          return {
            decision: "deny",
            reason:
              `XSOAR incident ${ref} has no Guardian Issue — open and ` +
              `investigate it (record a VERDICT) before closing. ` +
              `(block-close-without-verdict, strict mode)`,
            metadata: { check: "verdict-gate", incident: ref, tracked: false },
          };
        }
        continue; // untracked + not strict → allow this ref
      }
      const withVerdict = tracked.some((i) => hasVerdict(i.summary));
      if (!withVerdict) {
        const iss = tracked[0];
        return {
          decision: "deny",
          reason:
            `Guardian Issue ${iss.id} (XSOAR incident ${ref}) has no recorded ` +
            `VERDICT — record a disposition (VERDICT: TRUE POSITIVE | FALSE ` +
            `POSITIVE | BENIGN | …) before closing the incident. ` +
            `(block-close-without-verdict)`,
          metadata: { check: "verdict-gate", incident: ref, issue: iss.id, tracked: true },
        };
      }
    }
    // Every targeted incident either has a verdict or is untracked-and-allowed.
    return null;
  },
};
