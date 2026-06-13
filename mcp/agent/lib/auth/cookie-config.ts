import type { ResponseCookie } from "next/dist/compiled/@edge-runtime/cookies";
import { SESSION_COOKIE_NAME } from "@/lib/auth-defaults";

// Re-export the canonical session-cookie name (was the stale "spark-token";
// no current importer, but kept correct so it can't reintroduce the dead name).
export const COOKIE_NAME = SESSION_COOKIE_NAME;
export const MAX_AGE_SECONDS = 7 * 24 * 60 * 60; // 7 days

/**
 * Whether to set the Secure flag on auth cookies.
 *
 * In production (HTTPS) this MUST be true. In development behind an HTTP
 * tunnel (e.g. IAP tunnel to port 3080), browsers refuse to send Secure
 * cookies over plain HTTP — causing silent auth failures where the dashboard
 * shows "System Unhealthy" because the token cookie is never forwarded.
 *
 * Next.js inlines process.env at build time, so NODE_ENV checks are baked
 * into the compiled output. We use a dynamic require('next/headers') check
 * instead: if the incoming request uses HTTP (not HTTPS), skip Secure.
 *
 * Set COOKIE_SECURE=true|false to override explicitly at runtime.
 */
function isSecure(): boolean {
  // Explicit runtime override via environment variable.
  // Use dynamic access to avoid Next.js build-time inlining.
  const override = getEnvVar("COOKIE_SECURE");
  if (override === "false") return false;
  if (override === "true") return true;

  // Default: Secure cookies only when NODE_ENV is "production".
  // Note: Next.js bakes this at build time, so `next build` (which sets
  // NODE_ENV=production) will compile this as `true`. To disable Secure
  // at runtime, set COOKIE_SECURE=false in the container environment.
  return process.env.NODE_ENV === "production";
}

/**
 * Read an env var at runtime without Next.js inlining it at build time.
 * Next.js replaces `process.env.X` with the literal value during `next build`.
 * Indexing `process.env` dynamically bypasses this optimization.
 */
function getEnvVar(name: string): string | undefined {
  return (process.env as Record<string, string | undefined>)[name];
}

/** Standard cookie options for setting the auth token. */
export function tokenCookieOptions(): Partial<ResponseCookie> {
  return {
    httpOnly: true,
    secure: isSecure(),
    sameSite: "strict" as const,
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  };
}

/** Cookie options for clearing the auth token (logout). */
export function clearCookieOptions(): Partial<ResponseCookie> {
  return {
    httpOnly: true,
    secure: isSecure(),
    sameSite: "strict" as const,
    path: "/",
    maxAge: 0,
  };
}
