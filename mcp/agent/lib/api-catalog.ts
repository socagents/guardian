/**
 * API endpoint catalog — the single source of truth for the
 * /help/api documentation page, the try-it-out tool, and the
 * generated OpenAPI 3.0 spec.
 *
 * Conventions:
 *   - `path` is the agent-side proxy path (`/api/agent/<route>`),
 *     since that's what operators invoke from outside the bundle.
 *     The proxy attaches MCP_TOKEN server-side and forwards to
 *     `/api/v1/<route>` on the embedded MCP. Documenting the agent
 *     side means callers don't have to know about MCP_TOKEN at all.
 *   - Categories mirror the operator's mental model: Cognitive
 *     (what the agent knows), Configuration (what it acts on),
 *     Operations (what it runs), Self-Modification (the Phase-11
 *     surface), Observability, Identity, Workflows.
 *   - Each entry carries enough metadata to (a) render a detail
 *     page with sample request/response, (b) drive the try-it-out
 *     form, and (c) generate the OpenAPI 3.0 path object.
 *
 * Adding a new endpoint:
 *   1. Pick or add a category.
 *   2. Append an ApiEndpoint with the path, method, params, and a
 *      runnable example. The detail page form auto-generates from
 *      the params + body schema.
 *   3. The /api/agent/openapi route picks it up automatically.
 */

export type ApiCategory =
  | "cognitive"
  | "configuration"
  | "operations"
  | "self-modification"
  | "observability"
  | "identity"
  | "workflows"
  | "investigation";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface ParamSpec {
  name: string;
  /** OpenAPI primitive: string | integer | boolean | number | array | object */
  type: string;
  description: string;
  required?: boolean;
  /** Default value shown as the placeholder in the try-it-out form. */
  example?: string | number | boolean;
  /** When the param is an enum, list valid values. */
  enum?: string[];
}

export interface BodySpec {
  /** Always JSON for our REST surface. */
  contentType: "application/json";
  /** A small JSON schema fragment (object / properties / required). */
  schema: Record<string, unknown>;
  /** A complete, valid example body. */
  example: Record<string, unknown>;
}

export interface ResponseSpec {
  /** HTTP status — "200" / "404" / etc. */
  status: string;
  description: string;
  /** Truncated representative response body for docs. */
  example?: unknown;
}

export interface ApiEndpoint {
  /** Slug for /help/api/[id]. Stable across renames. */
  id: string;
  category: ApiCategory;
  method: HttpMethod;
  /** Agent-side path, e.g. /api/agent/jobs/{jobName}/runs */
  path: string;
  summary: string;
  description: string;
  pathParams?: ParamSpec[];
  queryParams?: ParamSpec[];
  body?: BodySpec;
  responses: ResponseSpec[];
  /** Phase-11 risk tier when this endpoint mutates state. Drives
   * the try-it-out warning banner color. Reads have no tier. */
  riskTier?: "soft" | "destructive" | "credential";
  /** True if invoking this endpoint requires operator approval at
   * the MCP-side gate (manifest.approvals.humanRequired[]). The
   * try-it-out UI surfaces this so operators don't get surprised. */
  requiresApproval?: boolean;
  /** OpenAPI tags for grouping in spec consumers. Defaults to category. */
  tags?: string[];
}

export const CATEGORY_META: Record<
  ApiCategory,
  { label: string; icon: string; description: string; color: string }
> = {
  cognitive: {
    label: "Cognitive",
    icon: "psychology",
    description: "Memory, knowledge bases, and chat sessions.",
    color: "primary",
  },
  configuration: {
    label: "Configuration",
    icon: "settings",
    description: "Runtime settings, persona, connector + provider instances, manifest.",
    color: "tertiary",
  },
  operations: {
    label: "Operations",
    icon: "schedule",
    description: "Scheduled jobs, run history, audit trail, notifications.",
    color: "primary",
  },
  "self-modification": {
    label: "Self-Modification",
    icon: "auto_fix_high",
    description: "Approvals lifecycle — what the agent has requested and what's pending.",
    color: "secondary",
  },
  observability: {
    label: "Observability",
    icon: "monitoring",
    description: "Health, metrics, embedder mode, request log.",
    color: "secondary",
  },
  identity: {
    label: "Identity & Access",
    icon: "vpn_key",
    description: "API keys — list, mint, rotate, revoke.",
    color: "error",
  },
  workflows: {
    label: "Workflows",
    icon: "account_tree",
    description: "A2UI workflows + model catalog.",
    color: "tertiary",
  },
  investigation: {
    label: "Investigation",
    icon: "shield",
    description: "Cases, issues, and indicators — the local investigation record.",
    color: "secondary",
  },
};

// ─────────────────────────────────────────────────────────────────
// COGNITIVE — memory, knowledge, sessions
// ─────────────────────────────────────────────────────────────────

