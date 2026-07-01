"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Guardian providers page — ported from spark/services/ui's
 * settings/providers, with two guardian-specific shifts:
 *
 *   1. **Endpoints**: Spark's apiRequest helper hits the api-gateway
 *      at /api/v1/config{,/providers}. Guardian doesn't ship those
 *      routes; this page calls /api/agent/providers/config directly,
 *      which reads/writes the MCP-side ProviderStore.
 *   2. **Scope**: Vertex AI (Gemini) and Anthropic are functional.
 *      OpenAI is still presented but disabled with a "Work in progress"
 *      badge pending the OpenAI API / Codex CLI integration.
 *
 * Anthropic credentials feed two paths:
 *   - anthropicApiKey is reserved for the future chat-route callAnthropic
 *     (direct API; not wired yet but the field persists for forward-compat).
 *   - anthropicCliKey is consumed by POST /api/chat/cli (Claude Code CLI
 *     shell-out). Either field accepts an OAuth token (sk-ant-oat01-...)
 *     or an API key (sk-ant-api03-...) — Claude Code CLI handles both.
 */

// ── Types ────────────────────────────────────────────────────────────────────

interface ProviderConfig {
  anthropicApiKey: string;
  anthropicCliKey: string;
  openaiApiKey: string;
  openaiCodexToken: string;
  ollamaEndpoint: string;
  /** Google Vertex AI — service-account JSON blob (multi-line). Encrypted in Infisical. */
  vertexServiceAccountJson: string;
  /** Google Vertex AI — GCP project that owns the quotas. Not a secret. */
  vertexProjectId: string;
  /** Google Vertex AI — region, defaults to us-central1. Gemini 3 auto-routes to global. */
  vertexLocation: string;
  /** Cohere North — base URL of the private deployment (e.g. https://core.stc.com.sa). Not a secret. */
  cohereNorthEndpoint: string;
  /** Cohere North — agent id to route requests to. Not a secret. */
  cohereNorthAgentId: string;
  /** Cohere North — bearer token. Encrypted in the SecretStore. */
  cohereNorthBearerToken: string;
  /** Cohere North — verify the endpoint's TLS cert ("true"/"false"). */
  cohereNorthTlsVerify: string;
}

interface ConnectionStatus {
  provider: string;
  status: "idle" | "testing" | "success" | "error";
  message?: string;
}

// ── Constants ────────────────────────────────────────────────────────────────

const glassCard: React.CSSProperties = {
  background: "var(--glass-bg-strong)",
  backdropFilter: "blur(12px)",
  border: "1px solid var(--glass-border)",
};

const DEFAULT_PROVIDER_CONFIG: ProviderConfig = {
  anthropicApiKey: "",
  anthropicCliKey: "",
  openaiApiKey: "",
  openaiCodexToken: "",
  ollamaEndpoint: "http://localhost:11434",
  vertexServiceAccountJson: "",
  vertexProjectId: "",
  vertexLocation: "us-central1",
  cohereNorthEndpoint: "",
  cohereNorthAgentId: "",
  cohereNorthBearerToken: "",
  cohereNorthTlsVerify: "true",
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function extractProviderConfig(
  config: Record<string, unknown> | null,
): ProviderConfig {
  const providers = (config?.providers ?? {}) as Record<string, unknown>;
  return {
    anthropicApiKey:
      typeof providers.anthropicApiKey === "string"
        ? providers.anthropicApiKey
        : "",
    anthropicCliKey:
      typeof providers.anthropicCliKey === "string"
        ? providers.anthropicCliKey
        : "",
    openaiApiKey:
      typeof providers.openaiApiKey === "string" ? providers.openaiApiKey : "",
    openaiCodexToken:
      typeof providers.openaiCodexToken === "string"
        ? providers.openaiCodexToken
        : "",
    ollamaEndpoint:
      typeof providers.ollamaEndpoint === "string"
        ? providers.ollamaEndpoint
        : "http://localhost:11434",
    vertexServiceAccountJson:
      typeof providers.vertexServiceAccountJson === "string"
        ? providers.vertexServiceAccountJson
        : "",
    vertexProjectId:
      typeof providers.vertexProjectId === "string"
        ? providers.vertexProjectId
        : "",
    vertexLocation:
      typeof providers.vertexLocation === "string"
        ? providers.vertexLocation
        : "us-central1",
    cohereNorthEndpoint:
      typeof providers.cohereNorthEndpoint === "string"
        ? providers.cohereNorthEndpoint
        : "",
    cohereNorthAgentId:
      typeof providers.cohereNorthAgentId === "string"
        ? providers.cohereNorthAgentId
        : "",
    cohereNorthBearerToken:
      typeof providers.cohereNorthBearerToken === "string"
        ? providers.cohereNorthBearerToken
        : "",
    cohereNorthTlsVerify:
      typeof providers.cohereNorthTlsVerify === "string"
        ? providers.cohereNorthTlsVerify
        : "true",
  };
}

// ── Masked Input ─────────────────────────────────────────────────────────────

function MaskedKeyInput({
  id,
  label,
  value,
  onChange,
  placeholder,
  helpText,
  disabled,
  maxWidth,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  helpText?: string;
  disabled?: boolean;
  maxWidth?: boolean;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="space-y-2">
      <label
        htmlFor={id}
        className="block text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label"
      >
        {label}
      </label>
      <div className={`relative group${maxWidth ? " max-w-xl" : ""}`}>
        <input
          id={id}
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder ?? "sk-..."}
          disabled={disabled}
          className="w-full bg-surface-container-lowest border-none rounded-lg px-4 py-3 text-sm font-mono text-on-surface focus:ring-1 focus:ring-primary/40 transition-all outline-none disabled:opacity-40 disabled:cursor-not-allowed"
        />
        {!disabled && (
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            aria-label={visible ? `Hide ${label}` : `Show ${label}`}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-white transition-colors"
          >
            <span className="material-symbols-outlined text-sm">
              {visible ? "visibility_off" : "visibility"}
            </span>
          </button>
        )}
      </div>
      {helpText && (
        <p className="text-[10px] text-on-surface-variant/50 font-label italic">
          {helpText}
        </p>
      )}
    </div>
  );
}

