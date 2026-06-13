"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";

import { resolveGatewayUrl } from "@/lib/gateway-url.server";
import { SESSION_COOKIE_NAME } from "@/lib/auth-defaults";

/**
 * Server action invoked by the "Verify pipeline" form on the Pipeline
 * Health page. POSTs to the api-gateway's verify endpoint, which runs
 * the canonical 3-component LGTM probe (Prometheus + Loki + Tempo),
 * updates the spark_verification_* metrics, and emits a structured
 * log line that the Loki-backed history feed reads on the next
 * render.
 *
 * Wrapped as a server action (not a route handler) so the form can
 * submit straight from the page without needing a `"use client"`
 * boundary or a separate `/api/observability/verify` Next.js route.
 *
 * After the POST completes, we call `revalidatePath` so the page
 * re-renders and the new run shows up at the top of the history feed
 * within the same submit cycle.
 */
export async function verifyPipelineAction(): Promise<void> {
  const gateway = resolveGatewayUrl();
  const cookieStore = await cookies();
  // Forward the operator's session as a Cookie header (middleware validates
  // the guardian_session cookie, not a Bearer of its value). Was reading the
  // stale "spark-token" cookie → always undefined → unauthenticated verify.
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  const url = `${gateway}/api/v1/observability/verify?trigger=manual`;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { cookie: `${SESSION_COOKIE_NAME}=${token}` } : {}),
      },
      cache: "no-store",
    });

    if (!response.ok) {
      // Log to the Next.js server console — operators can correlate
      // via promtail. We don't surface the error to the user UI here
      // because the page re-render will reflect the failure naturally
      // (the new run will appear with result=fail in the feed).
      console.error(
        `verifyPipelineAction: gateway returned ${response.status}`,
      );
    }
  } catch (err: unknown) {
    console.error(
      `verifyPipelineAction: fetch failed: ${err instanceof Error ? err.message : "unknown"}`,
    );
  }

  // Force the Pipeline Health page to re-render with the latest data.
  revalidatePath("/observability/pipeline");
}
