---
name: cortex_kb_api_reference
displayName: Cortex KB Search — Raw Fluid Topics API Reference
category: foundation
description: 'Lazy-loaded raw-API reference for the docs-cortex.paloaltonetworks.com Fluid Topics platform. Use only when crafting a custom API call beyond what the cortex-docs connector tools expose (e.g. advanced metadata filtering by Version + License + Solution facet combinations, raw clustered-search request body construction, parsing the inverse-search facets response shape). The cortex-docs connector wraps these endpoints with cortex_search / cortex_suggest / cortex_xql_lookup / cortex_fetch_topic / cortex_fetch_toc / cortex_deep_research — load this skill only when the connector tools are insufficient for the operator question.'
icon: api
source: platform
loadingMode: on-demand
locked: false
attack: []
---

# Skill: Cortex KB Search — Raw API Reference

> **Load this skill only when one of these conditions is true:**
> - You need to craft a custom API call not covered by the cortex-docs connector tools
> - You need to understand the full request/response schema for a specific endpoint
> - You need to build advanced filters (by Version, Category, License, Solution facets) beyond `product`
> - You are debugging an unexpected API response (4xx, 5xx, empty results)
>
> You do NOT need this skill to use the cortex-docs connector — its tools (`search`, `suggest`, `fetch_topic`, `fetch_toc`, `xql_lookup`, `deep_research`) work with sensible defaults and cover ~95% of operator questions.

---

## Quick reference: endpoint → connector tool mapping

| Connector tool | Wraps endpoint | Use when |
|---|---|---|
| `cortex-docs/search` | `POST /api/khub/clustered-search` | Standard full-text + product-scoped search |
| `cortex-docs/suggest` | `POST /api/khub/suggest` | Autocomplete; find the exact Palo Alto title |
| `cortex-docs/xql_lookup` | `search + rank + fetch_topic_with_fallback` | Focused XQL stage/function lookup |
| `cortex-docs/fetch_topic` | `GET /api/khub/maps/{mapId}/topics/{topicId}/content` (with auto-children fallback) | Get full topic content |
| `cortex-docs/fetch_toc` | `GET /api/khub/maps/{mapId}/pages` | Browse the full TOC of a publication |
| `cortex-docs/deep_research` | plan → search → fetch → gap-check → synthesize | Multi-section deliverables (whitepapers, briefings) |

If your need fits one of these tools, use the tool. This skill is for the 5% where you don't.

---

## API context

Base URL: `https://docs-cortex.paloaltonetworks.com`
Platform: **Fluid Topics** knowledge hub (public, no authentication required)
Discovered: February 2026 from live HAR capture

---

## Required Headers

Include these on every request to avoid 4xx/blocked responses:

```
accept: */*
content-type: application/json        (POST only)
user-agent: cortex-docs-skill/1.0
ft-calling-app: ft/turnkey-portal
```

---

## Endpoints

### 1. Clustered Search

**`POST /api/khub/clustered-search`**

Full-text search returning ranked results grouped by cluster (publication).

#### Request Body

```json
{
  "query": "filter stage",
  "clusterSortCriterions": [],
  "metadataFilters": [],
  "facets": [
    {"id": "Product"},
    {"id": "Category"},
    {"id": "License"},
    {"id": "Version"},
    {"id": "Solution"}
  ],
  "sort": [],
  "sortId": null,
  "paging": {"page": 1, "perPage": 10},
  "keywordMatch": null,
  "contentLocale": "en-US",
  "otherQueryParams": {},
  "virtualField": "EVERYWHERE",
  "scope": "DEFAULT"
}
```

**Key fields:**

| Field | Type | Notes |
|---|---|---|
| `query` | string | Free-text search. Empty string returns all. |
| `paging.perPage` | int | 1-20. Anything above 20 is ignored. |
| `paging.page` | int | 1-based pagination. |
| `scope` | string | `"DEFAULT"` (books+topics), `"ALL_TOPICS"` (topics only), `"DOCUMENTS"` (full docs). |
| `virtualField` | string | `"EVERYWHERE"` searches all content fields. |
| `contentLocale` | string | `"en-US"` is the only locale with full content (42,719 topics). |
| `metadataFilters` | array | Filter by publication, product, version, etc. See below. |
| `facets` | array | Which facet counts to include in response. Can be `[]` to skip. |

