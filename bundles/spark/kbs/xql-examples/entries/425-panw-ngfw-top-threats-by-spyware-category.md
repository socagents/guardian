---
id: XQL-425-fb428e37
title: PANW NGFW | Top Threats by Spyware Category
category: investigation
dataset: panw_ngfw_threat_raw
tags:
  - filter
  - comp
  - sort
  - panw_ngfw_threat_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Top Threats by Spyware Category

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| filter threat_category = "spyware"
| comp count() as spyware_count by threat_id, source_ip, dest_ip
| sort desc spyware_count
```

## When to use

Identifies the most frequently detected Next-Generation-Firewall (NGFW) threats categorized as spyware

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
