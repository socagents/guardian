---
name: cortex_kb_search
displayName: Cortex KB Search (docs-cortex.paloaltonetworks.com)
category: foundation
description: 'Answer questions about Palo Alto Networks Cortex products (XSOAR, XDR, XSIAM, AgentiX, Cortex CLOUD, Xpanse) by searching the official public documentation via the cortex-docs connector and returning evidence-backed answers with citations. Use this skill during incident investigation to resolve unknowns — how a Cortex incident/case field is defined, what a detection means, which playbook or close-reason applies, an API endpoint, a configuration or troubleshooting question. The skill enforces a discipline-driven workflow: (1) decompose multi-topic requests, (2) strip user-language and use Palo Alto vocabulary in queries, (3) use cortex-docs/suggest to find the exact title before searching, (4) cortex-docs/search with --product scope, (5) cortex-docs/fetch_topic with auto-children fallback for stub topics, (6) synthesize per concept, (7) cite sources. Two related skills hold the lookup tables: cortex_kb_search_patterns for query-shaping by intent + fallback strategies, and cortex_kb_api_reference for raw Fluid Topics API spec (load only when needed).'
icon: menu_book
source: platform
loadingMode: on-demand
locked: false
attack: []
---

# Skill: Cortex KB Search

## Category

foundation

## Purpose

Answer questions about Palo Alto Networks Cortex products by searching the official public documentation at `docs-cortex.paloaltonetworks.com` and returning accurate, sourced answers.

**This skill is the single front-door for any Cortex product question.** XSOAR, XDR, XSIAM, AgentiX, Cortex CLOUD, Xpanse — they all share one docs site, one search API, and one workflow. During a case investigation, this is how you resolve the unknowns: what a Cortex incident field means, what a detection name signals, which close reason or playbook applies. The skill enforces the discipline that makes that search actually work: title-weighted full-text search demands Palo Alto vocabulary, not user phrasing.

## Available tools

**Connector tools (cortex-docs):**

| Tool | Purpose |
|---|---|
| `cortex-docs/search` | Full-text search against the live docs API |
| `cortex-docs/suggest` | Autocomplete — finds the exact Palo Alto title for a partial term |
| `cortex-docs/fetch_topic` | Fetch full topic content (auto-descends into children when topic is a stub) |
| `cortex-docs/fetch_toc` | Get the full table of contents for a publication |
| `cortex-docs/deep_research` | Heavyweight multi-section synthesis for deliverables |

**Related skills — load only when the trigger condition is met:**

| Skill | Load when… |
|---|---|
| `cortex_kb_search_patterns` | Search returns 0 or irrelevant results; question is vague; need the response quality checklist before finalizing |
| `cortex_kb_api_reference` | Need to craft a custom raw API call; debug unexpected response shape; build advanced metadata filters beyond `--product` |

Do not load these reference skills preemptively. Load them only at the specific step where their trigger condition is met.

---

## Workflow

### Step 0 — Decompose the request

Before searching, analyze the user's message for **multiple distinct information needs**. A single message may require several independent lookups.

**Signals of a multi-topic request:**

| Signal | Example |
|---|---|
| Explicit conjunction | "install XDR agent **and** configure prevention profiles" |
| Multiple product areas | "what the XSOAR incident severity field means **and** how alert triage works" |
| Sequential procedure steps from separate domains | "set up the tenant **then** create a playbook" |
| Compare-and-contrast | "difference between the `Resolved` and `False Positive` close reasons" |
| Mixed concept types | "what ports does the agent use **and** how do I troubleshoot connectivity" |

**How to handle multi-topic requests:**

1. Break the request into individual sub-topics — one per distinct concept.
2. For **each sub-topic**: run the full **search → fetch** loop independently before moving to the next. Do not pool hits from different concepts into a single fetch pass.
3. If all concepts belong to the same product, reuse the same `product` scope.
4. Compose the final answer in clearly separated sections, one per concept.
5. Cite each source individually at the end.

**Single-topic vs multi-topic examples:**

