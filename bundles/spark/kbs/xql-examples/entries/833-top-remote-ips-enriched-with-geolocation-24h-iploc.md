---
id: XQL-833-3a926546
title: Top remote IPs enriched with geolocation (24h, iploc)
category: investigation
dataset: xdr_data
tags:
  - filter
  - comp
  - sort
  - iploc
  - fields
  - limit
  - xdr_data
  - network
  - geo
---

# Top remote IPs enriched with geolocation (24h, iploc)

**Dataset**: `xdr_data`

```sql
config timeframe = 24h
| dataset = xdr_data
| filter event_type = ENUM.NETWORK and action_remote_ip != null
| filter not incidr(action_remote_ip, "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16")
| comp count() as connections, sum(action_total_upload) as upload by action_remote_ip
| sort desc connections
| iploc action_remote_ip loc_country, loc_city, loc_region
| fields action_remote_ip, loc_country, loc_city, loc_region, connections, upload
| limit 10
```

## When to use

External destinations enriched with country/city/region via the `iploc` stage. The geolocation columns (loc_country, loc_city, loc_region, loc_latlon, loc_timezone) are auto-added by iploc — no setup needed. Useful for surfacing unexpected geographies in outbound traffic.

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
