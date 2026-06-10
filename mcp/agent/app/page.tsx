"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ApprovalCard } from "@/components/chat/approval-card";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageList } from "@/components/chat/message-list";
import { ChatHeader } from "@/components/chat/chat-header";
import { DebugPanel } from "@/components/chat/debug-panel";
import {
  SessionSidebar,
  type SessionSummary,
} from "@/components/chat/session-sidebar";
import { useChat } from "@/components/chat/use-chat";

// Stable localStorage key for the debug panel toggle. Lives at module
// scope so the constant doesn't re-allocate per render and stays
// trivially greppable from elsewhere.
const DEBUG_PANEL_KEY = "phantom.chat.debug-panel.open";
import type { ChatMessage } from "@/lib/api/chat";
import {
  listChatSessions,
  deleteSession,
  exportSession,
  patchSession,
  getSessionTranscript,
} from "@/lib/api/sessions";
import { listModels } from "@/lib/api/models";
import type { ModelInfo, Session } from "@/lib/api/types";
import { SparkLogo } from "@/components/sidebar";

// ─── Quick Action Chips (phantom-flavored) ──────────────────────────────────

const QUICK_ACTIONS = [
  { label: "Health Check", icon: "monitor_heart", prompt: "Run a system health check across the MCP and connector instances" },
  { label: "List Skills", icon: "auto_awesome", prompt: "Show me available skills" },
  { label: "Open Cases", icon: "folder_open", prompt: "Show me the open cases and issues from the tenant" },
  { label: "Run XQL", icon: "query_stats", prompt: "Author and run an XQL query to count agent events by host over the last 24 hours" },
  { label: "Asset Lookup", icon: "devices", prompt: "List the assets known to the tenant and summarize what's inventoried" },
  { label: "List Connectors", icon: "cable", prompt: "Show me the active connector instances and their status" },
] as const;

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * The Spark-ported `Session` type expects `session_id` / `last_active_at`
 * / `last_model` / `total_input_tokens` / `metadata` — none of which our
 * phantom MCP returns. The MCP shape is `{id, user, started_at, ended_at,
 * title, meta, message_count}`. Rather than coerce both servers into one
 * type (the Spark type is used by other Spark-port pages we may revive),
 * we read fields off a permissive `Record<string, unknown>` and fall
 * through Spark → phantom names. This keeps the chat page working today
 * without touching every other consumer of the Spark Session type.
 */
function readStr(obj: Record<string, unknown>, ...keys: string[]): string {
  for (const k of keys) {
    const v = obj[k];
    if (typeof v === "string" && v) return v;
  }
  return "";
}

function toSessionSummary(
  session: Session | Record<string, unknown>,
  model: string,
): SessionSummary {
  const s = session as Record<string, unknown>;
  // Title comes from MCP's top-level `title`, then `meta.title`, then
  // (Spark fallback) metadata.title, finally session_key.
  const meta = (s.meta ?? s.metadata) as Record<string, unknown> | null;
  const title =
    readStr(s, "title") ||
    (typeof meta?.title === "string" ? meta.title : "") ||
    readStr(s, "session_key");
  const id = readStr(s, "id", "session_id");
  const tokensStr = readStr(s, "total_input_tokens");
  // v0.5.38 / Issue #30 UI gap fill — parent_id from the v0.5.30
  // sessions schema. Forked sessions render under their parent.
  // Non-fork rows have parent_id NULL / undefined.
  const parentId =
    typeof s.parent_id === "string" && s.parent_id ? s.parent_id : null;
  return {
    id,
    firstMessage: title || (id ? `${id.slice(0, 12)}...` : "(untitled)"),
    // Also surface the title on the dedicated field so optimistic
    // rename updates stay coherent across reload (rename writes
    // session.title locally; toSessionSummary writes the same thing
    // when the page reloads from MCP).
    title: title || undefined,
    timestamp:
      readStr(s, "last_active_at", "updated_at", "started_at", "created_at"),
    modelBadge: readStr(s, "last_model") || model || "auto",
    tokenCount: tokensStr ? parseInt(tokensStr, 10) || 0 : 0,
    parentId,
  };
}

