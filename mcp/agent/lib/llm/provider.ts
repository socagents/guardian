import type { EffectiveRuntimeConfig } from "@/lib/runtime-config";

/** Context threaded to every provider invocation. */
export type LLMInvokeContext = {
  runtimeConfig: EffectiveRuntimeConfig;
  modelName: string;
};

/**
 * A model backend. The canonical interchange is the Gemini generateContent
 * request (`GeminiCallPayload`, built by the caller) and response object
 * (decoded by the caller). Adapters translate only at the wire, so the agent
 * loop is provider-agnostic without a bespoke neutral IR.
 */
export interface LLMProvider {
  readonly id: string;
  // The canonical response is the Gemini generateContent JSON — dynamically
  // shaped and read positionally by the agent loop (response.candidates[0]…).
  // The pre-seam dispatch returned `response.json()` (any); we preserve that
  // contract so the loop's existing reads type-check unchanged.
  invoke(payload: unknown, ctx: LLMInvokeContext): Promise<any>;
}

export const GEMINI_PROVIDER_ID = "gemini";
export const COHERE_NORTH_PROVIDER_ID = "cohere-north";

const registry = new Map<string, LLMProvider>();

export function registerProvider(provider: LLMProvider): void {
  registry.set(provider.id, provider);
}

export function hasProvider(id: string): boolean {
  return registry.has(id);
}

export function getProvider(id: string): LLMProvider {
  const provider = registry.get(id);
  if (!provider) {
    throw new Error(
      `No LLM provider registered for id '${id}'. Configure a model provider at /providers, then retry.`,
    );
  }
  return provider;
}

/**
 * Map a model name to its provider id. R1: every model that exists today is a
 * Google model → 'gemini' (the GeminiProvider handles the Vertex vs API-key
 * choice internally). The cohere/command prefixes are R2 forward-compat.
 */
export function resolveProviderForModel(modelName: string): string {
  const m = (modelName || "").toLowerCase();
  if (m.startsWith("cohere") || m.startsWith("command")) {
    return COHERE_NORTH_PROVIDER_ID;
  }
  return GEMINI_PROVIDER_ID;
}
