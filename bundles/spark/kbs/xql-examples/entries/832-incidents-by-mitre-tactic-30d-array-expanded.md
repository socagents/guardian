---
id: XQL-832-fecfe92f
title: Incidents by MITRE tactic (30d) — array-expanded
category: investigation
dataset: incidents
tags:
  - filter
  - arrayexpand
  - comp
  - sort
  - limit
  - incidents
  - mitre
---

# Incidents by MITRE tactic (30d) — array-expanded

**Dataset**: `incidents`

```sql
config timeframe = 30d
| dataset = incidents
| filter mitre_tactics_id_and_name != null
| arrayexpand mitre_tactics_id_and_name
| comp count() as cnt by mitre_tactics_id_and_name
| sort desc cnt
| limit 10
```

## When to use

MITRE tactic distribution at the incident level.  is an array — arrayexpand to enable aggregation.

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
