---
id: XQL-726-3edd6341
title: Credential-dumping alerts (Mimikatz, LSASS) (30d)
category: detection
dataset: alerts
tags:
  - filter
  - fields
  - sort
  - limit
  - alerts
  - T1003
---

# Credential-dumping alerts (Mimikatz, LSASS) (30d)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter lowercase(alert_name) contains "mimikatz" or lowercase(alert_name) contains "lsass" or lowercase(description) contains "mimikatz" or lowercase(description) contains "credential"
| fields _time, host_name, severity, alert_name, description
| sort desc _time
| limit 10
```

## When to use

Credential-extraction-related alerts. MITRE T1003 family — Mimikatz, LSASS memory access, credential dumping. Returns hits across the alert_name + description for broad coverage.

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
