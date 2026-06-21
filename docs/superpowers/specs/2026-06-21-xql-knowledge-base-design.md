# XQL Knowledge Base + Authoring Skill — Design

**Status:** approved (design) — 2026-06-21
**Goal:** Onboard the Phantom "XQL query knowledge base" capability into Guardian, in full, and extend it toward Guardian's incident-investigation mission.

## Background

Phantom (the attack-simulation sibling of Guardian) shipped a capability for authoring **Cortex XSIAM Query Language (XQL)** queries: a curated example-query knowledge base, an authoring skill that grounds queries in both org examples and live Cortex docs, and an enrichment/RAG layer. When the XSIAM connector was ported to Guardian (v0.2.27), the XQL pieces were deliberately dropped (`connector.yaml` header: ported "minus … the removed xql-examples KB RAG tools"). This design re-adds them, adapted to Guardian's architecture, and adds IR/threat-hunting content relevant to Guardian.

Guardian **already has** the dependencies the capability needs:
- `cortex-docs` connector v0.3.2 with `xql_lookup` (live Cortex syntax docs) — same tool name Phantom's skill expects.
- `knowledge_search` built-in (`builtin_components/cognitive_tools.py`) over the SqliteKnowledgeBase.
- `xsiam` connector with `get_datasets` + `run_xql_query`.

What's missing — and what this delivers — is the **`xql-examples` KB**, an **`xql_examples_search` enrichment built-in**, and the **`cortex_xql_query_authoring` skill**.

## Architecture

Everything lands in the **guardian-agent / MCP image** (KB data, a built-in tool, a skill, UI/doc text). No connector image changes → no connector rebuild and no dev-cycle gap. The XQL RAG+enrichment is **agent-side** because Guardian connectors run as separate containers with no access to the agent's knowledge base (and connector code may not import `usecase.*`); the KB exists only in the agent/MCP container, which is where `knowledge_search` and the new built-in run.

### Component A — `xql-examples` bundled KB  *(data only)*

Files:
- `bundles/spark/kbs/xql-examples/schema.json` — JSON Schema. Required `[id, title, category]`; `category` enum `[alert-mapping, detection, investigation, general, threat-hunting]` (adds `threat-hunting`); optional `dataset`, `tags`, `ecosystem`; `additionalProperties: true`. Adapted from Phantom's schema + Guardian's mitre schema conventions.
- `bundles/spark/kbs/xql-examples/entries/*.md` — one entry per query. Format (Phantom-compatible, Guardian-loadable):
  ```markdown
  ---
  id: XQL-047-6cecd981
  title: <analyst-intent name>
  category: investigation
  dataset: incidents
  ecosystem: xsiam
  tags: [filter, comp, alter]
  # optional pre-baked: embedding (base64 LE float32), embedding_model
  ---
  # <title>
  **Dataset**: `incidents`
  ```sql
  <XQL query>
  ```
  ```

Registration: add to `bundles/spark/manifest.yaml → knowledge.bundled[]`:
```yaml
- name: "xql-examples"
  path: "./kbs/xql-examples/"
  schema: "./kbs/xql-examples/schema.json"
```
Embeddings are **pre-baked** with `bundles/spark/kbs/_tools/kb_embed.py` (matches mitre-* KBs; zero boot-time Vertex calls). `ecosystem: xsiam` is set so passive-injection exclusion can be controlled via `manifest.context.passiveExcludeEcosystems`.

**Content policy (curate + augment, net larger):**
- Port the 161 Phantom entries. **Sanitize tags** to the canonical XQL stage set (`filter, alter, comp, sort, dedup, bin, fields, join, arrayexpand, call, config, view, ...`); strip the junk tags (user-agent strings, etc.) the mapping flagged.
- **Drop only pure-noise near-duplicates** — the environment-specific "Troy" demo dashboard-widget queries that are near-identical and teach nothing reusable. Keep one representative per distinct pattern; keep all `alert-mapping` (per-vendor alert parsing), all `general` (generic XQL patterns), and every instructive `investigation` entry.
- **Add an ATT&CK-aligned IR / threat-hunting set** (new entries, `threat-hunting`/`investigation`): brute-force / failed-logon spikes, new local-admin / persistence, suspicious / encoded PowerShell, C2 beaconing, DNS & data exfiltration, lateral movement (RDP/SMB), impossible travel, rare-process / LOLBins, scheduled-task creation, etc. Each is a real XQL query over common datasets (`xdr_data`, `endpoint_raw`, `network_story`, `incidents`, `panw_ngfw_*`) with the relevant ATT&CK technique in the body. Target ≥ ~40 new entries so the net KB is meaningfully larger and IR-weighted.

### Component B — Enrichment + RAG built-in  *(runtime)*

