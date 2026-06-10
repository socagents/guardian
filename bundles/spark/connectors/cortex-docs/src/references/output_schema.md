# Output Schema — Cortex Deep Search Research Brief

## JSON Output Format

The `research_planner.py` script outputs a JSON research brief with this structure:

```json
{
  "request": "The original user request",
  "deliverable_type": "presentation | report | whitepaper | brief | comparison",
  "audience": "Target audience description",
  "sections": [
    {
      "title": "Section Title",
      "description": "What this section covers",
      "priority": "high | medium | low",
      "queries_used": ["query1", "query2"],
      "evidence": [
        {
          "topic_title": "Documentation Topic Title",
          "map_title": "Publication Name",
          "map_id": "publication-map-id",
          "topic_id": "topic-content-id",
          "reader_url": "https://docs-cortex.paloaltonetworks.com/...",
          "content": "Full markdown content of the topic",
          "content_chars": 12500,
          "is_container": false,
          "children_fetched": []
        }
      ],
      "coverage": "strong | adequate | weak | none",
      "hit_count": 15,
      "fetched_count": 4
    }
  ],
  "citations": [
    "docs-cortex.paloaltonetworks.com — Topic Title (Publication Name)"
  ],
  "stats": {
    "sections_planned": 8,
    "sections_with_evidence": 7,
    "total_queries": 24,
    "total_search_hits": 120,
    "topics_fetched": 28,
    "total_content_chars": 350000,
    "gap_check_enabled": true,
    "gap_check_retries": 3,
    "execution_time_seconds": 45.2
  }
}
```

## Field Definitions

### Top Level

| Field | Type | Description |
|-------|------|-------------|
| `request` | string | Original user request verbatim |
| `deliverable_type` | string | Detected document type |
| `audience` | string | Target audience extracted from request |
| `sections` | array | Ordered list of research sections |
| `citations` | array | Deduplicated citation strings |
| `stats` | object | Execution statistics |

### Section Object

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Section heading (3-6 words) |
| `description` | string | What information this section needs |
| `priority` | string | high / medium / low |
| `queries_used` | array | All search queries executed for this section |
| `evidence` | array | Fetched topic content (ordered by relevance) |
| `coverage` | string | Coverage assessment |
| `hit_count` | int | Total search hits before filtering |
| `fetched_count` | int | Topics successfully fetched |

### Coverage Levels

| Level | Criteria |
|-------|----------|
| `strong` | 3+ evidence pieces with substantial content |
| `adequate` | 2 evidence pieces |
| `weak` | 1 evidence piece |
| `none` | 0 evidence pieces |

### Evidence Object

| Field | Type | Description |
|-------|------|-------------|
| `topic_title` | string | Title from Fluid Topics |
| `map_title` | string | Publication name |
| `map_id` | string | Publication map ID |
| `topic_id` | string | Topic content ID |
| `reader_url` | string | Full URL to docs reader |
| `content` | string | Full markdown content (up to max_chars) |
| `content_chars` | int | Character count of content |
| `is_container` | bool | Whether auto-children were fetched |
| `children_fetched` | array | Child topic titles if container |

## Text Output Format

When `--json` is NOT used, the script outputs human-readable text:

```
=== Deep Search Research Brief ===
Request: Create a presentation for MSSP partners on XDR IR
Type: presentation | Audience: MSSP partners
Sections: 8 planned, 7 with evidence | Topics fetched: 28

--- Section 1: XDR Incident Response Overview (HIGH) ---
Coverage: strong (4 topics)
Queries: "XDR incident response", "IR workflow cortex"

  [1] Incident Response Overview (Cortex XDR 5.x Documentation)
      https://docs-cortex.paloaltonetworks.com/...
      12,500 chars

  [2] Investigate Alerts (Cortex XDR 5.x Documentation)
      https://docs-cortex.paloaltonetworks.com/...
      8,200 chars

--- Section 2: Live Terminal & Forensics (HIGH) ---
...

=== Citations ===
- docs-cortex.paloaltonetworks.com — Incident Response Overview (Cortex XDR 5.x Documentation)
- docs-cortex.paloaltonetworks.com — Investigate Alerts (Cortex XDR 5.x Documentation)
...

=== Stats ===
Sections: 8 planned, 7 covered
Queries: 24 total, 120 hits
Topics: 28 fetched, 350K chars
Gap check: enabled, 3 retries
Time: 45.2s
```
