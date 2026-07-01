/**
 * Cohere North credentials resolver — reads the endpoint + agent id (config)
 * and bearer token (secret) from the MCP ProviderStore on demand, falls back
 * to env vars. Mirrors lib/anthropic-credentials.ts (same cache + bust pattern).
 *
 * # Resolution
 *   1. ProviderStore "cohere-north" instance → config.endpoint_url / config.agent_id
 *      / config.tls_verify / config.ca_pem, secrets.bearer_token
 *      (set via the /providers UI → ProviderStore PUT path)
 *   2. Env fallback: COHERE_NORTH_ENDPOINT / COHERE_NORTH_AGENT_ID /
 *      COHERE_NORTH_BEARER_TOKEN (.env-supplied first-install path)
 *
 * The bearer token is a SecretStore value — REST-only per the credential
 * guardrail; it is NEVER exposed to the agent as a tool.
 *
 * # Circular-import guard
 * Reads MCP_TOKEN/MCP_URL directly from process.env (getEffectiveRuntimeConfig
 * calls this module to populate the Cohere fields, so we must not call it back).
 */

export interface CohereNorthCreds {
  endpoint: string | null;
  agentId: string | null;
  bearerToken: string | null;
  tlsVerify: boolean;
  caPem: string | null;
}

interface CacheEntry {
  creds: CohereNorthCreds;
  expiresAt: number;
}

const CACHE_TTL_MS = 30_000;
const COHERE_NORTH_PROVIDER_ID = "cohere-north";

let cache: CacheEntry | null = null;

const EMPTY: CohereNorthCreds = {
  endpoint: null,
  agentId: null,
  bearerToken: null,
  tlsVerify: true,
  caPem: null,
};

function deriveBaseUrl(mcpUrl: string): string | null {
  try {
    const u = new URL(mcpUrl);
    return `${u.protocol}//${u.host}`;
  } catch {
    return null;
  }
}

function resolveMcpDirect(): { base: string; token: string } | null {
  const token = (process.env.MCP_TOKEN || "").trim();
  if (!token) return null;
  const url = (
    process.env.MCP_URL || "http://localhost:8080/api/v1/stream/mcp"
  ).trim();
  const base = deriveBaseUrl(url);
  if (!base) return null;
  return { base, token };
}

interface McpProviderInstance {
  id: string;
  provider_id: string;
  name: string;
  config: Record<string, unknown>;
  secrets: Record<string, unknown>;
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

async function fetchFromStore(base: string, token: string): Promise<CohereNorthCreds> {
  try {
    const listResp = await fetch(
      `${base}/api/v1/providers?provider_id=${COHERE_NORTH_PROVIDER_ID}`,
      { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(8000) },
    );
    if (!listResp.ok) return { ...EMPTY };
    const listData = (await listResp.json().catch(() => ({}))) as {
      instances?: McpProviderInstance[];
    };
    const instance = listData.instances?.[0];
    if (!instance) return { ...EMPTY };

    const detailResp = await fetch(
      `${base}/api/v1/providers/${encodeURIComponent(instance.id)}?include_secrets=true`,
      { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(8000) },
    );
    if (!detailResp.ok) return { ...EMPTY };
    const detailData = (await detailResp.json().catch(() => ({}))) as {
      instance?: McpProviderInstance;
    };
    const fetched = detailData.instance;
    if (!fetched) return { ...EMPTY };

    return {
      endpoint: str(fetched.config?.endpoint_url),
      agentId: str(fetched.config?.agent_id),
      bearerToken: str(fetched.secrets?.bearer_token),
      tlsVerify: fetched.config?.tls_verify === false ? false : true,
      caPem: str(fetched.config?.ca_pem),
    };
  } catch {
    return { ...EMPTY };
  }
}

async function refreshCache(): Promise<CacheEntry> {
  let store: CohereNorthCreds = { ...EMPTY };
  const r = resolveMcpDirect();
  if (r) store = await fetchFromStore(r.base, r.token);

  const creds: CohereNorthCreds = {
    endpoint: store.endpoint || (process.env.COHERE_NORTH_ENDPOINT || "").trim() || null,
    agentId: store.agentId || (process.env.COHERE_NORTH_AGENT_ID || "").trim() || null,
    bearerToken:
      store.bearerToken || (process.env.COHERE_NORTH_BEARER_TOKEN || "").trim() || null,
    tlsVerify: store.tlsVerify,
    caPem: store.caPem,
  };
  const entry: CacheEntry = { creds, expiresAt: Date.now() + CACHE_TTL_MS };
  cache = entry;
  return entry;
}

/** Resolve the Cohere North endpoint + agent id + bearer token. Returns EMPTY
 *  (all null) if nothing is configured. */
export async function resolveCohereNorthCreds(): Promise<CohereNorthCreds> {
  const now = Date.now();
  if (cache && cache.expiresAt > now) return cache.creds;
  const entry = await refreshCache();
  return entry.creds;
}

/** Drop the cached credentials — called from /providers PUT after a successful
 *  update so the operator's change is visible to the next chat dispatch. */
export function bustCohereCredsCache(): void {
  cache = null;
}