Files:
- `bundles/spark/mcp/src/usecase/builtin_components/_xql_enrichment.py` — ported verbatim from Phantom (pure stdlib: regex stage/dataset extraction, `xql_doc.md` snippet lookup, `dataset_fields.md` field-list lookup, module-level caches).
- `bundles/spark/mcp/resources/xql_doc.md` — XQL language reference (~8.6k lines, sourced from Cortex public docs).
- `bundles/spark/mcp/resources/dataset_fields.md` — dataset → fields map (markdown: `## dataset_name` headers, `- field` bullets).
- `bundles/spark/mcp/src/usecase/builtin_components/xql_tools.py` — new built-in defining `xql_examples_search(intent: str, top_k: int = 5)`:
  1. `knowledge_base().search(intent, kb_name="xql-examples", limit=top_k)`
  2. extract stages + datasets from each match (`_xql_enrichment`)
  3. `collect_stage_docs(resources_dir, stages)` + `collect_dataset_fields(resources_dir, datasets)`
  4. return Phantom's exact shape: `{status, intent, matches:[{id,title,query,dataset,category,score}], stage_docs:[{stage,snippet}], dataset_fields:[{dataset,fields}]}`.

Registration: wire `xql_examples_search` into the built-in tool registry the same way `knowledge_search` is registered (`cognitive_tools` registration path / `connector_loader.iter_registrations`), and add `xql_examples_search` to `manifest.yaml → tools.allow[]`. It is read-only (no approval gate).

Resource resolution uses Guardian's resources dir (not Phantom's `parents[3]` hardcode) — resolved via the runtime's resource path helper, with `/app/resources` as the container fallback.

### Component C — `cortex_xql_query_authoring` skill

File: `bundles/spark/mcp/skills/foundation/cortex_xql_query_authoring.md` (foundation, `loadingMode: on-demand`). Ported from Phantom with these adaptations:
- KB retrieval step calls **`xql_examples_search`** (preferred, enriched) or `knowledge_search(kb_name="xql-examples")`.
- Syntax step uses the existing **`cortex-docs/xql_lookup`** (+ `search`, `suggest`, `fetch_topic`, `fetch_toc`, `deep_research`) — names already match Guardian.
- Dataset discovery / failure-handling references Guardian's real xsiam tools: **`xsiam_get_datasets`**, **`xsiam_run_xql_query`**. Remove Phantom-only refs (`xsiam_get_xql_doc`, `phantom_*`).
- **IR re-framing:** add a section on pivoting from an incident under investigation (its indicators/host/user/time-window) to XQL hunts that scope blast radius across XSIAM datasets — tying XQL authoring to Guardian's investigation loop, and optionally executing via `xsiam_run_xql_query`.

UI: add a `SkillDef` entry to the `SKILLS[]` array in `mcp/agent/app/skills/page.tsx` (first-paint fallback; live `/api/skills` fetch is source of truth).

### Component D — Docs / UI surfacing
- `/knowledge` auto-discovers the KB via `GET /api/v1/kbs` (no code change).
- `/skills` shows the skill (live fetch + the static array entry).
- Help `architecture` page: document the new KB, the `xql_examples_search` built-in, and the data flow (per the inter-service-wiring rule). Help `user` page: the new XQL-authoring capability (tag with introducing version).
- `CHANGELOG.md` + `mcp/agent/lib/release-notes.ts`: operator-visible entry.

## Data flow

1. Operator asks for an XQL query (or the agent is mid-investigation and needs telemetry).
2. Agent loads `cortex_xql_query_authoring` (via `skills_read`).
3. `xql_examples_search(intent)` → idiomatic example queries + stage-syntax snippets + dataset field lists.
4. `cortex-docs/xql_lookup(term, kind, product)` → authoritative live syntax per stage/function.
5. Agent authors the query, citing org examples (pattern) + Cortex docs (syntax).
6. Optional: `xsiam_run_xql_query` executes it against the live tenant.

## Out of scope / explicitly skipped
- **`bootstrap_dataset_fields` skill** — Phantom attack-sim utility that generates synthetic events via `phantom_get_technology_stack` + xlog log injection. Guardian removed xlog and is an IR (not simulation) agent. Its useful by-product, `dataset_fields.md`, is kept as a reference for query authoring.
- **`find_xql_examples_rag` as an xsiam connector tool** — replaced by the agent-side `xql_examples_search` built-in (container-model constraint).
- Net-new XSIAM execution tooling beyond the existing `run_xql_query`.

## Error handling
- KB entries missing a required frontmatter field are silently skipped by `kb_loader` (v0.6.53). Mitigation: validate every entry against `schema.json` in tests before deploy.
- `xql_examples_search` returns `{status:"error", message}` (never raises) when the KB is unavailable/uninitialized or `intent` is empty — mirrors Phantom.
- Enrichment degrades gracefully: missing `xql_doc.md`/`dataset_fields.md` → empty `stage_docs`/`dataset_fields`, not an error.
- The skill documents the cortex-docs-unreachable and xsiam-not-configured fallbacks (proceed KB-only; don't invent syntax).

## Testing
- **Unit (pytest):** `_xql_enrichment` (stage/dataset extraction, snippet + field lookup, caching); `xql_examples_search` with a mocked KB (shape, enrichment, empty-intent + KB-down paths); schema validation over all `entries/*.md`.
- **Boot:** KB loads with expected entry count; pre-baked embeddings consumed (no Vertex calls).
- **Live smoke (XSIAM instance, in-container MCP):** `xql_examples_search` returns enriched matches; the skill drives an end-to-end authoring run; `cortex-docs/xql_lookup` resolves a stage; (optional) `xsiam_run_xql_query` executes an authored query.

## Deploy
Agent-image-only → rebuilds on every dev push (no connector rebuild). Ship as a normal release once smoke passes.
