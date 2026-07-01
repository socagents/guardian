# Guardian self-learning loop — state

> Rendered from `.guardian-loop/state.json` by `scripts/loop/loop_state.py`.
> Do not hand-edit; change the JSON (or use the CLI) and re-render.

## Counters

- Cycles total: **7**
- Fixes shipped: **1**
- No-ops: **2**
- Gate failures: **0**
- Checker rejections: **4**

## Active unit

- **connector-tool-count-doc-sync** — Connector tool-count doc-sync: stale hardcoded counts on living surfaces vs connector.yaml ground truth
  - mode: `narrow` · rejections: 0 · remaining slices: 2
  - scope: Slice 1 (this cycle, xsiam=56): route.ts:166,172; journeys.ts:4755; help/architecture:7379; help/user:3120; connectors/CLAUDE.md:11; CODEBASE_MAP.md:73; xsiam tests docstring:9. Keeps: CHANGELOG 905/917, release-notes.ts:964, route.ts:189 versions[], connectors/page.tsx:2942 comment, connector.py/yaml batch comments.

## Deferred — needs human

- **jobs-chat-prompt-doc-sync** — Jobs action-type doc-sync: chat->prompt terminology drift across docstrings, system-prompt, UI renderers, help-page prose → https://github.com/kite-production/guardian/issues/3
  - blocked on: Accumulated over cycles 2-4 (pre-Phase-1.5, backfilled): (c2) system-prompt.ts:430 type:'chat' + jobs/new:9 header stale; (c3) comparison branches describeAction jobs/[id]:72 + actionLabel jobs-list-client:205 + api-catalog.ts:972 + spec-patch-yaml-job-defs.md:87; (c4) prose evades literal greps — help/user/page.tsx:420-422,2015,4455 + help/architecture/page.tsx:1396 'chat-action job' + jobs/new:545-547 FALSE claim log rows migrate to tool_call (validator rejects log; only chat->prompt migrates). Each attempt fixed all enumerated surfaces and the gate passed 7/7, but the checker found a new same-family stratum every time (literal shapes -> comparison branches -> prose). Completeness needs case-insensitive 'action.{0,40}(chat|log)' + '(chat|log).{0,20}action' over mcp/agent/app/help + all prior greps, with every hit justified.

## Next focus

Continue unit connector-tool-count-doc-sync slice 2: xsoar tool-count sync (yaml=39) — README.md:31, help/user:3255, journeys.ts:4143, external-connectors-anatomy.tsx:113

## Open findings

_none_

## Recent cycles (last 10)

| # | started | focus | outcome | commit | gate | checker |
|---|---|---|---|---|---|---|
| 1 | 2026-06-11T09:43:08Z | self-heal scan: doc-sync + bug-family + spec-drift repo-only audits | no-op | — | — | n/a |
| 2 | 2026-06-11T12:42:27Z | self-heal: MCP tool docstrings vs UI forms lockstep audit (docs discipline #9) | checker-rejected | — | pass | rejected |
| 3 | 2026-06-11T13:17:22Z | redo doc-sync unit: jobs chat->prompt across docstrings, scheduler comments, system-prompt.ts, jobs/new header, RunResultBody | checker-rejected | — | pass | rejected |
| 4 | 2026-06-12T04:06:59Z | FOURTH attempt blocked: jobs chat->prompt doc-sync redo (all cycle-3 surfaces + RunRow comment block) | checker-rejected | — | pass | rejected |
| 5 | 2026-06-12T07:07:36Z | defer-after-K handoff: jobs-chat-prompt-doc-sync (wide, 3 checker rejections in cycles 2-4) | checker-rejected | — | — | n/a |
| 6 | 2026-06-12T08:12:56Z | Fresh self-heal scan: doc-sync + bug-family + spec-drift repo-only audits | no-op | — | — | n/a |
| 7 | 2026-07-01T22:30:42Z | connector-tool-count-doc-sync slice 1: xsiam tool count -> 56 across living surfaces | fixed | — | pass | approved |
