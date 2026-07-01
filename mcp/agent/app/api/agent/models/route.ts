/**
 * Guardian model catalog — returns the Vertex AI / Gemini models that
 * guardian standalone supports today, plus placeholder entries for the
 * other providers (Anthropic, OpenAI) that are WIP.
 *
 * Spark's workspace exposes /api/v1/models via its api-gateway, which
 * dynamically discovers models from each connected provider. Guardian
 * is single-tenant and currently only ships Vertex AI integration in
 * the chat code path, so we serve a curated catalog from this route
 * rather than probing remote model APIs at request time.
 *
 * Shape matches Spark's ModelInfo (lib/api/types.ts) so the ported
 * /models page renders without adapter glue.
 */

import { NextResponse } from "next/server";
import { getEffectiveRuntimeConfig } from "@/lib/runtime-config";
import {
  resolveAnthropicApiKey,
  resolveAnthropicCliKey,
} from "@/lib/anthropic-credentials";

export const dynamic = "force-dynamic";

// Trimmed `ModelInfo` shape — just the fields the /models page reads.
interface ModelInfo {
  provider: string;
  model: string;
  displayName?: string;
  kind?: "chat" | "embedding" | "image" | "voice";
  contextWindow: number;
  supportsThinking?: boolean;
  supportsTools?: boolean;
  interactionPatterns?: ("streaming_api" | "cli_tool" | "async_job" | "interactive_session")[];
  launchStage?: "GA" | "PUBLIC_PREVIEW" | "PRIVATE_PREVIEW" | "EXPERIMENTAL";
  // v0.17.86 — coming-soon flag. See lib/api/types.ts ModelInfo.wip.
  wip?: boolean;
}

// Guardian's curated Vertex catalog. Updated when Google ships new
// generations. Context windows reflect the published Vertex docs at
// the time of writing.
const VERTEX_MODELS: ModelInfo[] = [
  // ── Chat (Gemini 3 family) ──────────────────────────────────────
  // v0.17.86 — Gemini 3.5 Flash. Released at Google I/O 2026 (May
  // 19-20); GA on Vertex AI with global + regional endpoints. Coding
  // and reasoning quality close to Gemini Pro at Flash speed and
  // cost (~$1.50 / $9 per 1M tokens). Default thinking effort is
  // medium per the model card. There is no Gemini 3.5 Pro yet —
  // Google released only the Flash tier at I/O 2026.
  {
    provider: "vertex",
    model: "gemini-3.5-flash",
    displayName: "Gemini 3.5 Flash",
    kind: "chat",
    contextWindow: 1_000_000,
    supportsThinking: true,
    supportsTools: true,
    interactionPatterns: ["streaming_api"],
    launchStage: "GA",
  },
  {
    provider: "vertex",
    model: "gemini-3.1-pro-preview",
    displayName: "Gemini 3.1 Pro",
    kind: "chat",
    contextWindow: 2_000_000,
    supportsThinking: true,
    supportsTools: true,
    interactionPatterns: ["streaming_api"],
    launchStage: "PUBLIC_PREVIEW",
  },
  {
    provider: "vertex",
    model: "gemini-3.0-pro",
    displayName: "Gemini 3.0 Pro",
    kind: "chat",
    contextWindow: 2_000_000,
    supportsThinking: true,
    supportsTools: true,
    interactionPatterns: ["streaming_api"],
    launchStage: "GA",
  },
  {
    provider: "vertex",
    model: "gemini-2.5-pro",
    displayName: "Gemini 2.5 Pro",
    kind: "chat",
    contextWindow: 2_000_000,
    supportsThinking: true,
    supportsTools: true,
    interactionPatterns: ["streaming_api"],
    launchStage: "GA",
  },
  {
    provider: "vertex",
    model: "gemini-2.5-flash",
    displayName: "Gemini 2.5 Flash",
    kind: "chat",
    contextWindow: 1_000_000,
    supportsThinking: true,
    supportsTools: true,
    interactionPatterns: ["streaming_api"],
    launchStage: "GA",
  },
  {
    provider: "vertex",
    model: "gemini-2.5-flash-lite",
    displayName: "Gemini 2.5 Flash Lite",
    kind: "chat",
    contextWindow: 1_000_000,
    supportsThinking: false,
    supportsTools: true,
    interactionPatterns: ["streaming_api"],
    launchStage: "GA",
  },
  // ── Embedding ───────────────────────────────────────────────────
  {
    provider: "vertex",
    model: "gemini-embedding-001",
    displayName: "Gemini Embedding",
    kind: "embedding",
    contextWindow: 8_192,
    interactionPatterns: ["streaming_api"],
    launchStage: "GA",
  },
  {
    provider: "vertex",
    model: "text-embedding-005",
    displayName: "text-embedding-005",
    kind: "embedding",
    contextWindow: 2_048,
    interactionPatterns: ["streaming_api"],
    launchStage: "GA",
  },
  // ── Image generation ────────────────────────────────────────────
  {
    provider: "vertex",
    model: "imagen-4.0-generate-preview",
    displayName: "Imagen 4",
    kind: "image",
    contextWindow: 0,
    interactionPatterns: ["async_job"],
    launchStage: "PUBLIC_PREVIEW",
  },
  {
    provider: "vertex",
    model: "imagen-3.0-generate-002",
    displayName: "Imagen 3",
    kind: "image",
    contextWindow: 0,
    interactionPatterns: ["async_job"],
    launchStage: "GA",
  },
  // ── Voice (TTS / STT) ───────────────────────────────────────────
  {
    provider: "vertex",
    model: "chirp-3-hd",
    displayName: "Chirp 3 HD (TTS)",
    kind: "voice",
    contextWindow: 0,
    interactionPatterns: ["streaming_api"],
    launchStage: "PUBLIC_PREVIEW",
  },
];

