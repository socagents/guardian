# Changelog

All notable changes to Guardian are documented here.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0 releases bump the patch on every tagged release; minor bumps will resume after the v1.0.0 cut.

Each release section is written in operator language, not git-shortlog language. For commit-level granularity, run `git log vPREV..vNEW`.

<!-- [guardian v0.1.0] Retired: the upstream Phantom release history (v0.1.x–v0.17.x) — Guardian is a new product; the inherited changelog described subsystems that no longer exist here. -->

---

## [v0.2.4] (unreleased) — *Hooks page modernization*

The `/settings/hooks` CRUD views get the same polished, glass, Material-3 treatment as the Investigation pages. Pure UI — no change to the hook engine, transports, events, or the stored hook shape.

### What ships

- **Summary cards** — the page opens with four stat cards: total hooks · enabled · disabled · fail-closed (computed from the existing hook list, no new fetch).
- **Filter bar** — event-group chips (Tool · Prompt · Compaction · Run · Subagent · Other) + a name filter over the in-memory list, with an "N of M" count.
- **Slimmer hook rows** — each row now leads with three at-a-glance badges (event · transport · fail-closed), demoting the tool glob / trigger / priority to a muted second line; shared glass styling.
- **Tabbed editor drawer** — the create/edit drawer is now a glass panel with its fields grouped into tabs (Metadata · Matching · Transport · Execution), so a hook is configured one concern at a time instead of one long column. Validation jumps to the tab holding the offending field.
- **Shared empty state** — the "no hooks" view uses the standard glass empty-state with an "Add your first hook" CTA.
- The descriptive one-liner under the title is unchanged in wording but renders as a tight single descriptor rather than a wrapped block.

### Files

