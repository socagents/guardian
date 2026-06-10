"use client";

/**
 * /observability/plugins — Issue #29 UI gap fill (v0.5.44 + v0.5.47).
 *
 * View of the entry-point plugin discovery catalog with lifecycle
 * controls. Each plugin entry-point group (phantom.skills /
 * connectors / hooks / scanners / providers) gets a section;
 * per-group rows show each PluginRef (name, dist_name, dist_version,
 * target) plus an Uninstall button.
 *
 * On a fresh install with no third-party packages installed,
 * every section shows "(none discovered)" — the contract is in place
 * even when no plugins target it.
 *
 * v0.5.44 — discovery surface (GET /api/v1/plugin-entries, was
 *           erroneously named /api/v1/plugins; renamed in v0.5.47 to
 *           avoid colliding with the filesystem-plugin Phase X
 *           endpoint of the same path).
 * v0.5.47 — install + uninstall lifecycle. Install form at the top
 *           runs pip install --user <spec>. Per-row Uninstall buttons
 *           run pip uninstall -y <dist>. Both audit via record_event.
 *
 * What's STILL NOT here:
 *   - Plugin-contributed handler invocation (cross-language bridge,
 *     deferred to v0.5.48). Discovery + lifecycle work today;
 *     contributed handlers aren't yet reachable from the agent's
 *     hook-runner / skill registry / etc.
 */

import { useCallback, useEffect, useState } from "react";

interface PluginRef {
  group: string;
  name: string;
  dist_name: string;
  dist_version: string;
  target: string;
}

interface PluginCatalog {
  groups: Record<string, PluginRef[]>;
  total: number;
  error?: string;
}

const glassCard = {
  background: "var(--glass-bg-strong)",
  backdropFilter: "blur(12px)",
  border: "0.5px solid var(--glass-border)",
} as const;

const GROUP_META: Record<string, { label: string; icon: string; about: string }> = {
  "phantom.skills": {
    label: "Skills",
    icon: "school",
    about: "Skill-MD contributions. Discovered packages should export a function returning a SkillDef list.",
  },
  "phantom.connectors": {
    label: "Connectors",
    icon: "cable",
    about: "Connector manifests. Discovered packages export connector descriptors for the marketplace.",
  },
  "phantom.hooks": {
    label: "Hook builtins",
    icon: "webhook",
    about: "Builtin-hook specs (matches the in-image lib/hook-builtins/ shape). Pip-installable hook libraries.",
  },
  "phantom.scanners": {
    label: "Scanners",
    icon: "radar",
    about: "Deterministic SAST scanners (Octagon-style). Reserved for future scanner integration work.",
  },
  "phantom.providers": {
    label: "Providers",
    icon: "cloud",
    about: "Model-provider adapters. Discovered packages export provider factories.",
  },
};