function downloadBlob(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

const MIME_TYPES: Record<string, string> = {
  yaml: "text/yaml",
  json: "application/json",
  markdown: "text/markdown",
  // v0.2.3 — wire-event trace export (JSON-shaped event-list timeline
  // derived from messages + meta). Distinct mime-type record from
  // `json` so a future UI distinction (e.g. icon, viewer) has hooks.
  events: "application/json",
};

const FILE_EXTS: Record<string, string> = {
  yaml: "yml",
  json: "json",
  markdown: "md",
  // v0.2.3 — `.events.json` so operators can tell the trace export
  // apart from the full-session `json` export at a glance in their
  // downloads folder.
  events: "events.json",
};

// ─── Page Component ──────────────────────────────────────────────────────────

export default function ChatPage() {
  // Session sidebar state
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isLoadingSession, setIsLoadingSession] = useState(false);

  // Available models
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);

  // Chat hook — phantom is single-tenant, so no workspace defaults; the
  // chat handler picks the model from the runtime config (Vertex/Gemini).
  const {
    messages,
    isStreaming,
    sessionId,
    runId,
    toolCalls,
    events,
    pendingApprovals,
    resolveApproval,
    telemetryStats,
    subagents,
    sendMessage,
    resetChat,
    clearTelemetry,
    loadSession,
    currentModel,
    currentProvider,
    setModel,
    // v0.17.85 — chatRoute is still exposed by useChat (derived from
    // overrideProvider) but no longer destructured here. The toggle
    // button that consumed it on the chat header is gone; selecting
    // claude-code from the model dropdown now drives the route.
  } = useChat();

  // Right-side debug panel — defaults to closed; persisted in
  // localStorage so the operator's preference survives a reload.
  const [debugPanelOpen, setDebugPanelOpen] = useState(false);
  useEffect(() => {
    const stored = localStorage.getItem(DEBUG_PANEL_KEY);
    if (stored === "true") setDebugPanelOpen(true);
  }, []);
  const toggleDebugPanel = useCallback(() => {
    setDebugPanelOpen((prev) => {
      const next = !prev;
      localStorage.setItem(DEBUG_PANEL_KEY, String(next));
      return next;
    });
  }, []);

  // v0.6.6 — subagent toggle. Defaults to true; persisted to
  // operator_state.db (NOT localStorage) per CLAUDE.md three-category
  // state model: this is operator-personal progress (a workflow
  // preference) that should follow them across devices. Optimistic
  // update + fire-and-forget PUT for snappy UX; on PUT failure we
  // log but don't revert (the next mount fetch will reconcile).
  const [subagentsEnabled, setSubagentsEnabled] = useState(true);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch(
          "/api/agent/operator-state/chat_subagents_enabled",
          { method: "GET", cache: "no-store" },
        );
        if (cancelled) return;
        if (resp.status === 404) {
          // Never set — default to enabled. Don't write; let the first
          // toggle persist the explicit choice.
          return;
        }
        if (resp.ok) {
          const body = await resp.json().catch(() => null);
          if (cancelled) return;
          const raw = body?.value;
          if (typeof raw === "boolean") setSubagentsEnabled(raw);
          else if (raw && typeof raw === "object" && "enabled" in raw)
            setSubagentsEnabled(Boolean(raw.enabled));
        }
      } catch {
        // network blip — keep default ON.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  const toggleSubagents = useCallback(() => {
    setSubagentsEnabled((prev) => {
      const next = !prev;
      void fetch("/api/agent/operator-state/chat_subagents_enabled", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: next }),
      }).catch((err) => {
        // eslint-disable-next-line no-console
        console.warn("[chat] failed to persist subagents toggle:", err);
      });
      return next;
    });
  }, []);

  // Fetch available models on mount
  useEffect(() => {
    listModels().then((result) => {
      if (result.ok) setAvailableModels(result.data);
    });
  }, []);

  // Fetch sessions list on mount.
  //
  // v0.3.6 — server-side filter via `exclude_scheduled=true` drops
  // job-driven sessions (rows tagged `meta.scheduled_by=<job-name>` by
  // the chat-route when X-Phantom-Trigger is `job:*`) at the SQL layer.
  // Pre-v0.3.6 the filter ran client-side AFTER the fetch, which broke
  // on busy installs whose 50-row default window was 100% scheduled
  // sessions — the filter dropped all 50 and the sidebar showed empty
  // even though the operator had dozens of human sessions further back
  // in history. The server-side variant uses sqlite's json_extract
  // (`json_extract(meta_json, '$.scheduled_by') IS NULL`) so the 500-
  // row cap is filled with operator-relevant rows, not scheduler churn.
  useEffect(() => {
    void (async () => {
      const result = await listChatSessions({ excludeScheduled: true });
      if (result.ok) {
        const sorted = [...result.data].sort(
          (a, b) =>
            new Date(b.last_active_at || b.created_at).getTime() -
            new Date(a.last_active_at || a.created_at).getTime()
        );
        setSessions(sorted.map((s) => toSessionSummary(s, "auto")));
      }
    })();
  }, []);

  // Track current sessionId
  useEffect(() => {
    if (sessionId) setActiveSessionId(sessionId);
  }, [sessionId]);

  // v0.1.27 — per-session approval mode. Persisted in
  // session.metadata.approval_mode via PATCH /api/agent/sessions/[id].
  // The chat handler reads it on each turn (30s server-side cache);
  // when 'bypass' it forwards X-Phantom-Approval-Bypass to MCP, which
  // makes the gate auto-approve gated tools. Default 'manual' is
  // safe: every gated tool needs operator confirmation.
  const [approvalMode, setApprovalMode] = useState<"manual" | "bypass">(
    "manual",
  );
  // v0.3.7+: track whether the operator touched the dropdown BEFORE a
  // session existed. If they did, the next-session-creation effect
  // writes the chosen mode to the new session's metadata rather than
  // overwriting state with the GET response (which would be empty for
  // a brand-new session and revert the pre-session choice to manual).
  const preSessionApprovalIntentRef = useRef<"manual" | "bypass" | null>(null);

  // Sync approvalMode when sessionId changes — hit the per-session
  // proxy directly (not patchSession, which is for writes). Best-
  // effort; on failure we fall back to 'manual' which is the safe
  // default.
  //
  // v0.3.7+: if the operator pre-selected a mode (via the dropdown
  // BEFORE sending their first message — sessionId was null at the
  // time), this effect WRITES that intent to the new session's
  // metadata instead of reading-and-overwriting. Without that the
  // operator's pre-session choice would race with the GET and lose.
  useEffect(() => {
    if (!sessionId) {
      // No active session: reset state to the safe default, but keep
      // the pre-session intent ref so a subsequent session-creation
      // applies it.
      setApprovalMode("manual");
      return;
    }
    let cancelled = false;
    const pending = preSessionApprovalIntentRef.current;
    if (pending !== null) {
      // Operator pre-chose a mode before this session existed; write
      // it through, then clear the ref so subsequent session-switches
      // resume the GET-and-sync behaviour.
      preSessionApprovalIntentRef.current = null;
      setApprovalMode(pending);
      void (async () => {
        try {
          await fetch(
            `/api/agent/sessions/${encodeURIComponent(sessionId)}`,
            {
              method: "PATCH",
              credentials: "same-origin",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                metadata: { approval_mode: pending },
              }),
            },
          );
        } catch (err) {
          console.warn("Failed to persist pre-session approval_mode:", err);
        }
      })();
      return;
    }
    void (async () => {
      try {
        const resp = await fetch(
          `/api/agent/sessions/${encodeURIComponent(sessionId)}`,
          { method: "GET", credentials: "same-origin" },
        );
        if (!resp.ok) return;
        const data = (await resp.json()) as {
          session?: { meta?: Record<string, unknown> };
        };
        if (cancelled) return;
        const raw = data?.session?.meta?.["approval_mode"];
        setApprovalMode(raw === "bypass" ? "bypass" : "manual");
      } catch {
        // Best-effort; keep current value on error.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const handleApprovalModeChange = useCallback(
    (next: "manual" | "bypass") => {
      // v0.3.7+: dropdown is interactive pre-session too. If no
      // sessionId yet, stash the intent in the ref and update local
      // state so the dropdown reflects the chosen mode; the session-
      // creation effect above will PATCH it once the first message
      // creates a session.
      setApprovalMode(next);
      if (!sessionId) {
        preSessionApprovalIntentRef.current = next;
        return;
      }
      // Optimistic update — the PATCH below is fire-and-forget. Worst
      // case: the server rejects (e.g. session was deleted while the
      // dropdown was open), and the next session refresh corrects.
      void (async () => {
        try {
          await fetch(
            `/api/agent/sessions/${encodeURIComponent(sessionId)}`,
            {
              method: "PATCH",
              credentials: "same-origin",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                metadata: { approval_mode: next },
              }),
            },
          );
        } catch (err) {
          console.warn("Failed to persist approval_mode:", err);
        }
      })();
    },
    [sessionId],
  );

  // Refresh sessions. Uses the same server-side `exclude_scheduled`
  // filter as the initial mount fetch above — see that hook's comment
  // for the v0.3.6 architectural background.
  const refreshSessions = useCallback(() => {
    void (async () => {
      const result = await listChatSessions({ excludeScheduled: true });
      if (result.ok) {
        const sorted = [...result.data].sort(
          (a, b) =>
            new Date(b.last_active_at || b.created_at).getTime() -
            new Date(a.last_active_at || a.created_at).getTime()
        );
        setSessions(sorted.map((s) => toSessionSummary(s, "auto")));
      }
    })();
  }, []);

  // Auto-save session title on first user message. The server already
  // does this on lazy-create (see /api/chat route), but doing it client-
  // side too means: (a) the sidebar refreshes immediately rather than
  // waiting for the next manual list, and (b) if the operator typed a
  // longer first message than 60 chars, we still get a clean preview.
  // Field is top-level `title` (MCP's update_session accepts it directly);
  // earlier this set `metadata.title` which the MCP didn't read, so
  // titles were never persisted.
  const titleSavedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!sessionId) return;
    if (titleSavedRef.current === sessionId) return;
    const firstUserMsg = messages.find((m) => m.role === "user");
    if (!firstUserMsg) return;
    titleSavedRef.current = sessionId;
    const trimmed = firstUserMsg.content.trim();
    const title =
      trimmed.length > 60 ? `${trimmed.slice(0, 60).trimEnd()}…` : trimmed;
    if (!title) return;
    void (async () => {
      await patchSession(sessionId, { title });
      refreshSessions();
    })();
  }, [sessionId, messages, refreshSessions]);

  // Derived values
  const modelLabel = currentModel
    ? `${currentProvider ?? "auto"}/${currentModel}`
    : "auto";

  const firstUserMessage = messages.find((m) => m.role === "user");
  const sessionTitle = firstUserMessage
    ? firstUserMessage.content.slice(0, 60)
    : "New Chat";

  // Handlers
  const handleNewChat = useCallback(() => {
    resetChat();
    setActiveSessionId(null);
  }, [resetChat]);

  const handleSelectSession = useCallback(
    (id: string) => {
      if (id === activeSessionId) return;
      setActiveSessionId(id);
      setIsLoadingSession(true);
      void (async () => {
        try {
          const result = await getSessionTranscript(id);
          if (!result.ok) {
            loadSession(id, []);
            return;
          }
          const rawMessages = result.data?.messages ?? [];
          // Round-14 / Phase G — keep system rows that are compaction
          // checkpoints (the transcript loader filtered to user/asst +
          // these) so MessageList can render them as in-thread dividers.
          const history: ChatMessage[] = rawMessages.map((msg) => {
            if (msg.role === "system") {
              return {
                role: "system" as const,
                content: msg.content,
                timestamp: msg.timestamp,
                meta: msg.meta,
                // v0.5.46 — MCP message id propagation; surfaces on
                // ChatMessage so per-message Fork-from-here can bind.
                mcpId: msg.mcpId,
              };
            }
            return {
              role:
                msg.role === "assistant"
                  ? ("assistant" as const)
                  : ("user" as const),
              content: msg.content,
              timestamp: msg.timestamp,
              mcpId: msg.mcpId,
            };
          });
          loadSession(id, history);
        } catch {
          loadSession(id, []);
        } finally {
          setIsLoadingSession(false);
        }
      })();
    },
    [activeSessionId, loadSession]
  );

  // Deep-link support: /?session=<id> selects + loads that session on
  // mount. Used by the job detail page's "Open conversation" link, which
  // hands the operator from a chat-job run to the underlying transcript.
  // We deliberately read the param once on mount (via the ref) rather
  // than reacting to it on every render — that keeps in-app navigation
  // (clicking a different sidebar entry) from being overridden by a
  // stale URL the user hasn't actually changed.
  const searchParams = useSearchParams();
  const sessionParamRef = useRef(searchParams.get("session"));
  const initialSessionLoadedRef = useRef(false);
  useEffect(() => {
    const target = sessionParamRef.current;
    if (!target || initialSessionLoadedRef.current) return;
    initialSessionLoadedRef.current = true;
    handleSelectSession(target);
  }, [handleSelectSession]);

  const handleDeleteSession = useCallback(
    (id: string) => {
      void (async () => {
        const result = await deleteSession(id);
        if (result.ok) {
          setSessions((prev) => prev.filter((s) => s.id !== id));
          if (activeSessionId === id) {
            resetChat();
            setActiveSessionId(null);
          }
        }
      })();
    },
    [activeSessionId, resetChat]
  );

  // Round-12 — operator wanted the ability to rename existing sessions.
  // The MCP already has PATCH /api/v1/sessions/{id} that accepts {title}
  // (see lib/api/sessions.ts:patchSession). This handler:
  //   1. Optimistically updates local state so the sidebar reflects
  //      the change immediately.
  //   2. Fires the PATCH; on failure, reverts the local state and
  //      logs a warning. (No error toast yet — would need a notif
  //      system; for now operator can re-rename.)
  const handleRenameSession = useCallback(
    (id: string, title: string) => {
      const trimmed = title.trim();
      if (!trimmed) return;
      let prevTitle: string | undefined;
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== id) return s;
          prevTitle = s.title;
          return { ...s, title: trimmed };
        }),
      );
      void (async () => {
        const result = await patchSession(id, { title: trimmed });
        if (!result.ok) {
          console.warn(
            `rename session ${id}: PATCH failed:`,
            result.error.message,
          );
          // Revert optimistic update on failure.
          setSessions((prev) =>
            prev.map((s) => (s.id === id ? { ...s, title: prevTitle } : s)),
          );
        }
      })();
    },
    [],
  );

  // v0.5.46 / Issue #30 polish — Fork-from-here per-message. Same
  // backend path as handleForkSession but passes from_message_id so
  // the MCP-side fork_session() cut-off is precise (vs forking the
  // full conversation). Uses the active session id implicitly + the
  // message's MCP id from the AssistantMessage's onFork callback.
  const handleForkFromMessage = useCallback(
    (mcpMessageId: string) => {
      const parentId = activeSessionId;
      if (!parentId) return;
      void (async () => {
        try {
          const r = await fetch(
            `/api/agent/sessions/${encodeURIComponent(parentId)}/fork`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ from_message_id: mcpMessageId }),
            },
          );
          if (!r.ok) {
            const text = await r.text();
            console.warn(
              `fork-from-message ${parentId}/${mcpMessageId} failed:`,
              r.status,
              text.slice(0, 200),
            );
            return;
          }
          const data = (await r.json()) as {
            session?: { id?: string };
          };
          const newId = data.session?.id;
          if (!newId) {
            console.warn(
              `fork-from-message ${parentId}/${mcpMessageId}: response missing session.id`,
            );
            return;
          }
          await refreshSessions();
          handleSelectSession(newId);
        } catch (err) {
          console.warn(
            `fork-from-message ${parentId}/${mcpMessageId} crashed:`,
            err,
          );
        }
      })();
    },
    [activeSessionId, refreshSessions, handleSelectSession],
  );

  // v0.5.36 / Issue #30 UI gap fill — Fork session. POSTs to the
  // agent's fork proxy (which proxies to MCP's fork API which copies
  // the parent's message history into the new session). On success,
  // refreshes the session list + switches to the new session.
  const handleForkSession = useCallback(
    (id: string) => {
      void (async () => {
        try {
          const r = await fetch(
            `/api/agent/sessions/${encodeURIComponent(id)}/fork`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({}),
            },
          );
          if (!r.ok) {
            const text = await r.text();
            console.warn(
              `fork session ${id} failed:`,
              r.status,
              text.slice(0, 200),
            );
            return;
          }
          const data = (await r.json()) as {
            session?: { id?: string; title?: string };
          };
          const newId = data.session?.id;
          if (!newId) {
            console.warn(`fork session ${id}: response missing session.id`);
            return;
          }
          // Refresh the session list so the new fork appears in the
          // sidebar, then switch to it.
          await refreshSessions();
          handleSelectSession(newId);
        } catch (err) {
          console.warn(`fork session ${id} crashed:`, err);
        }
      })();
    },
    [refreshSessions, handleSelectSession],
  );

  const handleExportSession = useCallback(
    (id: string, format: "yaml" | "json" | "markdown" | "events") => {
      void (async () => {
        const result = await exportSession(id, format);
        if (result.ok) {
          const ext = FILE_EXTS[format] ?? format;
          const mime = MIME_TYPES[format] ?? "text/plain";
          downloadBlob(result.data, `session-${id.slice(0, 8)}.${ext}`, mime);
          return;
        }
        // v0.6.6 — surface failure to the operator. Pre-v0.6.6 this
        // path silently swallowed `result.ok === false`, so a failing
        // export looked identical to "the feature is missing" — the
        // operator clicked Export, nothing happened, no error
        // appeared anywhere. Using window.alert here as the simplest
        // unmissable surface; a proper toast/notification primitive
        // is a separate scope (none exists in the codebase today).
        const detail = result.error || "Unknown error";
        // console.error so the failure is captured for devtools / log
        // capture, in addition to the operator-facing alert.
        // eslint-disable-next-line no-console
        console.error(
          `[chat] session export failed (id=${id.slice(0, 8)} format=${format}):`,
          detail,
        );
        if (typeof window !== "undefined") {
          window.alert(
            `Export failed (format=${format}).\n\n${detail}\n\n` +
              `The failure has been logged to the browser console for diagnosis.`,
          );
        }
      })();
    },
    []
  );

  const handleExportCurrent = useCallback(
    (format: "yaml" | "json" | "markdown" | "events") => {
      if (!sessionId) return;
      handleExportSession(sessionId, format);
    },
    [sessionId, handleExportSession]
  );

  const handleDeleteCurrentSession = useCallback(() => {
    if (!sessionId) return;
    handleDeleteSession(sessionId);
  }, [sessionId, handleDeleteSession]);

  const handleQuickAction = useCallback(
    (prompt: string) => {
      sendMessage(prompt);
    },
    [sendMessage]
  );

  const showEmptyState = messages.length === 0 && !isLoadingSession;

  return (
    <div className="flex h-screen overflow-hidden">
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        onExportSession={handleExportSession}
        onRenameSession={handleRenameSession}
        onForkSession={handleForkSession}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((prev) => !prev)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <ChatHeader
          sessionTitle={sessionTitle}
          modelLabel={modelLabel}
          modelOnline={Boolean(currentModel)}
          sessionId={sessionId}
          onToggleSidebar={() => setSidebarCollapsed((prev) => !prev)}
          onExport={sessionId ? handleExportCurrent : undefined}
          onDeleteSession={sessionId ? handleDeleteCurrentSession : undefined}
          models={availableModels}
          selectedModel={currentModel}
          selectedProvider={currentProvider}
          onModelChange={setModel}
          debugPanelOpen={debugPanelOpen}
          onToggleDebugPanel={toggleDebugPanel}
          // v0.6.6 — subagent toggle. Operator-personal preference,
          // persisted to operator_state.db. Defaults ON.
          subagentsEnabled={subagentsEnabled}
          onToggleSubagents={toggleSubagents}
          // Round-14 / Phase A.3 + A.4 — semantic stats from the new
          // SSE event kinds (compaction_end, cache_hit). null until
          // the first event lands; the header components hide
          // themselves cleanly when nullish.
          compactionStats={telemetryStats.lastCompaction}
          cacheHit={telemetryStats.lastCacheHit}
          // v0.1.27 — per-session approval mode dropdown. Reads
          // from session.metadata.approval_mode; writes via PATCH.
          approvalMode={approvalMode}
          onApprovalModeChange={handleApprovalModeChange}
          // v0.17.85 — Claude Code toggle removed; selection now
          // flows through the model dropdown (v0.17.82). chatRoute
          // stays derived in useChat for the send-time URL switch.
        />

        <div className="flex-1 overflow-hidden">
          {showEmptyState ? (
            <EmptyState onQuickAction={handleQuickAction} />
          ) : (
            <MessageList
              messages={messages}
              isStreaming={isStreaming}
              isLoading={isLoadingSession}
              // Round-15 / Phase S — live subagent activity cards
              // pinned below the thread.
              subagents={subagents}
              // v0.5.46 — per-message Fork-from-here. Renders a
              // hover-revealed button on assistant bubbles that have
              // an mcpId (loaded from MCP persistence). Click branches
              // a new session from that exact message.
              onForkFromMessage={handleForkFromMessage}
            />
          )}
        </div>

        {/* Phase 11 — pending approval cards. Rendered between the
            chat thread and the input bar so they're always visible
            without scrolling. Each card resolves itself when the
            operator clicks Approve/Deny. */}
        {pendingApprovals.length > 0 && (
          <div className="px-6 py-3 space-y-3 border-t border-on-surface/10 bg-surface-container-lowest/30 max-h-[60vh] overflow-y-auto">
            {pendingApprovals.map((approval) => (
              <ApprovalCard
                key={approval.id}
                approval={approval}
                onResolve={resolveApproval}
              />
            ))}
          </div>
        )}

        <ChatInput
          onSend={sendMessage}
          isStreaming={isStreaming}
          // Round-14 / Phase A.2 — wire the most-recent context_warning
          // utilization through so the input renders the /compress
          // auto-suggest banner at >=80%.
          contextUtilization={telemetryStats.lastContextWarning?.utilization}
        />
      </div>

      {/* Right-side telemetry panel — collapsed by default; toggle in
          the chat header. The panel itself returns null when !open so
          the flex column doesn't reserve space when hidden. */}
      <DebugPanel
        open={debugPanelOpen}
        onClose={toggleDebugPanel}
        onClear={clearTelemetry}
        sessionId={sessionId}
        runId={runId}
        toolCalls={toolCalls}
        events={events}
        isStreaming={isStreaming}
      />
    </div>
  );
}