// Anthropic / Claude catalog. v0.17.81 — added so the /models page
// surfaces Claude entries when an Anthropic provider is configured
// (either anthropicApiKey for the streaming API path, or anthropicCliKey
// for the Claude Code CLI shell-out at /api/chat/cli).
//
// v0.17.86 — every Anthropic entry now ships with `wip: true`. The
// chat header's model dropdown filters wip entries out (operators
// can't accidentally route to a path we haven't fully validated yet).
// The /services Models page still surfaces them, just rendered with
// a greyed-out "Coming soon" treatment so the roadmap is visible.
// To re-enable Claude as a chat-selectable target, drop the wip flag
// on the relevant entries.
//
// Context windows + thinking flags reflect Anthropic's public model card
// at the time of writing. Update when Anthropic ships new generations.
const ANTHROPIC_MODELS: ModelInfo[] = [
  // ── Chat (Claude 4.x family, streaming_api path) ────────────────
  {
    provider: "anthropic",
    model: "claude-opus-4-7-20260415",
    displayName: "Claude Opus 4.7 (1M context)",
    kind: "chat",
    contextWindow: 1_000_000,
    supportsThinking: true,
    supportsTools: true,
    interactionPatterns: ["streaming_api"],
    launchStage: "GA",
    wip: true,
  },
  {
    provider: "anthropic",
    model: "claude-sonnet-4-6-20260213",
    displayName: "Claude Sonnet 4.6",
    kind: "chat",
    contextWindow: 200_000,
    supportsThinking: true,
    supportsTools: true,
    interactionPatterns: ["streaming_api"],
    launchStage: "GA",
    wip: true,
  },
  {
    provider: "anthropic",
    model: "claude-haiku-4-5-20260129",
    displayName: "Claude Haiku 4.5",
    kind: "chat",
    contextWindow: 200_000,
    supportsThinking: false,
    supportsTools: true,
    interactionPatterns: ["streaming_api"],
    launchStage: "GA",
    wip: true,
  },
  // ── CLI / Claude Code shell-out path ────────────────────────────
  // The Claude Code CLI uses its own runtime to pick the model; this
  // entry represents the routing target on the agent side. Operators
  // pair it with their Pro / Max subscription via anthropicCliKey
  // (device-code OAuth token).
  {
    provider: "anthropic-cli",
    model: "claude-code",
    displayName: "Claude Code (CLI shell-out)",
    kind: "chat",
    contextWindow: 1_000_000,
    supportsThinking: true,
    supportsTools: true,
    interactionPatterns: ["cli_tool", "interactive_session"],
    launchStage: "GA",
    wip: true,
  },
];

