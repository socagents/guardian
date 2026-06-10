---
id: XQL-402-df330dfd
title: PANW NGFW | Average Bytes per Session by Source Zone
category: investigation
dataset: panw_ngfw_traffic_raw
tags:
  - config
  - comp
  - sort
  - panw_ngfw_traffic_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Average Bytes per Session by Source Zone

**Dataset**: `panw_ngfw_traffic_raw`

```sql
config timeframe = 30d
| dataset = panw_ngfw_traffic_raw
| comp avg(bytes_total) as avg_bytes_per_session by from_zone
| sort desc avg_bytes_per_session
```

## When to use

Calculates the average number of Next-Generation-Firewall (NGFW) bytes transferred per session for each source zone over the last 30 days

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