```
# Single topic — one search is enough
"what does the XSOAR incident severity field mean?"

# Multi-topic — requires two separate searches
"how do I close an XSOAR incident and what close reasons are available?"
→ Search 1: "close incident" + product=xsoar
→ Search 2: "incident close reason" + product=xsoar

# Multi-topic across products — two searches, different product scope
"what does this XSOAR playbook do and how does XSIAM raise the alert that triggers it?"
→ Search 1: "playbook overview" + product=xsoar
→ Search 2: "alert triage workflow" + product=xsiam
```

---

### Step 1 — Build the query, then search

#### 1a. Construct the query — strip user language, use Palo Alto vocabulary

This API is **title-weighted full-text search**. Queries that match or closely resemble actual topic titles rank highest. The critical failure mode is **synonym mismatch**: the user says "deploy" but Palo Alto docs say "set up" — the wrong query surfaces release notes instead of the setup guide.

**Rule: extract 3-5 core nouns / feature names. Strip everything else.**

| Strip (adds noise) | Keep (drives ranking) |
|---|---|
| Question openers: "How do I", "What is", "List", "Build an executive comparison of", "Can I", "Explain" | Feature names: "Broker VM", "high availability", "false positive", "SSO", "RBAC" |
| Filler conjunctions: "and", "or", "while", "in order to" | Palo Alto product terms: "incident", "playbook", "War Room", "correlation rule", "BIOC" |
| User-language verbs: "deploy", "provision", "govern", "control" | Canonical doc verbs (when part of a title): "set up", "configure", "manage" |
| Platform generics: "in the platform", "for the system", "solution", "approach" | Version / scope qualifiers: "Azure", "Ubuntu", "KVM", "SAML 2.0" |

**Do NOT expand acronyms in queries.** Cortex product names (XSOAR, XSIAM, XDR) are brand identifiers — search them as-is; expanding them fragments the match.

**Examples:**

| User's message | ❌ Wrong query (full sentence) | ✅ Correct query |
|---|---|---|
| "How do I close an incident in XSOAR and pick a close reason?" | `How do I close an incident in XSOAR and pick a close reason` | `close incident` + `incident close reason` |
| "What does the severity field on an XSOAR case actually mean?" | `what does the severity field on an XSOAR case actually mean` | `incident severity field` |
| "What governance model should we use for exceptions so risk does not silently increase?" | `governance model exceptions risk silently increase` | `policy exceptions` or `exception configuration` |
| "List identity and access capabilities: SSO, RBAC, scoped access, and API key management" | `List identity and access capabilities SSO RBAC scoped access API key management` | `SSO SAML` + `RBAC user roles` + `API key management` |
| "What does this playbook task do?" | `what does this playbook task do` | `playbook task` + product=xsoar |

#### 1b. Use `cortex-docs/suggest` to find the exact Palo Alto title — especially when action verbs are involved

**Call `cortex-docs/suggest` whenever your query contains an action verb** ("deploy", "install", "configure", "enable", "migrate", "upgrade"). Palo Alto uses its own vocabulary ("set up", "manage", "achieve") that rarely matches user language. `suggest` maps your core term directly to the exact doc title:

```
# Discover the Palo Alto title before searching
cortex-docs/suggest(input_text="Broker VM Azure")
# → "Set up Broker VM on Microsoft Azure"   ← use this as your search query

cortex-docs/suggest(input_text="high availability", product="xsoar")
# → "High Availability Overview", "Multi-Tenant High Availability Overview", ...

cortex-docs/suggest(input_text="fair usage")
# → "Fair Usage policy for Cortex XSIAM", "Fair Usage policy for Cortex XDR", ...
```

Use the returned phrase **verbatim** as your next search query — it is the exact title in the index.

**Common user→Palo Alto vocabulary mappings** (when `suggest` is not used):

