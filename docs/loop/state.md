# Guardian self-learning loop — state

> Rendered from `.guardian-loop/state.json` by `scripts/loop/loop_state.py`.
> Do not hand-edit; change the JSON (or use the CLI) and re-render.

## Counters

- Cycles total: **3**
- Fixes shipped: **0**
- No-ops: **1**
- Gate failures: **0**
- Checker rejections: **2**

## Next focus

THIRD attempt jobs chat->prompt doc-sync — redo ALL of: self_mod_tools.py:768,930 docstrings; job_scheduler.py:119,126 comments; system-prompt.ts:430 shape (+skill?, deprecated-alias note); jobs/new/page.tsx:9 header; jobs/[id]/page.tsx RunResultBody:476 AND describeAction:72-93; jobs-list-client.tsx actionLabel:205-224; api-catalog.ts:972 action shape; docs/spec-patch-yaml-job-defs.md:87 example. Then grep chat|log patterns across mcp/agent/lib, mcp/agent/app, mcp/agent/components, docs/ before declaring complete. Keep chat as legacy-row match in renderers; journeys.ts:916 + jobs/new:264 + job_scheduler.py:498 stay (intentional legacy refs).

## Open findings

_none_

## Recent cycles (last 10)

| # | started | focus | outcome | commit | gate | checker |
|---|---|---|---|---|---|---|
| 1 | 2026-06-11T09:43:08Z | self-heal scan: doc-sync + bug-family + spec-drift repo-only audits | no-op | — | — | n/a |
| 2 | 2026-06-11T12:42:27Z | self-heal: MCP tool docstrings vs UI forms lockstep audit (docs discipline #9) | checker-rejected | — | pass | rejected |
| 3 | 2026-06-11T13:17:22Z | redo doc-sync unit: jobs chat->prompt across docstrings, scheduler comments, system-prompt.ts, jobs/new header, RunResultBody | checker-rejected | — | pass | rejected |
