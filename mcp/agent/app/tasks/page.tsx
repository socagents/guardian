"use client";

/**
 * /tasks page — Round-15 / Phase T.
 *
 * Operator surface for the durable task registry. Lists every
 * task (active + recent terminal) with status, progress, kind,
 * elapsed time, and a one-click Abort for running tasks.
 *
 * Auto-refreshes active tasks every 3s so progress stays live
 * without forcing the operator to hit refresh. Terminal tasks
 * stick around so the operator can review what happened.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import {
  glassStyle,
  Badge,
  StatCard,
  EmptyState,
} from "@/components/investigation/ui";
import {
  abortTask,
  formatElapsed,
  formatProgress,
  listTasks,
  statusTone,
  TASK_TERMINAL_STATUS,
  type Task,
  type TaskStatus,
} from "@/lib/api/tasks";

type Filter = "all" | "active" | "succeeded" | "failed" | "aborted";

const REFRESH_MS = 3000;

/** Map a task status onto a `Badge` tone string (border + text + bg classes),
 *  so the rows match the hooks/agents badge idiom rather than the old
 *  hand-rolled chip. running→primary, succeeded→secondary,
 *  failed/aborted→error, pending→on-surface-variant. */
function statusBadgeTone(status: TaskStatus): string {
  switch (status) {
    case "running":
      return "text-primary border-primary/40 bg-primary/10";
    case "succeeded":
      return "text-secondary border-secondary/40 bg-secondary/10";
    case "failed":
    case "aborted":
      return "text-error border-error/40 bg-error/10";
    case "pending":
    default:
      return "text-on-surface-variant border-outline-variant bg-surface-container-high";
  }
}