const COGNITIVE: ApiEndpoint[] = [
  {
    id: "memory-list",
    category: "cognitive",
    method: "GET",
    path: "/api/agent/memory",
    summary: "List memory entries",
    description:
      "Return the agent's stored memories, optionally filtered by scope. " +
      "Memory rows are operator-curated facts about the org (tech stack, " +
      "past incidents, validated detections) that the agent recalls via " +
      "semantic search across sessions.",
    queryParams: [
      {
        name: "scope",
        type: "string",
        description: "Filter to one scope: agent | session:<id> | user | system.",
        example: "agent",
      },
      {
        name: "limit",
        type: "integer",
        description: "Max rows (1-500). Default 100.",
        example: 50,
      },
    ],
    responses: [
      {
        status: "200",
        description: "List of memory rows.",
        example: {
          memories: [
            {
              id: "m_8a3b…",
              key: "tech_stack:firewall",
              value: "Fortinet FortiGate (CEF, SYSLOG)",
              scope: "agent",
              created_at: "2026-04-12T08:00:00Z",
            },
          ],
          count: 1,
        },
      },
    ],
  },
  {
    id: "memory-search",
    category: "cognitive",
    method: "POST",
    path: "/api/agent/memory/search",
    summary: "Semantic search over memory",
    description:
      "Cosine-similarity search via the configured embedder " +
      "(VertexEmbedder / text-embedding-004 by default). Returns ranked " +
      "memory rows matching the natural-language query.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["query"],
        properties: {
          query: { type: "string", description: "Natural-language query." },
          limit: { type: "integer", description: "Top-K (1-100). Default 5." },
          scope: { type: "string", description: "Optional scope filter." },
        },
      },
      example: {
        query: "What firewall vendor are we using?",
        limit: 5,
        scope: "agent",
      },
    },
    responses: [
      {
        status: "200",
        description: "Ranked memory rows with cosine score.",
        example: {
          results: [
            {
              key: "tech_stack:firewall",
              value: "Fortinet FortiGate (CEF, SYSLOG)",
              score: 0.811,
            },
          ],
          count: 1,
        },
      },
    ],
  },
  {
    id: "memory-by-key",
    category: "cognitive",
    method: "GET",
    path: "/api/agent/memory/{key}",
    summary: "Get a memory by key",
    description: "Guardian keys memory rows by `key` per (key, scope). The path-param `key` carries the URL-encoded key.",
    pathParams: [
      { name: "key", type: "string", description: "URL-encoded memory key.", example: "tech_stack:firewall" },
    ],
    queryParams: [
      { name: "scope", type: "string", description: "Defaults to 'agent'.", example: "agent" },
    ],
    responses: [
      { status: "200", description: "Memory row." },
      { status: "404", description: "Key not found in scope." },
    ],
  },
  {
    id: "memory-delete",
    category: "cognitive",
    method: "DELETE",
    path: "/api/agent/memory/{key}",
    summary: "Delete a memory by key",
    description: "Permanently removes the row identified by (key, scope).",
    pathParams: [
      { name: "key", type: "string", description: "URL-encoded key.", example: "tech_stack:firewall" },
    ],
    queryParams: [
      { name: "scope", type: "string", description: "Default 'agent'.", example: "agent" },
    ],
    responses: [
      { status: "200", description: "Deleted." },
      { status: "404", description: "Key not found." },
    ],
    riskTier: "destructive",
  },
  {
    id: "knowledge-list",
    category: "cognitive",
    method: "GET",
    path: "/api/agent/knowledge",
    summary: "List loaded knowledge bases",
    description: "Per-KB summary: name, doc_count, latest_loaded_at. KBs are bundle-shipped reference content.",
    responses: [
      {
        status: "200",
        description: "List of KBs.",
        example: {
          kbs: [
            { name: "guardian-soc", doc_count: 3, latest_loaded_at: "2026-04-29T09:07:42Z" },
            { name: "xql-examples", doc_count: 161, latest_loaded_at: "2026-05-01T08:24:09Z" },
          ],
          count: 2,
        },
      },
    ],
  },
  {
    id: "knowledge-docs",
    category: "cognitive",
    method: "GET",
    path: "/api/agent/knowledge/{name}/docs",
    summary: "List documents in a KB",
    description: "Browse view — content omitted. Fetch a single doc via /docs/{doc_id} for the full body.",
    pathParams: [
      { name: "name", type: "string", description: "KB name.", example: "xql-examples" },
    ],
    queryParams: [
      { name: "limit", type: "integer", description: "Max rows (1-500). Default 100.", example: 100 },
      { name: "offset", type: "integer", description: "Pagination offset.", example: 0 },
      { name: "category", type: "string", description: "Filter by schema category.", example: "detection" },
    ],
    responses: [
      { status: "200", description: "List of docs (no content)." },
      { status: "404", description: "Unknown KB name." },
    ],
  },
  {
    id: "knowledge-doc-get",
    category: "cognitive",
    method: "GET",
    path: "/api/agent/knowledge/{name}/docs/{doc_id}",
    summary: "Fetch one knowledge document",
    description: "Returns the full doc with content and metadata. Audited.",
    pathParams: [
      { name: "name", type: "string", description: "KB name.", example: "xql-examples" },
      { name: "doc_id", type: "string", description: "Document ID.", example: "XQL-001-bbfbd1c9" },
    ],
    responses: [
      { status: "200", description: "Document with content + metadata." },
      { status: "404", description: "Doc not found in KB." },
    ],
  },
  {
    id: "knowledge-search",
    category: "cognitive",
    method: "POST",
    path: "/api/agent/knowledge/{name}/search",
    summary: "Semantic search within a KB",
    description: "Cosine search via the same embedder as memory_search. Filter by category, tighten with min_score.",
    pathParams: [
      { name: "name", type: "string", description: "KB name.", example: "xql-examples" },
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["query"],
        properties: {
          query: { type: "string" },
          limit: { type: "integer", description: "Default 5." },
          category: { type: "string", description: "Optional schema-category filter." },
          min_score: { type: "number", description: "Hide results below this cosine threshold." },
        },
      },
      example: { query: "C2 beaconing detection", limit: 5 },
    },
    responses: [
      { status: "200", description: "Ranked docs with cosine score." },
      { status: "400", description: "Empty / missing query field." },
      { status: "404", description: "Unknown KB name." },
    ],
  },
  {
    id: "sessions-list",
    category: "cognitive",
    method: "GET",
    path: "/api/agent/sessions",
    summary: "List chat sessions",
    description: "Newest first. Used by the chat sidebar.",
    queryParams: [
      { name: "user", type: "string", description: "Filter to one user.", example: "operator" },
      { name: "limit", type: "integer", description: "Default 20.", example: 20 },
      { name: "active_only", type: "boolean", description: "Hide ended sessions.", example: false },
    ],
    responses: [{ status: "200", description: "Sessions newest first." }],
  },
  {
    id: "sessions-create",
    category: "cognitive",
    method: "POST",
    path: "/api/agent/sessions",
    summary: "Create a chat session",
    description: "Used by the chat route at the start of each new conversation.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        properties: {
          user: { type: "string" },
          title: { type: "string" },
          meta: { type: "object" },
        },
      },
      example: { user: "operator", title: null, meta: {} },
    },
    responses: [{ status: "201", description: "Session created." }],
  },
  {
    id: "sessions-get",
    category: "cognitive",
    method: "GET",
    path: "/api/agent/sessions/{sessionId}",
    summary: "Fetch a session header + ordered messages",
    description: "Body shape: {session, messages: [{role, content, ...}]}.",
    pathParams: [{ name: "sessionId", type: "string", description: "Session UUID.", example: "s_abc…" }],
    responses: [
      { status: "200", description: "Session + messages." },
      { status: "404", description: "Session not found." },
    ],
  },
  {
    id: "sessions-end",
    category: "cognitive",
    method: "POST",
    path: "/api/agent/sessions/{sessionId}/end",
    summary: "Mark a session as ended",
    description: "Sessions stay browsable but no new messages can be appended. Idempotent.",
    pathParams: [{ name: "sessionId", type: "string", description: "Session UUID." }],
    responses: [{ status: "200", description: "Ended." }],
    riskTier: "soft",
  },
  {
    id: "sessions-export",
    category: "cognitive",
    method: "GET",
    path: "/api/agent/sessions/{sessionId}/export",
    summary: "Export a session as JSON or markdown",
    description: "Format defaults to JSON; pass ?format=markdown for a human-readable transcript.",
    pathParams: [{ name: "sessionId", type: "string", description: "Session UUID." }],
    queryParams: [
      { name: "format", type: "string", enum: ["json", "markdown"], example: "markdown", description: "Output format." },
    ],
    responses: [{ status: "200", description: "Transcript." }],
  },
  {
    id: "sessions-by-sessionId-fork-post",
    category: "cognitive",
    method: "POST",
    path: "/api/agent/sessions/{sessionId}/fork",
    summary: "Fork a new session from an existing one",
    description: "Branches a new chat session off an existing session's message history. With no body it copies the full conversation; pass from_message_id to copy messages up-to-and-including that point. title and user override the defaults (parent title + ' (fork)', parent user). The agent route is a hand-rolled passthrough to the MCP POST /api/v1/sessions/{session_id}/fork handler, which calls SqliteSessionStore.fork_session and returns the new session. The new session's meta carries forked_from (and fork_point_message_id when a cut-off was given).",
    pathParams: [
      {
        name: "sessionId",
        type: "string",
        description: "ID of the parent session to fork from.",
        required: true,
        example: "9f3a1c20-1b4e-4d2a-bc77-0a1f2e3d4c5b"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: [],
        properties: {
          from_message_id: {
            type: "string",
            description: "Message ID to cut the fork off at (copies messages with ts <= the fork message's ts). Must belong to the parent session or the fork is rejected. Omit to fork the entire conversation."
          },
          title: {
            type: "string",
            description: "Title for the new session. Defaults to the parent's title with ' (fork)' appended (or null when the parent has no title)."
          },
          user: {
            type: "string",
            description: "Owner of the new session. Defaults to the parent session's user."
          }
        }
      },
      example: {
        from_message_id: "3c2b1a09-7f6e-5d4c-3b2a-1098f7e6d5c4",
        title: "Phishing triage (fork)",
        user: "operator"
      }
    },
    responses: [
      {
        status: "201",
        description: "Fork created. Returns {session: {...}} — id, user, started_at, ended_at, title, meta (includes forked_from, and fork_point_message_id when a cut-off was given), message_count.",
        example: {
          session: {
            id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            user: "operator",
            started_at: "2026-06-17T14:02:11Z",
            ended_at: null,
            title: "Phishing triage (fork)",
            meta: {
              forked_from: "9f3a1c20-1b4e-4d2a-bc77-0a1f2e3d4c5b",
              fork_point_message_id: "3c2b1a09-7f6e-5d4c-3b2a-1098f7e6d5c4"
            },
            message_count: 7
          }
        }
      },
      {
        status: "404",
        description: "Parent session not found, or from_message_id does not belong to it (invalid fork point). fork_session returns None in both cases.",
        example: { error: "parent session not found or fork_point invalid" }
      },
      {
        status: "401",
        description: "Missing or invalid session cookie / API key — rejected by the agent middleware before reaching this route."
      },
      {
        status: "500",
        description: "Resolved MCP base URL was empty/invalid ({error:'bad MCP URL'}).",
        example: { error: "bad MCP URL" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent host.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "soft",
    tags: ["sessions", "chat", "cognitive"],
  },
  {
    id: "sessions-by-sessionId-messages",
    category: "cognitive",
    method: "GET",
    path: "/api/agent/sessions/{sessionId}/messages",
    summary: "Read a session transcript",
    description: "Returns the ordered message history for a session. By default (no limit) every message is returned ascending by timestamp; pass limit to paginate. The agent route forwards the incoming query string verbatim to the MCP GET /api/v1/sessions/{session_id}/messages handler (get_session_messages), which 404s if the session does not exist.",
    pathParams: [
      {
        name: "sessionId",
        type: "string",
        description: "ID of the session whose messages to read.",
        required: true,
        example: "9f3a1c20-1b4e-4d2a-bc77-0a1f2e3d4c5b"
      }
    ],
    queryParams: [
      {
        name: "limit",
        type: "integer",
        description: "Max messages to return. Omitted/empty/unparseable/<=0 = no limit (full transcript, SQLite LIMIT -1). Pagination is opt-in.",
        example: "50"
      },
      {
        name: "offset",
        type: "integer",
        description: "Number of messages to skip. Defaults to 0.",
        example: "0"
      },
      {
        name: "ascending",
        type: "boolean",
        description: "Order by timestamp ascending (oldest first). Defaults to true.",
        example: "true"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Transcript returned as {session_id, messages:[...], count}. Each message has id, session_id, ts (microsecond ISO8601), role, content, tool_call_id, meta.",
        example: {
          session_id: "9f3a1c20-1b4e-4d2a-bc77-0a1f2e3d4c5b",
          messages: [
            {
              id: "3c2b1a09-7f6e-5d4c-3b2a-1098f7e6d5c4",
              session_id: "9f3a1c20-1b4e-4d2a-bc77-0a1f2e3d4c5b",
              ts: "2026-06-17T14:00:01.000123Z",
              role: "user",
              content: "Summarize case 4821",
              tool_call_id: null,
              meta: {}
            }
          ],
          count: 1
        }
      },
      {
        status: "404",
        description: "Session not found (get_session returned None).",
        example: { error: "session not found" }
      },
      {
        status: "401",
        description: "Missing or invalid session cookie / API key — rejected by the agent middleware before reaching this route."
      },
      {
        status: "502",
        description: "Upstream MCP fetch threw (network error or 10s AbortSignal.timeout). Returns {error:<message>}.",
        example: { error: "The operation was aborted due to timeout" }
      },
      {
        status: "500",
        description: "Resolved MCP base URL was empty/invalid ({error:'bad MCP URL'}).",
        example: { error: "bad MCP URL" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent host.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    tags: ["sessions", "chat", "transcript", "cognitive"],
  },
  {
    id: "sessions-by-sessionId-messages-post",
    category: "cognitive",
    method: "POST",
    path: "/api/agent/sessions/{sessionId}/messages",
    summary: "Append a message to a session",
    description: "Appends a single message turn to a session's transcript. role and content are required strings; role must be one of the store's allowed roles (user, assistant, tool, system). tool_call_id and meta are optional. The agent route forwards the raw body to the MCP POST /api/v1/sessions/{session_id}/messages handler (append_message), which persists via SqliteSessionStore.append_message.",
    pathParams: [
      {
        name: "sessionId",
        type: "string",
        description: "ID of the session to append to. Must already exist (else 400).",
        required: true,
        example: "9f3a1c20-1b4e-4d2a-bc77-0a1f2e3d4c5b"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["role", "content"],
        properties: {
          role: {
            type: "string",
            description: "Message role; must be one of the allowed roles: user, assistant, tool, system."
          },
          content: { type: "string", description: "Message body text." },
          tool_call_id: {
            type: "string",
            description: "Optional tool-call correlation ID for tool-role messages."
          },
          meta: {
            type: "object",
            description: "Optional metadata blob (e.g. tool name, args, model, cost). Falsy/omitted defaults to {}."
          }
        }
      },
      example: {
        role: "user",
        content: "Pull the indicators for case 4821",
        meta: { source: "operator" }
      }
    },
    responses: [
      {
        status: "201",
        description: "Message appended. Returns {message: {...}} — id, session_id, ts (microsecond ISO8601), role, content, tool_call_id, meta.",
        example: {
          message: {
            id: "7e6d5c4b-3a29-1807-f6e5-d4c3b2a10987",
            session_id: "9f3a1c20-1b4e-4d2a-bc77-0a1f2e3d4c5b",
            ts: "2026-06-17T14:05:33.456789Z",
            role: "user",
            content: "Pull the indicators for case 4821",
            tool_call_id: null,
            meta: { source: "operator" }
          }
        }
      },
      {
        status: "400",
        description: "Invalid JSON body ({error:'invalid JSON body: <exc>'}), body not an object ({error:'body must be a JSON object'}), role/content missing or not strings ({error:\"'role' and 'content' are required strings\"}), or append_message raised ValueError — role not in {user,assistant,tool,system} or the session does not exist.",
        example: { error: "'role' and 'content' are required strings" }
      },
      {
        status: "401",
        description: "Missing or invalid session cookie / API key — rejected by the agent middleware before reaching this route."
      },
      {
        status: "502",
        description: "Upstream MCP fetch threw (network error or 10s AbortSignal.timeout). Returns {error:<message>}.",
        example: { error: "fetch failed" }
      },
      {
        status: "500",
        description: "Resolved MCP base URL was empty/invalid ({error:'bad MCP URL'}).",
        example: { error: "bad MCP URL" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent host.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "soft",
    tags: ["sessions", "chat", "transcript", "cognitive"],
  },
  {
    id: "skills",
    category: "cognitive",
    method: "GET",
    path: "/api/skills",
    summary: "List all on-disk skills (or read one)",
    description: "Native agent route. It does NOT proxy to the MCP REST surface — it calls MCP TOOLS directly via mcpClient.callTool. With no query param it calls skills_list_all (which returns a bare JSON array of skill records) and wraps it as {success:true, skills:[...]}. When a file_path query param is present it instead calls skills_read and returns that tool's parsed object as-is.",
    queryParams: [
      {
        name: "file_path",
        type: "string",
        description: "Optional. When set, switches the route from list mode to single-skill read mode. Relative path from the skills directory, e.g. 'workflows/xsoar_case_investigation.md'.",
        example: "workflows/xsoar_case_investigation.md"
      }
    ],
    responses: [
      {
        status: "200",
        description: "List mode (no file_path): {success:true, skills:[...]}. Each skill record from get_all_skills carries file_path, absolute_path, name, displayName, category, declared_category, description, icon, source, filename, size_bytes, modified, has_frontmatter, plus frontmatter passthrough (keywords, model, thinking, permissions, etc.). Read mode (file_path set, skill exists): the skills_read object {success:true, content, path, size_bytes} returned verbatim.",
        example: {
          success: true,
          skills: [
            {
              file_path: "workflows/xsoar_case_investigation.md",
              name: "xsoar_case_investigation",
              displayName: "XSOAR Case Investigation",
              category: "workflows",
              description: "Investigate an XSOAR case end to end",
              source: "platform",
              filename: "xsoar_case_investigation.md",
              size_bytes: 4096,
              modified: 1718000000.0,
              has_frontmatter: true
            }
          ]
        }
      },
      {
        status: "200",
        description: "Read mode with file_path set but skill missing: skills_read returns {success:false, error:'Skill not found: <path>'}. The agent route does NOT use the MCP REST endpoint (which would set 404) — it calls the tool and returns the parsed result with HTTP 200.",
        example: { success: false, error: "Skill not found: workflows/missing.md" }
      },
      {
        status: "500",
        description: "Route-level failure (MCP unreachable, JSON parse error in parseToolResult). Catch block returns {success:false, error:<message|'Unknown error'>} with status 500.",
        example: { success: false, error: "Unknown error" }
      }
    ],
    tags: ["skills", "catalog", "read"],
  },
  {
    id: "skills-delete",
    category: "cognitive",
    method: "DELETE",
    path: "/api/skills",
    summary: "Soft-delete a skill file",
    description: "Native agent route. Unlike GET/POST/PUT, DELETE is the ONLY method that proxies to the MCP REST endpoint DELETE /api/v1/skills/{file_path:path} (api/skills.py delete_skill) rather than calling a tool. The REST handler calls skills_crud.delete_skill directly — bypassing the Phase-11 gated skills_delete tool wrapper because an operator UI click IS the approval. The delete is a soft-delete: the file is renamed into <skills_dir>/.deleted/ (collision-suffixed _1, _2, …) and is therefore recoverable. The agent path-encodes each segment of file_path while preserving slashes before proxying.",
    queryParams: [
      {
        name: "file_path",
        type: "string",
        description: "Relative path from the skills directory of the skill to delete, e.g. 'workflows/xsoar_case_investigation.md'. Read from the query string by the agent route, then forwarded as the {file_path:path} suffix to the MCP REST endpoint.",
        required: true,
        example: "workflows/xsoar_case_investigation.md"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Skill soft-deleted. delete_skill returns {success:true, message:'Deleted skill: <path>', backup:'<relpath-from-skills-dir>'} where backup is the new location under.deleted/. the agent proxy passes the body and status through unchanged.",
        example: {
          success: true,
          message: "Deleted skill: workflows/xsoar_case_investigation.md",
          backup: ".deleted/xsoar_case_investigation.md"
        }
      },
      {
        status: "400",
        description: "file_path query param missing. Agent route returns {success:false, error:'file_path is required.'} BEFORE proxying.",
        example: { success: false, error: "file_path is required." }
      },
      {
        status: "404",
        description: "Skill not found. The MCP REST delete_skill handler sets status_code=404 when skills_crud.delete_skill returns {success:false, error:'Skill not found: <path>'}; the agent proxy passes the 404 + body through.",
        example: { success: false, error: "Skill not found: workflows/missing.md" }
      }
    ],
    riskTier: "destructive",
    tags: ["skills", "catalog", "delete"],
  },
  {
    id: "skills-patch",
    category: "cognitive",
    method: "PATCH",
    path: "/api/skills",
    summary: "Enable or disable a skill",
    description: "Native agent route. Like DELETE, it proxies to the MCP REST endpoint PATCH /api/v1/skills/{file_path:path} (api/skills.py patch_skill → skills_crud.set_skill_enabled) rather than calling a tool. file_path arrives as a query param; the {enabled: boolean} body is forwarded. The handler writes the `enabled` flag into the skill's YAML frontmatter (preserving the body). A skill with enabled=false is excluded from the agent's system prompt by fetchSkillsForPrompt — disabling hides it from the agent entirely. Recorded in the audit log as skill_enabled / skill_disabled. The operator UI click is the approval (no /approvals step).",
    queryParams: [
      {
        name: "file_path",
        type: "string",
        description: "Relative path from the skills directory of the skill to toggle, e.g. 'workflows/xsoar_case_investigation.md'. Read from the query string, then forwarded as the {file_path:path} suffix to the MCP REST endpoint.",
        required: true,
        example: "workflows/xsoar_case_investigation.md"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["enabled"],
        properties: {
          enabled: { type: "boolean", description: "Desired state. false drops the skill from the agent prompt." }
        }
      },
      example: { enabled: false }
    },
    responses: [
      {
        status: "200",
        description: "Skill toggled. set_skill_enabled returns {success:true, message:'Skill disabled: <path>', path:'<path>', enabled:false}.",
        example: {
          success: true,
          message: "Skill disabled: workflows/xsoar_case_investigation.md",
          path: "workflows/xsoar_case_investigation.md",
          enabled: false
        }
      },
      {
        status: "400",
        description: "file_path query param missing, or the body's 'enabled' is not a boolean.",
        example: { success: false, error: "file_path is required." }
      },
      {
        status: "404",
        description: "Skill not found. The MCP REST patch_skill handler sets 404 when set_skill_enabled returns {success:false, error:'Skill not found: <path>'}.",
        example: { success: false, error: "Skill not found: workflows/missing.md" }
      }
    ],
    riskTier: "soft",
    tags: ["skills", "catalog", "update"],
  },
  {
    id: "skills-post",
    category: "cognitive",
    method: "POST",
    path: "/api/skills",
    summary: "Create a new skill file",
    description: "Native agent route. Validates that category, filename, and content are present in the JSON body, then calls the MCP TOOL skills_create (not the REST endpoint). The underlying skills_crud.create_skill enforces filename ends with.md and category is one of foundation|workflows, refuses to overwrite an existing file, and writes the markdown under <skills_dir>/<category>/<filename>. The route returns the parsed tool result verbatim.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["category", "filename", "content"],
        properties: {
          category: {
            type: "string",
            enum: ["foundation", "workflows"]
          },
          filename: { type: "string", description: "Must end with .md" },
          content: { type: "string", description: "Markdown body of the skill" }
        }
      },
      example: {
        category: "workflows",
        filename: "phishing_triage.md",
        content: "---\nname: phishing_triage\ndisplayName: Phishing Triage\n---\n# Phishing Triage\n\nSteps to triage a reported phishing email..."
      }
    },
    responses: [
      {
        status: "200",
        description: "Tool returned. On success skills_crud.create_skill returns {success:true, message:'Created skill: <category>/<filename>', path:'<category>/<filename>'}. Tool-level FAILURES (filename not.md, invalid category, file already exists) also come back here as {success:false, error:...} with HTTP 200, because the agent route returns the parsed tool result without remapping status (the parallel MCP REST endpoint would have used 400, but this route does not call it).",
        example: {
          success: true,
          message: "Created skill: workflows/phishing_triage.md",
          path: "workflows/phishing_triage.md"
        }
      },
      {
        status: "400",
        description: "Agent-route validation: category, filename, or content missing from the body. Returns {success:false, error:'category, filename, and content are required.'} before calling the tool.",
        example: { success: false, error: "category, filename, and content are required." }
      },
      {
        status: "500",
        description: "Route-level failure (MCP unreachable, JSON parse error). Catch block returns {success:false, error:<message|'Unknown error'>} with status 500.",
        example: { success: false, error: "Unknown error" }
      }
    ],
    riskTier: "soft",
    tags: ["skills", "catalog", "create"],
  },
  {
    id: "skills-put",
    category: "cognitive",
    method: "PUT",
    path: "/api/skills",
    summary: "Update an existing skill file",
    description: "Native agent route. Validates that file_path and content are present in the JSON body, then calls the MCP TOOL skills_update (not the REST endpoint). The underlying skills_crud.update_skill writes a.md.bak backup plus a best-effort timestamped copy under.history/, overwrites the file, and records a skill_updated audit-log event. The route returns the parsed tool result. Note: file_path travels in the JSON body for PUT (unlike DELETE, which uses the query string).",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["file_path", "content"],
        properties: {
          file_path: {
            type: "string",
            description: "Relative path from skills dir, e.g. 'workflows/phishing_triage.md'"
          },
          content: { type: "string", description: "New full markdown content (overwrites)" }
        }
      },
      example: {
        file_path: "workflows/phishing_triage.md",
        content: "---\nname: phishing_triage\n---\n# Phishing Triage (revised)\n\nUpdated triage steps..."
      }
    },
    responses: [
      {
        status: "200",
        description: "Tool returned. On success skills_crud.update_skill returns {success:true, message:'Updated skill: <path>', backup:'<path>.md.bak', history:'.history/<file__path>.<ts>.md' OR null}. history is null when the best-effort.history write fails. Skill-not-found also comes back here as {success:false, error:'Skill not found: <path>'} with HTTP 200 (the route returns the parsed tool result without remapping status).",
        example: {
          success: true,
          message: "Updated skill: workflows/phishing_triage.md",
          backup: "workflows/phishing_triage.md.bak",
          history: ".history/workflows__phishing_triage.md.20260617T120000Z.md"
        }
      },
      {
        status: "400",
        description: "Agent-route validation: file_path or content missing from the body. Returns {success:false, error:'file_path and content are required.'} before calling the tool.",
        example: { success: false, error: "file_path and content are required." }
      },
      {
        status: "500",
        description: "Route-level failure (MCP unreachable, JSON parse error). Catch block returns {success:false, error:<message|'Unknown error'>} with status 500.",
        example: { success: false, error: "Unknown error" }
      }
    ],
    riskTier: "destructive",
    tags: ["skills", "catalog", "update"],
  },

  {
    id: "knowledge-search-post",
    category: "cognitive",
    method: "POST",
    path: "/api/agent/knowledge/search",
    summary: "Semantic search across all knowledge bases",
    description: "Cross-KB semantic search: runs brute-force cosine-similarity retrieval over every loaded knowledge base when no kb_name is given, or scopes to one KB when kb_name is set. Optional category, tags (AND semantics, non-string entries dropped), pagination (limit/offset), and a minimum-score floor. Distinct from the per-KB variant at /knowledge/{name}/search. Read-only.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["query"],
        properties: {
          query: {
            type: "string",
            description: "Search query; required, must be a non-empty string or the call returns 400."
          },
          kb_name: {
            type: "string",
            description: "Optional KB to scope to. Omit to search across all loaded KBs."
          },
          category: { type: "string", description: "Optional category filter." },
          tags: {
            type: "array",
            items: { type: "string" },
            description: "Optional tag filter (AND semantics, lowercased). Non-string entries are dropped; a non-list value is ignored."
          },
          limit: {
            type: "integer",
            description: "Max results. Default 5 (soft-capped at 100 in the store)."
          },
          offset: { type: "integer", description: "Pagination offset. Default 0." },
          min_score: { type: "number", description: "Minimum cosine-similarity floor. Default 0.0." }
        }
      },
      example: {
        query: "lateral movement detection via SMB",
        tags: ["att&ck"],
        limit: 5,
        min_score: 0.2
      }
    },
    responses: [
      {
        status: "200",
        description: "Ranked matches across the selected KB(s) as {results: [...], count: N}. Each result carries id, kb_name, doc_id, title, category, metadata, source_path, loaded_at, content, and score.",
        example: {
          results: [
            {
              id: "...",
              kb_name: "attack-enterprise",
              doc_id: "T1021.002",
              title: "SMB/Windows Admin Shares",
              category: "technique",
              metadata: {},
              source_path: "attack/T1021.002.md",
              loaded_at: "2026-06-10T00:00:00Z",
              content: "...",
              score: 0.83
            }
          ],
          count: 1
        }
      },
      {
        status: "400",
        description: "Invalid JSON body, body not a JSON object, or missing/empty 'query'.",
        example: { error: "'query' is required (non-empty string)" }
      },
      {
        status: "401",
        description: "Missing/invalid auth. Agent-side middleware rejects requests lacking a valid guardian_session cookie or API-key bearer; MCP-side require_bearer rejects a missing/wrong MCP_TOKEN."
      }
    ],
    tags: ["knowledge", "cognitive", "search"],
  },
  {
    id: "knowledge-by-name-tags",
    category: "cognitive",
    method: "GET",
    path: "/api/agent/knowledge/{name}/tags",
    summary: "List tag facets for one knowledge base",
    description: "Returns the distinct tags present in a single named knowledge base, each with a per-tag document count, ordered by count desc then tag asc (capped at 200). Drives the filter chips on the /knowledge/{name} browser view. Read-only.",
    pathParams: [
      {
        name: "name",
        type: "string",
        description: "The knowledge-base name. Must match a loaded KB (checked via _kb_exists_or_404) or the call returns 404 with the list of valid names.",
        required: true,
        example: "soc-investigation"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Tag facets for the KB as {tags: [{tag, count}]}, ordered by count desc then tag asc. Empty array if the KB has no tagged docs.",
        example: {
          tags: [
            { tag: "att&ck", count: 697 },
            { tag: "playbook", count: 12 }
          ]
        }
      },
      {
        status: "404",
        description: "No KB with that name is loaded; response is {error: \"unknown knowledge base '<name>'\", valid_kbs: [...sorted names]}.",
        example: {
          error: "unknown knowledge base 'ghost'",
          valid_kbs: ["atlas", "attack-enterprise", "soc-investigation"]
        }
      },
      {
        status: "401",
        description: "Missing/invalid auth. Agent-side middleware rejects requests lacking a valid guardian_session cookie or API-key bearer; MCP-side require_bearer rejects a missing/wrong MCP_TOKEN."
      }
    ],
    tags: ["knowledge", "cognitive"],
  },
  {
    id: "memory-post",
    category: "cognitive",
    method: "POST",
    path: "/api/agent/memory",
    summary: "Store a semantic memory entry",
    description: "Inserts or updates a memory row keyed by the (key, scope) natural key in memory.db, embedding the value text for later cosine-similarity recall. Re-storing the same key/scope updates value/meta/ttl and re-embeds, bumping updated_at (idempotent upsert). Writes set the audit actor to user:operator. Returns the persisted memory.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["key"],
        properties: {
          key: {
            type: "string",
            description: "Natural key within the scope. Required: an empty or non-string key makes the store raise ValueError -> 400. Defaults to '' at the HTTP layer (which then fails validation)."
          },
          value: {
            type: "string",
            description: "The memory content; embedded for semantic search. Must be a string if provided (non-string -> 400). Defaults to '' (empty string is accepted)."
          },
          scope: {
            type: "string",
            description: "Namespace for the entry (e.g. 'agent', 'session:<id>'). Defaults to 'agent'."
          },
          ttl_seconds: {
            type: "integer",
            description: "Optional time-to-live in seconds, measured from updated_at; expired rows are reaped at boot. Null/omitted = no TTL."
          },
          meta: { type: "object", description: "Arbitrary JSON metadata. Defaults to {}." }
        }
      },
      example: {
        key: "preferred-soc-shift",
        value: "Operator prefers night-shift triage windows (22:00-06:00 UTC).",
        scope: "agent",
        ttl_seconds: 2592000,
        meta: { source: "chat" }
      }
    },
    responses: [
      {
        status: "201",
        description: "Memory stored (created or updated). Returns {memory: <entry>} where the entry has id, key, value, scope, created_at, updated_at, ttl_seconds, meta.",
        example: {
          memory: {
            id: "a1b2c3d4-...",
            key: "preferred-soc-shift",
            value: "Operator prefers night-shift triage windows (22:00-06:00 UTC).",
            scope: "agent",
            created_at: "2026-06-17T09:00:00Z",
            updated_at: "2026-06-17T09:00:00Z",
            ttl_seconds: 2592000,
            meta: { source: "chat" }
          }
        }
      },
      {
        status: "400",
        description: "Invalid JSON body, body not a JSON object, empty/non-string key, or non-string value.",
        example: { error: "key must be a non-empty string" }
      },
      {
        status: "401",
        description: "Missing/invalid auth. Agent-side middleware rejects requests lacking a valid guardian_session cookie or API-key bearer; MCP-side require_bearer rejects a missing/wrong MCP_TOKEN."
      }
    ],
    riskTier: "soft",
    tags: ["memory", "cognitive"],
  },
  {
    id: "sessions-by-sessionId-delete",
    category: "cognitive",
    method: "DELETE",
    path: "/api/agent/sessions/{sessionId}",
    summary: "Hard-delete a session and its messages",
    description: "Permanently removes a session and all of its messages (messages CASCADE on the FK). There is no soft-delete or undo — to merely mark a session finished without deleting it, use POST /api/agent/sessions/{id}/end instead. The agent route proxies via the agent proxy to the MCP DELETE /api/v1/sessions/{session_id} handler (delete_session).",
    pathParams: [
      {
        name: "sessionId",
        type: "string",
        description: "ID of the session to delete.",
        required: true,
        example: "9f3a1c20-1b4e-4d2a-bc77-0a1f2e3d4c5b"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Session deleted. Returns {deleted:true, id:<sessionId>}.",
        example: { deleted: true, id: "9f3a1c20-1b4e-4d2a-bc77-0a1f2e3d4c5b" }
      },
      {
        status: "404",
        description: "Session not found (delete_session affected 0 rows).",
        example: { error: "not found" }
      },
      {
        status: "401",
        description: "Missing or invalid session cookie / API key — rejected by the agent middleware before reaching this route."
      },
      {
        status: "502",
        description: "the agent proxy upstream fetch threw (network error or 15s AbortSignal.timeout). Returns {error:<message>}.",
        example: { error: "proxy fetch failed" }
      },
      {
        status: "500",
        description: "Resolved MCP base URL was empty/invalid ({error:'bad MCP URL'}).",
        example: { error: "bad MCP URL" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent host.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "destructive",
    tags: ["sessions", "chat", "cognitive"],
  },
  {
    id: "sessions-by-sessionId-patch",
    category: "cognitive",
    method: "PATCH",
    path: "/api/agent/sessions/{sessionId}",
    summary: "Rename a session or update its metadata",
    description: "Partial update of a session. title sets the session title (pass an empty string to clear it; omit to leave unchanged); metadata is shallow-merged over the existing meta by default, or fully replaces it when replace_metadata is true. All fields are optional. The agent route proxies via the agent proxy to the MCP PATCH /api/v1/sessions/{session_id} handler (patch_session), which calls SqliteSessionStore.update_session.",
    pathParams: [
      {
        name: "sessionId",
        type: "string",
        description: "ID of the session to update.",
        required: true,
        example: "9f3a1c20-1b4e-4d2a-bc77-0a1f2e3d4c5b"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: [],
        properties: {
          title: {
            type: "string",
            description: "New session title. Omit to leave unchanged; pass an empty string to clear it."
          },
          metadata: {
            type: "object",
            description: "Metadata to shallow-merge over the session's existing meta (or replace it when replace_metadata is true)."
          },
          replace_metadata: {
            type: "boolean",
            description: "When true, the metadata object replaces the whole meta blob instead of shallow-merging. Defaults to false."
          }
        }
      },
      example: {
        title: "APT29 investigation — wrapped",
        metadata: { status: "closed" }
      }
    },
    responses: [
      {
        status: "200",
        description: "Session updated. Returns {session: {...}} — the full updated session (id, user, started_at, ended_at, title, meta, message_count).",
        example: {
          session: {
            id: "9f3a1c20-1b4e-4d2a-bc77-0a1f2e3d4c5b",
            user: "operator",
            started_at: "2026-06-17T13:00:00Z",
            ended_at: null,
            title: "APT29 investigation — wrapped",
            meta: { status: "closed" },
            message_count: 42
          }
        }
      },
      {
        status: "400",
        description: "Request body is not valid JSON ({error:'request body must be JSON'}) or is valid JSON but not an object ({error:'request body must be an object'}).",
        example: { error: "request body must be JSON" }
      },
      {
        status: "404",
        description: "Session not found (update_session returned None).",
        example: { error: "not found" }
      },
      {
        status: "401",
        description: "Missing or invalid session cookie / API key — rejected by the agent middleware before reaching this route."
      },
      {
        status: "502",
        description: "the agent proxy upstream fetch threw (network error or 15s AbortSignal.timeout). Returns {error:<message>}.",
        example: { error: "proxy fetch failed" }
      },
      {
        status: "500",
        description: "Resolved MCP base URL was empty/invalid ({error:'bad MCP URL'}).",
        example: { error: "bad MCP URL" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent host.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "soft",
    tags: ["sessions", "chat", "cognitive"],
  },
  {
    id: "chat-cli-post",
    category: "cognitive",
    method: "POST",
    path: "/api/chat/cli",
    summary: "Run a task via the Claude Code CLI (SSE)",
    description: "Native (non-proxied) route that shells out to the pre-installed Claude Code CLI (`claude -p --output-format json --permission-mode bypassPermissions`) as a child process and streams its output back as Server-Sent Events. This is a separate 'second model option' from POST /api/chat: it does NOT run the chat-route tool-call/approval/hook loop, and on this path Claude Code sees only its own built-in tools (filesystem, bash, web fetch), NOT Guardian's MCP tools. The credential is resolved via resolveAnthropicCliKey() with priority: ProviderStore anthropic instance secrets.cli_key, else env CLAUDE_CODE_OAUTH_TOKEN, else env ANTHROPIC_API_KEY. The resolved key is injected into the child as CLAUDE_CODE_OAUTH_TOKEN (with IS_SANDBOX=1); ANTHROPIC_API_KEY/ANTHROPIC_API_KEY_OLD are cleared from the child env so the OAuth path is forced. Each request runs with a 10-minute (600000 ms) timeout. Gated by middleware.ts (matcher /api/chat/:path*) — accepts a guardian_session cookie OR an `agent:write`-scoped guardian_ak_* API key (not a credential route, so API keys are permitted).",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["prompt"],
        properties: {
          prompt: {
            type: "string",
            description: "The task text passed to the Claude Code CLI as the final positional arg. Trimmed server-side; must be non-empty after trim or the route returns 400."
          },
          workDir: {
            type: "string",
            description: "Optional cwd for the CLI child process. Defaults to /tmp when omitted (cli-wrapper.ts: config.workDir ?? '/tmp')."
          }
        }
      },
      example: {
        prompt: "Summarize the open incidents and draft a status update.",
        workDir: "/tmp/cli-run-1"
      }
    },
    responses: [
      {
        status: "200",
        description: "SSE stream (Content-Type: text/event-stream; Cache-Control: no-cache, no-transform; X-Accel-Buffering: no). Emits `meta` ({provider:'claude-code', started_at}) first, then per CLI stdout line either `output` (the parsed JSON object) or `output_raw` ({line}) when the line isn't valid JSON, then a terminal `done` ({exit_code, duration_ms, timed_out, stderr_tail}). A thrown error inside the stream emits `error` ({message}) before the stream closes."
      },
      {
        status: "400",
        description: "Returned as JSON (not SSE) before the stream opens for: invalid JSON body ({error:'invalid JSON body'}); missing/empty prompt after trim ({error:'prompt is required'}); or no Anthropic credential resolvable anywhere (ProviderStore cli_key + CLAUDE_CODE_OAUTH_TOKEN + ANTHROPIC_API_KEY all empty) — the error message instructs the operator to set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN in /opt/guardian/.env or configure via /providers.",
        example: { error: "prompt is required" }
      },
      {
        status: "401",
        description: "Rejected by middleware.ts before the handler runs: no guardian_session cookie ({error:'unauthenticated', code:'no_session_cookie'}), an invalid/expired session, or an invalid guardian_ak_* API key. Body is JSON with an unauthenticated error + a code field naming the cause.",
        example: { error: "unauthenticated", code: "no_session_cookie" }
      }
    ],
    riskTier: "soft",
    tags: ["chat", "cli", "claude-code", "sse", "provider"],
  },
];

// ─────────────────────────────────────────────────────────────────
// CONFIGURATION — settings, personality, instances, providers, manifest
// ─────────────────────────────────────────────────────────────────

const CONFIGURATION: ApiEndpoint[] = [
  {
    id: "settings-get",
    category: "configuration",
    method: "GET",
    path: "/api/agent/settings",
    summary: "Snapshot of runtime settings",
    description:
      "Returns {defaults, overridable, effective, overrides}. `defaults` come " +
      "from manifest.settings.defaults; `overrides` are operator-set values " +
      "in `<data_root>/settings.db`; `effective` is the merged view.",
    responses: [
      {
        status: "200",
        description: "Settings snapshot.",
        example: {
          defaults: { geminiModel: "gemini-3.1-pro-preview", defaultScenario: "dark_secrets" },
          overridable: ["geminiModel", "defaultScenario", "defaultLogFormat"],
          effective: { geminiModel: "gemini-3.1-pro-preview" },
          overrides: [],
        },
      },
    ],
  },
  {
    id: "settings-update",
    category: "configuration",
    method: "PUT",
    path: "/api/agent/settings",
    summary: "Bulk set / clear runtime overrides",
    description:
      "Set or clear keys in one call. Keys not in manifest.settings.overridable[] " +
      "are rejected with a per-key reason in the response.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        properties: {
          updates: { type: "object", description: "Key → value pairs to set." },
          clear: { type: "array", items: { type: "string" }, description: "Keys to revert." },
          actor: { type: "string", description: "Optional audit actor." },
        },
      },
      example: { updates: { geminiModel: "gemini-2.5-flash" }, clear: [], actor: "user:operator" },
    },
    responses: [
      { status: "200", description: "{ applied, cleared, rejected }." },
      { status: "400", description: "Malformed body." },
    ],
    riskTier: "soft",
  },
  {
    id: "personality-get",
    category: "configuration",
    method: "GET",
    path: "/api/agent/personality",
    summary: "Get the agent's persona document",
    description:
      "Single-row persona — operator-defined markdown plus operational settings (action policy, model defaults, notifications). Stored in MCP-side personality.db; the agent's chat-route system instruction reads `personalityMd` into the prompt and uses `actionPolicy` for safety classification.",
    responses: [
      {
        status: "200",
        description: "Persona document.",
        example: {
          personality: {
            personalityMd: "# Guardian Personality\n\n- Reply concisely.\n- Cite case IDs when referencing investigations.\n",
            actionPolicy: {
              askWhenUnsure: true,
              confirmLocalActions: "approve-card",
              confirmExternalActions: "soft",
            },
            defaultModel: "gemini-3.1-pro-preview",
          },
          updated_at: "2026-05-06T10:00:00Z",
          updated_by: "user:operator",
          version: 3,
        },
      },
    ],
  },
  {
    id: "personality-put",
    category: "configuration",
    method: "PUT",
    path: "/api/agent/personality",
    summary: "Replace the persona document",
    description:
      "Last-write-wins. Bumps version; previous version is preserved in personality_history. The agent prefers `personality_patch` for partial updates (atomic merge) — direct PUT requires sending the full blob.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["personality"],
        properties: {
          personality: { type: "object", description: "Full persona blob." },
          actor: { type: "string", description: "Audit actor." },
        },
      },
      example: {
        personality: {
          personalityMd: "# Guardian Personality\n\n- Reply in three bullets when possible.\n",
        },
        actor: "user:operator",
      },
    },
    responses: [
      { status: "200", description: "Updated row with new version." },
      { status: "400", description: "Body missing `personality` object." },
    ],
    riskTier: "soft",
  },
  {
    id: "personality-history",
    category: "configuration",
    method: "GET",
    path: "/api/agent/personality/history",
    summary: "List recent persona versions",
    description:
      "Returns recent personality versions newest-first as {versions, count} so the settings UI can show edit history / diffs. Each version carries the persona blob plus updated_at / updated_by / version. Proxies to the embedded MCP at GET /api/v1/personality/history.",
    queryParams: [
      {
        name: "limit",
        type: "integer",
        description: "Max versions to return (default 10).",
        example: "10",
      },
    ],
    responses: [
      { status: "200", description: "{versions, count} — versions newest-first." },
      {
        status: "401",
        description:
          "Caller not authenticated — Next.js middleware rejected the request.",
      },
    ],
  },
  {
    id: "instances-list",
    category: "configuration",
    method: "GET",
    path: "/api/agent/instances",
    summary: "List connector instances",
    description:
      "Connector config blobs (XSIAM, Cortex XDR, web, …). Secret values NEVER returned — only secret_refs paths.",
    queryParams: [
      { name: "connector_id", type: "string", description: "Filter to one connector id, e.g. xsiam | cortex-xdr | web.", example: "xsiam" },
    ],
    responses: [{ status: "200", description: "Instance rows." }],
  },
  {
    id: "providers-list",
    category: "configuration",
    method: "GET",
    path: "/api/agent/providers",
    summary: "List materialized provider instances",
    description: "Secrets redacted (paths only). Used by /providers admin page.",
    responses: [{ status: "200", description: "Provider rows." }],
  },
  {
    id: "providers-config",
    category: "configuration",
    method: "PUT",
    path: "/api/agent/providers/config",
    summary: "Write LLM provider credentials (Vertex + Anthropic)",
    description: "Persists provider credentials supplied on the /providers settings page directly to the SecretStore-backed ProviderStore (no setup.json). Native route: reads body.value, builds per-provider patches for Vertex (config project_id/region + secret serviceAccountJson) and Anthropic (secrets api_key/cli_key), then upserts a primary-vertex and/or primary-anthropic instance via the MCP provider CRUD (PUT /api/v1/providers/{id} when the instance exists, POST /api/v1/providers otherwise), busts the per-provider chat-handler credential caches, and aggregates both results. The \"***\" sentinel (or empty string) for a secret field means \"leave the stored secret unchanged\" and that field is skipped. Although PROVIDER_KEYS also lists openai/ollama fields, the PUT handler only processes the five vertex+anthropic fields. Writes secrets, so credential-tier.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["value"],
        properties: {
          value: {
            type: "object",
            properties: {
              vertexProjectId: {
                type: "string",
                description: "GCP project id -> primary-vertex config.project_id (trimmed; blank skipped)"
              },
              vertexLocation: {
                type: "string",
                description: "Vertex region -> primary-vertex config.region (trimmed; blank skipped)"
              },
              vertexServiceAccountJson: {
                type: "string",
                description: "GCP service-account key JSON -> primary-vertex secrets.serviceAccountJson; \"***\" or empty leaves it unchanged"
              },
              anthropicApiKey: {
                type: "string",
                description: "Anthropic API key -> primary-anthropic secrets.api_key; \"***\" or empty leaves it unchanged"
              },
              anthropicCliKey: {
                type: "string",
                description: "Claude Code CLI key (Pro/Max device-code OAuth) -> primary-anthropic secrets.cli_key; \"***\" or empty leaves it unchanged"
              }
            }
          }
        }
      },
      example: {
        value: {
          vertexProjectId: "cortex-gcp-labs",
          vertexLocation: "us-central1",
          vertexServiceAccountJson: "{\"type\":\"service_account\",\"project_id\":\"cortex-gcp-labs\",\"private_key\":\"-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n\",\"client_email\":\"guardian-sa@cortex-gcp-labs.iam.gserviceaccount.com\"}",
          anthropicApiKey: "***",
          anthropicCliKey: "sk-ant-cli-..."
        }
      }
    },
    responses: [
      {
        status: "200",
        description: "All requested provider upserts succeeded. Body carries per-provider sync results under mcp_sync.{vertex,anthropic}, each with success plus action (create|update|skipped) and updated/reason/error as applicable. A request supplying no actionable fields short-circuits BEFORE the upserts and returns a different mcp_sync shape: {ok:true, mcp_sync:{success:true, skipped:true, reason:\"no-op (no fields to update)\"}}.",
        example: {
          ok: true,
          mcp_sync: {
            vertex: { success: true, action: "update", updated: "a1b2c3d4" },
            anthropic: { success: true, action: "create", updated: "e5f6a7b8" }
          }
        }
      },
      {
        status: "400",
        description: "At least one provider upsert failed (e.g. first-time Vertex create missing project_id/region/serviceAccountJson, first-time Anthropic create with neither api_key nor cli_key, or an MCP create/update error). The body still carries both per-provider results under mcp_sync.{vertex,anthropic} so the form can surface which provider failed.",
        example: {
          ok: false,
          mcp_sync: {
            vertex: {
              success: false,
              error: "Vertex provider is not yet configured. Project ID, region, and service account JSON are all required to create the primary-vertex instance for the first time."
            },
            anthropic: { success: true, action: "skipped", reason: "no-op (no anthropic fields supplied)" }
          }
        }
      },
      {
        status: "503",
        description: "MCP could not be resolved: resolveMcp() returned its error NextResponse, which this route returns directly. 503 {\"error\":\"MCP_TOKEN not configured\"} when no bearer token is available; resolveMcp also returns 500 {\"error\":\"bad MCP URL\"} when the MCP base URL cannot be derived. (There is no 401 path — the earlier 401 claim was incorrect.)",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "credential",
    tags: ["providers", "vertex", "anthropic", "credentials"],
  },
  {
    id: "models-list",
    category: "configuration",
    method: "GET",
    path: "/api/agent/models",
    summary: "List available models from configured providers",
    description: "Aggregates the model catalog from every materialized provider instance.",
    responses: [{ status: "200", description: "Model list." }],
  },
  {
    id: "manifest-get",
    category: "configuration",
    method: "GET",
    path: "/api/agent/manifest",
    summary: "Read the bundle manifest",
    description:
      "Read-only by spec — bundle is immutable at runtime. The agent introspects its own contract via this endpoint (which built-in tools, which require approval, etc).",
    responses: [
      {
        status: "200",
        description: "Manifest excerpt + runtime info.",
        example: {
          name: "guardian-soc-agent",
          version: "0.2.0",
          runtime: { mode: "standalone-or-orchestrated", model: "gemini-3.1-pro-preview", setupRequired: false },
        },
      },
    ],
  },
  {
    id: "backup",
    category: "configuration",
    method: "GET",
    path: "/api/agent/backup",
    summary: "Download a full-config backup zip",
    description: "Streams a downloadable zip snapshot of every operator-owned data surface so the deployment can be restored (potentially on a different host) via POST /api/agent/restore. The handler is native (not a thin MCP proxy): it resolves the embedded MCP, then makes multiple bearer-authed reads and assembles a JSZip in-memory. Sections written to the zip root: manifest.json, personality.json (from /api/v1/personality), instances.json (with CLEARTEXT secrets via /api/v1/instances?include_secrets=true), memory.json (raw embedding fields stripped per-entry), jobs.json (runtime jobs only — filtered to source===\"runtime\"; manifest jobs reseed at boot), skills/ (MD tree read via the skills_list_all + skills_read MCP tools, preserving category subdir), knowledge/<kb>/<id>.md (KB doc content read via /api/v1/kbs/*), and data_sources/ (user/<id>.json per origin=user upload plus installed.json capturing the install set as pack/rule/dataset 3-tuples). The response is application/zip with Content-Disposition attachment filename guardian-backup-<timestamp>.zip, Cache-Control no-store, and an X-Guardian-Backup-Schema: 1 header. Auth is enforced upstream by middleware.ts (guardian_session cookie); the backup contains cleartext secrets so anonymous callers must never reach it.",
    responses: [
      {
        status: "200",
        description: "Zip bundle returned as a new NextResponse(arraybuffer) with Content-Type application/zip, Content-Disposition attachment (filename guardian-backup-<timestamp>.zip where timestamp is ISO sliced to seconds with:/. replaced by -), Cache-Control no-store, and X-Guardian-Backup-Schema: 1. Body is the binary zip; the embedded manifest.json carries schema_version (1), guardian_version, created_at, sections[], section_counts, a cleartext-secrets warning, restore_order, restore_notes, and (only when any section read failed) backup_warnings.",
        example: {
          schema_version: 1,
          guardian_version: "0.17.37",
          created_at: "2026-06-17T12:00:00.000Z",
          sections: [
            "personality",
            "instances",
            "memory",
            "jobs",
            "skills",
            "knowledge",
            "data_sources"
          ],
          section_counts: {
            personality: 1,
            instances: 2,
            memory: 14,
            jobs: 3,
            skills: 9,
            knowledge: 924,
            data_sources_user: 1,
            data_sources_installed: 5
          },
          warning: "This zip contains cleartext secrets (connector API keys, webhook keys, etc). Treat as sensitive. Do not commit to version control or share over unencrypted channels.",
          restore_order: [
            "personality",
            "instances",
            "skills",
            "memory",
            "knowledge",
            "data_sources",
            "jobs"
          ]
        }
      },
      {
        status: "500",
        description: "Backup failed (e.g. JSZip generateAsync error or another throw in the try block). Returns JSON {error} where error is the thrown Error message or the literal \"backup failed\". Individual section read failures do NOT 500 — each section is wrapped in its own try/catch, recorded in section_counts as 0 and appended to the manifest's backup_warnings instead.",
        example: { error: "backup failed" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (resolved from runtime config or process.env). Returned by _resolveMcp() before any section is read, so the embedded MCP is never contacted.",
        example: { error: "MCP_TOKEN not configured" }
      },
      {
        status: "401",
        description: "No valid guardian_session cookie. Enforced by middleware.ts upstream of this handler (the route handler itself does no cookie check; its header comment documents this)."
      }
    ],
    riskTier: "credential",
    tags: ["backup", "config-export", "secrets"],
  },
  {
    id: "chat-post",
    category: "configuration",
    method: "POST",
    path: "/api/chat",
    summary: "Start or continue a chat session (SSE streaming response)",
    description:
      "The agent turn endpoint. Body: { message, session_id? } (omit session_id to start a new session). Responds with a Server-Sent Events stream whose `event:` types include meta (session id), model, thinking, text_delta (assistant text), tool_call + tool_result (each agent tool invocation), turn_cost, and done. Bearer-auth with a GUARDIAN_API_KEY works (agent:write scope); the same hook lifecycle (PreToolUse/PostToolUse) fires as for interactive chat.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["message"],
        properties: {
          message: { type: "string", description: "The user turn." },
          session_id: { type: "string", description: "Omit to start a new session." },
        },
      },
      example: { message: "List active incidents on the v6 tenant", session_id: "<existing-session-id>" },
    },
    responses: [{ status: "200", description: "text/event-stream — meta · model · thinking · text_delta · tool_call · tool_result · turn_cost · done." }],
  },
  {
    id: "connectors",
    category: "configuration",
    method: "GET",
    path: "/api/agent/connectors",
    summary: "List the connector registry with state",
    description: "Returns every connector known to Guardian by merging manifest-declared connectors (manifest.toolConnectors[].id) with any persisted state rows from the SqliteConnectorStateStore. Manifest connectors never probed appear as state 'pending'; state rows not in the manifest appear with in_manifest=false. Each row carries a 'configured' flag (true when at least one instance is configured for that connector, derived from instance_store.configured_connector_ids()) plus 'in_manifest'. The agent route proxies GET to the MCP at /api/v1/connectors with a bearer token; it sends no body and no query params and passes the MCP status through unchanged.",
    responses: [
      {
        status: "200",
        description: "Registry list with per-connector state. Shape: {connectors: [...], count: N}. Each row: connector_id, state, last_transition_at, last_probed_at, last_error, consecutive_failures, configured, in_manifest.",
        example: {
          connectors: [
            {
              connector_id: "xsiam",
              state: "connected",
              last_transition_at: "2026-06-17T09:12:00Z",
              last_probed_at: "2026-06-17T09:12:00Z",
              last_error: null,
              consecutive_failures: 0,
              configured: true,
              in_manifest: true
            },
            {
              connector_id: "cortex-docs",
              state: "pending",
              last_transition_at: null,
              last_probed_at: null,
              last_error: null,
              consecutive_failures: 0,
              configured: false,
              in_manifest: true
            }
          ],
          count: 2
        }
      },
      {
        status: "401",
        description: "Bearer auth to the MCP failed (require_bearer rejected the token). Status is passed through from the MCP by the agent proxy."
      },
      {
        status: "500",
        description: "Agent proxy could not derive a valid MCP base URL from the configured MCP_URL. Returned as {error: \"bad MCP URL\"}.",
        example: { error: "bad MCP URL" }
      },
      {
        status: "502",
        description: "MCP unreachable — the agent proxy's upstream fetch threw. Returned as {error: \"MCP unreachable: <msg>\"}.",
        example: { error: "MCP unreachable: fetch failed" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured in the effective runtime config — the agent proxy cannot authenticate to the embedded MCP. Returned as {error: \"MCP_TOKEN not configured\"}.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    tags: ["connectors", "registry", "state"],
  },
  {
    id: "connectors-by-id-by-action-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/connectors/{id}/{action}",
    summary: "Connector lifecycle action (enable / disable / probe)",
    description:
      "Drives a connector's lifecycle by action. {action} is one of: enable (mark active, pending re-probe), disable (deregister its tools), or probe (force a health-check now). Toggling state re-catalogs the agent's tools. Not a create — instances are created via POST /api/agent/instances.",
    pathParams: [
      { name: "id", type: "string", description: "The connector id (e.g. xsoar, xsiam).", required: true },
      { name: "action", type: "string", description: "enable | disable | probe", required: true, enum: ["enable", "disable", "probe"] },
    ],
    responses: [{ status: "200", description: "Updated connector state." }],
  },
  {
    id: "instances-by-id",
    category: "configuration",
    method: "GET",
    path: "/api/agent/instances/{id}",
    summary: "Get a single connector instance",
    description:
      "Fetches ONE connector instance by id — its connector_id, name, config (with secrets redacted as ***), enabled flag, and container/health state. To LIST all instances, GET /api/agent/instances.",
    pathParams: [
      { name: "id", type: "string", description: "The instance UUID.", required: true },
    ],
    responses: [{ status: "200", description: "The instance record (secrets redacted)." }],
  },
  {
    id: "instances-by-id-delete",
    category: "configuration",
    method: "DELETE",
    path: "/api/agent/instances/{id}",
    summary: "Delete a connector instance",
    description: "Removes the instance row from instances.db. The agent route forwards verbatim (no body, bearer attached server-side) via the agent proxy to the MCP custom_route DELETE /api/v1/instances/{instance_id}. In delete_instance the handler first looks up the row; if it resolves and the connector's resolved runtimeMapping.style is 'container' (the default when unset), guardian-updater is called to STOP the per-instance container BEFORE store.delete runs, so no orphaned container or dangling proxy callable is left. On a successful row delete the instance's SecretStore entries are also purged (store.delete -> _secret_store.delete_under). Response carries requires_mcp_restart=true so the UI knows the tool catalog won't re-advertise until the MCP reloads.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The instance UUID (Instance.id) to delete. Forwarded URL-encoded to /api/v1/instances/{instance_id}.",
        required: true,
        example: "3f1c2a9e-4d77-41b0-9a2e-7b1c0d5e8f22"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Instance deleted. Returns deleted=true, the id, and requires_mcp_restart=true.",
        example: { deleted: true, id: "3f1c2a9e-4d77-41b0-9a2e-7b1c0d5e8f22", requires_mcp_restart: true }
      },
      {
        status: "404",
        description: "No instance with that id exists (store.delete returned False).",
        example: { error: "not found" }
      },
      {
        status: "401",
        description: "Missing or malformed Authorization header on the loopback proxy hop (require_bearer). Not normally reachable from the UI since the agent proxy attaches the MCP_TOKEN bearer server-side.",
        example: { error: "missing or malformed Authorization header" }
      }
    ],
    riskTier: "destructive",
    tags: ["instances", "connectors", "crud"],
  },
  {
    id: "instances-by-id-patch",
    category: "configuration",
    method: "PATCH",
    path: "/api/agent/instances/{id}",
    summary: "Partially update a connector instance",
    description: "Partial update of one connector instance. The agent route forwards the raw body via the agent proxy to the MCP PATCH /api/v1/instances/{instance_id}. Honored body fields (all optional; unrecognized keys ignored): enabled (bool toggle — on change the handler calls reload_tools_now() so the agent tool catalog reflects the new enabled set), name (non-empty string rename), config (object — replaces the config blob), secrets (object — rotates secret slots; a per-slot \"***\" sentinel leaves that slot unchanged), and disabled_tools (array of strings — per-instance tool opt-out, applied via store.update_disabled_tools with its own instance_tool_toggle audit event). When config or secrets change on an ENABLED container-style instance, the running container is recreated (via guardian-updater _updater_start) so it re-reads the new config; that outcome is echoed as container_restarted. Because the body can carry secret values (rotation) this sits on the credential side of the guardrail — REST/UI-only, never an agent MCP tool.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The instance UUID (Instance.id) to update.",
        required: true,
        example: "3f1c2a9e-4d77-41b0-9a2e-7b1c0d5e8f22"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: [],
        properties: {
          enabled: { type: "boolean" },
          name: { type: "string" },
          config: { type: "object" },
          secrets: { type: "object" },
          disabled_tools: {
            type: "array",
            items: { type: "string" }
          }
        }
      },
      example: {
        enabled: true,
        name: "xsoar-prod",
        config: { base_url: "https://xsoar.example.com" },
        secrets: { api_key: "***" },
        disabled_tools: ["xsoar.delete_incident"]
      }
    },
    responses: [
      {
        status: "200",
        description: "Instance updated. Returns the redacted serialized instance (secrets masked as \"***\", state sourced from connector_state) plus container_restarted — the {started,container_url,error} outcome when a container was recreated, otherwise null.",
        example: {
          instance: {
            id: "3f1c2a9e-4d77-41b0-9a2e-7b1c0d5e8f22",
            connector_id: "xsoar",
            name: "xsoar-prod",
            config: { base_url: "https://xsoar.example.com" },
            secrets: { api_key: "***" },
            created_at: "2026-06-15T10:00:00Z",
            enabled: true,
            state: "connected",
            container_url: "http://guardian-connector-xsoar-xsoar_prod:9000",
            disabled_tools: ["xsoar.delete_incident"]
          },
          container_restarted: null
        }
      },
      {
        status: "400",
        description: "Invalid JSON body, body not an object, a field failed type validation (enabled not bool, name empty/non-string, config/secrets not objects, disabled_tools not an array or contains non-strings), or a non-conflict ValueError from store.update.",
        example: { error: "enabled must be a boolean" }
      },
      {
        status: "404",
        description: "No instance with that id exists (store.get returned None).",
        example: { error: "not found" }
      },
      {
        status: "401",
        description: "Missing or malformed Authorization header on the loopback proxy hop. Not normally reachable from the UI (proxy attaches the bearer server-side).",
        example: { error: "missing or malformed Authorization header" }
      }
    ],
    riskTier: "credential",
    tags: ["instances", "connectors", "crud", "secrets"],
  },
  {
    id: "instances-by-id-test-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/instances/{id}/test",
    summary: "Test a connector instance's connectivity",
    description:
      "Runs the connector's health-check probe for an EXISTING instance against its configured tenant — it does NOT create an instance. Returns a reachability result (clean success or a structured error: auth failure, bad host, timeout). Backs the Test button on /connectors and confirms credentials after a create or rotate.",
    pathParams: [
      { name: "id", type: "string", description: "The instance UUID.", required: true },
    ],
    responses: [{ status: "200", description: "Probe result, e.g. { ok, reachable, detail? }." }],
  },
  {
    id: "internal-fire-hook-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/internal/fire-hook",
    summary: "Internal server-to-server hook dispatch bridge",
    description: "INTERNAL loopback-only endpoint (not proxied to the MCP, not reachable from the operator browser). MCP-side code paths that need to run the TypeScript-side hook dispatcher POST {event, payload} here; the agent runs dispatchHooks(event, payload) and returns the aggregate decision plus the per-hook decisions. Authenticated by an MCP_TOKEN bearer that is independent of the NextAuth session gating the rest of /api/agent/*. The 'internal' path name is the contract that lets a future ingress layer filter the loopback surface from the operator-facing one.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["event", "payload"],
        properties: {
          event: {
            type: "string",
            description: "Must be one of HOOK_EVENTS, else 400.",
            enum: [
              "PreToolUse",
              "PostToolUse",
              "PostToolUseFailure",
              "UserPromptSubmit",
              "PreCompact",
              "PostCompact",
              "RunStart",
              "RunEnd",
              "SubagentStart",
              "SubagentEnd",
              "Notification",
              "PermissionRequest"
            ]
          },
          payload: {
            type: "object",
            description: "HookPayload object passed to each matched hook handler. Must be a non-null object, else 400."
          }
        }
      },
      example: {
        event: "Notification",
        payload: { title: "Investigation complete", body: "Case 1042 triaged", severity: "info" }
      }
    },
    responses: [
      {
        status: "200",
        description: "Dispatcher ran. Returns {dispatched:true, decision, decisions} where decision is 'allow'|'deny'|'ask' or undefined (omitted) when no hooks fired, and decisions is the per-hook audit array.",
        example: {
          dispatched: true,
          decision: "allow",
          decisions: [
            { hookId: "a1b2", name: "block-prod-delete", decision: "allow", durationMs: 12 }
          ]
        }
      },
      {
        status: "400",
        description: "Body not JSON ({error:'body must be JSON'}), event missing/not in HOOK_EVENTS, or payload not an object."
      },
      {
        status: "401",
        description: "Missing or wrong MCP_TOKEN bearer (or MCP_TOKEN not configured) — returns {error:'unauthorized'}."
      },
      {
        status: "500",
        description: "dispatchHooks threw — returns {error:'dispatch failed', detail}."
      }
    ],
    riskTier: "soft",
    tags: ["hooks", "internal", "dispatch"],
  },
  {
    id: "marketplace-by-connectorId-download",
    category: "configuration",
    method: "GET",
    path: "/api/agent/marketplace/{connectorId}/download",
    summary: "Download a connector's connector.yaml",
    description: "Streams the full connector.yaml for a bundle or user connector back to the browser with save-as headers. The agent route forwards to the MCP's GET /api/v1/marketplace/{id}/download, which resolves the source file via the manifest (bundle path) then /app/data/user_connectors/<id>/connector.yaml, audits a connector_downloaded event, and returns the raw YAML as application/yaml with a Content-Disposition attachment header. The agent route forwards the MCP's exact status code (200/404/500) plus the Content-Type and Content-Disposition headers verbatim.",
    pathParams: [
      {
        name: "connectorId",
        type: "string",
        description: "Connector id to download (e.g. xsoar, xsiam, web, cortex-docs, or a user-uploaded connector id).",
        required: true,
        example: "xsoar"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Raw connector.yaml body. Content-Type: application/yaml (from MCP PlainTextResponse); Content-Disposition: attachment; filename=\"<connectorId>.yaml\"."
      },
      {
        status: "404",
        description: "Connector not found in the bundle manifest or user_connectors directory (MCP returns {error}, agent forwards the 404 status).",
        example: { error: "connector 'foo' not found" }
      },
      {
        status: "500",
        description: "Source file present in catalogue but could not be read from disk (MCP OSError → 500 {error}, forwarded by the agent route).",
        example: { error: "could not read /app/data/user_connectors/foo/connector.yaml: ..." }
      },
      {
        status: "401",
        description: "Caller not authenticated to the agent surface — enforced by middleware.ts (session cookie or API-key bearer) on the /api/agent/** prefix, not by the route handler."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (resolveMcp guard, before any upstream call).",
        example: { error: "MCP_TOKEN not configured" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable — the agent route's fetch threw.",
        example: { error: "MCP unreachable: ..." }
      }
    ],
    tags: ["marketplace", "connectors", "catalog", "download"],
  },
  {
    id: "marketplace-by-connectorId-uninstall-delete",
    category: "configuration",
    method: "DELETE",
    path: "/api/agent/marketplace/{connectorId}/uninstall",
    summary: "Uninstall a connector (remove install marker)",
    description: "Removes the marketplace install marker for a connector. The DELETE agent route forwards (as an empty-body POST) to the MCP's /api/v1/marketplace/{id}/uninstall, which refuses with 409 if any instances still exist for the connector (operator must delete instances first). It does NOT remove the connector from the catalogue — bundle connectors stay listed and user connectors persist on disk until the separate DELETE /api/v1/marketplace/{id} call. Catalog-side operation; touches no secret.",
    pathParams: [
      {
        name: "connectorId",
        type: "string",
        description: "Connector id whose install marker should be removed.",
        required: true,
        example: "web"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Uninstalled. Agent wraps the MCP result as { connector_id, uninstalled: true, upstream }, where upstream is the MCP body { ok, removed }.",
        example: {
          connector_id: "web",
          uninstalled: true,
          upstream: { ok: true, removed: true }
        }
      },
      {
        status: "409",
        description: "Connector still has instances; uninstall refused. The MCP body (carrying error + instances_count) is passed through verbatim with the 409 status.",
        example: {
          error: "connector 'web' has 2 instance(s); delete instances before uninstalling",
          instances_count: 2
        }
      },
      {
        status: "404",
        description: "Connector is not installed (no install marker present); MCP body forwarded verbatim with the 404 status.",
        example: { error: "connector 'web' is not installed" }
      },
      {
        status: "400",
        description: "connectorId path segment missing/empty (agent-side guard before any upstream call).",
        example: { error: "connectorId path segment is required" }
      },
      {
        status: "401",
        description: "Caller not authenticated to the agent surface (middleware.ts on /api/agent/**)."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (resolveMcp guard).",
        example: { error: "MCP_TOKEN not configured" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable — agent route fetch threw.",
        example: { error: "MCP unreachable", detail: "..." }
      }
    ],
    riskTier: "soft",
    tags: ["marketplace", "connectors", "catalog", "uninstall"],
  },
  {
    id: "marketplace-by-connectorId-delete",
    category: "configuration",
    method: "DELETE",
    path: "/api/agent/marketplace/{connectorId}",
    summary: "Delete a user-uploaded connector entirely (#CONN-F3)",
    description: "Fully removes a USER-uploaded connector — its install marker AND its on-disk definition (the connector.yaml under /app/data/user_connectors/<id>). The agent route forwards to the MCP's DELETE /api/v1/marketplace/{id}. Distinct from /uninstall (which only drops the install marker, leaving the connector listed): this is the irreversible 'remove it from the product' action behind the Delete button on the Marketplace tab's connector detail panel. Bundle connectors are image-baked and rejected with 403 (cannot_delete_bundle). Refused with 409 (has_instances) when any instance still exists — delete instances first. Catalog-side operation; touches no secret.",
    pathParams: [
      {
        name: "connectorId",
        type: "string",
        description: "Connector id to delete. Must be a user-uploaded connector (origin=user).",
        required: true,
        example: "my-edr"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Deleted. The MCP body { ok, deleted } is forwarded.",
        example: { ok: true, deleted: "my-edr" }
      },
      {
        status: "403",
        description: "Connector is a bundle connector (image-baked); deletion refused. MCP body forwarded verbatim.",
        example: { error: "cannot_delete_bundle", detail: "bundle connectors are image-baked and cannot be deleted at runtime" }
      },
      {
        status: "409",
        description: "Connector still has instances; deletion refused. MCP body (carrying the has_instances code + count) passed through verbatim.",
        example: { error: "has_instances", detail: "connector 'my-edr' has 1 instance(s); delete instances before deleting the connector" }
      },
      {
        status: "404",
        description: "No such connector on disk; MCP body forwarded verbatim.",
        example: { error: "not_found" }
      },
      {
        status: "401",
        description: "Caller not authenticated to the agent surface (middleware.ts on /api/agent/**)."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (resolveMcp guard).",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "destructive",
    tags: ["marketplace", "connectors", "catalog", "delete", "user-connector"],
  },
  {
    id: "marketplace-connectors",
    category: "configuration",
    method: "GET",
    path: "/api/marketplace/connectors",
    summary: "List marketplace connector cards",
    description: "Native (non-proxy) route the connectors page reads to render marketplace cards. Serves a hand-curated array of connector specs (xsoar, xsiam, web, cortex-docs) and overlays live metadata read directly from each connector.yaml on disk: it replaces tools[]/toolCount and version, and appends any config field the hardcoded entry doesn't already name. If a connector.yaml can't be read or parsed it silently keeps the hardcoded entry. Returns a bare JSON array (no envelope). Intentionally excluded from the auth middleware so pre-login pages can render the card list.",
    responses: [
      {
        status: "200",
        description: "Bare array of marketplace connector card objects. Each has id, name, type, version, publisher, description, longDescription, category, tags, icon/iconColor/iconBg, toolCount, installs, installCount, status, reliability, authType, tools[], config[], versions[], setupGuide, dockerImage, runtime, sdkLanguage, sdkPackage, ingestion, topAgents. toolCount + tools[] + version are overlaid live from connector.yaml when available; live config fields are appended (curated fields keep their hardcoded display/type).",
        example: [
          {
            id: "xsoar",
            name: "Cortex XSOAR",
            version: "0.1.0",
            toolCount: 13,
            status: "installed",
            category: "Security",
            tags: ["xsoar", "cortex", "soar", "cases", "incident-response"],
            tools: [],
            config: [
              {
                display: "Version",
                name: "version",
                type: "select",
                required: true,
                options: ["v6", "v8"],
                defaultValue: "v8"
              }
            ]
          }
        ]
      }
    ],
    tags: ["marketplace", "connectors", "catalog", "cards"],
  },
  {
    id: "marketplace-connectors-by-id",
    category: "configuration",
    method: "GET",
    path: "/api/marketplace/connectors/{id}",
    summary: "Get one marketplace connector card",
    description: "Native route backing the connectors-page detail panel. Server-side-fetches the full list from /api/marketplace/connectors (base from GUARDIAN_AGENT_INTERNAL_URL or http://localhost:3000), finds the entry whose id matches the path param, and returns it — or 404 if no card has that id. The returned object is identical in shape to one element of the list endpoint, including the live-overlaid toolCount/tools/version/config. Excluded from the auth middleware (no 401).",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "Connector id to look up in the marketplace card list (e.g. xsoar, xsiam, web, cortex-docs).",
        required: true,
        example: "xsiam"
      }
    ],
    responses: [
      {
        status: "200",
        description: "The single marketplace connector card object matching id (same shape as a /api/marketplace/connectors array element).",
        example: {
          id: "xsiam",
          name: "Cortex XSIAM",
          version: "0.2.0",
          toolCount: 54,
          status: "installed",
          category: "Security",
          authType: "Cortex XSIAM API key (api_id + api_key)"
        }
      },
      {
        status: "404",
        description: "No connector card has the requested id.",
        example: { error: "not found" }
      },
      {
        status: "502",
        description: "The internal /api/marketplace/connectors fetch returned non-OK.",
        example: { error: "catalog unavailable" }
      }
    ],
    tags: ["marketplace", "connectors", "catalog", "card-detail"],
  },
  {
    id: "marketplace-install-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/marketplace/install",
    summary: "Install a connector (mark installed)",
    description: "Marks a catalogue connector as installed so instances can be created against it. The agent route reads { connector_id, version? } from the JSON body and forwards to the MCP as a path-param POST (the JSON body is not forwarded downstream; the MCP derives version+origin from the catalogue). The MCP install is idempotent and pins the connector's origin (bundle vs user) from the catalogue — not from the client. The agent reshapes the MCP result into the legacy UI contract { id, connector_id, version, execution_mode:\"embedded\", install }. Catalog-side operation; touches no secret.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["connector_id"],
        properties: {
          connector_id: {
            type: "string",
            description: "Catalogue connector id to install. Trimmed; must be a non-empty string or the route returns 400."
          },
          version: {
            type: "string",
            description: "Optional; read off the request body type but NOT forwarded to the MCP (origin+version are catalogue-derived). The 200 response's version comes from the MCP install row, not this field."
          }
        }
      },
      example: { connector_id: "web" }
    },
    responses: [
      {
        status: "200",
        description: "Installed (idempotent). Agent returns the legacy install shape; install carries the MCP row (connector_id, installed_at, origin, version). version on the wrapper defaults to 'bundled' when the MCP install row has no string version.",
        example: {
          id: "web",
          connector_id: "web",
          version: "0.1.0",
          execution_mode: "embedded",
          install: {
            connector_id: "web",
            installed_at: "2026-06-17T09:00:00Z",
            origin: "bundle",
            version: "0.1.0"
          }
        }
      },
      {
        status: "400",
        description: "Invalid JSON body ({error:'invalid JSON body'}) or connector_id missing/not a string ({error:'connector_id is required (string)'}) — agent-side validation.",
        example: { error: "connector_id is required (string)" }
      },
      {
        status: "404",
        description: "Connector id not present in the catalogue (MCP body forwarded verbatim with the 404 status).",
        example: { error: "connector 'foo' not found in catalogue" }
      },
      {
        status: "401",
        description: "Caller not authenticated to the agent surface (middleware.ts on /api/agent/**)."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (resolveMcp guard).",
        example: { error: "MCP_TOKEN not configured" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable — agent route fetch threw.",
        example: { error: "MCP unreachable", detail: "..." }
      }
    ],
    riskTier: "soft",
    tags: ["marketplace", "connectors", "catalog", "install"],
  },
  {
    id: "marketplace-installed",
    category: "configuration",
    method: "GET",
    path: "/api/agent/marketplace/installed",
    summary: "List installed connectors",
    description: "Returns the connectors that currently have an install marker. The agent route fetches the MCP catalogue (GET /api/v1/marketplace), filters to entries with installed === true, and unwraps each into the legacy UI row { id, connector_id, version, execution_mode:\"embedded\" }, wrapped as { data: [...] }. Version comes from the install row (defaulting to \"bundled\"); execution_mode is a stable sentinel the UI's upgrade-comparison logic treats as \"no upgrade available\".",
    responses: [
      {
        status: "200",
        description: "Envelope { data: [...] } of installed connector rows.",
        example: {
          data: [
            { id: "xsoar", connector_id: "xsoar", version: "bundled", execution_mode: "embedded" },
            { id: "web", connector_id: "web", version: "bundled", execution_mode: "embedded" }
          ]
        }
      },
      {
        status: "401",
        description: "Caller not authenticated to the agent surface (middleware.ts on /api/agent/**)."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (resolveMcp guard).",
        example: { error: "MCP_TOKEN not configured" }
      },
      {
        status: "4xx/5xx (upstream passthrough)",
        description: "When the MCP responds non-OK, the agent route forwards the SAME upstream status code with { error: 'MCP returned <status>' } — it does NOT coerce this to 502.",
        example: { error: "MCP returned 500" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable (fetch threw → {error:'MCP unreachable', detail}) OR the MCP responded OK but with a non-JSON body ({error:'MCP returned non-JSON marketplace payload'}).",
        example: { error: "MCP returned non-JSON marketplace payload" }
      }
    ],
    tags: ["marketplace", "connectors", "catalog", "installed"],
  },
  {
    id: "marketplace-upload-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/marketplace/upload",
    summary: "Upload a user connector.yaml",
    description: "Registers a user-supplied connector by uploading its connector.yaml. The agent route requires a multipart/form-data body and re-streams the raw bytes (with the original Content-Type/boundary) verbatim to the MCP's /api/v1/marketplace/upload, forwarding the MCP's status code and body. The MCP reads ONLY the connector_yaml form field, parses + schema-validates it (connector.schema.json), rejects ids that collide with a bundle connector (409) or an existing user connector (409), requires an image field for user connectors (400 if absent), and on success writes /app/data/user_connectors/<id>/connector.yaml, audits a connector_uploaded event, and returns 201 with the connector summary. Catalog-side operation; the uploaded YAML carries config schema/secret slots but no secret values.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["connector_yaml"],
        properties: {
          connector_yaml: {
            type: "string",
            format: "binary",
            description: "Multipart file field carrying the raw connector.yaml content (may embed a base64 logo data URI). Must declare id, version, spec.tools and (for user connectors) an image field. This is the ONLY form field the MCP handler reads."
          }
        }
      },
      example: { connector_yaml: "@acme-edr/connector.yaml" }
    },
    responses: [
      {
        status: "201",
        description: "User connector persisted. MCP returns { ok, connector: <summary>, next_step }; the agent route forwards body + 201 status. connector summary fields: id, version, display_name, description, tools_count, tags, logo, origin.",
        example: {
          ok: true,
          connector: {
            id: "acme-edr",
            version: "1.0.0",
            display_name: "Acme EDR",
            description: "...",
            tools_count: 4,
            tags: ["edr"],
            logo: null,
            origin: "user"
          },
          next_step: "POST /api/v1/marketplace/acme-edr/install to make this connector available for instance creation."
        }
      },
      {
        status: "400",
        description: "Content-Type not multipart/form-data (agent guard {error:'Content-Type must be multipart/form-data'}); or MCP-side: multipart parse failure, missing connector_yaml field, empty connector_yaml, YAML parse failure, non-object YAML, schema validation failure (ConnectorSpecError), missing valid id field, or missing/blank image field for a user connector (code:image_ref_required).",
        example: {
          error: "user connectors must declare an 'image' field with the OCI image reference of the published connector container (e.g. 'ghcr.io/your-org/your-connector:v1.0')",
          code: "image_ref_required"
        }
      },
      {
        status: "409",
        description: "id collides with a bundle connector (code:id_collides_with_bundle) or an existing user connector (code:id_already_exists). MCP body forwarded with the 409 status.",
        example: {
          error: "connector id 'xsoar' is reserved by a bundle connector and cannot be overridden by upload",
          code: "id_collides_with_bundle"
        }
      },
      {
        status: "500",
        description: "Server missing pyyaml ({error:'server missing pyyaml dep — cannot parse uploads'}), or the YAML could not be written to disk (OSError).",
        example: { error: "could not persist user connector: ..." }
      },
      {
        status: "401",
        description: "Caller not authenticated to the agent surface (middleware.ts on /api/agent/**)."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (resolveMcp guard).",
        example: { error: "MCP_TOKEN not configured" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable — agent route fetch threw.",
        example: { error: "MCP unreachable: ..." }
      }
    ],
    riskTier: "soft",
    tags: ["marketplace", "connectors", "catalog", "upload", "user-connector"],
  },
  {
    id: "openapi",
    category: "configuration",
    method: "GET",
    path: "/api/agent/openapi",
    summary: "Export the agent REST surface as an OpenAPI 3.0 spec",
    description: "Native route (no MCP proxy). The GET handler calls generateOpenApiSpec() to build an OpenAPI 3.0.3 document from lib/api-catalog.ts at request time, so the spec stays in sync with the live catalog. servers[0].url is derived from the inbound request's host header and x-forwarded-proto header (defaulting to http://localhost:3000) so a spec downloaded from the deployed VM points at the VM, not localhost. Each operation carries x-guardian-risk-tier and x-guardian-requires-approval extensions mirrored from the catalog. Marked export const dynamic = 'force-dynamic' so it is never statically cached.",
    queryParams: [
      {
        name: "format",
        type: "string",
        description: "Output serialization. Default (or 'json') returns the spec as pretty-printed JSON (Content-Type application/json). 'yaml' or 'yml' returns it as YAML (Content-Type application/yaml) via lib/json-to-yaml. The value is lowercased before matching, so casing is ignored; any value other than yaml/yml falls through to JSON.",
        example: "yaml",
        enum: ["json", "yaml", "yml"]
      }
    ],
    responses: [
      {
        status: "200",
        description: "OpenAPI 3.0.3 document. JSON (Content-Type application/json; charset=utf-8) by default, or YAML (Content-Type application/yaml; charset=utf-8) when ?format=yaml|yml. Content-Disposition is inline with filename guardian-agent-openapi.json (or.yaml). Body includes info (title 'Guardian Agent API', version '0.2.0', contact name 'kite-production', license Apache-2.0), servers (request-derived url, description 'Local agent UI'), tags (one per ApiCategory), a method-keyed paths object generated from every catalog endpoint, and components.securitySchemes (cookieAuth apiKey-in-cookie 'session' + bearerAuth http bearer) with a top-level security of [{cookieAuth: []}].",
        example: {
          openapi: "3.0.3",
          info: {
            title: "Guardian Agent API",
            version: "0.2.0",
            description: "Operator-facing REST surface for the Guardian incident-response agent...",
            contact: { name: "kite-production", url: "https://github.com/kite-production/guardian" },
            license: { name: "Apache-2.0" }
          },
          servers: [
            { url: "https://localhost:3000", description: "Local agent UI" }
          ],
          tags: [
            { name: "configuration" },
            { name: "operations" }
          ],
          paths: {
            "/api/agent/jobs": {
              post: {
                operationId: "jobs-create",
                summary: "Create a runtime job",
                tags: ["operations"],
                requestBody: {
                  required: true,
                  content: {
                    "application/json": {
                      schema: { type: "object" }
                    }
                  }
                },
                responses: {
                  "201": { description: "Job created." }
                },
                "x-guardian-risk-tier": "soft"
              }
            }
          },
          components: {
            securitySchemes: {
              cookieAuth: { type: "apiKey", in: "cookie", name: "session" },
              bearerAuth: { type: "http", scheme: "bearer" }
            },
            schemas: {}
          },
          security: [
            {
              cookieAuth: []
            }
          ]
        }
      },
      {
        status: "500",
        description: "Only reachable on the YAML path: jsonToYaml() threw while serializing the spec (try/catch around the YAML branch). Returns a YAML-comment error body (Content-Type application/yaml; charset=utf-8) describing the failure and recommending the JSON download. The JSON path has no try/catch and no such failure mode."
      }
    ],
    tags: ["configuration"],
  },
  {
    id: "operator-state-by-key",
    category: "configuration",
    method: "GET",
    path: "/api/agent/operator-state/{key}",
    summary: "Read one operator workflow-state value by key",
    description: "Returns the operator workflow-state row for a single key (tested-journey marks, metrics-query bookmarks, etc.). This is the canonical home for operator workflow state: a key-value SQLite store (operator_state.db) that is NOT a secret and NOT platform catalogue. The agent-side route proxies to the embedded MCP at GET /api/v1/operator-state/{key}; the MCP returns {key, value, updated_at} where value is the parsed JSON the hook stored, or 404 when the key has never been set.",
    pathParams: [
      {
        name: "key",
        type: "string",
        description: "Stable caller-chosen key identifying the workflow-state value. Convention is lowercase snake_case, ASCII (e.g. 'tested_journeys', 'metrics_bookmarks'); the store does not enforce a shape. URL-encoded by the agent proxy via encodeURIComponent.",
        required: true,
        example: "tested_journeys"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Key found. Body is {key, value, updated_at}; value is the parsed JSON payload the hook persisted; updated_at is an ISO 8601 UTC string.",
        example: {
          key: "tested_journeys",
          value: ["v050-test-default-state", "v050-test-install-via-ui"],
          updated_at: "2026-06-17T09:14:02Z"
        }
      },
      {
        status: "400",
        description: "Empty key path segment (agent route forward() guard returns {error}).",
        example: { error: "key path segment is required" }
      },
      {
        status: "404",
        description: "Key has never been set. MCP returns {error} where the message embeds the Python repr of the key.",
        example: { error: "operator-state key 'tested_journeys' not set" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable from the Next.js proxy (fetch threw). Body {error:\"MCP unreachable\", detail}.",
        example: { error: "MCP unreachable", detail: "fetch failed" }
      },
      {
        status: "503",
        description: "MCP base/token could not be resolved by the agent proxy (MCP_TOKEN not configured). resolveMcp() returns {error:\"MCP_TOKEN not configured\"}.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    tags: ["operator-state", "workflow-state", "proxy"],
  },
  {
    id: "operator-state-by-key-delete",
    category: "configuration",
    method: "DELETE",
    path: "/api/agent/operator-state/{key}",
    summary: "Delete (reset) one operator workflow-state value by key",
    description: "Removes the operator workflow-state row for a key (e.g. the hook's reset() clearing all tested-journey marks). The agent-side route proxies to the embedded MCP at DELETE /api/v1/operator-state/{key}. Semantics are intentionally IDEMPOTENT: the MCP always returns 204 whether or not a row actually existed, because the caller's intent ('ensure this key is unset') is satisfied either way — there is no 404. The MCP records an audit event (action operator_state_delete) with status 'success' when a row was removed or 'noop' when none existed.",
    pathParams: [
      {
        name: "key",
        type: "string",
        description: "Key of the workflow-state value to remove (e.g. 'tested_journeys'). URL-encoded by the agent proxy via encodeURIComponent.",
        required: true,
        example: "tested_journeys"
      }
    ],
    responses: [
      {
        status: "204",
        description: "Key is now unset. Empty body. Returned whether or not a row existed (idempotent reset semantics). The agent route short-circuits an upstream 204 to an empty 204 without parsing a body."
      },
      {
        status: "400",
        description: "Empty key path segment (agent route forward() guard returns {error}).",
        example: { error: "key path segment is required" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable from the Next.js proxy (fetch threw). Body {error:\"MCP unreachable\", detail}.",
        example: { error: "MCP unreachable", detail: "fetch failed" }
      },
      {
        status: "503",
        description: "MCP base/token could not be resolved by the agent proxy (MCP_TOKEN not configured). resolveMcp() returns {error:\"MCP_TOKEN not configured\"}.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "destructive",
    tags: ["operator-state", "workflow-state", "proxy"],
  },
  {
    id: "operator-state-by-key-put",
    category: "configuration",
    method: "PUT",
    path: "/api/agent/operator-state/{key}",
    summary: "Upsert one operator workflow-state value by key",
    description: "Upserts the operator workflow-state value for a key. The request body MUST be a JSON object containing a 'value' field whose payload is any JSON-serializable blob the hook owns (list, dict, string, number, boolean, null). The agent-side route forwards the parsed JSON body unchanged to the embedded MCP at PUT /api/v1/operator-state/{key}, which serializes value into operator_state.db (json.dumps), records an audit event (action operator_state_set), and returns the persisted {key, value, updated_at} row.",
    pathParams: [
      {
        name: "key",
        type: "string",
        description: "Key to upsert (e.g. 'tested_journeys', 'metrics_bookmarks'). Convention is lowercase snake_case, ASCII. URL-encoded by the agent proxy via encodeURIComponent.",
        required: true,
        example: "tested_journeys"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["value"],
        properties: {
          value: {
            description: "Hook-owned JSON-serializable payload (array, object, string, number, boolean, null). Stored opaquely via json.dumps; the store does not enforce a shape."
          }
        }
      },
      example: {
        value: ["v050-test-default-state", "v050-test-install-via-ui"]
      }
    },
    responses: [
      {
        status: "200",
        description: "Value persisted. Body is the persisted row {key, value, updated_at}; updated_at is a freshly-stamped ISO 8601 UTC string.",
        example: {
          key: "tested_journeys",
          value: ["v050-test-default-state", "v050-test-install-via-ui"],
          updated_at: "2026-06-17T09:14:02Z"
        }
      },
      {
        status: "400",
        description: "One of: invalid JSON body (agent route → {error:'invalid JSON body'}, MCP → {error:'invalid JSON body:...'}); body is not a JSON object (MCP → {error:'body must be a JSON object'}); missing 'value' field (MCP → {error:\"body must contain a 'value' field\"}); value not JSON-serializable (store raises ValueError → {error}); or empty key path segment (agent guard → {error:'key path segment is required'}).",
        example: { error: "body must contain a 'value' field" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable from the Next.js proxy (fetch threw). Body {error:\"MCP unreachable\", detail}.",
        example: { error: "MCP unreachable", detail: "fetch failed" }
      },
      {
        status: "503",
        description: "MCP base/token could not be resolved by the agent proxy (MCP_TOKEN not configured). resolveMcp() returns {error:\"MCP_TOKEN not configured\"}.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "soft",
    tags: ["operator-state", "workflow-state", "proxy"],
  },
  {
    id: "providers-vertex-test-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/providers/vertex/test",
    summary: "Test a candidate Vertex service-account credential",
    description: "Probes a Vertex AI service-account JSON before it is saved. Native route (no MCP proxy): parses the JSON via parseCredentialsInput, resolves the redaction sentinel \"***\" (or an empty value) from the ProviderStore when the operator clicks Test without re-pasting, then performs a real JWT to OAuth2 token exchange via google-auth-library against Google's token endpoint and surfaces Google's verbatim error (or a translated local-PEM-decode message) on failure. Because it can resolve and exercise the stored Vertex SA JSON, it is credential-touching.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: [],
        properties: {
          service_account_json: {
            type: "string",
            description: "Full GCP service-account key JSON, or the literal \"***\" redaction sentinel (or empty) to test the currently-stored Vertex credential"
          },
          project_id: {
            type: "string",
            description: "Optional; declared in the TestBody type but never read by the handler — the auth probe is driven entirely by the SA JSON's own project_id"
          },
          location: {
            type: "string",
            description: "Optional; declared in the TestBody type but never read by the handler"
          }
        }
      },
      example: {
        service_account_json: "{\"type\":\"service_account\",\"project_id\":\"cortex-gcp-labs\",\"private_key\":\"-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n\",\"client_email\":\"guardian-sa@cortex-gcp-labs.iam.gserviceaccount.com\"}"
      }
    },
    responses: [
      {
        status: "200",
        description: "Always returned at the HTTP layer (every NextResponse.json carries {status:200}) so the page's status interpreter never falls through to a soft-success branch. The body's status field carries the verdict: \"success\" when the JWT/OAuth2 exchange returned an access token, \"error\" with a message when the body was not valid JSON, the SA JSON was empty/unparseable, no stored credential exists, the exchange returned no token, a local PEM decode failed (translated message), or Google rejected the exchange (verbatim, truncated to 400 chars).",
        example: {
          status: "success",
          message: "Connected. JWT exchange succeeded for guardian-sa@cortex-gcp-labs.iam.gserviceaccount.com against project cortex-gcp-labs."
        }
      }
    ],
    riskTier: "credential",
    tags: ["providers", "vertex", "credentials"],
  },
  {
    id: "restore-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/restore",
    summary: "Restore config from a backup zip",
    description: "Accepts a multipart/form-data upload (field name 'file') of a zip produced by GET /api/agent/backup and applies each section to the destination's stores in restore order: personality -> instances+secrets -> skills -> memory -> knowledge (verify-only) -> data_sources (user uploads then install set) -> jobs. Native handler (not a proxy): it parses the multipart body, opens the zip, validates manifest.json (schema_version must be in SUPPORTED_SCHEMAS=[1]), then makes per-section bearer-authed writes to the embedded MCP. Personality is always overwritten via PUT /api/v1/personality (single-row blob). Instances/skills/memory/jobs/data-sources use skip-on-collision semantics unless force=true; force bypasses the existence check (for skills it routes to skills_update for a true overwrite; for instances/jobs/data-sources it re-attempts the create). Instances are re-created via POST /api/v1/instances carrying their cleartext secrets, so the destination's SecretStore re-encrypts under its own KEK. Memory entries are POSTed without embeddings (destination re-embeds). Knowledge docs in the zip are ignored (KB content is image-baked, read-only at runtime) and reported as a warning. Restore is DESTRUCTIVE: personality is overwritten unconditionally and force=true overwrites colliding skills. Auth is enforced upstream by middleware.ts (guardian_session cookie).",
    queryParams: [
      {
        name: "dry_run",
        type: "boolean",
        description: "When the literal string 'true', parse + validate the zip and manifest and return a plan ({dry_run:true, manifest, sections_present, restore_order, force}) WITHOUT writing anything. Returns before _resolveMcp() so no MCP contact occurs.",
        example: "true"
      },
      {
        name: "force",
        type: "boolean",
        description: "When the literal string 'true', bypass the per-section collision skip. For skills this performs an overwrite via the skills_update MCP tool; for instances/jobs/data-sources it re-attempts the create (which may itself collide). Without force, name/id/tuple collisions are counted in the per-section `skipped` summary. Echoed back in the response as `force`.",
        example: "true"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["file"],
        properties: {
          file: {
            type: "string",
            format: "binary",
            description: "The backup zip uploaded as the multipart/form-data field named 'file' (NOT JSON). Must be a File instance, non-empty, <=100 MB, a valid zip, and contain a manifest.json with schema_version 1."
          }
        }
      },
      example: {
        file: "<binary guardian-backup-2026-06-17T12-00-00.zip uploaded via multipart field 'file'>"
      }
    },
    responses: [
      {
        status: "200",
        description: "Live restore completed — returned even when individual sections error; check the `ok` flag (true only when summary.errors is empty) and `errors[]`. Body: { ok, dry_run:false, force, schema_version (from manifest), backed_up_from (manifest.guardian_version), applied{}, skipped{}, errors[], warnings[] } via spread of the summary. When dry_run=true the SAME 200 status returns a DIFFERENT shape: { dry_run:true, manifest, sections_present, restore_order, force } with no writes performed.",
        example: {
          ok: true,
          dry_run: false,
          force: false,
          schema_version: 1,
          backed_up_from: "0.17.37",
          applied: {
            personality: 1,
            instances: 2,
            skills: 9,
            memory: 14,
            knowledge: 0,
            data_sources_user: 1,
            data_sources_installed: 5,
            jobs: 3
          },
          skipped: { instances: 0, skills: 0, data_sources_user: 0, data_sources_installed: 0, jobs: 0 },
          errors: [],
          warnings: [
            "924 knowledge doc(s) in zip ignored — knowledge bundles are image-baked and not writable at runtime. The destination's KB content is determined by its container image, not by restore."
          ]
        }
      },
      {
        status: "400",
        description: "Bad request: missing 'file' field (not a File instance), empty file (size 0), multipart parse failure, not a valid zip (JSZip.loadAsync threw), missing manifest.json, manifest.json not valid JSON, or unsupported/non-numeric schema_version (only 1 is supported). Returns JSON {error}.",
        example: {
          error: "missing manifest.json — this zip was not produced by GET /api/agent/backup or has been corrupted"
        }
      },
      {
        status: "413",
        description: "Uploaded file exceeds the 100 MB cap (file.size > 100*1024*1024). Returns {error:\"uploaded file exceeds 100 MB cap\"}.",
        example: { error: "uploaded file exceeds 100 MB cap" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured — returned by _resolveMcp() at the start of the live-write phase. Not reachable in dry_run, which returns the plan before MCP resolution.",
        example: { error: "MCP_TOKEN not configured" }
      },
      {
        status: "401",
        description: "No valid guardian_session cookie. Enforced by middleware.ts upstream of this handler (the route handler itself does no cookie check; its header comment documents this)."
      }
    ],
    riskTier: "credential",
    tags: ["restore", "config-import", "secrets", "destructive"],
  },

  {
    id: "connectors-by-id-tools",
    category: "configuration",
    method: "GET",
    path: "/api/agent/connectors/{id}/tools",
    summary: "List the tools a connector advertises",
    description: "Reads the connector's connector.yaml spec.tools[] (resolved via manifest.toolConnectors[].path under the bundle root) and returns one row per tool with name, namespaced name ('<connector_id>.<tool>'), one-line summary (first line of the tool description, truncated to 200 chars), full description, arg_count (length of the tool's args list), method (from tool.method, defaults to ''), and disabled. When ?instance_id is supplied AND that instance's connector_id matches this connector, each tool's 'disabled' reflects the instance's disabled_tools list; otherwise all tools report disabled=false. The agent route resolves the MCP via lib/mcp-proxy resolveMcp() and proxies GET to /api/v1/connectors/{id}/tools, forwarding instance_id when present.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "Connector id as declared in manifest.toolConnectors[].id (e.g. xsiam, xsoar, cortex-docs). URL-encoded by the agent route before forwarding.",
        required: true,
        example: "xsiam"
      }
    ],
    queryParams: [
      {
        name: "instance_id",
        type: "string",
        description: "Optional. When set to an instance id whose connector_id matches this connector, the per-tool 'disabled' flag reflects that instance's disabled_tools list; otherwise all tools report disabled=false. Echoed back as 'instance_id' in the response (null when absent).",
        example: "a1b2c3d4-0000-1111-2222-333344445555"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Tool listing with per-instance disabled state and aggregate counts. Shape: {connector_id, tools: [...], total, enabled, disabled, instance_id}. Each tool: name, namespaced, summary, description, arg_count, method, disabled.",
        example: {
          connector_id: "xsiam",
          tools: [
            {
              name: "get_cases",
              namespaced: "xsiam.get_cases",
              summary: "List cases from the XSIAM tenant.",
              description: "List cases from the XSIAM tenant.\nArgs: ...",
              arg_count: 3,
              method: "GET",
              disabled: false
            }
          ],
          total: 1,
          enabled: 1,
          disabled: 0,
          instance_id: null
        }
      },
      {
        status: "404",
        description: "Connector id not present in manifest.toolConnectors, or connector.yaml not found at the resolved path. Returned as {error: \"connector '<id>' not in manifest\"} or {error: \"connector.yaml not found for <id>\"}.",
        example: { error: "connector 'bogus' not in manifest" }
      },
      {
        status: "500",
        description: "Bundle manifest not found, manifest YAML parse failed, or connector.yaml parse failed. Returned as {error: \"bundle manifest not found at <path>\"}, {error: \"manifest parse failed: <exc>\"}, or {error: \"connector.yaml parse failed: <exc>\"}.",
        example: { error: "connector.yaml parse failed: <exc>" }
      },
      {
        status: "502",
        description: "MCP unreachable — the agent proxy's upstream fetch threw. Returned as {error: \"MCP unreachable\", detail: <msg>}.",
        example: { error: "MCP unreachable", detail: "fetch failed" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured — resolveMcp() short-circuits before forwarding. Returned as {error: \"MCP_TOKEN not configured\"}.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    tags: ["connectors", "tools", "schema", "instance"],
  },
  {
    id: "instances-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/instances",
    summary: "Create a connector instance",
    description: "Materializes a new connector instance — config plus per-instance secrets — into instances.db. The agent route forwards the raw body via the agent proxy to the MCP POST /api/v1/instances. The connector must be marketplace-installed first or the handler returns 409 connector_not_installed. Secret values are written to the SecretStore and the row holds only their paths (store.create). When the connector's resolved runtimeMapping.style is 'container' (the default when unset), the handler then calls guardian-updater to start the per-instance container and echoes the outcome as container_start. Because the body carries secret values this is on the credential side of the guardrail — REST/UI-only, never registered as an agent MCP tool.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["connector_id", "name"],
        properties: {
          connector_id: { type: "string" },
          name: { type: "string" },
          config: { type: "object" },
          secrets: { type: "object" },
          disabled_tools: {
            type: "array",
            items: { type: "string" }
          }
        }
      },
      example: {
        connector_id: "xsoar",
        name: "xsoar-prod",
        config: { base_url: "https://xsoar.example.com" },
        secrets: { api_key: "s3cr3t-token" },
        disabled_tools: []
      }
    },
    responses: [
      {
        status: "201",
        description: "Instance created. Returns the redacted serialized instance (secrets masked as \"***\"), requires_mcp_restart=true, the resolved runtime_style, and container_start (for container-style connectors the start runs in the background so this returns {started:null, pending:true} immediately and guardian-updater brings the container up out-of-band; null for non-container connectors).",
        example: {
          instance: {
            id: "3f1c2a9e-4d77-41b0-9a2e-7b1c0d5e8f22",
            connector_id: "xsoar",
            name: "xsoar-prod",
            config: { base_url: "https://xsoar.example.com" },
            secrets: { api_key: "***" },
            created_at: "2026-06-15T10:00:00Z",
            enabled: true,
            state: "pending",
            container_url: null,
            disabled_tools: []
          },
          requires_mcp_restart: true,
          runtime_style: "container",
          container_start: {
            started: true,
            container_url: "http://guardian-connector-xsoar-xsoar_prod:9000",
            error: null
          }
        }
      },
      {
        status: "400",
        description: "Invalid JSON, body not an object, missing/empty connector_id or name, config/secrets not objects, or disabled_tools not a list of strings.",
        example: { error: "connector_id is required (string)" }
      },
      {
        status: "409",
        description: "Connector is not marketplace-installed (code connector_not_installed), or store.create raised a ValueError (e.g. an (connector_id, name) UNIQUE collision, message 'instance (<id>, <name>) already exists').",
        example: {
          error: "connector 'xsoar' is not installed. Install it from /connectors first (or POST /api/v1/marketplace/xsoar/install).",
          code: "connector_not_installed",
          connector_id: "xsoar"
        }
      },
      {
        status: "401",
        description: "Missing or malformed Authorization header on the loopback proxy hop. Not normally reachable from the UI (proxy attaches the bearer server-side).",
        example: { error: "missing or malformed Authorization header" }
      }
    ],
    riskTier: "credential",
    tags: ["instances", "connectors", "crud", "secrets"],
  },
  {
    id: "providers-config-get",
    category: "configuration",
    method: "GET",
    path: "/api/agent/providers/config",
    summary: "Read LLM provider config (secrets redacted)",
    description: "Returns the current LLM provider configuration for the /providers settings page, read directly from the SecretStore-backed ProviderStore (no setup.json fallback). Native route: fetches the first primary-vertex and first primary-anthropic instances in parallel from the MCP provider list endpoint and returns a redacted view. Non-secret config (Vertex project id + region) is returned in cleartext; every secret that is present is reported as the \"***\" sentinel and flagged in a parallel configured map so the UI knows which credentials are already set. No secret value ever crosses this read path.",
    responses: [
      {
        status: "200",
        description: "Provider config view. providers holds cleartext non-secret fields (vertexProjectId, vertexLocation) plus \"***\" for each configured secret (vertexServiceAccountJson, anthropicApiKey, anthropicCliKey); configured maps each set field to true. Only keys that are actually configured appear — an unconfigured install returns {providers:{},configured:{}}.",
        example: {
          providers: {
            vertexProjectId: "cortex-gcp-labs",
            vertexLocation: "us-central1",
            vertexServiceAccountJson: "***",
            anthropicApiKey: "***",
            anthropicCliKey: "***"
          },
          configured: {
            vertexProjectId: true,
            vertexLocation: true,
            vertexServiceAccountJson: true,
            anthropicApiKey: true,
            anthropicCliKey: true
          }
        }
      },
      {
        status: "503",
        description: "MCP could not be resolved: resolveMcp() returned its error NextResponse, which this route returns directly. 503 {\"error\":\"MCP_TOKEN not configured\"} when no bearer token is available; resolveMcp also returns 500 {\"error\":\"bad MCP URL\"} when the MCP base URL cannot be derived. (There is no 401 path — the earlier 401 claim was incorrect.)",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    tags: ["providers", "vertex", "anthropic"],
  },
];

// ─────────────────────────────────────────────────────────────────
// OPERATIONS — jobs, audit, notifications
// ─────────────────────────────────────────────────────────────────

const OPERATIONS: ApiEndpoint[] = [
  {
    id: "jobs-list",
    category: "operations",
    method: "GET",
    path: "/api/agent/jobs",
    summary: "List scheduled jobs",
    description: "Both manifest-shipped and runtime-created jobs.",
    queryParams: [
      { name: "source", type: "string", enum: ["manifest", "runtime"], description: "Filter by source.", example: "runtime" },
    ],
    responses: [
      {
        status: "200",
        description: "List of jobs.",
        example: {
          jobs: [
            {
              name: "daily-soc-coverage-summary",
              cron: "0 8 * * *",
              timezone: "UTC",
              source: "manifest",
              enabled: true,
              next_due_at: "2026-05-02T08:00:00Z",
            },
          ],
          count: 1,
        },
      },
    ],
  },
  {
    id: "jobs-create",
    category: "operations",
    method: "POST",
    path: "/api/agent/jobs",
    summary: "Create a runtime job",
    description: "Persists to jobs.db AND mirrors to <data_root>/jobs/<name>.yaml so the runtime def is git-trackable.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["name", "cron", "action"],
        properties: {
          name: { type: "string", description: "Filesystem-safe name (no slashes, dots)." },
          cron: { type: "string", description: "5-field POSIX cron." },
          timezone: { type: "string", description: "IANA TZ name. Default UTC." },
          action: { type: "object", description: "{type: prompt|tool_call, ...} (legacy `chat` migrates to `prompt`)" },
          enabled: { type: "boolean" },
          run_once: { type: "boolean", description: "Auto-disable after first fire." },
        },
      },
      example: {
        name: "weekly-case-summary",
        cron: "0 9 * * MON",
        timezone: "UTC",
        action: { type: "tool_call", name: "xsiam.get_cases", args: { request: { limit: 50 } } },
        enabled: true,
        run_once: false,
      },
    },
    responses: [
      { status: "201", description: "Job created." },
      { status: "400", description: "Validation error (invalid cron, name conflict, etc)." },
    ],
    riskTier: "soft",
  },
  {
    id: "jobs-get",
    category: "operations",
    method: "GET",
    path: "/api/agent/jobs/{jobName}",
    summary: "Fetch one job",
    description: "Returns full row including last_status, next_due_at, enabled, cron, action.",
    pathParams: [{ name: "jobName", type: "string", description: "Job name.", example: "daily-soc-coverage-summary" }],
    responses: [
      { status: "200", description: "Job row." },
      { status: "404", description: "Not found." },
    ],
  },
  {
    id: "jobs-update",
    category: "operations",
    method: "PATCH",
    path: "/api/agent/jobs/{jobName}",
    summary: "Patch a runtime job",
    description: "Manifest jobs ignore most updates and revert on next boot.",
    pathParams: [{ name: "jobName", type: "string", description: "Job name." }],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        properties: {
          cron: { type: "string" },
          timezone: { type: "string" },
          action: { type: "object" },
          enabled: { type: "boolean" },
        },
      },
      example: { enabled: false },
    },
    responses: [{ status: "200", description: "Updated row." }],
    riskTier: "soft",
  },
  {
    id: "jobs-delete",
    category: "operations",
    method: "DELETE",
    path: "/api/agent/jobs/{jobName}",
    summary: "Permanently remove a job",
    description: "Runtime jobs: gone for good (YAML mirror also removed). Manifest jobs: reappear on next boot.",
    pathParams: [{ name: "jobName", type: "string", description: "Job name." }],
    responses: [{ status: "200", description: "Deleted." }],
    riskTier: "destructive",
  },
  {
    id: "jobs-runs",
    category: "operations",
    method: "GET",
    path: "/api/agent/jobs/{jobName}/runs",
    summary: "Recent run history",
    description: "Each row has run_id, started_at, finished_at, status (success|failure), result, error.",
    pathParams: [{ name: "jobName", type: "string", description: "Job name." }],
    queryParams: [{ name: "limit", type: "integer", description: "Default 20.", example: 20 }],
    responses: [{ status: "200", description: "Run rows." }],
  },
  {
    id: "jobs-action",
    category: "operations",
    method: "POST",
    path: "/api/agent/jobs/{jobName}/{action}",
    summary: "Trigger a job action",
    description: "Action is one of: run (fire now), pause (set enabled=false), resume (set enabled=true).",
    pathParams: [
      { name: "jobName", type: "string", description: "Job name." },
      { name: "action", type: "string", enum: ["run", "pause", "resume"], description: "Verb.", example: "run" },
    ],
    responses: [{ status: "200", description: "Action applied." }],
    riskTier: "soft",
  },
  {
    id: "audit-list",
    category: "operations",
    method: "GET",
    path: "/api/agent/audit",
    summary: "Search the audit log",
    description: "Filter by action, actor, target_prefix, free-text query, time range.",
    queryParams: [
      { name: "q", type: "string", description: "Free-text against action/target/metadata.", example: "xsiam" },
      { name: "action", type: "string", description: "Exact action filter.", example: "tool_call" },
      { name: "actor", type: "string", description: "Exact actor filter.", example: "operator" },
      { name: "target_prefix", type: "string", description: "Prefix filter.", example: "memory:" },
      { name: "limit", type: "integer", description: "Default 50.", example: 50 },
    ],
    responses: [{ status: "200", description: "Audit rows newest-first." }],
  },
  {
    id: "audit-stream",
    category: "operations",
    method: "GET",
    path: "/api/agent/audit/stream",
    summary: "Server-sent events stream of audit rows",
    description: "Long-lived SSE — emits one event per new audit row. Used by the live activity panel.",
    responses: [{ status: "200", description: "text/event-stream." }],
  },
  {
    id: "notifications-list",
    category: "operations",
    method: "GET",
    path: "/api/agent/notifications",
    summary: "List notifications",
    description: "Operator inbox. Supports unread_only filter.",
    queryParams: [
      { name: "unread_only", type: "boolean", description: "Hide already-read.", example: true },
      { name: "limit", type: "integer", description: "Default 50.", example: 50 },
    ],
    responses: [{ status: "200", description: "Notification rows." }],
  },
  {
    id: "notifications-ack",
    category: "operations",
    method: "POST",
    path: "/api/agent/notifications/{id}/ack",
    summary: "Mark a notification as read",
    description: "Idempotent.",
    pathParams: [{ name: "id", type: "string", description: "Notification UUID." }],
    responses: [{ status: "200", description: "Acked." }],
    riskTier: "soft",
  },

  {
    id: "notifications-post",
    category: "operations",
    method: "POST",
    path: "/api/agent/notifications",
    summary: "Publish a notification to a manifest-declared topic",
    description: "Forwards (via the agent proxy) to the MCP's POST /api/v1/notifications. Publishes one notification under a topic that MUST be declared in manifest.notifications.topics[]; the store stamps the topic's severity and target (from the manifest, NOT from the request), persists a row to notifications.db, optionally fans out to a channel webhook for channel:* targets, and fires the agent's Notification hook dispatcher (fire-and-forget). Undeclared topics are rejected. The notification bell UI reads the GET side of this route to render badges and the inbox.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["topic"],
        properties: {
          topic: { type: "string" },
          payload: { type: "object" },
          actor: { type: "string" }
        }
      },
      example: {
        topic: "job-run-completed",
        payload: {
          title: "Weekly summary done",
          body: "3 cases summarized",
          severity: "info",
          job_id: "weekly-summary"
        },
        actor: "ayman"
      }
    },
    responses: [
      {
        status: "201",
        description: "Notification published. Body is notif.to_dict(): id (uuid4), topic, severity (from the manifest topic, not the request), target (from the manifest topic), payload (the supplied dict), created_at (ISO8601 UTC micros), read_at (null on create), dispatch_status (\"stored\" for non-channel targets; \"dispatched\"/\"failed\" for channel:* targets), dispatch_error (null unless dispatch failed).",
        example: {
          id: "3f2a7c1e-1234-4abc-9def-000000000000",
          topic: "job-run-completed",
          severity: "info",
          target: "user:operator",
          payload: {
            title: "Weekly summary done",
            body: "3 cases summarized",
            severity: "info",
            job_id: "weekly-summary"
          },
          created_at: "2026-06-17T09:00:00.000000Z",
          read_at: null,
          dispatch_status: "stored",
          dispatch_error: null
        }
      },
      {
        status: "400",
        description: "Upstream MCP rejected the body: not JSON ({error:'Body must be JSON'}); topic missing/not a string ({error:'`topic` is required'}); payload not a JSON object ({error:'`payload` must be a JSON object'}); or topic not declared in manifest.notifications.topics (ValueError surfaced as {error:'topic... not declared...'}). Passed through by the agent proxy."
      },
      {
        status: "401",
        description: "Upstream MCP rejected the bearer (require_bearer guard on /api/v1/notifications); passed through by the agent proxy."
      },
      {
        status: "502",
        description: "Proxy could not reach the embedded MCP (fetch failed/timed out in the agent proxy)."
      },
      { status: "503", description: "MCP_TOKEN not configured (resolveMcp guard)." }
    ],
    riskTier: "soft",
    tags: ["notifications", "hooks"],
  },
  {
    id: "playbooks-validate-post",
    category: "operations",
    method: "POST",
    path: "/api/agent/playbooks/validate",
    summary: "Structurally validate a Cortex XSOAR playbook YAML",
    description: "Forwards (via the agent proxy) to the MCP's POST /api/v1/playbooks/validate. Runs the deterministic structural validator (playbook_validate) over a drafted XSOAR playbook YAML and returns a valid/invalid verdict with errors and warnings so the /playbooks/build UI can show a result before the operator imports a draft into XSOAR. It does not execute anything — structure check only.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["playbook_yaml"],
        properties: {
          playbook_yaml: { type: "string" }
        }
      },
      example: {
        playbook_yaml: "id: my-pb\nname: My Playbook\nstarttaskid: \"0\"\ntasks:\n  \"0\":\n    id: \"0\"\n    type: start\n"
      }
    },
    responses: [
      {
        status: "200",
        description: "Validation result, the return value of playbook_validate(playbook_yaml). Shape is determined by that function (not by the HTTP handler); the produced fields valid/errors/warnings/task_count reflect the documented validator contract but were not re-confirmed against playbook_tools.py in this pass.",
        example: {
          valid: false,
          errors: ["missing required field: name"],
          warnings: ["no task with type: start"],
          task_count: 3
        }
      },
      {
        status: "400",
        description: "Upstream MCP rejected the body: invalid JSON ({error:'invalid JSON body:...'}) or wrong shape ({error:'body must be {playbook_yaml: string}'} when body is not a dict or playbook_yaml is not a string). Passed through by the agent proxy."
      },
      {
        status: "401",
        description: "Upstream MCP rejected the bearer (require_bearer guard on /api/v1/playbooks/validate); passed through by the agent proxy."
      },
      {
        status: "502",
        description: "Proxy could not reach the embedded MCP (fetch failed/timed out in the agent proxy)."
      },
      { status: "503", description: "MCP_TOKEN not configured (resolveMcp guard)." }
    ],
    tags: ["playbooks", "xsoar", "validation"],
  },
  {
    id: "playbook-builds-list",
    category: "operations",
    method: "GET",
    path: "/api/agent/playbook-builds",
    summary: "List recorded playbook builds",
    description: "Returns the recorded playbook-build history from the PlaybookBuildStore (sqlite playbook_builds.db). Each row is a build the /playbooks/build page created — newest first — with its lifecycle status (drafted | validated | deployed | tested | failed), use_case, product, playbook_name, and timestamps. Drives the build-history grid, stat cards, status tabs, and search on /playbooks/build. Proxies (via the agent proxy, bearer MCP_TOKEN through lib/mcp-proxy.ts) to the embedded MCP at GET /api/v1/playbook-builds.",
    queryParams: [
      { name: "status", type: "string", enum: ["drafted", "validated", "deployed", "tested", "failed"], description: "Filter by lifecycle status.", example: "deployed" },
      { name: "limit", type: "integer", description: "Default 50.", example: 50 },
    ],
    responses: [
      {
        status: "200",
        description: "List of build records, newest first.",
        example: {
          builds: [
            {
              id: "pbb-9f2c1a",
              use_case: "Isolate a compromised endpoint on CrowdStrike and notify the analyst",
              product: "crowdstrike",
              playbook_name: "Isolate + Notify",
              status: "tested",
              test_incident_id: "1042",
              session_id: "sess-7b3e",
              created_by: "user:operator",
              created_at: "2026-06-25T14:02:11Z",
              updated_at: "2026-06-25T14:08:47Z",
            },
          ],
          count: 1,
        },
      },
    ],
  },
  {
    id: "playbook-builds-create",
    category: "operations",
    method: "POST",
    path: "/api/agent/playbook-builds",
    summary: "Record a new playbook build",
    description: "Inserts a build record into the PlaybookBuildStore and emits a best-effort playbook_drafted audit event. The build holds metadata only (no secret), so this is on the catalog side of the credential boundary. Proxies to the embedded MCP at POST /api/v1/playbook-builds.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["use_case", "playbook_yaml"],
        properties: {
          use_case: { type: "string", description: "Plain-English description the build was generated from." },
          product: { type: "string", description: "Optional product/integration (crowdstrike, defender, generic)." },
          playbook_name: { type: "string", description: "Name extracted from the drafted playbook." },
          playbook_yaml: { type: "string", description: "The drafted Cortex XSOAR playbook YAML." },
          status: { type: "string", description: "Initial lifecycle status. Default drafted." },
          validation: { type: "object", description: "Structural validation result (valid/errors/warnings/task_count)." },
          session_id: { type: "string", description: "Originating chat session id." },
        },
      },
      example: {
        use_case: "Investigate a phishing email end to end and delete similar messages on confirmation",
        product: "generic",
        playbook_name: "Phishing Triage + Cleanup",
        playbook_yaml: "id: phishing-triage\nname: Phishing Triage + Cleanup\nstarttaskid: \"0\"\ntasks:\n  \"0\":\n    id: \"0\"\n    type: start\n",
        status: "drafted",
        session_id: "sess-7b3e",
      },
    },
    responses: [
      { status: "201", description: "Build recorded; returns the stored record with its id." },
      { status: "400", description: "Validation error (missing use_case or playbook_yaml, wrong shape)." },
    ],
    riskTier: "soft",
  },
  {
    id: "playbook-builds-get",
    category: "operations",
    method: "GET",
    path: "/api/agent/playbook-builds/{id}",
    summary: "Fetch one playbook build",
    description: "Returns the full build record — use_case, product, playbook_name, playbook_yaml, status, validation, deploy_summary, test_incident_id, session_id, created_by, timestamps — backing the detail panel on /playbooks/build. Proxies to the embedded MCP at GET /api/v1/playbook-builds/{id}.",
    pathParams: [{ name: "id", type: "string", description: "Build id.", example: "pbb-9f2c1a" }],
    responses: [
      { status: "200", description: "Full build record." },
      { status: "404", description: "Not found." },
    ],
  },
  {
    id: "playbook-builds-update",
    category: "operations",
    method: "PATCH",
    path: "/api/agent/playbook-builds/{id}",
    summary: "Update a playbook build",
    description: "Patches a build record — typically advancing its lifecycle status (drafted → validated → deployed → tested, or failed) and attaching the validation result, deploy_summary, or test_incident_id as the build progresses. Emits a best-effort playbook_deployed or playbook_test_run audit event on the relevant transitions. Proxies to the embedded MCP at PATCH /api/v1/playbook-builds/{id}.",
    pathParams: [{ name: "id", type: "string", description: "Build id.", example: "pbb-9f2c1a" }],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        properties: {
          status: { type: "string", description: "drafted | validated | deployed | tested | failed." },
          validation: { type: "object", description: "Structural validation result." },
          deploy_summary: { type: "object", description: "Import + test-run outcome." },
          test_incident_id: { type: "string", description: "The disposable [Guardian test] incident the playbook ran on." },
        },
      },
      example: { status: "deployed", deploy_summary: { imported: true, run: true, war_room: "..." }, test_incident_id: "1042" },
    },
    responses: [
      { status: "200", description: "Updated build record." },
      { status: "404", description: "Not found." },
    ],
    riskTier: "soft",
  },
  {
    id: "playbook-builds-delete",
    category: "operations",
    method: "DELETE",
    path: "/api/agent/playbook-builds/{id}",
    summary: "Delete a playbook build",
    description: "Permanently removes a build record from the PlaybookBuildStore and emits a best-effort playbook_build_deleted audit event. Removes only the build-history metadata — it does not touch any playbook already imported into a tenant. Proxies to the embedded MCP at DELETE /api/v1/playbook-builds/{id}.",
    pathParams: [{ name: "id", type: "string", description: "Build id.", example: "pbb-9f2c1a" }],
    responses: [
      { status: "200", description: "Deleted." },
      { status: "404", description: "Not found." },
    ],
    riskTier: "destructive",
  },
];

// ─────────────────────────────────────────────────────────────────
// SELF-MODIFICATION — approvals lifecycle
// ─────────────────────────────────────────────────────────────────

const SELF_MOD: ApiEndpoint[] = [
  {
    id: "approvals-list",
    category: "self-modification",
    method: "GET",
    path: "/api/agent/approvals",
    summary: "List approval requests",
    description:
      "Pending + history depending on status filter. Each row includes risk_tier (soft|destructive|credential) — drives the inline approval card UI.",
    queryParams: [
      { name: "status", type: "string", enum: ["pending", "approved", "denied", "timeout"], description: "Filter by status.", example: "pending" },
      { name: "limit", type: "integer", description: "Default 50.", example: 50 },
    ],
    responses: [
      {
        status: "200",
        description: "Approval rows.",
        example: {
          approvals: [
            {
              id: "apv_abc",
              tool: "personality_update",
              actor: "agent",
              status: "pending",
              risk_tier: "soft",
              created_at: "2026-05-01T12:34:56.789Z",
              args: { blob_keys: ["personalityMd"], patch: true },
            },
          ],
          count: 1,
        },
      },
    ],
  },
  {
    id: "approvals-resolve",
    category: "self-modification",
    method: "POST",
    path: "/api/agent/approvals/{id}/resolve",
    summary: "Approve or deny a pending request",
    description:
      "Defense-in-depth: the bus's actor != resolver check rejects self-resolution (ApprovalSelfResolveError).",
    pathParams: [{ name: "id", type: "string", description: "Approval UUID.", example: "apv_abc" }],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["decision"],
        properties: {
          decision: { type: "string", enum: ["approved", "denied"] },
          reason: { type: "string" },
          actor: { type: "string" },
        },
      },
      example: { decision: "approved", reason: null, actor: "user:operator" },
    },
    responses: [
      { status: "200", description: "Resolved row." },
      { status: "403", description: "Self-resolution blocked." },
    ],
    riskTier: "soft",
  },
  {
    id: "agent-definitions",
    category: "configuration",
    method: "GET",
    path: "/api/agent/agent-definitions",
    summary: "List subagent definitions",
    description: "Lists the subagent-definition registry (name, description, system_prompt, tools_allowed/denied globs, model, max_turns, isolation, origin, enabled, timestamps). The agent-side route forwards the querystring unchanged to the embedded MCP at GET /api/v1/agent-definitions, which applies the origin and enabled_only filters and returns the rows ordered by name plus a count. The /agents UI reads from here and the chat-route subagent tooling resolves definitions registered here.",
    queryParams: [
      {
        name: "origin",
        type: "string",
        description: "Filter to one provenance source. Conventionally 'operator', 'builtin', or 'plugin:<name>'. Omitted = all origins. The handler passes the raw value straight to a SQL equality match, so it matches exact origin strings only.",
        example: "operator"
      },
      {
        name: "enabled_only",
        type: "string",
        description: "When the value is exactly '1', 'true', or 'yes', return only enabled definitions (enabled = 1). Any other value (or omitted) returns enabled and disabled definitions.",
        example: "true"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Registry rows wrapped under agent_definitions, plus a count of rows returned.",
        example: {
          agent_definitions: [
            {
              id: "b6f0c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d",
              name: "case-triage",
              description: "Triages new XSIAM cases",
              system_prompt: "You are a SOC triage analyst...",
              tools_allowed: ["xsiam_*"],
              tools_denied: [],
              model: null,
              max_turns: 10,
              isolation: "fresh_session",
              origin: "operator",
              enabled: true,
              created_at: "2026-06-17T09:00:00Z",
              updated_at: "2026-06-17T09:00:00Z"
            }
          ],
          count: 1
        }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable (fetch threw — network error or the 10s AbortSignal.timeout fired); body is {\"error\":\"MCP unreachable:...\"}.",
        example: { error: "MCP unreachable: The operation was aborted due to timeout" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent runtime; returned by the route before any upstream call.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    tags: ["agent-definitions", "subagents", "registry"],
  },
  {
    id: "agent-definitions-by-id",
    category: "configuration",
    method: "GET",
    path: "/api/agent/agent-definitions/{id}",
    summary: "Fetch one subagent definition",
    description: "Fetches a single subagent definition by its id. The agent-side route proxies to GET /api/v1/agent-definitions/{agent_id}; the MCP handler looks the row up by id and returns it wrapped under agent_definition, or a 404 when no definition has that id.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The agent definition's id (the 'id' field assigned at create time — a UUID when minted server-side). URL-encoded by the proxy before forwarding.",
        required: true,
        example: "b6f0c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d"
      }
    ],
    responses: [
      {
        status: "200",
        description: "The single definition wrapped under agent_definition.",
        example: {
          agent_definition: {
            id: "b6f0c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d",
            name: "case-triage",
            description: "Triages new XSIAM cases",
            system_prompt: "You are a SOC triage analyst...",
            tools_allowed: ["xsiam_*"],
            tools_denied: [],
            model: null,
            max_turns: 10,
            isolation: "fresh_session",
            origin: "operator",
            enabled: true,
            created_at: "2026-06-17T09:00:00Z",
            updated_at: "2026-06-17T09:00:00Z"
          }
        }
      },
      {
        status: "404",
        description: "No definition exists with that id; body is {\"error\":\"not found\"}.",
        example: { error: "not found" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable (fetch threw — network error or 10s timeout); body is {\"error\":\"MCP unreachable:...\"}.",
        example: { error: "MCP unreachable: fetch failed" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent runtime.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    tags: ["agent-definitions", "subagents"],
  },
  {
    id: "agent-definitions-by-id-delete",
    category: "configuration",
    method: "DELETE",
    path: "/api/agent/agent-definitions/{id}",
    summary: "Delete a subagent definition",
    description: "Removes a subagent definition from the registry. The agent-side route proxies to DELETE /api/v1/agent-definitions/{agent_id}. The MCP handler reads the row first (to capture name/origin for the audit), deletes it, writes an audit entry (action 'agent_definition_deleted'), and returns a deletion acknowledgement; a non-existent id (delete affected zero rows) yields 404.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The agent definition's id to delete. URL-encoded by the proxy before forwarding.",
        required: true,
        example: "b6f0c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Deletion acknowledged; body is {\"deleted\":true,\"id\":\"<id>\"} echoing the removed id.",
        example: { deleted: true, id: "b6f0c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d" }
      },
      {
        status: "404",
        description: "No definition exists with that id (defs.delete returned False — zero rows affected); body is {\"error\":\"not found\"}.",
        example: { error: "not found" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable (fetch threw — network error or 10s timeout); body is {\"error\":\"MCP unreachable:...\"}.",
        example: { error: "MCP unreachable: fetch failed" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent runtime.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "destructive",
    tags: ["agent-definitions", "subagents", "registry"],
  },
  {
    id: "agent-definitions-by-id-patch",
    category: "configuration",
    method: "PATCH",
    path: "/api/agent/agent-definitions/{id}",
    summary: "Partially update a subagent definition",
    description: "Partially updates an existing subagent definition. The agent-side route forwards the raw request body text to PATCH /api/v1/agent-definitions/{agent_id}. The MCP handler 404s when the id does not exist, then takes one of two paths: an enabled-only fast path (body keys are a subset of {enabled} and 'enabled' is present) that toggles activation via set_enabled and audits 'agent_definition_enabled'/'agent_definition_disabled'; otherwise it merges the body over the existing row (preserving id + created_at), re-validates, and upserts under the existing row's origin (audit 'agent_definition_upsert'). Returns the updated row under agent_definition.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The agent definition's id to update. URL-encoded by the proxy before forwarding.",
        required: true,
        example: "b6f0c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        properties: {
          name: { type: "string" },
          description: { type: "string" },
          system_prompt: { type: "string" },
          tools_allowed: {
            type: "array",
            items: { type: "string" }
          },
          tools_denied: {
            type: "array",
            items: { type: "string" }
          },
          model: {
            type: ["string", "null"]
          },
          max_turns: { type: "integer", description: "Integer in [1,50] on the merge path." },
          isolation: {
            type: "string",
            enum: ["parent_session", "fresh_session"]
          },
          enabled: {
            type: "boolean",
            description: "When the body's keys are exactly {enabled} and enabled is present, the fast-path toggle runs (set_enabled, no re-validation of other fields); otherwise enabled is merged into the row like any other field."
          }
        }
      },
      example: { enabled: false }
    },
    responses: [
      {
        status: "200",
        description: "Updated definition wrapped under agent_definition (both the fast-path toggle and the full merge return 200, not 201).",
        example: {
          agent_definition: {
            id: "b6f0c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d",
            name: "case-triage",
            description: "Triages new XSIAM cases",
            system_prompt: "You are a SOC triage analyst...",
            tools_allowed: ["xsiam_*"],
            tools_denied: [],
            model: null,
            max_turns: 10,
            isolation: "fresh_session",
            origin: "operator",
            enabled: false,
            created_at: "2026-06-17T09:00:00Z",
            updated_at: "2026-06-17T10:30:00Z"
          }
        }
      },
      {
        status: "400",
        description: "On the enabled-only fast path, 'enabled' is not a boolean → {\"error\":\"'enabled' must be a boolean\"}. On the full-merge path, the merged definition fails _validate_definition (empty name/system_prompt, invalid isolation, max_turns out of [1,50], or non-list tools_*). A malformed/non-object JSON body is also rejected 400 by the MCP. A duplicate name does NOT 400 (idempotent upsert by name).",
        example: { error: "'enabled' must be a boolean" }
      },
      {
        status: "404",
        description: "No definition exists with that id (checked before the body is read); body is {\"error\":\"not found\"}.",
        example: { error: "not found" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable (fetch threw — network error or 10s timeout); body is {\"error\":\"MCP unreachable:...\"}.",
        example: { error: "MCP unreachable: fetch failed" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent runtime.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "soft",
    tags: ["agent-definitions", "subagents", "registry"],
  },
  {
    id: "agent-definitions-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/agent-definitions",
    summary: "Create or upsert a subagent definition",
    description: "Creates a new subagent definition, or upserts an existing one when the body carries an id that already exists OR a name that already exists (the store is idempotent by id then by name). The agent-side route parses the JSON body and forwards it to POST /api/v1/agent-definitions. The MCP handler validates the body, mints a UUID into 'id' when absent, persists via the store with origin forced to 'operator', writes an audit row (action 'agent_definition_upsert'), and returns the persisted row under agent_definition with HTTP 201.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["name", "system_prompt"],
        properties: {
          id: {
            type: "string",
            description: "Optional; minted as a UUID when omitted. Supplying an existing id (or a name that already exists) upserts that row."
          },
          name: {
            type: "string",
            description: "Required, non-empty. UNIQUE in the DB schema, but a collision upserts the existing row rather than erroring."
          },
          description: { type: "string", description: "Optional; coerced to '' when omitted." },
          system_prompt: {
            type: "string",
            description: "Required, non-empty; the subagent's system instruction (the parent prompt is NOT inherited)."
          },
          tools_allowed: {
            type: "array",
            items: { type: "string" },
            description: "Glob patterns; empty/omitted = all tools. Must be a list if provided."
          },
          tools_denied: {
            type: "array",
            items: { type: "string" },
            description: "Glob patterns excluded even if allowed (deny-wins). Must be a list if provided."
          },
          model: {
            type: ["string", "null"],
            description: "Model override; null/omitted = parent's effective model."
          },
          max_turns: {
            type: "integer",
            description: "Integer in [1,50]; defaults to 10 (store also clamps to that range)."
          },
          isolation: {
            type: "string",
            enum: ["parent_session", "fresh_session"],
            description: "Defaults to fresh_session."
          },
          enabled: { type: "boolean", description: "Defaults to true." }
        }
      },
      example: {
        name: "case-triage",
        description: "Triages new XSIAM cases and proposes a severity",
        system_prompt: "You are a SOC triage analyst. Read the case, summarize the alerts, and recommend a severity.",
        tools_allowed: ["xsiam_*"],
        tools_denied: [],
        model: null,
        max_turns: 10,
        isolation: "fresh_session",
        enabled: true
      }
    },
    responses: [
      {
        status: "201",
        description: "Definition created or upserted; returns the persisted row under agent_definition (with generated id when minted and refreshed updated_at).",
        example: {
          agent_definition: {
            id: "b6f0c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d",
            name: "case-triage",
            description: "Triages new XSIAM cases and proposes a severity",
            system_prompt: "You are a SOC triage analyst...",
            tools_allowed: ["xsiam_*"],
            tools_denied: [],
            model: null,
            max_turns: 10,
            isolation: "fresh_session",
            origin: "operator",
            enabled: true,
            created_at: "2026-06-17T09:00:00Z",
            updated_at: "2026-06-17T09:00:00Z"
          }
        }
      },
      {
        status: "400",
        description: "Validation error from _validate_definition (missing/empty name, missing/empty system_prompt, isolation not in {fresh_session, parent_session}, max_turns not an int in [1,50], or tools_allowed/tools_denied not a list), OR a malformed/non-object JSON body rejected by the MCP. The agent route itself returns {\"error\":\"invalid JSON body\"} 400 if it cannot parse the request JSON. Note: a duplicate name does NOT 400 — the store upserts the existing row by name.",
        example: { error: "'name' is required and must be a non-empty string" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable (fetch threw — network error or 10s timeout); body is {\"error\":\"MCP unreachable:...\"}.",
        example: { error: "MCP unreachable: fetch failed" }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent runtime.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "soft",
    tags: ["agent-definitions", "subagents", "registry"],
  },
  {
    id: "hooks",
    category: "configuration",
    method: "GET",
    path: "/api/agent/hooks",
    summary: "List registered hooks",
    description: "Thin passthrough that forwards the incoming query string to the MCP's GET /api/v1/hooks. Lists all stored hook records, optionally filtered to one event via ?event= and/or enabled-only via ?enabled_only=. Backs the /settings/hooks UI page. Each hook is returned in full agent-shape (the stored JSON payload spread over canonical id/event/enabled/priority/createdAt/updatedAt fields), not the DB row shape.",
    queryParams: [
      {
        name: "event",
        type: "string",
        description: "Filter to hooks registered for one event. Must be in KNOWN_HOOK_EVENTS or the MCP returns 400 with the sorted known-event list.",
        example: "PreToolUse",
        enum: [
          "PreToolUse",
          "PostToolUse",
          "PostToolUseFailure",
          "UserPromptSubmit",
          "PreCompact",
          "PostCompact",
          "RunStart",
          "RunEnd",
          "SubagentStart",
          "SubagentEnd",
          "Notification",
          "PermissionRequest"
        ]
      },
      {
        name: "enabled_only",
        type: "string",
        description: "When '1'/'true'/'yes', returns only enabled hooks (priority ascending). Used at hook fire-sites.",
        example: "1"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Hooks listed. Returns {hooks, count} where each hook is the full agent-shape object (stored payload spread over id/event/enabled/priority/createdAt/updatedAt).",
        example: {
          hooks: [
            {
              id: "a1b2c3",
              name: "block-prod-delete",
              event: "PreToolUse",
              enabled: true,
              priority: 10,
              transport: {
                type: "builtin",
                name: "toolGuard",
                config: {
                  deny: ["xsiam.delete_case"]
                }
              },
              failurePolicy: "block",
              createdAt: "2026-06-15T09:00:00Z",
              updatedAt: "2026-06-15T09:00:00Z"
            }
          ],
          count: 1
        }
      },
      {
        status: "400",
        description: "Unknown ?event= value — MCP rejects with {error:\"unknown event '<x>'. Known: [...]\"}."
      },
      {
        status: "502",
        description: "MCP unreachable — agent returns {error:'MCP unreachable: <detail>'}."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (agent-side guard before proxying)."
      }
    ],
    tags: ["hooks", "read"],
  },
  {
    id: "hooks-builtins",
    category: "configuration",
    method: "GET",
    path: "/api/agent/hooks/builtins",
    summary: "List built-in hook recipe catalog",
    description: "Serves the in-image registry of built-in hook specs to /settings/hooks. Unlike /api/agent/hooks this route does NOT proxy to the MCP — the builtin registry is a TypeScript-side concept (lib/hook-builtins/) the MCP has no knowledge of. Operators install a builtin by POSTing a hook with transport.type==='builtin' + transport.name. The per-spec validateConfig/handle functions are intentionally omitted from the response; the UI only needs the metadata + config form fields.",
    responses: [
      {
        status: "200",
        description: "Builtin specs listed (metadata + config form fields only). Returns {builtins, count} where each builtin is {name, displayName, description, icon, compatibleEvents, configFields} and each configField is {key, label, type,...optional}.",
        example: {
          builtins: [
            {
              name: "flag-malicious-indicator",
              displayName: "Flag Malicious Indicator",
              description: "Deny or warn when a tool call references a known-bad indicator",
              icon: "flag",
              compatibleEvents: ["PreToolUse"],
              configFields: [
                {
                  key: "action",
                  label: "Action",
                  type: "select",
                  options: [
                    { value: "deny", label: "Deny" },
                    { value: "warn", label: "Warn" }
                  ]
                }
              ]
            }
          ],
          count: 1
        }
      }
    ],
    tags: ["hooks", "builtins", "catalog", "read"],
  },
  {
    id: "hooks-by-id",
    category: "configuration",
    method: "GET",
    path: "/api/agent/hooks/{id}",
    summary: "Fetch one hook by id",
    description: "Per-id passthrough to the MCP's GET /api/v1/hooks/{id}. Returns the single hook record in full agent-shape, or 404 with {error:'not found'} when no hook with that id exists.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The hook id (UUID minted at create time, or a caller-provided id used for idempotent upsert). URL-encoded into the MCP path.",
        required: true,
        example: "a1b2c3d4-0000-4000-8000-000000000000"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Hook found. Returns {hook: <full agent-shape object>}.",
        example: {
          hook: {
            id: "a1b2c3",
            name: "block-prod-delete",
            event: "PreToolUse",
            enabled: true,
            priority: 10,
            transport: {
              type: "builtin",
              name: "toolGuard",
              config: {
                deny: ["xsiam.delete_case"]
              }
            },
            failurePolicy: "block",
            createdAt: "2026-06-15T09:00:00Z",
            updatedAt: "2026-06-15T09:00:00Z"
          }
        }
      },
      { status: "404", description: "No hook with that id — MCP returns {error:'not found'}." },
      {
        status: "502",
        description: "MCP unreachable — agent returns {error:'MCP unreachable: <detail>'}."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (agent-side guard before proxying)."
      }
    ],
    tags: ["hooks", "read"],
  },
  {
    id: "hooks-by-id-delete",
    category: "configuration",
    method: "DELETE",
    path: "/api/agent/hooks/{id}",
    summary: "Delete a hook",
    description: "Per-id passthrough to the MCP's DELETE /api/v1/hooks/{id}. Permanently removes the hook record and writes a hook_deleted audit row (visible at /observability/events). Returns 404 when the id does not exist.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The hook id to delete.",
        required: true,
        example: "a1b2c3d4-0000-4000-8000-000000000000"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Hook deleted. Returns {deleted: true, id}.",
        example: { deleted: true, id: "a1b2c3" }
      },
      { status: "404", description: "No hook with that id — MCP returns {error:'not found'}." },
      {
        status: "502",
        description: "MCP unreachable — agent returns {error:'MCP unreachable: <detail>'}."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (agent-side guard before proxying)."
      }
    ],
    riskTier: "destructive",
    tags: ["hooks", "delete"],
  },
  {
    id: "hooks-by-id-patch",
    category: "configuration",
    method: "PATCH",
    path: "/api/agent/hooks/{id}",
    summary: "Partially update a hook",
    description: "Per-id passthrough to the MCP's PATCH /api/v1/hooks/{id}; the agent forwards the raw request body unparsed. The MCP has two paths: a fast toggle path when the body keys are exactly {enabled:<bool>} (the common UI enable/disable, writes a hook_enabled/hook_disabled audit row), and a full-upsert path that merges the body onto the existing hook, re-validates, and writes a hook_upsert audit row. id and createdAt are immutable across the merge.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The hook id to update.",
        required: true,
        example: "a1b2c3d4-0000-4000-8000-000000000000"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        properties: {
          enabled: {
            type: "boolean",
            description: "Toggle the hook on/off. When this is the only key present, the MCP runs the fast toggle path (must be a boolean else 400)."
          },
          name: { type: "string" },
          priority: { type: "integer" },
          transport: {
            type: "object",
            description: "command|http|agent|builtin|plugin transport spec; re-validated on the full-upsert path."
          },
          failurePolicy: {
            type: "string",
            enum: ["block", "allow", "warn"]
          },
          timeoutMs: { type: "integer", description: "Integer in [100, 60000]." }
        }
      },
      example: { enabled: false }
    },
    responses: [
      {
        status: "200",
        description: "Hook updated. Returns {hook: <full agent-shape object>}.",
        example: {
          hook: {
            id: "a1b2c3",
            name: "block-prod-delete",
            event: "PreToolUse",
            enabled: false,
            priority: 10,
            transport: {
              type: "builtin",
              name: "toolGuard",
              config: {
                deny: ["xsiam.delete_case"]
              }
            },
            failurePolicy: "block",
            createdAt: "2026-06-15T09:00:00Z",
            updatedAt: "2026-06-15T10:00:00Z"
          }
        }
      },
      {
        status: "400",
        description: "MCP-side: invalid JSON body, body not an object, non-boolean 'enabled' on the toggle path, or validation failure on the merged payload (missing/empty name, unknown event, bad transport, out-of-range timeoutMs, invalid failurePolicy)."
      },
      { status: "404", description: "No hook with that id — MCP returns {error:'not found'}." },
      {
        status: "502",
        description: "MCP unreachable — agent returns {error:'MCP unreachable: <detail>'}."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (agent-side guard before proxying)."
      }
    ],
    riskTier: "soft",
    tags: ["hooks", "update"],
  },
  {
    id: "hooks-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/hooks",
    summary: "Create or upsert a hook",
    description: "Passthrough to the MCP's POST /api/v1/hooks. Creates a new hook (id minted when absent) or upserts when a caller-provided id is given. The MCP validates name, event (must be a KNOWN_HOOK_EVENTS value), and the transport spec, then mints id/createdAt/updatedAt, persists, and writes a hook_upsert audit row. Backs the /settings/hooks create form.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["name", "event", "transport"],
        properties: {
          id: {
            type: "string",
            description: "Optional. Provide for idempotent upsert; minted as a UUID when absent."
          },
          name: { type: "string", description: "Required non-empty string." },
          event: {
            type: "string",
            description: "Must be one of KNOWN_HOOK_EVENTS.",
            enum: [
              "PreToolUse",
              "PostToolUse",
              "PostToolUseFailure",
              "UserPromptSubmit",
              "PreCompact",
              "PostCompact",
              "RunStart",
              "RunEnd",
              "SubagentStart",
              "SubagentEnd",
              "Notification",
              "PermissionRequest"
            ]
          },
          transport: {
            type: "object",
            description: "transport.type one of command|http|agent|builtin|plugin. command needs transport.command(str); http needs transport.url(str); agent needs transport.toolName(str); builtin needs transport.name(str) + transport.config(object); plugin needs transport.handlerName(str) (+optional config object, +optional positive timeoutS)."
          },
          enabled: { type: "boolean" },
          priority: { type: "integer" },
          failurePolicy: {
            type: "string",
            enum: ["block", "allow", "warn"]
          },
          timeoutMs: { type: "integer", description: "Integer in [100, 60000]." }
        }
      },
      example: {
        name: "block-prod-delete",
        event: "PreToolUse",
        enabled: true,
        priority: 10,
        transport: {
          type: "builtin",
          name: "toolGuard",
          config: {
            deny: ["xsiam.delete_case"]
          }
        },
        failurePolicy: "block"
      }
    },
    responses: [
      {
        status: "201",
        description: "Hook created/upserted. Returns {hook: <full agent-shape object with minted id/createdAt/updatedAt>}.",
        example: {
          hook: {
            id: "a1b2c3",
            name: "block-prod-delete",
            event: "PreToolUse",
            enabled: true,
            priority: 10,
            transport: {
              type: "builtin",
              name: "toolGuard",
              config: {
                deny: ["xsiam.delete_case"]
              }
            },
            failurePolicy: "block",
            createdAt: "2026-06-15T09:00:00Z",
            updatedAt: "2026-06-15T09:00:00Z"
          }
        }
      },
      {
        status: "400",
        description: "Agent-side {error:'invalid JSON body'} when the body isn't JSON; MCP-side when body isn't an object, name missing/empty, unknown event, invalid transport (missing required transport field for the type, bad transport.type), out-of-range timeoutMs, or invalid failurePolicy."
      },
      {
        status: "502",
        description: "MCP unreachable — agent returns {error:'MCP unreachable: <detail>'}."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (agent-side guard before proxying)."
      }
    ],
    riskTier: "soft",
    tags: ["hooks", "create", "upsert"],
  },
  {
    id: "jobs-yaml-issues",
    category: "operations",
    method: "GET",
    path: "/api/agent/jobs/yaml-issues",
    summary: "List jobs whose on-disk YAML failed to parse",
    description: "Read-only proxy (via the agent proxy) to the MCP's GET /api/v1/jobs/yaml-issues. Surfaces per-file YAML-load failures collected by the job scheduler at boot/reload (from the runtime jobs mirror, e.g. /app/data/jobs/*.yaml) that would otherwise only appear as WARN lines in docker compose logs. The /jobs UI polls this on render and shows a banner pointing the operator at the offending files when count > 0. The route performs no auto-quarantine or auto-delete; the data files belong to the operator.",
    responses: [
      {
        status: "200",
        description: "List of YAML-load issues. Each entry carries path (absolute), basename, error (\"<ExcType>: <msg>\"), and mtime (epoch seconds float, 0.0 if stat failed). count is len(issues).",
        example: {
          issues: [
            {
              path: "/app/data/jobs/weekly-summary.yaml",
              basename: "weekly-summary.yaml",
              error: "ScannerError: mapping values are not allowed here",
              mtime: 1718600000.0
            }
          ],
          count: 1
        }
      },
      {
        status: "401",
        description: "Upstream MCP rejected the bearer (require_bearer guard on /api/v1/jobs/yaml-issues); passed through by the agent proxy."
      },
      {
        status: "502",
        description: "Proxy could not reach the embedded MCP (fetch failed/timed out in the agent proxy)."
      },
      { status: "503", description: "MCP_TOKEN not configured (resolveMcp guard)." }
    ],
    tags: ["jobs", "scheduler", "diagnostics"],
  },
  {
    id: "plugin-entries",
    category: "configuration",
    method: "GET",
    path: "/api/agent/plugin-entries",
    summary: "List pip-installed plugin entry-points",
    description: "Catalog of the DISTRIBUTABLE plugin system — pip-installable Python packages that contribute via importlib.metadata entry_points across five reserved groups (guardian.skills, guardian.connectors, guardian.hooks, guardian.scanners, guardian.providers). Distinct from GET /api/agent/plugins (the filesystem tree). Calls discover_all() and returns entry-points grouped by group name plus a total count across all groups. Consumed by /observability/plugins. The agent route proxies to GET /api/v1/plugin-entries with the MCP_TOKEN bearer (cache: no-store, no explicit client timeout).",
    responses: [
      {
        status: "200",
        description: "Entry-points grouped by group name, with a total across all groups. On a fresh install every group is empty and total is 0.",
        example: {
          groups: {
            "guardian.hooks": [
              {
                group: "guardian.hooks",
                name: "my_hook",
                dist_name: "acme-guardian-plugin",
                dist_version: "0.2.0",
                target: "acme_plugin.hooks:on_alert"
              }
            ],
            "guardian.skills": []
          },
          total: 1
        }
      },
      {
        status: "401",
        description: "Missing or malformed Authorization header (passed through from the MCP's require_bearer).",
        example: { error: "missing or malformed Authorization header" }
      },
      {
        status: "500",
        description: "Entry-point discovery raised inside the MCP (discover_all failed); response includes empty groups and total 0.",
        example: {
          error: "discovery failed: ...",
          groups: {},
          total: 0
        }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable — proxy fetch failed.",
        example: { error: "MCP unreachable: ..." }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured in the agent runtime (agent route short-circuits before proxying).",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    tags: ["plugins", "entry-points", "read-only"],
  },
  {
    id: "plugin-entries-by-dist_name-delete",
    category: "configuration",
    method: "DELETE",
    path: "/api/agent/plugin-entries/{dist_name}",
    summary: "Uninstall a plugin distribution via pip",
    description: "Runs `pip uninstall -y --disable-pip-version-check <dist_name>` for the named distribution. #PLAT-F11: restricted to the internal MCP_TOKEN admin principal (API keys → 403) and human-approval-gated (deny → 403, timeout → 408) — removing a package the MCP imports can break the process. The MCP handler rejects a dist_name containing disallowed characters (; | & $ backtick / CR LF space) and rejects an empty value. On approval + success it clears the plugin-hook handler cache and records a 'plugin_uninstall' audit event; skill/connector/provider/scanner caches still require a guardian-agent restart to fully purge. The agent route URL-encodes dist_name and forwards to DELETE /api/v1/plugin-entries/{dist_name} with the MCP_TOKEN bearer (no explicit client timeout, so the approval wait is held by the proxy).",
    pathParams: [
      {
        name: "dist_name",
        type: "string",
        description: "The pip distribution name to uninstall (e.g. acme-guardian-plugin). Must be non-empty and contain none of:; | & $ backtick / CR LF space.",
        required: true,
        example: "acme-guardian-plugin"
      }
    ],
    responses: [
      {
        status: "200",
        description: "pip uninstall succeeded; plugin-hook handler cache flushed. Returns ok, the dist_name, a 500-char stdout tail, and an explanatory note.",
        example: {
          ok: true,
          dist_name: "acme-guardian-plugin",
          stdout_tail: "Successfully uninstalled acme-guardian-plugin-0.2.0",
          note: "Plugin-hook handler cache flushed. For other contribution types (skills, connectors, providers, scanners), restart guardian-agent to fully purge."
        }
      },
      {
        status: "400",
        description: "dist_name contains disallowed characters ({error:'dist_name contains disallowed characters'}) or is empty after the char check ({error:'dist_name is required'}).",
        example: { error: "dist_name contains disallowed characters" }
      },
      {
        status: "401",
        description: "Missing or malformed Authorization header (passed through from the MCP's require_bearer).",
        example: { error: "missing or malformed Authorization header" }
      },
      {
        status: "500",
        description: "pip uninstall returned a non-zero exit code; includes return_code plus 1500-char stderr/stdout tails.",
        example: {
          error: "pip uninstall failed",
          return_code: 1,
          stderr: "WARNING: Skipping ... as it is not installed.",
          stdout: ""
        }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured in the agent runtime (agent route short-circuits before proxying).",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "destructive",
    tags: ["plugins", "entry-points", "uninstall", "pip"],
  },
  {
    id: "plugin-entries-install-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/plugin-entries/install",
    summary: "Install a plugin distribution via pip",
    description: "Runs `pip install --user --disable-pip-version-check --quiet <spec>` for a single dist spec (PyPI name, git+url, or local path). #PLAT-F11: because pip executes arbitrary package build code in the MCP container (RCE-class), this is restricted to the internal MCP_TOKEN admin principal (operator-minted API keys are rejected with 403) AND gated behind a human approval — the MCP opens a destructive-tier approval and blocks until an operator resolves it in /approvals (deny → 403, timeout → 408). The MCP handler requires the body to be a JSON object with a non-empty string 'spec', and rejects any spec containing shell metacharacters (; | & $ backtick CR LF). On approval + success it re-discovers entry-points, clears the plugin-hook handler cache (so guardian.hooks handlers become invokable without restart), records a 'plugin_install' audit event, and returns 201. Other contribution types (skills/connectors/scanners/providers) still need a guardian-agent restart. The agent route parses req.json() (returning its own 400 {error:'body must be JSON'} if that fails) and forwards the parsed body to POST /api/v1/plugin-entries/install with the MCP_TOKEN bearer (no explicit client timeout, so the approval wait is held by the proxy).",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["spec"],
        properties: {
          spec: {
            type: "string",
            description: "pip install target: PyPI name, git+url, or local path. Non-empty after trim; must not contain ; | & $ backtick CR LF."
          }
        }
      },
      example: { spec: "acme-guardian-plugin" }
    },
    responses: [
      {
        status: "201",
        description: "pip install succeeded; entry-points re-discovered and plugin-hook handler cache cleared. Returns ok, the spec, a 500-char stdout tail, post-install discovery_counts, and an explanatory note.",
        example: {
          ok: true,
          spec: "acme-guardian-plugin",
          stdout_tail: "Successfully installed acme-guardian-plugin-0.2.0",
          discovery_counts: { "guardian.hooks": 1, "guardian.skills": 0 },
          note: "Newly-discovered entry-points visible at GET /api/v1/plugin-entries. ..."
        }
      },
      {
        status: "400",
        description: "Agent route: body not parseable as JSON ({error:'body must be JSON'}). MCP handler: body not a JSON object ({error:'body must be a JSON object'}), missing-or-empty 'spec' ({error:\"'spec' is required (non-empty string)\"}), or spec contains disallowed shell characters ({error:'spec contains disallowed shell characters'}).",
        example: { error: "'spec' is required (non-empty string)" }
      },
      {
        status: "401",
        description: "Missing or malformed Authorization header (passed through from the MCP's require_bearer).",
        example: { error: "missing or malformed Authorization header" }
      },
      {
        status: "403",
        description: "#PLAT-F11 — caller authenticated with an operator-minted API key, not the internal MCP_TOKEN admin principal; pip install is admin-only. Also returned when the human approval is DENIED ({error:'approval denied: <reason>'}).",
        example: { error: "plugin install/uninstall requires the MCP admin token" }
      },
      {
        status: "408",
        description: "#PLAT-F11 — the install approval timed out (no operator confirmed it in /approvals within the bus window).",
        example: { error: "approval timed out — no operator confirmed the install" }
      },
      {
        status: "500",
        description: "pip install returned a non-zero exit code; includes return_code plus 1500-char stderr/stdout tails.",
        example: {
          error: "pip install failed",
          return_code: 1,
          stderr: "ERROR: Could not find a version ...",
          stdout: ""
        }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured in the agent runtime (agent route short-circuits before proxying).",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "soft",
    tags: ["plugins", "entry-points", "install", "pip"],
  },
  {
    id: "plugin-hooks",
    category: "configuration",
    method: "GET",
    path: "/api/agent/plugin-hooks",
    summary: "List discovered plugin hook handlers",
    description: "Passthrough to the MCP's GET /api/v1/plugin-hooks. Returns the plugin-contributed hook handlers discovered by walking the guardian.hooks entry-point group across installed plugin packages. Populates the plugin-handler dropdown in /settings/hooks; ?refresh=1 clears the handler cache and forces a fresh entry-point walk (used by /observability/plugins after install/uninstall).",
    queryParams: [
      {
        name: "refresh",
        type: "string",
        description: "When '1'/'true'/'yes', clears the handler cache and re-walks entry-points before listing. The agent forwards the literal value through as ?refresh=<value>.",
        example: "1"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Handlers listed. Returns {handlers, count} where each handler descriptor is {name, dist_name, dist_version, target} (the callable itself is not included), sorted by name.",
        example: {
          handlers: [
            {
              name: "slack-notify",
              dist_name: "guardian-slack-plugin",
              dist_version: "1.2.0",
              target: "guardian_slack.hooks:notify"
            }
          ],
          count: 1
        }
      },
      {
        status: "500",
        description: "Entry-point discovery failed — MCP returns {error:'discovery failed: <detail>', handlers: []}."
      },
      {
        status: "502",
        description: "MCP unreachable — agent returns {error:'MCP unreachable: <detail>'}."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (agent-side guard before proxying)."
      }
    ],
    tags: ["hooks", "plugins", "read"],
  },
  {
    id: "plugins",
    category: "configuration",
    method: "GET",
    path: "/api/agent/plugins",
    summary: "List filesystem-discovered plugins",
    description: "Read-only inventory of the filesystem plugin tree (bundles/spark/plugins/<name>/). Returns every discovered plugin with manifest metadata and contribution counts. Applies NO contributions — calls loader.list_loaded(), which reads manifests and counts contributions without side effects; applying contributions is the /plugins/reload endpoint's job. The agent route proxies to the embedded MCP at GET /api/v1/plugins with the MCP_TOKEN bearer and a 10s timeout.",
    responses: [
      {
        status: "200",
        description: "Plugin inventory with per-plugin contribution counts. seeded_count is always 0 on this read path (only reload writes seeds).",
        example: {
          plugins: [
            {
              name: "acme-soc",
              version: "1.0.0",
              description: "ACME SOC plugin",
              enabled: true,
              path: "/app/plugins/acme/acme-soc",
              skills_count: 3,
              scenarios_count: 1,
              memory_seeds_count: 5,
              seeded_count: 0,
              error: null
            }
          ],
          count: 1
        }
      },
      {
        status: "401",
        description: "Missing or malformed Authorization header (passed through from the MCP's require_bearer).",
        example: { error: "missing or malformed Authorization header" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable — proxy fetch failed or timed out at 10s.",
        example: { error: "MCP unreachable: ..." }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured in the agent runtime (agent route short-circuits before proxying).",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    tags: ["plugins", "marketplace", "read-only"],
  },
  {
    id: "plugins-reload-post",
    category: "configuration",
    method: "POST",
    path: "/api/agent/plugins/reload",
    summary: "Re-apply enabled plugins' contributions",
    description: "Re-scans the filesystem plugin tree and re-applies every ENABLED plugin's contributions: skill/scenario file copies (shutil.copy2, idempotent), memory seeds (skipped when the (scope,key) already exists), and agent definitions (upserted with origin plugin:<name>). The MCP handler sets the audit actor to 'user:operator', records a 'plugins_reloaded' audit event, and returns the post-apply plugin list. The agent route always sends a fixed empty {} body (it ignores any client-supplied body) and proxies to POST /api/v1/plugins/reload with the MCP_TOKEN bearer and a 20s timeout.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: [],
        properties: {}
      },
      example: {}
    },
    responses: [
      {
        status: "200",
        description: "Reload applied; returns the post-apply plugin list. seeded_count reflects seeds actually written this run (existing keys are skipped, so a re-run typically returns 0).",
        example: {
          plugins: [
            {
              name: "acme-soc",
              version: "1.0.0",
              description: "ACME SOC plugin",
              enabled: true,
              path: "/app/plugins/acme/acme-soc",
              skills_count: 3,
              scenarios_count: 1,
              memory_seeds_count: 5,
              seeded_count: 0,
              error: null
            }
          ],
          count: 1
        }
      },
      {
        status: "401",
        description: "Missing or malformed Authorization header (passed through from the MCP's require_bearer).",
        example: { error: "missing or malformed Authorization header" }
      },
      {
        status: "502",
        description: "Embedded MCP unreachable — proxy fetch failed or timed out at 20s.",
        example: { error: "MCP unreachable: ..." }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured in the agent runtime (agent route short-circuits before proxying).",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "soft",
    tags: ["plugins", "marketplace", "reload"],
  },
  {
    id: "tasks",
    category: "operations",
    method: "GET",
    path: "/api/agent/tasks",
    summary: "List background agent tasks",
    description: "Returns a list of background agent tasks from the SqliteTaskStore (tasks.db). The agent route forwards the request's full query string verbatim to the MCP at GET /api/v1/tasks. Supports filtering by status, kind, parent session, and an active-only shortcut (pending+running). Used by the /tasks page, the chat-header drawer (active_only=1), and the /tasks slash command.",
    queryParams: [
      {
        name: "active_only",
        type: "string",
        description: "When equal to '1', 'true', or 'yes', returns only non-terminal tasks (pending + running). Any other value is treated as false.",
        example: "1",
        enum: ["1", "true", "yes"]
      },
      {
        name: "status",
        type: "string",
        description: "Filter by exact task status. Rejected with 400 if not one of the valid statuses.",
        example: "running",
        enum: ["pending", "running", "succeeded", "failed", "aborted"]
      },
      {
        name: "kind",
        type: "string",
        description: "Filter by task kind string (free-form category set at creation, e.g. 'investigation' or 'xql_query').",
        example: "xql_query"
      },
      {
        name: "session",
        type: "string",
        description: "Filter to tasks spawned by a given parent chat session id (maps to the parent_session_id column).",
        example: "sess_a1b2c3"
      },
      {
        name: "limit",
        type: "integer",
        description: "Max rows to return. Non-integer/empty values fall back to the default. Default 100 (set by the API layer's _int(\"limit\", 100)).",
        example: "100"
      },
      {
        name: "offset",
        type: "integer",
        description: "Row offset for pagination. Non-integer/empty values fall back to the default. Default 0.",
        example: "0"
      }
    ],
    responses: [
      {
        status: "200",
        description: "List of tasks plus a count of returned rows. Each task is Task.to_dict() — note it does NOT include the cancel_token column.",
        example: {
          tasks: [
            {
              id: "f3a0c2e1-4b5d-4e6f-8a90-112233445566",
              kind: "investigation",
              status: "running",
              title: "Triage incident 4821",
              parent_session_id: "sess_a1b2c3",
              progress: 0.4,
              progress_label: "Enriching indicators",
              output: null,
              meta: {},
              created_at: "2026-06-17T09:00:00Z",
              updated_at: "2026-06-17T09:05:00Z",
              completed_at: null
            }
          ],
          count: 1
        }
      },
      {
        status: "400",
        description: "Unknown status filter value (MCP-side). Body lists the valid statuses via sorted(VALID_STATUS).",
        example: {
          error: "unknown status 'foo'. Valid: ['aborted', 'failed', 'pending', 'running', 'succeeded']"
        }
      },
      {
        status: "401",
        description: "Missing or invalid MCP bearer token; the MCP's require_bearer rejects and the agent route proxies the status through verbatim."
      },
      {
        status: "502",
        description: "Agent route could not reach the embedded MCP (fetch threw / timed out at 10s).",
        example: { error: "MCP unreachable: ..." }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent (returned by the agent route before any upstream call).",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    tags: ["tasks", "operations", "background-jobs"],
  },
  {
    id: "tasks-by-id",
    category: "operations",
    method: "GET",
    path: "/api/agent/tasks/{id}",
    summary: "Fetch a single background agent task",
    description: "Returns one background agent task by id. The agent route forwards to GET /api/v1/tasks/{task_id} on the MCP, which looks up the row in tasks.db and returns its full to_dict() shape under a 'task' key, or 404 when no such id exists.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The task id (a uuid minted at creation unless a caller-supplied id was used). The agent route encodeURIComponent-encodes it into the upstream path.",
        required: true,
        example: "f3a0c2e1-4b5d-4e6f-8a90-112233445566"
      }
    ],
    responses: [
      {
        status: "200",
        description: "The requested task object under a 'task' key (Task.to_dict(); cancel_token not included).",
        example: {
          task: {
            id: "f3a0c2e1-4b5d-4e6f-8a90-112233445566",
            kind: "investigation",
            status: "succeeded",
            title: "Triage incident 4821",
            parent_session_id: "sess_a1b2c3",
            progress: 1.0,
            progress_label: "Done",
            output: "Summary: ...",
            meta: {},
            created_at: "2026-06-17T09:00:00Z",
            updated_at: "2026-06-17T09:12:00Z",
            completed_at: "2026-06-17T09:12:00Z"
          }
        }
      },
      {
        status: "404",
        description: "No task with that id exists (MCP-side, when tasks.get(...) returns None).",
        example: { error: "not found" }
      },
      {
        status: "401",
        description: "Missing or invalid MCP bearer token (proxied from the MCP's require_bearer)."
      },
      {
        status: "502",
        description: "Agent route could not reach the embedded MCP.",
        example: { error: "MCP unreachable: ..." }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    tags: ["tasks", "operations", "background-jobs"],
  },
  {
    id: "tasks-by-id-abort-post",
    category: "operations",
    method: "POST",
    path: "/api/agent/tasks/{id}/abort",
    summary: "Abort a running background task",
    description: "Marks a background task as aborted. Cooperative cancellation only — it transitions the task to terminal status 'aborted' (idempotent no-op if already terminal, returning the existing task) and records a task_aborted audit row only when the prior status was non-terminal. No subprocess signal is sent; the worker is expected to poll its own status and bail. The agent route reads the raw request body and forwards it (or '{}' if empty) to POST /api/v1/tasks/{task_id}/abort.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The task id to abort. encodeURIComponent-encoded into the upstream path by the agent route.",
        required: true,
        example: "f3a0c2e1-4b5d-4e6f-8a90-112233445566"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: [],
        properties: {
          reason: {
            type: "string",
            description: "Optional human-readable abort reason. Recorded in the task_aborted audit row's metadata and stored as the task's output via transition(output=reason). The body is allow_empty: a missing/invalid body is treated as {}."
          }
        }
      },
      example: { reason: "Operator cancelled from the tasks drawer" }
    },
    responses: [
      {
        status: "200",
        description: "The task after the abort (status 'aborted' if it was non-terminal; the unchanged existing task if it was already terminal). Returned under a 'task' key.",
        example: {
          task: {
            id: "f3a0c2e1-4b5d-4e6f-8a90-112233445566",
            kind: "investigation",
            status: "aborted",
            title: "Triage incident 4821",
            parent_session_id: "sess_a1b2c3",
            progress: 0.4,
            progress_label: "Enriching indicators",
            output: "Operator cancelled from the tasks drawer",
            meta: {},
            created_at: "2026-06-17T09:00:00Z",
            updated_at: "2026-06-17T09:06:00Z",
            completed_at: "2026-06-17T09:06:00Z"
          }
        }
      },
      {
        status: "404",
        description: "No task with that id exists (MCP-side, when the pre-abort get(...) returns None).",
        example: { error: "not found" }
      },
      {
        status: "401",
        description: "Missing or invalid MCP bearer token (proxied from the MCP's require_bearer)."
      },
      {
        status: "502",
        description: "Agent route could not reach the embedded MCP.",
        example: { error: "MCP unreachable: ..." }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "soft",
    tags: ["tasks", "operations", "background-jobs", "cancel"],
  },
  {
    id: "tasks-post",
    category: "operations",
    method: "POST",
    path: "/api/agent/tasks",
    summary: "Create a background agent task",
    description: "Creates a new background agent task in the SqliteTaskStore (tasks.db) and records a task_created audit row. The agent route parses the JSON body (returning its own 400 {\"error\":\"invalid JSON body\"} if it cannot) then forwards it to POST /api/v1/tasks. 'kind' and 'title' are required non-empty strings; the task starts in 'pending' state unless initial_status is 'running'. A caller-supplied 'id' allows idempotent re-create (INSERT OR REPLACE); otherwise a uuid is minted.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["kind", "title"],
        properties: {
          kind: {
            type: "string",
            description: "Non-empty task category, e.g. 'investigation' or 'xql_query'. Trimmed before storage."
          },
          title: {
            type: "string",
            description: "Non-empty human-readable task title. Trimmed before storage."
          },
          parent_session_id: {
            type: "string",
            description: "Optional chat session id that spawned this task (NULL for cron / system-spawned)."
          },
          meta: {
            type: "object",
            description: "Optional free-form metadata object stored as meta_json (defaults to {} when omitted or falsy)."
          },
          initial_status: {
            type: "string",
            enum: ["pending", "running"],
            description: "Starting status; defaults to 'pending'. Any other value is rejected with 400."
          },
          id: {
            type: "string",
            description: "Optional caller-supplied task id for idempotent re-create (INSERT OR REPLACE). A uuid is minted when absent."
          }
        }
      },
      example: {
        kind: "investigation",
        title: "Triage incident 4821",
        parent_session_id: "sess_a1b2c3",
        meta: { incident_id: 4821 },
        initial_status: "pending"
      }
    },
    responses: [
      {
        status: "201",
        description: "Task created. Returns the persisted task object under a 'task' key (Task.to_dict(); cancel_token not included).",
        example: {
          task: {
            id: "f3a0c2e1-4b5d-4e6f-8a90-112233445566",
            kind: "investigation",
            status: "pending",
            title: "Triage incident 4821",
            parent_session_id: "sess_a1b2c3",
            progress: 0,
            progress_label: null,
            output: null,
            meta: { incident_id: 4821 },
            created_at: "2026-06-17T09:00:00Z",
            updated_at: "2026-06-17T09:00:00Z",
            completed_at: null
          }
        }
      },
      {
        status: "400",
        description: "Validation error: missing/empty 'kind' or 'title', invalid 'initial_status', non-object body (\"body must be a JSON object\"), or unparseable JSON (the agent route returns \"invalid JSON body\"; the MCP returns \"invalid JSON body:...\"). Body carries a specific 'error' message.",
        example: { error: "'kind' is required (non-empty string)" }
      },
      {
        status: "401",
        description: "Missing or invalid MCP bearer token (proxied from the MCP's require_bearer)."
      },
      {
        status: "502",
        description: "Agent route could not reach the embedded MCP.",
        example: { error: "MCP unreachable: ..." }
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured on the agent.",
        example: { error: "MCP_TOKEN not configured" }
      }
    ],
    riskTier: "soft",
    tags: ["tasks", "operations", "background-jobs", "create"],
  },
  {
    id: "tool-call-post",
    category: "operations",
    method: "POST",
    path: "/api/agent/tool/call",
    summary: "Dispatch an MCP tool directly by name and arguments",
    description: "Native Next.js route (not a the agent proxy passthrough) that invokes a single MCP tool with no LLM in the loop — the deterministic test surface behind the chat input's `^toolname arg=val` syntax. It opens a JSON-RPC session against the embedded MCP (initialize + notifications/initialized), resolves a bare tool name to its fully-qualified form via tools/list (exact match, else unique suffix match on \".<bare>\" or \"_<bare>\"), then issues tools/call and returns the parsed result. Works without any provider config. Risk depends on which tool is named; treated as soft since it executes whatever tool the caller specifies (credential-management tools are never registered as MCP tools, so they are unreachable here).",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["name"],
        properties: {
          name: { type: "string" },
          arguments: { type: "object" }
        }
      },
      example: {
        name: "xsoar_get_incident",
        arguments: { incident_id: "42" }
      }
    },
    responses: [
      {
        status: "200",
        description: "Tool dispatched. ok = NOT isError from the tools/call result. result is structuredContent if present, else the first text content parsed as JSON (falling back to the raw text), else the raw result payload. resolved_name is the fully-qualified tool the MCP ran. duration_ms is wall-clock latency including the JSON-RPC handshake. On isError, ok=false and error carries the result (string, or JSON.stringify of a non-string).",
        example: {
          ok: true,
          resolved_name: "xsoar_get_incident",
          result: { id: "42", name: "Suspicious login", severity: 3 },
          duration_ms: 812
        }
      },
      {
        status: "400",
        description: "Request body was not JSON, or name was missing / not a string. Returns {ok:false, resolved_name:\"\", error, duration_ms}."
      },
      {
        status: "404",
        description: "Bare-name resolution failed: no registered tool matched the supplied name, or the name was ambiguous across multiple tools (error names the matches). Returns {ok:false, resolved_name:<input name>, error, duration_ms}."
      },
      {
        status: "502",
        description: "MCP session open failed (no mcp-session-id / initialize error), tools/call returned a non-200, or no JSON-RPC result frame was found in the SSE response."
      },
      {
        status: "503",
        description: "MCP_TOKEN not configured (resolveMcp returns a 503 NextResponse, surfaced directly by the route)."
      }
    ],
    riskTier: "soft",
    tags: ["tools", "mcp", "dispatch", "testing"],
  },
];

// ─────────────────────────────────────────────────────────────────
// OBSERVABILITY — health, metrics
// ─────────────────────────────────────────────────────────────────

const OBSERVABILITY: ApiEndpoint[] = [
  {
    id: "health",
    category: "observability",
    method: "GET",
    path: "/api/agent/health",
    summary: "Liveness + readiness probe",
    description:
      "Returns {status, embedder_mode}. embedder_mode='vertex' means the live VertexEmbedder is wired; 'stub' means the agent booted before Vertex creds were submitted.",
    responses: [
      {
        status: "200",
        description: "Health snapshot.",
        example: { status: "ok", embedder_mode: "vertex" },
      },
    ],
  },
  {
    id: "metrics",
    category: "observability",
    method: "GET",
    path: "/api/agent/metrics",
    summary: "Prometheus exposition",
    description:
      "Standard /metrics scrape target. Includes guardian_embedder_* gauges (upstream_calls, cache_hits, errors_total, fallback_calls, cache_entries) refreshed at scrape time.",
    responses: [
      {
        status: "200",
        description: "text/plain Prometheus 0.0.4 exposition.",
        example:
          "# HELP guardian_embedder_upstream_calls_total Vertex embed() calls...\nguardian_embedder_upstream_calls_total 4.0\n",
      },
    ],
  },
  {
    id: "bench-runs",
    category: "observability",
    method: "GET",
    path: "/api/agent/bench/runs",
    summary: "List recent benchmark runs",
    description: "Lists recorded benchmark runs newest-first (ORDER BY started_at DESC) from benchmark_runs.db. Thin proxy to the MCP GET /api/v1/bench/runs, which returns lightweight per-run metadata rows (run_id, manifest_id, started_at, completed_at, router_preset) with no embedded summary, plus a count. Backs the /observability/bench page run list.",
    queryParams: [
      {
        name: "limit",
        type: "integer",
        description: "Max number of runs to return, newest-first. The agent route forwards \"20\" when the query param is absent. The MCP applies no default cap: a missing/empty/non-integer/<=0 limit maps to SQL LIMIT -1 (unbounded).",
        example: "20"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Object with a 'runs' array of metadata rows and a 'count'. Each row contains exactly run_id, manifest_id, started_at, completed_at, router_preset (the full summary is omitted; use the per-run detail endpoint).",
        example: {
          runs: [
            {
              run_id: "bench_1718614800_a1b2c3d4",
              manifest_id: "guardian-soc-v1",
              started_at: "2026-06-17T09:00:00Z",
              completed_at: "2026-06-17T09:02:14Z",
              router_preset: null
            }
          ],
          count: 1
        }
      },
      {
        status: "503",
        description: "Agent-side: MCP_TOKEN resolves empty from runtime config and env.",
        example: { error: "MCP_TOKEN not configured" }
      },
      {
        status: "401",
        description: "MCP rejected the bearer token (require_bearer) — proxied through verbatim."
      }
    ],
    tags: ["bench", "observability", "runs"],
  },
  {
    id: "bench-runs-by-run_id",
    category: "observability",
    method: "GET",
    path: "/api/agent/bench/runs/{run_id}",
    summary: "Get one benchmark run's full detail",
    description: "Returns the full stored record for a single benchmark run wrapped under 'run', including the deserialized 5-axis BenchSummary (correctness_rate, avg_tool_jaccard, cost p50/p95, wall p50/p95, infrastructure_errors, per-case scores). Thin proxy to MCP GET /api/v1/bench/runs/{run_id}. Backs the /observability/bench run drill-down.",
    pathParams: [
      {
        name: "run_id",
        type: "string",
        description: "The benchmark run id (primary key in benchmark_runs.db), formatted bench_<unix-epoch>_<8-hex>, as returned by the list endpoint or a prior POST.",
        required: true,
        example: "bench_1718614800_a1b2c3d4"
      }
    ],
    responses: [
      {
        status: "200",
        description: "The run record wrapped under 'run', with row fields run_id, manifest_id, started_at, completed_at, router_preset and the parsed 'summary' (BenchSummary.to_dict() including per-case scores).",
        example: {
          run: {
            run_id: "bench_1718614800_a1b2c3d4",
            manifest_id: "guardian-soc-v1",
            started_at: "2026-06-17T09:00:00Z",
            completed_at: "2026-06-17T09:02:14Z",
            router_preset: null,
            summary: {
              run_id: "bench_1718614800_a1b2c3d4",
              manifest_id: "guardian-soc-v1",
              started_at: "2026-06-17T09:00:00Z",
              completed_at: "2026-06-17T09:02:14Z",
              case_count: 3,
              correctness_rate: 1.0,
              avg_tool_jaccard: 0.83,
              cost_p50: 0.0142,
              cost_p95: 0.021,
              wall_p50: 18.4,
              wall_p95: 41.2,
              infrastructure_errors: 0,
              cases: [
                {
                  case_id: "summarize-case",
                  correctness: true,
                  tool_call_jaccard: 1.0,
                  cost_usd: 0.0142,
                  wall_seconds: 18.4,
                  wall_warning: false,
                  error: null
                }
              ]
            }
          }
        }
      },
      {
        status: "404",
        description: "No run exists with that run_id.",
        example: { error: "not found" }
      },
      {
        status: "503",
        description: "Agent-side: MCP_TOKEN resolves empty from runtime config and env.",
        example: { error: "MCP_TOKEN not configured" }
      },
      {
        status: "401",
        description: "MCP rejected the bearer token (require_bearer) — proxied through verbatim."
      }
    ],
    tags: ["bench", "observability", "runs"],
  },
  {
    id: "bench-runs-post",
    category: "observability",
    method: "POST",
    path: "/api/agent/bench/runs",
    summary: "Start a benchmark run",
    description: "Triggers a synchronous benchmark run against a manifest (bundled id or YAML path). The MCP runner dispatches each case to the agent's /api/chat SSE endpoint, scores the result on 5 axes, and persists the summary to benchmark_runs.db. Thin proxy to MCP POST /api/v1/bench/runs, a convenience layer over run_manifest. Runs synchronously (typically 1-5 minutes for the bundled corpus) and returns the recorded summary at 201.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["manifest"],
        properties: {
          manifest: {
            type: "string",
            description: "Bundled manifest id (e.g. guardian-soc-v1) or a path to a manifest YAML. Required, must be a non-empty string."
          },
          router_preset_model: {
            type: "string",
            description: "Optional model id passed through to body.model on each case dispatch; null/omitted uses the router default. Must be a string when present."
          },
          thinking_enabled: {
            type: "boolean",
            description: "Optional; coerced via bool() and passed through to body.thinking on each dispatch. Defaults to false."
          }
        }
      },
      example: {
        manifest: "guardian-soc-v1",
        router_preset_model: null,
        thinking_enabled: false
      }
    },
    responses: [
      {
        status: "201",
        description: "Run completed and recorded. Returns run_id plus the full BenchSummary under 'summary'.",
        example: {
          run_id: "bench_1718614800_a1b2c3d4",
          summary: {
            run_id: "bench_1718614800_a1b2c3d4",
            manifest_id: "guardian-soc-v1",
            started_at: "2026-06-17T09:00:00Z",
            completed_at: "2026-06-17T09:02:14Z",
            case_count: 3,
            correctness_rate: 1.0,
            avg_tool_jaccard: 0.83,
            cost_p50: 0.0142,
            cost_p95: 0.021,
            wall_p50: 18.4,
            wall_p95: 41.2,
            infrastructure_errors: 0,
            cases: [
              {
                case_id: "summarize-case",
                correctness: true,
                tool_call_jaccard: 1.0,
                cost_usd: 0.0142,
                wall_seconds: 18.4,
                wall_warning: false,
                error: null
              }
            ]
          }
        }
      },
      {
        status: "400",
        description: "Body is not JSON (agent or MCP), not a JSON object, 'manifest' missing/not-a-string/blank, router_preset_model present but not a string, or run_manifest raised ValueError (e.g. manifest not found / invalid YAML).",
        example: { error: "'manifest' is required (path or bundled id)" }
      },
      {
        status: "500",
        description: "Run raised an unexpected (non-ValueError) exception during execution.",
        example: { error: "run failed: <detail>" }
      },
      {
        status: "503",
        description: "Agent-side: MCP_TOKEN resolves empty from runtime config and env.",
        example: { error: "MCP_TOKEN not configured" }
      },
      {
        status: "401",
        description: "MCP rejected the bearer token (require_bearer) — proxied through verbatim."
      }
    ],
    riskTier: "soft",
    tags: ["bench", "observability", "runs"],
  },
  {
    id: "digests",
    category: "observability",
    method: "GET",
    path: "/api/agent/digests",
    summary: "Report stack + per-connector image digest pins",
    description: "Comprehensive image-digest reporter for the running stack. Native route (does its own work, not an mcp-proxy.ts proxy to the embedded MCP): it builds version + ISO generated_at + the three stack-tier service digests (guardian-agent, guardian-updater, guardian-browser) synchronously from compose-injected DIGEST_GUARDIAN_AGENT|UPDATER|BROWSER env vars, then fetches guardian-updater's GET /api/v1/connectors/digests (bearer MCP_TOKEN, 3s AbortSignal timeout) to enumerate each running per-instance connector container's actual digest. If the updater query fails (timeout, non-2xx, or unreachable) it degrades gracefully — the route still returns 200 with connectors set to [] and connectors_error carrying the failure message. Consumed by the /observability/connectors panel and the About modal's image-versions section.",
    responses: [
      {
        status: "200",
        description: "Digest report. version + generated_at + stack[] are always present; stack[] is exactly 3 entries (guardian-agent, guardian-updater, guardian-browser) built env-only and never fails. connectors[] is the live per-instance connector digests from guardian-updater, or [] with connectors_error set if the updater query failed. A stack entry's digest is null (and pinned false) when its DIGEST_GUARDIAN_* env var is unset or not a sha256: value.",
        example: {
          version: "0.2.36",
          generated_at: "2026-06-17T14:03:21.118Z",
          stack: [
            { service: "guardian-agent", digest: "sha256:9f1c...", pinned: true },
            { service: "guardian-updater", digest: "sha256:4ab2...", pinned: true },
            {
              service: "guardian-browser",
              digest: null,
              pinned: false
            }
          ],
          connectors: [
            {
              connector_id: "xsiam",
              instance_id: "3f9a2c10-7b44-4e2a-9c1d-aa01bb22cc33",
              instance_name: "primary",
              digest: "sha256:e7d0...",
              pinning_mode: "digest",
              image_ref: "ghcr.io/kite-production/guardian-connector-xsiam:dev"
            }
          ]
        }
      },
      {
        status: "200",
        description: "Degraded variant — the guardian-updater query failed. The route still returns 200 with stack[] populated; connectors is [] and connectors_error holds the failure reason. The message is 'updater returned <status>' for a non-2xx response, or the underlying fetch error message (e.g. timeout / network) when the updater is unreachable.",
        example: {
          version: "0.2.36",
          generated_at: "2026-06-17T14:03:21.118Z",
          stack: [
            { service: "guardian-agent", digest: "sha256:9f1c...", pinned: true },
            { service: "guardian-updater", digest: "sha256:4ab2...", pinned: true },
            { service: "guardian-browser", digest: "sha256:1c0e...", pinned: true }
          ],
          connectors: [],
          connectors_error: "updater returned 503"
        }
      },
      {
        status: "401",
        description: "No accepted credential. middleware.ts (matcher /api/agent/:path*) requires one of: an Authorization: Bearer guardian_ak_* API key (validateApiKey), the internal MCP_TOKEN bearer, or a valid guardian_session cookie (validateSession). When none is present/valid the request is rejected with a JSON body {error:\"unauthenticated\", code:<reason>} (e.g. no_session_cookie).",
        example: { error: "unauthenticated", code: "no_session_cookie" }
      }
    ],
    tags: ["observability", "digests", "images", "connectors", "stack", "supply-chain"],
  },
  {
    id: "observability-events",
    category: "observability",
    method: "GET",
    path: "/api/agent/observability/events",
    summary: "Query the runtime structured-events feed",
    description: "Reads the runtime telemetry events feed (the high-signal stream declared in manifest.observability.events, e.g. rt.tool.failed) from the MCP's events.db. The agent route forwards the raw query string verbatim to the MCP handler at /api/v1/observability/events, which filters by event name, actor, and time window with pagination, ordering newest-first. Distinct from /api/agent/audit (forensic state-change log); this feed is for operator-facing alerts and dashboards.",
    queryParams: [
      {
        name: "event",
        type: "string",
        description: "Filter to a single event name (e.g. rt.tool.failed). Read as q.get('event') and passed as event_name to events.query (exact-match SQL clause).",
        example: "rt.tool.failed"
      },
      {
        name: "actor",
        type: "string",
        description: "Filter to events recorded by a specific principal/actor (exact-match SQL clause).",
        example: "agent"
      },
      {
        name: "since",
        type: "string",
        description: "Lower time bound (inclusive) compared as ts >= since against the ISO-8601 timestamp string.",
        example: "2026-06-17T00:00:00Z"
      },
      {
        name: "until",
        type: "string",
        description: "Upper time bound (inclusive) compared as ts <= until against the ISO-8601 timestamp string.",
        example: "2026-06-17T23:59:59Z"
      },
      {
        name: "limit",
        type: "integer",
        description: "Max events to return. The HTTP handler defaults to 100 (_int('limit', 100)); non-integer values fall back to 100.",
        example: "100"
      },
      {
        name: "offset",
        type: "integer",
        description: "Pagination offset. Defaults to 0 (_int('offset', 0)); non-integer values fall back to 0.",
        example: "0"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Matching events ordered newest-first (ORDER BY ts DESC), plus the count returned and the sorted list of declared event names. Each event id is a uuid4 string; ts is ISO-8601 UTC with microseconds.",
        example: {
          events: [
            {
              id: "3f2a8c14-9b1e-4d7a-bc02-1e5f8a9d0c33",
              event_name: "rt.tool.failed",
              ts: "2026-06-17T12:01:33.482190Z",
              actor: "agent",
              payload: { tool: "xsiam.get_cases", error: "timeout" }
            }
          ],
          count: 1,
          declared_events: ["rt.tool.failed"]
        }
      },
      {
        status: "401",
        description: "Missing or invalid MCP bearer token at the embedded MCP boundary (require_bearer), or missing/invalid UI session at the agent middleware boundary (validateSession over the guardian_session cookie)."
      }
    ],
    tags: ["observability", "events", "telemetry"],
  },
  {
    id: "observability-events-post",
    category: "observability",
    method: "POST",
    path: "/api/agent/observability/events",
    summary: "Record one runtime structured event",
    description: "Ingests a single runtime telemetry event into the MCP events.db via /api/v1/observability/events (POST). The event name must be one declared in manifest.observability.events or events.record() returns None and the handler responds 400. The actor is taken from the authenticated principal (request.state.auth_principal) first, falling back to a body-supplied actor, else None. Returns 201 with the new uuid4 row id on success.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["event"],
        properties: {
          event: {
            type: "string",
            description: "Declared event name from manifest.observability.events; must be a non-empty string"
          },
          payload: {
            type: "object",
            description: "Arbitrary JSON object of event detail; must be a dict, defaults to {} when omitted or null"
          },
          actor: {
            type: "string",
            description: "Fallback actor used only when request.state.auth_principal is absent"
          }
        }
      },
      example: {
        event: "rt.tool.failed",
        payload: { tool: "xsiam.get_cases", error: "timeout", instance: "xsoar-v8" }
      }
    },
    responses: [
      {
        status: "201",
        description: "Event recorded; returns recorded:true, the new uuid4 row id, and the echoed event name.",
        example: { recorded: true, id: "7c9e4f02-1a3b-4c8d-9e0f-2b6a1d7c4e85", event: "rt.tool.failed" }
      },
      {
        status: "400",
        description: "Validation/declaration failure. Non-JSON body returns {\"error\":\"Body must be JSON\"}; missing/empty event returns {\"error\":\"`event` is required\"}; non-object payload returns {\"error\":\"`payload` must be a JSON object\"}; an event name not declared in manifest.observability.events returns the recorded:false shape with a reason and declared_events.",
        example: {
          recorded: false,
          reason: "event not declared in manifest.observability.events",
          declared_events: ["rt.tool.failed"]
        }
      },
      {
        status: "401",
        description: "Missing or invalid MCP bearer token (require_bearer), or missing/invalid UI session at the agent middleware (guardian_session cookie)."
      }
    ],
    riskTier: "soft",
    tags: ["observability", "events", "telemetry", "ingest"],
  },
  {
    id: "observability-events-summary",
    category: "observability",
    method: "GET",
    path: "/api/agent/observability/events/summary",
    summary: "Counts-by-name rollup of runtime events",
    description: "Returns an aggregate rollup of the runtime events feed: a counts-by-event-name map (GROUP BY event_name over the entire retention window in events.db), alongside the sorted list of declared event names. Companion to /api/agent/observability/events. The agent route proxies straight to /api/v1/observability/events/summary; no query params are read.",
    responses: [
      {
        status: "200",
        description: "Map of event name to occurrence count (only names with at least one recorded event appear), plus the sorted declared event names.",
        example: {
          counts: { "rt.tool.failed": 7 },
          declared_events: ["rt.tool.failed"]
        }
      },
      {
        status: "401",
        description: "Missing or invalid MCP bearer token (require_bearer), or missing/invalid UI session at the agent middleware (guardian_session cookie)."
      }
    ],
    tags: ["observability", "events", "aggregates"],
  },
  {
    id: "version",
    category: "observability",
    method: "GET",
    path: "/api/agent/version",
    summary: "Running stack version and image digests",
    description: "Native agent route (no MCP proxy; returns NextResponse.json directly) that reports the pinned GUARDIAN_VERSION the agent stack is running, resolved from process.env.GUARDIAN_VERSION then NEXT_PUBLIC_GUARDIAN_VERSION (both.trim()'d), falling back to 'dev'. It also returns per-stack-image content digests for guardian-agent, guardian-updater, and guardian-browser, sourced from the compose-injected DIGEST_GUARDIAN_AGENT/UPDATER/BROWSER env vars; a digest is included only when its value starts with 'sha256:'. The digests object is omitted entirely when no qualifying digests are present (e.g. dev builds). Powers the sidebar version indicator and the About modal.",
    responses: [
      {
        status: "200",
        description: "Version label, plus an optional digests map keyed by compose service name (omitted entirely when no sha256:-prefixed digests are present). No authentication or error branches in the handler itself.",
        example: {
          version: "<running stack version>",
          digests: {
            "guardian-agent": "sha256:abc123",
            "guardian-updater": "sha256:def456",
            "guardian-browser": "sha256:789aaa"
          }
        }
      }
    ],
    tags: ["observability", "version", "digests"],
  },
  {
    id: "update-check",
    category: "observability",
    method: "GET",
    path: "/api/agent/update/check",
    summary: "Compare the running stack against the latest release",
    description: "Proxy route (bearer MCP_TOKEN, 15s AbortSignal timeout) forwarding to guardian-updater's GET /api/v1/version/check. The updater resolves the running stack version, queries the latest published GitHub Release, and resolves each service's target image digest, returning updates_available plus a per-service breakdown (current vs target digest, whether each needs an update). Drives the About modal's 'Update available' banner (the in-place upgrade affordance). Degrades to a soft {updates_available:false,error} body at HTTP 200 — never a 5xx — when the updater is unreachable, so the modal renders 'couldn't check' rather than breaking. Session-cookie/bearer authenticated like the rest of /api/agent/*.",
    responses: [
      {
        status: "200",
        description: "Version-check report. running_version + latest_version + updates_available are present on success; services maps each compose service to {current_version,current_digest,target_digest,update,running}. On updater failure the body is the degraded form {updates_available:false,error} (still 200).",
        example: {
          running_version: "0.2.64",
          latest_version: "0.2.65",
          updates_available: true,
          services: {
            "guardian-agent": {
              current_digest: "sha256:9f1c...",
              target_digest: "sha256:1a2b...",
              update: true,
              running: true
            }
          },
          checked_at: "2026-06-24T10:15:02.441Z"
        }
      }
    ],
    riskTier: "soft",
    tags: ["observability", "update", "version", "release"],
  },
  {
    id: "update-status",
    category: "observability",
    method: "GET",
    path: "/api/agent/update/status",
    summary: "Report whether an in-place update is in progress",
    description: "Proxy route (bearer MCP_TOKEN, 3s AbortSignal timeout) forwarding to guardian-updater's GET /api/v1/update/status. Returns the updater's single-flight in-progress flag so the About modal can re-attach after a page reload — or detect an update started from another tab — without opening a second SSE stream. Degrades to {in_progress:false} at HTTP 200 when the updater is unreachable so the UI stays usable.",
    responses: [
      {
        status: "200",
        description: "Update-lock state. in_progress is true while a POST /api/agent/update/apply run holds the updater's lock. The degraded (updater-unreachable) variant returns the same shape with in_progress:false.",
        example: { in_progress: false }
      }
    ],
    riskTier: "soft",
    tags: ["observability", "update", "status"],
  },
  {
    id: "update-apply",
    category: "observability",
    method: "POST",
    path: "/api/agent/update/apply",
    summary: "Trigger an in-place stack upgrade (SSE progress stream)",
    description: "SSE pass-through (runtime:'nodejs', bearer MCP_TOKEN, request.signal forwarded) to guardian-updater's POST /api/v1/update — the push-button in-place upgrade. Streams typed `phase` / `pull_progress` / `error` events to the About-modal progress panel as the updater fetches the release manifest, compares digests, pulls new images, applies the manifest, and swaps containers. After the `swapping` phase the guardian-agent container is replaced, severing the stream — the client treats a disconnect after `swapping` as an expected restart and polls /api/agent/version until the agent answers, then reloads. The updater holds a single-flight lock for the whole run and returns 409 (passed through verbatim) if one is already active; the UI then re-attaches via /api/agent/update/status rather than starting a second stream. Closing the modal aborts the upstream connection, but the updater's own finally releases the lock independently so the update itself is not interrupted.",
    responses: [
      {
        status: "200",
        description: "text/event-stream of update progress. Frames: `event: phase` (data.phase ∈ checking|fetching_manifest|comparing_digests|pulling|pulled|applying_manifest|swapping|waiting_healthy|complete|noop), `event: pull_progress` (data.service + data.ref), `event: error` (data.detail). The stream ends with a terminal `complete`/`noop` phase, or is severed mid-run by the container swap (expected)."
      },
      {
        status: "409",
        description: "An update is already in progress (the updater's single-flight lock is held). Body passed through verbatim; the UI re-attaches via GET /api/agent/update/status.",
        example: { detail: "update already in progress" }
      },
      {
        status: "502",
        description: "guardian-updater unreachable — the upstream fetch threw before any stream was established.",
        example: "updater unreachable"
      },
      {
        status: "503",
        description: "MCP_TOKEN is not configured in the agent environment, so the route cannot authenticate to the updater.",
        example: "MCP_TOKEN not configured"
      }
    ],
    riskTier: "destructive",
    tags: ["observability", "update", "upgrade", "sse", "updater"],
  },
];

// ─────────────────────────────────────────────────────────────────
// IDENTITY — API keys
// ─────────────────────────────────────────────────────────────────

const IDENTITY: ApiEndpoint[] = [
  {
    id: "api-keys-list",
    category: "identity",
    method: "GET",
    path: "/api/agent/api-keys",
    summary: "List minted API keys",
    description: "Metadata only — id, label, scopes, last_used. Plaintext is unrecoverable post-mint by design.",
    responses: [{ status: "200", description: "Key rows." }],
  },
  {
    id: "api-keys-create",
    category: "identity",
    method: "POST",
    path: "/api/agent/api-keys",
    summary: "Mint a new API key",
    description: "Plaintext returned ONCE in the response. Capture it immediately — no retrieval path.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["label"],
        properties: {
          label: { type: "string" },
          scopes: { type: "array", items: { type: "string" } },
        },
      },
      example: { label: "gh-actions", scopes: ["jobs:write", "audit:read"] },
    },
    responses: [
      {
        status: "201",
        description: "Created. Body includes plaintext (one-time).",
        example: { id: "abc12345", label: "gh-actions", plaintext: "phk_abc12345_…" },
      },
    ],
    riskTier: "credential",
  },
  {
    id: "api-keys-revoke",
    category: "identity",
    method: "DELETE",
    path: "/api/agent/api-keys/{id}",
    summary: "Revoke an API key",
    description: "Permanent — store.verify() returns None for any token derived from this key.",
    pathParams: [{ name: "id", type: "string", description: "Key id (the 8-hex prefix).", example: "abc12345" }],
    responses: [{ status: "200", description: "Revoked." }],
    riskTier: "credential",
  },
  {
    id: "auth-change-password-post",
    category: "identity",
    method: "POST",
    path: "/api/auth/change-password",
    summary: "Change the admin password (requires current password)",
    description: "Native Next.js route backing /profile. Requires the guardian_session cookie (else 401 'Not authenticated') AND the current password as a second factor (a stolen cookie alone cannot rotate the password). Reads {current_password,new_password,confirm_password} from the body and applies route-side validation: current_password and new_password non-empty, new_password===confirm_password, new_password length>=8, and new_password!==current_password (each yields 400 on failure). It then calls lib/auth-store.changePassword(), which POSTs {session_token,current_password,new_password} to the embedded MCP at /api/v1/ui/auth/change_password (confirm_password is consumed by the route and is NOT forwarded to the MCP). The MCP re-verifies the current password against the stored hash, writes the new PBKDF2 hash with mark_changed=true, and revokes ALL of the user's sessions. On success the route clears the guardian_session cookie locally (the operator must re-login) and returns {ok:true}.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["current_password", "new_password", "confirm_password"],
        properties: {
          current_password: {
            type: "string",
            description: "Existing password; re-verified MCP-side as a second factor"
          },
          new_password: {
            type: "string",
            description: "New password, minimum 8 characters, must differ from current_password"
          },
          confirm_password: {
            type: "string",
            description: "Must equal new_password; validated route-side, not forwarded to the MCP"
          }
        }
      },
      example: {
        current_password: "old-pass-123",
        new_password: "new-strong-pass-456",
        confirm_password: "new-strong-pass-456"
      }
    },
    responses: [
      {
        status: "200",
        description: "Password changed. All sessions for the user are revoked server-side and the guardian_session cookie is cleared; the operator must sign in again with the new password.",
        example: { ok: true }
      },
      {
        status: "400",
        description: "Validation error: invalid JSON ('Invalid JSON body'), missing current_password/new_password, new/confirm mismatch, new_password under 8 characters, new equals current, or an MCP-side validation_error.",
        example: { error: "new_password must be at least 8 characters" }
      },
      {
        status: "401",
        description: "No session cookie present ('Not authenticated'), or the session is expired/revoked ('Session expired. Please sign in again.').",
        example: { error: "Not authenticated" }
      },
      {
        status: "403",
        description: "Current password is incorrect.",
        example: { error: "Current password is incorrect" }
      },
      {
        status: "503",
        description: "Embedded MCP auth service unreachable (mcp_unreachable). Includes an optional detail field.",
        example: { error: "Authentication service unavailable. Please retry." }
      }
    ],
    riskTier: "credential",
    tags: ["auth", "password", "credential", "identity"],
  },
  {
    id: "auth-login-post",
    category: "identity",
    method: "POST",
    path: "/api/auth/login",
    summary: "Authenticate admin and set a session cookie",
    description: "Native Next.js route (not a /api/agent proxy). Reads {username,password} from the JSON body, enforces a per-source-IP in-memory sliding-window rate limit (5 failures/60s window -> 60s lockout, keyed off x-forwarded-for/x-real-ip), and rejects any username other than the canonical 'admin' (ADMIN_USERNAME) with the same 401 as a wrong password (no enumeration). On a username match it calls lib/auth-store.login(), which POSTs {username,password,user_agent} to the embedded MCP at /api/v1/ui/auth/login (bearer MCP_TOKEN); the MCP verifies the PBKDF2 password hash, mints a session token, and returns {session_token,expires_at_ms,credentials_changed,username}. The route then sets the guardian_session cookie (HttpOnly, Secure, SameSite=Strict, Max-Age=7200, Path=/) and returns {ok:true,credentialsChanged,username}. The UI uses credentialsChanged=false to redirect first-boot operators to /profile to rotate the default password.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["username", "password"],
        properties: {
          username: {
            type: "string",
            description: "Trimmed; must equal the canonical admin username ('admin'), else 401"
          },
          password: {
            type: "string",
            description: "Operator password, verified MCP-side against the PBKDF2 hash"
          }
        }
      },
      example: { username: "admin", password: "correct-horse-battery-staple" }
    },
    responses: [
      {
        status: "200",
        description: "Authenticated. guardian_session cookie set on the response (HttpOnly, Secure, SameSite=Strict, Max-Age=7200, Path=/).",
        example: { ok: true, credentialsChanged: false, username: "admin" }
      },
      {
        status: "400",
        description: "Invalid JSON body returns {error:'Invalid JSON body'}; missing username or password returns {error:'Username and password are required'}.",
        example: { error: "Username and password are required" }
      },
      {
        status: "401",
        description: "Invalid credentials (wrong password, or any non-admin username). A failure is recorded against the source IP.",
        example: { error: "Invalid credentials" }
      },
      {
        status: "429",
        description: "Too many failed attempts from this IP; locked out. Body includes retryAfter (seconds); a Retry-After header is also set.",
        example: { error: "Too many failed attempts. Try again in 60s.", retryAfter: 60 }
      },
      {
        status: "503",
        description: "Embedded MCP auth service unreachable/misconfigured (mcp_unreachable | transport_error). Not counted as a credentials failure so an outage cannot lock the operator out. Includes an optional detail field.",
        example: { error: "Authentication service unavailable. Please retry." }
      }
    ],
    riskTier: "credential",
    tags: ["auth", "session", "identity"],
  },
  {
    id: "auth-logout-post",
    category: "identity",
    method: "POST",
    path: "/api/auth/logout",
    summary: "Revoke the current session and clear the cookie",
    description: "Native Next.js route. Reads the guardian_session cookie; if a token is present it calls lib/auth-store.logout(token), which busts the local session cache and POSTs {session_token} to the embedded MCP at /api/v1/ui/auth/logout to mark the session revoked (best-effort; any error is swallowed in the route). Always clears the guardian_session cookie locally (Max-Age=0, expires epoch) and returns {ok:true}. Idempotent: succeeds even with no cookie or an already-revoked token, since the operator's intent to end the session is satisfied either way. Sets Cache-Control no-store/no-cache + Pragma no-cache. Takes no request body fields (the token comes from the cookie, not the body).",
    responses: [
      {
        status: "200",
        description: "Session revoked server-side (best-effort) and guardian_session cookie cleared. Always returned, including when no session cookie was present.",
        example: { ok: true }
      }
    ],
    riskTier: "soft",
    tags: ["auth", "session", "identity"],
  },
  {
    id: "auth-status",
    category: "identity",
    method: "GET",
    path: "/api/auth/status",
    summary: "Report whether the session cookie is currently valid",
    description: "Native Next.js route polled by the client-side AuthGate on mount, bfcache restore, and tab-visibility change. Reads the guardian_session cookie and calls lib/auth-store.validateSession(token), which POSTs {session_token} to the embedded MCP at /api/v1/ui/auth/session (positive results cached 30s in-process; negative results never cached so revocation takes effect immediately). Returns {authenticated,credentialsChanged,username}: authenticated=true only for a valid, non-expired, non-revoked token; otherwise authenticated=false, credentialsChanged=false, username=null (the same all-false shape is returned when the MCP is unreachable). Always sets Cache-Control no-store/no-cache + Pragma no-cache so an intermediary can't serve a stale authenticated:true after sign-out.",
    responses: [
      {
        status: "200",
        description: "Authentication state for the presented cookie. When the cookie is missing/expired/revoked or the MCP is unreachable, authenticated=false with credentialsChanged=false and username=null.",
        example: { authenticated: true, credentialsChanged: true, username: "admin" }
      }
    ],
    tags: ["auth", "session", "identity"],
  },
];

