/**
 * /api/agent/openapi — OpenAPI 3.0 spec for the agent UI's REST surface.
 *
 * Generated from lib/api-catalog.ts at request time. Cheap to compute
 * (~50 entries) and lets the catalog stay the single source of truth:
 * editing an endpoint description or example automatically flows into
 * the spec download.
 *
 * Use cases:
 *   - Operators paste the JSON into Swagger UI / Redoc / Postman to
 *     get an interactive client.
 *   - CI / lint tools validate that example bodies still match the
 *     declared schemas.
 *   - The /help/api detail page fetches per-endpoint snippets from
 *     the same generator (so the on-page snippet matches the
 *     downloadable spec exactly).
 *
 * Two output formats:
 *   - Default JSON (Content-Type: application/json)
 *   - YAML when ?format=yaml (Content-Type: application/yaml)
 *     useful for `git`-friendly spec checks-in.
 */

import { NextResponse } from "next/server";

import { generateOpenApiSpec } from "@/lib/openapi-generator";
// Round-13 / Phase 3.3 — jsonToYaml extracted to lib/ so it can be
// unit-tested without dragging in Next.js / OpenAPI generator surface.
// Test fixtures live in scripts/test-json-to-yaml.mjs.
import { jsonToYaml } from "@/lib/json-to-yaml";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const format = (url.searchParams.get("format") ?? "json").toLowerCase();
  // Use the request's host so the spec's `servers[0].url` matches
  // however the operator reached this route. Avoids "localhost:3000"
  // hard-coded into a spec downloaded from the deployed VM.
  const proto = request.headers.get("x-forwarded-proto") ?? "http";
  const host = request.headers.get("host") ?? "localhost:3000";
  // #API-F14 — stamp the spec with the running stack version instead of the
  // generator's hardcoded "0.2.0" placeholder. Same source/precedence as
  // /api/agent/version; falls back to "dev" on a build with no version env.
  const version =
    process.env.GUARDIAN_VERSION?.trim() ||
    process.env.NEXT_PUBLIC_GUARDIAN_VERSION?.trim() ||
    "dev";
  const spec = generateOpenApiSpec({ serverUrl: `${proto}://${host}`, version });

  if (format === "yaml" || format === "yml") {
    // Defense in depth: a YAML-conversion crash should return a
    // 500 with a real error body, not the bare empty 500 Next.js
    // emits when an exception escapes the route handler. Operator-
    // visible: the modal can show the failure message instead of
    // "loading…" forever.
    try {
      const body = jsonToYaml(spec);
      return new NextResponse(body, {
        status: 200,
        headers: {
          "Content-Type": "application/yaml; charset=utf-8",
          "Content-Disposition": 'inline; filename="guardian-agent-openapi.yaml"',
        },
      });
    } catch (err) {
      return new NextResponse(
        `# YAML conversion failed: ${err instanceof Error ? err.message : String(err)}\n# Falling back to JSON download is recommended.\n`,
        {
          status: 500,
          headers: { "Content-Type": "application/yaml; charset=utf-8" },
        },
      );
    }
  }

  // Default JSON. Pretty-printed for human eyeballs; the file size
  // (~50 endpoints) is small enough that compaction isn't worth the
  // worse readability.
  // #XCUT-F24 — mirror the YAML path's defense in depth: a serialization
  // crash should return a structured 500 with a real error body, not the
  // bare empty 500 Next.js emits when an exception escapes the handler.
  try {
    return new NextResponse(JSON.stringify(spec, null, 2), {
      status: 200,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Disposition": 'inline; filename="guardian-agent-openapi.json"',
      },
    });
  } catch (err) {
    return NextResponse.json(
      {
        error: "openapi_spec_serialization_failed",
        message: err instanceof Error ? err.message : String(err),
      },
      { status: 500 },
    );
  }
}