| User says | Palo Alto docs say |
|---|---|
| deploy, install, provision, spin up | **set up** |
| govern, control, manage, administer | **manage** |
| delete, remove | **delete** or **manage** (check with suggest) |
| turn on, activate | **configure** or **enable** |
| setup wizard, installation wizard | **set up** (with platform name) |
| case, ticket, alert-as-incident | **incident** (search: `incident management` + product=xsoar) |
| close a case, resolve a ticket | **close incident** (search: `close incident` + product=xsoar) |
| close codes, resolution reasons, disposition | **incident close reason** (search: `incident close reason` + product=xsoar) |
| war room, investigation timeline, case notes | **War Room** (search: `War Room` + product=xsoar) |
| automation, runbook, response workflow | **playbook** (search: `playbook` + product=xsoar) |
| pin proof, mark as evidence | **Evidence Board** (search: `Evidence Board` + product=xsoar) |
| IOC, IP/hash/domain reputation, threat intel | **indicators** (search: `indicators threat intelligence` + product=xsoar) |
| add field to incident, custom incident field | **custom incident fields** (search: `create incident field` + product=xsoar) |
| scheduled task, cron job, nightly job | **time triggered job** + product=xsoar |
| trigger playbook via API, REST API playbook run | **KB gap** — the XSOAR playbook trigger endpoint (`POST /entry/`, `POST /incident`) is documented at xsoar.pan.dev (a separate developer portal not indexed in this KB). Only XSOAR auth setup is available here (`Get Started with APIs` + product=xsoar). Acknowledge the gap and direct the user to xsoar.pan.dev. |
| pull audit logs via API, audit log API endpoint | **audit log API** (search: `audit log API` + product=xsoar, or `API reference audit`) |

#### 1c. Run the search with `product` scope

**Always use `product` when the topic area is identifiable** — it drastically improves precision.

**Mandatory product scope — use these by default, not only when explicitly stated:**

| Topic area | `product` value |
|---|---|
| Incidents/cases, playbooks, War Room, indicators, close reasons, IR | `xsoar` |
| Alert triage, BIOC, correlation rules, analytics | `xsiam` |
| XDR agent, prevention profiles, EDR, endpoint actions | `xdr` |
| AgentiX, agentic AI workflows, dashboards | `agentix` |
| Cloud onboarding, DSPM, CSPM, CIEM, cloud posture | `cloud` |
| Attack surface, exposure management | `xpanse` |

```
# General search — 3-5 keywords from step 1a, not the user's full sentence
cortex-docs/search(query="incident close reason")

# Scoped to a product (preferred whenever topic area is known)
cortex-docs/search(query="playbook overview", product="xsoar")

# Using exact title from suggest output
cortex-docs/search(query="Manage Incidents", product="xsoar")

# Get more results
cortex-docs/search(query="indicators threat intelligence", per_page=10)
```

The search returns hits with `map_id` and `topic_id` for each result. Take these values from the live output — do not use hardcoded IDs.

> **If search returns 0 results or all hits seem off-topic:**
> 1. FIRST — call `cortex-docs/suggest(input_text="<core term>")` (with product if known) to find the exact Palo Alto title.
> 2. THEN — Load skill `cortex_kb_search_patterns`. Use § **Fallback Strategies** to rephrase and § **Query Shaping by Intent** for terminology mappings. Retry before proceeding.

> **If the user is asking about a REST API operation** (drive a case via API, trigger via REST, retrieve data programmatically):
> - The KB titles API reference docs using **endpoint path names**, not natural-language descriptions.
> - Search for the specific API method name if known: `get_incidents`, `update_incident`, `close_incident`, `search_indicators`, etc.
> - Try: `cortex-docs/suggest(input_text="API", product="xsoar")` (or xsiam/xdr) to get the exact API reference titles.
> - Try browsing the publication TOC: `cortex-docs/fetch_toc(map_id="...")` after finding an API map.
> - Do NOT redirect users to the UI when they ask for an API endpoint — the API reference exists but may need a targeted search.

---

### Step 2 — Fetch topic content

If the search excerpt is not enough to answer the question, fetch the full topic.

**The tool automatically handles container and stub topics.** Two types of thin topics exist in this docs site:
- **Empty containers** — DITA section headers with no body text at all.
- **Stub topics** — topics with only a 1-2 sentence abstract (< 300 chars) that do not actually answer a question.

When either is detected, `cortex-docs/fetch_topic` automatically descends into direct child topics. v0.5.69+ adds **multi-level descent** — when a child is itself a stub, we descend into ITS children, up to `max_depth` (default 2).

