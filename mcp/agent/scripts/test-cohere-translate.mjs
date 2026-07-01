// Golden checks for the Cohere North translation core (pure functions; no
// network, no Cohere key). Run: node scripts/test-cohere-translate.mjs
import assert from "node:assert";
import {
  geminiToCohereBody,
  cohereConversationToGemini,
} from "../lib/llm/cohere-translate.ts";

// ---- geminiToCohereBody ----------------------------------------------------
const payload = {
  systemInstruction: { role: "system", parts: [{ text: "You are Guardian." }] },
  tools: [
    {
      functionDeclarations: [
        {
          name: "xsoar_get_incident",
          description: "Fetch an incident.",
          parameters: {
            type: "object",
            properties: { id: { type: "string", description: "incident id" }, limit: { type: "integer" } },
            required: ["id"],
          },
        },
      ],
    },
  ],
  contents: [
    { role: "user", parts: [{ text: "Investigate incident 42." }] },
    { role: "model", parts: [{ functionCall: { name: "xsoar_get_incident", args: { id: "42" } } }] },
    { role: "user", parts: [{ functionResponse: { name: "xsoar_get_incident", response: { severity: "high" } } }] },
  ],
};

const body = geminiToCohereBody(payload, "agent-123", "conv-abc");

assert.equal(body.stream, true, "stream true");
assert.equal(body.system, "You are Guardian.", "system prompt");
assert.deepEqual(body.agent, { id: "agent-123" }, "agent id");
assert.deepEqual(body.conversation, { id: "conv-abc" }, "conversation id");

// tools → parameter_definitions (JSON-Schema type map + required)
assert.equal(body.tools.length, 1);
const pd = body.tools[0].parameter_definitions;
assert.equal(pd.id.type, "str");
assert.equal(pd.id.required, true);
assert.equal(pd.limit.type, "int");
assert.equal(pd.limit.required, false);

// messages: USER text, CHATBOT tool_calls, TOOL tool_results
assert.equal(body.messages.length, 3);
assert.deepEqual(body.messages[0], { role: "USER", message: "Investigate incident 42." });
assert.equal(body.messages[1].role, "CHATBOT");
assert.deepEqual(body.messages[1].tool_calls, [{ name: "xsoar_get_incident", parameters: { id: "42" } }]);
assert.equal(body.messages[2].role, "TOOL");
assert.equal(body.messages[2].tool_results[0].call.name, "xsoar_get_incident");
assert.deepEqual(body.messages[2].tool_results[0].outputs, [{ severity: "high" }]);

console.log("cohere geminiToCohereBody: OK");

// ---- cohereConversationToGemini -------------------------------------------
// (a) final text reply with STC content[1].text nesting + token usage
const convoText = {
  messages: [
    { role: "USER", message: "hi" },
    { role: "CHATBOT", content: [{ type: "thinking" }, { text: "Two instances are connected." }] },
  ],
  meta: { tokens: { input_tokens: 120, output_tokens: 8 } },
};
const g1 = cohereConversationToGemini(convoText);
assert.equal(g1.candidates[0].content.parts[0].text, "Two instances are connected.");
assert.equal(g1.candidates[0].finishReason, "STOP");
assert.equal(g1.usageMetadata.promptTokenCount, 120);
assert.equal(g1.usageMetadata.candidatesTokenCount, 8);

// (b) tool-call reply → functionCall parts
const convoTool = {
  messages: [
    { role: "USER", message: "list incidents" },
    { role: "CHATBOT", tool_calls: [{ name: "instances_list", parameters: {} }] },
  ],
};
const g2 = cohereConversationToGemini(convoTool);
assert.equal(g2.candidates[0].content.parts[0].functionCall.name, "instances_list");
assert.equal(g2.candidates[0].finishReason, "TOOL_CALLS");

// (c) flat `message` fallback
const g3 = cohereConversationToGemini({ messages: [{ role: "CHATBOT", message: "flat text" }] });
assert.equal(g3.candidates[0].content.parts[0].text, "flat text");

console.log("cohere cohereConversationToGemini: OK");
