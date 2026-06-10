---
id: XQL-394-2fb78b29
title: PANW NGFW | Top 10 Destination Zones by Blocked Traffic
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

# PANW NGFW | Top 10 Destination Zones by Blocked Traffic

**Dataset**: `panw_ngfw_traffic_raw`

```sql
config timeframe = 30d
| dataset = panw_ngfw_traffic_raw
| filter action in ("deny","block")
| comp count() as blocked_count by to_zone
| sort desc blocked_count
| limit 10
```

## When to use

Identifies the top ten Next-Generation-Firewall (NGFW) destination zones that experienced the most blocked traffic over the last 30 days

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