```
# Standard fetch — stub/container fallback ON by default
cortex-docs/fetch_topic(map_id="<id>", topic_id="<id>")

# Limit content size only if you have an unusually large number of topics to fit
cortex-docs/fetch_topic(map_id="<id>", topic_id="<id>", max_chars=12000)

# Fetch more children if the container has many sub-topics
# Use max_children=5 for deployment, installation, or configuration guides
# (Broker VM setup, agent installation, cloud onboarding — these typically have 4-6 child pages)
cortex-docs/fetch_topic(map_id="<id>", topic_id="<id>", max_children=5)

# Disable fallback entirely
cortex-docs/fetch_topic(map_id="<id>", topic_id="<id>", max_children=0)

# Browse the table of contents for a publication
cortex-docs/fetch_toc(map_id="<id>")
```

**Reading the output:**
- If `is_container: true` and `children_fetched: [...]` — stub/container was detected and children were loaded.
- If all children are also stubs/empty — move on to the next search result, do not retry the same topic.

**Relevance check — before using fetched content:**
> After fetching a topic, verify the topic title and opening content match what the user asked.
> - Topic is about a **different product** than the user asked about → discard it, fetch the next search hit instead.
> - Topic is about "misconfiguration alerts" or "rule reference" when user asked for configuration steps → discard, retry.
> - Topic title matches but content is only a short overview → use `max_children=5` to load sub-topics.
>
> Do not use off-topic content to answer the question. If no relevant topic is found after retrying, acknowledge the gap and provide only what the evidence supports.

---

### Step 3 — Synthesize the answer

- Lead with a direct answer (one sentence per concept for multi-topic requests)
- Use 3-6 bullets for procedural steps
- For multi-topic answers, use a `##` heading per concept to keep sections distinct
- Quote key terms from the documentation verbatim

> **Before finalizing a complex or multi-step answer:**
> → Load skill `cortex_kb_search_patterns` § **Response Quality Checklist** to verify completeness.

---

### Step 4 — Cite the source

Always end the response with:
```
Source: docs-cortex.paloaltonetworks.com — <Topic Title> (<Publication Name>)
```
For multi-topic answers, cite each source on a separate line:
```
Sources:
- docs-cortex.paloaltonetworks.com — Deploy agent installation packages (Cortex XDR 5.x Documentation)
- docs-cortex.paloaltonetworks.com — Prevention Policy Profiles (Cortex XDR 5.x Documentation)
```
If the tool failed or returned no results, use:
```
Source: General knowledge (docs lookup failed)
```

---

## Product Scope Reference

Use `product` to scope searches to a specific product. The connector translates these keys to stable **Product metadata facet values** — not internal map IDs, which can change when documentation is republished.

| `product` key | Scopes to |
|---|---|
| `xsoar` | Cortex XSOAR |
| `xsiam` | Cortex XSIAM |
| `xdr` | Cortex XDR, Cortex XDR Agent |
| `agentix` | Cortex AgentiX |
| `cloud`, `dspm`, `cspm`, `ciem` | Cortex CLOUD, Cortex Cloud Posture Management |
| `xpanse` | Cortex XPANSE |

> `map_id` and `topic_id` values always come from live search output — never hardcode them. If a fetch returns 404, re-run the search.

---

## Constraints

- This skill uses the **public** Fluid Topics API — no authentication required. cortex-docs connector instances have no secret slots; only `baseUrl` config (defaults to the public endpoint).
- Do not invent documentation that was not returned by the tools.
- If results are weak or ambiguous, state uncertainty and still provide the best evidence-backed answer without asking the user to fix input terms.
- Fetch full topic content without artificial truncation; the default `max_chars` is intentionally large to give the model maximum evidence.
- For multi-topic requests, run all searches before synthesizing — do not answer with partial information.
- Container topics with empty children are a dead end; move to the next search result rather than retrying the same topic.

## Cross-references

- **Source skill**: ported from operator's personal workassistant `cortex-assistant/cortex-docs-search/SKILL.md` (Mar 2026 authoring; v0.5.69 port to Guardian).
- **Related Guardian skills**: `xsoar_case_investigation` (the load-first case-investigation workflow that uses this skill in its research step); `xsoar_case_triage` (case field/severity/status/close-reason reference); `cortex_kb_search_patterns` (lazy-loaded query shaping + fallback strategies); `cortex_kb_api_reference` (lazy-loaded raw Fluid Topics API spec for advanced filter authoring).
- **Connector**: `cortex-docs` — wraps the Fluid Topics public API. See `bundles/spark/connectors/cortex-docs/`.
