/**
 * Guardian v0.4.0 — runtime configuration resolution.
 *
 * Reads bundle-internal coordination from container env and operator-set
 * provider credentials from the MCP-side ProviderStore. Returns a single
 * flat `EffectiveRuntimeConfig` the chat handler + agent routes consume.
 *
 * # What changed in v0.4.0 (vs pre-v0.4.0)
 *
 *  - The setup page is gone. Pre-v0.4.0 `readRuntimeSetup()` read
 *    `/app/runtime/setup.json` for operator-typed values and layered
 *    them over env. v0.4.0 deletes setup.json and removes this layer
 *    entirely.
 *  - `UI_USER` / `UI_PASSWORD` are gone. Admin auth lives ONLY in
 *    SecretStore via `lib/auth-store.ts` + the baked
 *    `ADMIN_USERNAME` constant in `lib/auth-defaults.ts`. No env
 *    fallback, no setup.json fallback.
 *  - `isSetupRequired()` removed. AuthGate no longer branches on a
 *    "setup needed" state — defaults are seeded by entrypoint.sh on
 *    first boot, login works immediately.
 *  - `settings-resolve.ts` is gone. GEMINI_MODEL / defaultLogFormat
 *    fall back to env defaults; operator overrides via
 *    /settings/personality flow into settings_store and are read by
 *    the MCP side, not by this module.
 *  - All the setup-form prefill helpers (`publicSetupDefaults`,
 *    `SETUP_SECRET_KEYS`, `REDACTED_SENTINEL`, etc.) are gone —
 *    nothing consumes them post-setup-page-deletion.
 *
 * # Layering
 *
 *   env  →  ProviderStore (Vertex SA JSON)
 *
 * Provider lookups have a 30s cache in their own module
 * (lib/vertex-credentials.ts); a fresh getEffectiveRuntimeConfig()
 * does at most one round-trip per cache window, not per chat turn.
 */

/* ─── Types ─────────────────────────────────────────────────── */

export type RuntimeConfigValues = {
  MCP_URL?: string;
  MCP_TOKEN?: string;
  GOOGLE_APPLICATION_CREDENTIALS?: string;
  GEMINI_API_KEY?: string;
  GEMINI_MODEL?: string;
  SSL_CERT_PEM?: string;
  SSL_KEY_PEM?: string;
  GUARDIAN_TLS_VERIFY?: string;
  // Bundle-derived fields (connector configs) flow through here. Names
  // come from the bundle's connector.yaml configSchemas; we don't
  // enumerate them — consumers just read by key.
  [key: string]: string | undefined;
};

export type EffectiveRuntimeConfig = RuntimeConfigValues & {
  MCP_URL: string;
  MCP_TOOL_CACHE_TTL_MS: string;
  /** Operator-chosen default model (operator_state.db key `default_model`),
   *  populated per chat request by route.ts. Undefined = no default set →
   *  fall back to GEMINI_MODEL. */
  defaultModel?: string;
};

/* ─── Constants ────────────────────────────────────────────── */

const DEFAULT_MODEL = "gemini-3.1-pro-preview";

// #CHAT-F11 — the GEMINI_MODEL fallback to DEFAULT_MODEL was silent: an
// unset env var, or a DEFAULT_MODEL alias that Google later retires/renames,
// would degrade with no operator-visible signal. Warn ONCE per process when
// the fallback engages so the condition is surfaced in the agent logs instead
// of only manifesting as model-not-found errors at call time.
let _warnedModelFallback = false;
function noteModelFallback(): void {
  if (_warnedModelFallback) return;
  _warnedModelFallback = true;
  console.warn(
    `[runtime-config] GEMINI_MODEL is unset — falling back to the built-in ` +
      `default "${DEFAULT_MODEL}". Set GEMINI_MODEL (or an operator default ` +
      `model in /settings/personality) to pin the model explicitly; if this ` +
      `default alias is ever retired upstream, calls will fail with ` +
      `model-not-found until it is updated.`,
  );
}

/** Bundle-internal coordination keys. Container env wins; never
 *  operator-typed. The embedded MCP reads MCP_TOKEN from the same
 *  process env, so divergence between agent-side and MCP-side would
 *  break every admin /api/v1/* call. We pin both to env. */
const BUNDLE_INTERNAL_KEYS: ReadonlySet<string> = new Set(["MCP_URL", "MCP_TOKEN"]);

/* ─── Internal helpers ─────────────────────────────────────── */

function clean(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function envValue(key: string | number | symbol): string {
  if (typeof key !== "string") return "";
  return clean(process.env[key]);
}

/* ─── Public API ───────────────────────────────────────────── */

/**
 * Resolve the effective runtime config for one chat turn (or one
 * /api/agent/* proxy call). Reads env directly + lazily imports the
 * provider/instance resolvers so this module stays free of MCP
 * client wiring.
 */
export async function getEffectiveRuntimeConfig(): Promise<EffectiveRuntimeConfig> {
  const get = (key: keyof RuntimeConfigValues, fallback = ""): string => {
    if (typeof key === "string" && BUNDLE_INTERNAL_KEYS.has(key)) {
      // Env wins for bundle-internal keys.
      return envValue(key) || fallback;
    }
    return envValue(key) || fallback;
  };

  // v0.1.34 → v0.4.0 — provider credentials live in the MCP-side
  // ProviderStore. The chat handler reads `GOOGLE_APPLICATION_CREDENTIALS`
  // here at ~16 call sites; the resolution path was moved underneath
  // them without changing the read signature.
  const { resolveVertexCredentialsFromStore } = await import(
    "@/lib/vertex-credentials"
  );
  const vertexFromStore = await resolveVertexCredentialsFromStore();

  return {
    MCP_URL: get("MCP_URL", "http://localhost:8080/api/v1/stream/mcp"),
    MCP_TOKEN: get("MCP_TOKEN"),
    GOOGLE_APPLICATION_CREDENTIALS:
      vertexFromStore || get("GOOGLE_APPLICATION_CREDENTIALS"),
    GEMINI_API_KEY: get("GEMINI_API_KEY"),
    GEMINI_MODEL: (() => {
      const fromEnv = envValue("GEMINI_MODEL");
      if (!fromEnv) noteModelFallback();
      return fromEnv || DEFAULT_MODEL;
    })(),
    SSL_CERT_PEM: get("SSL_CERT_PEM"),
    SSL_KEY_PEM: get("SSL_KEY_PEM"),
    GUARDIAN_TLS_VERIFY: get("GUARDIAN_TLS_VERIFY"),
    MCP_TOOL_CACHE_TTL_MS: clean(process.env.MCP_TOOL_CACHE_TTL_MS) || "300000",
  };
}

/**
 * Derive the MCP's HTTP base URL from a full MCP_URL.
 * E.g. "http://guardian-mcp:8080/api/v1/stream/mcp" → "http://guardian-mcp:8080"
 *
 * Used by the /api/agent/* proxy routes that need to POST to admin
 * endpoints on the MCP at non-streamable paths.
 */
export function deriveMcpBaseUrl(mcpUrl: string): string {
  try {
    const u = new URL(mcpUrl);
    return `${u.protocol}//${u.host}`;
  } catch {
    return "";
  }
}