- `mcp/agent/app/settings/hooks/page.tsx` (reuses `components/investigation/ui.tsx` primitives: `glassStyle`, `Badge`, `StatCard`, `EmptyState`, `InvestigationTabBar`). Docs: `app/help/user/page.tsx#hooks-ux`, `CHANGELOG.md`, `lib/release-notes.ts`. See [#18](https://github.com/kite-production/guardian/issues/18).

### Change scenario

**Scenario 1** — code-only (agent image); no storage/engine change; volumes preserved. Patch bump (v0.2.4).

---

## [v0.2.3] (unreleased) — *Investigation diagram hardening*

Hardening pass over the v0.2.1/v0.2.2 diagram + relations work, from a post-release adversarial code review. No new feature surface — correctness, robustness, and doc-accuracy fixes.

### What ships

- **Regenerate no longer hangs silently.** The diagram Generate/Regenerate flow (issue + case tabs) now checks the job-submission response and surfaces an error if it fails, instead of leaving a "Regenerating…" spinner running to the 3-minute timeout. The one-shot job name is now collision-proof, and a timeout shows an actionable message + refreshes to the latest state.
- **SVG sanitizer closes two gaps.** The agent-produced-SVG cleaner now also strips `<foreignObject>` and unquoted `on*=` event handlers (it already stripped `<script>` + quoted handlers). The diagrams render sandboxed as `<img>` data-URIs (a no-script context) so there was no live exploit, but the stored markup now matches the documented contract.
- **Relationship validation.** `add_relationship` rejects an empty `source_type` (the column is `NOT NULL`), matching the schema.
- **Type + doc accuracy.** `IndicatorDetail.relationships` is now non-optional (the REST endpoint always populates it). The architecture page's `investigations.db` schema diagram is corrected to match the code (`issue_events` columns, `cases`/`issues` column lists).

### Files

- `bundles/spark/mcp/src/usecase/builtin_components/investigation_tools.py` (`_clean_svg` foreignObject + unquoted-handler strips) + `usecase/investigation_store.py` (`add_relationship` guard). +2 tests.
- `mcp/agent/app/investigation/issues/[id]/page.tsx` + `app/investigation/cases/[id]/page.tsx` (regenerate error-handling + timeout feedback), `lib/api/investigation.ts` (`relationships` non-optional), `app/help/architecture/page.tsx` (schema-diagram corrections). See [#17](https://github.com/kite-production/guardian/issues/17).

### Change scenario

**Scenario 1** — code-only (agent image); no storage change; volumes preserved. Patch bump (v0.2.3).

---

## [v0.2.2] (unreleased) — *Case-view attack chain + relations canvas*

The on-demand diagrams come to **Cases**: a multi-issue case now gets a campaign-level attack chain and relations canvas, synthesized across all the issues grouped under it.

### What ships

- **Case detail is now tabbed** — Issues · Attack chain · Relations (it was a flat issue list before). The Issues tab is the previous grouped-issue view.
- **Campaign-level attack chain** — the Case's Attack chain tab draws ONE causal diagram spanning all the case's issues (the shared kill-chain across the campaign), generated on demand like the issue-level chain.
- **Campaign-level relations canvas** — the Case's Relations tab draws ONE STIX graph over the union of the case's issues' indicators, surfacing the shared infrastructure / techniques / actors that tie the campaign together.
- **Agent tools** (catalog side — no secrets): `case_set_attack_chain` · `case_set_relation_graph` (mirror the issue tools; all four diagram tools now share one `_clean_svg` validator). The two skills (`svg_attack_chain`, `svg_relation_graph`) gained a case-level (campaign) variant.
- The SVGs ride on the existing case detail REST + proxy; the `DiagramTab` component was lifted into the shared module so the issue + case pages render diagrams identically.

### Storage

Additive to `investigations.db`: `attack_chain_svg` + `relations_canvas_svg` columns on `cases` (via `ALTER TABLE … ADD COLUMN`; existing data untouched). Kept off the lean Case DTO/list — read only on the case detail.

### Files

- `bundles/spark/mcp/src/usecase/investigation_store.py` (cases columns + migration + `set/get_case_attack_chain` + `set/get_case_relations_canvas`) + `builtin_components/investigation_tools.py` (`_clean_svg` helper + `case_set_attack_chain` + `case_set_relation_graph`) + `connector_loader.py` + `api/investigation.py` + `skills/workflows/svg_attack_chain.md` + `skills/workflows/svg_relation_graph.md` (case-level variants). +6 tests.
- `mcp/agent/components/investigation/ui.tsx` (shared `DiagramTab`), `app/investigation/cases/[id]/page.tsx` (tabs + diagram tabs + case regenerate), `app/investigation/issues/[id]/page.tsx` (imports shared `DiagramTab`), `lib/api/investigation.ts` (`CaseDetail` SVG fields). See [#16](https://github.com/kite-production/guardian/issues/16).

### Change scenario

**Scenario 1** — code-only (agent image); additive columns (volumes preserved); no installer change. Patch bump (v0.2.2).

---

## [v0.2.1] (unreleased) — *Relations canvas + STIX indicator attribution*

A STIX relationship layer over the Investigation module: Guardian records typed edges between indicators and other entities, attributes IoCs to techniques / malware / campaigns / actors, and draws an on-demand **Relations canvas** per issue — the relational companion to the causal Attack chain.

### What ships

- **Relations canvas** — the issue detail gains a **Relations** tab: a self-contained, layered STIX graph of the issue's indicators and how they relate to each other and to ATT&CK techniques, malware, campaigns, and threat-actors. Generated on demand (button) like the Attack chain, via a one-shot agent pass; rendered sandboxed as an `<img>` data-URI.
- **Indicator attribution** — a new agent action `indicator_relate` records a STIX-style edge from an indicator to a target (another IoC, an ATT&CK technique, a malware/tool, a campaign, an intrusion-set, or a threat-actor). The verb (`resolves-to`, `indicates`, `attributed-to`, `uses`, …) is a STIX verb stored verbatim, so it round-trips with XSOAR's EntityRelationship enum + MITRE ATT&CK. Edges are deduped by (source, verb, target).
- **Relationships on the indicator** — the Indicator detail gains a **Relationships** section listing every edge from that IoC (source → verb → target, with the target's STIX type).
- **Skill wiring** — the `xsoar_case_investigation` lifecycle now records relationships as it attributes (Step 6) and draws the relations canvas at resolve; a new `svg_relation_graph` skill carries the layout + safety contract (mirrors `svg_attack_chain`).
- **Agent tools** (catalog side — no secrets): `indicator_relate` · `issue_set_relation_graph`. The relations canvas SVG + the indicator's relationships ride on the existing issue/indicator detail REST + proxies.

### Storage

Additive to `investigations.db`: a new `relationships` table (STIX edges, unique on `(source_id, relationship_type, target_value, target_type)`) + a `relations_canvas_svg` column on `issues`, both created on boot via `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE … ADD COLUMN` (no destructive migration; existing data untouched).

### Files

- `bundles/spark/mcp/src/usecase/investigation_store.py` (`relationships` table + `relations_canvas_svg` column + `add_relationship`/`list_relationships`/`set_relations_canvas`/`get_relations_canvas`) + `builtin_components/indicator_tools.py` (`indicator_relate` + relationships on `indicator_get`) + `builtin_components/investigation_tools.py` (`issue_set_relation_graph`) + `connector_loader.py` + `api/investigation.py` + `skills/workflows/svg_relation_graph.md` (new) + `skills/workflows/xsoar_case_investigation.md` (attribution + canvas wiring). +9 tests.
- `mcp/agent/lib/api/investigation.ts` (`Relationship` type + `relations_canvas_svg` + target-type/verb helpers), `app/investigation/issues/[id]/page.tsx` (Relations tab + shared `DiagramTab` + generalized regenerate), `app/investigation/indicators/[id]/page.tsx` (Relationships section). See [#15](https://github.com/kite-production/guardian/issues/15).

### Change scenario

**Scenario 1** — code-only (agent image); additive table + column (volumes preserved); no installer change. Patch bump (v0.2.1).

---

## [v0.2.0] (unreleased) — *Indicators module + per-issue-type layouts*

A third Investigation object — **Indicators** (IoCs) — plus issue layouts tailored to each incident type. Guardian now keeps a deduped, cross-referenced record of every indicator it sees.

### What ships

- **Indicators** — a new Investigation subpage (Issues · Cases · **Indicators**). An indicator is an IoC (ip · domain · url · file_hash · email · cve · host · account) deduped by `(value, type)`; re-seeing one updates its last-seen and links the new issue rather than duplicating. The list shows type, reputation (DBotScore), source, #issues, and last-seen; the detail shows the enrichment, first/last seen, and **every issue the indicator appears in** (cross-case correlation).
- **Two feeds** — (1) Guardian records each IoC it enriches during an investigation (`source="guardian"`); (2) when it fetches an XSOAR case, the indicators the SOAR already extracted are imported (`source="xsoar"`), so XSOAR's enrichment carries into Guardian.
- **Extracted-indicators on the issue** — each issue detail gains an **Indicators** tab listing the IoCs linked to that issue, with the types that matter for the case kind highlighted.
- **Per-issue-type layouts** — the issue detail adapts to the kind: a kind-specific glyph + accent, a one-line investigative "focus" (what to look at for phishing vs malware vs lateral-movement vs access-violation), and IoC-type emphasis on the Indicators tab.
- **Agent tools** (catalog side — no secrets): `indicator_upsert` · `indicators_list` · `indicator_get`. **REST**: `/api/v1/indicators*` + Next proxies.

### Storage

Additive to `investigations.db`: new `indicators` + `indicator_issues` (M:N) tables created on boot via `CREATE TABLE IF NOT EXISTS` (no column migration; existing issues/cases untouched).

### Files

- `bundles/spark/mcp/src/usecase/investigation_store.py` (Indicator DTO + tables + upsert/list/get/per-issue) + `builtin_components/indicator_tools.py` + `connector_loader.py` + `api/investigation.py` + `skills/workflows/xsoar_case_investigation.md` (extraction wiring).
- `mcp/agent/app/api/agent/indicators/**`, `lib/api/investigation.ts`, `components/investigation/ui.tsx` (IndicatorRow + KIND_LAYOUT), `app/investigation/indicators/**`, `app/investigation/issues/[id]/page.tsx` (Indicators tab + per-type header), `components/sidebar.tsx`. +6 tests. See [#14](https://github.com/kite-production/guardian/issues/14).

### Change scenario

**Scenario 1** — code-only (agent image); additive tables (volumes preserved); no installer change. Minor bump (v0.2.0).

---

## [v0.1.10] (unreleased) — *Attack-chain diagram — richer, ATT&CK-mapped, animated*

The auto-generated attack chain is upgraded from a plain node→arrow flow to a tactic-colored, MITRE-mapped diagram.

### What ships (skill-only — `svg_attack_chain`)

- **No more clipped labels** — wider 250px node pitch gives each arrow a 70px gap; the technique id + short name sit terse above the arrow.
- **Tactic color-coding** — each stage is colored by its ATT&CK tactic (Initial Access · Execution · Lateral Movement · C2 · Impact · …), with a per-diagram legend.
- **Tactics + techniques** — every node carries a tactic pill; every arrow carries the technique id + name.
- **Attribution** — an attribution strip (threat actor / campaign, or "unattributed").
- **Subtle animation** — flowing dashed arrows + a gentle pulse on the impact node, via an inline `<style>` + CSS keyframes (declarative, so it plays even in the sandboxed `<img>` render — no script).

No code change: the renderer + `issue_set_attack_chain` already accept any valid SVG; the new template passes the sanitizer unchanged.

### Files

- `bundles/spark/mcp/skills/workflows/svg_attack_chain.md`. See [#13](https://github.com/kite-production/guardian/issues/13).

### Change scenario

**Scenario 1** — skill-only (agent image, volume-seeded on boot); no installer change; volumes preserved. Patch bump (v0.1.10).

---

## [v0.1.9] (unreleased) — *Investigation content — markdown rendering + Activity filter/sort*

The investigation text now renders as formatted markdown (the same as the chat window), and the Activity timeline is filterable + sortable.

### What ships

- **Markdown rendering** — the issue fields (Summary · Scope · Recommendations · Conclusions · Next steps), the activity event content, and the case description render through the shared `MarkdownContent` component the chat uses (react-markdown + remark-gfm + syntax highlighting). The agent already writes these fields as markdown; now they display formatted. Editing a field still shows the raw textarea.
- **Activity filter + sort** — the Activity tab gets type filter chips (all / action / finding / note …, derived from the events present), an Oldest/Newest sort toggle, and an "N of M" visible count.

### Files

- `mcp/agent/components/investigation/ui.tsx` (`EditableSection` → `MarkdownContent`) + `app/investigation/issues/[id]/page.tsx` + `app/investigation/cases/[id]/page.tsx`. See [#12](https://github.com/kite-production/guardian/issues/12).

### Change scenario

**Scenario 1** — code-only (agent image); no installer change; volumes preserved. Patch bump (v0.1.9).

---

## [v0.1.8] (unreleased) — *Attack-chain SVG diagram*

Guardian now draws a visual **attack chain** for each investigation — the causal path of the attack (entry → pivots → action → impact) — rendered on the issue's **Attack chain** tab. It generates automatically when an investigation resolves, and you can regenerate it on demand.

### What ships

- **Diagramming skill** (`svg_attack_chain`) — teaches the agent to emit a self-contained SVG of the attack chain (left-to-right nodes + labelled arrows, inline styling, own background, no scripts/external refs, XML-escaped labels), with a concrete template + palette.
- **Agent tool** `issue_set_attack_chain(issue_id, svg)` — validates the SVG (`<svg>…</svg>`, ≤256 KB), defensively strips `<script>`/`on*`, and stores it. On the catalog side of the credential guardrail (agent-callable, no secrets).
- **Automatic on resolve** — the `xsoar_case_investigation` skill now draws the chain at resolve time, so the autonomous loop produces one for every investigation.
- **Safe rendering** — the Attack-chain tab renders the SVG via an `<img>` data-URI, which is sandboxed (SVG-in-`<img>` never executes script or fetches external resources) — so agent-produced markup can't run code.
- **Regenerate** — a button on the tab redraws the diagram on demand (fires a one-shot agent pass; the tab polls until the new diagram lands).

### Files

- `bundles/spark/mcp/skills/workflows/svg_attack_chain.md` (new) + `xsoar_case_investigation.md` (resolve-step wiring).
- `bundles/spark/mcp/src/usecase/investigation_store.py` (`attack_chain_svg` column + set/get) + `builtin_components/investigation_tools.py` + `connector_loader.py` + `api/investigation.py`.
- `mcp/agent/lib/api/investigation.ts` + `app/investigation/issues/[id]/page.tsx`. +6 tests. See [#11](https://github.com/kite-production/guardian/issues/11).

### Change scenario

**Scenario 1** — code-only (agent image); the `attack_chain_svg` column is additive (migration preserves existing issues); no installer change; volumes preserved. Patch bump (v0.1.8).

---

## [v0.1.7] (unreleased) — *Investigation UI overhaul — full-width, tabbed, prettified*

The Investigation pages (Issues + Cases) now match the skills/jobs page standard, and the issue detail is split into tabs instead of one long page.

### What ships

- **Full-width, prettified layout** — all four pages (Issues list, Issue detail, Cases list, Case detail) use the `max-w-[1400px]` glass-card layout: summary stat cards, filter chips, glass rows with a per-kind glyph + status/severity/origin/XSOAR badges, and proper empty states. Shared primitives in `mcp/agent/components/investigation/ui.tsx` keep the list + detail visually consistent.
- **Tabbed issue detail** — **Overview** (Summary · Scope · Recommendations, with a derived VERDICT banner) · **Assessment** (Conclusions · Next steps) · **Activity** (the investigation timeline) · **Attack chain** (placeholder for the SVG causality diagram shipping in v0.1.8).
- **Cases-load performance fix** — `InvestigationStore.list_cases()` ran a correlated `(SELECT COUNT(*) FROM issues WHERE case_id = c.id)` *per case* (N+1 at the SQL level), which made the Cases list slower than Issues. Replaced with a single `LEFT JOIN issues … GROUP BY c.id` (one pass, identical response shape).
- **Manual analyst actions** — deferred; a disabled "Actions" control marks where they'll live in a later release.

### Files

- `mcp/agent/components/investigation/ui.tsx` (new shared primitives) + `app/investigation/{issues,issues/[id],cases,cases/[id]}/page.tsx` (rewritten).
- `bundles/spark/mcp/src/usecase/investigation_store.py` (`list_cases` LEFT JOIN). See [#10](https://github.com/kite-production/guardian/issues/10).

### Change scenario

**Scenario 1** — code-only (agent image); the `list_cases` query optimization preserves the response shape; no installer change; volumes preserved. Patch bump (v0.1.7).

---

## [v0.1.6] (unreleased) — *Investigation skill — blast-radius scoping gate*

A focused, evidence-driven increment on top of v0.1.5. A second structured evaluation of the autonomous loop's output (four investigations across lateral-movement, malware, data-exfiltration, and DNS-tunnel C2 — every proposed change adversarially verified and biased to reject churn) confirmed v0.1.5 is solid and surfaced exactly **one** recurring gap: investigations resolve the immediate finding but **defer blast-radius scoping to next-steps** instead of executing it.

### What ships

- **Blast-radius gate (Step 6)** — before an Issue can be marked `resolved`, the agent must enumerate the blast radius of every confirmed-malicious indicator and compromised principal *in-investigation*, not defer it: (1) follow every relationship enrichment already surfaced (a related hash, linked IP/domain, or co-sighting incident id) — enrich it or pull the named co-sighting and fold its hosts/accounts into scope; (2) pivot each confirmed-bad value outward via `xsoar_search_indicators` + `xsoar_list_incidents` (and the auth log via `xsoar_run_command` where `playground_id` exists) to find other affected hosts/cases; (3) state the scope as a one-line "N hosts / M cases" count or an explicit "contained to this host."
- **Matching constraint** — "Scope is part of resolution, not a next-step." A surfaced relationship left in prose is incomplete work.
- One general rule (no per-attack-type branches); complements — does not duplicate — the v0.1.5 resolution gate, which fires only on *competing root causes*.

### Files

- `bundles/spark/mcp/skills/workflows/xsoar_case_investigation.md`. See [#9](https://github.com/kite-production/guardian/issues/9).

### Change scenario

**Scenario 1** — skill-only (baked into the agent image, volume-seeded on boot); no installer change; volumes preserved. Patch bump (v0.1.6).

---

## [v0.1.5] (unreleased) — *Investigation skill hardening — IR rigor + tool-surface reconciliation*

Guardian's `xsoar_case_investigation` skill — the playbook that drives every autonomous and operator-initiated investigation — was upgraded from a structured evaluation of the autonomous loop's REAL output (two completed investigations scored against a SOC IR rubric, every proposed change adversarially verified against the connector source). The skill now teaches the full v0.2.0 tool surface, enforces complete IoC coverage, and gates "resolved" on a single supported root cause.

### What ships

- **Tool-family reconciliation** — the tool table listed only 9 of the connector's 21 tools and omitted every v0.2.0 command-engine tool the investigations actually used (`enrich_indicator`, `run_command`, `run_playbook`, the list tools, `create_incident`, `complete_task`). It now documents the full surface, grouped by phase, with the `playground_id` requirement flagged per tool.
- **Enrich step fixed** — `xsoar_enrich_indicator` (live DBotScore) is now the primary reputation tool; `xsoar_search_indicators` is for cross-case correlation. Previously the skill named only the store-search path.
- **Entity ledger + principal-first** — Step 2 now requires an explicit ledger of every IoC / account / host / email; the case isn't resolvable until every row has a result or a documented skip. Identity cases (access-violation, lateral-movement) characterize the ACCOUNT first, not the source IP.
- **Resolution gate** — don't mark an Issue `resolved` while competing root-cause hypotheses are undiscriminated; run the determinative query (e.g. recover the true client IP) FIRST rather than deferring it to next-steps.
- **Structured verdict + MITRE ATT&CK** — every Issue leads with a one-line `VERDICT:` and tags confirmed behaviors with ATT&CK technique IDs grounded in evidence.
- **Grounding rules** — quantitative claims (engine counts, scores) must trace to logged tool output; war-room citations quote the entry; blocklist recommendations check real list state via `get_list`.
- **Version-handling correction** — the skill previously said `xsoar_update_incident` *requires* the case `version`; the connector actually resolves the optimistic-lock version itself (the search-returned version is unreliable on Cortex 8). The skill now says leave `version` unset, and `xsoar_close_incident` takes `incident_ids` (array). Confirmed against `connector.py`.
- **Frontmatter parse fix** — the skill's YAML frontmatter carried a leaked shell-escape (`'\''` instead of YAML `''`) that made `yaml.safe_load` throw, so the loader silently discarded ALL frontmatter — including the `description` that auto-loads the skill when an operator asks to investigate a case. The loop masked this by binding the skill by name. Fixed; the auto-load trigger works again. Bug-family audit: no other skill carries the leak.

### How it was built

Evaluation → synthesis → adversarial verification ran as a multi-agent workflow; every proposed change was checked against the connector source before landing (two of eight needed correction). See [#8](https://github.com/kite-production/guardian/issues/8).

### Files

- `bundles/spark/mcp/skills/workflows/xsoar_case_investigation.md`.

### Change scenario

**Scenario 1** — skill-only (baked into the agent image, volume-seeded on boot via the per-release marker merge); no installer change; volumes preserved. Patch bump (v0.1.5).

---

## [v0.1.4] (unreleased) — *Agent chat resilience — retry transient Vertex socket resets*

Long agent turns — especially **scheduled investigation jobs** that run many tool calls against a real XSOAR tenant — no longer die mid-run with `chat error event: fetch failed`. The chat route already retried Vertex/Gemini **429 / quota** throttling; this release extends the same exponential-backoff retry to **transient socket resets** (`UND_ERR_SOCKET` / `ECONNRESET` / connect + body timeouts), which Vertex returns when it drops a long `generateContent` connection under load.

### What ships

- **Wider model-call retry** — the chat route's retry wrapper (renamed `withRateLimitRetry` → `withModelCallRetry`) now retries transient network failures in addition to 429s. A new `transientNetworkCode()` helper walks the `err.cause` chain (Node's fetch reports the real socket code on `cause`, not the top-level `fetch failed` message) and matches a set of retryable codes; a bare `fetch failed` / `socket hang up` / `other side closed` is treated as transient because undici only throws those for network-level errors (HTTP error statuses return a non-ok response, still handled by the 429 path).
- **Why it mattered** — the v0.1.3 autonomous investigation loop proved the Investigation module + skill work end-to-end (the agent opened a local Issue, `origin=agent`, the moment it began investigating) but every run then failed on a mid-investigation socket reset the retry predicate didn't cover. This is the fix that lets the loop *complete* an investigation. See [#7](https://github.com/kite-production/guardian/issues/7).

### Files

- `mcp/agent/app/api/chat/route.ts` — `transientNetworkCode()` + `TRANSIENT_NETWORK_CODES` + broadened `withModelCallRetry` (both Gemini-API-key and Vertex call sites).

### Change scenario

**Scenario 1** — code-only (agent image); no installer change; volumes preserved. Patch bump (v0.1.4).

---

## [v0.1.3] (unreleased) — *Investigation module — local Issues & Cases*

A new first-class **Investigation** area: Guardian (and the operator) open local **Issues** during investigations and group related ones into **Cases**. Distinct from upstream XSOAR incidents — an Issue is *Guardian's own* investigation record (what's being investigated, the activity timeline, recommendations, conclusions, summary, next steps), shown in the UI.

### What ships

- **Investigation store** (`investigations.db`) — issues + cases + per-issue activity timeline (`issue_events`). One-to-many issue→case. Catalog domain (not credentials).
- **Agent MCP tools** (catalog side of the credential guardrail — no SecretStore access): `issue_create` / `issue_update` / `issue_add_event` / `issue_get` / `issues_list` / `case_create` / `case_add_issue` / `cases_list` / `case_get`. The agent opens an Issue when it starts working a case (with `source_ref` = the XSOAR incident id), logs each step/finding, records the verdict, and groups related Issues into Cases.
- **REST API** (`/api/v1/issues|cases*`) + **Next.js proxies** (`/api/agent/issues|cases*`).
- **UI** — new sidebar **Investigation** group → **Issues** + **Cases**. Issues list (+ New Issue), rich issue detail (status/severity controls, editable Summary/Scope/Recommendations/Conclusions/Next-steps, activity timeline of what Guardian did, case assignment), cases list (+ New Case), case detail (grouped issues).
- **Skill + system prompt** — the `xsoar_case_investigation` skill + the agent's job description now drive opening + maintaining the local Issue + grouping Cases throughout every investigation.
- **Also in this release:** guardian-updater no longer crashes the `reconcile/digests` endpoint when a connector's running image was pruned (ImageNotFound → recreate). See [#6](https://github.com/kite-production/guardian/issues/6).

### Files

- `bundles/spark/mcp/src/usecase/investigation_store.py`, `src/api/investigation.py`, `src/usecase/builtin_components/investigation_tools.py` (+ `connector_loader.py`, `main.py` wiring) + tests.
- `mcp/agent/app/api/agent/{issues,cases}/**`, `lib/api/investigation.ts`, `app/investigation/{issues,cases}/**`, `components/sidebar.tsx`.
- `bundles/spark/mcp/skills/workflows/xsoar_case_investigation.md`, `mcp/agent/lib/system-prompt.ts`.
- `updater/src/main.py` (reconcile ImageNotFound fix).

### Change scenario

**Scenario 1** — code-only; `investigations.db` is created fresh on first boot (additive, no migration); no installer change; volumes preserved. Minor bump (v0.1.3).

### Forbidden going forward

- No SecretStore reads in the `issue_*` / `case_*` tools — they stay on the catalog side of the guardrail (that's why the agent may call them).
- Don't conflate a Guardian **Issue** with an upstream XSOAR **incident** — the Issue is Guardian's local record; `source_ref` links them.

---

## [v0.1.2] — 2026-06-12 — *XSOAR action toolset + default chat-model picker*

This release ships two concepts together (the default-model picker below was merged but never separately tagged, so it rides along here). The XSOAR connector grows from 13 to 21 tools, adding a command-execution engine, indicator enrichment, XSOAR Lists management, incident creation, and playbook execution. Previously Guardian could read and triage cases but could not run an XSOAR command, enrich an IoC, manage allow/block lists, open a case, or run a playbook.

### What ships

- **Command engine** (needs `playground_id`) — `xsoar_run_command` runs any XSOAR `!command` synchronously in the playground War Room (`POST /entry/execute/sync`) and returns the war-room output plus optional context keys. `xsoar_enrich_indicator` layers the `!ip`/`!url`/`!domain`/`!file`/`!cve` map onto it for DBotScore reputation. `xsoar_complete_task` runs `!taskComplete` to advance a playbook task.
- **XSOAR Lists** — `xsoar_get_list` / `xsoar_set_list` / `xsoar_append_to_list` read, overwrite, and append to XSOAR Lists (allow/block lists, lookups) via the `!getList` / `!setList` war-room commands. These need `playground_id` (the v6 `GET /lists/` REST endpoint returns HTTP 500 on Cortex 8 — verified live).
- **Incident lifecycle** — `xsoar_create_incident` (`POST /incident`) opens a case; `xsoar_run_playbook` runs `!setPlaybook` in the incident's *own* war room (an incident id is its investigation id, so no `playground_id` needed) to assign + start a playbook. The v6 `POST /inv-playbook/<pb>/<inv>` REST endpoint 303-redirects on Cortex 8 (verified live), so the war-room command path is used on both generations.
- **New `playground_id` config field** — an **optional** field on the XSOAR instance (the Playground / War Room investigation id). The 13 read/lifecycle tools and existing instances work unchanged; only the three command-engine tools require it, and they return a clean "playground_id not configured" message when it is blank. The field is surfaced in the **instance Create + Edit forms** so operators can set it (see the marketplace-overlay fix below).
- **Instance form surfaces newly-added config fields** — fixed a drift where the `/api/marketplace/connectors` catalogue hardcoded each connector's config-field list (and version), so a field added to a connector (like `playground_id`) never appeared in the UI. The catalogue now overlays the live `configSchema` + `version` from `connector.yaml` (the same overlay v0.15.5 added for `spec.tools[]`), and the Edit-Instance dialog seeds from the connector's full schema — so an existing instance's form shows fields added after it was created, empty + editable.

### Files

- `bundles/spark/connectors/xsoar/src/connector.py` — 8 new `xsoar_*` tools + the `_execute_command` / `_parse_war_room_entries` / `_get_playground_id` / `_find_list` helpers; connector version 0.1.0 → 0.2.0.
- `bundles/spark/connectors/xsoar/connector.yaml` — `playground_id` config field + 8 `spec.tools[]` entries.
- `bundles/spark/connectors/xsoar/tests/test_connector.py` — per-tool request-shape + envelope tests (v6 + v8).
- `mcp/agent/app/help/architecture/page.tsx` — `#xsoar-connector` gains an "Action toolset" subsection.
- `mcp/agent/app/help/user/page.tsx` — `#connectors` gains the command-tools + `playground_id` setup subsection.
- `mcp/agent/lib/journeys.ts` — `xsoar-run-command` journey.
- `mcp/agent/app/api/marketplace/connectors/route.ts` — overlay live `configSchema` + `version` from `connector.yaml` onto the catalogue (append config fields the hardcoded list doesn't name).
- `mcp/agent/app/connectors/page.tsx` — Edit-Instance dialog seeds from the connector's full schema so newly-added fields surface.

### Change scenario

**Scenario 1** — code-only, installer unchanged. `playground_id` is a backwards-compatible optional config field; volumes preserved; customers re-run the existing installer.

### Forbidden post-v0.1.2

- No XSIAM-side tools smuggled in under "XSOAR" (XQL / datasets / issues / assets / vendor lookups) — Guardian is XSOAR-only.
- No credential / SecretStore reads added to these tools — they stay on the catalog/connector side of the guardrail.
- No `close_investigation` tool — `close_incident` already closes the investigation.

---

## [v0.1.1] (shipped within v0.1.2) — *Default chat-model picker*

Operators can now pin a default model for all new chats. Previously every chat opened on the runtime default (`GEMINI_MODEL` env or the hardcoded `gemini-3.1-pro-preview` fallback) and operators had to run `/model <name>` in every session to override it.

### What ships

- **Default model picker** — Settings → Models → open a model card → **Set as default**. The selection is persisted in `operator_state.db` under key `default_model = {provider, model}`.
- **Chat route default resolution** — the resolution chain is now: per-chat override → operator default (`operator_state.db`) → `GEMINI_MODEL` env → hardcoded fallback. New chats automatically pick up the operator default without any slash command.
- **Dropdown chip** — the model picker chip in the chat header shows **Default — \<model\>** when an operator default is active (previously showed "auto"). Picking a different model in the dropdown overrides for that chat only; the next new chat resets to the default.

### Files

- `mcp/agent/app/(main)/models/[id]/page.tsx` — "Set as default" button on model detail page
- `mcp/agent/app/(main)/models/page.tsx` — visual indicator on the default model card
- `mcp/agent/app/api/chat/route.ts` — operator-default step inserted in `resolveModelName`
- `mcp/agent/components/chat/model-picker.tsx` — chip shows "Default — \<model\>" vs "auto"
- `mcp/agent/app/help/architecture/page.tsx` — `#model-routing` updated with the new chain
- `mcp/agent/app/help/user/page.tsx` — `#models-providers` new "Default model" subsection
- `mcp/agent/lib/journeys.ts` — `set-default-chat-model` journey added
- `CHANGELOG.md`, `mcp/agent/lib/release-notes.ts` — this entry

Scenario 1 (code-only, no installer change).

---

## [v0.1.0] (unreleased) — *Guardian initial release: an AI incident-response agent for Cortex XSOAR*

Guardian is derived from the Phantom agent platform, cut down to one job: **AI-assisted incident investigation on Cortex XSOAR.** An operator points Guardian at their XSOAR tenant; the agent then monitors the cases (incidents) opening on the SOAR, fetches each case's full record and war-room narrative, investigates and enriches it, documents its findings back onto the case, and updates or closes it — autonomously or on request.

**What was removed from the Phantom baseline:** everything that existed to *generate* or *query telemetry* rather than *investigate cases*. Gone are the synthetic log-generation backend, the red-team adversary-emulation stack, the data-source validation catalog, the log-destination subsystem, **the XSIAM and Cortex XDR telemetry connectors, the Cortex content catalog, all XQL-authoring tooling, and the bundled XQL-examples knowledge base.** None of these surfaces — services, connectors, UI pages, MCP tools, CI workflows, skills, KBs — ship in Guardian. The full `phantom → guardian` rename runs through service names, image names, env vars, tool prefixes, and the installer.

**What Guardian is:** a focused XSOAR case-investigation agent. The operator chats with (or schedules) an agent that lists and triages open cases, pulls full case detail and the war-room conversation, enriches the case's indicators against XSOAR threat intel, researches CVEs/IOCs in Palo Alto Cortex documentation and on the open web through a sandboxed Chromium sidecar, writes its findings as war-room notes, and updates case severity/owner/fields or closes the case with a reason — with IR-focused agent semantics throughout (an incident-investigation system prompt, plan mode for multi-step investigations, and quick actions for the common case-triage moves).

### What ships

- **The `guardian-agent` container** — Next.js 15 UI (port 3000, TLS proxy in front) + an embedded Python FastMCP subprocess (port 8080, bearer-token auth). The agent's chat, jobs, observability, and help surfaces all live here. The embedded-MCP test suite passes (283 tests).
- **3 connectors** (`bundles/spark/connectors/`), each running as a per-instance container on the shared connector runtime (`guardian-connector-runtime/`):
  - **xsoar** — 13 tools (`xsoar_` prefix) covering the full case lifecycle: `xsoar_list_incidents`, `xsoar_get_incident`, `xsoar_get_war_room`, `xsoar_add_entry`, `xsoar_add_note`, `xsoar_update_incident`, `xsoar_close_incident`, `xsoar_list_incident_types`, `xsoar_get_incident_fields`, `xsoar_search_indicators`, `xsoar_save_evidence`, `xsoar_search_evidence`, `xsoar_health_check`. Supports **both** XSOAR 6 (on-prem, API key in the `Authorization` header) and XSOAR 8 / Cortex cloud (API key + key id via `x-xdr-auth-id`, `/xsoar/public/v1` path prefix) — detected from whether an `api_id` is configured.
  - **cortex-docs** — Palo Alto Cortex documentation lookup (`cortex_` prefix), for grounding investigation reasoning in authoritative product docs.
  - **web** — Playwright browsing (`guardian_web_` prefix) through the browser sidecar, for CVE/IOC/threat-intel research.
- **Embedded MCP builtins** (`bundles/spark/mcp/`) — cognitive tools, skills CRUD, and self-modification tools, plus on-disk skills: `cortex_kb_search`, `cortex_kb_search_patterns`, `cortex_kb_api_reference` (Cortex-docs research) and the two XSOAR investigation skills `xsoar_case_investigation` (the load-first end-to-end case workflow) and `xsoar_case_triage`.
- **The `guardian-browser` sidecar** — headless Chromium driven over CDP, profile-gated, the only path the web connector uses to touch the internet.
- **The `guardian-updater` daemon** (port 8090) — container-lifecycle management for connector instances and image rollouts.
- **IR agent semantics** — an incident-investigation system prompt that drives the monitor → fetch → investigate → document → update/close loop, plan mode, and quick actions tuned for case triage.
- **Credential guardrail (unchanged from upstream)** — the agent has **no** MCP tool that reads, writes, mints, or rotates credentials; `providers_*`, `instances_*` (create/update/delete), and `api_keys_*` management stay REST-only.
- **Observability** — the manifest declares one runtime event family, `rt.tool.failed`, emitted for every MCP tool that raises.
- **AI-layer tooling** — the bundle validator passes 18/18 checks, and a codebase-search MCP server supports agent-assisted development on the repo itself.
- **Release plumbing** — `github.com/kite-production/guardian` with a registered self-hosted runner; a customer release ships **7 images at one version tag** (guardian-agent, guardian-updater, guardian-browser, guardian-connector-runtime, and the xsoar / cortex-docs / web connector images).

### Files

- `mcp/agent/` — Next.js UI + embedded-MCP host (the `guardian-agent` container)
- `bundles/spark/mcp/` — Python FastMCP server, builtin tools, skills, tests
- `bundles/spark/connectors/{xsoar,cortex-docs,web,_runtime}/` — the 3 connectors + shared runtime base
- `guardian-connector-runtime/` — shared connector base image
- `guardian-browser/` — Chromium CDP sidecar
- `updater/` — `guardian-updater` lifecycle daemon
- `installer/` — customer installer template
- `docker-compose.yml`, `.github/workflows/` — stack topology + build/release pipeline

First Guardian release — fresh install via the customer installer; there is no upgrade path from any Phantom version. **Live XSOAR connectivity is configured at first-run setup** (the operator supplies the XSOAR server URL, API key, and — for XSOAR 8/Cortex — the API key id).
