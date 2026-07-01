// Golden checks for the provider registry + model→provider resolution.
// Pure logic; no network. Run: node scripts/test-provider-seam.mjs
// (Node >=23 strips the type-only import in provider.ts at runtime.)
import assert from "node:assert";
import {
  registerProvider,
  getProvider,
  hasProvider,
  resolveProviderForModel,
  GEMINI_PROVIDER_ID,
  COHERE_NORTH_PROVIDER_ID,
} from "../lib/llm/provider.ts";

// resolveProviderForModel: today's models all route to gemini.
assert.equal(resolveProviderForModel("gemini-3.1-pro-preview"), GEMINI_PROVIDER_ID);
assert.equal(resolveProviderForModel("gemini-2.5-flash"), GEMINI_PROVIDER_ID);
assert.equal(resolveProviderForModel("text-embedding-004"), GEMINI_PROVIDER_ID);
assert.equal(resolveProviderForModel(""), GEMINI_PROVIDER_ID);
// R2 forward-compat: cohere/command names route to cohere-north.
assert.equal(resolveProviderForModel("cohere-north-default"), COHERE_NORTH_PROVIDER_ID);
assert.equal(resolveProviderForModel("command-r-plus"), COHERE_NORTH_PROVIDER_ID);

// registry: register/get/has + clear error on missing id.
assert.equal(hasProvider("test-x"), false);
const fake = { id: "test-x", invoke: async () => ({ ok: true }) };
registerProvider(fake);
assert.equal(hasProvider("test-x"), true);
assert.strictEqual(getProvider("test-x"), fake);
assert.throws(() => getProvider("nope"), /No LLM provider registered/);

console.log("provider-seam: OK");

// R1 invariant: every current model routes to gemini (no cohere yet configured).
for (const m of [
  "gemini-3.1-pro-preview",
  "gemini-2.5-pro",
  "gemini-2.5-flash",
  "gemini-2.0-flash",
  "text-embedding-004",
  "text-embedding-005",
]) {
  assert.equal(
    resolveProviderForModel(m),
    GEMINI_PROVIDER_ID,
    `model ${m} must route to gemini in R1`,
  );
}
console.log("provider-seam routing invariant: OK");
