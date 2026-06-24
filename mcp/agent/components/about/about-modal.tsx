"use client";

/**
 * About Guardian — centered overlay modal showing version + runtime
 * metadata. Deliberately scoped to JUST the "what am I running"
 * question, modeled after the Cortex XSIAM About dialog.
 *
 * "What's new" and "Release history" intentionally live on separate
 * pages (/about/whats-new + /about/history) so they open in a new
 * browser tab — operators don't want long-form release notes inside
 * a modal they have to dismiss to keep working.
 *
 * Architecture: the running version comes from /api/agent/version
 * (compose-interpolated GUARDIAN_VERSION). Static release-notes data
 * lives in lib/release-notes.ts so this works offline.
 *
 * Why we render via React Portal:
 *   The sidebar's <aside> has `backdrop-blur-xl` (backdrop-filter set).
 *   Per CSS spec, an ancestor with `backdrop-filter`, `transform`,
 *   `filter`, `perspective`, `will-change`, or `contain: paint`
 *   becomes the containing block for any `position: fixed`
 *   descendant — silently scoping the modal's `inset-0` to the
 *   sidebar's 16rem-wide rectangle instead of the viewport. That
 *   produced the bug where this modal rendered as a panel inside the
 *   sidebar instead of as a centered overlay. Portaling the modal to
 *   document.body moves the DOM node out of the sidebar subtree, so
 *   `fixed` resolves against the viewport again.
 */

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { findRelease } from "@/lib/release-notes";
import { useUpdateStream } from "@/lib/use-update-stream";

interface AboutModalProps {
  open: boolean;
  onClose: () => void;
}

interface UpdateCheck {
  updates_available?: boolean;
  latest_version?: string;
  running_version?: string;
  error?: string;
}

const glassStyle = {
  background: "var(--glass-bg-strong)",
  backdropFilter: "blur(12px)",
  border: "0.5px solid var(--glass-border)",
} as const;

