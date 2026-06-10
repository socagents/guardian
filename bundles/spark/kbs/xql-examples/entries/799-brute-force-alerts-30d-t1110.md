---
id: XQL-799-ff0abccc
title: Brute-force alerts (30d, T1110)
category: detection
dataset: alerts
tags:
  - filter
  - fields
  - sort
  - limit
  - alerts
  - T1110
---

# Brute-force alerts (30d, T1110)

**Dataset**: `alerts`

```sql
config timeframe = 30d
| dataset = alerts
| filter lowercase(alert_name) contains "brute" or lowercase(alert_name) contains "password spray" or lowercase(alert_name) contains "failed login" or mitre_attack_technique contains "T1110"
| fields _time, host_name, alert_name, severity, user_name
| sort desc _time
| limit 10
```

## When to use

Brute-force + password-spray detections (MITRE T1110). Common against external-facing services + privileged accounts.

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
