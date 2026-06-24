'use client';

import { useCallback, useRef, useState } from 'react';

/**
 * #CONN-F13 — drives the in-place stack upgrade from the About modal.
 *
 * POSTs /api/agent/update/apply and parses the updater's typed SSE
 * frames (`event: phase|pull_progress|error\ndata: <json>`). Tracks the
 * current phase + a bounded progress log. Handles the two tricky cases:
 *
 *  - After the `swapping` phase the guardian-agent container is replaced,
 *    so the SSE connection is severed mid-stream. We treat a disconnect
 *    AFTER `swapping` as an expected restart (status='restarting') and
 *    poll /api/agent/version until the agent answers, then reload — not
 *    an error.
 *  - `complete` / `noop` → success; auto-reload shortly after so the UI
 *    picks up the new version.
 */

export type UpdatePhase =
  | 'checking'
  | 'fetching_manifest'
  | 'comparing_digests'
  | 'pulling'
  | 'pulled'
  | 'applying_manifest'
  | 'swapping'
  | 'waiting_healthy'
  | 'complete'
  | 'noop'
  | string;

export type UpdateStatus =
  | 'idle'
  | 'streaming'
  | 'restarting'
  | 'complete'
  | 'error';

export interface UpdateStreamState {
  status: UpdateStatus;
  phase: UpdatePhase | null;
  log: string[];
  error: string | null;
  startUpdate: () => void;
  abort: () => void;
}

const MAX_LOG = 200;

const PHASE_LABEL: Record<string, string> = {
  checking: 'Checking for updates…',
  fetching_manifest: 'Fetching release manifest…',
  comparing_digests: 'Comparing image digests…',
  pulling: 'Pulling new images…',
  pulled: 'Images pulled.',
  applying_manifest: 'Applying manifest…',
  swapping: 'Swapping containers…',
  waiting_healthy: 'Waiting for services to become healthy…',
  complete: 'Update complete.',
  noop: 'Already up to date.',
};

export function useUpdateStream(): UpdateStreamState {
  const [status, setStatus] = useState<UpdateStatus>('idle');
  const [phase, setPhase] = useState<UpdatePhase | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const swappingRef = useRef(false);

  const append = useCallback((line: string) => {
    setLog((cur) => {
      const next = [...cur, line];
      return next.length > MAX_LOG ? next.slice(next.length - MAX_LOG) : next;
    });
  }, []);

  // Poll /api/agent/version until the (restarted) agent answers, then reload.
  const waitForAgentBack = useCallback(async () => {
    for (let i = 0; i < 120; i++) {
      try {
        const r = await fetch('/api/agent/version', { cache: 'no-store' });
        if (r.ok) {
          append('Agent is back online — reloading…');
          setTimeout(() => window.location.reload(), 1500);
          return;
        }
      } catch {
        /* still down — keep polling */
      }
      await new Promise((res) => setTimeout(res, 2500));
    }
    setStatus('error');
    setError('Agent did not come back within the expected window. Reload manually to check.');
  }, [append]);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const startUpdate = useCallback(() => {
    if (status === 'streaming' || status === 'restarting') return;
    swappingRef.current = false;
    setStatus('streaming');
    setPhase('checking');
    setLog([]);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    (async () => {
      let resp: Response;
      try {
        resp = await fetch('/api/agent/update/apply', {
          method: 'POST',
          signal: controller.signal,
        });
      } catch (e) {
        setStatus('error');
        setError(e instanceof Error ? e.message : 'could not start update');
        return;
      }

      if (resp.status === 409) {
        // An update is already running (started elsewhere / a prior tab).
        // Re-attach: poll status, and once it finishes the agent restarts.
        append('An update is already in progress — attaching…');
        setStatus('restarting');
        swappingRef.current = true;
        waitForAgentBack();
        return;
      }
      if (!resp.ok || !resp.body) {
        setStatus('error');
        setError(`update failed to start (HTTP ${resp.status})`);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split('\n\n');
          buffer = frames.pop() || '';
          for (const frame of frames) {
            let evType = 'message';
            let dataLine = '';
            for (const raw of frame.split('\n')) {
              const lineStr = raw.trim();
              if (lineStr.startsWith('event:')) evType = lineStr.slice(6).trim();
              else if (lineStr.startsWith('data:')) dataLine = lineStr.slice(5).trim();
            }
            if (!dataLine) continue;
            let data: Record<string, unknown> = {};
            try {
              data = JSON.parse(dataLine);
            } catch {
              continue;
            }

            if (evType === 'phase') {
              const ph = String(data.phase ?? '');
              setPhase(ph);
              append(PHASE_LABEL[ph] || `Phase: ${ph}`);
              if (ph === 'swapping') swappingRef.current = true;
              if (ph === 'complete' || ph === 'noop') {
                setStatus('complete');
                setTimeout(() => window.location.reload(), 3000);
                return;
              }
            } else if (evType === 'pull_progress') {
              const svc = data.service ?? '';
              const ref = data.package ?? data.ref ?? '';
              append(`  pull ${svc} ${ref}`.trimEnd());
            } else if (evType === 'error') {
              setStatus('error');
              setError(String(data.detail ?? data.error ?? 'update error'));
              return;
            }
          }
        }
        // Stream ended without a terminal phase. If we passed `swapping`,
        // the agent container was replaced (expected) — wait for it back.
        if (swappingRef.current) {
          setStatus('restarting');
          append('Connection closed during swap — the agent is restarting.');
          waitForAgentBack();
        } else if (status !== 'complete') {
          setStatus('error');
          setError('Update stream ended unexpectedly.');
        }
      } catch (e) {
        if (controller.signal.aborted) return; // operator closed the modal
        if (swappingRef.current) {
          setStatus('restarting');
          append('Connection dropped during swap — the agent is restarting.');
          waitForAgentBack();
        } else {
          setStatus('error');
          setError(e instanceof Error ? e.message : 'update stream error');
        }
      } finally {
        abortRef.current = null;
      }
    })();
  }, [status, append, waitForAgentBack]);

  return { status, phase, log, error, startUpdate, abort };
}