export function AboutModal({ open, onClose }: AboutModalProps) {
  const [version, setVersion] = useState<string | null>(null);
  // `mounted` gates the portal: document.body doesn't exist during
  // SSR, so we wait until after hydration to mount. Without this,
  // calling createPortal(..., document.body) would throw on the
  // server render. (Belt-and-suspenders — `open` is also false on
  // initial render, so the modal wouldn't try to render anyway —
  // but this protects future callers that might force-open.)
  const [mounted, setMounted] = useState(false);
  // #CONN-F13 — in-place upgrade affordance.
  const [updateCheck, setUpdateCheck] = useState<UpdateCheck | null>(null);
  const upd = useUpdateStream();
  const logEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // #CONN-F13 — check for a newer release when the modal opens.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setUpdateCheck(null);
    fetch("/api/agent/update/check", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data) setUpdateCheck(data as UpdateCheck);
      })
      .catch(() => {
        /* updater unreachable → no update affordance */
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  // Keep the progress log scrolled to the newest line.
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "end" });
  }, [upd.log]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    fetch("/api/agent/version", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data?.version) setVersion(String(data.version));
      })
      .catch(() => {
        // Network error → leave version null; modal shows "—".
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  // ESC closes the modal.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !mounted) return null;

  const inHistory = version ? Boolean(findRelease(version)) : false;

  // Portal target: document.body. This is the whole point of the
  // portal — escapes the sidebar's containing-block trap (see file
  // header). z-50 + the dark backdrop means we sit above page
  // content while still respecting the modal stacking convention.
  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style={{ background: "rgba(0, 0, 0, 0.6)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md max-h-[85vh] flex flex-col rounded-2xl overflow-hidden"
        style={glassStyle}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="px-6 py-5 flex items-start justify-between shrink-0">
          <p className="text-[10px] font-label uppercase tracking-widest text-on-surface-variant">
            About
          </p>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-on-surface-variant"
            aria-label="Close"
          >
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </header>

        {/* Body — centered identity block + key facts */}
        <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-6">
          <section className="text-center">
            <h2 className="font-headline text-3xl font-bold text-on-surface">
              Guardian
            </h2>
            <p className="font-mono text-base text-primary mt-1">
              v{version ?? "—"}
            </p>
            {!inHistory && version && (
              <p className="text-[11px] text-on-surface-variant mt-2">
                Dev build — release notes not yet committed for this version.
              </p>
            )}
          </section>

          {/* #CONN-F13 — in-place upgrade. Idle: show "update available"
              banner + Upgrade button (or an up-to-date note). Streaming /
              restarting: phase label + scrollable progress log. */}
          <section aria-live="polite">
            {upd.status === "idle" && updateCheck?.updates_available && (
              <div
                className="rounded-xl px-4 py-3"
                style={{ background: "var(--secondary-container, rgba(86,181,90,0.12))" }}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[13px] font-semibold text-on-surface">
                      Update available
                    </p>
                    <p className="text-[11px] text-on-surface-variant font-mono mt-0.5">
                      v{updateCheck.running_version ?? version ?? "—"} → v
                      {updateCheck.latest_version ?? "?"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={upd.startUpdate}
                    className="shrink-0 inline-flex items-center gap-1.5 px-4 h-9 rounded-lg bg-secondary text-on-secondary text-sm font-bold hover:opacity-90 transition-opacity"
                  >
                    <span className="material-symbols-outlined text-lg">
                      system_update_alt
                    </span>
                    Upgrade
                  </button>
                </div>
                <p className="text-[10px] text-on-surface-variant/80 mt-2">
                  Pulls the new images and swaps containers in place; the agent
                  briefly restarts and this page reloads when it&apos;s back.
                </p>
              </div>
            )}

            {upd.status === "idle" &&
              updateCheck &&
              !updateCheck.updates_available &&
              !updateCheck.error && (
                <p className="text-[12px] text-on-surface-variant text-center inline-flex items-center justify-center gap-1.5 w-full">
                  <span className="material-symbols-outlined text-[16px] text-secondary">
                    check_circle
                  </span>
                  You&apos;re on the latest release.
                </p>
              )}

            {(upd.status === "streaming" ||
              upd.status === "restarting" ||
              upd.status === "complete" ||
              upd.status === "error") && (
              <div className="rounded-xl px-4 py-3" style={glassStyle}>
                <div className="flex items-center gap-2">
                  {upd.status === "complete" ? (
                    <span className="material-symbols-outlined text-lg text-secondary">
                      check_circle
                    </span>
                  ) : upd.status === "error" ? (
                    <span className="material-symbols-outlined text-lg text-error">
                      error
                    </span>
                  ) : (
                    <span className="material-symbols-outlined text-lg text-primary animate-spin">
                      progress_activity
                    </span>
                  )}
                  <p className="text-[13px] font-semibold text-on-surface">
                    {upd.status === "complete"
                      ? "Update complete — reloading…"
                      : upd.status === "error"
                      ? "Update failed"
                      : upd.status === "restarting"
                      ? "Restarting — waiting for the agent to come back…"
                      : "Updating…"}
                  </p>
                </div>
                {upd.error && (
                  <p className="text-[11px] text-error mt-2">{upd.error}</p>
                )}
                {upd.log.length > 0 && (
                  <div className="mt-2 max-h-32 overflow-y-auto rounded-lg bg-black/20 p-2 font-mono text-[10px] text-on-surface-variant leading-relaxed">
                    {upd.log.map((line, i) => (
                      <div key={i} className="whitespace-pre-wrap">
                        {line}
                      </div>
                    ))}
                    <div ref={logEndRef} />
                  </div>
                )}
                {upd.status === "error" && (
                  <button
                    type="button"
                    onClick={upd.startUpdate}
                    className="mt-2 text-[12px] text-primary hover:underline"
                  >
                    Retry
                  </button>
                )}
              </div>
            )}
          </section>

          <section>
            <p className="text-[10px] font-label uppercase tracking-widest text-on-surface-variant mb-2">
              About this product
            </p>
            <p className="text-[13px] text-on-surface-variant leading-relaxed">
              AI incident-response agent for Cortex XSIAM and XSOAR:
              evidence-grounded investigations, XQL hunts, case
              enrichment, and orchestrated response workflows over MCP.
              Ships as a Docker Compose stack (guardian-agent,
              guardian-browser, guardian-updater, per-instance
              connector containers).
            </p>
          </section>

          <section>
            <p className="text-[10px] font-label uppercase tracking-widest text-on-surface-variant mb-2">
              Useful surfaces
            </p>
            <ul className="space-y-1.5 text-[13px] text-on-surface-variant leading-relaxed">
              <li className="flex gap-2">
                <span className="text-primary/70 shrink-0">•</span>
                <a className="text-primary hover:underline" href="/health">
                  /health
                </a>
                <span className="text-on-surface-variant/70">— stack health snapshot</span>
              </li>
              <li className="flex gap-2">
                <span className="text-primary/70 shrink-0">•</span>
                <a
                  className="text-primary hover:underline"
                  href="/observability/runtime-events"
                >
                  /observability/runtime-events
                </a>
                <span className="text-on-surface-variant/70">— event feed</span>
              </li>
              <li className="flex gap-2">
                <span className="text-primary/70 shrink-0">•</span>
                <a className="text-primary hover:underline" href="/connectors">
                  /connectors
                </a>
                <span className="text-on-surface-variant/70">— instances + probe</span>
              </li>
            </ul>
          </section>

          <section>
            <p className="text-[10px] font-label uppercase tracking-widest text-on-surface-variant mb-2">
              Source
            </p>
            <a
              href="https://github.com/kite-production/guardian"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[13px] text-primary hover:underline inline-flex items-center gap-1"
            >
              github.com/kite-production/guardian
              <span className="material-symbols-outlined text-[14px]">
                open_in_new
              </span>
            </a>
          </section>
        </div>
      </div>
    </div>,
    document.body,
  );
}
