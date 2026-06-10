---
id: XQL-704-1ce9fa11
title: Suspicious LOLBin parents spawning unusual children (24h)
category: detection
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - limit
  - xdr_data
  - process
  - lolbin
  - T1218
---

# Suspicious LOLBin parents spawning unusual children (24h)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.PROCESS and event_sub_type = ENUM.PROCESS_START
| filter lowercase(actor_process_image_name) in ("rundll32.exe", "regsvr32.exe", "mshta.exe", "wmic.exe", "certutil.exe", "bitsadmin.exe")
| comp count() as cnt by actor_process_image_name, action_process_image_name
| sort asc cnt
| limit 10
```

## When to use

Classic Living-Off-The-Land Binaries (LOLBins) — when these utilities spawn unusual children, it often indicates attacker abuse. Sort by ascending count to surface rare combinations first.

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
