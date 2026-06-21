# Structured Investigation Data Model — Arc Overview

**Status:** approved (full structured model), decomposed into a 4-stage arc — 2026-06-21
**Goal:** Turn Guardian's prose-based investigations into a structured, queryable, cross-incident data model that makes each investigation consistent + defensible and unlocks fleet/campaign analytics — while preserving the existing autonomous loop + judge.

## Why an arc (decomposition)

The "full structured model" is too large for one spec/release. It decomposes into four independently-shippable stages with a strict dependency order. Each stage = its own spec → plan → build → gate → live-smoke → release. The keystone (A) delivers value alone; B/C/D layer on top.

| Stage | Title | Depends on | Ships |
|---|---|---|---|
| **A** | Structured investigation record + report | — | verdict/confidence/blast-radius fields, technique_mappings table, generate_investigation_report, UI + skill + judge updates |
| **B** | Multi-source defensible depth | A | XQL blast-radius hunt wired into the lifecycle, push_verdict_to_xsoar, containment-recommendation step |
| **C** | Campaign / cross-incident analytics | A, B | case campaign rollup, playbook-match table, cross-case edges, relationship inference |
| **D** | Export + interop | A, C | STIX bundle export, report templates, ticket/webhook handoff |

## Foundations being reused (do NOT rebuild)

- **`xsoar_case_investigation`** workflow skill (the mandatory monitor→fetch→research→enrich→document→resolve lifecycle). Stages EXTEND it; never replace the filename (the judge whitelist + `bootstrap_loop_jobs.sh` reference `skill: xsoar_case_investigation`).
- **Investigation module** — SQLite store (`investigation_store.py`: Issue/Case/IssueEvent/Indicator/Relationship), 16 MCP tools (`investigation_tools.py` + `indicator_tools.py`), REST (`api/investigation.py`), UI (`/investigation/*`).
- **Autonomous loop** — seeder→investigator(cron */30, runs the skill)→judge(cron 0 */6, scores resolved Issues + self-edits the skill via `skills_update`). Structural dedup: seeder creates Issues; investigator has `denied_tools:[issue_create]`.
- **Verdict convention** — `summary` may start with a `VERDICT: …` line, rendered as a banner by `splitVerdict`/`verdictTone` (`components/investigation/ui.tsx`). All stages keep this back-compatible.
- **Hooks** — `block-close-without-verdict` (PreToolUse on `xsoar_close_incident`), `flag-malicious-indicator` (PostToolUse on `xsoar_enrich_indicator`).
- **KBs** — soc-investigation, mitre-attack-enterprise/ics/mobile, mitre-atlas, soar-playbooks, xql-examples — via `knowledge_search`.

## Cross-cutting principles

- **Additive, backward-safe migrations** — investigation_store schema changes are `ALTER TABLE … ADD COLUMN` (defaulted) or new tables; pre-migration DBs upgrade cleanly on boot (cover with a "pre-migration db gets column" test, the jobs-store pattern).
- **Catalog-side** — the investigation module has no SecretStore access; all new tools are agent-callable (no approval gate) EXCEPT containment execution (B), which stays recommend-only / approval-gated.
- **Agent-image-only where possible** — store/tools/skill/UI all live in the agent image (rebuilds every push, no connector rebuild). B's XQL hunt uses existing connector tools (no connector change).
- **Loop + judge benefit automatically** — because stages populate the same Issue schema the judge reads, and extend the same skill the loop runs, every stage upgrades the autonomous loop with no scheduler change. Judge rubric is extended per stage via `PATCH /api/agent/jobs/guardian-investigation-judge`.
- **Each stage**: TDD (pytest for store/tools; tsc for UI), full gate, push → agent build/deploy, in-container live smoke (KB/tool/skill + a headless `/api/chat` e2e where it exercises the new flow), then tag + release.

See the per-stage specs:
`2026-06-21-investigation-A-structured-record.md`, `…-B-multisource-depth.md`, `…-C-campaign-analytics.md`, `…-D-export-interop.md`.
