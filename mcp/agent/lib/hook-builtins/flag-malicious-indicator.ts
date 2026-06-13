/**
 * Flag-malicious-indicator — Guardian IR builtin (v0.2.5).
 *
 * Fires on PostToolUse for `xsoar_enrich_indicator` (set the hook's tool glob
 * to `xsoar_enrich_indicator`). It scans the enrichment result for a DBotScore
 * at or above the malicious threshold (3 by default) and injects a
 * confirmed-bad flag into the agent's next turn — so an analyst never misses a
 * malicious verdict buried in a long enrichment payload, and the agent is
 * nudged to record the indicator + recommend containment.
 *
 * PostToolUse honors `injectContext` only (a tool that already ran can't be
 * undone), so this is purely informational — it can never block a turn. Pair
 * with `failurePolicy: warn`.
 *
 * Inspect-only: it reads the tool RESULT already in the payload — no external
 * call, no SecretStore access. Catalog/workflow side of the guardrail.
 */

import type { BuiltinHookSpec } from "./types";

/** DBotScore semantics (mirrors investigation.ts dbotMeta): 3 = malicious. */
const KEY_RE = /^(dbot[_]?score|score)$/i;

/** Walk an arbitrary tool-result value, collecting numeric DBotScore-like
 *  values at/above the threshold. Bounded depth + breadth so a huge result
 *  can't blow the stack or stall the turn. */
function findScoresAtOrAbove(value: unknown, threshold: number): number[] {
  const hits: number[] = [];
  let visited = 0;
  const walk = (v: unknown, depth: number) => {
    if (depth > 8 || visited > 5000) return;
    visited++;
    if (Array.isArray(v)) {
      for (const item of v) walk(item, depth + 1);
      return;
    }
    if (v && typeof v === "object") {
      for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
        if (KEY_RE.test(k) && typeof val === "number" && val >= threshold) {
          hits.push(val);
        }
        walk(val, depth + 1);
      }
    }
  };
  walk(value, 0);
  return hits;
}

/** Best-effort: pull the indicator value the enrichment was about, from the
 *  call args (most reliable) or the result. Used only to make the injected
 *  line specific; absence is non-fatal. */
function indicatorLabel(args: Record<string, unknown>): string {
  const v = args.value ?? args.indicator ?? args.indicator_value;
  return v != null ? String(v) : "the enriched indicator";
}

export const flagMaliciousIndicatorBuiltin: BuiltinHookSpec = {
  name: "flag-malicious-indicator",
  displayName: "Flag malicious indicator",
  description:
    "On PostToolUse for xsoar_enrich_indicator, scans the result for a " +
    "DBotScore at/above the malicious threshold (3) and injects a " +
    "confirmed-bad flag into the next turn — so a malicious verdict is never " +
    "missed and the agent is nudged to record it + recommend containment. " +
    "Set the hook's tool glob to xsoar_enrich_indicator; use failurePolicy: warn.",
  icon: "coronavirus",
  compatibleEvents: ["PostToolUse"] as const,
  configFields: [
    {
      key: "min_score",
      label: "Malicious DBotScore threshold",
      type: "number",
      min: 1,
      max: 3,
      defaultValue: 3,
      helper:
        "Inject when the enrichment returns a DBotScore at/above this value. " +
        "3 = malicious (default). Lower to 2 to also flag 'suspicious'.",
      required: false,
    },
  ] as const,
  validateConfig(raw) {
    if (raw && typeof raw !== "object") {
      return { ok: false, error: "config must be an object" };
    }
    const cfg = (raw ?? {}) as Record<string, unknown>;
    const s = cfg.min_score;
    if (s === undefined) return { ok: true, config: { min_score: 3 } };
    if (typeof s !== "number" || s < 1 || s > 3) {
      return { ok: false, error: "min_score must be a number in [1, 3]" };
    }
    return { ok: true, config: { min_score: Math.floor(s) } };
  },
  async handle(payload, config) {
    if (payload.event !== "PostToolUse") return null;
    // Defensive: only act on the enrich tool even if the operator's glob is broad.
    if (!/enrich_indicator/i.test(payload.toolName)) return null;

    const threshold = (config.min_score as number) ?? 3;
    const scores = findScoresAtOrAbove(payload.result, threshold);
    if (scores.length === 0) return null;

    const max = Math.max(...scores);
    const label =
      max >= 3 ? "malicious" : max === 2 ? "suspicious" : "flagged";
    const ioc = indicatorLabel(payload.args ?? {});
    return {
      injectContext:
        `[flag-malicious-indicator] Enrichment of ${ioc} returned DBotScore ` +
        `${max} (${label}). Treat as confirmed-bad: record it with ` +
        `indicator_upsert (dbot_score ${max}), relate it to the issue's other ` +
        `IOCs, and recommend containment in your conclusions.`,
      metadata: { check: "dbot-flag", dbot: max, ioc },
    };
  },
};
