"use client";

/**
 * /agents — Round-15 / Phase S.
 *
 * Operator surface for the agent-definition registry. List
 * (operator + plugin + builtin) definitions, toggle enable, edit,
 * delete, view recent runs (subagent task history).
 *
 * The model invokes subagent_create with one of these definitions
 * inside chat — operators don't typically run subagents directly
 * from this page (though /tasks can show recent runs and link to
 * their sidechain transcripts).
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import {
  glassStyle,
  Badge,
  StatCard,
  EmptyState,
  InvestigationTabBar,
} from "@/components/investigation/ui";
import {
  deleteAgentDefinition,
  listAgentDefinitions,
  originBadgeTone,
  patchAgentDefinition,
  upsertAgentDefinition,
  type AgentDefinition,
} from "@/lib/api/agent-definitions";

// Origin filter chips — operator / plugin / builtin matched by `origin`
// prefix (plugin origins look like `plugin:<name>`).
const ORIGIN_GROUPS: { key: string; label: string; match: (origin: string) => boolean }[] = [
  { key: "operator", label: "Operator", match: (o) => o === "operator" },
  { key: "plugin", label: "Plugin", match: (o) => o.startsWith("plugin:") },
  { key: "builtin", label: "Built-in", match: (o) => o === "builtin" },
];

/** Map the origin's `originBadgeTone` colours onto a `Badge` tone string
 *  (border + text + bg classes), so the row cards match the hooks page's
 *  badge idiom rather than the old hand-rolled chip. */
function originTone(origin: string): string {
  if (origin.startsWith("plugin:")) return "text-tertiary border-tertiary/40 bg-tertiary/10";
  if (origin === "builtin") return "text-primary border-primary/40 bg-primary/10";
  return "text-secondary border-secondary/40 bg-secondary/10";
}