export default function PluginsPage() {
  const [catalog, setCatalog] = useState<PluginCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // v0.5.44: queries /api/agent/plugin-entries (entry-point
      // discovery) vs /api/agent/plugins (old Phase X filesystem
      // plugins). Distinct surfaces; this page is for the
      // distributable (pip-installable) plugin system.
      const r = await fetch("/api/agent/plugin-entries", { cache: "no-store" });
      if (!r.ok) {
        const text = await r.text();
        throw new Error(`plugins ${r.status}: ${text.slice(0, 200)}`);
      }
      const data = (await r.json()) as PluginCatalog;
      setCatalog(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  // v0.5.47 — install + uninstall handlers. Install runs
  // pip install --user; uninstall runs pip uninstall -y. Both audit
  // server-side. Both refresh the discovery view on success.
  const [installSpec, setInstallSpec] = useState("");
  const [installing, setInstalling] = useState(false);
  const [installResult, setInstallResult] = useState<string | null>(null);
  const handleInstall = useCallback(async () => {
    const spec = installSpec.trim();
    if (!spec) return;
    setInstalling(true);
    setInstallResult(null);
    setError(null);
    try {
      const r = await fetch("/api/agent/plugin-entries/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spec }),
      });
      const data = (await r.json()) as {
        ok?: boolean;
        spec?: string;
        stderr?: string;
        error?: string;
      };
      if (!r.ok || !data.ok) {
        setInstallResult(
          data.error
            ? `Install failed: ${data.error}${data.stderr ? "\n" + data.stderr.slice(-500) : ""}`
            : `Install failed (HTTP ${r.status})`,
        );
        return;
      }
      setInstallResult(`Installed ${data.spec}. Restart phantom-agent to load contributed builtins.`);
      setInstallSpec("");
      await refresh();
    } catch (err) {
      setInstallResult(`Install failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      setInstalling(false);
    }
  }, [installSpec, refresh]);

  const [uninstalling, setUninstalling] = useState<string | null>(null);
  const handleUninstall = useCallback(
    async (distName: string) => {
      if (!confirm(`Uninstall ${distName}? This runs pip uninstall -y inside the agent container.`)) {
        return;
      }
      setUninstalling(distName);
      setError(null);
      try {
        const r = await fetch(
          `/api/agent/plugin-entries/${encodeURIComponent(distName)}`,
          { method: "DELETE" },
        );
        const data = (await r.json()) as {
          ok?: boolean;
          error?: string;
          stderr?: string;
        };
        if (!r.ok || !data.ok) {
          setError(
            data.error
              ? `Uninstall failed: ${data.error}${data.stderr ? "\n" + data.stderr.slice(-500) : ""}`
              : `Uninstall failed (HTTP ${r.status})`,
          );
          return;
        }
        await refresh();
      } catch (err) {
        setError(`Uninstall failed: ${err instanceof Error ? err.message : err}`);
      } finally {
        setUninstalling(null);
      }
    },
    [refresh],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="h-screen overflow-y-auto custom-scrollbar">
      <div className="max-w-[1100px] mx-auto px-8 py-8 space-y-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className="material-symbols-outlined text-2xl text-primary">
              extension
            </span>
            <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface">
              Plugins
            </h1>
          </div>
          <p className="text-sm text-on-surface-variant ml-9 max-w-2xl">
            Discovered Python-entry-point plugins (v0.5.31 / Issue #29
            scaffolding). Five reserved groups; pip-installable
            packages targeting any of them appear here. v0.5.47 adds
            install / uninstall via{" "}
            <code className="font-mono text-xs">pip --user</code>{" "}
            inside the agent container — restart phantom-agent for
            newly-installed packages to surface.
          </p>
          <div className="ml-9 mt-2 inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-secondary/15 text-secondary text-xs">
            <span className="material-symbols-outlined text-sm">info</span>
            Discovery only — plugin-contributed handlers are NOT yet
            invocable. Cross-language handler bridge ships as a separate
            release.
          </div>
        </div>

        {/* v0.5.47 — install form. Server-side runs pip install --user
            and audits the action. Spec accepts pypi names, git+https://,
            file:// URLs, or local paths. */}
        <div className="rounded-2xl p-4" style={glassCard}>
          <div className="flex items-center gap-3 mb-3">
            <span className="material-symbols-outlined text-primary">
              add_circle
            </span>
            <div>
              <h2 className="text-sm font-semibold text-on-surface">
                Install plugin
              </h2>
              <p className="text-xs text-on-surface-variant/70 mt-0.5">
                Runs{" "}
                <code className="font-mono">pip install --user &lt;spec&gt;</code>{" "}
                inside the agent container. Restart phantom-agent
                afterward for contributed builtins to load.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 ml-9">
            <input
              type="text"
              value={installSpec}
              onChange={(e) => setInstallSpec(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !installing && installSpec.trim()) {
                  void handleInstall();
                }
              }}
              placeholder="e.g. phantom-hook-mypackage or git+https://github.com/..."
              disabled={installing}
              className="flex-1 bg-surface-container-low/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:border-primary/50 font-mono"
            />
            <button
              onClick={() => void handleInstall()}
              disabled={installing || !installSpec.trim()}
              className="px-4 py-2 bg-primary text-on-primary rounded-lg text-sm font-medium hover:bg-primary/90 disabled:bg-surface-container-low/40 disabled:text-on-surface-variant/40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
            >
              {installing ? "Installing…" : "Install"}
            </button>
          </div>
          {installResult && (
            <div className="ml-9 mt-3 rounded-lg border border-white/10 bg-surface-container-low/40 p-3 text-xs font-mono text-on-surface-variant whitespace-pre-wrap max-h-40 overflow-y-auto">
              {installResult}
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-xl border border-error/30 bg-error/10 p-3 text-xs text-error">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-16 text-sm text-on-surface-variant/60">
            Loading catalog…
          </div>
        ) : catalog ? (
          <>
            <div className="rounded-2xl p-4" style={glassCard}>
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-secondary">
                  inventory_2
                </span>
                <div>
                  <div className="text-sm text-on-surface">
                    <strong>{catalog.total}</strong> plugin
                    {catalog.total === 1 ? "" : "s"} discovered across{" "}
                    {Object.keys(catalog.groups).length} groups.
                  </div>
                  <div className="text-xs text-on-surface-variant/70 mt-0.5">
                    Fresh installs see 0 — no third-party packages target
                    these entry-point groups yet. The contract is in place
                    for future plugin authors.
                  </div>
                </div>
              </div>
            </div>

            {Object.entries(GROUP_META).map(([group, meta]) => {
              const refs = catalog.groups[group] ?? [];
              return (
                <div
                  key={group}
                  className="rounded-2xl p-5 space-y-3"
                  style={glassCard}
                >
                  <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-primary">
                      {meta.icon}
                    </span>
                    <div className="flex-1">
                      <h2 className="text-sm font-semibold text-on-surface">
                        {meta.label}{" "}
                        <span className="text-xs font-mono text-on-surface-variant/70">
                          ({group})
                        </span>
                      </h2>
                      <p className="text-xs text-on-surface-variant/70 mt-0.5">
                        {meta.about}
                      </p>
                    </div>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-secondary/15 text-secondary">
                      {refs.length}
                    </span>
                  </div>

                  {refs.length === 0 ? (
                    <p className="text-xs text-on-surface-variant/60 italic pl-9">
                      (none discovered)
                    </p>
                  ) : (
                    <table className="w-full text-xs">
                      <thead className="bg-white/5">
                        <tr className="text-on-surface-variant/80">
                          <th className="text-left px-3 py-2 font-label">Name</th>
                          <th className="text-left px-3 py-2 font-label">Distribution</th>
                          <th className="text-left px-3 py-2 font-label">Target</th>
                          <th className="text-right px-3 py-2 font-label">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {refs.map((ref) => (
                          <tr
                            key={ref.name}
                            className="border-t border-white/5"
                          >
                            <td className="px-3 py-2 font-mono text-on-surface">
                              {ref.name}
                            </td>
                            <td className="px-3 py-2 font-mono text-on-surface-variant">
                              {ref.dist_name}{" "}
                              <span className="text-on-surface-variant/60">
                                {ref.dist_version}
                              </span>
                            </td>
                            <td className="px-3 py-2 font-mono text-on-surface-variant/70 truncate max-w-md">
                              {ref.target}
                            </td>
                            <td className="px-3 py-2 text-right whitespace-nowrap">
                              <button
                                onClick={() => void handleUninstall(ref.dist_name)}
                                disabled={uninstalling === ref.dist_name}
                                className="text-xs px-2 py-1 rounded border border-error/30 text-error hover:bg-error/10 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                              >
                                {uninstalling === ref.dist_name ? "Uninstalling…" : "Uninstall"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              );
            })}

            <div className="rounded-2xl p-5 text-xs text-on-surface-variant/70 space-y-2" style={glassCard}>
              <div className="font-semibold text-on-surface">
                How to author a plugin
              </div>
              <p>
                In your <code className="font-mono">pyproject.toml</code>:
              </p>
              <pre className="bg-surface-container-low/40 p-3 rounded-lg text-[11px] font-mono leading-relaxed overflow-x-auto">{`[project.entry-points."phantom.hooks"]
my-hook = "my_pkg.hooks:my_hook_factory"

[project.entry-points."phantom.skills"]
my-skill = "my_pkg.skills:my_skill_factory"`}</pre>
              <p>
                Then{" "}
                <code className="font-mono">
                  docker exec phantom_agent pip install ./your-package
                </code>{" "}
                + restart MCP. The package will appear in the table
                above after the next boot&apos;s{" "}
                <code className="font-mono">log_discovery()</code> call.
              </p>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
