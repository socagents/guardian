/**
 * Cohere North translation core (R2) — PURE functions, no imports, no side
 * effects. Split out from cohere-provider.ts so a plain `node` golden script
 * can import + test them (the adapter file has value imports + a registration
 * side effect that node's alias resolver can't run).
 *
 * Canonical interchange = the Gemini generateContent shape (R1). These translate
 * that shape ↔ Cohere's chat request / conversation-object model.
 */

// ---- Gemini-side shapes (structural; GeminiCallPayload is file-local to route.ts) ----
export type GeminiPart = {
  text?: string;
  thought?: boolean;
  functionCall?: { name: string; args?: Record<string, unknown> };
  functionResponse?: { name: string; response: Record<string, unknown> };
};
export type GeminiContent = { role: "user" | "model"; parts: GeminiPart[] };
export type GeminiPayload = {
  contents?: GeminiContent[];
  tools?: Array<{ functionDeclarations?: Array<{ name: string; description?: string; parameters?: unknown }> }>;
  systemInstruction?: { role: "system"; parts: Array<{ text: string }> };
};

// ---- Cohere-side shapes ----
type CohereTool = {
  name: string;
  description: string;
  parameter_definitions: Record<string, { description: string; type: string; required: boolean }>;
};
type CohereMessage =
  | { role: "USER" | "SYSTEM"; message: string }
  | { role: "CHATBOT"; message?: string; tool_calls?: Array<{ name: string; parameters: Record<string, unknown> }> }
  | { role: "TOOL"; tool_results: Array<{ call: { name: string; parameters: Record<string, unknown> }; outputs: Array<Record<string, unknown>> }> };

// === REQUEST TRANSLATION: Gemini payload -> Cohere chat body ===============
export function geminiToCohereBody(
  payload: GeminiPayload,
  agentId: string,
  conversationId: string,
): Record<string, unknown> {
  const system = (payload.systemInstruction?.parts ?? []).map((p) => p.text).join("\n").trim();
  const messages: CohereMessage[] = [];

  for (const c of payload.contents ?? []) {
    const fnResponses = c.parts.filter((p) => p.functionResponse);
    if (fnResponses.length > 0) {
      messages.push({
        role: "TOOL",
        tool_results: fnResponses.map((p) => ({
          call: { name: p.functionResponse!.name, parameters: {} },
          outputs: [p.functionResponse!.response],
        })),
      });
      continue;
    }
    const fnCalls = c.parts.filter((p) => p.functionCall);
    if (c.role === "model" && fnCalls.length > 0) {
      messages.push({
        role: "CHATBOT",
        tool_calls: fnCalls.map((p) => ({ name: p.functionCall!.name, parameters: p.functionCall!.args ?? {} })),
      });
      continue;
    }
    const text = c.parts.filter((p) => p.text && !p.thought).map((p) => p.text).join("").trim();
    if (text) messages.push({ role: c.role === "model" ? "CHATBOT" : "USER", message: text });
  }

  const tools: CohereTool[] = (payload.tools ?? []).flatMap((t) =>
    (t.functionDeclarations ?? []).map((fd) => ({
      name: fd.name,
      description: fd.description ?? "",
      parameter_definitions: jsonSchemaToParamDefs(fd.parameters),
    })),
  );

  return {
    stream: true, // STC client sends stream:true; the adapter ignores the stream body and polls.
    messages,
    ...(system ? { system } : {}),
    ...(tools.length ? { tools } : {}),
    agent: { id: agentId },
    conversation: { id: conversationId },
  };
}

function jsonSchemaToParamDefs(schema: unknown): CohereTool["parameter_definitions"] {
  const s = (schema ?? {}) as { properties?: Record<string, { description?: string; type?: string }>; required?: string[] };
  const required = new Set(s.required ?? []);
  const out: CohereTool["parameter_definitions"] = {};
  for (const [name, prop] of Object.entries(s.properties ?? {})) {
    out[name] = { description: prop.description ?? "", type: mapType(prop.type), required: required.has(name) };
  }
  return out;
}
function mapType(t?: string): string {
  switch ((t ?? "string").toLowerCase()) {
    case "integer": return "int";
    case "number": return "float";
    case "boolean": return "bool";
    case "array": return "list";
    case "object": return "dict";
    default: return "str";
  }
}

// === RESPONSE TRANSLATION: Cohere conversation -> Gemini generateContent ====
export function cohereConversationToGemini(convo: unknown): {
  candidates: Array<{ content: { parts: GeminiPart[] }; finishReason: string }>;
  usageMetadata: { promptTokenCount: number; candidatesTokenCount: number; cachedContentTokenCount: number };
} {
  const c = (convo ?? {}) as { messages?: unknown[]; meta?: { tokens?: { input_tokens?: number; output_tokens?: number } } };
  const msgs = (c.messages ?? []) as Record<string, unknown>[];
  const last = msgs.length ? msgs[msgs.length - 1] : {};
  const parts: GeminiPart[] = [];

  const text = extractText(last);
  if (text) parts.push({ text });

  const toolCalls = (last.tool_calls ?? []) as Array<{ name: string; parameters?: Record<string, unknown> }>;
  for (const tc of toolCalls) parts.push({ functionCall: { name: tc.name, args: tc.parameters ?? {} } });

  const tokens = c.meta?.tokens ?? {};
  return {
    candidates: [{ content: { parts }, finishReason: toolCalls.length ? "TOOL_CALLS" : "STOP" }],
    usageMetadata: {
      promptTokenCount: tokens.input_tokens ?? 0,
      candidatesTokenCount: tokens.output_tokens ?? 0,
      cachedContentTokenCount: 0,
    },
  };
}

function extractText(msg: Record<string, unknown>): string {
  if (typeof msg.message === "string") return msg.message;
  if (typeof msg.text === "string") return msg.text;
  const content = msg.content;
  if (Array.isArray(content)) {
    const withText = content.find((b) => b && typeof (b as { text?: unknown }).text === "string");
    if (withText) return (withText as { text: string }).text;
  }
  if (typeof content === "string") return content;
  return "";
}

/** True when the conversation's last message is an assistant/CHATBOT reply
 *  (the poll-completion signal). */
export function lastRoleIsAssistant(convo: unknown): boolean {
  const msgs = ((convo as { messages?: unknown[] })?.messages ?? []) as Record<string, unknown>[];
  const last = msgs[msgs.length - 1];
  const role = String(last?.role ?? "").toUpperCase();
  return role === "CHATBOT" || role === "ASSISTANT";
}