// ─────────────────────────────────────────────────────────────────
// WORKFLOWS
// ─────────────────────────────────────────────────────────────────

const WORKFLOWS: ApiEndpoint[] = [
  {
    id: "workflows-list",
    category: "workflows",
    method: "GET",
    path: "/api/agent/workflows",
    summary: "List A2UI workflows",
    description: "Per-bundle declared workflows — chat, setup, etc.",
    responses: [{ status: "200", description: "Workflow list." }],
  },

  {
    id: "workflows-post",
    category: "workflows",
    method: "POST",
    path: "/api/agent/workflows",
    summary: "Resolve a predefined workflow template into a ready prompt",
    description: "Native Next.js route backed by the static agentWorkflows catalog in lib/agent-contract.ts. Despite the POST verb it does NOT create or persist a workflow — it looks up an existing workflow by workflowId, replaceAll-interpolates <key> placeholders in the workflow's prompt with the supplied variables, and returns the resolved prompt plus the workflow's requiredTools and outputs. Used to seed a chat run from a canned SOC workflow.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: [],
        properties: {
          workflowId: { type: "string" },
          variables: { type: "object" }
        }
      },
      example: {
        workflowId: "investigate-case",
        variables: { case_id: "42" }
      }
    },
    responses: [
      {
        status: "200",
        description: "Workflow resolved. Returns agentId (agentContract.metadata.id, 'guardian-soc-agent'), workflowId, the interpolated prompt, requiredTools, and expectedOutputs (mapped from the workflow's outputs field).",
        example: {
          agentId: "guardian-soc-agent",
          workflowId: "investigate-case",
          prompt: "Pick the highest-severity open XSOAR case, fetch its full record and war-room narrative, enrich the related indicators, summarize what happened with the key evidence, and recommend next steps.",
          requiredTools: ["xsoar_get_incident", "xsoar_get_war_room", "xsoar_search_indicators"],
          expectedOutputs: ["case_summary", "evidence_timeline", "recommended_next_steps"]
        }
      },
      {
        status: "404",
        description: "workflowId did not match any entry in agentWorkflows (also returned when the body is not JSON, since the parse falls back to {} and workflowId is undefined). Response is {error:'Unknown workflow', validWorkflowIds:[...]} listing the known ids."
      }
    ],
    tags: ["workflows", "agent-contract", "prompts"],
  },
];