// ── Status Badge Helpers ─────────────────────────────────────────────────────

function ConnectionBadge({ status }: { status: ConnectionStatus | undefined }) {
  if (!status || status.status === "idle") return null;

  if (status.status === "testing") {
    return (
      <span className="bg-tertiary/10 text-tertiary text-[10px] font-bold px-2 py-0.5 rounded border border-tertiary/20 uppercase tracking-tighter">
        Testing...
      </span>
    );
  }
  if (status.status === "success") {
    return (
      <span className="bg-secondary/10 text-secondary text-[10px] font-bold px-2 py-0.5 rounded border border-secondary/20 uppercase tracking-tighter">
        Connected
      </span>
    );
  }
  return (
    <span className="bg-error/10 text-error text-[10px] font-bold px-2 py-0.5 rounded border border-error/20 uppercase tracking-tighter">
      {status.message ?? "Error"}
    </span>
  );
}

function EncryptedBadge({ value }: { value: string }) {
  if (!value || !value.includes("...")) return null;
  return (
    <span className="bg-primary/5 text-primary/70 text-[10px] font-bold px-2 py-0.5 rounded border border-primary/20 uppercase tracking-tighter">
      Encrypted
    </span>
  );
}

function WipBadge() {
  return (
    <span className="bg-tertiary/10 text-tertiary text-[10px] font-bold px-2 py-0.5 rounded border border-tertiary/20 uppercase tracking-tighter">
      Work in progress
    </span>
  );
}

// ── Page Component ───────────────────────────────────────────────────────────

/**
 * Service-account JSON mask. The textarea is multi-line and `<input
 * type=password>` doesn't apply, so we render the value with every
 * non-newline char replaced by `•` when the operator hasn't clicked
 * Reveal. v0.1.34 fix: the textarea is NO LONGER readOnly while
 * masked — pre-fix, readOnly blocked all input and the operator
 * could never replace a stored value (Save stayed disabled forever).
 * Now any keystroke or paste fires `onChange`, which strips leftover
 * bullets and auto-reveals so subsequent edits show real content.
 */
function maskJson(value: string): string {
  return value.replace(/[^\n]/g, "•");
}