// ─── Empty State ─────────────────────────────────────────────────────────────

function EmptyState({ onQuickAction }: { onQuickAction: (prompt: string) => void }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-8 px-8">
      <div className="flex flex-col items-center gap-4">
        <div
          className="w-20 h-20 rounded-3xl flex items-center justify-center shadow-lg"
          style={{
            background: "var(--glass-bg-strong)",
            border: "0.5px solid var(--glass-border)",
            boxShadow: "0 0 40px rgba(25, 99, 179, 0.12)",
          }}
        >
          <SparkLogo size={48} />
        </div>
        <div className="text-center">
          <h2 className="text-xl font-headline font-bold text-on-surface">
            Talk to Phantom
          </h2>
          <p className="text-sm text-on-surface-variant/70 mt-1 font-body max-w-sm">
            AI incident response — case triage, XQL investigation,
            and live tool telemetry over MCP.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap justify-center gap-2 max-w-lg">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            type="button"
            onClick={() => onQuickAction(action.prompt)}
            className="group flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-label font-medium text-on-surface-variant hover:text-on-surface transition-all hover:scale-[1.02] active:scale-[0.98]"
            style={{
              background: "var(--glass-bg)",
              backdropFilter: "blur(12px)",
              border: "0.5px solid var(--glass-border)",
            }}
          >
            <span className="material-symbols-outlined text-sm text-secondary/70 group-hover:text-secondary transition-colors">
              {action.icon}
            </span>
            {action.label}
          </button>
        ))}
      </div>

      <p className="text-[11px] text-outline/50 font-label">
        Or type anything below to start a conversation
      </p>
    </div>
  );
}
