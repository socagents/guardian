/**
 * Slack approval builtin — Issue #26 (v0.5.21).
 *
 * Refactored from `lib/slack-approval-hook.ts` (which was a JSON-snippet
 * helper builders shipped pre-builtin-transport). The behavior is the
 * same: POST the `PreToolUse` payload to an operator-managed webhook
 * receiver that pings Slack with Approve/Deny buttons, wait for the
 * analyst's click, return their decision. The difference is the
 * operator now installs it from `/settings/hooks` with a single
 * dropdown pick + URL + auth-header — no JSON pasting, no separate
 * helper file to copy from.
 *
 * The legacy `slack-approval-hook.ts` helper is kept for backwards
 * compatibility (any operator who pasted a hook payload from it
 * continues to work — it produces an `http`-transport hook that
 * functions identically to this builtin). New installations go
 * through the builtin path.
 */

import type { BuiltinHookSpec } from "./types";
import { callMcpServer } from "@/lib/mcp-proxy";

export const slackApprovalBuiltin: BuiltinHookSpec = {
  name: "slack-approval",
  displayName: "Slack approval",
  description:
    "Routes destructive-tool approvals through Slack. POSTs the PreToolUse " +
    "payload to your webhook receiver that pings #soc-ops with " +
    "Approve/Deny buttons, then returns the analyst's decision.",
  icon: "chat",
  compatibleEvents: ["PreToolUse", "PermissionRequest"] as const,
  configFields: [
    {
      key: "webhookUrl",
      label: "Webhook URL",
      type: "url",
      placeholder: "https://your-receiver.example.com/pre-tool-approval-poll",
      helper:
        "Your slack-approval-receiver endpoint (Lambda / Cloud Run / Slack-bot). " +
        "POSTed with the PreToolUse payload; must respond with " +
        '`{"decision":"allow"|"deny","reason":"..."}`.',
      required: true,
    },
    {
      key: "authHeaderName",
      label: "Auth header name (optional)",
      type: "string",
      placeholder: "X-Guardian-Auth",
      helper:
        "If your receiver requires an auth header, name it here. " +
        "Leave blank for no auth header.",
    },
    {
      key: "authHeaderValue",
      label: "Auth header value (optional)",
      type: "secret-ref",
      placeholder: "secret:SLACK_APPROVAL_TOKEN",
      helper:
        "Header value. Use `secret:<ENV_NAME>` to read from the agent's " +
        "environment instead of storing the token in plaintext.",
    },
  ] as const,
  validateConfig(raw) {
    if (!raw || typeof raw !== "object") {
      return { ok: false, error: "config must be an object" };
    }
    const cfg = raw as Record<string, unknown>;
    const webhookUrl = cfg.webhookUrl;
    if (typeof webhookUrl !== "string" || !webhookUrl.trim()) {
      return { ok: false, error: "webhookUrl is required" };
    }
    try {
      const parsed = new URL(webhookUrl);
      if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
        return {
          ok: false,
          error: "webhookUrl must be http(s):// — Slack receivers expect HTTP",
        };
      }
    } catch {
      return { ok: false, error: `webhookUrl is not a valid URL: ${webhookUrl}` };
    }
    const authName = cfg.authHeaderName;
    if (authName !== undefined && typeof authName !== "string") {
      return { ok: false, error: "authHeaderName must be a string when set" };
    }
    const authValue = cfg.authHeaderValue;
    if (authValue !== undefined && typeof authValue !== "string") {
      return { ok: false, error: "authHeaderValue must be a string when set" };
    }
    // Both-or-neither — partial auth header is a misconfig.
    const hasName = typeof authName === "string" && authName.trim().length > 0;
    const hasValue = typeof authValue === "string" && authValue.trim().length > 0;
    if (hasName !== hasValue) {
      return {
        ok: false,
        error: "authHeaderName + authHeaderValue must be set together (or both blank)",
      };
    }
    return {
      ok: true,
      config: {
        webhookUrl,
        ...(hasName && hasValue
          ? { authHeaderName: authName, authHeaderValue: authValue }
          : {}),
      },
    };
  },
  async handle(payload, config, options) {
    const webhookUrl = config.webhookUrl as string;
    const authHeaderName = config.authHeaderName as string | undefined;
    const authHeaderValue = config.authHeaderValue as string | undefined;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (authHeaderName && authHeaderValue) {
      // #HOOK-F14 — resolve `secret:<ref>` via the MCP SecretStore
      // (audited), fail-closed: drop the auth header if the ref doesn't
      // resolve rather than leaking a raw env var.
      const resolved = await resolveSecretRef(authHeaderValue);
      if (resolved !== null) {
        headers[authHeaderName] = resolved;
      } else {
        console.warn(
          `[slack-approval] auth header secret ref did not resolve via the SecretStore; omitting header (fail-closed)`,
        );
      }
    }
    const resp = await fetch(webhookUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: options.signal,
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(
        `slack-approval receiver HTTP ${resp.status}: ${text.slice(0, 200)}`,
      );
    }
    const text = await resp.text();
    if (!text.trim()) return {};
    try {
      return JSON.parse(text) as Awaited<ReturnType<BuiltinHookSpec["handle"]>>;
    } catch (err) {
      throw new Error(
        `slack-approval receiver returned non-JSON body: ${
          err instanceof Error ? err.message : String(err)
        }`,
      );
    }
  },
};

/** #HOOK-F14 — resolve a `secret:<ref>` against the MCP SecretStore
 *  (an audited read via POST /api/v1/secrets/resolve). Plain values
 *  (no `secret:` prefix) pass through unchanged. Returns null when a
 *  `secret:` ref can't be resolved (missing secret / bad ref / MCP
 *  unreachable) so the caller can fail-closed — NEVER falls back to
 *  raw process.env. Mirrors `resolveSecretEnv` in `lib/hook-runner.ts`. */
async function resolveSecretRef(value: string): Promise<string | null> {
  if (!value.startsWith("secret:")) return value;
  const ref = value.slice("secret:".length);
  try {
    const body = await callMcpServer<{ value?: string }>(
      "/api/v1/secrets/resolve",
      { method: "POST", body: { ref } },
    );
    return typeof body.value === "string" ? body.value : null;
  } catch {
    return null;
  }
}
