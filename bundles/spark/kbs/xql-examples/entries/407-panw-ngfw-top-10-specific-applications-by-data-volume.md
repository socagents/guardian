---
id: XQL-407-c4f34ed6
title: PANW NGFW | Top 10 Specific Applications by Data Volume
category: investigation
dataset: panw_ngfw_traffic_raw
tags:
  - config
  - filter
  - comp
  - sort
  - limit
  - panw_ngfw_traffic_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Top 10 Specific Applications by Data Volume

**Dataset**: `panw_ngfw_traffic_raw`

```sql
config timeframe = 7d
| dataset = panw_ngfw_traffic_raw
| filter app in ($application)
| comp sum(bytes_total) as total_bytes by app
| sort desc total_bytes
| limit 10
```

## When to use

Identifies the top ten Next-Generation-Firewall (NGFW) applications generating the most network traffic (data volume) over the last 7 days, filtering by specific applications

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