const INVESTIGATION: ApiEndpoint[] = [
  {
    id: "cases",
    category: "investigation",
    method: "GET",
    path: "/api/agent/cases",
    summary: "List investigation cases",
    description: "Thin proxy (the agent proxy) to the embedded MCP at GET /api/v1/cases. Returns every case with a per-case `issue_count` (single-pass LEFT JOIN + GROUP BY over issues), ordered by updated_at then created_at descending. No filters or pagination on this route. Each case object is the Case dataclass fields plus `issue_count`; the campaign-level SVG columns are not on the Case dataclass so they are absent from this lean list (they surface only on the case detail).",
    responses: [
      {
        status: "200",
        description: "Object with `cases` (each = Case dataclass fields + integer `issue_count`) and a `count`.",
        example: {
          cases: [
            {
              id: "b1f2c3d4-0000-4abc-9def-1234567890ab",
              title: "APT29 spearphishing campaign",
              description: "Cluster of phishing-origin issues",
              status: "open",
              created_at: "2026-06-17T12:00:00Z",
              updated_at: "2026-06-17T12:05:00Z",
              issue_count: 3
            }
          ],
          count: 1
        }
      },
      {
        status: "401",
        description: "Caller not authenticated — Next.js middleware rejected the request (no/invalid session cookie and no valid API key). A read API key needs the `agent:read` scope.",
        example: { error: "unauthenticated", code: "no_session_cookie" }
      },
      {
        status: "502",
        description: "Proxy could not reach the embedded MCP (fetch failed / timeout).",
        example: { error: "proxy fetch failed" }
      }
    ],
    tags: ["cases", "investigation"],
  },
  {
    id: "cases-post",
    category: "investigation",
    method: "POST",
    path: "/api/agent/cases",
    summary: "Create an investigation case",
    description: "Thin proxy (the agent proxy) to the embedded MCP at POST /api/v1/cases. Creates a case in InvestigationStore (investigations.db) to group related issues. `title` is required and trimmed; an empty/whitespace title is rejected with 400. `description` is optional. The store assigns a UUID id, sets status to \"open\", and stamps created_at/updated_at. Returns the created Case dataclass (id/title/description/status/created_at/updated_at) — no SVG fields.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["title"],
        properties: {
          title: { type: "string", description: "Case title (trimmed; required, non-empty)" },
          description: { type: "string", description: "Optional free-text case description" }
        }
      },
      example: {
        title: "APT29 spearphishing campaign",
        description: "Cluster of phishing-origin issues across finance dept"
      }
    },
    responses: [
      {
        status: "201",
        description: "Case created. Body is the new Case dataclass (id/title/description/status/created_at/updated_at).",
        example: {
          id: "b1f2c3d4-0000-4abc-9def-1234567890ab",
          title: "APT29 spearphishing campaign",
          description: "Cluster of phishing-origin issues across finance dept",
          status: "open",
          created_at: "2026-06-17T12:00:00Z",
          updated_at: "2026-06-17T12:00:00Z"
        }
      },
      {
        status: "400",
        description: "Invalid JSON body, body not a JSON object, or `title` missing/empty after trim.",
        example: { error: "title is required" }
      },
      {
        status: "401",
        description: "Caller not authenticated — Next.js middleware rejected the request (no/invalid `guardian_session` cookie and no valid API key). Mutations also require an API key with the `agent:write` scope.",
        example: { error: "unauthenticated", code: "no_session_cookie" }
      },
      {
        status: "502",
        description: "Proxy could not reach the embedded MCP (fetch failed / timeout).",
        example: { error: "proxy fetch failed" }
      }
    ],
    riskTier: "soft",
    tags: ["cases", "investigation"],
  },
  {
    id: "cases-by-id-delete",
    category: "investigation",
    method: "DELETE",
    path: "/api/agent/cases/{id}",
    summary: "Delete an investigation case",
    description: "Thin proxy (the agent proxy) to the embedded MCP at DELETE /api/v1/cases/{id}. Removes the case row. Issues that belonged to the case survive: the issues.case_id FK is declared ON DELETE SET NULL, so they become ungrouped rather than deleted. Always returns 200 with a `deleted` boolean (false when no case matched the id — there is no 404 path).",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "Case UUID to delete (URL-encoded by the agent route).",
        required: true,
        example: "b1f2c3d4-0000-4abc-9def-1234567890ab"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Returns whether a case row was removed. `deleted:false` when the id matched nothing (no 404).",
        example: { deleted: true }
      },
      {
        status: "401",
        description: "Caller not authenticated — Next.js middleware rejected the request. A DELETE via API key requires the `agent:write` scope.",
        example: { error: "unauthenticated", code: "no_session_cookie" }
      },
      {
        status: "502",
        description: "Proxy could not reach the embedded MCP (fetch failed / timeout).",
        example: { error: "proxy fetch failed" }
      }
    ],
    riskTier: "destructive",
    tags: ["cases", "investigation"],
  },
  {
    id: "cases-by-id",
    category: "investigation",
    method: "GET",
    path: "/api/agent/cases/{id}",
    summary: "Get one case with its issues",
    description: "Thin proxy (the agent proxy) to the embedded MCP at GET /api/v1/cases/{id}. Returns the Case dataclass fields plus its member issues (full Issue dataclass dicts, fetched via list_issues(case_id=id)), an `issue_count`, and two campaign-level diagram SVG fields — `attack_chain_svg` and `relations_canvas_svg` — read from dedicated case columns and null until the agent generates them. 404 when the id matches no case.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "Case UUID to fetch (URL-encoded by the agent route).",
        required: true,
        example: "b1f2c3d4-0000-4abc-9def-1234567890ab"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Case dataclass fields + `issues` (array of full Issue dicts) + `issue_count` + nullable `attack_chain_svg` and `relations_canvas_svg`. Nested issue dicts carry the Issue dataclass fields only (no per-issue SVG keys).",
        example: {
          id: "b1f2c3d4-0000-4abc-9def-1234567890ab",
          title: "APT29 spearphishing campaign",
          description: "Cluster of phishing-origin issues",
          status: "open",
          created_at: "2026-06-17T12:00:00Z",
          updated_at: "2026-06-17T12:05:00Z",
          issues: [
            {
              id: "a0a0b1b1-2222-4ccc-8ddd-333344445555",
              title: "Phishing email to finance",
              status: "open",
              severity: "high",
              kind: "phishing",
              origin: "operator",
              source_ref: "INC-1001",
              case_id: "b1f2c3d4-0000-4abc-9def-1234567890ab",
              summary: null,
              scope: null,
              recommendations: null,
              conclusions: null,
              next_steps: null,
              created_at: "2026-06-17T12:01:00Z",
              updated_at: "2026-06-17T12:01:00Z"
            }
          ],
          issue_count: 1,
          attack_chain_svg: null,
          relations_canvas_svg: null
        }
      },
      {
        status: "404",
        description: "No case matched the id.",
        example: { error: "case not found" }
      },
      {
        status: "401",
        description: "Caller not authenticated — Next.js middleware rejected the request. A read API key needs the `agent:read` scope.",
        example: { error: "unauthenticated", code: "no_session_cookie" }
      },
      {
        status: "502",
        description: "Proxy could not reach the embedded MCP (fetch failed / timeout).",
        example: { error: "proxy fetch failed" }
      }
    ],
    tags: ["cases", "investigation"],
  },
  {
    id: "cases-by-id-patch",
    category: "investigation",
    method: "PATCH",
    path: "/api/agent/cases/{id}",
    summary: "Update an investigation case",
    description: "Thin proxy (the agent proxy) to the embedded MCP at PATCH /api/v1/cases/{id}. Partial update — the store whitelists only `title`, `description`, and `status` (any other body keys are ignored) and skips fields whose value is null. If no applicable field is supplied the existing case is returned unchanged. Returns the updated Case dataclass, or 404 if the id matches no case.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "Case UUID to update (URL-encoded by the agent route).",
        required: true,
        example: "b1f2c3d4-0000-4abc-9def-1234567890ab"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        properties: {
          title: { type: "string", description: "New case title" },
          description: { type: "string", description: "New case description" },
          status: { type: "string", description: "New case status (e.g. open / closed)" }
        }
      },
      example: { status: "closed", description: "Campaign contained; all member issues resolved" }
    },
    responses: [
      {
        status: "200",
        description: "Updated Case dataclass (id/title/description/status/created_at/updated_at). Also returned unchanged when no whitelisted field was supplied.",
        example: {
          id: "b1f2c3d4-0000-4abc-9def-1234567890ab",
          title: "APT29 spearphishing campaign",
          description: "Campaign contained; all member issues resolved",
          status: "closed",
          created_at: "2026-06-17T12:00:00Z",
          updated_at: "2026-06-17T13:30:00Z"
        }
      },
      {
        status: "400",
        description: "Invalid JSON body or body not a JSON object.",
        example: { error: "body must be a JSON object" }
      },
      {
        status: "404",
        description: "No case matched the id.",
        example: { error: "case not found" }
      },
      {
        status: "401",
        description: "Caller not authenticated — Next.js middleware rejected the request. A PATCH via API key requires the `agent:write` scope.",
        example: { error: "unauthenticated", code: "no_session_cookie" }
      },
      {
        status: "502",
        description: "Proxy could not reach the embedded MCP (fetch failed / timeout).",
        example: { error: "proxy fetch failed" }
      }
    ],
    riskTier: "soft",
    tags: ["cases", "investigation"],
  },
  {
    id: "cases-by-id-issues",
    category: "investigation",
    method: "GET",
    path: "/api/agent/cases/{id}/issues",
    summary: "List issues in a case",
    description: "Thin proxy (the agent proxy) to the embedded MCP at GET /api/v1/cases/{id}/issues. Returns the issues whose case_id matches this case id (full Issue dicts) plus a `count`. The path id is passed straight to store.list_issues as a case_id filter; an id that matches no case simply yields an empty list rather than a 404.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "Case UUID whose member issues are listed (URL-encoded by the agent route).",
        required: true,
        example: "b1f2c3d4-0000-4abc-9def-1234567890ab"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Object with `issues` (array of full Issue dicts in the case) and `count`. Empty list if the case has no issues or the id is unknown.",
        example: {
          issues: [
            {
              id: "a0a0b1b1-2222-4ccc-8ddd-333344445555",
              title: "Phishing email to finance",
              status: "open",
              severity: "high",
              kind: "phishing",
              origin: "operator",
              source_ref: "INC-1001",
              case_id: "b1f2c3d4-0000-4abc-9def-1234567890ab",
              summary: null,
              scope: null,
              recommendations: null,
              conclusions: null,
              next_steps: null,
              created_at: "2026-06-17T12:01:00Z",
              updated_at: "2026-06-17T12:06:00Z"
            }
          ],
          count: 1
        }
      },
      {
        status: "401",
        description: "Caller not authenticated — Next.js middleware rejected the request. A read API key needs the `agent:read` scope.",
        example: { error: "unauthenticated", code: "no_session_cookie" }
      },
      {
        status: "502",
        description: "Proxy could not reach the embedded MCP (fetch failed / timeout).",
        example: { error: "proxy fetch failed" }
      }
    ],
    tags: ["cases", "issues", "investigation"],
  },
  {
    id: "cases-by-id-issues-post",
    category: "investigation",
    method: "POST",
    path: "/api/agent/cases/{id}/issues",
    summary: "Add an issue to a case",
    description: "Thin proxy (the agent proxy) to the embedded MCP at POST /api/v1/cases/{id}/issues. Moves an existing issue under this case by setting issues.case_id (a move, not a copy — an issue belongs to at most one case). Body requires `issue_id`. Returns the updated full Issue dict. 404 if the case does not exist OR the issue id matches no row.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "Target case UUID the issue is added to (URL-encoded by the agent route).",
        required: true,
        example: "b1f2c3d4-0000-4abc-9def-1234567890ab"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["issue_id"],
        properties: {
          issue_id: { type: "string", description: "UUID of the existing issue to move under this case" }
        }
      },
      example: { issue_id: "a0a0b1b1-2222-4ccc-8ddd-333344445555" }
    },
    responses: [
      {
        status: "200",
        description: "Updated full Issue dict, now carrying this case_id.",
        example: {
          id: "a0a0b1b1-2222-4ccc-8ddd-333344445555",
          title: "Phishing email to finance",
          status: "open",
          severity: "high",
          kind: "phishing",
          origin: "operator",
          source_ref: "INC-1001",
          case_id: "b1f2c3d4-0000-4abc-9def-1234567890ab",
          summary: null,
          scope: null,
          recommendations: null,
          conclusions: null,
          next_steps: null,
          created_at: "2026-06-17T12:01:00Z",
          updated_at: "2026-06-17T12:06:00Z"
        }
      },
      {
        status: "400",
        description: "Invalid JSON body, body not a JSON object, or `issue_id` missing/empty.",
        example: { error: "issue_id is required" }
      },
      {
        status: "404",
        description: "The case was not found, or the issue id matched no row.",
        example: { error: "issue or case not found" }
      },
      {
        status: "401",
        description: "Caller not authenticated — Next.js middleware rejected the request. A POST via API key requires the `agent:write` scope.",
        example: { error: "unauthenticated", code: "no_session_cookie" }
      },
      {
        status: "502",
        description: "Proxy could not reach the embedded MCP (fetch failed / timeout).",
        example: { error: "proxy fetch failed" }
      }
    ],
    riskTier: "soft",
    tags: ["cases", "issues", "investigation"],
  },
  {
    id: "indicators",
    category: "investigation",
    method: "GET",
    path: "/api/agent/indicators",
    summary: "List indicators (IOCs)",
    description: "Lists deduped indicators of compromise from the investigation store, each annotated with an issue_count (distinct linked issues). Optional filters by type or by a linked issue_id. This REST surface is read-only; indicators are written by the agent's indicator_upsert MCP tool, not here. Proxies to the embedded MCP at GET /api/v1/indicators.",
    queryParams: [
      {
        name: "type",
        type: "string",
        description: "Filter by indicator type. Lowercased server-side before matching. Free-form; the store does not enforce an enum, but the common values are ip, domain, url, file_hash, email, cve, host, account.",
        example: "ip"
      },
      {
        name: "issue_id",
        type: "string",
        description: "Filter to indicators linked (via indicator_issues) to a specific issue id.",
        example: "b1c2d3e4-e5f6-7890-abcd-ef1234567890"
      }
    ],
    responses: [
      {
        status: "200",
        description: "{indicators, count}. indicators is ordered last_seen DESC, created_at DESC; each item is the full Indicator record (id, value, type, dbot_score, enrichment, source, first_seen, last_seen, created_at, updated_at) plus an added issue_count.",
        example: {
          indicators: [
            {
              id: "a1b2c3",
              value: "185.220.101.5",
              type: "ip",
              dbot_score: 3,
              enrichment: "{\"vendor\":\"VirusTotal\"}",
              source: "guardian",
              first_seen: "2026-06-15T10:00:00Z",
              last_seen: "2026-06-16T12:00:00Z",
              created_at: "2026-06-15T10:00:00Z",
              updated_at: "2026-06-16T12:00:00Z",
              issue_count: 2
            }
          ],
          count: 1
        }
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    tags: ["investigation", "indicators", "ioc", "read-only"],
  },
  {
    id: "indicators-by-id",
    category: "investigation",
    method: "GET",
    path: "/api/agent/indicators/{id}",
    summary: "Get one indicator with issues and relationships",
    description: "Returns a single indicator record, the issues it is linked to (each as id/title/kind/status/source_ref), and its STIX-style relationship edges. Proxies to the embedded MCP at GET /api/v1/indicators/{id}.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The indicator's store id (UUID primary key).",
        required: true,
        example: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
      }
    ],
    responses: [
      {
        status: "200",
        description: "The Indicator record fields, an issues[] array of linked issues (each {id,title,kind,status,source_ref}), and a relationships[] array. Each relationship is the FULL relationships row: id, source_id, source_type, target_value, target_type, relationship_type, description, source, first_seen, last_seen.",
        example: {
          id: "a1b2c3",
          value: "185.220.101.5",
          type: "ip",
          dbot_score: 3,
          enrichment: null,
          source: "guardian",
          first_seen: "2026-06-15T10:00:00Z",
          last_seen: "2026-06-16T12:00:00Z",
          created_at: "2026-06-15T10:00:00Z",
          updated_at: "2026-06-16T12:00:00Z",
          issues: [
            {
              id: "i1",
              title: "Suspicious egress",
              kind: "alert",
              status: "open",
              source_ref: "INCIDENT-42"
            }
          ],
          relationships: [
            {
              id: "r1",
              source_id: "a1b2c3",
              source_type: "ip",
              target_value: "evil.example",
              target_type: "domain",
              relationship_type: "communicates-with",
              description: null,
              source: "guardian",
              first_seen: "2026-06-16T12:00:00Z",
              last_seen: "2026-06-16T12:00:00Z"
            }
          ]
        }
      },
      {
        status: "404",
        description: "No indicator with that id: {\"error\":\"indicator not found\"}."
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    tags: ["investigation", "indicators", "ioc", "relationships", "read-only"],
  },
  {
    id: "issues",
    category: "investigation",
    method: "GET",
    path: "/api/agent/issues",
    summary: "List issues",
    description: "Lists local investigation tracking items, optionally filtered by status or case_id, with a sourceless-issue exclusion and an ordering toggle the autonomous investigation loop relies on. Proxies to the embedded MCP at GET /api/v1/issues.",
    queryParams: [
      {
        name: "status",
        type: "string",
        description: "Filter by issue status. Free-form; common values open, investigating, resolved, closed.",
        example: "open"
      },
      {
        name: "case_id",
        type: "string",
        description: "Filter to issues grouped under a specific case id.",
        example: "c1d2e3f4-a5b6-7890-abcd-ef1234567890"
      },
      {
        name: "source_ref_not_null",
        type: "boolean",
        description: "When the value lowercases to 1/true/yes, excludes issues with NULL or empty/whitespace source_ref (manual issues with no upstream incident to fetch). Any other value (or absent) = false.",
        example: "true"
      },
      {
        name: "order",
        type: "string",
        description: "Sort order. 'asc' sorts oldest-first (created_at ASC, updated_at ASC) for the loop's deterministic oldest-open pick; default 'desc' is newest-first (updated_at DESC, created_at DESC) for the UI.",
        example: "desc",
        enum: ["asc", "desc"]
      }
    ],
    responses: [
      {
        status: "200",
        description: "{issues, count}. issues is an array of full Issue DTOs.",
        example: {
          issues: [
            {
              id: "b1c2d3e4-e5f6-7890-abcd-ef1234567890",
              title: "Suspicious PowerShell on host-12",
              status: "open",
              severity: "high",
              kind: "alert",
              origin: "operator",
              source_ref: "INCIDENT-42",
              case_id: null,
              summary: null,
              scope: null,
              recommendations: null,
              conclusions: null,
              next_steps: null,
              created_at: "2026-06-17T09:00:00Z",
              updated_at: "2026-06-17T09:00:00Z"
            }
          ],
          count: 1
        }
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    tags: ["investigation", "issues", "read-only"],
  },
  {
    id: "issues-post",
    category: "investigation",
    method: "POST",
    path: "/api/agent/issues",
    summary: "Create an issue",
    description: "Creates a local investigation tracking item (issue). title is required (trimmed; empty rejected). kind, severity, origin default server-side to other/medium/operator; source_ref, scope, summary are optional. status is always forced to 'open' on create; case_id, recommendations, conclusions, next_steps are not settable on create (start null). Proxies to the embedded MCP at POST /api/v1/issues.",
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        required: ["title"],
        properties: {
          title: { type: "string" },
          kind: { type: "string", default: "other" },
          severity: { type: "string", default: "medium" },
          origin: { type: "string", default: "operator" },
          source_ref: { type: "string" },
          scope: { type: "string" },
          summary: { type: "string" }
        }
      },
      example: {
        title: "Suspicious PowerShell on host-12",
        kind: "alert",
        severity: "high",
        origin: "operator",
        source_ref: "INCIDENT-42",
        scope: "host-12",
        summary: "Encoded command spawned from Office"
      }
    },
    responses: [
      {
        status: "201",
        description: "The created Issue record (full DTO: id, title, status, severity, kind, origin, source_ref, case_id, summary, scope, recommendations, conclusions, next_steps, created_at, updated_at).",
        example: {
          id: "b1c2d3e4-e5f6-7890-abcd-ef1234567890",
          title: "Suspicious PowerShell on host-12",
          status: "open",
          severity: "high",
          kind: "alert",
          origin: "operator",
          source_ref: "INCIDENT-42",
          case_id: null,
          summary: "Encoded command spawned from Office",
          scope: "host-12",
          recommendations: null,
          conclusions: null,
          next_steps: null,
          created_at: "2026-06-17T09:00:00Z",
          updated_at: "2026-06-17T09:00:00Z"
        }
      },
      {
        status: "400",
        description: "title missing/empty after trim ({\"error\":\"title is required\"}); or invalid JSON body ({\"error\":\"invalid JSON body:...\"}); or body is not a JSON object ({\"error\":\"body must be a JSON object\"})."
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    riskTier: "soft",
    tags: ["investigation", "issues", "create"],
  },
  {
    id: "issues-by-id-delete",
    category: "investigation",
    method: "DELETE",
    path: "/api/agent/issues/{id}",
    summary: "Delete an issue",
    description: "Removes an issue and cascades its timeline events (issue_events FK ON DELETE CASCADE). Returns a deleted boolean rather than 404 when the id did not exist. Proxies to the embedded MCP at DELETE /api/v1/issues/{id}.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The issue id (UUID) to delete.",
        required: true,
        example: "b1c2d3e4-e5f6-7890-abcd-ef1234567890"
      }
    ],
    responses: [
      {
        status: "200",
        description: "Deletion result. deleted=true if a row was removed, false if no issue had that id (no 404 branch).",
        example: { deleted: true }
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    riskTier: "destructive",
    tags: ["investigation", "issues", "delete"],
  },
  {
    id: "issues-by-id",
    category: "investigation",
    method: "GET",
    path: "/api/agent/issues/{id}",
    summary: "Get one issue with timeline and case",
    description: "Returns a single issue's full record plus its timeline events, its parent case (if grouped), and the attack-chain / relations-canvas SVGs (null until the agent generates them). The SVGs ride on the detail response only — they are kept off the lean list. Proxies to the embedded MCP at GET /api/v1/issues/{id}.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The issue id (UUID) to fetch.",
        required: true,
        example: "b1c2d3e4-e5f6-7890-abcd-ef1234567890"
      }
    ],
    responses: [
      {
        status: "200",
        description: "The Issue DTO spread, plus events[] (timeline, oldest-first), case (parent Case object or null), attack_chain_svg (string|null), and relations_canvas_svg (string|null).",
        example: {
          id: "b1c2d3e4-e5f6-7890-abcd-ef1234567890",
          title: "Suspicious PowerShell on host-12",
          status: "open",
          severity: "high",
          kind: "alert",
          origin: "operator",
          source_ref: "INCIDENT-42",
          case_id: null,
          summary: null,
          scope: null,
          recommendations: null,
          conclusions: null,
          next_steps: null,
          created_at: "2026-06-17T09:00:00Z",
          updated_at: "2026-06-17T09:00:00Z",
          events: [
            {
              id: "e1",
              issue_id: "b1c2d3e4-e5f6-7890-abcd-ef1234567890",
              ts: "2026-06-17T09:05:00Z",
              type: "note",
              content: "Triage started"
            }
          ],
          case: null,
          attack_chain_svg: null,
          relations_canvas_svg: null
        }
      },
      { status: "404", description: "No issue with that id: {\"error\":\"issue not found\"}." },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    tags: ["investigation", "issues", "timeline", "read-only"],
  },
  {
    id: "issues-by-id-patch",
    category: "investigation",
    method: "PATCH",
    path: "/api/agent/issues/{id}",
    summary: "Update an issue",
    description: "Partial update of an issue. Only the recognized fields are applied (title, status, severity, kind, summary, scope, recommendations, conclusions, next_steps); any other key (including origin, source_ref, case_id) is ignored, and null values are skipped. updated_at is bumped when at least one field is set. Proxies to the embedded MCP at PATCH /api/v1/issues/{id}.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The issue id (UUID) to update.",
        required: true,
        example: "b1c2d3e4-e5f6-7890-abcd-ef1234567890"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        properties: {
          title: { type: "string" },
          status: { type: "string" },
          severity: { type: "string" },
          kind: { type: "string" },
          summary: { type: "string" },
          scope: { type: "string" },
          recommendations: { type: "string" },
          conclusions: { type: "string" },
          next_steps: { type: "string" }
        }
      },
      example: {
        status: "closed",
        conclusions: "Confirmed true positive",
        next_steps: "Monitor host-12 for 7 days"
      }
    },
    responses: [
      {
        status: "200",
        description: "The updated Issue record (full DTO).",
        example: {
          id: "b1c2d3e4-e5f6-7890-abcd-ef1234567890",
          title: "Suspicious PowerShell on host-12",
          status: "closed",
          severity: "high",
          kind: "alert",
          origin: "operator",
          source_ref: "INCIDENT-42",
          case_id: null,
          summary: "Contained",
          scope: "host-12",
          recommendations: "Reimage host",
          conclusions: "Confirmed TP",
          next_steps: "Monitor",
          created_at: "2026-06-17T09:00:00Z",
          updated_at: "2026-06-17T11:30:00Z"
        }
      },
      {
        status: "404",
        description: "No issue with that id: {\"error\":\"issue not found\"}. Note: returned only when the UPDATE matched no row AND at least one recognized field was provided; a body with no recognized fields short-circuits to a get_issue lookup (which would itself 404 only for a missing id — see groundingNote)."
      },
      {
        status: "400",
        description: "Invalid JSON body ({\"error\":\"invalid JSON body:...\"}) or body is not a JSON object ({\"error\":\"body must be a JSON object\"})."
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    riskTier: "soft",
    tags: ["investigation", "issues", "update"],
  },
  {
    id: "issues-by-id-events",
    category: "investigation",
    method: "GET",
    path: "/api/agent/issues/{id}/events",
    summary: "List an issue's timeline events",
    description: "Returns the activity-timeline events for an issue (oldest-first) plus a count. Returns an empty list (not 404) if the issue id has no events or does not exist. Proxies to the embedded MCP at GET /api/v1/issues/{id}/events.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The issue id (UUID) whose timeline to list.",
        required: true,
        example: "b1c2d3e4-e5f6-7890-abcd-ef1234567890"
      }
    ],
    responses: [
      {
        status: "200",
        description: "{events, count}. events is an array of IssueEvent records ordered seq ASC (oldest-first). Empty list (not 404) when the issue has no events or the id does not exist.",
        example: {
          events: [
            {
              id: "e1",
              issue_id: "b1c2d3e4-e5f6-7890-abcd-ef1234567890",
              ts: "2026-06-17T09:05:00Z",
              type: "note",
              content: "Triage started"
            }
          ],
          count: 1
        }
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    tags: ["investigation", "issues", "events", "timeline", "read-only"],
  },
  {
    id: "issues-by-id-events-post",
    category: "investigation",
    method: "POST",
    path: "/api/agent/issues/{id}/events",
    summary: "Append a timeline event",
    description: "Appends an activity-timeline event to an issue and bumps the issue's updated_at. type defaults to 'note' and content to '' when omitted or null. Returns 404 if the issue does not exist. Proxies to the embedded MCP at POST /api/v1/issues/{id}/events.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The issue id (UUID) to append the event to.",
        required: true,
        example: "b1c2d3e4-e5f6-7890-abcd-ef1234567890"
      }
    ],
    body: {
      contentType: "application/json",
      schema: {
        type: "object",
        properties: {
          type: { type: "string", default: "note" },
          content: { type: "string", default: "" }
        }
      },
      example: { type: "note", content: "Triage started; isolating host-12" }
    },
    responses: [
      {
        status: "201",
        description: "The created IssueEvent record (id, issue_id, ts, type, content).",
        example: {
          id: "e1f2a3b4-c5d6-7890-abcd-ef1234567890",
          issue_id: "b1c2d3e4-e5f6-7890-abcd-ef1234567890",
          ts: "2026-06-17T09:05:00Z",
          type: "note",
          content: "Triage started; isolating host-12"
        }
      },
      {
        status: "404",
        description: "No issue with that id: {\"error\":\"issue not found\"} (add_event returns None when the issue is absent)."
      },
      {
        status: "400",
        description: "Invalid JSON body ({\"error\":\"invalid JSON body:...\"}) or body is not a JSON object ({\"error\":\"body must be a JSON object\"})."
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    riskTier: "soft",
    tags: ["investigation", "issues", "events", "timeline", "create"],
  },
  {
    id: "issues-by-id-report",
    category: "investigation",
    method: "GET",
    path: "/api/agent/issues/{id}/report",
    summary: "Fetch an issue's generated report",
    description: "Returns the generated closure-report markdown for an issue as {issue_id, report}. Returns 404 if the issue does not exist or no report has been generated yet. Proxies to the embedded MCP at GET /api/v1/issues/{id}/report.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The issue id (UUID) whose report to fetch.",
        required: true,
        example: "b1c2d3e4-e5f6-7890-abcd-ef1234567890"
      }
    ],
    responses: [
      {
        status: "200",
        description: "{issue_id, report}. report is the full markdown closure document for the issue.",
        example: {
          issue_id: "b1c2d3e4-e5f6-7890-abcd-ef1234567890",
          report: "# Investigation report\n\n## Summary\nConfirmed true positive; host-12 reimaged.\n"
        }
      },
      {
        status: "404",
        description: "No issue with that id ({\"error\":\"issue not found\"}), or the issue exists but has no report yet ({\"error\":\"no report generated for this issue yet\"})."
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    tags: ["investigation", "issues", "report", "read-only"],
  },
  {
    id: "cases-by-id-related",
    category: "investigation",
    method: "GET",
    path: "/api/agent/cases/{id}/related",
    summary: "List a case's related cases",
    description: "Returns the typed cross-case links touching a case as {related, count}. Each entry carries the relationship_type, an optional note, a direction (incoming/outgoing relative to this case), and the other case's id/title/status. Returns 404 if the case does not exist. Proxies to the embedded MCP at GET /api/v1/cases/{id}/related.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The case id (UUID) whose related cases to list.",
        required: true,
        example: "c0ffee00-1234-5678-9abc-def012345678"
      }
    ],
    responses: [
      {
        status: "200",
        description: "{related, count}. related is an array of typed cross-case edges, each with the other case's id/title/status and the edge direction.",
        example: {
          related: [
            {
              relationship_type: "duplicate-of",
              note: "Same campaign, different tenant",
              direction: "outgoing",
              other_case: {
                id: "deadbeef-1111-2222-3333-444455556666",
                title: "APT29 follow-on intrusion",
                status: "open"
              }
            }
          ],
          count: 1
        }
      },
      {
        status: "404",
        description: "No case with that id: {\"error\":\"case not found\"}."
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    tags: ["investigation", "cases", "relationships", "campaign", "read-only"],
  },
  {
    id: "techniques-by-id-issues",
    category: "investigation",
    method: "GET",
    path: "/api/agent/techniques/{techniqueId}/issues",
    summary: "List issues mapped to an ATT&CK technique",
    description: "Returns issues whose structured technique_mappings include the given ATT&CK technique id as {issues, count}. Drives cross-issue ATT&CK pivots (\"what else exhibits T1566?\"). Proxies to the embedded MCP at GET /api/v1/techniques/{technique_id}/issues.",
    pathParams: [
      {
        name: "techniqueId",
        type: "string",
        description: "The ATT&CK technique id (e.g. T1566 or a sub-technique like T1566.001).",
        required: true,
        example: "T1566"
      }
    ],
    responses: [
      {
        status: "200",
        description: "{issues, count}. issues is an array of Issue dicts mapped to the technique.",
        example: { issues: [], count: 0 }
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    tags: ["investigation", "issues", "attack", "read-only"],
  },
  {
    id: "playbooks-by-doc-issues",
    category: "investigation",
    method: "GET",
    path: "/api/agent/playbooks/{docId}/issues",
    summary: "List issues matched to a playbook",
    description: "Returns issues whose structured playbook_matches reference the given playbook doc id as {issues, count}. Surfaces which investigations a playbook has been matched against. Proxies to the embedded MCP at GET /api/v1/playbooks/{doc_id}/issues.",
    pathParams: [
      {
        name: "docId",
        type: "string",
        description: "The playbook doc id (knowledge-base / playbook document identifier).",
        required: true,
        example: "soc-investigation/phishing-triage"
      }
    ],
    responses: [
      {
        status: "200",
        description: "{issues, count}. issues is an array of Issue dicts matched to the playbook.",
        example: { issues: [], count: 0 }
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    tags: ["investigation", "issues", "playbooks", "read-only"],
  },
  {
    id: "issues-by-id-stix",
    category: "investigation",
    method: "GET",
    path: "/api/agent/issues/{id}/stix",
    summary: "Export an issue as a STIX 2.1 bundle",
    description: "Assembles and returns the issue (its indicators and relationships) as a STIX 2.1 bundle (application/json) suitable for sharing with threat-intel platforms. Returns 404 if the issue does not exist. Proxies to the embedded MCP at GET /api/v1/issues/{id}/stix.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The issue id (UUID) to export as STIX.",
        required: true,
        example: "b1c2d3e4-e5f6-7890-abcd-ef1234567890"
      }
    ],
    responses: [
      {
        status: "200",
        description: "A STIX 2.1 bundle object: {type:\"bundle\", id, objects:[...]} where objects are the issue's STIX SDOs/SROs (indicators, relationships, etc.).",
        example: {
          type: "bundle",
          id: "bundle--a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          objects: [
            {
              type: "indicator",
              spec_version: "2.1",
              id: "indicator--11111111-2222-3333-4444-555566667777",
              pattern: "[ipv4-addr:value = '203.0.113.7']",
              pattern_type: "stix"
            }
          ]
        }
      },
      {
        status: "404",
        description: "No issue with that id: {\"error\":\"issue not found\"}."
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    tags: ["investigation", "issues", "stix", "export", "read-only"],
  },
  {
    id: "cases-by-id-stix",
    category: "investigation",
    method: "GET",
    path: "/api/agent/cases/{id}/stix",
    summary: "Export a case as a STIX 2.1 bundle",
    description: "Assembles and returns the case (campaign) as a STIX 2.1 bundle (application/json), rolling up the STIX objects across its grouped issues for sharing with threat-intel platforms. Returns 404 if the case does not exist. Proxies to the embedded MCP at GET /api/v1/cases/{id}/stix.",
    pathParams: [
      {
        name: "id",
        type: "string",
        description: "The case id (UUID) to export as STIX.",
        required: true,
        example: "c0ffee00-1234-5678-9abc-def012345678"
      }
    ],
    responses: [
      {
        status: "200",
        description: "A campaign-level STIX 2.1 bundle object: {type:\"bundle\", id, objects:[...]} aggregating the STIX SDOs/SROs across the case's issues.",
        example: {
          type: "bundle",
          id: "bundle--c0ffee00-1234-5678-9abc-def012345678",
          objects: [
            {
              type: "campaign",
              spec_version: "2.1",
              id: "campaign--88889999-aaaa-bbbb-cccc-ddddeeeeffff",
              name: "APT29 follow-on intrusion"
            }
          ]
        }
      },
      {
        status: "404",
        description: "No case with that id: {\"error\":\"case not found\"}."
      },
      {
        status: "401",
        description: "Agent middleware rejected the request: no/invalid guardian_session cookie and no valid guardian_ak_* bearer API key."
      }
    ],
    tags: ["investigation", "cases", "stix", "campaign", "export", "read-only"],
  },
];

export const API_ENDPOINTS: ApiEndpoint[] = [
  ...COGNITIVE,
  ...CONFIGURATION,
  ...OPERATIONS,
  ...SELF_MOD,
  ...OBSERVABILITY,
  ...IDENTITY,
  ...WORKFLOWS,
  ...INVESTIGATION,
];

// ─── Helpers ─────────────────────────────────────────────────────

export function getEndpointById(id: string): ApiEndpoint | undefined {
  return API_ENDPOINTS.find((e) => e.id === id);
}

export function getEndpointsByCategory(c: ApiCategory): ApiEndpoint[] {
  return API_ENDPOINTS.filter((e) => e.category === c);
}

export function searchEndpoints(query: string): ApiEndpoint[] {
  const q = query.trim().toLowerCase();
  if (!q) return API_ENDPOINTS;
  return API_ENDPOINTS.filter((e) => {
    return (
      e.summary.toLowerCase().includes(q) ||
      e.description.toLowerCase().includes(q) ||
      e.path.toLowerCase().includes(q) ||
      e.method.toLowerCase().includes(q) ||
      e.category.includes(q)
    );
  });
}
