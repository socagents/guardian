---
id: XQL-398-e6b359c2
title: PANW NGFW | Top 10 Destination Ports by Bytes Sent
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

# PANW NGFW | Top 10 Destination Ports by Bytes Sent

**Dataset**: `panw_ngfw_traffic_raw`

```sql
config timeframe = 7d
| dataset = panw_ngfw_traffic_raw
| comp sum(bytes_sent) as total_bytes_sent by dest_port
| sort desc total_bytes_sent
| limit 10
```

## When to use

Identifies the top ten Next-Generation-Firewall (NGFW) destination ports that received the most data in the last 7 days

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
