---
id: XQL-391-d95243c1
title: PANW NGFW |  Allowed vs. Denied Traffic Distribution
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

# PANW NGFW |  Allowed vs. Denied Traffic Distribution

**Dataset**: `panw_ngfw_traffic_raw`

```sql
config timeframe = 7d
| dataset = panw_ngfw_traffic_raw
| comp count() as action_count by action
| sort desc action_count
```

## When to use

Calculates the distribution of Next-Generation-Firewall (NGFW) allowed vs. denied traffic in the last 7 days by analyzing firewall actions

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
