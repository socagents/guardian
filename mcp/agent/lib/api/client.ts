import type { ApiError } from "./types";

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  token?: string;
  /**
   * Whether a network error / 5xx may be auto-retried. Defaults to TRUE for
   * idempotent methods (GET/HEAD/OPTIONS) and FALSE for every mutating method
   * (POST/PATCH/PUT/DELETE). A non-idempotent request must never be replayed:
   * a retry after a *partial* success — e.g. a create whose row was written
   * but whose response was lost to a proxy timeout — re-sends the mutation,
   * and the backend rejects the duplicate (409 "already exists"), surfacing a
   * phantom failure for an action that actually succeeded. Pass `retry: true`
   * to opt a genuinely-idempotent POST back into retries.
   */
  retry?: boolean;
}

export interface ApiSuccess<T> {
  ok: true;
  data: T;
}

export interface ApiFailure {
  ok: false;
  error: ApiError;
}

export type ApiResult<T> = ApiSuccess<T> | ApiFailure;

/**
 * Resolve the URL for an agent-runtime API call.
 *
 * Guardian-agent topology differs from the Spark workspace's: there is
 * no api-gateway, no nginx hop. The Next.js app proxies every backend
 * call through its own `/api/agent/*` route handlers
 * (see lib/mcp-proxy.ts), which forward to the embedded MCP at
 * `MCP_URL` with bearer auth attached server-side.
 *
 * Translation: `/api/v1/<path>` (Spark gateway-shape) → `/api/agent/<path>`
 * (guardian proxy-shape). Same payloads on the wire; only the prefix
 * differs.
 *
 * For client-side calls, relative paths work — the browser resolves
 * against the current origin. For SSR (server components, route
 * handlers calling other route handlers), `fetch()` needs an absolute
 * URL or it errors with "Failed to parse URL". We use
 * `GUARDIAN_AGENT_INTERNAL_URL` if set (e.g. when the agent runs behind
 * a non-trivial network setup), otherwise fall back to
 * `http://localhost:3000` — that's the in-process Next.js server
 * itself, calling its own `/api/agent/*` handler. Yes, it's a
 * round-trip into the same process, but that's the cost of keeping
 * one auth path (the proxy injects MCP_TOKEN) and avoiding having
 * two ways to talk to the MCP.
 */
function resolveGatewayUrl(path: string): string {
  let resolved = path;
  if (path.startsWith("/api/v1/")) {
    resolved = `/api/agent/${path.slice("/api/v1/".length)}`;
  }
  // Server-side: fetch() requires absolute URLs. Browser-side: relative paths
  // are fine and preferred (no env coupling, work behind any reverse proxy).
  if (typeof window === "undefined") {
    const internalBase = (
      process.env.GUARDIAN_AGENT_INTERNAL_URL ||
      "http://localhost:3000"
    ).replace(/\/+$/, "");
    return `${internalBase}${resolved}`;
  }
  return resolved;
}

/**
 * Parse the gateway error envelope from a non-OK response.
 * Falls back to a generic error if the body is not parseable.
 */
async function parseError(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null) {
      const envelope = body as Record<string, unknown>;
      // Spark-gateway shape: { code, message, retryable }.
      if ("code" in envelope && "message" in envelope) {
        return {
          code: String(envelope.code),
          message: String(envelope.message),
          retryable: Boolean(envelope.retryable),
        };
      }
      // Guardian-agent route shape: { error: "...", ... }.
      // Fallback so handlers like /api/agent/marketplace/.../uninstall
      // (which return 409 + {error: "..., delete N instances first"})
      // surface their helpful message to the UI instead of getting
      // collapsed to a generic "Conflict".
      if ("error" in envelope && typeof envelope.error === "string") {
        return {
          code: `HTTP_${response.status}`,
          message: envelope.error,
          retryable: response.status >= 500,
        };
      }
    }
  } catch {
    // Body was not JSON — fall through to generic error.
  }

  return {
    code: `HTTP_${response.status}`,
    message: response.statusText || "Request failed",
    retryable: response.status >= 500,
  };
}

/**
 * Typed fetch wrapper for communicating with the api-gateway.
 *
 * - Reads `NEXT_PUBLIC_GATEWAY_URL` (default same-origin relative paths)
 * - Attaches auth token from `options.token` or cookie-forwarded header
 * - JSON request/response serialization
 * - Parses gateway error envelope (`code`, `message`, `retryable`)
 * - Retries retryable errors up to 3 times with exponential backoff (1s, 2s, 4s)
 * - Supports AbortSignal for cancellation
 */
