---
id: XQL-406-bf55ec14
title: PANW NGFW | Average Packets per Session by Source User
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

# PANW NGFW | Average Packets per Session by Source User

**Dataset**: `panw_ngfw_traffic_raw`

```sql
config timeframe = 30d
| dataset = panw_ngfw_traffic_raw
| comp avg(packets_total) as avg_packets_per_session by source_user
| sort desc avg_packets_per_session
```

## When to use

Calculates the average number of Next-Generation-Firewall (NGFW) packets per session for each source user in the last 30 days

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
