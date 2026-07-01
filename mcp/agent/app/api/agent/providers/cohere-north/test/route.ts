/**
 * Cohere North connection test. Probes reachability + auth by POSTing a
 * minimal chat request to {endpoint}/api/v1/chat. Returns { status, message }
 * (always HTTP 200) so the /providers page's testConnection() can render the
 * result. A full poll-to-completion isn't needed for a connectivity test —
 * a non-401/403 response proves the endpoint is reachable and the bearer is
 * accepted.
 */
import { NextResponse } from "next/server";
import { randomUUID } from "node:crypto";
import { postAudit } from "@/lib/auth-store";
import { resolveCohereNorthCreds } from "@/lib/cohere-credentials";

export const dynamic = "force-dynamic";

const REDACTED = "***";

export async function POST(request: Request) {
  let body: {
    endpoint_url?: string;
    agent_id?: string;
    bearer_token?: string;
    tls_verify?: string;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ status: "error", message: "Invalid JSON body." });
  }

  const endpoint = (body.endpoint_url || "").trim().replace(/\/$/, "");
  const agentId = (body.agent_id || "").trim();
  let token = (body.bearer_token || "").trim();

  // Re-paste sentinel: pull the saved token from the ProviderStore.
  if (token === REDACTED || token === "") {
    const creds = await resolveCohereNorthCreds();
    token = creds.bearerToken || "";
  }

  if (!endpoint || !agentId || !token) {
    return NextResponse.json({
      status: "error",
      message: "Endpoint URL, agent id, and bearer token are all required to test.",
    });
  }

  const conversationId = randomUUID();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);

  try {
    const resp = await fetch(`${endpoint}/api/v1/chat`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        stream: true,
        messages: [{ role: "USER", message: "ping" }],
        agent: { id: agentId },
        conversation: { id: conversationId },
      }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    await resp.body?.cancel().catch(() => {});

    if (resp.status === 401 || resp.status === 403) {
      postAudit("provider_probed", {
        target: "provider:cohere-north",
        status: "failure",
        metadata: { provider: "cohere-north", endpoint, http_status: resp.status },
      });
      return NextResponse.json({
        status: "error",
        message: `Authentication rejected (HTTP ${resp.status}). Check the bearer token.`,
      });
    }
    if (resp.ok || resp.status === 202) {
      postAudit("provider_probed", {
        target: "provider:cohere-north",
        status: "success",
        metadata: { provider: "cohere-north", endpoint, http_status: resp.status },
      });
      return NextResponse.json({
        status: "success",
        message: "Endpoint reachable and bearer accepted.",
      });
    }
    postAudit("provider_probed", {
      target: "provider:cohere-north",
      status: "failure",
      metadata: { provider: "cohere-north", endpoint, http_status: resp.status },
    });
    return NextResponse.json({
      status: "error",
      message: `Endpoint returned HTTP ${resp.status}.`,
    });
  } catch (err) {
    clearTimeout(timeoutId);
    const msg = err instanceof Error ? err.message : "connection failed";
    const tls = /certificate|self.signed|CERT_|UNABLE_TO_VERIFY/i.test(msg)
      ? " (TLS trust error — add the endpoint's CA to the container trust store)"
      : "";
    postAudit("provider_probed", {
      target: "provider:cohere-north",
      status: "failure",
      metadata: { provider: "cohere-north", endpoint, error: msg.slice(0, 200) },
    });
    return NextResponse.json({
      status: "error",
      message: `Could not reach the endpoint${tls}.`,
    });
  }
}
