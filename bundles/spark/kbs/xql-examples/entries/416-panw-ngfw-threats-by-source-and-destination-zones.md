---
id: XQL-416-66bb8912
title: PANW NGFW | Threats by Source and Destination Zones
category: investigation
dataset: panw_ngfw_threat_raw
tags:
  - comp
  - sort
  - panw_ngfw_threat_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Threats by Source and Destination Zones

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| comp count() as threat_count by from_zone, to_zone
| sort desc threat_count
```

## When to use

Calculates which Next-Generation-Firewall (NGFW) network zones most frequently involve the detection of threats

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
