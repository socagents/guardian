# Guardian self-learning loop — state

> Rendered from `.guardian-loop/state.json` by `scripts/loop/loop_state.py`.
> Do not hand-edit; change the JSON (or use the CLI) and re-render.

## Counters

- Cycles total: **2**
- Fixes shipped: **0**
- No-ops: **1**
- Gate failures: **0**
- Checker rejections: **1**

## Next focus

Redo as ONE complete doc-sync unit: jobs_create/jobs_update docstrings chat->prompt + drop log refs (self_mod_tools.py:768,930), job_scheduler.py:119 comment, system-prompt.ts:430 jobs_create action shape, jobs/new/page.tsx:9 header comment; grep type."chat"/log across agent lib+app for remaining hits

## Open findings

_none_

## Recent cycles (last 10)

| # | started | focus | outcome | commit | gate | checker |
|---|---|---|---|---|---|---|
| 1 | 2026-06-11T09:43:08Z | self-heal scan: doc-sync + bug-family + spec-drift repo-only audits | no-op | — | — | n/a |
| 2 | 2026-06-11T12:42:27Z | self-heal: MCP tool docstrings vs UI forms lockstep audit (docs discipline #9) | checker-rejected | — | pass | rejected |
