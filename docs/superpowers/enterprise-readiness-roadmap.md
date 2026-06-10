# Phantom enterprise-readiness program — master roadmap

**Operator aim (verbatim intent):** Phantom is a customer product, not a lab tool. Quality, clean architecture, clean design, **no shortcuts, no workarounds**. Every UI button has a purpose and works; no bugs; every module exercised; observability covers every action; docs (user / architecture / API) current and detailed; hooks + subagents tested. Fully autonomous; go with recommendations aligned to quality.

**Sequencing (operator-ordered):** A → B → C. Do NOT start B until A is materially complete; do NOT start C until B is complete.

> Master anchor for a multi-day effort. Re-read on any new context window. Each phase has its own living doc + GitHub issue. Ship fixes as contained releases; never tag a customer release without explicit operator approval.

---

## Phase A — Data-source deep-dive XDM smoke (IN PROGRESS)

- Issue **#106**. Living doc: `docs/superpowers/smoke-campaign-2026-05-29.md`.
- 2-stage: (1) agent-direct max-field simulate → XQL-verify XDM saturation per source, fix YAML/skill/generator until the majority of fields map; (2) Phantom-chat agent does the same via the skill.
- Likely central fix: `xlog/app/dynamic_schema.py` `type: json` composite synthesis (design recorded in the campaign doc).
- **Status:** P0 deploy-gate done (v0.17.103 live); P1 baseline running.

## Phase B — UI quality walk + module/hook/subagent test (PENDING A)

Goal: every page + subpage works end-to-end; every affordance has a purpose; no bugs; observability covers every mutation.

- [ ] **Inventory** every page/subpage: `find mcp/agent/app -name page.tsx` vs the sidebar nav; list every interactive affordance (buttons, dropdowns, modals, forms, toggles).
- [ ] **Per-page walk** (UI via Chrome/computer-use, logged in admin/LAB_P@ssw0rd; or fetch the JSON endpoints each page reads): exercise each affordance, confirm it does what it claims, capture bugs.
- [ ] **Module coverage** — exercise each functional module end-to-end: data sources (covered by Phase A), **log destinations ("drops" — confirm operator meaning during walk: destinations vs drag-drop vs dropdowns)**, connectors + instances, providers, marketplace install/uninstall, skills CRUD + toggles, jobs/workers, chat (model routing), profile/auth, setup.
- [ ] **Hooks** — exercise the AI-layer hooks (see `AI-LAYER.md`): confirm each hook fires on its trigger + does its job; no broken/stale hooks.
- [ ] **Subagents** — exercise the AI-layer subagents: confirm each is invokable + functions.
- [ ] **Observability completeness** — for every operator action (every mutation across the modules above), confirm an audit/observability event is emitted + visible in `/observability/*`. Grep the audit-emit sites vs the mutation endpoints; fill gaps.
- [ ] Fix every bug found (contained releases). Track in the Phase-B doc.

## Phase C — Documentation / API / observability deep-dive (PENDING B)

Goal: docs match the deployed reality, detailed + enterprise-grade.

- [ ] **Architecture guide** (`app/help/architecture/page.tsx`) — service list matches `docker compose ps -a`; every feature added since last audit has an accurate section; inter-service wiring documented (source→dest port, auth, failure mode, sync/async); no spec drift (architecture-page-is-the-spec).
- [ ] **User guide** (`app/help/user/page.tsx`) — every operator-visible feature has a current section, version-tagged; removed/changed features updated.
- [ ] **API guide** — every `/api/agent/*` endpoint + every agent-callable MCP tool documented + current. (Confirm where the API reference actually lives — `app/help/api/*` is a dynamic route, may need a real catalog.)
- [ ] **Observability docs** — every telemetry surface documented + matches what's emitted.
- [ ] **Journeys** (`lib/journeys.ts`) — every documented flow has a journey; retired flows stubbed.
- [ ] **Release notes / CHANGELOG** coherence — the unreleased batch (v0.17.99–103 + this campaign's fixes) reads as a coherent story.

---

## Cross-cutting discipline (all phases)

- Spec-driven: an issue per non-trivial change; `Refs/Closes #N`; mechanical status labels.
- Pre-deploy gate before every push (tsc + lint + build + pytest). Wait-for-CI: own the deploy + verify, never punt.
- Contained releases: one concept per release; docs ship with code.
- **Customer tag = explicit operator approval only.** Everything else (build, deploy, smoke, iterate) is autonomous.
- Never end a turn idle while the operator is away — keep a background task pending or a wakeup armed.

## Decisions / clarifications to resolve during the walk

- "drops" — operator listed alongside modules/hooks/subagents. Resolve meaning when walking the UI (most likely log destinations; possibly dropdowns/drag-drop). Test whatever it maps to.
