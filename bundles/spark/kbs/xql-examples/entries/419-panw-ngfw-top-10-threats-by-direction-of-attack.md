---
id: XQL-419-e27273a8
title: PANW NGFW | Top 10 Threats by Direction of Attack
category: investigation
dataset: panw_ngfw_threat_raw
tags:
  - comp
  - sort
  - limit
  - panw_ngfw_threat_raw
  - source:dataset
  - operator-authored
---

# PANW NGFW | Top 10 Threats by Direction of Attack

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| comp count() as threat_count by direction_of_attack
| sort desc threat_count
| limit 10
```

## When to use

Categorizes the top ten Next-Generation-Firewall (NGFW) threats based on their direction of attack

## Variations

_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_

## Source

Operator-authored, exported from XSIAM tenant by amahmoud@paloaltonetworks.com. Imported as part of the v0.6.51 operator-dataset bulk import (see CHANGELOG). The `When to use` description above was carried over from the operator's XSIAM-saved-query `description` field. Original creation: 2025-04-06.
