---
id: XQL-759-7e45f632
title: Processes signed with non-Microsoft cert in System32 (24h, T1036.005)
category: detection
dataset: xdr_data
tags:
  - filter
  - fields
  - sort
  - limit
  - xdr_data
  - process
  - T1036.005
---

# Processes signed with non-Microsoft cert in System32 (24h, T1036.005)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(action_process_image_path) contains "system32\\"
| filter action_process_signature_vendor != null and lowercase(action_process_signature_vendor) != "microsoft corporation"
| fields _time, agent_hostname, action_process_image_path, action_process_signature_vendor, action_process_signature_status
| sort desc _time
| limit 10
```

## When to use

Binaries running from System32 signed by a non-Microsoft vendor — MITRE T1036.005 (Match Legitimate Name or Location). High-fidelity masquerading indicator.

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