#### Metadata Filters

Scope results to a specific publication:
```json
{
  "metadataFilters": [
    {
      "key": "ft:publicationId",
      "valueFilter": {
        "negative": false,
        "values": ["2iKvnhFnGXeKYHSA2AFcVw"]
      }
    }
  ]
}
```

Scope to a cluster (set of publications):
```json
{
  "metadataFilters": [
    {
      "key": "ft:clusterId",
      "valueFilter": {
        "negative": false,
        "values": ["UUID-31d9be61-b2f0-809d-635c-b3d1a8b82d07"]
      }
    }
  ]
}
```

Multiple publications (OR logic):
```json
{
  "metadataFilters": [
    {
      "key": "ft:publicationId",
      "valueFilter": {
        "negative": false,
        "values": ["KkeZwTYbDACMoWxJk0COqg", "5CAbsl8idaK8R43ZLhoTOw"]
      }
    }
  ]
}
```

#### Sort Options

By relevance (default):
```json
{"sort": [{"key": "ft:relevance", "order": "DESC"}]}
```

By last updated:
```json
{"sort": [{"key": "ft:lastEdition", "order": "DESC"}]}
```

#### Response Shape

```json
{
  "facets": [...],
  "results": [
    {
      "entries": [
        {
          "type": "TOPIC",
          "missingTerms": [],
          "topic": {
            "id": "IykutIp5DU_1VHx_mvyQFA",
            "topicId": "IykutIp5DU_1VHx_mvyQFA",
            "title": "Stages",
            "mapId": "2iKvnhFnGXeKYHSA2AFcVw",
            "mapTitle": "Cortex AgentiX Documentation",
            "readerUrl": "/r/Cortex-AgentiX/Cortex-AgentiX-Documentation/Stages",
            "htmlExcerpt": "<p>A <b>stage</b> is a building block...</p>",
            "score": 0.95
          }
        },
        {
          "type": "MAP",
          "map": {
            "mapId": "2iKvnhFnGXeKYHSA2AFcVw",
            "title": "Cortex AgentiX Documentation",
            "readerUrl": "/r/Cortex-AgentiX/Cortex-AgentiX-Documentation"
          }
        }
      ]
    }
  ]
}
```

**Result entry types:**
- `"TOPIC"` — individual doc page; use `topic.id` + `topic.mapId` to fetch content
- `"MAP"` — whole publication; use `map.mapId` to browse TOC

---

### 2. Suggest (Autocomplete)

**`POST /api/khub/suggest`**

Returns typeahead suggestions for a partial search string.

```json
{
  "contentLocale": "en-US",
  "input": "filter st",
  "metadataFilters": [],
  "sort": []
}
```

Scoped to a publication:
```json
{
  "input": "alter",
  "metadataFilters": [
    {
      "key": "ft:publicationId",
      "valueFilter": {"negative": false, "values": ["2iKvnhFnGXeKYHSA2AFcVw"]}
    }
  ],
  "sort": [],
  "contentLocale": "en-US",
  "scope": "ALL_TOPICS"
}
```

Response:
```json
{
  "suggestions": [
    {"type": "TOPIC", "value": "filter stage"},
    {"type": "TOPIC", "value": "filter command"}
  ]
}
```

> Returns `{"suggestions": []}` for obscure or very specific terms.

---

### 3. Publication (Map) Metadata

**`GET /api/khub/maps/{mapId}`**

Returns metadata for a publication (book):
```json
{
  "title": "Cortex AgentiX Documentation",
  "lang": "en-US",
  "id": "2iKvnhFnGXeKYHSA2AFcVw",
  "lastEdition": "2026-02-24",
  "clusterId": "UUID-31d9be61-b2f0-809d-635c-b3d1a8b82d07",
  "editorialType": "BOOK",
  "prettyUrl": "/go/Cortex-AgentiX/Cortex-AgentiX-Documentation",
  "readerUrl": "/r/Cortex-AgentiX/Cortex-AgentiX-Documentation"
}
```

---

### 4. Table of Contents

**`GET /api/khub/maps/{mapId}/pages`**

Returns the full nested TOC for a publication:

