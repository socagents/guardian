/**
 * GET /api/auth/status  (v0.4.0)
 *
 * Validates the session cookie against the MCP-side auth_store and
 * returns the result. AuthGate (client component) polls this on
 * mount + bfcache restore + tab-visibility change.
 *
 * # Response shape
 *
 *  {
 *    authenticated: bool,           // valid, non-expired, non-revoked
 *    credentialsChanged: bool,      // false on first boot before /profile change
 *    username: "admin" | null
 *  }
 *
 * `setupRequired` from pre-v0.4.0 is REMOVED. There is no setup page
 * in v0.4.0 — the entrypoint seeds defaults, the operator logs in
 * with them, the forced-change flow rotates them. AuthGate no longer
 * branches on setupRequired.
 *
 * # Cache headers
 *
 * Never cache. The browser MUST hit the server every time to learn
 * the current auth state. Without these headers an intermediary
 * could serve a stale `authenticated: true` after sign-out.
 */

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { SESSION_COOKIE_NAME } from "@/lib/auth-defaults";
import { validateSession } from "@/lib/auth-store";

export const dynamic = "force-dynamic";

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value ?? "";

  const validation = await validateSession(token);

  const response = NextResponse.json(
    validation.valid
      ? {
          authenticated: true,
          credentialsChanged: validation.credentialsChanged,
          username: validation.username,
        }
      : {
          authenticated: false,
          credentialsChanged: false,
          username: null,
        },
  );
  response.headers.set(
    "Cache-Control",
    "no-store, no-cache, must-revalidate, private",
  );
  response.headers.set("Pragma", "no-cache");
  return response;
}
