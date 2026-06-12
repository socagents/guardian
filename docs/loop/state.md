# Guardian self-learning loop — state

> Rendered from `.guardian-loop/state.json` by `scripts/loop/loop_state.py`.
> Do not hand-edit; change the JSON (or use the CLI) and re-render.

## Counters

- Cycles total: **4**
- Fixes shipped: **0**
- No-ops: **1**
- Gate failures: **0**
- Checker rejections: **3**

## Next focus

FIFTH attempt jobs chat->prompt doc-sync — redo the full cycle-4 diff (self_mod_tools.py jobs_create+jobs_update docstrings; job_scheduler.py:119,126 comments; system-prompt.ts:430 shape+skill?+alias note; jobs/new:9 header; jobs/[id] describeAction:72-93 + RunRow comment:326-338 + RunResultBody:483; jobs-list-client actionLabel:205-224; api-catalog.ts:972; spec-patch-yaml-job-defs.md:87) PLUS checker-found hits: help/user/page.tsx:420-422,2015,4455 prose 'chat actions'/'(chat / tool_call / log)'; help/architecture/page.tsx:1396 'chat-action job'; jobs/new:545-547 false claim that log rows migrate to tool_call (they are rejected, only chat->prompt migrates). Completeness grep MUST include case-insensitive 'action.{0,40}(chat|log)' + '(chat|log).{0,20}action' over mcp/agent/app/help + all prior literal-shape greps. Keeps: migration/alias code, legacy renderer branches, journeys.ts:916, jobs/new:264, job_scheduler.py:498, tests, model kind==chat, audit event names.

## Open findings

_none_

## Recent cycles (last 10)

| # | started | focus | outcome | commit | gate | checker |
|---|---|---|---|---|---|---|
| 1 | 2026-06-11T09:43:08Z | self-heal scan: doc-sync + bug-family + spec-drift repo-only audits | no-op | — | — | n/a |
| 2 | 2026-06-11T12:42:27Z | self-heal: MCP tool docstrings vs UI forms lockstep audit (docs discipline #9) | checker-rejected | — | pass | rejected |
| 3 | 2026-06-11T13:17:22Z | redo doc-sync unit: jobs chat->prompt across docstrings, scheduler comments, system-prompt.ts, jobs/new header, RunResultBody | checker-rejected | — | pass | rejected |
| 4 | 2026-06-12T04:06:59Z | FOURTH attempt blocked: jobs chat->prompt doc-sync redo (all cycle-3 surfaces + RunRow comment block) | checker-rejected | — | pass | rejected |