export default function TasksPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchTasks = useCallback(async () => {
    setError(null);
    try {
      const params: Parameters<typeof listTasks>[0] = { limit: 200 };
      if (filter === "active") params.active_only = true;
      else if (filter !== "all") {
        params.status = filter as TaskStatus;
      }
      const data = await listTasks(params);
      setTasks(data.tasks);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    setLoading(true);
    void fetchTasks();
  }, [fetchTasks]);

  // Auto-refresh: only poll when there are active tasks (otherwise
  // the data is stable and we'd be wasting cycles).
  useEffect(() => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    const hasActive = tasks.some(
      (t) => !TASK_TERMINAL_STATUS.has(t.status),
    );
    if (!hasActive) return;
    refreshTimerRef.current = setTimeout(() => {
      void fetchTasks();
    }, REFRESH_MS);
    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, [tasks, fetchTasks]);

  const handleAbort = useCallback(
    async (id: string, title: string) => {
      if (!confirm(`Abort task "${title}"? The worker will stop at its next checkpoint.`)) return;
      try {
        await abortTask(id, "operator-requested");
        void fetchTasks();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [fetchTasks],
  );

  // Group by kind for visual scanning.
  const grouped = (() => {
    const map = new Map<string, Task[]>();
    for (const t of tasks) {
      const list = map.get(t.kind) ?? [];
      list.push(t);
      map.set(t.kind, list);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  })();

  const runningCount = tasks.filter((t) => t.status === "running").length;
  const succeededCount = tasks.filter((t) => t.status === "succeeded").length;
  const failedCount = tasks.filter((t) => t.status === "failed").length;

  // The filter is server-side (each filter re-fetches), so `tasks` already holds
  // the active filter's rows. The count below mirrors the "N of M" idiom on the
  // hooks/agents pages: under "All" both numbers are the full set; under a
  // narrower filter the first number is the shown rows and the second the total
  // loaded under that filter.
  const filterCount = tasks.length;

  return (
    <div className="h-screen overflow-y-auto custom-scrollbar">
      <div className="max-w-[1400px] mx-auto px-8 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="material-symbols-outlined text-2xl text-primary">
                pending_actions
              </span>
              <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface">
                Tasks
              </h1>
              {runningCount > 0 && (
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-primary/15 text-primary">
                  {runningCount} running
                </span>
              )}
            </div>
            <p className="text-sm text-on-surface-variant ml-9 max-w-3xl leading-snug">
              Long-running background work Guardian spawns — enrichment sweeps, context compactions, subagent hunts, and hook runs kicked off by you or the agent. Watch progress, abort what&apos;s stale, and review results here.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void fetchTasks()}
            disabled={loading}
            className="px-4 py-2 rounded-xl text-xs font-medium text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-50"
            style={glassStyle}
          >
            <span className="material-symbols-outlined text-base align-middle mr-1">
              refresh
            </span>
            Refresh
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="rounded-xl border border-error/30 bg-error/10 p-3 text-xs text-error">
            {error}
          </div>
        )}

        {/* Summary stat cards */}
        {!loading && tasks.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard icon="pending_actions" label="Total tasks" value={tasks.length} />
            <StatCard
              icon="play_circle"
              label="Running"
              value={runningCount}
              tone="bg-primary/15 text-primary"
            />
            <StatCard
              icon="check_circle"
              label="Succeeded"
              value={succeededCount}
              tone="bg-secondary/15 text-secondary"
            />
            <StatCard
              icon="error"
              label="Failed"
              value={failedCount}
              tone="bg-error/15 text-error"
            />
          </div>
        )}

        {/* Filter bar */}
        {!loading && tasks.length > 0 && (
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 rounded-2xl p-1.5" style={glassStyle}>
              {(
                [
                  { key: "all" as const, label: "All" },
                  { key: "active" as const, label: "Active" },
                  { key: "succeeded" as const, label: "Succeeded" },
                  { key: "failed" as const, label: "Failed" },
                  { key: "aborted" as const, label: "Aborted" },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setFilter(opt.key)}
                  className={cn(
                    "rounded-lg px-3 py-1.5 text-[11px] uppercase tracking-wider font-medium transition",
                    filter === opt.key
                      ? "bg-secondary-container/40 border border-secondary/40 text-secondary"
                      : "border border-transparent text-on-surface-variant hover:text-on-surface hover:bg-white/5",
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <span className="text-[11px] text-on-surface-variant/60 ml-auto">
              {filterCount} of {filterCount}
            </span>
          </div>
        )}

        {/* List */}
        {loading && tasks.length === 0 ? (
          <div className="text-center py-16 text-sm text-on-surface-variant/60">
            Loading tasks…
          </div>
        ) : tasks.length === 0 ? (
          <EmptyState
            icon="task_alt"
            title="No background tasks yet"
            hint="Tasks appear when the agent or a job spawns long-running work — an enrichment sweep, a subagent hunt, a context compaction."
          />
        ) : (
          <div className="space-y-5">
            {grouped.map(([kind, kindTasks]) => (
              <div key={kind} className="space-y-2">
                <h3 className="text-xs font-label uppercase tracking-widest text-on-surface-variant/60">
                  {kind} <span className="font-mono">·</span>{" "}
                  <span className="font-mono">{kindTasks.length}</span>
                </h3>
                <div className="grid gap-3">
                  {kindTasks.map((t) => (
                    <TaskRow
                      key={t.id}
                      task={t}
                      onAbort={handleAbort}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── List row card ──────────────────────────────────────────────────

function TaskRow({
  task,
  onAbort,
}: {
  task: Task;
  onAbort: (id: string, title: string) => void;
}) {
  const tone = statusTone(task.status);
  const isActive = !TASK_TERMINAL_STATUS.has(task.status);
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-2xl p-5 flex flex-col gap-2" style={glassStyle}>
      <div className="flex items-start gap-4">
        <span
          className={cn(
            "material-symbols-outlined text-lg shrink-0 mt-0.5",
            tone.fg,
          )}
        >
          {tone.icon}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className="font-mono text-sm font-semibold text-on-surface truncate">
              {task.title}
            </span>
            <Badge tone={statusBadgeTone(task.status)}>{tone.label}</Badge>
            <Badge tone="text-on-surface-variant border-outline-variant bg-surface-container-high">
              {task.kind}
            </Badge>
            {task.parent_session_id && (
              <Link
                href={`/?session=${task.parent_session_id}`}
                className="text-[10px] font-mono text-on-surface-variant/60 hover:text-on-surface transition-colors"
                title="Open the chat session that spawned this task"
              >
                session {task.parent_session_id.slice(0, 8)}
              </Link>
            )}
          </div>
          {task.progress_label && (
            <p className="text-xs text-on-surface-variant mb-1.5">
              {task.progress_label}
            </p>
          )}
          {/* Progress bar — shown when active or reached 1.0 */}
          {(isActive || task.status === "succeeded") && (
            <div
              className="w-full h-1.5 rounded-full overflow-hidden"
              style={{ background: "rgba(140, 145, 157, 0.15)" }}
              aria-hidden="true"
            >
              <div
                className={cn(
                  "h-full transition-[width] duration-500 rounded-full",
                  tone.fg.replace("text-", "bg-"),
                )}
                style={{
                  width: `${Math.round(task.progress * 100)}%`,
                  background:
                    task.status === "running"
                      ? "var(--m3-primary)"
                      : task.status === "succeeded"
                        ? "var(--m3-secondary)"
                        : undefined,
                }}
              />
            </div>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0 text-[11px] font-mono text-on-surface-variant/70">
          <span className="text-right" title="Progress">
            {formatProgress(task)}
          </span>
          <span className="w-12 text-right" title="Elapsed">
            {formatElapsed(task)}
          </span>
          {isActive && (
            <button
              type="button"
              onClick={() => onAbort(task.id, task.title)}
              aria-label="Abort task"
              className="p-1.5 rounded hover:bg-error/10 text-on-surface-variant hover:text-error transition-colors"
              title="Abort"
            >
              <span className="material-symbols-outlined text-lg">
                cancel
              </span>
            </button>
          )}
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="p-1.5 rounded hover:bg-white/5 text-on-surface-variant/70 hover:text-on-surface transition-colors"
            title={expanded ? "Collapse" : "Expand"}
          >
            <span className="material-symbols-outlined text-lg">
              {expanded ? "expand_less" : "expand_more"}
            </span>
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-2 pt-2 border-t border-white/5 grid grid-cols-2 gap-3 text-[11px]">
          <Detail label="Created" value={task.created_at} mono />
          <Detail
            label="Updated"
            value={
              task.updated_at !== task.created_at
                ? task.updated_at
                : "—"
            }
            mono
          />
          {task.completed_at && (
            <Detail label="Completed" value={task.completed_at} mono />
          )}
          <Detail label="Task id" value={task.id} mono />
          {task.output && (
            <div className="col-span-2">
              <p className="text-[10px] font-label uppercase tracking-widest text-on-surface-variant/60 mb-1">
                Output
              </p>
              <pre className="font-mono text-[11px] text-on-surface-variant whitespace-pre-wrap break-all max-h-40 overflow-y-auto rounded-md p-2 bg-surface-container-lowest/50">
                {task.output}
              </pre>
            </div>
          )}
          {Object.keys(task.meta).length > 0 && (
            <div className="col-span-2">
              <p className="text-[10px] font-label uppercase tracking-widest text-on-surface-variant/60 mb-1">
                Metadata
              </p>
              <pre className="font-mono text-[10px] text-on-surface-variant whitespace-pre-wrap break-all max-h-40 overflow-y-auto rounded-md p-2 bg-surface-container-lowest/50">
                {JSON.stringify(task.meta, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Detail({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <p className="text-[10px] font-label uppercase tracking-widest text-on-surface-variant/60">
        {label}
      </p>
      <p
        className={cn(
          "text-on-surface-variant",
          mono && "font-mono text-[11px]",
        )}
      >
        {value || "—"}
      </p>
    </div>
  );
}
