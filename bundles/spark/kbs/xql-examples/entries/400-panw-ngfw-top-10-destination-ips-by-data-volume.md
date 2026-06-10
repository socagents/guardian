---
id: XQL-400-317441b1
title: PANW NGFW | Top 10 Destination IPs by Data Volume
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

# PANW NGFW | Top 10 Destination IPs by Data Volume

**Dataset**: `panw_ngfw_traffic_raw`

```sql
config timeframe = 30d
| dataset = panw_ngfw_traffic_raw
| comp sum(bytes_received) as total_bytes_received by dest_ip
| sort desc total_bytes_received
| limit 10
```

## When to use

Identifies the top 10 Next-Generation-Firewall (NGFW)  destination IPs that received the most data in the last 30 days

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
