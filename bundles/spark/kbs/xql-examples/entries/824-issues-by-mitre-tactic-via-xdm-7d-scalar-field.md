---
id: XQL-824-3327c5ef
title: Issues by MITRE tactic via XDM (7d) — scalar field
category: investigation
dataset: issues
tags:
  - filter
  - comp
  - sort
  - limit
  - issues
  - xdm
  - mitre
---

# Issues by MITRE tactic via XDM (7d) — scalar field

**Dataset**: `issues`

```sql
config timeframe = 7d
| dataset = issues
| filter xdm.issue.mitre_tactics != null
| comp count() as cnt by xdm.issue.mitre_tactics
| sort desc cnt
| limit 10
```

## When to use

XDM-normalized MITRE tactic distribution. `xdm.issue.mitre_tactics` is a scalar string in this tenant; aggregate directly without arrayexpand.

## Variations

_(v0.7.0 hand-curated — variations not yet authored. Operator's
curation pass adds these.)_

## Source

Hand-curated for v0.7.0's 100-query KB expansion. Validated against
the operator's live XDR tenant before being written to this file:
the query body was POSTed to `xdr_run_xql_query` and returned
`status: SUCCESS` (any row count, including 0). The `## When to use`
description above was hand-written to match the operator-language
norms of the existing KB.
