---
id: XQL-841-b1a37669
title: Living-off-the-land binary with network egress (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - iploc
  - fields
  - sort
  - limit
  - xdr_data
  - network
  - lolbin
  - geo
---

# Living-off-the-land binary with network egress (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and actor_process_image_name != null
| filter lowercase(actor_process_image_name) in ("certutil.exe", "bitsadmin.exe", "curl.exe", "wget.exe")
| filter action_remote_ip != null and not incidr(action_remote_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16")
| iploc action_remote_ip loc_country
| fields _time, agent_hostname, actor_process_image_name, action_remote_ip, loc_country, action_total_upload
| sort desc _time
| limit 10
```

## When to use

LOLBin network egress detection enriched with destination geo. Combines `filter` IN-clause + `incidr` exclusion + `iploc` enrichment — high-fidelity hunting query for exfil-via-LOLBin.

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
