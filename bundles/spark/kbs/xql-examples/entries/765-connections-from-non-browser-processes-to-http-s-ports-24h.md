---
id: XQL-765-6c1e36e4
title: Connections from non-browser processes to HTTP/S ports (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - network
---

# Connections from non-browser processes to HTTP/S ports (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_remote_port in (80, 443, 8080)
| filter lowercase(actor_process_image_name) not in ("chrome.exe", "firefox.exe", "msedge.exe", "iexplore.exe", "safari.exe", "opera.exe", "brave.exe", "svchost.exe", "system")
| comp count() as cnt by actor_process_image_name
| sort desc cnt
| limit 10
```

## When to use

Non-browser processes making web requests. Often legitimate (update agents, telemetry) but a useful triage starting-point for finding rogue clients that shouldn't be talking to the internet.

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
