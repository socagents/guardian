---
id: XQL-401-b0c396c6
title: PANW NGFW | Top 10 Source-Destination Pairs by Session Count
category: investigation
dataset: panw_ngfw_traffic_raw
tags:
  - config
  - comp
  - sort
  - limit
  - panw_ngfw_traffic_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Top 10 Source-Destination Pairs by Session Count

**Dataset**: `panw_ngfw_traffic_raw`

```sql
config timeframe = 7d
| dataset = panw_ngfw_traffic_raw
| comp count() as session_count by source_ip, dest_ip
| sort desc session_count
| limit 10
```

## When to use

Identifies the top ten Next-Generation-Firewall (NGFW) source-destination IP pairs with the highest number of network sessions in the last 7 days

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
