import type { ReadonlyRequestCookies } from "next/dist/server/web/spec-extension/adapters/request-cookies";
import { SESSION_COOKIE_NAME } from "@/lib/auth-defaults";

// The UI session cookie. (Was the stale Phantom-era "spark-token" until v0.2.6
// — never re-pointed during the v0.4.0 auth rename, which broke every
// server-component fetch that authenticates via getToken, e.g. the /jobs page.)
const COOKIE_NAME = SESSION_COOKIE_NAME;

export function getToken(
  cookies: ReadonlyRequestCookies | { get(name: string): { value: string } | undefined },
): string | undefined {
  return cookies.get(COOKIE_NAME)?.value;
}

/**
 * Headers that forward the operator's session for a SERVER-SIDE internal fetch
 * to `/api/agent/*`. The middleware validates the `guardian_session` COOKIE; it
 * does NOT accept the session token as a `Bearer` (that path only takes
 * `guardian_ak_*` API keys or the MCP_TOKEN). A server-side fetch does not
 * auto-forward the browser's cookies, so attach it explicitly. `{}` when no
 * session (caller decides how to degrade).
 */
export function getSessionFetchHeaders(
  cookies: ReadonlyRequestCookies | { get(name: string): { value: string } | undefined },
): Record<string, string> {
  const token = getToken(cookies);
  return token ? { cookie: `${COOKIE_NAME}=${token}` } : {};
}
