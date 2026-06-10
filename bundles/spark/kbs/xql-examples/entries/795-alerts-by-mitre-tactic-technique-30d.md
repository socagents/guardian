---
id: XQL-795-b6656f7a
title: Alerts by MITRE tactic + technique (30d)
category: investigation
dataset: alerts
tags:
  - filter
  - comp
  - sort
  - limit
  - alerts
  - mitre
---

# Alerts by MITRE tactic + technique (30d)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter mitre_attack_tactic != null
| comp count() as cnt by mitre_attack_tactic, mitre_attack_technique
| sort desc cnt
| limit 10
```

## When to use

Per-alert MITRE ATT&CK mapping using the live tenant's `mitre_attack_tactic` + `mitre_attack_technique` fields. Surfaces the tactic-coverage shape — which techniques fire most.

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
