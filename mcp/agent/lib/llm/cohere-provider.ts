/**
 * CohereProvider (R2) — runs Guardian's tool-using loop on a private Cohere
 * North deployment. Registered into the R1 provider registry; the chat-route
 * dispatches here when the resolved model routes to `cohere-north`.
 *
 * Canonical interchange = the Gemini generateContent shape (R1). The pure
 * translation (Gemini-shape ↔ Cohere) lives in ./cohere-translate; this file
 * wires it to the HTTP transport:
 *   - request:  geminiToCohereBody()  → POST {endpoint}/api/v1/chat
 *   - response: poll GET {endpoint}/api/v1/conversations/{id}
 *               → cohereConversationToGemini()  → Gemini-shaped response
 *
 * Conversation scoping: a FRESH conversation id per invoke() + the full
 * translated history each call (Guardian's loop is stateless-per-call), for
 * maximal isolation. (Lab-validation item: confirm real North processes the
 * full messages[] on a new conversation vs. only the last message.)
 *
 * The bearer token comes from runtimeConfig (populated by cohere-credentials.ts
 * from the SecretStore) — never from an agent tool.
 */

import { randomUUID } from "node:crypto";
import {
  registerProvider,
  COHERE_NORTH_PROVIDER_ID,
  type LLMProvider,
  type LLMInvokeContext,
} from "@/lib/llm/provider";
import {
  geminiToCohereBody,
  cohereConversationToGemini,
  lastRoleIsAssistant,
  type GeminiPayload,
} from "@/lib/llm/cohere-translate";

// Plain fetch — verifies TLS against the system trust store (spec: verify ON,
// never ship verify=False). A private/self-signed North endpoint needs its CA
// in the container trust store; wiring `ca_pem` / `tls_verify` into a custom
// dispatcher is a documented follow-up (the config fields are already stored).
async function cohereFetch(url: string, token: string, init: RequestInit): Promise<Response> {
  return fetch(url, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init.headers ?? {}),
    },
  });
}

async function invokeCohere(payload: unknown, ctx: LLMInvokeContext): Promise<unknown> {
  const rc = ctx.runtimeConfig;
  const base = (rc.COHERE_NORTH_ENDPOINT || "").trim().replace(/\/$/, "");
  const token = (rc.COHERE_NORTH_BEARER_TOKEN || "").trim();
  const agentId = (rc.COHERE_NORTH_AGENT_ID || "").trim();
  if (!base || !token || !agentId) {
    throw new Error(
      "Cohere North is not fully configured (endpoint + agent id + bearer token required). Configure it at /providers.",
    );
  }

  const conversationId = randomUUID();
  const body = geminiToCohereBody(payload as GeminiPayload, agentId, conversationId);

  // 1. POST the turn. Ignore the streamed body (as the STC client does).
  const post = await cohereFetch(`${base}/api/v1/chat`, token, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!post.ok && post.status !== 202) {
    const t = await post.text().catch(() => "");
    throw new Error(`Cohere North /api/v1/chat returned ${post.status}: ${t.slice(0, 300)}`);
  }
  await post.body?.cancel().catch(() => {}); // drop the stream; we poll instead.

  // 2. Poll the conversation for the assembled assistant reply.
  const convUrl = `${base}/api/v1/conversations/${encodeURIComponent(conversationId)}`;
  const deadline = Date.now() + 200_000;
  let attempt = 0;
  let convo: unknown = null;
  while (Date.now() < deadline) {
    attempt++;
    try {
      const g = await cohereFetch(convUrl, token, { method: "GET" });
      if (g.ok) {
        convo = await g.json().catch(() => null);
        if (convo && lastRoleIsAssistant(convo)) break;
      }
    } catch {
      // transient — keep polling until the deadline.
    }
    await new Promise((r) => setTimeout(r, Math.min(2000, 500 + attempt * 100)));
  }
  if (!convo) {
    throw new Error(`Cohere North conversation ${conversationId} did not return a reply before the deadline.`);
  }
  return cohereConversationToGemini(convo);
}

const cohereProvider: LLMProvider = {
  id: COHERE_NORTH_PROVIDER_ID,
  invoke: invokeCohere,
};
registerProvider(cohereProvider);

export default cohereProvider;