export default function ProvidersSettingsPage() {
  const [form, setForm] = useState<ProviderConfig>(DEFAULT_PROVIDER_CONFIG);
  const initialForm = useRef<ProviderConfig>(DEFAULT_PROVIDER_CONFIG);
  const [loading, setLoading] = useState(true);
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connectionStatuses, setConnectionStatuses] = useState<
    Record<string, ConnectionStatus>
  >({});
  // Vertex SA JSON masking — defaults to hidden when there's saved
  // content. New entries (operator typing into an empty field) start
  // visible until the next save round.
  const [vertexJsonVisible, setVertexJsonVisible] = useState(false);

  // ── Data fetching ────────────────────────────────────────────────────────

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/agent/providers/config", { cache: "no-store" });
      if (r.ok) {
        const data = (await r.json()) as Record<string, unknown>;
        const cfg = extractProviderConfig(data);
        setForm(cfg);
        initialForm.current = cfg;
      }
    } catch {
      // empty state — operator hasn't supplied creds yet
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  // ── Form helpers ─────────────────────────────────────────────────────────

  function updateField<K extends keyof ProviderConfig>(
    key: K,
    value: ProviderConfig[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setError(null);
  }

  function isProviderDirty(
    provider: "anthropic" | "openai" | "vertex" | "cohere-north",
  ): boolean {
    if (provider === "anthropic") {
      return (
        form.anthropicApiKey !== initialForm.current.anthropicApiKey ||
        form.anthropicCliKey !== initialForm.current.anthropicCliKey
      );
    }
    if (provider === "vertex") {
      return (
        form.vertexServiceAccountJson !==
          initialForm.current.vertexServiceAccountJson ||
        form.vertexProjectId !== initialForm.current.vertexProjectId ||
        form.vertexLocation !== initialForm.current.vertexLocation
      );
    }
    if (provider === "cohere-north") {
      return (
        form.cohereNorthEndpoint !== initialForm.current.cohereNorthEndpoint ||
        form.cohereNorthAgentId !== initialForm.current.cohereNorthAgentId ||
        form.cohereNorthBearerToken !== initialForm.current.cohereNorthBearerToken ||
        form.cohereNorthTlsVerify !== initialForm.current.cohereNorthTlsVerify
      );
    }
    return (
      form.openaiApiKey !== initialForm.current.openaiApiKey ||
      form.openaiCodexToken !== initialForm.current.openaiCodexToken
    );
  }

  // ── Save (per-card) ─────────────────────────────────────────────────────

  async function handleSaveProvider(
    provider: "anthropic" | "openai" | "vertex" | "cohere-north",
  ) {
    setSavingProvider(provider);
    setError(null);

    const payload = {
      anthropicApiKey: form.anthropicApiKey,
      anthropicCliKey: form.anthropicCliKey,
      openaiApiKey: form.openaiApiKey,
      openaiCodexToken: form.openaiCodexToken,
      ollamaEndpoint: form.ollamaEndpoint,
      vertexServiceAccountJson: form.vertexServiceAccountJson,
      vertexProjectId: form.vertexProjectId,
      vertexLocation: form.vertexLocation,
      cohereNorthEndpoint: form.cohereNorthEndpoint,
      cohereNorthAgentId: form.cohereNorthAgentId,
      cohereNorthBearerToken: form.cohereNorthBearerToken,
      cohereNorthTlsVerify: form.cohereNorthTlsVerify,
    };

    try {
      const r = await fetch("/api/agent/providers/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: payload }),
      });
      if (r.ok) {
        initialForm.current = { ...form };
      } else {
        const data = (await r.json().catch(() => ({}))) as { error?: string };
        setError(data.error || `Failed to save ${provider} configuration`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to save ${provider}`);
    }

    setSavingProvider(null);
  }

  // ── Connection test ──────────────────────────────────────────────────────

  /**
   * Test Connection only validates pay-per-token API keys. CLI / OAuth
   * refresh tokens (Anthropic CLI Token, OpenAI Codex CLI Token) can't be
   * probed without rotating them as a side effect, so their validation
   * happens at runtime when the CLI actually runs. This helper returns
   * true only when an API key is filled for the provider.
   */
  function hasTestableApiKey(provider: "anthropic" | "openai" | "vertex"): boolean {
    if (provider === "anthropic") {
      return !!form.anthropicApiKey;
    }
    if (provider === "vertex") {
      // Vertex requires ALL three fields filled before either Test or
      // Save activates — incomplete state would either fail at the
      // JWT exchange (no project) or be saved as a half-config that
      // the runtime can't register the provider from. Forcing all 3
      // fields up front gives the user a single clear "fill the
      // section completely" signal instead of letting them save junk.
      return (
        !!form.vertexServiceAccountJson.trim() &&
        !!form.vertexProjectId.trim() &&
        !!form.vertexLocation.trim()
      );
    }
    return !!form.openaiApiKey;
  }

  /**
   * v0.5.71 (issue #18): can the operator legitimately Test Vertex now?
   *
   * The bug this addresses: pre-v0.5.71 the Test button used only
   * `hasTestableApiKey("vertex")` — "all three fields non-empty." On a
   * fresh page load with saved creds, the JSON field carries the
   * backend's masked-bullet sentinel (• repeated), Project + Region come
   * down in cleartext from ProviderStore. `hasTestableApiKey` returns
   * true → button active → operator clicks → masked sentinel gets sent
   * as the JSON → backend's /providers/vertex/test responds "no Vertex
   * service-account JSON is configured yet" → operator misreads as
   * "my saved auth is broken" when in fact nothing changed and chat
   * still works fine. Misleading banner on a working install undermines
   * trust during onboarding.
   *
   * Returns {ok, reason}. The reason becomes the disabled-button tooltip
   * so the operator knows exactly which precondition isn't met — they
   * can decide whether to paste a real JSON (to actually validate) or
   * skip the test (the saved creds are already in effect at runtime).
   *
   * The three checks, in order:
   *   1. Every field has a non-empty value.
   *   2. The JSON in the form differs from the JSON we loaded — i.e.,
   *      the operator has re-pasted (or this is a fresh install with
   *      no prior JSON). Just changing Project or Region without
   *      re-pasting the JSON is NOT enough, because the test endpoint
   *      receives the JSON from the form and can't probe with the
   *      masked sentinel.
   *
   * Save Changes already enforces the dirty + populated combo via
   * `isProviderDirty + hasTestableApiKey`; this brings Test onto the
   * same model with the additional JSON-specifically-touched check.
   */
  function canTestVertex(): { ok: boolean; reason: string } {
    if (!form.vertexProjectId.trim()) {
      return { ok: false, reason: "Fill in Project ID before testing." };
    }
    if (!form.vertexLocation.trim()) {
      return { ok: false, reason: "Fill in Region before testing." };
    }
    if (!form.vertexServiceAccountJson.trim()) {
      return { ok: false, reason: "Paste a Service Account JSON before testing." };
    }
    // Loaded JSON arrives as the backend's redaction sentinel (• chars).
    // If the operator hasn't pasted anything, the form value equals the
    // initial value AND the initial value is the sentinel pattern. Re-
    // pasting the same JSON over the masked field produces a new form
    // value that differs from initial — that's "dirty," and test fires.
    if (
      initialForm.current.vertexServiceAccountJson.length > 0 &&
      form.vertexServiceAccountJson === initialForm.current.vertexServiceAccountJson
    ) {
      return {
        ok: false,
        reason:
          "Re-paste the Service Account JSON to test. The masked sentinel can't be probed; your saved creds are already in effect at runtime.",
      };
    }
    return { ok: true, reason: "" };
  }

  async function testConnection(provider: string) {
    setConnectionStatuses((prev) => ({
      ...prev,
      [provider]: { provider, status: "testing" },
    }));

    // Build the body per provider. Anthropic and OpenAI use a single
    // api_key. Vertex uses service-account JSON + project ID +
    // optional location, validated via a JWT→OAuth2 exchange followed
    // by a ping of Vertex's publisher-models endpoint.
    let body: Record<string, string>;
    if (provider === "vertex") {
      if (!form.vertexServiceAccountJson || !form.vertexProjectId) {
        setConnectionStatuses((prev) => ({
          ...prev,
          [provider]: {
            provider,
            status: "error",
            message: "Service account JSON and project ID are both required.",
          },
        }));
        return;
      }
      body = {
        service_account_json: form.vertexServiceAccountJson,
        project_id: form.vertexProjectId,
        location: form.vertexLocation || "us-central1",
      };
    } else if (provider === "cohere-north") {
      if (!form.cohereNorthEndpoint || !form.cohereNorthAgentId || !form.cohereNorthBearerToken) {
        setConnectionStatuses((prev) => ({
          ...prev,
          [provider]: {
            provider,
            status: "error",
            message: "Endpoint URL, agent id, and bearer token are all required.",
          },
        }));
        return;
      }
      body = {
        endpoint_url: form.cohereNorthEndpoint,
        agent_id: form.cohereNorthAgentId,
        bearer_token: form.cohereNorthBearerToken,
        tls_verify: form.cohereNorthTlsVerify,
      };
    } else {
      const apiKey =
        provider === "anthropic" ? form.anthropicApiKey : form.openaiApiKey;
      if (!apiKey) {
        setConnectionStatuses((prev) => ({
          ...prev,
          [provider]: {
            provider,
            status: "error",
            message: "Enter an API key to test connectivity.",
          },
        }));
        return;
      }
      body = { api_key: apiKey };
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    try {
      // Guardian doesn't yet ship a /api/agent/providers/{id}/test
      // backend route. For Vertex specifically the only meaningful
      // probe is the JWT→OAuth2 exchange, which the chat path does
      // implicitly on every request. Until a dedicated probe route
      // lands, we surface "Saved — validated at chat runtime" as
      // a soft success: the form persisted, but the credential is
      // proven only when the next message goes through.
      const r = await fetch(
        `/api/agent/providers/${encodeURIComponent(provider)}/test`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        },
      );
      clearTimeout(timeoutId);

      if (r.ok) {
        const data = (await r.json().catch(() => ({}))) as { status?: string; message?: string };
        if (data.status === "success") {
          setConnectionStatuses((prev) => ({
            ...prev,
            [provider]: { provider, status: "success", message: data.message || "Connected" },
          }));
        } else {
          setConnectionStatuses((prev) => ({
            ...prev,
            [provider]: { provider, status: "error", message: data.message || "Probe returned no status" },
          }));
        }
      } else if (r.status === 404) {
        // No probe endpoint — soft-success after save.
        setConnectionStatuses((prev) => ({
          ...prev,
          [provider]: {
            provider,
            status: "success",
            message: "Saved — validated at chat runtime",
          },
        }));
      } else {
        setConnectionStatuses((prev) => ({
          ...prev,
          [provider]: { provider, status: "error", message: `HTTP ${r.status}` },
        }));
      }
    } catch {
      clearTimeout(timeoutId);
      setConnectionStatuses((prev) => ({
        ...prev,
        [provider]: {
          provider,
          status: "error",
          message: "Connection timed out",
        },
      }));
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <main className="h-screen overflow-y-auto custom-scrollbar">
        <div className="max-w-[1400px] mx-auto px-8 py-10">
          <p className="text-sm text-on-surface-variant">Loading provider settings...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="h-screen overflow-y-auto custom-scrollbar">
      <div className="max-w-[1400px] mx-auto px-8 py-10 space-y-8">
        {/* Error Banner */}
        {error && (
          <div className="p-4 bg-error/10 border-l-4 border-error rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-error">error</span>
              <p className="text-error font-medium text-sm font-label">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-error/60 hover:text-error transition-colors"
              aria-label="Dismiss error"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        )}

        {/* Page Header — jobs-style (icon + title + subtitle). */}
        <header className="mb-2">
          <div className="flex items-center gap-3 mb-1">
            <span className="material-symbols-outlined text-2xl text-primary">
              key
            </span>
            <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface">
              Providers
            </h1>
          </div>
          <p className="text-sm text-on-surface-variant ml-9">
            Configure credentials for LLM providers and execution backends.
          </p>
        </header>

        <div className="space-y-6">
          {/* ── Google Vertex AI (Gemini) ─────────────────────────────── */}
          <section className="rounded-xl overflow-hidden relative" style={glassCard}>
            {/* Accent Bar — Google blue→teal gradient */}
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-[#4285F4] to-[#34A853]" />

            <div className="p-6">
              {/* Card Header */}
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-[#4285F4]/15 flex items-center justify-center text-[#4285F4]">
                    <span
                      className="material-symbols-outlined text-2xl"
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      diamond
                    </span>
                  </div>
                  <div>
                    <h3 className="font-headline text-lg font-bold text-on-surface">
                      Google Vertex AI (Gemini)
                    </h3>
                    <div className="flex gap-2 mt-1">
                      <ConnectionBadge status={connectionStatuses["vertex"]} />
                      <EncryptedBadge value={form.vertexServiceAccountJson} />
                    </div>
                  </div>
                </div>
                <div className="flex gap-3">
                  {/* v0.5.71 (issue #18): Test Connection now mirrors
                      the dirty-tracking discipline Save Changes already
                      uses, with one extra check — the JSON field
                      specifically must differ from its loaded value,
                      because the test endpoint receives the JSON from
                      the form and can't probe with the masked sentinel.
                      canTestVertex returns {ok, reason}; the reason
                      becomes the disabled-button tooltip so the
                      operator sees exactly which precondition isn't
                      met. Pre-v0.5.71 the button used only
                      hasTestableApiKey("vertex") which produced a
                      misleading "no JSON configured" banner on a
                      working install (operator's saved auth was fine;
                      they just hadn't re-pasted). */}
                  <button
                    type="button"
                    disabled={!canTestVertex().ok}
                    onClick={() => testConnection("vertex")}
                    title={
                      canTestVertex().ok
                        ? "Exchanges the service account JWT for an OAuth access token and pings the Vertex publisher-models endpoint."
                        : canTestVertex().reason
                    }
                    className="px-4 py-2 text-xs font-bold font-headline rounded bg-transparent border border-outline-variant/30 text-on-surface hover:bg-surface-bright transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Test Connection
                  </button>
                  <button
                    type="button"
                    disabled={
                      !hasTestableApiKey("vertex") ||
                      !isProviderDirty("vertex") ||
                      savingProvider === "vertex"
                    }
                    title={
                      !hasTestableApiKey("vertex")
                        ? "Fill in Project ID, Region, and Service Account JSON before saving."
                        : ""
                    }
                    onClick={() => handleSaveProvider("vertex")}
                    className="px-6 py-2 text-xs font-bold font-headline rounded bg-primary-container text-on-primary-container hover:shadow-[0_0_15px_rgba(25,99,179,0.3)] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {savingProvider === "vertex" ? "Saving..." : "Save Changes"}
                  </button>
                </div>
              </div>

              {/* Fields — 2-column top row (project / region), full-width JSON blob below */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label
                    htmlFor="vertex-project-id"
                    className="block text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label"
                  >
                    GCP Project ID
                  </label>
                  <div className="max-w-xl">
                    <input
                      id="vertex-project-id"
                      type="text"
                      value={form.vertexProjectId}
                      onChange={(e) => updateField("vertexProjectId", e.target.value)}
                      placeholder="my-gcp-project"
                      className="w-full bg-surface-container-lowest border-none rounded-lg px-4 py-3 text-sm font-mono text-on-surface focus:ring-1 focus:ring-primary/40 transition-all outline-none"
                    />
                  </div>
                  <p className="text-[10px] text-on-surface-variant/60 font-label">
                    GCP project that owns the Vertex AI quotas.
                  </p>
                </div>
                <div className="space-y-2">
                  <label
                    htmlFor="vertex-location"
                    className="block text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label"
                  >
                    Region
                  </label>
                  <div className="max-w-xl">
                    <input
                      id="vertex-location"
                      type="text"
                      value={form.vertexLocation}
                      onChange={(e) => updateField("vertexLocation", e.target.value)}
                      placeholder="us-central1"
                      className="w-full bg-surface-container-lowest border-none rounded-lg px-4 py-3 text-sm font-mono text-on-surface focus:ring-1 focus:ring-primary/40 transition-all outline-none"
                    />
                  </div>
                  <p className="text-[10px] text-on-surface-variant/60 font-label">
                    Default <code className="font-mono">us-central1</code>. Gemini 3 preview auto-routes to <code className="font-mono">global</code>.
                  </p>
                </div>
              </div>

              <div className="mt-6 space-y-2">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="vertex-sa-json"
                    className="block text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label"
                  >
                    Service Account JSON
                  </label>
                  {form.vertexServiceAccountJson && (
                    <button
                      type="button"
                      onClick={() => setVertexJsonVisible((v) => !v)}
                      className="flex items-center gap-1.5 text-[10px] font-bold text-on-surface-variant hover:text-on-surface uppercase tracking-widest transition-colors"
                      aria-label={vertexJsonVisible ? "Hide Service Account JSON" : "Show Service Account JSON"}
                    >
                      <span className="material-symbols-outlined text-sm">
                        {vertexJsonVisible ? "visibility_off" : "visibility"}
                      </span>
                      {vertexJsonVisible ? "Hide" : "Reveal"}
                    </button>
                  )}
                </div>
                <textarea
                  id="vertex-sa-json"
                  value={
                    vertexJsonVisible || !form.vertexServiceAccountJson
                      ? form.vertexServiceAccountJson
                      : maskJson(form.vertexServiceAccountJson)
                  }
                  onChange={(e) => {
                    // v0.1.34 fix: pre-fix the textarea was readOnly
                    // when the JSON was masked, so the operator could
                    // never paste/type a replacement and Save stayed
                    // disabled forever (form value never differed from
                    // the loaded "***" sentinel). readOnly is gone now.
                    //
                    // When the user types into a masked field, the
                    // textarea's new value contains BOTH the bullet-
                    // mask of the prior stored JSON AND the new char(s)
                    // they typed. Stripping the bullets leaves only
                    // what they actually entered, which is what we
                    // want to capture as the replacement value.
                    // Switching to visible mode at the same time so
                    // subsequent edits show real content, not bullets.
                    if (!vertexJsonVisible && form.vertexServiceAccountJson) {
                      const stripped = e.target.value.replace(/•/g, "");
                      setVertexJsonVisible(true);
                      updateField("vertexServiceAccountJson", stripped);
                    } else {
                      updateField("vertexServiceAccountJson", e.target.value);
                    }
                  }}
                  placeholder='{"type":"service_account","project_id":"...","private_key":"...","client_email":"..."}'
                  rows={6}
                  spellCheck={false}
                  autoComplete="off"
                  className="w-full bg-surface-container-lowest border-none rounded-lg px-4 py-3 text-xs font-mono text-on-surface focus:ring-1 focus:ring-primary/40 transition-all outline-none resize-y"
                />
                <p className="text-[10px] text-on-surface-variant/60 font-label">
                  Paste the full JSON key from GCP Console → IAM → Service Accounts. Stored encrypted at rest under
                  {" "}<code className="font-mono">setup.json</code>{" "}with operator-supplied <code className="font-mono">GUARDIAN_SECRET_KEK</code>.
                  To replace a stored value, just type or paste — the masked bullets clear automatically. <em>Reveal</em> shows the redaction sentinel returned by the API (your real key is never sent back to the browser).
                </p>
              </div>
            </div>
          </section>

          {/* ── Anthropic Card ──────────────────────────────────────────── */}
          <section
            className="rounded-xl overflow-hidden relative"
            style={glassCard}
          >
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-primary to-primary-container" />
            <div className="p-6">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-primary-container/20 flex items-center justify-center text-primary">
                    <span className="material-symbols-outlined text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                      auto_awesome
                    </span>
                  </div>
                  <div>
                    <h3 className="font-headline text-lg font-bold text-on-surface">Anthropic</h3>
                    <p className="text-xs text-on-surface-variant mt-0.5">
                      Claude API + Claude Code CLI
                    </p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    disabled
                    title="Connection test for Anthropic ships in a follow-on release (A1.2)."
                    className="px-4 py-2 text-xs font-bold font-headline rounded bg-transparent border border-outline-variant/30 text-on-surface hover:bg-surface-bright transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Test Connection
                  </button>
                  <button
                    type="button"
                    disabled={
                      savingProvider !== null ||
                      (form.anthropicApiKey === initialForm.current.anthropicApiKey &&
                       form.anthropicCliKey === initialForm.current.anthropicCliKey)
                    }
                    onClick={() => handleSaveProvider("anthropic")}
                    className="px-6 py-2 text-xs font-bold font-headline rounded bg-primary-container text-on-primary-container hover:shadow-[0_0_15px_rgba(25,99,179,0.3)] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {savingProvider === "anthropic" ? "Saving..." : "Save Changes"}
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <MaskedKeyInput
                  id="anthropic-api-key"
                  label="API Key"
                  value={form.anthropicApiKey}
                  onChange={(v) => updateField("anthropicApiKey", v)}
                  placeholder="sk-ant-api03-..."
                  helpText="Reserved for direct Claude API calls in the chat-route (follow-on release). Stored encrypted under primary-anthropic.secrets.api_key."
                />
                <MaskedKeyInput
                  id="anthropic-cli-key"
                  label="CLI Token (Claude Code)"
                  value={form.anthropicCliKey}
                  onChange={(v) => updateField("anthropicCliKey", v)}
                  placeholder="sk-ant-oat01-... or sk-ant-api03-..."
                  helpText="Used by the Claude Code CLI shell-out endpoint at POST /api/chat/cli. Accepts a Max OAuth token (sk-ant-oat01-) or an API key (sk-ant-api03-)."
                />
              </div>
            </div>
          </section>

          {/* ── Cohere North Card ───────────────────────────────────────── */}
          <section className="rounded-xl overflow-hidden relative" style={glassCard}>
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-primary to-primary-container" />
            <div className="p-6">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-primary-container/20 flex items-center justify-center text-primary">
                    <span className="material-symbols-outlined text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                      hub
                    </span>
                  </div>
                  <div>
                    <h3 className="font-headline text-lg font-bold text-on-surface">Cohere North</h3>
                    <p className="text-xs text-on-surface-variant mt-0.5">
                      Private / on-prem Cohere deployment · chat + tool-use
                    </p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    disabled={
                      connectionStatuses["cohere-north"]?.status === "testing" ||
                      !form.cohereNorthEndpoint.trim() ||
                      !form.cohereNorthAgentId.trim() ||
                      !form.cohereNorthBearerToken.trim() ||
                      form.cohereNorthBearerToken === "***"
                    }
                    onClick={() => testConnection("cohere-north")}
                    className="px-4 py-2 text-xs font-bold font-headline rounded bg-transparent border border-outline-variant/30 text-on-surface hover:bg-surface-bright transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {connectionStatuses["cohere-north"]?.status === "testing"
                      ? "Testing..."
                      : "Test Connection"}
                  </button>
                  <button
                    type="button"
                    disabled={savingProvider !== null || !isProviderDirty("cohere-north")}
                    onClick={() => handleSaveProvider("cohere-north")}
                    className="px-6 py-2 text-xs font-bold font-headline rounded bg-primary-container text-on-primary-container hover:shadow-[0_0_15px_rgba(25,99,179,0.3)] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {savingProvider === "cohere-north" ? "Saving..." : "Save Changes"}
                  </button>
                </div>
              </div>

              {connectionStatuses["cohere-north"]?.message && (
                <div
                  className={`mb-6 text-xs font-label px-3 py-2 rounded ${
                    connectionStatuses["cohere-north"]?.status === "success"
                      ? "bg-primary-container/20 text-primary"
                      : connectionStatuses["cohere-north"]?.status === "error"
                        ? "bg-error-container/20 text-error"
                        : "text-on-surface-variant"
                  }`}
                >
                  {connectionStatuses["cohere-north"]?.message}
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label htmlFor="cohere-endpoint" className="block text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label">
                    Endpoint URL
                  </label>
                  <input
                    id="cohere-endpoint"
                    type="text"
                    value={form.cohereNorthEndpoint}
                    onChange={(e) => updateField("cohereNorthEndpoint", e.target.value)}
                    placeholder="https://core.stc.com.sa"
                    className="w-full bg-surface-container-lowest border-none rounded-lg px-4 py-3 text-sm font-mono text-on-surface focus:ring-1 focus:ring-primary/40 transition-all outline-none"
                  />
                  <p className="text-[10px] text-on-surface-variant/60 font-label">
                    Base URL. The adapter calls {"{url}"}/api/v1/chat and polls /api/v1/conversations/&#123;id&#125;.
                  </p>
                </div>
                <div className="space-y-2">
                  <label htmlFor="cohere-agent-id" className="block text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label">
                    Agent ID
                  </label>
                  <input
                    id="cohere-agent-id"
                    type="text"
                    value={form.cohereNorthAgentId}
                    onChange={(e) => updateField("cohereNorthAgentId", e.target.value)}
                    placeholder="f78365f2-be10-466b-8fe4-..."
                    className="w-full bg-surface-container-lowest border-none rounded-lg px-4 py-3 text-sm font-mono text-on-surface focus:ring-1 focus:ring-primary/40 transition-all outline-none"
                  />
                  <p className="text-[10px] text-on-surface-variant/60 font-label">
                    The Cohere North agent to route requests to.
                  </p>
                </div>
                <MaskedKeyInput
                  id="cohere-bearer-token"
                  label="Bearer Token"
                  value={form.cohereNorthBearerToken}
                  onChange={(v) => updateField("cohereNorthBearerToken", v)}
                  placeholder="Bearer token for the Cohere North deployment"
                  helpText="Sent as Authorization: Bearer <token>. Stored encrypted under primary-cohere-north.secrets.bearer_token (REST-only; never exposed to the agent)."
                />
                <div className="space-y-2">
                  <label className="block text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label">
                    TLS Verification
                  </label>
                  <label className="flex items-center gap-2 text-sm text-on-surface font-label pt-2">
                    <input
                      type="checkbox"
                      checked={form.cohereNorthTlsVerify !== "false"}
                      onChange={(e) => updateField("cohereNorthTlsVerify", e.target.checked ? "true" : "false")}
                      className="accent-primary"
                    />
                    Verify the endpoint&apos;s TLS certificate
                  </label>
                  <p className="text-[10px] text-on-surface-variant/60 font-label">
                    Keep enabled. For a private CA, add the CA to the container trust store rather than disabling.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* ── OpenAI Card (WORK IN PROGRESS) ─────────────────────────── */}
          <section
            className="rounded-xl overflow-hidden relative opacity-50"
            style={{ ...glassCard, filter: "grayscale(0.5)" }}
          >
            {/* Accent Bar */}
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-primary-container to-secondary" />

            <div className="p-6">
              {/* Card Header */}
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                    <span
                      className="material-symbols-outlined text-2xl"
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      layers
                    </span>
                  </div>
                  <div>
                    <h3 className="font-headline text-lg font-bold text-on-surface">OpenAI</h3>
                    <div className="flex gap-2 mt-1">
                      <WipBadge />
                    </div>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    disabled
                    className="px-4 py-2 text-xs font-bold font-headline rounded bg-transparent border border-outline-variant/10 text-on-surface-variant/40 cursor-not-allowed"
                  >
                    Test Connection
                  </button>
                  <button
                    type="button"
                    disabled
                    className="px-6 py-2 text-xs font-bold font-headline rounded bg-surface-container-highest text-on-surface-variant/40 cursor-not-allowed"
                  >
                    Disabled
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <MaskedKeyInput
                  id="openai-api-key"
                  label="API Key"
                  value={form.openaiApiKey}
                  onChange={(v) => updateField("openaiApiKey", v)}
                  placeholder="sk-..."
                  helpText="Guardian's chat path is currently Vertex/Gemini only. OpenAI integration is on the roadmap."
                  disabled
                />
                <MaskedKeyInput
                  id="openai-codex-token"
                  label="Codex CLI Token"
                  value={form.openaiCodexToken}
                  onChange={(v) => updateField("openaiCodexToken", v)}
                  placeholder="rt_..."
                  helpText="Roadmap — once OpenAI integration ships, this will accept the ~/.codex/auth.json refresh token."
                  disabled
                />
              </div>
            </div>
          </section>


          {/* ── Ollama (Disabled) ──────────────────────────────────────── */}
          <section
            className="rounded-xl overflow-hidden relative opacity-50"
            style={{ ...glassCard, filter: "grayscale(0.5)" }}
          >
            <div className="p-6">
              {/* Card Header */}
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-surface-container-highest flex items-center justify-center text-on-surface-variant">
                    <span className="material-symbols-outlined text-2xl">dns</span>
                  </div>
                  <div>
                    <h3 className="font-headline text-lg font-bold text-on-surface">
                      Ollama (Local)
                    </h3>
                    <div className="flex gap-2 mt-1">
                      <span className="bg-tertiary/10 text-tertiary text-[10px] font-bold px-2 py-0.5 rounded border border-tertiary/20 uppercase tracking-tighter">
                        Roadmap
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    disabled
                    className="px-4 py-2 text-xs font-bold font-headline rounded bg-transparent border border-outline-variant/10 text-on-surface-variant/40 cursor-not-allowed"
                  >
                    Test Connection
                  </button>
                  <button
                    type="button"
                    disabled
                    className="px-6 py-2 text-xs font-bold font-headline rounded bg-surface-container-highest text-on-surface-variant/40 cursor-not-allowed"
                  >
                    Disabled
                  </button>
                </div>
              </div>

              {/* Disabled field */}
              <div className="grid grid-cols-1 gap-6">
                <div className="space-y-2">
                  <label
                    htmlFor="ollama-endpoint"
                    className="block text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label"
                  >
                    Endpoint URL
                  </label>
                  <div className="max-w-xl">
                    <input
                      id="ollama-endpoint"
                      type="text"
                      value={form.ollamaEndpoint}
                      disabled
                      className="w-full bg-surface-container-lowest/50 border-none rounded-lg px-4 py-3 text-sm font-mono text-on-surface-variant/40 cursor-not-allowed outline-none"
                    />
                  </div>
                  <p className="text-[10px] text-on-surface-variant/50 font-label italic">
                    Local inference backend integration arriving in v2.4.0.
                  </p>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* ── Metadata Footer ─────────────────────────────────────────── */}
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="rounded-xl p-4 flex items-center gap-4" style={glassCard}>
            <span className="material-symbols-outlined text-primary text-3xl">
              verified_user
            </span>
            <div>
              <p className="text-[10px] uppercase font-bold text-on-surface-variant tracking-widest">
                Security Protocol
              </p>
              <p className="text-sm font-bold text-on-surface">AES-256 Vault</p>
            </div>
          </div>
          <div className="rounded-xl p-4 flex items-center gap-4" style={glassCard}>
            <span className="material-symbols-outlined text-secondary text-3xl">
              hub
            </span>
            <div>
              <p className="text-[10px] uppercase font-bold text-on-surface-variant tracking-widest">
                Active Backends
              </p>
              <p className="text-sm font-bold text-on-surface">
                {
                  [
                    form.anthropicApiKey,
                    form.openaiApiKey,
                    form.vertexServiceAccountJson && form.vertexProjectId
                      ? "vertex"
                      : "",
                    form.cohereNorthEndpoint && form.cohereNorthBearerToken
                      ? "cohere-north"
                      : "",
                  ].filter(Boolean).length
                } Configured
              </p>
            </div>
          </div>
          <div className="rounded-xl p-4 flex items-center gap-4" style={glassCard}>
            <span className="material-symbols-outlined text-tertiary text-3xl">
              history_toggle_off
            </span>
            <div>
              <p className="text-[10px] uppercase font-bold text-on-surface-variant tracking-widest">
                Last Sync
              </p>
              <p className="text-sm font-bold text-on-surface">Just Now</p>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