export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<ApiResult<T>> {
  const { body, token, headers: extraHeaders, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...(extraHeaders as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const url = resolveGatewayUrl(path);

  const init: RequestInit = {
    ...fetchOptions,
    headers,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  };

  // Only idempotent methods are safe to auto-retry. A POST/PATCH/PUT/DELETE
  // that times out or 5xxes may have already applied server-side, so replaying
  // it risks a duplicate (e.g. a connector instance created twice → the second
  // attempt 409s "already exists" on a create that actually succeeded). The
  // caller can force retries on a known-idempotent mutation via `retry: true`.
  const method = (init.method ?? "GET").toUpperCase();
  const idempotentMethod =
    method === "GET" || method === "HEAD" || method === "OPTIONS";
  const allowRetry = options.retry ?? idempotentMethod;

  let lastError: ApiError | undefined;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (attempt > 0) {
      const delay = BASE_DELAY_MS * Math.pow(2, attempt - 1);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }

    // If the request was aborted before this attempt, stop immediately.
    if (options.signal?.aborted) {
      return {
        ok: false,
        error: {
          code: "ABORTED",
          message: "Request was aborted",
          retryable: false,
        },
      };
    }

    try {
      const response = await fetch(url, init);

      if (response.ok) {
        // 204 No Content has no body — return undefined data without parsing.
        if (response.status === 204) {
          return { ok: true, data: undefined as T };
        }
        const data = (await response.json()) as T;
        return { ok: true, data };
      }

      lastError = await parseError(response);

      // Only retry if the error is retryable, the method is replay-safe, and
      // we have attempts left.
      if (!lastError.retryable || !allowRetry || attempt === MAX_RETRIES) {
        return { ok: false, error: lastError };
      }
    } catch (error: unknown) {
      // Network errors / AbortError
      if (error instanceof DOMException && error.name === "AbortError") {
        return {
          ok: false,
          error: {
            code: "ABORTED",
            message: "Request was aborted",
            retryable: false,
          },
        };
      }

      lastError = {
        code: "NETWORK_ERROR",
        message: error instanceof Error ? error.message : "Network error",
        retryable: true,
      };

      if (!allowRetry || attempt === MAX_RETRIES) {
        return { ok: false, error: lastError };
      }
    }
  }

  // Unreachable in practice, but satisfies TypeScript.
  return {
    ok: false,
    error: lastError ?? {
      code: "UNKNOWN",
      message: "Unknown error",
      retryable: false,
    },
  };
}

/** Response envelope used by gateway list endpoints. */
interface ListEnvelope<T> {
  data: T[];
  meta?: { total_count?: number };
}

/**
 * Typed fetch wrapper for list endpoints. Normalizes the three envelope
 * shapes we see on the wire:
 *
 *   1. Bare array:        `[ {...}, {...} ]`
 *   2. Generic envelope:  `{ "data": [...], "meta": {...} }` (legacy gateway)
 *   3. Named envelope:    `{ "jobs": [...], "count": N }`,
 *                         `{ "approvals": [...], "count": N }`,
 *                         `{ "events": [...], "count": N }`, …
 *
 * The guardian MCP uses (3) almost everywhere — each endpoint names its
 * payload after the resource (`jobs`, `approvals`, `events`, `keys`,
 * `instances`, etc.). Earlier this helper only recognized (1) and (2),
 * which silently turned every named-envelope response into an empty
 * array — that's why the Jobs and Approvals pages rendered "no
 * results" while the chat-route's tool calls saw the same data fine.
 *
 * We recover the array by looking for the first top-level field whose
 * value is an array. There's only one in every shape we ship, so this
 * is unambiguous. Unknown shapes still fall through to `[]` rather
 * than crashing the page.
 */
export async function listRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<ApiResult<T[]>> {
  const result = await apiRequest<ListEnvelope<T> | T[] | Record<string, unknown>>(
    path,
    options,
  );

  if (!result.ok) {
    // Treat 404 as "endpoint not implemented yet" → return empty list
    // rather than showing an error. This lets catalog pages (tools,
    // skills, models) render a clean empty state before the backend
    // endpoints are built.
    if (result.error.code === "HTTP_404") {
      return { ok: true, data: [] };
    }
    return result;
  }

  // Shape 1: bare array.
  if (Array.isArray(result.data)) {
    return { ok: true, data: result.data };
  }

  if (typeof result.data === "object" && result.data !== null) {
    const obj = result.data as Record<string, unknown>;

    // Shape 2: explicit `data` envelope wins when present.
    if (Array.isArray(obj.data)) {
      return { ok: true, data: obj.data as T[] };
    }

    // Shape 3: named envelope. Take the first array-valued field.
    // Every MCP list endpoint ships exactly one such field
    // (`jobs`, `approvals`, `events`, `keys`, `instances`, …)
    // alongside scalars like `count`, so this is unambiguous.
    for (const key of Object.keys(obj)) {
      if (Array.isArray(obj[key])) {
        return { ok: true, data: obj[key] as T[] };
      }
    }
  }

  // Unexpected shape — return empty array rather than crashing.
  return { ok: true, data: [] };
}