```json
{
  "paginatedToc": [
    {
      "pageToc": [
        {
          "tocId": "w5PYxh2oKLDMfhpyQVeTtA",
          "contentId": "Yqz_cGxQkF9m8qIWIoS0tA",
          "title": "Learn about Cortex AgentiX",
          "prettyUrl": "/r/Cortex-AgentiX/Cortex-AgentiX-Documentation/Learn-about-Cortex-AgentiX",
          "hasRating": true,
          "children": [
            {
              "tocId": "2XTyy6gPIOWOEGn7F_Mphg",
              "contentId": "iT_cKZXfP8ceo_dZ0F6yvA",
              "title": "Get Started with Cortex AgentiX",
              "children": []
            }
          ]
        }
      ]
    }
  ]
}
```

**Notes:**
- `contentId` is the `topic_id` to use with the topic endpoints.
- `tocId` is an internal tree node ID (not for content fetching).
- Use `children` array to traverse the tree recursively.

---

### 5. Topic Metadata

**`GET /api/khub/maps/{mapId}/topics/{topicId}`**

```json
{
  "title": "Stages",
  "id": "IykutIp5DU_1VHx_mvyQFA",
  "contentApiEndpoint": "/api/khub/maps/2iKvnhFnGXeKYHSA2AFcVw/topics/IykutIp5DU_1VHx_mvyQFA/content",
  "metadata": [
    {"key": "Product", "values": ["Cortex AgentiX"]},
    {"key": "Version", "values": ["All"]},
    {"key": "Category", "values": ["Reference"]}
  ]
}
```

---

### 6. Topic Content (HTML)

**`GET /api/khub/maps/{mapId}/topics/{topicId}/content?target=DESIGNED_READER`**

Returns rendered HTML for the full topic body.

- Response is a `<div>` with `class="content-locale-en-US"`.
- Contains data attributes: `data-permalink`, `data-resource-title`, `data-topic-level`.
- Code samples are in `<pre>` or `<code>` blocks.
- The connector's `fetch_topic.py` already runs HTML→plain-text conversion (see `html_to_text()`).

> The `data-permalink` attribute can be used to construct the canonical documentation URL:
> `https://docs-cortex.paloaltonetworks.com/go/{data-permalink}`

---

### 7. Search Configuration

**`GET /api/configuration/search`**

Returns available sort options (`relevance`, `last_update`).

### 8. Reader Configuration

**`GET /api/configuration/reader`**

Returns reader UI parameters (rarely needed for programmatic access).

### 9. Locales

**`GET /api/khub/locales`**

Returns supported content locales. **Use `contentLocale: "en-US"` in all search requests** — it's the only locale with full content (42,719 topics; other locales have <100).

---

## Publication Map IDs

Map IDs (`ft:publicationId`) and topic IDs are **ephemeral** — they are assigned by the Fluid Topics platform and can change when Palo Alto republishes documentation. **Do not hardcode them.**

Always obtain `map_id` and `topic_id` values dynamically from live search results:

```
# Get map_id and topic_id from the search
cortex-docs/search(query="<your query>", product="xdr")
# Then use the map_id and topic_id from the results:
cortex-docs/fetch_topic(map_id="<map_id>", topic_id="<topic_id>")
```

**Preferred alternative to `ft:publicationId` filtering:** Use the `Product` metadata facet instead. Product names (e.g. `Cortex XDR`, `Cortex XSIAM`) are stable brand identifiers that survive publication restructuring — this is what the connector's `product` arg already does internally.

---

## Error Handling

| Status | Meaning | Action |
|---|---|---|
| `200` | OK | Parse response normally |
| `304` | Not Modified (cached) | Safe to use cached response |
| `302` | Redirect | Follow redirect automatically |
| `404` | Map/topic ID no longer valid | Re-run search to get fresh IDs |
| `429` | Rate limited | Retry after a short delay |
| `5xx` | Server error | Retry once; if persistent, report |

## Cross-references

- Parent skill: `cortex_kb_search` (loads this skill only when needed)
- Sibling skill: `cortex_kb_search_patterns` (query-shaping tables, fallback strategies, response quality checklist)
- Source: ported from operator's personal workassistant `cortex-assistant/cortex-docs-search/references/api_reference.md` (Feb 2026 HAR-derived; v0.5.69 port).
