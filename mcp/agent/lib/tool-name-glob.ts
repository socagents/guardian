/**
 * Canonical tool-name glob matcher (v0.2.9).
 *
 * Tool names reach the chat-route's matching layer in two separator
 * conventions, depending on which model emitted the function call and how
 * that model sanitizes catalog names:
 *
 *   - dotted:     `xsoar.close_incident`   — the connector-namespaced
 *     `<connector>.<tool>` form (e.g. gemini-3.5-flash emits this verbatim)
 *   - underscore: `xsoar_close_incident`   — the flat-alias form most
 *     Gemini variants emit (see `deriveConnectorId` in app/api/chat/route.ts,
 *     which already treats `xsoar_`/`cortex_`/`guardian_web_` prefixes and the
 *     dotted form as the SAME tool; the approval gate matches either too).
 *
 * The MCP layer resolves both downstream, so the tool fires either way — but
 * a hook author, a job permission policy, or a subagent allow/deny scope that
 * was written with one separator must still match a call emitted with the
 * other. Pre-v0.2.9 the matcher was an exact anchored regex, so a glob of
 * `xsoar_close_incident` silently failed to match a `xsoar.close_incident`
 * call: the verdict-gate hook never denied, deny-scoped subagents could reach
 * connector tools, and `denied_tools` policies leaked. (Root-caused live: the
 * PreToolUse fire-site saw `tool=xsoar.close_incident` while the hook glob was
 * `xsoar_close_incident`, so `matchesHook` returned false and zero
 * `hook_dispatched` audit fired.)
 *
 * Fix: normalize `.` → `_` on BOTH subject and pattern before matching, so a
 * glob authored either way matches a tool invoked either way. Builtin names
 * (`issue_create`, `indicators_list`) contain no dots and are unaffected. This
 * is the single matcher behind hook tool-globs (`lib/hooks.ts`), subagent
 * allow/deny scoping (`filterToolsForAgent` in the chat route), and job
 * permission policies (`lib/permission-policy.ts`). It has no imports, so both
 * `hooks.ts` (which imports hook-builtins) and `permission-policy.ts` can
 * depend on it without the circular-dependency surface that previously forced
 * the matcher to be duplicated in both files.
 */

/** Collapse the connector separator: dotted `<connector>.<tool>` and the flat
 *  underscore alias normalize to the same string for matching purposes. */
function normalizeToolName(s: string): string {
  return s.replace(/\./g, "_");
}

/**
 * Match `subject` (a tool name) against a comma-separated list of globs.
 * `*` matches any sequence, `?` matches a single character; comma-separated
 * items are OR'd. Each item is trimmed; empty items are ignored. Separator-
 * insensitive: `.` and `_` are equivalent on both sides.
 */
export function toolNameMatchesGlob(
  subject: string,
  patternList: string,
): boolean {
  const subj = normalizeToolName(subject);
  return patternList
    .split(",")
    .map((p) => p.trim())
    .filter((p) => p.length > 0)
    .some((p) => matchOne(subj, normalizeToolName(p)));
}

function matchOne(subject: string, pattern: string): boolean {
  // Convert glob to anchored regex: escape regex specials, then `.*` for `*`,
  // `.` for `?`. (Patterns are already separator-normalized, so any remaining
  // escape of `.` is a no-op — dots became underscores upstream.)
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(
    "^" + escaped.replace(/\*/g, ".*").replace(/\?/g, ".") + "$",
  );
  return re.test(subject);
}