// R2 — Cohere North. Single static model (no discovery endpoint). Surfaced in
// the chat/jobs model dropdowns when a cohere-north provider is configured.
const COHERE_NORTH_MODELS: ModelInfo[] = [
  {
    provider: "cohere-north",
    model: "cohere-north-default",
    displayName: "Cohere North",
    kind: "chat",
    contextWindow: 128_000,
    supportsThinking: false,
    supportsTools: true,
    interactionPatterns: ["streaming_api", "async_job", "interactive_session"],
    launchStage: "PRIVATE_PREVIEW",
  },
];

export async function GET() {
  // v0.6.9 fix — pre-v0.6.9 this read `cfg.vertexProjectId` +
  // `cfg.vertexServiceAccountJson`, which DON'T EXIST on the
  // EffectiveRuntimeConfig type. The fields were silently undefined
  // at runtime, so `vertexConfigured` was always false → the route
  // always returned []. The /models page rendered an empty state
  // even on installs with a fully-configured Vertex provider.
  //
  // The correct signal: `GOOGLE_APPLICATION_CREDENTIALS` is populated
  // by `getEffectiveRuntimeConfig()` from
  // `resolveVertexCredentialsFromStore()` (returns the SA JSON content
  // when a vertex provider instance exists in ProviderStore), with an
  // env fallback. If THAT field is non-empty, Vertex is configured.
  //
  // Companion check: `GEMINI_API_KEY` — alternative auth path. Either
  // populates the same underlying Gemini model catalog.
  //
  // v0.17.82 — Anthropic catalog wired in. Pre-v0.17.82 the /models
  // page returned an empty list for Anthropic even on installs with
  // a fully-configured Anthropic provider, because the route's
  // catalog was hardcoded to Vertex only. The chat header's model
  // dropdown therefore never surfaced Claude entries, so operators
  // had no way to switch to Claude from the chat UI.
  //
  // Anthropic credential resolution mirrors `lib/anthropic-credentials.ts`:
  // either an explicit API key OR a Pro/Max OAuth token (the device-code
  // path from the providers page) unlocks BOTH the streaming-API entries
  // and the CLI shell-out entry, because the resolver's fallback chain
  // is symmetric (api_key falls back to OAuth, cli_key falls back to
  // api_key).
  const [cfg, anthropicApiKey, anthropicCliKey] = await Promise.all([
    getEffectiveRuntimeConfig(),
    resolveAnthropicApiKey(),
    resolveAnthropicCliKey(),
  ]);
  const vertexConfigured = Boolean(
    cfg.GOOGLE_APPLICATION_CREDENTIALS &&
      cfg.GOOGLE_APPLICATION_CREDENTIALS.trim(),
  );
  const geminiKeyConfigured = Boolean(
    cfg.GEMINI_API_KEY && cfg.GEMINI_API_KEY.trim(),
  );
  const anthropicConfigured = Boolean(anthropicApiKey || anthropicCliKey);
  // cfg carries the Cohere North endpoint + bearer (resolved from the
  // ProviderStore by getEffectiveRuntimeConfig). Both present → configured.
  const cohereConfigured = Boolean(
    cfg.COHERE_NORTH_ENDPOINT &&
      cfg.COHERE_NORTH_ENDPOINT.trim() &&
      cfg.COHERE_NORTH_BEARER_TOKEN &&
      cfg.COHERE_NORTH_BEARER_TOKEN.trim(),
  );

  const models: ModelInfo[] = [
    ...(vertexConfigured || geminiKeyConfigured ? VERTEX_MODELS : []),
    ...(anthropicConfigured ? ANTHROPIC_MODELS : []),
    ...(cohereConfigured ? COHERE_NORTH_MODELS : []),
  ];
  return NextResponse.json(models);
}