export default function AgentsPage() {
  const [defs, setDefs] = useState<AgentDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<AgentDefinition | null>(null);
  const [adding, setAdding] = useState(false);
  const [originFilter, setOriginFilter] = useState<string>("all");
  const [nameFilter, setNameFilter] = useState("");

  // Client-side filtering over the already-fetched defs — no extra fetch.
  const filtered = useMemo(() => {
    const group = ORIGIN_GROUPS.find((g) => g.key === originFilter);
    const q = nameFilter.trim().toLowerCase();
    return defs.filter((d) => {
      if (group && !group.match(d.origin)) return false;
      if (q && !(`${d.name} ${d.description ?? ""}`.toLowerCase().includes(q))) return false;
      return true;
    });
  }, [defs, originFilter, nameFilter]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAgentDefinitions();
      setDefs(data.agent_definitions);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleToggle = useCallback(
    async (id: string, enabled: boolean) => {
      try {
        await patchAgentDefinition(id, { enabled });
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [refresh],
  );

  const handleDelete = useCallback(
    async (id: string, name: string) => {
      if (
        !confirm(
          `Delete agent "${name}"? Plugin-contributed agents will reappear on the next plugin reload.`,
        )
      )
        return;
      try {
        await deleteAgentDefinition(id);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [refresh],
  );

  const openNewAgent = useCallback(() => {
    setEditing({
      id: crypto.randomUUID(),
      name: "",
      description: "",
      system_prompt: "",
      tools_allowed: [],
      tools_denied: [],
      model: null,
      max_turns: 10,
      isolation: "fresh_session",
      origin: "operator",
      enabled: true,
      created_at: "",
      updated_at: "",
    });
    setAdding(true);
  }, []);

  return (
    <div className="h-screen overflow-y-auto custom-scrollbar">
      <div className="max-w-[1400px] mx-auto px-8 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="material-symbols-outlined text-2xl text-primary">
                groups
              </span>
              <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface">
                Agents
              </h1>
            </div>
            <p className="text-xs text-on-surface-variant/80 ml-9 max-w-5xl leading-snug">
              Subagent definitions — system prompt + scoped tool catalog. Spawned via <code className="font-mono">subagent_create</code>; runs appear in <Link href="/tasks" className="link">/tasks</Link>.
            </p>
          </div>
          <button
            type="button"
            onClick={openNewAgent}
            className="px-4 py-2 rounded-xl text-xs font-medium text-on-primary-container bg-primary-container/30 hover:bg-primary-container/50 transition-colors"
          >
            <span className="material-symbols-outlined text-base align-middle mr-1">
              add
            </span>
            New agent
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="rounded-xl border border-error/30 bg-error/10 p-3 text-xs text-error">
            {error}
          </div>
        )}

        {/* Summary stat cards */}
        {!loading && defs.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard icon="groups" label="Total agents" value={defs.length} />
            <StatCard
              icon="toggle_on"
              label="Enabled"
              value={defs.filter((d) => d.enabled).length}
              tone="bg-secondary/15 text-secondary"
            />
            <StatCard
              icon="person"
              label="Operator-defined"
              value={defs.filter((d) => d.origin === "operator").length}
              tone="bg-primary/15 text-primary"
            />
            <StatCard
              icon="extension"
              label="Plugin / built-in"
              value={defs.filter((d) => d.origin !== "operator").length}
              tone="bg-tertiary/15 text-tertiary"
            />
          </div>
        )}

        {/* Filter bar */}
        {!loading && defs.length > 0 && (
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 rounded-2xl p-1.5" style={glassStyle}>
              {[{ key: "all", label: "All" }, ...ORIGIN_GROUPS].map((g) => (
                <button
                  key={g.key}
                  onClick={() => setOriginFilter(g.key)}
                  className={cn(
                    "rounded-lg px-3 py-1.5 text-[11px] uppercase tracking-wider font-medium transition",
                    originFilter === g.key
                      ? "bg-secondary-container/40 border border-secondary/40 text-secondary"
                      : "border border-transparent text-on-surface-variant hover:text-on-surface hover:bg-white/5",
                  )}
                >
                  {g.label}
                </button>
              ))}
            </div>
            <div className="relative flex-1 min-w-[180px] max-w-xs">
              <span className="material-symbols-outlined text-[16px] absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant/60">
                search
              </span>
              <input
                type="text"
                value={nameFilter}
                onChange={(e) => setNameFilter(e.target.value)}
                placeholder="Filter by name…"
                className="w-full rounded-xl pl-9 pr-3 py-2 text-xs bg-surface-container-low border-[0.5px] border-outline-variant text-on-surface outline-none focus:border-primary/40"
              />
            </div>
            <span className="text-[11px] text-on-surface-variant/60 ml-auto">
              {filtered.length} of {defs.length}
            </span>
          </div>
        )}

        {/* List */}
        {loading ? (
          <div className="text-center py-16 text-sm text-on-surface-variant/60">
            Loading agents…
          </div>
        ) : defs.length === 0 ? (
          <EmptyState
            icon="groups"
            title="No agents registered"
            hint="Add an agent, OR drop a plugin under bundles/spark/plugins/ with an agents: block — e.g. a case-triage subagent scoped to xsoar_*, or an evidence-collector with read-only XSOAR + web tools."
          >
            <button
              type="button"
              onClick={openNewAgent}
              className="mt-3 inline-flex items-center gap-1.5 rounded-xl bg-primary text-on-primary px-4 py-2 text-sm font-medium hover:opacity-90 transition"
            >
              <span className="material-symbols-outlined text-[18px]">add</span>
              New agent
            </button>
          </EmptyState>
        ) : filtered.length === 0 ? (
          <EmptyState icon="filter_alt_off" title="No agents match the filter" hint="Clear the filter to see all registered agents." />
        ) : (
          <div className="grid gap-3">
            {filtered.map((d) => (
              <AgentRowCard
                key={d.id}
                def={d}
                onToggle={handleToggle}
                onEdit={() => {
                  setEditing(d);
                  setAdding(false);
                }}
                onDelete={() => handleDelete(d.id, d.name)}
              />
            ))}
          </div>
        )}
      </div>

      {editing && (
        <AgentEditor
          def={editing}
          isNew={adding}
          onCancel={() => {
            setEditing(null);
            setAdding(false);
          }}
          onSaved={() => {
            setEditing(null);
            setAdding(false);
            void refresh();
          }}
        />
      )}
    </div>
  );
}

// ─── List row card ──────────────────────────────────────────────────

function AgentRowCard({
  def,
  onToggle,
  onEdit,
  onDelete,
}: {
  def: AgentDefinition;
  onToggle: (id: string, enabled: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const tone = originBadgeTone(def.origin);
  const noAllowlist = def.tools_allowed.length === 0;
  // Tool-scope summary, demoted to a muted second line.
  const allowSummary = noAllowlist
    ? null
    : def.tools_allowed.length === 1
      ? def.tools_allowed[0]
      : `${def.tools_allowed.length} allow patterns`;
  return (
    <div
      className={cn(
        "rounded-2xl p-5 flex items-start gap-4 transition-opacity",
        !def.enabled && "opacity-60",
      )}
      style={glassStyle}
    >
      <button
        type="button"
        role="switch"
        aria-checked={def.enabled}
        aria-label={def.enabled ? "Disable agent" : "Enable agent"}
        onClick={() => onToggle(def.id, !def.enabled)}
        className={cn(
          "relative w-9 h-5 rounded-full transition-colors shrink-0 mt-1",
          def.enabled ? "bg-primary" : "bg-outline/30",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform",
            def.enabled ? "translate-x-4" : "translate-x-0.5",
          )}
        />
      </button>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
          <span className="font-mono text-sm font-semibold text-on-surface truncate">
            {def.name || "(unnamed)"}
          </span>
          <Badge tone={originTone(def.origin)}>{tone.label}</Badge>
          {def.model && (
            <Badge tone="text-on-surface-variant border-outline-variant bg-surface-container-high">
              {def.model}
            </Badge>
          )}
          <Badge tone="text-on-surface-variant border-outline-variant bg-surface-container-high">
            ≤{def.max_turns} turns
          </Badge>
        </div>
        {def.description && (
          <p className="text-xs text-on-surface-variant mb-1.5 leading-relaxed">
            {def.description}
          </p>
        )}
        <div className="text-[11px] text-on-surface-variant/70 font-mono truncate">
          {allowSummary ? (
            <>
              <span className="material-symbols-outlined text-[12px] align-middle mr-0.5 text-secondary">
                check_circle
              </span>
              {allowSummary}
            </>
          ) : (
            <span className="text-error">
              <span className="material-symbols-outlined text-[12px] align-middle mr-0.5">
                warning
              </span>
              No allowlist (sees ALL tools)
            </span>
          )}
          {def.tools_denied.length > 0 && (
            <span className="ml-3">
              <span className="material-symbols-outlined text-[12px] align-middle mr-0.5 text-error/80">
                block
              </span>
              {def.tools_denied.length} deny patterns
            </span>
          )}
        </div>
      </div>
      {/* #SUB-F3 — edit/delete are operator-only. A plugin:<name> / builtin
          agent is owned by its source (rewritten on reload); the API now
          rejects mutating/deleting it (403), so hide the controls and show a
          lock instead of offering an action that 403s. */}
      <div className="flex flex-col gap-1.5 shrink-0">
        {def.origin === "operator" ? (
          <>
            <button
              type="button"
              onClick={onEdit}
              aria-label="Edit agent"
              className="p-1.5 rounded hover:bg-white/5 text-on-surface-variant hover:text-on-surface transition-colors"
            >
              <span className="material-symbols-outlined text-lg">edit</span>
            </button>
            <button
              type="button"
              onClick={onDelete}
              aria-label="Delete agent"
              className="p-1.5 rounded hover:bg-white/5 text-on-surface-variant hover:text-error transition-colors"
            >
              <span className="material-symbols-outlined text-lg">delete</span>
            </button>
          </>
        ) : (
          <span
            className="p-1.5 text-on-surface-variant/50"
            title={`${def.origin} agent — managed by its source; not editable here`}
          >
            <span className="material-symbols-outlined text-lg">lock</span>
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Editor drawer ──────────────────────────────────────────────────

function AgentEditor({
  def,
  isNew,
  onCancel,
  onSaved,
}: {
  def: AgentDefinition;
  isNew: boolean;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<AgentDefinition>(def);
  const [allowedText, setAllowedText] = useState(
    def.tools_allowed.join("\n"),
  );
  const [deniedText, setDeniedText] = useState(
    def.tools_denied.join("\n"),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"def" | "tools" | "exec">("def");

  const noAllowlist = allowedText.split("\n").map((s) => s.trim()).filter(Boolean).length === 0;

  const handleSave = useCallback(async () => {
    setError(null);
    if (!draft.name.trim()) {
      setTab("def");
      setError("Name is required.");
      return;
    }
    if (!draft.system_prompt.trim()) {
      setTab("def");
      setError("System prompt is required.");
      return;
    }
    setSaving(true);
    try {
      const body: Partial<AgentDefinition> = {
        ...draft,
        tools_allowed: allowedText
          .split("\n")
          .map((s) => s.trim())
          .filter((s) => s.length > 0),
        tools_denied: deniedText
          .split("\n")
          .map((s) => s.trim())
          .filter((s) => s.length > 0),
      };
      if (isNew) {
        await upsertAgentDefinition(body);
      } else {
        await patchAgentDefinition(draft.id, body);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, [draft, allowedText, deniedText, isNew, onSaved]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-end bg-black/40"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full md:w-1/2 md:max-w-[1000px] md:min-w-[640px] h-full overflow-y-auto p-6 space-y-4 custom-scrollbar"
        style={{
          ...glassStyle,
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
          borderLeft: "0.5px solid var(--glass-border)",
        }}
      >
        <div className="flex items-center justify-between">
          <h2 className="font-headline text-xl font-bold text-on-surface truncate">
            {isNew ? "Creating new agent…" : `Editing ${draft.name || "agent"}`}
          </h2>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close editor"
            className="p-1.5 rounded hover:bg-white/5 text-on-surface-variant hover:text-on-surface shrink-0"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        {draft.origin.startsWith("plugin:") && !isNew && (
          <div className="rounded-xl border border-tertiary/30 bg-tertiary/10 p-3 text-xs text-tertiary">
            <span className="material-symbols-outlined text-sm align-middle mr-1">
              info
            </span>
            This agent comes from{" "}
            <code className="font-mono">{draft.origin}</code>. Edits
            here persist, but a plugin reload will overwrite them.
            For permanent changes, clone via &ldquo;New agent&rdquo; with
            origin=operator.
          </div>
        )}

        <InvestigationTabBar
          tabs={[
            { key: "def", label: "Definition", icon: "badge" },
            { key: "tools", label: "Tools", icon: "build" },
            { key: "exec", label: "Execution", icon: "bolt" },
          ]}
          active={tab}
          onChange={setTab}
        />

        {tab === "def" && (
          <>
            <Field label="Name (unique identifier)">
              <input
                type="text"
                value={draft.name}
                onChange={(e) => setDraft((p) => ({ ...p, name: e.target.value }))}
                disabled={!isNew}
                className="input-base font-mono"
                placeholder="e.g. case-triage"
              />
            </Field>

            <Field label="Description">
              <input
                type="text"
                value={draft.description}
                onChange={(e) =>
                  setDraft((p) => ({ ...p, description: e.target.value }))
                }
                className="input-base"
              />
            </Field>

            <Field label="System prompt">
              <textarea
                value={draft.system_prompt}
                onChange={(e) =>
                  setDraft((p) => ({ ...p, system_prompt: e.target.value }))
                }
                className="input-base font-body min-h-[200px]"
                placeholder="The system instruction the subagent runs with…"
              />
            </Field>
          </>
        )}

        {tab === "tools" && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Tools allowed (one glob per line; empty = all)">
                <textarea
                  value={allowedText}
                  onChange={(e) => setAllowedText(e.target.value)}
                  className="input-base font-mono min-h-[160px]"
                  placeholder={"xsoar_*\ncortex_*"}
                />
              </Field>
              <Field label="Tools denied (one glob per line)">
                <textarea
                  value={deniedText}
                  onChange={(e) => setDeniedText(e.target.value)}
                  className="input-base font-mono min-h-[160px]"
                  placeholder={"*_delete\nxsoar_close_incident"}
                />
              </Field>
            </div>
            {noAllowlist && (
              <div className="rounded-xl border border-error/30 bg-error/10 p-3 text-xs text-error">
                <span className="material-symbols-outlined text-sm align-middle mr-1">
                  warning
                </span>
                No allowlist set — this agent will see ALL tools. Add at
                least one allow glob to scope its catalog.
              </div>
            )}
          </>
        )}

        {tab === "exec" && (
          <div className="grid grid-cols-3 gap-3">
            <Field label="Max turns (1-50)">
              <input
                type="number"
                min={1}
                max={50}
                value={draft.max_turns}
                onChange={(e) =>
                  setDraft((p) => ({
                    ...p,
                    max_turns: Number(e.target.value) || 10,
                  }))
                }
                className="input-base"
              />
            </Field>
            <Field label="Isolation">
              <select
                value={draft.isolation}
                onChange={(e) =>
                  setDraft((p) => ({
                    ...p,
                    isolation: e.target.value as
                      | "fresh_session"
                      | "parent_session",
                  }))
                }
                className="input-base"
              >
                <option value="fresh_session">fresh_session (default)</option>
                <option value="parent_session">parent_session (advanced)</option>
              </select>
            </Field>
            <Field label="Model override (empty = inherit)">
              <input
                type="text"
                value={draft.model ?? ""}
                onChange={(e) =>
                  setDraft((p) => ({
                    ...p,
                    model: e.target.value || null,
                  }))
                }
                className="input-base font-mono"
                placeholder="(inherit)"
              />
            </Field>
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-error/30 bg-error/10 p-3 text-xs text-error">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="px-4 py-2 rounded-xl text-xs font-medium text-on-surface-variant hover:text-on-surface hover:bg-white/5 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="px-4 py-2 rounded-xl text-xs font-medium text-on-primary-container bg-primary-container/30 hover:bg-primary-container/50 transition-colors disabled:opacity-50"
          >
            {saving ? "Saving…" : isNew ? "Create" : "Save"}
          </button>
        </div>

        <style jsx>{`
          .input-base {
            width: 100%;
            padding: 0.625rem 0.75rem;
            border-radius: 0.75rem;
            font-size: 0.8125rem;
            color: var(--m3-on-surface);
            background: var(--m3-surface-container-low);
            border: 0.5px solid var(--glass-border);
            outline: none;
            font-family: inherit;
          }
          .input-base:focus {
            border-color: rgba(25, 99, 179, 0.4);
            box-shadow: 0 0 0 2px rgba(25, 99, 179, 0.15);
          }
          .input-base:disabled {
            opacity: 0.6;
            cursor: not-allowed;
          }
        `}</style>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-label text-on-surface-variant/80">
        {label}
      </label>
      {children}
    </div>
  );
}
